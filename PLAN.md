# PLAN: Trust Attestation Over Bounded Output, M1 Only

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260504-211401.md`
Supersedes: the prior multi-milestone `PLAN.md` on this branch

## Plan Summary

This plan is only for Milestone 1.

M1 freezes one canonical runner-owned `bounded_attestation_input` payload from an
already-completed bounded analysis run. The payload exists so a later milestone
can let trust attest a frozen bounded draft instead of regenerating a second full
answer lane.

M1 does not change trust execution, prompts, publication logic, report selection,
example strategies, or final deliverables. If this slice starts teaching trust
how to consume the new payload, the scope is wrong.

## Success Criteria

M1 is done only when all of these are true:

- bounded analysis runs persist a deterministic `bounded_attestation_input`
  payload in both `summary["bounded_attestation_input"]` and
  `summary["run_details"]["bounded_attestation_input"]`
- the payload is built only from finalized bounded-run state, not from proposer,
  critic, or partial reviser state
- the payload has an explicit schema version and deterministic serialization rules
- repo-local semantic validation fails loudly on missing, contradictory, or
  out-of-workspace handoff fields
- existing bounded final artifacts and existing legacy trust behavior remain
  unchanged
- no trust execution path reads the new payload yet

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | M1 decision |
|---|---|---|
| Shared analysis-review contract | `AnalysisReviewContract` and `TrustReviewPolicy` in `anvil/harness/contracts.py` | Extend the existing contract surface. Do not create a second workflow family. |
| Final bounded analysis resolution | `Runner._resolve_bounded_review_analysis_payload(...)` in `anvil/harness/runner.py` | Reuse this as the source of truth for finalized bounded output. |
| Existing bounded review surface summary | `Runner._build_bounded_review_summary(...)` in `anvil/harness/runner.py` | Reuse its finalized-analysis inputs and stage-derived review surface. |
| Shared review payload schema family | `analysis_review_schema()` in `anvil/harness/schemas.py` | Leave unchanged in M1. Trust output shape is not part of this milestone. |
| Existing semantic validation helpers | `anvil/harness/semantic_validation.py` | Add one handoff validator here instead of inventing a new validator stack. |
| Runner summary assembly | final summary construction in `Runner.run()` before `apply_final_artifacts(summary)` | Persist the handoff in the same runner-owned summary assembly path. |
| Contract docs and doc assertions | `docs/analysis_review_contract.md` and `tests/test_harness_analysis_contract.py` | Document the handoff in the existing contract doc and assert it there. |
| Strategic backlog intent | `TODOS.md` trust-attestation follow-up | Consume that backlog idea into a concrete M1 implementation slice. |

### Minimum complete change set

The smallest complete M1 change touches only these surfaces:

1. `anvil/harness/contracts.py`
2. `anvil/harness/runner.py`
3. `anvil/harness/schemas.py`
4. `anvil/harness/semantic_validation.py`
5. `docs/analysis_review_contract.md`
6. `tests/test_harness_runner.py`
7. `tests/test_harness_semantic_validation.py`
8. `tests/test_harness_analysis_contract.py`

Do not touch `anvil/harness/prompts.py`, `anvil/harness/report.py`,
`anvil/harness/reporting.py`, `examples/harness/strategies/`, `README.md`, or
`tests/test_harness_reporting.py` in M1 unless a failing regression proves this
plan wrong.

### Complexity check

This slice hits the eight-file smell threshold. That is already enough moving
parts. The implementation must stay boring:

- one new trust policy field
- one new schema helper
- one new runner builder path
- one new semantic validator entrypoint
- no new class family
- no new package
- no new public artifact file on disk

If the implementation starts growing "attestation managers", "handoff stores",
or "publication coordinators", stop. That is scope creep disguised as design.

### Search and boring-by-default check

M1 does not need new infrastructure. Reuse:

- the current dataclass-backed contract builder
- the existing summary assembly path in `Runner.run()`
- the current schema helper pattern in `anvil/harness/schemas.py`
- the existing semantic-validation helper style in
  `anvil/harness/semantic_validation.py`
- the current pytest organization

This is a harness decomposition slice, not a platform rewrite.

### TODOS cross-reference

`TODOS.md` already contains the relevant strategic follow-up:
"reshape trust mode into an attestation layer over bounded output." M1 consumes
that idea. Do not create new TODOs from this plan unless implementation reveals
follow-up work that is explicitly M2 or M3.

### Completeness check

The complete version is cheap here. Do not ship a half-contract.

M1 must do all of this together:

- build the payload
- validate it semantically
- mirror it consistently in summary output
- document it
- test deterministic behavior and failure paths

Shipping only the builder without validation, docs, and regression coverage would
save minutes and cost days later. Not acceptable.

### Distribution check

There is no new binary, package, container, or artifact family in M1.
Distribution impact is limited to preserving the current CLI and summary output
shape while adding one new runner-owned payload.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Scope | M1 only, bounded-run handoff freeze | Prevent M2 trust execution work from leaking in early |
| New contract field | `trust_review.execution_mode` | Minimal diff inside the existing contract surface |
| Allowed execution-mode literals | `legacy_full_review`, `attestation_over_bounded` | Gives M2 a real cutover knob without inventing a second contract family |
| Default execution mode | `legacy_full_review` | No behavior change in M1 |
| Handoff name | `bounded_attestation_input` | Clear, durable, and specific to the future trust handoff |
| Handoff schema version | `analysis_review_bounded_attestation_input_v1` | Explicit validation and future migration path |
| Handoff persistence | top-level summary mirror plus `run_details` mirror | Matches existing runner-owned artifact mirroring patterns |
| New artifact file | none | Keep deliverable vocabulary stable in M1 |
| Trust consumption | forbidden in M1 | Prevent accidental partial cutover |
| Publication fields in handoff | forbidden | Runner-owned truth stays runner-owned |
| README changes | forbidden in M1 | Contract documentation belongs in `docs/analysis_review_contract.md` for this slice |

## Architecture Overview

### Runtime shape after M1

```text
bounded run
    |
    v
