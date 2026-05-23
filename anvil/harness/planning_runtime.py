# mypy: disable-error-code="arg-type,typeddict-item"

from __future__ import annotations

"""Shared planning runtime helpers for the bounded C1 planning family."""

import json
import re
from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .bounded_stage_runtime import StageHandler, run_linear_stage_sequence
from .files import read_workspace_text, workspace_glob_paths
from .provider_adapter import get_provider
from .state import HarnessState
from .types import RoleConfig, StageRequest

PLANNING_PHASE_ORDER = (
    "rubric_design_doc",
    "architecture_seam_decomposition",
    "parallel_workstream_planning",
    "executable_slice_emission",
)
PLANNING_COVERAGE_DIMENSIONS = (
    "problem_frame",
    "repo_surface",
    "seam_selection",
    "dependency_shape",
    "execution_partitioning",
    "acceptance_shape",
    "risk_and_unknowns",
)
PLANNING_POLICY_FIELDS = (
    "artifact_policy",
    "coverage_policy",
    "determinism_policy",
    "discovery_policy",
    "rubric_policy",
    "stop_policy",
)
PLANNING_MATCH_LIMIT = 25
PLANNING_READ_LIMIT = 12
PLANNING_READ_BYTES_LIMIT = 150 * 1024
PLANNER_REVIEW_STAGE_TYPE = "planner_review"
PLANNING_DETERMINISTIC_POSTURE = "canonical_first_pass"
_TASK_TERMINAL_MODE_RE = re.compile(
    r"planning_fixture_mode\s*[:=]\s*(clarification_needed|failed)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_OUT_OF_CORPUS_RE = re.compile(
    r"\b("
    r"greenfield|from scratch|new app|new system|new service|multi-repo|"
    r"multi repo|migration|cross-team|cross team"
    r")\b",
    re.IGNORECASE,
)
_TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "but",
    "for",
    "from",
    "into",
    "its",
    "keep",
    "new",
    "not",
    "out",
    "plan",
    "planning",
    "runtime",
    "shared",
    "that",
    "the",
    "this",
    "use",
    "using",
    "with",
}
_CANONICAL_SEAM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "seam_id": "seam-runtime-routing",
        "title": "Runtime Target Routing",
        "summary": (
            "Route planning strategies through the shared harness graph runtime "
            "target."
        ),
        "path_hints": (
            "anvil/harness/builder.py",
            "anvil/harness/strategy_graph.py",
            "anvil/harness/planning_runtime.py",
            "anvil/harness/subgraphs/planning_v1.py",
        ),
        "workstream": {
            "workstream_id": "workstream-runtime-wiring",
            "title": "Runtime Wiring",
            "summary": ("Mount planning_v1 and preserve generic post-runtime routing."),
        },
        "slice": {
            "slice_id": "slice-mount-planning-runtime",
            "title": "Mount planning_v1",
            "summary": (
                "Add the planning runtime family and bypass draft selection for "
                "planning runs."
            ),
            "acceptance_criteria": [
                "planning_v1 is mounted in the shared graph builder",
                "planning routes directly to artifact writing",
            ],
        },
    },
    {
        "seam_id": "seam-artifact-publication",
        "title": "Planning Artifact Publication",
        "summary": (
            "Publish deterministic planning artifacts through the shared write seam."
        ),
        "path_hints": (
            "anvil/harness/reporting.py",
            "anvil/harness/artifacts.py",
            "anvil/harness/report.py",
        ),
        "workstream": {
            "workstream_id": "workstream-artifact-surface",
            "title": "Artifact Surface",
            "summary": "Project the frozen planning payload into PLAN.md and plan.json.",
        },
        "slice": {
            "slice_id": "slice-publish-planning-artifacts",
            "title": "Publish planning artifacts",
            "summary": (
                "Emit deterministic PLAN.md and plan.json artifacts for successful "
                "runs."
            ),
            "acceptance_criteria": [
                "artifact_index contains plan_md and plan_json",
                "CLI JSON returns the planning terminal payload",
            ],
        },
    },
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


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _empty_provider_review_delta(*, summary: str) -> dict[str, Any]:
    return {
        "delta_status": "none",
        "summary": summary,
        "uncovered_cited_surfaces": [],
        "behavioral_coverage_gaps": [],
        "expansion_candidates": [],
        "follow_up_questions": [],
        "confidence": 0.0,
        "preserves_canonical_structure": True,
    }


def _stable_id(prefix: str, index: int, label: str) -> str:
    parts = []
    for char in str(label or "").lower():
        if char.isalnum():
            parts.append(char)
        elif parts and parts[-1] != "-":
            parts.append("-")
    slug = "".join(parts).strip("-") or prefix
    return f"{prefix}-{index:02d}-{slug}"


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
            item.get("title") or item.get("name") or item.get("summary") or item_kind
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
                "ambiguity_flags": _normalize_string_list(
                    item.get("ambiguity_flags") or []
                ),
                "source_phase_id": phase_id,
                **{
                    key: deepcopy(item_value)
                    for key, item_value in item.items()
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


def _task_terminal_mode(task_spec: Mapping[str, Any]) -> str:
    for field_name in ("notes", "context", "prompt_addendum"):
        value = str(task_spec.get(field_name) or "")
        match = _TASK_TERMINAL_MODE_RE.search(value)
        if match:
            return str(match.group(1)).lower()
    return ""


def _task_terminal_override(
    task_spec: Mapping[str, Any],
    *,
    phase_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    mode = _task_terminal_mode(task_spec)
    if not mode:
        return None
    if mode == "clarification_needed":
        clarification_requests = payload.get("clarification_requests")
        if not isinstance(clarification_requests, list) or not clarification_requests:
            clarification_requests = [
                {
                    "question": (
                        "Which seam or repository surface should the planning "
                        "package prioritize first?"
                    ),
                    "rationale": (
                        "The task fixture explicitly requests clarification before "
                        "continuing."
                    ),
                }
            ]
        return {
            **dict(payload),
            "status": "clarification_needed",
            "stop_reason": str(
                payload.get("stop_reason") or f"{phase_id}_needs_clarification"
            ),
            "clarification_requests": clarification_requests,
        }
    return {
        **dict(payload),
        "status": "failed",
        "stop_reason": str(payload.get("stop_reason") or f"{phase_id}_failed"),
    }


def _lookup_planning_policy_versions(
    strategy_spec: Mapping[str, Any],
) -> dict[str, str]:
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
    evidence_refs: list[str],
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
    phase_result = {
        "phase_id": phase_id,
        "stage_type": stage_type,
        "status": status,
        "stop_reason": stop_reason,
        "repo_evidence_refs": list(evidence_refs),
        "clarification_request_ids": [item["id"] for item in clarification_requests],
        "planning_seam_ids": [
            str(item.get("seam_id") or item.get("id") or "") for item in seams
        ],
        "planning_workstream_ids": [
            str(item.get("workstream_id") or item.get("id") or "")
            for item in workstreams
        ],
        "planning_slice_ids": [
            str(item.get("slice_id") or item.get("id") or "") for item in slices
        ],
        "ambiguity_flags": ambiguity_flags,
        "search_pass_count": search_pass_count,
        "inspected_file_count": inspected_file_count,
        "discovery_budget_escalated": discovery_budget_escalated,
        "policy_versions": dict(policy_versions),
        "summary": str(payload.get("summary") or "").strip(),
    }
    primary_cut_summary = str(payload.get("primary_cut_summary") or "").strip()
    if primary_cut_summary:
        phase_result["primary_cut_summary"] = primary_cut_summary
    return phase_result


def _normalize_clarification_requests(
    value: Any, *, phase_id: str
) -> list[dict[str, Any]]:
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
    evidence_refs = _normalize_string_list(payload.get("repo_evidence_refs") or [])
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
                "question": str(
                    payload.get("question") or "Additional planning detail is required."
                ).strip(),
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
) -> dict[str, Any]:
    policy_versions = dict(state.get("planning_policy_versions") or {})
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
) -> dict[str, Any]:
    policy_versions = dict(state.get("planning_policy_versions") or {})
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
) -> dict[str, Any]:
    policy_versions = dict(state.get("planning_policy_versions") or {})
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
) -> dict[str, Any]:
    policy_versions = dict(state.get("planning_policy_versions") or {})
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


