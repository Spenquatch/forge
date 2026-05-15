# ORCH_PLAN: B2 Graph-Owned `analysis_review` Parity

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff workspace: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff branch context: `codex/b1-seam-extraction`  
Authoritative implementation plan: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`  
Historical orchestration reference: `/Users/spensermcconnell/__Active_Code/forge/docs/project_management/plans/history/ORCH_PLAN.md`

This orchestration plan replaces the stale B1 orchestration with a B2 plan for
`PLAN.md`: graph-owned `analysis_review` parity for the harness strangler.

What this run must deliver:

- make the graph the real entrypoint for both `memory` and `sqlite`
  checkpoints
- add request-level rollout control with exact values `legacy_bridge` and
  `graph_owned`
- keep the parent graph shape stable and migrate only the
  `analysis_review_v1` internals
- extract shared stage semantics into one new
  `anvil/harness/analysis_review_runtime.py` module
- preserve `summary_projection_v1(...)` as the only write-side boundary
- keep `summary_read_adapter_v1(...)` only in the locations allowed by
  `PLAN.md`
- prove the full B2 parity matrix and preserve rollback safety

This milestone is topology migration only. B3 cleanup is out of scope. The
parent agent owns kickoff, freeze points, worker dispatch, worktree creation,
integration, conflict resolution, gate reruns, and final acceptance. The parent
is the only integrator.

## Orchestration Runtime Policy

Parent runtime policy:

- `PLAN.md` is the active authored source for this session. If this file and
  `PLAN.md` disagree, `PLAN.md` wins.
- The root `PLAN.md` is currently modified in the main workspace. The parent
  snapshots it into the orchestration state root before dispatch, but the root
  file remains the authoritative source.
- The parent verifies the B2 precondition from `PLAN.md` before dispatch:
  implementation starts only once the integration tree is at a
  B1-landed-on-`main` equivalent state.
- The parent is the only agent allowed to create or switch the integration
  branch, create worktrees, merge worker branches, resolve conflicts, reopen
  lanes, or approve scope changes.
- The parent keeps all shared-touchpoint integration local, especially
  `anvil/harness/state.py`, freeze documents, and final regression.

Worker runtime policy:

- Every worker runs on `GPT-5.4` with `reasoning_effort=high`.
- Workers execute only their lane packet, owned files, frozen contracts, and
  declared validation commands.
- Workers do not merge, rebase for integration, widen scope, rename frozen
  contracts, or edit parent-owned orchestration files.
- Workers treat the copied `PLAN.md` excerpt in their packet as a dispatch
  snapshot, not as permission to diverge from the parent-owned plan.

Concurrency policy:

- Maximum concurrent worker lanes: `2`
- The core implementation is mostly sequential.
- Only one partially parallel test front is allowed:
  - `WS-E1` may run after Lane A freezes the request contract
  - it runs in parallel with `WS-B`
- `WS-C`, `WS-D`, and `WS-E2` remain serialized behind their upstream freezes

## Hard Guards

1. `PLAN.md` is authoritative. If this file and `PLAN.md` disagree, follow
   `PLAN.md`.
2. B2 scope is topology migration only. B3 state/reporting/selection cleanup is
   out of scope.
3. The default `analysis_review_execution_mode` in B2 remains `legacy_bridge`
   until the full parity matrix is green.
4. The only allowed execution-mode values are `legacy_bridge` and
   `graph_owned`.
5. Both `memory` and `sqlite` checkpoint modes must route through
   `HarnessLangGraphExecutor`.
6. The parent graph shape stays
   `prepare_run -> validator_preflight -> select_strategy -> analysis_review_v1 -> select_best_draft -> write_artifacts -> finalize`.
7. The migrated wedge is only the internals of `analysis_review_v1`.
8. `anvil/harness/subgraphs/_bridge.py` remains rollback plumbing only. No new
   semantics land there.
9. `HarnessRunner` may remain as fallback plumbing, but it may not remain the
   only topology truth after B2.
10. Shared stage semantics are extracted into one new
    `anvil/harness/analysis_review_runtime.py` module. No second runtime truth.
11. `summary_projection_v1(...)` remains the only write-side boundary.
12. `summary_read_adapter_v1(...)` is allowed only:
    - inside `LegacyBridgeBoundary.run(...)`
    - after projection in `write_artifacts_node`
    - in compatibility and parity tests
13. Graph-owned success paths may not rehydrate from summary before
    `write_artifacts`.
14. `summary_projection_v1(...)` and `summary_read_adapter_v1(...)` must not be
    duplicated under new names.
15. Validators remain adjacent orchestration helpers, not public graph stages.
16. `StrategyGraphSpec` remains the declared topology contract. Do not invent a
    second spec surface.
17. `run_details.graph_execution` and `StageRecord.metadata` are the only
    approved new trace surfaces for graph execution evidence.
18. Trust mode and bounded mode ship through the same topology family. No
    bounded-only graph cutover.
19. `anvil/harness/state.py` is a serialized shared surface. It is never
    concurrently owned by multiple active code lanes.
20. The parent is the only integrator.

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit Gate |
|---|---|---|---|---|
| Phase A: Kickoff and Preconditions | `task/b2-a1` to `task/b2-a6` | Parent | Strictly serialized | state root exists, plan snapshot exists, B1-equivalent tree verified, integration branch and initial worktrees created |
| Phase B: Request Contract and Graph Entrypoint | `task/b2-b1` | `WS-A` | Serialized | `gate/b2-lane-a` |
| Phase C: Parent Merge and Request Freeze | `task/b2-c1`, `task/b2-c2` | Parent | Strictly serialized | `request-freeze.md` published |
| Phase D: Runtime Extraction plus Early Tests | `task/b2-d1`, `task/b2-d2` | `WS-B`, `WS-E1` | Parallel | `gate/b2-lane-b`, `gate/b2-lane-e1` |
| Phase E: Parent Merge and Runtime Freeze | `task/b2-e1`, `task/b2-e2` | Parent | Strictly serialized | `runtime-freeze.md` published |
| Phase F: Graph-Owned Subgraph Wiring | `task/b2-f1` | `WS-C` | Serialized | `gate/b2-lane-c` |
| Phase G: Parent Merge and Topology Freeze | `task/b2-g1`, `task/b2-g2` | Parent | Strictly serialized | `topology-freeze.md` published |
| Phase H: Reporting and Trace Projection | `task/b2-h1` | `WS-D` | Serialized | `gate/b2-lane-d` |
| Phase I: Parent Merge and Trace Freeze | `task/b2-i1`, `task/b2-i2` | Parent | Strictly serialized | `trace-freeze.md` published |
| Phase J: Parity Matrix and Rollback Proof | `task/b2-j1` | `WS-E2` | Serialized | `gate/b2-lane-e2` |
| Phase K: Parent Final Regression and Acceptance | `task/b2-k1` to `task/b2-k3` | Parent | Strictly serialized | `gate/b2-targeted-regressions`, `gate/b2-acceptance`, `gate/b2-complete` |

### Launch Order

1. `task/b2-a1-read-authority`
2. `task/b2-a2-verify-b1-precondition`
3. `task/b2-a3-snapshot-active-plan`
4. `task/b2-a4-freeze-invariants`
5. `task/b2-a5-create-state-root`
6. `task/b2-a6-create-integration-branch-and-worktrees`
7. Dispatch `WS-A`
8. Merge `WS-A`
9. Publish `request-freeze.md`
10. Dispatch `WS-B`
11. Dispatch `WS-E1`
12. Merge `WS-E1` and `WS-B` after gate verification
13. Publish `runtime-freeze.md`
14. Dispatch `WS-C`
15. Merge `WS-C`
16. Publish `topology-freeze.md`
17. Dispatch `WS-D`
18. Merge `WS-D`
19. Publish `trace-freeze.md`
20. Dispatch `WS-E2`
21. Merge `WS-E2`
22. Run parent-only final regression and acceptance sweep

### Merge Order

Merge ordering is constrained as follows:

1. `WS-A` must merge first.
2. `WS-B` and `WS-E1` may merge in either order after `WS-A`, but
   `runtime-freeze.md` is published only after `WS-B` merges.
3. `WS-C` merges after `WS-B`.
4. `WS-D` merges after `WS-C`.
5. `WS-E2` merges last.
6. Final regression and acceptance are parent-only on the integrated tree.

### Phase Tasks

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/b2-a1-read-authority` | Re-read root `PLAN.md`, this `ORCH_PLAN.md`, and the historical orchestration reference | Parent | Parent can restate scope and locks exactly |
| `task/b2-a2-verify-b1-precondition` | Verify the integration tree is at a B1-landed-on-`main` equivalent state before dispatch | Parent | Precondition recorded in `state.json` |
| `task/b2-a3-snapshot-active-plan` | Copy the active root `PLAN.md` into the state root and record its hash | Parent | `inputs/PLAN.session.md` and hash recorded |
| `task/b2-a4-freeze-invariants` | Freeze lane ownership, serialized surfaces, gate commands, and blocker protocol | Parent | `invariants.md` written |
| `task/b2-a5-create-state-root` | Create the repo-local orchestration state root and sentinel layout | Parent | State root initialized |
| `task/b2-a6-create-integration-branch-and-worktrees` | Create the integration branch from the kickoff branch context and create worker worktrees | Parent | Branch and worktrees created |
| `task/b2-b1-request-contract-entrypoint` | Land rollout control, request-state contract, and graph entrypoint routing | `WS-A` | `gate/b2-lane-a` |
| `task/b2-c1-merge-ws-a` | Merge `WS-A` and rerun its gate in the integration tree | Parent | `WS-A` merged |
| `task/b2-c2-publish-request-freeze` | Publish the exact request contract and graph-entrypoint freeze | Parent | `request-freeze.md` written |
| `task/b2-d1-runtime-extraction` | Extract shared runtime helpers and keep legacy plumbing functional | `WS-B` | `gate/b2-lane-b` |
| `task/b2-d2-early-cli-executor-tests` | Land the early CLI/executor regression pass against the frozen request contract | `WS-E1` | `gate/b2-lane-e1` |
| `task/b2-e1-merge-b-and-e1` | Merge `WS-B` and `WS-E1`, rerunning their gates in the integration tree | Parent | `WS-B` and `WS-E1` merged |
| `task/b2-e2-publish-runtime-freeze` | Publish the exact runtime-bag keys and helper boundary expectations | Parent | `runtime-freeze.md` written |
| `task/b2-f1-graph-owned-subgraph` | Replace the bridge wrapper with the real internal graph-owned `analysis_review_v1` topology | `WS-C` | `gate/b2-lane-c` |
| `task/b2-g1-merge-ws-c` | Merge `WS-C` and rerun its gate | Parent | `WS-C` merged |
| `task/b2-g2-publish-topology-freeze` | Publish route-helper, metadata-key, and no-summary-rehydrate freeze | Parent | `topology-freeze.md` written |
| `task/b2-h1-reporting-trace-projection` | Project graph trace metadata through existing reporting surfaces | `WS-D` | `gate/b2-lane-d` |
| `task/b2-i1-merge-ws-d` | Merge `WS-D` and rerun its gate | Parent | `WS-D` merged |
| `task/b2-i2-publish-trace-freeze` | Publish the approved reporting and `run_details.graph_execution` shape | Parent | `trace-freeze.md` written |
| `task/b2-j1-parity-matrix-and-rollback` | Land the full parity and rollback proof matrix | `WS-E2` | `gate/b2-lane-e2` |
| `task/b2-k1-targeted-regression-sweep` | Run the full `PLAN.md` validation command set on the integrated tree | Parent | `gate/b2-targeted-regressions` |
| `task/b2-k2-acceptance-checklist-review` | Verify the integrated tree against the B2 acceptance checklist | Parent | `gate/b2-acceptance` |
| `task/b2-k3-final-verdict` | Record green or blocked milestone verdict | Parent | `gate/b2-complete` |

