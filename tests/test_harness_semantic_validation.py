from __future__ import annotations

import json
from pathlib import Path

from anvil.harness.contracts import build_analysis_review_contract
from anvil.harness.semantic_validation import (
    validate_analysis_output_payload,
    validate_analysis_review_payload,
)
from anvil.harness.types import StrategyConfig, TaskSpec


_FIXTURE_PATH = Path("tests/fixtures/harness/analysis_review_semantic_cases.json")



def _task(min_recommendations: int = 2) -> TaskSpec:
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
            "validators": [],
        }
    )



def _fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))



def test_analysis_output_semantic_validation_accepts_valid_payload():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_valid"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is True
    assert result.errors == []



def test_analysis_output_semantic_validation_rejects_missing_sections_and_files():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_missing_sections"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert "recommendations must contain at least 2 item(s) for this task." in result.errors
    assert "strengths must contain at least one concrete item or a non-empty none_reason." in result.errors
    assert "uncertainties must contain at least one concrete item or a non-empty none_reason." in result.errors
    assert "files_reviewed must contain at least 1 non-empty path(s)." in result.errors



def test_reviser_semantic_validation_requires_full_issue_resolution_map_coverage():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_missing_issue_resolution"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        expected_open_issue_ids=["AR-001", "AR-002"],
        require_issue_resolution_map=True,
    )

    assert result.ok is False
    assert "issue_resolution_map is missing open issue IDs: AR-002" in result.errors



def test_review_semantic_validation_requires_recommendation_and_issue_coverage():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_missing_coverage"]

    result = validate_analysis_review_payload(
        payload,
        task=task,
        contract=contract,
        prior_open_issue_ids=["AR-001"],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "recommendation_reviews is missing recommendation indices: 2" in result.errors
    assert (
        "prior open issue IDs are missing from resolved/carried_forward/waived arrays: AR-001"
        in result.errors
    )
