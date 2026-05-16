# ORCH_PLAN: B3 Graph-Native State / Selection / Artifact Canonicalization

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff workspace: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff branch context: `codex/b2-graph-owned-analysis-review-parity`  
Authoritative implementation plan: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`  
Historical orchestration reference: `/Users/spensermcconnell/__Active_Code/forge/docs/project_management/plans/history/ORCH_PLAN.md`

This orchestration plan supersedes the stale B2 root orchestration and defines
the parent-agent-led execution model for B3 from kickoff through final
acceptance.

What this run must deliver:

- complete the native `HarnessState` contract for the migrated
  `analysis_review` surface
- split canonical native draft projection from summary compatibility parsing
- make `select_best_draft_node(...)` the only graph-path ranking owner
- publish `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, `BEST_DRAFT.*`, `summary.json`,
  and `REPORT.md` from native state on the graph-owned success path
- keep `summary_projection_v1(...)` as the only sanctioned summary write seam
- reduce `summary_read_adapter_v1(...)` and `state_from_summary(...)` to
  explicit compatibility-only seams
- preserve `legacy_bridge` as the rollback path and keep rollout semantics
  unchanged
- prove the B3 parity matrix, historical summary readability, and the deleted
  success-path rehydration bridge by test

This is one serial implementation spine with one honest parallel test lane
beside it. The parent agent owns kickoff, precondition proof, freeze docs,
dispatch, merge order, conflict resolution, gate reruns, and final acceptance.
The parent is the only integrator.

## Orchestration Runtime Policy

Parent runtime policy:

- `PLAN.md` is the authored source of truth for the session. If this file and
  `PLAN.md` disagree, `PLAN.md` wins.
- The parent snapshots the active root `PLAN.md` into the orchestration state
  root before dispatch, but the root file remains authoritative.
- The parent verifies the B3 precondition from `PLAN.md` before dispatch:
  B2 parity must already be green on `main`, or the integration tree must be
  proven equivalent to that landed B2 state.
- The parent is the only agent allowed to create or switch the integration
  branch, create worktrees, publish freeze docs, merge worker branches, resolve
  conflicts, reopen lanes, or approve scope changes.
- The parent keeps every shared-surface integration local, especially
  `anvil/harness/state.py`, `anvil/harness/reporting.py`, gate reruns, and the
  final parity sweep.

Worker runtime policy:

- Every worker runs on `GPT-5.4` with `reasoning_effort=high`.
- Workers execute only their lane packet, owned files, frozen contracts, and
  declared gate commands.
- Workers do not merge, rebase for integration, widen scope, rename frozen
  interfaces, or edit parent-owned orchestration state.
- Workers treat the copied `PLAN.md` excerpt in their packet as a dispatch
  snapshot, not as permission to diverge from the root plan.

Concurrency policy:

- Maximum concurrent worker lanes: `2`
- Maximum concurrent code lanes on shared implementation surfaces: `1`
- Practical concurrency window:
  - `WS-A` runs first alone
  - `WS-B` and `WS-E1` may run in parallel after `state-contract-freeze.md`
  - `WS-C`, `WS-D`, and `WS-E2` remain serialized behind their upstream freezes
- `WS-C` is not a real parallel coding lane with `WS-B` on
  `anvil/harness/reporting.py`; if its worktree is created early, it stays
  packeted-only until `selection-freeze.md` exists

## Hard Guards

1. `PLAN.md` is authoritative. If this file and `PLAN.md` disagree, follow
   `PLAN.md`.
2. B3 does not start until B2 parity is already green on `main`.
3. Scope is limited to the migrated `analysis_review` surface.
4. Do not widen into `single_pass`, `pfr_v1`, or C-series graph/compiler work.
5. External artifact semantics stay stable in B3. `summary.json`, `REPORT.md`,
   `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*` may gain approved
   graph-trace metadata only.
6. `HarnessState` is canonical for graph-owned migrated surfaces.
7. Graph-owned success-path helpers may not refill required fields from
   `summary_payload`.
8. `drafts_from_stage_history_v1(...)` is the canonical draft projector for the
   graph-owned path.
9. `extract_drafts_from_summary(...)` remains compatibility-only.
10. `select_best_draft_node(...)` is the only canonical ranking owner on the
    graph-owned path.
11. `anvil/harness/reporting.py` may validate selected ids, but it may not make
    a second ranking decision on graph-owned success execution.
12. `summary_projection_v1(...)` remains the only sanctioned summary write
    boundary.
