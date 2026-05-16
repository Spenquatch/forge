# PLAN: C1 Deterministic Planning Compiler Wedge

Status: ready for implementation on `main`  
Target branch: `main`  
Prepared from repo state on: `main`  
Milestone: `C1`  
Design source: `/Users/spensermcconnell/.gstack/projects/Spenquatch-forge/spensermcconnell-main-design-20260515-231048.md`

Supersedes:
- the prior root `PLAN.md` for B3 graph-native state / selection / artifact canonicalization
- the C1 milestone sketch inside the 2026-05-15 deterministic planning design doc

## Executive Summary

C1 is where `forge` stops proving only fixed review and repair runtimes and starts
proving a compiled planning runtime.

Right now the harness has good bones:

- typed task and strategy specs in [anvil/harness/types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py)
- strategy graph metadata in [anvil/harness/strategy_graph.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/strategy_graph.py)
- a shared LangGraph wrapper in [anvil/harness/builder.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/builder.py)
- artifact publication in [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py)
- strong graph, CLI, and artifact regression coverage under `tests/`

But the planning claim is still false.

The current harness only knows three runtime families:

- `single_pass`
- `pfr_v1`
- `analysis_review_v1`

That hard-coding shows up in all the places that matter:

- `TaskSpec.from_dict(...)` only accepts `patch` and `analysis_review`
- `HarnessState` only types the existing runtime families
- `route_after_strategy_selection(...)` only routes to `single_pass`, `pfr_v1`, or `analysis_review_v1`
- `build_harness_langgraph(...)` only mounts those three runtime nodes and always runs `select_best_draft`
- `validator_preflight_node(...)` only knows how to auto-fit between patch and analysis-review tasks
- artifact publishing assumes the existing summary/report/draft deliverable family

C1 fixes that by adding one real compiled planning runtime, `planning_v1`, and one
curated strategy, `deterministic_feature_planning_v1`, that can be declared in
repo-managed config and executed end to end without strategy-specific core-engine
edits for that strategy.

The runtime proof is narrow on purpose:

1. input is one feature request in one or two sentences
2. execution is one four-phase planning flow
3. output is one canonical planning package:
   - `PLAN.md`
   - `plan.json`
4. blocked runs stop honestly with structured clarification requests

This milestone is not "build a public workflow DSL."

It is "prove the harness can compile and run one useful planning strategy through
shared runtime seams, shared policy lookup, shared validation, and shared artifact
publication."

## Preconditions and Non-Negotiables

- B3 is already landed on `main`. C1 must build on the current graph-owned harness surface, not reopen B3 state-canonicalization work.
- The planning wedge stays curated and internal in C1. No public workflow DSL, no user-authored custom graph composition, no plugin marketplace story.
- The new strategy must be declared in repo-managed strategy config and run without new per-strategy branches in the core runtime for `deterministic_feature_planning_v1`.
- `planning_v1` is a new runtime family, not a disguised `analysis_review_v1` variant.
- Parallel workstream output is advisory metadata only. C1 does not create worktrees, branches, jobs, or agent dispatch automatically.
- Existing harness families must keep working exactly as they do today:
  - `single_pass`
  - `pfr_v1`
  - `analysis_review_bounded_v1`
  - `analysis_review_trust_v1`
- The primary documented CLI surface stays `poetry run python -m anvil.cli harness-run`.
- Planning artifacts must be deterministic in structure, IDs, and stop behavior on the bounded fixture corpus.
- No second parser stack. Task and strategy declarations must still flow through the existing structured file loading and typed config surfaces.

## Success Criteria

- A new strategy declaration with `kind: deterministic_feature_planning_v1` and `runtime_target: planning_v1` loads through the existing harness config path.
- The graph runtime routes planning runs through a shared `planning_v1` path without hard-coding logic for this one strategy name.
- A successful planning run emits:
  - `PLAN.md`
  - `plan.json`
  - `artifact_index` entries for both
  - `summary_payload` populated with the canonical `plan.json` payload for CLI compatibility
- A blocked planning run emits:
  - `terminal_status: clarification_needed`
  - non-empty `clarification_requests[]`
  - empty or partial downstream records, depending on where the stop occurred
- A failed planning run emits:
  - `terminal_status: failed`
  - non-empty `stop_reason`
- The planning runtime executes four declared phases in order:
  - `rubric_design_doc`
  - `architecture_seam_decomposition`
  - `parallel_workstream_planning`
  - `executable_slice_emission`
- `PLAN.md` always renders the same five top-level sections in canonical order:
  - problem statement
  - rubric results
  - architectural seams
  - parallel workstreams/worktrees
  - executable slices
- `plan.json` passes schema validation and carries stable IDs for selected seams, workstreams, and slices across three repeated runs per fixture.
- The bounded fixture corpus proves both outcomes:
  - at least one fixture succeeds with credible artifacts
  - at least one fixture blocks with honest clarification requests
