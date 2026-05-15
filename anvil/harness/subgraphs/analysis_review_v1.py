from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from anvil.orchestrator import reload_config

from .. import analysis_review_runtime
from ..contracts import resolve_analysis_review_contract
from ..git_utils import (
    capture_git_snapshot,
    capture_non_git_workspace_state,
    changed_files,
    git_snapshot_is_dirty,
)
from ..runner import HarnessError, HarnessRunner
from ..selection import extract_drafts_from_summary, select_best_draft
from ..state import (
    LEGACY_BRIDGE_BOUNDARY_VERSION,
    HarnessState,
    stage_records_from_summary,
)
from ..types import ANALYSIS_REVIEW_BOUNDED_KIND, StrategyConfig, TaskSpec
from ._bridge import LegacyBridgeBoundary

_RUNNER_KEY = "__analysis_review_runner"
_ROOT_CONTRACT_KEY = "__analysis_review_root_contract"
_REVIEW_CONTRACT_KEY = "__analysis_review_review_contract"
_RUNTIME_KEY = "__analysis_review_runtime"
_FOCUS_DECISION_KEY = "__analysis_review_focus_decision"
_TERMINAL_OUTCOME_KEY = "__analysis_review_terminal_outcome"
_TERMINAL_ROUTE_KEY = "__analysis_review_terminal_route"
_LATEST_ANALYSIS_KEY = "__analysis_review_latest_analysis_payload"
_LATEST_REVIEW_KEY = "__analysis_review_latest_review_payload"
_VALIDATION_RUNS_KEY = "__analysis_review_validation_runs"
_TRUST_DETAILS_KEY = "__analysis_review_trust_details"


def _runtime_snapshot(state: HarnessState) -> dict[str, Any]:
    return analysis_review_runtime.runtime_snapshot(state.get("analysis_review_runtime"))


def _activate_runner_contract(state: HarnessState, contract_key: str) -> HarnessRunner:
    runner: HarnessRunner = state[_RUNNER_KEY]
    runner.analysis_review_contract = state[contract_key]
    return runner


def _build_graph_owned_runner(state: HarnessState) -> HarnessRunner:
    task_spec = dict(state.get("task_spec") or {})
    strategy_spec = dict(state.get("strategy_spec") or {})
    runner = HarnessRunner(
        task_path=str(state.get("task_path") or ""),
        strategy_path=str(state.get("strategy_path") or ""),
        workspace=str(state.get("workspace_root") or ""),
        out_root=str(state.get("out_root") or ".forge-harness-runs"),
        config_path=str(state.get("config_path") or "config/models.yaml"),
        task_data=task_spec,
        strategy_data=strategy_spec,
        thread_id=(str(state.get("thread_id")) if state.get("thread_id") else None),
        auto_fit_strategy=bool(state.get("auto_fit_strategy", True)),
    )
    reload_config(str(runner.config_path))

    runner.run_dir = Path(str(state.get("run_dir") or runner.out_root))
    runner.run_dir.mkdir(parents=True, exist_ok=True)
    runner.validators_dir = runner.run_dir / "validators"
    runner.artifacts_dir = runner.run_dir / "artifacts"
    runner.validators_dir.mkdir(parents=True, exist_ok=True)
    runner.artifacts_dir.mkdir(parents=True, exist_ok=True)

    runner.initial_git_snapshot = capture_git_snapshot(
        runner.workspace,
        ignored_rel_paths=runner.policy_ignored_rel_paths,
    )
    if not runner.initial_git_snapshot.get("is_git"):
        runner.initial_non_git_state = capture_non_git_workspace_state(
            runner.workspace,
            ignored_rel_paths=runner.policy_ignored_rel_paths,
        )
    if runner.initial_git_snapshot.get("is_git") and git_snapshot_is_dirty(
        runner.initial_git_snapshot
    ):
        runner.warnings.append(
            "Workspace is dirty at start. The harness will operate on the existing working tree. "
            "Use workspace_write_policy.require_clean_start=true to block this."
        )
    return runner


