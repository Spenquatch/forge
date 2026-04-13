"""Codex CLI provider."""

from __future__ import annotations

from anvil.cli_agents import BaseCliAgent, CodexCliAgent
from anvil.config_loader import ProviderCfg

from .cli_provider import CliProviderBase


class CodexCliProvider(CliProviderBase):
    def build_agent(self, cfg: ProviderCfg) -> BaseCliAgent:
        return CodexCliAgent(cfg)
