# ORCH_PLAN: C2 Measurable Coverage Ledger and Assumptions Register

## Summary

Repository: `/home/azureuser/__Active_Code/forge`  
Execution baseline branch: `codex/c1b-planning-quality-proof`  
Primary authority: `/home/azureuser/__Active_Code/forge/PLAN.md`  
Milestone: `C2 Measurable Coverage Ledger and Assumptions Register`

This runbook supersedes the stale root C1b orchestration plan. It is the
parent-owned execution plan for completing the full C2 session defined by
`PLAN.md` on the current branch. The parent agent is the sole integrator.
Workers execute bounded implementation lanes only. Concurrency is
intentionally capped at `2` worker lanes, all on `GPT-5.4/high`.

Completion means the integrated tree proves all C2 outcomes from `PLAN.md`,
including:

- successful planning runs emit `plan_artifact_v2`
- runtime owns `coverage_ledger`, `assumptions_register`, and `uncovered_delta`
- `summary.json` carries truthful partial coverage on
  `clarification_needed` and `failed`
- every required coverage dimension has exactly one ledger row
- cross-record refs use declared `phase_id` values, not `stage_type`
- assumptions resolve correctly
- delta rows exist only for `partial` or `uncovered`
- `PLAN.md` renders coverage sections in canonical order
- no strategy-name branching is introduced
- no parallel helper families are introduced such as `plan_projection_v2()`,
  `render_plan_markdown_v2()`, or `publish_planning_artifacts_v2()`

## Hard Guards

1. `PLAN.md` is the sole authority for scope. If this file and `PLAN.md`
   disagree, follow `PLAN.md`.
2. Scope stops at C2. No multi-strategy coverage framework, no refine adapter,
   no unrelated cleanup, no new planning pipeline.
3. Runtime owns facts, reporting serializes them, validation gates them,
   markdown renders them.
4. Upgrade existing planning helpers in place only. Do not create sibling
   `*_v2()` planning helper families.
5. Keep `plan_projection_v1()`, `render_plan_markdown_v1()`, and
   `publish_planning_artifacts_v1()` as the only planning publication helpers.
6. `summary.json` must carry coverage truth on blocked runs. `PLAN.md` and
   `plan.json` remain success-only artifacts.
7. Cross-record references must use declared `phase_id` values only.
8. The parent is the only agent allowed to merge, rebase for integration,
   resolve conflicts, reopen lane scope, or close the milestone.
9. Do not edit `PLAN.md`.
10. Do not read or rely on `SKILL.md` files.

## Runtime and Orchestration Policy

Parent runtime policy:

- Parent owns kickoff, contract freeze, worktree creation, worker packets,
  merge order, gate review, integration, final regressions, artifact capture,
  and milestone closeout.
- Parent lands Slice A locally on the integration branch before any worker
  dispatch.
- Parent writes the frozen downstream contracts workers must consume:
  - `.runs/c2-measurable-coverage-orch/contract-freeze.md`
  - `.runs/c2-measurable-coverage-orch/runtime-payload-freeze.md`
- Parent reruns every lane gate on the integrated tree before merging.

Worker runtime policy:

- Workers execute only the task IDs, files, and commands in their packet.
- Workers may not change frozen nouns, artifact version targets, coverage
  vocabulary, canonical headings, or merge order.
- Workers return a narrow handoff with exact commands run, exit codes, changed
  files, open blockers, and any assumptions.

Concurrency policy:

- Max concurrent worker lanes: `2`
- Parallel window 1: `WS-B` and `WS-D` after Slice A is merged locally
- Parallel window 2: none
- `WS-C` waits for merged `WS-B` and a parent-published runtime payload freeze
- `WS-E` runs only after `WS-C` and `WS-D` are merged

## Parent Critical Path

