# ORCH_PLAN: C1b Planning Quality and Live-Surface Credibility Proof

## Summary

Repository: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff workspace: `/Users/spensermcconnell/__Active_Code/forge`  
Kickoff branch context: `feat/planning-strategy`  
Kickoff dirty state: `PLAN.md` modified in the root workspace and remains
authoritative for this run  
Authoritative plan source: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`

This runbook replaces the stale root orchestration for `C1a`. It defines the
parent-agent execution model for the full `C1b` milestone from kickoff through
final acceptance.

This run must deliver all six `PLAN.md` slices:

1. Slice 1: Contract Freeze
2. Slice 2: Live Evidence Planning Runtime
3. Slice 3: Reporting and Integrity Projection
4. Slice 4: Operator Surface, CLI, and Example Credibility
5. Slice 5: Quality Gates and Shared-Family Non-Regression
6. Slice 6: Provider-Backed Review Proof

Current repo reality that changes orchestration mechanics:

- the authoritative `PLAN.md` is currently dirty in the kickoff workspace
- workers created from `feat/planning-strategy` worktrees will not
  automatically inherit that
  uncommitted `PLAN.md`
- the parent must snapshot `PLAN.md` and this `ORCH_PLAN.md` into the state
  root before dispatch and must packet workers against those snapshots, not
  branch-local copies
- `PLAN.md` is already updated and is not parent-owned for this run; do not
  rewrite it, revert it, or require workers to edit it
- the repository already has many historical worktrees under
  `.codex-worktrees/`, `forge.worktrees/`, and other sibling roots; `C1b` uses
  a fresh sibling root to avoid collisions

The parent is the only integrator. Workers own narrow lanes. The parent owns
branch creation, worktree creation, freeze publication, queue state, merge
order, conflict resolution, reopen decisions, the provider-backed proof run,
and final acceptance.

## Hard Guards

1. `PLAN.md` is authoritative. If this file and the current root `PLAN.md`
   disagree, follow the current root `PLAN.md`.
2. The parent must preserve the dirty root `PLAN.md` exactly as found at
   kickoff.
3. Scope is limited to milestone `C1b Planning Quality and Live-Surface
   Credibility Proof`.
4. Do not widen into new planning families, new workflow DSLs, automatic agent
   orchestration, or broad provider-platform redesign.
5. The canonical success path must be deterministic-live and workspace-grounded.
6. `phase_inputs` remain fixture-only for the success path. No silent success
   fallback is allowed.
7. Terminal states remain `success`, `clarification_needed`, and `failed`.
8. The deterministic evidence budget from `PLAN.md` is frozen and may not be
   widened inside lane work without a parent reopen decision.
9. Referential integrity for evidence refs, seam refs, workstream refs, and
   slice refs is merge-blocking.
10. `PLAN.md` and `plan.json` remain the only canonical planning success
    artifacts.
11. `analysis_review_v1` is the shared-family canary and must remain green.
12. No worker may merge, rebase for integration, resolve conflicts, or edit
    another lane's owned files without a parent reopen packet.
13. The parent is the only agent allowed to publish freeze docs, update queue
    state, or change lane ownership.
14. Maximum concurrent worker lanes is `2`.
15. The parent does not ingest full worker transcripts. Worker returns must be
    narrow and structured.
16. Slice 6 is parent-only because it is credentials-bound and must not let a
    worker improvise structural semantics late.
17. Existing historical worktrees are out of scope. Do not reuse or clean them
    as part of `C1b`.
18. Final acceptance is blocked until every required freeze, gate, and proof
    artifact is present under the `C1b` state root.

## Orchestration Runtime Policy

### Parent runtime policy

- Parent owns kickoff, baseline capture, state-root setup, packet writing,
  branch creation, worktree creation, freeze publication, gate review, merges,
  conflict resolution, reopen decisions, provider-proof execution, and final
  acceptance.
- Parent is the only integrator.
- Parent is the only agent allowed to:
  - switch the integration workspace off `feat/planning-strategy`
  - create `codex/c1b-*` branches
  - create or destroy `C1b` worktrees
  - publish artifacts under `.runs/c1b-planning-quality-proof-orch/freezes/`
  - rerun gates on the integrated tree
  - mark the milestone accepted or blocked
- Parent keeps the critical path local for every freeze boundary and every
  integrated regression sweep.

### Worker runtime policy

- Every worker lane runs on `GPT-5.4` with `reasoning_effort=high`.
- Worker lanes run only inside their assigned worktree, their owned files, and
  their parent-issued packet.
- Workers may read frozen artifacts from the state root by absolute path.
- Workers may write only:
  - their lane code/doc/test changes
  - their lane return file
  - their lane blocker files
  - their lane sentinels
- Workers may not mutate `queue.md`, `state.json`, freeze docs, or another
  lane's return artifacts.
- Workers may not widen scope, rename frozen IDs, or change lane dependencies.

### Concurrency policy

Maximum concurrent worker lanes: `2`

Allowed concurrency windows:

- `WS-A` runs alone.
- After `WS-A` merges and `01-contract-freeze.md` is published, `WS-B` and
  `WS-D` run in parallel.
- After `WS-B` merges and `02-runtime-shape-freeze.md` is published, `WS-C` may
  start even if `WS-D` is still active.
- `WS-E` starts only after `WS-B`, `WS-C`, and `WS-D` are merged and frozen.
- Slice 6 runs parent-only after `WS-E`.

This preserves the `PLAN.md` lane logic while keeping the parent's active
context narrow enough to review correctly.

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit gate |
|---|---|---|---|---|
| Phase 0: Kickoff baseline | `task/c1b-p0-1` to `task/c1b-p0-6` | Parent | Strictly serialized | state root, snapshots, and worktree plan frozen |
| Phase 1: Contract freeze | `task/c1b-a-1` to `task/c1b-a-4` | `WS-A` | Runs alone | `gate/c1b-ws-a-contract` |
| Phase 2: Contract merge freeze | `task/c1b-p1-1`, `task/c1b-p1-2` | Parent | Strictly serialized | `01-contract-freeze.md` |
| Phase 3: Runtime and operator surface | `task/c1b-b-*`, `task/c1b-d-*` | `WS-B`, `WS-D` | Parallel | `gate/c1b-ws-b-live-runtime`, `gate/c1b-ws-d-operator-surface` |
| Phase 4: Runtime merge freeze | `task/c1b-p2-1`, `task/c1b-p2-2` | Parent | Strictly serialized | `02-runtime-shape-freeze.md` |
| Phase 5: Reporting and integrity | `task/c1b-c-1` to `task/c1b-c-3` | `WS-C` | May overlap only with `WS-D` if still active | `gate/c1b-ws-c-reporting-integrity` |
| Phase 6: Publication and operator freeze | `task/c1b-p3-1` to `task/c1b-p3-4` | Parent | Strictly serialized | `03-publication-integrity-freeze.md`, `04-operator-surface-freeze.md` |
| Phase 7: Quality gates | `task/c1b-e-1` to `task/c1b-e-4` | `WS-E` | Runs alone | `gate/c1b-ws-e-quality-gates` |
| Phase 8: Quality merge freeze | `task/c1b-p4-1`, `task/c1b-p4-2` | Parent | Strictly serialized | `05-quality-gates-freeze.md` |
| Phase 9: Provider proof | `task/c1b-p5-1` to `task/c1b-p5-4` | Parent | Strictly serialized | `gate/c1b-parent-provider-proof`, `06-provider-proof-freeze.md` |
| Phase 10: Final acceptance | `task/c1b-p6-1` to `task/c1b-p6-4` | Parent | Strictly serialized | `gate/c1b-parent-final-regression`, `gate/c1b-parent-acceptance`, `gate/c1b-complete` |

## Launch Order

1. `task/c1b-p0-1-read-authority`
2. `task/c1b-p0-2-record-baseline`
3. `task/c1b-p0-3-create-state-root`
4. `task/c1b-p0-4-snapshot-authority-files`
5. `task/c1b-p0-5-freeze-invariants`
6. `task/c1b-p0-6-create-integration-branch-and-worktrees`
7. Dispatch `WS-A`
8. Merge `WS-A`
9. Publish `01-contract-freeze.md`
10. Dispatch `WS-B` and `WS-D`
11. Merge `WS-B`
12. Publish `02-runtime-shape-freeze.md`
13. Dispatch `WS-C`
14. Merge `WS-C`
15. Publish `03-publication-integrity-freeze.md`
16. Merge `WS-D`
17. Publish `04-operator-surface-freeze.md`
18. Dispatch `WS-E`
19. Merge `WS-E`
20. Publish `05-quality-gates-freeze.md`
21. Run parent-only Slice 6 provider proof
22. Publish `06-provider-proof-freeze.md`
23. Run parent-only final regression and acceptance

## Workstream Plan

| Lane ID | Slice | Owner | Depends on | Worker or parent | Branch | Gate |
|---|---|---|---|---|---|---|
| `WS-A` | Slice 1: Contract Freeze | Worker | kickoff only | Worker | `codex/c1b-ws-a-contract-freeze` | `gate/c1b-ws-a-contract` |
| `WS-B` | Slice 2: Live Evidence Planning Runtime | Worker | `WS-A` merged + `01-contract-freeze.md` | Worker | `codex/c1b-ws-b-live-runtime` | `gate/c1b-ws-b-live-runtime` |
| `WS-C` | Slice 3: Reporting and Integrity Projection | Worker | `WS-B` merged + `02-runtime-shape-freeze.md` | Worker | `codex/c1b-ws-c-reporting-integrity` | `gate/c1b-ws-c-reporting-integrity` |
| `WS-D` | Slice 4: Operator Surface, CLI, and Example Credibility | Worker | `WS-A` merged + `01-contract-freeze.md` | Worker | `codex/c1b-ws-d-operator-surface` | `gate/c1b-ws-d-operator-surface` |
| `WS-E` | Slice 5: Quality Gates and Shared-Family Non-Regression | Worker | `WS-B`, `WS-C`, `WS-D` merged + freezes `02` to `04` | Worker | `codex/c1b-ws-e-quality-gates` | `gate/c1b-ws-e-quality-gates` |
| `PF` | Slice 6: Provider-Backed Review Proof + final acceptance | Parent | `WS-E` merged + `05-quality-gates-freeze.md` | Parent | `codex/c1b-planning-quality-proof` | `gate/c1b-parent-provider-proof`, `gate/c1b-parent-acceptance` |

### WS-A: Contract Freeze

Purpose: freeze the planning contract so downstream lanes do not guess policy.

Owned files:

- `anvil/harness/types.py`
- `anvil/harness/state.py`
- `anvil/harness/strategy_graph.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/nodes/validator_preflight.py`
- `anvil/harness/nodes/select_strategy.py`
- `anvil/cli.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_semantic_validation.py`
- `tests/test_harness_cli_command.py`

Conditional-touch only:

- `anvil/harness/validation.py`
  - only if contract validation already lives there and moving it would create
    duplication

Must not touch:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/schemas.py`
- `anvil/harness/cli.py`
- `README.md`
- `examples/README.md`
- `docs/contributing.md`

