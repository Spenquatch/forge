# PLAN: M2 Seam Gate Hardening for Analysis Review

Status: ready for implementation
Branch: `feat/bounded-work-redesign`
Supersedes: the M1 focus-gate implementation plan that previously lived at this path
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260426-194445.md`
Implementation baseline: M1 focus-gate surface is already landed on this branch at `HEAD`

## Plan Summary

Do not spend this branch re-implementing M1.

The runner-owned focus gate already exists in code:

- `TaskSpec.focus_gate` and `TaskSpec.focus_gate_answer` parse in `anvil/harness/types.py`
- `AnalysisReviewContract.focus_gate` resolves in `anvil/harness/contracts.py`
- `HarnessRunner._run_focus_gate()` executes before proposer in `anvil/harness/runner.py`
- `focus_decision` persists into `summary.json` and renders in `REPORT.md`
- the harness already blocks as `blocked_for_clarification` and `no_viable_focus`
- semantic validation already enforces selected-seam drift against downstream `primary_seam`

M2 is the residual hardening pass that makes the seam gate production-grade without widening to a second focus type.

Branch scope for M2:

- keep `focus_type = seam`
- keep `focus_decision` as the top-level runner-owned artifact
- keep `selected`, `clarification_requested`, and `no_viable_focus` as the only terminal gate states
- add one repo-backed probe round on the `deliberate` path before asking the operator
- enrich candidate records with score, rationale, and evidence refs
- formalize selection thresholds instead of relying on vibes
- widen `clarification_policy` to support `never_ask`
- harden stale `focus_gate_answer` handling against repo and candidate drift
- render the richer rationale in `REPORT.md`

M3 remains out of scope. No second focus type in this branch.

## Step 0: Scope Challenge

### Mode Selection

Use **SELECTIVE EXPANSION**.

The right move is to harden the existing gate, not to redesign the harness around it. Stay inside the current `analysis_review_*` runner, the current contract family, and the current report pipeline. No new strategy kind. No generic planning subsystem. No pause/resume lifecycle.

### Premise Challenge

| Premise | Verdict | Why |
|---|---|---|
| M1 must be treated as a shipped baseline, not as planned work. | Accept | The contract field, runner flow, verdict taxonomy, reporting, and tests already exist in code. Re-planning them would create fake progress. |
| M2 should still support `focus_type = seam` only. | Accept | The downstream analysis-review loop is still seam-shaped through `analysis_output_schema()`, semantic validation, and recommendation seam binding. |
| The missing M2 value is a real deliberate probe, not more prose in the current prompt. | Accept | Today `deliberate` is still request-led. The gate can ask a question, but it cannot cheaply inspect repo-local seams first and explain the shortlist with grounded evidence. |
| M2 should introduce a second public gate artifact or a new provider protocol. | Reject | That is overbuilt. The public artifact should stay `focus_decision`; the probe can remain a runner-owned internal stage. |
| M2 should expose user-tunable numeric thresholds in YAML. | Reject | That is premature. M2 needs fixed, documented thresholds. If they need to move later, change code and docs together. |
| M2 should add a second focus type while the seam path is still immature. | Reject | That is how we get a “typed” abstraction that only works in demos. Make seam good first. |

### What Already Exists

| Sub-problem | Existing code | Reuse decision |
|---|---|---|
| task-level gate config and rerun answer parsing | `anvil/harness/types.py` | Reuse. Widen the existing parsing surface rather than adding a second config family. |
| effective gate contract resolution | `anvil/harness/contracts.py` | Reuse. Extend `FocusGatePolicy`; do not create a new contract type. |
| one-shot gate execution before proposer | `HarnessRunner._run_focus_gate()` in `anvil/harness/runner.py` | Reuse. Insert the probe into the current gate flow instead of adding a second mini-runner. |
| gate prompt builder | `build_focus_gate_prompt()` in `anvil/harness/prompts.py` | Reuse for the final decision call. Add a dedicated probe prompt builder rather than overloading one blob of prose. |
| top-level gate artifact | `focus_gate_output_schema()` in `anvil/harness/schemas.py` and `validate_focus_decision_payload()` in `anvil/harness/semantic_validation.py` | Reuse. Widen the existing shape instead of introducing `focus_decision_v2` under a new key. |
| report and summary persistence | `anvil/harness/report.py`, `anvil/harness/reporting.py` | Reuse. Extend the existing `## Focus Decision` section. |
| stage recording and read-only role enforcement | `HarnessRunner._effective_role_config()` and recorded `agent_stages` | Reuse. Record the probe as another read-only gate-adjacent stage. |
| selected-seam drift enforcement | `validate_analysis_review_payload()` in `anvil/harness/semantic_validation.py` | Reuse. Keep semantic validation as the single enforcement owner. |
| offline regression coverage | `tests/test_harness_analysis_contract.py`, `tests/test_harness_prompt_consistency.py`, `tests/test_harness_semantic_validation.py`, `tests/test_harness_runner.py`, `tests/test_harness_reporting.py` | Reuse. Add M2 coverage to the same files instead of spawning a second test suite. |

