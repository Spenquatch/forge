from __future__ import annotations

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
