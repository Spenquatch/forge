# PLAN: C2 Honest Live Planning Alignment

Status: ready for implementation on `codex/c1b-planning-quality-proof`  
Milestone: `C2`  
Prepared from repo state on: `2026-05-18`

Source of truth:
- `/home/azureuser/.gstack/projects/Spenquatch-forge/azureuser-codex-c1b-planning-quality-proof-design-20260518-223850.md`
- current repository code in `anvil/harness/`, `examples/harness/`, `tests/`, `README.md`, and `examples/README.md`

Branch context:
- the earlier `C2` pass already landed the measurable coverage contract
- this branch is the closeout pass that makes the live planner honest enough to justify that contract
- this file supersedes the older root planning pass and is the authoritative implementation guide for `C2`

## Executive Summary

`C2` is not blocked on coverage artifacts anymore.

The real remaining gap is upstream of the artifacts. The live planning runtime in
[`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py)
still inspects a real repo, then falls back to Forge-self seam truth:

- `_score_path()` gives explicit weight to canonical seam hint files
- `_discovered_workspace_matches()` re-injects canonical planning files
- `_seam_paths()`, `_workstreams_for_seams()`, and `_slices_for_workstreams()` all derive structure from `_CANONICAL_SEAM_SPECS`
- `_derive_live_phase_payloads()` asks the canned clarification
  `"Should the planner prioritize runtime routing or artifact publication first?"`
  when that scaffold does not fit

That means the coverage ledger is more honest than the runtime it describes. Backward.

This plan finishes `C2` by keeping the shipped artifact contract and replacing the
live structural truth source. After this lands, a bounded real feature ask in a real
repo must yield repo-derived seams, repo-derived workstreams, repo-derived slices,
and truthful blocked-run coverage when the evidence is not good enough.

## 1. Objective and Success Bar

### 1.1 Objective

Ship an honest live planning runtime for
`deterministic_feature_planning_v1` by replacing canonical scaffold-driven seam
selection in
[`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py)
with bounded, deterministic, repo-derived phase outputs while preserving the
already-landed `C2` coverage artifact contract.

### 1.2 Exact problem statement

What already works:

- `plan_artifact_v2` publication
- `coverage_ledger`
- `assumptions_register`
- `uncovered_delta`
- success-only `PLAN.md` / `plan.json` publication
- truthful blocked/failed `summary.json` output

What is still wrong:

```text
task input
  -> bounded path discovery
  -> bounded file reads
  -> canonical seam lookup
  -> canonical workstream emission
  -> canonical slice emission
  -> coverage derivation
```

The first half is real. The second half is demo scaffolding.

That is why an outside repo can be inspected successfully and still get a
Forge-internal clarification instead of a repo-specific planning answer.

### 1.3 Success bar

`C2` is complete only when all of the following are true:

- a bounded real feature ask in an outside repo can emit repo-specific seams
  instead of `seam-runtime-routing` and `seam-artifact-publication`
- `design_doc`, `seam_decomposition`, `parallel_planning`, and `slice_emission`
  each own real live outputs
- the live clarification path is feature-specific and evidence-specific, not
  Forge-internal
- repeat runs on the same repo snapshot preserve seam/workstream/slice IDs,
  counts, and ordering
- blocked and failed runs still publish truthful partial coverage in
  `summary.json`
- no strategy-name branching is introduced
- no second planning runtime family is introduced
- the existing coverage contract stays intact unless a minimal extension is
  required to preserve live phase truth
- at least one outside-repo canary, with `gsd-browser` first, proves the live
  planner can emit non-canonical seams

## 2. Step 0: Scope Challenge

### 2.1 What already exists

