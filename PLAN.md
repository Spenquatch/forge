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

C1 is the first honest proof that `forge` can compile and execute a planning
strategy, not just a review or repair strategy.

Today the harness only ships three runtime families:

- `single_pass`
- `pfr_v1`
- `analysis_review_v1`

That is enough to prove graph-owned execution, but not enough to prove the next
claim: a new strategy can be declared in config, routed through shared graph
machinery, and produce a stable artifact package without strategy-specific core
engine branches.

C1 adds exactly one new runtime family, `planning_v1`, and exactly one curated
strategy, `deterministic_feature_planning_v1`. The supported input is narrow on
purpose: one feature request in one or two sentences. The supported output is
also narrow on purpose: one deterministic planning package consisting of
`PLAN.md` and `plan.json`, or an honest blocked/failed terminal result when the
request cannot be completed credibly.

This milestone is not a public workflow DSL. It is not automatic worktree
dispatch. It is not a generic backlog generator. It is the smallest complete
compiler/runtime proof that moves `forge` from "hard-coded execution harness" to
"shared harness that can host a compiled planning strategy."

## 1. Scope, Constraints, and Success

### 1.1 Objective

Ship one repo-declared planning strategy that:

- loads through the existing harness config path
- routes through a shared `planning_v1` runtime family
- executes four declared planning phases in order
- emits deterministic planning artifacts on success
- emits explicit clarification or failure payloads when it cannot proceed
- preserves existing behavior for all non-planning harness families

### 1.2 Preconditions

- B3 is already landed on `main`. C1 builds on the graph-owned harness surface as
  it exists now.
- The planning wedge stays curated and internal in C1. No user-authored workflow
  composition.
- The documented operator surface remains:

```bash
poetry run python -m anvil.cli harness-run \
  --task <task.yaml> \
  --strategy <strategy.yaml> \
  --workspace <repo-root> \
  --out-root <artifacts-dir> \
  --json
```

- No second parser stack. Task and strategy declarations must still load through
  the existing structured-file and typed-config surfaces.
- No automatic worktree, branch, job, or agent dispatch. Parallelization output
  is advisory metadata only.

### 1.3 Non-Negotiables

- `planning_v1` is a real runtime family, not a disguised branch inside
  `analysis_review_v1`.
- `deterministic_feature_planning_v1` must run without strategy-specific
  core-engine edits for that strategy name.
- Runtime routing must key off `runtime_target`, not off special-casing
  `kind == deterministic_feature_planning_v1`.
- Existing strategy kinds keep working:
  - `single_pass`
  - `pfr_v1`
  - `analysis_review_bounded_v1`
  - `analysis_review_trust_v1`
- Existing runtime targets keep working:
  - `single_pass`
  - `pfr_v1`
  - `analysis_review_v1`
- Planning artifacts must be deterministic in structure, IDs, and stop behavior
  across the bounded fixture corpus.

### 1.4 Success Criteria

- A strategy declaration with `kind: deterministic_feature_planning_v1` and
  `runtime_target: planning_v1` loads through the existing harness config path.
- Planning runs route through a shared `planning_v1` path without hard-coding
  logic for this one strategy name.
- The planning runtime executes these four phases in canonical order:
  - `rubric_design_doc`
  - `architecture_seam_decomposition`
  - `parallel_workstream_planning`
  - `executable_slice_emission`
- Successful runs emit:
  - `PLAN.md`
  - `plan.json`
  - `artifact_index["plan_md"]`
  - `artifact_index["plan_json"]`
  - `summary_payload` populated with the canonical `plan.json` payload
- Blocked runs emit:
  - `terminal_status: clarification_needed`
  - non-empty `clarification_requests[]`
- Failed runs emit:
  - `terminal_status: failed`
  - non-empty `stop_reason`
- `PLAN.md` renders the same five top-level sections in canonical order:
  - problem statement
  - rubric results
  - architectural seams
  - parallel workstreams/worktrees
  - executable slices
