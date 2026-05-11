# ORCH_PLAN: M4 Bounded Work Redesign

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Base branch: `feat/bounded-work-redesign`  
Primary source of truth: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`

This orchestration plan replaces the stale trust-cutover orchestration with the branch-accurate plan for the bounded work redesign.

What this branch must deliver:

- keep `adjudicate` and `deliberate` public paths unchanged
- change only initial deliberate seam handling
- when the probe already surfaced a threshold-valid narrower seam candidate and the selected seam is too broad, the runner should try up to two narrower shortlist candidates from `focus_probe.candidates`
- continue automatically if one narrowed candidate survives validation
- stop before proposer with actionable exhausted-refinement `no_viable_focus` plus rerun guidance if none survive
- preserve ambiguity handling, artifact deliberate behavior, and stale rerun-answer hardening
- keep the public `focus_decision` contract within `selected | clarification_requested | no_viable_focus`

This milestone is `M4A bounded-work redesign`. There is no follow-on `M4B` in this orchestration. The parent agent owns planning, sequencing, contract freeze, integration, conflict resolution, and final verification. The parent is the only integrator.

## Orchestration Runtime Policy

Parent runtime policy:

- Parent owns kickoff, interface freeze, worktree creation, worker packets, gate review, merge decisions, conflict resolution, and final acceptance.
- Parent is the only integrator.
- Parent is the only agent allowed to merge, rebase for integration, resolve conflicts, or approve scope changes.
- Parent keeps the critical path local for the runner contract, all gate reruns, and the final regression sweep.

Worker runtime policy:

- Every worker runs on `GPT-5.4` with `reasoning_effort=high`.
- Workers execute only their assigned lane, owned files, acceptance commands, and frozen invariants.
- Workers do not make scope decisions, merge decisions, or public-contract decisions.

Concurrency policy:

- Maximum concurrent worker lanes: `2`
- Default concurrency window:
  - `WS-A` runs first alone
  - `WS-B` and `WS-C` run in parallel only after `WS-A` is merged and the parent publishes `contract-freeze.md`
- Final regression is parent-only

## Hard Guards

1. `PLAN.md` is authoritative. If this file and `PLAN.md` disagree, follow `PLAN.md`.
2. Scope is limited to deliberate seam bounded refinement on the initial run only.
3. `adjudicate` behavior must remain unchanged.
4. `deliberate` public path vocabulary must remain unchanged.
5. `focus_decision.decision_state` must remain within `selected | clarification_requested | no_viable_focus`.
6. `focus_decision.question` contract must remain unchanged.
7. Do not touch `anvil/harness/prompts.py`.
8. Do not touch `anvil/harness/schemas.py`.
9. Do not touch `tests/test_harness_semantic_validation.py`.
10. Do not touch `tests/test_harness_prompt_consistency.py`.
11. Refinement applies only when all eligibility conditions from `PLAN.md` hold:
   - `gate_path == deliberate`
   - `focus_type == seam`
   - `decision_state == selected`
   - `focus_gate_answer is None`
   - `focus_probe` exists and `_resolve_focus_probe_state(...)` returned a threshold-valid winner
   - `selected_focus_id` already matches the runner-computed valid winner
   - the selected seam is broad under the locked broadness triggers
12. True probe ambiguity must stay on the current clarification or `no_viable_focus` path. This milestone does not change probe thresholds or auto-pick from ambiguous shortlists.
13. Retry budget is hard-capped at `2` narrowed seam attempts.
14. Refinement candidates must come from `focus_probe.candidates`, not from the public `focus_decision.candidates`, not from a new search, and not from a new provider call.
15. No second probe stage, no second deliberate prompt, and no recursive search loop may be introduced.
16. Broadness and ambiguity are separate concepts in both code and docs.
17. Metadata must stay runner-owned under `run_details.focus_refinement` and, for blocked exhausted runs, mirrored under `failure_details.focus_refinement`.
18. Exhausted broad-seam refinement must normalize to actionable `no_viable_focus` with ranked rerun guidance, not a fake clarification question.
19. Artifact deliberate behavior must remain unchanged.
20. Stale rerun-answer hardening must remain unchanged.
21. Prompt or schema widening is out of scope. If required, stop and reopen planning.
22. The parent is the only integrator and the only agent allowed to merge, rebase for integration, resolve conflicts, or change lane ownership.

## Parent Critical Path

The parent owns the critical path and advances phases in order.

| Phase | Tasks | Owner | Mode | Exit Gate |
|---|---|---|---|---|
| Phase A: Kickoff and Freeze | `task/m4-a1` to `task/m4-a5` | Parent | Strictly serialized | Invariants, state root, worktrees, and launch packets frozen |
| Phase B: Runner Core and Contract Freeze | `task/m4-b1` | WS-A under parent control | Strictly serialized | `gate/m4a-runner-contract` |
| Phase C: Parallel Dependent Lanes | `task/m4-c1`, `task/m4-c2` | WS-B and WS-C | Parallel after Phase B | `gate/m4a-reporting`, `gate/m4a-docs-acceptance` |
| Phase D: Parent Integration | `task/m4-d1` to `task/m4-d4` | Parent | Strictly serialized | Integrated tree matches scope and all lane gates rerun cleanly |
| Phase E: Final Regression and Acceptance | `task/m4-e1` to `task/m4-e3` | Parent | Strictly serialized | `gate/m4a-targeted-regressions`, `gate/m4a-acceptance`, `gate/m4-complete` |

### Launch Order

1. `task/m4-a1-read-authority`
2. `task/m4-a2-freeze-invariants`
3. `task/m4-a3-create-state-root`
4. `task/m4-a4-create-worktrees`
5. `task/m4-a5-dispatch-ws-a`
6. `task/m4-b1-runner-refinement-core`
7. Parent reviews `WS-A`, reruns the gate, merges it, and writes `contract-freeze.md`
8. Dispatch `WS-B` and `WS-C` in parallel
9. Merge `WS-B`
10. Merge `WS-C`
11. Run parent-only final regression and acceptance sweep

### Merge Order

The merge order is fixed:

1. `WS-A` runner refinement core
2. `WS-B` report rendering
3. `WS-C` docs and acceptance surfaces
4. Parent-only final regression and acceptance on the integrated tree

### Phase Tasks

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/m4-a1-read-authority` | Re-read `PLAN.md`, current `ORCH_PLAN.md`, and the minimum affected repo surfaces | Parent | Parent can restate branch boundaries exactly |
| `task/m4-a2-freeze-invariants` | Freeze ownership, forbidden surfaces, retry budget, contract boundary, lane gates, and blocker protocol | Parent | `invariants.md` written |
| `task/m4-a3-create-state-root` | Create repo-local orchestration state root and sentinel layout | Parent | State root exists and is initialized |
| `task/m4-a4-create-worktrees` | Create sibling worktrees and branches | Parent | All planned worktrees exist and are clean |
| `task/m4-a5-dispatch-ws-a` | Write and issue the narrow WS-A handoff packet | Parent | WS-A dispatched |
| `task/m4-b1-runner-refinement-core` | Land runner helpers, deliberate hardening rewrite, and metadata persistence | WS-A | `gate/m4a-runner-contract` |
| `task/m4-c1-report-rendering` | Render refined success and exhausted refinement truthfully in `REPORT.md` output | WS-B | `gate/m4a-reporting` |
| `task/m4-c2-docs-and-acceptance` | Align contract docs, live acceptance manifests, and acceptance tests to the new deliberate behavior | WS-C | `gate/m4a-docs-acceptance` |
| `task/m4-d1-merge-ws-a` | Merge WS-A and rerun its gate in the integration worktree | Parent | WS-A merged |
| `task/m4-d2-refresh-ws-b-and-ws-c-if-needed` | Rebase or reopen dependent lanes if merged WS-A changed any frozen strings or scenario names | Parent | Dependent lanes confirmed against merged A |
| `task/m4-d3-merge-ws-b` | Merge reporting lane and rerun its gate | Parent | WS-B merged |
| `task/m4-d4-merge-ws-c` | Merge docs/acceptance lane and rerun its gate | Parent | WS-C merged |
| `task/m4-e1-targeted-regression-sweep` | Run the required targeted validation commands on the integrated tree | Parent | `gate/m4a-targeted-regressions` |
| `task/m4-e2-acceptance-checklist-review` | Verify the branch against the full acceptance checklist from `PLAN.md` | Parent | `gate/m4a-acceptance` |
| `task/m4-e3-final-verdict` | Record green or blocked milestone verdict | Parent | `gate/m4-complete` |

