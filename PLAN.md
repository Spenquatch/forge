# PLAN: C1b Planning Quality and Live-Surface Credibility Proof

Status: ready for implementation on `main`  
Target branch: `main`  
Milestone: `C1`  
Sub-milestone: `C1b`  
Prepared from repo state on: `2026-05-17`

Unified from:
- `/Users/spensermcconnell/.gstack/projects/Spenquatch-forge/spensermcconnell-main-c1b-planning-quality-proof-design-20260517-165308.md`
- `/Users/spensermcconnell/.gstack/projects/Spenquatch-forge/spensermcconnell-main-c1b-test-plan-20260517-165308.md`

Supersedes:
- the prior root `PLAN.md` for the C1a deterministic planning compiler wedge
- the split C1b design/test-plan drafts

## Executive Summary

`C1a` proved the compiler wedge. The repo can route `planning_v1`, emit
`PLAN.md`, and emit `plan.json`.

That is not the same as proving the planner is real.

Today `anvil/harness/planning_runtime.py` still turns declared `phase_inputs`
into a planning-shaped artifact. The graph shape is honest. The planning quality
is not yet earned.

`C1b` is the milestone that closes that gap. It makes the canonical planning
path derive structure from bounded live repo evidence, preserves deterministic
IDs and artifact structure, keeps shared harness families safe, repairs the
operator-facing docs/examples, and adds one explicit provider-backed review
proof that can challenge the plan without owning the structural output.

This is intentionally a bounded proof milestone. It does not widen the planning
corpus, add a second planning engine, or turn Forge into a generic freeform
planner.

## 1. Objective, Problem, and Success Bar

### 1.1 Objective

Ship one bounded, deterministic, workspace-grounded planning path that:

- accepts existing-repo feature, refactor, and automation asks within the
  current planning corpus
- derives seams, workstreams, and slices from live workspace evidence on the
  success path
- publishes `PLAN.md` and `plan.json` with stable structure and stable IDs
- fails honestly with `clarification_needed` or `failed` when the ask is out of
  corpus or under-specified
- preserves existing non-planning harness behavior, especially
  `analysis_review_v1`
- provides one explicit provider-backed challenge path without giving the
  provider ownership of the canonical structural plan

### 1.2 Problem Statement

Right now the planning surface is too close to demoware.

The risk is not "the graph does not compile." The graph already compiles.

The real risk is worse:

- the documented planning path still feels canned
- the emitted plan can be schema-valid but operationally hollow
- the example and docs surface can drift from what the runtime really supports
- planning changes can leak into shared harness seams and quietly regress
  `analysis_review`

If that ships, users will trust the feature less than they would trust an
honest "not ready yet."

### 1.3 Done Means

`C1b` is done only when all of the following are true:

- the canonical success path synthesizes structural output from bounded live
  repo evidence, not success-path `phase_inputs`
- `phase_inputs` remain allowed only for fixture-mode regression paths and are
  labeled as such
- in-corpus, clarification-needed, and failed behavior is explicit and tested
- every emitted `repo_evidence_ref.path`, seam reference, workstream reference,
  and slice reference passes referential-integrity validation
- the canonical hello-world command is copy-pasteable from repo root and honest
  about what mode ran
- `analysis_review_*` strategies still route to `analysis_review_v1`, preserve
  example wiring, and preserve one offline smoke path
- one provider-backed planning review proof exists with a named home and clear
  ownership
- the merged test plan below is strong enough to block fake completeness

## 2. Step 0: Scope Challenge

### 2.1 What Already Exists

| Sub-problem | Existing code | C1b decision |
|---|---|---|
| Planning runtime family and routing already exist | `anvil/harness/builder.py`, `anvil/harness/strategy_graph.py`, `anvil/harness/subgraphs/planning_v1.py` | Reuse the family and graph topology. Deepen behavior, do not redesign routing. |
| Planning artifact publication already exists | `anvil/harness/reporting.py`, `anvil/harness/report.py`, `tests/test_harness_planning_artifacts.py` | Keep the artifact contract. Strengthen how records are produced and validated. |
| Planning config contracts already exist | `anvil/harness/types.py`, `anvil/harness/schemas.py`, `examples/harness/strategies/deterministic_feature_planning_v1.yaml` | Keep one config surface. Remove success-path dependence on canned `phase_inputs`. |
| Graph-owned planning state already exists | `anvil/harness/state.py`, `tests/test_harness_state_boundaries.py` | Reuse the state surface. Extend it only where provenance or integrity needs to be explicit. |
| Example and graph wiring coverage already exists | `tests/test_harness_example_strategy_wiring.py`, `tests/test_harness_strategy_graph.py`, `tests/test_harness_planning_graph.py` | Extend the current regression perimeter instead of creating a second one. |
| Provider-family keys already exist | `config/models.yaml`, `anvil/harness/providers.py`, `anvil/providers/__init__.py` | Do not invent fake alias work. Fix clarity and tests around family-key versus concrete-provider naming. |
| CLI and docs entrypoints already exist | `anvil/cli.py`, `anvil/harness/cli.py`, `README.md`, `examples/README.md`, `docs/contributing.md` | Keep these as the canonical operator surface and make them truthful. |

