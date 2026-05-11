# PLAN: Repo Hygiene Without Losing the Original Thesis

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260511-111006.md`
Supersedes:
- the prior bounded-work `PLAN.md` on this branch
- `ORCH_PLAN.md` as an active implementation guide
- the earlier design draft `spensermcconnell-feat-bounded-work-redesign-design-20260510-222342.md`

## Plan Summary

This branch is a repo-surface cleanup pass, not a harness behavior change.

The problem is not missing documentation. The problem is that the repo root still
looks like multiple competing product definitions. `README.md` points at
non-existent docs, `roadmap.md` and `docs/roadmap.md` both act like canonical
roadmaps, and root-level plans and update notes still read like current
front-door material.

The implementation goal is to make the repo read as one coherent system with
three explicit layers:

1. canonical now
2. preserved history
3. future direction

No runtime behavior changes are allowed. The only code/test changes in scope are:

- updating path-coupled tests that break when historical docs move
- adding one small docs-surface regression test so the authority map does not
  drift back

## Success Criteria

- A new contributor can answer "what Forge is, how to run it, and where to
  start" in under 10 minutes from `README.md` plus one linked doc.
- `README.md` links only to files that exist after this branch lands.
- `docs/roadmap.md` is the only canonical roadmap body.
- root `roadmap.md` becomes a short pointer, not a second roadmap.
- root history/update-note clutter moves under `docs/project_management/`.
- leadership/performance code remains visible as active thesis and future
  direction, not deprecated code.
- `tests/test_harness_analysis_contract.py` keeps passing after the history-note
  move.
- `tests/test_docs_surface.py` prevents authority-map regressions.
- the root human-facing surface is reduced to:
  - `README.md`
  - `roadmap.md`
  - operational/package metadata
  - code directories

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing surface | Plan decision |
|---|---|---|
| Broken front door | [README.md](/Users/spensermcconnell/__Active_Code/forge/README.md) links to `docs/installation.md`, `docs/getting_started.md`, `docs/architecture_overview.md`, `docs/leadership_architecture.md`, `docs/configuration_system.md`, `docs/provider_system.md`, `docs/provider_support.md`, `docs/role_based_configuration.md`, `docs/testing_guide.md`, and `docs/checkpointing.md`, none of which exist | Rewrite README around files that actually exist today. |
| Duplicate roadmap authority | [roadmap.md](/Users/spensermcconnell/__Active_Code/forge/roadmap.md) and [docs/roadmap.md](/Users/spensermcconnell/__Active_Code/forge/docs/roadmap.md) both present roadmap content | Keep `docs/roadmap.md` canonical. Reduce root `roadmap.md` to a pointer only. |
| Historical docs mixed with current docs | root `PLAN.md`, `PLAN_M3.md`, `ORCH_PLAN.md`, `CLI_PROVIDER_UPDATE_NOTES.md`, `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`, and `TODOS.md` are visible from the repo root | Move them under `docs/project_management/` and label them by role. |
| Existing project-management namespace | [docs/project_management/](/Users/spensermcconnell/__Active_Code/forge/docs/project_management) already exists for ADR storage | Reuse the namespace instead of inventing a second history area. |
| Current canonical contract | [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md) is a real current-surface doc | Keep it canonical and link to it from the rewritten README. |
| Contributor-adjacent docs | [examples/README.md](/Users/spensermcconnell/__Active_Code/forge/examples/README.md) and [scripts/README.md](/Users/spensermcconnell/__Active_Code/forge/scripts/README.md) already exist | Link to them from a new contributor doc instead of overloading README. |
| Path-coupled regression | [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py:1027) hardcodes `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md` at the repo root | Update that test in the same slice as the move. |
| Active-plan tension | this file is currently root `PLAN.md`, but the desired end state removes root plans from the front door | Keep root `PLAN.md` authoritative until the final relocation slice. |

### Minimum complete scope

This is the minimum complete implementation. Nothing in this list is optional if
the branch is going to leave the repo in a coherent state:

1. [README.md](/Users/spensermcconnell/__Active_Code/forge/README.md)
2. [roadmap.md](/Users/spensermcconnell/__Active_Code/forge/roadmap.md)
3. [docs/roadmap.md](/Users/spensermcconnell/__Active_Code/forge/docs/roadmap.md)
4. `docs/contributing.md` (new)
5. `docs/project_management/README.md` (new)
6. `docs/project_management/history/`
7. `docs/project_management/history/notes/`
8. `docs/project_management/plans/active/feat-bounded-work-redesign/`
9. `docs/project_management/plans/history/`
10. `docs/project_management/future/`
11. moved historical/future markdown files from the root
12. [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py)
13. `tests/test_docs_surface.py` (new)

Do not touch Python runtime modules under `anvil/` for this pass.

### Complexity verdict

This pass touches more than 8 files. That normally smells.

Here it is justified because the blast radius is almost entirely path-level and
content-authority-level:

- one canonical front-door rewrite
- one canonical roadmap cleanup
- one contributor doc
- one project-management index
- a handful of markdown moves
- one existing path-coupled test fix
- one small regression test

What would be overbuilt:

- a docs site generator
- symlinks or redirect machinery
- Python package moves
- historical doc rewrites beyond light framing and link correction

### Search/build verdict

No new platform needs to be invented.

Reuse what already exists:

- `docs/project_management/` as the preserved-history namespace
- `docs/analysis_review_contract.md` as the canonical contract doc
- `examples/README.md` and `scripts/README.md` as secondary entry points

This is information architecture work, not infrastructure work.

### TODOS cross-reference

[TODOS.md](/Users/spensermcconnell/__Active_Code/forge/TODOS.md) contains real
future work, but it should not compete with the front door.

Preserve its contents exactly, move it to
`docs/project_management/future/TODOS.md`, and only add new TODO material if
implementation uncovers work that is clearly outside this cleanup pass.

### Completeness verdict

The shortcut is "rewrite README and leave the rest alone." That does not solve
the real problem.

The complete version must do all of this together:

- define one canonical roadmap
- create one contributor entry point
- move history out of the root
- preserve future-direction material without pretending it is current usage docs
- fix path-coupled tests
- add a regression check for the new authority map

### Distribution and DX verdict

Forge is a developer tool. For this slice, documentation is part of
distribution.

If the front door is wrong, the repo is effectively harder to install, harder to
orient, and easier to misread. That means this branch is incomplete unless the
README, contributor doc, roadmap, historical relocation, and path-level
regression checks all land together.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Canonical roadmap | `docs/roadmap.md` | One authoritative roadmap body. |
| Root roadmap path | keep `roadmap.md` as a short pointer file | Preserve the familiar path without carrying duplicate content. |
| Contributor entry point | create `docs/contributing.md` | README should not carry every contributor detail. |
| Historical namespace | use `docs/project_management/` | It already exists and matches the repo's current organization. |
| Historical note preservation | move note files individually, do not collapse them into a synthetic changelog | Lowest-risk preservation with minimal editorial churn. |
| Leadership/performance framing | describe it as active thesis and future direction, not deprecated | Matches the design intent and avoids falsifying repo history. |
| Runtime scope | no behavior changes under `anvil/` | This is repo hygiene only. |
| Root `PLAN.md` lifecycle | keep this file in the root while implementing, move it only in the final cleanup slice | Avoid losing the working spec mid-branch. |
| `ORCH_PLAN.md` treatment | treat as historical and move it during this pass | It describes a superseded implementation slice. |
| Test strategy | update the existing hardcoded-path test and add one focused docs-surface regression test | Engineered enough, without building a docs test framework. |
| Pointer strategy | no symlinks, no generated redirect layer | Too clever for a markdown-only cleanup. |
| Audit boundary | audit active surfaces only, exclude `archived/`, caches, and generated run artifacts | Historical archives can remain historically messy. |

## Implementation Topology

### Canonical authority map

| Surface | Role after this branch | Notes |
|---|---|---|
| `README.md` | canonical front door | present tense only, current reality only |
| `roadmap.md` | canonical pointer | must not contain roadmap body prose |
| `docs/roadmap.md` | canonical roadmap | explicit `Current focus` and `Future directions` split |
| `docs/contributing.md` | canonical contributor entry point | install/run/test plus repo map |
| `docs/analysis_review_contract.md` | canonical contract doc | keep in place |
| `docs/project_management/README.md` | canonical index into preserved docs | explains active plan vs history vs future |
| `docs/project_management/history/` | preserved historical docs | branch/milestone material no longer treated as front-door docs |
| `docs/project_management/future/` | future-facing backlog | preserves TODO-style planning without front-door competition |

### Concrete file map

| Current path | Action | New path |
|---|---|---|
| `README.md` | rewrite in place | `README.md` |
| `roadmap.md` | reduce to pointer | `roadmap.md` |
| `docs/roadmap.md` | keep as canonical roadmap | `docs/roadmap.md` |
| `docs/feature_specification_vnext_roadmap.md` | move | `docs/project_management/history/feature_specification_vnext_roadmap.md` |
| `PLAN.md` | move at final step | `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md` |
| `PLAN_M3.md` | move | `docs/project_management/plans/history/PLAN_M3.md` |
| `ORCH_PLAN.md` | move | `docs/project_management/plans/history/ORCH_PLAN.md` |
| `CLI_PROVIDER_UPDATE_NOTES.md` | move | `docs/project_management/history/notes/CLI_PROVIDER_UPDATE_NOTES.md` |
| `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md` | move | `docs/project_management/history/notes/FORGE_HARNESS_SURFACE_UPDATE_NOTES.md` |
| `TODOS.md` | move | `docs/project_management/future/TODOS.md` |

### Dependency graph

```text
authoritative docs rewrite
   ├── README.md
   ├── docs/contributing.md
   ├── docs/roadmap.md
   └── roadmap.md
          |
          v
