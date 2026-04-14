from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from anvil.config_loader import ProviderCfg
from anvil.providers import clear_registry, is_provider_available, register_provider_config
from anvil.providers.claude_code import ClaudeCodeProvider
from anvil.providers.codex_cli import CodexCliProvider


CODEx_SCRIPT = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
output_path = None
if "-o" in args:
    output_path = pathlib.Path(args[args.index("-o") + 1])
if output_path is not None:
    output_path.write_text(json.dumps({"status": "ok", "source": "codex"}), encoding="utf-8")

print(json.dumps({"type": "thread.started", "thread_id": "codex-thread-1"}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Codex final answer"}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 7}}))
'''

CLAUDE_SCRIPT = r'''#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if "--json-schema" in args:
    payload = {
        "result": "ignored",
        "structured_output": {"status": "ok", "source": "claude"},
        "usage": {"input_tokens": 13, "output_tokens": 5},
        "session_id": "claude-session-1",
    }
else:
    payload = {
        "result": "Claude final answer",
        "usage": {"input_tokens": 9, "output_tokens": 4},
        "session_id": "claude-session-1",
    }
print(json.dumps(payload))
'''


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def fake_cli_bins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    codex_path = tmp_path / "codex"
    claude_path = tmp_path / "claude"
    _write_executable(codex_path, CODEx_SCRIPT)
    _write_executable(claude_path, CLAUDE_SCRIPT)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")
    return {"codex": str(codex_path), "claude": str(claude_path)}


@pytest.mark.asyncio
async def test_codex_cli_provider_text(fake_cli_bins: dict[str, str]) -> None:
    provider = CodexCliProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.codex_cli.CodexCliProvider",
            binary=fake_cli_bins["codex"],
            model_name="gpt-5-codex",
            models={"gpt-5-codex/*": {"execute": {"access": "read", "effort": "high"}}},
        )
    )

    result = await provider.chat(
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Explain the project."},
        ],
        role="execute",
    )

    assert result == "Codex final answer"
    assert provider.last_usage is not None
    assert provider.last_usage.input_tokens == 11
    assert provider.last_usage.output_tokens == 7
    assert "--json" in provider.last_command
    assert "--model" not in provider.last_command
    assert provider.last_run_metadata["thread_id"] == "codex-thread-1"
    assert provider.last_run_metadata["item_type_counts"]["agent_message"] == 1


@pytest.mark.asyncio
async def test_codex_cli_provider_structured_output(fake_cli_bins: dict[str, str]) -> None:
    provider = CodexCliProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.codex_cli.CodexCliProvider",
            binary=fake_cli_bins["codex"],
            model_name="gpt-5-codex",
            models={},
        )
    )

    result = await provider.generate(
        "Return structured output.",
        output_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}, "source": {"type": "string"}},
            "required": ["status", "source"],
        },
    )

    assert json.loads(result) == {"status": "ok", "source": "codex"}
    assert provider.last_structured_output == {"status": "ok", "source": "codex"}


@pytest.mark.asyncio
async def test_codex_cli_provider_respects_explicit_model_override(fake_cli_bins: dict[str, str]) -> None:
    provider = CodexCliProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.codex_cli.CodexCliProvider",
            binary=fake_cli_bins["codex"],
            model_name="gpt-5-codex",
            models={},
        )
    )

    await provider.chat(
        [{"role": "user", "content": "Use a specific model."}],
        role="execute",
        model="codex-mini-latest",
    )

    model_index = provider.last_command.index("--model")
    assert provider.last_command[model_index + 1] == "codex-mini-latest"
    assert provider.reported_model_name("codex-mini-latest") == "codex-mini-latest"


def test_codex_cli_provider_reports_configured_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: Path("/tmp/codex-home-test"))

    def _fake_read_text(self: Path, encoding: str = "utf-8") -> str:
        assert self == Path("/tmp/codex-home-test/.codex/config.toml")
        return 'model = "gpt-5.4"\n'

    monkeypatch.setattr("pathlib.Path.read_text", _fake_read_text)

    provider = CodexCliProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.codex_cli.CodexCliProvider",
            binary="codex",
            model_name="gpt-5-codex",
            models={},
        )
    )

    assert provider.reported_model_name() == "gpt-5.4"


@pytest.mark.asyncio
async def test_claude_code_provider_text(fake_cli_bins: dict[str, str]) -> None:
    provider = ClaudeCodeProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.claude_code.ClaudeCodeProvider",
            binary=fake_cli_bins["claude"],
            model_name="sonnet",
            models={"sonnet/*": {"execute": {"access": "write", "max_turns": 3}}},
        )
    )

    result = await provider.chat(
        [{"role": "user", "content": "Review the workflow."}],
        role="execute",
    )

    assert result == "Claude final answer"
    assert provider.last_usage is not None
    assert provider.last_usage.total_tokens == 13
    assert provider.last_command[0].endswith("claude")
    model_index = provider.last_command.index("--model")
    assert provider.last_command[model_index + 1] == "sonnet"
    assert "--bare" not in provider.last_command
    assert "--no-session-persistence" not in provider.last_command
    assert "<prompt omitted>" in provider.last_command
    assert "--allowedTools" in provider.last_command
    assert provider.reported_model_name() == "sonnet"


@pytest.mark.asyncio
async def test_claude_code_provider_merges_wildcard_role_defaults_with_explicit_overrides(
    fake_cli_bins: dict[str, str]
) -> None:
    provider = ClaudeCodeProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.claude_code.ClaudeCodeProvider",
            binary=fake_cli_bins["claude"],
            model_name="sonnet",
            models={
                "sonnet/*": {
                    "critique": {
                        "access": "read",
                        "effort": "medium",
                        "max_turns": 4,
                    }
                }
            },
        )
    )

    await provider.chat(
        [{"role": "user", "content": "Review the workflow."}],
        role="critique",
        model="sonnet-override",
        effort="high",
    )

    model_index = provider.last_command.index("--model")
    effort_index = provider.last_command.index("--effort")
    max_turns_index = provider.last_command.index("--max-turns")
    assert provider.last_command[model_index + 1] == "sonnet-override"
    assert provider.last_command[effort_index + 1] == "high"
    assert provider.last_command[max_turns_index + 1] == "4"


@pytest.mark.asyncio
async def test_claude_code_provider_structured_output(fake_cli_bins: dict[str, str]) -> None:
    provider = ClaudeCodeProvider(
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.claude_code.ClaudeCodeProvider",
            binary=fake_cli_bins["claude"],
            model_name="sonnet",
            models={},
        )
    )

    result = await provider.generate(
        "Return structured output.",
        output_schema={
            "type": "object",
            "properties": {"status": {"type": "string"}, "source": {"type": "string"}},
            "required": ["status", "source"],
        },
    )

    assert json.loads(result) == {"status": "ok", "source": "claude"}
    assert provider.last_structured_output == {"status": "ok", "source": "claude"}


def test_cli_providers_report_available_when_binary_exists(fake_cli_bins: dict[str, str]) -> None:
    clear_registry()
    register_provider_config(
        "codex_cli",
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.codex_cli.CodexCliProvider",
            binary=fake_cli_bins["codex"],
            model_name="gpt-5-codex",
            models={},
        ),
    )
    register_provider_config(
        "claude_code",
        ProviderCfg(
            type="cli",
            class_path="anvil.providers.claude_code.ClaudeCodeProvider",
            binary=fake_cli_bins["claude"],
            model_name="sonnet",
            models={},
        ),
    )

    assert is_provider_available("codex_cli") is True
    assert is_provider_available("claude_code") is True