def _planning_provider_review_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["accept", "accept_with_caveat", "revise"],
            },
            "summary": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "coverage_challenges": {"type": "array", "items": {"type": "string"}},
            "provider_review_delta": {
                "type": "object",
                "properties": {
                    "delta_status": {
                        "type": "string",
                        "enum": [
                            "none",
                            "expansion_recommended",
                            "clarification_recommended",
                        ],
                    },
                    "summary": {"type": "string"},
                    "uncovered_cited_surfaces": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "gap_kind": {
                                    "type": "string",
                                    "enum": [
                                        "uncovered",
                                        "under_planned",
                                        "evidence_only_needs_attestation",
                                    ],
                                },
                                "reason": {"type": "string"},
                                "linked_seam_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "linked_workstream_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "linked_slice_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "path",
                                "gap_kind",
                                "reason",
                                "linked_seam_ids",
                                "linked_workstream_ids",
                                "linked_slice_ids",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "behavioral_coverage_gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "expansion_candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_kind": {
                                    "type": "string",
                                    "enum": [
                                        "seam_expansion",
                                        "workstream_expansion",
                                        "slice_expansion",
                                        "coverage_attestation",
                                        "clarification",
                                    ],
                                },
                                "summary": {"type": "string"},
                                "cited_paths": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "attach_to_seam_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "attach_to_workstream_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "attach_to_slice_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "candidate_kind",
                                "summary",
                                "cited_paths",
                                "attach_to_seam_ids",
                                "attach_to_workstream_ids",
                                "attach_to_slice_ids",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "follow_up_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "preserves_canonical_structure": {"type": "boolean"},
                },
                "required": [
                    "delta_status",
                    "summary",
                    "uncovered_cited_surfaces",
                    "behavioral_coverage_gaps",
                    "expansion_candidates",
                    "follow_up_questions",
                    "confidence",
                    "preserves_canonical_structure",
                ],
                "additionalProperties": False,
            },
            "follow_up_questions": {"type": "array", "items": {"type": "string"}},
            "referenced_seam_ids": {"type": "array", "items": {"type": "string"}},
            "referenced_workstream_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "referenced_slice_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "verdict",
            "summary",
            "strengths",
            "risks",
            "coverage_challenges",
            "provider_review_delta",
            "follow_up_questions",
            "referenced_seam_ids",
            "referenced_workstream_ids",
            "referenced_slice_ids",
            "confidence",
        ],
        "additionalProperties": False,
    }


def _planning_provider_review_payload(
    state: Mapping[str, Any],
) -> dict[str, Any]:
    coverage_rows = [
        {
            "dimension": str(item.get("dimension") or ""),
            "status": str(item.get("status") or ""),
            "summary": str(item.get("summary") or ""),
        }
        for item in _list_of_dicts(state.get("planning_coverage_ledger") or [])
    ]
    return {
        "task": {
            "objective": str((state.get("task_spec") or {}).get("objective") or ""),
            "acceptance": list((state.get("task_spec") or {}).get("acceptance") or []),
            "constraints": list(
                (state.get("task_spec") or {}).get("constraints") or []
            ),
        },
        "deterministic_planning_posture": PLANNING_DETERMINISTIC_POSTURE,
        "repo_evidence_refs": list(state.get("repo_evidence_refs") or []),
        "seams": _list_of_dicts(state.get("planning_seams") or []),
        "workstreams": _list_of_dicts(state.get("planning_workstreams") or []),
        "slices": _list_of_dicts(state.get("planning_slices") or []),
        "coverage_ledger": coverage_rows,
        "uncovered_delta": _list_of_dicts(state.get("planning_uncovered_delta") or []),
        "assumptions_register": _list_of_dicts(
            state.get("planning_assumptions_register") or []
        ),
        "phase_results": _list_of_dicts(state.get("planning_phase_results") or []),
    }


def _planning_provider_review_prompt(
    state: Mapping[str, Any],
    *,
    review_payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "Review the deterministic planning package as a bounded canonical first pass.",
            "You may only review, challenge, or attest the package without changing its canonical structure.",
            "Do not invent new seam, workstream, or slice ids.",
            "Do not rewrite or replace canonical seam, workstream, or slice ownership.",
            "Classify cited surfaces as planned, intentionally evidence-only, uncovered, or under-planned.",
            "Use provider_review_delta to describe expansion or clarification need without flattening deterministic coverage truth.",
            "If you disagree with the package, explain the disagreement in risks or coverage_challenges and mirror the actionable result in provider_review_delta.",
            "",
            "Return JSON matching the provided schema.",
            "",
            "Deterministic planning package:",
            json.dumps(review_payload, indent=2, sort_keys=False),
        ]
    )


