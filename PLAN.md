# PLAN: B1 Harness Seam Extraction for the State-Graph Strangler

Status: ready for implementation
Branch: `main`
Milestone: `B1`
Design source: `/Users/spensermcconnell/.gstack/projects/Spenquatch-forge/spensermcconnell-main-design-20260513-215858.md`
Supersedes:
- none
- this is the active implementation plan for B1 on `main`

## Plan Summary

B1 is the seam-extraction milestone for the harness strangler migration.

It does **not** move `analysis_review` topology into real graph-owned execution
yet. It makes the codebase honest about where topology, stage semantics, state
projection, selection, validation, and artifact publication live today, and it
creates the exact seams B2 will consume later.

Right now the LangGraph harness surface is mostly a shell:

- `anvil/harness/builder.py` routes into `analysis_review_v1_subgraph(...)`
- `anvil/harness/subgraphs/analysis_review_v1.py` immediately delegates to
  `anvil/harness/subgraphs/_bridge.py`
- `_bridge.py` instantiates `HarnessRunner.run()`
- the graph then reconstructs state from summary-shaped output through
  `state_from_summary(...)`
- `anvil/harness/nodes/write_artifacts.py` repeats that same pattern after
  `apply_final_artifacts(...)`

That means the graph exists, but topology truth and most product semantics still
live inside `anvil/harness/runner.py`, while the graph crosses the boundary by
round-tripping through summary artifacts as if that were neutral transport. It
is not neutral. B1 fixes the naming, ownership, and observability of that
reality without changing user-facing harness behavior.

The milestone question is simple:

**Which current files become permanent graph-era seams, and which current files
are temporary bridges that are not allowed to grow?**

This plan answers that explicitly and turns it into an implementable, testable
change contract.

## Success Criteria

- `StrategyGraphSpec` exists as an internal harness concept and can represent
  the approved bounded graph subset without implying arbitrary DAG support.
- `StageSpec` exists and names the current `analysis_review` topology in graph
  vocabulary, even though `HarnessRunner` still executes it.
- `HarnessState` becomes an explicit B1 state contract with
  `serialization_version`, contract ownership, graph metadata, focus/topic
  state, and sanctioned summary-boundary helpers.
- `summary_read_adapter_v1(...)` becomes the only sanctioned summary-to-state
  compatibility boundary.
- `summary_projection_v1(...)` becomes the only sanctioned state-to-summary
  compatibility boundary.
- `state_from_summary(...)` remains only as a backwards-compatible wrapper
  around `summary_read_adapter_v1(...)` during B1, not as a second concept.
- `write_state_artifacts(...)` remains only as the public artifact-writing entry
  point and delegates into `summary_projection_v1(...)`.
- `anvil/harness/subgraphs/_bridge.py` and
  `anvil/harness/nodes/write_artifacts.py` are clearly marked as temporary
  bridge/projection boundaries and do not gain new semantics.
- `anvil/harness/runner.py` remains the only topology truth for B1 execution.
- B1 adds the observability B2 parity work will need without changing final
  artifacts, validator behavior, or review semantics.
