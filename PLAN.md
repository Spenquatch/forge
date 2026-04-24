# Next Iteration Plan: Canonical Final Publication State

## Purpose

Slice F and the follow-on hardening landed. Good.

The next bug is narrower. It is not recommendation admissibility, topic closure proof, or trust wording in general. It is one product-facing contradiction in the final publication state.

The April 24 trust replay at `.forge-harness-runs/20260424T191008Z-recommend_automation_improvements-838bd449` shows all of these at once:

1. `REPORT.md` says `Final publication: publishable`
2. `REPORT.md` says `Publication blockers: none`
3. the primary deliverable is `PARTIAL_ANSWER.md`
4. the partial deliverable says final publication was blocked and Recommendation 2 was withheld

That means the harness currently has two competing truths for the same run. Humans can notice the contradiction. Downstream tooling cannot.

This slice fixes exactly that.

## The Exact Failure Mechanism

The contradiction is mechanical, not mysterious:

1. `anvil/harness/runner.py:_analysis_publishability()` computes `analysis_review_status.publishability` before artifact projection.
2. `anvil/harness/reporting.py:apply_final_artifacts()` later tries to emit `FINAL_ANSWER.*`.
3. if `_final_answer_admissible()` rejects the payload, `apply_final_artifacts()` silently flips local control flow to `PARTIAL_ANSWER.*` or `BEST_DRAFT.*`.
4. `anvil/harness/report.py` still renders `Final publication: publishable|blocked` from the earlier `analysis_review_status.publishability` object.

So the selected deliverable and the rendered publication state can diverge.

That is the whole bug.

## Step 0: Scope Challenge

### Recommended review mode

Use **HOLD SCOPE**.

This is one seam:

- final publication state finalization
- artifact selection
- report/rendered status parity

Do not reopen trust architecture. Do not reopen Slice F. Do not invent a new publication state model.

### What already exists

| Sub-problem | Existing code | Why it is enough |
|---|---|---|
| pre-artifact publication gating | `anvil/harness/runner.py:_analysis_publishability()` | already owns provenance/topic/semantic/content blockers |
| final artifact selection | `anvil/harness/reporting.py:apply_final_artifacts()` | already decides `FINAL_ANSWER.*` vs `PARTIAL_ANSWER.*` vs `BEST_DRAFT.*` |
| final-answer payload admissibility check | `anvil/harness/reporting.py:_final_answer_admissible()` | already catches the payload mismatch that triggers the contradiction |
| report-side publication rendering | `anvil/harness/report.py` | already renders both publication state and primary deliverable |
| regression coverage for fallback artifacts | `tests/test_harness_reporting.py` | already covers partial-answer and best-draft fallback paths, but not canonical-state parity |
| contract wording | `README.md`, `docs/analysis_review_contract.md`, `tests/test_harness_analysis_contract.py` | already freeze field names and artifact semantics |

### Minimum change that achieves the goal

Do not add a new top-level state object.

The minimum complete fix is:

1. keep `analysis_review_status.publishability` as the canonical field
2. finalize that field after artifact selection knows what actually shipped
3. make `REPORT.md`, `summary.json`, and fallback deliverables all project that finalized field

Anything bigger is overbuilt.

### Complexity check

Target touched files:

- `anvil/harness/reporting.py`
- `anvil/harness/report.py`
- `tests/test_harness_reporting.py`
- `README.md`
- `docs/analysis_review_contract.md`
- `tests/test_harness_analysis_contract.py`

Optional only if wording drift forces it:

- `FORGE_HARNESS_SURFACE_UPDATE_NOTES.md`

This stays under one module seam and one doc seam. Good.

### Search check

- **[Layer 1]** reuse `analysis_review_status.publishability`
- **[Layer 1]** reuse `summary["artifacts"]["final_artifact_kind"]`
- **[Layer 1]** reuse `_final_answer_admissible()` as the predicate source, or refactor it into a blocker-producing helper
- **[Layer 3]** stop letting pre-selection policy masquerade as final publication truth

No external search needed. The bug is entirely repo-local.

### Completeness check

Take the complete version.

A runtime-only patch is not enough if docs and tests still describe pre-selection publishability as if it were final truth. The extra cost to update docs and regression tests is minutes.

### Distribution check

No new artifact type. No CI or release work changes.

This slice changes the truth contract behind existing run artifacts only.

## Architecture Review

### Current flow

