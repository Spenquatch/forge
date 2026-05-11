# PLAN: Bounded Work Redesign

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260510-222342.md`
Supersedes: the prior trust-attestation `PLAN.md` on this branch and the earlier design draft `spensermcconnell-feat-bounded-work-redesign-design-20260507-082505.md`

## Plan Summary

This branch is not a new request-gate architecture. The important split already
exists:

- `adjudicate` is the fast direct-selection lane
- `deliberate` is the probe-backed lane
- blocked outcomes already terminate before proposer with runner-owned
  `focus_decision`

What is still wrong is the product behavior inside initial deliberate seam runs.
Today `anvil/harness/runner.py` correctly detects unsafe broad seam selections,
but it converts them straight into `clarification_requested` or
`no_viable_focus`. That is honest, but it is too eager to hand work back to the
operator when the probe already surfaced narrower seam candidates.

This plan redefines deliberate seam handling as a bounded runner-owned salvage
pass. When the model selected a threshold-valid seam but that seam is still too
broad, the runner should try up to two narrower probe candidates that already
exist in the live shortlist. If one candidate survives canonical seam and
downstream bridge validation, the run continues automatically on that narrower
seam. If none survive, the run still stops before proposer, but it stops as an
actionable exhausted-refinement block with ranked rerun guidance instead of a
generic clarification prompt.

## Success Criteria

- A deliberate seam run no longer blocks purely because the model chose an
  umbrella seam when the live probe already exposed a narrower threshold-valid
  seam candidate.
- True probe ambiguity remains on the existing clarification path. This slice
  does not change `_resolve_focus_probe_state(...)` thresholds or auto-pick from
  an ambiguous shortlist.
- Exhausted broad-seam refinement produces actionable rerun guidance and a
  truthful `REPORT.md` explanation, without fabricating a clarification prompt.
- `adjudicate`, artifact deliberate behavior, and stale rerun-answer hardening
  remain unchanged unless explicitly called out below.
- The public `focus_decision` schema stays within the existing
  `selected | clarification_requested | no_viable_focus` contract.
- Acceptance coverage proves four cases: refinement success, refinement
  exhaustion, unchanged close-contest ambiguity, and unchanged artifact/stale
  guards.

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | Plan decision |
|---|---|---|
| Probe-backed deliberate lane | `anvil/harness/runner.py` via `_run_focus_gate(...)`, `_execute_focus_gate_probe_stage(...)`, `_execute_focus_gate_stage(...)` | Reuse this flow. No new provider stage and no second model call. |
| Winner thresholds | `_resolve_focus_probe_state(...)` | Reuse as-is. Do not turn ambiguous probe results into automatic refinement in this slice. |
| Broad seam hardening | `_normalize_focus_gate_decision_for_policy(...)` | Replace the current umbrella/collapsed-subset immediate block with bounded refinement plus exhausted fallback. |
| Blocked outcome shaping | `_probe_blocked_focus_gate_decision_from_probe(...)`, `_build_focus_gate_blocked_outcome(...)` | Extend blocked payloads with refinement metadata and rerun guidance. Do not add a new public decision state. |
| Focus-decision rendering | `anvil/harness/report.py` | Expand `## Focus Decision` to explain refinement success or exhaustion truthfully. |
| Public contract prose | `docs/analysis_review_contract.md` | Update deliberate semantics and blocked fallback wording. Keep the `focus_decision` enum family stable. |
| Acceptance surfaces | `examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`, `examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml` | Update seam-deliberate expectations to cover refined success and exhausted refinement. |
| Regression coverage | `tests/test_harness_runner.py`, `tests/test_harness_reporting.py`, `tests/test_run_focus_gate_acceptance.py`, `tests/test_harness_example_strategy_wiring.py` | Repoint deliberate seam cases to the new behavior and preserve old non-targeted guards. |

### Minimum change set

The minimum complete implementation touches these areas:

1. `anvil/harness/runner.py`
2. `anvil/harness/report.py`
3. `docs/analysis_review_contract.md`
4. `examples/harness/live_acceptance/focus_gate_acceptance.template.yaml`
5. `examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml`
6. `tests/test_harness_runner.py`
7. `tests/test_harness_reporting.py`
8. `tests/test_run_focus_gate_acceptance.py`
9. `tests/test_harness_example_strategy_wiring.py`

