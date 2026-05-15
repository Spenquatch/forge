# PLAN: B3 Graph-Native State / Selection / Artifact Canonicalization for the Harness Strangler

Status: ready for implementation after B2 parity lands on `main`  
Target branch: `main`  
Prepared from repo state on: `codex/b2-graph-owned-analysis-review-parity`  
Milestone: `B3`  
Design source: `/Users/spensermcconnell/.gstack/projects/Spenquatch-forge/spensermcconnell-main-design-20260513-215858.md`

Supersedes:
- the prior root `PLAN.md` B2 graph-owned parity plan
- the B3 milestone sketch inside the design doc

## Executive Summary

B3 ends fake state.

Today the harness graph owns most of the `analysis_review` topology, but the
success path still treats summary-shaped data as the durable source of truth in
three places:

1. `anvil/harness/subgraphs/analysis_review_v1.py` still reconstructs
   `drafts` by calling
   `extract_drafts_from_summary(_draft_summary_from_runner(runner))`.
2. `anvil/harness/nodes/write_artifacts.py` still performs the round-trip
   `summary_projection_v1(...) -> apply_final_artifacts(...) -> summary_read_adapter_v1(...)`
   before returning state.
3. `anvil/harness/reporting.py` still reranks drafts during artifact emission,
   so selection truth is duplicated between the graph node
   `select_best_draft_node(...)` and the reporting layer.

That means B2 can prove topology parity, but B3 still has split truth for state,
selection, and artifact emission.

B3 fixes that split in one milestone:

- graph-native `HarnessState` becomes canonical for migrated surfaces
- native draft projection replaces summary-derived draft reconstruction on the
  graph-owned success path
- `select_best_draft_node(...)` becomes the only ranking owner
- artifact publishing becomes state-native
- `summary_projection_v1(...)` remains, but only as the final one-way summary
  projection seam
- `summary_read_adapter_v1(...)` remains compatibility-only and is removed from
  the graph-owned success path
- legacy summaries and reports remain readable, and restart-at-run-boundary
  remains the minimum recovery contract

The milestone question is simple:

**Can the harness keep the B2 graph-owned topology, but make state, selection,
and artifact publishing canonical on native graph state without changing the
artifact contract?**

This plan says yes, but only if native state completion, single-owner
selection, state-native artifact publishing, compatibility-boundary reduction,
and full parity coverage land together.

## Preconditions and Non-Negotiables

These are implementation gates, not suggestions.

- B2 parity must already be green on `main` before B3 starts. B3 is not allowed
  to debug unfinished B2 topology drift at the same time it changes state truth.
- B3 only covers the `analysis_review` migrated surface. Do not widen into
  `single_pass`, `pfr_v1`, or future C-series graph/compiler work.
- External artifact semantics stay stable in this milestone. `summary.json`,
  `REPORT.md`, `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*` may gain
  approved graph-trace metadata, but they may not change contract shape or
  meaning.
- `legacy_bridge` remains the boring rollback path for the whole milestone. B3
  does not change rollout defaults, flags, or operator playbooks.
- No merge is complete until the parity matrix, readability checks, and the
  named deleted bridge path are all proven green.

## Success Criteria

- no graph-owned success path calls `summary_read_adapter_v1(...)`
- no graph-owned success path calls `state_from_summary(...)`
- graph-owned `drafts` are built from native stage history plus validator state,
  not from a synthetic summary wrapper
- `select_best_draft_node(...)` is the only canonical draft-ranking owner on
  the graph path
- artifact publishing on the graph-owned success path consumes
  `HarnessState`, not rehydrated summary-derived state
- `summary_projection_v1(...)` remains the only sanctioned summary write
  boundary
- `summary_read_adapter_v1(...)` remains allowed only:
  - inside `LegacyBridgeBoundary.run(...)`
  - in historical summary/readability tooling
  - in compatibility and parity tests
- `bridge_boundary_version` is stamped only by the actual legacy bridge path,
  never by graph-owned success-path execution
- final artifact kind and payload remain stable across `legacy_bridge` and
  `graph_owned` runs for the canonical parity corpus
- `summary.json` and `REPORT.md` remain readable and stable except for approved
  graph-trace metadata