def _prepare_graph_owned_state(state: HarnessState) -> HarnessState:
    if str(state.get("analysis_review_execution_mode") or "legacy_bridge") != "graph_owned":
        return state

    runner = _build_graph_owned_runner(state)
    root_contract = runner._analysis_contract()
    review_contract = root_contract

    if (
        root_contract.mode == "trust"
        and root_contract.trust_review.execution_mode == "attestation_over_bounded"
    ):
        bounded_strategy_payload = dict(runner.strategy.to_dict())
        bounded_strategy_payload["kind"] = ANALYSIS_REVIEW_BOUNDED_KIND
        bounded_strategy = StrategyConfig.from_dict(bounded_strategy_payload)
        review_contract = resolve_analysis_review_contract(runner.task, bounded_strategy)

    payload = dict(state)
    payload[_RUNNER_KEY] = runner
    payload[_ROOT_CONTRACT_KEY] = root_contract
    payload[_REVIEW_CONTRACT_KEY] = review_contract
    payload[_RUNTIME_KEY] = _runtime_snapshot(state)
    payload["analysis_review_contract"] = root_contract.to_dict()
    payload["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(
        payload[_RUNTIME_KEY]
    )
    return payload


def route_execution_mode(state: HarnessState) -> str:
    if str(state.get("analysis_review_execution_mode") or "legacy_bridge") != "graph_owned":
        return "legacy_bridge"

    contract = state.get(_ROOT_CONTRACT_KEY)
    if contract is None:
        return "legacy_bridge"
    if contract.focus_gate.enabled:
        return "focus_gate"
    return "proposer"


def _set_terminal_outcome(
    state: HarnessState,
    *,
    route: str,
    outcome: dict[str, Any],
) -> HarnessState:
    state[_TERMINAL_ROUTE_KEY] = route
    state[_TERMINAL_OUTCOME_KEY] = outcome
    return state


def _focus_terminal_route(focus_decision: dict[str, Any] | None) -> str:
    decision_state = str((focus_decision or {}).get("decision_state") or "").strip()
    if decision_state == "no_viable_focus":
        return "finish_no_viable_focus"
    return "finish_blocked"


def _graph_owned_focus_gate(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _ROOT_CONTRACT_KEY)
    contract = state[_ROOT_CONTRACT_KEY]
    runtime = state[_RUNTIME_KEY]
    focus_gate_outcome = analysis_review_runtime.execute_focus_gate(
        runtime=runtime,
        contract=contract,
        run_focus_gate=runner._run_analysis_focus_gate_stage,
    )

    if focus_gate_outcome["kind"] == "selected":
        state[_FOCUS_DECISION_KEY] = focus_gate_outcome["focus_decision"]
        state["focus_decision"] = deepcopy(focus_gate_outcome["focus_decision"])
    elif focus_gate_outcome["kind"] == "failed":
        outcome = analysis_review_runtime.attach_runtime_details(
            runner._analysis_stage_failure_outcome(
                stage_label="focus_gate",
                run=focus_gate_outcome["run"],
                validator_verdict="not_run",
                review_loop_exercised=False,
                final_analysis=None,
                contract=contract,
            ),
            runtime,
        )
        _set_terminal_outcome(state, route="finish_terminal", outcome=outcome)
    else:
        focus_decision = focus_gate_outcome["outcome"].get("details", {}).get("focus_decision")
        if isinstance(focus_decision, dict) and focus_decision:
            state["focus_decision"] = deepcopy(focus_decision)
        _set_terminal_outcome(
            state,
            route=_focus_terminal_route(focus_decision),
            outcome=focus_gate_outcome["outcome"],
        )

    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return state


def route_focus_gate_outcome(state: HarnessState) -> str:
    if state.get(_TERMINAL_OUTCOME_KEY):
        return str(state.get(_TERMINAL_ROUTE_KEY) or "finish_terminal")
    return "proposer"


