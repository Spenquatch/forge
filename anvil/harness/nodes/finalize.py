from __future__ import annotations

from ..state import HarnessState


def finalize_node(state: HarnessState) -> HarnessState:
    if not state.get("run_verdict"):
        state["run_verdict"] = state.get("content_verdict") or state.get("config_verdict") or "invalid_config"
    if not state.get("summary_text"):
        state["summary_text"] = "Harness run completed."
    if not state.get("policy_verdict"):
        state["policy_verdict"] = "pass"
    if not state.get("validator_verdict"):
        state["validator_verdict"] = "not_applicable"
    if not state.get("config_verdict"):
        state["config_verdict"] = "pass"
    return state
