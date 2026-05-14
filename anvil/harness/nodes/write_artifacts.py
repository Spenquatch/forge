from __future__ import annotations

from ..reporting import (
    apply_final_artifacts,
    summary_projection_v1,
    write_state_artifacts,
)
from ..state import HarnessState, summary_read_adapter_v1


def write_artifacts_node(state: HarnessState) -> HarnessState:
    projectable_state = state
    summary_payload = state.get("summary_payload")
    if isinstance(summary_payload, dict) and "run_dir" not in state and "out_root" not in state:
        projectable_state = summary_read_adapter_v1(
            summary_payload, fallback_thread_id=str(state.get("thread_id") or "")
        )
    elif "run_dir" not in state and "out_root" not in state:
        return write_state_artifacts(state)

    # Projection call site only orders the sanctioned boundary helpers; no new
    # semantics may land here.
    projected_summary = summary_projection_v1(projectable_state)
    updated_summary = apply_final_artifacts(projected_summary)
    request_keys = {
        key: state.get(key)
        for key in ("task_path", "strategy_path", "config_path", "auto_fit_strategy")
        if key in state
    }
    merged_state = summary_read_adapter_v1(
        updated_summary, fallback_thread_id=str(state.get("thread_id") or "")
    )
    for key, value in request_keys.items():
        if value is not None:
            merged_state[key] = value
    merged_state["summary_payload"] = updated_summary
    return merged_state
