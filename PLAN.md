# Closure Plan: Live Seam Parity Acceptance

## Purpose

The seam-selection slice is already landed.

The branch no longer needs another plan about how to introduce `primary_seam`, `secondary_seams_considered`, or recommendation seam bindings. Those surfaces already exist in:

- [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py)
- [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py)
- [anvil/harness/report.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py)
- [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py)
- [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md)

The branch is blocked by a narrower problem:

- real bounded and trust runs can still choose different canonical seams
- both runs can still publish `FINAL_ANSWER.*`
- the repo has no cross-run acceptance gate that fails on that divergence

This plan replaces the old milestone plan with the closure pass the repo actually needs.

## Current Status

The saved checkpoint for this branch is:

- [20260426-090856-seam-parity-closure-pass.md](/Users/spensermcconnell/.gstack/projects/forge/checkpoints/20260426-090856-seam-parity-closure-pass.md)

The approved design doc for the landed seam-contract milestone is:

- [spensermcconnell-feat-bounded-work-redesign-design-20260425-155529.md](/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260425-155529.md)

The latest live evidence reviewed for this closure pass is:

- bounded: `.forge-harness-runs/20260426T025522Z-recommend_automation_improvements-304a7127`
- trust: `.forge-harness-runs/20260426T025528Z-recommend_automation_improvements-6aac3032`

Observed live drift:

| Run | `analysis_review_status.primary_seam.seam_id` | `final_artifact_kind` |
|---|---|---|
| bounded | `release-automation-workflows` | `final_answer` |
| trust | `release-trigger-automation` | `final_answer` |

That is the blocker.

## Accepted Premises

1. The seam metadata contract is already shipped. Do not reopen the contract-design slice.
2. The remaining defect is missing parity enforcement across completed runs, not missing single-run seam structure.
3. The current offline parity regression is too synthetic because [_TrustCorroborationHarnessAdapter](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py) inherits [_BoundedCorroborationHarnessAdapter](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py).
4. The next complete fix is a closure pass: independent parity fixtures, paired-summary comparison, and a loud acceptance gate.
5. The future `adjudicate` or `deliberate` request gate remains a later milestone. It is not part of this closure pass.

## Exact Failure

The repo can now prove a lot about one run.

It still cannot prove that two runs over the same task and workspace agree on the same canonical seam.

What is already true:

1. Each run persists canonical seam state into `summary.json` under `analysis_review_status`.
2. Single-run semantic validation rejects malformed seam structures.
3. Reporting and projection preserve canonical seam state inside one run.
4. The harness CLI prints a `summary=` pointer for each run.

What is still false:

1. There is no checker that compares two `summary.json` files and fails on seam drift.
2. The main bounded vs trust parity regression shares a seam-selection implementation through inheritance.
3. A bounded run and a trust run can both exit cleanly even when their canonical seams differ.

## Step 0: Scope Challenge

### Recommended review mode

Use **HOLD SCOPE**.

This is not another seam-contract milestone.

This is a closure pass over the acceptance surface.

### What already exists

| Sub-problem | Existing code | Why it is enough |
|---|---|---|
| canonical seam state inside one run | [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py) | already writes `analysis_review_status.primary_seam`, secondaries, and recommendation seam bindings into the run summary |
| seam structure enforcement | [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py) | already rejects malformed single payloads |
| seam rendering and projection | [anvil/harness/report.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py) and [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py) | already expose canonical seam state for one run |
| run artifact pointer surface | [anvil/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/cli.py) | already prints the `summary.json` path that a pair checker should consume |
| offline replay precedent | [scripts/generate_topic_closure_replays.py](/Users/spensermcconnell/__Active_Code/forge/scripts/generate_topic_closure_replays.py) | already shows the repo pattern for a small verification helper living in `scripts/` |
| bounded/trust fixture family | [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py) | good place to harden parity tests, but only after trust stops inheriting bounded seam behavior |

### Minimum change that achieves the goal

Do not redesign prompts.

