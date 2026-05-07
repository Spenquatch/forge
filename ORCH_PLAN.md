# ORCH_PLAN: Trust Attestation Over Bounded Output (M1 Only)

## Summary

Target branch: `feat/bounded-work-redesign`  
Implementation source of truth: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`

This orchestration plan is a full rewrite for M1 only. It is executable by a
parent agent driving the `PLAN.md` session to completion. It does not inherit
workflow or scope from the current repository `ORCH_PLAN.md`.

M1 scope is limited to these files:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py`

M1 outcome:

- bounded runs persist deterministic `bounded_attestation_input`
- payload is mirrored in both top-level summary and `run_details`
- payload is built only from finalized bounded analysis state
- payload is semantically validated and fails loudly when malformed
- trust execution does not consume the payload yet
- prompts, reporting, example strategies, public-surface docs, and artifact
  selection remain unchanged

Parent agent remains the only integrator.

## Hard Guards

1. `PLAN.md` is authoritative. If this plan conflicts with `PLAN.md`, stop and
   follow `PLAN.md`.
2. M1 only. No trust-consumption work is allowed.
3. Only the eight scoped files may be modified.
4. Out of scope and must not be edited:
   - `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py`
   - `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py`
   - `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py`
   - anything under `/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/`
   - `/Users/spensermcconnell/__Active_Code/forge/README.md`
   - `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_reporting.py`
5. `analysis_review_schema()` must not change in M1.
6. `apply_final_artifacts(...)`, report selection, publication truth, and final
   artifact semantics must not change.
7. No new package, class family, manager, store, CLI surface, or artifact
   family.
8. Parent is the only actor allowed to merge into `feat/bounded-work-redesign`.
9. If any in-scope file is already dirty before launch, stop and ask the user
   before creating worktrees or assigning tasks.
10. If `PLAN.md` changes at any point, suspend orchestration, refresh
    `interface-lock.md`, and revalidate all active work before resuming.
11. If a lane needs an out-of-scope file to proceed, it must stop and hand off
    a blocker. It may not widen scope on its own.
12. If full-suite failures are unrelated or ambiguous, stop and surface
    evidence to the user.

## Subagent Execution Contract

### Worker Model

Both implementation workers must run as:

- model: `GPT-5.4`
- `reasoning_effort=high`

### Worker Roles

- Parent: orchestration, interface lock, review, merge, rebase, final
  verification
- Worker A: `M1-T02`
- Worker B: `M1-T03`

Parent remains the only integrator.

### Worker Handoff Requirements

Each worker must return one handoff file under the orchestration state root that
contains:

- task ID
- branch name
- worktree path
- changed files
- confirmation whether all changes stayed within owned-file scope: `yes` or `no`
- commands run
- exit code for each command
- tests run
- blockers
- assumptions
- open risks
- explicit statement whether the work matches `PLAN.md` and `interface-lock.md`

### No Tight Polling Rule

Workers are launched once per task. Parent does not tight-poll for progress.
Parent waits for one of these completion sentinels:

- handoff file created under `handoffs/`
- blocked file created under `blocked/`

No repeated status-ping loop. A worker reports only on completion or blocked
exit.

## Orchestration State Root

Canonical state root:

`/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1`

Parent-owned artifacts:

- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/task-board.md`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/interface-lock.md`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/merge-log.md`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/verification.md`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/handoffs/M1-T02.md`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/handoffs/M1-T03.md`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/blocked/`
- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/completion-note.md`

Blocked-run artifact path:

- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/blocked/<task-id>.md`

Successful-close artifact path:

- `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/completion-note.md`

## State Model

### Allowed Task States

| State | Meaning | Set By |
|---|---|---|
| `pending` | task exists but cannot start yet | parent |
| `ready` | prerequisites satisfied and launch packet prepared | parent |
| `in_progress` | worker or parent is actively executing task | parent |
| `handoff` | worker completed and wrote handoff | worker |
| `blocked` | worker or parent cannot proceed and wrote blocker | worker or parent |
| `merged` | parent accepted and merged task branch | parent |
| `verified` | parent completed required post-merge verification | parent |

### Transition Rules

| From | To | Allowed Actor |
|---|---|---|
| `pending` | `ready` | parent |
| `ready` | `in_progress` | parent |
| `in_progress` | `handoff` | worker |
| `in_progress` | `blocked` | worker or parent |
| `handoff` | `merged` | parent |
| `merged` | `verified` | parent |

Invalid transitions are not allowed. Workers may not set `merged` or
`verified`.

## Kickoff / Bootstrap

Parent performs bootstrap locally in `/Users/spensermcconnell/__Active_Code/forge`.

### Preflight Stop Check

Run:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge branch --show-current
git -C /Users/spensermcconnell/__Active_Code/forge status --short -- \
  /Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py \
  /Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py \
  /Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py \
  /Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py \
  /Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md \
  /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py \
  /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py \
  /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py
```

