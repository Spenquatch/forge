# PLAN: C2 Measurable Coverage Ledger and Assumptions Register

Status: ready for implementation on `codex/c1b-planning-quality-proof`  
Milestone: `C2`  
Prepared from repo state on: `2026-05-18`

Source of truth:
- `/home/azureuser/.gstack/projects/Spenquatch-forge/azureuser-codex-c1b-planning-quality-proof-design-20260518-165310.md`
- current repository code in `anvil/harness/`, `examples/harness/`, `tests/`, and `README.md`

Source note:
- The branch name is still `codex/c1b-planning-quality-proof`, but recent commits show the `C1b` slices already landed: live runtime (`7b24c2d`), integrity publication (`9fe5b04`), operator surface (`f17c68e`), and provider proof command (`a0bc27f`).
- This file supersedes the earlier root `C1b` plan. It is the authoritative `C2` implementation plan for this branch.

## Executive Summary

`C1a` proved that Forge can compile one deterministic planning strategy.
`C1b` proved that the strategy can inspect a live repo, emit `PLAN.md` and
`plan.json`, and stop honestly when the ask is ambiguous or out of corpus.

`C2` is the next proof. It does not widen planner breadth. It makes the current
planning artifact answer the skeptical question mechanically:

"What did this plan cover, what did it not cover, and which parts are still assumptions?"

This milestone adds one runtime-owned truth surface, published consistently in
both machine and human artifacts:

- `coverage_ledger`
- `assumptions_register`
- `uncovered_delta`

The implementation rule is strict:

- runtime owns the facts
- reporting serializes them
- validation gates them
- markdown renders them

No strategy-name branching. No post-hoc auditor inventing truth after the run.
No second planning pipeline.

## 1. Objective and Success Bar

### 1.1 Objective

Ship measurable coverage for the existing
`deterministic_feature_planning_v1` path by extending the shared planning
contract, runtime state, projection, validation, and render layers so one
planning run can publish:

- `plan.json` with explicit coverage, assumptions, and uncovered-delta records
- `PLAN.md` with a readable coverage summary that matches the JSON exactly
- `summary.json` with honest partial coverage on `clarification_needed` and
  `failed` runs

### 1.2 Problem Statement

The current planning artifact can tell you the plan.
It still cannot tell you the shape of its uncertainty.

Today the repo already publishes:

- `terminal_status`
- `run_mode`
- `repo_evidence_refs`
- `seams`
- `workstreams`
- `slices`
- `phase_results`

That is enough to describe structure.
It is not enough to prove completeness.

The missing product claim is not "more metadata."
It is "the artifact can say, deterministically and honestly, which planning
dimensions are covered, which are partial, which are uncovered, which claims
are assumptions, and what exact delta should drive the next refine pass."

### 1.3 Success Bar

`C2` is complete only when all of the following are true:

- successful planning runs emit `plan_artifact_v2`
- every required coverage dimension has exactly one ledger row
- coverage rows use declared strategy `phase_id` values, not `stage_type`, for
  all cross-record references
- assumption rows resolve from every linked `assumption_id`
- delta rows exist only for `partial` or `uncovered` coverage rows
- `PLAN.md` renders coverage, assumptions, and uncovered-delta sections in a
  fixed canonical order
- `summary.json` carries truthful partial coverage on
  `clarification_needed` and `failed`
- the runtime gains no `if strategy == ...` branches to make this work

## 2. Step 0: Scope Challenge

### 2.1 What already exists

| Sub-problem | Existing code | C2 decision |
|---|---|---|
| Runtime-owned planning state | `anvil/harness/state.py`, `anvil/harness/planning_runtime.py` | extend the existing `planning_*` surface, do not add a second planning store |
| Success artifact projection | `anvil/harness/reporting.py`, especially `plan_projection_v1()` and `publish_planning_artifacts_v1()` | extend the current projection path in place, do not create a coverage-only publisher |
| Success artifact schema | `anvil/harness/schemas.py`, `plan_json_schema()` | bump the planning artifact schema to v2 and require coverage fields there |
| Success artifact integrity gating | `anvil/harness/validation.py`, `validate_planning_success_artifacts()` | extend existing planning integrity checks with coverage invariants |
| Markdown rendering | `anvil/harness/reporting.py`, `render_plan_markdown_v1()` | extend the current planning markdown renderer in place, do not create a parallel renderer family |
| Example strategy and task corpus | `examples/harness/strategies/deterministic_feature_planning_v1.yaml`, `examples/harness/tasks/deterministic_feature_planning_*.yaml` | keep one canonical strategy, add one explicit `coverage_policy` version surface |
| Planning regression wall | `tests/test_harness_planning_graph.py`, `tests/test_harness_planning_artifacts.py`, `tests/test_harness_example_strategy_wiring.py`, `tests/test_harness_reporting.py`, `tests/test_harness_state_boundaries.py`, `tests/test_harness_strategy_graph.py` | reuse and widen the current planning tests rather than inventing a new harness |
| Ledger-style precedent | `analysis_review` provenance and topic-ledger surfaces in `anvil/harness/report.py`, `anvil/harness/reporting.py`, `anvil/harness/state.py` | reuse the pattern of stable IDs, projection discipline, and truth gating without coupling planning to analysis-review contracts |

### 2.2 Minimum complete scope

Skipping any item below turns `C2` into another pretty spec instead of a proof:

1. Extend the planning state and artifact contract with coverage, assumptions,
   and uncovered-delta fields.