def _graph_owned_proposer(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _REVIEW_CONTRACT_KEY)
    review_contract = state[_REVIEW_CONTRACT_KEY]
    runtime = state[_RUNTIME_KEY]
    focus_decision = state.get(_FOCUS_DECISION_KEY)

    proposer_run = runner._run_analysis_proposer_stage(
        contract=review_contract,
        focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
    )
    if not proposer_run.ok:
        outcome = analysis_review_runtime.attach_runtime_details(
            runner._analysis_stage_failure_outcome(
                stage_label="proposer",
                run=proposer_run,
                validator_verdict=runner._classify_validator_verdict([]),
                review_loop_exercised=False,
                final_analysis=None,
                contract=review_contract,
                focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
            ),
            runtime,
        )
        _set_terminal_outcome(state, route="finish_terminal", outcome=outcome)
        state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
        return state

    runtime["current_analysis_payload"] = deepcopy(proposer_run.structured_output or {})
    runtime["transition_reason"] = "proposer_completed"
    state[_LATEST_ANALYSIS_KEY] = proposer_run.structured_output or {}

    validation_runs = runner._run_validator_round(0)
    runtime["latest_validator_round"] = [item.to_dict() for item in validation_runs]
    runtime["transition_reason"] = "validator_round_completed"
    runtime["revisions_completed"] = 0
    runtime["max_loops"] = runner._analysis_review_max_loops()
    state[_VALIDATION_RUNS_KEY] = validation_runs
    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return state


def _graph_owned_critic(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _REVIEW_CONTRACT_KEY)
    review_contract = state[_REVIEW_CONTRACT_KEY]
    runtime = state[_RUNTIME_KEY]
    focus_decision = state.get(_FOCUS_DECISION_KEY)
    latest_analysis_payload = state.get(_LATEST_ANALYSIS_KEY)
    validation_runs = list(state.get(_VALIDATION_RUNS_KEY) or [])

    critic_run = runner._run_analysis_critic_stage(
        contract=review_contract,
        prior_output=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
        validation_runs=validation_runs,
    )
    if not critic_run.ok:
        outcome = analysis_review_runtime.attach_runtime_details(
            runner._analysis_stage_failure_outcome(
                stage_label="critic",
                run=critic_run,
                validator_verdict=runner._classify_validator_verdict(validation_runs),
                review_loop_exercised=False,
                final_analysis=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
                contract=review_contract,
                focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
            ),
            runtime,
        )
        _set_terminal_outcome(state, route="finish_terminal", outcome=outcome)
        state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
        return state

    runner._ingest_review_payload(
        critic_run.structured_output or {},
        round_index=0,
        role_name="critic",
        reviser_output=None,
    )
    runtime["current_review_payload"] = deepcopy(critic_run.structured_output or {})
    runtime["review_loop_exercised"] = True
    runtime["transition_reason"] = "critic_completed"
    state[_LATEST_REVIEW_KEY] = critic_run.structured_output or {}
    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return state


def route_critic_revision(state: HarnessState) -> str:
    if state.get(_TERMINAL_OUTCOME_KEY):
        return str(state.get(_TERMINAL_ROUTE_KEY) or "finish_terminal")

    runner: HarnessRunner = state[_RUNNER_KEY]
    runtime = state[_RUNTIME_KEY]
    latest_review_payload = state.get(_LATEST_REVIEW_KEY)
    revisions_completed = int(state[_RUNTIME_KEY].get("revisions_completed") or 0)
    if runner._analysis_needs_revision(
        latest_review_payload if isinstance(latest_review_payload, dict) else {},
        revisions_completed,
    ):
        return "reviser"
    runtime["transition_reason"] = "stop_policy_satisfied"
    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return "trust_attestation_gate"


