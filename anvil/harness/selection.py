from __future__ import annotations

"""Draft extraction and best-draft selection helpers for the harness surface."""

import copy
import re
from typing import Any

from .files import slugify

_CANDIDATE_PREFIXES = ("solver", "proposer", "patcher", "reviser")
_REVIEW_PREFIXES = ("critic", "auditor", "falsifier")
_ROUND_RE = re.compile(r"_round_(\d+)$")


def _candidate_round_index(role_name: str) -> int:
    match = _ROUND_RE.search(role_name)
    if match:
        return int(match.group(1))
    return 0


def _count_issue_severities(payload: dict[str, Any]) -> dict[str, int]:
    issues = payload.get("issues")
    counts = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
        "medium_or_higher": 0,
        "blocking_medium_or_higher": 0,
    }
    if not isinstance(issues, list):
        return counts
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", "")).strip().lower()
        blocking_class = (
            str(issue.get("blocking_class", "presentation")).strip().lower()
        )
        if severity in counts:
            counts[severity] += 1
        if severity in {"medium", "high", "critical"}:
            counts["medium_or_higher"] += 1
            if blocking_class in {"correctness", "actionability", "completeness"}:
                counts["blocking_medium_or_higher"] += 1
    return counts


def _required_validator_failure_count(results: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in results
        if item.get("required")
        and str(item.get("status", "")).lower() in {"failed", "error"}
    )


def _draft_review_status(payload: dict[str, Any]) -> str | None:
    verdict = str(payload.get("verdict", "")).strip().lower()
    if verdict == "accept":
        return "accepted"
    if verdict == "accept_partial":
        return "accepted_partial"
    if verdict == "reject":
        return "rejected"
    return None


def _accepted_recommendation_count(payload: dict[str, Any]) -> int:
    reviews = payload.get("recommendation_reviews")
    if not isinstance(reviews, list):
        return 0
    return sum(
        1
        for item in reviews
        if isinstance(item, dict)
        and str(item.get("verdict", "")).strip().lower()
        in {"accept", "accept_with_caveat"}
    )


def _remaining_topic_counts(payload: dict[str, Any]) -> tuple[int, int, int]:
    """Return unresolved topic counts for a completed review payload.

    carried_forward_topic_ids represents prior topics that remain unresolved for the
    current draft, so those IDs must count as remaining topic debt during draft
    reconstruction and ranking.
    """

    new_topic_count = len(payload.get("topics", []) or [])
    if not new_topic_count:
        new_topic_count = len(payload.get("missing_topics", []) or [])
    carried_forward_topic_count = len(
        payload.get("carried_forward_topic_ids", []) or []
    )
    return (
        new_topic_count,
        carried_forward_topic_count,
        new_topic_count + carried_forward_topic_count,
    )


def _review_provenance_penalty(
    payload: dict[str, Any], stage: dict[str, Any]
) -> tuple[int, int]:
    provenance = stage.get("semantic_validation_payload_provenance")
    if not isinstance(provenance, dict):
        metadata = stage.get("metadata")
        if isinstance(metadata, dict):
            provenance = metadata.get("semantic_validation_payload_provenance")
    if not isinstance(provenance, dict):
        return (0, 0)
    policy_mode = str(provenance.get("policy_mode") or "").strip().lower()
    if policy_mode != "payload_hash_and_refs":
        return (0, 0)
    closure_satisfied = bool(provenance.get("closure_provenance_satisfied"))
    uncovered_global_issue_ids = provenance.get("uncovered_global_issue_ids") or []
    uncovered_global_topic_ids = provenance.get("uncovered_global_topic_ids") or []
    uncovered_global_count = len(uncovered_global_issue_ids) + len(
        uncovered_global_topic_ids
    )
    uncovered_recommendation_indices = (
        provenance.get("uncovered_recommendation_indices") or []
    )
    uncovered_recommendation_count = len(uncovered_recommendation_indices)
    if (
        closure_satisfied
        and uncovered_global_count == 0
        and uncovered_recommendation_count == 0
    ):
        return (0, 0)
    return (1, uncovered_global_count + uncovered_recommendation_count)


def _is_candidate_stage(stage: dict[str, Any]) -> bool:
    role_name = str(stage.get("role_name") or "")
    return role_name.startswith(_CANDIDATE_PREFIXES)


def _is_review_stage(stage: dict[str, Any]) -> bool:
    role_name = str(stage.get("role_name") or "")
    return role_name.startswith(_REVIEW_PREFIXES)


def _looks_like_completed_review_payload(payload: dict[str, Any]) -> bool:
    required_fields = {
        "verdict",
        "issues",
        "recommendation_reviews",
        "grounding_score",
        "actionability_score",
        "scope_compliance_score",
    }
    return isinstance(payload, dict) and required_fields.issubset(payload)


