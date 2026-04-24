from __future__ import annotations

import copy
import re
from typing import Any

_BANNED_PUBLICATION_AUTHORITY_PATTERNS = (
    re.compile(r"\bFINAL[\s_]*ANSWER\b", re.IGNORECASE),
    re.compile(r"\bfinal artifact\b", re.IGNORECASE),
    re.compile(r"\bpublication[- ]ready\b", re.IGNORECASE),
    re.compile(r"\bready to publish\b", re.IGNORECASE),
)

_SUMMARY_REPLACEMENTS = {
    "deliverable_summary": (
        "Runner note: model-authored summary withheld because publication eligibility is "
        "runner-owned."
    ),
    "recommendation_review": (
        "Runner note: review summary withheld because publication eligibility is runner-owned."
    ),
    "draft_summary": (
        "Runner note: draft summary withheld because publication eligibility is runner-owned."
    ),
}


def contains_publication_authority_claim(text: Any) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    return any(pattern.search(value) for pattern in _BANNED_PUBLICATION_AUTHORITY_PATTERNS)


def sanitize_summary_text(text: Any, *, surface: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if not contains_publication_authority_claim(value):
        return value
    try:
        return _SUMMARY_REPLACEMENTS[surface]
    except KeyError as exc:
        raise ValueError(f"Unsupported publication-authority summary surface: {surface!r}") from exc


def partial_acceptance_summary_suffix(
    included_recommendation_indices: list[int],
    withheld_recommendation_indices: list[int],
    excluded_recommendation_indices: list[int],
) -> str:
    return (
        "Partial acceptance: "
        "Recommendation indices included in `PARTIAL_ANSWER.*`: "
        f"{_render_summary_recommendation_index_list(included_recommendation_indices)}; "
        "Recommendation indices withheld from `FINAL_ANSWER.*`: "
        f"{_render_summary_recommendation_index_list(withheld_recommendation_indices)}; "
        "Recommendation indices excluded from `PARTIAL_ANSWER.*`: "
        f"{_render_summary_recommendation_index_list(excluded_recommendation_indices)}."
    )


def sanitize_recommendation_reviews(
    recommendation_reviews: Any,
) -> list[dict[str, Any]] | Any:
    if not isinstance(recommendation_reviews, list):
        return recommendation_reviews
    sanitized_reviews: list[dict[str, Any]] = []
    for item in recommendation_reviews:
        if not isinstance(item, dict):
            sanitized_reviews.append(item)
            continue
        sanitized_item = copy.deepcopy(item)
        sanitized_item["summary"] = sanitize_summary_text(
            sanitized_item.get("summary"),
            surface="recommendation_review",
        )
        sanitized_reviews.append(sanitized_item)
    return sanitized_reviews


def sanitize_artifact_payload(
    payload: dict[str, Any],
    *,
    artifact_kind: str,
) -> dict[str, Any]:
    sanitized = copy.deepcopy(payload)
    summary_text = str(sanitized.get("summary") or "").strip()
    if artifact_kind == "partial_answer":
        included_indices = _normalized_recommendation_indices(
            sanitized.get("included_recommendation_indices")
        )
        excluded_indices = _normalized_recommendation_indices(
            sanitized.get("excluded_recommendation_indices")
        )
        suffix = partial_acceptance_summary_suffix(
            included_indices,
            _withheld_recommendation_indices(
                sanitized.get("recommendation_admissibility"),
                fallback_indices=excluded_indices,
            ),
            excluded_indices,
        )
        if summary_text.endswith(suffix):
            model_summary = summary_text[: -len(suffix)].rstrip()
            sanitized_model_summary = sanitize_summary_text(
                model_summary,
                surface="deliverable_summary",
            )
            parts = [part for part in (sanitized_model_summary, suffix) if part]
            sanitized["summary"] = "\n\n".join(parts).strip()
        else:
            sanitized["summary"] = sanitize_summary_text(
                summary_text,
                surface="deliverable_summary",
            )
    else:
        sanitized["summary"] = sanitize_summary_text(
            summary_text,
            surface="deliverable_summary",
        )
    sanitized["recommendation_reviews"] = sanitize_recommendation_reviews(
        sanitized.get("recommendation_reviews")
    )
    return sanitized


def _normalized_recommendation_indices(raw_items: Any) -> list[int]:
    indices: list[int] = []
    for item in raw_items or []:
        try:
            indices.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _render_summary_recommendation_index_list(items: list[int]) -> str:
    if not items:
        return "none"
    return ", ".join(str(item) for item in items)


def _withheld_recommendation_indices(
    recommendation_admissibility: Any,
    *,
    fallback_indices: list[int],
) -> list[int]:
    if not isinstance(recommendation_admissibility, dict) or not recommendation_admissibility:
        return sorted(set(fallback_indices))

    withheld_indices = [
        *(
            recommendation_admissibility.get("partial_only_recommendation_indices")
            or []
        ),
        *(
            recommendation_admissibility.get("excluded_recommendation_indices")
            or []
        ),
    ]
    return _normalized_recommendation_indices(withheld_indices)
