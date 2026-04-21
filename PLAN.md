<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260421-102518.md -->

# Next Iteration Plan: Trust Auditability and Topic Accounting

## Purpose

The bounded/trust split landed. That part is real.

The next iteration should make the trust tier feel dependable instead of merely stricter in reporting. The current repo already has explicit strategy kinds, a unified contract, issue-ledger carry-forward, provenance binding, and `accepted_with_warnings`. The remaining gap is that some reviewer concerns still disappear too easily, and some trust evidence is bound as payload shape instead of as auditable review proof.

This plan turns the outside notes into one tight follow-up iteration:

1. keep the landed topic ledger as the source of truth and remove the remaining legacy `missing_topics` fallback where it still muddies the seam
2. make trust review provenance closure-complete, not just hash-bound or non-zero-ref
3. stop trust-mode evidence caps and renderer residue from undermining otherwise honest output
4. tighten trust acceptance semantics where the current defaults are too soft

## Current Repo Truth

### What already exists

The current branch already shipped the hard part of the first tranche:

| Surface | Evidence | What it now does |
|---|---|---|
| `anvil/harness/contracts.py` | `analysis_review_bounded_v1`, `analysis_review_trust_v1`, contract v5 | explicit bounded vs trust mode, one shared contract |
| `anvil/harness/runner.py` | payload normalization, issue ledger, downgrade causes, provenance binding | one unified execution path with trust-aware verdicting |
| `anvil/harness/semantic_validation.py` | trust-only checks for verified evidence subset, affected-file coverage, override reason | stricter trust validation |
| `anvil/harness/prompts.py` | contract-derived bounded/trust guidance | same payload family, mode-specific instructions |
| `anvil/harness/report.py` / `anvil/harness/reporting.py` | mode + provenance + downgrade cause rendering | trust mode explains caveats instead of hiding them |
| `tests/test_harness_*` | contract, prompt, runner, semantic validation coverage | regression rails for the split |

### What the last two successful runs still show

Two run artifacts on disk are the best evidence for what is still off:

- `.forge-harness-runs/20260419T015403Z-recommend_automation_improvements-16467fbd`
- `.forge-harness-runs/20260419T030446Z-recommend_automation_improvements-24d6b22b`

Observed repo truth from those artifacts:

- bounded run finished `accepted` with `semantic_warning_count = 2`
- bounded `FINAL_ANSWER.md` still leaked `none_reason:` bullets inside populated `Strengths` and `Uncertainties`
- trust run finished `accepted_with_warnings`, which is better and more honest
- trust provenance is `bound`, but the review-stage provenance record still shows `normalized_ref_count = 0` and `normalized_ref_field_count = 0`
- trust review surfaced `missing_topics` during the critic stage, but there is still no typed lifecycle proving how a missing topic was incorporated, waived, or intentionally left open

That is the whole game. The split shipped. The audit trail still needs one more pass.

## Step 0: Scope Challenge

### Recommended review mode

Use **SELECTIVE EXPANSION** logic for this iteration.

Reason:

- the branch already paid the cost of the public mode split
- the next highest-value work is inside the existing harness path, not a new subsystem
- there are real follow-up ideas worth capturing, but only a few belong in the immediate implementation slice

### Premises

These are the premises this plan accepts:

1. The current bounded/trust split is worth keeping. Reversing to one public mode would throw away useful user-facing semantics.
2. The next user-facing quality jump comes from stronger accounting and stronger review evidence, not from another prompt-only refinement pass.
3. Trust mode does not yet need a separate subgraph or a read-tracing platform project. That is an ocean, not this lake.
4. The current issue ledger model is strong enough to extend rather than replace.

### Dream state

```text
CURRENT
  explicit bounded/trust modes
  issue ledger
  payload-hash provenance
  warning-aware verdicts
  but topics can disappear and review evidence is weak

THIS ITERATION
  topic ledger
  review-stage structured refs
  trust-safe evidence budgeting
  renderer cleanup
  tighter trust downgrade semantics

12-MONTH IDEAL
  trust mode can explain every accepted claim with durable structured evidence,
  every raised concern has a visible lifecycle,
  and bounded vs trust differ in both honesty posture and audit depth
```

### Implementation alternatives

| Approach | Effort | Pros | Cons | Decision |
|---|---|---|---|---|
| Extend the current unified path with topic accounting plus closure-complete trust provenance | medium | minimal diff, preserves shipped split, directly fixes the observed trust hole, keeps one runner | still one engine, still not a separate attestation layer | recommended |
| Keep recommendation-level refs only and just make reports louder about their limits | low | smallest diff, easy to ship | prettier caveats, same proof gap for global issue/topic closure | reject |
| Add narrow issue/topic-scoped proof only where recommendation-level closure cannot work | medium | explicit fix for global closures, no new orchestrator, matches current failure mode exactly | adds new contract fields and more validation surface | accepted inside the recommended path |
| Recast trust as a pure audit/attestation layer over bounded output | high | cleaner product story long-term | bigger architecture move, new orchestration semantics, more docs churn | defer |
| Split bounded and trust into separate subgraphs/runners now | very high | strongest conceptual separation | duplicate logic, duplicate tests, unnecessary churn | reject |

### Complexity check

This iteration will touch more than eight files. That is acceptable only because it stays within one seam:

- contract/prompt/schema surface
- runner normalization and verdicting
- reporting/rendering
- tests/fixtures/docs

No new subsystem. No second runner. No new artifact family.

### Search check

- **[Layer 1]** Reuse the existing issue ledger, review payload family, provenance normalization, and summary/report surfaces.
- **[Layer 3]** Make trust more truthful by tightening lifecycle and evidence semantics, not by pretending prompt wording is proof.

Search was not needed beyond repo truth here. This is harness-specific policy work.

## CEO Review

### What problem is actually worth solving

The real product gap is not "make trust stricter." That already shipped.

The real gap is "make trust auditable enough that a human can follow why a concern was raised, what happened to it, and what evidence actually supports the final accepted draft."

More specifically, Slice B must close the exact hole the runner already knows about:

- recommendation-level review refs are real and useful
- repo-wide issue/topic closure is still provenance-incomplete when no concrete recommendation owns it
- `bound` is not the same thing as closure-complete

If this slice only increases ref counts, it will look better in artifacts and still fail the important human question: "what exactly proves that this concern was actually checked and closed?"

If you do not close that gap, trust mode risks feeling like a nicer warning banner over roughly the same engine. Users will notice.

### What already exists

Map each remaining sub-problem to the current code:

| Sub-problem | Existing surface to extend |
|---|---|
| reviewer concern lifecycle | `anvil/harness/runner.py` issue ledger and review summary assembly |
| topic lifecycle | `analysis_review_schema()` + review payload normalization + report rendering |
| review evidence provenance | `_normalize_analysis_review_payload()` and `_final_payload_provenance_records()` in `anvil/harness/runner.py` |
| trust evidence budgeting | `BoundedReviewPolicy` in `anvil/harness/contracts.py` and enforcement in `anvil/harness/semantic_validation.py` |
| user-facing cleanup | `_render_analysis_section()` path via `anvil/harness/report.py` and `anvil/harness/reporting.py` |
| trust acceptance policy | `_analysis_warning_causes()` and semantic warning handling in `anvil/harness/runner.py` |

### Strategic recommendation

Do not spend this iteration making bounded and trust search differently.

Do spend it making trust materially easier to audit after the fact. That increases user trust immediately, keeps the architecture boring, and leaves room for an attestation-layer design later if it still feels worth it.

The bar is not "more review refs." The bar is "closure-complete provenance for every trust-mode accept, caveat, carry-forward, or waiver."

### CLAUDE SUBAGENT (CEO, strategic independence)

- **Critical:** Slice B is pointed at "more review refs" when the real unsolved problem is global closure proof. Recommendation-level review refs are not sufficient for repo-wide issue/topic closure.
- **High:** The current acceptance bar is too weak. Non-zero structured refs can still leave provenance `insufficient`.
- **Medium:** The alternatives section skipped the important local fork: keep recommendation-scoped refs only, or add explicit issue/topic-scoped proof where recommendation linkage does not exist.

### CODEX SAYS (CEO, strategy challenge)

