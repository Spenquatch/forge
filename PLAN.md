<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260429-193825.md -->
# PLAN: M4 Request-Gate Productization on Top of M3

Status: ready for implementation
Milestone: `M4`
Branch: `feat/bounded-work-redesign`
Supersedes: the prior draft at this path and the already-landed M3 typed focus-gate finalization work
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260429-193245.md`
Implementation baseline: M3 typed focus gate is already landed on this branch at `HEAD`

## M4 Summary

M3 already did the hard foundational work:

- typed `focus_type = seam | artifact` exists
- `focus_decision` is persisted, validated, and rendered
- blocked deliberate behavior exists
- stale rerun-answer handling exists
- artifact singleton bridging exists
- acceptance tooling already covers the core focus-gate surface

M4 must not rebuild that machinery.

M4 turns the existing pre-proposer focus-gate surface into the explicit productized
request gate for analysis-review runs. The implementation stays local to the
analysis-review harness. It does not introduce a second router, a second public
artifact, or a third packet family.

The real M4 deliverable is not "we added another stage." That stage already exists.
The M4 deliverable is:

- one unambiguous public artifact boundary
- one explicit policy for when `seam` wins, when `artifact` wins, and when the run blocks
- one consistent report and summary story for the request-gate decision
- one complete acceptance and regression matrix proving early select and early block behavior
- one honest success bar tied to wasted-work reduction, not just cleaner contracts

## User Outcome

After M4, a user should feel three things:

1. Obvious singleton-file requests route cleanly without pretending they are broad seam reviews.
2. Obvious seam-shaped requests still take the same bounded review path they take today.
3. Ambiguous requests block before proposer instead of doing expensive wrong work first.

If users cannot feel that difference, M4 is not a product milestone. It is just
internal tidying.

## Success Criteria

M4 is successful only if all of these are true:

- every analysis-review run with focus gating enabled produces exactly one public `focus_decision`
- that `focus_decision` is finalized before proposer starts
- `focus_type` remains exactly `seam` or `artifact`, never a new third value
- clear singleton-file requests can select `artifact` and still bridge cleanly into the downstream seam-shaped payload surface
- clear seam requests still select `seam` and behave like current M3 happy paths
- ambiguous requests block before proposer on `clarification_requested` or `no_viable_focus`
- `summary.json`, persisted stage artifacts, and `REPORT.md` all expose the same request-gate result
- the acceptance matrix proves selected seam, selected artifact, blocked ambiguity, `never_ask`, stale rerun-answer, and regression compatibility paths

### Quantified Proof

Do not call M4 done on green unit tests alone.

Before closing the milestone, capture before-or-after evidence for:

- wrong-route rate on sampled seam-shaped requests
- wrong-route rate on sampled artifact-shaped requests
- median time from run start to final request-gate decision
- clarification rate on ambiguous requests
- number of runs that avoid the expensive review loop because the gate blocks early
- net runtime and token delta after including probe overhead

If those numbers do not move in the right direction, M4 should be treated as a
bounded experiment, not as proof that this abstraction deserves expansion.

## Step 0: Scope Challenge

### What Already Exists

| Sub-problem | Existing code | M4 decision |
|---|---|---|
| Canonical typed focus vocabulary | [anvil/harness/focus_types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/focus_types.py:1) | Reuse directly. No new packet-family enum. |
| Public `focus_decision` schema | [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:642) | Keep as the only public routing artifact unless validation proves it is insufficient. |
| Semantic validation for `seam` and `artifact` | [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:328) | Reuse and tighten only where M4 semantics expose a gap. |
| Pre-proposer focus gate orchestration | [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:614) | Keep the existing stage shape. M4 hardens and clarifies it; M4 does not invent a second gate. |
| Internal probe stage for deliberate flows | [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:389), [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:4748) | Keep internal-only. Do not promote probe output to a second public artifact. |
| Artifact singleton bridge | [anvil/harness/focus_types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/focus_types.py:35), [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:519) | Reuse unchanged as the downstream handoff contract. |
| Acceptance harness | [scripts/run_focus_gate_acceptance.py](/Users/spensermcconnell/__Active_Code/forge/scripts/run_focus_gate_acceptance.py:1), [tests/test_run_focus_gate_acceptance.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_run_focus_gate_acceptance.py:1) | Reuse and expand. Do not invent a new acceptance runner. |

### Minimum Change Set

M4 should stay inside four code surfaces:

1. `anvil/harness/` for runtime, prompt, validation, and reporting alignment
2. `tests/` for unit and semantic coverage
3. `scripts/` for acceptance assertions
4. `examples/harness/live_acceptance/` for scenario manifests

M4 should not add a new package, a new service layer, or a new public artifact type.

### Complexity Check

This work will likely touch more than eight files once tests and manifests are
counted. That is a smell, but not a reason to widen scope. The correct response is
to keep the conceptual change small:

- no new workflow family
- no new packet family
- no new planner
- no new pause or resume lifecycle
- no new external distribution surface

The implementation should still feel like one bounded capability change inside the
existing harness, not a platform rewrite in disguise.

### Search and Boring-by-Default Check

M4 should spend zero innovation tokens on new infrastructure.

The repo already has:

- a runner-owned pre-proposer gate
- a private probe stage for deliberate routing
- a typed public decision artifact
- semantic validation and acceptance infrastructure

The boring choice is the correct choice:

- keep existing stage names in code
- keep existing artifact family in public output
- keep the current downstream seam bridge
- extend tests and reporting instead of building another abstraction

### Scope Decision

M4 is locked to this scope:

- productize the existing pre-proposer focus gate as the M4 request gate for analysis-review runs
- keep exactly two packet families in scope: `seam` and `artifact`
- keep `focus_decision` as the only public routing artifact
- keep `focus_gate_probe` internal-only
- keep downstream review payload shape unchanged
- prove the behavior with unit tests, semantic validation, and live acceptance

## Decisions Locked for M4

| Decision | Chosen option | Why | Rejected alternative |
|---|---|---|---|
| Public artifact boundary | Reuse `focus_decision` | Minimal diff, matches existing validation and reporting surfaces, avoids dual-artifact drift | Add a second public request-decision artifact |
| Probe visibility | Keep `focus_gate_probe` internal-only | The probe is evidence-gathering context, not the published routing contract | Persist the probe as a second public surface |
| Runtime stage naming | Keep `focus_gate_probe` and `focus_gate` in code for M4 | Boring, low-risk, preserves existing tests and artifact paths | Rename runtime stages mid-milestone |
| Packet-family set | Exactly `seam` and `artifact` | Already landed, already validated, already bridged downstream | Add a third request type |
| Deliberate path | Use only for materially ambiguous routing | Protects users from confident wrong routing without teaching the system to ask all the time | Clarify first on every low-confidence case |
| Contract versioning | No public contract bump by default | Existing shape already represents the decision; only bump if implementation discovers a missing public field | Preemptive schema churn |
| Success bar | User-visible wasted-work reduction + correctness proof | Internal neatness alone is not enough | Declare victory on schema cleanliness |

## Architecture Plan

### Core M4 Call

Treat the existing focus-gate surface as the analysis-review request gate.

Do not add a second outer router. Do not add a second public artifact. Do not force
a rename that ripples through tests, reports, and scripts unless the behavior itself
demands it. M4 is a semantics and proof milestone built on top of the M3 runtime.

### Current Runtime Leverage

```text
analysis-review run
    |
    v
