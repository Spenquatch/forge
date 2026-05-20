# PLAN: C2.9 Public Subset Gate for C3

Status: hardened, implementation-ready on `codex/c1b-planning-quality-proof`  
Milestone: `C2.9`  
Prepared from repo state on: `2026-05-20`

Source of truth:
- `/home/azureuser/.gstack/projects/Spenquatch-forge/azureuser-c29-public-subset-gate-design-20260520-015124.md`
- current repository code in `anvil/harness/`, `examples/harness/`, `tests/`, `README.md`, `examples/README.md`, and `docs/contributing.md`

Plan authority:
- this file is the authoritative implementation guide for `C2.9`
- there are no blocking open questions for this milestone
- `C2.9` ends at contract-freeze artifacts plus drift tests
- `C3` parser/preflight/runtime enforcement is explicitly next work, not hidden inside this branch

## Executive Summary

`C2.9` is not blocked on whether Forge can emit a bounded planning artifact.

`C2.9` is blocked on contract honesty.

The repo currently exposes real behavior through several different layers at the
same time:

- public strategy names
- compatibility aliases
- runtime-owned knobs
- emitted graph metadata
- fixture-only planning scaffolding
- runnable internal harness examples

Those surfaces are all real. They are not all public contract.

This branch closes `C2.9` by freezing one explicit, truthful public subset for
`C3 v1`, then making the repo say exactly that and nothing more. The work is a
contract-hardening pass:

- one canonical contract doc
- one machine-readable registry
- one public example pack split by intent
- one relabeling pass for the existing runnable fixture examples
- one regression wall that prevents the story from drifting again

No runtime behavior change is required to finish this milestone.

## 1. Objective and Success Bar

### 1.1 Objective

Ship a repo-owned `C2.9` contract freeze for `C3 v1` public strategy authoring
that:

- separates canonical public surface, broader public built-ins,
  compatibility-only surface, runtime-owned surface, metadata-only surface, and
  fixture-only surface
- gives `C3` one machine-readable registry instead of prose-only decisions
- gives contributors one canonical doc and one canonical example pack for the
  future public strategy surface
- stops front-door docs from presenting internal harness fixtures as the public
  DSL

### 1.2 Exact problem statement

What exists today is useful, but it is not yet an honest public contract.

Verified repo facts:

- `anvil/harness/types.py` still treats `StrategyConfig.kind` as an open string
  transport field and still accepts planning-only fields in the same transport
  object
- `anvil/harness/nodes/prepare_run.py` still merges raw top-level task and
  strategy keys back into state
- `anvil/harness/nodes/validator_preflight.py` still normalizes
  `analysis_review_v1` to `analysis_review_bounded_v1`
- `anvil/harness/providers.py` still falls back to `execute` semantics for
  unknown role-like names
- `anvil/harness/strategy_graph.py` emits `schema_version` and `subset` as
  runtime metadata on graph specs
- `anvil/harness/planning_runtime.py` still treats `coverage_policy` and
  `phase_inputs` as live planning-runtime inputs
- `examples/harness/strategies/deterministic_feature_planning_v1.yaml` is still
  a runnable fixture-backed strategy, not a clean public DSL example
- `README.md`, `examples/README.md`, and `docs/contributing.md` still steer
  readers first toward the runnable fixture planning example

Those surfaces are not wrong. They are just not the same thing.

`C2.9` exists to classify them precisely and freeze one honest future-facing
subset before `C3` starts coding against folklore.

### 1.3 Success bar

`C2.9` is complete only when all of the following are true:

- the repo has one canonical contract doc for the `C3 v1` public strategy
  subset
- the repo has one machine-readable registry for public kinds, stage families,
  role families, graph primitives, transition forms, planning phase types,
  runtime-owned exclusions, and metadata-only fields
- the repo has one classified example pack split into canonical,
  compatibility-only, and negative examples
- front-door docs explicitly distinguish canonical public examples from runnable
  internal harness fixtures
- the current runnable fixture surfaces continue to work and continue to be
  documented, but they are no longer mislabeled as the public DSL
- regression tests fail if docs, registries, and example packs drift out of
  sync
- no part of this milestone silently starts implementing `C3` runtime behavior

