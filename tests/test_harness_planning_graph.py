from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from anvil.harness.builder import build_harness_langgraph
from anvil.harness.state import initialize_harness_state


def _write_workspace_file(workspace: Path, relative_path: str, content: str) -> None:
    path = workspace / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_planning_workspace(
    workspace: Path,
    *,
    include_hint_matches: bool = True,
) -> None:
    if not include_hint_matches:
        _write_workspace_file(workspace, "README.md", "# workspace\n")
        return

    _write_workspace_file(workspace, "PLAN.md", "# C1 planning package\n")
    _write_workspace_file(
        workspace,
        "anvil/harness/builder.py",
        "def build_harness_langgraph():\n    return 'planning_v1'\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/strategy_graph.py",
        "PLANNING_RUNTIME_TARGET = 'planning_v1'\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/planning_runtime.py",
        "def execute_planning_runtime(state):\n    return state\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/reporting.py",
        "def publish_state_artifacts_v1(state):\n    return state\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/artifacts.py",
        "def artifact_description(name):\n    return name\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/report.py",
        "def render_report(summary):\n    return summary\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/subgraphs/planning_v1.py",
        "def planning_v1_subgraph(state):\n    return state\n",
    )


def _planning_state(tmp_path: Path) -> dict[str, Any]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    state = initialize_harness_state(
        task_path=str(tmp_path / "task.yaml"),
        strategy_path=str(tmp_path / "strategy.yaml"),
        workspace_root=str(workspace),
        out_root=str(out_root),
    )
    state["run_id"] = "planning-run"
    state["thread_id"] = "thread-planning"
    state["run_dir"] = str(out_root / "planning-run")
    state["created_at"] = "2026-05-17T00:00:00+00:00"
    state["task_spec"] = {
        "id": "task-plan",
        "objective": "Plan a deterministic rollout for the planning runtime.",
        "task_kind": "planning",
        "workspace_write_policy": {"mode": "forbid"},
        "files_hint": ["PLAN.md", "anvil/harness/*"],
    }
    state["task_kind"] = "planning"  # type: ignore[assignment]
    state["strategy_spec"] = {
        "name": "deterministic planning",
        "kind": "deterministic_feature_planning_v1",
        "runtime_target": "planning_v1",
        "phases": [
            {"id": "design_doc", "stage_type": "rubric_design_doc"},
            {
                "id": "seam_decomposition",
                "stage_type": "architecture_seam_decomposition",
            },
            {
                "id": "parallel_planning",
                "stage_type": "parallel_workstream_planning",
            },
            {"id": "slice_emission", "stage_type": "executable_slice_emission"},
        ],
        "artifact_policy": "planning_package_v1",
        "determinism_policy": "stable_structure_v1",
        "discovery_policy": "bounded_repo_scan_v1",
        "rubric_policy": "design_doc_gate_v1",
        "stop_policy": "clarification_or_stop_v1",
    }
    state["strategy_kind"] = "deterministic_feature_planning_v1"  # type: ignore[assignment]
    state["config_verdict"] = "pass"
    state["validator_verdict"] = "not_applicable"
    state["policy_verdict"] = "pass"
    return state


def _planning_graph_state(
    tmp_path: Path,
    *,
    phase_inputs: dict[str, Any] | None = None,
    include_hint_matches: bool = True,
) -> dict[str, Any]:
    state = _planning_state(tmp_path)
    _seed_planning_workspace(
        Path(str(state["workspace_root"])),
        include_hint_matches=include_hint_matches,
    )
    if phase_inputs is not None:
        state["strategy_spec"] = {
            **dict(state["strategy_spec"]),
            "phase_inputs": phase_inputs,
        }
    state["strategy_graph_spec"] = {
        "runtime_target": "planning_v1",
        "post_runtime_action": "write_artifacts",
    }
    state["strategy_graph_spec_id"] = "planning_v1.test"
    state["strategy_graph_subset"] = "bounded_strategy_graph_v1"
    return state


