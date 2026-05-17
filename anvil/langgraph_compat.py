# mypy: disable-error-code="no-redef"

from __future__ import annotations

"""Compatibility helpers for LangGraph-style workflows.

This module prefers the real LangGraph package when it is installed. When it is
not available, it provides a very small in-process fallback that supports the
subset of the API Forge uses in tests:

- ``StateGraph`` with ``add_node`` / ``add_edge`` / ``add_conditional_edges``
- ``compile(checkpointer=...)`` returning an object with ``ainvoke`` and
  ``astream_events``
- ``MemorySaver`` and a simple SQLite-backed saver for resumable local runs

The fallback is intentionally lightweight; it is not a drop-in replacement for
LangGraph. It only models the execution behavior needed by Forge's graph
builders and offline tests.
"""

import importlib
import inspect
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Mapping,
    MutableMapping,
    cast,
)

try:  # pragma: no cover - exercised when LangGraph is installed
    from langgraph.graph import END, StateGraph  # type: ignore[assignment]

    try:  # pragma: no cover - version-dependent import path
        MemorySaver = importlib.import_module("langgraph.checkpoint.memory").MemorySaver
    except ImportError:  # pragma: no cover
        MemorySaver = importlib.import_module("langgraph.checkpoint").MemorySaver

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - exercised in this container
    HAS_LANGGRAPH = False
    END = "__END__"

    class MemorySaver:
        """Small in-memory checkpoint saver used by the fallback runtime."""

        def __init__(self) -> None:
            self._records: dict[str, list[dict[str, Any]]] = {}

        def save_state(
            self, thread_id: str, node_name: str, state: Mapping[str, Any]
        ) -> None:
            bucket = self._records.setdefault(str(thread_id), [])
            bucket.append(
                {
                    "saved_at": time.time(),
                    "node": node_name,
                    "state": json.loads(json.dumps(state)),
                }
            )

        def latest_state(self, thread_id: str) -> dict[str, Any] | None:
            bucket = self._records.get(str(thread_id), [])
            if not bucket:
                return None
            return dict(bucket[-1]["state"])


@dataclass
class SimpleSqliteSaver:
    """Very small SQLite-based checkpoint saver used when LangGraph is absent."""

    db_path: str

    def __post_init__(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    saved_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_state(
        self, thread_id: str, node_name: str, state: Mapping[str, Any]
    ) -> None:
        payload_json = json.dumps(state)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO checkpoints (thread_id, node_name, saved_at, payload_json) VALUES (?, ?, ?, ?)",
                (str(thread_id), str(node_name), time.time(), payload_json),
            )
            conn.commit()

    def latest_state(self, thread_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM checkpoints WHERE thread_id = ? ORDER BY saved_at DESC LIMIT 1",
                (str(thread_id),),
            ).fetchone()
        if row is None:
            return None
        return cast(dict[str, Any], json.loads(row[0]))

    def close(self) -> None:
        return None


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _checkpoint_save(
    checkpointer: Any, thread_id: str, node_name: str, state: Mapping[str, Any]
) -> None:
    if checkpointer is None:
        return
    save_fn = getattr(checkpointer, "save_state", None)
    if callable(save_fn):
        save_fn(thread_id, node_name, state)
        return
    put_fn = getattr(checkpointer, "put", None)
    if callable(put_fn):  # pragma: no cover - compatibility path
        put_fn(thread_id, node_name, dict(state))


