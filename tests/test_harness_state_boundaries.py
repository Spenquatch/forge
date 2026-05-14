from __future__ import annotations

from anvil.harness.state import (
    HARNESS_STATE_SERIALIZATION_VERSION,
    SUMMARY_BOUNDARY_VERSION,
    state_from_summary,
    summary_read_adapter_v1,
)


def _focus_decision() -> dict[str, object]:
    return {
        "decision_state": "selected",
        "selected_focus_id": "focus-1",
        "selected_focus_paths": ["src/focus.py"],
        "question": {"prompt": "", "options": []},
        "warnings": [],
    }


def test_summary_read_adapter_v1_reads_b1_boundary_fields(tmp_path):
    summary = {
        "run_id": "run-123",
        "thread_id": "thread-123",
        "workspace": "/tmp/workspace",
        "task": {"id": "task-123", "task_kind": "analysis_review"},
        "strategy_name": "analysis_review_v1",
        "strategy_kind": "analysis_review_v1",
        "serialization_version": "custom-serialization-v1",
        "summary_boundary_version": "summary_projection_v1",
        "bridge_boundary_version": "legacy_bridge_boundary_v1",
        "strategy_graph_spec": {"runtime_target": "analysis_review_v1"},
        "strategy_graph_spec_id": "analysis-review-spec",
        "strategy_graph_subset": "bounded_strategy_graph_v1",
        "artifacts": {"run_dir": str(tmp_path / "run")},
        "run_details": {
            "revisions_completed": 2,
            "analysis_review_contract": {"mode": "bounded"},
            "focus_decision": _focus_decision(),
            "topic_ledger": [
                {"topic_id": "TOPIC-1", "resolution_status": "open"}
            ],
        },
    }

    state = summary_read_adapter_v1(summary)

    assert state["serialization_version"] == "custom-serialization-v1"
    assert state["analysis_review_contract"] == {"mode": "bounded"}
    assert state["strategy_graph_spec"] == {"runtime_target": "analysis_review_v1"}
    assert state["strategy_graph_spec_id"] == "analysis-review-spec"
    assert state["strategy_graph_subset"] == "bounded_strategy_graph_v1"
    assert state["focus_decision"]["selected_focus_id"] == "focus-1"
    assert state["topic_ledger"] == [
        {"topic_id": "TOPIC-1", "resolution_status": "open"}
    ]
    assert state["summary_boundary_version"] == "summary_projection_v1"
    assert state["bridge_boundary_version"] == "legacy_bridge_boundary_v1"
    assert state["revision_round"] == 2
    assert state["summary_payload"] == summary


def test_state_from_summary_is_a_compatibility_wrapper():
    summary = {
        "run_id": "run-legacy",
        "workspace": "/tmp/workspace",
        "task": {"id": "task-legacy"},
        "strategy_kind": "single_pass",
        "artifacts": {"run_dir": ".forge-harness-runs/run-legacy"},
    }

    adapted = summary_read_adapter_v1(summary, fallback_thread_id="fallback-thread")
    wrapped = state_from_summary(summary, fallback_thread_id="fallback-thread")

    assert wrapped["run_id"] == adapted["run_id"]
    assert wrapped["thread_id"] == adapted["thread_id"]
    assert wrapped["task_spec"] == adapted["task_spec"]
    assert wrapped["strategy_kind"] == adapted["strategy_kind"]
    assert wrapped["summary_payload"] == adapted["summary_payload"]
    assert wrapped["thread_id"] == "fallback-thread"
    assert wrapped["serialization_version"] == HARNESS_STATE_SERIALIZATION_VERSION
    assert wrapped["summary_boundary_version"] == SUMMARY_BOUNDARY_VERSION
    assert wrapped["bridge_boundary_version"] is None
