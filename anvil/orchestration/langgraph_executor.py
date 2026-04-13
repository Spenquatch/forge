# anvil/orchestration/langgraph_executor.py
"""LangGraph executor for Forge - handles execution and streaming."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from anvil.langgraph_compat import close_sqlite_saver, open_sqlite_saver
from anvil.orchestration.langgraph_builder import build_forge_langgraph
from anvil.orchestration.state import ForgeState


class LangGraphExecutor:
    """
    Executor for the LangGraph-based Forge workflow.

    Handles execution, streaming, and checkpointing configuration.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        checkpoint: str = "memory",
        db_path: str = "forge_checkpoints.db",
    ):
        """
        Initialize the LangGraph executor.

        Args:
            max_attempts: Maximum retry attempts
            checkpoint: Checkpoint type ("memory" or "sqlite")
            db_path: Path to SQLite database for checkpointing
        """
        self.max_attempts = max_attempts
        self.checkpoint = checkpoint
        self.db_path = db_path

        self._graph = (
            build_forge_langgraph(max_attempts=max_attempts)
            if checkpoint == "memory"
            else None
        )

    def _get_graph(self):
        if self._graph is None:
            raise RuntimeError(
                "Graph is not initialized; sqlite checkpointing requires per-run "
                "graph compilation."
            )
        return self._graph

    @asynccontextmanager
    async def _sqlite_checkpointer(self):
        saver = await open_sqlite_saver(self.db_path)
        try:
            yield saver
        finally:
            await close_sqlite_saver(saver)

    async def execute(
        self,
        task: str,
        config: Optional[Dict[str, Any]] = None,
        pipeline: Optional[Dict[str, str]] = None,
    ) -> ForgeState:
        """
        Execute a task through the LangGraph workflow.

        Args:
            task: Task description
            config: Optional runtime configuration

        Returns:
            Final ForgeState with results
        """
        # Create initial state
        state = ForgeState(
            task, pipeline=pipeline or {}, runtime_overrides=config or {}
        )

        # Ensure thread_id is set
        state.thread_id = state.thread_id or str(uuid.uuid4())

        # Configure execution
        cfg = {"configurable": {"thread_id": state.thread_id}}

        # Execute the graph with StateCarrier format (serialize state)
        if self.checkpoint == "sqlite":
            async with self._sqlite_checkpointer() as checkpointer:
                graph = build_forge_langgraph(
                    max_attempts=self.max_attempts, checkpointer=checkpointer
                )
                final_carrier = await graph.ainvoke({"state": state.to_dict()}, cfg)
        else:
            final_carrier = await self._get_graph().ainvoke(
                {"state": state.to_dict()}, cfg
            )

        # Extract and reconstruct the ForgeState from the carrier
        state_data = final_carrier["state"]
        if isinstance(state_data, dict):
            return ForgeState.from_dict(state_data)
        if isinstance(state_data, ForgeState):
            return state_data
        raise TypeError(f"Unexpected final state type: {type(state_data).__name__}")

    async def run(self, state: ForgeState) -> ForgeState:
        """
        Run the LangGraph workflow with an existing ForgeState.

        This method provides compatibility with call sites that expect
        a graph-like object with a .run(state) method.

        Args:
            state: ForgeState to execute

        Returns:
            Final ForgeState with results
        """
        # Ensure thread_id is set
        if not state.thread_id:
            state.thread_id = str(uuid.uuid4())

        # Configure execution
        cfg = {"configurable": {"thread_id": state.thread_id}}

        # Execute the graph with StateCarrier format (serialize state)
        if self.checkpoint == "sqlite":
            async with self._sqlite_checkpointer() as checkpointer:
                graph = build_forge_langgraph(
                    max_attempts=self.max_attempts, checkpointer=checkpointer
                )
                final_carrier = await graph.ainvoke({"state": state.to_dict()}, cfg)
        else:
            final_carrier = await self._get_graph().ainvoke(
                {"state": state.to_dict()}, cfg
            )

        # Extract and reconstruct the ForgeState from the carrier
        state_data = final_carrier["state"]
        if isinstance(state_data, dict):
            return ForgeState.from_dict(state_data)
        if isinstance(state_data, ForgeState):
            return state_data
        raise TypeError(f"Unexpected final state type: {type(state_data).__name__}")

    async def stream_execution(
        self,
        task: str,
        config: Optional[Dict[str, Any]] = None,
        pipeline: Optional[Dict[str, str]] = None,
        thread_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream execution events from the LangGraph workflow.

        Args:
            task: Task description
            config: Optional runtime configuration

        Yields:
            Normalized event dictionaries
        """
        # Create initial state
        state = ForgeState(
            task, pipeline=pipeline or {}, runtime_overrides=config or {}
        )

        # Ensure thread_id is set
        if thread_id:
            state.thread_id = thread_id
        state.thread_id = state.thread_id or str(uuid.uuid4())

        # Configure execution
        cfg = {"configurable": {"thread_id": state.thread_id}}

        async def _iter_events(graph):
            async for event in graph.astream_events(
                {"state": state.to_dict()}, cfg, version="v2"
            ):
                yield event

        if self.checkpoint == "sqlite":
            async with self._sqlite_checkpointer() as checkpointer:
                graph = build_forge_langgraph(
                    max_attempts=self.max_attempts, checkpointer=checkpointer
                )
                async for event in _iter_events(graph):
                    yield self._normalize_event(event)
        else:
            async for event in _iter_events(self._get_graph()):
                yield self._normalize_event(event)

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = event.get("data", {}) or {}

        node = event.get("name")
        if node is None:
            metadata = event.get("metadata")
            if isinstance(metadata, dict):
                node = (
                    metadata.get("name")
                    or metadata.get("node")
                    or metadata.get("langgraph_node")
                )

        normalized: Dict[str, Any] = {
            "event": event.get("event") or event.get("type") or event.get("kind"),
            "node": node,
            "time": time.time(),
            "data": data,
        }

        # Best-effort extraction of final output state (when present).
        output = data.get("output")
        if isinstance(output, dict):
            state_data = output.get("state")
            if isinstance(state_data, dict):
                normalized["final_state"] = ForgeState.from_dict(state_data)
            elif isinstance(state_data, ForgeState):
                normalized["final_state"] = state_data

        return normalized