13. `summary_read_adapter_v1(...)` and `state_from_summary(...)` are allowed
    only:
    - inside `LegacyBridgeBoundary.run(...)`
    - in historical summary/readability tooling
    - in compatibility and parity tests
14. No graph-owned success path may call `summary_read_adapter_v1(...)`.
15. No graph-owned success path may call `state_from_summary(...)`.
16. No graph-owned success path may stamp `bridge_boundary_version`.
17. `bridge_boundary_version` is set only by the actual legacy bridge path.
18. `anvil/harness/runner.py` is conditional-touch only under the `PLAN.md`
    touch rule. It is never a convenience spillover file.
19. `legacy_bridge` remains the boring rollback path for the full milestone.
20. B3 does not change rollout defaults, flags, or operator playbooks.
21. `anvil/harness/state.py` is a serialized surface across lanes.
22. `anvil/harness/reporting.py` is a serialized surface across selection and
    publisher lanes.
23. The parent is the only integrator.

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit Gate |
|---|---|---|---|---|
| Phase A: Kickoff and Preconditions | `task/b3-a1` to `task/b3-a6` | Parent | Strictly serialized | state root exists, plan snapshot exists, B2 precondition recorded, integration branch and initial worktrees created |
| Phase B: Native State Contract and Draft Projection | `task/b3-b1` | `WS-A` | Serialized | `gate/b3-lane-a` |
| Phase C: Parent Merge and State Freeze | `task/b3-c1`, `task/b3-c2` | Parent | Strictly serialized | `state-contract-freeze.md` published |
| Phase D: Selection Ownership plus Early Boundary Tests | `task/b3-d1`, `task/b3-d2` | `WS-B`, `WS-E1` | Parallel | `gate/b3-lane-b`, `gate/b3-lane-e1` |
| Phase E: Parent Merge and Selection Freeze | `task/b3-e1`, `task/b3-e2` | Parent | Strictly serialized | `selection-freeze.md` published |
| Phase F: State-Native Artifact Publishing | `task/b3-f1` | `WS-C` | Serialized | `gate/b3-lane-c` |
| Phase G: Parent Merge and Publisher Freeze | `task/b3-g1`, `task/b3-g2` | Parent | Strictly serialized | `publisher-freeze.md` published |
| Phase H: Compatibility Boundary Cleanup | `task/b3-h1` | `WS-D` | Serialized | `gate/b3-lane-d` |
| Phase I: Parent Merge and Compatibility Freeze | `task/b3-i1`, `task/b3-i2` | Parent | Strictly serialized | `compatibility-freeze.md` published |
| Phase J: Parity and Compatibility Matrix | `task/b3-j1` | `WS-E2` | Serialized | `gate/b3-lane-e2` |
| Phase K: Parent Final Regression and Acceptance | `task/b3-k1` to `task/b3-k4` | Parent | Strictly serialized | `gate/b3-targeted-regressions`, `gate/b3-acceptance`, `gate/b3-complete` |

### Launch Order

1. `task/b3-a1-read-authority`
2. `task/b3-a2-verify-b2-precondition`
3. `task/b3-a3-snapshot-active-plan`
4. `task/b3-a4-freeze-invariants`
5. `task/b3-a5-create-state-root`
6. `task/b3-a6-create-integration-branch-and-worktrees`
7. Dispatch `WS-A`
8. Merge `WS-A`
9. Publish `state-contract-freeze.md`
10. Dispatch `WS-B`
11. Dispatch `WS-E1`
12. Merge `WS-E1` and `WS-B` after gate verification
13. Publish `selection-freeze.md`
14. Dispatch `WS-C`
15. Merge `WS-C`
16. Publish `publisher-freeze.md`
17. Dispatch `WS-D`
18. Merge `WS-D`
19. Publish `compatibility-freeze.md`
20. Dispatch `WS-E2`
21. Merge `WS-E2`
22. Run parent-only final regression and acceptance sweep

### Merge Order

Merge ordering is constrained as follows:

1. `WS-A` must merge first.
2. `WS-B` and `WS-E1` may merge in either order after `WS-A`, but
   `selection-freeze.md` is published only after `WS-B` merges.
3. `WS-C` merges after `WS-B`.
4. `WS-D` merges after `WS-C`.
5. `WS-E2` merges last.
6. Final regression and acceptance are parent-only on the integrated tree.