2. Derive those fields inside `anvil/harness/planning_runtime.py` from the
   existing deterministic planning pass.
3. Render the new fields in `PLAN.md` and serialize them in `plan.json`.
4. Enforce schema and referential-integrity rules at publication time.
5. Preserve truthful partial publication in `summary.json` for blocked runs.
6. Update the canonical example strategy and tests so repeat runs prove stable
   ordering and stable IDs.

### 2.3 Complexity verdict

This work is cross-cutting. That is real.

It still fits the "engineered enough" bar because it stays inside existing
modules:

- no second planning engine
- no post-hoc coverage auditor service
- no second artifact pipeline
- no planner-family framework project
- no runnable refine adapter yet

The smell to avoid is not file count.
It is split authorship.

### 2.4 Search/build verdict

No new platform needs to be invented.

Reuse what already exists:

- `HarnessState` for durable graph state
- `PLANNING_POLICY_FIELDS` for strategy policy version lookup
- `plan_projection_v1()` for planning payload assembly
- `render_plan_markdown_v1()` for human-readable artifact rendering
- `validate_planning_success_artifacts()` for success-only integrity gating
- the existing planning example corpus and reporting tests for regression proof

This is a contract extension, not a platform rewrite.

### 2.5 Scope reduction opportunities rejected

The following shortcuts are tempting and wrong for this milestone:

- "Just add optional fields to `plan_artifact_v1` and call it done"
  Rejected because the contract meaning changes materially.
- "Create `plan_projection_v2()` and `render_plan_markdown_v2()` beside the
  current helpers"
  Rejected because that doubles the planning publication surface for one
  strategy and adds unnecessary drift risk.
- "Compute coverage in `reporting.py` from seams/workstreams/slices"
  Rejected because it would make projection own truth.
- "Emit uncovered delta only on success"
  Rejected because blocked runs are exactly where honest gap signaling matters.
- "Let assumptions hang off seams/workstreams/slices immediately"
  Rejected because that widens the blast radius for little product value in C2.

### 2.6 TODO cross-reference

`docs/project_management/future/TODOS.md` has no deferred item that blocks C2.
This milestone may create follow-on TODOs around multi-strategy coverage or a
real refine adapter, but those stay out of this branch.

### 2.7 NOT in scope

- widening planning beyond `deterministic_feature_planning_v1`
- a general planning-family coverage framework with per-strategy dimension
  inference
- a runnable refine-loop adapter or automatic re-planning workflow
- provider-backed review of coverage outputs
- per-object assumption refs on seams, workstreams, or slices
- new packaging or distribution channels beyond the existing CLI artifact path
- unrelated repo-wide cleanup

## 3. Locked C2 Decisions

These decisions are now frozen for implementation. Nothing later in this file
reopens them.

| Decision | Locked choice | Why |
|---|---|---|
| Artifact schema version | bump emitter to `plan_artifact_v2` | this is a material contract expansion, not a quiet additive tweak |
| Coverage owner | `anvil/harness/planning_runtime.py` | runtime owns truth, renderers do not invent or grade it |
| State field names | `planning_coverage_status`, `planning_coverage_ledger`, `planning_assumptions_register`, `planning_uncovered_delta` | consistent with existing `planning_*` naming |
| Success artifact field names | `coverage_status`, `coverage_ledger`, `assumptions_register`, `uncovered_delta` | artifact stays product-shaped, not state-shaped |
| Coverage vocabulary | fixed shared dimension set in runtime policy | explicit over clever, deterministic over inferred |
| Assumption linkage in C2 | assumptions link from coverage rows only, not directly from seams/workstreams/slices | minimal diff, avoids exploding the contract across every object |
| Non-success publication | `summary.json` always carries coverage payloads; `plan.json` and `PLAN.md` remain success-only | preserves the current success-artifact contract while keeping blocked runs honest |
| Refine loop scope | emit `uncovered_delta` only; do not ship a runnable refine adapter in C2 | prove the handoff contract before widening behavior |
| Helper strategy | upgrade existing planning helpers in place | minimal diff, no duplicated publication stack |
| Function naming | keep `plan_projection_v1()`, `render_plan_markdown_v1()`, and `publish_planning_artifacts_v1()` as the only planning publication helpers for now | the artifact version changes, not the helper family count |

## 4. Frozen C2 Coverage Contract

### 4.1 Shared coverage vocabulary

The canonical C2 coverage unit is `coverage_dimension`.

The fixed dimension set for this milestone is:

- `problem_frame`
- `repo_surface`
- `seam_selection`
- `dependency_shape`
- `execution_partitioning`
- `acceptance_shape`
- `risk_and_unknowns`

This dimension set is runtime-owned and versioned by policy.
It is not inferred from provider prose and not authored ad hoc per run.

### 4.2 Phase identifier rule

Every cross-record reference uses declared strategy `phase_id` values, not
`stage_type`.

For the current canonical strategy those are:

- `design_doc`
- `seam_decomposition`
- `parallel_planning`
- `slice_emission`

### 4.3 Coverage ledger shape

Each `coverage_ledger` row must contain:

- `coverage_id`
- `dimension`
- `status`
- `summary`
- `evidence_refs`
- `seam_ids`
- `workstream_ids`
- `slice_ids`
- `assumption_ids`
- `source_phase_ids`

Allowed `status` values:

- `covered`
- `partial`
- `uncovered`
- `not_applicable`