## 2. Step 0: Scope Challenge

### 2.1 What already exists

| Sub-problem | Existing surface | Reuse decision |
|---|---|---|
| Contract artifact precedent | `docs/analysis_review_contract.md` | mirror this format instead of inventing a second contract-doc style |
| Public-kind and runtime-target truth | `anvil/harness/types.py`, `anvil/harness/nodes/validator_preflight.py` | use these files as the verified source for names, aliases, and planning runtime-target rules |
| Internal graph vocabulary | `anvil/harness/strategy_graph.py` | derive graph primitives, transition forms, planning phase types, and metadata-only fields from here |
| Stage-family to provider-role mapping | `anvil/harness/providers.py` | freeze the public stage-family registry and role-family bindings from this verified mapping |
| Runtime-owned planning leakage | `anvil/harness/planning_runtime.py`, `anvil/harness/nodes/prepare_run.py` | use these as the explicit evidence for excluded public fields |
| Existing runnable example tree | `examples/harness/strategies/` | keep runnable examples in place, but reclassify them instead of moving them |
| Existing docs entry points | `README.md`, `examples/README.md`, `docs/contributing.md` | update routing instead of building new entry documents |
| Existing docs/example regression tests | `tests/test_docs_surface.py`, `tests/test_harness_example_strategy_wiring.py` | extend these instead of inventing a second docs-audit framework |

### 2.2 Minimum complete scope

Nothing below is optional if this milestone is going to close `C2.9` honestly:

1. `docs/strategy_dsl_public_subset_contract.md`
2. `anvil/harness/public_subset_registry.py`
3. `examples/harness/public_subset/README.md`
4. `examples/harness/public_subset/canonical/`
5. `examples/harness/public_subset/compatibility/`
6. `examples/harness/public_subset/negative/`
7. updates to `README.md`
8. updates to `examples/README.md`
9. updates to `docs/contributing.md`
10. explicit relabeling in `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
11. `tests/test_harness_public_subset_contract.py`
12. focused updates to `tests/test_docs_surface.py`
13. focused updates to `tests/test_harness_example_strategy_wiring.py`

### 2.3 Complexity verdict

This branch touches more than eight files. That is normally a smell.

Here it is acceptable because the blast radius is tightly constrained:

- one new canonical contract doc
- one new data-only registry module
- one new public example pack
- three front-door doc updates
- one relabeling pass on the existing planning fixture example
- one new contract regression file plus two focused test updates

What would be overbuilt:

- implementing parser or preflight enforcement inside `C2.9`
- wiring the new registry into runtime selection logic
- rewriting the planning runtime
- moving the entire example tree for aesthetics
- freezing a public task-spec contract in the same PR

### 2.4 TODOS cross-reference

`docs/project_management/future/TODOS.md` contains no deferred item that blocks
this milestone.

This plan should add or preserve explicit post-`C2.9` follow-ups for:

- parser/preflight enforcement of the frozen public subset
- public task-spec contract work, if desired later
- richer diagnostics/publication work beyond the contract freeze

### 2.5 Completeness and distribution verdict

Completeness verdict:

- the complete version of this milestone includes the negative example pack and
  the drift wall
- omitting those would save little effort and would leave the contract easy to
  misrepresent again

Distribution verdict:

- this milestone introduces no new binary, package, container, or deployable
  runtime artifact
- no CI/CD or publish pipeline changes are required

### 2.6 Not in scope

- implementing full public parser enforcement
- changing builder/runtime routing
- changing planning runtime semantics
- deleting compatibility aliases from the runtime
- removing raw merge-back from harness state
- changing provider/model configuration
- publishing a public validator contract
- imports, overlays, inheritance, or arbitrary DAG composition
- freezing a public task-spec contract

## 3. Locked Decisions

These decisions are frozen. Implementation may explain them, not reopen them.

| Decision | Locked choice | Why |
|---|---|---|
| Milestone boundary | `C2.9` ends at contract-freeze artifacts plus drift tests | keeps `C2.9` honest and keeps `C3` implementation work separate |
| Public unit of declaration | one full strategy spec | matches how the current runtime already reasons |
| Contract path | `docs/strategy_dsl_public_subset_contract.md` | one canonical human-facing artifact |
| Machine-readable source of truth | `anvil/harness/public_subset_registry.py` | prose-only contracts drift too easily |
| Example taxonomy path | `examples/harness/public_subset/` with `canonical/`, `compatibility/`, and `negative/` | separates truthful public examples from runnable internal fixtures |
| Public version field | `dsl_version: c3_strategy_v1` | explicit versioning is part of the public contract |
| Canonical `C3` graph-DSL kinds | `analysis_review_bounded_v1`, `analysis_review_trust_v1`, `deterministic_feature_planning_v1` | these are the narrowed forward-looking public family |
| Broader public built-ins | `single_pass`, `pfr_v1` remain public, but they are not themselves proof of the `C3` graph-DSL story | avoids widening the claim by accident |
| Compatibility-only kind | `analysis_review_v1` stays compatibility-only and must never appear in canonical examples | keeps forward docs honest while preserving runtime compatibility |
| Runtime target rule | canonical non-planning examples omit `runtime_target`; canonical planning example declares `runtime_target: planning_v1` | matches current `StrategyConfig` validation and keeps public examples DRY |
| Runtime-owned excluded strategy fields | `coverage_policy` and `phase_inputs` are excluded from the public strategy subset | these are real runtime surfaces, but not truthful public authoring fields |
| Metadata-only fields | `schema_version` and `subset` are runtime-emitted metadata only | users must not treat emitted graph labels as authoring keys |
| Existing runnable planning strategy | keep `examples/harness/strategies/deterministic_feature_planning_v1.yaml` runnable, but relabel it as fixture-backed internal harness scaffolding | preserves regression value without teaching the wrong contract |
| Code boundary | the new registry module is data-only and is not wired into runtime behavior yet | avoids accidental half-implementation of `C3` |
| Scope boundary | this milestone freezes the public strategy-spec surface only | prevents task-spec scope creep inside a strategy-contract branch |

## 4. Verified Current-State Evidence

| Surface | Verified fact | Implementation implication |
|---|---|---|
| `anvil/harness/types.py` | defines current strategy kinds, infers runtime targets, enforces planning runtime-target coupling, and freezes planning phase stage-type order | registry must reuse these verified names and canonical planning phase order |
| `anvil/harness/strategy_graph.py` | defines internal graph vocabulary and emits `schema_version` and `subset` in `StrategyGraphSpec.to_dict()` | contract doc must classify graph vocabulary separately from metadata-only fields |
| `anvil/harness/providers.py` | maps `solver`, `proposer`, `falsifier`, `critic`, `patcher`, `reviser`, and `auditor` to `execute`, `critique`, `refine`, and `review`, while unknown names fall back to `execute` | public stage-family registry must be closed, and role-family bindings must be explicit |
| `anvil/harness/nodes/prepare_run.py` | merges raw task/strategy payloads back into state alongside typed `to_dict()` output | current transport shape is broader than the future public contract |
| `anvil/harness/nodes/validator_preflight.py` | normalizes `analysis_review_v1` to `analysis_review_bounded_v1` and performs runtime-target/task-kind compatibility checks | compatibility alias remains real runtime behavior, but it is not canonical public authoring |
| `anvil/harness/planning_runtime.py` | still treats `coverage_policy` and `phase_inputs` as active runtime inputs | those fields must be called runtime-owned and excluded from canonical public examples |
| `examples/harness/strategies/deterministic_feature_planning_v1.yaml` | still carries `coverage_policy` and `phase_inputs` in a runnable example | that file must be relabeled, not promoted |
| `README.md`, `examples/README.md`, `docs/contributing.md` | still route planning readers first to the runnable fixture example | docs routing must change so public readers start at the contract doc and example pack |
| `tests/test_docs_surface.py`, `tests/test_harness_example_strategy_wiring.py` | already protect docs routing and example relationships | extend them instead of building parallel test infrastructure |

## 5. Target Artifact Set and Authority Chain

### 5.1 Authority chain

```text
public_subset_registry.py
        |
        +--> strategy_dsl_public_subset_contract.md
        |
        +--> examples/harness/public_subset/
        |
        +--> docs routing in README.md / examples/README.md / docs/contributing.md
        |
        +--> tests/test_harness_public_subset_contract.py
              tests/test_docs_surface.py
              tests/test_harness_example_strategy_wiring.py
