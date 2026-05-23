from __future__ import annotations

"""Evaluation helpers for provider-reviewed deterministic planning runs."""

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EVAL_REPORT_SCHEMA_VERSION = "planning_review_eval_report_v1"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def planning_review_eval_entry(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    plan_payload = _load_json(run_path / "plan.json")
    summary_payload = _load_json(run_path / "summary.json")
    task_payload = (
        plan_payload.get("task")
        if isinstance(plan_payload.get("task"), dict)
        else summary_payload.get("task")
    ) or {}
    provider_review = (
        plan_payload.get("provider_review")
        if isinstance(plan_payload.get("provider_review"), dict)
        else summary_payload.get("planning_provider_review")
    ) or {}
    provider_review_delta = (
        plan_payload.get("provider_review_delta")
        if isinstance(plan_payload.get("provider_review_delta"), dict)
        else summary_payload.get("planning_provider_review_delta")
    ) or {}

    return {
        "run_id": str(
            plan_payload.get("run_id") or summary_payload.get("run_id") or ""
        ),
        "run_dir": str(run_path),
        "workspace": str(summary_payload.get("workspace") or ""),
        "task_id": str(task_payload.get("id") or ""),
        "objective": str(task_payload.get("objective") or ""),
        "deterministic_planning_posture": str(
            plan_payload.get("deterministic_planning_posture")
            or summary_payload.get("planning_deterministic_planning_posture")
            or ""
        ),
        "deterministic_seam_ids": [
            str(item.get("seam_id") or "")
            for item in _dict_list(
                plan_payload.get("seams") or summary_payload.get("planning_seams")
            )
            if str(item.get("seam_id") or "").strip()
        ],
        "deterministic_workstream_ids": [
            str(item.get("workstream_id") or "")
            for item in _dict_list(
                plan_payload.get("workstreams")
                or summary_payload.get("planning_workstreams")
            )
            if str(item.get("workstream_id") or "").strip()
        ],
        "deterministic_slice_ids": [
            str(item.get("slice_id") or "")
            for item in _dict_list(
                plan_payload.get("slices") or summary_payload.get("planning_slices")
            )
            if str(item.get("slice_id") or "").strip()
        ],
        "deterministic_uncovered_delta_ids": [
            str(item.get("delta_id") or "")
            for item in _dict_list(
                plan_payload.get("uncovered_delta")
                or summary_payload.get("planning_uncovered_delta")
            )
            if str(item.get("delta_id") or "").strip()
        ],
        "provider_review_verdict": str(provider_review.get("verdict") or ""),
        "provider_review_delta_status": str(
            provider_review_delta.get("delta_status") or "none"
        ),
        "provider_review_delta_summary": str(
            provider_review_delta.get("summary") or ""
        ),
        "cited_but_unplanned_surfaces": [
            str(item.get("path") or "")
            for item in _dict_list(
                provider_review_delta.get("uncovered_cited_surfaces")
            )
            if str(item.get("path") or "").strip()
        ],
        "behavioral_coverage_gaps": _string_list(
            provider_review_delta.get("behavioral_coverage_gaps")
        ),
        "expansion_candidate_kinds": [
            str(item.get("candidate_kind") or "")
            for item in _dict_list(provider_review_delta.get("expansion_candidates"))
            if str(item.get("candidate_kind") or "").strip()
        ],
        "follow_up_questions": _string_list(
            provider_review_delta.get("follow_up_questions")
        ),
        "provider_disagreement_count": int(
            plan_payload.get("provider_disagreement_count")
            or summary_payload.get("planning_provider_disagreement_count")
            or 0
        ),
    }


def build_planning_review_eval_report(
    run_dirs: list[str | Path],
    *,
    holdout_run_ids: list[str] | None = None,
    min_recurrence: int = 2,
) -> dict[str, Any]:
    holdout_ids = {
        str(item).strip() for item in holdout_run_ids or [] if str(item).strip()
    }
    entries = [planning_review_eval_entry(run_dir) for run_dir in run_dirs]

    delta_status_counts = Counter(
        str(item.get("provider_review_delta_status") or "none") for item in entries
    )
    recurring_surface_runs: dict[str, list[str]] = defaultdict(list)
    recurring_gap_runs: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        run_id = str(entry.get("run_id") or "")
        if run_id in holdout_ids:
            continue
        for path in _string_list(entry.get("cited_but_unplanned_surfaces")):
            recurring_surface_runs[path].append(run_id)
        for gap in _string_list(entry.get("behavioral_coverage_gaps")):
            recurring_gap_runs[gap].append(run_id)

    recurring_surface_gaps = [
        {"path": path, "count": len(run_ids), "run_ids": sorted(set(run_ids))}
        for path, run_ids in sorted(recurring_surface_runs.items())
    ]
    recurring_behavioral_gaps = [
        {"gap": gap, "count": len(run_ids), "run_ids": sorted(set(run_ids))}
        for gap, run_ids in sorted(recurring_gap_runs.items())
    ]

    return {
        "schema_version": EVAL_REPORT_SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "run_count": len(entries),
        "recommended_batch_size": "6-12",
        "holdout_run_ids": sorted(holdout_ids),
        "promotion_rule": (
            "Promote deterministic heuristics only when the same miss pattern recurs "
            f"across at least {min_recurrence} non-holdout runs."
        ),
        "runs": entries,
        "aggregates": {
            "delta_status_counts": dict(delta_status_counts),
            "recurring_surface_gaps": recurring_surface_gaps,
            "recurring_behavioral_gaps": recurring_behavioral_gaps,
            "tuning_ready_surface_patterns": [
                item
                for item in recurring_surface_gaps
                if int(item["count"]) >= min_recurrence
            ],
            "tuning_ready_behavioral_patterns": [
                item
                for item in recurring_behavioral_gaps
                if int(item["count"]) >= min_recurrence
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a structured evaluation report for provider-reviewed deterministic planning runs."
        )
    )
    parser.add_argument(
        "run_dirs",
        nargs="+",
        help="Run directories containing plan.json or summary.json.",
    )
    parser.add_argument(
        "--holdout-run-id",
        action="append",
        default=[],
        help="Run ID to treat as holdout for tuning-promotion counts. Repeatable.",
    )
    parser.add_argument(
        "--min-recurrence",
        type=int,
        default=2,
        help="Minimum non-holdout recurrence count needed before a miss pattern is tuning-ready.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the report JSON. Defaults to stdout.",
    )
    args = parser.parse_args(argv)
    report = build_planning_review_eval_report(
        list(args.run_dirs),
        holdout_run_ids=list(args.holdout_run_id),
        min_recurrence=max(1, int(args.min_recurrence)),
    )
    rendered = json.dumps(report, indent=2, sort_keys=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
