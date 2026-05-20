# ORCH_PLAN: C2.9 Public Subset Gate for C3

## 1. Summary

Repository: `/home/azureuser/__Active_Code/forge`  
Integration branch: `codex/c1b-planning-quality-proof`  
Authority file: `/home/azureuser/__Active_Code/forge/PLAN.md`  
Milestone: `C2.9 Public Subset Gate for C3`  
Stale file being replaced: `/home/azureuser/__Active_Code/forge/ORCH_PLAN.md`

This file is the parent-owned orchestration runbook for executing `PLAN.md` on
the current branch. `C2.9` is a contract-freeze milestone only. It must not add
parser enforcement, preflight enforcement, runtime wiring, or any runtime
behavior change.

The parent is the only integrator. Workers execute bounded lanes and return
handoffs. Workstream A freezes the contract vocabulary first. Workstreams B and
C may run in parallel only after A is merged. Workstream D runs last as the
drift wall.

## 2. Orchestration Runtime Policy

Parent runtime policy:

- Role: parent orchestrator and sole integrator
- Model: `GPT-5.4`
- Reasoning: `high`

Worker runtime policy:

- Role: bounded implementation worker for a single lane
- Model: `GPT-5.4`
- Reasoning: `high`

Concurrency policy:

- Maximum concurrency window: `2`
- Why it cannot be higher:
  - Workstream A must freeze the vocabulary before any downstream content work
    starts.
  - Workstreams B and C both depend on A’s exact vocabulary and terminology.
  - Workstream D depends on the merged outputs of both B and C and must run
    last.
  - Higher concurrency would create false parallelism across shared contract
    language and increase reopen risk without improving throughput on this
    branch.

## 3. Hard Guards

1. `/home/azureuser/__Active_Code/forge/PLAN.md` is authoritative. If this
   file and `PLAN.md` disagree, follow `PLAN.md`.
2. Do not edit `PLAN.md`.
3. `C2.9` ends at contract-freeze artifacts plus drift tests.
4. Runtime behavior must not change.
5. Do not wire `anvil/harness/public_subset_registry.py` into runtime behavior
   in this branch.
6. Do not implement parser enforcement, preflight enforcement, or task-spec
   contract work in this branch.
7. Do not relabel compatibility-only or runtime-owned surfaces as canonical
   public DSL.
8. Do not move or delete
   `examples/harness/strategies/deterministic_feature_planning_v1.yaml`; keep
   it runnable and relabel it honestly.
9. Do not invent new public kinds, stage families, role families, transition
   forms, planning phase types, excluded fields, or metadata-only fields beyond
   `PLAN.md`.
10. The parent is the only integrator.
11. Any worker that needs to change another workstream’s frozen vocabulary or
    owned files must stop and reopen to the parent.
12. B and C must not start before A is merged.
13. D must not start before both B and C are merged.
14. No unrelated repo cleanup, refactors, formatting sweeps, or doc rewrites
    outside the scoped files.

## 4. Parent-Owned Critical Path and Merge Order

### 4.1 Critical path

| Phase | Task IDs | Owner | Mode | Gate |
|---|---|---|---|---|
| Parent kickoff | `task/c29-p01` to `task/c29-p04` | Parent | serialized | `gate/c29-kickoff` |
| Workstream A: registry + contract doc | `task/c29-a1` to `task/c29-a4` | `WS-A` | serialized | `gate/c29-a-contract-freeze` |
| Parent freeze publish | `task/c29-p05` to `task/c29-p06` | Parent | serialized | `gate/c29-a-merged` |
| Workstreams B and C | `task/c29-b1` to `task/c29-b5`, `task/c29-c1` to `task/c29-c5` | `WS-B`, `WS-C` | parallel, max 2 | `gate/c29-b-example-pack`, `gate/c29-c-front-door` |
| Parent integration of B and C | `task/c29-p07` to `task/c29-p09` | Parent | serialized | `gate/c29-bc-merged` |
| Workstream D: drift wall tests | `task/c29-d1` to `task/c29-d4` | `WS-D` | serialized | `gate/c29-d-drift-wall` |
| Final closeout | `task/c29-p10` to `task/c29-p12` | Parent | serialized | `gate/c29-final` |

