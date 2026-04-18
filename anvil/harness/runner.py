from __future__ import annotations

import datetime as dt
import hashlib
import json
import posixpath
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from anvil.orchestrator import reload_config

from .contracts import (
    AnalysisReviewContract,
    build_analysis_review_contract,
    default_blocking_class_for_kind,
)
from .files import load_structured_file, slugify, write_json, write_text
from .git_utils import (
    capture_git_snapshot,
    capture_non_git_workspace_state,
    capture_workspace_file_inventory,
    changed_files,
    evaluate_workspace_write_policy,
    git_snapshot_is_dirty,
)
from .prompts import (
    build_analysis_auditor_prompt,
    build_analysis_critic_prompt,
    build_analysis_proposer_prompt,
    build_analysis_reviser_prompt,
    build_falsifier_prompt,
    build_patcher_prompt,
    build_proposer_prompt,
    build_single_pass_prompt,
)
from .providers import get_provider
from .reporting import apply_final_artifacts
from .schemas import (
    analysis_output_schema,
    analysis_review_schema,
    falsifier_schema,
    patcher_schema,
    proposer_schema,
    single_pass_schema,
)
from .selection import extract_drafts_from_summary, select_best_draft
from .semantic_validation import validate_stage_output
from .types import (
    ANALYSIS_REVIEW_BOUNDED_KIND,
    ANALYSIS_REVIEW_LEGACY_KIND,
    ProviderRun,
    RoleConfig,
    StageRequest,
    StrategyConfig,
    TaskSpec,
    ValidationRun,
    is_analysis_review_strategy_kind,
)
from .validation import preflight_validators, run_validators


class HarnessError(RuntimeError):
    pass


class WorkspacePolicyViolationError(HarnessError):
    def __init__(self, checkpoint: str, evaluation: dict[str, Any]) -> None:
        self.checkpoint = checkpoint
        self.evaluation = evaluation
        message = "; ".join(evaluation.get("violations", [])) or "Workspace write policy violated."
        super().__init__(f"Workspace write policy violated at {checkpoint}: {message}")