```

Rules:

- the registry is the only machine-readable source of truth
- the contract doc mirrors the registry, it does not invent a second list
- canonical public examples must conform to the registry and contract doc
- docs route readers to the contract doc and public example pack first
- tests prove the four surfaces stay aligned

### 5.2 Exact registry contents

`anvil/harness/public_subset_registry.py` must be data-only and must export the
exact public sets needed for `C2.9`.

Required constants:

| Constant group | Exact content |
|---|---|
| `PUBLIC_SUBSET_DSL_VERSION` | `c3_strategy_v1` |
| `C3_GRAPH_DSL_KINDS` | `analysis_review_bounded_v1`, `analysis_review_trust_v1`, `deterministic_feature_planning_v1` |
| `BROADER_PUBLIC_BUILTIN_KINDS` | `single_pass`, `pfr_v1` |
| `COMPATIBILITY_ONLY_KINDS` | `analysis_review_v1` |
| `PUBLIC_GRAPH_PRIMITIVES` | `stage`, `linear_edge`, `conditional_branch`, `bounded_loop`, `terminal_outcome`, `planning_phase` |
| `PUBLIC_TRANSITION_FORMS` | `linear_next`, `enumerated_branch`, `bounded_loop_back_edge`, `terminal_exit` |
| `PUBLIC_STAGE_FAMILIES` | `solver`, `proposer`, `falsifier`, `patcher`, `critic`, `reviser`, `auditor`, `focus_gate`, `planner` |
| `PUBLIC_ROLE_FAMILIES` | `execute`, `critique`, `refine`, `review` |
| `STAGE_FAMILY_ROLE_BINDINGS` | `solver -> execute`, `proposer -> execute`, `planner -> execute`, `focus_gate -> execute`, `falsifier -> critique`, `critic -> critique`, `patcher -> refine`, `reviser -> refine`, `auditor -> review` |
| `CANONICAL_PLANNING_PHASE_STAGE_TYPES` | `rubric_design_doc`, `architecture_seam_decomposition`, `parallel_workstream_planning`, `executable_slice_emission` |
| `PLANNING_REQUIRED_POLICY_FIELDS` | `artifact_policy`, `determinism_policy`, `discovery_policy`, `rubric_policy`, `stop_policy` |
| `RUNTIME_OWNED_EXCLUDED_FIELDS` | `coverage_policy`, `phase_inputs` |
| `METADATA_ONLY_FIELDS` | `schema_version`, `subset` |

Registry implementation rules:

- use plain tuples, frozensets, and dictionaries only
- do not add validation or parser logic to this module
- do not wire this module into runtime behavior in `C2.9`
- prefer defining the public sets directly in this module and letting tests
  compare them against current runtime constants, rather than importing half the
  truth from multiple runtime modules

### 5.3 Contract doc requirements

`docs/strategy_dsl_public_subset_contract.md` must be the human-readable mirror
of the registry and must include all of the following sections:

1. Scope and milestone boundary
2. Canonical public strategy kinds versus broader public built-ins
3. Compatibility-only kinds
4. Public versioning via `dsl_version`
5. Public graph primitives
6. Public transition forms
7. Public stage families and role-family bindings
8. Planning-specific canonical phase order and required policy refs
9. Runtime-owned excluded fields
10. Metadata-only fields
11. Canonical example taxonomy
12. Explicit exclusions and post-`C2.9` follow-up boundary

Doc rules:

- it freezes the public strategy-spec subset only
- it does not claim parser enforcement already exists
- it calls `coverage_policy` and `phase_inputs` runtime-owned, not deprecated
  public fields
- it calls `schema_version` and `subset` metadata-only, not authoring keys
- it states that canonical non-planning examples omit `runtime_target`
- it states that canonical planning examples include `runtime_target: planning_v1`

### 5.4 Example pack requirements

The public example pack must be new and separate from existing runnable
fixtures.

Required files:

- `examples/harness/public_subset/README.md`
- `examples/harness/public_subset/canonical/analysis_review_bounded_v1.yaml`
- `examples/harness/public_subset/canonical/analysis_review_trust_v1.yaml`
- `examples/harness/public_subset/canonical/deterministic_feature_planning_v1.yaml`
- `examples/harness/public_subset/compatibility/analysis_review_v1.yaml`
- `examples/harness/public_subset/negative/invalid_kind.yaml`
- `examples/harness/public_subset/negative/unknown_top_level_key.yaml`
- `examples/harness/public_subset/negative/invalid_stage_family.yaml`
- `examples/harness/public_subset/negative/runtime_owned_phase_inputs.yaml`
- `examples/harness/public_subset/negative/metadata_only_schema_version.yaml`

Canonical example rules:

- every canonical example carries `dsl_version: c3_strategy_v1`
- canonical examples use canonical kinds only
- canonical examples never use `analysis_review_v1`
- canonical examples never use `coverage_policy`
- canonical examples never use `phase_inputs`
- canonical examples never use `schema_version`
- canonical examples never use `subset`
- canonical non-planning examples omit `runtime_target`
- canonical planning example includes `runtime_target: planning_v1`
- canonical planning example keeps the current verified phase order and the
  required planning policy refs

Compatibility example rules:

- `analysis_review_v1.yaml` is accepted legacy input, not a canonical public
  example
- it should make the compatibility-only status obvious in file comments and in
  the example-pack README
- it should not be presented anywhere as the recommended starting point

Negative example rules:

- each negative example maps to exactly one contract violation
- `examples/harness/public_subset/README.md` must explain the expected rejection
  reason for each negative file
- negative examples are documentation and future parser fixtures, not runnable
  happy-path harness examples

### 5.5 Front-door routing requirements

The repo must teach the public subset first, while preserving runnable harness
examples as runnable harness examples.

Front-door rules:

- `README.md` must point readers first to the contract doc and public example
  pack for the future public subset
- `examples/README.md` must distinguish canonical public examples from runnable
  harness fixtures
- `docs/contributing.md` must explain the same split for maintainers
- the current planning run command can stay, but it must be clearly framed as a
  runnable internal harness example path, not the canonical public DSL example
- `examples/harness/strategies/deterministic_feature_planning_v1.yaml` must be
  relabeled as internal or fixture-backed scaffolding in its header comments

## 6. Exact Implementation Plan

### 6.1 Workstream A: Freeze the registry and contract doc

Goal: make the public subset explicit in one code artifact and one doc artifact.

Primary paths:

- `anvil/harness/public_subset_registry.py`
- `docs/strategy_dsl_public_subset_contract.md`

Implementation tasks:

1. Add `public_subset_registry.py` with the exact constants listed in section
   5.2.
2. Write `strategy_dsl_public_subset_contract.md` so each enumerated public set
   maps 1:1 to a registry constant group.
3. Make the doc explicit about the following three layers:
   - canonical public strategy-spec surface
   - compatibility-only accepted runtime inputs
   - runtime-owned and metadata-only surfaces that are not public authoring
4. State plainly that this milestone freezes the contract but does not yet
   enforce it at runtime.
5. State plainly that task-spec surface freeze is out of scope for this branch.

Definition of done:

- the registry exists as code data
- the contract doc exists as the human-facing source of truth
- the doc and registry agree on all enumerated sets
- the doc does not blur broader public built-ins with the narrower `C3`
  graph-DSL family

### 6.2 Workstream B: Build the classified public example pack

Goal: give the repo one clean example pack that matches the new contract
exactly.

Primary paths:

- `examples/harness/public_subset/README.md`
- `examples/harness/public_subset/canonical/`
- `examples/harness/public_subset/compatibility/`
- `examples/harness/public_subset/negative/`

Implementation tasks:

1. Add the example-pack README with three sections:
   - canonical
   - compatibility-only
   - negative
2. Add the three canonical examples.
3. Add the one compatibility-only legacy alias example.
4. Add the five negative examples named in section 5.4.
5. Make the planning canonical example structurally honest:
   - keep `runtime_target: planning_v1`
   - keep the canonical phase order from `StrategyConfig`
   - keep required planning policy refs
   - omit `coverage_policy`
   - omit `phase_inputs`
6. Keep the negative examples simple enough that `C3` parser/preflight work can
   reuse them directly later.

Definition of done:

- the example pack exists and is navigable
- canonical examples are clean public examples, not fixture mirrors
- compatibility example is obviously non-canonical
- negative examples cover kind closure, unknown top-level key rejection,
  stage-family closure, runtime-owned field exclusion, and metadata-only field
  exclusion

### 6.3 Workstream C: Align docs and relabel runnable fixtures

Goal: stop the repo from teaching the wrong surface first.

Primary paths:

- `README.md`
- `examples/README.md`
- `docs/contributing.md`
- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`

