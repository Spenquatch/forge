from __future__ import annotations

from anvil.harness.selection import (
    drafts_from_stage_history_v1,
    extract_drafts_from_summary,
    select_best_draft,
)
from anvil.harness.state import stage_records_from_summary


def _candidate_stage(
    *,
    stage_index: int,
    role_name: str = "proposer",
    summary: str = "Draft summary",
) -> dict:
    return {
        "stage_index": stage_index,
        "role_name": role_name,
        "structured_output": {
            "summary": summary,
            "recommendations": [],
        },
        "stdout_path": f"/tmp/{role_name}-{stage_index}.txt",
        "output_path": f"/tmp/{role_name}-{stage_index}.normalized.json",
        "raw_output_path": f"/tmp/{role_name}-{stage_index}.raw.json",
        "normalized_output_path": f"/tmp/{role_name}-{stage_index}.normalized.json",
        "requested_access": "none",
        "effective_access": "none",
    }


def _review_stage(
    *,
    stage_index: int,
    payload: dict,
    role_name: str = "critic",
    ok: bool = True,
) -> dict:
    return {
        "stage_index": stage_index,
        "role_name": role_name,
        "ok": ok,
        "structured_output": payload,
    }


def _completed_review_payload(**overrides) -> dict:
    payload = {
        "verdict": "accept",
        "issues": [],
        "recommendation_reviews": [],
        "grounding_score": 0.9,
        "actionability_score": 0.8,
        "scope_compliance_score": 0.95,
        "topics": [],
        "resolved_topic_ids": [],
        "carried_forward_topic_ids": [],
        "waived_topic_ids": [],
    }
    payload.update(overrides)
    return payload


def test_extract_drafts_counts_carried_forward_topics_as_remaining_debt():
    summary = {
        "task": {"task_kind": "patch"},
        "verdicts": {"content_verdict": "accepted_with_warnings"},
        "agent_stages": [
            _candidate_stage(stage_index=1),
            _review_stage(
                stage_index=2,
                payload=_completed_review_payload(
                    carried_forward_topic_ids=["AT-001"],
                ),
            ),
        ],
    }

    drafts = extract_drafts_from_summary(summary)

    assert len(drafts) == 1
    assert drafts[0]["issue_counts"]["topics"] == 1
    assert drafts[0]["issue_counts"]["missing_topics"] == 1
    assert drafts[0]["issue_counts"]["open_topics"] == 1
    assert drafts[0]["issue_counts"]["carried_forward_topics"] == 1
    assert drafts[0]["issue_counts"]["new_topics"] == 0


def test_extract_drafts_from_summary_matches_native_stage_history_projection():
    summary = {
        "task": {"task_kind": "patch"},
        "verdicts": {"content_verdict": "accepted_with_warnings"},
        "validator_rounds": [
            {
                "round_index": 0,
                "results": [
                    {
                        "required": True,
                        "status": "passed",
                    }
                ],
            }
        ],
        "agent_stages": [
            _candidate_stage(stage_index=1),
            {
                **_review_stage(
                    stage_index=2,
                    payload=_completed_review_payload(
                        carried_forward_topic_ids=["AT-001"],
                    ),
                ),
                "semantic_validation_payload_provenance": {
                    "policy_mode": "payload_hash_and_refs",
                    "closure_provenance_satisfied": True,
                    "uncovered_global_issue_ids": [],
                    "uncovered_global_topic_ids": [],
                    "uncovered_recommendation_indices": [],
                },
            },
        ],
    }

    native_drafts = drafts_from_stage_history_v1(
        stage_records_from_summary(summary),
        task_kind="patch",
        validator_rounds=list(summary["validator_rounds"]),
        content_verdict="accepted_with_warnings",
    )
    compatibility_drafts = extract_drafts_from_summary(summary)

    assert compatibility_drafts == native_drafts


