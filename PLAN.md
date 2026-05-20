# PLAN: C3 Bounded Public Strategy DSL Enforcement

Status: unified, implementation-ready on `codex/c1b-planning-quality-proof`  
Milestone: `C3`  
Prepared from repo state on: `2026-05-20`

Source of truth:
- `/home/azureuser/.gstack/projects/Spenquatch-forge/azureuser-c3-bounded-public-strategy-graph-dsl-design-20260519-141721.md`
- `/home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md`
- `/home/azureuser/__Active_Code/forge/docs/roadmap.md`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`
- `/home/azureuser/__Active_Code/forge/docs/contributing.md`
- `/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/types.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/nodes/prepare_run.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/strategy_graph.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/runner.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_public_subset_contract.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`

Plan authority:
- this file is the implementation authority for `C3` on this branch
- the May 19 design doc is intent authority for the bounded public DSL direction
- `docs/strategy_dsl_public_subset_contract.md` and
  `anvil/harness/public_subset_registry.py` are vocabulary authority for the
  frozen public subset
- if public-contract wording and runtime-owned internals disagree, keep the
  public boundary strict at authoring time and keep runtime truth owned by the
  existing builder, graph spec, and planning runtime after acceptance

## Executive Summary

`C2` and `C2.9` got Forge to an honest place on planning truth and public
contract vocabulary, but they stopped short of live enforcement.

The repo now has the right frozen nouns:

- the public registry
- the canonical example pack
- the compatibility example
- the negative fixtures
- the internal runnable planning fixture

What it does not yet have is one enforcement seam that makes those nouns real.
Today, direct `StrategyConfig.from_dict()` callers, `prepare_run_node()`,
`validator_preflight_node()`, `runner.py`, and fixture-oriented tests can still
reach parse/runtime behavior without a shared public-boundary gate.

`C3` closes that gap by adding one shared raw-payload validation seam, making
parser enforcement universal, surfacing compatibility warnings in preflight, and
proving the whole thing with canonical/compatibility/negative/internal fixture
coverage.

## 1. Objective and Success Bar

### 1.1 Objective

Ship one enforceable public strategy authoring surface for `C3` that:

- accepts canonical public `dsl_version: c3_strategy_v1` strategies
- accepts the one compatibility-only legacy input `analysis_review_v1`
- preserves existing internal fixture-backed planning behavior
- rejects public-contract violations before model work
- keeps the current strategy graph builder and runtime targets authoritative

### 1.2 Exact problem statement

Forge currently tells users that:

- the canonical public `C3 v1` examples live under
  `examples/harness/public_subset/canonical/`
- the compatibility-only legacy example lives under
  `examples/harness/public_subset/compatibility/`
- the negative fixtures represent real contract violations

But runtime behavior still relies too heavily on convention:

- direct parser entrypoints do not universally enforce the public boundary
- preflight does not yet own crisp compatibility-vs-canonical messaging for the
  public subset
- internal fixture scaffolding and canonical public authoring can still be
  confused if enforcement is implemented too late or too narrowly

That means the public contract is frozen in docs and tests, but not yet fully
enforced in code.

### 1.3 Success bar

`C3` is complete only when all of the following are true:

- canonical public examples with `dsl_version: c3_strategy_v1` parse cleanly
  through `StrategyConfig.from_dict()`
- canonical public examples then pass `validator_preflight_node()` without
  public-surface warnings or invalid-config failures
- compatibility-only `analysis_review_v1` input remains accepted, but is
  explicitly labeled as legacy and non-canonical before model work
- each negative public fixture fails with one targeted public-contract error
- invalid public examples stop before provider initialization or runtime graph
  execution
- internal fixture-backed strategies under `examples/harness/strategies/`
  continue to work, including `coverage_policy` and `phase_inputs`
- no second parser, no public-only runtime target, and no alternate graph-spec
  builder are introduced
- docs and regression tests clearly separate canonical public, compatibility,
  and internal fixture-backed surfaces

## 2. Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Public-contract trigger | `dsl_version: c3_strategy_v1` | explicit opt-in marker for canonical public authoring |
| Canonical public kinds | `analysis_review_bounded_v1`, `analysis_review_trust_v1`, `deterministic_feature_planning_v1` | already frozen in `C2.9` |
| Broader public built-ins | `single_pass`, `pfr_v1` remain public but outside the narrowed `C3` proof surface | keeps `C3` focused |
| Compatibility-only input | `analysis_review_v1` without `dsl_version` remains accepted | preserves intentional legacy bridge |
| Enforcement ownership | parser-owned validation with preflight-owned messaging | covers all direct parse entrypoints without duplicating rule lists |
| Runtime architecture | reuse current builder, graph spec, runtime targets, and reporting flows | no second compiler, no second runner |
| Runtime-owned exclusions | `coverage_policy`, `phase_inputs` stay internal-only | canonical public authoring must not own fixture/runtime scaffolding |
| Metadata-only exclusions | `schema_version`, `subset` stay runtime-emitted only | graph metadata is not public authoring input |
| Public boundary | strategy spec only | task-spec freezing is later work |
| State policy | do not add new durable state only to label authoring surface | warning/error surfaces are enough for `C3` |
| Planning artifact schema | no `plan.json` or `plan.md` contract change | `C3` is an authoring-boundary milestone, not an artifact-schema milestone |

## 3. Step 0: Scope Challenge

### 3.1 What already exists

| Sub-problem | Existing surface | Reuse decision |
|---|---|---|
| Frozen public vocabulary | `anvil/harness/public_subset_registry.py` | reuse as the single source of truth for kinds, stage families, exclusions, and canonical planning phase order |
| Public contract narrative | `docs/strategy_dsl_public_subset_contract.md` | reuse as the normative authoring description; update only where enforcement becomes live |
| Canonical, compatibility, and negative corpora | `examples/harness/public_subset/` | reuse as the acceptance corpus rather than inventing a second fixture family |
| Typed strategy parsing | `anvil/harness/types.py` | extend the existing parser instead of adding a public-only parser |
| Direct runtime load path | `anvil/harness/nodes/prepare_run.py` | treat as proof that parser-owned enforcement is mandatory, not optional |
| Preflight invalid-config surface | `anvil/harness/nodes/validator_preflight.py` | reuse for warning/error adaptation before model work |
| Runtime graph selection | `anvil/harness/strategy_graph.py` | keep the current runtime-target routing authoritative |
| Direct execution entrypoint | `anvil/harness/runner.py` | audit because it reparses strategy payloads directly |
| Analysis-review subgraph bridge | `anvil/harness/subgraphs/analysis_review_v1.py` | audit because it reparses bounded payloads directly |
| Internal planning fixture | `examples/harness/strategies/deterministic_feature_planning_v1.yaml` | preserve as internal fixture-backed scaffolding, not public canonical authoring |
| Existing public-subset drift wall | `tests/test_harness_public_subset_contract.py`, `tests/test_harness_example_strategy_wiring.py`, `tests/test_docs_surface.py` | extend rather than replace |

### 3.2 Minimum complete scope

This is the minimum complete implementation. Separate edit-required surfaces from
audit-required surfaces so the diff stays honest.

Edit-required surfaces:

1. `anvil/harness/public_subset_registry.py` only if shared constants need
   additive cleanup for enforcement reuse
2. new shared helper: `anvil/harness/public_subset_validation.py`
3. `anvil/harness/types.py`
4. `anvil/harness/nodes/validator_preflight.py`
5. `tests/test_harness_public_subset_contract.py`
6. `tests/test_harness_example_strategy_wiring.py`
7. one focused enforcement test file:
   - `tests/test_harness_public_subset_enforcement.py`, or
   - equivalent concentrated coverage in an existing harness test file
8. `tests/test_harness_strategy_graph.py`
9. `tests/test_harness_cli_command.py`
10. `tests/test_harness_standalone_cli.py`
11. `docs/strategy_dsl_public_subset_contract.md`
12. `README.md`
13. `examples/README.md`
14. `docs/contributing.md`
15. `docs/roadmap.md`

Audit-required surfaces:

1. `anvil/harness/nodes/prepare_run.py`
2. `anvil/harness/runner.py`
3. `anvil/harness/subgraphs/analysis_review_v1.py`
4. `anvil/harness/strategy_graph.py`
5. `anvil/harness/planning_runtime.py`

Audit-required means:

- confirm the parser-owned gate covers the path without a second validator
- add or update tests if the path proves a missed branch
- do not patch the module unless the audit shows a real loophole

### 3.3 Complexity verdict

This milestone touches more than eight files. That is normally a smell.

Here it is justified because the contract really spans:

- raw strategy payload classification
- typed parser integration
- preflight warning/error adaptation
- CLI invalid-config behavior
- direct parse entrypoint audits
- example-pack regression coverage
- contributor-facing docs

What would be overbuilt:

- a second public parser
- path-based "public mode" detection
- a second graph-spec type
- a second runtime target
- a JSON schema compiler or new standalone linter binary
- task-spec freezing in the same cut

### 3.4 Search and reuse verdict

This plan should stay boring by default.

Reuse calls:

- [Layer 1] reuse `public_subset_registry.py` for all frozen vocabulary
- [Layer 1] reuse `StrategyConfig.from_dict()` as the universal parse gate
- [Layer 1] reuse `validator_preflight_node()` for warning/error adaptation
- [Layer 1] reuse the current CLI invalid-config surface rather than inventing
  a new command
- [Layer 3] validate raw payloads before typed coercion, then hand accepted
  payloads to the existing parser and runtime flow

### 3.5 TODOS cross-reference

`/home/azureuser/__Active_Code/forge/docs/project_management/future/TODOS.md`
contains no blocker for `C3`.

`C3` should explicitly leave follow-up room for:

- public task-spec contract work
- eventual retirement of `analysis_review_v1` compatibility input
- richer authoring diagnostics or formatting tooling
- future decisions about whether `single_pass` and `pfr_v1` should enter or
  leave the narrowed canonical proof surface

### 3.6 Completeness and distribution verdict

Completeness verdict:

- the complete version includes canonical accept, compatibility accept, and
  negative reject behavior
- the complete version proves that direct parser entrypoints cannot bypass the
  public boundary
- the complete version preserves internal runnable planning fixtures
- the complete version updates docs so runtime behavior and author guidance say
  the same thing

A docs-only or examples-only cut would be dishonest and only save minutes.

Distribution verdict:

- this is not a new binary or package
- the distribution surface remains the existing harness CLI and tests
- because Forge is a developer tool, parser behavior plus contributor docs are
  part of the product surface for this milestone

### 3.7 NOT in scope

- a public task-spec contract
- a hosted authoring UI or editor integration
- removal of internal fixture-backed strategies
- removal of `single_pass` or `pfr_v1`
- full retirement of `analysis_review_v1`
- a new standalone strategy compiler or linter binary
- changes to `C2` planning artifact schema or planning runtime truth behavior
- provider/model behavior changes unrelated to public-surface enforcement

## 4. Architecture Plan

### 4.1 Exact enforcement model

This plan makes one explicit architectural choice:

- `StrategyConfig.from_dict()` becomes the universal enforcement gate for the
  public authoring boundary
- one new shared helper module,
  `anvil/harness/public_subset_validation.py`, owns raw-payload classification
  and public-surface validation
- `validator_preflight_node()` reuses that helper for compatibility messaging
  and invalid-config adaptation, but it does not own independent copies of the
  allowlists or exclusion rules

Why this is the right choice:

- `prepare_run_node()` calls `StrategyConfig.from_dict()` directly
- `runner.py` calls `StrategyConfig.from_dict()` directly
- `analysis_review_v1.py` reparses bounded strategy payloads directly
- tests also exercise `StrategyConfig.from_dict()` directly

If enforcement lived only in preflight, those paths would remain loopholes.

### 4.2 Shared helper contract

The helper module should expose exactly two public seams:

1. `classify_public_strategy_surface(raw_payload)`
   - returns one of:
     - `canonical_public`
     - `compatibility_only`
     - `internal_or_private`

2. `validate_public_strategy_payload(raw_payload)`
   - validates only the canonical public surface
   - raises `ValueError` with one crisp reason when the payload violates the
     public contract
   - no side effects

The helper must not:

- mutate strategy kinds
- infer public mode from file path
- build graph specs
- know about task-spec compatibility
- emit warnings directly into run state

### 4.3 Canonical authoring and runtime flow

```text
strategy.yaml
    |
    v
