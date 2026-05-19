# ORCH_PLAN: C2 Honest Live Planning Alignment

## 1. Summary

Repository: `/home/azureuser/__Active_Code/forge`  
Integration branch: `codex/c1b-planning-quality-proof`  
Authority file: `/home/azureuser/__Active_Code/forge/PLAN.md`  
Authority title: `C2 Honest Live Planning Alignment`  
Milestone: `C2`

This file is the parent-owned orchestration runbook for carrying the current
`PLAN.md` session to completion. It replaces the stale root orchestration plan.

Parent-agent ownership model:

- The parent owns kickoff, freeze decisions, worktree creation, worker packets,
  merge order, conflict resolution, reopen decisions, final verification, and
  milestone closeout.
- The parent is the only integrator.
- Workers execute bounded lanes only and return handoffs; they do not merge,
  rebase for integration, or widen scope.

Worker model:

- model: `GPT-5.4`
- reasoning: `high`
- maximum concurrent worker lanes: `2`

Completion means the integrated tree on
`codex/c1b-planning-quality-proof` satisfies the current `PLAN.md` end to end:

- live planning truth is repo-derived rather than scaffold-derived
- `anvil/harness/planning_runtime.py` remains the single live runtime family
- success runs still publish `PLAN.md` and `plan.json` only on success
- blocked/failed runs still publish `summary.json` only
- the current coverage contract stays intact unless a narrow metadata-preserving
  patch is required
- `tests/test_harness_planning_graph.py` and
  `tests/test_harness_example_strategy_wiring.py` stop encoding canonical seam
  IDs as live truth
- at least one outside-repo canary against
  `/home/azureuser/__Active_Code/gsd-browser` proves non-canonical live seams

## 2. Hard Guards

1. `/home/azureuser/__Active_Code/forge/PLAN.md` is authoritative. If this file
   and `PLAN.md` disagree, follow `PLAN.md`.
2. Do not edit `PLAN.md`.
3. No `planning_v2`.
4. No strategy-name branching.
5. No second runtime family.
6. No provider-backed seam synthesis.
7. No helper-family sprawl such as `*_v2`, `*_live_v2`, or parallel publishing
   stacks.
8. Preserve the existing bounded discovery budget in
   `anvil/harness/planning_runtime.py` unless a strictly minimal bug fix is
   required to preserve current behavior.
9. Preserve success-only `PLAN.md` and `plan.json`, and preserve summary-only
   blocked/failed behavior.
10. Preserve the current coverage contract unless a minimal metadata-preservation
    patch is required for truthful phase output publication.
11. Keep fixture truth distinct from live truth. Fixture/example scaffolding may
    remain deterministic, but it must not masquerade as the live success path.
12. `_CANONICAL_SEAM_SPECS` must not remain in the live success path.
13. The true bottleneck is `anvil/harness/planning_runtime.py`; do not
    over-parallelize lanes that couple on that file.
14. The parent is the only integrator.
15. A lane that discovers required scope outside its packet must stop and reopen
    rather than freelancing into peer-owned files.

## 3. Parent Critical Path

### 3.1 Serialized and Parallel Phases

| Phase | Task IDs | Owner | Mode | Exit gate |
|---|---|---|---|---|
| A. Authority and freeze | `task/c2h-a1` to `task/c2h-a7` | Parent | serialized | `gate/c2h-authority-freeze` |
| B. Phase-1 runtime gate | `task/c2h-b1` to `task/c2h-b5` | `WS-B` | serialized after A | `gate/c2h-phase1-runtime` |
| BF. Phase-1 freeze publication | `task/c2h-bf1` to `task/c2h-bf4` | Parent | serialized | `gate/c2h-phase1-freeze` |
| C. Structural derivation runtime | `task/c2h-c1` to `task/c2h-c5` | `WS-C` | serialized after BF | `gate/c2h-structure-runtime` |
| D. Artifact-truth lane | `task/c2h-d1` to `task/c2h-d6` | `WS-D` | starts after BF; final merge waits for C | `gate/c2h-artifact-truth` |
| E. Regression and canary wall | `task/c2h-e1` to `task/c2h-e6` | `WS-E` | after C and D merge | `gate/c2h-regression-canary` |
| F. Final parent closeout | `task/c2h-f1` to `task/c2h-f9` | Parent | serialized | `gate/c2h-final` |

