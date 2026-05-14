# ORCH_PLAN: B1 Harness Seam Extraction

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Base branch at kickoff: `main`  
Authoritative implementation plan for this session: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`  
Historical orchestration style reference: `/Users/spensermcconnell/__Active_Code/forge/docs/project_management/plans/history/ORCH_PLAN.md`

This orchestration plan executes milestone `B1` from `PLAN.md`: harness seam extraction for the state-graph strangler.

B1 is not topology migration. It is the ownership and seam-freezing milestone that makes the current graph-era boundaries explicit while keeping `HarnessRunner` as the only execution truth for `analysis_review`.

What this run must deliver:

- add internal graph vocabulary only for the approved bounded subset
- make `select_strategy_node` emit explicit internal graph metadata
- make summary read and write boundaries explicit and singular
- keep `anvil/harness/runner.py` as the only topology truth in B1
- add runner seam metadata and boundary observability without changing publication outcomes
- add direct seam and boundary regression coverage in the same lanes that implement those seams
- preserve existing harness CLI, Forge CLI, examples, and canonical parity tests

The parent agent owns kickoff, plan freeze, interface freeze, worker dispatch, worktree creation, merges, conflict resolution, and final acceptance. The parent is the only integrator.

## Orchestration Runtime Policy

Parent runtime policy:

- Parent owns the active session plan at `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`, including the fact that it is currently untracked.
- Parent snapshots the active `PLAN.md` into the orchestration state root before dispatching workers, but the root `PLAN.md` remains the authoritative authored plan source for this session.
- Parent is the only agent allowed to create or switch the integration branch, merge worker branches, resolve conflicts, or approve scope changes.
- Parent keeps the critical path local for interface freeze, boundary freeze, integration, and final regression.

Worker runtime policy:

- Every worker runs on `GPT-5.4` with `reasoning_effort=high`.
- Workers execute only their assigned lane, owned files, frozen invariants, and declared validation commands.
- Workers own the direct regression tests that prove their seam contract wherever write sets permit.
- Workers do not make scope decisions, rename frozen interfaces, or merge peer work.
- Workers treat the copied `PLAN.md` excerpt in their packet as a dispatch snapshot, not as permission to diverge from the parent-owned plan.

Concurrency policy:

- Maximum concurrent worker lanes: `2`
- Launch `WS-A` and `WS-B` in parallel
- Launch `WS-C` only after `WS-A` and `WS-B` are merged and the parent publishes `interface-freeze.md`
- Final regression and acceptance are parent-only

## Hard Guards

1. `PLAN.md` is authoritative. If this orchestration file and `PLAN.md` disagree, follow `PLAN.md`.
2. The root `PLAN.md` is active authored source for this session even though it is currently untracked.
3. Scope is limited to B1 seam extraction only.
4. `HarnessRunner` remains the only topology truth for B1 execution.
5. Validators remain adjacent orchestration, not graph stages.
6. `StrategyGraphSpec` is internal declaration only. No public DAG claim, compiler, schema, or config surface ships in B1.
7. `StageSpec` names stage identity and capabilities only. It is not executable runtime truth.
8. `summary_read_adapter_v1(...)` is the only sanctioned summary-to-state path in B1.
9. `state_from_summary(...)` must end B1 as a compatibility wrapper only.
10. `summary_projection_v1(...)` is the only sanctioned state-to-summary path in B1.
11. `write_state_artifacts(...)` stays public but delegates through `summary_projection_v1(...)`.
12. `anvil/harness/subgraphs/_bridge.py` and `anvil/harness/nodes/write_artifacts.py` are temporary bridge boundaries and may not gain policy, selection, validation, or publication semantics.
13. `anvil/harness/reporting.py` remains the publication truth.
14. `anvil/harness/selection.py` remains the ranking and draft-selection truth.
15. `anvil/harness/contracts.py` remains the contract truth. No duplicate contract model may be introduced.
16. Preserve existing top-level `StageRecord` fields. New observability belongs under `StageRecord.metadata` unless an existing typed field already carries it.
17. No artifact contract version bump ships in B1.
18. `anvil/harness/selection.py`, `anvil/harness/validation.py`, `anvil/harness/semantic_validation.py`, `anvil/harness/prompts.py`, and `anvil/harness/schemas.py` are no-touch by default. Any edit requires a parent-approved blocker-driven exception.
19. `examples/harness/live_acceptance/*`, `examples/harness/strategies/*`, and `examples/harness/tasks/*` are validation surfaces, not default implementation targets. Any edit requires a parent-approved blocker-driven exception.
20. Existing examples, acceptance fixtures, `python -m anvil.harness.cli run --help`, and `python -m anvil list` must continue to work.
21. The parent is the only integrator.

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit Gate |
|---|---|---|---|---|
| Phase A: Kickoff and Freeze | `task/b1-a1` to `task/b1-a6` | Parent | Strictly serialized | state root, plan snapshot, invariants, integration branch, and initial worktrees exist |
| Phase B: Parallel Code + Direct Test Lanes | `task/b1-b1`, `task/b1-b2` | `WS-A`, `WS-B` | Parallel | `gate/b1-lane-a`, `gate/b1-lane-b` |
| Phase C: Parent Integration and Interface Freeze | `task/b1-c1`, `task/b1-c2` | Parent | Strictly serialized | `interface-freeze.md` published |
| Phase D: Boundary Extraction + Direct Boundary Tests | `task/b1-d1` | `WS-C` | Serialized | `gate/b1-lane-c` |
| Phase E: Parent Integration and Boundary Freeze | `task/b1-e1`, `task/b1-e2` | Parent | Strictly serialized | `boundary-freeze.md` published |
| Phase F: Final Regression and Acceptance | `task/b1-f1` to `task/b1-f3` | Parent | Strictly serialized | `gate/b1-targeted-regressions`, `gate/b1-acceptance`, `gate/b1-complete` |

### Launch Order

1. `task/b1-a1-read-authority`
2. `task/b1-a2-snapshot-untracked-plan`
3. `task/b1-a3-freeze-invariants`
4. `task/b1-a4-create-state-root`
5. `task/b1-a5-create-integration-branch`
6. `task/b1-a6-create-ws-a-ws-b-worktrees`
7. Dispatch `WS-A`
8. Dispatch `WS-B`
9. Merge `WS-B`
10. Merge `WS-A`
11. Publish `interface-freeze.md`
12. Create and dispatch `WS-C`
13. Merge `WS-C`
14. Publish `boundary-freeze.md`
15. Run parent-only final regression and acceptance sweep

### Merge Order

The merge order is fixed:

1. `WS-B` runner ownership and observability
2. `WS-A` graph vocabulary and strategy selection
3. `WS-C` state and boundary extraction
4. Parent-only final regression and milestone acceptance on the integrated tree

### Phase Tasks

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/b1-a1-read-authority` | Re-read root `PLAN.md`, historical `ORCH_PLAN.md`, and the B1 implementation surfaces | Parent | Parent can restate scope and locks exactly |
| `task/b1-a2-snapshot-untracked-plan` | Copy the active untracked `PLAN.md` into the state root and record its hash | Parent | `inputs/PLAN.session.md` and hash recorded |
| `task/b1-a3-freeze-invariants` | Freeze lane ownership, forbidden surfaces, gate commands, and blocker protocol | Parent | `invariants.md` written |
| `task/b1-a4-create-state-root` | Create the repo-local orchestration state root and sentinel layout | Parent | state root initialized |
| `task/b1-a5-create-integration-branch` | Create the parent-owned integration branch from `main` in the current workspace without disturbing the untracked `PLAN.md` | Parent | integration branch active |
| `task/b1-a6-create-ws-a-ws-b-worktrees` | Create sibling worktrees for the first two lanes | Parent | worktrees created and clean |
| `task/b1-b1-graph-vocabulary-selection` | Land B1 graph vocabulary, strategy-selection metadata stamping, and direct graph-vocabulary tests | `WS-A` | `gate/b1-lane-a` |
| `task/b1-b2-runner-ownership-observability` | Land runner seam naming, stage metadata, and direct runner tests | `WS-B` | `gate/b1-lane-b` |
| `task/b1-c1-merge-b-then-a` | Merge `WS-B` and `WS-A` into the integration tree and rerun their gates | Parent | merged cleanly |
| `task/b1-c2-publish-interface-freeze` | Publish exact interface and naming freeze for downstream lane `WS-C` | Parent | `interface-freeze.md` written |
| `task/b1-d1-state-summary-boundaries` | Land explicit read/write boundary extraction and direct boundary/reporting tests | `WS-C` | `gate/b1-lane-c` |
| `task/b1-e1-merge-ws-c` | Merge `WS-C` into the integration tree and rerun its gate | Parent | merged cleanly |
| `task/b1-e2-publish-boundary-freeze` | Publish exact boundary contract and state-key freeze for final regression | Parent | `boundary-freeze.md` written |
| `task/b1-f1-targeted-regression-sweep` | Run the full PLAN.md validation command set on the integrated tree | Parent | `gate/b1-targeted-regressions` |
| `task/b1-f2-acceptance-checklist-review` | Verify the integrated tree against the B1 acceptance checklist | Parent | `gate/b1-acceptance` |
| `task/b1-f3-final-verdict` | Record green or blocked milestone verdict | Parent | `gate/b1-complete` |

## Orchestration State and Source of Truth

The parent maintains one repo-local orchestration state root for the full run:

- `.runs/b1-seam-extraction-orch/`

Required layout:

- `.runs/b1-seam-extraction-orch/queue.md`
- `.runs/b1-seam-extraction-orch/state.json`
- `.runs/b1-seam-extraction-orch/invariants.md`
- `.runs/b1-seam-extraction-orch/interface-freeze.md`
- `.runs/b1-seam-extraction-orch/boundary-freeze.md`
- `.runs/b1-seam-extraction-orch/session.log`
- `.runs/b1-seam-extraction-orch/handoffs/`
- `.runs/b1-seam-extraction-orch/gates/`
- `.runs/b1-seam-extraction-orch/logs/`
- `.runs/b1-seam-extraction-orch/sentinels/`
- `.runs/b1-seam-extraction-orch/inputs/`
- `.runs/b1-seam-extraction-orch/acceptance/`

### File Roles

- `queue.md`
  - Canonical task table with one row per `task/b1-*`
  - Tracks owner, state, gate, reopen reason, and merge status
- `state.json`
  - Current phase, active lanes, branch names, plan hash, blockers, merge state, and final verdict
- `invariants.md`
  - Frozen scope, ownership boundaries, forbidden surfaces, commands, and gate definitions
- `interface-freeze.md`
  - Parent-accepted internal naming freeze after `WS-A` and `WS-B`
  - Freezes exact keys:
    - `strategy_graph_spec`
    - `strategy_graph_spec_id`
    - `strategy_graph_subset`
    - `resolve_analysis_review_contract(...)`
    - `graph_stage_id`
    - `transition_reason`
    - `boundary_source`
    - `semantic_validation_path`
- `boundary-freeze.md`
  - Parent-accepted boundary freeze after `WS-C`
  - Freezes exact keys and boundary surfaces:
    - `serialization_version`
    - `analysis_review_contract`
    - `strategy_graph_spec`
    - `strategy_graph_spec_id`
    - `strategy_graph_subset`
    - `focus_decision`
    - `topic_ledger`
    - `summary_boundary_version`
    - `bridge_boundary_version`
    - `summary_read_adapter_v1(...)`
    - `summary_projection_v1(...)`
    - `LegacyBridgeBoundary`
- `session.log`
  - Parent-only sequential log of dispatches, readiness, blockers, merges, reopen events, and final decisions
- `inputs/PLAN.session.md`
  - Immutable kickoff snapshot of the active root `PLAN.md`
  - This is a run artifact snapshot, not the authored source of truth
- `inputs/PLAN.session.sha256`
  - Hash of the kickoff `PLAN.md` snapshot
- `handoffs/task-b1-*.md`
  - Narrow worker packets plus parent-accepted return summaries
- `gates/*.md`
  - Parent gate results with exact commands and verdicts
- `acceptance/`
  - Final command outputs, acceptance notes, and parity observations used during milestone review

### Git-Tracked Authored Sources vs Run Artifacts

Git-tracked authored sources for this milestone:

- root `ORCH_PLAN.md`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/builder.py`
- `anvil/harness/nodes/select_strategy.py`
- `anvil/harness/state.py`
- `anvil/harness/reporting.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/contracts.py`
- `anvil/harness/runner.py`
- new and expanded B1 tests under `tests/`

Session-authored but currently untracked source:

- root `PLAN.md`

Run artifacts that must not be committed:

- everything under `.runs/b1-seam-extraction-orch/`
- copied plan snapshots and hashes under `.runs/.../inputs/`
- worker packets, gate logs, command logs, acceptance notes
- any temporary smoke output directories created only for gate commands

### Plan Drift Rule

If the root `PLAN.md` changes after kickoff and its content no longer matches `inputs/PLAN.session.sha256`, the parent must halt dispatch and integration, diff the plan change, and either:

- republish the freezes and reopen affected lanes, or
- explicitly declare the plan drift out of scope for the current run

Workers do not continue on stale plan packets once the parent declares plan drift.

## Sentinel Conventions

Per-task sentinels live under:

- `.runs/b1-seam-extraction-orch/sentinels/`

Required sentinel names:

- `task-b1-*.dispatched`
- `task-b1-*.ready`
- `task-b1-*.blocked`
- `task-b1-*.merged`
- `task-b1-*.failed-gate`

Required meanings:

- `.dispatched`
  - parent has issued the packet and opened the lane
- `.ready`
  - worker claims the lane gate is ready for parent verification
- `.blocked`
  - worker cannot proceed without a parent decision
- `.merged`
  - parent merged the lane and reran the lane gate successfully
- `.failed-gate`
  - parent verification failed and the lane is reopened

### Parent Wait Protocol

The parent does not broad-poll worktrees or consume full worker transcripts.

The parent waits on:

- sentinel changes
- narrow handoff completion
- explicit blocker notes
- gate reruns in the integration worktree

## Worktree and Branch Plan

Integration worktree:

- Path: `/Users/spensermcconnell/__Active_Code/forge`
- Branch: `codex/b1-seam-extraction`
- Owner: Parent only

Sibling worktree root:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/`

Lane worktrees:

- `WS-A`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/ws-a-graph-vocabulary`
  - Branch: `codex/b1-ws-a-graph-vocabulary`
- `WS-B`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/ws-b-runner-observability`
  - Branch: `codex/b1-ws-b-runner-observability`
- `WS-C`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/ws-c-boundary-extraction`
  - Branch: `codex/b1-ws-c-boundary-extraction`

### Worktree Creation Commands

Create the integration branch in the current workspace first so the untracked root `PLAN.md` remains present in the parent-owned tree:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge switch -c codex/b1-seam-extraction
mkdir -p /Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/ws-a-graph-vocabulary \
  -b codex/b1-ws-a-graph-vocabulary \
  codex/b1-seam-extraction

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/ws-b-runner-observability \
  -b codex/b1-ws-b-runner-observability \
  codex/b1-seam-extraction
```

Create `WS-C` only after `WS-A` and `WS-B` merge:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b1-seam-extraction/ws-c-boundary-extraction \
  -b codex/b1-ws-c-boundary-extraction \
  codex/b1-seam-extraction
```

### Worktree Rules

- The parent is the only integrator.
- Workers never merge peer branches.
- Workers never rebase peer changes into their own lane unless the parent instructs it.
- Parent resolves every merge or rebase in the integration worktree only.
- If a lane needs a peer-owned change, it raises a blocker instead of editing that file.
- Worker worktrees must not assume the untracked root `PLAN.md` exists locally. They rely on the parent-issued snapshot and excerpt packet.
- `WS-C` does not start until `interface-freeze.md` exists.

## Blocker, Interface-Change, and Conflict Protocols

### Blocker Protocol

A worker must mark `.blocked` and stop when any of these occur:

- it needs a peer-owned file change
- it cannot satisfy its lane gate without touching a frozen surface
- the parent-owned freeze document for its lane dependency does not exist
- the root `PLAN.md` changed and the parent declared plan drift
- an apparent implementation need would change user-visible artifact behavior, prompt behavior, schema behavior, validator behavior, selection behavior, or public CLI behavior
- a required example or acceptance fixture appears to need editing even though it is frozen by default

Required blocker return:

- exact file or interface requested
- exact reason
- exact minimal parent decision needed
- exact command or failing assertion demonstrating the blocker, if relevant

### Interface-Change Protocol

For this milestone, interface changes include:

- changing the exact B1 state keys frozen by `PLAN.md`
- changing the bridge or projection function names after freeze
- changing `StageRecord` top-level fields instead of adding metadata under `metadata`
- changing `analysis_review` execution order or loop policy
- touching `anvil/harness/selection.py`, `anvil/harness/validation.py`, `anvil/harness/semantic_validation.py`, `anvil/harness/prompts.py`, or `anvil/harness/schemas.py` without parent approval
- editing example strategies, tasks, or live acceptance manifests without an explicit parent-approved blocker

Worker behavior:

- do not implement interface changes speculatively
- raise `.blocked`
- wait for a revised parent packet

### Conflict Protocol

Conflict type: textual overlap

- Example: a lane starts editing a file already assigned to another lane.
- Resolution: parent reassigns ownership or serializes the follow-up.
- Workers do not self-resolve peer overlap.

Conflict type: contract drift

- Example: `WS-C` needs a state key or boundary name that does not match `interface-freeze.md`.
- Resolution: parent compares against `PLAN.md` and the freeze file, then reopens the affected lane.
- Workers do not invent fallback names.

Conflict type: scope drift

- Example: a lane starts changing publication behavior, validator rules, ranking rules, or prompt/schema behavior.
- Resolution: stop immediately, mark blocked, and return the smallest drift summary.
- Parent either rejects the drift or replans explicitly.

Conflict type: fixture drift

- Example: a worker believes `examples/harness/live_acceptance/*` or strategy/task fixtures must change.
- Resolution: stop, mark blocked, and show the exact failing test and the minimum fixture delta required.
- Parent decides whether to keep fixtures frozen or serialize a tightly-scoped follow-up.

## Workstream Plan

### WS-A: Graph Vocabulary, Strategy Selection, and Direct Graph Tests

Task ID:

- `task/b1-b1-graph-vocabulary-selection`

Owner:

- Worker `WS-A`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `anvil/harness/strategy_graph.py`
- `anvil/harness/builder.py`
- `anvil/harness/nodes/select_strategy.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_example_strategy_wiring.py`

Files explicitly not owned by `WS-A`:

- `anvil/harness/contracts.py`
- `anvil/harness/runner.py`
- `anvil/harness/state.py`
- `anvil/harness/reporting.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/selection.py`
- `anvil/harness/validation.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/schemas.py`
- `examples/harness/live_acceptance/*`
- `examples/harness/strategies/*`
- `examples/harness/tasks/*`
- all other `tests/` files

Required changes:

- add internal `StrategyGraphSpec`
- add internal `StageSpec`
- support the bounded subset only:
  - linear stages
  - bounded single back-edge loop metadata
  - conditional branch metadata
  - terminal outcome metadata
- cover existing strategy kinds:
  - `single_pass`
  - `pfr_v1`
  - `analysis_review_*`
- make `select_strategy_node` stop being a no-op
- stamp these exact keys into state:
  - `strategy_graph_spec`
  - `strategy_graph_spec_id`
  - `strategy_graph_subset`
- keep `build_harness_langgraph(...)` routing behavior unchanged
- add direct tests proving the graph vocabulary and metadata emission
- keep any `tests/test_harness_example_strategy_wiring.py` changes minimal and limited to the added graph metadata expectations
- do not derive runtime execution from the spec

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_strategy_graph.py \
  tests/test_harness_example_strategy_wiring.py

poetry run python - <<'PY'
from anvil.harness.nodes.prepare_run import prepare_run_node
from anvil.harness.nodes.validator_preflight import validator_preflight_node
from anvil.harness.nodes.select_strategy import select_strategy_node

state = prepare_run_node(
    {
        "task_path": "examples/harness/tasks/recommend_automation_improvements.yaml",
        "strategy_path": "examples/harness/strategies/analysis_review_bounded_codex_claude.yaml",
        "workspace_root": ".",
        "out_root": ".tmp/b1-lane-a-smoke",
    }
)
state = validator_preflight_node(state)
state = select_strategy_node(state)

assert state["strategy_graph_spec_id"]
assert state["strategy_graph_subset"]
assert isinstance(state["strategy_graph_spec"], dict)
print("ok")
PY
```

`gate/b1-lane-a` is green only when all of these are true:

- all lane commands are green
- `select_strategy_node` is no longer a no-op
- direct tests prove the bounded graph vocabulary and metadata emission
- the graph still routes `single_pass`, `pfr_v1`, `analysis_review_v1`, and `write_artifacts` exactly as before
- no public config or DAG surface was added
- no code outside the owned files changed

### WS-B: Runner Ownership, Observability, and Direct Runner Tests

Task ID:

- `task/b1-b2-runner-ownership-observability`

Owner:

- Worker `WS-B`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `anvil/harness/contracts.py`
- `anvil/harness/runner.py`
- `tests/test_harness_runner.py`

Files explicitly not owned by `WS-B`:

- `anvil/harness/strategy_graph.py`
- `anvil/harness/builder.py`
- `anvil/harness/nodes/select_strategy.py`
- `anvil/harness/state.py`
- `anvil/harness/reporting.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/selection.py`
- `anvil/harness/validation.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/schemas.py`
- all other `tests/` files
- all `examples/harness/*` surfaces

Required changes:

- add `resolve_analysis_review_contract(...)` in `anvil/harness/contracts.py`
- keep `build_analysis_review_contract(...)` stable
- keep `HarnessRunner` as the only B1 execution truth
- add these metadata keys under `StageRecord.metadata` unless already present as typed fields:
  - `graph_stage_id`
  - `transition_reason`
  - `boundary_source`
  - `semantic_validation_path`
- reuse existing fields such as `normalized_json_path` where they already carry the value
- add direct tests proving seam metadata is emitted without changing stage order or verdict behavior
- do not change stage order, loop policy, validator scheduling, selection behavior, or publication outcomes

Lane commands:

```bash
poetry run pytest -q tests/test_harness_runner.py
```

`gate/b1-lane-b` is green only when all of these are true:

- the lane command is green
- direct tests prove the new seam metadata and unchanged runner behavior
- `runner.py` remains the only topology truth
- no validator-as-stage rewrite exists
- no new product semantics landed outside `contracts.py` and `runner.py`
- no code outside the owned files changed

### WS-C: State and Summary-Boundary Extraction with Direct Boundary Tests

Task ID:

- `task/b1-d1-state-summary-boundaries`

Owner:

- Worker `WS-C`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `anvil/harness/state.py`
- `anvil/harness/reporting.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/write_artifacts.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_reporting.py`

Files explicitly not owned by `WS-C`:

- `anvil/harness/contracts.py`
- `anvil/harness/runner.py`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/builder.py`
- `anvil/harness/nodes/select_strategy.py`
- `anvil/harness/selection.py`
- `anvil/harness/validation.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/schemas.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_selection.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_lg_offline_smoke.py`
- all `examples/harness/*` surfaces

Required changes:

- extend `HarnessState` with these exact B1 fields:
  - `serialization_version`
  - `analysis_review_contract`
  - `strategy_graph_spec`
  - `strategy_graph_spec_id`
  - `strategy_graph_subset`
  - `focus_decision`
  - `topic_ledger`
  - `summary_boundary_version`
  - `bridge_boundary_version`
- add `summary_read_adapter_v1(...)` in `anvil/harness/state.py`
- convert `state_from_summary(...)` into a compatibility wrapper only
- add `summary_projection_v1(...)` in `anvil/harness/reporting.py`
- make `write_state_artifacts(...)` delegate through `summary_projection_v1(...)`
- rewire `_bridge.py` into an explicit `LegacyBridgeBoundary`
- keep `analysis_review_v1.py` a thin wrapper only
- rewire `write_artifacts_node` to use this exact order:
  - `summary_projection_v1(...)`
  - `apply_final_artifacts(...)`
  - `summary_read_adapter_v1(...)`
- add short comments at the bridge and projection call sites stating that no new semantics may land there
- add direct tests proving the read and write boundaries
- update `tests/test_harness_reporting.py` only as needed to prove artifact and report parity after the boundary extraction
- preserve current artifact and summary behavior

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_reporting.py
```

`gate/b1-lane-c` is green only when all of these are true:

- the lane command is green
- direct tests prove the explicit read and write boundaries
- reporting assertions still prove the same externally visible artifact and report surface
- there is exactly one sanctioned summary-to-state path
- there is exactly one sanctioned state-to-summary path
- `write_artifacts_node` stays orchestration-thin
- bridge files are clearly labeled compatibility boundaries
- no code outside the owned files changed

## Context-Control Rules

### Parent Live Context Policy

Parent keeps only this narrow live set in active context:

- root `PLAN.md`
- root `ORCH_PLAN.md`
- `invariants.md`
- `interface-freeze.md`
- `boundary-freeze.md`
- `queue.md`
- `state.json`
- the active lane packet
- the active gate result being reviewed

Parent does not keep full worker transcripts in live context after accepting a narrow handoff.

### Worker Packet Policy

Each worker packet contains only:

- task ID
- owned file list
- relevant `PLAN.md` excerpt copied from `inputs/PLAN.session.md`
- exact acceptance commands
- frozen interface decisions already published by the parent
- forbidden surfaces
- blocker protocol

Worker packets do not include:

- unrelated repo summaries
- peer-lane transcripts
- full milestone prose outside the lane excerpt

### Worker Return Policy

Each worker returns only:

- changed files
- commands run
- pass or fail status
- exact blocker, if any

Workers do not return:

- long freeform transcripts
- redesign pitches
- peer-lane reviews

### Parent Review Policy

Parent reviews:

- worker summary
- narrow diff in owned files
- lane gate output

Parent does not review:

- full worker reasoning transcripts
- broad repo-wide diffs when the lane owns a small file set
- peer-lane internals unless a blocker requires it

## Repo Tests and Acceptance

### 1. Targeted Regression Sweep

Run on the integrated tree.

Required commands:

```bash
poetry run pytest -q \
  tests/test_harness_strategy_graph.py \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
  tests/test_harness_selection.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_run_focus_gate_acceptance.py

poetry run pytest -q tests/test_lg_offline_smoke.py

poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

`gate/b1-targeted-regressions` is green only when every command above passes.

### 2. Acceptance Checklist

The branch is done only when all of these are true:

- `StrategyGraphSpec` exists and represents the approved bounded subset only
- `StageSpec` exists for current harness strategy families
- `select_strategy_node` emits explicit strategy graph metadata
- `HarnessState` carries `serialization_version` and the B1 state fields required for seam ownership and B2 parity setup
- `summary_read_adapter_v1(...)` is the only sanctioned summary-to-state path
- `state_from_summary(...)` is only a compatibility wrapper around `summary_read_adapter_v1(...)`
- `summary_projection_v1(...)` is the only sanctioned state-to-summary path
- `write_state_artifacts(...)` delegates through `summary_projection_v1(...)`
- `_bridge.py` is explicitly bridge-only and does not gain new semantics
- `write_artifacts_node` is explicitly projection-only and does not gain new publication semantics
- `runner.py` remains the only topology truth for B1 execution
- each implementation lane landed the direct tests that prove its own seam contract
- existing harness reporting, prompt, acceptance, example, selection, and offline smoke tests remain green
- harness CLI help still works
- existing Forge CLI still works

### 3. Parent Acceptance Review

Parent acceptance review must also verify:

- the integrated diff still matches the B1 file change contract
- no prompt or schema widening slipped in
- `anvil/harness/selection.py`, `anvil/harness/validation.py`, and `anvil/harness/semantic_validation.py` stayed untouched unless a blocker-driven exception was explicitly approved
- no bridge file gained policy, selection, validator, or publication semantics
- example strategies, tasks, and live acceptance manifests remained validation surfaces unless a blocker forced a parent-approved serialized edit
- no B1 change depends on an untested implicit summary field
- the integrated tree still preserves current user-facing harness behavior

### 4. Green Conditions

`gate/b1-complete` is green only when all of these are true:

- `gate/b1-lane-a` is green
- `gate/b1-lane-b` is green
- `gate/b1-lane-c` is green
- `gate/b1-targeted-regressions` is green
- `gate/b1-acceptance` is green

## Assumptions

- The parent will create a new integration branch from the current `main` worktree instead of implementing directly on `main`.
- The untracked root `PLAN.md` is stable enough to snapshot at kickoff; if it changes materially, the parent will pause and republish freezes.
- `anvil/harness/subgraphs/analysis_review_v1.py` will likely need only a thin import or wrapper update when `_bridge.py` is renamed to an explicit legacy boundary.
- Example strategies, tasks, and live acceptance manifests are preserved by default for B1; if a test proves one must change, the parent will serialize that as an explicit blocker-driven exception.
- Lane-level gates are intentionally strong because each lane owns the direct tests for its own seam contract rather than deferring them to a late standalone test lane.
- `build_analysis_review_contract(...)` remains usable during `WS-A`; `resolve_analysis_review_contract(...)` is introduced in `WS-B` without forcing a duplicate contract path.
