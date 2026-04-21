from __future__ import annotations

"""Artifact and reporting helpers for the LangGraph-backed harness surface."""

import copy
import json
from pathlib import Path
from typing import Any

from .files import write_json, write_text
from .report import render_report
from .selection import select_best_draft
from .topic_lifecycle import (
    partial_accept_topic_eligibility,
    topic_ids_for_status_name,
    topic_status_field_name,
)

_FULLY_ACCEPTED_RUN_VERDICTS = {"accepted", "accepted_with_warnings"}
_PARTIAL_ACCEPTED_RUN_VERDICTS = {"accepted_partial"}


def artifact_ref(path: str | Path, *, kind: str, description: str) -> dict[str, str]:
    return {
        "kind": kind,
        "path": str(path),
        "description": description,
    }


def ensure_run_dir(run_dir: str | Path) -> Path:
    path = Path(run_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _accepted_recommendation_indices(summary: dict[str, Any]) -> list[int]:
    reviews = summary.get("recommendation_reviews") or []
    indices: list[int] = []
    for item in reviews:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict") or "").strip().lower()
        if verdict not in {"accept", "accept_with_caveat"}:
            continue
        try:
            indices.append(int(item.get("recommendation_index")))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _eligible_partial_answer_indices(summary: dict[str, Any]) -> list[int]:
    accepted_indices = _accepted_recommendation_indices(summary)
    if not accepted_indices:
        return []
    topic_eligibility = partial_accept_topic_eligibility(
        _topic_ledger(summary),
        accepted_recommendation_indices=accepted_indices,
    )
    if topic_eligibility["global_blocking_topic_ids"]:
        return []
    return list(topic_eligibility["eligible_recommendation_indices"])


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


def _topic_status_ids(summary: dict[str, Any], *, status_name: str) -> list[str]:
    status = _analysis_review_status(summary)
    field_name = topic_status_field_name(status_name)
    raw_ids = status.get(field_name)
    if isinstance(raw_ids, list):
        return sorted(str(item).strip() for item in raw_ids if str(item).strip())

    return topic_ids_for_status_name(_topic_ledger(summary), status_name=status_name)


def _render_id_list(items: list[str]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return "none"
    return ", ".join(f"`{item}`" for item in values)


def _topic_source_role(topic: dict[str, Any]) -> str:
    introduced_by = str(topic.get("introduced_by") or "").strip()
    return introduced_by or "unknown"


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


def _append_topic_lifecycle(lines: list[str], summary: dict[str, Any]) -> None:
    topic_ledger = _topic_ledger(summary)
    if not topic_ledger:
        return

    lines.extend(["## Topic Lifecycle", ""])
    for topic in topic_ledger:
        line = (
            f"- `{topic.get('topic_id')}` "
            f"`{topic.get('resolution_status')}` "
            f"via `{_topic_source_role(topic)}`: {_topic_summary_text(topic)}"
        )
        resolution_note = str(topic.get("resolution_note") or "").strip()
        if resolution_note:
            line += f" — {resolution_note}"
        lines.append(line)
    lines.append("")


def _recommendation_review_lookup(summary: dict[str, Any]) -> dict[int, dict[str, Any]]:
    reviews = summary.get("recommendation_reviews") or []
    lookup: dict[int, dict[str, Any]] = {}
    for item in reviews:
        if not isinstance(item, dict):
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        lookup[recommendation_index] = item
    return lookup


def _recommendation_source_indices(payload: dict[str, Any], recommendation_count: int) -> list[int]:
    source_indices = payload.get("included_recommendation_indices")
    if isinstance(source_indices, list):
        normalized_indices: list[int] = []
        for item in source_indices:
            try:
                normalized_indices.append(int(item))
            except (TypeError, ValueError):
                return list(range(1, recommendation_count + 1))
        if len(normalized_indices) == recommendation_count:
            return normalized_indices
    return list(range(1, recommendation_count + 1))


def _filter_records_by_recommendation_indices(
    records: list[dict[str, Any]] | None,
    *,
    included_recommendation_indices: list[int],
) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        return []
    included_index_set = set(included_recommendation_indices)
    filtered: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        if recommendation_index not in included_index_set:
            continue
        filtered.append(copy.deepcopy(item))
    return filtered


def _partial_artifact_downgrade_causes(
    *,
    issue_ledger: list[dict[str, Any]],
    topic_ledger: list[dict[str, Any]],
    recommendation_reviews: list[dict[str, Any]],
    inferred_indices: list[int],
) -> list[str]:
    causes: list[str] = []
    if any(
        str(item.get("severity") or "").strip().lower() == "low"
        and str(item.get("resolution_status") or "").strip() in {"open", "carried_forward"}
        for item in issue_ledger
    ):
        causes.append("low-severity reviewer issues remain open")
    unresolved_topic_ids = sorted(
        {
            *topic_ids_for_status_name(topic_ledger, status_name="open"),
            *topic_ids_for_status_name(topic_ledger, status_name="carried_forward"),
        }
    )
    if unresolved_topic_ids:
        causes.append("review topics remain open: " + ", ".join(unresolved_topic_ids))
    accepted_caveat_indices = sorted(
        int(item.get("recommendation_index"))
        for item in recommendation_reviews
        if str(item.get("verdict") or "").strip().lower() == "accept_with_caveat"
    )
    if accepted_caveat_indices:
        causes.append(
            "accepted recommendation reviews include accept_with_caveat: "
            + ", ".join(str(item) for item in accepted_caveat_indices)
        )
    if inferred_indices:
        causes.append(
            "accepted recommendations rely on inference-only grounding: "
            + ", ".join(str(item) for item in inferred_indices)
        )
    return causes


def _build_partial_artifact_summary(
    summary: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    included_recommendation_indices = _recommendation_source_indices(
        payload,
        len(payload.get("recommendations") or []),
    )
    filtered_reviews = _filter_records_by_recommendation_indices(
        summary.get("recommendation_reviews"),
        included_recommendation_indices=included_recommendation_indices,
    )
    filtered_topic_ledger = _filter_records_by_recommendation_indices(
        _topic_ledger(summary),
        included_recommendation_indices=included_recommendation_indices,
    )
    filtered_issue_ledger = _filter_records_by_recommendation_indices(
        summary.get("issue_ledger"),
        included_recommendation_indices=included_recommendation_indices,
    )
    analysis_status = copy.deepcopy(_analysis_review_status(summary))
    included_index_set = set(included_recommendation_indices)
    inferred_indices: list[int] = []
    for item in (analysis_status.get("accepted_recommendations_with_inferred_grounding") or []):
        try:
            recommendation_index = int(item)
        except (TypeError, ValueError):
            continue
        if recommendation_index in included_index_set:
            inferred_indices.append(recommendation_index)
    accepted_caveat_indices: list[int] = []
    for item in filtered_reviews:
        if str(item.get("verdict") or "").strip().lower() != "accept_with_caveat":
            continue
        try:
            accepted_caveat_indices.append(int(item.get("recommendation_index")))
        except (TypeError, ValueError):
            continue
    analysis_status.update(
        {
            "review_status_scope": "partial_subset",
            "accepted_recommendations_with_caveats": sorted(set(accepted_caveat_indices)),
            "accepted_recommendations_with_inferred_grounding": sorted(set(inferred_indices)),
            "open_topic_ids": topic_ids_for_status_name(filtered_topic_ledger, status_name="open"),
            "carried_forward_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger,
                status_name="carried_forward",
            ),
            "waived_topic_ids": topic_ids_for_status_name(filtered_topic_ledger, status_name="waived"),
            "resolved_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger,
                status_name="resolved",
            ),
            "disagreed_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger,
                status_name="disagreed",
            ),
            "topic_ledger_count": len(filtered_topic_ledger),
            "downgrade_causes": _partial_artifact_downgrade_causes(
                issue_ledger=filtered_issue_ledger,
                topic_ledger=filtered_topic_ledger,
                recommendation_reviews=filtered_reviews,
                inferred_indices=sorted(set(inferred_indices)),
            ),
        }
    )
    scoped_summary = copy.deepcopy(summary)
    scoped_summary["analysis_review_status"] = analysis_status
    scoped_summary["recommendation_reviews"] = filtered_reviews
    scoped_summary["topic_ledger"] = filtered_topic_ledger
    scoped_summary["issue_ledger"] = filtered_issue_ledger
    return scoped_summary


