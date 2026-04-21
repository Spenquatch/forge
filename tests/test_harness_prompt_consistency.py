from __future__ import annotations

import pytest

from anvil.harness.contracts import build_analysis_review_contract, confidence_rubric_lines
from anvil.harness.prompts import (
    build_analysis_auditor_prompt,
    build_analysis_critic_prompt,
    build_analysis_proposer_prompt,
    build_analysis_reviser_prompt,
)
from anvil.harness.types import StrategyConfig, TaskSpec


_GIT_SNAPSHOT = {
    "is_git": False,
    "ignored_rel_paths": [],
}



def _task() -> TaskSpec:
    return TaskSpec.from_dict(
        {
            "id": "recommend_automation_improvements",
            "task_kind": "analysis_review",
            "objective": "Review the CI/CD automation and recommend improvements.",
            "workspace_write_policy": {
                "mode": "forbid",
                "allow_untracked": False,
                "allow_renames": False,
                "allow_deletions": False,
                "max_touched_files": 0,
            },
            "acceptance": ["Ground every recommendation in repo evidence."],
            "review_requirements": {
                "require_evidence_per_recommendation": True,
                "require_classification": True,
                "require_priority": True,
                "min_recommendations": 2,
            },
        }
    )



def _strategy(kind: str = "analysis_review_bounded_v1") -> StrategyConfig:
    return StrategyConfig.from_dict(
        {
            "name": "analysis-review-codex-claude",
            "kind": kind,
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


@pytest.mark.parametrize(
    ("strategy_kind", "mode", "trust_lines", "payload_line", "issue_line", "acceptance_lines"),
    [
        (
            "analysis_review_bounded_v1",
            "bounded",
            [
                "Taxonomy override reason required: False",
                "verified_evidence_refs must be a subset of evidence refs: False",
                "Non-inferred affected_files require evidence or checked-file coverage: False",
                "Payload provenance mode: none",
                "Downgrade clean acceptance when semantic warnings remain: False",
                "Downgrade inference-backed acceptance to caveated acceptance: False",
                "Late auditor medium-or-higher issue policy: error",
            ],
            "verified_evidence_refs is optional advisory metadata in this mode; keep it a subset of evidence when you provide it.",
            "blocking_class_override_reason is optional context when you intentionally override the default blocking_class.",
            [
                "In this mode, clean accept is allowed without the extra trust downgrade rules.",
                "In this mode, semantic warning handling follows the standard bounded-review flow.",
            ],
        ),
        (
            "analysis_review_trust_v1",
            "trust",
            [
                "Taxonomy override reason required: True",
                "verified_evidence_refs must be a subset of evidence refs: True",
                "Non-inferred affected_files require evidence or checked-file coverage: True",
                "Payload provenance mode: payload_hash_and_refs",
                "Downgrade clean acceptance when semantic warnings remain: True",
                "Downgrade inference-backed acceptance to caveated acceptance: True",
                "Late auditor medium-or-higher issue policy: warn",
            ],
            "In this mode, populate verified_evidence_refs with the evidence refs you directly re-checked; keep it a subset of evidence.",
            "If you intentionally override the default blocking_class for a kind, include blocking_class_override_reason with concrete justification.",
            [
                "In this mode, inference-heavy recommendations should usually receive accept_with_caveat instead of clean accept.",
                "In this mode, unresolved semantic warnings are treated as caveats, not clean acceptance.",
            ],
        ),
    ],
)
def test_analysis_prompts_share_contract_and_confidence_rubric_text(
    strategy_kind: str,
    mode: str,
    trust_lines: list[str],
    payload_line: str,
    issue_line: str,
    acceptance_lines: list[str],
):
    task = _task()
    strategy = _strategy(strategy_kind)
    contract = build_analysis_review_contract(task, strategy)

    proposer = build_analysis_proposer_prompt(task, strategy.prompt_preamble, _GIT_SNAPSHOT, contract)
    prior_analysis = {
        "status": "done",
        "recommendations": [
            {"title": "Add concurrency controls"},
            {"title": "Align timeout handling"},
            {"title": "Document operator rollback"},
        ],
    }
    critic = build_analysis_critic_prompt(
        task,
        strategy.prompt_preamble,
        prior_output=prior_analysis,
        validation_runs=[],
        git_snapshot=_GIT_SNAPSHOT,
        review_policy=strategy.review_loops,
        contract=contract,
    )
    auditor = build_analysis_auditor_prompt(
        task,
        strategy.prompt_preamble,
        prior_output=prior_analysis,
        reviser_output={"issue_resolution_map": []},
        validation_runs=[],
        git_snapshot=_GIT_SNAPSHOT,
        review_policy=strategy.review_loops,
        contract=contract,
        issue_ledger=[{"issue_id": "AR-001", "title": "Example issue", "resolution_status": "open"}],
        topic_ledger=[{"topic_id": "TOPIC-001", "title": "Example topic", "resolution_status": "open"}],
        round_index=1,
    )
    reviser = build_analysis_reviser_prompt(
        task,
        strategy.prompt_preamble,
        prior_output={"status": "done"},
        critic_output={"verdict": "revise"},
        validation_runs=[],
        git_snapshot=_GIT_SNAPSHOT,
        revision_round=1,
        contract=contract,
        open_issues=[{"issue_id": "AR-001", "severity": "medium", "title": "Example issue"}],
        open_topics=[{"topic_id": "TOPIC-001", "severity": "medium", "title": "Example topic"}],
    )

    common_bounded_lines = [
        "Analysis-review contract: analysis_review_v1_contract_v5",
        f"Effective strategy kind: {strategy_kind}",
        f"Mode: {mode}",
        "Bounded review policy:",
        "Recommendation evidence refs: 1..3 per recommendation",
        "review_surface.must_check_files: 1..3 per recommendation",
        "review_surface.optional_check_files: 0..2 per recommendation",
        "Evidence cap policy: trim_to_cap",
        "review_surface.must_check_files must be a subset of files_reviewed",
        "Critic issue cap: 5",
        "Critic new-topic cap: 2",
        "Auditor new medium-or-higher issue cap after round 0: 1",
        "Scope escapes require non-empty reasons: True",
    ]

    for line in common_bounded_lines:
        assert line in proposer
        assert line in critic
        assert line in auditor
        assert line in reviser

    for line in trust_lines:
        assert line in proposer
        assert line in critic
        assert line in auditor
        assert line in reviser

    assert "Minimum accepted recommendations for partial acceptance: 2" in critic
    assert "Create stable issue IDs such as AR-001" in critic
    assert "Validate each recommendation's cited evidence first" in critic
    assert "Record `scope_escapes` whenever you inspect files outside the declared review_surface" in critic
    assert "Recommendation review coverage:" in critic
    assert "Use `topics` only for genuinely new bounded-review topics introduced by this review stage" in critic
    assert (
        "Emit each new topic as a structured record with `topic_id`, `severity`, `title`, `evidence`, `repair_hint`, and `recommendation_index`."
        in critic
    )
    assert (
        "Use `resolved_topic_ids`, `carried_forward_topic_ids`, and `waived_topic_ids` only to classify prior open topics."
        in critic
    )
    assert "Populate `files_reviewed` with the concrete workspace files you inspected during this review stage." in critic
    assert (
        "recommendation_reviews[*].checked_files should name the concrete files you re-checked for that recommendation verdict."
        in critic
    )
    assert (
        "recommendation_reviews[*].verified_evidence_refs should name the concrete evidence refs you directly re-checked for that recommendation verdict."
        in critic
    )
    assert "The prior analysis contains 3 recommendation(s)." in critic
    assert "Do not omit acceptable recommendations." in critic
    assert "1. Add concurrency controls" in critic
    assert "2. Align timeout handling" in critic
    assert "3. Document operator rollback" in critic
    assert "You are not starting from scratch" in auditor
    assert "Open issue ledger entering this audit" in auditor
    assert "Open topic ledger entering this audit" in auditor
    assert "For every previously open topic, you must explicitly classify it as resolved, carried_forward, or waived" in auditor
    assert "Preserve topic IDs for carried-forward or waived prior topics" in auditor
    assert "Populate `files_reviewed` with the concrete workspace files you inspected during this audit stage." in auditor
    assert "If you introduce any new medium-or-higher issue after round 0, include `why_not_raised_earlier`." in auditor
    assert "Recommendation review coverage:" in auditor
    assert "The prior analysis contains 3 recommendation(s)." in auditor
    assert "3. Document operator rollback" in auditor
    assert "close all open medium-or-higher blockers" in reviser
    assert "Return an `issue_resolution_map` entry for every open issue ID" in reviser
    assert "return a `topic_resolution_map` entry for every open topic ID" in reviser
    assert "Use `topic_resolution_map` to classify prior open topics. Do not emit `topics` from the reviser stage." in reviser
    assert "Populate strengths and uncertainties as objects with `items` and `none_reason`" in proposer
    assert (
        "Every evidence ref must be a concrete path-only workspace path you inspected in this run, so every evidence ref must also appear in files_reviewed."
        in proposer
    )
    assert "Do not cite evidence as `path:line-range`" in proposer
    assert "If multiple excerpts come from one file, cite the file once and put line-specific detail in rationale or scope_note." in proposer
    assert "Every recommendation uses the same payload family in both modes." in proposer
    assert "Every recommendation uses the same payload family in both modes." in reviser
    assert (
        "Keep each recommendation bounded: include review_surface.must_check_files, optional_check_files, and a scope_note, and keep evidence within the bounded-review cap."
        in proposer
    )
    assert "keep evidence within the bounded-review cap." in proposer
    assert "Update strengths and uncertainties using the same `items` plus `none_reason` section shape" in reviser
    assert (
        "Preserve each recommendation's bounded evidence list and review_surface unless an open issue or open topic requires changing them."
        in reviser
    )
    assert (
        "Every evidence ref must stay a concrete path-only workspace path you inspected in this run, so every evidence ref must also appear in files_reviewed."
        in reviser
    )
    assert "Do not cite evidence as `path:line-range`" in reviser
    assert "Keep each recommendation's evidence list within the bounded-review cap unless the contract explicitly allows more." in reviser
    assert payload_line in proposer
    assert payload_line in reviser
    assert issue_line in critic

    if mode == "trust":
        assert "In trust mode, do not leave these review-stage refs empty when you introduce or classify issues/topics." in critic
        assert "In trust mode, zero structured review refs is a contract failure even if the payload hash is recorded." in critic
        assert "In trust mode, do not leave these review-stage refs empty when you introduce or classify issues/topics." in auditor
        assert "In trust mode, zero structured review refs is a contract failure even if the payload hash is recorded." in auditor
        assert (
            "In trust mode, populate `recommendation_reviews[*].checked_files` and `recommendation_reviews[*].verified_evidence_refs` whenever you are making concrete recommendation-level review judgments."
            in critic
        )
        assert (
            "In trust mode, populate `recommendation_reviews[*].checked_files` and `recommendation_reviews[*].verified_evidence_refs` whenever you are making concrete recommendation-level review judgments."
            in auditor
        )
    else:
        assert "In bounded mode, these review-stage refs are optional advisory metadata, but populate them when it is cheap and concrete." in critic
        assert "In bounded mode, these review-stage refs are optional advisory metadata, but populate them when it is cheap and concrete." in auditor
    assert issue_line in auditor
    for line in acceptance_lines:
        assert line in critic
        assert line in auditor
    assert "Minimum items when a section is populated: 1" in proposer
    assert "Minimum files_reviewed entries: 1" in proposer

    for rubric_line in confidence_rubric_lines():
        assert rubric_line in proposer
        assert rubric_line in critic
        assert rubric_line in auditor
        assert rubric_line in reviser