- failed-run recovery remains supported at restart-at-run-boundary minimum
- at least one named bridge-only path is deleted:
  `write_artifacts_node -> summary_read_adapter_v1(...)` on the graph-owned
  success path

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | B3 decision |
|---|---|---|
| Native graph state carrier already exists | `anvil/harness/state.py` already defines `HarnessState`, `drafts`, `stage_history`, `issue_history`, `artifact_index`, `summary_payload`, `analysis_review_runtime`, and selection ids | Keep `HarnessState` as the canonical carrier. Expand it to include every graph-owned field downstream reporting and publication actually consume. |
| Graph-owned subgraph already merges most runtime outputs into state | `anvil/harness/subgraphs/analysis_review_v1.py` already copies stage history, validator rounds, policy checks, issue/topic ledgers, verdicts, and analysis details into state | Finish the migration here. Remove summary-derived draft reconstruction and stop stamping legacy bridge metadata on graph-owned success paths. |
| Draft ranking logic already accepts native drafts | `anvil/harness/selection.py` exposes `select_best_draft(drafts)` and `anvil/harness/nodes/select_best_draft.py` already selects from `state["drafts"]` | Keep the ranking rules. Change only how drafts are projected and lock the graph node as the sole ranking owner. |
| Draft projection logic already exists, but it is summary-shaped | `extract_drafts_from_summary(...)` in `anvil/harness/selection.py` rebuilds draft semantics from `summary["agent_stages"]` and `summary["validator_rounds"]` | Split this into a canonical native projector plus a thin summary compatibility wrapper. |
| Artifact publishing seam already exists | `anvil/harness/reporting.py` owns `summary_projection_v1(...)`, `apply_final_artifacts(...)`, and `write_state_artifacts(...)` | Keep module ownership here, but invert the control flow so state-native publication is canonical and summary projection happens once at the end. |
| Current artifact node still round-trips through summary | `anvil/harness/nodes/write_artifacts.py` projects summary, writes artifacts, then rehydrates state with `summary_read_adapter_v1(...)` | Delete this success-path round-trip in B3. This is the named bridge-only path that must go away. |
| Report rendering surface already exists | `anvil/harness/report.py` renders `REPORT.md` from the summary contract | Keep `REPORT.md` stable. Make `summary_projection_v1(...)` responsible for producing a complete report-ready summary from state. |
| Legacy bridge boundary is already explicit | `anvil/harness/subgraphs/_bridge.py` re-enters `HarnessRunner` and rehydrates state from summary | Keep this path compatibility-only. No B3 semantics land here. |
| Regression floor already exists | `tests/test_harness_selection.py`, `tests/test_harness_state_boundaries.py`, `tests/test_harness_reporting.py`, `tests/test_harness_analysis_review_graph.py`, `tests/test_harness_runner.py` | Expand these. Do not create a parallel test universe that ignores the existing seams. |

### Minimum complete scope

This is the minimum complete B3 slice. If any item is skipped, the milestone is
not actually graph-native state canonicalization.

1. root `PLAN.md`
2. `anvil/harness/state.py`
3. `anvil/harness/selection.py`
4. `anvil/harness/subgraphs/analysis_review_v1.py`
5. `anvil/harness/nodes/select_best_draft.py`
6. `anvil/harness/nodes/write_artifacts.py`
7. `anvil/harness/reporting.py`
8. `anvil/harness/report.py`
9. `anvil/harness/subgraphs/_bridge.py`
10. targeted compatibility adjustments in `anvil/harness/runner.py` only if
    needed to preserve legacy summary behavior after the draft-projection split
11. targeted test expansions under `tests/`

### Complexity verdict

This milestone crosses more than 8 files. That is justified.

The problem is not one bad helper. The problem is split ownership between:

- a graph that now owns topology
- a subgraph merge step that still reconstructs drafts from summary-shaped data
- a selection node that ranks drafts correctly
- a reporting layer that reranks drafts again
- a write-artifacts node that still treats summary rehydration as normal

A smaller diff that removes one `summary_read_adapter_v1(...)` call but leaves
duplicate ranking, seeded-summary overrides, or legacy bridge metadata on
graph-owned runs will create a fake B3.

What would be overbuilt:

- a new artifact contract version in the same milestone
- stage-boundary resume
- a generic graph-state persistence framework
- a full rewrite of `report.py`
- public DAG/compiler work from C1-C3
- touching `single_pass` or `pfr_v1` just because the files are nearby

### Search/build verdict

This is a Layer 1 reuse milestone with one Layer 3 rule.

Reuse:

- `HarnessState` as the canonical native carrier
- `select_best_draft(drafts)` as the ranking algorithm
- `summary_projection_v1(...)` as the only sanctioned write-side summary seam
- `render_report(...)` as the existing report renderer
- `LegacyBridgeBoundary` as the compatibility fallback
- the existing canonical parity corpus and artifact-diff assertions

First-principles rule:

- state is truth, summary is projection

That means B3 must not keep treating `summary_payload` as a shadow source of
truth just because it is convenient. If the graph-owned success path needs a
field, that field belongs in `HarnessState`.

### TODOS cross-reference

`docs/project_management/future/TODOS.md` has no blocker for B3.

Do not pull stage-boundary resume, artifact-contract v2 work, or public graph
config into this milestone. If B3 exposes new follow-up work, capture it after
native-state parity is green.

### Completeness verdict

The shortcut is "stop rehydrating in `write_artifacts_node(...)`, but keep
reconstructing drafts from summary-shaped data and let reporting rerank them."

That is fake progress.

The complete B3 version must do all of this together:

- define the full native state contract for migrated surfaces
- split canonical draft projection from summary compatibility parsing
- make `select_best_draft_node(...)` the only ranking owner
- make artifact publishing consume native state directly
- keep summary projection as a final one-way serialization step
- preserve historical summary readability and restart-at-run-boundary recovery
- prove parity on summary/report/final-artifact surfaces and failure paths

### Distribution and DX verdict

Forge is a developer tool. B3 is incomplete if native-state publication only
works in unit tests.

B3 must preserve:

- `python -m anvil.harness.cli run ...`
- readable `summary.json`
- readable `REPORT.md`
- stable `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*` semantics
- replay/readability of old summaries produced before B3

It does not need to change CLI flags or rollout defaults. This is a state and
artifact-truth milestone, not a product-surface rewrite.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Milestone scope | B3 is state/reporting/selection cleanup only | No new topology rewrite. B2 remains the topology milestone. |
| Native truth | `HarnessState` is canonical for graph-owned migrated surfaces | The graph already owns topology. State must now own execution truth. |
| Draft projection truth | add a canonical native draft projector in `anvil/harness/selection.py`; keep `extract_drafts_from_summary(...)` compatibility-only | Drafts must stop depending on synthetic summary wrappers. |
| Ranking owner | `anvil/harness/nodes/select_best_draft.py` is the only canonical draft-ranking owner | Selection truth cannot be duplicated in `reporting.py`. |
| Reporting behavior | reporting may validate selected ids, but may not silently rerank drafts on the graph-owned success path | One ranking owner. No shadow decision logic. |
| Summary write boundary | `summary_projection_v1(...)` stays canonical | This is still the only sanctioned graph-to-summary projection. |
| Summary read boundary | `summary_read_adapter_v1(...)` and `state_from_summary(...)` are compatibility-only in B3 | They remain useful for historical readability, not graph-owned success execution. |
| Artifact truth | state-native publisher in `anvil/harness/reporting.py` becomes canonical | Artifact emission must consume native state directly. |
| Legacy bridge metadata | `bridge_boundary_version` is set only by `LegacyBridgeBoundary.run(...)` | Graph-owned paths must stop pretending they crossed the bridge. |
| Recovery contract | restart-at-run-boundary only | Stage-boundary resume remains deferred. |
| Rollout control | B3 does not change `legacy_bridge` / `graph_owned` flag semantics or defaults | Keep rollback boring while state truth changes under the hood. |

## Source of Truth and Contracts

### B3 source-of-truth table

| Concern | Canonical owner in B3 | Notes |
|---|---|---|
| Topology truth for migrated `analysis_review` | `anvil/harness/subgraphs/analysis_review_v1.py` | Unchanged from B2. B3 does not reopen topology ownership. |
| Stage-semantics execution | `anvil/harness/analysis_review_runtime.py` plus existing runner-backed stage helpers | Reused. No new semantics copied into compatibility glue. |
| Native state truth | `anvil/harness/state.py` | Must carry every downstream field required for selection, artifacts, and reports. |
| Draft projection truth | canonical native draft projector in `anvil/harness/selection.py` | Graph-owned success path uses this directly; summary parser becomes compatibility-only. |
| Selection truth | `anvil/harness/nodes/select_best_draft.py` | Sole owner of best/selected draft choice on the graph path. |
| Artifact truth | state-native publisher in `anvil/harness/reporting.py` | Produces deliverables, `summary.json`, `REPORT.md`, and `artifact_index` from state. |
| Summary/report contract | `summary_projection_v1(...)` + `render_report(...)` | One-way projection from state into stable external surfaces. |
| Historical summary read compatibility | `summary_read_adapter_v1(...)` / `state_from_summary(...)` | Legacy/historical only. Not success-path execution helpers. |
| Rollback path | `anvil/harness/subgraphs/_bridge.py` | Remains the only sanctioned legacy bridge. |

### Current-to-B3 dependency graph

```text
CURRENT
=======
analysis_review_v1_subgraph
  -> graph-owned stage execution
  -> _merge_runner_state(...)
       -> stage_records_from_summary(...)
       -> extract_drafts_from_summary(_draft_summary_from_runner(...))
       -> select_best_draft(drafts)
       -> bridge_boundary_version = legacy_bridge_boundary_v1
  -> parent graph select_best_draft node
  -> write_artifacts_node
       -> summary_projection_v1(...)
       -> apply_final_artifacts(...)
            -> select_best_draft(summary["drafts"])
       -> summary_read_adapter_v1(...)
  -> finalize


B3 TARGET
=========
analysis_review_v1_subgraph
  -> graph-owned stage execution
  -> native state merge
       -> stage_history
       -> drafts_from_stage_history_v1(...)
       -> issue_history / topic_ledger / recommendation_reviews
       -> best/selected ids left for select_best_draft node
       -> no legacy bridge metadata on graph-owned path
  -> parent graph select_best_draft node
       -> sole ranking owner
  -> write_artifacts_node
       -> publish_state_artifacts_v1(state)
            -> choose deliverable from selected ids + native verdict state
            -> summary_projection_v1(state)
            -> write summary/report/deliverables
            -> update artifact_index + summary_payload in place
       -> no summary_read_adapter_v1(...)
  -> finalize


COMPATIBILITY PATHS THAT REMAIN
===============================
LegacyBridgeBoundary.run(...)
  -> summary_read_adapter_v1(...)

historical summary tooling / compatibility tests
  -> state_from_summary(...)
```

### Graph-native state and artifact flow

