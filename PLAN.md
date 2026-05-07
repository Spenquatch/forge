# PLAN: Trust Attestation Over Bounded Output, M2 Only

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260504-211401.md`
Supersedes: the prior M1-only `PLAN.md` on this branch

## Plan Summary

M1 is done. The repo can already emit a runner-owned `bounded_attestation_input`
payload from bounded runs.

M2 makes that handoff real for trust mode without changing public strategy kinds,
artifact semantics, or reporting logic. The entire point is to stop trust from
behaving like a second full answer generator when the bounded lane already knows
how to produce the candidate draft.

This plan keeps one product promise fixed:

- `analysis_review_trust_v1` remains the public trust strategy kind
- `trust_review.execution_mode` becomes the internal cutover knob
- `legacy_full_review` keeps today's trust behavior
- `attestation_over_bounded` runs bounded production first, freezes the handoff,
  then runs trust as attestation over that frozen object
- `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, `BEST_DRAFT.*`, and
  `analysis_review_status.publishability` remain runner-owned and unchanged in M2

If implementation starts rewriting publication or artifact projection, it has
left M2 and wandered into M3.

## M1 Validation Verdict

M1 landed the right prerequisite pieces:

- `build_analysis_review_contract(...)` already serializes
  `trust_review.execution_mode`, but the value is still effectively fixed at
  `legacy_full_review`
- bounded runs already build and persist `bounded_attestation_input`
- the handoff builder already validates schema plus semantic invariants
- contract docs already mark the handoff as runner-owned and "M1 emits, M2 consumes"
- trust still starts from raw task plus workspace and does not consume the handoff yet

Validation commands already run on this branch:

- `poetry run pytest -q tests/test_harness_runner.py -k "bounded_attestation_input"`
- `poetry run pytest -q tests/test_harness_semantic_validation.py -k "bounded_attestation_input"`
- `poetry run pytest -q tests/test_harness_analysis_contract.py -k "bounded_attestation_input or execution_mode or contract_docs_freeze"`

Result: `19 passed`

## Success Criteria

M2 is complete only when all of these are true:

- trust strategies can opt into `trust_review.execution_mode=attestation_over_bounded`
  without changing the public `analysis_review_trust_v1` kind
- attestation-mode trust runs execute the bounded producer lane first
- the bounded producer lane and the final trust attestation stage remain logically
  separate in runner state
- attestation-mode trust runs persist the exact frozen `bounded_attestation_input`
  they consumed
- attestation-mode trust uses the bounded producer's `final_analysis` as the final
  answer source and does not fabricate a second trust-authored analysis payload
- the final trust review payload contains recommendation verdicts, closure proof,
  provenance, and final content verdicts over the bounded draft
- `legacy_full_review` continues to behave exactly like today's trust path
- final artifact selection and publishability logic remain unchanged in M2

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | M2 decision |
|---|---|---|
| Strategy surface for trust mode | `StrategyConfig` in `anvil/harness/types.py` | Extend strategy parsing so `trust_review.execution_mode` is a real input, not dead metadata. |
| Shared contract field | `TrustReviewPolicy.execution_mode` in `anvil/harness/contracts.py` | Reuse this field. Do not invent a second cutover knob. |
| Bounded producer lane | `_run_analysis_review_v1(...)` in `anvil/harness/runner.py` | Extract reusable bounded-producer helpers from the current lane instead of building a second producer implementation. |
| Frozen handoff contract | `_build_bounded_attestation_input(...)` in `anvil/harness/runner.py` | Reuse the M1 handoff unchanged except where M2 must consume it. |
| Shared review payload schema | `analysis_review_schema()` in `anvil/harness/schemas.py` | Keep the shared review JSON family. Attestation emits a review payload, not a new schema family. |
| Existing trust review semantics | prompt and validation rules in `anvil/harness/prompts.py` and `anvil/harness/semantic_validation.py` | Reuse the trust review payload shape. Add an attestation-specific prompt builder instead of overloading bounded reviewer prompts. |
| Runner-owned publication truth | `apply_final_artifacts(...)` in `anvil/harness/reporting.py` plus status assembly in `anvil/harness/runner.py` | Hold this stable in M2. No reporting rewrite. |