def _recommendation_caveat_lines(
    *,
    recommendation_index: int,
    review_lookup: dict[int, dict[str, Any]],
    analysis_status: dict[str, Any],
) -> list[str]:
    caveat_lines: list[str] = []
    review = review_lookup.get(recommendation_index) or {}
    verdict = str(review.get("verdict") or "").strip().lower()
    if verdict == "accept_with_caveat":
        review_summary = str(review.get("summary") or "").strip()
        caveat_lines.append(
            review_summary or "This recommendation was accepted with caveats."
        )
    inferred_indices: set[int] = set()
    for item in (analysis_status.get("accepted_recommendations_with_inferred_grounding") or []):
        try:
            inferred_indices.add(int(item))
        except (TypeError, ValueError):
            continue
    if recommendation_index in inferred_indices:
        caveat_lines.append(
            "This recommendation relies on inference-only grounding rather than direct verified evidence."
        )
    return caveat_lines


def _append_recommendation_caveat_callout(lines: list[str], caveat_lines: list[str]) -> None:
    if not caveat_lines:
        return
    lines.append("> [!NOTE]")
    lines.append("> This recommendation carries review caveats:")
    for item in caveat_lines:
        lines.append(f"> - {item}")
    lines.append("")


def _render_analysis_section(lines: list[str], title: str, section: Any) -> None:
    if not isinstance(section, dict):
        return
    items = [str(item).strip() for item in section.get("items", []) if str(item).strip()]
    none_reason = str(section.get("none_reason") or "").strip()
    if not items and not none_reason:
        return
    lines.extend([f"## {title}", ""])
    if items:
        for item in items:
            lines.append(f"- {item}")
    if none_reason:
        lines.append(f"- none_reason: {none_reason}")
    lines.append("")


