<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260422-192048.md -->

# Next Iteration Plan: Trust Recommendation Admissibility and Artifact Promotion

## Purpose

Slices B and C landed. That matters.

`analysis_review_trust_v1` now has uncapped recommendation evidence, closure-complete global proof, honest trust publishability gating, compact markdown projections, and explicit artifact pointers. The old slice map in this file is therefore partly historical. It still preserves the Slice A / Slice B review work and the now-landed Slice C blueprint, but it is no longer the active next-slice recommendation.

The active next slice is narrower and more product-visible:

1. stop treating caveated or inference-backed trust recommendations as silently shippable `FINAL_ANSWER.*` content
2. freeze one runner-owned admissibility matrix for `FINAL_ANSWER.*` versus `PARTIAL_ANSWER.*` versus `BEST_DRAFT.*`
3. keep the contract boring: no new model-authored payload family, no second runner, no silent filtering of `FINAL_ANSWER.*`

## Current Repo Truth

### What already exists

The current branch already shipped the hard part:

| Surface | Evidence | What it now does |
|---|---|---|
| `anvil/harness/contracts.py` | `analysis_review_v1_contract_v6` | explicit bounded vs trust mode, trust recommendation evidence uncapped, trust policy rendered from one contract |
| `anvil/harness/runner.py` | topic ledger, closure proof, downgrade causes, publishability, inferred-grounding rollups | one execution path with trust-aware provenance, publish blockers, and partial gating |
| `anvil/harness/semantic_validation.py` | scoped closure proof rules, trust-only subset checks, affected-file coverage, late-auditor overflow warnings | Slice B proof semantics enforced, with remaining trust strictness decisions still policy-shaped |
| `anvil/harness/report.py` / `anvil/harness/reporting.py` | review provenance sections, artifact pointers, compact previews, cleaned section rendering | trust mode explains caveats, blocks non-publishable finals, and no longer leaks `none_reason:` noise |
| `tests/test_harness_*` | runner, reporting, semantic validation, contract coverage | Slice B and Slice C behavior are guarded end-to-end |

### What changed since the last autoplan pass

- trust recommendation evidence is now uncapped in `contracts.py`, preserved in `runner.py`, and covered in `tests/test_harness_runner.py`
- closure proof is now counted through `closure_proof_by_id` plus uncovered recommendation / issue / topic sets
- trust-mode final publication is now gated through `analysis_review_status.publishability`
- markdown artifacts now use compact preview rendering while JSON stays full-fidelity
- the old note that Slice C should still be the active next slice is stale as written

### Active planning question

The remaining gap is not "can trust withhold `FINAL_ANSWER.*`." That landed. The remaining gap is what trust is allowed to promote into `FINAL_ANSWER.*`, when the harness must demote to `PARTIAL_ANSWER.*`, and how to do that without inventing a second payload family or silently filtering the final artifact.

Historical Slice A / Slice B review material remains below for provenance. The landed Slice C blueprint remains below for implementation history. The active Slice D blueprint is appended after the Slice C resolution section.

## Historical Slice B Review Context

The next sections preserve the prior Slice B `autoplan` output so the rationale for the landed closure-proof work stays in one file. They are still useful context, but they are not the active next-slice recommendation anymore.

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

Make trust-mode review provenance closure-complete for global issue and topic classifications.

This slice does exactly one thing: it closes the current trust hole where a payload can be hash-bound and still lack proof for global closure outcomes. It does **not** reopen Slice A topic accounting, redesign trust as a second engine, or bundle unrelated renderer or policy cleanups into the same diff.

If two separate agents implement Slice B from this plan, they should touch the same files, add the same contract fields, enforce the same validation rules, and land the same test matrix.

#### Step 0: Scope challenge

##### What already exists

Reuse the current trust-proof seam instead of inventing a second audit engine:

| Sub-problem | Existing code to extend | Why this is enough |
|---|---|---|
| recommendation-scoped review proof | `RECOMMENDATION_REVIEW_SCHEMA` in `anvil/harness/schemas.py` plus trust prompt language in `anvil/harness/prompts.py` | the payload family already knows how to carry review refs per recommendation |
| ref normalization and payload binding | `_normalize_analysis_review_payload()` and `_bind_normalized_payload()` in `anvil/harness/runner.py` | the runner already canonicalizes and hashes structured refs |
| closure coverage accounting | `_review_payload_ref_coverage()` in `anvil/harness/runner.py` | the runner already distinguishes covered recommendation closures from uncovered global closures |
| trust-mode failure semantics | `_validate_review_payload_provenance()` in `anvil/harness/semantic_validation.py` | semantic validation already rejects incomplete trust closure proof |
| selection and partial artifacts | `anvil/harness/selection.py` plus existing partial-artifact gating in `anvil/harness/runner.py` | globally proven versus unproven closures already influence which payloads can be treated as clean |
| trust reporting | `_final_payload_provenance_records()` in `anvil/harness/runner.py` plus `anvil/harness/report.py` and `anvil/harness/reporting.py` | artifacts already render provenance status and can expose finer-grained closure proof |

##### Minimum change set

Do the smallest complete version:

1. keep recommendation-level proof exactly as the base case
2. add one issue-scoped proof surface and one topic-scoped proof surface for global closures
3. teach runner coverage and selection logic to accept either proof path
4. render closure-complete versus incomplete provenance explicitly in artifacts
5. lock the behavior with runner, validation, reporting, selection, prompt, and contract tests

Do not add a new attestation runner, a second review pass, or a generic proof framework.

##### Scope lock

Slice B is intentionally **not** the place to decide:

- trust display-vs-audit evidence cap splitting
- renderer cleanup outside trust provenance surfaces
- late-auditor severity policy changes
- proposer-strategy divergence between bounded and trust
- line-level provenance or hard read tracing

Those items stay in the surrounding plan and `TODOS.md`. Slice B is only the closure-proof slice.

##### Complexity check

Slice B is a legitimate multi-file change, but it still stays inside one seam:

- primary code modules: `anvil/harness/schemas.py`, `anvil/harness/prompts.py`, `anvil/harness/runner.py`, `anvil/harness/semantic_validation.py`, `anvil/harness/report.py`, `anvil/harness/reporting.py`, `anvil/harness/selection.py`
- primary docs/tests: `docs/analysis_review_contract.md`, `tests/test_harness_analysis_contract.py`, `tests/test_harness_prompt_consistency.py`, `tests/test_harness_runner.py`, `tests/test_harness_semantic_validation.py`, `tests/test_harness_reporting.py`, `tests/test_harness_selection.py`, `tests/fixtures/harness/analysis_review_semantic_cases.json`

That breadth is acceptable because the work remains one explicit semantic change, global closure proof completeness.

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
- selection and partial artifacts respect that proof state
- artifacts distinguish closure-complete from merely hash-bound
- zero uncovered closures becomes the success bar

##### Distribution check

No new artifact family is introduced. Slice B only enriches the existing run summary, report, and final answer provenance surfaces.

#### Architecture review

##### Decision

Keep one runner, one payload family, and exactly two proof paths:

1. recommendation-scoped proof for recommendation-owned closures
2. issue/topic-scoped proof for global closures

No third proof path is allowed. No fallback proof shape is allowed. The classification arrays remain status truth. The new scoped-review arrays carry proof only.

##### Canonical implementation contract

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
   - `uncovered_global_issue_ids`
   - `uncovered_global_topic_ids`

5. `summary.json` addition
   - `closure_proof_by_id`

##### Normative semantics, no guesswork allowed

These rules are the source of truth for Slice B implementation. If code, prompts, docs, or tests disagree, this section wins.

1. `recommendation_reviews[*].checked_files` and `recommendation_reviews[*].verified_evidence_refs` remain the canonical proof surface for recommendation-level verdicts and closures.

2. If an issue or topic has a non-null `recommendation_index`, and that recommendation index is covered by recommendation-level review refs, no extra issue/topic-scoped closure proof is required.

3. If an issue or topic has a null `recommendation_index`, trust mode requires explicit issue/topic-scoped closure proof only when that issue or topic is being classified as resolved, carried forward, waived, or otherwise treated as a closed classification outcome.

4. `issue_closure_reviews[]` and `topic_closure_reviews[]` are the one canonical proof surface for global closure classification. They do not replace `resolved_*`, `carried_forward_*`, or `waived_*` arrays. They prove those classifications.

5. One scoped closure-review object must map to exactly one issue or topic ID.

6. Unknown IDs are invalid. Duplicate IDs are invalid. Missing required scoped proof for a global trust closure is invalid.

7. Trust-mode closure is provenance-complete only when all of these are true:
   - every accepted or classified recommendation closure is recommendation-covered
   - every global issue closure has explicit scoped proof
   - every global topic closure has explicit scoped proof
   - `uncovered_recommendation_indices`, `uncovered_global_issue_ids`, and `uncovered_global_topic_ids` are all empty

8. `bound` is not enough. A trust payload with a hash and some refs but any remaining uncovered closures is `insufficient`.

