# PLAN: Typed Focus Gate for Analysis Review

Status: ready for implementation  
Branch: `feat/bounded-work-redesign`  
Supersedes: the seam-parity closure plan that was already landed on this branch  
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260426-194445.md`

## Plan Summary

This branch should not try to build the full planner platform from the design doc in one shot.

The implementable slice is **M1 only**:

- add a runner-owned front-door focus gate before proposer
- support `gate_path = adjudicate | deliberate`
- support `focus_type = seam` only
- persist a typed `focus_decision` artifact into `summary.json`
- render a compact focus-decision block in `REPORT.md`
- fail fast as `blocked_for_clarification` or `no_viable_focus` instead of silently entering the main loop on an ambiguous request

M2 and M3 stay in this plan as explicit follow-ons, not branch scope.

## Step 0: Scope Challenge

### Mode Selection

Use **SELECTIVE EXPANSION**.

The plan needs enough new surface to make the gate real, but it should stay inside the existing `analysis_review_*` runner and contract family. No new strategy kind. No new orchestration subsystem. No pause/resume lifecycle.

### Premise Challenge

| Premise | Verdict | Why |
|---|---|---|
| The next milestone must decide focus before the expensive review loop starts. | Accept | Today `HarnessRunner._run_analysis_review_v1()` enters proposer immediately, which means the harness can spend a full run on the wrong surface. |
| `seam` should be the first `focus_type`, but the shape should be typed from day one. | Accept | The repo is still seam-shaped downstream, but hardcoding the artifact shape to seams again would force another rewrite. |
| `deliberate` should block for clarification rather than silently auto-route. | Accept | Silent fallback is the exact trust failure this milestone is trying to remove. |
| M1 should include repo probing, multi-type adapters, and pause/resume. | Reject | That is an ocean. M1 only needs request-level adjudication, typed artifacts, and a clean blocked path. |

### What Already Exists

| Sub-problem | Existing code | Reuse decision |
|---|---|---|
| task and strategy loading | `anvil/harness/types.py` | Reuse. Extend `TaskSpec` and `StrategyConfig`; do not introduce a new spec family. |
| effective analysis-review contract | `anvil/harness/contracts.py` | Reuse. Add a typed `focus_gate` policy to the existing contract instead of branching contract types. |
| main bounded/trust review loop | `anvil/harness/runner.py` | Reuse. Insert the gate before proposer, then keep critic/reviser/auditor flow unchanged. |
| seam-shaped downstream payload | `anvil/harness/schemas.py`, `anvil/harness/semantic_validation.py` | Reuse. Keep `primary_seam` and recommendation seam bindings as the downstream contract. |
| report and artifact emission | `anvil/harness/report.py`, `anvil/harness/reporting.py` | Reuse. Add a focus-decision section; do not invent a second artifact writer. |
| repo-local discovery guidance | `anvil/harness/prompts.py`, `docs/analysis_review_contract.md` | Reuse. The gate should consume the same request context and `files_hint` rules. |
| bounded/trust examples | `examples/harness/tasks/recommend_automation_improvements.yaml`, strategy examples | Reuse. No new strategy kind is needed for M1. |

### Minimum Change That Achieves the Goal

The minimum complete fix is:

1. Extend task, strategy, and contract surfaces with a `focus_gate` policy and optional `focus_gate_answer`.
2. Add a dedicated focus-gate prompt/schema pair that can emit `selected`, `clarification_requested`, or `no_viable_focus`.
3. Run that gate before proposer in `HarnessRunner._run_analysis_review_v1()`.
4. Persist the runner-owned `focus_decision` artifact even when the run stops before proposer.
5. Seed proposer with the selected seam and enforce downstream seam agreement against the gate output.
6. Render the focus decision in `REPORT.md`.
7. Add unit and runner tests for the happy path, blocked path, warning path, and drift path.

Anything smaller is a shortcut:

- prompt-only seam hints are not enough
- report-only explanations are not enough
- allowing the loop to keep silently re-selecting the seam is not enough

### Complexity Check

Expected touched modules:

- `anvil/harness/types.py`
- `anvil/harness/contracts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/runner.py`
- `anvil/harness/report.py`
- `docs/analysis_review_contract.md`
- harness test files covering contract, prompts, runner, semantic validation, and reporting

That is more than 8 files, so it is a complexity smell.

The right response is **not** to cut the gate. The right response is to keep the architecture boring:

- no new strategy kind
- no new graph/subgraph
- no new distribution artifact
- at most one new contract dataclass
- no second focus type in this branch

### Search Check

- **[Layer 1]** Reuse the existing task/strategy parsing surface instead of inventing a gate-specific config file.
- **[Layer 1]** Reuse the current runner entrypoint and report writer instead of adding a second mini-runner for the gate.
- **[Layer 1]** Reuse seam-shaped downstream payloads and validation rather than widening the whole review loop in M1.
- **[Layer 3]** The key architectural move is not “pick seams better.” It is “own focus selection before proposer,” because today the seam contract is enforced only after cost has already been spent.

### TODOS Cross-Reference

`TODOS.md` has no blocker for this slice.

This plan should not bundle unrelated backlog work from `TODOS.md` into the branch. The only future work that should be recorded from this slice is:

- second focus-type proof for M3
- repo-probe enrichment for `deliberate` in M2
- possible task-authoring ergonomics around `focus_gate_answer`

### Completeness Check

Ship the complete M1, not the shortcut.

Complete M1 means:

- typed policy
- runner-owned artifact
- blocked clarification path
- report + summary surfacing
- downstream seam-agreement enforcement
- offline tests for selected, blocked, and no-viable outcomes

Shortcut M1 would be:

- new prompt prose but no runner-owned artifact
- a selected seam in proposer context but no persisted decision
- ambiguity warnings without a blocked outcome

Reject the shortcut.

### Distribution Check

No new CLI binary, package, or container image is introduced.

This ships through the existing repo workflow:

- Python source changes under `anvil/harness/`
- pytest coverage
- repo docs update in `docs/analysis_review_contract.md`

## Dream State

```text
CURRENT
task + strategy + files_hint
    │
    ▼