## Orchestration State and Source of Truth

The parent maintains one repo-local orchestration state root for the full run:

- `.runs/m4-bounded-work-redesign-orch/`

Required layout:

- `.runs/m4-bounded-work-redesign-orch/queue.md`
- `.runs/m4-bounded-work-redesign-orch/state.json`
- `.runs/m4-bounded-work-redesign-orch/invariants.md`
- `.runs/m4-bounded-work-redesign-orch/contract-freeze.md`
- `.runs/m4-bounded-work-redesign-orch/session.log`
- `.runs/m4-bounded-work-redesign-orch/handoffs/`
- `.runs/m4-bounded-work-redesign-orch/gates/`
- `.runs/m4-bounded-work-redesign-orch/logs/`
- `.runs/m4-bounded-work-redesign-orch/sentinels/`
- `.runs/m4-bounded-work-redesign-orch/acceptance/`

### File Roles

- `queue.md`
  - Canonical task table with one row per `task/m4-*`
  - Tracks owner, state, gate, reopen reason, and merge status
- `state.json`
  - Current phase, active lanes, branch names, blockers, merge state, and final verdict
- `invariants.md`
  - Frozen scope, ownership boundaries, forbidden surfaces, commands, and gate definitions
- `contract-freeze.md`
  - Parent-accepted `focus_refinement` payload shape and canonical strings after WS-A gate
  - Authoritative source for WS-B and WS-C before they start work
