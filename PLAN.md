# Analysis Review Bounded-Work Redesign Plan

## Purpose

Turn `analysis_review_v1` into a bounded-review harness where runtime predictability comes from explicit work contracts, not from provider turn semantics or blunt subprocess timeouts.

This plan is now implementation-ready enough for a small PR sequence. The main move is simple:

- keep the existing harness shape
- tighten the contract
- carry bounded review surfaces inside the existing structured payload
- enforce the new limits in semantic validation

No second harness. No new strategy kind. No derived packet subsystem in v1.

## Step 0: Scope Challenge

### What already exists

The repo already has most of the machinery this redesign needs.

| Existing surface | What it already solves | Reuse decision |
|---|---|---|
| [`anvil/harness/contracts.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:1) | Typed contract, stop policy, shared role rules | Reuse and extend |
| [`anvil/harness/prompts.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:320) | Distinct proposer/critic/reviser/auditor prompt builders | Reuse and narrow |
| [`anvil/harness/schemas.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:1) | Structured payloads for recommendations, review issues, issue resolution | Reuse and extend |
| [`anvil/harness/semantic_validation.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:1) | Contract-aware validation beyond JSON schema | Reuse as the primary enforcement point |
| [`anvil/harness/runner.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:456) | Stage orchestration, issue ledger, recommendation reviews, loop control | Reuse, avoid new orchestration path |
| [`anvil/harness/report.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py:1) | Human-readable contract/report output | Reuse for packet-budget visibility |
| Existing tests under [`tests/`](/Users/spensermcconnell/__Active_Code/forge/tests) | Contract, prompt, semantic validation, runner integration coverage | Extend, do not create a second test stack |

### Existing behavior we should not rebuild

The current harness already has:

- stable `AR-###` issue IDs
- an issue ledger across rounds
- recommendation-level verdicts
- semantic validation hooks
- review coverage reporting

That matters because the redesign does **not** need a separate packet store or a second review-loop implementation. The cheap move is to make the existing payloads more explicit and more bounded.

### Minimum viable scope

The minimum change that achieves the goal is:

1. extend the contract with bounded-review policy
2. extend recommendation payloads with bounded `review_surface`
3. update prompts to force bounded reviewer behavior
4. enforce the limits in semantic validation
5. surface bounded-review metrics in the report

Anything beyond that is optional.

### Scope reduction decision

The original outline implied a big surface area. That is a smell. The plan now reduces scope in three concrete ways:

1. **No new strategy kind**
   Keep `analysis_review_v1`, bump the contract version, and let the existing runner keep working.

2. **No derived packet artifact in v1**
   Put the bounded review surface directly on each recommendation instead of inventing a second artifact lifecycle.

3. **No provider-specific budget logic as the main mechanism**
   Provider knobs remain secondary. The harness contract is the control plane.

### Search check

- **[Layer 1]** Reuse the existing issue ledger and recommendation-review model instead of building a parallel packet tracker.
- **[Layer 1]** Reuse semantic validation as the enforcement point instead of scattering caps across runner conditionals.
- **[Layer 3]** Bound reviewer work with payload-level surfaces and budget caps. This is the boring move, and it matches the codebase you already have.

No external framework built-in replaces this cleanly. This is harness-specific behavior. First-principles design is the right tool here.

### Complexity check

This still touches more than 8 files. That remains a smell, so implementation should be split:

- **PR 1**: contract, schema, prompts, semantic validation, docs, focused unit tests
- **PR 2**: runner/reporting exposure, strategy example, integration tests

That keeps structural and behavioral changes separated. Much safer.

### Completeness check

Do the complete version for the bounded-review contract now:

- bounded review surface
- issue budgets
- scope-escape justification
- reviewer prompt changes
- semantic validation
- tests

Do **not** ship a half-version where prompts mention bounded work but validation cannot enforce it. That would create a paper contract. Not great.

### Distribution check

No new binary, package, or container is introduced here. Distribution work is not applicable.

## Architecture Review

### Opinionated decisions