Lane tasks:

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1b-a-1-corpus-and-terminal-freeze` | codify in-corpus, clarification-needed, and failed rules | out-of-corpus asks fail before fake downstream output |
| `task/c1b-a-2-evidence-budget-freeze` | codify the deterministic evidence budget and fixture-only `phase_inputs` semantics | later slices do not need to guess planner policy |
| `task/c1b-a-3-state-and-run-mode-contract` | freeze state fields for provenance, integrity, and run-mode labeling | runtime can report fixture-backed vs deterministic-live vs provider-reviewed |
| `task/c1b-a-4-cli-exit-contract` | freeze operator-visible terminal wording and exit semantics | `success` is the only exit `0` path |

`gate/c1b-ws-a-contract`

```bash
poetry run ruff check anvil/harness/types.py anvil/harness/state.py anvil/harness/strategy_graph.py anvil/harness/semantic_validation.py anvil/harness/nodes/validator_preflight.py anvil/harness/nodes/select_strategy.py anvil/cli.py tests/test_harness_strategy_graph.py tests/test_harness_state_boundaries.py tests/test_harness_semantic_validation.py tests/test_harness_cli_command.py
poetry run pytest -q tests/test_harness_strategy_graph.py tests/test_harness_state_boundaries.py tests/test_harness_semantic_validation.py tests/test_harness_cli_command.py
```

### WS-B: Live Evidence Planning Runtime

Purpose: replace success-path canned replay with bounded live evidence
derivation.

Owned files:

- `anvil/harness/builder.py`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/files.py`
- `anvil/harness/subgraphs/planning_v1.py`
- `anvil/harness/subgraphs/__init__.py`
- `tests/test_harness_planning_graph.py`