- `session.log`
  - Parent-only sequential log of dispatches, readiness, blockers, merges, reopen events, and final decisions
- `handoffs/task-m4-*.md`
  - Narrow worker packet plus parent-accepted return summary for each lane
- `gates/*.md`
  - Parent gate results with exact commands and verdicts
- `acceptance/`
  - Final command outputs, acceptance notes, and any rerun guidance wording snapshots used during review

### Frozen Contract Snapshot

`contract-freeze.md` must capture the runner contract that downstream lanes rely on. At minimum it must freeze:

- `focus_refinement` top-level keys
- accepted `status` values
- accepted `trigger_reason` values
- accepted `rejected_candidates.reason` values
- exhausted rerun-guidance rendering expectations
- any parent-approved scenario names used by acceptance surfaces

The target shape is the one described in `PLAN.md`:

- `status`
- `trigger_reason`
- `source_selected_focus_id`
- `source_selected_focus_paths`
- `candidate_shortlist_ids`
- `attempted_candidate_ids`
- `rejected_candidates`
- `selected_candidate_id`
- `selected_candidate_paths`
- `exhausted_reason`
- `rerun_guidance`

### Sentinel Conventions

Per-task sentinels live under:

- `.runs/m4-bounded-work-redesign-orch/sentinels/`

Required sentinel names:

- `task-m4-*.dispatched`
- `task-m4-*.ready`
- `task-m4-*.blocked`
- `task-m4-*.merged`
- `task-m4-*.failed-gate`

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

The parent does not broad-poll worktrees or inspect full worker reasoning transcripts.

The parent waits on:

- sentinel changes
- narrow handoff completion
- explicit blocker notes
- gate reruns in the integration worktree

## Worktree and Branch Plan

Integration worktree:

- Path: `/Users/spensermcconnell/__Active_Code/forge`
- Branch: `feat/bounded-work-redesign`
- Owner: Parent only

Sibling worktree root:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/`

Lane worktrees:

- `WS-A`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/ws-a-runner-core`
  - Branch: `feat/bounded-work-redesign-ws-m4a-runner-core`
