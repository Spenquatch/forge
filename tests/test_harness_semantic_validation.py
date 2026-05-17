from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from anvil.harness.contracts import (
    build_analysis_review_contract,
    canonical_artifact_focus_id,
    canonical_seam_id_for_paths,
)
from anvil.harness.schemas import focus_gate_output_schema
from anvil.harness.semantic_validation import (
    BOUNDED_ATTESTATION_SCHEMA_VERSION,
    validate_analysis_output_payload,
    validate_analysis_review_payload,
    validate_bounded_attestation_input_payload,
    validate_focus_decision_payload,
    validate_stage_output,
)
from anvil.harness.types import (
    DETERMINISTIC_FEATURE_PLANNING_KIND,
    GENERIC_FOCUS_GATE_QUESTION_PROMPT,
    PLANNING_RUNTIME_TARGET,
    StrategyConfig,
    TaskSpec,
    canonical_workspace_ref_list,
)

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


def _strategy(
    kind: str = "analysis_review_bounded_v1",
    *,
    trust_execution_mode: str | None = None,
) -> StrategyConfig:
    payload = {
        "name": "analysis-review-codex-claude",
        "kind": kind,
        "roles": {
            "proposer": {
                "provider": "codex_cli",
                "effort": "medium",
                "access": "read",
            },
            "critic": {
                "provider": "claude_code",
                "effort": "high",
                "access": "read",
            },
            "reviser": {
                "provider": "codex_cli",
                "effort": "high",
                "access": "read",
            },
            "auditor": {
                "provider": "claude_code",
                "effort": "high",
                "access": "read",
            },
        },
        "validators": [],
    }
    if trust_execution_mode is not None:
        payload["trust_review"] = {"execution_mode": trust_execution_mode}
    return StrategyConfig.from_dict(payload)


