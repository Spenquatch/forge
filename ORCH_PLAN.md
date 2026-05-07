# ORCH_PLAN: Trust Attestation Over Bounded Output (M2)

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Base branch: `feat/bounded-work-redesign`  
Primary source of truth: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`

This orchestration plan is for the parent coding agent to execute M2 end to end without improvising the orchestration model. The parent owns the critical path, owns all merges, owns conflict resolution, owns final verification, and is the only integrator.

M2 outcome to deliver:

- `analysis_review_trust_v1` remains the public trust strategy kind.
- `trust_review.execution_mode` becomes the real strategy-level cutover knob.
- `legacy_full_review` preserves current trust behavior.
- `attestation_over_bounded` runs the bounded producer first, freezes `bounded_attestation_input`, then runs one trust attestation review over that frozen object.
- In attestation mode, `final_analysis` comes from the bounded producer.
- No second trust-authored `final_analysis` is created.
- `apply_final_artifacts(summary)` and reporting/artifact selection remain unchanged in M2.

Repo-specific implementation surfaces:

- `anvil/harness/types.py`
- `anvil/harness/contracts.py`
- `anvil/harness/runner.py`
- `anvil/harness/prompts.py`
- `anvil/harness/semantic_validation.py`
- `docs/analysis_review_contract.md`
- `examples/harness/strategies/analysis_review_trust_attestation_codex_claude.yaml`
- `examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml`
- `examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml`
- `tests/test_harness_runner.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`
- `tests/test_harness_analysis_contract.py`

## Hard Guards

1. `PLAN.md` is authoritative. If this plan and `PLAN.md` disagree, follow `PLAN.md`.
2. M2 only. Do not rewrite reporting, artifact selection, README product framing, or publication semantics.
3. The public trust strategy kind stays `analysis_review_trust_v1`.
4. Use `trust_review.execution_mode` as the only cutover knob. Do not add task-level, runner-only, or duplicate knobs.
5. `legacy_full_review` must preserve current trust behavior.
6. `attestation_over_bounded` must reuse bounded production and bounded `final_analysis`.
7. No second trust-authored `final_analysis` is allowed in attestation mode.
8. `anvil/harness/runner.py` is single-owner work. It stays in one lane only.
9. The parent agent is the only integrator. Workers do not merge, rebase peer branches, or resolve peer conflicts.
10. Existing trust YAMLs remain legacy. Add new attestation examples instead of mutating the current trust example surface.
11. If work appears to require changes in `anvil/harness/report.py` or `anvil/harness/reporting.py`, stop and prove the regression first.
12. If a proposed conflict resolution would imply architecture drift from `PLAN.md`, do not resolve creatively. Stop and escalate to the parent for a spec check.
13. The current working-tree state on `feat/bounded-work-redesign`, including the edited `PLAN.md`, is treated as intentional and must not be overwritten.

## Parent Critical Path

The parent owns these phases and advances them in order.

| Phase | Tasks | Owner | Mode |
|---|---|---|---|
| Phase A: Kickoff And Freeze | `task/m2-a1` to `task/m2-a4` | Parent | Strictly serialized |
| Phase B: Prerequisite Contract Surface | `task/m2-b1` | Worker, parent-controlled | Strictly serialized |
| Phase C: Parallel Non-Runner Lanes | `task/m2-c1`, `task/m2-c2` | Workers, parent-controlled | Parallel after Phase B is green |
| Phase D: Runner Cutover | `task/m2-d1` | Worker, parent-controlled | Strictly serialized after `task/m2-c1` |
| Phase E: Integration | `task/m2-e1` to `task/m2-e4` | Parent | Strictly serialized |
| Phase F: Final Verification | `task/m2-f1` to `task/m2-f3` | Parent | Strictly serialized |
| Phase G: Completion Or Block | `task/m2-g1` | Parent | Terminal |

### Phase A: Kickoff And Freeze

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/m2-a1-read-plan` | Re-read `PLAN.md` locked decisions, file plan, tests, worktree strategy, done criteria | Parent | Parent can restate M2 invariants from source |
| `task/m2-a2-freeze-interfaces` | Freeze the contract/prompt/runner invariants workers must honor | Parent | Frozen interface packet written to orchestration state |
| `task/m2-a3-create-state-root` | Create the parent run-state/checklist/log layout under `.runs/` | Parent | Queue and sentinel layout initialized |
| `task/m2-a4-create-worktrees` | Create lane worktrees and branches under one common root | Parent | All lane worktrees exist and are clean |