- `WS-B`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/ws-b-reporting`
  - Branch: `feat/bounded-work-redesign-ws-m4a-reporting`
- `WS-C`
  - Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/ws-c-docs-acceptance`
  - Branch: `feat/bounded-work-redesign-ws-m4a-docs-acceptance`

There is no separate worker worktree for final regression. Final regression is parent-only and runs in the integration worktree.

### Worktree Creation Commands

```bash
mkdir -p /Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/ws-a-runner-core \
  -b feat/bounded-work-redesign-ws-m4a-runner-core \
  feat/bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/ws-b-reporting \
  -b feat/bounded-work-redesign-ws-m4a-reporting \
  feat/bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m4-bounded-work-redesign/ws-c-docs-acceptance \
  -b feat/bounded-work-redesign-ws-m4a-docs-acceptance \
  feat/bounded-work-redesign
```

### Worktree Rules

- The parent is the only integrator.
- Workers never merge peer branches.
- Workers never rebase peer changes into their own lane without parent instruction.
- Parent resolves every merge or rebase in the integration worktree only.
- If a lane needs a peer-owned change, it raises a blocker instead of editing that file.
- `WS-B` and `WS-C` do not launch until the parent has published `contract-freeze.md`.
- The critical path stays local in the integration worktree for all gates, merges, and final verification.

## Blocker, Interface-Change, and Conflict Protocols

### Blocker Protocol

A worker must mark `.blocked` and stop when any of these occur:

- it needs a peer-owned file change
- it detects scope drift beyond its lane
- it cannot satisfy its lane gate without touching a forbidden surface
- the runner contract is not frozen and the lane depends on it
- a failing test suggests public contract widening or prompt/schema edits

Required blocker return:

- exact file or interface requested
- exact reason
- exact minimal parent decision needed
- exact command or test demonstrating the blocker, if relevant

### Interface-Change Protocol

For this milestone, interface changes include:

- changing the public `focus_decision` contract
- changing any prompt or schema surface
- changing the accepted `focus_refinement` payload shape after freeze
- inventing new `trigger_reason`, rejection-reason, or rerun-guidance wording after WS-A freeze
- changing scenario names consumed by acceptance tests after WS-A freeze without parent approval

Worker behavior:

- do not implement interface changes speculatively
- raise `.blocked`
- wait for a revised parent packet

### Conflict Protocol

Conflict type: textual overlap

- Example: two lanes touch the same test file by accident.
- Resolution: parent reassigns ownership or serializes the edit.
- Workers do not self-resolve peer overlap.

Conflict type: contract drift

- Example: WS-B needs a field name or status token that differs from merged WS-A.
- Resolution: parent compares against `PLAN.md` and `contract-freeze.md`, then reopens the affected lane or rewrites the freeze packet.
- Workers do not invent fallback heuristics.

Conflict type: scope drift

- Example: a lane starts modifying ambiguity thresholds, artifact behavior, or stale rerun-answer logic.
- Resolution: stop immediately, mark blocked, and return the smallest drift summary.
- Parent either rejects the drift or explicitly re-plans. It does not merge “close enough” drift.

Conflict type: merge drift after WS-A lands

- Example: WS-C started from the frozen contract but WS-A landed with renamed scenario strings.
- Resolution: parent rebases or reopens WS-C before merge.
- `WS-B` and `WS-C` do not independently reinterpret merged `WS-A`.

## Workstream Plan

### WS-A: Runner Refinement Core

Task ID:

- `task/m4-b1-runner-refinement-core`

Owner:

- Worker `WS-A`
- Parent controls dispatch, contract freeze, integration, and acceptance

Owned files:

- `anvil/harness/runner.py`
- `tests/test_harness_runner.py`

Files explicitly not owned by WS-A:

- `anvil/harness/report.py`
- `docs/analysis_review_contract.md`
- `examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`
- `examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml`
- `tests/test_harness_reporting.py`
- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_harness_example_strategy_wiring.py`
- all forbidden surfaces listed in Hard Guards

Required changes:

- add runner-owned private helpers in `runner.py`
- rewire `_normalize_focus_gate_decision_for_policy(...)` for deliberate seam broadness handling
- keep stale-answer handling unchanged
- keep ambiguous probe blocking unchanged
- keep artifact deliberate blocking unchanged
- attempt at most two narrowed shortlist candidates from `focus_probe.candidates`
- replace the selected seam with the narrowed seam on success
- persist `focus_refinement` metadata into run details and blocked failure details on exhaustion
- add runner assertions for:
  - refined success
  - candidate A failure followed by candidate B success
  - exhausted refinement
  - `clarification_policy=never_ask` still auto-refines when no operator input is needed
  - unchanged ambiguity behavior
  - unchanged artifact deliberate behavior
  - unchanged stale-answer hardening

Lane command:

```bash
poetry run pytest -q tests/test_harness_runner.py -k "focus_gate"
```

`gate/m4a-runner-contract` is green only when all of these are true:

- the lane command is green
- no forbidden surfaces were touched
- no second provider call or recursive refinement loop exists
- broadness and ambiguity remain separate code paths
- retry budget is hard-capped at `2`
- selected narrowed seams replace the canonical selected `focus_decision`
- exhausted refinement produces runner-owned rerun guidance under `focus_refinement`
- the parent can write `contract-freeze.md` with the actual landed payload shape and canonical string tokens

### WS-B: Report Rendering

Task ID:

- `task/m4-c1-report-rendering`

Owner:

- Worker `WS-B`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `anvil/harness/report.py`
- `tests/test_harness_reporting.py`

Files explicitly not owned by WS-B:

- `anvil/harness/runner.py`
- `docs/analysis_review_contract.md`
- `examples/harness/live_acceptance/`
- `tests/test_harness_runner.py`
- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_harness_example_strategy_wiring.py`

Required changes:

- render when deliberate auto-refined and continued
- render trigger reason and relevant attempted or rejected candidates when useful
- render exhausted refinement as actionable rerun guidance
- never render a fake clarification prompt for exhausted refinement
- preserve correct stale `no_viable_focus` rendering
- source rendering from persisted `focus_refinement` metadata, not from heuristic inference

Lane command:

```bash
poetry run pytest -q tests/test_harness_reporting.py -k "focus_decision or no_viable_focus or clarification"
```

`gate/m4a-reporting` is green only when all of these are true:

- the lane command is green
- rendering matches `contract-freeze.md`
- refined success reads as intentional and explicit
- exhausted refinement reads as actionable and truthful
- stale or true-ambiguity rendering is not regressed

### WS-C: Docs and Acceptance Surfaces

Task ID:

- `task/m4-c2-docs-and-acceptance`

Owner:

- Worker `WS-C`
- Parent controls dispatch, integration, and acceptance

Owned files:

- `docs/analysis_review_contract.md`
- `examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`
- `examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml`
- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_harness_example_strategy_wiring.py`

Files explicitly not owned by WS-C:

- `anvil/harness/runner.py`
- `anvil/harness/report.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`
- all forbidden surfaces listed in Hard Guards

Required changes:

- describe deliberate seam behavior precisely as:
  - probe
  - deliberate decision
  - bounded internal broad-seam refinement
  - exhausted rerun-guidance fallback
- add acceptance expectations for one refined-success seam deliberate scenario
- add acceptance expectations for one exhausted-refinement seam deliberate scenario
- keep artifact deliberate acceptance expectations unchanged
- align scenario names and rerun-guidance wording to `contract-freeze.md`
- keep wiring tests honest with the updated acceptance surfaces

Lane commands:

```bash
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

`gate/m4a-docs-acceptance` is green only when all of these are true:

- both lane commands are green
- docs describe the deliberate behavior precisely and do not imply every block is a clarification prompt
- acceptance manifests cover refined success and exhausted refinement
- artifact deliberate expectations remain unchanged
- WS-C did not invent contract strings or scenario names outside `contract-freeze.md`

