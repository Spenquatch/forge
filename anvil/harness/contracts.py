from __future__ import annotations

"""Shared typed contracts for the analysis-review harness surface.

The contract in this module is the single source of truth for analysis-review
stage behavior. Changes here should be reviewed in PRs together with the prompt,
runner, schema, and test updates that enforce the new contract.
"""

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .files import slugify
from .types import (
    DEFAULT_ALLOWED_FOCUS_TYPES,
    ReviewLoopPolicy,
    StrategyConfig,
    TaskSpec,
    normalize_workspace_ref,
)

ConfidenceAssessment = Literal["too_low", "well_calibrated", "too_high", "not_assessed"]
RecommendationVerdict = Literal["accept", "accept_with_caveat", "revise", "reject"]
BlockingClass = Literal["correctness", "actionability", "completeness", "presentation"]
AnalysisReviewMode = Literal["bounded", "trust"]
PayloadProvenanceMode = Literal["none", "payload_hash_and_refs"]
LateAuditorPolicy = Literal["error", "warn"]
GroundingMode = Literal["direct", "mixed", "inferred"]
TrustExecutionMode = Literal["legacy_full_review", "attestation_over_bounded"]
RecommendationAdmissibilityReason = Literal[
    "accepted_with_caveat",
    "inferred_grounding",
    "not_accepted",
    "topic_blocked",
]

BOUNDED_ATTESTATION_INPUT_SCHEMA_VERSION = (
    "analysis_review_bounded_attestation_input_v1"
)


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
TRUST_EXECUTION_MODE_VALUES: tuple[TrustExecutionMode, ...] = (
    "legacy_full_review",
    "attestation_over_bounded",
)
RECOMMENDATION_ADMISSIBILITY_REASON_VALUES: tuple[RecommendationAdmissibilityReason, ...] = (
    "accepted_with_caveat",
    "inferred_grounding",
    "not_accepted",
    "topic_blocked",
)


def canonical_seam_id_for_paths(paths: list[str]) -> str:
    normalized_paths = sorted({str(path).strip() for path in paths if str(path).strip()})
    if not normalized_paths:
        return "seam-empty"

    stem_prefix = slugify("-".join(Path(path).stem for path in normalized_paths))[
        :48
    ].strip("-._")
    digest = hashlib.sha1("\n".join(normalized_paths).encode("utf-8")).hexdigest()[:12]
    if stem_prefix:
        return f"{stem_prefix}-{digest}"
    return f"seam-{digest}"


def canonical_artifact_focus_id(path: str) -> str:
    normalized_path = normalize_workspace_ref(path)
    if not normalized_path:
        return "artifact-empty"
    stem_prefix = slugify(Path(normalized_path).stem).strip("-._")
    digest = hashlib.sha1(normalized_path.encode("utf-8")).hexdigest()[:12]
    if stem_prefix:
        return f"artifact-{stem_prefix}-{digest}"
    return f"artifact-{digest}"


@dataclass
class RecommendationAdmissibilityStatus:
    final_answer_recommendation_indices: list[int] = field(default_factory=list)
    partial_only_recommendation_indices: list[int] = field(default_factory=list)
    excluded_recommendation_indices: list[int] = field(default_factory=list)
    reasons_by_recommendation_index: dict[str, list[RecommendationAdmissibilityReason]] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "final_answer_recommendation_indices": list(
                self.final_answer_recommendation_indices
            ),
            "partial_only_recommendation_indices": list(
                self.partial_only_recommendation_indices
            ),
            "excluded_recommendation_indices": list(self.excluded_recommendation_indices),
            "reasons_by_recommendation_index": {
                str(index): list(reasons)
                for index, reasons in self.reasons_by_recommendation_index.items()
            },
        }


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
    evidence_cap_policy: Literal["trim_to_cap", "strict"] = "trim_to_cap"
    critic_issue_cap: int = 5
    critic_new_topic_cap: int = 2
    auditor_new_medium_or_higher_issue_cap_after_round0: int = 1
    require_scope_escape_justification: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class TrustReviewPolicy:
    max_evidence_refs_per_recommendation: int | None = None
    execution_mode: TrustExecutionMode = "legacy_full_review"
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
class DiscoveryPolicy:
    prioritize_files_hint: bool = True
    require_primary_seam: bool = True
    require_primary_seam_exhaustion_before_expansion: bool = True
    require_nearest_governing_source_for_spec_claims: bool = True
    require_sibling_baseline_for_parity_claims: bool = True
    prefer_nearer_sources_over_plan_prose: bool = True
    allow_secondary_seams_only_with_reason: bool = True
    require_recommendation_seam_binding: bool = True
    max_secondary_seams_considered_bounded: int = 2

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class FocusGatePolicy:
    enabled: bool = False
    default_path: Literal["adjudicate", "deliberate"] = "adjudicate"
    allowed_focus_types: list[Literal["seam", "artifact"]] = field(
        default_factory=lambda: list(DEFAULT_ALLOWED_FOCUS_TYPES)
    )
    clarification_policy: Literal[
        "block_for_clarification", "never_ask"
    ] = "block_for_clarification"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class AnalysisReviewContract:
    contract_version: str
    strategy_kind: str
    mode: AnalysisReviewMode
    stop_policy: ReviewLoopPolicy
    reviser_goal: Literal["close_all_open_blockers"] = "close_all_open_blockers"
    discovery_policy: DiscoveryPolicy = field(default_factory=DiscoveryPolicy)
    partial_acceptance: PartialAcceptancePolicy = field(default_factory=PartialAcceptancePolicy)
    required_sections: RequiredSectionPolicy = field(default_factory=RequiredSectionPolicy)
    bounded_review: BoundedReviewPolicy = field(default_factory=BoundedReviewPolicy)
    trust_review: TrustReviewPolicy = field(default_factory=TrustReviewPolicy)
    focus_gate: FocusGatePolicy = field(default_factory=FocusGatePolicy)
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
            "discovery_policy": self.discovery_policy.to_dict(),
            "partial_acceptance": self.partial_acceptance.to_dict(),
            "required_sections": self.required_sections.to_dict(),
            "bounded_review": self.bounded_review.to_dict(),
            "trust_review": self.trust_review.to_dict(),
            "focus_gate": self.focus_gate.to_dict(),
            "require_issue_ledger": self.require_issue_ledger,
            "require_recommendation_reviews": self.require_recommendation_reviews,
            "confidence_rubric_version": self.confidence_rubric_version,
            "confidence_rubric": list(CONFIDENCE_RUBRIC_LINES),
            "issue_taxonomy_version": self.issue_taxonomy_version,
            "issue_kind_default_blocking_class": dict(ISSUE_KIND_DEFAULT_BLOCKING_CLASS),
        }


