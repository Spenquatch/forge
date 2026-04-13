import os
from pathlib import Path

import pytest

from anvil.cli import list_providers
from anvil.config_loader import ProviderCfg
from anvil.config_validator import ConfigurationValidator


def _write_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


@pytest.mark.asyncio
async def test_list_providers_shows_status_lines(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    binary_path = tmp_path / "codex"
    _write_executable(binary_path)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    providers = {
        "codex_cli": ProviderCfg(
            type="cli",
            class_path="pathlib.Path",
            binary="codex",
            model_name="gpt-5-codex",
            models={"gpt-5-codex/*": {}},
        ),
        "openai": ProviderCfg(
            type="api",
            class_path="pathlib.Path",
            key_env="OPENAI_API_KEY",
            model_name="gpt-4o-mini",
            models={"gpt-4o-mini/*": {}},
        ),
    }

    monkeypatch.setattr("anvil.cli.reload_config", lambda: (providers, {}))
    monkeypatch.setattr(
        "anvil.cli.get_config_validator", lambda: ConfigurationValidator()
    )

    await list_providers()

    output = capsys.readouterr().out
    assert "Listing configured providers:" in output
    assert "  - codex_cli: cli (gpt-5-codex)" in output
    assert "    Status: ready" in output
    assert "  - openai: api (gpt-4o-mini)" in output
    assert "    Status: missing API key env OPENAI_API_KEY not set" in output
