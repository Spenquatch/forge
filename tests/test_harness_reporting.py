from __future__ import annotations

import json

from anvil.harness.nodes.write_artifacts import write_artifacts_node
from anvil.harness.report import render_report
from anvil.harness.reporting import (
    _artifact_label_for_kind,
    apply_final_artifacts,
    build_partial_answer_payload,
    render_deliverable_markdown,
)


def _rendered_section(markdown: str, heading_prefix: str) -> str:
    section = markdown.split(heading_prefix, 1)[1]
    if "\n### " in section:
        section = section.split("\n### ", 1)[0]
    return section


def _best_draft_record(payload: dict[str, object]) -> dict[str, object]:
    return {
        "draft_id": "draft-clean",
        "review_status": "accepted",
        "review_state": "evaluated",
        "round_index": 0,
        "summary": str(payload.get("summary") or ""),
        "issue_counts": {
            "blocking_medium_or_higher": 0,
            "medium_or_higher": 0,
            "accepted_recommendations": len(payload.get("recommendations") or []),
            "required_validator_failures": 0,
            "topics": 0,
            "open_topics": 0,
        },
        "scores": {
            "grounding_score": 0.72,
            "actionability_score": 0.81,
            "scope_compliance_score": 0.88,
        },
        "metadata": {"stage_index": 1, "payload": payload},
    }


def _section_payload_with_redundant_none_reason() -> dict[str, object]:
    return {
        "summary": "Payload with populated and empty analysis sections.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Document fallback handling",
                "rationale": "Operators need an explicit fallback path.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
        "strengths": {
            "items": ["Grounded in workflow files"],
            "none_reason": "This stale schema text should not leak.",
        },
        "uncertainties": {
            "items": [],
            "none_reason": "No material uncertainties remained after comparing the relevant files.",
        },
    }


def _first_line(path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0]


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
        artifact_kind="final_answer",
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
        artifact_kind="partial_answer",
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


def test_render_deliverable_markdown_omits_none_reason_label_in_analysis_sections():
    markdown = render_deliverable_markdown(
        "task-sections",
        _section_payload_with_redundant_none_reason(),
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary={"analysis_review_status": {"mode": "bounded"}},
    )

    strengths = _rendered_section(markdown, "## Strengths")
    uncertainties = _rendered_section(markdown, "## Uncertainties")

    assert "- Grounded in workflow files" in strengths
    assert "This stale schema text should not leak." not in strengths
    assert "No material uncertainties remained after comparing the relevant files." in uncertainties
    assert "none_reason:" not in markdown


def test_render_deliverable_markdown_compacts_recommendation_evidence_preview():
    payload = {
        "summary": "Accepted recommendations with long evidence lists.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify fallback handling",
                "rationale": "Operators need a direct fallback rule.",
                "evidence": ["a.py", "b.py", "c.py", "d.py"],
                "proposed_change": "Document the fallback rule explicitly.",
                "confidence": 0.74,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-evidence-preview",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary={"analysis_review_status": {"mode": "bounded"}},
    )

    recommendation = _rendered_section(markdown, "### 1. Clarify fallback handling")

    assert "- a.py" in recommendation
    assert "- b.py" in recommendation
    assert "- c.py" in recommendation
    assert "- (+1 more)" in recommendation
    assert "- d.py" not in recommendation


def test_build_partial_answer_payload_filters_topic_blocked_accepted_recommendations():
    payload = {
        "summary": "Partial acceptance output.",
        "recommendations": [
            {"title": "First", "classification": "recommendation", "priority": "medium"},
            {"title": "Second", "classification": "recommendation", "priority": "medium"},
            {"title": "Third", "classification": "recommendation", "priority": "medium"},
        ],
    }
    summary = {
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept_with_caveat", "summary": "Carries topic debt."},
            {"recommendation_index": 3, "verdict": "accept", "summary": "Clean."},
        ],
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "resolution_status": "carried_forward",
                "recommendation_index": 2,
            }
        ],
    }

    partial_payload = build_partial_answer_payload(summary, payload)

    assert partial_payload is not None
    assert partial_payload["included_recommendation_indices"] == [1, 3]
    assert partial_payload["excluded_recommendation_indices"] == [2]
    assert [item["title"] for item in partial_payload["recommendations"]] == ["First", "Third"]
    assert [
        item["recommendation_index"] for item in partial_payload["recommendation_reviews"]
    ] == [1, 3]