def _planning_strategy() -> StrategyConfig:
    return StrategyConfig.from_dict(
        {
            "name": "deterministic-feature-planning",
            "kind": DETERMINISTIC_FEATURE_PLANNING_KIND,
            "runtime_target": PLANNING_RUNTIME_TARGET,
            "roles": {
                "planner": {
                    "provider": "codex_cli",
                    "effort": "high",
                    "access": "read",
                }
            },
            "phases": [
                {"id": "design_doc", "stage_type": "rubric_design_doc"},
                {
                    "id": "seam_decomposition",
                    "stage_type": "architecture_seam_decomposition",
                },
                {
                    "id": "parallel_planning",
                    "stage_type": "parallel_workstream_planning",
                },
                {"id": "slice_emission", "stage_type": "executable_slice_emission"},
            ],
            "artifact_policy": "planning_package_v1",
            "determinism_policy": "stable_structure_v1",
            "discovery_policy": "bounded_repo_scan_v1",
            "rubric_policy": "design_doc_gate_v1",
            "stop_policy": "clarification_or_stop_v1",
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


def _with_default_seams(payload: dict) -> dict:
    normalized = copy.deepcopy(payload)
    files_reviewed = list(normalized.get("files_reviewed") or [])

    primary_path = (
        files_reviewed[0]
        if files_reviewed
        else ".github/workflows/codex-cli-release-watch.yml"
    )
    secondary_path = files_reviewed[1] if len(files_reviewed) > 1 else primary_path
    normalized.setdefault(
        "primary_seam",
        {
            "seam_id": canonical_seam_id_for_paths([primary_path]),
            "summary": "Primary release-watch workflow seam.",
            "why_primary": "It is the nearest governing surface for the review.",
            "paths": [primary_path],
        },
    )
    secondary_seam_id = canonical_seam_id_for_paths([secondary_path])
    normalized.setdefault(
        "secondary_seams_considered",
        [
            {
                "seam_id": secondary_seam_id,
                "summary": "Sibling workflow parity seam.",
                "why_not_primary": "It is relevant for parity but not the governing seam.",
                "paths": [secondary_path],
            }
        ],
    )
    normalized.setdefault("scope_escapes", [])

    recommendations = normalized.get("recommendations") or []
    for index, recommendation in enumerate(recommendations, start=1):
        if not isinstance(recommendation, dict):
            continue
        if "seam_id" in recommendation:
            recommendation.setdefault("seam_expansion_reason", "")
            continue
        if index == 1:
            recommendation["seam_id"] = normalized["primary_seam"]["seam_id"]
            recommendation["seam_expansion_reason"] = ""
        else:
            recommendation["seam_id"] = secondary_seam_id
            recommendation["seam_expansion_reason"] = (
                "Cross-check sibling workflow behavior before broadening the review."
            )
    return normalized


def _analysis_output_payload(name: str) -> dict:
    return _with_default_seams(_fixture()[name])


def _focus_decision_payload(
    decision_state: str = "selected",
    focus_type: str = "seam",
) -> dict:
    release_paths = canonical_workspace_ref_list(
        [
            "./.github/workflows/release.yml",
            ".github/workflows/release.yml",
        ]
    )
    nightly_paths = canonical_workspace_ref_list(
        [
            ".github/workflows/nightly.yml",
            "./.github/workflows/nightly.yml",
        ]
    )
    if focus_type == "artifact":
        release_paths = [release_paths[0]]
        nightly_paths = [nightly_paths[0]]
        release_focus_id = canonical_artifact_focus_id(release_paths[0])
        nightly_focus_id = canonical_artifact_focus_id(nightly_paths[0])
        adaptation_basis = "artifact_singleton"
    else:
        release_focus_id = canonical_seam_id_for_paths(release_paths)
        nightly_focus_id = canonical_seam_id_for_paths(nightly_paths)
        adaptation_basis = "selected_focus_paths"
    payload = {
        "gate_path": "adjudicate",
        "focus_type": focus_type,
        "decision_state": decision_state,
        "decision_basis": "request_only",
        "selected_focus_id": release_focus_id,
        "selected_focus_summary": "Release trigger workflows are the governing seam.",
        "selected_focus_paths": list(release_paths),
        "confidence": 0.86,
        "confidence_band": "high",
        "files_hint_disposition": "absent",
        "checked_files": [],
        "candidates": [
            {
                "focus_id": release_focus_id,
                "focus_summary": "Release trigger workflows",
                "candidate_paths": [
                    "./.github/workflows/release.yml",
                    ".github/workflows/release.yml",
                ],
                "why_candidate": "The release workflow paths are the governing seam.",
                "evidence_refs": [],
                "score": 0.86,
            },
            {
                "focus_id": nightly_focus_id,
                "focus_summary": "Nightly workflow parity",
                "candidate_paths": [
                    ".github/workflows/nightly.yml",
                    "./.github/workflows/nightly.yml",
                ],
                "why_candidate": "The nightly workflow remains a plausible sibling seam.",
                "evidence_refs": [],
                "score": 0.61,
            },
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [],
        "adapter_plan": {
            "primary_focus_id": release_focus_id,
            "secondary_focus_ids": [nightly_focus_id],
            "downstream_primary_seam_id": canonical_seam_id_for_paths(release_paths),
            "downstream_primary_seam_paths": list(release_paths),
            "adaptation_basis": adaptation_basis,
        },
    }
    if decision_state == "clarification_requested":
        payload["gate_path"] = "deliberate"
        payload["decision_basis"] = "repo_probe"
        payload["selected_focus_id"] = None
        payload["selected_focus_summary"] = None
        payload["selected_focus_paths"] = []
        payload["files_hint_disposition"] = "helped"
        payload["checked_files"] = [
            "./.github/workflows/release.yml",
            ".github/workflows/nightly.yml",
        ]
        payload["candidates"][0]["evidence_refs"] = ["./.github/workflows/release.yml"]
        payload["candidates"][1]["evidence_refs"] = [".github/workflows/nightly.yml"]
        payload["question"] = {
            "prompt": GENERIC_FOCUS_GATE_QUESTION_PROMPT,
            "options": [release_focus_id, nightly_focus_id],
        }
        payload["adapter_plan"] = {
            "primary_focus_id": None,
            "secondary_focus_ids": [release_focus_id, nightly_focus_id],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        }
    elif decision_state == "no_viable_focus":
        payload["selected_focus_id"] = None
        payload["selected_focus_summary"] = None
        payload["selected_focus_paths"] = []
        payload["files_hint_disposition"] = "absent"
        payload["checked_files"] = []
        payload["candidates"] = []
        payload["adapter_plan"] = {
            "primary_focus_id": None,
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        }
    return payload


def _sha256_hex(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _bounded_attestation_input_payload() -> dict:
    bounded_analysis = {
        "summary": "Review the workflow seam and keep recommendations bounded.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "high",
                "title": "Align release-watch issue handling",
                "rationale": "The governing workflow should match the parity spec.",
                "evidence": [
                    ".github/workflows/codex-cli-release-watch.yml",
                    ".github/workflows/claude-code-release-watch.yml",
                ],
                "proposed_change": "Align issue handling across the release-watch seam.",
                "confidence": 0.9,
                "review_surface": {
                    "must_check_files": [
                        ".github/workflows/codex-cli-release-watch.yml",
                    ],
                    "optional_check_files": [
                        ".github/workflows/claude-code-release-watch.yml",
                    ],
                    "scope_note": "Stay on the release-watch seam.",
                },
            },
            {
                "classification": "risk",
                "priority": "medium",
                "title": "Document snapshot timeout parity",
                "rationale": "Timeout settings drift between sibling workflows.",
                "evidence": [
                    ".github/workflows/release.yml",
                ],
                "proposed_change": "Document the intended timeout parity.",
                "confidence": 0.72,
                "review_surface": {
                    "must_check_files": [
                        ".github/workflows/release.yml",
                    ],
                    "optional_check_files": [
                        ".github/workflows/nightly.yml",
                    ],
                    "scope_note": "Use the sibling workflow only as a parity check.",
                },
            },
        ],
        "files_reviewed": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/claude-code-release-watch.yml",
            ".github/workflows/release.yml",
            ".github/workflows/nightly.yml",
        ],
        "primary_seam": {
            "seam_id": canonical_seam_id_for_paths(
                [".github/workflows/codex-cli-release-watch.yml"]
            ),
            "summary": "Primary release-watch seam.",
            "why_primary": "It is the governing workflow for the requested review.",
            "paths": [".github/workflows/codex-cli-release-watch.yml"],
        },
        "secondary_seams_considered": [
            {
                "seam_id": canonical_seam_id_for_paths(
                    [".github/workflows/claude-code-release-watch.yml"]
                ),
                "summary": "Sibling release-watch seam.",
                "why_not_primary": "It is corroborating parity context only.",
                "paths": [".github/workflows/claude-code-release-watch.yml"],
            }
        ],
        "scope_escapes": [],
    }
    recommendation_evidence_index = {
        "1": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/claude-code-release-watch.yml",
        ],
        "2": [".github/workflows/release.yml"],
    }
    return {
        "schema_version": BOUNDED_ATTESTATION_SCHEMA_VERSION,
        "source": {
            "strategy_kind": "analysis_review_bounded_v1",
            "mode": "bounded",
            "analysis_stage_role_name": "reviser_round_1",
            "analysis_stage_index": 3,
            "bounded_payload_sha256": _sha256_hex(bounded_analysis),
        },
        "focus_decision": _focus_decision_payload("selected"),
        "contract": {
            "contract_version": "analysis_review_contract_v1",
            "strategy_kind": "analysis_review_bounded_v1",
            "trust_execution_mode": "legacy_full_review",
        },
        "bounded_analysis": bounded_analysis,
        "review_surface": {
            "recommendation_count": 2,
            "recommendations_with_review_surface": 2,
            "review_stages": [
                {
                    "role_name": "critic",
                    "round_index": 0,
                    "scope_escape_count": 0,
                },
                {
                    "role_name": "auditor",
                    "round_index": 1,
                    "scope_escape_count": 0,
                },
            ],
            "scope_escape_count": 0,
        },
        "ledgers": {
            "issue_ledger": [],
            "topic_ledger": [],
        },
        "provenance_context": {
            "normalized_ref_count": 3,
            "recommendation_evidence_index": recommendation_evidence_index,
        },
    }


