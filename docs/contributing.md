# Contributing

## Repo map

- `anvil/`: primary Python package, CLI entrypoints, orchestration, providers, persistence, and harness logic
- `docs/`: canonical usage, contract, and roadmap documentation
- `examples/`: runnable examples for orchestration and harness workflows
- `scripts/`: developer utilities and ad-hoc helpers outside the packaged CLI
- `tests/`: pytest coverage for CLI, orchestration, and harness behavior

Preserved plans, historical notes, and future-planning material live under `docs/project_management/`.

## Public strategy docs first

If you are updating strategy-authoring docs or examples, route readers to these
surfaces first:

- [Strategy DSL public subset contract](strategy_dsl_public_subset_contract.md)
- [Public subset example pack](../examples/harness/public_subset/README.md)

The runnable harness YAML files under `examples/harness/strategies/` remain
useful fixture-backed coverage surfaces, but they are not the canonical public
`C3 v1` authoring examples unless a doc explicitly says otherwise.

The live public-boundary enforcement gate is `StrategyConfig.from_dict()`, and
preflight now adapts that parser-owned boundary for compatibility warnings and
invalid-config stop behavior.

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

Runnable internal planning fixture command:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .forge-harness-runs \
  --json
```

On `harness-run`, omitting `--workspace` defaults to the current working directory. The planning surface is intentionally bounded to one existing repo and will stop with `clarification_needed` or `failed` instead of implying a generic greenfield planner.

That strategy file remains internal and fixture-backed. The canonical public
`C3 v1` planning example now lives in the public subset example pack, while the
fixture-backed strategy remains a regression surface rather than public
authoring truth.
Canonical public planning now supports:

- `planning_execution.mode: graph_owned` for deterministic-only planning
- `planning_execution.mode: graph_owned_with_planner_review` plus
  `roles.planner.provider` for bounded read-only provider review layered on top
  of deterministic structure

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