- Existing non-planning harness tests stay green.

## Step 0: Scope Challenge

### What already exists

| Sub-problem | Existing code | C1 decision |
|---|---|---|
| Typed task parsing exists, but only for review and patch tasks | [anvil/harness/types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py) only accepts `patch` and `analysis_review` in `VALID_TASK_KINDS`, and `TaskSpec.from_dict(...)` defaults based on write policy | Extend the existing task surface with `planning`. Do not overload `analysis_review` for feature-planning requests. |
| Typed strategy parsing exists, but planning fields do not | `StrategyConfig` already loads `kind`, `roles`, validators, loops, focus-gate, and trust-review fields | Extend `StrategyConfig` with generic planning keys: `runtime_target`, `phases[]`, `artifact_policy`, `determinism_policy`, `discovery_policy`, `rubric_policy`, and `stop_policy`. Keep one loader. |
| Strategy graph metadata already exists | [anvil/harness/strategy_graph.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/strategy_graph.py) builds structured specs for `single_pass`, `pfr_v1`, and `analysis_review_*` | Reuse this file as the canonical strategy-to-runtime metadata builder. Add `planning_v1` as a new runtime family and add one generic post-runtime routing field so planning can bypass draft selection cleanly. |
| The shared graph wrapper already exists | [anvil/harness/builder.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/builder.py) builds a LangGraph wrapper with shared preflight, selection, artifact, and finalize nodes | Keep the shared wrapper. Add one `planning_v1` node and one generic post-runtime route. Do not create a second graph builder. |
| Executor, checkpointing, and streaming already exist | [anvil/harness/executor.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/executor.py) and [anvil/harness/graph_factory.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/graph_factory.py) already manage memory/sqlite graph execution | Reuse them unchanged except where new planning verdict semantics must flow through. |
| Preflight and task/strategy compatibility checks exist | [anvil/harness/nodes/validator_preflight.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py) auto-fits between patch and analysis-review surfaces | Extend preflight to validate planning tasks and planning strategies explicitly. Do not let auto-fit rewrite planning into review or patch flows. |
| Artifact publication seam already exists | [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py) already owns publication and projection logic, and [anvil/harness/artifacts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/artifacts.py) already owns run directory helpers | Reuse those modules. Add planning-specific projection and publication functions alongside the existing summary/report functions. |
| CLI entrypoints already exist | [anvil/harness/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/cli.py) and [anvil/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/cli.py) already expose `harness-run` and JSON mode | Keep those entrypoints. Extend printed fields and exit-code semantics so planning runs report `success`, `clarification_needed`, and `failed` clearly. |
| Example strategy and graph regression coverage already exists | `examples/harness/strategies/`, `tests/test_harness_strategy_graph.py`, `tests/test_harness_example_strategy_wiring.py`, `tests/test_harness_cli_command.py`, `tests/test_harness_standalone_cli.py`, `tests/test_harness_analysis_review_graph.py`, `tests/test_harness_reporting.py` | Extend this suite. Do not create a parallel, unconnected test surface that ignores the existing harness contracts. |

### Minimum complete scope

This is the minimum complete C1 slice. If any item below is skipped, the repo
still does not honestly prove compiled planning strategies.

1. root `PLAN.md`
2. [anvil/harness/types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py)
3. [anvil/harness/state.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/state.py)
4. [anvil/harness/strategy_graph.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/strategy_graph.py)
5. [anvil/harness/builder.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/builder.py)
6. [anvil/harness/nodes/validator_preflight.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py)
7. [anvil/harness/nodes/select_strategy.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/select_strategy.py)
8. [anvil/harness/nodes/write_artifacts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/write_artifacts.py)
9. [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py)
10. [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py)
11. [anvil/harness/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/cli.py)
12. [anvil/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/cli.py)
13. one new planning runtime module
14. one new planning subgraph module
15. strategy/task example fixtures under `examples/harness/`
16. targeted test additions under `tests/`
17. README / examples doc updates

### Complexity verdict

This milestone crosses more than 8 files. That is justified.

The C1 problem is not one missing helper.

It is a cross-cutting runtime-family addition that touches:

- task/strategy parsing
- preflight compatibility
- runtime routing
- graph construction
- state shape
- artifact publication
- CLI verdict handling
- fixture-backed tests

A smaller diff that only adds a new YAML example or a new subgraph file while
keeping task parsing, runtime routing, or artifact publication hard-coded will
create a fake C1.

What would be overbuilt:

- a public workflow DSL
- generic multi-strategy planning families beyond what this one wedge needs
- automatic branch/worktree orchestration
- phase-specific model optimization
- a broad rename of `summary_payload` or a generic executor-wide payload refactor
- touching orchestration/leadership surfaces outside the harness