### Complexity verdict

This slice legitimately touches more than 8 files. That is not scope creep here.
The cutover crosses config parsing, contract resolution, runner orchestration,
prompts, validation, examples, docs, and tests. Anything smaller would leave a fake
knob or an untested branch.

The constraint is not "few files at any cost." The constraint is "few new moving
parts." M2 should introduce:

- zero new provider abstractions
- zero new schema families
- zero reporting changes
- at most two new runner-local helper seams
- one new prompt builder

### Search/build verdict

Use the harness shapes already on disk. Do not roll custom infrastructure where the
repo already has the primitive:

- contract resolution already exists
- bounded handoff validation already exists
- final artifact selection already exists
- trust review payload validation already exists

This is a refactor of orchestration, not a platform expansion.

### TODOS cross-reference

`TODOS.md` already contains the exact follow-up this slice now implements:
"reshape trust mode into an attestation layer over bounded output." That item is no
longer backlog once M2 starts. Other backlog items remain deferred:

- generalized intent-intake
- trust-vs-bounded product reshaping beyond this single cutover
- report UX polish
- richer provenance or audit artifacts

### Completeness verdict

Do the complete M2, not a shortcut. That means:

- real strategy parsing
- real runner branch cutover
- real attestation prompt path
- real semantic validation
- real regression coverage

What does not count as complete:

- hardcoding attestation mode in examples only
- attaching bounded payloads to trust summaries without actually consuming them
- treating the bounded producer as an undocumented subroutine

### Distribution check

No new binary, package, container image, or external distribution surface is
introduced here. Distribution is unchanged. No CI or publish-pipeline work is needed
for M2.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Public trust strategy kind | keep `analysis_review_trust_v1` | Preserve current product surface and examples. |
| M2 cutover knob | strategy-level `trust_review.execution_mode` | The contract already has this field. Make it real. |
| Default execution mode | `legacy_full_review` | Existing trust runs must remain stable until the new path is chosen deliberately. |
| Producer source of truth | internal bounded producer lane reusing today's bounded flow | One real producer. No duplicate implementation. |
| Focus gate timing | run once, before bounded production | Trust must attest the same selected focus the producer used. |
| Attestation review shape | one trust attestation review stage, not a second proposer/reviser/auditor lane | Trust is attesting the frozen draft, not generating a new one. |
| Final analysis in attestation mode | bounded producer `final_analysis` becomes the final answer source | Keeps M2 out of M3 publication and artifact logic. |
| Handoff persistence | persist `bounded_attestation_input` in attestation-mode trust summaries | The consumed object must be inspectable after the run. |
| Publication logic | unchanged in M2 | M3 owns reporting and publication cutover. |
| Provider surface | no provider wrapper unless the current role request shape truly cannot express attestation prompts | Avoid speculative plumbing. |

## Architecture Review

### Current runtime shape

Legacy trust today still behaves like a full review lane:

```text
focus gate (optional)
  ->
trust proposer
  ->
trust critic
  ->
trust reviser loop(s)
  ->
trust auditor
  ->
runner-owned admissibility + publishability
```

That shape is expensive and conceptually wrong for the product distinction we want.

### Target runtime shape for M2

```text
focus gate (optional)
  ->
bounded producer lane
  ->
frozen bounded_attestation_input
  ->
trust attestation review
  ->
runner-owned admissibility + publishability
```

### Branch split inside `anvil/harness/runner.py`

```text
_run_analysis_review_v1()
  |
  +-- resolve contract
  +-- run focus gate once
  +-- if mode != trust:
  |     -> keep existing bounded path
  |
  +-- if mode == trust and execution_mode == legacy_full_review:
  |     -> keep existing trust full-review path
  |
  +-- if mode == trust and execution_mode == attestation_over_bounded:
        -> derive bounded producer contract
        -> run bounded producer helper
        -> freeze/persist bounded_attestation_input
        -> reset final-review stage selection to attestation phase only
        -> run trust attestation review helper
        -> compute final status from bounded final_analysis + attestation review payload
```

### Module boundary plan