| Sub-problem | Existing code | Plan decision |
|---|---|---|
| bounded repo discovery | [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py): `_direct_workspace_matches()`, `_discovered_workspace_matches()`, `_read_workspace_evidence()`, `_rank_paths()` | reuse the bounded discovery budget, do not create a new discovery subsystem |
| phase runtime skeleton | `PLANNING_PHASE_ORDER`, `PLANNING_PHASE_REGISTRY`, `_run_rubric_design_doc()`, `_run_architecture_seam_decomposition()`, `_run_parallel_workstream_planning()`, `_run_executable_slice_emission()` | keep the four-phase runtime family, make each phase produce real outputs |
| coverage truth pipeline | `_derive_planning_coverage()`, [`anvil/harness/reporting.py`](/home/azureuser/__Active_Code/forge/anvil/harness/reporting.py), [`anvil/harness/validation.py`](/home/azureuser/__Active_Code/forge/anvil/harness/validation.py), [`anvil/harness/schemas.py`](/home/azureuser/__Active_Code/forge/anvil/harness/schemas.py), [`anvil/harness/state.py`](/home/azureuser/__Active_Code/forge/anvil/harness/state.py) | preserve this contract unless a small metadata-preservation change is required |
| example strategy surface | [`examples/harness/strategies/deterministic_feature_planning_v1.yaml`](/home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml) | keep one visible canonical strategy |
| fixture stop paths | `examples/harness/tasks/deterministic_feature_planning_*.yaml` | keep fixtures for deterministic regression coverage, remove them as live seam truth |
| existing regression wall | [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py), [`tests/test_harness_planning_artifacts.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py), [`tests/test_harness_example_strategy_wiring.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py), [`tests/test_harness_state_boundaries.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_state_boundaries.py) | widen existing tests instead of creating a second acceptance harness |

### 2.2 Minimum complete scope

Nothing below is optional if this branch is going to close `C2` honestly:

1. Replace canonical live seam derivation with evidence-driven primary-cut
   selection inside
   [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py).
2. Make `design_doc`, `seam_decomposition`, `parallel_planning`, and
   `slice_emission` produce genuine live outputs from bounded repo evidence.
3. Preserve deterministic ordering, stable IDs, and frozen discovery budgets.
4. Preserve truthful blocked/failed coverage behavior.
5. Update example strategy/tests/docs so they prove repo-derived live planning,
   not canonical Forge-self seam scaffolding.
6. Add at least one outside-repo canary run, with `gsd-browser` first.

### 2.3 Complexity verdict

This branch touches more than eight files. That usually smells. Here the smell is
acceptable because the blast radius is tightly clustered around one runtime family
plus its already-existing artifact and test surfaces.

What would be overbuilt:

- a new planning runtime family
- a new discovery engine
- provider-backed seam synthesis
- a generalized planner-breadth project
- broad artifact schema churn for a problem that mostly lives in live derivation

### 2.4 Search/build verdict

No new platform needs to be invented.

Reuse what already exists:

- bounded discovery and read budgets in `planning_runtime.py`
- the current phase registry and terminal status plumbing
- the shipped coverage/artifact/validation pipeline
- the existing fixture strategy and task set

Do not add:

- a `planning_v2`
- a `*_live_v2` helper family
- a config-name switch on `deterministic_feature_planning_v1`
- a secondary schema/reporting family

### 2.5 TODO cross-reference

[`docs/project_management/future/TODOS.md`](/home/azureuser/__Active_Code/forge/docs/project_management/future/TODOS.md)
contains no deferred item that blocks this milestone.

This branch may create follow-up TODOs around planner breadth or future strategy
reuse, but those are explicitly outside this implementation.

### 2.6 NOT in scope

- user-authored graph config or public strategy authoring
- widening planning beyond the supported bounded corpus
- a second planning runtime family
- a runnable refine adapter
- provider/model redesign
- multi-repo planning
- background indexing or cached search infrastructure
- new CLI distribution or publish workflow

## 3. Locked Decisions

These decisions are frozen. Implementation may explain them, not reopen them.

| Decision | Locked choice | Why |
|---|---|---|
| visible strategy surface | keep one canonical strategy, `deterministic_feature_planning_v1` | product scope stays narrow |
| runtime target | keep `planning_v1` | no new runtime family |
| live truth source | remove `_CANONICAL_SEAM_SPECS` from the live success path | fixture truth must not masquerade as live truth |
| graph/config boundary | key behavior off phase semantics, never strategy name | preserves the architecture promise |
| discovery budget | keep `PLANNING_MATCH_LIMIT=25`, `PLANNING_READ_LIMIT=12`, `PLANNING_READ_BYTES_LIMIT=150 KiB` | bounded deterministic planning remains the product boundary |
| primary-cut credibility | require at least two supporting signals before proceeding | stops generic fake cuts |
| clarification behavior | clarification must be feature-specific and evidence-specific | canned Forge seam questions are not acceptable |
| artifact contract | preserve current success-only `PLAN.md` / `plan.json` rule and summary-only blocked/failed rule | minimal diff, already shipped |
| metadata preservation | if `primary_cut_summary` is emitted, preserve it through `reporting.py` and state round-trip instead of inventing a parallel reporting surface | keeps live truth inspectable without new artifact families |

## 4. Current Code Diagnosis

### 4.1 The exact truth gap

The current live path still hardcodes canonical planning truth:

- `_score_path()` gives a `+100` score to `_CANONICAL_SEAM_SPECS["path_hints"]`
- `_discovered_workspace_matches()` injects canonical planning files back into the candidate set
- `_seam_paths()` emits seams only from `_CANONICAL_SEAM_SPECS`
- `_workstreams_for_seams()` emits workstreams only from `_CANONICAL_SEAM_SPECS`
- `_slices_for_workstreams()` emits slices only from `_CANONICAL_SEAM_SPECS`
- `_derive_live_phase_payloads()` asks the canned runtime-routing-vs-artifact-publication question when that scaffold does not fit

The repo is being read. The structure is still being faked.

### 4.2 The test suite currently encodes the wrong thing

Current tests prove the existing wrong behavior:

- [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py)
  asserts `seam-runtime-routing`, `seam-artifact-publication`,
  `workstream-runtime-wiring`, and `slice-mount-planning-runtime`
- [`tests/test_harness_example_strategy_wiring.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py)
  asserts repeat-run stability on those same canonical IDs

Those tests were correct for the old demo scaffold. They are wrong for the `C2`
closeout we actually want.

