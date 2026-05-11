# ORCH_PLAN: Repo Surface Cleanup Pass

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Base branch: `feat/bounded-work-redesign`  
Primary source of truth: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`

This orchestration plan replaces the stale bounded-work `ORCH_PLAN.md` with the
branch-accurate execution plan for the repo-surface cleanup pass.

What this branch must deliver:

- rewrite the canonical docs surfaces
- add `docs/contributing.md`
- add `docs/project_management/README.md` plus the required directory scaffold
- move root historical and future markdown files under
  `docs/project_management/`
- update `tests/test_harness_analysis_contract.py` for the moved notes path
- add `tests/test_docs_surface.py`
- move `PLAN.md` only in the final cleanup slice

This is not a harness/runtime behavior change. The parent agent owns planning,
sequencing, worker packets, integration, conflict resolution, gate reruns, and
final acceptance. The parent is the only integrator.

## Orchestration Runtime Policy

Parent runtime policy:

- Parent re-reads `PLAN.md` at every phase boundary.
- Parent freezes lane ownership, authority rules, and verification commands
  before dispatch.
- Parent is the only agent allowed to merge, rebase for integration, resolve
  conflicts, or widen scope.
- Parent reruns every lane gate in the integration worktree before accepting a
  merge.
- Parent keeps the critical path local for moved-path correctness, audit
  reruns, and final `PLAN.md` relocation.

Worker runtime policy:

- Only `WS-A` and `WS-B` run as worker lanes.
- Workers execute only their owned files, frozen invariants, and lane commands.
- Workers do not move root historical files, touch tests, or change runtime
  code.

Concurrency policy:

- Maximum concurrent worker lanes: `2`
- Parallel window: `WS-A` and `WS-B` only
- `WS-C`, `WS-D`, and `WS-E` remain parent-local because they are path-coupled,
  depend on active root `PLAN.md` authority, and require immediate audit reruns
  in the integration worktree.

## Hard Guards

1. If this file and `PLAN.md` disagree, follow `PLAN.md`.
2. Scope is limited to repo-surface cleanup. No runtime behavior changes under
   `anvil/`.
3. `README.md` is the canonical front door and must describe current reality
   only.
4. `docs/roadmap.md` is the only canonical roadmap body.
5. root `roadmap.md` must be a short pointer only and must not carry roadmap
   body prose.
6. `docs/contributing.md` is the canonical contributor entry point once added.
7. `docs/project_management/README.md` must explain active plan vs history vs
   future and must not become a second front door.
8. Historical docs may receive only light framing or path fixes; no substantive
   historical rewrites.
9. Do not touch `docs/project_management/adrs/`.
10. Do not clean up `archived/`.
11. Do not rename packages, modules, or the branch.
12. Do not introduce symlinks, redirect machinery, generated docs tooling, or
    path shims.
13. Root `PLAN.md` remains authoritative and stays in place until the final
    relocation phase.
14. The only code/test changes in scope are:
    - `tests/test_harness_analysis_contract.py`
    - `tests/test_docs_surface.py` (new)
15. Lane sequencing is locked:
    - `WS-A` and `WS-B` in parallel
    - `WS-C` after both are merged
    - `WS-D` after `WS-C`
    - `WS-E` last
16. If any lane needs a runtime change, harness contract change, ADR rewrite,
    or `archived/` cleanup to pass, stop and reopen planning.
17. The parent is the only integrator.

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit Gate |
|---|---|---|---|---|
| Phase A: Kickoff and Freeze | `task/repo-a1` to `task/repo-a6` | Parent | Strictly serialized | invariants frozen, snapshots captured, state root initialized, worker packets dispatched |
| Phase B: Parallel Worker Lanes | `task/repo-b1`, `task/repo-b2` | `WS-A`, `WS-B` under parent control | Parallel | `gate/canonical-docs`, `gate/pm-scaffold` |
| Phase C: Parent Local History/Future Moves | `task/repo-c1` | Parent | Strictly serialized | `gate/history-moves` |
| Phase D: Parent Local Regression Protection | `task/repo-d1` | Parent | Strictly serialized | `gate/docs-regression` |
| Phase E: Parent Local Final Plan Relocation | `task/repo-e1`, `task/repo-e2` | Parent | Strictly serialized | `gate/final-root-cleanup`, `gate/repo-surface-complete` |

### Kickoff Tasks

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/repo-a1-read-authority` | Re-read `PLAN.md`, current `ORCH_PLAN.md`, `README.md`, `docs/roadmap.md`, `AGENTS.md`, and the path-coupled test section | Parent | Parent can restate scope, authority rules, and lane order exactly |
| `task/repo-a2-freeze-invariants` | Freeze hard guards, file ownership, lane commands, merge order, and blocker protocol | Parent | invariants recorded |
| `task/repo-a3-capture-snapshots` | Capture `PLAN.md` and the stale pre-replacement `ORCH_PLAN.md` into the orchestration state root | Parent | authoritative inputs preserved |
| `task/repo-a4-create-state-root` | Create the repo-local orchestration state root and initialize queue/state/sentinel layout | Parent | state root exists |
| `task/repo-a5-create-worktrees` | Create worker worktrees and branches for `WS-A` and `WS-B` | Parent | worker worktrees exist and are clean |
| `task/repo-a6-dispatch-workers` | Write and issue narrow worker packets for `WS-A` and `WS-B` | Parent | both workers dispatched |