def _graph_owned_reviser(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _REVIEW_CONTRACT_KEY)
    review_contract = state[_REVIEW_CONTRACT_KEY]
    runtime = state[_RUNTIME_KEY]
    focus_decision = state.get(_FOCUS_DECISION_KEY)
    latest_analysis_payload = state.get(_LATEST_ANALYSIS_KEY)
    latest_review_payload = state.get(_LATEST_REVIEW_KEY)
    validation_runs = list(state.get(_VALIDATION_RUNS_KEY) or [])

    revision_round = int(runtime.get("revisions_completed") or 0) + 1
    runtime["revisions_completed"] = revision_round

    reviser_run = runner._run_analysis_reviser_stage(
        contract=review_contract,
        focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
        latest_analysis_payload=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
        latest_review_payload=latest_review_payload if isinstance(latest_review_payload, dict) else None,
        validation_runs=validation_runs,
        revision_round=revision_round,
    )
    if not reviser_run.ok:
        outcome = analysis_review_runtime.attach_runtime_details(
            runner._analysis_stage_failure_outcome(
                stage_label=f"reviser round {revision_round}",
                run=reviser_run,
                validator_verdict=runner._classify_validator_verdict(validation_runs),
                review_loop_exercised=True,
                final_analysis=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
                contract=review_contract,
                focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
            ),
            runtime,
        )
        _set_terminal_outcome(state, route="finish_terminal", outcome=outcome)
        state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
        return state

    runtime["current_analysis_payload"] = deepcopy(reviser_run.structured_output or {})
    runtime["transition_reason"] = "reviser_completed"
    state[_LATEST_ANALYSIS_KEY] = reviser_run.structured_output or {}
    state["revision_round"] = revision_round
    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return state


def _graph_owned_auditor(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _REVIEW_CONTRACT_KEY)
    review_contract = state[_REVIEW_CONTRACT_KEY]
    runtime = state[_RUNTIME_KEY]
    focus_decision = state.get(_FOCUS_DECISION_KEY)
    latest_analysis_payload = state.get(_LATEST_ANALYSIS_KEY)
    validation_runs = list(state.get(_VALIDATION_RUNS_KEY) or [])
    revision_round = int(runtime.get("revisions_completed") or 0)

    auditor_run = runner._run_analysis_auditor_stage(
        contract=review_contract,
        prior_output=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
        validation_runs=validation_runs,
        round_index=revision_round,
        reviser_output=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
    )
    if not auditor_run.ok:
        outcome = analysis_review_runtime.attach_runtime_details(
            runner._analysis_stage_failure_outcome(
                stage_label="auditor",
                run=auditor_run,
                validator_verdict=runner._classify_validator_verdict(validation_runs),
                review_loop_exercised=True,
                final_analysis=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
                contract=review_contract,
                focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
            ),
            runtime,
        )
        _set_terminal_outcome(state, route="finish_terminal", outcome=outcome)
        state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
        return state

    runner._ingest_review_payload(
        auditor_run.structured_output or {},
        round_index=revision_round,
        role_name="auditor",
        reviser_output=latest_analysis_payload if isinstance(latest_analysis_payload, dict) else None,
    )
    runtime["current_review_payload"] = deepcopy(auditor_run.structured_output or {})
    runtime["review_loop_exercised"] = True
    runtime["transition_reason"] = "auditor_completed"
    state[_LATEST_REVIEW_KEY] = auditor_run.structured_output or {}
    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return state


def route_auditor_revision(state: HarnessState) -> str:
    if state.get(_TERMINAL_OUTCOME_KEY):
        return str(state.get(_TERMINAL_ROUTE_KEY) or "finish_terminal")

    runner: HarnessRunner = state[_RUNNER_KEY]
    runtime = state[_RUNTIME_KEY]
    latest_review_payload = state.get(_LATEST_REVIEW_KEY)
    revisions_completed = int(runtime.get("revisions_completed") or 0)
    if not runner._analysis_needs_revision(
        latest_review_payload if isinstance(latest_review_payload, dict) else {},
        revisions_completed,
    ):
        runtime["transition_reason"] = "stop_policy_satisfied"
        state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
        return "trust_attestation_gate"

    if revisions_completed >= int(runtime.get("max_loops") or 0):
        runtime["transition_reason"] = "max_loops_exhausted"
        state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
        return "finish_loop_exhausted"

    return "reviser"