| Phase | Tasks | Owner | Mode | Exit gate |
|---|---|---|---|---|
| A. Authority and contract freeze | `task/c2-a1` to `task/c2-a7` | Parent | serialized | `gate/c2-contract-freeze` |
| B. Runtime coverage derivation | `task/c2-b1` to `task/c2-b5` | `WS-B` | after A | `gate/c2-runtime` |
| D. Example surface and docs | `task/c2-d1` to `task/c2-d4` | `WS-D` | parallel with B after A | `gate/c2-docs` |
| C. Projection, rendering, validation | `task/c2-c1` to `task/c2-c5` | `WS-C` | after merged B | `gate/c2-publication` |
| E. Regression wall | `task/c2-e1` to `task/c2-e4` | `WS-E` | after merged C and D | `gate/c2-regression-lane` |
| F. Final integration and closeout | `task/c2-f1` to `task/c2-f7` | Parent | serialized | `gate/c2-final` |

### End-to-End Execution Sequence

1. Parent reads `PLAN.md`, confirms current branch, confirms canonical harness
   CLI surface, and freezes C2 nouns.
2. Parent creates `.runs/c2-measurable-coverage-orch/`, gate templates, and
   sibling worktrees.
3. Parent lands Slice A locally on `codex/c1b-planning-quality-proof`.
4. Parent runs `gate/c2-contract-freeze`. Do not dispatch workers until it
   passes.
5. Parent dispatches `WS-B` and `WS-D` in parallel.
6. Parent reruns `WS-B` gate on the integration tree and merges `WS-B` first.
   Do not proceed to `WS-C` until merged B is green.
7. Parent writes `runtime-payload-freeze.md` from merged B.
8. Parent reruns `WS-D` gate on the integration tree and merges `WS-D`.
9. Parent dispatches `WS-C` with the frozen runtime payload contract.
10. Parent reruns `WS-C` gate on the integration tree and merges `WS-C`.
11. Parent dispatches `WS-E` as a regression-only lane after product surfaces
    stop moving.
12. Parent reruns `WS-E` gate on the integration tree and merges `WS-E`.
13. Parent runs integrated fixture commands, targeted planning tests,
    repo-quality checks, and full `pytest -q`.
14. Parent captures final derived runs, gate results, acceptance notes, and
    closes the milestone.

### Fixed Merge Order

1. Parent-local Slice A
2. `WS-B` runtime truth
3. `WS-D` docs/examples
4. `WS-C` projection/render/validation
5. `WS-E` regression-only lane
6. Parent-only final verification and closeout

Do not proceed conditions:

- Do not dispatch any worker before `gate/c2-contract-freeze` passes.
- Do not launch `WS-C` before `WS-B` is merged and
  `runtime-payload-freeze.md` exists.
- Do not launch `WS-E` before `WS-C` and `WS-D` are merged.
- Do not close the milestone until `gate/c2-final` passes on the integrated
  tree.

## Orchestration State and Artifact Layout

Repo-local orchestration root:

- `.runs/c2-measurable-coverage-orch/`

Required layout:

- `.runs/c2-measurable-coverage-orch/queue.md`
- `.runs/c2-measurable-coverage-orch/state.json`
- `.runs/c2-measurable-coverage-orch/invariants.md`
- `.runs/c2-measurable-coverage-orch/contract-freeze.md`
- `.runs/c2-measurable-coverage-orch/runtime-payload-freeze.md`
- `.runs/c2-measurable-coverage-orch/session.log`
- `.runs/c2-measurable-coverage-orch/handoffs/`
- `.runs/c2-measurable-coverage-orch/gates/`
- `.runs/c2-measurable-coverage-orch/logs/`
- `.runs/c2-measurable-coverage-orch/sentinels/`
- `.runs/c2-measurable-coverage-orch/acceptance/c2-acceptance-checklist.md`
- `.runs/c2-measurable-coverage-orch/acceptance/final-gate-report.md`
- `.runs/c2-measurable-coverage-orch/qa/c2-final-handoff.md`
- `.runs/c2-measurable-coverage-orch/derived-runs/success/`
- `.runs/c2-measurable-coverage-orch/derived-runs/clarification/`
- `.runs/c2-measurable-coverage-orch/derived-runs/failed/`

Artifact roles:

- `queue.md`: canonical task ledger with one row per `task/c2-*`, owner,
  status, gate, reopen reason, and merge state
- `state.json`: current phase, active lanes, branch names, blockers, gate
  status, final verdict, and derived-run paths
- `invariants.md`: frozen scope, ownership boundaries, forbidden surfaces, and
  merge blockers
- `contract-freeze.md`: frozen field names, schema target, coverage
  vocabulary, canonical headings, CLI/docs truth, and worker ownership