def _normalized_provider_review_delta(
    review_output: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(review_output, Mapping):
        return _empty_provider_review_delta(
            summary="Provider review was not exercised."
        )

    raw_delta = review_output.get("provider_review_delta")
    follow_up_questions = _normalize_string_list(
        review_output.get("follow_up_questions") or []
    )
    if not isinstance(raw_delta, Mapping):
        verdict = str(review_output.get("verdict") or "").strip().lower()
        behavioral_gaps = _normalize_string_list(
            review_output.get("coverage_challenges") or []
        )
        risks = _normalize_string_list(review_output.get("risks") or [])
        if verdict in {"accept_with_caveat", "revise"} or behavioral_gaps or risks:
            return {
                "delta_status": (
                    "clarification_recommended"
                    if follow_up_questions and not (behavioral_gaps or risks)
                    else "expansion_recommended"
                ),
                "summary": str(review_output.get("summary") or "").strip(),
                "uncovered_cited_surfaces": [],
                "behavioral_coverage_gaps": behavioral_gaps or risks,
                "expansion_candidates": [],
                "follow_up_questions": follow_up_questions,
                "confidence": float(review_output.get("confidence") or 0.0),
                "preserves_canonical_structure": True,
            }
        return _empty_provider_review_delta(
            summary="Provider review found no expansion delta."
        )

    uncovered_cited_surfaces: list[dict[str, Any]] = []
    for item in _list_of_dicts(raw_delta.get("uncovered_cited_surfaces") or []):
        uncovered_cited_surfaces.append(
            {
                "path": str(item.get("path") or "").strip(),
                "gap_kind": str(item.get("gap_kind") or "").strip(),
                "reason": str(item.get("reason") or "").strip(),
                "linked_seam_ids": _normalize_string_list(
                    item.get("linked_seam_ids") or []
                ),
                "linked_workstream_ids": _normalize_string_list(
                    item.get("linked_workstream_ids") or []
                ),
                "linked_slice_ids": _normalize_string_list(
                    item.get("linked_slice_ids") or []
                ),
            }
        )

    expansion_candidates: list[dict[str, Any]] = []
    for item in _list_of_dicts(raw_delta.get("expansion_candidates") or []):
        expansion_candidates.append(
            {
                "candidate_kind": str(item.get("candidate_kind") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "cited_paths": _normalize_string_list(item.get("cited_paths") or []),
                "attach_to_seam_ids": _normalize_string_list(
                    item.get("attach_to_seam_ids") or []
                ),
                "attach_to_workstream_ids": _normalize_string_list(
                    item.get("attach_to_workstream_ids") or []
                ),
                "attach_to_slice_ids": _normalize_string_list(
                    item.get("attach_to_slice_ids") or []
                ),
            }
        )

    delta_status = str(raw_delta.get("delta_status") or "none").strip() or "none"
    summary = str(raw_delta.get("summary") or "").strip()
    return {
        "delta_status": delta_status,
        "summary": summary,
        "uncovered_cited_surfaces": uncovered_cited_surfaces,
        "behavioral_coverage_gaps": _normalize_string_list(
            raw_delta.get("behavioral_coverage_gaps") or []
        ),
        "expansion_candidates": expansion_candidates,
        "follow_up_questions": _normalize_string_list(
            raw_delta.get("follow_up_questions") or follow_up_questions
        ),
        "confidence": float(raw_delta.get("confidence") or 0.0),
        "preserves_canonical_structure": bool(
            raw_delta.get("preserves_canonical_structure", True)
        ),
    }


def _planner_role_config(state: Mapping[str, Any]) -> RoleConfig | None:
    strategy_spec = state.get("strategy_spec")
    if not isinstance(strategy_spec, Mapping):
        return None
    roles = strategy_spec.get("roles")
    if not isinstance(roles, Mapping):
        return None
    planner_role = roles.get("planner")
    if not isinstance(planner_role, Mapping):
        return None
    return RoleConfig.from_dict(dict(planner_role))


def _append_provider_stage_result(
    state: MutableMapping[str, Any],
    provider_stage_result: dict[str, Any],
) -> None:
    provider_stage_results = list(state.get("planning_provider_stage_results") or [])
    provider_stage_results.append(provider_stage_result)
    state["planning_provider_stage_results"] = provider_stage_results


def _run_planner_review(
    state: MutableMapping[str, Any],
    phase_spec: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    del payload
    planner_role = _planner_role_config(state)
    if planner_role is None:
        failure = {
            "stage_id": str(phase_spec.get("id") or "planner_review"),
            "stage_type": str(
                phase_spec.get("stage_type") or PLANNER_REVIEW_STAGE_TYPE
            ),
            "role_name": "planner",
            "status": "failed",
            "provider": "",
            "error": "planner role is not configured for provider-backed planning review.",
            "failure_kind": "missing_planner_role",
        }
        return {
            "status": "failed",
            "stop_reason": "planning_provider_review_missing_planner_role",
            "provider_stage_result": failure,
            "planning_provider_failure": failure,
        }

    review_payload = _planning_provider_review_payload(state)
    prompt_text = _planning_provider_review_prompt(state, review_payload=review_payload)
    run_dir = Path(str(state.get("run_dir") or ".forge-harness-runs"))
    out_dir = run_dir / "artifacts" / "planner_review"
    request = StageRequest(
        role_name="planner",
        role_config=planner_role,
        prompt_text=prompt_text,
        schema=_planning_provider_review_schema(),
        cwd=str(state.get("workspace_root") or ""),
        out_dir=str(out_dir),
    )
    run = get_provider(planner_role.provider).run(request)
    stage_result = {
        "stage_id": str(phase_spec.get("id") or "planner_review"),
        "stage_type": str(phase_spec.get("stage_type") or PLANNER_REVIEW_STAGE_TYPE),
        "role_name": "planner",
        "status": "success" if run.ok else "failed",
        "provider": run.provider,
        "model": run.model,
        "error": str(run.error or ""),
        "failure_kind": str(run.failure_kind or ""),
        "failure_summary": str(run.failure_summary or ""),
        "stdout_path": run.stdout_path,
        "stderr_path": run.stderr_path,
        "prompt_path": run.prompt_path,
        "schema_path": run.schema_path,
        "output_path": run.output_path,
    }
    if not run.ok or not isinstance(run.structured_output, dict):
        stop_reason = str(run.failure_kind or run.error or "planner_review_failed")
        return {
            "status": "failed",
            "stop_reason": f"planning_provider_review_failed:{stop_reason}",
            "provider_stage_result": stage_result,
            "planning_provider_failure": dict(stage_result),
        }

    review = {
        "stage_id": stage_result["stage_id"],
        "provider": run.provider,
        "model": run.model,
        **dict(run.structured_output),
    }
    review_delta = _normalized_provider_review_delta(review)
    review["provider_review_delta"] = review_delta
    stage_result["verdict"] = str(review.get("verdict") or "")
    stage_result["summary"] = str(review.get("summary") or "")
    stage_result["delta_status"] = str(review_delta.get("delta_status") or "")
    disagreement_count = (
        1
        if (
            str(review_delta.get("delta_status") or "").strip().lower() != "none"
            or str(review.get("verdict") or "").strip().lower()
            in {"accept_with_caveat", "revise"}
        )
        else 0
    )
    return {
        "status": "success",
        "stop_reason": None,
        "provider_stage_result": stage_result,
        "planning_provider_review": review,
        "planning_provider_review_delta": review_delta,
        "planning_provider_disagreement_count": disagreement_count,
    }


PLANNING_STAGE_REGISTRY: dict[str, StageHandler] = {
    "rubric_design_doc": _run_rubric_design_doc,
    "architecture_seam_decomposition": _run_architecture_seam_decomposition,
    "parallel_workstream_planning": _run_parallel_workstream_planning,
    "executable_slice_emission": _run_executable_slice_emission,
    PLANNER_REVIEW_STAGE_TYPE: _run_planner_review,
}


def _planning_graph_spec(state: Mapping[str, Any]) -> Mapping[str, Any]:
    graph_spec = state.get("strategy_graph_spec")
    if isinstance(graph_spec, Mapping):
        return graph_spec
    return {}


def _planning_phase_specs(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    graph_spec = _planning_graph_spec(state)
    raw_phases = graph_spec.get("phases")
    if not isinstance(raw_phases, list):
        strategy_spec = state.get("strategy_spec")
        raw_phases = (
            strategy_spec.get("phases") if isinstance(strategy_spec, Mapping) else []
        )
    return [
        _phase_spec(
            raw_phases[index - 1] if index - 1 < len(raw_phases) else {},
            expected_stage_type=expected_stage_type,
            index=index,
        )
        for index, expected_stage_type in enumerate(PLANNING_PHASE_ORDER, start=1)
    ]


def _planning_runtime_stage_specs(
    state: Mapping[str, Any],
    *,
    phase_specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    graph_spec = _planning_graph_spec(state)
    raw_stages = graph_spec.get("stages")
    compiled_stage_specs: list[dict[str, Any]] = []
    if isinstance(raw_stages, list):
        for index, stage in enumerate(raw_stages, start=1):
            if not isinstance(stage, Mapping):
                continue
            stage_type = str(stage.get("stage_type") or "").strip()
            if not stage_type:
                continue
            compiled_stage_specs.append(
                {
                    "id": str(stage.get("stage_id") or f"stage_{index}"),
                    "stage_type": stage_type,
                    "role_name": str(stage.get("role_name") or ""),
                }
            )
    if compiled_stage_specs:
        return compiled_stage_specs
    return [dict(phase_spec) for phase_spec in phase_specs]


def _planning_execution_contract(state: Mapping[str, Any]) -> dict[str, str]:
    graph_spec = _planning_graph_spec(state)
    planning_execution = graph_spec.get("planning_execution")
    if not isinstance(planning_execution, Mapping):
        strategy_spec = state.get("strategy_spec")
        if isinstance(strategy_spec, Mapping):
            planning_execution = strategy_spec.get("planning_execution")
    if isinstance(planning_execution, Mapping):
        mode = str(planning_execution.get("mode") or "").strip() or "graph_owned"
        provider_participation = str(
            planning_execution.get("provider_participation") or ""
        ).strip()
    else:
        mode = "graph_owned"
        provider_participation = ""
    if not provider_participation:
        provider_participation = (
            "planner_review" if mode == "graph_owned_with_planner_review" else "none"
        )
    return {
        "family": "planning_v1",
        "mode": mode,
        "provider_participation": provider_participation,
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
    execution_contract: Mapping[str, str],
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
    state["planning_execution_mode"] = str(execution_contract.get("mode") or "")
    state["planning_execution_contract"] = dict(execution_contract)
    state["planning_coverage_status"] = None
    state["planning_coverage_ledger"] = []
    state["planning_assumptions_register"] = []
    state["planning_uncovered_delta"] = []
    state["planning_provider_stage_results"] = []
    state["planning_provider_review"] = None
    state["planning_provider_review_delta"] = _empty_provider_review_delta(
        summary="Provider review was not exercised."
    )
    state["planning_provider_failure"] = None
    state["planning_provider_disagreement_count"] = 0
    state["planning_deterministic_planning_posture"] = PLANNING_DETERMINISTIC_POSTURE
    state["search_pass_count"] = 0
    state["inspected_file_count"] = 0
    state["discovery_budget_escalated"] = False


def _merge_repo_evidence_refs(
    current_refs: list[str],
    new_refs: list[str],
) -> list[str]:
    return _dedupe_strings(list(current_refs) + list(new_refs))


def _append_phase_result(
    state: MutableMapping[str, Any],
    phase_result: dict[str, Any],
) -> None:
    phase_results = list(state.get("planning_phase_results") or [])
    phase_results.append(phase_result)
    state["planning_phase_results"] = phase_results


def _planning_phase_id_map(
    phase_specs: list[dict[str, Any]],
) -> dict[str, str]:
    ordered_phase_ids = [
        str(phase_spec.get("id") or f"phase_{index}")
        for index, phase_spec in enumerate(phase_specs, start=1)
    ]
    fallback_phase_ids = {
        "design_doc": "design_doc",
        "seam_decomposition": "seam_decomposition",
        "parallel_planning": "parallel_planning",
        "slice_emission": "slice_emission",
    }
    phase_keys = tuple(fallback_phase_ids)
    return {
        phase_key: (
            ordered_phase_ids[index]
            if index < len(ordered_phase_ids)
            else fallback_phase_ids[phase_key]
        )
        for index, phase_key in enumerate(phase_keys)
    }


def _planning_item_ids(
    items: list[dict[str, Any]],
    *,
    primary_key: str,
) -> list[str]:
    ids: list[str] = []
    for item in items:
        item_id = str(item.get(primary_key) or item.get("id") or "").strip()
        if item_id:
            ids.append(item_id)
    return _dedupe_strings(ids)


def _planning_item_ref_list(
    items: list[dict[str, Any]],
    *,
    field_name: str,
) -> list[str]:
    refs: list[str] = []
    for item in items:
        refs.extend(_normalize_string_list(item.get(field_name) or []))
    return _dedupe_strings(refs)


def _coverage_id(index: int, dimension: str) -> str:
    return f"coverage-{index:02d}-{dimension}"


def _delta_id(index: int, dimension: str) -> str:
    return f"delta-{index:02d}-{dimension}"


def _assumption_kind(dimension: str) -> str:
    return {
        "problem_frame": "acceptance",
        "repo_surface": "environment",
        "seam_selection": "scope",
        "dependency_shape": "dependency",
        "execution_partitioning": "dependency",
        "acceptance_shape": "acceptance",
        "risk_and_unknowns": "risk",
    }.get(dimension, "scope")


def _coverage_gap_kind(
    *,
    dimension: str,
    status: str,
    terminal_status: str,
    has_assumptions: bool,
    has_grounding: bool,
) -> str:
    if dimension == "risk_and_unknowns" and has_assumptions:
        return "assumption_blocked"
    if dimension in {"problem_frame", "repo_surface"}:
        if terminal_status == "clarification_needed" or status == "partial":
            return "ambiguous_scope"
        return "missing_evidence"
    if dimension in {"seam_selection", "dependency_shape", "execution_partitioning"}:
        return "missing_structure" if has_grounding else "missing_evidence"
    if dimension == "acceptance_shape":
        return "missing_structure" if has_grounding else "missing_evidence"
    if has_assumptions:
        return "assumption_blocked"
    return "missing_evidence"


def _coverage_required_input(
    *,
    dimension: str,
    status: str,
    terminal_status: str,
) -> str:
    del status
    if dimension == "problem_frame":
        return "Explicit task-level acceptance criteria or success constraints."
    if dimension == "repo_surface":
        return "Concrete repository paths or seam hints that the planner can inspect."
    if dimension == "seam_selection":
        return "A declared architectural cut that can be decomposed into seams."
    if dimension == "dependency_shape":
        return "Dependency reasoning that explains how the selected seams interact."
    if dimension == "execution_partitioning":
        return "Parallel workstream boundaries grounded in the selected seams."
    if dimension == "acceptance_shape":
        return "Executable slices with explicit acceptance criteria."
    if terminal_status == "clarification_needed":
        return "Clarified risks, unknowns, or operator guidance for the blocked plan."
    return "Validated risk evidence or operator guidance for the remaining unknowns."


def _coverage_recommended_next_phase(
    *,
    dimension: str,
    terminal_status: str,
    phase_ids: Mapping[str, str],
) -> str:
    if dimension in {"problem_frame", "repo_surface", "risk_and_unknowns"}:
        return "clarify" if terminal_status != "success" else phase_ids["design_doc"]
    if dimension in {"seam_selection"}:
        return phase_ids["seam_decomposition"]
    if dimension in {"dependency_shape", "execution_partitioning"}:
        return phase_ids["parallel_planning"]
    return phase_ids["slice_emission"]


def _dimension_assumption_statement(
    *,
    dimension: str,
    status: str,
    terminal_status: str,
) -> str:
    if dimension == "problem_frame":
        if status == "partial":
            return (
                "Task-level acceptance criteria remain implicit and should be "
                "confirmed explicitly."
            )
        return (
            "The planning objective needs explicit success boundaries before the "
            "problem frame can be trusted."
        )
    if dimension == "repo_surface":
        return (
            "A concrete repository surface must be identified before coverage can "
            "be grounded."
        )
    if dimension == "seam_selection":
        return (
            "A credible architectural cut still needs to be confirmed before seam "
            "selection is reliable."
        )
    if dimension == "dependency_shape":
        return (
            "Dependency edges between the selected seams remain assumed rather than "
            "validated."
        )
    if dimension == "execution_partitioning":
        return (
            "Parallel workstream boundaries remain provisional until they are "
            "confirmed against the seam cut."
        )
    if dimension == "acceptance_shape":
        return (
            "Executable acceptance criteria still need to be confirmed for the "
            "planned delivery slices."
        )
    if terminal_status == "clarification_needed":
        return (
            "Residual risks and unknowns need operator clarification before the "
            "plan can be considered complete."
        )
    return (
        "Residual risks and unknowns remain unvalidated in the bounded planning "
        "pass."
    )


def _derive_planning_coverage(
    state: MutableMapping[str, Any],
    *,
    phase_specs: list[dict[str, Any]],
) -> None:
    phase_ids = _planning_phase_id_map(phase_specs)
    task_spec = dict(state.get("task_spec") or {})
    terminal_status = str(state.get("planning_terminal_status") or "").strip()
    clarification_requests = _list_of_dicts(state.get("clarification_requests") or [])
    repo_evidence_refs = _normalize_string_list(state.get("repo_evidence_refs") or [])
    seams = _list_of_dicts(state.get("planning_seams") or [])
    workstreams = _list_of_dicts(state.get("planning_workstreams") or [])
    slices = _list_of_dicts(state.get("planning_slices") or [])
    phase_results = _list_of_dicts(state.get("planning_phase_results") or [])

    seam_ids = _planning_item_ids(seams, primary_key="seam_id")
    workstream_ids = _planning_item_ids(workstreams, primary_key="workstream_id")
    slice_ids = _planning_item_ids(slices, primary_key="slice_id")
    acceptance_slice_ids = _dedupe_strings(
        [
            str(slice_record.get("slice_id") or slice_record.get("id") or "").strip()
            for slice_record in slices
            if _normalize_string_list(slice_record.get("acceptance_criteria") or [])
        ]
    )
    seam_evidence_refs = _planning_item_ref_list(seams, field_name="repo_evidence_refs")
    dependency_reasoning_present = any(
        _normalize_string_list(item.get("dependency_reasoning") or [])
        for item in [*workstreams, *slices]
    )
    ambiguity_flags = _dedupe_strings(
        [
            *(
                flag
                for phase_result in phase_results
                for flag in _normalize_string_list(
                    phase_result.get("ambiguity_flags") or []
                )
            ),
            *(
                flag
                for item in [*seams, *workstreams, *slices]
                for flag in _normalize_string_list(item.get("ambiguity_flags") or [])
            ),
        ]
    )
    objective_present = bool(str(task_spec.get("objective") or "").strip())
    explicit_acceptance = bool(
        _normalize_string_list(task_spec.get("acceptance") or [])
    )

    row_specs: list[dict[str, Any]] = []

    problem_frame_refs = repo_evidence_refs[:1]
    problem_frame_source_phase_ids = [phase_ids["design_doc"]]
    if acceptance_slice_ids:
        problem_frame_source_phase_ids.append(phase_ids["slice_emission"])
    if (
        objective_present
        and explicit_acceptance
        and (problem_frame_refs or acceptance_slice_ids)
    ):
        row_specs.append(
            {
                "dimension": "problem_frame",
                "status": "covered",
                "summary": (
                    "The task objective is grounded and explicit acceptance "
                    "criteria define the problem frame."
                ),
                "evidence_refs": problem_frame_refs,
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": acceptance_slice_ids,
                "source_phase_ids": _dedupe_strings(problem_frame_source_phase_ids),
            }
        )
    elif objective_present and (problem_frame_refs or acceptance_slice_ids):
        row_specs.append(
            {
                "dimension": "problem_frame",
                "status": "partial",
                "summary": (
                    "The objective is grounded, but task-level acceptance criteria "
                    "are inferred rather than declared explicitly."
                ),
                "evidence_refs": problem_frame_refs,
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": acceptance_slice_ids,
                "source_phase_ids": _dedupe_strings(problem_frame_source_phase_ids),
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "problem_frame",
                "status": "uncovered",
                "summary": (
                    "The planner could not establish a grounded problem frame from "
                    "the available task inputs."
                ),
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["design_doc"]],
            }
        )

    if repo_evidence_refs:
        row_specs.append(
            {
                "dimension": "repo_surface",
                "status": "covered",
                "summary": (
                    f"The planner grounded the plan in {len(repo_evidence_refs)} "
                    "repository evidence reference(s)."
                ),
                "evidence_refs": repo_evidence_refs,
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["design_doc"]],
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "repo_surface",
                "status": "uncovered",
                "summary": (
                    "No concrete repository evidence was established for the "
                    "planning run."
                ),
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["design_doc"]],
            }
        )

    if seam_ids:
        row_specs.append(
            {
                "dimension": "seam_selection",
                "status": "covered",
                "summary": (
                    f"The runtime derived {len(seam_ids)} architectural seam(s) in "
                    "canonical order."
                ),
                "evidence_refs": seam_evidence_refs,
                "seam_ids": seam_ids,
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["seam_decomposition"]],
            }
        )
    elif repo_evidence_refs:
        row_specs.append(
            {
                "dimension": "seam_selection",
                "status": "partial",
                "summary": (
                    "Repository evidence was inspected, but the plan did not land "
                    "a credible seam cut."
                ),
                "evidence_refs": repo_evidence_refs[:2],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["seam_decomposition"]],
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "seam_selection",
                "status": "uncovered",
                "summary": "No architectural seam selection was established.",
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["seam_decomposition"]],
            }
        )

    dependency_source_phase_ids = [phase_ids["parallel_planning"]]
    if slice_ids:
        dependency_source_phase_ids.append(phase_ids["slice_emission"])
    if dependency_reasoning_present and (workstream_ids or slice_ids):
        row_specs.append(
            {
                "dimension": "dependency_shape",
                "status": "covered",
                "summary": (
                    "Dependency reasoning is attached to the planned workstreams "
                    "or slices."
                ),
                "evidence_refs": [],
                "seam_ids": seam_ids,
                "workstream_ids": workstream_ids,
                "slice_ids": slice_ids,
                "source_phase_ids": _dedupe_strings(dependency_source_phase_ids),
            }
        )
    elif seam_ids or workstream_ids or slice_ids:
        row_specs.append(
            {
                "dimension": "dependency_shape",
                "status": "partial",
                "summary": (
                    "The plan established structure, but dependency edges remain "
                    "implicit."
                ),
                "evidence_refs": [],
                "seam_ids": seam_ids,
                "workstream_ids": workstream_ids,
                "slice_ids": slice_ids,
                "source_phase_ids": _dedupe_strings(
                    [phase_ids["seam_decomposition"], *dependency_source_phase_ids]
                ),
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "dependency_shape",
                "status": "uncovered",
                "summary": "No dependency shape was established for the plan.",
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["parallel_planning"]],
            }
        )

    if workstream_ids:
        row_specs.append(
            {
                "dimension": "execution_partitioning",
                "status": "covered",
                "summary": (
                    f"The runtime partitioned execution into {len(workstream_ids)} "
                    "parallel workstream(s)."
                ),
                "evidence_refs": [],
                "seam_ids": seam_ids,
                "workstream_ids": workstream_ids,
                "slice_ids": [],
                "source_phase_ids": [phase_ids["parallel_planning"]],
            }
        )
    elif seam_ids:
        row_specs.append(
            {
                "dimension": "execution_partitioning",
                "status": "partial",
                "summary": (
                    "Architectural seams exist, but parallel workstream boundaries "
                    "were not finalized."
                ),
                "evidence_refs": [],
                "seam_ids": seam_ids,
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["parallel_planning"]],
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "execution_partitioning",
                "status": "uncovered",
                "summary": "No execution partitioning was established.",
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["parallel_planning"]],
            }
        )

    if acceptance_slice_ids:
        row_specs.append(
            {
                "dimension": "acceptance_shape",
                "status": "covered",
                "summary": (
                    "Executable slice acceptance criteria were emitted for the "
                    "planned work."
                ),
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": workstream_ids,
                "slice_ids": acceptance_slice_ids,
                "source_phase_ids": [phase_ids["slice_emission"]],
            }
        )
    elif slice_ids or workstream_ids:
        row_specs.append(
            {
                "dimension": "acceptance_shape",
                "status": "partial",
                "summary": (
                    "Delivery structure exists, but explicit slice-level acceptance "
                    "criteria remain incomplete."
                ),
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": workstream_ids,
                "slice_ids": slice_ids,
                "source_phase_ids": [phase_ids["slice_emission"]],
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "acceptance_shape",
                "status": "uncovered",
                "summary": "No executable acceptance shape was established.",
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["slice_emission"]],
            }
        )

    has_risk_grounding = bool(
        repo_evidence_refs or seam_ids or workstream_ids or slice_ids
    )
    if (
        terminal_status == "success"
        and not ambiguity_flags
        and not clarification_requests
    ):
        row_specs.append(
            {
                "dimension": "risk_and_unknowns",
                "status": "covered",
                "summary": (
                    "No unresolved ambiguity flags were raised inside the bounded "
                    "planning pass."
                ),
                "evidence_refs": repo_evidence_refs[:1],
                "seam_ids": seam_ids[:1],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["design_doc"]],
            }
        )
    elif has_risk_grounding:
        row_specs.append(
            {
                "dimension": "risk_and_unknowns",
                "status": "partial",
                "summary": (
                    "Residual ambiguity or blocked follow-up remains in the plan's "
                    "risk surface."
                ),
                "evidence_refs": repo_evidence_refs[:1],
                "seam_ids": seam_ids[:1],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["design_doc"]],
            }
        )
    else:
        row_specs.append(
            {
                "dimension": "risk_and_unknowns",
                "status": "uncovered",
                "summary": "The runtime could not ground a credible risk surface.",
                "evidence_refs": [],
                "seam_ids": [],
                "workstream_ids": [],
                "slice_ids": [],
                "source_phase_ids": [phase_ids["design_doc"]],
            }
        )

    if [row["dimension"] for row in row_specs] != list(PLANNING_COVERAGE_DIMENSIONS):
        raise AssertionError("planning coverage rows must follow canonical order")

    coverage_rows: list[dict[str, Any]] = []
    assumptions_register: list[dict[str, Any]] = []
    for index, row_spec in enumerate(row_specs, start=1):
        dimension = str(row_spec["dimension"])
        status = str(row_spec["status"])
        evidence_refs = _dedupe_strings(list(row_spec.get("evidence_refs") or []))
        row_seam_ids = _dedupe_strings(list(row_spec.get("seam_ids") or []))
        row_workstream_ids = _dedupe_strings(list(row_spec.get("workstream_ids") or []))
        row_slice_ids = _dedupe_strings(list(row_spec.get("slice_ids") or []))
        source_phase_ids = _dedupe_strings(list(row_spec.get("source_phase_ids") or []))
        coverage_id = _coverage_id(index, dimension)
        assumption_ids: list[str] = []

        if status in {"partial", "uncovered"}:
            statement = _dimension_assumption_statement(
                dimension=dimension,
                status=status,
                terminal_status=terminal_status,
            )
            assumption_id = _stable_id(
                "assumption", len(assumptions_register) + 1, statement
            )
            assumption_ids.append(assumption_id)
            assumptions_register.append(
                {
                    "assumption_id": assumption_id,
                    "statement": statement,
                    "kind": _assumption_kind(dimension),
                    "status": "active",
                    "linked_coverage_ids": [coverage_id],
                    "evidence_refs": list(evidence_refs),
                    "source_phase_id": (
                        source_phase_ids[0]
                        if source_phase_ids
                        else phase_ids["design_doc"]
                    ),
                }
            )

        coverage_rows.append(
            {
                "coverage_id": coverage_id,
                "dimension": dimension,
                "status": status,
                "summary": str(row_spec["summary"]),
                "evidence_refs": evidence_refs,
                "seam_ids": row_seam_ids,
                "workstream_ids": row_workstream_ids,
                "slice_ids": row_slice_ids,
                "assumption_ids": assumption_ids,
                "source_phase_ids": source_phase_ids,
            }
        )

    uncovered_delta: list[dict[str, Any]] = []
    for index, coverage_row in enumerate(coverage_rows, start=1):
        status = str(coverage_row.get("status") or "")
        if status not in {"partial", "uncovered"}:
            continue
        dimension = str(coverage_row["dimension"])
        has_grounding = bool(
            coverage_row.get("evidence_refs")
            or coverage_row.get("seam_ids")
            or coverage_row.get("workstream_ids")
            or coverage_row.get("slice_ids")
        )
        blocking_assumption_ids = _normalize_string_list(
            coverage_row.get("assumption_ids") or []
        )
        uncovered_delta.append(
            {
                "delta_id": _delta_id(index, dimension),
                "coverage_id": str(coverage_row["coverage_id"]),
                "dimension": dimension,
                "gap_kind": _coverage_gap_kind(
                    dimension=dimension,
                    status=status,
                    terminal_status=terminal_status,
                    has_assumptions=bool(blocking_assumption_ids),
                    has_grounding=has_grounding,
                ),
                "required_input": _coverage_required_input(
                    dimension=dimension,
                    status=status,
                    terminal_status=terminal_status,
                ),
                "recommended_next_phase": _coverage_recommended_next_phase(
                    dimension=dimension,
                    terminal_status=terminal_status,
                    phase_ids=phase_ids,
                ),
                "blocking_assumption_ids": blocking_assumption_ids,
            }
        )

    state["planning_coverage_status"] = terminal_status or None
    state["planning_coverage_ledger"] = coverage_rows
    state["planning_assumptions_register"] = assumptions_register
    state["planning_uncovered_delta"] = uncovered_delta


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
    state["planning_terminal_status"] = terminal_status
    state["planning_coverage_status"] = terminal_status
    state["planning_stop_reason"] = stop_reason
    state["stop_reason"] = stop_reason
    state["run_verdict"] = terminal_status
    state["content_verdict"] = terminal_status
    state["summary_text"] = summary_by_status[terminal_status]