Invariants:

- exactly one row per required dimension
- deterministic ordering follows the dimension-set order above
- `coverage_id` format is `coverage-{index:02d}-{dimension}`
- `covered` and `partial` rows must include at least one `evidence_ref` or one
  structural ref
- `not_applicable` requires explicit rationale in `summary`
- `source_phase_ids` must be non-empty and resolve to declared strategy phases

### 4.4 Assumptions register shape

Each `assumptions_register` row must contain:

- `assumption_id`
- `statement`
- `kind`
- `status`
- `linked_coverage_ids`
- `evidence_refs`
- `source_phase_id`

Allowed `kind` values:

- `scope`
- `dependency`
- `acceptance`
- `environment`
- `risk`

Allowed `status` values:

- `active`
- `validated`
- `rejected`

Invariants:

- `assumption_id` format is `assumption-{index:02d}-{slug}`
- every `linked_coverage_id` must resolve to a declared coverage row
- rejected assumptions must not remain linked to rows whose summary still
  claims full confidence without being updated
- ordering is stable by first introduction order

### 4.5 Uncovered delta shape

Each `uncovered_delta` row must contain:

- `delta_id`
- `coverage_id`
- `dimension`
- `gap_kind`
- `required_input`
- `recommended_next_phase`
- `blocking_assumption_ids`

Allowed `gap_kind` values:

- `missing_evidence`
- `missing_structure`
- `assumption_blocked`
- `ambiguous_scope`

Invariants:

- only `partial` or `uncovered` coverage rows may emit delta entries
- every delta row must resolve to one coverage row
- ordering follows coverage-ledger order
- `recommended_next_phase` must be one declared `phase_id` or `clarify`
- every `blocking_assumption_id` must resolve to an assumptions-register row

### 4.6 State vs artifact ownership

State fields added in `anvil/harness/state.py`:

- `planning_coverage_status`
- `planning_coverage_ledger`
- `planning_assumptions_register`
- `planning_uncovered_delta`

Artifact fields added in `plan.json` and `summary.json`:

- `coverage_status`
- `coverage_ledger`
- `assumptions_register`
- `uncovered_delta`

Ownership model:

- runtime owns coverage facts
- projection owns serialization
- validation owns gating
- report rendering owns presentation

That is the whole cut.

### 4.7 Non-success behavior

Success:

- emit `PLAN.md`
- emit `plan.json`
- require all four coverage fields in the artifact payload

Clarification needed:

- do not emit `PLAN.md`
- do not emit `plan.json`
- `summary.json` must carry `coverage_status: clarification_needed`
- `coverage_ledger`, `assumptions_register`, and `uncovered_delta` must still
  be present as arrays, even if empty or partial

Failed:

- do not emit `PLAN.md`
- do not emit `plan.json`
- `summary.json` must carry `coverage_status: failed`
- no row may claim `covered` unless its evidence and linked structure were
  established before failure

## 5. Architecture Review

### 5.1 Current behavior gap

The repo already knows how to plan structure.
It does not yet know how to publish the shape of uncertainty.

Today the runtime can emit:

- deterministic seams
- deterministic workstreams
- deterministic slices
- deterministic terminal status

Today it cannot emit:

- one row per planning dimension explaining what is covered
- one assumptions registry explaining what the plan still depends on
- one uncovered-delta contract explaining what the next refine pass should ask
  for

### 5.2 Target architecture

```text
task yaml (task_kind=planning)
strategy yaml (runtime_target=planning_v1)
        │
        ▼
validator_preflight
        │
        └── planning contract sanity only
        │
        ▼
planning_v1 subgraph
        │
        ▼
execute_planning_runtime()
        │
        ├── derive problem statement, seams, workstreams, slices
        ├── derive coverage rows for the fixed dimension set
        ├── derive assumptions register from unresolved claims
        ├── derive uncovered delta from partial/uncovered dimensions
        ├── attach source_phase_ids using declared phase_id values
        └── stamp planning_coverage_status truthfully
        │
        ▼
plan_projection_v1()
        │
        ├── success: plan.json + PLAN.md + summary.json
        └── blocked: summary.json only
        │
        ▼
validate_planning_success_artifacts()
        │
        ├── schema_version
        ├── referential integrity
        ├── coverage invariants
        └── PLAN.md / plan.json parity
        │
        ▼
render_plan_markdown_v1()
```

### 5.3 Exact ownership map

| Concern | Canonical owner | Exact touch points | Required outcome |
|---|---|---|---|
| Runtime-owned planning truth | `anvil/harness/planning_runtime.py` | `PLANNING_POLICY_FIELDS`, `_seed_planning_state()`, `execute_planning_runtime()` | derive coverage, assumptions, and delta from the same deterministic planning pass |
| Durable graph state | `anvil/harness/state.py` | `HarnessState`, `initialize_harness_state()`, summary rehydration block | first-class `planning_*` coverage fields that survive projection and reload |
| Strategy policy surface | `examples/harness/strategies/deterministic_feature_planning_v1.yaml` | top-level policy keys | add explicit `coverage_policy` version and keep phase IDs canonical |
| Artifact projection | `anvil/harness/reporting.py` | `PLANNING_ARTIFACT_SCHEMA_VERSION`, `plan_projection_v1()`, `publish_planning_artifacts_v1()` | emit v2 payloads and preserve success-only artifact publication |
| Markdown rendering | `anvil/harness/reporting.py`, `anvil/harness/validation.py` | `render_plan_markdown_v1()`, `_PLANNING_MARKDOWN_SECTION_HEADINGS` | render coverage sections in canonical order |
| Machine contract | `anvil/harness/schemas.py` | `plan_json_schema()` and new nested record schemas | define `plan_artifact_v2` and the new nested record schemas |
| Success-artifact integrity | `anvil/harness/validation.py` | `validate_planning_success_artifacts()` | enforce coverage invariants, cross-record resolution, and markdown parity |
| Example corpus and docs | `examples/harness/tasks/`, `README.md`, `examples/README.md` | fixture descriptions and example prose | keep the visible planning surface honest about the richer artifact |

