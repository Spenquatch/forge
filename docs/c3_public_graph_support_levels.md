# C3 Public Graph Support Levels

This document translates the `C2.9` public-subset contract into current support
levels.

It answers a practical question:

What parts of the intended public graph workflow builder are real today, and
what parts are only documented, parser-enforced, runtime-routed, or still
missing?

Primary references:

- [Strategy DSL Public Subset Contract](/home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md)
- [public_subset_registry.py](/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py)
- [public_subset_validation.py](/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_validation.py)
- [types.py](/home/azureuser/__Active_Code/forge/anvil/harness/types.py)
- [strategy_graph.py](/home/azureuser/__Active_Code/forge/anvil/harness/strategy_graph.py)
- [builder.py](/home/azureuser/__Active_Code/forge/anvil/harness/builder.py)
- [planning_v1.py](/home/azureuser/__Active_Code/forge/anvil/harness/subgraphs/planning_v1.py)

## Legend

| Level | Meaning |
|---|---|
| `Supported` | Documented, parser-enforced, and has meaningful runtime behavior today |
| `Partial` | Real in code, but only part of the intended product contract is implemented |
| `Parser-only` | Enforced at parse/preflight time, but not yet a user-composable runtime surface |
| `Runtime-only` | Exists as runtime/emitted behavior, but is not a user-declarable public surface |
| `Documented-only` | Named in the contract, but not actually exposed as a user-wirable surface yet |
| `Not supported` | Explicitly out of scope or still missing |

## Summary

The current repo has a real `C3` parser boundary and a real bounded public
authoring surface.

What it does not yet have is a full user-wirable graph workflow builder where
users can compose predefined nodes, edges, transitions, and role families into
new executable graphs.

The current state is best described as:

- public grammar: partially real
- analysis-review runtime execution: substantially real, including model-backed
  execution and a newer graph-owned path
- planning execution: real, graph-owned, and explicitly deterministic
- generic user graph composition: not real yet

## Support Matrix