### 4.3 The reporting path has one concrete metadata trap

[`anvil/harness/schemas.py`](/home/azureuser/__Active_Code/forge/anvil/harness/schemas.py)
already allows extra keys on `phase_results`.

But [`anvil/harness/reporting.py`](/home/azureuser/__Active_Code/forge/anvil/harness/reporting.py)
normalizes phase results down to three fields:

- `phase_id`
- `status`
- `summary`

So if we want `primary_cut_summary`, ambiguity flags, or other phase-owned metadata
to survive into artifacts, `reporting.py` has to preserve those fields deliberately.
Otherwise the runtime becomes more honest internally than the published plan.

### 4.4 Required runtime decision flow

This is the minimum deterministic live behavior the runtime must implement:

1. Rank candidate paths from task signals plus repo evidence.
2. In `design_doc`, choose a primary cut only when at least two credibility signals support it.
3. In `seam_decomposition`, synthesize `1-3` repo-derived seams from that cut.
4. In `parallel_planning`, derive workstreams from emitted seams and make dependency direction explicit.
5. In `slice_emission`, derive `1-2` executable slices per workstream with explicit acceptance criteria.
6. Only after those steps, derive coverage from what the runtime actually emitted.

## 5. Target Architecture

### 5.1 Target runtime shape

```text
task yaml + strategy yaml
        │
        ▼
execute_planning_runtime()
        │
        ├── bounded discovery
        │   ├── _direct_workspace_matches()
        │   ├── _discovered_workspace_matches()   [live, not canonical-biased]
        │   ├── _rank_paths()
        │   └── _read_workspace_evidence()
        │
        ├── design_doc
        │   ├── supported corpus check
        │   ├── primary cut selection
        │   └── feature-specific clarification when the cut is not credible
        │
        ├── seam_decomposition
        │   └── repo-derived seams
        │
        ├── parallel_planning
        │   └── repo-derived workstreams + dependency reasoning
        │
        ├── slice_emission
        │   └── executable slices + acceptance criteria
        │
        ├── _derive_planning_coverage()
        │   └── existing coverage contract, now grounded in real live structure
        │
        ▼
plan_projection_v1() / publish_state_artifacts_v1()
        │
        ├── success -> PLAN.md + plan.json + summary.json
        └── blocked/failed -> summary.json only
```

### 5.2 Exact ownership map

| Concern | Canonical owner | Required outcome |
|---|---|---|
| path ranking and evidence budget | `planning_runtime.py` | deterministic candidate set within the frozen budget |
| primary cut selection | `planning_runtime.py` | credible repo-derived cut or truthful clarification |
| seam/workstream/slice truth | `planning_runtime.py` | repo-derived live structures, no canonical scaffold dependency |
| phase result durability | `planning_runtime.py`, `reporting.py`, `state.py` | live phase metadata survives if it is needed for artifact truth |
| coverage truth | `_derive_planning_coverage()` plus existing reporting/validation | preserve contract, improve truth by improving upstream structure |
| example truth | `examples/harness/` | fixtures stay deterministic but stop pretending to be the live success path |
| acceptance proof | `tests/` plus outside-repo canary | repo-derived live planning is provable and repeatable |

### 5.3 Concrete live heuristics

#### Candidate path ranking

Input signals:

- explicit `files_hint` matches
- objective-token overlap
- acceptance-token overlap
- repeated directory roots
- implementation-file bias over broad docs when both match

Tie-break rules:

1. higher score wins
2. if scores tie, shorter repo-relative path wins
3. if still tied, lexical order wins

Determinism rule:

- same repo snapshot plus same task input must yield the same ranked path order

#### Primary cut selection in `design_doc`

A primary cut is credible only if at least two of these signals support it:

- repeated task-token overlap across a shared module or directory root
- implementation files plus matching API/UI/supporting files in the same area
- docs or ADR references that name the same subsystem as live code matches
- an obvious user-facing and backend surface meeting at one workflow boundary

If no cut reaches two signals, stop with `clarification_needed`.

#### Seam synthesis in `seam_decomposition`

Generate `1-3` seams using this fallback order:

1. workflow boundary seams
2. module/package seams
3. integration seams

Each seam must include:

- `seam_id`
- `title`
- `summary`
- `repo_evidence_refs`
- optional `dependency_reasoning`
- optional `ambiguity_flags`

#### Workstream derivation in `parallel_planning`

Rules:

- one workstream per seam by default
- merge seams only when the evidence shows they cannot ship independently
- record dependency direction explicitly
- set `worktree_recommended` only when the workstream boundary is genuinely isolated

#### Slice derivation in `slice_emission`

Rules:

- emit `1-2` slices per workstream
- slice one proves the core user-visible or architecture-visible move
- slice two, when present, covers follow-through or contract work
- every slice must include explicit acceptance criteria

### 5.4 Stable ID rules

- `seam_id = seam-{index:02d}-{slug}`
- `workstream_id = workstream-{index:02d}-{primary-seam-slug}`
- `slice_id = slice-{workstream_index:02d}-{action-slug}`

Collision rule:

- preserve discovery order
- keep the index distinct
- do not mutate the slug to hide nondeterminism

### 5.5 Phase output contract

| Phase | Required live outputs | Optional outputs | Downstream consumers |
|---|---|---|---|
| `design_doc` | `summary`, `repo_evidence_refs`, `search_pass_count`, `inspected_file_count`, `discovery_budget_escalated`, `primary_cut_summary` | `clarification_requests`, `ambiguity_flags` | stop-path logic, coverage `problem_frame`, coverage `repo_surface` |
| `seam_decomposition` | `planning_seams[]` with `seam_id`, `title`, `summary`, `repo_evidence_refs` | `dependency_reasoning`, `ambiguity_flags` | coverage `seam_selection`, workstream derivation |
| `parallel_planning` | `planning_workstreams[]` with `workstream_id`, `title`, `summary`, `seam_ids`, `worktree_recommended` | `dependency_reasoning`, `ambiguity_flags` | coverage `dependency_shape`, `execution_partitioning`, slice derivation |
| `slice_emission` | `planning_slices[]` with `slice_id`, `title`, `summary`, `workstream_id`, `seam_ids`, `acceptance_criteria[]` | `dependency_reasoning`, `ambiguity_flags` | coverage `acceptance_shape`, final artifact truth |

Implementation note:

- if `primary_cut_summary` is emitted, preserve it through `planning_phase_results`
  and plan payload normalization
- do not create a second phase-reporting surface just to carry it

## 6. Implementation Plan

### 6.1 Primary files to touch

| File | Why it changes |
|---|---|
| [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py) | core live-planning truth gap lives here |
| [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py) | runtime success, clarification, failure, and determinism assertions must change materially |
| [`tests/test_harness_planning_artifacts.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py) | artifact assertions must prove coverage is grounded in repo-derived structures |
| [`tests/test_harness_example_strategy_wiring.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py) | example success path must stop asserting canonical seam IDs for live success |
| [`examples/harness/strategies/deterministic_feature_planning_v1.yaml`](/home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml) | fixture/example language must clearly distinguish fixture truth from live truth |
| `examples/harness/tasks/deterministic_feature_planning_*.yaml` | stop-path fixtures must stay honest |
| [`README.md`](/home/azureuser/__Active_Code/forge/README.md) | supported planning corpus and artifact truth need an honest description |
| [`examples/README.md`](/home/azureuser/__Active_Code/forge/examples/README.md) | example behavior must distinguish fixture scaffolding from live repo-derived planning |
| [`anvil/harness/reporting.py`](/home/azureuser/__Active_Code/forge/anvil/harness/reporting.py) | required if phase-result metadata must survive publication |
| [`anvil/harness/state.py`](/home/azureuser/__Active_Code/forge/anvil/harness/state.py) and [`tests/test_harness_state_boundaries.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_state_boundaries.py) | required if phase-result metadata must survive summary round-trip |
| [`anvil/harness/validation.py`](/home/azureuser/__Active_Code/forge/anvil/harness/validation.py) | touch only if new preserved metadata needs validation or stale assumptions emerge |

### 6.2 Execution contract

| Slice | Why it exists | Cannot start until | Produces |
|---|---|---|---|
| A. Freeze runtime rules | lock heuristics, cut criteria, and object contract | — | one unambiguous runtime decision flow |
| B. Make `design_doc` real | move supported-corpus and primary-cut truth into phase 1 | A | credible cut selection or feature-specific clarification |
| C. Make seam/workstream/slice derivation real | replace canonical scaffold truth with repo-derived structure | A, B | repo-derived seams, workstreams, slices |
| D. Preserve artifact truth | keep coverage, reporting, docs, and examples aligned with live reality | B, C | truthful artifacts, honest docs, honest fixtures |
| E. Add canaries and regression wall | prove this works on fixtures and outside repos | B, C, D | repeatable acceptance proof |

Rules:

- Slice A freezes the nouns and heuristics.
- Slice B owns the first real decision: is the ask grounded enough to proceed?
- Slice C owns structural truth.
- Slice D keeps the shipped contract honest.
- Slice E is the merge wall.

### 6.3 Slice A: Freeze runtime rules

Goal: remove ambiguity before changing behavior.

Primary files:

- [`PLAN.md`](/home/azureuser/__Active_Code/forge/PLAN.md)
- [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py)
- strategy/example comments if wording must align immediately

Concrete changes:

- freeze the supported-corpus language in code comments and docs
- freeze the primary-cut two-signal rule
- freeze the seam synthesis fallback order:
  workflow boundary -> module/package -> integration seam
- freeze the ID recipes and tie-break rules
- freeze the rule that `_CANONICAL_SEAM_SPECS` becomes fixture/example scaffolding only
- decide now that `primary_cut_summary` is required plan truth, not optional branch lore

Definition of done:

- all later implementation can point to one set of heuristics
- no later slice needs to reinterpret what counts as a credible primary cut

### 6.4 Slice B: Make `design_doc` real

Goal: turn phase 1 into a real live planning gate instead of a pass-through.

Primary files:

- [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py)
- [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py)

Exact implementation work:

1. Refactor `_score_path()` so live ranking no longer awards canonical seam hints.
2. Refactor `_discovered_workspace_matches()` so it expands from selected roots and live repo structure, not from `_CANONICAL_SEAM_SPECS`.
3. Add a focused primary-cut helper inside `planning_runtime.py`. One helper is fine. A new module is not.
   The helper must:
   - score candidate clusters
   - require two credibility signals
   - emit `primary_cut_summary`
   - emit feature-specific clarification text when the cut is not credible
4. Thread `search_pass_count`, `inspected_file_count`, and `discovery_budget_escalated`
   through the phase result exactly as they work today.

Definition of done:

- a credible supported ask proceeds
- an unsupported or weakly grounded ask stops honestly
- the clarification text references the feature or repo surface, not Forge internals

### 6.5 Slice C: Make seam/workstream/slice derivation real

Goal: derive structural outputs from the selected primary cut instead of from
`_CANONICAL_SEAM_SPECS`.

Primary files:

- [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py)
- [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py)
- [`tests/test_harness_example_strategy_wiring.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py)

