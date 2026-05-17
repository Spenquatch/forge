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

    monkeypatch.setattr(
        "anvil.cli.reload_config", lambda: ({"codex_cli": object()}, {})
    )
    monkeypatch.setattr("anvil.cli.get_provider_exact", lambda name: provider)

    exit_code = await cli_module.test_provider("codex_cli")

    assert exit_code == 0
    assert provider.generate_kwargs is not None
    assert provider.chat_kwargs is not None
    assert provider.generate_kwargs["skip_git_repo_check"] is True
    assert provider.chat_kwargs["skip_git_repo_check"] is True


@pytest.mark.asyncio
async def test_test_provider_returns_nonzero_for_unknown_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "anvil.cli.reload_config", lambda: ({"codex_cli": object()}, {})
    )

    exit_code = await cli_module.test_provider("does_not_exist")

    assert exit_code == 2


@pytest.mark.asyncio
async def test_main_async_returns_nonzero_for_unknown_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "anvil.cli.reload_config", lambda: ({"codex_cli": object()}, {})
    )

    exit_code = await cli_module.main_async(["test", "does_not_exist"])

    assert exit_code == 2