### 5.4 Production failure scenarios by seam

| Seam | Realistic failure | Planned guard |
|---|---|---|
| runtime coverage derivation | runtime emits two rows for the same dimension or skips one entirely | schema + semantic invariant tests |
| assumptions register | a rejected assumption still props up a `covered` row | referential and status-consistency validation |
| uncovered delta derivation | a `covered` row still emits a delta | delta-to-coverage invariant checks |
| non-success projection | blocked runs imply fake completeness by omitting coverage status | summary payload contract tests |
| markdown rendering | `PLAN.md` coverage sections drift from `plan.json` ordering | markdown parity validation plus artifact tests |
| schema evolution | new fields silently ship under `plan_artifact_v1` | explicit schema-version bump to `plan_artifact_v2` |

### 5.5 Architecture verdict

Do not add:

- a second planning runtime
- a generic coverage framework layer before one proof exists
- coverage computation inside `reporting.py`
- provider-owned or reviewer-owned planning completeness grading
- a new `*_v2` helper family for projection/render/publication

This milestone wins by extending the existing planning runtime honestly and by
keeping one planning publication path.

## 6. Implementation Plan

Read this section as the authoritative execution order for `C2`.
Later sections explain why these steps exist and how they are validated. They do
not redefine the sequence.

### 6.1 Primary files to touch

| File | Why it changes |
|---|---|
| `anvil/harness/state.py` | add durable coverage fields and summary rehydration |
| `anvil/harness/planning_runtime.py` | derive coverage, assumptions, delta, and coverage status |
| `anvil/harness/schemas.py` | define the v2 artifact contract and nested schemas |
| `anvil/harness/reporting.py` | project, publish, and render the new payload |
| `anvil/harness/validation.py` | gate success publication on coverage integrity and markdown parity |
| `examples/harness/strategies/deterministic_feature_planning_v1.yaml` | add `coverage_policy` and keep phase IDs authoritative |
| `examples/harness/tasks/deterministic_feature_planning_*.yaml` | keep success/clarification/failed fixture expectations honest |
| `README.md` | document the richer planning artifact |
| `examples/README.md` | document success-only artifacts vs summary-only blocked runs |
| `tests/test_harness_planning_graph.py` | runtime and stop-path planning assertions |
| `tests/test_harness_planning_artifacts.py` | artifact publication and integrity assertions |
| `tests/test_harness_example_strategy_wiring.py` | strategy policy and repeat-run determinism assertions |
| `tests/test_harness_strategy_graph.py` | graph/spec stability assertions if strategy metadata changes |
| `tests/test_harness_state_boundaries.py` | state serialization and summary rehydration assertions |
| `tests/test_harness_reporting.py` | summary/report publication parity assertions |

### 6.2 Execution contract

| Slice | Why it exists | Cannot start until | Produces |
|---|---|---|---|
| A. Contract and state freeze | lock the new truth surface before code fans out | — | field names, schema-version choice, coverage vocabulary, ownership rules |
| B. Runtime coverage derivation | make coverage facts runtime-owned and deterministic | A | coverage rows, assumptions, delta, coverage status in state |
| C. Projection, rendering, and validation | make the artifact publishable and trustworthy | A, B | `plan_artifact_v2`, canonical markdown sections, integrity checks |
| D. Example surface and docs | keep the public planning surface honest | A | explicit policy version, updated example expectations, visible artifact semantics |
| E. Quality gates and regressions | prove the whole thing and block drift | B, C, D | regression wall for success and blocked paths |

Rules:

- Slice A locks the nouns.
- Slice B owns the facts.
- Slice C owns serialization and gating, never truth invention.
- Slice D is visible product surface, not cleanup.
- Slice E is the merge wall. Not follow-up hardening.

### 6.3 Slice A: Contract and state freeze

Goal: freeze the new truth surface before behavior spreads across modules.

Primary files:

- `anvil/harness/state.py`
- `anvil/harness/schemas.py`
- `anvil/harness/planning_runtime.py`
- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`

Concrete changes:

- add `planning_coverage_status`, `planning_coverage_ledger`,
  `planning_assumptions_register`, and `planning_uncovered_delta` to
  `HarnessState`
- initialize those fields in `initialize_harness_state()`
- restore those fields from summary payloads in the summary rehydration block in
  `anvil/harness/state.py`
- extend `PLANNING_POLICY_FIELDS` with `coverage_policy`
- define the fixed coverage dimension set and allowed enum values in one shared
  runtime-owned location
- add `coverage_policy: measurable_coverage_v1` to
  `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- lock the artifact schema version to `plan_artifact_v2`

Produces:

- one canonical vocabulary
- one state shape
- one strategy policy version surface

Done when:

- downstream code can reference the new fields by one name only
- the strategy example exposes `coverage_policy: measurable_coverage_v1`
- no later slice needs to invent field names, status enums, or schema versioning

### 6.4 Slice B: Runtime coverage derivation

Goal: derive coverage, assumptions, and uncovered delta inside the existing
deterministic planning runtime.

Primary files:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/state.py`

Concrete changes:

- extend `_seed_planning_state()` to initialize the new coverage fields every run
- add one runtime-owned coverage derivation pass after seams, workstreams, and
  slices are known and before terminal success publication is finalized
- derive one `coverage_ledger` row per fixed dimension using:
  - task objective and acceptance for `problem_frame`
  - `repo_evidence_refs` for `repo_surface`
  - seams for `seam_selection`
  - dependency reasoning on workstreams/slices for `dependency_shape`
  - workstreams for `execution_partitioning`
  - slice acceptance criteria for `acceptance_shape`
  - ambiguity flags, clarification signals, or missing evidence for
    `risk_and_unknowns`
- derive `assumptions_register` from claims that remain active but unvalidated
  after the planning pass
- derive `uncovered_delta` only from `partial` and `uncovered` rows
- stamp `planning_coverage_status` as:
  - `success` when terminal status is `success`
  - `clarification_needed` when terminal status is `clarification_needed`
  - `failed` when terminal status is `failed`
- ensure all cross-record refs use declared strategy `phase_id` values:
  `design_doc`, `seam_decomposition`, `parallel_planning`, `slice_emission`

Produces:

- runtime-owned coverage truth in state
- stable IDs and stable ordering for all three new record types
- honest partial payloads for blocked runs

Done when:

- repeat runs on the same workspace emit the same coverage IDs and order
- blocked runs can still carry partial coverage without pretending to be complete
- no logic in projection or validation needs to infer missing runtime facts

### 6.5 Slice C: Projection, rendering, and validation

Goal: make the new contract publishable, readable, and impossible to fake.

Primary files:

- `anvil/harness/reporting.py`
- `anvil/harness/validation.py`
- `anvil/harness/schemas.py`

Concrete changes:

- keep `plan_projection_v1()` as the single planning payload assembler, but
  extend it to emit the v2 shape
- keep `render_plan_markdown_v1()` as the single planning markdown renderer, but
  extend it to render the full C2 section set
- keep `publish_planning_artifacts_v1()` as the single planning publisher, but
  make it publish `plan_artifact_v2`
- extend `plan_json_schema()` with:
  - `schema_version = plan_artifact_v2`
  - `coverage_status`
  - `coverage_ledger`
  - `assumptions_register`
  - `uncovered_delta`
- add nested schemas for coverage rows, assumption rows, and delta rows
- update `_PLANNING_MARKDOWN_SECTION_HEADINGS` to require this canonical order:
  1. `## Problem Statement`
  2. `## Rubric Results`
  3. `## Architectural Seams`
  4. `## Parallel Workstreams/Worktrees`
  5. `## Executable Slices`
  6. `## Coverage Ledger`
  7. `## Assumptions Register`
  8. `## Uncovered Delta`
- emit `coverage_status`, `coverage_ledger`, `assumptions_register`, and
  `uncovered_delta` in `plan.json`
- emit the same four surfaces in `summary.json`
- extend `validate_planning_success_artifacts()` with:
  - coverage-row cardinality and ordering checks
  - coverage-to-assumption resolution
  - delta-to-coverage resolution
  - non-empty evidence or structural refs for `covered` and `partial` rows
  - markdown parity for coverage, assumptions, and delta sections

Produces:

- one canonical v2 plan artifact
- one canonical markdown order
- one publication gate that blocks dishonest artifacts

Done when:

- `plan.json` and `PLAN.md` cannot disagree silently about coverage surfaces
- success publication fails on any missing or inconsistent coverage record
- blocked runs preserve summary truth without writing success artifacts

### 6.6 Slice D: Example surface and docs

Goal: keep the visible planning surface honest now that the artifact is richer.

Primary files:

- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- `examples/harness/tasks/deterministic_feature_planning_*.yaml`
- `README.md`
- `examples/README.md`

Concrete changes:

- add `coverage_policy` to the canonical planning strategy example
- update planning example prose to say the artifact now includes coverage,
  assumptions, and uncovered delta
- keep success, clarification, and failed fixture tasks honest about what gets
  published on each path
- state plainly that successful planning runs publish `PLAN.md` and `plan.json`,
  while blocked runs publish `summary.json` only with explicit coverage truth

Produces:

- one visible canonical strategy surface for C2
- one honest explanation of success-only artifacts vs summary-only blocked runs

Done when:

- the example strategy and docs do not undersell or overclaim the C2 artifact
- fixture tasks still describe live-vs-fixture behavior truthfully

### 6.7 Slice E: Quality gates and regressions

Goal: prove the coverage truth surface is real and stays stable.