Exact implementation work:

1. Replace `_seam_paths()` with repo-derived seam synthesis.
2. Replace `_workstreams_for_seams()` with emitted-seam-driven workstream derivation.
3. Replace `_slices_for_workstreams()` with workstream-driven slice emission.
4. Keep all of this in `planning_runtime.py`. Do not create a parallel helper framework.
5. Preserve:
   - `1-3` seams
   - deterministic ordering
   - stable IDs
   - explicit `repo_evidence_refs`
   - explicit seam/workstream/slice linkage
   - explicit dependency reasoning when seams merge or sequence

Definition of done:

- success runs can emit non-canonical seam IDs on a real outside repo
- repeat runs against the same repo snapshot preserve IDs, counts, and ordering

### 6.6 Slice D: Preserve artifact truth

Goal: keep the already-shipped coverage and publication contract while making it
describe the new live truth source honestly.

Primary files:

- [`anvil/harness/planning_runtime.py`](/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py)
- [`anvil/harness/reporting.py`](/home/azureuser/__Active_Code/forge/anvil/harness/reporting.py), conditionally
- [`anvil/harness/state.py`](/home/azureuser/__Active_Code/forge/anvil/harness/state.py), conditionally
- [`tests/test_harness_planning_artifacts.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py)
- [`tests/test_harness_state_boundaries.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_state_boundaries.py), conditionally
- [`README.md`](/home/azureuser/__Active_Code/forge/README.md)
- [`examples/README.md`](/home/azureuser/__Active_Code/forge/examples/README.md)
- [`examples/harness/strategies/deterministic_feature_planning_v1.yaml`](/home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml)
- `examples/harness/tasks/deterministic_feature_planning_*.yaml`

Exact implementation work:

1. Confirm `_derive_planning_coverage()` still derives truthful rows from repo-derived structures.
2. Preserve `primary_cut_summary` through `phase_results` normalization if it is part of the published truth.
3. Update README/example prose so it says clearly:
   - fixture mode remains deterministic scaffolding
   - live success mode is repo-derived
   - blocked/failed runs still publish `summary.json` only
4. Update example success assertions so they check determinism and honesty, not Forge-self seam IDs.

Definition of done:

- docs no longer imply that canonical seam IDs are the live success path
- plan payloads and summaries preserve the live metadata the user needs to inspect
- artifact tests prove coverage is grounded in emitted repo-derived structures

### 6.7 Slice E: Add canaries and regression wall

Goal: prove the runtime is now honest on both fixture-backed and live repo asks.

Primary files:

- [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py)
- [`tests/test_harness_planning_artifacts.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py)
- [`tests/test_harness_example_strategy_wiring.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py)
- canary procedure captured in docs or branch notes

Exact implementation work:

- update fixture success assertions to validate determinism without pinning live success to Forge-self seams
- add repeat-run assertions for stable repo-derived IDs
- add a regression that fails if the canned clarification question appears for a credible supported outside-repo ask
- add the `gsd-browser` canary requirement:
  - live run emits `1-3` non-canonical seams
  - none of them equal `seam-runtime-routing` or `seam-artifact-publication`
  - workstreams and slices reference those seams cleanly

Definition of done:

- fixture paths still pass
- outside-repo canary proves repo-derived planning
- determinism still holds

## 7. Code Quality and Contract Hygiene

### 7.1 Engineering rules

- Keep the diff minimal. Most contract work is already shipped.
- Bias toward explicit over clever.
- Reuse the current runtime/publication/validation surfaces.
- Prefer extending existing helpers over spawning `*_v2` families.
- Keep deterministic ID rules close to derivation logic.
- Do not mix this structural change with speculative planner breadth.

### 7.2 Truth ownership boundaries