- **High:** The plan still argues from repo truth, not user truth. The immediate proxy metric therefore has to be a trust-mode behavior change a human can feel, not just cleaner internal counters.
- **High:** The split should not be protected as doctrine. This iteration only earns the split if trust mode becomes materially more dependable to inspect and act on.
- **Medium:** Internal acceptance bars like non-zero refs and passing pytest are not enough. The plan needs user-facing proxy outcomes such as lower audit burden and fewer ambiguous "accepted_with_warnings" cases caused by incomplete proof.

### CEO DUAL VOICES — CONSENSUS TABLE

```text
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   mixed    mixed   DISAGREE
  2. Right problem to solve?           no       no      CONFIRMED
  3. Scope calibration correct?        yes      mixed   DISAGREE
  4. Alternatives sufficiently explored? no     no      CONFIRMED
  5. Competitive/product risks covered? no      no      CONFIRMED
  6. 6-month trajectory sound?         mixed    mixed   DISAGREE
═══════════════════════════════════════════════════════════════
```

Read plainly:

- both outside voices agree the current Slice B framing is too weak
- both agree the missing local alternative is explicit issue/topic-scoped closure proof
- both agree the plan needs a user-facing proxy for "trust feels more dependable"
- they disagree on whether the current bounded/trust split is strategically settled or merely tolerated for now

### Dream-state delta

This iteration still does not make trust a separate attestation product.

It should make one visible difference to a human reviewer:

- before: trust mode can say a closure happened without proving the closure path for global issues/topics
- after: every trust-mode closure is either provenance-complete or explicitly marked incomplete with no room for a fake clean accept

### NOT in scope

- converting trust into a separate attestation pass over `BEST_DRAFT`
- hard read tracing or sandbox-proof file access
- a second analysis-review runner or subgraph
- provider retuning as the primary fix for auditability
- UI work, design-system work, or any frontend review pass

## Eng Review

### Architectural direction

Keep one analysis-review execution path.

Slice A already landed the topic ledger. The next architectural move is narrower:

1. keep the topic ledger as the canonical concern-lifecycle surface
2. add one explicit closure-proof surface for trust-mode global issue/topic classification

This is the least surprising architecture and the highest-leverage one.

### Target flow

```text
critic / auditor payload
    │
    ├── issues[]
    ├── recommendation_reviews[]
    ├── missing_topics[] or topic records
    └── review evidence refs
    │
    ▼
runner normalization
    ├── canonicalize review refs
    ├── assign topic IDs / statuses
    ├── bind payload hash + normalized refs
    └── attach topic ledger + review provenance
    │
    ▼
semantic validation
    ├── topic lifecycle completeness
    ├── review evidence subset / presence rules
    ├── trust coverage rules
    └── bounded vs trust evidence budget rules
    │
    ▼
verdict engine
    ├── downgrade on unresolved trust caveats
    ├── downgrade on semantic warnings
    ├── downgrade on inferred acceptance
    └── optionally treat late medium+ auditor findings more strictly
    │
    ▼
reporting
    ├── topic lifecycle summary
    ├── review provenance with closure-complete proof
    ├── clean strengths/uncertainties rendering
    └── explicit downgrade causes
```

### Priority 1: Stabilize the landed topic ledger and retire the legacy fallback

**Why it matters**

Right now the branch can already tell a coherent story about topics. The remaining risk is that the old `missing_topics` compatibility path and stale wording in the plan can make the seam look less settled than it is.

This is now cleanup and seam-hardening work, not a second topic-ledger project.

**Modules**

- `anvil/harness/schemas.py`
- `anvil/harness/runner.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/report.py`
- `anvil/harness/reporting.py`

**Changes**

- keep the typed topic record and runner-owned topic ledger as the only canonical lifecycle surface
- remove or tightly constrain the legacy `missing_topics` compatibility bridge once Slice B no longer depends on it
- preserve the current reviser/auditor classification requirements and reporting surfaces as stable inputs to Slice B
- treat any new topic work in this iteration as stabilization, cleanup, or regression protection only

**Acceptance**

- a topic raised by the critic still cannot silently disappear
- legacy compatibility does not create a second source of truth
- final artifacts still explain what happened to each prior topic

### Priority 2: Add structured review evidence to trust mode

**Why it matters**

The current trust run proves which review payload was accepted. It does not yet prove what structured evidence the review itself checked, and it still cannot prove repo-wide issue/topic closure when no concrete recommendation owns that closure.

That is why provenance can show `bound` while closure provenance is still `insufficient`.

**Modules**

- `anvil/harness/schemas.py`
- `anvil/harness/prompts.py`
- `anvil/harness/runner.py`
- `anvil/harness/semantic_validation.py`
- `docs/analysis_review_contract.md`

**Changes**

- extend critic/auditor/recommendation-review surfaces with explicit structured review refs:
  - `verified_evidence_refs`
  - `checked_files`
  - issue/topic-scoped closure proof for cases where recommendation-level closure cannot work
- normalize those refs in `_normalize_analysis_review_payload()`
- include normalized review refs in `_final_payload_provenance_records()`
- in trust mode, require provenance-complete closure coverage, not just non-zero refs, when the review makes concrete closure claims

**Acceptance**

- trust review provenance records show zero uncovered recommendation/global closures when the review closes issues or topics
- trust-mode review provenance ends `bound`, not `insufficient`, for closure-complete runs
- review-stage provenance is not merely hash-bound, it is evidence-bound enough to audit

### Priority 3: Separate display evidence from audit evidence

**Why it matters**

The current cap of 3 works for bounded readability. It is starting to distort trust-mode auditability.

The visible symptom is already in the trust run: recommendation 1 spans four workflows, but one file is trimmed from public evidence and has to be explained in prose.

**Modules**

- `anvil/harness/contracts.py`
- `anvil/harness/prompts.py`
- `anvil/harness/runner.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/report.py`
- `tests/fixtures/harness/analysis_review_semantic_cases.json`

**Changes**

- keep bounded public evidence at `1..3`
- introduce either:
  - trust-mode higher cap, or
  - dual fields such as `display_evidence_refs` and `audit_evidence_refs`
- keep report rendering concise, but preserve the fuller audit surface in artifacts and provenance

**Recommendation**

Prefer the split-field model:

- public markdown stays readable
- trust artifacts stay auditable
- bounded mode remains cheap and simple

**Acceptance**

- trust recommendations no longer need prose apologizing for trimmed evidence
- bounded mode remains readable
- semantic validation can distinguish "too much to show" from "not enough to prove"

### Priority 4: Clean renderer residue and tighten trust verdict semantics

**Why it matters**

Two things still look backward:

1. bounded deliverables leak `none_reason:` bullets into user-facing markdown
2. trust mode still treats `late_auditor_medium_or_higher_policy = warn` as acceptable default even though trust is the mode where late medium+ findings should hurt more, not less

**Modules**

- `anvil/harness/report.py`
- `anvil/harness/reporting.py`
- `anvil/harness/runner.py`
- `anvil/harness/contracts.py`
- `anvil/harness/semantic_validation.py`

**Changes**

- normalize section rendering:
  - if `items` is non-empty, suppress `none_reason`
  - if `items` is empty, allow `none_reason`
- revisit trust late-auditor policy:
  - likely move default from `warn` to `error`, or
  - at minimum make the downgrade explicit in top-level verdict logic
- keep `accept_with_caveat` and inferred-grounding downgrade behavior
- consider adding a trust-only rule that a high-priority mixed-grounding recommendation cannot end as plain `accept` without explicit justification

**Acceptance**

- no user-facing markdown contains schema residue like `none_reason:`
- trust mode is stricter on late medium+ review churn than bounded mode, or the soft policy is explicitly justified and surfaced

### Priority 5: Tests, fixtures, docs, and replay

**Modules**

- `tests/test_harness_analysis_contract.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`
- `tests/fixtures/harness/analysis_review_semantic_cases.json`
- `docs/analysis_review_contract.md`

**Changes**

- add topic-ledger fixtures and lifecycle validation tests
- add trust review evidence-ref tests
- add trust evidence-budget tests
- add renderer cleanup tests for strengths/uncertainties
- add trust late-auditor policy tests
- replay bounded and trust on the same task and compare:
  - verdict
  - downgrade causes
  - topic lifecycle output
  - review provenance ref counts

**Acceptance**