### Search/build verdict

This is mostly a Layer 1 reuse milestone with one Layer 3 constraint.

Layer 1 reuse:

- keep `TaskSpec`, `StrategyConfig`, and structured YAML loading as the only config path
- keep `StrategyGraphSpec` as the strategy metadata authority
- keep `build_harness_langgraph(...)` as the only graph builder
- keep `HarnessLangGraphExecutor` as the only executor wrapper
- keep `publish_state_artifacts_v1(...)` as the write-artifacts entrypoint, but make it runtime-aware
- keep the existing CLI entrypoints and artifact-index pattern

Layer 3 rule:

- runtime family is not strategy name

That means the runtime must route on declared `runtime_target`, not on a one-off
check for `deterministic_feature_planning_v1`.

### TODOS cross-reference

[docs/project_management/future/TODOS.md](/Users/spensermcconnell/__Active_Code/forge/docs/project_management/future/TODOS.md) has no blocker for C1.

Nothing in the current TODO backlog should be bundled into this milestone. C1 is
already a big enough lake:

- compiled planning runtime
- planning artifacts
- deterministic IDs
- bounded fixture proof

If C1 uncovers later work, capture it after the wedge is green.

### Completeness verdict

The shortcut is:

- add a planning strategy YAML
- branch on its `kind` somewhere inside the runtime
- emit one pretty markdown plan
- skip schema, blocked-run payloads, stable IDs, and bounded fixture coverage

That is fake progress.

The complete C1 version must do all of this together:

- add a real planning task/strategy contract
- route through a shared `planning_v1` runtime family
- resolve policy objects generically
- execute declared phases generically
- emit `PLAN.md` and `plan.json`
- enforce blocked-run and success payload contracts
- prove determinism on a bounded fixture corpus
- preserve existing runtime families

### Distribution and DX verdict

Forge is a developer tool. C1 is incomplete if the new planning runtime only
works in unit tests.

C1 must preserve the documented harness surface:

```bash
poetry run python -m anvil.cli harness-run \
  --task <task.yaml> \
  --strategy <strategy.yaml> \
  --workspace <repo-root> \
  --out-root <artifacts-dir> \
  --json
```

Required C1 distribution behavior:

- planning strategy files live under `examples/harness/strategies/`
- planning task files live under `examples/harness/tasks/`
- artifacts land under the existing run directory surface
- JSON mode returns the planning terminal payload cleanly
- README and examples docs explain supported planning request classes

No new packaging, publishing, or installer work is required in C1. The existing
CLI distribution surface is the product surface.

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Task kind | add `planning` to `TaskSpec` and `HarnessState` | A feature-planning request is not an `analysis_review` task and should not inherit review-only defaults. |
| Strategy declaration surface | extend `StrategyConfig` with `runtime_target`, `phases[]`, and versioned policy refs | The wedge must be config-declared or it does not prove C1. |
| Runtime routing | route on `runtime_target: planning_v1`, not on `kind == deterministic_feature_planning_v1` | Runtime family must stay generic and future-proof. |
| Graph shape | add one `planning_v1` runtime node plus one generic post-runtime routing decision | Planning runs do not produce drafts and should not be forced through `select_best_draft`. |
| Post-runtime behavior | add a generic `post_runtime_action` or equivalent metadata to the strategy graph spec | Existing families still select drafts; planning goes directly to artifact publication. |
| Planning runtime implementation | one new shared planning runtime module plus one new `planning_v1` subgraph module | This is the smallest explicit boundary that keeps planning semantics out of analysis-review files. |
| Policy resolution | versioned policy lookup through shared runtime code | Policy behavior must be declarative, not hidden inside strategy-specific branches. |
| Artifact publication | keep `publish_state_artifacts_v1(...)` as the top-level write seam, but dispatch by runtime family internally | Minimal diff, one artifact entrypoint, clear runtime-specific projection helpers. |
| Terminal payload carrier | keep `state["summary_payload"]` as the executor-to-CLI payload field in C1, even for planning runs | Avoids a broad executor/CLI refactor in the same milestone while still allowing `plan.json` as the canonical on-disk artifact. |
| Planning artifact family | `PLAN.md` plus `plan.json` only | One canonical human artifact and one canonical machine artifact keeps the wedge honest. |
| Stop semantics | `success`, `clarification_needed`, and `failed` are planning terminal states | The runtime must distinguish honest clarification from hard failure. |
| CLI exit codes | `0` for `success`, `1` for `clarification_needed` or `failed`, `2` for invalid invocation/runtime errors | Matches the design doc and keeps operator behavior simple. |
| Workstream semantics | `worktree_recommended` is advisory metadata only | C1 outputs planning, not orchestration. |
| Model policy | one fixed planning model policy across all four planning phases in C1 | C1 proves compiled strategy first, not model-mix optimization. |