def _tokenize(value: Any) -> list[str]:
    tokens = [
        token
        for token in _TOKEN_RE.findall(str(value or "").lower())
        if len(token) >= 3 and token not in _TOKEN_STOPWORDS
    ]
    return list(dict.fromkeys(tokens))


def _planning_query_tokens(
    task_spec: Mapping[str, Any],
    strategy_spec: Mapping[str, Any],
) -> list[str]:
    values: list[Any] = [
        task_spec.get("objective"),
        task_spec.get("context"),
        task_spec.get("notes"),
        strategy_spec.get("runtime_target"),
    ]
    values.extend(task_spec.get("acceptance") or [])
    values.extend(task_spec.get("constraints") or [])
    values.extend(task_spec.get("files_hint") or [])
    tokens: list[str] = []
    for value in values:
        tokens.extend(_tokenize(value))
    return list(dict.fromkeys(tokens))


def _score_path(path: str, *, query_tokens: list[str]) -> int:
    normalized = path.lower()
    score = 0
    for token in query_tokens:
        if token in normalized:
            score += 10
    if normalized.endswith(".py"):
        score += 2
    if normalized.endswith(".md"):
        score += 1
    return score


def _rank_paths(paths: list[str], *, query_tokens: list[str]) -> list[str]:
    return sorted(
        _dedupe_strings(paths),
        key=lambda path: (-_score_path(path, query_tokens=query_tokens), path),
    )