- `plan.json` passes schema validation and preserves selected seam/workstream/slice
  IDs across three repeated runs per fixture.
- The bounded fixture corpus proves both classes of honest outcomes:
  - at least one successful planning run
  - at least one clarification-needed planning run
- Existing non-planning harness tests stay green.

## 2. Step 0: Scope Challenge

### 2.1 What Already Exists

| Sub-problem | Existing code | C1 decision |
|---|---|---|
| Typed task parsing exists, but only for patch and review tasks | `anvil/harness/types.py` accepts `patch` and `analysis_review` in `VALID_TASK_KINDS` | Extend the existing task surface with `planning`. Do not overload `analysis_review` for feature-planning requests. |
| Typed strategy parsing exists, but planning fields do not | `StrategyConfig` already loads `kind`, `roles`, validators, loops, focus-gate, and trust-review fields | Extend `StrategyConfig` with generic planning keys: `runtime_target`, `phases[]`, `artifact_policy`, `determinism_policy`, `discovery_policy`, `rubric_policy`, and `stop_policy`. Keep one loader. |
| Strategy graph metadata already exists | `anvil/harness/strategy_graph.py` builds structured specs for `single_pass`, `pfr_v1`, and `analysis_review_*` | Reuse this file as the canonical strategy-to-runtime metadata builder. Add `planning_v1` and one generic post-runtime routing field. |
| The shared graph wrapper already exists | `anvil/harness/builder.py` owns LangGraph construction, shared nodes, and runtime routing | Keep one graph builder. Add one `planning_v1` node and one generic post-runtime route. |
| Preflight compatibility checks already exist | `anvil/harness/nodes/validator_preflight.py` already validates and auto-fits current task/strategy combinations | Extend preflight to validate planning task and planning strategy compatibility explicitly. Do not let auto-fit rewrite planning into review or patch flows. |
| Artifact publication already has a single seam | `anvil/harness/reporting.py`, `anvil/harness/artifacts.py`, and `anvil/harness/nodes/write_artifacts.py` already own publication and run-directory handling | Reuse those modules. Add planning-specific projection and publication functions inside the shared artifact path. |
| CLI entrypoints already exist | `anvil/harness/cli.py` and `anvil/cli.py` already expose `harness-run` and JSON mode | Keep those entrypoints. Extend summary printing and exit semantics for planning verdicts. |
| Regression coverage already exists around graph, CLI, examples, and artifacts | `tests/test_harness_strategy_graph.py`, `tests/test_harness_example_strategy_wiring.py`, `tests/test_harness_cli_command.py`, `tests/test_harness_standalone_cli.py`, `tests/test_harness_reporting.py` | Extend the existing suite. Add only the minimum new planning-specific test files justified by the new runtime family. |

### 2.2 Minimum Complete Scope

If any item below is skipped, C1 does not prove compiled planning honestly.

1. Extend the task contract in `anvil/harness/types.py`.
2. Extend graph-owned planning state in `anvil/harness/state.py`.
3. Extend runtime metadata in `anvil/harness/strategy_graph.py`.
4. Extend preflight compatibility in `anvil/harness/nodes/validator_preflight.py`.
5. Mount and route `planning_v1` in `anvil/harness/builder.py`.
6. Add one shared planning runtime module.
7. Add one `planning_v1` subgraph entrypoint.
8. Extend shared artifact publication and schema validation.
9. Extend CLI verdict handling and JSON output.
10. Add planning strategy/task examples under `examples/harness/`.
11. Add bounded planning regression coverage under `tests/`.
12. Update README/examples docs to describe the shipped planning surface.

### 2.3 Complexity Verdict

This milestone spans more than eight files. That is justified.

The diff is cross-cutting because the change is cross-cutting:

- task parsing
- strategy parsing
- preflight compatibility
- runtime-family routing
- graph construction
- graph-owned state
- artifact projection
- schema validation
- CLI semantics
- example fixtures
- deterministic regression tests

What would be overbuilt:

- a public workflow DSL
- generic multi-strategy planning families beyond what this wedge needs
- automatic branch/worktree orchestration
- phase-specific model optimization
- a broad `summary_payload` refactor across executor and CLI
- touching orchestration or leadership surfaces outside the harness

### 2.4 Search/Build Verdict

This is primarily a Layer 1 reuse milestone with one Layer 3 rule.

Layer 1 reuse:

- keep `TaskSpec.from_dict(...)` and `StrategyConfig.from_dict(...)` as the only
  config parsers
- keep `build_strategy_graph_spec(...)` as the strategy metadata authority
- keep `build_harness_langgraph(...)` as the only graph builder
- keep `publish_state_artifacts_v1(...)` as the top-level artifact seam
- keep `harness-run` as the only CLI entrypoint for this feature

Layer 3 rule:

- runtime family must not equal strategy name

That is the core architecture constraint for C1.

### 2.5 Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Task kind | add `planning` to `TaskSpec` and `HarnessState` | A feature-planning request is not an `analysis_review` task. |
| Strategy declaration surface | extend `StrategyConfig` with `runtime_target`, `phases[]`, and policy refs | The wedge must be config-declared or it does not prove C1. |
| Runtime routing | route on `runtime_target: planning_v1`, not on strategy name | Runtime family must stay generic and future-proof. |
| Graph shape | add one `planning_v1` runtime node plus one generic post-runtime route | Planning does not produce ranked draft candidates. |
| Post-runtime behavior | add `post_runtime_action` metadata to the strategy graph spec | Existing families still select drafts; planning publishes directly. |
| Planning implementation boundary | exactly one shared planning runtime module plus one `planning_v1` subgraph module | Smallest explicit seam that keeps planning semantics out of analysis-review files. |
| Artifact publication | keep `publish_state_artifacts_v1(...)` as the top-level write seam | Minimal diff, one artifact entrypoint, runtime-aware internals. |
| Terminal payload carrier | keep `state["summary_payload"]` for planning too | Avoids a broad executor/CLI refactor in the same milestone. |
| Planning artifact family | `PLAN.md` plus `plan.json` only | One human artifact and one machine artifact keeps the wedge honest. |
| Terminal states | `success`, `clarification_needed`, `failed` | The runtime must distinguish honest clarification from hard failure. |
| CLI exit codes | `0` for `success`, `1` for `clarification_needed` and `failed`, `2` for invalid invocation/runtime errors | Simple operator contract. |
| Workstream semantics | `worktree_recommended` is advisory metadata only | C1 outputs planning, not orchestration. |
| Model policy | one fixed planning model policy for all four phases in C1 | C1 proves compiled strategy first, not model-mix optimization. |

### 2.6 NOT in Scope

- Public custom workflow DSL
  - Rationale: C1 proves one curated compiled strategy first.
- Automatic worktree, branch, or agent orchestration
  - Rationale: C1 outputs advisory planning metadata only.
- Phase-specific model selection
  - Rationale: model-mix optimization is a later milestone.
- Cross-repo or multi-team planning
  - Rationale: the supported corpus stays repo-local and bounded.
- Replacing analysis-review artifact contracts
  - Rationale: current families must remain stable while planning lands.
- Renaming `summary_payload` across the executor/CLI stack
  - Rationale: worthwhile cleanup later, not part of the C1 proof.
- Generic planning strategy family beyond what this wedge needs
  - Rationale: do not abstract for the second strategy before the first is proven.

### 2.7 TODO Cross-Reference

`docs/project_management/future/TODOS.md` contains no blocker that should be
bundled into C1. This milestone is already a complete lake:

- compiled planning runtime
- planning artifacts
- deterministic IDs
- bounded fixture proof

If C1 uncovers follow-on work, capture it after the wedge is green.

## 3. Architecture Plan

### 3.1 Current Shape

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

This shape cannot express C1 honestly because planning:

- does not fit `patch` or `analysis_review`
- needs declared phases, not fixed reviewer loops
- does not produce ranked draft candidates
- needs `PLAN.md` and `plan.json`, not the current summary/report-only family

### 3.2 Target Shape

```text
task.yaml (task_kind=planning)
strategy.yaml (runtime_target=planning_v1, phases[], policy refs)
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
                ├── select_best_draft   (existing families)
                └── write_artifacts     (planning)
                        │
                        ▼
                     finalize
```

### 3.3 Source-of-Truth Ownership Map

| Concern | Canonical owner in C1 | Required outcome |
|---|---|---|
| Task kind and strategy declaration parsing | `anvil/harness/types.py` | One typed config surface for all harness families. |
| Runtime-family metadata | `anvil/harness/strategy_graph.py` | `runtime_target`, declared phases, and `post_runtime_action` are encoded here. |
| Preflight compatibility | `anvil/harness/nodes/validator_preflight.py` | Planning incompatibilities fail before model work. |
| Shared graph construction | `anvil/harness/builder.py` | One graph builder, one new planning node, one generic post-runtime route. |
| Planning phase execution and policy lookup | `anvil/harness/planning_runtime.py` | Shared registry and executor helpers for the four planning phase types. |
| Planning runtime entrypoint | `anvil/harness/subgraphs/planning_v1.py` | Thin subgraph wrapper around the planning runtime. |
| Graph-owned planning state | `anvil/harness/state.py` | Planning records, terminal state, counters, and artifact refs live here. |
| Artifact projection and publication | `anvil/harness/reporting.py` | Planning projection and publication live beside existing artifact logic. |
| Machine schema validation | `anvil/harness/schemas.py` | `plan.json` validation lives in the shared schema surface. |
| Operator-facing invocation | `anvil/harness/cli.py`, `anvil/cli.py` | Existing CLI stays canonical. |

### 3.4 Planning Contract

#### Strategy declaration contract

Minimum declaration keys:

- `kind`
- `runtime_target`
- `phases[]`
- `artifact_policy`
- `determinism_policy`
- `discovery_policy`
- `rubric_policy`
- `stop_policy`

Canonical C1 example:

```yaml
kind: deterministic_feature_planning_v1
runtime_target: planning_v1
phases:
  - id: design_doc
    stage_type: rubric_design_doc
  - id: seam_decomposition
    stage_type: architecture_seam_decomposition
  - id: parallel_planning
    stage_type: parallel_workstream_planning
  - id: slice_emission
    stage_type: executable_slice_emission
artifact_policy: planning_package_v1
determinism_policy: stable_structure_v1
discovery_policy: bounded_repo_scan_v1
rubric_policy: design_doc_gate_v1
stop_policy: clarification_or_stop_v1
```

Compiler responsibility:

- interpret `phases[]` generically
- bind each `stage_type` through a shared planning-stage registry
- enforce declared policy objects without strategy-specific runtime branches

#### Runtime state contract

Planning state additions in `HarnessState` must cover:

- terminal outcome
- stop reason
- clarification requests
- repo evidence refs
- seams
- workstreams
- slices
- per-phase results
- policy versions
- discovery counters
- determinism counters

Canonical field set for C1:

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

Existing summary/reporting fields stay intact for current runtime families.

#### Artifact contract

Successful planning publication writes:

- `PLAN.md`
- `plan.json`

It also populates:

- `artifact_index["plan_md"]`
- `artifact_index["plan_json"]`
- `summary_payload = <plan_json payload>`

Blocked and failed runs still publish a machine-verifiable terminal payload through
`summary_payload`, even when the human artifact package is partial or absent.

#### Canonical PLAN.md contract

Every generated planning artifact must render these sections in this order:

1. problem statement
2. rubric results
3. architectural seams
4. parallel workstreams/worktrees
5. executable slices

That section order is part of the determinism contract.

## 4. Implementation Plan

### Slice 1: Contract and Routing Foundation

Goal: make planning a first-class harness family in config, state, and graph metadata.

Files:

- `anvil/harness/types.py`
- `anvil/harness/state.py`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/nodes/validator_preflight.py`
- `anvil/harness/nodes/select_strategy.py`

Required work:

- add `planning` to `VALID_TASK_KINDS`
- extend `TaskSpec.from_dict(...)` so planning does not inherit review-only defaults
- extend `StrategyConfig` with planning-specific contract keys
- require those keys when `runtime_target == planning_v1`
- teach strategy graph spec generation to emit planning runtime metadata
- add generic `post_runtime_action` support
- forbid planning/non-planning auto-fit in preflight
- validate phase order and required policy refs in preflight

Acceptance checks:

- planning task files parse
- planning strategy files parse
- invalid planning declarations fail at preflight
- strategy graph spec serializes with `runtime_target: planning_v1`
- strategy graph spec serializes declared planning phases in canonical order

### Slice 2: Planning Runtime Execution

Goal: execute declared planning phases through a shared `planning_v1` runtime family.

Files:

- `anvil/harness/builder.py`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/subgraphs/planning_v1.py`

Required work:

- mount `planning_v1` in the shared LangGraph
- add a generic post-runtime route so planning bypasses `select_best_draft`
- implement the shared planning phase registry for:
  - `rubric_design_doc`
  - `architecture_seam_decomposition`
  - `parallel_workstream_planning`
  - `executable_slice_emission`
- implement versioned policy lookup
- record evidence refs, dependency reasoning, ambiguity flags, stable IDs, and
  determinism counters in graph-owned state
- stop honestly when the request cannot support a credible plan

Acceptance checks:

- planning strategies route through `planning_v1`
- successful runs populate seams, workstreams, and slices in state
- clarification-needed runs stop without fake downstream records
- failed runs emit explicit `planning_stop_reason`

### Slice 3: Artifact Publication and CLI Surfacing

Goal: publish planning outputs as first-class harness artifacts.

Files:

- `anvil/harness/reporting.py`
- `anvil/harness/artifacts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/cli.py`
- `anvil/cli.py`

Required work:

- keep `publish_state_artifacts_v1(...)` as the write node entrypoint
- dispatch publication internally on runtime family
- add:
  - `plan_projection_v1(...)`
  - `publish_planning_artifacts_v1(...)`
  - `render_plan_markdown_v1(...)`
- validate `plan.json` through the shared schema surface
- update CLI JSON and human-readable output for planning terminal states
- enforce exit-code semantics

Acceptance checks:

- `PLAN.md` is written on successful runs
- `plan.json` is written on successful runs
- `artifact_index` is populated correctly
- `summary_payload` contains the planning terminal payload
- CLI JSON mode returns the planning payload
- CLI exit code is `0` only for `success`

### Slice 4: Fixture Corpus, Docs, and Regression Proof

Goal: prove the feature on a bounded corpus and document the shipped surface.

Files:

- `examples/harness/strategies/`
- `examples/harness/tasks/`
- `tests/`
- `README.md`
- `examples/README.md`

Required work:

- add one canonical planning strategy example:
  - `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- add three canonical planning task fixtures:
  - one success case
  - one clarification-needed case
  - one hard-failure case
- add deterministic repeat-run proof for the bounded corpus
- update docs to describe supported planning request classes and CLI usage
- keep docs strictly aligned to the shipped surface, not the aspirational surface

Acceptance checks:

- repeated runs preserve selected seam IDs
- repeated runs preserve selected workstream IDs
- repeated runs preserve selected slice IDs
- docs match the real CLI surface
- existing non-planning harness tests stay green

## 5. Code Quality Rules

### 5.1 DRY and Ownership Rules

These are hard rules for C1 implementation, not soft preferences.

- one parser stack:
  - `TaskSpec.from_dict(...)`
  - `StrategyConfig.from_dict(...)`
- one runtime metadata builder:
  - `build_strategy_graph_spec(...)`
- one graph builder:
  - `build_harness_langgraph(...)`
- one planning runtime family:
  - `planning_v1`
- one write-artifacts entrypoint:
  - `publish_state_artifacts_v1(...)`
- one machine schema surface:
  - `anvil/harness/schemas.py`

Do not create planning-only duplicates of any of those seams.

### 5.2 Explicit-over-Clever Rules

- `runtime_target` is explicit config, not inferred from strategy-name patterns.
- `phases[]` is explicit order, not synthesized from partial config.
- `terminal_status` is explicit state, not inferred later from artifact presence.
- `worktree_recommended` is explicit advisory output, not an implicit side effect.
- Stable IDs are computed in deterministic code, not copied from model prose.

### 5.3 Minimal-Diff Rules

- Do not rename `summary_payload` in C1.
- Do not move existing analysis-review contract logic into the planning runtime.
- Do not add a second CLI command for planning.
- Do not teach `select_best_draft_node(...)` about planning. Planning must route
  around it generically.

### 5.4 New Modules Allowed

Exactly two new production modules are justified:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/subgraphs/planning_v1.py`

Anything beyond that is a smell unless a concrete implementation blocker proves
otherwise.

## 6. Test Plan

Framework: `pytest`

Primary existing coverage to extend:

- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_analysis_review_graph.py`

New planning-specific test files that are justified:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`

### 6.1 Code Path Coverage

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
        ├── [GAP] routes planning around select_best_draft
        └── [GAP] preserves existing families unchanged

[+] Planning runtime
    │
    ├── rubric_design_doc
    │   ├── [GAP] pass case with bounded repo evidence
    │   └── [GAP] clarification_needed when rubric evidence is insufficient
    │
    ├── architecture_seam_decomposition
    │   ├── [GAP] primary seam selected with evidence refs
    │   └── [GAP] clarification_needed when no trustworthy seam exists
    │
    ├── parallel_workstream_planning
    │   ├── [GAP] emits dependency-aware workstreams
    │   └── [GAP] emits limited-parallelism explanation when a split is not honest
    │
    └── executable_slice_emission
        ├── [GAP] emits slices with acceptance checks
        └── [GAP] fails honestly when slice boundaries are incoherent

[+] Artifact publication
    │
    ├── publish_planning_artifacts_v1(...)
    │   ├── [GAP] writes PLAN.md
    │   ├── [GAP] writes plan.json
    │   ├── [GAP] sets artifact_index correctly
    │   └── [GAP] sets summary_payload for CLI compatibility
    │
    └── plan.json schema
        ├── [GAP] success payload validation
        ├── [GAP] clarification payload validation
        └── [GAP] failed payload validation

[+] CLI and operator behavior
    │
    ├── [GAP] harness-run --json for success
    ├── [GAP] harness-run --json for clarification_needed
    ├── [GAP] harness-run --json for failed
    ├── [GAP] exit code 0 only for success
    └── [GAP] printed summary includes PLAN.md and plan.json artifact refs

[+] Determinism proof
    │
    ├── [GAP] repeat-run stable seam IDs
    ├── [GAP] repeat-run stable workstream IDs
    ├── [GAP] repeat-run stable slice IDs
    └── [GAP] prose may vary, structure may not
```

### 6.2 Operator Flow Coverage

```text
OPERATOR FLOW COVERAGE
======================
[+] Successful planning run
    │
    ├── task + strategy load
    ├── planning runtime executes all four phases
    ├── PLAN.md + plan.json are published
    └── CLI returns exit 0 with machine payload

[+] Clarification-needed run
    │
    ├── request is parseable but under-specified
    ├── runtime halts at the first dishonest phase boundary
    ├── clarification_requests[] is populated
    └── CLI returns non-zero without pretending success

[+] Failed run
    │
    ├── request or strategy reaches an unrecoverable invalid state
    ├── stop_reason is explicit
    └── automation can distinguish failure from clarification_needed
