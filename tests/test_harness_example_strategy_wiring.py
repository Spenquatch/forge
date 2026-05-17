from __future__ import annotations

import asyncio
import copy
from pathlib import Path

import pytest

from anvil.harness.builder import build_harness_langgraph
from anvil.harness.contracts import build_analysis_review_contract
from anvil.harness.files import load_structured_file
from anvil.harness.nodes.prepare_run import prepare_run_node
from anvil.harness.nodes.validator_preflight import validator_preflight_node
from anvil.harness.strategy_graph import (
    STRATEGY_GRAPH_SUBSET,
    build_strategy_graph_spec,
)
from anvil.harness.types import StrategyConfig, TaskSpec


def _task() -> TaskSpec:
    return TaskSpec.from_dict(
        {
            "id": "recommend_automation_improvements",
            "task_kind": "analysis_review",
            "objective": "Review the repo and recommend workflow improvements.",
            "workspace_write_policy": {"mode": "forbid"},
        }
    )


def _resolved_execution_mode(strategy_path: Path) -> str:
    strategy = StrategyConfig.from_dict(load_structured_file(strategy_path))
    contract = build_analysis_review_contract(_task(), strategy)
    return contract.trust_review.execution_mode


def _scenario_names(scenarios: list[dict[str, object]]) -> list[str]:
    return [str(scenario["name"]) for scenario in scenarios]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _planning_strategy_path() -> Path:
    return Path("examples/harness/strategies/deterministic_feature_planning_v1.yaml")


def _planning_task_path(name: str) -> Path:
    return Path(f"examples/harness/tasks/deterministic_feature_planning_{name}.yaml")


def _run_planning_example_fixture(
    task_path: Path,
    *,
    tmp_path: Path,
    run_label: str,
) -> dict[str, object]:
    raw_strategy = load_structured_file(_planning_strategy_path())
    original_prepare_run_node = prepare_run_node
    original_validator_preflight_node = validator_preflight_node

    def _with_phase_inputs(state: dict[str, object]) -> dict[str, object]:
        strategy_spec = dict(state.get("strategy_spec") or {})
        phase_inputs = raw_strategy.get("phase_inputs")
        if isinstance(phase_inputs, dict):
            strategy_spec["phase_inputs"] = copy.deepcopy(phase_inputs)
        state["strategy_spec"] = strategy_spec
        return state

    def _prepare(payload: dict[str, object]) -> dict[str, object]:
        prepared = original_prepare_run_node(payload)
        return _with_phase_inputs(prepared)

    def _validator(payload: dict[str, object]) -> dict[str, object]:
        validated = original_validator_preflight_node(payload)
        return _with_phase_inputs(validated)

    out_root = tmp_path / run_label
    out_root.mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("anvil.harness.builder.prepare_run_node", _prepare)
        monkeypatch.setattr(
            "anvil.harness.builder.validator_preflight_node",
            _validator,
        )
        graph = build_harness_langgraph()
        return asyncio.run(
            graph.ainvoke(
                {
                    "task_path": str(task_path),
                    "strategy_path": str(_planning_strategy_path()),
                    "workspace_root": str(_repo_root()),
                    "out_root": str(out_root),
                    "thread_id": f"thread-{run_label}",
                },
                {"configurable": {"thread_id": f"thread-{run_label}"}},
            )
        )


def _plan_payload(summary: dict[str, object]) -> dict[str, object]:
    artifacts = dict(summary["artifacts"])
    return load_structured_file(Path(str(artifacts["plan_json"])))


def _planning_ids(
    plan_payload: dict[str, object],
) -> tuple[list[str], list[str], list[str]]:
    seams = [str(item["seam_id"]) for item in plan_payload["seams"]]
    workstreams = [str(item["workstream_id"]) for item in plan_payload["workstreams"]]
    slices = [str(item["slice_id"]) for item in plan_payload["slices"]]
    return seams, workstreams, slices


