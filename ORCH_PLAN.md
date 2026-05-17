# ORCH_PLAN: C1 Deterministic Planning Compiler Wedge

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff workspace: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff branch context: `main`  
Authoritative implementation plan: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`  
Historical orchestration reference: `/Users/spensermcconnell/__Active_Code/forge/docs/project_management/plans/history/ORCH_PLAN.md`

This orchestration plan supersedes the stale B3 root orchestration and defines
the parent-agent execution model for milestone `C1` from kickoff through final
acceptance.

What this run must deliver:

- add runtime family `planning_v1`
- add curated strategy `deterministic_feature_planning_v1`
- route planning through shared graph machinery keyed by `runtime_target`
- preserve one parser stack, one graph builder, and one artifact write seam
- publish deterministic planning artifacts:
  - `PLAN.md`
  - `plan.json`
- prove success, clarification-needed, and failed outcomes on a bounded fixture
  corpus
- keep existing non-planning families green

Execution order is fixed by `PLAN.md` section 9:

1. `Lane A` first
2. `Lane B` and `Lane C` in parallel
3. `Lane D`
4. `Lane E`

The parent is the only integrator.

## Orchestration Runtime Policy

Parent runtime policy:

- `PLAN.md` is the authored source of truth for the full session. If this file
  and `PLAN.md` disagree, `PLAN.md` wins immediately.
- The parent snapshots the active root `PLAN.md` and this `ORCH_PLAN.md` into
  the orchestration state root before dispatch, but the root files remain
  authoritative.
- The parent is the only agent allowed to:
  - create or switch the integration branch
  - create worktrees
  - write or revise lane packets
  - publish freeze docs
  - merge worker branches
  - resolve conflicts
  - reopen blocked lanes
  - run the final integrated regression and acceptance sweep
- The parent owns all cross-lane contract decisions, especially:
  - planning state field shape
  - `runtime_target` and `post_runtime_action` routing
  - planning terminal payload shape
  - artifact filenames and schema obligations
  - final CLI exit semantics
- The parent keeps the critical path local for kickoff, all freeze publication,
  all merges, and final acceptance.

Worker runtime policy:

- Every worker lane runs on `GPT-5.4` with `reasoning_effort=high`.
- Workers operate only inside their lane packet, owned files, and published
  freezes.
- Workers do not merge, rebase for integration, widen scope, or edit `.runs/`.
- Workers do not rename frozen interfaces or change lane ownership.
- Workers treat packeted plan excerpts as dispatch context only. They do not
  override the root `PLAN.md`.

Concurrency policy:

- Maximum concurrent worker lanes: `2`
- Actual concurrency window:
  - `Lane A` runs alone
  - `Lane B` and `Lane C` run in parallel after the parent publishes the
    `Lane A` freeze
  - `Lane D` runs only after both `Lane B` and `Lane C` are merged and frozen
  - `Lane E` runs last

## Hard Guards

1. Scope is limited to milestone `C1 Deterministic Planning Compiler Wedge`.
2. Do not widen into post-C1 planning families, public workflow DSLs, or agent
   orchestration features.
3. Runtime routing must key off `runtime_target`, not strategy-name special
   casing.
4. `planning_v1` must be a real runtime family, not a branch hidden inside
   `analysis_review_v1`.
5. `deterministic_feature_planning_v1` must execute through shared planning
   machinery without strategy-name branches in core runtime code.
6. Keep one parser stack:
   - `TaskSpec.from_dict(...)`
   - `StrategyConfig.from_dict(...)`
7. Keep one runtime metadata builder:
   - `build_strategy_graph_spec(...)`
8. Keep one graph builder:
   - `build_harness_langgraph(...)`
9. Keep one artifact write entrypoint:
   - `publish_state_artifacts_v1(...)`
10. Keep one machine schema surface:
    - `anvil/harness/schemas.py`
11. No automatic worktree, branch, job, or agent dispatch may become product
    behavior.
12. Planning output may emit only advisory worktree metadata.
13. Deterministic planning artifacts are required across the bounded fixture
    corpus.
14. Existing runtime families must stay green:
    - `single_pass`
    - `pfr_v1`
    - `analysis_review_v1`
15. Existing strategy kinds must stay green:
    - `single_pass`
    - `pfr_v1`
    - `analysis_review_bounded_v1`
    - `analysis_review_trust_v1`
16. The parent is the only integrator.

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit Gate |
|---|---|---|---|---|
| Phase A: Kickoff and Authority Freeze | `task/c1-a1` to `task/c1-a7` | Parent | Strictly serialized | state root, branch, worktrees, invariants, packets exist |
| Phase B: Contract and Routing Foundation | `task/c1-b1` to `task/c1-b4` | `Lane A` | Serialized | `gate/c1-lane-a` |
| Phase C: Merge and Contract Freeze | `task/c1-c1`, `task/c1-c2` | Parent | Strictly serialized | `contract-routing-freeze.md` published |
| Phase D: Planning Runtime and Artifact/CLI Lanes | `task/c1-d1` to `task/c1-d6` | `Lane B`, `Lane C` | Parallel | `gate/c1-lane-b`, `gate/c1-lane-c` |
| Phase E: Merge and Planning Payload Freeze | `task/c1-e1`, `task/c1-e2` | Parent | Strictly serialized | `planning-payload-freeze.md` published |
| Phase F: Fixtures and Regression Proof | `task/c1-f1` to `task/c1-f4` | `Lane D` | Serialized | `gate/c1-lane-d` |
| Phase G: Merge and Fixture/Determinism Freeze | `task/c1-g1`, `task/c1-g2` | Parent | Strictly serialized | `fixtures-regression-freeze.md` published |
| Phase H: Docs and Final Surface Alignment | `task/c1-h1` to `task/c1-h3` | `Lane E` | Serialized | `gate/c1-lane-e` |
| Phase I: Merge and Docs Freeze | `task/c1-i1`, `task/c1-i2` | Parent | Strictly serialized | `docs-surface-freeze.md` published |
| Phase J: Final Regression and Acceptance | `task/c1-j1` to `task/c1-j4` | Parent | Strictly serialized | `gate/c1-final`, `gate/c1-acceptance`, `gate/c1-complete` |

## Launch Order

1. `task/c1-a1-read-authority`
2. `task/c1-a2-record-main-baseline`
3. `task/c1-a3-create-state-root`
4. `task/c1-a4-snapshot-plan-authority`
5. `task/c1-a5-freeze-invariants`
6. `task/c1-a6-create-integration-branch`
7. `task/c1-a7-create-worktrees-and-packets`
8. Dispatch `Lane A`
9. Merge `Lane A`
10. Publish `contract-routing-freeze.md`
11. Dispatch `Lane B`
12. Dispatch `Lane C`
13. Merge `Lane B`
14. Merge `Lane C`
15. Publish `planning-payload-freeze.md`
16. Dispatch `Lane D`
17. Merge `Lane D`
18. Publish `fixtures-regression-freeze.md`
19. Dispatch `Lane E`
20. Merge `Lane E`
21. Publish `docs-surface-freeze.md`
22. Run parent-only final regression and acceptance sweep

## Merge Order

1. `Lane A` merges first.
2. `Lane B` and `Lane C` merge after `Lane A`; either merge order is allowed.
3. The parent publishes `planning-payload-freeze.md` only after both `Lane B`
   and `Lane C` are merged and re-gated on the integration branch.
4. `Lane D` merges after both `Lane B` and `Lane C`.
5. `Lane E` merges last.
6. Final acceptance is parent-only on the fully integrated tree.

## Task Breakdown

### Phase A: Parent Kickoff Tasks

| Task ID | Purpose | Owner | Exit condition |
|---|---|---|---|
| `task/c1-a1-read-authority` | Re-read root `PLAN.md` and root `ORCH_PLAN.md`; restate C1 scope, lane order, and non-negotiables | Parent | scope and order recorded in `state.json` |
| `task/c1-a2-record-main-baseline` | Record current `main` HEAD SHA, working tree status, and baseline environment assumptions | Parent | baseline recorded in `state.json` |
| `task/c1-a3-create-state-root` | Initialize `.runs/c1-deterministic-planning-compiler-wedge-orch/` layout | Parent | required directories exist |
| `task/c1-a4-snapshot-plan-authority` | Copy `PLAN.md` and `ORCH_PLAN.md` into `inputs/` and record hashes | Parent | `inputs/PLAN.session.md` and `inputs/ORCH_PLAN.session.md` exist |
| `task/c1-a5-freeze-invariants` | Write `invariants.md` with hard guards, lane ownership, gates, blocker policy, and plan-drift rule | Parent | `invariants.md` exists |
| `task/c1-a6-create-integration-branch` | Create `codex/c1-deterministic-planning-compiler-wedge` from `main` in the root workspace | Parent | integration branch exists |
| `task/c1-a7-create-worktrees-and-packets` | Create all lane branches/worktrees and write handoff packets | Parent | all worktrees and packets exist |

### Lane A: Contract and Routing Foundation

Lane purpose: deliver `PLAN.md` slice 1 and freeze the planning contract so
later lanes can rely on it without churn.

Owned files:

- `anvil/harness/types.py`
- `anvil/harness/state.py`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/nodes/validator_preflight.py`
- `anvil/harness/nodes/select_strategy.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_semantic_validation.py`

