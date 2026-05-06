# PLAN: Trust Attestation Over Bounded Output

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Supersedes: the prior `PLAN.md` for M4 request-gate productization and the design draft at `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260502-155217.md`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260504-211401.md`
Implementation baseline: M4 request-gate work is already landed on this branch and is not part of this change

## Summary

This plan changes trust mode from "a second full answer-generation lane" into "an
attestation pass over bounded output." Bounded remains the only answer producer.
Trust becomes a narrower verifier that re-checks bounded recommendations, closure
proof, and publication safety, then hands control back to the runner for final
artifact selection.

The key constraint is stability. The branch just finished hardening request-gate
behavior. This plan must not turn that stabilization pass into a stealth rewrite.
The implementation stays inside the existing harness surfaces, keeps the runner as
the publication authority, preserves `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`,
`BEST_DRAFT.*`, `REPORT.md`, and `summary.json`, and rolls out behind an explicit
compatibility switch before cutover.

## User Outcome

After this lands, users should feel a clean product distinction:

1. Bounded mode answers, "What should we recommend?"
2. Trust mode answers, "Which parts of that bounded answer are safe to publish as truth?"
3. Final publication still comes from runner-owned rules, not model-authored prose.

If users still experience trust as "the same review again, but stricter and noisier,"
the redesign failed.

## Success Criteria

This work is done only when all of these are true:

- bounded and trust have non-overlapping responsibilities that can be explained in one sentence each
- trust attestation can run end-to-end from a frozen bounded artifact without regenerating a fresh full answer from raw task input
- `analysis_review_status.recommendation_admissibility` and `analysis_review_status.publishability` remain runner-owned
- `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, `BEST_DRAFT.*`, `REPORT.md`, and `summary.json` remain deterministic
- the legacy trust path remains available until parity is proven
- fixture and regression coverage prove parity for accept, partial, and blocked publication outcomes
- the new path earns at least one measurable win: lower token cost, lower runtime, or materially simpler debugging behavior

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | Plan decision |
|---|---|---|
| Bounded vs trust contract split | [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:152) | Reuse the shared contract. Add one explicit trust execution-mode knob instead of a second strategy family. |
| Existing bounded review summary | [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:1525) | Reuse as source material, but do not overload it as the trust handoff. Build one new canonical handoff artifact from the same runner-owned data. |
| Trust review output schema | [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:579) | Reuse `analysis_review_schema()` for trust output. Do not mint a second trust response schema. |
| Trust provenance and closure-proof enforcement | [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:1755), [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:1879) | Keep these rules. Retarget them so the attestation pass proves verdicts against the frozen bounded handoff. |
| Trust review prompt guidance | [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:1002) | Reuse the review-payload semantics. Change the prompt to review bounded output, not to regenerate the world from scratch. |
| Runner-owned admissibility and publishability | [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:2552), [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:2808) | Preserve runner ownership exactly. Trust may supply evidence and blockers, but not canonical publication state. |
| Final artifact projection | [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py:1466), [anvil/harness/report.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py:805) | Reuse. Only change inputs and wording once attestation parity is proven. |
| Existing trust-attestation intent in backlog | [TODOS.md](/Users/spensermcconnell/__Active_Code/forge/TODOS.md:11) | This plan promotes that backlog item into the branch's primary implementation plan. |

### Minimum change set

The minimum complete implementation touches these surfaces:

1. `anvil/harness/contracts.py` for the trust execution-mode contract
2. `anvil/harness/runner.py` for frozen bounded handoff generation and trust-path routing
3. `anvil/harness/schemas.py` and `anvil/harness/semantic_validation.py` for handoff validation and attestation semantics
4. `anvil/harness/prompts.py` for the attestation prompt
5. `anvil/harness/report.py` and `anvil/harness/reporting.py` for final cutover and clearer publication explanations
6. `docs/analysis_review_contract.md`, `README.md`, and contract-doc tests
7. `tests/` for runner, semantic, prompt, reporting, and contract regression coverage

