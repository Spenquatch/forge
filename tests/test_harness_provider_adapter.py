from __future__ import annotations

from pathlib import Path

from anvil.config_loader import ProviderCfg
from anvil.harness.providers import ForgeProviderAdapter, resolve_provider_name
from anvil.harness.types import RoleConfig, StageRequest


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
    assert Path(result.output_path or "").exists()