Stop conditions at preflight:

- branch is not `feat/bounded-work-redesign`
- any in-scope file is dirty

If either condition is true, stop and ask the user.

### Bootstrap Commands

```bash
mkdir -p /Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/handoffs
mkdir -p /Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/blocked
mkdir -p /Users/spensermcconnell/__Active_Code/forge/.worktrees

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge/.worktrees/bounded-work-redesign-m1-contract-docs \
  -b codex/bounded-work-redesign-m1-contract-docs \
  feat/bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge/.worktrees/bounded-work-redesign-m1-runner-validation \
  -b codex/bounded-work-redesign-m1-runner-validation \
  feat/bounded-work-redesign
```

### Seed `task-board.md`

Create `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/task-board.md` with:

```md
# Task Board

## Branch
- target: `feat/bounded-work-redesign`

## Tasks
| Task ID | Owner | Branch | State | Notes |
|---|---|---|---|---|
| M1-T00 | parent | feat/bounded-work-redesign | in_progress | bootstrap |
| M1-T01 | parent | feat/bounded-work-redesign | pending | interface lock and launch packets |
| M1-T02 | worker-a | codex/bounded-work-redesign-m1-contract-docs | pending | contracts/schema/docs lane |
| M1-T03 | worker-b | codex/bounded-work-redesign-m1-runner-validation | pending | runner/validation lane |
| M1-T04 | parent | feat/bounded-work-redesign | pending | review/merge/rebase |
| M1-T05 | parent | feat/bounded-work-redesign | pending | merged verification and closeout |
```

### Seed `interface-lock.md`

Create `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/interface-lock.md` with:

```md
# Interface Lock

## M1 Scope
- M1 only
- `PLAN.md` is authoritative
- no trust consumption
- no prompt/reporting/example/public-surface changes

## Locked Literals
- handoff key: `bounded_attestation_input`
- schema version: `analysis_review_bounded_attestation_input_v1`
- trust execution modes:
  - `legacy_full_review`
  - `attestation_over_bounded`

## Locked Invariants
- bounded-only emission
- build from finalized bounded analysis only
- same payload mirrored in top-level summary and `run_details`
- semantic validation must fail loudly
- forbidden publication fields must be absent
- recommendation order is frozen
- `analysis_review_schema()` remains unchanged

## File Ownership
- M1-T02:
  - `anvil/harness/contracts.py`
  - `anvil/harness/schemas.py`
  - `docs/analysis_review_contract.md`
  - `tests/test_harness_analysis_contract.py`
- M1-T03:
  - `anvil/harness/runner.py`
  - `anvil/harness/semantic_validation.py`
  - `tests/test_harness_runner.py`
  - `tests/test_harness_semantic_validation.py`
```

### Seed `merge-log.md`

Create `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/merge-log.md` with:

```md
# Merge Log

Record for each merge:
- task ID
- source branch
- target branch
- reviewed diff scope
- ownership check result
- stale-plan check result
- commands run
- test outputs reviewed
- accept/reject decision
- resulting commit SHA
```

### Seed `verification.md`

Create `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/verification.md` with:

```md
# Verification

Record:
- targeted test commands and exit codes
- full-suite command and exit code
- whether failures are clearly M1-related
- whether failures are unrelated or ambiguous
- final merged verification checklist status
```

### Bootstrap State Transitions

After seeding files and worktrees:

- `M1-T00`: `in_progress` -> `verified`
- `M1-T01`: `pending` -> `ready`

## Workstream Plan

### M1-T00 Parent Bootstrap

Owner: parent  
Branch: `feat/bounded-work-redesign`  
Worktree: `/Users/spensermcconnell/__Active_Code/forge`

Acceptance checklist:

- branch verified as `feat/bounded-work-redesign`
- in-scope dirty check completed
- state root created
- both worktrees created
- `task-board.md` seeded
- `interface-lock.md` seeded
- `merge-log.md` seeded
- `verification.md` seeded

### M1-T01 Parent Interface Lock And Launch

Owner: parent  
Branch: `feat/bounded-work-redesign`  
Worktree: `/Users/spensermcconnell/__Active_Code/forge`

Implements from `PLAN.md`:

- locked decisions
- exact M1 file scope
- hard invariants
- parallelization window after field/literal freeze

Must not do:

- any code edits
- any merge
- any scope expansion

Acceptance checklist:

- `interface-lock.md` reflects `PLAN.md`
- worker ownership is explicit and non-overlapping
- launch packets cite only `PLAN.md` and `interface-lock.md`
- `task-board.md` marks `M1-T02` and `M1-T03` as `ready`

