from __future__ import annotations

"""Semantic validation helpers for harness stage outputs.

JSON schema catches shape-level errors. This module adds task- and contract-aware
checks that need runtime context, such as minimum recommendation counts,
per-stage issue-ledger coverage, and required analysis sections.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable

from .contracts import AnalysisReviewContract
from .types import TaskSpec


@dataclass
class SemanticValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "SemanticValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def canonical_stage_role(role_name: str) -> str:
    text = str(role_name or "").strip().lower()
    if text.startswith("reviser_round_"):
        return "reviser"
    if text.startswith("patcher_round_"):
        return "patcher"
    return text


def validate_stage_output(
    *,
    role_name: str,
    payload: dict[str, Any] | None,
    task: TaskSpec,
    contract: AnalysisReviewContract | None,
    open_issue_ids: Iterable[str] | None = None,
    prior_open_issue_ids: Iterable[str] | None = None,
    expected_recommendation_count: int | None = None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    if task.task_kind != "analysis_review" or contract is None:
        return result
    if not isinstance(payload, dict) or not payload:
        result.errors.append("Structured output is empty, so semantic validation could not run.")
        return result

    role = canonical_stage_role(role_name)
    if role in {"proposer", "reviser"}:
        result.extend(
            validate_analysis_output_payload(
                payload,
                task=task,
                contract=contract,
                expected_open_issue_ids=open_issue_ids,
                require_issue_resolution_map=(role == "reviser"),
            )
        )
    elif role in {"critic", "auditor"}:
        result.extend(
            validate_analysis_review_payload(
                payload,
                task=task,
                contract=contract,
                prior_open_issue_ids=prior_open_issue_ids,
                expected_recommendation_count=expected_recommendation_count,
            )
        )
    return result


def validate_analysis_output_payload(
    payload: dict[str, Any],
    *,
    task: TaskSpec,
    contract: AnalysisReviewContract,
    expected_open_issue_ids: Iterable[str] | None,
    require_issue_resolution_map: bool,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    review_requirements = task.review_requirements
    recommendations = payload.get("recommendations") or []
    if not isinstance(recommendations, list):
        result.errors.append("recommendations must be a list.")
        recommendations = []
    min_recommendations = int(review_requirements.min_recommendations or 0)
    if len(recommendations) < min_recommendations:
        result.errors.append(
            f"recommendations must contain at least {min_recommendations} item(s) for this task."
        )

    for index, item in enumerate(recommendations, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"recommendations[{index}] must be an object.")
            continue
        if review_requirements.require_classification and not str(item.get("classification") or "").strip():
            result.errors.append(f"recommendations[{index}] is missing classification.")
        if review_requirements.require_priority and not str(item.get("priority") or "").strip():
            result.errors.append(f"recommendations[{index}] is missing priority.")
        if review_requirements.require_evidence_per_recommendation:
            evidence = item.get("evidence") or []
            evidence_items = _non_empty_strings(evidence if isinstance(evidence, list) else [])
            if not evidence_items:
                result.errors.append(
                    f"recommendations[{index}] must include at least one non-empty evidence item."
                )

    required_sections = contract.required_sections
    _validate_section(
        result,
        name="strengths",
        payload=payload.get("strengths"),
        required=required_sections.strengths_required,
        none_reason_allowed=required_sections.none_reason_allowed,
        min_items_when_populated=required_sections.min_items_when_populated,
    )
    _validate_section(
        result,
        name="uncertainties",
        payload=payload.get("uncertainties"),
        required=required_sections.uncertainties_required,
        none_reason_allowed=required_sections.none_reason_allowed,
        min_items_when_populated=required_sections.min_items_when_populated,
    )

    files_reviewed = payload.get("files_reviewed") or []
    file_items = _non_empty_strings(files_reviewed if isinstance(files_reviewed, list) else [])
    if len(file_items) < int(required_sections.minimum_files_reviewed or 0):
        result.errors.append(
            f"files_reviewed must contain at least {required_sections.minimum_files_reviewed} non-empty path(s)."
        )

    if require_issue_resolution_map:
        expected_ids = {str(item).strip() for item in (expected_open_issue_ids or []) if str(item).strip()}
        resolution_entries = payload.get("issue_resolution_map") or []
        if not isinstance(resolution_entries, list):
            result.errors.append("issue_resolution_map must be a list.")
            resolution_entries = []
        seen_ids: list[str] = []
        for item in resolution_entries:
            if not isinstance(item, dict):
                result.errors.append("issue_resolution_map entries must be objects.")
                continue
            issue_id = str(item.get("issue_id") or "").strip()
            if not issue_id:
                result.errors.append("issue_resolution_map entries must include a non-empty issue_id.")
                continue
            seen_ids.append(issue_id)
        duplicates = sorted({issue_id for issue_id in seen_ids if seen_ids.count(issue_id) > 1})
        if duplicates:
            result.errors.append(
                "issue_resolution_map contains duplicate issue IDs: " + ", ".join(duplicates)
            )
        seen_set = set(seen_ids)
        missing_ids = sorted(expected_ids - seen_set)
        if missing_ids:
            result.errors.append(
                "issue_resolution_map is missing open issue IDs: " + ", ".join(missing_ids)
            )
        unexpected_ids = sorted(seen_set - expected_ids)
        if unexpected_ids:
            result.errors.append(
                "issue_resolution_map references unknown issue IDs: " + ", ".join(unexpected_ids)
            )

    return result


def validate_analysis_review_payload(
    payload: dict[str, Any],
    *,
    task: TaskSpec,
    contract: AnalysisReviewContract,
    prior_open_issue_ids: Iterable[str] | None,
    expected_recommendation_count: int | None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    del task  # reserved for future task-specific review checks
    del contract

    issues = payload.get("issues") or []
    issue_id_order: list[str] = []
    if not isinstance(issues, list):
        result.errors.append("issues must be a list.")
        issues = []
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            result.errors.append(f"issues[{index}] must be an object.")
            continue
        issue_id = str(issue.get("issue_id") or "").strip()
        if not issue_id:
            result.errors.append(f"issues[{index}] must include a non-empty issue_id.")
            continue
        issue_id_order.append(issue_id)
        recommendation_index = issue.get("recommendation_index")
        if recommendation_index not in (None, ""):
            try:
                recommendation_number = int(recommendation_index)
            except (TypeError, ValueError):
                result.errors.append(
                    f"issues[{index}].recommendation_index must be an integer or null."
                )
            else:
                if recommendation_number < 1:
                    result.errors.append(
                        f"issues[{index}].recommendation_index must be >= 1 when provided."
                    )
                if expected_recommendation_count is not None and recommendation_number > expected_recommendation_count:
                    result.errors.append(
                        f"issues[{index}].recommendation_index={recommendation_number} exceeds the recommendation count ({expected_recommendation_count})."
                    )
    duplicate_issue_ids = sorted({issue_id for issue_id in issue_id_order if issue_id_order.count(issue_id) > 1})
    if duplicate_issue_ids:
        result.errors.append("issues contains duplicate issue IDs: " + ", ".join(duplicate_issue_ids))
    issue_ids = set(issue_id_order)

    recommendation_reviews = payload.get("recommendation_reviews") or []
    if not isinstance(recommendation_reviews, list):
        result.errors.append("recommendation_reviews must be a list.")
        recommendation_reviews = []
    recommendation_indices: list[int] = []
    for index, item in enumerate(recommendation_reviews, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"recommendation_reviews[{index}] must be an object.")
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            result.errors.append(
                f"recommendation_reviews[{index}].recommendation_index must be an integer."
            )
            continue
        recommendation_indices.append(recommendation_index)
        if expected_recommendation_count is not None and recommendation_index > expected_recommendation_count:
            result.errors.append(
                f"recommendation_reviews[{index}].recommendation_index={recommendation_index} exceeds the recommendation count ({expected_recommendation_count})."
            )
        open_issue_ids = item.get("open_issue_ids") or []
        open_issue_set = {str(issue_id).strip() for issue_id in open_issue_ids if str(issue_id).strip()}
        unknown_issue_ids = sorted(open_issue_set - issue_ids)
        if unknown_issue_ids:
            result.errors.append(
                f"recommendation_reviews[{index}] references issue IDs not present in issues: "
                + ", ".join(unknown_issue_ids)
            )
    duplicate_recommendations = sorted(
        {value for value in recommendation_indices if recommendation_indices.count(value) > 1}
    )
    if duplicate_recommendations:
        result.errors.append(
            "recommendation_reviews contains duplicate recommendation indices: "
            + ", ".join(str(item) for item in duplicate_recommendations)
        )
    if expected_recommendation_count is not None:
        expected_indices = set(range(1, expected_recommendation_count + 1))
        review_index_set = set(recommendation_indices)
        missing_indices = sorted(expected_indices - review_index_set)
        if missing_indices:
            result.errors.append(
                "recommendation_reviews is missing recommendation indices: "
                + ", ".join(str(item) for item in missing_indices)
            )
        unexpected_indices = sorted(review_index_set - expected_indices)
        if unexpected_indices:
            result.errors.append(
                "recommendation_reviews includes unexpected recommendation indices: "
                + ", ".join(str(item) for item in unexpected_indices)
            )

    prior_open_ids = {str(item).strip() for item in (prior_open_issue_ids or []) if str(item).strip()}
    resolved_ids = _normalized_id_set(payload.get("resolved_issue_ids"))
    carried_ids = _normalized_id_set(payload.get("carried_forward_issue_ids"))
    waived_ids = _normalized_id_set(payload.get("waived_issue_ids"))
    if overlap := sorted((resolved_ids & carried_ids) | (resolved_ids & waived_ids) | (carried_ids & waived_ids)):
        result.errors.append(
            "resolved_issue_ids, carried_forward_issue_ids, and waived_issue_ids overlap: "
            + ", ".join(overlap)
        )
    classification_union = resolved_ids | carried_ids | waived_ids
    unexpected_classifications = sorted(classification_union - prior_open_ids)
    if unexpected_classifications:
        result.errors.append(
            "issue classification arrays reference unknown prior open issue IDs: "
            + ", ".join(unexpected_classifications)
        )
    missing_classifications = sorted(prior_open_ids - classification_union)
    if missing_classifications:
        result.errors.append(
            "prior open issue IDs are missing from resolved/carried_forward/waived arrays: "
            + ", ".join(missing_classifications)
        )

    return result


def _validate_section(
    result: SemanticValidationResult,
    *,
    name: str,
    payload: Any,
    required: bool,
    none_reason_allowed: bool,
    min_items_when_populated: int,
) -> None:
    if payload is None:
        if required:
            result.errors.append(f"{name} is required.")
        return
    if not isinstance(payload, dict):
        result.errors.append(f"{name} must be an object with items[] and none_reason.")
        return
    items = payload.get("items")
    none_reason = str(payload.get("none_reason") or "").strip()
    if not isinstance(items, list):
        result.errors.append(f"{name}.items must be a list of strings.")
        items = []
    non_empty_items = _non_empty_strings(items)
    if non_empty_items and len(non_empty_items) < int(min_items_when_populated or 0):
        result.errors.append(
            f"{name}.items must contain at least {min_items_when_populated} non-empty item(s) when populated."
        )
    if non_empty_items and none_reason:
        result.warnings.append(
            f"{name} contains both concrete items and none_reason; prefer one or the other."
        )
    if required and not non_empty_items:
        if none_reason_allowed:
            if not none_reason:
                result.errors.append(
                    f"{name} must contain at least one concrete item or a non-empty none_reason."
                )
        else:
            result.errors.append(f"{name} must contain at least one concrete item.")


def _non_empty_strings(values: Iterable[Any]) -> list[str]:
    cleaned: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            cleaned.append(text)
    return cleaned


def _normalized_id_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(item).strip() for item in values if str(item).strip()}
