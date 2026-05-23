# mypy: disable-error-code="union-attr,index,arg-type,return-value,no-redef,operator"

from __future__ import annotations

"""Artifact and reporting helpers for the LangGraph-backed harness surface."""

import copy
import json
from pathlib import Path
from typing import Any

from .artifacts import artifact_description
from .files import write_json, write_text
from .providers import _soft_validate_schema
from .publication_authority import (
    partial_acceptance_summary_suffix,
    sanitize_artifact_payload,
    sanitize_summary_text,
)
from .report import render_report
from .schemas import PLANNING_ARTIFACT_SCHEMA_VERSION, plan_json_schema
from .selection import select_best_draft
from .topic_lifecycle import (
    partial_accept_topic_eligibility,
    topic_ids_for_status_name,
    topic_status_field_name,
)
from .validation import validate_planning_success_artifacts

_FULLY_ACCEPTED_RUN_VERDICTS = {"accepted", "accepted_with_warnings"}
_PARTIAL_ACCEPTED_RUN_VERDICTS = {"accepted_partial"}
_CANONICAL_ADMISSIBILITY_REASONS = {
    "accepted_with_caveat",
    "inferred_grounding",
    "not_accepted",
    "topic_blocked",
}
_FINAL_ANSWER_INCLUDES_WITHHELD_PREFIX = "final answer payload includes recommendation indices withheld from FINAL_ANSWER.*: "
_FINAL_ANSWER_OMITS_REQUIRED_PREFIX = (
    "final answer payload omits recommendation indices required for FINAL_ANSWER.*: "
)
HARNESS_STATE_SERIALIZATION_VERSION = "harness_state_v1"
SUMMARY_BOUNDARY_VERSION = "summary_projection_v1"
PLANNING_RUNTIME_TARGET = "planning_v1"
PLANNING_RUN_MODES = (
    "fixture-backed",
    "deterministic-live",
    "provider-reviewed",
)
PLANNING_TERMINAL_STATUSES = {
    "success",
    "clarification_needed",
    "failed",
}


def artifact_ref(path: str | Path, *, kind: str, description: str) -> dict[str, str]:
    return {
        "kind": kind,
        "path": str(path),
        "description": description,
    }