final bounded analysis payload
    |
    +--> Runner._build_bounded_review_summary(...)
    |
    +--> Runner._build_bounded_attestation_input(...)
             |
             v
      run_details["bounded_attestation_input"]
      summary["bounded_attestation_input"]
```

Nothing else changes.

Trust still runs exactly the old way in M1.

### Dependency graph

```text
contracts.py
    |
    v
runner.py -------> schemas.py
    |                 |
    |                 v
    +----------> semantic_validation.py
    |
    v
summary.json / REPORT.md generation path
```

Important nuance:

- M1 may add the new payload into `summary.json`
- M1 must not change report selection or publication semantics
- `apply_final_artifacts(summary)` stays untouched

### Exact runner insertion point

The current final summary path in `Runner.run()` already does this in order:

1. build `bounded_review_summary`
2. finalize `analysis_review_status` and `focus_decision` into `run_details`
3. derive `final_answer`
4. build the `summary` dict
5. call `apply_final_artifacts(summary)`

M1 inserts the new handoff between steps 1 and 3:

1. build `bounded_review_summary`
2. build `bounded_attestation_input`
3. persist `run_details["bounded_attestation_input"]`
4. build `summary`
5. mirror `summary["bounded_attestation_input"]`
6. continue unchanged through `apply_final_artifacts(summary)`

The payload must be built from the same finalized bounded analysis object already
resolved by `_resolve_bounded_review_analysis_payload(...)`. Do not derive it
from proposer-only, critic-only, or partial reviser state.

## Canonical `bounded_attestation_input` Contract

### Required top-level shape

```text
bounded_attestation_input
├── schema_version
├── source
├── focus_decision
├── contract
├── bounded_analysis
├── review_surface
├── ledgers
└── provenance_context
```

### Required field rules

#### `schema_version`

- exact literal: `analysis_review_bounded_attestation_input_v1`
- centralize this literal in code, do not hand-type it in multiple builders

#### `source`

- `strategy_kind`
- `mode`, exact value `bounded`
- `analysis_stage_role_name`
- `analysis_stage_index`
- `bounded_payload_sha256`

`bounded_payload_sha256` is computed from canonical JSON bytes of the
`bounded_analysis` subsection only, using:

- sorted keys
- compact separators
- UTF-8 encoding
- no dependence on outer summary ordering

#### `focus_decision`

- mirror the runner-normalized `focus_decision` object when present
- otherwise persist `null`
- do not re-normalize or re-derive it here

#### `contract`

- `contract_version`
- `strategy_kind`
- `trust_execution_mode`

`trust_execution_mode` must serialize the contract field even though M1 never
consumes it.

#### `bounded_analysis`

Copy from the finalized bounded analysis payload only:

- `summary`
- `recommendations`
- `files_reviewed`
- `primary_seam`
- `secondary_seams_considered`
- `scope_escapes`

Recommendation order is canonical here. Do not sort or rewrite it.

#### `review_surface`

Build from the already-computed bounded review summary:

- `recommendation_count`
- `recommendations_with_review_surface`
- `review_stages`
- `scope_escape_count`

Use `bounded_review_summary` as the source of truth for these counts. Do not
recompute them with a parallel counting implementation unless the summary is
missing unexpectedly, in which case fail validation instead of silently drifting.

#### `ledgers`

- `issue_ledger`
- `topic_ledger`

Use `run_details` copies when present. Otherwise reuse the runner's serialized
ledger helpers.

#### `provenance_context`

- `normalized_ref_count`
- `recommendation_evidence_index`

`recommendation_evidence_index` is a deterministic mapping from 1-based
recommendation index string to canonical normalized evidence refs.

Normalization rule:

- use the existing workspace-ref canonicalization path
- preserve order
- dedupe preserving order

`normalized_ref_count` is the count of unique normalized refs across the full
evidence index after order-preserving dedupe.

### Hard invariants

1. Recommendation order is frozen by this payload.
2. `review_surface.recommendation_count` must equal
   `len(bounded_analysis.recommendations)`.
3. `source.mode` must be `bounded`.
4. `contract.trust_execution_mode` must exist and be one of the allowed literals.
5. The payload must not contain runner-owned publication state:
   `analysis_review_status`, `publishability`,
   `recommendation_admissibility`, `final_answer_publishable`, or any final
   artifact claim.
6. The payload must be deterministic for the same finalized bounded analysis
   input.
7. For bounded mode, missing or malformed handoff payload is an error, not a
   warning and not a silent `None`.

## File-by-File Implementation Plan

### 1. Contract update in `anvil/harness/contracts.py`

Add `execution_mode` to `TrustReviewPolicy`:

- allowed values:
  - `legacy_full_review`
  - `attestation_over_bounded`
- default value: `legacy_full_review`

Requirements:

- `TrustReviewPolicy.to_dict()` must serialize `execution_mode`
- `build_analysis_review_contract(...)` must set the field for bounded, trust,
  and legacy alias strategies
- `analysis_review_trust_v1` must still resolve `mode == "trust"` in M1
- `execution_mode` is metadata only in M1, not runtime routing

Done when:

- contract serialization exposes the field everywhere
- no existing strategy kind behavior changes

### 2. Schema helper in `anvil/harness/schemas.py`

Add:

- `bounded_attestation_input_schema() -> dict[str, Any]`

Requirements:

- `additionalProperties = False` at every new object layer
- `schema_version` required and fixed to the v1 literal
- `focus_decision` allows `null`
- `recommendations` must be an array with `minItems = 1`
- `review_stages`, `issue_ledger`, and `topic_ledger` must always serialize as
  arrays, even when empty
- `recommendation_evidence_index` keys are strings and values are string arrays

Explicit non-goal:

- do not modify `analysis_review_schema()`

### 3. Runner builder in `anvil/harness/runner.py`

Add:

- `Runner._build_bounded_attestation_input(run_details: dict[str, Any]) -> dict[str, Any] | None`

Behavior:

- return `None` only when there is no contract or `contract.mode != "bounded"`
- for bounded mode, resolve finalized analysis via
  `_resolve_bounded_review_analysis_payload(run_details)`
- consume the existing `bounded_review_summary` from `run_details` if present
- reuse runner-owned `issue_ledger`, `topic_ledger`, and `focus_decision`
- derive `recommendation_evidence_index` from finalized recommendation evidence
- compute `bounded_payload_sha256` from canonical JSON bytes of the
  `bounded_analysis` subsection
- validate before persistence

Persistence rules:

- build the payload once
- assign the same payload object to `run_details["bounded_attestation_input"]`
- mirror it into `summary["bounded_attestation_input"]`
- do not mutate the payload after persistence

Exact sequencing inside `Runner.run()`:

1. build `bounded_review_summary`
2. write `run_details["bounded_review_summary"]`
3. build `bounded_attestation_input`
4. write `run_details["bounded_attestation_input"]`
5. assemble `summary`
6. mirror `summary["bounded_attestation_input"]`
7. continue through draft extraction and `apply_final_artifacts(summary)` unchanged

Guardrails:

- no new public utility module for hashing
- if a private helper is needed, keep it near
  `_build_bounded_review_summary(...)`
- do not change `final_answer`, report rendering, artifact selection, or trust
  execution branches

### 4. Semantic validation in `anvil/harness/semantic_validation.py`

Add:

- `validate_bounded_attestation_input_payload(...)`

This validator is for runner-owned persisted state, not model-authored stage
output. Keep it separate from `validate_stage_output(...)`.

It must verify:

1. required fields exist
2. `schema_version` matches the fixed literal
3. recommendation ordering is dense, stable, and aligned with the bounded
   analysis list
4. every evidence ref is normalized and in-workspace
5. `normalized_ref_count` matches the derived unique normalized refs
6. every `review_surface` count matches the serialized arrays
7. forbidden runner-owned publication fields are absent
8. `source.mode` is `bounded`
9. `trust_execution_mode` exists and is one of the allowed literals

Failure mode:

- semantic validation error blocks the run and surfaces as a runner failure
- no best-effort fallback
- no warning-only mode

### 5. Contract docs in `docs/analysis_review_contract.md`

Add one dedicated subsection for `bounded_attestation_input` that states:

- it is runner-owned
- it is not a public deliverable
- it exists to freeze the future trust-attestation review object
- it intentionally excludes final publication truth
- M1 emits it, M2 consumes it
- `analysis_review_schema()` remains unchanged in M1

Do not rewrite broader bounded-vs-trust product docs here. This is a contract
freeze, not a README storytelling pass.

## Architecture Review

### Module responsibilities

| Module | Responsibility in M1 | Must not do |
|---|---|---|
| `contracts.py` | declare execution mode and serialize it | route runtime behavior |
| `schemas.py` | define handoff payload shape | redefine trust review output |
| `runner.py` | build, validate, and persist the handoff | let trust consume it |
| `semantic_validation.py` | reject incomplete or contradictory handoffs | silently coerce bad payloads |
| `docs/analysis_review_contract.md` | explain field ownership and invariants | promise M2 behavior as already landed |

### Production failure scenario

The real disaster case is recommendation-index drift.

If the frozen handoff changes recommendation order, drops evidence refs, or
serializes mismatched review-surface counts, M2 will later attest the wrong thing
while looking perfectly structured. That is why M1 treats ordering and evidence
normalization as hard validation failures, not cleanup work.

## Code Quality Review

### Guardrails

- keep the new builder next to `_build_bounded_review_summary(...)`
- prefer a small private helper over new classes
- keep naming literal and boring
- centralize only the truly shared literals that would otherwise drift:
  `bounded_attestation_input` and
  `analysis_review_bounded_attestation_input_v1`
- do not duplicate normalization logic already present in the runner or semantic
  validator

### Required implementation rules

1. One canonical builder for `bounded_attestation_input`
2. One canonical schema helper
3. One canonical semantic validator entrypoint
4. No prompt changes in M1
5. No publication-logic changes in M1

### Files that may deserve inline ASCII comments

If the builder or validator becomes non-obvious, add a short ASCII pipeline
comment in:

- `anvil/harness/runner.py` above `_build_bounded_attestation_input(...)`
- `anvil/harness/semantic_validation.py` above
  `validate_bounded_attestation_input_payload(...)`

Keep the comments tiny and accurate.

## Test Review

Framework: `pytest`

This repo already has the right test surface. M1 should add targeted coverage,
not invent a new harness.

### Code path coverage

```text
CODE PATH COVERAGE
==================
[+] contracts.py
    |
    └── TrustReviewPolicy.execution_mode
        ├── [GAP] default serializes as legacy_full_review
        ├── [GAP] bounded strategies serialize the field without changing mode
        └── [GAP] trust strategies serialize the field without changing runtime behavior

