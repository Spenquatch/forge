from __future__ import annotations

"""Shared planning runtime helpers for the bounded C1 planning family."""

from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy
from typing import Any

from .state import HarnessState

PlanningPhaseHandler = Callable[
    [MutableMapping[str, Any], dict[str, Any], dict[str, Any], dict[str, str]],
    dict[str, Any],
]

PLANNING_PHASE_ORDER = (
    "rubric_design_doc",
    "architecture_seam_decomposition",
    "parallel_workstream_planning",
    "executable_slice_emission",
)
PLANNING_POLICY_FIELDS = (
    "artifact_policy",
    "determinism_policy",
    "discovery_policy",
    "rubric_policy",
    "stop_policy",
)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _dedupe_records(records: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        record_key = str(record.get(key) or "").strip()
        if not record_key or record_key in seen:
            continue
        seen.add(record_key)
        deduped.append(record)
    return deduped


def _stable_id(prefix: str, index: int, label: str) -> str:
    parts = []
    for char in str(label or "").lower():
        if char.isalnum():
            parts.append(char)
        elif parts and parts[-1] != "-":
            parts.append("-")
    slug = "".join(parts).strip("-") or prefix
    return f"{prefix}-{index:02d}-{slug}"


def _normalize_evidence_refs(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return refs
    for index, item in enumerate(value, start=1):
        if isinstance(item, Mapping):
            ref = {
                "id": str(item.get("id") or _stable_id("evidence", index, item.get("path") or item.get("ref") or "ref")),
                "path": str(item.get("path") or item.get("ref") or "").strip(),
                "kind": str(item.get("kind") or "workspace_ref"),
                "summary": str(item.get("summary") or item.get("note") or "").strip(),
            }
        else:
            path = str(item or "").strip()
            if not path:
                continue
            ref = {
                "id": _stable_id("evidence", index, path),
                "path": path,
                "kind": "workspace_ref",
                "summary": "",
            }
        if ref["path"]:
            refs.append(ref)
    return _dedupe_records(refs, key="id")


def _normalize_clarification_requests(value: Any, *, phase_id: str) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return requests
    for index, item in enumerate(value, start=1):
        if isinstance(item, Mapping):
            question = str(item.get("question") or item.get("prompt") or "").strip()
            rationale = str(item.get("rationale") or item.get("reason") or "").strip()
        else:
            question = str(item or "").strip()
            rationale = ""
        if not question:
            continue
        requests.append(
            {
                "id": str(
                    item.get("id")
                    if isinstance(item, Mapping) and item.get("id")
                    else _stable_id("clarify", index, phase_id)
                ),
                "phase_id": phase_id,
                "question": question,
                "rationale": rationale,
            }
        )
    return requests


def _normalize_planning_items(
    value: Any,
    *,
    item_kind: str,
    phase_id: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return normalized
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            continue
        label = str(
            item.get("title")
            or item.get("name")
            or item.get("summary")
            or item_kind
        ).strip()
        normalized.append(
            {
                "id": str(item.get("id") or _stable_id(item_kind, index, label)),
                "title": label,
                "summary": str(item.get("summary") or "").strip(),
                "repo_evidence_refs": _normalize_string_list(
                    item.get("repo_evidence_refs") or item.get("evidence_refs") or []
                ),
                "dependency_reasoning": _normalize_string_list(
                    item.get("dependency_reasoning") or []
                ),
                "ambiguity_flags": _normalize_string_list(item.get("ambiguity_flags") or []),
                "source_phase_id": phase_id,
                **{
                    key: deepcopy(value)
                    for key, value in item.items()
                    if key
                    not in {
                        "id",
                        "title",
                        "name",
                        "summary",
                        "repo_evidence_refs",
                        "evidence_refs",
                        "dependency_reasoning",
                        "ambiguity_flags",
                    }
                },
            }
        )
    return _dedupe_records(normalized, key="id")


def _phase_payload(
    strategy_spec: Mapping[str, Any],
    *,
    phase_id: str,
    stage_type: str,
) -> dict[str, Any]:
    phase_inputs = strategy_spec.get("phase_inputs")
    if not isinstance(phase_inputs, Mapping):
        return {}
    payload = phase_inputs.get(phase_id)
    if isinstance(payload, Mapping):
        return dict(payload)
    payload = phase_inputs.get(stage_type)
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}


def _lookup_planning_policy_versions(strategy_spec: Mapping[str, Any]) -> dict[str, str]:
    policy_versions: dict[str, str] = {}
    for field_name in PLANNING_POLICY_FIELDS:
        value = str(strategy_spec.get(field_name) or "").strip()
        if value:
            policy_versions[field_name] = value
    return policy_versions


def _planning_phase_result(
    *,
    phase_id: str,
    stage_type: str,
    status: str,
    stop_reason: str | None,
    evidence_refs: list[dict[str, Any]],
    clarification_requests: list[dict[str, Any]],
    seams: list[dict[str, Any]],
    workstreams: list[dict[str, Any]],
    slices: list[dict[str, Any]],
    ambiguity_flags: list[str],
    search_pass_count: int,
    inspected_file_count: int,
    discovery_budget_escalated: bool,
    policy_versions: Mapping[str, str],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "phase_id": phase_id,
        "stage_type": stage_type,
        "status": status,
        "stop_reason": stop_reason,
        "repo_evidence_ref_ids": [item["id"] for item in evidence_refs],
        "clarification_request_ids": [item["id"] for item in clarification_requests],
        "planning_seam_ids": [item["id"] for item in seams],
        "planning_workstream_ids": [item["id"] for item in workstreams],
        "planning_slice_ids": [item["id"] for item in slices],
        "ambiguity_flags": ambiguity_flags,
        "search_pass_count": search_pass_count,
        "inspected_file_count": inspected_file_count,
        "discovery_budget_escalated": discovery_budget_escalated,
        "policy_versions": dict(policy_versions),
        "summary": str(payload.get("summary") or "").strip(),
    }


def _phase_outcome(
    *,
    phase_id: str,
    stage_type: str,
    payload: Mapping[str, Any],
    policy_versions: Mapping[str, str],
    seams: list[dict[str, Any]] | None = None,
    workstreams: list[dict[str, Any]] | None = None,
    slices: list[dict[str, Any]] | None = None,
    default_status: str = "success",
    required_outputs: tuple[str, ...] = (),
) -> dict[str, Any]:
    status = str(payload.get("status") or default_status).strip() or default_status
    stop_reason = str(payload.get("stop_reason") or "").strip() or None
    ambiguity_flags = _normalize_string_list(payload.get("ambiguity_flags") or [])
    clarification_requests = _normalize_clarification_requests(
        payload.get("clarification_requests") or [],
        phase_id=phase_id,
    )
    evidence_refs = _normalize_evidence_refs(payload.get("repo_evidence_refs") or [])
    phase_seams = list(seams or [])
    phase_workstreams = list(workstreams or [])
    phase_slices = list(slices or [])

    missing_outputs = [
        output_name
        for output_name in required_outputs
        if (
            (output_name == "planning_seams" and not phase_seams)
            or (output_name == "planning_workstreams" and not phase_workstreams)
            or (output_name == "planning_slices" and not phase_slices)
        )
    ]
    if status == "success" and missing_outputs:
        status = "failed"
        stop_reason = stop_reason or f"{phase_id}_missing_{'_'.join(missing_outputs)}"

    if status == "clarification_needed" and not clarification_requests:
        clarification_requests = [
            {
                "id": _stable_id("clarify", 1, phase_id),
                "phase_id": phase_id,
                "question": str(payload.get("question") or "Additional planning detail is required.").strip(),
                "rationale": str(
                    payload.get("rationale")
                    or stop_reason
                    or "The phase could not complete credibly with the available inputs."
                ).strip(),
            }
        ]

    search_pass_count = int(payload.get("search_pass_count") or 0)
    inspected_file_count = int(payload.get("inspected_file_count") or 0)
    discovery_budget_escalated = bool(payload.get("discovery_budget_escalated", False))

    phase_result = _planning_phase_result(
        phase_id=phase_id,
        stage_type=stage_type,
        status=status,
        stop_reason=stop_reason,
        evidence_refs=evidence_refs,
        clarification_requests=clarification_requests,
        seams=phase_seams,
        workstreams=phase_workstreams,
        slices=phase_slices,
        ambiguity_flags=ambiguity_flags,
        search_pass_count=search_pass_count,
        inspected_file_count=inspected_file_count,
        discovery_budget_escalated=discovery_budget_escalated,
        policy_versions=policy_versions,
        payload=payload,
    )
    return {
        "status": status,
        "stop_reason": stop_reason,
        "clarification_requests": clarification_requests,
        "repo_evidence_refs": evidence_refs,
        "planning_seams": phase_seams,
        "planning_workstreams": phase_workstreams,
        "planning_slices": phase_slices,
        "search_pass_count": search_pass_count,
        "inspected_file_count": inspected_file_count,
        "discovery_budget_escalated": discovery_budget_escalated,
        "phase_result": phase_result,
    }


def _run_rubric_design_doc(
    state: MutableMapping[str, Any],
    phase_spec: dict[str, Any],
    payload: dict[str, Any],
    policy_versions: dict[str, str],
) -> dict[str, Any]:
    del state
    return _phase_outcome(
        phase_id=str(phase_spec["id"]),
        stage_type=str(phase_spec["stage_type"]),
        payload=payload,
        policy_versions=policy_versions,
    )


def _run_architecture_seam_decomposition(
    state: MutableMapping[str, Any],
    phase_spec: dict[str, Any],
    payload: dict[str, Any],
    policy_versions: dict[str, str],
) -> dict[str, Any]:
    del state
    seams = _normalize_planning_items(
        payload.get("planning_seams") or payload.get("seams") or [],
        item_kind="seam",
        phase_id=str(phase_spec["id"]),
    )
    return _phase_outcome(
        phase_id=str(phase_spec["id"]),
        stage_type=str(phase_spec["stage_type"]),
        payload=payload,
        policy_versions=policy_versions,
        seams=seams,
        required_outputs=("planning_seams",),
    )


def _run_parallel_workstream_planning(
    state: MutableMapping[str, Any],
    phase_spec: dict[str, Any],
    payload: dict[str, Any],
    policy_versions: dict[str, str],
) -> dict[str, Any]:
    del state
    workstreams = _normalize_planning_items(
        payload.get("planning_workstreams") or payload.get("workstreams") or [],
        item_kind="workstream",
        phase_id=str(phase_spec["id"]),
    )
    return _phase_outcome(
        phase_id=str(phase_spec["id"]),
        stage_type=str(phase_spec["stage_type"]),
        payload=payload,
        policy_versions=policy_versions,
        workstreams=workstreams,
        required_outputs=("planning_workstreams",),
    )


def _run_executable_slice_emission(
    state: MutableMapping[str, Any],
    phase_spec: dict[str, Any],
    payload: dict[str, Any],
    policy_versions: dict[str, str],
) -> dict[str, Any]:
    del state
    slices = _normalize_planning_items(
        payload.get("planning_slices") or payload.get("slices") or [],
        item_kind="slice",
        phase_id=str(phase_spec["id"]),
    )
    return _phase_outcome(
        phase_id=str(phase_spec["id"]),
        stage_type=str(phase_spec["stage_type"]),
        payload=payload,
        policy_versions=policy_versions,
        slices=slices,
        required_outputs=("planning_slices",),
    )


PLANNING_PHASE_REGISTRY: dict[str, PlanningPhaseHandler] = {
    "rubric_design_doc": _run_rubric_design_doc,
    "architecture_seam_decomposition": _run_architecture_seam_decomposition,
    "parallel_workstream_planning": _run_parallel_workstream_planning,
    "executable_slice_emission": _run_executable_slice_emission,
}


def _phase_spec(phase: Any, *, expected_stage_type: str, index: int) -> dict[str, Any]:
    if not isinstance(phase, Mapping):
        return {
            "id": f"phase_{index}",
            "stage_type": expected_stage_type,
        }
    return {
        "id": str(phase.get("id") or f"phase_{index}"),
        "stage_type": str(phase.get("stage_type") or expected_stage_type),
    }


def _seed_planning_state(
    state: MutableMapping[str, Any],
    *,
    policy_versions: dict[str, str],
) -> None:
    state["planning_terminal_status"] = None
    state["planning_stop_reason"] = None
    state["clarification_requests"] = []
    state["repo_evidence_refs"] = []
    state["planning_seams"] = []
    state["planning_workstreams"] = []
    state["planning_slices"] = []
    state["planning_phase_results"] = []
    state["planning_policy_versions"] = dict(policy_versions)
    state["search_pass_count"] = 0
    state["inspected_file_count"] = 0
    state["discovery_budget_escalated"] = False


def _merge_repo_evidence_refs(
    current_refs: list[dict[str, Any]],
    new_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_records(current_refs + new_refs, key="id")


def _append_phase_result(
    state: MutableMapping[str, Any],
    phase_result: dict[str, Any],
) -> None:
    phase_results = list(state.get("planning_phase_results") or [])
    phase_results.append(phase_result)
    state["planning_phase_results"] = phase_results


def _apply_terminal_status(
    state: MutableMapping[str, Any],
    *,
    terminal_status: str,
    stop_reason: str | None,
) -> None:
    summary_by_status = {
        "success": "Planning runtime completed successfully.",
        "clarification_needed": "Planning stopped pending clarification.",
        "failed": "Planning failed before a credible plan could be produced.",
    }
    run_verdict_by_status = {
        "success": "success",
        "clarification_needed": "clarification_needed",
        "failed": "failed",
    }
    content_verdict_by_status = {
        "success": "success",
        "clarification_needed": "clarification_needed",
        "failed": "failed",
    }
    state["planning_terminal_status"] = terminal_status
    state["planning_stop_reason"] = stop_reason
    state["stop_reason"] = stop_reason
    state["run_verdict"] = run_verdict_by_status[terminal_status]
    state["content_verdict"] = content_verdict_by_status[terminal_status]
    state["summary_text"] = summary_by_status[terminal_status]


def execute_planning_runtime(state: HarnessState) -> HarnessState:
    mutable_state = state
    strategy_spec = dict(mutable_state.get("strategy_spec") or {})
    phases = list(strategy_spec.get("phases") or [])
    policy_versions = _lookup_planning_policy_versions(strategy_spec)

    _seed_planning_state(mutable_state, policy_versions=policy_versions)

    for index, expected_stage_type in enumerate(PLANNING_PHASE_ORDER, start=1):
        phase_spec = _phase_spec(
            phases[index - 1] if index - 1 < len(phases) else {},
            expected_stage_type=expected_stage_type,
            index=index,
        )
        stage_type = str(phase_spec["stage_type"])
        handler = PLANNING_PHASE_REGISTRY.get(stage_type)
        if handler is None:
            _apply_terminal_status(
                mutable_state,
                terminal_status="failed",
                stop_reason=f"unsupported_planning_phase:{stage_type}",
            )
            return state

        payload = _phase_payload(
            strategy_spec,
            phase_id=str(phase_spec["id"]),
            stage_type=stage_type,
        )
        outcome = handler(mutable_state, phase_spec, payload, policy_versions)

        mutable_state["repo_evidence_refs"] = _merge_repo_evidence_refs(
            list(mutable_state.get("repo_evidence_refs") or []),
            list(outcome.get("repo_evidence_refs") or []),
        )
        if outcome.get("planning_seams"):
            mutable_state["planning_seams"] = list(outcome["planning_seams"])
        if outcome.get("planning_workstreams"):
            mutable_state["planning_workstreams"] = list(outcome["planning_workstreams"])
        if outcome.get("planning_slices"):
            mutable_state["planning_slices"] = list(outcome["planning_slices"])
        mutable_state["search_pass_count"] = int(
            mutable_state.get("search_pass_count") or 0
        ) + int(outcome.get("search_pass_count") or 0)
        mutable_state["inspected_file_count"] = int(
            mutable_state.get("inspected_file_count") or 0
        ) + int(outcome.get("inspected_file_count") or 0)
        mutable_state["discovery_budget_escalated"] = bool(
            mutable_state.get("discovery_budget_escalated") or outcome.get("discovery_budget_escalated")
        )
        _append_phase_result(
            mutable_state,
            dict(outcome.get("phase_result") or {}),
        )

        status = str(outcome.get("status") or "success")
        if status != "success":
            mutable_state["clarification_requests"] = list(
                outcome.get("clarification_requests") or []
            )
            _apply_terminal_status(
                mutable_state,
                terminal_status=status,
                stop_reason=str(outcome.get("stop_reason") or f"{phase_spec['id']}_{status}"),
            )
            return state

    mutable_state["clarification_requests"] = []
    _apply_terminal_status(mutable_state, terminal_status="success", stop_reason=None)
    return state
