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
            "coverage_policy": "measurable_coverage_v1",
            "determinism_policy": "stable_structure_v1",
        },
        "planning_coverage_status": terminal_status,
        "planning_coverage_ledger": [
            {
                "coverage_id": "coverage-01-problem_frame",
                "dimension": "problem_frame",
                "status": "covered" if terminal_status == "success" else "partial",
                "summary": "Task objective and acceptance shape are explicit.",
                "evidence_refs": ["anvil/harness/builder.py"],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": ["slice-routing"] if terminal_status == "success" else [],
                "assumption_ids": [] if terminal_status == "success" else ["assumption-01-problem-frame"],
                "source_phase_ids": ["design_doc"],
            },
            {
                "coverage_id": "coverage-02-repo_surface",
                "dimension": "repo_surface",
                "status": "covered",
                "summary": "Repo surface is grounded.",
                "evidence_refs": ["anvil/harness/builder.py", "anvil/harness/cli.py"],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "assumption_ids": [],
                "source_phase_ids": ["design_doc"],
            },
            {
                "coverage_id": "coverage-03-seam_selection",
                "dimension": "seam_selection",
                "status": "covered",
                "summary": "A seam was selected.",
                "evidence_refs": ["anvil/harness/builder.py"],
                "seam_ids": ["seam-builder"],
                "workstream_ids": [],
                "slice_ids": [],
                "assumption_ids": [],
                "source_phase_ids": ["seam_decomposition"],
            },
            {
                "coverage_id": "coverage-04-dependency_shape",
                "dimension": "dependency_shape",
                "status": "covered" if terminal_status == "success" else "partial",
                "summary": "Dependency reasoning is attached to emitted planning structure.",
                "evidence_refs": ["anvil/harness/cli.py"],
                "seam_ids": ["seam-builder"],
                "workstream_ids": ["workstream-routing"],
                "slice_ids": ["slice-routing"],
                "assumption_ids": [] if terminal_status == "success" else ["assumption-02-dependency-shape"],
                "source_phase_ids": ["parallel_planning", "slice_emission"],
            },
            {
                "coverage_id": "coverage-05-execution_partitioning",
                "dimension": "execution_partitioning",
                "status": "covered",
                "summary": "Execution partitioning is explicit.",
                "evidence_refs": [],
                "seam_ids": ["seam-builder"],
                "workstream_ids": ["workstream-routing"],
                "slice_ids": [],
                "assumption_ids": [],
                "source_phase_ids": ["parallel_planning"],
            },
            {
                "coverage_id": "coverage-06-acceptance_shape",
                "dimension": "acceptance_shape",
                "status": "covered",
                "summary": "Acceptance criteria exist on emitted slices.",
                "evidence_refs": ["planning_v1 is mounted"],
                "seam_ids": [],
                "workstream_ids": ["workstream-routing"],
                "slice_ids": ["slice-routing"],
                "assumption_ids": [],
                "source_phase_ids": ["slice_emission"],
            },
            {
                "coverage_id": "coverage-07-risk_and_unknowns",
                "dimension": "risk_and_unknowns",
                "status": "covered" if terminal_status == "success" else "partial",
                "summary": "Risk posture is explicit for the bounded run.",
                "evidence_refs": ["anvil/harness/builder.py"],
                "seam_ids": ["seam-builder"],
                "workstream_ids": [],
                "slice_ids": [],
                "assumption_ids": [] if terminal_status == "success" else ["assumption-03-risk-and-unknowns"],
                "source_phase_ids": ["design_doc"],
            },
        ],
        "planning_assumptions_register": (
            []
            if terminal_status == "success"
            else [
                {
                    "assumption_id": "assumption-01-problem-frame",
                    "statement": "The problem frame will stabilize after clarification.",
                    "kind": "acceptance",
                    "status": "active",
                    "linked_coverage_ids": ["coverage-01-problem_frame"],
                    "evidence_refs": ["Which seam is in scope?"],
                    "source_phase_id": "design_doc",
                },
                {
                    "assumption_id": "assumption-02-dependency-shape",
                    "statement": "Dependency edges remain provisional until publication completes.",
                    "kind": "dependency",
                    "status": "active",
                    "linked_coverage_ids": ["coverage-04-dependency_shape"],
                    "evidence_refs": ["anvil/harness/cli.py"],
                    "source_phase_id": "parallel_planning",
                },
                {
                    "assumption_id": "assumption-03-risk-and-unknowns",
                    "statement": "Residual risks remain pending the blocked-run outcome.",
                    "kind": "risk",
                    "status": "active",
                    "linked_coverage_ids": ["coverage-07-risk_and_unknowns"],
                    "evidence_refs": ["Which seam is in scope?"],
                    "source_phase_id": "design_doc",
                },
            ]
        ),
        "planning_uncovered_delta": (
            []
            if terminal_status == "success"
            else [
                {
                    "delta_id": "delta-01-problem_frame",
                    "coverage_id": "coverage-01-problem_frame",
                    "dimension": "problem_frame",
                    "gap_kind": "ambiguous_scope",
                    "required_input": "Explicit acceptance criteria.",
                    "recommended_next_phase": "clarify",
                    "blocking_assumption_ids": ["assumption-01-problem-frame"],
                },
                {
                    "delta_id": "delta-02-dependency_shape",
                    "coverage_id": "coverage-04-dependency_shape",
                    "dimension": "dependency_shape",
                    "gap_kind": "assumption_blocked",
                    "required_input": "Confirmed dependency reasoning.",
                    "recommended_next_phase": "parallel_planning",
                    "blocking_assumption_ids": ["assumption-02-dependency-shape"],
                },
                {
                    "delta_id": "delta-03-risk_and_unknowns",
                    "coverage_id": "coverage-07-risk_and_unknowns",
                    "dimension": "risk_and_unknowns",
                    "gap_kind": "assumption_blocked",
                    "required_input": "Clarified residual risk posture.",
                    "recommended_next_phase": "clarify",
                    "blocking_assumption_ids": ["assumption-03-risk-and-unknowns"],
                },
            ]
        ),
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
    markdown = plan_md_path.read_text(encoding="utf-8")
    assert _soft_validate_schema(plan_payload, plan_json_schema()) == []
    assert plan_payload["schema_version"] == "plan_artifact_v2"
    assert plan_payload["terminal_status"] == "success"
    assert plan_payload["run_mode"] == "deterministic-live"
    assert plan_payload["coverage_status"] == "success"
    assert [row["dimension"] for row in plan_payload["coverage_ledger"]] == [
        "problem_frame",
        "repo_surface",
        "seam_selection",
        "dependency_shape",
        "execution_partitioning",
        "acceptance_shape",
        "risk_and_unknowns",
    ]
    assert markdown.index("## Executable Slices") < markdown.index("## Coverage Ledger")
    assert markdown.index("## Coverage Ledger") < markdown.index("## Assumptions Register")
    assert markdown.index("## Assumptions Register") < markdown.index("## Uncovered Delta")
    assert summary["planning_terminal_status"] == "success"
    assert summary["planning_run_mode"] == "deterministic-live"
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
    assert summary["coverage_status"] == "clarification_needed"
    assert len(summary["coverage_ledger"]) == 7
    assert summary["assumptions_register"]
    assert summary["uncovered_delta"]
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
    assert summary["coverage_status"] == "failed"
    assert len(summary["coverage_ledger"]) == 7
    assert "plan_md" not in summary["artifacts"]
    assert "plan_json" not in summary["artifacts"]