### Phase B: Prerequisite Contract Surface

| Task ID | Purpose | Owner | Depends On | Gate |
|---|---|---|---|---|
| `task/m2-b1-contract-surface` | Make `trust_review.execution_mode` real in parsing and contract resolution | WS-B1 | Phase A | Contract surface tests pass and parent freezes final field shape |

### Phase C: Parallel Non-Runner Lanes

| Task ID | Purpose | Owner | Depends On | Mode | Gate |
|---|---|---|---|---|---|
| `task/m2-c1-prompt-validation-surface` | Add attestation prompt path and attestation semantic validation | WS-C1 | `task/m2-b1` | Parallel | Prompt and semantic validation tests pass |
| `task/m2-c2-docs-examples` | Add execution-mode docs and additive attestation example YAMLs | WS-C2 | `task/m2-b1` | Parallel | Docs/examples are additive and accurate |

### Phase D: Runner Cutover

| Task ID | Purpose | Owner | Depends On | Gate |
|---|---|---|---|---|
| `task/m2-d1-runner-cutover` | Split trust execution modes, run bounded producer first, consume frozen handoff, preserve final artifact behavior | WS-D1 | `task/m2-b1`, `task/m2-c1` | Runner tests prove real cutover and no second trust-authored final analysis |

### Phase E: Integration

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/m2-e1-integrate-b1` | Merge contract surface lane into integration worktree | Parent | Parent reruns B1 gate cleanly |
| `task/m2-e2-integrate-c1-c2` | Merge prompt/validation and docs/examples lanes | Parent | Parent reruns C1 gates and verifies additive docs/examples |
| `task/m2-e3-integrate-d1` | Merge runner lane last among implementation lanes | Parent | Parent reruns D1 gate cleanly |
| `task/m2-e4-integration-review` | Review integrated diff against `PLAN.md` invariants | Parent | No architecture drift found |

### Phase F: Final Verification

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/m2-f1-targeted-test-gates` | Run the exact targeted commands from `PLAN.md` | Parent | All commands pass |
| `task/m2-f2-parity-gate` | Confirm required parity coverage for seam/artifact and adjudicate/deliberate paths | Parent | Explicit parity checklist passes |
| `task/m2-f3-scope-guard` | Confirm no reporting/artifact-selection changes landed | Parent | No forbidden scope drift |

### Phase G: Completion Or Block

| Task ID | Purpose | Owner | Gate |
|---|---|---|---|
| `task/m2-g1-close-or-block` | Mark run complete or blocked with exact reason and reopen point | Parent | Terminal decision recorded |

## Orchestration State And Source Of Truth

The parent maintains one repo-local orchestration state root for the whole run:

- `.runs/m2-attestation-orch/`

The parent uses this directory as the operational source of truth for queue state, handoffs, sentinels, and final gate records.

Recommended layout:

- `.runs/m2-attestation-orch/queue.md`
- `.runs/m2-attestation-orch/state.json`
- `.runs/m2-attestation-orch/interface-freeze.md`
- `.runs/m2-attestation-orch/tasks/`
- `.runs/m2-attestation-orch/handoffs/`
- `.runs/m2-attestation-orch/sentinels/`
- `.runs/m2-attestation-orch/logs/`
- `.runs/m2-attestation-orch/gates/`