def _attestation_review_payload() -> dict:
    return {
        "verdict": "accept_partial",
        "summary": "The bounded recommendations remain usable with one caveat.",
        "files_reviewed": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/release.yml",
        ],
        "issues": [],
        "topics": [],
        "resolved_issue_ids": [],
        "carried_forward_issue_ids": [],
        "waived_issue_ids": [],
        "resolved_topic_ids": [],
        "carried_forward_topic_ids": [],
        "waived_topic_ids": [],
        "recommendation_reviews": [
            {
                "recommendation_index": 1,
                "verdict": "accept",
                "open_issue_ids": [],
                "summary": "Recommendation 1 is still directly supported.",
                "checked_files": [
                    ".github/workflows/codex-cli-release-watch.yml"
                ],
                "verified_evidence_refs": [
                    ".github/workflows/codex-cli-release-watch.yml"
                ],
                "confidence_assessment": "well_calibrated",
            },
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "open_issue_ids": [],
                "summary": "Recommendation 2 still holds but needs caveated rollout language.",
                "checked_files": [".github/workflows/release.yml"],
                "verified_evidence_refs": [".github/workflows/release.yml"],
                "confidence_assessment": "well_calibrated",
            },
        ],
        "issue_closure_reviews": [],
        "topic_closure_reviews": [],
        "scope_escapes": [],
        "warnings": [],
    }


def test_planning_task_spec_rejects_workspace_writes():
    with pytest.raises(
        ValueError,
        match="planning tasks must set workspace_write_policy.mode to forbid",
    ):
        TaskSpec.from_dict(
            {
                "id": "plan-release-watch-parity",
                "task_kind": "planning",
                "objective": "Plan release-watch parity work.",
                "workspace_write_policy": {"mode": "allow"},
            }
        )


def test_planning_strategy_config_accepts_canonical_declaration():
    strategy = _planning_strategy()

    assert strategy.kind == DETERMINISTIC_FEATURE_PLANNING_KIND
    assert strategy.runtime_target == PLANNING_RUNTIME_TARGET
    assert [phase.to_dict() for phase in strategy.phases] == [
        {"id": "design_doc", "stage_type": "rubric_design_doc"},
        {
            "id": "seam_decomposition",
            "stage_type": "architecture_seam_decomposition",
        },
        {
            "id": "parallel_planning",
            "stage_type": "parallel_workstream_planning",
        },
        {"id": "slice_emission", "stage_type": "executable_slice_emission"},
    ]
    assert strategy.artifact_policy == "planning_package_v1"
    assert strategy.determinism_policy == "stable_structure_v1"
    assert strategy.discovery_policy == "bounded_repo_scan_v1"
    assert strategy.rubric_policy == "design_doc_gate_v1"
    assert strategy.stop_policy == "clarification_or_stop_v1"


def test_focus_gate_output_schema_exposes_v10_focus_decision_surface():
    schema = focus_gate_output_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["gate_path"]["enum"] == ["adjudicate", "deliberate"]
    assert schema["properties"]["focus_type"]["enum"] == ["seam", "artifact"]
    assert schema["properties"]["decision_state"]["enum"] == [
        "selected",
        "clarification_requested",
        "no_viable_focus",
    ]
    assert "adapter_plan" in schema["required"]
    assert "question" in schema["required"]
    assert "candidates" in schema["required"]
    assert "selected_focus_paths" in schema["required"]
    assert (
        "downstream_primary_seam_id" in schema["properties"]["adapter_plan"]["required"]
    )
    assert (
        "downstream_primary_seam_paths"
        in schema["properties"]["adapter_plan"]["required"]
    )
    assert "adaptation_basis" in schema["properties"]["adapter_plan"]["required"]
    assert "candidate_paths" in schema["properties"]["candidates"]["items"]["required"]


def test_focus_decision_semantic_validation_accepts_selected_payload():
    result = validate_focus_decision_payload(
        _focus_decision_payload("selected"),
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is True
    assert result.errors == []


def test_focus_decision_semantic_validation_rejects_selected_rule_violations():
    payload = _focus_decision_payload("selected")
    payload["selected_focus_id"] = None
    payload["question"] = {
        "prompt": GENERIC_FOCUS_GATE_QUESTION_PROMPT,
        "options": ["mismatched-focus-id"],
    }
    payload["adapter_plan"]["primary_focus_id"] = None

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "selected_focus_id is required when decision_state=selected." in result.errors
    )
    assert (
        "adapter_plan.primary_focus_id must equal selected_focus_id when decision_state=selected."
        in result.errors
    )
    assert (
        "question must serialize as {'prompt': '', 'options': []} when decision_state is not clarification_requested."
        in result.errors
    )


def test_focus_decision_semantic_validation_rejects_clarification_rule_violations():
    payload = _focus_decision_payload("clarification_requested")
    payload["question"] = {"prompt": "", "options": ["unknown-focus"]}
    payload["adapter_plan"]["secondary_focus_ids"] = ["unknown-focus"]

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "question.prompt is required when decision_state=clarification_requested."
        in result.errors
    )
    assert (
        "adapter_plan.secondary_focus_ids must be a subset of candidates: unknown-focus"
        in result.errors
    )
    assert (
        "question.options must equal candidate focus IDs in order when decision_state=clarification_requested."
        in result.errors
    )


def test_focus_decision_semantic_validation_accepts_artifact_selected_payload():
    result = validate_focus_decision_payload(
        _focus_decision_payload("selected", focus_type="artifact"),
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is True
    assert result.errors == []


def test_focus_decision_semantic_validation_rejects_artifact_bridge_rule_violations():
    payload = _focus_decision_payload("selected", focus_type="artifact")
    payload["selected_focus_paths"] = [
        ".github/workflows/release.yml",
        ".github/workflows/nightly.yml",
    ]
    payload["adapter_plan"]["downstream_primary_seam_id"] = payload["selected_focus_id"]
    payload["adapter_plan"]["adaptation_basis"] = "selected_focus_paths"

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "selected_focus_paths must contain exactly one normalized path when focus_type=artifact and decision_state=selected."
        in result.errors
    )
    assert (
        "adapter_plan.downstream_primary_seam_id must equal the canonical seam ID derived from selected_focus_paths when focus_type=artifact and decision_state=selected."
        in result.errors
    )
    assert (
        "adapter_plan.adaptation_basis must equal 'artifact_singleton' when focus_type=artifact and decision_state=selected."
        in result.errors
    )


