from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from anvil.harness.builder import build_harness_langgraph
from anvil.harness.state import initialize_harness_state


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
    phase_inputs: dict[str, Any],
) -> dict[str, Any]:
    state = _planning_state(tmp_path)
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
    state = _planning_graph_state(
        tmp_path,
        phase_inputs={
            "design_doc": {
                "repo_evidence_refs": [
                    "anvil/harness/builder.py",
                    "anvil/harness/planning_runtime.py",
                ],
                "search_pass_count": 1,
                "inspected_file_count": 2,
                "summary": "The design doc gate passed with bounded repo evidence.",
            },
            "seam_decomposition": {
                "repo_evidence_refs": ["anvil/harness/subgraphs/planning_v1.py"],
                "search_pass_count": 1,
                "inspected_file_count": 3,
                "planning_seams": [
                    {
                        "title": "Graph Routing",
                        "summary": "Mount the shared runtime target in the builder.",
                        "dependency_reasoning": ["Unblocks the shared graph path."],
                        "ambiguity_flags": [],
                    },
                    {
                        "title": "Terminal State",
                        "summary": "Populate frozen planning fields directly in graph-owned state.",
                        "dependency_reasoning": ["Needed before artifact publication."],
                        "ambiguity_flags": [],
                    },
                ],
            },
            "parallel_planning": {
                "search_pass_count": 2,
                "inspected_file_count": 4,
                "planning_workstreams": [
                    {
                        "title": "Runtime Wiring",
                        "summary": "Builder and runtime mounting changes.",
                        "dependency_reasoning": ["Depends on the graph routing seam."],
                        "ambiguity_flags": [],
                    },
                    {
                        "title": "Coverage",
                        "summary": "Planning graph tests for terminal outcomes.",
                        "dependency_reasoning": ["Depends on runtime-owned state fields."],
                        "ambiguity_flags": [],
                    },
                ],
            },
            "slice_emission": {
                "search_pass_count": 1,
                "inspected_file_count": 2,
                "discovery_budget_escalated": True,
                "planning_slices": [
                    {
                        "title": "Mount planning_v1",
                        "summary": "Add the planning subgraph and shared post-runtime routing.",
                        "dependency_reasoning": ["Requires the Graph Routing seam."],
                        "ambiguity_flags": [],
                    },
                    {
                        "title": "Record planning terminals",
                        "summary": "Persist success, clarification, and failed outcomes honestly.",
                        "dependency_reasoning": ["Requires Terminal State seam."],
                        "ambiguity_flags": [],
                    },
                ],
            },
        },
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"
    assert result["planning_stop_reason"] is None
    assert result["run_verdict"] == "success"
    assert result["content_verdict"] == "success"
    assert result["clarification_requests"] == []
    assert len(result["repo_evidence_refs"]) == 3
    assert [item["title"] for item in result["planning_seams"]] == [
        "Graph Routing",
        "Terminal State",
    ]
    assert [item["title"] for item in result["planning_workstreams"]] == [
        "Runtime Wiring",
        "Coverage",
    ]
    assert [item["title"] for item in result["planning_slices"]] == [
        "Mount planning_v1",
        "Record planning terminals",
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
    assert result["search_pass_count"] == 5
    assert result["inspected_file_count"] == 11
    assert result["discovery_budget_escalated"] is True
    assert result["drafts"] == []
    assert Path(result["summary_payload"]["artifacts"]["summary_json"]).exists()


def test_planning_runtime_stops_for_clarification_without_fake_downstream_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(
        tmp_path,
        phase_inputs={
            "design_doc": {
                "repo_evidence_refs": ["PLAN.md"],
                "status": "clarification_needed",
                "stop_reason": "rubric_scope_ambiguous",
                "clarification_requests": [
                    {
                        "question": "Which user journey should the planning package prioritize first?",
                        "rationale": "The objective names multiple surfaces without a primary path.",
                    }
                ],
                "ambiguity_flags": ["multiple_candidate_entrypoints"],
            }
        },
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "clarification_needed"
    assert result["planning_stop_reason"] == "rubric_scope_ambiguous"
    assert result["run_verdict"] == "clarification_needed"
    assert result["content_verdict"] == "clarification_needed"
    assert [item["question"] for item in result["clarification_requests"]] == [
        "Which user journey should the planning package prioritize first?"
    ]
    assert len(result["planning_phase_results"]) == 1
    assert result["planning_phase_results"][0]["status"] == "clarification_needed"
    assert result["planning_workstreams"] == []
    assert result["planning_slices"] == []
    assert result["drafts"] == []
    assert result.get("best_draft_id") is None
    assert result.get("selected_draft_id") is None


def test_planning_runtime_failed_sets_explicit_stop_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(
        tmp_path,
        phase_inputs={
            "design_doc": {
                "repo_evidence_refs": ["PLAN.md"],
            },
            "seam_decomposition": {
                "status": "failed",
                "stop_reason": "seam_signal_insufficient",
                "repo_evidence_refs": ["anvil/harness/state.py"],
            },
        },
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "failed"
    assert result["planning_stop_reason"] == "seam_signal_insufficient"
    assert result["run_verdict"] == "failed"
    assert result["content_verdict"] == "failed"
    assert [item["status"] for item in result["planning_phase_results"]] == [
        "success",
        "failed",
    ]
    assert result["planning_workstreams"] == []
    assert result["planning_slices"] == []


def test_planning_runtime_bypasses_select_best_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