def test_build_partial_answer_payload_returns_none_when_trust_provenance_is_incomplete():
    payload = {
        "summary": "Partial acceptance output.",
        "recommendations": [
            {"title": "First", "classification": "recommendation", "priority": "medium"},
            {"title": "Second", "classification": "recommendation", "priority": "medium"},
        ],
    }
    summary = {
        "verdict": "accepted_partial",
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept", "summary": "Also clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
        },
        "topic_ledger": [],
    }

    partial_payload = build_partial_answer_payload(summary, payload)

    assert partial_payload is None


def test_render_deliverable_markdown_names_uncovered_recommendation_indices_in_trust_mode():
    payload = {
        "summary": "Accepted recommendations with incomplete trust provenance.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify operator fallback path",
                "rationale": "Operators need a concrete fallback path.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "uncovered_recommendation_indices": [1, 2],
                "uncovered_global_issue_ids": ["AR-001"],
                "uncovered_global_topic_ids": ["TOPIC-001"],
            },
            "topic_ledger_count": 0,
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
    }

    markdown = render_deliverable_markdown(
        "task-trust-incomplete",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert (
        "- Closure proof incomplete: recommendation-linked closures for recommendation indices 1, 2; uncovered global issue closures: AR-001; uncovered global topic closures: TOPIC-001"
        in markdown
    )


def test_apply_final_artifacts_scopes_partial_answer_review_status_to_included_recommendations(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-scope"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "strengths": {
                "items": ["Grounded in workflow files"],
                "none_reason": "This stale schema text should not leak.",
            },
            "summary": "Partial acceptance output.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Clean recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Carries excluded topic debt.",
                    "evidence": ["b.py"],
                    "proposed_change": "Do not ship this one.",
                    "confidence": 0.62,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Third",
                    "rationale": "Included, but inference-backed.",
                    "evidence": ["c.py"],
                    "proposed_change": "Ship with narrower claim.",
                    "confidence": 0.58,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Carries topic debt.",
            },
            {"recommendation_index": 3, "verdict": "accept", "summary": "Inference-backed."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "accepted_recommendations_with_inferred_grounding": [3],
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": [
                "review topics remain open: TOPIC-001",
                "accepted recommendation reviews include accept_with_caveat: 2",
                "accepted recommendations rely on inference-only grounding: 3",
            ],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 2 still needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The second recommendation still leaves fallback handling implicit.",
                "recommendation_index": 2,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "carried_forward",
                "resolution_note": "not_addressed | Still unresolved.",
                "resolved_in_stage_index": None,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["partial_answer"]["included_recommendation_indices"] == [1, 3]
    assert _first_line(tmp_path / "PARTIAL_ANSWER.md") == "# Partial Answer: task-partial-scope"
    assert "- Review status scope: `included recommendations only`" in markdown
    assert "- Run-level provenance status: `bound`" in markdown
    assert "- Run-level semantic warnings: `1`" in markdown
    assert "accepted recommendations rely on inference-only grounding: 3" in markdown
    assert "TOPIC-001" not in markdown
    assert "accept_with_caveat: 2" not in markdown
    assert "## Topic Lifecycle" not in markdown
    assert "none_reason:" not in markdown