def _trust_attestation_required(state: HarnessState) -> bool:
    root_contract = state.get(_ROOT_CONTRACT_KEY)
    return bool(
        root_contract is not None
        and root_contract.mode == "trust"
        and root_contract.trust_review.execution_mode == "attestation_over_bounded"
    )


def _trust_attestation_gate(state: HarnessState) -> HarnessState:
    return state


def route_trust_attestation(state: HarnessState) -> str:
    if _trust_attestation_required(state):
        return "attestation_auditor"
    return "finish_complete"


def _graph_owned_attestation_auditor(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _ROOT_CONTRACT_KEY)
    root_contract = state[_ROOT_CONTRACT_KEY]
    review_contract = state[_REVIEW_CONTRACT_KEY]
    runtime = state[_RUNTIME_KEY]
    focus_decision = state.get(_FOCUS_DECISION_KEY)
    revisions_completed = int(runtime.get("revisions_completed") or 0)
    validation_runs = list(state.get(_VALIDATION_RUNS_KEY) or [])
    final_analysis_payload = state.get(_LATEST_ANALYSIS_KEY)

    bounded_run_details: dict[str, Any] = {
        "analysis_review_contract": review_contract.to_dict(),
        "final_analysis": final_analysis_payload if isinstance(final_analysis_payload, dict) else {},
        "issue_ledger": runner._serialized_issue_ledger(),
        "topic_ledger": runner._serialized_topic_ledger(),
        "focus_decision": focus_decision if isinstance(focus_decision, dict) else None,
    }
    if isinstance(runtime.get("focus_refinement"), dict):
        bounded_run_details["focus_refinement"] = runtime["focus_refinement"]
    bounded_review_summary = runner._build_bounded_review_summary(bounded_run_details)
    if bounded_review_summary is None:
        raise HarnessError(
            "attestation_over_bounded requires a bounded_review_summary before attestation."
        )
    bounded_run_details["bounded_review_summary"] = bounded_review_summary
    bounded_attestation_input = runner._build_bounded_attestation_input(
        bounded_run_details
    )
    if bounded_attestation_input is None:
        raise HarnessError(
            "attestation_over_bounded requires bounded_attestation_input before attestation."
        )

    attestation = analysis_review_runtime.execute_trust_attestation(
        runtime=runtime,
        contract=root_contract,
        focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
        revisions_completed=revisions_completed,
        validation_runs=validation_runs,
        final_analysis_payload=final_analysis_payload if isinstance(final_analysis_payload, dict) else {},
        bounded_attestation_input=bounded_attestation_input,
        run_trust_attestation_stage=runner._run_analysis_trust_attestation_stage,
        ingest_review_payload=runner._ingest_review_payload,
        classify_validator_verdict=runner._classify_validator_verdict,
        build_stage_failure_outcome=runner._analysis_stage_failure_outcome,
    )
    if "failure_outcome" in attestation:
        _set_terminal_outcome(
            state,
            route="finish_terminal",
            outcome=attestation["failure_outcome"],
        )
    else:
        state[_LATEST_REVIEW_KEY] = attestation["attestation_run"].structured_output or {}
        state[_TRUST_DETAILS_KEY] = {
            "bounded_review_summary": bounded_review_summary,
            "bounded_attestation_input": bounded_attestation_input,
        }

    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    return state


def _draft_summary_from_runner(runner: HarnessRunner) -> dict[str, Any]:
    return {
        "task": runner.task.to_dict(),
        "agent_stages": deepcopy(runner.agent_stages),
        "validator_rounds": deepcopy(runner.validator_rounds),
    }


