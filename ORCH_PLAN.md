# ORCH_PLAN: M4 Request-Gate Closeout

## Summary

This document tracks the implementation contract for closing out M4 request-gate work on `feat/bounded-work-redesign`.

- Scope is closeout and operational honesty, not feature redesign.
- `focus_decision` remains the only public routing artifact.
- The authoritative acceptance path is the shard contract implemented by `scripts/run_focus_gate_acceptance.py`.
- Raw proof is generated output, not committed source of truth.

## Canonical Acceptance Contract

Canonical manifest:

- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/focus_gate_acceptance.yaml`

Seed template:

- `/Users/spensermcconnell/__Active_Code/forge/examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`

Shard inventory:

1. `seam-adjudicate`
2. `seam-deliberate`
3. `artifact-adjudicate`
4. `artifact-deliberate`

Each shard command must use one shared `pass-id`:

```bash
poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance.yaml \
  --shard <shard-name> \
  --pass-id <pass-id>
```

Aggregate closeout rule:

1. All four shards pass.
2. All four shard results come from one commit SHA and one `pass-id`.
3. Final metadata cites only fresh outputs from that pass.

## Workspace Provisioning

The canonical shard path provisions its own isolated workspace and must not depend on manual `/tmp` preparation.

Provisioning sequence per shard:

1. Create a fresh temp parent directory.
2. Copy `tests/fixtures/harness/m2_focus_gate_fixture_wiring/workspace` into `workspace/`.
3. Run `git init` inside the copied workspace.
4. Set local git identity for the temporary repo.
5. `git add .`
6. `git commit -m "baseline fixture seed"`
7. Verify:
   - `git rev-parse --is-inside-work-tree` is `true`
   - `git status --short` is empty
   - `git rev-parse HEAD` succeeds
8. Run the shard against that workspace only.

## Proof Hygiene

Committed closeout metadata is limited to:

- `.gstack/m4-request-gate/orch/focus_gate_acceptance.yaml`
- `.gstack/m4-request-gate/orch/status.md`
- `.gstack/m4-request-gate/orch/queue.yaml`
- `.gstack/m4-request-gate/orch/escalations.md`
- `.gstack/m4-request-gate/orch/metrics.md`
- `.gstack/m4-request-gate/orch/integration-plan.md`
- `.gstack/m4-request-gate/orch/runtime-freeze.md`
- `.gstack/m4-request-gate/orch/freeze.sha`
- `.gstack/m4-request-gate/orch/tasks/**`

Generated proof stays ignored:

- `.gstack/m4-request-gate/quarantine/**`
- `.forge-harness-runs-live/**`

Forbidden final-pass inputs:

- prior `.attempt*`
- prior `tmp-*`
- prior `WS5-06-workspace-path.txt`
- prior `summary.json` or `REPORT.md` references
- prior shard outputs from a different commit SHA or `pass-id`

## Hard Gates

1. No `anvil/harness/runner.py` change lands unless the new shard path reproduces a concrete runtime defect first.
2. `skip_git_repo_check: true` is forbidden in the authoritative shard path.
3. `.local.yaml` strategy overrides are forbidden in the authoritative shard path.
4. If the shard path cannot be made honest without manual `/tmp` prep or hidden local strategy hacks, closeout is blocked.
