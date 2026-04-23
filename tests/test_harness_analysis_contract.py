from __future__ import annotations

from pathlib import Path

from anvil.harness.contracts import (
    build_analysis_review_contract,
    default_blocking_class_for_kind,
)
from anvil.harness.files import load_structured_file
from anvil.harness.schemas import analysis_review_schema
from anvil.harness.types import ReviewLoopPolicy, StrategyConfig, TaskSpec


def _task(min_recommendations: int = 2, evidence_cap_policy: str = "trim_to_cap") -> TaskSpec:
    return TaskSpec.from_dict(
        {
            "id": "recommend_automation_improvements",
            "task_kind": "analysis_review",
            "objective": "Review the repo and recommend workflow improvements.",
            "workspace_write_policy": {
                "mode": "forbid",
                "allow_untracked": False,
                "allow_renames": False,
                "allow_deletions": False,
                "max_touched_files": 0,
            },
            "acceptance": ["Ground recommendations in repo evidence."],
            "review_requirements": {
                "require_evidence_per_recommendation": True,
                "require_classification": True,
                "require_priority": True,
                "min_recommendations": min_recommendations,
                "evidence_cap_policy": evidence_cap_policy,
            },
        }
    )



def _strategy() -> StrategyConfig:
    return StrategyConfig.from_dict(
        {
            "name": "analysis-review-codex-claude",
            "kind": "analysis_review_bounded_v1",
            "roles": {
                "proposer": {"provider": "codex_cli", "effort": "medium", "access": "read"},
                "critic": {"provider": "claude_code", "effort": "high", "access": "read"},
                "reviser": {"provider": "codex_cli", "effort": "high", "access": "read"},
                "auditor": {"provider": "claude_code", "effort": "high", "access": "read"},
            },
            "review_loops": {
                "min_loops": 1,
                "max_loops": 3,
                "always_run_first_revision": True,
                "stop_when": {
                    "max_open_medium_issues": 0,
                    "min_grounding_score": 0.8,
                    "min_actionability_score": 0.75,
                    "min_scope_compliance_score": 0.85,
                },
            },
            "validators": [],
        }
    )



def test_build_analysis_review_contract_uses_task_and_strategy_requirements():
    contract = build_analysis_review_contract(_task(min_recommendations=3), _strategy())
    serialized = contract.to_dict()

    assert contract.contract_version == "analysis_review_v1_contract_v7"
    assert contract.mode == "bounded"
    assert contract.reviser_goal == "close_all_open_blockers"
    assert contract.stop_policy.max_loops == 3
    assert contract.stop_policy.min_grounding_score == 0.8
    assert contract.partial_acceptance.enabled is True
    assert contract.partial_acceptance.min_accepted_recommendations == 3
    assert contract.partial_acceptance.forbid_correctness_blockers_on_accepted_recommendations is True
    assert contract.require_issue_ledger is True
    assert contract.require_recommendation_reviews is True
    assert contract.required_sections.strengths_required is True
    assert contract.required_sections.uncertainties_required is True
    assert contract.required_sections.min_items_when_populated == 1
    assert contract.required_sections.minimum_files_reviewed == 1
    assert contract.bounded_review.max_evidence_refs_per_recommendation == 3
    assert contract.bounded_review.max_must_check_files_per_recommendation == 3
    assert contract.bounded_review.max_optional_check_files_per_recommendation == 2
    assert contract.bounded_review.evidence_cap_policy == "trim_to_cap"
    assert contract.bounded_review.critic_issue_cap == 5
    assert contract.bounded_review.critic_new_topic_cap == 2
    assert contract.bounded_review.auditor_new_medium_or_higher_issue_cap_after_round0 == 1
    assert contract.bounded_review.require_scope_escape_justification is True
    assert contract.trust_review.require_taxonomy_override_reason is False
    assert contract.trust_review.max_evidence_refs_per_recommendation == 3
    assert contract.trust_review.require_verified_evidence_refs_subset is False
    assert contract.trust_review.require_affected_file_coverage is False
    assert contract.trust_review.payload_provenance_mode == "none"
    assert contract.trust_review.downgrade_on_semantic_warnings is False
    assert contract.trust_review.downgrade_on_inferred_acceptance is False
    assert contract.trust_review.late_auditor_medium_or_higher_policy == "error"
    assert serialized["effective_strategy"] == {
        "kind": "analysis_review_bounded_v1",
        "mode": "bounded",
    }
    assert serialized["bounded_review"] == {
        "max_evidence_refs_per_recommendation": 3,
        "max_must_check_files_per_recommendation": 3,
        "max_optional_check_files_per_recommendation": 2,
        "evidence_cap_policy": "trim_to_cap",
        "critic_issue_cap": 5,
        "critic_new_topic_cap": 2,
        "auditor_new_medium_or_higher_issue_cap_after_round0": 1,
        "require_scope_escape_justification": True,
    }
    assert serialized["trust_review"] == {
        "max_evidence_refs_per_recommendation": 3,
        "require_taxonomy_override_reason": False,
        "require_verified_evidence_refs_subset": False,
        "require_affected_file_coverage": False,
        "payload_provenance_mode": "none",
        "downgrade_on_semantic_warnings": False,
        "downgrade_on_inferred_acceptance": False,
        "late_auditor_medium_or_higher_policy": "error",
    }