- the next replay proves a measurable difference from the current runs:
  - trust review provenance has non-zero refs
  - topic lifecycle is visible
  - bounded markdown is clean

## Error & Rescue Registry

| Failure | Where it happens | Rescue |
|---|---|---|
| critic raises a missing topic but later stages omit it | review payload lifecycle | topic ledger requires explicit resolved/carried/waived classification |
| trust review closes an issue without structured review proof | review provenance | require review evidence refs in trust mode and bind them |
| evidence cap hides a key file in trust mode | recommendation evidence budgeting | split public display refs from audit refs |
| user-facing markdown shows schema noise | report rendering | suppress `none_reason` when concrete items exist |
| late medium+ auditor issue gets papered over by a soft policy | verdict engine | tighten policy or downgrade verdict explicitly |

## Failure Modes Registry

| Surface | Real failure mode | Test planned | Release significance |
|---|---|---|---|
| topic ledger | topics still disappear silently through normalization or reporting gaps | yes | blocking |
| trust provenance | review-stage provenance remains `0 refs` after implementation | yes | blocking |
| evidence budget split | display/audit refs drift apart and contradict each other | yes | high |
| renderer cleanup | sanitized markdown diverges from JSON truth | yes | medium |
| trust late-auditor policy | stricter semantics create false negatives or excessive rejection | yes | medium |

## Test Review

### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] Topic lifecycle
    │
    ├── [GAP] critic introduces a topic record
    ├── [GAP] reviser maps topic into recommendation or waiver
    ├── [GAP] auditor classifies prior open topics
    └── [GAP] summary/report render final topic state

[+] Trust review provenance
    │
    ├── [GAP] review-stage refs normalize into provenance records
    ├── [GAP] trust mode rejects zero-ref review closure when refs are required
    └── [GAP] bounded mode still allows lightweight review payloads

[+] Evidence budgeting
    │
    ├── [GAP] bounded display cap remains 3
    ├── [GAP] trust audit refs can exceed display refs without contradiction
    └── [GAP] report rendering stays concise while audit artifact stays complete

[+] Renderer cleanup
    │
    ├── [GAP] strengths suppress none_reason when items exist
    └── [GAP] uncertainties suppress none_reason when items exist

[+] Trust acceptance semantics
    │
    ├── [GAP] late medium+ auditor findings trigger stricter handling
    ├── [GAP] high-priority mixed-grounding clean accepts are challenged
    └── [GAP] downgrade causes stay explicit in final report
```

### Required tests

1. `tests/test_harness_semantic_validation.py`
   Add topic lifecycle completeness, zero-ref trust review failure, and display-vs-audit evidence cases.

2. `tests/test_harness_runner.py`
   Add integration coverage for topic ledger carry-forward, trust provenance ref counts, and trust late-auditor verdict behavior.

3. `tests/test_harness_reporting.py`
   Assert cleaned strengths/uncertainties rendering and new topic lifecycle sections.

4. `tests/test_harness_prompt_consistency.py`
   Assert trust prompts require review evidence refs and bounded prompts stay lighter.

5. `tests/test_harness_selection.py`
   Assert partial-answer and draft-selection behavior stay correct when globally unresolved topics or globally proven closures are present.

6. `tests/fixtures/harness/analysis_review_semantic_cases.json`
   Add positive and negative topic/evidence-budget fixtures.

### Verification commands

```bash
poetry run pytest -q \
  tests/test_harness_analysis_contract.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
  tests/test_harness_selection.py \
  tests/test_harness_semantic_validation.py
