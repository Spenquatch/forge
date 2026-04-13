"""Claude Code CLI provider."""

from __future__ import annotations

from anvil.cli_agents import BaseCliAgent, ClaudeCodeCliAgent
from anvil.config_loader import ProviderCfg

from .cli_provider import CliProviderBase


class ClaudeCodeProvider(CliProviderBase):
    def build_agent(self, cfg: ProviderCfg) -> BaseCliAgent:
        return ClaudeCodeCliAgent(cfg)