9. Scoped closure proof is still review-attested metadata. If a closure-review `verified_evidence_refs` cannot be tied back to surfaced evidence for that issue or topic, the proof is valid for closure accounting but must be labeled weaker than recommendation evidence in reporting.

10. Slice B does not change bounded-mode requirements. The new arrays may remain empty in bounded mode.

##### File-by-file implementation contract

| File | Required change | Notes |
|---|---|---|
| `anvil/harness/schemas.py` | add `REVIEW_ISSUE_CLOSURE_SCHEMA`, `REVIEW_TOPIC_CLOSURE_SCHEMA`, wire `issue_closure_reviews` and `topic_closure_reviews` into `analysis_review_schema()` | no generic proof union |
| `anvil/harness/prompts.py` | update critic and auditor instructions to require scoped proof for trust-mode global closures and to state that `files_reviewed` is context, not proof | wording must mirror the normative rules above |
| `anvil/harness/runner.py` | normalize both new arrays, count their refs, compute coverage through `_review_payload_ref_coverage()`, and emit per-ID closure proof records | this remains the canonical provenance calculator |
| `anvil/harness/semantic_validation.py` | reject duplicate IDs, unknown IDs, missing scoped proof for classified global closures, refs outside `checked_files`, and overclaimed evidence refs when surfaced evidence exists | bounded mode stays lightweight |
| `anvil/harness/selection.py` | make clean trust selection and partial-artifact eligibility depend on closure completeness, not raw ref counts | proven global closures can pass, unproven ones cannot |
| `anvil/harness/report.py` | expose proof counts, uncovered IDs, and user-facing consequence text for `insufficient` trust provenance | no raw provenance blob dump in final answer |
| `anvil/harness/reporting.py` | render per-ID proof-path rows for globally classified issues and topics | `recommendation` versus `scoped` must stay visible |
| `docs/analysis_review_contract.md` | update contract docs to describe scoped proof as the rule for global trust closures | remove stale “global closures remain provenance-incomplete” wording |
| `tests/test_harness_analysis_contract.py` | assert contract shape and docs match the new closure-proof model | contract drift guard |
| `tests/test_harness_prompt_consistency.py` | assert both proof paths are explained consistently in prompts | prompt drift guard |
| `tests/test_harness_runner.py` | cover normalization, coverage accounting, and provenance record emission | main behavior guard |
| `tests/test_harness_semantic_validation.py` | cover invalid ID, duplicate ID, missing proof, and subset validation failures | trust failure guard |
| `tests/test_harness_reporting.py` | cover separated proof counts, uncovered IDs, and per-ID proof-path rendering | user-visible audit guard |
| `tests/test_harness_selection.py` | cover clean selection and partial-artifact behavior for proven versus unproven global closures | downstream behavior guard |
| `tests/fixtures/harness/analysis_review_semantic_cases.json` | add valid and invalid closure-proof fixtures | shared fixture source |

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
    ├── canonicalize issue closure-review refs
    ├── canonicalize topic closure-review refs
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
selection / partial-artifact gating
    │
    ├── allow clean trust selection only when closure proof is complete
    └── block clean partial artifacts when uncovered global closures remain
    │
    ▼
summary.json / REPORT.md / FINAL_ANSWER.md
    │
    ├── expose closure-complete versus insufficient provenance
    ├── show uncovered closure IDs when trust proof is incomplete
    └── show proof path by ID so ref inflation cannot fake success
```

##### Architecture-specific failure scenario

Real production failure: the auditor waives a global topic with `topic_id = TOPIC-004`, includes `files_reviewed`, and even binds the payload hash, but never attaches recommendation-scoped or topic-scoped structured proof. Today the runner can describe that as provenance-bound but closure-incomplete. Slice B must make that impossible to confuse with success.

##### Final artifact contract

The reporting shape is fixed, not left to taste.

`summary.json`

- extend `analysis_review_status.provenance` with closure-review ref counts and uncovered closure IDs
- add `closure_proof_by_id`, keyed by `issue_id` or `topic_id`, with:
  - `proof_path`: `recommendation` or `scoped`
  - `classification_status`
  - `checked_files`
  - `verified_evidence_refs`
  - `proof_strength`: `recommendation_evidence` or `review_attested`
- expose whether trust closure proof is `bound` or `insufficient`
- keep uncovered sets machine-readable

`REPORT.md`

- add a `## Review Provenance` subsection that distinguishes:
  - recommendation review refs
  - issue closure review refs
  - topic closure review refs
  - uncovered closures, if any
- add a per-ID table mapping each classified global issue or topic to its proof path, proof strength, checked files, and refs

`FINAL_ANSWER.md`

- do not dump raw provenance records
- when trust mode is not clean, add a compact note that names uncovered issue or topic IDs and the reason closure proof is incomplete

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
- Do not reopen Slice A topic-ledger work inside Slice B.

##### Determinism rules

These choices are already decided. Implementers should not invent alternatives during execution:

1. `issue_closure_reviews[]` and `topic_closure_reviews[]` are the only new proof arrays.
2. `selection.py` participates in the change. This is not reporting-only work.
3. Proof completeness is determined by uncovered closure sets, not by raw ref counts.
4. Scoped proof can satisfy closure accounting while still being labeled weaker than recommendation evidence.
5. Slice B does not change evidence-budget policy, bounded-mode UX, or late-auditor defaults.

##### Concrete implementation checklist

1. Freeze contract and prompt wording first.
2. Update runner normalization and coverage accounting second.
3. Update semantic validation and selection semantics against the frozen coverage model.
4. Update reporting only after the provenance model is settled.
5. Add and run the full targeted test matrix before calling the slice done.

##### NOT in scope for Slice B

- attestation-layer redesign
- display-vs-audit evidence-cap split
- line-level or excerpt-level provenance
- hard read tracing
- bounded-mode UI work or workflow changes
- changing proposer search strategy
- tightening late-auditor severity policy defaults
- renderer cleanup unrelated to provenance output

#### Test review

##### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] Recommendation-owned closure proof
    │
    ├── [REQUIRED] recommendation-linked issue closure stays covered by recommendation_reviews refs
    ├── [REQUIRED] recommendation-linked topic closure stays covered by recommendation_reviews refs
    └── [REQUIRED] bounded mode still accepts lightweight review payloads

[+] Global closure proof
    │
    ├── [REQUIRED] global issue closure becomes covered by issue_closure_reviews
    ├── [REQUIRED] global topic closure becomes covered by topic_closure_reviews
    └── [REQUIRED] missing scoped proof leaves trust provenance insufficient

[+] Ref normalization and binding
    │
    ├── [REQUIRED] issue/topic closure-review refs normalize to workspace paths
    ├── [REQUIRED] closure-review refs are counted in final provenance records
    └── [REQUIRED] files_reviewed-only payload cannot fake closure completeness

[+] Reporting
    │
    ├── [REQUIRED] report shows recommendation versus issue/topic scoped proof counts separately
    ├── [REQUIRED] report shows proof path and proof strength by ID
    └── [REQUIRED] uncovered closure IDs are rendered when trust proof is incomplete

[+] Selection and partial artifacts
    │
    ├── [REQUIRED] globally proven closures do not block clean partial acceptance when closure proof is complete
    ├── [REQUIRED] globally unproven closures still block clean partial artifacts
    └── [REQUIRED] best-draft selection does not prefer a payload that only inflated scoped proof counts
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
   - closure-review refs outside `checked_files`
   - trust payloads that classify global closures without scoped proof
   - closure-review `verified_evidence_refs` that overclaim beyond surfaced evidence when surfaced evidence exists

3. `tests/test_harness_prompt_consistency.py`
   Assert critic and auditor prompts explain both proof paths clearly and keep `checked_files` framed as context rather than proof.

4. `tests/test_harness_reporting.py`
   Assert the report distinguishes recommendation proof from issue/topic closure proof, emits per-ID proof-path rows, and names uncovered IDs when provenance is `insufficient`.

5. `tests/test_harness_analysis_contract.py`
   Assert the contract docs and schema defaults describe closure-complete provenance correctly.

6. `tests/test_harness_selection.py`
   Add selection and partial-answer coverage for globally proven versus globally unproven closures.

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
- derive coverage from already-normalized state instead of walking the payload twice

If Slice B starts paying latency by doing more reading rather than carrying better proof metadata, the design is wrong.

#### Failure modes for Slice B

| Failure mode | Where it would show up | Required guard |
|---|---|---|
| a global trust closure still looks successful with only `checked_files` | semantic validation + reporting | fail trust validation and surface `insufficient` provenance |
| recommendation-linked closures incorrectly require scoped proof too | runner coverage logic | accept recommendation-level coverage as sufficient when `recommendation_index` is present |
| duplicate closure-review objects silently override each other | semantic validation | reject duplicate `issue_id` or `topic_id` inside closure-review arrays |
| closure-review refs drift outside `checked_files` | semantic validation | require closure-review refs to stay subsets of `checked_files` |
| report collapses recommendation proof and global proof into one opaque count | reporting | render separate counts, proof paths, proof strength, and uncovered IDs |
| globally proven closures accidentally skew partial-answer or best-draft behavior | selection + partial artifact logic | add explicit selection tests for proven versus unproven global closures |