project-management scaffold
   ├── docs/project_management/README.md
   ├── history/
   ├── history/notes/
   ├── plans/active/feat-bounded-work-redesign/
   ├── plans/history/
   └── future/
          |
          v
historical and future file moves
   ├── note files
   ├── old plans
   ├── future backlog
   └── historical roadmap doc
          |
          v
compatibility and regression protection
   ├── tests/test_harness_analysis_contract.py path update
   └── tests/test_docs_surface.py
          |
          v
final plan relocation
   └── PLAN.md -> docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md
```

### Architecture constraints

- The root README must describe current reality only.
- The root roadmap file must never contain roadmap body prose again.
- Historical files must remain reachable, but only through
  `docs/project_management/`.
- Active-surface reference audits run against:
  - `README.md`
  - `roadmap.md`
  - `docs/roadmap.md`
  - `docs/contributing.md`
  - `docs/project_management/README.md`
  - `docs/analysis_review_contract.md`
  - `examples/README.md`
  - `scripts/README.md`
  - `tests/`
  - `anvil/`
- Preserved history under `docs/project_management/history/**`,
  `docs/project_management/plans/history/**`, and
  `docs/project_management/future/**` is not part of the active-surface grep
  gate.
- Historical docs may remain largely verbatim unless a link rewrite is required
  for active-surface correctness.
- Existing ADR locations under `docs/project_management/adrs/` stay unchanged.
- Root `PLAN.md` remains the source of truth until the final relocation slice
  passes validation.

## Code Quality Review

### Authority-map rules

1. `README.md` is present tense only.
2. `docs/roadmap.md` is the canonical roadmap body.
3. `roadmap.md` is a pointer only.
4. `docs/contributing.md` explains where to work and where to read next.
5. `docs/project_management/README.md` explains active plan vs history vs future.
6. historical docs stay mostly verbatim; only add light framing where needed.

### DRY rules

- Do not duplicate the roadmap body in two files.
- Do not duplicate install/run/test detail across README and contributing.
  README links out, contributor doc carries detail.
- Do not keep both root and moved copies of historical docs.
- Do not create a second history namespace outside `docs/project_management/`.

### Naming and structure rules

- `history/` means landed or superseded material.
- `future/` means backlog and planned work.
- `plans/active/<branch>/PLAN.md` means a preserved working plan.
- `plans/history/` means old milestone or branch plans no longer driving work.

### Branch-name mismatch

The branch name still says `bounded-work-redesign`. Leave it alone.

Renaming the git branch is out of scope and buys nothing for repo readers.

## Test Review

This branch is docs-heavy, but the failure modes are real. Coverage here means
path coverage, authority coverage, and broken-reference coverage.

### Existing regression already at risk

[tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py:1027)
hardcodes the root path for `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`. If the file
moves without updating that test, the branch fails immediately.

### Required new regression test

Add `tests/test_docs_surface.py` with focused assertions for the new docs
contract:

- `README.md` exists and links to `docs/contributing.md`,
  `docs/analysis_review_contract.md`, and `docs/roadmap.md`
- `README.md` no longer links to the non-existent doc set currently named above
- `roadmap.md` is a pointer, not a second roadmap body
- `docs/contributing.md` exists
- `docs/project_management/README.md` exists
- moved history and future files exist at their new paths
- root no longer contains:
  - `PLAN_M3.md`
  - `ORCH_PLAN.md`
  - `CLI_PROVIDER_UPDATE_NOTES.md`
  - `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`
  - `TODOS.md`

### Coverage diagram

```text
DOC PATH COVERAGE
===========================
[+] README.md
    ├── [GAP] stale links to non-existent docs
    ├── [PLAN] rewrite to existing canonical docs only
    └── [TEST] assert required links + assert banned links absent

[+] roadmap authority
    ├── [GAP] root roadmap duplicates docs/roadmap.md
    ├── [PLAN] reduce root roadmap to pointer only
    └── [TEST] assert root roadmap is pointer-shaped, not body-shaped

[+] project-management history moves
    ├── [GAP] root historical docs currently compete with current docs
    ├── [PLAN] move to docs/project_management/*
    ├── [REGRESSION] tests/test_harness_analysis_contract.py path update
    └── [TEST] assert moved files exist and root copies do not

[+] contributor orientation
    ├── [GAP] no dedicated docs/contributing.md
    ├── [PLAN] create docs/contributing.md
    └── [TEST] assert doc exists and is linked from README
```

### Validation commands

Run these commands after the moves and rewrites land:

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py tests/test_docs_surface.py
poetry run python -m anvil list
rg -n "docs/installation\\.md|docs/getting_started\\.md|docs/architecture_overview\\.md|docs/leadership_architecture\\.md|docs/configuration_system\\.md|docs/provider_system\\.md|docs/provider_support\\.md|docs/role_based_configuration\\.md|docs/testing_guide\\.md|docs/checkpointing\\.md" README.md roadmap.md docs/roadmap.md docs/contributing.md docs/project_management/README.md docs/analysis_review_contract.md examples/README.md scripts/README.md
rg -n "(^|/)(CLI_PROVIDER_UPDATE_NOTES\\.md|FORGE_HARNESS_SURFACE_UPDATE_NOTES\\.md|PLAN_M3\\.md|ORCH_PLAN\\.md|TODOS\\.md|feature_specification_vnext_roadmap\\.md)" README.md roadmap.md docs/roadmap.md docs/contributing.md docs/project_management/README.md docs/analysis_review_contract.md examples/README.md scripts/README.md tests anvil --glob '!archived/**'
```

Expected result:

- the targeted pytest run passes
- `python -m anvil list` still works
- the first `rg` command returns no hits
- the second `rg` command only returns intentional new paths under
  `docs/project_management/` from canonical docs, tests, or code references

### Done criteria for test coverage

This plan is not complete until both of these are true:

1. the path-coupled regression is updated in the same slice as the note move
2. the new docs-surface regression test proves the new authority map

## Performance Review

The main performance risk here is human performance, not CPU time.

### Risks to avoid

- moving files before canonical links exist, causing a broken-doc window
- rewriting historical documents instead of relocating them
- touching Python runtime modules and dragging product regression into a docs branch
- trying to clean `archived/` in the same slice

### Boring implementation choices

- scaffold destination directories first
- rewrite canonical docs second
- move historical files third
- update tests and run audits fourth
- move root `PLAN.md` last

That sequence is the whole game. It minimizes merge churn and keeps the branch
readable while work is in flight.

## Detailed Implementation Plan

### Phase 1: Freeze authority and scaffold destinations

Goal: create the directory structure and one authoritative index before moving
anything.

Files touched:

- `docs/project_management/README.md` (new)
- `docs/project_management/history/`
- `docs/project_management/history/notes/`
- `docs/project_management/plans/active/feat-bounded-work-redesign/`
- `docs/project_management/plans/history/`
- `docs/project_management/future/`

Steps:

1. Create the destination directories if they do not already exist.
2. Add `docs/project_management/README.md` with a short authority map:
   - current docs live outside this folder
   - this folder holds active plan history, preserved history, ADRs, and future backlog
   - link to `plans/active/feat-bounded-work-redesign/PLAN.md` as the eventual active-plan destination
3. Do not move any root files yet.

Exit criteria:

- destination directories exist
- `docs/project_management/README.md` exists and explains the taxonomy clearly
- root surface is unchanged so far

### Phase 2: Rewrite canonical current-surface docs

Goal: make the canonical front door correct before historical moves happen.

Files touched:

- [README.md](/Users/spensermcconnell/__Active_Code/forge/README.md)
- [roadmap.md](/Users/spensermcconnell/__Active_Code/forge/roadmap.md)
- [docs/roadmap.md](/Users/spensermcconnell/__Active_Code/forge/docs/roadmap.md)
- `docs/contributing.md` (new)

Steps:

1. Rewrite `README.md` so it does only these jobs:
   - describe Forge in present tense
   - show the current primary surfaces:
     - analysis-review harness
     - leadership/orchestration foundation
   - provide correct install/run/test commands
   - link only to files that actually exist after this branch
2. Create `docs/contributing.md` with:
   - repo map for `anvil/`, `docs/`, `examples/`, `scripts/`, and `tests/`
   - current entry points for harness and non-harness code
   - project-management history location
   - concrete commands from the repo guidelines:
     - `poetry install`
     - `poetry run python -m anvil list`
     - `poetry run pytest -q`
     - `poetry run pytest -q tests/test_lg_offline_smoke.py`
3. Rewrite `docs/roadmap.md` so it has two explicit sections:
   - `## Current focus`
   - `## Future directions`
4. Replace root `roadmap.md` with a short pointer to `docs/roadmap.md`.

Exit criteria:

- README has no dead links
- root roadmap no longer contains duplicated roadmap prose
- contributor guidance has exactly one canonical location

### Phase 3: Move preserved history and future docs

Goal: remove non-canonical history from the root without losing it.

Files touched:

- `docs/feature_specification_vnext_roadmap.md`
- `PLAN_M3.md`
- `ORCH_PLAN.md`
- `CLI_PROVIDER_UPDATE_NOTES.md`
- `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`
- `TODOS.md`
- `docs/project_management/README.md` if link paths need updating

Steps:

1. Move `docs/feature_specification_vnext_roadmap.md` to
   `docs/project_management/history/feature_specification_vnext_roadmap.md`.
2. Move root historical notes:
   - `CLI_PROVIDER_UPDATE_NOTES.md`
   - `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`
   into `docs/project_management/history/notes/`.
3. Move old plans:
   - `PLAN_M3.md`
   - `ORCH_PLAN.md`
   into `docs/project_management/plans/history/`.
4. Move `TODOS.md` to `docs/project_management/future/TODOS.md`.
5. Update any active-surface links or indexes that still reference the old
   locations.
6. Leave historical documents mostly verbatim unless a path correction is needed.

Exit criteria:

- root historical files are gone from the root
- moved files exist at the new locations
- active-surface docs point at the new locations where needed

### Phase 4: Compatibility fixes and regression protection

Goal: close the known path regressions and prove the new authority map.

Files touched:

- [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py)
- `tests/test_docs_surface.py` (new)

Steps:

1. Update [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py:1027)
   to read the moved `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md` path.
2. Add `tests/test_docs_surface.py` with the assertions listed above.
3. Run the validation commands from the Test Review section.
4. Fix any stale active-surface references found by the grep audit.

Exit criteria:

- both targeted tests pass
- the grep audits are clean
- `python -m anvil list` still works

### Phase 5: Final plan relocation and root cleanup

Goal: finish the cleanup by moving the active branch plan out of the root after
every other dependency is already stable.

Files touched:

- `PLAN.md`
- `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md`
- `docs/project_management/README.md`

Steps:

1. Move this file from root `PLAN.md` to
   `docs/project_management/plans/active/feat-bounded-work-redesign/PLAN.md`.
2. Update `docs/project_management/README.md` to point at that active-plan path.
3. Re-run the targeted tests and grep audits after the move.
4. Do not leave a second full plan copy at the root.

Exit criteria:

- the plan exists only at the active-plan destination
- root cleanup is complete
- the same validation commands still pass after the move

## Failure Modes

| Failure mode | Test coverage | Error handling | User-visible impact | Plan response |
|---|---|---|---|---|
| README still links to missing docs | new `tests/test_docs_surface.py` + grep audit | none in runtime | new contributors hit dead links immediately | rewrite README and add regression test |
| root and docs roadmap drift again | new `tests/test_docs_surface.py` | none in runtime | conflicting product direction docs | force root roadmap to pointer-only |
| moved history note breaks existing test | existing `tests/test_harness_analysis_contract.py` after path update | pytest failure | CI break, unclear cause | update the test in the same slice as the move |
| moving `PLAN.md` too early strands the working spec | no automatic recovery | human-process failure | branch loses its authoritative implementation plan mid-flight | move `PLAN.md` last |
| leadership/performance work is framed as deprecated | docs review only | none in runtime | repo tells a false story about product direction | explicit wording in README and roadmap |
| root clutter remains because moves were partial | docs-surface test + grep audit | none in runtime | root still looks experimental and noisy | enforce no-root-history end state |

Critical gap definition for this branch:

Any moved-path failure that has no regression test and leaves the repo claiming a
path that no longer exists is a critical gap. This plan closes those gaps with
one required regression update plus one new docs-surface test.

## NOT in Scope

- Python module moves under `anvil/`
- package renames
- CLI behavior changes
- harness contract changes
- ADR rewrites or status reclassification
- generated site tooling, symlinks, or redirect infrastructure
- cleanup of `archived/`
- cleanup of `.forge-harness-runs*`, caches, or generated artifacts
- git branch renaming
- consolidating historical notes into one synthetic changelog

## Worktree Parallelization Strategy

Parallelization is available, but only for the slices that do not fight over the
same module-level surface.

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Canonical docs rewrite | repo root docs surface, `docs/` | — |
| B. Project-management scaffold | `docs/project_management/` | — |
| C. Historical and future file moves | repo root docs surface, `docs/project_management/` | A, B |
| D. Compatibility test updates | `tests/`, `docs/project_management/` | C |
| E. Final plan relocation | repo root docs surface, `docs/project_management/` | D |

### Parallel lanes

- Lane A: canonical docs rewrite
  - `README.md`
  - `roadmap.md`
  - `docs/roadmap.md`
  - `docs/contributing.md`
- Lane B: project-management scaffold
  - `docs/project_management/README.md`
  - destination directories for `history/`, `history/notes/`, `plans/active/`, `plans/history/`, and `future/`
- Lane C: historical and future file moves
  - move root historical and future docs into `docs/project_management/`
  - repair active-surface references to those new locations
- Lane D: compatibility and regression protection
  - update `tests/test_harness_analysis_contract.py`
  - add `tests/test_docs_surface.py`
  - run validation commands
- Lane E: final plan relocation
  - move `PLAN.md` to the active-plan path
  - rerun validation

### Execution order

Launch Lane A and Lane B in parallel worktrees.

After both land, run Lane C.

After Lane C lands, run Lane D.

Run Lane E last. Do not start it until Lane D passes.

### Conflict flags

- Lanes A and C both touch the root docs surface. Do not run them in parallel.
- Lanes B and C both touch `docs/project_management/`. C must wait for B.
- Lanes C and D are coupled by moved-path correctness. D must run after C.
- Lane E touches the plan path itself. It must be the final lane.

## Acceptance Checklist

- [ ] `README.md` links only to existing files
- [ ] `README.md` no longer links to the current non-existent docs set
- [ ] `docs/contributing.md` exists and is linked from README
- [ ] `docs/roadmap.md` is canonical and split into current focus vs future directions
- [ ] root `roadmap.md` is a pointer only
- [ ] `docs/project_management/README.md` exists and explains active plan vs history vs future
- [ ] history notes moved under `docs/project_management/history/notes/`
- [ ] old plans moved under `docs/project_management/plans/history/`
- [ ] `TODOS.md` moved under `docs/project_management/future/`
- [ ] `tests/test_harness_analysis_contract.py` updated to the new history-note path
- [ ] `tests/test_docs_surface.py` added and passing
- [ ] `poetry run python -m anvil list` still works
- [ ] grep audit shows no stale active-surface references to removed paths
- [ ] root `PLAN.md` moved only after all earlier validation passes

## Completion Summary

- Step 0: Scope Challenge — scope accepted with one explicit addition: a small
  docs-surface regression test
- Architecture Review: resolved around a three-layer docs topology with one
  canonical entry path
- Code Quality Review: DRY authority map locked, duplicate roadmap removed,
  naming and ownership clarified
- Test Review: one existing path regression fixed, one new docs-surface test
  required
- Performance Review: sequential last-mile move plan avoids broken-doc windows
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none beyond preserving the current backlog at a new path
- Failure modes: two docs-path critical gaps, both covered by the test plan
- Parallelization: 5 lanes total, 2 initial parallel, 3 sequential follow-ons
- Lake Score: choose the complete option, not the README-only shortcut
