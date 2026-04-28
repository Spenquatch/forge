<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260428-173839.md -->
# PLAN: M3 Typed Focus Gate Finalization

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Supersedes: the stale M2 implementation plan that previously lived at this path
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260428-173839.md`
Implementation baseline: M2 focus-gate v9 behavior is landed on this branch at `HEAD`

## Plan Summary

Do not spend this branch re-implementing M2.

The focus gate is already real:

- `focus_gate_probe` and `focus_gate` both exist in `anvil/harness/runner.py`
- split prompt builders already exist in `anvil/harness/prompts.py`
- `clarification_policy = never_ask` already survives parse -> contract -> runner -> report
- stale rerun-answer handling already exists and is candidate-aware
- the widened `focus_decision` artifact already exists in schema, semantic validation, and report rendering
- the targeted regression sweep is green:
  - `poetry run pytest -q tests/test_harness_analysis_contract.py tests/test_harness_prompt_consistency.py tests/test_harness_semantic_validation.py tests/test_harness_runner.py tests/test_harness_reporting.py tests/test_run_m2_focus_gate_live_acceptance.py`
  - `259 passed`
- saved run artifacts already prove:
  - clean adjudicate selection on `.forge-harness-runs-live/20260427T232849Z-recommend_automation_improvements-e56c861f`
  - deliberate clarification block on `.forge-harness-runs/m2-live-deliberate-block-v2/...`
  - deliberate `never_ask` normalization on `.forge-harness-runs/m2-live-deliberate-never-ask-v2/...`
  - deliberate stale-answer handling on `.forge-harness-runs/m2-live-deliberate-stale-v2/...`

M3 is therefore the final milestone for the feature, not another seam-only hardening pass.

The M3 job is:

1. extract a real typed gate core
2. move remaining seam assumptions behind an adapter boundary
3. prove one second real `focus_type`
4. leave the public surface stable: `focus_gate`, `focus_gate_answer`, and top-level `focus_decision`

## Step 0: Scope Challenge

### Mode Selection

Use **SELECTIVE EXPANSION**.

The right move is to finish the feature, not widen it into a general request router.

Stay inside:

- the existing analysis-review harness
- the existing runner-owned `focus_decision` artifact family
- the existing bounded/trust product split
- the existing pre-loop gate flow

Do not widen into:

- a generic planning subsystem
- multi-task routing across unrelated task kinds
- pause/resume lifecycle work
- a downstream non-seam analysis payload rewrite

### Premise Challenge

| Premise | Verdict | Why |
|---|---|---|
| M2 is materially landed and should be treated as baseline, not planned work. | Accept | Code, tests, docs, and saved deliberate-path artifacts all exist at `HEAD`. |
| The final milestone should prove real typed reuse with a second focus type. | Accept | The current code still looks typed in branding but seam-only in substance. |
| The second focus type should be `artifact`, not another seam-adjacent label like `subsystem`. | Accept | `artifact` is narrower, more honest, and grounded in real workflow / manifest review tasks already present in this repo. |
| M3 should preserve the current public artifact shell and runner-owned decision ownership. | Accept | Replacing `focus_decision` now would throw away the cleanest part of M2. |
| M3 should allow mixed-type arbitration inside one run, for example `["seam", "artifact"]` simultaneously. | Reject | That is a second problem. M3 should prove multiple supported types, not heterogeneous ranking in one gate call. |
| M3 should widen the downstream analysis payload away from `primary_seam` immediately. | Reject | That is a separate downstream genericity project. M3 only needs a clean adapter boundary into the existing seam-shaped loop. |
| The old `run_m2_focus_gate_live_acceptance.py` and `m2_focus_gate_local.template.yaml` naming can stay forever. | Reject | Final feature polish should not fossilize milestone names in public acceptance tooling. |

### What Already Exists

| Sub-problem | Existing code | Reuse decision |
|---|---|---|
| typed gate policy surface | `anvil/harness/types.py`, `anvil/harness/contracts.py` | Reuse. Widen the allowed type set, do not invent a second config family. |
| gate orchestration | `HarnessRunner._run_focus_gate()` and its probe / decision helpers in `anvil/harness/runner.py` | Reuse. Make the gate core call adapters, not seam helpers directly. |
| gate artifact shell | `focus_gate_output_schema()` and `focus_gate_probe_output_schema()` in `anvil/harness/schemas.py` | Reuse. Widen enums and type-specific invariants in place. |
| semantic validation entrypoint | `validate_stage_output()` in `anvil/harness/semantic_validation.py` | Reuse. Route through typed focus validators plus adapter-derived downstream expectations. |
| report surfacing | `anvil/harness/report.py` | Reuse. Keep one `## Focus Decision` section and make it type-aware. |
| deliberate-path proof surface | saved M2 deliberate artifacts under `.forge-harness-runs/` | Reuse as baseline evidence. Add second-type proof instead of rebuilding the seam matrix. |
| live acceptance helper pattern | `scripts/run_m2_focus_gate_live_acceptance.py` plus template manifest under `examples/harness/live_acceptance/` | Reuse, but rename and generalize for post-M2 feature ownership. |