## Orchestration State and Source of Truth

The parent maintains one repo-local orchestration state root for the full run:

- `.runs/b2-graph-owned-analysis-review-parity-orch/`

Required layout:

- `.runs/b2-graph-owned-analysis-review-parity-orch/queue.md`
- `.runs/b2-graph-owned-analysis-review-parity-orch/state.json`
- `.runs/b2-graph-owned-analysis-review-parity-orch/invariants.md`
- `.runs/b2-graph-owned-analysis-review-parity-orch/request-freeze.md`
- `.runs/b2-graph-owned-analysis-review-parity-orch/runtime-freeze.md`
- `.runs/b2-graph-owned-analysis-review-parity-orch/topology-freeze.md`
- `.runs/b2-graph-owned-analysis-review-parity-orch/trace-freeze.md`
- `.runs/b2-graph-owned-analysis-review-parity-orch/session.log`
- `.runs/b2-graph-owned-analysis-review-parity-orch/handoffs/`
- `.runs/b2-graph-owned-analysis-review-parity-orch/gates/`
- `.runs/b2-graph-owned-analysis-review-parity-orch/logs/`
- `.runs/b2-graph-owned-analysis-review-parity-orch/sentinels/`
- `.runs/b2-graph-owned-analysis-review-parity-orch/inputs/`
- `.runs/b2-graph-owned-analysis-review-parity-orch/acceptance/`

