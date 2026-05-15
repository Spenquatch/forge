from __future__ import annotations

"""Typed shared state for the LangGraph-backed harness surface."""

import datetime as dt
import operator
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

from .reporting import artifact_ref
from .selection import drafts_from_stage_history_v1, select_best_draft

HARNESS_STATE_SERIALIZATION_VERSION = "harness_state_v1"
SUMMARY_BOUNDARY_VERSION = "summary_projection_v1"
LEGACY_BRIDGE_BOUNDARY_VERSION = "legacy_bridge_boundary_v1"


class ArtifactRef(TypedDict, total=False):
    kind: str
    path: str
    description: str


class StageRecord(TypedDict, total=False):
    stage_id: str
    role_name: str
    provider_name: str
    model: str | None
    requested_access: str
    effective_access: str
    stage_index: int
    round_index: int
    ok: bool
    verdict: str | None
    text_path: str | None
    json_path: str | None
    raw_json_path: str | None
    normalized_json_path: str | None
    prompt_path: str | None
    schema_path: str | None
    duration_sec: float | None
    usage: dict[str, Any] | None
    warnings: list[str]
    error: str | None
    structured_output: dict[str, Any] | None
    failure_kind: str | None
    failure_summary: str | None
    semantic_validation_payload_provenance: dict[str, Any] | None
    metadata: dict[str, Any]


class DraftRecord(TypedDict, total=False):
    draft_id: str
    source_stage_id: str
    role_name: str
    task_kind: str
    round_index: int
    text_path: str
    json_path: str | None
    raw_json_path: str | None
    normalized_json_path: str | None
    summary: str
    review_status: Literal["candidate", "accepted", "accepted_partial", "rejected", "best"]
    scores: dict[str, float]
    issue_counts: dict[str, int]
    metadata: dict[str, Any]


class IssueRecord(TypedDict, total=False):
    issue_id: str
    source_stage_id: str
    first_seen_round: int
    last_seen_round: int
    severity: Literal["low", "medium", "high", "critical"]
    kind: str
    blocking_class: str
    recommendation_index: int | None
    title: str
    evidence: str
    repair_hint: str
    why_not_raised_earlier: str | None
    resolution_status: Literal["open", "resolved", "carried_forward", "waived"]
    resolution_note: str


class ValidatorResult(TypedDict, total=False):
    name: str
    status: Literal["passed", "failed", "error", "skipped", "not_applicable"]
    required: bool
    run_when: str
    reason: str | None
    command: str
    exit_code: int | None
    log_path: str | None
    duration_sec: float | None


class ValidatorRound(TypedDict, total=False):
    round_index: int
    results: list[ValidatorResult]


class PolicyCheck(TypedDict, total=False):
    checkpoint: str
    final: bool
    ok: bool
    mode: str
    touched_files: list[str]
    violations: list[str]
    git_snapshot_path: str | None


class ReviewScores(TypedDict, total=False):
    grounding_score: float
    actionability_score: float
    scope_compliance_score: float


class AnalysisReviewRuntimeState(TypedDict, total=False):
    current_analysis_payload: dict[str, Any] | None
    current_review_payload: dict[str, Any] | None
    latest_validator_round: list[dict[str, Any]]
    revisions_completed: int
    max_loops: int
    focus_refinement: dict[str, Any] | None
    transition_reason: str | None
    review_loop_exercised: bool


def _normalized_draft_id(raw_value: Any) -> str:
    return str(raw_value or "").strip()


def _draft_by_id(
    drafts: list[dict[str, Any]],
    draft_id: str | None,
) -> dict[str, Any] | None:
    normalized_id = _normalized_draft_id(draft_id)
    if not normalized_id:
        return None
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        if _normalized_draft_id(draft.get("draft_id")) == normalized_id:
            return draft
    return None