Implementation tasks:

1. Update the three docs so the future public subset points to:
   - `docs/strategy_dsl_public_subset_contract.md`
   - `examples/harness/public_subset/README.md`
2. Preserve current runnable commands and current example paths where practical.
3. Change wording that currently calls the runnable deterministic planning
   example canonical public DSL.
4. Add explicit header comments to
   `examples/harness/strategies/deterministic_feature_planning_v1.yaml` that say:
   - this file is a runnable internal harness fixture
   - it preserves regression scaffolding
   - it is not the canonical public `C3 v1` example

Definition of done:

- no front-door doc teaches the fixture-backed planning strategy as the
  canonical public DSL example
- public readers can discover the contract doc and example pack from the repo
  front door
- runnable fixtures stay easy to find and easy to run

### 6.4 Workstream D: Add the contract drift wall

Goal: make it difficult for the repo to drift back into mixed stories.

Primary paths:

- `tests/test_harness_public_subset_contract.py`
- `tests/test_docs_surface.py`
- `tests/test_harness_example_strategy_wiring.py`

Implementation tasks:

1. Add `tests/test_harness_public_subset_contract.py`.
2. Extend `tests/test_docs_surface.py` so front-door routing points at the
   public contract and example pack first.
3. Extend `tests/test_harness_example_strategy_wiring.py` so the new public
   example pack and the old runnable fixture tree coexist with explicit labels.