Parent-owned artifact rules:

- `queue.md` is the canonical checklist with one row per `task/m2-*`.
- `state.json` tracks current phase, active lanes, blockers, and merge status.
- `interface-freeze.md` records the exact frozen interface packet workers must honor.
- `handoffs/task-m2-*.md` stores the worker packet the parent issued and the narrow worker return summary the parent accepted.
- `gates/final-verification.md` records the exact command outcomes and parity checklist.

Per-task sentinels:

- `.runs/m2-attestation-orch/sentinels/task-m2-*.dispatched`
- `.runs/m2-attestation-orch/sentinels/task-m2-*.ready`
- `.runs/m2-attestation-orch/sentinels/task-m2-*.blocked`
- `.runs/m2-attestation-orch/sentinels/task-m2-*.merged`
- `.runs/m2-attestation-orch/sentinels/task-m2-*.failed-gate`

Parent wait protocol:

- The parent waits on sentinel changes, not tight polling of full branch state.
- A worker reaching its acceptance gate emits or reports readiness for `.ready`.
- A worker that cannot continue emits or reports `.blocked` with a concise blocker note.
- The parent marks `.merged` only after integration and gate re-run in the integration worktree.
- If a post-integration gate fails, the parent marks `.failed-gate` on the originating task before reopening it.

## Worktree And Branch Plan

### Named Worktrees

Integration worktree:

- `wt/m2-integration`
- Path: `/Users/spensermcconnell/__Active_Code/forge`
- Branch: `feat/bounded-work-redesign`
- Owner: Parent only

Common root for sibling lane worktrees:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/`

Lane worktrees under that root:

- `wt/m2-b1-contract`
- Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-b1-contract`
- Branch: `feat/bounded-work-redesign-ws-b1-contract`

- `wt/m2-c1-prompt-validation`
- Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-c1-prompt-validation`
- Branch: `feat/bounded-work-redesign-ws-c1-prompt-validation`

- `wt/m2-c2-docs-examples`
- Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-c2-docs-examples`
- Branch: `feat/bounded-work-redesign-ws-c2-docs-examples`

- `wt/m2-d1-runner`
- Path: `/Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-d1-runner`
- Branch: `feat/bounded-work-redesign-ws-d1-runner`

### Worktree Creation Commands

Parent-only commands:

```bash
mkdir -p /Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-b1-contract \
  -b feat/bounded-work-redesign-ws-b1-contract \
  feat/bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-c1-prompt-validation \
  -b feat/bounded-work-redesign-ws-c1-prompt-validation \
  feat/bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-c2-docs-examples \
  -b feat/bounded-work-redesign-ws-c2-docs-examples \
  feat/bounded-work-redesign

git -C /Users/spensermcconnell/__Active_Code/forge worktree add \
  /Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-d1-runner \
  -b feat/bounded-work-redesign-ws-d1-runner \
  feat/bounded-work-redesign
```

### Worktree Rules

- The parent is the only integrator.
- Workers never merge peer branches.
- Workers never rebase peer work into their lane without explicit parent instruction.
- `runner.py` work happens only in `wt/m2-d1-runner`.
- If a worker needs a peer-owned file change, it requests an interface change through the parent instead of editing that file.

## Workstream Plan

### WS-B1: Strategy + Contract Surface

Task ID:

- `task/m2-b1-contract-surface`

Owner:

- Worker `WS-B1`
- Parent controls dispatch, review, integration, and acceptance

Owned files:

- `anvil/harness/types.py`
- `anvil/harness/contracts.py`
- `tests/test_harness_analysis_contract.py`

Required changes:

- Add typed strategy parsing for `trust_review.execution_mode`.
- Permit only `legacy_full_review` and `attestation_over_bounded`.
- Reject unknown keys under `trust_review`.
- Round-trip `trust_review.execution_mode` through `StrategyConfig.to_dict()`.
- Make `build_analysis_review_contract(...)` source the execution mode from parsed strategy config.
- Preserve default `legacy_full_review`.
- Preserve bounded and legacy serialization behavior.
- Preserve `effective_strategy`.