Primary files:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_reporting.py`

Concrete changes:

- add runtime tests for stable coverage IDs and ordered dimension rows
- add artifact tests for `plan_artifact_v2`
- add blocked-run tests for honest partial coverage in `summary.json`
- add validation tests for broken assumption refs and invalid delta rows
- add state-boundary tests for new `planning_*` coverage field round-tripping
- update example-strategy tests to assert the new `coverage_policy`
- update reporting tests to prove summary payload and report output stay aligned

Produces:

- a regression wall for deterministic coverage
- explicit failure tests for dishonest publication

Done when:

- the coverage truth surface is as hard to fake as seams/workstreams/slices are today
- schema, runtime, state, and markdown drift all fail fast in tests

## 7. Code Quality and Contract Hygiene

### 7.1 Engineering rules

- Keep the diff minimal. No second artifact pipeline. No second runtime.
- Bias toward explicit over clever. Fixed dimensions beat inferred magic.
- Reuse existing planning normalization and publication seams.
- Reuse the repo's ledger-style lessons from `analysis_review` without sharing
  contract objects across planning and review.
- Keep all new record IDs stable and deterministic.
- Do not create sibling helpers just to put `v2` in a function name.

### 7.2 Truth ownership boundaries

| Concern | Owner | Rule |
|---|---|---|
| structural planning facts | `planning_runtime.py` | seams, workstreams, and slices remain runtime-owned |
| coverage truth | `planning_runtime.py` | one row per dimension, one assumptions register, one uncovered delta |
| state durability | `state.py` | the new `planning_*` fields must survive initialization and summary reload |
| artifact serialization | `reporting.py` | publish exactly what runtime produced |
| markdown presentation | `reporting.py` + `validation.py` | render canonical headings and preserve parity |
| integrity gating | `validation.py` | reject inconsistent success artifacts before publication |

### 7.3 Anti-patterns explicitly rejected

- computing coverage in `reporting.py` from already-rendered data
- leaving schema version at `plan_artifact_v1`
- attaching assumptions to every structural object in C2
- letting blocked runs omit coverage payloads entirely
- using `stage_type` instead of declared `phase_id` in cross-record refs
- creating `plan_projection_v2()` beside `plan_projection_v1()` for one branch

## 8. Test Review

Framework: `pytest`  
Coverage target: every new C2 branch gets deterministic test coverage.  
Ship rule: `C2` is not done if tests only prove schema validity.

### 8.1 Codepath coverage diagram

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/planning_runtime.py
    │
    ├── execute_planning_runtime()
    │   ├── [EXISTING] success / clarification_needed / failed terminal routing
    │   ├── [EXISTING] deterministic seams / workstreams / slices
    │   ├── [GAP]      planning_coverage_status population
    │   ├── [GAP]      coverage row derivation for all 7 dimensions
    │   ├── [GAP]      assumptions register derivation
    │   ├── [GAP]      uncovered delta derivation
    │   └── [GAP]      stable IDs and stable ordering for coverage records
    │
    └── blocked-run path
        ├── [EXISTING] empty downstream structural records on clarification
        └── [GAP]      truthful partial coverage payload on clarification / failure

[+] anvil/harness/state.py
    │
    ├── initialize_harness_state()
    │   └── [GAP]      initialize new planning coverage fields
    │
    └── summary rehydration
        └── [GAP]      round-trip new planning coverage fields from summary payload

[+] anvil/harness/reporting.py
    │
    ├── plan_projection_v1()
    │   ├── [EXISTING] structural planning projection pattern
    │   ├── [GAP]      coverage fields in plan payload
    │   └── [GAP]      summary payload parity for blocked runs
    │
    ├── render_plan_markdown_v1()
    │   ├── [EXISTING] planning markdown section rendering
    │   ├── [GAP]      coverage ledger section
    │   ├── [GAP]      assumptions register section
    │   └── [GAP]      uncovered delta section
    │
    └── publish_planning_artifacts_v1()
        ├── [EXISTING] success-only PLAN.md / plan.json publication
        ├── [GAP]      schema_version = plan_artifact_v2
        └── [GAP]      validation failures for inconsistent coverage surfaces

[+] anvil/harness/validation.py
    │
    └── validate_planning_success_artifacts()
        ├── [EXISTING] seam / workstream / slice integrity
        ├── [GAP]      coverage cardinality and ordering checks
        ├── [GAP]      assumption-link integrity
        ├── [GAP]      uncovered-delta integrity
        └── [GAP]      markdown parity for new sections

[+] examples/harness/strategies/deterministic_feature_planning_v1.yaml
    │
    ├── [EXISTING] canonical planning phase order and policies
    └── [GAP]      explicit coverage policy version

USER / OPERATOR FLOW COVERAGE
===========================
[+] Successful planning run
    ├── [EXISTING] emits PLAN.md and plan.json
    ├── [GAP]      emitted artifact shows covered vs partial vs uncovered dimensions
    └── [GAP]      emitted artifact shows assumptions and next refine delta

[+] Clarification-needed run
    ├── [EXISTING] emits summary only
    └── [GAP]      summary exposes partial coverage truth without pretending success

[+] Failed run
    ├── [EXISTING] emits summary only
    └── [GAP]      summary prevents fake `covered` rows after early failure
```

### 8.2 Required test additions

1. Runtime coverage tests in `tests/test_harness_planning_graph.py`:
   prove every fixed coverage dimension gets exactly one row in deterministic order.
2. State round-trip tests in `tests/test_harness_state_boundaries.py`:
   prove new `planning_*` coverage fields survive initialization and summary reload.
3. Assumptions tests in `tests/test_harness_planning_artifacts.py`:
   prove linked assumption IDs resolve and rejected assumptions force summary updates.
4. Uncovered-delta tests in `tests/test_harness_planning_artifacts.py`:
   prove only `partial` or `uncovered` rows generate delta entries.
5. Blocked-run summary tests in `tests/test_harness_planning_artifacts.py` and
   `tests/test_harness_reporting.py`:
   prove `summary.json` carries truthful coverage payloads for
   `clarification_needed` and `failed`.