```text
graph-owned stage execution
  -> stage_history
  -> validator_rounds
  -> issue_history / topic_ledger
  -> analysis_review_status / recommendation_reviews / final_answer
  -> drafts_from_stage_history_v1(...)
  -> select_best_draft_node(...)
       -> best_draft_id / selected_draft_id
  -> publish_state_artifacts_v1(...)
       -> FINAL_ANSWER / PARTIAL_ANSWER / BEST_DRAFT
       -> summary_projection_v1(...)
       -> REPORT.md
       -> summary.json
       -> artifact_index
```

### Native state contract

These names are fixed for B3. Do not rename them during implementation.

| Surface | Exact contract |
|---|---|
| Native draft truth | `HarnessState.drafts` |
| Native selection ids | `current_draft_id`, `best_draft_id`, `selected_draft_id` |
| Native issue truth | `issue_history`, `open_issue_ids` |
| Native topic truth | `topic_ledger` |
| Native publishability truth | `run_verdict`, `content_verdict`, `validator_verdict`, `policy_verdict`, `analysis_review_status`, `recommendation_reviews`, `final_answer`, `bounded_review_summary`, `bounded_attestation_input` |
| Native observability truth | `stage_history`, `validator_rounds`, `policy_checks`, `changed_files`, `validator_summary`, `analysis_review_coverage` |
| External artifact refs | `artifact_index` |
| Final projected summary cache | `summary_payload` |
| Legacy bridge marker | `bridge_boundary_version`, set only by the actual legacy bridge |

Rules:

- graph-owned success-path helpers may append or transform native state
- graph-owned success-path helpers may not rebuild required fields from
  `summary_payload`
- if `report.py` or artifact emission needs a field and that field is not in
  `HarnessState`, B3 adds it to native state rather than teaching reporting to
  read around the gap from seeded summary data

### Summary boundary rules

Allowed uses of `summary_read_adapter_v1(...)` and `state_from_summary(...)` in
B3:

1. `LegacyBridgeBoundary.run(...)`
2. historical summary/readability tooling
3. compatibility and parity tests

Forbidden uses on the graph-owned success path in B3:

- inside `_merge_runner_state(...)`
- inside `select_best_draft_node(...)`
- inside `write_artifacts_node(...)`
- after `summary_projection_v1(...)`
- as a fallback to refill missing native state fields that should be explicit in
  `HarnessState`

The rule is simple:

**Graph-owned execution carries native state all the way through artifact
publication.**

### File change contract

| File | Allowed change in B3 | Forbidden change in B3 |
|---|---|---|
| `anvil/harness/state.py` | expand `HarnessState` and compatibility comments so all graph-owned downstream fields are first-class | No artifact-contract version bump here |
| `anvil/harness/selection.py` | add canonical native draft projection and keep summary parsing as compatibility-only | No ranking-rule rewrite unless parity proves current ordering is wrong |
| `anvil/harness/subgraphs/analysis_review_v1.py` | replace summary-derived draft reconstruction with native projection and remove legacy bridge metadata from graph-owned runs | No topology rewrite, no new reporting semantics hidden here |
| `anvil/harness/nodes/select_best_draft.py` | remain the sole ranking owner and update native draft ids deterministically | No artifact-writing or summary-repair logic here |
| `anvil/harness/nodes/write_artifacts.py` | call a state-native publisher and stop rehydrating state from summary on success paths | No hidden compatibility fallbacks that recreate native state from summary |
| `anvil/harness/reporting.py` | publish artifacts from native state and project the final summary once | No reranking drafts on graph-owned success paths |
| `anvil/harness/report.py` | continue rendering from the stable summary contract only | No new required report-only fields that cannot be projected from state |
| `anvil/harness/subgraphs/_bridge.py` | remain legacy-only and preserve compatibility behavior | No new graph-owned logic |
| `anvil/harness/runner.py` | adjust only as needed so legacy summary behavior still works after the projector split | No new canonical state truth here |
| `tests/*` | add native-state, parity, readability, and recovery assertions | No golden drift without an explicit contract reason |

## Execution Spine

The implementation order is fixed. This is one spine with merge gates, not five
independent cleanup ideas.

### Merge gates

| Gate | Must be true before moving on |
|---|---|
| Gate 1: native state frozen | `HarnessState` carries every downstream publish/report field and graph-owned draft projection no longer depends on synthetic summary wrappers |
| Gate 2: selection frozen | `select_best_draft_node(...)` is the only graph-path ranking owner and `reporting.py` no longer makes a second winner decision |
| Gate 3: publisher frozen | graph-owned success execution publishes deliverables, `summary.json`, and `REPORT.md` from native state without `summary_read_adapter_v1(...)` |
| Gate 4: compatibility frozen | remaining summary-read seams are explicit, legacy-only, and historical readability still passes |
| Gate 5: parity frozen | full B3 parity matrix, CLI/readability surfaces, and the deleted bridge-path regression assertions are green |

### `runner.py` touch rule

`anvil/harness/runner.py` is not a default edit target in B3.

Touch it only if one of these becomes true after the projector split:

1. legacy summary-only execution fails to emit the pre-B3 compatibility shape,
2. historical summary readability tests prove the runner still owns a helper
   that the new compatibility wrapper must call, or
3. parity tests show the legacy path now diverges only because runner-local
   summary assembly still assumes summary-native draft truth.

If none of those trigger, do not edit `runner.py`.