Conditional-touch only:

- `anvil/harness/state.py`
  - additive population only against the `WS-A` frozen field names

Must not touch:

- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/schemas.py`
- `anvil/harness/cli.py`
- `anvil/cli.py`
- docs and example surfaces

Lane tasks:

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1b-b-1-bounded-evidence-discovery` | implement bounded workspace evidence discovery | no unbounded crawl and no fake success when `files_hint` resolves to nothing |
| `task/c1b-b-2-live-structure-derivation` | derive rubric findings, seams, workstreams, and slices from inspected files | success-path structure is not copied from success-path `phase_inputs` |
| `task/c1b-b-3-deterministic-runtime-honesty` | preserve deterministic IDs and stop cleanly with `clarification_needed` or `failed` | repeat-run IDs stay stable and blocked runs stay structurally empty |

`gate/c1b-ws-b-live-runtime`

```bash
poetry run ruff check anvil/harness/builder.py anvil/harness/planning_runtime.py anvil/harness/files.py anvil/harness/subgraphs/planning_v1.py anvil/harness/subgraphs/__init__.py tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_graph.py
```

### WS-C: Reporting and Integrity Projection

Purpose: make `PLAN.md` and `plan.json` a single canonical projection with
publish-time integrity checks.

Owned files:

- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/schemas.py`
- `anvil/harness/validation.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_reporting.py`

Must not touch:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/cli.py`
- `anvil/cli.py`
- docs and example surfaces

