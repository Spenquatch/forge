<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260420-183924.md -->

# Next Iteration Plan: Trust Auditability and Topic Accounting

## Purpose

The bounded/trust split landed. That part is real.

The next iteration should make the trust tier feel dependable instead of merely stricter in reporting. The current repo already has explicit strategy kinds, a unified contract, issue-ledger carry-forward, provenance binding, and `accepted_with_warnings`. The remaining gap is that some reviewer concerns still disappear too easily, and some trust evidence is bound as payload shape instead of as auditable review proof.

This plan turns the outside notes into one tight follow-up iteration:

1. make `missing_topics` first-class tracked state
2. make trust review provenance carry structured review evidence, not just payload hashes
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
| Extend the current unified path with topic accounting and stronger trust evidence | medium | minimal diff, preserves shipped split, directly fixes observed artifacts | still one engine, not a separate attestation layer | recommended |
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

### NOT in scope

- converting trust into a separate attestation pass over `BEST_DRAFT`
- hard read tracing or sandbox-proof file access
- a second analysis-review runner or subgraph
- provider retuning as the primary fix for auditability
- UI work, design-system work, or any frontend review pass

## Eng Review

### Architectural direction

Keep one analysis-review execution path and add two new first-class concepts:

1. a **topic ledger** alongside the issue ledger
2. a **review evidence surface** for critic/auditor outputs that can be normalized and provenance-bound just like analysis payload refs

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
    ├── review provenance with non-zero refs
    ├── clean strengths/uncertainties rendering
    └── explicit downgrade causes
```

### Priority 1: Promote missing topics into tracked state

**Why it matters**

Right now the system can tell a coherent story about issues. It cannot yet tell the same story about topics that the critic says are missing.

That is the biggest honesty gap left.

**Modules**

- `anvil/harness/schemas.py`
- `anvil/harness/runner.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/prompts.py`
- `anvil/harness/report.py`
- `anvil/harness/reporting.py`

**Changes**

- replace raw `missing_topics: string[]` as the only lifecycle surface
- add a typed topic record, either directly in the payload or as a runner-normalized ledger:
  - `topic_id`
  - `title`
  - `severity`
  - `status`
  - `introduced_by`
  - `incorporated_into_recommendation_index` or `waive_reason`
- require the auditor or reviser path to classify prior open topics just like prior open issues
- surface topic carry-forward/resolution in `summary.json`, `REPORT.md`, and `FINAL_ANSWER.md` when relevant

**Acceptance**

- a topic raised by the critic cannot silently disappear
- every open topic is resolved, carried forward, or waived
- final artifacts can explain what happened to each prior topic

### Priority 2: Add structured review evidence to trust mode

**Why it matters**

The current trust run proves which review payload was accepted. It does not yet prove what structured evidence the review itself checked.

That is why provenance shows `bound` while review refs still show `0`.

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
  - `verified_issue_refs` or equivalent review-stage evidence field
- normalize those refs in `_normalize_analysis_review_payload()`
- include normalized review refs in `_final_payload_provenance_records()`
- in trust mode, require non-zero structured review refs when the review makes concrete closure claims

**Acceptance**

- trust review provenance records show non-zero normalized refs when the review closes issues or topics
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

5. `tests/fixtures/harness/analysis_review_semantic_cases.json`
   Add positive and negative topic/evidence-budget fixtures.

### Verification commands

```bash
poetry run pytest -q \
  tests/test_harness_analysis_contract.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_reporting.py \
  tests/test_harness_runner.py \
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
| B. Trust review evidence | `schemas`, `runner`, `semantic_validation`, `prompts`, `docs` | bind structured review refs into provenance | none |
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

## Cross-Phase Themes

Two themes showed up everywhere:

1. **Lifecycle honesty beats raw strictness.**
   The biggest remaining gap is not another cap or another warning. It is incomplete accounting for what happened to concerns.

2. **Trust needs auditable evidence, not just caveat language.**
   The current trust run already sounds more honest. The next step is making it easier to verify why.

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
| 3 | CEO | Make topic tracking the top priority | mechanical | P1 completeness | It is the clearest remaining honesty hole in the trust run | leaving `missing_topics` as strings only |
| 4 | Eng | Add structured review evidence refs instead of only tightening report prose | mechanical | P5 explicit over clever | Trust needs auditable review proof, not just stronger caveat copy | prompt-only hardening |
| 5 | Eng | Split display evidence from audit evidence rather than simply raising the cap everywhere | taste | P3 pragmatic | This preserves bounded readability while fixing trust auditability | global cap increase only |
| 6 | Eng | Tighten trust late-auditor semantics in this tranche | taste | P1 completeness | Trust mode should be less tolerant of late medium+ churn, not more | leaving the current `warn` default untouched |
| 7 | Eng | Defer attestation-layer redesign to backlog | mechanical | P2 boil lakes | It is a valid next move, but it is a larger orchestration change than this branch needs right now | doing the architecture rewrite in this iteration |
| 8 | Eng | Skip design review | mechanical | P3 pragmatic | This plan has no UI scope and the affected files are harness/runtime/docs/test surfaces only | forcing a design pass with no UI changes |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | The split shipped, but trust still lacks topic lifecycle accounting and strong enough review evidence |
| Codex Review | `codex review` | Independent 2nd opinion | 0 | unavailable | Outside voice not run in this turn |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | Topic ledger, review evidence binding, evidence-budget split, renderer cleanup, and stricter trust acceptance remain |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No UI scope detected in `PLAN.md`, `anvil/harness/*`, or the run artifacts |

**VERDICT:** PLAN UPDATED FOR NEXT ITERATION. Highest-priority work is topic accounting plus structured trust review evidence. Optional longer-horizon ideas are captured in `TODOS.md`.