load_structured_file()
    |
    v
classify_public_strategy_surface(raw_payload)
    |
    +--> canonical_public
    |      - requires dsl_version: c3_strategy_v1
    |      - kind must be one of the frozen canonical kinds
    |      - top-level keys must be in the public allowlist
    |      - stage families must be in the frozen set
    |      - planning examples must use canonical phase order
    |      - no runtime-owned fields
    |      - no metadata-only fields
    |
    +--> compatibility_only
    |      - kind: analysis_review_v1
    |      - accepted runtime input, not canonical public authoring
    |      - warning surfaced in preflight
    |
    +--> internal_or_private
           - existing internal fixtures remain allowed
           - current runtime-only scaffolding remains allowed
    |
    v
validate_public_strategy_payload(raw_payload)  [canonical_public only]
    |
    v
StrategyConfig.from_dict()
    |
    v
validator_preflight_node()
    |
    +--> canonical invalid payload
    |      stop before model work
    |      run_verdict=invalid_config
    |
    +--> compatibility_only payload
    |      accepted with explicit legacy warning
    |
    +--> accepted config
           existing graph/runtime path
    |
    v
build_strategy_graph_spec(...)
    |
    v
runtime_target routing
```

### 4.4 Ownership boundaries

| Surface | Owner | Responsibility |
|---|---|---|
| canonical kinds, stage families, exclusions, canonical planning phase order | `public_subset_registry.py` | vocabulary source of truth |
| raw public-surface classification and canonical validation | `public_subset_validation.py` | classify and validate raw payloads |
| typed strategy parsing | `types.py` | coerce accepted payloads into `StrategyConfig` |
| compatibility warning and invalid-config stop behavior | `validator_preflight.py` | adapt parser/helper results into run-state warnings/errors |
| graph spec construction and runtime target routing | `strategy_graph.py` | remain runtime-owned after acceptance |
| planning fixture runtime scaffolding | `planning_runtime.py` and internal strategy fixtures | remain valid for internal/private surfaces only |
| direct execution entrypoints | `prepare_run.py`, `runner.py`, subgraphs | audit to ensure the parser-owned gate is sufficient |

### 4.5 Canonical boundary rules

Canonical public payloads are allowed to declare only:

- `dsl_version`
- `name`
- `kind`
- `roles`
- `runtime_target`
- `phases`
- `artifact_policy`
- `determinism_policy`
- `discovery_policy`
- `rubric_policy`
- `stop_policy`
- `trust_review`

Canonical public payloads must obey all of these rules:

- `dsl_version` must equal `c3_strategy_v1`
- `kind` must be one of:
  - `analysis_review_bounded_v1`
  - `analysis_review_trust_v1`
  - `deterministic_feature_planning_v1`
- analysis-review canonical examples omit `runtime_target`
- planning canonical examples require `runtime_target: planning_v1`
- planning canonical examples must declare the four canonical phase
  `stage_type` values in the frozen order
- role keys must stay inside the frozen public stage-family set
- `coverage_policy` and `phase_inputs` are forbidden in canonical public mode
- `schema_version` and `subset` are forbidden in canonical public mode

Compatibility-only payloads obey these rules:

- `kind: analysis_review_v1`
- no `dsl_version`
- still accepted by parser and preflight
- warning must say it is legacy accepted input, not canonical public `C3 v1`

Internal/private payloads obey these rules:

- may continue using runtime-owned scaffolding needed by internal fixtures
- must not be relabeled as canonical public authoring in docs or examples

### 4.6 Ordered implementation sequence

1. Add the shared helper and lock the exact classification/validation rules.
2. Wire `StrategyConfig.from_dict()` to call the helper before typed coercion.
3. Update `validator_preflight_node()` to reuse the helper for compatibility
   warnings and invalid-config adaptation.
4. Extend tests so parser, preflight, CLI, and example wiring all prove the
   same contract.
5. Update docs only after the live enforcement behavior is in place.

Hard rule:

- `strategy_graph.py`, `planning_runtime.py`, and reporting code are downstream
  truth surfaces after acceptance. `C3` does not duplicate or reinterpret them.

## 5. Code Quality Rules

### 5.1 Boring by default

- no second parser
- no second graph spec
- no public-only runtime target
- no path-based "public mode" heuristics
- no duplicate allowlists across parser and preflight

### 5.2 Explicit over clever

- public mode is triggered by `dsl_version`, not by vibes
- compatibility is explicit, not inferred
- one negative fixture should fail for one crisp reason
- one helper owns the boundary; everyone else calls it

### 5.3 DRY boundaries

Keep one source of truth for:

- canonical public kinds
- compatibility-only kinds
- public stage families
- runtime-owned excluded fields
- metadata-only excluded fields
- canonical planning phase order

### 5.4 Smallest clean diff

Prefer one focused shared helper plus small integrations over scattering public
contract logic across every caller.

The smallest acceptable clean diff is:

- one new helper module
- one parser integration
- one preflight integration
- tests and docs that reflect the live behavior

### 5.5 Diagram maintenance

If the helper logic or preflight integration grows a non-obvious branch split,
add one short ASCII diagram comment near the boundary. Do not add decorative
diagrams.

## 6. Test Review

100% coverage is the goal for the new public-authoring codepaths. The critical
coverage is branch coverage across canonical, compatibility, internal, and
invalid public inputs.

### 6.1 Code path and user-flow diagram

```text
CODE PATHS
[+] raw strategy surface classification
  ├── [TEST] canonical public payload identified by dsl_version
  ├── [TEST] compatibility-only legacy payload identified without dsl_version
  └── [TEST] internal fixture-backed payload bypasses canonical-only exclusions

