# Forge

Forge is a modular AI agent system with two active repo surfaces:

- a harness for structured analysis-review and deterministic planning runs
- a leadership/orchestration foundation built on LangGraph for configurable multi-role execution

The harness builds on the same repo and thesis as the orchestration stack; it does not replace it.

## Quick start

Install dependencies:

```bash
poetry install
```

List configured providers and models:

```bash
poetry run python -m anvil list
```

Run the orchestration CLI:

```bash
poetry run python -m anvil run "Write a haiku" --stream
```

Run the analysis-review harness:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs
```

Run the deterministic planning harness:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs \
  --json
```

Successful planning runs publish `PLAN.md` and `plan.json`. Planning exits `0` only for `success`; `clarification_needed` and `failed` return exit code `1`.

Most provider-backed runs require API keys in `.env`, such as `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

## Test commands

Run the full test suite:

```bash
poetry run pytest -q
```

Run the offline LangGraph smoke coverage:

```bash
poetry run pytest -q tests/test_lg_offline_smoke.py
```

## Canonical docs

- [Contributing guide](docs/contributing.md)
- [Analysis-review contract](docs/analysis_review_contract.md)
- [Roadmap](docs/roadmap.md)
- [Examples](examples/README.md)
- [Scripts](scripts/README.md)