```

## Performance Review

Keep the iteration honest about cost.

- do not add repo-wide rescans to fake stronger proof
- do not add a second review pass just to make the trust tier look serious
- do add metadata and lifecycle rigor that make the existing pass auditable

If this iteration starts to require a second orchestration graph, stop. That is the next project, not this one.

## Implementation Slices

| Slice | Modules | Goal | Depends on |
|---|---|---|---|
| A. Topic ledger | `schemas`, `runner`, `semantic_validation`, `prompts`, `report*` | make missing topics first-class tracked state | none |
| B. Closure-complete trust provenance | `schemas`, `runner`, `semantic_validation`, `prompts`, `docs`, `report*` | prove every trust-mode closure with recommendation-scoped or issue/topic-scoped structured evidence | none |
| C. Evidence budget split | `contracts`, `runner`, `semantic_validation`, `report`, fixtures | preserve readable display and fuller trust audit evidence | A, B |
| D. Renderer + verdict tightening | `report*`, `runner`, `contracts`, `semantic_validation` | clean markdown and tighten trust acceptance rules | A, B |
| E. Tests + replay | `tests`, `fixtures`, `docs` | prove the new semantics with one bounded/trust replay pair | A, B, C, D |

### Recommended order

Run **A** and **B** first.

Then land **C** and **D**.

Finish with **E**.

That is the minimum path that keeps the audit surface coherent while avoiding fake parallelism in `runner.py`.

### Implementation Slice A, fully implementable blueprint

#### Slice A objective

Replace `missing_topics: string[]` with a first-class topic lifecycle that survives critic, reviser, auditor, summary, and final-report rendering.

This slice exists to close the exact gap still visible in current code:

- `anvil/harness/schemas.py:357-393` still models topics as raw strings
- `anvil/harness/semantic_validation.py:384-393` only caps topic count, it does not enforce topic lifecycle coverage
- `anvil/harness/runner.py:1225-1258` only counts topic strings for review-stage stats
- `anvil/harness/runner.py:1368-1372` only emits the generic downgrade cause `reviewer missing_topics remain open`
- `anvil/harness/report.py` and `anvil/harness/reporting.py` expose review state, but they cannot explain what happened to each topic

That is why the plan needs a real topic ledger, not one more prompt nudge.

#### Step 0: Scope challenge

##### What already exists

Reuse the current issue-lifecycle pattern instead of inventing a parallel subsystem:

| Sub-problem | Existing code to extend | Why this is enough |
|---|---|---|
| stable review-stage classification | `anvil/harness/schemas.py`, `RECOMMENDATION_REVIEW_SCHEMA`, issue classification arrays in `analysis_review_schema()` | topic lifecycle can mirror the same contract shape |
| per-stage semantic enforcement | `anvil/harness/semantic_validation.py` | issue coverage checks already exist and can be mirrored for topics |
| cross-stage state and IDs | `anvil/harness/runner.py`, especially issue-ledger helpers near `_next_issue_id()`, `_open_issue_records()`, and `_serialized_issue_ledger()` | topic ledger can live beside issue ledger with the same in-memory lifecycle |
| run summary and review status rendering | `anvil/harness/report.py`, `anvil/harness/reporting.py` | reporting surfaces already know how to render review metadata and can add a topic section without a new artifact family |

##### Minimum change set

Do the smallest complete version:

1. add typed topic structures to the shared schema
2. normalize and persist topic records in the runner
3. enforce full topic classification in semantic validation
4. render topic lifecycle in summary/report/final markdown
5. add tests and fixtures for each lifecycle state

Do not add a new `topic_ledger.py`, a second runner, or a dedicated persistence layer. That is overbuilt for one seam.

##### Complexity check

Slice A is a legitimate multi-file change, but it is still one subsystem:

- primary code modules: `anvil/harness/schemas.py`, `anvil/harness/runner.py`, `anvil/harness/semantic_validation.py`, `anvil/harness/prompts.py`, `anvil/harness/report.py`, `anvil/harness/reporting.py`
- primary tests and fixtures: `tests/test_harness_runner.py`, `tests/test_harness_semantic_validation.py`, `tests/test_harness_prompt_consistency.py`, `tests/test_harness_reporting.py`, `tests/fixtures/harness/analysis_review_semantic_cases.json`

That is more than eight touched files once tests land. Accept it anyway, because the work stays inside the harness contract seam and does not introduce a new abstraction family.

##### Search check

- **[Layer 1]** Extend the existing issue-ledger and issue-resolution-map patterns.
- **[Layer 1]** Reuse the existing analysis-review schema family and summary/report artifacts.
- **[Layer 3]** Keep runner-owned lifecycle state in memory. Do not build a faux-general ledger framework for one payload family.

##### TODOS and completeness check

`TODOS.md` already captures the larger ocean items: attestation layer, stronger mode divergence, line-level refs, hard read tracing.

Slice A should boil the lake now:

- full lifecycle coverage for topics
- no silent drop path
- visible rendering in artifacts
- regression coverage from critic through final answer

##### Distribution check

No new user-distributed artifact type is introduced in Slice A. CI/publish changes are not part of this slice.

#### Architecture review

##### Decision

Model topics the same way issues are modeled today: explicit records plus explicit classification. Keep the canonical ledger in `HarnessRunner`.

##### Proposed contract shape

Add these structures to the shared analysis-review contract:

1. `ANALYSIS_TOPIC_SCHEMA` in `anvil/harness/schemas.py`
   Required fields:
   - `topic_id`
   - `title`
   - `severity`
   - `evidence`
   - `recommendation_index` nullable
   - `repair_hint`

2. `TOPIC_RESOLUTION_SCHEMA` in `anvil/harness/schemas.py`
   Required fields:
   - `topic_id`
   - `status` with `addressed | not_addressed | disagree`
   - `change_summary`
   - `residual_risk`

3. Review payload changes in `analysis_review_schema()`
   - replace `missing_topics` with `topics`
   - add `resolved_topic_ids`
   - add `carried_forward_topic_ids`
   - add `waived_topic_ids`

4. Analysis output changes in `analysis_output_schema()`
   - add `topic_resolution_map` when the reviser must respond to open topics

##### Normative semantics, no guesswork allowed

These rules are the source of truth for Slice A implementation. If code, prompts, or tests disagree, this section wins.

1. `topics[]` in critic/auditor review payloads means **new topics introduced by that stage only**.
   It is not the full set of all open topics. Historical open topics continue to live in the runner-owned topic ledger, just like open issues already live in the issue ledger.

2. `resolved_topic_ids[]`, `carried_forward_topic_ids[]`, and `waived_topic_ids[]` mean **classification of prior open topics only**.
   They must not contain IDs from the current stage's newly introduced `topics[]` array.

3. The stage-local review payload therefore has two topic surfaces:
   - `topics[]` = new topics raised now
   - topic classification arrays = what happened to previously open topics

4. The reviser does not emit `topics[]`.
   The reviser responds to prior open topics through `topic_resolution_map`, just as it already responds to prior open issues through `issue_resolution_map`.

5. `topic_id` ownership rules:
   - if a critic or auditor explicitly emits `topic_id`, preserve it after validation
   - if legacy `missing_topics[]` is normalized, the runner assigns stable IDs
   - once a `topic_id` enters the runner ledger, later stages must reuse that exact ID

##### Exact schema requirements

`ANALYSIS_TOPIC_SCHEMA` must require:

- `topic_id: string`
- `severity: low | medium | high | critical`
- `title: string`
- `evidence: string`
- `repair_hint: string`
- `recommendation_index: integer | null`

`TOPIC_RESOLUTION_SCHEMA` must require:

- `topic_id: string`
- `status: addressed | not_addressed | disagree`
- `change_summary: string`
- `residual_risk: string`
- `recommendation_index: integer | null`

The added `recommendation_index` on resolution entries is deliberate. It prevents hand-wavy "addressed somewhere" claims and lets the final ledger tie an addressed topic back to a concrete recommendation when one exists.

##### Backward-compat rule

Keep one compatibility bridge inside runner normalization for this branch only:

- accept legacy `missing_topics` from old fixtures or stale prompts
- normalize each string into a topic record with generated `topic_id`
- immediately rewrite prompts, schema fixtures, and tests to emit `topics`, not `missing_topics`

This avoids a flag day while still moving the repo to the explicit shape.

##### Reviser contract, explicit and required

When prior open topics exist, `analysis_output_schema()` must require `topic_resolution_map` exactly the same way it can already require `issue_resolution_map`.

Rules:

1. If prior open topics exist, `topic_resolution_map` is required.
2. If no prior open topics exist, `topic_resolution_map` is omitted entirely.
3. `topic_resolution_map` must contain exactly one entry per prior open topic ID.
4. No duplicates.
5. No unknown topic IDs.
6. No missing topic IDs.
7. If `status == addressed`, at least one of these must be true:
   - `recommendation_index` points at a valid current recommendation
   - `change_summary` explicitly explains a non-recommendation resolution

This is intentionally stricter than "add it when needed." The validator should be able to decide mechanically whether the reviser satisfied the contract.

##### Runner-owned canonical state

Add topic-ledger helpers in `anvil/harness/runner.py`, colocated with the existing issue-ledger helpers:

- `self.topic_ledger: list[dict[str, Any]]`
- `self._topic_ledger_by_id: dict[str, dict[str, Any]]`
- `_next_topic_id()` using `AT-001` style IDs
- `_open_topic_records()`
- `_serialized_topic_ledger()`
- `_merge_review_topics()` or equivalent helper that applies critic/auditor classifications into the canonical ledger

Do not generalize issue and topic handling into a shared meta-ledger unless the diff stays genuinely smaller. Explicit duplication beats a 200-line abstraction here.

##### Canonical topic ledger shape

The runner-owned topic ledger entries should use one stable shape from introduction through final rendering:

| Field | Meaning |
|---|---|
| `topic_id` | stable canonical ID, `AT-001` style |
| `title` | short human-readable topic |
| `severity` | current severity |
| `evidence` | original evidence string from the stage that introduced the topic |
| `recommendation_index` | nullable link to the related recommendation, if any |
| `introduced_by` | `critic` or `auditor` |
| `introduced_in_stage_index` | concrete stage index from `self.agent_stages` |
| `resolution_status` | `open | addressed | carried_forward | waived | disagree` |
| `resolution_note` | final user-visible explanation of what happened |
| `resolved_in_stage_index` | nullable stage index of the stage that last classified it |

`summary.json` must expose this exact structure as top-level `topic_ledger`.

`run_details` may also duplicate it if convenient, but `summary.json["topic_ledger"]` is the canonical artifact contract.

##### Data flow

```text
critic / auditor structured output
    │
    ├── topics[]
    ├── resolved_topic_ids[]
    ├── carried_forward_topic_ids[]
    └── waived_topic_ids[]
    │
    ▼
_normalize_analysis_review_payload()
    │
    ├── normalize legacy missing_topics -> topics[] during transition
    ├── assign / validate topic_id values
    └── bind topic refs into payload provenance
    │
    ▼
validate_analysis_review_payload()
    │
    ├── enforce critic topic cap
    ├── enforce prior open topic classification coverage
    └── reject duplicate / unknown / unclassified topic IDs
    │
    ▼
runner topic ledger
    │
    ├── persist introduced topics
    ├── carry open topics across rounds
    ├── apply reviser topic_resolution_map
    └── expose final open / addressed / waived topic state
    │
    ▼
summary.json / REPORT.md / FINAL_ANSWER.md
    │
    ├── topic lifecycle section
    ├── downgrade causes with concrete topic IDs
    └── visible carry-forward / waiver explanations
```

##### Architecture-specific failure scenario

Real production failure: the critic raises a topic, the reviser changes recommendation text, and the auditor accepts the result without ever reclassifying that topic. Today that can collapse into a generic warning. Slice A must make that a validation error or an explicit carried-forward topic, never a silent disappearance.

##### Final artifact contract

The reporting shape should be fixed, not left to taste.

`summary.json`

- add top-level `topic_ledger: list[topic-ledger-entry]`
- add `analysis_review_status.open_topic_ids`
- add `analysis_review_status.carried_forward_topic_ids`
- add `analysis_review_status.waived_topic_ids`

`REPORT.md`

- add a `## Topic Lifecycle` section with one row per ledger entry:

| Topic ID | Title | Severity | Introduced By | Status | Recommendation | Resolution Note |
|---|---|---|---|---|---|---|

`FINAL_ANSWER.md`

- do not dump the whole ledger
- add a compact `## Topic Lifecycle` section only when at least one topic exists
- each bullet must use this shape:
  - ``AT-001` `carried_forward` via `critic`: deployment rollback path still unspecified`
  - ``AT-002` `addressed`: covered by recommendation 2`

This split is intentional:

- `summary.json` carries the full machine-readable truth
- `REPORT.md` carries the full human-auditable truth
- `FINAL_ANSWER.md` carries the compact user-facing truth

#### Code quality review

##### Minimal-diff rules