[+] parser-owned public validation
  ├── [TEST] canonical bounded example accepted
  ├── [TEST] canonical trust example accepted
  ├── [TEST] canonical planning example accepted
  ├── [TEST] invalid kind rejected
  ├── [TEST] unknown top-level key rejected
  ├── [TEST] invalid public stage family rejected
  ├── [TEST] runtime-owned phase_inputs rejected in public mode
  └── [TEST] metadata-only schema_version rejected in public mode

[+] direct parse entrypoints
  ├── [TEST] prepare_run_node cannot bypass public validation
  ├── [TEST] runner direct parse cannot bypass public validation
  └── [TEST] internal planning fixture still parses with coverage_policy + phase_inputs

[+] validator preflight
  ├── [TEST] invalid public payload stops before model work
  ├── [TEST] compatibility-only legacy input emits warning, not error
  └── [TEST] existing task/runtime mismatch checks still fire

[+] strategy graph routing
  ├── [TEST] canonical planning example routes to planning_v1
  ├── [TEST] canonical analysis public examples route to analysis_review_v1
  └── [TEST] compatibility-only legacy input still normalizes to bounded runtime behavior

[+] CLI/report invalid-config surface
  ├── [TEST] invalid public example exits non-zero
  ├── [TEST] summary/error text names the contract violation
  └── [TEST] no provider/model work starts on invalid public input

