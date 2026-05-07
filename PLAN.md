# PLAN: Trust Attestation Over Bounded Output, M2 Only

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260504-211401.md`
Supersedes: the prior M1-only `PLAN.md` on this branch

## Plan Summary

M1 is closed.

The repo now has a real `bounded_attestation_input` handoff, but trust still runs
as a full review lane from raw task + workspace. M2 is the slice that makes the
new architecture real without touching publication semantics yet:

- keep `analysis_review_trust_v1` as the public trust strategy kind
- make `trust_review.execution_mode` a real strategy-level cutover knob
- for `attestation_over_bounded`, run a bounded producer lane first
- freeze the producer result into `bounded_attestation_input`
- run trust as an attestation review over that frozen object
- keep final artifact selection and publishability logic unchanged for now

If M2 starts rewriting reporting or artifact selection, it is leaking into M3.

## M1 Validation Verdict

M1 landed the right thing.

Evidence from the current branch:

- `build_analysis_review_contract(...)` now serializes
  `trust_review.execution_mode`, but it is still hardcoded to
  `legacy_full_review` in [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:316).
- bounded runs build and persist the handoff before final summary assembly in
  [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:311).
- the handoff builder exists and validates schema + semantics in
  [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:1716).
- the handoff is documented as runner-owned and explicitly marked "M1 emits, M2 consumes"
  in [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md:63).
- trust still does not consume the handoff. The trust path still starts from a raw
  proposer prompt in [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:628).

Validation commands run on this branch:

- `poetry run pytest -q tests/test_harness_runner.py -k "bounded_attestation_input"`
- `poetry run pytest -q tests/test_harness_semantic_validation.py -k "bounded_attestation_input"`
- `poetry run pytest -q tests/test_harness_analysis_contract.py -k "bounded_attestation_input or execution_mode or contract_docs_freeze"`

Result: `19 passed`.

## Success Criteria

M2 is done only when all of these are true:

- trust strategies can opt into `trust_review.execution_mode=attestation_over_bounded`
  without changing the public `analysis_review_trust_v1` strategy kind
- attestation-mode trust runs produce a bounded source draft internally before trust
  review begins
- attestation-mode trust runs persist the frozen `bounded_attestation_input` they
  actually consumed
- the final trust run reuses the bounded producer's final analysis payload as the
  candidate answer source instead of generating a second trust-authored analysis lane
- trust attestation returns recommendation verdicts, closure proof, and provenance
  over the bounded draft with dense recommendation coverage
- legacy trust mode with `execution_mode=legacy_full_review` still behaves exactly
  like today's trust path
- `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, `BEST_DRAFT.*`, and
  `analysis_review_status.publishability` do not require logic changes in M2

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | M2 decision |
|---|---|---|
| Strategy surface for trust mode | `StrategyConfig` in [anvil/harness/types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py:645) | Extend strategy parsing so `trust_review.execution_mode` is real input, not dead metadata. |
| Shared contract field | `TrustReviewPolicy.execution_mode` in [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:177) | Reuse this exact field. Do not invent a second cutover knob. |
| Bounded producer lane | `_run_analysis_review_v1(...)` in [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:628) | Extract reusable bounded-producer helpers from the current lane instead of building a second producer implementation. |
| Frozen handoff contract | `_build_bounded_attestation_input(...)` in [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:1716) | Reuse the M1 handoff. Do not redesign the payload in M2. |
| Shared review payload schema | `analysis_review_schema()` in [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:632) | Keep the shared review JSON family. Attestation emits review payloads, not a new review schema family. |
| Trust prompt guidance | trust policy blocks in [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:535) | Add attestation-specific prompt builders instead of overloading the bounded proposer/reviser builders with branching prose. |
| Trust publication truth | `_build_analysis_review_status(...)` and artifact projection in [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:2951) and [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py:1470) | Hold this stable in M2. M3 owns publication cutover. |

### Minimum complete change set

The smallest complete M2 change should touch these surfaces:

1. `anvil/harness/types.py`
2. `anvil/harness/contracts.py`
3. `anvil/harness/runner.py`
4. `anvil/harness/prompts.py`
5. `anvil/harness/semantic_validation.py`
6. `docs/analysis_review_contract.md`
7. `examples/harness/strategies/analysis_review_trust_attestation_codex_claude.yaml`
8. `examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml`
9. `examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml`
10. `tests/test_harness_runner.py`
11. `tests/test_harness_prompt_consistency.py`
12. `tests/test_harness_semantic_validation.py`
13. `tests/test_harness_analysis_contract.py`