```

### 6.3 Required Test Additions

- Extend `tests/test_harness_strategy_graph.py` for planning graph spec emission.
- Extend `tests/test_harness_cli_command.py` and
  `tests/test_harness_standalone_cli.py` for planning exit-code and JSON behavior.
- Add `tests/test_harness_planning_graph.py` for end-to-end planning runtime runs
  through `HarnessLangGraphExecutor`.
- Add `tests/test_harness_planning_artifacts.py` for `PLAN.md` / `plan.json`
  publication and blocked/failure payload shape.
- Add repeat-run determinism tests for the bounded fixture corpus.
- Extend `tests/test_harness_example_strategy_wiring.py` so examples and docs
  cannot drift from the planning strategy surface.

### 6.4 Regression Rule

If any existing harness family regresses because of planning-runtime changes,
add a regression test in the existing relevant test file before merging C1.

That includes:

- strategy graph routing
- analysis-review artifact publication
- CLI summary printing
- state boundary compatibility

## 7. Performance and Determinism

### 7.1 Discovery Budget

The planning runtime must stay bounded.

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

### 7.2 State and Checkpoint Size

- Store evidence refs and metadata in state, not full file bodies.
- Keep `summary_payload` machine-shaped and compact.
- Do not checkpoint giant raw repo scans.
- Reuse recorded evidence between phases when possible instead of rescanning the
  same file bodies.

### 7.3 Stability Over Raw Speed

The C1 performance bar is repeat-run stability, not minimum latency.

If a faster implementation weakens:

- stable IDs
- bounded discovery accounting
- honest clarification behavior

then the faster implementation is wrong.

### 7.4 Local Caching Opportunities

- cache normalized evidence refs per inspected file path within one run
- cache deterministic ID inputs after seam ranking
- do not rerender unchanged planning sections twice during one publication pass

## 8. Failure Modes Registry

| New codepath | Realistic production failure | Test covers it? | Error handling exists? | User-visible outcome | Status |
|---|---|---:|---:|---|---|
| planning task parse | user provides `task_kind: planning` but omits required planning-task fields | must add | must add | clear invalid-config error before model work | required |
| planning strategy parse | strategy declares `runtime_target: planning_v1` but omits `phases[]` | must add | must add | clear invalid-config error | required |
| planning runtime routing | graph routes planning directly to artifact publication without running phases | must add | must add | empty fake plan or malformed payload if unguarded | critical gap until covered |
| rubric gate | design-doc phase passes without enough repo evidence | must add | must add | misleading success with fake seams | critical gap until covered |
| seam decomposition | two primary seams tie and the runtime picks one nondeterministically | must add | must add | unstable IDs across repeated runs | critical gap until covered |
| parallel planning | workstreams emit circular dependencies | must add | must add | unusable worktree advice | required |
| slice emission | slice references seam/workstream IDs that do not exist | must add | must add | invalid `plan.json` and broken markdown | critical gap until covered |
| plan publication | `PLAN.md` and `plan.json` disagree on selected workstream order | must add | must add | operator mistrust and broken review | critical gap until covered |
| CLI exit handling | `clarification_needed` exits `0` | must add | must add | automation falsely treats blocked planning as success | critical gap until covered |

Any row with "must add" in both the test and error-handling columns is a merge
blocker until the implementation covers it.

## 9. Worktree Parallelization Strategy

### 9.1 Dependency Table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Contract and routing freeze | `anvil/harness/types.py`, `anvil/harness/state.py`, `anvil/harness/strategy_graph.py`, `anvil/harness/nodes/` | — |
| B. Planning runtime execution | `anvil/harness/subgraphs/`, `anvil/harness/planning_runtime.py`, graph runtime wiring in `anvil/harness/builder.py` | A |
| C. Artifact and CLI surfacing | `anvil/harness/reporting.py`, `anvil/harness/artifacts.py`, `anvil/harness/schemas.py`, `anvil/harness/cli.py`, `anvil/cli.py` | A |
| D. Fixtures and deterministic regression proof | `examples/harness/`, `tests/` | A, B, C |
| E. Docs and final plan/demo alignment | `README.md`, `examples/README.md`, root planning/docs surface | D |

### 9.2 Parallel Lanes

Lane A: contract and routing freeze  
Sequential foundation lane. This lane freezes the planning task kind, strategy
shape, graph metadata, preflight semantics, and post-runtime routing contract.

Lane B: planning runtime execution  
Starts only after Lane A lands. This lane owns the planning phase registry,
terminal-state behavior, deterministic IDs, and runtime-state mutation.

Lane C: artifact and CLI surfacing  
Starts only after Lane A lands. This lane owns publication, schema validation,
JSON output, and exit semantics. It can proceed in parallel with Lane B once the
planning payload contract is frozen.

Lane D: fixtures and deterministic regression proof  
Starts only after Lane B and Lane C both land. This lane depends on stable phase
outputs, stable artifact names, and stable CLI behavior.

Lane E: docs and final surface alignment  
Runs last. Docs must describe the shipped surface, not the guessed one.

### 9.3 Execution Order

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

Execution order:

1. Launch Lane A first and merge it.
2. Launch Lane B and Lane C in parallel worktrees after A freezes the contract.
3. Merge B and C.
4. Run Lane D after runtime behavior and artifact shapes are both frozen.
5. Run Lane E last so docs reflect the shipped behavior.

### 9.4 Conflict Flags

- Lanes A, B, and C all depend on the exact planning state shape. B and C must
  not start before A freezes it.
- Lanes B and C both depend on runtime terminal payload semantics. If either lane
  changes `summary_payload` structure late, Lane D will churn.
- Lanes C and D both touch artifact names and examples. Freeze artifact filenames
  before D starts.
- Lane E touches the same docs surfaces that D validates. E must run last.

## 10. Acceptance Checklist

- [ ] `TaskSpec` accepts `task_kind: planning`
- [ ] `StrategyConfig` accepts declared planning phase and policy fields
- [ ] `validator_preflight_node(...)` rejects invalid planning declarations before model work
- [ ] `build_strategy_graph_spec(...)` emits `runtime_target: planning_v1`
- [ ] strategy graph spec serializes declared planning phases in canonical order
- [ ] strategy graph spec emits a generic post-runtime action for planning
- [ ] `build_harness_langgraph(...)` mounts `planning_v1`
- [ ] planning runs bypass `select_best_draft` through a generic post-runtime route
- [ ] the planning runtime executes four declared phases in order
- [ ] blocked runs emit structured clarification requests
- [ ] failed runs emit explicit `stop_reason`
- [ ] successful runs emit `PLAN.md`
- [ ] successful runs emit `plan.json`
- [ ] `plan.json` passes schema validation
- [ ] `artifact_index["plan_md"]` and `artifact_index["plan_json"]` are populated
- [ ] `summary_payload` contains the planning terminal payload for CLI compatibility
- [ ] CLI JSON mode returns the planning payload
- [ ] CLI exit code is `0` only for `success`
- [ ] example planning strategy and task files exist and are runnable
- [ ] repeat-run determinism tests pass for the bounded fixture corpus
- [ ] existing `single_pass`, `pfr_v1`, and `analysis_review_*` tests stay green

## 11. Completion Summary

- Step 0: scope accepted as a real runtime-family addition, not a markdown-only shortcut
- What already exists: mapped and reused; no second parser stack, graph builder, or artifact path
- Architecture: locked around one new `planning_v1` runtime family, one shared planning runtime module, and one generic post-runtime route
- Code quality: DRY authority map is explicit, minimal-diff rules are explicit, overbuilding is explicitly forbidden
- Test plan: full code-path and operator-flow coverage is defined, with determinism proof treated as required coverage
- Performance: bounded discovery and repeat-run stability are mandatory
- Failure modes: critical gaps are enumerated and tied to required tests and stop behavior
- Parallelization: one foundation lane, two parallel middle lanes, one proof lane, one docs lane
- Lake score: choose the complete compiler/runtime proof, not the pretty-markdown shortcut