## Architecture Review

### Current blocker map

The current harness is still hard-coded at the runtime-family boundary.

```text
task.yaml + strategy.yaml
        │
        ▼
prepare_run
        │
        ▼
validator_preflight
        │
        ▼
select_strategy
        │
        ▼
route_after_strategy_selection(...)
        ├── single_pass
        ├── pfr_v1
        └── analysis_review_v1
                │
                ▼
        select_best_draft
                │
                ▼
        write_artifacts
                │
                ▼
             finalize
```

That shape cannot express C1 honestly because:

- planning does not fit `patch` or `analysis_review`
- planning needs declared phases, not fixed reviewer loops
- planning does not produce draft candidates that need ranking
- planning needs `PLAN.md` and `plan.json`, not the current summary/report/final-answer family

### Target architecture

```text
task.yaml (task_kind=planning)
strategy.yaml (runtime_target=planning_v1, declared phases, policy refs)
        │
        ▼
prepare_run
        │
        ▼
validator_preflight
        │
        ▼
select_strategy
        │
        ▼
build_strategy_graph_spec(...)
        │
        ▼
route_after_strategy_selection(...)
        ├── single_pass
        ├── pfr_v1
        ├── analysis_review_v1
        └── planning_v1
                │
                ▼
       planning phase registry
                │
                ├── rubric_design_doc
                ├── architecture_seam_decomposition
                ├── parallel_workstream_planning
                └── executable_slice_emission
                │
                ▼
       route_post_runtime(...)
                ├── select_best_draft     (existing families)
                └── write_artifacts       (planning)
                        │
                        ▼
                   finalize
```

### C1 source-of-truth table

| Concern | Canonical owner in C1 | Notes |
|---|---|---|
| Task kind and strategy declaration parsing | [anvil/harness/types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py) | One typed config surface for all harness families. |
| Runtime-family metadata | [anvil/harness/strategy_graph.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/strategy_graph.py) | `runtime_target`, declared phases, and post-runtime behavior live here. |
| Preflight compatibility and surface validation | [anvil/harness/nodes/validator_preflight.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py) | Planning incompatibilities fail before model work. |
| Shared graph construction | [anvil/harness/builder.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/builder.py) | One graph builder, one new planning node, one generic post-runtime route. |
| Planning phase execution and policy lookup | new `anvil/harness/planning_runtime.py` | Shared registry and executor helpers for the four planning phase types. |
| Planning subgraph entrypoint | new `anvil/harness/subgraphs/planning_v1.py` | Thin graph wrapper around the planning runtime helpers. |
| Runtime state and determinism counters | [anvil/harness/state.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/state.py) | Planning records, terminal state, counters, and artifact refs live here. |
| Planning artifact projection and publication | [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py) | Add planning publication helpers here, do not create a sidecar artifact writer. |
| Machine schema validation | [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py) | Add `plan_json` schema in the shared schema surface. |
| Operator-facing invocation and exit semantics | [anvil/harness/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/cli.py), [anvil/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/cli.py) | Existing CLI stays canonical. |

### Subsystem implementation plan

#### 1. Contract surface

Files:

- [anvil/harness/types.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py)
- [anvil/harness/state.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/state.py)
- [anvil/harness/nodes/validator_preflight.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py)

Required changes:

- Add `planning` to `VALID_TASK_KINDS`.
- Extend `TaskSpec.from_dict(...)` so `planning` is valid and does not inherit analysis-review-specific `review_requirements`.
- Extend `StrategyConfig` to carry:
  - `runtime_target`
  - `phases[]`
  - `artifact_policy`
  - `determinism_policy`
  - `discovery_policy`
  - `rubric_policy`
  - `stop_policy`
- Keep these keys optional for existing runtime families and required for `runtime_target: planning_v1`.
- Extend `HarnessState` with planning-native fields:
  - `planning_terminal_status`
  - `planning_stop_reason`
  - `clarification_requests`
  - `repo_evidence_refs`
  - `planning_seams`
  - `planning_workstreams`
  - `planning_slices`
  - `planning_phase_results`
  - `planning_policy_versions`
  - `search_pass_count`
  - `inspected_file_count`
  - `discovery_budget_escalated`
- Keep existing summary/reporting fields intact for current runtime families.
- In `validator_preflight_node(...)`:
  - forbid auto-fit between planning and non-planning runtime families
  - validate declared phase order
  - validate required planning policy refs
  - fail fast on unsupported `runtime_target`

#### 2. Runtime routing and graph construction

Files:

- [anvil/harness/strategy_graph.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/strategy_graph.py)
- [anvil/harness/builder.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/builder.py)
- [anvil/harness/nodes/select_strategy.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/nodes/select_strategy.py)

Required changes:

- Teach `build_strategy_graph_spec(...)` to build a planning spec from declared phases instead of a hard-coded strategy name.
- Add `runtime_target: planning_v1`.
- Add a generic field in the strategy graph spec for post-runtime behavior:
  - `post_runtime_action = select_best_draft` for existing families
  - `post_runtime_action = write_artifacts` for planning
- Keep `route_after_strategy_selection(...)` runtime-family based, not strategy-name based.
- Add one new node to `build_harness_langgraph(...)`: `planning_v1`.
- Add one generic route after runtime execution so planning bypasses `select_best_draft`.
- Keep existing families on the current route.

#### 3. Planning runtime and phase registry

Files:

- new `anvil/harness/planning_runtime.py`
- new `anvil/harness/subgraphs/planning_v1.py`

Required changes:

- Implement one registry for the four planning phase types:
  - `rubric_design_doc`
  - `architecture_seam_decomposition`
  - `parallel_workstream_planning`
  - `executable_slice_emission`
- Policy lookup must be versioned and generic.
- Every phase must accept and return shared planning state rather than phase-specific ad hoc payloads.
- The runtime must record:
  - evidence refs
  - stable IDs
  - dependency reasoning
  - ambiguity flags
  - clarification requests
  - deterministic counters
- The runtime must stop honestly when:
  - rubric coverage is insufficient
  - no trustworthy primary seam exists
  - dependency ambiguity blocks workstream planning
  - slice emission cannot map cleanly to seams/workstreams

#### 4. Artifact publication and CLI semantics

Files:

- [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py)
- [anvil/harness/artifacts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/artifacts.py)
- [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py)
- [anvil/harness/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/cli.py)
- [anvil/cli.py](/Users/spensermcconnell/__Active_Code/forge/anvil/cli.py)

Required changes:

- Keep `publish_state_artifacts_v1(...)` as the write node entrypoint, but dispatch internally on runtime family.
- Add:
  - `plan_projection_v1(...)`
  - `publish_planning_artifacts_v1(...)`
  - `render_plan_markdown_v1(...)`
- Planning publication must write:
  - `PLAN.md`
  - `plan.json`
- Planning publication must also populate:
  - `artifact_index["plan_md"]`
  - `artifact_index["plan_json"]`
  - `summary_payload = <plan_json payload>` for executor/CLI compatibility
- Add shared schema validation for `plan.json`.
- Update CLI summary printing and exit-code behavior for planning terminal states.

#### 5. Fixtures, docs, and proof corpus

Files:

- `examples/harness/strategies/`
- `examples/harness/tasks/`
- [README.md](/Users/spensermcconnell/__Active_Code/forge/README.md)
- [examples/README.md](/Users/spensermcconnell/__Active_Code/forge/examples/README.md)

Required changes:

- Add one canonical planning strategy example:
  - `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- Add a small bounded planning task fixture surface:
  - one success case
  - one clarification-needed case
  - one out-of-scope failure case
- Document supported request classes and CLI usage.
- Do not document public workflow composition or phase-specific model selection in C1 docs.

## Code Quality Review

### DRY and ownership rules

These are hard rules for C1 implementation, not soft preferences.

- One parser stack:
  - `TaskSpec.from_dict(...)`
  - `StrategyConfig.from_dict(...)`
- One runtime metadata builder:
  - `build_strategy_graph_spec(...)`
- One graph builder:
  - `build_harness_langgraph(...)`
- One planning runtime family:
  - `planning_v1`
- One write-artifacts entrypoint:
  - `publish_state_artifacts_v1(...)`
- One machine schema surface:
  - `anvil/harness/schemas.py`

Do not duplicate any of these with planning-only alternatives.

### Explicit-over-clever rules

- `runtime_target` is explicit config, not inferred from strategy name patterns.
- `phases[]` is explicit order, not synthesized from missing keys.
- `terminal_status` is explicit state, not inferred later from artifact presence.
- `worktree_recommended` is explicit advisory output, not an implicit side effect.
- Stable IDs must be computed in deterministic code, not left to model prose.

### Minimal-diff rules

- Do not rename `summary_payload` in C1. Keep it as the in-memory terminal payload carrier and document that planning reuses it for compatibility.
- Do not move existing analysis-review contract logic into the planning runtime.
- Do not add a second CLI command for planning. Extend `harness-run`.
- Do not make `select_best_draft_node(...)` understand planning. Route planning around it generically instead.

### New modules allowed

Exactly two new code modules are justified:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/subgraphs/planning_v1.py`

Anything beyond that needs a very strong reason because it likely means the
runtime is being abstracted before it is proven.

## Executable Slices

### Slice 1: Contract and routing foundation

- Goal: make planning a first-class harness family in config, state, and graph metadata
- Files:
  - `anvil/harness/types.py`
  - `anvil/harness/state.py`
  - `anvil/harness/strategy_graph.py`
  - `anvil/harness/nodes/validator_preflight.py`
  - `anvil/harness/nodes/select_strategy.py`