Do not redesign schemas.

Do not move seam choice into a new orchestration stage.

The minimum complete fix is:

1. Replace the inherited trust corroboration fixture with an independently authored trust fixture.
2. Add a paired-summary checker that compares canonical seam context across two persisted `summary.json` files.
3. Add offline positive and negative tests for that checker.
4. Add a manual live acceptance loop that reruns bounded and trust on the same task and workspace, then runs the checker.
5. Update `PLAN.md` and one short user-facing doc surface so closure evidence is reproducible.

Anything bigger is reopening the solved milestone.

### Complexity check

Expected touched files:

- `tests/test_harness_runner.py`
- `scripts/check_seam_parity.py`
- `tests/test_check_seam_parity.py`
- `README.md`
- `PLAN.md`

That is a small closure slice.

No new package surface is required.

No new runtime subsystem is justified.

### Search check

- **[Layer 1]** reuse persisted `summary.json` as the canonical comparison surface
- **[Layer 1]** reuse the existing `scripts/` replay-helper pattern
- **[Layer 3]** treat seam parity as a cross-run invariant, not a single-run validation problem

No external web search is needed.

### TODOS cross-reference

[TODOS.md](/Users/spensermcconnell/__Active_Code/forge/TODOS.md) does not block this slice.

Do not add a new TODO unless implementation exposes a follow-up that is clearly separate from seam parity closure.

### Completeness check

Take the complete version.

Replacing the synthetic fixture alone is not enough.

Adding a checker without live rerun commands is not enough.

Running live reruns without a machine-readable checker is not enough.

This is a lake:

- independent fixtures
- paired-summary checker
- positive and negative regressions
- live rerun acceptance

### Distribution check

No new artifact type.

The checker can live as a repo script invoked with `poetry run python`.

No packaging or release pipeline change is needed.

## Architecture Review

### Current blind spot

```text
bounded run
    │
    ├── emits summary.json with canonical seam state
    └── exits cleanly

trust run
    │
    ├── emits summary.json with canonical seam state
    └── exits cleanly

repo today
    │
    └── never compares the two summaries
            │
            └── seam drift survives as a "green" result
```

### Target closure flow

```text
same task + same workspace + same commit
    │
    ├── bounded run → summary.json
    ├── trust run   → summary.json
    │
    ▼
paired-summary checker
    │
    ├── compare primary_seam.seam_id
    ├── compare normalized primary_seam.paths
    ├── compare normalized secondary seam IDs
    ├── compare recommendation seam bindings
    └── fail hard if canonical seam state is missing
    │
    ▼
parity verdict
    │
    ├── PASS: bounded/trust share canonical seam context
    └── FAIL: branch cannot claim seam parity closure
```

### Plan slices

#### Slice 1: Independent parity fixtures

Change [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py) so the trust parity surface no longer inherits bounded seam selection behavior.

Requirements:

1. Shared helpers are fine.
2. Shared seam-selection implementation is not.
3. `_TrustCorroborationHarnessAdapter` must not subclass `_BoundedCorroborationHarnessAdapter`.
4. If the two fixtures share code, that shared code must live in helper functions that do not choose or mutate seam outputs.
5. One matched pair must prove that bounded and trust can independently arrive at the same seam.
6. One divergent pair must prove that the acceptance checker rejects drift even when both runs look otherwise publishable.

#### Slice 2: Paired-summary checker

Add `scripts/check_seam_parity.py`.

It should:

1. accept `--bounded-summary` and `--trust-summary`
2. load only canonical state from `summary.json`
3. normalize comparison inputs exactly this way:
   - `primary_seam.paths`: trim whitespace, require repo-relative strings, de-duplicate, then sort ascending
   - `secondary_seams_considered[*].seam_id`: trim whitespace, de-duplicate, then sort ascending
   - `recommendation_seam_bindings[*]`: reduce to `{recommendation_index, seam_id}`, trim `seam_id`, then sort by `recommendation_index`