Parent dispatch commands:

```bash
git -C /Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/ws-b1-contract status --short
```

Worker-local acceptance commands:

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"
```

Acceptance gate:

- Strategy parsing accepts and round-trips `trust_review.execution_mode`.
- Default remains `legacy_full_review`.
- Invalid literals and unknown keys fail loudly.
- Trust strategies can serialize `attestation_over_bounded` without changing `analysis_review_trust_v1`.

### WS-C1: Prompt + Semantic Validation Surface

Task ID:

- `task/m2-c1-prompt-validation-surface`

Owner:

- Worker `WS-C1`

Depends on:

- `task/m2-b1-contract-surface` merged or parent-frozen

Owned files:

- `anvil/harness/prompts.py`
- `anvil/harness/semantic_validation.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`

Required changes:

- Add `build_trust_attestation_review_prompt(...)`.
- Make the prompt explicitly consume `bounded_attestation_input`.
- Require dense recommendation coverage across bounded recommendation indices.
- Require direct re-checking of workspace evidence before attestation.
- Forbid replacement analysis generation.
- Add attestation-specific semantic validation keyed to the frozen handoff.
- Keep legacy trust validation behavior unchanged.

Worker-local acceptance commands:

```bash
poetry run pytest -q tests/test_harness_prompt_consistency.py -k "attestation or trust"
poetry run pytest -q tests/test_harness_semantic_validation.py -k "attestation or bounded_attestation_input"
```

Acceptance gate:

- Attestation prompt references the frozen handoff explicitly.
- Attestation prompt requires dense recommendation coverage.
- Attestation prompt forbids replacement analysis payload generation.
- Semantic validation fails missing coverage, out-of-range indices, malformed closure proof, and invalid workspace provenance.
- Legacy trust prompt and validation behavior remain green.

### WS-C2: Docs + Example Strategies

Task ID:

- `task/m2-c2-docs-examples`

Owner:

- Worker `WS-C2`

Depends on:

- `task/m2-b1-contract-surface` merged or parent-frozen

Owned files:

- `docs/analysis_review_contract.md`
- `examples/harness/strategies/analysis_review_trust_attestation_codex_claude.yaml`
- `examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml`
- `examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml`

Required changes:

- Document `trust_review.execution_mode`.
- Describe `legacy_full_review` as today’s trust lane.
- Describe `attestation_over_bounded` as trust attestation over the frozen bounded draft.
- State that publication semantics remain runner-owned and unchanged in M2.
- Add new attestation YAMLs using the current trust provider lineup unless a test proves otherwise.
- Leave existing trust YAMLs as legacy.

Worker-local acceptance commands:

```bash
git diff --stat -- docs/analysis_review_contract.md examples/harness/strategies/
```

Acceptance gate:

- Docs are accurate and scoped to M2.
- New examples are additive.
- Existing trust examples remain legacy.
- No tests or runtime files were edited by this lane.

### WS-D1: Runner Cutover

Task ID:

- `task/m2-d1-runner-cutover`

Owner:

- Worker `WS-D1`

Depends on:

- `task/m2-b1-contract-surface`
- `task/m2-c1-prompt-validation-surface`

Owned files:

- `anvil/harness/runner.py`
- `tests/test_harness_runner.py`

Required changes:

- Keep bounded mode unchanged.
- Keep trust `legacy_full_review` path unchanged.
- Add explicit trust `attestation_over_bounded` branch.
- Run focus gate once before bounded production in attestation mode.
- Reuse bounded producer flow instead of cloning it.
- Freeze and persist `bounded_attestation_input` on the final trust summary.
- Run one trust attestation review stage over the frozen handoff.
- Reuse bounded `final_analysis`.
- Prevent bounded producer review stages from contaminating final trust stage selection and provenance resolution.
- Keep `apply_final_artifacts(summary)` untouched.

Worker-local acceptance commands:

```bash
poetry run pytest -q tests/test_harness_runner.py -k "attestation or bounded_attestation_input"
```

Acceptance gate:

- Legacy trust still enters the existing full-review path.
- Attestation trust runs bounded producer first.
- Attestation trust persists and consumes the frozen handoff.
- Attestation trust reuses bounded `final_analysis`.
- Final provenance and final review-stage selection resolve from the attestation stage only.
- No second trust-authored `final_analysis` exists.

## Lane Launch And Merge Protocol

### Launch Order

1. Parent completes Phase A.
2. Parent dispatches `task/m2-b1-contract-surface`.
3. Parent waits for `task/m2-b1-contract-surface.ready`.
4. Parent integrates B1 and freezes the final contract/config surface.
5. Parent dispatches `task/m2-c1-prompt-validation-surface` and `task/m2-c2-docs-examples` in parallel.
6. Parent waits for `task/m2-c1-prompt-validation-surface.ready` and `task/m2-c2-docs-examples.ready`.
7. Parent integrates C1 and C2.
8. Parent dispatches `task/m2-d1-runner-cutover`.
9. Parent waits for `task/m2-d1-runner-cutover.ready`.
10. Parent integrates D1 last among implementation lanes.
11. Parent runs final verification.

### Parent Merge Order

- Merge B1 first.
- Merge C1 before D1.
- Merge C2 anytime after B1, but before final closeout.
- Merge D1 last among implementation lanes.

### Blocker Protocol

If a lane hits a blocker:

- The worker stops at once.
- The worker reports a narrow blocker summary and marks the task blocked.
- The worker does not broaden scope to “unstick” itself.
- The parent triages the blocker into one of three classes:
  - missing dependency from an earlier lane
  - interface ambiguity that requires a parent freeze update
  - true conflict with `PLAN.md` or repo state
- The parent either:
  - resolves the missing dependency by integrating the prerequisite lane
  - updates `interface-freeze.md` and redispatches the blocked lane
  - halts the run as blocked if the issue implies spec drift or out-of-scope work

### Interface-Change Protocol

If a worker discovers it needs a peer-owned change:

- The worker does not edit peer-owned files.
- The worker files an interface request in its handoff summary.
- The parent compares the request to `PLAN.md`.
- The parent either:
  - approves the interface update and republishes the frozen interface packet
  - rejects the request as out of scope
  - converts the request into a new parent-owned integration note if it is a merge-only concern

### Conflict Protocol

If two lanes conflict:

- The parent is the only resolver.
- The parent first decides whether the conflict is:
  - textual merge overlap only
  - interface mismatch within the current M2 architecture
  - architecture drift from `PLAN.md`
- If it is textual merge overlap only, the parent resolves it in the integration worktree and reruns the relevant lane gate.
- If it is interface mismatch, the parent updates the frozen interface and reopens the affected lane.
- If it would require a creative resolution that changes public kinds, introduces new schema families, splits runner ownership, or touches reporting semantics, do not resolve creatively. Stop, compare against `PLAN.md`, and mark the run blocked until the spec question is answered.

## Parent-Agent Integration Flow

1. Use `/Users/spensermcconnell/__Active_Code/forge` as `wt/m2-integration`.
2. Before each merge, record the queue state and confirm the incoming lane passed its worker-local gate.
3. Review only the lane’s owned-file diff plus its narrow summary before merging.
4. Integrate `task/m2-b1-contract-surface`.
5. Rerun the B1 gate in `wt/m2-integration`.
6. Update `interface-freeze.md` with the final B1 surface.
7. Integrate `task/m2-c1-prompt-validation-surface`.
8. Rerun the C1 gates in `wt/m2-integration`.
9. Integrate `task/m2-c2-docs-examples`.
10. Verify docs/examples are additive and repo-specific.
11. Integrate `task/m2-d1-runner-cutover`.
12. Rerun the D1 gate in `wt/m2-integration`.
13. Review the integrated diff against `PLAN.md` and confirm:
    - one real bounded producer
    - one real trust attestation stage
    - bounded `final_analysis` reused in attestation mode
    - no second trust-authored final analysis
    - reporting untouched
14. Only after all implementation merges are complete, run the parent final gates.
15. If any post-merge gate fails, do not patch opportunistically across multiple surfaces. Map the failure back to the owning task, mark `.failed-gate`, reopen that lane or resolve an integration-only merge artifact, and rerun the gate.

## Final Verification Flow

### Parent Final Gates

Run these exact commands in `wt/m2-integration`:

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"
poetry run pytest -q tests/test_harness_prompt_consistency.py -k "attestation or trust"
poetry run pytest -q tests/test_harness_runner.py -k "attestation or bounded_attestation_input"
poetry run pytest -q tests/test_harness_semantic_validation.py -k "attestation or bounded_attestation_input"
poetry run pytest -q tests/test_harness_reporting.py -k "apply_final_artifacts"
```