- Deliverables:
  - `planning` task kind
  - extended strategy declaration contract
  - planning-capable strategy graph spec
  - preflight validation for planning declarations
- Blocking dependencies: none
- Acceptance checks:
  - planning task/strategy files parse
  - invalid planning declarations fail at preflight
  - strategy graph spec serializes with `runtime_target: planning_v1`

### Slice 2: Planning runtime execution

- Goal: execute declared planning phases through a shared `planning_v1` runtime
- Files:
  - `anvil/harness/builder.py`
  - `anvil/harness/planning_runtime.py`
  - `anvil/harness/subgraphs/planning_v1.py`
- Deliverables:
  - mounted `planning_v1` node
  - phase registry
  - deterministic counters and stable ID helpers
  - honest stop behavior for clarification/failure
- Blocking dependencies:
  - Slice 1
- Acceptance checks:
  - planning strategy routes through `planning_v1`
  - successful runs emit seams/workstreams/slices in state
  - blocked runs emit clarification payloads without fake downstream records

### Slice 3: Artifact publication and CLI surfacing

- Goal: publish planning outputs as first-class harness artifacts
- Files:
  - `anvil/harness/reporting.py`
  - `anvil/harness/artifacts.py`
  - `anvil/harness/schemas.py`
  - `anvil/harness/cli.py`
  - `anvil/cli.py`
- Deliverables:
  - `PLAN.md`
  - `plan.json`
  - planning artifact-index entries
  - CLI verdict / exit-code updates
- Blocking dependencies:
  - Slice 1
  - Slice 2
- Acceptance checks:
  - `plan.json` passes schema validation
  - `PLAN.md` renders canonical sections
  - CLI JSON mode returns planning terminal payload
  - CLI exit code is `0` only for `success`

### Slice 4: Fixture corpus, docs, and regression proof

- Goal: prove C1 on a bounded corpus and document the supported surface
- Files:
  - `examples/harness/strategies/`
  - `examples/harness/tasks/`
  - `README.md`
  - `examples/README.md`
  - targeted tests under `tests/`
- Deliverables:
  - success fixture
  - clarification-needed fixture
  - failure fixture
  - updated docs
  - deterministic repeat-run proof
- Blocking dependencies:
  - Slices 1-3
- Acceptance checks:
  - three repeated runs preserve selected IDs on each fixture
  - docs match the shipped CLI surface
  - existing harness families still pass regression coverage

## Test Review

Framework: `pytest`

Primary existing coverage to extend:

- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_analysis_review_graph.py`

New coverage files that are justified:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`

### Code path coverage

```text
CODE PATH COVERAGE TO ADD
=========================
[+] Config parsing and preflight
    │
    ├── TaskSpec.from_dict(task_kind=planning)
    │   ├── [GAP] accepts valid planning task
    │   └── [GAP] rejects unsupported planning task shape
    │
    ├── StrategyConfig.from_dict(runtime_target=planning_v1, phases[])
    │   ├── [GAP] accepts valid planning declaration
    │   ├── [GAP] rejects missing policy refs
    │   └── [GAP] rejects invalid phase ordering
    │
    └── validator_preflight_node(...)
        ├── [GAP] planning + planning strategy passes
        ├── [GAP] planning + pfr_v1 fails without auto-fit rewrite
        └── [GAP] invalid runtime_target fails before model work

[+] Runtime routing
    │
    ├── build_strategy_graph_spec(...)
    │   ├── [GAP] emits runtime_target=planning_v1
    │   ├── [GAP] emits declared stages in canonical order
    │   └── [GAP] emits post_runtime_action=write_artifacts
    │
    └── build_harness_langgraph(...)
        ├── [GAP] mounts planning_v1 node
        ├── [GAP] routes planning runs around select_best_draft
        └── [GAP] preserves existing families unchanged

[+] Planning runtime
    │
    ├── rubric_design_doc
    │   ├── [GAP] pass case with bounded repo evidence
    │   └── [GAP] clarification_needed when required rubric fields are missing
    │
    ├── architecture_seam_decomposition
    │   ├── [GAP] primary seam selected with evidence refs
    │   └── [GAP] clarification_needed when no trustworthy seam exists
    │
    ├── parallel_workstream_planning
    │   ├── [GAP] emits dependency-aware workstreams
    │   └── [GAP] emits limited-parallelism explanation when split is not honest
    │
    └── executable_slice_emission
        ├── [GAP] emits slices with acceptance checks
        └── [GAP] fails honestly when slice boundary is incoherent

[+] Artifact publication
    │
    ├── publish_planning_artifacts_v1(...)
    │   ├── [GAP] writes PLAN.md
    │   ├── [GAP] writes plan.json
    │   ├── [GAP] sets artifact_index correctly
    │   └── [GAP] sets summary_payload to plan payload for CLI compatibility
    │
    └── plan.json schema
        ├── [GAP] success payload validation
        ├── [GAP] clarification payload validation
        └── [GAP] failed payload validation

[+] CLI and operator behavior
    │
    ├── harness-run --json for success
    ├── harness-run --json for clarification_needed
    ├── harness-run --json for failed
    ├── [GAP] exit code 0 only for success
    └── [GAP] printed summary includes PLAN.md and plan.json artifact refs

[+] Determinism proof
    │
    ├── [GAP] repeat-run stable seam IDs
    ├── [GAP] repeat-run stable workstream IDs
    ├── [GAP] repeat-run stable slice IDs
    └── [GAP] prose may vary, structure may not
```