### 2.2 Minimum Complete Scope

Skipping any item below turns `C1b` into polish instead of proof:

1. Replace success-path `phase_inputs` replay with bounded live evidence
   synthesis in `anvil/harness/planning_runtime.py`.
2. Freeze explicit corpus-membership, evidence-sufficiency, and deterministic
   evidence-budget rules.
3. Add referential-integrity validation for evidence refs, seams, workstreams,
   and slices.
4. Preserve deterministic IDs and canonical section ordering across repeat runs.
5. Tighten the operator surface so docs, examples, and CLI semantics match
   reality.
6. Add a shared-family non-regression gate for `analysis_review_v1`.
7. Add one provider-backed review proof that annotates or challenges the
   deterministic plan without owning structural output.
8. Keep the design doc and test plan merged into this root `PLAN.md`.

### 2.3 Complexity Verdict

This milestone is cross-cutting, but it is still the minimum honest diff.

It touches shared seams:

- planning runtime behavior
- graph/runtime contracts
- reporting and validation
- CLI surface
- docs/examples
- regression coverage

What would be overbuilt:

- a second planning family beyond `deterministic_feature_planning_v1`
- public workflow composition
- broad provider-platform redesign
- automatic agent or worktree dispatch
- per-phase model optimization
- repo-wide unrelated refactors

### 2.4 Search/Build Verdict

This is mostly a Layer 1 reuse milestone with one Layer 3 constraint.

Layer 1 reuse:

- keep `TaskSpec.from_dict(...)` and `StrategyConfig.from_dict(...)` as the only
  config loaders
- keep `build_strategy_graph_spec(...)` as the runtime metadata authority
- keep `build_harness_langgraph(...)` as the shared graph builder
- keep `publish_state_artifacts_v1(...)` as the top-level write seam
- keep the current artifact family: `PLAN.md` plus `plan.json`

Layer 3 constraint:

- the planner must derive structure from bounded live workspace evidence on the
  canonical success path

That is the whole game for `C1b`.

### 2.5 Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Canonical planning path | deterministic-live, workspace-grounded | Trust comes from repeatable evidence, not prose flair. |
| Provider role in C1b | review/challenge layer only | Provider output may annotate or challenge, but may not silently rewrite canonical seams, workstreams, or slices. |
| `phase_inputs` semantics | fixture-only, never silent success fallback | Otherwise `C1b` can fake quality with preauthored payloads. |
| Corpus boundary | existing-repo bounded planning only | Keep scope honest and testable. |
| Workspace writes during planning | default read-only | Planning is inspection plus artifact emission, not repo mutation. |
| Provider naming story | keep `codex_cli` and `claude_code` family keys valid | The repo already supports them. The problem is clarity and verification, not missing aliases. |
| CLI ergonomics | allow the canonical hello-world from repo root without tribal setup | TTHW must be real, not aspirational. |
| Shared-family safety | `analysis_review_v1` is the explicit canary | Planning changes touch shared seams. Regressions must be blocked. |

### 2.6 TODO Cross-Reference

`docs/project_management/future/TODOS.md` does not contain a blocker that must
be folded into `C1b`.

If `C1b` surfaces worthwhile follow-on work, capture it after the planner is
credible. Do not widen the milestone preemptively.

### 2.7 NOT in Scope

- widening the planning corpus beyond the current bounded classes
- arbitrary greenfield or multi-repo planning
- broad provider registry cleanup outside the harness and documented example
  surfaces
- multi-provider or per-phase model experimentation
- automatic agent or worktree orchestration
- public workflow DSLs
- repo-wide unrelated lint, format, or type cleanup

## 3. Frozen Planning Contract

### 3.1 Supported request shape

A request is in corpus when all of the following hold:

- `task_kind == planning`
- the ask targets one existing repo
- bounded evidence resolution yields between 1 and 25 concrete workspace paths
- those paths collapse into at most 3 plausible seam groups
- the first implementation cut can be defined from repo evidence without hidden
  external context

### 3.2 Terminal states

Canonical terminal states:

- `success`
- `clarification_needed`
- `failed`

Return `clarification_needed` when the request appears in corpus but the runtime
cannot choose a primary cut credibly after one bounded scan.

Concrete triggers:

- `files_hint` resolves to 0 workspace paths
- more than one primary seam candidate remains within a close score band
- a required dependency path is mentioned but not found
- acceptance criteria cannot be grounded in inspected files

Return `failed` when the ask is outside the bounded planning corpus.

Concrete triggers:

- explicit greenfield or "build a new app/system" asks
- multi-repo or multi-team migration asks
- hidden external-system dependency is required before any trustworthy seam can
  be chosen
- bounded evidence resolution exceeds 25 candidate files or more than 3 seam
  clusters even after narrowing

### 3.3 Deterministic evidence budget

Freeze one first-pass budget:

- inspect up to 25 matched workspace paths
- read up to 12 files
- read up to 150 KB of file content total
- allow one narrowing pass beyond direct `files_hint` matches

If the runtime cannot produce a credible primary seam inside that budget, it
must clarify or fail. It may not silently widen into an unbounded repo crawl.

### 3.4 Referential-integrity rules

Planning outputs must validate all of the following before a success artifact is
published:

- every `repo_evidence_ref.path` exists inside the workspace snapshot
- every seam path exists inside the workspace snapshot
- every workstream `seam_id` resolves to a declared seam
- every slice `workstream_id` resolves to a declared workstream
- every slice `seam_id` resolves to a declared seam
- every slice has at least one concrete acceptance criterion

### 3.5 Structural invariants

The canonical artifact contract stays small and explicit.

Canonical human artifact sections:

1. problem statement
2. rubric results
3. architectural seams
4. parallel workstreams or worktrees
5. executable slices

Canonical structural invariants:

- stable seam, workstream, and slice IDs across repeat runs on the same input
- deterministic section order
- explicit provenance for why each seam, workstream, and slice exists
- provider-backed annotations may not mutate canonical structural IDs

## 4. Architecture Review

### 4.1 Current behavior gap

The current planning surface already routes correctly, but it still centers on
declared phase payload replay:

```text
task yaml + strategy yaml
        │
        ▼
select strategy / route planning_v1
        │
        ▼
planning_runtime
        │
        ├── reads declared phase_inputs
        ├── normalizes payloads
        └── republishes seams/workstreams/slices
        │
        ▼
reporting.publish_state_artifacts_v1
        │
        ├── PLAN.md
        └── plan.json
```

That proves shape. It does not prove planning quality.

### 4.2 Target architecture

```text
task yaml (task_kind=planning)
strategy yaml (runtime_target=planning_v1)
        │
        ▼
validator_preflight
        │
        ├── corpus fit checks
        ├── policy checks
        └── strategy/runtime compatibility checks
        │
        ▼
planning_v1 subgraph
        │
        ▼
planning_runtime
        │
        ├── bounded workspace evidence discovery
        ├── rubric derivation
        ├── seam derivation
        ├── workstream derivation
        ├── slice derivation
        ├── referential-integrity validation
        └── clarification/failure decision
        │
        ▼
optional provider-backed challenge layer
        │
        └── annotations only, no structural ownership
        │
        ▼
reporting.publish_state_artifacts_v1
        │
        ├── PLAN.md
        └── plan.json
```

### 4.3 Module ownership map

| Concern | Canonical owner | Required outcome |
|---|---|---|
| Task and strategy parsing | `anvil/harness/types.py` | One typed config surface. No second parser stack. |
| Runtime-family metadata | `anvil/harness/strategy_graph.py` | `planning_v1` metadata stays explicit and shared-family safe. |
| Shared graph construction | `anvil/harness/builder.py` | No topology rewrite, only behavior deepening. |
| Planning phase execution | `anvil/harness/planning_runtime.py` | Live evidence derivation, deterministic IDs, honest stops. |
| Planning runtime entrypoint | `anvil/harness/subgraphs/planning_v1.py` | Thin wrapper only. |
| Graph-owned planning state | `anvil/harness/state.py` | Provenance and integrity fields are first-class. |
| Artifact projection and publication | `anvil/harness/reporting.py` | One publication seam for `PLAN.md` and `plan.json`. |
| Machine validation | `anvil/harness/schemas.py`, `anvil/harness/validation.py` | Schema plus referential-integrity checks stay enforceable. |
| Operator CLI surface | `anvil/cli.py`, `anvil/harness/cli.py` | Canonical command, clear terminal semantics, usable rescue messages. |

