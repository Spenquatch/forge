# Forge

Forge is a modular AI agent system with two active repo surfaces:

- a harness for structured analysis-review and bounded deterministic existing-repo planning runs
- a leadership/orchestration foundation built on LangGraph for configurable multi-role execution

The harness builds on the same repo and thesis as the orchestration stack; it does not replace it.

## Public strategy subset

If you are authoring against the live bounded public `C3` strategy DSL, start
here first:

- [Strategy DSL public subset contract](docs/strategy_dsl_public_subset_contract.md)
- [Public subset example pack](examples/harness/public_subset/README.md)

Canonical public authoring is enforced at `StrategyConfig.from_dict()`, and
preflight reuses that boundary for legacy-warning and invalid-config behavior.
The runnable harness YAML files under `examples/harness/strategies/` remain
useful internal and fixture-backed examples, but they are not by themselves the
canonical public `C3 v1` authoring surface.

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

Run the runnable internal planning fixture:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .forge-harness-runs \
  --json
```

This harness command is distinct from the general orchestration entrypoint
`poetry run python -m anvil` shown above.

On `harness-run`, omitting `--workspace` uses the current working directory, so the planning command above is copy-pasteable from the repo root.

That planning strategy path remains a runnable internal harness fixture, not
the canonical public `C3 v1` example. For the live bounded public authoring
contract, start with the contract doc and public example pack linked above.

The deterministic planning surface is intentionally bounded: it plans against
one existing repo, scans only a limited evidence budget, and stops honestly
with `clarification_needed` or `failed` when the ask is out of corpus or
underspecified. Successful planning runs publish `PLAN.md` and `plan.json`
with C2 coverage, assumptions, uncovered-delta truth, and repo-derived
planning structure. Planning exits `0` only for `success`; `clarification_needed`
and `failed` return exit code `1`
and publish `summary.json` only with truthful coverage payloads.

Harness strategies use provider family keys from `config/models.yaml` such as `codex_cli` and `claude_code`, not raw binary names in the YAML files. CLI-backed families still respect `FORGE_CODEX_BIN` and `FORGE_CLAUDE_BIN` when you need to point at a local install.

Most provider-backed runs require API keys in `.env`, such as `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`, or a prior login for the corresponding CLI provider.

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

- [Strategy DSL public subset contract](docs/strategy_dsl_public_subset_contract.md)
- [Contributing guide](docs/contributing.md)
- [Analysis-review contract](docs/analysis_review_contract.md)
- [Roadmap](docs/roadmap.md)
- [Examples](examples/README.md)
- [Scripts](scripts/README.md)
