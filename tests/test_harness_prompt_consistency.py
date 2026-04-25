from __future__ import annotations

import pytest

from anvil.harness.contracts import (
    build_analysis_review_contract,
    confidence_rubric_lines,
)
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
        }
    )


@pytest.mark.parametrize(
    (
        "strategy_kind",
        "mode",
        "trust_lines",
        "final_artifact_lines",
        "payload_line",
        "issue_line",
        "acceptance_lines",
    ),
    [
        (
            "analysis_review_bounded_v1",
            "bounded",
            [
                "Recommendation evidence refs in trust-mode analysis outputs: n/a (bounded mode)",
                "Taxonomy override reason required: False",
                "verified_evidence_refs must be a subset of evidence refs: False",
                "Non-inferred affected_files require evidence or checked-file coverage: False",
                "Payload provenance mode: none",
                "Downgrade clean acceptance when semantic warnings remain: False",
                "Downgrade inference-backed acceptance to caveated acceptance: False",
                "Late auditor medium-or-higher issue policy: error",
            ],
            [],
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
                "Recommendation evidence refs in trust-mode analysis outputs: uncapped",
                "Taxonomy override reason required: True",
                "verified_evidence_refs must be a subset of evidence refs: True",
                "Non-inferred affected_files require evidence or checked-file coverage: True",
                "Payload provenance mode: payload_hash_and_refs",
                "Downgrade clean acceptance when semantic warnings remain: True",
                "Downgrade inference-backed acceptance to caveated acceptance: True",
                "Late auditor medium-or-higher issue policy: warn",
            ],
            [
                "Final-artifact eligibility is runner-owned in trust mode: only accept verdicts with non-inferred grounding and no runner-known per-index topic blocker are clean final-answer candidates.",
                "accept_with_caveat and inferred acceptance remain partial-only considerations, and you should not add any extra payload field to encode that.",
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
    final_artifact_lines: list[str],
    payload_line: str,
    issue_line: str,
    acceptance_lines: list[str],
):
    task = _task()
    strategy = _strategy(strategy_kind)
    contract = build_analysis_review_contract(task, strategy)

    proposer = build_analysis_proposer_prompt(
        task, strategy.prompt_preamble, _GIT_SNAPSHOT, contract
    )
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
        issue_ledger=[
            {
                "issue_id": "AR-001",
                "title": "Example issue",
                "resolution_status": "open",
            }
        ],
        topic_ledger=[
            {
                "topic_id": "TOPIC-001",
                "title": "Example topic",
                "resolution_status": "open",
            }
        ],
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
        open_issues=[
            {"issue_id": "AR-001", "severity": "medium", "title": "Example issue"}
        ],
        open_topics=[
            {"topic_id": "TOPIC-001", "severity": "medium", "title": "Example topic"}
        ],
    )

    common_bounded_lines = [
        "Analysis-review contract: analysis_review_v1_contract_v9",
        f"Effective strategy kind: {strategy_kind}",
        f"Mode: {mode}",
        "Bounded review policy:",
        "Bounded-mode recommendation evidence refs: 1..3 per recommendation",
        "review_surface.must_check_files: 1..3 per recommendation",
        "review_surface.optional_check_files: 0..2 per recommendation",
        "Evidence cap policy: trim_to_cap",
        "review_surface.must_check_files must be a subset of files_reviewed",
        "Critic issue cap: 5",
        "Critic new-topic cap: 2",
        "Auditor new medium-or-higher issue cap after round 0: 1",
        "Scope escapes require non-empty reasons: True",
    ]
    shared_seam_lines = [
        "Seam selection guidance:",
        "Use `primary_seam` as the canonical run-context seam.",
        "Exhaust the primary seam before expanding; use `secondary_seams_considered` only for seams you actually declared or inspected beyond the primary seam.",
        "Bind every recommendation with `recommendations[*].seam_id`; when that seam expands beyond the primary seam, populate `recommendations[*].seam_expansion_reason`.",
        "default bounded cap is 2; declaring or inspecting a third secondary seam requires a recorded scope_escape; overflow is never silently normalized away.",
    ]
    seam_role_lines = {
        "proposer": "In the proposer draft, you may declare or inspect a third bounded secondary seam only when `scope_escapes` records every third-seam path with a non-empty reason.",
        "reviser": "In the reviser stage, you may retain or introduce a third bounded secondary seam only when `scope_escapes` records every third-seam path with a non-empty reason.",
        "critic": "In the critic stage, treat a third bounded secondary seam without matching `scope_escapes` as a bounded-mode scope violation.",
        "auditor": "In the auditor stage, do not call the draft cleanly closed when a third bounded secondary seam lacks matching `scope_escapes`.",
    }

    for line in common_bounded_lines:
        assert line in proposer
        assert line in critic
        assert line in auditor
        assert line in reviser

    for line in shared_seam_lines:
        assert line in proposer
        assert line in critic
        assert line in auditor
        assert line in reviser
    assert seam_role_lines["proposer"] in proposer
    assert seam_role_lines["reviser"] in reviser
    assert seam_role_lines["critic"] in critic
    assert seam_role_lines["auditor"] in auditor

    for prompt in (proposer, critic, auditor, reviser):
        assert (
            prompt.index("Bounded review policy:")
            < prompt.index("Seam selection guidance:")
            < prompt.index("Repo-local discovery guidance:")
        )

    for line in trust_lines:
        assert line in proposer
        assert line in critic
        assert line in auditor
        assert line in reviser

    shared_discovery_lines = [
        "Repo-local discovery guidance:",
        "Treat `files_hint`, when provided, as a starting slice, not the total review universe.",
        "For requirement, policy, or spec claims, inspect and cite the nearest governing repo-local doc or manifest.",
        "For parity, symmetry, or sibling-workflow claims, inspect and cite the sibling implementation or workflow that establishes the baseline, and compare the full like-for-like seam rather than one convenient step.",
        "Include corroborating files in `files_reviewed`, `evidence`, and `review_surface`.",
    ]
    bounded_discovery_tail_lines = [
        "In bounded mode, one-hop repo-local corroboration outside `files_hint` is allowed when it is needed to support a recommendation.",
        "Keep corroboration inside the current bounded caps: evidence <= 3 refs, review_surface.must_check_files <= 3, review_surface.optional_check_files <= 2.",
        "Use `review_surface.must_check_files` for directly governing corroboration and `review_surface.optional_check_files` for supporting corroboration.",
        "Use analysis-stage `scope_escapes` only for the exact third-secondary-seam overflow path in bounded mode; otherwise reserve `scope_escapes` for later review work that truly leaves the declared `review_surface`.",
    ]
    bounded_role_lines = {
        "proposer": "In the proposer draft, do not leave governing or sibling corroboration for later stages; pull the needed repo-local file into `files_reviewed`, `evidence`, and `review_surface` now.",
        "critic": "In the critic stage, flag missing repo-local corroboration when a requirement/spec or parity claim lacks its governing or sibling file in `files_reviewed`, `evidence`, or `review_surface`.",
        "reviser": "In the reviser stage, repair missing corroboration by widening `review_surface` within cap before inventing new recommendations.",
        "auditor": "In the auditor stage, do not call the draft cleanly closed while a spec-backed or parity-backed claim still lacks the needed governing or sibling corroborating file.",
    }
    trust_discovery_tail_lines = [
        "In trust mode, repo-local discovery still starts from the same governing or sibling seam before any downstream admissibility or publication split.",
        "Keep trust corroboration uncapped and complete; record every corroborating file in `files_reviewed`, `evidence`, and `review_surface`.",
        "When both exist, prefer nearer governing/spec/workflow evidence over farther plan/runbook prose.",
    ]
    trust_discovery_role_lines = {
        "proposer": "In the proposer draft, start from the nearer governing or sibling repo-local seam and do not lean on farther plan/runbook prose when the governing spec, manifest, or workflow already exists in-repo.",
        "critic": "In the critic stage, flag recommendations that cite farther plan/runbook prose while skipping nearer governing or sibling repo-local evidence.",
        "reviser": "In the reviser stage, repair discovery gaps by adding the nearer governing or sibling repo-local seam before preserving broader plan/runbook prose.",
        "auditor": "In the auditor stage, do not call the draft cleanly closed while nearer governing/spec/workflow evidence is missing or replaced by farther plan/runbook prose.",
    }
    trust_atomicity_lines = [
        "Trust recommendation atomicity:",
        "In trust mode, recommendations must be atomic by admissibility boundary.",
        "emit it as its own recommendation instead of bundling it with weaker optional hardening.",
        'Reserve `grounding_mode="mixed"` for truly inseparable single-action recommendations, not convenient bundling of a direct half and an inferred half.',
    ]

    for line in shared_discovery_lines:
        assert line in proposer
        assert line in critic
        assert line in auditor
        assert line in reviser

    if mode == "trust":
        for line in trust_discovery_tail_lines:
            assert line in proposer
            assert line in critic
            assert line in auditor
            assert line in reviser
        assert trust_discovery_role_lines["proposer"] in proposer
        assert trust_discovery_role_lines["critic"] in critic
        assert trust_discovery_role_lines["reviser"] in reviser
        assert trust_discovery_role_lines["auditor"] in auditor

        for line in final_artifact_lines:
            assert line in proposer
            assert line in critic
            assert line in auditor
            assert line in reviser
        for line in trust_atomicity_lines:
            assert line in proposer
            assert line in critic
            assert line in auditor
            assert line in reviser
        assert (
            "Split a directly grounded or spec-backed action from optional inference-backed or parity hardening when they are independently actionable."
            in proposer
        )
        assert (
            "raise `kind=insufficient_specificity` with `blocking_class=actionability` and require a split."
            in critic
        )
        assert (
            "Do not use `missing_evidence` for bundling unless the problem is actually absent corroboration."
            in critic
        )
        assert (
            "When splitting one recommendation into two, keep the directly grounded action in the original recommendation slot when possible."
            in reviser
        )
        assert (
            "Make the weaker hardening guidance the new adjacent recommendation rather than reshuffling unrelated recommendation order."
            in reviser
        )
        assert (
            "Do not return clean acceptance while an avoidable mixed-grounding bundle remains."
            in auditor
        )
        assert (
            "If the bundle is still present, leave that recommendation unresolved and force revision rather than treating a caveat as sufficient closure."
            in auditor
        )
    else:
        assert (
            "Final-artifact eligibility is runner-owned in trust mode" not in proposer
        )
        assert "Final-artifact eligibility is runner-owned in trust mode" not in critic
        assert "Final-artifact eligibility is runner-owned in trust mode" not in auditor
        assert "Final-artifact eligibility is runner-owned in trust mode" not in reviser
        assert "partial-only considerations" not in proposer
        assert "partial-only considerations" not in critic
        assert "partial-only considerations" not in auditor
        assert "partial-only considerations" not in reviser
        for line in trust_discovery_tail_lines:
            assert line not in proposer
            assert line not in critic
            assert line not in auditor
            assert line not in reviser
        for line in trust_discovery_role_lines.values():
            assert line not in proposer
            assert line not in critic
            assert line not in auditor
            assert line not in reviser
        assert "Trust recommendation atomicity:" not in proposer
        assert "Trust recommendation atomicity:" not in critic
        assert "Trust recommendation atomicity:" not in auditor
        assert "Trust recommendation atomicity:" not in reviser

    if mode == "bounded":
        for line in bounded_discovery_tail_lines:
            assert line in proposer
            assert line in critic
            assert line in auditor
            assert line in reviser
        assert bounded_role_lines["proposer"] in proposer
        assert bounded_role_lines["critic"] in critic
        assert bounded_role_lines["reviser"] in reviser
        assert bounded_role_lines["auditor"] in auditor
    else:
        for line in bounded_discovery_tail_lines:
            assert line not in proposer
            assert line not in critic
            assert line not in auditor
            assert line not in reviser
        for line in bounded_role_lines.values():
            assert line not in proposer
            assert line not in critic
            assert line not in auditor
            assert line not in reviser

    assert "Minimum accepted recommendations for partial acceptance: 2" in critic
    assert "Create stable issue IDs such as AR-001" in critic
    assert "Validate each recommendation's cited evidence first" in critic
    assert (
        "Record `scope_escapes` whenever you inspect files outside the declared review_surface"
        in critic
    )
    assert "Recommendation review coverage:" in critic
    assert (
        "Use `topics` only for genuinely new bounded-review topics introduced by this review stage"
        in critic
    )
    assert (
        "Emit each new topic as a structured record with `topic_id`, `severity`, `title`, `evidence`, `repair_hint`, and `recommendation_index`."
        in critic
    )
    assert (
        "Use `resolved_topic_ids`, `carried_forward_topic_ids`, and `waived_topic_ids` only to classify prior open topics."
        in critic
    )
    assert (
        "Populate `files_reviewed` with the concrete workspace files you inspected during this review stage."
        in critic
    )
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
    assert (
        "For every previously open topic, you must explicitly classify it as resolved, carried_forward, or waived"
        in auditor
    )
    assert "Preserve topic IDs for carried-forward or waived prior topics" in auditor
    assert (
        "Populate `files_reviewed` with the concrete workspace files you inspected during this audit stage."
        in auditor
    )
    assert (
        "If you introduce any new medium-or-higher issue after round 0, include `why_not_raised_earlier`."
        in auditor
    )
    assert "Recommendation review coverage:" in auditor
    assert "The prior analysis contains 3 recommendation(s)." in auditor
    assert "3. Document operator rollback" in auditor
    assert "close all open medium-or-higher blockers" in reviser
    assert "Return an `issue_resolution_map` entry for every open issue ID" in reviser
    assert "return a `topic_resolution_map` entry for every open topic ID" in reviser
    assert (
        "Use `topic_resolution_map` to classify prior open topics. Do not emit `topics` from the reviser stage."
        in reviser
    )
    assert (
        "Populate strengths and uncertainties as objects with `items` and `none_reason`"
        in proposer
    )
    assert (
        'For strengths/uncertainties: when you have concrete items, put them in `items` and set `none_reason` to `""`; use a non-empty `none_reason` only when `items` is empty.'
        in proposer
    )
    assert (
        "Every evidence ref must be a concrete path-only workspace path you inspected in this run, so every evidence ref must also appear in files_reviewed."
        in proposer
    )
    assert "Do not cite evidence as `path:line-range`" in proposer
    assert (
        "If multiple excerpts come from one file, cite the file once and put line-specific detail in rationale or scope_note."
        in proposer
    )
    assert (
        "Every recommendation uses the same payload family in both modes." in proposer
    )
    assert "Every recommendation uses the same payload family in both modes." in reviser
    if mode == "trust":
        assert (
            "Keep each recommendation scoped: include review_surface.must_check_files, optional_check_files, and a scope_note, and retain every concrete evidence ref needed for audit completeness."
            in proposer
        )
        assert (
            "recommendation evidence is uncapped; include every concrete workspace ref needed to preserve audit completeness."
            in proposer
        )
    else:
        assert (
            "Keep each recommendation bounded: include review_surface.must_check_files, optional_check_files, and a scope_note, and keep evidence within the bounded-review cap."
            in proposer
        )
        assert "keep recommendation evidence within the bounded-review cap." in proposer
    assert (
        'Update strengths and uncertainties using the same `items` plus `none_reason` section shape required by the schema: when a section has concrete items, put them in `items` and set `none_reason` to `""`; use a non-empty `none_reason` only when `items` is empty.'
        in reviser
    )
    if mode == "trust":
        assert (
            "Preserve each recommendation's evidence list and review_surface unless an open issue or open topic requires changing them; do not drop concrete evidence refs just to match a bounded cap."
            in reviser
        )
    else:
        assert (
            "Preserve each recommendation's bounded evidence list and review_surface unless an open issue or open topic requires changing them."
            in reviser
        )
    assert (
        "Every evidence ref must stay a concrete path-only workspace path you inspected in this run, so every evidence ref must also appear in files_reviewed."
        in reviser
    )
    assert "Do not cite evidence as `path:line-range`" in reviser
    if mode == "trust":
        assert (
            "Keep each recommendation's evidence list complete for trust-mode auditability; do not trim concrete evidence refs to the bounded-review cap."
            in reviser
        )
        assert (
            "within the bounded-review cap unless the contract explicitly allows more"
            not in reviser
        )
    else:
        assert (
            "Keep each recommendation's evidence list within the bounded-review cap unless the contract explicitly allows more."
            in reviser
        )
    assert payload_line in proposer
    assert payload_line in reviser
    assert issue_line in critic
    for prompt in (proposer, critic, auditor, reviser):
        assert "FINAL_ANSWER" not in prompt
        assert "publication-ready" not in prompt
        assert "ready to publish" not in prompt
        assert "final artifact" not in prompt.lower()

    if mode == "trust":
        assert (
            "In trust mode, every concrete recommendation_reviews verdict must carry its own checked_files or verified_evidence_refs."
            in critic
        )
        assert (
            "In trust mode, recommendation-linked closures must map to the covered recommendation review, and recommendation_index=null closures must map to the matching issue_closure_reviews/topic_closure_reviews entry."
            in critic
        )
        assert (
            "Use `recommendation_reviews` to prove recommendation-linked closures, and use `issue_closure_reviews` / `topic_closure_reviews` only for global closures where `recommendation_index` is null."
            in critic
        )
        assert (
            "In trust mode, every concrete recommendation_reviews verdict must carry its own checked_files or verified_evidence_refs."
            in auditor
        )
        assert (
            "In trust mode, recommendation-linked closures must map to the covered recommendation review, and recommendation_index=null closures must map to the matching issue_closure_reviews/topic_closure_reviews entry."
            in auditor
        )
        assert (
            "Use `recommendation_reviews` to prove recommendation-linked closures, and use `issue_closure_reviews` / `topic_closure_reviews` only for global closures where `recommendation_index` is null."
            in auditor
        )
        assert "files_reviewed is review context, not proof by itself." in critic
        assert "files_reviewed is review context, not proof by itself." in auditor
    else:
        assert (
            "In bounded mode, still keep these refs concrete and scoped to the exact recommendation, issue, or topic they support."
            in critic
        )
        assert (
            "In bounded mode, still keep these refs concrete and scoped to the exact recommendation, issue, or topic they support."
            in auditor
        )
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
