# anvil/orchestration/langgraph_builder.py
"""LangGraph builder for Forge - constructs the complete LangGraph workflow."""

from typing import Any, Callable, Dict, Optional

from anvil.langgraph_compat import END, MemorySaver, StateGraph
from anvil.orchestration.nodes.critique import critique_node
from anvil.orchestration.nodes.execute import execute_node
from anvil.orchestration.nodes.finalize import finalize_node
from anvil.orchestration.nodes.meta_learning import meta_learning_node
from anvil.orchestration.nodes.monitor import monitor_node
from anvil.orchestration.nodes.orchestrator import orchestrator_node
from anvil.orchestration.nodes.refine import refine_node
from anvil.orchestration.nodes.reflect import reflect_node
from anvil.orchestration.nodes.review import review_node
from anvil.orchestration.state import ForgeState


def wrap_node(fn: Callable, name: str) -> Callable:
    """
    Wrap a ForgeState node function to work with StateCarrier dict format.

    Args:
        fn: The original node function that takes/returns ForgeState
        name: Name of the node (for debugging)

    Returns:
        Wrapped function that takes/returns dict with {"state": ForgeState}
    """

    async def _wrapped(carrier: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapped node function for StateCarrier compatibility."""
        # Deserialize ForgeState if needed
        state_data = carrier.get("state")
        if state_data is None:
            raise ValueError(f"Node {name} received carrier without 'state' key")

        # If it's a dict, reconstruct ForgeState
        if isinstance(state_data, dict):
            fs = ForgeState.from_dict(state_data)
        else:
            fs = state_data

        # Run the actual node
        new_fs = await fn(fs)

        # Return with serialized state for checkpointing
        return {"state": new_fs.to_dict()}

    _wrapped.__name__ = f"wrapped_{name}"
    return _wrapped


def build_forge_langgraph(
    max_attempts: int = 3,
    *,
    checkpointer: Optional[Any] = None,
):
    """
    Build the complete Forge LangGraph with leadership and worker nodes.

    Args:
        max_attempts: Maximum retry attempts
        checkpointer: Optional LangGraph checkpointer (defaults to in-memory)

    Returns:
        Compiled LangGraph
    """
    # Create the graph with dict state (StateCarrier format)
    graph = StateGraph(dict)  # type: ignore[type-var]

    # Add leadership nodes (wrapped for StateCarrier)
    graph.add_node("orchestrator", wrap_node(orchestrator_node, "orchestrator"))
    graph.add_node("monitor", wrap_node(monitor_node, "monitor"))
    graph.add_node("meta_learning", wrap_node(meta_learning_node, "meta_learning"))

    # Add worker nodes (wrapped for StateCarrier)
    graph.add_node("execute", wrap_node(execute_node, "execute"))
    graph.add_node("critique", wrap_node(critique_node, "critique"))
    graph.add_node("refine", wrap_node(refine_node, "refine"))
    graph.add_node("review", wrap_node(review_node, "review"))
    graph.add_node("reflect", wrap_node(reflect_node, "reflect"))
    graph.add_node("finalize", wrap_node(finalize_node, "finalize"))

    # Set entry point
    graph.set_entry_point("orchestrator")

    # Define edges for main flow
    graph.add_edge("orchestrator", "execute")
    graph.add_edge("execute", "critique")
    graph.add_edge("critique", "refine")
    graph.add_edge("refine", "review")

    # Define review router for conditional routing (StateCarrier-aware)
    def review_router(carrier: Dict[str, Any]) -> str:
        """Route based on review results."""
        state_data = carrier.get("state")
        if state_data is None:
            raise ValueError("review_router received carrier without 'state' key")

        # Handle both dict and ForgeState
        if isinstance(state_data, dict):
            fs = ForgeState.from_dict(state_data)
        else:
            fs = state_data

        passed = bool(fs.logs.get("review", {}).get("pass"))
        if passed or int(getattr(fs, "retry_count", 0)) >= max_attempts:
            return "finalize"
        return "monitor"

    # Add conditional edges from review
    graph.add_conditional_edges(
        "review",
        review_router,
        {"finalize": "finalize", "monitor": "monitor"},
    )

    # Define monitor router (StateCarrier-aware)
    def monitor_router(carrier: Dict[str, Any]) -> str:
        """Route after monitoring adjustments."""
        # After adjustments, reflect then try again via orchestrator
        return "reflect"

    # Add conditional edges from monitor
    graph.add_conditional_edges(
        "monitor",
        monitor_router,
        {"reflect": "reflect"},
    )

    # Add edges for retry loop
    graph.add_edge("reflect", "orchestrator")
    graph.add_edge("finalize", END)

    # Configure checkpointing
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Compile and return the graph
    return graph.compile(checkpointer=checkpointer)
