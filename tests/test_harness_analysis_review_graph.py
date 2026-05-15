from __future__ import annotations

import asyncio
import importlib.util
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from anvil.harness.executor import HarnessLangGraphExecutor


_HELPER_MODULE_PATH = Path(__file__).with_name("test_harness_runner.py")
_HELPER_SPEC = importlib.util.spec_from_file_location(
    "test_harness_runner_helpers",
    _HELPER_MODULE_PATH,
)
assert _HELPER_SPEC is not None
assert _HELPER_SPEC.loader is not None
_HELPERS = importlib.util.module_from_spec(_HELPER_SPEC)
_HELPER_SPEC.loader.exec_module(_HELPERS)


@dataclass(frozen=True)
class _RunArtifacts:
    state: dict[str, Any]
    summary: dict[str, Any]
    summary_json: dict[str, Any]
    report_text: str
    workspace: Path
    run_dir: Path


class _TrustAttestationFocusGateHarnessAdapter(_HELPERS._TrustFocusGateHarnessAdapter):
    def run(self, request):
        if (
            request.role_name == "auditor"
            and "TRUST_ATTESTATION_REVIEW" in request.prompt_text
        ):
            payload = _HELPERS._build_corroboration_review_payload(
                summary=(
                    "The attestation review confirms the focus-selected bounded draft "
                    "stays grounded inside the frozen review surface."
                ),
                files_reviewed=self._review_files_reviewed(),
                recommendation_count=len(
                    self._base_analysis(revised=False)["recommendations"]
                ),
            )
            for item in payload["recommendation_reviews"]:
                metadata = self._trust_metadata()[int(item["recommendation_index"])]
                item["checked_files"] = list(metadata["checked_files"])
                item["verified_evidence_refs"] = list(
                    metadata["verified_evidence_refs"]
                )
            return _HELPERS._successful_provider_run(request, payload=payload)
        return super().run(request)


def _build_specs(
    tmp_path: Path,
    *,
    strategy_kind: str = "analysis_review_bounded_v1",
    trust_execution_mode: str | None = None,
    task_focus_gate: str = "",
    task_focus_gate_answer: str = "",
    strategy_focus_gate: str = "",
    include_focus_gate_role: bool = False,
    auto_fit_strategy: bool = True,
) -> tuple[Path, Path, Path, bool]:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = tmp_path / "workspace_seed"
    workspace_root.mkdir(parents=True, exist_ok=True)
    workspace = _HELPERS._prepare_workspace(workspace_root)
    task_path, strategy_path = _HELPERS._write_task_and_strategy(
        specs_dir,
        strategy_kind=strategy_kind,
        trust_execution_mode=trust_execution_mode,
        task_focus_gate=task_focus_gate,
        task_focus_gate_answer=task_focus_gate_answer,
        strategy_focus_gate=strategy_focus_gate,
        include_focus_gate_role=include_focus_gate_role,
    )
    return task_path, strategy_path, workspace, auto_fit_strategy


def _run_executor_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider_factory,
    checkpoint: str,
    execution_mode: str,
    strategy_kind: str = "analysis_review_bounded_v1",
    trust_execution_mode: str | None = None,
    task_focus_gate: str = "",
    task_focus_gate_answer: str = "",
    strategy_focus_gate: str = "",
    include_focus_gate_role: bool = False,
    auto_fit_strategy: bool = True,
) -> _RunArtifacts:
    task_path, strategy_path, workspace, auto_fit_strategy = _build_specs(
        tmp_path,
        strategy_kind=strategy_kind,
        trust_execution_mode=trust_execution_mode,
        task_focus_gate=task_focus_gate,
        task_focus_gate_answer=task_focus_gate_answer,
        strategy_focus_gate=strategy_focus_gate,
        include_focus_gate_role=include_focus_gate_role,
        auto_fit_strategy=auto_fit_strategy,
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.subgraphs.analysis_review_v1.reload_config",
        lambda path: ({}, {}),
    )
    if provider_factory is not None:
        monkeypatch.setattr("anvil.harness.runner.get_provider", provider_factory)

    out_root = tmp_path / f"out-{checkpoint}-{execution_mode}"
    executor = HarnessLangGraphExecutor(
        checkpoint=checkpoint,
        db_path=str(tmp_path / f"{checkpoint}-{execution_mode}.sqlite"),
        analysis_review_execution_mode=execution_mode,
    )
    state = asyncio.run(
        executor.execute(
            task_path=str(task_path),
            strategy_path=str(strategy_path),
            workspace=str(workspace),
            out_root=str(out_root),
            auto_fit_strategy=auto_fit_strategy,
        )
    )
    summary = dict(state["summary_payload"])
    summary_json_path = Path(summary["artifacts"]["summary_json"])
    report_path = Path(summary["artifacts"]["report_md"])
    return _RunArtifacts(
        state=state,
        summary=summary,
        summary_json=json.loads(summary_json_path.read_text(encoding="utf-8")),
        report_text=report_path.read_text(encoding="utf-8"),
        workspace=workspace,
        run_dir=Path(summary["artifacts"]["run_dir"]),
    )