proposer chooses seam inside the review loop
    │
    ▼
critic / reviser / auditor may notice ambiguity only after cost is spent
    │
    ▼
summary.json and REPORT.md explain the seam after the fact

THIS PLAN (M1)
task + strategy + files_hint + optional focus_gate_answer
    │
    ▼
runner-owned focus gate
    ├── adjudicate  -> selected
    ├── deliberate  -> clarification_requested
    └── adjudicate  -> no_viable_focus
    │
    ▼
focus_decision artifact
    │
    ├── persisted into summary.json
    ├── rendered in REPORT.md
    └── adapted into downstream seam context
    │
    ▼
existing proposer -> critic -> reviser -> auditor loop

12-MONTH IDEAL
typed gate core
    │
    ├── seam
    ├── artifact
    ├── policy_surface
    └── subsystem
    │
    ▼
focus-specific adapters feeding still-boring downstream review flows
```

## NOT In Scope

- making the downstream analysis-review loop generic across all future `focus_type` values
- adding a second real `focus_type` in this branch
- repo-backed candidate probing in M1
- any pause, suspend, or resume lifecycle inside the runner
- changing recommendation admissibility, provenance, publication, or trust atomicity rules beyond what is needed to persist and display `focus_decision`
- replacing the imperative runner bridge with a new LangGraph-native implementation
- redesigning bounded/trust role lineups or review-loop stop policies

## Architecture Review

### Core Architecture Decision

`focus_gate` should be an **extension of the existing analysis-review contract**, not a new strategy kind.

That keeps the public surface boring:

- task still declares the job
- strategy still declares roles and review loops
- the contract still resolves the effective behavior
- the runner still owns execution

### Proposed Dependency Graph

```text
TaskSpec + StrategyConfig
    │
    ├── task.focus_gate (optional raw config)
    ├── task.focus_gate_answer (optional rerun answer)
    └── strategy.focus_gate (optional raw defaults)
            │
            ▼
build_analysis_review_contract()
    │
    ▼
AnalysisReviewContract.focus_gate
    │
    ▼
HarnessRunner._run_focus_gate()
    │
    ├── build_focus_gate_*_prompt()
    ├── focus_gate_output_schema()
    ├── validate_focus_decision_payload()
    └── persist focus_decision
            │
            ├── selected -> proposer seeded with chosen seam
            ├── clarification_requested -> blocked run, no main loop
            └── no_viable_focus -> blocked run, no main loop
                    │
                    ▼
