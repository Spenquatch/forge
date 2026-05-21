from __future__ import annotations

from typing import Any, cast

from ..state import HarnessState
from ..strategy_graph import STRATEGY_GRAPH_SUBSET, build_strategy_graph_spec


def select_strategy_node(state: HarnessState) -> HarnessState:
    if str(state.get("config_verdict") or "pass") == "invalid_config":
        return state
    strategy_kind = str(state.get("strategy_kind") or "single_pass")
    strategy_spec = dict(state.get("strategy_spec") or {})
    graph_spec = build_strategy_graph_spec(strategy_kind, strategy_spec)
    payload = cast(dict[str, Any], state)
    payload["strategy_graph_spec"] = graph_spec.to_dict()
    payload["strategy_graph_spec_id"] = graph_spec.spec_id
    payload["strategy_graph_subset"] = STRATEGY_GRAPH_SUBSET
    return state