4. compare these fields:
   - `analysis_review_status.primary_seam.seam_id`
   - normalized `analysis_review_status.primary_seam.paths`
   - normalized `analysis_review_status.secondary_seams_considered[*].seam_id`
   - normalized `analysis_review_status.recommendation_seam_bindings[*]`
5. ignore allowed downstream differences:
   - `recommendation_admissibility`
   - `publishability`
   - `final_artifact_kind`
6. support `--out`, defaulting to `./seam_parity_report.json`
7. emit a machine-readable report with this exact top-level shape:

```json
{
  "ok": true,
  "bounded_summary": "/abs/path/to/bounded/summary.json",
  "trust_summary": "/abs/path/to/trust/summary.json",
  "checks": {
    "primary_seam_id": {"ok": true, "bounded": "seam-a", "trust": "seam-a"},
    "primary_seam_paths": {"ok": true, "bounded": ["a.py"], "trust": ["a.py"]},
    "secondary_seam_ids": {"ok": true, "bounded": ["seam-b"], "trust": ["seam-b"]},
    "recommendation_seam_bindings": {
      "ok": true,
      "bounded": [{"recommendation_index": 1, "seam_id": "seam-a"}],
      "trust": [{"recommendation_index": 1, "seam_id": "seam-a"}]
    }
  },
  "mismatches": []
}
```

8. write one entry to `mismatches` per failed check, using only:
   - `primary_seam_id`
   - `primary_seam_paths`
   - `secondary_seam_ids`
   - `recommendation_seam_bindings`
   - `missing_canonical_state`
9. exit `0` only when `ok == true`; exit non-zero on drift, malformed summaries, or missing canonical seam state

Keep it outside `HarnessRunner`.

This is a cross-run acceptance helper, not a new single-run subsystem.

#### Slice 3: Live closure evidence

Closure is not done when offline tests pass.

Closure is done when fresh bounded and trust runs over the same task and workspace also pass the paired-summary checker.

Required artifacts:

- bounded `summary.json`
- trust `summary.json`
- emitted `seam_parity_report.json`

## Code Quality Review

The main code-quality risk is false confidence, not complexity.

The branch already has the habit of proving one-run canonicalization very well. The closure gap is that those proofs are being mistaken for paired-run parity.

The most important DRY call here is negative: do not build a second seam-state contract, a second reporting format, or a second orchestration path just to compare two summaries. The comparison surface already exists in `summary.json`.

## Test Review

### Code path coverage

```text
SEAM PARITY CLOSURE COVERAGE
============================
[+] tests/test_harness_runner.py
    │
    ├── [GAP] trust parity fixture is independently authored
    ├── [GAP] matched bounded/trust pair preserves canonical seam context
    └── [GAP] intentionally divergent pair still looks individually green but fails pair acceptance

[+] scripts/check_seam_parity.py
    │
    ├── [GAP] loads both summary.json files
    ├── [GAP] fails on missing canonical seam state
    ├── [GAP] compares primary seam id + paths
    ├── [GAP] compares secondary seam ids
    └── [GAP] compares recommendation seam bindings

[+] tests/test_check_seam_parity.py
    │
    ├── [GAP] same canonical seam pair passes
    ├── [GAP] primary seam id drift fails
    ├── [GAP] primary seam path drift fails
    ├── [GAP] secondary seam drift fails
    ├── [GAP] recommendation seam binding drift fails
    └── [GAP] artifact-kind divergence alone does not fail when canonical seam context matches

[+] live acceptance
    │
    ├── [GAP] bounded live rerun captured
    ├── [GAP] trust live rerun captured
    └── [GAP] checker passes on the fresh pair

---------------------------------
COVERAGE TARGET: 14/14 paths locked
QUALITY TARGET: all new assertions ★★★
---------------------------------
```

### Required test commands