def _merge_runner_state(state: HarnessState) -> HarnessState:
    runner: HarnessRunner = state[_RUNNER_KEY]
    runtime = state[_RUNTIME_KEY]
    root_contract = state[_ROOT_CONTRACT_KEY]
    policy_ignored_rel_paths = list(getattr(runner, "policy_ignored_rel_paths", []))

    normalized_stage_history = stage_records_from_summary(
        {"agent_stages": deepcopy(runner.agent_stages)}
    )
    drafts = extract_drafts_from_summary(_draft_summary_from_runner(runner))
    best_draft = select_best_draft(drafts)
    final_policy_evaluation = next(
        (
            deepcopy(check)
            for check in reversed(runner.workspace_policy_checks)
            if isinstance(check, dict) and check.get("final") is True
        ),
        {},
    )
    final_git_snapshot: dict[str, Any] = {}
    current_workspace_state = None
    if hasattr(runner, "workspace"):
        final_git_snapshot = capture_git_snapshot(
            runner.workspace,
            ignored_rel_paths=policy_ignored_rel_paths,
        )
        if not final_git_snapshot.get("is_git"):
            current_workspace_state = capture_non_git_workspace_state(
                runner.workspace,
                ignored_rel_paths=policy_ignored_rel_paths,
            )
    changed_paths = []
    if final_git_snapshot:
        changed_paths = (
            changed_files(final_git_snapshot)
            if final_git_snapshot.get("is_git")
            else list(final_policy_evaluation.get("touched_files", []))
        )

    state["analysis_review_contract"] = root_contract.to_dict()
    state["analysis_review_runtime"] = analysis_review_runtime.runtime_snapshot(runtime)
    state["stage_history"] = normalized_stage_history
    state["validator_rounds"] = deepcopy(runner.validator_rounds)
    state["policy_checks"] = deepcopy(runner.workspace_policy_checks)
    state["drafts"] = drafts
    state["warnings"] = list(state.get("warnings") or []) + list(runner.warnings)
    state["errors"] = list(state.get("errors") or []) + list(runner.errors)
    state["stage_counter"] = int(runner.stage_counter)
    state["revision_round"] = int(runtime.get("revisions_completed") or 0)
    state["issue_history"] = deepcopy(runner._serialized_issue_ledger())
    state["topic_ledger"] = deepcopy(runner._serialized_topic_ledger())
    state["current_draft_id"] = drafts[-1].get("draft_id") if drafts else None
    state["best_draft_id"] = best_draft.get("draft_id") if best_draft else None
    state["selected_draft_id"] = state["current_draft_id"]
    state["open_issue_ids"] = [
        str(item.get("issue_id") or "")
        for item in state["issue_history"]
        if str(item.get("resolution_status") or "") in {"open", "carried_forward"}
    ]
    state["initial_git_snapshot"] = deepcopy(getattr(runner, "initial_git_snapshot", {}))
    state["current_git_snapshot"] = final_git_snapshot
    state["current_workspace_state"] = current_workspace_state
    state["workspace_policy_ignored_rel_paths"] = policy_ignored_rel_paths
    state["validator_summary"] = (
        runner._summarize_validator_rounds()
        if hasattr(runner, "_summarize_validator_rounds")
        else {}
    )
    state["analysis_review_coverage"] = (
        runner._analysis_review_coverage()
        if hasattr(runner, "_analysis_review_coverage")
        else {}
    )
    state["final_workspace_policy_evaluation"] = final_policy_evaluation
    state["changed_files"] = changed_paths
    state["config_path"] = str(getattr(runner, "config_path", ""))
    state["bridge_boundary_version"] = LEGACY_BRIDGE_BOUNDARY_VERSION
    focus_decision = state.get(_FOCUS_DECISION_KEY)
    if isinstance(focus_decision, dict) and focus_decision:
        state["focus_decision"] = deepcopy(focus_decision)
    return state


