from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .contracts import AnalysisReviewContract
from .types import ProviderRun, ValidationRun

AnalysisReviewRuntime = dict[str, Any]


def new_analysis_review_runtime() -> AnalysisReviewRuntime:
    return {
        "current_analysis_payload": None,
        "current_review_payload": None,
        "latest_validator_round": [],
        "revisions_completed": 0,
        "max_loops": 0,
        "focus_refinement": None,
        "transition_reason": None,
        "review_loop_exercised": False,
    }


def runtime_snapshot(runtime: AnalysisReviewRuntime | None) -> AnalysisReviewRuntime:
    snapshot = new_analysis_review_runtime()
    if isinstance(runtime, dict):
        snapshot.update(deepcopy(runtime))
    return snapshot


def attach_runtime_details(
    outcome: dict[str, Any], runtime: AnalysisReviewRuntime
) -> dict[str, Any]:
    snapshot = runtime_snapshot(runtime)
    details = outcome.get("details")
    if isinstance(details, dict):
        details["analysis_review_runtime"] = deepcopy(snapshot)
    failure_details = outcome.get("failure_details")
    if isinstance(failure_details, dict):
        failure_details["analysis_review_runtime"] = deepcopy(snapshot)
    return outcome


def execute_focus_gate(
    *,
    runtime: AnalysisReviewRuntime,
    contract: AnalysisReviewContract,
    run_focus_gate: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    outcome = run_focus_gate(contract=contract)
    runtime["focus_refinement"] = deepcopy(outcome.get("focus_refinement"))

    kind = str(outcome.get("kind") or "").strip()
    if kind == "failed":
        runtime["transition_reason"] = "focus_gate_failed"
    elif kind == "blocked":
        runtime["transition_reason"] = "focus_gate_blocked"
    elif kind == "selected":
        runtime["transition_reason"] = "focus_gate_selected"
    return outcome


def execute_review_flow(
    *,
    runtime: AnalysisReviewRuntime,
    contract: AnalysisReviewContract,
    focus_decision: dict[str, Any] | None,
    max_loops: int,
    run_proposer_stage: Callable[..., ProviderRun],
    run_validator_round: Callable[[int], list[ValidationRun]],
    run_critic_stage: Callable[..., ProviderRun],
    run_reviser_stage: Callable[..., ProviderRun],
    run_auditor_stage: Callable[..., ProviderRun],
    ingest_review_payload: Callable[..., None],
    analysis_needs_revision: Callable[[dict[str, Any], int], bool],
    classify_validator_verdict: Callable[[list[ValidationRun]], str],
    build_stage_failure_outcome: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    runtime["max_loops"] = max_loops

    proposer_run = run_proposer_stage(
        contract=contract,
        focus_decision=focus_decision,
    )
    if not proposer_run.ok:
        runtime["transition_reason"] = "proposer_failed"
        return {
            "failure_outcome": attach_runtime_details(
                build_stage_failure_outcome(
                    stage_label="proposer",
                    run=proposer_run,
                    validator_verdict=classify_validator_verdict([]),
                    review_loop_exercised=False,
                    final_analysis=None,
                    contract=contract,
                    focus_decision=focus_decision,
                ),
                runtime,
            )
        }

    runtime["current_analysis_payload"] = deepcopy(proposer_run.structured_output or {})
    runtime["transition_reason"] = "proposer_completed"

    validation_runs = run_validator_round(0)
    runtime["latest_validator_round"] = [item.to_dict() for item in validation_runs]
    runtime["transition_reason"] = "validator_round_completed"

    critic_run = run_critic_stage(
        contract=contract,
        prior_output=proposer_run.structured_output,
        validation_runs=validation_runs,
    )
    if not critic_run.ok:
        runtime["transition_reason"] = "critic_failed"
        return {
            "failure_outcome": attach_runtime_details(
                build_stage_failure_outcome(
                    stage_label="critic",
                    run=critic_run,
                    validator_verdict=classify_validator_verdict(validation_runs),
                    review_loop_exercised=False,
                    final_analysis=proposer_run.structured_output,
                    contract=contract,
                    focus_decision=focus_decision,
                ),
                runtime,
            )
        }

    ingest_review_payload(
        critic_run.structured_output or {},
        round_index=0,
        role_name="critic",
        reviser_output=None,
    )
    runtime["current_review_payload"] = deepcopy(critic_run.structured_output or {})
    runtime["review_loop_exercised"] = True
    runtime["transition_reason"] = "critic_completed"

    latest_analysis_run = proposer_run
    latest_review_run = critic_run
    revisions_completed = 0
    runtime["revisions_completed"] = revisions_completed

    while revisions_completed < max_loops:
        if not analysis_needs_revision(
            latest_review_run.structured_output or {},
            revisions_completed,
        ):
            break

        revisions_completed += 1
        runtime["revisions_completed"] = revisions_completed
        prior_analysis_payload = latest_analysis_run.structured_output

        next_analysis_run = run_reviser_stage(
            contract=contract,
            focus_decision=focus_decision,
            latest_analysis_payload=latest_analysis_run.structured_output,
            latest_review_payload=latest_review_run.structured_output,
            validation_runs=validation_runs,
            revision_round=revisions_completed,
        )
        if not next_analysis_run.ok:
            runtime["transition_reason"] = "reviser_failed"
            return {
                "failure_outcome": attach_runtime_details(
                    build_stage_failure_outcome(
                        stage_label=f"reviser round {revisions_completed}",
                        run=next_analysis_run,
                        validator_verdict=classify_validator_verdict(validation_runs),
                        review_loop_exercised=True,
                        final_analysis=prior_analysis_payload,
                        contract=contract,
                        focus_decision=focus_decision,
                    ),
                    runtime,
                )
            }

        latest_analysis_run = next_analysis_run
        runtime["current_analysis_payload"] = deepcopy(
            latest_analysis_run.structured_output or {}
        )
        runtime["transition_reason"] = "reviser_completed"

        latest_review_run = run_auditor_stage(
            contract=contract,
            prior_output=latest_analysis_run.structured_output,
            validation_runs=validation_runs,
            round_index=revisions_completed,
            reviser_output=latest_analysis_run.structured_output,
        )
        if not latest_review_run.ok:
            runtime["transition_reason"] = "auditor_failed"
            return {
                "failure_outcome": attach_runtime_details(
                    build_stage_failure_outcome(
                        stage_label="auditor",
                        run=latest_review_run,
                        validator_verdict=classify_validator_verdict(validation_runs),
                        review_loop_exercised=True,
                        final_analysis=latest_analysis_run.structured_output,
                        contract=contract,
                        focus_decision=focus_decision,
                    ),
                    runtime,
                )
            }

        ingest_review_payload(
            latest_review_run.structured_output or {},
            round_index=revisions_completed,
            role_name="auditor",
            reviser_output=latest_analysis_run.structured_output,
        )
        runtime["current_review_payload"] = deepcopy(
            latest_review_run.structured_output or {}
        )
        runtime["review_loop_exercised"] = True
        runtime["transition_reason"] = "auditor_completed"

    if analysis_needs_revision(
        latest_review_run.structured_output or {}, revisions_completed
    ):
        runtime["transition_reason"] = "max_loops_exhausted"
    else:
        runtime["transition_reason"] = "stop_policy_satisfied"

    return {
        "validation_runs": validation_runs,
        "revisions_completed": revisions_completed,
        "max_loops": max_loops,
        "final_review_payload": latest_review_run.structured_output or {},
        "final_analysis_payload": latest_analysis_run.structured_output or {},
    }


def execute_trust_attestation(
    *,
    runtime: AnalysisReviewRuntime,
    contract: AnalysisReviewContract,
    focus_decision: dict[str, Any] | None,
    revisions_completed: int,
    validation_runs: list[ValidationRun],
    final_analysis_payload: dict[str, Any],
    bounded_attestation_input: dict[str, Any],
    run_trust_attestation_stage: Callable[..., ProviderRun],
    ingest_review_payload: Callable[..., None],
    classify_validator_verdict: Callable[[list[ValidationRun]], str],
    build_stage_failure_outcome: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    attestation_run = run_trust_attestation_stage(
        contract=contract,
        bounded_attestation_input=bounded_attestation_input,
        validation_runs=validation_runs,
        final_analysis_payload=final_analysis_payload,
    )
    if not attestation_run.ok:
        runtime["transition_reason"] = "trust_attestation_failed"
        return {
            "failure_outcome": attach_runtime_details(
                build_stage_failure_outcome(
                    stage_label="trust attestation review",
                    run=attestation_run,
                    validator_verdict=classify_validator_verdict(validation_runs),
                    review_loop_exercised=True,
                    final_analysis=final_analysis_payload,
                    contract=contract,
                    focus_decision=focus_decision,
                ),
                runtime,
            )
        }

    ingest_review_payload(
        attestation_run.structured_output or {},
        round_index=revisions_completed + 1,
        role_name="auditor",
        reviser_output=None,
    )
    runtime["current_review_payload"] = deepcopy(attestation_run.structured_output or {})
    runtime["review_loop_exercised"] = True
    runtime["transition_reason"] = "trust_attestation_completed"
    return {"attestation_run": attestation_run}


def build_success_outcome(
    *,
    runtime: AnalysisReviewRuntime,
    contract: AnalysisReviewContract,
    validation_runs: list[ValidationRun],
    final_review_payload: dict[str, Any],
    final_analysis_payload: dict[str, Any],
    focus_decision: dict[str, Any] | None,
    classify_validator_verdict: Callable[[list[ValidationRun]], str],
    analysis_content_verdict: Callable[..., str],
    build_analysis_review_status: Callable[..., dict[str, Any]],
    analysis_final_summary: Callable[..., str],
    combine_run_verdict: Callable[[str, str], str],
    serialized_issue_ledger: Callable[[], list[dict[str, Any]]],
    serialized_topic_ledger: Callable[[], list[dict[str, Any]]],
    recommendation_reviews: Callable[[dict[str, Any]], list[dict[str, Any]]],
    accepted_recommendation_reviews: Callable[[dict[str, Any]], list[dict[str, Any]]],
    extra_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    revisions_completed = int(runtime.get("revisions_completed") or 0)
    max_loops = int(runtime.get("max_loops") or 0)
    validator_verdict = classify_validator_verdict(validation_runs)
    content_verdict = analysis_content_verdict(
        final_review_payload,
        final_analysis_payload=final_analysis_payload,
        revisions_completed=revisions_completed,
        max_loops=max_loops,
    )
    analysis_review_status = build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict=content_verdict,
    )
    final_summary = analysis_final_summary(
        final_review_payload,
        final_analysis_payload=final_analysis_payload,
        content_verdict=content_verdict,
        revisions_completed=revisions_completed,
        max_loops=max_loops,
        validator_verdict=validator_verdict,
    )
    details = {
        "revisions_completed": revisions_completed,
        "review_policy": contract.stop_policy.to_dict(),
        "analysis_review_contract": contract.to_dict(),
        "final_review": final_review_payload,
        "final_analysis": final_analysis_payload,
        "issue_ledger": serialized_issue_ledger(),
        "topic_ledger": serialized_topic_ledger(),
        "recommendation_reviews": recommendation_reviews(final_review_payload),
        "accepted_recommendation_count": len(
            accepted_recommendation_reviews(final_review_payload)
        ),
        "analysis_review_status": analysis_review_status,
        "focus_decision": focus_decision,
        "focus_refinement": deepcopy(runtime.get("focus_refinement")),
        "review_loop_exercised": bool(runtime.get("review_loop_exercised")),
        "analysis_review_runtime": runtime_snapshot(runtime),
    }
    if isinstance(extra_details, dict):
        details.update(extra_details)
    return {
        "run_verdict": combine_run_verdict(content_verdict, validator_verdict),
        "content_verdict": content_verdict,
        "validator_verdict": validator_verdict,
        "final_summary": final_summary,
        "details": details,
    }