### Current Code Reality at `HEAD`

M2 closed the behavioral gaps. The remaining problem is structural honesty.

| Area | Current behavior at `HEAD` | M3 change |
|---|---|---|
| typed contract | `FocusGatePolicy.allowed_focus_types` in `anvil/harness/contracts.py` still resolves only `["seam"]` | support exactly one selected type per run, chosen from `["seam"]` or `["artifact"]` |
| task parsing | `_validate_m1_allowed_focus_types()` in `anvil/harness/types.py` hard-rejects non-seam values | replace the M1-only validator with a real focus-type whitelist validator |
| public schema | `focus_type` enum in `anvil/harness/schemas.py` is still `["seam"]` | widen to `["seam", "artifact"]` |
| semantic validation | focus-decision validation assumes canonical seam IDs and seam path semantics | split generic focus validation from seam-specific adapter validation |
| runner handoff | downstream validation receives raw gate-selected seam expectations | runner should ask the focus adapter for downstream seam expectations |
| identity helpers | `canonical_seam_id_for_paths()` is the only canonical focus identity helper | introduce a typed identity layer so seam and artifact IDs are both first-class |
| acceptance tooling | helper + docs still carry M2-specific names | rename to generic focus-gate acceptance tooling and add typed scenario manifests |

### Minimum Change That Achieves the Goal

The minimum complete M3 is:

1. keep the current public `focus_gate`, `focus_gate_answer`, and `focus_decision` names
2. add a typed adapter boundary between gate-core logic and seam-specific downstream expectations
3. support a second real `focus_type = artifact`
4. keep `allowed_focus_types` single-valued per run in M3, even though the field remains plural
5. keep the downstream analysis-review loop seam-shaped, but derive its expected seam from the selected adapter
6. generalize acceptance tooling so post-M2 proof is inspectable without milestone-specific script names
7. prove both seam and artifact paths through adjudicate and deliberate behavior

Anything smaller is a cosmetic finish:

- adding `"artifact"` to an enum without removing seam hardcoding is not enough
- choosing a second type that is just seam with a new name is not enough
- shipping only an artifact happy path with no deliberate-path proof is not enough
- leaving `run_m2_focus_gate_live_acceptance.py` as the permanent acceptance entrypoint is not enough

## M3 Product Decision

### Chosen Second Focus Type: `artifact`

M3 should prove genericity with `focus_type = artifact`.

This is the right proof for this repo because:

- it is materially different from seam
  - seam = a run-context review unit with recommendation-binding expectations
  - artifact = a governing file focus chosen before the seam-shaped loop begins
- it is already implied by current tasks
  - workflow files
  - manifests
  - governing specs
- it keeps the adapter honest
  - the gate selects one concrete repo artifact
  - the adapter maps that artifact into a seam-shaped downstream starting point
  - later stages may widen into sibling seams when justified
- it does not require a second downstream payload family

Why not `subsystem` in M3:

- too close to current seam behavior
- too easy to fake with new names over the same path-set logic

Why not `policy_surface` in M3:

- not grounded in current tasks
- higher ambiguity
- worse proof packet for a final milestone

### Artifact Rules in M3

`artifact` is intentionally narrow in the first proof packet.

Normative M3 artifact rules:

- `focus_type = artifact`
- `selected_focus_paths` must contain exactly one canonical workspace path
- `candidates[*].candidate_paths` must contain exactly one canonical workspace path
- `checked_files` may include corroborating files beyond the selected artifact
- `selected_focus_id` is a typed artifact ID, not a seam ID
- the artifact adapter derives the downstream seam expectation from the selected artifact path

This is important because it forces M3 to prove the adapter boundary with a genuinely different focus object instead of another multi-file path-set.

## Architecture Plan

### 1. Introduce a Typed Focus Adapter Layer

Add a new focus-type module, for example:

- `anvil/harness/focus_types.py`

It should define the boring interface M3 needs:

- focus type enum / literals
- typed canonical ID helpers
- candidate normalization hooks
- prompt instruction hooks
- public focus-decision semantic invariants
- downstream adapter expectations for analysis-review

Minimum adapter contract:

```text
FocusTypeAdapter
  - focus_type_name()
  - validate_allowed_focus_types(...)
  - normalize_candidate(...)
  - canonical_focus_id(candidate_paths)
  - validate_focus_decision(...)
  - prompt_rules_for_probe()
  - prompt_rules_for_decision()
  - adapt_selected_focus_to_analysis_review(...)
```

Required concrete adapters:

- `SeamFocusAdapter`
- `ArtifactFocusAdapter`

### 2. Split Generic Gate Validation from Seam Validation

Today focus validation and downstream seam expectations are intertwined.

M3 should separate them:

- generic focus validation checks:
  - `gate_path`
  - `focus_type`
  - `decision_state`
  - `decision_basis`
  - candidate count caps
  - `checked_files`
  - warnings / question shape
- adapter validation checks:
  - seam-specific ID/path invariants for `focus_type = seam`
  - artifact-specific single-path invariants for `focus_type = artifact`
- downstream analysis validation checks:
  - continue to enforce `primary_seam` and recommendation seam binding
  - but only against adapter-derived expected seam state

That keeps the gate core typed while preserving the current downstream rigor.

### 3. Keep the Public Artifact Stable

M3 keeps the existing shell:

```json
{
  "gate_path": "...",
  "focus_type": "...",
  "decision_state": "...",
  "decision_basis": "...",
  "selected_focus_id": "...",
  "selected_focus_summary": "...",
  "selected_focus_paths": [],
  "confidence": 0.0,
  "confidence_band": "...",
  "files_hint_disposition": "...",
  "checked_files": [],
  "candidates": [],
  "question": {"prompt": "", "options": []},
  "warnings": [],
  "adapter_plan": {...}
}
```

M3 changes:

- widen `focus_type` enum to `seam | artifact`
- keep `decision_basis` unchanged
- keep `adapter_plan` as the runner-owned bridge
- do not add `focus_decision_v2`

### 4. Make the Runner Ask the Adapter for Downstream Expectations

The runner should no longer assume the selected focus is already a seam.

Instead:

1. run probe / decision normally
2. normalize the public `focus_decision`
3. resolve the adapter from `focus_type`
4. ask the adapter for downstream seam expectations
5. pass those expectations into proposer / reviser semantic validation

For `focus_type = seam`:

- the adapter returns the current path-set-derived primary seam expectation

For `focus_type = artifact`:

- the adapter returns a one-file primary seam expectation rooted at the selected artifact path
- later seam expansion remains a downstream review responsibility, not a gate-core concern

### 5. Generalize Acceptance Tooling

M3 should retire milestone-specific acceptance naming.

Replace:

- `scripts/run_m2_focus_gate_live_acceptance.py`
- `examples/harness/live_acceptance/m2_focus_gate_local.template.yaml`
- docs that point at `m2_focus_gate_local.yaml`

With something like:

- `scripts/run_focus_gate_acceptance.py`
- `examples/harness/live_acceptance/focus_gate_local.template.yaml`
- typed scenario manifests, for example:
  - `focus_gate_seam_local.template.yaml`
  - `focus_gate_artifact_fixture.yaml`

The important point is not the exact filenames.

The important point is that the feature should end with a generic acceptance surface, not one frozen to its M2 milestone packet.

## Implementation Slices

### Slice 0: M2 Closure Hygiene

Goal:

- clean the feature boundary before widening it

Work:

1. replace stale M2 wording in `PLAN.md` and any remaining doc text that still describes landed code as pending work
2. fix the manifest naming mismatch:
   - docs and helper should not point at a non-existent `m2_focus_gate_local.yaml`
   - keep the template flow explicit
3. preserve the clean adjudicate and deliberate saved-run references in docs or acceptance notes

Done when:

- no public doc tells the user to use a missing local manifest filename
- M2 is described as landed baseline, not future work

### Slice 1: Typed Focus Adapter Core

Goal:

- extract seam assumptions out of gate-core orchestration

Work:

1. add adapter module and typed focus-type enum support
2. widen task / contract / schema parsing to `seam | artifact`
3. keep `allowed_focus_types` single-valued per run in M3
4. route focus-decision normalization and semantic validation through the adapter layer

Done when:

- gate-core code no longer reaches directly for seam-only canonicalization helpers
- seam logic lives behind the seam adapter
- artifact logic lives behind the artifact adapter

### Slice 2: Artifact Focus Packet

Goal:

- land one second real focus type

Work:

1. define artifact candidate and selected-focus invariants
2. add artifact-specific prompt instructions for adjudicate and deliberate
3. implement artifact -> analysis-review seam adaptation
4. add at least one artifact-focused task / fixture packet

