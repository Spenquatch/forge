from __future__ import annotations

"""Artifact and reporting helpers for the LangGraph-backed harness surface."""

import copy
import json
from pathlib import Path
from typing import Any

from .files import write_json, write_text
from .publication_authority import (
    partial_acceptance_summary_suffix,
    sanitize_artifact_payload,
    sanitize_summary_text,
)
from .report import render_report
from .selection import select_best_draft
from .topic_lifecycle import (
    partial_accept_topic_eligibility,
    topic_ids_for_status_name,
    topic_status_field_name,
)

_FULLY_ACCEPTED_RUN_VERDICTS = {"accepted", "accepted_with_warnings"}
_PARTIAL_ACCEPTED_RUN_VERDICTS = {"accepted_partial"}
_CANONICAL_ADMISSIBILITY_REASONS = {
    "accepted_with_caveat",
    "inferred_grounding",
    "not_accepted",
    "topic_blocked",
}


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


def _normalized_recommendation_indices(raw_items: Any) -> list[int]:
    indices: list[int] = []
    for item in raw_items or []:
        try:
            indices.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _recommendation_admissibility(summary: dict[str, Any]) -> dict[str, Any]:
    raw_admissibility = _analysis_review_status(summary).get("recommendation_admissibility")
    if not isinstance(raw_admissibility, dict) or not raw_admissibility:
        return {}

    reasons_by_index: dict[str, list[str]] = {}
    for raw_index, raw_reasons in (
        raw_admissibility.get("reasons_by_recommendation_index") or {}
    ).items():
        try:
            normalized_index = int(raw_index)
        except (TypeError, ValueError):
            continue
        normalized_reasons = [
            str(reason).strip()
            for reason in (raw_reasons or [])
            if str(reason).strip() in _CANONICAL_ADMISSIBILITY_REASONS
        ]
        if normalized_reasons:
            reasons_by_index[str(normalized_index)] = normalized_reasons

    normalized = {
        "final_answer_recommendation_indices": _normalized_recommendation_indices(
            raw_admissibility.get("final_answer_recommendation_indices")
        ),
        "partial_only_recommendation_indices": _normalized_recommendation_indices(
            raw_admissibility.get("partial_only_recommendation_indices")
        ),
        "excluded_recommendation_indices": _normalized_recommendation_indices(
            raw_admissibility.get("excluded_recommendation_indices")
        ),
        "reasons_by_recommendation_index": reasons_by_index,
    }
    if not any(
        (
            normalized["final_answer_recommendation_indices"],
            normalized["partial_only_recommendation_indices"],
            normalized["excluded_recommendation_indices"],
            normalized["reasons_by_recommendation_index"],
        )
    ):
        return {}
    return normalized