6. Artifact schema tests in `tests/test_harness_planning_artifacts.py`:
   prove the emitter writes `plan_artifact_v2`.
7. Markdown parity tests in `tests/test_harness_planning_artifacts.py`:
   prove `PLAN.md` coverage sections match `plan.json` ordering and IDs.
8. Example surface tests in `tests/test_harness_example_strategy_wiring.py`:
   prove the canonical strategy exposes the C2 coverage policy and still keeps
   stop-path fixtures honest.
9. Shared-surface regression tests in `tests/test_harness_reporting.py`:
   prove report rendering and summary publication still behave for planning
   after the new coverage fields land.

### 8.3 Suggested commands

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
```

### 8.4 Human acceptance checks

- Skeptical-reader rubric:
  the artifact answers "what is missing?" without needing conversation context.
- Builder rubric:
  the uncovered delta is specific enough to drive the next deterministic refine pass.
- Honesty rubric:
  blocked runs do not look complete just because they rendered tidy JSON.

## 9. Performance and Reliability Review

### 9.1 Performance risks

| Risk | Why it matters | Required mitigation |
|---|---|---|
| coverage derivation rereads files | latency grows for no product value | derive coverage from already-collected runtime facts wherever possible |
| coverage rows duplicate structural refs noisily | artifact becomes unreadable and unstable | keep refs bounded and deterministic |
| markdown parity checks become brittle | publication starts failing for formatting trivia | validate canonical ordering and item presence, not incidental whitespace |
| blocked-run payload inflation | summary artifacts become noisy and misleading | keep partial payloads truthful and minimal |

### 9.2 Reliability rules

- coverage derivation must not reopen the file-discovery budget
- success publication fails closed on any broken coverage invariant
- blocked runs always include explicit `coverage_status`
- stable IDs must survive repeat runs on the same workspace snapshot

### 9.3 Performance verdict

Do not add a caching layer or background coverage pass in C2.
The new truth surface should be cheap because it reuses the planning facts the
runtime already has.

## 10. Error & Rescue Registry

| Failure | User-visible impact | Rescue |
|---|---|---|
| coverage row missing for one dimension | artifact claims completeness but has a blind spot | fail schema/integrity validation before success publication |
| rejected assumption still props up a `covered` row | reader over-trusts the plan | fail assumption-link consistency checks |
| uncovered delta emitted for a `covered` row | refine-loop handoff becomes nonsense | fail delta invariants |
| blocked run omits coverage payloads | the exact uncertainty disappears | require arrays and explicit `coverage_status` in `summary.json` |
| state reload drops planning coverage fields | rehydrated runs lose truth surfaces silently | add state-boundary tests and summary rehydration assertions |
| schema version stays at v1 | downstream readers cannot tell the contract changed | emit `plan_artifact_v2` only |
| markdown omits coverage section | human reader sees less truth than automation | fail markdown parity validation |

## 11. Failure Modes Registry

| New codepath | Realistic production failure | Test covers it? | Error handling exists? | User-visible outcome | Status |
|---|---|---:|---:|---|---|
| coverage derivation | one dimension is skipped silently | must add | must add | misleading completeness | critical gap until covered |
| coverage ordering | rows emit in nondeterministic order | must add | must add | unstable diffs and flaky automation | critical gap until covered |
| assumptions linkage | coverage row points at missing assumption ID | must add | must add | broken artifact consumers | critical gap until covered |
| assumption rejection | rejected assumption leaves stale `covered` prose behind | must add | must add | false confidence | required |
| delta derivation | `covered` row still emits a delta | must add | must add | bogus refine-loop handoff | critical gap until covered |
| blocked-run summary | failure path still claims `covered` after early stop | must add | must add | dishonest summary payload | critical gap until covered |
| state rehydration | summary reload drops coverage fields and later consumers see incomplete state | must add | must add | flaky downstream behavior | critical gap until covered |
| markdown rendering | coverage sections drift from JSON IDs | must add | must add | human/machine disagreement | critical gap until covered |

Any row with no test and no error handling is a merge blocker.

## 12. DX and Operator Experience

### 12.1 Developer journey map

| Stage | Current experience | C2 target |
|---|---|---|
| discover planning | planning artifact exists | same |
| inspect artifact | structure is visible | coverage, assumptions, and delta are visible too |
| decide whether to trust it | requires reading prose and guessing what is missing | artifact names what is partial or uncovered explicitly |
| compare two runs | seams/workstreams/slices are stable | coverage rows are stable too |
| handle blocked run | summary explains stop reason | summary also exposes coverage truth accumulated before the stop |
| decide next action | builder must infer what to ask next | uncovered delta says what input the next refine pass needs |

### 12.2 Distribution plan

Distribution remains the existing CLI artifact path.
No new package or publish workflow is required.

Canonical path:

- repo checkout
- `poetry run python -m anvil.cli harness-run ...`
- inspect `summary.json` on blocked runs
- inspect `PLAN.md` and `plan.json` on success runs

### 12.3 DX verdict

This is a developer-facing artifact feature.
The main DX win is not fewer steps.
It is less ambiguity after the command finishes.

## 13. Worktree Parallelization Strategy

This plan has real parallelization opportunity, but only after the contract is
frozen. The goal is parallel implementation without merge-conflict roulette.

### 13.1 Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Contract and state freeze | `anvil/harness/`, `examples/harness/strategies/` | — |
| B. Runtime coverage derivation | `anvil/harness/` | A |
| C. Projection, rendering, and validation | `anvil/harness/` | A, B |
| D. Example surface and docs | `examples/harness/`, repo docs | A |
| E. Quality gates and regressions | `tests/`, `anvil/harness/`, docs surface expectations | B, C, D |

### 13.2 Parallel lanes

Lane A: Contract freeze  
Run first. Lock field names, schema version, coverage vocabulary, policy
versioning, and the exact summary/publication contract.

Lane B: Runtime coverage derivation  
Run after A. Own coverage rows, assumptions, delta, and blocked-run partial
truth in `planning_runtime.py` and `state.py`.

Lane C: Projection, rendering, and validation  
Run after B exposes the exact runtime payload shape. Own serialization,
markdown headings, schema, and integrity gating.

Lane D: Example surface and docs  
Run after A. This can proceed in parallel with B because it mostly touches the
public surface and canonical example files.

Lane E: Quality gates and regressions  
Run only after B, C, and D settle. This is the merge-blocking regression wall.

### 13.3 Worktree ownership plan

| Lane | Recommended owner surface | Why |
|---|---|---|
| A | contract owner | centralizes the noun freeze and avoids parallel drift |
| B | runtime owner | one person owns truth derivation end to end |
| C | publication owner | one person owns schema, markdown, and validation parity |
| D | docs/example owner | isolated public-surface work with low overlap after A |
| E | test owner or integrator | best done after the implementation surfaces stop moving |

### 13.4 Execution order

```text
Lane A
  │
  ├──────────────► Lane B ─────► Lane C
  │
  └──────────────► Lane D
                      │
          Lane C + Lane D complete
                      │
                      ▼
                    Lane E