If any one of these ends with silent user-facing ambiguity, Slice B is incomplete.

#### Worktree parallelization strategy for Slice B

##### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| B1. Contract and prompt shape | `anvil/harness/schemas.py`, `anvil/harness/prompts.py`, `docs/analysis_review_contract.md` | — |
| B2. Runner closure-proof coverage | `anvil/harness/runner.py` | B1 |
| B3. Semantic validation and selection semantics | `anvil/harness/semantic_validation.py`, `anvil/harness/selection.py` | B1, B2 |
| B4. Reporting | `anvil/harness/report.py`, `anvil/harness/reporting.py` | B2, B3 |
| B5. Fixtures and tests | `tests/`, `tests/fixtures/harness/` | B1, B2, B3, B4 |

##### Parallel lanes

- Lane A: `B1`
  Freeze the contract first. Everything else depends on field names and proof semantics.

- Lane B: `B2`
  Runner coverage and provenance counts, starts after B1.

- Lane C: `B3`
  Validation and selection work, starts after B2 because both need the final uncovered-set semantics from `runner.py`.

- Lane D: `B4`
  Reporting, starts after B2 and B3 so rendered semantics match real proof semantics and clean-selection behavior.

- Lane E: `B5`
  Tests and fixtures, last, because they touch every shape that is still moving upstream.

##### Execution order

Launch `Lane A` first and merge it before opening any downstream worktree.

Then launch `Lane B`.

After `Lane B` lands, launch `Lane C` in a separate worktree. Do **not** start `Lane C` from the pre-B2 state because `selection.py` and semantic validation both depend on the final runner coverage contract.

When `Lane C` merges, run `Lane D`.

Finish with `Lane E` as the stabilizing pass that locks contract, behavior, and rendered output together.

##### Conflict flags

- Do not split `anvil/harness/runner.py` across multiple worktrees for Slice B.
- Freeze the closure-review field names before validation, selection, or tests branch off.
- Keep `anvil/harness/selection.py` in the same downstream lane as semantic validation. They share the same clean-versus-insufficient decision boundary.
- Keep docs in `B1`, not `B5`, or the repo will temporarily describe stale provenance semantics.

#### Slice B exit criteria

Slice B is done only when all of these are true:

- trust-mode global issue and topic closures can no longer fake success with `checked_files` alone
- recommendation-linked closures still work with recommendation-level proof only
- trust provenance is judged by zero uncovered closures, not non-zero ref counts
- clean selection and partial artifacts respect closure completeness
- `summary.json` and `REPORT.md` expose scoped-proof counts, proof paths, proof strength, and uncovered closure IDs explicitly
- the targeted pytest suite above passes

That is the bar for "closure-complete provenance." Not just "we added more refs."

### Slice B planning resolution

The engineering review is resolved for implementation purposes:

- keep the already-landed Slice A seam intact
- make Slice B about one canonical global-closure proof model
- thread that model through provenance, selection, partial artifacts, validation, and reporting
- defer unrelated evidence-budget, renderer, and late-auditor policy work out of this slice
- judge success by zero uncovered closures plus explicit proof-path rendering, not by raw ref counts

### Implementation Slice C, fully implementable blueprint

#### Slice C objective

Make trust-mode artifact publication honest and readable without introducing a second truth surface.

This slice does exactly one thing: it hardens the downstream output-policy seam after the review payload is already normalized, validated, and scored. It must:

1. block `FINAL_ANSWER.*` when trust-mode audit debt is still blocking
2. keep markdown concise by deriving compact previews from canonical JSON and provenance truth

It does **not** reopen Slice B closure-proof semantics, mutate prompt/schema payload shape, or introduce a second runner.

If two separate agents implement Slice C from this plan, they should touch the same files, freeze the same publishability rules, preserve the same canonical JSON truth, and land the same test matrix.

#### Step 0: Scope challenge

##### Recommended review mode

Use **HOLD SCOPE** for Slice C.

Reason:

- Slice B already changed contract, prompt, validation, and provenance semantics
- the remaining gap is artifact honesty and renderer projection, not another policy migration
- bundling late-auditor policy changes, schema growth, or trust-attestation redesign into this slice would make the acceptance bar fuzzy immediately

##### What already exists

Reuse the existing output seam instead of inventing a second artifact policy system:

| Sub-problem | Existing code to extend | Why this is enough |
|---|---|---|
| trust warning and downgrade causes | `_analysis_warning_causes()` in `anvil/harness/runner.py` | the runner already distinguishes advisory debt from cleaner accepts |
| content acceptance gate | `_analysis_can_fully_accept()` and `_analysis_content_verdict()` in `anvil/harness/runner.py` | final publishability can be layered on top without changing verdict vocabulary |
| final artifact selection | `apply_final_artifacts()` in `anvil/harness/reporting.py` | artifact kind is already selected downstream from verdict and partial-eligibility state |
| partial fallback precedent | `_partial_answer_eligibility()` in `anvil/harness/reporting.py` | trust partial publication is already stricter than plain final publication, which gives the right fallback model |
| deliverable markdown rendering | `render_deliverable_markdown()` in `anvil/harness/reporting.py` | user-facing recommendation evidence already flows through one renderer seam |
| report-side provenance rendering | `_append_review_provenance_section()` in `anvil/harness/report.py` | review provenance already has a dedicated table-rendering seam that can be compacted safely |
| artifact pointer contract | `summary.json` artifact pointers documented in `README.md` | users already have one official source of truth for the primary deliverable |

##### Minimum change set

Do the smallest complete version:

1. classify trust publish blockers explicitly from existing provenance, topic-ledger, and semantic-warning state
2. make `FINAL_ANSWER.*` publication depend on that blocker state, not just `accepted_with_warnings`
3. derive concise markdown previews from canonical recommendation evidence and provenance lists
4. document that markdown is preview-only while JSON remains full fidelity
5. lock the behavior with runner, reporting, and contract/doc tests

Do not add a second evidence store, a second artifact-ranking engine, or a new model-authored payload family.

##### Scope lock

Slice C is intentionally **not** the place to decide:

- new `display_*` versus `audit_*` schema fields
- prompt wording or payload shape changes
- late-auditor severity-policy changes
- topic-ledger cleanup outside final publishability semantics
- trust as a dedicated attestation layer over bounded output
- different bounded versus trust proposer search strategies

Those stay deferred in `TODOS.md`. Slice C is only the honest-publication and compact-projection slice.

##### Complexity check

Slice C should stay inside eight files with zero new classes or services:

- primary code modules: `anvil/harness/runner.py`, `anvil/harness/report.py`, `anvil/harness/reporting.py`
- primary docs/tests: `README.md`, `docs/analysis_review_contract.md`, `tests/test_harness_runner.py`, `tests/test_harness_reporting.py`, `tests/test_harness_analysis_contract.py`

That breadth is acceptable because the work remains one explicit seam, downstream artifact honesty. If the implementation spreads into schemas, prompts, or new helper modules just to shorten markdown, it is overbuilt.

##### Search check

- **[Layer 1]** Reuse the existing verdict pipeline, topic ledger, provenance status, and artifact pointers instead of inventing new state calculators.
- **[Layer 1]** Reuse the existing `PARTIAL_ANSWER.*` and `BEST_DRAFT.*` fallback paths rather than introducing a trust-only artifact type.
- **[Layer 3]** Separate content verdict from final publishability, because the user-facing bug is not verdict calculation. It is artifact honesty.

No external search was needed here. The question is repo-local policy coherence.

##### TODOS and completeness check

`TODOS.md` already carries the larger follow-ups:

- trust as an attestation layer over bounded output
- stronger bounded versus trust operational divergence
- richer line-level review refs
- hard reviewer read tracing
- more UX polish in rendered markdown

Slice C should boil the lake now:

- final publication must stop pretending unresolved trust debt is still shippable final output
- markdown must stop dumping raw full lists when a concise preview is enough
- canonical JSON and provenance artifacts must remain lossless
- bounded-mode behavior must remain unchanged

##### Distribution check

No new artifact family is introduced. Slice C only changes how existing artifacts are selected and rendered:

- `summary.json`
- `REPORT.md`
- `FINAL_ANSWER.*`
- `PARTIAL_ANSWER.*`
- `BEST_DRAFT.*`

That is important. This slice changes what ships, not how users install or invoke the harness.

#### Architecture review

##### Decision

Keep one runner, one canonical audit truth, and one downstream artifact-selection path.

Do **not** add new model-authored fields.

Do **not** add a second evidence store.

Do **not** change closure-proof semantics again.

##### Canonical implementation contract

Freeze these structures for Slice C:

1. `analysis_review_status.publishability`
   Required fields:
   - `final_answer_publishable`
   - `blocking_causes`