### Parity Matrix Gate

The parent must explicitly verify parity coverage, not just assume it exists. The gate is not complete until the parent can point to tests or fixtures that cover all eight combinations below:

| Focus Type | Gate Path | Mode A | Mode B | Parent Check |
|---|---|---|---|---|
| seam | adjudicate | legacy trust | attestation trust | Same `focus_decision`, same bounded candidate payload, same or stricter trust admissibility, no artifact-selection regression |
| seam | deliberate | legacy trust | attestation trust | Same gate-path behavior and same bounded candidate payload before attestation |
| artifact | adjudicate | legacy trust | attestation trust | Same artifact focus selection and unchanged final artifact semantics |
| artifact | deliberate | legacy trust | attestation trust | Same rerun/clarification behavior and unchanged bounded candidate payload before attestation |

Parent parity checklist:

- confirm the matrix is represented in tests or fixture-driven coverage
- confirm attestation mode does not alter bounded candidate generation
- confirm trust admissibility is same or stricter in attestation mode
- confirm final artifact selection remains unchanged

The parent should prefer narrow evidence from targeted diffs and relevant tests such as the existing focus-gate fixture wiring over broad transcript review.

### Scope Guard

The parent must also verify:

- `anvil/harness/report.py` unchanged
- `anvil/harness/reporting.py` unchanged
- existing trust examples remain legacy
- new attestation examples exist
- docs describe both execution modes and unchanged publication semantics