- Existing canonical harness tests remain green.
- New seam and boundary tests prevent silent growth of bridge code.

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | B1 decision |
|---|---|---|
| Parent graph exists but does not own strategy topology | `anvil/harness/builder.py` wires `prepare_run -> validator_preflight -> select_strategy -> analysis_review_v1 -> select_best_draft -> write_artifacts -> finalize`, while `anvil/harness/nodes/select_strategy.py` is a no-op | Keep the parent graph. Make strategy selection emit explicit graph vocabulary instead of pretending routing is already modeled. |
| `analysis_review` subgraph is only a bridge | `anvil/harness/subgraphs/analysis_review_v1.py` immediately calls `run_harness_runner(...)` from `anvil/harness/subgraphs/_bridge.py` | Keep this as the sanctioned temporary bridge in B1. Do not add product logic here. |
| State is reconstructed from summary output | `anvil/harness/state.py` exposes `stage_records_from_summary(...)` and `state_from_summary(...)` | Promote this into an explicit compatibility seam named `summary_read_adapter_v1(...)`. Keep `state_from_summary(...)` only as a compatibility wrapper during B1. |
| Artifact writing also round-trips through summary output | `anvil/harness/nodes/write_artifacts.py` calls `apply_final_artifacts(...)` and then `state_from_summary(...)`; `anvil/harness/reporting.py` exposes `write_state_artifacts(...)` | Promote the write side into explicit `summary_projection_v1(...)` ownership. Keep `write_state_artifacts(...)` as the public entry point that delegates to the explicit projection seam. |
| Contract resolution already exists as real product logic | `anvil/harness/contracts.py` exposes `build_analysis_review_contract(...)` and `AnalysisReviewContract` | Treat this module as the `ContractResolver` seam in B1. Reuse it instead of inventing a second policy layer. |
| Validator behavior already exists as real product logic | `anvil/harness/validation.py` exposes `preflight_validators(...)` and `run_validators(...)` | Keep validators as an adjacent orchestration seam, not graph stages, through B1-B3. |
| Draft projection and selection already exist as real semantics | `anvil/harness/selection.py` exposes `extract_drafts_from_summary(...)` and `select_best_draft(...)` | Keep this as the canonical selection seam. Do not rewrite ranking in B1. |
| Artifact/report shaping already exists as real semantics | `anvil/harness/reporting.py` owns `apply_final_artifacts(...)`, `write_state_artifacts(...)`, and report rendering flow | Keep this as the artifact seam. Make the boundary explicit, not a hidden side effect. |
| Stage execution and semantic normalization are still fused into the runner | `HarnessRunner._run_agent_stage(...)` in `anvil/harness/runner.py` handles provider invocation, normalization, schema validation, semantic validation, and stage recording | Leave execution truth in the runner for B1. Do not split it twice. Only extract ownership and observability seams now. |
| B2 parity corpus already exists | `tests/test_run_focus_gate_acceptance.py`, `tests/test_harness_prompt_consistency.py`, `tests/test_harness_reporting.py`, `tests/test_harness_example_strategy_wiring.py`, `tests/test_lg_offline_smoke.py`, and `tests/test_harness_selection.py` | Reuse these as the parity oracle floor. B1 adds seam/boundary coverage, not a fake parity rewrite. |

### Minimum complete scope

This is the minimum complete B1 slice. If any item is skipped, the milestone
stays fuzzy and B2 will drift.

1. `PLAN.md`
2. `anvil/harness/strategy_graph.py`
3. `anvil/harness/state.py`
4. `anvil/harness/builder.py`
5. `anvil/harness/nodes/select_strategy.py`
6. `anvil/harness/subgraphs/_bridge.py`
7. `anvil/harness/nodes/write_artifacts.py`
8. `anvil/harness/reporting.py`
9. `anvil/harness/runner.py`
10. `anvil/harness/contracts.py`
11. targeted seam/boundary regression tests under `tests/`
12. observability assertions added to existing harness runner/reporting surfaces

### Complexity verdict

This milestone touches more than 8 files. That normally smells.

Here it is justified because the problem is split ownership, not one isolated
bug. B1 is the point where the codebase stops pretending the graph is already in
charge and starts naming the real seams.

What would be overbuilt:

- a generalized graph compiler
- a public DAG or YAML graph surface
- converting validators into first-class stages
- deleting the runner path during the seam milestone
- versioning the artifact contract in the same slice
- extracting a broad `StageRegistry` or custom-stage system in B1

### Search/build verdict

This is a Layer 1 reuse milestone, not a framework milestone.

Reuse what already exists:

- `contracts.py` as `ContractResolver`
- `validation.py` as validator orchestration
- `selection.py` as draft projection/selection
- `reporting.py` as artifact publication
- `runner.py` as the B1 execution truth
- the existing parity corpus as the future oracle

Do **not** invent:

- a second harness beside the current one
- a second artifact pipeline
- graph-only semantics duplicated outside the runner
- a public configuration promise the runtime cannot honor yet

### TODOS cross-reference

`docs/project_management/future/TODOS.md` contains future product and auditability
follow-ups, but nothing there blocks B1.

Do not bundle those items into this milestone unless implementation uncovers a
hard blocker for explicit seam extraction. New B2/B3 follow-up work discovered
during B1 should be captured after B1 lands, not smuggled into this PR.

### Completeness verdict

The shortcut is "add a graph-spec file and call it progress." That does not
solve the problem.

The complete B1 version must do all of this together:

- define the graph-era vocabulary
- classify permanent seams versus temporary bridges
- make the summary read/write boundaries explicit
- preserve current behavior
- add the observability B2 needs
- lock regression tests around the bridge boundaries

### Distribution and DX verdict

Forge is a developer tool. B1 is incomplete if it makes the internal
architecture cleaner while making the harness surface harder to understand or
less testable.

That means B1 must preserve:

- `python -m anvil.harness.cli run ...`
- `HarnessLangGraphExecutor`
- checkpoint mode behavior
- current examples and acceptance fixtures

No new user-facing config surface ships in B1.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Milestone scope | B1 is seam extraction only | Topology migration belongs to B2. |
| Topology truth in B1 | `HarnessRunner` remains the execution truth | Do not move topology and semantics in the same slice. |
| Validator positioning | validators stay adjacent orchestration, not graph stages | This is explicit in the design and avoids fake generality. |
| Summary read boundary | `summary_read_adapter_v1(...)` is the only sanctioned summary-to-state path | The current implicit helper needs a real name and ownership. |
| Legacy read helper | `state_from_summary(...)` becomes a compatibility wrapper that forwards into `summary_read_adapter_v1(...)` | This keeps the diff small while collapsing to one real concept. |
| Summary write boundary | `summary_projection_v1(...)` is the only sanctioned state-to-summary path | B1 must make this boundary honest before B2 relies on it. |
| Legacy write helper | `write_state_artifacts(...)` stays public but delegates through `summary_projection_v1(...)` | Existing callers stay stable while the seam becomes explicit. |
| Artifact contract | no version bump in B1 | Seam extraction should not change the external surface. |
| Graph subset | linear flows, bounded single back-edge loops, conditional branching only | No arbitrary DAG promise. |
| New semantics in bridges | forbidden | Temporary bridge code must shrink, not attract new truth. |
| Stage semantics extraction | only extract what B1 needs to name and observe | Full registry generalization is explicitly deferred out of B1. |
| Selection truth | keep `selection.py` canonical | Ranking is product behavior, not cleanup glue. |
| Reporting truth | keep `reporting.py` canonical | Publication authority already lives there. |
| Observability shape | preserve existing top-level stage record fields; add new seam metadata under `StageRecord.metadata` unless a matching field already exists | Minimal diff, explicit ownership, no second telemetry model. |
| Rollout | keep legacy runner path as the default execution mode | B2 needs a safe fallback. |

## Architecture Review

### B1 source-of-truth table

| Concern | Canonical owner in B1 | Notes |
|---|---|---|
| Topology truth | `anvil/harness/runner.py` | The runner still decides stage order and loop behavior. |
| Graph vocabulary | new `anvil/harness/strategy_graph.py` | Internal declaration only. No public DAG claim. |
| Strategy-to-graph resolution | `anvil/harness/nodes/select_strategy.py` | Must stop being a no-op and stamp graph metadata into state. |
| Stage semantics truth | existing seam modules behind runner calls | `contracts.py`, `semantic_validation.py`, `validation.py`, `selection.py`, `reporting.py` |
| State truth | `HarnessState` plus `summary_read_adapter_v1(...)`/`summary_projection_v1(...)` | Explicit compatibility boundary, not hidden transport. |
| Selection truth | `anvil/harness/selection.py` | Draft projection and best-draft ranking stay canonical. |
| Artifact truth | `anvil/harness/reporting.py` | External artifact surface stays stable. |
| Direct legacy re-entry | `anvil/harness/subgraphs/_bridge.py` | Temporary bridge only. |

### Permanent seams vs temporary bridges

| Module / surface | Classification in B1 | Why |
|---|---|---|
| `anvil/harness/contracts.py` | permanent seam | Contract resolution is already stable product logic. |
| `anvil/harness/semantic_validation.py` | permanent seam | Semantic validation is real behavior, not bridge glue. |
| `anvil/harness/validation.py` | permanent seam | Validator applicability and execution are first-class semantics. |
| `anvil/harness/selection.py` | permanent seam | Draft extraction and ranking are product semantics. |
| `anvil/harness/reporting.py` | permanent seam with explicit compatibility boundary | Artifact publication stays here; summary projection must be named. |
| `anvil/harness/state.py` | permanent seam | Graph-era state and boundary adapters belong here. |
| new `anvil/harness/strategy_graph.py` | permanent seam | B1 needs one internal topology vocabulary. |
| `anvil/harness/runner.py::_run_agent_stage(...)` | legacy implementation behind a future permanent seam | Worth preserving, but do not fully extract in B1. |
| `anvil/harness/runner.py` strategy-specific flow methods | temporary bridge / legacy implementation | Current topology truth lives here and must shrink in B2. |
| `anvil/harness/builder.py` routing shell | temporary bridge | Parent graph exists, but it still routes into legacy execution. |
| `anvil/harness/subgraphs/_bridge.py` | temporary bridge | Explicit legacy re-entry seam. No new semantics allowed. |
| `anvil/harness/subgraphs/analysis_review_v1.py` | temporary bridge wrapper | Thin wrapper only until B2. |
| `anvil/harness/nodes/write_artifacts.py` summary rehydration path | temporary bridge until B3 | Current artifact flow still round-trips through summary state. |
| `examples/harness/*` and acceptance fixtures | stable contract surface | Must remain valid while internals shift. |
| harness parity tests under `tests/` | stable oracle | Migration is judged against these surfaces. |

