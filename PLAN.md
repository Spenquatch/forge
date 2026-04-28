<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260428-173839.md -->
# PLAN: M3 Typed Focus Gate Finalization

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Supersedes: the stale M2 implementation plan that previously lived at this path
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260428-173839.md`
Implementation baseline: M2 focus-gate v9 behavior is landed on this branch at `HEAD`

## Plan Summary

Do not spend this branch re-implementing M2.

The focus gate already exists end to end:

- `focus_gate_probe` and `focus_gate` exist in `anvil/harness/runner.py`
- split prompt builders exist in `anvil/harness/prompts.py`
- `clarification_policy = never_ask` survives parse -> contract -> runner -> report
- stale rerun-answer handling already exists and is candidate-aware
- the runner-owned top-level `focus_decision` artifact already exists in schema, semantic validation, and reporting
- targeted regression coverage is already green on the seam-only surface

M3 is the finish pass for this feature family.

The job is not "invent focus gating again." The job is:

1. remove the remaining seam-only assumptions from gate-core code
2. add one narrow second focus packet that proves the gate is genuinely typed
3. keep the public surface stable enough that existing seam behavior does not regress
4. leave a generic acceptance surface instead of an M2-branded one-off helper

## User Outcome and Success Criteria

This milestone still serves a user outcome, not just internal cleanup.

When a task is really about one governing file, for example a workflow file or manifest, the gate should be able to focus that run without first pretending the user already handed it a seam-shaped multi-file review unit.

M3 is successful only if all of the following are true:

- existing seam tasks behave exactly as they do today
- a narrow `focus_type = artifact` run can complete bounded and trust end to end
- deliberate ambiguity, `never_ask`, and stale rerun-answer behavior work for both supported focus types
- downstream analysis remains seam-shaped in M3, but the runner-owned bridge from selected focus to downstream seam expectations is explicit, persisted, and validated
- acceptance tooling no longer hardcodes M2-only file names or adjudicate-only assumptions

## Step 0: Scope Challenge

### Mode Selection

Use **SELECTIVE EXPANSION**.

Finish the feature that already exists. Do not widen into a general router, a new task kind, or a new downstream payload family.

### Premise Challenge

| Premise | Verdict | Why |
|---|---|---|
| M2 is landed baseline, not future work. | Accept | Code, tests, docs, and saved artifacts already exist at `HEAD`. |
| M3 still needs one second focus packet to make the typed claim honest. | Accept | `allowed_focus_types`, schemas, prompts, normalization, and semantic validation still hardcode `seam`. |
| The second packet on this branch remains `artifact`. | Accept with narrowing | Keep the branch direction, but define it narrowly as a governing-file focus packet, not a broad new product taxonomy. |
| M3 can keep the downstream analysis loop seam-shaped. | Accept | That is the smallest safe implementation, but the adapter bridge must be explicit and persisted. |
| M3 should support mixed seam+artifact arbitration in one run. | Reject | That is a separate front-door routing milestone and would expand scope materially. |
| M3 can keep the existing contract version and just widen enums silently. | Reject | This is a real contract change, not a comment-only cleanup. |
| M3 can treat deliberate stale-answer handling as unchanged. | Reject | The current rerun and stale-answer path is seam-authored and must move behind the typed adapter boundary. |

### Implementation Alternatives

| Option | Summary | Pros | Cons | Verdict |
|---|---|---|---|---|
| A. M2 closeout only | Rename helpers, clean docs, stop. | Small diff. | Leaves the "typed focus" claim half-true forever. | Reject |
| B. Internal seam adapter only | Isolate seam logic internally, but keep `seam` as the only supported type. | Lower risk. | Does not prove typed reuse and punts the second packet again. | Reject |
| C. Typed adapter core + narrow artifact packet | Extract typed gate-core seams, add one governing-file packet, keep downstream seam-shaped. | Honest finish, minimal public churn, clear proof packet. | Real contract and acceptance work, not just enum widening. | Choose |

### What Already Exists

| Sub-problem | Existing code | Reuse decision |
|---|---|---|
| task-level focus-gate parsing | `anvil/harness/types.py` | Reuse, but replace `_validate_m1_allowed_focus_types()` with a real typed validator. |
| resolved focus-gate contract | `anvil/harness/contracts.py` | Reuse, but bump contract version and widen `FocusGatePolicy`. |
| public focus schemas | `anvil/harness/schemas.py` | Reuse the existing shell. Extend `focus_type` and `adapter_plan`; do not add `focus_decision_v2`. |
| focus-decision semantic validation | `anvil/harness/semantic_validation.py` | Reuse the entrypoint, split generic focus checks from type-specific and downstream bridge checks. |
| gate orchestration and normalization | `HarnessRunner` helpers in `anvil/harness/runner.py` | Reuse the stage flow, but stop calling seam-only canonicalization directly from generic helpers. |
| gate prompts | `anvil/harness/prompts.py` | Reuse the split adjudicate/deliberate builders, but move type rules and downstream handoff wording behind the adapter boundary. |
| focus report rendering | `anvil/harness/report.py` | Reuse the `## Focus Decision` section and make it type-aware plus bridge-aware. |
| acceptance helper pattern | `scripts/run_m2_focus_gate_live_acceptance.py` and `examples/harness/live_acceptance/` | Reuse the pattern, not the M2-only assumptions or names. |