### 3.2 Fixed Merge Order

1. Parent-local Phase A freeze only
2. `WS-B` phase-1 runtime gate
3. Parent-local phase-1 freeze publication
4. `WS-C` structural derivation runtime
5. `WS-D` artifact-truth lane
6. `WS-E` regression and canary wall
7. Parent-only final verification and closeout

### 3.3 Do-Not-Proceed Conditions

- Do not dispatch any worker before `gate/c2h-authority-freeze` passes.
- Do not dispatch `WS-C` before `WS-B` is merged and the parent publishes
  `phase1-runtime-freeze.md`.
- Do not merge `WS-D` before `WS-C` is merged, even if `WS-D` started earlier.
- Do not dispatch `WS-E` before `WS-C` and `WS-D` are both merged.
- Do not proceed if a lane requires a second runtime family, strategy-name
  branching, or coverage-contract churn.
- Do not proceed if the only way to preserve truthful phase metadata is a broad
  schema redesign. Stop and reopen.
- Do not proceed to milestone closeout until the `gsd-browser` canary proves
  non-canonical seams and clean downstream linkage.

### 3.4 Realistic Coupling Rules

- `anvil/harness/planning_runtime.py` is single-owner at any moment.
- `WS-B` and `WS-C` are strictly serialized because both materially change
  `planning_runtime.py`.
- `WS-D` may start after the phase-1 freeze, but it may not touch
  `planning_runtime.py`. If it uncovers a required runtime change, parent reopens
  `WS-C`.
- `WS-E` is regression-first. It does not backdoor product logic changes.

## 4. Repo-Local Orchestration State Root

Repo-local state root:

- `/home/azureuser/__Active_Code/forge/.runs/c2-honest-live-planning-alignment-orch/`

Required layout:

- `queue.md`
- `state.json`
- `invariants.md`
- `authority-notes.md`
- `runtime-rule-freeze.md`
- `phase1-runtime-freeze.md`
- `structure-output-freeze.md`
- `canary-targets.md`
- `session.log`
- `handoffs/`
- `gates/`
- `logs/`
- `sentinels/`
- `acceptance/c2h-acceptance-checklist.md`
- `acceptance/final-gate-report.md`
- `canary/gsd-browser-task.yaml`
- `canary/out/`

File roles:

- `queue.md`: one row per `task/c2h-*` with owner, state, lane, gate, merge
  status, and reopen reason
- `state.json`: current phase, active worktrees, blocker status, freeze status,
  gate results, and canary result
- `invariants.md`: frozen hard guards, file ownership boundaries, and stop rules
- `authority-notes.md`: parent restatement of the current `PLAN.md`, repo facts,
  and branch-local scope
- `runtime-rule-freeze.md`: frozen heuristics, tie-break rules, ID recipes,
  artifact behavior rules, and banned approaches
- `phase1-runtime-freeze.md`: parent-approved phase-1 output contract after
  `WS-B` merges, including `primary_cut_summary` expectations
- `structure-output-freeze.md`: parent-approved seam/workstream/slice output
  shape after `WS-C` merges
- `canary-targets.md`: exact canary repo path, task prompt, command, and success
  rubric for `gsd-browser`
- `session.log`: parent-only chronological log of dispatches, merges, gate
  reruns, blockers, and final verdicts
- `handoffs/`: one worker packet and one return handoff per lane
- `gates/`: exact commands, exit codes, and parent verdicts for every gate
- `logs/`: captured pytest and canary logs
- `sentinels/`: lightweight readiness and blocker signals

Sentinel conventions:

- `task-c2h-*.dispatched`
- `task-c2h-*.ready`
- `task-c2h-*.blocked`
- `task-c2h-*.merged`
- `task-c2h-*.failed-gate`