def test_extract_drafts_sums_new_and_carried_forward_topics_into_open_topic_count():
    summary = {
        "task": {"task_kind": "patch"},
        "agent_stages": [
            _candidate_stage(stage_index=1),
            _review_stage(
                stage_index=2,
                payload=_completed_review_payload(
                    verdict="revise",
                    topics=[
                        {
                            "topic_id": "AT-002",
                            "severity": "medium",
                            "title": "Topic title",
                            "evidence": "Topic evidence",
                            "repair_hint": "Topic repair hint",
                            "recommendation_index": 1,
                        }
                    ],
                    carried_forward_topic_ids=["AT-001"],
                ),
            ),
        ],
    }

    drafts = extract_drafts_from_summary(summary)

    assert drafts[0]["issue_counts"]["topics"] == 2
    assert drafts[0]["issue_counts"]["missing_topics"] == 2
    assert drafts[0]["issue_counts"]["open_topics"] == 2
    assert drafts[0]["issue_counts"]["carried_forward_topics"] == 1
    assert drafts[0]["issue_counts"]["new_topics"] == 1


def test_extract_drafts_keeps_legacy_missing_topics_as_remaining_topic_debt():
    summary = {
        "task": {"task_kind": "patch"},
        "agent_stages": [
            _candidate_stage(stage_index=1),
            _review_stage(
                stage_index=2,
                payload=_completed_review_payload(
                    verdict="revise",
                    missing_topics=["Legacy missing topic"],
                ),
            ),
        ],
    }

    drafts = extract_drafts_from_summary(summary)

    assert drafts[0]["issue_counts"]["topics"] == 1
    assert drafts[0]["issue_counts"]["missing_topics"] == 1
    assert drafts[0]["issue_counts"]["open_topics"] == 1
    assert drafts[0]["issue_counts"]["carried_forward_topics"] == 0
    assert drafts[0]["issue_counts"]["new_topics"] == 1


def test_select_best_draft_prefers_clean_accepted_draft_over_higher_grounding_topic_debt():
    clean_draft = {
        "draft_id": "draft-clean",
        "review_status": "accepted",
        "round_index": 0,
        "issue_counts": {
            "blocking_medium_or_higher": 0,
            "medium_or_higher": 0,
            "accepted_recommendations": 1,
            "required_validator_failures": 0,
            "topics": 0,
            "open_topics": 0,
        },
        "scores": {"grounding_score": 0.71},
        "metadata": {"stage_index": 1},
    }
    caveated_draft = {
        "draft_id": "draft-caveated",
        "review_status": "accepted",
        "round_index": 1,
        "issue_counts": {
            "blocking_medium_or_higher": 0,
            "medium_or_higher": 0,
            "accepted_recommendations": 1,
            "required_validator_failures": 0,
            "topics": 1,
            "open_topics": 1,
            "carried_forward_topics": 1,
        },
        "scores": {"grounding_score": 0.99},
        "metadata": {"stage_index": 3},
    }

    best = select_best_draft([caveated_draft, clean_draft])

    assert best is not None
    assert best["draft_id"] == "draft-clean"
    assert best["review_status"] == "best"


def test_select_best_draft_penalizes_incomplete_closure_provenance():
    clean_draft = {
        "draft_id": "draft-proven",
        "review_status": "accepted",
        "round_index": 0,
        "issue_counts": {
            "blocking_medium_or_higher": 0,
            "medium_or_higher": 0,
            "accepted_recommendations": 1,
            "required_validator_failures": 0,
            "topics": 0,
            "open_topics": 0,
            "provenance_incomplete": 0,
            "uncovered_closure_count": 0,
        },
        "scores": {"grounding_score": 0.72},
        "metadata": {"stage_index": 1},
    }
    unproven_draft = {
        "draft_id": "draft-unproven",
        "review_status": "accepted",
        "round_index": 1,
        "issue_counts": {
            "blocking_medium_or_higher": 0,
            "medium_or_higher": 0,
            "accepted_recommendations": 1,
            "required_validator_failures": 0,
            "topics": 0,
            "open_topics": 0,
            "provenance_incomplete": 1,
            "uncovered_closure_count": 1,
        },
        "scores": {"grounding_score": 0.99},
        "metadata": {"stage_index": 3},
    }

    best = select_best_draft([unproven_draft, clean_draft])

    assert best is not None
    assert best["draft_id"] == "draft-proven"