summary.json + REPORT.md
```

### Exact Contract Shape

Provenance: **grounded in existing code + new normative decision**

- Grounded in existing code:
  the repo already resolves effective behavior through `TaskSpec`, `StrategyConfig`, and `build_analysis_review_contract()`.
- New normative decision:
  `focus_gate` becomes the exact new contract field name and lives on the existing analysis-review contract instead of a new strategy kind or spec family.

M1 should add one new contract field:

```yaml
focus_gate:
  enabled: true
  default_path: adjudicate
  allowed_focus_types: [seam]
  clarification_policy: block_for_clarification
```

Rules:

- runner default: `enabled = false`
- strategy may set `enabled` and `default_path`
- task may narrow `allowed_focus_types` and set `clarification_policy`
- the effective resolved surface lives in `AnalysisReviewContract.focus_gate`
- M1 only accepts `allowed_focus_types: [seam]`

### Normative M1 Input Shapes

Provenance: **new normative decision**

- Grounded in existing code:
  task and strategy YAMLs already flow through `TaskSpec.from_dict()` and `StrategyConfig.from_dict()`.
- New normative decision:
  these exact YAML field names, allowed keys, and validation rules do not exist yet and are being locked by this plan.

The raw config should live in the existing task and strategy YAMLs with these exact field names.

Task YAML:

```yaml
focus_gate:
  enabled: true
  allowed_focus_types: [seam]
  clarification_policy: block_for_clarification

focus_gate_answer:
  question_prompt: "Which seam should this run prioritize?"
  selected_option: "release-trigger-automation"
  freeform_answer: ""
```

Strategy YAML:

```yaml
focus_gate:
  enabled: true
  default_path: adjudicate
```

Parsing rules:

- `TaskSpec.focus_gate` is optional and may only override `enabled`, `allowed_focus_types`, and `clarification_policy`.
- `StrategyConfig.focus_gate` is optional and may only override `enabled` and `default_path`.
- `TaskSpec.focus_gate_answer` is optional and is only meaningful when `focus_gate.enabled = true`.
- M1 rejects unknown `focus_gate` keys in task or strategy specs.
- M1 rejects any `allowed_focus_types` value other than exactly `["seam"]`.
- `freeform_answer` may be empty, but `question_prompt` and `selected_option` must be non-empty when `focus_gate_answer` is present.

### Focus Decision Artifact

Provenance: **grounded in existing code + new normative decision**

- Grounded in existing code:
  the repo already persists runner-owned state into `summary.json` and renders runner-owned sections in `REPORT.md`.
- New normative decision:
  `focus_decision` becomes the exact top-level field name and this exact artifact shape is new.

Persist a top-level runner-owned `focus_decision` object in `summary.json`.

Do **not** bury it under `analysis_review_status`. It exists before the review loop and must survive runs that never reach proposer.

M1 artifact:

```json
{
  "gate_path": "adjudicate | deliberate",
  "focus_type": "seam",
  "decision_state": "selected | clarification_requested | no_viable_focus",
  "selected_focus_id": "string|null",
  "selected_focus_summary": "string|null",
  "confidence": 0.0,
  "confidence_band": "high | medium | low",
  "candidates": [],
  "question": {
    "prompt": "string",
    "options": ["string"]
  },
  "warnings": [],
  "adapter_plan": {
    "primary_focus_id": "string|null",
    "secondary_focus_ids": []
  }
}
```

M1 artifact rules:

- `gate_path` is always `adjudicate` or `deliberate`.
- `focus_type` is always `seam`.
- `decision_state` is always one of `selected`, `clarification_requested`, `no_viable_focus`.
- `selected_focus_id` and `selected_focus_summary` are required when `decision_state = selected` and must be `null` otherwise.
- `question.prompt` and `question.options` are required when `decision_state = clarification_requested`; otherwise `question` must serialize as `{ "prompt": "", "options": [] }`.
- `candidates` may be empty only when `decision_state = no_viable_focus`; for `selected` and `clarification_requested`, `candidates` must contain at least the selected or shortlisted seam set.
- `adapter_plan.primary_focus_id` must equal `selected_focus_id` for `selected` and must be `null` otherwise.

### Runner Flow

```text
_run_analysis_review_v1()
    │
    ├── build contract
    ├── if contract.focus_gate.enabled is false:
    │       continue with existing proposer path
    │
    └── if contract.focus_gate.enabled is true:
            │
            ├── run focus gate stage
            ├── persist focus_decision
            ├── if decision_state == selected:
            │       continue into proposer with selected seam context
            ├── if decision_state == clarification_requested:
            │       return blocked_for_clarification
            └── if decision_state == no_viable_focus:
                    return no_viable_focus