def _recommendation_withholding_entries(
    recommendation_admissibility: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons_by_index = (
        recommendation_admissibility.get("reasons_by_recommendation_index") or {}
    )
    withheld_indices = sorted(
        set(
            recommendation_admissibility.get("partial_only_recommendation_indices") or []
        ).union(recommendation_admissibility.get("excluded_recommendation_indices") or [])
    )
    entries: list[dict[str, Any]] = []
    for recommendation_index in withheld_indices:
        reasons = [
            str(reason).strip()
            for reason in (reasons_by_index.get(str(recommendation_index)) or [])
            if str(reason).strip() in _CANONICAL_ADMISSIBILITY_REASONS
        ]
        if not reasons:
            continue
        entries.append(
            {
                "recommendation_index": recommendation_index,
                "reasons": reasons,
            }
        )
    return entries


def _partial_acceptance_min_accepted_recommendations(summary: dict[str, Any]) -> int:
    contract = summary.get("analysis_review_contract") or {}
    partial_acceptance = contract.get("partial_acceptance") or {}
    raw_minimum = partial_acceptance.get("min_accepted_recommendations")
    if raw_minimum is None:
        raw_minimum = ((summary.get("task") or {}).get("review_requirements") or {}).get(
            "min_recommendations"
        )
    try:
        return max(1, int(raw_minimum))
    except (TypeError, ValueError):
        return 1


def _partial_candidate_recommendation_indices(summary: dict[str, Any]) -> list[int]:
    admissibility = _recommendation_admissibility(summary)
    if admissibility:
        return sorted(
            set(admissibility["final_answer_recommendation_indices"]).union(
                admissibility["partial_only_recommendation_indices"]
            )
        )
    return _accepted_recommendation_indices(summary)


def _recommendation_exclusion_reasons_by_index(
    summary: dict[str, Any],
    *,
    source_recommendation_indices: list[int],
    included_recommendation_indices: list[int],
) -> dict[str, list[str]]:
    included_index_set = set(included_recommendation_indices)
    admissibility = _recommendation_admissibility(summary)
    if admissibility:
        reasons_by_index = admissibility.get("reasons_by_recommendation_index") or {}
        return {
            str(index): list(reasons_by_index.get(str(index)) or [])
            for index in source_recommendation_indices
            if index not in included_index_set and list(reasons_by_index.get(str(index)) or [])
        }

    candidate_indices = set(_partial_candidate_recommendation_indices(summary))
    topic_eligibility = partial_accept_topic_eligibility(
        _topic_ledger(summary),
        accepted_recommendation_indices=sorted(candidate_indices),
    )
    topic_blocked_indices = set(topic_eligibility["blocked_recommendation_indices"])
    reasons_by_index: dict[str, list[str]] = {}
    for index in source_recommendation_indices:
        if index in included_index_set:
            continue
        if index in topic_blocked_indices:
            reasons_by_index[str(index)] = ["topic_blocked"]
        elif index not in candidate_indices:
            reasons_by_index[str(index)] = ["not_accepted"]
    return reasons_by_index


def _final_answer_admissible(summary: dict[str, Any], payload: dict[str, Any]) -> bool:
    admissibility = _recommendation_admissibility(summary)
    if not admissibility:
        return True

    recommendations = payload.get("recommendations")
    recommendation_count = len(recommendations) if isinstance(recommendations, list) else 0
    source_indices = _recommendation_source_indices(payload, recommendation_count)
    return (
        source_indices == admissibility["final_answer_recommendation_indices"]
        and not admissibility["partial_only_recommendation_indices"]
        and not admissibility["excluded_recommendation_indices"]
    )


def _partial_answer_eligibility(summary: dict[str, Any]) -> tuple[bool, list[int]]:
    candidate_indices = _partial_candidate_recommendation_indices(summary)
    if not candidate_indices:
        return (False, [])

    analysis_status = _analysis_review_status(summary)
    provenance = analysis_status.get("provenance") or {}
    review_mode = str(analysis_status.get("mode") or "").strip().lower()
    provenance_policy = str(provenance.get("policy_mode") or "").strip().lower()
    provenance_status = str(provenance.get("status") or "").strip().lower()
    if review_mode == "trust" and provenance_policy == "payload_hash_and_refs":
        if provenance_status != "bound":
            return (False, [])

    topic_eligibility = partial_accept_topic_eligibility(
        _topic_ledger(summary),
        accepted_recommendation_indices=candidate_indices,
    )
    if topic_eligibility["global_blocking_topic_ids"]:
        return (False, [])

    eligible_indices = list(topic_eligibility["eligible_recommendation_indices"])
    if len(eligible_indices) < _partial_acceptance_min_accepted_recommendations(summary):
        return (False, [])
    return (True, eligible_indices)


def _eligible_partial_answer_indices(summary: dict[str, Any]) -> list[int]:
    eligible, recommendation_indices = _partial_answer_eligibility(summary)
    if not eligible:
        return []
    return recommendation_indices


def _analysis_review_status(summary: dict[str, Any]) -> dict[str, Any]:
    status = summary.get("analysis_review_status")
    if isinstance(status, dict) and status:
        return status
    run_details = summary.get("run_details") or {}
    status = run_details.get("analysis_review_status")
    if isinstance(status, dict) and status:
        return status
    return {}


def _analysis_publishability(summary: dict[str, Any]) -> dict[str, Any]:
    publishability = _analysis_review_status(summary).get("publishability")
    if isinstance(publishability, dict):
        return publishability
    return {}


def _final_answer_publication_state(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    verdict = str(summary.get("verdict") or "").strip()
    if verdict not in _FULLY_ACCEPTED_RUN_VERDICTS:
        return (False, [])

    publishability = _analysis_publishability(summary)
    if not publishability:
        return (True, [])

    blocking_causes = [
        str(item)
        for item in (publishability.get("blocking_causes") or [])
        if str(item).strip()
    ]
    return (bool(publishability.get("final_answer_publishable")), blocking_causes)


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
    open_topic_ids = topic_ids_for_status_name(topic_ledger, status_name="open")
    if open_topic_ids:
        causes.append("open review topics remain: " + ", ".join(open_topic_ids))
    carried_forward_topic_ids = topic_ids_for_status_name(
        topic_ledger,
        status_name="carried_forward",
    )
    if carried_forward_topic_ids:
        causes.append(
            "review topics are carried forward: " + ", ".join(carried_forward_topic_ids)
        )
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
            "recommendation_admissibility": copy.deepcopy(
                payload.get("recommendation_admissibility")
                or analysis_status.get("recommendation_admissibility")
                or {}
            ),
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
        review_summary = sanitize_summary_text(
            review.get("summary"),
            surface="recommendation_review",
        )
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


def _render_recommendation_index_list(items: list[int]) -> str:
    if not items:
        return "none"
    return ", ".join(f"`{item}`" for item in items)


def _append_partial_admissibility_section(
    lines: list[str],
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    included_indices = _normalized_recommendation_indices(
        payload.get("included_recommendation_indices")
    )
    excluded_indices = _normalized_recommendation_indices(
        payload.get("excluded_recommendation_indices")
    )
    admissibility = (
        payload.get("recommendation_admissibility")
        if isinstance(payload.get("recommendation_admissibility"), dict)
        else _recommendation_admissibility(summary)
    )
    if not included_indices and not excluded_indices and not admissibility:
        return

    reasons_by_index = payload.get("excluded_recommendation_reasons_by_index")
    if not isinstance(reasons_by_index, dict) or not reasons_by_index:
        reasons_by_index = _recommendation_exclusion_reasons_by_index(
            summary,
            source_recommendation_indices=included_indices + excluded_indices,
            included_recommendation_indices=included_indices,
        )

    lines.extend(["## Recommendation Withholding", ""])
    lines.append(
        "- Recommendation indices included in `PARTIAL_ANSWER.*`: "
        + _render_recommendation_index_list(included_indices)
    )
    if admissibility:
        withholding_entries = _recommendation_withholding_entries(admissibility)
        lines.append(
            "- Recommendation indices withheld from `FINAL_ANSWER.*`: "
            + _render_recommendation_index_list(
                [item["recommendation_index"] for item in withholding_entries]
            )
        )
    else:
        lines.append(
            "- Recommendation indices withheld from `FINAL_ANSWER.*`: "
            + _render_recommendation_index_list(excluded_indices)
        )
    lines.append(
        "- Recommendation indices excluded from `PARTIAL_ANSWER.*`: "
        + _render_recommendation_index_list(excluded_indices)
    )
    if reasons_by_index:
        for raw_index in sorted(reasons_by_index, key=lambda item: int(item)):
            reasons = [
                str(reason).strip()
                for reason in (reasons_by_index.get(raw_index) or [])
                if str(reason).strip()
            ]
            if not reasons:
                continue
            lines.append(
                f"  - `{raw_index}`: " + ", ".join(f"`{reason}`" for reason in reasons)
            )
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
    elif none_reason:
        lines.append(none_reason)
    lines.append("")


def build_partial_answer_payload(summary: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    eligible, recommendation_indices = _partial_answer_eligibility(summary)
    if not eligible:
        return None
    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations or not recommendation_indices:
        return None
    source_indices = _recommendation_source_indices(payload, len(recommendations))
    if not set(recommendation_indices).issubset(set(source_indices)):
        return None
    selected_recommendations = [
        copy.deepcopy(item)
        for item, source_index in zip(recommendations, source_indices, strict=False)
        if source_index in recommendation_indices and isinstance(item, dict)
    ]
    if not selected_recommendations:
        return None
    excluded_indices = [
        index for index in source_indices if index not in set(recommendation_indices)
    ]
    excluded_reasons = _recommendation_exclusion_reasons_by_index(
        summary,
        source_recommendation_indices=source_indices,
        included_recommendation_indices=recommendation_indices,
    )
    recommendation_admissibility = _recommendation_admissibility(summary)
    withheld_indices = (
        [item["recommendation_index"] for item in _recommendation_withholding_entries(recommendation_admissibility)]
        if recommendation_admissibility
        else excluded_indices
    )
    partial_payload = copy.deepcopy(payload)
    partial_payload["summary"] = (
        str(payload.get("summary") or "").strip()
        + "\n\n"
        + partial_acceptance_summary_suffix(
            recommendation_indices,
            withheld_indices,
            excluded_indices,
        )
    ).strip()
    partial_payload["recommendations"] = selected_recommendations
    partial_payload["included_recommendation_indices"] = recommendation_indices
    partial_payload["excluded_recommendation_indices"] = excluded_indices
    partial_payload["excluded_recommendation_reasons_by_index"] = excluded_reasons
    if recommendation_admissibility:
        partial_payload["recommendation_admissibility"] = copy.deepcopy(
            recommendation_admissibility
        )
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
        "This is a partial answer. Excluded recommendations: "
        + f"{', '.join(str(i) for i in excluded_indices) or 'none'}."
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


def _clear_partial_artifact_state(summary: dict[str, Any], artifacts: dict[str, Any]) -> None:
    summary.pop("partial_answer", None)
    artifacts.pop("partial_answer_json", None)
    artifacts.pop("partial_answer_md", None)

    if str(artifacts.get("final_artifact_kind") or "").strip() == "partial_answer":
        artifacts.pop("final_artifact_kind", None)
    final_artifact = str(artifacts.get("final_artifact") or "").strip()
    if "PARTIAL_ANSWER" in final_artifact:
        artifacts.pop("final_artifact", None)
    final_artifact_json = str(artifacts.get("final_artifact_json") or "").strip()
    if "PARTIAL_ANSWER" in final_artifact_json:
        artifacts.pop("final_artifact_json", None)


def _clear_deliverable_artifact_pointers(artifacts: dict[str, Any]) -> None:
    for key in (
        "final_artifact",
        "final_artifact_json",
        "final_artifact_kind",
        "final_answer_json",
        "final_answer_md",
        "partial_answer_json",
        "partial_answer_md",
        "best_draft_json",
        "best_draft_md",
    ):
        artifacts.pop(key, None)


def _artifact_label_for_kind(artifact_kind: str) -> str:
    labels = {
        "final_answer": "Final Answer",
        "partial_answer": "Partial Answer",
        "best_draft": "Best Draft",
    }
    try:
        return labels[artifact_kind]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported artifact kind for deliverable markdown: {artifact_kind!r}"
        ) from exc


def _final_artifact_withholding_note_inputs(summary: dict[str, Any]) -> dict[str, Any]:
    verdict = str(summary.get("verdict") or "").strip()
    if verdict not in _FULLY_ACCEPTED_RUN_VERDICTS:
        return {
            "blocking_causes": [],
            "admissibility_withheld_entries": [],
        }

    _, blocking_causes = _final_answer_publication_state(summary)
    admissibility = _recommendation_admissibility(summary)
    admissibility_withheld_entries = _recommendation_withholding_entries(admissibility)

    return {
        "blocking_causes": list(blocking_causes),
        "admissibility_withheld_entries": admissibility_withheld_entries,
    }


def _append_blocked_publication_note(
    lines: list[str],
    *,
    artifact_kind: str,
    note_inputs: dict[str, Any],
) -> None:
    if artifact_kind not in {"partial_answer", "best_draft"}:
        return

    blocking_causes = [
        str(item).strip()
        for item in (note_inputs.get("blocking_causes") or [])
        if str(item).strip()
    ]
    admissibility_withheld_entries = [
        item
        for item in (note_inputs.get("admissibility_withheld_entries") or [])
        if isinstance(item, dict)
    ]
    if not blocking_causes and not admissibility_withheld_entries:
        return
    lines.extend(
        [
            "> [!NOTE]",
            "> Final answer publication was blocked, so this deliverable is emitted as a fallback artifact.",
        ]
    )
    if blocking_causes:
        lines.append("> Publication blockers:")
        for cause in blocking_causes:
            lines.append(f"> - {cause}")
    if admissibility_withheld_entries:
        lines.append("> Recommendation indices withheld from `FINAL_ANSWER.*`:")
        for item in admissibility_withheld_entries:
            reasons = [
                str(reason).strip()
                for reason in (item.get("reasons") or [])
                if str(reason).strip()
            ]
            if not reasons:
                continue
            lines.append(
                "> - `"
                + str(item.get("recommendation_index"))
                + "`: "
                + ", ".join(f"`{reason}`" for reason in reasons)
            )
    lines.append("")


def _render_recommendation_evidence_item(evidence_item: Any) -> str:
    if isinstance(evidence_item, dict):
        path = evidence_item.get("path") or evidence_item.get("file") or "workspace"
        note = evidence_item.get("note")
        return f"{path}" + (f" — {note}" if note else "")
    return str(evidence_item)


def _append_recommendation_evidence_preview(lines: list[str], evidence: list[Any]) -> None:
    if not evidence:
        return
    lines.append("**Evidence:**")
    preview = evidence[:3]
    for evidence_item in preview:
        lines.append(f"- {_render_recommendation_evidence_item(evidence_item)}")
    remaining = len(evidence) - len(preview)
    if remaining > 0:
        lines.append(f"- (+{remaining} more)")
    lines.append("")


def render_deliverable_markdown(
    task_id: str,
    payload: dict[str, Any],
    *,
    artifact_kind: str,
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
    final_artifact_withholding_note_inputs = _final_artifact_withholding_note_inputs(
        summary or {}
    )
    _append_blocked_publication_note(
        lines,
        artifact_kind=artifact_kind,
        note_inputs=final_artifact_withholding_note_inputs if accepted else {},
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
        if (
            str(analysis_status.get("mode") or "").strip().lower() == "trust"
            and str(provenance.get("status") or "").strip().lower() != "bound"
        ):
            incomplete_parts: list[str] = []
            uncovered_recommendation_indices = provenance.get("uncovered_recommendation_indices") or []
            uncovered_global_issue_ids = provenance.get("uncovered_global_issue_ids") or []
            uncovered_global_topic_ids = provenance.get("uncovered_global_topic_ids") or []
            if uncovered_recommendation_indices:
                incomplete_parts.append(
                    "recommendation-linked closures for recommendation indices "
                    + ", ".join(str(item) for item in uncovered_recommendation_indices)
                )
            if uncovered_global_issue_ids:
                incomplete_parts.append(
                    "uncovered global issue closures: "
                    + ", ".join(str(item) for item in uncovered_global_issue_ids)
                )
            if uncovered_global_topic_ids:
                incomplete_parts.append(
                    "uncovered global topic closures: "
                    + ", ".join(str(item) for item in uncovered_global_topic_ids)
                )
            if not incomplete_parts:
                incomplete_parts.append("structured review provenance is not fully bound")
            lines.append("- Closure proof incomplete: " + "; ".join(incomplete_parts))
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

    if artifact_kind == "partial_answer":
        _append_partial_admissibility_section(
            lines,
            payload=payload,
            summary=summary or {},
        )

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
            recommendation_index = source_indices[display_index - 1]
            title = str(item.get("title") or f"Recommendation {recommendation_index}")
            classification = str(item.get("classification") or "").strip()
            priority = str(item.get("priority") or "").strip()
            header_parts = [title]
            meta = ", ".join(bit for bit in (classification, priority) if bit)
            if meta:
                header_parts.append(f"({meta})")
            lines.append(f"### {recommendation_index}. {' '.join(header_parts)}")
            lines.append("")
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
                _append_recommendation_evidence_preview(lines, evidence)
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
    _clear_deliverable_artifact_pointers(artifacts)
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
    final_answer_publishable, _ = _final_answer_publication_state(summary)
    final_answer_blocked = fully_accepted and not final_answer_publishable
    payload: dict[str, Any] | None = None
    artifact_kind = None
    artifact_json_path: Path | None = None
    artifact_md_path: Path | None = None

    if fully_accepted and final_answer_publishable:
        payload = summary.get("final_answer")
        if not isinstance(payload, dict) or not payload:
            if best_draft is not None:
                payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
        if isinstance(payload, dict) and payload and _final_answer_admissible(summary, payload):
            artifact_kind = "final_answer"
            artifact_json_path = run_dir / "FINAL_ANSWER.json"
            artifact_md_path = run_dir / "FINAL_ANSWER.md"
        else:
            final_answer_blocked = True
    if artifact_kind is None and (partially_accepted or final_answer_blocked):
        partial_allowed, _ = _partial_answer_eligibility(summary)
        if partial_allowed:
            existing_partial_payload = summary.get("partial_answer")
            source_payload = summary.get("final_answer")
            if (not isinstance(source_payload, dict) or not source_payload) and best_draft is not None:
                source_payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
            payload = build_partial_answer_payload(summary, source_payload)
            if (
                (not isinstance(payload, dict) or not payload)
                and isinstance(existing_partial_payload, dict)
                and existing_partial_payload
            ):
                payload = copy.deepcopy(existing_partial_payload)
                recommendations = payload.get("recommendations")
                recommendation_count = (
                    len(recommendations) if isinstance(recommendations, list) else 0
                )
                included_indices = _normalized_recommendation_indices(
                    payload.get("included_recommendation_indices")
                )
                excluded_indices = sorted(
                    set(_recommendation_source_indices(payload, recommendation_count)).union(
                        _normalized_recommendation_indices(
                            payload.get("excluded_recommendation_indices")
                        )
                    )
                    - set(included_indices)
                )
                payload["excluded_recommendation_indices"] = excluded_indices
                payload.setdefault(
                    "excluded_recommendation_reasons_by_index",
                    _recommendation_exclusion_reasons_by_index(
                        summary,
                        source_recommendation_indices=sorted(
                            set(included_indices).union(excluded_indices)
                        ),
                        included_recommendation_indices=included_indices,
                    ),
                )
                recommendation_admissibility = _recommendation_admissibility(summary)
                if recommendation_admissibility:
                    payload.setdefault(
                        "recommendation_admissibility",
                        copy.deepcopy(recommendation_admissibility),
                    )
            if isinstance(payload, dict) and payload:
                artifact_kind = "partial_answer"
                artifact_json_path = run_dir / "PARTIAL_ANSWER.json"
                artifact_md_path = run_dir / "PARTIAL_ANSWER.md"
                summary["partial_answer"] = payload
        else:
            _clear_partial_artifact_state(summary, artifacts)

    if artifact_kind is None and final_answer_blocked:
        _clear_partial_artifact_state(summary, artifacts)

    if artifact_kind is None and (not fully_accepted or final_answer_blocked):
        if best_draft is not None:
            payload = copy.deepcopy((best_draft.get("metadata") or {}).get("payload") or {})
            if isinstance(payload, dict) and payload:
                payload = _augment_best_draft_payload(best_draft, payload)
            artifact_kind = "best_draft"
            artifact_json_path = run_dir / "BEST_DRAFT.json"
            artifact_md_path = run_dir / "BEST_DRAFT.md"
            summary["best_draft"] = best_draft

    if artifact_json_path is not None and artifact_md_path is not None and isinstance(payload, dict) and payload:
        emitted_payload = sanitize_artifact_payload(payload, artifact_kind=artifact_kind)
        render_summary = (
            _build_partial_artifact_summary(summary, payload)
            if artifact_kind == "partial_answer"
            else summary
        )
        write_json(artifact_json_path, emitted_payload)
        write_text(
            artifact_md_path,
            render_deliverable_markdown(
                task_id,
                emitted_payload,
                artifact_kind=artifact_kind,
                artifact_label=_artifact_label_for_kind(artifact_kind),
                accepted=fully_accepted,
                summary=render_summary,
            ),
        )
        artifacts["final_artifact"] = str(artifact_md_path)
        artifacts["final_artifact_json"] = str(artifact_json_path)
        artifacts["final_artifact_kind"] = artifact_kind
        if artifact_kind == "final_answer":
            artifacts["final_answer_json"] = str(artifact_json_path)
            artifacts["final_answer_md"] = str(artifact_md_path)
            summary["final_answer"] = payload
        elif artifact_kind == "partial_answer":
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