### M1-T02 Worker A: Contract / Schema / Docs Lane

Worker profile:

- model: `GPT-5.4`
- `reasoning_effort=high`

Owner files only:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py`
- `/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py`

Implements from `PLAN.md`:

- contract update in `contracts.py`
- schema helper in `schemas.py`
- contract-doc subsection in `docs/analysis_review_contract.md`
- contract/doc assertions in `tests/test_harness_analysis_contract.py`

Must not touch:

- `runner.py`
- `semantic_validation.py`
- runner tests
- prompt/reporting/example/public-surface files

Acceptance checklist:

- `TrustReviewPolicy.execution_mode` added with allowed literals
- default is `legacy_full_review`
- `to_dict()` serializes `execution_mode`
- strategy contract serialization includes the field without changing runtime
  behavior
- `bounded_attestation_input_schema()` exists
- `analysis_review_schema()` unchanged
- new schema uses `additionalProperties = False` at each new object layer
- docs state:
  - runner-owned
  - not a public deliverable
  - M1 emits it
  - M2 consumes it later
  - publication truth is excluded
  - `analysis_review_schema()` is unchanged in M1
- `tests/test_harness_analysis_contract.py` passes
- handoff file written to `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/handoffs/M1-T02.md`

### M1-T03 Worker B: Runner / Validation Lane

Worker profile:

- model: `GPT-5.4`
- `reasoning_effort=high`

Owner files only:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py`

Implements from `PLAN.md`:

- runner builder and persistence rules
- semantic validator entrypoint
- runner tests
- semantic validation tests

Must not touch:

- `contracts.py`
- `schemas.py`
- docs
- contract-doc tests
- prompt/reporting/example/public-surface files

Acceptance checklist:

- `Runner._build_bounded_attestation_input(...)` exists
- bounded mode builds from finalized bounded analysis only
- non-bounded mode returns `None`
- `bounded_review_summary` is consumed as source of truth for review-surface
  counts
- payload is assigned to `run_details["bounded_attestation_input"]`
- same payload is mirrored to top-level summary
- payload is validated before persistence
- no trust execution path consumes the payload
- semantic validator rejects:
  - missing required fields
  - wrong schema version
  - invalid `trust_execution_mode`
  - review-surface count mismatch
  - out-of-workspace refs
  - forbidden publication fields
  - recommendation ordering drift
- targeted tests pass:
  - `tests/test_harness_runner.py`
  - `tests/test_harness_semantic_validation.py`
- handoff file written to `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/handoffs/M1-T03.md`

## Dependency Ordering

1. Complete `M1-T00`.
2. Complete `M1-T01`.
3. Launch `M1-T02` and `M1-T03` in parallel.
4. Review `M1-T02` first.
5. Merge `M1-T02` first.
6. Rebase `M1-T03` onto updated `feat/bounded-work-redesign`.
7. Rerun `M1-T03` targeted tests after rebase.
8. If `M1-T03` no longer matches `interface-lock.md` after rebase, reject the
   handoff, set `M1-T03` back to `ready`, refresh the launch packet, and rerun
   the worker.
9. Merge `M1-T03`.
10. Run merged verification in `M1-T05`.
11. Stop on any blocked condition.

## Parent Review And Merge Protocol

### Pre-Merge Review For Any Worker Handoff

Parent must perform all of these before merge:

1. scope diff check
2. ownership check
3. stale-plan check
4. handoff completeness check
5. targeted test output check

### Required Commands Before Merge

For `M1-T02`:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge diff --name-only feat/bounded-work-redesign...codex/bounded-work-redesign-m1-contract-docs
git -C /Users/spensermcconnell/__Active_Code/forge log --oneline -1 codex/bounded-work-redesign-m1-contract-docs
```

For `M1-T03`:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge diff --name-only feat/bounded-work-redesign...codex/bounded-work-redesign-m1-runner-validation
git -C /Users/spensermcconnell/__Active_Code/forge log --oneline -1 codex/bounded-work-redesign-m1-runner-validation
```

### Review Rules

- Reject the handoff if changed files exceed owned scope.
- Reject the handoff if commands, tests, or exit codes are missing.
- Reject the handoff if it appears to implement anything outside M1.
- Reject the handoff if `PLAN.md` changed after worker launch and the worker did
  not refresh against the new interface lock.
- Reject the handoff if the worker’s changes conflict with locked literals or
  invariants.

### Merge Order

1. merge `M1-T02`
2. rebase `M1-T03`
3. rerun `M1-T03` targeted tests
4. merge `M1-T03`

### Post-`M1-T02` Rebase Protocol For `M1-T03`

