# Strategy DSL Public Subset Contract

## 1. Scope and live enforcement

This document describes the live bounded public `C3` strategy-authoring
surface.

- `StrategyConfig.from_dict()` is the universal public-boundary enforcement
  gate.
- `anvil/harness/public_subset_validation.py` owns raw-payload
  classification and canonical-public validation.
- `validator_preflight_node()` reuses that parser-owned boundary to emit the
  compatibility warning path and invalid-config adaptation before model work
  starts.
- Task-spec enforcement remains out of scope for this milestone.

## 2. Surface classification

Every raw strategy payload is treated as one of these surfaces:

- `canonical_public`: the payload declares `dsl_version` and is validated as
  canonical public authoring
- `compatibility_only`: the payload omits `dsl_version` and uses legacy kind
  `analysis_review_v1`
- `internal_or_private`: every remaining payload, including internal and
  fixture-backed harness strategies

Omitting `dsl_version` does not make a payload canonical public. It leaves the
payload on either the compatibility-only or internal/private surface.

## 3. Canonical public version and kinds

Canonical public examples must declare:

- `dsl_version: c3_strategy_v1`

Canonical public `kind` values are:

- `analysis_review_bounded_v1`
- `analysis_review_trust_v1`
- `deterministic_feature_planning_v1`

Declaring `dsl_version` on any other kind is rejected at the parser boundary.

## 4. Canonical public top-level rules

Canonical public authoring is restricted to the registry-owned allowlist in
`CANONICAL_PUBLIC_TOP_LEVEL_FIELDS`.

Canonical public authoring must not declare runtime-owned fields:

- `coverage_policy`
- `phase_inputs`

Canonical public authoring must not declare metadata-only fields:

- `schema_version`
- `subset`

Unknown top-level keys are rejected as invalid canonical public authoring.

## 5. Public graph primitives

The canonical public graph primitives are:

- `stage`
- `linear_edge`
- `conditional_branch`
- `bounded_loop`
- `terminal_outcome`
- `planning_phase`

## 6. Public transition forms

The canonical public transition forms are:

- `linear_next`
- `enumerated_branch`
- `bounded_loop_back_edge`
- `terminal_exit`

## 7. Public stage families and role-family bindings

Canonical public role keys must stay within these public stage families:

- `solver`
- `proposer`
- `falsifier`
- `patcher`
- `critic`
- `reviser`
- `auditor`
- `focus_gate`
- `planner`

The frozen stage-family to role-family bindings are:

- `solver -> execute`
- `proposer -> execute`
- `planner -> execute`
- `focus_gate -> execute`
- `falsifier -> critique`
- `critic -> critique`
- `patcher -> refine`
- `reviser -> refine`
- `auditor -> review`

## 8. Planning-specific canonical requirements

Canonical planning public authoring is the `deterministic_feature_planning_v1`
kind with:

- `runtime_target: planning_v1`
- `planning_execution.mode: graph_owned` for deterministic-only planning, or
  `planning_execution.mode: graph_owned_with_planner_review` for deterministic
  planning plus bounded provider review
- all required planning policy refs:
  `artifact_policy`, `determinism_policy`, `discovery_policy`,
  `rubric_policy`, and `stop_policy`
- a non-empty `phases` list
- canonical planning phase order:
  `rubric_design_doc`, `architecture_seam_decomposition`,
  `parallel_workstream_planning`, `executable_slice_emission`
- deterministic-only planning must omit `roles`
- planner-review planning must declare exactly one role, `roles.planner`, with
  a provider family key and read-only access
- deterministic planning is the bounded canonical first pass for seams,
  workstreams, slices, and deterministic coverage truth
- planner review is advisory only: the runtime invokes it after deterministic
  seams, workstreams, slices, and coverage have already been derived, and it
  reports expansion delta without replacing canonical structure

Canonical non-planning public authoring:

- must omit `runtime_target`
- must omit `phases`
- must omit `planning_execution`
- must omit planning-only policy refs

## 9. Compatibility-only input

`analysis_review_v1` remains accepted only as compatibility input when
`dsl_version` is omitted.

- It is not a canonical public `C3 v1` authoring example.
- Preflight emits an explicit legacy warning for this input.
- Docs and examples should route new public authoring to the canonical
  `analysis_review_bounded_v1` and `analysis_review_trust_v1` examples instead.

## 10. Internal and private preserved surfaces

Everything outside canonical public authoring and the one compatibility-only
path remains internal or private for this milestone.

This includes the runnable harness fixture
`examples/harness/strategies/deterministic_feature_planning_v1.yaml`, which
remains useful regression scaffolding but is not the canonical public `C3 v1`
authoring example. That internal fixture still declares the same
`planning_execution.mode: graph_owned` contract, but it keeps
`coverage_policy` and `phase_inputs` as runtime-owned fixture scaffolding.

The bounded provider-review variant is shown separately in
`examples/harness/public_subset/canonical/deterministic_feature_planning_planner_review_v1.yaml`
and the runnable internal example
`examples/harness/strategies/deterministic_feature_planning_planner_review_v1.yaml`.

Internal and private fixture-backed strategies are preserved; this milestone
does not relabel them as canonical public authoring.

## 11. Example taxonomy

Canonical public examples live under:

- `examples/harness/public_subset/canonical/`

Compatibility-only accepted input lives under:

- `examples/harness/public_subset/compatibility/`

Negative contract fixtures live under:

- `examples/harness/public_subset/negative/`

The negative fixtures document one-violation rejection cases for canonical
public authoring. They are not happy-path runnable examples.

## 12. Diagnostics and out-of-scope boundary

Invalid canonical public authoring is rejected during parsing and surfaced
through preflight as `invalid_config`, so the harness can stop before model
work starts.

This milestone does not:

- create a second parser or a public-only runtime target
- relabel compatibility-only or internal/private surfaces as canonical public
  authoring
- freeze a public task-spec contract