| Module | Responsibility in M2 | Must stay out of scope |
|---|---|---|
| `anvil/harness/types.py` | parse and round-trip `trust_review.execution_mode` | no new task-level knob |
| `anvil/harness/contracts.py` | resolve execution mode into the contract | no new public strategy kind |
| `anvil/harness/prompts.py` | build one dedicated attestation review prompt | no branching prose jammed into bounded critic/auditor prompts |
| `anvil/harness/runner.py` | branch orchestration, bounded producer reuse, stage isolation, final status assembly | no reporting rewrite, no second trust-authored analysis payload |
| `anvil/harness/semantic_validation.py` | enforce dense attestation coverage and bounded-universe invariants | no new validation model family |
| `docs/analysis_review_contract.md` | document execution modes and M2 ownership boundaries | no M3 publication redesign |

### Runner-local helper plan

Keep the implementation boring. The runner needs two explicit helper seams:

1. A bounded producer helper that reuses today's proposer/critic/reviser/auditor
   flow and returns:
   - bounded `final_analysis`
   - bounded review summary
   - frozen `bounded_attestation_input`
   - stage metadata needed to prevent final-review contamination

2. A trust attestation review helper that:
   - takes the frozen handoff plus current workspace snapshot
   - runs one trust attestation review stage
   - returns the final review payload used to compute trust status

Do not create a generic subgraph framework. Do not create a new runner class.
This is one branch split inside the existing harness runner.

### Required invariants

These are hard rules, not suggestions:

1. In `attestation_over_bounded`, `run_details["final_analysis"]` must come from the
   bounded producer result.
2. In `attestation_over_bounded`, `run_details["bounded_attestation_input"]` must be
   the exact frozen object passed to the trust attestation review stage.
3. In `attestation_over_bounded`, the final trust review payload must not include a
   second trust-authored answer draft.
4. Final-stage selectors such as `_latest_successful_stage(...)` must not accidentally
   read bounded producer critic/auditor stages as the final trust review stage.
5. `apply_final_artifacts(summary)` stays untouched in M2.
6. Legacy trust mode remains byte-for-byte compatible at the contract and artifact
   level unless a regression test proves current behavior was already wrong.

### Production failure scenarios to defend

| Codepath | Real failure | Required defense |
|---|---|---|
| Strategy parsing | execution mode silently ignored | parser tests plus contract serialization tests |
| Runner branch cutover | trust still enters proposer-first path in attestation mode | branch-selection runner tests |
| Stage resolution | bounded producer review stages contaminate final trust provenance | explicit phase tagging or equivalent runner-local filtering |
| Attestation review | attestor emits verdicts for only a subset of recommendations | dense recommendation coverage validation |
| Final artifact assembly | summary uses bounded `final_analysis` but trust review from wrong stage | final status regression tests |

## Code Quality Guardrails

### Minimal-diff rules

- Keep new logic inside existing files unless a test fixture becomes impossible to
  express cleanly.
- Prefer new small helpers over new classes.
- Keep naming explicit: "bounded producer", "attestation review", "execution mode".
  No cute abstractions.
- Reuse the current review payload shape. Attestation is a different prompt, not a
  different data family.

### DRY rules

- No duplicate bounded producer implementation.
- No duplicate execution-mode source of truth.
- No duplicate artifact-selection logic.
- No duplicate recommendation-coverage validation logic if the existing trust-mode
  validators can be reused with bounded-universe inputs.

### File-level expectations

- `anvil/harness/runner.py` may grow new helpers, but the public control flow should
  remain readable from `_run_analysis_review_v1(...)`.
- `anvil/harness/prompts.py` should gain a dedicated
  `build_trust_attestation_review_prompt(...)` builder.
- Existing critic/auditor builders should not gain mode-specific prose branches for
  attestation behavior.

## File-by-File Implementation Plan

### 1. Strategy parsing in `anvil/harness/types.py`

Add a small typed strategy config for trust execution:

- new `StrategyTrustReviewConfig`
- allow `trust_review.execution_mode`
- allowed literals:
  - `legacy_full_review`
  - `attestation_over_bounded`

Requirements:

- default remains `legacy_full_review`
- unknown keys under `trust_review` fail loudly
- `StrategyConfig.to_dict()` round-trips the field