```

### Exact Verdict Taxonomy

Provenance: **new normative decision**

- Grounded in existing code:
  the runner already emits terminal `run_verdict`, `content_verdict`, `validator_verdict`, `final_summary`, and `failure_details`.
- New normative decision:
  the exact new verdict strings `blocked_for_clarification` and `no_viable_focus`, plus their summary payload rules, are new and are being fixed here.

M1 should add two new terminal review outcomes with these exact summary fields:

For `clarification_requested`:

- `run_verdict = "blocked_for_clarification"`
- `content_verdict = "blocked_for_clarification"`
- `validator_verdict = "not_run"`
- `final_summary = "Focus gate blocked the run pending clarification."`
- `failure_details = { "stage": "focus_gate", "decision_state": "clarification_requested", "question": ..., "candidates": ..., "warnings": ... }`

For `no_viable_focus`:

- `run_verdict = "no_viable_focus"`
- `content_verdict = "no_viable_focus"`
- `validator_verdict = "not_run"`
- `final_summary = "Focus gate could not identify a viable focus target."`
- `failure_details = { "stage": "focus_gate", "decision_state": "no_viable_focus", "candidates": ..., "warnings": ... }`

For `selected`:

- the run proceeds normally through proposer and later verdicts
- `focus_decision` must still be persisted in `run_details`, top-level `summary.json`, and `REPORT.md`

These blocked outcomes are terminal, not intermediate. In both cases:

- no proposer stage runs
- no validator round runs
- `analysis_review_status` may be absent
- `REPORT.md` is still emitted

### Gate Stage Recording

Provenance: **grounded in existing code + new normative decision**

- Grounded in existing code:
  gate execution will reuse the existing `agent_stages` / `ProviderRun` stage-record model.
- New normative decision:
  `role_name = "focus_gate"` and the exact metadata conventions for this stage are new.

The focus gate must appear in `agent_stages` as a normal stage record with these exact conventions:

- `role_name = "focus_gate"`
- `stage_index` is less than proposer's stage index
- `round_index = 0`
- `requested_access = "read"`
- `effective_access = "read"`
- `structured_output` is the validated `focus_decision`
- `metadata.focus_gate.gate_path`, `metadata.focus_gate.focus_type`, and `metadata.focus_gate.decision_state` are copied into the stage record for easy debugging

If a strategy defines `roles.focus_gate`, that role config is used. Otherwise `roles.proposer` is cloned for the gate stage and forced read-only.

### Proposer Handoff Contract

Provenance: **grounded in existing code + new normative decision**

- Grounded in existing code:
  the current harness hands context to providers through prompt builders and `StageRequest.prompt_text`, not through extra structured provider fields.
- New normative decision:
  M1 will seed proposer and reviser by prompt text only, using a fixed `Focus Gate Decision` block, rather than extending the provider protocol.

M1 should hand the selected focus into proposer by **prompt text only**, not by changing `StageRequest` or the provider protocol.

Implement it this way:

1. extend `build_analysis_proposer_prompt()` and `build_analysis_reviser_prompt()` to accept an optional `focus_decision`
2. inject a fixed `Focus Gate Decision` prompt block when `decision_state = selected`
3. that block must include:
   - `selected_focus_id`
   - `selected_focus_summary`
   - the shortlisted candidate IDs
   - a hard requirement that downstream `primary_seam.seam_id` must equal the selected focus ID unless the run is being deliberately rejected for invalid gate output

Do not add a new provider request field in M1. Keep the handoff explicit and inspectable in the prompt artifact.

### Rerun Answer Matching Contract

Provenance: **new normative decision**

- Grounded in existing code:
  reruns already happen as fresh harness invocations against task YAML input.
- New normative decision:
  these exact matching semantics for `focus_gate_answer` are new and are being fixed here to avoid fuzzy behavior in M1.

`focus_gate_answer` matching should be deterministic and narrow in M1.

Rules:

- `focus_gate_answer.question_prompt` must equal the previously emitted `focus_decision.question.prompt` after trimming leading and trailing whitespace
- `focus_gate_answer.selected_option` must match one of the prior `focus_decision.question.options` exactly after trimming
- `freeform_answer` is optional supporting text and is never used as the primary matcher
- when both `question_prompt` and `selected_option` match, the gate must not re-ask the question and should continue through the adjudication path using the answer context
- when either field does not match, the runner may re-ask once and then terminate again as `blocked_for_clarification`

This is intentionally boring. M1 does not need fuzzy matching, question IDs, or resume tokens.

### Seam Adapter Rule

Provenance: **grounded in existing code + new normative decision**

- Grounded in existing code:
  the downstream loop is seam-shaped today through `analysis_output_schema()`, semantic validation, and `_build_analysis_review_status()`.
- New normative decision:
  the gate-selected seam becomes an authoritative upstream constraint, and semantic validation becomes the single owner of drift enforcement.

M1 keeps the downstream loop seam-shaped.

That means:

- proposer and reviser still emit `primary_seam`
- `selected_focus_id` must become the canonical downstream primary seam identity
- candidate overflow stays in `secondary_seams_considered`
- recommendation seam binding stays exactly where it lives today

Enforcement rule:

- when the gate selected a seam, downstream `primary_seam.seam_id` must match `focus_decision.selected_focus_id`
- if it does not match, semantic validation should fail loudly and name the drift

Authoritative enforcement location:

- semantic validation is the source of truth
- `validate_stage_output()` for proposer and reviser payloads should receive `expected_primary_seam_id` from the runner context
- the validator should reject any proposer or reviser payload whose `primary_seam.seam_id` differs from that expected value
- the runner should not add a second independent drift checker after the loop except for tests and summary wording

That keeps one enforcement owner instead of splitting the rule across runner logic and semantic validation.

This matters because a gate that can be silently ignored is not a gate.

### Gate Role Decision

Provenance: **grounded in existing code + new normative decision**

- Grounded in existing code:
  the runner already supports role lookup and fallback behavior across existing role names.
- New normative decision:
  `focus_gate` becomes an optional strategy role name with proposer fallback and forced read-only access in M1.

Add an optional `focus_gate` role in strategy configs, but make it **fallback to `proposer` when absent**.

Why this is the right trade:

- existing strategies keep working
- the gate can use a smaller/cheaper model later without changing public shape
- M1 does not require an example-strategy migration just to run

### Error & Rescue Registry

| Failure | Likely cause | Rescue |
|---|---|---|
| `clarification_requested` in a non-interactive run | request ambiguity is real | stop cleanly, persist `question`, rerun with `focus_gate_answer` |
| `no_viable_focus` on a good task | poor candidate generation from request-only context | inspect `candidates` and `warnings`, tighten task context or defer to M2 probe work |
| selected seam drifts from final `primary_seam` | proposer/reviser ignored gate context | fail semantic validation; do not silently publish |
| gate output is structurally invalid | prompt/schema mismatch | fail the gate stage before proposer |
| `files_hint` is missing or messy | task author gave weak entry signals | warn in artifact, do not fail by itself |

## Code Quality Review

### Explicit-Over-Clever Decisions

1. Add one focused `focus_gate` policy to the existing contract. Do not create `analysis_review_focus_gate_v1`.
2. Add one dedicated focus-decision schema. Do not overload `analysis_output_schema()`.
3. Store `focus_decision` at summary top-level. Do not thread it through fake `analysis_review_status` fields.
4. Allow `focus_gate` role override, but default to proposer. Do not force every strategy fixture to gain a new role before the feature can run.
5. Keep M1 validation seam-specific. Do not build a registry/plug-in system for future focus types yet.

### Module-Level Plan

| Slice | Files | What changes |
|---|---|---|
| input + contract | `anvil/harness/types.py`, `anvil/harness/contracts.py` | parse raw `focus_gate` / `focus_gate_answer`, resolve effective `focus_gate` policy |
| gate schema + validation | `anvil/harness/schemas.py`, `anvil/harness/semantic_validation.py` | define gate output schema and lightweight semantic checks for state transitions |
| prompt surface | `anvil/harness/prompts.py` | add adjudicate and deliberate gate prompt builders and inject a fixed `Focus Gate Decision` block into proposer/reviser prompts |
| runner integration | `anvil/harness/runner.py` | run `focus_gate` before proposer, persist `focus_decision`, emit exact blocked verdicts, seed proposer by prompt text, enforce seam agreement through semantic validation context |
| reporting | `anvil/harness/report.py` | render `## Focus Decision` even when the review loop never starts |
| docs | `docs/analysis_review_contract.md` | document config precedence, terminal states, rerun answer contract, and report behavior |

