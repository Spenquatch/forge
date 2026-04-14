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
                "proposer": {"provider": "codex_cli", "effort": "low", "access": "read"},
                "critic": {"provider": "claude_code", "effort": "high", "access": "read"},
                "reviser": {"provider": "codex_cli", "effort": "high", "access": "read"},
                "auditor": {"provider": "claude_code", "effort": "high", "access": "read"},
            },
            "review_loops": {
                "min_loops": 1,
                "max_loops": 2,
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

    assert "Analysis-review contract: analysis_review_v1_contract_v1" in proposer
    assert "Minimum accepted recommendations for partial acceptance: 2" in critic
    assert "Create stable issue IDs such as AR-001" in critic
    assert "You are not starting from scratch" in auditor
    assert "Open issue ledger entering this audit" in auditor
    assert "close all open medium-or-higher blockers" in reviser
    assert "Return an `issue_resolution_map` entry for every open issue ID" in reviser

    for rubric_line in confidence_rubric_lines():
        assert rubric_line in proposer
        assert rubric_line in critic
        assert rubric_line in auditor
        assert rubric_line in reviser