USER FLOWS
[+] author uses canonical public example
  ├── [TEST] parse + preflight succeeds
  └── [TEST] runtime routing matches the declared public example shape

[+] author uses compatibility-only legacy input
  ├── [TEST] run is accepted
  └── [TEST] warning says "legacy accepted input, not canonical public C3"

[+] author copies a negative fixture by mistake
  ├── [TEST] run fails before model work
  └── [TEST] operator sees a precise fix instead of a late runtime error

[+] maintainer runs internal planning fixture
  ├── [TEST] internal fixture still loads
  └── [TEST] deterministic fixture-backed stop-path coverage is preserved
```

### 6.2 Required test files

- `tests/test_harness_public_subset_contract.py`
- `tests/test_harness_example_strategy_wiring.py`
- one focused enforcement file:
  - `tests/test_harness_public_subset_enforcement.py`, or
  - equivalent focused coverage in an existing file
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_docs_surface.py`

### 6.3 Regression rule

Every new public-contract rule must land with:

- one example or inline payload that exercises the rule
- one parser/preflight test that proves the acceptance or rejection behavior
- one message assertion that proves the error or warning is actionable

No docs-only contract rule is allowed.

### 6.4 Required validation commands

```bash
poetry run pytest -q tests/test_harness_public_subset_contract.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
poetry run pytest -q tests/test_docs_surface.py
```