Lane tasks:

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1b-c-1-canonical-projection` | project deterministic-live payloads into `PLAN.md` and `plan.json` with shared ordering and IDs | the two artifacts cannot disagree silently |
| `task/c1b-c-2-referential-integrity-publish-gate` | validate evidence refs, seam refs, workstream refs, and slice refs before success publication | invalid references fail before success artifacts are written |
| `task/c1b-c-3-terminal-alignment` | align summary payload and artifact terminal semantics | summary payload and published artifact stay in lockstep |

`gate/c1b-ws-c-reporting-integrity`

```bash
poetry run ruff check anvil/harness/reporting.py anvil/harness/report.py anvil/harness/schemas.py anvil/harness/validation.py tests/test_harness_planning_artifacts.py tests/test_harness_reporting.py
poetry run pytest -q tests/test_harness_planning_artifacts.py tests/test_harness_reporting.py
```

### WS-D: Operator Surface, CLI, and Example Credibility

Purpose: make the canonical repo-root planning path runnable and honest.

Owned files:

- `anvil/harness/cli.py`
- `README.md`
- `examples/README.md`
- `docs/contributing.md`
- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- `examples/harness/tasks/deterministic_feature_planning_success.yaml`
- `examples/harness/tasks/deterministic_feature_planning_clarification.yaml`
- `examples/harness/tasks/deterministic_feature_planning_failed.yaml`
- `tests/test_harness_standalone_cli.py`
- `tests/test_docs_surface.py`
- `tests/test_harness_example_strategy_wiring.py`

Conditional-touch only:

- `anvil/cli.py`
  - workspace default and rescue messaging only; no changes to frozen exit-code
    semantics or terminal state vocabulary without a parent reopen
- `tests/test_harness_cli_command.py`
  - only if the canonical repo-root command or rescue wording requires a narrow
    assertion update

Must not touch:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `anvil/harness/schemas.py`

Lane tasks:

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1b-d-1-cli-workspace-default` | default `--workspace` to the current working directory on the canonical harness path | the canonical hello-world command works from repo root |
| `task/c1b-d-2-rescue-messaging` | tighten missing-binary and missing-auth rescue messaging | failure modes tell operators what to do next |
| `task/c1b-d-3-example-and-doc-honesty` | align docs and examples to the real bounded planning surface and provider-family story | examples stop implying broader capability than the runtime supports |