Definition of done:

- docs, registry, and example pack cannot silently diverge
- canonical public examples cannot silently regain runtime-owned fields
- existing runnable example coverage remains intact

## 7. Test Review

Framework: `pytest`  
Goal: every contract decision frozen by `C2.9` gets a drift test.

### 7.1 Coverage diagram

```text
CONTRACT COVERAGE
=================
[+] anvil/harness/public_subset_registry.py
    |
    |-- canonical kinds
    |-- broader public built-ins
    |-- compatibility-only kinds
    |-- graph primitives
    |-- transition forms
    |-- stage families
    |-- role families and bindings
    |-- planning phase stage types
    |-- required planning policy refs
    |-- runtime-owned excluded fields
    `-- metadata-only fields

[+] docs/strategy_dsl_public_subset_contract.md
    |
    |-- must mirror registry names and exclusions
    |-- must separate public vs compatibility vs runtime-owned vs metadata-only
    `-- must state the C2.9/C3 boundary honestly

[+] examples/harness/public_subset/canonical/
    |
    |-- must use canonical names only
    |-- must carry dsl_version
    |-- must omit runtime-owned fields
    `-- must omit metadata-only fields

[+] examples/harness/public_subset/compatibility/
    |
    `-- must teach legacy accepted input without pretending it is canonical

[+] examples/harness/public_subset/negative/
    |
    |-- invalid_kind.yaml
    |-- unknown_top_level_key.yaml
    |-- invalid_stage_family.yaml
    |-- runtime_owned_phase_inputs.yaml
    `-- metadata_only_schema_version.yaml

[+] front-door docs
    |
    |-- README.md
    |-- examples/README.md
    `-- docs/contributing.md
        must point readers at the correct public surfaces first

[+] runnable fixture example
    |
    `-- examples/harness/strategies/deterministic_feature_planning_v1.yaml
        must remain runnable and must be explicitly labeled internal/fixture-backed
