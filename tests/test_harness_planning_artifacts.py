from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.harness.providers import _soft_validate_schema
from anvil.harness.reporting import publish_state_artifacts_v1
from anvil.harness.schemas import plan_json_schema


def _planning_state(tmp_path: Path, *, terminal_status: str) -> dict[str, object]:
    state: dict[str, object] = {
        "run_id": "run-plan",
        "thread_id": "thread-plan",
        "workspace_root": str(tmp_path / "workspace"),
        "run_dir": str(tmp_path / "run"),
        "created_at": "2026-05-17T00:00:00+00:00",
        "task_spec": {
            "id": "task-plan",
            "task_kind": "planning",
            "objective": "Produce a deterministic planning package.",
            "acceptance": ["Emit seams, workstreams, and slices."],
        },
        "strategy_spec": {
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
                {
                    "id": "slice_emission",
                    "stage_type": "executable_slice_emission",
                },
            ],
        },
        "strategy_kind": "deterministic_feature_planning_v1",
        "strategy_graph_spec": {
            "runtime_target": "planning_v1",
            "post_runtime_action": "write_artifacts",
        },
        "planning_terminal_status": terminal_status,
        "planning_stop_reason": (
            "" if terminal_status == "success" else f"{terminal_status}_stop_reason"
        ),
        "clarification_requests": (
            []
            if terminal_status == "success"
            else [{"question": "Which seam is in scope?"}]
        ),
        "repo_evidence_refs": ["anvil/harness/builder.py", "anvil/harness/cli.py"],
        "planning_seams": [
            {
                "seam_id": "seam-builder",
                "summary": "Builder routing seam",
                "paths": ["anvil/harness/builder.py"],
            }
        ],
        "planning_workstreams": [
            {
                "workstream_id": "workstream-routing",
                "summary": "Route planning through the shared graph",
                "seam_ids": ["seam-builder"],
                "worktree_recommended": True,
            }
        ],
        "planning_slices": [
            {
                "slice_id": "slice-routing",
                "summary": "Mount planning_v1 and bypass draft selection",
                "workstream_id": "workstream-routing",
                "seam_ids": ["seam-builder"],
                "acceptance_criteria": ["planning_v1 is mounted"],
            }
        ],
        "planning_phase_results": [
            {
                "phase_id": "rubric_design_doc",
                "status": "success",
                "summary": "Problem statement and rubric are coherent.",
            },
            {
                "phase_id": "architecture_seam_decomposition",
                "status": "success",
                "summary": "Graph routing seam isolated.",
            },
        ],
        "planning_policy_versions": {
            "artifact_policy": "planning_package_v1",
            "determinism_policy": "stable_structure_v1",
        },
        "search_pass_count": 2,
        "inspected_file_count": 4,
        "discovery_budget_escalated": False,
        "run_verdict": terminal_status,
        "content_verdict": terminal_status,
        "validator_verdict": "not_applicable",
        "policy_verdict": "pass",
        "config_verdict": "pass",
        "summary_text": "Planning summary.",
        "warnings": [],
        "errors": [],
    }
    workspace_root = Path(state["workspace_root"])
    workspace_root.mkdir(parents=True, exist_ok=True)
    for rel_path in (
        "anvil/harness/builder.py",
        "anvil/harness/cli.py",
    ):
        file_path = workspace_root / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# fixture\n", encoding="utf-8")
    return state


def test_publish_state_artifacts_v1_writes_plan_package_for_success(tmp_path: Path):
    state = _planning_state(tmp_path, terminal_status="success")

    updated = publish_state_artifacts_v1(state)
    summary = updated["summary_payload"]
    artifacts = summary["artifacts"]

    plan_json_path = Path(artifacts["plan_json"])
    plan_md_path = Path(artifacts["plan_md"])
    assert plan_json_path.exists()
    assert plan_md_path.exists()
    assert updated["artifact_index"]["plan_json"]["path"] == str(plan_json_path)
    assert updated["artifact_index"]["plan_md"]["path"] == str(plan_md_path)

    plan_payload = json.loads(plan_json_path.read_text(encoding="utf-8"))
    assert _soft_validate_schema(plan_payload, plan_json_schema()) == []
    assert plan_payload["terminal_status"] == "success"
    assert plan_payload["run_mode"] == "deterministic-live"
    assert summary["planning_terminal_status"] == "success"
    assert summary["planning_run_mode"] == "deterministic-live"
    markdown = plan_md_path.read_text(encoding="utf-8")
    assert "- Terminal status: `success`" in markdown
    assert "- Run mode: `deterministic-live`" in markdown
    assert markdown.index("## Problem Statement") < markdown.index("## Rubric Results")
    assert markdown.index("## Rubric Results") < markdown.index(
        "## Architectural Seams"
    )
    assert markdown.index("## Architectural Seams") < markdown.index(
        "## Parallel Workstreams/Worktrees"
    )
    assert markdown.index("## Parallel Workstreams/Worktrees") < markdown.index(
        "## Executable Slices"
    )


def test_publish_state_artifacts_v1_returns_terminal_payload_for_clarification(
    tmp_path: Path,
):
    state = _planning_state(tmp_path, terminal_status="clarification_needed")

    updated = publish_state_artifacts_v1(state)
    summary = updated["summary_payload"]

    assert summary["terminal_status"] == "clarification_needed"
    assert summary["clarification_requests"] == ["Which seam is in scope?"]
    assert "plan_md" not in summary["artifacts"]
    assert "plan_json" not in summary["artifacts"]
    assert "plan_md" not in updated["artifact_index"]
    assert "plan_json" not in updated["artifact_index"]


def test_publish_state_artifacts_v1_returns_failed_terminal_payload(tmp_path: Path):
    state = _planning_state(tmp_path, terminal_status="failed")

    updated = publish_state_artifacts_v1(state)
    summary = updated["summary_payload"]

    assert summary["terminal_status"] == "failed"
    assert summary["stop_reason"] == "failed_stop_reason"
    assert "plan_md" not in summary["artifacts"]
    assert "plan_json" not in summary["artifacts"]


def test_publish_state_artifacts_v1_blocks_success_when_integrity_refs_do_not_resolve(
    tmp_path: Path,
):
    state = _planning_state(tmp_path, terminal_status="success")
    state["repo_evidence_refs"] = ["missing/file.py"]

    with pytest.raises(ValueError, match="integrity checks"):
        publish_state_artifacts_v1(state)
