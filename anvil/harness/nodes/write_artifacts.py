from __future__ import annotations

from ..reporting import apply_final_artifacts, write_state_artifacts
from ..state import HarnessState, state_from_summary


def write_artifacts_node(state: HarnessState) -> HarnessState:
    summary_payload = state.get("summary_payload")
    if isinstance(summary_payload, dict):
        updated_summary = apply_final_artifacts(summary_payload)
        request_keys = {
            key: state.get(key)
            for key in ("task_path", "strategy_path", "config_path", "auto_fit_strategy")
            if key in state
        }
        merged_state = state_from_summary(updated_summary, fallback_thread_id=str(state.get("thread_id") or ""))
        for key, value in request_keys.items():
            if value is not None:
                merged_state[key] = value
        merged_state["summary_payload"] = updated_summary
        return merged_state
    return write_state_artifacts(state)
