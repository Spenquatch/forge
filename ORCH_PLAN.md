# ORCH_PLAN: C3 Bounded Public Strategy DSL Enforcement

## Summary

Execute the current `PLAN.md` from the live integration branch
`codex/c1b-planning-quality-proof`.

The parent owns the critical path, the only integration worktree, every merge,
and the final acceptance decision. Workers execute bounded lanes in isolated
worktrees under:

- `/home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/`

Worker branches must use this pattern:

- `codex/c3-public-subset-<lane>-<slug>`

Concurrency cap: `2`.

Why the cap is fixed at `2`:

- `Lane A` must freeze the helper contract and exact rule ownership first.
- `Lane B` and `Lane C` may run in parallel only after `Lane A` merges.
- `Lane D` must run last because it proves the final merged behavior and final
  wording.
- Higher concurrency would create false parallelism across shared contract
  language and increase reopen risk.

Orchestration state lives under this source-of-truth control plane:

- `/home/azureuser/__Active_Code/forge/.runs/c3-public-subset-enforcement-orch/`

Parallelism policy:

- allowed in parallel: `Lane B` and `Lane C`
- cannot run in parallel:
  - `Lane A` with anything
  - `Lane D` with anything
  - `Lane C` may execute in parallel with `Lane B`, but it must not merge before
    `Lane B` is integrated

This runbook is `C3`-specific. It replaces stale `C2.9` framing completely.

## Authority and Scope

Repository: `/home/azureuser/__Active_Code/forge`  
Integration branch: `codex/c1b-planning-quality-proof`  
Authority file: `/home/azureuser/__Active_Code/forge/PLAN.md`  
Supersedes: stale `/home/azureuser/__Active_Code/forge/ORCH_PLAN.md`

Mission:

- ship one shared helper:
  `anvil/harness/public_subset_validation.py`
- make `StrategyConfig.from_dict()` the universal public-boundary enforcement
  gate
- make `validator_preflight_node()` own compatibility warning and invalid-config
  adaptation
- preserve internal fixture-backed planning behavior
- prove the contract with parser, preflight, graph, CLI, docs, and wiring tests
- update docs only after live enforcement behavior is in place

## Hard Guards

1. `PLAN.md` is the authority. If this file and `PLAN.md` disagree, follow
   `PLAN.md`.
2. Scope is `C3` implementation, not contract-freeze-only work.
3. `StrategyConfig.from_dict()` is the universal enforcement gate.
4. `anvil/harness/public_subset_validation.py` is the only shared helper seam
   for raw-payload classification and canonical-public validation.
5. `validator_preflight_node()` owns warning/error adaptation only. It must not
   own a second copy of the rules.
6. Do not introduce a second parser.
7. Do not introduce a public-only runtime target.
8. Do not introduce a second graph-spec builder, second compiler, or second
   runner path.
9. Do not duplicate canonical kinds, stage families, exclusions, or canonical
   planning phase order across modules.
10. Do not infer public mode from file path, example directory, or naming
    conventions.
11. Do not relabel internal/private fixture-backed strategies as canonical public
    authoring.
12. Do not add task-spec enforcement in this milestone.
13. Do not change planning artifact schema, reporting schema, or durable state
    just to label the public surface.
14. Audit-only surfaces may be patched only if the audit proves a real loophole.
15. No unrelated cleanup, formatting sweep, or opportunistic refactor outside
    scoped files.
16. The parent is the only integrator.

## Parent Execution Script

The parent executes this sequence serially.

### Parent task list

- `task/c3-p01-read-authority`
  Read `PLAN.md`, confirm this runbook is aligned, and treat `PLAN.md` as the
  final authority.
- `task/c3-p02-confirm-branch`
  Confirm current branch is `codex/c1b-planning-quality-proof`.
- `task/c3-p03-check-repo-assumptions`
  Check for dirty-worktree or unrelated-change conditions that would affect lane
  ownership; do not revert user changes.
- `task/c3-p04-create-state-root`
  Create the `.runs/c3-public-subset-enforcement-orch/` control plane.
- `task/c3-p05-create-worktrees`
  Create all worker worktrees and branches from the integration branch.