def resolve_analysis_review_contract(
    task: TaskSpec,
    strategy: StrategyConfig,
) -> AnalysisReviewContract:
    mode = derive_analysis_review_mode(strategy.kind)
    trust_execution_mode = (
        "legacy_full_review"
        if strategy.trust_review is None
        else strategy.trust_review.execution_mode
    )
    min_accepted_recommendations = max(1, int(task.review_requirements.min_recommendations or 0))
    focus_gate = FocusGatePolicy()
    if strategy.focus_gate is not None:
        if strategy.focus_gate.enabled is not None:
            focus_gate.enabled = strategy.focus_gate.enabled
        if strategy.focus_gate.default_path is not None:
            focus_gate.default_path = strategy.focus_gate.default_path
    if task.focus_gate is not None:
        if task.focus_gate.enabled is not None:
            focus_gate.enabled = task.focus_gate.enabled
        if task.focus_gate.allowed_focus_types is not None:
            focus_gate.allowed_focus_types = list(task.focus_gate.allowed_focus_types)
        if task.focus_gate.clarification_policy is not None:
            focus_gate.clarification_policy = task.focus_gate.clarification_policy
    if task.focus_gate_answer is not None:
        if not focus_gate.enabled:
            raise ValueError(
                "focus_gate_answer requires focus_gate.enabled=true in the resolved analysis-review contract."
            )
        if focus_gate.default_path != "deliberate":
            raise ValueError(
                "focus_gate_answer is only allowed when the resolved focus gate path is deliberate; "
                f"resolved default_path={focus_gate.default_path}."
            )
    return AnalysisReviewContract(
        contract_version="analysis_review_v1_contract_v10",
        strategy_kind=str(strategy.kind),
        mode=mode,
        stop_policy=strategy.review_loops,
        discovery_policy=DiscoveryPolicy(),
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
        bounded_review=BoundedReviewPolicy(
            evidence_cap_policy=task.review_requirements.evidence_cap_policy,
        ),
        trust_review=TrustReviewPolicy(
            max_evidence_refs_per_recommendation=(
                None if mode == "trust" else BoundedReviewPolicy().max_evidence_refs_per_recommendation
            ),
            execution_mode=trust_execution_mode,
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
        focus_gate=focus_gate,
        require_issue_ledger=True,
        require_recommendation_reviews=True,
    )


def build_analysis_review_contract(
    task: TaskSpec,
    strategy: StrategyConfig,
) -> AnalysisReviewContract:
    return resolve_analysis_review_contract(task, strategy)


def derive_analysis_review_mode(strategy_kind: str | None) -> AnalysisReviewMode:
    normalized = str(strategy_kind or "analysis_review_v1").strip().lower()
    return ANALYSIS_REVIEW_MODE_BY_STRATEGY_KIND.get(normalized, "bounded")


def default_blocking_class_for_kind(kind: str | None) -> BlockingClass:
    normalized = str(kind or "other").strip().lower()
    return ISSUE_KIND_DEFAULT_BLOCKING_CLASS.get(normalized, "presentation")


def confidence_rubric_lines() -> tuple[str, ...]:
    return CONFIDENCE_RUBRIC_LINES
