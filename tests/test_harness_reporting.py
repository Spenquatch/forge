from __future__ import annotations

from anvil.harness.report import render_report
from anvil.harness.reporting import render_deliverable_markdown


def _rendered_section(markdown: str, heading_prefix: str) -> str:
    section = markdown.split(heading_prefix, 1)[1]
    if "\n### " in section:
        section = section.split("\n### ", 1)[0]
    return section


def test_render_deliverable_markdown_attaches_caveats_to_affected_recommendations():
    payload = {
        "summary": "Prioritized recommendations.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "high",
                "title": "Tighten retry policy",
                "rationale": "Current retries can duplicate releases.",
                "evidence": ["a.py"],
                "proposed_change": "Reduce retry fanout.",
                "confidence": 0.78,
            },
            {
                "classification": "risk",
                "priority": "medium",
                "title": "Document fallback path",
                "rationale": "Fallback behavior is inferred from adjacent workflow logic.",
                "evidence": ["b.py"],
                "proposed_change": "Describe the fallback explicitly.",
                "confidence": 0.64,
            },
            {
                "classification": "recommendation",
                "priority": "low",
                "title": "Normalize logging labels",
                "rationale": "Labels diverge across handlers.",
                "evidence": ["c.py"],
                "proposed_change": "Align the label set.",
                "confidence": 0.82,
            },
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "recommendation_reviews": [
            {
                "recommendation_index": 1,
                "verdict": "accept_with_caveat",
                "summary": "Useful recommendation with a caveat about rollout timing.",
            },
            {
                "recommendation_index": 2,
                "verdict": "accept",
                "summary": "Acceptable, but grounded by inference.",
            },
            {
                "recommendation_index": 3,
                "verdict": "accept",
                "summary": "Fully grounded.",
            },
        ],
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "downgrade_causes": [
                "accepted recommendations rely on inference-only grounding: 2"
            ],
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "accepted_recommendations_with_inferred_grounding": [2],
        },
    }

    markdown = render_deliverable_markdown(
        "task-123",
        payload,
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    recommendation_one = _rendered_section(markdown, "### 1. Tighten retry policy")
    recommendation_two = _rendered_section(markdown, "### 2. Document fallback path")
    recommendation_three = _rendered_section(markdown, "### 3. Normalize logging labels")

    assert "This recommendation carries review caveats:" in recommendation_one
    assert "Useful recommendation with a caveat about rollout timing." in recommendation_one
    assert "inference-only grounding" not in recommendation_one

    assert "This recommendation carries review caveats:" in recommendation_two
    assert (
        "This recommendation relies on inference-only grounding rather than direct verified evidence."
        in recommendation_two
    )

    assert "This recommendation carries review caveats:" not in recommendation_three


def test_render_deliverable_markdown_uses_original_indices_for_partial_answers():
    payload = {
        "summary": "Partial acceptance output.",
        "included_recommendation_indices": [2, 3],
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Second original recommendation",
                "rationale": "Carries a reviewer caveat.",
                "evidence": ["b.py"],
                "proposed_change": "Adjust rollout docs.",
                "confidence": 0.66,
            },
            {
                "classification": "risk",
                "priority": "medium",
                "title": "Third original recommendation",
                "rationale": "Accepted with inference-only grounding.",
                "evidence": ["c.py"],
                "proposed_change": "Narrow the claim.",
                "confidence": 0.59,
            },
        ],
    }
    summary = {
        "verdict": "accepted_partial",
        "recommendation_reviews": [
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Retain this recommendation, but validate rollout ordering before landing it.",
            },
            {
                "recommendation_index": 3,
                "verdict": "accept",
                "summary": "Grounding is weaker than the first item.",
            },
        ],
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "downgrade_causes": [
                "accepted recommendations rely on inference-only grounding: 3"
            ],
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "accepted_recommendations_with_inferred_grounding": [3],
        },
    }

    markdown = render_deliverable_markdown(
        "task-456",
        payload,
        artifact_label="PARTIAL_ANSWER",
        accepted=False,
        summary=summary,
    )

    recommendation_one = _rendered_section(markdown, "### 1. Second original recommendation")
    recommendation_two = _rendered_section(markdown, "### 2. Third original recommendation")

    assert "validate rollout ordering before landing it" in recommendation_one
    assert (
        "This recommendation relies on inference-only grounding rather than direct verified evidence."
        in recommendation_two
    )