### Current Code Reality at `HEAD`

These are the real seam-only anchors that M3 must remove:

- `anvil/harness/types.py`
  - `_validate_m1_allowed_focus_types()` accepts only `["seam"]`
- `anvil/harness/contracts.py`
  - `FocusGatePolicy.allowed_focus_types` is typed as `list[Literal["seam"]]`
  - the resolved contract is still `analysis_review_v1_contract_v9`
- `anvil/harness/schemas.py`
  - `focus_gate_output_schema()` and `focus_probe_output_schema()` allow only `focus_type = seam`
  - `FOCUS_GATE_ADAPTER_PLAN_SCHEMA` carries only `primary_focus_id` and `secondary_focus_ids`
- `anvil/harness/semantic_validation.py`
  - `validate_focus_decision_payload()` requires `focus_type == "seam"`
  - canonical selected focus IDs are derived with `canonical_seam_id_for_paths(...)`
- `anvil/harness/runner.py`
  - `_normalize_focus_gate_candidate_payloads()` and `_normalize_focus_gate_decision_payload()` derive seam IDs directly
  - `_canonical_focus_gate_question_prompt()` hardcodes `"Which seam should this run prioritize?"`
  - stale rerun-answer handling and fallback synthesis are seam-only
  - proposer / reviser validation passes `selected_focus_id` and `selected_focus_paths` directly into `expected_primary_seam_*`
- `anvil/harness/prompts.py`
  - focus-gate output rules and probe rules say `focus_type` is always `seam`
  - downstream analysis prompt blocks still describe selected focus paths as seam identity
- `anvil/harness/report.py`
  - the focus-decision section renders only the current minimal `adapter_plan` bridge and assumes seam-centric wording
- docs and acceptance
  - `README.md`, `examples/README.md`, `docs/analysis_review_contract.md`, and `scripts/run_m2_focus_gate_live_acceptance.py` still describe an M2-only surface

### Scope Decision

Proceed with M3 as:

- a real typed gate-core extraction
- one narrow `artifact` proof packet
- one explicit contract bump
- one explicit runner-owned downstream seam bridge
- one generic acceptance surface

Do not widen this branch into mixed-type arbitration or a downstream non-seam review payload.

## Architecture Plan

### 1. Keep the Public Surface Stable, But Bump the Contract Version

Keep these public names:

- `focus_gate`
- `focus_gate_answer`
- top-level `focus_decision`

Do not add `focus_decision_v2`.

Do bump the resolved contract version from `analysis_review_v1_contract_v9` to `analysis_review_v1_contract_v10`.

Why:

- widening `allowed_focus_types`
- widening `focus_type`
- widening `adapter_plan`
- making deliberate rerun behavior typed instead of seam-only

This is a real contract change. Treating it as an in-place v9 edit would make old docs, old test fixtures, and old saved artifacts silently change meaning.

### 2. Introduce a Typed Focus Adapter Module

Add:

- `anvil/harness/focus_types.py`

This module owns typed focus logic that is currently scattered across `contracts.py`, `runner.py`, `semantic_validation.py`, and `prompts.py`.

Minimum interface:

```text
FocusTypeAdapter
  - focus_type_name() -> Literal["seam", "artifact"]
  - normalize_candidate_paths(...)
  - canonical_focus_id(candidate_paths) -> str
  - question_prompt() -> str
  - validate_selected_paths(...)
  - validate_candidate_paths(...)
  - build_downstream_primary_seam(selected_focus_paths) -> {seam_id, paths}
  - prompt_rules_for_probe() -> str
  - prompt_rules_for_decision() -> str
  - prompt_rules_for_analysis_handoff() -> str
  - stale_answer_fallback(...)
```

Concrete adapters:

- `SeamFocusAdapter`
- `ArtifactFocusAdapter`

### 3. Define M3 Artifact Narrowly

`focus_type = artifact` is a governing-file focus packet in M3.

Normative rules:

- `selected_focus_paths` must contain exactly one normalized workspace path
- each `candidates[*].candidate_paths` must contain exactly one normalized workspace path
- `checked_files` may contain corroborating files beyond the selected artifact path
- the artifact focus ID is runner-owned, not model-owned
- the downstream bridge remains seam-shaped for M3

Runner-owned artifact ID rule:

```text
canonical_artifact_focus_id(path) =
  "artifact-" + slugify(Path(path).stem) + "-" + sha1(normalized_path)[:12]
```

This must be deterministic across:

- candidate normalization
- selected-focus normalization
- rerun-answer option matching
- report rendering
- saved artifact inspection

### 4. Extend the Public Bridge, Do Not Hide It

The current `adapter_plan` is too small for typed focus.

Today:

```json
{
  "primary_focus_id": "string|null",
  "secondary_focus_ids": []
}
```

M3 must widen it to:

```json
{
  "primary_focus_id": "string|null",
  "secondary_focus_ids": [],
  "downstream_primary_seam_id": "string|null",
  "downstream_primary_seam_paths": [],
  "adaptation_basis": "selected_focus_paths|artifact_singleton"
}
```

Rules:

- for `decision_state = selected`
  - `primary_focus_id == selected_focus_id`
  - `secondary_focus_ids` is the shortlisted remainder
  - `downstream_primary_seam_id` is always non-null
  - `downstream_primary_seam_paths` is always non-empty
- for `decision_state != selected`
  - both downstream seam bridge fields must serialize as null / `[]`

This bridge is runner-owned state. The runner, semantic validation, reporting, and acceptance tooling must all use it.

### 5. Keep the Downstream Loop Seam-Shaped, Explicitly

M3 does not widen proposer / critic / reviser / auditor payloads away from `primary_seam`.

It does make the bridge explicit:

```text
focus_gate selected focus
        |
        v
typed adapter
        |
        v
adapter_plan.downstream_primary_seam_{id,paths}
        |
        v
proposer / reviser expected_primary_seam_{id,paths}
```

For `focus_type = seam`:

- `downstream_primary_seam_id = selected_focus_id`
- `downstream_primary_seam_paths = selected_focus_paths`

For `focus_type = artifact`:

- `selected_focus_id` remains the artifact ID
- `selected_focus_paths` remains the single selected artifact path
- `downstream_primary_seam_id = canonical_seam_id_for_paths([selected_artifact_path])`
- `downstream_primary_seam_paths = [selected_artifact_path]`
- later widening into sibling seams remains a downstream review responsibility, not a gate-core responsibility

This is intentionally narrow. M3 is not claiming artifact focus is a full downstream typed review family.

### 6. Move Deliberate Rerun and Stale-Answer Logic Behind the Adapter Boundary

M3 must update all of these runner behaviors, not just happy-path adjudicate selection:

- canonical clarification prompt generation
- candidate ID generation
- rerun answer matching
- stale-answer detection
- stale fallback synthesis for `never_ask`
- `clarification_requested` option generation

Required rule:

- the canonical question prompt must become generic, not seam-specific
- use: `"Which focus should this run prioritize?"`

The current seam-only prompt text must not survive in typed code paths.

### 7. Update Prompt Handoff, Not Just Gate Prompts

M3 prompt work includes:

- focus-gate adjudicate prompt
- focus-gate deliberate prompt
- focus-gate probe guidance
- downstream proposer / reviser focus-handoff blocks

The critical downstream prompt change:

- selected focus is the public focus choice
- downstream `primary_seam` is the runner-owned adapted seam
- models must not assume `selected_focus_paths` is always identical to downstream seam identity

### 8. Make Acceptance Scenario-Driven