- `runtime-payload-freeze.md`: parent-captured runtime-owned payload shape
  after B merge, used by `WS-C`
- `session.log`: parent-only chronological log of dispatches, gate reruns,
  merge decisions, reopen events, and milestone closeout
- `handoffs/`: one worker handoff per lane, including changed files, commands,
  exit codes, blockers, and residual risk
- `gates/`: exact gate command sets and parent verdicts for A, B, C, D, E, and
  final integrated verification
- `derived-runs/*`: captured `summary.json`, success artifacts when present,
  CLI stdout, exit codes, and parity notes
- `acceptance/*`: final checklist and signoff notes proving each C2 success
  condition
- `qa/c2-final-handoff.md`: concise release-quality summary of what changed,
  what was run, and remaining watchpoints

## Worktree and Branch Plan

Integration worktree:

- Path: `/home/azureuser/__Active_Code/forge`
- Branch: `codex/c1b-planning-quality-proof`
- Owner: Parent only

Sibling worktree root:

- `/home/azureuser/__Active_Code/forge.worktrees/c2-measurable-coverage/`

Worker lanes:

- `WS-B`
  - Path: `/home/azureuser/__Active_Code/forge.worktrees/c2-measurable-coverage/ws-b-runtime`
  - Branch: `codex/c2-measurable-coverage-ws-b-runtime`
  - Purpose: runtime-owned coverage truth
- `WS-C`
  - Path: `/home/azureuser/__Active_Code/forge.worktrees/c2-measurable-coverage/ws-c-publication`
  - Branch: `codex/c2-measurable-coverage-ws-c-publication`
  - Purpose: projection, schema, validation, markdown
- `WS-D`
  - Path: `/home/azureuser/__Active_Code/forge.worktrees/c2-measurable-coverage/ws-d-docs`
  - Branch: `codex/c2-measurable-coverage-ws-d-docs`
  - Purpose: canonical strategy surface, fixture wording, docs truth
- `WS-E`
  - Path: `/home/azureuser/__Active_Code/forge.worktrees/c2-measurable-coverage/ws-e-regression`
  - Branch: `codex/c2-measurable-coverage-ws-e-regression`
  - Purpose: regression-only assertion fill after product merges settle

## Worker Packet Minimums

Every worker packet must contain:

- exact task IDs
- authority reference to `/home/azureuser/__Active_Code/forge/PLAN.md`
- allowed files
- forbidden files
- frozen nouns and explicit non-goals
- lane-local commands to run
- acceptance criteria
- handoff file path under `.runs/c2-measurable-coverage-orch/handoffs/`

Every worker must return:

- changed files list
- commands run with exit codes
- brief change summary mapped to task IDs
- blockers or residual risks
- confirmation that no frozen noun changed
- confirmation that no `*_v2()` helper family or strategy-name branching was
  introduced

Reopen rules:

- touching forbidden files
- changing frozen field names, enums, headings, or schema target
- introducing helper-family sprawl
- introducing strategy-name branching
- omitting required commands or failing them without an explicit blocker note
- broad unrelated cleanup or formatting churn

Any reopen sends the lane back to its own worktree. Parent does not patch
around ownership violations during integration.

## Workstream Plan

### Phase A: Parent-Local Contract and State Freeze

Task ledger:

- `task/c2-a1-confirm-authority-and-cli-surface`
  - Read `PLAN.md`, `README.md`, `examples/README.md`, `anvil/__main__.py`,
    and `anvil/harness/cli.py`.
  - Confirm the current documented harness command is
    `poetry run python -m anvil.cli harness-run`.
  - Confirm `python -m anvil` remains the orchestration CLI entrypoint, not the
    canonical harness command.
- `task/c2-a2-freeze-c2-invariants`
  - Write `invariants.md` and `contract-freeze.md` with C2 scope, frozen
    nouns, schema target, and helper-family ban.
- `task/c2-a3-create-orchestration-root`
  - Create the `.runs/c2-measurable-coverage-orch/` structure, sentinels,
    derived-run roots, and gate files.
- `task/c2-a4-create-worktrees-and-branches`
  - Create `WS-B`, `WS-C`, `WS-D`, and `WS-E` worktrees from the baseline
    branch.