#### 1. Evolve in place, contract bump only

**Recommendation:** keep strategy kind `analysis_review_v1`, introduce `analysis_review_v1_contract_v3`.

Why:

- the runner, report, and tests already key off the current harness kind
- a new strategy kind would spend an innovation token on routing, not on user value
- the change is behavioral, not architectural enough to deserve a second runtime path

#### 2. Reuse `evidence`, add `review_surface`

**Recommendation:** keep `recommendations[].evidence` as the canonical bounded evidence list and add one nested `review_surface` object per recommendation.

Do **not** add both `evidence` and `primary_evidence`. That is avoidable duplication.

Recommended `review_surface` shape:

```json
{
  "must_check_files": ["path/a.py", "path/b.py"],
  "optional_check_files": ["path/c.py"],
  "scope_note": "Validate timeout handling and retry behavior only."
}
```

Contract defaults:

- `evidence` length: `1..3`
- `must_check_files` length: `1..3`
- `optional_check_files` length: `0..2`

That is enough structure to bound the critic without creating a second packet artifact.

#### 3. Add explicit bounded-review policy to the contract

Add a new contract section, for example:

```python
@dataclass
class BoundedReviewPolicy:
    max_evidence_refs_per_recommendation: int = 3
    max_must_check_files_per_recommendation: int = 3
    max_optional_check_files_per_recommendation: int = 2
    critic_issue_cap: int = 5
    critic_new_topic_cap: int = 2
    auditor_new_medium_or_higher_issue_cap_after_round0: int = 1
    require_scope_escape_justification: bool = True
```

This belongs in the contract, not strategy YAML, because it defines harness semantics.

Strategy YAML can still tune loops/timeouts later, but the behavioral rules need one source of truth.

#### 4. Track scope escapes explicitly

Add a review-payload field for when a critic or auditor leaves the bounded review surface:

```json
{
  "scope_escapes": [
    {
      "path": "anvil/harness/state.py",
      "reason": "Cited evidence was contradictory, needed adjacent source of truth."
    }
  ]
}
```

Why this matters:

- reporting can explain why a run got slower
- semantic validation can reject unjustified broad repo exploration
- the auditor can still escalate real blockers without silently becoming a second full review

#### 5. Reviser stays ledger-first

Keep the reviser contract narrow:

- revise only against open issues
- preserve accepted recommendations when possible
- do not add new recommendations unless required to close a logged gap or satisfy minimum recommendation count

The reviser is not a second proposer.

### Target flow

```text
task + workspace
      │
      ▼
 PROPOSER
   ├─ recommendations[ ]
   │   ├─ evidence[1..3]
   │   └─ review_surface
   │       ├─ must_check_files[1..3]
   │       ├─ optional_check_files[0..2]
   │       └─ scope_note
   └─ files_reviewed
      │
      ▼
 CRITIC
   ├─ validate cited evidence first
   ├─ stay inside review_surface by default
   ├─ raise <= 5 issues
   ├─ raise <= 2 new topics
   └─ record scope_escapes if it leaves bounds
      │
      ▼
 REVISER
   ├─ resolve open issue ledger
   ├─ preserve accepted recommendations
   └─ no broad re-analysis
      │
      ▼
 AUDITOR
   ├─ verify issue closure first
   ├─ only add new medium+ issue if justified
   └─ record scope_escapes if it leaves bounds
```

### Realistic production failure scenarios

| Surface | Failure mode | Plan response |
|---|---|---|
| Contract defaults | Caps drift between prompt text and semantic validation | Centralize caps in contract and render them into prompts |
| Proposer payload | `review_surface` references files not in `files_reviewed` | Semantic validation rejects payload |
| Critic | Raises 12 issues and effectively restarts the task | Semantic validation rejects issue-cap overflow |
| Auditor | Raises a new blocker in round 2 with no explanation | Semantic validation rejects missing scope-escape / missing `why_not_raised_earlier` |
| Reporting | Operators cannot tell why one run was slower than another | Add scope-escape counts and budget-usage summary to report |

