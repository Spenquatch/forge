from __future__ import annotations

import json
from pathlib import Path

from anvil.harness.planning_eval import (
    EVAL_REPORT_SCHEMA_VERSION,
    build_planning_review_eval_report,
)


def _write_run(
    root: Path,
    run_id: str,
    *,
    delta_status: str,
    cited_paths: list[str],
    behavioral_gaps: list[str],
) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_payload = {
        "run_id": run_id,
        "task": {
            "id": f"task-{run_id}",
            "task_kind": "planning",
            "objective": "Produce a bounded deterministic planning package.",
        },
        "deterministic_planning_posture": "canonical_first_pass",
        "seams": [{"seam_id": "seam-01"}],
        "workstreams": [{"workstream_id": "workstream-01"}],
        "slices": [{"slice_id": "slice-01"}],
        "uncovered_delta": [],
        "provider_review": {"verdict": "accept_with_caveat"},
        "provider_review_delta": {
            "delta_status": delta_status,
            "summary": "Provider review delta summary.",
            "uncovered_cited_surfaces": [
                {
                    "path": path,
                    "gap_kind": "under_planned",
                    "reason": "Still evidence-only in the deterministic package.",
                    "linked_seam_ids": ["seam-01"],
                    "linked_workstream_ids": ["workstream-01"],
                    "linked_slice_ids": ["slice-01"],
                }
                for path in cited_paths
            ],
            "behavioral_coverage_gaps": list(behavioral_gaps),
            "expansion_candidates": [
                {
                    "candidate_kind": "slice_expansion",
                    "summary": "Expand the existing slice.",
                    "cited_paths": list(cited_paths),
                    "attach_to_seam_ids": ["seam-01"],
                    "attach_to_workstream_ids": ["workstream-01"],
                    "attach_to_slice_ids": ["slice-01"],
                }
            ],
            "follow_up_questions": [],
            "confidence": 0.8,
            "preserves_canonical_structure": True,
        },
        "provider_disagreement_count": 1 if delta_status != "none" else 0,
    }
    (run_dir / "plan.json").write_text(
        json.dumps(plan_payload, indent=2), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"workspace": "/tmp/workspace"}), encoding="utf-8"
    )
    return run_dir


def test_build_planning_review_eval_report_aggregates_recurring_misses(tmp_path: Path):
    run_a = _write_run(
        tmp_path,
        "run-a",
        delta_status="expansion_recommended",
        cited_paths=["src/report.py"],
        behavioral_gaps=["Acceptance remains too path-shaped."],
    )
    run_b = _write_run(
        tmp_path,
        "run-b",
        delta_status="expansion_recommended",
        cited_paths=["src/report.py", "src/api.py"],
        behavioral_gaps=["Acceptance remains too path-shaped."],
    )
    run_c = _write_run(
        tmp_path,
        "run-c",
        delta_status="clarification_recommended",
        cited_paths=["src/api.py"],
        behavioral_gaps=["Clarify lifecycle ownership before expansion."],
    )

    report = build_planning_review_eval_report(
        [run_a, run_b, run_c],
        holdout_run_ids=["run-c"],
        min_recurrence=2,
    )

    assert report["schema_version"] == EVAL_REPORT_SCHEMA_VERSION
    assert report["run_count"] == 3
    assert report["recommended_batch_size"] == "6-12"
    assert report["holdout_run_ids"] == ["run-c"]
    assert report["aggregates"]["delta_status_counts"] == {
        "expansion_recommended": 2,
        "clarification_recommended": 1,
    }
    assert report["aggregates"]["tuning_ready_surface_patterns"] == [
        {"path": "src/report.py", "count": 2, "run_ids": ["run-a", "run-b"]}
    ]
    assert report["aggregates"]["tuning_ready_behavioral_patterns"] == [
        {
            "gap": "Acceptance remains too path-shaped.",
            "count": 2,
            "run_ids": ["run-a", "run-b"],
        }
    ]
    assert report["runs"][0]["deterministic_planning_posture"] == (
        "canonical_first_pass"
    )