def _scenario_tmp_path(
    tmp_path: Path,
    *,
    checkpoint: str,
    execution_mode: str,
) -> Path:
    scenario_path = tmp_path / checkpoint / execution_mode
    scenario_path.mkdir(parents=True, exist_ok=True)
    return scenario_path


def _normalize_value(value: Any, *, run_dir: Path, workspace: Path) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"run_id", "thread_id", "created_at"}:
                normalized[key] = f"<{key}>"
                continue
            if key == "run_details" and isinstance(item, dict):
                item = deepcopy(item)
                item.pop("graph_execution", None)
            if key == "metadata" and isinstance(item, dict):
                item = deepcopy(item)
                item.pop("graph_node_id", None)
                item.pop("semantic_validation_outcome", None)
                item.pop("execution_mode", None)
            normalized[key] = _normalize_value(
                item,
                run_dir=run_dir,
                workspace=workspace,
            )
        return normalized
    if isinstance(value, list):
        return [
            _normalize_value(item, run_dir=run_dir, workspace=workspace)
            for item in value
        ]
    if isinstance(value, str):
        text = value
        text = text.replace(str(run_dir), "<RUN_DIR>")
        text = text.replace(str(workspace), "<WORKSPACE>")
        return text
    return value


def _normalized_summary(run: _RunArtifacts) -> dict[str, Any]:
    return _normalize_value(run.summary, run_dir=run.run_dir, workspace=run.workspace)


def _normalized_summary_json(run: _RunArtifacts) -> dict[str, Any]:
    return _normalize_value(
        run.summary_json,
        run_dir=run.run_dir,
        workspace=run.workspace,
    )


def _strip_run_details_section(report_text: str) -> str:
    return re.sub(
        r"\n## Run Details\n.*?(?=\n## |\Z)",
        "\n",
        report_text,
        flags=re.S,
    )


def _normalized_report(run: _RunArtifacts) -> str:
    normalized = run.report_text.replace(str(run.workspace), "<WORKSPACE>")
    normalized = normalized.replace(str(run.run_dir), "<RUN_DIR>")
    return _strip_run_details_section(normalized)


def _stage_roles(summary: dict[str, Any]) -> list[str]:
    return [str(stage["role_name"]) for stage in summary.get("agent_stages", [])]


def _stage_graph_ids(summary: dict[str, Any]) -> list[str]:
    graph_ids: list[str] = []
    for stage in summary.get("agent_stages", []):
        metadata = stage.get("metadata") if isinstance(stage, dict) else None
        graph_ids.append(str((metadata or {}).get("graph_stage_id") or ""))
    return graph_ids