### Current-to-B1 dependency graph

```text
CURRENT
=======
prepare_run
  -> validator_preflight
  -> select_strategy (no-op)
  -> analysis_review_v1_subgraph
       -> _bridge.run_harness_runner
            -> HarnessRunner.run()
            -> summary payload
            -> state_from_summary(...)
  -> select_best_draft
  -> write_artifacts_node
       -> apply_final_artifacts(...)
       -> state_from_summary(...)
  -> finalize


B1 TARGET
=========
prepare_run
  -> validator_preflight
  -> select_strategy
       -> resolve contract ownership
       -> build StrategyGraphSpec
       -> emit StageSpec identities
       -> stamp strategy_graph_spec_id / subset / boundary versions
  -> analysis_review_v1_subgraph
       -> LegacyBridgeBoundary.run(...)
            -> HarnessRunner.run()
       -> summary_read_adapter_v1(...)
  -> select_best_draft
  -> write_artifacts_node
       -> summary_projection_v1(...)
       -> apply_final_artifacts(...)
       -> summary_read_adapter_v1(...)
  -> finalize
```

### File change contract

This is the core anti-ambiguity section. Each file has an explicit change budget.

| File | Allowed change in B1 | Forbidden change in B1 |
|---|---|---|
| `anvil/harness/strategy_graph.py` | Define internal `StrategyGraphSpec`, `StageSpec`, bounded-subset constants, and the spec builder for existing strategy kinds | No public config parser, no DAG compiler, no execution runtime |
| `anvil/harness/nodes/select_strategy.py` | Resolve the internal spec, stamp graph metadata into state, and remain side-effect free | No execution routing, no validator logic, no artifact shaping |
| `anvil/harness/builder.py` | Continue routing exactly as today while preserving the new strategy metadata through the graph | No topology generalization driven from spec |
| `anvil/harness/state.py` | Add B1 state fields and the explicit summary read boundary; keep `state_from_summary(...)` as a wrapper only | No new product semantics, no second projection layer |
| `anvil/harness/reporting.py` | Add `summary_projection_v1(...)`, keep `apply_final_artifacts(...)` canonical, make `write_state_artifacts(...)` delegate through the projection seam | No contract version bump, no new publication semantics |
| `anvil/harness/subgraphs/_bridge.py` | Rename the seam in code/comments to an explicit legacy bridge boundary and call `summary_read_adapter_v1(...)` | No new policy, selection, or validation rules |
| `anvil/harness/nodes/write_artifacts.py` | Route through explicit projection/read boundaries and keep orchestration thin | No publication policy, no ranking logic, no artifact contract changes |
| `anvil/harness/contracts.py` | Add seam-naming helper such as `resolve_analysis_review_contract(...)` while keeping `build_analysis_review_contract(...)` stable | No duplicate contract model |
| `anvil/harness/runner.py` | Preserve execution truth; add explicit seam metadata to stage records and boundary output | No topology migration, no validator-as-stage rewrite |
| `tests/*` | Add direct regression coverage for graph vocabulary, state boundaries, runner observability, and artifact parity | No fake green tests that only assert helper existence |

### Architecture constraints

- `select_strategy_node` must stop being a no-op. It must emit explicit internal
  topology metadata for the chosen strategy.
- The graph-spec layer may describe only the bounded subset already approved in
  the design doc.
- `subgraphs/_bridge.py` may adapt request/state into `HarnessRunner`, but it
  may not introduce policy, routing, selection, or publication semantics.
- `nodes/write_artifacts.py` may orchestrate the boundary, but publication
  authority remains in `reporting.py`.
- `runner.py` remains the only place allowed to define actual stage ordering and
  loop control in B1.
- Any new field crossing the summary boundary must be optional or derivable from
  the existing artifact contract.
- B1 may add observability, but not new user-visible harness semantics.

## Code Quality Review

### Guardrail rules