### Milestone Boundaries

#### M1: Branch Scope

- typed `focus_gate` policy
- `focus_type = seam`
- `adjudicate` and `deliberate`
- `focus_decision` artifact
- blocked clarification path
- downstream seam-agreement enforcement

#### M2: Explicit Follow-On

- one quick repo probe round before asking a question
- richer candidate scoring and rationale
- better handling of malformed or stale `focus_gate_answer`

#### M3: Explicit Follow-On

- remove remaining seam assumptions from gate-core decision logic
- prove a second focus type

## Test Review

### Test Strategy

The implementation should add tests before or alongside each slice. This is not optional.

The plan needs both unit-style coverage and runner-style integration coverage, because the gate is mostly orchestration logic and failure-state plumbing.

### Code Path Coverage

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/types.py
    │
    ├── TaskSpec parses focus_gate + focus_gate_answer
    │   ├── [ADD] defaults when fields absent
    │   ├── [ADD] accepts valid focus_gate_answer shape
    │   └── [ADD] rejects invalid focus_gate config
    │
    └── StrategyConfig parses optional focus_gate defaults
        └── [ADD] strategy/task precedence coverage

[+] anvil/harness/contracts.py
    │
    ├── build_analysis_review_contract() resolves effective focus_gate policy
    │   ├── [ADD] disabled by default
    │   ├── [ADD] strategy default_path respected
    │   └── [ADD] task narrowing allowed_focus_types / clarification_policy
    │
    └── contract serialization includes focus_gate
        └── [ADD] bounded + trust serialization coverage

