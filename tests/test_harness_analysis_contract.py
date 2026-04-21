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

    assert contract.contract_version == "analysis_review_v1_contract_v5"
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
    assert trust.trust_review.require_verified_evidence_refs_subset is True
    assert trust.trust_review.require_affected_file_coverage is True
    assert trust.trust_review.payload_provenance_mode == "payload_hash_and_refs"
    assert trust.trust_review.downgrade_on_semantic_warnings is True
    assert trust.trust_review.downgrade_on_inferred_acceptance is True
    assert trust.trust_review.late_auditor_medium_or_higher_policy == "warn"
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