If a dedicated enforcement file is added:

```bash
poetry run pytest -q tests/test_harness_public_subset_enforcement.py
```

## 7. Performance Review

This milestone is not performance-heavy, but it still has one real requirement:
invalid public authoring must fail cheaply.

Performance rules:

- raw public validation runs once per parse
- preflight reuses classification results or reuses the same helper, but does
  not duplicate deep validation logic in a second implementation
- validation cost stays linear in top-level keys, roles, and phases
- invalid public payloads must not initialize providers or enter runtime graph
  execution
- compatibility warnings must not require a separate graph build

The only acceptable expensive path is a valid strategy entering the existing
runtime flow.

## 8. Failure Modes Registry

| Codepath | Realistic failure | Test required | Error handling required | User-visible outcome |
|---|---|---|---|---|
| parser-owned validation | canonical public payload silently ignores forbidden `phase_inputs` | yes | hard parse failure surfaced as invalid-config in preflight | clear authoring error |
| parser-owned validation | canonical payload accepts `schema_version` or `subset` and looks legitimate | yes | hard parse failure surfaced as invalid-config | clear authoring error |
| compatibility path | `analysis_review_v1` is accepted but looks canonical | yes | warning before model work | explicit legacy notice |
| direct parse entrypoint | `prepare_run_node()` bypasses the boundary while preflight would catch it | yes | parser owns the gate | no loophole |
| internal planning fixture | parser-owned enforcement accidentally rejects `coverage_policy` or `phase_inputs` on internal fixtures | yes | classify as internal/private before canonical checks | no regression for internal fixture corpus |
| graph routing | accepted canonical public example routes differently from its current runtime family | yes | route through current graph-spec builder | predictable behavior |
| CLI/reporting | invalid public example exits as success | yes | non-zero exit and invalid_config verdict | automation sees failure |
| docs/examples | docs still describe enforcement as future-only after behavior is live | yes | doc refresh + docs-surface tests | contributor trust preserved |

