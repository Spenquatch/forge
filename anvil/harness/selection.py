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
    counts = {"low": 0, "medium": 0, "high": 0, "critical": 0, "medium_or_higher": 0}
    if not isinstance(issues, list):
        return counts
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", "")).strip().lower()
        if severity in counts:
            counts[severity] += 1
        if severity in {"medium", "high", "critical"}:
            counts["medium_or_higher"] += 1
    return counts


def _required_validator_failure_count(results: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in results
        if item.get("required") and str(item.get("status", "")).lower() in {"failed", "error"}
    )


def _draft_review_status(payload: dict[str, Any]) -> str | None:
    verdict = str(payload.get("verdict", "")).strip().lower()
    if verdict == "accept":
        return "accepted"
    if verdict == "reject":
        return "rejected"
    return None


def _is_candidate_stage(stage: dict[str, Any]) -> bool:
    role_name = str(stage.get("role_name") or "")
    return role_name.startswith(_CANDIDATE_PREFIXES)


def _is_review_stage(stage: dict[str, Any]) -> bool:
    role_name = str(stage.get("role_name") or "")
    return role_name.startswith(_REVIEW_PREFIXES)


def extract_drafts_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Project agent stages + validator rounds into the draft contract from ADR-0024.

    The imperative runner records stage envelopes in order. The harness graph uses
    those envelopes to reconstruct durable draft metadata without replaying the
    raw transcripts.
    """

    task = summary.get("task") or {}
    task_kind = str(task.get("task_kind", "patch"))
    validator_rounds = {
        int(round_blob.get("round_index", 0)): list(round_blob.get("results", []))
        for round_blob in summary.get("validator_rounds", [])
    }

    drafts: list[dict[str, Any]] = []
    latest_draft: dict[str, Any] | None = None

    for stage_index, stage in enumerate(summary.get("agent_stages", []), start=1):
        if not isinstance(stage, dict):
            continue
        payload = stage.get("structured_output")
        if not isinstance(payload, dict) or not payload:
            continue

        role_name = str(stage.get("role_name") or "")
        stage_id = f"stage-{stage.get('stage_index', stage_index):02d}-{slugify(role_name)}"

        if _is_candidate_stage(stage):
            round_index = _candidate_round_index(role_name)
            validator_results = validator_rounds.get(round_index, [])
            issue_counts = {
                **_count_issue_severities(payload),
                "required_validator_failures": _required_validator_failure_count(validator_results),
                "missing_topics": len(payload.get("missing_topics", []) or []),
            }
            draft = {
                "draft_id": f"draft-{slugify(role_name)}",
                "source_stage_id": stage_id,
                "role_name": role_name,
                "task_kind": task_kind,
                "round_index": round_index,
                "text_path": str(stage.get("stdout_path") or ""),
                "json_path": str(stage.get("output_path") or "") or None,
                "summary": str(payload.get("summary", "") or ""),
                "review_status": "candidate",
                "scores": {},
                "issue_counts": issue_counts,
                "metadata": {
                    "stage_index": int(stage.get("stage_index", stage_index)),
                    "requested_access": stage.get("requested_access"),
                    "effective_access": stage.get("effective_access"),
                    "payload": copy.deepcopy(payload),
                    "validator_round_index": round_index,
                    "validator_results": copy.deepcopy(validator_results),
                },
            }
            drafts.append(draft)
            latest_draft = draft
            continue

        if _is_review_stage(stage) and latest_draft is not None:
            issue_counts = latest_draft.setdefault("issue_counts", {})
            review_counts = _count_issue_severities(payload)
            for key, value in review_counts.items():
                issue_counts[key] = max(int(issue_counts.get(key, 0)), int(value))
            issue_counts["missing_topics"] = max(
                int(issue_counts.get("missing_topics", 0)),
                len(payload.get("missing_topics", []) or []),
            )
            scores = latest_draft.setdefault("scores", {})
            for field_name in (
                "grounding_score",
                "actionability_score",
                "scope_compliance_score",
                "confidence",
            ):
                value = payload.get(field_name)
                if value is None:
                    continue
                try:
                    scores[field_name] = float(value)
                except (TypeError, ValueError):
                    continue
            review_status = _draft_review_status(payload)
            if review_status is not None:
                latest_draft["review_status"] = review_status
            latest_draft.setdefault("metadata", {})["review_stage_id"] = stage_id
            latest_draft["metadata"]["review_payload"] = copy.deepcopy(payload)
            latest_draft["metadata"]["reviewer_role"] = role_name

    content_verdict = str((summary.get("verdicts") or {}).get("content_verdict") or "")
    if drafts:
        if content_verdict in {"accepted", "accepted_with_warnings"}:
            drafts[-1]["review_status"] = "accepted"
        elif content_verdict in {"rejected", "best_effort_exhausted"} and not any(
            draft.get("review_status") == "accepted" for draft in drafts
        ):
            drafts[-1]["review_status"] = "rejected"

    return drafts


def select_best_draft(drafts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the best available draft following ADR-0024's ordering."""

    candidates = [draft for draft in drafts if isinstance(draft, dict)]
    if not candidates:
        return None

    def _sort_key(draft: dict[str, Any]) -> tuple[Any, ...]:
        issue_counts = draft.get("issue_counts") or {}
        scores = draft.get("scores") or {}
        medium_plus = int(issue_counts.get("medium_or_higher", 0))
        accepted = 0 if draft.get("review_status") == "accepted" else 1
        grounding = float(scores.get("grounding_score", -1.0))
        validator_failures = int(issue_counts.get("required_validator_failures", 0))
        round_index = int(draft.get("round_index", 0))
        stage_index = int((draft.get("metadata") or {}).get("stage_index", 0))
        return (
            0 if medium_plus == 0 else 1,
            accepted,
            -grounding,
            validator_failures,
            -round_index,
            -stage_index,
        )

    best = min(candidates, key=_sort_key)
    best_copy = copy.deepcopy(best)
    best_copy["review_status"] = "best"
    return best_copy