- Keep all topic lifecycle behavior inside existing harness modules.
- Add small runner helpers near the issue-ledger helpers. Do not create a new service object just to move dictionaries around.
- Mirror the issue-lifecycle semantics where that reduces surprise.
- Avoid clever generic "ledger entity" abstractions unless they remove more code than they add.

##### Concrete implementation guidance

1. `anvil/harness/schemas.py`
   Add topic schemas next to `ANALYSIS_ISSUE_SCHEMA` and `ISSUE_RESOLUTION_SCHEMA`, not in a separate file.

2. `anvil/harness/prompts.py`
   Update critic, reviser, and auditor instructions to speak in topic records and topic classifications.
   The reviser prompt must explicitly require `topic_resolution_map` whenever open topics exist, the same way it already does for issue resolution.

3. `anvil/harness/semantic_validation.py`
   Add topic coverage checks parallel to the existing issue checks:
   - duplicate topic IDs
   - unknown topic IDs in classification arrays
   - missing prior-open-topic classifications
   - critic cap enforcement
   - `topic_resolution_map` coverage on reviser output

4. `anvil/harness/runner.py`
   Replace the current string-list handling in `_build_bounded_review_summary()` and `_analysis_warning_causes()` with topic-ledger-aware summaries and downgrade causes.

5. `anvil/harness/report.py` and `anvil/harness/reporting.py`
   Add a dedicated topic lifecycle section. Do not hide topic state inside generic warnings text.

##### NOT in scope for Slice A

- structured review evidence refs, that is Slice B
- display-vs-audit evidence split, that is Slice C
- `none_reason` cleanup and trust verdict tightening, that is Slice D
- replay comparisons and docs sweep beyond the topic contract updates, that is Slice E

#### Test review

##### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] Review payload schema + normalization
    │
    ├── [GAP] legacy missing_topics[] normalizes into topics[] with generated IDs
    ├── [GAP] critic topics[] payload preserves explicit topic_id values
    └── [GAP] duplicate topic_id values are rejected

[+] Reviser lifecycle closure
    │
    ├── [GAP] reviser topic_resolution_map covers every prior open topic
    ├── [GAP] missing topic_resolution_map entry fails semantic validation
    └── [GAP] addressed topic links back to recommendation_index or change_summary

[+] Auditor carry-forward logic
    │
    ├── [GAP] auditor classifies every prior open topic
    ├── [GAP] unknown topic IDs in resolved/carried/waived arrays fail
    └── [GAP] carried-forward topic remains visible in final status and downgrade causes

[+] Runner summary + final artifacts
    │
    ├── [GAP] summary.json includes topic_ledger with final statuses
    ├── [GAP] REPORT.md renders topic lifecycle table/section
    └── [GAP] FINAL_ANSWER.md surfaces open-topic caveats when acceptance is not clean

[+] Failure handling
    │
    ├── [GAP] critic topic cap still enforced after migration from strings to records
    ├── [GAP] stale prompt emitting missing_topics still passes through compatibility path
    └── [GAP] topic disappearance between critic and auditor becomes a hard failure
```

##### Required tests by file

1. `tests/test_harness_semantic_validation.py`
   Add topic classification coverage tests, duplicate-topic rejection, critic topic-cap tests, and reviser `topic_resolution_map` coverage tests.

2. `tests/test_harness_runner.py`
   Add end-to-end topic-ledger tests covering:
   - critic introduces topic
   - reviser addresses or declines it
   - auditor carries it forward or waives it
   - final `summary.json` and `analysis_review_status` expose the final state

3. `tests/test_harness_prompt_consistency.py`
   Assert critic and auditor prompts require `topics` and explicit topic classification arrays.
   Assert reviser prompts require `topic_resolution_map` when open topics exist.

4. `tests/test_harness_reporting.py`
   Assert `REPORT.md` and deliverable markdown show topic lifecycle clearly and do not collapse it into a generic one-line warning.

5. `tests/fixtures/harness/analysis_review_semantic_cases.json`
   Add:
   - valid topic lifecycle fixture
   - critic topic-cap overflow fixture
   - missing topic classification fixture
   - unknown topic ID fixture
   - legacy `missing_topics` compatibility fixture

##### Regression rule for Slice A

If any current bounded or trust replay loses a critic-raised topic after the Slice A diff, add a regression test immediately. That is the exact class of bug this slice exists to kill.

##### Verification commands for Slice A

```bash
poetry run pytest -q \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
  tests/test_harness_semantic_validation.py