## 5. Worktree and Branch Plan

Integration worktree:

- path: `/home/azureuser/__Active_Code/forge`
- branch: `codex/c1b-planning-quality-proof`
- owner: Parent only

Sibling worktree root:

- `/home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/`

Worker lanes:

- `WS-B`
  - path:
    `/home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-b-phase1-runtime`
  - branch: `codex/c2-honest-live-alignment-ws-b-phase1-runtime`
  - purpose: `design_doc` truth, primary cut, live clarification gate
- `WS-C`
  - path:
    `/home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-c-structure-runtime`
  - branch: `codex/c2-honest-live-alignment-ws-c-structure-runtime`
  - purpose: repo-derived seams, workstreams, slices, stable IDs
- `WS-D`
  - path:
    `/home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-d-artifact-truth`
  - branch: `codex/c2-honest-live-alignment-ws-d-artifact-truth`
  - purpose: reporting/state metadata preservation, docs, examples, fixture
    wording, artifact-truth tests
- `WS-E`
  - path:
    `/home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-e-regression-canary`
  - branch: `codex/c2-honest-live-alignment-ws-e-regression-canary`
  - purpose: last-mile regression wall and outside-repo canary proof

Worktree creation commands:

```bash
mkdir -p /home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-b-phase1-runtime \
  -b codex/c2-honest-live-alignment-ws-b-phase1-runtime \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-c-structure-runtime \
  -b codex/c2-honest-live-alignment-ws-c-structure-runtime \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-d-artifact-truth \
  -b codex/c2-honest-live-alignment-ws-d-artifact-truth \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge.worktrees/c2-honest-live-planning-alignment/ws-e-regression-canary \
  -b codex/c2-honest-live-alignment-ws-e-regression-canary \
  codex/c1b-planning-quality-proof
```

## 6. Worker Packet Minimums and Reopen Rules

Every worker packet must include:

- exact task IDs
- authority path to `/home/azureuser/__Active_Code/forge/PLAN.md`
- lane purpose and freeze prerequisites
- allowed files
- forbidden files
- lane-local commands
- acceptance criteria
- merge preconditions
- handoff path under
  `/home/azureuser/__Active_Code/forge/.runs/c2-honest-live-planning-alignment-orch/handoffs/`

Every worker return must include:

- changed files
- commands run with exit codes
- concise task-by-task summary
- blockers or residual risks
- explicit note whether any frozen contract was pressured
- explicit note whether any forbidden file would be needed for full completion

Mandatory reopen triggers:

- touching `PLAN.md`
- introducing `planning_v2`, strategy-name branching, provider synthesis, or
  helper-family sprawl
- changing success-only vs blocked/failed artifact behavior
- widening the coverage contract instead of preserving it narrowly
- touching peer-owned files without parent approval
- `WS-D` touching `anvil/harness/planning_runtime.py`
- `WS-E` changing product logic instead of routing failures back to owning lanes
- missing commands, missing exit codes, or missing handoff

## 7. Detailed Workstream Plan

### 7.1 Phase A: Parent-Local Freeze and Authority Pass

Parent-owned tasks:

- `task/c2h-a1-read-authority`
  - Read:
    - `/home/azureuser/__Active_Code/forge/PLAN.md`
    - `/home/azureuser/__Active_Code/forge/ORCH_PLAN.md`
    - `/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py`
    - `/home/azureuser/__Active_Code/forge/anvil/harness/reporting.py`
    - `/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py`
    - `/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`
- `task/c2h-a2-freeze-hard-guards`
  - Write `invariants.md` and restate the non-negotiables from `PLAN.md`.
- `task/c2h-a3-freeze-runtime-rules`
  - Write `runtime-rule-freeze.md` with:
    - two-signal primary-cut rule
    - stable ID recipes
    - workflow-boundary -> module/package -> integration seam fallback order
    - bounded discovery budget
    - success-only vs summary-only publication rules
- `task/c2h-a4-create-state-root`
  - Create the `.runs/c2-honest-live-planning-alignment-orch/` layout.