1. No new semantics in bridge code.
2. No duplicate topology truth outside `runner.py` in B1.
3. No artifact-contract decisions outside `reporting.py`.
4. No validator applicability rules outside `validation.py`.
5. No second ranking implementation outside `selection.py`.
6. No public DAG language, schema, or config keys in B1.
7. No broad `StageRegistry` abstraction in B1.
8. No field crosses the summary boundary invisibly.

### DRY rules

- Do not define executable stage ordering in both `StrategyGraphSpec` and graph
  routing logic. In B1, the spec is declarative vocabulary; execution still
  belongs to the runner.
- Do not keep both `state_from_summary(...)` and `summary_read_adapter_v1(...)`
  as parallel concepts. The former must forward to the latter.
- Do not keep both `write_state_artifacts(...)` and a second summary builder as
  separate truth. `write_state_artifacts(...)` must delegate through
  `summary_projection_v1(...)`.
- Do not add a second contract resolver when `build_analysis_review_contract(...)`
  already exists.

### Naming and structure rules

- `StrategyGraphSpec` means declared topology, not executable graph runtime.
- `StageSpec` means declared stage identity and capabilities, not provider run
  output.
- `summary_read_adapter_v1` means legacy summary -> graph-state compatibility.
- `summary_projection_v1` means graph-state -> stable summary/report projection.
- `LegacyBridgeBoundary` means direct re-entry into runner-owned execution.

### Explicit-over-clever rules

- Prefer one small new vocabulary module over a premature compiler package.
- Prefer explicit boundary functions over hidden helper chains.
- Prefer clear dataclasses or `TypedDict` additions over meta-factories.
- Prefer comments and tests that label bridge ownership over a broad refactor
  that hides the same truth under more files.

## Test Review

B1 is a seam milestone. Coverage here means boundary coverage, ownership
coverage, and observability coverage, not just happy-path execution.

### Existing regression floor

These are the non-negotiable regression floor. B1 must not break them.

- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_selection.py`
- `tests/test_lg_offline_smoke.py`

### Required new and expanded tests

| Test file | Required assertions |
|---|---|
| new `tests/test_harness_strategy_graph.py` | `StrategyGraphSpec` can represent the current `analysis_review` loop, rejects unsupported arbitrary-DAG shapes, and `select_strategy_node` emits `strategy_graph_spec`, `strategy_graph_spec_id`, and `strategy_graph_subset` for existing strategy kinds |
| new `tests/test_harness_state_boundaries.py` | `summary_read_adapter_v1(...)` preserves run identity, selected draft, focus decision, contract payload, topic ledger, and issue/stage history; `state_from_summary(...)` is just a compatibility wrapper; `summary_projection_v1(...)` emits the stable summary/report surface without silently depending on non-contract fields |
| expand `tests/test_harness_reporting.py` | artifact-writing path still yields the same externally visible summary, deliverable choice, artifact keys, and report content after the boundary is made explicit |
| expand `tests/test_harness_runner.py` | analysis-review stage records carry the new seam metadata under `metadata`, and runner topology/order remains unchanged |
| expand `tests/test_harness_example_strategy_wiring.py` | existing strategy fixtures still resolve the same effective contract while the graph metadata is added |

### Coverage diagram

```text
CODE PATH COVERAGE
===========================
[+] strategy selection
    ├── [GAP]  select_strategy_node is currently a no-op
    ├── [PLAN] build StrategyGraphSpec and stamp StageSpec metadata
    └── [TEST] tests/test_harness_strategy_graph.py

[+] legacy execution bridge
    ├── [GAP]  _bridge.py silently re-enters HarnessRunner and silently rehydrates state
    ├── [PLAN] route through LegacyBridgeBoundary + summary_read_adapter_v1
    └── [TEST] tests/test_harness_state_boundaries.py

[+] artifact projection boundary
    ├── [GAP]  write_artifacts_node currently applies artifacts then rehydrates state without named ownership
    ├── [PLAN] route through summary_projection_v1 + apply_final_artifacts + summary_read_adapter_v1
    └── [TEST] tests/test_harness_reporting.py

[+] runner seam ownership
    ├── [GAP]  topology truth and stage semantics are mixed but unlabeled
    ├── [PLAN] preserve runner truth and add explicit seam metadata
    └── [TEST] tests/test_harness_runner.py

[+] regression floor
    ├── [PLAN] keep focus-gate, reporting, prompt consistency, selection, example wiring, and offline smoke tests green
    └── [TEST] existing canonical corpus