### 4.2 Fixed merge order

1. Parent kickoff and state-root setup
2. Merge `WS-A`
3. Parent publishes the A freeze note
4. Run `WS-B` and `WS-C` in parallel
5. Merge `WS-B`
6. Merge `WS-C`
7. Run and merge `WS-D`
8. Parent reruns final validation on `codex/c1b-planning-quality-proof`

### 4.3 Do-not-proceed gates

- Do not dispatch `WS-B` or `WS-C` until `gate/c29-a-contract-freeze` passes.
- Do not dispatch `WS-D` until both `gate/c29-b-example-pack` and
  `gate/c29-c-front-door` pass and both branches are merged.
- Do not merge a worker if its diff crosses into another lane’s owned files
  without explicit parent reassignment.
- Do not proceed if any lane requires runtime wiring, parser enforcement, or
  scope beyond the artifacts listed in `PLAN.md` section 2.2.

## 5. Workstream Plan

### 5.1 Parent-owned orchestration tasks

- `task/c29-p01-read-authority`
  Read `PLAN.md` and the current `ORCH_PLAN.md`, then seed the repo-local
  orchestration state.
- `task/c29-p02-create-state-root`
  Create the `.runs/c29-public-subset-gate-orch/` layout and sentinel
  conventions.
- `task/c29-p03-create-worktrees`
  Create all worker worktrees from `codex/c1b-planning-quality-proof`.
- `task/c29-p04-dispatch-ws-a`
  Dispatch the contract-freeze lane first.
- `task/c29-p05-review-merge-ws-a`
  Review `WS-A`, rerun the A gate checks, and merge only if vocabulary exactly
  matches `PLAN.md`.
- `task/c29-p06-publish-a-freeze`
  Write `contract-freeze.md` under the state root with the exact approved
  vocabulary and exclusions.
- `task/c29-p07-dispatch-ws-b-ws-c`
  Dispatch the example-pack and front-door-doc lanes in parallel.
- `task/c29-p08-merge-ws-b`
  Review and merge the example pack.
- `task/c29-p09-merge-ws-c`
  Review and merge the front-door docs and runnable fixture relabeling.
- `task/c29-p10-dispatch-ws-d`
  Dispatch the drift-wall tests only after B and C are integrated.
- `task/c29-p11-merge-ws-d`
  Review and merge the test lane.
- `task/c29-p12-final-validation-closeout`
  Rerun final validation commands on the integration branch and close the
  milestone only if all pass.

### 5.2 Workstream A: registry + contract doc

Owner: `WS-A`  
Purpose: freeze the contract vocabulary and terminology that every later lane
depends on.

Owned paths:

- `/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py`
- `/home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md`

Forbidden paths:

- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`
- `/home/azureuser/__Active_Code/forge/docs/contributing.md`
- `/home/azureuser/__Active_Code/forge/tests/`

Tasks:

- `task/c29-a1-add-registry`
  Add the data-only registry with the exact constant groups from `PLAN.md`
  section 5.2.
- `task/c29-a2-write-contract-doc`
  Add the human-readable contract doc mirroring the registry 1:1.
- `task/c29-a3-freeze-layering-language`
  Make the doc explicit about canonical public surface, compatibility-only
  input, runtime-owned exclusions, and metadata-only fields.
- `task/c29-a4-freeze-boundary`
  State plainly that `C2.9` is contract freeze only and that task-spec surface
  and runtime enforcement are out of scope.

Definition of done:

- Registry contents match `PLAN.md` exactly.
- Contract doc mirrors the registry exactly.
- No runtime code is touched.
- No terminology in A leaves ambiguity for B, C, or D.

### 5.3 Workstream B: classified public example pack

Owner: `WS-B`  
Purpose: create the clean public example pack that follows the frozen A
vocabulary exactly.

Owned paths:

- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/README.md`
- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/canonical/`
- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/compatibility/`
- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/negative/`

Forbidden paths:

- `/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py`
- `/home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md`
- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`
- `/home/azureuser/__Active_Code/forge/docs/contributing.md`
- `/home/azureuser/__Active_Code/forge/tests/`
- `/home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml`