Replace the current M2-only acceptance helper assumptions:

- hardcoded task and strategy pair
- adjudicate-only success expectation
- mandatory proposer artifacts for every scenario
- seam-path equality assumptions between selected focus and `primary_seam`

M3 acceptance must validate scenarios by:

- expected `gate_path`
- expected terminal `decision_state`
- expected `focus_type`
- whether proposer artifacts must exist
- whether the downstream seam bridge must exist

Blocked deliberate scenarios should validate only:

- `summary.json`
- `REPORT.md`
- `focus_gate_probe` artifacts
- `focus_gate` artifacts

They must not require proposer artifacts when the run blocks before proposer.

## Concrete Implementation Plan

### Slice 0: Contract, Naming, and Doc Hygiene

Goal:

- make the finish line honest before adding typed behavior

Files:

- `anvil/harness/contracts.py`
- `docs/analysis_review_contract.md`
- `README.md`
- `examples/README.md`
- `PLAN.md`

Work:

1. bump the contract version to v10
2. update docs so they describe M2 as landed baseline
3. document the typed bridge and the generic focus prompt
4. rename M2-specific helper references in docs to the generic acceptance surface

Done when:

- no doc claims the typed surface is still seam-only by contract
- no public doc points users at a missing `m2_focus_gate_local.yaml`

### Slice 1: Adapter Core and Typed Parsing

Goal:

- centralize focus-type behavior

Files:

- `[ADD] anvil/harness/focus_types.py`
- `anvil/harness/types.py`
- `anvil/harness/contracts.py`

Work:

1. replace `_validate_m1_allowed_focus_types()` with a typed whitelist validator
2. allow exactly `["seam"]` or `["artifact"]` in M3
3. reject mixed-type lists explicitly in M3 with a direct error
4. define canonical focus ID helpers for seam and artifact
5. resolve the active adapter once from the resolved contract

Done when:

- parse -> contract resolution accepts both supported single-type runs
- mixed-type input fails early with a deterministic validation error

### Slice 2: Schema, Validation, and Bridge Widening

Goal:

- make the public artifact and semantic checks typed and honest

Files:

- `anvil/harness/schemas.py`
- `anvil/harness/semantic_validation.py`

Work:

1. widen `focus_type` enums in both focus schemas to `seam | artifact`
2. widen `FOCUS_GATE_ADAPTER_PLAN_SCHEMA` with downstream seam bridge fields
3. split generic decision validation from adapter-specific path and ID invariants
4. validate artifact candidate single-path rules
5. validate runner-owned downstream seam bridge fields

Done when:

- seam and artifact focus decisions validate cleanly
- blocked decisions serialize null / empty bridge fields correctly
- selected decisions always carry a valid downstream seam bridge

### Slice 3: Runner Integration and Deliberate-Path Hardening

Goal:

- remove seam-only assumptions from normalization and rerun behavior

Files:

- `anvil/harness/runner.py`

Work:

1. route candidate normalization through the active adapter
2. route selected-focus normalization through the active adapter
3. populate the widened `adapter_plan`
4. pass `adapter_plan.downstream_primary_seam_{id,paths}` into proposer / reviser semantic validation
5. move canonical question prompt generation behind the adapter boundary
6. make stale rerun-answer detection and fallback synthesis typed

Done when:

- the runner no longer uses `selected_focus_id` and `selected_focus_paths` directly as downstream seam truth for artifact runs
- deliberate artifact `clarification_requested`, `never_ask`, and stale rerun-answer paths work

### Slice 4: Prompt, Report, and Acceptance Surface

Goal:

- make typed behavior visible and inspectable

Files:

- `anvil/harness/prompts.py`
- `anvil/harness/report.py`
- `scripts/run_focus_gate_acceptance.py`
- `examples/harness/live_acceptance/*`
- `README.md`
- `examples/README.md`
- `docs/analysis_review_contract.md`

Work:

1. replace seam-only gate prompt rules with adapter-provided type rules
2. update downstream analysis handoff text so selected focus and downstream seam are distinct concepts
3. render downstream seam bridge fields in `## Focus Decision`
4. replace the M2-only helper with a scenario-driven acceptance runner
5. rename live-acceptance templates to generic focus-gate names

Done when:

- `REPORT.md` reads correctly for seam and artifact runs
- acceptance tooling supports adjudicate-selected and deliberate-blocked scenarios