Do not add a new package. Do not add a new service layer. Do not add a new public
deliverable family.

### Complexity check

This will touch more than eight files. That is justified only if the conceptual
shape stays small:

- one new runner-owned handoff artifact
- one new trust execution mode
- no new workflow family
- no new provider abstraction unless the existing provider call surface physically cannot carry the new prompt
- no new report or summary format family

If implementation starts creating "attestation managers," "publication coordinators,"
or a second runner graph, stop. That is overbuilt for this repo.

### Search and boring-by-default check

This plan spends zero innovation tokens on infrastructure.

Reuse what already exists:

- the current contract builder
- the current analysis-review output schema
- the current semantic validation pipeline
- the current runner-owned status object
- the current artifact projection path
- the existing pytest suite and fixture strategy surface

The boring choice is right here. This is a harness decomposition, not a platform migration.

### Distribution check

This plan does not introduce a new binary, library package, container image, or
external service. Distribution work is limited to keeping the existing CLI and
example strategy surfaces runnable. That means:

- keep `python -m anvil` behavior unchanged for non-trust and legacy-trust runs
- provide at least one opt-in example strategy for the new attestation path before cutover
- do not defer the example strategy surface if manual parity validation depends on it

### Scope decision

Scope is locked to this:

- freeze a canonical bounded-to-trust handoff artifact
- add a new trust execution mode that consumes that artifact
- preserve runner-owned admissibility and publishability
- cut over artifact projection only after parity is proven
- keep the legacy trust path available until the end of the migration

## Decisions Locked

| Decision | Chosen option | Why | Rejected alternative |
|---|---|---|---|
| Canonical handoff name | `bounded_attestation_input` | Clear, literal, and scoped to exactly one job | Reusing `bounded_review_summary` and letting semantics drift |
| Canonical handoff persistence | Persist at `summary["bounded_attestation_input"]` and `summary["run_details"]["bounded_attestation_input"]` | Runner-owned, already mirrored through canonical persisted summary surfaces, no new user-facing artifact family | Writing a new top-level deliverable file or hiding the handoff only in transient memory |
| Handoff schema version | `analysis_review_bounded_attestation_input_v1` | Explicit contract for validation and migrations | Implicit schema inferred from whatever bounded output happens to look like |
| Trust execution-mode switch | `trust_review.execution_mode = legacy_full_review | attestation_over_bounded` | Minimal diff inside the existing contract | A new strategy kind or a second trust runner family |
| Trust response schema | Reuse `analysis_review_schema()` | Keeps downstream normalization, validation, report rendering, and status computation stable | A new attestation-only response schema |
| Publication ownership | Runner computes final `recommendation_admissibility` and `publishability` | Preserves the branch's strongest invariant | Model-authored final publication state |
| Legacy compatibility window | Keep legacy path until parity passes, then flip the default | Safe migration | Big-bang cutover |
| Provider integration | Stay on existing provider call surface unless prompt transport forces a wrapper | Minimal diff | Preemptive provider abstraction work |

## Architecture Plan

### Current leverage

The repo already has the right primitives, but they are split across two jobs inside
trust mode:

```text
request gate
    |
    v
analysis review producer
    |
    +--> bounded mode
    |       |
    |       v
    |   proposer -> critic -> revisers -> auditor -> runner publication
    |
    +--> trust mode
            |
            v
        proposer -> critic -> revisers -> auditor
            |
            v
        stricter provenance + closure proof + runner publication
```

That is the core problem. Trust still pays full answer-generation cost before it
gets to the part users actually value, which is attestation.

### Target runtime shape

```text
request gate
    |
    v
bounded producer path
    |
    v
final bounded analysis payload
    |
    v
Runner._build_bounded_attestation_input(...)
    |
    v
trust attestation pass
    |
    v
analysis_review_schema() review payload
    |
    v
Runner._build_analysis_review_status(...)
    |
    v
apply_final_artifacts(...)
    |
    +--> FINAL_ANSWER.*
    +--> PARTIAL_ANSWER.*
    +--> BEST_DRAFT.*
```

