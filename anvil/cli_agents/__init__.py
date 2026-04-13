"""CLI agent adapters for headless agent binaries."""

from .base import BaseCliAgent, CliInvocationPlan, CliRunResult, render_messages_as_transcript
from .claude_code import ClaudeCodeCliAgent
from .codex import CodexCliAgent

__all__ = [
    "BaseCliAgent",
    "CliInvocationPlan",
    "CliRunResult",
    "render_messages_as_transcript",
    "CodexCliAgent",
    "ClaudeCodeCliAgent",
]
