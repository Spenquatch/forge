from __future__ import annotations

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



def _strategy() -> StrategyConfig:
    return StrategyConfig.from_dict(
        {
            "name": "analysis-review-codex-claude",
            "kind": "analysis_review_v1",
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



def test_analysis_prompts_share_contract_and_confidence_rubric_text():
    task = _task()
    strategy = _strategy()
    contract = build_analysis_review_contract(task, strategy)

    proposer = build_analysis_proposer_prompt(task, strategy.prompt_preamble, _GIT_SNAPSHOT, contract)
    critic = build_analysis_critic_prompt(
        task,
        strategy.prompt_preamble,
        prior_output={"status": "done"},
        validation_runs=[],
        git_snapshot=_GIT_SNAPSHOT,
        review_policy=strategy.review_loops,
        contract=contract,
    )
    auditor = build_analysis_auditor_prompt(
        task,
        strategy.prompt_preamble,
        prior_output={"status": "revised"},
        reviser_output={"issue_resolution_map": []},
        validation_runs=[],
        git_snapshot=_GIT_SNAPSHOT,
        review_policy=strategy.review_loops,
        contract=contract,
        issue_ledger=[{"issue_id": "AR-001", "title": "Example issue", "resolution_status": "open"}],
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
    )

    common_bounded_lines = [
        "Analysis-review contract: analysis_review_v1_contract_v3",
        "Bounded review policy:",
        "Recommendation evidence refs: 1..3 per recommendation",
        "review_surface.must_check_files: 1..3 per recommendation",
        "review_surface.optional_check_files: 0..2 per recommendation",
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

    assert "Minimum accepted recommendations for partial acceptance: 2" in critic
    assert "Create stable issue IDs such as AR-001" in critic
    assert "Validate each recommendation's cited evidence first" in critic
    assert "Record `scope_escapes` whenever you inspect files outside the declared review_surface" in critic
    assert "You are not starting from scratch" in auditor
    assert "Open issue ledger entering this audit" in auditor
    assert "If you introduce any new medium-or-higher issue after round 0, include `why_not_raised_earlier`." in auditor
    assert "close all open medium-or-higher blockers" in reviser
    assert "Return an `issue_resolution_map` entry for every open issue ID" in reviser
    assert "Populate strengths and uncertainties as objects with `items` and `none_reason`" in proposer
    assert "Keep each recommendation bounded: include review_surface.must_check_files, optional_check_files, and a scope_note." in proposer
    assert "Update strengths and uncertainties using the same `items` plus `none_reason` section shape" in reviser
    assert "Preserve each recommendation's bounded evidence list and review_surface unless an open issue requires changing them." in reviser
    assert "Minimum items when a section is populated: 1" in proposer
    assert "Minimum files_reviewed entries: 1" in proposer

    for rubric_line in confidence_rubric_lines():
        assert rubric_line in proposer
        assert rubric_line in critic
        assert rubric_line in auditor
        assert rubric_line in reviser
