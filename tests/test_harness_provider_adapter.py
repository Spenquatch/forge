from __future__ import annotations

from pathlib import Path

from anvil.config_loader import ProviderCfg
from anvil.harness.providers import ForgeProviderAdapter, resolve_provider_name
from anvil.harness.types import RoleConfig, StageRequest
from anvil.providers.claude_code import ClaudeCodeProvider
from anvil.providers.codex_cli import CodexCliProvider


class _FakeApiProvider:
    model_name = "fake-api-model"
    cfg = ProviderCfg(type="api", class_path="fake.Provider", model_name="fake-api-model")
    last_run_metadata = {"request_id": "req-1"}
    last_command = []

    async def generate(self, prompt: str, role: str = "execute", **kwargs):
        assert role == "execute"
        assert "JSON schema" in prompt
        return '{"status":"done","summary":"ok","workspace_write_intent":"none","changes_made":[],"claims_to_verify":[],"tests_recommended":[],"known_risks":[],"confidence":0.72}'


class _FakeCfg:
    type = "api"


class _FakeCliCfg:
    type = "cli"


class _FakeCliResult:
    def __init__(self):
        self.exit_code = 1
        self.stdout_text = '{"type":"result","subtype":"success","is_error":true,"result":"You\'ve hit your limit · resets soon"}'
        self.stderr_text = ""
        self.command = ["fake-claude"]
        self.structured_output = {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": "You've hit your limit · resets soon",
        }
        self.metadata = {}
        self.usage = None


class _FakeCliFailureProvider:
    model_name = "fake-cli-model"

    def __init__(self):
        self.last_cli_result = _FakeCliResult()

    async def generate(self, prompt: str, role: str = "execute", **kwargs):
        raise RuntimeError("cli failed")


class _FakeSuccessfulCliWarningResult:
    def __init__(self):
        self.exit_code = 0
        self.stdout_text = '{"summary":"ok"}'
        self.stderr_text = (
            "WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt"
        )
        self.command = ["fake-claude"]
        self.structured_output = {"summary": "ok"}
        self.metadata = {}
        self.usage = None


class _FakeSuccessfulCliWarningProvider:
    model_name = "fake-cli-model"

    def __init__(self):
        self.last_cli_result = None

    async def generate(self, prompt: str, role: str = "execute", **kwargs):
        self.last_cli_result = _FakeSuccessfulCliWarningResult()
        return self.last_cli_result.stdout_text


class _FakeCodexSchemaFailureResult:
    def __init__(self):
        self.exit_code = 1
        self.stdout_text = "\n".join(
            [
                '{"type":"thread.started","thread_id":"codex-thread-1"}',
                '{"type":"error","message":"{\\"type\\":\\"error\\",\\"error\\":{\\"type\\":\\"invalid_request_error\\",\\"code\\":\\"invalid_json_schema\\",\\"message\\":\\"Invalid schema for response_format \\\\\\"codex_output_schema\\\\\\": Missing \\\\\\"verified_evidence_refs\\\\\\".\\"},\\"status\\":400}"}',
                '{"type":"turn.failed","error":{"message":"Invalid schema for response_format \\"codex_output_schema\\": Missing \\"verified_evidence_refs\\"."}}',
            ]
        )
        self.stderr_text = "WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt"
        self.command = ["fake-codex"]
        self.structured_output = {
            "type": "thread.started",
            "thread_id": "codex-thread-1",
        }
        self.metadata = {}
        self.usage = None


class _FakeCodexSchemaFailureProvider:
    model_name = "fake-cli-model"

    def __init__(self):
        self.last_cli_result = _FakeCodexSchemaFailureResult()

    async def generate(self, prompt: str, role: str = "execute", **kwargs):
        raise RuntimeError("cli failed")