Tasks:

- `task/c29-b1-add-example-pack-readme`
- `task/c29-b2-add-three-canonical-examples`
- `task/c29-b3-add-one-compatibility-example`
- `task/c29-b4-add-five-negative-examples`
- `task/c29-b5-verify-example-pack-uses-a-freeze`

Definition of done:

- All required files from `PLAN.md` section 5.4 exist at the exact paths.
- Canonical examples use canonical kinds only and carry
  `dsl_version: c3_strategy_v1`.
- Canonical examples omit `coverage_policy`, `phase_inputs`, `schema_version`,
  and `subset`.
- Canonical non-planning examples omit `runtime_target`.
- The canonical planning example includes `runtime_target: planning_v1` and the
  required planning policy refs.
- The compatibility example is obviously non-canonical.
- Each negative example maps to one contract violation only.

### 5.4 Workstream C: front-door docs alignment + runnable fixture relabeling

Owner: `WS-C`  
Purpose: route readers to the new public contract first while preserving
existing runnable fixture coverage.

Owned paths:

- `/home/azureuser/__Active_Code/forge/README.md`
- `/home/azureuser/__Active_Code/forge/examples/README.md`
- `/home/azureuser/__Active_Code/forge/docs/contributing.md`
- `/home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml`

Forbidden paths:

- `/home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py`
- `/home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md`
- `/home/azureuser/__Active_Code/forge/examples/harness/public_subset/`
- `/home/azureuser/__Active_Code/forge/tests/`

Tasks:

- `task/c29-c1-update-root-readme`
- `task/c29-c2-update-examples-readme`
- `task/c29-c3-update-contributing-doc`
- `task/c29-c4-relabel-runnable-planning-fixture`
- `task/c29-c5-verify-front-door-terminology`

Definition of done:

- Front-door docs point readers first to
  `docs/strategy_dsl_public_subset_contract.md` and
  `examples/harness/public_subset/README.md`.
- Existing runnable commands remain documented where they already belong.
- The deterministic planning fixture is clearly labeled internal or
  fixture-backed and explicitly not the canonical public `C3 v1` example.

### 5.5 Workstream D: contract drift wall tests

Owner: `WS-D`  
Purpose: make docs, registry, and example pack drift visible immediately.

Owned paths:

- `/home/azureuser/__Active_Code/forge/tests/test_harness_public_subset_contract.py`
- `/home/azureuser/__Active_Code/forge/tests/test_docs_surface.py`
- `/home/azureuser/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`

Forbidden paths:

- `/home/azureuser/__Active_Code/forge/anvil/`
- `/home/azureuser/__Active_Code/forge/docs/`
- `/home/azureuser/__Active_Code/forge/examples/`
- `/home/azureuser/__Active_Code/forge/README.md`

Tasks:

- `task/c29-d1-add-new-contract-test`
- `task/c29-d2-extend-docs-surface-test`
- `task/c29-d3-extend-example-wiring-test`
- `task/c29-d4-run-focused-pytest-wall`

Definition of done:

- `tests/test_harness_public_subset_contract.py` asserts the exact contract sets
  and example-pack rules from `PLAN.md`.
- `tests/test_docs_surface.py` enforces front-door routing and terminology.
- `tests/test_harness_example_strategy_wiring.py` enforces coexistence of the
  new public example pack and the existing runnable fixture tree.
- No product or runtime logic is changed in this lane.

## 6. Context Control

### 6.1 Parent live working context

The parent keeps only the following in live context during the run:

- `/home/azureuser/__Active_Code/forge/PLAN.md`
- `/home/azureuser/__Active_Code/forge/ORCH_PLAN.md`
- `/home/azureuser/__Active_Code/forge/.runs/c29-public-subset-gate-orch/queue.md`
- `/home/azureuser/__Active_Code/forge/.runs/c29-public-subset-gate-orch/state.json`
- `/home/azureuser/__Active_Code/forge/.runs/c29-public-subset-gate-orch/contract-freeze.md`
- the current worker packet being dispatched or reviewed
- the narrow diff and handoff for the worker being merged

The parent should not keep full-file copies of every lane in active context
after merge. After integration, the parent reviews the worker summary, inspects
the narrow diff, reruns the gate, merges, records the result, and closes that
worker.

### 6.2 Worker packet minimums

Every worker packet must contain:

- worker ID and workstream ID
- exact task IDs
- authority path: `/home/azureuser/__Active_Code/forge/PLAN.md`
- integration branch: `codex/c1b-planning-quality-proof`
- worktree path and worker branch
- owned paths
- forbidden paths
- relevant `PLAN.md` sections only
- current `contract-freeze.md` contents if A is already merged
- lane-specific definition of done
- lane-specific validation commands
- reopen triggers
- required handoff destination under
  `/home/azureuser/__Active_Code/forge/.runs/c29-public-subset-gate-orch/handoffs/`

### 6.3 Worker return minimums

Every worker return must contain:

- task IDs completed
- short summary of what changed
- exact changed files
- commands run
- exit codes for each command
- any blockers or residual risks
- explicit note whether frozen vocabulary pressure was encountered
- explicit note whether any forbidden path would be required for full completion
- a narrow diff summary suitable for parent merge review

### 6.4 Parent closeout of each worker

For each worker, the parent must:

1. Read the return summary
2. Inspect the narrow diff
3. Rerun the gate on the integration branch
4. Merge only if the gate passes and the lane stayed in scope
5. Update `queue.md`, `state.json`, and `merge-log.md`
6. Mark the worker closed after merge

## 7. Repo-Local Orchestration State Root

State root:

- `/home/azureuser/__Active_Code/forge/.runs/c29-public-subset-gate-orch/`

### 7.1 Source-of-truth files

- `queue.md`
- `state.json`
- `contract-freeze.md`
- `merge-log.md`
- `handoffs/`
- `gates/`
- `logs/`
- `sentinels/`

### 7.2 Operational use during the run

- `queue.md`
  The parent’s task board. Tracks every `task/c29-*` item, owner, status,
  active lane, reopen reason, and merge state.
- `state.json`
  The parent’s machine-readable run state. Tracks active worktrees, current
  phase, gate results, and worker closure state.
- `contract-freeze.md`
  The frozen A vocabulary and exclusions approved by the parent. This is the
  downstream contract source for B, C, and D during the run.
- `merge-log.md`
  The parent’s chronological integration record. Stores merge order, rerun
  results, gate outcomes, and closeout notes.

### 7.3 Supporting directories

- `handoffs/`
  One dispatch packet and one return handoff per worker lane.
- `gates/`
  Parent rerun commands, command outputs, and gate verdict notes.
- `logs/`
  Validation logs from focused pytest runs and any conditional smoke checks.
- `sentinels/`
  Lightweight lane and gate status files.

### 7.4 Sentinel set

- `sentinels/ws-a.dispatched`
- `sentinels/ws-a.ready`
- `sentinels/ws-a.blocked`
- `sentinels/ws-a.merged`
- `sentinels/ws-b.dispatched`
- `sentinels/ws-b.ready`
- `sentinels/ws-b.blocked`
- `sentinels/ws-b.merged`
- `sentinels/ws-c.dispatched`
- `sentinels/ws-c.ready`
- `sentinels/ws-c.blocked`
- `sentinels/ws-c.merged`
- `sentinels/ws-d.dispatched`
- `sentinels/ws-d.ready`
- `sentinels/ws-d.blocked`
- `sentinels/ws-d.merged`
- `sentinels/gate-c29-a-contract-freeze.pass`
- `sentinels/gate-c29-b-example-pack.pass`
- `sentinels/gate-c29-c-front-door.pass`
- `sentinels/gate-c29-d-drift-wall.pass`
- `sentinels/gate-c29-final.pass`

