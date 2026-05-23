from __future__ import annotations

import asyncio

import anvil.harness.executor as executor_module


class _FakeGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], dict[str, object]]] = []

    async def ainvoke(
        self, state: dict[str, object], cfg: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append((dict(state), dict(cfg)))
        return {"ok": True, "state": state, "cfg": cfg}


def test_executor_reloads_provider_config_before_execution(monkeypatch) -> None:
    fake_graph = _FakeGraph()
    reload_calls: list[str] = []

    monkeypatch.setattr(
        executor_module, "build_harness_langgraph", lambda checkpointer=None: fake_graph
    )
    monkeypatch.setattr(
        executor_module, "reload_config", lambda path: reload_calls.append(path)
    )

    executor = executor_module.HarnessLangGraphExecutor(checkpoint="memory")
    result = asyncio.run(
        executor.execute(
            task_path="task.yaml",
            strategy_path="strategy.yaml",
            workspace="/tmp/workspace",
            config_path="config/test-models.yaml",
            thread_id="thread-123",
        )
    )

    assert reload_calls == ["config/test-models.yaml"]
    assert fake_graph.calls
    state, cfg = fake_graph.calls[-1]
    assert state["config_path"] == "config/test-models.yaml"
    assert cfg == {"configurable": {"thread_id": "thread-123"}}
    assert result["ok"] is True