class HarnessState(TypedDict, total=False):
    run_id: str
    thread_id: str
    task_spec: dict[str, Any]
    strategy_spec: dict[str, Any]
    task_kind: Literal["patch", "analysis_review"]
    strategy_kind: Literal[
        "single_pass",
        "pfr_v1",
        "analysis_review_bounded_v1",
        "analysis_review_trust_v1",
        "analysis_review_v1",
    ]
    workspace_root: str
    out_root: str
    run_dir: str
    created_at: str

    initial_git_snapshot: dict[str, Any]
    initial_workspace_state: dict[str, Any] | None
    current_git_snapshot: dict[str, Any]
    current_workspace_state: dict[str, Any] | None

    stage_history: Annotated[list[StageRecord], operator.add]
    drafts: Annotated[list[DraftRecord], operator.add]
    validator_rounds: Annotated[list[ValidatorRound], operator.add]
    policy_checks: Annotated[list[PolicyCheck], operator.add]
    issue_history: Annotated[list[IssueRecord], operator.add]
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

    stage_counter: int
    revision_round: int
    current_draft_id: str | None
    best_draft_id: str | None
    selected_draft_id: str | None
    open_issue_ids: list[str]
    latest_review_scores: ReviewScores
    stop_reason: str | None

    content_verdict: str | None
    validator_verdict: str | None
    policy_verdict: str | None
    config_verdict: str | None
    run_verdict: str | None
    summary_text: str | None

    artifact_index: dict[str, ArtifactRef]
    summary_payload: dict[str, Any]
    analysis_review_status: dict[str, Any]
    recommendation_reviews: list[dict[str, Any]]
    final_answer: dict[str, Any] | None
    bounded_review_summary: dict[str, Any] | None
    bounded_attestation_input: dict[str, Any] | None
    changed_files: list[str]
    validator_summary: dict[str, Any]
    analysis_review_coverage: dict[str, Any]
    run_details: dict[str, Any]
    failure_details: dict[str, Any]
    closure_proof_by_id: dict[str, Any]
    workspace_policy_ignored_rel_paths: list[str]
    final_workspace_policy_evaluation: dict[str, Any]
    serialization_version: str
    analysis_review_contract: dict[str, Any]
    analysis_review_runtime: AnalysisReviewRuntimeState
    strategy_graph_spec: dict[str, Any]
    strategy_graph_spec_id: str | None
    strategy_graph_subset: str | None
    focus_decision: dict[str, Any]
    topic_ledger: list[dict[str, Any]]
    summary_boundary_version: str
    bridge_boundary_version: str | None

    # Execution request metadata used by the wrapper graph. These keys are not
    # part of the ADR's durable contract, but they make it possible to re-enter
    # the imperative runner without storing raw payloads in state.
    task_path: str
    strategy_path: str
    config_path: str
    auto_fit_strategy: bool
    analysis_review_execution_mode: Literal["legacy_bridge", "graph_owned"]


def initialize_harness_state(
    *,
    task_path: str,
    strategy_path: str,
    workspace_root: str,
    out_root: str,
    config_path: str = "config/models.yaml",
    thread_id: str | None = None,
    auto_fit_strategy: bool = True,
    analysis_review_execution_mode: Literal["legacy_bridge", "graph_owned"] = "legacy_bridge",
) -> HarnessState:
    now = dt.datetime.now(dt.UTC)
    return HarnessState(
        run_id="",
        thread_id=thread_id or str(uuid.uuid4()),
        task_spec={},
        strategy_spec={},
        workspace_root=workspace_root,
        out_root=out_root,
        run_dir="",
        created_at=now.isoformat(),
        initial_git_snapshot={},
        initial_workspace_state=None,
        current_git_snapshot={},
        current_workspace_state=None,
        stage_history=[],
        drafts=[],
        validator_rounds=[],
        policy_checks=[],
        issue_history=[],
        warnings=[],
        errors=[],
        stage_counter=0,
        revision_round=0,
        current_draft_id=None,
        best_draft_id=None,
        selected_draft_id=None,
        open_issue_ids=[],
        latest_review_scores={},
        stop_reason=None,
        content_verdict=None,
        validator_verdict=None,
        policy_verdict=None,
        config_verdict="pass",
        run_verdict=None,
        summary_text=None,
        artifact_index={},
        summary_payload={},
        analysis_review_status={},
        recommendation_reviews=[],
        final_answer=None,
        bounded_review_summary=None,
        bounded_attestation_input=None,
        changed_files=[],
        validator_summary={},
        analysis_review_coverage={},
        run_details={},
        failure_details={},
        closure_proof_by_id={},
        workspace_policy_ignored_rel_paths=[],
        final_workspace_policy_evaluation={},
        serialization_version=HARNESS_STATE_SERIALIZATION_VERSION,
        analysis_review_contract={},
        strategy_graph_spec={},
        strategy_graph_spec_id=None,
        strategy_graph_subset=None,
        focus_decision={},
        topic_ledger=[],
        summary_boundary_version=SUMMARY_BOUNDARY_VERSION,
        bridge_boundary_version=None,
        task_path=task_path,
        strategy_path=strategy_path,
        config_path=config_path,
        auto_fit_strategy=auto_fit_strategy,
        analysis_review_execution_mode=analysis_review_execution_mode,
        analysis_review_runtime={},
    )