Run exactly these:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_check_seam_parity.py
```

Do not extract or share replay utilities for this closure pass.

`scripts/check_seam_parity.py` is a standalone helper and must not depend on `scripts/generate_topic_closure_replays.py`.

### Manual acceptance

Run bounded and trust over the same repo snapshot and workspace.

Rules:

1. Use the same checked-out commit for both runs.
2. Do not edit the repo between the bounded and trust runs.
3. Use the same `--task`, the same `--workspace`, and the same `--out-root`.
4. Capture the `summary=` line printed by each command. Do not discover runs by globbing `.forge-harness-runs`.

Exact command flow:

```bash
set -euo pipefail

BOUNDED_SUMMARY=$(
  poetry run python -m anvil.cli harness-run \
    --task examples/harness/tasks/recommend_automation_improvements.yaml \
    --strategy examples/harness/strategies/analysis_review_bounded_codex_claude.yaml \
    --workspace /path/to/repo \
    --out-root .forge-harness-runs | awk -F= '/^summary=/{print $2}'
)

TRUST_SUMMARY=$(
  poetry run python -m anvil.cli harness-run \
    --task examples/harness/tasks/recommend_automation_improvements.yaml \
    --strategy examples/harness/strategies/analysis_review_trust_codex_claude.yaml \
    --workspace /path/to/repo \
    --out-root .forge-harness-runs | awk -F= '/^summary=/{print $2}'
)

test -n "$BOUNDED_SUMMARY"
test -n "$TRUST_SUMMARY"

poetry run python scripts/check_seam_parity.py \
  --bounded-summary "$BOUNDED_SUMMARY" \
  --trust-summary "$TRUST_SUMMARY" \
  --out ./seam_parity_report.json