### Slice 5: Test Completion and Saved Proof Packets

Goal:

- prove the final feature, not just the happy path

Files:

- `tests/test_harness_analysis_contract.py`
- `tests/test_harness_semantic_validation.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`
- replacement acceptance-helper tests
- typed task / fixture manifests under `examples/harness/live_acceptance/`

Work:

1. add seam-regression tests for the new v10 contract
2. add artifact selected / blocked / stale deliberate coverage
3. add tests for widened `adapter_plan`
4. add tests for the generic clarification prompt
5. add generic acceptance helper scenario coverage

Done when:

- seam runs still pass
- artifact runs pass with typed bridge semantics
- blocked deliberate cases prove the correct artifact-only surface without false proposer expectations

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
- `scripts/run_focus_gate_acceptance.py`
- `README.md`
- `examples/README.md`
- `docs/analysis_review_contract.md`
- `examples/harness/live_acceptance/*`
- targeted harness tests

Keep the architecture boring:

- no new strategy kind
- no new task kind
- no mixed-type arbitration in one run
- no downstream non-seam payload family
- no second public focus artifact family

## Architecture Diagram

```text
TASK / STRATEGY INPUT
    |
    v
types.py + contracts.py
resolve focus_gate policy
    |
    v
focus_types.py
resolve active adapter
    |
    v
runner.py focus_gate_* stages
    |
    +--> selected_focus_{id,paths,summary}
    |
    +--> adapter_plan
           |
           +--> primary_focus_id
           +--> secondary_focus_ids
           +--> downstream_primary_seam_id
           +--> downstream_primary_seam_paths
           +--> adaptation_basis
    |
    v
semantic_validation.py
validate focus decision + bridge
    |
    v
proposer / reviser
consume downstream_primary_seam_{id,paths}
    |
    v
report.py + summary.json + acceptance helper
render both selected focus and downstream seam bridge
```

## Test Review

### Test Strategy

M3 needs full branch coverage on the typed gate surface, not just an enum bump and one happy-path artifact run.

The risky areas are:

- contract-version drift
- selected-focus vs downstream-seam divergence
- deliberate rerun-answer handling
- blocked deliberate artifact scenarios
- acceptance-helper assumptions that every scenario reaches proposer

### Code Path Coverage

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/types.py + contracts.py
    |
    ├── allowed_focus_types parsing
    │   ├── [EXISTS] seam
    │   ├── [ADD]    artifact
    │   └── [ADD]    reject mixed seam+artifact lists
    |
    └── contract versioning
        ├── [EXISTS] v9 seam contract
        └── [ADD]    v10 typed contract surface

[+] anvil/harness/schemas.py + semantic_validation.py
    |
    ├── focus_type enum
    │   ├── [EXISTS] seam
    │   └── [ADD]    artifact
    |
    ├── adapter_plan bridge
    │   ├── [EXISTS] primary_focus_id + secondary_focus_ids
    │   └── [ADD]    downstream_primary_seam_id + paths + adaptation_basis
    |
    ├── seam invariants
    │   └── [EXISTS] canonical seam ID and path-set checks
    |
    └── artifact invariants
        ├── [ADD] exactly one candidate path
        ├── [ADD] exactly one selected path
        ├── [ADD] runner-owned artifact ID
        └── [ADD] downstream seam bridge required when selected

[+] anvil/harness/runner.py
    |
    ├── candidate normalization
    │   ├── [EXISTS] seam canonicalization
    │   └── [ADD]    adapter-routed canonicalization
    |
    ├── selected decision normalization
    │   ├── [EXISTS] seam selected focus
    │   └── [ADD]    typed selected focus + widened adapter_plan
    |
    ├── deliberate clarification prompt
    │   ├── [EXISTS] seam-only prompt text
    │   └── [ADD]    generic focus prompt
    |
    ├── stale rerun-answer path
    │   ├── [EXISTS] seam-only stale fallback
    │   └── [ADD]    typed stale fallback
    |
    └── downstream validation handoff
        ├── [EXISTS] selected_focus_* -> expected_primary_seam_*
        └── [ADD]    adapter bridge -> expected_primary_seam_*

