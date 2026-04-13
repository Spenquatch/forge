"""Shared test fixtures and configuration.

Adds the project root to sys.path so tests can import the local `anvil` package
without requiring PYTHONPATH or an editable install.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest


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


@pytest.fixture
def mock_providers(monkeypatch):
    """Fixture to mock provider system for offline testing."""
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

    return fake_provider