```

Manual acceptance criteria:

1. bounded and trust expose the same `primary_seam.seam_id`
2. bounded and trust expose the same normalized `primary_seam.paths`
3. bounded and trust expose the same canonical secondary seam IDs
4. bounded and trust expose the same recommendation-to-seam bindings
5. parity still passes when bounded and trust differ in admissibility or publication
6. the checker fails hard if either run omits canonical seam state
7. `./seam_parity_report.json` exists and records `"ok": true`

## Performance Review

No meaningful runtime risk is expected.

The checker is offline and cross-run.

The only runtime-adjacent cost is reading two `summary.json` files, which is trivial.

## Failure Modes Registry

| Failure mode | Test covers it | Error handling exists | User-visible impact | Required mitigation |
|---|---|---|---|---|
| trust and bounded choose different `primary_seam.seam_id` | not yet | no | branch looks green while the product invariant is false | paired-summary checker must fail non-zero |
| seam IDs match but `primary_seam.paths` differ | not yet | no | users see the same seam label masking different actual review surfaces | checker must compare normalized path sets |
| secondary seam IDs drift while primary seam matches | not yet | no | parity looks cleaner than it is, especially for corroboration scope | checker must compare secondary seam IDs |
| recommendation seam bindings drift while primary seam matches | not yet | no | canonical seam choice looks aligned but the actual recommendations are grounded on different seams | checker must compare recommendation seam bindings |
| both runs publish `FINAL_ANSWER.*` and no pair gate notices | not yet | no | false release confidence | negative pair regression and live checker command |
| one run downgrades to `PARTIAL_ANSWER.*` and checker reads artifact payload instead of `summary.json` | not yet | no | allowed publication divergence is mistaken for seam drift, or real seam drift is missed | checker must read only canonical `summary.json` state |
| trust fixture still inherits bounded seam behavior | partially | no | offline parity test stays green even if real trust behavior drifts | independently author trust fixture |

Critical gap to avoid: a closure pass that replaces the synthetic fixture but still lacks a machine-readable paired acceptance gate.

## What Already Exists

Use these instead of rebuilding anything:

- canonical seam state in `summary.json`
- runner-owned `analysis_review_status`
- current reporting/projection surfaces
- current harness-run CLI summary pointer
- current `scripts/` replay-helper pattern

## NOT in Scope

- redesigning seam metadata fields
- redesigning semantic validation for single-run payload structure
- redesigning report rendering unless the checker exposes a real canonical-state bug
- moving seam choice into a new orchestration phase
- `adjudicate` / `deliberate` request-gate work
- LangGraph parity work
- new package or deploy surfaces

## TODOS.md

No new TODO should be added from this closure pass.

If a later follow-up wants a richer dashboard for paired-run comparison, that should be a separate milestone after parity closure is green.

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|------|-----------------|------------|
| independent trust fixture + runner parity regressions | `tests/` | — |
| paired-summary checker | `scripts/` | — |
| checker unit tests | `tests/` | paired-summary checker |
| README / command docs | repo docs | checker command settled |
| live rerun evidence | run artifacts | fixture + checker complete |

### Parallel lanes

- Lane A: independent trust fixture and bounded/trust runner parity regressions
- Lane B: `scripts/check_seam_parity.py`
- Lane C: checker unit tests after Lane B
- Lane D: README command updates after Lane B
- Lane E: live rerun evidence after Lane A, B, and C

### Execution order

Launch Lane A and Lane B in parallel.

Then run Lane C and Lane D.

Then run Lane E as the closure lane.

### Conflict flags

- Lane A and Lane C both touch `tests/`, so they should not edit the same file in parallel.
- Everything else is cleanly separable.

## Completion Summary

- Step 0: Scope Challenge, hold scope accepted
- Design Review: skipped, no UI scope
- Architecture Review: complete
- Code Quality Review: complete
- Test Review: diagram produced, 14 coverage targets identified
- Performance Review: 0 issues
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none
- Failure modes: 1 critical gap currently open, missing paired-run acceptance
- Outside voice: ran via `codex exec`, agreed the closure blocker is the missing paired-summary acceptance gate
- Parallelization: 5 lanes, 2 initial lanes, 2 follow-on lanes, 1 closure lane
- Lake Score: 6/6 key decisions chose the complete option

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Replace the old seam-contract implementation plan with a closure-pass acceptance plan | mechanical | pragmatic | the contract slice is already landed and the live blocker is cross-run drift | continuing to plan already-shipped seam metadata work |
| 2 | Eng | Treat the blocker as missing paired-run acceptance, not missing single-run seam structure | mechanical | explicit over clever | the repo already stores canonical seam state per run | reopening schema or validator design |
| 3 | Eng | Independently author the trust parity fixture | mechanical | explicit over clever | inheritance keeps the current parity regression artificially green | relying on shared bounded seam behavior |
| 4 | Eng | Put the checker in `scripts/` instead of `HarnessRunner` | taste | minimal diff | the invariant is cross-run and offline, not part of single-run orchestration | adding a new core runtime subsystem |
| 5 | Eng | Compare canonical `summary.json` seam state, not final artifact payloads | mechanical | engineered enough | publication may diverge while seam parity still holds | reading `FINAL_ANSWER.*` or `PARTIAL_ANSWER.*` as the parity source |
| 6 | CEO | Keep request-gate ideas explicitly out of this pass | mechanical | boil the lake | closure should finish the current milestone before starting the next one | folding `adjudicate` or `deliberate` into parity closure |

## Autonomous Review Report

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Checkpoint Recovery | `/checkpoint` | Restore live blocker and last accepted direction | 1 | complete | Confirmed the slice is structurally landed but behaviorally incomplete in live runs |
| Outside Voice | `codex exec` | Independent plan challenge | 1 | aligned | Outside review agreed the missing paired-summary acceptance gate is the blocking gap |
| Eng Review | autonomous synthesis | Architecture, tests, failure modes | 1 | open_until_implemented | Required 3 concrete work items: independent trust fixtures, paired-summary checker, fresh live acceptance evidence |
| Design Review | skipped | UI/UX gaps | 0 | skipped | No UI scope |

**VERDICT:** DO NOT REOPEN THE SEAM-CONTRACT MILESTONE. Close live seam parity by proving bounded and trust agree on canonical seam context across fresh paired summaries, then move to the request-gate milestone.