Done when:

- the runner can complete an analysis-review run with `allowed_focus_types: [artifact]`
- downstream semantic validation still receives seam expectations and stays strict

### Slice 3: Report + Artifact Honesty

Goal:

- make typed focus visible and inspectable

Work:

1. render `artifact` focus decisions without seam-only wording
2. keep stale-answer callouts, decision basis, checked files, and candidate comparison intact for both types
3. make report language talk about "selected focus" first and seam adaptation second

Done when:

- `REPORT.md` reads correctly for both seam and artifact runs
- no user-facing report line implies every focus target is already a seam

### Slice 4: Generic Acceptance Matrix

Goal:

- prove the final feature, not one branch of it

Work:

1. keep the saved M2 seam proofs as the baseline typed-seam packet
2. add artifact adjudicate acceptance
3. add artifact deliberate ambiguity acceptance
4. add artifact `never_ask` acceptance
5. add artifact stale-rerun acceptance
6. run bounded and trust for the artifact selected path when the task is the same

Done when:

- the acceptance helper / manifests can reproduce both seam and artifact proof packets
- the saved outputs are inspectable without relying on one workstation-specific memory dump

## File and Module Plan

Expected touched modules:

- `anvil/harness/types.py`
- `anvil/harness/contracts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/runner.py`
- `anvil/harness/report.py`
- `[ADD] anvil/harness/focus_types.py`
- `scripts/run_m2_focus_gate_live_acceptance.py` or its renamed replacement
- `README.md`
- `examples/README.md`
- `docs/analysis_review_contract.md`
- `examples/harness/live_acceptance/*`
- new task / strategy / fixture packets for artifact acceptance
- targeted harness tests

Keep the architecture boring:

- no new strategy kind
- no new task kind
- no new top-level public focus artifact
- no mixed-type arbitration in one run
- no downstream non-seam payload family

## Test Review

### Test Strategy

M3 should add the smallest complete proof surface that makes the typed claim true.

That means:

- unit coverage for parsing and identity rules
- semantic-validation coverage for typed focus invariants
- runner coverage for seam and artifact handoff
- reporting coverage for type-aware rendering
- acceptance coverage for both gate paths, not just adjudicate

### Code Path Coverage

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/types.py + contracts.py
    │
    ├── focus_gate.allowed_focus_types
    │   ├── [EXISTS] seam
    │   └── [ADD]    artifact
    │
    └── single-selected-type rule
        └── [ADD]    reject mixed seam+artifact lists in M3

[+] anvil/harness/schemas.py + semantic_validation.py
    │
    ├── focus_type enum
    │   ├── [EXISTS] seam
    │   └── [ADD]    artifact
    │
    ├── seam adapter invariants
    │   └── [EXISTS] selected seam path-set + canonical seam ID checks
    │
    └── artifact adapter invariants
        ├── [ADD] selected_focus_paths length == 1
        ├── [ADD] candidate_paths length == 1
        └── [ADD] typed artifact ID checks

[+] anvil/harness/prompts.py
    │
    ├── generic gate-core instructions
    │   └── [ADD] adapter-provided type rules
    │
    ├── seam guidance
    │   └── [EXISTS] path-set / seam semantics
    │
    └── artifact guidance
        └── [ADD] governing-file focus semantics

[+] anvil/harness/runner.py
    │
    ├── focus_gate_probe
    │   └── [EXISTS] generic probe orchestration
    │
    ├── focus_gate decision normalization
    │   └── [ADD] adapter-resolved typed normalization
    │
    └── downstream handoff
        ├── [EXISTS] seam expectations
        └── [ADD] artifact -> seam adapter expectations

[+] anvil/harness/report.py
    │
    ├── focus decision section
    │   ├── [EXISTS] seam rendering
    │   └── [ADD] artifact-aware wording
    │
    └── stale-answer callouts
        └── [EXISTS] keep identical behavior across types

[+] acceptance tooling
    │
    ├── seam packet
    │   └── [EXISTS] reuse saved M2 proof
    │
    └── artifact packet
        ├── [ADD] adjudicate selected
        ├── [ADD] deliberate block
        ├── [ADD] deliberate never_ask
        └── [ADD] deliberate stale rerun
```

### Targeted Pytest Sweep

Run at minimum:

```bash
poetry run pytest -q \
  tests/test_harness_analysis_contract.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_semantic_validation.py \
  tests/test_harness_runner.py \
  tests/test_harness_reporting.py \
  tests/test_run_m2_focus_gate_live_acceptance.py