[+] anvil/harness/runner.py
    │
    ├── gate disabled -> legacy proposer path
    │   └── [ADD] regression that legacy runs still work unchanged
    │
    ├── gate enabled + selected
    │   ├── [ADD] focus gate stage runs before proposer
    │   ├── [ADD] summary.json persists focus_decision
    │   ├── [ADD] proposer prompt contains the fixed Focus Gate Decision block
    │   └── [ADD] reviser prompt preserves the same selected seam requirement
    │
    ├── gate enabled + clarification_requested
    │   ├── [ADD] run exits before proposer
    │   ├── [ADD] run_verdict/content_verdict are exactly blocked_for_clarification
    │   └── [ADD] question block is preserved in summary/report
    │
    ├── gate enabled + no_viable_focus
    │   ├── [ADD] run exits before proposer
    │   ├── [ADD] run_verdict/content_verdict are exactly no_viable_focus
    │   └── [ADD] candidate rationale is preserved
    │
    ├── focus_gate_answer rerun path
    │   ├── [ADD] trimmed question_prompt must match prior prompt exactly
    │   └── [ADD] selected_option must match one prior option exactly
    │
    └── selected seam drift
        └── [ADD] semantic validation failure when proposer or reviser primary_seam differs

[+] anvil/harness/report.py
    │
    ├── selected focus block
    │   └── [ADD] report renders compact explanation block
    │
    ├── clarification focus block
    │   └── [ADD] report renders question + options for blocked runs
    │
    └── no-viable focus block
        └── [ADD] report renders warnings and candidate summary
```

### User Flow Coverage

```text
USER FLOW COVERAGE
===========================
[+] Operator runs a clear seam-focused task
    ├── [ADD] Gate selects a seam and the run enters proposer
    └── [ADD] REPORT.md shows why that seam won

[+] Operator runs an ambiguous task
    ├── [ADD] Gate asks one clarification question and stops
    └── [ADD] No silent auto-route into the expensive review loop

[+] Operator reruns with focus_gate_answer
    ├── [ADD] Gate uses the answer and selects a seam
    └── [ADD] The main loop starts only after a selected state

[+] Operator gives bad files_hint
    ├── [ADD] Warning emitted
    └── [ADD] Run does not fail on files_hint alone

[+] Operator compares bounded and trust runs on the same task
    ├── [ADD] focus_decision is visible in both summaries
    └── [ADD] bounded/trust still differ only downstream of focus selection
