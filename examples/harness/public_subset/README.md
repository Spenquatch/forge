# Public Strategy DSL Example Pack

This directory is the classified example pack for the frozen `C2.9` public
subset contract described in
[`docs/strategy_dsl_public_subset_contract.md`](../../../docs/strategy_dsl_public_subset_contract.md).

## Taxonomy

- `canonical/`: the recommended public `C3 v1` authoring examples
- `compatibility/`: accepted legacy input that remains non-canonical
- `negative/`: one-violation contract fixtures for docs and future parser tests

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
  with `runtime_target: planning_v1` and the required planning policy refs

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

These negative files are documentation and future parser fixtures, not runnable
happy-path harness examples.