### 4.4 Production failure scenarios by seam

| Seam | Realistic failure | Planned guard |
|---|---|---|
| `validator_preflight` | a greenfield ask slips through as planning and yields fake structure | explicit in-corpus/out-of-corpus checks plus failure tests |
| `planning_runtime` evidence discovery | `files_hint` resolves to nothing but runtime keeps going | bounded evidence gate plus `clarification_needed` tests |
| seam derivation | two primary seams tie and the runtime picks one nondeterministically | deterministic tie handling plus clarification path |
| workstream derivation | circular or fake-independent workstreams are emitted | dependency validation plus workstream tests |
| artifact publication | `PLAN.md` and `plan.json` disagree on IDs or order | shared artifact projection tests |
| provider-backed review layer | provider annotations rewrite structural IDs | freeze structural ownership boundary in code and tests |

### 4.5 Architecture verdict

The graph shape is already good enough. The architecture change is behavioral,
not topological.

Do not add:

- a second planning runtime
- a separate planning-only CLI
- a second reporting path
- a second parser or schema layer

All of those spend complexity without increasing trust.

## 5. Implementation Plan

### Slice 1: Contract Freeze

Goal: freeze the planning contract before changing behavior.

Primary modules:

- `anvil/harness/types.py`
- `anvil/harness/state.py`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/nodes/validator_preflight.py`
- `anvil/cli.py`

Required work:

- codify in-corpus, clarification-needed, and failed rules
- codify the deterministic evidence budget
- mark `phase_inputs` as fixture-only for the canonical success path
- add or tighten state fields needed for provenance and integrity
- freeze exit semantics and operator-visible terminal wording

Acceptance checks:

- out-of-corpus asks fail before fake downstream output
- later slices do not need to guess policy
- the runtime contract can report whether a run was fixture-backed,
  deterministic-live, or provider-reviewed

### Slice 2: Live Evidence Planning Runtime

Goal: make `planning_runtime` derive structure from workspace evidence.

Primary modules:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/subgraphs/planning_v1.py`
- `anvil/harness/files.py`
- `anvil/harness/state.py`

Required work:

- implement bounded workspace evidence discovery
- derive rubric findings from inspected files instead of preauthored payloads
- derive seams from path clusters and coupling hints
- derive workstreams from seams plus dependency boundaries
- derive executable slices with concrete acceptance checks
- validate referential integrity before success publication
- stop with `clarification_needed` or `failed` when the runtime cannot make an
  honest cut

Acceptance checks:

- success-path seams, workstreams, and slices are not copied from success-path
  `phase_inputs`
- repeat-run IDs remain stable
- blocked runs do not leave fake downstream records in state
- emitted structure carries enough provenance to justify the cut

### Slice 3: Reporting and Integrity Projection

Goal: ensure the published artifacts are canonical, aligned, and trustworthy.

Primary modules:

- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/schemas.py`
- `tests/test_harness_planning_artifacts.py`

Required work:

- project the deterministic-live planning payload into both `PLAN.md` and
  `plan.json`
- ensure both artifacts share the same IDs, ordering, and terminal semantics
- validate evidence refs, seam refs, workstream refs, and slice refs at publish
  time
- make structural mismatches impossible to publish as success

Acceptance checks:

- `PLAN.md` and `plan.json` cannot disagree silently
- invalid references fail before success artifacts are written
- summary payload and artifact payload stay aligned

### Slice 4: Operator Surface, CLI, and Example Credibility

Goal: make the documented planning path runnable and honest.

Primary modules:

- `anvil/cli.py`
- `anvil/harness/cli.py`
- `README.md`
- `examples/README.md`
- `docs/contributing.md`
- `examples/harness/strategies/`
- `examples/harness/tasks/`

Required work:

- default `--workspace` to the current working directory when omitted on the
  canonical harness path
- tighten rescue messaging for missing CLI binaries and missing auth
- document the provider-family story clearly
- make the canonical hello-world command copy-pasteable from repo root
- ensure example task and strategy files describe the real bounded planning
  surface

Acceptance checks:

- the literal canonical hello-world command from docs works from repo root
- documented failure modes tell the operator what to do next
- examples no longer imply broader capability than the runtime actually supports

### Slice 5: Quality Gates and Shared-Family Non-Regression

Goal: block fake completeness and protect shared harness behavior.

Primary modules:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_provider_adapter.py`
- `tests/test_docs_surface.py`