`gate/c1b-ws-d-operator-surface`

```bash
poetry run ruff check anvil/harness/cli.py anvil/cli.py tests/test_harness_standalone_cli.py tests/test_docs_surface.py tests/test_harness_example_strategy_wiring.py tests/test_harness_cli_command.py
poetry run pytest -q tests/test_harness_standalone_cli.py tests/test_docs_surface.py tests/test_harness_example_strategy_wiring.py tests/test_harness_cli_command.py
```

Docs and example surfaces are verified through the pytest layer in this gate.
Do not run Ruff directly against Markdown or YAML files.

### WS-E: Quality Gates and Shared-Family Non-Regression

Purpose: make fake completeness impossible to merge and keep shared harness
families safe.

Owned files:

- `tests/test_harness_planning_graph.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_harness_strategy_graph.py`
- `tests/test_harness_cli_command.py`
- `tests/test_harness_standalone_cli.py`
- `tests/test_harness_provider_adapter.py`
- `tests/test_docs_surface.py`
- `tests/test_harness_analysis_review_graph.py`
- `tests/test_lg_offline_smoke.py`

Conditional-touch only:

- `examples/harness/tasks/`
- `examples/harness/strategies/`
  - only if a docs-smoke or regression fixture must change after the `04`
    freeze and the parent explicitly reopens the lane

Must not touch:

- runtime modules
- publication modules
- CLI implementation modules
- docs prose outside test fixtures