def test_analysis_review_contract_serializes_bounded_trust_and_legacy_alias_modes():
    task = _task(min_recommendations=2)

    legacy = build_analysis_review_contract(
        task,
        StrategyConfig.from_dict({**_strategy().to_dict(), "kind": "analysis_review_v1"}),
    )
    trust = build_analysis_review_contract(
        task,
        StrategyConfig.from_dict({**_strategy().to_dict(), "kind": "analysis_review_trust_v1"}),
    )

    assert legacy.mode == "bounded"
    assert legacy.strategy_kind == "analysis_review_v1"
    assert legacy.to_dict()["effective_strategy"] == {
        "kind": "analysis_review_v1",
        "mode": "bounded",
    }

    assert trust.mode == "trust"
    assert trust.strategy_kind == "analysis_review_trust_v1"
    assert trust.trust_review.require_taxonomy_override_reason is True
    assert trust.trust_review.max_evidence_refs_per_recommendation is None
    assert trust.trust_review.require_verified_evidence_refs_subset is True
    assert trust.trust_review.require_affected_file_coverage is True
    assert trust.trust_review.payload_provenance_mode == "payload_hash_and_refs"
    assert trust.trust_review.downgrade_on_semantic_warnings is True
    assert trust.trust_review.downgrade_on_inferred_acceptance is True
    assert trust.trust_review.late_auditor_medium_or_higher_policy == "warn"
    assert trust.to_dict()["trust_review"]["max_evidence_refs_per_recommendation"] is None
    assert trust.to_dict()["effective_strategy"] == {
        "kind": "analysis_review_trust_v1",
        "mode": "trust",
    }


def test_task_review_requirements_default_and_explicit_evidence_cap_policy():
    default_task = TaskSpec.from_dict(
        {
            "id": "recommend_automation_improvements",
            "task_kind": "analysis_review",
            "objective": "Review the repo and recommend workflow improvements.",
            "workspace_write_policy": {"mode": "forbid"},
        }
    )
    strict_task = _task(evidence_cap_policy="strict")

    assert default_task.review_requirements.evidence_cap_policy == "trim_to_cap"
    assert strict_task.review_requirements.evidence_cap_policy == "strict"


def test_analysis_review_schema_requires_files_reviewed_and_closure_review_arrays():
    schema = analysis_review_schema()

    assert "files_reviewed" in schema["required"]
    assert "issue_closure_reviews" in schema["required"]
    assert "topic_closure_reviews" in schema["required"]
    assert schema["properties"]["issue_closure_reviews"]["items"]["required"] == [
        "issue_id",
        "checked_files",
        "verified_evidence_refs",
        "summary",
    ]
    assert schema["properties"]["topic_closure_reviews"]["items"]["required"] == [
        "topic_id",
        "checked_files",
        "verified_evidence_refs",
        "summary",
    ]


def test_default_blocking_class_for_kind_matches_analysis_issue_taxonomy():
    assert default_blocking_class_for_kind("confidence_calibration") == "presentation"
    assert default_blocking_class_for_kind("insufficient_specificity") == "actionability"
    assert default_blocking_class_for_kind("factual_error") == "correctness"
    assert default_blocking_class_for_kind("missing_priority") == "completeness"
    assert default_blocking_class_for_kind("unknown-kind") == "presentation"



def test_analysis_review_defaults_and_example_strategy_are_tuned_for_priority2():
    assert ReviewLoopPolicy.defaults_for_strategy_kind("analysis_review_v1").max_loops == 3
    assert ReviewLoopPolicy.defaults_for_strategy_kind("analysis_review_bounded_v1").max_loops == 3
    assert ReviewLoopPolicy.defaults_for_strategy_kind("analysis_review_trust_v1").max_loops == 3

    bounded_example = load_structured_file(
        Path("examples/harness/strategies/analysis_review_bounded_codex_claude.yaml")
    )
    trust_example = load_structured_file(
        Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml")
    )
    assert bounded_example["kind"] == "analysis_review_bounded_v1"
    assert bounded_example["roles"]["proposer"]["effort"] == "medium"
    assert bounded_example["review_loops"]["max_loops"] == 3
    assert trust_example["kind"] == "analysis_review_trust_v1"
    assert trust_example["roles"]["auditor"]["provider"] == "claude_code_sonnet"
    assert trust_example["review_loops"]["max_loops"] == 3