### File Roles

- `queue.md`
  - Canonical task table with one row per `task/b2-*`
  - Tracks owner, state, gate, reopen reason, and merge status
- `state.json`
  - Current phase, active lanes, branch names, plan hash, B1-precondition
    status, blockers, merge state, and final verdict
- `invariants.md`
  - Frozen scope, ownership boundaries, serialized surfaces, commands, and gate
    definitions
- `request-freeze.md`
  - Parent-accepted freeze after `WS-A`
  - Freezes exact request-contract names:
    - `--analysis-review-execution-mode`
    - `legacy_bridge`
    - `graph_owned`
    - `analysis_review_execution_mode`
    - `analysis_review_runtime`
  - Freezes the rule that both checkpoint modes enter through
    `HarnessLangGraphExecutor`
- `runtime-freeze.md`
  - Parent-accepted freeze after `WS-B`
  - Freezes the `analysis_review_runtime` bag keys required by `PLAN.md`:
    - `current_analysis_payload`
    - `current_review_payload`
    - `latest_validator_round`
    - `revisions_completed`
    - `max_loops`
    - `focus_refinement`
    - `transition_reason`
    - `review_loop_exercised`
- `topology-freeze.md`
  - Parent-accepted freeze after `WS-C`
  - Freezes:
    - execution-mode routing behavior
    - focus-gate outcome routing
    - critic/auditor revision routing
    - trust-attestation routing
    - the rule that graph-owned success paths do not call
      `summary_read_adapter_v1(...)` before `write_artifacts`
    - the metadata keys:
      - `metadata.graph_node_id`
      - `metadata.transition_reason`
      - `metadata.semantic_validation_outcome`
      - `metadata.execution_mode`