def _workspace_root(state: Mapping[str, Any]) -> Path:
    return Path(str(state.get("workspace_root") or ".")).resolve()


def _direct_workspace_matches(
    state: Mapping[str, Any],
    *,
    files_hint: list[str],
) -> list[str]:
    workspace_root = _workspace_root(state)
    matches: list[str] = []
    for pattern in files_hint:
        matches.extend(workspace_glob_paths(workspace_root, pattern))
    return _dedupe_strings(matches)


def _discovered_workspace_matches(
    state: Mapping[str, Any],
    *,
    selected_paths: list[str],
) -> list[str]:
    workspace_root = _workspace_root(state)
    discovered: list[str] = []
    roots = sorted(
        {
            str(Path(path).parent)
            for path in selected_paths
            if "/" in path and str(Path(path).parent) not in {"", "."}
        }
    )
    for root in roots:
        root_path = workspace_root / root
        if not root_path.is_dir():
            continue
        for pattern in (
            "**/*.py",
            "**/*.md",
            "**/*.yaml",
            "**/*.yml",
            "**/*.ts",
            "**/*.tsx",
        ):
            discovered.extend(workspace_glob_paths(workspace_root, f"{root}/{pattern}"))
    return _dedupe_strings(discovered)


def _read_workspace_evidence(
    state: Mapping[str, Any],
    *,
    candidate_paths: list[str],
    query_tokens: list[str],
) -> dict[str, str]:
    ranked = _rank_paths(candidate_paths, query_tokens=query_tokens)
    evidence: dict[str, str] = {}
    remaining_bytes = PLANNING_READ_BYTES_LIMIT
    for relative_path in ranked:
        if len(evidence) >= PLANNING_READ_LIMIT or remaining_bytes <= 0:
            break
        path = _workspace_root(state) / relative_path
        if not path.is_file():
            continue
        read_size = min(remaining_bytes, max(1, path.stat().st_size))
        text = read_workspace_text(
            _workspace_root(state), relative_path, max_bytes=read_size
        )
        evidence[relative_path] = text
        remaining_bytes -= len(text.encode("utf-8"))
    return evidence