```

### Required Test Files

- `tests/test_harness_analysis_contract.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`

### Manual Acceptance

Run at minimum:

```bash
poetry run pytest -q tests/test_harness_analysis_contract.py tests/test_harness_prompt_consistency.py tests/test_harness_semantic_validation.py tests/test_harness_runner.py tests/test_harness_reporting.py
```

Then run one live clear-task case and one live ambiguous-task case with `focus_gate.enabled: true`:

1. clear case: expect `decision_state = selected` and proposer stage present
2. ambiguous case: expect `decision_state = clarification_requested` and no proposer stage

## Failure Modes Registry

| Codepath | Production failure | Test required | Error handling required | User-visible outcome |
|---|---|---|---|---|
| task/strategy parsing | invalid `focus_gate` config is accepted and mis-executed | yes | yes | clear config error |
| gate selected path | gate returns malformed artifact | yes | yes | run fails before proposer |
| clarification path | runner still enters proposer after asking a question | yes | yes | blocked, not silent continuation |
| no-viable path | runner emits vague failure with no candidate context | yes | yes | actionable blocked explanation |
| seam adapter | proposer/reviser changes `primary_seam` after gate selection | yes | yes | loud semantic validation failure |
| report rendering | blocked run has no `Focus Decision` section | yes | yes | operator can see why the run stopped |

Critical gap if omitted:

- If selected-seam drift is not tested and not enforced, the branch will reintroduce the same trust problem in a shinier place.

## Performance Review

### Expected Cost

The gate adds one extra provider round for enabled tasks.

That is acceptable because:

- the round is single-shot in M1
- there is no repo probe in M1
- the gate is cheaper than spending a whole proposer/critic/auditor loop on the wrong seam

### Performance Constraints

1. The gate must run at most once per request in M1.
2. `deliberate` may ask at most one clarification block.
3. Candidate lists should cap at three items.
4. No additional validator round should be introduced before proposer.

### Performance Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| clear tasks become slower | every enabled run pays one more LLM call | default `focus_gate` role to a cheap read-only model or proposer fallback |
| blocked runs look like failures | operators may think the harness broke | make `REPORT.md` and `summary.json` explicit about blocked-for-clarification |
| large candidate payloads bloat artifacts | noisy reports and harder debugging | hard-cap candidate list size and warnings count in M1 |

## Implementation Plan

### Slice 1: Input and Contract Surface

Files:

- `anvil/harness/types.py`
- `anvil/harness/contracts.py`
- `tests/test_harness_analysis_contract.py`

Changes:

1. Add optional raw `focus_gate` config to `TaskSpec` and `StrategyConfig`.
2. Add optional `focus_gate_answer` to `TaskSpec`.
3. Add one `FocusGatePolicy` dataclass to `contracts.py`.
4. Resolve effective `focus_gate` policy inside `build_analysis_review_contract()`.
5. Reject unknown `focus_gate` keys and reject any non-`seam` allowed focus type in M1.

Acceptance:

- contracts serialize deterministic `focus_gate` policy
- bounded and trust both carry the same focus-gate shape
- absent config keeps legacy behavior

### Slice 2: Gate Schema, Prompt, and Validation

Files:

- `anvil/harness/schemas.py`
- `anvil/harness/prompts.py`
- `anvil/harness/semantic_validation.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`

Changes:

1. Add a focused gate output schema.
2. Add adjudicate and deliberate gate prompt builders.
3. Add semantic validation for:
   - allowed `decision_state`
   - `selected` requires `selected_focus_id`
   - `clarification_requested` requires non-empty `question`
   - `no_viable_focus` requires candidate/warning context
   - proposer/reviser `primary_seam.seam_id` must equal `expected_primary_seam_id` when provided by the runner
4. Add prompt-consistency tests so bounded and trust share the gate vocabulary.

Acceptance:

- prompt text states that non-interactive ambiguity blocks instead of auto-routing
- semantic validation rejects malformed gate artifacts

### Slice 3: Runner Integration and Seam Adapter

Files:

- `anvil/harness/runner.py`
- `tests/test_harness_runner.py`

Changes:

1. Insert `_run_focus_gate()` before proposer in `_run_analysis_review_v1()`.
2. Persist `focus_decision` into summary details even when the loop never starts.
3. Short-circuit the run on `clarification_requested` and `no_viable_focus` using the exact blocked verdict taxonomy above.
4. Record the gate as `role_name = "focus_gate"` in `agent_stages`.
5. Seed proposer and reviser by injecting the fixed Focus Gate Decision prompt block.
6. Enforce that downstream `primary_seam.seam_id` matches gate selection through semantic validation context.
7. Keep bounded/trust divergence strictly downstream of focus selection.

Acceptance:

- gate-disabled runs are unchanged
- gate-selected runs enter proposer with seeded context
- blocked runs have no proposer stage
- drift path fails loudly

### Slice 4: Report and Summary Surfacing

Files:

- `anvil/harness/report.py`
- `tests/test_harness_reporting.py`

Changes:

1. Render a dedicated `## Focus Decision` section.
2. Render selected rationale, clarification prompt/options, or no-viable warnings depending on state.
3. Ensure the section appears even when `analysis_review_status` is absent.

