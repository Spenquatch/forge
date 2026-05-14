from __future__ import annotations

"""Parent LangGraph builder for the harness surface."""

from typing import Any, MutableMapping, Optional

from anvil.langgraph_compat import END, MemorySaver, StateGraph

from .nodes.finalize import finalize_node
from .nodes.prepare_run import prepare_run_node
from .nodes.select_best_draft import select_best_draft_node
from .nodes.select_strategy import select_strategy_node
from .nodes.validator_preflight import validator_preflight_node
from .nodes.write_artifacts import write_artifacts_node
from .strategy_graph import route_after_strategy_selection
from .subgraphs.analysis_review_v1 import analysis_review_v1_subgraph
from .subgraphs.pfr_v1 import pfr_v1_subgraph
from .subgraphs.single_pass import single_pass_subgraph


async def _wrap_state_node(fn, state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    result = fn(state)
    if hasattr(result, "__await__"):
        return await result
    return result


def build_harness_langgraph(*, checkpointer: Optional[Any] = None):
    graph = StateGraph(dict)  # type: ignore[type-var]

    async def _prepare(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(prepare_run_node, state)

    async def _preflight(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(validator_preflight_node, state)

    async def _select(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(select_strategy_node, state)

    async def _single(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(single_pass_subgraph, state)

    async def _pfr(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(pfr_v1_subgraph, state)

    async def _analysis(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(analysis_review_v1_subgraph, state)

    async def _best(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(select_best_draft_node, state)

    async def _write(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(write_artifacts_node, state)

    async def _finalize(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return await _wrap_state_node(finalize_node, state)

    graph.add_node("prepare_run", _prepare)
    graph.add_node("validator_preflight", _preflight)
    graph.add_node("select_strategy", _select)
    graph.add_node("single_pass", _single)
    graph.add_node("pfr_v1", _pfr)
    graph.add_node("analysis_review_v1", _analysis)
    graph.add_node("select_best_draft", _best)
    graph.add_node("write_artifacts", _write)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("prepare_run")
    graph.add_edge("prepare_run", "validator_preflight")
    graph.add_edge("validator_preflight", "select_strategy")

    graph.add_conditional_edges(
        "select_strategy",
        route_after_strategy_selection,
        {
            "single_pass": "single_pass",
            "pfr_v1": "pfr_v1",
            "analysis_review_v1": "analysis_review_v1",
            "write_artifacts": "write_artifacts",
        },
    )

    graph.add_edge("single_pass", "select_best_draft")
    graph.add_edge("pfr_v1", "select_best_draft")
    graph.add_edge("analysis_review_v1", "select_best_draft")
    graph.add_edge("select_best_draft", "write_artifacts")
    graph.add_edge("write_artifacts", "finalize")
    graph.add_edge("finalize", END)

    if checkpointer is None:
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