def _write_claude_stub(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json

print(json.dumps({
    "result": "Claude final answer",
    "usage": {"input_tokens": 9, "output_tokens": 4},
    "session_id": "claude-session-1",
}))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_codex_retry_stub(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
output_path = None
if "-o" in args:
    output_path = pathlib.Path(args[args.index("-o") + 1])

model = None
if "--model" in args:
    model = args[args.index("--model") + 1]

if model == "gpt-5-codex":
    sys.stderr.write(
        "The 'gpt-5-codex' model is not supported when using Codex with a ChatGPT account. invalid_request_error\\n"
    )
    sys.exit(1)

if output_path is not None:
    output_path.write_text(json.dumps({"summary": "ok"}), encoding="utf-8")

print(json.dumps({"type": "thread.started", "thread_id": "codex-thread-1"}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Codex final answer"}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 7}}))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_provider_aliases_and_non_cli_json_parsing(tmp_path, monkeypatch):
    assert resolve_provider_name("codex") == "codex_cli"
    assert resolve_provider_name("claude") == "claude_code"
    assert resolve_provider_name("openai") == "openai"

    monkeypatch.setattr("anvil.harness.providers.get_provider_exact", lambda name: _FakeApiProvider())
    monkeypatch.setattr("anvil.harness.providers.get_provider_config", lambda name: _FakeCfg())

    adapter = ForgeProviderAdapter("openai")
    request = StageRequest(
        role_name="solver",
        role_config=RoleConfig(provider="openai", model="ignored-model", access="read"),
        prompt_text="Solve the task.",
        schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["done"]},
                "summary": {"type": "string"},
                "workspace_write_intent": {"type": "string", "enum": ["none"]},
                "changes_made": {"type": "array", "items": {"type": "string"}},
                "claims_to_verify": {"type": "array", "items": {"type": "string"}},
                "tests_recommended": {"type": "array", "items": {"type": "string"}},
                "known_risks": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "status",
                "summary",
                "workspace_write_intent",
                "changes_made",
                "claims_to_verify",
                "tests_recommended",
                "known_risks",
                "confidence",
            ],
        },
        cwd=str(tmp_path),
        out_dir=str(tmp_path / "stage"),
    )

    result = adapter.run(request)
    assert result.ok is True
    assert result.structured_output is not None
    assert result.structured_output["status"] == "done"
    assert result.raw_meta["model_override_ignored"] == "ignored-model"
    assert Path(result.stdout_path).exists()
    assert Path(result.raw_output_path or "").exists()
    assert Path(result.normalized_output_path or "").exists()
    assert Path(result.output_path or "").exists()


def test_provider_adapter_classifies_provider_failures_before_schema_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("anvil.harness.providers.get_provider_exact", lambda name: _FakeCliFailureProvider())
    monkeypatch.setattr("anvil.harness.providers.get_provider_config", lambda name: _FakeCliCfg())

    adapter = ForgeProviderAdapter("claude_code")
    request = StageRequest(
        role_name="critic",
        role_config=RoleConfig(provider="claude_code", model="sonnet", access="read", effort="high"),
        prompt_text="Critique this draft.",
        schema={
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["verdict", "summary"],
        },
        cwd=str(tmp_path),
        out_dir=str(tmp_path / "stage-failure"),
    )

    result = adapter.run(request)

    assert result.ok is False
    assert result.failure_kind == "quota_exhausted"
    assert result.failure_summary == "Provider quota exhausted: You've hit your limit · resets soon"
    assert result.schema_validation_errors == []
    assert "missing required field" not in (result.error or "")
    assert Path(result.stdout_path).exists()
    assert Path(result.raw_output_path or "").exists()
    assert Path(result.normalized_output_path or "").exists()
    assert Path(result.output_path or "").exists()


def test_provider_adapter_prefers_codex_stdout_error_events_over_stderr_noise(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "anvil.harness.providers.get_provider_exact",
        lambda name: _FakeCodexSchemaFailureProvider(),
    )
    monkeypatch.setattr("anvil.harness.providers.get_provider_config", lambda name: _FakeCliCfg())

    adapter = ForgeProviderAdapter("codex_cli")
    request = StageRequest(
        role_name="proposer",
        role_config=RoleConfig(provider="codex_cli", model="gpt-5.4-mini", access="read"),
        prompt_text="Return recommendations.",
        schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
            "required": ["summary"],
        },
        cwd=str(tmp_path),
        out_dir=str(tmp_path / "stage-codex-schema-failure"),
    )

    result = adapter.run(request)

    assert result.ok is False
    assert result.failure_kind == "provider_error"
    assert "invalid_json_schema" in (result.failure_summary or "")
    assert "verified_evidence_refs" in (result.failure_summary or "")
    assert "permission error" not in (result.failure_summary or "").lower()