def test_apply_final_artifacts_blocks_partial_answer_when_trust_provenance_is_incomplete(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-blocked"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "summary": "Draft that should not be published as a partial artifact.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Supported recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Also supported.",
                    "evidence": ["b.py"],
                    "proposed_change": "Ship that too.",
                    "confidence": 0.69,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert "partial_answer" not in updated
    assert "partial_answer_json" not in updated["artifacts"]
    assert "partial_answer_md" not in updated["artifacts"]
    assert updated["artifacts"]["final_artifact"] == ""
    assert updated["artifacts"]["final_artifact_kind"] == "none"
    assert "final_artifact_json" not in updated["artifacts"]
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.md").exists()


def test_apply_final_artifacts_blocks_trust_final_answer_and_falls_back_to_partial_answer(
    tmp_path,
):
    summary = {
        "task": {"id": "task-final-blocked-partial"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "summary": "Accepted content that is not publishable as a final answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Clean recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Carries topic debt.",
                    "evidence": ["b.py"],
                    "proposed_change": "Do not ship this one.",
                    "confidence": 0.62,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Third",
                    "rationale": "Still acceptable.",
                    "evidence": ["c.py", "d.py", "e.py", "f.py"],
                    "proposed_change": "Ship with a narrower claim.",
                    "confidence": 0.58,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Carries topic debt.",
            },
            {"recommendation_index": 3, "verdict": "accept", "summary": "Usable."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["review topics are carried forward: TOPIC-001"],
            },
            "accepted_recommendations_with_inferred_grounding": [],
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": [
                "review topics remain open: TOPIC-001",
                "accepted recommendation reviews include accept_with_caveat: 2",
            ],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 2 still needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The second recommendation still leaves fallback handling implicit.",
                "recommendation_index": 2,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "carried_forward",
                "resolution_note": "not_addressed | Still unresolved.",
                "resolved_in_stage_index": None,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("PARTIAL_ANSWER.md")
    assert updated["artifacts"]["final_artifact_json"].endswith("PARTIAL_ANSWER.json")
    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert "final_answer_md" not in updated["artifacts"]
    assert "final_answer_json" not in updated["artifacts"]
    assert updated["partial_answer"]["included_recommendation_indices"] == [1, 3]
    assert markdown.index("> Blocking causes:") < markdown.index("## Review Status")
    assert "> - review topics are carried forward: TOPIC-001" in markdown
    assert "- (+1 more)" in markdown
    assert "- f.py" not in markdown


def test_apply_final_artifacts_clears_stale_partial_metadata_and_falls_back_to_best_draft(
    tmp_path,
):
    best_payload = {
        "summary": "Fallback best draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "Safe fallback.",
                "evidence": ["draft.py"],
                "proposed_change": "Publish the fallback draft.",
                "confidence": 0.75,
            }
        ],
    }
    summary = {
        "task": {"id": "task-stale-partial"},
        "verdict": "accepted_partial",
        "artifacts": {
            "run_dir": str(tmp_path),
            "partial_answer_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "partial_answer_md": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "final_artifact_kind": "partial_answer",
        },
        "partial_answer": {
            "summary": "Stale partial answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Stale recommendation",
                }
            ],
            "included_recommendation_indices": [1],
            "excluded_recommendation_indices": [],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "drafts": [_best_draft_record(best_payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert "partial_answer" not in updated
    assert "partial_answer_json" not in updated["artifacts"]
    assert "partial_answer_md" not in updated["artifacts"]
    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert updated["artifacts"]["final_artifact_json"].endswith("BEST_DRAFT.json")
    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert updated["best_draft"]["summary"] == "Fallback best draft."
    assert (tmp_path / "BEST_DRAFT.json").exists()
    assert (tmp_path / "BEST_DRAFT.md").exists()
    assert _first_line(tmp_path / "BEST_DRAFT.md") == "# Best Draft: task-stale-partial"
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.md").exists()


def test_apply_final_artifacts_non_accepted_partial_does_not_render_blocked_publication_note(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-no-blocked-note"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "partial_answer": {
            "summary": "Partial answer remains the right artifact.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Included recommendation",
                    "rationale": "Safe subset.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship the clean subset.",
                    "confidence": 0.66,
                }
            ],
            "included_recommendation_indices": [1],
            "excluded_recommendation_indices": [2],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "reject", "summary": "Excluded."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["content verdict is not fully accepted: accepted_partial"],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 0,
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("PARTIAL_ANSWER.md")
    assert "> This run did not reach a fully accepted verdict." in markdown
    assert "> Blocking causes:" not in markdown
    assert "content verdict is not fully accepted: accepted_partial" not in markdown


def test_apply_final_artifacts_non_accepted_best_draft_does_not_render_blocked_publication_note(
    tmp_path,
):
    best_payload = {
        "summary": "Best draft remains the fallback artifact.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "No clean partial subset exists.",
                "evidence": ["draft.py"],
                "proposed_change": "Keep as best-effort draft.",
                "confidence": 0.61,
            }
        ],
    }
    summary = {
        "task": {"id": "task-best-draft-no-blocked-note"},
        "verdict": "best_effort_exhausted",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "best_effort_exhausted",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [
                    "content verdict is not fully accepted: best_effort_exhausted"
                ],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 0,
            "downgrade_causes": [],
        },
        "drafts": [_best_draft_record(best_payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert "> This run did not reach a fully accepted verdict." in markdown
    assert "> Blocking causes:" not in markdown
    assert "content verdict is not fully accepted: best_effort_exhausted" not in markdown


def test_apply_final_artifacts_blocks_trust_final_answer_and_falls_back_to_best_draft(
    tmp_path,
):
    best_payload = {
        "summary": "Fallback best draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "Safe fallback.",
                "evidence": ["draft.py"],
                "proposed_change": "Publish the fallback draft.",
                "confidence": 0.75,
            }
        ],
    }
    summary = {
        "task": {"id": "task-final-blocked-best-draft"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "summary": "Accepted content that is not publishable as a final answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Supported recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Also supported.",
                    "evidence": ["b.py"],
                    "proposed_change": "Ship that too.",
                    "confidence": 0.69,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["review topics are carried forward: TOPIC-001"],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": ["review topics remain open: TOPIC-001"],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "The final answer still needs a concrete fallback classification policy.",
                "severity": "medium",
                "evidence": "The analysis never states the fallback classification policy.",
                "recommendation_index": None,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "carried_forward",
                "resolution_note": "not_addressed | Still unresolved.",
                "resolved_in_stage_index": None,
            }
        ],
        "drafts": [_best_draft_record(best_payload)],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert updated["artifacts"]["final_artifact_json"].endswith("BEST_DRAFT.json")
    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert "partial_answer_json" not in updated["artifacts"]
    assert "partial_answer_md" not in updated["artifacts"]
    assert "final_answer_json" not in updated["artifacts"]
    assert "final_answer_md" not in updated["artifacts"]
    assert markdown.index("> Blocking causes:") < markdown.index("## Review Status")
    assert "> - review topics are carried forward: TOPIC-001" in markdown