### Minimum Change That Achieves the Goal

The minimum complete M2 is:

1. Keep the current public `focus_gate` config surface, but widen `clarification_policy` from only `block_for_clarification` to `block_for_clarification | never_ask`.
2. Keep the current public `focus_decision` shell, but widen it with probe-backed fields and richer candidate objects.
3. Add one internal repo-backed `focus_gate_probe` stage that runs only on the `deliberate` path.
4. Feed the probe artifact into the final `focus_gate` decision call.
5. Lock exact score and lead thresholds for `selected` vs ambiguity.
6. Treat stale rerun answers as first-class logic, not string-matching accidents.
7. Render the richer decision basis in `REPORT.md`.
8. Add full offline coverage for probe success, ambiguity, stale answers, `never_ask`, and report output.

Anything smaller is a shortcut:

- telling the current prompt to “look harder” is not enough
- adding more candidate prose without score and evidence is not enough
- using request-only `deliberate` again and calling it M2 is not enough
- widening the contract without report/test coverage is not enough

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
- harness test files covering contract, prompts, semantic validation, runner, and reporting

That is still more than 8 files, so the smell is real.

The right response is to keep the architecture boring:

- no new strategy kind
- no provider protocol change
- no new top-level summary artifact besides `focus_decision`
- no user-tunable threshold registry
- no second focus type
- one internal probe round only

### Search Check

- **[Layer 1]** Reuse the existing `focus_gate` role and read-only stage machinery instead of inventing a bespoke probe agent system.
- **[Layer 1]** Reuse the current top-level `focus_decision` artifact and widen it in place instead of adding `focus_decision_v2` or `probe_summary`.
- **[Layer 1]** Reuse semantic validation as the single owner of downstream seam drift instead of adding an extra runner-only checker.
- **[Layer 3]** The real M2 improvement is not “ask a better question.” It is “ground ambiguity in one cheap repo-backed shortlist before involving the operator.”

### TODOS Cross-Reference

`TODOS.md` does not block this slice.

This branch should not absorb unrelated backlog items. The only future work that should survive into follow-on packets is:

- second focus-type proof in M3
- removing remaining seam assumptions from gate-core logic in M3
- revisiting whether task authors ever need user-tunable gate thresholds

### Completeness Check

Ship the complete M2 seam hardening pass, not the cosmetic version.

Complete M2 means:

- repo-backed deliberate probe
- explicit thresholds
- richer candidate payloads
- `never_ask` support
- stale-answer handling tied to current candidate reality
- report surfacing for probe-backed rationale
- offline tests for all of the above

Shortcut M2 would be:

- prompt wording only
- still-thin candidate objects
- string-match rerun answers with no drift awareness
- keeping `never_ask` undocumented and unsupported

Reject the shortcut.

### Distribution Check

No new CLI binary, package, or container image is introduced.

This ships through the existing repo workflow:

- Python source changes under `anvil/harness/`
- pytest coverage
- docs update in `docs/analysis_review_contract.md`

## Dream State

```text
CURRENT (HEAD / M1 LANDED)
task + strategy + files_hint + optional focus_gate_answer
    │
    ▼
one-shot focus_gate
    ├── adjudicate -> selected
    └── deliberate -> clarification_requested or selected from request-only context
    │
    ▼
focus_decision (thin candidates, no probe evidence)
    │
    ▼
existing proposer -> critic -> reviser -> auditor loop

THIS PLAN (M2)
task + strategy + files_hint + optional focus_gate_answer
    │
    ├── adjudicate
    │     └── request-only selection with explicit thresholds
    │
    └── deliberate
          ├── focus_gate_probe (one cheap repo-backed shortlist round)
          └── focus_gate (selected | clarification_requested | no_viable_focus)
    │
    ▼
focus_decision
    ├── decision_basis
    ├── files_hint_disposition
    ├── checked_files
    ├── scored candidates with rationale + evidence refs
    └── adapter_plan
    │
    ▼
existing seam-shaped proposer -> critic -> reviser -> auditor loop

12-MONTH IDEAL
typed gate core
    │
    ├── seam adapter (production-grade)
    ├── second focus type packet
    └── zero remaining seam assumptions in gate-core logic
```

## NOT In Scope

- adding a second real `focus_type` in this branch
- making the downstream review loop generic across future focus types
- changing recommendation admissibility, provenance, publication, or trust atomicity rules
- replacing prompt-text handoff with a new provider request field
- adding a pause, suspend, or resume lifecycle
- adding more than one repo probe round
- adding vector search, indexing, embeddings, or a candidate cache
- exposing threshold knobs in task or strategy YAML
- redesigning bounded/trust role lineups or review-loop stop policies

## Architecture Review

### Core Architecture Decision

Keep one public gate contract and one public gate artifact.

That means:

- public config remains `focus_gate`
- public rerun input remains `focus_gate_answer`
- public runner-owned output remains top-level `focus_decision`
- M2 adds an internal `focus_gate_probe` stage, not a second public artifact family

This is the boring path. It keeps the public surface stable while still making the deliberate path materially smarter.

### Proposed Dependency Graph

```text
TaskSpec + StrategyConfig
    │
    ├── task.focus_gate
    ├── task.focus_gate_answer
    └── strategy.focus_gate
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
    ├── if default_path == adjudicate:
    │       build_focus_gate_prompt()
    │       validate_focus_decision_payload()
    │
    └── if default_path == deliberate:
            build_focus_probe_prompt()
            validate_focus_probe_payload()
            │
            ▼
            build_focus_gate_prompt(probe artifact + optional focus_gate_answer)
            validate_focus_decision_payload()
            │
            ├── selected -> proposer seeded with selected seam
            ├── clarification_requested -> blocked run
            └── no_viable_focus -> blocked run
                    │
                    ▼
summary.json + REPORT.md + stage artifacts
```

### Exact Public Contract Shape

M2 should keep the existing field names and widen only what needs to become real.

Public config:

```yaml
focus_gate:
  enabled: true
  default_path: adjudicate   # adjudicate | deliberate
  allowed_focus_types: [seam]
  clarification_policy: block_for_clarification   # block_for_clarification | never_ask
```

Rules:

- runner default: `enabled = false`
- runner default: `default_path = adjudicate`
- runner default: `allowed_focus_types = [seam]`
- runner default: `clarification_policy = block_for_clarification`
- strategy may set `enabled` and `default_path`
- task may set `enabled`, `allowed_focus_types`, and `clarification_policy`
- the effective resolved surface still lives at `AnalysisReviewContract.focus_gate`
- M2 still rejects any `allowed_focus_types` value other than exactly `["seam"]`

`clarification_policy` semantics in M2:

- `block_for_clarification`: when ambiguity remains after the probe, emit `clarification_requested` and stop
- `never_ask`: when ambiguity remains after the probe, emit `no_viable_focus` with candidate rationale and warnings, never a question block

This is the smallest public widening that makes the contract honest.

### Normative M2 Input Shapes

Task YAML:

```yaml
focus_gate:
  enabled: true
  allowed_focus_types: [seam]
  clarification_policy: never_ask

focus_gate_answer:
  question_prompt: "Which seam should this run prioritize?"
  selected_option: "release-trigger-automation"
  freeform_answer: "Prefer the workflow trigger path first."
```

Strategy YAML:

```yaml
focus_gate:
  enabled: true
  default_path: deliberate
```

Parsing rules:

- `TaskSpec.focus_gate` remains optional and may override only `enabled`, `allowed_focus_types`, and `clarification_policy`
- `StrategyConfig.focus_gate` remains optional and may override only `enabled` and `default_path`
- `TaskSpec.focus_gate_answer` remains optional
- M2 rejects unknown `focus_gate` keys in task or strategy specs
- M2 accepts `clarification_policy` values `block_for_clarification` and `never_ask`
- `freeform_answer` may be empty, but `question_prompt` and `selected_option` must still be non-empty when `focus_gate_answer` is present

### Internal Probe Artifact

M2 adds one internal runner-owned probe payload. It is not a new public summary artifact.

Persist it in the `focus_gate_probe` stage envelope and feed it into the final `focus_gate` decision call.

Probe artifact:

```json
{
  "focus_type": "seam",
  "files_hint_disposition": "helped | hurt | ignored | absent",
  "checked_files": ["string"],
  "candidates": [
    {
      "focus_id": "string",
      "focus_summary": "string",
      "why_candidate": "string",
      "evidence_refs": ["string"],
      "score": 0.0
    }
  ],
  "warnings": ["string"]
}
```

Probe rules:

- `focus_type` is always `seam`
- `checked_files` must contain the concrete repo files the probe inspected
- each `evidence_refs` entry must be a path-only ref and must appear in `checked_files`
- candidate count caps at 3
- `checked_files` caps at 6
- each candidate `score` is a float in `[0.0, 1.0]`
- `warnings` may explain bad or misleading `files_hint` input, but must not replace `checked_files`

The probe exists to make ambiguity concrete. If it cannot point to files, it did not do the job.

### Focus Decision Artifact

Keep `focus_decision` as the top-level runner-owned object in `summary.json`.

Do not bury it under `analysis_review_status`. It still exists before the main review loop and must survive blocked runs.

M2 `focus_decision`:

```json
{
  "gate_path": "adjudicate | deliberate",
  "focus_type": "seam",
  "decision_state": "selected | clarification_requested | no_viable_focus",
  "decision_basis": "request_only | repo_probe | rerun_answer",
  "selected_focus_id": "string|null",
  "selected_focus_summary": "string|null",
  "confidence": 0.0,
  "confidence_band": "high | medium | low",
  "files_hint_disposition": "helped | hurt | ignored | absent",
  "checked_files": ["string"],
  "candidates": [
    {
      "focus_id": "string",
      "focus_summary": "string",
      "why_candidate": "string",
      "evidence_refs": ["string"],
      "score": 0.0
    }
  ],
  "question": {
    "prompt": "string",
    "options": ["string"]
  },
  "warnings": ["string"],
  "adapter_plan": {
    "primary_focus_id": "string|null",
    "secondary_focus_ids": ["string"]
  }
}
```