focus_gate? enabled
    |
    +--> adjudicate path
    |       |
    |       v
    |   selected | blocked
    |
    +--> deliberate path
            |
            v
      focus_gate_probe
            |
            v
      focus_gate
            |
            v
      selected | blocked
```

That is already real in the codebase. M4 should standardize what it means, not
pretend it is missing.

### Target M4 Behavioral Contract

```text
task + strategy + files_hint
        |
        v
M4 request gate
  (implemented by the existing focus-gate surface)
        |
        +--> selected seam
        |       |
        |       v
        |   proposer -> critic -> revisers -> auditor
        |
        +--> selected artifact
        |       |
        |       v
        |   singleton focus + downstream seam bridge
        |   proposer -> critic -> revisers -> auditor
        |
        +--> clarification_requested | no_viable_focus
                |
                v
             STOP
             no proposer artifacts
```

### Exact Stage Rules

#### Rule 1: `focus_decision` stays public and final

The only published routing artifact for M4 is `focus_decision`.

It must continue to be the single source of truth across:

- `summary.json`
- the persisted `focus_gate` stage artifact
- `run_details.focus_decision`
- `REPORT.md`

#### Rule 2: `focus_gate_probe` stays private

The probe stage may exist only to support deliberate routing. Its output is repo
evidence used to justify the final public decision.

The probe must not become:

- a second public decision surface
- a second report surface
- a second compatibility contract for downstream consumers

#### Rule 3: `adjudicate` is the cheap obvious-case path

When the task context alone is enough to choose the family, M4 should stay on
`gate_path=adjudicate` with:

- `decision_basis=request_only`
- `checked_files=[]`
- `files_hint_disposition=absent`

This path is for clear cases. It should not silently do probe-like work.

#### Rule 4: `deliberate` is the ambiguity path

Use `deliberate` only when packet-family ambiguity materially changes the review
shape.

For M4 that means:

- the request could plausibly be a multi-file seam or a singleton artifact
- the distinction matters to the correct review path
- asking or blocking is cheaper than confident wrong routing

#### Rule 5: blocked states halt before proposer

If `decision_state` is `clarification_requested` or `no_viable_focus`, the run stops.

M4 must preserve this invariant:

- no proposer stage
- no reviewer stages
- no fake downstream seam artifacts
- failure details include the gate decision, candidates, and warnings

### Packet-Family Rules

#### `seam` wins when:

- the task is clearly about a repo-local review unit that spans multiple related files
- the user intent is inherently multi-file even if `files_hint` is sparse
- a singleton-file interpretation would obviously under-scope the work

#### `artifact` wins when:

- the request is clearly about one governing file or one singleton control surface
- the selected path set normalizes to exactly one path
- the artifact singleton can still bridge into the downstream seam-shaped payload without ambiguity

#### `clarification_requested` wins when:

- both families remain plausible after the deliberate shortlist
- the user can answer the missing distinction directly
- the wrong route would waste more time than the clarification pause costs

#### `no_viable_focus` wins when:

- the request does not support a defensible shortlist
- `never_ask` prevents clarification on an ambiguous case
- a stale rerun answer no longer maps cleanly onto the current candidate set

### Artifact Boundary Decision Memo

M4 explicitly resolves the single-artifact versus dual-artifact question.

Choose the single-artifact design.

Why this is correct here:

- the runtime already persists `focus_decision`
- semantic validation already encodes the key invariants for `seam` and `artifact`
- the acceptance runner already reads `summary["focus_decision"]`
- a second public artifact would create two truths for one routing event

What makes this safe:

- the probe remains available as internal evidence
- the final public contract remains one object with one decision
- the downstream bridge stays encoded in `adapter_plan`

What would force a later reversal:

- if report clarity becomes materially worse
- if downstream consumers need probe-level evidence as a first-class contract
- if validation cannot express the final routing semantics cleanly in the existing shape

M4 assumes none of those are true until the implementation proves otherwise.

### Contract and Reporting Rules

M4 should keep the existing public `focus_decision` shape as the default contract.

That means the implementation should keep using:

- `gate_path`
- `focus_type`
- `decision_state`
- `decision_basis`
- `files_hint_disposition`
- `checked_files`
- `selected_focus_id`
- `selected_focus_paths`
- `adapter_plan`

The downstream bridge remains explicit:

- `focus_type=seam` => `adapter_plan.adaptation_basis = selected_focus_paths`
- `focus_type=artifact` => `adapter_plan.adaptation_basis = artifact_singleton`

M4 should only bump the public contract version if implementation discovers that
one of the user-visible invariants above cannot be represented without adding or
changing a public field.

## Implementation Plan

### Step 1: Lock the M4 semantics in runtime and docs

Modules touched:

- `anvil/harness/runner.py`
- `anvil/harness/prompts.py`
- `PLAN.md`

Required outcome:

- the code and plan both describe the same M4 request-gate semantics
- no lingering language implies a second public artifact or a separate router

### Step 2: Make reporting and summary output tell one story

Modules touched:

- `anvil/harness/runner.py`
- `anvil/harness/report.py`
- `anvil/harness/reporting.py`

Required outcome:

- `summary.json`, stage metadata, and `REPORT.md` expose the same request-gate result
- blocked runs show that the review loop was not exercised
- selected artifact runs show the singleton selection plus downstream bridge cleanly

### Step 3: Tighten prompt and policy text

Modules touched:

- `anvil/harness/prompts.py`

Required outcome:

- adjudicate guidance is clearly the cheap obvious-case path
- deliberate guidance is clearly the ambiguity path
- the prompt language reinforces the single public artifact boundary

### Step 4: Validate the public invariants

Modules touched:

- `anvil/harness/semantic_validation.py`
- `anvil/harness/schemas.py` only if a true gap is discovered

Required outcome:

- semantic validation enforces the M4 rules instead of relying on prompt compliance
- no contract change is made unless validation proves it is necessary

### Step 5: Expand acceptance and regression proof

Modules touched:

- `scripts/run_focus_gate_acceptance.py`
- `examples/harness/live_acceptance/`
- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`

