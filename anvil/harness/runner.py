from __future__ import annotations

import datetime as dt
import hashlib
import inspect
import json
import posixpath
import re
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from anvil.orchestrator import reload_config

from .contracts import (
    AnalysisReviewContract,
    PartialAcceptancePolicy,
    RecommendationAdmissibilityStatus,
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
    build_focus_gate_adjudicate_prompt,
    build_focus_gate_deliberate_prompt,
    build_focus_probe_prompt,
    build_patcher_prompt,
    build_proposer_prompt,
    build_single_pass_prompt,
)
from .providers import _soft_validate_schema, get_provider
from .reporting import apply_final_artifacts
from .schemas import (
    analysis_output_schema,
    analysis_review_schema,
    falsifier_schema,
    focus_gate_output_schema,
    focus_gate_probe_output_schema,
    patcher_schema,
    proposer_schema,
    single_pass_schema,
)
from .selection import extract_drafts_from_summary, select_best_draft
from .semantic_validation import validate_stage_output
from .topic_lifecycle import (
    partial_accept_topic_eligibility,
    topic_ids_for_status_name,
)
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

_PRIOR_SURFACED_REFS_FIELD = "_prior_surfaced_refs"
_FOCUS_MAX_CHECKED_FILES = 6
_FOCUS_MAX_EVIDENCE_REFS = 2
_FULLY_ACCEPTED_CONTENT_VERDICTS = {"accepted", "accepted_with_warnings"}
_TRUST_PUBLICATION_ADVISORY_WARNING_ALLOWLIST = {
    "strengths contains both concrete items and none_reason; prefer one or the other.",
    "uncertainties contains both concrete items and none_reason; prefer one or the other.",
}


class HarnessError(RuntimeError):
    pass


class WorkspacePolicyViolationError(HarnessError):
    def __init__(self, checkpoint: str, evaluation: dict[str, Any]) -> None:
        self.checkpoint = checkpoint
        self.evaluation = evaluation
        message = (
            "; ".join(evaluation.get("violations", []))
            or "Workspace write policy violated."
        )
        super().__init__(f"Workspace write policy violated at {checkpoint}: {message}")


