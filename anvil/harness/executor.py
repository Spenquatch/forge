from __future__ import annotations

"""LangGraph-style executor for harness runs."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Literal, Mapping, Optional, cast

from anvil.langgraph_compat import close_sqlite_saver, open_sqlite_saver

from .builder import build_harness_langgraph
from .state import HarnessState


class HarnessLangGraphExecutor:
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        checkpoint: str = "memory",
        db_path: str = "forge_harness_checkpoints.db",
        auto_fit_strategy: bool = True,
        analysis_review_execution_mode: Literal["legacy_bridge", "graph_owned"] = "legacy_bridge",
    ) -> None:
        self.max_attempts = max_attempts
        self.checkpoint = checkpoint
        self.db_path = db_path
        self.auto_fit_strategy = auto_fit_strategy
        self.analysis_review_execution_mode = analysis_review_execution_mode
        self._graph = build_harness_langgraph() if checkpoint == "memory" else None

    def _get_graph(self):
        if self._graph is None:
            raise RuntimeError(
                "Graph is not initialized; sqlite checkpointing requires per-run graph compilation."
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
        *,
        task_path: str,
        strategy_path: str,
        workspace: str,
        out_root: str = ".forge-harness-runs",
        config_path: str = "config/models.yaml",
        thread_id: Optional[str] = None,
        auto_fit_strategy: Optional[bool] = None,
        analysis_review_execution_mode: Optional[
            Literal["legacy_bridge", "graph_owned"]
        ] = None,
    ) -> HarnessState:
        request: Dict[str, Any] = {
            "task_path": task_path,
            "strategy_path": strategy_path,
            "workspace_root": workspace,
            "out_root": out_root,
            "config_path": config_path,
            "thread_id": thread_id or str(uuid.uuid4()),
            "auto_fit_strategy": self.auto_fit_strategy if auto_fit_strategy is None else auto_fit_strategy,
            "analysis_review_execution_mode": (
                self.analysis_review_execution_mode
                if analysis_review_execution_mode is None
                else analysis_review_execution_mode
            ),
            "max_attempts": self.max_attempts,
        }
        return await self.run(request)

    async def run(self, state: Mapping[str, Any]) -> HarnessState:
        working_state = dict(state)
        thread_id = str(working_state.get("thread_id") or uuid.uuid4())
        working_state["thread_id"] = thread_id
        cfg = {"configurable": {"thread_id": thread_id}}

        if self.checkpoint == "sqlite":
            async with self._sqlite_checkpointer() as checkpointer:
                graph = build_harness_langgraph(checkpointer=checkpointer)
                final_state = await graph.ainvoke(working_state, cfg)
        else:
            final_state = await self._get_graph().ainvoke(working_state, cfg)
        return cast(HarnessState, final_state)

    async def stream_execution(
        self,
        *,
        task_path: str,
        strategy_path: str,
        workspace: str,
        out_root: str = ".forge-harness-runs",
        config_path: str = "config/models.yaml",
        thread_id: Optional[str] = None,
        auto_fit_strategy: Optional[bool] = None,
        analysis_review_execution_mode: Optional[
            Literal["legacy_bridge", "graph_owned"]
        ] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request: Dict[str, Any] = {
            "task_path": task_path,
            "strategy_path": strategy_path,
            "workspace_root": workspace,
            "out_root": out_root,
            "config_path": config_path,
            "thread_id": thread_id or str(uuid.uuid4()),
            "auto_fit_strategy": self.auto_fit_strategy if auto_fit_strategy is None else auto_fit_strategy,
            "analysis_review_execution_mode": (
                self.analysis_review_execution_mode
                if analysis_review_execution_mode is None
                else analysis_review_execution_mode
            ),
            "max_attempts": self.max_attempts,
        }
        cfg = {"configurable": {"thread_id": request["thread_id"]}}

        async def _iter_events(graph):
            async for event in graph.astream_events(request, cfg, version="v2"):
                yield event

        if self.checkpoint == "sqlite":
            async with self._sqlite_checkpointer() as checkpointer:
                graph = build_harness_langgraph(checkpointer=checkpointer)
                async for event in _iter_events(graph):
                    yield self._normalize_event(event)
        else:
            async for event in _iter_events(self._get_graph()):
                yield self._normalize_event(event)

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = event.get("data", {}) or {}
        node = event.get("name")
        return {
            "event": event.get("event") or event.get("type") or event.get("kind"),
            "node": node,
            "time": time.time(),
            "data": data,
        }