- `task/c3-p06-dispatch-a`
  Dispatch `Lane A` with only its minimal context packet.
- `task/c3-p07-merge-a`
  Review `Lane A`, rerun its gate, merge it, and publish the contract-freeze
  artifact.
- `task/c3-p08-dispatch-bc`
  Dispatch `Lane B` and `Lane C` in parallel using the frozen contract summary.
- `task/c3-p09-merge-b`
  Review `Lane B`, rerun its gate, merge it first, and record audit results.
- `task/c3-p10-merge-c`
  Review `Lane C`, rerun its gate after `Lane B` is merged, and then merge it.
- `task/c3-p11-dispatch-d`
  Dispatch `Lane D` against the merged `A+B+C` branch only.
- `task/c3-p12-merge-d`
  Review `Lane D`, rerun the full regression wall, and merge it.
- `task/c3-p13-final-gate`
  Run the final focused acceptance suite on the integration branch.
- `task/c3-p14-closeout`
  Close all worker records, write the final session note, and mark the run done
  only if every acceptance criterion is satisfied.

### Parent serialized checklist

1. Read `/home/azureuser/__Active_Code/forge/PLAN.md`.
2. Confirm the current branch is `codex/c1b-planning-quality-proof`.
3. Inspect repo state for unrelated edits that could affect lane boundaries.
4. Create `.runs/c3-public-subset-enforcement-orch/`.
5. Initialize `queue.json`, `session-log.md`, `merge-log.md`, and sentinel
   files.
6. Create all worker worktrees and branches.
7. Dispatch `Lane A`.
8. Review `Lane A` handoff.
9. Rerun `Lane A` gate on the integration branch.
10. Merge `Lane A`.
11. Publish `contract-freeze.md`.
12. Dispatch `Lane B` and `Lane C` in parallel.
13. Review `Lane B` handoff and audit report.
14. Rerun `Lane B` gate on the integration branch.
15. Merge `Lane B`.
16. Review `Lane C` handoff.
17. Rerun `Lane C` gate after `Lane B` is merged.
18. Merge `Lane C`.
19. Dispatch `Lane D`.
20. Review `Lane D` handoff.
21. Rerun `Lane D` gate on the integration branch.
22. Merge `Lane D`.
23. Run the final acceptance gate.
24. Write final results to `session-log.md` and `merge-log.md`.
25. Mark the run done only if the final gate and all acceptance criteria pass.

## Worktree and Branch Plan

### Integration worktree

- Path: `/home/azureuser/__Active_Code/forge`
- Branch: `codex/c1b-planning-quality-proof`
- Owner: parent only

### Worker worktree root

- `/home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/`

### Worker branches and worktrees

| Lane | Branch | Worktree |
|---|---|---|
| `Lane A` | `codex/c3-public-subset-a-helper-contract` | `/home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-a-helper-contract` |
| `Lane B` | `codex/c3-public-subset-b-parser-preflight` | `/home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-b-parser-preflight` |
| `Lane C` | `codex/c3-public-subset-c-docs-taxonomy` | `/home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-c-docs-taxonomy` |
| `Lane D` | `codex/c3-public-subset-d-regression-wall` | `/home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-d-regression-wall` |

### Worktree creation commands

```bash
mkdir -p /home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-a-helper-contract \
  -b codex/c3-public-subset-a-helper-contract \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-b-parser-preflight \
  -b codex/c3-public-subset-b-parser-preflight \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-c-docs-taxonomy \
  -b codex/c3-public-subset-c-docs-taxonomy \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c3-public-subset-enforcement/ws-d-regression-wall \
  -b codex/c3-public-subset-d-regression-wall \
  codex/c1b-planning-quality-proof
```

### Parent merge commands

```bash
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c3-public-subset-a-helper-contract
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c3-public-subset-b-parser-preflight
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c3-public-subset-c-docs-taxonomy
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c3-public-subset-d-regression-wall
```

## Control Plane State Root

State root:

- `/home/azureuser/__Active_Code/forge/.runs/c3-public-subset-enforcement-orch/`

### Source-of-truth artifacts

- `queue.json`
  Machine-readable lane/task status and gate state.