Required outcome:

- selected seam and selected artifact paths pass
- blocked ambiguity paths pass
- `never_ask` blocked behavior passes
- stale rerun-answer behavior passes
- M3 happy-path compatibility stays green

## Test and Validation Plan

### Test Framework

The repo uses `pytest` and `pytest-asyncio` from [pyproject.toml](/Users/spensermcconnell/__Active_Code/forge/pyproject.toml:56).

M4 should land with repo-local tests first, then live acceptance.

### Required Coverage Diagram

```text
CODE PATH COVERAGE
==================

[+] anvil/harness/runner.py
    |
    ├── _run_analysis_review_v1()
    |   ├── focus gate disabled
    |   |   └── [KEEP] Existing non-gated behavior remains unchanged
    |   |
    |   └── focus gate enabled
    |       ├── adjudicate -> selected seam
    |       |   └── [REQUIRED] runner test + acceptance scenario
    |       |
    |       ├── adjudicate -> selected artifact
    |       |   └── [REQUIRED] runner test + acceptance scenario
    |       |
    |       ├── adjudicate -> no_viable_focus
    |       |   └── [REQUIRED] runner test proving proposer never runs
    |       |
    |       └── deliberate default
    |           ├── probe -> selected seam
    |           |   └── [KEEP] Existing deliberate selected path stays green
    |           |
    |           ├── probe -> clarification_requested
    |           |   └── [REQUIRED] runner test + acceptance scenario
    |           |
    |           ├── probe -> stale rerun_answer -> clarification_requested
    |           |   └── [REQUIRED] runner test + acceptance scenario
    |           |
    |           └── probe -> stale/ambiguous rerun_answer + never_ask -> no_viable_focus
    |               └── [REQUIRED] runner test + acceptance scenario
    |
    └── blocked outcome construction
        ├── clarification_requested
        |   └── [REQUIRED] failure_details contains question, candidates, warnings
        └── no_viable_focus
            └── [REQUIRED] failure_details contains candidates, warnings, no proposer artifacts

[+] anvil/harness/semantic_validation.py
    |
    ├── selected seam invariants
    |   └── [KEEP] selected_focus_id and downstream seam parity
    |
    ├── selected artifact invariants
    |   └── [KEEP] singleton path + canonical artifact ID + artifact_singleton basis
    |
    ├── adjudicate invariants
    |   └── [REQUIRED] request_only => gate_path=adjudicate, checked_files=[]
    |
    └── deliberate invariants
        └── [REQUIRED] repo_probe/rerun_answer => gate_path=deliberate, checked_files non-empty

[+] anvil/harness/prompts.py
    |
    ├── adjudicate prompt guidance
    |   └── [REQUIRED] prompt consistency test for request-only rules
    |
    ├── deliberate prompt guidance
    |   └── [REQUIRED] prompt consistency test for shortlist + stale answer rules
    |
    └── public/private artifact boundary language
        └── [REQUIRED] prompt consistency test that probe stays internal-only

USER FLOW COVERAGE
==================

[+] Clear seam request
    └── [REQUIRED] selected seam, review loop runs, downstream seam unchanged

[+] Clear artifact request
    └── [REQUIRED] selected artifact, singleton surfaced, downstream seam bridge preserved

[+] Ambiguous request
    └── [REQUIRED] clarification_requested, review loop does not start

[+] Ambiguous request with never_ask
    └── [REQUIRED] no_viable_focus, review loop does not start

[+] Rerun after stale clarification answer
    └── [REQUIRED] stale warning, no silent wrong selection

[+] M3 regression
    └── [REQUIRED] existing seam/artifact happy paths still produce the same visible output class
```