def _stage_payload_triplets(summary: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    triplets: list[tuple[str, Any, Any]] = []
    for stage in summary.get("agent_stages", []):
        raw_json_path = stage.get("raw_json_path")
        normalized_json_path = stage.get("normalized_json_path")
        if raw_json_path in {None, ""} or normalized_json_path in {None, ""}:
            continue
        triplets.append(
            (
                str(stage["role_name"]),
                json.loads(Path(raw_json_path).read_text(encoding="utf-8")),
                json.loads(Path(normalized_json_path).read_text(encoding="utf-8")),
            )
        )
    return triplets


def _artifact_payloads(summary: dict[str, Any]) -> dict[str, Any]:
    artifacts = summary.get("artifacts") or {}
    payloads: dict[str, Any] = {
        "final_artifact_kind": artifacts.get("final_artifact_kind"),
    }
    for key in (
        "final_answer_json",
        "partial_answer_json",
        "best_draft_json",
        "issue_ledger_json",
    ):
        artifact_path = artifacts.get(key)
        if artifact_path:
            payloads[key] = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    for key in ("final_answer_md", "partial_answer_md", "best_draft_md"):
        artifact_path = artifacts.get(key)
        if artifact_path:
            payloads[key] = Path(artifact_path).read_text(encoding="utf-8")
    return payloads


def _assert_common_parity(
    legacy_run: _RunArtifacts,
    graph_run: _RunArtifacts,
    *,
    expected_role_names: list[str],
) -> None:
    assert _stage_roles(legacy_run.summary) == expected_role_names
    assert _stage_roles(graph_run.summary) == expected_role_names
    assert _stage_payload_triplets(legacy_run.summary) == _stage_payload_triplets(
        graph_run.summary
    )
    assert (
        legacy_run.summary["verdicts"]["policy_verdict"]
        == graph_run.summary["verdicts"]["policy_verdict"]
    )
    assert legacy_run.summary.get("workspace_policy_checks") == graph_run.summary.get(
        "workspace_policy_checks"
    )
    assert _artifact_payloads(legacy_run.summary) == _artifact_payloads(
        graph_run.summary
    )
    assert _normalized_summary(legacy_run) == _normalized_summary(graph_run)
    assert _normalized_summary_json(legacy_run) == _normalized_summary_json(graph_run)
    assert _normalized_report(legacy_run) == _normalized_report(graph_run)


@pytest.mark.parametrize("checkpoint", ["memory", "sqlite"])
def test_b2_parity_matrix_bounded_no_focus_gate_matches_legacy_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checkpoint: str,
) -> None:
    legacy_run = _run_executor_case(
        _scenario_tmp_path(tmp_path, checkpoint=checkpoint, execution_mode="legacy"),
        monkeypatch,
        provider_factory=lambda name: _HELPERS._AcceptingHarnessAdapter(),
        checkpoint=checkpoint,
        execution_mode="legacy_bridge",
    )
    graph_run = _run_executor_case(
        _scenario_tmp_path(tmp_path, checkpoint=checkpoint, execution_mode="graph"),
        monkeypatch,
        provider_factory=lambda name: _HELPERS._AcceptingHarnessAdapter(),
        checkpoint=checkpoint,
        execution_mode="graph_owned",
    )

    _assert_common_parity(
        legacy_run,
        graph_run,
        expected_role_names=["proposer", "critic", "reviser_round_1", "auditor"],
    )
    assert legacy_run.summary["analysis_review_status"] == graph_run.summary[
        "analysis_review_status"
    ]
    assert legacy_run.summary["issue_ledger"] == graph_run.summary["issue_ledger"]
    assert legacy_run.summary["topic_ledger"] == graph_run.summary["topic_ledger"]
    assert legacy_run.summary["recommendation_reviews"] == graph_run.summary[
        "recommendation_reviews"
    ]