- `session-log.md`
  Parent narrative log of dispatches, merges, stops, and final closeout.
- `merge-log.md`
  Chronological merge record with branch names, gate results, and commit ids.
- `contract-freeze.md`
  Parent-published frozen helper contract and rule summary after `Lane A`.
- `handoffs/ws-a.md`
- `handoffs/ws-b.md`
- `handoffs/ws-c.md`
- `handoffs/ws-d.md`

### Supporting artifacts

- `gates/ws-a.txt`
- `gates/ws-b.txt`
- `gates/ws-c.txt`
- `gates/ws-d.txt`
- `gates/final.txt`
- `audits/ws-b.json`
  Required audit return for `Lane B`
- `sentinels/`
- `packets/`
- `logs/`

### Required queue shape

`queue.json` must track at least:

- task id
- owner
- lane
- status: `pending | in_progress | blocked | ready | merged | closed`
- worktree path
- branch
- depends_on
- gate name
- last_update
- reopen_reason

### Sentinel conventions

Minimum sentinel files:

- `sentinels/ws-a.dispatched`
- `sentinels/ws-a.ready`
- `sentinels/ws-a.merged`
- `sentinels/ws-b.dispatched`
- `sentinels/ws-b.ready`
- `sentinels/ws-b.merged`
- `sentinels/ws-c.dispatched`
- `sentinels/ws-c.ready`
- `sentinels/ws-c.merged`
- `sentinels/ws-d.dispatched`
- `sentinels/ws-d.ready`
- `sentinels/ws-d.merged`
- `sentinels/gate-c3-a.pass`
- `sentinels/gate-c3-b.pass`
- `sentinels/gate-c3-c.pass`
- `sentinels/gate-c3-d.pass`
- `sentinels/gate-c3-final.pass`

Optional per-task sentinels are allowed under `sentinels/tasks/`.

## Context Control

### Parent live context

The parent should keep only:

- `/home/azureuser/__Active_Code/forge/PLAN.md`
- this runbook
- current dispatch packet
- current worker handoff
- current narrow diff
- current gate output
- current control-plane files

After a lane is merged, the parent closes it in the control plane and drops its
full working context.

### Worker packet minimums

Every packet under `packets/` must include:

- worker ID
- lane ID
- task IDs
- authority branch
- worktree path and branch
- owned paths
- forbidden paths
- relevant `PLAN.md` sections only
- lane definition of done
- lane gate commands
- bounce triggers
- handoff destination
- explicit reminder that the parent is the only integrator

### Worker return minimums

Every handoff file must include:

- tasks completed
- changed files
- commands run
- exit code per command
- residual risks
- blockers, if any
- whether forbidden-path edits were needed
- whether frozen vocabulary pressure was encountered
- narrow diff summary

## Lane Runbooks

## Lane A: shared helper and rule freeze

Purpose: add the shared helper and freeze the exact raw-payload classification
and canonical validation rules in one place before downstream integration or
documentation work proceeds.

Depends on: none

### Lane A tasks

- `task/c3-a1-helper-seam`
  Add `anvil/harness/public_subset_validation.py` with exactly two public seams:
  `classify_public_strategy_surface(raw_payload)` and
  `validate_public_strategy_payload(raw_payload)`.
- `task/c3-a2-classification-rules`
  Encode canonical, compatibility-only, and internal/private classification from
  the existing frozen registry vocabulary.
- `task/c3-a3-canonical-validation-rules`
  Encode canonical allowlist, exclusions, stage-family rules, and canonical
  planning-phase-order checks.
- `task/c3-a4-registry-cleanup-if-needed`
  Apply only additive cleanup in
  `anvil/harness/public_subset_registry.py` if required for helper reuse.

### Owned edit paths

- `/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_validation.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py`
  only for additive cleanup required by the helper

### Forbidden edits