## Code Quality Review

### Keep the design DRY

The dangerous version of this work is:

- caps hard-coded in prompts
- separate caps hard-coded in semantic validation
- runner warnings with their own thresholds

That would rot immediately.

The clean version is:

- contract stores the numbers
- prompts render the numbers
- semantic validation enforces the numbers
- reports display the numbers and actual usage

One source of truth. Minimal diff. Explicit over clever.

### Module boundaries

| File | Responsibility after change |
|---|---|
| [`anvil/harness/contracts.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:1) | Contract version bump, bounded-review policy dataclasses |
| [`anvil/harness/schemas.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:1) | `review_surface` and `scope_escapes` schema additions |
| [`anvil/harness/prompts.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:320) | Role-boundary wording that mirrors contract caps |
| [`anvil/harness/semantic_validation.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:1) | Budget enforcement and cross-field coherence |
| [`anvil/harness/runner.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:456) | Persist new review metadata, no new loop type |
| [`anvil/harness/report.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py:1) | Show bounded-review usage and scope escapes |

### Engineering quality rules for implementation

- keep new types in the existing modules, do not spawn helper files unless one module becomes unreadable
- keep schema additions additive where possible
- keep reporter output human-readable, not raw JSON blobs everywhere
- update docs and tests in the same PR as each behavioral change

## Implementation Plan

### Slice 1: Contract and schema foundation

**Files**

- [`anvil/harness/contracts.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:1)
- [`anvil/harness/schemas.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:1)
- [`docs/analysis_review_contract.md`](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md:1)

**Changes**

- bump contract version to `analysis_review_v1_contract_v3`
- add `BoundedReviewPolicy`
- add `REVIEW_SURFACE_SCHEMA`
- add `SCOPE_ESCAPE_SCHEMA`
- extend proposer/reviser recommendation schema with `review_surface`
- extend critic/auditor review schema with `scope_escapes`

**Acceptance**

- contract serializes the new policy
- schemas accept bounded payloads and reject malformed surfaces
- docs describe the new bounded-review semantics

### Slice 2: Prompt and validation enforcement

**Files**

- [`anvil/harness/prompts.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:320)
- [`anvil/harness/semantic_validation.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:1)

**Changes**

- proposer prompt requires bounded `evidence` and `review_surface`
- critic prompt says "validate cited evidence first, do not perform open-ended repo exploration"
- auditor prompt says "issue-closure first, new medium+ issues after round 0 require explicit justification"
- semantic validation enforces:
  - evidence cap
  - `must_check_files` / `optional_check_files` caps
  - `must_check_files ⊆ files_reviewed`
  - issue cap
  - new-topic cap
  - round>0 medium+ issues require `why_not_raised_earlier`
  - scope escapes require non-empty reasons

**Acceptance**

- invalid bounded-review payloads fail before they can influence loop behavior
- prompts and validation both reflect the same contract numbers

### Slice 3: Runner and reporting visibility

**Files**

- [`anvil/harness/runner.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:456)
- [`anvil/harness/report.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py:1)
- [`anvil/harness/reporting.py`](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py:1)

**Changes**

- include bounded-review policy in final run details
- persist `scope_escapes` and budget-usage counts in summary details
- report:
  - review-surface mode
  - issue cap / actual usage
  - missed-topic cap / actual usage
  - scope escapes and reasons

**Acceptance**

- operators can tell whether a run stayed packet-bounded
- when a reviewer leaves the bounded surface, the report says so plainly

### Slice 4: Tests and example strategy

**Files**

- [`tests/test_harness_analysis_contract.py`](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py:1)
- [`tests/test_harness_prompt_consistency.py`](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py:1)
- [`tests/test_harness_semantic_validation.py`](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py:1)
- [`tests/test_harness_runner.py`](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:333)
- [`tests/fixtures/harness/analysis_review_semantic_cases.json`](/Users/spensermcconnell/__Active_Code/forge/tests/fixtures/harness/analysis_review_semantic_cases.json:1)
- [`examples/harness/strategies/analysis_review_codex_claude.yaml`](/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/analysis_review_codex_claude.yaml:1)

