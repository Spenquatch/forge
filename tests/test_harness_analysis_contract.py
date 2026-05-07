from __future__ import annotations

from pathlib import Path

import pytest

from anvil.harness.contracts import (
    build_analysis_review_contract,
    default_blocking_class_for_kind,
)
from anvil.harness.files import load_structured_file
from anvil.harness.schemas import (
    analysis_review_schema,
    bounded_attestation_input_schema,
)
from anvil.harness.types import ReviewLoopPolicy, StrategyConfig, TaskSpec


def _task(
    min_recommendations: int = 2,
    evidence_cap_policy: str = "trim_to_cap",
    focus_gate: dict[str, object] | None = None,
    focus_gate_answer: dict[str, object] | None = None,
) -> TaskSpec:
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
            "focus_gate": focus_gate,
            "focus_gate_answer": focus_gate_answer,
        }
    )


def _strategy(focus_gate: dict[str, object] | None = None) -> StrategyConfig:
    return StrategyConfig.from_dict(
        {
            "name": "analysis-review-codex-claude",
            "kind": "analysis_review_bounded_v1",
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
            "focus_gate": focus_gate,
        }
    )


def test_build_analysis_review_contract_uses_task_and_strategy_requirements():
    contract = build_analysis_review_contract(_task(min_recommendations=3), _strategy())
    serialized = contract.to_dict()

    assert contract.contract_version == "analysis_review_v1_contract_v10"
    assert contract.mode == "bounded"
    assert contract.reviser_goal == "close_all_open_blockers"
    assert contract.stop_policy.max_loops == 3
    assert contract.stop_policy.min_grounding_score == 0.8
    assert contract.partial_acceptance.enabled is True
    assert contract.partial_acceptance.min_accepted_recommendations == 3
    assert (
        contract.partial_acceptance.forbid_correctness_blockers_on_accepted_recommendations
        is True
    )
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
    assert (
        contract.bounded_review.auditor_new_medium_or_higher_issue_cap_after_round0 == 1
    )
    assert contract.bounded_review.require_scope_escape_justification is True
    assert contract.trust_review.require_taxonomy_override_reason is False
    assert contract.trust_review.max_evidence_refs_per_recommendation == 3
    assert contract.trust_review.execution_mode == "legacy_full_review"
    assert contract.trust_review.require_verified_evidence_refs_subset is False
    assert contract.trust_review.require_affected_file_coverage is False
    assert contract.trust_review.payload_provenance_mode == "none"
    assert contract.trust_review.downgrade_on_semantic_warnings is False
    assert contract.trust_review.downgrade_on_inferred_acceptance is False
    assert contract.trust_review.late_auditor_medium_or_higher_policy == "error"
    assert contract.focus_gate.enabled is False
    assert contract.focus_gate.default_path == "adjudicate"
    assert contract.focus_gate.allowed_focus_types == ["seam"]
    assert contract.focus_gate.clarification_policy == "block_for_clarification"
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
        "max_evidence_refs_per_recommendation": 3,
        "execution_mode": "legacy_full_review",
        "require_taxonomy_override_reason": False,
        "require_verified_evidence_refs_subset": False,
        "require_affected_file_coverage": False,
        "payload_provenance_mode": "none",
        "downgrade_on_semantic_warnings": False,
        "downgrade_on_inferred_acceptance": False,
        "late_auditor_medium_or_higher_policy": "error",
    }
    assert serialized["focus_gate"] == {
        "enabled": False,
        "default_path": "adjudicate",
        "allowed_focus_types": ["seam"],
        "clarification_policy": "block_for_clarification",
    }