Artifact rules:

- M2 preserves all existing M1 top-level fields and widens the shape in place
- `decision_basis` is required and is exactly one of:
  - `request_only` for one-shot adjudicate
  - `repo_probe` for deliberate decisions that rely on the probe
  - `rerun_answer` for decisions that accept a still-valid operator answer
- `files_hint_disposition` is required and is exactly one of `helped`, `hurt`, `ignored`, `absent`
- `checked_files` is required and must be empty only when `decision_basis = request_only`
- candidate count caps at 3
- every candidate must include `why_candidate`, `evidence_refs`, and `score`
- `selected_focus_id` and `selected_focus_summary` are required when `decision_state = selected` and must be `null` otherwise
- `question.prompt` and `question.options` are required only when `decision_state = clarification_requested`; otherwise `question` must serialize as `{ "prompt": "", "options": [] }`
- `adapter_plan.primary_focus_id` must equal `selected_focus_id` for `selected` and must be `null` otherwise
- `adapter_plan.secondary_focus_ids` must be a subset of candidate IDs

### Selection Thresholds

M2 must stop hand-waving around confidence.

Threshold rules:

- `high`: `confidence >= 0.80`
- `medium`: `0.55 <= confidence < 0.80`
- `low`: `confidence < 0.55`

Selection rules:

- select directly when top candidate is `high`
- select directly when top candidate is `medium` and leads the second candidate by at least `0.15`
- ambiguity remains when top candidate is `medium` and lead is `< 0.15`
- ambiguity remains when top candidate is `low`
- `no_viable_focus` is valid when no defensible candidate survives request-only or probe-backed comparison

These rules apply to both adjudicate and deliberate. The deliberate path is different because it gets one repo-backed probe before applying them.

### Runner Flow

```text
_run_analysis_review_v1()
    │
    ├── build contract
    ├── if contract.focus_gate.enabled is false:
    │       continue with legacy proposer path
    │
    └── if contract.focus_gate.enabled is true:
            │
            ├── if default_path == adjudicate:
            │       run focus_gate once
            │       ├── selected -> continue
            │       ├── clarification_requested -> blocked_for_clarification
            │       └── no_viable_focus -> no_viable_focus
            │
            └── if default_path == deliberate:
                    run focus_gate_probe once
                    │
                    ├── if no candidates:
                    │       no_viable_focus
                    │
                    └── run focus_gate once with probe artifact
                            │
                            ├── if selected:
                            │       continue into proposer
                            │
                            ├── if ambiguity remains and clarification_policy == block_for_clarification:
                            │       clarification_requested
                            │
                            └── if ambiguity remains and clarification_policy == never_ask:
                                    no_viable_focus
```

### Exact Verdict Taxonomy

M2 does not add new terminal states.

It keeps:

- `selected`
- `clarification_requested`
- `no_viable_focus`

And keeps these blocked outcomes:

- `run_verdict = "blocked_for_clarification"`
- `content_verdict = "blocked_for_clarification"`
- `validator_verdict = "not_run"`
- `final_summary = "Focus gate blocked the run pending clarification."`

and:

- `run_verdict = "no_viable_focus"`
- `content_verdict = "no_viable_focus"`
- `validator_verdict = "not_run"`
- `final_summary = "Focus gate could not identify a viable focus target."`

The M2 change is in how those outcomes are earned:

- `clarification_requested` now reflects probe-backed ambiguity, not just request-only ambiguity
- `no_viable_focus` can now come from `clarification_policy = never_ask`
- blocked outcomes must carry candidate scores, rationale, `files_hint_disposition`, `checked_files`, and warnings through `focus_decision`

### Stage Recording

M2 should record two distinct gate-adjacent stages on deliberate runs:

1. `role_name = "focus_gate_probe"`
2. `role_name = "focus_gate"`

Rules:

- both are forced read-only
- both use `round_index = 0`
- `focus_gate_probe` records the internal probe artifact
- `focus_gate` records the final public `focus_decision`
- `focus_gate_probe.stage_index < focus_gate.stage_index < proposer.stage_index`
- `metadata.focus_gate_probe.candidate_count` and `metadata.focus_gate_probe.files_hint_disposition` should be copied into the stage record
- `metadata.focus_gate.gate_path`, `metadata.focus_gate.focus_type`, and `metadata.focus_gate.decision_state` remain required

Adjudicate runs should keep a single `focus_gate` stage.

### Gate Role Decision

Keep the strategy role surface small:

- strategy may define `roles.focus_gate`
- runner may reuse that same role config for both `focus_gate_probe` and `focus_gate`
- if absent, both stages fall back to `roles.proposer` with forced read-only access