Critical-gap rule:

- no public authoring failure may be silent, untested, and only discoverable
  after model work

## 9. Worktree Parallelization Strategy

This plan has real parallelization opportunity once the shared helper contract
is frozen.

### 9.1 Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Freeze public validation contract | `anvil/harness/` validation surfaces | — |
| B. Parser + preflight integration | `anvil/harness/` parse/preflight surfaces | A |
| C. Example pack and docs alignment | `examples/harness/public_subset/`, `docs/`, `README.md`, `examples/README.md` | A |
| D. Regression wall | `tests/` | B, C |

### 9.2 Parallel lanes

```text
Lane A: contract freeze
  A1. helper API
  A2. canonical allowlist and exclusion rules
  A3. canonical planning-specific rules

Lane B: parser + preflight integration
  B1. StrategyConfig.from_dict() hook-in
  B2. preflight warning/error adaptation
  B3. direct parse entrypoint audit notes or fixes

Lane C: docs + examples
  C1. contract doc wording refresh
  C2. example-pack wording and taxonomy refresh
  C3. README / contributing / roadmap alignment

Lane D: regression wall
  D1. parser acceptance and rejection tests
  D2. direct-entrypoint bypass tests
  D3. CLI invalid-config and no-model-work tests
```

### 9.3 Execution order

1. Launch Lane A first and freeze the helper API plus exact validation rules.
2. Launch Lanes B and C in parallel after A is stable.
3. Merge B and C.
4. Launch Lane D last because it must test the final accepted behavior and final
   wording.

### 9.4 Conflict flags

- Lanes B and C must not invent vocabulary beyond Lane A.
- Lane B must not hardcode a second copy of the allowlist or exclusion sets.
- Lane C must not relabel the internal planning fixture as canonical public
  authoring.
- Lane D must assert final error text and final taxonomy, not draft wording.

## 10. Implementation Tasks

Synthesized from the design lineage, the live repo seams, and the current
contract gap.

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — shared public-boundary helper — add `anvil/harness/public_subset_validation.py` with one classification seam and one canonical validation seam driven entirely by the frozen registry constants
  - Surfaced by: Step 0 + Architecture review — the contract needs one owner
  - Files: `anvil/harness/public_subset_validation.py`, optional light registry cleanup
  - Verify: focused enforcement coverage plus `tests/test_harness_public_subset_contract.py`
