# ORCH_PLAN: M4 Request-Gate Productization Execution Orchestration

## Summary

This document is the execution orchestration plan for implementing `PLAN.md` M4 on top of the already-landed M3 focus-gate base.

Repository authority branch: `feat/bounded-work-redesign`  
Repository root: `/Users/spensermcconnell/__Active_Code/forge`  
Milestone scope: productize the existing pre-proposer focus-gate surface as the explicit request gate for analysis-review runs

Execution stance:

- This is a bounded M4 execution plan, not a redesign plan and not a restatement of `PLAN.md`.
- The parent agent owns the critical path, the runtime-semantics freeze, all final integration, and all closeout proof.
- Real parallelism begins only after the runtime/request-gate contract is frozen at `G1`.
- After `G1`, three delegated lanes are allowed and expected:
  - reporting parity
  - acceptance harness and manifest expansion
  - runner, prompt, and semantic regression expansion
- There are no human approval gates in this plan. Every release gate is technical.

### Worktree And Branch Topology

Use an explicit worktree namespace under the repo:

- Namespace root: `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate`

Branches and worktrees:

| Lane | Owner | Branch | Worktree | Purpose |
|---|---|---|---|---|
| `INT` | Parent-agent-only | `codex/m4-request-gate-int` | `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/int` | Parent integration, critical-path edits, merge target, final validation |
| `RPT` | Delegated after `G1` | `codex/m4-request-gate-reporting` | `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/reporting` | `REPORT.md` and summary or stage parity alignment |
| `ACC` | Delegated after `G1` | `codex/m4-request-gate-acceptance` | `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/acceptance` | acceptance runner, manifest, example wiring |
| `TST` | Delegated after `G1` | `codex/m4-request-gate-tests` | `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/tests` | runner, prompt, and semantic regression expansion |

Authority checkout rule:

- `/Users/spensermcconnell/__Active_Code/forge` remains the source checkout on `feat/bounded-work-redesign`.
- All implementation work happens in `INT` or child worktrees.
- Final landing happens by replaying `INT` back onto `feat/bounded-work-redesign`.

This is stricter than editing the root checkout directly and makes fanout, invalidation, and reintegration explicit.

### Local Orchestration Source Of Truth

The orchestration state lives under:

- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch`

Required files:

- `queue.yaml`
- `status.md`
- `runtime-freeze.md`
- `freeze.sha`
- `integration-plan.md`
- `metrics.md`
- `validation.log`
- `escalations.md`

Required task-state directories:

- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS0`
- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS1`
- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS2-RPT`
- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS3-ACC`
- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS4-TST`
- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS5-INT`
- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/tasks/WS6-CLOSE`

Each task-state directory must contain:

- `state.json`
- `owner.txt`
- `branch.txt`
- `worktree.txt`
- `gate.txt`

Each task-state directory must expose exactly one active sentinel file at a time:

- `READY`
- `RUNNING`
- `BLOCKED`
- `DONE`
- `INTEGRATED`
- `INVALIDATED`

State precedence:

1. `queue.yaml` is the authoritative scheduler and source of truth.
2. `state.json` and the sentinel files are the task-local execution state.
3. `status.md` is the human-readable digest only.

`queue.yaml` must track, per workstream:

- `id`
- `lane`
- `owner`
- `branch`
- `worktree`
- `write_scope`
- `depends_on`
- `gate`
- `state`
- `integration_state`
- `base_freeze_sha`

### Live Acceptance Runtime Paths

Local acceptance manifest path:

- `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch/focus_gate_acceptance_local.yaml`

Live acceptance output root:

- `/Users/spensermcconnell/__Active_Code/forge/.forge-harness-runs-live/m4-request-gate`

## Hard Guards

`HG-1`. M4 must not rebuild M3 machinery.

Reuse as-is unless a true M4 gap is proven:

- typed `focus_type = seam | artifact`
- public `focus_decision`
- blocked deliberate behavior
- stale rerun-answer handling
- artifact singleton bridging
- existing acceptance harness shape

`HG-2`. `focus_decision` remains the only public routing artifact.

`HG-3`. `focus_gate_probe` remains internal-only.

`HG-4`. Exactly two packet families exist in M4:

- `seam`
- `artifact`

`HG-5`. M4 must not introduce:

- a second router
- a third packet family
- a second public artifact
- a new pause or resume lifecycle
- a downstream payload-family rewrite

`HG-6`. The true blast-radius center is parent-only for the full session:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py` only if a real contract gap is proven

`HG-7`. Reporting parity is delegable only after `G1` and only within:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py`

Justification:

- reporting parity is downstream of the frozen request-gate contract
- these files consume the contract, they do not define it
- this creates a real third lane without exposing the core routing machinery to merge churn

`HG-8`. Lane write scopes after `G1` are disjoint by default.

- `RPT` owns reporting files only
- `ACC` owns acceptance files only
- `TST` owns runner, prompt, and semantic regression tests only
- only the parent may cross lane boundaries

`HG-9`. If a delegated lane discovers that its required outcome cannot be achieved without touching a parent-only file, it must stop, mark itself `BLOCKED`, append an entry to `escalations.md`, and wait for parent resolution.

`HG-10`. If the parent must touch a child-owned file to resolve an escalation, that child lane is invalidated and must refresh from the current `INT` head before resuming.

`HG-11`. Any change that causes a blocked focus-gate run to advance to proposer is a release blocker.

`HG-12`. Any change that causes summary, report, or stage parity drift is a release blocker.

`HG-13`. Any change that weakens artifact singleton bridge correctness is a release blocker.

`HG-14`. M4 closeout is incomplete unless the session either captures the available runtime, token, and clarification evidence or explicitly records an instrumentation gap in `metrics.md`.

## Workstream Plan

### WS0: Parent Setup And Queue Bootstrap
Owner: Parent-agent-only  
Lane: `INT`  
Branch: `codex/m4-request-gate-int`  
Worktree: `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/int`  
Start condition: none  
Exit gate: `G0`

`WS0.1`. Create the `INT` worktree from `feat/bounded-work-redesign`.

`WS0.2`. Bootstrap the orchestration state root at `/Users/spensermcconnell/__Active_Code/forge/.gstack/m4-request-gate/orch`.

`WS0.3`. Initialize `queue.yaml` with all workstreams and their initial dependency graph.

`WS0.4`. Create each `tasks/<WS>` state directory and place initial sentinels.

`WS0.5`. Seed `focus_gate_acceptance_local.yaml` from:

- `/Users/spensermcconnell/__Active_Code/forge/examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml`

Set:

- `workspace: /Users/spensermcconnell/__Active_Code/forge`
- `out_root: .forge-harness-runs-live/m4-request-gate`

`WS0.6`. Capture baseline `HEAD`, branch ancestry, and current test status in `validation.log`.

`WS0.7`. Run the repo-local baseline commands from `INT`:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Acceptance criteria:

- `queue.yaml` exists and is complete for `WS0` through `WS6`
- every workstream has a state directory and exactly one sentinel
- `INT` worktree is live and clean
- baseline command outcomes are recorded

Gate `G0`:

- baseline understood and queue bootstrap complete
- if baseline is red, the parent must classify red tests as pre-existing or M4-relevant in `status.md` before continuing

### WS1: Parent Runtime-Semantics Freeze
Owner: Parent-agent-only  
Lane: `INT`  
Start condition: `G0`  
Exit gate: `G1`

