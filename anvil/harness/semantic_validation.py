from __future__ import annotations

"""Semantic validation helpers for harness stage outputs.

JSON schema catches shape-level errors. This module adds task- and contract-aware
checks that need runtime context, such as minimum recommendation counts,
per-stage issue-ledger coverage, and required analysis sections.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable

from .contracts import (
    AnalysisReviewContract,
    canonical_seam_id_for_paths,
    default_blocking_class_for_kind,
)
from .types import TaskSpec, canonical_workspace_ref_list

_PRIOR_SURFACED_REFS_FIELD = "_prior_surfaced_refs"


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
    prior_open_issue_records: Iterable[dict[str, Any]] | None = None,
    prior_open_topic_ids: Iterable[str] | None = None,
    prior_open_topic_records: Iterable[dict[str, Any]] | None = None,
    historical_topic_ids: Iterable[str] | None = None,
    expected_recommendation_count: int | None = None,
    expected_primary_seam_id: str | None = None,
    expected_primary_seam_paths: Iterable[str] | None = None,
    expected_gate_path: str | None = None,
    payload_provenance: dict[str, Any] | None = None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    if task.task_kind != "analysis_review" or contract is None:
        return result
    if not isinstance(payload, dict) or not payload:
        result.errors.append("Structured output is empty, so semantic validation could not run.")
        return result

    role = canonical_stage_role(role_name)
    if role == "focus_gate":
        result.extend(
            validate_focus_decision_payload(
                payload,
                workspace_paths=workspace_paths,
                expected_gate_path=expected_gate_path or contract.focus_gate.default_path,
            )
        )
    elif role in {"proposer", "reviser"}:
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
                expected_primary_seam_id=expected_primary_seam_id,
                expected_primary_seam_paths=expected_primary_seam_paths,
            )
        )
    elif role in {"critic", "auditor"}:
        result.extend(
            validate_analysis_review_payload(
                payload,
                role_name=role,
                task=task,
                contract=contract,
                workspace_paths=workspace_paths,
                prior_open_issue_ids=prior_open_issue_ids,
                prior_open_issue_records=prior_open_issue_records,
                prior_open_topic_ids=prior_open_topic_ids,
                prior_open_topic_records=prior_open_topic_records,
                historical_topic_ids=historical_topic_ids,
                expected_recommendation_count=expected_recommendation_count,
                payload_provenance=payload_provenance,
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
    expected_primary_seam_id: str | None = None,
    expected_primary_seam_paths: Iterable[str] | None = None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    review_requirements = task.review_requirements
    bounded_review = contract.bounded_review
    workspace_path_set = _workspace_path_set(workspace_paths)
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
    file_items = _canonical_workspace_paths(
        files_reviewed if isinstance(files_reviewed, list) else []
    )
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

    scope_escapes = _validate_scope_escapes(
        result,
        scope_escapes=payload.get("scope_escapes"),
        require_reason=bounded_review.require_scope_escape_justification,
    )
    primary_seam_id, primary_seam_paths, declared_secondary_seam_ids = _validate_declared_seams(
        result,
        payload=payload,
        files_reviewed=files_reviewed_set,
        workspace_paths=workspace_path_set,
        contract=contract,
        scope_escapes=scope_escapes,
    )
    if expected_primary_seam_id is not None or expected_primary_seam_paths is not None:
        _validate_expected_primary_seam_id(
            result,
            actual_primary_seam_id=primary_seam_id,
            expected_primary_seam_id=expected_primary_seam_id,
            actual_primary_seam_paths=primary_seam_paths,
            expected_primary_seam_paths=expected_primary_seam_paths,
        )
    declared_seam_ids = ({primary_seam_id} if primary_seam_id else set()) | declared_secondary_seam_ids
    primary_bound_recommendation_count = 0

    for index, item in enumerate(recommendations, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"recommendations[{index}] must be an object.")
            continue
        if review_requirements.require_classification and not str(item.get("classification") or "").strip():
            result.errors.append(f"recommendations[{index}] is missing classification.")
        if review_requirements.require_priority and not str(item.get("priority") or "").strip():
            result.errors.append(f"recommendations[{index}] is missing priority.")
        evidence = item.get("evidence") or []
        evidence_items = _canonical_workspace_paths(
            evidence if isinstance(evidence, list) else []
        )
        if review_requirements.require_evidence_per_recommendation:
            if not evidence_items:
                result.errors.append(
                    f"recommendations[{index}] must include at least one non-empty evidence item."
                )
            if (
                contract.mode == "bounded"
                and len(evidence_items) > bounded_review.max_evidence_refs_per_recommendation
            ):
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
        if _validate_recommendation_seam_binding(
            result,
            recommendation=item,
            recommendation_index=index,
            primary_seam_id=primary_seam_id,
            declared_seam_ids=declared_seam_ids,
        ):
            primary_bound_recommendation_count += 1
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

    if recommendations and primary_seam_id and primary_bound_recommendation_count < 1:
        result.errors.append(
            "At least one recommendation must remain bound to primary_seam.seam_id."
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


def validate_focus_decision_payload(
    payload: dict[str, Any] | None,
    *,
    workspace_paths: Iterable[str] | None = None,
    expected_gate_path: str | None = None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    if not isinstance(payload, dict) or not payload:
        result.errors.append("Structured output is empty, so semantic validation could not run.")
        return result

    workspace_path_set = _workspace_path_set(workspace_paths)
    gate_path = str(payload.get("gate_path") or "").strip()
    if gate_path not in {"adjudicate", "deliberate"}:
        result.errors.append("gate_path must be exactly 'adjudicate' or 'deliberate'.")
    normalized_expected_gate_path = str(expected_gate_path or "").strip().lower()
    if normalized_expected_gate_path:
        if normalized_expected_gate_path not in {"adjudicate", "deliberate"}:
            result.errors.append(
                "expected_gate_path must be exactly 'adjudicate' or 'deliberate' when provided."
            )
        elif gate_path and gate_path != normalized_expected_gate_path:
            result.errors.append(
                f"gate_path must match expected_gate_path={normalized_expected_gate_path}; got {gate_path or '(missing)'}."
            )

    focus_type = str(payload.get("focus_type") or "").strip()
    if focus_type != "seam":
        result.errors.append("focus_type must be exactly 'seam'.")

    decision_state = str(payload.get("decision_state") or "").strip()
    if decision_state not in {"selected", "clarification_requested", "no_viable_focus"}:
        result.errors.append(
            "decision_state must be exactly one of: selected, clarification_requested, no_viable_focus."
        )
        return result

    selected_focus_id = payload.get("selected_focus_id")
    selected_focus_summary = payload.get("selected_focus_summary")
    selected_focus_id_text = _nullable_non_empty_string(selected_focus_id)
    selected_focus_summary_text = _nullable_non_empty_string(selected_focus_summary)
    selected_focus_paths = _canonical_workspace_paths(payload.get("selected_focus_paths"))
    unknown_selected_focus_paths = sorted(set(selected_focus_paths) - workspace_path_set)
    if unknown_selected_focus_paths:
        result.errors.append(
            "selected_focus_paths contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_selected_focus_paths)
        )

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        result.errors.append("candidates must be a list.")
        candidates = []
    candidate_ids, candidate_paths_by_id = _validated_focus_candidates(
        result,
        candidates=candidates,
        workspace_paths=workspace_path_set,
    )

    question = payload.get("question")
    question_is_canonical_empty = (
        isinstance(question, dict)
        and question.get("prompt") == ""
        and question.get("options") == []
    )
    question_prompt, question_options = _validated_focus_question(
        result,
        question=question,
    )

    adapter_plan = payload.get("adapter_plan")
    adapter_primary_focus_id, adapter_secondary_focus_ids = _validated_focus_adapter_plan(
        result,
        adapter_plan=adapter_plan,
    )

    if decision_state == "selected":
        if not selected_focus_id_text:
            result.errors.append(
                "selected_focus_id is required when decision_state=selected."
            )
        if not selected_focus_summary_text:
            result.errors.append(
                "selected_focus_summary is required when decision_state=selected."
            )
        if not selected_focus_paths:
            result.errors.append(
                "selected_focus_paths must be non-empty when decision_state=selected."
            )
        if not candidate_ids:
            result.errors.append(
                "candidates must be non-empty when decision_state=selected."
            )
        if selected_focus_id_text and selected_focus_id_text not in candidate_ids:
            result.errors.append(
                "selected_focus_id must appear in candidates when decision_state=selected."
            )
        expected_selected_focus_id = canonical_seam_id_for_paths(selected_focus_paths)
        if (
            selected_focus_id_text
            and selected_focus_paths
            and selected_focus_id_text != expected_selected_focus_id
        ):
            result.errors.append(
                "selected_focus_id must equal the canonical seam ID derived from selected_focus_paths: "
                f"expected {expected_selected_focus_id}, got {selected_focus_id_text}."
            )
        selected_candidate_paths = candidate_paths_by_id.get(selected_focus_id_text or "")
        if (
            selected_focus_id_text
            and selected_candidate_paths is not None
            and selected_focus_paths != selected_candidate_paths
        ):
            result.errors.append(
                "selected_focus_paths must equal the selected candidate's candidate_paths after normalization."
            )
        if not adapter_primary_focus_id or adapter_primary_focus_id != selected_focus_id_text:
            result.errors.append(
                "adapter_plan.primary_focus_id must equal selected_focus_id when decision_state=selected."
            )
    else:
        if selected_focus_id is not None:
            result.errors.append(
                "selected_focus_id must be null when decision_state is not selected."
            )
        if selected_focus_summary is not None:
            result.errors.append(
                "selected_focus_summary must be null when decision_state is not selected."
            )
        if adapter_primary_focus_id is not None:
            result.errors.append(
                "adapter_plan.primary_focus_id must be null when decision_state is not selected."
            )
        if selected_focus_paths:
            result.errors.append(
                "selected_focus_paths must serialize as [] when decision_state is not selected."
            )

    if decision_state == "clarification_requested":
        if not candidate_ids:
            result.errors.append(
                "candidates must be non-empty when decision_state=clarification_requested."
            )
        if not question_prompt:
            result.errors.append(
                "question.prompt is required when decision_state=clarification_requested."
            )
        if not question_options:
            result.errors.append(
                "question.options must be non-empty when decision_state=clarification_requested."
            )
        if question_options and question_options != candidate_ids:
            result.errors.append(
                "question.options must equal candidate focus IDs in order when decision_state=clarification_requested."
            )
    elif decision_state == "no_viable_focus":
        if candidate_ids:
            pass
    else:
        # selected path already handled above
        pass

    if decision_state != "clarification_requested" and not question_is_canonical_empty:
        result.errors.append(
            "question must serialize as {'prompt': '', 'options': []} when decision_state is not clarification_requested."
        )

    secondary_focus_id_set = set(adapter_secondary_focus_ids)
    unknown_secondary_focus_ids = sorted(secondary_focus_id_set - set(candidate_ids))
    if unknown_secondary_focus_ids:
        result.errors.append(
            "adapter_plan.secondary_focus_ids must be a subset of candidates: "
            + ", ".join(unknown_secondary_focus_ids)
        )

    return result


def validate_analysis_review_payload(
    payload: dict[str, Any],
    *,
    role_name: str,
    task: TaskSpec,
    contract: AnalysisReviewContract,
    workspace_paths: Iterable[str] | None = None,
    prior_open_issue_ids: Iterable[str] | None = None,
    prior_open_issue_records: Iterable[dict[str, Any]] | None = None,
    prior_open_topic_ids: Iterable[str] | None = None,
    prior_open_topic_records: Iterable[dict[str, Any]] | None = None,
    historical_topic_ids: Iterable[str] | None = None,
    expected_recommendation_count: int | None = None,
    payload_provenance: dict[str, Any] | None = None,
) -> SemanticValidationResult:
    result = SemanticValidationResult()
    del task  # reserved for future task-specific review checks
    bounded_review = contract.bounded_review
    workspace_path_set = _workspace_path_set(workspace_paths)

    issues = payload.get("issues") or []
    issue_id_order: list[str] = []
    if not isinstance(issues, list):
        result.errors.append("issues must be a list.")
        issues = []
    if role_name == "critic" and len(issues) > bounded_review.critic_issue_cap:
        result.errors.append(
            f"issues exceeds the bounded-review cap of {bounded_review.critic_issue_cap} item(s) for critic."
        )

    prior_open_issue_records_by_id = _record_map_by_id(
        prior_open_issue_records,
        id_field="issue_id",
    )
    prior_open_issue_record_map = _record_recommendation_index_by_id(
        prior_open_issue_records,
        id_field="issue_id",
    )
    prior_open_ids = set(prior_open_issue_record_map)
    if not prior_open_ids:
        prior_open_ids = {
            str(item).strip() for item in (prior_open_issue_ids or []) if str(item).strip()
        }
        prior_open_issue_records_by_id = {
            issue_id: {"issue_id": issue_id} for issue_id in prior_open_ids
        }
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

    files_reviewed = payload.get("files_reviewed") or []
    review_file_items = _canonical_workspace_paths(
        files_reviewed if isinstance(files_reviewed, list) else []
    )
    if len(review_file_items) < int(contract.required_sections.minimum_files_reviewed or 0):
        result.errors.append(
            f"files_reviewed must contain at least {contract.required_sections.minimum_files_reviewed} non-empty path(s)."
        )
    files_reviewed_set = set(review_file_items)
    unknown_files_reviewed = sorted(files_reviewed_set - workspace_path_set)
    if unknown_files_reviewed:
        result.errors.append(
            "files_reviewed contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_files_reviewed)
        )

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
        _validate_review_recommendation_metadata(
            result,
            recommendation_review=item,
            recommendation_index=index,
            files_reviewed=files_reviewed_set,
            workspace_paths=workspace_path_set,
            contract=contract,
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
    required_global_issue_closure_ids = sorted(
        issue_id for issue_id in classification_union if prior_open_issue_record_map.get(issue_id) is None
    )
    _validate_scoped_closure_reviews(
        result,
        field_name="issue_closure_reviews",
        values=payload.get("issue_closure_reviews"),
        id_field="issue_id",
        prior_record_map=prior_open_issue_records_by_id,
        required_ids=required_global_issue_closure_ids if contract.mode == "trust" else [],
        files_reviewed=files_reviewed_set,
        workspace_paths=workspace_path_set,
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

    prior_open_topic_records_by_id = _record_map_by_id(
        prior_open_topic_records,
        id_field="topic_id",
    )
    prior_open_topic_record_map = _record_recommendation_index_by_id(
        prior_open_topic_records,
        id_field="topic_id",
    )
    prior_open_topic_id_set = set(prior_open_topic_record_map)
    if not prior_open_topic_id_set:
        prior_open_topic_id_set = {
            str(item).strip() for item in (prior_open_topic_ids or []) if str(item).strip()
        }
        prior_open_topic_records_by_id = {
            topic_id: {"topic_id": topic_id} for topic_id in prior_open_topic_id_set
        }
    historical_topic_id_set = {
        str(item).strip() for item in (historical_topic_ids or []) if str(item).strip()
    }
    reused_historical_topic_ids = sorted(
        set(topic_id_order) & (historical_topic_id_set - prior_open_topic_id_set)
    )
    if reused_historical_topic_ids:
        result.errors.append(
            "topics reuses historical topic IDs that are not currently open: "
            + ", ".join(reused_historical_topic_ids)
        )
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
    required_global_topic_closure_ids = sorted(
        topic_id
        for topic_id in classified_topic_ids
        if prior_open_topic_record_map.get(topic_id) is None
    )
    _validate_scoped_closure_reviews(
        result,
        field_name="topic_closure_reviews",
        values=payload.get("topic_closure_reviews"),
        id_field="topic_id",
        prior_record_map=prior_open_topic_records_by_id,
        required_ids=required_global_topic_closure_ids if contract.mode == "trust" else [],
        files_reviewed=files_reviewed_set,
        workspace_paths=workspace_path_set,
    )

    _validate_scope_escapes(
        result,
        scope_escapes=payload.get("scope_escapes"),
        require_reason=bounded_review.require_scope_escape_justification,
    )

    if _review_payload_requires_structured_refs(payload):
        _validate_review_payload_provenance(
            result,
            contract=contract,
            payload_provenance=payload_provenance,
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
    must_check_items = _canonical_workspace_paths(
        must_check_files if isinstance(must_check_files, list) else []
    )
    optional_check_items = _canonical_workspace_paths(
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


def _validate_declared_seams(
    result: SemanticValidationResult,
    *,
    payload: dict[str, Any],
    files_reviewed: set[str],
    workspace_paths: set[str],
    contract: AnalysisReviewContract,
    scope_escapes: list[dict[str, str]],
) -> tuple[str | None, list[str], set[str]]:
    primary_seam_id, primary_seam_paths = _validate_seam_entry(
        result,
        seam=payload.get("primary_seam"),
        field_name="primary_seam",
        reason_field="why_primary",
        files_reviewed=files_reviewed,
        workspace_paths=workspace_paths,
    )
    secondary_seams = payload.get("secondary_seams_considered")
    if not isinstance(secondary_seams, list):
        result.errors.append("secondary_seams_considered must be a list.")
        return primary_seam_id, primary_seam_paths, set()

    secondary_seam_ids: set[str] = set()
    for index, item in enumerate(secondary_seams, start=1):
        seam_id, _ = _validate_seam_entry(
            result,
            seam=item,
            field_name=f"secondary_seams_considered[{index}]",
            reason_field="why_not_primary",
            files_reviewed=files_reviewed,
            workspace_paths=workspace_paths,
        )
        if not seam_id:
            continue
        if primary_seam_id and seam_id == primary_seam_id:
            result.errors.append(
                f"secondary_seams_considered[{index}].seam_id must not duplicate primary_seam.seam_id={primary_seam_id}."
            )
            continue
        if seam_id in secondary_seam_ids:
            result.errors.append(
                f"secondary_seams_considered[{index}].seam_id duplicates an earlier secondary seam ID: {seam_id}."
            )
            continue
        secondary_seam_ids.add(seam_id)

    _validate_bounded_secondary_seam_overflow(
        result,
        secondary_seams=secondary_seams,
        contract=contract,
        scope_escapes=scope_escapes,
    )

    return primary_seam_id, primary_seam_paths, secondary_seam_ids


def _validate_scope_escapes(
    result: SemanticValidationResult,
    *,
    scope_escapes: Any,
    require_reason: bool,
) -> list[dict[str, str]]:
    if scope_escapes is None:
        return []
    if not isinstance(scope_escapes, list):
        result.errors.append("scope_escapes must be a list.")
        return []

    validated: list[dict[str, str]] = []
    for index, item in enumerate(scope_escapes, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"scope_escapes[{index}] must be an object.")
            continue
        normalized_paths = _canonical_workspace_paths([item.get("path")])
        path = normalized_paths[0] if normalized_paths else ""
        reason = str(item.get("reason") or "").strip()
        if require_reason and not reason:
            result.errors.append(
                f"scope_escapes[{index}].reason must be non-empty when scope escapes are recorded."
            )
        validated.append({"path": path, "reason": reason})
    return validated


def _validate_bounded_secondary_seam_overflow(
    result: SemanticValidationResult,
    *,
    secondary_seams: list[Any],
    contract: AnalysisReviewContract,
    scope_escapes: list[dict[str, str]],
) -> None:
    if contract.mode != "bounded":
        return

    seam_count = len(secondary_seams)
    default_cap = contract.discovery_policy.max_secondary_seams_considered_bounded
    if seam_count <= default_cap:
        if scope_escapes:
            result.errors.append(
                "analysis-stage scope_escapes are only allowed when justifying a third secondary seam in bounded mode."
            )
        return
    if seam_count > default_cap + 1:
        result.errors.append(
            "secondary_seams_considered overflow: bounded mode allows at most one third secondary seam when scope_escapes explicitly justify it."
        )
        return

    third_seam = secondary_seams[default_cap]
    third_seam_paths = set()
    if isinstance(third_seam, dict):
        third_seam_paths = set(
            _canonical_workspace_paths(
                third_seam.get("paths") if isinstance(third_seam.get("paths"), list) else []
            )
        )
    escape_paths = {
        str(item.get("path") or "").strip()
        for item in scope_escapes
        if str(item.get("path") or "").strip()
    }

    missing_paths = sorted(third_seam_paths - escape_paths)
    if missing_paths:
        result.errors.append(
            "secondary_seams_considered[3] requires scope_escapes coverage for every declared third-seam path: "
            + ", ".join(missing_paths)
        )

    extra_paths = sorted(escape_paths - third_seam_paths)
    if extra_paths:
        result.errors.append(
            "analysis-stage scope_escapes used for bounded third-seam overflow must stay within secondary_seams_considered[3].paths: "
            + ", ".join(extra_paths)
        )


def _validate_seam_entry(
    result: SemanticValidationResult,
    *,
    seam: Any,
    field_name: str,
    reason_field: str,
    files_reviewed: set[str],
    workspace_paths: set[str],
) -> tuple[str | None, list[str]]:
    if not isinstance(seam, dict):
        result.errors.append(f"{field_name} must be an object.")
        return None, []

    seam_id = str(seam.get("seam_id") or "").strip()
    if not seam_id:
        result.errors.append(f"{field_name}.seam_id must be non-empty.")
    if not str(seam.get("summary") or "").strip():
        result.errors.append(f"{field_name}.summary must be non-empty.")
    if not str(seam.get(reason_field) or "").strip():
        result.errors.append(f"{field_name}.{reason_field} must be non-empty.")

    paths = seam.get("paths")
    if not isinstance(paths, list):
        result.errors.append(f"{field_name}.paths must be a list.")
        return seam_id or None, []
    path_items = _canonical_workspace_paths(paths)
    if not path_items:
        result.errors.append(f"{field_name}.paths must contain at least one non-empty path.")
        return seam_id or None, []
    missing_files = sorted(set(path_items) - files_reviewed)
    if missing_files:
        result.errors.append(
            f"{field_name}.paths must be a subset of files_reviewed: " + ", ".join(missing_files)
        )
    unknown_files = sorted(set(path_items) - workspace_paths)
    if unknown_files:
        result.errors.append(
            f"{field_name}.paths contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_files)
        )
    return seam_id or None, path_items


def _validate_expected_primary_seam_id(
    result: SemanticValidationResult,
    *,
    actual_primary_seam_id: str | None,
    expected_primary_seam_id: str | None,
    actual_primary_seam_paths: list[str],
    expected_primary_seam_paths: Iterable[str] | None,
) -> None:
    expected = str(expected_primary_seam_id or "").strip()
    actual = str(actual_primary_seam_id or "").strip()
    if expected and actual != expected:
        result.errors.append(
            "primary_seam.seam_id drifted from the selected focus gate seam: "
            f"expected {expected}, got {actual or '(missing)'}."
        )
    expected_paths = _canonical_workspace_paths(expected_primary_seam_paths)
    if expected_paths and actual_primary_seam_paths != expected_paths:
        result.errors.append(
            "primary_seam.paths drifted from the selected focus gate paths after normalization: "
            f"expected {expected_paths}, got {actual_primary_seam_paths}."
        )


def _validate_recommendation_seam_binding(
    result: SemanticValidationResult,
    *,
    recommendation: dict[str, Any],
    recommendation_index: int,
    primary_seam_id: str | None,
    declared_seam_ids: set[str],
) -> bool:
    seam_id = str(recommendation.get("seam_id") or "").strip()
    if not seam_id:
        result.errors.append(f"recommendations[{recommendation_index}].seam_id must be non-empty.")
        return False
    if seam_id not in declared_seam_ids:
        result.errors.append(
            f"recommendations[{recommendation_index}].seam_id must bind to primary_seam.seam_id or a declared secondary_seams_considered seam_id: {seam_id}"
        )
        return False

    seam_expansion_reason = str(recommendation.get("seam_expansion_reason") or "").strip()
    if primary_seam_id and seam_id == primary_seam_id:
        if seam_expansion_reason:
            result.errors.append(
                f"recommendations[{recommendation_index}].seam_expansion_reason must be empty when bound to primary_seam."
            )
        return True

    if not seam_expansion_reason:
        result.errors.append(
            f"recommendations[{recommendation_index}].seam_expansion_reason must be non-empty for non-primary seams."
        )
    return False


def _validated_focus_candidates(
    result: SemanticValidationResult,
    *,
    candidates: list[Any],
    workspace_paths: set[str],
) -> tuple[list[str], dict[str, list[str]]]:
    candidate_ids: list[str] = []
    candidate_paths_by_id: dict[str, list[str]] = {}
    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"candidates[{index}] must be an object.")
            continue
        focus_id = str(item.get("focus_id") or "").strip()
        focus_summary = str(item.get("focus_summary") or "").strip()
        if not focus_id:
            result.errors.append(f"candidates[{index}].focus_id must be non-empty.")
            continue
        if not focus_summary:
            result.errors.append(f"candidates[{index}].focus_summary must be non-empty.")
        candidate_paths = _canonical_workspace_paths(item.get("candidate_paths"))
        if not candidate_paths:
            result.errors.append(
                f"candidates[{index}].candidate_paths must contain at least one non-empty path."
            )
        unknown_candidate_paths = sorted(set(candidate_paths) - workspace_paths)
        if unknown_candidate_paths:
            result.errors.append(
                f"candidates[{index}].candidate_paths contains path(s) not present in the workspace snapshot: "
                + ", ".join(unknown_candidate_paths)
            )
        expected_focus_id = canonical_seam_id_for_paths(candidate_paths)
        if candidate_paths and focus_id != expected_focus_id:
            result.errors.append(
                f"candidates[{index}].focus_id must equal the canonical seam ID derived from candidate_paths: "
                f"expected {expected_focus_id}, got {focus_id}."
            )
        candidate_ids.append(focus_id)
        candidate_paths_by_id[focus_id] = candidate_paths
    duplicates = sorted(
        {focus_id for focus_id in candidate_ids if candidate_ids.count(focus_id) > 1}
    )
    if duplicates:
        result.errors.append(
            "candidates contains duplicate focus IDs: " + ", ".join(duplicates)
        )
    return candidate_ids, candidate_paths_by_id


def _validated_focus_question(
    result: SemanticValidationResult,
    *,
    question: Any,
) -> tuple[str, list[str]]:
    if not isinstance(question, dict):
        result.errors.append("question must be an object.")
        return "", []
    prompt = str(question.get("prompt") or "")
    options = question.get("options")
    if not isinstance(options, list):
        result.errors.append("question.options must be a list.")
        return prompt.strip(), []
    normalized_options = _non_empty_strings(options)
    return prompt.strip(), normalized_options


def _validated_focus_adapter_plan(
    result: SemanticValidationResult,
    *,
    adapter_plan: Any,
) -> tuple[str | None, list[str]]:
    if not isinstance(adapter_plan, dict):
        result.errors.append("adapter_plan must be an object.")
        return None, []

    raw_primary_focus_id = adapter_plan.get("primary_focus_id")
    if raw_primary_focus_id is None:
        primary_focus_id = None
    else:
        primary_focus_id = str(raw_primary_focus_id or "").strip() or None

    secondary_focus_ids = adapter_plan.get("secondary_focus_ids")
    if not isinstance(secondary_focus_ids, list):
        result.errors.append("adapter_plan.secondary_focus_ids must be a list.")
        return primary_focus_id, []

    normalized_secondary_focus_ids = _non_empty_strings(secondary_focus_ids)
    duplicates = sorted(
        {
            focus_id
            for focus_id in normalized_secondary_focus_ids
            if normalized_secondary_focus_ids.count(focus_id) > 1
        }
    )
    if duplicates:
        result.errors.append(
            "adapter_plan.secondary_focus_ids contains duplicate IDs: "
            + ", ".join(duplicates)
        )
    return primary_focus_id, normalized_secondary_focus_ids


def _nullable_non_empty_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validate_trust_recommendation_metadata(
    result: SemanticValidationResult,
    *,
    recommendation: dict[str, Any],
    recommendation_index: int,
    evidence_items: list[str],
    workspace_paths: set[str],
    contract: AnalysisReviewContract,
) -> None:
    verified_items = _canonical_workspace_paths(
        (recommendation.get("verified_evidence_refs") or [])
        if isinstance(recommendation.get("verified_evidence_refs"), list)
        else []
    )
    checked_items = _canonical_workspace_paths(
        (recommendation.get("checked_files") or [])
        if isinstance(recommendation.get("checked_files"), list)
        else []
    )
    affected_items = _canonical_workspace_paths(
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


def _validate_review_recommendation_metadata(
    result: SemanticValidationResult,
    *,
    recommendation_review: dict[str, Any],
    recommendation_index: int,
    files_reviewed: set[str],
    workspace_paths: set[str],
    contract: AnalysisReviewContract,
) -> None:
    checked_items = _canonical_workspace_paths(
        (recommendation_review.get("checked_files") or [])
        if isinstance(recommendation_review.get("checked_files"), list)
        else []
    )
    verified_items = _canonical_workspace_paths(
        (recommendation_review.get("verified_evidence_refs") or [])
        if isinstance(recommendation_review.get("verified_evidence_refs"), list)
        else []
    )
    verdict = str(recommendation_review.get("verdict") or "").strip().lower()

    if contract.mode == "trust" and verdict and not checked_items and not verified_items:
        result.errors.append(
            f"recommendation_reviews[{recommendation_index}] must include checked_files or verified_evidence_refs for trust-mode verdict provenance."
        )

    missing_checked_files = sorted(set(checked_items) - files_reviewed)
    if missing_checked_files:
        result.errors.append(
            f"recommendation_reviews[{recommendation_index}].checked_files must be a subset of files_reviewed: "
            + ", ".join(missing_checked_files)
        )
    unknown_checked_files = sorted(set(checked_items) - workspace_paths)
    if unknown_checked_files:
        result.errors.append(
            f"recommendation_reviews[{recommendation_index}].checked_files contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_checked_files)
        )
    missing_verified_refs = sorted(set(verified_items) - files_reviewed)
    if missing_verified_refs:
        result.errors.append(
            f"recommendation_reviews[{recommendation_index}].verified_evidence_refs must be a subset of files_reviewed: "
            + ", ".join(missing_verified_refs)
        )
    unknown_verified_refs = sorted(set(verified_items) - workspace_paths)
    if unknown_verified_refs:
        result.errors.append(
            f"recommendation_reviews[{recommendation_index}].verified_evidence_refs contains path(s) not present in the workspace snapshot: "
            + ", ".join(unknown_verified_refs)
        )


def _review_payload_requires_structured_refs(payload: dict[str, Any]) -> bool:
    closure_fields = (
        "issues",
        "topics",
        "resolved_issue_ids",
        "carried_forward_issue_ids",
        "waived_issue_ids",
        "resolved_topic_ids",
        "carried_forward_topic_ids",
        "waived_topic_ids",
    )
    for field_name in closure_fields:
        values = payload.get(field_name)
        if isinstance(values, list) and values:
            return True
    return False


def _validate_review_payload_provenance(
    result: SemanticValidationResult,
    *,
    contract: AnalysisReviewContract,
    payload_provenance: dict[str, Any] | None,
) -> None:
    if contract.mode != "trust":
        return
    if contract.trust_review.payload_provenance_mode != "payload_hash_and_refs":
        return
    provenance = payload_provenance if isinstance(payload_provenance, dict) else {}
    uncovered_recommendation_indices = _validated_provenance_index_list(
        provenance.get("uncovered_recommendation_indices")
    )
    uncovered_global_issue_ids = _non_empty_strings(
        provenance.get("uncovered_global_issue_ids")
        if isinstance(provenance.get("uncovered_global_issue_ids"), list)
        else []
    )
    uncovered_global_topic_ids = _non_empty_strings(
        provenance.get("uncovered_global_topic_ids")
        if isinstance(provenance.get("uncovered_global_topic_ids"), list)
        else []
    )
    if "closure_provenance_satisfied" in provenance:
        closure_provenance_satisfied = bool(provenance.get("closure_provenance_satisfied"))
    else:
        recommendation_review_ref_count = provenance.get("recommendation_review_ref_count", 0)
        try:
            closure_provenance_satisfied = int(recommendation_review_ref_count) > 0
        except (TypeError, ValueError):
            closure_provenance_satisfied = False
    if (
        uncovered_recommendation_indices
        or uncovered_global_issue_ids
        or uncovered_global_topic_ids
    ):
        coverage_parts: list[str] = []
        if uncovered_recommendation_indices:
            coverage_parts.append(
                "recommendation-linked closures for recommendation indices "
                + ", ".join(str(item) for item in uncovered_recommendation_indices)
            )
        if uncovered_global_issue_ids:
            coverage_parts.append(
                "global issue closures " + ", ".join(uncovered_global_issue_ids)
            )
        if uncovered_global_topic_ids:
            coverage_parts.append(
                "global topic closures " + ", ".join(uncovered_global_topic_ids)
            )
        result.errors.append(
            "trust review payload lacks provenance-complete structured review refs for "
            + "; ".join(coverage_parts)
            + ". files_reviewed alone is not sufficient."
        )
        return
    if closure_provenance_satisfied:
        return
    recommendation_review_ref_count = provenance.get("recommendation_review_ref_count", 0)
    issue_closure_review_ref_count = provenance.get("issue_closure_review_ref_count", 0)
    topic_closure_review_ref_count = provenance.get("topic_closure_review_ref_count", 0)
    try:
        ref_count = int(recommendation_review_ref_count)
    except (TypeError, ValueError):
        ref_count = 0
    try:
        issue_ref_count = int(issue_closure_review_ref_count)
    except (TypeError, ValueError):
        issue_ref_count = 0
    try:
        topic_ref_count = int(topic_closure_review_ref_count)
    except (TypeError, ValueError):
        topic_ref_count = 0
    if ref_count > 0 or issue_ref_count > 0 or topic_ref_count > 0:
        return
    result.errors.append(
        "trust review payload introduced or classified issues/topics without structured closure proof; files_reviewed alone is not sufficient, so provide recommendation_reviews checked_files/verified_evidence_refs for recommendation-linked closures and issue_closure_reviews/topic_closure_reviews for recommendation_index=null global closures."
    )


def _canonical_workspace_paths(values: Any) -> list[str]:
    if isinstance(values, (set, tuple)):
        values = list(values)
    return canonical_workspace_ref_list(values)


def _workspace_path_set(values: Iterable[str] | None) -> set[str]:
    return set(_canonical_workspace_paths(list(values or [])))


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


def _normalized_optional_recommendation_index(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if normalized < 1:
        return None
    return normalized


def _record_recommendation_index_by_id(
    records: Iterable[dict[str, Any]] | None,
    *,
    id_field: str,
) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get(id_field) or "").strip()
        if not record_id:
            continue
        result[record_id] = _normalized_optional_recommendation_index(
            item.get("recommendation_index")
        )
    return result


def _record_map_by_id(
    records: Iterable[dict[str, Any]] | None,
    *,
    id_field: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get(id_field) or "").strip()
        if not record_id:
            continue
        result[record_id] = dict(item)
    return result


def _prior_surfaced_ref_set(record: dict[str, Any] | None) -> set[str]:
    if not isinstance(record, dict):
        return set()
    values = record.get(_PRIOR_SURFACED_REFS_FIELD)
    if not isinstance(values, list):
        return set()
    return {str(item).strip() for item in values if str(item).strip()}


def _validated_provenance_index_list(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    normalized: set[int] = set()
    for item in values:
        try:
            numeric = int(item)
        except (TypeError, ValueError):
            continue
        if numeric >= 1:
            normalized.add(numeric)
    return sorted(normalized)


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


def _validate_scoped_closure_reviews(
    result: SemanticValidationResult,
    *,
    field_name: str,
    values: Any,
    id_field: str,
    prior_record_map: dict[str, dict[str, Any]],
    required_ids: list[str],
    files_reviewed: set[str],
    workspace_paths: set[str],
) -> None:
    if values is None:
        values = []
    if not isinstance(values, list):
        result.errors.append(f"{field_name} must be a list.")
        return
    seen_ids: list[str] = []
    for index, item in enumerate(values, start=1):
        if not isinstance(item, dict):
            result.errors.append(f"{field_name}[{index}] must be an object.")
            continue
        record_id = str(item.get(id_field) or "").strip()
        if not record_id:
            result.errors.append(f"{field_name}[{index}].{id_field} must be a non-empty ID.")
            continue
        seen_ids.append(record_id)
        if record_id not in prior_record_map:
            result.errors.append(
                f"{field_name}[{index}].{id_field} references an unknown prior open ID: {record_id}"
            )
        checked_items = _canonical_workspace_paths(
            item.get("checked_files") if isinstance(item.get("checked_files"), list) else []
        )
        verified_items = _canonical_workspace_paths(
            item.get("verified_evidence_refs")
            if isinstance(item.get("verified_evidence_refs"), list)
            else []
        )
        missing_checked_files = sorted(set(checked_items) - files_reviewed)
        if missing_checked_files:
            result.errors.append(
                f"{field_name}[{index}].checked_files must be a subset of files_reviewed: "
                + ", ".join(missing_checked_files)
            )
        unknown_checked_files = sorted(set(checked_items) - workspace_paths)
        if unknown_checked_files:
            result.errors.append(
                f"{field_name}[{index}].checked_files contains path(s) not present in the workspace snapshot: "
                + ", ".join(unknown_checked_files)
            )
        unexpected_verified_refs = sorted(set(verified_items) - set(checked_items))
        if unexpected_verified_refs:
            result.errors.append(
                f"{field_name}[{index}].verified_evidence_refs must be a subset of checked_files: "
                + ", ".join(unexpected_verified_refs)
            )
        unknown_verified_refs = sorted(set(verified_items) - workspace_paths)
        if unknown_verified_refs:
            result.errors.append(
                f"{field_name}[{index}].verified_evidence_refs contains path(s) not present in the workspace snapshot: "
                + ", ".join(unknown_verified_refs)
            )
        prior_surfaced_refs = _prior_surfaced_ref_set(prior_record_map.get(record_id))
        overclaimed_prior_refs = sorted(set(verified_items) - prior_surfaced_refs)
        if prior_surfaced_refs and overclaimed_prior_refs:
            result.errors.append(
                f"{field_name}[{index}].verified_evidence_refs must be a subset of the prior surfaced refs for {id_field} {record_id}: "
                + ", ".join(overclaimed_prior_refs)
            )
    duplicates = sorted({item for item in seen_ids if seen_ids.count(item) > 1})
    if duplicates:
        result.errors.append(
            f"{field_name} contains duplicate {id_field}s: " + ", ".join(duplicates)
        )
    missing_required_ids = sorted(set(required_ids) - set(seen_ids))
    if missing_required_ids:
        result.errors.append(
            f"{field_name} is missing scoped closure proof IDs: " + ", ".join(missing_required_ids)
        )


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