### Contract: bounded attestation input

`bounded_attestation_input` is the new frozen trust handoff. It is runner-owned.
It is built after bounded output is finalized and before trust attestation starts.
It is not a new public deliverable.

Required fields:

```text
bounded_attestation_input
├── schema_version = analysis_review_bounded_attestation_input_v1
├── source
│   ├── strategy_kind
│   ├── mode = bounded
│   ├── analysis_stage_role_name
│   ├── analysis_stage_index
│   └── bounded_payload_sha256
├── focus_decision
├── contract
│   ├── contract_version
│   ├── strategy_kind
│   └── trust_execution_mode
├── bounded_analysis
│   ├── summary
│   ├── recommendations[*]
│   ├── files_reviewed
│   ├── primary_seam
│   ├── secondary_seams_considered
│   ├── recommendation_seam_bindings
│   └── scope_escapes
├── review_surface
│   ├── recommendation_count
│   ├── review_stages
│   └── recommendations_with_review_surface
├── ledgers
│   ├── issue_ledger
│   └── topic_ledger
└── provenance_context
    ├── normalized_ref_count
    └── recommendation_evidence_index
```

Rules:

1. This artifact contains only what trust needs to attest the bounded answer.
2. It must not contain runner-finalized `publishability` or `recommendation_admissibility`.
3. Recommendation indices and order are frozen here. Trust may downgrade or reject them. Trust may not renumber them.
4. If this artifact cannot be built completely, trust attestation must fail closed and the run must keep the legacy path or stop before claiming attestation succeeded.

### Contract: trust attestation output

Trust output stays on the existing `analysis_review_schema()` shape. The meaning
changes, not the schema family.

Interpretation rules in attestation mode:

- `summary` is the attestation summary
- `recommendation_reviews[*]` are verdicts over bounded recommendations, not freshly invented recommendations
- `issues` and `topics` record attestation findings discovered while checking the bounded draft
- `issue_closure_reviews` and `topic_closure_reviews` remain the only structured proof for global closures
- `files_reviewed` lists files trust actually re-checked during attestation
- no model-authored field may claim final publishability or override runner-owned admissibility

### Exact stage rules

#### Rule 1: bounded remains the only answer producer

The bounded path still owns:

- recommendation generation
- primary/secondary seam binding
- evidence selection
- scope-escape disclosure
- best-draft materialization

Trust attestation must not regenerate a parallel recommendation set from raw task input.

#### Rule 2: `bounded_attestation_input` is built once, then frozen

Create the artifact after the final bounded analysis payload is resolved. Persist it
immediately into `summary` and `run_details`. All later trust steps read the same
frozen object.

No stage may mutate it in place.

#### Rule 3: legacy trust remains selectable

`trust_review.execution_mode` controls behavior:

- `legacy_full_review`: current trust path, unchanged
- `attestation_over_bounded`: new path, consumes `bounded_attestation_input`

The default stays `legacy_full_review` until Phase 3 cutover.

#### Rule 4: trust attestation consumes the frozen handoff, not a blank workspace story

The prompt should still include task and workspace context where needed for file
re-checks, but the primary review object is the frozen bounded artifact. Trust is
verifying bounded output, not pretending bounded never ran.

#### Rule 5: publication remains runner-owned

`Runner._build_analysis_review_status(...)` and `apply_final_artifacts(...)` continue
to decide:

- which recommendation indices are final-admissible
- which recommendation indices are partial-only
- whether `FINAL_ANSWER.*` may ship
- when fallback must drop to `PARTIAL_ANSWER.*` or `BEST_DRAFT.*`

#### Rule 6: cutover is isolated

Phase 1 and Phase 2 must land without changing default publication behavior for
trust runs. Publication cutover is Phase 3 only.

## Implementation Plan

## Phase 1: Freeze the bounded-to-trust handoff