- `trace-freeze.md`
  - Parent-accepted freeze after `WS-D`
  - Freezes the optional `run_details.graph_execution` block:
    - `execution_mode`
    - `graph_owned`
    - `fallback_used`
    - `transition_log`
- `session.log`
  - Parent-only sequential log of dispatches, readiness, blockers, merges,
    reopen events, and final decisions
- `inputs/PLAN.session.md`
  - Immutable kickoff snapshot of the active root `PLAN.md`
  - This is a run artifact snapshot, not the authored source of truth
- `inputs/PLAN.session.sha256`
  - Hash of the kickoff `PLAN.md` snapshot
- `handoffs/task-b2-*.md`
  - Narrow worker packets and parent-accepted return summaries
- `gates/*.md`
  - Parent gate results with exact commands and verdicts
- `acceptance/`
  - Final command outputs, parity observations, rollback notes, and acceptance
    evidence used during milestone review

### Git-Tracked Authored Sources vs Run Artifacts

Git-tracked authored sources for this milestone include:

- root `ORCH_PLAN.md`
- root `PLAN.md`
- `anvil/harness/cli.py`
- `anvil/harness/executor.py`
- `anvil/harness/nodes/prepare_run.py`
- `anvil/harness/state.py`
- new `anvil/harness/analysis_review_runtime.py`
- `anvil/harness/runner.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/builder.py`
- `anvil/harness/reporting.py`
- targeted `anvil/harness/report.py` updates only if required
- targeted B2 test expansions and new parity tests under `tests/`

Run artifacts that must not be committed:

- everything under `.runs/b2-graph-owned-analysis-review-parity-orch/`
- copied plan snapshots and hashes under `.runs/.../inputs/`
- worker packets, gate logs, command logs, and acceptance notes
- temporary smoke output directories created only for gate commands

### Plan Drift Rule

If the root `PLAN.md` changes after kickoff and its content no longer matches
`inputs/PLAN.session.sha256`, the parent must halt dispatch and integration,
diff the plan change, and either:

- republish freezes and reopen affected lanes, or
- explicitly declare the drift out of scope for the current run

Workers do not continue on stale plan packets once the parent declares plan
drift.