def _run_graph(
    state: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    monkeypatch.setattr(
        "anvil.harness.builder.prepare_run_node",
        lambda payload: deepcopy(state),
    )
    monkeypatch.setattr(
        "anvil.harness.builder.validator_preflight_node",
        lambda payload: payload,
    )
    monkeypatch.setattr(
        "anvil.harness.builder.select_strategy_node",
        lambda payload: payload,
    )
    graph = build_harness_langgraph()
    return asyncio.run(
        graph.ainvoke(
            {
                "task_path": state["task_path"],
                "strategy_path": state["strategy_path"],
                "workspace_root": state["workspace_root"],
                "out_root": state["out_root"],
                "thread_id": state["thread_id"],
            },
            {"configurable": {"thread_id": str(state.get("thread_id") or "thread")}},
        )
    )


def test_planning_runtime_success_populates_frozen_state_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"
    assert result["planning_stop_reason"] is None
    assert result["run_verdict"] == "success"
    assert result["content_verdict"] == "success"
    assert result["clarification_requests"] == []
    assert "anvil/harness/subgraphs/planning_v1.py" in result["repo_evidence_refs"]
    assert [item["seam_id"] for item in result["planning_seams"]] == [
        "seam-runtime-routing",
        "seam-artifact-publication",
    ]
    assert [item["workstream_id"] for item in result["planning_workstreams"]] == [
        "workstream-runtime-wiring",
        "workstream-artifact-surface",
    ]
    assert [item["slice_id"] for item in result["planning_slices"]] == [
        "slice-mount-planning-runtime",
        "slice-publish-planning-artifacts",
    ]
    assert [item["stage_type"] for item in result["planning_phase_results"]] == [
        "rubric_design_doc",
        "architecture_seam_decomposition",
        "parallel_workstream_planning",
        "executable_slice_emission",
    ]
    assert result["planning_policy_versions"] == {
        "artifact_policy": "planning_package_v1",
        "determinism_policy": "stable_structure_v1",
        "discovery_policy": "bounded_repo_scan_v1",
        "rubric_policy": "design_doc_gate_v1",
        "stop_policy": "clarification_or_stop_v1",
    }
    assert result["search_pass_count"] == 2
    assert result["inspected_file_count"] == 8
    assert result["discovery_budget_escalated"] is True
    assert result["drafts"] == []
    assert Path(result["summary_payload"]["artifacts"]["summary_json"]).exists()
    assert result["run_details"]["planning_run_mode"] == "deterministic-live"


def test_planning_runtime_stops_for_clarification_without_fake_downstream_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(
        tmp_path,
        include_hint_matches=False,
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "clarification_needed"
    assert result["planning_stop_reason"] == "files_hint_unresolved"
    assert result["run_verdict"] == "clarification_needed"
    assert result["content_verdict"] == "clarification_needed"
    assert [item["question"] for item in result["clarification_requests"]] == [
        "Which concrete repository path or seam should the planning package inspect first?"
    ]
    assert len(result["planning_phase_results"]) == 1
    assert result["planning_phase_results"][0]["status"] == "clarification_needed"
    assert result["planning_phase_results"][0]["repo_evidence_refs"] == []
    assert result["planning_seams"] == []
    assert result["planning_workstreams"] == []
    assert result["planning_slices"] == []
    assert result["drafts"] == []
    assert result.get("best_draft_id") is None
    assert result.get("selected_draft_id") is None


def test_planning_runtime_failed_sets_explicit_stop_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)
    state["task_spec"]["objective"] = "Plan a brand-new system from scratch."

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "failed"
    assert result["planning_stop_reason"] == "planning_request_out_of_corpus"
    assert result["run_verdict"] == "failed"
    assert result["content_verdict"] == "failed"
    assert [item["status"] for item in result["planning_phase_results"]] == ["failed"]
    assert result["planning_seams"] == []
    assert result["planning_workstreams"] == []
    assert result["planning_slices"] == []


def test_planning_runtime_bypasses_select_best_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _planning_graph_state(tmp_path)

    monkeypatch.setattr(
        "anvil.harness.builder.select_best_draft_node",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("planning_v1 should route directly to write_artifacts")
        ),
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"


@pytest.mark.parametrize(
    ("fixture_mode", "expected_terminal_status"),
    [
        ("clarification_needed", "clarification_needed"),
        ("failed", "failed"),
    ],
)
def test_planning_runtime_allows_task_fixture_modes_to_override_success_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixture_mode: str,
    expected_terminal_status: str,
) -> None:
    state = _planning_graph_state(
        tmp_path,
        phase_inputs={
            "design_doc": {"repo_evidence_refs": ["PLAN.md"]},
            "seam_decomposition": {
                "planning_seams": [{"title": "Seam A", "summary": "A"}],
            },
            "parallel_planning": {
                "planning_workstreams": [{"title": "Workstream A", "summary": "A"}],
            },
            "slice_emission": {
                "planning_slices": [{"title": "Slice A", "summary": "A"}],
            },
        },
    )
    state["task_spec"]["notes"] = f"planning_fixture_mode={fixture_mode}"

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == expected_terminal_status