def test_readme_documents_trust_recommendation_admissibility_and_preview_only_markdown():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "analysis_review_status.recommendation_admissibility" in readme
    assert "FINAL_ANSWER.*` is all-or-nothing" in readme
    assert "final_answer_recommendation_indices" in readme
    assert "partial_only_recommendation_indices" in readme
    assert "excluded_recommendation_indices" in readme
    assert "reasons_by_recommendation_index" in readme
    assert "`accepted_with_caveat`, `inferred_grounding`, `not_accepted`, and `topic_blocked`" in readme
    assert "accepted-but-inferred recommendations are not final-admissible in trust mode" in readme
    assert "candidate subset comes from the final-admissible plus partial-only recommendations" in readme
    assert "analysis_review_status.publishability" in readme
    assert "final_answer_publishable" in readme
    assert "blocking_causes" in readme
    assert "final_artifact`, `final_artifact_json`, `final_artifact_kind`" in readme
    assert "Markdown compaction is preview-only and renderer-owned." in readme


def test_analysis_review_contract_docs_freeze_v7_admissibility_publishability_and_preview_budgets():
    contract_doc = Path("docs/analysis_review_contract.md").read_text(encoding="utf-8")

    assert "analysis_review_v1_contract_v7" in contract_doc
    assert "recommendation admissibility layer" in contract_doc
    assert "recommendation_admissibility" in contract_doc
    assert "runner-owned status, not a model-authored payload field" in contract_doc
    assert "payload shape remains unchanged" in contract_doc
    assert "FINAL_ANSWER.*` is all-or-nothing" in contract_doc
    assert "final_answer_recommendation_indices" in contract_doc
    assert "partial_only_recommendation_indices" in contract_doc
    assert "excluded_recommendation_indices" in contract_doc
    assert "reasons_by_recommendation_index" in contract_doc
    assert "`accept_with_caveat` and accepted recommendations with `grounding_mode = inferred` move to `partial_only_recommendation_indices`" in contract_doc
    assert "`accepted_with_caveat`, `inferred_grounding`, `not_accepted`, and `topic_blocked`" in contract_doc
    assert "candidate partial subset comes from `final_answer_recommendation_indices + partial_only_recommendation_indices`" in contract_doc
    assert "Global topic blockers, provenance gating, and minimum-threshold fallout remain whole-artifact promotion rules." in contract_doc
    assert "final_answer_publishable" in contract_doc
    assert "blocking_causes" in contract_doc
    assert "accepted_with_warnings` does not guarantee `FINAL_ANSWER.*`" in contract_doc
    assert "content verdict is not fully accepted: <verdict>" in contract_doc
    assert "For fully accepted trust runs, `blocking_causes` is deterministic." in contract_doc
    assert "1. provenance blocker first, when present" in contract_doc
    assert "2. open topic IDs in sorted order" in contract_doc
    assert "3. carried-forward topic IDs in sorted order" in contract_doc
    assert "4. one semantic-warning blocker" in contract_doc
    assert "deliverable markdown previews at most the first `3` recommendation evidence refs" in contract_doc
    assert "`REPORT.md` previews at most the first `2` `checked_files` values" in contract_doc


def test_surface_update_notes_document_primary_deliverable_artifacts():
    notes = Path("FORGE_HARNESS_SURFACE_UPDATE_NOTES.md").read_text(encoding="utf-8")

    assert "Primary deliverable artifacts for harness runs" in notes
    assert "FINAL_ANSWER.json` / `FINAL_ANSWER.md` only when the selected primary deliverable is a publishable final answer" in notes
    assert "PARTIAL_ANSWER.json` / `PARTIAL_ANSWER.md` for eligible accepted-partial outputs" in notes
    assert "BEST_DRAFT.json` / `BEST_DRAFT.md` when no shippable final or partial artifact is allowed" in notes


def test_draft_adr_0024_documents_slice_c_artifact_contract_without_old_two_state_wording():
    adr = Path(
        "docs/project_management/adrs/draft/ADR-0024-harness-state-and-artifact-contract.md"
    ).read_text(encoding="utf-8")

    assert "PARTIAL_ANSWER.md" in adr
    assert "PARTIAL_ANSWER.json" in adr
    assert "publishability" in adr
    assert "accepted_with_warnings" in adr
    assert "does not guarantee `FINAL_ANSWER.*`" in adr
    assert "falls through to `PARTIAL_ANSWER.*` when eligible, otherwise `BEST_DRAFT.*`" in adr
    assert 'summary.json["artifacts"]["final_artifact"]' in adr
    assert "Accepted / accepted_with_warnings runs" not in adr
    assert "### Non-accepted runs" not in adr


def test_draft_adr_0025_documents_slice_c_artifact_fallback_without_old_two_state_wording():
    adr = Path(
        "docs/project_management/adrs/draft/ADR-0025-harness-strategy-subgraphs-and-migration-plan.md"
    ).read_text(encoding="utf-8")

    assert "PARTIAL_ANSWER.*" in adr
    assert "publishable final answer" in adr
    assert "trust final publication is blocked" in adr
    assert "fall through partial-answer eligibility before writing `BEST_DRAFT.*`" in adr
    assert "falls through to `PARTIAL_ANSWER.*` when eligible, otherwise `BEST_DRAFT.*`" in adr
    assert "write `FINAL_ANSWER.*` only for accepted runs" not in adr
    assert "otherwise write `BEST_DRAFT.*`" not in adr
    assert "Non-accepted runs produce `BEST_DRAFT.*` artifacts" not in adr