| Concern | Owner | Rule |
|---|---|---|
| bounded discovery and primary-cut selection | `planning_runtime.py` | runtime decides what evidence matters |
| seam/workstream/slice structure | `planning_runtime.py` | runtime emits live structure, examples do not |
| coverage truth | `_derive_planning_coverage()` | coverage summarizes runtime-owned structure, it does not invent it |
| artifact serialization | `reporting.py` | publish exactly what runtime produced |
| integrity gating | `validation.py` | reject inconsistent success artifacts before publication |
| fixture scaffolding | `examples/harness/` | fixture truths are for regression coverage only |

### 7.3 Anti-patterns explicitly rejected

- keeping `_CANONICAL_SEAM_SPECS` in the live success path
- changing docs without changing runtime behavior
- solving this with strategy-name branching
- adding provider calls or LLM prompts to synthesize seams
- reopening `plan_artifact_v2` wholesale when a metadata-preservation patch will do
- adding new abstraction layers for hypothetical future strategies before one honest built-in strategy exists

## 8. Test Review

Framework: `pytest`  
Coverage target: every changed branch in the live planning path gets regression
coverage.  
Ship rule: `C2` is not done if tests only prove schema validity while the live
runtime still emits Forge-self seams.

### 8.1 Codepath coverage diagram

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/planning_runtime.py
    │
    ├── _score_path()
    │   ├── [EXISTING] bounded scoring and lexical ordering
    │   └── [GAP]      remove canonical seam hint bias from live scoring
    │
    ├── _discovered_workspace_matches()
    │   ├── [EXISTING] second-pass discovery hook
    │   └── [GAP]      stop injecting canonical planning files as live truth
    │
    ├── _derive_live_phase_payloads()
    │   ├── [EXISTING] out-of-corpus rejection
    │   ├── [EXISTING] bounded path discovery and file reads
    │   ├── [GAP]      primary-cut selection using repo evidence
    │   ├── [GAP]      feature-specific clarification when the cut is not credible
    │   └── [GAP]      live payloads that are not scaffold-driven
    │
    ├── _seam_paths() or replacement
    │   ├── [EXISTING] canonical seam match
    │   └── [GAP]      repo-derived seam synthesis
    │
    ├── _workstreams_for_seams() or replacement
    │   ├── [EXISTING] canonical workstream emission
    │   └── [GAP]      dependency-aware workstream derivation from emitted seams
    │
    ├── _slices_for_workstreams() or replacement
    │   ├── [EXISTING] canonical slice emission
    │   └── [GAP]      slice derivation with explicit acceptance criteria from workstream intent
    │
    └── _derive_planning_coverage()
        ├── [EXISTING] coverage rows, assumptions, delta
        └── [GAP]      prove those rows stay truthful when live structure becomes repo-derived

[+] tests/test_harness_planning_graph.py
    │
    ├── [EXISTING] success / clarification_needed / failed terminal assertions
    ├── [GAP]      primary-cut assertions
    ├── [GAP]      non-canonical seam/workstream/slice assertions on live success
    ├── [GAP]      clarification text regression assertions
    └── [GAP]      repeat-run determinism assertions for repo-derived IDs

[+] tests/test_harness_example_strategy_wiring.py
    │
    ├── [EXISTING] fixture/example strategy assertions
    └── [GAP]      stop asserting live success equals Forge-self seam IDs

[+] tests/test_harness_planning_artifacts.py
    │
    ├── [EXISTING] plan_artifact_v2 and coverage contract assertions
    ├── [GAP]      assert coverage truth references repo-derived live structures correctly
    └── [GAP]      assert preserved design-phase metadata survives if published

[+] tests/test_harness_state_boundaries.py
    │
    ├── [EXISTING] summary round-trip checks
    └── [GAP]      preserve new phase-result metadata if it becomes part of the contract

USER / OPERATOR FLOW COVERAGE
===========================
[+] Successful bounded live planning run
    ├── [EXISTING] emits PLAN.md and plan.json
    ├── [GAP]      emits repo-derived seams for a real target repo
    └── [GAP]      coverage surfaces describe those repo-derived seams honestly

[+] Clarification-needed run
    ├── [EXISTING] emits summary only
    └── [GAP]      asks a feature-specific clarification, not a Forge-internal seam question

[+] Failed run
    ├── [EXISTING] emits summary only
    └── [GAP]      still carries truthful partial coverage based on what the runtime actually learned
```

### 8.2 Required test additions

1. Runtime decision tests in
   [`tests/test_harness_planning_graph.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_graph.py):
   prove `design_doc` chooses a primary cut only when the two-signal rule is satisfied.
2. Clarification-path tests in the same file:
   prove credible outside-repo asks do not fall back to the canned
   `"runtime routing or artifact publication"` question.
3. Live success tests in the same file:
   prove repo-derived seam IDs are emitted for non-Forge repo surfaces.
4. Determinism tests in
   [`tests/test_harness_example_strategy_wiring.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py)
   and/or the graph tests:
   prove repeat runs preserve seam/workstream/slice counts and IDs.
5. Coverage-grounding tests in
   [`tests/test_harness_planning_artifacts.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_planning_artifacts.py):
   prove `coverage_ledger` rows still resolve against emitted structural IDs when those IDs are repo-derived.