- [ ] **T2 (P1, human: ~1.5h / CC: ~15min)** — parser-owned enforcement — wire `StrategyConfig.from_dict()` to call the shared helper before typed coercion so direct parse callers cannot bypass the public boundary
  - Surfaced by: Architecture review — preflight-only enforcement leaves real loopholes
  - Files: `anvil/harness/types.py`
  - Verify: parser acceptance/rejection tests plus direct-entrypoint coverage
- [ ] **T3 (P1, human: ~1.5h / CC: ~15min)** — preflight compatibility and invalid-config adaptation — reuse the shared helper in `validator_preflight_node()` for legacy warnings and invalid-config stop behavior without duplicating rule lists
  - Surfaced by: Architecture + Failure-modes review — users need precise answers before model work starts
  - Files: `anvil/harness/nodes/validator_preflight.py`
  - Verify: `tests/test_harness_cli_command.py`, `tests/test_harness_standalone_cli.py`
- [ ] **T4 (P1, human: ~1h / CC: ~10min)** — audit direct parse entrypoints — confirm `prepare_run_node()`, `runner.py`, `analysis_review_v1.py`, and graph-building helpers are covered by parser-owned enforcement and patch only if the audit reveals a real bypass
  - Surfaced by: Step 0 scope challenge — these are the easiest loopholes to miss
  - Files: audit of `anvil/harness/nodes/prepare_run.py`, `anvil/harness/runner.py`, `anvil/harness/subgraphs/analysis_review_v1.py`, `anvil/harness/strategy_graph.py`
  - Verify: direct-entrypoint tests in example wiring and focused enforcement coverage
- [ ] **T5 (P1, human: ~2h / CC: ~20min)** — regression wall for canonical, compatibility, and internal/private examples — add or tighten acceptance and rejection tests so one violation yields one targeted failure and internal planning scaffolding remains intact
  - Surfaced by: Test review — the contract is not real until the negative fixtures become live enforcement coverage
  - Files: `tests/test_harness_public_subset_contract.py`, `tests/test_harness_example_strategy_wiring.py`, focused enforcement tests, CLI tests
  - Verify: targeted pytest commands for contract, wiring, graph, and CLI
- [ ] **T6 (P2, human: ~1h / CC: ~10min)** — docs and roadmap alignment — update the contract doc, examples README, contributor docs, and roadmap so they describe enforcement as live and preserve the canonical/compatibility/internal distinction
  - Surfaced by: Scope review — contributors should not need to reverse-engineer the boundary from tests
  - Files: `docs/strategy_dsl_public_subset_contract.md`, `README.md`, `examples/README.md`, `docs/contributing.md`, `docs/roadmap.md`
  - Verify: `poetry run pytest -q tests/test_docs_surface.py`

## 11. Retrospective Learning From This Branch

The branch history and current file layout point to one important lesson:

- `C2` and `C2.9` already paid the cost to make planning and public vocabulary
  honest
- the main way `C3` can fail now is not "missing ideas"
- it is enforcing the right idea in the wrong place

That means review posture for `C3` should stay aggressive about:

- raw payload validation before typed coercion
- not duplicating runtime vocabulary in more than one place
- preserving internal fixture-backed planning behavior
- keeping docs, example taxonomy, parser behavior, and tests in lockstep

## 12. Completion Summary

`C3` is ready to call done only when this checklist is true:

- [ ] canonical public `c3_strategy_v1` examples are accepted by `StrategyConfig.from_dict()`
- [ ] canonical public examples then pass preflight cleanly
- [ ] compatibility-only `analysis_review_v1` input is accepted with an explicit non-canonical warning
- [ ] each negative public fixture fails before model work with one targeted invalid-config reason
- [ ] direct parse entrypoints have been audited and no public-boundary bypass remains
- [ ] internal fixture-backed planning strategies still accept runtime-owned scaffolding
- [ ] accepted public canonical specs route through the existing runtime graph families with no second compiler
- [ ] CLI exits non-zero for invalid public authoring
- [ ] docs and example pack describe live enforcement accurately
- [ ] task-spec freezing is still explicitly out of scope

## 13. Post-C3 Follow-Ups

These are explicitly after `C3`, not blockers for this plan:

- public task-spec contract definition and enforcement
- eventual retirement plan for `analysis_review_v1`
- richer authoring diagnostics or formatter/generator support
- broader decisions about whether `single_pass` and `pfr_v1` should move into or
  out of the narrowed canonical proof surface