2. Recommendation-evidence preview policy in `render_deliverable_markdown()`
   - first `3` evidence refs
   - append `(+N more)` when refs are elided

3. Review-provenance preview policy in `_append_review_provenance_section()`
   - first `2` `checked_files`
   - first `2` `verified_evidence_refs`
   - append `(+N more)` per column when values are elided

##### Normative semantics, no guesswork allowed

These rules are the source of truth for Slice C. If code, docs, or tests disagree, this section wins.

1. `summary.json`, the selected artifact JSON, and provenance records remain the canonical full-fidelity audit truth.

2. `content_verdict` and final publishability are not the same thing. A trust run may remain `accepted_with_warnings` while still being non-publishable as `FINAL_ANSWER.*`.

3. Trust-mode `FINAL_ANSWER.*` is publishable only when all of these are true:
   - the content verdict is exactly `accepted` or `accepted_with_warnings`
   - provenance status is `bound`
   - topic ledger has no `open` topic IDs
   - topic ledger has no `carried_forward` topic IDs
   - final semantic warning count is `0`

4. Low-severity reviewer issues, `accept_with_caveat` recommendation reviews, and inference-only accepted recommendations remain advisory causes. They stay visible, but they do not block final publication by themselves.

5. If trust mode is content-accepted but not final-publishable, artifact selection must skip `FINAL_ANSWER.*` and fall through to the existing partial-answer path when eligible, otherwise `BEST_DRAFT.*`.

6. `analysis_review_status.publishability.blocking_causes` must explain exactly why `FINAL_ANSWER.*` was withheld. Do not force users to reverse-engineer that from downgrade causes alone.

7. Markdown preview is renderer-owned. No prompt, schema, or provider payload may introduce `display_evidence_refs`, `audit_evidence_refs`, or any other dual-truth field family.

8. Preview rendering must preserve stable order, show the first items deterministically, and append omitted-count markers. It must never reorder refs for prettiness.

9. JSON artifacts keep the full lists even when markdown is compacted.

10. Bounded-mode behavior is unchanged by this slice.

##### File-by-file implementation contract

| File | Required change | Notes |
|---|---|---|
| `anvil/harness/runner.py` | add explicit trust publishability classification and expose `analysis_review_status.publishability` in the summary | blocker logic must reuse existing provenance, topic-ledger, and semantic-warning state |
| `anvil/harness/reporting.py` | gate `FINAL_ANSWER.*` on final publishability, keep partial/best-draft fallback intact, and render concise recommendation-evidence previews | artifact selection stays verdict-aware but no longer treats every `accepted_with_warnings` trust run as shippable final output |
| `anvil/harness/report.py` | render compact provenance previews and name publish blockers clearly in `REPORT.md` | full raw values stay in JSON |
| `README.md` | document the difference between content verdict and final artifact kind for trust mode | readers must stop assuming `accepted_with_warnings` implies `FINAL_ANSWER.*` |
| `docs/analysis_review_contract.md` | document renderer-owned preview policy and the new `analysis_review_status.publishability` surface | no prompt/schema changes |
| `tests/test_harness_runner.py` | cover publish-blocker classification and summary status emission | main behavior guard |
| `tests/test_harness_reporting.py` | cover artifact fallback, concise preview rendering, and preview-versus-JSON fidelity | user-visible output guard |
| `tests/test_harness_analysis_contract.py` | assert docs and contract language stay aligned on publishability and preview semantics | doc drift guard |

##### Data flow

```text
review payload + topic ledger + provenance + semantic warnings
                │
                ▼
      anvil/harness/runner.py
        ├── compute content verdict
        ├── classify downgrade causes
        └── classify final publish blockers
                │
                ▼
     summary["analysis_review_status"]
        ├── content_verdict
        ├── downgrade_causes
        └── publishability{final_answer_publishable, blocking_causes}
                │
                ▼
     anvil/harness/reporting.py
        ├── choose FINAL / PARTIAL / BEST_DRAFT
        └── render compact recommendation-evidence previews
                │
                ▼
       anvil/harness/report.py
        └── render compact provenance previews + blocker explanation

Canonical raw refs stay in JSON and provenance records the whole time.
Markdown is derived projection only.
```

##### Architecture-specific failure scenario

Real production failure: a trust run lands at `accepted_with_warnings` because topic debt or semantic warnings remain, but `apply_final_artifacts()` still writes `FINAL_ANSWER.*`. A user sees the final artifact, skips `summary.json`, and assumes the answer is safe to ship. Slice C must make that impossible.

##### Final artifact contract

The reporting shape is fixed, not left to taste.

`summary.json`

- preserve the full canonical payload, recommendation evidence, and provenance arrays
- add `analysis_review_status.publishability.final_answer_publishable`
- add `analysis_review_status.publishability.blocking_causes`
- keep `artifacts.final_artifact`, `final_artifact_json`, and `final_artifact_kind` as the source of truth for what actually shipped

`REPORT.md`

- add a compact publishability explanation when trust final publication is blocked
- keep full audit meaning, but preview long `checked_files` and `verified_evidence_refs` lists instead of dumping raw lists inline
- make it obvious whether the primary deliverable is final, partial, or best draft

`FINAL_ANSWER.md`

- only exists when `final_answer_publishable` is true
- shows compact evidence previews, not raw full lists

`PARTIAL_ANSWER.md` / `BEST_DRAFT.md`

- become the primary deliverable when final publication is blocked
- must include a top-of-file note that names the blocked final-publication reason using `analysis_review_status.publishability.blocking_causes`
- the note must appear before the `## Review Status` section
- the note must not paraphrase away the blocker taxonomy; it should reuse the blocker strings directly or join them verbatim

This split is intentional:

- `summary.json` is the machine-readable truth
- `REPORT.md` is the auditable human explanation
- deliverable markdown is the concise projection

#### Code quality review

##### Minimal-diff rules

- Reuse existing topic-ledger and provenance state. Do not recompute them from raw payload text.
- Keep preview generation in renderer helpers, not provider payloads.
- Keep publish-blocker logic next to `_analysis_warning_causes()` so the advisory-versus-blocking split stays obvious.
- Do not touch `anvil/harness/schemas.py` or `anvil/harness/prompts.py` for this slice.
- Do not add a generic preview abstraction if two local helper functions in reporting/report are enough.

##### Determinism rules

These choices are already decided. Implementers should not reopen them during execution:

1. Trust publish blockers are unbound provenance, open topics, carried-forward topics, and final semantic warnings.
2. Advisory-only causes remain visible but non-blocking.
3. `FINAL_ANSWER.*` withholding is an artifact-selection decision, not a new content-verdict string.
4. Preview budgets are fixed for this slice: `3` recommendation evidence refs, `2` provenance refs per report column.
5. Markdown compaction never changes the JSON truth.

##### Concrete implementation checklist

1. Add publishability classification in `runner.py` first and freeze the blocker taxonomy there.
2. Wire `apply_final_artifacts()` to the new publishability state second.
3. Add compact preview rendering in `reporting.py` and `report.py` only after publishability semantics are frozen.
4. Update `README.md` and `docs/analysis_review_contract.md` once field names and artifact semantics are fixed.
5. Add and run the targeted tests before calling the slice done.

##### NOT in scope for Slice C

- changing closure-proof semantics
- changing prompt or schema payload shape
- new `display_*` versus `audit_*` model fields
- removing every remaining `missing_topics` fallback path as a separate cleanup slice
- changing selection ranking or partial-answer eligibility rules
- tightening `late_auditor_medium_or_higher_policy` defaults
- trust as a separate attestation runner or post-pass

#### Test review

##### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] Publishability classification
    │
    ├── [REQUIRED] trust accepted_with_warnings + provenance.status != bound blocks FINAL_ANSWER.*
    ├── [REQUIRED] trust accepted_with_warnings + open topic IDs blocks FINAL_ANSWER.*
    ├── [REQUIRED] trust accepted_with_warnings + carried-forward topic IDs blocks FINAL_ANSWER.*
    ├── [REQUIRED] trust accepted_with_warnings + semantic warnings blocks FINAL_ANSWER.*
    └── [REQUIRED] advisory-only trust warnings leave FINAL_ANSWER.* publishable

[+] Artifact fallback
    │
    ├── [REQUIRED] blocked final artifact falls through to PARTIAL_ANSWER.* when subset is eligible
    ├── [REQUIRED] blocked final artifact falls through to BEST_DRAFT.* when no clean subset is publishable
    └── [REQUIRED] bounded-mode accepted_with_warnings behavior stays unchanged

[+] Deliverable markdown projection
    │
    ├── [REQUIRED] recommendation evidence > 3 refs becomes stable preview + (+N more)
    ├── [REQUIRED] blocked PARTIAL_ANSWER.md explains why FINAL_ANSWER.* was withheld
    └── [REQUIRED] blocked BEST_DRAFT.md explains why FINAL_ANSWER.* was withheld