Conditional-touch only:

- `tests/test_harness_analysis_contract.py`
  - Only if the existing contract coverage there is the cleanest place for one
    or two planning contract assertions.
  - It is not a default spillover file.

Must not touch:

- `anvil/harness/builder.py`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/subgraphs/`
- `anvil/harness/reporting.py`
- `anvil/harness/artifacts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/cli.py`
- `anvil/cli.py`
- `examples/harness/`
- `README.md`
- `examples/README.md`

#### Lane A tasks

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1-b1-planning-task-contract` | Add `planning` to the task contract and keep planning parse semantics distinct from review defaults | planning task files parse; unsupported planning task shape fails clearly |
| `task/c1-b2-planning-strategy-contract` | Extend `StrategyConfig` with planning keys: `runtime_target`, `phases[]`, `artifact_policy`, `determinism_policy`, `discovery_policy`, `rubric_policy`, `stop_policy` | valid planning strategy parses; missing policy refs fail |
| `task/c1-b3-runtime-metadata-and-post-route` | Extend `build_strategy_graph_spec(...)` to emit `runtime_target: planning_v1`, declared planning phases, and generic `post_runtime_action` | planning metadata serializes in canonical order |
| `task/c1-b4-preflight-compatibility-freeze` | Extend preflight to validate planning compatibility and block planning/non-planning auto-fit rewrites | invalid planning declarations fail before model work |