def test_focus_gate_adjudicate_examples_clone_base_analysis_review_strategies():
    cases = [
        (
            Path(
                "examples/harness/strategies/analysis_review_bounded_codex_claude.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-bounded-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude-focus-gate-adjudicate",
        ),
    ]

    for base_path, derived_path, expected_name in cases:
        base_strategy = load_structured_file(base_path)
        derived_strategy = load_structured_file(derived_path)

        expected_strategy = dict(base_strategy)
        expected_strategy["name"] = expected_name
        expected_strategy["focus_gate"] = {
            "enabled": True,
            "default_path": "adjudicate",
        }

        assert derived_strategy == expected_strategy


def test_canonical_trust_examples_match_attestation_source_of_truth():
    cases = [
        (
            Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
            Path(
                "examples/harness/strategies/analysis_review_trust_attestation_codex_claude.yaml"
            ),
            "analysis-review-trust-codex-claude",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml"
            ),
            "analysis-review-trust-codex-claude-focus-gate-deliberate",
        ),
    ]

    for canonical_path, source_path, expected_name in cases:
        canonical_strategy = load_structured_file(canonical_path)
        source_strategy = load_structured_file(source_path)

        expected_strategy = dict(source_strategy)
        expected_strategy["name"] = expected_name

        assert canonical_strategy == expected_strategy
        assert _resolved_execution_mode(canonical_path) == "attestation_over_bounded"


def test_explicit_legacy_trust_compatibility_examples_resolve_legacy_full_review():
    cases = [
        (
            Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude_focus_gate_deliberate.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude-focus-gate-deliberate",
        ),
    ]

    for canonical_path, compatibility_path, expected_name in cases:
        canonical_strategy = load_structured_file(canonical_path)
        compatibility_strategy = load_structured_file(compatibility_path)

        expected_strategy = dict(canonical_strategy)
        expected_strategy["name"] = expected_name
        expected_strategy["trust_review"] = {"execution_mode": "legacy_full_review"}

        assert compatibility_strategy == expected_strategy
        assert _resolved_execution_mode(compatibility_path) == "legacy_full_review"


def test_analysis_review_entry_points_document_attestation_first_canonical_trust():
    examples_readme = Path("examples/README.md").read_text(encoding="utf-8")
    root_readme = Path("README.md").read_text(encoding="utf-8")
    run_script = Path("examples/harness/run_analysis_review_codex_claude.sh").read_text(
        encoding="utf-8"
    )
    canonical_template = Path(
        "examples/harness/live_acceptance/focus_gate_acceptance.template.yaml"
    ).read_text(encoding="utf-8")
    local_template = Path(
        "examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml"
    ).read_text(encoding="utf-8")
    compatibility_template = Path(
        "examples/harness/live_acceptance/m2_focus_gate_local.template.yaml"
    ).read_text(encoding="utf-8")

    canonical_trust_path = (
        "examples/harness/strategies/"
        "analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
    )

    assert canonical_trust_path in examples_readme
    assert "attestation-first" in examples_readme
    assert "analysis_review_trust_legacy_*" in examples_readme
    assert "legacy_full_review" in examples_readme
    assert "[Examples](examples/README.md)" in root_readme
    assert canonical_trust_path in run_script
    assert "attestation-first" in run_script
    assert "analysis_review_trust_legacy_*" in run_script
    assert "poetry run python -m anvil.cli harness-run" in run_script
    assert canonical_trust_path in canonical_template
    assert canonical_trust_path in local_template
    assert canonical_trust_path in compatibility_template
    assert "attestation-first" in canonical_template
    assert "attestation-first" in local_template
    assert "attestation-first" in compatibility_template
    assert "analysis_review_trust_legacy_*" in canonical_template
    assert "analysis_review_trust_legacy_*" in local_template
    assert "analysis_review_trust_legacy_*" in compatibility_template


def test_focus_gate_live_acceptance_templates_still_target_canonical_trust_example():
    canonical_manifest = load_structured_file(
        Path("examples/harness/live_acceptance/focus_gate_acceptance.template.yaml")
    )
    local_manifest = load_structured_file(
        Path(
            "examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml"
        )
    )
    compatibility_manifest = load_structured_file(
        Path("examples/harness/live_acceptance/m2_focus_gate_local.template.yaml")
    )

    canonical_shards = {
        shard["name"]: shard["scenarios"] for shard in canonical_manifest["shards"]
    }
    seam_deliberate = canonical_shards["seam-deliberate"]
    assert _scenario_names(seam_deliberate) == [
        "deliberate-refined-success",
        "deliberate-refinement-exhausted",
        "stale-rerun",
    ]
    assert seam_deliberate[0]["expected_decision_state"] == "selected"
    assert seam_deliberate[0]["expect_proposer_artifacts"] is True
    assert seam_deliberate[0]["expect_downstream_bridge"] is True
    assert seam_deliberate[1]["task"] == (
        "examples/harness/tasks/recommend_automation_improvements_never_ask.yaml"
    )
    assert seam_deliberate[1]["expected_decision_state"] == "no_viable_focus"
    assert seam_deliberate[1]["expect_proposer_artifacts"] is False
    assert seam_deliberate[1]["expect_downstream_bridge"] is False
    assert _scenario_names(canonical_shards["artifact-deliberate"]) == [
        "artifact-deliberate-ambiguity",
        "artifact-never-ask",
        "artifact-stale-rerun",
    ]

    local_seam_deliberate = [
        scenario
        for scenario in local_manifest["scenarios"]
        if scenario["expected_gate_path"] == "deliberate"
        and scenario["expected_focus_type"] == "seam"
    ]
    assert _scenario_names(local_seam_deliberate) == [
        "deliberate-refined-success",
        "deliberate-refinement-exhausted",
        "stale-rerun",
    ]

    assert (
        canonical_manifest["default_task"]
        == "examples/harness/tasks/recommend_automation_improvements.yaml"
    )
    assert local_manifest["task"] == canonical_manifest["default_task"]
    assert compatibility_manifest["task"] == canonical_manifest["default_task"]
    assert compatibility_manifest["strategies"] == {
        "bounded": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
        "trust": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
    }
    assert (
        _resolved_execution_mode(Path(compatibility_manifest["strategies"]["trust"]))
        == "attestation_over_bounded"
    )