def test_publish_state_artifacts_v1_blocks_success_when_integrity_refs_do_not_resolve(
    tmp_path: Path,
):
    state = _planning_state(tmp_path, terminal_status="success")
    state["repo_evidence_refs"] = ["missing/file.py"]

    with pytest.raises(ValueError, match="integrity checks"):
        publish_state_artifacts_v1(state)


def test_publish_state_artifacts_v1_blocks_success_on_coverage_cardinality_drift(
    tmp_path: Path,
):
    state = _planning_state(tmp_path, terminal_status="success")
    state["planning_coverage_ledger"] = list(state["planning_coverage_ledger"][:-1])

    with pytest.raises(ValueError, match="integrity checks"):
        publish_state_artifacts_v1(state)


def test_publish_state_artifacts_v1_blocks_success_on_invalid_delta_target(
    tmp_path: Path,
):
    state = _planning_state(tmp_path, terminal_status="success")
    state["planning_uncovered_delta"] = [
        {
            "delta_id": "delta-01-problem_frame",
            "coverage_id": "coverage-02-repo_surface",
            "dimension": "repo_surface",
            "gap_kind": "missing_evidence",
            "required_input": "Extra repo evidence.",
            "recommended_next_phase": "design_doc",
            "blocking_assumption_ids": [],
        }
    ]

    with pytest.raises(ValueError, match="integrity checks"):
        publish_state_artifacts_v1(state)