```

#### Performance review

Keep the ledger cheap:

- store topic state in the existing runner process, not in a second artifact readback pass
- maintain `self._topic_ledger_by_id` for O(1) lookup during critic, reviser, and auditor classification
- only normalize refs and topic IDs for the current stage payload, not the entire run history

Slice A is metadata-heavy, not compute-heavy. If it starts scanning the workspace again just to justify topic state, the design is wrong.

#### Failure modes for Slice A

| Failure mode | Where it would show up | Required guard |
|---|---|---|
| topic IDs are regenerated across rounds and split one logical topic into two records | runner merge logic | `_topic_ledger_by_id` plus duplicate-ID validation |
| reviser omits one open topic and the plan still passes | semantic validation | require full `topic_resolution_map` coverage |
| auditor resolves a topic ID that never existed | semantic validation | reject unknown topic IDs in classification arrays |
| report renders only open topics and hides waived or addressed state | reporting | add explicit topic lifecycle rendering, not open-topic-only warnings |
| legacy `missing_topics` path silently bypasses the new ledger | normalization + tests | compatibility fixture plus explicit deprecation path |

If any one of these ends with no test, no error handling, and silent user-facing failure, treat Slice A as incomplete.

#### Worktree parallelization strategy for Slice A

##### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A1. Contract shape and prompt migration | `anvil/harness/schemas.py`, `anvil/harness/prompts.py` | — |
| A2. Runner topic ledger core | `anvil/harness/runner.py` | A1 |
| A3. Semantic validation for topic lifecycle | `anvil/harness/semantic_validation.py` | A1 |
| A4. Reporting and artifact rendering | `anvil/harness/report.py`, `anvil/harness/reporting.py` | A2, A3 |
| A5. Fixtures and tests | `tests/`, `tests/fixtures/harness/` | A1, A2, A3, A4 |

##### Parallel lanes

- Lane A: `A1`
  schema and prompt contract definition, sequential because both files define the payload family

- Lane B: `A2`
  runner ledger work, starts after A1

- Lane C: `A3`
  semantic-validation work, starts after A1 and can run in parallel with B because it only shares the field contract, not the module directory

- Lane D: `A4`
  reporting work, starts after B and C because it renders final ledger state

- Lane E: `A5`
  tests and fixtures, starts once A1-A4 have settled enough to avoid churn

##### Execution order

Launch `Lane B` and `Lane C` in parallel after `Lane A` lands.

Merge both.

Then run `Lane D`.

Finish with `Lane E` as the stabilizing pass that locks the contract and catches regressions.

##### Conflict flags

- `Lane B` and `Lane C` both depend on exact field names chosen in `Lane A`. Freeze the schema first or they will drift immediately.
- `Lane E` will touch fixture shapes used by both runner and semantic-validation tests. Keep it last unless the team wants to spend an afternoon re-resolving JSON conflicts.
- Do not split `anvil/harness/runner.py` across multiple worktrees for Slice A. That is fake parallelism and guaranteed merge pain.

#### Slice A exit criteria

Slice A is done only when all of these are true:

- topic strings no longer disappear without a typed lifecycle
- reviser and auditor must classify every prior open topic
- `summary.json`, `REPORT.md`, and final deliverables expose topic outcomes clearly
- downgrade causes cite concrete open topics, not just generic `missing_topics`
- the targeted pytest suite above passes

That is the bar for "fully implementable." Not just "we added a new array to the schema."

### Implementation Slice B, fully implementable blueprint

#### Slice B objective

Make trust-mode review provenance closure-complete.

This slice exists to close the exact gap still visible in current code:

- `anvil/harness/prompts.py` explicitly says recommendation-level review refs are necessary but not sufficient for global issue/topic closure in trust mode
- `anvil/harness/runner.py` already computes `uncovered_global_issue_ids` and `uncovered_global_topic_ids`
- `anvil/harness/semantic_validation.py` already knows how to fail trust-mode payloads whose closure proof is incomplete
- the current plan wording only asked for non-zero structured refs, which is weaker than the runtime's actual truth

That is the bug in the plan. Slice B must target closure-complete provenance, not prettier ref counts.

#### Step 0: Scope challenge

##### What already exists

Reuse the current trust-proof seam instead of inventing a second audit engine:

| Sub-problem | Existing code to extend | Why this is enough |
|---|---|---|
| recommendation-scoped review proof | `RECOMMENDATION_REVIEW_SCHEMA` in `anvil/harness/schemas.py` plus trust prompt language in `anvil/harness/prompts.py` | the payload family already knows how to carry review refs per recommendation |
| ref normalization and payload binding | `_normalize_analysis_review_payload()` and `_bind_normalized_payload()` in `anvil/harness/runner.py` | the runner already canonicalizes and hashes structured refs |
| closure coverage accounting | `_review_payload_ref_coverage()` in `anvil/harness/runner.py` | the runner already distinguishes covered recommendation closures from uncovered global closures |
| trust-mode failure semantics | `_validate_review_payload_provenance()` in `anvil/harness/semantic_validation.py` | semantic validation already rejects incomplete trust closure proof |
| trust reporting | `_final_payload_provenance_records()` in `anvil/harness/runner.py` plus `anvil/harness/report.py` | artifacts already render provenance status and can expose finer-grained closure proof |

##### Minimum change set

Do the smallest complete version:

1. keep recommendation-level proof exactly as the base case
2. add a narrow issue/topic-scoped proof surface for global closures
3. teach runner coverage to accept either proof path
4. render closure-complete vs incomplete provenance explicitly in artifacts
5. lock the whole thing with trust-mode regression tests

Do not add a new attestation runner, a second review pass, or a generic "proof framework." That is ocean behavior.

##### Complexity check

Slice B is another legitimate multi-file change, but it still stays in one seam:

- primary code modules: `anvil/harness/schemas.py`, `anvil/harness/prompts.py`, `anvil/harness/runner.py`, `anvil/harness/semantic_validation.py`, `anvil/harness/report.py`, `anvil/harness/reporting.py`, `anvil/harness/selection.py`
- primary docs/tests: `docs/analysis_review_contract.md`, `tests/test_harness_analysis_contract.py`, `tests/test_harness_prompt_consistency.py`, `tests/test_harness_runner.py`, `tests/test_harness_semantic_validation.py`, `tests/test_harness_reporting.py`, `tests/test_harness_selection.py`, `tests/fixtures/harness/analysis_review_semantic_cases.json`

That is acceptable because the work stays inside trust provenance semantics and avoids a new subsystem.

##### Search check

- **[Layer 1]** Reuse `recommendation_reviews[*].checked_files` and `recommendation_reviews[*].verified_evidence_refs` as the default proof path.
- **[Layer 1]** Reuse the runner's existing uncovered-closure accounting instead of inventing a second provenance calculator.
- **[Layer 3]** Add explicit issue/topic-scoped proof only where recommendation-scoped proof cannot work.

##### TODOS and completeness check

`TODOS.md` already carries the larger-ocean follow-ups:

- trust as an attestation layer over bounded output
- stronger proposer-strategy divergence between bounded and trust
- richer line-level refs
- hard read tracing

Slice B should boil the lake now:

- trust-mode recommendation closures stay recommendation-scoped
- trust-mode global issue/topic closures get explicit scoped proof
- artifacts distinguish closure-complete from merely hash-bound
- zero uncovered closures becomes the success bar

##### Distribution check

No new artifact family is introduced. Slice B only enriches the existing run summary, report, and final answer provenance surfaces.

#### Architecture review

##### Decision

Keep one runner, one payload family, and two proof paths:

1. recommendation-scoped proof for recommendation-owned closures
2. issue/topic-scoped proof for global closures

This is the smallest explicit fix for the real trust hole.

##### Proposed contract shape

Add these structures to the shared analysis-review contract:

1. `REVIEW_ISSUE_CLOSURE_SCHEMA` in `anvil/harness/schemas.py`
   Required fields:
   - `issue_id`
   - `checked_files`
   - `verified_evidence_refs`
   - `summary`

2. `REVIEW_TOPIC_CLOSURE_SCHEMA` in `anvil/harness/schemas.py`
   Required fields:
   - `topic_id`
   - `checked_files`
   - `verified_evidence_refs`
   - `summary`

3. `analysis_review_schema()` additions
   - `issue_closure_reviews`
   - `topic_closure_reviews`

4. `analysis_review_status.provenance` additions in the summary
   - `issue_closure_review_ref_count`
   - `topic_closure_review_ref_count`
   - `closure_complete_issue_ids`
   - `closure_complete_topic_ids`

The classification arrays remain the status truth. The new closure-review arrays carry proof, not status.

##### Normative semantics, no guesswork allowed

These rules are the source of truth for Slice B implementation. If code, prompts, docs, or tests disagree, this section wins.

1. `recommendation_reviews[*].checked_files` and `recommendation_reviews[*].verified_evidence_refs` remain the canonical proof surface for recommendation-level verdicts and closures.

2. If an issue or topic has a non-null `recommendation_index`, and that recommendation index is covered by recommendation-level review refs, no extra issue/topic-scoped closure proof is required.

3. If an issue or topic has a null `recommendation_index`, trust mode requires explicit issue/topic-scoped closure proof only when that issue or topic is being classified as resolved, carried forward, waived, or otherwise treated as a closed classification outcome.

4. `issue_closure_reviews[]` and `topic_closure_reviews[]` are the one canonical proof surface for global closure classification. They do not replace `resolved_*`, `carried_forward_*`, or `waived_*` arrays. They prove those classifications.

5. One scoped closure-review object must map to exactly one issue or topic ID.

6. Unknown IDs are invalid. Duplicate IDs are invalid. Missing required scoped proof for a global trust closure is invalid.

7. Trust-mode closure is provenance-complete only when:
   - every accepted or classified recommendation closure is recommendation-covered, and
   - every global issue/topic closure has explicit scoped proof, and
   - `uncovered_recommendation_indices`, `uncovered_global_issue_ids`, and `uncovered_global_topic_ids` are all empty

8. `bound` is not enough. A trust payload with a hash and some refs but remaining uncovered closures is `insufficient`.

9. Scoped closure proof is still review-attested metadata. Unless the closure-review `verified_evidence_refs` can be tied back to surfaced evidence, it is weaker than recommendation evidence and the report must say so plainly.

##### Exact schema requirements

`REVIEW_ISSUE_CLOSURE_SCHEMA` must require:

- `issue_id: string`
- `checked_files: string[]`
- `verified_evidence_refs: string[]`
- `summary: string`

`REVIEW_TOPIC_CLOSURE_SCHEMA` must require:

- `topic_id: string`
- `checked_files: string[]`
- `verified_evidence_refs: string[]`
- `summary: string`

Schema-level note:

- the arrays may be empty in bounded mode if the payload family stays shared
- trust-mode semantic validation is what makes the proof required when closure scope demands it
- closure-review `verified_evidence_refs` should be validated as a subset of the available surfaced evidence for that issue/topic when such evidence exists; otherwise the report must label the proof as review-attested rather than evidence-equivalent

##### Backward-compat rule

Do not introduce a second compatibility bridge for Slice B.

The current branch already has trust recommendation review refs. Slice B should extend that surface, not support a second stale shape indefinitely.

##### Runner-owned coverage semantics

Update `_review_payload_ref_coverage()` in `anvil/harness/runner.py` so that:

- recommendation-level proof still covers any issue/topic linked to a covered recommendation index
- global issue closure can become covered via `issue_closure_reviews[]`
- global topic closure can become covered via `topic_closure_reviews[]`
- final uncovered sets only contain IDs that truly lack both proof paths

The runner should also emit these proof counts in the final provenance record:

- recommendation-level ref counts
- issue-closure ref counts
- topic-closure ref counts
- total closure-complete issue/topic IDs

##### Data flow

```text
critic / auditor structured output
    │
    ├── recommendation_reviews[]
    ├── issues[] / topics[]
    ├── resolved_* / carried_forward_* / waived_* arrays
    └── issue_closure_reviews[] / topic_closure_reviews[] when needed
    │
    ▼