### Test requirements to add to the plan

- Extend `tests/test_harness_strategy_graph.py` for planning graph spec emission.
- Extend `tests/test_harness_cli_command.py` and `tests/test_harness_standalone_cli.py` for planning exit-code and JSON behavior.
- Add `tests/test_harness_planning_graph.py` for end-to-end `HarnessLangGraphExecutor` planning runs.
- Add `tests/test_harness_planning_artifacts.py` for `PLAN.md` / `plan.json` publication and blocked-run payload shape.
- Add repeat-run determinism tests for the bounded fixture corpus.
- Extend `tests/test_harness_example_strategy_wiring.py` so examples/docs cannot drift from the planning strategy surface.

### Regression rule

If any existing harness family regresses because of planning runtime changes, add a
regression test in the existing relevant test file before merging C1.

That includes:

- strategy graph routing
- analysis-review artifact publication
- CLI summary printing
- state boundary compatibility

## Performance Review

### Discovery performance

The runtime must stay bounded.

Required defaults:

- small repo:
  - 2 search passes
  - 20 inspected files
- medium repo:
  - 3 search passes
  - 35 inspected files
- one justified escalation:
  - record `discovery_budget_escalated`
  - record `additional_files_inspected`
  - record `discovery_escalation_reason`

### State and checkpoint size

- Store evidence refs and metadata in state, not full file bodies.
- Keep `summary_payload` / plan payload machine-shaped and compact.
- Do not checkpoint giant raw repo scans.
- Keep repeated phase inputs derived from recorded evidence, not repeated full scans when possible.

### Stability over raw speed

The important performance bar in C1 is repeat-run stability, not minimum latency.

If a faster implementation weakens:

- stable IDs
- bounded discovery accounting
- honest clarification behavior

then the faster implementation is wrong.

### Caching opportunities

- cache normalized evidence refs per inspected file path within one run
- cache deterministic ID inputs after seam ranking
- do not rerender unchanged planning sections twice during one publication pass

## Failure Modes Registry

| New codepath | Realistic production failure | Test covers it? | Error handling exists? | User-visible outcome | Status |
|---|---|---:|---:|---|---|
| planning task parse | user provides `task_kind: planning` but missing required workspace policy | must add | must add | clear invalid-config error before model work | required |
| planning strategy parse | strategy declares `runtime_target: planning_v1` but omits `phases[]` | must add | must add | clear invalid-config error | required |
| planning runtime routing | graph routes planning run to `write_artifacts` without running phases | must add | must add | empty fake plan or malformed payload if unguarded | critical gap until covered |
| rubric gate | design-doc phase passes without repo evidence | must add | must add | misleading success with fake seams | critical gap until covered |
| seam decomposition | two primary seams are tied and the runtime picks one nondeterministically | must add | must add | unstable IDs across repeated runs | critical gap until covered |
| parallel planning | workstreams emitted with circular dependencies | must add | must add | unusable worktree advice | required |
| slice emission | slice points to seam/workstream IDs that do not exist | must add | must add | invalid `plan.json` and broken markdown | critical gap until covered |
| plan publication | `PLAN.md` and `plan.json` disagree on selected workstream order | must add | must add | operator mistrust, impossible review | critical gap until covered |
| CLI exit handling | `clarification_needed` exits `0` | must add | must add | automation falsely treats blocked planning as success | critical gap until covered |

Any row with "must add" in both the test and error-handling columns is a merge
blocker until the plan covers it and the implementation adds it.

## NOT in scope

- Public custom workflow DSL
  - Rationale: C1 proves one curated compiled strategy first.
- Automatic worktree, branch, or agent orchestration
  - Rationale: C1 outputs advisory planning metadata only.
- Phase-specific model selection
  - Rationale: model-mix optimization is a later milestone, not required for the compiler proof.
- Cross-repo or multi-team planning
  - Rationale: the supported corpus stays repo-local and bounded.
- Replacing analysis-review artifact contracts
  - Rationale: current families must remain stable while planning lands.
