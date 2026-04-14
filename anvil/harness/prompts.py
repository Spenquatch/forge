from __future__ import annotations

import json
from typing import Any, Iterable

from .contracts import AnalysisReviewContract, confidence_rubric_lines
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
        ]
    )


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
6. Populate strengths, uncertainties, and files_reviewed with concrete observations from this run.
7. Use workspace_write_intent=`none` unless you truly changed the repo.

{_analysis_contract_block(contract)}
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
2. For every issue you raise, classify both `kind` and `blocking_class`.
3. Review every recommendation individually and return recommendation-level verdicts.
4. Use `accept_partial` when a subset of recommendations is already valid even if the overall draft still needs revision.
5. Use the shared confidence rubric below when judging whether confidence is too high or too low.

Decision guidance:
- Return verdict=revise when the overall draft still needs more work.
- Return verdict=reject only for severe, fundamental problems.
- Return verdict=accept only when the entire draft is sound.
- Return verdict=accept_partial when at least one recommendation is sound but the whole draft is not yet fully acceptable.

{_analysis_contract_block(contract)}
{_review_policy_block(review_policy)}
{_confidence_rubric_block(contract)}

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
5. Use `accept_partial` when a subset of recommendations is already valid even if the whole draft still needs revision.

Decision guidance:
- Return verdict=accept when the entire draft is acceptable.
- Return verdict=accept_partial when the accepted subset is usable but the whole draft is not.
- Return verdict=revise when additional work is still required.
- Return verdict=reject only for severe, fundamental problems.

Audit round: {round_index}
{_analysis_contract_block(contract)}
{_review_policy_block(review_policy)}
{_confidence_rubric_block(contract)}

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
4. Use the shared confidence rubric below when revising confidence values.
5. Do not add new recommendations unless needed to fix a missed issue or satisfy the minimum recommendation count.
6. Use workspace_write_intent=`none` unless you truly changed the repo.

Revision round: {revision_round}
{_analysis_contract_block(contract)}
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
