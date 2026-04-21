from __future__ import annotations

from anvil.harness.report import render_report
from anvil.harness.reporting import (
    apply_final_artifacts,
    build_partial_answer_payload,
    render_deliverable_markdown,
)


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


def test_apply_final_artifacts_scopes_partial_answer_review_status_to_included_recommendations(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-scope"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
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
    assert "- Review status scope: `included recommendations only`" in markdown
    assert "- Run-level provenance status: `bound`" in markdown
    assert "- Run-level semantic warnings: `1`" in markdown
    assert "accepted recommendations rely on inference-only grounding: 3" in markdown
    assert "TOPIC-001" not in markdown
    assert "accept_with_caveat: 2" not in markdown
    assert "## Topic Lifecycle" not in markdown


def test_apply_final_artifacts_prefers_clean_accepted_draft_over_caveated_accepted_draft(
    tmp_path,
):
    clean_payload = {
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
    assert "- Uncovered global topic IDs: `TOPIC-002`" in report
    assert "| `TOPIC-001` | `scoped` | `review_attested` | `carried_forward` | .github/workflows/claude-code-release-watch.yml | .github/workflows/claude-code-release-watch.yml |" in report