Required work:

- add coverage proving the success path is live-derived
- add referential-integrity coverage
- add docs smoke coverage for the canonical command
- keep `analysis_review_*` routing, example, and smoke behavior green
- freeze deterministic repeat-run coverage

Acceptance checks:

- fake planning success via canned replay is impossible without test failures
- the canonical docs or examples command is executable in fixture smoke
- shared-family regressions are caught before merge

### Slice 6: Provider-Backed Review Proof

Goal: add one narrow live credibility proof after deterministic-live behavior is
frozen.

Primary surface:

- one named acceptance config or command surface
- one proof-artifact capture location under a documented owner path
- one explicit manual or nightly workflow home

Required work:

- pick one canonical fixture inside the bounded planning corpus
- run one provider-backed planning review or challenge pass
- capture the artifact set and operating instructions
- document where this proof lives and who owns it

Acceptance checks:

- the provider-backed review can run end-to-end when its prerequisites are
  present
- provider output cannot mutate canonical structural IDs
- the proof has a named home instead of rotting as a one-off demo

## 6. Code Quality and Contract Hygiene

This milestone should leave the harness more explicit, not more abstract.

### 6.1 Keep the diff minimal

- no second parser stack
- no planning-only graph builder
- no parallel reporting path
- no provider alias churn that does not improve operator clarity
- no new service layer unless two existing modules would otherwise duplicate the
  same logic

### 6.2 Bias toward explicit over clever

Preferred implementation style:

- explicit terminal-state branching over polymorphic "magic" dispatch
- explicit provenance fields over inferred hidden state
- explicit integrity checks over best-effort repair
- explicit fixture-mode labels over silent fallback behavior

### 6.3 DRY boundaries

Reuse these seams aggressively:

- `TaskSpec.from_dict(...)`
- `StrategyConfig.from_dict(...)`
- `build_strategy_graph_spec(...)`
- `build_harness_langgraph(...)`
- `publish_state_artifacts_v1(...)`

Do not reuse by copy-pasting planning-specific logic into tests, docs, or the
CLI surface. If the same terminal-state or provenance formatting logic appears
in more than one production module, extract it once.

### 6.4 Diagram maintenance

If touched files already contain nearby ASCII diagrams or structural comments,
update them in the same change. Stale diagrams are worse than no diagrams.

## 7. Test Review

Framework: `pytest`

Coverage target: every new branch introduced by `C1b` gets a deterministic test.
100% of new branches is the goal.

Primary regression perimeter to extend:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_provider_adapter.py`
- `tests/test_docs_surface.py`

### 7.1 Codepath coverage diagram

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/planning_runtime.py
    │
    ├── execute_planning_runtime()
    │   ├── [EXISTING] phase-order execution and terminal recording
    │   ├── [GAP]      live evidence discovery instead of success-path phase replay
    │   ├── [GAP]      evidence-budget enforcement
    │   ├── [GAP]      in-corpus vs clarification-needed vs failed branching
    │   ├── [GAP]      deterministic tie handling for seam selection
    │   └── [GAP]      referential-integrity validation before success publication
    │
    ├── phase payload handling
    │   ├── [EXISTING] fixture-mode phase_inputs normalization
    │   └── [GAP]      explicit fixture-only guard on canonical success path
    │
    └── structural output assembly
        ├── [EXISTING] normalized seams/workstreams/slices payload shape
        └── [GAP]      live-derived provenance and stable-ID assertions

[+] anvil/harness/reporting.py / report.py
    │
    ├── publish_state_artifacts_v1()
    │   ├── [EXISTING] writes planning artifacts on success
    │   ├── [GAP]      blocks mismatched refs or ordering
    │   └── [GAP]      enforces PLAN.md / plan.json parity
    │
    └── terminal payload projection
        ├── [EXISTING] clarification/failed payload publication
        └── [GAP]      mode/provenance visibility in published summary

[+] anvil/cli.py
    │
    ├── harness-run parsing
    │   ├── [EXISTING] explicit --workspace support
    │   ├── [GAP]      default workspace=current working directory
    │   └── [EXISTING] planning exit code 0 only for success
    │
    └── operator rescue surface
        ├── [EXISTING] runtime dependency failures
        └── [GAP]      missing-provider-binary and auth guidance with fix steps

[+] anvil/harness/strategy_graph.py / builder.py
    │
    ├── planning_v1 routing
    │   ├── [EXISTING] planning runtime target selection
    │   └── [GAP]      tighter contract assertions around planning-only semantics
    │
    └── analysis_review_v1 routing
        └── [EXISTING] shared-family route coverage, must stay green

USER / OPERATOR FLOW COVERAGE
===========================
[+] Fixture-backed hello-world planning run
    │
    ├── [EXISTING] success fixture emits PLAN.md and plan.json
    ├── [GAP]      docs command works verbatim from repo root
    └── [GAP]      output states whether run was fixture-backed or deterministic-live

[+] Ambiguous planning ask
    │
    ├── [EXISTING] clarification fixture terminal payload
    └── [GAP]      clarification request names the missing discriminator clearly

[+] Out-of-corpus planning ask
    │
    ├── [EXISTING] failed fixture terminal payload
    └── [GAP]      failed response explains why the ask is unsupported

[+] Provider-backed review proof
    │
    ├── [GAP] [→MANUAL/NIGHTLY] end-to-end review run on canonical plan shape
    └── [GAP] [→MANUAL/NIGHTLY] annotations cannot rewrite structural IDs

────────────────────────────────────────────────────────────
COVERAGE TARGET AFTER C1b:
  All new planning-runtime branches covered
  All terminal paths covered
  All structural-ref integrity checks covered
  Docs smoke covered for the canonical command
  Shared-family non-regression covered
────────────────────────────────────────────────────────────
```