### Merge and Verification Tasks

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/repo-b1-canonical-docs` | Canonical docs rewrite lane | `WS-A` | `gate/canonical-docs` |
| `task/repo-b2-pm-scaffold` | Project-management scaffold lane | `WS-B` | `gate/pm-scaffold` |
| `task/repo-b3-verify-merge-ws-b` | Parent reruns `WS-B` gate in integration worktree and accepts/merges | Parent | `WS-B` merged |
| `task/repo-b4-verify-merge-ws-a` | Parent reruns `WS-A` gate in integration worktree and accepts/merges | Parent | `WS-A` merged |
| `task/repo-c1-history-and-future-moves` | Parent performs moved-file slice and verifies root/path state | Parent | `gate/history-moves` |
| `task/repo-d1-regression-protection` | Parent updates tests, adds docs-surface regression, and reruns audits | Parent | `gate/docs-regression` |
| `task/repo-e1-final-plan-relocation` | Parent moves `PLAN.md` last and reruns validations | Parent | `gate/final-root-cleanup` |
| `task/repo-e2-record-final-verdict` | Parent records green or blocked completion verdict | Parent | `gate/repo-surface-complete` |

### Launch Order

1. `task/repo-a1-read-authority`
2. `task/repo-a2-freeze-invariants`
3. `task/repo-a3-capture-snapshots`
4. `task/repo-a4-create-state-root`
5. `task/repo-a5-create-worktrees`
6. `task/repo-a6-dispatch-workers`
7. Parent reruns `WS-B` gate in the integration worktree, then merges `WS-B`
8. Parent reruns `WS-A` gate in the integration worktree, then merges `WS-A`
9. Parent runs `task/repo-c1-history-and-future-moves`
10. Parent runs `task/repo-d1-regression-protection`
11. Parent runs `task/repo-e1-final-plan-relocation`
12. Parent runs `task/repo-e2-record-final-verdict`

### Merge Order

The merge order is fixed:

1. `WS-B` project-management scaffold
2. `WS-A` canonical docs rewrite
3. parent-local `WS-C` history/future moves
4. parent-local `WS-D` regression protection
5. parent-local `WS-E` final `PLAN.md` relocation

For `WS-A` and `WS-B`, merge acceptance requires:

- worker reports ready
- parent reruns the lane gate in the integration worktree
- parent confirms owned-file boundaries were respected
- parent merges only after the rerun passes cleanly

## Orchestration State and Source of Truth

State root:

- `.runs/repo-surface-cleanup-orch/`

Required layout:

- `.runs/repo-surface-cleanup-orch/queue.md`
- `.runs/repo-surface-cleanup-orch/state.json`
- `.runs/repo-surface-cleanup-orch/invariants.md`
- `.runs/repo-surface-cleanup-orch/session.log`
- `.runs/repo-surface-cleanup-orch/inputs/PLAN.snapshot.md`
- `.runs/repo-surface-cleanup-orch/inputs/ORCH_PLAN.active.md`
- `.runs/repo-surface-cleanup-orch/inputs/ORCH_PLAN.stale.md`
- `.runs/repo-surface-cleanup-orch/handoffs/`
- `.runs/repo-surface-cleanup-orch/gates/`
- `.runs/repo-surface-cleanup-orch/sentinels/`
- `.runs/repo-surface-cleanup-orch/acceptance/`

### File Roles

- `queue.md`
  - canonical task table for `task/repo-*`
  - tracks owner, state, gate, blocker status, and merge status
- `state.json`
  - current phase, active lanes, worktree paths, branch names, blockers, and
    final verdict
- `invariants.md`
  - frozen hard guards, ownership boundaries, merge order, and exact gate
    commands
- `session.log`
  - parent-only sequential log of dispatches, ready notices, gate reruns,
    merges, blockers, and final decisions
- `inputs/PLAN.snapshot.md`
  - frozen worker/reference copy of the active root `PLAN.md`
- `inputs/ORCH_PLAN.active.md`
  - this orchestration plan as the continuing execution guide after root
    `ORCH_PLAN.md` leaves the root surface
- `inputs/ORCH_PLAN.stale.md`
  - preserved pre-replacement stale orchestration content for later historical
    archiving
- `handoffs/task-repo-*.md`
  - narrow worker packet plus parent-accepted return summary for `WS-A` and
    `WS-B`
- `gates/*.md`
  - parent gate results with exact commands, outputs, and green/blocked verdicts
- `acceptance/`
  - final command outputs, audit results, moved-file verification notes, and
    completion checklist evidence

### Source-of-Truth Order

1. root `PLAN.md` in the integration worktree until `WS-E`
2. `inputs/PLAN.snapshot.md` for worker packets and frozen acceptance criteria
3. `inputs/ORCH_PLAN.active.md` after root `ORCH_PLAN.md` is removed from the
   root surface
4. `inputs/ORCH_PLAN.stale.md` as the preserved stale orchestration file to
   archive during `WS-C`

### Sentinel Conventions

- `task-repo-b1.dispatched|ready|blocked|merged|failed-gate`
- `task-repo-b2.dispatched|ready|blocked|merged|failed-gate`

Meanings:

- `.dispatched`: parent issued the worker packet
- `.ready`: worker claims the lane gate is ready for parent verification
- `.blocked`: worker cannot proceed without a parent decision
- `.merged`: parent reran the lane gate and merged the lane
- `.failed-gate`: parent reran the lane gate and reopened the lane

## Worktree and Branch Plan

Integration worktree:

- Path: `/Users/spensermcconnell/__Active_Code/forge`
- Branch: `feat/bounded-work-redesign`
- Owner: Parent only

Sibling worktree root:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/repo-surface-cleanup/`

Worker worktrees:

- `WS-A`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/repo-surface-cleanup/ws-a-canonical-docs`
  - Branch: `feat/bounded-work-redesign-ws-a-canonical-docs`
- `WS-B`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/repo-surface-cleanup/ws-b-pm-scaffold`
  - Branch: `feat/bounded-work-redesign-ws-b-pm-scaffold`

`WS-C`, `WS-D`, and `WS-E` stay local in the integration worktree because:

- moved-path correctness is tightly coupled across root and
  `docs/project_management/`
- root `PLAN.md` must remain the active authority until the final slice
- each local phase requires immediate audit reruns against the integrated tree
- splitting them into more worktrees increases merge churn without adding useful
  concurrency

## Workstream Plan

### WS-A: Canonical Docs Rewrite

Task ID:

- `task/repo-b1-canonical-docs`

Owner:

- Worker `WS-A`
- Parent controls dispatch, verification, merge, and reopen decisions

Owned files:

- `README.md`
- `roadmap.md`
- `docs/roadmap.md`
- `docs/contributing.md`

Forbidden surfaces:

- `docs/project_management/**`
- `tests/**`
- `anvil/**`
- root historical/future markdown files

Required changes:

- `README.md` becomes the canonical front door and links only to files that
  will exist after this branch
- `README.md` links to `docs/contributing.md`,
  `docs/analysis_review_contract.md`, and `docs/roadmap.md`
- `README.md` drops the non-existent docs set listed in `PLAN.md`
- `docs/roadmap.md` becomes the only roadmap body and is split into
  `## Current focus` and `## Future directions`
- root `roadmap.md` becomes a short pointer only

Lane command:

```bash
rg -n "docs/installation\.md|docs/getting_started\.md|docs/architecture_overview\.md|docs/leadership_architecture\.md|docs/configuration_system\.md|docs/provider_system\.md|docs/provider_support\.md|docs/role_based_configuration\.md|docs/testing_guide\.md|docs/checkpointing\.md" README.md roadmap.md docs/roadmap.md docs/contributing.md
```

`gate/canonical-docs` is green only when:

- the lane command returns no hits
- `README.md` contains the canonical current-doc links
- root `roadmap.md` is pointer-shaped, not roadmap-body-shaped
- `docs/roadmap.md` carries the required two-section split
- no forbidden surfaces were touched

### WS-B: Project-Management Scaffold

Task ID:

- `task/repo-b2-pm-scaffold`

Owner:

- Worker `WS-B`
- Parent controls dispatch, verification, merge, and reopen decisions

Owned files and directories:

- `docs/project_management/README.md`
- `docs/project_management/history/`
- `docs/project_management/history/notes/`
- `docs/project_management/plans/active/feat-bounded-work-redesign/`
- `docs/project_management/plans/history/`
- `docs/project_management/future/`

Forbidden surfaces:

- `README.md`
- `roadmap.md`
- `docs/roadmap.md`
- root historical/future markdown files
- `tests/**`
- `anvil/**`

Required changes:

- destination directories exist
- `docs/project_management/README.md` explains:
  - current docs live outside this folder
  - this folder holds preserved history, ADRs, future backlog, and active-plan
    archival material
  - the eventual active plan destination is
    `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md`
- no root files are moved yet

Lane command:

```bash
test -d docs/project_management/history && test -d docs/project_management/history/notes && test -d docs/project_management/plans/active/feat-bounded-work-redesign && test -d docs/project_management/plans/history && test -d docs/project_management/future && test -f docs/project_management/README.md
```

`gate/pm-scaffold` is green only when:

- the lane command succeeds
- `docs/project_management/adrs/` remains untouched
- `docs/project_management/README.md` defines active vs history vs future
  clearly
- no canonical docs, tests, or runtime files were touched

### WS-C: Parent Local History and Future Moves

Task ID:

- `task/repo-c1-history-and-future-moves`

Owner:

- Parent only

Owned files:

- `docs/project_management/history/feature_specification_vnext_roadmap.md`
- `docs/project_management/history/notes/CLI_PROVIDER_UPDATE_NOTES.md`
- `docs/project_management/history/notes/FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`
- `docs/project_management/plans/history/PLAN_M3.md`
- `docs/project_management/plans/history/ORCH_PLAN.md`
- `docs/project_management/future/TODOS.md`
- root deletions of moved copies
- `docs/project_management/README.md` only if moved-path links require repair

Required changes:

- move `docs/feature_specification_vnext_roadmap.md` under
  `docs/project_management/history/`
- move root notes under `docs/project_management/history/notes/`
- move old plans under `docs/project_management/plans/history/`
- move `TODOS.md` under `docs/project_management/future/`
- materialize preserved stale orchestration content at
  `docs/project_management/plans/history/ORCH_PLAN.md`
- remove root `ORCH_PLAN.md` from the repo surface after
  `inputs/ORCH_PLAN.active.md` exists
- leave root `PLAN.md` in place

Phase commands:

```bash
test -f PLAN.md
test -f docs/project_management/history/feature_specification_vnext_roadmap.md
test -f docs/project_management/history/notes/CLI_PROVIDER_UPDATE_NOTES.md
test -f docs/project_management/history/notes/FORGE_HARNESS_SURFACE_UPDATE_NOTES.md
test -f docs/project_management/plans/history/PLAN_M3.md
test -f docs/project_management/plans/history/ORCH_PLAN.md
test -f docs/project_management/future/TODOS.md
test ! -f docs/feature_specification_vnext_roadmap.md
test ! -f CLI_PROVIDER_UPDATE_NOTES.md
test ! -f FORGE_HARNESS_SURFACE_UPDATE_NOTES.md
test ! -f PLAN_M3.md
test ! -f ORCH_PLAN.md
test ! -f TODOS.md
```

`gate/history-moves` is green only when:

- all moved-file existence checks succeed
- all removed-root-file checks succeed
- root `PLAN.md` still exists
- preserved historical files remain substantially verbatim
- no runtime or test files were modified in this phase

### WS-D: Parent Local Regression Protection

Task ID:

- `task/repo-d1-regression-protection`

Owner:

- Parent only

Owned files:

- `tests/test_harness_analysis_contract.py`
- `tests/test_docs_surface.py`

Required changes:

- update the hardcoded notes path in `tests/test_harness_analysis_contract.py`
- add `tests/test_docs_surface.py`
- run the validation commands from `PLAN.md`
- fix only stale active-surface references discovered by those audits

Phase commands:

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py tests/test_docs_surface.py
poetry run python -m anvil list
rg -n "docs/installation\.md|docs/getting_started\.md|docs/architecture_overview\.md|docs/leadership_architecture\.md|docs/configuration_system\.md|docs/provider_system\.md|docs/provider_support\.md|docs/role_based_configuration\.md|docs/testing_guide\.md|docs/checkpointing\.md" README.md roadmap.md docs/roadmap.md docs/contributing.md docs/project_management/README.md docs/analysis_review_contract.md examples/README.md scripts/README.md
rg -n "(^|/)(CLI_PROVIDER_UPDATE_NOTES\.md|FORGE_HARNESS_SURFACE_UPDATE_NOTES\.md|PLAN_M3\.md|ORCH_PLAN\.md|TODOS\.md|feature_specification_vnext_roadmap\.md)" README.md roadmap.md docs/roadmap.md docs/contributing.md docs/project_management/README.md docs/analysis_review_contract.md examples/README.md scripts/README.md tests anvil --glob '!archived/**'
```

`gate/docs-regression` is green only when:

- targeted pytest passes
- `poetry run python -m anvil list` still works
- the first `rg` command returns no hits
- the second `rg` command returns only intentional
  `docs/project_management/` references
- no runtime files were modified

### WS-E: Parent Local Final Plan Relocation

Task ID:

- `task/repo-e1-final-plan-relocation`

Owner:

- Parent only

Owned files:

- `PLAN.md`
- `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md`
- `docs/project_management/README.md`

Required changes:

- move root `PLAN.md` to
  `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md`
- update `docs/project_management/README.md` to point at the final active-plan
  path
- rerun the same validation commands from `WS-D`
- verify that root cleanup is complete only after the move

Phase commands:

```bash
test ! -f PLAN.md
test -f docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md
poetry run pytest -q tests/test_harness_analysis_contract.py tests/test_docs_surface.py
poetry run python -m anvil list
rg -n "docs/installation\.md|docs/getting_started\.md|docs/architecture_overview\.md|docs/leadership_architecture\.md|docs/configuration_system\.md|docs/provider_system\.md|docs/provider_support\.md|docs/role_based_configuration\.md|docs/testing_guide\.md|docs/checkpointing\.md" README.md roadmap.md docs/roadmap.md docs/contributing.md docs/project_management/README.md docs/analysis_review_contract.md examples/README.md scripts/README.md
rg -n "(^|/)(CLI_PROVIDER_UPDATE_NOTES\.md|FORGE_HARNESS_SURFACE_UPDATE_NOTES\.md|PLAN_M3\.md|ORCH_PLAN\.md|TODOS\.md|feature_specification_vnext_roadmap\.md|PLAN\.md)" README.md roadmap.md docs/roadmap.md docs/contributing.md docs/project_management/README.md docs/analysis_review_contract.md examples/README.md scripts/README.md tests anvil --glob '!archived/**'
```

`gate/final-root-cleanup` is green only when:

- root `PLAN.md` is gone
- the active plan exists only at
  `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md`
- the rerun pytest and CLI checks still pass after the move
- the stale-link audit remains clean
- the moved-path audit returns only intentional preserved-history references

## Blocker and Conflict Protocols

### Blocker Protocol

A worker or parent-local phase must stop when:

- it needs a peer-owned file change
- it detects scope drift beyond repo-surface cleanup
- it cannot satisfy a gate without touching `anvil/`, `archived/`, or ADR files
- it would require moving `PLAN.md` before `WS-E`
- the stale pre-replacement `ORCH_PLAN.md` was not captured before root
  replacement

Required blocker return:

- exact file or interface at issue
- exact reason
- smallest parent decision needed
- exact command or audit output demonstrating the blocker, if relevant

### Conflict Protocol

Conflict type: textual overlap

- Resolution: parent reassigns or serializes the edit
- Workers do not self-resolve peer overlap

Conflict type: authority drift

- Example: a lane proposes a second canonical roadmap body or a second
  contributor front door
- Resolution: parent rejects the drift and reissues the packet against `PLAN.md`

Conflict type: path-coupled merge drift

- Example: root removals and moved-path tests no longer line up after worker
  merges
- Resolution: parent handles the fix locally in `WS-C` or `WS-D`
- This is one reason the final three phases stay local

## Context-Control Rules

Parent live-context policy:

- Keep only `PLAN.md`, frozen invariants, current lane packet, and current gate
  results live.
- Re-open `PLAN.md` before each phase transition instead of trusting memory.
- Continue execution from `inputs/ORCH_PLAN.active.md` after root `ORCH_PLAN.md`
  leaves the root.

Worker packet policy:

- Each worker packet includes:
  - task id
  - owned files
  - forbidden surfaces
  - exact exit criteria
  - exact lane command
  - only the relevant excerpt from `PLAN.md`
- Do not pass the full repo history or unrelated roadmap prose into worker
  context.

Worker return policy:

- Return only:
  - changed files
  - commands run and results
  - blockers
  - any gate-relevant ambiguity

Parent review policy:

- Parent reviews owned-file boundaries first.
- Parent reruns every worker gate in the integration worktree before merge
  acceptance.
- Parent does the only final acceptance sweep.

## Repo Tests and Acceptance

### Acceptance Checklist

- [ ] `README.md` links only to existing files
- [ ] `README.md` no longer links to the non-existent docs set
- [ ] `docs/contributing.md` exists and is linked from `README.md`
- [ ] `docs/roadmap.md` is canonical and split into current focus vs future
      directions
- [ ] root `roadmap.md` is a pointer only
- [ ] `docs/project_management/README.md` explains active plan vs history vs
      future
- [ ] history notes moved under `docs/project_management/history/notes/`
- [ ] old plans moved under `docs/project_management/plans/history/`
- [ ] `TODOS.md` moved under `docs/project_management/future/`
- [ ] `tests/test_harness_analysis_contract.py` updated to the moved notes path
- [ ] `tests/test_docs_surface.py` added and passing
- [ ] `poetry run python -m anvil list` still works
- [ ] grep audits show no stale active-surface references to removed paths
- [ ] root `PLAN.md` moved only after all earlier validation passes

### Final Green / Blocked Protocol

If a gate fails:

- parent records a `blocked` verdict in `state.json`
- parent writes the failing command, output, affected files, and reopen reason
  to `gates/<gate-name>.md`
- parent appends the blocker and next required action to `session.log`
- no later phase starts until the failed gate is resolved or planning is
  reopened

If the run completes:

- parent records a `green` verdict in `state.json`
- parent writes final gate results and checklist completion to `acceptance/`
- parent appends the completion summary and final validation commands to
  `session.log`

### Green Conditions

`gate/repo-surface-complete` is green only when:

- every prior gate is green
- no hard guard was violated
- the final repo root surface matches the `PLAN.md` success criteria
- the acceptance checklist is fully checked off
- the parent has recorded the final command results under
  `.runs/repo-surface-cleanup-orch/acceptance/`

## Assumptions

- The parent will capture the stale pre-replacement root `ORCH_PLAN.md` into
  `inputs/ORCH_PLAN.stale.md` before writing this new file.
- The parent will snapshot the current modified root `PLAN.md` before
  dispatching workers, because worker worktrees may not include that in-progress
  worktree state.
- `docs/project_management/adrs/` already exists and remains read-only context
  for this pass.