Anything beyond that is scope creep.

### Complexity verdict

This is a 9-file branch. That is above the usual smell threshold, but the size is
coming from required coverage and acceptance surfaces, not architecture sprawl.
The implementation is still the boring version:

- no new service
- no new dataclass family
- no new prompt schema
- no new public decision state
- no new orchestrator loop

The main smell to avoid is building a "refinement framework" when the actual
behavior change is a narrow normalization upgrade inside one existing runner
decision point.

### Search/build verdict

Everything needed already exists in the repo:

- probe shortlist and scores
- checked-files normalization
- canonical seam identity helpers
- existing downstream seam bridge validation surface
- current blocked outcome shaping
- current report rendering surface
- existing live acceptance manifests

This is a runner decision and reporting upgrade, not a subsystem build.

### TODOS cross-reference

Relevant deferred work already in `TODOS.md` remains deferred:

- generalized intent-intake work is still out of scope
- trust-attestation follow-ups are still out of scope
- product-level bounded-vs-trust validation is still out of scope

This branch should add no new TODO unless implementation reveals a real need for
generic path-cluster synthesis that does not belong in this slice.

### Completeness verdict

The complete version is not "auto-select from any shortlist." The complete
version is:

- refine only when the probe already produced a threshold-valid winner and the
  only remaining problem is broadness
- keep true ambiguity on the current clarification path
- persist runner-owned refinement metadata outside the public `focus_decision`
  schema
- render exhausted refinement with copyable rerun guidance
- cover success, exhaustion, close-contest, artifact, and stale-answer paths

The shortcut to avoid is a success-only implementation that auto-refines broad
seams but leaves exhausted runs with the same vague clarification behavior.

### Distribution and DX verdict

Forge is a developer tool. Distribution here means the documented and tested
behavior surface:

- `docs/analysis_review_contract.md`
- `REPORT.md`
- live acceptance manifests
- regression tests

If code changes but those surfaces still describe deliberate as a generic
clarification lane, the branch is incomplete.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Public gate paths | Keep `adjudicate` and `deliberate` exactly as-is | This slice changes deliberate behavior, not surface vocabulary. |
| Refinement scope | Seam-only, initial deliberate pass only | The product gap is broad seam selection, not artifact or rerun-answer behavior. |
| Refinement trigger | Only after a deliberate `selected` seam survives threshold validation but is still too broad | This preserves current ambiguity thresholds and avoids hidden auto-picks from weak evidence. |
| Ambiguous probe behavior | Unchanged | If `_resolve_focus_probe_state(...)` says the shortlist is ambiguous, stay on clarification / no-viable behavior. |
| Retry budget | At most 2 narrowed seam attempts | Enough to salvage obvious shortlist wins without inventing search recursion. |
| Public contract | Keep `focus_decision` schema and enums unchanged | Avoids dragging `schemas.py`, prompt builders, and semantic-validation fixtures into a protocol migration. |
| Metadata placement | Add runner-owned refinement metadata under `run_details` and blocked `failure_details`, not as new public `focus_decision` keys | Lowest diff and cleanest contract boundary. |
| Exhausted fallback | Use actionable blocked output with ranked rerun guidance, not a fake clarification prompt | Broadness exhaustion is not the same thing as operator ambiguity. |
| Artifact deliberate path | Unchanged | The existing operator-confirmation rule remains correct. |
| Rerun-answer stale logic | Unchanged | This slice is about first-pass broad seam salvage, not stale operator input. |
| Prompt/schema files | Do not touch unless the public contract is intentionally widened | That would be a different branch. |

## Architecture Review

### Current deliberate behavior

```text
task + strategy(default_path=deliberate)
  ->
focus_gate_probe
  ->
focus_gate(deliberate)
  ->
runner hardening
  ->
selected -> proposer
or
clarification_requested / no_viable_focus -> stop
```

### Current bad product shape

```text
probe finds the right neighborhood
  ->
model picks a threshold-valid but broad seam
  ->
runner detects umbrella/collapsed-subset shape
  ->
run stops immediately
```

That is honest. It is also noisy. The runner already has enough evidence to try
one more bounded narrowing step before it asks the operator to do the obvious.

### Target behavior