| Surface | Current level | What is real today | What is still missing |
|---|---|---|---|
| `dsl_version: c3_strategy_v1` | `Supported` | Canonical public payloads must declare it, and validation rejects incorrect values | Nothing major at the parser boundary |
| Public surface classification | `Supported` | Raw payloads are classified as `canonical_public`, `compatibility_only`, or `internal_or_private` | Nothing major for the current contract |
| Canonical public kind registry | `Partial` | `analysis_review_bounded_v1`, `analysis_review_trust_v1`, and `deterministic_feature_planning_v1` are frozen in the public registry and validated | Analysis-review kinds already map into a shared real runtime family. Planning maps into one bounded runtime family with two explicit execution postures rather than a broader user-authored graph family |
| Compatibility-only `analysis_review_v1` | `Supported` | Accepted only without `dsl_version`, warned in preflight, and treated as legacy | Long-term migration/removal policy is still a product decision |
| Unknown top-level key rejection | `Supported` | Canonical public payloads reject unsupported top-level keys | Nothing major for the current parser-owned gate |
| Runtime-owned field exclusion | `Supported` | Canonical public payloads reject `coverage_policy` and `phase_inputs` | Nothing major for the current parser-owned gate |
| Metadata-only field exclusion | `Supported` | Canonical public payloads reject `schema_version` and `subset` | Nothing major for the current parser-owned gate |
| Public stage-family names | `Partial` | Canonical public roles are restricted to the bounded family list such as `solver`, `proposer`, `planner`, and `auditor` | Stage-family names are validated, but users are not yet wiring generic stage graphs out of these families |
| Stage-family to role-family bindings | `Documented-only` | The binding table is frozen in the registry and docs | There is no generic user-authored graph compiler that lets users compose stages and have those bindings drive execution as a first-class public mechanism |
| Public graph primitives | `Documented-only` | `stage`, `linear_edge`, `conditional_branch`, `bounded_loop`, `terminal_outcome`, and `planning_phase` are named in the contract | Users do not currently declare these primitives directly in canonical public config, except indirectly through planning phases |
| `planning_phase` primitive | `Partial` | Planning strategies do declare `phases[]`, and the parser enforces canonical phase order | This is only a fixed planning phase sequence, not a broader user-composable phase or node language |
| Public transition forms | `Documented-only` | `linear_next`, `enumerated_branch`, `bounded_loop_back_edge`, and `terminal_exit` are named in the contract | Users do not currently author transition graphs with these forms in public config |
| Public declaration unit: one full strategy spec | `Supported` | The public subset is framed around a whole strategy spec, not fragments or overlays | Imports, overlays, graph fragments, and extension mechanisms are still out of scope |
| Bounded analysis-review public kind | `Supported` | `analysis_review_bounded_v1` is a real public kind, parses cleanly, maps to `analysis_review_v1`, and runs through model-backed analysis-review stages | It still shares a bounded built-in runtime family rather than a user-composed public graph grammar |
| Trust analysis-review public kind | `Supported` | `analysis_review_trust_v1` is a real public kind, parses cleanly, maps to the same shared runtime family, and supports both trust execution modes through the unified contract | It still shares a bounded built-in runtime family rather than a user-composed public graph grammar |
| Analysis-review execution-mode flag | `Supported` | CLI/state wiring supports `--analysis-review-execution-mode legacy_bridge|graph_owned`, and `graph_owned` runs the newer native subgraph path | This execution-mode switch is not yet generalized as a public graph-builder composition control |
| Trust execution-mode knob | `Supported` | `trust_review.execution_mode` is a typed parsed input with real runtime consequences: `legacy_full_review` or `attestation_over_bounded` | It is a narrow trust-lane mode switch, not a general public execution-mode taxonomy for all graph families |
| Planning required policy refs | `Supported` | Planning strategies must declare the required planning policy refs, and parsing enforces that | Policy values are still string labels rather than a richer public registry with compatibility/version semantics |
| Planning execution contract | `Supported` | Canonical public planning declares either `planning_execution.mode: graph_owned` or `graph_owned_with_planner_review`; artifacts record the resulting execution contract, and the runtime consumes the compiled stage/phase spec through `strategy_graph_spec` | Planner review is still a bounded post-structure review layer, not a general planner-composition system |
| `runtime_target: planning_v1` | `Supported` | Planning strategies must declare it, and builder routing sends them to the planning runtime | `planning_v1` still means deterministic planning as the structural owner; provider-backed behavior is layered review, not provider-owned planning |
| Planning phase order | `Supported` | `rubric_design_doc -> architecture_seam_decomposition -> parallel_workstream_planning -> executable_slice_emission` is parser-enforced | Users cannot yet define alternative bounded planning graphs inside the public subset |
| Planning artifact shape | `Supported` | Planning runs emit real artifacts such as `PLAN.md`, `plan.json`, `phase_results`, and `coverage_ledger` | The artifacts come from a deterministic planner, not a user-composed graph workflow engine |
| Planning role declaration | `Supported` | Deterministic-only canonical planning omits `roles`, while planner-review mode requires exactly `roles.planner` with read-only provider access | The bounded planner role does not yet expand into arbitrary planning-stage families |
| Model-backed planning execution | `Supported` | Canonical public planning can opt into bounded planner review after deterministic structure derivation, and provider failures fail closed with explicit artifact truth | Provider-backed review cannot replace seams, workstreams, slices, coverage truth, or stop-reason ownership |
| Strategy graph spec emission | `Partial` | The runtime emits `strategy_graph_spec_v1`, `runtime_target`, `stages`, `phases`, `planning_execution`, `linear_edges`, and terminal outcomes | Planning now consumes the compiled phase/execution subset for real execution, but the broader graph inventory is still not a user-authored public graph grammar |
| `post_runtime_action` routing | `Runtime-only` | Builder routing does honor emitted `post_runtime_action` | Users do not declare it directly in the canonical public surface |
| `subset=bounded_strategy_graph_v1` | `Runtime-only` | Emitted as metadata on graph specs | It is descriptive metadata, not an enforceable public execution grammar |
| Broader built-in kinds `single_pass` and `pfr_v1` | `Partial` | They are real runnable built-ins and remain publicly visible | They are broader built-ins, not the same thing as the `C3` bounded graph DSL surface |
| Reusable bounded stage-sequence substrate | `Partial` | Planning and `single_pass` now both execute through the same compiled bounded stage substrate, and repo tests cover both families | This is a real reuse proof, not yet a full user-facing custom graph family |
| Generic user composition of predefined nodes and edges | `Not supported` | None in canonical public config | This is the main missing product surface if the goal is a true config-driven graph workflow builder |
| User-authored bounded loops and branches | `Not supported` | None in canonical public config | The contract names these forms, but users cannot yet wire them together into new public workflows |
| Public validator contract | `Not supported` | Validators exist in broader strategy config machinery | Canonical public `C3` authoring does not yet expose validators as part of the supported public subset |
| Public execution-mode story | `Partial` | Analysis-review already has two real axes: `analysis_review_execution_mode=legacy_bridge|graph_owned` plus trust `execution_mode=legacy_full_review|attestation_over_bounded` | There is not yet a clean execution-mode contract for the graph DSL as a whole, especially for planning and future user-authored graph families |

## What This Means

The strongest real claim the repo can make today is:

- Forge has a bounded public strategy-authoring contract.
- Forge validates a real `C3` public subset at the parser boundary.
- Analysis-review bounded and trust kinds route into a real model-backed runtime
  family, including a newer `graph_owned` path behind an execution-mode flag.
- Planning is a real supported kind with an explicit `planning_execution`
  contract, and today it resolves to deterministic structure ownership with an
  optional bounded provider-review layer.

The repo cannot yet honestly claim:

- users can wire together arbitrary supported graph workflows out of predefined
  nodes, edges, transitions, and role families
- public graph primitives are already a first-class user-authored execution
  grammar
- planner-provider declarations unlock arbitrary planning behavior
- users can yet treat the documented node/edge/transition vocabulary as a fully
  general public graph builder

## Biggest Remaining Gaps

If the intended product is a real config-driven graph workflow builder, the
largest missing pieces are:

1. A user-authored public graph grammar that actually consumes the documented
   node/edge/transition vocabulary.
2. A generic compiler/runtime path that executes those authored graph shapes
   using bounded existing families.
3. A truthful cross-family execution-mode contract beyond the current bounded
   planning and analysis-review families.
4. Provider-backed planning behavior if planner-provider stages are ever meant
   to re-enter the canonical public planning surface.

## Practical Reading Of C2.9

The best current reading of the `C2.9` packet is:

- it is the first serious support list for the public graph builder
- it freezes the intended bounded vocabulary
- it does not mean every item in that vocabulary is already implemented as a
  user-wirable runtime surface

That is why this support-levels doc exists.
