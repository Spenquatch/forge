import pytest

from anvil.config_loader import ProviderCfg
from anvil.providers.openai import OpenAIProvider


@pytest.fixture
def provider_config() -> ProviderCfg:
    return ProviderCfg(
        type="api",
        class_path="anvil.providers.openai.OpenAIProvider",
        key_env="OPENAI_API_KEY",
        model_name="gpt-4o-mini",
        models={
            "gpt-4o-mini/*": {
                "execute": {"temperature": 0.7, "max_tokens": 512},
                "critique": {"temperature": 0.4, "max_tokens": 300},
            }
        },
    )


class _DummyResponse:
    def __init__(self, content: str):
        self.content = content


class _DummyLLM:
    def __init__(self) -> None:
        self.model_copy_called = False
        self.bind_called = False
        self.last_update = None

    def model_copy(self, *, update=None, **_kwargs):
        self.model_copy_called = True
        self.last_update = update
        return self

    def bind(self, **_kwargs):
        self.bind_called = True
        return self

    def invoke(self, _messages):
        return _DummyResponse("FINAL:\nOK")


def test_normalize_langchain_params_keeps_max_tokens_and_stop(provider_config) -> None:
    provider = OpenAIProvider(provider_config)
    normalized = provider._normalize_langchain_params(
        {"temperature": 0.2, "max_tokens": 10, "stop": ["\n\n"]}
    )
    assert normalized["temperature"] == 0.2
    assert normalized["max_tokens"] == 10
    assert normalized["stop"] == ["\n\n"]
    assert "max_completion_tokens" not in normalized
    assert "stop_sequences" not in normalized


@pytest.mark.asyncio
async def test_chat_uses_model_copy_not_bind(provider_config) -> None:
    provider = OpenAIProvider(provider_config)
    provider._llm = _DummyLLM()
    result = await provider.chat(
        [{"role": "user", "content": "hi"}], role="execute", max_tokens=5
    )
    assert result == "FINAL:\nOK"
    assert provider._llm.model_copy_called is True
    assert provider._llm.bind_called is False
    assert provider._llm.last_update is not None


@pytest.mark.asyncio
async def test_chat_puts_unknown_params_into_model_kwargs(provider_config) -> None:
    provider = OpenAIProvider(provider_config)
    provider._llm = _DummyLLM()
    await provider.chat(
        [{"role": "user", "content": "hi"}],
        role="execute",
        response_format={"type": "json_object"},
    )
    assert provider._llm.model_copy_called is True
    update = provider._llm.last_update or {}
    assert "model_kwargs" in update
    assert update["model_kwargs"]["response_format"] == {"type": "json_object"}