Acceptance:

- blocked runs still produce readable `REPORT.md`
- report wording stays runner-owned

### Slice 5: Docs

Files:

- `docs/analysis_review_contract.md`

Changes:

1. Document `focus_gate` precedence.
2. Document terminal states.
3. Document `focus_gate_answer` rerun contract.
4. Document that `focus_decision` is top-level runner-owned state, not model-authored review status.

Acceptance:

- docs explain M1 behavior without implying M2 repo probing already exists

## Worktree Parallelization Strategy

### Dependency Table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Input + contract surface | `anvil/harness/types.py`, `anvil/harness/contracts.py` | — |
| B. Gate schema + prompt + validation | `anvil/harness/schemas.py`, `anvil/harness/prompts.py`, `anvil/harness/semantic_validation.py` | A |
| C. Runner integration | `anvil/harness/runner.py` | A, B |
| D. Report surfacing | `anvil/harness/report.py` | A, artifact shape from B |
| E. Docs | `docs/analysis_review_contract.md` | A, B, D |
| F. Tests | `tests/test_harness_*` | A, B, C, D |

### Parallel Lanes

- Lane A: `A -> B -> C`  
  Sequential because the runner needs stable contract names and gate schema shape.

- Lane B: `D -> E`  
  Can run in parallel with late `B` or early `C` once the artifact JSON shape is frozen.

- Lane C: `F`  
  Sequential after A+B+C+D. Tests span all touched modules and will churn badly if started too early.

### Execution Order

1. Launch Lane A and agree the `focus_gate` policy plus `focus_decision` artifact shape.
2. Once that shape is frozen, start Lane B in parallel while Lane A finishes runner integration.
3. Merge A and B.
4. Run Lane C.

### Conflict Flags

- `runner.py` depends on exact schema and prompt helper names from Lane A.
- `report.py` depends on exact persisted field names for `focus_decision`.
- test worktrees will conflict with both lanes if they start before artifact names are stable.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Scope | Ship M1 only in this branch | Auto-decided | Completeness + Pragmatic | M1 is the full shippable lake; M2/M3 belong in follow-on packets | full planner platform now |
| 2 | Architecture | Keep one analysis-review contract family | Auto-decided | Explicit over clever | New strategy kinds would duplicate runner and docs surface for no gain | gate-specific strategy kind |
| 3 | Architecture | Store `focus_decision` at summary top-level | Auto-decided | Explicit over clever | Blocked runs may never have `analysis_review_status` | burying it under review status |
| 4 | Code quality | Add optional `focus_gate` role with proposer fallback | Auto-decided | DRY + Minimal diff | Existing strategies keep working while allowing future cheaper gate roles | mandatory strategy migrations |
| 5 | Runner | Block on clarification instead of silent auto-route | Auto-decided | Completeness | Silent routing defeats the entire trust objective | warn-and-continue behavior |
| 6 | Validation | Enforce selected seam agreement downstream | Auto-decided | Rigor | A gate that can be ignored is cosmetic | advisory-only seam mismatch |

## Completion Summary

- Step 0: Scope Challenge — scope accepted as selective expansion, **M1 only**
- Architecture Review: insertion point and artifact shape defined
- Code Quality Review: boring-extension path chosen, no new strategy kind
- Test Review: coverage diagram produced, full test list specified
- Performance Review: extra gate call accepted with explicit caps
- NOT in scope: written
- What already exists: written
- Failure modes: critical drift gap identified
- Parallelization: 3 lanes, 1 real parallel window, 2 sequential merges
- Lake Score: `6/6` key decisions chose the complete M1 over the shortcut