```text
task + strategy(default_path=deliberate)
  ->
focus_gate_probe
  ->
focus_gate(deliberate)
  ->
runner hardening
  ->
if selected seam is broad:
    try narrowed shortlist candidate A
    if A invalid, try candidate B
  ->
selected narrowed seam -> proposer
or
no_viable_focus + rerun guidance -> stop
```

### Contract boundary

This is the most important implementation constraint.

Do change:

- runner normalization behavior in `anvil/harness/runner.py`
- blocked outcome payload details
- report rendering
- contract prose and acceptance expectations

Do not change in this slice:

- `focus_decision.decision_state` enum
- `focus_decision.question` contract
- prompt builders in `anvil/harness/prompts.py`
- schema definitions in `anvil/harness/schemas.py`
- semantic-validation expectations in `tests/test_harness_semantic_validation.py`
- prompt-consistency expectations in `tests/test_harness_prompt_consistency.py`

That boundary keeps this branch about runtime behavior, not a wider protocol
revision.

### Refinement eligibility rules

Attempt internal refinement only when all of these are true:

1. `gate_path == deliberate`
2. `focus_type == seam`
3. `decision_state == selected`
4. `focus_gate_answer is None`
5. `focus_probe` exists and `_resolve_focus_probe_state(...)` returned a
   threshold-valid winner
6. `selected_focus_id` already matches the runner-computed valid winner
7. the selected seam is broad under one of the broadness triggers below

Do not attempt refinement for:

- `adjudicate`
- `artifact`
- stale rerun answers
- any probe state where `valid_winner_focus_id` is empty
- any selected result that already points to a narrow seam with no stronger
  narrower candidate

### Broadness triggers

Refinement is for broadness, not ambiguity.

Trigger refinement when either of these is true:

1. **Umbrella seam**: `selected_focus_paths == checked_files` and the selected
   seam spans more than one file.
2. **Collapsed narrower subsets**: a different probe candidate has
   `score >= 0.55`, non-empty normalized `candidate_paths`, and those paths form
   a proper subset of the selected seam's normalized path set.

Do not trigger refinement for:

- close contests where the probe has no threshold-valid winner
- single-candidate shortlists with no narrower subset evidence
- any case that would require changing the existing winner thresholds

### Candidate ranking and admissibility

Build the refinement pool from `focus_probe.candidates`, not from the public
`focus_decision.candidates`, because the probe payload is the live shortlist and
the public payload may already be capped or deduplicated for contract reasons.

Algorithm:

1. Keep only dict candidates with a non-empty `focus_id`, numeric `score`, and
   non-empty normalized `candidate_paths`.
2. Keep only candidates whose normalized path set is a proper subset of the
   selected seam's normalized path set.
3. Collapse duplicate canonical seam identities. Keep the highest-scoring
   representative.
4. Rank the remaining candidates by:
   - higher `score`
   - fewer normalized paths
   - original probe order as final tiebreak
5. Try at most two candidates in ranked order.

A candidate succeeds only if it:

- still resolves to a proper narrowed subset
- retains stable canonical seam identity
- can populate `selected_focus_*` and
  `adapter_plan.downstream_primary_seam_*` without drift
- does not require threshold relaxation or prompt re-execution

If candidate A fails, record why, then try candidate B. If both fail, the
refinement is exhausted.

### Metadata contract

Keep `focus_decision` public shape stable. Persist runner-owned refinement
details separately.

For successful runs:

```text
run_details.focus_refinement
```

For blocked exhausted-refinement runs:

```text
run_details.focus_refinement
failure_details.focus_refinement
```

Proposed metadata shape:

```json
{
  "status": "applied | exhausted",
  "trigger_reason": "umbrella_selected_checked_files | collapsed_narrower_subset",
  "source_selected_focus_id": "string",
  "source_selected_focus_paths": ["string"],
  "candidate_shortlist_ids": ["string"],
  "attempted_candidate_ids": ["string"],
  "rejected_candidates": [
    {
      "focus_id": "string",
      "reason": "not_proper_subset | canonical_drift | downstream_bridge_drift"
    }
  ],
  "selected_candidate_id": "string|null",
  "selected_candidate_paths": ["string"],
  "exhausted_reason": "string|null",
  "rerun_guidance": [
    {
      "focus_id": "string",
      "score": 0.0,
      "candidate_paths": ["string"],
      "why_candidate": "string"
    }
  ]
}
```

Notes:

- `rerun_guidance` is runner-owned display metadata, not a new public question
  format.