After `M1-T02` merges, parent requires:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge/.worktrees/bounded-work-redesign-m1-runner-validation fetch origin
git -C /Users/spensermcconnell/__Active_Code/forge/.worktrees/bounded-work-redesign-m1-runner-validation rebase feat/bounded-work-redesign
poetry run pytest -q tests/test_harness_runner.py tests/test_harness_semantic_validation.py
```

If rebase changes the interface assumptions and `M1-T03` no longer matches
`interface-lock.md`:

- do not merge
- mark `M1-T03` as `ready`
- record the mismatch in `blocked/M1-T03.md` or `merge-log.md`
- relaunch `M1-T03` against the refreshed merged branch

### Narrow Integration-Conflict Rule

Parent may edit only in-scope files, and only to reconcile already-approved
`PLAN.md` behavior during merge or rebase fallout. Parent may not use
integration cleanup to add new behavior, widen scope, or touch out-of-scope
files.

## Context-Control Rules

1. Subagents receive only:
   - `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`
   - `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/interface-lock.md`
   - their owned files
   - minimal adjacent excerpts needed for imports or call sites
2. Subagents must not use the repository `ORCH_PLAN.md` as context.
3. Subagents must not inspect or edit prompt, reporting, example, README, or
   other public-surface files.
4. Additional context is parent-supplied and minimal.
5. Any suspicion that broader repo changes are required is a stop condition, not
   an invitation to explore.

## Tests And Acceptance

### Per-Lane Minimum Test Commands

`M1-T02`:

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py
```

`M1-T03`:

```bash
poetry run pytest -q tests/test_harness_runner.py tests/test_harness_semantic_validation.py
```

### Parent Merged Test Commands

```bash
poetry run pytest -q tests/test_harness_runner.py tests/test_harness_semantic_validation.py tests/test_harness_analysis_contract.py
poetry run pytest -q
```

### Final Merged Verification Checklist

Record in `/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/verification.md`:

- `M1-T02` merged with owned-scope check passed
- `M1-T03` rebased after `M1-T02`
- `M1-T03` targeted tests rerun after rebase
- merged targeted M1 test suite passed
- full suite passed, or explicit blocked evidence recorded
- no prompt changes landed
- no reporting changes landed
- no example strategy changes landed
- no README or public-surface changes landed
- no `analysis_review_schema()` change landed
- no trust-consumption logic landed
- summary mirror behavior verified
- existing legacy trust behavior unchanged
- existing bounded final artifacts unchanged

## Blocked-Path Behavior

Write blocked artifacts under:

`/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/blocked/`

Each blocked artifact must include:

- task ID
- actor
- exact stop condition
- files involved
- evidence
- whether retry is possible without scope change

Use blocked status for any of these:

- in-scope file dirty before launch
- out-of-scope file required
- `PLAN.md` changed mid-flight
- targeted tests fail and the lane cannot resolve inside scope
- full-suite failures are unrelated or ambiguous
- rebase invalidates worker assumptions
- ownership or interface-lock violation

## Stop Conditions

Stop and surface evidence to the user if any of these occur:

1. any in-scope file is already dirty before launch
2. `PLAN.md` changes and the interface lock is stale
3. a worker requires out-of-scope changes
4. a worker returns a handoff that violates ownership
5. `M1-T03` no longer matches `interface-lock.md` after rebase and requires
   nontrivial replanning
6. full-suite failures are unrelated or ambiguous
7. parent cannot verify that trust execution remains unchanged
8. parent cannot verify that bounded final artifacts remain unchanged

## Completion Criteria

M1 is complete only when all of the following are true on merged branch state:

- `TrustReviewPolicy.execution_mode` exists and defaults to
  `legacy_full_review`
- `bounded_attestation_input_schema()` exists
- `analysis_review_schema()` is unchanged
- `Runner._build_bounded_attestation_input(...)` exists and emits only for
  bounded mode
- semantic validation fails loudly on malformed payloads
- top-level and `run_details` mirrors are identical when serialized
- docs describe the handoff as runner-owned, non-public, emitted in M1, and not
  yet consumed
- targeted M1 tests pass on merged state
- full suite passes, or an explicit blocked-run artifact was produced and
  surfaced to the user
- no prompt, reporting, example-strategy, README, or other public-surface
  changes landed
- no trust execution path reads `bounded_attestation_input`

## Completion Artifact

On successful close, parent writes:

`/Users/spensermcconnell/__Active_Code/forge/.codex/orch/feat-bounded-work-redesign-m1/completion-note.md`

Required contents:

- branch
- merged task SHAs
- commands run with exit codes
- targeted-suite result
- full-suite result
- explicit statement that M1 remained inside the eight-file scope
- explicit statement that trust consumption was not implemented
- explicit statement that prompts, reporting, examples, and public surfaces were
  unchanged

This plan ends at M1 completion. No M2 or M3 work starts from this document.