def test_analysis_review_contract_serializes_bounded_trust_and_legacy_alias_modes():
    task = _task(min_recommendations=2)

    legacy = build_analysis_review_contract(
        task,
        StrategyConfig.from_dict(
            {**_strategy().to_dict(), "kind": "analysis_review_v1"}
        ),
    )
    trust = build_analysis_review_contract(
        task,
        StrategyConfig.from_dict(
            {**_strategy().to_dict(), "kind": "analysis_review_trust_v1"}
        ),
    )

    assert legacy.mode == "bounded"
    assert legacy.strategy_kind == "analysis_review_v1"
    assert legacy.to_dict()["trust_review"]["execution_mode"] == "legacy_full_review"
    assert legacy.to_dict()["effective_strategy"] == {
        "kind": "analysis_review_v1",
        "mode": "bounded",
    }

    assert trust.mode == "trust"
    assert trust.strategy_kind == "analysis_review_trust_v1"
    assert trust.trust_review.execution_mode == "legacy_full_review"
    assert trust.trust_review.require_taxonomy_override_reason is True
    assert trust.trust_review.max_evidence_refs_per_recommendation is None
    assert trust.trust_review.require_verified_evidence_refs_subset is True
    assert trust.trust_review.require_affected_file_coverage is True
    assert trust.trust_review.payload_provenance_mode == "payload_hash_and_refs"
    assert trust.trust_review.downgrade_on_semantic_warnings is True
    assert trust.trust_review.downgrade_on_inferred_acceptance is True
    assert trust.trust_review.late_auditor_medium_or_higher_policy == "warn"
    assert (
        trust.to_dict()["trust_review"]["max_evidence_refs_per_recommendation"] is None
    )
    assert trust.to_dict()["trust_review"]["execution_mode"] == "legacy_full_review"
    assert trust.to_dict()["effective_strategy"] == {
        "kind": "analysis_review_trust_v1",
        "mode": "trust",
    }
    assert legacy.to_dict()["focus_gate"] == {
        "enabled": False,
        "default_path": "adjudicate",
        "allowed_focus_types": ["seam"],
        "clarification_policy": "block_for_clarification",
    }
    assert trust.to_dict()["focus_gate"] == {
        "enabled": False,
        "default_path": "adjudicate",
        "allowed_focus_types": ["seam"],
        "clarification_policy": "block_for_clarification",
    }


def test_analysis_review_contract_resolves_focus_gate_from_strategy_and_task():
    contract = build_analysis_review_contract(
        _task(
            focus_gate={
                "enabled": True,
                "allowed_focus_types": ["seam"],
                "clarification_policy": "block_for_clarification",
            }
        ),
        _strategy(
            focus_gate={
                "enabled": False,
                "default_path": "deliberate",
            }
        ),
    )

    assert contract.contract_version == "analysis_review_v1_contract_v10"
    assert contract.focus_gate.enabled is True
    assert contract.focus_gate.default_path == "deliberate"
    assert contract.focus_gate.allowed_focus_types == ["seam"]
    assert contract.focus_gate.clarification_policy == "block_for_clarification"
    assert contract.to_dict()["focus_gate"] == {
        "enabled": True,
        "default_path": "deliberate",
        "allowed_focus_types": ["seam"],
        "clarification_policy": "block_for_clarification",
    }


def test_analysis_review_contract_accepts_never_ask_focus_gate_policy():
    contract = build_analysis_review_contract(
        _task(
            focus_gate={
                "enabled": True,
                "allowed_focus_types": ["seam"],
                "clarification_policy": "never_ask",
            }
        ),
        _strategy(
            focus_gate={
                "enabled": True,
                "default_path": "deliberate",
            }
        ),
    )

    assert contract.focus_gate.clarification_policy == "never_ask"
    assert contract.to_dict()["focus_gate"] == {
        "enabled": True,
        "default_path": "deliberate",
        "allowed_focus_types": ["seam"],
        "clarification_policy": "never_ask",
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


def test_task_focus_gate_answer_accepts_empty_freeform_answer():
    task = _task(
        focus_gate_answer={
            "question_prompt": " Which focus should this run prioritize? ",
            "selected_option": " release-trigger-automation ",
            "freeform_answer": "",
        }
    )

    assert task.focus_gate_answer is not None
    assert task.focus_gate_answer.question_prompt == "Which focus should this run prioritize?"
    assert task.focus_gate_answer.selected_option == "release-trigger-automation"
    assert task.focus_gate_answer.freeform_answer == ""


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"question_prompt": "", "selected_option": "release-trigger-automation"},
            "focus_gate_answer.question_prompt must be a non-empty string.",
        ),
        (
            {
                "question_prompt": "Which focus should this run prioritize?",
                "selected_option": "   ",
            },
            "focus_gate_answer.selected_option must be a non-empty string.",
        ),
    ],
)
def test_task_focus_gate_answer_requires_non_empty_prompt_and_selection(
    payload: dict[str, object], message: str
):
    with pytest.raises(ValueError, match=message):
        _task(focus_gate_answer=payload)


def test_build_analysis_review_contract_rejects_adjudicate_focus_gate_answer_before_runner():
    task = _task(
        focus_gate={"enabled": True, "allowed_focus_types": ["seam"]},
        focus_gate_answer={
            "question_prompt": "Which focus should this run prioritize?",
            "selected_option": "release-trigger-automation",
            "freeform_answer": "",
        },
    )
    strategy = _strategy(
        focus_gate={
            "enabled": True,
            "default_path": "adjudicate",
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "focus_gate_answer is only allowed when the resolved focus gate path is deliberate; "
            "resolved default_path=adjudicate\\."
        ),
    ):
        build_analysis_review_contract(task, strategy)