@pytest.mark.parametrize(
    ("scenario_name", "adapter_factory", "task_focus_gate", "strategy_focus_gate", "trust_execution_mode", "strategy_kind", "expected_role_names", "expected_graph_stage_ids", "expected_decision_state"),
    [
        (
            "bounded-focus-selected",
            lambda name: _HELPERS._FocusGateHarnessAdapter(),
            _HELPERS._task_focus_gate_block(),
            _HELPERS._strategy_focus_gate_block(default_path="adjudicate"),
            None,
            "analysis_review_bounded_v1",
            ["focus_gate", "proposer", "critic", "reviser_round_1", "auditor"],
            ["focus_gate", "proposer", "critic", "reviser", "auditor"],
            "selected",
        ),
        (
            "bounded-focus-blocked",
            lambda name: _HELPERS._FocusGateHarnessAdapter(),
            _HELPERS._task_focus_gate_block(),
            _HELPERS._strategy_focus_gate_block(default_path="deliberate"),
            None,
            "analysis_review_bounded_v1",
            ["focus_gate_probe", "focus_gate"],
            ["focus_gate_probe", "focus_gate"],
            "clarification_requested",
        ),
        (
            "bounded-no-viable-focus",
            lambda name: _HELPERS._NoViableFocusHarnessAdapter(),
            _HELPERS._task_focus_gate_block(),
            _HELPERS._strategy_focus_gate_block(default_path="adjudicate"),
            None,
            "analysis_review_bounded_v1",
            ["focus_gate"],
            ["focus_gate"],
            "no_viable_focus",
        ),
        (
            "trust-attestation-focus-on",
            lambda name: _TrustAttestationFocusGateHarnessAdapter(),
            _HELPERS._task_focus_gate_block(),
            _HELPERS._strategy_focus_gate_block(default_path="adjudicate"),
            "attestation_over_bounded",
            "analysis_review_trust_v1",
            ["focus_gate", "proposer", "critic", "reviser_round_1", "auditor", "auditor"],
            [
                "focus_gate",
                "proposer",
                "critic",
                "reviser",
                "auditor",
                "attestation_auditor",
            ],
            "selected",
        ),
    ],
    ids=[
        "bounded-focus-selected",
        "bounded-focus-blocked",
        "bounded-no-viable-focus",
        "trust-attestation-focus-on",
    ],
)
def test_b2_parity_matrix_focus_gate_rows_match_legacy_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario_name: str,
    adapter_factory,
    task_focus_gate: str,
    strategy_focus_gate: str,
    trust_execution_mode: str | None,
    strategy_kind: str,
    expected_role_names: list[str],
    expected_graph_stage_ids: list[str],
    expected_decision_state: str,
) -> None:
    legacy_run = _run_executor_case(
        _scenario_tmp_path(
            tmp_path / scenario_name,
            checkpoint="memory",
            execution_mode="legacy",
        ),
        monkeypatch,
        provider_factory=adapter_factory,
        checkpoint="memory",
        execution_mode="legacy_bridge",
        strategy_kind=strategy_kind,
        trust_execution_mode=trust_execution_mode,
        task_focus_gate=task_focus_gate,
        strategy_focus_gate=strategy_focus_gate,
        include_focus_gate_role=True,
    )
    graph_run = _run_executor_case(
        _scenario_tmp_path(
            tmp_path / scenario_name,
            checkpoint="memory",
            execution_mode="graph",
        ),
        monkeypatch,
        provider_factory=adapter_factory,
        checkpoint="memory",
        execution_mode="graph_owned",
        strategy_kind=strategy_kind,
        trust_execution_mode=trust_execution_mode,
        task_focus_gate=task_focus_gate,
        strategy_focus_gate=strategy_focus_gate,
        include_focus_gate_role=True,
    )

    _assert_common_parity(
        legacy_run,
        graph_run,
        expected_role_names=expected_role_names,
    )
    assert legacy_run.summary["focus_decision"] == graph_run.summary["focus_decision"]
    assert legacy_run.summary["focus_decision"]["decision_state"] == expected_decision_state
    assert graph_run.summary["focus_decision"]["decision_state"] == expected_decision_state

    if expected_decision_state in {"clarification_requested", "no_viable_focus"}:
        assert "proposer" not in _stage_roles(legacy_run.summary)
        assert "proposer" not in _stage_roles(graph_run.summary)
        assert legacy_run.summary["verdict"] == graph_run.summary["verdict"]
    else:
        assert legacy_run.summary["analysis_review_status"] == graph_run.summary[
            "analysis_review_status"
        ]
        assert legacy_run.summary["issue_ledger"] == graph_run.summary["issue_ledger"]
        assert legacy_run.summary["topic_ledger"] == graph_run.summary["topic_ledger"]
        assert legacy_run.summary["recommendation_reviews"] == graph_run.summary[
            "recommendation_reviews"
        ]
        assert _stage_graph_ids(graph_run.summary) == expected_graph_stage_ids


