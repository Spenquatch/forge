## examples/

Small, runnable examples for common Forge workflows.

Run these from the repo root (recommended):

```bash
poetry run python examples/00_offline_smoke.py
```

Some examples require API keys (see `.env`).



CLI-backed examples:

```bash
poetry run python examples/03_run_codex_cli.py
poetry run python examples/04_run_mixed_cli.py
```

These require the corresponding CLI binaries to be installed and available on `PATH` (or provided via `FORGE_CODEX_BIN` / `FORGE_CLAUDE_BIN`).


Harness task/strategy examples:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs
```

Trust-oriented analysis runs can use `examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml`.
That canonical `analysis_review_trust_*` entrypoint is attestation-first in M3A. Use `analysis_review_trust_legacy_*` only for explicit `legacy_full_review` compatibility checks.

Harness strategy YAML uses provider family keys from `config/models.yaml`, such as `codex_cli` and `claude_code`. CLI-backed families still honor `FORGE_CODEX_BIN` and `FORGE_CLAUDE_BIN` if you need to override the installed binary location.

Deterministic planning examples use the canonical strategy `examples/harness/strategies/deterministic_feature_planning_v1.yaml` with these bounded task fixtures:

- `examples/harness/tasks/deterministic_feature_planning_success.yaml`
- `examples/harness/tasks/deterministic_feature_planning_clarification.yaml`
- `examples/harness/tasks/deterministic_feature_planning_failed.yaml`

These planning fixtures are intentionally narrow: they plan one existing repo from bounded workspace evidence, and the clarification/failed fixtures are explicit stop-path fixtures rather than a broader planning capability.

Run the successful planning fixture from the repo root with:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .forge-harness-runs \
  --json
```

This harness command is distinct from the general orchestration entrypoint
`poetry run python -m anvil`.

On `harness-run`, omitting `--workspace` uses the current working directory, so the canonical repo-root command does not need extra setup. Successful planning runs emit `PLAN.md` and `plan.json` with C2 coverage, assumptions, and uncovered delta. The clarification and failed fixtures exercise the same strategy surface, return exit code `1`, and publish `summary.json` only with truthful coverage payloads. Repeat-run determinism coverage for the bounded planning corpus lives in `tests/test_harness_example_strategy_wiring.py`.

These adjudicate strategies are runnable examples, not by themselves the authoritative focus-gate acceptance proof.

Repo-local fixture wiring coverage lives under `tests/fixtures/harness/m2_focus_gate_fixture_wiring/` and remains seam-regression-only wiring coverage.

Authoritative focus-gate acceptance uses the shard manifest at `.gstack/m4-request-gate/orch/focus_gate_acceptance.yaml`.
Seed it from `examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`.
The canonical shard path provisions its own isolated git-backed workspace from `tests/fixtures/harness/m2_focus_gate_fixture_wiring/workspace`; do not manually prepare `/tmp` workspaces and do not pass `--workspace`.

Run preflight first:

```bash
poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance.yaml \
  --shard seam-adjudicate \
  --preflight-only
```

Then run the four authoritative shards under one `pass-id`:

```bash
poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance.yaml \
  --shard seam-adjudicate \
  --pass-id m4-final-001

poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance.yaml \
  --shard seam-deliberate \
  --pass-id m4-final-001

poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance.yaml \
  --shard artifact-adjudicate \
  --pass-id m4-final-001

poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance.yaml \
  --shard artifact-deliberate \
  --pass-id m4-final-001
```

The legacy `scripts/run_m2_focus_gate_live_acceptance.py` entrypoint remains as an explicit compatibility shim. Its legacy local config name stays `examples/harness/live_acceptance/m2_focus_gate_local.yaml`, and it still accepts the old `strategies:` shorthand surface, but its trust slot should still point at the canonical attestation-first `analysis_review_trust_*` strategy unless you are intentionally running a `legacy_full_review` compatibility check with an explicit `analysis_review_trust_legacy_*` file.