Do not add a new required `focus_gate_probe` role in strategies. That is needless migration churn.

### Proposer Handoff Contract

Keep prompt-text handoff. Do not add a provider protocol field in M2.

`build_analysis_proposer_prompt()` and `build_analysis_reviser_prompt()` should still accept `focus_decision`, but the fixed `Focus Gate Decision` block must now include:

- `decision_basis`
- `selected_focus_id`
- `selected_focus_summary`
- the next-best candidate ID and score when present
- `checked_files`
- a hard requirement that downstream `primary_seam.seam_id` must equal `selected_focus_id`

The goal is to make the handoff inspectable in artifacts, not implicit in runner memory.

### Rerun Answer Matching Contract

M1 string matching is too thin for M2.

M2 answer acceptance rules:

- `focus_gate_answer.question_prompt` must still match the current question prompt after trimming
- `focus_gate_answer.selected_option` must still match one current question option after trimming
- the selected option must still appear in the current deliberate probe candidate set
- if the selected option vanished from the current probe candidate set, the answer is stale
- if the selected option remains but the current probe now makes a different candidate clearly dominant, the answer is stale
- `freeform_answer` remains advisory context, never the primary matcher

Stale-answer behavior:

- when `clarification_policy = block_for_clarification`, re-ask once with a warning that the prior answer went stale
- when `clarification_policy = never_ask`, emit `no_viable_focus` with a stale-answer warning instead of re-asking

This is still boring. No question IDs. No resume tokens. Just current-candidate reality instead of blind string matching.

### Seam Adapter Rule

M2 keeps the downstream loop seam-shaped.

That means:

- proposer and reviser still emit `primary_seam`
- `selected_focus_id` remains the authoritative upstream seam identity
- shortlisted overflow still lands in `secondary_seams_considered`
- recommendation seam binding remains where it already lives

Enforcement rule stays the same:

- when the gate selected a seam, downstream `primary_seam.seam_id` must match `focus_decision.selected_focus_id`
- semantic validation remains the single owner of that enforcement

Do not split this rule between runner heuristics and validator heuristics.

### Error & Rescue Registry

| Failure | Likely cause | Rescue |
|---|---|---|
| `deliberate` still asks a question with no repo-backed evidence | probe path was skipped or fake | fail tests and inspect stage order; the deliberate path must record `focus_gate_probe` |
| `no_viable_focus` on a task that obviously has a seam | probe candidate generation is weak or score thresholds are wrong | inspect `checked_files`, candidate scores, and warnings; tighten prompt or thresholds |
| stale `focus_gate_answer` still gets accepted | answer matching still relies on prompt/options only | compare against current candidate set before acceptance |
| `never_ask` still emits a question block | policy handling leaked the old clarification behavior | normalize ambiguity to `no_viable_focus` and suppress question serialization |
| selected seam drifts from final `primary_seam` | proposer or reviser ignored gate context | fail semantic validation; do not silently publish |
| candidate evidence refs cite files not actually checked | probe artifact is decorative instead of grounded | fail semantic validation on probe payload |
| report hides why a probe-backed decision won | report only renders ID/summary | render next-best candidate, checked files, and warnings |

## Code Quality Review

### Explicit-Over-Clever Decisions

1. Keep one public `focus_decision` object. Do not create `focus_probe_summary` beside it.
2. Add one internal probe stage. Do not bury repo probing inside a bigger, less testable focus prompt and call it architecture.
3. Widen candidate records in place. Do not create parallel `ranked_candidates` and `shortlist_candidates` arrays.
4. Keep threshold values in code and docs. Do not add YAML knobs in M2.
5. Add `never_ask` as a policy. Do not add a third gate path just to express “same path, different ambiguity behavior.”

### Module-Level Plan

| Slice | Files | What changes |
|---|---|---|
| public contract | `anvil/harness/types.py`, `anvil/harness/contracts.py` | widen `clarification_policy`, keep the same field names, preserve task/strategy precedence |
| schema + semantic rules | `anvil/harness/schemas.py`, `anvil/harness/semantic_validation.py` | widen candidate fields, add probe schema, validate scores/evidence/checked-files invariants |
| prompt surface | `anvil/harness/prompts.py` | add `build_focus_probe_prompt()` and widen final focus-decision prompt instructions |
| runner integration | `anvil/harness/runner.py` | orchestrate probe -> decision on deliberate path, widen answer matching, record stages, normalize `never_ask` |
| reporting | `anvil/harness/report.py`, `anvil/harness/reporting.py` | render decision basis, checked files, candidate rationale, and stale-answer warnings |
| docs | `docs/analysis_review_contract.md` | document public config widening, thresholds, deliberate probe flow, and stale-answer semantics |

### Milestone Boundaries

#### M1: Already Landed Baseline

- typed `focus_gate` policy
- `focus_type = seam`
- `adjudicate` and `deliberate`
- top-level `focus_decision`
- blocked clarification path
- downstream seam-agreement enforcement