**Changes**

- add contract serialization assertions for bounded policy
- add prompt text assertions for critic/auditor bounded wording
- add semantic-validation failures for cap overflow and invalid `review_surface`
- add runner integration coverage for accepted bounded-review payloads
- leave provider timeout tuning unchanged in the first PR unless tests show the caps are still too loose

**Acceptance**

- full test suite proves bounded review is enforced structurally and semantically
- example strategy remains provider-agnostic

## Test Review

### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] anvil/harness/contracts.py
    │
    └── build_analysis_review_contract()
        ├── [★★  TESTED] Existing contract defaults — tests/test_harness_analysis_contract.py
        └── [GAP]         BoundedReviewPolicy serialization and v3 versioning

[+] anvil/harness/schemas.py
    │
    ├── RECOMMENDATION_SCHEMA
    │   └── [GAP]         review_surface shape + bounds
    └── analysis_review_schema()
        └── [GAP]         scope_escapes on critic/auditor payloads

[+] anvil/harness/prompts.py
    │
    ├── build_analysis_proposer_prompt()
    │   └── [GAP]         bounded evidence + review_surface instructions
    ├── build_analysis_critic_prompt()
    │   └── [GAP]         issue cap + no open-ended repo exploration
    ├── build_analysis_auditor_prompt()
    │   └── [GAP]         issue-closure-first + scope escape rules
    └── build_analysis_reviser_prompt()
        └── [GAP]         ledger-first wording with no broad re-analysis

[+] anvil/harness/semantic_validation.py
    │
    ├── validate_analysis_output_payload()
    │   ├── [★★  TESTED] Existing section/files_reviewed rules
    │   └── [GAP]         review_surface subset/cap validation
    └── validate_analysis_review_payload()
        ├── [★★  TESTED] Existing recommendation coverage / issue classification
        └── [GAP]         issue caps, new-topic caps, scope_escape validation

[+] anvil/harness/runner.py + report.py
    │
    ├── summary details
    │   └── [GAP]         bounded-review metrics surfaced
    └── human report
        └── [GAP]         scope escape visibility
```

### User-flow coverage

```text
USER FLOW COVERAGE
===========================
[+] Normal bounded run
    ├── [GAP] [→UNIT] proposer emits bounded review surface
    ├── [GAP] [→UNIT] critic stays within cap and validates recommendations
    ├── [GAP] [→UNIT] reviser closes issue ledger without new rec churn
    └── [GAP] [→INT]  report shows bounded-review policy and usage

[+] Reviewer escapes bounded surface
    ├── [GAP] [→UNIT] critic escape with reason is accepted
    ├── [GAP] [→UNIT] critic escape without reason is rejected
    └── [GAP] [→INT]  report surfaces escape reason

[+] Auditor late blocker
    ├── [GAP] [→UNIT] new round>0 medium issue with why_not_raised_earlier passes
    └── [GAP] [→UNIT] new round>0 medium issue without why_not_raised_earlier fails