#### Lane A gate

`gate/c1-lane-a`
```bash
poetry run ruff check anvil/harness/types.py anvil/harness/state.py anvil/harness/strategy_graph.py anvil/harness/nodes/validator_preflight.py anvil/harness/nodes/select_strategy.py tests/test_harness_strategy_graph.py tests/test_harness_state_boundaries.py tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_harness_strategy_graph.py tests/test_harness_state_boundaries.py tests/test_harness_semantic_validation.py
```

#### Parent tasks after Lane A

| Task ID | Purpose | Exit condition |
|---|---|---|
| `task/c1-c1-merge-lane-a` | Merge `Lane A` into the integration branch and rerun `gate/c1-lane-a` on the integrated tree | `Lane A` merged and re-gated |
| `task/c1-c2-publish-contract-routing-freeze` | Publish the exact contract later lanes may rely on | `contract-routing-freeze.md` exists |

### Lane B: Planning Runtime Execution

Lane purpose: deliver `PLAN.md` slice 2 through the shared `planning_v1`
runtime family.

Owned files:

- `anvil/harness/builder.py`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/subgraphs/planning_v1.py`
- `anvil/harness/subgraphs/__init__.py`
- `tests/test_harness_planning_graph.py`

Must not touch:

- Lane A files
- Lane C files
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_example_strategy_wiring.py`
- `examples/harness/`
- docs surfaces

