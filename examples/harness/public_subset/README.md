# Public Strategy DSL Example Pack

This directory is the classified example pack for the live bounded public `C3`
strategy contract described in
[`docs/strategy_dsl_public_subset_contract.md`](../../../docs/strategy_dsl_public_subset_contract.md).

## Taxonomy

- `canonical/`: the recommended public `C3 v1` authoring examples accepted by
  the parser-owned public boundary
- `compatibility/`: accepted legacy input that remains non-canonical and emits
  an explicit warning path in preflight
- `negative/`: one-violation contract fixtures for canonical public rejection
  cases

The existing runnable strategy
`examples/harness/strategies/deterministic_feature_planning_v1.yaml` stays in
place for regression coverage, but it is internal and fixture-backed rather
than the canonical public planning example.

## Canonical examples

- `canonical/analysis_review_bounded_v1.yaml`: canonical bounded analysis-review
  example
- `canonical/analysis_review_trust_v1.yaml`: canonical trust analysis-review
  example
- `canonical/deterministic_feature_planning_v1.yaml`: canonical planning example
  with `runtime_target: planning_v1`,
  `planning_execution.mode: graph_owned`, and the required planning policy refs
- `canonical/deterministic_feature_planning_planner_review_v1.yaml`: canonical
  planning example with bounded provider-backed review layered on top of the
  same deterministic first-pass structure contract; review may emit expansion
  delta but may not replace canonical seams, workstreams, or slices

## Compatibility-only example

- `compatibility/analysis_review_v1.yaml`: accepted legacy input only; do not
  use this as the recommended starting point for new public `C3 v1` examples

## Negative examples

- `negative/invalid_kind.yaml`: uses a strategy kind outside the frozen public
  and compatibility sets
- `negative/unknown_top_level_key.yaml`: adds one unsupported top-level
  strategy key
- `negative/invalid_stage_family.yaml`: uses one stage family name outside the
  frozen public stage-family set
- `negative/runtime_owned_phase_inputs.yaml`: adds runtime-owned
  `phase_inputs` to a public planning example
- `negative/metadata_only_schema_version.yaml`: adds metadata-only
  `schema_version` as if it were a public authoring field
- `negative/planning_roles_over_signal.yaml`: reintroduces `roles.planner`
  while staying in deterministic-only `planning_execution.mode: graph_owned`
- `negative/planning_provider_review_missing_role.yaml`: selects planner-review
  mode without declaring `roles.planner.provider`

These negative files document the live rejection surface for canonical public
authoring. They are not runnable happy-path harness examples.