```

### 7.2 Required tests

#### A. `tests/test_harness_public_subset_contract.py`

This new test file must assert all of the following:

1. registry constants equal the exact sets listed in section 5.2
2. the contract doc contains each canonical kind, broader built-in kind,
   compatibility-only kind, stage family, role family, transition form,
   excluded field, and metadata-only field
3. canonical examples:
   - exist at the expected paths
   - carry `dsl_version: c3_strategy_v1`
   - use canonical kinds only
   - omit `analysis_review_v1`
   - omit `coverage_policy`
   - omit `phase_inputs`
   - omit `schema_version`
   - omit `subset`
4. canonical planning example:
   - includes `runtime_target: planning_v1`
   - declares phases in the exact canonical order
   - includes the required planning policy refs
5. canonical non-planning examples omit `runtime_target`
6. compatibility example:
   - exists at the expected path
   - uses `kind: analysis_review_v1`
   - is labeled compatibility-only in raw text or in the example-pack README
7. negative examples:
   - all exist
   - are indexed in `examples/harness/public_subset/README.md`
   - each map to the expected rejection reason

#### B. `tests/test_docs_surface.py`

Update existing docs-surface tests to assert:

- `README.md` links to `docs/strategy_dsl_public_subset_contract.md`
- `README.md` links to `examples/harness/public_subset/README.md`
- `examples/README.md` distinguishes canonical public examples from runnable
  harness fixtures
- `docs/contributing.md` uses the same taxonomy
- the planning run command still exists where intended
- the docs no longer call
  `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
  the canonical public DSL example

#### C. `tests/test_harness_example_strategy_wiring.py`

Update existing example-wiring tests to assert:

- the new public example-pack directories exist
- canonical, compatibility, and negative example counts match the plan
- the existing deterministic planning fixture example still exists at the
  current path
- the existing deterministic planning fixture raw text now labels it as
  internal or fixture-backed
- existing analysis-review example wiring assertions still pass

### 7.3 Suggested commands

```bash
poetry run pytest -q tests/test_harness_public_subset_contract.py
poetry run pytest -q tests/test_docs_surface.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Optional broader smoke tests if example surface changes spill further than
expected:

```bash
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_planning_graph.py
```

### 7.4 Diagram maintenance and code-comment verdict

Plan-level ASCII diagrams are required and are already included here.

Inline code-comment diagrams are not required in implementation files for
`C2.9`, because this branch should not add new multi-step runtime logic. If the
implementation unexpectedly adds logic beyond data/docs/test surfaces, that is a
scope-break smell and should be challenged before merging.

## 8. Reliability, Failure Modes, and Performance

### 8.1 Reliability rules

- `C2.9` must not change runtime behavior
- current runnable harness examples must keep their existing paths unless a move
  is strictly necessary
- canonical public examples must live in a separate namespace from internal
  runnable fixtures
- every public set that matters to `C3` must live in code data once

### 8.2 Failure modes registry

| Failure | User-visible impact | Planned protection |
|---|---|---|
| canonical example accidentally includes `phase_inputs` | public example teaches fixture scaffolding as public API | contract test asserts canonical examples omit runtime-owned fields |
| canonical example includes `schema_version` or `subset` | users mistake metadata for authoring keys | contract test asserts canonical examples omit metadata-only fields |
| `analysis_review_v1` appears in canonical docs or examples | legacy alias is mistaken for forward contract | contract test and docs-surface test enforce the canonical/compatibility split |
| contract doc and registry disagree | future `C3` work starts from conflicting truth | new contract test fails |
| front-door docs still point readers first to fixture examples | contributors keep learning the wrong surface | docs-surface test fails |
| runnable planning fixture loses its runnable status during relabeling | regression coverage breaks for the wrong reason | example-wiring test keeps path and raw-file presence stable |

### 8.3 Performance verdict

There is no meaningful runtime performance risk in this milestone because the
branch is artifact-, docs-, and test-focused.

The real risk is contract drift. The regression wall addresses that directly.

## 9. Worktree Parallelization Strategy

This branch is moderately parallelizable once the registry vocabulary is frozen.

### 9.1 Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Freeze registry and contract doc | `anvil/harness/`, `docs/` | — |
| B. Build public example pack | `examples/harness/public_subset/` | A |
| C. Align docs and relabel runnable planning fixture | `README.md`, `examples/`, `docs/`, `examples/harness/strategies/` | A |
| D. Add regression wall | `tests/`, plus read access to all surfaces above | B, C |

### 9.2 Parallel lanes

Lane A: foundation  
Freeze registry names, exclusions, versioning, and contract vocabulary.

Lane B: example pack  
Owns `examples/harness/public_subset/` and nothing else.

Lane C: docs alignment  
Owns front-door wording plus the header relabeling in
`examples/harness/strategies/deterministic_feature_planning_v1.yaml`.

Lane D: regression wall  
Owns the test integration pass after example and docs work land.

### 9.3 Execution order

```text
Lane A
  |
  +-----> Lane B
  |
  +-----> Lane C
             |
     Lane B + Lane C merge
             |
             v
           Lane D
