from __future__ import annotations

from typing import Any, cast

from ..runner import HarnessRunner
from ..state import (
    LEGACY_BRIDGE_BOUNDARY_VERSION,
    HarnessState,
    summary_read_adapter_v1,
)

_REQUEST_STATE_KEYS = (
    "task_path",
    "strategy_path",
    "config_path",
    "auto_fit_strategy",
)
_BOUNDARY_STATE_KEYS = (
    "serialization_version",
    "strategy_graph_spec",
    "strategy_graph_spec_id",
    "strategy_graph_subset",
    "summary_boundary_version",
)


class LegacyBridgeBoundary:
    """Temporary B1 runner bridge. No new semantics may land here."""

    def run(self, state: HarnessState) -> HarnessState:
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
        preserved_state = {
            key: state.get(key)
            for key in (*_REQUEST_STATE_KEYS, *_BOUNDARY_STATE_KEYS)
            if key in state
        }
        # Bridge call site only rehydrates the sanctioned boundary shape; no new
        # semantics may land here.
        new_state = summary_read_adapter_v1(
            summary, fallback_thread_id=str(state.get("thread_id") or "")
        )
        new_state_payload = cast(dict[str, Any], new_state)
        for key, value in preserved_state.items():
            if value is not None:
                new_state_payload[key] = value
        new_state_payload["bridge_boundary_version"] = LEGACY_BRIDGE_BOUNDARY_VERSION
        new_state_payload["summary_payload"] = summary
        return new_state


def run_harness_runner(state: HarnessState) -> HarnessState:
    return LegacyBridgeBoundary().run(state)