[+] Report projection
    │
    ├── [REQUIRED] REPORT.md previews checked_files with first 2 refs + (+N more)
    ├── [REQUIRED] REPORT.md previews verified_evidence_refs with first 2 refs + (+N more)
    └── [REQUIRED] REPORT.md names blocking causes without losing full JSON fidelity

[+] Canonical JSON fidelity
    │
    ├── [REQUIRED] summary.json keeps full evidence and provenance lists
    └── [REQUIRED] final_artifact pointers reflect the actually published deliverable
```

##### Required tests by file

1. `tests/test_harness_runner.py`
   Add end-to-end coverage for:
   - trust accepted-with-warnings plus unbound provenance
   - trust accepted-with-warnings plus open topic debt
   - trust accepted-with-warnings plus carried-forward topic debt
   - trust accepted-with-warnings plus semantic warnings
   - trust advisory-only warnings still marking final publication as allowed

2. `tests/test_harness_reporting.py`
   Add rendering and artifact-selection coverage for:
   - final-artifact fallback from blocked trust publication to partial answer
   - final-artifact fallback from blocked trust publication to best draft
   - recommendation evidence preview with `(+N more)`
   - report-side provenance preview with `(+N more)`
   - partial/best-draft markdown note explaining why `FINAL_ANSWER.*` was withheld
   - JSON artifacts keeping full raw lists while markdown is compact

3. `tests/test_harness_analysis_contract.py`
   Add or update assertions that docs describe:
   - `analysis_review_status.publishability`
   - the difference between content verdict and final artifact kind
   - renderer-owned preview semantics versus full JSON truth

##### Test plan artifact

The concrete test plan for this slice is written to:

`/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-eng-review-test-plan-20260422-140827.md`

##### Verification commands for Slice C

```bash
poetry run pytest -q \
  tests/test_harness_runner.py \
  tests/test_harness_reporting.py \
  tests/test_harness_analysis_contract.py
```

#### Performance review

Keep Slice C cheap:

- no new model pass
- no replay requirement for basic correctness
- no second evidence store
- no extra workspace scan
- render previews from already-normalized lists instead of recomputing provenance

If Slice C starts paying latency by re-reading more state rather than carrying better downstream policy metadata, the design is wrong.

#### Failure modes for Slice C

| Failure mode | Where it would show up | Required guard |
|---|---|---|
| trust still writes `FINAL_ANSWER.*` with unresolved publish blockers | artifact selection | runner/reporting tests must assert fallback to partial or best draft |
| advisory caveats accidentally become blocking | runner | tests must distinguish `blocking_causes` from downgrade/advisory causes |
| markdown preview hides the only meaningful ref | renderer | preview keeps first refs stable and records omitted counts |
| markdown preview becomes a second truth surface | renderer + docs | JSON stays full fidelity and docs name markdown as preview-only |
| `REPORT.md` and deliverable markdown use different preview budgets | report + reporting | mirrored tests must pin `3` recommendation refs and `2` provenance refs |
| artifact pointers say `final_answer` while the files on disk are partial or best draft | reporting | tests must assert `final_artifact_kind` and file paths after fallback |

If any one of these ends with silent user-facing ambiguity, Slice C is incomplete.

#### Worktree parallelization strategy for Slice C

##### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| C1. Publishability classification | `anvil/harness/runner.py` | — |
| C2. Final artifact fallback semantics | `anvil/harness/reporting.py` | C1 |
| C3. Report-side provenance projection | `anvil/harness/report.py` | C1 |
| C4. Docs and contract wording | `README.md`, `docs/analysis_review_contract.md` | C1 |
| C5. Tests | `tests/` | C1, C2, C3, C4 |

##### Parallel lanes

- Lane A: `C1`
  Freeze publishability semantics first. Everything downstream depends on the blocker taxonomy.

- Lane B: `C2`
  Artifact fallback and deliverable markdown work, starts after `C1`.

- Lane C: `C3`
  Report-side provenance projection, starts after `C1`. Independent from `C2` as long as preview budgets are already frozen.

- Lane D: `C4`
  Docs and contract wording, starts after `C1`. This can run in parallel with `C2` and `C3` once field names are frozen.

- Lane E: `C5`
  Tests, last, because they need the final runner, report, reporting, and docs semantics.

##### Execution order

Launch `Lane A` first and merge it before opening downstream worktrees.

Then launch `Lane B`, `Lane C`, and `Lane D` in parallel worktrees.

Merge `Lane B` and `Lane C` before starting `Lane E`, because the tests need the real fallback and preview behavior, not placeholder wording.

Finish with `Lane E` as the lock-the-whole-slice pass.

##### Conflict flags

- Do not split `anvil/harness/reporting.py` across multiple worktrees. Final-artifact fallback and deliverable preview rendering share the same file and will conflict immediately.
- Freeze the `analysis_review_status.publishability` field names before docs or tests branch off.
- Keep preview budgets identical across `report.py` and `reporting.py` or the user will see two different compact views of the same truth.
- Keep docs in `C4`, not `C5`, or the repo will temporarily describe stale artifact semantics.

#### Completion summary

- Step 0: Scope Challenge, scope accepted as-is
- Architecture Review: output policy stays in one runner/report/reporting seam
- Code Quality Review: minimal-diff rules locked, no schema/prompt churn allowed
- Test Review: coverage diagram produced, 13 required behaviors pinned
- Performance Review: no new pass, no new store, no extra scan
- NOT in scope: written
- What already exists: written
- TODOS.md updates: existing deferred items remain valid, no new TODO required for this slice
- Failure modes: 6 critical ambiguity risks pinned with guards
- Outside voice: prior codex-only review already incorporated into the slice framing
- Parallelization: 5 steps, 3 parallel lanes after the initial runner freeze, 2 sequential stages
- Lake Score: complete option chosen throughout, no shortcut variant accepted

#### Slice C exit criteria

Slice C is done only when all of these are true:

- trust publish blockers can prevent `FINAL_ANSWER.*` even when content verdict stays `accepted_with_warnings`
- advisory-only trust warnings can still publish
- partial or best-draft fallback stays honest and updates artifact pointers correctly
- markdown artifacts show concise previews instead of raw full evidence/proof lists
- `REPORT.md` uses the same compact projection policy without becoming a second truth surface
- JSON artifacts and provenance records remain full fidelity
- the targeted pytest suite above passes

That is the bar for "honest trust publication." Not just "the markdown looks shorter."

## Slice D Review Refresh

### CODEX SAYS (CEO, codex-only)

- **Critical:** the next slice is not generic "verdict tightening." The real product seam is trust recommendation admissibility and artifact promotion.
- **Critical:** after Slice C, the trust-mode failure users will still feel is seeing `FINAL_ANSWER.*` ship recommendations the system itself marks as caveated or inference-backed.
- **High:** the foolishly large version of this slice would bundle late-auditor policy rewrites, caveat taxonomy growth, new verdict strings, schema changes, and `BEST_DRAFT` redesign into one pass.
- **Recommendation:** freeze one artifact-promotion matrix first. Make shipping behavior honest before you reopen trust architecture.

### CODEX SAYS (eng, codex-only)

- **High:** `FINAL_ANSWER.*` cannot become a silently pruned subset. Under the current artifact contract, that demotion must route through `PARTIAL_ANSWER.*` or `BEST_DRAFT.*`.
- **High:** accepted-recommendation semantics are duplicated today across `runner.py`, `reporting.py`, and `selection.py`, so the next slice must centralize runner-owned admissibility instead of patching artifact selection alone.
- **Medium:** raw `accept_with_caveat` is too coarse to become a permanent schema-level policy language. Use it as a strict trust-promotion signal in runtime policy only, not as a reason to expand model payload shape.
- **Medium:** late-auditor overflow is real, but it is a separate validator-policy seam. Keep it out of the first admissibility pass unless the implementation can close the partial-publication loophole without broadening scope.

### Slice D consensus

Subagent voice was unavailable in this environment, so this refresh is codex-only.

The outside review still converged on a clear direction:

1. the active next slice should be recommendation admissibility and artifact promotion, not another generic warning pass
2. `FINAL_ANSWER.*` must remain all-or-nothing, never an implicitly filtered subset
3. the strict version of this work should stay runner-owned and payload-neutral
4. late-auditor overflow is important, but it should not hijack the main slice framing

## Implementation Slice D, fully implementable blueprint

#### Slice D objective

Freeze trust recommendation admissibility and artifact promotion using existing structured signals.

This slice does exactly one thing: it decides which accepted recommendations may appear in `FINAL_ANSWER.*`, which may only appear in `PARTIAL_ANSWER.*`, and when the harness must fall back to `BEST_DRAFT.*`.

It must:

1. add one runner-owned admissibility surface for accepted recommendations
2. keep `FINAL_ANSWER.*` all-or-nothing
3. make `PARTIAL_ANSWER.*` the honest home for trust recommendations that are usable but not final-admissible
4. keep `BEST_DRAFT.*` as the unchanged last-resort fallback when no admissible partial answer remains

It does **not** reopen prompt/schema payload shape, invent a second artifact family, or redesign trust as a second runner.

#### Step 0: Scope challenge

##### Recommended review mode

Use **HOLD SCOPE** for Slice D.

Reason:

- Slice C already changed run-level publishability semantics and downstream artifact honesty
- the next user-facing gap is recommendation-level shipping policy, not a broader trust rewrite
- mixing admissibility, late-auditor validator policy, and `BEST_DRAFT` ranking changes would blur the acceptance bar immediately

##### Premises

These are the premises this plan accepts:

1. Slice C solved run-level trust publishability, but not recommendation-level shipping honesty.
2. In trust mode, `FINAL_ANSWER.*` should not ship recommendations the system itself marks as caveated or inference-backed.
3. `PARTIAL_ANSWER.*` is the correct artifact for scoped, explicit demotions. `FINAL_ANSWER.*` must not become a silently filtered subset.
4. The next slice should reuse existing verdicts, grounding modes, topic lifecycle, and artifact paths instead of growing the payload schema.

##### What already exists

Reuse the existing trust/output seam instead of inventing a new one:

| Sub-problem | Existing code to extend | Why this is enough |
|---|---|---|
| accepted recommendation rollups | `_accepted_recommendation_reviews()`, `_accepted_caveat_recommendation_indices()`, and `_accepted_inferred_recommendation_indices()` in `anvil/harness/runner.py` | the runner already knows which recommendations are accepted, caveated, and inference-backed |
| run-level publishability | `_analysis_publishability()` plus `analysis_review_status.publishability` in `anvil/harness/runner.py` | the repo already distinguishes run-level final blockers from advisory downgrade causes |
| partial artifact shaping | `_partial_answer_eligibility()`, `_eligible_partial_answer_indices()`, and partial-summary helpers in `anvil/harness/reporting.py` | `PARTIAL_ANSWER.*` already carries explicit included/excluded indices and is the honest subset artifact |
| recommendation review rendering | `## Recommendation Reviews` and analysis-review status sections in `anvil/harness/report.py` | the report already has the right seam for explaining scoped demotions without inventing new markdown surfaces |
| trust-mode guidance | `_trust_review_policy_block()` and `_mode_acceptance_guidance_block()` in `anvil/harness/prompts.py` | trust prompts already render policy from the contract and can stay payload-neutral |
| contract/docs/tests | `anvil/harness/contracts.py`, `docs/analysis_review_contract.md`, `README.md`, and `tests/test_harness_*` | the repo already freezes trust-mode policy in code and documentation, so Slice D can stay explicit and testable |