- `task/c2h-a5-create-worktrees`
  - Create all sibling worktrees and branches.
- `task/c2h-a6-seed-canary-target`
  - Write `canary-targets.md` and
    `canary/gsd-browser-task.yaml` for a bounded real feature ask against
    `/home/azureuser/__Active_Code/gsd-browser`.
- `task/c2h-a7-dispatch-ws-b`
  - Open `WS-B` only after the freeze files exist.

Acceptance for Phase A:

- `gate/c2h-authority-freeze` passes only when `runtime-rule-freeze.md`,
  `invariants.md`, `queue.md`, `state.json`, and `canary-targets.md` exist and
  accurately restate the current branch scope.

### 7.2 Phase B: WS-B Phase-1 Runtime Gate

Lane purpose:

- make `design_doc` honest before any seam/workstream/slice derivation begins

Owned files:

- `/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py`

Forbidden files:

- `PLAN.md`
- `anvil/harness/reporting.py`
- `anvil/harness/state.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_example_strategy_wiring.py`

Tasks:

- `task/c2h-b1-remove-live-scaffold-bias`
  - strip live canonical weighting from `_score_path()`
  - stop scaffold reinjection in `_discovered_workspace_matches()`
- `task/c2h-b2-implement-primary-cut-selection`
  - add or extend the smallest in-file helper(s) needed for cluster scoring and
    the two-signal credibility rule
- `task/c2h-b3-make-clarification-feature-specific`
  - remove the canned runtime-routing vs artifact-publication clarification from
    credible live paths
- `task/c2h-b4-thread-phase1-truth`
  - preserve `search_pass_count`, `inspected_file_count`,
    `discovery_budget_escalated`, and `primary_cut_summary` in phase-1 runtime
    output
- `task/c2h-b5-prove-phase1-gate`
  - update graph tests for:
    - credible cut success
    - weak-evidence clarification
    - no canned Forge seam clarification on credible outside-repo asks

Lane-local commands:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
```

Merge conditions:

- `planning_runtime.py` contains no new runtime family or strategy-name branch
- graph tests prove the phase-1 gate is repo-evidence driven
- canned clarification is removed from the credible live path
- worker handoff includes exact changed assertions

### 7.3 Phase BF: Parent-Local Phase-1 Freeze

Parent-owned tasks:

- `task/c2h-bf1-rerun-ws-b-gate`
  - rerun `WS-B` tests in the integration worktree
- `task/c2h-bf2-merge-ws-b`
  - merge `WS-B` only after the rerun gate is green
- `task/c2h-bf3-publish-phase1-freeze`
  - write `phase1-runtime-freeze.md` with the exact approved phase-1 output
    shape and allowed metadata
- `task/c2h-bf4-dispatch-ws-c-and-ws-d`
  - open `WS-C` and `WS-D`

Parent rerun commands for `gate/c2h-phase1-runtime`:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
```

Acceptance for Phase BF:

- `gate/c2h-phase1-freeze` passes only if the integrated tree reproduces the
  `WS-B` result and the parent freeze explicitly states whether
  `primary_cut_summary` is now published truth.

### 7.4 Phase C: WS-C Structural Derivation Runtime

Lane purpose:

- replace canonical seam/workstream/slice scaffolding with repo-derived
  structure while preserving determinism

Owned files:

- `/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`

Forbidden files:

- `PLAN.md`
- `anvil/harness/reporting.py`
- `anvil/harness/state.py`
- `tests/test_harness_planning_artifacts.py`

Tasks:

- `task/c2h-c1-replace-live-seam-derivation`
  - remove live dependence on `_CANONICAL_SEAM_SPECS` for seam emission
- `task/c2h-c2-derive-workstreams-from-emitted-seams`
  - preserve deterministic ordering and explicit dependency direction
- `task/c2h-c3-derive-slices-from-workstreams`
  - emit `1-2` executable slices per workstream with explicit acceptance
    criteria