_normalize_analysis_review_payload()
    │
    ├── canonicalize recommendation-level refs
    ├── canonicalize issue/topic closure-review refs
    └── bind all normalized refs into one provenance record
    │
    ▼
_review_payload_ref_coverage()
    │
    ├── mark recommendation-owned closures as covered by recommendation reviews
    ├── mark global issue closures as covered by issue_closure_reviews
    └── mark global topic closures as covered by topic_closure_reviews
    │
    ▼
validate_analysis_review_payload()
    │
    ├── reject duplicate or unknown closure-review IDs
    ├── reject trust payloads with uncovered closures
    └── keep bounded mode lightweight
    │
    ▼
summary.json / REPORT.md / FINAL_ANSWER.md
    │
    ├── expose closure-complete vs insufficient provenance
    ├── show uncovered closure IDs when trust proof is incomplete
    └── show scoped-proof counts so ref inflation cannot fake success
```

##### Architecture-specific failure scenario

Real production failure: the auditor waives a global topic with `topic_id = TOPIC-004`, includes `files_reviewed`, and even binds the payload hash, but never attaches recommendation-scoped or topic-scoped structured proof. Today the runner can describe that as provenance-bound but closure-incomplete. Slice B must make that impossible to confuse with success.

##### Final artifact contract

The reporting shape should be fixed, not left to taste.

`summary.json`

- extend `analysis_review_status.provenance` with closure-review ref counts and uncovered closure IDs
- add `closure_proof_by_id` keyed by `issue_id` / `topic_id`, with:
  - proof path: `recommendation` or `scoped`
  - classification status
  - checked files
  - verified evidence refs
- expose whether the trust closure proof is `bound` or `insufficient`
- keep the final uncovered sets machine-readable

`REPORT.md`

- add a `## Review Provenance` subsection that distinguishes:
  - recommendation review refs
  - issue closure review refs
  - topic closure review refs
  - uncovered closures, if any
- add a per-ID table mapping each classified global issue/topic to its proof path and refs

`FINAL_ANSWER.md`

- do not dump raw provenance records
- when trust mode is not clean, add a compact note that names uncovered issue/topic IDs and the reason the closure proof is incomplete

This split is intentional:

- `summary.json` carries the machine-readable proof contract
- `REPORT.md` carries the full auditable explanation
- `FINAL_ANSWER.md` carries only the user-facing consequence

#### Code quality review

##### Minimal-diff rules

- Keep all new proof handling inside the existing trust-review path.
- Add targeted closure-review schemas instead of a generic proof abstraction.
- Reuse the current uncovered-closure accounting instead of branching the provenance engine.
- Prefer explicit `issue_closure_reviews` and `topic_closure_reviews` arrays over a polymorphic mixed-type proof list.

##### Concrete implementation guidance

1. `anvil/harness/schemas.py`
   Add the two closure-review schemas next to the other review-stage schemas and wire them into `analysis_review_schema()`.

2. `anvil/harness/prompts.py`
   Update critic and auditor prompts so they explicitly say:
   - recommendation-level refs are the default proof path
   - global issue/topic closures require explicit scoped proof in trust mode
   - `files_reviewed` alone is context, not closure proof
   - scoped closure proof may still be weaker than recommendation evidence unless `verified_evidence_refs` ties back to surfaced evidence

3. `anvil/harness/runner.py`
   Normalize `issue_closure_reviews` and `topic_closure_reviews` exactly the same way recommendation review refs are normalized today.

4. `anvil/harness/semantic_validation.py`
   Add coverage checks for:
   - duplicate closure-review IDs
   - unknown issue/topic IDs in closure-review arrays
   - missing scoped proof for global trust closures
   - closure-review refs that are not subsets of `files_reviewed`
   - closure-review `verified_evidence_refs` that overclaim beyond surfaced evidence when surfaced evidence exists

5. `anvil/harness/selection.py`
   Explicitly define how global closure proof interacts with best-draft ranking and partial-answer eligibility so unowned but proven closures do not silently skew accepted subsets.

6. `anvil/harness/report.py` and `anvil/harness/reporting.py`
   Render trust provenance in a way that makes `insufficient` unmistakable, names the uncovered closures directly, and shows proof-path-by-ID for classified global issues/topics.

6. `docs/analysis_review_contract.md`
   Replace the current “global issues/topics remain provenance-incomplete” language with the post-Slice-B rule:
   - global closures are allowed only when scoped proof is present
   - otherwise the payload is closure-incomplete and trust mode cannot claim a clean closure

##### NOT in scope for Slice B

- attestation-layer redesign
- line-level or excerpt-level provenance
- hard read tracing
- bounded-mode UI work or workflow changes
- changing proposer search strategy

#### Test review

##### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] Recommendation-owned closure proof
    │
    ├── [GAP] recommendation-linked issue closure stays covered by recommendation_reviews refs
    ├── [GAP] recommendation-linked topic closure stays covered by recommendation_reviews refs
    └── [GAP] bounded mode still accepts lightweight review payloads

[+] Global closure proof
    │
    ├── [GAP] global issue closure becomes covered by issue_closure_reviews
    ├── [GAP] global topic closure becomes covered by topic_closure_reviews
    └── [GAP] missing scoped proof leaves trust provenance insufficient

[+] Ref normalization and binding
    │
    ├── [GAP] issue/topic closure-review refs normalize to workspace paths
    ├── [GAP] closure-review refs are counted in final provenance records
    └── [GAP] files_reviewed-only payload cannot fake closure completeness

[+] Reporting
    │
    ├── [GAP] report shows recommendation vs issue/topic scoped proof counts separately
    ├── [GAP] final answer only surfaces user-facing provenance consequences
    └── [GAP] uncovered closure IDs are rendered when trust proof is incomplete

[+] Selection and partial artifacts
    │
    ├── [GAP] globally proven closures do not accidentally block partial acceptance when they are truly closure-complete
    ├── [GAP] globally unproven closures still block clean partial artifacts
    └── [GAP] best-draft selection does not prefer a payload that only inflated scoped proof counts
```

##### Required tests by file

1. `tests/test_harness_runner.py`
   Add end-to-end coverage for:
   - global issue closure proven by `issue_closure_reviews`
   - global topic closure proven by `topic_closure_reviews`
   - incomplete global closure staying `insufficient`
   - recommendation-linked closure still working without extra scoped proof

2. `tests/test_harness_semantic_validation.py`
   Add validation coverage for:
   - duplicate closure-review IDs
   - unknown IDs
   - closure-review refs outside `files_reviewed`
   - trust payloads that classify global closures without scoped proof

3. `tests/test_harness_prompt_consistency.py`
   Assert critic and auditor prompts explain both proof paths clearly and keep `files_reviewed` framed as context rather than proof.

4. `tests/test_harness_reporting.py`
   Assert the report distinguishes recommendation proof from issue/topic closure proof and that `insufficient` provenance names uncovered IDs.

5. `tests/test_harness_analysis_contract.py`
   Assert the contract docs/defaults describe closure-complete provenance correctly.

6. `tests/test_harness_selection.py`
   Add selection and partial-answer coverage for globally proven vs globally unproven closures.

7. `tests/fixtures/harness/analysis_review_semantic_cases.json`
   Add:
   - valid global issue closure proof
   - valid global topic closure proof
   - missing scoped proof failure
   - duplicate closure-review ID failure

##### Verification commands for Slice B

```bash
poetry run pytest -q \
  tests/test_harness_analysis_contract.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
  tests/test_harness_selection.py \
  tests/test_harness_semantic_validation.py