Lane tasks:

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1b-e-1-live-success-coverage` | prove success-path planning is live-derived and deterministic | canned replay cannot pass as success |
| `task/c1b-e-2-integrity-and-parity-coverage` | add referential-integrity and artifact-parity coverage | invalid refs or ordering mismatches block merge |
| `task/c1b-e-3-docs-smoke-coverage` | add executable coverage for the literal canonical docs command | repo-root hello-world smoke stays real |
| `task/c1b-e-4-shared-family-canary` | keep `analysis_review_*` routing, examples, and one offline smoke path green | planning changes do not regress the shared family |

`gate/c1b-ws-e-quality-gates`

```bash
poetry run pytest -q tests/test_harness_planning_graph.py tests/test_harness_planning_artifacts.py tests/test_harness_example_strategy_wiring.py tests/test_harness_strategy_graph.py tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py tests/test_harness_provider_adapter.py tests/test_docs_surface.py tests/test_harness_analysis_review_graph.py tests/test_lg_offline_smoke.py
```

### PF: Provider-Backed Review Proof and Final Acceptance

Purpose: run the narrow provider-backed credibility proof only after the
deterministic-live path, publication surface, operator surface, and quality
gates are all frozen.

Parent-only surfaces:

- `.runs/c1b-planning-quality-proof-orch/acceptance/provider-proof/`
- `.runs/c1b-planning-quality-proof-orch/freezes/06-provider-proof-freeze.md`
- one named provider-backed acceptance config or command surface under
  `examples/harness/live_acceptance/` if `WS-D` or `WS-E` did not already add
  it during implementation

Parent tasks:

| Task ID | Required work | Acceptance focus |
|---|---|---|
| `task/c1b-p5-1-verify-proof-entrypoint` | verify the named config or command surface exists and matches frozen semantics | provider proof has a stable home |
| `task/c1b-p5-2-run-provider-proof` | run one canonical provider-backed review or challenge pass when credentials and binaries are present | provider-backed review runs end-to-end |
| `task/c1b-p5-3-capture-proof-artifacts` | record command, environment prerequisites, output paths, and proof artifact set under the state root | proof is reproducible and reviewable |
| `task/c1b-p5-4-freeze-proof-home` | publish the final owner path and operating instructions | proof does not rot as a one-off demo |

## Approvals and Freeze Gates

The parent publishes exactly six freeze artifacts. Downstream lanes may rely
only on published freezes, not on worker intent.

| Freeze | Published after | Contents |
|---|---|---|
| `freezes/00-kickoff-baseline.md` | kickoff baseline | root branch, head SHA, dirty files, authority snapshot paths, branch/worktree plan |
| `freezes/01-contract-freeze.md` | `WS-A` merged and re-gated | corpus rules, terminal semantics, evidence budget, run-mode vocabulary, frozen state keys, CLI exit semantics |
| `freezes/02-runtime-shape-freeze.md` | `WS-B` merged and re-gated | live payload shape, deterministic ID rules, blocked-state empties, provenance expectations |
| `freezes/03-publication-integrity-freeze.md` | `WS-C` merged and re-gated | publish-time parity rules, integrity checks, artifact ordering, failure semantics |
| `freezes/04-operator-surface-freeze.md` | `WS-D` merged and re-gated | canonical repo-root command, workspace default semantics, rescue messaging, example filenames |
| `freezes/05-quality-gates-freeze.md` | `WS-E` merged and re-gated | merge-blocking test set, shared-family canary set, docs smoke command, repeat-run expectations |
| `freezes/06-provider-proof-freeze.md` | parent proof run complete | named proof home, prerequisite list, command surface, captured artifact paths, last verified date |

Approval rules:

- A lane is not considered accepted when the worker says "done". It is accepted
  only when the parent reruns the lane gate on the lane branch or integrated
  branch and records the result under `gates/`.
- A downstream lane may start only after the required freeze exists.
- Any frozen contract drift requires a parent reopen decision and a new freeze
  revision note.

## Worktree and Branch Plan

Integration workspace:

- Path: `/Users/spensermcconnell/__Active_Code/forge`
- Initial branch context: `feat/planning-strategy`
- Integration branch: `codex/c1b-planning-quality-proof`
- Owner: parent only

Sibling worktree root:

- `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/`

Worker worktrees:

- `WS-A`
  - Path:
    `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/ws-a-contract-freeze`
  - Branch: `codex/c1b-ws-a-contract-freeze`
- `WS-B`
  - Path:
    `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/ws-b-live-runtime`
  - Branch: `codex/c1b-ws-b-live-runtime`
- `WS-C`
  - Path:
    `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/ws-c-reporting-integrity`
  - Branch: `codex/c1b-ws-c-reporting-integrity`
- `WS-D`
  - Path:
    `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/ws-d-operator-surface`
  - Branch: `codex/c1b-ws-d-operator-surface`
- `WS-E`
  - Path:
    `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/ws-e-quality-gates`
  - Branch: `codex/c1b-ws-e-quality-gates`

Branch rules:

- Parent creates `codex/c1b-planning-quality-proof` from the current
  `feat/planning-strategy` head after baseline capture. Do not clean or stash
  the dirty root `PLAN.md`.
- Worker branches are created from the integration branch head, not from
  historical feature branches.
- Worker packets must point to authority snapshots under `.runs/.../inputs/`
  because the current root `PLAN.md` is uncommitted.

## Orchestration State Root

State root:

- `.runs/c1b-planning-quality-proof-orch/`

Required layout:

- `.runs/c1b-planning-quality-proof-orch/queue.md`
- `.runs/c1b-planning-quality-proof-orch/state.json`
- `.runs/c1b-planning-quality-proof-orch/session.log`
- `.runs/c1b-planning-quality-proof-orch/inputs/`
- `.runs/c1b-planning-quality-proof-orch/handoffs/`
- `.runs/c1b-planning-quality-proof-orch/returns/`
- `.runs/c1b-planning-quality-proof-orch/gates/`
- `.runs/c1b-planning-quality-proof-orch/freezes/`
- `.runs/c1b-planning-quality-proof-orch/blockers/`
- `.runs/c1b-planning-quality-proof-orch/sentinels/`
- `.runs/c1b-planning-quality-proof-orch/acceptance/`

Required input snapshots:

- `inputs/PLAN.session.md`
- `inputs/ORCH_PLAN.session.md`
- `inputs/git-baseline.txt`
- `inputs/worktree-inventory.txt`

Queue rules:

- `queue.md` is the canonical task ledger.
- One row per `task/c1b-*`.
- Minimum columns:
  - `task_id`
  - `lane`
  - `owner`
  - `depends_on`
  - `status`
  - `gate`
  - `branch`
  - `worktree`
  - `reopen_count`
  - `blocker_artifact`

State rules:

- `state.json` tracks:
  - current phase
  - integration branch
  - active lanes
  - merged lanes
  - published freezes
  - blockers
  - final verdict

Return rules:

- each worker writes one return file:
  - `returns/ws-a-return.md`
  - `returns/ws-b-return.md`
  - `returns/ws-c-return.md`
  - `returns/ws-d-return.md`
  - `returns/ws-e-return.md`
- each return file must contain only:
  - summary of landed changes
  - touched files
  - commands run
  - observed risks
  - explicit reopen requests, if any

## Sentinel, Queue, and Blocker Protocol

Sentinels live under:

- `.runs/c1b-planning-quality-proof-orch/sentinels/`

Required sentinel names:

- `ws-a.dispatched`
- `ws-a.ready`
- `ws-a.blocked`
- `ws-a.merged`
- `ws-a.reopened`
- repeat for `ws-b`, `ws-c`, `ws-d`, and `ws-e`
- `parent.provider-proof.ready`
- `parent.acceptance.complete`

Sentinel meanings:

- `.dispatched`
  - parent issued the packet and opened the lane
- `.ready`
  - worker claims the lane gate is ready for parent verification
- `.blocked`
  - worker cannot proceed without a parent decision
- `.merged`
  - parent merged the lane and reran its gate successfully
- `.reopened`
  - parent rejected the lane gate or found integration drift and issued a new
    narrow blocker packet

Blocker artifacts live under:

- `.runs/c1b-planning-quality-proof-orch/blockers/`

Blocker file naming:

- `blockers/ws-<lane>/<timestamp>-<slug>.md`

Every blocker file must state:

- exact blocked task ID
- reason for block
- frozen files or strings involved
- one required parent decision
- one recommended next action

Reopen protocol:

1. Parent records the failed gate or integration conflict under `gates/`.
2. Parent writes a blocker artifact under `blockers/`.
3. Parent increments `reopen_count` in `queue.md`.
4. Parent touches `<lane>.reopened`.
5. Worker may address only the recorded blocker scope before returning again.

## Context-Control Rules

1. Parent reads the root `PLAN.md` and this `ORCH_PLAN.md` once at kickoff,
   snapshots both, and then works from the snapshots plus freeze docs.
2. Parent does not ask workers to read branch-local `PLAN.md` because the
   authoritative file is dirty and uncommitted in the kickoff workspace.
3. Parent keeps only one active freeze, one active worker packet, one gate
   result, and the queue row for the current lane in active context.
4. Parent does not ingest full worker transcripts, chain-of-thought, or broad
   exploratory notes.
5. Parent reads worker return files before opening code diffs.
6. Parent opens only the owned files listed in the worker packet unless a
   blocker requires more.
7. Parent resolves cross-lane questions by updating a freeze doc, not by
   relaying ad hoc chat between workers.
8. Workers receive only:
   - the lane packet
   - the required freeze docs
   - the exact gate command
   - the absolute path to authority snapshots
9. Workers do not receive full transcripts from other lanes.
10. If a lane needs a wider contract than its packet or freeze allows, it must
    block and wait. It may not infer new scope locally.

## Merge Order

Merge order is fixed:

1. `WS-A`
2. `WS-B`
3. `WS-C`
4. `WS-D`
5. `WS-E`
6. parent-only Slice 6 proof
7. parent-only final acceptance

Rules:

- `WS-D` may finish before `WS-C`, but it does not merge until the parent has
  published `03-publication-integrity-freeze.md` and verified that docs and CLI
  language still match the final publication surface.
- `WS-E` never starts against moving runtime, publication, or docs surfaces.
- If merging one lane invalidates another lane's freeze assumptions, the parent
  reopens the downstream lane instead of patching it directly on the
  integration branch.

## Tests and Acceptance

### Parent gate recording

Every gate rerun is recorded under:

- `.runs/c1b-planning-quality-proof-orch/gates/<gate-name>.md`

Each gate record must include:

- branch and worktree path
- exact commands
- pass or fail verdict
- touched files reviewed
- blocker link if failed

### Required final integrated gates

`gate/c1b-parent-final-regression`

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_provider_adapter.py
poetry run pytest -q tests/test_harness_cli_command.py
poetry run pytest -q tests/test_harness_standalone_cli.py
poetry run pytest -q tests/test_docs_surface.py
poetry run pytest -q tests/test_harness_analysis_review_graph.py
poetry run pytest -q tests/test_lg_offline_smoke.py
```