def test_focus_decision_semantic_validation_rejects_noncanonical_clarification_prompt():
    payload = _focus_decision_payload("clarification_requested", focus_type="artifact")
    payload["question"]["prompt"] = "Which seam should this run prioritize?"

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "question.prompt must equal the canonical focus-gate clarification prompt when decision_state=clarification_requested."
        in result.errors
    )


def test_focus_decision_semantic_validation_accepts_no_viable_focus_with_empty_candidates():
    result = validate_focus_decision_payload(
        _focus_decision_payload("no_viable_focus"),
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is True
    assert result.errors == []


def test_validate_stage_output_supports_focus_gate_role():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())

    result = validate_stage_output(
        role_name="focus_gate",
        payload=_focus_decision_payload("selected"),
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is True
    assert result.errors == []


def test_focus_decision_semantic_validation_rejects_expected_gate_path_mismatch():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task,
        _strategy(
            kind="analysis_review_bounded_v1",
        ),
    )
    contract.focus_gate.default_path = "deliberate"
    payload = _focus_decision_payload("selected")

    result = validate_stage_output(
        role_name="focus_gate",
        payload=payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "gate_path must match expected_gate_path=deliberate; got adjudicate."
        in result.errors
    )


def test_focus_decision_semantic_validation_rejects_noncanonical_selected_focus_id():
    payload = _focus_decision_payload("selected")
    payload["selected_focus_id"] = "release-trigger-automation"

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert any(
        error.startswith(
            "selected_focus_id must equal the canonical seam ID derived from selected_focus_paths:"
        )
        for error in result.errors
    )


def test_focus_decision_semantic_validation_rejects_duplicate_candidate_focus_ids():
    payload = _focus_decision_payload("clarification_requested")
    payload["candidates"].append(
        {
            "focus_id": payload["candidates"][0]["focus_id"],
            "focus_summary": "Release trigger workflows duplicate",
            "candidate_paths": list(payload["candidates"][0]["candidate_paths"]),
            "why_candidate": "This duplicate should still be rejected by semantic validation.",
            "evidence_refs": list(payload["candidates"][0]["evidence_refs"]),
            "score": 0.51,
        }
    )
    payload["question"]["options"] = [
        item["focus_id"] for item in payload["candidates"] if item["focus_id"]
    ]
    payload["adapter_plan"]["secondary_focus_ids"] = list(
        payload["question"]["options"]
    )

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert any(
        error.startswith("candidates contains duplicate focus IDs:")
        for error in result.errors
    )


def test_focus_decision_semantic_validation_rejects_selected_path_handoff_drift():
    payload = _focus_decision_payload("selected")
    payload["candidates"][0]["candidate_paths"] = [".github/workflows/nightly.yml"]
    payload["adapter_plan"]["downstream_primary_seam_paths"] = [
        ".github/workflows/nightly.yml"
    ]

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "candidates[1].focus_id must equal the canonical seam ID derived from candidate_paths: "
        f"expected {canonical_seam_id_for_paths(['.github/workflows/nightly.yml'])}, got "
        f"{canonical_seam_id_for_paths(['.github/workflows/release.yml'])}."
        in result.errors
    )
    assert (
        "selected_focus_paths must equal the selected candidate's candidate_paths after normalization."
        in result.errors
    )
    assert (
        "adapter_plan.downstream_primary_seam_paths must equal selected_focus_paths when focus_type=seam and decision_state=selected."
        in result.errors
    )


def test_focus_decision_semantic_validation_rejects_repo_probe_without_deliberate_checked_files():
    payload = _focus_decision_payload("selected")
    payload["decision_basis"] = "repo_probe"

    result = validate_focus_decision_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert "decision_basis=repo_probe requires gate_path=deliberate." in result.errors
    assert (
        "checked_files must be non-empty when decision_basis=repo_probe."
        in result.errors
    )


def test_analysis_output_semantic_validation_accepts_valid_payload():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")

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


def test_analysis_output_semantic_validation_rejects_selected_focus_drift():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    actual_primary_seam_id = payload["primary_seam"]["seam_id"]

    result = validate_stage_output(
        role_name="proposer",
        payload=payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_primary_seam_id="gate-selected-seam",
    )

    assert result.ok is False
    assert (
        f"primary_seam.seam_id drifted from the selected focus gate seam: expected gate-selected-seam, got {actual_primary_seam_id}."
        in result.errors
    )


def test_analysis_output_semantic_validation_accepts_artifact_downstream_bridge():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    primary_path = payload["primary_seam"]["paths"][0]
    focus_decision = _focus_decision_payload("selected", focus_type="artifact")
    focus_decision["selected_focus_id"] = canonical_artifact_focus_id(primary_path)
    focus_decision["selected_focus_paths"] = [primary_path]
    focus_decision["candidates"][0]["focus_id"] = canonical_artifact_focus_id(
        primary_path
    )
    focus_decision["candidates"][0]["candidate_paths"] = [primary_path]
    focus_decision["adapter_plan"]["primary_focus_id"] = canonical_artifact_focus_id(
        primary_path
    )
    focus_decision["adapter_plan"]["downstream_primary_seam_id"] = (
        canonical_seam_id_for_paths([primary_path])
    )
    focus_decision["adapter_plan"]["downstream_primary_seam_paths"] = [primary_path]

    result = validate_stage_output(
        role_name="proposer",
        payload=payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_primary_seam_id=focus_decision["adapter_plan"][
            "downstream_primary_seam_id"
        ],
        expected_primary_seam_paths=focus_decision["adapter_plan"][
            "downstream_primary_seam_paths"
        ],
    )

    assert result.ok is True
    assert result.errors == []


def test_analysis_output_semantic_validation_accepts_matching_selected_focus_id():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    expected_primary_seam_id = payload["primary_seam"]["seam_id"]

    result = validate_stage_output(
        role_name="reviser_round_1",
        payload=payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_primary_seam_id=expected_primary_seam_id,
        expected_primary_seam_paths=[
            "./.github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/codex-cli-release-watch.yml",
        ],
        open_issue_ids=[],
        expected_open_topic_ids=[],
    )

    assert result.ok is True
    assert result.errors == []


