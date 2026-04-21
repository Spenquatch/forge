from __future__ import annotations

"""Semantic validation helpers for harness stage outputs.

JSON schema catches shape-level errors. This module adds task- and contract-aware
checks that need runtime context, such as minimum recommendation counts,
per-stage issue-ledger coverage, and required analysis sections.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable

from .contracts import AnalysisReviewContract, default_blocking_class_for_kind
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
    workspace_paths: Iterable[str] | None = None,
    open_issue_ids: Iterable[str] | None = None,
    expected_open_topic_ids: Iterable[str] | None = None,
    prior_open_issue_ids: Iterable[str] | None = None,
    prior_open_topic_ids: Iterable[str] | None = None,
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
                workspace_paths=workspace_paths,
                expected_open_issue_ids=open_issue_ids,
                expected_open_topic_ids=expected_open_topic_ids,
                require_issue_resolution_map=(role == "reviser"),
                require_topic_resolution_map=(role == "reviser"),
            )
        )
    elif role in {"critic", "auditor"}:
        result.extend(
            validate_analysis_review_payload(
                payload,
                role_name=role,
                task=task,
                contract=contract,
                prior_open_issue_ids=prior_open_issue_ids,
                prior_open_topic_ids=prior_open_topic_ids,
                expected_recommendation_count=expected_recommendation_count,
            )
        )
    return result


def validate_analysis_output_payload(
    payload: dict[str, Any],
    *,
    task: TaskSpec,
    contract: AnalysisReviewContract,
    workspace_paths: Iterable[str] | None,
    expected_open_issue_ids: Iterable[str] | None,
    expected_open_topic_ids: Iterable[str] | None = None,
    require_issue_resolution_map: bool = False,
    require_topic_resolution_map: bool = False,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    review_requirements = task.review_requirements
    bounded_review = contract.bounded_review
    workspace_path_set = {
        str(item).strip() for item in (workspace_paths or []) if str(item).strip()
    }
    recommendations = payload.get("recommendations") or []
    if not isinstance(recommendations, list):
        result.errors.append("recommendations must be a list.")
        recommendations = []
    min_recommendations = int(review_requirements.min_recommendations or 0)
    if len(recommendations) < min_recommendations:
        result.errors.append(
            f"recommendations must contain at least {min_recommendations} item(s) for this task."
        )

    files_reviewed = payload.get("files_reviewed") or []
    file_items = _non_empty_strings(files_reviewed if isinstance(files_reviewed, list) else [])
    if len(file_items) < int(contract.required_sections.minimum_files_reviewed or 0):
        result.errors.append(
            f"files_reviewed must contain at least {contract.required_sections.minimum_files_reviewed} non-empty path(s)."
        )
    files_reviewed_set = set(file_items)
    unknown_files_reviewed = sorted(files_reviewed_set - workspace_path_set)
    if unknown_files_reviewed:
        result.errors.append(
            "files_reviewed contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_files_reviewed)
        )

    for index, item in enumerate(recommendations, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"recommendations[{index}] must be an object.")
            continue
        if review_requirements.require_classification and not str(item.get("classification") or "").strip():
            result.errors.append(f"recommendations[{index}] is missing classification.")
        if review_requirements.require_priority and not str(item.get("priority") or "").strip():
            result.errors.append(f"recommendations[{index}] is missing priority.")
        evidence = item.get("evidence") or []
        evidence_items = _non_empty_strings(evidence if isinstance(evidence, list) else [])
        if review_requirements.require_evidence_per_recommendation:
            if not evidence_items:
                result.errors.append(
                    f"recommendations[{index}] must include at least one non-empty evidence item."
                )
            if len(evidence_items) > bounded_review.max_evidence_refs_per_recommendation:
                result.errors.append(
                    f"recommendations[{index}].evidence exceeds the bounded-review cap of "
                    f"{bounded_review.max_evidence_refs_per_recommendation} item(s)."
                )
            _validate_recommendation_evidence(
                result,
                evidence_items=evidence_items,
                recommendation_index=index,
                files_reviewed=files_reviewed_set,
                workspace_paths=workspace_path_set,
            )
        _validate_review_surface(
            result,
            review_surface=item.get("review_surface"),
            recommendation_index=index,
            files_reviewed=files_reviewed_set,
            workspace_paths=workspace_path_set,
            contract=contract,
        )
        if contract.mode == "trust":
            _validate_trust_recommendation_metadata(
                result,
                recommendation=item,
                recommendation_index=index,
                evidence_items=evidence_items,
                workspace_paths=workspace_path_set,
                contract=contract,
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

    if require_topic_resolution_map:
        _validate_topic_resolution_map(
            result,
            topic_resolution_map=payload.get("topic_resolution_map"),
            expected_open_topic_ids=expected_open_topic_ids,
            expected_recommendation_count=len(recommendations),
        )

    return result


def validate_analysis_review_payload(
    payload: dict[str, Any],
    *,
    role_name: str,
    task: TaskSpec,
    contract: AnalysisReviewContract,
    prior_open_issue_ids: Iterable[str] | None,
    prior_open_topic_ids: Iterable[str] | None = None,
    expected_recommendation_count: int | None = None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    del task  # reserved for future task-specific review checks
    bounded_review = contract.bounded_review

    issues = payload.get("issues") or []
    issue_id_order: list[str] = []
    if not isinstance(issues, list):
        result.errors.append("issues must be a list.")
        issues = []
    if role_name == "critic" and len(issues) > bounded_review.critic_issue_cap:
        result.errors.append(
            f"issues exceeds the bounded-review cap of {bounded_review.critic_issue_cap} item(s) for critic."
        )

    prior_open_ids = {str(item).strip() for item in (prior_open_issue_ids or []) if str(item).strip()}
    new_medium_or_higher_issue_ids: list[str] = []
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            result.errors.append(f"issues[{index}] must be an object.")
            continue
        issue_id = str(issue.get("issue_id") or "").strip()
        if not issue_id:
            result.errors.append(f"issues[{index}] must include a non-empty issue_id.")
            continue
        issue_id_order.append(issue_id)
        if contract.mode == "trust":
            issue_kind = str(issue.get("kind") or "other").strip().lower()
            blocking_class = str(issue.get("blocking_class") or "").strip().lower()
            override_reason = str(issue.get("blocking_class_override_reason") or "").strip()
            if blocking_class and blocking_class != default_blocking_class_for_kind(issue_kind) and not override_reason:
                result.errors.append(
                    f"issues[{index}] overrides blocking_class for kind={issue_kind} but is missing blocking_class_override_reason."
                )
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
        if (
            role_name == "auditor"
            and issue_id not in prior_open_ids
            and str(issue.get("severity") or "").strip() in {"medium", "high", "critical"}
        ):
            new_medium_or_higher_issue_ids.append(issue_id)
            if not str(issue.get("why_not_raised_earlier") or "").strip():
                result.errors.append(
                    f"issues[{index}] must include why_not_raised_earlier for new medium-or-higher auditor issues."
                )
    duplicate_issue_ids = sorted({issue_id for issue_id in issue_id_order if issue_id_order.count(issue_id) > 1})
    if duplicate_issue_ids:
        result.errors.append("issues contains duplicate issue IDs: " + ", ".join(duplicate_issue_ids))
    issue_ids = set(issue_id_order)
    if (
        role_name == "auditor"
        and len(new_medium_or_higher_issue_ids)
        > bounded_review.auditor_new_medium_or_higher_issue_cap_after_round0
    ):
        overflow_message = (
            "new medium-or-higher auditor issues exceed the bounded-review cap of "
            f"{bounded_review.auditor_new_medium_or_higher_issue_cap_after_round0} after round 0."
        )
        if contract.mode == "trust" and contract.trust_review.late_auditor_medium_or_higher_policy == "warn":
            result.warnings.append(overflow_message)
        else:
            result.errors.append(overflow_message)

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

    topics = payload.get("topics") or []
    topic_id_order: list[str] = []
    if not isinstance(topics, list):
        result.errors.append("topics must be a list.")
        topics = []
    if role_name == "critic" and len(topics) > bounded_review.critic_new_topic_cap:
        result.errors.append(
            "topics exceeds the bounded-review cap of "
            f"{bounded_review.critic_new_topic_cap} item(s) for critic."
        )
    for index, topic in enumerate(topics, start=1):
        if not isinstance(topic, dict):
            result.errors.append(f"topics[{index}] must be an object.")
            continue
        topic_id = str(topic.get("topic_id") or "").strip()
        if not topic_id:
            result.errors.append(f"topics[{index}] must include a non-empty topic_id.")
            continue
        topic_id_order.append(topic_id)
        recommendation_index = topic.get("recommendation_index")
        if recommendation_index not in (None, ""):
            try:
                recommendation_number = int(recommendation_index)
            except (TypeError, ValueError):
                result.errors.append(
                    f"topics[{index}].recommendation_index must be an integer or null."
                )
            else:
                if recommendation_number < 1:
                    result.errors.append(
                        f"topics[{index}].recommendation_index must be >= 1 when provided."
                    )
                if expected_recommendation_count is not None and recommendation_number > expected_recommendation_count:
                    result.errors.append(
                        f"topics[{index}].recommendation_index={recommendation_number} exceeds the recommendation count ({expected_recommendation_count})."
                    )
    duplicate_topic_ids = sorted({topic_id for topic_id in topic_id_order if topic_id_order.count(topic_id) > 1})
    if duplicate_topic_ids:
        result.errors.append("topics contains duplicate topic IDs: " + ", ".join(duplicate_topic_ids))

    prior_open_topic_id_set = {
        str(item).strip() for item in (prior_open_topic_ids or []) if str(item).strip()
    }
    resolved_topic_ids = _validated_id_list(
        result,
        field_name="resolved_topic_ids",
        values=payload.get("resolved_topic_ids"),
        id_label="topic ID",
    )
    carried_forward_topic_ids = _validated_id_list(
        result,
        field_name="carried_forward_topic_ids",
        values=payload.get("carried_forward_topic_ids"),
        id_label="topic ID",
    )
    waived_topic_ids = _validated_id_list(
        result,
        field_name="waived_topic_ids",
        values=payload.get("waived_topic_ids"),
        id_label="topic ID",
    )
    resolved_topic_set = set(resolved_topic_ids)
    carried_forward_topic_set = set(carried_forward_topic_ids)
    waived_topic_set = set(waived_topic_ids)
    if overlap := sorted(
        (resolved_topic_set & carried_forward_topic_set)
        | (resolved_topic_set & waived_topic_set)
        | (carried_forward_topic_set & waived_topic_set)
    ):
        result.errors.append(
            "resolved_topic_ids, carried_forward_topic_ids, and waived_topic_ids overlap: "
            + ", ".join(overlap)
        )
    classified_topic_ids = resolved_topic_set | carried_forward_topic_set | waived_topic_set
    unexpected_topic_classifications = sorted(classified_topic_ids - prior_open_topic_id_set)
    if unexpected_topic_classifications:
        result.errors.append(
            "topic classification arrays reference unknown prior open topic IDs: "
            + ", ".join(unexpected_topic_classifications)
        )
    missing_topic_classifications = sorted(prior_open_topic_id_set - classified_topic_ids)
    if missing_topic_classifications:
        result.errors.append(
            "prior open topic IDs are missing from resolved_topic_ids/carried_forward_topic_ids/waived_topic_ids: "
            + ", ".join(missing_topic_classifications)
        )
    introduced_and_classified_topic_ids = sorted(set(topic_id_order) & classified_topic_ids)
    if introduced_and_classified_topic_ids:
        result.errors.append(
            "topics contains newly introduced topic IDs that also appear in resolved_topic_ids/carried_forward_topic_ids/waived_topic_ids: "
            + ", ".join(introduced_and_classified_topic_ids)
        )

    scope_escapes = payload.get("scope_escapes") or []
    if not isinstance(scope_escapes, list):
        result.errors.append("scope_escapes must be a list.")
        scope_escapes = []
    if bounded_review.require_scope_escape_justification:
        for index, item in enumerate(scope_escapes, start=1):
            if not isinstance(item, dict):
                result.errors.append(f"scope_escapes[{index}] must be an object.")
                continue
            if not str(item.get("reason") or "").strip():
                result.errors.append(
                    f"scope_escapes[{index}].reason must be non-empty when scope escapes are recorded."
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


def _validate_review_surface(
    result: SemanticValidationResult,
    *,
    review_surface: Any,
    recommendation_index: int,
    files_reviewed: set[str],
    workspace_paths: set[str],
    contract: AnalysisReviewContract,
) -> None:
    if not isinstance(review_surface, dict):
        result.errors.append(f"recommendations[{recommendation_index}].review_surface must be an object.")
        return

    bounded_review = contract.bounded_review
    must_check_files = review_surface.get("must_check_files") or []
    optional_check_files = review_surface.get("optional_check_files") or []
    must_check_items = _non_empty_strings(must_check_files if isinstance(must_check_files, list) else [])
    optional_check_items = _non_empty_strings(
        optional_check_files if isinstance(optional_check_files, list) else []
    )

    if not must_check_items:
        result.errors.append(
            f"recommendations[{recommendation_index}].review_surface.must_check_files must contain at least one non-empty path."
        )
    if len(must_check_items) > bounded_review.max_must_check_files_per_recommendation:
        result.errors.append(
            f"recommendations[{recommendation_index}].review_surface.must_check_files exceeds the bounded-review cap of "
            f"{bounded_review.max_must_check_files_per_recommendation} item(s)."
        )
    if len(optional_check_items) > bounded_review.max_optional_check_files_per_recommendation:
        result.errors.append(
            f"recommendations[{recommendation_index}].review_surface.optional_check_files exceeds the bounded-review cap of "
            f"{bounded_review.max_optional_check_files_per_recommendation} item(s)."
        )
    missing_files = sorted(set(must_check_items) - files_reviewed)
    if missing_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].review_surface.must_check_files must be a subset of files_reviewed: "
            + ", ".join(missing_files)
        )
    unknown_must_check_files = sorted(set(must_check_items) - workspace_paths)
    if unknown_must_check_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].review_surface.must_check_files contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_must_check_files)
        )
    unknown_optional_check_files = sorted(set(optional_check_items) - workspace_paths)
    if unknown_optional_check_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].review_surface.optional_check_files contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_optional_check_files)
        )


def _validate_recommendation_evidence(
    result: SemanticValidationResult,
    *,
    evidence_items: list[str],
    recommendation_index: int,
    files_reviewed: set[str],
    workspace_paths: set[str],
) -> None:
    missing_files = sorted(set(evidence_items) - files_reviewed)
    if missing_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].evidence must be a subset of files_reviewed: "
            + ", ".join(missing_files)
        )
    unknown_files = sorted(set(evidence_items) - workspace_paths)
    if unknown_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].evidence contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_files)
        )


def _validate_trust_recommendation_metadata(
    result: SemanticValidationResult,
    *,
    recommendation: dict[str, Any],
    recommendation_index: int,
    evidence_items: list[str],
    workspace_paths: set[str],
    contract: AnalysisReviewContract,
) -> None:
    verified_items = _non_empty_strings(
        (recommendation.get("verified_evidence_refs") or [])
        if isinstance(recommendation.get("verified_evidence_refs"), list)
        else []
    )
    checked_items = _non_empty_strings(
        (recommendation.get("checked_files") or [])
        if isinstance(recommendation.get("checked_files"), list)
        else []
    )
    affected_items = _non_empty_strings(
        (recommendation.get("affected_files") or [])
        if isinstance(recommendation.get("affected_files"), list)
        else []
    )

    unknown_checked_files = sorted(set(checked_items) - workspace_paths)
    if unknown_checked_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].checked_files contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_checked_files)
        )
    unknown_affected_files = sorted(set(affected_items) - workspace_paths)
    if unknown_affected_files:
        result.errors.append(
            f"recommendations[{recommendation_index}].affected_files contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_affected_files)
        )

    if contract.trust_review.require_verified_evidence_refs_subset:
        unexpected_verified = sorted(set(verified_items) - set(evidence_items))
        if unexpected_verified:
            result.errors.append(
                f"recommendations[{recommendation_index}].verified_evidence_refs must be a subset of evidence: "
                + ", ".join(unexpected_verified)
            )

    grounding_mode = str(recommendation.get("grounding_mode") or "").strip().lower()
    if contract.trust_review.require_affected_file_coverage and grounding_mode != "inferred":
        supported_refs = set(evidence_items) | set(verified_items) | set(checked_items)
        uncovered_affected_files = sorted(set(affected_items) - supported_refs)
        if uncovered_affected_files:
            result.errors.append(
                f"recommendations[{recommendation_index}].affected_files must be covered by evidence or checked_files when grounding_mode is not inferred: "
                + ", ".join(uncovered_affected_files)
            )


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


def _validated_id_list(
    result: SemanticValidationResult,
    *,
    field_name: str,
    values: Any,
    id_label: str,
) -> list[str]:
    if values is None:
        values = []
    if not isinstance(values, list):
        result.errors.append(f"{field_name} must be a list.")
        return []
    normalized_ids: list[str] = []
    for index, item in enumerate(values, start=1):
        text = str(item).strip()
        if not text:
            result.errors.append(f"{field_name}[{index}] must be a non-empty {id_label}.")
            continue
        normalized_ids.append(text)
    duplicates = sorted({item for item in normalized_ids if normalized_ids.count(item) > 1})
    if duplicates:
        result.errors.append(f"{field_name} contains duplicate {id_label}s: " + ", ".join(duplicates))
    return normalized_ids


def _validate_topic_resolution_map(
    result: SemanticValidationResult,
    *,
    topic_resolution_map: Any,
    expected_open_topic_ids: Iterable[str] | None,
    expected_recommendation_count: int,
) -> None:
    expected_topic_ids = {
        str(item).strip() for item in (expected_open_topic_ids or []) if str(item).strip()
    }
    if topic_resolution_map is None:
        topic_resolution_map = []
    if not isinstance(topic_resolution_map, list):
        result.errors.append("topic_resolution_map must be a list.")
        return

    seen_topic_ids: list[str] = []
    for index, item in enumerate(topic_resolution_map, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"topic_resolution_map[{index}] must be an object.")
            continue
        topic_id = str(item.get("topic_id") or "").strip()
        if not topic_id:
            result.errors.append(f"topic_resolution_map[{index}] must include a non-empty topic_id.")
            continue
        seen_topic_ids.append(topic_id)

        recommendation_index = item.get("recommendation_index")
        has_valid_recommendation_index = False
        if recommendation_index not in (None, ""):
            try:
                recommendation_number = int(recommendation_index)
            except (TypeError, ValueError):
                result.errors.append(
                    f"topic_resolution_map[{index}].recommendation_index must be an integer or null."
                )
            else:
                if recommendation_number < 1:
                    result.errors.append(
                        f"topic_resolution_map[{index}].recommendation_index must be >= 1 when provided."
                    )
                elif recommendation_number > expected_recommendation_count:
                    result.errors.append(
                        f"topic_resolution_map[{index}].recommendation_index={recommendation_number} exceeds the recommendation count ({expected_recommendation_count})."
                    )
                else:
                    has_valid_recommendation_index = True
        change_summary = str(item.get("change_summary") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        if (
            status == "addressed"
            and not has_valid_recommendation_index
            and not _has_substantive_change_summary(change_summary)
        ):
            result.errors.append(
                f"topic_resolution_map[{index}] with status=addressed must include a valid recommendation_index or a substantive change_summary."
            )

    duplicates = sorted({item for item in seen_topic_ids if seen_topic_ids.count(item) > 1})
    if duplicates:
        result.errors.append(
            "topic_resolution_map contains duplicate topic IDs: " + ", ".join(duplicates)
        )

    seen_topic_id_set = set(seen_topic_ids)
    missing_topic_ids = sorted(expected_topic_ids - seen_topic_id_set)
    if missing_topic_ids:
        result.errors.append(
            "topic_resolution_map is missing open topic IDs: " + ", ".join(missing_topic_ids)
        )
    unexpected_topic_ids = sorted(seen_topic_id_set - expected_topic_ids)
    if unexpected_topic_ids:
        result.errors.append(
            "topic_resolution_map references unknown topic IDs: " + ", ".join(unexpected_topic_ids)
        )


def _has_substantive_change_summary(change_summary: str) -> bool:
    if not change_summary:
        return False
    normalized = " ".join(change_summary.split()).strip().lower()
    if not normalized:
        return False
    if normalized in {"n/a", "na", "none", "no change", "unchanged", "same"}:
        return False
    return True