def test_write_artifacts_node_clears_ineligible_partial_artifacts_and_falls_back_to_best_draft(
    tmp_path,
):
    best_payload = {
        "summary": "Fallback best draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "Safe fallback.",
                "evidence": ["draft.py"],
                "proposed_change": "Publish the fallback draft.",
                "confidence": 0.75,
            }
        ],
    }
    summary = {
        "task": {"id": "task-write-node"},
        "verdict": "accepted_partial",
        "artifacts": {
            "run_dir": str(tmp_path),
            "partial_answer_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "partial_answer_md": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "final_artifact_kind": "partial_answer",
        },
        "partial_answer": {
            "summary": "Stale partial answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Stale recommendation",
                }
            ],
            "included_recommendation_indices": [1],
            "excluded_recommendation_indices": [],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "drafts": [_best_draft_record(best_payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }
    state = {
        "thread_id": "thread-123",
        "task_path": "task.md",
        "strategy_path": "strategy.md",
        "summary_payload": summary,
    }

    updated_state = write_artifacts_node(state)
    updated_summary = updated_state["summary_payload"]

    assert "partial_answer" not in updated_summary
    assert "partial_answer_json" not in updated_summary["artifacts"]
    assert "partial_answer_md" not in updated_summary["artifacts"]
    assert updated_summary["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert updated_summary["artifacts"]["final_artifact_json"].endswith("BEST_DRAFT.json")
    assert updated_summary["artifacts"]["final_artifact_kind"] == "best_draft"
    assert updated_state["artifact_index"]["best_draft_md"]["path"].endswith("BEST_DRAFT.md")
    assert "partial_answer_md" not in updated_state["artifact_index"]
    assert (tmp_path / "BEST_DRAFT.md").exists()
    assert _first_line(tmp_path / "BEST_DRAFT.md") == "# Best Draft: task-write-node"
    assert not (tmp_path / "PARTIAL_ANSWER.md").exists()


def test_apply_final_artifacts_prefers_clean_accepted_draft_over_caveated_accepted_draft(
    tmp_path,
):
    clean_payload = {
        "strengths": {
            "items": ["Grounded in workflow files"],
            "none_reason": "This stale schema text should not leak.",
        },
        "summary": "Clean accepted draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clean recommendation",
                "rationale": "Grounded and caveat-free.",
                "evidence": ["clean.py"],
                "proposed_change": "Apply the clean change.",
                "confidence": 0.61,
            }
        ],
    }
    caveated_payload = {
        "summary": "Accepted draft with carried-forward topic debt.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Caveated recommendation",
                "rationale": "Higher grounding but still caveated.",
                "evidence": ["caveated.py"],
                "proposed_change": "Apply the caveated change.",
                "confidence": 0.92,
            }
        ],
    }
    summary = {
        "task": {"id": "task-selection"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "drafts": [
            {
                "draft_id": "draft-clean",
                "review_status": "accepted",
                "review_state": "evaluated",
                "round_index": 0,
                "summary": clean_payload["summary"],
                "issue_counts": {
                    "blocking_medium_or_higher": 0,
                    "medium_or_higher": 0,
                    "accepted_recommendations": 1,
                    "required_validator_failures": 0,
                    "topics": 0,
                    "open_topics": 0,
                },
                "scores": {
                    "grounding_score": 0.62,
                    "actionability_score": 0.80,
                    "scope_compliance_score": 0.90,
                },
                "metadata": {"stage_index": 1, "payload": clean_payload},
            },
            {
                "draft_id": "draft-caveated",
                "review_status": "accepted",
                "review_state": "evaluated",
                "round_index": 1,
                "summary": caveated_payload["summary"],
                "issue_counts": {
                    "blocking_medium_or_higher": 0,
                    "medium_or_higher": 0,
                    "accepted_recommendations": 1,
                    "required_validator_failures": 0,
                    "topics": 1,
                    "open_topics": 1,
                    "carried_forward_topics": 1,
                },
                "scores": {
                    "grounding_score": 0.99,
                    "actionability_score": 0.83,
                    "scope_compliance_score": 0.92,
                },
                "metadata": {"stage_index": 3, "payload": caveated_payload},
            },
        ],
    }

    updated = apply_final_artifacts(summary)

    assert updated["best_draft_id"] == "draft-clean"
    assert updated["selected_draft_id"] == "draft-clean"
    assert updated["final_answer"]["summary"] == "Clean accepted draft."
    assert _first_line(tmp_path / "FINAL_ANSWER.md") == "# Final Answer: task-selection"
    assert "none_reason:" not in (tmp_path / "FINAL_ANSWER.md").read_text(encoding="utf-8")


def test_artifact_label_for_kind_rejects_unknown_values():
    try:
        _artifact_label_for_kind("mystery_artifact")
    except ValueError as exc:
        assert "Unsupported artifact kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown artifact kind")


