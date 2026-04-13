# Forge CLI provider update

This update makes CLI agents first-class Forge providers while preserving the existing API and local provider model.

## Added

- `anvil/cli_agents/base.py`
  - reusable subprocess-based CLI execution layer
  - normalized invocation/result objects
  - transcript rendering for chat-style prompts
- `anvil/cli_agents/codex.py`
  - headless `codex exec` adapter
  - access/sandbox mapping
  - JSONL parsing and optional structured-output file support
- `anvil/cli_agents/claude_code.py`
  - headless `claude -p` adapter
  - `--bare` / JSON output / schema support
  - tool gating and budget/turn controls
- `anvil/providers/cli_provider.py`
  - Forge provider wrapper for CLI agents
- `anvil/providers/codex_cli.py`
- `anvil/providers/claude_code.py`
- `tests/test_cli_providers.py`
- `tests/test_config_validator_cli.py`
- `examples/03_run_codex_cli.py`
- `examples/04_run_mixed_cli.py`

## Updated

- `config/models.yaml`
  - CLI providers are now configured as normal providers
  - default pipeline prefers `codex_cli` / `claude_code`
  - OpenAI / Anthropic / local providers remain available
- `anvil/providers/__init__.py`
  - provider availability + fallback order now understands CLI providers
- `anvil/config_loader.py`
  - `ProviderCfg` now supports `binary`, `default_args`, and `env`
- `anvil/config_validator.py`
  - validates CLI binaries
  - accepts CLI runtime params
  - missing optional provider dependencies are warnings, not hard failures
- `anvil/orchestrator.py`
  - fallback order prefers CLI providers first
- `anvil/cli.py`
  - provider listing shows CLI metadata
  - command module now supports `python -m anvil.cli ...`
  - clearer runtime error if orchestration deps are missing
- `anvil/providers/base.py`
  - lightweight import fallback so CLI-provider tests can run without LangChain installed
- `examples/README.md`
  - new CLI-first examples and environment notes

## Expected environment

Install Forge normally, then ensure the CLI tools are available on `PATH` or set:

- `FORGE_CODEX_BIN`
- `FORGE_CLAUDE_BIN`

The config validator will warn about missing optional providers, but it will not fail the whole configuration just because API/local extras are not installed.

## Quick smoke checks

```bash
python -m anvil.cli list
python -m anvil.cli test codex_cli
python -m anvil.cli test claude_code
```

## Tests run for this update

```bash
python -m compileall anvil tests/test_cli_providers.py
pytest -q tests/test_cli_providers.py tests/test_config_validator_cli.py tests/test_usage.py tests/test_cli_utils.py tests/test_text_sanitize.py
```

Result: `27 passed`