## Detailed Implementation Plan

### Phase 1: Complete the native state contract and split draft projection

Goal: graph-owned success execution must build selection inputs from native
state, not from synthetic summary wrappers.

Primary code surfaces:

- `anvil/harness/state.py`
- `anvil/harness/selection.py`
- `anvil/harness/subgraphs/analysis_review_v1.py`
- `anvil/harness/runner.py` only if the touch rule above triggers

Implementation contract:

1. Expand `HarnessState` so every graph-owned downstream field consumed by
   selection, publication, report rendering, or recovery is explicit and typed.
2. Add a canonical native draft projection helper in `anvil/harness/selection.py`
   named `drafts_from_stage_history_v1(...)`.
3. Define `drafts_from_stage_history_v1(...)` to accept stage history plus
   validator-round context, not summary blobs.
4. Refactor `extract_drafts_from_summary(...)` into a compatibility wrapper that
   unpacks summary fields and delegates to `drafts_from_stage_history_v1(...)`.
5. Update `_merge_runner_state(...)` in
   `anvil/harness/subgraphs/analysis_review_v1.py` to use
   `drafts_from_stage_history_v1(...)` directly.
6. Preserve the current ranking algorithm in `select_best_draft(drafts)`.
   B3 changes draft projection ownership, not ranking semantics.
7. Stop setting `bridge_boundary_version` on graph-owned success paths.
   Only `LegacyBridgeBoundary.run(...)` is allowed to stamp that field.

Merge gate to exit Phase 1:

- graph-owned `drafts` are built without `extract_drafts_from_summary(...)`
- graph-owned success-path state carries all downstream publish/report fields
- legacy summary parsing still works for historical readability and tests
- the projector signature and native field names are frozen for downstream work

### Phase 2: Make `select_best_draft_node(...)` the sole selection owner

Goal: selection truth must exist in one place.

Primary code surfaces:

- `anvil/harness/nodes/select_best_draft.py`
- `anvil/harness/selection.py`
- `anvil/harness/reporting.py`
- `anvil/harness/state.py`

Implementation contract:

1. Keep `anvil/harness/nodes/select_best_draft.py` as the only canonical place
   that chooses `best_draft_id` and `selected_draft_id` on the graph path.
2. Ensure graph-owned state entering `select_best_draft_node(...)` has
   deterministic `drafts` and `current_draft_id`, but does not pretend ranking
   is final before the node runs.
3. Remove graph-owned success-path reranking from the reporting layer.
   `reporting.py` may look up the selected draft by id, but it may not call
   `select_best_draft(...)` to make a second decision.
4. Preserve summary-read compatibility by allowing summary adapters to compute
   missing selection ids only when reading old summaries that predate B3.
5. Keep final artifact choice aligned with `selected_draft_id` and
   `best_draft_id` already present in native state.

Merge gate to exit Phase 2:

- graph-owned success execution has exactly one ranking owner
- `reporting.py` no longer silently picks a different best draft than the graph
- legacy summary compatibility remains readable
- selection ids are now a frozen upstream input for publication work

### Phase 3: Replace success-path summary round-tripping with state-native artifact publishing

Goal: artifact emission must consume native state directly and project summary
once at the end.

Primary code surfaces:

- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`

Implementation contract:

1. Add a canonical state-native publisher in `anvil/harness/reporting.py`
   named `publish_state_artifacts_v1(state)`.
2. Move graph-owned success-path deliverable selection, artifact emission, and
   artifact-index population under `publish_state_artifacts_v1(state)`.
3. Make `publish_state_artifacts_v1(state)` consume native verdicts, selected
   ids, ledgers, publishability details, and final-answer payloads directly from
   `HarnessState`.
4. Keep `summary_projection_v1(...)` as the final one-way projection used to
   materialize `summary.json` and feed `render_report(...)`.
5. Update `write_artifacts_node(...)` to return the same native state with
   `artifact_index` and `summary_payload` updated in place. No
   `summary_read_adapter_v1(...)` call on the graph-owned success path.
6. Treat the current `apply_final_artifacts(summary)` flow as a compatibility
   helper for summary-native inputs only if a legacy summary-only path still
   requires it. It is no longer canonical for graph-owned success execution.

Merge gate to exit Phase 3:

- graph-owned success execution does not rehydrate state from summary
- final deliverables, `summary.json`, and `REPORT.md` are emitted from native
  state via a single publish path
- `summary_payload` becomes a final projected cache, not an input dependency
- publisher inputs and outputs are stable enough for boundary cleanup and full
  parity assertions

### Phase 4: Reduce the summary boundary surface and lock the recovery contract

Goal: make the remaining compatibility seams explicit, small, and honest.

Primary code surfaces:

- `anvil/harness/state.py`
- `anvil/harness/nodes/write_artifacts.py`
- `anvil/harness/subgraphs/_bridge.py`
- `anvil/harness/reporting.py`
- `anvil/harness/runner.py` only if the touch rule above triggers

Implementation contract:

1. Enumerate the only remaining sanctioned `summary_read_adapter_v1(...)` and
   `state_from_summary(...)` call sites in code comments and tests.
2. Remove any graph-owned success-path fallback branches that treat summary as a
   general-purpose state carrier.
3. Ensure seeded summary data in `summary_projection_v1(...)` never overrides
   canonical native state on graph-owned success execution.
4. Keep historical summary readability intact for old artifacts.
5. Preserve restart-at-run-boundary recovery by ensuring the projected summary
   remains complete and readable after failed runs.
6. Do not promise stage-boundary resume. That remains out of scope.

Merge gate to exit Phase 4:

- compatibility seams are explicit and small
- graph-owned success path is free of summary rehydration
- historical summary readability still works
- restart-at-run-boundary remains supported
- only the sanctioned legacy call sites remain for summary-to-state adaptation

### Phase 5: Prove B3 parity and compatibility on the canonical matrix

Goal: B3 lands only when native-state truth is real, not just cleaner-looking.

Primary code surfaces:

- `tests/test_harness_selection.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_analysis_review_graph.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_run_focus_gate_acceptance.py`

Implementation contract:

1. Prove native draft projection parity between:
   - historical summary compatibility parsing
   - graph-owned native stage-history projection
2. Prove `select_best_draft_node(...)` is the only graph-path ranking owner.
3. Prove graph-owned success-path artifact publication never calls
   `summary_read_adapter_v1(...)`.
4. Diff `legacy_bridge` and `graph_owned` runs on:
   - final artifact kind
   - emitted payload
   - `summary.json`
   - `REPORT.md`
   - `analysis_review_status`
   - `recommendation_reviews`
   - issue/topic ledgers
   - selection ids and publishability surface
5. Prove historical summary readability still works for pre-B3 artifact shapes.
6. Prove failed-run summaries remain readable and support restart-at-run-boundary
   reasoning.

Merge gate to exit Phase 5:

- parity rows are green for both compatibility and graph-owned success surfaces
- historical summary readability remains green
- the deleted success-path rehydration bridge stays dead by test coverage
- CLI and operator-visible artifact/report surfaces remain stable

## Test and Parity Plan

### Existing regression floor

These are non-negotiable and must stay green:

- `tests/test_harness_selection.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_analysis_review_graph.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_run_focus_gate_acceptance.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/fixtures/harness/analysis_review_semantic_cases.json`
- `tests/fixtures/harness/m2_focus_gate_fixture_wiring/triads.yaml`

### Required new and expanded tests

| Test file | Required assertions |
|---|---|
| expand `tests/test_harness_selection.py` | `drafts_from_stage_history_v1(...)` matches expected draft semantics; `extract_drafts_from_summary(...)` is a compatibility wrapper, not a second source of truth |
| expand `tests/test_harness_state_boundaries.py` | graph-owned success path never calls `summary_read_adapter_v1(...)`; graph-owned success path never stamps `bridge_boundary_version`; historical summaries still adapt cleanly |
| expand `tests/test_harness_reporting.py` | `publish_state_artifacts_v1(state)` emits stable deliverables, `summary.json`, and `REPORT.md` from native state; reporting does not rerank drafts on graph-owned success paths |
| expand `tests/test_harness_analysis_review_graph.py` | graph-owned runs populate native drafts, selection ids, and artifact-ready state before `write_artifacts_node(...)` |
| expand `tests/test_harness_runner.py` | legacy runner summary output remains readable and compatible with the new compatibility wrappers |
| expand `tests/test_harness_cli_command.py` | CLI output and exit codes stay stable after the publisher path changes |
| expand `tests/test_harness_standalone_cli.py` | memory and sqlite checkpoint modes keep stable user-visible artifact/report surfaces |
| expand `tests/test_harness_example_strategy_wiring.py` | strategy wiring still yields the same migrated surface outputs after selection and publication truth move fully into state |
| expand `tests/test_run_focus_gate_acceptance.py` | blocked, selected, and no-viable-focus outcomes still produce stable artifacts and report/readability behavior in both execution modes |

### Coverage diagram

```text
CODE PATH COVERAGE
===========================
[+] Native draft projection
    ├── [GAP]  graph-owned drafts are still reconstructed via summary-shaped data
    ├── [PLAN] add drafts_from_stage_history_v1(...)
    └── [TEST] tests/test_harness_selection.py, tests/test_harness_analysis_review_graph.py

[+] Selection ownership
    ├── [GAP]  select_best_draft node and reporting both participate in ranking
    ├── [PLAN] keep ranking in select_best_draft_node(...) only
    └── [TEST] tests/test_harness_reporting.py, tests/test_harness_state_boundaries.py

[+] Artifact publishing
    ├── [GAP]  write_artifacts still projects summary then rehydrates state
    ├── [PLAN] publish artifacts directly from native state
    └── [TEST] tests/test_harness_reporting.py, tests/test_harness_state_boundaries.py

[+] Report and summary projection
    ├── [GAP]  seeded summary data can still behave like shadow state
    ├── [PLAN] summary_projection_v1(...) is final one-way projection only
    └── [TEST] tests/test_harness_reporting.py

[+] Compatibility readability
    ├── [GAP]  summary adapters are still normalized as general execution helpers
    ├── [PLAN] restrict them to legacy/historical compatibility only
    └── [TEST] tests/test_harness_state_boundaries.py, tests/test_harness_runner.py