def test_provider_adapter_keeps_successful_cli_stderr_in_error_artifact_only(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "anvil.harness.providers.get_provider_exact",
        lambda name: _FakeSuccessfulCliWarningProvider(),
    )
    monkeypatch.setattr("anvil.harness.providers.get_provider_config", lambda name: _FakeCliCfg())

    adapter = ForgeProviderAdapter("claude_code")
    request = StageRequest(
        role_name="critic",
        role_config=RoleConfig(provider="claude_code", model="sonnet", access="read"),
        prompt_text="Critique this draft.",
        schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
            "required": ["summary"],
        },
        cwd=str(tmp_path),
        out_dir=str(tmp_path / "stage-success-warning"),
    )

    result = adapter.run(request)

    assert result.ok is True
    assert result.structured_output == {"summary": "ok"}
    assert result.error is None
    assert result.failure_kind is None
    assert result.failure_summary is None
    assert Path(result.stderr_path).read_text(encoding="utf-8") == (
        "WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt"
    )


def test_provider_adapter_inherits_cli_role_defaults_for_mapped_analysis_review_roles(
    tmp_path, monkeypatch
):
    claude_bin = tmp_path / "claude"
    _write_claude_stub(claude_bin)
    provider_cfg = ProviderCfg(
        type="cli",
        class_path="anvil.providers.claude_code.ClaudeCodeProvider",
        binary=str(claude_bin),
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
    provider = ClaudeCodeProvider(provider_cfg)

    monkeypatch.setattr("anvil.harness.providers.get_provider_exact", lambda name: provider)
    monkeypatch.setattr("anvil.harness.providers.get_provider_config", lambda name: provider_cfg)

    adapter = ForgeProviderAdapter("claude_code")
    request = StageRequest(
        role_name="critic",
        role_config=RoleConfig(
            provider="claude_code",
            model="sonnet-override",
            effort="high",
            access="read",
        ),
        prompt_text="Critique this draft.",
        schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
            "required": ["summary"],
        },
        cwd=str(tmp_path),
        out_dir=str(tmp_path / "stage-merged-defaults"),
    )

    result = adapter.run(request)

    assert result.ok is False
    assert result.command[0] == str(claude_bin)
    model_index = result.command.index("--model")
    effort_index = result.command.index("--effort")
    max_turns_index = result.command.index("--max-turns")
    assert result.command[model_index + 1] == "sonnet-override"
    assert result.command[effort_index + 1] == "high"
    assert result.command[max_turns_index + 1] == "4"


def test_provider_adapter_retries_codex_models_yaml_model_and_reports_fallback_metadata(
    tmp_path, monkeypatch
):
    codex_bin = tmp_path / "codex"
    _write_codex_retry_stub(codex_bin)
    provider_cfg = ProviderCfg(
        type="cli",
        class_path="anvil.providers.codex_cli.CodexCliProvider",
        binary=str(codex_bin),
        model_name="gpt-5-codex",
        models={
            "gpt-5-codex/*": {
                "execute": {
                    "access": "read",
                    "effort": "medium",
                    "timeout_sec": 300,
                }
            }
        },
    )
    provider = CodexCliProvider(provider_cfg)

    monkeypatch.setattr("anvil.harness.providers.get_provider_exact", lambda name: provider)
    monkeypatch.setattr("anvil.harness.providers.get_provider_config", lambda name: provider_cfg)
    monkeypatch.setattr("anvil.providers.codex_cli._configured_codex_default_model", lambda: "gpt-5.4")

    adapter = ForgeProviderAdapter("codex_cli")
    request = StageRequest(
        role_name="proposer",
        role_config=RoleConfig(
            provider="codex_cli",
            effort="high",
            access="read",
        ),
        prompt_text="Return a summary.",
        schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
        cwd=str(tmp_path),
        out_dir=str(tmp_path / "stage-codex-fallback"),
    )

    result = adapter.run(request)

    assert result.ok is True
    assert "--model" not in result.command
    effort_index = result.command.index("-c")
    assert result.command[effort_index + 1] == 'model_reasoning_effort="high"'
    assert result.model == "gpt-5.4"
    assert result.raw_meta["provider_model_initial_attempt"] == "gpt-5-codex"
    assert result.raw_meta["provider_model_effective"] == "gpt-5.4"
    assert result.raw_meta["provider_model_effective_source"] == "codex_config"
    assert result.raw_meta["provider_model_fallback_used"] is True
    assert result.raw_meta["provider_model_attempt_count"] == 2