- successful refinement should also replace the canonical selected
  `focus_decision` with the narrowed seam so downstream proposer behavior stays
  honest.
- exhausted refinement should preserve the blocked `focus_decision`, but the
  block should now carry refinement metadata and rerun guidance.

### Exhausted outcome semantics

This plan intentionally distinguishes **broadness exhaustion** from **user
clarification**.

- **True ambiguity** stays on existing `clarification_requested` or
  `no_viable_focus` behavior, depending on `clarification_policy`.
- **Exhausted broad-seam refinement** should normalize to `no_viable_focus` with
  non-empty candidate shortlist and runner-owned rerun guidance.

Why this matters:

- `clarification_requested` requires the canonical prompt and options contract
- exhausted refinement is not asking a new question, it is providing a narrower
  next move
- `REPORT.md` must not fake a question when the actual advice is "rerun with one
  of these narrower `files_hint` slices"

## Code Quality Guardrails

- Keep the implementation inside `anvil/harness/runner.py`. Extract at most a
  few focused private helpers if they make the refinement path easier to read.
- Do not introduce a `FocusRefinementService`, `RefinementPlanner`, or similar
  abstraction. This branch does not need a framework to choose between two seam
  candidates.
- Reuse existing workspace-ref normalization, canonical seam identity, and
  adapter-plan builder logic. Do not fork seam identity rules.
- Keep broadness and ambiguity as separate concepts in code and prose. That
  distinction is the whole feature.
- Preserve current artifact deliberate warning paths exactly.
- Preserve stale-answer hardening exactly.
- Keep report language explicit:
  - `auto-refined and continued`
  - `refinement exhausted`
  - `rerun with one of these files_hint slices`

## Test Review

### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/runner.py deliberate seam path
    |
    |-- probe has threshold-valid winner + selected seam is broad
    |   |-- [GAP] top narrowed candidate survives validation -> selected continues
    |   `-- [GAP] candidate A fails, candidate B survives -> selected continues
    |
    |-- probe has threshold-valid winner + selected seam is broad + no candidate survives
    |   `-- [GAP] normalized no_viable_focus with rerun guidance
    |
    |-- probe is ambiguous under existing thresholds
    |   |-- [TESTED TODAY] clarification_requested path
    |   `-- [TESTED TODAY] never_ask -> no_viable_focus path
    |
    |-- focus_type=artifact deliberate
    |   |-- [TESTED TODAY] clarification_requested
    |   `-- [TESTED TODAY] never_ask -> no_viable_focus
    |
    `-- stale rerun-answer handling
        |-- [TESTED TODAY] stale prompt / vanished option blocks
        `-- [TESTED TODAY] never_ask stale answer -> no_viable_focus

[+] anvil/harness/report.py focus decision rendering
    |
    |-- [GAP] refined success renders "auto-refined and continued"
    |-- [GAP] exhausted refinement renders ranked rerun guidance
    |-- [GAP] exhausted refinement does not render fake clarification prompt
    `-- [TESTED TODAY] stale no_viable_focus avoids fake clarification block

[+] live acceptance manifests
    |
    |-- [GAP] seam deliberate success scenario expects continuation
    |-- [GAP] seam deliberate exhausted scenario expects blocked rerun guidance
    `-- [TESTED TODAY] artifact deliberate remains blocked

---------------------------------
COVERAGE TARGET: 100% of new runner branches
Critical regressions to keep: true ambiguity blocking, artifact deliberate
blocking, stale-answer blocking, adjudicate direct selection
---------------------------------
```

### User flow coverage

```text
USER FLOW COVERAGE
===========================
[+] Large repo, broad seam, strong narrowed shortlist
    |-- [GAP] runner narrows automatically
    |-- [GAP] proposer executes on the narrowed seam
    `-- [GAP] report explains what changed

[+] Large repo, broad seam, no narrowed candidate survives validation
    |-- [GAP] run stops before proposer
    |-- [GAP] report shows ranked shortlist
    `-- [GAP] rerun guidance is copyable as files_hint

[+] True shortlist ambiguity
    |-- [TESTED TODAY] clarification_requested when asking is allowed
    `-- [TESTED TODAY] no_viable_focus when clarification_policy=never_ask
```

### Required test additions

Update or add coverage in these files:

- `tests/test_harness_runner.py`
  - broad selected seam auto-refines to the top narrowed shortlisted seam
  - candidate A can fail bridge validation and candidate B still succeed
  - exhausted refinement normalizes to `no_viable_focus` with rerun guidance
  - `clarification_policy=never_ask` still auto-refines when no operator input is
    needed
  - close-contest ambiguity remains blocked
  - artifact deliberate behavior remains blocked
- `tests/test_harness_reporting.py`
  - refined success renders the refinement note
  - exhausted refinement renders rerun guidance and ranked shortlist
  - exhausted refinement does not render a clarification prompt block
- `tests/test_run_focus_gate_acceptance.py`
  - seam deliberate success scenario continues through proposer
  - seam deliberate exhausted scenario blocks with rerun guidance
- `tests/test_harness_example_strategy_wiring.py`
  - acceptance template expectations still match the canonical trust entrypoint
    after seam-deliberate scenario changes

Do not add plan-only smoke tests. Every new branch in the runner needs a real
assertion path.

### Validation commands

Run at minimum:

```bash
poetry run pytest -q tests/test_harness_runner.py -k "focus_gate"
poetry run pytest -q tests/test_harness_reporting.py -k "focus_decision or no_viable_focus or clarification"
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

## Performance Review

- The refinement pass must stay O(n) in shortlist size. Probe candidate lists are
  already small, so the runtime cost is tiny next to the model call.
- Do not add a second probe stage or a second provider invocation.
- Do not re-run the deliberate prompt after refinement failure.
- Normalize candidate path sets once per candidate and reuse them during ranking
  and admissibility checks.
- No caching layer is needed.

## Failure Modes Registry

| Codepath | Real failure | Test cover required | Error handling required | User-visible outcome |
|---|---|---|---|---|
| Successful auto-refinement | runner picks a narrowed seam whose canonical or downstream bridge does not match persisted selected state | yes | reject candidate and try the next one | run continues only on a validated narrowed seam |
| Exhausted refinement | runner has shortlist data but still emits the old vague block text | yes | synthesize rerun guidance from ranked candidates | blocked with copyable next step |
| Ambiguity drift | runner auto-selects from a genuinely ambiguous shortlist | yes | preserve `_resolve_focus_probe_state(...)` thresholds exactly | clarification or no-viable remains |
| Artifact drift | seam refinement logic touches artifact deliberate behavior | yes | explicit `focus_type == seam` guard | artifact path stays blocked |
| Report drift | `REPORT.md` implies the runner asked a question when it actually emitted rerun guidance | yes | render from `focus_refinement` metadata, not inferred prompt text | truthful report |

Critical gap to avoid: a blocked exhausted-refinement run that has no test, no
rerun guidance, and no clear operator action. That is the exact product hole this
branch is fixing.

## NOT in Scope

- changing `adjudicate` behavior
- upgrading ambiguous probe results into automatic refinement
- artifact deliberate auto-selection
- stale rerun-answer behavior changes
- new public `decision_state` or `decision_basis` enums
- prompt-family rewrites for `focus_gate_probe` or `focus_gate`
- `focus_decision` schema growth
- semantic-validation contract rewrites
- hidden background retries or recursive search
- generic path-cluster synthesis beyond the live probe shortlist

## Implementation Plan

### Step 1: Add runner-owned refinement helpers

In `anvil/harness/runner.py`:

- add a helper that decides whether a deliberate `selected` seam is:
  - safely selected
  - broad and refineable
  - broad but not refineable
  - ambiguous and unchanged
- add a helper that builds the ranked narrowed seam candidate pool from
  `focus_probe.candidates`
- add a helper that tries up to two narrowed candidates and returns:
  - refined `focus_decision` plus `focus_refinement` metadata
  - or exhausted blocked metadata plus rerun guidance

Done means:

- the helper API is private and local to `runner.py`
- ambiguity and broadness are separate code paths
- no new provider call exists anywhere in the branch

### Step 2: Rewire deliberate hardening

Inside `_normalize_focus_gate_decision_for_policy(...)`:

- keep stale-answer handling first and unchanged
- keep ambiguous probe blocking unchanged
- keep initial deliberate artifact blocking unchanged
- replace the current umbrella/collapsed-subset immediate block with:
  - classify broadness
  - attempt narrowed seam refinement
  - continue on success
  - normalize to exhausted blocked outcome on failure

Done means:

- broadness no longer immediately becomes generic clarification
- true ambiguity still does
- `adjudicate` behavior stays untouched

### Step 3: Persist refinement metadata

In runner success and blocked outcomes:

- persist runner-owned `focus_refinement` metadata under `details`
- ensure it survives into `summary.run_details.focus_refinement`
- mirror it into `failure_details.focus_refinement` for blocked exhausted runs
- keep `focus_decision` itself stable except when a narrowed seam becomes the
  real selected focus

Done means:

- `summary.focus_decision` still fits the existing contract
- report rendering has a stable metadata source for both success and exhaustion

### Step 4: Update report rendering

In `anvil/harness/report.py`:

- render whether deliberate auto-refined
- render the trigger reason
- render attempted and rejected candidates when useful
- render rerun guidance as narrowed `files_hint` suggestions when refinement was
  exhausted
- never render a fake clarification prompt for exhausted refinement

Done means:

- refined success reads as intentional, not magical
- exhausted refinement reads as actionable, not vague
- stale no-viable behavior still renders correctly

### Step 5: Update docs and acceptance surfaces

- update `docs/analysis_review_contract.md` to describe deliberate seam behavior
  as:
  - probe
  - public deliberate decision
  - bounded internal broad-seam refinement
  - exhausted rerun guidance fallback
- update both live acceptance templates so seam deliberate now covers:
  - one scenario that auto-refines and continues
  - one scenario that exhausts and blocks with rerun guidance
- keep artifact deliberate acceptance expectations unchanged

Done means:

- docs, manifests, and tests all tell the same story
- there is no contract prose implying that every deliberate seam block is a
  clarification prompt

### Step 6: Lock the regression suite

- add runner coverage first
- add report coverage second
- update acceptance manifests and acceptance tests third
- run the targeted commands last

Done means:

- all new branches are covered before final acceptance expectations are updated
- regression failures point to the behavior change, not to stale fixtures

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| 1. Runner refinement core | `anvil/harness/` | - |
| 2. Report rendering + report tests | `anvil/harness/`, `tests/` | 1 |
| 3. Docs + live acceptance manifests + acceptance expectations | `docs/`, `examples/harness/live_acceptance/`, `tests/` | 1 |
| 4. Final regression sweep | `tests/` | 1, 2, 3 |

### Parallel lanes

- Lane A: Step 1
  Shared modules: `anvil/harness/runner.py`, `tests/test_harness_runner.py`
- Lane B: Step 2
  Shared modules: `anvil/harness/report.py`, `tests/test_harness_reporting.py`
- Lane C: Step 3
  Shared modules: `docs/analysis_review_contract.md`,
  `examples/harness/live_acceptance/`,
  `tests/test_run_focus_gate_acceptance.py`,
  `tests/test_harness_example_strategy_wiring.py`
- Lane D: Step 4
  Shared modules: `tests/`

### Execution order

1. Launch Lane A first. It defines the actual refinement semantics and metadata
   names.
2. Once Lane A settles the `focus_refinement` payload shape, launch Lane B and
   Lane C in parallel worktrees.
3. Merge Lane A.
4. Rebase Lane B and Lane C onto A if any metadata strings or scenario names
   shifted.
5. Run Lane D after B and C both land.

### Conflict flags

- Lane A and Lane B both touch `anvil/harness/`, but the intended ownership
  split is `runner.py` versus `report.py`.
- Lane B and Lane C both touch `tests/`, but they should stay on disjoint test
  files.
- Lane C must not invent final scenario names or rerun-guidance wording before
  Lane A settles them.
- This is not a fully parallel branch. The real parallel window opens only after
  Lane A defines the runner contract.

## Acceptance Checklist

The branch is done only when all of these are true:

- deliberate seam refinement can continue automatically on a narrowed shortlisted
  seam
- candidate A failure can still fall through to candidate B success
- exhausted refinement stops before proposer with ranked rerun guidance
- exhausted refinement renders as actionable `no_viable_focus`, not a fake
  clarification question
- close-contest ambiguity still blocks under the existing rules
- artifact deliberate still blocks
- stale rerun-answer hardening still blocks
- `REPORT.md` tells the truth in both refined-success and exhausted-refinement
  cases
- contract docs describe the new deliberate behavior precisely
- the targeted regression commands are green