def _stage_metadata(stage: dict[str, Any]) -> dict[str, Any]:
    metadata = stage.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _stage_payload(stage: dict[str, Any]) -> dict[str, Any] | None:
    payload = stage.get("structured_output")
    if isinstance(payload, dict):
        return payload
    payload = _stage_metadata(stage).get("structured_output")
    if isinstance(payload, dict):
        return payload
    return None


def _stage_text_path(stage: dict[str, Any]) -> str:
    value = stage.get("text_path")
    if value in (None, ""):
        value = stage.get("stdout_path")
    return str(value or "")


def _stage_json_path(stage: dict[str, Any], key: str, legacy_key: str) -> str | None:
    value = stage.get(key)
    if value in (None, ""):
        value = stage.get(legacy_key)
    if value in (None, ""):
        return None
    return str(value)


def _stage_failure_value(stage: dict[str, Any], key: str) -> str | None:
    value = stage.get(key)
    if value in (None, ""):
        value = _stage_metadata(stage).get(key)
    if value in (None, ""):
        return None
    return str(value)


def drafts_from_stage_history_v1(
    stage_history: list[dict[str, Any]],
    *,
    task_kind: str,
    validator_rounds: list[dict[str, Any]] | None = None,
    content_verdict: str | None = None,
) -> list[dict[str, Any]]:
    """Project native stage history into the durable draft contract from ADR-0024.

    The graph-owned path carries stage_history directly in HarnessState. This
    projector rebuilds draft semantics from that native state instead of
    round-tripping through summary-shaped compatibility wrappers.
    """

    validator_rounds_by_index = {
        int(round_blob.get("round_index", 0)): list(round_blob.get("results", []))
        for round_blob in (validator_rounds or [])
    }

    drafts: list[dict[str, Any]] = []
    latest_draft: dict[str, Any] | None = None

    for stage_index, stage in enumerate(stage_history, start=1):
        if not isinstance(stage, dict):
            continue
        payload = _stage_payload(stage)
        if not isinstance(payload, dict) or not payload:
            continue

        role_name = str(stage.get("role_name") or "")
        stage_id = str(
            stage.get("stage_id")
            or f"stage-{stage.get('stage_index', stage_index):02d}-{slugify(role_name)}"
        )

        if _is_candidate_stage(stage):
            round_index = _candidate_round_index(role_name)
            validator_results = validator_rounds_by_index.get(round_index, [])
            issue_counts = {
                "required_validator_failures": _required_validator_failure_count(
                    validator_results
                ),
            }
            draft = {
                "draft_id": f"draft-{slugify(role_name)}",
                "source_stage_id": stage_id,
                "role_name": role_name,
                "task_kind": task_kind,
                "round_index": round_index,
                "text_path": _stage_text_path(stage),
                "json_path": _stage_json_path(stage, "json_path", "output_path"),
                "raw_json_path": _stage_json_path(
                    stage, "raw_json_path", "raw_output_path"
                ),
                "normalized_json_path": _stage_json_path(
                    stage,
                    "normalized_json_path",
                    "normalized_output_path",
                ),
                "summary": str(payload.get("summary", "") or ""),
                "review_status": "candidate",
                "review_state": "not_evaluated",
                "scores": {},
                "issue_counts": issue_counts,
                "metadata": {
                    "stage_index": int(stage.get("stage_index", stage_index)),
                    "requested_access": stage.get("requested_access"),
                    "effective_access": stage.get("effective_access"),
                    "payload": copy.deepcopy(payload),
                    "validator_round_index": round_index,
                    "validator_results": copy.deepcopy(validator_results),
                    "review_attempted": False,
                    "review_completed": False,
                },
            }
            drafts.append(draft)
            latest_draft = draft
            continue

        if _is_review_stage(stage) and latest_draft is not None:
            metadata = latest_draft.setdefault("metadata", {})
            metadata["review_stage_id"] = stage_id
            metadata["reviewer_role"] = role_name
            metadata["review_attempted"] = True

            if not stage.get("ok") or not _looks_like_completed_review_payload(payload):
                latest_draft["review_state"] = "not_evaluated"
                metadata["review_completed"] = False
                metadata["review_failure_kind"] = (
                    _stage_failure_value(stage, "failure_kind") or "review_stage_failed"
                )
                metadata["review_failure_summary"] = (
                    _stage_failure_value(stage, "failure_summary")
                    or _stage_failure_value(stage, "error")
                    or "Review stage did not produce a valid review payload."
                )
                metadata["review_attempt_payload"] = copy.deepcopy(payload)
                continue

            latest_draft["review_state"] = "evaluated"
            metadata["review_completed"] = True
            issue_counts = latest_draft.setdefault("issue_counts", {})
            review_counts = _count_issue_severities(payload)
            for key, value in review_counts.items():
                issue_counts[key] = max(int(issue_counts.get(key, 0)), int(value))
            provenance_incomplete, uncovered_closure_count = _review_provenance_penalty(
                payload,
                stage,
            )
            new_topic_count, carried_forward_topic_count, open_topic_count = (
                _remaining_topic_counts(payload)
            )
            issue_counts["topics"] = max(
                int(issue_counts.get("topics", 0)),
                open_topic_count,
            )
            issue_counts["missing_topics"] = max(
                int(issue_counts.get("missing_topics", 0)),
                open_topic_count,
            )
            issue_counts["new_topics"] = max(
                int(issue_counts.get("new_topics", 0)),
                new_topic_count,
            )
            issue_counts["carried_forward_topics"] = max(
                int(issue_counts.get("carried_forward_topics", 0)),
                carried_forward_topic_count,
            )
            issue_counts["open_topics"] = max(
                int(issue_counts.get("open_topics", 0)),
                open_topic_count,
            )
            issue_counts["accepted_recommendations"] = max(
                int(issue_counts.get("accepted_recommendations", 0)),
                _accepted_recommendation_count(payload),
            )
            issue_counts["provenance_incomplete"] = max(
                int(issue_counts.get("provenance_incomplete", 0)),
                provenance_incomplete,
            )
            issue_counts["uncovered_closure_count"] = max(
                int(issue_counts.get("uncovered_closure_count", 0)),
                uncovered_closure_count,
            )
            scores = latest_draft.setdefault("scores", {})
            for field_name in (
                "grounding_score",
                "actionability_score",
                "scope_compliance_score",
                "confidence",
            ):
                score_value: Any = payload.get(field_name)
                if score_value is None:
                    continue
                try:
                    scores[field_name] = float(score_value)
                except (TypeError, ValueError):
                    continue
            review_status = _draft_review_status(payload)
            if review_status is not None:
                latest_draft["review_status"] = review_status
            metadata["review_payload"] = copy.deepcopy(payload)

    normalized_content_verdict = str(content_verdict or "").strip().lower()
    if drafts:
        if normalized_content_verdict in {"accepted", "accepted_with_warnings"}:
            drafts[-1]["review_status"] = "accepted"
            drafts[-1]["review_state"] = "evaluated"
        elif normalized_content_verdict == "accepted_partial":
            drafts[-1]["review_status"] = "accepted_partial"
            drafts[-1]["review_state"] = "evaluated"
        elif normalized_content_verdict in {
            "rejected",
            "best_effort_exhausted",
        } and not any(
            draft.get("review_status") in {"accepted", "accepted_partial"}
            for draft in drafts
        ):
            drafts[-1]["review_status"] = "rejected"
            drafts[-1]["review_state"] = "evaluated"

    return drafts