### 7.2 Required test additions

1. Runtime synthesis tests
   - prove a supported planning task can emit seams, workstreams, and slices
     without success-path `phase_inputs`
   - prove deterministic IDs and section ordering remain stable
   - prove canonical success rejects silent canned fallback

2. Clarification and failure tests
   - in-corpus but under-specified asks return `clarification_needed`
   - out-of-corpus asks return `failed`
   - both produce actionable terminal metadata

3. Referential-integrity tests
   - every evidence ref exists in the workspace snapshot
   - every workstream references declared seam IDs only
   - every slice references declared seam and workstream IDs only
   - every slice carries at least one concrete acceptance criterion

4. Artifact-parity tests
   - `PLAN.md` and `plan.json` agree on IDs, order, and terminal semantics
   - invalid references or mismatched ordering fail before success artifacts are
     written

5. Docs and example smoke tests
   - the literal canonical hello-world command from docs runs green in fixture
     smoke
   - the run produces `PLAN.md` and `plan.json`

6. Shared-family non-regression tests
   - canonical `analysis_review_*` strategies still route to
     `analysis_review_v1`
   - canonical `analysis_review_*` example files still build expected graph
     metadata
   - one offline bounded `analysis_review` smoke path still publishes the
     expected surface

7. Provider-backed challenge proof
   - one canonical provider-backed review run is executable end-to-end
   - provider output cannot mutate canonical seam, workstream, or slice IDs