6. Metadata round-trip tests in
   [`tests/test_harness_state_boundaries.py`](/home/azureuser/__Active_Code/forge/tests/test_harness_state_boundaries.py),
   if `primary_cut_summary` becomes part of published phase truth.
7. Outside-repo canary procedure:
   record one `gsd-browser` planning ask and assert non-canonical seam IDs plus clean downstream links.

### 8.3 Suggested commands

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
```

Run the reporting test only if phase-result normalization changes.

### 8.4 Human acceptance checks

- real-repo rubric:
  emitted seams read like the target repo, not Forge internals
- skeptical-reader rubric:
  the artifact explains what is covered and what is assumed without branch lore
- honesty rubric:
  blocked runs expose the actual missing cut or missing evidence, not a generic fallback question

## 9. Performance and Reliability Review

### 9.1 Performance risks

| Risk | Why it matters | Required mitigation |
|---|---|---|
| primary-cut heuristics overread the workspace | planning latency grows with no product value | reuse the existing bounded discovery and read budgets |
| seam synthesis uses too many weak signals | runtime becomes unstable across repeat runs | keep the two-signal cut rule and deterministic tie-breakers |
| docs dominate ranking | planner chooses prose instead of implementation surfaces | keep implementation-file bias when both docs and code match |
| feature-specific clarification becomes nondeterministic prose | test output becomes flaky and hard to trust | derive clarification from explicit stop reasons and selected evidence |

### 9.2 Reliability rules

- no phase may reopen the discovery budget after `design_doc`
- the live success path must never depend on `_CANONICAL_SEAM_SPECS`
- repeat runs on the same repo snapshot must preserve IDs, counts, and ordering
- success publication must still fail closed on broken coverage invariants

### 9.3 Performance verdict

Do not add caching, background indexing, or a second search-pass framework in
`C2`. The current bounded runtime should stay cheap and boring.

## 10. Error & Rescue Registry

| Failure | User-visible impact | Rescue |
|---|---|---|
| primary cut is too broad | plan feels generic and not executable | tighten the two-signal rule and add targeted clarification |
| canonical seam question still appears | planner exposes Forge-internal fallback instead of target-repo truth | add explicit regression coverage and remove the live fallback |
| seam titles are unstable across reruns | artifact churn and trust loss | enforce deterministic title and slug generation |
| workstream dependencies are implicit | false parallelism and bad worktree advice | require explicit dependency reasoning on merged seams |
| phase-result metadata is lost in reporting | runtime gets more honest than published artifacts | preserve whitelisted phase metadata in reporting/state round-trip |
| coverage stays formally valid but semantically weak | artifact looks honest while structure is fake | tie artifact assertions to emitted seam/workstream/slice IDs |

## 11. Failure Modes Registry

| New codepath | Realistic production failure | Test covers it? | Error handling exists? | User-visible outcome | Status |
|---|---|---:|---:|---|---|
| primary-cut selection | planner chooses a docs-only surface and misses the implementation boundary | must add | must add | vague or misleading plan | critical gap until covered |
| clarification path | credible ask still emits the Forge seam question | must add | must add | user gets irrelevant guidance | critical gap until covered |
| seam synthesis | same repo snapshot yields different seam IDs across reruns | must add | must add | unstable artifacts and flaky automation | critical gap until covered |
| workstream derivation | seams that should be sequential are marked parallel | must add | must add | merge-conflict bait and invalid worktree advice | required |
| slice derivation | acceptance criteria are absent or too generic | must add | must add | non-executable slices | required |
| coverage grounding | coverage rows reference repo-derived IDs incorrectly after runtime refactor | must add | existing validation partially helps | broken trust surface | critical gap until covered |
| phase metadata preservation | `primary_cut_summary` disappears from published plan payload | must add | must add | user cannot inspect why the cut was chosen | required if metadata is published |
| outside-repo canary | canary still resolves to canonical Forge seams | must add | must add | milestone claim remains unproven | critical gap until covered |

Any row with no test and no clear stop-path handling is a merge blocker.

## 12. DX and Operator Experience

### 12.1 Developer journey map

| Stage | Current experience | C2 target |
|---|---|---|
| run planner | command succeeds | same |
| inspect seams | often sees Forge-self seams | sees target-repo seams |
| interpret clarification | may get Forge-internal question | gets feature-specific missing-input question |
| trust coverage artifact | mechanically valid, semantically shaky | mechanically and semantically aligned |
| split implementation | worktree advice may reflect fake seams | worktree advice reflects real repo boundaries |

### 12.2 Distribution plan

Distribution remains the existing CLI artifact path.

No new package, workflow, or publish step is required. The product proof remains:

- run the planner through the current CLI
- inspect `summary.json` on blocked runs
- inspect `PLAN.md` and `plan.json` on success runs

### 12.3 DX verdict

This is a DX improvement through honesty, not through new commands. The command
count stays the same. The ambiguity after the command finishes should drop
materially.

## 13. Worktree Parallelization Strategy

This branch is only partly parallelizable. The core behavior change is concentrated
in `anvil/harness/planning_runtime.py`, so the structural middle of the branch is
mostly sequential. The real safe parallel lane is docs/examples/canary prep after
the runtime rules are frozen.

### 13.1 Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Freeze runtime rules | `anvil/harness/`, plan/docs surface | — |
| B. Implement real `design_doc` and primary-cut logic | `anvil/harness/` | A |
| C. Implement real seam/workstream/slice derivation | `anvil/harness/`, runtime tests | B |
| D. Align reporting, docs, fixtures, and examples | `anvil/harness/`, `examples/harness/`, repo docs | A, B |
| E. Regression wall and canary verification | `tests/`, `anvil/harness/`, docs/examples surface | C, D |

### 13.2 Parallel lanes

Lane A: rule freeze  
Run first. This locks the heuristics, output expectations, and what counts as a
credible primary cut.

Lane B: phase-1 runtime gate  
Run after A. This owns the ranking cleanup, primary-cut selection, and clarification path.

Lane C: structural derivation  
Run after B. This owns repo-derived seams, workstreams, slices, and stable live IDs.

Lane D: docs/examples/reporting alignment  
Run after B in parallel with C, as long as the reporting change stays narrowly scoped.
This lane owns:

- example wording
- fixture wording
- README/example updates
- plan/report normalization changes needed to preserve phase metadata

Lane E: regression wall  
Run last. This finalizes tests and outside-repo verification after behavior and wording settle.

### 13.3 Execution order

```text
Lane A
  │
  ▼
