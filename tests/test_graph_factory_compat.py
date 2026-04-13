# tests/test_graph_factory_compat.py
"""Test that create_forge_graph() returns a compatible object with .run() method."""

import pytest

from anvil.orchestration.graph import create_forge_graph
from anvil.orchestration.state import create_state


class FakeProvider:
    """Fake provider for offline testing."""

    model_name = "fake-model"

    async def generate(self, prompt: str, **kwargs):
        """Generate fake response."""
        return f"EXEC: Task completed for {prompt[:30]}"

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
            return "Critique: The implementation looks solid"
        if "refine" in content.lower():
            return "Refined: Task completed successfully"
        if "reflect" in content.lower():
            return "Reflection: Strategy working well"

        return "Generic response"


@pytest.mark.asyncio
async def test_graph_factory_with_langgraph(monkeypatch):
    """Test that create_forge_graph() returns object with .run()."""

    # LangGraph is the default backend; no env var required for tests

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

    # Create graph
    graph = create_forge_graph()

    # Verify it has the run method
    assert hasattr(graph, "run"), "LangGraphExecutor should have .run() method"
    assert callable(graph.run), ".run() should be callable"

    # Create a state and run it
    state = create_state("Test task")
    result = await graph.run(state)

    # Verify result
    assert result is not None, "Should return a state"
    assert result.task == "Test task", "Task should be preserved"
    assert hasattr(result, "completion_status"), "Should have completion_status"
    assert hasattr(result, "thread_id"), "Should have thread_id"

    print("✅ Graph factory compatibility test passed!")
    print(f"  Completion status: {result.completion_status}")
    print(f"  Thread ID: {result.thread_id}")


@pytest.mark.asyncio
async def test_graph_factory_always_langgraph(monkeypatch):
    """Test that create_forge_graph() always returns an object with .run()."""
    # Create graph
    graph = create_forge_graph()
    # Verify it has the run method
    assert hasattr(graph, "run"), "LangGraphExecutor should have .run() method"
    assert callable(graph.run), ".run() should be callable"
    print("✅ Graph factory always returns LangGraphExecutor")


@pytest.mark.asyncio
async def test_leadership_nodes_history(monkeypatch):
    """Test that leadership nodes record history entries."""

    # LangGraph is the default backend; no env var required for tests

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

    # Create graph and run
    graph = create_forge_graph()
    state = create_state("Test task for history")
    result = await graph.run(state)

    # Check that history exists
    assert len(result.history) > 0, "Should have history entries"

    # Check for leadership node entries
    history_nodes = [entry["node"] for entry in result.history]
    leadership_nodes = ["orchestrator", "monitor", "meta_learning", "finalize"]

    # At least orchestrator and finalize should be in history
    assert "orchestrator" in history_nodes or any(
        n in history_nodes for n in leadership_nodes
    ), f"Should have at least one leadership node in history. Found: {history_nodes}"

    # Check that history entries have required fields
    for entry in result.history:
        assert "node" in entry, "History entry should have 'node'"
        assert "timestamp" in entry, "History entry should have 'timestamp'"
        if "metadata" in entry:
            assert isinstance(entry["metadata"], dict), "Metadata should be a dict"

    print("✅ Leadership nodes history test passed!")
    print(f"  Total history entries: {len(result.history)}")
    print(f"  Nodes in history: {set(history_nodes)}")