def test_m2_focus_gate_fixture_wiring_triads_resolve_task_strategy_and_workspace():
    triads = load_structured_file(
        Path("tests/fixtures/harness/m2_focus_gate_fixture_wiring/triads.yaml")
    )

    assert triads["fixture_namespace"] == "m2_focus_gate_fixture_wiring"
    assert triads["fixture_purpose"] == "seam_regression_only_wiring_coverage"

    for case in triads["cases"]:
        task_path = Path(case["task"])
        strategy_path = Path(case["strategy"])
        workspace_path = Path(case["workspace"])

        assert task_path.exists(), case["name"]
        assert strategy_path.exists(), case["name"]
        assert workspace_path.exists(), case["name"]

        task = load_structured_file(task_path)
        strategy = load_structured_file(strategy_path)

        assert task["id"] == "recommend_automation_improvements"
        assert task["task_kind"] == "analysis_review"
        assert strategy["kind"] == case["expected_strategy_kind"]
        assert strategy["focus_gate"] == {
            "enabled": True,
            "default_path": "adjudicate",
        }

        for workspace_ref in task["files_hint"]:
            matches = list(workspace_path.glob(workspace_ref))
            assert matches, (case["name"], workspace_ref)


def test_example_strategies_resolve_to_expected_internal_graph_family_metadata():
    cases = [
        (
            "examples/harness/strategies/single_pass_codex.yaml",
            "single_pass",
            "single_pass",
            ["solver"],
        ),
        (
            "examples/harness/strategies/pfr_codex_claude.yaml",
            "pfr_v1",
            "pfr_v1",
            ["proposer", "falsifier", "patcher"],
        ),
        (
            "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
            "analysis_review_bounded_v1",
            "analysis_review_v1",
            ["focus_gate", "proposer", "critic", "reviser", "auditor"],
        ),
        (
            "examples/harness/strategies/analysis_review_trust_codex_claude.yaml",
            "analysis_review_trust_v1",
            "analysis_review_v1",
            ["proposer", "critic", "reviser", "auditor", "attestation_auditor"],
        ),
        (
            "examples/harness/strategies/deterministic_feature_planning_v1.yaml",
            "deterministic_feature_planning_v1",
            "planning_v1",
            [
                "design_doc",
                "seam_decomposition",
                "parallel_planning",
                "slice_emission",
            ],
        ),
    ]

    for path, expected_kind, expected_runtime_target, expected_stage_ids in cases:
        strategy = load_structured_file(Path(path))
        spec = build_strategy_graph_spec(expected_kind, strategy).to_dict()

        assert spec["subset"] == STRATEGY_GRAPH_SUBSET
        assert spec["strategy_kind"] == expected_kind
        assert spec["runtime_target"] == expected_runtime_target
        assert [stage["stage_id"] for stage in spec["stages"]] == expected_stage_ids