```text
runner builds analysis_review_status.publishability
    │
    ├── report renders "Final publication: publishable"
    │
    ▼
apply_final_artifacts()
    │
    ├── tries FINAL_ANSWER payload
    ├── _final_answer_admissible() returns false
    └── falls back to PARTIAL_ANSWER or BEST_DRAFT
         without finalizing publishability
```

That is how we get one run claiming both "publishable" and "blocked".

### Target flow

```text
runner builds initial publishability candidate
    │
    ▼
apply_final_artifacts()
    │
    ├── evaluates actual FINAL_ANSWER payload admissibility
    ├── finalizes analysis_review_status.publishability
    │    ├── final_answer_publishable = true only if FINAL_ANSWER actually ships
    │    └── blocking_causes include payload/admissibility blockers when fallback wins
    └── emits FINAL_ANSWER or PARTIAL_ANSWER or BEST_DRAFT
         from the same finalized state
    │
    ▼
REPORT.md + summary.json + fallback markdown all read the same finalized truth
```

### Canonical invariant

After this slice, these must always agree:

1. `analysis_review_status.publishability.final_answer_publishable`
2. `summary["artifacts"]["final_artifact_kind"] == "final_answer"`
3. `REPORT.md` lines for `Final publication:` and `Primary deliverable:`

Concrete invariant:

```text
analysis_review_status.publishability.final_answer_publishable
==
(summary["artifacts"]["final_artifact_kind"] == "final_answer")
```

If that expression is false in either direction, the run is invalid.

### Canonical implementation contract

Freeze these rules:

1. `analysis_review_status.publishability` remains the canonical publication-state field.
   No new sibling field. No `publication_outcome_v2`. No renderer-only override.

2. `apply_final_artifacts()` becomes the finalizer for publishability.
   Runner still computes the initial candidate state. Artifact selection finalizes it.

3. If `FINAL_ANSWER.*` does not ship for any reason, `final_answer_publishable` must end as `false`.

4. `blocking_causes` must explain the final demotion reason when artifact selection falls off the final-answer path.

5. Payload/admissibility blockers must be deterministic. Use exact strings:
   - `final answer payload includes recommendation indices withheld from FINAL_ANSWER.*: <indices>`
   - `final answer payload omits recommendation indices required for FINAL_ANSWER.*: <indices>`

6. Existing policy blockers keep their current wording and order. Payload blockers append after existing blockers.

7. `report.py` continues to render from `analysis_review_status.publishability`. It does not grow its own artifact-state logic.

8. Bounded mode keeps its current admissibility semantics. This slice only enforces publication-state parity. If bounded ever falls off the final-answer path, the same invariant applies.

### File-by-file implementation plan

#### 1. `anvil/harness/reporting.py`

Make `apply_final_artifacts()` finalize publication state instead of carrying a private `final_answer_blocked` truth.

Required changes:

- Refactor `_final_answer_admissible()` into a blocker-aware helper, or add a sibling helper:
  - input: `summary`, candidate payload
  - output: deterministic blocker strings, not just `True` / `False`
- In `apply_final_artifacts()`:
  - compute existing publishability from `analysis_review_status.publishability`
  - if the run is fully accepted and the initial state says publishable, evaluate payload blockers before selecting `FINAL_ANSWER.*`
  - if payload blockers exist:
    - set `analysis_review_status.publishability.final_answer_publishable = False`
    - append payload blockers to `blocking_causes`
    - keep selecting `PARTIAL_ANSWER.*` or `BEST_DRAFT.*` exactly as today
- Write the finalized publishability back to both:
  - `summary["analysis_review_status"]`
  - `summary["run_details"]["analysis_review_status"]` when present
- Keep `_append_blocked_publication_note()` reading the finalized blocker list, not an alternate local truth

Do not create a new module for this. Keep it in `reporting.py`.

#### 2. `anvil/harness/report.py`

Keep rendering thin.

Required changes:

- no new decision logic
- no artifact-kind reinterpretation
- only consume finalized `analysis_review_status.publishability`

If needed, add one defensive assertion in tests that the report overview and the analysis-review-status section both show the same final publication state.

#### 3. `README.md`

Update the contract text so it says the correct thing:

- `analysis_review_status.publishability` is the canonical final publication outcome
- artifact selection finalizes that outcome
- if `FINAL_ANSWER.*` does not ship, `final_answer_publishable` must be `false`
- `summary["artifacts"]` and `publishability` must agree

Do not turn README into an ADR. One concise paragraph is enough.

#### 4. `docs/analysis_review_contract.md`

Add the explicit invariant and blocker semantics.

Must document:

- `final_answer_publishable` is not merely a pre-selection gate
- it is finalized after artifact projection
- payload/admissibility mismatch can add final publication blockers
- `REPORT.md` and `summary.json["artifacts"]` must agree with that finalized state

Keep the field names unchanged.

#### 5. `tests/test_harness_reporting.py`

This is the main regression lock.

Required changes:

- extend the trust partial-fallback test so it also asserts:
  - `summary.json["analysis_review_status"]["publishability"]["final_answer_publishable"] is False`
  - `REPORT.md` says `Final publication: blocked`
  - `REPORT.md` primary deliverable is `partial_answer`
  - the new payload blocker string is present
- extend the best-draft fallback test for omitted accepted recommendations so it also asserts:
  - `final_answer_publishable` flips to `False`
  - `REPORT.md` says `blocked`
  - `blocking_causes` includes the omission blocker
- add one explicit parity regression:
  - no accepted run may produce `PARTIAL_ANSWER.*` or `BEST_DRAFT.*` while the report still says `publishable`
- keep the bounded accepted-final test unchanged except for one extra assertion:
  - it still says `publishable`
  - it still ships `FINAL_ANSWER.*`

#### 6. `tests/test_harness_analysis_contract.py`

Add assertions for the new invariant language in:

- `README.md`
- `docs/analysis_review_contract.md`

Only touch other doc assertions if current wording becomes contradictory.

## Code Quality Review

### Issue 1: duplicated authority in publication state

Current problem:

- `analysis_review_status.publishability` says one thing
- local `final_answer_blocked` flow in `apply_final_artifacts()` can say another

Decision:

- one authoritative finalization point in `apply_final_artifacts()`
- zero renderer-owned reinterpretation

Why:

This matches your preferences exactly: explicit over clever, minimal diff, no duplicate sources of truth.

### Issue 2: avoid inventing a new publication schema

Decision:

- keep `publishability`
- keep `final_answer_publishable`
- keep `blocking_causes`

Why:

A new state object would be architecture cosplay. The bug is not missing vocabulary. It is stale vocabulary.

### Issue 3: do not hide the mismatch behind markdown-only notes

Decision:

- the blocker must live in structured status first
- markdown notes only project it

Why:

Machines read `summary.json`. Humans read markdown. The structured state wins.

## Test Review

### Framework

Use `pytest`.

### Code path coverage

```text
CODE PATH COVERAGE
==================

[+] anvil/harness/reporting.py::apply_final_artifacts()
    │
    ├── fully accepted + publishable + payload matches final admissibility
    │   └── [★★ TESTED] emits FINAL_ANSWER
    │
    ├── fully accepted + publishable + payload includes withheld indices
    │   └── [GAP] must demote to PARTIAL_ANSWER and finalize publishability=false
    │
    ├── fully accepted + publishable + payload omits required final indices
    │   └── [GAP] must demote to BEST_DRAFT and finalize publishability=false
    │
    └── fully accepted + already blocked by provenance/topic/warnings
        └── [★★ TESTED] fallback path exists, but blocker finalization parity should be asserted

[+] anvil/harness/report.py::render_report()
    │
    ├── Overview section renders Final publication
    ├── Overview section renders Primary deliverable
    └── Analysis Review Status section renders Final publication / blockers
        └── [GAP] report must never claim publishable when primary deliverable is not final_answer

[+] Fallback deliverable markdown
    │
    ├── PARTIAL_ANSWER note shows blockers and withheld indices
    └── BEST_DRAFT note shows blockers and withheld indices when applicable
        └── [★★ TESTED] note exists, but structured publishability parity should be asserted

────────────────────────────────────────────
COVERAGE TARGET
  Runtime parity checks: 4
  Report parity checks: 3
  Contract/doc assertions: 2
────────────────────────────────────────────
```

### Required test edits

1. Extend the existing trust partial-fallback regression in `tests/test_harness_reporting.py`.
   Add assertions for finalized `publishability`, report status, and exact blocker string.

2. Extend the existing best-draft fallback regression for omitted accepted recommendations.
   Add assertions for finalized `publishability`, report status, and exact omission blocker.

3. Add one explicit parity regression:
   if `final_artifact_kind != "final_answer"`, report text must not contain `Final publication: publishable`.

4. Keep one bounded accepted-final regression as the control.
   It proves this slice does not accidentally demote good final answers.

5. Update `tests/test_harness_analysis_contract.py` for the new invariant wording.

### Regression rule

This is a regression slice.

The trust replay already proved a previously shipped branch can emit contradictory publication state. Regression tests are mandatory. No TODO deferral.

## Performance Review

No meaningful runtime risk.