Non-goal:

- do not expose a second task-level trust execution knob

### 2. Contract resolution in `anvil/harness/contracts.py`

Change `build_analysis_review_contract(...)` so
`TrustReviewPolicy.execution_mode` comes from parsed strategy config instead of
being effectively fixed at `legacy_full_review`.

Requirements:

- bounded and legacy strategies still serialize `legacy_full_review`
- trust strategies may choose either execution mode
- `effective_strategy` stays unchanged

### 3. Attestation prompt builder in `anvil/harness/prompts.py`

Add `build_trust_attestation_review_prompt(...)`.

Required prompt inputs:

- `bounded_attestation_input`
- the bounded `focus_decision`
- bounded review-surface summary
- current workspace snapshot
- the resolved trust contract

Prompt rules:

- review the frozen bounded draft, do not regenerate recommendations from scratch
- return one `recommendation_reviews` verdict for every bounded recommendation index
- use closure-review arrays only for `recommendation_index = null` global proof
- re-check workspace evidence directly before attesting
- do not emit a replacement analysis payload

### 4. Runner cutover in `anvil/harness/runner.py`

Split the current trust path into two explicit branches:

- `legacy_full_review` -> existing path
- `attestation_over_bounded` -> new path

Required shape:

1. resolve trust contract
2. run focus gate once
3. if `legacy_full_review`, keep existing flow
4. if `attestation_over_bounded`:
   - derive an internal bounded producer contract from the resolved trust contract
   - run the bounded producer helper with the existing bounded proposer/reviewer loop
   - capture bounded `final_analysis`, bounded review summary, and the frozen handoff
   - persist `bounded_attestation_input` on the final trust summary
   - isolate producer-stage bookkeeping from the final trust attestation stage
   - run one trust attestation review stage over the frozen handoff
   - compute final trust `analysis_review_status` from bounded `final_analysis` plus
     the attestation review payload

Guardrails:

- do not let final stage selectors pick bounded producer review stages
- do not let attestation mode fabricate a second trust-authored `final_analysis`
- keep `apply_final_artifacts(summary)` untouched

### 5. Semantic validation in `anvil/harness/semantic_validation.py`

Add attestation-mode review invariants on top of today's trust validation:

- when `contract.mode == "trust"` and
  `contract.trust_review.execution_mode == "attestation_over_bounded"`:
  - `recommendation_reviews` must densely cover every bounded recommendation index
  - no attested index may exceed the bounded draft length
  - closure proof must stay scoped to the bounded recommendation universe
  - provenance refs must remain concrete, normalized, and in-workspace

Validation source of truth:

- use the frozen handoff's recommendation count and evidence universe
- do not infer expected coverage from a new trust-authored draft because that draft
  must not exist

### 6. Contract docs in `docs/analysis_review_contract.md`

Add one compact subsection for `trust_review.execution_mode`:

- `legacy_full_review` means today's full trust lane
- `attestation_over_bounded` means trust reviews the frozen bounded draft
- the public trust strategy kind does not change
- publication semantics remain runner-owned and unchanged in M2

### 7. Example strategies

Add new example strategies instead of mutating the current trust examples:

- `analysis_review_trust_attestation_codex_claude.yaml`
- `analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml`
- `analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml`

Rules:

- same providers and role lineup as current trust examples unless tests prove otherwise
- set only `trust_review.execution_mode: attestation_over_bounded`
- leave existing trust YAMLs on `legacy_full_review`

## Test Review

### Test framework and execution

This repo already uses `pytest`. M2 stays inside the existing Python test surface.
There is no separate external eval harness required for this slice. Prompt behavior
is locked with prompt-consistency tests, not a new eval subsystem.

### Code path coverage diagram

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/types.py
    |
    └── StrategyConfig trust_review.execution_mode
        ├── default -> legacy_full_review
        ├── explicit attestation_over_bounded
        └── invalid literal / unknown key failure

[+] anvil/harness/contracts.py
    |
    └── build_analysis_review_contract(...)
        ├── bounded strategy -> mode=bounded, execution_mode=legacy_full_review
        ├── trust strategy + legacy mode
        └── trust strategy + attestation mode