def stage_records_from_summary(summary: dict[str, Any]) -> list[StageRecord]:
    records: list[StageRecord] = []
    for fallback_index, stage in enumerate(summary.get("agent_stages", []), start=1):
        if not isinstance(stage, dict):
            continue
        role_name = str(stage.get("role_name") or "stage")
        stage_index = int(stage.get("stage_index", fallback_index))
        records.append(
            StageRecord(
                stage_id=f"stage-{stage_index:02d}-{role_name.replace(' ', '-')}",
                role_name=role_name,
                provider_name=str(stage.get("provider") or stage.get("provider_name") or ""),
                model=(None if stage.get("model") in (None, "") else str(stage.get("model"))),
                requested_access=str(stage.get("requested_access") or stage.get("access") or "read"),
                effective_access=str(stage.get("effective_access") or stage.get("access") or "read"),
                stage_index=stage_index,
                round_index=int(stage.get("round_index") or 0),
                ok=bool(stage.get("ok")),
                verdict=(None if stage.get("verdict") in (None, "") else str(stage.get("verdict"))),
                text_path=(None if stage.get("stdout_path") in (None, "") else str(stage.get("stdout_path"))),
                json_path=(
                    None
                    if stage.get("output_path") in (None, "")
                    else str(stage.get("output_path"))
                ),
                raw_json_path=(
                    None
                    if stage.get("raw_output_path") in (None, "")
                    else str(stage.get("raw_output_path"))
                ),
                normalized_json_path=(
                    None
                    if stage.get("normalized_output_path") in (None, "")
                    else str(stage.get("normalized_output_path"))
                ),
                prompt_path=(None if stage.get("prompt_path") in (None, "") else str(stage.get("prompt_path"))),
                schema_path=(None if stage.get("schema_path") in (None, "") else str(stage.get("schema_path"))),
                duration_sec=(None if stage.get("duration_sec") is None else float(stage.get("duration_sec"))),
                usage=(stage.get("usage") if isinstance(stage.get("usage"), dict) else None),
                warnings=[str(item) for item in stage.get("warnings", [])],
                error=(None if stage.get("error") in (None, "") else str(stage.get("error"))),
                structured_output=(
                    stage.get("structured_output")
                    if isinstance(stage.get("structured_output"), dict)
                    else None
                ),
                failure_kind=(
                    None
                    if stage.get("failure_kind") in (None, "")
                    else str(stage.get("failure_kind"))
                ),
                failure_summary=(
                    None
                    if stage.get("failure_summary") in (None, "")
                    else str(stage.get("failure_summary"))
                ),
                semantic_validation_payload_provenance=(
                    stage.get("semantic_validation_payload_provenance")
                    if isinstance(stage.get("semantic_validation_payload_provenance"), dict)
                    else None
                ),
                metadata={
                    key: value
                    for key, value in stage.items()
                    if key
                    not in {
                        "provider",
                        "provider_name",
                        "model",
                        "requested_access",
                        "effective_access",
                        "stage_index",
                        "round_index",
                        "ok",
                        "verdict",
                        "stdout_path",
                        "output_path",
                        "raw_output_path",
                        "normalized_output_path",
                        "prompt_path",
                        "schema_path",
                        "duration_sec",
                        "usage",
                        "warnings",
                        "error",
                        "structured_output",
                        "failure_kind",
                        "failure_summary",
                        "semantic_validation_payload_provenance",
                    }
                },
            )
        )
    return records


def _issue_history_from_summary(summary: dict[str, Any], drafts: list[dict[str, Any]]) -> list[IssueRecord]:
    ledger = summary.get("issue_ledger")
    if isinstance(ledger, list) and ledger:
        issues: list[IssueRecord] = []
        for item in ledger:
            if not isinstance(item, dict):
                continue
            issues.append(IssueRecord(**item))
        return issues

    issues = []
    for draft in drafts:
        metadata = draft.get("metadata") or {}
        review_payload = metadata.get("review_payload")
        if not isinstance(review_payload, dict):
            continue
        for issue_index, issue in enumerate(review_payload.get("issues", []), start=1):
            if not isinstance(issue, dict):
                continue
            issues.append(
                IssueRecord(
                    issue_id=str(issue.get("issue_id") or f"{draft.get('draft_id', 'draft')}-issue-{issue_index}"),
                    source_stage_id=str(metadata.get("review_stage_id") or draft.get("source_stage_id") or ""),
                    first_seen_round=int(draft.get("round_index") or 0),
                    last_seen_round=int(draft.get("round_index") or 0),
                    severity=str(issue.get("severity") or "low"),
                    kind=str(issue.get("kind") or "other"),
                    blocking_class=str(issue.get("blocking_class") or "presentation"),
                    recommendation_index=(
                        None
                        if issue.get("recommendation_index") in (None, "")
                        else int(issue.get("recommendation_index"))
                    ),
                    title=str(issue.get("title") or "Issue"),
                    evidence=str(issue.get("evidence") or ""),
                    repair_hint=str(issue.get("repair_hint") or ""),
                    why_not_raised_earlier=(
                        None
                        if issue.get("why_not_raised_earlier") in (None, "")
                        else str(issue.get("why_not_raised_earlier"))
                    ),
                    resolution_status="open",
                    resolution_note="",
                )
            )
    return issues