[+] Recovery contract
    ├── [GAP]  B3 could accidentally shrink failed-run readability while cleaning state seams
    ├── [PLAN] keep restart-at-run-boundary and readable final artifacts
    └── [TEST] tests/test_harness_reporting.py, tests/test_harness_analysis_review_graph.py
```

### B3 parity matrix

This matrix is the milestone gate. No row is optional.

| Scenario family | Mode | Must match |
|---|---|---|
| bounded, no focus gate | `legacy_bridge` vs `graph_owned` | selected/best draft ids, final artifact kind, emitted payload, `summary.json`, `REPORT.md`, ledgers |
| bounded, focus gate selected | both | `focus_decision`, downstream selection ids, summary/report parity |
| bounded, focus gate blocked | both | early stop readability, no bogus selected draft, artifact/report parity |
| bounded, no viable focus | both | early stop readability, no downstream publication drift |
| trust, `attestation_over_bounded` | both | bounded-review summary, attestation-derived publication surfaces, final artifacts, report parity |
| partial acceptance | both | included/excluded recommendation indices, admissibility reasons, emitted artifact kind |
| invalid config / preflight failure | both | readable `summary.json`, readable `REPORT.md`, no success-path rehydration fallback |
| historical artifact read compatibility | old summaries | `state_from_summary(...)` / `summary_read_adapter_v1(...)` still reconstruct readable compatibility state |

### Operator and user-surface checks

These are the human-visible flows that must stay boring while B3 changes
internal truth ownership.

| Surface | What must remain true |
|---|---|
| `python -m anvil.harness.cli run ...` | still produces the same artifact family and readable failure/success surfaces for equivalent inputs |
| `summary.json` | remains readable as the canonical machine-readable audit surface |
| `REPORT.md` | remains readable as the canonical human-readable audit surface |
| `FINAL_ANSWER.*` / `PARTIAL_ANSWER.*` / `BEST_DRAFT.*` | still match verdict and admissibility rules, with no summary-vs-deliverable drift |
| old run directories | still load through compatibility tooling without asking the user to regenerate artifacts |
| failed runs | still leave enough readable state for restart-at-run-boundary reasoning and postmortem inspection |

### Validation commands

Run these commands before calling B3 done:

```bash
poetry run pytest -q \
  tests/test_harness_selection.py \
  tests/test_harness_state_boundaries.py \
  tests/test_harness_reporting.py \
  tests/test_harness_analysis_review_graph.py \
  tests/test_harness_runner.py \
  tests/test_harness_cli_command.py \
  tests/test_harness_standalone_cli.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_run_focus_gate_acceptance.py