[+] anvil/harness/prompts.py + report.py
    |
    ├── gate rules
    │   ├── [EXISTS] seam-only focus rules
    │   └── [ADD]    adapter-provided typed rules
    |
    ├── downstream handoff wording
    │   └── [ADD]    selected focus distinct from adapted seam
    |
    └── report rendering
        ├── [EXISTS] focus decision section
        └── [ADD]    downstream seam bridge rendering

[+] acceptance tooling
    |
    ├── selected adjudicate seam baseline
    │   └── [EXISTS] reuse as regression proof
    |
    ├── selected adjudicate artifact
    │   ├── [ADD] bounded
    │   └── [ADD] trust
    |
    └── deliberate artifact cases
        ├── [ADD] clarification_requested
        ├── [ADD] never_ask -> no_viable_focus
        └── [ADD] stale rerun-answer -> normalized block
```

### Test Files and Assertions

Add or update tests for:

- `tests/test_harness_analysis_contract.py`
  - accepts `["artifact"]`
  - rejects `["seam", "artifact"]`
  - serializes v10 focus-gate contract correctly
- `tests/test_harness_semantic_validation.py`
  - validates widened `adapter_plan`
  - validates artifact single-path invariants
  - rejects missing downstream seam bridge for selected decisions
- `tests/test_harness_prompt_consistency.py`
  - uses `"Which focus should this run prioritize?"`
  - includes typed gate rules and typed downstream handoff wording
- `tests/test_harness_runner.py`
  - artifact selected normalization
  - artifact deliberate clarification
  - artifact deliberate `never_ask`
  - artifact stale rerun-answer fallback
  - downstream seam bridge feeds proposer / reviser expectations
- `tests/test_harness_reporting.py`
  - reports selected focus and downstream seam bridge distinctly
- generic acceptance-helper tests
  - selected scenarios require proposer artifacts
  - blocked deliberate scenarios do not require proposer artifacts

### Targeted Pytest Sweep

Run at minimum:

```bash
poetry run pytest -q \
  tests/test_harness_analysis_contract.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_semantic_validation.py \
  tests/test_harness_runner.py \
  tests/test_harness_reporting.py \
  tests/test_run_focus_gate_acceptance.py