[+] anvil/harness/runner.py
    |
    └── _run_analysis_review_v1(...)
        ├── bounded mode -> unchanged
        ├── trust + legacy_full_review -> unchanged
        └── trust + attestation_over_bounded
            ├── focus gate once
            ├── bounded producer helper
            ├── frozen bounded_attestation_input persisted
            ├── final_analysis reused from bounded producer
            ├── trust attestation review stage
            └── final status/provenance resolves from attestation stage only

[+] anvil/harness/prompts.py
    |
    └── build_trust_attestation_review_prompt(...)
        ├── references frozen handoff explicitly
        ├── demands dense recommendation verdict coverage
        └── forbids replacement analysis payload

[+] anvil/harness/semantic_validation.py
    |
    └── attestation-mode coverage validation
        ├── missing recommendation index -> fail
        ├── out-of-range index -> fail
        ├── malformed closure proof -> fail
        └── legacy trust validation -> unchanged

[+] anvil/harness/reporting.py
    |
    └── apply_final_artifacts(...)
        └── regression coverage only, no code changes
```

### Required tests by file

#### `tests/test_harness_analysis_contract.py`

Add tests proving:

- strategy parsing accepts and round-trips `trust_review.execution_mode`
- default remains `legacy_full_review`
- invalid execution-mode literals fail loudly
- trust strategies may serialize `attestation_over_bounded` without changing
  `effective_strategy`

#### `tests/test_harness_prompt_consistency.py`

Add tests proving:

- the attestation prompt references the frozen handoff explicitly
- the attestation prompt requires dense recommendation coverage
- the attestation prompt forbids drafting a replacement analysis payload
- legacy trust prompt text remains unchanged

#### `tests/test_harness_runner.py`

Add runner-path tests proving:

- legacy trust still enters the proposer-first path
- attestation trust enters bounded producer first
- attestation trust runs persist `bounded_attestation_input`
- attestation trust runs reuse bounded `final_analysis`
- final provenance and final review-stage selection resolve from the attestation
  stage, not the bounded producer review stages

#### `tests/test_harness_semantic_validation.py`

Add validation tests proving:

- missing attestation review coverage for a bounded recommendation fails
- out-of-range attestation review indices fail
- malformed closure proof in attestation mode fails
- legacy trust validation behavior is unchanged

#### Existing reporting regression coverage

Do not add reporting code changes, but run the existing reporting tests to prove no
artifact-selection regression slipped in:

- `poetry run pytest -q tests/test_harness_reporting.py -k "apply_final_artifacts"`

### Fixture parity matrix

Minimum parity matrix:

1. seam focus, adjudicate path
2. seam focus, deliberate path
3. artifact focus, adjudicate path
4. artifact focus, deliberate path

For each case, compare:

- legacy trust
- attestation trust

Parity checks:

- same `focus_decision`
- same bounded candidate answer payload
- same or stricter trust admissibility outcome
- no regression in final artifact selection

### Validation commands for M2

- `poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"`
- `poetry run pytest -q tests/test_harness_prompt_consistency.py -k "attestation or trust"`
- `poetry run pytest -q tests/test_harness_runner.py -k "attestation or bounded_attestation_input"`
- `poetry run pytest -q tests/test_harness_semantic_validation.py -k "attestation or bounded_attestation_input"`
- `poetry run pytest -q tests/test_harness_reporting.py -k "apply_final_artifacts"`

## Failure Modes Registry

| Failure mode | Test coverage required | Error handling required | User-visible risk if missed |
|---|---|---|---|
| Execution mode parses but runner ignores it | runner branch test | explicit branch selection based on contract mode + execution mode | fake cutover, operators think trust changed when it did not |
| Attestation mode emits a second trust-authored draft | runner test plus prompt-consistency test | hard guard that final analysis comes from bounded producer | architecture drift, more complexity, misleading summaries |
| Producer review stages contaminate final trust provenance | runner stage-selection test | isolate producer and attestation phases in runner-local stage bookkeeping | wrong publishability decision from the wrong review surface |
| Attestation reviewer skips one recommendation index | semantic-validation test | dense coverage invariant keyed to bounded handoff length | silent truth gap in final answer eligibility |
| Attestation review references non-workspace evidence | semantic-validation test | normalized path and evidence subset validation | false provenance claims |
| M2 changes final artifact selection | reporting regression test | no code changes in reporting path | accidental M3 leak and user-facing artifact drift |