## Context-Control Rules

### Parent Live Context Policy

Parent keeps only a narrow live set of artifacts in active context:

- `PLAN.md`
- `ORCH_PLAN.md`
- `invariants.md`
- `contract-freeze.md`
- `queue.md`
- `state.json`
- the active lane handoff packet
- the active lane’s narrow diff summary
- the active gate result being reviewed

Parent does not keep full worker transcripts in live context once a narrow handoff has been accepted.

### Worker Packet Policy

Each worker packet contains only:

- task ID
- owned file list
- relevant `PLAN.md` excerpt for that lane
- exact acceptance commands
- frozen contract or naming decisions already made by the parent
- forbidden surfaces list
- blocker protocol

Worker packets do not include:

- unrelated repo summaries
- other lanes’ transcripts
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

- full worker reasoning transcript
- broad repo-wide diff for a lane that only owns a few files
- peer lane internals unless a blocker requires it

## Repo Tests and Acceptance

### 1. Targeted Regression Sweep

Run on the integrated tree.

Required commands:

```bash
poetry run pytest -q tests/test_harness_runner.py -k "focus_gate"
poetry run pytest -q tests/test_harness_reporting.py -k "focus_decision or no_viable_focus or clarification"
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

`gate/m4a-targeted-regressions` is green only when every command above passes.

### 2. Acceptance Checklist

The branch is done only when all of these are true:

- deliberate seam refinement can continue automatically on a narrowed shortlisted seam
- candidate A failure can still fall through to candidate B success
- exhausted refinement stops before proposer with ranked rerun guidance
- exhausted refinement renders as actionable `no_viable_focus`, not a fake clarification question
- close-contest ambiguity still blocks under the existing rules
- artifact deliberate still blocks
- stale rerun-answer hardening still blocks
- `REPORT.md` tells the truth in both refined-success and exhausted-refinement cases
- contract docs describe the new deliberate behavior precisely
- the targeted regression commands are green

### 3. Parent Acceptance Review

Parent acceptance review must also verify:

- only the minimum complete implementation surfaces from `PLAN.md` changed:
  - `anvil/harness/runner.py`
  - `anvil/harness/report.py`
  - `docs/analysis_review_contract.md`
  - `examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`
  - `examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml`
  - `tests/test_harness_runner.py`
  - `tests/test_harness_reporting.py`
  - `tests/test_run_focus_gate_acceptance.py`
  - `tests/test_harness_example_strategy_wiring.py`
- no forbidden surfaces changed
- no public contract widening slipped in through tests or docs
- rerun guidance is copyable and grounded in ranked shortlist candidates
- the integrated diff still matches the branch goal of deliberate seam bounded refinement only

### 4. Green Conditions

`gate/m4-complete` is green only when all of these are true:

- `gate/m4a-runner-contract` is green
- `gate/m4a-reporting` is green
- `gate/m4a-docs-acceptance` is green
- `gate/m4a-targeted-regressions` is green
- `gate/m4a-acceptance` is green
- the integrated tree preserved:
  - unchanged ambiguity thresholds
  - unchanged artifact deliberate behavior
  - unchanged stale rerun-answer hardening
  - unchanged public `focus_decision` contract

## Assumptions

- The working integration branch remains `feat/bounded-work-redesign` for the duration of the run.
- `PLAN.md` remains the single authoritative product and implementation spec.
- `focus_probe.candidates` already carries enough shortlist data to rank narrowed seam attempts without a new provider call.
- The required implementation remains confined to the nine surfaces listed in `PLAN.md`.
- Live acceptance manifests are test and documentation surfaces for this milestone, not a reason to widen runtime behavior.
- Parent has permission to create sibling worktrees under `/Users/spensermcconnell/__Active_Code/forge.worktrees/` and local run state under `.runs/`.
- If unexpected overlap appears outside the declared lane ownership, the parent will serialize the work rather than expand scope.
- The targeted validation commands from `PLAN.md` are the required milestone gate. Broader repo validation is optional unless those commands expose bleed outside this slice.
