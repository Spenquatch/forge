from __future__ import annotations

import json
from typing import Any, Iterable

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
5. If the evidence is incomplete, lower confidence and classify conservatively instead of overstating certainty.
6. Use workspace_write_intent=`none` unless you truly changed the repo.

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
    reviewer_label: str,
    round_index: int,
) -> str:
    role_word = reviewer_label.upper()
    return f"""
You are the {role_word} stage in an analysis-review harness.

Critical rules:
- Do NOT edit files in this stage.
- Audit the prior analysis for factual grounding, overclaims, omissions, actionability, and scope discipline.
- Return ONLY the JSON object required by the schema.

How to score:
- grounding_score: Are the recommendations supported by actual repo evidence?
- actionability_score: Are the recommendations concrete enough to execute?
- scope_compliance_score: Do they stay within the requested task and avoid unrelated drift?

Decision guidance:
- Return verdict=revise if any medium-or-higher issue remains, or if the scores fail the stated stop policy.
- Return verdict=reject only for severe, fundamental problems.
- Return verdict=accept only when the analysis is well-grounded, specific, and properly scoped.

Review round: {round_index}
{_review_policy_block(review_policy)}

{_task_block(task, prompt_preamble)}

{_json_block('Prior analysis structured output', prior_output)}

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
) -> str:
    return f"""
You are the REVISER stage in an analysis-review harness.

Critical rules:
- This is still an analysis task. Do not modify files unless your effective permissions and the task policy explicitly allow it.
- Fix factual problems, soften overclaims, and improve actionability.
- Return ONLY the JSON object required by the schema.

Your job:
1. Inspect the current workspace directly.
2. Revise the prior analysis to address the critic's strongest evidence-backed issues.
3. Prefer improving a few high-value recommendations over expanding the list with weak ideas.
4. Preserve well-supported points; do not rewrite them away without reason.
5. Use workspace_write_intent=`none` unless you truly changed the repo.

Revision round: {revision_round}

{_task_block(task, prompt_preamble)}

{_json_block('Prior analysis structured output', prior_output)}

{_json_block('Critic structured output', critic_output)}

Validator and advisory results:
{_validator_block(validation_runs)}

Current workspace snapshot:
{render_git_snapshot(git_snapshot)}
""".strip()