### Test File Plan

| Test surface | File |
|---|---|
| Runner behavior and stage ordering | [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:3112) |
| Prompt semantics and artifact-boundary language | [tests/test_harness_prompt_consistency.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py:675) |
| Public schema and semantic validation | [tests/test_harness_semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py:266) |
| Acceptance harness assertions | [tests/test_run_focus_gate_acceptance.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_run_focus_gate_acceptance.py:236) |
| Acceptance scenario manifests and strategy wiring | [tests/test_harness_example_strategy_wiring.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py:69) |

### Live Acceptance Matrix

Required scenario families:

1. clear seam request, `adjudicate`, `selected`
2. clear artifact request, `adjudicate`, `selected`
3. ambiguous request, `deliberate`, `clarification_requested`
4. ambiguous request with `never_ask`, `no_viable_focus`
5. stale rerun-answer on a deliberate request, `clarification_requested`
6. regression proof that existing M3 seam and artifact happy paths still succeed

### Commands

Minimum repo-local command set for M4:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Then run the acceptance harness against the local manifest in the same style M3 uses.

## Failure Modes

| Codepath | Real production failure | Test required | Error handling required | User-visible result |
|---|---|---|---|---|
| adjudicate -> selected artifact | singleton file selected, but downstream seam bridge drifts | yes | semantic validation must fail parity drift | hard failure, not silent wrong review |
| adjudicate -> no_viable_focus | gate reports no viable focus but proposer still runs | yes | blocked outcome must halt before proposer | clear blocked verdict |
| deliberate -> clarification_requested | question emitted but candidates/options drift from shortlist | yes | stale or invalid question must re-block | clear clarification request |
| rerun_answer -> stale | old answer silently forces a now-wrong selection | yes | stale warning + re-block or no-viable | clear blocked verdict, never silent reuse |
| artifact report rendering | report hides singleton choice or bridge basis | yes | report and summary parity checks | readable request-gate story |
| summary/report parity | `summary.json` and `REPORT.md` disagree | yes | acceptance harness must compare both | hard acceptance failure |

