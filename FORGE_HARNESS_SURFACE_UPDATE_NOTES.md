# Forge mini-harness surface update

This update adds a new task/strategy execution surface to Forge without removing or replacing the existing leadership/LangGraph path.

## What was added

- New `anvil.harness` package with:
  - task and strategy spec parsing
  - workspace write-policy enforcement
  - validator applicability / preflight logic
  - prompt builders and JSON schemas
  - report generation
  - runner for:
    - `single_pass`
    - `pfr_v1`
    - `analysis_review_v1`
- New standalone harness CLI:
  - `python -m anvil.harness.cli run ...`
  - `python -m anvil.cli harness-run ...`
- Exact-provider lookup support so the harness does not silently fall back to a different provider than the strategy requested.
- CLI provider tracking improvement:
  - `CliProviderBase` now stores the last CLI run result so the harness can capture command/output metadata cleanly.
- Example task/strategy files under `examples/harness/`
- Final-answer artifacts for harness runs:
  - `FINAL_ANSWER.json`
  - `FINAL_ANSWER.md`
- New targeted tests for:
  - harness runner flow
  - provider adapter JSON parsing
  - top-level CLI dispatch

## Design notes

- The existing Forge `run` / `stream` leadership flows are unchanged.
- The new harness surface is parallel and opt-in.
- CLI providers are first-class in the harness surface, but API/local providers still work through Forge's provider registry.
- For API/local providers, structured output is prompt-driven JSON parsing rather than native schema enforcement.
- For CLI providers (`codex_cli`, `claude_code`), the harness passes structured output schemas directly through the provider adapter.

## New commands

```bash
python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_codex_claude.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs
```

Standalone harness entrypoint:

```bash
python -m anvil.harness.cli run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_codex_claude.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs
```

## Validation performed here

Passed:

```bash
python -m compileall anvil
pytest -q tests/test_harness_runner.py tests/test_harness_provider_adapter.py tests/test_harness_cli_command.py
python -m anvil.cli harness-run --help
```

Note on full test suite in this container:

- `pytest -q` did not complete here because this environment does not have optional dependencies like `langgraph` and `langchain_core` installed, and some pre-existing Forge tests import those modules directly during collection.
- The new harness-specific surface itself compiled and passed its targeted tests.
