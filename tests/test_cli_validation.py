import os
from pathlib import Path

from anvil.cli import _validate_requested_provider_configurations
from anvil.config_loader import ProviderCfg
from anvil.config_validator import ConfigurationValidator


def _write_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def test_selected_cli_provider_validation_ignores_unrelated_missing_api_keys(
    tmp_path: Path, monkeypatch
) -> None:
    claude_path = tmp_path / "claude"
    _write_executable(claude_path)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    validator = ConfigurationValidator()
    providers_config = {
        "claude_code_sonnet": ProviderCfg(
            type="cli",
            class_path="pathlib.Path",
            binary="claude",
            model_name="sonnet",
            models={"sonnet/*": {}},
        ),
        "openai": ProviderCfg(
            type="api",
            class_path="pathlib.Path",
            key_env="OPENAI_API_KEY",
            model_name="gpt-4o-mini",
            models={"gpt-4o-mini/*": {}},
        ),
    }

    report = _validate_requested_provider_configurations(
        validator,
        providers_config,
        {"execute": "claude_code_sonnet"},
    )

    assert report.is_valid is True


def test_selected_api_provider_validation_still_fails_when_key_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    validator = ConfigurationValidator()
    providers_config = {
        "openai": ProviderCfg(
            type="api",
            class_path="pathlib.Path",
            key_env="OPENAI_API_KEY",
            model_name="gpt-4o-mini",
            models={"gpt-4o-mini/*": {}},
        ),
    }

    report = _validate_requested_provider_configurations(
        validator,
        providers_config,
        {"execute": "openai"},
    )

    assert report.is_valid is False
