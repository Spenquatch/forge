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

These adjudicate strategies are runnable examples, not by themselves the authoritative focus-gate acceptance proof.

Repo-local fixture wiring coverage lives under `tests/fixtures/harness/m2_focus_gate_fixture_wiring/` and remains seam-regression-only wiring coverage.

Authoritative focus-gate acceptance uses `scripts/run_focus_gate_acceptance.py` with a local manifest based on `examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml`.
That canonical manifest template covers the full seam and artifact M3 acceptance matrix, including adjudicate, deliberate ambiguity, `never_ask`, and stale rerun-answer cases.

The legacy `scripts/run_m2_focus_gate_live_acceptance.py` entrypoint remains as an explicit compatibility shim. Its legacy local config name stays `examples/harness/live_acceptance/m2_focus_gate_local.yaml`, and it still accepts the old `strategies:` shorthand surface.