### If Final Gates Fail

If final gates fail after integration:

- classify the failure as integration-only, lane-owned, or spec-drift
- if integration-only, repair the merge artifact in `wt/m2-integration` and rerun the exact failing gate
- if lane-owned, reopen the owning task and return only the failing test evidence plus the narrow diff context
- if spec-drift, stop the run and mark blocked rather than improvising a broader redesign
- do not close the run until all final gates pass again in the integration worktree

## Context-Control Rules

### What Goes Into Each Worker Prompt

Each worker prompt must contain only:

- the task ID
- the phase and dependency state
- the lane’s exact owned files
- the exact required outcome
- the frozen interface packet from `interface-freeze.md`
- the exact commands the worker must run
- the lane’s acceptance gate
- the explicit out-of-scope list
- the exact return format required by the parent

### What Must Stay Out Of Each Worker Prompt

Each worker prompt must not include:

- repo-wide “fix anything necessary” language
- permission to touch peer-owned files
- instructions to merge, rebase, or resolve peer conflicts
- full transcripts from prior workers
- broad architectural brainstorming once `PLAN.md` is already clear
- permission to reinterpret M2 into M3

### Expected Worker Return Format

Each worker must return a narrow summary in this exact shape:

- `Task:` `task/m2-*`
- `Status:` `ready` or `blocked`
- `Files Changed:` comma-separated owned files only
- `Commands Run:` exact commands executed
- `Acceptance Gate:` `passed` or `failed`
- `Diff Summary:` 3-6 lines describing only substantive changes
- `Open Questions:` `none` or a short interface request
- `Blocker:` `none` or one concise blocker statement

