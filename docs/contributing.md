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

Canonical repo-root planning harness command:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .forge-harness-runs \
  --json
```

On `harness-run`, omitting `--workspace` defaults to the current working directory. The planning surface is intentionally bounded to one existing repo and will stop with `clarification_needed` or `failed` instead of implying a generic greenfield planner.

Harness strategy YAML uses provider family keys from `config/models.yaml`, including `codex_cli` and `claude_code`. When those families back a run through a local CLI, Forge still respects `FORGE_CODEX_BIN` and `FORGE_CLAUDE_BIN`; API-backed providers still require credentials such as `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

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

Opt-in real-repo planning smoke:

```bash
examples/harness/live_acceptance/run_gsd_browser_session_lifecycle_smoke.sh \
  /path/to/gsd-browser
```

That smoke uses `examples/harness/live_acceptance/gsd_browser_session_lifecycle_planning.template.yaml` plus the canonical planning strategy to prove repo-derived seams on an external workspace. Keep it out of the default `pytest -q` path so the main suite stays self-contained and deterministic.

## Working conventions

- Keep contributor-facing docs anchored in `README.md`, this guide, the analysis-review contract, and the roadmap.
- Treat `config/models.yaml` as the source of truth for provider and role configuration.
- Update related docs and examples when changing CLI surfaces or configuration behavior.
