from __future__ import annotations

import json
from typing import Any


def _render_policy_list(items: list[str]) -> str:
    values = [str(item) for item in items if str(item).strip()]
    return ", ".join(values) if values else "none"


def render_report(summary: dict[str, Any]) -> str:
    lines: list[str] = ["# Forge Harness Report", ""]

    task = summary.get("task") or {}
    verdicts = summary.get("verdicts") or {}
    validator_summary = summary.get("validator_summary") or {}
    run_details = summary.get("run_details") or {}
    contract = summary.get("analysis_review_contract") or {}
    review_coverage = summary.get("analysis_review_coverage") or {}

    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Run verdict: **{summary.get('verdict')}**")
    if verdicts:
        lines.append(f"- Content verdict: `{verdicts.get('content_verdict', 'unknown')}`")
        lines.append(f"- Validator verdict: `{verdicts.get('validator_verdict', 'unknown')}`")
        lines.append(f"- Policy verdict: `{verdicts.get('policy_verdict', 'unknown')}`")
        lines.append(f"- Config verdict: `{verdicts.get('config_verdict', 'unknown')}`")
    lines.append(f"- Task ID: `{task.get('id', 'task')}`")
    lines.append(f"- Task kind: `{task.get('task_kind', 'unknown')}`")
    lines.append(f"- Strategy: `{summary.get('strategy_name', 'strategy')}` ({summary.get('strategy_kind', 'kind')})")
    lines.append(f"- Workspace: `{summary.get('workspace')}`")
    final_artifact = (summary.get("artifacts") or {}).get("final_artifact")
    final_artifact_kind = (summary.get("artifacts") or {}).get("final_artifact_kind")
    if final_artifact:
        lines.append(f"- Primary deliverable: `{final_artifact_kind}` → `{final_artifact}`")
    lines.append("")

    if summary.get("final_summary"):
        lines.append("## Final Summary")
        lines.append("")
        lines.append(summary["final_summary"])
        lines.append("")

    if contract:
        lines.append("## Analysis Review Contract")
        lines.append("")
        lines.append(f"- Contract version: `{contract.get('contract_version')}`")
        stop_policy = contract.get("stop_policy") or {}
        stop_when = stop_policy.get("stop_when") or {}
        lines.append(f"- Reviser goal: `{contract.get('reviser_goal')}`")
        lines.append(f"- Require issue ledger: `{contract.get('require_issue_ledger')}`")
        lines.append(f"- Require recommendation reviews: `{contract.get('require_recommendation_reviews')}`")
        if stop_when:
            lines.append(f"- Stop policy: `{json.dumps(stop_when, sort_keys=True)}`")
        partial_acceptance = contract.get("partial_acceptance") or {}
        if partial_acceptance:
            lines.append(
                f"- Partial acceptance policy: `{json.dumps(partial_acceptance, sort_keys=True)}`"
            )
        required_sections = contract.get("required_sections") or {}
        if required_sections:
            lines.append(
                f"- Required analysis sections: `{json.dumps(required_sections, sort_keys=True)}`"
            )
        lines.append("")

    if task.get("task_kind") == "analysis_review" or summary.get("strategy_kind") == "analysis_review_v1":
        lines.append("## Review Loop Coverage")
        lines.append("")
        lines.append(f"- Review stages attempted: `{review_coverage.get('review_stages_attempted', 0)}`")
        lines.append(f"- Review stages completed: `{review_coverage.get('review_stages_completed', 0)}`")
        lines.append(f"- Review loop exercised: `{review_coverage.get('review_loop_exercised', False)}`")
        failed_review_stages = review_coverage.get("failed_review_stages") or []
        if failed_review_stages:
            lines.append("- Failed review stages:")
            for item in failed_review_stages:
                label = item.get("role_name") or f"stage-{item.get('stage_index')}"
                detail = item.get("failure_summary") or item.get("failure_kind") or "unknown error"
                lines.append(f"  - {label}: {detail}")
        if not review_coverage.get("review_loop_exercised", False):
            lines.append(
                "- Notes: reviewer-derived issue counts and recommendation verdicts were not produced for this run."
            )
        lines.append("")

    if run_details:
        lines.append("## Run Details")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(run_details, indent=2, sort_keys=False))
        lines.append("```")
        lines.append("")

    if summary.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for warning in summary["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    policy = summary.get("workspace_write_policy") or {}
    lines.append("## Workspace Write Policy")
    lines.append("")
    lines.append(f"- Mode: `{policy.get('mode', 'unknown')}`")
    lines.append(f"- Allowed paths: {_render_policy_list(policy.get('allowed_paths', []))}")
    lines.append(f"- Denied paths: {_render_policy_list(policy.get('denied_paths', []))}")
    lines.append(f"- Allow untracked files: `{policy.get('allow_untracked')}`")
    lines.append(f"- Allow renames: `{policy.get('allow_renames')}`")
    lines.append(f"- Allow deletions: `{policy.get('allow_deletions')}`")
    max_touched = policy.get('max_touched_files')
    lines.append(f"- Max touched files: `{max_touched if max_touched is not None else 'unlimited'}`")
    lines.append(f"- Require clean start: `{policy.get('require_clean_start')}`")
    ignored = summary.get("workspace_policy_ignored_rel_paths") or []
    lines.append(f"- Ignored harness-artifact paths: {_render_policy_list(ignored)}")
    review_requirements = task.get("review_requirements") or {}
    if task.get("task_kind") == "analysis_review":
        lines.append(f"- Require evidence per recommendation: `{review_requirements.get('require_evidence_per_recommendation')}`")
        lines.append(f"- Require classification: `{review_requirements.get('require_classification')}`")
        lines.append(f"- Require priority: `{review_requirements.get('require_priority')}`")
        lines.append(f"- Minimum recommendations: `{review_requirements.get('min_recommendations')}`")
    lines.append("")

    checks = summary.get("workspace_policy_checks", [])
    lines.append("## Workspace Policy Checks")
    lines.append("")
    if not checks:
        lines.append("No workspace policy checks were recorded.")
        lines.append("")
    else:
        for check in checks:
            outcome = "PASS" if check.get("ok") else "FAIL"
            lines.append(f"### {check.get('checkpoint')} — {outcome}")
            lines.append("")
            lines.append(f"- Touched files: {_render_policy_list(check.get('touched_files', []))}")
            if check.get("modified_files"):
                lines.append(f"- Modified files: {_render_policy_list(check.get('modified_files', []))}")
            if check.get("added_files"):
                lines.append(f"- Added files: {_render_policy_list(check.get('added_files', []))}")
            if check.get("deleted_files"):
                lines.append(f"- Deleted files: {_render_policy_list(check.get('deleted_files', []))}")
            if check.get("renamed_files"):
                rename_text = ", ".join(
                    f"{item.get('from')} -> {item.get('to')}" for item in check.get("renamed_files", [])
                )
                lines.append(f"- Renamed files: {rename_text}")
            if check.get("new_untracked_files"):
                lines.append(
                    f"- New untracked files: {_render_policy_list(check.get('new_untracked_files', []))}"
                )
            if check.get("violations"):
                lines.append("- Violations:")
                for violation in check.get("violations", []):
                    lines.append(f"  - {violation}")
            if check.get("notes"):
                lines.append("- Notes:")
                for note in check.get("notes", []):
                    lines.append(f"  - {note}")
            lines.append("")

    lines.append("## Validators")
    lines.append("")
    lines.append(f"- Total validator executions: `{validator_summary.get('total_runs', 0)}`")
    lines.append(f"- Latest round verdict: `{validator_summary.get('latest_round_verdict', 'not_configured')}`")
    if validator_summary.get("status_counts"):
        lines.append(f"- Status counts: `{json.dumps(validator_summary.get('status_counts'), sort_keys=True)}`")
    if validator_summary.get("required_status_counts"):
        lines.append(
            f"- Required status counts: `{json.dumps(validator_summary.get('required_status_counts'), sort_keys=True)}`"
        )
    lines.append("")

    validator_rounds = summary.get("validator_rounds", [])
    if not validator_rounds:
        lines.append("No validators configured or run.")
        lines.append("")
    else:
        for round_data in validator_rounds:
            lines.append(f"### Round {round_data.get('round_index')}")
            lines.append("")
            for item in round_data.get("results", []):
                required = "required" if item.get("required") else "optional"
                lines.append(
                    f"- **{item.get('name')}** — {item.get('status')} — exit `{item.get('exit_code') if item.get('exit_code') is not None else 'n/a'}` — {required}"
                )
                if item.get("skip_reason"):
                    lines.append(f"  - reason: {item.get('skip_reason')}")
                if item.get("missing_paths"):
                    lines.append(f"  - missing paths: {_render_policy_list(item.get('missing_paths', []))}")
                if item.get("missing_binaries"):
                    lines.append(f"  - missing binaries: {_render_policy_list(item.get('missing_binaries', []))}")
                if item.get("error"):
                    lines.append(f"  - error: {item.get('error')}")
            lines.append("")

    issue_ledger = summary.get("issue_ledger") or []
    if issue_ledger:
        lines.append("## Issue Ledger")
        lines.append("")
        open_count = sum(
            1 for issue in issue_ledger if str(issue.get("resolution_status") or "") in {"open", "carried_forward"}
        )
        resolved_count = sum(
            1 for issue in issue_ledger if str(issue.get("resolution_status") or "") == "resolved"
        )
        lines.append(f"- Open issues: `{open_count}`")
        lines.append(f"- Resolved issues: `{resolved_count}`")
        lines.append("")
        for issue in issue_ledger:
            lines.append(
                f"### {issue.get('issue_id')} — {issue.get('severity')} — {issue.get('blocking_class')} — {issue.get('resolution_status')}"
            )
            lines.append("")
            lines.append(f"- Kind: `{issue.get('kind')}`")
            if issue.get("recommendation_index") is not None:
                lines.append(f"- Recommendation index: `{issue.get('recommendation_index')}`")
            lines.append(f"- Title: {issue.get('title')}")
            lines.append(f"- Evidence: {issue.get('evidence')}")
            lines.append(f"- Repair hint: {issue.get('repair_hint')}")
            if issue.get("why_not_raised_earlier"):
                lines.append(f"- Why not raised earlier: {issue.get('why_not_raised_earlier')}")
            lines.append("")

    drafts = summary.get("drafts", [])
    if drafts:
        lines.append("## Draft Selection")
        lines.append("")
        lines.append(f"- Best draft ID: `{summary.get('best_draft_id')}`")
        lines.append(f"- Selected draft ID: `{summary.get('selected_draft_id')}`")
        lines.append("")
        for draft in drafts:
            lines.append(f"### {draft.get('draft_id')} — {draft.get('review_status')}")
            lines.append("")
            lines.append(f"- Role: `{draft.get('role_name')}`")
            lines.append(f"- Round: `{draft.get('round_index')}`")
            lines.append(f"- Review state: `{draft.get('review_state', 'not_evaluated')}`")
            issue_counts = draft.get('issue_counts') or {}
            validator_failures = issue_counts.get("required_validator_failures")
            if validator_failures is not None:
                lines.append(f"- Required validator failures: `{validator_failures}`")
            if draft.get("review_state") == "evaluated":
                review_issue_counts = {
                    key: value
                    for key, value in issue_counts.items()
                    if key != "required_validator_failures"
                }
                if review_issue_counts:
                    lines.append(f"- Review issue counts: `{json.dumps(review_issue_counts, sort_keys=True)}`")
            else:
                lines.append("- Review issue counts: `not evaluated`")
            scores = draft.get('scores') or {}
            if scores:
                lines.append(f"- Scores: `{json.dumps(scores, sort_keys=True)}`")
            if draft.get('summary'):
                lines.append(f"- Summary: {draft.get('summary')}")
            metadata = draft.get("metadata") or {}
            if metadata.get("review_attempted") and not metadata.get("review_completed"):
                lines.append(
                    f"- Review attempt failed: {metadata.get('review_failure_summary') or metadata.get('review_failure_kind') or 'unknown error'}"
                )
            lines.append("")

    recommendation_reviews = summary.get("recommendation_reviews") or []
    if recommendation_reviews:
        lines.append("## Recommendation Reviews")
        lines.append("")
        for item in recommendation_reviews:
            lines.append(
                f"- Recommendation {item.get('recommendation_index')}: `{item.get('verdict')}` — {item.get('summary')}"
            )
            if item.get("open_issue_ids"):
                lines.append(f"  - Open issues: {_render_policy_list(item.get('open_issue_ids', []))}")
            lines.append(
                f"  - Confidence assessment: `{item.get('confidence_assessment', 'not_assessed')}`"
            )
        lines.append("")

    lines.append("## Agent Stages")
    lines.append("")
    for stage in summary.get("agent_stages", []):
        title = f"{stage.get('stage_index'):02d}. {stage.get('role_name')}"
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"- Provider: `{stage.get('provider')}`")
        lines.append(f"- Model: `{stage.get('model')}`")
        lines.append(f"- Requested access: `{stage.get('requested_access', stage.get('access'))}`")
        lines.append(f"- Effective access: `{stage.get('effective_access', stage.get('access'))}`")
        if stage.get("access_override_reason"):
            lines.append(f"- Access override: {stage.get('access_override_reason')}")
        lines.append(f"- OK: `{stage.get('ok')}`")
        lines.append(f"- Exit code: `{stage.get('exit_code')}`")
        lines.append(f"- Duration: `{stage.get('duration_sec')}` seconds")
        if stage.get("failure_kind"):
            lines.append(f"- Failure kind: `{stage.get('failure_kind')}`")
        if stage.get("failure_summary"):
            lines.append(f"- Failure summary: {stage.get('failure_summary')}")
        if stage.get("error"):
            lines.append(f"- Error: {stage.get('error')}")
        schema_errors = stage.get("schema_validation_errors") or []
        if schema_errors:
            lines.append("- Schema validation errors:")
            for item in schema_errors:
                lines.append(f"  - {item}")
        semantic_path = stage.get("semantic_validation_path")
        if semantic_path:
            lines.append(f"- Semantic validation artifact: `{semantic_path}`")
        semantic_errors = stage.get("semantic_validation_errors") or []
        if semantic_errors:
            lines.append("- Semantic validation errors:")
            for item in semantic_errors:
                lines.append(f"  - {item}")
        semantic_warnings = stage.get("semantic_validation_warnings") or []
        if semantic_warnings:
            lines.append("- Semantic validation warnings:")
            for item in semantic_warnings:
                lines.append(f"  - {item}")
        structured = stage.get("structured_output") or {}
        if structured:
            lines.append("")
            lines.append("Structured output:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(structured, indent=2, sort_keys=False))
            lines.append("```")
        lines.append("")

    git_final = summary.get("final_git_snapshot") or {}
    if git_final.get("is_git"):
        lines.append("## Final Git Snapshot")
        lines.append("")
        lines.append(f"- Branch: `{git_final.get('branch')}`")
        lines.append(f"- HEAD: `{git_final.get('head')}`")
        changed = summary.get("changed_files", [])
        lines.append(f"- Changed files: {', '.join(changed) if changed else 'none'}")
        lines.append("")
        diff_stat = git_final.get("diff_stat", "").strip()
        lines.append("```text")
        lines.append(diff_stat or "no unstaged diff")
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