def test_analysis_output_semantic_validation_rejects_selected_focus_path_drift_after_normalization():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    expected_primary_seam_id = payload["primary_seam"]["seam_id"]

    result = validate_stage_output(
        role_name="proposer",
        payload=payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_primary_seam_id=expected_primary_seam_id,
        expected_primary_seam_paths=["./.github/workflows/release.yml"],
    )

    assert result.ok is False
    assert (
        "primary_seam.paths drifted from the selected focus gate paths after normalization: "
        "expected ['.github/workflows/release.yml'], got ['.github/workflows/codex-cli-release-watch.yml']."
        in result.errors
    )


def test_analysis_output_semantic_validation_accepts_empty_none_reason_when_items_exist():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["uncertainties"] = {
        "items": ["Edge cases remain around rollback sequencing."],
        "none_reason": "",
    }

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
    assert result.warnings == []


def test_analysis_output_semantic_validation_rejects_missing_sections_and_files():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_missing_sections")

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
        "recommendations must contain at least 2 item(s) for this task."
        in result.errors
    )
    assert (
        "strengths must contain at least one concrete item or a non-empty none_reason."
        in result.errors
    )
    assert (
        "uncertainties must contain at least one concrete item or a non-empty none_reason."
        in result.errors
    )
    assert "files_reviewed must contain at least 1 non-empty path(s)." in result.errors


def test_analysis_output_semantic_validation_preserves_exact_section_redundancy_warnings():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["strengths"]["none_reason"] = "Already covered above."
    payload["uncertainties"] = {
        "items": ["Manual rollback verification was not re-run."],
        "none_reason": "A caveat was already recorded.",
    }

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
    assert result.warnings == [
        "strengths contains both concrete items and none_reason; prefer one or the other.",
        "uncertainties contains both concrete items and none_reason; prefer one or the other.",
    ]


def test_reviser_semantic_validation_requires_full_issue_resolution_map_coverage():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_missing_issue_resolution")

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
    payload = _analysis_output_payload("analysis_output_missing_topic_resolution")

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
    payload = _analysis_output_payload("analysis_output_unknown_topic_resolution")

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
    assert (
        "topic_resolution_map references unknown topic IDs: TOPIC-999" in result.errors
    )


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
    assert (
        "recommendation_reviews is missing recommendation indices: 2" in result.errors
    )
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
    payload = _analysis_output_payload("analysis_output_too_many_evidence")

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
        "recommendations[1].evidence exceeds the bounded-review cap of 3 item(s)."
        in result.errors
    )


def test_trust_analysis_output_semantic_validation_allows_more_than_three_evidence_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _analysis_output_payload("analysis_output_trust_surface_valid")
    payload["recommendations"][0]["evidence"] = [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/release.yml",
        ".github/workflows/nightly.yml",
    ]
    payload["files_reviewed"] = [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/release.yml",
        ".github/workflows/nightly.yml",
    ]
    payload["recommendations"][0]["verified_evidence_refs"] = [
        ".github/workflows/codex-cli-release-watch.yml"
    ]
    payload["recommendations"][0]["checked_files"] = [
        ".github/workflows/codex-cli-release-watch.yml"
    ]
    payload["recommendations"][0]["affected_files"] = [
        ".github/workflows/codex-cli-release-watch.yml"
    ]
    payload["recommendations"][0]["grounding_mode"] = "direct"

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


def test_analysis_output_semantic_validation_rejects_evidence_outside_files_reviewed():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
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
    payload = _analysis_output_payload("analysis_output_valid")
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
    payload = _analysis_output_payload("analysis_output_valid")

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
    payload = _analysis_output_payload("analysis_output_too_many_must_check_files")

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
    payload = _analysis_output_payload("analysis_output_too_many_optional_check_files")

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
    payload = _analysis_output_payload(
        "analysis_output_must_check_not_in_files_reviewed"
    )

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
    payload = _analysis_output_payload("analysis_output_valid")
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
    payload = _analysis_output_payload("analysis_output_valid")
    payload["files_reviewed"].append("does/not/exist.py")
    payload["recommendations"][0]["review_surface"]["must_check_files"] = [
        "does/not/exist.py"
    ]

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
    payload = _analysis_output_payload("analysis_output_valid")
    payload["recommendations"][0]["review_surface"]["optional_check_files"] = [
        "does/not/exist.py"
    ]

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


def test_analysis_output_semantic_validation_requires_primary_seam_structure():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["primary_seam"] = {
        "seam_id": "",
        "summary": "",
        "why_primary": "",
        "paths": [],
    }

    result = validate_analysis_output_payload(
        payload,
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        expected_open_issue_ids=[],
        require_issue_resolution_map=False,
    )

    assert result.ok is False
    assert "primary_seam.seam_id must be non-empty." in result.errors
    assert "primary_seam.summary must be non-empty." in result.errors
    assert "primary_seam.why_primary must be non-empty." in result.errors
    assert (
        "primary_seam.paths must contain at least one non-empty path." in result.errors
    )


def test_analysis_output_semantic_validation_rejects_seam_paths_outside_files_reviewed():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["secondary_seams_considered"][0]["paths"] = [
        ".github/workflows/release.yml"
    ]

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
        "secondary_seams_considered[1].paths must be a subset of files_reviewed: "
        ".github/workflows/release.yml"
    ) in result.errors


def test_analysis_output_semantic_validation_rejects_seam_paths_outside_workspace_snapshot():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["primary_seam"]["paths"] = ["does/not/exist.py"]

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
        "primary_seam.paths contains path(s) not present in the workspace snapshot: "
        "does/not/exist.py"
    ) in result.errors


def test_analysis_output_semantic_validation_rejects_recommendation_binding_to_undeclared_seam():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["recommendations"][1]["seam_id"] = "undeclared-seam"

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
        "recommendations[2].seam_id must bind to primary_seam.seam_id or a declared "
        "secondary_seams_considered seam_id: undeclared-seam"
    ) in result.errors


def test_analysis_output_semantic_validation_requires_non_primary_seam_expansion_reason():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["recommendations"][1]["seam_expansion_reason"] = ""

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
        "recommendations[2].seam_expansion_reason must be non-empty for non-primary seams."
        in result.errors
    )