```

### Validation commands

Run these commands before calling B1 done:

```bash
poetry run pytest -q \
  tests/test_harness_strategy_graph.py \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
  tests/test_harness_selection.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_run_focus_gate_acceptance.py

poetry run pytest -q tests/test_lg_offline_smoke.py

poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

Expected result:

- all targeted tests pass
- the harness CLI help path still works
- the existing Forge CLI still lists commands successfully

### Done criteria for test coverage

This plan is not complete until all of these are true:

1. the strategy-graph vocabulary has direct tests
2. the summary read/write boundaries have direct tests
3. the runner observability additions have direct tests
4. the existing harness contract/reporting corpus still passes
5. no B1 change depends on an untested implicit summary field

## Performance and Reversibility Review

The main risk in B1 is architecture drag, not runtime latency.

### Risks to avoid

- extracting a fancy topology language before the current graph can even name
  the existing loop honestly
- letting bridge files accumulate new policy because they are "already there"
- changing artifact structure and seam ownership in the same slice
- deleting the runner path before B2 parity exists
- over-generalizing stage capabilities in B1 and creating dead abstractions

### Boring implementation sequence

1. define vocabulary and ownership first
2. make the summary boundaries explicit second
3. add runner observability third
4. add seam tests fourth
5. leave actual graph-owned topology migration for B2

That order keeps the blast radius readable and reversible.

## Detailed Implementation Plan

### Phase 1: Introduce graph vocabulary without claiming graph-owned execution

Goal: create the internal declaration layer B2 will consume later.

Files touched:

- `anvil/harness/strategy_graph.py` (new)
- `anvil/harness/builder.py`
- `anvil/harness/nodes/select_strategy.py`

Required changes:

1. Add `StrategyGraphSpec` with only the bounded subset approved by the design:
   - linear stages
   - bounded single back-edge loop metadata
   - conditional branch metadata
   - terminal outcome metadata
2. Add `StageSpec` with minimum viable fields:
   - `stage_id`
   - `archetype`
   - `provider_role`
   - `capabilities`
   - `prompt_builder_key`
   - `schema_key`
3. Add one explicit builder in `strategy_graph.py` for current strategy kinds.
   The builder must cover:
   - `single_pass`
   - `pfr_v1`
   - `analysis_review_*`
4. Update `select_strategy_node` so it resolves the chosen internal spec and
   records it in state under these exact keys:
   - `strategy_graph_spec`
   - `strategy_graph_spec_id`
   - `strategy_graph_subset`
5. When graph metadata needs contract context, read it from the canonical
   contract seam. Do not recalculate policy rules inside the node.
6. Keep executable routing behavior unchanged. B1 names topology; it does not
   execute from spec yet.

Forbidden changes:

- no executable graph compiler
- no public config surface
- no routing decisions derived from spec at runtime

Exit criteria:

- `select_strategy_node` is no longer a no-op
- the chosen strategy has an explicit internal graph spec in state
- no new public config surface exists

### Phase 2: Make state and compatibility boundaries explicit

Goal: stop treating summary round-tripping as an unnamed helper chain.

Files touched:

- `anvil/harness/state.py`
- `anvil/harness/reporting.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/nodes/write_artifacts.py`

Required changes:

1. Extend `HarnessState` for B1 with explicit migration fields:
   - `serialization_version`
   - `analysis_review_contract`
   - `strategy_graph_spec`
   - `strategy_graph_spec_id`
   - `strategy_graph_subset`
   - `focus_decision`
   - `topic_ledger`
   - `summary_boundary_version`
   - `bridge_boundary_version`
2. Add `summary_read_adapter_v1(...)` in `state.py`.
3. Convert `state_from_summary(...)` into a compatibility wrapper that forwards
   to `summary_read_adapter_v1(...)` so existing callers stay stable while the
   real seam name becomes explicit.
4. Add `summary_projection_v1(...)` in `anvil/harness/reporting.py`.
5. Make `write_state_artifacts(...)` delegate through `summary_projection_v1(...)`
   instead of acting like a second unnamed summary builder.
6. Rewire `_bridge.py` to call the explicit read boundary.
7. Rewire `write_artifacts_node` to use this exact order:
   - project summary through `summary_projection_v1(...)`
   - finalize artifacts through `apply_final_artifacts(...)`
   - rehydrate graph-adjacent state through `summary_read_adapter_v1(...)`
8. Add short comments at the boundary call sites stating that no new semantics
   may land there.

Forbidden changes:

- no artifact contract changes
- no second summary builder
- no direct business logic added inside `_bridge.py` or `write_artifacts_node`