_WORKSPACE_REF_LOCATION_SUFFIX_RE = re.compile(
    r"^(?P<path>.+?):(?P<ranges>\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)$"
)


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
        self._validate_inputs()
        task_payload = (
            task_data if task_data is not None else load_structured_file(self.task_path)
        )
        strategy_payload = (
            strategy_data
            if strategy_data is not None
            else load_structured_file(self.strategy_path)
        )
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
        self.topic_ledger: list[dict[str, Any]] = []
        self._topic_ledger_by_id: dict[str, dict[str, Any]] = {}
        self.policy_ignored_rel_paths = self._workspace_ignored_rel_paths()
        self.initial_git_snapshot: dict[str, Any] | None = None
        self.initial_non_git_state: dict[str, Any] | None = None

    def _validate_inputs(self) -> None:
        for label, path in (
            ("Task spec", self.task_path),
            ("Strategy spec", self.strategy_path),
        ):
            if not path.exists():
                raise HarnessError(f"{label} file not found: {path}")
            if not path.is_file():
                raise HarnessError(f"{label} path is not a file: {path}")

        if not self.workspace.exists():
            raise HarnessError(f"Workspace directory not found: {self.workspace}")
        if not self.workspace.is_dir():
            raise HarnessError(f"Workspace path is not a directory: {self.workspace}")

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

        if self.initial_git_snapshot.get("is_git") and git_snapshot_is_dirty(
            self.initial_git_snapshot
        ):
            self.warnings.append(
                "Workspace is dirty at start. The harness will operate on the existing working tree. "
                "Use workspace_write_policy.require_clean_start=true to block this."
            )

        try:
            self._emit_task_strategy_warnings()
            self._apply_strategy_autofit()
            if is_analysis_review_strategy_kind(self.strategy.kind):
                self.analysis_review_contract = build_analysis_review_contract(
                    self.task, self.strategy
                )
            write_json(self.run_dir / "task.effective.json", self.task.to_dict())
            write_json(
                self.run_dir / "strategy.effective.json", self.strategy.to_dict()
            )
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
                    raise HarnessError(
                        f"Unsupported strategy kind: {self.strategy.kind}"
                    )
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
            validator_verdict = self._classify_validator_verdict(
                self._latest_validator_results()
            )
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
        write_json(
            self.run_dir / "workspace.policy.final.json", final_policy_evaluation
        )

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
        focus_decision = run_details.get("focus_decision")
        if isinstance(focus_decision, dict) and focus_decision:
            run_details["focus_decision"] = focus_decision

        final_answer_payload = self._derive_final_answer_payload(run_details)
        recommendation_reviews = list(run_details.get("recommendation_reviews") or [])
        issue_ledger = list(
            run_details.get("issue_ledger") or self._serialized_issue_ledger()
        )
        topic_ledger = list(
            run_details.get("topic_ledger") or self._serialized_topic_ledger()
        )
        analysis_review_contract = (
            run_details.get("analysis_review_contract")
            if isinstance(run_details.get("analysis_review_contract"), dict)
            else (
                self.analysis_review_contract.to_dict()
                if self.analysis_review_contract is not None
                else None
            )
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
            "focus_decision": (
                focus_decision if isinstance(focus_decision, dict) else None
            ),
            "analysis_review_coverage": analysis_review_coverage,
            "issue_ledger": issue_ledger,
            "topic_ledger": topic_ledger,
            "recommendation_reviews": recommendation_reviews,
            "closure_proof_by_id": (
                ((analysis_review_status or {}).get("provenance") or {}).get(
                    "closure_proof_by_id"
                )
                if isinstance(analysis_review_status, dict)
                else {}
            ),
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
        summary["selected_draft_id"] = (
            best_draft.get("draft_id") if best_draft else None
        )
        summary = apply_final_artifacts(summary)
        return summary

    def _run_single_pass(self) -> dict[str, Any]:
        role = self.strategy.roles.get("solver") or self.strategy.roles.get("proposer")
        if role is None:
            raise HarnessError(
                "single_pass strategy requires a solver or proposer role"
            )

        git_snapshot = capture_git_snapshot(
            self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
        )
        prompt = build_single_pass_prompt(
            self.task, self.strategy.prompt_preamble, git_snapshot
        )
        stage = self._run_agent_stage(
            "solver", role.provider, prompt, single_pass_schema(), role
        )
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
            "run_verdict": self._combine_run_verdict(
                content_verdict, validator_verdict
            ),
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

        git_snapshot = capture_git_snapshot(
            self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
        )
        proposer_prompt = build_proposer_prompt(
            self.task, self.strategy.prompt_preamble, git_snapshot
        )
        proposer_run = self._run_agent_stage(
            "proposer",
            proposer_cfg.provider,
            proposer_prompt,
            proposer_schema(),
            proposer_cfg,
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
                capture_git_snapshot(
                    self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
                ),
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
                    "validator_verdict": self._classify_validator_verdict(
                        last_validation_runs
                    ),
                    "final_summary": f"Patcher stage failed: {patcher_run.error or 'unknown error'}",
                    "failure_details": {
                        "stage": f"patcher_round_{repair_round}",
                        "error": patcher_run.error,
                    },
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
                        "validator_verdict": self._classify_validator_verdict(
                            last_validation_runs
                        ),
                        "final_summary": f"Falsifier re-run failed: {last_falsifier_run.error or 'unknown error'}",
                        "failure_details": {
                            "stage": "falsifier_rerun",
                            "error": last_falsifier_run.error,
                        },
                    }

        required_failures = self._required_validator_failures(last_validation_runs)
        falsifier_payload = last_falsifier_run.structured_output or {}
        verdict_signal = falsifier_payload.get("verdict")
        validator_verdict = self._classify_validator_verdict(last_validation_runs)

        if required_failures:
            content_verdict = "rejected"
            final_summary = f"Required validators still fail after the repair loop ({len(required_failures)} failure(s))."
        elif verdict_signal == "reject":
            content_verdict = "needs_manual_review"
            final_summary = "Required validators pass, but the falsifier still recommends rejection."
        elif verdict_signal == "inconclusive":
            content_verdict = "accepted_with_warnings"
            final_summary = (
                "Required validators pass, but the falsifier remained inconclusive."
            )
        else:
            content_verdict = "accepted"
            final_summary = (
                "Required validators pass and the final falsifier verdict is accept."
            )

        if validator_verdict == "misconfigured":
            final_summary = (
                "The P/F/R loop completed, but one or more required validators were not applicable to this workspace. "
                "Check validator configuration."
            )

        return {
            "run_verdict": self._combine_run_verdict(
                content_verdict, validator_verdict
            ),
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
        focus_gate_cfg = self._focus_gate_role_config()

        focus_decision: dict[str, Any] | None = None
        if contract.focus_gate.enabled:
            focus_gate_outcome = self._run_focus_gate(
                contract=contract,
                role_cfg=focus_gate_cfg,
            )
            if focus_gate_outcome["kind"] == "blocked":
                return focus_gate_outcome["outcome"]
            if focus_gate_outcome["kind"] == "failed":
                return self._analysis_stage_failure_outcome(
                    stage_label="focus_gate",
                    run=focus_gate_outcome["run"],
                    validator_verdict="not_run",
                    review_loop_exercised=False,
                    final_analysis=None,
                    contract=contract,
                )
            focus_decision = focus_gate_outcome["focus_decision"]

        git_snapshot = capture_git_snapshot(
            self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
        )
        proposer_prompt = build_analysis_proposer_prompt(
            self.task,
            self.strategy.prompt_preamble,
            git_snapshot,
            contract,
            focus_decision=focus_decision,
        )
        proposer_run = self._run_agent_stage(
            "proposer",
            proposer_cfg.provider,
            proposer_prompt,
            analysis_output_schema(),
            proposer_cfg,
            semantic_context={
                "contract": contract,
                "expected_primary_seam_id": self._selected_focus_id(focus_decision),
                "expected_primary_seam_paths": self._selected_focus_paths(
                    focus_decision
                ),
                "selected_focus_paths": self._selected_focus_paths(focus_decision),
            },
        )
        if not proposer_run.ok:
            return self._analysis_stage_failure_outcome(
                stage_label="proposer",
                run=proposer_run,
                validator_verdict=self._classify_validator_verdict([]),
                review_loop_exercised=False,
                final_analysis=None,
                contract=contract,
            )

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
            if not self._analysis_needs_revision(
                latest_review_run.structured_output or {}, revisions_completed
            ):
                break
            revisions_completed += 1
            reviser_prompt = build_analysis_reviser_prompt(
                self.task,
                self.strategy.prompt_preamble,
                latest_analysis_run.structured_output,
                latest_review_run.structured_output,
                validation_runs,
                capture_git_snapshot(
                    self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
                ),
                revision_round=revisions_completed,
                contract=contract,
                open_issues=self._open_issue_records(),
                open_topics=self._open_topic_records(),
                focus_decision=focus_decision,
            )
            prior_analysis_payload = latest_analysis_run.structured_output
            next_analysis_run = self._run_agent_stage(
                f"reviser_round_{revisions_completed}",
                reviser_cfg.provider,
                reviser_prompt,
                analysis_output_schema(
                    require_issue_resolution_map=True,
                    require_topic_resolution_map=bool(self._open_topic_records()),
                ),
                reviser_cfg,
                semantic_context={
                    "contract": contract,
                    "open_issue_ids": [
                        str(item.get("issue_id"))
                        for item in self._open_issue_records()
                        if str(item.get("issue_id") or "").strip()
                    ],
                    "expected_open_topic_ids": [
                        str(item.get("topic_id"))
                        for item in self._open_topic_records()
                        if str(item.get("topic_id") or "").strip()
                    ],
                    "expected_primary_seam_id": self._selected_focus_id(focus_decision),
                    "expected_primary_seam_paths": self._selected_focus_paths(
                        focus_decision
                    ),
                    "selected_focus_paths": self._selected_focus_paths(focus_decision),
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
        accepted_recommendation_count = len(
            self._accepted_recommendation_reviews(final_review_payload)
        )

        return {
            "run_verdict": self._combine_run_verdict(
                content_verdict, validator_verdict
            ),
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
                "topic_ledger": self._serialized_topic_ledger(),
                "recommendation_reviews": self._recommendation_reviews(
                    final_review_payload
                ),
                "accepted_recommendation_count": accepted_recommendation_count,
                "analysis_review_status": analysis_review_status,
                "focus_decision": focus_decision,
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
            capture_git_snapshot(
                self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
            ),
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
        git_snapshot = capture_git_snapshot(
            self.workspace, ignored_rel_paths=self.policy_ignored_rel_paths
        )
        prior_open_issue_records = self._open_issue_records()
        prior_open_topic_records = self._open_topic_records()
        prior_open_issue_ids = [
            str(item.get("issue_id"))
            for item in prior_open_issue_records
            if str(item.get("issue_id") or "").strip()
        ]
        prior_open_topic_ids = [
            str(item.get("topic_id"))
            for item in prior_open_topic_records
            if str(item.get("topic_id") or "").strip()
        ]
        historical_topic_ids = [
            str(item.get("topic_id"))
            for item in self.topic_ledger
            if str(item.get("topic_id") or "").strip()
        ]
        expected_recommendation_count = 0
        if isinstance(prior_output, dict):
            recommendations = prior_output.get("recommendations")
            if isinstance(recommendations, list):
                expected_recommendation_count = len(recommendations)
        if role_name == "auditor":
            prior_open_topic_records = self._auditor_prior_open_topic_records(
                reviser_output
            )
            prior_open_topic_ids = [
                str(item.get("topic_id"))
                for item in prior_open_topic_records
                if str(item.get("topic_id") or "").strip()
            ]
            prompt = build_analysis_auditor_prompt(
                self.task,
                self.strategy.prompt_preamble,
                prior_output,
                reviser_output,
                validation_runs,
                git_snapshot,
                self.strategy.review_loops,
                contract,
                prior_open_issue_records,
                prior_open_topic_records,
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
            prior_open_topic_ids = []
            prior_open_issue_records = []
            prior_open_topic_records = []
        return self._run_agent_stage(
            role_name,
            role_cfg.provider,
            prompt,
            analysis_review_schema(),
            role_cfg,
            semantic_context={
                "contract": contract,
                "prior_open_issue_ids": prior_open_issue_ids,
                "prior_open_issue_records": prior_open_issue_records,
                "prior_open_topic_ids": prior_open_topic_ids,
                "prior_open_topic_records": prior_open_topic_records,
                "historical_topic_ids": historical_topic_ids,
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
        *,
        record_stage: bool = True,
        record_workspace_policy_check: bool = True,
    ) -> ProviderRun:
        stage_index = self.stage_counter + 1
        stage_dir = self.artifacts_dir / f"{stage_index:02d}_{slugify(role_name)}"
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
        raw_structured_output = (
            deepcopy(run.structured_output)
            if isinstance(run.structured_output, dict)
            else run.structured_output
        )

        semantic_errors: list[str] = []
        semantic_warnings: list[str] = []
        semantic_validation_path: str | None = None
        provider_schema_validation_errors = list(run.schema_validation_errors or [])
        schema_validation_errors = list(provider_schema_validation_errors)
        context = dict(semantic_context or {})
        contract = context.pop("contract", None)
        normalized_payload: dict[str, Any] | None = None
        payload_provenance: dict[str, Any] | None = None
        normalization_warnings: list[str] = []
        normalized_output_path = run.normalized_output_path or run.output_path
        raw_output_path = run.raw_output_path
        if isinstance(contract, AnalysisReviewContract):
            normalization_prior_open_issue_records = context.get(
                "prior_open_issue_records"
            )
            normalization_prior_open_topic_records = context.get(
                "prior_open_topic_records"
            )
            selected_focus_paths = context.get("selected_focus_paths")
            if isinstance(run.structured_output, dict):
                if role_name == "focus_gate":
                    normalized_payload = self._normalize_focus_gate_decision_payload(
                        run.structured_output,
                        expected_gate_path=context.get("expected_gate_path"),
                    )
                    payload_provenance = None
                    normalization_warnings = []
                elif role_name == "focus_gate_probe":
                    normalized_payload = self._normalize_focus_gate_probe_payload(
                        run.structured_output
                    )
                    payload_provenance = None
                    normalization_warnings = []
                else:
                    normalized_payload, payload_provenance, normalization_warnings = (
                        self._normalize_analysis_review_payload(
                            run.structured_output,
                            role_name=role_name,
                            payload_provenance_mode=contract.trust_review.payload_provenance_mode,
                            contract=contract,
                            prior_open_issue_records=normalization_prior_open_issue_records,
                            prior_open_topic_records=normalization_prior_open_topic_records,
                            selected_focus_paths=selected_focus_paths,
                        )
                    )
                schema_validation_errors = _soft_validate_schema(
                    normalized_payload, schema
                )
                raw_meta = dict(run.raw_meta or {})
                if payload_provenance is not None:
                    raw_meta["payload_provenance"] = payload_provenance
                run = replace(
                    run,
                    structured_output=normalized_payload,
                    raw_meta=raw_meta,
                )
            if (
                provider_schema_validation_errors
                and not schema_validation_errors
                and run.failure_kind is None
            ):
                run = replace(
                    run,
                    ok=(
                        run.exit_code == 0
                        and run.structured_output is not None
                        and run.failure_kind is None
                    ),
                    error=None,
                    failure_summary=None,
                    schema_validation_errors=[],
                )
            elif schema_validation_errors and not run.failure_kind:
                run = replace(
                    run,
                    ok=False,
                    failure_kind="schema_validation_error",
                    failure_summary="Schema validation failed.",
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
                    **self._semantic_validation_kwargs(
                        role_name=role_name,
                        payload=normalized_payload,
                        task=self.task,
                        contract=contract,
                        context=context,
                    ),
                    payload_provenance=payload_provenance,
                )
                semantic_errors = list(semantic_result.errors)
                semantic_warnings = list(normalization_warnings) + list(
                    semantic_result.warnings
                )
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
                    failure_summary=run.failure_summary
                    or "Semantic validation failed.",
                )
            else:
                run = replace(run, raw_meta=raw_meta)
            for warning in semantic_warnings:
                self.warnings.append(f"{role_name}: {warning}")

        if isinstance(raw_structured_output, dict) and raw_output_path:
            write_json(Path(raw_output_path), raw_structured_output)
        if isinstance(run.structured_output, dict) and normalized_output_path:
            write_json(Path(normalized_output_path), run.structured_output)
        run = replace(
            run,
            output_path=normalized_output_path,
            raw_output_path=raw_output_path,
            normalized_output_path=normalized_output_path,
        )

        if record_stage:
            self.stage_counter = stage_index
        stage_record = asdict(run)
        stage_record["stage_index"] = stage_index
        stage_record["requested_access"] = role_config.access
        stage_record["effective_access"] = effective_role_config.access
        if role_name == "focus_gate":
            stage_record["round_index"] = 0
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
            stage_record["access_override_reason"] = (
                "Task-level workspace_write_policy forced this stage to run read-only."
            )
        if role_name == "focus_gate" and isinstance(run.structured_output, dict):
            stage_record["metadata"] = {
                "focus_gate": {
                    "gate_path": run.structured_output.get("gate_path"),
                    "focus_type": run.structured_output.get("focus_type"),
                    "decision_state": run.structured_output.get("decision_state"),
                }
            }
        if record_stage:
            self.agent_stages.append(stage_record)
            write_json(stage_dir / "run.envelope.json", stage_record)

        if record_workspace_policy_check:
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

    def _required_validator_failures(
        self, results: list[ValidationRun]
    ) -> list[ValidationRun]:
        return [
            item
            for item in results
            if item.required and item.status in {"failed", "error"}
        ]

    def _should_patch(
        self, validation_runs: list[ValidationRun], falsifier_run: ProviderRun
    ) -> bool:
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

    def _analysis_needs_revision(
        self, review_payload: dict[str, Any], revisions_completed: int
    ) -> bool:
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
        return bool(self._blocking_issues(review_payload)) or bool(
            self._score_threshold_failures(review_payload)
        )

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
        if (
            revisions_completed >= max_loops
            and str(review_payload.get("verdict") or "").lower() == "reject"
        ):
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
        for field_name in (
            "grounding_score",
            "actionability_score",
            "scope_compliance_score",
        ):
            if field_name in review_payload:
                parts.append(f"{field_name}={review_payload[field_name]}")
        issue_count = len(review_payload.get("issues", []))
        if issue_count:
            parts.append(f"Open reviewer issues: {issue_count}.")
        open_topic_ids = self._topic_ids_for_status({"open"})
        carried_forward_topic_ids = self._topic_ids_for_status({"carried_forward"})
        waived_topic_ids = self._topic_ids_for_status({"waived"})
        disagreed_topic_ids = self._topic_ids_for_status({"disagree"})
        if open_topic_ids:
            parts.append("Open reviewer topics: " + ", ".join(open_topic_ids) + ".")
        if carried_forward_topic_ids:
            parts.append(
                "Carried-forward topic IDs: "
                + ", ".join(carried_forward_topic_ids)
                + "."
            )
        if waived_topic_ids:
            parts.append("Waived topic IDs: " + ", ".join(waived_topic_ids) + ".")
        if disagreed_topic_ids:
            parts.append("Disagreed topic IDs: " + ", ".join(disagreed_topic_ids) + ".")
        accepted_recommendation_count = len(
            self._accepted_recommendation_reviews(review_payload)
        )
        if accepted_recommendation_count:
            parts.append(f"Accepted recommendations: {accepted_recommendation_count}.")
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
                parts.append(
                    "The content is usable, but the auditor still left low-severity warnings."
                )
        elif verdict == "accepted_partial":
            parts.append(
                "The run reached a partial acceptance outcome. Only the accepted recommendation subset is included in the final deliverable."
            )
        elif verdict == "best_effort_exhausted":
            parts.append(
                "The harness used its available review loops but still did not meet the stop criteria."
            )
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
            topic_ledger=self._serialized_topic_ledger(),
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
        topic_ledger: list[dict[str, Any]] | None = None,
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
        if topic_ledger is not None:
            details["topic_ledger"] = topic_ledger
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
                    "failure_summary": stage.get("failure_summary")
                    or stage.get("error"),
                }
            )

        return {
            "review_stages_attempted": attempted,
            "review_stages_completed": completed,
            "review_loop_exercised": completed > 0,
            "failed_review_stages": failed,
        }

    def _build_bounded_review_summary(
        self, run_details: dict[str, Any]
    ) -> dict[str, Any] | None:
        contract_dict = run_details.get("analysis_review_contract")
        if not isinstance(contract_dict, dict):
            if self.analysis_review_contract is None:
                return None
            contract_dict = self.analysis_review_contract.to_dict()

        bounded_policy = contract_dict.get("bounded_review")
        if not isinstance(bounded_policy, dict):
            return None

        final_analysis = self._resolve_bounded_review_analysis_payload(run_details)
        recommendations = (
            final_analysis.get("recommendations")
            if isinstance(final_analysis, dict)
            else []
        )
        if not isinstance(recommendations, list):
            recommendations = []
        final_analysis_scope_escapes = self._canonical_analysis_scope_escapes(
            final_analysis
        )
        final_analysis_stage = self._resolve_final_analysis_stage()

        issue_ledger = run_details.get("issue_ledger")
        if not isinstance(issue_ledger, list):
            issue_ledger = self._serialized_issue_ledger()
        topic_ledger = run_details.get("topic_ledger")
        if not isinstance(topic_ledger, list):
            topic_ledger = self._serialized_topic_ledger()

        review_stages: list[dict[str, Any]] = []
        scope_escapes: list[dict[str, Any]] = []
        next_auditor_round = 1

        if final_analysis_scope_escapes:
            role_name = str((final_analysis_stage or {}).get("role_name") or "proposer")
            round_index = self._analysis_stage_round_index(role_name)
            for escape in final_analysis_scope_escapes:
                scope_escapes.append(
                    {
                        "role_name": role_name,
                        "round_index": round_index,
                        "path": str(escape.get("path") or "").strip(),
                        "reason": str(escape.get("reason") or "").strip(),
                    }
                )

        for stage in self.agent_stages:
            if not isinstance(stage, dict):
                continue
            role_name = str(stage.get("role_name") or "").strip()
            if role_name not in {"critic", "auditor"}:
                continue
            payload = stage.get("structured_output")
            if (
                not stage.get("ok")
                or not isinstance(payload, dict)
                or "verdict" not in payload
            ):
                continue

            if role_name == "critic":
                round_index = 0
            else:
                round_index = next_auditor_round
                next_auditor_round += 1

            issues = [
                item
                for item in payload.get("issues", []) or []
                if isinstance(item, dict)
            ]
            topics = [
                item
                for item in payload.get("topics", []) or []
                if isinstance(item, dict)
            ]
            new_topic_ids = [
                str(item.get("topic_id") or "").strip()
                for item in topics
                if str(item.get("topic_id") or "").strip()
            ]
            resolved_topic_ids = [
                str(item).strip()
                for item in payload.get("resolved_topic_ids", []) or []
                if str(item).strip()
            ]
            carried_forward_topic_ids = [
                str(item).strip()
                for item in payload.get("carried_forward_topic_ids", []) or []
                if str(item).strip()
            ]
            waived_topic_ids = [
                str(item).strip()
                for item in payload.get("waived_topic_ids", []) or []
                if str(item).strip()
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
                        bounded_policy.get("critic_issue_cap")
                        if role_name == "critic"
                        else None
                    ),
                    "missing_topic_count": len(new_topic_ids),
                    "missing_topic_cap": (
                        bounded_policy.get("critic_new_topic_cap")
                        if role_name == "critic"
                        else None
                    ),
                    "new_topic_count": len(new_topic_ids),
                    "new_topic_cap": (
                        bounded_policy.get("critic_new_topic_cap")
                        if role_name == "critic"
                        else None
                    ),
                    "resolved_topic_count": len(resolved_topic_ids),
                    "carried_forward_topic_count": len(carried_forward_topic_ids),
                    "waived_topic_count": len(waived_topic_ids),
                    "open_topic_count": len(new_topic_ids)
                    + len(carried_forward_topic_ids),
                    "new_medium_or_higher_issue_count": self._count_new_medium_or_higher_review_issues(
                        role_name=role_name,
                        round_index=round_index,
                        issues=issues,
                        issue_ledger=issue_ledger,
                    ),
                    "topic_ledger_count": len(topic_ledger),
                    "new_medium_or_higher_issue_cap": (
                        bounded_policy.get(
                            "auditor_new_medium_or_higher_issue_cap_after_round0"
                        )
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
                if isinstance(item, dict)
                and isinstance(item.get("review_surface"), dict)
            ),
            "review_stages": review_stages,
            "scope_escape_count": len(scope_escapes),
            "scope_escapes": scope_escapes,
        }

    def _resolve_bounded_review_analysis_payload(
        self, run_details: dict[str, Any]
    ) -> dict[str, Any]:
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
            if str(issue.get("severity") or "").strip().lower()
            in {"medium", "high", "critical"}
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
                and str(record.get("severity") or "").strip().lower()
                in {"medium", "high", "critical"}
                and record.get("first_seen_round") == round_index
            )

        return sum(
            1
            for issue in issues
            if str(issue.get("severity") or "").strip().lower()
            in {"medium", "high", "critical"}
            and str(issue.get("why_not_raised_earlier") or "").strip()
        )

    @staticmethod
    def _count_review_issues(
        review_payload: dict[str, Any], severities: set[str]
    ) -> int:
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
        open_topic_ids = topic_ids_for_status_name(
            self.topic_ledger, status_name="open"
        )
        if open_topic_ids:
            causes.append("open review topics remain: " + ", ".join(open_topic_ids))
        carried_forward_topic_ids = topic_ids_for_status_name(
            self.topic_ledger,
            status_name="carried_forward",
        )
        if carried_forward_topic_ids:
            causes.append(
                "review topics are carried forward: "
                + ", ".join(carried_forward_topic_ids)
            )
        accepted_caveat_indices = self._accepted_caveat_recommendation_indices(
            review_payload
        )
        if accepted_caveat_indices:
            causes.append(
                "accepted recommendation reviews include accept_with_caveat: "
                + ", ".join(str(item) for item in accepted_caveat_indices)
            )
        contract = self._analysis_contract()
        if contract.mode == "trust":
            semantic_warning_records = self._final_semantic_warning_records()
            if (
                contract.trust_review.downgrade_on_semantic_warnings
                and semantic_warning_records
            ):
                causes.append(
                    "semantic validation warnings remain: "
                    + "; ".join(
                        record["warning"] for record in semantic_warning_records
                    )
                )
            inferred_indices = self._accepted_inferred_recommendation_indices(
                final_analysis_payload,
                review_payload,
            )
            if (
                contract.trust_review.downgrade_on_inferred_acceptance
                and inferred_indices
            ):
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

    def _analysis_publishability(
        self,
        *,
        content_verdict: str,
    ) -> dict[str, Any]:
        contract = self._analysis_contract()
        if contract.mode != "trust":
            return {
                "final_answer_publishable": content_verdict
                in _FULLY_ACCEPTED_CONTENT_VERDICTS,
                "blocking_causes": [],
            }

        if content_verdict not in _FULLY_ACCEPTED_CONTENT_VERDICTS:
            return {
                "final_answer_publishable": False,
                "blocking_causes": [
                    f"content verdict is not fully accepted: {content_verdict}"
                ],
            }

        blocking_causes: list[str] = []
        if self._final_payload_provenance_status() != "bound":
            blocking_causes.append("final payload provenance is not fully bound")

        open_topic_ids = topic_ids_for_status_name(
            self.topic_ledger, status_name="open"
        )
        if open_topic_ids:
            blocking_causes.append(
                "open review topics remain: " + ", ".join(open_topic_ids)
            )

        carried_forward_topic_ids = topic_ids_for_status_name(
            self.topic_ledger,
            status_name="carried_forward",
        )
        if carried_forward_topic_ids:
            blocking_causes.append(
                "review topics are carried forward: "
                + ", ".join(carried_forward_topic_ids)
            )

        blocking_semantic_warning_records = (
            self._final_publication_blocking_semantic_warning_records()
        )
        if blocking_semantic_warning_records:
            blocking_causes.append(
                "semantic validation warnings remain: "
                + "; ".join(
                    str(record.get("warning") or "")
                    for record in blocking_semantic_warning_records
                )
            )

        return {
            "final_answer_publishable": not blocking_causes,
            "blocking_causes": blocking_causes,
        }

    def _final_publication_blocking_semantic_warning_records(
        self,
    ) -> list[dict[str, Any]]:
        return [
            record
            for record in self._final_semantic_warning_records()
            if str(record.get("warning") or "")
            not in _TRUST_PUBLICATION_ADVISORY_WARNING_ALLOWLIST
        ]

    def _analysis_contract(self) -> AnalysisReviewContract:
        if self.analysis_review_contract is None:
            self.analysis_review_contract = build_analysis_review_contract(
                self.task, self.strategy
            )
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

    def _next_topic_id(self, reserved_ids: set[str] | None = None) -> str:
        reserved = set(self._topic_ledger_by_id)
        if reserved_ids:
            reserved.update(reserved_ids)
        index = 1
        while True:
            topic_id = f"AT-{index:03d}"
            if topic_id not in reserved:
                return topic_id
            index += 1

    def _open_issue_records(self) -> list[dict[str, Any]]:
        return [
            self._validation_issue_record(record)
            for record in self.issue_ledger
            if str(record.get("resolution_status") or "") in {"open", "carried_forward"}
        ]

    def _open_topic_records(self) -> list[dict[str, Any]]:
        return [
            self._validation_topic_record(record)
            for record in self.topic_ledger
            if str(record.get("resolution_status") or "") in {"open", "carried_forward"}
        ]

    def _auditor_prior_open_topic_records(
        self,
        reviser_output: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        records = [dict(item) for item in self._open_topic_records()]
        if not isinstance(reviser_output, dict) or not records:
            return records
        records_by_id = {
            str(item.get("topic_id") or "").strip(): item
            for item in records
            if str(item.get("topic_id") or "").strip()
        }
        for item in reviser_output.get("topic_resolution_map", []) or []:
            if not isinstance(item, dict):
                continue
            topic_id = str(item.get("topic_id") or "").strip()
            if not topic_id:
                continue
            record = records_by_id.get(topic_id)
            if record is None:
                continue
            recommendation_index = self._normalized_recommendation_index(
                item.get("recommendation_index")
            )
            if recommendation_index is not None:
                record["recommendation_index"] = recommendation_index
        return records

    def _serialized_issue_ledger(self) -> list[dict[str, Any]]:
        return [self._serialized_issue_record(record) for record in self.issue_ledger]

    def _serialized_topic_ledger(self) -> list[dict[str, Any]]:
        return [self._serialized_topic_record(record) for record in self.topic_ledger]

    @staticmethod
    def _serialized_issue_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "issue_id": str(record.get("issue_id") or ""),
            "source_stage_id": str(record.get("source_stage_id") or ""),
            "first_seen_round": record.get("first_seen_round"),
            "last_seen_round": record.get("last_seen_round"),
            "severity": str(record.get("severity") or ""),
            "kind": str(record.get("kind") or ""),
            "blocking_class": str(record.get("blocking_class") or ""),
            "recommendation_index": record.get("recommendation_index"),
            "title": str(record.get("title") or ""),
            "evidence": str(record.get("evidence") or ""),
            "repair_hint": str(record.get("repair_hint") or ""),
            "why_not_raised_earlier": record.get("why_not_raised_earlier"),
            "resolution_status": str(record.get("resolution_status") or ""),
            "resolution_note": str(record.get("resolution_note") or ""),
        }

    @staticmethod
    def _serialized_topic_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "topic_id": str(record.get("topic_id") or ""),
            "title": str(record.get("title") or ""),
            "severity": str(record.get("severity") or ""),
            "evidence": str(record.get("evidence") or ""),
            "recommendation_index": record.get("recommendation_index"),
            "introduced_by": str(record.get("introduced_by") or ""),
            "introduced_in_stage_index": record.get("introduced_in_stage_index"),
            "resolution_status": str(record.get("resolution_status") or ""),
            "resolution_note": str(record.get("resolution_note") or ""),
            "resolved_in_stage_index": record.get("resolved_in_stage_index"),
        }

    @classmethod
    def _validation_issue_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        serialized = cls._serialized_issue_record(record)
        serialized[_PRIOR_SURFACED_REFS_FIELD] = cls._normalized_internal_ref_list(
            record.get(_PRIOR_SURFACED_REFS_FIELD)
        )
        return serialized

    @classmethod
    def _validation_topic_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        serialized = cls._serialized_topic_record(record)
        serialized[_PRIOR_SURFACED_REFS_FIELD] = cls._normalized_internal_ref_list(
            record.get(_PRIOR_SURFACED_REFS_FIELD)
        )
        return serialized

    @staticmethod
    def _normalized_internal_ref_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return HarnessRunner._dedupe_preserving_order(
            [str(value).strip() for value in values if str(value).strip()]
        )

    @staticmethod
    def _topic_resolution_status_from_reviewer_classification(
        *,
        topic_id: str,
        resolved_topic_ids: set[str],
        waived_topic_ids: set[str],
        current_topic_ids: set[str],
        carried_topic_ids: set[str],
        resolution_entry: dict[str, Any] | None,
    ) -> str:
        if topic_id in resolved_topic_ids:
            return "addressed"
        if topic_id in waived_topic_ids:
            resolution_status = (
                str((resolution_entry or {}).get("status") or "").strip().lower()
            )
            if resolution_status == "disagree":
                return "disagree"
            return "waived"
        if topic_id in current_topic_ids or topic_id in carried_topic_ids:
            return "carried_forward"
        return "carried_forward"

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
        normalized["severity"] = (
            str(normalized.get("severity") or "low").strip().lower()
        )
        normalized["kind"] = str(normalized.get("kind") or "other").strip().lower()
        normalized["blocking_class"] = (
            str(
                normalized.get("blocking_class")
                or default_blocking_class_for_kind(normalized.get("kind"))
            )
            .strip()
            .lower()
        )
        recommendation_index = normalized.get("recommendation_index")
        try:
            normalized["recommendation_index"] = (
                None
                if recommendation_index in (None, "")
                else int(recommendation_index)
            )
        except (TypeError, ValueError):
            normalized["recommendation_index"] = None
        normalized["title"] = str(
            normalized.get("title") or normalized.get("summary") or "Issue"
        )
        normalized["evidence"] = str(normalized.get("evidence") or "")
        normalized["repair_hint"] = str(normalized.get("repair_hint") or "")
        why_not_raised_earlier = normalized.get("why_not_raised_earlier")
        normalized["why_not_raised_earlier"] = (
            None
            if why_not_raised_earlier in (None, "")
            else str(why_not_raised_earlier)
        )
        if round_index > 0 and issue_id not in self._issue_ledger_by_id:
            if (
                normalized["severity"] in {"medium", "high", "critical"}
                and not normalized["why_not_raised_earlier"]
            ):
                self.warnings.append(
                    f"{issue_id} was introduced as a new medium-or-higher issue in round {round_index} without why_not_raised_earlier."
                )
        return normalized

    def _normalize_review_topic(
        self,
        topic: dict[str, Any],
        *,
        reserved_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(topic)
        topic_id = str(normalized.get("topic_id") or "").strip()
        if not topic_id:
            topic_id = self._next_topic_id(reserved_ids)
        normalized["topic_id"] = topic_id
        normalized["severity"] = (
            str(normalized.get("severity") or "low").strip().lower()
        )
        recommendation_index = normalized.get("recommendation_index")
        try:
            normalized["recommendation_index"] = (
                None
                if recommendation_index in (None, "")
                else int(recommendation_index)
            )
        except (TypeError, ValueError):
            normalized["recommendation_index"] = None
        normalized["title"] = str(normalized.get("title") or "Topic")
        normalized["evidence"] = str(normalized.get("evidence") or "")
        normalized["repair_hint"] = str(normalized.get("repair_hint") or "")
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

    def _topic_resolution_note_from_reviser(
        self,
        reviser_output: dict[str, Any] | None,
        topic_id: str,
    ) -> str:
        entry = self._topic_resolution_entry_from_reviser(reviser_output, topic_id)
        if not isinstance(entry, dict):
            return ""
        status = str(entry.get("status") or "")
        change_summary = str(entry.get("change_summary") or "")
        residual_risk = str(entry.get("residual_risk") or "")
        note_bits = [bit for bit in (status, change_summary, residual_risk) if bit]
        return " | ".join(note_bits)

    @staticmethod
    def _topic_resolution_entry_from_reviser(
        reviser_output: dict[str, Any] | None,
        topic_id: str,
    ) -> dict[str, Any] | None:
        if not isinstance(reviser_output, dict):
            return None
        for item in reviser_output.get("topic_resolution_map", []) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("topic_id") or "") != topic_id:
                continue
            return item
        return None

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

        stage_index = self.stage_counter
        stage_id = f"stage-{stage_index:02d}-{slugify(role_name)}"
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
        resolved_ids = {
            str(item)
            for item in review_payload.get("resolved_issue_ids", [])
            if str(item).strip()
        }
        carried_ids = {
            str(item)
            for item in review_payload.get("carried_forward_issue_ids", [])
            if str(item).strip()
        }
        waived_ids = {
            str(item)
            for item in review_payload.get("waived_issue_ids", [])
            if str(item).strip()
        }
        prior_open_topic_ids = {
            str(record.get("topic_id"))
            for record in self.topic_ledger
            if str(record.get("resolution_status") or "") in {"open", "carried_forward"}
        }
        normalized_topics = []
        reserved_topic_ids = set(self._topic_ledger_by_id)
        for topic in review_payload.get("topics", []) or []:
            if not isinstance(topic, dict):
                continue
            normalized_topic = self._normalize_review_topic(
                topic,
                reserved_ids=reserved_topic_ids,
            )
            reserved_topic_ids.add(str(normalized_topic.get("topic_id")))
            normalized_topics.append(normalized_topic)
        current_topic_ids = {str(item.get("topic_id")) for item in normalized_topics}
        resolved_topic_ids = {
            str(item)
            for item in review_payload.get("resolved_topic_ids", [])
            if str(item).strip()
        }
        carried_topic_ids = {
            str(item)
            for item in review_payload.get("carried_forward_topic_ids", [])
            if str(item).strip()
        }
        waived_topic_ids = {
            str(item)
            for item in review_payload.get("waived_topic_ids", [])
            if str(item).strip()
        }
        recommendation_review_proof_by_index = (
            self._recommendation_review_proof_by_index(review_payload)
        )
        issue_closure_review_map = self._scoped_closure_review_map(
            review_payload.get("issue_closure_reviews"),
            id_field="issue_id",
        )
        topic_closure_review_map = self._scoped_closure_review_map(
            review_payload.get("topic_closure_reviews"),
            id_field="topic_id",
        )

        for issue_id in prior_open_ids:
            record = self._issue_ledger_by_id.get(issue_id)
            if record is None:
                continue
            if issue_id in resolved_ids:
                record["resolution_status"] = "resolved"
                record["resolution_note"] = self._resolution_note_from_reviser(
                    reviser_output, issue_id
                )
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
            self._refresh_issue_prior_surfaced_refs(
                record,
                recommendation_review_proof_by_index=recommendation_review_proof_by_index,
            )

        for topic_id in prior_open_topic_ids:
            record = self._topic_ledger_by_id.get(topic_id)
            if record is None:
                continue
            resolution_entry = self._topic_resolution_entry_from_reviser(
                reviser_output, topic_id
            )
            resolution_note = self._topic_resolution_note_from_reviser(
                reviser_output, topic_id
            )
            resolution_recommendation_index = None
            if isinstance(resolution_entry, dict):
                raw_resolution_recommendation_index = resolution_entry.get(
                    "recommendation_index"
                )
                if raw_resolution_recommendation_index not in (None, ""):
                    try:
                        resolution_recommendation_index = int(
                            raw_resolution_recommendation_index
                        )
                    except (TypeError, ValueError):
                        resolution_recommendation_index = None
            if resolution_recommendation_index is not None:
                record["recommendation_index"] = resolution_recommendation_index
            if topic_id in resolved_topic_ids:
                record["resolution_status"] = "addressed"
                if resolution_note:
                    record["resolution_note"] = resolution_note
                record["resolved_in_stage_index"] = stage_index
            elif topic_id in waived_topic_ids:
                record["resolution_status"] = (
                    self._topic_resolution_status_from_reviewer_classification(
                        topic_id=topic_id,
                        resolved_topic_ids=resolved_topic_ids,
                        waived_topic_ids=waived_topic_ids,
                        current_topic_ids=current_topic_ids,
                        carried_topic_ids=carried_topic_ids,
                        resolution_entry=resolution_entry,
                    )
                )
                if resolution_note:
                    record["resolution_note"] = resolution_note
                record["resolved_in_stage_index"] = stage_index
            elif topic_id in current_topic_ids or topic_id in carried_topic_ids:
                record["resolution_status"] = "carried_forward"
                if resolution_note:
                    record["resolution_note"] = resolution_note
                record["resolved_in_stage_index"] = None
            else:
                self.warnings.append(
                    f"Review stage '{role_name}' did not explicitly classify prior open topic {topic_id}; treating it as carried_forward."
                )
                record["resolution_status"] = "carried_forward"
                if resolution_note:
                    record["resolution_note"] = resolution_note
                record["resolved_in_stage_index"] = None

        for topic in normalized_topics:
            topic_id = str(topic.get("topic_id"))
            if topic_id in self._topic_ledger_by_id:
                if topic_id not in prior_open_topic_ids:
                    raise ValueError(
                        f"Review stage '{role_name}' reused historical topic ID {topic_id} even though it is not currently open."
                    )
                record = self._topic_ledger_by_id[topic_id]
                record.update(
                    {
                        "severity": topic.get("severity"),
                        "title": topic.get("title"),
                        "evidence": topic.get("evidence"),
                        "repair_hint": topic.get("repair_hint"),
                        "resolution_status": "carried_forward",
                        "resolved_in_stage_index": None,
                    }
                )
                topic_recommendation_index = topic.get("recommendation_index")
                if topic_recommendation_index not in (None, ""):
                    record["recommendation_index"] = topic_recommendation_index
            else:
                record = {
                    "topic_id": topic_id,
                    "severity": topic.get("severity"),
                    "recommendation_index": topic.get("recommendation_index"),
                    "title": topic.get("title"),
                    "evidence": topic.get("evidence"),
                    "repair_hint": topic.get("repair_hint"),
                    "introduced_by": role_name,
                    "introduced_in_stage_index": stage_index,
                    "resolution_status": "open",
                    "resolution_note": "",
                    "resolved_in_stage_index": None,
                }
                self.topic_ledger.append(record)
                self._topic_ledger_by_id[topic_id] = record
            self._refresh_topic_prior_surfaced_refs(
                record,
                recommendation_review_proof_by_index=recommendation_review_proof_by_index,
            )

        for issue_id in resolved_ids | carried_ids | waived_ids:
            record = self._issue_ledger_by_id.get(issue_id)
            if record is None:
                continue
            self._refresh_issue_prior_surfaced_refs(
                record,
                recommendation_review_proof_by_index=recommendation_review_proof_by_index,
                issue_closure_review_map=issue_closure_review_map,
            )

        for topic_id in resolved_topic_ids | carried_topic_ids | waived_topic_ids:
            record = self._topic_ledger_by_id.get(topic_id)
            if record is None:
                continue
            self._refresh_topic_prior_surfaced_refs(
                record,
                recommendation_review_proof_by_index=recommendation_review_proof_by_index,
                topic_closure_review_map=topic_closure_review_map,
            )

    @staticmethod
    def _recommendation_reviews(review_payload: dict[str, Any]) -> list[dict[str, Any]]:
        reviews = []
        for item in review_payload.get("recommendation_reviews", []) or []:
            if isinstance(item, dict):
                reviews.append(item)
        reviews.sort(key=lambda item: int(item.get("recommendation_index") or 0))
        return reviews

    def _accepted_recommendation_reviews(
        self, review_payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in self._recommendation_reviews(review_payload)
            if str(item.get("verdict") or "").strip().lower()
            in {"accept", "accept_with_caveat"}
        ]

    def _accepted_recommendation_indices(
        self, review_payload: dict[str, Any]
    ) -> list[int]:
        accepted_indices: list[int] = []
        for item in self._accepted_recommendation_reviews(review_payload):
            recommendation_index = self._normalized_recommendation_index(
                item.get("recommendation_index")
            )
            if recommendation_index is not None:
                accepted_indices.append(recommendation_index)
        return sorted(set(accepted_indices))

    def _has_recommendation_caveats(self, review_payload: dict[str, Any]) -> bool:
        return any(
            str(item.get("verdict") or "").strip().lower() == "accept_with_caveat"
            for item in self._recommendation_reviews(review_payload)
        )

    def _accepted_caveat_recommendation_indices(
        self, review_payload: dict[str, Any]
    ) -> list[int]:
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
        accepted_indices = set(self._accepted_recommendation_indices(review_payload))
        inferred_indices: list[int] = []
        for index, item in enumerate(recommendations, start=1):
            if index not in accepted_indices or not isinstance(item, dict):
                continue
            if str(item.get("grounding_mode") or "").strip().lower() == "inferred":
                inferred_indices.append(index)
        return inferred_indices

    def _build_recommendation_admissibility(
        self,
        *,
        final_analysis_payload: dict[str, Any],
        final_review_payload: dict[str, Any],
    ) -> dict[str, Any]:
        contract = self._analysis_contract()
        empty_status = RecommendationAdmissibilityStatus()

        recommendations = final_analysis_payload.get("recommendations")
        if not isinstance(recommendations, list):
            return empty_status.to_dict()

        review_by_index: dict[int, dict[str, Any]] = {}
        for item in self._recommendation_reviews(final_review_payload):
            recommendation_index = self._normalized_recommendation_index(
                item.get("recommendation_index")
            )
            if recommendation_index is not None:
                review_by_index[recommendation_index] = item

        topic_blocked_indices = set(
            partial_accept_topic_eligibility(
                self.topic_ledger,
                accepted_recommendation_indices=self._accepted_recommendation_indices(
                    final_review_payload
                ),
            )["blocked_recommendation_indices"]
        )

        final_indices: list[int] = []
        partial_only_indices: list[int] = []
        excluded_indices: list[int] = []
        reasons_by_index: dict[str, list[str]] = {}

        for recommendation_index, recommendation in enumerate(recommendations, start=1):
            if not isinstance(recommendation, dict):
                excluded_indices.append(recommendation_index)
                reasons_by_index[str(recommendation_index)] = ["not_accepted"]
                continue

            if recommendation_index in topic_blocked_indices:
                excluded_indices.append(recommendation_index)
                reasons_by_index[str(recommendation_index)] = ["topic_blocked"]
                continue

            review = review_by_index.get(recommendation_index) or {}
            verdict = str(review.get("verdict") or "").strip().lower()
            if verdict not in {"accept", "accept_with_caveat"}:
                excluded_indices.append(recommendation_index)
                reasons_by_index[str(recommendation_index)] = ["not_accepted"]
                continue

            reasons: list[str] = []
            if contract.mode == "trust":
                if verdict == "accept_with_caveat":
                    reasons.append("accepted_with_caveat")
                if (
                    str(recommendation.get("grounding_mode") or "").strip().lower()
                    == "inferred"
                ):
                    reasons.append("inferred_grounding")

            if reasons:
                partial_only_indices.append(recommendation_index)
                reasons_by_index[str(recommendation_index)] = reasons
                continue

            final_indices.append(recommendation_index)

        return RecommendationAdmissibilityStatus(
            final_answer_recommendation_indices=final_indices,
            partial_only_recommendation_indices=partial_only_indices,
            excluded_recommendation_indices=excluded_indices,
            reasons_by_recommendation_index=reasons_by_index,
        ).to_dict()

    def _latest_successful_stage(
        self, *, role_names: set[str] | None = None
    ) -> dict[str, Any] | None:
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
            status = provenance.get("status") or "missing"
            if (
                surface == "review"
                and status == "bound"
                and provenance.get("policy_mode") == "payload_hash_and_refs"
                and not bool(provenance.get("closure_provenance_satisfied"))
            ):
                status = "insufficient"
            record = {
                "surface": surface,
                "stage_index": stage.get("stage_index"),
                "role_name": stage.get("role_name"),
                "status": status,
                "policy_mode": provenance.get("policy_mode") or "none",
                "payload_sha256": provenance.get("payload_sha256"),
                "normalized_ref_field_count": provenance.get(
                    "normalized_ref_field_count", 0
                ),
                "normalized_ref_count": provenance.get("normalized_ref_count", 0),
                "recommendation_review_ref_field_count": provenance.get(
                    "recommendation_review_ref_field_count",
                    0,
                ),
                "recommendation_review_ref_count": provenance.get(
                    "recommendation_review_ref_count",
                    0,
                ),
                "issue_closure_review_ref_count": provenance.get(
                    "issue_closure_review_ref_count",
                    0,
                ),
                "topic_closure_review_ref_count": provenance.get(
                    "topic_closure_review_ref_count",
                    0,
                ),
                "closure_provenance_satisfied": bool(
                    provenance.get("closure_provenance_satisfied")
                ),
                "covered_recommendation_indices": list(
                    provenance.get("covered_recommendation_indices") or []
                ),
                "uncovered_recommendation_indices": list(
                    provenance.get("uncovered_recommendation_indices") or []
                ),
                "closure_complete_issue_ids": list(
                    provenance.get("closure_complete_issue_ids") or []
                ),
                "closure_complete_topic_ids": list(
                    provenance.get("closure_complete_topic_ids") or []
                ),
                "uncovered_global_issue_ids": list(
                    provenance.get("uncovered_global_issue_ids") or []
                ),
                "uncovered_global_topic_ids": list(
                    provenance.get("uncovered_global_topic_ids") or []
                ),
                "closure_proof_by_id": dict(
                    provenance.get("closure_proof_by_id") or {}
                ),
            }
            records.append(record)
        return records

    def _final_payload_provenance_status(self) -> str:
        records = self._final_payload_provenance_records()
        if not records:
            return "missing"
        statuses = {str(item.get("status") or "missing") for item in records}
        if "insufficient" in statuses:
            return "insufficient"
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
        accepted_caveat_indices = self._accepted_caveat_recommendation_indices(
            final_review_payload
        )
        inferred_indices = self._accepted_inferred_recommendation_indices(
            final_analysis_payload,
            final_review_payload,
        )
        downgrade_causes = self._analysis_warning_causes(
            final_review_payload,
            final_analysis_payload=final_analysis_payload,
        )
        provenance_status = self._final_payload_provenance_status()
        open_topic_ids = topic_ids_for_status_name(
            self.topic_ledger, status_name="open"
        )
        carried_forward_topic_ids = topic_ids_for_status_name(
            self.topic_ledger,
            status_name="carried_forward",
        )
        waived_topic_ids = topic_ids_for_status_name(
            self.topic_ledger, status_name="waived"
        )
        resolved_topic_ids = topic_ids_for_status_name(
            self.topic_ledger, status_name="resolved"
        )
        disagreed_topic_ids = topic_ids_for_status_name(
            self.topic_ledger, status_name="disagreed"
        )
        review_provenance = next(
            (
                item
                for item in provenance_records
                if str(item.get("surface") or "") == "review"
            ),
            {},
        )
        if (
            contract.trust_review.payload_provenance_mode == "none"
            and provenance_status == "missing"
        ):
            provenance_status = "not_required"
        publishability = self._analysis_publishability(content_verdict=content_verdict)
        recommendation_admissibility = self._build_recommendation_admissibility(
            final_analysis_payload=final_analysis_payload,
            final_review_payload=final_review_payload,
        )
        primary_seam = self._canonical_primary_seam(final_analysis_payload)
        secondary_seams_considered = self._canonical_secondary_seams_considered(
            final_analysis_payload
        )
        recommendation_seam_bindings = self._canonical_recommendation_seam_bindings(
            final_analysis_payload
        )
        scope_escapes = self._canonical_analysis_scope_escapes(final_analysis_payload)
        return {
            "mode": contract.mode,
            "content_verdict": content_verdict,
            "primary_seam": primary_seam,
            "secondary_seams_considered": secondary_seams_considered,
            "recommendation_seam_bindings": recommendation_seam_bindings,
            "scope_escapes": scope_escapes,
            "semantic_warning_count": len(semantic_warning_records),
            "semantic_warnings": semantic_warning_records,
            "provenance": {
                "status": provenance_status,
                "policy_mode": contract.trust_review.payload_provenance_mode,
                "required": contract.trust_review.payload_provenance_mode
                == "payload_hash_and_refs",
                "issue_closure_review_ref_count": review_provenance.get(
                    "issue_closure_review_ref_count",
                    0,
                ),
                "topic_closure_review_ref_count": review_provenance.get(
                    "topic_closure_review_ref_count",
                    0,
                ),
                "closure_complete_issue_ids": list(
                    review_provenance.get("closure_complete_issue_ids") or []
                ),
                "closure_complete_topic_ids": list(
                    review_provenance.get("closure_complete_topic_ids") or []
                ),
                "uncovered_recommendation_indices": list(
                    review_provenance.get("uncovered_recommendation_indices") or []
                ),
                "uncovered_global_issue_ids": list(
                    review_provenance.get("uncovered_global_issue_ids") or []
                ),
                "uncovered_global_topic_ids": list(
                    review_provenance.get("uncovered_global_topic_ids") or []
                ),
                "closure_proof_by_id": dict(
                    review_provenance.get("closure_proof_by_id") or {}
                ),
                "stages": provenance_records,
            },
            "accepted_recommendations_with_caveats": accepted_caveat_indices,
            "accepted_recommendations_with_inferred_grounding": inferred_indices,
            "open_topic_ids": open_topic_ids,
            "carried_forward_topic_ids": carried_forward_topic_ids,
            "waived_topic_ids": waived_topic_ids,
            "resolved_topic_ids": resolved_topic_ids,
            "disagreed_topic_ids": disagreed_topic_ids,
            "topic_ledger_count": len(self.topic_ledger),
            "downgrade_causes": downgrade_causes,
            "recommendation_admissibility": recommendation_admissibility,
            "publishability": publishability,
        }

    @staticmethod
    def _canonical_primary_seam(
        final_analysis_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        primary_seam = final_analysis_payload.get("primary_seam")
        if not isinstance(primary_seam, dict):
            return None
        return json.loads(json.dumps(primary_seam))

    @staticmethod
    def _canonical_secondary_seams_considered(
        final_analysis_payload: dict[str, Any],
    ) -> list[Any]:
        secondary_seams_considered = final_analysis_payload.get(
            "secondary_seams_considered"
        )
        if not isinstance(secondary_seams_considered, list):
            return []
        return json.loads(json.dumps(secondary_seams_considered))

    @staticmethod
    def _canonical_recommendation_seam_bindings(
        final_analysis_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        recommendations = final_analysis_payload.get("recommendations")
        if not isinstance(recommendations, list):
            return []
        bindings: list[dict[str, Any]] = []
        for recommendation_index, item in enumerate(recommendations, start=1):
            if not isinstance(item, dict):
                continue
            bindings.append(
                {
                    "recommendation_index": recommendation_index,
                    "seam_id": item.get("seam_id"),
                    "seam_expansion_reason": item.get("seam_expansion_reason"),
                }
            )
        return bindings

    @staticmethod
    def _canonical_analysis_scope_escapes(
        final_analysis_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        scope_escapes = final_analysis_payload.get("scope_escapes")
        if not isinstance(scope_escapes, list):
            return []
        return json.loads(
            json.dumps([item for item in scope_escapes if isinstance(item, dict)])
        )

    def _resolve_final_analysis_stage(self) -> dict[str, Any] | None:
        for stage in reversed(self.agent_stages):
            if not isinstance(stage, dict):
                continue
            role_name = str(stage.get("role_name") or "").strip()
            if role_name == "proposer" or role_name.startswith("reviser_round_"):
                payload = stage.get("structured_output")
                if stage.get("ok") and isinstance(payload, dict) and payload:
                    return stage
        return None

    @staticmethod
    def _analysis_stage_round_index(role_name: str) -> int:
        normalized = str(role_name or "").strip()
        if normalized == "proposer":
            return 0
        if normalized.startswith("reviser_round_"):
            suffix = normalized.removeprefix("reviser_round_")
            try:
                return int(suffix)
            except ValueError:
                return 0
        return 0

    def _blocking_issues(self, review_payload: dict[str, Any]) -> list[dict[str, Any]]:
        blocking: list[dict[str, Any]] = []
        for issue in review_payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            severity = str(issue.get("severity") or "").strip().lower()
            blocking_class = (
                str(issue.get("blocking_class") or "presentation").strip().lower()
            )
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
        if (
            self._count_review_issues(review_payload, {"medium", "high", "critical"})
            > 0
        ):
            return False
        if self._score_threshold_failures(review_payload):
            return False
        recommendation_reviews = self._recommendation_reviews(review_payload)
        if recommendation_reviews and any(
            str(item.get("verdict") or "").strip().lower()
            not in {"accept", "accept_with_caveat"}
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
        if (
            contract.mode == "trust"
            and contract.trust_review.payload_provenance_mode == "payload_hash_and_refs"
        ):
            provenance_status = self._final_payload_provenance_status()
            if provenance_status != "bound":
                return False

        accepted_recommendation_indices: list[int] = []
        accepted_issue_ids: set[str] = set()
        for review in accepted_reviews:
            raw_index = review.get("recommendation_index")
            if raw_index in (None, ""):
                pass
            else:
                try:
                    accepted_recommendation_indices.append(int(raw_index))
                except (TypeError, ValueError):
                    pass
            for issue_id in review.get("open_issue_ids", []) or []:
                normalized_issue_id = str(issue_id or "").strip()
                if normalized_issue_id:
                    accepted_issue_ids.add(normalized_issue_id)

        accepted_recommendation_index_set = set(accepted_recommendation_indices)
        for issue in review_payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            if self._issue_blocks_partial_accept(
                issue,
                accepted_recommendation_indices=accepted_recommendation_index_set,
                accepted_issue_ids=accepted_issue_ids,
                policy=policy,
            ):
                return False

        topic_eligibility = partial_accept_topic_eligibility(
            self.topic_ledger,
            accepted_recommendation_indices=accepted_recommendation_indices,
        )
        if topic_eligibility["global_blocking_topic_ids"]:
            return False
        if (
            len(topic_eligibility["eligible_recommendation_indices"])
            < policy.min_accepted_recommendations
        ):
            return False

        return True

    @staticmethod
    def _issue_blocks_partial_accept(
        issue: dict[str, Any],
        *,
        accepted_recommendation_indices: set[int],
        accepted_issue_ids: set[str],
        policy: PartialAcceptancePolicy,
    ) -> bool:
        severity = str(issue.get("severity") or "").strip().lower()
        if severity not in {"medium", "high", "critical"}:
            return False

        issue_id = str(issue.get("issue_id") or "").strip()
        recommendation_index = HarnessRunner._normalized_recommendation_index(
            issue.get("recommendation_index")
        )
        if recommendation_index is None:
            return True
        if (
            recommendation_index not in accepted_recommendation_indices
            and issue_id not in accepted_issue_ids
        ):
            return False
        if severity in {"high", "critical"}:
            return True

        blocking_class = (
            str(issue.get("blocking_class") or "presentation").strip().lower()
        )
        if blocking_class == "correctness":
            return policy.forbid_correctness_blockers_on_accepted_recommendations
        if blocking_class in {"actionability", "completeness", "presentation"}:
            return not policy.allow_localized_medium_non_correctness_issues
        return True

    def _require_role(self, role_name: str) -> RoleConfig:
        role = self.strategy.roles.get(role_name)
        if role is None:
            raise HarnessError(f"Strategy requires role: {role_name}")
        return role

    def _focus_gate_role_config(self) -> RoleConfig:
        role = self.strategy.roles.get("focus_gate")
        if role is not None:
            return replace(role, access="read")
        proposer = self._require_role("proposer")
        return replace(proposer, access="read")

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

    def _strip_workspace_ref_location_suffix(self, value: str) -> str:
        text = str(value or "").strip()
        if not text or "://" in text:
            return text
        match = _WORKSPACE_REF_LOCATION_SUFFIX_RE.match(text)
        if not match:
            return text
        return match.group("path")

    def _normalize_workspace_ref(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "://" in text:
            return text
        normalized = self._strip_workspace_ref_location_suffix(text).replace("\\", "/")
        candidate = Path(normalized)
        if candidate.is_absolute():
            try:
                normalized = (
                    candidate.resolve(strict=False)
                    .relative_to(self.workspace)
                    .as_posix()
                )
            except ValueError:
                if normalized.startswith("/.") and not normalized.startswith("//"):
                    normalized = posixpath.normpath(normalized.lstrip("/"))
                    if normalized == ".":
                        return ""
                    while normalized.startswith("./"):
                        normalized = normalized[2:]
                    return normalized
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

    @staticmethod
    def _dedupe_preserving_order(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _bind_normalized_payload(
        self,
        payload: dict[str, Any],
        *,
        payload_provenance_mode: str,
        normalized_refs: dict[str, Any],
        prior_open_issue_records: list[dict[str, Any]] | None = None,
        prior_open_topic_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_ref_count = 0
        for value in normalized_refs.values():
            if isinstance(value, list):
                normalized_ref_count += len(value)
            elif value:
                normalized_ref_count += 1
        (
            recommendation_review_ref_count,
            recommendation_review_ref_field_count,
        ) = self._recommendation_review_ref_stats(normalized_refs)
        issue_closure_review_ref_count = self._scoped_closure_review_ref_count(
            normalized_refs,
            prefix="issue_closure_reviews[",
        )
        topic_closure_review_ref_count = self._scoped_closure_review_ref_count(
            normalized_refs,
            prefix="topic_closure_reviews[",
        )
        coverage = self._review_payload_ref_coverage(
            payload,
            prior_open_issue_records=prior_open_issue_records,
            prior_open_topic_records=prior_open_topic_records,
        )
        closure_provenance_satisfied = (
            not coverage["uncovered_recommendation_indices"]
            and not coverage["uncovered_global_issue_ids"]
            and not coverage["uncovered_global_topic_ids"]
        )
        if payload_provenance_mode == "none":
            return {
                "status": "not_required",
                "policy_mode": payload_provenance_mode,
                "normalized_ref_field_count": len(normalized_refs),
                "normalized_ref_count": normalized_ref_count,
                "recommendation_review_ref_field_count": recommendation_review_ref_field_count,
                "recommendation_review_ref_count": recommendation_review_ref_count,
                "issue_closure_review_ref_count": issue_closure_review_ref_count,
                "topic_closure_review_ref_count": topic_closure_review_ref_count,
                "closure_provenance_satisfied": closure_provenance_satisfied,
                **coverage,
            }
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return {
            "status": "bound",
            "binding_method": "payload_hash_and_refs",
            "policy_mode": payload_provenance_mode,
            "payload_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            "normalized_ref_field_count": len(normalized_refs),
            "normalized_ref_count": normalized_ref_count,
            "recommendation_review_ref_field_count": recommendation_review_ref_field_count,
            "recommendation_review_ref_count": recommendation_review_ref_count,
            "issue_closure_review_ref_count": issue_closure_review_ref_count,
            "topic_closure_review_ref_count": topic_closure_review_ref_count,
            "closure_provenance_satisfied": closure_provenance_satisfied,
            **coverage,
            "normalized_refs": normalized_refs,
        }

    @staticmethod
    def _normalized_recommendation_index(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        if normalized < 1:
            return None
        return normalized

    @staticmethod
    def _record_recommendation_index_map(
        records: list[dict[str, Any]] | None,
        *,
        id_field: str,
    ) -> dict[str, int | None]:
        mapping: dict[str, int | None] = {}
        for item in records or []:
            if not isinstance(item, dict):
                continue
            record_id = str(item.get(id_field) or "").strip()
            if not record_id:
                continue
            mapping[record_id] = HarnessRunner._normalized_recommendation_index(
                item.get("recommendation_index")
            )
        return mapping

    @staticmethod
    def _recommendation_review_proof_by_index(
        payload: dict[str, Any],
    ) -> dict[int, dict[str, Any]]:
        mapping: dict[int, dict[str, Any]] = {}
        for item in payload.get("recommendation_reviews", []) or []:
            if not isinstance(item, dict):
                continue
            recommendation_index = HarnessRunner._normalized_recommendation_index(
                item.get("recommendation_index")
            )
            if recommendation_index is None:
                continue
            checked_files = [
                str(value).strip()
                for value in (item.get("checked_files") or [])
                if str(value).strip()
            ]
            verified_refs = [
                str(value).strip()
                for value in (item.get("verified_evidence_refs") or [])
                if str(value).strip()
            ]
            mapping[recommendation_index] = {
                "checked_files": checked_files,
                "verified_evidence_refs": verified_refs,
                "has_structured_refs": bool(checked_files or verified_refs),
            }
        return mapping

    @staticmethod
    def _structured_ref_union(proof: dict[str, Any] | None) -> list[str]:
        if not isinstance(proof, dict):
            return []
        refs: list[str] = []
        for field_name in ("verified_evidence_refs", "checked_files"):
            for value in proof.get(field_name) or []:
                text = str(value).strip()
                if text:
                    refs.append(text)
        return HarnessRunner._dedupe_preserving_order(refs)

    def _refresh_issue_prior_surfaced_refs(
        self,
        record: dict[str, Any],
        *,
        recommendation_review_proof_by_index: dict[int, dict[str, Any]],
        issue_closure_review_map: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        recommendation_index = self._normalized_recommendation_index(
            record.get("recommendation_index")
        )
        surfaced_refs: list[str] = []
        if recommendation_index is not None:
            surfaced_refs = self._structured_ref_union(
                recommendation_review_proof_by_index.get(recommendation_index)
            )
        elif issue_closure_review_map is not None:
            surfaced_refs = self._structured_ref_union(
                issue_closure_review_map.get(str(record.get("issue_id") or "").strip())
            )
        if surfaced_refs:
            record[_PRIOR_SURFACED_REFS_FIELD] = surfaced_refs

    def _refresh_topic_prior_surfaced_refs(
        self,
        record: dict[str, Any],
        *,
        recommendation_review_proof_by_index: dict[int, dict[str, Any]],
        topic_closure_review_map: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        recommendation_index = self._normalized_recommendation_index(
            record.get("recommendation_index")
        )
        surfaced_refs: list[str] = []
        if recommendation_index is not None:
            surfaced_refs = self._structured_ref_union(
                recommendation_review_proof_by_index.get(recommendation_index)
            )
        elif topic_closure_review_map is not None:
            surfaced_refs = self._structured_ref_union(
                topic_closure_review_map.get(str(record.get("topic_id") or "").strip())
            )
        if surfaced_refs:
            record[_PRIOR_SURFACED_REFS_FIELD] = surfaced_refs

    def _review_payload_ref_coverage(
        self,
        payload: dict[str, Any],
        *,
        prior_open_issue_records: list[dict[str, Any]] | None,
        prior_open_topic_records: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        covered_recommendation_indices: set[int] = set()
        uncovered_recommendation_indices: set[int] = set()
        recommendation_review_proof_by_index = (
            self._recommendation_review_proof_by_index(payload)
        )

        for item in payload.get("recommendation_reviews", []) or []:
            if not isinstance(item, dict):
                continue
            verdict = str(item.get("verdict") or "").strip().lower()
            if not verdict:
                continue
            recommendation_index = self._normalized_recommendation_index(
                item.get("recommendation_index")
            )
            if recommendation_index is None:
                continue
            proof = recommendation_review_proof_by_index.get(recommendation_index) or {}
            checked_files = list(proof.get("checked_files") or [])
            verified_refs = list(proof.get("verified_evidence_refs") or [])
            if checked_files or verified_refs:
                covered_recommendation_indices.add(recommendation_index)
                uncovered_recommendation_indices.discard(recommendation_index)
            else:
                uncovered_recommendation_indices.add(recommendation_index)

        issue_closure_review_map = self._scoped_closure_review_map(
            payload.get("issue_closure_reviews"),
            id_field="issue_id",
        )
        topic_closure_review_map = self._scoped_closure_review_map(
            payload.get("topic_closure_reviews"),
            id_field="topic_id",
        )
        uncovered_global_issue_ids: set[str] = set()
        uncovered_global_topic_ids: set[str] = set()
        closure_complete_issue_ids: set[str] = set()
        closure_complete_topic_ids: set[str] = set()
        closure_proof_by_id: dict[str, dict[str, Any]] = {}
        prior_open_issue_map = self._record_recommendation_index_map(
            prior_open_issue_records,
            id_field="issue_id",
        )
        prior_open_topic_map = self._record_recommendation_index_map(
            prior_open_topic_records,
            id_field="topic_id",
        )

        def _record_recommendation_proof(
            *,
            record_id: str,
            classification_status: str,
            recommendation_index: int,
        ) -> None:
            proof = recommendation_review_proof_by_index.get(recommendation_index) or {}
            closure_proof_by_id[record_id] = {
                "proof_path": "recommendation",
                "classification_status": classification_status,
                "checked_files": list(proof.get("checked_files") or []),
                "verified_evidence_refs": list(
                    proof.get("verified_evidence_refs") or []
                ),
                "proof_strength": "recommendation_evidence",
            }

        def _record_scoped_proof(
            *,
            record_id: str,
            classification_status: str,
            proof: dict[str, Any],
        ) -> None:
            closure_proof_by_id[record_id] = {
                "proof_path": "scoped",
                "classification_status": classification_status,
                "checked_files": list(proof.get("checked_files") or []),
                "verified_evidence_refs": list(
                    proof.get("verified_evidence_refs") or []
                ),
                "proof_strength": "review_attested",
            }

        def require_issue_coverage(
            issue_id: str, recommendation_index: int | None
        ) -> None:
            if not issue_id:
                return
            if recommendation_index is None:
                return
            if recommendation_index not in covered_recommendation_indices:
                uncovered_recommendation_indices.add(recommendation_index)

        def require_topic_coverage(
            topic_id: str, recommendation_index: int | None
        ) -> None:
            if not topic_id:
                return
            if recommendation_index is None:
                return
            if recommendation_index not in covered_recommendation_indices:
                uncovered_recommendation_indices.add(recommendation_index)

        def require_classified_issue_closure(
            issue_id: str,
            recommendation_index: int | None,
            *,
            classification_status: str,
        ) -> None:
            if not issue_id:
                return
            if recommendation_index is None:
                proof = issue_closure_review_map.get(issue_id)
                if proof and proof.get("has_structured_refs"):
                    closure_complete_issue_ids.add(issue_id)
                    _record_scoped_proof(
                        record_id=issue_id,
                        classification_status=classification_status,
                        proof=proof,
                    )
                else:
                    uncovered_global_issue_ids.add(issue_id)
                return
            if recommendation_index in covered_recommendation_indices:
                closure_complete_issue_ids.add(issue_id)
                _record_recommendation_proof(
                    record_id=issue_id,
                    classification_status=classification_status,
                    recommendation_index=recommendation_index,
                )
                return
            uncovered_recommendation_indices.add(recommendation_index)

        def require_classified_topic_closure(
            topic_id: str,
            recommendation_index: int | None,
            *,
            classification_status: str,
        ) -> None:
            if not topic_id:
                return
            if recommendation_index is None:
                proof = topic_closure_review_map.get(topic_id)
                if proof and proof.get("has_structured_refs"):
                    closure_complete_topic_ids.add(topic_id)
                    _record_scoped_proof(
                        record_id=topic_id,
                        classification_status=classification_status,
                        proof=proof,
                    )
                else:
                    uncovered_global_topic_ids.add(topic_id)
                return
            if recommendation_index in covered_recommendation_indices:
                closure_complete_topic_ids.add(topic_id)
                _record_recommendation_proof(
                    record_id=topic_id,
                    classification_status=classification_status,
                    recommendation_index=recommendation_index,
                )
                return
            uncovered_recommendation_indices.add(recommendation_index)

        for item in payload.get("issues", []) or []:
            if not isinstance(item, dict):
                continue
            require_issue_coverage(
                str(item.get("issue_id") or "").strip(),
                self._normalized_recommendation_index(item.get("recommendation_index")),
            )
        for field_name in (
            "resolved_issue_ids",
            "carried_forward_issue_ids",
            "waived_issue_ids",
        ):
            for raw_issue_id in payload.get(field_name, []) or []:
                issue_id = str(raw_issue_id or "").strip()
                if not issue_id:
                    continue
                require_classified_issue_closure(
                    issue_id,
                    prior_open_issue_map.get(issue_id),
                    classification_status=field_name.removesuffix("_issue_ids"),
                )

        for item in payload.get("topics", []) or []:
            if not isinstance(item, dict):
                continue
            require_topic_coverage(
                str(item.get("topic_id") or "").strip(),
                self._normalized_recommendation_index(item.get("recommendation_index")),
            )
        for field_name in (
            "resolved_topic_ids",
            "carried_forward_topic_ids",
            "waived_topic_ids",
        ):
            for raw_topic_id in payload.get(field_name, []) or []:
                topic_id = str(raw_topic_id or "").strip()
                if not topic_id:
                    continue
                require_classified_topic_closure(
                    topic_id,
                    prior_open_topic_map.get(topic_id),
                    classification_status=field_name.removesuffix("_topic_ids"),
                )

        return {
            "covered_recommendation_indices": sorted(covered_recommendation_indices),
            "uncovered_recommendation_indices": sorted(
                uncovered_recommendation_indices
            ),
            "issue_closure_review_ref_count": sum(
                len(item.get("checked_files") or [])
                + len(item.get("verified_evidence_refs") or [])
                for item in issue_closure_review_map.values()
                if item.get("has_structured_refs")
            ),
            "topic_closure_review_ref_count": sum(
                len(item.get("checked_files") or [])
                + len(item.get("verified_evidence_refs") or [])
                for item in topic_closure_review_map.values()
                if item.get("has_structured_refs")
            ),
            "closure_complete_issue_ids": sorted(closure_complete_issue_ids),
            "closure_complete_topic_ids": sorted(closure_complete_topic_ids),
            "uncovered_global_issue_ids": sorted(uncovered_global_issue_ids),
            "uncovered_global_topic_ids": sorted(uncovered_global_topic_ids),
            "closure_proof_by_id": closure_proof_by_id,
        }

    @staticmethod
    def _recommendation_review_ref_stats(
        normalized_refs: dict[str, Any],
    ) -> tuple[int, int]:
        ref_count = 0
        field_count = 0
        for field_name, value in normalized_refs.items():
            if not field_name.startswith("recommendation_reviews["):
                continue
            if not (
                field_name.endswith(".checked_files")
                or field_name.endswith(".verified_evidence_refs")
            ):
                continue
            if isinstance(value, list):
                value_count = len(value)
            elif value:
                value_count = 1
            else:
                value_count = 0
            if value_count <= 0:
                continue
            field_count += 1
            ref_count += value_count
        return (ref_count, field_count)

    @staticmethod
    def _scoped_closure_review_ref_count(
        normalized_refs: dict[str, Any],
        *,
        prefix: str,
    ) -> int:
        ref_count = 0
        for field_name, value in normalized_refs.items():
            if not field_name.startswith(prefix):
                continue
            if not (
                field_name.endswith(".checked_files")
                or field_name.endswith(".verified_evidence_refs")
            ):
                continue
            if isinstance(value, list):
                ref_count += len(value)
            elif value:
                ref_count += 1
        return ref_count

    @staticmethod
    def _scoped_closure_review_map(
        values: Any,
        *,
        id_field: str,
    ) -> dict[str, dict[str, Any]]:
        mapping: dict[str, dict[str, Any]] = {}
        if not isinstance(values, list):
            return mapping
        for item in values:
            if not isinstance(item, dict):
                continue
            record_id = str(item.get(id_field) or "").strip()
            if not record_id:
                continue
            checked_files = [
                str(value).strip()
                for value in (item.get("checked_files") or [])
                if str(value).strip()
            ]
            verified_refs = [
                str(value).strip()
                for value in (item.get("verified_evidence_refs") or [])
                if str(value).strip()
            ]
            mapping[record_id] = {
                "checked_files": checked_files,
                "verified_evidence_refs": verified_refs,
                "summary": str(item.get("summary") or "").strip(),
                "has_structured_refs": bool(checked_files or verified_refs),
            }
        return mapping

    @staticmethod
    def _review_payload_requires_structured_refs(payload: dict[str, Any]) -> bool:
        closure_fields = (
            "issues",
            "topics",
            "resolved_issue_ids",
            "carried_forward_issue_ids",
            "waived_issue_ids",
            "resolved_topic_ids",
            "carried_forward_topic_ids",
            "waived_topic_ids",
        )
        for field_name in closure_fields:
            values = payload.get(field_name)
            if isinstance(values, list) and values:
                return True
        return False

    def _normalize_analysis_review_payload(
        self,
        payload: dict[str, Any],
        *,
        role_name: str,
        payload_provenance_mode: str,
        contract: AnalysisReviewContract,
        prior_open_issue_records: list[dict[str, Any]] | None = None,
        prior_open_topic_records: list[dict[str, Any]] | None = None,
        selected_focus_paths: list[str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        normalized = json.loads(json.dumps(payload))
        normalized_refs: dict[str, Any] = {}
        warnings: list[str] = []
        canonical_role_name = self._canonical_stage_role_name(role_name)
        if prior_open_issue_records is None:
            prior_open_issue_records = self._open_issue_records()
        else:
            prior_open_issue_records = [dict(item) for item in prior_open_issue_records]
        if prior_open_topic_records is None:
            prior_open_topic_records = self._open_topic_records()
        else:
            prior_open_topic_records = [dict(item) for item in prior_open_topic_records]

        if canonical_role_name in {"critic", "auditor"}:
            prior_open_topics_exist = bool(prior_open_topic_records)
            for field_name in ("issue_closure_reviews", "topic_closure_reviews"):
                if field_name not in normalized:
                    normalized[field_name] = []
            reserved_topic_ids = {
                str(item.get("topic_id") or "").strip()
                for item in normalized.get("topics", []) or []
                if isinstance(item, dict) and str(item.get("topic_id") or "").strip()
            }
            normalized_topics: list[dict[str, Any]] = []
            raw_topics = normalized.get("topics")
            can_normalize_topics = raw_topics is None or isinstance(raw_topics, list)
            if can_normalize_topics:
                for item in raw_topics or []:
                    if not isinstance(item, dict):
                        continue
                    normalized_topic = self._normalize_review_topic(
                        item,
                        reserved_ids=reserved_topic_ids,
                    )
                    reserved_topic_ids.add(str(normalized_topic.get("topic_id")))
                    normalized_topics.append(normalized_topic)
                legacy_missing_topics = normalized.get("missing_topics")
                if isinstance(legacy_missing_topics, list):
                    for item in legacy_missing_topics:
                        title = str(item or "").strip()
                        if not title:
                            continue
                        normalized_topic = self._normalize_review_topic(
                            {
                                "title": title,
                                "severity": "low",
                                "evidence": "",
                                "repair_hint": "",
                                "recommendation_index": None,
                            },
                            reserved_ids=reserved_topic_ids,
                        )
                        reserved_topic_ids.add(str(normalized_topic.get("topic_id")))
                        normalized_topics.append(normalized_topic)
                    if legacy_missing_topics:
                        warnings.append(
                            "Normalized legacy missing_topics into topics with stable topic IDs."
                        )
                normalized["topics"] = normalized_topics
                normalized.pop("missing_topics", None)
            for field_name in (
                "resolved_topic_ids",
                "carried_forward_topic_ids",
                "waived_topic_ids",
            ):
                if field_name in normalized:
                    if isinstance(normalized.get(field_name), list):
                        normalized[field_name] = self._normalize_string_list(
                            normalized.get(field_name)
                        )
                elif not prior_open_topics_exist:
                    normalized[field_name] = []

        files_reviewed = self._normalize_workspace_ref_list(
            normalized.get("files_reviewed")
        )
        if files_reviewed:
            files_reviewed = self._dedupe_preserving_order(files_reviewed)
            normalized["files_reviewed"] = files_reviewed
            normalized_refs["files_reviewed"] = files_reviewed

        recommendation_reviews = normalized.get("recommendation_reviews")
        if isinstance(recommendation_reviews, list):
            for index, item in enumerate(recommendation_reviews, start=1):
                if not isinstance(item, dict):
                    continue
                for field_name in ("checked_files", "verified_evidence_refs"):
                    values = self._normalize_workspace_ref_list(item.get(field_name))
                    if values:
                        values = self._dedupe_preserving_order(values)
                        item[field_name] = values
                        normalized_refs[
                            f"recommendation_reviews[{index}].{field_name}"
                        ] = values

        for field_name, id_field in (
            ("issue_closure_reviews", "issue_id"),
            ("topic_closure_reviews", "topic_id"),
        ):
            closure_reviews = normalized.get(field_name)
            if not isinstance(closure_reviews, list):
                continue
            prior_open_ids = {
                str(item.get(id_field) or "").strip()
                for item in (
                    prior_open_issue_records
                    if field_name == "issue_closure_reviews"
                    else prior_open_topic_records
                )
                if str(item.get(id_field) or "").strip()
            }
            filtered_closure_reviews: list[dict[str, Any]] = []
            for index, item in enumerate(closure_reviews, start=1):
                if not isinstance(item, dict):
                    continue
                record_id = str(item.get(id_field) or "").strip()
                if record_id:
                    if prior_open_ids and record_id not in prior_open_ids:
                        warnings.append(
                            f"Dropped {field_name}[{index}] because it referenced an unknown prior open ID: {record_id}."
                        )
                        continue
                    item[id_field] = record_id
                for ref_field_name in ("checked_files", "verified_evidence_refs"):
                    values = self._normalize_workspace_ref_list(
                        item.get(ref_field_name)
                    )
                    if values:
                        values = self._dedupe_preserving_order(values)
                        item[ref_field_name] = values
                        normalized_refs[f"{field_name}[{index}].{ref_field_name}"] = (
                            values
                        )
                filtered_closure_reviews.append(item)
            normalized[field_name] = filtered_closure_reviews

        recommendations = normalized.get("recommendations")
        if isinstance(recommendations, list):
            for index, item in enumerate(recommendations, start=1):
                if not isinstance(item, dict):
                    continue
                evidence_values = self._dedupe_preserving_order(
                    self._normalize_workspace_ref_list(item.get("evidence"))
                )
                if evidence_values:
                    cap = contract.bounded_review.max_evidence_refs_per_recommendation
                    if (
                        contract.mode == "bounded"
                        and contract.bounded_review.evidence_cap_policy == "trim_to_cap"
                        and len(evidence_values) > cap
                    ):
                        dropped_refs = evidence_values[cap:]
                        evidence_values = evidence_values[:cap]
                        warnings.append(
                            f"recommendations[{index}].evidence exceeded the bounded-review cap of {cap}; trimmed dropped refs: "
                            + ", ".join(dropped_refs)
                        )
                    item["evidence"] = evidence_values
                    normalized_refs[f"recommendations[{index}].evidence"] = (
                        evidence_values
                    )
                for field_name in (
                    "verified_evidence_refs",
                    "checked_files",
                    "affected_files",
                ):
                    values = self._normalize_workspace_ref_list(item.get(field_name))
                    if values:
                        values = self._dedupe_preserving_order(values)
                        item[field_name] = values
                        normalized_refs[f"recommendations[{index}].{field_name}"] = (
                            values
                        )
                review_surface = item.get("review_surface")
                if isinstance(review_surface, dict):
                    for field_name in ("must_check_files", "optional_check_files"):
                        values = self._normalize_workspace_ref_list(
                            review_surface.get(field_name)
                        )
                        if values:
                            values = self._dedupe_preserving_order(values)
                            review_surface[field_name] = values
                            normalized_refs[
                                f"recommendations[{index}].review_surface.{field_name}"
                            ] = values

        self._canonicalize_analysis_payload_seams(
            normalized=normalized,
            selected_focus_paths=selected_focus_paths,
        )

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

        payload_provenance = self._bind_normalized_payload(
            normalized,
            payload_provenance_mode=payload_provenance_mode,
            normalized_refs=normalized_refs,
            prior_open_issue_records=prior_open_issue_records,
            prior_open_topic_records=prior_open_topic_records,
        )
        if (
            canonical_role_name in {"critic", "auditor"}
            and payload_provenance_mode == "payload_hash_and_refs"
            and not bool(payload_provenance.get("closure_provenance_satisfied"))
        ):
            payload_provenance["status"] = "insufficient"
            payload_provenance["failure_reason"] = (
                "trust_review_requires_structured_refs_for_recommendation_and_closure_provenance"
            )

        return (normalized, payload_provenance, warnings)

    def _canonicalize_analysis_payload_seams(
        self,
        *,
        normalized: dict[str, Any],
        selected_focus_paths: list[str] | None,
    ) -> None:
        primary_seam = normalized.get("primary_seam")
        secondary_seams = normalized.get("secondary_seams_considered")
        recommendations = normalized.get("recommendations")
        if not isinstance(primary_seam, dict) or not isinstance(secondary_seams, list):
            return

        seam_entries: list[dict[str, Any]] = [primary_seam]
        seam_entries.extend(item for item in secondary_seams if isinstance(item, dict))
        primary_canonical_seam_id: str | None = None

        del selected_focus_paths
        old_to_canonical: dict[str, str] = {}
        ambiguous_old_ids: set[str] = set()
        for seam in seam_entries:
            normalized_paths = self._dedupe_preserving_order(
                self._normalize_workspace_ref_list(seam.get("paths"))
            )
            if normalized_paths:
                seam["paths"] = normalized_paths
                canonical_seam_id = self._canonical_seam_id_for_paths(normalized_paths)
                old_seam_id = str(seam.get("seam_id") or "").strip()
                seam["seam_id"] = canonical_seam_id
                if seam is primary_seam:
                    primary_canonical_seam_id = canonical_seam_id
                if old_seam_id:
                    existing = old_to_canonical.get(old_seam_id)
                    if existing is not None and existing != canonical_seam_id:
                        ambiguous_old_ids.add(old_seam_id)
                    else:
                        old_to_canonical[old_seam_id] = canonical_seam_id

        for seam_id in ambiguous_old_ids:
            old_to_canonical.pop(seam_id, None)

        if not isinstance(recommendations, list):
            return

        for item in recommendations:
            if not isinstance(item, dict):
                continue
            old_seam_id = str(item.get("seam_id") or "").strip()
            canonical_seam_id = old_to_canonical.get(old_seam_id)
            if canonical_seam_id:
                item["seam_id"] = canonical_seam_id
            recommendation_seam_id = str(item.get("seam_id") or "").strip()
            if (
                primary_canonical_seam_id
                and recommendation_seam_id == primary_canonical_seam_id
            ):
                item["seam_expansion_reason"] = ""

    @staticmethod
    def _canonical_seam_id_for_paths(paths: list[str]) -> str:
        normalized_paths = sorted(
            {str(path).strip() for path in paths if str(path).strip()}
        )
        if not normalized_paths:
            return "seam-empty"

        stem_prefix = slugify("-".join(Path(path).stem for path in normalized_paths))[
            :48
        ].strip("-._")
        digest = hashlib.sha1("\n".join(normalized_paths).encode("utf-8")).hexdigest()[
            :12
        ]
        if stem_prefix:
            return f"{stem_prefix}-{digest}"
        return f"seam-{digest}"

    @staticmethod
    def _canonical_stage_role_name(role_name: str) -> str:
        text = str(role_name or "").strip().lower()
        if text.startswith("reviser_round_"):
            return "reviser"
        if text.startswith("patcher_round_"):
            return "patcher"
        return text

    @staticmethod
    def _normalize_string_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return [str(item).strip() for item in values if str(item).strip()]

    @staticmethod
    def _semantic_validation_kwargs(
        *,
        role_name: str,
        payload: dict[str, Any],
        task: TaskSpec,
        contract: AnalysisReviewContract,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "role_name": role_name,
            "payload": payload,
            "task": task,
            "contract": contract,
        }
        allowed = set(inspect.signature(validate_stage_output).parameters)
        for key, value in context.items():
            if key in allowed:
                kwargs[key] = value
        return kwargs

    def _topic_ids_for_status(self, statuses: set[str]) -> list[str]:
        return sorted(
            str(record.get("topic_id"))
            for record in self.topic_ledger
            if str(record.get("resolution_status") or "").strip() in statuses
            and str(record.get("topic_id") or "").strip()
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

    def _effective_role_config(
        self, role_name: str, role_config: RoleConfig
    ) -> RoleConfig:
        effective_access = role_config.access
        forced_read_roles = {
            "falsifier",
            "critic",
            "auditor",
            "focus_gate",
            "focus_gate_probe",
        }
        if role_name in forced_read_roles:
            effective_access = "read"
        elif not self.task.workspace_write_policy.allows_workspace_writes():
            effective_access = "read"
        return replace(role_config, access=effective_access)

    def _focus_gate_answer_payload(self) -> dict[str, Any] | None:
        if self.task.focus_gate_answer is None:
            return None
        return asdict(self.task.focus_gate_answer)

    @staticmethod
    def _selected_focus_id(focus_decision: dict[str, Any] | None) -> str | None:
        if not isinstance(focus_decision, dict):
            return None
        value = str(focus_decision.get("selected_focus_id") or "").strip()
        return value or None

    def _selected_focus_paths(
        self, focus_decision: dict[str, Any] | None
    ) -> list[str] | None:
        if not isinstance(focus_decision, dict):
            return None
        values = self._dedupe_preserving_order(
            self._normalize_workspace_ref_list(
                focus_decision.get("selected_focus_paths")
            )
        )
        return values or None

    def _normalize_focus_gate_candidate_payloads(
        self,
        candidates: Any,
        *,
        checked_files: list[str],
    ) -> list[dict[str, Any]]:
        if not isinstance(candidates, list):
            return []
        checked_file_set = set(checked_files)
        normalized_candidates: list[dict[str, Any]] = []
        for item in candidates[:3]:
            if not isinstance(item, dict):
                continue
            normalized_candidate = deepcopy(item)
            candidate_paths = self._dedupe_preserving_order(
                self._normalize_workspace_ref_list(item.get("candidate_paths"))
            )
            normalized_candidate["candidate_paths"] = candidate_paths
            if candidate_paths:
                normalized_candidate["focus_id"] = self._canonical_seam_id_for_paths(
                    candidate_paths
                )
            evidence_refs = self._dedupe_preserving_order(
                self._normalize_workspace_ref_list(item.get("evidence_refs"))
            )
            if checked_file_set:
                evidence_refs = [
                    ref for ref in evidence_refs if ref in checked_file_set
                ]
            else:
                evidence_refs = []
            normalized_candidate["evidence_refs"] = evidence_refs[
                :_FOCUS_MAX_EVIDENCE_REFS
            ]
            normalized_candidates.append(normalized_candidate)
        return normalized_candidates

    def _normalize_focus_gate_probe_payload(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = deepcopy(payload)
        checked_files = self._dedupe_preserving_order(
            self._normalize_workspace_ref_list(payload.get("checked_files"))
        )[:_FOCUS_MAX_CHECKED_FILES]
        normalized["checked_files"] = checked_files
        normalized["candidates"] = self._normalize_focus_gate_candidate_payloads(
            payload.get("candidates"),
            checked_files=checked_files,
        )
        return normalized

    def _normalize_focus_gate_decision_payload(
        self,
        payload: dict[str, Any],
        *,
        expected_gate_path: Any,
    ) -> dict[str, Any]:
        normalized = deepcopy(payload)
        gate_path = str(normalized.get("gate_path") or "").strip()
        checked_files = self._dedupe_preserving_order(
            self._normalize_workspace_ref_list(payload.get("checked_files"))
        )[:_FOCUS_MAX_CHECKED_FILES]
        if gate_path == "adjudicate":
            normalized["decision_basis"] = "request_only"
            normalized["files_hint_disposition"] = "absent"
            checked_files = []
        normalized["checked_files"] = checked_files
        normalized["candidates"] = self._normalize_focus_gate_candidate_payloads(
            payload.get("candidates"),
            checked_files=checked_files,
        )
        candidate_ids = [
            str(item.get("focus_id") or "").strip()
            for item in normalized["candidates"]
            if str(item.get("focus_id") or "").strip()
        ]
        selected_focus_paths = self._dedupe_preserving_order(
            self._normalize_workspace_ref_list(payload.get("selected_focus_paths"))
        )
        normalized["selected_focus_paths"] = selected_focus_paths
        if selected_focus_paths:
            canonical_focus_id = self._canonical_seam_id_for_paths(selected_focus_paths)
            normalized["selected_focus_id"] = canonical_focus_id
            adapter_plan = normalized.get("adapter_plan")
            if isinstance(adapter_plan, dict):
                adapter_plan["primary_focus_id"] = canonical_focus_id
                adapter_plan["secondary_focus_ids"] = [
                    candidate_id
                    for candidate_id in candidate_ids
                    if candidate_id != canonical_focus_id
                ]
        else:
            adapter_plan = normalized.get("adapter_plan")
            if isinstance(adapter_plan, dict):
                adapter_plan["secondary_focus_ids"] = candidate_ids
        decision_state = str(normalized.get("decision_state") or "").strip()
        question = normalized.get("question")
        if decision_state == "clarification_requested":
            prompt = ""
            if isinstance(question, dict):
                prompt = str(question.get("prompt") or "").strip()
            normalized["question"] = {"prompt": prompt, "options": candidate_ids}
        if gate_path == "adjudicate":
            question = normalized.get("question")
            if isinstance(question, dict) and decision_state != "clarification_requested":
                normalized["question"] = {"prompt": "", "options": []}
        del expected_gate_path
        return normalized

    @staticmethod
    def _probe_candidate_score_map(
        focus_probe: dict[str, Any] | None,
    ) -> dict[str, float]:
        if not isinstance(focus_probe, dict):
            return {}
        score_map: dict[str, float] = {}
        for item in focus_probe.get("candidates") or []:
            if not isinstance(item, dict):
                continue
            focus_id = str(item.get("focus_id") or "").strip()
            score = item.get("score")
            if focus_id and isinstance(score, (int, float)) and not isinstance(score, bool):
                score_map[focus_id] = float(score)
        return score_map

    @staticmethod
    def _focus_confidence_band(confidence: float) -> str:
        if confidence >= 0.80:
            return "high"
        if confidence >= 0.55:
            return "medium"
        return "low"

    @classmethod
    def _dominant_probe_candidate_against_answer(
        cls,
        *,
        focus_probe: dict[str, Any] | None,
        answered_focus_id: str,
    ) -> dict[str, Any] | None:
        if not isinstance(focus_probe, dict):
            return None
        score_map = cls._probe_candidate_score_map(focus_probe)
        answered_score = score_map.get(answered_focus_id)
        if answered_score is None:
            return None

        best_other: dict[str, Any] | None = None
        for item in focus_probe.get("candidates") or []:
            if not isinstance(item, dict):
                continue
            focus_id = str(item.get("focus_id") or "").strip()
            if not focus_id or focus_id == answered_focus_id:
                continue
            score = score_map.get(focus_id)
            if score is None:
                continue
            if best_other is None or score > float(best_other["score"]):
                best_other = {"focus_id": focus_id, "score": score}

        if best_other is None:
            return None
        if best_other["score"] >= 0.80:
            return best_other
        if best_other["score"] >= 0.55 and (best_other["score"] - answered_score) >= 0.15:
            return best_other
        return None

    @classmethod
    def _focus_gate_stale_answer_context(
        cls,
        *,
        focus_probe: dict[str, Any] | None,
        focus_gate_answer: dict[str, Any] | None,
        clarification_policy: str,
    ) -> dict[str, Any] | None:
        if not isinstance(focus_probe, dict) or not isinstance(focus_gate_answer, dict):
            return None

        answer_prompt = str(focus_gate_answer.get("question_prompt") or "").strip()
        answered_focus_id = str(focus_gate_answer.get("selected_option") or "").strip()
        if not answer_prompt or not answered_focus_id:
            return None

        candidate_ids = [
            str(item.get("focus_id") or "").strip()
            for item in (focus_probe.get("candidates") or [])
            if isinstance(item, dict) and str(item.get("focus_id") or "").strip()
        ]
        if answered_focus_id not in candidate_ids:
            return {
                "reason": "selected option vanished from the current probe candidate set",
                "clarification_policy": clarification_policy,
                "question_prompt": answer_prompt,
                "selected_option": answered_focus_id,
                "probe_candidate_ids": candidate_ids,
            }

        dominant_candidate = cls._dominant_probe_candidate_against_answer(
            focus_probe=focus_probe,
            answered_focus_id=answered_focus_id,
        )
        if dominant_candidate is None:
            return None

        return {
            "reason": (
                "current probe now makes a different candidate clearly dominant: "
                f"{dominant_candidate['focus_id']}"
            ),
            "clarification_policy": clarification_policy,
            "question_prompt": answer_prompt,
            "selected_option": answered_focus_id,
            "dominant_candidate_id": dominant_candidate["focus_id"],
            "dominant_candidate_score": dominant_candidate["score"],
            "probe_candidate_ids": candidate_ids,
        }

    @staticmethod
    def _normalized_focus_gate_no_viable_decision(
        focus_decision: dict[str, Any],
        *,
        warning: str | None = None,
    ) -> dict[str, Any]:
        normalized = deepcopy(focus_decision)
        normalized["decision_state"] = "no_viable_focus"
        normalized["selected_focus_id"] = None
        normalized["selected_focus_summary"] = None
        normalized["selected_focus_paths"] = []
        normalized["question"] = {"prompt": "", "options": []}
        adapter_plan = normalized.get("adapter_plan")
        if isinstance(adapter_plan, dict):
            adapter_plan["primary_focus_id"] = None
        warnings = [
            str(item).strip()
            for item in (normalized.get("warnings") or [])
            if str(item).strip()
        ]
        if warning and warning not in warnings:
            warnings.append(warning)
        normalized["warnings"] = warnings
        return normalized

    @classmethod
    def _stale_focus_gate_decision_from_probe(
        cls,
        *,
        focus_probe: dict[str, Any],
        focus_gate_answer: dict[str, Any] | None,
        stale_answer_context: dict[str, Any],
        clarification_policy: str,
    ) -> dict[str, Any]:
        candidates = [
            deepcopy(item)
            for item in (focus_probe.get("candidates") or [])
            if isinstance(item, dict)
        ]
        checked_files = [
            str(item).strip()
            for item in (focus_probe.get("checked_files") or [])
            if str(item).strip()
        ]
        candidate_ids = [
            str(item.get("focus_id") or "").strip()
            for item in candidates
            if str(item.get("focus_id") or "").strip()
        ]
        prompt = ""
        if isinstance(focus_gate_answer, dict):
            prompt = str(focus_gate_answer.get("question_prompt") or "").strip()
        confidence = max(
            (
                float(item.get("score"))
                for item in candidates
                if isinstance(item.get("score"), (int, float))
                and not isinstance(item.get("score"), bool)
            ),
            default=0.0,
        )
        warning = (
            "Prior focus_gate_answer went stale: "
            + str(stale_answer_context.get("reason") or "").strip()
            + "."
        )
        warnings = [
            str(item).strip()
            for item in (focus_probe.get("warnings") or [])
            if str(item).strip()
        ]
        if warning not in warnings:
            warnings.append(warning)
        decision_state = "clarification_requested"
        question = {"prompt": prompt, "options": candidate_ids}
        if clarification_policy == "never_ask" or not candidate_ids:
            decision_state = "no_viable_focus"
            question = {"prompt": "", "options": []}
        return {
            "gate_path": "deliberate",
            "focus_type": "seam",
            "decision_state": decision_state,
            "decision_basis": "rerun_answer",
            "selected_focus_id": None,
            "selected_focus_summary": None,
            "selected_focus_paths": [],
            "confidence": confidence,
            "confidence_band": cls._focus_confidence_band(confidence),
            "files_hint_disposition": str(
                focus_probe.get("files_hint_disposition") or "absent"
            ).strip(),
            "checked_files": checked_files,
            "candidates": candidates,
            "question": question,
            "warnings": warnings,
            "adapter_plan": {
                "primary_focus_id": None,
                "secondary_focus_ids": candidate_ids,
            },
        }

    def _normalize_focus_gate_decision_for_policy(
        self,
        *,
        contract: AnalysisReviewContract,
        focus_decision: dict[str, Any],
        focus_probe: dict[str, Any] | None,
        focus_gate_answer: dict[str, Any] | None,
        stale_answer_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if (
            isinstance(stale_answer_context, dict)
            and isinstance(focus_probe, dict)
            and focus_probe
        ):
            return self._stale_focus_gate_decision_from_probe(
                focus_probe=focus_probe,
                focus_gate_answer=focus_gate_answer,
                stale_answer_context=stale_answer_context,
                clarification_policy=contract.focus_gate.clarification_policy,
            )

        decision_state = str(focus_decision.get("decision_state") or "").strip()
        if (
            decision_state == "clarification_requested"
            and contract.focus_gate.clarification_policy == "never_ask"
        ):
            warning = None
            if isinstance(stale_answer_context, dict):
                reason = str(stale_answer_context.get("reason") or "").strip()
                if reason:
                    warning = f"Prior focus_gate_answer went stale: {reason}."
            return self._normalized_focus_gate_no_viable_decision(
                focus_decision,
                warning=warning,
            )
        return focus_decision

    @staticmethod
    def _focus_gate_stage_metadata(
        focus_decision: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "focus_gate": {
                "gate_path": focus_decision.get("gate_path"),
                "focus_type": focus_decision.get("focus_type"),
                "decision_state": focus_decision.get("decision_state"),
            }
        }

    @staticmethod
    def _focus_gate_probe_stage_metadata(
        focus_probe: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "focus_gate_probe": {
                "focus_type": focus_probe.get("focus_type"),
                "files_hint_disposition": focus_probe.get("files_hint_disposition"),
                "candidate_count": len(focus_probe.get("candidates") or []),
            }
        }

    def _sync_persisted_focus_gate_stage(
        self,
        *,
        focus_decision: dict[str, Any],
    ) -> None:
        for stage_record in reversed(self.agent_stages):
            if stage_record.get("role_name") != "focus_gate":
                continue
            stage_record["structured_output"] = deepcopy(focus_decision)
            stage_record["metadata"] = self._focus_gate_stage_metadata(focus_decision)

            stdout_path = str(stage_record.get("stdout_path") or "").strip()
            if stdout_path:
                envelope_path = Path(stdout_path).with_name("run.envelope.json")
                write_json(envelope_path, stage_record)
            normalized_output_path = (
                str(stage_record.get("normalized_output_path") or "").strip()
                or str(stage_record.get("output_path") or "").strip()
            )
            if normalized_output_path:
                write_json(Path(normalized_output_path), focus_decision)
            return

    def _build_focus_gate_blocked_outcome(
        self,
        *,
        contract: AnalysisReviewContract,
        focus_decision: dict[str, Any],
    ) -> dict[str, Any]:
        decision_state = str(focus_decision.get("decision_state") or "").strip()
        if decision_state == "clarification_requested":
            return {
                "run_verdict": "blocked_for_clarification",
                "content_verdict": "blocked_for_clarification",
                "validator_verdict": "not_run",
                "final_summary": "Focus gate blocked the run pending clarification.",
                "failure_details": {
                    "stage": "focus_gate",
                    "decision_state": "clarification_requested",
                    "question": focus_decision.get("question"),
                    "candidates": focus_decision.get("candidates"),
                    "warnings": focus_decision.get("warnings"),
                },
                "details": {
                    "focus_decision": focus_decision,
                    "review_loop_exercised": False,
                    "analysis_review_contract": contract.to_dict(),
                },
            }
        return {
            "run_verdict": "no_viable_focus",
            "content_verdict": "no_viable_focus",
            "validator_verdict": "not_run",
            "final_summary": "Focus gate could not identify a viable focus target.",
            "failure_details": {
                "stage": "focus_gate",
                "decision_state": "no_viable_focus",
                "candidates": focus_decision.get("candidates"),
                "warnings": focus_decision.get("warnings"),
            },
            "details": {
                "focus_decision": focus_decision,
                "review_loop_exercised": False,
                "analysis_review_contract": contract.to_dict(),
            },
        }

    def _execute_focus_gate_probe_stage(
        self,
        *,
        contract: AnalysisReviewContract,
        role_cfg: RoleConfig,
        record_stage: bool,
        record_workspace_policy_check: bool,
    ) -> ProviderRun:
        prompt = build_focus_probe_prompt(
            self.task,
            self.strategy.prompt_preamble,
            capture_git_snapshot(
                self.workspace,
                ignored_rel_paths=self.policy_ignored_rel_paths,
            ),
            contract,
        )
        return self._run_agent_stage(
            "focus_gate_probe",
            role_cfg.provider,
            prompt,
            focus_gate_probe_output_schema(),
            role_cfg,
            semantic_context={"contract": contract},
            record_stage=record_stage,
            record_workspace_policy_check=record_workspace_policy_check,
        )

    def _execute_focus_gate_stage(
        self,
        *,
        contract: AnalysisReviewContract,
        role_cfg: RoleConfig,
        gate_path: str,
        focus_probe: dict[str, Any] | None,
        focus_gate_answer: dict[str, Any] | None,
        stale_answer_context: dict[str, Any] | None,
        record_stage: bool,
        record_workspace_policy_check: bool,
    ) -> ProviderRun:
        git_snapshot = capture_git_snapshot(
            self.workspace,
            ignored_rel_paths=self.policy_ignored_rel_paths,
        )
        if gate_path == "adjudicate":
            prompt = build_focus_gate_adjudicate_prompt(
                self.task,
                self.strategy.prompt_preamble,
                git_snapshot,
                contract,
                focus_probe=focus_probe,
                focus_gate_answer=focus_gate_answer,
                prior_focus_decision=None,
                stale_answer_context=stale_answer_context,
            )
        else:
            prompt = build_focus_gate_deliberate_prompt(
                self.task,
                self.strategy.prompt_preamble,
                git_snapshot,
                contract,
                focus_probe=focus_probe,
                focus_gate_answer=focus_gate_answer,
                prior_focus_decision=None,
                stale_answer_context=stale_answer_context,
            )
        return self._run_agent_stage(
            "focus_gate",
            role_cfg.provider,
            prompt,
            focus_gate_output_schema(),
            role_cfg,
            semantic_context={
                "contract": contract,
                "expected_gate_path": gate_path,
            },
            record_stage=record_stage,
            record_workspace_policy_check=record_workspace_policy_check,
        )

    def _run_focus_gate(
        self,
        *,
        contract: AnalysisReviewContract,
        role_cfg: RoleConfig,
    ) -> dict[str, Any]:
        focus_gate_answer = self._focus_gate_answer_payload()
        default_gate_path = contract.focus_gate.default_path
        assert not (
            default_gate_path == "adjudicate" and focus_gate_answer is not None
        ), "adjudicate focus-gate runs cannot consume focus_gate_answer."

        if default_gate_path == "deliberate":
            probe_run = self._execute_focus_gate_probe_stage(
                contract=contract,
                role_cfg=role_cfg,
                record_stage=True,
                record_workspace_policy_check=True,
            )
            if not probe_run.ok:
                return {
                    "kind": "failed",
                    "run": probe_run,
                    "stage_label": "focus_gate_probe",
                }

            focus_probe = probe_run.structured_output or {}
            stale_answer_context = self._focus_gate_stale_answer_context(
                focus_probe=focus_probe,
                focus_gate_answer=focus_gate_answer,
                clarification_policy=contract.focus_gate.clarification_policy,
            )
            focus_gate_run = self._execute_focus_gate_stage(
                contract=contract,
                role_cfg=role_cfg,
                gate_path="deliberate",
                focus_probe=focus_probe,
                focus_gate_answer=focus_gate_answer,
                stale_answer_context=stale_answer_context,
                record_stage=True,
                record_workspace_policy_check=True,
            )
            if not focus_gate_run.ok:
                return {
                    "kind": "failed",
                    "run": focus_gate_run,
                    "stage_label": "focus_gate",
                }

            focus_decision = self._normalize_focus_gate_decision_for_policy(
                contract=contract,
                focus_decision=focus_gate_run.structured_output or {},
                focus_probe=focus_probe,
                focus_gate_answer=focus_gate_answer,
                stale_answer_context=stale_answer_context,
            )
            self._sync_persisted_focus_gate_stage(focus_decision=focus_decision)
            if str(focus_decision.get("decision_state") or "").strip() in {
                "clarification_requested",
                "no_viable_focus",
            }:
                return {
                    "kind": "blocked",
                    "outcome": self._build_focus_gate_blocked_outcome(
                        contract=contract,
                        focus_decision=focus_decision,
                    ),
                }
            return {"kind": "selected", "focus_decision": focus_decision}

        focus_gate_run = self._execute_focus_gate_stage(
            contract=contract,
            role_cfg=role_cfg,
            gate_path=default_gate_path,
            focus_probe=None,
            focus_gate_answer=None,
            stale_answer_context=None,
            record_stage=True,
            record_workspace_policy_check=True,
        )
        if not focus_gate_run.ok:
            return {
                "kind": "failed",
                "run": focus_gate_run,
                "stage_label": "focus_gate",
            }
        focus_decision = self._normalize_focus_gate_decision_for_policy(
            contract=contract,
            focus_decision=focus_gate_run.structured_output or {},
            focus_probe=None,
            focus_gate_answer=None,
            stale_answer_context=None,
        )
        self._sync_persisted_focus_gate_stage(focus_decision=focus_decision)
        if str(focus_decision.get("decision_state") or "").strip() in {
            "clarification_requested",
            "no_viable_focus",
        }:
            return {
                "kind": "blocked",
                "outcome": self._build_focus_gate_blocked_outcome(
                    contract=contract,
                    focus_decision=focus_decision,
                ),
            }
        return {"kind": "selected", "focus_decision": focus_decision}

    def _emit_task_strategy_warnings(self) -> None:
        if self.strategy.kind == ANALYSIS_REVIEW_LEGACY_KIND:
            self.warnings.append(
                "Strategy kind analysis_review_v1 is deprecated and now resolves to analysis_review_bounded_v1."
            )
        if self.task.task_kind == "analysis_review" and self.strategy.kind in {
            "pfr_v1",
            "single_pass",
        }:
            self.warnings.append(
                "This task looks like an analysis_review task, but the selected strategy is patch-oriented. "
                "analysis_review_bounded_v1 or analysis_review_trust_v1 will usually be a better fit."
            )
        if self.task.task_kind == "patch" and is_analysis_review_strategy_kind(
            self.strategy.kind
        ):
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
        elif self.task.task_kind == "patch" and is_analysis_review_strategy_kind(
            self.strategy.kind
        ):
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
                reason = str(
                    item.get("reason")
                    or f"Validator {item.get('name')} is misconfigured."
                )
                preflight_errors.append(reason)
            elif not item.get("required") and status in {"failed", "not_applicable"}:
                self.warnings.append(
                    str(
                        item.get("reason")
                        or f"Optional validator {item.get('name')} is not applicable."
                    )
                )

        if not preflight_errors:
            return None

        self.errors.extend(preflight_errors)
        return {
            "run_verdict": "invalid_config",
            "content_verdict": "rejected",
            "validator_verdict": "misconfigured",
            "config_verdict": "invalid_config",
            "final_summary": preflight_errors[0],
            "failure_details": {
                "preflight_errors": preflight_errors,
                "validator_preflight": preflight,
            },
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
                        + (
                            f", ... (+{len(dirty_paths) - 8} more)"
                            if len(dirty_paths) > 8
                            else ""
                        )
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

    def _derive_final_answer_payload(
        self, run_details: dict[str, Any]
    ) -> dict[str, Any] | None:
        candidate_keys = ("final_analysis", "final_solution")
        for key in candidate_keys:
            candidate = run_details.get(key)
            if isinstance(candidate, dict) and candidate:
                return candidate
        return None

    def _write_final_answer_artifacts(
        self, payload: dict[str, Any] | None
    ) -> dict[str, str]:
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
            lines.extend(
                [
                    "## Structured Output",
                    "",
                    "```json",
                    json.dumps(payload, indent=2, sort_keys=False),
                    "```",
                    "",
                ]
            )
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
                required_status_counts[status] = (
                    required_status_counts.get(status, 0) + 1
                )
        latest_round_results = self._latest_validator_results()
        return {
            "total_runs": len(all_results),
            "status_counts": status_counts,
            "required_status_counts": required_status_counts,
            "latest_round_verdict": self._classify_validator_verdict(
                latest_round_results
            ),
        }
