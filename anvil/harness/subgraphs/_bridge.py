from __future__ import annotations

from ..runner import HarnessRunner
from ..state import HarnessState, state_from_summary


def run_harness_runner(state: HarnessState) -> HarnessState:
    runner = HarnessRunner(
        task_path=str(state.get("task_path") or ""),
        strategy_path=str(state.get("strategy_path") or ""),
        workspace=str(state.get("workspace_root") or ""),
        out_root=str(state.get("out_root") or ".forge-harness-runs"),
        config_path=str(state.get("config_path") or "config/models.yaml"),
        task_data=dict(state.get("task_spec") or {}),
        strategy_data=dict(state.get("strategy_spec") or {}),
        thread_id=(str(state.get("thread_id")) if state.get("thread_id") else None),
        auto_fit_strategy=bool(state.get("auto_fit_strategy", True)),
    )
    summary = runner.run()
    request_keys = {
        key: state.get(key)
        for key in ("task_path", "strategy_path", "config_path", "auto_fit_strategy")
        if key in state
    }
    new_state = state_from_summary(summary, fallback_thread_id=str(state.get("thread_id") or ""))
    for key, value in request_keys.items():
        if value is not None:
            new_state[key] = value
    new_state["summary_payload"] = summary
    return new_state
