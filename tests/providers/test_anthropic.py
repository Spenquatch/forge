import os
from unittest.mock import MagicMock, patch

import pytest

from anvil.config_loader import ProviderCfg
from anvil.providers.anthropic import AnthropicProvider


@pytest.fixture
def provider_config():
    return ProviderCfg(
        type="api",
        class_path="anvil.providers.anthropic.AnthropicProvider",
        key_env="ANTHROPIC_API_KEY",
        model_name="claude-3-haiku-20240307",
        models={
            "claude-3-haiku-20240307/*": {
                "execute": {"temperature": 0.7, "max_tokens": 512},
                "critique": {"temperature": 0.4, "max_tokens": 300},
            }
        },
    )


@pytest.fixture
def mock_anthropic_response():
    mock_response = MagicMock()

    # Set up the content attribute with a text attribute
    mock_content = MagicMock()
    mock_content.text = "This is a test response from Claude"

    # Set up the content list attribute
    mock_response.content = [mock_content]

    # Set up the embedding attribute
    mock_response.embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    return mock_response


@pytest.mark.asyncio
async def test_init_provider(provider_config):
    """Test provider initialization with mocked API key"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        provider = AnthropicProvider(provider_config)
        assert provider.model_name == "claude-3-haiku-20240307"
        assert provider.client.api_key == "test-key"


@pytest.mark.asyncio
async def test_generate(provider_config, mock_anthropic_response):
    """Test the generate method with mocked response"""
    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("anthropic.Anthropic") as mock_anthropic,
    ):

        # Set up the mock Anthropic client
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic.return_value = mock_client

        # Initialize provider and call generate
        provider = AnthropicProvider(provider_config)
        result = await provider.generate("Test prompt", temperature=0.5, max_tokens=100)

        # Check result and verify mock was called correctly
        assert result == "This is a test response from Claude"
        mock_client.messages.create.assert_called_once()

        # Check correct parameters were passed to create
        call_args = mock_client.messages.create.call_args[1]
        assert call_args["model"] == "claude-3-haiku-20240307"
        assert call_args["temperature"] == 0.5
        assert call_args["max_tokens"] == 100
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Test prompt"


@pytest.mark.asyncio
async def test_chat(provider_config, mock_anthropic_response):
    """Test the chat method with mocked response"""
    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("anthropic.Anthropic") as mock_anthropic,
    ):

        # Set up the mock Anthropic client
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic.return_value = mock_client

        # Initialize provider and call chat
        provider = AnthropicProvider(provider_config)
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant"},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, how can I help?"},
            {"role": "user", "content": "Tell me about Claude"},
        ]

        result = await provider.chat(messages, temperature=0.3)

        # Check result and verify mock was called correctly
        assert result == "This is a test response from Claude"
        mock_client.messages.create.assert_called_once()

        # Check that system message was extracted and other messages were formatted correctly
        call_args = mock_client.messages.create.call_args[1]
        assert call_args["system"] == "You are a helpful AI assistant"
        assert len(call_args["messages"]) == 3  # System message removed, 3 remaining
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][1]["role"] == "assistant"
        assert call_args["messages"][2]["role"] == "user"


@pytest.mark.asyncio
async def test_embed(provider_config, mock_anthropic_response):
    """Test the embed method with mocked response"""
    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("anthropic.Anthropic") as mock_anthropic,
    ):

        # Set up the mock Anthropic client
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_anthropic_response
        mock_anthropic.return_value = mock_client

        # Initialize provider and call embed
        provider = AnthropicProvider(provider_config)
        result = await provider.embed("Test text for embedding")

        # Check result and verify mock was called correctly
        assert result == [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_client.embeddings.create.assert_called_once()

        # Check model and input parameters
        call_args = mock_client.embeddings.create.call_args[1]
        assert "claude-3-haiku-20240307" in call_args["model"]
        assert call_args["input"] == "Test text for embedding"


@pytest.mark.asyncio
async def test_get_model_info(provider_config):
    """Test the get_model_info method"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        provider = AnthropicProvider(provider_config)
        model_info = await provider.get_model_info()

        assert model_info["model"] == "claude-3-haiku-20240307"
        assert model_info["provider"] == "anthropic"
        assert "chat" in model_info["capabilities"]
        assert model_info["context_window"] > 0  # Context window should be set