class HarnessRunner:
    def __init__(
        self,
        *,
        task_path: str | Path,
        strategy_path: str | Path,
        workspace: str | Path,
        out_root: str | Path,
        config_path: str | Path = "config/models.yaml",
        task_data: dict[str, Any] | None = None,
        strategy_data: dict[str, Any] | None = None,
        thread_id: str | None = None,
        auto_fit_strategy: bool = True,
    ) -> None:
        self.task_path = Path(task_path)
        self.strategy_path = Path(strategy_path)
        self.workspace = Path(workspace).resolve()
        self.out_root = Path(out_root).resolve()
        self.config_path = Path(config_path)
        self.thread_id = thread_id
        self.auto_fit_strategy = auto_fit_strategy
        task_payload = task_data if task_data is not None else load_structured_file(self.task_path)
        strategy_payload = strategy_data if strategy_data is not None else load_structured_file(self.strategy_path)
        self.task = TaskSpec.from_dict(task_payload)
        self.strategy = StrategyConfig.from_dict(strategy_payload)
        self.agent_stages: list[dict[str, Any]] = []
        self.validator_rounds: list[dict[str, Any]] = []
        self.workspace_policy_checks: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.stage_counter = 0
        self.analysis_review_contract: AnalysisReviewContract | None = None
        self.issue_ledger: list[dict[str, Any]] = []
        self._issue_ledger_by_id: dict[str, dict[str, Any]] = {}
        self.policy_ignored_rel_paths = self._workspace_ignored_rel_paths()
        self.initial_git_snapshot: dict[str, Any] | None = None
        self.initial_non_git_state: dict[str, Any] | None = None

    def run(self) -> dict[str, Any]:
        reload_config(str(self.config_path))
        run_id = f"{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}-{slugify(self.task.id)}-{uuid4().hex[:8]}"
        self.run_dir = self.out_root / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.validators_dir = self.run_dir / "validators"
        self.artifacts_dir = self.run_dir / "artifacts"
        self.validators_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        run_verdict = "harness_error"
        content_verdict = "harness_error"
        validator_verdict = "not_run"
        policy_verdict = "pass"
        config_verdict = "pass"
        final_summary = "Harness did not complete."
        failure_details: dict[str, Any] | None = None
        run_details: dict[str, Any] = {}

        self.initial_git_snapshot = capture_git_snapshot(
            self.workspace,
            ignored_rel_paths=self.policy_ignored_rel_paths,
        )
        if not self.initial_git_snapshot.get("is_git"):
            self.initial_non_git_state = capture_non_git_workspace_state(
                self.workspace,
                ignored_rel_paths=self.policy_ignored_rel_paths,
            )
        write_json(self.run_dir / "git.initial.json", self.initial_git_snapshot)

        if self.initial_git_snapshot.get("is_git") and git_snapshot_is_dirty(self.initial_git_snapshot):
            self.warnings.append(
                "Workspace is dirty at start. The harness will operate on the existing working tree. "
                "Use workspace_write_policy.require_clean_start=true to block this."
            )

        try:
            self._emit_task_strategy_warnings()
            self._apply_strategy_autofit()
            if is_analysis_review_strategy_kind(self.strategy.kind):
                self.analysis_review_contract = build_analysis_review_contract(self.task, self.strategy)
            write_json(self.run_dir / "task.effective.json", self.task.to_dict())
            write_json(self.run_dir / "strategy.effective.json", self.strategy.to_dict())
            if self.analysis_review_contract is not None:
                write_json(
                    self.run_dir / "analysis_review.contract.effective.json",
                    self.analysis_review_contract.to_dict(),
                )
            write_json(
                self.run_dir / "workspace.policy.config.json",
                {
                    "ignored_rel_paths": self.policy_ignored_rel_paths,
                    "workspace_write_policy": self.task.workspace_write_policy.to_dict(),
                },
            )
            preflight_outcome = self._validator_preflight_outcome()
            if preflight_outcome is not None:
                outcome = preflight_outcome
            else:
                self._enforce_clean_start_if_required()
                if self.strategy.kind == "single_pass":
                    outcome = self._run_single_pass()
                elif self.strategy.kind == "pfr_v1":
                    outcome = self._run_pfr_v1()
                elif is_analysis_review_strategy_kind(self.strategy.kind):
                    outcome = self._run_analysis_review_v1()
                else:
                    raise HarnessError(f"Unsupported strategy kind: {self.strategy.kind}")
            run_verdict = str(outcome.get("run_verdict", "harness_error"))
            content_verdict = str(outcome.get("content_verdict", run_verdict))
            validator_verdict = str(outcome.get("validator_verdict", "not_run"))
            config_verdict = str(outcome.get("config_verdict", "pass"))
            final_summary = str(outcome.get("final_summary", final_summary))
            failure_details = outcome.get("failure_details")
            run_details = dict(outcome.get("details", {}))
        except WorkspacePolicyViolationError as exc:
            run_verdict = "policy_violation"
            content_verdict = "policy_violation"
            validator_verdict = self._classify_validator_verdict(self._latest_validator_results())
            final_summary = str(exc)
            failure_details = exc.evaluation
            self.warnings.append(str(exc))

        final_git_snapshot = capture_git_snapshot(
            self.workspace,
            ignored_rel_paths=self.policy_ignored_rel_paths,
        )
        final_non_git_state = None
        if not final_git_snapshot.get("is_git"):
            final_non_git_state = capture_non_git_workspace_state(
                self.workspace,
                ignored_rel_paths=self.policy_ignored_rel_paths,
            )
        write_json(self.run_dir / "git.final.json", final_git_snapshot)

        final_policy_evaluation = self._evaluate_workspace_policy(
            current_git_snapshot=final_git_snapshot,
            current_non_git_state=final_non_git_state,
            final=True,
            checkpoint="final",
        )
        self.workspace_policy_checks.append(final_policy_evaluation)
        write_json(self.run_dir / "workspace.policy.final.json", final_policy_evaluation)

        if final_policy_evaluation.get("violations"):
            policy_verdict = "policy_violation"
            run_verdict = "policy_violation"
            final_summary = "; ".join(final_policy_evaluation["violations"])
            failure_details = final_policy_evaluation
        else:
            policy_verdict = "pass"

        final_changed_files = (
            changed_files(final_git_snapshot)
            if final_git_snapshot.get("is_git")
            else list(final_policy_evaluation.get("touched_files", []))
        )

        bounded_review_summary = self._build_bounded_review_summary(run_details)
        if bounded_review_summary is not None:
            run_details["bounded_review_summary"] = bounded_review_summary
        analysis_review_status = run_details.get("analysis_review_status")
        if isinstance(analysis_review_status, dict) and analysis_review_status:
            run_details["analysis_review_status"] = analysis_review_status

        final_answer_payload = self._derive_final_answer_payload(run_details)
        recommendation_reviews = list(run_details.get("recommendation_reviews") or [])
        issue_ledger = list(run_details.get("issue_ledger") or self._serialized_issue_ledger())
        analysis_review_contract = (
            run_details.get("analysis_review_contract")
            if isinstance(run_details.get("analysis_review_contract"), dict)
            else (self.analysis_review_contract.to_dict() if self.analysis_review_contract is not None else None)
        )
        analysis_review_coverage = self._analysis_review_coverage()

        summary = {
            "run_id": run_id,
            "thread_id": self.thread_id,
            "workspace": str(self.workspace),
            "config_path": str(self.config_path),
            "task": self.task.to_dict(),
            "strategy_name": self.strategy.name,
            "strategy_kind": self.strategy.kind,
            "warnings": self.warnings,
            "errors": self.errors,
            "verdict": run_verdict,
            "verdicts": {
                "run_verdict": run_verdict,
                "content_verdict": content_verdict,
                "validator_verdict": validator_verdict,
                "policy_verdict": policy_verdict,
                "config_verdict": config_verdict,
            },
            "final_summary": final_summary,
            "failure_details": failure_details,
            "run_details": run_details,
            "validator_summary": self._summarize_validator_rounds(),
            "workspace_write_policy": self.task.workspace_write_policy.to_dict(),
            "workspace_policy_ignored_rel_paths": self.policy_ignored_rel_paths,
            "workspace_policy_checks": self.workspace_policy_checks,
            "final_workspace_policy_evaluation": final_policy_evaluation,
            "agent_stages": self.agent_stages,
            "validator_rounds": self.validator_rounds,
            "initial_git_snapshot": self.initial_git_snapshot,
            "final_git_snapshot": final_git_snapshot,
            "changed_files": final_changed_files,
            "analysis_review_contract": analysis_review_contract,
            "analysis_review_status": analysis_review_status,
            "analysis_review_coverage": analysis_review_coverage,
            "issue_ledger": issue_ledger,
            "recommendation_reviews": recommendation_reviews,
            "artifacts": {
                "run_dir": str(self.run_dir),
                "report_md": str(self.run_dir / "REPORT.md"),
                "summary_json": str(self.run_dir / "summary.json"),
            },
            "final_answer": final_answer_payload,
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        if bounded_review_summary is not None:
            summary["bounded_review_summary"] = bounded_review_summary
        drafts = extract_drafts_from_summary(summary)
        summary["drafts"] = drafts
        best_draft = select_best_draft(drafts)
        summary["best_draft_id"] = best_draft.get("draft_id") if best_draft else None
        summary["selected_draft_id"] = best_draft.get("draft_id") if best_draft else None
        summary = apply_final_artifacts(summary)
        return summary

    def _run_single_pass(self) -> dict[str, Any]:
        role = self.strategy.roles.get("solver") or self.strategy.roles.get("proposer")
        if role is None:
            raise HarnessError("single_pass strategy requires a solver or proposer role")

        git_snapshot = capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths)
        prompt = build_single_pass_prompt(self.task, self.strategy.prompt_preamble, git_snapshot)
        stage = self._run_agent_stage("solver", role.provider, prompt, single_pass_schema(), role)
        if not stage.ok:
            return {
                "run_verdict": "harness_error",
                "content_verdict": "harness_error",
                "validator_verdict": self._classify_validator_verdict([]),
                "final_summary": f"Solver stage failed: {stage.error or 'unknown error'}",
                "failure_details": {"stage": "solver", "error": stage.error},
            }

        validation_runs = self._run_validator_round(round_index=0)
        validator_verdict = self._classify_validator_verdict(validation_runs)
        required_failures = self._required_validator_failures(validation_runs)
        content_verdict = "accepted" if not required_failures else "rejected"
        final_summary = (
            "Single-pass run succeeded and all required validators passed."
            if content_verdict == "accepted"
            else f"Single-pass run left {len(required_failures)} required validator failure(s)."
        )
        if validator_verdict == "misconfigured":
            final_summary = (
                "Single-pass run completed, but required validators were not applicable to this workspace. "
                "Check the validator configuration."
            )
        return {
            "run_verdict": self._combine_run_verdict(content_verdict, validator_verdict),
            "content_verdict": content_verdict,
            "validator_verdict": validator_verdict,
            "final_summary": final_summary,
            "details": {
                "final_validator_round": 0,
                "required_validator_failures": len(required_failures),
                "final_solution": stage.structured_output,
            },
        }

    def _run_pfr_v1(self) -> dict[str, Any]:
        proposer_cfg = self._require_role("proposer")
        self._require_role("falsifier")
        patcher_cfg = self.strategy.roles.get("patcher")

        git_snapshot = capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths)
        proposer_prompt = build_proposer_prompt(self.task, self.strategy.prompt_preamble, git_snapshot)
        proposer_run = self._run_agent_stage(
            "proposer", proposer_cfg.provider, proposer_prompt, proposer_schema(), proposer_cfg
        )
        if not proposer_run.ok:
            return {
                "run_verdict": "harness_error",
                "content_verdict": "harness_error",
                "validator_verdict": self._classify_validator_verdict([]),
                "final_summary": self._analysis_stage_failure_summary(
                    "proposer",
                    proposer_run,
                    review_loop_exercised=False,
                ),
                "failure_details": self._stage_failure_details(
                    "proposer",
                    proposer_run,
                    review_loop_exercised=False,
                ),
                "details": {"review_loop_exercised": False},
            }

        validation_runs = self._run_validator_round(round_index=0)
        falsifier_run = self._run_falsifier(
            prior_output=proposer_run.structured_output,
            validation_runs=validation_runs,
        )
        if not falsifier_run.ok:
            return {
                "run_verdict": "harness_error",
                "content_verdict": "harness_error",
                "validator_verdict": self._classify_validator_verdict(validation_runs),
                "final_summary": f"Falsifier stage failed: {falsifier_run.error or 'unknown error'}",
                "failure_details": {"stage": "falsifier", "error": falsifier_run.error},
            }

        last_validation_runs = validation_runs
        last_falsifier_run = falsifier_run
        latest_solution_run = proposer_run
        patch_rounds_executed = 0

        for repair_round in range(1, self.strategy.max_repair_loops + 1):
            if not self._should_patch(last_validation_runs, last_falsifier_run):
                break
            if patcher_cfg is None:
                self.warnings.append(
                    "Patch was needed but no patcher role is configured, so the harness stopped early."
                )
                break
            patch_prompt = build_patcher_prompt(
                self.task,
                self.strategy.prompt_preamble,
                proposer_run.structured_output,
                last_falsifier_run.structured_output,
                last_validation_runs,
                capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths),
                repair_round=repair_round,
            )
            patcher_run = self._run_agent_stage(
                f"patcher_round_{repair_round}",
                patcher_cfg.provider,
                patch_prompt,
                patcher_schema(),
                patcher_cfg,
            )
            if not patcher_run.ok:
                return {
                    "run_verdict": "harness_error",
                    "content_verdict": "harness_error",
                    "validator_verdict": self._classify_validator_verdict(last_validation_runs),
                    "final_summary": f"Patcher stage failed: {patcher_run.error or 'unknown error'}",
                    "failure_details": {"stage": f"patcher_round_{repair_round}", "error": patcher_run.error},
                }

            patch_rounds_executed += 1
            latest_solution_run = patcher_run
            last_validation_runs = self._run_validator_round(round_index=repair_round)
            if self.strategy.rerun_falsifier_after_patch:
                last_falsifier_run = self._run_falsifier(
                    prior_output=patcher_run.structured_output,
                    validation_runs=last_validation_runs,
                )
                if not last_falsifier_run.ok:
                    return {
                        "run_verdict": "harness_error",
                        "content_verdict": "harness_error",
                        "validator_verdict": self._classify_validator_verdict(last_validation_runs),
                        "final_summary": f"Falsifier re-run failed: {last_falsifier_run.error or 'unknown error'}",
                        "failure_details": {"stage": "falsifier_rerun", "error": last_falsifier_run.error},
                    }

        required_failures = self._required_validator_failures(last_validation_runs)
        falsifier_payload = last_falsifier_run.structured_output or {}
        verdict_signal = falsifier_payload.get("verdict")
        validator_verdict = self._classify_validator_verdict(last_validation_runs)

        if required_failures:
            content_verdict = "rejected"
            final_summary = (
                f"Required validators still fail after the repair loop ({len(required_failures)} failure(s))."
            )
        elif verdict_signal == "reject":
            content_verdict = "needs_manual_review"
            final_summary = "Required validators pass, but the falsifier still recommends rejection."
        elif verdict_signal == "inconclusive":
            content_verdict = "accepted_with_warnings"
            final_summary = "Required validators pass, but the falsifier remained inconclusive."
        else:
            content_verdict = "accepted"
            final_summary = "Required validators pass and the final falsifier verdict is accept."

        if validator_verdict == "misconfigured":
            final_summary = (
                "The P/F/R loop completed, but one or more required validators were not applicable to this workspace. "
                "Check validator configuration."
            )

        return {
            "run_verdict": self._combine_run_verdict(content_verdict, validator_verdict),
            "content_verdict": content_verdict,
            "validator_verdict": validator_verdict,
            "final_summary": final_summary,
            "details": {
                "patch_rounds_executed": patch_rounds_executed,
                "final_validator_round": patch_rounds_executed,
                "final_falsifier_verdict": verdict_signal,
                "required_validator_failures": len(required_failures),
                "final_solution": latest_solution_run.structured_output,
                "final_falsifier": last_falsifier_run.structured_output,
            },
        }

    def _run_analysis_review_v1(self) -> dict[str, Any]:
        contract = self._analysis_contract()
        proposer_cfg = self._require_role("proposer")
        critic_cfg = self._role_or_fallback("critic", ["falsifier"])
        reviser_cfg = self._role_or_fallback("reviser", ["patcher", "proposer"])
        auditor_cfg = self._role_or_fallback("auditor", ["critic", "falsifier"])

        git_snapshot = capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths)
        proposer_prompt = build_analysis_proposer_prompt(
            self.task,
            self.strategy.prompt_preamble,
            git_snapshot,
            contract,
        )
        proposer_run = self._run_agent_stage(
            "proposer",
            proposer_cfg.provider,
            proposer_prompt,
            analysis_output_schema(),
            proposer_cfg,
            semantic_context={"contract": contract},
        )
        if not proposer_run.ok:
            return {
                "run_verdict": "harness_error",
                "content_verdict": "harness_error",
                "validator_verdict": self._classify_validator_verdict([]),
                "final_summary": f"Proposer stage failed: {proposer_run.error or 'unknown error'}",
                "failure_details": {"stage": "proposer", "error": proposer_run.error},
            }

        validation_runs = self._run_validator_round(round_index=0)
        critic_run = self._run_analysis_reviewer(
            role_name="critic",
            role_cfg=critic_cfg,
            prior_output=proposer_run.structured_output,
            validation_runs=validation_runs,
            round_index=0,
            reviser_output=None,
        )
        if not critic_run.ok:
            return self._analysis_stage_failure_outcome(
                stage_label="critic",
                run=critic_run,
                validator_verdict=self._classify_validator_verdict(validation_runs),
                review_loop_exercised=False,
                final_analysis=proposer_run.structured_output,
                contract=contract,
            )
        self._ingest_review_payload(
            critic_run.structured_output or {},
            round_index=0,
            role_name="critic",
            reviser_output=None,
        )

        latest_analysis_run = proposer_run
        latest_review_run = critic_run
        revisions_completed = 0
        max_loops = max(
            self.strategy.review_loops.max_loops,
            self.strategy.review_loops.min_loops,
            1 if self.strategy.review_loops.always_run_first_revision else 0,
        )

        while revisions_completed < max_loops:
            if not self._analysis_needs_revision(latest_review_run.structured_output or {}, revisions_completed):
                break
            revisions_completed += 1
            reviser_prompt = build_analysis_reviser_prompt(
                self.task,
                self.strategy.prompt_preamble,
                latest_analysis_run.structured_output,
                latest_review_run.structured_output,
                validation_runs,
                capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths),
                revision_round=revisions_completed,
                contract=contract,
                open_issues=self._open_issue_records(),
            )
            prior_analysis_payload = latest_analysis_run.structured_output
            next_analysis_run = self._run_agent_stage(
                f"reviser_round_{revisions_completed}",
                reviser_cfg.provider,
                reviser_prompt,
                analysis_output_schema(require_issue_resolution_map=True),
                reviser_cfg,
                semantic_context={
                    "contract": contract,
                    "open_issue_ids": [
                        str(item.get("issue_id"))
                        for item in self._open_issue_records()
                        if str(item.get("issue_id") or "").strip()
                    ],
                },
            )
            if not next_analysis_run.ok:
                return self._analysis_stage_failure_outcome(
                    stage_label=f"reviser round {revisions_completed}",
                    run=next_analysis_run,
                    validator_verdict=self._classify_validator_verdict(validation_runs),
                    review_loop_exercised=True,
                    final_analysis=prior_analysis_payload,
                    contract=contract,
                )
            latest_analysis_run = next_analysis_run

            latest_review_run = self._run_analysis_reviewer(
                role_name="auditor",
                role_cfg=auditor_cfg,
                prior_output=latest_analysis_run.structured_output,
                validation_runs=validation_runs,
                round_index=revisions_completed,
                reviser_output=latest_analysis_run.structured_output,
            )
            if not latest_review_run.ok:
                return self._analysis_stage_failure_outcome(
                    stage_label="auditor",
                    run=latest_review_run,
                    validator_verdict=self._classify_validator_verdict(validation_runs),
                    review_loop_exercised=True,
                    final_analysis=latest_analysis_run.structured_output,
                    contract=contract,
                )
            self._ingest_review_payload(
                latest_review_run.structured_output or {},
                round_index=revisions_completed,
                role_name="auditor",
                reviser_output=latest_analysis_run.structured_output,
            )

        final_review_payload = latest_review_run.structured_output or {}
        final_analysis_payload = latest_analysis_run.structured_output or {}
        validator_verdict = self._classify_validator_verdict(validation_runs)
        content_verdict = self._analysis_content_verdict(
            final_review_payload,
            final_analysis_payload=final_analysis_payload,
            revisions_completed=revisions_completed,
            max_loops=max_loops,
        )
        analysis_review_status = self._build_analysis_review_status(
            final_analysis_payload=final_analysis_payload,
            final_review_payload=final_review_payload,
            content_verdict=content_verdict,
        )

        final_summary = self._analysis_final_summary(
            final_review_payload,
            final_analysis_payload=final_analysis_payload,
            content_verdict=content_verdict,
            revisions_completed=revisions_completed,
            max_loops=max_loops,
            validator_verdict=validator_verdict,
        )
        accepted_recommendation_count = len(self._accepted_recommendation_reviews(final_review_payload))

        return {
            "run_verdict": self._combine_run_verdict(content_verdict, validator_verdict),
            "content_verdict": content_verdict,
            "validator_verdict": validator_verdict,
            "final_summary": final_summary,
            "details": {
                "revisions_completed": revisions_completed,
                "review_policy": contract.stop_policy.to_dict(),
                "analysis_review_contract": contract.to_dict(),
                "final_review": final_review_payload,
                "final_analysis": final_analysis_payload,
                "issue_ledger": self._serialized_issue_ledger(),
                "recommendation_reviews": self._recommendation_reviews(final_review_payload),
                "accepted_recommendation_count": accepted_recommendation_count,
                "analysis_review_status": analysis_review_status,
                "review_loop_exercised": True,
            },
        }

    def _run_falsifier(
        self,
        *,
        prior_output: dict[str, Any] | None,
        validation_runs: list[ValidationRun],
    ) -> ProviderRun:
        falsifier_cfg = self._require_role("falsifier")
        falsifier_prompt = build_falsifier_prompt(
            self.task,
            self.strategy.prompt_preamble,
            prior_output,
            validation_runs,
            capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths),
        )
        return self._run_agent_stage(
            "falsifier",
            falsifier_cfg.provider,
            falsifier_prompt,
            falsifier_schema(),
            falsifier_cfg,
        )

    def _run_analysis_reviewer(
        self,
        *,
        role_name: str,
        role_cfg: RoleConfig,
        prior_output: dict[str, Any] | None,
        validation_runs: list[ValidationRun],
        round_index: int,
        reviser_output: dict[str, Any] | None,
    ) -> ProviderRun:
        contract = self._analysis_contract()
        git_snapshot = capture_git_snapshot(self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths)
        prior_open_issue_ids = [
            str(item.get("issue_id"))
            for item in self._open_issue_records()
            if str(item.get("issue_id") or "").strip()
        ]
        expected_recommendation_count = 0
        if isinstance(prior_output, dict):
            recommendations = prior_output.get("recommendations")
            if isinstance(recommendations, list):
                expected_recommendation_count = len(recommendations)
        if role_name == "auditor":
            prompt = build_analysis_auditor_prompt(
                self.task,
                self.strategy.prompt_preamble,
                prior_output,
                reviser_output,
                validation_runs,
                git_snapshot,
                self.strategy.review_loops,
                contract,
                self._open_issue_records(),
                round_index,
            )
        else:
            prompt = build_analysis_critic_prompt(
                self.task,
                self.strategy.prompt_preamble,
                prior_output,
                validation_runs,
                git_snapshot,
                self.strategy.review_loops,
                contract,
            )
            prior_open_issue_ids = []
        return self._run_agent_stage(
            role_name,
            role_cfg.provider,
            prompt,
            analysis_review_schema(),
            role_cfg,
            semantic_context={
                "contract": contract,
                "prior_open_issue_ids": prior_open_issue_ids,
                "expected_recommendation_count": expected_recommendation_count,
            },
        )

    def _run_agent_stage(
        self,
        role_name: str,
        provider_name: str,
        prompt_text: str,
        schema: dict[str, Any],
        role_config: RoleConfig,
        semantic_context: dict[str, Any] | None = None,
    ) -> ProviderRun:
        self.stage_counter += 1
        stage_dir = self.artifacts_dir / f"{self.stage_counter:02d}_{slugify(role_name)}"
        provider = get_provider(provider_name)
        effective_role_config = self._effective_role_config(role_name, role_config)
        request = StageRequest(
            role_name=role_name,
            role_config=effective_role_config,
            prompt_text=prompt_text,
            schema=schema,
            cwd=str(self.workspace),
            out_dir=str(stage_dir),
        )
        run = provider.run(request)

        semantic_errors: list[str] = []
        semantic_warnings: list[str] = []
        semantic_validation_path: str | None = None
        schema_validation_errors = list(run.schema_validation_errors or [])
        context = dict(semantic_context or {})
        contract = context.pop("contract", None)
        normalized_payload: dict[str, Any] | None = None
        payload_provenance: dict[str, Any] | None = None
        if isinstance(contract, AnalysisReviewContract):
            if isinstance(run.structured_output, dict):
                normalized_payload, payload_provenance = self._normalize_analysis_review_payload(
                    run.structured_output,
                    payload_provenance_mode=contract.trust_review.payload_provenance_mode,
                )
                raw_meta = dict(run.raw_meta or {})
                raw_meta["payload_provenance"] = payload_provenance
                run = replace(
                    run,
                    structured_output=normalized_payload,
                    raw_meta=raw_meta,
                )
            context.setdefault(
                "workspace_paths",
                capture_workspace_file_inventory(
                    self.workspace,
                    ignored_rel_paths=self.policy_ignored_rel_paths,
                ),
            )
            semantic_validation_path = str(stage_dir / "semantic_validation.json")
            if run.failure_kind:
                semantic_payload = {
                    "ok": False,
                    "skipped": True,
                    "skipped_reason": f"provider_failure:{run.failure_kind}",
                    "errors": [],
                    "warnings": [],
                    "payload_provenance": payload_provenance,
                }
            elif schema_validation_errors:
                semantic_payload = {
                    "ok": False,
                    "skipped": True,
                    "skipped_reason": "schema_validation_failed",
                    "errors": list(schema_validation_errors),
                    "warnings": [],
                    "payload_provenance": payload_provenance,
                }
            elif isinstance(normalized_payload, dict):
                semantic_result = validate_stage_output(
                    role_name=role_name,
                    payload=normalized_payload,
                    task=self.task,
                    contract=contract,
                    **context,
                )
                semantic_errors = list(semantic_result.errors)
                semantic_warnings = list(semantic_result.warnings)
                semantic_payload = {
                    "ok": not semantic_errors,
                    "skipped": False,
                    "errors": semantic_errors,
                    "warnings": semantic_warnings,
                    "payload_provenance": payload_provenance,
                }
            else:
                semantic_payload = {
                    "ok": False,
                    "skipped": True,
                    "skipped_reason": "structured_output_missing",
                    "errors": [],
                    "warnings": [],
                    "payload_provenance": payload_provenance,
                }

            write_json(semantic_validation_path, semantic_payload)
            raw_meta = dict(run.raw_meta or {})
            raw_meta["semantic_validation"] = semantic_payload
            if semantic_errors:
                semantic_error_text = "Semantic validation failed:\n" + "\n".join(
                    f"- {item}" for item in semantic_errors
                )
                combined_error = semantic_error_text
                if run.error:
                    combined_error = f"{run.error.rstrip()}\n{semantic_error_text}"
                run = replace(
                    run,
                    ok=False,
                    error=combined_error,
                    raw_meta=raw_meta,
                    failure_kind=run.failure_kind or "semantic_validation_error",
                    failure_summary=run.failure_summary or "Semantic validation failed.",
                )
            else:
                run = replace(run, raw_meta=raw_meta)
            for warning in semantic_warnings:
                self.warnings.append(f"{role_name}: {warning}")

        stage_record = asdict(run)
        stage_record["stage_index"] = self.stage_counter
        stage_record["requested_access"] = role_config.access
        stage_record["effective_access"] = effective_role_config.access
        if run.failure_kind:
            stage_record["failure_kind"] = run.failure_kind
        if run.failure_summary:
            stage_record["failure_summary"] = run.failure_summary
        if schema_validation_errors:
            stage_record["schema_validation_errors"] = list(schema_validation_errors)
        if semantic_warnings:
            stage_record["warnings"] = list(semantic_warnings)
        if semantic_errors:
            stage_record["semantic_validation_errors"] = semantic_errors
        if semantic_warnings:
            stage_record["semantic_validation_warnings"] = semantic_warnings
        if semantic_validation_path:
            stage_record["semantic_validation_path"] = semantic_validation_path
        if payload_provenance:
            stage_record["semantic_validation_payload_provenance"] = payload_provenance
        if role_config.access != effective_role_config.access:
            stage_record[
                "access_override_reason"
            ] = "Task-level workspace_write_policy forced this stage to run read-only."
        self.agent_stages.append(stage_record)
        write_json(stage_dir / "run.envelope.json", stage_record)

        self._record_workspace_policy_check(
            checkpoint=f"after_{role_name}",
            final=False,
            raise_on_violation=True,
        )
        return run

    def _run_validator_round(self, round_index: int) -> list[ValidationRun]:
        current_git_snapshot = capture_git_snapshot(
            self.workspace,
            ignored_rel_paths=self.policy_ignored_rel_paths,
        )
        current_non_git_state = None
        if not current_git_snapshot.get("is_git"):
            current_non_git_state = capture_non_git_workspace_state(
                self.workspace,
                ignored_rel_paths=self.policy_ignored_rel_paths,
            )
        workspace_eval = self._evaluate_workspace_policy(
            current_git_snapshot=current_git_snapshot,
            current_non_git_state=current_non_git_state,
            final=False,
            checkpoint=f"validator_round_{round_index}",
        )
        results = run_validators(
            self.strategy.validators,
            self.workspace,
            self.validators_dir,
            round_index,
            task=self.task,
            strategy=self.strategy,
            workspace_changed=bool(workspace_eval.get("touched_files")),
        )
        self.validator_rounds.append(
            {
                "round_index": round_index,
                "results": [r.to_dict() for r in results],
            }
        )
        return results

    def _required_validator_failures(self, results: list[ValidationRun]) -> list[ValidationRun]:
        return [item for item in results if item.required and item.status in {"failed", "error"}]

    def _should_patch(self, validation_runs: list[ValidationRun], falsifier_run: ProviderRun) -> bool:
        if self._required_validator_failures(validation_runs):
            return True
        payload = falsifier_run.structured_output or {}
        verdict = payload.get("verdict")
        if verdict == "reject":
            return True
        if verdict == "inconclusive" and self.strategy.patch_on_inconclusive:
            return True
        for issue in payload.get("issues", []):
            if issue.get("severity") in {"high", "critical"}:
                return True
        return False

    def _analysis_needs_revision(self, review_payload: dict[str, Any], revisions_completed: int) -> bool:
        policy = self.strategy.review_loops
        if revisions_completed < policy.min_loops:
            return True
        if revisions_completed == 0 and policy.always_run_first_revision:
            return True
        if not review_payload:
            return True
        if self._analysis_can_fully_accept(review_payload):
            return False
        if self._analysis_can_partially_accept(review_payload):
            return False
        if review_payload.get("verdict") in {"revise", "reject"}:
            return True
        return bool(self._blocking_issues(review_payload)) or bool(self._score_threshold_failures(review_payload))

    def _analysis_content_verdict(
        self,
        review_payload: dict[str, Any],
        *,
        final_analysis_payload: dict[str, Any] | None,
        revisions_completed: int,
        max_loops: int,
    ) -> str:
        if self._analysis_can_fully_accept(review_payload):
            if self._analysis_warning_causes(
                review_payload,
                final_analysis_payload=final_analysis_payload,
            ):
                return "accepted_with_warnings"
            return "accepted"
        if self._analysis_can_partially_accept(review_payload):
            return "accepted_partial"
        if revisions_completed >= max_loops and str(review_payload.get("verdict") or "").lower() == "reject":
            return "rejected"
        if revisions_completed >= max_loops:
            return "best_effort_exhausted"
        return "needs_revision"

    def _analysis_final_summary(
        self,
        review_payload: dict[str, Any],
        *,
        final_analysis_payload: dict[str, Any] | None,
        content_verdict: str,
        revisions_completed: int,
        max_loops: int,
        validator_verdict: str,
    ) -> str:
        verdict = content_verdict
        parts = [
            f"Analysis-review loop completed after {revisions_completed} revision round(s).",
            f"Final reviewer verdict: {review_payload.get('verdict', 'unknown')}.",
        ]
        for field_name in ("grounding_score", "actionability_score", "scope_compliance_score"):
            if field_name in review_payload:
                parts.append(f"{field_name}={review_payload[field_name]}")
        issue_count = len(review_payload.get("issues", []))
        if issue_count:
            parts.append(f"Open reviewer issues: {issue_count}.")
        accepted_recommendation_count = len(self._accepted_recommendation_reviews(review_payload))
        if accepted_recommendation_count:
            parts.append(f"Accepted recommendations: {accepted_recommendation_count}.")
        if review_payload.get("missing_topics"):
            parts.append(
                "Missing topics: " + ", ".join(str(x) for x in review_payload.get("missing_topics", []))
            )
        if validator_verdict == "misconfigured":
            parts.append(
                "Required validators were not applicable to this workspace. Check validator configuration."
            )
        if verdict == "accepted_with_warnings":
            downgrade_causes = self._analysis_warning_causes(
                review_payload,
                final_analysis_payload=final_analysis_payload,
            )
            if downgrade_causes:
                parts.append("Downgrade causes: " + "; ".join(downgrade_causes) + ".")
            else:
                parts.append("The content is usable, but the auditor still left low-severity warnings.")
        elif verdict == "accepted_partial":
            parts.append(
                "The run reached a partial acceptance outcome. Only the accepted recommendation subset is included in the final deliverable."
            )
        elif verdict == "best_effort_exhausted":
            parts.append("The harness used its available review loops but still did not meet the stop criteria.")
        return " ".join(parts)

    def _analysis_stage_failure_summary(
        self,
        stage_label: str,
        run: ProviderRun,
        *,
        review_loop_exercised: bool,
    ) -> str:
        kind = str(run.failure_kind or "").strip()
        if kind == "quota_exhausted":
            prefix = f"{stage_label.capitalize()} stage could not run because the provider hit its quota or usage limit."
        elif kind == "authentication_error":
            prefix = f"{stage_label.capitalize()} stage could not run because provider authentication failed."
        elif kind == "permission_denied":
            prefix = f"{stage_label.capitalize()} stage could not run because the provider denied access."
        elif kind == "provider_unavailable":
            prefix = f"{stage_label.capitalize()} stage could not run because the provider is unavailable or misconfigured."
        elif kind:
            prefix = f"{stage_label.capitalize()} stage failed ({kind})."
        else:
            prefix = f"{stage_label.capitalize()} stage failed."

        detail = str(run.failure_summary or run.error or "").strip()
        parts = [prefix]
        if detail:
            parts.append(detail)
        if not review_loop_exercised:
            parts.append("Review loop not exercised.")
        return " ".join(parts)

    def _analysis_stage_failure_outcome(
        self,
        *,
        stage_label: str,
        run: ProviderRun,
        validator_verdict: str,
        review_loop_exercised: bool,
        final_analysis: dict[str, Any] | None,
        contract: AnalysisReviewContract | None,
    ) -> dict[str, Any]:
        details = self._stage_failure_details(
            stage_label,
            run,
            review_loop_exercised=review_loop_exercised,
            final_analysis=final_analysis,
            contract=contract,
            issue_ledger=self._serialized_issue_ledger(),
        )
        return {
            "run_verdict": "harness_error",
            "content_verdict": "harness_error",
            "validator_verdict": validator_verdict,
            "final_summary": self._analysis_stage_failure_summary(
                stage_label,
                run,
                review_loop_exercised=review_loop_exercised,
            ),
            "failure_details": details,
            "details": details,
        }

    @staticmethod
    def _stage_failure_details(
        stage_label: str,
        run: ProviderRun,
        *,
        review_loop_exercised: bool | None = None,
        final_analysis: dict[str, Any] | None = None,
        contract: AnalysisReviewContract | None = None,
        issue_ledger: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {
            "stage": stage_label,
            "error": run.error,
            "failure_kind": run.failure_kind,
            "failure_summary": run.failure_summary,
            "provider": run.provider,
            "model": run.model,
            "exit_code": run.exit_code,
        }
        if run.schema_validation_errors:
            details["schema_validation_errors"] = list(run.schema_validation_errors)
        if review_loop_exercised is not None:
            details["review_loop_exercised"] = review_loop_exercised
        if isinstance(final_analysis, dict) and final_analysis:
            details["final_analysis"] = final_analysis
        if contract is not None:
            details["analysis_review_contract"] = contract.to_dict()
        if issue_ledger is not None:
            details["issue_ledger"] = issue_ledger
        return details

    def _analysis_review_coverage(self) -> dict[str, Any]:
        attempted = 0
        completed = 0
        failed: list[dict[str, Any]] = []

        for stage in self.agent_stages:
            if not isinstance(stage, dict):
                continue
            role_name = str(stage.get("role_name") or "")
            if not role_name.startswith(("critic", "auditor")):
                continue
            attempted += 1
            payload = stage.get("structured_output")
            if stage.get("ok") and isinstance(payload, dict) and "verdict" in payload:
                completed += 1
                continue
            failed.append(
                {
                    "stage_index": stage.get("stage_index"),
                    "role_name": role_name,
                    "failure_kind": stage.get("failure_kind"),
                    "failure_summary": stage.get("failure_summary") or stage.get("error"),
                }
            )

        return {
            "review_stages_attempted": attempted,
            "review_stages_completed": completed,
            "review_loop_exercised": completed > 0,
            "failed_review_stages": failed,
        }

    def _build_bounded_review_summary(self, run_details: dict[str, Any]) -> dict[str, Any] | None:
        contract_dict = run_details.get("analysis_review_contract")
        if not isinstance(contract_dict, dict):
            if self.analysis_review_contract is None:
                return None
            contract_dict = self.analysis_review_contract.to_dict()

        bounded_policy = contract_dict.get("bounded_review")
        if not isinstance(bounded_policy, dict):
            return None

        final_analysis = self._resolve_bounded_review_analysis_payload(run_details)
        recommendations = final_analysis.get("recommendations") if isinstance(final_analysis, dict) else []
        if not isinstance(recommendations, list):
            recommendations = []

        issue_ledger = run_details.get("issue_ledger")
        if not isinstance(issue_ledger, list):
            issue_ledger = self._serialized_issue_ledger()

        review_stages: list[dict[str, Any]] = []
        scope_escapes: list[dict[str, Any]] = []
        next_auditor_round = 1

        for stage in self.agent_stages:
            if not isinstance(stage, dict):
                continue
            role_name = str(stage.get("role_name") or "").strip()
            if role_name not in {"critic", "auditor"}:
                continue
            payload = stage.get("structured_output")
            if not stage.get("ok") or not isinstance(payload, dict) or "verdict" not in payload:
                continue

            if role_name == "critic":
                round_index = 0
            else:
                round_index = next_auditor_round
                next_auditor_round += 1

            issues = [item for item in payload.get("issues", []) or [] if isinstance(item, dict)]
            missing_topics = [
                item for item in payload.get("missing_topics", []) or [] if str(item or "").strip()
            ]

            stage_scope_escapes: list[dict[str, Any]] = []
            for escape in payload.get("scope_escapes", []) or []:
                if not isinstance(escape, dict):
                    continue
                path = str(escape.get("path") or "").strip()
                reason = str(escape.get("reason") or "").strip()
                if not path and not reason:
                    continue
                escape_entry = {
                    "role_name": role_name,
                    "round_index": round_index,
                    "path": path,
                    "reason": reason,
                }
                stage_scope_escapes.append(escape_entry)
                scope_escapes.append(escape_entry)

            review_stages.append(
                {
                    "role_name": role_name,
                    "round_index": round_index,
                    "issue_count": len(issues),
                    "issue_cap": (
                        bounded_policy.get("critic_issue_cap") if role_name == "critic" else None
                    ),
                    "missing_topic_count": len(missing_topics),
                    "missing_topic_cap": (
                        bounded_policy.get("critic_new_topic_cap") if role_name == "critic" else None
                    ),
                    "new_medium_or_higher_issue_count": self._count_new_medium_or_higher_review_issues(
                        role_name=role_name,
                        round_index=round_index,
                        issues=issues,
                        issue_ledger=issue_ledger,
                    ),
                    "new_medium_or_higher_issue_cap": (
                        bounded_policy.get("auditor_new_medium_or_higher_issue_cap_after_round0")
                        if role_name == "auditor" and round_index > 0
                        else None
                    ),
                    "scope_escape_count": len(stage_scope_escapes),
                }
            )

        return {
            "mode": "recommendation_review_surface",
            "policy": bounded_policy,
            "recommendation_count": len(recommendations),
            "recommendations_with_review_surface": sum(
                1
                for item in recommendations
                if isinstance(item, dict) and isinstance(item.get("review_surface"), dict)
            ),
            "review_stages": review_stages,
            "scope_escape_count": len(scope_escapes),
            "scope_escapes": scope_escapes,
        }

    def _resolve_bounded_review_analysis_payload(self, run_details: dict[str, Any]) -> dict[str, Any]:
        final_analysis = run_details.get("final_analysis")
        if isinstance(final_analysis, dict) and final_analysis:
            return final_analysis

        for stage in reversed(self.agent_stages):
            if not isinstance(stage, dict):
                continue
            role_name = str(stage.get("role_name") or "").strip()
            if not role_name.startswith("reviser_round_"):
                continue
            payload = stage.get("structured_output")
            if stage.get("ok") and isinstance(payload, dict) and payload:
                return payload

        for stage in self.agent_stages:
            if not isinstance(stage, dict):
                continue
            if str(stage.get("role_name") or "").strip() != "proposer":
                continue
            payload = stage.get("structured_output")
            if stage.get("ok") and isinstance(payload, dict) and payload:
                return payload
        return {}

    @staticmethod
    def _count_medium_or_higher_review_issues(issues: list[dict[str, Any]]) -> int:
        return sum(
            1
            for issue in issues
            if str(issue.get("severity") or "").strip().lower() in {"medium", "high", "critical"}
        )

    def _count_new_medium_or_higher_review_issues(
        self,
        *,
        role_name: str,
        round_index: int,
        issues: list[dict[str, Any]],
        issue_ledger: list[dict[str, Any]],
    ) -> int:
        if role_name == "critic":
            return self._count_medium_or_higher_review_issues(issues)

        current_issue_ids = {
            str(issue.get("issue_id") or "").strip()
            for issue in issues
            if str(issue.get("issue_id") or "").strip()
        }
        if current_issue_ids:
            return sum(
                1
                for record in issue_ledger
                if isinstance(record, dict)
                and str(record.get("issue_id") or "").strip() in current_issue_ids
                and str(record.get("severity") or "").strip().lower() in {"medium", "high", "critical"}
                and record.get("first_seen_round") == round_index
            )

        return sum(
            1
            for issue in issues
            if str(issue.get("severity") or "").strip().lower() in {"medium", "high", "critical"}
            and str(issue.get("why_not_raised_earlier") or "").strip()
        )

    @staticmethod
    def _count_review_issues(review_payload: dict[str, Any], severities: set[str]) -> int:
        return sum(
            1
            for issue in review_payload.get("issues", [])
            if str(issue.get("severity", "")).lower() in severities
        )

    def _analysis_warning_causes(
        self,
        review_payload: dict[str, Any],
        *,
        final_analysis_payload: dict[str, Any] | None,
    ) -> list[str]:
        causes: list[str] = []
        if self._count_review_issues(review_payload, {"low"}):
            causes.append("low-severity reviewer issues remain open")
        if review_payload.get("missing_topics"):
            causes.append("reviewer missing_topics remain open")
        accepted_caveat_indices = self._accepted_caveat_recommendation_indices(review_payload)
        if accepted_caveat_indices:
            causes.append(
                "accepted recommendation reviews include accept_with_caveat: "
                + ", ".join(str(item) for item in accepted_caveat_indices)
            )
        contract = self._analysis_contract()
        if contract.mode == "trust":
            semantic_warning_records = self._final_semantic_warning_records()
            if contract.trust_review.downgrade_on_semantic_warnings and semantic_warning_records:
                causes.append(
                    "semantic validation warnings remain: "
                    + "; ".join(record["warning"] for record in semantic_warning_records)
                )
            inferred_indices = self._accepted_inferred_recommendation_indices(
                final_analysis_payload,
                review_payload,
            )
            if contract.trust_review.downgrade_on_inferred_acceptance and inferred_indices:
                causes.append(
                    "accepted recommendations rely on inference-only grounding: "
                    + ", ".join(str(item) for item in inferred_indices)
                )
            provenance_status = self._final_payload_provenance_status()
            if (
                contract.trust_review.payload_provenance_mode == "payload_hash_and_refs"
                and provenance_status != "bound"
            ):
                causes.append("final payload provenance is not fully bound")
        return causes

    def _analysis_contract(self) -> AnalysisReviewContract:
        if self.analysis_review_contract is None:
            self.analysis_review_contract = build_analysis_review_contract(self.task, self.strategy)
        return self.analysis_review_contract

    def _next_issue_id(self, reserved_ids: set[str] | None = None) -> str:
        reserved = set(self._issue_ledger_by_id)
        if reserved_ids:
            reserved.update(reserved_ids)
        index = 1
        while True:
            issue_id = f"AR-{index:03d}"
            if issue_id not in reserved:
                return issue_id
            index += 1

    def _open_issue_records(self) -> list[dict[str, Any]]:
        return [
            json.loads(json.dumps(record))
            for record in self.issue_ledger
            if str(record.get("resolution_status") or "") in {"open", "carried_forward"}
        ]

    def _serialized_issue_ledger(self) -> list[dict[str, Any]]:
        return [json.loads(json.dumps(record)) for record in self.issue_ledger]

    def _normalize_review_issue(
        self,
        issue: dict[str, Any],
        *,
        round_index: int,
        reserved_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(issue)
        issue_id = str(normalized.get("issue_id") or "").strip()
        if not issue_id:
            issue_id = self._next_issue_id(reserved_ids)
        normalized["issue_id"] = issue_id
        normalized["severity"] = str(normalized.get("severity") or "low").strip().lower()
        normalized["kind"] = str(normalized.get("kind") or "other").strip().lower()
        normalized["blocking_class"] = str(
            normalized.get("blocking_class") or default_blocking_class_for_kind(normalized.get("kind"))
        ).strip().lower()
        recommendation_index = normalized.get("recommendation_index")
        try:
            normalized["recommendation_index"] = (
                None if recommendation_index in (None, "") else int(recommendation_index)
            )
        except (TypeError, ValueError):
            normalized["recommendation_index"] = None
        normalized["title"] = str(normalized.get("title") or normalized.get("summary") or "Issue")
        normalized["evidence"] = str(normalized.get("evidence") or "")
        normalized["repair_hint"] = str(normalized.get("repair_hint") or "")
        why_not_raised_earlier = normalized.get("why_not_raised_earlier")
        normalized["why_not_raised_earlier"] = (
            None if why_not_raised_earlier in (None, "") else str(why_not_raised_earlier)
        )
        if round_index > 0 and issue_id not in self._issue_ledger_by_id:
            if normalized["severity"] in {"medium", "high", "critical"} and not normalized["why_not_raised_earlier"]:
                self.warnings.append(
                    f"{issue_id} was introduced as a new medium-or-higher issue in round {round_index} without why_not_raised_earlier."
                )
        return normalized

    def _resolution_note_from_reviser(
        self,
        reviser_output: dict[str, Any] | None,
        issue_id: str,
    ) -> str:
        if not isinstance(reviser_output, dict):
            return ""
        for item in reviser_output.get("issue_resolution_map", []) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("issue_id") or "") != issue_id:
                continue
            status = str(item.get("status") or "")
            change_summary = str(item.get("change_summary") or "")
            residual_risk = str(item.get("residual_risk") or "")
            note_bits = [bit for bit in (status, change_summary, residual_risk) if bit]
            return " | ".join(note_bits)
        return ""

    def _ingest_review_payload(
        self,
        review_payload: dict[str, Any],
        *,
        round_index: int,
        role_name: str,
        reviser_output: dict[str, Any] | None,
    ) -> None:
        if not isinstance(review_payload, dict) or not review_payload:
            return

        stage_id = f"stage-{self.stage_counter:02d}-{slugify(role_name)}"
        prior_open_ids = {
            str(record.get("issue_id"))
            for record in self.issue_ledger
            if str(record.get("resolution_status") or "") in {"open", "carried_forward"}
        }
        normalized_issues = []
        reserved_ids = set(self._issue_ledger_by_id)
        for issue in review_payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            normalized_issue = self._normalize_review_issue(
                issue,
                round_index=round_index,
                reserved_ids=reserved_ids,
            )
            reserved_ids.add(str(normalized_issue.get("issue_id")))
            normalized_issues.append(normalized_issue)
        current_issue_ids = {str(item.get("issue_id")) for item in normalized_issues}
        resolved_ids = {str(item) for item in review_payload.get("resolved_issue_ids", []) if str(item).strip()}
        carried_ids = {str(item) for item in review_payload.get("carried_forward_issue_ids", []) if str(item).strip()}
        waived_ids = {str(item) for item in review_payload.get("waived_issue_ids", []) if str(item).strip()}

        for issue_id in prior_open_ids:
            record = self._issue_ledger_by_id.get(issue_id)
            if record is None:
                continue
            if issue_id in resolved_ids:
                record["resolution_status"] = "resolved"
                record["resolution_note"] = self._resolution_note_from_reviser(reviser_output, issue_id)
                record["last_seen_round"] = round_index
            elif issue_id in waived_ids:
                record["resolution_status"] = "waived"
                record["last_seen_round"] = round_index
            elif issue_id in current_issue_ids or issue_id in carried_ids:
                record["resolution_status"] = "carried_forward"
                record["last_seen_round"] = round_index
            else:
                self.warnings.append(
                    f"Review stage '{role_name}' did not explicitly classify prior open issue {issue_id}; treating it as carried_forward."
                )
                record["resolution_status"] = "carried_forward"
                record["last_seen_round"] = round_index

        for issue in normalized_issues:
            issue_id = str(issue.get("issue_id"))
            if issue_id in self._issue_ledger_by_id:
                record = self._issue_ledger_by_id[issue_id]
                record.update(
                    {
                        "source_stage_id": stage_id,
                        "last_seen_round": round_index,
                        "severity": issue.get("severity"),
                        "kind": issue.get("kind"),
                        "blocking_class": issue.get("blocking_class"),
                        "recommendation_index": issue.get("recommendation_index"),
                        "title": issue.get("title"),
                        "evidence": issue.get("evidence"),
                        "repair_hint": issue.get("repair_hint"),
                        "why_not_raised_earlier": issue.get("why_not_raised_earlier"),
                        "resolution_status": (
                            "carried_forward" if issue_id in prior_open_ids else "open"
                        ),
                    }
                )
            else:
                record = {
                    "issue_id": issue_id,
                    "source_stage_id": stage_id,
                    "first_seen_round": round_index,
                    "last_seen_round": round_index,
                    "severity": issue.get("severity"),
                    "kind": issue.get("kind"),
                    "blocking_class": issue.get("blocking_class"),
                    "recommendation_index": issue.get("recommendation_index"),
                    "title": issue.get("title"),
                    "evidence": issue.get("evidence"),
                    "repair_hint": issue.get("repair_hint"),
                    "why_not_raised_earlier": issue.get("why_not_raised_earlier"),
                    "resolution_status": "open",
                    "resolution_note": "",
                }
                self.issue_ledger.append(record)
                self._issue_ledger_by_id[issue_id] = record

    @staticmethod
    def _recommendation_reviews(review_payload: dict[str, Any]) -> list[dict[str, Any]]:
        reviews = []
        for item in review_payload.get("recommendation_reviews", []) or []:
            if isinstance(item, dict):
                reviews.append(item)
        reviews.sort(key=lambda item: int(item.get("recommendation_index") or 0))
        return reviews

    def _accepted_recommendation_reviews(self, review_payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            item
            for item in self._recommendation_reviews(review_payload)
            if str(item.get("verdict") or "").strip().lower() in {"accept", "accept_with_caveat"}
        ]

    def _has_recommendation_caveats(self, review_payload: dict[str, Any]) -> bool:
        return any(
            str(item.get("verdict") or "").strip().lower() == "accept_with_caveat"
            for item in self._recommendation_reviews(review_payload)
        )

    def _accepted_caveat_recommendation_indices(self, review_payload: dict[str, Any]) -> list[int]:
        indices: list[int] = []
        for item in self._recommendation_reviews(review_payload):
            if str(item.get("verdict") or "").strip().lower() != "accept_with_caveat":
                continue
            try:
                indices.append(int(item.get("recommendation_index")))
            except (TypeError, ValueError):
                continue
        return sorted(set(indices))

    def _accepted_inferred_recommendation_indices(
        self,
        final_analysis_payload: dict[str, Any] | None,
        review_payload: dict[str, Any],
    ) -> list[int]:
        if not isinstance(final_analysis_payload, dict):
            return []
        recommendations = final_analysis_payload.get("recommendations")
        if not isinstance(recommendations, list):
            return []
        accepted_indices: set[int] = set()
        for item in self._accepted_recommendation_reviews(review_payload):
            raw_index = item.get("recommendation_index")
            if raw_index in (None, ""):
                continue
            try:
                accepted_indices.add(int(raw_index))
            except (TypeError, ValueError):
                continue
        inferred_indices: list[int] = []
        for index, item in enumerate(recommendations, start=1):
            if index not in accepted_indices or not isinstance(item, dict):
                continue
            if str(item.get("grounding_mode") or "").strip().lower() == "inferred":
                inferred_indices.append(index)
        return inferred_indices

    def _latest_successful_stage(self, *, role_names: set[str] | None = None) -> dict[str, Any] | None:
        for stage in reversed(self.agent_stages):
            if not isinstance(stage, dict) or not stage.get("ok"):
                continue
            role_name = str(stage.get("role_name") or "").strip()
            if role_names is not None and role_name not in role_names:
                continue
            payload = stage.get("structured_output")
            if isinstance(payload, dict) and payload:
                return stage
        return None

    def _final_semantic_warning_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        final_stages = [
            self._resolve_bounded_review_analysis_stage(),
            self._latest_successful_stage(role_names={"critic", "auditor"}),
        ]
        seen_keys: set[tuple[Any, Any, Any]] = set()
        for stage in final_stages:
            if not isinstance(stage, dict):
                continue
            for warning in stage.get("semantic_validation_warnings") or []:
                key = (stage.get("stage_index"), stage.get("role_name"), warning)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                records.append(
                    {
                        "stage_index": stage.get("stage_index"),
                        "role_name": stage.get("role_name"),
                        "warning": warning,
                    }
                )
        return records

    def _final_payload_provenance_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        stage_specs = (
            ("analysis", self._resolve_bounded_review_analysis_stage()),
            ("review", self._latest_successful_stage(role_names={"critic", "auditor"})),
        )
        for surface, stage in stage_specs:
            if not isinstance(stage, dict):
                continue
            provenance = stage.get("semantic_validation_payload_provenance")
            if not isinstance(provenance, dict):
                provenance = {"status": "missing"}
            record = {
                "surface": surface,
                "stage_index": stage.get("stage_index"),
                "role_name": stage.get("role_name"),
                "status": provenance.get("status") or "missing",
                "policy_mode": provenance.get("policy_mode") or "none",
                "payload_sha256": provenance.get("payload_sha256"),
                "normalized_ref_field_count": provenance.get("normalized_ref_field_count", 0),
                "normalized_ref_count": provenance.get("normalized_ref_count", 0),
            }
            records.append(record)
        return records

    def _final_payload_provenance_status(self) -> str:
        records = self._final_payload_provenance_records()
        if not records:
            return "missing"
        statuses = {str(item.get("status") or "missing") for item in records}
        if statuses == {"bound"}:
            return "bound"
        if "bound" in statuses:
            return "partial"
        if "not_required" in statuses and statuses <= {"not_required", "missing"}:
            return "not_required"
        return "missing"

    def _build_analysis_review_status(
        self,
        *,
        final_analysis_payload: dict[str, Any],
        final_review_payload: dict[str, Any],
        content_verdict: str,
    ) -> dict[str, Any]:
        contract = self._analysis_contract()
        semantic_warning_records = self._final_semantic_warning_records()
        provenance_records = self._final_payload_provenance_records()
        accepted_caveat_indices = self._accepted_caveat_recommendation_indices(final_review_payload)
        inferred_indices = self._accepted_inferred_recommendation_indices(
            final_analysis_payload,
            final_review_payload,
        )
        downgrade_causes = self._analysis_warning_causes(
            final_review_payload,
            final_analysis_payload=final_analysis_payload,
        )
        provenance_status = self._final_payload_provenance_status()
        if contract.trust_review.payload_provenance_mode == "none" and provenance_status == "missing":
            provenance_status = "not_required"
        return {
            "mode": contract.mode,
            "content_verdict": content_verdict,
            "semantic_warning_count": len(semantic_warning_records),
            "semantic_warnings": semantic_warning_records,
            "provenance": {
                "status": provenance_status,
                "policy_mode": contract.trust_review.payload_provenance_mode,
                "required": contract.trust_review.payload_provenance_mode == "payload_hash_and_refs",
                "stages": provenance_records,
            },
            "accepted_recommendations_with_caveats": accepted_caveat_indices,
            "accepted_recommendations_with_inferred_grounding": inferred_indices,
            "downgrade_causes": downgrade_causes,
        }

    def _blocking_issues(self, review_payload: dict[str, Any]) -> list[dict[str, Any]]:
        blocking: list[dict[str, Any]] = []
        for issue in review_payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            severity = str(issue.get("severity") or "").strip().lower()
            blocking_class = str(issue.get("blocking_class") or "presentation").strip().lower()
            if severity in {"medium", "high", "critical"} and blocking_class in {
                "correctness",
                "actionability",
                "completeness",
            }:
                blocking.append(issue)
        return blocking

    def _score_threshold_failures(self, review_payload: dict[str, Any]) -> list[str]:
        policy = self._analysis_contract().stop_policy
        failures: list[str] = []
        score_checks = [
            ("grounding_score", policy.min_grounding_score),
            ("actionability_score", policy.min_actionability_score),
            ("scope_compliance_score", policy.min_scope_compliance_score),
        ]
        for field_name, threshold in score_checks:
            if threshold is None:
                continue
            value = review_payload.get(field_name)
            if value is None:
                failures.append(field_name)
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                failures.append(field_name)
                continue
            if numeric_value < threshold:
                failures.append(field_name)
        return failures

    def _analysis_can_fully_accept(self, review_payload: dict[str, Any]) -> bool:
        if not review_payload:
            return False
        if str(review_payload.get("verdict") or "").strip().lower() != "accept":
            return False
        if self._count_review_issues(review_payload, {"medium", "high", "critical"}) > 0:
            return False
        if self._score_threshold_failures(review_payload):
            return False
        recommendation_reviews = self._recommendation_reviews(review_payload)
        if recommendation_reviews and any(
            str(item.get("verdict") or "").strip().lower() not in {"accept", "accept_with_caveat"}
            for item in recommendation_reviews
        ):
            return False
        return True

    def _analysis_can_partially_accept(self, review_payload: dict[str, Any]) -> bool:
        contract = self._analysis_contract()
        policy = contract.partial_acceptance
        if not policy.enabled:
            return False
        if str(review_payload.get("verdict") or "").strip().lower() == "reject":
            return False

        accepted_reviews = self._accepted_recommendation_reviews(review_payload)
        if len(accepted_reviews) < policy.min_accepted_recommendations:
            return False

        issues_by_id: dict[str, dict[str, Any]] = {}
        for issue in review_payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            issues_by_id[str(issue.get("issue_id") or "")] = issue
            severity = str(issue.get("severity") or "").strip().lower()
            recommendation_index = issue.get("recommendation_index")
            blocking_class = str(issue.get("blocking_class") or "presentation").strip().lower()
            if recommendation_index in (None, "") and severity in {"medium", "high", "critical"} and blocking_class in {
                "correctness",
                "actionability",
                "completeness",
            }:
                return False
            if recommendation_index in (None, "") and severity in {"high", "critical"}:
                return False

        for review in accepted_reviews:
            for issue_id in review.get("open_issue_ids", []) or []:
                issue = issues_by_id.get(str(issue_id))
                if not isinstance(issue, dict):
                    continue
                severity = str(issue.get("severity") or "").strip().lower()
                blocking_class = str(issue.get("blocking_class") or "presentation").strip().lower()
                if severity in {"high", "critical"}:
                    return False
                if severity == "medium" and blocking_class in {
                    "correctness",
                    "actionability",
                    "completeness",
                }:
                    return False

        return True

    def _require_role(self, role_name: str) -> RoleConfig:
        role = self.strategy.roles.get(role_name)
        if role is None:
            raise HarnessError(f"Strategy requires role: {role_name}")
        return role

    def _role_or_fallback(self, preferred: str, fallbacks: list[str]) -> RoleConfig:
        if preferred in self.strategy.roles:
            return self.strategy.roles[preferred]
        for name in fallbacks:
            if name in self.strategy.roles:
                self.warnings.append(
                    f"Strategy role '{preferred}' is not configured; using '{name}' as a fallback."
                )
                return self.strategy.roles[name]
        raise HarnessError(
            f"Strategy requires role '{preferred}' or one of these fallbacks: {', '.join(fallbacks)}"
        )

    def _workspace_ignored_rel_paths(self) -> list[str]:
        if self.out_root == self.workspace:
            raise HarnessError(
                "--out-root cannot be the same directory as --workspace. "
                "Artifacts must live outside the target workspace or in a dedicated subdirectory."
            )
        try:
            rel = self.out_root.relative_to(self.workspace)
        except ValueError:
            return []
        rel_str = rel.as_posix().strip("/")
        return [rel_str] if rel_str else []

    def _normalize_workspace_ref(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "://" in text:
            return text
        normalized = text.replace("\\", "/")
        candidate = Path(normalized)
        if candidate.is_absolute():
            try:
                normalized = candidate.resolve(strict=False).relative_to(self.workspace).as_posix()
            except ValueError:
                return candidate.as_posix()
        else:
            normalized = posixpath.normpath(normalized)
            if normalized == ".":
                return ""
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

    def _normalize_workspace_ref_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        normalized: list[str] = []
        for item in values:
            if not isinstance(item, str):
                continue
            value = self._normalize_workspace_ref(item)
            if value:
                normalized.append(value)
        return normalized

    def _bind_normalized_payload(
        self,
        payload: dict[str, Any],
        *,
        payload_provenance_mode: str,
        normalized_refs: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_ref_count = 0
        for value in normalized_refs.values():
            if isinstance(value, list):
                normalized_ref_count += len(value)
            elif value:
                normalized_ref_count += 1
        if payload_provenance_mode == "none":
            return {
                "status": "not_required",
                "policy_mode": payload_provenance_mode,
                "normalized_ref_field_count": len(normalized_refs),
                "normalized_ref_count": normalized_ref_count,
            }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return {
            "status": "bound",
            "binding_method": "payload_hash_and_refs",
            "policy_mode": payload_provenance_mode,
            "payload_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            "normalized_ref_field_count": len(normalized_refs),
            "normalized_ref_count": normalized_ref_count,
            "normalized_refs": normalized_refs,
        }

    def _normalize_analysis_review_payload(
        self,
        payload: dict[str, Any],
        *,
        payload_provenance_mode: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        normalized = json.loads(json.dumps(payload))
        normalized_refs: dict[str, Any] = {}

        files_reviewed = self._normalize_workspace_ref_list(normalized.get("files_reviewed"))
        if files_reviewed:
            normalized["files_reviewed"] = files_reviewed
            normalized_refs["files_reviewed"] = files_reviewed

        recommendations = normalized.get("recommendations")
        if isinstance(recommendations, list):
            for index, item in enumerate(recommendations, start=1):
                if not isinstance(item, dict):
                    continue
                for field_name in (
                    "evidence",
                    "verified_evidence_refs",
                    "checked_files",
                    "affected_files",
                ):
                    values = self._normalize_workspace_ref_list(item.get(field_name))
                    if values:
                        item[field_name] = values
                        normalized_refs[f"recommendations[{index}].{field_name}"] = values
                review_surface = item.get("review_surface")
                if isinstance(review_surface, dict):
                    for field_name in ("must_check_files", "optional_check_files"):
                        values = self._normalize_workspace_ref_list(review_surface.get(field_name))
                        if values:
                            review_surface[field_name] = values
                            normalized_refs[
                                f"recommendations[{index}].review_surface.{field_name}"
                            ] = values

        scope_escapes = normalized.get("scope_escapes")
        if isinstance(scope_escapes, list):
            for index, item in enumerate(scope_escapes, start=1):
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or "").strip()
                if not path:
                    continue
                normalized_path = self._normalize_workspace_ref(path)
                item["path"] = normalized_path or path
                normalized_refs[f"scope_escapes[{index}].path"] = item["path"]

        return normalized, self._bind_normalized_payload(
            normalized,
            payload_provenance_mode=payload_provenance_mode,
            normalized_refs=normalized_refs,
        )

    def _resolve_bounded_review_analysis_stage(self) -> dict[str, Any] | None:
        reviser_role_names = {
            str(stage.get("role_name") or "")
            for stage in self.agent_stages
            if str(stage.get("role_name") or "").startswith("reviser_round_")
        }
        if reviser_role_names:
            stage = self._latest_successful_stage(role_names=reviser_role_names)
            if stage is not None:
                return stage
        return self._latest_successful_stage(role_names={"proposer"})

    def _effective_role_config(self, role_name: str, role_config: RoleConfig) -> RoleConfig:
        effective_access = role_config.access
        forced_read_roles = {"falsifier", "critic", "auditor"}
        if role_name in forced_read_roles:
            effective_access = "read"
        elif not self.task.workspace_write_policy.allows_workspace_writes():
            effective_access = "read"
        return replace(role_config, access=effective_access)

    def _emit_task_strategy_warnings(self) -> None:
        if self.strategy.kind == ANALYSIS_REVIEW_LEGACY_KIND:
            self.warnings.append(
                "Strategy kind analysis_review_v1 is deprecated and now resolves to analysis_review_bounded_v1."
            )
        if self.task.task_kind == "analysis_review" and self.strategy.kind in {"pfr_v1", "single_pass"}:
            self.warnings.append(
                "This task looks like an analysis_review task, but the selected strategy is patch-oriented. "
                "analysis_review_bounded_v1 or analysis_review_trust_v1 will usually be a better fit."
            )
        if self.task.task_kind == "patch" and is_analysis_review_strategy_kind(self.strategy.kind):
            self.warnings.append(
                f"This task requires a patch-oriented workflow, but the selected strategy is {self.strategy.kind}."
            )

    def _copy_role_if_missing(self, missing_role: str, source_roles: list[str]) -> None:
        if missing_role in self.strategy.roles:
            return
        for source in source_roles:
            if source in self.strategy.roles:
                self.strategy.roles[missing_role] = self.strategy.roles[source]
                return

    def _apply_strategy_autofit(self) -> None:
        if self.strategy.kind == ANALYSIS_REVIEW_LEGACY_KIND:
            self.strategy.kind = ANALYSIS_REVIEW_BOUNDED_KIND
        if self.task.task_kind == "analysis_review" and self.strategy.kind == "pfr_v1":
            if not self.auto_fit_strategy:
                self.errors.append(
                    "analysis_review tasks are incompatible with pfr_v1 unless auto-fit is enabled."
                )
                return
            self.strategy.kind = ANALYSIS_REVIEW_BOUNDED_KIND
            self._copy_role_if_missing("critic", ["falsifier"])
            self._copy_role_if_missing("reviser", ["patcher", "proposer"])
            self._copy_role_if_missing("auditor", ["critic", "falsifier"])
            self.warnings.append(
                "Auto-fit changed strategy kind from pfr_v1 to analysis_review_bounded_v1 for an analysis_review task."
            )
        elif self.task.task_kind == "patch" and is_analysis_review_strategy_kind(self.strategy.kind):
            original_kind = self.strategy.kind
            if not self.auto_fit_strategy:
                self.errors.append(
                    f"patch tasks are incompatible with {original_kind} unless auto-fit is enabled."
                )
                return
            self.strategy.kind = "pfr_v1"
            self._copy_role_if_missing("falsifier", ["critic", "auditor"])
            self._copy_role_if_missing("patcher", ["reviser", "proposer"])
            self.warnings.append(
                f"Auto-fit changed strategy kind from {original_kind} to pfr_v1 for a patch task."
            )

    def _validator_preflight_outcome(self) -> dict[str, Any] | None:
        if self.errors:
            return {
                "run_verdict": "invalid_config",
                "content_verdict": "rejected",
                "validator_verdict": "misconfigured",
                "config_verdict": "invalid_config",
                "final_summary": self.errors[0],
                "failure_details": {"preflight_errors": list(self.errors)},
                "details": {},
            }

        preflight = preflight_validators(
            self.strategy.validators,
            self.workspace,
            task=self.task,
            strategy=self.strategy,
            workspace_changed=False,
        )
        self.validator_preflight = preflight

        preflight_errors: list[str] = []
        for item in preflight:
            status = str(item.get("status") or "")
            if item.get("required") and status in {"failed", "not_applicable"}:
                reason = str(item.get("reason") or f"Validator {item.get('name')} is misconfigured.")
                preflight_errors.append(reason)
            elif not item.get("required") and status in {"failed", "not_applicable"}:
                self.warnings.append(str(item.get("reason") or f"Optional validator {item.get('name')} is not applicable."))

        if not preflight_errors:
            return None

        self.errors.extend(preflight_errors)
        return {
            "run_verdict": "invalid_config",
            "content_verdict": "rejected",
            "validator_verdict": "misconfigured",
            "config_verdict": "invalid_config",
            "final_summary": preflight_errors[0],
            "failure_details": {"preflight_errors": preflight_errors, "validator_preflight": preflight},
            "details": {},
        }

    def _enforce_clean_start_if_required(self) -> None:
        if not self.task.workspace_write_policy.require_clean_start:
            return
        if self.initial_git_snapshot and self.initial_git_snapshot.get("is_git"):
            dirty_paths = changed_files(self.initial_git_snapshot)
            if dirty_paths:
                evaluation = {
                    "checkpoint": "start",
                    "final": False,
                    "policy_mode": self.task.workspace_write_policy.mode,
                    "touched_files": dirty_paths,
                    "modified_files": dirty_paths,
                    "added_files": [],
                    "deleted_files": [],
                    "renamed_files": [],
                    "new_untracked_files": [],
                    "notes": [],
                    "violations": [
                        "workspace_write_policy.require_clean_start=true, but the workspace started dirty: "
                        + ", ".join(dirty_paths[:8])
                        + (f", ... (+{len(dirty_paths) - 8} more)" if len(dirty_paths) > 8 else "")
                    ],
                    "ok": False,
                }
                self.workspace_policy_checks.append(evaluation)
                raise WorkspacePolicyViolationError("start", evaluation)

    def _evaluate_workspace_policy(
        self,
        *,
        current_git_snapshot: dict[str, Any],
        current_non_git_state: dict[str, Any] | None,
        final: bool,
        checkpoint: str,
    ) -> dict[str, Any]:
        return evaluate_workspace_write_policy(
            cwd=self.workspace,
            initial_git_snapshot=self.initial_git_snapshot,
            current_git_snapshot=current_git_snapshot,
            initial_non_git_state=self.initial_non_git_state,
            current_non_git_state=current_non_git_state,
            policy=self.task.workspace_write_policy,
            final=final,
            checkpoint=checkpoint,
        )

    def _record_workspace_policy_check(
        self,
        *,
        checkpoint: str,
        final: bool,
        raise_on_violation: bool,
    ) -> dict[str, Any]:
        current_git_snapshot = capture_git_snapshot(
            self.workspace,
            ignored_rel_paths=self.policy_ignored_rel_paths,
        )
        current_non_git_state = None
        if not current_git_snapshot.get("is_git"):
            current_non_git_state = capture_non_git_workspace_state(
                self.workspace,
                ignored_rel_paths=self.policy_ignored_rel_paths,
            )
        evaluation = self._evaluate_workspace_policy(
            current_git_snapshot=current_git_snapshot,
            current_non_git_state=current_non_git_state,
            final=final,
            checkpoint=checkpoint,
        )
        self.workspace_policy_checks.append(evaluation)
        if evaluation.get("violations") and raise_on_violation:
            raise WorkspacePolicyViolationError(checkpoint, evaluation)
        return evaluation

    @staticmethod
    def _classify_validator_verdict(results: list[ValidationRun]) -> str:
        if not results:
            return "not_configured"
        required = [result for result in results if result.required]
        if not required:
            return "advisory_only"
        if any(result.status in {"failed", "error"} for result in required):
            return "required_failures"
        if any(result.status == "not_applicable" for result in required):
            return "misconfigured"
        if all(result.status == "skipped" for result in required):
            return "not_run"
        return "pass"

    @staticmethod
    def _combine_run_verdict(content_verdict: str, validator_verdict: str) -> str:
        if content_verdict == "harness_error":
            return "harness_error"
        if validator_verdict == "misconfigured":
            return "invalid_config"
        return content_verdict

    def _derive_final_answer_payload(self, run_details: dict[str, Any]) -> dict[str, Any] | None:
        candidate_keys = ("final_analysis", "final_solution")
        for key in candidate_keys:
            candidate = run_details.get(key)
            if isinstance(candidate, dict) and candidate:
                return candidate
        return None

    def _write_final_answer_artifacts(self, payload: dict[str, Any] | None) -> dict[str, str]:
        if not payload:
            return {}
        final_json_path = self.run_dir / "FINAL_ANSWER.json"
        final_md_path = self.run_dir / "FINAL_ANSWER.md"
        write_json(final_json_path, payload)
        write_text(final_md_path, self._render_final_answer_markdown(payload))
        return {
            "final_answer_json": str(final_json_path),
            "final_answer_md": str(final_md_path),
        }

    def _render_final_answer_markdown(self, payload: dict[str, Any]) -> str:
        lines: list[str] = [f"# Final Answer: {self.task.id}", ""]
        summary_text = str(payload.get("summary", "")).strip()
        if summary_text:
            lines.extend(["## Summary", "", summary_text, ""])

        recommendations = payload.get("recommendations")
        if isinstance(recommendations, list) and recommendations:
            lines.extend(["## Recommendations", ""])
            for idx, item in enumerate(recommendations, start=1):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or f"Recommendation {idx}")
                classification = str(item.get("classification", "")).strip()
                priority = str(item.get("priority", "")).strip()
                header_bits = [title]
                meta_bits = [bit for bit in (classification, priority) if bit]
                if meta_bits:
                    header_bits.append(f"({', '.join(meta_bits)})")
                lines.append(f"### {idx}. {' '.join(header_bits)}")
                lines.append("")
                for field_name, label in (
                    ("rationale", "Rationale"),
                    ("proposed_change", "Suggested change"),
                ):
                    value = item.get(field_name)
                    if value:
                        lines.extend([f"**{label}:** {value}", ""])
                evidence = item.get("evidence")
                if isinstance(evidence, list) and evidence:
                    lines.append("**Evidence:**")
                    for evidence_item in evidence:
                        lines.append(f"- {evidence_item}")
                    lines.append("")
                confidence = item.get("confidence")
                if confidence is not None:
                    lines.extend([f"**Confidence:** {confidence}", ""])
        else:
            lines.extend(["## Structured Output", "", "```json", json.dumps(payload, indent=2, sort_keys=False), "```", ""])
        return "\n".join(lines).rstrip() + "\n"

    def _latest_validator_results(self) -> list[ValidationRun]:
        if not self.validator_rounds:
            return []
        latest = self.validator_rounds[-1]
        results: list[ValidationRun] = []
        for item in latest.get("results", []):
            results.append(ValidationRun(**item))
        return results

    def _summarize_validator_rounds(self) -> dict[str, Any]:
        all_results: list[dict[str, Any]] = []
        for round_data in self.validator_rounds:
            for item in round_data.get("results", []):
                all_results.append(item)
        status_counts: dict[str, int] = {}
        required_status_counts: dict[str, int] = {}
        for item in all_results:
            status = str(item.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
            if item.get("required"):
                required_status_counts[status] = required_status_counts.get(status, 0) + 1
        latest_round_results = self._latest_validator_results()
        return {
            "total_runs": len(all_results),
            "status_counts": status_counts,
            "required_status_counts": required_status_counts,
            "latest_round_verdict": self._classify_validator_verdict(latest_round_results),
        }