## Sentinel Conventions

Per-task sentinels live under:

- `.runs/b2-graph-owned-analysis-review-parity-orch/sentinels/`

Required sentinel names:

- `task-b2-*.dispatched`
- `task-b2-*.ready`
- `task-b2-*.blocked`
- `task-b2-*.merged`
- `task-b2-*.failed-gate`

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
- the next required freeze publication

## Worktree and Branch Plan

Integration worktree:

- Path: `/Users/spensermcconnell/__Active_Code/forge`
- Kickoff branch context: `codex/b1-seam-extraction`
- Integration branch: `codex/b2-graph-owned-analysis-review-parity`
- Owner: Parent only

Sibling worktree root:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/`

Lane worktrees:

- `WS-A`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-a-request-entrypoint`
  - Branch: `codex/b2-ws-a-request-entrypoint`
- `WS-B`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-b-runtime-extraction`
  - Branch: `codex/b2-ws-b-runtime-extraction`
- `WS-C`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-c-subgraph-wiring`
  - Branch: `codex/b2-ws-c-subgraph-wiring`
- `WS-D`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-d-reporting-trace`
  - Branch: `codex/b2-ws-d-reporting-trace`
- `WS-E1`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-e1-cli-tests`
  - Branch: `codex/b2-ws-e1-cli-tests`
- `WS-E2`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-e2-parity-matrix`
  - Branch: `codex/b2-ws-e2-parity-matrix`

### Worktree Creation Commands

Create the integration branch in the current workspace after snapshotting the
modified root `PLAN.md` so the active authored plan remains available:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge switch -c \
  codex/b2-graph-owned-analysis-review-parity

mkdir -p \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-a-request-entrypoint \
  -b codex/b2-ws-a-request-entrypoint \
  codex/b2-graph-owned-analysis-review-parity

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-b-runtime-extraction \
  -b codex/b2-ws-b-runtime-extraction \
  codex/b2-graph-owned-analysis-review-parity

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-e1-cli-tests \
  -b codex/b2-ws-e1-cli-tests \
  codex/b2-graph-owned-analysis-review-parity
```

Create the remaining worktrees only when the upstream freeze exists:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-c-subgraph-wiring \
  -b codex/b2-ws-c-subgraph-wiring \
  codex/b2-graph-owned-analysis-review-parity

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-d-reporting-trace \
  -b codex/b2-ws-d-reporting-trace \
  codex/b2-graph-owned-analysis-review-parity

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b2-graph-owned-analysis-review-parity/ws-e2-parity-matrix \
  -b codex/b2-ws-e2-parity-matrix \
  codex/b2-graph-owned-analysis-review-parity