def build_partial_answer_payload(summary: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    recommendation_indices = _eligible_partial_answer_indices(summary)
    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations or not recommendation_indices:
        return None
    selected_recommendations = [
        copy.deepcopy(item)
        for index, item in enumerate(recommendations, start=1)
        if index in recommendation_indices and isinstance(item, dict)
    ]
    if not selected_recommendations:
        return None
    excluded_indices = [
        index for index in range(1, len(recommendations) + 1) if index not in recommendation_indices
    ]
    partial_payload = copy.deepcopy(payload)
    partial_payload["summary"] = (
        str(payload.get("summary") or "").strip()
        + (
            f"\n\nPartial acceptance: recommendations {', '.join(str(i) for i in recommendation_indices)} "
            f"are included; recommendations {', '.join(str(i) for i in excluded_indices) or 'none'} were excluded."
        )
    ).strip()
    partial_payload["recommendations"] = selected_recommendations
    partial_payload["included_recommendation_indices"] = recommendation_indices
    partial_payload["excluded_recommendation_indices"] = excluded_indices
    filtered_reviews: list[dict[str, Any]] = []
    for item in summary.get("recommendation_reviews") or []:
        if not isinstance(item, dict):
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        if recommendation_index in recommendation_indices:
            filtered_reviews.append(copy.deepcopy(item))
    partial_payload["recommendation_reviews"] = filtered_reviews
    partial_payload["caveats"] = [
        f"This is a partial answer. Excluded recommendations: {', '.join(str(i) for i in excluded_indices) or 'none'}."
    ]
    return partial_payload


def _augment_best_draft_payload(best_draft: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(payload)
    caveats = [str(item) for item in enriched.get("caveats", []) if str(item).strip()]
    review_state = str(best_draft.get("review_state") or "not_evaluated")
    metadata = best_draft.get("metadata") or {}
    if review_state != "evaluated":
        failure_kind = str(metadata.get("review_failure_kind") or "").strip()
        failure_summary = str(metadata.get("review_failure_summary") or "").strip()
        message = "This draft was not evaluated by a successful critic/auditor stage."
        if failure_kind or failure_summary:
            detail = failure_summary or failure_kind.replace("_", " ")
            message = f"{message} Latest review attempt: {detail}."
        caveats.append(message)
    if caveats:
        enriched["caveats"] = caveats
    return enriched


def render_deliverable_markdown(
    task_id: str,
    payload: dict[str, Any],
    *,
    artifact_label: str,
    accepted: bool,
    summary: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = [f"# {artifact_label}: {task_id}", ""]
    verdict = str((summary or {}).get("verdict") or "").strip()
    analysis_status = _analysis_review_status(summary or {})
    review_lookup = _recommendation_review_lookup(summary or {})
    if not accepted:
        lines.extend(
            [
                "> [!WARNING]",
                "> This run did not reach a fully accepted verdict. This file may contain a best-effort or partial deliverable.",
                "",
            ]
        )
    elif verdict == "accepted_with_warnings":
        lines.extend(
            [
                "> [!NOTE]",
                "> This deliverable was accepted with warnings. Review mode, provenance status, and downgrade causes are listed below.",
                "",
            ]
        )

    if analysis_status:
        provenance = analysis_status.get("provenance") or {}
        topic_ledger = _topic_ledger(summary or {})
        open_topic_ids = _topic_status_ids(summary or {}, status_name="open")
        carried_forward_topic_ids = _topic_status_ids(summary or {}, status_name="carried_forward")
        resolved_topic_ids = _topic_status_ids(summary or {}, status_name="resolved")
        waived_topic_ids = _topic_status_ids(summary or {}, status_name="waived")
        disagreed_topic_ids = _topic_status_ids(summary or {}, status_name="disagreed")
        review_status_scope = str(analysis_status.get("review_status_scope") or "").strip()
        lines.extend(["## Review Status", ""])
        if verdict:
            lines.append(f"- Verdict: `{verdict}`")
        if review_status_scope == "partial_subset":
            lines.append("- Review status scope: `included recommendations only`")
            lines.append(f"- Run-level mode: `{analysis_status.get('mode', 'unknown')}`")
            lines.append(f"- Run-level provenance status: `{provenance.get('status', 'unknown')}`")
            lines.append(f"- Run-level provenance policy: `{provenance.get('policy_mode', 'none')}`")
            lines.append(
                f"- Run-level semantic warnings: `{analysis_status.get('semantic_warning_count', 0)}`"
            )
        else:
            lines.append(f"- Mode: `{analysis_status.get('mode', 'unknown')}`")
            lines.append(f"- Provenance status: `{provenance.get('status', 'unknown')}`")
            lines.append(f"- Provenance policy: `{provenance.get('policy_mode', 'none')}`")
            lines.append(f"- Semantic warnings: `{analysis_status.get('semantic_warning_count', 0)}`")
        topic_ledger_count = analysis_status.get("topic_ledger_count")
        effective_count = topic_ledger_count
        if effective_count is None:
            effective_count = len(topic_ledger)
        if effective_count:
            lines.append(f"- Topic ledger count: `{effective_count}`")
        if open_topic_ids:
            lines.append("- Open topic IDs: " + _render_id_list(open_topic_ids))
        if carried_forward_topic_ids:
            lines.append("- Carried-forward topic IDs: " + _render_id_list(carried_forward_topic_ids))
        if resolved_topic_ids:
            lines.append("- Resolved topic IDs: " + _render_id_list(resolved_topic_ids))
        if waived_topic_ids:
            lines.append("- Waived topic IDs: " + _render_id_list(waived_topic_ids))
        if disagreed_topic_ids:
            lines.append("- Disagreed topic IDs: " + _render_id_list(disagreed_topic_ids))
        downgrade_causes = analysis_status.get("downgrade_causes") or []
        if downgrade_causes:
            lines.append("- Downgrade causes: " + "; ".join(str(item) for item in downgrade_causes))
        lines.append("")

    _append_topic_lifecycle(lines, summary or {})

    summary_text = str(payload.get("summary", "") or "").strip()
    if summary_text:
        lines.extend(["## Summary", "", summary_text, ""])

    caveats = payload.get("caveats")
    if isinstance(caveats, list) and caveats:
        lines.append("## Caveats")
        lines.append("")
        for item in caveats:
            lines.append(f"- {item}")
        lines.append("")

    _render_analysis_section(lines, "Strengths", payload.get("strengths"))
    _render_analysis_section(lines, "Uncertainties", payload.get("uncertainties"))

    files_reviewed = payload.get("files_reviewed")
    if isinstance(files_reviewed, list) and files_reviewed:
        lines.extend(["## Files Reviewed", ""])
        for item in files_reviewed:
            if str(item).strip():
                lines.append(f"- {item}")
        lines.append("")

    recommendations = payload.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        source_indices = _recommendation_source_indices(payload, len(recommendations))
        lines.extend(["## Recommendations", ""])
        for display_index, item in enumerate(recommendations, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or f"Recommendation {display_index}")
            classification = str(item.get("classification") or "").strip()
            priority = str(item.get("priority") or "").strip()
            header_parts = [title]
            meta = ", ".join(bit for bit in (classification, priority) if bit)
            if meta:
                header_parts.append(f"({meta})")
            lines.append(f"### {display_index}. {' '.join(header_parts)}")
            lines.append("")
            recommendation_index = source_indices[display_index - 1]
            _append_recommendation_caveat_callout(
                lines,
                _recommendation_caveat_lines(
                    recommendation_index=recommendation_index,
                    review_lookup=review_lookup,
                    analysis_status=analysis_status,
                ),
            )
            for field_name, label in (
                ("rationale", "Rationale"),
                ("proposed_change", "Suggested change"),
                ("suggested_change", "Suggested change"),
            ):
                value = item.get(field_name)
                if value:
                    lines.extend([f"**{label}:** {value}", ""])
            evidence = item.get("evidence")
            if isinstance(evidence, list) and evidence:
                lines.append("**Evidence:**")
                for evidence_item in evidence:
                    if isinstance(evidence_item, dict):
                        path = evidence_item.get("path") or evidence_item.get("file") or "workspace"
                        note = evidence_item.get("note")
                        lines.append(f"- {path}" + (f" — {note}" if note else ""))
                    else:
                        lines.append(f"- {evidence_item}")
                lines.append("")
            confidence = item.get("confidence")
            if confidence is not None:
                lines.extend([f"**Confidence:** {confidence}", ""])
    else:
        lines.extend(["## Structured Output", "", "```json", json.dumps(payload, indent=2, sort_keys=False), "```", ""])

    return "\n".join(lines).rstrip() + "\n"


def apply_final_artifacts(summary: dict[str, Any]) -> dict[str, Any]:
    """Ensure the summary includes best-draft selection and deliverable artifacts.

    Accepted runs get ``FINAL_ANSWER.*``. Partially accepted runs get
    ``PARTIAL_ANSWER.*``. Other runs get ``BEST_DRAFT.*``. The summary/report are
    rewritten after the selection step so the artifacts are internally consistent.
    """

    summary = copy.deepcopy(summary)
    run_dir = ensure_run_dir((summary.get("artifacts") or {}).get("run_dir") or summary.get("run_dir") or ".")
    artifacts = dict(summary.get("artifacts") or {})
    task = summary.get("task") or {}
    task_id = str(task.get("id") or "task")
    bounded_review_summary = summary.get("bounded_review_summary")
    if not isinstance(bounded_review_summary, dict) or not bounded_review_summary:
        run_details = summary.get("run_details") or {}
        bounded_review_summary = run_details.get("bounded_review_summary")
        if isinstance(bounded_review_summary, dict) and bounded_review_summary:
            summary["bounded_review_summary"] = copy.deepcopy(bounded_review_summary)

    drafts = list(summary.get("drafts") or [])
    best_draft = select_best_draft(drafts)
    if best_draft is not None:
        summary["best_draft_id"] = best_draft.get("draft_id")
        summary.setdefault("selected_draft_id", best_draft.get("draft_id"))
        for index, draft in enumerate(drafts):
            if draft.get("draft_id") == best_draft.get("draft_id"):
                drafts[index] = best_draft
                break
    summary["drafts"] = drafts

    verdict = str(summary.get("verdict") or "")
    fully_accepted = verdict in _FULLY_ACCEPTED_RUN_VERDICTS
    partially_accepted = verdict in _PARTIAL_ACCEPTED_RUN_VERDICTS
    payload: dict[str, Any] | None = None
    artifact_kind = None
    artifact_json_path: Path | None = None
    artifact_md_path: Path | None = None

    if fully_accepted:
        payload = summary.get("final_answer")
        if not isinstance(payload, dict) or not payload:
            if best_draft is not None:
                payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
        if isinstance(payload, dict) and payload:
            artifact_kind = "final_answer"
            artifact_json_path = run_dir / "FINAL_ANSWER.json"
            artifact_md_path = run_dir / "FINAL_ANSWER.md"
    elif partially_accepted:
        payload = summary.get("partial_answer")
        if not isinstance(payload, dict) or not payload:
            source_payload = summary.get("final_answer")
            if (not isinstance(source_payload, dict) or not source_payload) and best_draft is not None:
                source_payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
            payload = build_partial_answer_payload(summary, source_payload)
        if isinstance(payload, dict) and payload:
            artifact_kind = "partial_answer"
            artifact_json_path = run_dir / "PARTIAL_ANSWER.json"
            artifact_md_path = run_dir / "PARTIAL_ANSWER.md"
            summary["partial_answer"] = payload
    else:
        if best_draft is not None:
            payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
            if isinstance(payload, dict) and payload:
                payload = _augment_best_draft_payload(best_draft, payload)
            artifact_kind = "best_draft"
            artifact_json_path = run_dir / "BEST_DRAFT.json"
            artifact_md_path = run_dir / "BEST_DRAFT.md"
            summary["best_draft"] = best_draft

    if artifact_json_path is not None and artifact_md_path is not None and isinstance(payload, dict) and payload:
        render_summary = (
            _build_partial_artifact_summary(summary, payload) if partially_accepted else summary
        )
        write_json(artifact_json_path, payload)
        write_text(
            artifact_md_path,
            render_deliverable_markdown(
                task_id,
                payload,
                artifact_label=(
                    "Final Answer"
                    if fully_accepted
                    else "Partial Answer"
                    if partially_accepted
                    else "Best Draft"
                ),
                accepted=fully_accepted,
                summary=render_summary,
            ),
        )
        artifacts["final_artifact"] = str(artifact_md_path)
        artifacts["final_artifact_json"] = str(artifact_json_path)
        artifacts["final_artifact_kind"] = artifact_kind
        if fully_accepted:
            artifacts["final_answer_json"] = str(artifact_json_path)
            artifacts["final_answer_md"] = str(artifact_md_path)
            summary["final_answer"] = payload
        elif partially_accepted:
            artifacts["partial_answer_json"] = str(artifact_json_path)
            artifacts["partial_answer_md"] = str(artifact_md_path)
        else:
            artifacts["best_draft_json"] = str(artifact_json_path)
            artifacts["best_draft_md"] = str(artifact_md_path)
    else:
        artifacts.setdefault("final_artifact", "")
        artifacts.setdefault("final_artifact_kind", "none")

    contract = summary.get("analysis_review_contract")
    if isinstance(contract, dict) and contract:
        contract_path = run_dir / "analysis_review.contract.effective.json"
        write_json(contract_path, contract)
        artifacts["analysis_review_contract_json"] = str(contract_path)

    issue_ledger = summary.get("issue_ledger")
    if isinstance(issue_ledger, list) and issue_ledger:
        issue_ledger_path = run_dir / "issue_ledger.final.json"
        write_json(issue_ledger_path, issue_ledger)
        artifacts["issue_ledger_json"] = str(issue_ledger_path)

    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    artifacts["report_md"] = str(report_path)
    artifacts["summary_json"] = str(summary_path)
    artifacts["run_dir"] = str(run_dir)
    summary["artifacts"] = artifacts

    write_json(summary_path, summary)
    write_text(report_path, render_report(summary))
    return summary


def write_state_artifacts(state: dict[str, Any]) -> dict[str, Any]:
    """Write report/summary artifacts for a state-style payload.

    This is used by the new harness graph in the rare path where the graph exits
    early before the imperative runner creates on-disk artifacts.
    """

    run_dir_raw = state.get("run_dir") or state.get("out_root") or ".forge-harness-runs"
    run_dir = ensure_run_dir(run_dir_raw)
    summary = {
        "run_id": state.get("run_id"),
        "thread_id": state.get("thread_id"),
        "workspace": state.get("workspace_root"),
        "task": state.get("task_spec") or {},
        "strategy_name": (state.get("strategy_spec") or {}).get("name"),
        "strategy_kind": state.get("strategy_kind"),
        "warnings": list(state.get("warnings") or []),
        "verdict": state.get("run_verdict") or state.get("content_verdict") or "invalid_config",
        "verdicts": {
            "run_verdict": state.get("run_verdict"),
            "content_verdict": state.get("content_verdict"),
            "validator_verdict": state.get("validator_verdict"),
            "policy_verdict": state.get("policy_verdict"),
            "config_verdict": state.get("config_verdict"),
        },
        "final_summary": state.get("summary_text"),
        "workspace_write_policy": ((state.get("task_spec") or {}).get("workspace_write_policy") or {}),
        "workspace_policy_checks": list(state.get("policy_checks") or []),
        "agent_stages": list(state.get("stage_history") or []),
        "validator_rounds": list(state.get("validator_rounds") or []),
        "drafts": list(state.get("drafts") or []),
        "issue_ledger": list(state.get("issue_history") or []),
        "artifacts": {
            "run_dir": str(run_dir),
        },
    }
    summary = apply_final_artifacts(summary)
    state.setdefault("artifact_index", {})["summary_json"] = artifact_ref(
        summary["artifacts"]["summary_json"],
        kind="summary_json",
        description="Machine-readable harness run summary",
    )
    state.setdefault("artifact_index", {})["report_md"] = artifact_ref(
        summary["artifacts"]["report_md"],
        kind="report_md",
        description="Human-readable harness run report",
    )
    state["summary_payload"] = summary
    return state
