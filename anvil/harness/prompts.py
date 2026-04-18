from __future__ import annotations

import json
from typing import Any, Iterable

from .contracts import (
    GROUNDING_MODE_VALUES,
    ISSUE_KIND_DEFAULT_BLOCKING_CLASS,
    AnalysisReviewContract,
    confidence_rubric_lines,
)
from .git_utils import render_git_snapshot
from .types import ReviewLoopPolicy, TaskSpec, ValidationRun, WorkspaceWritePolicy

MAX_BLOCK_CHARS = 5000


def _bullets(items: Iterable[str]) -> str:
    values = [str(x).strip() for x in items if str(x).strip()]
    if not values:
        return "- none"
    return "\n".join(f"- {v}" for v in values)


def _clip(text: str, max_chars: int = MAX_BLOCK_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars // 2] + "\n...[truncated]...\n" + text[-max_chars // 2 :]


def _workspace_policy_block(policy: WorkspaceWritePolicy) -> str:
    mode_guidance = {
        "forbid": (
            "This task is analysis-only for the target workspace. Do not modify target-workspace files. "
            "Return recommendations or analysis only."
        ),
        "allow": (
            "Target-workspace writes are allowed only if they stay within the declared policy bounds. "
            "Prefer the smallest possible patch surface."
        ),
        "require": (
            "A target-workspace patch is expected for this task, but it must stay within the declared policy bounds."
        ),
    }[policy.mode]
    parts = [
        f"Mode: {policy.mode}",
        f"Allowed paths: {_bullets(policy.allowed_paths)}",
        f"Denied paths: {_bullets(policy.denied_paths)}",
        f"Allow untracked files: {policy.allow_untracked}",
        f"Allow renames: {policy.allow_renames}",
        f"Allow deletions: {policy.allow_deletions}",
        f"Max touched files: {policy.max_touched_files if policy.max_touched_files is not None else 'unlimited'}",
        f"Require clean start: {policy.require_clean_start}",
        mode_guidance,
        "This task-level workspace write policy overrides any broader stage tool permissions.",
    ]
    return "Workspace write policy:\n" + "\n".join(parts)


def _review_requirements_block(task: TaskSpec) -> str:
    req = task.review_requirements
    items: list[str] = [f"Task kind: {task.task_kind}"]
    if task.task_kind == "analysis_review":
        items.extend(
            [
                f"Require evidence per recommendation: {req.require_evidence_per_recommendation}",
                f"Require classification per recommendation: {req.require_classification}",
                f"Require priority per recommendation: {req.require_priority}",
                f"Minimum recommendations: {req.min_recommendations}",
                "Use the labels confirmed_issue, risk, and recommendation carefully.",
                "If evidence is ambiguous, downgrade the claim rather than overstating certainty.",
            ]
        )
    return "Review requirements:\n" + "\n".join(items)


def _task_block(task: TaskSpec, prompt_preamble: str = "") -> str:
    parts = []
    if prompt_preamble.strip():
        parts.append(prompt_preamble.strip())
    parts.extend(
        [
            f"Task ID: {task.id}",
            "Objective:\n" + task.objective.strip(),
            _workspace_policy_block(task.workspace_write_policy),
            _review_requirements_block(task),
            "Acceptance criteria:\n" + _bullets(task.acceptance),
            "Constraints:\n" + _bullets(task.constraints),
        ]
    )
    if task.context.strip():
        parts.append("Context:\n" + task.context.strip())
    if task.notes.strip():
        parts.append("Notes:\n" + task.notes.strip())
    if task.files_hint:
        parts.append("Files to prioritize:\n" + _bullets(task.files_hint))
    if task.prompt_addendum.strip():
        parts.append("Prompt addendum:\n" + task.prompt_addendum.strip())
    return "\n\n".join(parts)


def _validator_block(validation_runs: list[ValidationRun]) -> str:
    if not validation_runs:
        return "No external validators were configured or applicable."

    rendered: list[str] = []
    for run in validation_runs:
        body = [
            f"Validator: {run.name}",
            f"Required: {run.required}",
            f"Command: {run.command}",
            f"Status: {run.status}",
            f"Applicable: {run.applicable}",
            f"Exit code: {run.exit_code if run.exit_code is not None else 'n/a'}",
        ]
        if run.skip_reason:
            body.append("Reason:\n" + run.skip_reason)
        if run.missing_paths:
            body.append("Missing paths:\n" + _bullets(run.missing_paths))
        if run.missing_binaries:
            body.append("Missing binaries:\n" + _bullets(run.missing_binaries))
        if run.stdout_tail.strip():
            body.append("stdout tail:\n" + _clip(run.stdout_tail))
        if run.stderr_tail.strip():
            body.append("stderr tail:\n" + _clip(run.stderr_tail))
        if run.error:
            body.append("Error:\n" + run.error)
        rendered.append("\n".join(body))
    return "\n\n---\n\n".join(rendered)


def _json_block(title: str, payload: dict | list | None) -> str:
    if payload in (None, {}, []):
        return f"{title}: none"
    return f"{title}:\n{_clip(json.dumps(payload, indent=2, sort_keys=False))}"


def _recommendation_review_coverage_block(prior_output: dict | None) -> str:
    recommendations: list[dict[str, Any]] = []
    if isinstance(prior_output, dict):
        raw_recommendations = prior_output.get("recommendations")
        if isinstance(raw_recommendations, list):
            recommendations = [item for item in raw_recommendations if isinstance(item, dict)]
    if not recommendations:
        return (
            "Recommendation review coverage:\n"
            "- If the prior analysis includes recommendations, return exactly one "
            "`recommendation_reviews` item per recommendation index."
        )

    lines = [
        "Recommendation review coverage:",
        (
            "- The prior analysis contains "
            f"{len(recommendations)} recommendation(s). Return exactly one "
            "`recommendation_reviews` item for each recommendation index below."
        ),
        "- Do not omit acceptable recommendations. Use verdict=accept or accept_with_caveat when appropriate.",
        "- Keep the indices aligned with this checklist:",
    ]
    for index, item in enumerate(recommendations, start=1):
        title = str(item.get("title") or "").strip() or "(untitled recommendation)"
        lines.append(f"{index}. {title}")
    return "\n".join(lines)


def _review_policy_block(review_policy: ReviewLoopPolicy) -> str:
    return "\n".join(
        [
            "Review stop policy:",
            f"- min_loops: {review_policy.min_loops}",
            f"- max_loops: {review_policy.max_loops}",
            f"- always_run_first_revision: {review_policy.always_run_first_revision}",
            f"- max_open_medium_issues: {review_policy.max_open_medium_issues}",
            f"- min_grounding_score: {review_policy.min_grounding_score}",
            f"- min_actionability_score: {review_policy.min_actionability_score}",
            f"- min_scope_compliance_score: {review_policy.min_scope_compliance_score}",
        ]
    )


def _confidence_rubric_block(contract: AnalysisReviewContract) -> str:
    lines = [
        f"Confidence rubric ({contract.confidence_rubric_version}):",
        *[f"- {line}" for line in confidence_rubric_lines()],
        "Use the same rubric for generating recommendations and for judging whether confidence is too high or too low.",
    ]
    return "\n".join(lines)


def _analysis_contract_block(contract: AnalysisReviewContract) -> str:
    partial = contract.partial_acceptance
    required_sections = contract.required_sections
    return "\n".join(
        [
            f"Analysis-review contract: {contract.contract_version}",
            f"- Effective strategy kind: {contract.strategy_kind}",
            f"- Mode: {contract.mode}",
            f"- Reviser goal: {contract.reviser_goal}",
            f"- Require issue ledger: {contract.require_issue_ledger}",
            f"- Require recommendation reviews: {contract.require_recommendation_reviews}",
            f"- Partial acceptance enabled: {partial.enabled}",
            f"- Minimum accepted recommendations for partial acceptance: {partial.min_accepted_recommendations}",
            f"- Allow localized medium non-correctness issues for partial acceptance: {partial.allow_localized_medium_non_correctness_issues}",
            f"- Forbid correctness blockers on accepted recommendations: {partial.forbid_correctness_blockers_on_accepted_recommendations}",
            f"- Strengths required: {required_sections.strengths_required}",
            f"- Uncertainties required: {required_sections.uncertainties_required}",
            f"- Empty section rationale allowed: {required_sections.none_reason_allowed}",
            f"- Minimum items when a section is populated: {required_sections.min_items_when_populated}",
            f"- Minimum files_reviewed entries: {required_sections.minimum_files_reviewed}",
        ]
    )


def _trust_review_policy_block(contract: AnalysisReviewContract) -> str:
    trust = contract.trust_review
    return "\n".join(
        [
            "Trust review policy:",
            f"- Taxonomy override reason required: {trust.require_taxonomy_override_reason}",
            (
                "- verified_evidence_refs must be a subset of evidence refs: "
                f"{trust.require_verified_evidence_refs_subset}"
            ),
            (
                "- Non-inferred affected_files require evidence or checked-file coverage: "
                f"{trust.require_affected_file_coverage}"
            ),
            f"- Payload provenance mode: {trust.payload_provenance_mode}",
            (
                "- Downgrade clean acceptance when semantic warnings remain: "
                f"{trust.downgrade_on_semantic_warnings}"
            ),
            (
                "- Downgrade inference-backed acceptance to caveated acceptance: "
                f"{trust.downgrade_on_inferred_acceptance}"
            ),
            (
                "- Late auditor medium-or-higher issue policy: "
                f"{trust.late_auditor_medium_or_higher_policy}"
            ),
        ]
    )


def _bounded_review_policy_block(contract: AnalysisReviewContract) -> str:
    bounded = contract.bounded_review
    return "\n".join(
        [
            "Bounded review policy:",
            (
                "- Recommendation evidence refs: "
                f"1..{bounded.max_evidence_refs_per_recommendation} per recommendation"
            ),
            (
                "- review_surface.must_check_files: "
                f"1..{bounded.max_must_check_files_per_recommendation} per recommendation"
            ),
            (
                "- review_surface.optional_check_files: "
                f"0..{bounded.max_optional_check_files_per_recommendation} per recommendation"
            ),
            f"- Evidence cap policy: {bounded.evidence_cap_policy}",
            "- review_surface.must_check_files must be a subset of files_reviewed",
            f"- Critic issue cap: {bounded.critic_issue_cap}",
            f"- Critic new-topic cap: {bounded.critic_new_topic_cap}",
            (
                "- Auditor new medium-or-higher issue cap after round 0: "
                f"{bounded.auditor_new_medium_or_higher_issue_cap_after_round0}"
            ),
            (
                "- Scope escapes require non-empty reasons: "
                f"{bounded.require_scope_escape_justification}"
            ),
        ]
    )


def _recommendation_payload_block(contract: AnalysisReviewContract) -> str:
    grounding_modes = ", ".join(GROUNDING_MODE_VALUES)
    trust = contract.trust_review
    lines = [
        "Recommendation payload fields:",
        "- Every recommendation uses the same payload family in both modes.",
        "- Always populate classification, priority, rationale, evidence, proposed_change, confidence, and review_surface.",
        "- Evidence refs must be path-only workspace refs. Do not append line numbers or line ranges such as path:12-18.",
        "- If multiple excerpts come from one file, cite the file once and put line-specific detail in rationale or scope_note.",
        f"- grounding_mode, when present, must be one of: {grounding_modes}.",
        "- checked_files should list the concrete files you personally inspected to verify the recommendation.",
        "- affected_files should name the concrete files the recommendation says are affected.",
    ]
    if trust.require_verified_evidence_refs_subset:
        lines.append(
            "- In this mode, populate verified_evidence_refs with the evidence refs you directly re-checked; keep it a subset of evidence."
        )
    else:
        lines.append(
            "- verified_evidence_refs is optional advisory metadata in this mode; keep it a subset of evidence when you provide it."
        )
    if trust.require_affected_file_coverage:
        lines.append(
            "- In this mode, non-inferred affected_files should be backed by evidence refs or checked_files."
        )
    else:
        lines.append(
            "- In this mode, affected_files and checked_files are optional scoping metadata rather than strict trust requirements."
        )
    return "\n".join(lines)


def _issue_taxonomy_block(contract: AnalysisReviewContract) -> str:
    trust = contract.trust_review
    defaults = ", ".join(
        f"{kind}={blocking_class}"
        for kind, blocking_class in ISSUE_KIND_DEFAULT_BLOCKING_CLASS.items()
    )
    lines = [
        "Issue taxonomy guidance:",
        f"- Default blocking_class by issue kind: {defaults}.",
    ]
    if trust.require_taxonomy_override_reason:
        lines.append(
            "- If you intentionally override the default blocking_class for a kind, include blocking_class_override_reason with concrete justification."
        )
    else:
        lines.append(
            "- blocking_class_override_reason is optional context when you intentionally override the default blocking_class."
        )
    return "\n".join(lines)


def _mode_acceptance_guidance_block(contract: AnalysisReviewContract) -> str:
    trust = contract.trust_review
    lines = ["Mode-specific acceptance guidance:"]
    if trust.downgrade_on_inferred_acceptance:
        lines.append(
            "- In this mode, inference-heavy recommendations should usually receive accept_with_caveat instead of clean accept."
        )
    else:
        lines.append(
            "- In this mode, clean accept is allowed without the extra trust downgrade rules."
        )
    if trust.downgrade_on_semantic_warnings:
        lines.append(
            "- In this mode, unresolved semantic warnings are treated as caveats, not clean acceptance."
        )
    else:
        lines.append(
            "- In this mode, semantic warning handling follows the standard bounded-review flow."
        )
    return "\n".join(lines)


def build_single_pass_prompt(task: TaskSpec, prompt_preamble: str, git_snapshot: dict) -> str:
    return f"""
You are the SOLVER stage in an external evaluation harness.

Your job:
1. Inspect the current workspace directly.
2. If your effective tool permissions and the task-level workspace policy allow it, make the smallest changes needed to satisfy the task.
3. Prefer narrow, reversible edits.
4. Do not refactor unrelated code or rewrite large areas without strong evidence.
5. Base every claim on what you actually observed.
6. Return ONLY the JSON object required by the schema. Do not wrap it in Markdown.

When helpful, set workspace_write_intent to `none` or `repo_patch` to match what you actually did.

{_task_block(task, prompt_preamble)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_proposer_prompt(task: TaskSpec, prompt_preamble: str, git_snapshot: dict) -> str:
    return f"""
You are the PROPOSER stage in a proposer/falsifier/patcher harness.

Your job:
1. Inspect the current workspace directly.
2. If your effective tool permissions and the task-level workspace policy allow it, implement the smallest plausible fix or improvement for the task.
3. Keep the patch as local and reversible as possible.
4. Avoid unrelated cleanup.
5. When finished, return ONLY the JSON object required by the schema.

Extra guidance:
- Record concrete claims that can be externally checked.
- If you are uncertain, say so in known_risks instead of hiding it.
- If you cannot finish safely, return status=partial or blocked.
- When helpful, set workspace_write_intent to `none` or `repo_patch` to match what you actually did.

{_task_block(task, prompt_preamble)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_falsifier_prompt(
    task: TaskSpec,
    prompt_preamble: str,
    prior_output: dict | None,
    validation_runs: list[ValidationRun],
    git_snapshot: dict,
) -> str:
    return f"""
You are the FALSIFIER stage in a proposer/falsifier/patcher harness.

Critical rules:
- Do NOT edit files in this stage.
- Check whether the current workspace state complies with the task-level workspace write policy.

Your job:
1. Inspect the current workspace directly.
2. Treat the prior attempt as suspect until proven otherwise.
3. Find the strongest concrete reasons to reject it.
4. Prefer evidence from the workspace and validator outputs over speculation.
5. If everything looks solid, return verdict=accept.
6. Return ONLY the JSON object required by the schema.

Focus on:
- acceptance criteria that are not actually satisfied
- hidden regressions
- over-broad or unnecessary changes
- unsupported claims
- missing validation steps that still matter
- workspace-write-policy violations or suspicious file changes

{_task_block(task, prompt_preamble)}

{_json_block('Prior attempt structured output', prior_output)}

Validator results:
{_validator_block(validation_runs)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_patcher_prompt(
    task: TaskSpec,
    prompt_preamble: str,
    proposer_output: dict | None,
    falsifier_output: dict | None,
    validation_runs: list[ValidationRun],
    git_snapshot: dict,
    repair_round: int,
) -> str:
    return f"""
You are the PATCHER stage in a proposer/falsifier/patcher harness.

Your job:
1. Inspect the current workspace directly.
2. Make the smallest concrete edits needed to resolve the failures below.
3. Prioritize required validator failures first.
4. Then address falsifier issues that include concrete evidence.
5. Ignore speculative nice-to-have changes.
6. Return ONLY the JSON object required by the schema.

Scope rules:
- The task-level workspace write policy is a hard limit on what you may change.
- Do not widen the patch unless it is necessary to fix a confirmed issue.
- Prefer minimal, local changes.
- If no change is needed, return status=no_change_needed.
- When helpful, set workspace_write_intent to `none` or `repo_patch` to match what you actually did.

Repair round: {repair_round}

{_task_block(task, prompt_preamble)}

{_json_block('Original proposer structured output', proposer_output)}

{_json_block('Falsifier structured output', falsifier_output)}

Validator results:
{_validator_block(validation_runs)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_analysis_proposer_prompt(
    task: TaskSpec,
    prompt_preamble: str,
    git_snapshot: dict,
    contract: AnalysisReviewContract,
) -> str:
    return f"""
You are the PROPOSER stage in an analysis-review harness.

Critical rules:
- This task is primarily about analysis, feedback, and recommendations.
- Do not modify files unless your effective permissions and the task-level workspace policy explicitly allow it.
- Base every recommendation on concrete observations from the current workspace.
- Return ONLY the JSON object required by the schema.

Your job:
1. Inspect the target workspace directly, prioritizing the files that appear most relevant.
2. Produce a short list of the most important recommendations.
3. For every recommendation, include classification, priority, evidence, and a concrete proposed change.
4. Distinguish carefully among confirmed_issue, risk, and recommendation.
5. Use the shared confidence rubric below. High confidence is appropriate for direct workspace evidence; lower confidence is appropriate for partial inference.
6. Populate strengths and uncertainties as objects with `items` and `none_reason`.
7. For strengths/uncertainties: include concrete items when you have them; otherwise leave `items` empty and explain why in `none_reason`.
8. Populate files_reviewed with the concrete workspace paths you actually inspected in this run.
9. Every evidence ref must be a concrete path-only workspace path you inspected in this run, so every evidence ref must also appear in files_reviewed.
10. Do not cite evidence as `path:line-range`; if line detail matters, put it in rationale or scope_note while citing the file path once.
11. Keep each recommendation bounded: include review_surface.must_check_files, optional_check_files, and a scope_note, and keep evidence within the bounded-review cap.
12. Keep the recommendation payload on the shared JSON family; in trust mode that includes deliberate use of grounding_mode, verified_evidence_refs, checked_files, and affected_files.
13. Use workspace_write_intent=`none` unless you truly changed the repo.

{_analysis_contract_block(contract)}
{_bounded_review_policy_block(contract)}
{_trust_review_policy_block(contract)}
{_recommendation_payload_block(contract)}
{_confidence_rubric_block(contract)}

{_task_block(task, prompt_preamble)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_analysis_critic_prompt(
    task: TaskSpec,
    prompt_preamble: str,
    prior_output: dict | None,
    validation_runs: list[ValidationRun],
    git_snapshot: dict,
    review_policy: ReviewLoopPolicy,
    contract: AnalysisReviewContract,
) -> str:
    return f"""
You are the CRITIC stage in an analysis-review harness.

Critical rules:
- Do NOT edit files in this stage.
- Perform the first structured review pass on the proposer draft.
- Create stable issue IDs such as AR-001, AR-002, and keep them deterministic within this review.
- Return ONLY the JSON object required by the schema.

Your job:
1. Audit the prior analysis for factual grounding, overclaims, omissions, actionability, and scope discipline.
2. Validate each recommendation's cited evidence first, then stay inside its review_surface unless you must leave it.
3. For every issue you raise, classify both `kind` and `blocking_class`, and follow the contract rule for blocking_class_override_reason when you override the default taxonomy mapping.
4. Review every recommendation individually and return recommendation-level verdicts.
5. Use `missing_topics` only for genuinely new bounded-review topics, not for open-ended repo exploration.
6. Record `scope_escapes` whenever you inspect files outside the declared review_surface, and give each escape a non-empty reason.
7. Use the shared confidence rubric below when judging whether confidence is too high or too low.

Decision guidance:
- Return verdict=revise when the overall draft still needs more work.
- Return verdict=reject only for severe, fundamental problems.
- Return verdict=accept only when the entire draft is sound.
- Return verdict=accept_partial when at least one recommendation is sound but the whole draft is not yet fully acceptable.

{_analysis_contract_block(contract)}
{_bounded_review_policy_block(contract)}
{_trust_review_policy_block(contract)}
{_issue_taxonomy_block(contract)}
{_mode_acceptance_guidance_block(contract)}
{_review_policy_block(review_policy)}
{_confidence_rubric_block(contract)}
{_recommendation_review_coverage_block(prior_output)}

{_task_block(task, prompt_preamble)}

{_json_block('Prior analysis structured output', prior_output)}

Validator and advisory results:
{_validator_block(validation_runs)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_analysis_auditor_prompt(
    task: TaskSpec,
    prompt_preamble: str,
    prior_output: dict | None,
    reviser_output: dict | None,
    validation_runs: list[ValidationRun],
    git_snapshot: dict,
    review_policy: ReviewLoopPolicy,
    contract: AnalysisReviewContract,
    issue_ledger: list[dict[str, Any]],
    round_index: int,
) -> str:
    return f"""
You are the AUDITOR stage in an analysis-review harness.

Critical rules:
- Do NOT edit files in this stage.
- You are not starting from scratch. Your first job is to verify closure of the existing issue ledger.
- For every previously open issue, you must explicitly classify it as resolved, carried_forward, or waived via the required issue-ID arrays.
- If you introduce any new medium-or-higher issue after round 0, include `why_not_raised_earlier`.
- Return ONLY the JSON object required by the schema.

Your job:
1. Verify whether the reviser closed the existing blocker set.
2. Preserve issue IDs for carried-forward issues.
3. Only raise a new medium-or-higher issue when it was genuinely missed earlier or created by the revision.
4. Review every recommendation individually and return recommendation-level verdicts.
5. Stay inside each recommendation's bounded review_surface unless you must leave it.
6. Record `scope_escapes` whenever you inspect files outside the bounded review surface, and give each escape a non-empty reason.
7. Follow the contract rule for blocking_class_override_reason when you override the default blocking_class for an issue kind.
8. Use `accept_partial` when a subset of recommendations is already valid even if the whole draft still needs revision.

Decision guidance:
- Return verdict=accept when the entire draft is acceptable.
- Return verdict=accept_partial when the accepted subset is usable but the whole draft is not.
- Return verdict=revise when additional work is still required.
- Return verdict=reject only for severe, fundamental problems.

Audit round: {round_index}
{_analysis_contract_block(contract)}
{_bounded_review_policy_block(contract)}
{_trust_review_policy_block(contract)}
{_issue_taxonomy_block(contract)}
{_mode_acceptance_guidance_block(contract)}
{_review_policy_block(review_policy)}
{_confidence_rubric_block(contract)}
{_recommendation_review_coverage_block(prior_output)}

{_task_block(task, prompt_preamble)}

{_json_block('Current analysis structured output', prior_output)}

{_json_block('Reviser structured output', reviser_output)}

{_json_block('Open issue ledger entering this audit', issue_ledger)}

Validator and advisory results:
{_validator_block(validation_runs)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()


def build_analysis_reviser_prompt(
    task: TaskSpec,
    prompt_preamble: str,
    prior_output: dict | None,
    critic_output: dict | None,
    validation_runs: list[ValidationRun],
    git_snapshot: dict,
    revision_round: int,
    contract: AnalysisReviewContract,
    open_issues: list[dict[str, Any]],
) -> str:
    return f"""
You are the REVISER stage in an analysis-review harness.

Critical rules:
- This is still an analysis task. Do not modify files unless your effective permissions and the task policy explicitly allow it.
- Your job is to close all open medium-or-higher blockers, not merely to improve the strongest few issues.
- Preserve already-solid recommendations wherever possible.
- Return ONLY the JSON object required by the schema.

Your job:
1. Inspect the current workspace directly.
2. Revise the prior analysis to address every open issue in the issue ledger below.
3. Return an `issue_resolution_map` entry for every open issue ID, even if you disagree with it.
4. Update strengths and uncertainties using the same `items` plus `none_reason` section shape required by the schema.
5. Preserve each recommendation's bounded evidence list and review_surface unless an open issue requires changing them.
6. Keep the recommendation payload on the shared JSON family; in trust mode that includes deliberate use of grounding_mode, verified_evidence_refs, checked_files, and affected_files.
7. Every evidence ref must stay a concrete path-only workspace path you inspected in this run, so every evidence ref must also appear in files_reviewed.
8. Do not cite evidence as `path:line-range`; if line detail matters, keep the evidence ref at file granularity and move the excerpt detail into rationale or scope_note.
9. Keep each recommendation's evidence list within the bounded-review cap unless the contract explicitly allows more.
10. Use the shared confidence rubric below when revising confidence values.
11. Do not add new recommendations unless needed to fix a missed issue or satisfy the minimum recommendation count.
12. Use workspace_write_intent=`none` unless you truly changed the repo.

Revision round: {revision_round}
{_analysis_contract_block(contract)}
{_bounded_review_policy_block(contract)}
{_trust_review_policy_block(contract)}
{_recommendation_payload_block(contract)}
{_review_policy_block(contract.stop_policy)}
{_confidence_rubric_block(contract)}

{_task_block(task, prompt_preamble)}

{_json_block('Prior analysis structured output', prior_output)}

{_json_block('Latest review structured output', critic_output)}

{_json_block('Open issue ledger', open_issues)}

Validator and advisory results:
{_validator_block(validation_runs)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()