```

### Worktree Rules

- The parent is the only integrator.
- Workers never merge peer branches.
- Workers never rebase peer changes into their own lane unless the parent
  instructs it.
- Parent resolves every merge or rebase in the integration worktree only.
- `anvil/harness/state.py` is serialized across lanes:
  - `WS-A` owns the initial request-contract edit
  - `WS-B` owns the runtime-bag follow-up
  - `WS-C` owns the final topology-consumer follow-up
- If a lane needs a peer-owned change, it raises a blocker instead of editing
  that file.
- Worker worktrees must not assume the modified root `PLAN.md` is present. They
  rely on the parent-issued snapshot and lane excerpt.
- `WS-C` does not launch until `runtime-freeze.md` exists.
- `WS-D` does not launch until `topology-freeze.md` exists.
- `WS-E2` does not launch until `trace-freeze.md` exists.

## Blocker, Freeze-Change, and Conflict Protocols

### Blocker Protocol

A worker must mark `.blocked` and stop when any of these occur:

- it needs a peer-owned file change
- it needs to touch `anvil/harness/state.py` outside the currently assigned lane
- it cannot satisfy its lane gate without touching a frozen surface
- the parent-owned freeze document for its dependency does not exist
- the root `PLAN.md` changed and the parent declared plan drift
- a required change would widen summary/report shape beyond the `PLAN.md`
  allowance
- a required change would introduce a second summary boundary, second runtime
  truth, or second topology truth

Required blocker return:

- exact file or interface requested
- exact reason
- exact minimal parent decision needed
- exact command or failing assertion demonstrating the blocker, if relevant

### Freeze-Change Protocol

For this milestone, freeze-sensitive surfaces include:

- the CLI flag name and allowed values
- `analysis_review_execution_mode`
- `analysis_review_runtime`
- the runtime-bag keys named in `PLAN.md`
- route-helper behavior for focus gate, revision loops, and attestation routing
- the `summary_read_adapter_v1(...)` allowed-use rule
- the `summary_projection_v1(...)` write-boundary rule
- `metadata.graph_node_id`
- `metadata.transition_reason`
- `metadata.semantic_validation_outcome`
- `metadata.execution_mode`
- `run_details.graph_execution`

Worker behavior:

- do not change a frozen surface speculatively
- raise `.blocked`
- wait for a revised parent packet or an explicit freeze update

### Conflict Protocol

Conflict type: textual overlap

- Example: a lane begins editing a file already assigned to another active lane.
- Resolution: parent reassigns ownership or serializes the follow-up.
- Workers do not self-resolve peer overlap.

Conflict type: contract drift

- Example: `WS-D` needs reporting keys that do not match `topology-freeze.md`.
- Resolution: parent compares against `PLAN.md` and the freeze file, then
  reopens the affected lane.
- Workers do not invent fallback names.

Conflict type: topology drift

- Example: `WS-C` attempts to route success paths through summary rehydration.
- Resolution: stop immediately, mark blocked, and return the smallest drift
  summary.
- Parent either rejects the drift or replans explicitly.

Conflict type: parity drift

- Example: `WS-E2` finds summary/report mismatches outside approved graph trace
  metadata.
- Resolution: parent treats this as a rollback trigger, reopens the offending
  lane, and keeps `legacy_bridge` as the safe mode.

## Workstream Plan

### WS-A: Request Contract and Graph Entrypoint

Task ID:

- `task/b2-b1-request-contract-entrypoint`

Owned files:

- `anvil/harness/cli.py`
- `anvil/harness/executor.py`
- `anvil/harness/nodes/prepare_run.py`
- `anvil/harness/state.py`

Files explicitly not owned by `WS-A`:

- new `anvil/harness/analysis_review_runtime.py`
- `anvil/harness/runner.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/builder.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- all `tests/` files

Required changes:

- add CLI flag `--analysis-review-execution-mode` with exact allowed values
  `legacy_bridge` and `graph_owned`
- add matching executor parameter `analysis_review_execution_mode`
- route both `memory` and `sqlite` checkpoint modes through
  `HarnessLangGraphExecutor`
- persist `analysis_review_execution_mode` into initialized state
- initialize `analysis_review_runtime` as an empty dict
- keep non-`analysis_review` strategies tolerant of the flag
- preserve output, exit-code, and checkpoint semantics

Lane commands:

```bash
poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

`gate/b2-lane-a` is green only when all of these are true:

- the lane commands are green
- the exact request-contract names from `PLAN.md` are present
- both checkpoint modes now enter through `HarnessLangGraphExecutor`
- `anvil/harness/state.py` contains only the Phase 1 contract additions, not
  later topology logic
- no code outside the owned files changed

### WS-E1: Early CLI and Executor Regression Tests

Task ID:

- `task/b2-d2-early-cli-executor-tests`

Owned files:

- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`

Files explicitly not owned by `WS-E1`:

- all `anvil/harness/*` implementation files
- all other `tests/` files

Required changes:

- cover `--analysis-review-execution-mode` acceptance
- prove both checkpoint backends honor the execution-mode flag
- prove both checkpoint backends enter through the graph entrypoint
- keep non-`analysis_review` behavior stable

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_cli_command.py \
  tests/test_harness_standalone_cli.py
```

`gate/b2-lane-e1` is green only when all of these are true:

- the lane command is green
- the tests prove the new request contract without changing broader behavior
- no implementation files changed

### WS-B: Shared Runtime Extraction

Task ID:

- `task/b2-d1-runtime-extraction`

Owned files:

- new `anvil/harness/analysis_review_runtime.py`
- `anvil/harness/runner.py`
- `anvil/harness/state.py`
- `tests/test_harness_runner.py`

Files explicitly not owned by `WS-B`:

- `anvil/harness/cli.py`
- `anvil/harness/executor.py`
- `anvil/harness/nodes/prepare_run.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/builder.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- all other `tests/` files

Required changes:

- extract reusable stage-semantics helpers into one new internal runtime module
- cover focus gate, proposer, validator rounds, critic, reviser, auditor,
  trust attestation, ledger ingestion, and final verdict assembly