Parent-only write scope:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py` only if needed

`WS1.1`. Lock runtime semantics in `runner.py`.

Required outcomes:

- the existing focus-gate surface is the explicit M4 request gate for analysis-review runs
- adjudicate is the cheap obvious-case path
- deliberate is the ambiguity path
- blocked outcomes halt before proposer
- `focus_decision` finalizes before proposer starts
- artifact-selected flows keep the existing downstream singleton bridge
- no second router or second public artifact appears

`WS1.2`. Lock prompt or policy semantics in `prompts.py`.

Required outcomes:

- adjudicate language encodes request-only obvious-case behavior
- deliberate language encodes ambiguity handling, shortlist use, and stale rerun-answer rules
- probe remains clearly internal-only in prompt semantics

`WS1.3`. Tighten semantic validation.

Required outcomes:

- public invariants are enforced semantically, not just by prompt text
- `focus_type` remains exactly `seam | artifact`
- gate-path expectations are enforced
- artifact singleton bridge invariants stay canonical
- blocked serialization rules stay explicit and stable

`WS1.4`. Touch `schemas.py` only if a true M4 contract gap is discovered and logged.

`WS1.5`. Write `runtime-freeze.md`.

`runtime-freeze.md` must freeze:

- the single-public-artifact rule
- the internal-only probe rule
- the two-packet-family rule
- adjudicate versus deliberate semantics
- blocked-before-proposer semantics
- artifact-bridge semantics
- summary, report, and stage parity obligations
- lane write scopes
- invalidation rules tied to `freeze.sha`

`WS1.6`. Record the fanout anchor in `freeze.sha`.

`WS1.7`. Update `queue.yaml` so `RPT`, `ACC`, and `TST` move from `BLOCKED` to `READY` only if `G1` passes.

Acceptance criteria:

- parent-only runtime files reflect the M4 request-gate contract
- `runtime-freeze.md` is complete and specific enough for delegation
- `freeze.sha` points at the exact fanout base commit
- no delegated lane has started before this gate passes

Gate `G1`:

Run and log:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
```

`G1` is green only if all three commands pass from `INT`.

### WS2-RPT: Delegated Reporting Parity Lane
Owner: Delegated after `G1`  
Lane: `RPT`  
Branch: `codex/m4-request-gate-reporting`  
Worktree: `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/reporting`  
Start condition: `G1`  
Exit gate: `G2-RPT`

Write scope:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py`

Optional write scope only if strictly needed and pre-declared in `queue.yaml`:

- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_reporting.py`

`WS2-RPT.1`. Align reporting with the frozen request-gate contract.

`WS2-RPT.2`. Ensure `REPORT.md` tells the same request-gate story as:

- `summary.json`
- persisted `focus_gate` stage metadata
- `run_details.focus_decision`

`WS2-RPT.3`. Make blocked runs visibly show that the review loop did not execute.

`WS2-RPT.4`. Make artifact-selected runs visibly show singleton selection plus downstream bridge basis.

`WS2-RPT.5`. Do not redefine runtime semantics or expand public contract shape.

Acceptance criteria:

- `REPORT.md` renders one consistent request-gate result per run
- selected seam, selected artifact, `clarification_requested`, and `no_viable_focus` all have report output consistent with summary and stage metadata
- blocked runs do not read as partial successful review runs
- artifact-selected runs do not hide the singleton versus downstream-bridge distinction
- no changes occur outside the `RPT` write scope

Gate `G2-RPT`:

- parent-reviewed diff confirms parity intent is purely downstream
- if targeted reporting tests exist, run them and log them
- if no targeted reporting tests exist, record that explicitly in `validation.log` and defer full parity proof to `G4` and `G5`

### WS3-ACC: Delegated Acceptance Harness Lane
Owner: Delegated after `G1`  
Lane: `ACC`  
Branch: `codex/m4-request-gate-acceptance`  
Worktree: `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/acceptance`  
Start condition: `G1`  
Exit gate: `G2-ACC`

Write scope:

- `/Users/spensermcconnell/__Active_Code/forge/scripts/run_focus_gate_acceptance.py`
- `/Users/spensermcconnell/__Active_Code/forge/examples/harness/live_acceptance/`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_run_focus_gate_acceptance.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_example_strategy_wiring.py`

`WS3-ACC.1`. Expand the canonical live-acceptance manifest only within M4 scope.

Required scenario families:

- clear seam selected via adjudicate
- clear artifact selected via adjudicate
- deliberate ambiguity to `clarification_requested` for seam
- deliberate ambiguity to `clarification_requested` for artifact
- `never_ask` to `no_viable_focus` for seam
- `never_ask` to `no_viable_focus` for artifact
- stale rerun-answer to `clarification_requested` for seam
- stale rerun-answer to `clarification_requested` for artifact
- compatibility wiring for existing M3 seam-happy-path surfaces

`WS3-ACC.2`. Tighten acceptance assertions around:

- `summary=` and `report=` path emission
- `focus_decision` presence in summary
- `focus_gate` stage metadata parity
- `focus_gate_probe` ordering for deliberate scenarios
- blocked-before-proposer behavior
- artifact singleton bridge parity
- stale warning substring behavior

`WS3-ACC.3`. Preserve the existing acceptance-runner shape.

`WS3-ACC.4`. Preserve template and example wiring integrity.

Acceptance criteria:

- canonical template covers the M4 scenario matrix without inventing a new runner or manifest family
- acceptance assertions fail hard on summary, report, and stage parity drift
- deliberate blocked runs prove no proposer execution
- artifact-selected acceptance cases prove singleton and downstream bridge consistency
- compatibility wiring remains intact

Gate `G2-ACC`:

Run and log:

```bash
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

### WS4-TST: Delegated Regression Expansion Lane
Owner: Delegated after `G1`  
Lane: `TST`  
Branch: `codex/m4-request-gate-tests`  
Worktree: `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate/tests`  
Start condition: `G1`  
Exit gate: `G2-TST`

Write scope:

- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py`

`WS4-TST.1`. Expand runner coverage for the frozen request-gate semantics.

`WS4-TST.2`. Expand prompt consistency coverage for the frozen public and private boundary and adjudicate versus deliberate split.

`WS4-TST.3`. Expand semantic-validation coverage for the frozen public invariants.

`WS4-TST.4`. Do not edit runtime files. If runtime changes are required, escalate.

Acceptance criteria:

- runner tests prove selected seam, selected artifact, blocked ambiguity, `never_ask`, and stale rerun-answer paths against the frozen contract
- prompt tests prove adjudicate and deliberate semantics are spelled distinctly and probe remains internal-only
- semantic-validation tests prove the M4 public invariants fail hard when violated
- no changes occur outside the `TST` write scope

Gate `G2-TST`:

Run and log:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
```

### WS5-INT: Parent Integration, Conflict Resolution, And Full Repo-Local Proof
Owner: Parent-agent-only  
Lane: `INT`  
Start condition: `G2-RPT`, `G2-ACC`, and `G2-TST`  
Exit gate: `G3`

`WS5-INT.1`. Validate child-lane freshness before merge.

For each child lane:

- compare its `base_freeze_sha` to current `freeze.sha`
- if they differ, mark the lane `INVALIDATED`
- require refresh or rebase from current `INT` before merge

`WS5-INT.2`. Merge order is exact:

1. `TST`
2. `RPT`
3. `ACC`

Rationale:

- `TST` validates the frozen contract without changing runtime surfaces
- `RPT` consumes the frozen contract and may influence downstream parity expectations
- `ACC` is merged last so acceptance assertions encode the actual final integrated parity behavior

`WS5-INT.3`. After each merge, re-run the owning gate before continuing.

- after `TST` merge: rerun `G2-TST`
- after `RPT` merge: rerun `G2-RPT` if targeted tests exist, otherwise run the smallest parity smoke available and log that the lane relies on `G4` and `G5` for full proof
- after `ACC` merge: rerun `G2-ACC`

`WS5-INT.4`. Escalation handling rules.

