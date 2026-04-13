import pytest

import anvil.cli as cli_module


class _RecordingProvider:
    def __init__(self) -> None:
        self.generate_kwargs = None
        self.chat_kwargs = None

    async def get_model_info(self):
        return {"provider_type": "cli", "provider": "codexcli"}

    async def generate(self, prompt: str, **kwargs):
        self.generate_kwargs = kwargs
        return "generated"

    async def chat(self, messages, **kwargs):
        self.chat_kwargs = kwargs
        return "chat"


@pytest.mark.asyncio
async def test_test_provider_passes_skip_git_repo_check_for_codex_cli(
    monkeypatch,
) -> None:
    provider = _RecordingProvider()

    monkeypatch.setattr("anvil.cli.reload_config", lambda: ({}, {}))
    monkeypatch.setattr("anvil.cli.get_provider", lambda name: provider)

    await cli_module.test_provider("codex_cli")

    assert provider.generate_kwargs is not None
    assert provider.chat_kwargs is not None
    assert provider.generate_kwargs["skip_git_repo_check"] is True
    assert provider.chat_kwargs["skip_git_repo_check"] is True