- `task/c2h-c4-stabilize-id-generation`
  - enforce stable seam/workstream/slice IDs across repeat runs on the same repo
    snapshot
- `task/c2h-c5-prove-structural-truth`
  - update runtime and example wiring tests so they prove repo-derived live
    truth rather than canonical IDs

Lane-local commands:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Merge conditions:

- success runs can emit non-canonical seam IDs
- workstreams and slices reference emitted seams cleanly
- repeat runs preserve counts, IDs, and ordering
- no new helper family is introduced

### 7.5 Phase D: WS-D Artifact-Truth Lane

Lane purpose:

- preserve and document truthful artifact publication without reopening the
  planning runtime family

Start condition:

- `phase1-runtime-freeze.md` exists

Final merge condition:

- `WS-C` has already merged and the parent has published
  `structure-output-freeze.md`

Owned files:

- `/home/azureuser/__Active_Code/forge/anvil/harness/reporting.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/state.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_state_boundaries.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_reporting.py`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`
- `/home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- `examples/harness/tasks/deterministic_feature_planning_*.yaml`

Forbidden files:

- `PLAN.md`
- `anvil/harness/planning_runtime.py`
- `tests/test_harness_planning_graph.py`
- `tests/test_harness_example_strategy_wiring.py`

Tasks:

- `task/c2h-d1-audit-phase-result-normalization`
  - confirm whether `phase_results` normalization drops required live metadata
- `task/c2h-d2-preserve-whitelisted-phase-metadata`
  - make the narrowest possible `reporting.py` and `state.py` patch if
    `primary_cut_summary` or equivalent must survive publication
- `task/c2h-d3-verify-coverage-contract-stability`
  - keep `coverage_ledger`, `assumptions_register`, and `uncovered_delta`
    contractually intact
- `task/c2h-d4-align-docs-and-example-wording`
  - distinguish deterministic fixture scaffolding from live repo-derived truth
- `task/c2h-d5-keep-stop-path-honesty`
  - preserve success-only `PLAN.md` and `plan.json`, plus summary-only
    blocked/failed behavior
- `task/c2h-d6-prove-artifact-truth`
  - update artifact and state-boundary tests to match the preserved contract

Lane-local commands:

```bash
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_docs_surface.py
```

Merge conditions:

- any metadata-preservation change is narrow and whitelisted
- docs/examples do not imply canonical seam IDs are live success truth
- artifact tests prove the coverage contract stayed intact
- docs surface coverage passes in-lane and is rerun by the parent before merge

### 7.6 Phase D-Freeze: Parent Structural Output Freeze

Parent-owned tasks:

- `task/c2h-df1-rerun-ws-c-gate`
  - rerun `WS-C` commands in the integration worktree
- `task/c2h-df2-merge-ws-c`
  - merge `WS-C` only after the rerun gate is green
- `task/c2h-df3-publish-structure-freeze`
  - write `structure-output-freeze.md` with approved seam/workstream/slice
    output expectations and stable-ID rules
- `task/c2h-df4-rerun-ws-d-gate`
  - rerun `WS-D` commands in the integration worktree before merge
- `task/c2h-df5-merge-ws-d`
  - merge `WS-D` only after `WS-C` is integrated, the structure freeze exists,
    and the rerun gate is green

Parent rerun commands for `gate/c2h-structure-runtime`:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Parent rerun commands for `gate/c2h-artifact-truth`:

```bash
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_docs_surface.py
```

Acceptance:

- `structure-output-freeze.md` exists before `WS-D` merges
- any newly published metadata is named and justified explicitly

### 7.7 Phase E: WS-E Regression and Canary Wall

Lane purpose:

- land last and prove the branch is honest on both fixture-backed and real-repo
  paths

Owned files:

- `/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`
- `/home/azureuser/__Active_Code/forge/.runs/c2-honest-live-planning-alignment-orch/canary-targets.md`
- `/home/azureuser/__Active_Code/forge/.runs/c2-honest-live-planning-alignment-orch/acceptance/c2h-acceptance-checklist.md`

Forbidden files:

- `PLAN.md`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/reporting.py`
- `anvil/harness/state.py`

Tasks:

- `task/c2h-e1-fill-regression-gaps`
  - add any last assertion coverage still missing after `WS-C` and `WS-D`
- `task/c2h-e2-lock-repeat-run-determinism`
  - keep repo-derived ID stability explicit in tests
- `task/c2h-e3-lock-canned-question-regression`
  - ensure credible outside-repo asks cannot regress back to the canned
    clarification
- `task/c2h-e4-run-gsd-browser-canary`
  - run the prepared canary task against
    `/home/azureuser/__Active_Code/gsd-browser`
- `task/c2h-e5-record-canary-evidence`
  - capture artifacts and exit codes under `logs/` and `canary/out/`
- `task/c2h-e6-complete-acceptance-checklist`
  - mark every checklist item with evidence

Lane-local commands:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run python -m anvil.cli harness-run \
  --task .runs/c2-honest-live-planning-alignment-orch/canary/gsd-browser-task.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /home/azureuser/__Active_Code/gsd-browser \
  --out-root .runs/c2-honest-live-planning-alignment-orch/canary/out \
  --json
```

Merge conditions:

- fixture-backed regressions still pass
- `gsd-browser` emits `1-3` non-canonical seams
- no emitted seam equals `seam-runtime-routing` or
  `seam-artifact-publication`
- workstreams and slices link cleanly to emitted seams
- acceptance checklist is complete and evidence-backed

Parent rerun commands for `gate/c2h-regression-canary`:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run python -m anvil.cli harness-run \
  --task .runs/c2-honest-live-planning-alignment-orch/canary/gsd-browser-task.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /home/azureuser/__Active_Code/gsd-browser \
  --out-root .runs/c2-honest-live-planning-alignment-orch/canary/out \
  --json
```

### 7.8 Phase F: Parent Final Integration and Closeout

This is the authoritative parent ledger for integrating the worker lanes and
closing the milestone. The parent executes these tasks in order on the
integration worktree.

Parent-owned tasks:

- `task/c2h-f1-rerun-merge-ws-b-and-publish-phase1-freeze`
  - rerun the `WS-B` gate in the integration worktree
  - merge `WS-B`
  - publish `phase1-runtime-freeze.md`
- `task/c2h-f2-dispatch-ws-c-and-ws-d`
  - dispatch `WS-C` and `WS-D` only after the phase-1 freeze is written
- `task/c2h-f3-rerun-merge-ws-c-and-publish-structure-freeze`
  - rerun the `WS-C` gate in the integration worktree
  - merge `WS-C`
  - publish `structure-output-freeze.md`
- `task/c2h-f4-rerun-and-merge-ws-d-after-c`
  - rerun the `WS-D` gate only after `WS-C` is integrated
  - merge `WS-D`
- `task/c2h-f5-dispatch-rerun-and-merge-ws-e`
  - dispatch `WS-E` only after `WS-C` and `WS-D` are merged
  - rerun the `WS-E` gate in the integration worktree
  - merge `WS-E`
- `task/c2h-f6-rerun-final-integrated-fixtures`
  - run integrated success, clarification, and failed fixture commands on the
    final integrated tree
- `task/c2h-f7-run-final-targeted-planning-tests`
  - rerun the targeted planning regression wall on the final integrated tree
- `task/c2h-f8-run-broader-repo-quality-gates`
  - run broader repo health checks on the final integrated tree
- `task/c2h-f9-capture-final-acceptance-and-closeout`
  - write the final gate report, capture artifact paths and exit codes, and
    record the milestone verdict

Parent rerun commands by task:

- `task/c2h-f1`

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
```

- `task/c2h-f3`

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

- `task/c2h-f4`

```bash
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_docs_surface.py
```

- `task/c2h-f5`

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run python -m anvil.cli harness-run \
  --task .runs/c2-honest-live-planning-alignment-orch/canary/gsd-browser-task.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /home/azureuser/__Active_Code/gsd-browser \
  --out-root .runs/c2-honest-live-planning-alignment-orch/canary/out \
  --json