- `/home/azureuser/__Active_Code/forge/anvil/harness/types.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py`
- `/home/azureuser/__Active_Code/forge/tests/`
- `/home/azureuser/__Active_Code/forge/docs/`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`

### Definition of done

- helper API matches `PLAN.md`
- helper owns classification and canonical validation only
- compatibility-only input is classified explicitly
- internal/private payloads are classified before canonical-only exclusions
- no warnings, mutation, graph building, or task-spec logic are added
- no second rule list is introduced elsewhere

### Lane A gate commands

The parent reruns these before merge:

```bash
poetry run python -c "from anvil.harness.public_subset_validation import classify_public_strategy_surface, validate_public_strategy_payload; print(classify_public_strategy_surface); print(validate_public_strategy_payload)"
poetry run pytest -q tests/test_harness_public_subset_contract.py
```

If `tests/test_harness_public_subset_contract.py` does not yet exercise the new
helper directly, that is acceptable at this lane. The import sanity command is
still mandatory because `Lane A` introduces the new module.

### Lane A bounce triggers

- helper grows beyond the two allowed public seams
- worker introduces file-path heuristics
- worker tries to move rule ownership into parser or preflight
- worker needs new public vocabulary not already frozen by `PLAN.md`

## Lane B: parser + preflight integration and loophole audit

Purpose: make parser-owned enforcement real, adapt preflight messaging, and
prove no direct parse entrypoint can bypass the boundary.

Depends on: merged `Lane A`

### Lane B tasks

- `task/c3-b1-load-frozen-helper`
  Consume the merged helper and frozen rule summary without duplicating rules.
- `task/c3-b2-parser-hook`
  Wire `StrategyConfig.from_dict()` to call the shared helper before typed
  coercion.
- `task/c3-b3-preflight-adaptation`
  Update `validator_preflight_node()` to reuse the helper for compatibility
  warning and invalid-config adaptation.
- `task/c3-b4-audit-direct-entrypoints`
  Audit `prepare_run.py`, `runner.py`, `analysis_review_v1.py`,
  `strategy_graph.py`, and `planning_runtime.py`; patch only if a real loophole
  exists.

### Owned edit paths

- `/home/azureuser/__Active_Code/forge/anvil/harness/types.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/nodes/validator_preflight.py`

### Audit-only surfaces

- `/home/azureuser/__Active_Code/forge/anvil/harness/nodes/prepare_run.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/runner.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/subgraphs/analysis_review_v1.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/strategy_graph.py`
- `/home/azureuser/__Active_Code/forge/anvil/harness/planning_runtime.py`

### Audit return policy

If no patch is needed, `audits/ws-b.json` must still include one record per
audited file with:

- `file`
- `loophole_result`: `none` or `found`
- `reason_no_edit_necessary`
- `notes`

If a loophole is found and patched, include:

- `file`
- `loophole_result`: `found`
- `patch_required`: `true`
- `why_parser_owned_gate_was_insufficient_without_patch`

### Forbidden edits

- `/home/azureuser/__Active_Code/forge/tests/`
- `/home/azureuser/__Active_Code/forge/docs/`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`

### Definition of done

- `StrategyConfig.from_dict()` is the universal enforcement gate
- `validator_preflight_node()` adapts helper results without owning a second
  rule list
- compatibility-only input remains accepted with explicit warning path
- invalid canonical-public input can stop before model work
- internal/private fixture-backed inputs remain accepted
- every audited file has a recorded loophole result

### Lane B gate commands

The parent reruns these before merge:

```bash
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
```

Why these are the minimum `Lane B` gate:

- `Lane B` changes parser/preflight behavior that must surface through wiring,
  graph routing, and CLI invalid-config behavior.
- `Lane D` will strengthen the regression wall later, but `Lane B` still must
  pass the existing route-level and CLI-level checks before merge.

### Lane B bounce triggers

- worker introduces a second parser or alternate validation path
- worker duplicates canonical rule sets
- worker introduces public-only runtime routing
- worker needs docs or tests changed to explain incomplete code behavior
- audit proves a loophole that exceeds the allowed audited surfaces

## Lane C: docs, readmes, and example taxonomy wording

Purpose: align contributor-facing docs and example-surface taxonomy to the live
C3 behavior without taking ownership of enforcement truth or test truth.

Depends on: merged `Lane A` for vocabulary; merge blocked until `Lane B` is
merged

### Lane C ownership policy

`Lane C` is intentionally narrowed.

It owns:

- docs
- readmes
- example taxonomy wording
- example-pack explanatory text