def _path_cluster(path: str) -> tuple[str, str]:
    parts = Path(path).parts
    parent_parts = parts[:-1]
    if len(parent_parts) >= 2 and parts[0] == ".github" and parts[1] == "workflows":
        return ("workflow-boundary", ".github/workflows")
    if (
        len(parent_parts) >= 2
        and parts[0] == "docs"
        and parts[1]
        in {
            "adr",
            "planning",
        }
    ):
        return ("workflow-boundary", "/".join(parts[:2]))
    if len(parent_parts) >= 2 and parts[0] in {"anvil", "tests", "examples"}:
        return ("module-package", "/".join(parts[:2]))
    if len(parent_parts) >= 3 and parent_parts[1] in {"src", "app", "lib"}:
        return ("module-package", "/".join(parent_parts[: min(4, len(parent_parts))]))
    if len(parent_parts) >= 2:
        return ("module-package", "/".join(parent_parts[:2]))
    if parent_parts:
        return ("integration-seam", "/".join(parent_parts))
    return ("integration-seam", path)


def _primary_cut_candidates(
    *,
    candidate_paths: list[str],
    evidence_by_path: Mapping[str, str],
    query_tokens: list[str],
) -> list[dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    for path in _dedupe_strings(candidate_paths):
        kind, label = _path_cluster(path)
        cluster = clusters.setdefault(
            label,
            {
                "kind": kind,
                "label": label,
                "supporting_paths": [],
                "matched_query_tokens": set(),
                "grounded_paths": set(),
            },
        )
        cluster["supporting_paths"].append(path)
        haystack = " ".join(
            [path.lower(), str(evidence_by_path.get(path) or "").lower()]
        )
        matched_tokens = {token for token in query_tokens if token in haystack}
        if matched_tokens:
            cluster["matched_query_tokens"].update(matched_tokens)
            cluster["grounded_paths"].add(path)

    priority = {
        "workflow-boundary": 0,
        "module-package": 1,
        "integration-seam": 2,
    }
    candidates: list[dict[str, Any]] = []
    for cluster in clusters.values():
        supporting_paths = _dedupe_strings(cluster["supporting_paths"])
        matched_query_tokens = sorted(cluster["matched_query_tokens"])
        grounded_paths = sorted(cluster["grounded_paths"])
        signal_labels: list[str] = []
        if len(supporting_paths) >= 2:
            signal_labels.append("multi_path_cluster")
        if len(matched_query_tokens) >= 2:
            signal_labels.append("task_token_grounding")
        if len(grounded_paths) >= 2:
            signal_labels.append("cross_file_grounding")
        candidates.append(
            {
                "kind": cluster["kind"],
                "label": cluster["label"],
                "supporting_paths": supporting_paths,
                "matched_query_tokens": matched_query_tokens,
                "grounded_paths": grounded_paths,
                "signal_labels": signal_labels,
                "signal_count": len(signal_labels),
            }
        )

    return sorted(
        candidates,
        key=lambda item: (
            -int(item["signal_count"]),
            -len(item["grounded_paths"]),
            -len(item["supporting_paths"]),
            priority.get(str(item["kind"]), 99),
            str(item["label"]),
        ),
    )


def _primary_cut_summary(primary_cut: Mapping[str, Any]) -> str:
    supporting_paths = list(primary_cut.get("supporting_paths") or [])
    signal_labels = list(primary_cut.get("signal_labels") or [])
    summary = (
        f"Selected primary cut `{primary_cut.get('label')}` "
        f"({primary_cut.get('kind')}) from {len(supporting_paths)} supporting "
        f"path(s) with {len(signal_labels)} credibility signal(s)."
    )
    if supporting_paths:
        summary = f"{summary} Anchors: {', '.join(supporting_paths[:3])}."
    return summary


def _primary_cut_clarification_question(
    *,
    primary_cut: Mapping[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> tuple[str, str]:
    if primary_cut is not None:
        label = str(primary_cut.get("label") or "the current repo surface")
        if len(candidates) > 1:
            alternate = str(candidates[1].get("label") or "another repo surface")
            return (
                f"Should the planner stay focused on `{label}` or pivot to `{alternate}` for this slice?",
                (
                    "The bounded repo evidence suggests a credible primary cut, but "
                    "the downstream structure is not yet explicit enough to continue "
                    "without operator confirmation."
                ),
            )
        return (
            f"Should the planner stay focused on `{label}`, or is another repository surface in scope for this slice?",
            (
                "The bounded repo evidence suggests a credible primary cut, but the "
                "requested implementation slice still needs confirmation before "
                "continuing."
            ),
        )
    if candidates:
        candidate_labels = [
            f"`{candidate['label']}`"
            for candidate in candidates[:2]
            if candidate.get("label")
        ]
        if candidate_labels:
            return (
                f"Which repository surface is the intended planning slice: {' or '.join(candidate_labels)}?",
                (
                    "The bounded repo evidence surfaced multiple plausible cuts, but "
                    "none passed the frozen credibility threshold."
                ),
            )
    return (
        "Which concrete repository path or seam should the planning package inspect first?",
        "The current files_hint slice did not isolate a credible first cut.",
    )


def _cluster_title(label: str) -> str:
    parts = [part for part in re.split(r"[/_-]+", label) if part]
    if not parts:
        return "Repo Surface"
    return " ".join(part.capitalize() for part in parts[-2:])


def _objective_is_out_of_corpus(task_spec: Mapping[str, Any]) -> bool:
    values = [
        task_spec.get("objective"),
        task_spec.get("context"),
        task_spec.get("notes"),
    ]
    return any(_OUT_OF_CORPUS_RE.search(str(value or "")) for value in values)


def _seam_paths(
    *,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seams: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        signal_count = int(candidate.get("signal_count") or 0)
        if index == 1 and signal_count < 2:
            continue
        if index > 1 and signal_count < 1:
            continue
        seam_paths = _dedupe_strings(list(candidate.get("supporting_paths") or []))
        if not seam_paths:
            continue
        label = str(candidate.get("label") or f"repo-surface-{index}")
        seam_id = _stable_id("seam", index, label)
        seams.append(
            {
                "id": seam_id,
                "seam_id": seam_id,
                "title": f"{_cluster_title(label)} Seam",
                "summary": (
                    f"Ground the bounded plan in `{label}` using "
                    f"{len(seam_paths)} repo-backed anchor path(s)."
                ),
                "paths": seam_paths,
                "repo_evidence_refs": seam_paths,
                "dependency_reasoning": [
                    f"Derived from the repo-backed primary-cut candidate `{label}`."
                ],
                "ambiguity_flags": [],
                "candidate_label": label,
            }
        )
        if len(seams) >= 3:
            break
    return seams


def _workstreams_for_seams(seams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workstreams: list[dict[str, Any]] = []
    previous_workstream_id: str | None = None
    for index, seam in enumerate(seams, start=1):
        seam_id = str(seam.get("seam_id") or seam.get("id") or "").strip()
        label = str(seam.get("candidate_label") or seam.get("title") or seam_id)
        if not seam_id:
            continue
        workstream_id = _stable_id("workstream", index, label)
        dependency_reasoning = [f"Grounded in `{seam_id}`."]
        summary = f"Translate `{label}` into a bounded implementation workstream."
        depends_on_workstream_ids: list[str] = []
        if previous_workstream_id:
            depends_on_workstream_ids.append(previous_workstream_id)
            dependency_reasoning.append(
                f"Sequence this after `{previous_workstream_id}` to preserve the repo-derived execution order."
            )
            summary = (
                f"Translate `{label}` into a bounded implementation workstream after "
                f"`{previous_workstream_id}`."
            )
        workstreams.append(
            {
                "id": workstream_id,
                "workstream_id": workstream_id,
                "title": f"{_cluster_title(label)} Workstream",
                "summary": summary,
                "seam_ids": [seam_id],
                "worktree_recommended": True,
                "dependency_reasoning": dependency_reasoning,
                "ambiguity_flags": [],
                "depends_on_workstream_ids": depends_on_workstream_ids,
                "candidate_label": label,
            }
        )
        previous_workstream_id = workstream_id
    return workstreams


def _slices_for_workstreams(
    workstreams: list[dict[str, Any]],
    *,
    seams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    seams_by_id = {
        str(seam.get("seam_id") or seam.get("id") or ""): seam for seam in seams
    }
    for index, workstream in enumerate(workstreams, start=1):
        workstream_id = str(
            workstream.get("workstream_id") or workstream.get("id") or ""
        ).strip()
        seam_ids = _normalize_string_list(workstream.get("seam_ids") or [])
        if not workstream_id or not seam_ids:
            continue
        label = str(
            workstream.get("candidate_label")
            or workstream.get("title")
            or workstream_id
        )
        anchor_paths: list[str] = []
        for seam_id in seam_ids:
            seam = seams_by_id.get(seam_id) or {}
            anchor_paths.extend(_normalize_string_list(seam.get("paths") or []))
        anchor_paths = _dedupe_strings(anchor_paths)
        slice_id = _stable_id("slice", index, label)
        slices.append(
            {
                "id": slice_id,
                "slice_id": slice_id,
                "title": f"{_cluster_title(label)} Slice",
                "summary": (
                    f"Define the next executable change slice for `{label}` using "
                    "the repo-backed anchors from its parent workstream."
                ),
                "workstream_id": workstream_id,
                "seam_ids": seam_ids,
                "acceptance_criteria": [
                    (
                        f"Anchor the slice to concrete repo paths such as "
                        f"{', '.join(anchor_paths[:2]) or label}."
                    ),
                    f"Keep the execution scope bounded to the `{label}` surface and its declared workstream dependencies.",
                ],
                "dependency_reasoning": [f"Implements `{workstream_id}`."],
                "ambiguity_flags": [],
                "candidate_label": label,
            }
        )
    return slices


def _clarification_payload(
    *,
    phase_id: str,
    stop_reason: str,
    summary: str,
    repo_evidence_refs: list[str],
    search_pass_count: int,
    inspected_file_count: int,
    discovery_budget_escalated: bool,
    question: str,
    rationale: str,
) -> dict[str, Any]:
    return {
        "status": "clarification_needed",
        "stop_reason": stop_reason,
        "summary": summary,
        "repo_evidence_refs": repo_evidence_refs,
        "search_pass_count": search_pass_count,
        "inspected_file_count": inspected_file_count,
        "discovery_budget_escalated": discovery_budget_escalated,
        "clarification_requests": [
            {
                "id": _stable_id("clarify", 1, phase_id),
                "question": question,
                "rationale": rationale,
            }
        ],
    }


def _failed_payload(
    *,
    stop_reason: str,
    summary: str,
    repo_evidence_refs: list[str],
    search_pass_count: int,
    inspected_file_count: int,
    discovery_budget_escalated: bool,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "stop_reason": stop_reason,
        "summary": summary,
        "repo_evidence_refs": repo_evidence_refs,
        "search_pass_count": search_pass_count,
        "inspected_file_count": inspected_file_count,
        "discovery_budget_escalated": discovery_budget_escalated,
    }


def _derive_live_phase_payloads(
    state: Mapping[str, Any],
    *,
    task_spec: Mapping[str, Any],
    strategy_spec: Mapping[str, Any],
    phases: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    run_mode = "deterministic-live"
    design_phase = phases[0]
    seam_phase = phases[1]
    workstream_phase = phases[2]
    slice_phase = phases[3]

    files_hint = _normalize_string_list(task_spec.get("files_hint") or [])
    direct_matches = _direct_workspace_matches(state, files_hint=files_hint)
    query_tokens = _planning_query_tokens(task_spec, strategy_spec)

    if _objective_is_out_of_corpus(task_spec):
        return (
            {
                str(design_phase["id"]): _failed_payload(
                    stop_reason="planning_request_out_of_corpus",
                    summary=(
                        "The request requires a broader planning corpus than the "
                        "bounded C1 planner supports."
                    ),
                    repo_evidence_refs=[],
                    search_pass_count=0,
                    inspected_file_count=0,
                    discovery_budget_escalated=False,
                )
            },
            run_mode,
        )

    if not direct_matches:
        return (
            {
                str(design_phase["id"]): _clarification_payload(
                    phase_id=str(design_phase["id"]),
                    stop_reason="files_hint_unresolved",
                    summary=(
                        "The provided files_hint did not resolve to any workspace "
                        "paths within the bounded planning budget."
                    ),
                    repo_evidence_refs=[],
                    search_pass_count=1 if files_hint else 0,
                    inspected_file_count=0,
                    discovery_budget_escalated=False,
                    question=(
                        "Which concrete repository path or seam should the planning "
                        "package inspect first?"
                    ),
                    rationale=(
                        "The current files_hint slice did not map to any files in the "
                        "workspace snapshot."
                    ),
                )
            },
            run_mode,
        )

    ranked_direct = _rank_paths(direct_matches, query_tokens=query_tokens)
    selected_paths = ranked_direct[:PLANNING_MATCH_LIMIT]
    discovery_budget_escalated = len(ranked_direct) > PLANNING_MATCH_LIMIT
    search_pass_count = 1

    discovered_paths: list[str] = []
    if len(selected_paths) < PLANNING_MATCH_LIMIT:
        discovered_paths = [
            path
            for path in _discovered_workspace_matches(
                state, selected_paths=selected_paths
            )
            if path not in selected_paths
        ]
        if discovered_paths:
            discovery_budget_escalated = True
            search_pass_count = 2
            selected_paths = _rank_paths(
                selected_paths + discovered_paths,
                query_tokens=query_tokens,
            )[:PLANNING_MATCH_LIMIT]

    if len(selected_paths) > PLANNING_MATCH_LIMIT:
        return (
            {
                str(design_phase["id"]): _failed_payload(
                    stop_reason="planning_evidence_budget_exceeded",
                    summary=(
                        "Bounded evidence discovery exceeded the frozen path budget "
                        "before a credible primary cut could be chosen."
                    ),
                    repo_evidence_refs=selected_paths[:PLANNING_MATCH_LIMIT],
                    search_pass_count=search_pass_count,
                    inspected_file_count=0,
                    discovery_budget_escalated=True,
                )
            },
            run_mode,
        )

    evidence_by_path = _read_workspace_evidence(
        state,
        candidate_paths=selected_paths,
        query_tokens=query_tokens,
    )
    inspected_file_count = len(evidence_by_path)
    primary_cut_candidates = _primary_cut_candidates(
        candidate_paths=selected_paths,
        evidence_by_path=evidence_by_path,
        query_tokens=query_tokens,
    )
    primary_cut = (
        dict(primary_cut_candidates[0])
        if primary_cut_candidates
        and int(primary_cut_candidates[0]["signal_count"]) >= 2
        else None
    )
    clarification_question, clarification_rationale = (
        _primary_cut_clarification_question(
            primary_cut=primary_cut,
            candidates=primary_cut_candidates,
        )
    )
    primary_cut_summary = (
        _primary_cut_summary(primary_cut) if primary_cut is not None else ""
    )

    if primary_cut is None:
        tentative_summary = (
            _primary_cut_summary(primary_cut_candidates[0])
            if primary_cut_candidates
            else ""
        )
        return (
            {
                str(design_phase["id"]): {
                    **_clarification_payload(
                        phase_id=str(design_phase["id"]),
                        stop_reason="primary_cut_not_credible",
                        summary=(
                            "The planner could not choose a credible primary cut from "
                            "the bounded workspace evidence."
                        ),
                        repo_evidence_refs=selected_paths,
                        search_pass_count=search_pass_count,
                        inspected_file_count=inspected_file_count,
                        discovery_budget_escalated=discovery_budget_escalated,
                        question=clarification_question,
                        rationale=clarification_rationale,
                    ),
                    "primary_cut_summary": tentative_summary,
                }
            },
            run_mode,
        )

    seams = _seam_paths(candidates=primary_cut_candidates)
    if not seams:
        return (
            {
                str(design_phase["id"]): _clarification_payload(
                    phase_id=str(design_phase["id"]),
                    stop_reason="primary_cut_not_credible",
                    summary=(
                        "The planner found a credible primary cut, but the bounded "
                        "workspace evidence was still too weak to emit truthful "
                        "downstream planning structure."
                    ),
                    repo_evidence_refs=selected_paths,
                    search_pass_count=search_pass_count,
                    inspected_file_count=inspected_file_count,
                    discovery_budget_escalated=discovery_budget_escalated,
                    question=clarification_question,
                    rationale=clarification_rationale,
                )
                | {"primary_cut_summary": primary_cut_summary}
            },
            run_mode,
        )

    if len(seams) > 3:
        return (
            {
                str(design_phase["id"]): _failed_payload(
                    stop_reason="planning_seam_clusters_exceeded",
                    summary=(
                        "Bounded evidence discovery produced more seam clusters than "
                        "the frozen planning contract allows."
                    ),
                    repo_evidence_refs=selected_paths,
                    search_pass_count=search_pass_count,
                    inspected_file_count=inspected_file_count,
                    discovery_budget_escalated=discovery_budget_escalated,
                )
            },
            run_mode,
        )

    workstreams = _workstreams_for_seams(seams)
    slices = _slices_for_workstreams(workstreams, seams=seams)

    repo_evidence_refs = _dedupe_strings(
        (["PLAN.md"] if (_workspace_root(state) / "PLAN.md").is_file() else [])
        + selected_paths
        + [path for seam in seams for path in seam.get("paths", [])]
    )
    live_payloads: dict[str, dict[str, Any]] = {
        str(design_phase["id"]): {
            "summary": (
                "The planning objective is coherent, bounded to the workspace, and "
                "anchored to a credible repo-derived primary cut."
            ),
            "repo_evidence_refs": repo_evidence_refs,
            "search_pass_count": search_pass_count,
            "inspected_file_count": inspected_file_count,
            "discovery_budget_escalated": discovery_budget_escalated,
            "primary_cut_summary": primary_cut_summary,
        },
        str(seam_phase["id"]): {
            "summary": (
                f"Derived {len(seams)} architectural seam(s) from bounded workspace "
                "evidence."
            ),
            "repo_evidence_refs": _dedupe_strings(
                [path for seam in seams for path in seam.get("paths", [])]
            ),
            "planning_seams": seams,
        },
        str(workstream_phase["id"]): {
            "summary": (
                f"Prepared {len(workstreams)} parallel workstream(s) grounded in the "
                "derived seams."
            ),
            "planning_workstreams": workstreams,
        },
        str(slice_phase["id"]): {
            "summary": (
                f"Emitted {len(slices)} executable slice(s) with concrete acceptance "
                "criteria."
            ),
            "planning_slices": slices,
        },
    }
    return live_payloads, run_mode


def execute_planning_runtime(state: HarnessState) -> HarnessState:
    mutable_state = state
    task_spec = dict(mutable_state.get("task_spec") or {})
    strategy_spec = dict(mutable_state.get("strategy_spec") or {})
    phase_specs = _planning_phase_specs(mutable_state)
    runtime_stage_specs = _planning_runtime_stage_specs(
        mutable_state, phase_specs=phase_specs
    )
    policy_versions = _lookup_planning_policy_versions(strategy_spec)
    execution_contract = _planning_execution_contract(mutable_state)

    _seed_planning_state(
        mutable_state,
        policy_versions=policy_versions,
        execution_contract=execution_contract,
    )

    fixture_mode = _task_terminal_mode(task_spec)
    live_phase_payloads: dict[str, dict[str, Any]] = {}
    run_mode = "fixture-backed" if fixture_mode else "deterministic-live"
    if fixture_mode:
        live_phase_payloads = {}
    else:
        live_phase_payloads, run_mode = _derive_live_phase_payloads(
            mutable_state,
            task_spec=task_spec,
            strategy_spec=strategy_spec,
            phases=phase_specs,
        )

    run_details = dict(mutable_state.get("run_details") or {})
    run_details["planning_run_mode"] = run_mode
    run_details["planning_execution_mode"] = execution_contract["mode"]
    run_details["provider_participation"] = execution_contract["provider_participation"]
    mutable_state["run_details"] = run_details

    def _payload_resolver(
        runtime_state: MutableMapping[str, Any], phase_spec: dict[str, Any]
    ) -> dict[str, Any]:
        stage_type = str(phase_spec["stage_type"])
        if stage_type == PLANNER_REVIEW_STAGE_TYPE:
            return {}
        if fixture_mode:
            payload = _phase_payload(
                strategy_spec,
                phase_id=str(phase_spec["id"]),
                stage_type=stage_type,
            )
            payload = dict(payload)
            if stage_type == PLANNING_PHASE_ORDER[0]:
                payload = (
                    _task_terminal_override(
                        task_spec,
                        phase_id=str(phase_spec["id"]),
                        payload=payload,
                    )
                    or payload
                )
            return payload
        return dict(live_phase_payloads.get(str(phase_spec["id"])) or {})

    def _observe_outcome(
        runtime_state: MutableMapping[str, Any],
        phase_spec: dict[str, Any],
        outcome: dict[str, Any],
    ) -> None:
        mutable_state["repo_evidence_refs"] = _merge_repo_evidence_refs(
            list(runtime_state.get("repo_evidence_refs") or []),
            list(outcome.get("repo_evidence_refs") or []),
        )
        if outcome.get("planning_seams"):
            runtime_state["planning_seams"] = list(outcome["planning_seams"])
        if outcome.get("planning_workstreams"):
            runtime_state["planning_workstreams"] = list(
                outcome["planning_workstreams"]
            )
        if outcome.get("planning_slices"):
            runtime_state["planning_slices"] = list(outcome["planning_slices"])
        if outcome.get("provider_stage_result"):
            _append_provider_stage_result(
                runtime_state, dict(outcome["provider_stage_result"])
            )
        if outcome.get("planning_provider_review"):
            runtime_state["planning_provider_review"] = dict(
                outcome["planning_provider_review"]
            )
        if outcome.get("planning_provider_review_delta"):
            runtime_state["planning_provider_review_delta"] = dict(
                outcome["planning_provider_review_delta"]
            )
        if outcome.get("planning_provider_failure"):
            runtime_state["planning_provider_failure"] = dict(
                outcome["planning_provider_failure"]
            )
        runtime_state["planning_provider_disagreement_count"] = int(
            runtime_state.get("planning_provider_disagreement_count") or 0
        ) + int(outcome.get("planning_provider_disagreement_count") or 0)
        runtime_state["search_pass_count"] = int(
            runtime_state.get("search_pass_count") or 0
        ) + int(outcome.get("search_pass_count") or 0)
        runtime_state["inspected_file_count"] = int(
            runtime_state.get("inspected_file_count") or 0
        ) + int(outcome.get("inspected_file_count") or 0)
        runtime_state["discovery_budget_escalated"] = bool(
            runtime_state.get("discovery_budget_escalated")
            or outcome.get("discovery_budget_escalated")
        )
        phase_result = dict(outcome.get("phase_result") or {})
        if phase_result:
            _append_phase_result(runtime_state, phase_result)

    sequence_outcome = run_linear_stage_sequence(
        mutable_state,
        stage_specs=runtime_stage_specs,
        handler_registry=PLANNING_STAGE_REGISTRY,
        payload_resolver=_payload_resolver,
        observe_outcome=_observe_outcome,
    )
    terminal_status = str(sequence_outcome.get("terminal_status") or "failed")
    if execution_contract["provider_participation"] != "none":
        run_mode = "provider-reviewed"
        run_details = dict(mutable_state.get("run_details") or {})
        run_details["planning_run_mode"] = run_mode
        mutable_state["run_details"] = run_details
        mutable_state["planning_run_mode"] = run_mode
    if terminal_status != "success":
        stage_outcome = sequence_outcome.get("stage_outcome")
        if isinstance(stage_outcome, Mapping):
            mutable_state["clarification_requests"] = list(
                stage_outcome.get("clarification_requests") or []
            )
        _apply_terminal_status(
            mutable_state,
            terminal_status=terminal_status,
            stop_reason=str(sequence_outcome.get("stop_reason") or ""),
        )
        _derive_planning_coverage(mutable_state, phase_specs=phase_specs)
        return state

    mutable_state["clarification_requests"] = []
    mutable_state["planning_run_mode"] = run_mode
    _apply_terminal_status(mutable_state, terminal_status="success", stop_reason=None)
    _derive_planning_coverage(mutable_state, phase_specs=phase_specs)
    return state