def _apply_outcome_to_state(state: HarnessState, outcome: dict[str, Any]) -> HarnessState:
    _merge_runner_state(state)
    runner: HarnessRunner = state[_RUNNER_KEY]
    state["run_verdict"] = str(outcome.get("run_verdict") or "harness_error")
    state["content_verdict"] = str(
        outcome.get("content_verdict") or state.get("run_verdict") or "harness_error"
    )
    state["validator_verdict"] = str(outcome.get("validator_verdict") or "not_run")
    state["summary_text"] = str(outcome.get("final_summary") or "")
    state["run_details"] = deepcopy(outcome.get("details") or {})

    failure_details = outcome.get("failure_details")
    if isinstance(failure_details, dict):
        state["failure_details"] = deepcopy(failure_details)
        stop_reason = (
            failure_details.get("checkpoint")
            or failure_details.get("stage")
            or failure_details.get("decision_state")
        )
        if stop_reason not in (None, ""):
            state["stop_reason"] = str(stop_reason)

    run_details = state.get("run_details")
    if isinstance(run_details, dict):
        analysis_review_status = run_details.get("analysis_review_status")
        if isinstance(analysis_review_status, dict):
            state["analysis_review_status"] = deepcopy(analysis_review_status)
            provenance = analysis_review_status.get("provenance")
            if isinstance(provenance, dict):
                closure_proof_by_id = provenance.get("closure_proof_by_id")
                if isinstance(closure_proof_by_id, dict):
                    state["closure_proof_by_id"] = deepcopy(closure_proof_by_id)
        recommendation_reviews = run_details.get("recommendation_reviews")
        if isinstance(recommendation_reviews, list):
            state["recommendation_reviews"] = deepcopy(recommendation_reviews)
        bounded_review_summary = run_details.get("bounded_review_summary")
        if not isinstance(bounded_review_summary, dict) and hasattr(
            runner, "_build_bounded_review_summary"
        ):
            bounded_review_summary = runner._build_bounded_review_summary(run_details)
        if isinstance(bounded_review_summary, dict):
            state["bounded_review_summary"] = deepcopy(bounded_review_summary)
            state["run_details"]["bounded_review_summary"] = deepcopy(
                bounded_review_summary
            )
        bounded_attestation_input = run_details.get("bounded_attestation_input")
        if not isinstance(bounded_attestation_input, dict) and hasattr(
            runner, "_build_bounded_attestation_input"
        ):
            bounded_attestation_input = runner._build_bounded_attestation_input(
                state["run_details"]
            )
        if isinstance(bounded_attestation_input, dict):
            state["bounded_attestation_input"] = deepcopy(bounded_attestation_input)
            state["run_details"]["bounded_attestation_input"] = deepcopy(
                bounded_attestation_input
            )
        if hasattr(runner, "_derive_final_answer_payload"):
            final_answer = runner._derive_final_answer_payload(state["run_details"])
            if isinstance(final_answer, dict) and final_answer:
                state["final_answer"] = deepcopy(final_answer)

    if state.get("config_verdict") in (None, ""):
        state["config_verdict"] = "pass"
    if state.get("policy_verdict") in (None, ""):
        state["policy_verdict"] = "pass"
    return state


def _finish_complete(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _ROOT_CONTRACT_KEY)
    runtime = state[_RUNTIME_KEY]
    root_contract = state[_ROOT_CONTRACT_KEY]
    focus_decision = state.get(_FOCUS_DECISION_KEY)
    trust_details = state.get(_TRUST_DETAILS_KEY)
    extra_details = (
        {
            "bounded_review_summary": trust_details["bounded_review_summary"],
            "bounded_attestation_input": trust_details["bounded_attestation_input"],
        }
        if isinstance(trust_details, dict)
        else None
    )

    outcome = analysis_review_runtime.build_success_outcome(
        runtime=runtime,
        contract=root_contract,
        validation_runs=list(state.get(_VALIDATION_RUNS_KEY) or []),
        final_review_payload=(
            state.get(_LATEST_REVIEW_KEY) if isinstance(state.get(_LATEST_REVIEW_KEY), dict) else {}
        ),
        final_analysis_payload=(
            state.get(_LATEST_ANALYSIS_KEY) if isinstance(state.get(_LATEST_ANALYSIS_KEY), dict) else {}
        ),
        focus_decision=focus_decision if isinstance(focus_decision, dict) else None,
        classify_validator_verdict=runner._classify_validator_verdict,
        analysis_content_verdict=runner._analysis_content_verdict,
        build_analysis_review_status=runner._build_analysis_review_status,
        analysis_final_summary=runner._analysis_final_summary,
        combine_run_verdict=runner._combine_run_verdict,
        serialized_issue_ledger=runner._serialized_issue_ledger,
        serialized_topic_ledger=runner._serialized_topic_ledger,
        recommendation_reviews=runner._recommendation_reviews,
        accepted_recommendation_reviews=runner._accepted_recommendation_reviews,
        extra_details=extra_details,
    )
    if (
        hasattr(runner, "_record_workspace_policy_check")
        and not any(
            isinstance(check, dict) and check.get("final") is True
            for check in runner.workspace_policy_checks
        )
    ):
        runner._record_workspace_policy_check(
            checkpoint="final",
            final=True,
            raise_on_violation=False,
        )
    return _finalize_graph_owned_state(_apply_outcome_to_state(state, outcome))