#### M2: Branch Scope

- repo-backed deliberate probe
- richer candidate comparison and rationale
- explicit score and lead thresholds
- `clarification_policy = never_ask`
- stale-answer handling against current candidate reality
- richer report surfacing

#### M3: Explicit Follow-On

- remove remaining seam assumptions from gate-core decision logic
- prove a second focus type

## Test Review

### Test Strategy

The existing M1 coverage is real. M2 should add tests only for the new risk surface.

The plan still needs both unit-style coverage and runner-style integration coverage because the M2 behavior is mostly orchestration logic, state normalization, and artifact honesty.

### Code Path Coverage

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/types.py + contracts.py
    │
    ├── focus_gate.clarification_policy
    │   ├── [EXISTS] block_for_clarification
    │   └── [ADD]    never_ask
    │
    └── contract serialization
        └── [ADD]    never_ask survives task/strategy resolution

[+] anvil/harness/schemas.py + semantic_validation.py
    │
    ├── focus_probe_output_schema()
    │   ├── [ADD] checked_files required
    │   ├── [ADD] candidates cap at 3
    │   └── [ADD] evidence_refs subset of checked_files
    │
    └── focus_gate_output_schema()
        ├── [EXISTS] selected / clarification_requested / no_viable_focus
        ├── [ADD]    decision_basis
        ├── [ADD]    files_hint_disposition
        ├── [ADD]    checked_files
        └── [ADD]    candidate why_candidate / evidence_refs / score

[+] anvil/harness/prompts.py
    │
    ├── build_focus_probe_prompt()
    │   └── [ADD] probe-specific instructions and hard caps
    │
    └── build_focus_gate_prompt()
        ├── [EXISTS] gate_path-specific decision prompt
        └── [ADD]    accepts probe artifact and stale-answer context

[+] anvil/harness/runner.py
    │
    ├── adjudicate path
    │   ├── [EXISTS] request-only decision before proposer
    │   └── [ADD]    threshold-based selected vs ambiguous behavior
    │
    ├── deliberate path
    │   ├── [ADD]    focus_gate_probe stage runs first
    │   ├── [ADD]    selected after probe enters proposer
    │   ├── [ADD]    ambiguity + block_for_clarification blocks with question
    │   └── [ADD]    ambiguity + never_ask returns no_viable_focus
    │
    ├── rerun answer path
    │   ├── [EXISTS] prompt/options match plumbing
    │   ├── [ADD]    stale answer when option vanished from current shortlist
    │   └── [ADD]    stale answer when current probe now favors a different seam
    │
    └── stage recording
        ├── [ADD] focus_gate_probe appears before focus_gate
        └── [EXISTS] focus_gate remains before proposer

[+] anvil/harness/report.py + reporting.py
    │
    ├── selected focus block
    │   ├── [EXISTS] selected ID and summary
    │   └── [ADD]    decision_basis, checked_files, next-best candidate
    │
    ├── clarification block
    │   ├── [EXISTS] question + options
    │   └── [ADD]    probe-backed candidate rationale and warnings
    │
    └── no-viable block
        ├── [EXISTS] warnings and candidate summary
        └── [ADD]    never_ask and stale-answer explanation
```

### User Flow Coverage

```text
USER FLOW COVERAGE
===========================
[+] Operator runs a clear seam-focused task with adjudicate
    ├── [EXISTS] Gate selects a seam before proposer
    └── [ADD]    Selection obeys explicit thresholds

[+] Operator runs an ambiguous task with deliberate
    ├── [ADD]    Probe inspects repo files and builds a shortlist
    ├── [ADD]    Gate asks one clarification question only if ambiguity remains
    └── [ADD]    REPORT.md shows checked files and why the shortlist was ambiguous

[+] CI-style task uses deliberate + never_ask
    ├── [ADD]    Probe still runs
    └── [ADD]    Ambiguity returns no_viable_focus instead of a question

[+] Operator reruns with focus_gate_answer
    ├── [EXISTS] Answer can advance the run
    ├── [ADD]    Answer must still match the current shortlist
    └── [ADD]    Stale answer re-asks or no-viables based on policy

[+] Task has weak or misleading files_hint
    ├── [ADD]    Probe records files_hint_disposition = hurt or ignored
    └── [ADD]    Run still proceeds when a defensible shortlist exists

[+] Bounded and trust runs share the same chosen seam
    ├── [EXISTS] downstream drift enforcement
    └── [ADD]    focus_decision now carries grounded checked_files and rationale in both modes
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

If `poetry` is missing on PATH in this repo, use:

```bash
./.venv/bin/python -m pytest -q tests/test_harness_analysis_contract.py tests/test_harness_prompt_consistency.py tests/test_harness_semantic_validation.py tests/test_harness_runner.py tests/test_harness_reporting.py
```

Then run at least four live harness cases with `focus_gate.enabled: true`:

1. adjudicate clear case: expect `decision_state = selected`, no probe stage, proposer present
2. deliberate ambiguous case: expect `focus_gate_probe` then `clarification_requested`, no proposer
3. deliberate ambiguous + `never_ask`: expect `focus_gate_probe` then `no_viable_focus`, no question block
4. deliberate rerun with stale answer: expect probe-backed stale warning and either re-ask or `no_viable_focus` depending on policy

## Failure Modes Registry

| Codepath | Production failure | Test required | Error handling required | User-visible outcome |
|---|---|---|---|---|
| public config parsing | `never_ask` is rejected or silently downgraded | yes | yes | clear config error |
| probe payload | probe cites files it did not inspect | yes | yes | loud validation failure |
| deliberate orchestration | runner asks for clarification without ever probing | yes | yes | blocked output is honest about repo evidence |
| rerun answers | stale answer still gets accepted | yes | yes | operator sees stale-answer warning instead of a silent wrong seam |
| never_ask policy | ambiguous deliberate task still emits a question | yes | yes | deterministic `no_viable_focus` result |
| selected seam handoff | proposer/reviser drift away from selected seam | yes | yes | loud semantic validation failure |
| report rendering | probe-backed rationale never appears in `REPORT.md` | yes | yes | operator can see why the seam won or why ambiguity remained |

Critical gap if omitted:

- If stale rerun answers are not tested, M2 can select the wrong seam after the repo changed and still look “successful” in summary artifacts. That is the exact kind of silent trust failure this branch is supposed to remove.

## Performance Review

### Expected Cost

M2 adds one extra provider round on deliberate runs only.

Expected call profile:

- adjudicate: still 1 gate call before proposer
- deliberate: 1 probe call + 1 final decision call before proposer

That is acceptable because a deliberate task is already ambiguous. Spending 2 cheap read-only calls to avoid a full wrong-seam proposer/critic/reviser/auditor cycle is a good trade.

### Performance Constraints

1. Probe rounds cap at 1.
2. Candidate lists cap at 3.
3. Probe checked files cap at 6.
4. Candidate evidence refs cap at 2 per candidate.
5. No validator round is introduced before proposer.

### Performance Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| deliberate tasks get noticeably slower | M2 adds a second gate call | keep `focus_gate` read-only, fallback to proposer role, and cap probe scope tightly |
| probe reads too many files | cost balloons and rationale gets noisy | hard-cap checked files at 6 and require evidence refs to be path-specific |
| never_ask masks useful clarification in CI | operators may miss a recoverable ambiguity | render rich candidate rationale and warnings in `REPORT.md` and `summary.json` |
| report noise grows | richer candidates can bloat artifacts | render top candidate, next-best candidate, and compact checked-file list instead of dumping raw stage JSON |

## Implementation Plan

### Slice 1: Public Contract and Schema Widening

Files:

- `anvil/harness/types.py`
- `anvil/harness/contracts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/semantic_validation.py`
- `tests/test_harness_analysis_contract.py`
- `tests/test_harness_semantic_validation.py`

Changes:

1. Widen `VALID_FOCUS_GATE_CLARIFICATION_POLICIES` to include `never_ask`.
2. Keep `FocusGatePolicy` public shape intact, but widen `clarification_policy`.
3. Widen `FOCUS_GATE_CANDIDATE_SCHEMA` with `why_candidate`, `evidence_refs`, and `score`.
4. Widen `focus_gate_output_schema()` with `decision_basis`, `files_hint_disposition`, and `checked_files`.
5. Add `focus_probe_output_schema()`.
6. Add semantic validation for:
   - `never_ask`
   - checked-files caps
   - evidence refs subset of checked files
   - candidate score bounds
   - required decision-basis fields

Acceptance:

- existing M1 payloads fail loudly until updated to the widened shape
- `never_ask` survives parsing and contract serialization
- malformed probe artifacts fail before the final decision stage can use them

### Slice 2: Probe Prompt and Decision Prompt Widening

Files:

- `anvil/harness/prompts.py`
- `tests/test_harness_prompt_consistency.py`

Changes:

1. Add `build_focus_probe_prompt()`.
2. Keep `build_focus_gate_prompt()`, but teach it to accept:
   - prior probe artifact
   - optional rerun answer
   - stale-answer warning context
3. Lock prompt instructions for:
   - checked file caps
   - candidate caps
   - score and lead thresholds
   - `files_hint_disposition`
   - `never_ask`

Acceptance:

- prompt text for deliberate runs clearly distinguishes probe and decision work
- prompt-consistency tests prove bounded and trust share the same M2 vocabulary

### Slice 3: Runner Integration

Files:

- `anvil/harness/runner.py`
- `tests/test_harness_runner.py`

Changes:

1. Add `_run_focus_gate_probe()` and a corresponding stage record path.
2. Route deliberate runs through `focus_gate_probe` before the final `focus_gate` decision call.
3. Keep adjudicate runs on the current single-call path.
4. Widen `_focus_gate_answer_matches()` into current-candidate-aware stale-answer logic.
5. Normalize ambiguity under `never_ask` into `no_viable_focus`.
6. Preserve selected-seam handoff and downstream drift enforcement exactly as today.