```

Integrated fixture rerun commands for `task/c2h-f6`:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /home/azureuser/__Active_Code/forge \
  --out-root .runs/c2-honest-live-planning-alignment-orch/final-fixtures/success \
  --json

poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_clarification.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /home/azureuser/__Active_Code/forge \
  --out-root .runs/c2-honest-live-planning-alignment-orch/final-fixtures/clarification \
  --json

poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_failed.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --workspace /home/azureuser/__Active_Code/forge \
  --out-root .runs/c2-honest-live-planning-alignment-orch/final-fixtures/failed \
  --json
```

Expected truths for `task/c2h-f6`:

- success exits `0` and emits `PLAN.md`, `plan.json`, and `summary.json`
- clarification exits `1` and emits `summary.json` only
- failed exits `1` and emits `summary.json` only
- clarification and failed reruns must not emit `PLAN.md` or `plan.json`

Final targeted planning commands for `task/c2h-f7`:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_docs_surface.py
```

Broader repo quality commands for `task/c2h-f8`:

```bash
poetry run ruff check .
poetry run black --check .
poetry run isort --check-only .
poetry run mypy anvil
poetry run pytest -q
```

Closeout conditions for `task/c2h-f9`:

- `acceptance/c2h-acceptance-checklist.md` is complete and evidence-backed
- `acceptance/final-gate-report.md` records every rerun command and exit code
- final fixture artifact paths are recorded under `.runs/.../state.json`
- `gate/c2h-final` is green only if all merge gates, integrated fixtures,
  targeted planning tests, the `gsd-browser` canary, and broader repo quality
  gates are green on the integrated tree

## 8. Parent Integration Discipline

Parent-only rules:

- Merge and rerun every lane in the integration worktree, never by trusting a
  worker branch result alone.
- Update `queue.md`, `state.json`, `session.log`, and gate files immediately
  after every dispatch, merge, reopen, or blocker.
- Write freeze files only after rerunning the relevant lane gate on the
  integration worktree.
- If a lane fails because peer-owned changes are missing, reopen the owning lane
  instead of hot-patching from the parent.
- If a lane uncovers a hard-guard violation, stop the sequence and record the
  blocker before any new dispatch.

Parent gate rerun rule:

- Every merge requires a fresh parent rerun of that lane's commands on
  `/home/azureuser/__Active_Code/forge`.

Concrete parent rerun map:

| Gate | Parent rerun commands |
|---|---|
| `gate/c2h-phase1-runtime` | `poetry run pytest -q tests/test_harness_planning_graph.py` |
| `gate/c2h-structure-runtime` | `poetry run pytest -q tests/test_harness_planning_graph.py` and `poetry run pytest -q tests/test_harness_example_strategy_wiring.py` |
| `gate/c2h-artifact-truth` | `poetry run pytest -q tests/test_harness_planning_artifacts.py`, `poetry run pytest -q tests/test_harness_state_boundaries.py`, `poetry run pytest -q tests/test_harness_reporting.py`, and `poetry run pytest -q tests/test_docs_surface.py` |
| `gate/c2h-regression-canary` | targeted planning tests plus the `harness-run` `gsd-browser` canary command from Phase E |
| `gate/c2h-final` | integrated fixture reruns, final targeted planning tests, and broader repo quality gates from Phase F |

## 9. Repo Quality Gates

Targeted planning commands:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_docs_surface.py
```

Broader repo quality gates for parent closeout:

```bash
poetry run ruff check .
poetry run black --check .
poetry run isort --check-only .
poetry run mypy anvil
poetry run pytest -q
```

Final gate policy:

- `gate/c2h-final` is green only if the integrated success, clarification, and
  failed fixture reruns, all targeted planning tests, the `gsd-browser`
  canary, and the broader repo quality gates pass on the integrated tree.

## 10. Merge and Conflict Policy

1. The parent merges in the fixed order from Section 3.2 only.
2. Workers never merge peer branches.
3. Workers never rebase peer work into their own lane unless the parent
   instructs them.