`gate/c1b-parent-hello-world`

```bash
poetry run python -m anvil.cli harness-run --task examples/harness/tasks/deterministic_feature_planning_success.yaml --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml --out-root .forge-harness-runs --json
```

`gate/c1b-parent-provider-proof`

- run the named provider-backed proof command or config surface after verifying
  prerequisites
- if credentials or binaries are missing, record the exact missing prerequisite
  and stop acceptance; do not mark `C1b` complete

### Final acceptance flow

1. Confirm `WS-A` through `WS-E` are merged and every freeze `00` through `05`
   exists.
2. Rerun `gate/c1b-parent-final-regression` on the integrated tree.
3. Run `gate/c1b-parent-hello-world` from repo root and capture emitted
   `PLAN.md` and `plan.json` paths under
   `.runs/c1b-planning-quality-proof-orch/acceptance/hello-world/`.
4. Verify the hello-world output reports the correct run mode and non-zero exit
   behavior for blocked terminals.
5. Run `gate/c1b-parent-provider-proof` and capture the proof artifact set under
   `.runs/c1b-planning-quality-proof-orch/acceptance/provider-proof/`.
6. Verify every `PLAN.md` acceptance checklist item from section 13 is satisfied.
7. Publish `06-provider-proof-freeze.md`.
8. Record the final verdict in `state.json`, `queue.md`, and `session.log`.

Acceptance is green only when all of the following are true:

- success-path planning is live-derived, not success-path `phase_inputs` replay
- referential integrity is enforced at publication time
- deterministic IDs survive repeat runs on the same fixture
- the canonical repo-root command works and tells the truth
- `analysis_review_*` stays green
- one provider-backed review proof has a named home and a captured artifact set

## Assumptions

1. The current root `PLAN.md` content is the real C1b authority even though it
   is uncommitted. That is why worker packets must target the state-root
   snapshots.
2. The current `feat/planning-strategy` head at kickoff is the correct base for
   the integration branch.
3. The fresh sibling worktree root
   `/Users/spensermcconnell/__Active_Code/forge.worktrees/c1b-planning-quality-proof/`
   is available and will not collide with historical worktree roots.
4. Slice 6 credentials and binaries may not be present in every local
   environment. If they are missing, the milestone remains blocked until the
   proof is run in an environment that satisfies the prerequisites.
5. `WS-D` can develop in parallel with `WS-B` against the `01` freeze, but its
   merge still waits for `03-publication-integrity-freeze.md` so the docs do
   not get ahead of the artifact surface.