def test_planning_example_strategy_matches_frozen_surface_and_graph_metadata(
    tmp_path: Path,
):
    raw_strategy = load_structured_file(_planning_strategy_path())
    phase_inputs = raw_strategy.pop("phase_inputs")
    parsed = StrategyConfig.from_dict(raw_strategy | {"phase_inputs": phase_inputs})
    spec = build_strategy_graph_spec(raw_strategy["kind"], raw_strategy).to_dict()
    prepared = prepare_run_node(
        {
            "task_path": str(_planning_task_path("success")),
            "strategy_path": str(_planning_strategy_path()),
            "workspace_root": str(_repo_root()),
            "out_root": str(tmp_path),
        }
    )
    validated = validator_preflight_node(
        {
            **prepared,
            "warnings": [],
            "errors": [],
            "auto_fit_strategy": True,
        }
    )

    assert list(phase_inputs) == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]
    assert parsed.name == raw_strategy["name"]
    assert parsed.kind == raw_strategy["kind"]
    assert parsed.runtime_target == raw_strategy["runtime_target"]
    assert list(parsed.roles) == ["planner"]
    assert [phase.id for phase in parsed.phases] == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]
    assert [phase.stage_type for phase in parsed.phases] == [
        "rubric_design_doc",
        "architecture_seam_decomposition",
        "parallel_workstream_planning",
        "executable_slice_emission",
    ]
    assert spec["subset"] == STRATEGY_GRAPH_SUBSET
    assert spec["strategy_kind"] == "deterministic_feature_planning_v1"
    assert spec["runtime_target"] == "planning_v1"
    assert spec["post_runtime_action"] == "write_artifacts"
    assert [stage["stage_id"] for stage in spec["stages"]] == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]
    assert list(prepared["strategy_spec"]["phase_inputs"]) == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]
    assert list(validated["strategy_spec"]["phase_inputs"]) == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]


def test_planning_example_tasks_cover_success_clarification_and_failed_modes():
    cases = [
        (_planning_task_path("success"), ""),
        (
            _planning_task_path("clarification"),
            "planning_fixture_mode=clarification_needed",
        ),
        (_planning_task_path("failed"), "planning_fixture_mode=failed"),
    ]

    for task_path, expected_fixture_mode in cases:
        task_payload = load_structured_file(task_path)
        task = TaskSpec.from_dict(task_payload)

        assert task.task_kind == "planning"
        assert task.workspace_write_policy.mode == "forbid"
        assert task.files_hint
        if expected_fixture_mode:
            assert expected_fixture_mode in str(task_payload.get("notes") or "")
        else:
            assert "planning_fixture_mode=" not in str(task_payload.get("notes") or "")


def test_planning_example_fixture_corpus_proves_all_terminal_outcomes(tmp_path: Path):
    success_state = _run_planning_example_fixture(
        _planning_task_path("success"),
        tmp_path=tmp_path,
        run_label="success",
    )
    clarification_state = _run_planning_example_fixture(
        _planning_task_path("clarification"),
        tmp_path=tmp_path,
        run_label="clarification",
    )
    failed_state = _run_planning_example_fixture(
        _planning_task_path("failed"),
        tmp_path=tmp_path,
        run_label="failed",
    )

    success_summary = dict(success_state["summary_payload"])
    clarification_summary = dict(clarification_state["summary_payload"])
    failed_summary = dict(failed_state["summary_payload"])
    success_plan = _plan_payload(success_summary)

    assert success_summary["terminal_status"] == "success"
    assert Path(str(success_summary["artifacts"]["plan_md"])).exists()
    assert Path(str(success_summary["artifacts"]["plan_json"])).exists()
    assert success_plan["terminal_status"] == "success"
    assert len(success_plan["seams"]) == 2
    assert len(success_plan["workstreams"]) == 2
    assert len(success_plan["slices"]) == 2

    assert clarification_summary["terminal_status"] == "clarification_needed"
    assert clarification_summary["clarification_requests"]
    assert "plan_md" not in clarification_summary["artifacts"]
    assert "plan_json" not in clarification_summary["artifacts"]

    assert failed_summary["terminal_status"] == "failed"
    assert failed_summary["stop_reason"] == "design_doc_failed"
    assert "plan_md" not in failed_summary["artifacts"]
    assert "plan_json" not in failed_summary["artifacts"]


def test_planning_example_success_repeat_runs_preserve_stable_ids(
    tmp_path: Path,
):
    observed_ids = []

    for attempt in range(3):
        state = _run_planning_example_fixture(
            _planning_task_path("success"),
            tmp_path=tmp_path,
            run_label=f"success-repeat-{attempt}",
        )
        summary = dict(state["summary_payload"])
        observed_ids.append(_planning_ids(_plan_payload(summary)))

    assert (
        observed_ids
        == [
            (
                [
                    "seam-runtime-routing",
                    "seam-artifact-publication",
                ],
                [
                    "workstream-runtime-wiring",
                    "workstream-artifact-surface",
                ],
                [
                    "slice-mount-planning-runtime",
                    "slice-publish-planning-artifacts",
                ],
            )
        ]
        * 3
    )