### Phase Tasks

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/b3-a1-read-authority` | Re-read root `PLAN.md`, this `ORCH_PLAN.md`, and the historical orchestration reference | Parent | Parent can restate scope, freezes, and serialized surfaces exactly |
| `task/b3-a2-verify-b2-precondition` | Verify B2 parity is already green on `main` or the integration tree is proven equivalent | Parent | Precondition evidence recorded in `state.json` |
| `task/b3-a3-snapshot-active-plan` | Copy the active root `PLAN.md` into the state root and record its hash | Parent | `inputs/PLAN.session.md` and hash recorded |
| `task/b3-a4-freeze-invariants` | Freeze lane ownership, serialized surfaces, gate commands, and blocker protocol | Parent | `invariants.md` written |
| `task/b3-a5-create-state-root` | Create the repo-local orchestration state root and sentinel layout | Parent | State root initialized |
| `task/b3-a6-create-integration-branch-and-worktrees` | Create the integration branch from the kickoff branch context and create worker worktrees | Parent | Branch and worktrees created |
| `task/b3-b1-native-state-contract-and-draft-projection` | Land the native state contract, native draft projector, graph-owned merge update, and any trigger-only runner follow-up | `WS-A` | `gate/b3-lane-a` |
| `task/b3-c1-merge-ws-a` | Merge `WS-A` and rerun its gate in the integration tree | Parent | `WS-A` merged |
| `task/b3-c2-publish-state-contract-freeze` | Publish the exact native field names, projector signature, and graph-owned merge contract | Parent | `state-contract-freeze.md` written |
| `task/b3-d1-selection-owner-canonicalization` | Make `select_best_draft_node(...)` the sole ranking owner and remove reporting rerank behavior | `WS-B` | `gate/b3-lane-b` |
| `task/b3-d2-early-native-state-boundary-tests` | Land the early native-state and compatibility-boundary assertions against the frozen state contract | `WS-E1` | `gate/b3-lane-e1` |
| `task/b3-e1-merge-b-and-e1` | Merge `WS-B` and `WS-E1`, rerunning their gates in the integration tree | Parent | `WS-B` and `WS-E1` merged |
| `task/b3-e2-publish-selection-freeze` | Publish the exact selection-id semantics and no-rerank rule | Parent | `selection-freeze.md` written |
| `task/b3-f1-state-native-artifact-publishing` | Replace success-path summary round-tripping with the state-native publisher path | `WS-C` | `gate/b3-lane-c` |
| `task/b3-g1-merge-ws-c` | Merge `WS-C` and rerun its gate | Parent | `WS-C` merged |
| `task/b3-g2-publish-publisher-freeze` | Publish the exact publisher inputs, outputs, and one-way summary projection rules | Parent | `publisher-freeze.md` written |
| `task/b3-h1-compatibility-boundary-cleanup` | Lock the sanctioned summary-read seams and preserve recovery/readability behavior | `WS-D` | `gate/b3-lane-d` |
| `task/b3-i1-merge-ws-d` | Merge `WS-D` and rerun its gate | Parent | `WS-D` merged |
| `task/b3-i2-publish-compatibility-freeze` | Publish the exact allowed summary-read call sites and recovery contract | Parent | `compatibility-freeze.md` written |
| `task/b3-j1-parity-and-compatibility-matrix` | Land the full B3 parity, readability, CLI, and deleted-bridge-path proof matrix | `WS-E2` | `gate/b3-lane-e2` |
| `task/b3-k1-merge-ws-e2` | Merge `WS-E2` and rerun its gate | Parent | `WS-E2` merged |
| `task/b3-k2-targeted-regression-sweep` | Run the full `PLAN.md` validation command set on the integrated tree | Parent | `gate/b3-targeted-regressions` |
| `task/b3-k3-acceptance-checklist-review` | Verify the integrated tree against the B3 checklist, parity matrix, and rollback triggers | Parent | `gate/b3-acceptance` |
| `task/b3-k4-final-verdict` | Record green or blocked milestone verdict | Parent | `gate/b3-complete` |

## Orchestration State and Source of Truth

The parent maintains one repo-local orchestration state root for the full run:

- `.runs/b3-graph-native-state-selection-artifacts-orch/`

Required layout:

- `.runs/b3-graph-native-state-selection-artifacts-orch/queue.md`
- `.runs/b3-graph-native-state-selection-artifacts-orch/state.json`
- `.runs/b3-graph-native-state-selection-artifacts-orch/invariants.md`
- `.runs/b3-graph-native-state-selection-artifacts-orch/state-contract-freeze.md`
- `.runs/b3-graph-native-state-selection-artifacts-orch/selection-freeze.md`
- `.runs/b3-graph-native-state-selection-artifacts-orch/publisher-freeze.md`
- `.runs/b3-graph-native-state-selection-artifacts-orch/compatibility-freeze.md`
- `.runs/b3-graph-native-state-selection-artifacts-orch/session.log`
- `.runs/b3-graph-native-state-selection-artifacts-orch/handoffs/`
- `.runs/b3-graph-native-state-selection-artifacts-orch/gates/`
- `.runs/b3-graph-native-state-selection-artifacts-orch/logs/`
- `.runs/b3-graph-native-state-selection-artifacts-orch/sentinels/`
- `.runs/b3-graph-native-state-selection-artifacts-orch/inputs/`
- `.runs/b3-graph-native-state-selection-artifacts-orch/acceptance/`

### File Roles

- `queue.md`
  - Canonical task table with one row per `task/b3-*`
  - Tracks owner, state, gate, reopen reason, and merge status
- `state.json`
  - Current phase, active lanes, branch names, plan hash, B2-precondition
    status, blockers, merge state, and final verdict
- `invariants.md`
  - Frozen scope, ownership boundaries, serialized surfaces, commands, and gate
    definitions
- `state-contract-freeze.md`
  - Parent-accepted freeze after `WS-A`
  - Freezes the Phase 1 names from `PLAN.md`:
    - `HarnessState.drafts`
    - `current_draft_id`
    - `best_draft_id`
    - `selected_draft_id`
    - `issue_history`
    - `open_issue_ids`
    - `topic_ledger`
    - `run_verdict`
    - `content_verdict`
    - `validator_verdict`
    - `policy_verdict`
    - `analysis_review_status`
    - `recommendation_reviews`
    - `final_answer`
    - `bounded_review_summary`
    - `bounded_attestation_input`
    - `stage_history`
    - `validator_rounds`
    - `policy_checks`
    - `changed_files`
    - `validator_summary`
    - `analysis_review_coverage`
    - `artifact_index`
    - `summary_payload`
    - `bridge_boundary_version`
    - `drafts_from_stage_history_v1(...)`
- `selection-freeze.md`
  - Parent-accepted freeze after `WS-B`
  - Freezes:
    - `select_best_draft_node(...)` as the sole graph-path ranking owner
    - the rule that `reporting.py` may look up selected ids but may not rerank
    - deterministic selection-id updates in native state
- `publisher-freeze.md`
  - Parent-accepted freeze after `WS-C`
  - Freezes:
    - `publish_state_artifacts_v1(state)` as the canonical graph-owned publish
      path
    - the rule that `summary_projection_v1(...)` is final one-way projection
      only
    - the rule that `write_artifacts_node(...)` updates `artifact_index` and
      `summary_payload` in place with no success-path rehydration
    - stable external artifact semantics for `summary.json`, `REPORT.md`,
      `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*`
- `compatibility-freeze.md`
  - Parent-accepted freeze after `WS-D`
  - Freezes:
    - the only sanctioned `summary_read_adapter_v1(...)` and
      `state_from_summary(...)` call sites
    - the rule that graph-owned success paths never stamp
      `bridge_boundary_version`
    - restart-at-run-boundary readability as the minimum recovery contract
- `session.log`
  - Parent-only sequential log of dispatches, readiness, blockers, merges,
    reopen events, freeze publications, and final decisions
- `inputs/PLAN.session.md`
  - Immutable kickoff snapshot of the active root `PLAN.md`
  - This is a run artifact snapshot, not the authored source of truth
- `inputs/PLAN.session.sha256`
  - Hash of the kickoff `PLAN.md` snapshot
- `handoffs/task-b3-*.md`
  - Narrow worker packets and parent-accepted return summaries
- `gates/*.md`
  - Parent gate results with exact commands and verdicts
- `acceptance/`
  - Final command outputs, parity observations, rollback notes, and acceptance
    evidence used during milestone review

### Git-Tracked Authored Sources vs Run Artifacts

Git-tracked authored sources for this milestone include:

- root `PLAN.md`
- root `ORCH_PLAN.md`
- `anvil/harness/state.py`
- `anvil/harness/selection.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/select_best_draft.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/runner.py` only if the touch rule in `PLAN.md` triggers
- targeted test expansions under `tests/`

Run artifacts that must not be committed:

- everything under `.runs/b3-graph-native-state-selection-artifacts-orch/`
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

- `.runs/b3-graph-native-state-selection-artifacts-orch/sentinels/`

Required sentinel names:

- `task-b3-*.dispatched`
- `task-b3-*.ready`
- `task-b3-*.blocked`
- `task-b3-*.merged`
- `task-b3-*.failed-gate`

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
- Kickoff branch context: `codex/b2-graph-owned-analysis-review-parity`
- Integration branch: `codex/b3-graph-native-state-selection-artifacts`
- Owner: Parent only

Sibling worktree root:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/`

Lane worktrees:

- `WS-A`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-a-native-state-contract`
  - Branch: `codex/b3-ws-a-native-state-contract`
- `WS-B`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-b-selection-owner`
  - Branch: `codex/b3-ws-b-selection-owner`
- `WS-C`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-c-state-native-publisher`
  - Branch: `codex/b3-ws-c-state-native-publisher`
- `WS-D`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-d-compat-boundary`
  - Branch: `codex/b3-ws-d-compat-boundary`
- `WS-E1`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-e1-native-state-tests`
  - Branch: `codex/b3-ws-e1-native-state-tests`
- `WS-E2`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-e2-parity-matrix`
  - Branch: `codex/b3-ws-e2-parity-matrix`

### Worktree Creation Commands

Create the integration branch from the current checked-out kickoff branch
context after snapshotting the active `PLAN.md`:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge switch -c \
  codex/b3-graph-native-state-selection-artifacts

mkdir -p \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-a-native-state-contract \
  -b codex/b3-ws-a-native-state-contract \
  codex/b3-graph-native-state-selection-artifacts
```

Create dependent worktrees only when the upstream freeze exists:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-b-selection-owner \
  -b codex/b3-ws-b-selection-owner \
  codex/b3-graph-native-state-selection-artifacts

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-e1-native-state-tests \
  -b codex/b3-ws-e1-native-state-tests \
  codex/b3-graph-native-state-selection-artifacts

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-c-state-native-publisher \
  -b codex/b3-ws-c-state-native-publisher \
  codex/b3-graph-native-state-selection-artifacts

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-d-compat-boundary \
  -b codex/b3-ws-d-compat-boundary \
  codex/b3-graph-native-state-selection-artifacts

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/b3-graph-native-state-selection-artifacts/ws-e2-parity-matrix \
  -b codex/b3-ws-e2-parity-matrix \
  codex/b3-graph-native-state-selection-artifacts
```

### Worktree Rules

- The parent is the only integrator.
- Workers never merge peer branches.
- Workers never rebase peer changes into their own lane unless the parent
  instructs it.
- Parent resolves every merge or rebase in the integration worktree only.
- `anvil/harness/state.py` is serialized across lanes:
  - `WS-A` owns the initial native state completion
  - `WS-B` owns any selection-id follow-up
  - `WS-D` owns any final compatibility annotations or cleanup
- `anvil/harness/reporting.py` is serialized across lanes:
  - `WS-B` owns the selection-owner cleanup
  - `WS-C` owns the state-native publisher cutover
  - `WS-D` may only touch it if publisher freeze proves a sanctioned
    compatibility follow-up is still required
- Conditional `runner.py` ownership stays with `WS-A` unless the parent reopens
  it after `WS-C` or `WS-D` proves the touch rule actually triggered.
- If a lane needs a peer-owned change, it raises a blocker instead of editing
  that file.
- `WS-B` and `WS-E1` do not launch until `state-contract-freeze.md` exists.
- `WS-C` does not actively code until `selection-freeze.md` exists.
- `WS-D` does not launch until `publisher-freeze.md` exists.
- `WS-E2` does not launch until `compatibility-freeze.md` exists.

## Blocker, Freeze-Change, and Conflict Protocols

### Blocker Protocol

A worker must mark `.blocked` and stop when any of these occur:

- it needs a peer-owned file change
- it needs to touch `anvil/harness/state.py` or `anvil/harness/reporting.py`
  outside the currently assigned lane
- it cannot satisfy its lane gate without touching a frozen surface
- the parent-owned freeze document for its dependency does not exist
- the root `PLAN.md` changed and the parent declared plan drift
- a required change would widen artifact contract semantics
- a required change would introduce a second state truth, second ranking owner,
  or second summary boundary
- a required change would force `runner.py` edits without satisfying the touch
  rule in `PLAN.md`

Required blocker return:

- exact file or interface requested
- exact reason
- exact minimal parent decision needed
- exact command or failing assertion demonstrating the blocker, if relevant

### Freeze-Change Protocol

For this milestone, freeze-sensitive surfaces include:

- every native field name listed in `state-contract-freeze.md`
- `drafts_from_stage_history_v1(...)`
- `extract_drafts_from_summary(...)` as compatibility-only
- `current_draft_id`
- `best_draft_id`
- `selected_draft_id`
- `select_best_draft_node(...)` as sole ranking owner
- `publish_state_artifacts_v1(state)`
- `summary_projection_v1(...)`
- `summary_read_adapter_v1(...)`
- `state_from_summary(...)`
- `artifact_index`
- `summary_payload`
- `bridge_boundary_version`
- any approved graph-trace metadata keys only if already frozen by the parent

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

- Example: `WS-C` needs publisher inputs that do not match
  `selection-freeze.md`.
- Resolution: parent compares against `PLAN.md` and the relevant freeze file,
  then reopens the affected lane.
- Workers do not invent fallback names or shadow adapters.

Conflict type: topology drift

- Example: a lane tries to restore success-path summary rehydration to make a
  test pass.
- Resolution: stop immediately, mark blocked, and return the smallest drift
  summary.
- Parent either rejects the drift or replans explicitly.

Conflict type: compatibility drift

- Example: `WS-D` proves old summaries are unreadable without a runner-local
  compatibility fix.
- Resolution: parent applies the `runner.py` touch rule and either reopens
  `WS-A` or issues a new parent-approved `WS-D` packet.
- No worker self-authorizes a runner spillover.

Conflict type: parity drift

- Example: `WS-E2` finds `summary.json`, `REPORT.md`, or final artifact payload
  drift outside approved metadata.
- Resolution: parent treats this as a rollback trigger, reopens the offending
  lane, and keeps `legacy_bridge` as the safe mode.

## Workstream Plan

### WS-A: Native State Contract and Draft Projection

Task ID:

- `task/b3-b1-native-state-contract-and-draft-projection`

Owner:

- Worker `WS-A`
- Parent controls dispatch, state freeze, integration, and acceptance

Owned files:

- `anvil/harness/state.py`
- `anvil/harness/selection.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/runner.py` only if the `PLAN.md` touch rule triggers
- `tests/test_harness_selection.py`
- `tests/test_harness_analysis_review_graph.py`

Files explicitly not owned by `WS-A`:

- `anvil/harness/nodes/select_best_draft.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/subgraphs/_bridge.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_run_focus_gate_acceptance.py`

Required changes:

- expand `HarnessState` so every graph-owned downstream publish/report field
  named in `PLAN.md` is explicit
- add `drafts_from_stage_history_v1(...)` in `anvil/harness/selection.py`
- refactor `extract_drafts_from_summary(...)` into a compatibility wrapper
  around the native projector
- update graph-owned merge logic in
  `anvil/harness/subgraphs/analysis_review_v1.py` to build drafts from native
  state, not a synthetic summary wrapper
- stop stamping `bridge_boundary_version` on graph-owned success paths
- touch `runner.py` only if the `PLAN.md` touch rule is proven necessary
- land the Phase 1 test coverage for native draft projection and graph-owned
  state population

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_selection.py \
  tests/test_harness_analysis_review_graph.py
```

`gate/b3-lane-a` is green only when all of these are true:

- the lane command is green
- graph-owned draft projection no longer depends on
  `extract_drafts_from_summary(...)`
- graph-owned success-path state carries the downstream publish/report fields
  frozen in `state-contract-freeze.md`
- graph-owned success paths do not stamp `bridge_boundary_version`
- `runner.py` is untouched unless the touch rule was explicitly satisfied
- no code outside the owned files changed

### WS-B: Selection Owner Canonicalization

Task ID:

- `task/b3-d1-selection-owner-canonicalization`

Owner:

- Worker `WS-B`
- Parent controls dispatch, selection freeze, integration, and acceptance

Owned files:

- `anvil/harness/nodes/select_best_draft.py`
- `anvil/harness/reporting.py`
- `anvil/harness/state.py`
- `tests/test_harness_reporting.py`

Files explicitly not owned by `WS-B`:

- `anvil/harness/selection.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/report.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/runner.py`
- `tests/test_harness_selection.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`

Required changes:

- keep `select_best_draft_node(...)` as the only graph-path ranking owner
- ensure native state entering the node has deterministic `drafts` and
  `current_draft_id`, but does not pretend final ranking is already resolved
- remove graph-owned success-path reranking from `anvil/harness/reporting.py`
- preserve compatibility-only computation of missing selection ids when reading
  historical summaries
- align reporting lookups and emitted artifact choice with
  `selected_draft_id` and `best_draft_id` already frozen in native state

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_reporting.py
```

`gate/b3-lane-b` is green only when all of these are true:

- the lane command is green
- `select_best_draft_node(...)` is the only graph-path ranking owner
- `anvil/harness/reporting.py` no longer makes a second winner decision on
  graph-owned success execution
- selection ids are deterministic and match the frozen names
- no code outside the owned files changed

### WS-C: State-Native Artifact Publishing

Task ID:

- `task/b3-f1-state-native-artifact-publishing`

Owner:

- Worker `WS-C`
- Parent controls dispatch, publisher freeze, integration, and acceptance

Owned files:

- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`

Files explicitly not owned by `WS-C`:

- `anvil/harness/state.py`
- `anvil/harness/selection.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/select_best_draft.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/runner.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_run_focus_gate_acceptance.py`

Required changes:

- add `publish_state_artifacts_v1(state)` as the canonical graph-owned publish
  path
- move graph-owned success-path deliverable selection, artifact writing, and
  artifact-index population under the native publisher
- keep `summary_projection_v1(...)` as the final one-way projection used to
  materialize `summary.json` and feed `render_report(...)`
- update `write_artifacts_node(...)` to update native state in place with
  `artifact_index` and `summary_payload`
- delete the graph-owned success-path round-trip through
  `summary_read_adapter_v1(...)`
- keep CLI-visible artifact and report surfaces stable

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_cli_command.py \
  tests/test_harness_standalone_cli.py

poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

`gate/b3-lane-c` is green only when all of these are true:

- every lane command is green
- graph-owned success execution publishes deliverables, `summary.json`, and
  `REPORT.md` from native state
- `write_artifacts_node(...)` no longer rehydrates state from summary on the
  success path
- `summary_payload` is now a final projected cache, not an input dependency
- no code outside the owned files changed

### WS-D: Compatibility Boundary Cleanup

Task ID:

- `task/b3-h1-compatibility-boundary-cleanup`

Owner:

- Worker `WS-D`
- Parent controls dispatch, compatibility freeze, integration, and acceptance

Owned files:

- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/state.py`
- `anvil/harness/reporting.py` only if `publisher-freeze.md` still requires an
  explicit compatibility follow-up
- `anvil/harness/nodes/write_artifacts.py` only if a sanctioned boundary cleanup
  remains after `WS-C`
- `anvil/harness/runner.py` only if the parent explicitly confirms the touch
  rule triggered
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_runner.py`

Files explicitly not owned by `WS-D`:

- `anvil/harness/selection.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/nodes/select_best_draft.py`
- `anvil/harness/report.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_run_focus_gate_acceptance.py`

Required changes:

- enumerate and preserve only the sanctioned summary-read adapter call sites
- remove any remaining graph-owned success-path fallback branches that treat
  summary as general execution state
- prove seeded summary data does not override canonical native state on
  graph-owned success execution
- preserve historical summary readability
- preserve restart-at-run-boundary readability
- keep legacy bridge behavior boring and explicit

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_runner.py
```

`gate/b3-lane-d` is green only when all of these are true:

- the lane command is green
- only sanctioned legacy or historical summary-read seams remain
- graph-owned success execution is free of summary rehydration
- historical summary readability still works
- restart-at-run-boundary readability remains supported
- no code outside the owned files changed

### WS-E1: Early Native-State and Boundary Tests

Task ID:

- `task/b3-d2-early-native-state-boundary-tests`

Owner:

- Worker `WS-E1`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `tests/test_harness_state_boundaries.py`

Files explicitly not owned by `WS-E1`:

- all `anvil/harness/*` implementation files
- every other `tests/` file

Required changes:

- assert graph-owned success paths never call `summary_read_adapter_v1(...)`
- assert graph-owned success paths never stamp `bridge_boundary_version`
- assert historical summaries still adapt cleanly after the Phase 1 contract
  freeze
- stay aligned with `state-contract-freeze.md` and do not assume Phase 3 or
  Phase 4 publisher details early

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_state_boundaries.py
```

`gate/b3-lane-e1` is green only when all of these are true:

- the lane command is green
- assertions are grounded in `state-contract-freeze.md`
- no implementation files changed
- no future-lane publisher or compatibility behavior is guessed into the tests

### WS-E2: Parity and Compatibility Matrix

Task ID:

- `task/b3-j1-parity-and-compatibility-matrix`

Owner:

- Worker `WS-E2`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_run_focus_gate_acceptance.py`

Files explicitly not owned by `WS-E2`:

- all `anvil/harness/*` implementation files
- `tests/test_harness_selection.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_analysis_review_graph.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`

Required changes:

- prove the B3 parity matrix rows described in `PLAN.md`
- keep CLI and acceptance surfaces stable across `legacy_bridge` and
  `graph_owned`
- keep focus-gate and example-strategy wiring surfaces honest after native
  state, selection, and publishing move fully into state
- avoid widening acceptance semantics outside the artifact/report stability
  allowed by `PLAN.md`

Lane commands:

```bash
poetry run pytest -q \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_run_focus_gate_acceptance.py
```

`gate/b3-lane-e2` is green only when all of these are true:

- the lane command is green
- parity assertions align to the exact B3 matrix in `PLAN.md`
- no implementation files changed
- no artifact or report contract widening was introduced to make a parity row
  pass

## Context-Control Rules

### Parent Live Context Policy

Parent keeps only a narrow live set of artifacts in active context:

- `PLAN.md`
- `ORCH_PLAN.md`
- `invariants.md`
- the active freeze document
- `queue.md`
- `state.json`
- the active lane handoff packet
- the active lane's narrow diff summary
- the active gate result being reviewed

Parent does not keep full worker transcripts in live context once a narrow
handoff has been accepted.

### Worker Packet Policy

Each worker packet contains only:

- task ID
- owned file list
- relevant `PLAN.md` excerpt for that lane
- exact gate commands
- frozen contract or naming decisions already made by the parent
- forbidden surfaces list
- blocker protocol

Worker packets do not include:

- unrelated repo summaries
- other lanes' transcripts
- full milestone prose outside the relevant excerpt

### Worker Return Policy

Each worker returns only:

- changed files
- commands run
- pass or fail status
- exact blocker, if any

Workers do not return:

- long freeform transcripts
- speculative redesign notes
- peer-lane reviews

### Parent Review Policy

Parent reviews:

- worker summary
- narrow diff in owned files
- lane gate output

Parent does not review:

- full worker reasoning transcripts
- broad repo-wide diffs for narrow lanes
- peer lane internals unless a blocker requires it

## Repo Tests and Acceptance

### 1. Targeted Regression Sweep

Run on the integrated tree.

Required commands:

```bash
poetry run pytest -q \
  tests/test_harness_selection.py \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_reporting.py \
  tests/test_harness_analysis_review_graph.py \
  tests/test_harness_runner.py \
  tests/test_harness_cli_command.py \
  tests/test_harness_standalone_cli.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_run_focus_gate_acceptance.py

poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

`gate/b3-targeted-regressions` is green only when every command above passes.

### 2. Acceptance Checklist

The integrated tree is not done until all of these are true:

- `HarnessState` carries all graph-owned downstream publish/report fields named
  in `PLAN.md`
- graph-owned draft projection no longer depends on a synthetic summary wrapper
- `select_best_draft_node(...)` is the only graph-path ranking owner
- graph-owned success-path artifact publication is state-native
- graph-owned success path never calls `summary_read_adapter_v1(...)`
- graph-owned success path never calls `state_from_summary(...)`
- graph-owned success path never stamps `bridge_boundary_version`
- `summary_projection_v1(...)` remains the sole summary write boundary
- historical summary readability still works
- restart-at-run-boundary readability remains supported
- full B3 parity matrix is green
- no parity drift appears outside approved graph-trace metadata

### 3. Rollback Triggers

Any of these findings blocks completion and reopens the owning lane:

- mismatch in final artifact kind or emitted payload between `legacy_bridge`
  and `graph_owned`
- mismatch in selected or best draft ids between graph-owned state and emitted
  artifacts
- any graph-owned success path calling `summary_read_adapter_v1(...)`
- any graph-owned success path calling `state_from_summary(...)`
- any graph-owned success path stamping `bridge_boundary_version`
- any historical summary that stops adapting cleanly

Rollback action:

- rerun with `--analysis-review-execution-mode legacy_bridge`
- keep B2 compatibility behavior as the safe operational fallback until the B3
  drift is fixed

### 4. Parent Acceptance Review

The parent records `gate/b3-acceptance` only after:

- the targeted regression sweep is green
- each freeze doc still matches the integrated code
- the parity matrix and rollback triggers were reviewed explicitly
- the deleted bridge-only path remains dead by test coverage:
  `write_artifacts_node -> summary_read_adapter_v1(...)` on the graph-owned
  success path

The parent records `gate/b3-complete` only when B3 satisfies the done criteria
from `PLAN.md` with no open blockers.

## Assumptions

- B2 parity will have landed on `main` before B3 execution actually starts.
- The current checked-out branch context,
  `codex/b2-graph-owned-analysis-review-parity`, is the correct kickoff branch
  context for creating the B3 integration branch after the precondition is
  verified.
- The parent can create sibling worktrees under
  `/Users/spensermcconnell/__Active_Code/forge.worktrees/`.
- No artifact-contract version bump is required to satisfy B3.
- `anvil/harness/runner.py` probably stays untouched, but the orchestration
  keeps a guarded path open if the `PLAN.md` touch rule proves otherwise.