Critical gap rule for M2: any failure mode with no test and no runner-side defense
blocks completion.

## Performance and Operational Notes

- Token/runtime goal: attestation mode should be cheaper than legacy trust because it
  removes the second full trust generation lane.
- Memory/summary goal: the summary should carry one bounded final analysis plus one
  trust review payload, not two parallel answer drafts.
- Operational goal: the frozen handoff must be inspectable in saved summaries so
  replay/debugging can explain exactly what trust attested.

## What Already Exists

Reuse, do not rebuild:

- bounded producer proposer/critic/reviser/auditor loop
- bounded handoff builder and validator
- trust review payload schema and most trust validation rules
- runner-owned final artifact projection

If implementation starts cloning these into new helpers with slightly different
names, stop. That is duplication, not progress.

## Not In Scope

These are explicitly not M2:

- rewriting `anvil/harness/report.py` or `anvil/harness/reporting.py`
- changing `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, or `BEST_DRAFT.*` semantics
- changing README product copy
- retiring the old trust lane
- generalized intent-intake or multi-workflow routing
- richer provenance artifacts beyond the existing frozen handoff
- new provider wrappers, orchestration frameworks, or schema families

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| 1. Strategy/config surface | `anvil/harness/types.py`, `anvil/harness/contracts.py`, `tests/test_harness_analysis_contract.py` | — |
| 2. Attestation prompt + validation surface | `anvil/harness/prompts.py`, `anvil/harness/semantic_validation.py`, `tests/test_harness_prompt_consistency.py`, `tests/test_harness_semantic_validation.py` | Step 1 contract shape |
| 3. Runner cutover | `anvil/harness/runner.py`, `tests/test_harness_runner.py` | Step 1 contract shape, Step 2 prompt/validation interface |
| 4. Docs + example strategies | `docs/analysis_review_contract.md`, `examples/harness/strategies/` | Step 1 finalized knob name |
| 5. Regression sweep | `tests/test_harness_reporting.py` execution only, full pytest selection | Steps 2-4 |

### Parallel lanes

Lane A: Step 1 -> Step 4  
Sequential because both steps depend on the final knob name and public config shape.

Lane B: Step 2  
Independent after Step 1. Prompt/validation work can proceed in parallel with docs/examples.

Lane C: Step 3  
Starts after Step 2 interface is stable. Sequential inside the lane because all real
orchestration risk is concentrated in `anvil/harness/runner.py`.

Lane D: Step 5  
Launch after A, B, and C merge. This is the proof lane.

### Execution order

1. Land Step 1 first. It defines the only allowed config surface.
2. Launch Lane A Step 4 and Lane B Step 2 in parallel worktrees.
3. Once Step 2 is stable, launch Lane C Step 3.
4. Merge A + B + C.
5. Run Lane D as the final regression sweep.

### Conflict flags

- Lane B and Lane C both touch `anvil/harness/` and both influence runner-facing
  semantics. Coordinate on prompt/validation interfaces before Lane C starts.
- All runner work belongs in one lane. Do not split `anvil/harness/runner.py` across
  multiple worktrees.
- Test files may be edited in parallel only if ownership is explicit:
  - contract tests -> Step 1 owner
  - prompt/semantic tests -> Step 2 owner
  - runner tests -> Step 3 owner

## Definition of Done

Do not call M2 complete until all of these are true:

- strategy-level `trust_review.execution_mode` is real and tested
- new attestation example strategies exist
- attestation-mode trust runs execute bounded producer first
- attestation-mode trust runs persist and consume `bounded_attestation_input`
- attestation-mode trust runs do not create a second trust-authored analysis payload
- attestation-mode trust reuse of bounded `final_analysis` is covered by tests
- parity matrix covers seam + artifact focus-gate cases
- reporting/artifact selection regressions are absent
- the final summary still reads like one system, not two partially merged lanes

That is the exact M2 shape.
