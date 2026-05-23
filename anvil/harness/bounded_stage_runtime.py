from __future__ import annotations

"""Reusable bounded stage-sequence execution helpers."""

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import Any

StageHandler = Callable[
    [MutableMapping[str, Any], dict[str, Any], dict[str, Any]],
    dict[str, Any],
]
StagePayloadResolver = Callable[
    [MutableMapping[str, Any], dict[str, Any]], dict[str, Any]
]
StageOutcomeObserver = Callable[
    [MutableMapping[str, Any], dict[str, Any], dict[str, Any]], None
]


def run_linear_stage_sequence(
    state: MutableMapping[str, Any],
    *,
    stage_specs: Sequence[dict[str, Any]],
    handler_registry: Mapping[str, StageHandler],
    payload_resolver: StagePayloadResolver,
    observe_outcome: StageOutcomeObserver | None = None,
) -> dict[str, Any]:
    for stage_spec in stage_specs:
        stage_type = str(stage_spec.get("stage_type") or "").strip()
        if not stage_type:
            return {
                "terminal_status": "failed",
                "stop_reason": "bounded_stage_missing_stage_type",
                "failed_stage_id": str(stage_spec.get("id") or "unknown"),
            }

        handler = handler_registry.get(stage_type)
        if handler is None:
            return {
                "terminal_status": "failed",
                "stop_reason": f"unsupported_bounded_stage:{stage_type}",
                "failed_stage_id": str(stage_spec.get("id") or "unknown"),
            }

        payload = payload_resolver(state, stage_spec)
        outcome = handler(state, stage_spec, payload)
        if observe_outcome is not None:
            observe_outcome(state, stage_spec, outcome)

        status = str(outcome.get("status") or "success").strip() or "success"
        if status != "success":
            return {
                "terminal_status": status,
                "stop_reason": str(
                    outcome.get("stop_reason")
                    or f"{stage_spec.get('id') or stage_type}_{status}"
                ),
                "failed_stage_id": str(stage_spec.get("id") or "unknown"),
                "stage_outcome": outcome,
            }

    return {
        "terminal_status": "success",
        "stop_reason": None,
        "failed_stage_id": None,
    }