Acceptance:

- deliberate runs record probe then decision in the right order
- adjudicate runs still record only `focus_gate`
- stale answers never select a seam silently
- blocked runs still skip proposer and validator rounds

### Slice 4: Report and Summary Surfacing

Files:

- `anvil/harness/report.py`
- `anvil/harness/reporting.py`
- `tests/test_harness_reporting.py`

Changes:

1. Render `decision_basis`.
2. Render `files_hint_disposition` and `checked_files`.
3. Render top candidate plus next-best candidate when present.
4. Render stale-answer warnings and `never_ask` explanations for blocked runs.
5. Keep the report compact. No raw stage JSON dumps.

Acceptance:

- selected runs explain why the seam won
- blocked deliberate runs explain what was probed and why ambiguity remained
- `never_ask` blocked runs do not render a fake question block

### Slice 5: Docs

Files:

- `docs/analysis_review_contract.md`

Changes:

1. Document `clarification_policy = never_ask`.
2. Document the deliberate probe round and its caps.
3. Document widened candidate fields and top-level `focus_decision` additions.
4. Document stale-answer semantics.
5. Document that the probe is an internal stage and `focus_decision` remains the only public summary artifact.

Acceptance:

- docs describe the real M2 behavior, not the already-landed M1 baseline

## Worktree Parallelization Strategy

### Dependency Table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Public contract + schema widening | `anvil/harness/types.py`, `anvil/harness/contracts.py`, `anvil/harness/schemas.py`, `anvil/harness/semantic_validation.py` | — |
| B. Prompt surface | `anvil/harness/prompts.py` | A |
| C. Runner integration | `anvil/harness/runner.py` | A, B |
| D. Reporting | `anvil/harness/report.py`, `anvil/harness/reporting.py` | A, C |
| E. Docs | `docs/analysis_review_contract.md` | A, B, D |
| F. Tests | `tests/test_harness_*` | A, B, C, D |

### Parallel Lanes

- Lane A: `A -> B -> C`
  Sequential. The runner needs stable schema names, prompt helper names, and threshold semantics.

- Lane B: `D -> E`
  Can start once A is frozen and C's persisted field names are settled.

- Lane C: `F`
  Splitable late, but should not start before A and most of C are stable.

### Execution Order

1. Freeze the M2 artifact and policy shape in Lane A.
2. Finish runner orchestration in Lane A.
3. Start Lane B once persisted field names are stable.
4. Merge A and B.
5. Run Lane C.

### Conflict Flags

- `runner.py` depends on exact schema fields from A and exact prompt helpers from B.
- `report.py` depends on the persisted field names from C.
- test worktrees will churn badly if they start before the widened candidate schema is final.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Scope | Treat M1 as already landed baseline | Auto-decided | Pragmatic | The code already contains the gate surface and tests; pretending otherwise wastes the branch | re-planning M1 as future work |
| 2 | Scope | Keep M2 seam-only | Auto-decided | Completeness + Minimal diff | The downstream loop is still seam-shaped; adding a second focus type now would be fake genericity | multi-type rollout in this branch |
| 3 | Architecture | Add one internal `focus_gate_probe` stage | Auto-decided | Explicit over clever | Repo probing needs its own testable artifact instead of hiding inside one larger prompt | “probe implicitly inside focus_gate” |
| 4 | Contract | Widen `clarification_policy` to include `never_ask` | Auto-decided | Completeness | Non-interactive deliberate runs need an honest terminal policy, not an implied question path | leaving policy half-typed |
| 5 | Artifact | Keep `focus_decision` as the only public summary artifact | Auto-decided | DRY + Explicit over clever | The probe is implementation detail; user-facing state should stay in one place | new top-level probe artifact family |
| 6 | Runner | Reject stale rerun answers against the current candidate set | Auto-decided | Rigor | Prompt/option string matching alone is too weak once repo-backed probing exists | blind string-match acceptance |
| 7 | Performance | Cap probe round at one and files at six | Auto-decided | Pragmatic | M2 should harden ambiguity handling without turning the gate into a mini review loop | open-ended probing |

## Completion Summary

- Step 0: Scope Challenge — scope reduced to the real residual M2 seam hardening work
- Architecture Review: probe + decision architecture and public/private artifact boundary defined
- Code Quality Review: boring-extension path chosen, no new strategy kind or provider protocol
- Test Review: M2-only coverage diagram produced, stale-answer and `never_ask` gaps made explicit
- Performance Review: deliberate path cost accepted with hard caps
- NOT in scope: written
- What already exists: written
- Failure modes: stale-answer silent selection identified as the key critical gap
- Parallelization: 3 lanes, 1 main sequential lane, 1 late parallel lane
- Lake Score: `7/7` key decisions chose the complete M2 over the cosmetic shortcut