Exit criteria:

- there is exactly one sanctioned summary->state path
- there is exactly one sanctioned state->summary path
- bridge files are labeled and testable as compatibility seams

### Phase 3: Freeze runner ownership and add observability

Goal: preserve current execution truth while making its ownership visible.

Files touched:

- `anvil/harness/runner.py`
- `anvil/harness/contracts.py`

Required changes:

1. Route contract resolution through an explicit helper naming the seam:
   - add `resolve_analysis_review_contract(...)` in `anvil/harness/contracts.py`
   - keep `build_analysis_review_contract(...)` as the stable public builder
2. Keep validators adjacent to the runner/graph orchestration path. Do not
   model them as stages.
3. Preserve `_run_agent_stage(...)` in the runner, but add the metadata B2 will
   need.
   Add these keys under `StageRecord.metadata` unless an existing typed field
   already carries the value:
   - `graph_stage_id`
   - `transition_reason`
   - `boundary_source`
   - `semantic_validation_path` when a separate artifact exists
4. Reuse existing path fields such as `normalized_json_path` instead of creating
   parallel observability fields for the same artifact.
5. Ensure the runner remains the only executable topology truth for
   `analysis_review` in B1.
6. Do not change stage-ordering behavior, loop policy, validator scheduling, or
   publication outcomes.

Forbidden changes:

- no stage registry rollout
- no topology migration into the graph
- no validator behavior change

Exit criteria:

- runner ownership is explicit
- no new product semantics were introduced outside canonical seam modules
- observability is richer without changing artifacts

### Phase 4: Add seam and boundary regression coverage

Goal: prove the boundaries are explicit and stable enough for B2.

Files touched:

- `tests/test_harness_strategy_graph.py` (new)
- `tests/test_harness_state_boundaries.py` (new)
- `tests/test_harness_reporting.py`
- `tests/test_harness_runner.py`

Required changes:

1. Add direct tests for graph-spec construction and bounded-subset guarantees.
2. Add direct tests for summary read/write boundary behavior.
3. Add reporting-path regression assertions proving the same external artifact
   surface still emerges after the explicit boundary extraction.
4. Add runner assertions proving the new seam metadata is emitted without
   changing stage order or verdict behavior.
5. Keep the canonical parity floor green, including
   `tests/test_lg_offline_smoke.py` as a required validation command even if it
   does not need file edits.

Exit criteria:

- the new boundaries have direct regression tests
- the runner observability additions have direct regression tests
- the old public behavior still passes its current corpus

## Failure Modes Registry

| Failure mode | Covered by test | Error handling | User-visible impact | Plan response |
|---|---|---|---|---|
| Bridge files gain new semantics because they are convenient | `tests/test_harness_state_boundaries.py` and review comments at bridge call sites | failing regression tests + code review guardrails | B2 inherits dual truth and parity becomes fake | boundary comments + explicit tests + file change contract |
| `StrategyGraphSpec` overclaims support for arbitrary DAGs | `tests/test_harness_strategy_graph.py` | design-time validation failure | future work is built on a dishonest contract | keep bounded subset explicit and enforced |
| Summary read boundary silently drops state needed for B2 | `tests/test_harness_state_boundaries.py` | failing adapter tests | parity work later loses focus, topic, contract, or draft truth | explicit adapters + state contract extensions |
| Summary write boundary leaks non-contract fields into published artifacts | `tests/test_harness_reporting.py` | regression test failure | downstream tools start depending on accidental fields | explicit projection seam + contract-preserving assertions |
| Runner observability stays too thin for parity diffs | `tests/test_harness_runner.py` and targeted reporting assertions | failing tests | B2 cannot explain mismatches or rollback triggers | add stage/transition metadata in B1 |
| Validators accidentally drift into graph-stage semantics | existing validator tests + code review guardrails | failing tests or review rejection | execution semantics split across two models | keep validator orchestration adjacent and explicit |
| B1 changes artifacts or publication behavior by accident | `tests/test_harness_reporting.py` and existing harness corpus | regression test failure | users see artifact drift before parity is even attempted | artifact contract stays stable in B1 |

Critical gap definition for B1:

Any bridge or boundary change that is untested **and** can silently redefine
state, topology truth, or artifact truth is a critical gap.

This plan closes those gaps with one explicit ownership map plus direct boundary
tests.

## NOT in Scope