It does not own:

- canonical/compatibility/negative strategy-body content truth
- parser behavior
- test assertions

Content-shape truth is locked by `Lane A` and `Lane B`, then proven by
`Lane D`. If `Lane C` discovers that example strategy bodies themselves must
change to match live enforcement, stop and bounce to the parent instead of
editing around the mismatch in docs.

### Lane C tasks

- `task/c3-c1-contract-doc-refresh`
  Update `docs/strategy_dsl_public_subset_contract.md` so it describes live
  enforcement accurately.
- `task/c3-c2-front-door-readmes`
  Update `README.md` and `examples/README.md` to route users to the live bounded
  public contract correctly.
- `task/c3-c3-contributor-and-roadmap-alignment`
  Update `docs/contributing.md` and `docs/roadmap.md` so they reflect current
  C3 behavior.
- `task/c3-c4-example-taxonomy-wording`
  Update only explanatory text under `examples/harness/public_subset/`, such as
  README/taxonomy wording, without taking ownership of strategy-body truth.

### Owned edit paths

- `/home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`
- `/home/azureuser/__Active_Code/forge/docs/contributing.md`
- `/home/azureuser/__Active_Code/forge/docs/roadmap.md`
- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/README.md`
- any explanatory markdown under
  `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/`

### Forbidden edits

- `/home/azureuser/__Active_Code/forge/anvil/harness/`
- `/home/azureuser/__Active_Code/forge/tests/`
- canonical/compatibility/negative strategy-body files under
  `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/`

### Definition of done

- docs describe parser-owned enforcement as live
- docs describe preflight warning/error adaptation as live
- canonical public, compatibility-only, and internal/private surfaces are
  clearly separated
- no doc or taxonomy wording suggests `analysis_review_v1` is canonical public
  `C3 v1`
- no doc suggests `coverage_policy`, `phase_inputs`, `schema_version`, or
  `subset` belong in canonical public authoring
- example taxonomy wording is accurate without altering enforcement truth

### Lane C gate commands

The parent reruns these before merge, after `Lane B` is merged:

```bash
poetry run pytest -q tests/test_docs_surface.py
```

No broader unique command is required for `Lane C` because this lane is
wording-only by policy. Content-shape truth is owned by `Lane A+B` and proven by
`Lane D`, not by `Lane C`.

### Lane C bounce triggers

- docs claim behavior the merged code does not implement
- worker wants to edit example strategy bodies to make docs easier to align
- worker wants to relabel internal/private fixture-backed strategies as
  canonical public authoring
- worker expands scope beyond wording/taxonomy alignment

## Lane D: regression wall

Purpose: prove the merged `A+B+C` contract across parser, preflight, direct
entrypoints, graph routing, CLI behavior, docs, and example wiring.

Depends on: merged `Lane B` and merged `Lane C`

### Lane D tasks

- `task/c3-d1-parser-and-contract-wall`
  Extend contract and enforcement coverage for canonical accept,
  compatibility-only accept-with-warning, and negative reject behavior.
- `task/c3-d2-entrypoint-and-routing-wall`
  Extend example wiring and strategy graph coverage so direct parse entrypoints
  and routing behavior prove the same contract.
- `task/c3-d3-cli-invalid-config-wall`
  Extend CLI coverage so invalid public input exits non-zero and no model work
  starts.
- `task/c3-d4-docs-drift-wall`
  Extend docs-surface coverage so front-door docs and example taxonomy stay in
  sync with live enforcement.

### Owned edit paths

- `/home/azureuser/__Active_Code/forge/tests/test_harness_public_subset_contract.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_strategy_graph.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_cli_command.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_standalone_cli.py`
- `/home/azureuser/__Active_Code/forge/tests/test_docs_surface.py`
- one focused enforcement file, if added:
  `/home/azureuser/__Active_Code/forge/tests/test_harness_public_subset_enforcement.py`

### Forbidden edits

- `/home/azureuser/__Active_Code/forge/anvil/`
- `/home/azureuser/__Active_Code/forge/docs/`
- `/home/azureuser/__Active_Code/forge/examples/`
- `/home/azureuser/__Active_Code/forge/README.md`

### Definition of done

- every new public-contract rule has:
  - one example or inline payload
  - one parser/preflight assertion
  - one message assertion
- direct parse entrypoints are covered
- internal/private fixture-backed planning preservation is covered
- CLI invalid-config and no-model-work behavior is covered
- docs-surface drift is covered
- tests assert final taxonomy and final wording only

### Lane D gate commands

The parent reruns this full focused wall before merge:

```bash
poetry run pytest -q tests/test_harness_public_subset_contract.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_cli_command.py tests/test_harness_standalone_cli.py
poetry run pytest -q tests/test_docs_surface.py
```

If a dedicated enforcement file exists, also rerun:

```bash
poetry run pytest -q tests/test_harness_public_subset_enforcement.py
```

### Lane D bounce triggers

- a failing test reveals a real code or docs mismatch
- worker needs to patch product code or docs to make tests pass
- assertions are weakened instead of forcing the source of truth back into
  alignment

## Merge Order and Lane Dependencies

### Fixed order

1. `Lane A`
2. `Lane B` and `Lane C` may execute in parallel
3. merge `Lane B`
4. merge `Lane C`
5. `Lane D`
6. final parent gate

### Do-not-proceed rules

- do not dispatch `Lane B` or `Lane C` until `Lane A` is merged and
  `contract-freeze.md` exists
- do not merge `Lane C` until `Lane B` is merged
- do not dispatch `Lane D` until `Lane B` and `Lane C` are merged
- do not merge any lane that crosses its owned-path boundary without explicit
  parent reassignment

## Final Acceptance and Failure Policy

### DONE

The run is `DONE` only when all are true on
`codex/c1b-planning-quality-proof`:

- canonical public `c3_strategy_v1` examples are accepted by
  `StrategyConfig.from_dict()`
- canonical public examples pass preflight cleanly
- compatibility-only `analysis_review_v1` remains accepted with explicit legacy
  warning
- each negative public fixture fails before model work with one targeted
  invalid-config reason
- direct parse entrypoints have been audited and no bypass remains
- internal fixture-backed planning behavior still works
- accepted canonical specs route through the existing runtime graph families
  with no second compiler or public-only runtime target
- CLI exits non-zero for invalid public authoring
- docs and example taxonomy describe live enforcement accurately
- task-spec freezing remains explicitly out of scope
- `Lane D` gate passes
- final focused gate passes
- `session-log.md` and `merge-log.md` record a clean closeout

### BLOCKED

The run is `BLOCKED` if any of the following occurs:

- `PLAN.md` changes during execution
- the current branch is no longer `codex/c1b-planning-quality-proof`
- a lane requires architecture outside the locked `C3` decisions
- a real loophole requires scope beyond the audited surfaces
- unrelated conflicting edits appear in lane-owned files and prevent safe
  bounded merge
- the final focused gate does not pass

### BOUNCE BACK

Bounce a lane back instead of integrating around it when:

- the diff crosses owned-path boundaries
- docs claim behavior that code does not yet implement
- tests are weakened instead of enforcing truth
- a worker silently expands scope
- a lane edits another lane’s source of truth
- a worker needs to touch forbidden paths for completion

### STOP INSTEAD OF INTEGRATING AROUND A MISMATCH

Stop the run and reopen planning if:

- the helper contract in `Lane A` is insufficient for the plan’s required
  behavior
- `Lane B` cannot make parser-owned enforcement universal without introducing a
  second enforcement path
- `Lane C` reveals example-surface truth that contradicts merged enforcement
- `Lane D` exposes a mismatch that cannot be resolved by fixing the owning lane
  within current scope

## Final Gate

After `Lane D` merges, the parent reruns the final focused suite on the
integration branch:

```bash
poetry run pytest -q \
  tests/test_harness_public_subset_contract.py \
  tests/test_harness_example_strategy_wiring.py \
  tests/test_harness_strategy_graph.py \
  tests/test_harness_cli_command.py \
  tests/test_harness_standalone_cli.py \
  tests/test_docs_surface.py
```

If the dedicated enforcement file exists, include it in the final run.

Do not close the run on partial success. If any acceptance item still requires a
follow-up to become true, the milestone is not complete.