def test_analysis_output_semantic_validation_rejects_primary_seam_expansion_reason():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["recommendations"][0]["seam_expansion_reason"] = "Should not be expanded."

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
        "recommendations[1].seam_expansion_reason must be empty when bound to primary_seam."
        in result.errors
    )


def test_analysis_output_semantic_validation_requires_primary_seam_binding_retention():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["recommendations"][0]["seam_id"] = payload["secondary_seams_considered"][0][
        "seam_id"
    ]
    payload["recommendations"][0][
        "seam_expansion_reason"
    ] = "Shifted entirely to the sibling seam."

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
        "At least one recommendation must remain bound to primary_seam.seam_id."
        in result.errors
    )


def test_analysis_output_semantic_validation_rejects_bounded_secondary_seam_overflow():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["secondary_seams_considered"] = [
        {
            "seam_id": "secondary-a",
            "summary": "Secondary seam A.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/claude-code-release-watch.yml"],
        },
        {
            "seam_id": "secondary-b",
            "summary": "Secondary seam B.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/release.yml"],
        },
        {
            "seam_id": "secondary-c",
            "summary": "Secondary seam C.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/nightly.yml"],
        },
    ]
    payload["files_reviewed"] = list(_workspace_paths())
    payload["scope_escapes"] = []
    payload["recommendations"][1]["seam_id"] = "secondary-a"
    payload["recommendations"][1][
        "seam_expansion_reason"
    ] = "Corroborate against sibling automation."

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
        "secondary_seams_considered[3] requires scope_escapes coverage for every declared third-seam path: "
        ".github/workflows/nightly.yml"
    ) in result.errors


def test_analysis_output_semantic_validation_accepts_bounded_third_secondary_seam_with_matching_scope_escapes():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["secondary_seams_considered"] = [
        {
            "seam_id": "secondary-a",
            "summary": "Secondary seam A.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/claude-code-release-watch.yml"],
        },
        {
            "seam_id": "secondary-b",
            "summary": "Secondary seam B.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/release.yml"],
        },
        {
            "seam_id": "secondary-c",
            "summary": "Secondary seam C.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/nightly.yml"],
        },
    ]
    payload["files_reviewed"] = list(_workspace_paths())
    payload["scope_escapes"] = [
        {
            "path": ".github/workflows/nightly.yml",
            "reason": "The third seam is required to check the final sibling workflow in the bounded parity slice.",
        }
    ]
    payload["recommendations"][1]["seam_id"] = "secondary-a"
    payload["recommendations"][1][
        "seam_expansion_reason"
    ] = "Corroborate against sibling automation."

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


def test_analysis_output_semantic_validation_rejects_bounded_third_secondary_seam_with_extraneous_scope_escape_path():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["secondary_seams_considered"] = [
        {
            "seam_id": "secondary-a",
            "summary": "Secondary seam A.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/claude-code-release-watch.yml"],
        },
        {
            "seam_id": "secondary-b",
            "summary": "Secondary seam B.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/release.yml"],
        },
        {
            "seam_id": "secondary-c",
            "summary": "Secondary seam C.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/nightly.yml"],
        },
    ]
    payload["files_reviewed"] = list(_workspace_paths())
    payload["scope_escapes"] = [
        {
            "path": ".github/workflows/nightly.yml",
            "reason": "The third seam is required to check the final sibling workflow in the bounded parity slice.",
        },
        {
            "path": ".github/workflows/release.yml",
            "reason": "This unrelated escape path should not authorize the overflow.",
        },
    ]
    payload["recommendations"][1]["seam_id"] = "secondary-a"
    payload["recommendations"][1][
        "seam_expansion_reason"
    ] = "Corroborate against sibling automation."

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
        "analysis-stage scope_escapes used for bounded third-seam overflow must stay within secondary_seams_considered[3].paths: "
        ".github/workflows/release.yml"
    ) in result.errors


def test_analysis_output_semantic_validation_rejects_more_than_three_secondary_seams_in_bounded_mode():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(task, _strategy())
    payload = _analysis_output_payload("analysis_output_valid")
    payload["secondary_seams_considered"] = [
        {
            "seam_id": "secondary-a",
            "summary": "Secondary seam A.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/claude-code-release-watch.yml"],
        },
        {
            "seam_id": "secondary-b",
            "summary": "Secondary seam B.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/release.yml"],
        },
        {
            "seam_id": "secondary-c",
            "summary": "Secondary seam C.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/nightly.yml"],
        },
        {
            "seam_id": "secondary-d",
            "summary": "Secondary seam D.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/codex-cli-release-watch.yml"],
        },
    ]
    payload["files_reviewed"] = list(_workspace_paths())
    payload["scope_escapes"] = [
        {
            "path": ".github/workflows/nightly.yml",
            "reason": "The third seam is required to check the final sibling workflow in the bounded parity slice.",
        }
    ]

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
        "secondary_seams_considered overflow: bounded mode allows at most one third secondary seam when scope_escapes explicitly justify it."
    ) in result.errors


def test_trust_analysis_output_semantic_validation_allows_more_than_two_secondary_seams():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _analysis_output_payload("analysis_output_trust_surface_valid")
    payload["files_reviewed"] = list(_workspace_paths())
    payload["secondary_seams_considered"] = [
        {
            "seam_id": "secondary-a",
            "summary": "Secondary seam A.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/claude-code-release-watch.yml"],
        },
        {
            "seam_id": "secondary-b",
            "summary": "Secondary seam B.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/release.yml"],
        },
        {
            "seam_id": "secondary-c",
            "summary": "Secondary seam C.",
            "why_not_primary": "Additional corroboration only.",
            "paths": [".github/workflows/nightly.yml"],
        },
    ]
    payload["recommendations"][1]["seam_id"] = "secondary-a"
    payload["recommendations"][1][
        "seam_expansion_reason"
    ] = "Corroborate against sibling automation."

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
    assert (
        "issues exceeds the bounded-review cap of 5 item(s) for critic."
        in result.errors
    )


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
    assert (
        "topics exceeds the bounded-review cap of 2 item(s) for critic."
        in result.errors
    )


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
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _analysis_output_payload("analysis_output_trust_surface_valid")

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
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _analysis_output_payload("analysis_output_verified_evidence_not_subset")

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
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _analysis_output_payload("analysis_output_uncovered_affected_files")

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
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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

    assert result.ok is False
    assert (
        "issues[1] overrides blocking_class for kind=missing_priority but is missing blocking_class_override_reason."
        in result.errors
    )