```

Execution order:

1. Launch Lane A first.
2. After A lands, launch B and C in parallel worktrees.
3. Merge B and C.
4. Run D last as the merge-blocking drift wall.

### 9.4 Conflict flags

- Lane A and Lane B both care about exact registry names, so B must wait for A
- Lane A and Lane C both care about canonical terminology, so C must wait for A
- Lanes B and D both touch example-pack expectations, so D must run last
- Lanes C and D both touch docs-surface assertions, so D must run last
- do not expand Lane D into parser enforcement, that would break scope

## 10. Acceptance Checklist

- [ ] `docs/strategy_dsl_public_subset_contract.md` exists and is discoverable
- [ ] `anvil/harness/public_subset_registry.py` exists and is data-only
- [ ] `C3_GRAPH_DSL_KINDS` contains exactly `analysis_review_bounded_v1`, `analysis_review_trust_v1`, and `deterministic_feature_planning_v1`
- [ ] broader public built-ins are explicitly separated from the narrower `C3` graph-DSL claim
- [ ] `analysis_review_v1` is documented as compatibility-only, not canonical
- [ ] canonical public examples live under `examples/harness/public_subset/canonical/`
- [ ] canonical public examples carry `dsl_version: c3_strategy_v1`
- [ ] canonical public examples do not contain `coverage_policy`, `phase_inputs`, `schema_version`, or `subset`
- [ ] canonical non-planning examples omit `runtime_target`
- [ ] canonical planning example includes `runtime_target: planning_v1`
- [ ] compatibility example lives under `examples/harness/public_subset/compatibility/`
- [ ] negative examples live under `examples/harness/public_subset/negative/`
- [ ] front-door docs route readers to the contract doc and public example pack first
- [ ] the existing runnable deterministic planning strategy is explicitly labeled fixture-backed/internal
- [ ] `tests/test_harness_public_subset_contract.py` exists and passes
- [ ] `tests/test_docs_surface.py` and `tests/test_harness_example_strategy_wiring.py` are updated and pass
- [ ] no runtime behavior change is claimed or required for this milestone

## 11. Post-C2.9 Follow-Ups

These are explicitly after `C2.9`, not blockers for this plan:

- add parser/preflight enforcement for unknown top-level keys, closed kind
  registry, stage-family closure, runtime-owned field rejection, and
  metadata-only field rejection
- decide whether to freeze a public task-spec contract as a separate packet
- decide whether to publish richer public diagnostics guidance once runtime
  enforcement exists
- decide whether to widen the public surface later to imports, overlays, or
  broader graph composition

## 12. Completion Summary

- Step 0 verdict: scope accepted as contract-freeze work, not hidden `C3`
  runtime work
- What already exists: reused directly, especially `types.py`,
  `strategy_graph.py`, `providers.py`, the current docs entry points, and the
  existing docs/example tests
- Locked decisions: milestone boundary, registry ownership, versioning,
  canonical kinds, compatibility-only aliasing, runtime-owned exclusions, and
  example taxonomy are all frozen
- Architecture: one registry, one contract doc, one public example pack, one
  docs-routing pass, one regression wall
- Test review: full contract coverage is specified, including negative-example
  indexing and canonical/non-canonical example assertions
- Performance review: runtime performance risk is effectively zero; contract
  drift is the real risk and is directly covered
- Parallelization: one foundation lane, two safe content lanes, one final test
  lane
