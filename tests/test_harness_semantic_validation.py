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


def test_reviser_semantic_validation_requires_full_topic_resolution_map_coverage():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_missing_topic_resolution"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        expected_open_topic_ids=["TOPIC-001", "TOPIC-002"],
        require_issue_resolution_map=False,
        require_topic_resolution_map=True,
    )

    assert result.ok is False
    assert "topic_resolution_map is missing open topic IDs: TOPIC-002" in result.errors


def test_reviser_semantic_validation_rejects_unknown_topic_resolution_ids():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["analysis_output_unknown_topic_resolution"]

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        expected_open_topic_ids=["TOPIC-001"],
        require_issue_resolution_map=False,
        require_topic_resolution_map=True,
    )

    assert result.ok is False
    assert "topic_resolution_map references unknown topic IDs: TOPIC-999" in result.errors



def test_review_semantic_validation_requires_recommendation_and_issue_coverage():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_missing_coverage"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=["AR-001"],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "recommendation_reviews is missing recommendation indices: 2" in result.errors
    assert (
        "prior open issue IDs are missing from resolved/carried_forward/waived arrays: AR-001"
        in result.errors
    )


def test_review_semantic_validation_accepts_valid_topic_lifecycle():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_valid_topic_lifecycle"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-001", "TOPIC-002"],
        expected_recommendation_count=2,
    )

    assert result.ok is True
    assert result.errors == []


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
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "issues exceeds the bounded-review cap of 5 item(s) for critic." in result.errors


def test_critic_semantic_validation_rejects_new_topic_cap_overflow():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_too_many_topics"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "topics exceeds the bounded-review cap of 2 item(s) for critic." in result.errors


def test_review_semantic_validation_requires_topic_classification_for_every_open_topic():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_missing_topic_classification"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-001"],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert (
        "prior open topic IDs are missing from resolved_topic_ids/carried_forward_topic_ids/waived_topic_ids: TOPIC-001"
        in result.errors
    )


def test_review_semantic_validation_rejects_unknown_topic_classification_ids():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_unknown_topic_id"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-001"],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert (
        "topic classification arrays reference unknown prior open topic IDs: TOPIC-999"
        in result.errors
    )


def test_review_semantic_validation_rejects_historical_resolved_topic_id_reuse():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_reused_historical_topic_id"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-002"],
        historical_topic_ids=["TOPIC-001", "TOPIC-002"],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert (
        "topics reuses historical topic IDs that are not currently open: TOPIC-001"
        in result.errors
    )


def test_auditor_semantic_validation_requires_why_not_raised_earlier_for_new_medium_issue():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["auditor_payload_missing_why_not_raised_earlier"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
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
        workspace_paths=_workspace_paths(),
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
        workspace_paths=_workspace_paths(),
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
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is True
    assert result.errors == []


def test_trust_analysis_output_semantic_validation_accepts_valid_trust_metadata():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = _fixture()["analysis_output_trust_surface_valid"]

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


def test_trust_analysis_output_semantic_validation_rejects_verified_evidence_not_subset():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = _fixture()["analysis_output_verified_evidence_not_subset"]

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
        "recommendations[1].verified_evidence_refs must be a subset of evidence: .github/workflows/release.yml"
        in result.errors
    )


def test_trust_analysis_output_semantic_validation_rejects_uncovered_affected_files():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = _fixture()["analysis_output_uncovered_affected_files"]

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
        "recommendations[1].affected_files must be covered by evidence or checked_files when grounding_mode is not inferred: .github/workflows/nightly.yml"
        in result.errors
    )


def test_trust_review_semantic_validation_requires_blocking_class_override_reason():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = _fixture()["review_payload_override_reason_missing"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "bound",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
        },
    )

    assert result.ok is False
    assert (
        "issues[1] overrides blocking_class for kind=missing_priority but is missing blocking_class_override_reason."
        in result.errors
    )


def test_trust_review_semantic_validation_accepts_override_reason_and_warns_on_late_auditor_overflow():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = copy.deepcopy(_fixture()["review_payload_override_reason_valid"])
    payload["issues"].extend(
        [
            {
                "issue_id": "AR-002",
                "severity": "medium",
                "kind": "missing_evidence",
                "blocking_class": "correctness",
                "recommendation_index": 2,
                "title": "A first new issue arrived late.",
                "evidence": "The revision introduced an unsupported claim.",
                "repair_hint": "Restore direct evidence for recommendation 2.",
                "blocking_class_override_reason": None,
                "why_not_raised_earlier": "The first evidence gap was introduced by the revision.",
            },
            {
                "issue_id": "AR-003",
                "severity": "medium",
                "kind": "missing_evidence",
                "blocking_class": "correctness",
                "recommendation_index": 2,
                "title": "A second new issue arrived late.",
                "evidence": "The revision introduced a second unsupported claim.",
                "repair_hint": "Restore direct evidence for recommendation 2.",
                "blocking_class_override_reason": None,
                "why_not_raised_earlier": "The second evidence gap was introduced by the revision.",
            },
        ]
    )
    payload["carried_forward_issue_ids"] = ["AR-001"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=["AR-001"],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "bound",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
        },
    )

    assert result.ok is True
    assert result.errors == []
    assert result.warnings == [
        "new medium-or-higher auditor issues exceed the bounded-review cap of 1 after round 0."
    ]