- Renaming `summary_payload` across the executor/CLI stack
  - Rationale: that is worthwhile cleanup later, but it is not part of the C1 proof.
- Generic planning strategy family beyond what this one wedge needs
  - Rationale: do not abstract for the second strategy before the first is proven.

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Contract + routing freeze | `anvil/harness/types.py`, `anvil/harness/state.py`, `anvil/harness/strategy_graph.py`, `anvil/harness/nodes/` | — |
| B. Planning runtime implementation | `anvil/harness/subgraphs/`, new planning runtime module | A |
| C. Artifact + CLI publication | `anvil/harness/reporting.py`, `anvil/harness/artifacts.py`, `anvil/harness/schemas.py`, `anvil/harness/cli.py`, `anvil/cli.py` | A |
| D. Fixtures + deterministic regression coverage | `examples/harness/`, `tests/` | A, B, C |
| E. Docs polish and final plan/demo alignment | `README.md`, `examples/README.md`, repo root plan/docs surface | D |

### Parallel lanes

Lane A: contract + routing freeze  
Sequential, foundation lane.  
Shared modules:

- `anvil/harness/types.py`
- `anvil/harness/state.py`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/nodes/validator_preflight.py`

Lane B: planning runtime  
Starts after Lane A freezes planning state keys, declared phase shape, and runtime metadata.  
Shared modules:

- `anvil/harness/subgraphs/`
- new planning runtime module

Lane C: planning artifacts + CLI  
Starts after Lane A freezes planning terminal payload shape and post-runtime routing.  
Shared modules:

- `anvil/harness/reporting.py`
- `anvil/harness/schemas.py`
- CLI surfaces

Lane D: fixtures + regression proof  
Starts after Lane B and Lane C freeze:

- phase outputs
- artifact names
- exit semantics

Lane E: docs and final surface alignment  
Runs last after D proves the shipped surface.

### Execution order

```text
Lane A
  │
  ├──────────────► Lane B
  │
  └──────────────► Lane C
                     │
           Lane B + Lane C complete
                     │
                     ▼
                   Lane D
                     │
                     ▼
                   Lane E
```

1. Launch Lane A first and merge it.
2. Launch Lane B and Lane C in parallel worktrees after A freezes the contract.
3. Merge B and C.
4. Run Lane D after both runtime behavior and artifact shapes are frozen.
5. Run Lane E last so docs describe the actual shipped surface, not a guessed one.

### Conflict flags

- Lanes A, B, and C all depend on the exact planning state shape. B and C must not start before A freezes it.
- Lanes B and C both depend on runtime terminal payload semantics. If either changes `summary_payload` structure late, Lane D will churn.
- Lanes C and D both touch examples and output names. Keep artifact filenames frozen before D starts.
- Lane E touches the same docs surfaces that D validates. E must be last.

## Acceptance Checklist

- [ ] `TaskSpec` accepts `task_kind: planning`
- [ ] `StrategyConfig` accepts declared planning phase and policy fields
- [ ] `validator_preflight_node(...)` rejects invalid planning declarations before model work
- [ ] `build_strategy_graph_spec(...)` emits `runtime_target: planning_v1`
- [ ] the strategy graph spec serializes declared planning phases in canonical order
- [ ] `build_harness_langgraph(...)` mounts `planning_v1`
- [ ] planning runs bypass `select_best_draft` through a generic post-runtime route
- [ ] the planning runtime executes four declared phases in order
- [ ] blocked runs emit structured clarification requests
- [ ] failed runs emit explicit `stop_reason`
- [ ] successful runs emit `PLAN.md`
- [ ] successful runs emit `plan.json`
- [ ] `plan.json` passes schema validation
- [ ] `summary_payload` contains the planning terminal payload for CLI compatibility
- [ ] CLI JSON mode returns the planning payload
- [ ] CLI exit code is `0` only for `success`
- [ ] example planning strategy and task files exist and are runnable
- [ ] repeat-run determinism tests pass for the bounded fixture corpus
- [ ] existing `single_pass`, `pfr_v1`, and `analysis_review_*` tests stay green

## Completion Summary

- Step 0: Scope Challenge — scope accepted with one explicit architectural addition: a real `planning` task family
- Architecture Review: locked around one new `planning_v1` runtime family, one shared planning runtime module, and one generic post-runtime route
- Code Quality Review: DRY authority map locked, no second parser stack, no second graph builder, no per-strategy core-engine branch
- Test Review: full planning coverage diagram produced, all new codepaths mapped to required tests
- Performance Review: bounded discovery counters and repeat-run stability are mandatory, not nice-to-have
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none bundled into C1
- Failure modes: nine concrete failure modes identified, four are critical gaps until test and stop behavior land
- Parallelization: 5 steps total, 2 middle lanes can run in parallel after the contract freeze
- Lake Score: choose the complete compiler/runtime proof, not the markdown-only shortcut