4. Conflict resolution happens in the integration worktree only.
5. `planning_runtime.py` conflicts always route back to the currently owning
   runtime lane.
6. If `WS-D` discovers a required runtime change, it stops and reopens `WS-C`.
7. If `WS-E` discovers a product-logic failure, it stops and reopens the owning
   lane instead of fixing logic itself.
8. A lane that performs unrelated cleanup is reopened even if its tests are
   green.

## 11. Failure-Routing Matrix

| Failure | Likely owner | Immediate action | Reopen target |
|---|---|---|---|
| canonical seam bias still present in live ranking | `WS-B` | fail `gate/c2h-phase1-runtime` | `WS-B` |
| credible ask still emits canned clarification | `WS-B` | block phase-1 freeze | `WS-B` |
| seam/workstream/slice IDs unstable across reruns | `WS-C` | fail structural gate | `WS-C` |
| workstreams or slices still scaffold-derived | `WS-C` | block `WS-D` final merge and `WS-E` dispatch | `WS-C` |
| required phase metadata collapses during publication | `WS-D` | fail artifact-truth gate | `WS-D` |
| coverage contract change grows beyond narrow preservation | Parent | stop sequence | planning reopen |
| docs/examples imply fixture truth equals live truth | `WS-D` | fail artifact-truth gate | `WS-D` |
| canary emits canonical seam IDs | `WS-E` | record blocker and identify whether runtime or tests are wrong | `WS-C` by default |
| canary cannot run because target repo or task spec is missing | Parent | restore `canary-targets.md` and task file | Parent |
| full repo checks fail for unrelated style drift | Parent | isolate failure, decide whether reopen is needed | owning lane |

## 12. Tests and Acceptance

Branch acceptance checklist:

- [ ] live success no longer depends on `_CANONICAL_SEAM_SPECS`
- [ ] `_score_path()` and `_discovered_workspace_matches()` no longer bias live
  success toward canonical Forge seams
- [ ] `design_doc` chooses a credible primary cut or emits a feature-specific
  clarification
- [ ] `seam_decomposition` emits `1-3` repo-derived seams
- [ ] `parallel_planning` emits workstreams derived from those seams
- [ ] `slice_emission` emits slices with explicit acceptance criteria
- [ ] repeat runs preserve seam/workstream/slice counts, IDs, and ordering
- [ ] `tests/test_harness_planning_graph.py` no longer encodes canonical live
  seam IDs
- [ ] `tests/test_harness_example_strategy_wiring.py` no longer encodes
  canonical live seam IDs
- [ ] artifact publication preserves the current contract, with only a narrow
  metadata-preservation patch if required
- [ ] blocked/failed runs still publish `summary.json` only
- [ ] success runs still publish `PLAN.md` and `plan.json` only on success
- [ ] `gsd-browser` emits non-canonical seams with clean downstream linkage
- [ ] no `planning_v2`, no strategy-name branching, no second runtime family,
  no provider-backed seam synthesis, and no helper-family sprawl

Acceptance evidence sources:

- targeted pytest logs under `logs/`
- parent gate records under `gates/`
- final fixture artifacts under `final-fixtures/`
- canary artifacts under `canary/out/`
- final checklist under `acceptance/c2h-acceptance-checklist.md`
- final verdict under `acceptance/final-gate-report.md`

## 13. Assumptions

1. `/home/azureuser/__Active_Code/forge/PLAN.md` is the current authoritative
   plan for this branch and supersedes stale root orchestration content.
2. The main runtime bottleneck remains
   `/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py`.
3. The existing coverage contract is already good enough to preserve, aside from
   a possible narrow metadata-preservation patch.
4. `/home/azureuser/__Active_Code/gsd-browser` is available locally for the
   outside-repo canary.
5. The parent can create repo-local `.runs/` state and sibling worktrees without
   changing branch scope.
6. If preserving truthful phase metadata would require a broad schema or
   reporting redesign, this runbook is intentionally incomplete and must reopen
   planning instead of forcing scope through.