Lane B
  │
  ├──────────────► Lane C
  │
  └──────────────► Lane D
                      │
              Lane C + Lane D complete
                      │
                      ▼
                    Lane E
```

Execution order:

1. Launch Lane A and freeze the rules.
2. Launch Lane B and land the phase-1 gate.
3. Launch Lane C and Lane D in parallel worktrees.
4. Merge C and D.
5. Run Lane E as the merge-blocking regression wall and canary proof.

### 13.4 Recommended worktree ownership

| Lane | Primary owner surface | Why |
|---|---|---|
| A | `PLAN.md`, runtime comments | freezes decisions before code spreads |
| B | `planning_runtime.py`, graph tests | one file family, high coupling |
| C | `planning_runtime.py`, graph/example wiring tests | structural truth and stable IDs |
| D | `reporting.py`, `state.py`, docs, example strategy/tasks | low-risk contract threading plus wording alignment |
| E | `tests/`, canary notes | final integration proof |

### 13.5 Conflict flags

- Lanes A and B both touch `planning_runtime.py`. B must wait for A.
- Lanes B and C both touch `planning_runtime.py`. C must wait for B.
- Lanes C and E both touch planning graph tests. Keep final assertion shape in E.
- Lanes D and E may both touch artifact/reporting tests. Final truth assertions belong in E.
- If phase-result metadata preservation expands beyond a narrow whitelist, stop and re-evaluate. That is how this branch accidentally turns into contract churn.

## 14. Acceptance Checklist

- [ ] live success no longer depends on `_CANONICAL_SEAM_SPECS`
- [ ] `_score_path()` and `_discovered_workspace_matches()` no longer bias live success toward canonical Forge seams
- [ ] `design_doc` chooses a credible primary cut or emits a feature-specific clarification
- [ ] `seam_decomposition` emits `1-3` repo-derived seams
- [ ] `parallel_planning` emits workstreams derived from those seams
- [ ] `slice_emission` emits slices with explicit acceptance criteria
- [ ] repeat runs preserve seam/workstream/slice counts, IDs, and ordering
- [ ] outside-repo canary emits non-canonical seam IDs
- [ ] the canned Forge seam clarification question is gone from credible supported outside-repo asks
- [ ] `coverage_ledger`, `assumptions_register`, and `uncovered_delta` remain truthful without reopening the `C2` artifact contract
- [ ] published artifacts preserve any newly required design-phase metadata
- [ ] blocked/failed runs still publish `summary.json` only
- [ ] no strategy-name branching is introduced
- [ ] no second planning runtime family is introduced

## 15. Completion Summary

- Step 0: scope accepted as live-planner honesty work, not another coverage-contract project
- What already exists: mapped and reused, especially the landed `C2` coverage contract and publication gates
- Locked decisions: one built-in strategy, one runtime family, one bounded corpus, one live truth source
- Architecture: live phase outputs become repo-derived while coverage stays on the shipped contract
- Implementation plan: five slices with exact file ownership, sequencing rules, and acceptance proof
- Code quality: explicit heuristics, explicit tie-breakers, minimal diff, no new framework work
- Test review: coverage now targets the real truth gap in `_derive_live_phase_payloads()` and the canonical seam scaffold
- Performance review: bounded discovery stays frozen and cheap
- Failure modes: critical gaps enumerated for fake cuts, canned clarifications, unstable IDs, semantically weak coverage truth, and dropped phase metadata
- DX: same command surface, much less ambiguity after the run
- Parallelization: one foundation lane, one phase-1 lane, one structural lane, one docs/reporting lane, one regression lane
- Lake score: do the complete honest live-planning fix now, not the wording-only shortcut