def test_trust_review_semantic_validation_accepts_structured_review_refs_for_topic_classification():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = _fixture()["review_payload_trust_structured_refs_valid"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-001"],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "bound",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 6,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "closure_provenance_satisfied": True,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
    )

    assert result.ok is True
    assert result.errors == []


def test_trust_review_semantic_validation_rejects_zero_ref_topic_classification():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = _fixture()["review_payload_trust_topic_closure_zero_refs"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-001"],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
            "recommendation_review_ref_count": 0,
            "recommendation_review_ref_field_count": 0,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [],
            "uncovered_recommendation_indices": [1, 2],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
    )

    assert result.ok is False
    assert (
        "trust review payload lacks provenance-complete recommendation-level structured review refs for recommendation indices 1, 2. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_global_topic_without_recommendation_level_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = copy.deepcopy(_fixture()["review_payload_trust_topic_closure_zero_refs"])
    payload["topics"] = [
        {
            "topic_id": "TOPIC-002",
            "severity": "medium",
            "title": "A global fallback policy is still missing.",
            "evidence": "The review describes the gap at the run level rather than on a single recommendation.",
            "repair_hint": "Add an explicit global fallback policy or introduce a future topic-scoped ref surface.",
            "recommendation_index": None,
        }
    ]
    payload["carried_forward_topic_ids"] = []

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
            "recommendation_review_ref_count": 0,
            "recommendation_review_ref_field_count": 0,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": ["TOPIC-002"],
        },
    )

    assert result.ok is False
    assert (
        "trust review payload lacks provenance-complete recommendation-level structured review refs for global topic closures TOPIC-002. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_global_topic_when_recommendations_are_covered():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = copy.deepcopy(_fixture()["review_payload_trust_structured_refs_valid"])
    payload["topics"] = [
        {
            "topic_id": "TOPIC-002",
            "severity": "medium",
            "title": "A global fallback policy is still missing.",
            "evidence": "The review still describes a run-level gap rather than a recommendation-local one.",
            "repair_hint": "Add a dedicated global ref surface or avoid claiming global closure.",
            "recommendation_index": None,
        }
    ]
    payload["resolved_topic_ids"] = []

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 6,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": ["TOPIC-002"],
        },
    )

    assert result.ok is False
    assert (
        "trust review payload lacks provenance-complete recommendation-level structured review refs for global topic closures TOPIC-002. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_global_issue_when_recommendations_are_covered():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = copy.deepcopy(_fixture()["review_payload_trust_structured_refs_valid"])
    payload["issues"] = [
        {
            "issue_id": "AR-002",
            "severity": "medium",
            "kind": "missing_evidence",
            "blocking_class": "correctness",
            "recommendation_index": None,
            "title": "A global evidence gap is still open.",
            "evidence": "The review claims a run-wide invariant without a dedicated scoped ref surface.",
            "repair_hint": "Add an issue-scoped ref surface or narrow the claim.",
            "blocking_class_override_reason": None,
            "why_not_raised_earlier": None,
        }
    ]
    payload["resolved_issue_ids"] = []

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 6,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": ["AR-002"],
            "uncovered_global_topic_ids": [],
        },
    )

    assert result.ok is False
    assert (
        "trust review payload lacks provenance-complete recommendation-level structured review refs for global issue closures AR-002. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_requires_per_verdict_structured_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy("analysis_review_trust_v1"))
    payload = copy.deepcopy(_fixture()["review_payload_override_reason_valid"])
    for item in payload["recommendation_reviews"]:
        item.pop("checked_files", None)
        item.pop("verified_evidence_refs", None)

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
            "recommendation_review_ref_count": 0,
            "recommendation_review_ref_field_count": 0,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [],
            "uncovered_recommendation_indices": [1, 2],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
    )

    assert result.ok is False
    assert (
        "recommendation_reviews[1] must include checked_files or verified_evidence_refs for trust-mode verdict provenance."
        in result.errors
    )


def test_review_semantic_validation_requires_review_stage_files_reviewed():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _fixture()["review_payload_missing_files_reviewed"]

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        expected_recommendation_count=2,
    )

    assert result.ok is False
    assert "files_reviewed must contain at least 1 non-empty path(s)." in result.errors