### 7.3 Suggested commands

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_provider_adapter.py
poetry run pytest -q tests/test_harness_cli_command.py
poetry run pytest -q tests/test_harness_standalone_cli.py
poetry run pytest -q tests/test_docs_surface.py
```

If the provider-backed proof becomes scriptable, add one dedicated command and
freeze it in docs plus a manual or nightly gate.

### 7.4 Human acceptance checks

- Solo-builder rubric:
  - can start implementation from emitted slices without inventing missing seams
  - clarification prompts are concrete and answerable
  - plan provenance is visible enough to trust the cut

- Small-team rubric:
  - at least one workstream can start independently
  - cross-workstream dependencies are explicit
  - slices are assignable without rewriting the plan

## 8. Performance and Reliability Review

This is not a throughput milestone, but there are still real performance and
operational footguns to avoid.

### 8.1 Performance risks

| Risk | Why it matters | Required mitigation |
|---|---|---|
| unbounded repo scan | planning latency explodes and determinism degrades | enforce the fixed evidence budget |
| repeated reads of the same files | runtime gets slower while appearing deterministic | dedupe resolved paths before reading |
| oversized artifact payloads | published plans become noisy and unstable | keep provenance bounded and structural, not full-content dumps |
| path-normalization drift | same file can appear under multiple spellings and break ID stability | normalize workspace-relative paths once at the evidence boundary |

### 8.2 Reliability rules

- no success artifact is published after an integrity failure
- blocked planning runs must leave downstream structural lists empty
- exit code `0` is reserved for `success`
- the docs command and the CLI behavior must agree on terminal semantics

### 8.3 Performance verdict

Do not add caching, indexing, or background precomputation in `C1b` unless the
fixed evidence budget proves insufficient. That would spend complexity before we
have evidence it is needed.

## 9. Error & Rescue Registry

| Failure | User-visible impact | Rescue |
|---|---|---|
| request is out of corpus | planner emits nonsense or fake completeness | stop with `failed` and explain why the ask is unsupported |
| request is in corpus but ambiguous | planner guesses the wrong seam | stop with `clarification_needed` and name the missing discriminator |
| success path silently reuses canned payloads | milestone claims credibility without live planning | fail tests that detect canned-success fallback |
| missing CLI binary or auth for provider-backed proof | operator assumes the whole feature is broken | emit problem + cause + fix + docs link, and keep the fixture-backed hello-world separate |
| shared planning change regresses `analysis_review` | main harness family quietly breaks | block merge on shared-family routing, example, and smoke regressions |
| docs or examples drift from behavior | first-time user hits dead or misleading commands | add executable docs smoke and keep docs in scope, not cleanup |

## 10. Failure Modes Registry

| New codepath | Realistic production failure | Test covers it? | Error handling exists? | User-visible outcome | Status |
|---|---|---:|---:|---|---|
| planning task parse | task omits required planning fields | must add | must add | clear invalid-config error before runtime work | required |
| corpus detection | a greenfield or multi-repo ask is treated as valid | must add | must add | fake success or useless clarification if unguarded | critical gap until covered |
| evidence discovery | `files_hint` resolves to nothing but runtime continues anyway | must add | must add | misleading success with invented seams | critical gap until covered |
| seam selection | two primary seams tie and runtime picks nondeterministically | must add | must add | unstable IDs and inconsistent plans | critical gap until covered |
| workstream derivation | workstreams form circular dependencies | must add | must add | fake parallelism, unusable team split | required |
| slice emission | slice references seam or workstream IDs that do not exist | must add | must add | invalid `plan.json`, broken markdown | critical gap until covered |
| plan publication | `PLAN.md` and `plan.json` disagree on ordering or refs | must add | must add | operator mistrust and broken automation | critical gap until covered |
| CLI exit handling | `clarification_needed` exits `0` | existing partial, tighten | existing partial, tighten | automation treats blocked planning as success | critical gap until covered |
| provider-backed review | provider annotations rewrite canonical structural IDs | must add | must add | determinism contract collapses | critical gap until covered |

Any row with "must add" in both the test and error-handling columns is a merge
blocker until implementation covers it.

## 11. DX and Operator Experience

### 11.1 Developer journey map

| Stage | Current experience | C1b target |
|---|---|---|
| Discover planning | planning appears in docs | same |
| Pick command | command exists but trust is unclear | one canonical hello-world command is obvious |
| Pick strategy | canonical strategy exists but still feels fixture-shaped | canonical strategy is honest about fixture versus live behavior |
| Understand providers | family keys and concrete entries can blur together | one clear provider-family story with rescue guidance |
| Run first plan | may feel canned or require tribal setup | first run works from repo root and fails honestly when needed |
| Inspect artifacts | artifact shape is good | artifact shape plus provenance is trustworthy |
| Handle failure | terminal contract exists | failure explains what is missing and what to do next |
| Share with teammate | unclear whether workstreams are trustworthy | workstreams have honest dependency boundaries |
| Repeat with confidence | not there yet | same bounded path works again with stable IDs |

### 11.2 TTHW target

Current TTHW for "get one trustworthy plan" is too high because the operator
may need to debug whether the path is real or canned.

`C1b` target:

- under 5 minutes for one fixture-backed hello-world run from repo root
- explicit second-step provider-backed credibility proof

Canonical hello-world target after Slice 4:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .forge-harness-runs \
  --json
```

That command is only honest if the CLI defaults `--workspace` to the current
working directory and the output clearly states whether the run was
fixture-backed or deterministic-live.

### 11.3 Docs gate

`C1b` adds two docs-surface checks:

1. fixture smoke for the literal canonical hello-world command
2. a named manual or nightly home for the provider-backed review proof

Docs are product surface here. Treat them like code.

## 12. Worktree Parallelization Strategy