- if a child lane is `BLOCKED`, parent resolves the issue in `INT`
- if parent resolves by touching a child-owned file, that child lane becomes `INVALIDATED`
- if parent resolves by touching a parent-only file, all unmerged child lanes remain valid only if `freeze.sha` is unchanged and `runtime-freeze.md` is still semantically identical
- if parent changes frozen semantics in any meaningful way, parent must:
  - update `runtime-freeze.md`
  - write a new `freeze.sha`
  - mark all child lanes `INVALIDATED`
  - require all child lanes to refresh from the new `INT` head

`WS5-INT.5`. Run the full repo-local M4 matrix from `INT`:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Acceptance criteria:

- all merged lane work is integrated into `INT`
- all child lane sentinels are either `INTEGRATED` or `INVALIDATED`
- full repo-local matrix passes from `INT`
- no out-of-scope file churn was introduced during reintegration

Gate `G3`:

- full repo-local M4 proof green from `INT`

### WS6-CLOSE: Parent Live Acceptance, Quantified Proof Capture, And Landing
Owner: Parent-agent-only  
Lane: `INT`  
Start condition: `G3`  
Exit gates: `G4`, `G5`, and `G6`

`WS6-CLOSE.1`. Run the live acceptance harness from `INT`:

```bash
poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance_local.yaml \
  --workspace /Users/spensermcconnell/__Active_Code/forge \
  --out-root .forge-harness-runs-live/m4-request-gate
```

`WS6-CLOSE.2`. Verify scenario-level acceptance artifacts.

For every scenario, confirm:

- `summary=` path emitted
- `report=` path emitted
- blocked scenarios stop before proposer
- selected scenarios produce proposer artifacts
- artifact-selected scenarios preserve singleton and bridge parity
- stale rerun scenarios surface the expected warning
- overall output ends with `{"overall":"PASS"}`

`WS6-CLOSE.3`. Capture quantified proof or explicit instrumentation gap in `metrics.md`.

`metrics.md` must contain one of these outcomes:

Outcome A: available evidence captured  
Record whatever the current harness exposes for:

- wrong-route rate on sampled seam requests
- wrong-route rate on sampled artifact requests
- median time from run start to final request-gate decision
- clarification rate on ambiguous requests
- count of runs blocked before expensive review
- runtime or token delta if token or runtime metrics are present in summaries or stage artifacts

Outcome B: instrumentation gap logged  
If one or more metrics are not extractable, write a concrete gap note naming:

- which metric is missing
- which artifact was inspected
- which field or instrumentation is absent
- whether the missing proof is a closeout caveat versus a release blocker

`WS6-CLOSE.4`. Record final validation evidence in `validation.log`.

Include:

- every final command
- pass or fail result
- representative summary and report paths
- final `INT` `HEAD`
- final diff scope

`WS6-CLOSE.5`. Run closeout audit against M4 hard guards.

Explicitly confirm:

- no second router
- no third packet family
- no second public artifact
- no new pause or resume lifecycle
- no downstream payload-family rewrite
- `focus_decision` remains the only public routing artifact
- `focus_gate_probe` remains internal-only

`WS6-CLOSE.6`. Land `INT` back onto `feat/bounded-work-redesign`.

- replay `INT` onto `feat/bounded-work-redesign`
- re-run the final mandatory matrix on the landing branch if the replay changed commit shape
- mark queue entries `INTEGRATED`

Acceptance criteria:

- live acceptance passes
- quantified evidence is either captured or explicitly gap-logged
- closeout audit passes
- final landing branch is `feat/bounded-work-redesign` with the integrated M4 result

Gate `G4`:

- live acceptance green

Gate `G5`:

- quantified proof captured or instrumentation gap explicitly logged

Gate `G6`:

- closeout audit and landing complete

## Context-Control Rules

`CCR-1`. `queue.yaml` is the authoritative scheduler and ownership record for the session.

`CCR-2`. A delegated lane may start only if:

- its dependency gate is green
- its sentinel is `READY`
- its `base_freeze_sha` matches `freeze.sha`