def test_render_deliverable_markdown_renders_compact_topic_lifecycle_when_topics_exist():
    payload = {
        "summary": "Accepted recommendations with a resolved review topic.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify operator fallback path",
                "rationale": "Operators need an explicit fallback classification.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
    }
    summary = {
        "verdict": "accepted",
        "analysis_review_status": {
            "mode": "bounded",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
            },
            "topic_ledger_count": 1,
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": ["TOPIC-001"],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "source_stage_id": "stage-02-critic",
                "resolution_status": "resolved",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "repair_hint": "Clarify the fallback label and operator path together.",
                "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-789",
        payload,
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert "## Topic Lifecycle" in markdown
    assert (
        "- `TOPIC-001` `resolved` via `critic`: Recommendation 1 needs a concrete fallback classification. — addressed | Added the fallback classification note to recommendation 1."
        in markdown
    )


def test_render_report_renders_full_topic_lifecycle_section():
    summary = {
        "verdict": "accepted_partial",
        "task": {"id": "task-789"},
        "verdicts": {
            "content_verdict": "accepted_partial",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {
            "bounded_review_summary": {
                "mode": "recommendation_review_surface",
                "recommendation_count": 1,
                "recommendations_with_review_surface": 1,
                "scope_escape_count": 0,
                "scope_escapes": [],
                "review_stages": [
                    {
                        "role_name": "critic",
                        "round_index": 0,
                        "issue_count": 0,
                        "issue_cap": 5,
                        "missing_topic_count": 1,
                        "missing_topic_cap": 2,
                        "new_topic_count": 1,
                        "new_topic_cap": 2,
                        "resolved_topic_count": 0,
                        "carried_forward_topic_count": 0,
                        "waived_topic_count": 0,
                        "open_topic_count": 1,
                        "new_medium_or_higher_issue_count": 0,
                        "new_medium_or_higher_issue_cap": None,
                        "topic_ledger_count": 1,
                        "scope_escape_count": 0,
                    },
                    {
                        "role_name": "auditor",
                        "round_index": 1,
                        "issue_count": 0,
                        "issue_cap": None,
                        "missing_topic_count": 0,
                        "missing_topic_cap": None,
                        "new_topic_count": 0,
                        "new_topic_cap": None,
                        "resolved_topic_count": 1,
                        "carried_forward_topic_count": 0,
                        "waived_topic_count": 0,
                        "open_topic_count": 0,
                        "new_medium_or_higher_issue_count": 0,
                        "new_medium_or_higher_issue_cap": 1,
                        "topic_ledger_count": 1,
                        "scope_escape_count": 0,
                    },
                ],
            }
        },
        "analysis_review_contract": {
            "mode": "bounded",
            "bounded_review": {
                "critic_issue_cap": 5,
                "critic_new_topic_cap": 2,
                "auditor_new_medium_or_higher_issue_cap_after_round0": 1,
            },
        },
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "bounded",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
                "required": False,
                "stages": [],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": ["TOPIC-001"],
            "waived_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "source_stage_id": "stage-02-critic",
                "first_seen_round": 0,
                "last_seen_round": 1,
                "severity": "medium",
                "recommendation_index": 1,
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "repair_hint": "Clarify the fallback label and operator path together.",
                "resolution_status": "resolved",
                "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
            }
        ],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "## Topic Lifecycle" in report
    assert "- Topic ledger entries: `1`" in report
    assert "- Resolved topics: `1` (`TOPIC-001`)" in report
    assert "### TOPIC-001 — medium — resolved" in report
    assert "- Introduced by: `critic`" in report
    assert "- Resolution note: addressed | Added the fallback classification note to recommendation 1." in report