```

#### Performance review

Keep the proof path cheap:

- no extra workspace scan
- no second model pass
- no recomputation of historical artifacts
- normalize only the current stage's closure-review refs

If Slice B starts paying latency by doing more reading rather than carrying better proof metadata, the design is wrong.

#### Failure modes for Slice B

| Failure mode | Where it would show up | Required guard |
|---|---|---|
| a global trust closure still looks successful with only `files_reviewed` | semantic validation + reporting | fail trust validation and surface `insufficient` provenance |
| recommendation-linked closures incorrectly require scoped proof too | runner coverage logic | accept recommendation-level coverage as sufficient when `recommendation_index` is present |
| duplicate closure-review objects silently override each other | semantic validation | reject duplicate `issue_id` / `topic_id` inside closure-review arrays |
| closure-review refs drift outside `files_reviewed` | semantic validation | require closure-review refs to stay subsets of `files_reviewed` |
| report collapses recommendation proof and global proof into one opaque count | reporting | render separate counts and uncovered IDs |
| globally proven closures accidentally skew partial-answer or best-draft behavior | selection + partial artifact logic | add explicit selection tests for proven vs unproven global closures |

If any one of these ends with silent user-facing ambiguity, Slice B is incomplete.

#### Worktree parallelization strategy for Slice B

##### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| B1. Contract and prompt shape | `anvil/harness/schemas.py`, `anvil/harness/prompts.py`, `docs/analysis_review_contract.md` | — |
| B2. Runner closure-proof coverage | `anvil/harness/runner.py` | B1 |
| B3. Semantic validation | `anvil/harness/semantic_validation.py` | B1 |
| B4. Reporting | `anvil/harness/report.py`, `anvil/harness/reporting.py` | B2, B3 |
| B5. Fixtures and tests | `tests/`, `tests/fixtures/harness/` | B1, B2, B3, B4 |

##### Parallel lanes

- Lane A: `B1`
  Freeze the contract first. Everything else depends on field names and proof semantics.

- Lane B: `B2`
  Runner coverage and provenance counts, starts after B1.

- Lane C: `B3`
  Validation logic, starts after B1 and can run in parallel with B2.

- Lane D: `B4`
  Reporting, starts after B2 and B3 so the rendered semantics match the real proof semantics.

- Lane E: `B5`
  Tests and fixtures, last, because they touch every shape that is still moving upstream.

##### Conflict flags

- Do not split `anvil/harness/runner.py` across multiple worktrees for Slice B.
- Freeze the closure-review field names before validation and tests branch off.
- Keep docs in B1, not B5, or the repo will temporarily describe stale provenance semantics.

#### Slice B exit criteria

Slice B is done only when all of these are true:

- trust-mode global issue/topic closures can no longer fake success with `files_reviewed` alone
- recommendation-linked closures still work with recommendation-level proof only
- trust provenance is judged by zero uncovered closures, not non-zero ref counts
- `summary.json` and `REPORT.md` expose scoped-proof counts and uncovered closure IDs explicitly
- the targeted pytest suite above passes

That is the bar for "closure-complete provenance." Not just "we added more refs."

### CLAUDE SUBAGENT (eng, independent review)

- **Critical:** The first Slice B draft accidentally defined two proof shapes for global items. Keep one canonical proof surface, `issue_closure_reviews[]` / `topic_closure_reviews[]`, and require it only for closure/classification transitions.
- **High:** Scoped closure proof is still self-attested unless the plan either ties `verified_evidence_refs` back to surfaced evidence or labels the proof as weaker than recommendation evidence.
- **Medium:** Reporting needs a per-ID proof map, not just counts, or humans will still reconstruct closure proof by hand.

### CODEX SAYS (eng, architecture challenge)

- **High:** The plan was still phrased like topic accounting needed to be added, even though most of that work already landed. The actual delta is cleanup plus closure-proof semantics.
- **High:** Global closure proof affects selection and partial artifacts, not just provenance reporting. The plan must say so explicitly.
- **High:** Any display-vs-audit split needs one canonical truth source or the contract will fork itself.
- **Medium:** Tightening late-auditor policy changes the product from caveated acceptance to failure; that choice needs an explicit user-facing outcome.

### ENG DUAL VOICES — CONSENSUS TABLE

```text
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               mixed    mixed   CONFIRMED
  2. Test coverage sufficient?         no       no      CONFIRMED
  3. Performance risks addressed?      mixed    mixed   DISAGREE
  4. Security/trust boundary covered?  no       no      CONFIRMED
  5. Error paths handled?              no       no      CONFIRMED
  6. Deployment risk manageable?       mixed    mixed   DISAGREE
═══════════════════════════════════════════════════════════════
```

Read plainly:

- both engineering voices agree the one-runner direction is still right
- both agree the contract needed one more pass to avoid a second proof surface for global closures
- both agree selection, partial artifacts, and reporting need to participate in the Slice B truth model
- they differ on how much performance and ship-risk this adds, but neither thinks it justifies a new subsystem

### Eng completion summary

The engineering review lands on one clear implementation stance:

- stabilize the already-landed Slice A seam instead of reopening it
- make Slice B about one canonical global-closure proof model
- thread that model through provenance, selection, partial artifacts, validation, and reporting
- judge success by zero uncovered closures plus explicit proof-path rendering, not by raw ref counts

## Cross-Phase Themes

Three themes showed up everywhere:

1. **Lifecycle honesty beats raw strictness.**
   The biggest remaining gap is not another cap or another warning. It is incomplete accounting for what happened to concerns.

2. **Trust needs closure-complete proof, not just more refs.**
   The current trust run already binds payloads and recommendation review refs. The missing seam is explicit proof for global closure states.

3. **One canonical truth surface beats almost-right duplication.**
   This showed up in both phases: do not rebuild Slice A, do not invent a second topic truth, and do not let global closure proof fork into multiple competing surfaces.

## Deferred to TODOS.md

Items intentionally deferred out of this iteration:

- trust as a dedicated attestation layer over bounded output
- stronger operational divergence between bounded/trust proposer strategy
- removing no-op trust boilerplate from bounded prompts
- richer line-level review refs instead of path-level refs only
- hard reviewer read tracing / sandbox-backed proof

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Keep the bounded/trust split and plan a follow-up iteration instead of reopening the split | mechanical | P3 pragmatic | The split is already in code and the run artifacts show the remaining problems are post-split auditability gaps | reverting to one public mode |
| 2 | CEO | Use selective expansion logic for the next iteration | taste | P2 boil lakes | The branch needs one more complete auditability pass, but not every idea belongs in the immediate slice | scope expansion, scope reduction |
| 3 | CEO | Treat Slice A as landed and keep only cleanup/stabilization work in scope | mechanical | P3 pragmatic | Rebuilding topic accounting would duplicate code that already exists on this branch | a second topic-ledger implementation push |
| 4 | CEO | Reframe Slice B around closure-complete provenance instead of non-zero refs | mechanical | P1 completeness | Both outside voices agreed the real gap is global closure proof, not raw ref counts | report-only hardening |
| 5 | CEO | Add a user-facing proxy outcome for trust-mode dependability | taste | P6 bias toward action | Internal counters are not enough to judge whether trust mode became more usable | purely internal success metrics |
| 6 | Eng | Use one canonical global-closure proof surface, `issue_closure_reviews[]` / `topic_closure_reviews[]` | mechanical | P5 explicit over clever | Two competing proof paths for global closures would recreate the ambiguity this slice is supposed to remove | mixed per-record and per-array proof shapes |
| 7 | Eng | Thread Slice B semantics into selection and partial artifacts | mechanical | P1 completeness | Proven global closures and unproven global closures already affect accepted subsets and best-draft behavior | provenance-only implementation |
| 8 | Eng | Keep display-vs-audit evidence split tentative until a single canonical truth source is named | taste | P3 pragmatic | The repo already has multiple evidence-related invariants; a sloppy split would fork the contract | blind cap increase or dual truth sources |
| 9 | Eng | Defer attestation-layer redesign to backlog | mechanical | P2 boil lakes | It is still a valid next move, but it is larger than this branch needs right now | doing the architecture rewrite in this iteration |
| 10 | Eng | Skip design review | mechanical | P3 pragmatic | This plan has no UI scope and the affected files are harness/runtime/docs/test surfaces only | forcing a design pass with no UI changes |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | Slice B had to be reframed from “more refs” to closure-complete provenance, with a user-facing trust outcome instead of raw internal counters |
| Codex Review | `codex review` | Independent 2nd opinion | 2 | issues_open | Codex flagged stale Slice A framing, internal-only success metrics, and missing selection/partial-artifact implications for global closure proof |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | The canonical global-closure proof model is now specified, but evidence-split and late-auditor behavior still need final implementation choices |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No UI scope detected in `PLAN.md`, `anvil/harness/*`, or the run artifacts |

**VERDICT:** PLAN UPDATED FOR NEXT ITERATION. Highest-priority work is closure-complete trust provenance on top of the landed topic ledger. Optional longer-horizon ideas are captured in `TODOS.md`.