- keep the extraction explicit with plain helpers and plain data
- extend `analysis_review_runtime` with the keys frozen by `PLAN.md`
- leave `HarnessRunner._run_analysis_review_v1(...)` functional as rollback
  plumbing that reuses the extracted helpers

Lane commands:

```bash
poetry run pytest -q tests/test_harness_runner.py
```

`gate/b2-lane-b` is green only when all of these are true:

- the lane command is green
- no unique stage-semantics helper remains trapped only inside `runner.py`
- `anvil/harness/state.py` contains only the runtime-bag follow-up, not
  subgraph routing logic
- no code outside the owned files changed

### WS-C: Graph-Owned `analysis_review_v1` Subgraph

Task ID:

- `task/b2-f1-graph-owned-subgraph`

Owned files:

- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/builder.py`
- `anvil/harness/state.py`
- `tests/test_harness_state_boundaries.py`

Files explicitly not owned by `WS-C`:

- `anvil/harness/cli.py`
- `anvil/harness/executor.py`
- `anvil/harness/nodes/prepare_run.py`
- new `anvil/harness/analysis_review_runtime.py`
- `anvil/harness/runner.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_analysis_review_graph.py`
- `tests/test_run_focus_gate_acceptance.py`
- all other `tests/` files

Required changes:

- replace the thin bridge wrapper with the real graph-owned subgraph
- route by `analysis_review_execution_mode`
- implement explicit route helpers for:
  - execution mode
  - focus-gate outcome
  - critic revision
  - auditor revision
  - trust-attestation routing
- keep validators adjacent to review nodes, not as public graph stages
- ensure graph-owned success paths do not call `summary_read_adapter_v1(...)`
  before `write_artifacts`
- preserve `select_best_draft -> write_artifacts -> finalize`

Lane commands:

```bash
poetry run pytest -q tests/test_harness_state_boundaries.py
```

`gate/b2-lane-c` is green only when all of these are true:

- the lane command is green
- the bridge remains rollback-only and flag-driven
- graph-owned success paths carry native state to `write_artifacts`
- `anvil/harness/state.py` changes are limited to topology-consumer needs
- no code outside the owned files changed

### WS-D: Reporting and Trace Projection

Task ID:

- `task/b2-h1-reporting-trace-projection`

Owned files:

- `anvil/harness/reporting.py`
- `anvil/harness/report.py` only if required
- `tests/test_harness_reporting.py`

Files explicitly not owned by `WS-D`:

- all other `anvil/harness/*` files
- all other `tests/` files

Required changes:

- project graph-mode trace metadata through
  `stage_history -> agent_stages[*].metadata`
- add optional `run_details.graph_execution`
- preserve final artifact, report, and summary shape outside the approved trace
  additions
- keep `summary_projection_v1(...)` as the only write-side contract

Lane commands:

```bash
poetry run pytest -q tests/test_harness_reporting.py
```

`gate/b2-lane-d` is green only when all of these are true:

- the lane command is green
- approved trace additions are visible
- no artifact or summary drift appears outside the approved additions
- no code outside the owned files changed

### WS-E2: Full Parity Matrix and Rollback Proof

Task ID:

- `task/b2-j1-parity-matrix-and-rollback`

Owned files:

- `tests/test_harness_analysis_review_graph.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_strategy_graph.py` only if needed
- `tests/test_run_focus_gate_acceptance.py`

Files explicitly not owned by `WS-E2`:

- all implementation files
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_state_boundaries.py`

Required changes:

- implement the full B2 parity matrix from `PLAN.md`
- compare `legacy_bridge` and `graph_owned` on:
  - stage sequence and count
  - normalized payload boundaries
  - `focus_decision`
  - `analysis_review_status`
  - `issue_ledger`
  - `topic_ledger`
  - `recommendation_reviews`
  - final artifacts
  - `summary.json`
  - `REPORT.md`
  - workspace policy verdict and touched-files surface
- cover:
  - bounded, no focus gate
  - bounded, focus-gate selected
  - bounded, focus-gate blocked
  - bounded, focus-gate no viable focus
  - trust `attestation_over_bounded`, focus gate off
  - trust `attestation_over_bounded`, focus gate on
  - invalid config and preflight failure
  - memory and sqlite checkpoint backend coverage
- keep rollback proof green by rerunning the same rows in `legacy_bridge`

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_analysis_review_graph.py \
  tests/test_harness_strategy_graph.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_run_focus_gate_acceptance.py
```

`gate/b2-lane-e2` is green only when all of these are true:

- the lane command is green
- every parity row from `PLAN.md` is covered
- rollback rows remain green
- no implementation files changed

## Context-Control Rules

### Parent Live Context Policy

Parent keeps only this narrow live set in active context:

- root `PLAN.md`
- root `ORCH_PLAN.md`
- `invariants.md`
- `request-freeze.md`
- `runtime-freeze.md`
- `topology-freeze.md`
- `trace-freeze.md`
- `queue.md`
- `state.json`
- the active lane packet
- the active gate result being reviewed

Parent does not keep full worker transcripts in live context after accepting a
narrow handoff.

### Worker Packet Policy

Each worker packet contains only:

- task ID
- owned file list
- relevant `PLAN.md` excerpt copied from `inputs/PLAN.session.md`
- exact acceptance commands
- the current upstream freeze document
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
  tests/test_harness_analysis_review_graph.py \
  tests/test_harness_strategy_graph.py \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_cli_command.py \
  tests/test_harness_standalone_cli.py \
  tests/test_run_focus_gate_acceptance.py

poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

`gate/b2-targeted-regressions` is green only when every command above passes.

### 2. Acceptance Checklist

The branch is done only when all of these are true:

- rollout flag exists and is honored by CLI and executor
- both checkpoint modes enter through `HarnessLangGraphExecutor`
- `analysis_review_execution_mode` exists with exact values `legacy_bridge` and
  `graph_owned`
- `analysis_review_runtime` exists and is the only graph-owned transient state
  bag
- graph-owned `analysis_review_v1` topology exists for bounded and trust modes
- fallback mode still routes through `LegacyBridgeBoundary`
- `HarnessRunner` no longer owns unique stage semantics by itself
- graph-owned success paths do not rehydrate from summary before
  `write_artifacts`
- `summary_projection_v1(...)` remains the sole write boundary
- `summary_read_adapter_v1(...)` remains only in its approved locations
- stage metadata and `run_details.graph_execution` expose execution mode and
  transition reasons
- the full B2 parity matrix is green
- rollback coverage for `legacy_bridge` remains green
- the default rollout mode remains `legacy_bridge`

### 3. Parent Acceptance Review

Parent acceptance review must also verify:

- the integrated diff still matches the B2 file change contract in `PLAN.md`
- no memory-checkpoint path bypasses the graph
- no graph-owned success path uses summary rehydration before `write_artifacts`
- no second topology truth or second runtime truth was introduced
- trust and bounded modes still share one topology family
- no artifact or summary drift appears outside approved trace metadata
- no B3 cleanup leaked into the milestone

### 4. Green Conditions

`gate/b2-complete` is green only when all of these are true:

- `gate/b2-lane-a` is green
- `gate/b2-lane-b` is green
- `gate/b2-lane-c` is green
- `gate/b2-lane-d` is green
- `gate/b2-lane-e1` is green
- `gate/b2-lane-e2` is green
- `gate/b2-targeted-regressions` is green
- `gate/b2-acceptance` is green

## Assumptions

- The kickoff workspace starts on `codex/b1-seam-extraction`, but the parent
  creates a dedicated B2 integration branch before dispatch.
- The B2 precondition from `PLAN.md` is satisfied either because B1 has landed
  on `main` or because the integration tree has been advanced to the same code
  state before work begins.
- The modified root `PLAN.md` is stable enough to snapshot at kickoff; if it
  changes materially, the parent will pause and republish freezes.
- `anvil/harness/state.py` is the highest-conflict file, so serialization across
  A -> B -> C is cheaper and safer than trying to parallelize core code lanes.
- The only worthwhile parallelism is the early CLI/executor test front after
  Lane A. The rest of the core remains sequential by design.
- If final parity exposes cleanup debt beyond the approved trace additions, that
  debt is recorded for B3 rather than absorbed into B2.

## Done Criteria

This milestone is done when a developer can run the same canonical
`analysis_review` task/strategy pair twice, once with `legacy_bridge` and once
with `graph_owned`, through either checkpoint backend, and the only intentional
observable difference is the approved graph trace metadata proving that the
graph owned the topology.