- `task/c2-a5-land-slice-a-local`
  - Land the contract-freeze slice locally, limited to field names, policy
    version surface, and shared state/schema freeze points from `PLAN.md`.
- `task/c2-a6-run-contract-freeze-gate`
  - Run the parent-local gate and record the result in
    `gates/c2-contract-freeze.md`.
- `task/c2-a7-dispatch-ws-b-and-ws-d`
  - Create narrow worker packets and open both lanes.

Parent-owned files in A:

- `anvil/harness/state.py`
- `anvil/harness/planning_runtime.py`
- `anvil/harness/schemas.py`
- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`

Acceptance criteria:

- canonical harness command truth is explicitly frozen in
  `contract-freeze.md`
- `coverage_policy: measurable_coverage_v1` is frozen as the C2 strategy
  policy surface
- state field names and artifact field names are frozen exactly once
- schema target is frozen to `plan_artifact_v2`
- no worker needs to invent nouns later

Lane-local gate for A:

```bash
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_cli_command.py
poetry run pytest -q tests/test_harness_standalone_cli.py
```

### WS-B: Runtime Coverage Derivation

Task ledger:

- `task/c2-b1-seed-runtime-state`
  - Initialize `planning_coverage_status`, `planning_coverage_ledger`,
    `planning_assumptions_register`, and `planning_uncovered_delta` in runtime
    state paths.
- `task/c2-b2-derive-coverage-ledger`
  - Emit exactly one deterministic row per required coverage dimension in
    canonical order with stable IDs.
- `task/c2-b3-derive-assumptions-and-delta`
  - Derive assumptions from unresolved claims and uncovered delta only from
    `partial` or `uncovered` rows.
- `task/c2-b4-preserve-blocked-run-truth`
  - Ensure blocked runs carry truthful partial coverage payloads without
    pretending success.
- `task/c2-b5-run-runtime-gate-and-handoff`
  - Run lane-local tests and write a narrow handoff.

Owned files:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/state.py`
- `tests/test_harness_planning_graph.py`
- `tests/test_harness_state_boundaries.py`

Must not touch:

- `anvil/harness/reporting.py`
- `anvil/harness/validation.py`
- `README.md`
- `examples/README.md`

Acceptance criteria:

- runtime, not reporting, derives coverage truth
- every required dimension has exactly one row
- ordering and IDs are stable across repeat runs on the same workspace snapshot
- blocked runs stamp truthful `planning_coverage_status`
- no cross-record ref uses `stage_type`
- no strategy-name branching is introduced

Lane-local gate for B:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_state_boundaries.py
```

### WS-D: Example Surface and Docs

Task ledger:

- `task/c2-d1-freeze-strategy-surface`
  - Add or confirm `coverage_policy` in the canonical planning strategy
    example.
- `task/c2-d2-update-fixture-task-wording`
  - Keep success, clarification, and failed fixture wording honest about
    emitted artifacts and blocked-run behavior.
- `task/c2-d3-update-readmes`
  - Update `README.md` and `examples/README.md` to describe C2 outputs without
    overselling capability.
- `task/c2-d4-run-docs-gate-and-handoff`
  - Run lane-local checks and write a narrow handoff.

Owned files:

- `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
- `examples/harness/tasks/deterministic_feature_planning_success.yaml`
- `examples/harness/tasks/deterministic_feature_planning_clarification.yaml`
- `examples/harness/tasks/deterministic_feature_planning_failed.yaml`
- `README.md`
- `examples/README.md`

Must not touch:

- `anvil/harness/planning_runtime.py`
- `anvil/harness/reporting.py`
- `anvil/harness/validation.py`

Acceptance criteria:

- docs use the exact canonical harness command frozen in A
- docs distinguish `python -m anvil` orchestration CLI from
  `python -m anvil.cli harness-run`
- success docs mention `PLAN.md` and `plan.json`
- blocked-run docs mention `summary.json` only and truthful coverage payloads
- wording stays inside C2 and does not imply a broader planning engine

Lane-local gate for D:

```bash
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_docs_surface.py
```

### WS-C: Projection, Rendering, and Validation

Task ledger:

- `task/c2-c1-extend-schema-to-v2`
  - Define the `plan_artifact_v2` contract and nested record schemas.
- `task/c2-c2-extend-projection`
  - Keep `plan_projection_v1()` as the single planning payload assembler and
    emit the C2 fields in both `plan.json` and `summary.json`.
- `task/c2-c3-render-canonical-markdown`
  - Keep `render_plan_markdown_v1()` as the single renderer and add the
    canonical C2 section order.
- `task/c2-c4-extend-validation`
  - Keep `publish_planning_artifacts_v1()` as the single publisher and make
    success publication fail closed on broken coverage invariants.
- `task/c2-c5-run-publication-gate-and-handoff`
  - Run lane-local tests and write a narrow handoff.

Owned files:

- `anvil/harness/reporting.py`
- `anvil/harness/schemas.py`
- `anvil/harness/validation.py`
- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_strategy_graph.py`

Must not touch:

- `anvil/harness/planning_runtime.py`
- docs files unless parent reopens minimal wording cleanup explicitly

Acceptance criteria:

- no new planning helper family appears
- success artifacts publish `plan_artifact_v2`
- `summary.json` preserves the same coverage surfaces on blocked runs
- markdown renders sections in canonical order
- validation fails on cardinality drift, broken refs, invalid delta rows, and
  markdown parity drift
- projection serializes runtime truth only and does not infer missing facts

Lane-local gate for C:

```bash
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_harness_strategy_graph.py
```

### WS-E: Regression-Only Lane

Why this lane is safe:

- It launches only after B, C, and D are merged, so product surfaces have
  stopped moving.
- It owns regression expansion only. It must not change runtime, reporting,
  validation, or docs behavior except for the smallest test-driven fix
  explicitly reopened by the parent.
- Its purpose is to encode final acceptance gaps discovered after integration,
  not to redesign implementation.

Task ledger:

- `task/c2-e1-audit-integrated-gaps`
  - Compare integrated tree behavior against `PLAN.md` acceptance and parent
    acceptance checklist.
- `task/c2-e2-add-final-regression-assertions`
  - Add remaining negative cases and round-trip assertions for helper-family
    bans, blocked-run truth, state rehydration, CLI/docs contract, and
    canonical ordering.
- `task/c2-e3-run-regression-lane-gate`
  - Run the regression lane gate and capture failures precisely.
- `task/c2-e4-write-regression-handoff`
  - Write a handoff that maps every new assertion to a C2 acceptance
    condition.

Owned files:

- `tests/test_harness_planning_artifacts.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_state_boundaries.py`
- `tests/test_harness_example_strategy_wiring.py`
- `tests/test_docs_surface.py`

Must not touch without explicit parent reopen:

- any file under `anvil/harness/`
- `README.md`
- `examples/README.md`

Acceptance criteria:

- all final acceptance conditions are represented in tests
- blocked-run summary truth, state rehydration, and docs/CLI contract drift
  are explicitly guarded
- no product-code churn is introduced by the lane
- the lane produces only regression coverage or the smallest reopened fix
  approved by the parent

Lane-local gate for E:

```bash
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_docs_surface.py
```

## Parent Final Integration Phase

Task ledger:

1. `task/c2-f1-merge-ws-b-and-freeze-runtime-payload`
   - Rerun `gate/c2-runtime` on the integration tree, merge `WS-B`, and write
     `runtime-payload-freeze.md`.
2. `task/c2-f2-merge-ws-d`
   - Rerun `gate/c2-docs` on the integration tree and merge `WS-D`.
3. `task/c2-f3-dispatch-merge-ws-c`
   - Dispatch `WS-C` against the frozen runtime payload, rerun
     `gate/c2-publication`, and merge only if green.
4. `task/c2-f4-dispatch-merge-ws-e`
   - Dispatch `WS-E`, rerun `gate/c2-regression-lane`, and merge only if green.
5. `task/c2-f5-run-integrated-derived-runs`
   - Run success, clarification, and failed planning fixtures and capture
     outputs under `derived-runs/`.
6. `task/c2-f6-run-final-quality-gates`
   - Run targeted planning tests, repo-quality checks, and full integrated
     `pytest`.
7. `task/c2-f7-capture-acceptance-and-close`
   - Write final gate report, acceptance checklist, QA handoff, and milestone
     closeout note.

## Parent Integration Discipline

Parent reruns every lane gate before merging. Parent does not rely on
worker-reported green status alone. Parent records each rerun and merge result
in `session.log`.

Parent integrated fixture commands:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .runs/c2-measurable-coverage-orch/derived-runs/success \
  --json

poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_clarification.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .runs/c2-measurable-coverage-orch/derived-runs/clarification \
  --json

poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/deterministic_feature_planning_failed.yaml \
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \
  --out-root .runs/c2-measurable-coverage-orch/derived-runs/failed \
  --json
```