```

```text
─────────────────────────────────
COVERAGE: 4 existing paths tested, 13 gaps to add
QUALITY:  ★★★: 0  ★★: 4  ★: 0
GAPS: contract/schema/prompt/validation/report visibility
─────────────────────────────────
```

### Required new tests

1. `tests/test_harness_analysis_contract.py`
   Assert `analysis_review_v1_contract_v3` and bounded-review default caps serialize correctly.

2. `tests/test_harness_prompt_consistency.py`
   Assert each prompt includes the exact bounded-review policy language rendered from the contract.

3. `tests/test_harness_semantic_validation.py`
   Add cases for:
   - too many evidence refs
   - `must_check_files` not present in `files_reviewed`
   - too many issues in critic payload
   - too many missing topics
   - empty `scope_escapes[].reason`

4. `tests/test_harness_runner.py`
   Add an integration case where a bounded run succeeds and the report exposes the bounded-review summary.

5. `tests/fixtures/harness/analysis_review_semantic_cases.json`
   Add valid and invalid bounded-review fixtures.

## Failure Modes

| New codepath | Real production failure | Test planned | Error handling planned | User-visible outcome |
|---|---|---|---|---|
| Contract v3 serialization | Prompt/validator numbers diverge | Yes | Fail tests | Internal only |
| `review_surface` validation | Proposer points critic at files it never inspected | Yes | Semantic validation error | Clear harness error |
| Critic issue cap enforcement | Critic performs full re-review and explodes issue count | Yes | Semantic validation error | Clear harness error |
| Auditor late-issue rule | Auditor invents a new blocker in round 2 with no explanation | Yes | Semantic validation error | Clear harness error |
| Scope escape reporting | Reviewer leaves packet bounds but operators cannot tell why run slowed down | Yes | Report summary | Clear report note |

**Critical gaps to avoid in implementation**

None are acceptable where all three are true:

- no test
- no validation/error handling
- silent behavior drift

The only way to avoid that is to ship validation and tests with the prompt changes, not after.

## Performance Review

### Main performance concern

The redesign is supposed to reduce review-time work. It will fail if we add heavy validation while still allowing open-ended repo exploration.

The practical performance rule is:

- small extra schema/semantic-validation cost is fine
- unbounded extra file reads are not

### Performance guidance

- validate caps using cheap list-count and subset checks
- do not resolve or stat the whole repo to enforce bounded review
- keep report summaries count-based, not full duplicated packet dumps

### Caching / complexity notes

- no new caching layer needed
- no N+1-style data structure risk in this design
- avoid serializing duplicate large payload blobs into both runner details and report artifacts if a compact count will do

## NOT in Scope

- New strategy kind such as `analysis_review_v2`
  Rationale: too much routing churn for too little value.

- Provider-specific turn-budget tuning as the main fix
  Rationale: this is exactly the fragile control surface we are trying to de-emphasize.

- A standalone derived packet artifact lifecycle
  Rationale: existing proposer payload already carries recommendations and evidence.

- A new "deep review" mode in the first PR
  Rationale: useful later, but it expands scope before bounded-review basics are proven.

- Replacing `timeout_sec`
  Rationale: keep it as the safety fuse.

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| Slice 1: contract + schema | `anvil/harness/`, `docs/` | — |
| Slice 2: prompt + semantic validation | `anvil/harness/`, `tests/` | Slice 1 |
| Slice 3: runner + report visibility | `anvil/harness/` | Slice 1 |
| Slice 4: tests + example strategy | `tests/`, `examples/`, `docs/` | Slice 2, Slice 3 |

### Parallel lanes

- **Lane A:** Slice 1 → Slice 2
  Sequential, shared `anvil/harness/` contract/validation surfaces.

- **Lane B:** Slice 3
  Can start after Slice 1 lands, mostly runner/report visibility.

- **Lane C:** Slice 4
  Wait for A + B because tests need final schema/prompt/report shapes.

### Execution order

Launch **Lane A** and **Lane B** after the contract/schema direction is fixed.

Merge both.

Then run **Lane C**.

### Conflict flags

- Lanes A and B both touch `anvil/harness/`
  Potential merge conflict. Safe only with clear ownership and small patches.

## Review Completion Summary

- Step 0: Scope Challenge — scope reduced to in-place contract evolution, no new harness kind
- Architecture Review: 5 core decisions locked
- Code Quality Review: 2 structural rules locked
- Test Review: diagram produced, 13 gaps identified
- Performance Review: 1 primary concern, no new infra required
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 0 proposed
- Failure modes: 0 unresolved critical gaps if validation + tests ship together
- Outside voice: skipped
- Parallelization: 3 lanes, 1 parallel window / 2 sequential dependencies
- Lake Score: 5/5 recommendations chose the complete option

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 21 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**UNRESOLVED:** 0
**VERDICT:** ENG CLEARED — ready to implement