The new work is tiny:

- normalize recommendation indices
- compute two set diffs
- append deterministic blocker strings

Guardrails:

- do not add another deep-copy pass over the whole summary
- do not recompute draft selection
- do not scan recommendation lists more than once per finalization path

## Failure Modes Registry

| Failure mode | Test required | Error handling required | User-visible impact if missed |
|---|---|---|---|
| partial deliverable ships while report still says publishable | yes | yes | contradictory run report, tooling cannot trust summary |
| best draft ships because final payload omitted accepted recommendations but publishability stays true | yes | yes | silent downgrade with false publishability |
| payload blocker is added only to markdown note, not structured status | yes | yes | JSON/markdown drift |
| duplicate blocker strings accumulate across retries or rewrites | yes | yes | noisy reports and unstable assertions |
| bounded accepted-final run is accidentally demoted by trust-only logic leaking across modes | yes | yes | false negative final publication |

Critical gap definition for this slice:

If a fallback artifact can ship without `analysis_review_status.publishability` changing to `blocked`, that is a critical gap.

## What Already Exists

The repo already has most of the machinery this slice needs:

- `apply_final_artifacts()` already owns final artifact selection
- `_final_answer_admissible()` already knows when the final payload should not ship
- `render_report()` already renders both publication state and primary deliverable
- existing tests already cover partial-answer and best-draft fallback mechanics

The slice is not about building those seams. It is about making them agree.

## NOT in Scope

- recommendation admissibility redesign
- topic closure proof changes
- new artifact kinds
- trust vs bounded strategy redesign
- new publication state schema
- line-level provenance
- replay-diff tooling
- validator policy changes unrelated to final publication-state parity

## Worktree Parallelization Strategy

Sequential implementation, no parallelization opportunity.

Reason:

- the blocker vocabulary lives in one seam
- runtime, report assertions, and docs all depend on the same exact wording
- parallel worktrees would mostly fight over strings and truth ownership

Do it in one lane:

1. finalize runtime state in `reporting.py`
2. lock report regression tests
3. update docs and contract assertions

## Completion Summary

- Step 0: Scope Challenge, scope held
- Architecture Review: one core issue, split publication authority between status and artifact selection
- Code Quality Review: three issues found, all resolved by one finalization seam
- Test Review: coverage diagram produced, four regression assertions required
- Performance Review: no material runtime risk
- NOT in scope: written
- What already exists: written
- Failure modes: one critical gap class pinned, five failure modes enumerated
- Parallelization: sequential, one lane
- Lake Score: complete option chosen, no shortcut accepted

## Exit Criteria

This slice is done only when all of these are true:

1. no run can emit `PARTIAL_ANSWER.*` or `BEST_DRAFT.*` while `REPORT.md` still says `Final publication: publishable`
2. `analysis_review_status.publishability.final_answer_publishable` matches `summary["artifacts"]["final_artifact_kind"] == "final_answer"`
3. trust fallback runs persist payload/admissibility blockers into structured status
4. the trust partial-fallback regression covers the exact contradiction seen on April 24
5. the omitted-accepted-recommendation best-draft regression covers the second silent mismatch path
6. bounded accepted-final behavior remains unchanged
7. README and contract docs explicitly describe publishability as finalized post-selection truth

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Hold scope on publication-state parity only | mechanical | P3 pragmatic | The active bug is one contradiction, not a broader trust redesign | reopening Slice F or trust architecture |
| 2 | Eng | Keep `analysis_review_status.publishability` as the canonical field | mechanical | P5 explicit | The bug is stale state, not missing schema | adding `publication_state_v2` |
| 3 | Eng | Finalize publishability inside `apply_final_artifacts()` | mechanical | P1 completeness | Artifact selection is where actual ship state becomes known | report-side reinterpretation |
| 4 | Eng | Use deterministic payload blocker strings for extra vs missing indices | mechanical | P5 explicit | Tests and reports need stable reasons, not vague “inadmissible” wording | one generic blocker with no detail |
| 5 | Eng | Keep the slice sequential | mechanical | P3 pragmatic | This seam is small and wording-sensitive | parallel worktrees for runtime/tests/docs |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | clear | Scope held to one product bug: canonical final publication state |
| Codex Review | `codex review` | Independent 2nd opinion | 1 | clear | Root cause is split authority between pre-selection publishability and post-selection artifact fallback |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clear | One seam, six target files, four regression assertions, no new schema |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No UI scope |

**VERDICT:** CLEARED. This is the next slice. It is narrow, implementable, and specific enough to code without another planning pass.