Avoid touching `anvil/harness/report.py`, `anvil/harness/reporting.py`, and `README.md`
unless a failing regression proves the plan wrong.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Public trust strategy kind | keep `analysis_review_trust_v1` | Preserve current product surface and examples. |
| M2 cutover knob | strategy-level `trust_review.execution_mode` | The contract already has this field. Make it real. |
| Default execution mode | `legacy_full_review` | Existing trust runs must remain stable until the new path is chosen deliberately. |
| New example strategy shape | add new attestation example YAMLs, leave old trust YAMLs untouched | Compatibility must be explicit, not magical. |
| Focus gate timing | run once, before bounded production | Trust should attest the same selected focus the bounded producer used. |
| Producer source of truth | internal bounded producer lane reusing today's bounded flow | One real producer. No duplicate implementation. |
| Trust attestation output | review payload only, no second trust-authored analysis payload | Trust attests the draft. It does not become a second drafter again. |
| Final analysis for trust attestation mode | bounded producer `final_analysis` becomes the final answer source | Keeps M2 out of M3 publication and artifact logic. |
| Handoff persistence | persist `bounded_attestation_input` in attestation-mode trust summaries too | The consumed object must be inspectable after the run. |
| Publication logic | unchanged in M2 | M3 owns reporting and publication cutover. |
| Provider surface | no provider wrapper unless the current role request shape truly cannot express attestation prompts | Avoid speculative plumbing. |

## Runtime Shape

### Legacy trust path, unchanged

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

### M2 attestation path

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

### Critical boundary

The attestation review must not write a second `final_analysis`.

In `attestation_over_bounded` mode:

- `run_details["final_analysis"]` comes from the bounded producer lane
- `run_details["bounded_attestation_input"]` is the exact frozen object the trust review consumed
- trust review contributes the final `recommendation_reviews`, `issue_ledger`,
  `topic_ledger`, provenance, and verdict

That is the whole game for M2.

## File-by-File Implementation Plan

### 1. Strategy parsing in `anvil/harness/types.py`

Add a small typed strategy config for trust execution:

- new `StrategyTrustReviewConfig`
- allowed key now: `trust_review.execution_mode`
- allowed literals:
  - `legacy_full_review`
  - `attestation_over_bounded`

Requirements:

- default remains `legacy_full_review`
- unknown keys under `trust_review` fail loudly
- `StrategyConfig.to_dict()` round-trips the field

Non-goal:

- do not expose a second task-level trust execution knob in M2

### 2. Contract resolution in `anvil/harness/contracts.py`

Change `build_analysis_review_contract(...)` so `TrustReviewPolicy.execution_mode`
comes from the parsed strategy config instead of being hardcoded at
`legacy_full_review`.

Requirements:

- bounded and legacy analysis-review strategies still serialize
  `legacy_full_review`
- trust strategies may choose either execution mode
- `effective_strategy` remains unchanged

### 3. Attestation prompt builders in `anvil/harness/prompts.py`

Add dedicated prompt builders for attestation review over the frozen handoff.

Minimum builder:

- `build_trust_attestation_review_prompt(...)`

Input context must include:

- `bounded_attestation_input`
- bounded `focus_decision`
- bounded review surface summary
- the current workspace snapshot
- the trust contract

Prompt rules:

- review the frozen bounded draft, do not regenerate recommendations from scratch
- return review verdicts for every bounded recommendation index
- use `recommendation_reviews` as the primary attestation surface
- use closure-review arrays only for `recommendation_index = null` global proof
- re-check workspace evidence directly before attesting, do not trust the handoff blindly
- do not emit a replacement analysis payload

Do not jam this into `build_analysis_critic_prompt(...)`. The jobs are different.

### 4. Runner cutover in `anvil/harness/runner.py`

Split the current monolithic trust flow into two explicit branches:

- `legacy_full_review` -> existing path
- `attestation_over_bounded` -> new path

Required extraction:

- one helper for the reusable bounded producer lane
- one helper for trust attestation review

The new runner shape should look like this:

1. resolve trust contract
2. run focus gate once
3. if `legacy_full_review`, keep existing flow
4. if `attestation_over_bounded`:
   - derive an internal bounded producer contract
   - run the bounded producer lane with the existing proposer/critic/reviser/auditor logic
   - capture its final analysis payload, review summary, and handoff
   - keep producer stage artifacts logically separate from the final trust attestation stage
   - reset final trust review state so attestation provenance/status only sees the attestation review stage
   - run one trust attestation review stage over the frozen handoff
   - compute final trust `analysis_review_status` from bounded `final_analysis` plus attestation review payload