### Goal

Define, build, persist, and validate one canonical `bounded_attestation_input`
artifact without changing trust runtime behavior yet.

### Files in scope

- [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py)
- [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py)
- [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py)
- [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py)
- [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md)
- [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py)
- [tests/test_harness_semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py)
- [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py)

### Implementation steps

1. Add `execution_mode` to `TrustReviewPolicy` with default `legacy_full_review`.
2. Add a schema/helper for `analysis_review_bounded_attestation_input_v1`.
3. Implement `Runner._build_bounded_attestation_input(run_details)` and call it only after bounded output is finalized.
4. Persist the result to `summary["bounded_attestation_input"]` and `summary["run_details"]["bounded_attestation_input"]`.
5. Add semantic validation for required fields, recommendation-index stability, and prohibition on runner-owned publication fields inside the handoff.
6. Document field ownership and invariants in `docs/analysis_review_contract.md`.

### Acceptance gate

Phase 1 is done only when:

- bounded runs emit the frozen handoff artifact deterministically
- legacy trust behavior is unchanged
- summary persistence mirrors the handoff in both top-level and `run_details`
- invalid or incomplete handoff payloads fail validation loudly

## Phase 2: Add the trust attestation execution path

### Goal

Teach trust mode to run in `attestation_over_bounded` mode while keeping the
legacy path intact.

### Files in scope

- [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py)
- [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py)
- [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py)
- [examples/harness/strategies](/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies)
- [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py)
- [tests/test_harness_prompt_consistency.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py)
- [tests/test_harness_semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py)

### Implementation steps

1. Add a runner branch that chooses trust execution shape from `trust_review.execution_mode`.
2. Keep the legacy trust path byte-for-byte stable where possible.
3. Add an attestation prompt path that supplies `bounded_attestation_input` as the primary review object.
4. Keep trust output on `analysis_review_schema()` and tighten semantics in prompt + validation:
   - every recommendation review maps to a bounded recommendation index
   - no new recommendation indices
   - no final publication claims
   - closure proof must still satisfy current structured-ref rules
5. Add at least one opt-in example trust strategy that enables `attestation_over_bounded` while the contract default remains `legacy_full_review`.
6. Add parity fixtures comparing legacy and attestation paths on the same bounded source cases.

### Acceptance gate

Phase 2 is done only when:

- both trust execution modes can run on the same repo
- attestation mode consumes the frozen bounded handoff and does not regenerate a second answer lane
- trust verdicts still produce valid recommendation reviews and closure proof
- parity fixtures cover accepted, partial, and blocked trust outcomes

## Phase 3: Cut over publication logic and retire legacy as the default

### Goal

Make `attestation_over_bounded` the primary trust path and align publication
reporting around that model.

### Files in scope

- [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py)
- [anvil/harness/report.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py)
- [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py)
- [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md)
- [README.md](/Users/spensermcconnell/__Active_Code/forge/README.md)
- [examples/harness/strategies](/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies)
- [tests/test_harness_reporting.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_reporting.py)
- [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py)

### Implementation steps

1. Flip the default trust example strategy surface to `attestation_over_bounded` only after Phase 2 parity is green.
2. Flip the `TrustReviewPolicy.execution_mode` default to `attestation_over_bounded` only in this phase, after the parity gate passes.
3. Keep `Runner._build_analysis_review_status(...)` as the only place that computes admissibility and publishability.
4. Update `apply_final_artifacts(...)` and report wording only where the new attestation path changes operator explanations.
5. Remove or hide legacy-full-review assumptions from trust docs and examples, but keep the compatibility mode available behind the explicit execution-mode switch until follow-up cleanup.
6. Prove that final artifact parity still holds across `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*`.

### Acceptance gate

Phase 3 is done only when:

- default trust examples run on attestation mode
- final artifact selection stays deterministic
- report wording explains publication blockers more clearly than before
- legacy mode remains available as an escape hatch, not the default story

## Architecture Review