##### Minimum change set

Do the smallest complete version:

1. classify accepted recommendations into `final`, `partial_only`, or `excluded` using runner-owned logic
2. require all shipped `FINAL_ANSWER.*` recommendations to be `final`
3. route mixed admissibility sets through `PARTIAL_ANSWER.*`, preserving original recommendation indices and naming exclusions explicitly
4. keep `BEST_DRAFT.*` behavior unchanged unless no admissible partial answer remains
5. update prompts, docs, and tests so the repo stops freezing the old advisory-only policy for trust final artifacts

##### Scope lock

Slice D is intentionally **not** the place to decide:

- new model-authored caveat taxonomy fields
- new verdict strings
- trust as a dedicated attestation layer over bounded output
- a new artifact family beyond `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*`
- `BEST_DRAFT` ranking redesign in `anvil/harness/selection.py`
- a broader late-auditor validator-policy rewrite

Those stay deferred in `TODOS.md`. Slice D is only the recommendation-admissibility and artifact-promotion slice.

##### Complexity check

Slice D should stay inside nine files with zero new services:

- primary code modules: `anvil/harness/contracts.py`, `anvil/harness/runner.py`, `anvil/harness/report.py`, `anvil/harness/reporting.py`, `anvil/harness/prompts.py`
- primary docs/tests: `README.md`, `docs/analysis_review_contract.md`, `tests/test_harness_runner.py`, `tests/test_harness_reporting.py`, `tests/test_harness_prompt_consistency.py`

That breadth is acceptable because the work stays inside one seam, trust artifact promotion. If the implementation spills into schemas, subgraphs, providers, or new helper modules just to encode recommendation admissibility, it is overbuilt.

##### Search check

- **[Layer 1]** Reuse runner-owned accepted-review, inferred-grounding, topic-lifecycle, and artifact-selection helpers.
- **[Layer 1]** Reuse `PARTIAL_ANSWER.*` as the explicit subset artifact instead of trying to make `FINAL_ANSWER.*` secretly behave like a subset artifact.
- **[Layer 3]** Keep recommendation admissibility runtime-derived and payload-neutral. The repo already has enough truth to do this without adding new model fields.

No external search was needed here. The seam is repo-local and the current code already exposes the important coupling points.

##### TODOS and completeness check

`TODOS.md` already carries the larger follow-ups:

- a richer caveat taxonomy instead of raw `accept_with_caveat`
- a separate trust attestation layer over bounded output
- `BEST_DRAFT` strategy changes
- stronger late-auditor policy changes
- richer line-level review refs

Slice D should boil the lake now:

- `FINAL_ANSWER.*` must stop shipping caveated or inference-backed trust recommendations silently
- `PARTIAL_ANSWER.*` must become the explicit home for scoped trust demotions
- recommendation admissibility must be derived once in the runner, not re-derived ad hoc in renderers
- bounded-mode behavior must remain unchanged

##### Distribution check

No new artifact family is introduced. Slice D only changes how existing artifacts are promoted:

- `FINAL_ANSWER.*`
- `PARTIAL_ANSWER.*`
- `BEST_DRAFT.*`
- `summary.json`
- `REPORT.md`

That is the right boundary. This slice changes what is allowed to ship, not how the harness is distributed.

#### Architecture review

##### Decision

Keep one runner, one payload family, and one artifact-selection path.

Do **not** add new model-authored fields.

Do **not** let `FINAL_ANSWER.*` become a filtered subset.

Do **not** redesign `BEST_DRAFT.*` in the same slice.

##### Canonical implementation contract

Freeze these structures for Slice D:

1. `analysis_review_status.recommendation_admissibility`
   Required fields:
   - `final_answer_recommendation_indices`
   - `partial_only_recommendation_indices`
   - `excluded_recommendation_indices`
   - `reasons_by_recommendation_index`

2. Trust promotion rules in `anvil/harness/contracts.py`
   Required policy decisions:
   - final artifacts do not allow `accept_with_caveat`
   - final artifacts do not allow inference-only accepted recommendations
   - partial artifacts may include those recommendations when the run-level partial gates are still satisfied

3. Artifact promotion in `apply_final_artifacts()`
   - `FINAL_ANSWER.*` only when every shipped accepted recommendation is final-admissible
   - `PARTIAL_ANSWER.*` when an admissible subset still meets the partial-acceptance minimum
   - `BEST_DRAFT.*` when no admissible subset remains

##### Normative semantics, no guesswork allowed

These rules are the source of truth for Slice D. If code, docs, or tests disagree, this section wins.

1. Recommendation admissibility is runner-owned. Prompts may describe it, but they do not author it.

2. In trust mode, a recommendation is `final` only when all of these are true:
   - its recommendation review verdict is `accept`
   - its final recommendation grounding mode is not `inferred`
   - it is not removed by existing topic-based partial-acceptance rules

3. In trust mode, a recommendation is `partial_only` when either of these is true:
   - its recommendation review verdict is `accept_with_caveat`
   - its recommendation review verdict is `accept` but the final recommendation grounding mode is `inferred`

4. In trust mode, a recommendation is `excluded` when it is not accepted at all or when existing topic-based partial-acceptance rules already make it unshippable.

5. `FINAL_ANSWER.*` is all-or-nothing. It may never silently omit accepted-but-not-final-admissible recommendations.

6. `PARTIAL_ANSWER.*` is the explicit subset artifact. It may include both `final` and `partial_only` recommendations, but it must name excluded recommendation indices and the reasons they were excluded.

7. If the count of `final` plus `partial_only` recommendations falls below `min_accepted_recommendations`, the harness must not manufacture a partial answer. It must fall through to `BEST_DRAFT.*`.

8. `BEST_DRAFT.*` remains the existing raw fallback in this slice. Slice D does not redesign best-draft ranking or filter best drafts by recommendation admissibility.

9. Bounded-mode behavior is unchanged.

##### File-by-file implementation contract

