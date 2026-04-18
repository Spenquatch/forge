from __future__ import annotations

"""Shared typed contracts for the analysis-review harness surface.

The contract in this module is the single source of truth for analysis-review
stage behavior. Changes here should be reviewed in PRs together with the prompt,
runner, schema, and test updates that enforce the new contract.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal

from .types import ReviewLoopPolicy, StrategyConfig, TaskSpec

ConfidenceAssessment = Literal["too_low", "well_calibrated", "too_high", "not_assessed"]
RecommendationVerdict = Literal["accept", "accept_with_caveat", "revise", "reject"]
BlockingClass = Literal["correctness", "actionability", "completeness", "presentation"]
AnalysisReviewMode = Literal["bounded", "trust"]
PayloadProvenanceMode = Literal["none", "payload_hash_and_refs"]
LateAuditorPolicy = Literal["error", "warn"]
GroundingMode = Literal["direct", "mixed", "inferred"]


CONFIDENCE_RUBRIC_LINES: tuple[str, ...] = (
    "0.85-1.00: direct code-level observation or explicit file-to-file comparison in the current workspace",
    "0.65-0.84: strong inference from repo structure, workflow semantics, or repeated supporting evidence",
    "0.40-0.64: plausible but partially inferred behavior that is not directly proven by the workspace",
    "0.00-0.39: speculative, runtime-dependent, or otherwise weakly supported claim",
)


ISSUE_KIND_DEFAULT_BLOCKING_CLASS: dict[str, BlockingClass] = {
    "factual_error": "correctness",
    "overclaim": "correctness",
    "missing_evidence": "correctness",
    "missing_priority": "completeness",
    "missing_classification": "completeness",
    "missed_issue": "completeness",
    "scope_drift": "correctness",
    "confidence_calibration": "presentation",
    "insufficient_specificity": "actionability",
    "missing_section": "completeness",
    "other": "presentation",
}


ANALYSIS_REVIEW_MODE_BY_STRATEGY_KIND: dict[str, AnalysisReviewMode] = {
    "analysis_review_v1": "bounded",
    "analysis_review_bounded_v1": "bounded",
    "analysis_review_trust_v1": "trust",
}

GROUNDING_MODE_VALUES: tuple[GroundingMode, ...] = ("direct", "mixed", "inferred")


@dataclass
class PartialAcceptancePolicy:
    enabled: bool = True
    min_accepted_recommendations: int = 1
    allow_localized_medium_non_correctness_issues: bool = True
    forbid_correctness_blockers_on_accepted_recommendations: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class RequiredSectionPolicy:
    strengths_required: bool = True
    uncertainties_required: bool = True
    none_reason_allowed: bool = True
    min_items_when_populated: int = 1
    minimum_files_reviewed: int = 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class BoundedReviewPolicy:
    max_evidence_refs_per_recommendation: int = 3
    max_must_check_files_per_recommendation: int = 3
    max_optional_check_files_per_recommendation: int = 2
    critic_issue_cap: int = 5
    critic_new_topic_cap: int = 2
    auditor_new_medium_or_higher_issue_cap_after_round0: int = 1
    require_scope_escape_justification: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class TrustReviewPolicy:
    require_taxonomy_override_reason: bool = True
    require_verified_evidence_refs_subset: bool = True
    require_affected_file_coverage: bool = True
    payload_provenance_mode: PayloadProvenanceMode = "payload_hash_and_refs"
    downgrade_on_semantic_warnings: bool = True
    downgrade_on_inferred_acceptance: bool = True
    late_auditor_medium_or_higher_policy: LateAuditorPolicy = "warn"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class AnalysisReviewContract:
    contract_version: str
    strategy_kind: str
    mode: AnalysisReviewMode
    stop_policy: ReviewLoopPolicy
    reviser_goal: Literal["close_all_open_blockers"] = "close_all_open_blockers"
    partial_acceptance: PartialAcceptancePolicy = field(default_factory=PartialAcceptancePolicy)
    required_sections: RequiredSectionPolicy = field(default_factory=RequiredSectionPolicy)
    bounded_review: BoundedReviewPolicy = field(default_factory=BoundedReviewPolicy)
    trust_review: TrustReviewPolicy = field(default_factory=TrustReviewPolicy)
    require_issue_ledger: bool = True
    require_recommendation_reviews: bool = True
    confidence_rubric_version: str = "analysis_review_confidence_v1"
    issue_taxonomy_version: str = "analysis_review_issue_taxonomy_v1"

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "strategy_kind": self.strategy_kind,
            "mode": self.mode,
            "effective_strategy": {
                "kind": self.strategy_kind,
                "mode": self.mode,
            },
            "stop_policy": self.stop_policy.to_dict(),
            "reviser_goal": self.reviser_goal,
            "partial_acceptance": self.partial_acceptance.to_dict(),
            "required_sections": self.required_sections.to_dict(),
            "bounded_review": self.bounded_review.to_dict(),
            "trust_review": self.trust_review.to_dict(),
            "require_issue_ledger": self.require_issue_ledger,
            "require_recommendation_reviews": self.require_recommendation_reviews,
            "confidence_rubric_version": self.confidence_rubric_version,
            "confidence_rubric": list(CONFIDENCE_RUBRIC_LINES),
            "issue_taxonomy_version": self.issue_taxonomy_version,
            "issue_kind_default_blocking_class": dict(ISSUE_KIND_DEFAULT_BLOCKING_CLASS),
        }


def build_analysis_review_contract(
    task: TaskSpec,
    strategy: StrategyConfig,
) -> AnalysisReviewContract:
    mode = derive_analysis_review_mode(strategy.kind)
    min_accepted_recommendations = max(1, int(task.review_requirements.min_recommendations or 0))
    return AnalysisReviewContract(
        contract_version="analysis_review_v1_contract_v4",
        strategy_kind=str(strategy.kind),
        mode=mode,
        stop_policy=strategy.review_loops,
        partial_acceptance=PartialAcceptancePolicy(
            enabled=True,
            min_accepted_recommendations=min_accepted_recommendations,
            allow_localized_medium_non_correctness_issues=True,
            forbid_correctness_blockers_on_accepted_recommendations=True,
        ),
        required_sections=RequiredSectionPolicy(
            strengths_required=(task.task_kind == "analysis_review"),
            uncertainties_required=(task.task_kind == "analysis_review"),
            none_reason_allowed=True,
            min_items_when_populated=1,
            minimum_files_reviewed=1,
        ),
        trust_review=TrustReviewPolicy(
            require_taxonomy_override_reason=(mode == "trust"),
            require_verified_evidence_refs_subset=(mode == "trust"),
            require_affected_file_coverage=(mode == "trust"),
            payload_provenance_mode=(
                "payload_hash_and_refs" if mode == "trust" else "none"
            ),
            downgrade_on_semantic_warnings=(mode == "trust"),
            downgrade_on_inferred_acceptance=(mode == "trust"),
            late_auditor_medium_or_higher_policy=("warn" if mode == "trust" else "error"),
        ),
        require_issue_ledger=True,
        require_recommendation_reviews=True,
    )


def derive_analysis_review_mode(strategy_kind: str | None) -> AnalysisReviewMode:
    normalized = str(strategy_kind or "analysis_review_v1").strip().lower()
    return ANALYSIS_REVIEW_MODE_BY_STRATEGY_KIND.get(normalized, "bounded")


def default_blocking_class_for_kind(kind: str | None) -> BlockingClass:
    normalized = str(kind or "other").strip().lower()
    return ISSUE_KIND_DEFAULT_BLOCKING_CLASS.get(normalized, "presentation")


def confidence_rubric_lines() -> tuple[str, ...]:
    return CONFIDENCE_RUBRIC_LINES