### Dependency graph

```text
contracts.py
    |
    v
runner.py -----------------------> reporting.py
    |                                 |
    v                                 v
schemas.py -> semantic_validation.py  report.py
    ^
    |
prompts.py
```

Interpretation:

- `contracts.py` defines whether trust runs in legacy or attestation mode
- `runner.py` builds the frozen handoff and routes execution
- `schemas.py` and `semantic_validation.py` keep the handoff and trust output honest
- `prompts.py` changes what trust reviews, not what downstream consumers parse
- `reporting.py` and `report.py` only change once the new upstream behavior is proven

### Security and correctness boundaries

- The runner remains the authority for publication state
- Trust attestation must never publish recommendations the runner later marks ineligible
- Recommendation indices are stable across bounded output, trust attestation, summary persistence, and final artifact projection
- Closure proof remains structured-ref-based. `files_reviewed` alone is still not enough

### Realistic production failure scenario

If `bounded_attestation_input` drops a recommendation's evidence refs or seam binding,
trust may produce a clean accept against incomplete review context. That is worse than
an obvious crash because it creates false confidence. The plan handles this by freezing
the handoff contract, validating it, and failing closed when the handoff is incomplete.

## Code Quality Review

### Organization rules

- Keep new logic in helper functions inside existing harness modules
- Prefer one new builder helper and one validation helper over new classes
- Do not duplicate publication-state logic between the runner and reporting surfaces
- Do not duplicate trust semantics in both prompts and reporting. Prompts describe review behavior. The runner computes publication truth

### DRY rules to enforce

- one canonical builder for `bounded_attestation_input`
- one canonical validator for the handoff
- one trust execution-mode branch point
- one place that computes runner-owned admissibility and publishability

### Minimal-diff rules

- no new package
- no new workflow family
- no new stage family unless a new stage name is strictly required to keep persisted stage history understandable
- if a new stage name is introduced for attestation, document it and keep the legacy name stable for legacy mode

### Diagram maintenance

If nearby harness comments or docs contain ASCII diagrams of trust flow, update them
in the same change. A stale review-lane diagram after this refactor will mislead the
next person instantly.

## Test Review

### Test framework

Use the existing pytest suite. Primary commands:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_harness_analysis_contract.py
```

### CODE PATH COVERAGE

```text
CODE PATH COVERAGE TO ADD
=========================
[+] bounded handoff artifact
    |
    ├── Runner._build_bounded_attestation_input(...)
    |   ├── [NEW TEST] emits canonical payload from a successful bounded run
    |   ├── [NEW TEST] freezes recommendation order, indices, seam bindings, and refs
    |   ├── [NEW TEST] mirrors into summary + run_details without drift
    |   └── [NEW TEST] fails closed when bounded output is incomplete
    |
    └── semantic validation
        ├── [NEW TEST] rejects missing schema_version / source metadata
        ├── [NEW TEST] rejects runner-owned publishability fields in the handoff
        └── [NEW TEST] rejects non-deterministic recommendation ordering

[+] trust execution routing
    |
    ├── trust_review.execution_mode = legacy_full_review
    |   └── [REGRESSION TEST] current trust path remains unchanged
    |
    └── trust_review.execution_mode = attestation_over_bounded
        ├── [NEW TEST] trust prompt consumes bounded_attestation_input
        ├── [NEW TEST] trust cannot invent new recommendation indices
        ├── [NEW TEST] trust still emits structured closure proof
        └── [NEW TEST] missing handoff blocks attestation success

[+] runner-owned status and publication
    |
    ├── Runner._build_analysis_review_status(...)
    |   ├── [REGRESSION TEST] bounded mode unchanged
    |   ├── [NEW TEST] attestation-mode accepts direct-grounded recommendations as final-admissible
    |   ├── [NEW TEST] attestation-mode keeps caveated/inferred recommendations partial-only
    |   └── [NEW TEST] topic/global blockers still suppress final publication
    |
    └── apply_final_artifacts(...)
        ├── [REGRESSION TEST] FINAL_ANSWER parity preserved
        ├── [REGRESSION TEST] PARTIAL_ANSWER parity preserved
        └── [REGRESSION TEST] BEST_DRAFT fallback preserved