poetry run python -m anvil.harness.cli run --help
poetry run python -m anvil list
```

Expected result:

- graph-owned success-path artifact publication is state-native
- legacy rollback and historical summary readability remain green
- no parity drift appears outside approved graph-trace metadata

## Failure Modes Registry

| Codepath | Realistic production failure | Test required | Error handling required | User-visible outcome |
|---|---|---|---|---|
| native draft projection | draft projector drops validator failures or topic debt, so the wrong draft wins | yes | yes | user gets the wrong `BEST_DRAFT` or `FINAL_ANSWER` with no obvious crash |
| selection ownership | reporting silently reranks drafts and picks a different winner than the graph | yes | yes | `summary.json`, `REPORT.md`, and deliverables disagree |
| graph-owned merge | graph-owned success path still stamps `bridge_boundary_version` | yes | yes | operators think the legacy bridge ran when it did not |
| artifact publication | state-native publisher emits a different final artifact kind than B2 for the same verdict | yes | yes | user sees `BEST_DRAFT` where `FINAL_ANSWER` or `PARTIAL_ANSWER` should exist |
| partial acceptance | included/excluded recommendation indices drift between deliverable and summary/report | yes | yes | user sees contradictory acceptance surfaces |
| summary projection | seeded summary data overrides newer native state during final projection | yes | yes | silent summary/report drift |
| compatibility adapter | old summaries stop being readable after the projector split | yes | yes | users cannot inspect or replay old runs |
| failed-run recovery | B3 cleanup accidentally makes failed runs unreadable even if execution cannot resume | yes | yes | postmortem quality regresses and restart-at-run-boundary becomes guesswork |

Critical-gap rule:

Any failure mode with no test, no guard, and silent user impact blocks the
milestone. No exceptions.

## Rollout and Reversibility

### Risks to avoid

- topology stays graph-owned, but state truth remains split
- reporting continues to rerank drafts after the graph already chose one
- graph-owned success execution still advertises the legacy bridge boundary
- seeded summary data silently wins over native state on projection
- compatibility cleanup breaks old artifact readability
- B3 accidentally changes rollout defaults instead of just fixing state truth

### Boring implementation sequence

1. finish the native state contract and split draft projection
2. make the select-best-draft node the only ranking owner
3. switch artifact publication to state-native flow
4. reduce compatibility boundaries and lock recovery rules
5. prove parity and readability on the full matrix

### Rollout and rollback criteria

Roll forward rules:

- do not start B3 until B2 parity is already green
- do not change `legacy_bridge` / `graph_owned` rollout semantics or defaults
- keep legacy summary readability intact throughout the milestone

Rollback triggers:

- any mismatch in final artifact kind or emitted payload between modes
- any mismatch in selected/best draft ids between graph-owned state and emitted
  artifacts
- any graph-owned success path calling `summary_read_adapter_v1(...)`
- any graph-owned success path stamping `bridge_boundary_version`
- any historical summary that stops adapting cleanly through compatibility
  tooling

Rollback action:

- rerun with `--analysis-review-execution-mode legacy_bridge`
- keep the B2 compatibility path as the safe operational fallback until the B3
  drift is fixed

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| native state contract + draft projection | `anvil.harness.state`, `anvil.harness.selection`, `anvil.harness.subgraphs` | — |
| selection-owner canonicalization | `anvil.harness.nodes`, `anvil.harness.reporting`, `anvil.harness.state` | native state contract + draft projection |
| state-native artifact publishing | `anvil.harness.nodes`, `anvil.harness.reporting`, `anvil.harness.report` | native state contract + draft projection, selection ids frozen |
| compatibility boundary cleanup | `anvil.harness.subgraphs`, `anvil.harness.runner`, `anvil.harness.state`, `anvil.harness.nodes` | native state contract + artifact publisher contract |
| parity and compatibility tests | `tests/` | each lane above as its contract freezes |

### Parallel lanes

Lane A: native state contract + draft projection  
Sequential within the lane. It freezes the native field names, the canonical
draft-projector signature, and the graph-owned merge contract.

Lane B: selection-owner canonicalization  
Starts after Lane A freezes `drafts`, `current_draft_id`, `best_draft_id`, and
`selected_draft_id`.

Lane C: state-native artifact publishing  
Starts after Lane A freezes the native publish inputs. Finishes after Lane B
freezes selection ownership.

Lane D: compatibility boundary cleanup  
Starts after Lane C freezes the final publisher contract.

Lane E: tests  
Split into two passes:
- E1: native draft projection and state-boundary assertions can start after
  Lane A
- E2: reporting/parity/readability assertions finish after Lanes B, C, and D

### Execution order

1. Launch Lane A first and merge it.
2. Start Lane B after A freezes state and draft contracts.
3. Start Lane E1 in parallel with Lane B for native-state and boundary tests.
4. Start Lane C after A, but do not finish it until B freezes selection
   ownership.
5. Start Lane D after C freezes the state-native publisher contract.
6. Finish Lane E2 after B, C, and D merge.

### Conflict flags

- Lanes A, B, and D all touch the `anvil.harness.state` surface, so they cannot
  merge independently without coordination.
- Lanes B and C both touch the `anvil.harness.reporting` surface, so selection
  ownership must freeze before final publisher work lands.
- Lanes C and D both touch node-layer publication behavior, so D cannot start
  early without rebase churn.
- Lanes C and E2 both touch reporting-focused test surfaces. Keep test
  ownership crisp to avoid merge noise.

Verdict:

This is partially parallel, but the core state and publisher contracts are
serial. Treat it like one primary spine with a test lane running beside it.

## NOT in scope

| Deferred item | Why not in B3 |
|---|---|
| changing B2 topology ownership | B2 already owns topology parity; reopening it would hide whether B3 actually fixed state truth |
| changing `legacy_bridge` / `graph_owned` rollout semantics or defaults | rollout changes would spend the rollback safety margin on operator behavior instead of correctness |
| deleting the legacy bridge entirely | B3 still needs the boring rollback path while native-state publication hardens |
| `single_pass` or `pfr_v1` state/reporting cleanup | nearby code is not part of the migrated `analysis_review` truth surface for this milestone |
| stage-boundary resume | that is a larger recovery-contract milestone and would blur the B3 acceptance target |
| artifact contract v2 | external surface versioning is a separate product decision, not a prerequisite for native-state truth |
| public DAG or graph compiler work | that belongs to C-series follow-on work after internal graph/state parity is real |
| C1, C2, or C3 future-state work | directional future architecture is already captured in the design doc and should not leak into B3 execution |

## Completion Checklist

- `HarnessState` carries all graph-owned downstream publication fields
- graph-owned draft projection no longer depends on synthetic summary wrappers
- `select_best_draft_node(...)` is the only graph-path ranking owner
- graph-owned success-path artifact publication is state-native
- graph-owned success path never calls `summary_read_adapter_v1(...)`
- graph-owned success path never stamps `bridge_boundary_version`
- `summary_projection_v1(...)` remains the sole summary write boundary
- historical summary readability still works
- restart-at-run-boundary readability remains supported
- full B3 parity matrix is green

## Done Criteria

This milestone is done when a developer can run the same canonical
`analysis_review` task/strategy pair in both `legacy_bridge` and `graph_owned`
mode, and:

- the graph-owned success path publishes deliverables directly from native state
- `summary.json` and `REPORT.md` are still stable projections of that state
- no success-path summary rehydration occurs
- no second ranking decision occurs after `select_best_draft_node(...)`
- old summaries are still readable through compatibility tooling

At that point, B3 has actually made graph-native state canonical instead of
just making the code look cleaner.