if not HAS_LANGGRAPH:

    class _SimpleCompiledGraph:
        def __init__(
            self,
            *,
            nodes: Mapping[str, Callable[[MutableMapping[str, Any]], Any]],
            entry_point: str,
            edges: Mapping[str, str],
            conditional_edges: Mapping[
                str,
                tuple[
                    Callable[[MutableMapping[str, Any]], str],
                    Mapping[str, str],
                ],
            ],
            checkpointer: Any = None,
        ) -> None:
            self._nodes = dict(nodes)
            self._entry_point = entry_point
            self._edges = dict(edges)
            self._conditional_edges = dict(conditional_edges)
            self._checkpointer = checkpointer

        async def ainvoke(
            self,
            state: MutableMapping[str, Any],
            config: Mapping[str, Any] | None = None,
        ) -> MutableMapping[str, Any]:
            thread_id = _thread_id_from_config(config)
            current = self._entry_point
            working_state: MutableMapping[str, Any] = dict(state)

            while current != END:
                node_fn = self._nodes[current]
                working_state = await _maybe_await(node_fn(working_state))
                _checkpoint_save(self._checkpointer, thread_id, current, working_state)

                if current in self._conditional_edges:
                    router, mapping = self._conditional_edges[current]
                    route_key = await _maybe_await(router(working_state))
                    current = mapping[str(route_key)]
                else:
                    current = self._edges[current]
            return working_state

        async def astream_events(
            self,
            state: MutableMapping[str, Any],
            config: Mapping[str, Any] | None = None,
            version: str | None = None,
        ) -> AsyncIterator[dict[str, Any]]:
            del version
            thread_id = _thread_id_from_config(config)
            current = self._entry_point
            working_state: MutableMapping[str, Any] = dict(state)

            while current != END:
                yield {
                    "event": "on_node_start",
                    "name": current,
                    "data": {"input": working_state, "thread_id": thread_id},
                }
                node_fn = self._nodes[current]
                working_state = await _maybe_await(node_fn(working_state))
                _checkpoint_save(self._checkpointer, thread_id, current, working_state)
                yield {
                    "event": "on_node_end",
                    "name": current,
                    "data": {"output": working_state, "thread_id": thread_id},
                }

                if current in self._conditional_edges:
                    router, mapping = self._conditional_edges[current]
                    route_key = await _maybe_await(router(working_state))
                    next_node = mapping[str(route_key)]
                    yield {
                        "event": "on_router",
                        "name": current,
                        "data": {"route": route_key, "next": next_node},
                    }
                    current = next_node
                else:
                    current = self._edges[current]

    class StateGraph:
        """Minimal graph builder mirroring the tiny subset Forge uses."""

        def __init__(self, state_type: Any) -> None:
            self.state_type = state_type
            self._nodes: dict[str, Callable[[MutableMapping[str, Any]], Any]] = {}
            self._entry_point: str | None = None
            self._edges: dict[str, str] = {}
            self._conditional_edges: dict[
                str,
                tuple[
                    Callable[[MutableMapping[str, Any]], str],
                    Mapping[str, str],
                ],
            ] = {}

        def add_node(
            self, name: str, fn: Callable[[MutableMapping[str, Any]], Any]
        ) -> None:
            self._nodes[name] = fn

        def set_entry_point(self, name: str) -> None:
            self._entry_point = name

        def add_edge(self, source: str, target: str) -> None:
            self._edges[source] = target

        def add_conditional_edges(
            self,
            source: str,
            router: Callable[[MutableMapping[str, Any]], str],
            mapping: Mapping[str, str],
        ) -> None:
            self._conditional_edges[source] = (router, dict(mapping))

        def compile(self, checkpointer: Any = None) -> _SimpleCompiledGraph:
            if not self._entry_point:
                raise ValueError("Graph entry point is not set")
            return _SimpleCompiledGraph(
                nodes=self._nodes,
                entry_point=self._entry_point,
                edges=self._edges,
                conditional_edges=self._conditional_edges,
                checkpointer=checkpointer,
            )


def _thread_id_from_config(config: Mapping[str, Any] | None) -> str:
    if not config:
        return "default"
    configurable = config.get("configurable")
    if isinstance(configurable, Mapping):
        thread_id = configurable.get("thread_id")
        if thread_id:
            return str(thread_id)
    return "default"


async def open_sqlite_saver(db_path: str) -> Any:
    """Return a SQLite-capable checkpointer.

    Prefers the real LangGraph saver when available; otherwise falls back to the
    lightweight saver implemented above.
    """

    if HAS_LANGGRAPH:  # pragma: no cover - exercised when dependency is installed
        try:
            import aiosqlite
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            conn = await aiosqlite.connect(db_path)
            if not hasattr(conn, "is_alive") and hasattr(conn, "_thread"):
                conn.is_alive = conn._thread.is_alive  # type: ignore[attr-defined]
            saver = AsyncSqliteSaver(conn)
            cast(Any, saver)._forge_conn = conn
            return saver
        except Exception:
            pass
    return SimpleSqliteSaver(db_path)


async def close_sqlite_saver(saver: Any) -> None:
    conn = getattr(saver, "_forge_conn", None)
    if conn is not None:  # pragma: no cover - real LangGraph path
        await conn.close()
        return
    close_fn = getattr(saver, "close", None)
    if callable(close_fn):
        result = close_fn()
        if isinstance(result, Awaitable):
            await result