```

Execution order:

1. Launch Lane A and merge it.
2. Launch Lane B and Lane D in parallel worktrees.
3. Launch Lane C only after Lane B freezes the runtime payload shape.
4. Merge B, C, and D.
5. Run Lane E last as the merge-blocking regression wall.

### 13.5 Merge checkpoints

Checkpoint 1, after Lane A:

- `coverage_policy` exists in the strategy example
- `PLANNING_POLICY_FIELDS` includes `coverage_policy`
- state field names are frozen
- artifact version target is frozen to `plan_artifact_v2`

Checkpoint 2, after Lane B:

- runtime emits the full coverage payload into state
- all IDs and ordering rules are deterministic
- blocked-run coverage payload behavior is frozen

Checkpoint 3, after Lane C + Lane D:

- success artifacts publish the v2 contract
- markdown headings and validation parity are locked
- public docs describe the artifact honestly

Checkpoint 4, after Lane E:

- all targeted tests pass
- no uncovered critical gaps remain

### 13.6 Conflict flags

- Lanes A and B both touch `anvil/harness/state.py`. B must not start before A freezes the field names.
- Lanes A and C both touch `anvil/harness/schemas.py` and planning publication expectations. Keep the schema-version decision in A, then let C fill in the exact record shapes.
- Lanes B and C both shape the coverage payload. C must not validate against a moving runtime contract.
- Lanes D and E both touch public-surface expectations. Freeze visible wording before landing docs/reporting assertions.
- Lanes B, C, and E all touch `tests/test_harness_planning_artifacts.py` if done carelessly. Prefer reserving final assertion expansion for Lane E.

## 14. Acceptance Checklist

- [ ] `HarnessState` includes first-class `planning_*` coverage fields
- [ ] summary rehydration restores the new coverage fields correctly
- [ ] canonical planning strategy exposes `coverage_policy`
- [ ] successful runs emit `plan_artifact_v2`
- [ ] `coverage_ledger` has exactly one row per required dimension
- [ ] `coverage_id`, `assumption_id`, and `delta_id` are stable across repeat runs
- [ ] `source_phase_ids` and `recommended_next_phase` use declared `phase_id` values
- [ ] `PLAN.md` renders coverage, assumptions, and uncovered-delta sections in canonical order
- [ ] `summary.json` preserves truthful coverage payloads on blocked runs
- [ ] publication fails on broken assumption refs, broken delta refs, invalid coverage cardinality, or markdown parity drift
- [ ] no strategy-name branching is introduced to make C2 work
- [ ] no duplicate planning publication helper family is introduced

## 15. Completion Summary

- Step 0: scope accepted as a measurable-completeness proof, not a planner-breadth project
- What already exists: mapped and reused, especially runtime state, projection, validation, and ledger-style patterns
- Locked decisions: helper strategy, schema version, ownership boundaries, and non-success behavior are now explicit
- Architecture: one engine, one truth owner, one artifact path
- Implementation plan: five slices with exact file owners, exit criteria, and merge checkpoints
- Code quality: explicit contract, explicit schema-version bump, minimal diff on ownership boundaries
- Test review: coverage diagram merged into this plan and upgraded to block dishonest coverage publication and state reload drift
- Performance review: coverage derivation must reuse planning facts, not reopen discovery
- Failure modes: critical gaps enumerated for missing rows, stale assumptions, bogus delta, blocked-run dishonesty, and dropped state reload fields
- DX: artifact trust improves because uncertainty becomes first-class instead of implied
- Parallelization: one foundation lane, two middle implementation lanes, one publication lane, one regression lane
- Lake score: choose the complete truth surface now, not the schema-valid shortcut
