# Strategy DSL Public Subset Contract

## 1. Scope and milestone boundary

This document freezes the `C2.9` public strategy-spec subset for future `C3`
authoring work.

- It covers the public strategy-spec surface only.
- It does not claim parser enforcement, preflight enforcement, or runtime
  wiring already exists.
- It does not freeze a public task-spec contract in this branch.
- `C2.9` ends at contract-freeze artifacts plus drift tests.

## 2. Canonical public strategy kinds versus broader public built-ins

Canonical `C3` graph-DSL kinds:

- `analysis_review_bounded_v1`
- `analysis_review_trust_v1`
- `deterministic_feature_planning_v1`

Broader public built-ins that remain public but are not the narrowed `C3`
graph-DSL proof surface:

- `single_pass`
- `pfr_v1`

## 3. Compatibility-only kinds

Compatibility-only accepted runtime input:

- `analysis_review_v1`

`analysis_review_v1` is not a canonical public `C3 v1` authoring example.

## 4. Public versioning via `dsl_version`

Canonical public examples declare:

- `dsl_version: c3_strategy_v1`

## 5. Public graph primitives

The frozen public graph primitives are:

- `stage`
- `linear_edge`
- `conditional_branch`
- `bounded_loop`
- `terminal_outcome`
- `planning_phase`

## 6. Public transition forms

The frozen public transition forms are:

- `linear_next`
- `enumerated_branch`
- `bounded_loop_back_edge`
- `terminal_exit`

## 7. Public stage families and role-family bindings

Public stage families:

- `solver`
- `proposer`
- `falsifier`
- `patcher`
- `critic`
- `reviser`
- `auditor`
- `focus_gate`
- `planner`

Public role families:

- `execute`
- `critique`
- `refine`
- `review`

Frozen stage-family to role-family bindings:

- `solver -> execute`
- `proposer -> execute`
- `planner -> execute`
- `focus_gate -> execute`
- `falsifier -> critique`
- `critic -> critique`
- `patcher -> refine`
- `reviser -> refine`
- `auditor -> review`

## 8. Planning-specific canonical phase order and required policy refs

Canonical planning phase stage types:

- `rubric_design_doc`
- `architecture_seam_decomposition`
- `parallel_workstream_planning`
- `executable_slice_emission`

Required planning policy refs:

- `artifact_policy`
- `determinism_policy`
- `discovery_policy`
- `rubric_policy`
- `stop_policy`

Canonical planning examples include `runtime_target: planning_v1`.
Canonical non-planning examples omit `runtime_target`.

## 9. Runtime-owned excluded fields

These runtime-owned fields are real runtime surfaces, but they are not part of
the canonical public strategy authoring subset:

- `coverage_policy`
- `phase_inputs`

## 10. Metadata-only fields

These metadata-only fields are runtime-emitted graph labels, not public
authoring keys:

- `schema_version`
- `subset`

## 11. Canonical example taxonomy

Canonical public examples live under:

- `examples/harness/public_subset/canonical/`

Compatibility-only accepted input examples live under:

- `examples/harness/public_subset/compatibility/`

Negative contract fixtures live under:

- `examples/harness/public_subset/negative/`

The existing runnable harness fixture
`examples/harness/strategies/deterministic_feature_planning_v1.yaml` remains
useful for regression coverage, but it is internal fixture-backed scaffolding,
not the canonical public `C3 v1` example.

## 12. Explicit exclusions and post-`C2.9` follow-up boundary

This contract does not:

- wire `anvil/harness/public_subset_registry.py` into runtime behavior
- relabel compatibility-only, runtime-owned, or metadata-only surfaces as
  canonical public DSL
- implement parser enforcement, preflight enforcement, or runtime enforcement
- freeze a public task-spec contract

Post-`C2.9` work may add enforcement and diagnostics, but that work belongs to
later milestones rather than this contract-freeze branch.