def _finish_terminal(state: HarnessState) -> HarnessState:
    runner = _activate_runner_contract(state, _ROOT_CONTRACT_KEY)
    outcome = state.get(_TERMINAL_OUTCOME_KEY)
    if not isinstance(outcome, dict):
        outcome = {
            "run_verdict": "harness_error",
            "content_verdict": "harness_error",
            "validator_verdict": "not_run",
            "final_summary": "Analysis-review graph exited without a terminal outcome.",
        }
    if (
        hasattr(runner, "_record_workspace_policy_check")
        and not any(
            isinstance(check, dict) and check.get("final") is True
            for check in runner.workspace_policy_checks
        )
    ):
        runner._record_workspace_policy_check(
            checkpoint="final",
            final=True,
            raise_on_violation=False,
        )
    return _finalize_graph_owned_state(_apply_outcome_to_state(state, outcome))


def _finalize_graph_owned_state(state: HarnessState) -> HarnessState:
    payload = dict(state)
    for key in (
        _RUNNER_KEY,
        _ROOT_CONTRACT_KEY,
        _REVIEW_CONTRACT_KEY,
        _RUNTIME_KEY,
        _FOCUS_DECISION_KEY,
        _TERMINAL_OUTCOME_KEY,
        _TERMINAL_ROUTE_KEY,
        _LATEST_ANALYSIS_KEY,
        _LATEST_REVIEW_KEY,
        _VALIDATION_RUNS_KEY,
        _TRUST_DETAILS_KEY,
    ):
        payload.pop(key, None)
    return payload


def _finish_route(state: HarnessState, route: str) -> HarnessState:
    if route == "finish_complete":
        return _finish_complete(state)
    if route == "finish_loop_exhausted":
        return _finish_complete(state)
    return _finish_terminal(state)


def _run_graph_owned_subgraph(state: HarnessState) -> HarnessState:
    state = _prepare_graph_owned_state(dict(state))
    route = route_execution_mode(state)
    if route == "legacy_bridge":
        return LegacyBridgeBoundary().run(state)
    if route == "focus_gate":
        state = _graph_owned_focus_gate(state)
        route = route_focus_gate_outcome(state)
        if route != "proposer":
            return _finish_route(state, route)

    state = _graph_owned_proposer(state)
    if state.get(_TERMINAL_OUTCOME_KEY):
        return _finish_terminal(state)

    state = _graph_owned_critic(state)
    route = route_critic_revision(state)
    if route == "finish_terminal":
        return _finish_terminal(state)

    while route == "reviser":
        state = _graph_owned_reviser(state)
        if state.get(_TERMINAL_OUTCOME_KEY):
            return _finish_terminal(state)

        state = _graph_owned_auditor(state)
        route = route_auditor_revision(state)
        if route == "finish_terminal":
            return _finish_terminal(state)
        if route == "finish_loop_exhausted":
            return _finish_complete(state)

    if route != "trust_attestation_gate":
        return _finish_route(state, route)

    state = _trust_attestation_gate(state)
    route = route_trust_attestation(state)
    if route == "attestation_auditor":
        state = _graph_owned_attestation_auditor(state)
        if state.get(_TERMINAL_OUTCOME_KEY):
            return _finish_terminal(state)
    return _finish_complete(state)


async def analysis_review_v1_subgraph(state: HarnessState) -> HarnessState:
    return _run_graph_owned_subgraph(state)
