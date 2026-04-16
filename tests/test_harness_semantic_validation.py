from __future__ import annotations

import copy
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


def _workspace_paths() -> set[str]:
    return {
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/release.yml",
        ".github/workflows/nightly.yml",
    }



def test_analysis_output_semantic_validation_accepts_valid_payload():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_valid"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
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
        workspace_paths=_workspace_paths(),
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
        workspace_paths=_workspace_paths(),
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
        role_name="critic",
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


def test_analysis_output_semantic_validation_rejects_too_many_evidence_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_too_many_evidence"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert "recommendations[1].evidence exceeds the bounded-review cap of 3 item(s)." in result.errors


def test_analysis_output_semantic_validation_rejects_evidence_outside_files_reviewed():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = copy.deepcopy(_fixture()["analysis_output_valid"])
    payload["recommendations"][0]["evidence"] = [".github/workflows/release.yml"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].evidence must be a subset of files_reviewed: .github/workflows/release.yml"
        in result.errors
    )


def test_analysis_output_semantic_validation_rejects_evidence_outside_workspace_snapshot():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = copy.deepcopy(_fixture()["analysis_output_valid"])
    payload["recommendations"][0]["evidence"] = ["does/not/exist.py"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].evidence contains path(s) not present in the workspace snapshot: does/not/exist.py"
        in result.errors
    )


def test_analysis_output_semantic_validation_accepts_evidence_present_in_files_reviewed():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = copy.deepcopy(_fixture()["analysis_output_valid"])

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is True
    assert result.errors == []


def test_analysis_output_semantic_validation_rejects_too_many_must_check_files():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_too_many_must_check_files"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].review_surface.must_check_files exceeds the bounded-review cap of 3 item(s)."
        in result.errors
    )


def test_analysis_output_semantic_validation_rejects_too_many_optional_check_files():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_too_many_optional_check_files"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].review_surface.optional_check_files exceeds the bounded-review cap of 2 item(s)."
        in result.errors
    )


def test_analysis_output_semantic_validation_rejects_must_check_files_outside_files_reviewed():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_must_check_not_in_files_reviewed"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].review_surface.must_check_files must be a subset of files_reviewed: "
        ".github/workflows/missing.yml"
    ) in result.errors


def test_analysis_output_semantic_validation_rejects_files_reviewed_outside_workspace_snapshot():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = copy.deepcopy(_fixture()["analysis_output_valid"])
    payload["files_reviewed"].append("does/not/exist.py")

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "files_reviewed contains path(s) not present in the workspace snapshot: does/not/exist.py"
        in result.errors
    )


def test_analysis_output_semantic_validation_rejects_must_check_files_outside_workspace_snapshot():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = copy.deepcopy(_fixture()["analysis_output_valid"])
    payload["files_reviewed"].append("does/not/exist.py")
    payload["recommendations"][0]["review_surface"]["must_check_files"] = ["does/not/exist.py"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].review_surface.must_check_files contains path(s) not present in the workspace snapshot: "
        "does/not/exist.py"
    ) in result.errors


def test_analysis_output_semantic_validation_rejects_optional_check_files_outside_workspace_snapshot():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = copy.deepcopy(_fixture()["analysis_output_valid"])
    payload["recommendations"][0]["review_surface"]["optional_check_files"] = ["does/not/exist.py"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert (
        "recommendations[1].review_surface.optional_check_files contains path(s) not present in the workspace snapshot: "
        "does/not/exist.py"
    ) in result.errors


def test_critic_semantic_validation_rejects_issue_cap_overflow():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_too_many_issues"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "issues exceeds the bounded-review cap of 5 item(s) for critic." in result.errors


def test_critic_semantic_validation_rejects_new_topic_cap_overflow():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_too_many_missing_topics"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "missing_topics exceeds the bounded-review cap of 2 item(s) for critic." in result.errors


def test_auditor_semantic_validation_requires_why_not_raised_earlier_for_new_medium_issue():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["auditor_payload_missing_why_not_raised_earlier"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        prior_open_issue_ids=["AR-001"],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert (
        "issues[1] must include why_not_raised_earlier for new medium-or-higher auditor issues."
        in result.errors
    )


def test_auditor_semantic_validation_accepts_new_medium_issue_with_why_not_raised_earlier():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["auditor_payload_valid_new_issue_with_why_not_raised_earlier"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        prior_open_issue_ids=["AR-001"],
        expected_recommendation_count=2,
    )

    assert result.ok is True
    assert result.errors == []


def test_review_semantic_validation_rejects_empty_scope_escape_reason():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_scope_escape_empty_reason"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert (
        "scope_escapes[1].reason must be non-empty when scope escapes are recorded."
        in result.errors
    )


def test_review_semantic_validation_accepts_scope_escape_with_reason():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_scope_escape_valid"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is True
    assert result.errors == []
