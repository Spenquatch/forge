from __future__ import annotations

"""Typed shared state for the LangGraph-backed harness surface."""

import datetime as dt
import operator
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal
from typing_extensions import TypedDict

from .reporting import artifact_ref
from .selection import extract_drafts_from_summary, select_best_draft


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
    prompt_path: str | None
    schema_path: str | None
    duration_sec: float | None
    usage: dict[str, Any] | None
    warnings: list[str]
    error: str | None
    metadata: dict[str, Any]


class DraftRecord(TypedDict, total=False):
    draft_id: str
    source_stage_id: str
    role_name: str
    task_kind: str
    round_index: int
    text_path: str
    json_path: str | None
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


class HarnessState(TypedDict, total=False):
    run_id: str
    thread_id: str
    task_spec: dict[str, Any]
    strategy_spec: dict[str, Any]
    task_kind: Literal["patch", "analysis_review"]
    strategy_kind: Literal["single_pass", "pfr_v1", "analysis_review_v1"]
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

    # Execution request metadata used by the wrapper graph. These keys are not
    # part of the ADR's durable contract, but they make it possible to re-enter
    # the imperative runner without storing raw payloads in state.
    task_path: str
    strategy_path: str
    config_path: str
    auto_fit_strategy: bool


def initialize_harness_state(
    *,
    task_path: str,
    strategy_path: str,
    workspace_root: str,
    out_root: str,
    config_path: str = "config/models.yaml",
    thread_id: str | None = None,
    auto_fit_strategy: bool = True,
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
        task_path=task_path,
        strategy_path=strategy_path,
        config_path=config_path,
        auto_fit_strategy=auto_fit_strategy,
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
                json_path=(None if stage.get("output_path") in (None, "") else str(stage.get("output_path"))),
                prompt_path=(None if stage.get("prompt_path") in (None, "") else str(stage.get("prompt_path"))),
                schema_path=(None if stage.get("schema_path") in (None, "") else str(stage.get("schema_path"))),
                duration_sec=(None if stage.get("duration_sec") is None else float(stage.get("duration_sec"))),
                usage=(stage.get("usage") if isinstance(stage.get("usage"), dict) else None),
                warnings=[str(item) for item in stage.get("warnings", [])],
                error=(None if stage.get("error") in (None, "") else str(stage.get("error"))),
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
                        "prompt_path",
                        "schema_path",
                        "duration_sec",
                        "usage",
                        "warnings",
                        "error",
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


def state_from_summary(summary: dict[str, Any], *, fallback_thread_id: str | None = None) -> HarnessState:
    drafts = extract_drafts_from_summary(summary)
    best_draft = select_best_draft(drafts)
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

    verdicts = summary.get("verdicts") or {}
    task = summary.get("task") or {}

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
        stage_history=stage_records_from_summary(summary),
        drafts=drafts,
        validator_rounds=list(summary.get("validator_rounds") or []),
        policy_checks=list(summary.get("workspace_policy_checks") or []),
        issue_history=issue_history,
        warnings=[str(item) for item in summary.get("warnings", [])],
        errors=[],
        stage_counter=len(summary.get("agent_stages", [])),
        revision_round=int((summary.get("run_details") or {}).get("revisions_completed") or 0),
        current_draft_id=(drafts[-1].get("draft_id") if drafts else None),
        best_draft_id=(best_draft.get("draft_id") if best_draft else None),
        selected_draft_id=(summary.get("selected_draft_id") or (best_draft.get("draft_id") if best_draft else None)),
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
    )
    return state