Expected truths:

- success exits `0` and emits `PLAN.md`, `plan.json`, and `summary.json`
- clarification and failed exit `1` and emit `summary.json` only
- blocked runs still carry truthful coverage payloads

## Repo Quality Gates

Lane-local gates are narrow and lane-specific. Final integrated parent gates
are broader and merge-blocking.

Final parent gate sequence:

```bash
poetry run pytest -q tests/test_harness_planning_graph.py
poetry run pytest -q tests/test_harness_planning_artifacts.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_state_boundaries.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run ruff check anvil tests
poetry run black --check anvil tests examples
poetry run isort --check-only anvil tests examples
poetry run mypy anvil
poetry run pytest -q
```

Gate policy:

- targeted planning suites run first for fast signal
- static checks run on the integrated tree only
- full `pytest -q` runs last as the repo-wide non-regression wall
- any failure reopens the narrowest responsible lane unless the parent
  identifies a purely mechanical integration fix

## Merge and Conflict Policy

- `state.py` is parent-frozen in A before B starts to avoid noun drift.
- `schemas.py` version target is frozen in A. C fills contract details later.
- `tests/test_harness_planning_artifacts.py` is first touched by C and only
  reopened to E after C is merged.
- Docs wording is frozen by D before E adds docs-surface assertions.
- Parent rejects any lane that creates `*_v2()` planning helper families,
  computes coverage truth in `reporting.py`, or introduces strategy-name
  branching.

## Failure-Routing Matrix

| Failure | Detection point | Recovery route | Owner |
|---|---|---|---|
| helper-family proliferation | lane review or final gate | reject lane, reopen same lane with explicit helper-family removal | Parent + responsible worker |
| blocked-run summary truth drift | `tests/test_harness_planning_artifacts.py` or derived blocked runs | reopen `WS-B` if truth derivation is wrong, `WS-C` if serialization is wrong | Parent + B or C |
| state rehydration drift | `tests/test_harness_state_boundaries.py` | reopen `WS-B` for state/runtime ownership or `WS-E` for missing assertion only | Parent + B or E |
| CLI/docs contract drift | `tests/test_docs_surface.py`, parent fixture run, or A audit | reopen `WS-D`; if command truth itself changed unexpectedly, parent redoes A freeze before any docs merge | Parent + D |
| coverage cardinality or ordering drift | `tests/test_harness_planning_graph.py` or final fixture artifacts | reopen `WS-B` only | Parent + B |
| assumption or delta ref integrity drift | `tests/test_harness_planning_artifacts.py` | reopen `WS-C` if validation/projection issue, `WS-B` if runtime emits bad refs | Parent + B or C |
| markdown parity drift | `tests/test_harness_planning_artifacts.py` or final success artifact inspection | reopen `WS-C` only | Parent + C |
| final integrated gate failure after all merges | `gate/c2-final` | isolate first failing command, reopen the narrowest lane, rerun merged-tree gates after fix | Parent |
| ownership violation or forbidden-file edits | handoff review | reject merge, reopen same lane from its worktree, no parent patch-around | Parent |

## Assumptions

- `PLAN.md` remains the authoritative C2 specification throughout the session.
- The canonical documented harness command for this repo is currently
  `poetry run python -m anvil.cli harness-run`.
- `python -m anvil` remains the general orchestration CLI entrypoint and should
  not replace the harness command in C2 docs.
- `.runs/` is available for repo-local orchestration state.
- Sibling worktrees under
  `/home/azureuser/__Active_Code/forge.worktrees/c2-measurable-coverage/` are
  acceptable.
- No human approval gate beyond normal parent integration review is required.