| File | Required change | Notes |
|---|---|---|
| `anvil/harness/contracts.py` | freeze trust recommendation-promotion policy in the contract | no new payload fields, only runtime policy fields |
| `anvil/harness/runner.py` | classify per-recommendation admissibility and expose it in `analysis_review_status` | the runner is the only place that already sees review verdicts, grounding, and topic debt together |
| `anvil/harness/reporting.py` | use runner-owned admissibility for final versus partial artifact selection, keeping `FINAL_ANSWER.*` all-or-nothing | no silent subset final artifacts |
| `anvil/harness/report.py` | render admissibility outcomes and excluded recommendation reasons explicitly in `REPORT.md` | keep the report as the human-auditable explanation seam |
| `anvil/harness/prompts.py` | update trust-mode guidance so reviewers know `accept_with_caveat` and inference-backed accepts demote final-artifact eligibility | prompt behavior stays derived from contract text |
| `README.md` | document the new difference between accepted content and final-admissible recommendations | users must stop assuming all accepted trust recommendations can ship in `FINAL_ANSWER.*` |
| `docs/analysis_review_contract.md` | document the admissibility surface and artifact-promotion rules | keep payload shape unchanged |
| `tests/test_harness_runner.py` | cover recommendation admissibility classification and min-threshold fallout | main behavior guard |
| `tests/test_harness_reporting.py` | cover final-versus-partial promotion and excluded-index rendering | user-visible output guard |
| `tests/test_harness_prompt_consistency.py` | lock prompt text to the new contract rules | doc/prompt drift guard |

##### Data flow

```text
review verdicts + recommendation grounding + topic ledger + partial-acceptance rules
                │
                ▼
      anvil/harness/runner.py
        ├── classify run-level publishability
        ├── classify recommendation admissibility
        └── expose both in analysis_review_status
                │
                ▼
     anvil/harness/reporting.py
        ├── FINAL_ANSWER when all accepted recommendations are final-admissible
        ├── PARTIAL_ANSWER when final publication is not allowed but an admissible subset remains
        └── BEST_DRAFT when no admissible subset remains
                │
                ▼
       anvil/harness/report.py
        ├── explain why FINAL_ANSWER was withheld
        ├── list final / partial-only / excluded recommendation indices
        └── show per-index reasons for exclusions
```

##### Architecture-specific failure scenario

Real production failure: a trust run accepts three recommendations, but recommendation 2 is `accept_with_caveat` and recommendation 3 is inference-backed. If `FINAL_ANSWER.*` still ships all three, users see "Final Answer" and miss the epistemic downgrade. If `FINAL_ANSWER.*` silently ships only recommendation 1, users lose scope without being told. Slice D must force that run into an explicit `PARTIAL_ANSWER.*` with the omitted indices and reasons named.

##### Final artifact contract

The reporting shape is fixed, not left to taste.

`summary.json`

- preserve full recommendation reviews, topic ledger, and publishability state
- add `analysis_review_status.recommendation_admissibility`
- keep `artifacts.final_artifact`, `final_artifact_json`, and `final_artifact_kind` as the source of truth for what actually shipped

`REPORT.md`

- add a compact recommendation-admissibility section
- list `final`, `partial_only`, and `excluded` recommendation indices
- name the per-index exclusion reasons directly

`FINAL_ANSWER.md`

- only exists when every shipped accepted recommendation is `final`
- must not silently omit accepted recommendations

`PARTIAL_ANSWER.md`

- becomes the primary deliverable when some accepted recommendations are only `partial_only`
- must preserve original recommendation indices
- must include a top-of-file note that names which recommendation indices were excluded from `FINAL_ANSWER.*` and why

`BEST_DRAFT.md`

- remains the current fallback when no admissible partial answer remains
- is not re-ranked or filtered differently in this slice

This split is intentional:

- `summary.json` is the machine-readable truth
- `REPORT.md` is the full human explanation
- `PARTIAL_ANSWER.*` is the explicit scoped fallback when trust recommendations are usable but not final-admissible

#### Code quality review

##### Minimal-diff rules

- Reuse accepted-review and inferred-grounding helpers in `runner.py`. Do not re-derive admissibility separately inside reporting.
- Keep promotion rules contract-driven and runner-owned.
- Keep `FINAL_ANSWER.*` all-or-nothing.
- Do not add a caveat parser for free-text recommendation review summaries.
- Do not touch `anvil/harness/schemas.py`, `anvil/harness/subgraphs/*`, or provider adapters in this slice.

##### Determinism rules

These choices are already decided. Implementers should not reopen them during execution:

1. `accept_with_caveat` is not final-admissible in trust mode.
2. Inference-backed accepted recommendations are not final-admissible in trust mode.
3. `PARTIAL_ANSWER.*` can still carry those recommendations when the admissible subset stays above the partial minimum.
4. `FINAL_ANSWER.*` cannot silently drop accepted recommendations.
5. `BEST_DRAFT.*` ranking stays unchanged in Slice D.

##### Concrete implementation checklist

1. Freeze the contract-level trust promotion rules first.
2. Classify recommendation admissibility in `runner.py` second.
3. Wire `apply_final_artifacts()` to runner-owned admissibility third.
4. Update report rendering and top-of-file markdown notes fourth.
5. Update prompts and docs once field names and artifact semantics are fixed.
6. Add and run the targeted tests before calling the slice done.

##### NOT in scope for Slice D

- new schema fields for caveat kinds
- late-auditor overflow as a full validator-policy rewrite
- `BEST_DRAFT` ranking changes
- removing every remaining legacy compatibility path
- bounded-mode recommendation-promotion changes
- trust as a separate attestation runner

#### Test review

##### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] Recommendation admissibility classification
    │
    ├── [REQUIRED] trust verdict=accept + direct grounding -> final
    ├── [REQUIRED] trust verdict=accept_with_caveat -> partial_only
    ├── [REQUIRED] trust verdict=accept + inferred grounding -> partial_only
    └── [REQUIRED] non-accepted recommendations -> excluded

[+] Artifact promotion
    │
    ├── [REQUIRED] all accepted recommendations final-admissible -> FINAL_ANSWER
    ├── [REQUIRED] mixed final + partial_only recommendations -> PARTIAL_ANSWER
    ├── [REQUIRED] admissible subset below min_accepted_recommendations -> BEST_DRAFT
    └── [REQUIRED] FINAL_ANSWER never silently omits accepted recommendations

[+] Partial artifact fidelity
    │
    ├── [REQUIRED] PARTIAL_ANSWER preserves original recommendation indices
    ├── [REQUIRED] PARTIAL_ANSWER names excluded indices and reasons
    └── [REQUIRED] REPORT.md shows the same admissibility truth as summary.json

[+] Existing trust blockers stay composed
    │
    ├── [REQUIRED] final publish blockers still win before admissibility can publish FINAL_ANSWER
    ├── [REQUIRED] topic-based partial blockers still remove unshippable recommendations
    └── [REQUIRED] bounded mode keeps current FINAL_ANSWER behavior
```

##### Required tests by file

1. `tests/test_harness_runner.py`
   Add end-to-end coverage for:
   - all-final trust acceptance
   - caveated trust acceptance producing `partial_only`
   - inference-only accepted recommendations producing `partial_only`
   - admissible-subset count dropping below `min_accepted_recommendations`
   - bounded mode staying unchanged

2. `tests/test_harness_reporting.py`
   Add rendering and artifact-selection coverage for:
   - `FINAL_ANSWER.*` when all accepted recommendations are final-admissible
   - `PARTIAL_ANSWER.*` when some accepted recommendations are only partial-admissible
   - top-of-file notes naming excluded recommendation indices and reasons
   - `REPORT.md` admissibility sections matching `summary.json`
   - artifact pointers reflecting the actual primary deliverable

3. `tests/test_harness_prompt_consistency.py`
   Add or update assertions that trust prompts explicitly say:
   - `accept_with_caveat` demotes final-artifact eligibility
   - inference-backed accepted recommendations demote final-artifact eligibility
   - bounded-mode prompts stay unchanged

4. `tests/test_harness_analysis_contract.py`
   Update assertions that docs describe:
   - `analysis_review_status.recommendation_admissibility`
   - `FINAL_ANSWER.*` as all-or-nothing
   - `PARTIAL_ANSWER.*` as the explicit scoped fallback

##### Test plan artifact

The concrete test plan for this slice is written to:

`/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-eng-review-test-plan-20260422-192048.md`

##### Verification commands for Slice D

```bash
poetry run pytest -q \
  tests/test_harness_runner.py \
  tests/test_harness_reporting.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_analysis_contract.py