def test_apply_final_artifacts_best_draft_markdown_omits_none_reason_label(tmp_path):
    summary = {
        "task": {"id": "task-best-draft-sections"},
        "verdict": "revise",
        "artifacts": {"run_dir": str(tmp_path)},
        "drafts": [_best_draft_record(_section_payload_with_redundant_none_reason())],
        "analysis_review_status": {"mode": "bounded"},
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert "none_reason:" not in (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")


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
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "addressed",
                "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
                "resolved_in_stage_index": 4,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-789",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert "## Topic Lifecycle" in markdown
    assert (
        "- `TOPIC-001` `addressed` via `critic`: Recommendation 1 needs a concrete fallback classification. — addressed | Added the fallback classification note to recommendation 1."
        in markdown
    )


def test_render_deliverable_markdown_renders_carried_forward_topic_resolution_note():
    payload = {
        "summary": "Accepted recommendations with a carried-forward review topic.",
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
        "verdict": "accepted_with_warnings",
        "analysis_review_status": {
            "mode": "bounded",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
            },
            "topic_ledger_count": 1,
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["review topics remain open: TOPIC-001"],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "resolution_status": "carried_forward",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_note": "not_addressed | The recommendation improved, but the fallback label is still implicit. | Operators still need a concrete fallback label.",
                "resolved_in_stage_index": None,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-790",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert (
        "- `TOPIC-001` `carried_forward` via `critic`: Recommendation 1 needs a concrete fallback classification. — not_addressed | The recommendation improved, but the fallback label is still implicit. | Operators still need a concrete fallback label."
        in markdown
    )


def test_render_deliverable_markdown_renders_disagreed_topic_rollups():
    payload = {
        "summary": "Accepted recommendations with a disagreed review topic.",
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
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": ["TOPIC-001"],
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "resolution_status": "disagree",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_note": "disagree | The requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label.",
                "resolved_in_stage_index": 4,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-791",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert "- Disagreed topic IDs: `TOPIC-001`" in markdown
    assert (
        "- `TOPIC-001` `disagree` via `critic`: Recommendation 1 needs a concrete fallback classification. — disagree | The requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label."
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
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "addressed",
                "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
                "resolved_in_stage_index": 4,
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
    assert "| Topic ID | Title | Severity | Introduced By | Status | Recommendation | Resolution Note |" in report
    assert (
        "| `TOPIC-001` | Recommendation 1 needs a concrete fallback classification. | `medium` | `critic` | `addressed` | `1` | addressed \\| Added the fallback classification note to recommendation 1. |"
        in report
    )


def test_render_report_renders_disagreed_topic_status_section():
    summary = {
        "verdict": "accepted",
        "task": {"id": "task-790"},
        "verdicts": {
            "content_verdict": "accepted",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "bounded", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "bounded",
            "content_verdict": "accepted",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
                "required": False,
                "stages": [],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": ["TOPIC-001"],
            "topic_ledger_count": 1,
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "disagree",
                "resolution_note": "disagree | The requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label.",
                "resolved_in_stage_index": 4,
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

    assert "- Disagreed topic IDs: `TOPIC-001`" in report
    assert "- Disagreed topics: `1` (`TOPIC-001`)" in report


def test_render_report_renders_review_provenance_section_for_scoped_global_closure():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-provenance"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
                "issue_closure_review_ref_count": 0,
                "topic_closure_review_ref_count": 2,
                "closure_complete_issue_ids": [],
                "closure_complete_topic_ids": ["TOPIC-001"],
                "uncovered_recommendation_indices": [2],
                "uncovered_global_issue_ids": [],
                "uncovered_global_topic_ids": ["TOPIC-002"],
                "closure_proof_by_id": {
                    "TOPIC-001": {
                        "proof_path": "scoped",
                        "classification_status": "carried_forward",
                        "checked_files": [".github/workflows/claude-code-release-watch.yml"],
                        "verified_evidence_refs": [".github/workflows/claude-code-release-watch.yml"],
                        "proof_strength": "review_attested",
                    }
                },
                "stages": [
                    {
                        "surface": "review",
                        "status": "insufficient",
                        "policy_mode": "payload_hash_and_refs",
                        "recommendation_review_ref_count": 4,
                        "issue_closure_review_ref_count": 0,
                        "topic_closure_review_ref_count": 2,
                        "closure_complete_issue_ids": [],
                        "closure_complete_topic_ids": ["TOPIC-001"],
                        "uncovered_recommendation_indices": [2],
                        "uncovered_global_issue_ids": [],
                        "uncovered_global_topic_ids": ["TOPIC-002"],
                        "closure_proof_by_id": {
                            "TOPIC-001": {
                                "proof_path": "scoped",
                                "classification_status": "carried_forward",
                                "checked_files": [".github/workflows/claude-code-release-watch.yml"],
                                "verified_evidence_refs": [".github/workflows/claude-code-release-watch.yml"],
                                "proof_strength": "review_attested",
                            }
                        },
                    }
                ],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "## Review Provenance" in report
    assert "- Topic closure review refs: `2`" in report
    assert "- Closure-complete topic IDs: `TOPIC-001`" in report
    assert "- Uncovered recommendation indices: `2`" in report
    assert "- Uncovered global topic IDs: `TOPIC-002`" in report
    assert "| `TOPIC-001` | `scoped` | `review_attested` | `carried_forward` | .github/workflows/claude-code-release-watch.yml | .github/workflows/claude-code-release-watch.yml |" in report


def test_render_report_renders_review_provenance_section_for_scoped_global_issue_closure():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-provenance-issue"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
                "issue_closure_review_ref_count": 2,
                "topic_closure_review_ref_count": 0,
                "closure_complete_issue_ids": ["AR-001"],
                "closure_complete_topic_ids": [],
                "uncovered_global_issue_ids": [],
                "uncovered_global_topic_ids": ["TOPIC-002"],
                "closure_proof_by_id": {
                    "AR-001": {
                        "proof_path": "scoped",
                        "classification_status": "carried_forward",
                        "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
                        "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
                        "proof_strength": "review_attested",
                    }
                },
                "stages": [
                    {
                        "surface": "review",
                        "status": "insufficient",
                        "policy_mode": "payload_hash_and_refs",
                        "recommendation_review_ref_count": 4,
                        "issue_closure_review_ref_count": 2,
                        "topic_closure_review_ref_count": 0,
                        "closure_complete_issue_ids": ["AR-001"],
                        "closure_complete_topic_ids": [],
                        "uncovered_global_issue_ids": [],
                        "uncovered_global_topic_ids": ["TOPIC-002"],
                        "closure_proof_by_id": {
                            "AR-001": {
                                "proof_path": "scoped",
                                "classification_status": "carried_forward",
                                "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
                                "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
                                "proof_strength": "review_attested",
                            }
                        },
                    }
                ],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "## Review Provenance" in report
    assert "- Issue closure review refs: `2`" in report
    assert "- Closure-complete issue IDs: `AR-001`" in report
    assert "- Uncovered global topic IDs: `TOPIC-002`" in report
    assert "| `AR-001` | `scoped` | `review_attested` | `carried_forward` | .github/workflows/codex-cli-release-watch.yml | .github/workflows/codex-cli-release-watch.yml |" in report


def test_render_report_renders_publishability_and_compact_provenance_previews():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-publishability"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["review topics are carried forward: TOPIC-001"],
            },
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
                "issue_closure_review_ref_count": 0,
                "topic_closure_review_ref_count": 3,
                "closure_complete_issue_ids": [],
                "closure_complete_topic_ids": ["TOPIC-001"],
                "uncovered_recommendation_indices": [],
                "uncovered_global_issue_ids": [],
                "uncovered_global_topic_ids": [],
                "closure_proof_by_id": {
                    "TOPIC-001": {
                        "proof_path": "scoped",
                        "classification_status": "carried_forward",
                        "checked_files": ["a.py", "b.py", "c.py"],
                        "verified_evidence_refs": ["r1", "r2", "r3"],
                        "proof_strength": "review_attested",
                    }
                },
                "stages": [
                    {
                        "surface": "review",
                        "status": "insufficient",
                        "policy_mode": "payload_hash_and_refs",
                        "recommendation_review_ref_count": 4,
                        "issue_closure_review_ref_count": 0,
                        "topic_closure_review_ref_count": 3,
                        "closure_complete_issue_ids": [],
                        "closure_complete_topic_ids": ["TOPIC-001"],
                        "uncovered_recommendation_indices": [],
                        "uncovered_global_issue_ids": [],
                        "uncovered_global_topic_ids": [],
                        "closure_proof_by_id": {
                            "TOPIC-001": {
                                "proof_path": "scoped",
                                "classification_status": "carried_forward",
                                "checked_files": ["a.py", "b.py", "c.py"],
                                "verified_evidence_refs": ["r1", "r2", "r3"],
                                "proof_strength": "review_attested",
                            }
                        },
                    }
                ],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["review topics remain open: TOPIC-001"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "- Final publication: `blocked`" in report
    assert "- Publication blockers: review topics are carried forward: TOPIC-001" in report
    assert "| `TOPIC-001` | `scoped` | `review_attested` | `carried_forward` | a.py, b.py (+1 more) | r1, r2 (+1 more) |" in report
    assert "a.py, b.py, c.py" not in report
    assert "r1, r2, r3" not in report


def test_render_report_renders_non_accepted_verdict_blocker():
    summary = {
        "verdict": "accepted_partial",
        "task": {"id": "task-publishability-non-accepted"},
        "verdicts": {
            "content_verdict": "accepted_partial",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["content verdict is not fully accepted: accepted_partial"],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "- Final publication: `blocked`" in report
    assert (
        "- Publication blockers: content verdict is not fully accepted: accepted_partial" in report
    )


def test_render_report_uses_defensive_publishability_fallback_when_blockers_missing():
    summary = {
        "verdict": "accepted_partial",
        "task": {"id": "task-publishability-fallback"},
        "verdicts": {
            "content_verdict": "accepted_partial",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert (
        "- Publication blockers: not applicable because content verdict is `accepted_partial`"
        in report
    )


def test_render_report_uses_generic_publishability_fallback_for_fully_accepted_runs():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-publishability-generic-fallback"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "- Publication blockers: withheld due to non-publishable run state" in report


def _recommendation_payload(*titles: str) -> dict[str, object]:
    return {
        "summary": "Trusted analysis payload.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": title,
                "rationale": f"{title} rationale.",
                "evidence": [f"{index}.py"],
                "proposed_change": f"Ship {title.lower()}.",
                "confidence": 0.7 + (index * 0.01),
            }
            for index, title in enumerate(titles, start=1)
        ],
    }


def _trust_status(
    *,
    final_indices: list[int],
    partial_only_indices: list[int],
    excluded_indices: list[int],
    reasons_by_index: dict[str, list[str]] | None = None,
    provenance_status: str = "bound",
    final_answer_publishable: bool = True,
) -> dict[str, object]:
    return {
        "mode": "trust",
        "content_verdict": "accepted_with_warnings",
        "semantic_warning_count": 0,
        "publishability": {
            "final_answer_publishable": final_answer_publishable,
            "blocking_causes": [],
        },
        "provenance": {
            "status": provenance_status,
            "policy_mode": "payload_hash_and_refs",
            "required": True,
        },
        "open_topic_ids": [],
        "carried_forward_topic_ids": [],
        "resolved_topic_ids": [],
        "waived_topic_ids": [],
        "disagreed_topic_ids": [],
        "topic_ledger_count": 0,
        "downgrade_causes": [],
        "recommendation_admissibility": {
            "final_answer_recommendation_indices": final_indices,
            "partial_only_recommendation_indices": partial_only_indices,
            "excluded_recommendation_indices": excluded_indices,
            "reasons_by_recommendation_index": reasons_by_index or {},
        },
    }


def test_apply_final_artifacts_emits_final_answer_when_all_accepted_recommendations_are_final_admissible(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    summary = {
        "task": {"id": "task-final-admissible"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v7",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1, 2],
            partial_only_indices=[],
            excluded_indices=[],
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact_kind"] == "final_answer"
    assert (tmp_path / "FINAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert not (tmp_path / "BEST_DRAFT.json").exists()


def test_apply_final_artifacts_emits_partial_answer_from_surviving_admissible_subset(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second", "Third")
    summary = {
        "task": {"id": "task-partial-admissible"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v7",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[3],
            reasons_by_index={
                "2": ["accepted_with_caveat"],
                "3": ["topic_blocked"],
            },
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    partial_json = json.loads((tmp_path / "PARTIAL_ANSWER.json").read_text(encoding="utf-8"))
    partial_markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    summary_json = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert partial_json["included_recommendation_indices"] == [1, 2]
    assert partial_json["excluded_recommendation_indices"] == [3]
    assert partial_json["excluded_recommendation_reasons_by_index"] == {
        "3": ["topic_blocked"]
    }
    assert "- Included recommendation indices: `1`, `2`" in partial_markdown
    assert "- Final-answer admissible indices: `1`" in partial_markdown
    assert "- Partial-only admissible indices: `2`" in partial_markdown
    assert "  - `3`: `topic_blocked`" in partial_markdown
    assert (
        summary_json["analysis_review_status"]["recommendation_admissibility"][
            "reasons_by_recommendation_index"
        ]["3"]
        == ["topic_blocked"]
    )
    assert "- Excluded recommendation indices: `3`" in report_markdown
    assert "  - `3`: `topic_blocked`" in report_markdown


def test_apply_final_artifacts_falls_back_to_best_draft_when_global_topic_blocker_prevents_partial_publication(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    summary = {
        "task": {"id": "task-global-blocker"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v7",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[],
            reasons_by_index={"2": ["accepted_with_caveat"]},
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [
            {
                "topic_id": "TOPIC-GLOBAL",
                "resolution_status": "carried_forward",
                "recommendation_index": None,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert (tmp_path / "BEST_DRAFT.json").exists()


def test_apply_final_artifacts_falls_back_to_best_draft_when_partial_subset_drops_below_minimum(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    summary = {
        "task": {"id": "task-minimum-partial"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v7",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[],
            reasons_by_index={"2": ["accepted_with_caveat"]},
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [
            {
                "topic_id": "TOPIC-002",
                "resolution_status": "carried_forward",
                "recommendation_index": 2,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert (tmp_path / "BEST_DRAFT.json").exists()


def test_apply_final_artifacts_never_emits_final_answer_when_source_payload_omits_accepted_recommendations(
    tmp_path,
):
    incomplete_final_answer = _recommendation_payload("First")
    complete_best_draft = _recommendation_payload("First", "Second")
    incomplete_final_answer["included_recommendation_indices"] = [1]
    summary = {
        "task": {"id": "task-no-silent-omission"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v7",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1, 2],
            partial_only_indices=[],
            excluded_indices=[],
        ),
        "final_answer": incomplete_final_answer,
        "drafts": [_best_draft_record(complete_best_draft)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert not (tmp_path / "FINAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert (tmp_path / "BEST_DRAFT.json").exists()


def test_build_partial_answer_payload_preserves_original_indices_and_canonical_exclusion_reasons():
    payload = _recommendation_payload("First", "Second", "Third")
    summary = {
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v7",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[3],
            excluded_indices=[2],
            reasons_by_index={
                "2": ["not_accepted"],
                "3": ["inferred_grounding"],
            },
        ),
        "topic_ledger": [],
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 3, "verdict": "accept", "summary": "Inference-backed."},
        ],
    }

    partial_payload = build_partial_answer_payload(summary, payload)

    assert partial_payload is not None
    assert partial_payload["included_recommendation_indices"] == [1, 3]
    assert partial_payload["excluded_recommendation_indices"] == [2]
    assert partial_payload["excluded_recommendation_reasons_by_index"] == {
        "2": ["not_accepted"]
    }
    assert [item["title"] for item in partial_payload["recommendations"]] == [
        "First",
        "Third",
    ]
