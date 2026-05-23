from __future__ import annotations

"""Shared single-pass runtime helpers for the bounded stage substrate."""

from collections.abc import Mapping, MutableMapping
from typing import Any

from .bounded_stage_runtime import StageHandler, run_linear_stage_sequence
from .state import HarnessState
from .subgraphs._bridge import run_harness_runner

SINGLE_PASS_STAGE_TYPE = "single_pass_solution"


def _single_pass_stage_specs(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    graph_spec = state.get("strategy_graph_spec")
    if isinstance(graph_spec, Mapping):
        raw_stages = graph_spec.get("stages")
        if isinstance(raw_stages, list):
            compiled_stage_specs: list[dict[str, Any]] = []
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
    return [
        {
            "id": "solver",
            "stage_type": SINGLE_PASS_STAGE_TYPE,
            "role_name": "solver",
        }
    ]


def _run_single_pass_solution(
    state: MutableMapping[str, Any],
    stage_spec: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    del payload
    bridged_state = run_harness_runner(state)  # type: ignore[arg-type]
    state.clear()
    state.update(bridged_state)
    run_details = dict(state.get("run_details") or {})
    run_details["single_pass_runtime_stage_id"] = str(stage_spec.get("id") or "solver")
    run_details["single_pass_runtime_stage_type"] = str(
        stage_spec.get("stage_type") or SINGLE_PASS_STAGE_TYPE
    )
    state["run_details"] = run_details
    return {"status": "success", "stop_reason": None}


SINGLE_PASS_STAGE_REGISTRY: dict[str, StageHandler] = {
    SINGLE_PASS_STAGE_TYPE: _run_single_pass_solution,
}


def execute_single_pass_runtime(state: HarnessState) -> HarnessState:
    mutable_state = state
    stage_specs = _single_pass_stage_specs(mutable_state)

    sequence_outcome = run_linear_stage_sequence(
        mutable_state,
        stage_specs=stage_specs,
        handler_registry=SINGLE_PASS_STAGE_REGISTRY,
        payload_resolver=lambda *_args, **_kwargs: {},
    )
    if str(sequence_outcome.get("terminal_status") or "failed") != "success":
        mutable_state["stop_reason"] = str(sequence_outcome.get("stop_reason") or "")
    return state