```

### Acceptance Matrix

Seam regression packet:

1. adjudicate selected, bounded
2. adjudicate selected, trust
3. deliberate ambiguous -> `blocked_for_clarification`
4. deliberate ambiguous + `never_ask` -> `no_viable_focus`
5. deliberate stale `focus_gate_answer` -> stale warning + normalized block

Artifact packet:

1. adjudicate selected, bounded
2. adjudicate selected, trust
3. deliberate ambiguous -> `blocked_for_clarification`
4. deliberate ambiguous + `never_ask` -> `no_viable_focus`
5. deliberate stale rerun-answer -> stale warning + normalized block

For each selected packet inspect:

- `summary.json`
- `REPORT.md`
- `artifacts/*focus_gate_probe*/structured_output.*` when deliberate
- `artifacts/*focus_gate*/structured_output.*`
- proposer normalized payload
- adapted downstream seam bridge in `adapter_plan`

For each blocked deliberate packet inspect:

- `summary.json`
- `REPORT.md`
- `artifacts/*focus_gate_probe*/structured_output.*`
- `artifacts/*focus_gate*/structured_output.*`
- absence of proposer artifacts when the run blocks before proposer

## Failure Modes Registry

| Failure mode | Where it happens | Prevention | Test required |
|---|---|---|---|
| silent contract drift between v9 docs and typed runtime | `contracts.py`, docs, fixtures | explicit v10 bump and doc rewrite | yes |
| artifact selected focus passes, but downstream seam validation still reads `selected_focus_*` directly | `runner.py`, `semantic_validation.py` | widened `adapter_plan` bridge and runner handoff rewrite | yes |
| artifact deliberate rerun-answer emits seam-only stale fallback | `runner.py` | adapter-owned prompt and stale fallback helpers | yes |
| blocked deliberate acceptance still expects proposer artifacts | acceptance helper | scenario-driven acceptance expectations | yes |
| artifact candidates emit unstable IDs from model-authored text | `runner.py`, `focus_types.py` | runner-owned canonical artifact IDs derived from normalized path | yes |
| selected focus and downstream seam become conceptually indistinguishable in reports | `report.py` | render both surfaces distinctly | yes |

No M3 failure mode is allowed to remain without both a test and explicit error-handling behavior.

## Performance Review

Expected runtime impact is small.

- extra normalization and validation branches are O(candidate_count), and candidate count is already capped at 3
- artifact ID derivation is one normalized path plus one hash
- the main risk is not latency, it is semantic drift between selected focus, rerun options, and downstream seam expectations

No additional caching or concurrency work is required in M3.

## Worktree Parallelization Strategy

This plan has real parallelization opportunity after the typed foundation lands.

### Dependency Table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Foundation and contract bump | `anvil/harness/`, `docs/` | — |
| B. Runner integration | `anvil/harness/` | A |
| C. Prompt/report/docs/helper surface | `anvil/harness/`, `scripts/`, `examples/`, `docs/` | A |
| D. Tests and acceptance proof packets | `tests/`, `examples/`, `scripts/` | B, C |

### Parallel Lanes

Lane A: Foundation and contract bump in `anvil/harness/types.py`, `contracts.py`, `schemas.py`, `semantic_validation.py`, and new `focus_types.py`

Lane B: Runner integration in `anvil/harness/runner.py` after Lane A

Lane C: Prompt/report/docs/helper work in `anvil/harness/prompts.py`, `report.py`, `scripts/`, `examples/`, and docs after Lane A

Lane D: Tests and acceptance proof packets after Lanes B and C

### Execution Order

1. Launch Lane A first. It defines the contract, IDs, bridge fields, and validation rules that everything else depends on.
2. After Lane A merges, launch Lane B and Lane C in parallel worktrees.
3. After B and C merge, launch Lane D.

### Conflict Flags

- Lane B and Lane C both depend on the widened bridge shape defined in Lane A. Do not start them before Lane A stabilizes.
- Lane C and Lane D will both touch acceptance helper naming and manifest expectations. Keep those changes in one lane at a time or land helper changes before scenario tests.
- `docs/analysis_review_contract.md` is touched by Lane A and Lane C. Prefer Lane A to define the normative bridge fields, then let Lane C finish wording and examples.

## Risks and Mitigations

| Risk | Why it happens | Mitigation |
|---|---|---|
| M3 becomes "proof theater" instead of user-visible improvement | typed cleanup dominates the milestone story | keep the success criteria tied to real governing-file tasks and deliberate-path behavior |
| artifact becomes a fake seam alias | bridge fields stay implicit | persist both selected focus and downstream seam distinctly |
| the branch pays contract cost without admitting it | v9 is silently widened | bump to v10 and update docs / fixtures accordingly |
| mixed-type routing pressure keeps leaking in | plural field survives but mixed lists are rejected | document this explicitly as a deliberate deferral, not an accidental gap |

## NOT in Scope

- mixed seam+artifact arbitration inside one run
- a new task kind outside `analysis_review`
- a downstream non-seam output family
- pause / resume lifecycle for clarification
- more than two supported focus types
- user-facing UX redesign of rerun-answer options beyond the existing internal harness surface

## Definition of Done

M3 is done only when all of these are true:

1. the resolved focus-gate contract is versioned explicitly for the typed surface
2. gate-core code no longer hardcodes seam-only focus typing outside the seam adapter
3. `focus_type = artifact` works end to end
4. `selected_focus_*` and downstream seam bridge fields are both persisted and validated
5. deliberate artifact ambiguity, `never_ask`, and stale rerun-answer behavior are correct
6. reporting renders selected focus and downstream seam distinctly
7. acceptance tooling is genericized beyond M2 naming and supports blocked deliberate scenarios
8. seam regression and artifact proof packets both pass

## Completion Summary

- Step 0: Scope Challenge — scope accepted with explicit contract bump and explicit bridge widening
- Architecture Review: major issues resolved in plan by adding contract versioning, widened `adapter_plan`, and typed deliberate-path work
- Code Quality Review: seam-only logic is consolidated behind a new adapter module instead of being duplicated
- Test Review: full code-path coverage diagram included, no happy-path-only exit
- Performance Review: no major runtime risk, main risk is semantic drift
- NOT in scope: written
- What already exists: written
- Failure modes: explicit registry included, no silent critical gaps allowed
- Parallelization: 4 steps, 2 parallel lanes after foundation, 1 final test lane
- Lake Score: complete option chosen for contract versioning, typed stale-answer handling, bridge persistence, and blocked-scenario acceptance