#### Lane B tasks

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1-d1-mount-planning-runtime` | Mount `planning_v1` in `build_harness_langgraph(...)` and wire generic post-runtime routing around `select_best_draft` | planning strategies route through `planning_v1`; existing families stay unchanged |
| `task/c1-d2-build-phase-registry` | Implement shared planning phase registry in `anvil/harness/planning_runtime.py` for the four canonical phases | registry executes phases in declared order |
| `task/c1-d3-stateful-phase-execution` | Record repo evidence refs, seams, workstreams, slices, counters, and policy versions in graph-owned planning state | successful runs populate seams, workstreams, slices, and counters |
| `task/c1-d4-honest-stop-behavior` | Implement `clarification_needed` and `failed` stop behavior without fake downstream records | clarification-needed and failed cases stop honestly |

#### Lane B gate

`gate/c1-lane-b`
```bash
poetry run ruff check anvil/harness/builder.py anvil/harness/planning_runtime.py anvil/harness/subgraphs/planning_v1.py anvil/harness/subgraphs/__init__.py tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_graph.py tests/test_harness_analysis_review_graph.py
```

### Lane C: Artifact Publication and CLI Surfacing

Lane purpose: deliver `PLAN.md` slice 3 with first-class planning artifacts and
operator-visible behavior.

Owned files:

- `anvil/harness/reporting.py`
- `anvil/harness/artifacts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/cli.py`
- `anvil/cli.py`
- `anvil/harness/nodes/write_artifacts.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`

Must not touch:

- Lane A files
- Lane B files
- `tests/test_harness_planning_graph.py`
- `tests/test_harness_example_strategy_wiring.py`
- `examples/harness/`
- docs surfaces

#### Lane C tasks

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1-d5-plan-publication-surface` | Keep `publish_state_artifacts_v1(...)` as entrypoint and add internal planning publication path: `plan_projection_v1(...)`, `publish_planning_artifacts_v1(...)`, `render_plan_markdown_v1(...)` | successful runs write `PLAN.md` and `plan.json` |
| `task/c1-d6-schema-cli-and-exit-semantics` | Validate `plan.json` in the shared schema surface; update CLI JSON, human summary, and exit semantics for planning terminal states | `artifact_index` and `summary_payload` are correct; CLI exit code is `0` only for `success` |

#### Lane C gate

`gate/c1-lane-c`
```bash
poetry run ruff check anvil/harness/reporting.py anvil/harness/artifacts.py anvil/harness/schemas.py anvil/harness/cli.py anvil/cli.py anvil/harness/nodes/write_artifacts.py tests/test_harness_planning_artifacts.py tests/test_harness_reporting.py tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
poetry run pytest -q tests/test_harness_planning_artifacts.py tests/test_harness_reporting.py tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
```

#### Parent tasks after Lanes B and C

| Task ID | Purpose | Exit condition |
|---|---|---|
| `task/c1-e1-merge-lanes-b-and-c` | Merge `Lane B` and `Lane C` into the integration branch and rerun both lane gates on the integrated tree | both lanes merged and re-gated |
| `task/c1-e2-publish-planning-payload-freeze` | Publish the exact runtime/output contract `Lane D` may rely on | `planning-payload-freeze.md` exists |

### Lane D: Fixtures, Example Wiring, and Determinism Proof

Lane purpose: deliver `PLAN.md` slice 4 without overlapping B/C-owned planning
test files.

Owned files:

- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- `examples/harness/tasks/deterministic_feature_planning_success.yaml`
- `examples/harness/tasks/deterministic_feature_planning_clarification.yaml`
- `examples/harness/tasks/deterministic_feature_planning_failed.yaml`
- `tests/test_harness_example_strategy_wiring.py`