### Parent Review Discipline

The parent should review:

- narrow diffs for owned files
- `git diff --stat`
- the worker’s acceptance command results
- targeted hunks only when needed to resolve a conflict or verify an invariant

The parent should not absorb full worker transcripts as primary review input. The source of truth is the repo diff, the worker’s narrow summary, and the gate results.

## Tests And Acceptance

### Worker-Local Gates

`task/m2-b1-contract-surface`

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"
```

`task/m2-c1-prompt-validation-surface`

```bash
poetry run pytest -q tests/test_harness_prompt_consistency.py -k "attestation or trust"
poetry run pytest -q tests/test_harness_semantic_validation.py -k "attestation or bounded_attestation_input"
```

`task/m2-c2-docs-examples`

```bash
git diff --stat -- docs/analysis_review_contract.md examples/harness/strategies/
```

`task/m2-d1-runner-cutover`

```bash
poetry run pytest -q tests/test_harness_runner.py -k "attestation or bounded_attestation_input"
```

### Parent Final Gates

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"
poetry run pytest -q tests/test_harness_prompt_consistency.py -k "attestation or trust"
poetry run pytest -q tests/test_harness_runner.py -k "attestation or bounded_attestation_input"
poetry run pytest -q tests/test_harness_semantic_validation.py -k "attestation or bounded_attestation_input"
poetry run pytest -q tests/test_harness_reporting.py -k "apply_final_artifacts"
```

### Acceptance Criteria

M2 is complete only when all of these are true:

- strategy-level `trust_review.execution_mode` is real and tested
- `legacy_full_review` still preserves the current trust path
- attestation-mode trust runs bounded producer first
- attestation-mode trust persists and consumes `bounded_attestation_input`
- attestation-mode trust reuses bounded `final_analysis`
- attestation-mode trust does not create a second trust-authored analysis payload
- attestation prompt and semantic validation enforce dense attestation coverage over the bounded draft
- parity coverage exists for seam/artifact and adjudicate/deliberate combinations
- reporting/artifact-selection behavior is unchanged
- the final integrated diff still reads like one coherent M2 orchestration change

## Completion And Blocked Outcomes

### Complete Outcome

Mark the run complete only when:

- all task sentinels through `.merged` are present for B1, C1, C2, and D1
- all final gates pass in `wt/m2-integration`
- the parent verified the parity matrix gate explicitly
- the parent verified scope guards explicitly
- `queue.md`, `state.json`, and `gates/final-verification.md` all agree on completion state

### Blocked Outcome

Mark the run blocked if any of these occur:

- a needed change would leave M2 and enter reporting/publication redesign
- a conflict would require a creative architecture rewrite inconsistent with `PLAN.md`
- runner ownership cannot remain single-lane
- final gates fail and cannot be mapped to an integration artifact or a lane-owned fix without widening scope
- parity coverage cannot be demonstrated

Blocked runs must record:

- exact blocking task ID
- exact failing gate or unresolved conflict
- exact owner expected to resume
- exact next action required before restart

## Assumptions

- The current `PLAN.md` on `feat/bounded-work-redesign` is the authoritative implementation spec for M2 and remains read-only during orchestration.
- The parent can use `.runs/m2-attestation-orch/` as the repo-local operational source of truth.
- Sibling lane worktrees under `/Users/spensermcconnell/__Active_Code/forge.worktrees/m2-attestation/` are acceptable for this repository.
- Existing harness tests and fixtures are sufficient to express the attestation cutover without introducing new infrastructure or new schema families.