```

### USER FLOW / OPERATOR FLOW COVERAGE

```text
OPERATOR FLOW COVERAGE TO ADD
=============================
[+] Trust migration flows
    |
    ├── [NEW TEST] Legacy trust run remains available and produces current artifacts
    ├── [NEW TEST] Attestation trust run publishes FINAL_ANSWER when all accepted recommendations stay final-admissible
    ├── [NEW TEST] Attestation trust run falls back to PARTIAL_ANSWER when caveats or inferred grounding block final publication
    ├── [NEW TEST] Attestation trust run falls back to BEST_DRAFT when global blockers prevent partial publication
    └── [NEW TEST] Summary/report persistence stays index-consistent across all three outcomes

[+] Prompt and fixture parity
    |
    ├── [NEW TEST] Prompt instructions explicitly forbid regenerating fresh recommendations
    ├── [NEW TEST] Prompt instructions preserve closure-proof semantics
    ├── [NEW TEST] Opt-in attestation example strategy resolves through config/models.yaml
    └── [→ACCEPTANCE] Side-by-side fixture replays compare legacy vs attestation trust outputs on the same bounded source scenarios
```

### Regression rule

Any change that alters existing trust publication outcomes must add a regression test.
No exception. This branch already spent too much effort stabilizing artifact and
publication semantics to trust memory here.

### LLM/prompt change validation

This plan changes prompt behavior. There is no separate eval framework in the repo,
so the minimum acceptable substitute is:

1. prompt-consistency assertions in `tests/test_harness_prompt_consistency.py`
2. offline fixture parity in runner and semantic-validation tests
3. at least one opt-in manual acceptance run on the new strategy after pytest is green

The manual acceptance run is not a substitute for pytest. It is the last check, not the first.

## Performance Review

The main performance risks are token cost and duplicated serialization, not CPU or
database access.

### Risks and requirements

1. Do not send both the full bounded payload history and the frozen handoff to trust unless a field is genuinely missing from the handoff.
2. Build `bounded_attestation_input` once. Reuse it for summary persistence and trust input.
3. Keep payload hashing and normalized-ref indexing linear in recommendation count.
4. Measure both runtime and token delta between legacy trust and attestation trust on the same fixtures before cutover.

### Performance success bar

Record before/after numbers for:

- median trust-mode runtime on parity fixtures
- total prompt tokens for trust mode
- number of attestation-path failures that require hand-reading raw stage history to debug

The new path does not have to be faster to be worth it, but it does have to be
cheaper or easier to debug. Prefer both.

## Failure Modes Registry

| Codepath | Real failure mode | Test required | Error handling required | User/operator outcome |
|---|---|---|---|---|
| Handoff builder | Recommendation indices drift between bounded payload and frozen handoff | Yes | Hard validation failure | Operator sees explicit contract error, not silent mispublication |
| Handoff builder | Evidence refs or seam bindings omitted from frozen handoff | Yes | Hard validation failure | Trust attestation refuses to claim complete proof |
| Trust attestation routing | Attestation mode accidentally regenerates fresh recommendations | Yes | Prompt + semantic rejection | Prevents fake "independent" answers that drift from bounded |
| Trust closure proof | Global issue/topic closures lack structured proof refs | Yes | Existing semantic failure stays active | Run blocks from claiming trustworthy closure |
| Publication cutover | `FINAL_ANSWER.*` emitted when attestation leaves caveated/inferred recommendations partial-only | Yes | Runner-owned admissibility gate | Final artifact downgraded correctly |
| Reporting | `REPORT.md` and `summary.json` disagree on withheld indices | Yes | Artifact parity assertion | Operator sees one canonical truth |
| Compatibility | Legacy trust path removed before parity is proven | Yes | Strategy knob + regression test | Safe rollback remains possible |

Any row with "Yes / hard validation failure / silent otherwise" is a critical gap if untested.

## NOT in scope

- generalized intent intake beyond analysis review
- removing the M2 compatibility shim as part of this change
- redesigning the request gate
- replacing runner-owned publication authority with model-authored prose
- introducing a new deliverable family beyond `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, `BEST_DRAFT.*`, `REPORT.md`, and `summary.json`
- refactoring provider infrastructure unless the existing call surface cannot carry the attestation prompt
- changing bounded mode semantics beyond what is required to build the frozen handoff