Must not touch:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`
- any Lane A, B, or C production files
- docs surfaces

Determinism protocol:

- Determinism proof is owned by `Lane D` inside
  `tests/test_harness_example_strategy_wiring.py`.
- `Lane D` does not modify `tests/test_harness_planning_graph.py` or
  `tests/test_harness_planning_artifacts.py`.
- This keeps lane ownership disjoint and avoids normal-path reopen churn after
  B/C merge.

#### Lane D tasks

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1-f1-add-planning-strategy-example` | Add canonical example strategy `deterministic_feature_planning_v1.yaml` aligned to the frozen strategy contract | example strategy loads and matches shipped surface |
| `task/c1-f2-add-bounded-task-fixtures` | Add success, clarification-needed, and failed planning task fixtures | all three fixture classes exist and are runnable |
| `task/c1-f3-extend-example-wiring-proof` | Extend `tests/test_harness_example_strategy_wiring.py` so examples and docs cannot drift from the planning surface | strategy/task example wiring is proven |
| `task/c1-f4-repeat-run-determinism-proof` | Add repeat-run determinism tests for the bounded corpus in `tests/test_harness_example_strategy_wiring.py` using the frozen runtime and payload contract | stable seam, workstream, and slice IDs across repeated runs |

#### Lane D gate

`gate/c1-lane-d`
```bash
poetry run pytest -q tests/test_harness_example_strategy_wiring.py tests/test_harness_planning_graph.py tests/test_harness_planning_artifacts.py
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_success.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --workspace /Users/spensermcconnell/__Active_Code/forge --out-root .runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/success --json
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_clarification.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --workspace /Users/spensermcconnell/__Active_Code/forge --out-root .runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/clarification --json
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_failed.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --workspace /Users/spensermcconnell/__Active_Code/forge --out-root .runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/failed --json
```

#### Parent tasks after Lane D

| Task ID | Purpose | Exit condition |
|---|---|---|
| `task/c1-g1-merge-lane-d` | Merge `Lane D` into the integration branch and rerun `gate/c1-lane-d` on the integrated tree | `Lane D` merged and re-gated |
| `task/c1-g2-publish-fixtures-regression-freeze` | Freeze fixture names, repeat-run proof obligations, and accepted example command surfaces | `fixtures-regression-freeze.md` exists |

### Lane E: Docs and Final Surface Alignment

Lane purpose: update docs only after the shipped runtime, artifact, and fixture
surfaces are frozen.

Owned files:

- `README.md`
- `examples/README.md`

Must not touch:

- all production code
- all tests
- all example fixture YAML files

#### Lane E tasks

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1-h1-read-frozen-surface` | Read the contract, planning-payload, and fixtures-regression freezes and restate the shipped operator surface | docs start from shipped reality |
| `task/c1-h2-update-root-readme` | Update root `README.md` with the supported planning surface and existing CLI invocation | root docs match actual behavior |
| `task/c1-h3-update-examples-readme` | Update `examples/README.md` with the planning example strategy and bounded task fixtures | examples docs match actual fixtures and workflow |

#### Lane E gate

`gate/c1-lane-e`
```bash
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

#### Parent tasks after Lane E

| Task ID | Purpose | Exit condition |
|---|---|---|
| `task/c1-i1-merge-lane-e` | Merge `Lane E` into the integration branch and rerun `gate/c1-lane-e` on the integrated tree | `Lane E` merged and re-gated |
| `task/c1-i2-publish-docs-surface-freeze` | Freeze the exact documented C1 operator surface | `docs-surface-freeze.md` exists |

### Final Parent Acceptance Tasks

| Task ID | Purpose | Exit condition |
|---|---|---|
| `task/c1-j1-targeted-regression-sweep` | Run the full targeted integrated command set from `PLAN.md` and repo conventions | `gate/c1-final` passes or blocker is explicitly recorded |
| `task/c1-j2-acceptance-checklist-review` | Verify integrated tree against `PLAN.md` sections 6, 9, and 10 | `gate/c1-acceptance` passes |
| `task/c1-j3-non-planning-family-preservation-check` | Verify existing non-planning families remain green | preservation status recorded |
| `task/c1-j4-final-verdict` | Record green or blocked milestone verdict in `acceptance/final-verdict.md` | `gate/c1-complete` passes |

## Orchestration State and Source of Truth

State root:

- `.runs/c1-deterministic-planning-compiler-wedge-orch/`

Required layout:

- `.runs/c1-deterministic-planning-compiler-wedge-orch/queue.md`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/state.json`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/invariants.md`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/contract-routing-freeze.md`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/planning-payload-freeze.md`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/fixtures-regression-freeze.md`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/docs-surface-freeze.md`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/session.log`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/handoffs/`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/gates/`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/logs/`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/blockers/`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/sentinels/`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/inputs/`
- `.runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/`

### File roles

- `queue.md`
  - canonical task table for every `task/c1-*`
  - tracks owner, status, gate, reopen reason, and merge state
- `state.json`
  - branch names, worktree paths, plan hashes, freeze status, blockers, lane
    status, and final verdict
- `invariants.md`
  - frozen hard guards, lane ownership, commands, blocker protocol, and
    plan-drift rule
- `contract-routing-freeze.md`
  - parent-owned contract freeze after `Lane A`
- `planning-payload-freeze.md`
  - parent-owned runtime/output freeze after both `Lane B` and `Lane C`
- `fixtures-regression-freeze.md`
  - parent-owned fixture and determinism freeze after `Lane D`
- `docs-surface-freeze.md`
  - parent-owned docs alignment freeze after `Lane E`

### Plan-drift rule

- If implementation packets, stale orchestration text, or cached assumptions
  conflict with the current root `PLAN.md`, the parent updates packets and
  queue state to re-align with `PLAN.md`.
- No worker may use historical B3 materials, archived plans, or a prior freeze
  to justify drift from the current root `PLAN.md`.

## Operational Freeze Contents

### `contract-routing-freeze.md` after Lane A

Later lanes may rely on these exact frozen items:

- `TaskSpec` accepts `task_kind: planning`
- planning tasks do not inherit review-only defaults
- `StrategyConfig` planning keys are exactly:
  - `kind`
  - `runtime_target`
  - `phases[]`
  - `artifact_policy`
  - `determinism_policy`
  - `discovery_policy`
  - `rubric_policy`
  - `stop_policy`
- `runtime_target: planning_v1` is the only valid runtime family target for the
  curated C1 strategy
- declared planning phase order is canonical and validated in preflight
- `post_runtime_action` exists in strategy graph metadata and planning uses the
  direct-write path, not draft selection
- frozen planning state fields added by C1 are exactly:
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
- planning/non-planning auto-fit is forbidden in preflight

Lane B and Lane C may build on these fields and contracts without renaming
them.

### `planning-payload-freeze.md` after Lanes B and C

Later lanes may rely on these exact frozen items:

- the graph mounts `planning_v1`
- planning routes around `select_best_draft` through generic post-runtime
  routing
- canonical planning phase types are exactly:
  - `rubric_design_doc`
  - `architecture_seam_decomposition`
  - `parallel_workstream_planning`
  - `executable_slice_emission`
- planning terminal statuses are exactly:
  - `success`
  - `clarification_needed`
  - `failed`
- blocked runs populate non-empty `clarification_requests[]`
- failed runs populate explicit `planning_stop_reason`
- successful artifact filenames are exactly:
  - `PLAN.md`
  - `plan.json`
- `artifact_index` planning keys are exactly:
  - `plan_md`
  - `plan_json`
- `summary_payload` carries the planning terminal payload for CLI compatibility
- `plan.json` validation lives in `anvil/harness/schemas.py`
- CLI exit semantics are frozen:
  - `0` for `success`
  - `1` for `clarification_needed`
  - `1` for `failed`
  - `2` for invalid invocation or runtime error
- CLI JSON mode returns the planning terminal payload shape frozen here
- `Lane D` may assume these payload and artifact contracts without editing
  B/C-owned files

### `fixtures-regression-freeze.md` after Lane D

Later lanes may rely on these exact frozen items:

- canonical planning strategy fixture filename
- canonical success, clarification-needed, and failed planning task filenames
- repeat-run determinism proof location in
  `tests/test_harness_example_strategy_wiring.py`
- expected stable ID families:
  - seams
  - workstreams
  - slices
- accepted CLI example invocations for docs

## Sentinels

The parent maintains these sentinels under `sentinels/`:

- `parent-kickoff-complete`
- `lane-a-ready`
- `lane-a-merged`
- `contract-routing-freeze`
- `lane-b-ready`
- `lane-c-ready`
- `lane-b-merged`
- `lane-c-merged`
- `planning-payload-freeze`
- `lane-d-ready`
- `lane-d-merged`
- `fixtures-regression-freeze`
- `lane-e-ready`
- `lane-e-merged`
- `docs-surface-freeze`
- `final-acceptance-green`

Workers may start only when their `*-ready` sentinel exists and their handoff
packet exists.

## Wait Protocol

- A lane that does not have its `*-ready` sentinel waits.
- A lane that lacks a required freeze doc waits.
- A lane that hits a scope ambiguity, ownership conflict, or missing freeze
  writes `blockers/<lane>.md`, marks itself blocked in `queue.md`, and stops.
- Workers do not self-resolve by editing another lane’s files.
- Only the parent may clear a blocker, revise a packet, reopen a lane, or
  republish a freeze.

## Worktree and Branch Plan

Integration branch:

- `codex/c1-deterministic-planning-compiler-wedge`

Lane branches:

- `codex/c1-lane-a-contract-routing`
- `codex/c1-lane-b-planning-runtime`
- `codex/c1-lane-c-artifacts-cli`
- `codex/c1-lane-d-fixtures-regression`
- `codex/c1-lane-e-docs-alignment`

Worktree directories:

- `/Users/spensermcconnell/__Active_Code/forge`
- `/Users/spensermcconnell/__Active_Code/forge/.worktrees/c1/lane-a-contract-routing`
- `/Users/spensermcconnell/__Active_Code/forge/.worktrees/c1/lane-b-planning-runtime`
- `/Users/spensermcconnell/__Active_Code/forge/.worktrees/c1/lane-c-artifacts-cli`
- `/Users/spensermcconnell/__Active_Code/forge/.worktrees/c1/lane-d-fixtures-regression`
- `/Users/spensermcconnell/__Active_Code/forge/.worktrees/c1/lane-e-docs-alignment`

## Conflict and Reopen Protocol

Serialized surfaces:

- `anvil/harness/state.py` is serialized to `Lane A`
- `anvil/harness/builder.py` is serialized to `Lane B`
- `anvil/harness/reporting.py`, `anvil/harness/artifacts.py`,
  `anvil/harness/schemas.py`, `anvil/harness/cli.py`, and `anvil/cli.py` are
  serialized to `Lane C`
- `tests/test_harness_planning_graph.py` is serialized to `Lane B`
- `tests/test_harness_planning_artifacts.py` is serialized to `Lane C`
- `tests/test_harness_example_strategy_wiring.py` is serialized to `Lane D`
- `README.md` and `examples/README.md` are serialized to `Lane E`

Reopen rule:

- Reopen is exceptional, not the normal path.
- The parent reopens a lane only if a frozen contract was incomplete or wrong.
- Parent-owned reopen decisions must be recorded in `queue.md`, `state.json`,
  and the revised lane packet.

## Repo-Test Mapping to `PLAN.md` Section 6.3

This orchestration maps the required test work exactly as follows:

- extend `tests/test_harness_strategy_graph.py`
  - owner: `Lane A`
- extend `tests/test_harness_cli_command.py`
  - owner: `Lane C`
- extend `tests/test_harness_standalone_cli.py`
  - owner: `Lane C`
- add `tests/test_harness_planning_graph.py`
  - owner: `Lane B`
- add `tests/test_harness_planning_artifacts.py`
  - owner: `Lane C`
- add repeat-run determinism tests for the bounded fixture corpus
  - owner: `Lane D`
  - location: `tests/test_harness_example_strategy_wiring.py`
- extend `tests/test_harness_example_strategy_wiring.py`
  - owner: `Lane D`

This ownership map is intentionally disjoint to minimize merge churn.

## Context-Control Rules

- Each lane packet must include only the relevant `PLAN.md` sections, owned
  files, freeze docs, and gate commands for that lane.
- Workers should prefer the current codebase and packeted plan excerpts over
  historical docs, archived plans, or stale orchestration notes.
- No worker should load or edit unrelated repo areas to “help” another lane.
- If a lane discovers a likely cross-lane improvement outside scope, it records
  it in the packet handback and does not implement it.
- The parent keeps queue state and freeze docs small and factual so workers do
  not accumulate stale context.

## Final Regression and Acceptance

Lane gate commands:

`gate/c1-lane-a`
```bash
poetry run ruff check anvil/harness/types.py anvil/harness/state.py anvil/harness/strategy_graph.py anvil/harness/nodes/validator_preflight.py anvil/harness/nodes/select_strategy.py tests/test_harness_strategy_graph.py tests/test_harness_state_boundaries.py tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_harness_strategy_graph.py tests/test_harness_state_boundaries.py tests/test_harness_semantic_validation.py
```

`gate/c1-lane-b`
```bash
poetry run ruff check anvil/harness/builder.py anvil/harness/planning_runtime.py anvil/harness/subgraphs/planning_v1.py anvil/harness/subgraphs/__init__.py tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_graph.py tests/test_harness_analysis_review_graph.py
```

`gate/c1-lane-c`
```bash
poetry run ruff check anvil/harness/reporting.py anvil/harness/artifacts.py anvil/harness/schemas.py anvil/harness/cli.py anvil/cli.py anvil/harness/nodes/write_artifacts.py tests/test_harness_planning_artifacts.py tests/test_harness_reporting.py tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
poetry run pytest -q tests/test_harness_planning_artifacts.py tests/test_harness_reporting.py tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
```

`gate/c1-lane-d`
```bash
poetry run pytest -q tests/test_harness_example_strategy_wiring.py tests/test_harness_planning_graph.py tests/test_harness_planning_artifacts.py
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_success.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --workspace /Users/spensermcconnell/__Active_Code/forge --out-root .runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/success --json
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_clarification.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --workspace /Users/spensermcconnell/__Active_Code/forge --out-root .runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/clarification --json
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_failed.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --workspace /Users/spensermcconnell/__Active_Code/forge --out-root .runs/c1-deterministic-planning-compiler-wedge-orch/acceptance/failed --json
```

`gate/c1-lane-e`
```bash
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Parent final sweep:

`gate/c1-final`
```bash
poetry run ruff check .
poetry run black --check .
poetry run isort --check-only .
poetry run mypy anvil
poetry run pytest -q
poetry run pytest -q tests/test_lg_offline_smoke.py
```

`gate/c1-acceptance`

- `TaskSpec` accepts `task_kind: planning`
- `StrategyConfig` accepts declared planning phase and policy fields
- `validator_preflight_node(...)` rejects invalid planning declarations before
  model work
- `build_strategy_graph_spec(...)` emits `runtime_target: planning_v1`
- planning phases serialize in canonical order
- strategy graph emits a generic post-runtime action for planning
- `build_harness_langgraph(...)` mounts `planning_v1`
- planning bypasses `select_best_draft` through generic post-runtime routing
- the planning runtime executes four declared phases in order
- blocked runs emit structured clarification requests
- failed runs emit explicit `planning_stop_reason`
- successful runs emit `PLAN.md`
- successful runs emit `plan.json`
- `plan.json` passes shared schema validation
- `artifact_index["plan_md"]` and `artifact_index["plan_json"]` are populated
- `summary_payload` contains the planning terminal payload
- CLI JSON mode returns the planning payload
- CLI exit code is `0` only for `success`
- example planning strategy and planning task files exist and are runnable
- repeat-run determinism proof passes for the bounded fixture corpus
- existing `single_pass`, `pfr_v1`, and `analysis_review_*` tests stay green
- actual execution order matched `Lane A -> Lane B/C -> Lane D -> Lane E`

`gate/c1-complete`

- parent writes `acceptance/final-verdict.md`
- parent stamps `sentinels/final-acceptance-green`

## Assumptions

- `main` already contains the graph-owned harness surface C1 builds on.
- The local Poetry environment is sufficient to run the listed offline tests and
  CLI commands.
- C1 does not require provider API keys for acceptance.
- The bounded planning corpus is repo-local and small enough to respect the
  discovery-budget constraints in `PLAN.md` section 7.
- If final integrated gates expose a pre-existing unrelated baseline failure,
  the parent records it explicitly before deciding whether C1 is blocked.