@pytest.mark.parametrize(
    ("task_focus_gate", "strategy_focus_gate", "message"),
    [
        (
            {"default_path": "adjudicate"},
            None,
            "focus_gate contains unsupported keys: default_path.",
        ),
        (
            None,
            {"clarification_policy": "block_for_clarification"},
            "focus_gate contains unsupported keys: clarification_policy.",
        ),
    ],
)
def test_focus_gate_rejects_unknown_keys(
    task_focus_gate: dict[str, object] | None,
    strategy_focus_gate: dict[str, object] | None,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        if task_focus_gate is not None:
            _task(focus_gate=task_focus_gate)
        else:
            _strategy(focus_gate=strategy_focus_gate)


def test_task_focus_gate_accepts_artifact_singleton_allowed_focus_types():
    task = _task(focus_gate={"allowed_focus_types": ["artifact"]})

    assert task.focus_gate is not None
    assert task.focus_gate.allowed_focus_types == ["artifact"]


@pytest.mark.parametrize(
    ("allowed_focus_types", "message"),
    [
        (
            ["seam", "artifact"],
            "focus_gate.allowed_focus_types must contain exactly one value; mixed-type lists are not allowed.",
        ),
        (
            ["seam", "seam"],
            r"focus_gate\.allowed_focus_types must contain exactly one value: \['seam'\] or \['artifact'\]\.",
        ),
        (
            ["unknown"],
            r"focus_gate\.allowed_focus_types must contain exactly one value: \['seam'\] or \['artifact'\]\.",
        ),
    ],
)
def test_task_focus_gate_rejects_non_singleton_or_unknown_allowed_focus_types(
    allowed_focus_types: list[str], message: str
):
    with pytest.raises(ValueError, match=message):
        _task(focus_gate={"allowed_focus_types": allowed_focus_types})


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
    assert "bounded_attestation_input" not in schema["properties"]


def test_bounded_attestation_input_schema_freezes_m1_handoff_shape():
    schema = bounded_attestation_input_schema()

    assert schema["required"] == [
        "schema_version",
        "source",
        "focus_decision",
        "contract",
        "bounded_analysis",
        "review_surface",
        "ledgers",
        "provenance_context",
    ]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == (
        "analysis_review_bounded_attestation_input_v1"
    )
    assert schema["properties"]["source"]["additionalProperties"] is False
    assert schema["properties"]["source"]["properties"]["mode"]["enum"] == ["bounded"]
    assert schema["properties"]["focus_decision"]["anyOf"][1] == {"type": "null"}
    assert (
        schema["properties"]["focus_decision"]["anyOf"][0]["additionalProperties"]
        is False
    )
    assert schema["properties"]["contract"]["additionalProperties"] is False
    assert schema["properties"]["contract"]["properties"]["trust_execution_mode"][
        "enum"
    ] == ["legacy_full_review", "attestation_over_bounded"]
    assert schema["properties"]["bounded_analysis"]["additionalProperties"] is False
    assert schema["properties"]["bounded_analysis"]["properties"]["recommendations"][
        "minItems"
    ] == 1
    assert schema["properties"]["review_surface"]["additionalProperties"] is False
    assert schema["properties"]["review_surface"]["properties"]["review_stages"][
        "type"
    ] == "array"
    assert schema["properties"]["ledgers"]["additionalProperties"] is False
    assert schema["properties"]["ledgers"]["properties"]["issue_ledger"]["type"] == "array"
    assert schema["properties"]["ledgers"]["properties"]["topic_ledger"]["type"] == "array"
    assert (
        schema["properties"]["provenance_context"]["additionalProperties"] is False
    )
    assert (
        schema["properties"]["provenance_context"]["properties"][
            "recommendation_evidence_index"
        ]["additionalProperties"]
        is False
    )
    assert (
        schema["properties"]["provenance_context"]["properties"][
            "recommendation_evidence_index"
        ]["patternProperties"]["^[0-9]+$"]["items"]
        == {"type": "string"}
    )


def test_default_blocking_class_for_kind_matches_analysis_issue_taxonomy():
    assert default_blocking_class_for_kind("confidence_calibration") == "presentation"
    assert (
        default_blocking_class_for_kind("insufficient_specificity") == "actionability"
    )
    assert default_blocking_class_for_kind("factual_error") == "correctness"
    assert default_blocking_class_for_kind("missing_priority") == "completeness"
    assert default_blocking_class_for_kind("unknown-kind") == "presentation"


def test_analysis_review_defaults_and_example_strategy_are_tuned_for_priority2():
    assert (
        ReviewLoopPolicy.defaults_for_strategy_kind("analysis_review_v1").max_loops == 3
    )
    assert (
        ReviewLoopPolicy.defaults_for_strategy_kind(
            "analysis_review_bounded_v1"
        ).max_loops
        == 3
    )
    assert (
        ReviewLoopPolicy.defaults_for_strategy_kind(
            "analysis_review_trust_v1"
        ).max_loops
        == 3
    )

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
    assert trust_example["roles"]["critic"]["provider"] == "codex_gpt_5_4"
    assert trust_example["roles"]["critic"]["effort"] == "high"
    assert trust_example["roles"]["auditor"]["provider"] == "codex_gpt_5_4"
    assert trust_example["roles"]["auditor"]["effort"] == "high"
    assert trust_example["review_loops"]["max_loops"] == 3


def test_readme_documents_trust_recommendation_admissibility_and_preview_only_markdown():
    readme = Path("README.md").read_text(encoding="utf-8")

    shared_discovery_phrase = (
        "Shared repo-local discovery applies to both bounded and trust."
    )
    bounded_difference_phrase = "Bounded differs by caps and scope discipline."
    trust_difference_phrase = (
        "Trust differs by provenance completeness, evidence completeness, atomicity, and publication."
    )
    assert shared_discovery_phrase in readme
    assert bounded_difference_phrase in readme
    assert trust_difference_phrase in readme
    assert (
        readme.index(shared_discovery_phrase)
        < readme.index(bounded_difference_phrase)
        < readme.index(trust_difference_phrase)
    )
    assert (
        "`files_hint` is a starting slice rather than a hard discovery boundary"
        in readme
    )
    assert "same nearest governing spec/manifest or sibling workflow" in readme
    assert "one-hop repo-local corroboration" in readme
    assert "existing bounded caps" in readme
    assert (
        "prefer nearer governing/spec/workflow evidence over farther plan/runbook prose"
        in readme
    )
    assert (
        "PARTIAL_ANSWER.json` / `PARTIAL_ANSWER.md` when an eligible accepted-partial output or trust-mode fallback subset is the selected primary deliverable"
        in readme
    )
    assert "analysis_review_status.recommendation_admissibility" in readme
    assert "Across bounded and trust modes" in readme
    assert "FINAL_ANSWER.*` is all-or-nothing" in readme
    assert "final_answer_recommendation_indices" in readme
    assert "partial_only_recommendation_indices" in readme
    assert "excluded_recommendation_indices" in readme
    assert "reasons_by_recommendation_index" in readme
    assert (
        "`accepted_with_caveat`, `inferred_grounding`, `not_accepted`, and `topic_blocked`"
        in readme
    )
    assert (
        "accepted recommendations, including `accept_with_caveat`, stay in `final_answer_recommendation_indices`"
        in readme
    )
    assert (
        "Recommendations outside `final_answer_recommendation_indices` are withheld from `FINAL_ANSWER.*` in trust mode"
        in readme
    )
    assert (
        "split independently actionable direct or spec-backed guidance from weaker inferred or optional hardening before review"
        in readme
    )
    assert "Reserve `grounding_mode = mixed` for inseparable single actions." in readme
    assert (
        "Avoidable mixed-grounding bundles are a prompt/review defect, not a runner-owned admissibility state."
        in readme
    )
    assert (
        "candidate subset comes from recommendations kept for `FINAL_ANSWER.*` plus the partial-only recommendations"
        in readme
    )
    assert "Recommendation indices included in `PARTIAL_ANSWER.*`: `1`, `2`" in readme
    assert "Recommendation indices withheld from `FINAL_ANSWER.*`: `2`" in readme
    assert "Recommendation indices excluded from `PARTIAL_ANSWER.*`: none" in readme
    assert "Those partial-scope lines are frozen only for `PARTIAL_ANSWER.*`." in readme
    assert (
        "`REPORT.md` keeps only final-publication / final-withholding wording" in readme
    )
    assert "analysis_review_status.publishability" in readme
    assert "final_answer_publishable" in readme
    assert "blocking_causes" in readme
    assert (
        "Artifact selection finalizes that publishability outcome after artifact projection"
        in readme
    )
    assert "`final_answer_publishable` must agree with `final_artifact_kind`" in readme
    assert (
        'summary.json["artifacts"]["final_artifact_kind"] == "final_answer"' in readme
    )
    assert "reviewer prose does not decide artifact eligibility" in readme
    assert "advisory carveout is limited to the exact warning strings" in readme
    assert "final_artifact`, `final_artifact_json`, `final_artifact_kind`" in readme
    assert "`Open topics:` and `Carried-forward topics:` as separate labels" in readme
    assert "Markdown compaction is preview-only and renderer-owned." in readme


def test_analysis_review_contract_docs_freeze_v10_admissibility_publishability_and_preview_budgets():
    contract_doc = Path("docs/analysis_review_contract.md").read_text(encoding="utf-8")

    assert "analysis_review_v1_contract_v10" in contract_doc
    assert "`bounded_attestation_input` is runner-owned." in contract_doc
    assert "It is not a public deliverable." in contract_doc
    assert "It intentionally excludes final publication truth" in contract_doc
    assert "M1 emits `bounded_attestation_input`, M2 consumes it." in contract_doc
    assert "`analysis_review_schema()` remains unchanged in M1" in contract_doc
    assert "`bounded_attestation_input_schema()` helper" in contract_doc
    assert 'the only allowed singleton values are `["seam"]` and `["artifact"]`' in contract_doc
    assert 'mixed-type lists such as `["seam", "artifact"]` are rejected explicitly' in contract_doc
    assert '"focus_type": "seam | artifact"' in contract_doc
    assert "Which focus should this run prioritize?" in contract_doc
    assert "downstream_primary_seam_id" in contract_doc
    assert "downstream_primary_seam_paths" in contract_doc
    assert "adaptation_basis" in contract_doc
    assert "hard rule: for artifact runs, `selected_focus_*` is not downstream seam truth" in contract_doc
    shared_discovery_phrase = (
        "Shared repo-local discovery applies to both bounded mode and trust mode:"
    )
    bounded_difference_phrase = "Bounded differs by caps and scope discipline:"
    trust_difference_phrase = (
        "Trust differs by provenance completeness, evidence completeness, atomicity, and publication:"
    )
    assert shared_discovery_phrase in contract_doc
    assert bounded_difference_phrase in contract_doc
    assert trust_difference_phrase in contract_doc
    assert (
        contract_doc.index(shared_discovery_phrase)
        < contract_doc.index(bounded_difference_phrase)
        < contract_doc.index(trust_difference_phrase)
    )
    assert "bounded mode is discovery-bounded, not workflow-file-only" in contract_doc
    assert "`files_hint` is a starting slice, not a hard boundary" in contract_doc
    assert "one-hop repo-local corroboration outside `files_hint`" in contract_doc
    assert "nearest governing repo-local doc or manifest" in contract_doc
    assert (
        "sibling implementation or workflow that establishes the baseline"
        in contract_doc
    )
    assert (
        "corroboration must still stay inside the current caps: evidence max `3`"
        in contract_doc
    )
    assert (
        "trust mode remains stricter because of provenance and publication rules"
        in contract_doc
    )
    assert (
        "prefer nearer governing/spec/workflow evidence over farther plan/runbook prose"
        in contract_doc
    )
    assert "recommendation withholding ledger" in contract_doc
    assert "recommendation_admissibility" in contract_doc
    assert "runner-owned status, not a model-authored payload field" in contract_doc
    assert "payload shape remains unchanged" in contract_doc
    assert "canonical in both bounded mode and trust mode" in contract_doc
    assert "FINAL_ANSWER.*` is all-or-nothing" in contract_doc
    assert "final_answer_recommendation_indices" in contract_doc
    assert "partial_only_recommendation_indices" in contract_doc
    assert "excluded_recommendation_indices" in contract_doc
    assert "reasons_by_recommendation_index" in contract_doc
    assert (
        "In bounded mode, accepted recommendations, including `accept_with_caveat`, stay in `final_answer_recommendation_indices`"
        in contract_doc
    )
    assert (
        "Recommendations outside `final_answer_recommendation_indices` are withheld from `FINAL_ANSWER.*`"
        in contract_doc
    )
    assert (
        "`accepted_with_caveat` and accepted recommendations with `grounding_mode = inferred` move to `partial_only_recommendation_indices`"
        in contract_doc
    )
    assert (
        "Trust admissibility remains recommendation-level, so independently actionable direct or spec-backed guidance should be split from weaker inferred or optional hardening before review."
        in contract_doc
    )
    assert (
        "Reserve `grounding_mode = mixed` for genuinely inseparable single-action recommendations, not bundles that could be split cleanly."
        in contract_doc
    )
    assert (
        "Avoidable mixed-grounding bundles are an authoring and review defect, not a runner-state feature."
        in contract_doc
    )
    assert (
        "`accepted_with_caveat`, `inferred_grounding`, `not_accepted`, and `topic_blocked`"
        in contract_doc
    )
    assert (
        "candidate partial subset comes from `final_answer_recommendation_indices + partial_only_recommendation_indices`"
        in contract_doc
    )
    assert (
        "Global topic blockers, provenance gating, and minimum-threshold fallout remain whole-artifact promotion rules."
        in contract_doc
    )
    assert "Recommendation indices included in PARTIAL_ANSWER.*: 1, 2" in contract_doc
    assert "Recommendation indices withheld from FINAL_ANSWER.*: 2" in contract_doc
    assert "Recommendation indices excluded from PARTIAL_ANSWER.*: none" in contract_doc
    assert "final_answer_publishable" in contract_doc
    assert "blocking_causes" in contract_doc
    assert (
        "`analysis_review_status.publishability` is the canonical final publication outcome."
        in contract_doc
    )
    assert "accepted_with_warnings` does not guarantee `FINAL_ANSWER.*`" in contract_doc
    assert (
        "strengths contains both concrete items and none_reason; prefer one or the other."
        in contract_doc
    )
    assert (
        "uncertainties contains both concrete items and none_reason; prefer one or the other."
        in contract_doc
    )
    assert (
        'Artifact projection finalizes `publishability`; `final_answer_publishable` is `true` exactly when `summary.json["artifacts"]["final_artifact_kind"] == "final_answer"`.'
        in contract_doc
    )
    assert (
        "`Final publication: publishable|blocked`, `Publication blockers:`, and `Recommendation indices withheld from FINAL_ANSWER.*:`"
        in contract_doc
    )
    assert (
        "`REPORT.md` freezes only final-publication / final-withholding wording"
        in contract_doc
    )
    assert (
        "does not render `Recommendation indices included in PARTIAL_ANSWER.*` or `Recommendation indices excluded from PARTIAL_ANSWER.*`"
        in contract_doc
    )
    assert (
        'only runner-owned `analysis_review_status.publishability`, `analysis_review_status.recommendation_admissibility`, and `summary.json["artifacts"]` decide artifact eligibility and publication state'
        in contract_doc
    )
    assert "content verdict is not fully accepted: <verdict>" in contract_doc
    assert (
        "For fully accepted trust runs, `blocking_causes` is deterministic."
        in contract_doc
    )
    assert "1. provenance blocker first, when present" in contract_doc
    assert "2. open topic IDs in sorted order" in contract_doc
    assert "3. carried-forward topic IDs in sorted order" in contract_doc
    assert "4. one semantic-warning blocker" in contract_doc
    assert (
        "deliverable markdown previews at most the first `3` recommendation evidence refs"
        in contract_doc
    )
    assert (
        "`REPORT.md` previews at most the first `2` `checked_files` values"
        in contract_doc
    )
    assert (
        "`Open topics:` and `Carried-forward topics:` as separate labels"
        in contract_doc
    )
    assert "The seam-selection contract is additive to the shared payload family" in contract_doc
    assert "- `primary_seam`" in contract_doc
    assert "- `secondary_seams_considered`" in contract_doc
    assert "- `scope_escapes`" in contract_doc
    assert "- `recommendations[*].seam_id`" in contract_doc
    assert "- `recommendations[*].seam_expansion_reason`" in contract_doc
    assert "- `analysis_review_status.primary_seam`" in contract_doc
    assert "- `analysis_review_status.secondary_seams_considered`" in contract_doc
    assert "- `analysis_review_status.scope_escapes`" in contract_doc
    assert "- `analysis_review_status.recommendation_seam_bindings`" in contract_doc
    assert (
        "Canonical `analysis_review_status.recommendation_seam_bindings[*]` objects are frozen to:"
        in contract_doc
    )
    assert "- `recommendation_index`" in contract_doc
    assert "- `seam_id`" in contract_doc
    assert "- `seam_expansion_reason`" in contract_doc
    assert (
        "`primary_seam` remains the canonical run-context seam." in contract_doc
    )
    assert (
        "`secondary_seams_considered` records only seams actually declared or inspected beyond the primary seam."
        in contract_doc
    )
    assert (
        "analysis/proposer/reviser payloads now include `scope_escapes`."
        in contract_doc
    )
    assert (
        "`recommendations[*].seam_id` binds each recommendation to its seam, and `recommendations[*].seam_expansion_reason` explains why that recommendation expands beyond the primary seam when it does."
        in contract_doc
    )
    assert (
        "in bounded analysis outputs, `scope_escapes` may justify exactly one third secondary seam and nothing beyond that."
        in contract_doc
    )
    assert (
        "review-stage `scope_escapes` semantics remain separate: critic/auditor still use them for later review-surface escapes rather than analysis-stage seam declaration."
        in contract_doc
    )
    assert (
        "default bounded cap is 2; declaring or inspecting a third secondary seam requires a recorded scope_escape; overflow beyond that third seam is never silently normalized away."
        in contract_doc
    )
    assert (
        '- `primary_seam_projection_status: "retained_without_included_recommendations"`'
        in contract_doc
    )
    assert (
        "Canonical primary seam retained for run context; no included recommendation in this artifact binds to it."
        in contract_doc
    )
    assert (
        "Role-specific seam-review duties are separate from the shared seam-selection rules and do not apply to proposer."
        in contract_doc
    )
    assert "Critic seam-review duties:" in contract_doc
    assert (
        "In the critic stage, challenge seam choice before recommendation polish."
        in contract_doc
    )
    assert (
        "In the critic stage, when a recommendation relies on farther plan/runbook prose while a nearer governing spec/manifest or sibling workflow exists, raise the seam defect before polishing wording."
        in contract_doc
    )
    assert (
        "In the critic stage, in bounded mode, flag secondary-seam exploration that silently widened review beyond bounded discipline, even if the recommendation text looks reasonable."
        in contract_doc
    )
    assert (
        "In the critic stage, use `kind=scope_drift` for wrong seam selection, unjustified off-primary expansion, and bounded widening abuse."
        in contract_doc
    )
    assert (
        "In the critic stage, use `kind=missing_evidence` only when corroboration is actually absent."
        in contract_doc
    )
    assert "Auditor seam-review duties:" in contract_doc
    assert (
        "In the auditor stage, do not return clean acceptance while the wrong seam remains primary."
        in contract_doc
    )
    assert (
        "In the auditor stage, do not accept off-primary recommendations without justified seam expansion."
        in contract_doc
    )
    assert (
        "In the auditor stage, do not return clean acceptance when seam metadata was used to bypass bounded corroboration limits."
        in contract_doc
    )
    assert (
        "In the auditor stage, use `kind=scope_drift` for wrong seam selection, unjustified off-primary expansion, and bounded widening abuse."
        in contract_doc
    )
    assert (
        "In the auditor stage, use `kind=missing_evidence` only when corroboration is actually absent."
        in contract_doc
    )
    assert "Reviser seam-review duties:" in contract_doc
    assert (
        "In the reviser stage, return to the higher-ranked seam first."
        in contract_doc
    )
    assert (
        "In the reviser stage, when an open issue shows the current seam choice is wrong, update `primary_seam`, `secondary_seams_considered`, `recommendations[*].seam_id`, `recommendations[*].seam_expansion_reason`, `review_surface`, and evidence together."
        in contract_doc
    )
    assert (
        "In the reviser stage, preserve recommendation order where possible while rebinding to the higher-ranked seam."
        in contract_doc
    )
    assert (
        "In the reviser stage, collapse gratuitous secondary seams after rebinding instead of carrying stale seam declarations forward."
        in contract_doc
    )
    assert (
        "In the reviser stage, keep at least one recommendation bound to `primary_seam` after rebinding."
        in contract_doc
    )


def test_surface_update_notes_document_primary_deliverable_artifacts():
    notes = Path("FORGE_HARNESS_SURFACE_UPDATE_NOTES.md").read_text(encoding="utf-8")

    assert "Primary deliverable artifacts for harness runs" in notes
    assert (
        "FINAL_ANSWER.json` / `FINAL_ANSWER.md` only when the selected primary deliverable is a publishable final answer"
        in notes
    )
    assert (
        "PARTIAL_ANSWER.json` / `PARTIAL_ANSWER.md` when an eligible accepted-partial output or trust-mode fallback subset is the selected primary deliverable"
        in notes
    )
    assert (
        "BEST_DRAFT.json` / `BEST_DRAFT.md` when no shippable final or partial artifact is allowed"
        in notes
    )
    assert "`Final publication: publishable|blocked`" in notes
    assert "`Publication blockers:`" in notes
    assert "`Recommendation indices withheld from FINAL_ANSWER.*:`" in notes
    assert (
        "`analysis_review_status.publishability` is finalized after artifact projection and must agree with `final_artifact_kind`."
        in notes
    )
    assert (
        "`REPORT.md` keeps `Final publication: publishable|blocked`, `Publication blockers:`, and `Recommendation indices withheld from FINAL_ANSWER.*:`"
        in notes
    )
    assert "`Recommendation indices included in PARTIAL_ANSWER.*: 1, 2`" in notes
    assert "`Recommendation indices withheld from FINAL_ANSWER.*: 2`" in notes
    assert "`Recommendation indices excluded from PARTIAL_ANSWER.*: none`" in notes
    assert (
        "`PARTIAL_ANSWER.*` keeps `Recommendation indices included in PARTIAL_ANSWER.*: 1, 2`, `Recommendation indices withheld from FINAL_ANSWER.*: 2`, and `Recommendation indices excluded from PARTIAL_ANSWER.*: none`"
        in notes
    )
    assert "`Open topics:`" in notes
    assert "`Carried-forward topics:`" in notes


def test_draft_adr_0024_documents_slice_c_artifact_contract_without_old_two_state_wording():
    adr = Path(
        "docs/project_management/adrs/draft/ADR-0024-harness-state-and-artifact-contract.md"
    ).read_text(encoding="utf-8")

    assert "PARTIAL_ANSWER.md" in adr
    assert "PARTIAL_ANSWER.json" in adr
    assert "publishability" in adr
    assert "accepted_with_warnings" in adr
    assert "does not guarantee `FINAL_ANSWER.*`" in adr
    assert (
        "falls through to `PARTIAL_ANSWER.*` when eligible, otherwise `BEST_DRAFT.*`"
        in adr
    )
    assert "reviewer prose does not decide artifact eligibility" in adr
    assert (
        "Artifact projection finalizes `analysis_review_status.publishability`, and `final_answer_publishable` must agree with `final_artifact_kind`."
        in adr
    )
    assert "`Recommendation indices withheld from FINAL_ANSWER.*:`" in adr
    assert "Recommendation indices included in PARTIAL_ANSWER.*: 1, 2" in adr
    assert "Recommendation indices withheld from FINAL_ANSWER.*: 2" in adr
    assert "Recommendation indices excluded from PARTIAL_ANSWER.*: none" in adr
    assert (
        "`REPORT.md` freezes only final-publication / final-withholding wording" in adr
    )
    assert "`Open topics:` and `Carried-forward topics:` separate" in adr
    assert 'summary.json["artifacts"]["final_artifact"]' in adr
    assert "Accepted / accepted_with_warnings runs" not in adr
    assert "### Non-accepted runs" not in adr


def test_draft_adr_0025_documents_slice_c_artifact_fallback_without_old_two_state_wording():
    adr = Path(
        "docs/project_management/adrs/draft/ADR-0025-harness-strategy-subgraphs-and-migration-plan.md"
    ).read_text(encoding="utf-8")

    assert "PARTIAL_ANSWER.*" in adr
    assert "publishable final answer" in adr
    assert "trust final publication is blocked" in adr
    assert (
        "fall through partial-answer eligibility before writing `BEST_DRAFT.*`" in adr
    )
    assert (
        "falls through to `PARTIAL_ANSWER.*` when eligible, otherwise `BEST_DRAFT.*`"
        in adr
    )
    assert (
        "finalize `analysis_review_status.publishability` after artifact projection so it agrees with `final_artifact_kind`"
        in adr
    )
    assert "`Final publication: publishable|blocked`" in adr
    assert "`Recommendation indices withheld from FINAL_ANSWER.*:`" in adr
    assert "`REPORT.md` wording runner-owned" in adr
    assert "Recommendation indices included in PARTIAL_ANSWER.*: 1, 2" in adr
    assert "Recommendation indices withheld from FINAL_ANSWER.*: 2" in adr
    assert "Recommendation indices excluded from PARTIAL_ANSWER.*: none" in adr
    assert "`Open topics:` and `Carried-forward topics:`" in adr
    assert "write `FINAL_ANSWER.*` only for accepted runs" not in adr
    assert "otherwise write `BEST_DRAFT.*`" not in adr
    assert "Non-accepted runs produce `BEST_DRAFT.*` artifacts" not in adr