def test_b2_parity_matrix_trust_attestation_focus_off_matches_legacy_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_run = _run_executor_case(
        _scenario_tmp_path(tmp_path, checkpoint="memory", execution_mode="legacy"),
        monkeypatch,
        provider_factory=lambda name: _HELPERS._TrustAttestationHarnessAdapter(),
        checkpoint="memory",
        execution_mode="legacy_bridge",
        strategy_kind="analysis_review_trust_v1",
        trust_execution_mode="attestation_over_bounded",
    )
    graph_run = _run_executor_case(
        _scenario_tmp_path(tmp_path, checkpoint="memory", execution_mode="graph"),
        monkeypatch,
        provider_factory=lambda name: _HELPERS._TrustAttestationHarnessAdapter(),
        checkpoint="memory",
        execution_mode="graph_owned",
        strategy_kind="analysis_review_trust_v1",
        trust_execution_mode="attestation_over_bounded",
    )

    _assert_common_parity(
        legacy_run,
        graph_run,
        expected_role_names=[
            "proposer",
            "critic",
            "reviser_round_1",
            "auditor",
            "auditor",
        ],
    )
    assert legacy_run.summary["analysis_review_status"] == graph_run.summary[
        "analysis_review_status"
    ]
    assert legacy_run.summary["issue_ledger"] == graph_run.summary["issue_ledger"]
    assert legacy_run.summary["topic_ledger"] == graph_run.summary["topic_ledger"]
    assert legacy_run.summary["recommendation_reviews"] == graph_run.summary[
        "recommendation_reviews"
    ]
    assert _stage_graph_ids(graph_run.summary) == [
        "proposer",
        "critic",
        "reviser",
        "auditor",
        "attestation_auditor",
    ]
    assert legacy_run.summary[_HELPERS.BOUNDED_ATTESTATION_INPUT_KEY] == graph_run.summary[
        _HELPERS.BOUNDED_ATTESTATION_INPUT_KEY
    ]


@pytest.mark.parametrize("execution_mode", ["legacy_bridge", "graph_owned"])
def test_b2_parity_matrix_invalid_config_preflight_still_routes_to_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    execution_mode: str,
) -> None:
    run = _run_executor_case(
        _scenario_tmp_path(
            tmp_path,
            checkpoint="memory",
            execution_mode=execution_mode,
        ),
        monkeypatch,
        provider_factory=None,
        checkpoint="memory",
        execution_mode=execution_mode,
        strategy_kind="pfr_v1",
        auto_fit_strategy=False,
    )

    assert run.state["config_verdict"] == "invalid_config"
    assert run.summary["verdict"] == "invalid_config"
    assert run.summary["verdicts"]["config_verdict"] == "invalid_config"
    assert run.summary["artifacts"]["summary_json"]
    assert run.summary["artifacts"]["report_md"]
    assert _stage_roles(run.summary) == []


@pytest.mark.parametrize("execution_mode", ["legacy_bridge", "graph_owned"])
def test_b2_parity_matrix_checkpoint_backends_share_user_visible_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    execution_mode: str,
) -> None:
    memory_run = _run_executor_case(
        _scenario_tmp_path(tmp_path, checkpoint="memory", execution_mode=execution_mode),
        monkeypatch,
        provider_factory=lambda name: _HELPERS._AcceptingHarnessAdapter(),
        checkpoint="memory",
        execution_mode=execution_mode,
    )
    sqlite_run = _run_executor_case(
        _scenario_tmp_path(tmp_path, checkpoint="sqlite", execution_mode=execution_mode),
        monkeypatch,
        provider_factory=lambda name: _HELPERS._AcceptingHarnessAdapter(),
        checkpoint="sqlite",
        execution_mode=execution_mode,
    )

    assert _stage_roles(memory_run.summary) == _stage_roles(sqlite_run.summary)
    assert _stage_graph_ids(memory_run.summary) == _stage_graph_ids(sqlite_run.summary)
    assert _stage_payload_triplets(memory_run.summary) == _stage_payload_triplets(
        sqlite_run.summary
    )
    assert _artifact_payloads(memory_run.summary) == _artifact_payloads(
        sqlite_run.summary
    )
    assert _normalized_summary(memory_run) == _normalized_summary(sqlite_run)
    assert _normalized_summary_json(memory_run) == _normalized_summary_json(sqlite_run)
    assert _normalized_report(memory_run) == _normalized_report(sqlite_run)
