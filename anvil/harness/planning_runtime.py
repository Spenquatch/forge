# mypy: disable-error-code="arg-type,typeddict-item"

from __future__ import annotations

"""Shared planning runtime helpers for the bounded C1 planning family."""

import re
from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .files import read_workspace_text, workspace_glob_paths
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
    "coverage_policy",
    "determinism_policy",
    "discovery_policy",
    "rubric_policy",
    "stop_policy",
)
PLANNING_MATCH_LIMIT = 25
PLANNING_READ_LIMIT = 12
PLANNING_READ_BYTES_LIMIT = 150 * 1024
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
            "summary": (
                "Mount planning_v1 and preserve generic post-runtime routing."
            ),
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
    return {
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
            str(item.get("workstream_id") or item.get("id") or "") for item in workstreams
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
    state["planning_coverage_status"] = None
    state["planning_coverage_ledger"] = []
    state["planning_assumptions_register"] = []
    state["planning_uncovered_delta"] = []
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
    values.extend(
        [
            "planning_v1",
            "builder",
            "reporting",
            "strategy graph",
            "subgraph",
            "artifact",
        ]
    )
    tokens: list[str] = []
    for value in values:
        tokens.extend(_tokenize(value))
    return list(dict.fromkeys(tokens))


def _score_path(path: str, *, query_tokens: list[str]) -> int:
    normalized = path.lower()
    score = 0
    for seam_spec in _CANONICAL_SEAM_SPECS:
        if normalized in seam_spec["path_hints"]:
            score += 100
    for token in query_tokens:
        if token in normalized:
            score += 10
    filename = Path(path).name.lower()
    if filename in {"builder.py", "reporting.py", "artifacts.py", "planning_runtime.py"}:
        score += 25
    if "planning" in normalized:
        score += 15
    if "report" in normalized or "artifact" in normalized:
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
    roots = sorted({str(Path(path).parent) for path in selected_paths if "/" in path})
    if "anvil/harness" in roots or any(path.startswith("anvil/harness/") for path in selected_paths):
        if (workspace_root / "anvil/harness/subgraphs/planning_v1.py").is_file():
            discovered.append("anvil/harness/subgraphs/planning_v1.py")
    for seam_spec in _CANONICAL_SEAM_SPECS:
        for rel_path in seam_spec["path_hints"]:
            if (workspace_root / rel_path).is_file():
                discovered.append(rel_path)
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
        text = read_workspace_text(_workspace_root(state), relative_path, max_bytes=read_size)
        evidence[relative_path] = text
        remaining_bytes -= len(text.encode("utf-8"))
    return evidence


def _objective_is_out_of_corpus(task_spec: Mapping[str, Any]) -> bool:
    values = [
        task_spec.get("objective"),
        task_spec.get("context"),
        task_spec.get("notes"),
    ]
    return any(_OUT_OF_CORPUS_RE.search(str(value or "")) for value in values)


def _seam_paths(
    *,
    candidate_paths: list[str],
    evidence_by_path: Mapping[str, str],
) -> list[dict[str, Any]]:
    available_paths = _dedupe_strings(list(candidate_paths) + list(evidence_by_path))
    seams: list[dict[str, Any]] = []
    for seam_spec in _CANONICAL_SEAM_SPECS:
        seam_paths = [
            path for path in seam_spec["path_hints"] if path in available_paths
        ]
        if not seam_paths:
            continue
        seams.append(
            {
                "id": seam_spec["seam_id"],
                "seam_id": seam_spec["seam_id"],
                "title": seam_spec["title"],
                "summary": seam_spec["summary"],
                "paths": seam_paths,
                "repo_evidence_refs": seam_paths,
                "dependency_reasoning": [
                    f"Grounded in {', '.join(seam_paths)}."
                ],
                "ambiguity_flags": [],
            }
        )
    return seams


def _workstreams_for_seams(seams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workstreams: list[dict[str, Any]] = []
    for seam_spec in _CANONICAL_SEAM_SPECS:
        seam_id = seam_spec["seam_id"]
        if not any(str(seam.get("seam_id") or seam.get("id")) == seam_id for seam in seams):
            continue
        workstream = dict(seam_spec["workstream"])
        workstream.update(
            {
                "id": workstream["workstream_id"],
                "seam_ids": [seam_id],
                "worktree_recommended": True,
                "dependency_reasoning": [f"Depends on `{seam_id}`."],
                "ambiguity_flags": [],
            }
        )
        workstreams.append(workstream)
    return workstreams


def _slices_for_workstreams(workstreams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for seam_spec in _CANONICAL_SEAM_SPECS:
        workstream_id = seam_spec["workstream"]["workstream_id"]
        seam_id = seam_spec["seam_id"]
        if not any(
            str(workstream.get("workstream_id") or workstream.get("id")) == workstream_id
            for workstream in workstreams
        ):
            continue
        slice_record = dict(seam_spec["slice"])
        slice_record.update(
            {
                "id": slice_record["slice_id"],
                "workstream_id": workstream_id,
                "seam_ids": [seam_id],
                "dependency_reasoning": [f"Implements `{workstream_id}`."],
                "ambiguity_flags": [],
            }
        )
        slices.append(slice_record)
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
            for path in _discovered_workspace_matches(state, selected_paths=selected_paths)
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

    seams = _seam_paths(
        candidate_paths=selected_paths,
        evidence_by_path=evidence_by_path,
    )
    if not seams:
        return (
            {
                str(design_phase["id"]): _clarification_payload(
                    phase_id=str(design_phase["id"]),
                    stop_reason="primary_cut_not_credible",
                    summary=(
                        "The planner could not derive a credible primary seam from the "
                        "bounded workspace evidence."
                    ),
                    repo_evidence_refs=selected_paths,
                    search_pass_count=search_pass_count,
                    inspected_file_count=inspected_file_count,
                    discovery_budget_escalated=discovery_budget_escalated,
                    question=(
                        "Should the planner prioritize runtime routing or artifact "
                        "publication first?"
                    ),
                    rationale=(
                        "The inspected workspace evidence did not isolate a confident "
                        "first cut inside the frozen budget."
                    ),
                )
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
    slices = _slices_for_workstreams(workstreams)

    repo_evidence_refs = _dedupe_strings(
        ["PLAN.md"]
        + selected_paths
        + [path for seam in seams for path in seam.get("paths", [])]
    )
    live_payloads = {
        str(design_phase["id"]): {
            "summary": (
                "The planning objective is coherent, bounded to the workspace, and "
                "credible within the deterministic evidence budget."
            ),
            "repo_evidence_refs": repo_evidence_refs,
            "search_pass_count": search_pass_count,
            "inspected_file_count": inspected_file_count,
            "discovery_budget_escalated": discovery_budget_escalated,
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
    phases = list(strategy_spec.get("phases") or [])
    phase_specs = [
        _phase_spec(
            phases[index - 1] if index - 1 < len(phases) else {},
            expected_stage_type=expected_stage_type,
            index=index,
        )
        for index, expected_stage_type in enumerate(PLANNING_PHASE_ORDER, start=1)
    ]
    policy_versions = _lookup_planning_policy_versions(strategy_spec)

    _seed_planning_state(mutable_state, policy_versions=policy_versions)

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
    mutable_state["run_details"] = run_details

    for phase_spec in phase_specs:
        stage_type = str(phase_spec["stage_type"])
        handler = PLANNING_PHASE_REGISTRY.get(stage_type)
        if handler is None:
            _apply_terminal_status(
                mutable_state,
                terminal_status="failed",
                stop_reason=f"unsupported_planning_phase:{stage_type}",
            )
            return state

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
        else:
            payload = dict(live_phase_payloads.get(str(phase_spec["id"])) or {})

        outcome = handler(mutable_state, phase_spec, payload, policy_versions)

        mutable_state["repo_evidence_refs"] = _merge_repo_evidence_refs(
            list(mutable_state.get("repo_evidence_refs") or []),
            list(outcome.get("repo_evidence_refs") or []),
        )
        if outcome.get("planning_seams"):
            mutable_state["planning_seams"] = list(outcome["planning_seams"])
        if outcome.get("planning_workstreams"):
            mutable_state["planning_workstreams"] = list(
                outcome["planning_workstreams"]
            )
        if outcome.get("planning_slices"):
            mutable_state["planning_slices"] = list(outcome["planning_slices"])
        mutable_state["search_pass_count"] = int(
            mutable_state.get("search_pass_count") or 0
        ) + int(outcome.get("search_pass_count") or 0)
        mutable_state["inspected_file_count"] = int(
            mutable_state.get("inspected_file_count") or 0
        ) + int(outcome.get("inspected_file_count") or 0)
        mutable_state["discovery_budget_escalated"] = bool(
            mutable_state.get("discovery_budget_escalated")
            or outcome.get("discovery_budget_escalated")
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
                stop_reason=str(
                    outcome.get("stop_reason") or f"{phase_spec['id']}_{status}"
                ),
            )
            return state

    mutable_state["clarification_requests"] = []
    _apply_terminal_status(mutable_state, terminal_status="success", stop_reason=None)
    return state