def test_trust_review_semantic_validation_accepts_override_reason_and_warns_on_late_auditor_overflow():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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
        prior_open_issue_records=[{"issue_id": "AR-001", "recommendation_index": 2}],
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
    assert result.warnings == [
        "new medium-or-higher auditor issues exceed the bounded-review cap of 1 after round 0."
    ]


def test_trust_review_semantic_validation_accepts_structured_review_refs_for_topic_classification():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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


def test_trust_review_semantic_validation_accepts_structured_review_refs_for_global_issue_classification():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _fixture()["review_payload_trust_issue_closure_valid"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=["AR-001"],
        prior_open_issue_records=[
            {
                "issue_id": "AR-001",
                "recommendation_index": None,
                "_prior_surfaced_refs": [
                    ".github/workflows/codex-cli-release-watch.yml"
                ],
            }
        ],
        prior_open_topic_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "bound",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 8,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "issue_closure_review_ref_count": 2,
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
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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
            "normalized_ref_count": 4,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "topic_closure_review_ref_count": 0,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": ["TOPIC-001"],
        },
    )

    assert result.ok is False
    assert (
        "trust review payload lacks provenance-complete structured review refs for global topic closures TOPIC-001. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_issue_closure_verified_refs_that_overclaim_prior_surfaced_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = _fixture()["review_payload_trust_issue_closure_overclaim"]

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=["AR-001"],
        prior_open_issue_records=[
            {
                "issue_id": "AR-001",
                "recommendation_index": None,
                "_prior_surfaced_refs": [
                    ".github/workflows/codex-cli-release-watch.yml"
                ],
            }
        ],
        prior_open_topic_ids=[],
        expected_recommendation_count=2,
        payload_provenance={
            "status": "bound",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 9,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "issue_closure_review_ref_count": 3,
            "closure_provenance_satisfied": True,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
    )

    assert result.ok is False
    assert (
        "issue_closure_reviews[1].verified_evidence_refs must be a subset of the prior surfaced refs for issue_id AR-001: .github/workflows/claude-code-release-watch.yml"
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_global_topic_without_recommendation_level_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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
    payload["topic_closure_reviews"] = []

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
        "trust review payload lacks provenance-complete structured review refs for global topic closures TOPIC-002. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_global_topic_when_recommendations_are_covered():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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
    payload["carried_forward_topic_ids"] = []
    payload["topic_closure_reviews"] = []

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
        "trust review payload lacks provenance-complete structured review refs for global topic closures TOPIC-002. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_allows_relinked_topic_to_close_on_recommendation_proof():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = copy.deepcopy(_fixture()["review_payload_trust_structured_refs_valid"])
    payload["resolved_topic_ids"] = ["TOPIC-001"]
    payload["carried_forward_topic_ids"] = []
    payload["waived_topic_ids"] = []
    payload["topic_closure_reviews"] = []

    result = validate_analysis_review_payload(
        payload,
        role_name="critic",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=["TOPIC-001"],
        prior_open_topic_records=[{"topic_id": "TOPIC-001", "recommendation_index": 2}],
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


def test_trust_review_semantic_validation_rejects_global_issue_when_recommendations_are_covered():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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
    payload["carried_forward_topic_ids"] = []
    payload["topic_closure_reviews"] = []

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
        "trust review payload lacks provenance-complete structured review refs for global issue closures AR-002. files_reviewed alone is not sufficient."
        in result.errors
    )


def test_trust_review_semantic_validation_rejects_duplicate_topic_closure_review_ids():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = copy.deepcopy(_fixture()["review_payload_trust_structured_refs_valid"])
    payload["topic_closure_reviews"] = [
        {
            "topic_id": "TOPIC-001",
            "checked_files": [".github/workflows/claude-code-release-watch.yml"],
            "verified_evidence_refs": [
                ".github/workflows/claude-code-release-watch.yml"
            ],
            "summary": "First proof entry.",
        },
        {
            "topic_id": "TOPIC-001",
            "checked_files": [".github/workflows/claude-code-release-watch.yml"],
            "verified_evidence_refs": [
                ".github/workflows/claude-code-release-watch.yml"
            ],
            "summary": "Duplicate proof entry.",
        },
    ]

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
            "normalized_ref_count": 10,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "topic_closure_review_ref_count": 4,
            "closure_provenance_satisfied": True,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
    )

    assert result.ok is False
    assert (
        "topic_closure_reviews contains duplicate topic_ids: TOPIC-001" in result.errors
    )


def test_trust_review_semantic_validation_rejects_topic_closure_verified_refs_outside_checked_files():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
    payload = copy.deepcopy(_fixture()["review_payload_trust_structured_refs_valid"])
    payload["topic_closure_reviews"] = [
        {
            "topic_id": "TOPIC-001",
            "checked_files": [".github/workflows/claude-code-release-watch.yml"],
            "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
            "summary": "The proof overclaims beyond the checked file set.",
        }
    ]

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
            "normalized_ref_count": 8,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "topic_closure_review_ref_count": 2,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": ["TOPIC-001"],
        },
    )

    assert result.ok is False
    assert (
        "topic_closure_reviews[1].verified_evidence_refs must be a subset of checked_files: .github/workflows/codex-cli-release-watch.yml"
        in result.errors
    )


def test_trust_review_semantic_validation_requires_per_verdict_structured_refs():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task, _strategy("analysis_review_trust_v1")
    )
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


def test_trust_attestation_review_semantic_validation_accepts_dense_bounded_coverage():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task,
        _strategy(
            "analysis_review_trust_v1",
            trust_execution_mode="attestation_over_bounded",
        ),
    )
    contract.trust_review.execution_mode = "attestation_over_bounded"
    payload = _attestation_review_payload()
    bounded_attestation_input = _bounded_attestation_input_payload()
    bounded_attestation_input["contract"]["trust_execution_mode"] = (
        "attestation_over_bounded"
    )

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=[],
        payload_provenance={
            "status": "bound",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "closure_provenance_satisfied": True,
            "covered_recommendation_indices": [1, 2],
            "uncovered_recommendation_indices": [],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
        bounded_attestation_input=bounded_attestation_input,
    )

    assert result.ok is True
    assert result.errors == []