```

Add new focused tests for:

- typed allowed-focus parsing
- mixed-type rejection in M3
- artifact decision schema + semantic validation
- artifact -> seam adapter expectations
- artifact deliberate stale rerun normalization
- generic acceptance helper manifest validation

### Acceptance Matrix

M3 is done only when the feature is proven across both supported focus types.

Seam packet baseline:

1. adjudicate selected, accepted or publishable baseline proof
2. deliberate ambiguous -> `blocked_for_clarification`
3. deliberate ambiguous + `never_ask` -> `no_viable_focus`
4. deliberate stale `focus_gate_answer` -> stale warning + normalized block

Artifact packet:

1. adjudicate clear artifact selection, bounded
2. adjudicate clear artifact selection, trust
3. deliberate ambiguous artifact -> `blocked_for_clarification`
4. deliberate ambiguous artifact + `never_ask` -> `no_viable_focus`
5. deliberate stale artifact rerun answer -> stale warning + normalized block

For each packet inspect:

- `summary.json`
- `REPORT.md`
- `artifacts/*focus_gate_probe*/structured_output.*`
- `artifacts/*focus_gate*/structured_output.*`
- proposer normalized payload for adapter-derived seam expectations

## Risks and Failure Modes

| Risk | Why it happens | Prevention |
|---|---|---|
| `"artifact"` is added only to enums, while seam helpers still own identity and downstream expectations | fake genericity | force the runner through an adapter boundary before proposer validation |
| artifact focus is just seam with a one-file path set and no changed semantics | weak proof | require artifact-specific validation and report wording, not just smaller candidate lists |
| mixed seam+artifact ranking sneaks into the milestone | scope creep | explicitly reject heterogeneous `allowed_focus_types` lists in M3 |
| artifact tasks feel too narrow to be useful | wrong second type packet | author artifact tasks around governing workflow / manifest reviews where single-file focus is actually the product |
| acceptance tooling stays M2-branded and confusing | milestone-specific cleanup deferred | rename helper + template as part of the feature finalization slice |

## NOT in Scope

- mixed-type arbitration inside one run
- a new task kind outside `analysis_review`
- a generic front-door request classifier for the whole harness
- a non-seam downstream output family
- pause / resume lifecycle for clarification
- more than two supported focus types in this milestone

## Definition of Done

M3 is done only when all of these are true:

1. the gate core no longer hardcodes seam-only decision semantics outside the seam adapter
2. `focus_type = artifact` is supported end to end
3. the public `focus_decision` artifact remains stable
4. `allowed_focus_types` supports `seam` and `artifact`, but M3 still rejects mixed-type lists
5. artifact runs adapt cleanly into the current seam-shaped analysis-review loop
6. report rendering reads correctly for both focus types
7. acceptance tooling is genericized beyond M2-specific naming
8. the seam packet and artifact packet both pass their acceptance matrices

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Scope | Treat M2 as landed baseline | Auto-decided | Explicit over clever | The branch already contains code, docs, tests, and saved deliberate-path artifacts for M2 behavior | re-planning M2 as pending implementation |
| 2 | Product | Make M3 the final milestone | Auto-decided | Completeness | The feature is only truly done once typed genericity is proven beyond seam | another seam-only cleanup milestone |
| 3 | Architecture | Add a real adapter boundary | Auto-decided | Explicit over clever | Generic core plus typed adapters is the smallest honest way to remove seam hardcoding | sprinkling conditionals through the runner |
| 4 | Focus type | Choose `artifact` as the second type | Auto-decided | Pragmatic | It is grounded in real workflow / manifest tasks and stresses the adapter boundary without a downstream rewrite | `subsystem`, `policy_surface` |
| 5 | Contract | Keep one selected focus type per run in M3 | Auto-decided | Scope discipline | Supporting multiple types is different from supporting multiple allowed values over time | mixed seam+artifact arbitration |
| 6 | UX | Keep `focus_decision` as the only top-level focus artifact | Auto-decided | DRY | Users already have one inspectable focus artifact; a second public family adds churn without value | `focus_decision_v2`, parallel artifact family |
| 7 | Acceptance | Generalize the acceptance helper and require an artifact deliberate packet | Auto-decided | Rigor | Final feature proof must outlive M2 naming and cover the generic behaviors, not one happy path | leaving M2-named helper as permanent, artifact happy-path only |

## Review Summary

### Office-Hours Outcome

- M2 is sufficiently real to move on
- the final milestone should prove typed reuse, not add more seam-only polish
- `artifact` is the most honest second-type packet for this repo

### Engineering Verdict

- the feature bottleneck is no longer behavior invention
- the bottleneck is structural honesty and typed proof
- the adapter boundary plus generic acceptance tooling are required for a credible finish