Critical gap rule for M4:

Any path that can silently misroute a run or silently continue after a blocked gate is
a release blocker. No exceptions.

## Worktree Parallelization Strategy

Parallelization exists, but it is limited. Most of the real logic still sits in
`anvil/harness/`, so pretending this is highly parallel would be fake precision.

### Dependency Table

| Step | Modules touched | Depends on |
|---|---|---|
| Lock runtime semantics | `anvil/harness/`, `PLAN.md` | — |
| Reporting and summary alignment | `anvil/harness/` | Lock runtime semantics |
| Acceptance manifest and script expansion | `scripts/`, `examples/harness/live_acceptance/` | Lock runtime semantics |
| Unit and semantic test expansion | `tests/` | Lock runtime semantics |
| Regression pass and closeout | `tests/`, `scripts/`, `anvil/harness/` | Reporting alignment + acceptance expansion + test expansion |

### Parallel Lanes

Lane A: lock runtime semantics -> reporting and summary alignment

Lane B: acceptance manifest and script expansion

Lane C: unit and semantic test expansion

### Execution Order

1. Do the runtime semantics lock first. That is the critical path.
2. Once those rules are frozen, launch Lane B and Lane C in parallel worktrees.
3. Merge B and C back.
4. Run the regression pass and fix any parity drift.

### Conflict Flags

- Lane A and Lane C are low-conflict once the runtime interface is frozen, but C should not start changing assertion shapes before A locks the final semantics.
- Lane A and Lane B are medium-conflict if B starts encoding acceptance expectations before A finalizes report and summary wording.
- Anything that touches `anvil/harness/runner.py` stays sequential. That file is the blast radius center.

This is not a three-lane freeway. It is one critical path plus two safe sidecars.

## What Already Exists

M4 should explicitly reuse these truths instead of recreating them:

- the runner already executes focus gating before proposer when enabled
- the repo already distinguishes `adjudicate` and `deliberate`
- the repo already validates `artifact_singleton` versus `selected_focus_paths`
- the acceptance harness already knows how to inspect `focus_decision`
- the repo already has regression coverage around blocked-before-proposer behavior

If an implementation step duplicates any of those, it is overbuilt.

## NOT in Scope

- a general multi-workflow request router
- a third packet family beyond `seam` and `artifact`
- renaming runtime stages from `focus_gate*` to a new public vocabulary during M4
- a second public request-decision artifact
- a new pause or resume lifecycle beyond the current rerun-answer behavior
- removal of all M2 compatibility shims in the same milestone
- a downstream review payload-family rewrite
- any new deployment or distribution surface

## Definition of Done

M4 is done only when all of these are true:

1. `focus_decision` remains the single public routing artifact.
2. The existing focus-gate surface behaves as the explicit M4 request gate for analysis-review runs.
3. Selected seam and selected artifact flows both pass with the same downstream payload contract M3 established.
4. `clarification_requested` and `no_viable_focus` both halt before proposer.
5. `summary.json`, stage artifacts, and `REPORT.md` tell the same request-gate story.
6. The full acceptance matrix passes, including stale rerun-answer and `never_ask`.
7. Regression coverage proves M3 happy paths still work.
8. The implementation proves real wasted-work reduction or, at minimum, does not regress it.
9. No new public artifact, workflow family, or packet family was introduced to get there.

That is M4.