```

#### Performance review

Keep Slice D cheap:

- no new model pass
- no new payload family
- no new draft-selection algorithm
- no extra workspace scan
- no renderer-side re-derivation of admissibility

If Slice D starts paying latency by recomputing admissibility in multiple files, the design is wrong.

#### Failure modes for Slice D

| Failure mode | Where it would show up | Required guard |
|---|---|---|
| `FINAL_ANSWER.*` still ships a caveated or inference-backed trust recommendation | runner + reporting | end-to-end tests must assert demotion to `PARTIAL_ANSWER.*` |
| `FINAL_ANSWER.*` silently drops accepted recommendations | reporting | tests must assert final artifacts include all accepted indices or do not exist |
| `PARTIAL_ANSWER.*` loses original recommendation indices | reporting | tests must pin included/excluded indices exactly |
| recommendation admissibility is re-derived differently in runner and reporting | runner + reporting | summary/report assertions must compare the same per-index truth |
| the admissible subset falls below the partial minimum but the harness still emits `PARTIAL_ANSWER.*` | runner + reporting | runner tests must assert fallback to `BEST_DRAFT.*` |
| bounded-mode artifacts change as collateral damage | runner + reporting | bounded-mode regression tests must stay green |

If any one of these ends with silent user-facing ambiguity, Slice D is incomplete.

#### Worktree parallelization strategy for Slice D

##### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| D1. Contract freeze | `contracts.py`, `prompts.py` | — |
| D2. Runner admissibility | `runner.py` | D1 |
| D3. Artifact promotion + report rendering | `reporting.py`, `report.py` | D2 |
| D4. Docs | `README.md`, `docs/analysis_review_contract.md` | D2 |
| D5. Tests | `tests/` | D2, D3, D4 |

##### Parallel lanes

- Lane A: `D1`
  Freeze the trust-promotion policy first.

- Lane B: `D2`
  Build the runner-owned admissibility surface immediately after `D1`.

- Lane C: `D3`
  Artifact promotion and report rendering, starts after `D2`.

- Lane D: `D4`
  Docs and contract wording, starts after `D2`.

- Lane E: `D5`
  Tests, last, because they need the final runner, reporting, and docs semantics.

##### Conflict flags

- Do not split `anvil/harness/reporting.py` across multiple worktrees.
- Freeze the `recommendation_admissibility` field names before docs or tests branch off.
- Do not let `report.py` invent a second admissibility calculation.
- Keep `selection.py` out of the first pass unless scope explicitly expands.

#### Completion summary

- Step 0: Scope Challenge, scope accepted as-is
- Architecture Review: recommendation admissibility stays runner-owned and payload-neutral
- Code Quality Review: minimal-diff rules locked, no schema growth allowed
- Test Review: coverage diagram produced, 12 required behaviors pinned
- Performance Review: no new pass, no new payload family, no ranking rewrite
- NOT in scope: written
- What already exists: written
- TODOS.md updates: existing deferred items remain valid, no new TODO required for this slice
- Failure modes: 6 critical ambiguity risks pinned with guards
- Outside voice: codex-only strategy and eng challenge incorporated into the slice framing
- Parallelization: 5 steps, 1 contract freeze, 2 downstream lanes, 1 final test lock
- Lake Score: complete option chosen throughout, no shortcut variant accepted

#### Slice D exit criteria

Slice D is done only when all of these are true:

- trust `FINAL_ANSWER.*` ships only when every shipped accepted recommendation is final-admissible
- caveated or inference-backed trust recommendations route through `PARTIAL_ANSWER.*`, not `FINAL_ANSWER.*`
- `FINAL_ANSWER.*` never silently omits accepted recommendations
- `PARTIAL_ANSWER.*` preserves original recommendation indices and names excluded indices plus reasons
- runs with no admissible partial subset fall through to `BEST_DRAFT.*`
- bounded-mode behavior remains unchanged
- the targeted pytest suite above passes

That is the bar for "honest trust promotion." Not just "more warnings showed up."

## Cross-Phase Themes

Three themes showed up everywhere:

1. **Artifact honesty now means recommendation honesty.**
   Slice C fixed run-level publication honesty. Slice D has to fix what individual accepted recommendations are actually allowed to ship under a "Final Answer" label.

2. **All-or-nothing finals beat silent subset finals.**
   The repo already has an honest subset artifact in `PARTIAL_ANSWER.*`. Reusing it is better than teaching `FINAL_ANSWER.*` to lie by omission.

3. **One runner-owned promotion truth beats duplicated renderer logic.**
   Recommendation admissibility has to be computed once, then projected everywhere else. Otherwise the repo will drift immediately.

## Deferred to TODOS.md

Items intentionally deferred out of this iteration:

- trust as a dedicated attestation layer over bounded output
- a richer caveat taxonomy instead of raw `accept_with_caveat`
- broader late-auditor validator-policy rewrites
- `BEST_DRAFT` ranking changes tied to admissibility semantics
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
| 8 | Eng | Defer display-vs-audit evidence splitting out of Slice B and keep one canonical closure-proof truth source inside this slice | mechanical | P3 pragmatic | Slice B needs one deterministic closure-proof implementation, not a second evidence-policy decision bundled into the same diff | blind cap increase or dual truth sources |
| 9 | Eng | Defer attestation-layer redesign to backlog | mechanical | P2 boil lakes | It is still a valid next move, but it is larger than this branch needs right now | doing the architecture rewrite in this iteration |
| 10 | Eng | Skip design review | mechanical | P3 pragmatic | This plan has no UI scope and the affected files are harness/runtime/docs/test surfaces only | forcing a design pass with no UI changes |
| 11 | CEO | Reframe the active next slice from stale evidence-cap work to trust artifact publishability | mechanical | P1 completeness | The cap and markdown-residue work already landed, but trust can still ship `FINAL_ANSWER.*` while audit debt only appears as a warning | continuing to treat old Slice C notes as current |
| 12 | Eng | Combine publish-blocker gating and display projection into one output-policy slice | taste | P3 pragmatic | Both concerns touch the same downstream files, and splitting them would create two small but overlapping follow-up slices | publishability-only slice, projection-only slice |
| 13 | Eng | Keep display projection renderer-owned instead of adding model-authored `display_*` fields | mechanical | P5 explicit over clever | JSON/provenance already hold the canonical truth, so dual fields would only create drift risk | prompt/schema migration for display refs |
| 14 | Eng | Treat unbound provenance, unresolved topics, and semantic warnings as trust publish blockers | mechanical | P1 completeness | Those are audit-debt states, not cosmetic caveats, and partial publication is already stricter on the same seam | letting FINAL_ANSWER publish with unresolved audit debt |
| 15 | Eng | Keep low reviewer issues, `accept_with_caveat`, and inference-only acceptance as advisory-only causes | taste | P3 pragmatic | These still matter and should stay visible, but they are weaker than provenance/topic incompleteness and should not automatically block shipment | making every trust warning publish-blocking |
| 16 | Eng | Skip design review again for Slice C | mechanical | P3 pragmatic | The active slice only touches harness/runtime/reporting/docs/tests and has no UI implementation surface | forcing a design pass with no UI changes |
| 17 | CEO | Reframe the active next slice from landed Slice C work to trust recommendation admissibility and artifact promotion | mechanical | P1 completeness | The remaining user-facing gap is no longer run-level publishability. It is what recommendation states trust is allowed to ship under a final artifact label | continuing to treat Slice C as the active next slice |
| 18 | CEO | Keep Slice D payload-neutral and runner-owned | mechanical | P5 explicit over clever | The repo already has the structured truth needed for admissibility, so a new schema family would only add drift risk | caveat-taxonomy schema growth in the same slice |
| 19 | Eng | Keep `FINAL_ANSWER.*` all-or-nothing and route mixed-admissibility runs through `PARTIAL_ANSWER.*` | mechanical | P1 completeness | The repo already has an explicit subset artifact, and silent final filtering would make the final label dishonest | silently pruning `FINAL_ANSWER.*` |
| 20 | Eng | Treat trust `accept_with_caveat` and inference-backed accepted recommendations as partial-only, not final-admissible | taste | P1 completeness | Trust mode should make epistemic weakness visible at the artifact boundary, not bury it as a recommendation-level footnote | letting caveated or inferred recommendations stay final-admissible |
| 21 | Eng | Leave `BEST_DRAFT.*` ranking unchanged in the first admissibility pass | mechanical | P3 pragmatic | Ranking is a separate seam and the repo already has an honest final fallback once partial admissibility is exhausted | coupling admissibility to draft ranking in Slice D |
| 22 | Eng | Defer late-auditor overflow as a broader validator-policy rewrite instead of making it the headline slice | taste | P3 pragmatic | The loophole is real, but the clean first move is freezing recommendation admissibility and artifact promotion without reopening validator semantics | making late-auditor overflow the whole Slice D |
| 23 | Eng | Skip design review again for Slice D | mechanical | P3 pragmatic | The active slice only touches harness/runtime/reporting/docs/tests and has no UI implementation surface | forcing a design pass with no UI changes |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | The next slice had to be reframed from generic verdict tightening to trust recommendation admissibility and artifact promotion |
| Codex Review | `codex review` | Independent 2nd opinion | 4 | issues_open | Codex flagged stale Slice C framing, final-artifact dishonesty around caveated or inferred recommendations, and the need to keep `FINAL_ANSWER.*` all-or-nothing |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | Slice D is now locked to one runner-owned admissibility matrix with `PARTIAL_ANSWER.*` as the explicit scoped fallback and `BEST_DRAFT.*` left unchanged |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No UI scope detected in `PLAN.md`, `anvil/harness/*`, or the run artifacts |

**VERDICT:** PLAN UPDATED FOR SLICE D. Highest-priority work is trust recommendation admissibility and artifact promotion on top of the landed Slice C publishability seam. Optional longer-horizon ideas remain captured in `TODOS.md`.