- graph-owned `analysis_review` execution
- public DAG or YAML graph configuration
- arbitrary fork/join or parallel stage execution as a product feature
- full `StageRegistry` generalization
- converting validators into ordinary graph stages
- artifact contract version bumps
- deleting legacy summary rehydration entirely
- deleting the runner path
- new trust/bounded product semantics
- example or docs redesign outside what is required to keep current surfaces honest

## Worktree Parallelization Strategy

Parallelization exists, but only after the milestone is decomposed by module
ownership instead of by file count.

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Graph vocabulary and strategy selection | `anvil/harness/strategy_graph.py`, `anvil/harness/builder.py`, `anvil/harness/nodes/` | — |
| B. Runner seam ownership and observability | `anvil/harness/runner.py`, `anvil/harness/contracts.py` | — |
| C. State and summary-boundary extraction | `anvil/harness/state.py`, `anvil/harness/reporting.py`, `anvil/harness/subgraphs/`, `anvil/harness/nodes/` | A, B |
| D. Regression coverage and acceptance | `tests/` | A, B, C |

### Parallel lanes

- Lane A: graph vocabulary and selection plumbing
  - internal `StrategyGraphSpec`
  - `StageSpec`
  - `select_strategy_node`
  - parent graph metadata wiring
- Lane B: runner seam ownership and observability
  - contract seam naming
  - stage trace and transition metadata
  - preserve validator and selection ownership exactly as-is
- Lane C: state and boundary extraction
  - `summary_read_adapter_v1`
  - `summary_projection_v1`
  - bridge node rewiring
- Lane D: tests and acceptance
  - seam tests
  - boundary tests
  - runner observability assertions
  - reporting regressions
  - canonical corpus run

### Execution order

Launch Lane A and Lane B in parallel worktrees.

After both land, run Lane C.

After Lane C lands, run Lane D.

Do not start any B2 topology work until Lane D is green.

### Conflict flags

- Lanes A and C both touch `anvil/harness/nodes/`. Keep C behind A.
- Lanes B and C both influence the state/observability contract. C must wait for
  B's field names and metadata shape to settle.
- Lane D depends on the final public interface of A, B, and C. Run it last.

### Merge gates

- Merge gate after Lane A: `select_strategy_node` emits graph metadata and the
  graph still routes exactly as before.
- Merge gate after Lane B: runner stage records expose the new seam metadata and
  no topology or verdict behavior changes.
- Merge gate after Lane C: there is one sanctioned read boundary and one
  sanctioned write boundary.
- Merge gate after Lane D: all targeted tests and CLI smoke commands are green.

## Acceptance Checklist

- [ ] `StrategyGraphSpec` exists and represents the approved bounded subset only
- [ ] `StageSpec` exists for current harness strategy families
- [ ] `select_strategy_node` emits explicit strategy graph metadata
- [ ] `HarnessState` carries `serialization_version` and the B1 state fields
  required for seam ownership and B2 parity setup
- [ ] `summary_read_adapter_v1(...)` is the only sanctioned summary->state path
- [ ] `state_from_summary(...)` is only a compatibility wrapper around
  `summary_read_adapter_v1(...)`
- [ ] `summary_projection_v1(...)` is the only sanctioned state->summary path
- [ ] `write_state_artifacts(...)` delegates through `summary_projection_v1(...)`
- [ ] `_bridge.py` is explicitly bridge-only and does not gain new semantics
- [ ] `write_artifacts_node` is explicitly projection-only and does not gain new
  publication semantics
- [ ] `runner.py` remains the only topology truth for B1 execution
- [ ] existing harness reporting/prompt/acceptance/example/selection tests remain green
- [ ] new seam, boundary, and runner-observability tests are added and green
- [ ] harness CLI help still works
- [ ] existing Forge CLI still works

## Completion Summary

- Step 0: Scope Challenge — scope accepted as seam extraction only, with no
  graph-owned topology migration in B1
- Architecture Review: one explicit ownership map for permanent seams versus
  temporary bridges, plus a file-level change contract
- Code Quality Review: bridge files frozen, DRY truth boundaries locked, no new
  semantics outside canonical seam modules
- Test Review: direct graph-spec, state-boundary, runner-observability, and
  artifact-projection coverage added on top of the existing harness corpus
- Performance Review: boring, reversible sequencing chosen over speculative
  framework work
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none required to start B1
- Failure modes: critical architecture gaps closed by explicit boundaries and
  direct regression tests
- Parallelization: 4 steps total, 2 initial parallel lanes, 2 sequential
  follow-ons, explicit merge gates
- Lake Score: choose the complete seam milestone, not the fake-compiler
  shortcut
