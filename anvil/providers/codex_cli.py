"""Codex CLI provider."""

from __future__ import annotations

from pathlib import Path
import tomllib

from anvil.cli_agents import BaseCliAgent, CodexCliAgent
from anvil.config_loader import ProviderCfg

from .cli_provider import CliProviderBase


class CodexCliProvider(CliProviderBase):
    def forces_default_model_arg(self) -> bool:
        # Codex CLI account support varies by auth mode. Let the CLI pick its own
        # default unless the caller explicitly requested a model override.
        return False

    def reported_model_name(self, explicit_model: str | None = None) -> str | None:
        if explicit_model:
            return explicit_model
        return _configured_codex_default_model()

    def build_agent(self, cfg: ProviderCfg) -> BaseCliAgent:
        return CodexCliAgent(cfg)


def _configured_codex_default_model() -> str | None:
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return None
    model = data.get("model")
    if model in (None, ""):
        return None
    return str(model)