### 12.1 Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Contract freeze | `anvil/harness/types.py`, `anvil/harness/state.py`, `anvil/harness/strategy_graph.py`, `anvil/harness/nodes/`, `anvil/cli.py` | — |
| B. Live planning runtime | `anvil/harness/planning_runtime.py`, `anvil/harness/subgraphs/`, `anvil/harness/files.py`, `anvil/harness/state.py` | A |
| C. Reporting and integrity projection | `anvil/harness/reporting.py`, `anvil/harness/report.py`, `anvil/harness/schemas.py`, planning artifact tests | A, B |
| D. Operator surface and docs | `anvil/cli.py`, `anvil/harness/cli.py`, `examples/harness/`, `README.md`, `examples/README.md`, `docs/contributing.md` | A |
| E. Quality gates and non-regression | `tests/`, `examples/harness/tasks/`, `examples/harness/strategies/`, docs smoke | B, C, D |
| F. Provider-backed proof capture | proof config/docs surface, proof artifact capture surface | C, D, E |

### 12.2 Parallel lanes

Lane A: contract freeze  
Sequential foundation lane. Freeze corpus rules, evidence budget, fixture-only
`phase_inputs`, terminal semantics, and required state contract.

Lane B: live planning runtime  
Starts after A. Owns evidence discovery, seam, workstream, and slice derivation.

Lane C: reporting and integrity projection  
Starts after B has the basic live payload shape. Owns publish-time parity and
referential integrity.

Lane D: operator surface and docs  
Starts after A. Owns CLI ergonomics, rescue messaging, example honesty, and the
canonical repo-root command. Can run in parallel with B.

Lane E: quality gates and non-regression  
Starts after B, C, and D settle. Owns the merge-blocking test perimeter.

Lane F: provider-backed proof capture  
Runs last. Depends on the deterministic-live path and operator surface being
stable first.

### 12.3 Execution order

```text
Lane A
  │
  ├──────────────► Lane B ─────► Lane C
  │
  └──────────────► Lane D
                      │
          Lane C + Lane D complete
                      │
                      ▼
                    Lane E
                      │
                      ▼
                    Lane F
```

Execution order:

1. Launch Lane A first and merge it.
2. Launch Lane B and Lane D in parallel worktrees after A freezes the contract.
3. Launch Lane C once B has the live payload shape.
4. Merge B, C, and D.
5. Run Lane E after behavior, publication, and operator surface all settle.
6. Run Lane F last so the live proof documents shipped reality, not a moving
   target.

### 12.4 Conflict flags

- Lanes A and B both touch state and planning contract semantics. B must not
  start before A freezes them.
- Lanes B and C both affect planning payload shape. C must not publish parity
  rules against a moving runtime schema.
- Lanes B and D both affect what the CLI and docs claim a planning run means.
  Keep run-mode vocabulary aligned.
- Lanes D and E both touch examples and docs-backed smoke surfaces. Freeze
  filenames and commands before E starts.
- Lane F depends on the exact structural plan contract. Do not let the
  provider-backed proof invent new structural semantics late.

## 13. Acceptance Checklist

- [ ] success-path planning no longer depends on success-path `phase_inputs`
- [ ] `phase_inputs` remain fixture-only and explicitly labeled when used
- [ ] corpus-membership, clarification-needed, and failed rules are codified
- [ ] deterministic evidence budget is enforced
- [ ] referential-integrity checks cover evidence refs, seams, workstreams, and
      slices
- [ ] stable seam, workstream, and slice IDs survive repeat runs on the same
      fixture
- [ ] the canonical docs command works from repo root
- [ ] missing-binary and missing-auth rescue messages are explicit
- [ ] `analysis_review_*` shared-family routing and smoke coverage stay green
- [ ] `PLAN.md` and `plan.json` remain the canonical successful planning
      artifacts
- [ ] CLI JSON mode returns the planning terminal payload
- [ ] exit code `0` is reserved for `success`
- [ ] one provider-backed review proof exists with a named home and owner

## 14. Completion Summary

- Step 0: scope accepted as a planning-quality milestone, not a new
  planning-platform milestone
- What already exists: mapped and reused; no second parser stack, graph builder,
  or artifact path
- Architecture: graph shape preserved, runtime credibility deepened
- Code quality: explicit contract, no fake alias work, no second runtime
- Test review: coverage diagram merged into this plan and upgraded to block
  canned-success regressions
- Performance review: bounded evidence budget is the primary latency and
  determinism guard
- Failure modes: critical gaps enumerated with explicit merge blockers
- DX: first-run path and provider-backed proof are intentionally separate
- Parallelization: one foundation lane, two mid-flight implementation lanes, one
  publication lane, one test lane, one proof lane
- Lake score: choose the complete trustworthy-planner proof, not the
  schema-valid shortcut