def ensure_run_dir(run_dir: str | Path) -> Path:
    path = Path(run_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _planning_runtime_target(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
) -> str:
    strategy_graph_spec = state.get("strategy_graph_spec")
    if isinstance(strategy_graph_spec, dict):
        runtime_target = str(strategy_graph_spec.get("runtime_target") or "").strip()
        if runtime_target:
            return runtime_target
    seeded_strategy_graph_spec = seeded_summary.get("strategy_graph_spec")
    if isinstance(seeded_strategy_graph_spec, dict):
        runtime_target = str(
            seeded_strategy_graph_spec.get("runtime_target") or ""
        ).strip()
        if runtime_target:
            return runtime_target
    strategy = seeded_summary.get("strategy")
    if isinstance(strategy, dict):
        runtime_target = str(strategy.get("runtime_target") or "").strip()
        if runtime_target:
            return runtime_target
    return ""


def _is_planning_runtime_state(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
) -> bool:
    return _planning_runtime_target(state, seeded_summary=seeded_summary) == (
        PLANNING_RUNTIME_TARGET
    )


def _string_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_present_string(item: Any, *keys: str) -> str:
    if not isinstance(item, dict):
        return _string_or_empty(item)
    for key in keys:
        value = _string_or_empty(item.get(key))
        if value:
            return value
    return ""


def _normalized_string_list(raw_items: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items or []:
        if isinstance(item, dict):
            value = _first_present_string(
                item,
                "question",
                "prompt",
                "summary",
                "title",
                "label",
                "id",
            )
        else:
            value = _string_or_empty(item)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _iter_planning_records(raw_items: Any, *, id_field: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                records.append(copy.deepcopy(item))
            else:
                value = _string_or_empty(item)
                if value:
                    records.append({id_field: value, "summary": value})
        return records
    if isinstance(raw_items, dict):
        for record_id, item in raw_items.items():
            if isinstance(item, dict):
                record = copy.deepcopy(item)
                if not _string_or_empty(record.get(id_field)):
                    record[id_field] = str(record_id)
                records.append(record)
                continue
            value = _string_or_empty(item)
            if value:
                records.append({id_field: str(record_id), "summary": value})
    return records


def _normalize_planning_phase_results(
    raw_phase_results: Any,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in _iter_planning_records(raw_phase_results, id_field="phase_id"):
        phase_id = _first_present_string(item, "phase_id", "id", "phase")
        if not phase_id:
            continue
        phase_result = {
            "phase_id": phase_id,
            "status": _first_present_string(
                item,
                "status",
                "outcome",
                "verdict",
                "result",
            )
            or "done",
            "summary": _first_present_string(
                item,
                "summary",
                "result_summary",
                "notes",
                "description",
            )
            or phase_id,
        }
        primary_cut_summary = _first_present_string(item, "primary_cut_summary")
        if primary_cut_summary:
            phase_result["primary_cut_summary"] = primary_cut_summary
        normalized.append(phase_result)
    return normalized


def _normalize_rubric_results(
    raw_phase_results: Any,
    *,
    seeded_summary: dict[str, Any],
) -> list[str]:
    seeded_results = _normalized_string_list(seeded_summary.get("rubric_results"))
    if seeded_results:
        return seeded_results
    for item in _iter_planning_records(raw_phase_results, id_field="phase_id"):
        phase_id = _first_present_string(item, "phase_id", "id", "phase")
        if phase_id != "rubric_design_doc":
            continue
        for key in ("rubric_results", "criteria", "items", "bullets"):
            results = _normalized_string_list(item.get(key))
            if results:
                return results
        summary = _first_present_string(
            item,
            "summary",
            "result_summary",
            "notes",
            "description",
        )
        if summary:
            return [summary]
    return []


def _normalize_planning_seams(
    raw_items: Any,
    *,
    fallback_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in _iter_planning_records(raw_items, id_field="seam_id"):
        seam_id = _first_present_string(item, "seam_id", "id")
        if not seam_id:
            continue
        paths = _normalized_string_list(
            item.get("paths")
            or item.get("files")
            or item.get("candidate_paths")
            or item.get("repo_evidence_refs")
            or item.get("evidence_refs")
        )
        if not paths and fallback_paths:
            paths = list(fallback_paths)
        normalized.append(
            {
                "seam_id": seam_id,
                "summary": _first_present_string(
                    item,
                    "summary",
                    "title",
                    "name",
                    "description",
                )
                or seam_id,
                "paths": paths,
                "repo_evidence_refs": _normalized_string_list(
                    item.get("repo_evidence_refs") or item.get("evidence_refs")
                ),
                "dependency_reasoning": _normalized_string_list(
                    item.get("dependency_reasoning")
                ),
                "ambiguity_flags": _normalized_string_list(item.get("ambiguity_flags")),
                "source_phase_id": _first_present_string(item, "source_phase_id"),
            }
        )
    return normalized


def _normalize_planning_workstreams(raw_items: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in _iter_planning_records(raw_items, id_field="workstream_id"):
        workstream_id = _first_present_string(item, "workstream_id", "id")
        if not workstream_id:
            continue
        normalized.append(
            {
                "workstream_id": workstream_id,
                "summary": _first_present_string(
                    item,
                    "summary",
                    "title",
                    "name",
                    "description",
                )
                or workstream_id,
                "seam_ids": _normalized_string_list(
                    item.get("seam_ids") or item.get("seams")
                ),
                "worktree_recommended": bool(
                    item.get("worktree_recommended")
                    or item.get("worktree")
                    or item.get("worktree_path")
                ),
                "repo_evidence_refs": _normalized_string_list(
                    item.get("repo_evidence_refs") or item.get("evidence_refs")
                ),
                "dependency_reasoning": _normalized_string_list(
                    item.get("dependency_reasoning")
                ),
                "ambiguity_flags": _normalized_string_list(item.get("ambiguity_flags")),
                "source_phase_id": _first_present_string(item, "source_phase_id"),
            }
        )
    return normalized


def _normalize_planning_slices(raw_items: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in _iter_planning_records(raw_items, id_field="slice_id"):
        slice_id = _first_present_string(item, "slice_id", "id")
        if not slice_id:
            continue
        normalized.append(
            {
                "slice_id": slice_id,
                "summary": _first_present_string(
                    item,
                    "summary",
                    "title",
                    "name",
                    "description",
                )
                or slice_id,
                "workstream_id": _first_present_string(
                    item,
                    "workstream_id",
                    "workstream",
                ),
                "seam_ids": _normalized_string_list(
                    item.get("seam_ids") or item.get("seams")
                ),
                "acceptance_criteria": _normalized_string_list(
                    item.get("acceptance_criteria")
                    or item.get("tests")
                    or item.get("deliverables")
                ),
                "repo_evidence_refs": _normalized_string_list(
                    item.get("repo_evidence_refs") or item.get("evidence_refs")
                ),
                "dependency_reasoning": _normalized_string_list(
                    item.get("dependency_reasoning")
                ),
                "ambiguity_flags": _normalized_string_list(item.get("ambiguity_flags")),
                "source_phase_id": _first_present_string(item, "source_phase_id"),
            }
        )
    return normalized


def _normalize_planning_policy_versions(raw_value: Any) -> dict[str, str]:
    if not isinstance(raw_value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw_value.items():
        normalized_key = _string_or_empty(key)
        normalized_value = _string_or_empty(value)
        if not normalized_key or not normalized_value:
            continue
        normalized[normalized_key] = normalized_value
    return normalized


def _normalize_planning_terminal_coverage_status(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
    terminal_status: str,
) -> str:
    for value in (
        state.get("planning_coverage_status"),
        seeded_summary.get("coverage_status"),
        seeded_summary.get("planning_coverage_status"),
    ):
        normalized = _string_or_empty(value)
        if normalized in PLANNING_TERMINAL_STATUSES:
            return normalized
    return terminal_status


def _normalize_planning_runtime_records(
    raw_value: Any, *, id_field: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _iter_planning_records(raw_value, id_field=id_field):
        record_id = _first_present_string(item, id_field, "id")
        if not record_id:
            continue
        record = copy.deepcopy(item)
        record[id_field] = record_id
        records.append(record)
    return records


def _planning_terminal_status(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
) -> str:
    for value in (
        state.get("planning_terminal_status"),
        seeded_summary.get("terminal_status"),
        (seeded_summary.get("verdicts") or {}).get("run_verdict"),
        seeded_summary.get("verdict"),
    ):
        normalized = _string_or_empty(value)
        if normalized in PLANNING_TERMINAL_STATUSES:
            return normalized
    return "failed"


def _planning_run_mode(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
) -> str:
    seeded_run_details = (
        seeded_summary.get("run_details")
        if isinstance(seeded_summary.get("run_details"), dict)
        else {}
    )
    state_run_details = (
        state.get("run_details") if isinstance(state.get("run_details"), dict) else {}
    )
    strategy_spec = state.get("strategy_spec")
    for value in (
        state.get("planning_run_mode"),
        state_run_details.get("planning_run_mode"),
        seeded_summary.get("planning_run_mode"),
        seeded_summary.get("run_mode"),
        seeded_run_details.get("planning_run_mode"),
    ):
        normalized = _string_or_empty(value)
        if normalized in PLANNING_RUN_MODES:
            return normalized
    if isinstance(strategy_spec, dict):
        phase_inputs = strategy_spec.get("phase_inputs")
        if isinstance(phase_inputs, dict) and phase_inputs:
            return "fixture-backed"
    return "deterministic-live"


def _planning_execution_contract(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
) -> dict[str, str]:
    for candidate in (
        state.get("planning_execution_contract"),
        seeded_summary.get("execution_contract"),
        seeded_summary.get("planning_execution_contract"),
    ):
        if isinstance(candidate, dict) and candidate:
            return {
                "family": _string_or_empty(candidate.get("family")) or "planning_v1",
                "mode": _string_or_empty(candidate.get("mode")) or "graph_owned",
                "provider_participation": (
                    _string_or_empty(candidate.get("provider_participation")) or "none"
                ),
            }

    strategy_graph_spec = state.get("strategy_graph_spec")
    if isinstance(strategy_graph_spec, dict):
        planning_execution = strategy_graph_spec.get("planning_execution")
        if isinstance(planning_execution, dict):
            mode = _string_or_empty(planning_execution.get("mode")) or "graph_owned"
            return {
                "family": "planning_v1",
                "mode": mode,
                "provider_participation": (
                    _string_or_empty(planning_execution.get("provider_participation"))
                    or (
                        "planner_review"
                        if mode == "graph_owned_with_planner_review"
                        else "none"
                    )
                ),
            }

    strategy = state.get("strategy_spec")
    if isinstance(strategy, dict):
        planning_execution = strategy.get("planning_execution")
        if isinstance(planning_execution, dict):
            mode = _string_or_empty(planning_execution.get("mode")) or "graph_owned"
            return {
                "family": "planning_v1",
                "mode": mode,
                "provider_participation": (
                    _string_or_empty(planning_execution.get("provider_participation"))
                    or (
                        "planner_review"
                        if mode == "graph_owned_with_planner_review"
                        else "none"
                    )
                ),
            }

    return {
        "family": "planning_v1",
        "mode": "graph_owned",
        "provider_participation": "none",
    }


def plan_projection_v1(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seeded_summary = copy.deepcopy(seeded_summary or {})
    task = (
        copy.deepcopy(state.get("task_spec"))
        if isinstance(state.get("task_spec"), dict)
        else (
            copy.deepcopy(seeded_summary.get("task"))
            if isinstance(seeded_summary.get("task"), dict)
            else {}
        )
    )
    strategy_spec = (
        copy.deepcopy(state.get("strategy_spec"))
        if isinstance(state.get("strategy_spec"), dict)
        else {}
    )
    strategy_graph_spec = (
        copy.deepcopy(state.get("strategy_graph_spec"))
        if isinstance(state.get("strategy_graph_spec"), dict)
        else {}
    )
    runtime_target = _planning_runtime_target(state, seeded_summary=seeded_summary)
    raw_phase_results = (
        state.get("planning_phase_results")
        if state.get("planning_phase_results") is not None
        else seeded_summary.get("phase_results")
    )
    raw_phases = strategy_graph_spec.get("phases")
    if not isinstance(raw_phases, list):
        raw_phases = strategy_spec.get("phases")
    if not isinstance(raw_phases, list):
        raw_phases = ((seeded_summary.get("strategy") or {}).get("phases")) or []
    phases = _normalized_string_list(raw_phases)
    phase_results = _normalize_planning_phase_results(raw_phase_results)
    if not phases and phase_results:
        phases = [item["phase_id"] for item in phase_results]
    strategy = {
        "name": _string_or_empty(
            strategy_spec.get("name") or seeded_summary.get("strategy_name")
        ),
        "kind": _string_or_empty(
            state.get("strategy_kind")
            or strategy_spec.get("kind")
            or seeded_summary.get("strategy_kind")
        ),
        "runtime_target": runtime_target or PLANNING_RUNTIME_TARGET,
        "phases": phases,
    }
    terminal_status = _planning_terminal_status(state, seeded_summary=seeded_summary)
    run_mode = _planning_run_mode(state, seeded_summary=seeded_summary)
    execution_contract = _planning_execution_contract(
        state, seeded_summary=seeded_summary
    )
    coverage_status = _normalize_planning_terminal_coverage_status(
        state,
        seeded_summary=seeded_summary,
        terminal_status=terminal_status,
    )
    stop_reason = _string_or_empty(
        state.get("planning_stop_reason")
        or state.get("stop_reason")
        or seeded_summary.get("stop_reason")
        or seeded_summary.get("final_summary")
    )
    clarification_requests = _normalized_string_list(
        state.get("clarification_requests")
        if state.get("clarification_requests") is not None
        else seeded_summary.get("clarification_requests")
    )
    repo_evidence_refs = _normalized_string_list(
        state.get("repo_evidence_refs")
        if state.get("repo_evidence_refs") is not None
        else seeded_summary.get("repo_evidence_refs")
    )
    if terminal_status == "clarification_needed" and not stop_reason:
        stop_reason = "Planning requires clarification before execution can proceed."
    if terminal_status == "failed" and not stop_reason:
        stop_reason = "Planning runtime failed before emitting a valid plan."
    coverage_ledger = _normalize_planning_runtime_records(
        (
            state.get("planning_coverage_ledger")
            if state.get("planning_coverage_ledger") is not None
            else (
                seeded_summary.get("coverage_ledger")
                if seeded_summary.get("coverage_ledger") is not None
                else seeded_summary.get("planning_coverage_ledger")
            )
        ),
        id_field="coverage_id",
    )
    assumptions_register = _normalize_planning_runtime_records(
        (
            state.get("planning_assumptions_register")
            if state.get("planning_assumptions_register") is not None
            else (
                seeded_summary.get("assumptions_register")
                if seeded_summary.get("assumptions_register") is not None
                else seeded_summary.get("planning_assumptions_register")
            )
        ),
        id_field="assumption_id",
    )
    uncovered_delta = _normalize_planning_runtime_records(
        (
            state.get("planning_uncovered_delta")
            if state.get("planning_uncovered_delta") is not None
            else (
                seeded_summary.get("uncovered_delta")
                if seeded_summary.get("uncovered_delta") is not None
                else seeded_summary.get("planning_uncovered_delta")
            )
        ),
        id_field="delta_id",
    )
    payload = {
        "schema_version": PLANNING_ARTIFACT_SCHEMA_VERSION,
        "run_id": _string_or_empty(state.get("run_id") or seeded_summary.get("run_id")),
        "task": {
            "id": _string_or_empty(task.get("id")),
            "task_kind": "planning",
            "objective": _string_or_empty(task.get("objective")),
        },
        "strategy": strategy,
        "terminal_status": terminal_status,
        "run_mode": run_mode,
        "execution_contract": execution_contract,
        "stop_reason": stop_reason,
        "problem_statement": _string_or_empty(
            seeded_summary.get("problem_statement") or task.get("objective")
        ),
        "clarification_requests": clarification_requests,
        "repo_evidence_refs": repo_evidence_refs,
        "rubric_results": _normalize_rubric_results(
            raw_phase_results,
            seeded_summary=seeded_summary,
        ),
        "seams": _normalize_planning_seams(
            (
                state.get("planning_seams")
                if state.get("planning_seams") is not None
                else seeded_summary.get("seams")
            ),
            fallback_paths=repo_evidence_refs,
        ),
        "workstreams": _normalize_planning_workstreams(
            state.get("planning_workstreams")
            if state.get("planning_workstreams") is not None
            else seeded_summary.get("workstreams")
        ),
        "slices": _normalize_planning_slices(
            state.get("planning_slices")
            if state.get("planning_slices") is not None
            else seeded_summary.get("slices")
        ),
        "phase_results": phase_results,
        "policy_versions": _normalize_planning_policy_versions(
            state.get("planning_policy_versions")
            if state.get("planning_policy_versions") is not None
            else seeded_summary.get("policy_versions")
        ),
        "search_pass_count": _coerce_non_negative_int(
            state.get("search_pass_count")
            if state.get("search_pass_count") is not None
            else seeded_summary.get("search_pass_count")
        ),
        "inspected_file_count": _coerce_non_negative_int(
            state.get("inspected_file_count")
            if state.get("inspected_file_count") is not None
            else seeded_summary.get("inspected_file_count")
        ),
        "discovery_budget_escalated": bool(
            state.get("discovery_budget_escalated")
            if state.get("discovery_budget_escalated") is not None
            else seeded_summary.get("discovery_budget_escalated")
        ),
        "coverage_status": coverage_status,
        "coverage_ledger": coverage_ledger,
        "assumptions_register": assumptions_register,
        "uncovered_delta": uncovered_delta,
        "provider_stage_results": _normalize_planning_runtime_records(
            (
                state.get("planning_provider_stage_results")
                if state.get("planning_provider_stage_results") is not None
                else seeded_summary.get("planning_provider_stage_results")
            ),
            id_field="stage_id",
        ),
        "provider_review": (
            copy.deepcopy(state.get("planning_provider_review"))
            if isinstance(state.get("planning_provider_review"), dict)
            else (
                copy.deepcopy(seeded_summary.get("planning_provider_review"))
                if isinstance(seeded_summary.get("planning_provider_review"), dict)
                else {}
            )
        ),
        "provider_failure": (
            copy.deepcopy(state.get("planning_provider_failure"))
            if isinstance(state.get("planning_provider_failure"), dict)
            else (
                copy.deepcopy(seeded_summary.get("planning_provider_failure"))
                if isinstance(seeded_summary.get("planning_provider_failure"), dict)
                else {}
            )
        ),
        "provider_disagreement_count": _coerce_non_negative_int(
            state.get("planning_provider_disagreement_count")
            if state.get("planning_provider_disagreement_count") is not None
            else seeded_summary.get("planning_provider_disagreement_count")
        ),
    }
    return payload


def render_plan_markdown_v1(plan_payload: dict[str, Any]) -> str:
    lines = [
        f"# {plan_payload.get('task', {}).get('id') or 'Plan'}",
        "",
        f"- Terminal status: `{plan_payload.get('terminal_status') or 'failed'}`",
        f"- Run mode: `{plan_payload.get('run_mode') or 'deterministic-live'}`",
        (
            "- Execution contract: `"
            + str(
                (plan_payload.get("execution_contract") or {}).get("mode")
                or "graph_owned"
            )
            + "`"
        ),
        "",
        "## Problem Statement",
        plan_payload.get("problem_statement") or "- None provided.",
        "",
        "## Rubric Results",
    ]
    rubric_results = plan_payload.get("rubric_results") or []
    if rubric_results:
        lines.extend(f"- {item}" for item in rubric_results)
    else:
        lines.append("- No rubric results captured.")

    lines.extend(["", "## Architectural Seams"])
    seams = plan_payload.get("seams") or []
    if seams:
        for seam in seams:
            lines.append(
                f"- `{seam.get('seam_id')}`: {seam.get('summary') or seam.get('seam_id')}"
            )
            paths = seam.get("paths") or []
            if paths:
                lines.append(f"  Paths: {', '.join(str(path) for path in paths)}")
    else:
        lines.append("- No seams selected.")

    lines.extend(["", "## Parallel Workstreams/Worktrees"])
    workstreams = plan_payload.get("workstreams") or []
    if workstreams:
        for workstream in workstreams:
            advisory = "yes" if workstream.get("worktree_recommended") else "no"
            seam_ids = ", ".join(workstream.get("seam_ids") or []) or "none"
            lines.append(
                f"- `{workstream.get('workstream_id')}`: {workstream.get('summary') or workstream.get('workstream_id')}"
            )
            lines.append(f"  Worktree recommended: {advisory}; seam_ids: {seam_ids}")
    else:
        lines.append("- No workstreams planned.")

    lines.extend(["", "## Executable Slices"])
    slices = plan_payload.get("slices") or []
    if slices:
        for slice_payload in slices:
            lines.append(
                f"- `{slice_payload.get('slice_id')}`: {slice_payload.get('summary') or slice_payload.get('slice_id')}"
            )
            workstream_id = slice_payload.get("workstream_id") or "unassigned"
            seam_ids = ", ".join(slice_payload.get("seam_ids") or []) or "none"
            lines.append(f"  Workstream: {workstream_id}; seam_ids: {seam_ids}")
            acceptance_criteria = slice_payload.get("acceptance_criteria") or []
            if acceptance_criteria:
                lines.append(
                    "  Acceptance: "
                    + "; ".join(str(item) for item in acceptance_criteria)
                )
    else:
        lines.append("- No executable slices emitted.")

    provider_stage_results = plan_payload.get("provider_stage_results") or []
    if provider_stage_results:
        lines.extend(["", "## Provider Review"])
        for item in provider_stage_results:
            lines.append(
                f"- `{item.get('stage_id')}` via `{item.get('provider') or 'unknown'}`: "
                f"{item.get('status') or 'unknown'}"
            )
            summary = str(item.get("summary") or "").strip()
            verdict = str(item.get("verdict") or "").strip()
            if verdict or summary:
                detail = ": ".join(part for part in (verdict, summary) if part)
                lines.append(f"  Detail: {detail}")
            error = str(item.get("error") or item.get("failure_summary") or "").strip()
            if error:
                lines.append(f"  Error: {error}")

    lines.extend(["", "## Coverage Ledger"])
    coverage_ledger = plan_payload.get("coverage_ledger") or []
    if coverage_ledger:
        for coverage_row in coverage_ledger:
            lines.append(
                f"- `{coverage_row.get('coverage_id')}`: `{coverage_row.get('status')}` {coverage_row.get('summary') or coverage_row.get('dimension')}"
            )
            lines.append(
                "  Dimension: "
                + str(coverage_row.get("dimension") or "unknown")
                + "; phase_ids: "
                + (", ".join(coverage_row.get("source_phase_ids") or []) or "none")
            )
    else:
        lines.append("- No coverage rows emitted.")

    lines.extend(["", "## Assumptions Register"])
    assumptions_register = plan_payload.get("assumptions_register") or []
    if assumptions_register:
        for assumption_row in assumptions_register:
            lines.append(
                f"- `{assumption_row.get('assumption_id')}`: `{assumption_row.get('status')}` {assumption_row.get('statement') or ''}".rstrip()
            )
            lines.append(
                "  Kind: "
                + str(assumption_row.get("kind") or "unknown")
                + "; source_phase_id: "
                + str(assumption_row.get("source_phase_id") or "unknown")
            )
    else:
        lines.append("- No active assumptions remain.")

    lines.extend(["", "## Uncovered Delta"])
    uncovered_delta = plan_payload.get("uncovered_delta") or []
    if uncovered_delta:
        for delta_row in uncovered_delta:
            lines.append(
                f"- `{delta_row.get('delta_id')}`: `{delta_row.get('gap_kind')}` {delta_row.get('required_input') or ''}".rstrip()
            )
            lines.append(
                "  Coverage: "
                + str(delta_row.get("coverage_id") or "unknown")
                + "; next phase: "
                + str(delta_row.get("recommended_next_phase") or "unknown")
            )
    else:
        lines.append("- No uncovered delta remains.")
    return "\n".join(lines) + "\n"


def publish_planning_artifacts_v1(
    state: dict[str, Any],
    *,
    run_dir: Path,
    seeded_summary: dict[str, Any],
) -> dict[str, Any]:
    plan_payload = plan_projection_v1(state, seeded_summary=seeded_summary)
    terminal_status = str(plan_payload.get("terminal_status") or "failed")
    summary = copy.deepcopy(plan_payload)
    summary.update(
        {
            "thread_id": state.get("thread_id") or seeded_summary.get("thread_id"),
            "workspace": state.get("workspace_root") or seeded_summary.get("workspace"),
            "config_path": state.get("config_path")
            or seeded_summary.get("config_path"),
            "created_at": state.get("created_at") or seeded_summary.get("created_at"),
            "strategy_name": plan_payload.get("strategy", {}).get("name"),
            "strategy_kind": plan_payload.get("strategy", {}).get("kind"),
            "planning_terminal_status": terminal_status,
            "planning_stop_reason": plan_payload.get("stop_reason"),
            "planning_run_mode": plan_payload.get("run_mode"),
            "planning_execution_mode": (
                plan_payload.get("execution_contract") or {}
            ).get("mode"),
            "planning_execution_contract": copy.deepcopy(
                plan_payload.get("execution_contract") or {}
            ),
            "planning_seams": copy.deepcopy(plan_payload.get("seams") or []),
            "planning_workstreams": copy.deepcopy(
                plan_payload.get("workstreams") or []
            ),
            "planning_slices": copy.deepcopy(plan_payload.get("slices") or []),
            "planning_phase_results": copy.deepcopy(
                plan_payload.get("phase_results") or []
            ),
            "planning_policy_versions": copy.deepcopy(
                plan_payload.get("policy_versions") or {}
            ),
            "planning_provider_stage_results": copy.deepcopy(
                plan_payload.get("provider_stage_results") or []
            ),
            "planning_provider_review": copy.deepcopy(
                plan_payload.get("provider_review") or {}
            ),
            "planning_provider_failure": copy.deepcopy(
                plan_payload.get("provider_failure") or {}
            ),
            "planning_provider_disagreement_count": int(
                plan_payload.get("provider_disagreement_count") or 0
            ),
            "coverage_status": plan_payload.get("coverage_status"),
            "coverage_ledger": copy.deepcopy(plan_payload.get("coverage_ledger") or []),
            "assumptions_register": copy.deepcopy(
                plan_payload.get("assumptions_register") or []
            ),
            "uncovered_delta": copy.deepcopy(plan_payload.get("uncovered_delta") or []),
            "planning_coverage_status": plan_payload.get("coverage_status"),
            "planning_coverage_ledger": copy.deepcopy(
                plan_payload.get("coverage_ledger") or []
            ),
            "planning_assumptions_register": copy.deepcopy(
                plan_payload.get("assumptions_register") or []
            ),
            "planning_uncovered_delta": copy.deepcopy(
                plan_payload.get("uncovered_delta") or []
            ),
            "verdict": terminal_status,
            "verdicts": {
                "run_verdict": terminal_status,
                "content_verdict": terminal_status,
                "validator_verdict": state.get("validator_verdict")
                or (seeded_summary.get("verdicts") or {}).get("validator_verdict"),
                "policy_verdict": state.get("policy_verdict")
                or (seeded_summary.get("verdicts") or {}).get("policy_verdict"),
                "config_verdict": state.get("config_verdict")
                or (seeded_summary.get("verdicts") or {}).get("config_verdict")
                or "pass",
            },
            "final_summary": state.get("summary_text")
            or seeded_summary.get("final_summary")
            or plan_payload.get("stop_reason")
            or plan_payload.get("problem_statement"),
            "warnings": list(
                state.get("warnings") or seeded_summary.get("warnings") or []
            ),
            "errors": list(state.get("errors") or seeded_summary.get("errors") or []),
            "strategy_graph_spec": copy.deepcopy(
                state.get("strategy_graph_spec")
                if isinstance(state.get("strategy_graph_spec"), dict)
                else (
                    seeded_summary.get("strategy_graph_spec")
                    if isinstance(seeded_summary.get("strategy_graph_spec"), dict)
                    else {}
                )
            ),
            "run_details": copy.deepcopy(
                state.get("run_details")
                if isinstance(state.get("run_details"), dict)
                else (
                    seeded_summary.get("run_details")
                    if isinstance(seeded_summary.get("run_details"), dict)
                    else {}
                )
            ),
        }
    )

    artifacts = dict(seeded_summary.get("artifacts") or {})
    plan_json_path = run_dir / "plan.json"
    plan_md_path = run_dir / "PLAN.md"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"

    if terminal_status == "success":
        schema_errors = _soft_validate_schema(plan_payload, plan_json_schema())
        markdown = render_plan_markdown_v1(plan_payload)
        integrity_errors = validate_planning_success_artifacts(
            plan_payload,
            workspace_root=state.get("workspace_root")
            or seeded_summary.get("workspace"),
            markdown_text=markdown,
        )
        if schema_errors:
            raise ValueError(
                "plan.json schema validation failed: " + "; ".join(schema_errors)
            )
        if integrity_errors:
            raise ValueError(
                "Planning artifact publication failed integrity checks: "
                + "; ".join(integrity_errors)
            )
        write_json(plan_json_path, plan_payload)
        write_text(plan_md_path, markdown)
        artifacts["plan_json"] = str(plan_json_path)
        artifacts["plan_md"] = str(plan_md_path)
        artifacts["final_artifact"] = str(plan_md_path)
        artifacts["final_artifact_json"] = str(plan_json_path)
        artifacts["final_artifact_kind"] = "plan"
    else:
        artifacts.pop("plan_json", None)
        artifacts.pop("plan_md", None)
        artifacts.setdefault("final_artifact", "")
        artifacts.setdefault("final_artifact_kind", "none")

    artifacts["report_md"] = str(report_path)
    artifacts["summary_json"] = str(summary_path)
    artifacts["run_dir"] = str(run_dir)
    summary["artifacts"] = artifacts

    write_json(summary_path, summary)
    write_text(report_path, render_report(summary))
    return summary


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
            return copy.deepcopy(draft)
    return None


def _summary_graph_execution_mode(summary: dict[str, Any]) -> str:
    run_details = summary.get("run_details")
    if isinstance(run_details, dict):
        graph_execution = run_details.get("graph_execution")
        if isinstance(graph_execution, dict):
            return str(graph_execution.get("execution_mode") or "").strip()
    return ""


def _resolve_summary_draft_selection(
    summary: dict[str, Any],
    drafts: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    best_draft_id = _normalized_draft_id(summary.get("best_draft_id"))
    selected_draft_id = _normalized_draft_id(summary.get("selected_draft_id"))
    best_draft = _draft_by_id(drafts, best_draft_id) or _draft_by_id(
        drafts, selected_draft_id
    )
    selected_draft = _draft_by_id(drafts, selected_draft_id) or _draft_by_id(
        drafts, best_draft_id
    )

    if _summary_graph_execution_mode(summary) == "graph_owned":
        if best_draft is not None:
            summary["best_draft_id"] = best_draft.get("draft_id")
        if selected_draft is not None:
            summary["selected_draft_id"] = selected_draft.get("draft_id")
        return best_draft, selected_draft

    if best_draft is None:
        ranked_best_draft = select_best_draft(drafts)
        if ranked_best_draft is not None:
            best_draft = ranked_best_draft
            summary["best_draft_id"] = ranked_best_draft.get("draft_id")
            summary.setdefault("selected_draft_id", ranked_best_draft.get("draft_id"))
            for index, draft in enumerate(drafts):
                if draft.get("draft_id") == ranked_best_draft.get("draft_id"):
                    drafts[index] = ranked_best_draft
                    break
            selected_draft = _draft_by_id(
                drafts,
                _normalized_draft_id(summary.get("selected_draft_id"))
                or ranked_best_draft.get("draft_id"),
            )
        return best_draft, selected_draft

    summary["best_draft_id"] = best_draft.get("draft_id")
    if selected_draft is None:
        summary.setdefault("selected_draft_id", best_draft.get("draft_id"))
        selected_draft = _draft_by_id(drafts, summary.get("selected_draft_id"))
    return best_draft, selected_draft


def _sync_focus_decision_into_summary(summary: dict[str, Any]) -> None:
    top_level_focus = summary.get("focus_decision")
    run_details = summary.get("run_details")
    run_details_focus = (
        run_details.get("focus_decision")
        if isinstance(run_details, dict)
        and isinstance(run_details.get("focus_decision"), dict)
        and run_details.get("focus_decision")
        else None
    )

    if isinstance(top_level_focus, dict) and top_level_focus:
        if not isinstance(run_details, dict):
            run_details = {}
            summary["run_details"] = run_details
        run_details["focus_decision"] = copy.deepcopy(top_level_focus)
        return

    if run_details_focus is not None:
        summary["focus_decision"] = copy.deepcopy(run_details_focus)


def _semantic_validation_outcome_for_stage(
    stage: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    outcome = str(metadata.get("semantic_validation_outcome") or "").strip()
    if outcome:
        return outcome
    if stage.get("semantic_validation_errors"):
        return "failed"
    if stage.get("semantic_validation_warnings"):
        return "warnings"
    if stage.get("semantic_validation_path"):
        return "passed"
    return "not_run"


def _project_stage_trace_metadata(
    stage: dict[str, Any],
    *,
    execution_mode: str,
) -> dict[str, Any]:
    metadata = (
        copy.deepcopy(stage.get("metadata"))
        if isinstance(stage.get("metadata"), dict)
        else {}
    )
    nested_metadata = (
        metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    )
    graph_stage_id = str(
        metadata.get("graph_stage_id") or nested_metadata.get("graph_stage_id") or ""
    ).strip()
    if graph_stage_id:
        metadata["graph_stage_id"] = graph_stage_id
    graph_node_id = str(
        metadata.get("graph_node_id") or graph_stage_id or stage.get("role_name") or ""
    ).strip()
    if graph_node_id:
        metadata["graph_node_id"] = graph_node_id
    transition_reason = str(
        metadata.get("transition_reason")
        or nested_metadata.get("transition_reason")
        or ""
    ).strip()
    if transition_reason:
        metadata["transition_reason"] = transition_reason
    metadata["semantic_validation_outcome"] = _semantic_validation_outcome_for_stage(
        stage,
        metadata,
    )
    if execution_mode:
        metadata["execution_mode"] = execution_mode
    return metadata


def _project_agent_stages(
    raw_stages: Any,
    *,
    execution_mode: str,
) -> list[Any]:
    projected: list[Any] = []
    for raw_stage in raw_stages or []:
        if not isinstance(raw_stage, dict):
            projected.append(copy.deepcopy(raw_stage))
            continue
        stage = copy.deepcopy(raw_stage)
        stage["metadata"] = _project_stage_trace_metadata(
            stage,
            execution_mode=execution_mode,
        )
        projected.append(stage)
    return projected


def _graph_execution_mode(
    state: dict[str, Any],
    *,
    seeded_summary: dict[str, Any],
) -> str:
    execution_mode = str(state.get("analysis_review_execution_mode") or "").strip()
    if execution_mode:
        return execution_mode
    run_details = seeded_summary.get("run_details")
    if isinstance(run_details, dict):
        graph_execution = run_details.get("graph_execution")
        if isinstance(graph_execution, dict):
            execution_mode = str(graph_execution.get("execution_mode") or "").strip()
            if execution_mode:
                return execution_mode
    for raw_stage in (
        state.get("stage_history") or seeded_summary.get("agent_stages") or []
    ):
        if not isinstance(raw_stage, dict):
            continue
        metadata = raw_stage.get("metadata")
        if not isinstance(metadata, dict):
            continue
        execution_mode = str(metadata.get("execution_mode") or "").strip()
        if execution_mode:
            return execution_mode
    return ""


def _project_graph_execution(
    *,
    execution_mode: str,
    agent_stages: list[Any],
    seeded_summary: dict[str, Any],
) -> dict[str, Any]:
    run_details = seeded_summary.get("run_details")
    existing_graph_execution = (
        copy.deepcopy(run_details.get("graph_execution"))
        if isinstance(run_details, dict)
        and isinstance(run_details.get("graph_execution"), dict)
        else {}
    )
    transition_log = [
        {
            key: copy.deepcopy(metadata[key])
            for key in (
                "graph_node_id",
                "transition_reason",
                "semantic_validation_outcome",
                "execution_mode",
            )
            if key in metadata and metadata.get(key) not in (None, "", [])
        }
        for stage in agent_stages
        if isinstance(stage, dict)
        and isinstance((metadata := stage.get("metadata")), dict)
        and metadata
    ]
    projected = dict(existing_graph_execution)
    if execution_mode:
        projected["execution_mode"] = execution_mode
        projected["graph_owned"] = execution_mode == "graph_owned"
        projected["fallback_used"] = execution_mode != "graph_owned"
    if transition_log:
        projected["transition_log"] = transition_log
    elif isinstance(existing_graph_execution.get("transition_log"), list):
        projected["transition_log"] = copy.deepcopy(
            existing_graph_execution["transition_log"]
        )
    if not any(
        key in projected
        for key in (
            "execution_mode",
            "graph_owned",
            "fallback_used",
            "transition_log",
        )
    ):
        return {}
    return projected


def _accepted_recommendation_indices(summary: dict[str, Any]) -> list[int]:
    reviews = summary.get("recommendation_reviews") or []
    indices: list[int] = []
    for item in reviews:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict") or "").strip().lower()
        if verdict not in {"accept", "accept_with_caveat"}:
            continue
        try:
            indices.append(int(item.get("recommendation_index")))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _normalized_recommendation_indices(raw_items: Any) -> list[int]:
    indices: list[int] = []
    for item in raw_items or []:
        try:
            indices.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(indices))


def _render_plain_recommendation_indices(items: list[int]) -> str:
    return ", ".join(str(item) for item in items)


def _normalized_blocking_causes(raw_items: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items or []:
        cause = str(item).strip()
        if not cause or cause in seen:
            continue
        seen.add(cause)
        normalized.append(cause)
    return normalized


def _recommendation_admissibility(summary: dict[str, Any]) -> dict[str, Any]:
    raw_admissibility = _analysis_review_status(summary).get(
        "recommendation_admissibility"
    )
    if not isinstance(raw_admissibility, dict) or not raw_admissibility:
        return {}

    reasons_by_index: dict[str, list[str]] = {}
    for raw_index, raw_reasons in (
        raw_admissibility.get("reasons_by_recommendation_index") or {}
    ).items():
        try:
            normalized_index = int(raw_index)
        except (TypeError, ValueError):
            continue
        normalized_reasons = [
            str(reason).strip()
            for reason in (raw_reasons or [])
            if str(reason).strip() in _CANONICAL_ADMISSIBILITY_REASONS
        ]
        if normalized_reasons:
            reasons_by_index[str(normalized_index)] = normalized_reasons

    normalized = {
        "final_answer_recommendation_indices": _normalized_recommendation_indices(
            raw_admissibility.get("final_answer_recommendation_indices")
        ),
        "partial_only_recommendation_indices": _normalized_recommendation_indices(
            raw_admissibility.get("partial_only_recommendation_indices")
        ),
        "excluded_recommendation_indices": _normalized_recommendation_indices(
            raw_admissibility.get("excluded_recommendation_indices")
        ),
        "reasons_by_recommendation_index": reasons_by_index,
    }
    if not any(
        (
            normalized["final_answer_recommendation_indices"],
            normalized["partial_only_recommendation_indices"],
            normalized["excluded_recommendation_indices"],
            normalized["reasons_by_recommendation_index"],
        )
    ):
        return {}
    return normalized


def _recommendation_withholding_entries(
    recommendation_admissibility: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons_by_index = (
        recommendation_admissibility.get("reasons_by_recommendation_index") or {}
    )
    withheld_indices = sorted(
        set(
            recommendation_admissibility.get("partial_only_recommendation_indices")
            or []
        ).union(
            recommendation_admissibility.get("excluded_recommendation_indices") or []
        )
    )
    entries: list[dict[str, Any]] = []
    for recommendation_index in withheld_indices:
        reasons = [
            str(reason).strip()
            for reason in (reasons_by_index.get(str(recommendation_index)) or [])
            if str(reason).strip() in _CANONICAL_ADMISSIBILITY_REASONS
        ]
        if not reasons:
            continue
        entries.append(
            {
                "recommendation_index": recommendation_index,
                "reasons": reasons,
            }
        )
    return entries


def _partial_acceptance_min_accepted_recommendations(summary: dict[str, Any]) -> int:
    contract = summary.get("analysis_review_contract") or {}
    partial_acceptance = contract.get("partial_acceptance") or {}
    raw_minimum = partial_acceptance.get("min_accepted_recommendations")
    if raw_minimum is None:
        raw_minimum = (
            (summary.get("task") or {}).get("review_requirements") or {}
        ).get("min_recommendations")
    try:
        return max(1, int(raw_minimum))
    except (TypeError, ValueError):
        return 1


def _partial_candidate_recommendation_indices(summary: dict[str, Any]) -> list[int]:
    admissibility = _recommendation_admissibility(summary)
    if admissibility:
        return sorted(
            set(admissibility["final_answer_recommendation_indices"]).union(
                admissibility["partial_only_recommendation_indices"]
            )
        )
    return _accepted_recommendation_indices(summary)


def _recommendation_exclusion_reasons_by_index(
    summary: dict[str, Any],
    *,
    source_recommendation_indices: list[int],
    included_recommendation_indices: list[int],
) -> dict[str, list[str]]:
    included_index_set = set(included_recommendation_indices)
    admissibility = _recommendation_admissibility(summary)
    if admissibility:
        reasons_by_index = admissibility.get("reasons_by_recommendation_index") or {}
        return {
            str(index): list(reasons_by_index.get(str(index)) or [])
            for index in source_recommendation_indices
            if index not in included_index_set
            and list(reasons_by_index.get(str(index)) or [])
        }

    candidate_indices = set(_partial_candidate_recommendation_indices(summary))
    topic_eligibility = partial_accept_topic_eligibility(
        _topic_ledger(summary),
        accepted_recommendation_indices=sorted(candidate_indices),
    )
    topic_blocked_indices = set(topic_eligibility["blocked_recommendation_indices"])
    reasons_by_index: dict[str, list[str]] = {}
    for index in source_recommendation_indices:
        if index in included_index_set:
            continue
        if index in topic_blocked_indices:
            reasons_by_index[str(index)] = ["topic_blocked"]
        elif index not in candidate_indices:
            reasons_by_index[str(index)] = ["not_accepted"]
    return reasons_by_index


def _final_answer_admissible(summary: dict[str, Any], payload: dict[str, Any]) -> bool:
    return not _final_answer_payload_blockers(summary, payload)


def _partial_answer_eligibility(summary: dict[str, Any]) -> tuple[bool, list[int]]:
    candidate_indices = _partial_candidate_recommendation_indices(summary)
    if not candidate_indices:
        return (False, [])

    analysis_status = _analysis_review_status(summary)
    provenance = analysis_status.get("provenance") or {}
    review_mode = str(analysis_status.get("mode") or "").strip().lower()
    provenance_policy = str(provenance.get("policy_mode") or "").strip().lower()
    provenance_status = str(provenance.get("status") or "").strip().lower()
    if review_mode == "trust" and provenance_policy == "payload_hash_and_refs":
        if provenance_status != "bound":
            return (False, [])

    topic_eligibility = partial_accept_topic_eligibility(
        _topic_ledger(summary),
        accepted_recommendation_indices=candidate_indices,
    )
    if topic_eligibility["global_blocking_topic_ids"]:
        return (False, [])

    eligible_indices = list(topic_eligibility["eligible_recommendation_indices"])
    if len(eligible_indices) < _partial_acceptance_min_accepted_recommendations(
        summary
    ):
        return (False, [])
    return (True, eligible_indices)


def _eligible_partial_answer_indices(summary: dict[str, Any]) -> list[int]:
    eligible, recommendation_indices = _partial_answer_eligibility(summary)
    if not eligible:
        return []
    return recommendation_indices


def _analysis_review_status(summary: dict[str, Any]) -> dict[str, Any]:
    status = summary.get("analysis_review_status")
    if isinstance(status, dict) and status:
        return status
    run_details = summary.get("run_details") or {}
    status = run_details.get("analysis_review_status")
    if isinstance(status, dict) and status:
        return status
    return {}


def _analysis_publishability(summary: dict[str, Any]) -> dict[str, Any]:
    publishability = _analysis_review_status(summary).get("publishability")
    if isinstance(publishability, dict):
        return publishability
    return {}


def _canonical_primary_seam(analysis_status: dict[str, Any]) -> dict[str, Any] | None:
    primary_seam = analysis_status.get("primary_seam")
    if not isinstance(primary_seam, dict):
        return None
    return copy.deepcopy(primary_seam)


def _canonical_secondary_seams_considered(
    analysis_status: dict[str, Any],
) -> list[dict[str, Any]]:
    secondary_seams = analysis_status.get("secondary_seams_considered")
    if not isinstance(secondary_seams, list):
        return []
    return [copy.deepcopy(item) for item in secondary_seams if isinstance(item, dict)]


def _canonical_recommendation_seam_bindings(
    analysis_status: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendation_seam_bindings = analysis_status.get("recommendation_seam_bindings")
    if not isinstance(recommendation_seam_bindings, list):
        return []
    return [
        copy.deepcopy(item)
        for item in recommendation_seam_bindings
        if isinstance(item, dict)
    ]


def _canonical_analysis_scope_escapes(
    analysis_status: dict[str, Any],
) -> list[dict[str, Any]]:
    scope_escapes = analysis_status.get("scope_escapes")
    if not isinstance(scope_escapes, list):
        return []
    return [copy.deepcopy(item) for item in scope_escapes if isinstance(item, dict)]


def _normalized_seam_id(raw_value: Any) -> str:
    return str(raw_value or "").strip()


def _projected_partial_seam_state(
    summary: dict[str, Any],
    *,
    included_recommendation_indices: list[int],
) -> dict[str, Any]:
    analysis_status = _analysis_review_status(summary)
    if not analysis_status:
        return {}

    primary_seam = _canonical_primary_seam(analysis_status)
    secondary_seams = _canonical_secondary_seams_considered(analysis_status)
    recommendation_seam_bindings = _canonical_recommendation_seam_bindings(
        analysis_status
    )
    analysis_scope_escapes = _canonical_analysis_scope_escapes(analysis_status)
    included_index_set = set(included_recommendation_indices)
    included_seam_ids: set[str] = set()
    for item in recommendation_seam_bindings:
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        if recommendation_index not in included_index_set:
            continue
        seam_id = _normalized_seam_id(item.get("seam_id"))
        if seam_id:
            included_seam_ids.add(seam_id)

    projected_state: dict[str, Any] = {}
    if primary_seam is not None:
        projected_state["primary_seam"] = primary_seam
        primary_seam_id = _normalized_seam_id(primary_seam.get("seam_id"))
        if primary_seam_id and primary_seam_id not in included_seam_ids:
            projected_state["primary_seam_projection_status"] = (
                "retained_without_included_recommendations"
            )
    if secondary_seams or "secondary_seams_considered" in analysis_status:
        retained_secondary_seams = [
            seam
            for seam in secondary_seams
            if _normalized_seam_id(seam.get("seam_id")) in included_seam_ids
        ]
        projected_state["secondary_seams_considered"] = retained_secondary_seams
        retained_seam_paths: set[str] = set()
        if primary_seam is not None:
            retained_seam_paths.update(
                _non_empty_path_values(primary_seam.get("paths"))
            )
        for seam in retained_secondary_seams:
            retained_seam_paths.update(_non_empty_path_values(seam.get("paths")))
        projected_state["scope_escapes"] = [
            escape
            for escape in analysis_scope_escapes
            if str(escape.get("path") or "").strip() in retained_seam_paths
        ]
    elif analysis_scope_escapes:
        projected_state["scope_escapes"] = []
    return projected_state


def _non_empty_path_values(paths: Any) -> list[str]:
    return [str(item).strip() for item in (paths or []) if str(item).strip()]


def _set_analysis_review_status(
    summary: dict[str, Any],
    analysis_status: dict[str, Any],
) -> None:
    summary["analysis_review_status"] = copy.deepcopy(analysis_status)
    run_details = summary.get("run_details")
    if isinstance(run_details, dict) and isinstance(
        run_details.get("analysis_review_status"), dict
    ):
        run_details["analysis_review_status"] = copy.deepcopy(analysis_status)


def _is_payload_publication_blocker(cause: str) -> bool:
    return cause.startswith(_FINAL_ANSWER_INCLUDES_WITHHELD_PREFIX) or cause.startswith(
        _FINAL_ANSWER_OMITS_REQUIRED_PREFIX
    )


def _runner_publication_blockers(summary: dict[str, Any]) -> list[str]:
    return [
        cause
        for cause in _normalized_blocking_causes(
            (_analysis_publishability(summary) or {}).get("blocking_causes")
        )
        if not _is_payload_publication_blocker(cause)
    ]


def _final_answer_payload_blockers(
    summary: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    admissibility = _recommendation_admissibility(summary)
    if not admissibility:
        return []

    required_final_indices = _normalized_recommendation_indices(
        admissibility.get("final_answer_recommendation_indices")
    )
    recommendations = payload.get("recommendations")
    recommendation_count = (
        len(recommendations) if isinstance(recommendations, list) else 0
    )
    actual_payload_indices = _recommendation_source_indices(
        payload, recommendation_count
    )
    includes_withheld_indices = sorted(
        set(actual_payload_indices) - set(required_final_indices)
    )
    omits_required_indices = sorted(
        set(required_final_indices) - set(actual_payload_indices)
    )

    blocking_causes: list[str] = []
    if includes_withheld_indices:
        blocking_causes.append(
            _FINAL_ANSWER_INCLUDES_WITHHELD_PREFIX
            + _render_plain_recommendation_indices(includes_withheld_indices)
        )
    if omits_required_indices:
        blocking_causes.append(
            _FINAL_ANSWER_OMITS_REQUIRED_PREFIX
            + _render_plain_recommendation_indices(omits_required_indices)
        )
    return blocking_causes


def _finalize_analysis_publishability(
    summary: dict[str, Any],
    *,
    artifact_kind: str | None,
    payload_blockers: list[str],
) -> None:
    analysis_status = _analysis_review_status(summary)
    if not analysis_status:
        return

    finalized_status = copy.deepcopy(analysis_status)
    if artifact_kind == "final_answer":
        finalized_status["publishability"] = {
            "final_answer_publishable": True,
            "blocking_causes": [],
        }
    else:
        finalized_status["publishability"] = {
            "final_answer_publishable": False,
            "blocking_causes": _normalized_blocking_causes(
                _runner_publication_blockers(summary) + list(payload_blockers)
            ),
        }
    _set_analysis_review_status(summary, finalized_status)


def _final_answer_publication_state(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    verdict = str(summary.get("verdict") or "").strip()
    if verdict not in _FULLY_ACCEPTED_RUN_VERDICTS:
        return (False, [])

    publishability = _analysis_publishability(summary)
    if not publishability:
        return (True, [])

    blocking_causes = _normalized_blocking_causes(
        publishability.get("blocking_causes") or []
    )
    return (bool(publishability.get("final_answer_publishable")), blocking_causes)


def _topic_ledger(summary: dict[str, Any]) -> list[dict[str, Any]]:
    topic_ledger = summary.get("topic_ledger")
    if isinstance(topic_ledger, list):
        return [item for item in topic_ledger if isinstance(item, dict)]
    run_details = summary.get("run_details") or {}
    topic_ledger = run_details.get("topic_ledger")
    if isinstance(topic_ledger, list):
        return [item for item in topic_ledger if isinstance(item, dict)]
    return []


def _topic_status_ids(summary: dict[str, Any], *, status_name: str) -> list[str]:
    status = _analysis_review_status(summary)
    field_name = topic_status_field_name(status_name)
    raw_ids = status.get(field_name)
    if isinstance(raw_ids, list):
        return sorted(str(item).strip() for item in raw_ids if str(item).strip())

    return topic_ids_for_status_name(_topic_ledger(summary), status_name=status_name)


def _render_id_list(items: list[str]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return "none"
    return ", ".join(f"`{item}`" for item in values)


def _topic_source_role(topic: dict[str, Any]) -> str:
    introduced_by = str(topic.get("introduced_by") or "").strip()
    return introduced_by or "unknown"


def _topic_summary_text(topic: dict[str, Any]) -> str:
    title = str(topic.get("title") or "").strip()
    evidence = str(topic.get("evidence") or "").strip()
    repair_hint = str(topic.get("repair_hint") or "").strip()
    if title and title.lower() != "topic":
        return title
    if evidence:
        return evidence
    if repair_hint:
        return repair_hint
    return title or "Topic"


def _render_seam_paths(paths: Any) -> str:
    values = [str(item).strip() for item in (paths or []) if str(item).strip()]
    return ", ".join(f"`{item}`" for item in values) if values else "none"


def _append_seam_context_section(
    lines: list[str],
    *,
    artifact_kind: str,
    payload: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    analysis_status = _analysis_review_status(summary)
    if artifact_kind == "partial_answer":
        primary_seam = payload.get("primary_seam")
        secondary_seams = payload.get("secondary_seams_considered")
        projection_status = str(
            payload.get("primary_seam_projection_status") or ""
        ).strip()
    else:
        primary_seam = analysis_status.get("primary_seam")
        secondary_seams = analysis_status.get("secondary_seams_considered")
        projection_status = ""
        if not isinstance(primary_seam, dict):
            primary_seam = payload.get("primary_seam")
        if not isinstance(secondary_seams, list):
            secondary_seams = payload.get("secondary_seams_considered")

    primary_seam = primary_seam if isinstance(primary_seam, dict) else None
    secondary_seams = (
        [item for item in secondary_seams if isinstance(item, dict)]
        if isinstance(secondary_seams, list)
        else []
    )
    if primary_seam is None and not secondary_seams and not projection_status:
        return

    lines.extend(["## Seam Context", ""])
    if primary_seam is not None:
        lines.append(
            "- Primary seam: "
            + f"`{_normalized_seam_id(primary_seam.get('seam_id')) or 'unknown'}`"
        )
        summary_text = str(primary_seam.get("summary") or "").strip()
        if summary_text:
            lines.append(f"  - Summary: {summary_text}")
        why_primary = str(primary_seam.get("why_primary") or "").strip()
        if why_primary:
            lines.append(f"  - Why primary: {why_primary}")
        lines.append("  - Paths: " + _render_seam_paths(primary_seam.get("paths")))
    else:
        lines.append("- Primary seam: none")
    if projection_status == "retained_without_included_recommendations":
        lines.append(
            "Canonical primary seam retained for run context; no included recommendation in this artifact binds to it."
        )
    if secondary_seams:
        lines.append(
            "- Secondary seams considered: "
            + ", ".join(
                f"`{_normalized_seam_id(item.get('seam_id')) or 'unknown'}`"
                for item in secondary_seams
            )
        )
        for item in secondary_seams:
            lines.append(
                "  - "
                + f"`{_normalized_seam_id(item.get('seam_id')) or 'unknown'}`"
                + ": "
                + (str(item.get("summary") or "").strip() or "No summary provided.")
            )
    else:
        lines.append("- Secondary seams considered: none")
    lines.append("")


def _append_topic_lifecycle(lines: list[str], summary: dict[str, Any]) -> None:
    topic_ledger = _topic_ledger(summary)
    if not topic_ledger:
        return

    lines.extend(["## Topic Lifecycle", ""])
    for topic in topic_ledger:
        line = (
            f"- `{topic.get('topic_id')}` "
            f"`{topic.get('resolution_status')}` "
            f"via `{_topic_source_role(topic)}`: {_topic_summary_text(topic)}"
        )
        resolution_note = str(topic.get("resolution_note") or "").strip()
        if resolution_note:
            line += f" — {resolution_note}"
        lines.append(line)
    lines.append("")


def _recommendation_review_lookup(summary: dict[str, Any]) -> dict[int, dict[str, Any]]:
    reviews = summary.get("recommendation_reviews") or []
    lookup: dict[int, dict[str, Any]] = {}
    for item in reviews:
        if not isinstance(item, dict):
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        lookup[recommendation_index] = item
    return lookup


def _recommendation_source_indices(
    payload: dict[str, Any], recommendation_count: int
) -> list[int]:
    source_indices = payload.get("included_recommendation_indices")
    if isinstance(source_indices, list):
        normalized_indices: list[int] = []
        for item in source_indices:
            try:
                normalized_indices.append(int(item))
            except (TypeError, ValueError):
                return list(range(1, recommendation_count + 1))
        if len(normalized_indices) == recommendation_count:
            return normalized_indices
    return list(range(1, recommendation_count + 1))


def _filter_records_by_recommendation_indices(
    records: list[dict[str, Any]] | None,
    *,
    included_recommendation_indices: list[int],
) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        return []
    included_index_set = set(included_recommendation_indices)
    filtered: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        if recommendation_index not in included_index_set:
            continue
        filtered.append(copy.deepcopy(item))
    return filtered


def _partial_artifact_downgrade_causes(
    *,
    issue_ledger: list[dict[str, Any]],
    topic_ledger: list[dict[str, Any]],
    recommendation_reviews: list[dict[str, Any]],
    inferred_indices: list[int],
) -> list[str]:
    causes: list[str] = []
    if any(
        str(item.get("severity") or "").strip().lower() == "low"
        and str(item.get("resolution_status") or "").strip()
        in {"open", "carried_forward"}
        for item in issue_ledger
    ):
        causes.append("low-severity reviewer issues remain open")
    open_topic_ids = topic_ids_for_status_name(topic_ledger, status_name="open")
    if open_topic_ids:
        causes.append("open review topics remain: " + ", ".join(open_topic_ids))
    carried_forward_topic_ids = topic_ids_for_status_name(
        topic_ledger,
        status_name="carried_forward",
    )
    if carried_forward_topic_ids:
        causes.append(
            "review topics are carried forward: " + ", ".join(carried_forward_topic_ids)
        )
    accepted_caveat_indices = sorted(
        int(item.get("recommendation_index"))
        for item in recommendation_reviews
        if str(item.get("verdict") or "").strip().lower() == "accept_with_caveat"
    )
    if accepted_caveat_indices:
        causes.append(
            "accepted recommendation reviews include accept_with_caveat: "
            + ", ".join(str(item) for item in accepted_caveat_indices)
        )
    if inferred_indices:
        causes.append(
            "accepted recommendations rely on inference-only grounding: "
            + ", ".join(str(item) for item in inferred_indices)
        )
    return causes


def _build_partial_artifact_summary(
    summary: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    included_recommendation_indices = _recommendation_source_indices(
        payload,
        len(payload.get("recommendations") or []),
    )
    filtered_reviews = _filter_records_by_recommendation_indices(
        summary.get("recommendation_reviews"),
        included_recommendation_indices=included_recommendation_indices,
    )
    filtered_topic_ledger = _filter_records_by_recommendation_indices(
        _topic_ledger(summary),
        included_recommendation_indices=included_recommendation_indices,
    )
    filtered_issue_ledger = _filter_records_by_recommendation_indices(
        summary.get("issue_ledger"),
        included_recommendation_indices=included_recommendation_indices,
    )
    analysis_status = copy.deepcopy(_analysis_review_status(summary))
    included_index_set = set(included_recommendation_indices)
    inferred_indices: list[int] = []
    for item in (
        analysis_status.get("accepted_recommendations_with_inferred_grounding") or []
    ):
        try:
            recommendation_index = int(item)
        except (TypeError, ValueError):
            continue
        if recommendation_index in included_index_set:
            inferred_indices.append(recommendation_index)
    accepted_caveat_indices: list[int] = []
    for item in filtered_reviews:
        if str(item.get("verdict") or "").strip().lower() != "accept_with_caveat":
            continue
        try:
            accepted_caveat_indices.append(int(item.get("recommendation_index")))
        except (TypeError, ValueError):
            continue
    analysis_status.update(
        {
            "review_status_scope": "partial_subset",
            "recommendation_admissibility": copy.deepcopy(
                payload.get("recommendation_admissibility")
                or analysis_status.get("recommendation_admissibility")
                or {}
            ),
            "accepted_recommendations_with_caveats": sorted(
                set(accepted_caveat_indices)
            ),
            "accepted_recommendations_with_inferred_grounding": sorted(
                set(inferred_indices)
            ),
            "open_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger, status_name="open"
            ),
            "carried_forward_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger,
                status_name="carried_forward",
            ),
            "waived_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger, status_name="waived"
            ),
            "resolved_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger,
                status_name="resolved",
            ),
            "disagreed_topic_ids": topic_ids_for_status_name(
                filtered_topic_ledger,
                status_name="disagreed",
            ),
            "topic_ledger_count": len(filtered_topic_ledger),
            "downgrade_causes": _partial_artifact_downgrade_causes(
                issue_ledger=filtered_issue_ledger,
                topic_ledger=filtered_topic_ledger,
                recommendation_reviews=filtered_reviews,
                inferred_indices=sorted(set(inferred_indices)),
            ),
        }
    )
    scoped_summary = copy.deepcopy(summary)
    _set_analysis_review_status(scoped_summary, analysis_status)
    scoped_summary["recommendation_reviews"] = filtered_reviews
    scoped_summary["topic_ledger"] = filtered_topic_ledger
    scoped_summary["issue_ledger"] = filtered_issue_ledger
    return scoped_summary


def _recommendation_caveat_lines(
    *,
    recommendation_index: int,
    review_lookup: dict[int, dict[str, Any]],
    analysis_status: dict[str, Any],
) -> list[str]:
    caveat_lines: list[str] = []
    review = review_lookup.get(recommendation_index) or {}
    verdict = str(review.get("verdict") or "").strip().lower()
    if verdict == "accept_with_caveat":
        review_summary = sanitize_summary_text(
            review.get("summary"),
            surface="recommendation_review",
        )
        caveat_lines.append(
            review_summary or "This recommendation was accepted with caveats."
        )
    inferred_indices: set[int] = set()
    for item in (
        analysis_status.get("accepted_recommendations_with_inferred_grounding") or []
    ):
        try:
            inferred_indices.add(int(item))
        except (TypeError, ValueError):
            continue
    if recommendation_index in inferred_indices:
        caveat_lines.append(
            "This recommendation relies on inference-only grounding rather than direct verified evidence."
        )
    return caveat_lines


def _append_recommendation_caveat_callout(
    lines: list[str], caveat_lines: list[str]
) -> None:
    if not caveat_lines:
        return
    lines.append("> [!NOTE]")
    lines.append("> This recommendation carries review caveats:")
    for item in caveat_lines:
        lines.append(f"> - {item}")
    lines.append("")


def _render_recommendation_index_list(items: list[int]) -> str:
    if not items:
        return "none"
    return ", ".join(f"`{item}`" for item in items)


def _append_partial_admissibility_section(
    lines: list[str],
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    included_indices = _normalized_recommendation_indices(
        payload.get("included_recommendation_indices")
    )
    excluded_indices = _normalized_recommendation_indices(
        payload.get("excluded_recommendation_indices")
    )
    admissibility = (
        payload.get("recommendation_admissibility")
        if isinstance(payload.get("recommendation_admissibility"), dict)
        else _recommendation_admissibility(summary)
    )
    if not included_indices and not excluded_indices and not admissibility:
        return

    reasons_by_index = payload.get("excluded_recommendation_reasons_by_index")
    if not isinstance(reasons_by_index, dict) or not reasons_by_index:
        reasons_by_index = _recommendation_exclusion_reasons_by_index(
            summary,
            source_recommendation_indices=included_indices + excluded_indices,
            included_recommendation_indices=included_indices,
        )

    lines.extend(["## Recommendation Withholding", ""])
    lines.append(
        "- Recommendation indices included in `PARTIAL_ANSWER.*`: "
        + _render_recommendation_index_list(included_indices)
    )
    if admissibility:
        withholding_entries = _recommendation_withholding_entries(admissibility)
        lines.append(
            "- Recommendation indices withheld from `FINAL_ANSWER.*`: "
            + _render_recommendation_index_list(
                [item["recommendation_index"] for item in withholding_entries]
            )
        )
    else:
        lines.append(
            "- Recommendation indices withheld from `FINAL_ANSWER.*`: "
            + _render_recommendation_index_list(excluded_indices)
        )
    lines.append(
        "- Recommendation indices excluded from `PARTIAL_ANSWER.*`: "
        + _render_recommendation_index_list(excluded_indices)
    )
    if reasons_by_index:
        for raw_index in sorted(reasons_by_index, key=lambda item: int(item)):
            reasons = [
                str(reason).strip()
                for reason in (reasons_by_index.get(raw_index) or [])
                if str(reason).strip()
            ]
            if not reasons:
                continue
            lines.append(
                f"  - `{raw_index}`: " + ", ".join(f"`{reason}`" for reason in reasons)
            )
    lines.append("")


def _render_analysis_section(lines: list[str], title: str, section: Any) -> None:
    if not isinstance(section, dict):
        return
    items = [
        str(item).strip() for item in section.get("items", []) if str(item).strip()
    ]
    none_reason = str(section.get("none_reason") or "").strip()
    if not items and not none_reason:
        return
    lines.extend([f"## {title}", ""])
    if items:
        for item in items:
            lines.append(f"- {item}")
    elif none_reason:
        lines.append(none_reason)
    lines.append("")


def build_partial_answer_payload(
    summary: dict[str, Any], payload: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    eligible, recommendation_indices = _partial_answer_eligibility(summary)
    if not eligible:
        return None
    recommendations = payload.get("recommendations")
    if (
        not isinstance(recommendations, list)
        or not recommendations
        or not recommendation_indices
    ):
        return None
    source_indices = _recommendation_source_indices(payload, len(recommendations))
    if not set(recommendation_indices).issubset(set(source_indices)):
        return None
    selected_recommendations = [
        copy.deepcopy(item)
        for item, source_index in zip(recommendations, source_indices, strict=False)
        if source_index in recommendation_indices and isinstance(item, dict)
    ]
    if not selected_recommendations:
        return None
    excluded_indices = [
        index for index in source_indices if index not in set(recommendation_indices)
    ]
    excluded_reasons = _recommendation_exclusion_reasons_by_index(
        summary,
        source_recommendation_indices=source_indices,
        included_recommendation_indices=recommendation_indices,
    )
    recommendation_admissibility = _recommendation_admissibility(summary)
    withheld_indices = (
        [
            item["recommendation_index"]
            for item in _recommendation_withholding_entries(
                recommendation_admissibility
            )
        ]
        if recommendation_admissibility
        else excluded_indices
    )
    partial_payload = copy.deepcopy(payload)
    partial_payload["summary"] = (
        str(payload.get("summary") or "").strip()
        + "\n\n"
        + partial_acceptance_summary_suffix(
            recommendation_indices,
            withheld_indices,
            excluded_indices,
        )
    ).strip()
    partial_payload["recommendations"] = selected_recommendations
    partial_payload["included_recommendation_indices"] = recommendation_indices
    partial_payload["excluded_recommendation_indices"] = excluded_indices
    partial_payload["excluded_recommendation_reasons_by_index"] = excluded_reasons
    if recommendation_admissibility:
        partial_payload["recommendation_admissibility"] = copy.deepcopy(
            recommendation_admissibility
        )
    partial_payload.pop("primary_seam", None)
    partial_payload.pop("secondary_seams_considered", None)
    partial_payload.pop("scope_escapes", None)
    partial_payload.pop("primary_seam_projection_status", None)
    partial_payload.update(
        _projected_partial_seam_state(
            summary,
            included_recommendation_indices=recommendation_indices,
        )
    )
    filtered_reviews: list[dict[str, Any]] = []
    for item in summary.get("recommendation_reviews") or []:
        if not isinstance(item, dict):
            continue
        try:
            recommendation_index = int(item.get("recommendation_index"))
        except (TypeError, ValueError):
            continue
        if recommendation_index in recommendation_indices:
            filtered_reviews.append(copy.deepcopy(item))
    partial_payload["recommendation_reviews"] = filtered_reviews
    partial_payload["caveats"] = [
        "This is a partial answer. Excluded recommendations: "
        + f"{', '.join(str(i) for i in excluded_indices) or 'none'}."
    ]
    return partial_payload


def _augment_best_draft_payload(
    best_draft: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    enriched = copy.deepcopy(payload)
    caveats = [str(item) for item in enriched.get("caveats", []) if str(item).strip()]
    review_state = str(best_draft.get("review_state") or "not_evaluated")
    metadata = best_draft.get("metadata") or {}
    if review_state != "evaluated":
        failure_kind = str(metadata.get("review_failure_kind") or "").strip()
        failure_summary = str(metadata.get("review_failure_summary") or "").strip()
        message = "This draft was not evaluated by a successful critic/auditor stage."
        if failure_kind or failure_summary:
            detail = failure_summary or failure_kind.replace("_", " ")
            message = f"{message} Latest review attempt: {detail}."
        caveats.append(message)
    if caveats:
        enriched["caveats"] = caveats
    return enriched


def _clear_partial_artifact_state(
    summary: dict[str, Any], artifacts: dict[str, Any]
) -> None:
    summary.pop("partial_answer", None)
    artifacts.pop("partial_answer_json", None)
    artifacts.pop("partial_answer_md", None)

    if str(artifacts.get("final_artifact_kind") or "").strip() == "partial_answer":
        artifacts.pop("final_artifact_kind", None)
    final_artifact = str(artifacts.get("final_artifact") or "").strip()
    if "PARTIAL_ANSWER" in final_artifact:
        artifacts.pop("final_artifact", None)
    final_artifact_json = str(artifacts.get("final_artifact_json") or "").strip()
    if "PARTIAL_ANSWER" in final_artifact_json:
        artifacts.pop("final_artifact_json", None)


def _clear_deliverable_artifact_pointers(artifacts: dict[str, Any]) -> None:
    for key in (
        "final_artifact",
        "final_artifact_json",
        "final_artifact_kind",
        "final_answer_json",
        "final_answer_md",
        "partial_answer_json",
        "partial_answer_md",
        "best_draft_json",
        "best_draft_md",
    ):
        artifacts.pop(key, None)


def _artifact_label_for_kind(artifact_kind: str) -> str:
    labels = {
        "final_answer": "Final Answer",
        "partial_answer": "Partial Answer",
        "best_draft": "Best Draft",
    }
    try:
        return labels[artifact_kind]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported artifact kind for deliverable markdown: {artifact_kind!r}"
        ) from exc


def _final_artifact_withholding_note_inputs(summary: dict[str, Any]) -> dict[str, Any]:
    verdict = str(summary.get("verdict") or "").strip()
    if verdict not in _FULLY_ACCEPTED_RUN_VERDICTS:
        return {
            "blocking_causes": [],
            "admissibility_withheld_entries": [],
        }

    _, blocking_causes = _final_answer_publication_state(summary)
    admissibility = _recommendation_admissibility(summary)
    admissibility_withheld_entries = _recommendation_withholding_entries(admissibility)

    return {
        "blocking_causes": list(blocking_causes),
        "admissibility_withheld_entries": admissibility_withheld_entries,
    }


def _append_blocked_publication_note(
    lines: list[str],
    *,
    artifact_kind: str,
    note_inputs: dict[str, Any],
) -> None:
    if artifact_kind not in {"partial_answer", "best_draft"}:
        return

    blocking_causes = [
        str(item).strip()
        for item in (note_inputs.get("blocking_causes") or [])
        if str(item).strip()
    ]
    admissibility_withheld_entries = [
        item
        for item in (note_inputs.get("admissibility_withheld_entries") or [])
        if isinstance(item, dict)
    ]
    if not blocking_causes and not admissibility_withheld_entries:
        return
    lines.extend(
        [
            "> [!NOTE]",
            "> Final answer publication was blocked, so this deliverable is emitted as a fallback artifact.",
        ]
    )
    if blocking_causes:
        lines.append("> Publication blockers:")
        for cause in blocking_causes:
            lines.append(f"> - {cause}")
    if admissibility_withheld_entries:
        lines.append("> Recommendation indices withheld from `FINAL_ANSWER.*`:")
        for item in admissibility_withheld_entries:
            reasons = [
                str(reason).strip()
                for reason in (item.get("reasons") or [])
                if str(reason).strip()
            ]
            if not reasons:
                continue
            lines.append(
                "> - `"
                + str(item.get("recommendation_index"))
                + "`: "
                + ", ".join(f"`{reason}`" for reason in reasons)
            )
    lines.append("")


def _render_recommendation_evidence_item(evidence_item: Any) -> str:
    if isinstance(evidence_item, dict):
        path = evidence_item.get("path") or evidence_item.get("file") or "workspace"
        note = evidence_item.get("note")
        return f"{path}" + (f" — {note}" if note else "")
    return str(evidence_item)


def _append_recommendation_evidence_preview(
    lines: list[str], evidence: list[Any]
) -> None:
    if not evidence:
        return
    lines.append("**Evidence:**")
    preview = evidence[:3]
    for evidence_item in preview:
        lines.append(f"- {_render_recommendation_evidence_item(evidence_item)}")
    remaining = len(evidence) - len(preview)
    if remaining > 0:
        lines.append(f"- (+{remaining} more)")
    lines.append("")


def render_deliverable_markdown(
    task_id: str,
    payload: dict[str, Any],
    *,
    artifact_kind: str,
    artifact_label: str,
    accepted: bool,
    summary: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = [f"# {artifact_label}: {task_id}", ""]
    verdict = str((summary or {}).get("verdict") or "").strip()
    analysis_status = _analysis_review_status(summary or {})
    review_lookup = _recommendation_review_lookup(summary or {})
    if not accepted:
        lines.extend(
            [
                "> [!WARNING]",
                "> This run did not reach a fully accepted verdict. This file may contain a best-effort or partial deliverable.",
                "",
            ]
        )
    elif verdict == "accepted_with_warnings":
        lines.extend(
            [
                "> [!NOTE]",
                "> This deliverable was accepted with warnings. Review mode, provenance status, and downgrade causes are listed below.",
                "",
            ]
        )
    final_artifact_withholding_note_inputs = _final_artifact_withholding_note_inputs(
        summary or {}
    )
    _append_blocked_publication_note(
        lines,
        artifact_kind=artifact_kind,
        note_inputs=final_artifact_withholding_note_inputs if accepted else {},
    )

    if analysis_status:
        provenance = analysis_status.get("provenance") or {}
        topic_ledger = _topic_ledger(summary or {})
        open_topic_ids = _topic_status_ids(summary or {}, status_name="open")
        carried_forward_topic_ids = _topic_status_ids(
            summary or {}, status_name="carried_forward"
        )
        resolved_topic_ids = _topic_status_ids(summary or {}, status_name="resolved")
        waived_topic_ids = _topic_status_ids(summary or {}, status_name="waived")
        disagreed_topic_ids = _topic_status_ids(summary or {}, status_name="disagreed")
        review_status_scope = str(
            analysis_status.get("review_status_scope") or ""
        ).strip()
        lines.extend(["## Review Status", ""])
        if verdict:
            lines.append(f"- Verdict: `{verdict}`")
        if review_status_scope == "partial_subset":
            lines.append("- Review status scope: `included recommendations only`")
            lines.append(
                f"- Run-level mode: `{analysis_status.get('mode', 'unknown')}`"
            )
            lines.append(
                f"- Run-level provenance status: `{provenance.get('status', 'unknown')}`"
            )
            lines.append(
                f"- Run-level provenance policy: `{provenance.get('policy_mode', 'none')}`"
            )
            lines.append(
                f"- Run-level semantic warnings: `{analysis_status.get('semantic_warning_count', 0)}`"
            )
        else:
            lines.append(f"- Mode: `{analysis_status.get('mode', 'unknown')}`")
            lines.append(
                f"- Provenance status: `{provenance.get('status', 'unknown')}`"
            )
            lines.append(
                f"- Provenance policy: `{provenance.get('policy_mode', 'none')}`"
            )
            lines.append(
                f"- Semantic warnings: `{analysis_status.get('semantic_warning_count', 0)}`"
            )
        if (
            str(analysis_status.get("mode") or "").strip().lower() == "trust"
            and str(provenance.get("status") or "").strip().lower() != "bound"
        ):
            incomplete_parts: list[str] = []
            uncovered_recommendation_indices = (
                provenance.get("uncovered_recommendation_indices") or []
            )
            uncovered_global_issue_ids = (
                provenance.get("uncovered_global_issue_ids") or []
            )
            uncovered_global_topic_ids = (
                provenance.get("uncovered_global_topic_ids") or []
            )
            if uncovered_recommendation_indices:
                incomplete_parts.append(
                    "recommendation-linked closures for recommendation indices "
                    + ", ".join(str(item) for item in uncovered_recommendation_indices)
                )
            if uncovered_global_issue_ids:
                incomplete_parts.append(
                    "uncovered global issue closures: "
                    + ", ".join(str(item) for item in uncovered_global_issue_ids)
                )
            if uncovered_global_topic_ids:
                incomplete_parts.append(
                    "uncovered global topic closures: "
                    + ", ".join(str(item) for item in uncovered_global_topic_ids)
                )
            if not incomplete_parts:
                incomplete_parts.append(
                    "structured review provenance is not fully bound"
                )
            lines.append("- Closure proof incomplete: " + "; ".join(incomplete_parts))
        topic_ledger_count = analysis_status.get("topic_ledger_count")
        effective_count = topic_ledger_count
        if effective_count is None:
            effective_count = len(topic_ledger)
        if effective_count:
            lines.append(f"- Topic ledger count: `{effective_count}`")
        if open_topic_ids:
            lines.append("- Open topic IDs: " + _render_id_list(open_topic_ids))
        if carried_forward_topic_ids:
            lines.append(
                "- Carried-forward topic IDs: "
                + _render_id_list(carried_forward_topic_ids)
            )
        if resolved_topic_ids:
            lines.append("- Resolved topic IDs: " + _render_id_list(resolved_topic_ids))
        if waived_topic_ids:
            lines.append("- Waived topic IDs: " + _render_id_list(waived_topic_ids))
        if disagreed_topic_ids:
            lines.append(
                "- Disagreed topic IDs: " + _render_id_list(disagreed_topic_ids)
            )
        downgrade_causes = analysis_status.get("downgrade_causes") or []
        if downgrade_causes:
            lines.append(
                "- Downgrade causes: "
                + "; ".join(str(item) for item in downgrade_causes)
            )
        lines.append("")

    _append_seam_context_section(
        lines,
        artifact_kind=artifact_kind,
        payload=payload,
        summary=summary or {},
    )
    _append_topic_lifecycle(lines, summary or {})

    summary_text = str(payload.get("summary", "") or "").strip()
    if summary_text:
        lines.extend(["## Summary", "", summary_text, ""])

    caveats = payload.get("caveats")
    if isinstance(caveats, list) and caveats:
        lines.append("## Caveats")
        lines.append("")
        for item in caveats:
            lines.append(f"- {item}")
        lines.append("")

    if artifact_kind == "partial_answer":
        _append_partial_admissibility_section(
            lines,
            payload=payload,
            summary=summary or {},
        )

    _render_analysis_section(lines, "Strengths", payload.get("strengths"))
    _render_analysis_section(lines, "Uncertainties", payload.get("uncertainties"))

    files_reviewed = payload.get("files_reviewed")
    if isinstance(files_reviewed, list) and files_reviewed:
        lines.extend(["## Files Reviewed", ""])
        for item in files_reviewed:
            if str(item).strip():
                lines.append(f"- {item}")
        lines.append("")

    recommendations = payload.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        source_indices = _recommendation_source_indices(payload, len(recommendations))
        lines.extend(["## Recommendations", ""])
        for display_index, item in enumerate(recommendations, start=1):
            if not isinstance(item, dict):
                continue
            recommendation_index = source_indices[display_index - 1]
            title = str(item.get("title") or f"Recommendation {recommendation_index}")
            classification = str(item.get("classification") or "").strip()
            priority = str(item.get("priority") or "").strip()
            header_parts = [title]
            meta = ", ".join(bit for bit in (classification, priority) if bit)
            if meta:
                header_parts.append(f"({meta})")
            lines.append(f"### {recommendation_index}. {' '.join(header_parts)}")
            lines.append("")
            _append_recommendation_caveat_callout(
                lines,
                _recommendation_caveat_lines(
                    recommendation_index=recommendation_index,
                    review_lookup=review_lookup,
                    analysis_status=analysis_status,
                ),
            )
            for field_name, label in (
                ("rationale", "Rationale"),
                ("proposed_change", "Suggested change"),
                ("suggested_change", "Suggested change"),
            ):
                value = item.get(field_name)
                if value:
                    lines.extend([f"**{label}:** {value}", ""])
            evidence = item.get("evidence")
            if isinstance(evidence, list) and evidence:
                _append_recommendation_evidence_preview(lines, evidence)
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


def apply_final_artifacts(summary: dict[str, Any]) -> dict[str, Any]:
    """Ensure the summary includes best-draft selection and deliverable artifacts.

    Accepted runs get ``FINAL_ANSWER.*``. Partially accepted runs get
    ``PARTIAL_ANSWER.*``. Other runs get ``BEST_DRAFT.*``. The summary/report are
    rewritten after the selection step so the artifacts are internally consistent.
    """

    summary = copy.deepcopy(summary)
    _sync_focus_decision_into_summary(summary)
    run_dir = ensure_run_dir(
        (summary.get("artifacts") or {}).get("run_dir") or summary.get("run_dir") or "."
    )
    artifacts = dict(summary.get("artifacts") or {})
    task = summary.get("task") or {}
    task_id = str(task.get("id") or "task")
    _clear_deliverable_artifact_pointers(artifacts)
    bounded_review_summary = summary.get("bounded_review_summary")
    if not isinstance(bounded_review_summary, dict) or not bounded_review_summary:
        run_details = summary.get("run_details") or {}
        bounded_review_summary = run_details.get("bounded_review_summary")
        if isinstance(bounded_review_summary, dict) and bounded_review_summary:
            summary["bounded_review_summary"] = copy.deepcopy(bounded_review_summary)

    drafts = list(summary.get("drafts") or [])
    best_draft, _selected_draft = _resolve_summary_draft_selection(summary, drafts)
    summary["drafts"] = drafts

    verdict = str(summary.get("verdict") or "")
    fully_accepted = verdict in _FULLY_ACCEPTED_RUN_VERDICTS
    partially_accepted = verdict in _PARTIAL_ACCEPTED_RUN_VERDICTS
    initial_final_answer_publishable, _ = _final_answer_publication_state(summary)
    final_answer_blocked = fully_accepted and not initial_final_answer_publishable
    payload: dict[str, Any] | None = None
    final_answer_candidate_payload: dict[str, Any] | None = None
    final_answer_payload_blockers: list[str] = []
    artifact_kind = None
    artifact_json_path: Path | None = None
    artifact_md_path: Path | None = None

    if fully_accepted:
        final_answer_candidate_payload = summary.get("final_answer")
        if (
            not isinstance(final_answer_candidate_payload, dict)
            or not final_answer_candidate_payload
        ):
            if best_draft is not None:
                final_answer_candidate_payload = copy.deepcopy(
                    (best_draft.get("metadata") or {}).get("payload") or {}
                )
        if (
            isinstance(final_answer_candidate_payload, dict)
            and final_answer_candidate_payload
        ):
            final_answer_payload_blockers = _final_answer_payload_blockers(
                summary,
                final_answer_candidate_payload,
            )
    if fully_accepted and initial_final_answer_publishable:
        payload = final_answer_candidate_payload
        if isinstance(payload, dict) and payload and not final_answer_payload_blockers:
            artifact_kind = "final_answer"
            artifact_json_path = run_dir / "FINAL_ANSWER.json"
            artifact_md_path = run_dir / "FINAL_ANSWER.md"
        else:
            final_answer_blocked = True
    if artifact_kind is None and (partially_accepted or final_answer_blocked):
        partial_allowed, _ = _partial_answer_eligibility(summary)
        if partial_allowed:
            existing_partial_payload = summary.get("partial_answer")
            source_payload = summary.get("final_answer")
            if (
                not isinstance(source_payload, dict) or not source_payload
            ) and best_draft is not None:
                source_payload = copy.deepcopy(
                    (best_draft.get("metadata") or {}).get("payload") or {}
                )
            payload = build_partial_answer_payload(summary, source_payload)
            if (
                (not isinstance(payload, dict) or not payload)
                and isinstance(existing_partial_payload, dict)
                and existing_partial_payload
            ):
                payload = copy.deepcopy(existing_partial_payload)
                recommendations = payload.get("recommendations")
                recommendation_count = (
                    len(recommendations) if isinstance(recommendations, list) else 0
                )
                included_indices = _normalized_recommendation_indices(
                    payload.get("included_recommendation_indices")
                )
                excluded_indices = sorted(
                    set(
                        _recommendation_source_indices(payload, recommendation_count)
                    ).union(
                        _normalized_recommendation_indices(
                            payload.get("excluded_recommendation_indices")
                        )
                    )
                    - set(included_indices)
                )
                payload["excluded_recommendation_indices"] = excluded_indices
                payload.setdefault(
                    "excluded_recommendation_reasons_by_index",
                    _recommendation_exclusion_reasons_by_index(
                        summary,
                        source_recommendation_indices=sorted(
                            set(included_indices).union(excluded_indices)
                        ),
                        included_recommendation_indices=included_indices,
                    ),
                )
                recommendation_admissibility = _recommendation_admissibility(summary)
                if recommendation_admissibility:
                    payload.setdefault(
                        "recommendation_admissibility",
                        copy.deepcopy(recommendation_admissibility),
                    )
            if isinstance(payload, dict) and payload:
                artifact_kind = "partial_answer"
                artifact_json_path = run_dir / "PARTIAL_ANSWER.json"
                artifact_md_path = run_dir / "PARTIAL_ANSWER.md"
                summary["partial_answer"] = payload
        else:
            _clear_partial_artifact_state(summary, artifacts)

    if artifact_kind is None and final_answer_blocked:
        _clear_partial_artifact_state(summary, artifacts)

    if artifact_kind is None and (not fully_accepted or final_answer_blocked):
        if best_draft is not None:
            payload = copy.deepcopy(
                (best_draft.get("metadata") or {}).get("payload") or {}
            )
            if isinstance(payload, dict) and payload:
                payload = _augment_best_draft_payload(best_draft, payload)
            artifact_kind = "best_draft"
            artifact_json_path = run_dir / "BEST_DRAFT.json"
            artifact_md_path = run_dir / "BEST_DRAFT.md"
            summary["best_draft"] = best_draft

    _finalize_analysis_publishability(
        summary,
        artifact_kind=artifact_kind,
        payload_blockers=final_answer_payload_blockers,
    )

    if (
        artifact_json_path is not None
        and artifact_md_path is not None
        and isinstance(payload, dict)
        and payload
    ):
        emitted_payload = sanitize_artifact_payload(
            payload, artifact_kind=artifact_kind
        )
        render_summary = (
            _build_partial_artifact_summary(summary, payload)
            if artifact_kind == "partial_answer"
            else summary
        )
        write_json(artifact_json_path, emitted_payload)
        write_text(
            artifact_md_path,
            render_deliverable_markdown(
                task_id,
                emitted_payload,
                artifact_kind=artifact_kind,
                artifact_label=_artifact_label_for_kind(artifact_kind),
                accepted=fully_accepted,
                summary=render_summary,
            ),
        )
        artifacts["final_artifact"] = str(artifact_md_path)
        artifacts["final_artifact_json"] = str(artifact_json_path)
        artifacts["final_artifact_kind"] = artifact_kind
        if artifact_kind == "final_answer":
            artifacts["final_answer_json"] = str(artifact_json_path)
            artifacts["final_answer_md"] = str(artifact_md_path)
            summary["final_answer"] = payload
        elif artifact_kind == "partial_answer":
            artifacts["partial_answer_json"] = str(artifact_json_path)
            artifacts["partial_answer_md"] = str(artifact_md_path)
        else:
            artifacts["best_draft_json"] = str(artifact_json_path)
            artifacts["best_draft_md"] = str(artifact_md_path)
    else:
        artifacts.setdefault("final_artifact", "")
        artifacts.setdefault("final_artifact_kind", "none")

    contract = summary.get("analysis_review_contract")
    if isinstance(contract, dict) and contract:
        contract_path = run_dir / "analysis_review.contract.effective.json"
        write_json(contract_path, contract)
        artifacts["analysis_review_contract_json"] = str(contract_path)

    issue_ledger = summary.get("issue_ledger")
    if isinstance(issue_ledger, list) and issue_ledger:
        issue_ledger_path = run_dir / "issue_ledger.final.json"
        write_json(issue_ledger_path, issue_ledger)
        artifacts["issue_ledger_json"] = str(issue_ledger_path)

    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    artifacts["report_md"] = str(report_path)
    artifacts["summary_json"] = str(summary_path)
    artifacts["run_dir"] = str(run_dir)
    summary["artifacts"] = artifacts

    write_json(summary_path, summary)
    write_text(report_path, render_report(summary))
    return summary


def _sync_native_publish_selection(state: dict[str, Any]) -> None:
    drafts = state.get("drafts")
    if not isinstance(drafts, list) or not drafts:
        return

    selected_draft_id = _normalized_draft_id(state.get("selected_draft_id"))
    best_draft = _draft_by_id(drafts, state.get("best_draft_id")) or _draft_by_id(
        drafts, selected_draft_id
    )
    if best_draft is None:
        best_draft = select_best_draft(drafts)
        if best_draft is None:
            return

    best_draft_id = _normalized_draft_id(best_draft.get("draft_id"))
    if not best_draft_id:
        return

    best_draft = copy.deepcopy(best_draft)
    best_draft["review_status"] = "best"
    for index, draft in enumerate(drafts):
        if _normalized_draft_id(draft.get("draft_id")) == best_draft_id:
            drafts[index] = best_draft
            break

    state["best_draft_id"] = best_draft_id
    if not selected_draft_id or _draft_by_id(drafts, selected_draft_id) is None:
        state["selected_draft_id"] = best_draft_id


def _artifact_index_from_summary(summary: dict[str, Any]) -> dict[str, dict[str, str]]:
    artifact_index: dict[str, dict[str, str]] = {}
    for key, value in dict(summary.get("artifacts") or {}).items():
        if str(key).endswith("_kind"):
            continue
        path = str(value or "").strip()
        if not path:
            continue
        artifact_index[str(key)] = artifact_ref(
            path,
            kind=str(key),
            description=artifact_description(str(key)),
        )
    return artifact_index


def _should_sync_optional_container(
    value: Any,
    *,
    seeded_summary: dict[str, Any],
    key: str,
) -> bool:
    return bool(value) or key in seeded_summary


def _sync_graph_owned_native_summary_fields(
    summary: dict[str, Any],
    state: dict[str, Any],
    *,
    execution_mode: str,
    seeded_summary: dict[str, Any],
) -> None:
    if execution_mode != "graph_owned":
        return

    if "warnings" in state:
        summary["warnings"] = [str(item) for item in state.get("warnings") or []]
    if "errors" in state:
        summary["errors"] = [str(item) for item in state.get("errors") or []]

    if any(key in state for key in ("run_verdict", "content_verdict")):
        summary["verdict"] = (
            state.get("run_verdict") or state.get("content_verdict") or "invalid_config"
        )
    if any(
        key in state
        for key in (
            "run_verdict",
            "content_verdict",
            "validator_verdict",
            "policy_verdict",
            "config_verdict",
        )
    ):
        summary["verdicts"] = {
            "run_verdict": state.get("run_verdict"),
            "content_verdict": state.get("content_verdict"),
            "validator_verdict": state.get("validator_verdict"),
            "policy_verdict": state.get("policy_verdict"),
            "config_verdict": state.get("config_verdict"),
        }

    if "summary_text" in state:
        summary["final_summary"] = state.get("summary_text")
    if "failure_details" in state:
        summary["failure_details"] = (
            copy.deepcopy(state.get("failure_details"))
            if isinstance(state.get("failure_details"), dict)
            else None
        )
    if "workspace_policy_ignored_rel_paths" in state:
        summary["workspace_policy_ignored_rel_paths"] = [
            str(item) for item in state.get("workspace_policy_ignored_rel_paths") or []
        ]
    if "policy_checks" in state:
        summary["workspace_policy_checks"] = list(state.get("policy_checks") or [])
    if "final_workspace_policy_evaluation" in state:
        summary["final_workspace_policy_evaluation"] = (
            copy.deepcopy(state.get("final_workspace_policy_evaluation"))
            if isinstance(state.get("final_workspace_policy_evaluation"), dict)
            else None
        )

    if "stage_history" in state:
        summary["agent_stages"] = _project_agent_stages(
            state.get("stage_history") or [],
            execution_mode=execution_mode,
        )
    if "validator_rounds" in state:
        summary["validator_rounds"] = list(state.get("validator_rounds") or [])
    if "validator_summary" in state:
        summary["validator_summary"] = (
            copy.deepcopy(state.get("validator_summary"))
            if isinstance(state.get("validator_summary"), dict)
            else {}
        )
    if "drafts" in state:
        summary["drafts"] = list(state.get("drafts") or [])
    if "best_draft_id" in state:
        summary["best_draft_id"] = state.get("best_draft_id")
    if "selected_draft_id" in state:
        summary["selected_draft_id"] = state.get("selected_draft_id")
    if "issue_history" in state:
        summary["issue_ledger"] = list(state.get("issue_history") or [])
    if "changed_files" in state:
        summary["changed_files"] = list(state.get("changed_files") or [])
    if "initial_git_snapshot" in state:
        summary["initial_git_snapshot"] = (
            copy.deepcopy(state.get("initial_git_snapshot"))
            if isinstance(state.get("initial_git_snapshot"), dict)
            else {}
        )
    if "current_git_snapshot" in state:
        summary["final_git_snapshot"] = (
            copy.deepcopy(state.get("current_git_snapshot"))
            if isinstance(state.get("current_git_snapshot"), dict)
            else {}
        )

    if "run_details" in state:
        run_details = (
            copy.deepcopy(state.get("run_details"))
            if isinstance(state.get("run_details"), dict)
            else {}
        )
        graph_execution = (
            summary.get("run_details", {}).get("graph_execution")
            if isinstance(summary.get("run_details"), dict)
            else None
        )
        if isinstance(graph_execution, dict):
            run_details["graph_execution"] = copy.deepcopy(graph_execution)
        summary["run_details"] = run_details
    if "analysis_review_contract" in state:
        summary["analysis_review_contract"] = (
            copy.deepcopy(state.get("analysis_review_contract"))
            if isinstance(state.get("analysis_review_contract"), dict)
            else {}
        )
    if "strategy_graph_spec" in state:
        summary["strategy_graph_spec"] = (
            copy.deepcopy(state.get("strategy_graph_spec"))
            if isinstance(state.get("strategy_graph_spec"), dict)
            else {}
        )
    if "strategy_graph_spec_id" in state:
        summary["strategy_graph_spec_id"] = (
            None
            if state.get("strategy_graph_spec_id") in (None, "")
            else str(state.get("strategy_graph_spec_id"))
        )
    if "strategy_graph_subset" in state:
        summary["strategy_graph_subset"] = (
            None
            if state.get("strategy_graph_subset") in (None, "")
            else str(state.get("strategy_graph_subset"))
        )
    if "focus_decision" in state and _should_sync_optional_container(
        state.get("focus_decision"),
        seeded_summary=seeded_summary,
        key="focus_decision",
    ):
        summary["focus_decision"] = (
            copy.deepcopy(state.get("focus_decision"))
            if isinstance(state.get("focus_decision"), dict)
            else None
        )
    if "analysis_review_status" in state and _should_sync_optional_container(
        state.get("analysis_review_status"),
        seeded_summary=seeded_summary,
        key="analysis_review_status",
    ):
        summary["analysis_review_status"] = (
            copy.deepcopy(state.get("analysis_review_status"))
            if isinstance(state.get("analysis_review_status"), dict)
            else None
        )
    if "analysis_review_coverage" in state and _should_sync_optional_container(
        state.get("analysis_review_coverage"),
        seeded_summary=seeded_summary,
        key="analysis_review_coverage",
    ):
        summary["analysis_review_coverage"] = (
            copy.deepcopy(state.get("analysis_review_coverage"))
            if isinstance(state.get("analysis_review_coverage"), dict)
            else {}
        )
    if "recommendation_reviews" in state:
        summary["recommendation_reviews"] = [
            copy.deepcopy(item)
            for item in state.get("recommendation_reviews") or []
            if isinstance(item, dict)
        ]
    if "closure_proof_by_id" in state and _should_sync_optional_container(
        state.get("closure_proof_by_id"),
        seeded_summary=seeded_summary,
        key="closure_proof_by_id",
    ):
        summary["closure_proof_by_id"] = (
            copy.deepcopy(state.get("closure_proof_by_id"))
            if isinstance(state.get("closure_proof_by_id"), dict)
            else {}
        )
    if "bounded_review_summary" in state and _should_sync_optional_container(
        state.get("bounded_review_summary"),
        seeded_summary=seeded_summary,
        key="bounded_review_summary",
    ):
        summary["bounded_review_summary"] = (
            copy.deepcopy(state.get("bounded_review_summary"))
            if isinstance(state.get("bounded_review_summary"), dict)
            else {}
        )
    if "bounded_attestation_input" in state and _should_sync_optional_container(
        state.get("bounded_attestation_input"),
        seeded_summary=seeded_summary,
        key="bounded_attestation_input",
    ):
        summary["bounded_attestation_input"] = (
            copy.deepcopy(state.get("bounded_attestation_input"))
            if isinstance(state.get("bounded_attestation_input"), dict)
            else {}
        )
    if "final_answer" in state and _should_sync_optional_container(
        state.get("final_answer"),
        seeded_summary=seeded_summary,
        key="final_answer",
    ):
        summary["final_answer"] = (
            copy.deepcopy(state.get("final_answer"))
            if isinstance(state.get("final_answer"), dict)
            else None
        )
    if "topic_ledger" in state and _should_sync_optional_container(
        state.get("topic_ledger"),
        seeded_summary=seeded_summary,
        key="topic_ledger",
    ):
        summary["topic_ledger"] = [
            copy.deepcopy(item)
            for item in state.get("topic_ledger") or []
            if isinstance(item, dict)
        ]
    if "bridge_boundary_version" in state:
        if state.get("bridge_boundary_version") in (None, ""):
            summary.pop("bridge_boundary_version", None)
        else:
            summary["bridge_boundary_version"] = str(
                state.get("bridge_boundary_version")
            )


def publish_state_artifacts_v1(state: dict[str, Any]) -> dict[str, Any]:
    """Write report/summary artifacts for a state-style payload.

    This is used by the new harness graph in the rare path where the graph exits
    early before the imperative runner creates on-disk artifacts.
    """

    seeded_summary = (
        copy.deepcopy(state.get("summary_payload"))
        if isinstance(state.get("summary_payload"), dict)
        else {}
    )
    seeded_artifacts = (
        seeded_summary.get("artifacts")
        if isinstance(seeded_summary.get("artifacts"), dict)
        else {}
    )
    run_dir_raw = (
        state.get("run_dir")
        or state.get("out_root")
        or seeded_artifacts.get("run_dir")
        or seeded_summary.get("run_dir")
        or ".forge-harness-runs"
    )
    run_dir = ensure_run_dir(run_dir_raw)
    if _is_planning_runtime_state(state, seeded_summary=seeded_summary):
        summary = publish_planning_artifacts_v1(
            state,
            run_dir=run_dir,
            seeded_summary=seeded_summary,
        )
    else:
        _sync_native_publish_selection(state)
        summary = summary_projection_v1(state, run_dir=run_dir)
        summary = apply_final_artifacts(summary)
    state["artifact_index"] = _artifact_index_from_summary(summary)
    state["summary_payload"] = summary
    artifacts = dict(summary.get("artifacts") or {})
    if artifacts.get("run_dir"):
        state["run_dir"] = str(artifacts["run_dir"])
        state.setdefault("out_root", str(Path(str(artifacts["run_dir"])).parent))
    if summary.get("best_draft_id") not in (None, ""):
        state["best_draft_id"] = str(summary["best_draft_id"])
    if summary.get("selected_draft_id") not in (None, ""):
        state["selected_draft_id"] = str(summary["selected_draft_id"])
    if isinstance(summary.get("final_answer"), dict):
        state["final_answer"] = copy.deepcopy(summary["final_answer"])
    if isinstance(summary.get("bounded_review_summary"), dict):
        state["bounded_review_summary"] = copy.deepcopy(
            summary["bounded_review_summary"]
        )
    if isinstance(summary.get("analysis_review_status"), dict):
        state["analysis_review_status"] = copy.deepcopy(
            summary["analysis_review_status"]
        )
    return state


def write_state_artifacts(state: dict[str, Any]) -> dict[str, Any]:
    return publish_state_artifacts_v1(state)


def summary_projection_v1(
    state: dict[str, Any], *, run_dir: str | Path | None = None
) -> dict[str, Any]:
    projection_run_dir = (
        str(run_dir)
        if run_dir is not None
        else str(state.get("run_dir") or state.get("out_root") or ".forge-harness-runs")
    )
    seeded_summary = (
        copy.deepcopy(state.get("summary_payload"))
        if isinstance(state.get("summary_payload"), dict)
        else {}
    )
    seeded_verdicts = (
        seeded_summary.get("verdicts")
        if isinstance(seeded_summary.get("verdicts"), dict)
        else {}
    )
    execution_mode = _graph_execution_mode(state, seeded_summary=seeded_summary)
    agent_stages = _project_agent_stages(
        state.get("stage_history") or seeded_summary.get("agent_stages") or [],
        execution_mode=execution_mode,
    )
    summary = dict(seeded_summary)
    summary.update(
        {
            "run_id": state.get("run_id") or seeded_summary.get("run_id"),
            "thread_id": state.get("thread_id") or seeded_summary.get("thread_id"),
            "workspace": state.get("workspace_root") or seeded_summary.get("workspace"),
            "config_path": state.get("config_path")
            or seeded_summary.get("config_path"),
            "task": state.get("task_spec") or seeded_summary.get("task") or {},
            "strategy_name": (state.get("strategy_spec") or {}).get("name")
            or seeded_summary.get("strategy_name"),
            "strategy_kind": state.get("strategy_kind")
            or seeded_summary.get("strategy_kind"),
            "created_at": state.get("created_at") or seeded_summary.get("created_at"),
            "serialization_version": str(
                state.get("serialization_version")
                or seeded_summary.get("serialization_version")
                or HARNESS_STATE_SERIALIZATION_VERSION
            ),
            "summary_boundary_version": str(
                state.get("summary_boundary_version")
                or seeded_summary.get("summary_boundary_version")
                or SUMMARY_BOUNDARY_VERSION
            ),
            "warnings": list(
                state.get("warnings") or seeded_summary.get("warnings") or []
            ),
            "errors": list(state.get("errors") or seeded_summary.get("errors") or []),
            "verdict": state.get("run_verdict")
            or state.get("content_verdict")
            or seeded_summary.get("verdict")
            or "invalid_config",
            "verdicts": {
                "run_verdict": state.get("run_verdict")
                or seeded_verdicts.get("run_verdict"),
                "content_verdict": state.get("content_verdict")
                or seeded_verdicts.get("content_verdict"),
                "validator_verdict": state.get("validator_verdict")
                or seeded_verdicts.get("validator_verdict"),
                "policy_verdict": state.get("policy_verdict")
                or seeded_verdicts.get("policy_verdict"),
                "config_verdict": state.get("config_verdict")
                or seeded_verdicts.get("config_verdict"),
            },
            "final_summary": state.get("summary_text")
            or seeded_summary.get("final_summary"),
            "failure_details": (
                copy.deepcopy(state.get("failure_details"))
                if isinstance(state.get("failure_details"), dict)
                else (
                    copy.deepcopy(seeded_summary.get("failure_details"))
                    if isinstance(seeded_summary.get("failure_details"), dict)
                    else None
                )
            ),
            "workspace_write_policy": (
                (state.get("task_spec") or {}).get("workspace_write_policy")
                or seeded_summary.get("workspace_write_policy")
                or {}
            ),
            "workspace_policy_ignored_rel_paths": list(
                state.get("workspace_policy_ignored_rel_paths")
                or seeded_summary.get("workspace_policy_ignored_rel_paths")
                or []
            ),
            "workspace_policy_checks": list(
                state.get("policy_checks")
                or seeded_summary.get("workspace_policy_checks")
                or []
            ),
            "final_workspace_policy_evaluation": (
                copy.deepcopy(state.get("final_workspace_policy_evaluation"))
                if isinstance(state.get("final_workspace_policy_evaluation"), dict)
                else (
                    copy.deepcopy(
                        seeded_summary.get("final_workspace_policy_evaluation")
                    )
                    if isinstance(
                        seeded_summary.get("final_workspace_policy_evaluation"), dict
                    )
                    else None
                )
            ),
            "agent_stages": agent_stages,
            "validator_rounds": list(
                state.get("validator_rounds")
                or seeded_summary.get("validator_rounds")
                or []
            ),
            "validator_summary": (
                copy.deepcopy(state.get("validator_summary"))
                if isinstance(state.get("validator_summary"), dict)
                else (
                    copy.deepcopy(seeded_summary.get("validator_summary"))
                    if isinstance(seeded_summary.get("validator_summary"), dict)
                    else {}
                )
            ),
            "drafts": list(state.get("drafts") or seeded_summary.get("drafts") or []),
            "best_draft_id": state.get("best_draft_id")
            or seeded_summary.get("best_draft_id"),
            "selected_draft_id": state.get("selected_draft_id")
            or seeded_summary.get("selected_draft_id"),
            "issue_ledger": list(
                state.get("issue_history") or seeded_summary.get("issue_ledger") or []
            ),
            "changed_files": list(
                state.get("changed_files") or seeded_summary.get("changed_files") or []
            ),
            "initial_git_snapshot": (
                copy.deepcopy(state.get("initial_git_snapshot"))
                if isinstance(state.get("initial_git_snapshot"), dict)
                else (
                    copy.deepcopy(seeded_summary.get("initial_git_snapshot"))
                    if isinstance(seeded_summary.get("initial_git_snapshot"), dict)
                    else {}
                )
            ),
            "final_git_snapshot": (
                copy.deepcopy(state.get("current_git_snapshot"))
                if isinstance(state.get("current_git_snapshot"), dict)
                else (
                    copy.deepcopy(seeded_summary.get("final_git_snapshot"))
                    if isinstance(seeded_summary.get("final_git_snapshot"), dict)
                    else {}
                )
            ),
        }
    )
    artifacts = dict(seeded_summary.get("artifacts") or {})
    artifacts["run_dir"] = projection_run_dir
    summary["artifacts"] = artifacts
    run_details = (
        copy.deepcopy(seeded_summary.get("run_details"))
        if isinstance(seeded_summary.get("run_details"), dict)
        else {}
    )
    state_run_details = state.get("run_details")
    if isinstance(state_run_details, dict):
        run_details.update(copy.deepcopy(state_run_details))
    graph_execution = _project_graph_execution(
        execution_mode=execution_mode,
        agent_stages=agent_stages,
        seeded_summary=seeded_summary,
    )
    if graph_execution:
        run_details["graph_execution"] = graph_execution
    if run_details:
        summary["run_details"] = run_details
    analysis_review_contract = state.get("analysis_review_contract")
    if isinstance(analysis_review_contract, dict) and analysis_review_contract:
        summary["analysis_review_contract"] = copy.deepcopy(analysis_review_contract)
    strategy_graph_spec = state.get("strategy_graph_spec")
    if isinstance(strategy_graph_spec, dict) and strategy_graph_spec:
        summary["strategy_graph_spec"] = copy.deepcopy(strategy_graph_spec)
    strategy_graph_spec_id = state.get("strategy_graph_spec_id")
    if strategy_graph_spec_id not in (None, ""):
        summary["strategy_graph_spec_id"] = str(strategy_graph_spec_id)
    strategy_graph_subset = state.get("strategy_graph_subset")
    if strategy_graph_subset not in (None, ""):
        summary["strategy_graph_subset"] = str(strategy_graph_subset)
    focus_decision = state.get("focus_decision")
    if isinstance(focus_decision, dict):
        summary["focus_decision"] = copy.deepcopy(focus_decision)
    elif "focus_decision" in state or "focus_decision" in seeded_summary:
        summary["focus_decision"] = (
            copy.deepcopy(seeded_summary.get("focus_decision"))
            if seeded_summary.get("focus_decision") is not None
            else None
        )
    analysis_review_status = state.get("analysis_review_status")
    if isinstance(analysis_review_status, dict) and analysis_review_status:
        summary["analysis_review_status"] = copy.deepcopy(analysis_review_status)
    elif (
        "analysis_review_status" in state or "analysis_review_status" in seeded_summary
    ):
        summary["analysis_review_status"] = (
            copy.deepcopy(seeded_summary.get("analysis_review_status"))
            if seeded_summary.get("analysis_review_status") is not None
            else None
        )
    else:
        summary["analysis_review_status"] = None
    analysis_review_coverage = state.get("analysis_review_coverage")
    if isinstance(analysis_review_coverage, dict) and analysis_review_coverage:
        summary["analysis_review_coverage"] = copy.deepcopy(analysis_review_coverage)
    elif isinstance(seeded_summary.get("analysis_review_coverage"), dict):
        summary["analysis_review_coverage"] = copy.deepcopy(
            seeded_summary["analysis_review_coverage"]
        )
    recommendation_reviews = state.get("recommendation_reviews")
    if isinstance(recommendation_reviews, list):
        summary["recommendation_reviews"] = [
            copy.deepcopy(item)
            for item in recommendation_reviews
            if isinstance(item, dict)
        ]
    elif isinstance(seeded_summary.get("recommendation_reviews"), list):
        summary["recommendation_reviews"] = [
            copy.deepcopy(item)
            for item in seeded_summary["recommendation_reviews"]
            if isinstance(item, dict)
        ]
    else:
        summary["recommendation_reviews"] = []
    closure_proof_by_id = state.get("closure_proof_by_id")
    if isinstance(closure_proof_by_id, dict):
        summary["closure_proof_by_id"] = copy.deepcopy(closure_proof_by_id)
    elif isinstance(seeded_summary.get("closure_proof_by_id"), dict):
        summary["closure_proof_by_id"] = copy.deepcopy(
            seeded_summary["closure_proof_by_id"]
        )
    else:
        summary["closure_proof_by_id"] = {}
    bounded_review_summary = state.get("bounded_review_summary")
    if isinstance(bounded_review_summary, dict):
        summary["bounded_review_summary"] = copy.deepcopy(bounded_review_summary)
    elif isinstance(seeded_summary.get("bounded_review_summary"), dict):
        summary["bounded_review_summary"] = copy.deepcopy(
            seeded_summary["bounded_review_summary"]
        )
    bounded_attestation_input = state.get("bounded_attestation_input")
    if isinstance(bounded_attestation_input, dict):
        summary["bounded_attestation_input"] = copy.deepcopy(bounded_attestation_input)
    elif isinstance(seeded_summary.get("bounded_attestation_input"), dict):
        summary["bounded_attestation_input"] = copy.deepcopy(
            seeded_summary["bounded_attestation_input"]
        )
    final_answer = state.get("final_answer")
    if isinstance(final_answer, dict) and final_answer:
        summary["final_answer"] = copy.deepcopy(final_answer)
    elif isinstance(seeded_summary.get("final_answer"), dict):
        summary["final_answer"] = copy.deepcopy(seeded_summary["final_answer"])
    else:
        summary["final_answer"] = None
    topic_ledger = state.get("topic_ledger")
    if isinstance(topic_ledger, list):
        summary["topic_ledger"] = [
            copy.deepcopy(item) for item in topic_ledger if isinstance(item, dict)
        ]
    bridge_boundary_version = state.get("bridge_boundary_version")
    if bridge_boundary_version not in (None, ""):
        summary["bridge_boundary_version"] = str(bridge_boundary_version)
    _sync_graph_owned_native_summary_fields(
        summary,
        state,
        execution_mode=execution_mode,
        seeded_summary=seeded_summary,
    )
    _sync_focus_decision_into_summary(summary)
    return summary