def test_trust_attestation_review_semantic_validation_requires_dense_bounded_indices():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task,
        _strategy(
            "analysis_review_trust_v1",
            trust_execution_mode="attestation_over_bounded",
        ),
    )
    contract.trust_review.execution_mode = "attestation_over_bounded"
    payload = _attestation_review_payload()
    payload["recommendation_reviews"] = [payload["recommendation_reviews"][0]]
    bounded_attestation_input = _bounded_attestation_input_payload()
    bounded_attestation_input["contract"]["trust_execution_mode"] = (
        "attestation_over_bounded"
    )

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=[],
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 1,
            "recommendation_review_ref_count": 2,
            "recommendation_review_ref_field_count": 2,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1],
            "uncovered_recommendation_indices": [2],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
        bounded_attestation_input=bounded_attestation_input,
    )

    assert result.ok is False
    assert (
        "recommendation_reviews is missing recommendation indices: 2"
        in result.errors
    )


def test_trust_attestation_review_semantic_validation_requires_direct_bounded_evidence_rechecks():
    task = _task(min_recommendations=2)
    contract = build_analysis_review_contract(
        task,
        _strategy(
            "analysis_review_trust_v1",
            trust_execution_mode="attestation_over_bounded",
        ),
    )
    contract.trust_review.execution_mode = "attestation_over_bounded"
    payload = _attestation_review_payload()
    payload["recommendation_reviews"][1]["verified_evidence_refs"] = [
        ".github/workflows/nightly.yml"
    ]
    bounded_attestation_input = _bounded_attestation_input_payload()
    bounded_attestation_input["contract"]["trust_execution_mode"] = (
        "attestation_over_bounded"
    )

    result = validate_analysis_review_payload(
        payload,
        role_name="auditor",
        task=task,
        contract=contract,
        workspace_paths=_workspace_paths(),
        prior_open_issue_ids=[],
        prior_open_topic_ids=[],
        payload_provenance={
            "status": "insufficient",
            "policy_mode": "payload_hash_and_refs",
            "normalized_ref_count": 2,
            "recommendation_review_ref_count": 4,
            "recommendation_review_ref_field_count": 4,
            "closure_provenance_satisfied": False,
            "covered_recommendation_indices": [1],
            "uncovered_recommendation_indices": [2],
            "uncovered_global_issue_ids": [],
            "uncovered_global_topic_ids": [],
        },
        bounded_attestation_input=bounded_attestation_input,
    )

    assert result.ok is False
    assert (
        "recommendation_reviews[2].verified_evidence_refs must stay within bounded_attestation_input.provenance_context.recommendation_evidence_index[2]: .github/workflows/nightly.yml"
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_accepts_valid_payload():
    result = validate_bounded_attestation_input_payload(
        _bounded_attestation_input_payload(),
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is True
    assert result.errors == []


def test_bounded_attestation_input_semantic_validation_rejects_missing_required_fields():
    payload = _bounded_attestation_input_payload()
    payload.pop("schema_version")
    payload.pop("contract")

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "bounded_attestation_input is missing required field: schema_version"
        in result.errors
    )
    assert "bounded_attestation_input is missing required field: contract" in result.errors


def test_bounded_attestation_input_semantic_validation_rejects_wrong_schema_version():
    payload = _bounded_attestation_input_payload()
    payload["schema_version"] = "analysis_review_bounded_attestation_input_v0"

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "schema_version must equal analysis_review_bounded_attestation_input_v1; got analysis_review_bounded_attestation_input_v0."
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_rejects_invalid_source_mode():
    payload = _bounded_attestation_input_payload()
    payload["source"].pop("mode")

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert "source.mode is required." in result.errors

    payload = _bounded_attestation_input_payload()
    payload["source"]["mode"] = "trust"
    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert "source.mode must equal bounded; got trust." in result.errors


def test_bounded_attestation_input_semantic_validation_rejects_invalid_trust_execution_mode():
    payload = _bounded_attestation_input_payload()
    payload["contract"]["trust_execution_mode"] = "future_mode"

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "contract.trust_execution_mode must be one of ['attestation_over_bounded', 'legacy_full_review']; got future_mode."
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_rejects_review_surface_count_mismatch():
    payload = _bounded_attestation_input_payload()
    payload["review_surface"]["recommendation_count"] = 1

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "review_surface.recommendation_count must equal len(bounded_analysis.recommendations)."
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_rejects_out_of_workspace_refs():
    payload = _bounded_attestation_input_payload()
    payload["provenance_context"]["recommendation_evidence_index"]["2"] = [
        "../outside.py"
    ]

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "provenance_context.recommendation_evidence_index[2] contains path(s) not present in the workspace snapshot: ../outside.py"
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_rejects_forbidden_publication_fields():
    payload = _bounded_attestation_input_payload()
    payload["bounded_analysis"]["analysis_review_status"] = {"publishability": "ready"}

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "bounded_attestation_input.bounded_analysis must not contain forbidden publication field 'analysis_review_status'."
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_rejects_recommendation_ordering_drift():
    payload = _bounded_attestation_input_payload()
    payload["provenance_context"]["recommendation_evidence_index"] = {
        "1": [".github/workflows/release.yml"],
        "2": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/claude-code-release-watch.yml",
        ],
    }

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "provenance_context.recommendation_evidence_index must preserve bounded_analysis recommendation evidence order without drift."
        in result.errors
    )


def test_bounded_attestation_input_semantic_validation_rejects_normalized_ref_count_mismatch():
    payload = _bounded_attestation_input_payload()
    payload["provenance_context"]["normalized_ref_count"] = 2

    result = validate_bounded_attestation_input_payload(
        payload,
        workspace_paths=_workspace_paths(),
    )

    assert result.ok is False
    assert (
        "provenance_context.normalized_ref_count must match the unique normalized evidence refs derived from recommendation_evidence_index."
        in result.errors
    )
