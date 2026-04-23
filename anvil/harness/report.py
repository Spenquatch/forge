from __future__ import annotations

import json
from typing import Any

from .topic_lifecycle import topic_ids_for_status_name, topic_status_field_name

_FULLY_ACCEPTED_CONTENT_VERDICTS = {"accepted", "accepted_with_warnings"}
_CANONICAL_ADMISSIBILITY_REASONS = {
    "accepted_with_caveat",
    "inferred_grounding",
    "not_accepted",
    "topic_blocked",
}


def _render_policy_list(items: list[str]) -> str:
    values = [str(item) for item in items if str(item).strip()]
    return ", ".join(values) if values else "none"


def _bounded_review_summary(summary: dict[str, Any]) -> dict[str, Any]:
    bounded_review = summary.get("bounded_review_summary")
    if isinstance(bounded_review, dict) and bounded_review:
        return bounded_review
    run_details = summary.get("run_details") or {}
    bounded_review = run_details.get("bounded_review_summary")
    if isinstance(bounded_review, dict) and bounded_review:
        return bounded_review
    return {}


def _sanitize_run_details_for_report(run_details: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(run_details)
    if "bounded_review_summary" in sanitized:
        sanitized["bounded_review_summary"] = {
            "rendered_in_report_section": True,
            "mode": (
                sanitized.get("bounded_review_summary", {}).get("mode")
                if isinstance(sanitized.get("bounded_review_summary"), dict)
                else None
            ),
        }
    return sanitized


def _analysis_review_status(summary: dict[str, Any]) -> dict[str, Any]:
    status = summary.get("analysis_review_status")
    if isinstance(status, dict) and status:
        return status
    run_details = summary.get("run_details") or {}
    status = run_details.get("analysis_review_status")
    if isinstance(status, dict) and status:
        return status
    return {}


def _topic_ledger(summary: dict[str, Any]) -> list[dict[str, Any]]:
    topic_ledger = summary.get("topic_ledger")
    if isinstance(topic_ledger, list):
        return [item for item in topic_ledger if isinstance(item, dict)]
    run_details = summary.get("run_details") or {}
    topic_ledger = run_details.get("topic_ledger")
    if isinstance(topic_ledger, list):
        return [item for item in topic_ledger if isinstance(item, dict)]
    return []


def _render_id_list(items: list[str]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return "none"
    return ", ".join(f"`{item}`" for item in values)


def _normalized_recommendation_indices(raw_items: Any) -> list[int]:
    indices: list[int] = []
    for item in raw_items or []:
        try:
            indices.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _render_recommendation_index_list(items: list[int]) -> str:
    if not items:
        return "none"
    return ", ".join(f"`{item}`" for item in items)


def _topic_status_ids(summary: dict[str, Any], *, status_name: str) -> list[str]:
    status = _analysis_review_status(summary)
    field_name = topic_status_field_name(status_name)
    raw_ids = status.get(field_name)
    if isinstance(raw_ids, list):
        return sorted(str(item).strip() for item in raw_ids if str(item).strip())

    return topic_ids_for_status_name(_topic_ledger(summary), status_name=status_name)


def _topic_summary_text(topic: dict[str, Any]) -> str:
    title = str(topic.get("title") or "").strip()
    evidence = str(topic.get("evidence") or "").strip()
    repair_hint = str(topic.get("repair_hint") or "").strip()
    if title and title.lower() != "topic":
        return title
    if evidence:
        return evidence
    if repair_hint:
        return repair_hint
    return title or "Topic"


def _topic_source_role(topic: dict[str, Any]) -> str:
    introduced_by = str(topic.get("introduced_by") or "").strip()
    return introduced_by or "unknown"


def _render_cap_usage(used: Any, cap: Any) -> str:
    used_value = 0 if used is None else used
    if cap is None:
        return f"`{used_value}` / `n/a`"
    return f"`{used_value}` / `{cap}`"


def _table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _render_provenance_preview(items: Any) -> str:
    values = [str(item).strip() for item in (items or []) if str(item).strip()]
    if not values:
        return "n/a"
    preview = values[:2]
    rendered = ", ".join(preview)
    remaining = len(values) - len(preview)
    if remaining > 0:
        rendered += f" (+{remaining} more)"
    return rendered


def _render_publishability_fallback(status: dict[str, Any]) -> str:
    # Defensive report rendering for legacy fixtures or malformed summaries.
    content_verdict = str(status.get("content_verdict") or "").strip()
    if content_verdict and content_verdict not in _FULLY_ACCEPTED_CONTENT_VERDICTS:
        return f"not applicable because content verdict is `{content_verdict}`"
    return "withheld due to non-publishable run state"


def _append_review_scope_section(lines: list[str], summary: dict[str, Any]) -> None:
    bounded_review = _bounded_review_summary(summary)
    if not bounded_review:
        return

    lines.append("## Review Scope")
    lines.append("")
    lines.append(f"- Mode: `{bounded_review.get('mode', 'unknown')}`")
    lines.append(
        "- Review surfaces declared: "
        f"`{bounded_review.get('recommendations_with_review_surface', 0)}` / "
        f"`{bounded_review.get('recommendation_count', 0)}` recommendations"
    )
    lines.append(f"- Total scope escapes: `{bounded_review.get('scope_escape_count', 0)}`")
    lines.append("")

    review_stages = bounded_review.get("review_stages") or []
    if review_stages:
        lines.append("### Review Stages")
        lines.append("")
        for stage in review_stages:
            role_name = stage.get("role_name") or "reviewer"
            round_index = stage.get("round_index", 0)
            new_topic_count = stage.get("new_topic_count", stage.get("missing_topic_count"))
            new_topic_cap = stage.get("new_topic_cap", stage.get("missing_topic_cap"))
            lines.append(f"- `{role_name}` round `{round_index}`")
            lines.append(
                "  - Issue cap/usage: "
                f"{_render_cap_usage(stage.get('issue_count'), stage.get('issue_cap'))}"
            )
            lines.append(
                "  - New-topic cap/usage: "
                f"{_render_cap_usage(new_topic_count, new_topic_cap)}"
            )
            lines.append(
                "  - Topic lifecycle: "
                f"new `{new_topic_count or 0}`, "
                f"resolved `{stage.get('resolved_topic_count', 0)}`, "
                f"carried forward `{stage.get('carried_forward_topic_count', 0)}`, "
                f"waived `{stage.get('waived_topic_count', 0)}`, "
                f"open `{stage.get('open_topic_count', 0)}`"
            )
            lines.append(
                "  - Auditor new medium+ cap/usage: "
                f"{_render_cap_usage(stage.get('new_medium_or_higher_issue_count'), stage.get('new_medium_or_higher_issue_cap'))}"
            )
            lines.append(f"  - Scope escapes: `{stage.get('scope_escape_count', 0)}`")
        lines.append("")

    scope_escapes = bounded_review.get("scope_escapes") or []
    if scope_escapes:
        lines.append("### Scope Escapes")
        lines.append("")
        for item in scope_escapes:
            role_name = item.get("role_name") or "reviewer"
            round_index = item.get("round_index", 0)
            path = item.get("path") or "workspace"
            reason = item.get("reason") or "No reason provided."
            lines.append(f"- `{role_name}` round `{round_index}` — `{path}`: {reason}")
        lines.append("")


def _append_analysis_review_status_section(lines: list[str], summary: dict[str, Any]) -> None:
    status = _analysis_review_status(summary)
    if not status:
        return

    provenance = status.get("provenance") or {}
    publishability = status.get("publishability") or {}
    lines.append("## Analysis Review Status")
    lines.append("")
    lines.append(f"- Mode: `{status.get('mode', 'unknown')}`")
    lines.append(f"- Content verdict: `{status.get('content_verdict', 'unknown')}`")
    if publishability:
        lines.append(
            "- Final publication: "
            + (
                "`publishable`"
                if publishability.get("final_answer_publishable")
                else "`blocked`"
            )
        )
        blocking_causes = [
            str(item).strip()
            for item in (publishability.get("blocking_causes") or [])
            if str(item).strip()
        ]
        if publishability.get("final_answer_publishable"):
            lines.append("- Publication blockers: none")
        else:
            lines.append(
                "- Publication blockers: "
                + (
                    "; ".join(blocking_causes)
                    if blocking_causes
                    else _render_publishability_fallback(status)
                )
            )
    lines.append(f"- Provenance status: `{provenance.get('status', 'unknown')}`")
    lines.append(f"- Provenance policy: `{provenance.get('policy_mode', 'none')}`")
    lines.append(f"- Provenance required: `{provenance.get('required', False)}`")
    lines.append(f"- Semantic warnings: `{status.get('semantic_warning_count', 0)}`")
    topic_ledger_count = status.get("topic_ledger_count")
    open_topic_ids = _topic_status_ids(summary, status_name="open")
    carried_forward_topic_ids = _topic_status_ids(summary, status_name="carried_forward")
    waived_topic_ids = _topic_status_ids(summary, status_name="waived")
    resolved_topic_ids = _topic_status_ids(summary, status_name="resolved")
    disagreed_topic_ids = _topic_status_ids(summary, status_name="disagreed")
    effective_count = topic_ledger_count
    if effective_count is None:
        effective_count = len(_topic_ledger(summary))
    if (
        effective_count
        or open_topic_ids
        or carried_forward_topic_ids
        or waived_topic_ids
        or resolved_topic_ids
        or disagreed_topic_ids
    ):
        lines.append(f"- Topic ledger count: `{effective_count}`")
        lines.append(f"- Open topic IDs: {_render_id_list(open_topic_ids)}")
        lines.append(
            "- Carried-forward topic IDs: " + _render_id_list(carried_forward_topic_ids)
        )
        lines.append(f"- Resolved topic IDs: {_render_id_list(resolved_topic_ids)}")
        lines.append(f"- Waived topic IDs: {_render_id_list(waived_topic_ids)}")
        lines.append(f"- Disagreed topic IDs: {_render_id_list(disagreed_topic_ids)}")
    downgrade_causes = status.get("downgrade_causes") or []
    if downgrade_causes:
        lines.append("- Downgrade causes:")
        for item in downgrade_causes:
            lines.append(f"  - {item}")
    caveat_indices = status.get("accepted_recommendations_with_caveats") or []
    if caveat_indices:
        lines.append(
            "- Accepted recommendations with caveats: "
            + ", ".join(str(item) for item in caveat_indices)
        )
    inferred_indices = status.get("accepted_recommendations_with_inferred_grounding") or []
    if inferred_indices:
        lines.append(
            "- Accepted recommendations with inference-only grounding: "
            + ", ".join(str(item) for item in inferred_indices)
        )
    recommendation_admissibility = status.get("recommendation_admissibility") or {}
    if isinstance(recommendation_admissibility, dict) and recommendation_admissibility:
        final_indices = _normalized_recommendation_indices(
            recommendation_admissibility.get("final_answer_recommendation_indices")
        )
        partial_only_indices = _normalized_recommendation_indices(
            recommendation_admissibility.get("partial_only_recommendation_indices")
        )
        excluded_indices = _normalized_recommendation_indices(
            recommendation_admissibility.get("excluded_recommendation_indices")
        )
        reasons_by_index = recommendation_admissibility.get("reasons_by_recommendation_index") or {}
        lines.append(
            "- Final-answer admissible recommendation indices: "
            + _render_recommendation_index_list(final_indices)
        )
        lines.append(
            "- Partial-only admissible recommendation indices: "
            + _render_recommendation_index_list(partial_only_indices)
        )
        lines.append(
            "- Excluded recommendation indices: "
            + _render_recommendation_index_list(excluded_indices)
        )
        rendered_reason_lines: list[str] = []
        for raw_index in sorted(reasons_by_index, key=lambda item: int(item)):
            normalized_reasons = [
                str(reason).strip()
                for reason in (reasons_by_index.get(raw_index) or [])
                if str(reason).strip() in _CANONICAL_ADMISSIBILITY_REASONS
            ]
            if not normalized_reasons:
                continue
            rendered_reason_lines.append(
                f"  - `{raw_index}`: " + ", ".join(f"`{reason}`" for reason in normalized_reasons)
            )
        if rendered_reason_lines:
            lines.append("- Recommendation admissibility reasons:")
            lines.extend(rendered_reason_lines)

    semantic_warnings = status.get("semantic_warnings") or []
    if semantic_warnings:
        lines.append("")
        lines.append("### Final Semantic Warnings")
        lines.append("")
        for item in semantic_warnings:
            lines.append(
                f"- Stage `{item.get('stage_index')}` `{item.get('role_name')}`: {item.get('warning')}"
            )

    provenance_stages = provenance.get("stages") or []
    if any(
        str(item.get("status") or "").strip().lower() in {"bound", "insufficient"}
        for item in provenance_stages
    ):
        lines.append("")
        lines.append("### Provenance Binding")
        lines.append("")
        for item in provenance_stages:
            digest = str(item.get("payload_sha256") or "").strip()
            digest_text = digest[:12] if digest else "n/a"
            lines.append(
                f"- `{item.get('surface')}` via stage `{item.get('stage_index')}` `{item.get('role_name')}`: "
                f"`{item.get('status', 'unknown')}` (sha `{digest_text}`, refs `{item.get('normalized_ref_count', 0)}` across `{item.get('normalized_ref_field_count', 0)}` field(s))"
            )
    lines.append("")


def _append_review_provenance_section(lines: list[str], summary: dict[str, Any]) -> None:
    status = _analysis_review_status(summary)
    if not status:
        return
    provenance = status.get("provenance") or {}
    provenance_stages = provenance.get("stages") or []
    review_stage = next(
        (item for item in provenance_stages if str(item.get("surface") or "") == "review"),
        {},
    )
    recommendation_ref_count = review_stage.get(
        "recommendation_review_ref_count",
        provenance.get("recommendation_review_ref_count", 0),
    )
    issue_ref_count = provenance.get(
        "issue_closure_review_ref_count",
        review_stage.get("issue_closure_review_ref_count", 0),
    )
    topic_ref_count = provenance.get(
        "topic_closure_review_ref_count",
        review_stage.get("topic_closure_review_ref_count", 0),
    )
    closure_complete_issue_ids = provenance.get("closure_complete_issue_ids") or review_stage.get(
        "closure_complete_issue_ids",
        [],
    )
    closure_complete_topic_ids = provenance.get("closure_complete_topic_ids") or review_stage.get(
        "closure_complete_topic_ids",
        [],
    )
    uncovered_recommendation_indices = provenance.get(
        "uncovered_recommendation_indices"
    ) or review_stage.get("uncovered_recommendation_indices", [])
    uncovered_global_issue_ids = provenance.get("uncovered_global_issue_ids") or review_stage.get(
        "uncovered_global_issue_ids",
        [],
    )
    uncovered_global_topic_ids = provenance.get("uncovered_global_topic_ids") or review_stage.get(
        "uncovered_global_topic_ids",
        [],
    )
    closure_proof_by_id = provenance.get("closure_proof_by_id") or review_stage.get(
        "closure_proof_by_id",
        {},
    )
    if not (
        recommendation_ref_count
        or issue_ref_count
        or topic_ref_count
        or closure_complete_issue_ids
        or closure_complete_topic_ids
        or uncovered_recommendation_indices
        or uncovered_global_issue_ids
        or uncovered_global_topic_ids
        or closure_proof_by_id
    ):
        return

    lines.append("## Review Provenance")
    lines.append("")
    lines.append(f"- Recommendation review refs: `{recommendation_ref_count}`")
    lines.append(f"- Issue closure review refs: `{issue_ref_count}`")
    lines.append(f"- Topic closure review refs: `{topic_ref_count}`")
    lines.append(
        "- Closure-complete issue IDs: " + _render_id_list(list(closure_complete_issue_ids))
    )
    lines.append(
        "- Closure-complete topic IDs: " + _render_id_list(list(closure_complete_topic_ids))
    )
    lines.append(
        "- Uncovered recommendation indices: "
        + _render_id_list(list(uncovered_recommendation_indices))
    )
    lines.append(
        "- Uncovered global issue IDs: " + _render_id_list(list(uncovered_global_issue_ids))
    )
    lines.append(
        "- Uncovered global topic IDs: " + _render_id_list(list(uncovered_global_topic_ids))
    )
    lines.append("")
    if closure_proof_by_id:
        lines.append(
            "| ID | Proof Path | Proof Strength | Classification | Checked Files | Verified Evidence Refs |"
        )
        lines.append("|---|---|---|---|---|---|")
        for record_id in sorted(closure_proof_by_id):
            item = closure_proof_by_id.get(record_id) or {}
            checked_files = _render_provenance_preview(item.get("checked_files"))
            verified_refs = _render_provenance_preview(item.get("verified_evidence_refs"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(f"`{record_id}`"),
                        _table_cell(f"`{item.get('proof_path', 'unknown')}`"),
                        _table_cell(f"`{item.get('proof_strength', 'unknown')}`"),
                        _table_cell(f"`{item.get('classification_status', 'unknown')}`"),
                        _table_cell(checked_files),
                        _table_cell(verified_refs),
                    ]
                )
                + " |"
            )
        lines.append("")


def _append_topic_lifecycle_section(lines: list[str], summary: dict[str, Any]) -> None:
    topic_ledger = _topic_ledger(summary)
    if not topic_ledger:
        return

    open_topic_ids = _topic_status_ids(summary, status_name="open")
    carried_forward_topic_ids = _topic_status_ids(summary, status_name="carried_forward")
    resolved_topic_ids = _topic_status_ids(summary, status_name="resolved")
    waived_topic_ids = _topic_status_ids(summary, status_name="waived")
    disagreed_topic_ids = _topic_status_ids(summary, status_name="disagreed")

    lines.append("## Topic Lifecycle")
    lines.append("")
    lines.append(f"- Topic ledger entries: `{len(topic_ledger)}`")
    lines.append(
        f"- Open topics: `{len(open_topic_ids)}`"
        + (f" ({_render_id_list(open_topic_ids)})" if open_topic_ids else "")
    )
    lines.append(
        f"- Carried-forward topics: `{len(carried_forward_topic_ids)}`"
        + (
            f" ({_render_id_list(carried_forward_topic_ids)})"
            if carried_forward_topic_ids
            else ""
        )
    )
    lines.append(
        f"- Resolved topics: `{len(resolved_topic_ids)}`"
        + (f" ({_render_id_list(resolved_topic_ids)})" if resolved_topic_ids else "")
    )
    lines.append(
        f"- Waived topics: `{len(waived_topic_ids)}`"
        + (f" ({_render_id_list(waived_topic_ids)})" if waived_topic_ids else "")
    )
    lines.append(
        f"- Disagreed topics: `{len(disagreed_topic_ids)}`"
        + (f" ({_render_id_list(disagreed_topic_ids)})" if disagreed_topic_ids else "")
    )
    lines.append("")

    lines.append("| Topic ID | Title | Severity | Introduced By | Status | Recommendation | Resolution Note |")
    lines.append("|---|---|---|---|---|---|---|")
    for topic in topic_ledger:
        recommendation = topic.get("recommendation_index")
        recommendation_text = (
            f"`{recommendation}`" if recommendation not in (None, "") else "n/a"
        )
        resolution_note = str(topic.get("resolution_note") or "").strip() or "n/a"
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(f"`{topic.get('topic_id')}`"),
                    _table_cell(_topic_summary_text(topic)),
                    _table_cell(f"`{topic.get('severity')}`"),
                    _table_cell(f"`{_topic_source_role(topic)}`"),
                    _table_cell(f"`{topic.get('resolution_status')}`"),
                    _table_cell(recommendation_text),
                    _table_cell(resolution_note),
                ]
            )
            + " |"
        )
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    lines: list[str] = ["# Forge Harness Report", ""]

    task = summary.get("task") or {}
    verdicts = summary.get("verdicts") or {}
    validator_summary = summary.get("validator_summary") or {}
    run_details = summary.get("run_details") or {}
    contract = summary.get("analysis_review_contract") or {}
    review_coverage = summary.get("analysis_review_coverage") or {}
    analysis_status = _analysis_review_status(summary)
    provenance = analysis_status.get("provenance") or {}
    publishability = analysis_status.get("publishability") or {}

    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Run verdict: **{summary.get('verdict')}**")
    if verdicts:
        lines.append(f"- Content verdict: `{verdicts.get('content_verdict', 'unknown')}`")
        lines.append(f"- Validator verdict: `{verdicts.get('validator_verdict', 'unknown')}`")
        lines.append(f"- Policy verdict: `{verdicts.get('policy_verdict', 'unknown')}`")
        lines.append(f"- Config verdict: `{verdicts.get('config_verdict', 'unknown')}`")
    lines.append(f"- Task ID: `{task.get('id', 'task')}`")
    lines.append(f"- Task kind: `{task.get('task_kind', 'unknown')}`")
    lines.append(f"- Strategy: `{summary.get('strategy_name', 'strategy')}` ({summary.get('strategy_kind', 'kind')})")
    if analysis_status:
        lines.append(f"- Review mode: `{analysis_status.get('mode', 'unknown')}`")
        if publishability:
            lines.append(
                "- Final publication: "
                + (
                    "`publishable`"
                    if publishability.get("final_answer_publishable")
                    else "`blocked`"
                )
            )
        lines.append(f"- Provenance status: `{provenance.get('status', 'unknown')}`")
        downgrade_causes = analysis_status.get("downgrade_causes") or []
        if downgrade_causes:
            lines.append("- Downgrade causes: " + "; ".join(str(item) for item in downgrade_causes))
    lines.append(f"- Workspace: `{summary.get('workspace')}`")
    final_artifact = (summary.get("artifacts") or {}).get("final_artifact")
    final_artifact_kind = (summary.get("artifacts") or {}).get("final_artifact_kind")
    if final_artifact:
        lines.append(f"- Primary deliverable: `{final_artifact_kind}` → `{final_artifact}`")
    lines.append("")

    if summary.get("final_summary"):
        lines.append("## Final Summary")
        lines.append("")
        lines.append(summary["final_summary"])
        lines.append("")

    if contract:
        lines.append("## Analysis Review Contract")
        lines.append("")
        lines.append(f"- Contract version: `{contract.get('contract_version')}`")
        stop_policy = contract.get("stop_policy") or {}
        stop_when = stop_policy.get("stop_when") or {}
        lines.append(f"- Reviser goal: `{contract.get('reviser_goal')}`")
        lines.append(f"- Require issue ledger: `{contract.get('require_issue_ledger')}`")
        lines.append(f"- Require recommendation reviews: `{contract.get('require_recommendation_reviews')}`")
        if stop_when:
            lines.append(f"- Stop policy: `{json.dumps(stop_when, sort_keys=True)}`")
        partial_acceptance = contract.get("partial_acceptance") or {}
        if partial_acceptance:
            lines.append(
                f"- Partial acceptance policy: `{json.dumps(partial_acceptance, sort_keys=True)}`"
            )
        required_sections = contract.get("required_sections") or {}
        if required_sections:
            lines.append(
                f"- Required analysis sections: `{json.dumps(required_sections, sort_keys=True)}`"
            )
        lines.append("")

    if task.get("task_kind") == "analysis_review" or summary.get("strategy_kind") == "analysis_review_v1":
        lines.append("## Review Loop Coverage")
        lines.append("")
        lines.append(f"- Review stages attempted: `{review_coverage.get('review_stages_attempted', 0)}`")
        lines.append(f"- Review stages completed: `{review_coverage.get('review_stages_completed', 0)}`")
        lines.append(f"- Review loop exercised: `{review_coverage.get('review_loop_exercised', False)}`")
        failed_review_stages = review_coverage.get("failed_review_stages") or []
        if failed_review_stages:
            lines.append("- Failed review stages:")
            for item in failed_review_stages:
                label = item.get("role_name") or f"stage-{item.get('stage_index')}"
                detail = item.get("failure_summary") or item.get("failure_kind") or "unknown error"
                lines.append(f"  - {label}: {detail}")
        if not review_coverage.get("review_loop_exercised", False):
            lines.append(
                "- Notes: reviewer-derived issue counts and recommendation verdicts were not produced for this run."
            )
        lines.append("")

        _append_review_scope_section(lines, summary)
    _append_analysis_review_status_section(lines, summary)
    _append_review_provenance_section(lines, summary)

    if run_details:
        lines.append("## Run Details")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(_sanitize_run_details_for_report(run_details), indent=2, sort_keys=False))
        lines.append("```")
        lines.append("")

    if summary.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for warning in summary["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    policy = summary.get("workspace_write_policy") or {}
    lines.append("## Workspace Write Policy")
    lines.append("")
    lines.append(f"- Mode: `{policy.get('mode', 'unknown')}`")
    lines.append(f"- Allowed paths: {_render_policy_list(policy.get('allowed_paths', []))}")
    lines.append(f"- Denied paths: {_render_policy_list(policy.get('denied_paths', []))}")
    lines.append(f"- Allow untracked files: `{policy.get('allow_untracked')}`")
    lines.append(f"- Allow renames: `{policy.get('allow_renames')}`")
    lines.append(f"- Allow deletions: `{policy.get('allow_deletions')}`")
    max_touched = policy.get('max_touched_files')
    lines.append(f"- Max touched files: `{max_touched if max_touched is not None else 'unlimited'}`")
    lines.append(f"- Require clean start: `{policy.get('require_clean_start')}`")
    ignored = summary.get("workspace_policy_ignored_rel_paths") or []
    lines.append(f"- Ignored harness-artifact paths: {_render_policy_list(ignored)}")
    review_requirements = task.get("review_requirements") or {}
    if task.get("task_kind") == "analysis_review":
        lines.append(f"- Require evidence per recommendation: `{review_requirements.get('require_evidence_per_recommendation')}`")
        lines.append(f"- Require classification: `{review_requirements.get('require_classification')}`")
        lines.append(f"- Require priority: `{review_requirements.get('require_priority')}`")
        lines.append(f"- Minimum recommendations: `{review_requirements.get('min_recommendations')}`")
    lines.append("")

    checks = summary.get("workspace_policy_checks", [])
    lines.append("## Workspace Policy Checks")
    lines.append("")
    if not checks:
        lines.append("No workspace policy checks were recorded.")
        lines.append("")
    else:
        for check in checks:
            outcome = "PASS" if check.get("ok") else "FAIL"
            lines.append(f"### {check.get('checkpoint')} — {outcome}")
            lines.append("")
            lines.append(f"- Touched files: {_render_policy_list(check.get('touched_files', []))}")
            if check.get("modified_files"):
                lines.append(f"- Modified files: {_render_policy_list(check.get('modified_files', []))}")
            if check.get("added_files"):
                lines.append(f"- Added files: {_render_policy_list(check.get('added_files', []))}")
            if check.get("deleted_files"):
                lines.append(f"- Deleted files: {_render_policy_list(check.get('deleted_files', []))}")
            if check.get("renamed_files"):
                rename_text = ", ".join(
                    f"{item.get('from')} -> {item.get('to')}" for item in check.get("renamed_files", [])
                )
                lines.append(f"- Renamed files: {rename_text}")
            if check.get("new_untracked_files"):
                lines.append(
                    f"- New untracked files: {_render_policy_list(check.get('new_untracked_files', []))}"
                )
            if check.get("violations"):
                lines.append("- Violations:")
                for violation in check.get("violations", []):
                    lines.append(f"  - {violation}")
            if check.get("notes"):
                lines.append("- Notes:")
                for note in check.get("notes", []):
                    lines.append(f"  - {note}")
            lines.append("")

    lines.append("## Validators")
    lines.append("")
    lines.append(f"- Total validator executions: `{validator_summary.get('total_runs', 0)}`")
    lines.append(f"- Latest round verdict: `{validator_summary.get('latest_round_verdict', 'not_configured')}`")
    if validator_summary.get("status_counts"):
        lines.append(f"- Status counts: `{json.dumps(validator_summary.get('status_counts'), sort_keys=True)}`")
    if validator_summary.get("required_status_counts"):
        lines.append(
            f"- Required status counts: `{json.dumps(validator_summary.get('required_status_counts'), sort_keys=True)}`"
        )
    lines.append("")

    validator_rounds = summary.get("validator_rounds", [])
    if not validator_rounds:
        lines.append("No validators configured or run.")
        lines.append("")
    else:
        for round_data in validator_rounds:
            lines.append(f"### Round {round_data.get('round_index')}")
            lines.append("")
            for item in round_data.get("results", []):
                required = "required" if item.get("required") else "optional"
                lines.append(
                    f"- **{item.get('name')}** — {item.get('status')} — exit `{item.get('exit_code') if item.get('exit_code') is not None else 'n/a'}` — {required}"
                )
                if item.get("skip_reason"):
                    lines.append(f"  - reason: {item.get('skip_reason')}")
                if item.get("missing_paths"):
                    lines.append(f"  - missing paths: {_render_policy_list(item.get('missing_paths', []))}")
                if item.get("missing_binaries"):
                    lines.append(f"  - missing binaries: {_render_policy_list(item.get('missing_binaries', []))}")
                if item.get("error"):
                    lines.append(f"  - error: {item.get('error')}")
            lines.append("")

    issue_ledger = summary.get("issue_ledger") or []
    if issue_ledger:
        lines.append("## Issue Ledger")
        lines.append("")
        open_count = sum(
            1 for issue in issue_ledger if str(issue.get("resolution_status") or "") in {"open", "carried_forward"}
        )
        resolved_count = sum(
            1 for issue in issue_ledger if str(issue.get("resolution_status") or "") == "resolved"
        )
        lines.append(f"- Open issues: `{open_count}`")
        lines.append(f"- Resolved issues: `{resolved_count}`")
        lines.append("")
        for issue in issue_ledger:
            lines.append(
                f"### {issue.get('issue_id')} — {issue.get('severity')} — {issue.get('blocking_class')} — {issue.get('resolution_status')}"
            )
            lines.append("")
            lines.append(f"- Kind: `{issue.get('kind')}`")
            if issue.get("recommendation_index") is not None:
                lines.append(f"- Recommendation index: `{issue.get('recommendation_index')}`")
            lines.append(f"- Title: {issue.get('title')}")
            lines.append(f"- Evidence: {issue.get('evidence')}")
            lines.append(f"- Repair hint: {issue.get('repair_hint')}")
            if issue.get("why_not_raised_earlier"):
                lines.append(f"- Why not raised earlier: {issue.get('why_not_raised_earlier')}")
            lines.append("")

    _append_topic_lifecycle_section(lines, summary)

    drafts = summary.get("drafts", [])
    if drafts:
        lines.append("## Draft Selection")
        lines.append("")
        lines.append(f"- Best draft ID: `{summary.get('best_draft_id')}`")
        lines.append(f"- Selected draft ID: `{summary.get('selected_draft_id')}`")
        lines.append("")
        for draft in drafts:
            lines.append(f"### {draft.get('draft_id')} — {draft.get('review_status')}")
            lines.append("")
            lines.append(f"- Role: `{draft.get('role_name')}`")
            lines.append(f"- Round: `{draft.get('round_index')}`")
            lines.append(f"- Review state: `{draft.get('review_state', 'not_evaluated')}`")
            issue_counts = draft.get('issue_counts') or {}
            validator_failures = issue_counts.get("required_validator_failures")
            if validator_failures is not None:
                lines.append(f"- Required validator failures: `{validator_failures}`")
            if draft.get("review_state") == "evaluated":
                review_issue_counts = {
                    key: value
                    for key, value in issue_counts.items()
                    if key != "required_validator_failures"
                }
                if review_issue_counts:
                    lines.append(f"- Review issue counts: `{json.dumps(review_issue_counts, sort_keys=True)}`")
            else:
                lines.append("- Review issue counts: `not evaluated`")
            scores = draft.get('scores') or {}
            if scores:
                lines.append(f"- Scores: `{json.dumps(scores, sort_keys=True)}`")
            if draft.get('summary'):
                lines.append(f"- Summary: {draft.get('summary')}")
            metadata = draft.get("metadata") or {}
            if metadata.get("review_attempted") and not metadata.get("review_completed"):
                lines.append(
                    f"- Review attempt failed: {metadata.get('review_failure_summary') or metadata.get('review_failure_kind') or 'unknown error'}"
                )
            lines.append("")

    recommendation_reviews = summary.get("recommendation_reviews") or []
    if recommendation_reviews:
        lines.append("## Recommendation Reviews")
        lines.append("")
        for item in recommendation_reviews:
            lines.append(
                f"- Recommendation {item.get('recommendation_index')}: `{item.get('verdict')}` — {item.get('summary')}"
            )
            if item.get("open_issue_ids"):
                lines.append(f"  - Open issues: {_render_policy_list(item.get('open_issue_ids', []))}")
            lines.append(
                f"  - Confidence assessment: `{item.get('confidence_assessment', 'not_assessed')}`"
            )
        lines.append("")

    lines.append("## Agent Stages")
    lines.append("")
    for stage in summary.get("agent_stages", []):
        title = f"{stage.get('stage_index'):02d}. {stage.get('role_name')}"
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"- Provider: `{stage.get('provider')}`")
        lines.append(f"- Model: `{stage.get('model')}`")
        lines.append(f"- Requested access: `{stage.get('requested_access', stage.get('access'))}`")
        lines.append(f"- Effective access: `{stage.get('effective_access', stage.get('access'))}`")
        if stage.get("access_override_reason"):
            lines.append(f"- Access override: {stage.get('access_override_reason')}")
        lines.append(f"- OK: `{stage.get('ok')}`")
        lines.append(f"- Exit code: `{stage.get('exit_code')}`")
        lines.append(f"- Duration: `{stage.get('duration_sec')}` seconds")
        if stage.get("failure_kind"):
            lines.append(f"- Failure kind: `{stage.get('failure_kind')}`")
        if stage.get("failure_summary"):
            lines.append(f"- Failure summary: {stage.get('failure_summary')}")
        if stage.get("error"):
            lines.append(f"- Error: {stage.get('error')}")
        schema_errors = stage.get("schema_validation_errors") or []
        if schema_errors:
            lines.append("- Schema validation errors:")
            for item in schema_errors:
                lines.append(f"  - {item}")
        semantic_path = stage.get("semantic_validation_path")
        if semantic_path:
            lines.append(f"- Semantic validation artifact: `{semantic_path}`")
        payload_provenance = stage.get("semantic_validation_payload_provenance") or {}
        if payload_provenance:
            digest = str(payload_provenance.get("payload_sha256") or "").strip()
            digest_text = digest[:12] if digest else "n/a"
            lines.append(
                "- Payload provenance: "
                f"`{payload_provenance.get('status', 'unknown')}`"
                + (
                    f" — policy `{payload_provenance.get('policy_mode', 'none')}`"
                    f", sha `{digest_text}`"
                    f", refs `{payload_provenance.get('normalized_ref_count', 0)}`"
                )
            )
        semantic_errors = stage.get("semantic_validation_errors") or []
        if semantic_errors:
            lines.append("- Semantic validation errors:")
            for item in semantic_errors:
                lines.append(f"  - {item}")
        semantic_warnings = stage.get("semantic_validation_warnings") or []
        if semantic_warnings:
            lines.append("- Semantic validation warnings:")
            for item in semantic_warnings:
                lines.append(f"  - {item}")
        structured = stage.get("structured_output") or {}
        if structured:
            lines.append("")
            lines.append("Structured output:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(structured, indent=2, sort_keys=False))
            lines.append("```")
        lines.append("")

    git_final = summary.get("final_git_snapshot") or {}
    if git_final.get("is_git"):
        lines.append("## Final Git Snapshot")
        lines.append("")
        lines.append(f"- Branch: `{git_final.get('branch')}`")
        lines.append(f"- HEAD: `{git_final.get('head')}`")
        changed = summary.get("changed_files", [])
        lines.append(f"- Changed files: {', '.join(changed) if changed else 'none'}")
        lines.append("")
        diff_stat = git_final.get("diff_stat", "").strip()
        lines.append("```text")
        lines.append(diff_stat or "no unstaged diff")
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