[+] runner.py
    |
    ├── _build_bounded_attestation_input(...)
    │   ├── [GAP] bounded mode builds payload from finalized analysis
    │   ├── [GAP] trust mode returns None
    │   ├── [GAP] focus_decision mirrors normalized runner state or null
    │   ├── [GAP] top-level and run_details mirrors are byte-equivalent
    │   └── [GAP] deterministic hash stays stable for identical input
    |
    └── summary assembly
        ├── [GAP] bounded runs persist the new payload before apply_final_artifacts(...)
        └── [GAP] existing final artifacts stay unchanged

[+] semantic_validation.py
    |
    └── validate_bounded_attestation_input_payload(...)
        ├── [GAP] missing schema_version fails
        ├── [GAP] invalid trust_execution_mode fails
        ├── [GAP] review_surface count mismatch fails
        ├── [GAP] evidence refs outside workspace fail
        ├── [GAP] forbidden publication fields fail
        └── [GAP] recommendation ordering drift fails

[+] docs/analysis_review_contract.md
    |
    └── contract doc assertions
        ├── [GAP] new payload is documented as runner-owned
        └── [GAP] M1 explicitly states analysis_review_schema() is unchanged
```

### Required test additions

#### `tests/test_harness_runner.py`

Add tests for:

- bounded runs persist `bounded_attestation_input`
- trust runs do not persist it in M1
- top-level and `run_details` mirrors are identical when serialized
- deterministic hashing for identical bounded payloads
- existing bounded artifact outputs remain unchanged after the new field is added
- validation failure blocks the run if the builder emits malformed attestation data

#### `tests/test_harness_semantic_validation.py`

Add tests for:

- missing `schema_version`
- missing `source.mode`
- non-bounded `source.mode`
- invalid `trust_execution_mode`
- recommendation index gaps or reordering
- mismatched `recommendation_count`
- mismatched `normalized_ref_count`
- forbidden publication fields present
- invalid evidence refs or out-of-workspace normalized refs

#### `tests/test_harness_analysis_contract.py`

Add tests for:

- `trust_review.execution_mode` serializes in bounded, trust, and legacy alias modes
- the new handoff artifact and its ownership are documented
- docs explicitly state `analysis_review_schema()` remains unchanged in M1

### Regression rule

Any failure where the new payload changes legacy bounded summary behavior, legacy
trust behavior, or final artifact selection requires a regression test before the
change is considered done. No exceptions.

### Test commands

Run at minimum:

```bash
poetry run pytest -q tests/test_harness_runner.py tests/test_harness_semantic_validation.py tests/test_harness_analysis_contract.py
```

Then run the full suite before merge:

```bash
poetry run pytest -q
```

## Performance Review

This slice is not runtime-heavy, but there are still two ways to make it stupid:

1. re-normalizing evidence refs repeatedly in multiple helpers
2. serializing large payloads more than once per run just to compute hashes and
   mirrors

Performance rules:

- canonicalize evidence refs once per attestation build path where possible
- hash only the `bounded_analysis` subsection, not the whole summary
- reuse already-resolved final analysis state
- avoid copying large nested structures more times than necessary

There is no caching work in M1. That would be premature.

## Failure Modes Registry

| Surface | Failure mode | Test required | Error handling required | User-visible risk |
|---|---|---|---|---|
| Contract | `execution_mode` omitted from serialized contract | yes | fail test | M2 has no trustworthy cutover knob |
| Builder | handoff built from non-final stage payload | yes | hard fail | later attestation targets the wrong recommendation set |
| Builder | top-level and `run_details` mirrors diverge | yes | hard fail | debugging becomes unreliable |
| Validation | recommendation indices drift | yes | hard fail | silent mis-attestation later |
| Validation | forbidden publishability fields leak into payload | yes | hard fail | runner-owned truth boundary erodes |
| Validation | evidence refs normalize outside the workspace snapshot | yes | hard fail | future attestation proves the wrong files |
| Docs | handoff ownership not documented | yes | test failure | later milestones re-litigate the contract |

Critical gap rule:

Any path that allows a malformed handoff to persist without a failing test and a
failing runtime validation is a release blocker for M1.

## NOT in Scope

- trust prompt changes
- trust execution path changes
- `analysis_review_schema()` changes
- publication logic changes
- `apply_final_artifacts(...)` changes
- `REPORT.md` wording changes
- README storytelling updates
- example strategy rewiring
- flipping any default from legacy trust to attestation trust
- side-by-side parity fixtures between legacy trust and attestation trust
- removal of the old trust path

Those are M2 or M3. Keep them out.

## Worktree Parallelization Strategy

Sequential implementation would work, but there is one safe parallel window after
the contract and field names are frozen.

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Lock contract literals and schema shape | `anvil/harness/contracts.py`, `anvil/harness/schemas.py`, `docs/` | — |
| B. Implement runner builder and summary persistence | `anvil/harness/runner.py` | A |
| C. Implement validator and validator tests | `anvil/harness/semantic_validation.py`, `tests/` | A |
| D. Add runner tests and doc assertions, then polish | `tests/`, `docs/`, `anvil/harness/runner.py` | B, C |

### Parallel lanes

- Lane A: Step A, sequential, shared contract and schema surfaces
- Lane B: Step B, sequential after A, shared runner surface
- Lane C: Step C, parallel with B after A, mostly validator plus test surface
- Lane D: Step D, sequential after B and C, final integration and regression pass

### Execution order

Launch Lane A first.

Once the field names and schema version are locked, launch Lane B and Lane C in
parallel worktrees.

Merge B and C, then run Lane D in the main worktree for final test alignment and
doc assertions.

### Conflict flags

- Lane A and Lane B both touch `anvil/harness/`, do not parallelize them before
  the contract names are frozen
- Lane C and Lane D both touch `tests/test_harness_semantic_validation.py` if D
  starts too early
- Lane B and Lane D both touch `tests/test_harness_runner.py`, expect merge
  pressure if D starts before B settles

## Exit Gate

Do not call M1 complete until all of these are true:

- `TrustReviewPolicy.execution_mode` exists and defaults to
  `legacy_full_review`
- `bounded_attestation_input_schema()` exists
- `Runner._build_bounded_attestation_input(...)` exists and only emits payloads
  for bounded mode
- both summary mirrors are identical when serialized
- semantic validation fails on malformed payloads
- docs explain ownership and scope correctly
- targeted tests pass
- full pytest passes
- trust execution and publication behavior are unchanged

## Completion Summary

- Step 0: Scope Challenge, scope reduced to M1 only
- Architecture Review: one new runner-owned handoff, no execution cutover
- Code Quality Review: no new classes, no new package, no new artifact family
- Test Review: targeted coverage required in runner, semantic validation, and
  contract docs
- Performance Review: minimal overhead, no caching work
- NOT in scope: written
- What already exists: written
- Failure modes: seven concrete failure paths called out
- Parallelization: four steps, one safe parallel window after contract lock

This is the whole game for M1. Freeze the handoff cleanly, prove it is stable,
and stop before the trust cutover starts sneaking in.
