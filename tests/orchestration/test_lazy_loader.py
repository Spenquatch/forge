"""
Test suite for lazy provider initialization logic.

This file contains unit tests for the lazy provider initialization functionality
that was implemented in Slice 0.1.
"""

import pytest
from unittest.mock import patch, MagicMock

from anvil.config_loader import ProviderCfg
from anvil.providers import (
    clear_registry,
    register_provider_config,
    get_registry_status,
)
from anvil.orchestration.lazy_loader import (
    reload_config_lazy,
    get_provider_status_lazy
)


def test_reload_config_lazy_with_prewarm():
    """
    Test that reload_config_lazy works with prewarm=True.
    """
    # Mock the config loading and provider initialization
    with patch("anvil.orchestration.lazy_loader.load_config") as mock_load:
        # Mock providers config
        mock_providers = {
            "openai": ProviderCfg(
                type="openai",
                class_path="anvil.providers.openai.OpenAIProvider",
                key_env="OPENAI_API_KEY"
            ),
            "anthropic": ProviderCfg(
                type="anthropic",
                class_path="anvil.providers.anthropic.AnthropicProvider",
                key_env="ANTHROPIC_API_KEY"
            )
        }
        mock_load.return_value = (mock_providers, {})

        with patch("anvil.orchestration.lazy_loader.clear_registry") as mock_clear:
            with patch("anvil.orchestration.lazy_loader.register_provider_config") as mock_register:
                with patch("anvil.orchestration.lazy_loader.initialize_provider") as mock_init:
                    # Mock successful initialization
                    mock_init.return_value = True

                    # Test with prewarm=True
                    providers, default_pipeline = reload_config_lazy(prewarm=True)

                    # Verify the correct functions were called
                    mock_clear.assert_called_once()
                    mock_load.assert_called_once_with("config/models.yaml")
                    assert len(providers) == 2
                    assert "openai" in providers
                    assert "anthropic" in providers


def test_reload_config_lazy_without_prewarm():
    """
    Test that reload_config_lazy works with prewarm=False (default).
    """
    # Mock the config loading and provider initialization
    with patch("anvil.orchestration.lazy_loader.load_config") as mock_load:
        # Mock providers config
        mock_providers = {
            "openai": ProviderCfg(
                type="openai",
                class_path="anvil.providers.openai.OpenAIProvider",
                key_env="OPENAI_API_KEY"
            )
        }
        mock_load.return_value = (mock_providers, {})

        with patch("anvil.orchestration.lazy_loader.clear_registry") as mock_clear:
            with patch("anvil.orchestration.lazy_loader.register_provider_config") as mock_register:
                # Test with prewarm=False (default)
                providers, default_pipeline = reload_config_lazy(prewarm=False)

                # Verify the correct functions were called
                mock_clear.assert_called_once()
                mock_load.assert_called_once_with("config/models.yaml")
                assert len(providers) == 1
                assert "openai" in providers


def test_get_provider_status_lazy():
    """
    Test that get_provider_status_lazy returns correct status information.
    """
    with patch("anvil.orchestration.lazy_loader.get_registry_status") as mock_status:
        # Mock registry status response
        mock_status.return_value = {
            "initialized": ["openai"],
            "configured": ["anthropic", "openai"],
            "available": ["openai", "anthropic"]
        }

        result = get_provider_status_lazy()

        # Verify the response format
        assert "openai" in result
        assert "anthropic" in result
        assert result["openai"]["initialized"] is True
        assert result["anthropic"]["initialized"] is False
