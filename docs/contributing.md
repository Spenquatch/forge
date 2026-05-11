# Contributing

## Repo map

- `anvil/`: primary Python package, CLI entrypoints, orchestration, providers, persistence, and harness logic
- `docs/`: canonical usage, contract, and roadmap documentation
- `examples/`: runnable examples for orchestration and harness workflows
- `scripts/`: developer utilities and ad-hoc helpers outside the packaged CLI
- `tests/`: pytest coverage for CLI, orchestration, and harness behavior

Preserved plans, historical notes, and future-planning material live under `docs/project_management/`.

## Setup

Install dependencies from the repo root:

```bash
poetry install
```

If you need optional provider backends, install the matching extras or use `poetry install -E all`.

## Current entrypoints

Non-harness CLI:

```bash
poetry run python -m anvil list
poetry run python -m anvil run "Write a haiku" --stream
```

Online provider verification:

```bash
poetry run python -m anvil test openai
```

Analysis-review harness:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs
```

For more runnable task and strategy examples, see [examples/README.md](../examples/README.md).

## Tests

Run the main suite:

```bash
poetry run pytest -q
```

Run the offline LangGraph smoke tests:

```bash
poetry run pytest -q tests/test_lg_offline_smoke.py
```

## Working conventions

- Keep contributor-facing docs anchored in `README.md`, this guide, the analysis-review contract, and the roadmap.
- Treat `config/models.yaml` as the source of truth for provider and role configuration.
- Update related docs and examples when changing CLI surfaces or configuration behavior.