def _summary_dict(summary: dict[str, Any], key: str) -> dict[str, Any]:
    value = summary.get(key)
    if isinstance(value, dict):
        return dict(value)
    run_details = summary.get("run_details")
    if isinstance(run_details, dict):
        nested_value = run_details.get(key)
        if isinstance(nested_value, dict):
            return dict(nested_value)
    return {}


def _summary_optional_dict(summary: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = _summary_dict(summary, key)
    return value or None


def _summary_list_of_dicts(summary: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = summary.get(key)
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    run_details = summary.get("run_details")
    if isinstance(run_details, dict):
        nested_value = run_details.get(key)
        if isinstance(nested_value, list):
            return [dict(item) for item in nested_value if isinstance(item, dict)]
    return []


def summary_read_adapter_v1(
    summary: dict[str, Any], *, fallback_thread_id: str | None = None
) -> HarnessState:
    task = summary.get("task") or {}
    verdicts = summary.get("verdicts") or {}
    stage_history = stage_records_from_summary(summary)
    drafts = drafts_from_stage_history_v1(
        stage_history,
        task_kind=str(task.get("task_kind") or "patch"),
        validator_rounds=list(summary.get("validator_rounds") or []),
        content_verdict=(
            None
            if verdicts.get("content_verdict") in (None, "")
            else str(verdicts.get("content_verdict"))
        ),
    )
    best_draft_id = _normalized_draft_id(summary.get("best_draft_id"))
    selected_draft_id = _normalized_draft_id(summary.get("selected_draft_id"))
    best_draft = _draft_by_id(drafts, best_draft_id)
    if best_draft is None and not best_draft_id:
        ranked_best_draft = select_best_draft(drafts)
        if ranked_best_draft is not None:
            best_draft = ranked_best_draft
            best_draft_id = _normalized_draft_id(ranked_best_draft.get("draft_id"))
    if not selected_draft_id:
        selected_draft_id = best_draft_id
    issue_history = _issue_history_from_summary(summary, drafts)

    artifacts = summary.get("artifacts") or {}
    artifact_index: dict[str, ArtifactRef] = {}
    for key, value in artifacts.items():
        if not value:
            continue
        artifact_index[str(key)] = artifact_ref(
            value,
            kind=str(key),
            description=str(key).replace("_", " "),
        )

    latest_review_scores: ReviewScores = {}
    if best_draft is not None:
        best_scores = best_draft.get("scores") or {}
        for field_name in (
            "grounding_score",
            "actionability_score",
            "scope_compliance_score",
        ):
            if field_name in best_scores:
                latest_review_scores[field_name] = float(best_scores[field_name])

    analysis_review_status = _summary_dict(summary, "analysis_review_status")
    analysis_review_provenance = analysis_review_status.get("provenance")

    state = HarnessState(
        run_id=str(summary.get("run_id") or ""),
        thread_id=str(summary.get("thread_id") or fallback_thread_id or uuid.uuid4()),
        task_spec=dict(task),
        strategy_spec={
            "name": summary.get("strategy_name"),
            "kind": summary.get("strategy_kind"),
        },
        task_kind=str(task.get("task_kind") or "patch"),
        strategy_kind=str(summary.get("strategy_kind") or "single_pass"),
        workspace_root=str(summary.get("workspace") or ""),
        out_root=str(Path(str(artifacts.get("run_dir") or ".")).parent),
        run_dir=str(artifacts.get("run_dir") or ""),
        created_at=str(summary.get("created_at") or dt.datetime.now(dt.UTC).isoformat()),
        initial_git_snapshot=dict(summary.get("initial_git_snapshot") or {}),
        initial_workspace_state=None,
        current_git_snapshot=dict(summary.get("final_git_snapshot") or {}),
        current_workspace_state=None,
        stage_history=stage_history,
        drafts=drafts,
        validator_rounds=list(summary.get("validator_rounds") or []),
        policy_checks=list(summary.get("workspace_policy_checks") or []),
        issue_history=issue_history,
        warnings=[str(item) for item in summary.get("warnings", [])],
        errors=[],
        stage_counter=len(summary.get("agent_stages", [])),
        revision_round=int((summary.get("run_details") or {}).get("revisions_completed") or 0),
        current_draft_id=(drafts[-1].get("draft_id") if drafts else None),
        best_draft_id=(best_draft_id or None),
        selected_draft_id=(selected_draft_id or None),
        open_issue_ids=[
            issue.get("issue_id", "")
            for issue in issue_history
            if str(issue.get("resolution_status") or "") in {"open", "carried_forward"}
        ],
        latest_review_scores=latest_review_scores,
        stop_reason=(summary.get("failure_details") or {}).get("checkpoint") if isinstance(summary.get("failure_details"), dict) else None,
        content_verdict=(None if verdicts.get("content_verdict") in (None, "") else str(verdicts.get("content_verdict"))),
        validator_verdict=(None if verdicts.get("validator_verdict") in (None, "") else str(verdicts.get("validator_verdict"))),
        policy_verdict=(None if verdicts.get("policy_verdict") in (None, "") else str(verdicts.get("policy_verdict"))),
        config_verdict=(None if verdicts.get("config_verdict") in (None, "") else str(verdicts.get("config_verdict"))),
        run_verdict=(None if verdicts.get("run_verdict") in (None, "") else str(verdicts.get("run_verdict"))),
        summary_text=(None if summary.get("final_summary") in (None, "") else str(summary.get("final_summary"))),
        artifact_index=artifact_index,
        summary_payload=dict(summary),
        analysis_review_status=analysis_review_status,
        recommendation_reviews=_summary_list_of_dicts(summary, "recommendation_reviews"),
        final_answer=_summary_optional_dict(summary, "final_answer"),
        bounded_review_summary=_summary_optional_dict(summary, "bounded_review_summary"),
        bounded_attestation_input=_summary_optional_dict(summary, "bounded_attestation_input"),
        changed_files=[str(item) for item in summary.get("changed_files", []) or []],
        validator_summary=_summary_dict(summary, "validator_summary"),
        analysis_review_coverage=_summary_dict(summary, "analysis_review_coverage"),
        run_details=(
            dict(summary.get("run_details"))
            if isinstance(summary.get("run_details"), dict)
            else {}
        ),
        failure_details=(
            dict(summary.get("failure_details"))
            if isinstance(summary.get("failure_details"), dict)
            else {}
        ),
        closure_proof_by_id=(
            dict(analysis_review_provenance.get("closure_proof_by_id", {}))
            if isinstance(analysis_review_provenance, dict)
            else {}
        ),
        workspace_policy_ignored_rel_paths=[
            str(item)
            for item in summary.get("workspace_policy_ignored_rel_paths", []) or []
        ],
        final_workspace_policy_evaluation=_summary_dict(
            summary, "final_workspace_policy_evaluation"
        ),
        serialization_version=str(
            summary.get("serialization_version") or HARNESS_STATE_SERIALIZATION_VERSION
        ),
        analysis_review_contract=_summary_dict(summary, "analysis_review_contract"),
        analysis_review_runtime=_summary_dict(summary, "analysis_review_runtime"),
        strategy_graph_spec=_summary_dict(summary, "strategy_graph_spec"),
        strategy_graph_spec_id=(
            None
            if summary.get("strategy_graph_spec_id") in (None, "")
            else str(summary.get("strategy_graph_spec_id"))
        ),
        strategy_graph_subset=(
            None
            if summary.get("strategy_graph_subset") in (None, "")
            else str(summary.get("strategy_graph_subset"))
        ),
        focus_decision=_summary_dict(summary, "focus_decision"),
        topic_ledger=_summary_list_of_dicts(summary, "topic_ledger"),
        summary_boundary_version=str(
            summary.get("summary_boundary_version") or SUMMARY_BOUNDARY_VERSION
        ),
        bridge_boundary_version=(
            None
            if summary.get("bridge_boundary_version") in (None, "")
            else str(summary.get("bridge_boundary_version"))
        ),
    )
    return state


def state_from_summary(
    summary: dict[str, Any], *, fallback_thread_id: str | None = None
) -> HarnessState:
    return summary_read_adapter_v1(
        summary, fallback_thread_id=fallback_thread_id
    )