`CCR-3`. The parent agent is the only integrator. Child lanes never merge directly into each other.

`CCR-4`. The parent agent owns all cross-lane decisions and all changes to `runtime-freeze.md`.

`CCR-5`. Child lanes receive only the minimal bounded context:

- `runtime-freeze.md`
- their exact write scope
- their exact branch and worktree
- their exact gate
- invalidation rules
- escalation path

`CCR-6`. `status.md` must summarize, at all times:

- active gate
- active owner per lane
- blocked lanes
- invalidated lanes
- next integration action

`CCR-7`. `escalations.md` is append-only while any delegated lane is active.

Each escalation entry must include:

- workstream ID
- current `freeze.sha`
- failing file, test, or artifact
- whether the issue is runtime, reporting, acceptance, or regression
- whether the lane is blocked or invalidated

`CCR-8`. If the parent edits a child-owned file during escalation, that child lane becomes stale immediately and must refresh before any merge.

`CCR-9`. If `freeze.sha` changes, all non-integrated child lanes become stale immediately and must refresh before any merge.

`CCR-10`. No lane may silently widen scope by opportunistically editing adjacent files.

`CCR-11`. The acceptance output directory is evidence, not scheduler state. Scheduler state remains under `.gstack/m4-request-gate/orch`.

## Tests And Acceptance

Mandatory repo-local command set:

```bash
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_run_focus_gate_acceptance.py
poetry run pytest -q tests/test_harness_example_strategy_wiring.py
```

Mandatory live acceptance command:

```bash
poetry run python scripts/run_focus_gate_acceptance.py \
  --config .gstack/m4-request-gate/orch/focus_gate_acceptance_local.yaml \
  --workspace /Users/spensermcconnell/__Active_Code/forge \
  --out-root .forge-harness-runs-live/m4-request-gate
```

Technical gates only:

- `G0`: baseline understood and queue bootstrap complete
- `G1`: runtime-semantics freeze green
- `G2-RPT`: reporting lane accepted
- `G2-ACC`: acceptance lane accepted
- `G2-TST`: regression lane accepted
- `G3`: full repo-local matrix green in `INT`
- `G4`: live acceptance green
- `G5`: quantified proof captured or instrumentation gap logged
- `G6`: closeout audit and landing complete

Session closeout is valid only if all of the following are true:

- selected seam flow proven
- selected artifact flow proven
- blocked ambiguity proven
- `never_ask` block proven
- stale rerun-answer handling proven
- blocked-before-proposer invariant proven
- summary, report, and stage parity proven
- `focus_decision` remains the only public routing artifact
- `focus_gate_probe` remains internal-only
- all queue entries are `INTEGRATED` or intentionally `INVALIDATED`
- metrics are captured or gap-logged

## Assumptions

`A-1`. The M3 typed focus-gate base is already the correct starting point on `feat/bounded-work-redesign`.

`A-2`. The repo can support local git worktrees under `/Users/spensermcconnell/__Active_Code/forge/.worktrees/m4-request-gate`.

`A-3`. `poetry` and the listed pytest commands are usable from the repo environment.

`A-4`. The live acceptance manifest referenced by the existing template remains the correct M4 acceptance surface.

`A-5`. The workspace for local live acceptance is the repo root:

- `/Users/spensermcconnell/__Active_Code/forge`

`A-6`. Reporting parity can be delegated safely after `G1` because `report.py` and `reporting.py` consume the frozen request-gate contract rather than defining it.

`A-7`. `anvil/harness/schemas.py` should remain untouched unless a real public contract gap is proven during `WS1`.

`A-8`. If current harness artifacts do not expose enough timing or token fields for full quantified proof, logging that instrumentation gap explicitly in `metrics.md` is acceptable and required. Silently omitting it is not.

`A-9`. No additional milestone or human approval process exists for M4. Only the technical gates in this document control fanout, integration, and closeout.