## 8. Worktree and Branch Plan

Integration worktree:

- path: `/home/azureuser/__Active_Code/forge`
- branch: `codex/c1b-planning-quality-proof`
- owner: Parent only

Worker worktree root:

- `/home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/`

Worker branches and worktrees:

- `WS-A`
  - branch: `codex/c29-public-subset-a-registry-contract`
  - worktree:
    `/home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-a-registry-contract`
- `WS-B`
  - branch: `codex/c29-public-subset-b-example-pack`
  - worktree:
    `/home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-b-example-pack`
- `WS-C`
  - branch: `codex/c29-public-subset-c-front-door`
  - worktree:
    `/home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-c-front-door`
- `WS-D`
  - branch: `codex/c29-public-subset-d-drift-wall`
  - worktree:
    `/home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-d-drift-wall`

Worktree creation commands:

```bash
mkdir -p /home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-a-registry-contract \
  -b codex/c29-public-subset-a-registry-contract \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-b-example-pack \
  -b codex/c29-public-subset-b-example-pack \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-c-front-door \
  -b codex/c29-public-subset-c-front-door \
  codex/c1b-planning-quality-proof

git -C /home/azureuser/__Active_Code/forge worktree add \
  /home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/ws-d-drift-wall \
  -b codex/c29-public-subset-d-drift-wall \
  codex/c1b-planning-quality-proof
```

Parent merge commands:

```bash
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c29-public-subset-a-registry-contract
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c29-public-subset-b-example-pack
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c29-public-subset-c-front-door
git -C /home/azureuser/__Active_Code/forge merge --no-ff codex/c29-public-subset-d-drift-wall
```

## 9. Conflict Flags

Main cross-lane coupling risks:

- B and C both depend on A vocabulary. If A terminology shifts after dispatch,
  reopen B and C rather than drifting locally.
- B and C together define what D should assert. D must not rewrite product
  truth to make tests pass.
- Any docs/example-pack mismatch belongs to the owning content lane. D may
  expose it, but must not paper over it with weaker assertions.
- The deterministic planning fixture relabeling in C must stay consistent with
  the example taxonomy introduced by B.
- If B introduces example naming or labeling that conflicts with C’s front-door
  language, reopen the owning lane and fix the source, not the test.

## 10. Blocker and Reopen Rules

Mandatory reopen triggers:

- a worker needs to change a file outside its owned paths
- `WS-B`, `WS-C`, or `WS-D` discovers that A’s frozen vocabulary must change
- any lane requires runtime behavior change to complete
- any lane wants to wire the new registry into runtime behavior
- any lane wants to add parser enforcement or task-spec scope
- any lane cannot keep the deterministic planning fixture at its current path
- a test lane failure reveals a real mismatch between `PLAN.md` and merged
  artifacts rather than a simple assertion bug

Parent blocker policy:

- reopen to A if the contract vocabulary itself is wrong
- reopen to B if example taxonomy or file naming is wrong
- reopen to C if front-door wording or relabeling is wrong
- reopen to B and C together only if the blocker is pure terminology drift
  across both lanes
- do not let D silently redefine product truth to make tests pass

## 11. Tests and Acceptance

### 11.1 Gate checks before B and C dispatch

A is review-gated because the drift wall does not exist yet. The parent must
rerun these checks on the integration worktree before dispatching B and C:

```bash
test -f /home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py
test -f /home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md
rg -n "PUBLIC_SUBSET_DSL_VERSION|C3_GRAPH_DSL_KINDS|BROADER_PUBLIC_BUILTIN_KINDS|COMPATIBILITY_ONLY_KINDS|PUBLIC_GRAPH_PRIMITIVES|PUBLIC_TRANSITION_FORMS|PUBLIC_STAGE_FAMILIES|PUBLIC_ROLE_FAMILIES|STAGE_FAMILY_ROLE_BINDINGS|CANONICAL_PLANNING_PHASE_STAGE_TYPES|PLANNING_REQUIRED_POLICY_FIELDS|RUNTIME_OWNED_EXCLUDED_FIELDS|METADATA_ONLY_FIELDS" /home/azureuser/__Active_Code/forge/anvil/harness/public_subset_registry.py
rg -n "c3_strategy_v1|analysis_review_bounded_v1|analysis_review_trust_v1|deterministic_feature_planning_v1|analysis_review_v1|coverage_policy|phase_inputs|schema_version|subset" /home/azureuser/__Active_Code/forge/docs/strategy_dsl_public_subset_contract.md
```

### 11.2 Gate checks before D dispatch

The parent must rerun these checks after merging B and C and before dispatching
D:

```bash
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/README.md
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/canonical/analysis_review_bounded_v1.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/canonical/analysis_review_trust_v1.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/canonical/deterministic_feature_planning_v1.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/compatibility/analysis_review_v1.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/negative/invalid_kind.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/negative/unknown_top_level_key.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/negative/invalid_stage_family.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/negative/runtime_owned_phase_inputs.yaml
test -f /home/azureuser/__Active_Code/forge/examples/harness/public_subset/negative/metadata_only_schema_version.yaml
rg -n "strategy_dsl_public_subset_contract.md|examples/harness/public_subset/README.md" /home/azureuser/__Active_Code/forge/README.md /home/azureuser/__Active_Code/forge/examples/README.md /home/azureuser/__Active_Code/forge/docs/contributing.md
rg -n "internal|fixture-backed|not the canonical public" /home/azureuser/__Active_Code/forge/examples/harness/strategies/deterministic_feature_planning_v1.yaml
```

### 11.3 Final parent validation commands

The parent must rerun all focused tests on the integration branch and must not
claim completion until they all pass on
`codex/c1b-planning-quality-proof`:

```bash
cd /home/azureuser/__Active_Code/forge
poetry run pytest -q tests/test_harness_public_subset_contract.py
poetry run pytest -q tests/test_docs_surface.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Conditional broader smoke tests only if merged diffs unexpectedly touch
adjacent surfaces:

```bash
cd /home/azureuser/__Active_Code/forge
poetry run pytest -q tests/test_harness_strategy_graph.py
poetry run pytest -q tests/test_harness_planning_graph.py
```

### 11.4 Acceptance checklist

- [ ] `anvil/harness/public_subset_registry.py` exists and is data-only.
- [ ] `docs/strategy_dsl_public_subset_contract.md` exists and mirrors the
  registry.
- [ ] Workstream A landed before any example-pack or docs-alignment work
  started.
- [ ] `examples/harness/public_subset/` exists with `canonical/`,
  `compatibility/`, and `negative/`.
- [ ] Canonical examples carry `dsl_version: c3_strategy_v1`.
- [ ] Canonical examples omit runtime-owned and metadata-only fields.
- [ ] `analysis_review_v1` appears only as compatibility-only, never as
  canonical.
- [ ] Front-door docs route readers to the contract doc and public example pack
  first.
- [ ] `examples/harness/strategies/deterministic_feature_planning_v1.yaml`
  remains runnable and is explicitly labeled internal or fixture-backed.
- [ ] `tests/test_harness_public_subset_contract.py` exists and passes.
- [ ] `tests/test_docs_surface.py` passes with the new routing rules.
- [ ] `tests/test_harness_example_strategy_wiring.py` passes with the
  coexistence rules.
- [ ] No runtime behavior change was introduced.

## 12. Assumptions

- The current integration branch remains `codex/c1b-planning-quality-proof` for
  the full execution of this plan.
- The repo-local worktree root
  `/home/azureuser/__Active_Code/forge/.worktrees/c29-public-subset-gate/` is
  available for temporary worker worktrees.
- The existing `poetry` environment is usable for the focused pytest reruns.