Guardrails:

- do not let `_latest_successful_stage(role_names={"critic", "auditor"})` accidentally
  read bounded-producer review stages as the final trust review stage
- do not let attestation mode fabricate a second trust-authored `final_analysis`
- keep `apply_final_artifacts(summary)` untouched in M2

### 5. Semantic validation in `anvil/harness/semantic_validation.py`

Add attestation-mode review invariants on top of today's trust validation:

- when `contract.mode == "trust"` and
  `contract.trust_review.execution_mode == "attestation_over_bounded"`:
  - `recommendation_reviews` must cover every bounded recommendation index densely
  - no attested recommendation index may exceed the bounded draft length
  - attestation closure proof must stay scoped to the bounded recommendation universe
  - provenance refs must still be concrete, normalized, and in-workspace

Validation source of truth:

- use the bounded handoff's recommendation count and evidence universe
- do not infer expected coverage from a new trust-authored draft

### 6. Contract docs in `docs/analysis_review_contract.md`

Add one compact subsection for `trust_review.execution_mode`:

- `legacy_full_review` means today's full trust lane
- `attestation_over_bounded` means trust reviews the frozen bounded draft
- the public trust strategy kind does not change
- M2 keeps publication semantics runner-owned and unchanged

### 7. Example strategies

Add new example strategies instead of mutating the current trust examples:

- `analysis_review_trust_attestation_codex_claude.yaml`
- `analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml`
- `analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml`

Rules:

- same providers and role lineup as current trust examples unless tests prove otherwise
- set only `trust_review.execution_mode: attestation_over_bounded`
- leave existing trust YAMLs on `legacy_full_review`

## Test Plan

### Contract and parsing

Add tests proving:

- strategy parsing accepts and round-trips `trust_review.execution_mode`
- default remains `legacy_full_review`
- invalid execution-mode literal fails loudly

### Runner path coverage

Add tests proving:

- legacy trust strategies still enter the current proposer-first path
- attestation trust strategies enter bounded producer first
- attestation trust runs persist `bounded_attestation_input`
- attestation trust runs reuse bounded `final_analysis`
- attestation trust provenance/status derives from the attestation review stage, not the bounded producer review stage

### Prompt coverage

Add tests proving:

- attestation prompt text references the frozen handoff explicitly
- attestation prompt forbids drafting a replacement analysis payload
- legacy trust prompt text remains unchanged

### Semantic validation

Add tests proving:

- missing attestation review coverage for a bounded recommendation fails
- out-of-range attestation review indices fail
- malformed closure proof in attestation mode fails
- legacy trust validation behavior is unchanged

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

## Failure Modes Registry

| Failure | Why it matters | M2 defense |
|---|---|---|
| Execution mode is parsed but ignored | Fake cutover, worst kind of config | explicit branch tests in runner |
| Attestation path still generates a second trust draft | architecture lie, more complexity not less | forbid second trust-authored `final_analysis` |
| Bounded producer review stages contaminate final trust provenance | publishability gets computed from the wrong review surface | isolate stage bookkeeping between producer and attestor |
| Attestation review skips a bounded recommendation index | silent truth gap in final answer eligibility | dense coverage validation |
| M2 silently changes artifact selection | accidental M3 leak | keep reporting/artifact logic frozen and regression-test it |

## Not In Scope

These are explicitly not M2:

- rewriting `report.py` or `reporting.py`
- changing `FINAL_ANSWER.*` / `PARTIAL_ANSWER.*` / `BEST_DRAFT.*` semantics
- changing README product copy
- retiring the old trust lane
- removing the M2 compatibility shim from older focus-gate work
- generalized intent-intake or multi-workflow routing

## Done Checklist

Do not call M2 complete until all of these are true:

- strategy-level `trust_review.execution_mode` is real and tested
- new attestation example strategies exist
- attestation-mode trust runs execute bounded producer first
- attestation-mode trust runs persist and consume `bounded_attestation_input`
- attestation-mode trust runs do not create a second trust-authored analysis payload
- legacy trust examples and behavior still work
- parity matrix covers seam + artifact request-gate cases
- reporting/artifact selection regressions are absent

That is the exact M2 shape.