def extract_drafts_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibility wrapper that delegates summary-shaped inputs to the native projector."""

    task = summary.get("task") or {}
    verdicts = summary.get("verdicts") or {}
    return drafts_from_stage_history_v1(
        list(summary.get("agent_stages") or []),
        task_kind=str(task.get("task_kind", "patch")),
        validator_rounds=list(summary.get("validator_rounds", [])),
        content_verdict=(
            None
            if verdicts.get("content_verdict") in (None, "")
            else str(verdicts.get("content_verdict"))
        ),
    )


def select_best_draft(drafts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the best available draft following ADR-0024's ordering."""

    candidates = [draft for draft in drafts if isinstance(draft, dict)]
    if not candidates:
        return None

    def _status_rank(draft: dict[str, Any]) -> int:
        status = str(draft.get("review_status") or "candidate")
        if status == "accepted":
            return 0
        if status == "accepted_partial":
            return 1
        if status == "candidate":
            return 2
        if status == "rejected":
            return 3
        return 4

    def _sort_key(draft: dict[str, Any]) -> tuple[Any, ...]:
        issue_counts = draft.get("issue_counts") or {}
        scores = draft.get("scores") or {}
        accepted_recommendations = int(issue_counts.get("accepted_recommendations", 0))
        blocking_medium_plus = int(issue_counts.get("blocking_medium_or_higher", 0))
        medium_plus = int(issue_counts.get("medium_or_higher", 0))
        open_topics = int(
            issue_counts.get("open_topics", issue_counts.get("topics", 0))
        )
        provenance_incomplete = int(issue_counts.get("provenance_incomplete", 0))
        uncovered_closure_count = int(issue_counts.get("uncovered_closure_count", 0))
        grounding = float(scores.get("grounding_score", -1.0))
        validator_failures = int(issue_counts.get("required_validator_failures", 0))
        round_index = int(draft.get("round_index", 0))
        stage_index = int((draft.get("metadata") or {}).get("stage_index", 0))
        return (
            _status_rank(draft),
            0 if blocking_medium_plus == 0 else 1,
            0 if medium_plus == 0 else 1,
            provenance_incomplete,
            uncovered_closure_count,
            0 if open_topics == 0 else 1,
            open_topics,
            -accepted_recommendations,
            validator_failures,
            -grounding,
            -round_index,
            -stage_index,
        )

    best = min(candidates, key=_sort_key)
    best_copy = copy.deepcopy(best)
    best_copy["review_status"] = "best"
    return best_copy
