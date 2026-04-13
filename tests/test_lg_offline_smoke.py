# tests/test_lg_offline_smoke.py
"""Offline smoke test using a fake provider (no network required)."""

import pytest

from anvil.orchestration.langgraph_executor import LangGraphExecutor


class FakeProvider:
    """Fake provider for offline testing."""

    model_name = "fake-model"

    async def generate(self, prompt: str, **kwargs):
        """Generate fake response."""
        return f"EXEC:{prompt[:20]}"

    async def chat(self, messages, **kwargs):
        """Generate fake chat response."""
        content = " ".join(
            m.get("content", "") for m in messages if isinstance(m, dict)
        )

        # Simulate review logic
        if "review" in content.lower() or "EXEC:" in content:
            return "[PASS] Looks good"

        # Default responses for other nodes
        if "critique" in content.lower():
            return "Critique: The code could be improved"
        if "refine" in content.lower():
            return "Refined: def add(a, b): return a + b"
        if "reflect" in content.lower():
            return "Reflection: Try a different approach"

        return "Generic response"


@pytest.mark.asyncio
async def test_offline_smoke(monkeypatch):
    """Test LangGraph execution without network calls."""

    # Create fake provider instance
    fake_provider = FakeProvider()

    # Mock the provider getter function
    def mock_get_provider(name):
        return fake_provider

    # Mock configuration resolver's get_provider_for_role
    def mock_get_provider_for_role(self, role, overrides=None):
        # Return provider and a mock config
        class MockConfig:
            provider_name = "fake"
            model_name = "fake-model"
            kwargs = {}
            fallback_used = False
            resolution_path = ["direct"]

        return fake_provider, MockConfig()

    # Patch get_provider where it's used
    monkeypatch.setattr("anvil.providers.get_provider", mock_get_provider)

    # Patch the configuration resolver for nodes that use state.get_provider_for_role
    from anvil.configuration_resolver import ConfigurationResolver

    monkeypatch.setattr(
        ConfigurationResolver, "get_provider_for_role", mock_get_provider_for_role
    )

    # Create executor and run task
    executor = LangGraphExecutor()
    state = await executor.execute("Write a function add(a,b)")

    # Verify execution completed
    assert state.result is not None
    assert state.completion_status in ["success", "failed"]
    assert state.thread_id is not None

    # Check that nodes executed
    assert "execute" in state.logs
    assert "orchestrator" in state.logs or state.strategy is not None

    print("✅ Offline smoke test passed!")
    print(f"  Result: {state.result}")
    print(f"  Status: {state.completion_status}")
    print(f"  Nodes executed: {list(state.logs.keys())}")


@pytest.mark.asyncio
async def test_offline_streaming(monkeypatch):
    """Test LangGraph streaming without network calls."""

    # Create fake provider instance
    fake_provider = FakeProvider()

    # Mock the provider getter function
    def mock_get_provider(name):
        return fake_provider

    # Mock configuration resolver's get_provider_for_role
    def mock_get_provider_for_role(self, role, overrides=None):
        # Return provider and a mock config
        class MockConfig:
            provider_name = "fake"
            model_name = "fake-model"
            kwargs = {}
            fallback_used = False
            resolution_path = ["direct"]

        return fake_provider, MockConfig()

    # Patch get_provider where it's used
    monkeypatch.setattr("anvil.providers.get_provider", mock_get_provider)

    # Patch the configuration resolver for nodes that use state.get_provider_for_role
    from anvil.configuration_resolver import ConfigurationResolver

    monkeypatch.setattr(
        ConfigurationResolver, "get_provider_for_role", mock_get_provider_for_role
    )

    # Create executor and stream execution
    executor = LangGraphExecutor()
    events = []

    async for event in executor.stream_execution("Calculate 2 + 2"):
        events.append(event)

    # Verify events were streamed
    assert len(events) > 0
    assert all("event" in e for e in events)
    assert all("node" in e for e in events)
    assert all("time" in e for e in events)

    # Check that key nodes were visited
    node_names = [e["node"] for e in events]
    assert any("execute" in str(n) for n in node_names)

    print("✅ Offline streaming test passed!")
    print(f"  Total events: {len(events)}")
    print(f"  Unique nodes: {len(set(node_names))}")


@pytest.mark.asyncio
async def test_offline_checkpointing(monkeypatch):
    """Test checkpointing functionality offline."""

    # Create fake provider instance
    fake_provider = FakeProvider()

    # Mock the provider getter function
    def mock_get_provider(name):
        return fake_provider

    # Mock configuration resolver's get_provider_for_role
    def mock_get_provider_for_role(self, role, overrides=None):
        # Return provider and a mock config
        class MockConfig:
            provider_name = "fake"
            model_name = "fake-model"
            kwargs = {}
            fallback_used = False
            resolution_path = ["direct"]

        return fake_provider, MockConfig()

    # Patch get_provider where it's used
    monkeypatch.setattr("anvil.providers.get_provider", mock_get_provider)

    # Patch the configuration resolver for nodes that use state.get_provider_for_role
    from anvil.configuration_resolver import ConfigurationResolver

    monkeypatch.setattr(
        ConfigurationResolver, "get_provider_for_role", mock_get_provider_for_role
    )

    # Test memory checkpointing (default)
    executor_memory = LangGraphExecutor(checkpoint="memory")
    state1 = await executor_memory.execute("Test task 1")

    assert state1.thread_id is not None
    assert state1.result is not None

    # Test that thread_id is unique for different tasks
    state2 = await executor_memory.execute("Test task 2")
    assert state2.thread_id != state1.thread_id

    print("✅ Offline checkpointing test passed!")
    print(f"  Thread 1: {state1.thread_id}")
    print(f"  Thread 2: {state2.thread_id}")


@pytest.mark.asyncio
async def test_offline_checkpointing_sqlite(monkeypatch, tmp_path):
    """Test sqlite checkpointing functionality offline."""

    # Create fake provider instance
    fake_provider = FakeProvider()

    # Mock the provider getter function
    def mock_get_provider(name):
        return fake_provider

    # Mock configuration resolver's get_provider_for_role
    def mock_get_provider_for_role(self, role, overrides=None):
        # Return provider and a mock config
        class MockConfig:
            provider_name = "fake"
            model_name = "fake-model"
            kwargs = {}
            fallback_used = False
            resolution_path = ["direct"]

        return fake_provider, MockConfig()

    # Patch get_provider where it's used
    monkeypatch.setattr("anvil.providers.get_provider", mock_get_provider)

    # Patch the configuration resolver for nodes that use state.get_provider_for_role
    from anvil.configuration_resolver import ConfigurationResolver

    monkeypatch.setattr(
        ConfigurationResolver, "get_provider_for_role", mock_get_provider_for_role
    )

    db_path = tmp_path / "forge_checkpoints.db"

    executor = LangGraphExecutor(checkpoint="sqlite", db_path=str(db_path))
    state1 = await executor.execute("Test sqlite task 1")
    assert state1.thread_id is not None
    assert state1.result is not None
    assert db_path.exists()

    state2 = await executor.execute("Test sqlite task 2")
    assert state2.thread_id is not None
    assert state2.result is not None
    assert state2.thread_id != state1.thread_id

    executor2 = LangGraphExecutor(checkpoint="sqlite", db_path=str(db_path))
    state3 = await executor2.execute("Test sqlite task 3")
    assert state3.thread_id is not None
    assert state3.result is not None

    print("✅ Offline sqlite checkpointing test passed!")