## What already exists

- `bounded_review_summary` already captures bounded review-stage metadata. Reuse it as source input, not as the attestation contract.
- `analysis_review_status` already captures canonical admissibility, provenance, and publishability. Reuse it as the publication truth surface.
- trust prompt guidance and semantic validation already know how to reason about recommendation reviews and closure proof. Reuse that machinery against a tighter review object.
- `apply_final_artifacts(...)` already projects the three deliverable states correctly. Preserve that behavior and change inputs carefully.

## Worktree Parallelization Strategy

This plan has one real parallel window, but only after the contract foundation lands.

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| 1. Handoff contract foundation | `anvil/harness/`, `docs/` | — |
| 2. Trust attestation runner path | `anvil/harness/` | 1 |
| 3. Opt-in strategy and fixture scaffolding | `examples/harness/strategies/`, `tests/fixtures/harness/` | 1 |
| 4. Publication cutover and reporting | `anvil/harness/`, `docs/` | 2 |
| 5. Cross-cutting regression assertions | `tests/` | 2, 3, 4 |

### Parallel lanes

- Lane A: Step 1 -> Step 2 -> Step 4
  Sequential. Shared `anvil/harness/` ownership.
- Lane B: Step 3
  Launch after Step 1. Independent from runner implementation while the contract is stable.
- Lane C: Step 5
  Launch after Steps 2, 3, and 4 merge. This is test consolidation, not early implementation.

### Execution order

1. Land Step 1 first. No parallelism before the handoff contract exists.
2. Launch Lane A Step 2 and Lane B Step 3 in parallel worktrees.
3. Merge Lane B first if it only adds strategies and fixtures cleanly.
4. Complete Lane A Step 4 after Step 2 is stable.
5. Run Lane C last for final regression tightening.

### Conflict flags

- Steps 1, 2, and 4 all touch `anvil/harness/`. Do not parallelize them.
- Step 5 touches broad `tests/` surfaces and will conflict with almost anything if started early.
- If Step 3 starts modifying shared runner fixtures inside `tests/` instead of staying in fixture directories, pull it back into the main lane.

## Validation Commands

Minimum command set before calling this complete:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_harness_analysis_contract.py
poetry run python -m anvil.cli harness-run --task <task> --strategy examples/harness/strategies/<attestation-strategy>.yaml --workspace <repo> --out-root .forge-harness-runs
```

## Completion Summary

- Step 0: Scope Challenge, complete
- Architecture plan: concrete target flow and contract boundaries defined
- Code quality rules: explicit DRY, minimal-diff, and diagram-maintenance rules defined
- Test review: coverage plan and regression requirements defined
- Performance review: token/runtime measurement requirements defined
- NOT in scope: written
- What already exists: written
- Failure modes: written, with critical silent-failure cases identified
- Parallelization: 3 lanes total, 1 practical parallel lane after foundation

## Done means

Do not call this redesign done until all of these are true in the codebase:

- `bounded_attestation_input` exists, is validated, and is persisted deterministically
- trust can run in both `legacy_full_review` and `attestation_over_bounded`
- attestation mode does not regenerate fresh recommendations
- runner-owned admissibility and publishability remain canonical
- final artifacts stay deterministic across final, partial, and best-draft outcomes
- docs explain bounded vs trust in one sentence each
- parity data justifies making attestation the default trust path
