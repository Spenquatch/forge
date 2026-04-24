# Analysis-review contract

The analysis-review harness is driven by a typed contract in `anvil/harness/contracts.py`.

## Why this exists

The contract keeps the proposer, critic, reviser, auditor, runner stop logic, and reporting aligned. Without a shared contract, prompt text and runtime behavior drift into contradictory expectations.

`analysis_review_v1_contract_v7` keeps the bounded-review rules from v6, keeps trust-mode recommendation evidence explicitly uncapped, and adds runner-owned recommendation admissibility for bounded and trust artifact selection without changing the model-authored payload shape.

## What the contract governs

The current contract covers:

- effective strategy surface: `strategy_kind` plus explicit `mode`
- stop policy and loop limits
- partial-acceptance policy
- required analysis sections
- bounded-review policy
- trust-review policy
- issue-ledger requirements
- recommendation-level review requirements
- the shared confidence rubric
- the issue taxonomy and default blocking classes

The contract now serializes:

```json
{
  "contract_version": "analysis_review_v1_contract_v7",
  "strategy_kind": "analysis_review_v1",
  "mode": "bounded",
  "effective_strategy": {
    "kind": "analysis_review_v1",
    "mode": "bounded"
  }
}
```

Today the legacy `analysis_review_v1` surface still resolves to bounded behavior. When explicit public strategy kinds land, `analysis_review_bounded_v1` and `analysis_review_trust_v1` should serialize through the same contract with different `mode` and `trust_review` values.

## Unified policy model

The v7 contract keeps one analysis-review contract type and adds one `TrustReviewPolicy`.

Why this is preferable to mode-specific contract classes:

- one source of truth for prompts and validation
- bounded and trust stay comparable
- mode-specific behavior lives in policy fields instead of branching the whole type system

The trust policy covers:

- whether blocking-class overrides require a reason
- whether `verified_evidence_refs` must stay a subset of recommendation evidence
- whether non-inferred `affected_files` require evidence or checked-file coverage
- whether payload provenance binding is expected
- whether clean acceptance should be downgraded on semantic warnings
- whether inference-backed acceptance should be downgraded to a caveated acceptance
- whether late auditor medium-or-higher issues are treated as errors or warnings

## Topic lifecycle artifact contract

Slice A topic lifecycle is exported through the run summary, not inferred ad hoc from stage-local payloads.

`summary.json["topic_ledger"]` is the canonical machine-readable contract and each entry uses this shape:

```json
{
  "topic_id": "TOPIC-001",
  "title": "Recommendation 1 needs a concrete fallback classification.",
  "severity": "medium",
  "evidence": "The draft names the operator path but not the fallback state taxonomy.",
  "recommendation_index": 1,
  "introduced_by": "critic",
  "introduced_in_stage_index": 2,
  "resolution_status": "addressed",
  "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
  "resolved_in_stage_index": 4
}
```

Rules:

- `introduced_by` is the role that first raised the topic.
- `introduced_in_stage_index` is the concrete stage index where the topic entered the ledger.
- `resolution_status` uses the Slice A vocabulary: `open | addressed | carried_forward | waived | disagree`.
- `resolved_in_stage_index` is nullable and is only set when the topic reaches a non-open terminal classification such as `addressed`, `waived`, or `disagree`.

`analysis_review_status` keeps the existing ID lists for compatibility, but they derive from the canonical ledger:

- `open_topic_ids` = topics whose ledger status is `open`
- `carried_forward_topic_ids` = topics whose ledger status is `carried_forward`
- `resolved_topic_ids` = topics whose ledger status is `addressed`
- `waived_topic_ids` = topics whose ledger status is `waived`
- `disagreed_topic_ids` = topics whose ledger status is `disagree`

For `accepted_partial`, the shipped subset must also be topic-clean:

- a recommendation can only remain in the partial artifact when its linked topics are terminal (`addressed`, `waived`, or `disagree`)
- a topic left `open` or `carried_forward` removes its `recommendation_index` from the partial subset
- an unresolved topic without a usable `recommendation_index` blocks partial acceptance entirely, because no clean subset can be proven

`REPORT.md` renders the same ledger in a row-shaped `## Topic Lifecycle` table, while `FINAL_ANSWER.md` keeps a compact bullet summary of the same canonical records.

## Recommendation withholding and artifact selection

Slice D adds a runner-owned recommendation withholding ledger under `analysis_review_status.recommendation_admissibility`:

```json
{
  "analysis_review_status": {
    "recommendation_admissibility": {
      "final_answer_recommendation_indices": [1],
      "partial_only_recommendation_indices": [2],
      "excluded_recommendation_indices": [3],
      "reasons_by_recommendation_index": {
        "2": ["accepted_with_caveat"],
        "3": ["not_accepted"]
      }
    }
  }
}
```

Rules:

- `final_answer_recommendation_indices`, `partial_only_recommendation_indices`, `excluded_recommendation_indices`, and `reasons_by_recommendation_index` are the frozen field names.
- `recommendation_admissibility` is runner-owned status, not a model-authored payload field. The payload shape remains unchanged.
- `recommendation_admissibility` is canonical in both bounded mode and trust mode, and both modes share the same status object shape.
- `final_answer_recommendation_indices` is the runner-owned canonical published-final subset in both modes.
- In bounded mode, accepted recommendations, including `accept_with_caveat`, stay in `final_answer_recommendation_indices` unless they are topic-blocked.
- In bounded mode, `partial_only_recommendation_indices` stays empty.
- In trust mode, `FINAL_ANSWER.*` is all-or-nothing. Recommendations outside `final_answer_recommendation_indices` are withheld from `FINAL_ANSWER.*`.
- A recommendation stays in `final_answer_recommendation_indices` only when its review verdict is `accept`, its grounding is not `inferred`, and no runner-known per-index topic blocker applies.
- `accepted_with_caveat` and accepted recommendations with `grounding_mode = inferred` move to `partial_only_recommendation_indices`; they are withheld from `FINAL_ANSWER.*` in trust mode.
- Non-accepted recommendations and per-index topic-blocked recommendations move to `excluded_recommendation_indices`.
- `reasons_by_recommendation_index` uses only the canonical reasons `accepted_with_caveat`, `inferred_grounding`, `not_accepted`, and `topic_blocked`.
- The candidate partial subset comes from `final_answer_recommendation_indices + partial_only_recommendation_indices`, but publishing `PARTIAL_ANSWER.*` still reuses the existing partial gates.
- Global topic blockers, provenance gating, and minimum-threshold fallout remain whole-artifact promotion rules. This withholding ledger does not replace them.
- When that scoped partial fallback is rendered, freeze the partial-answer scope lines to `Recommendation indices included in PARTIAL_ANSWER.*: 1, 2`, `Recommendation indices withheld from FINAL_ANSWER.*: 2`, and `Recommendation indices excluded from PARTIAL_ANSWER.*: none`.

Slice C also keeps an explicit publishability layer under `analysis_review_status`:

```json
{
  "analysis_review_status": {
    "content_verdict": "accepted_partial",
    "publishability": {
      "final_answer_publishable": false,
      "blocking_causes": [
        "content verdict is not fully accepted: accepted_partial"
      ]
    }
  }
}
```

Rules:

- `final_answer_publishable` and `blocking_causes` are the frozen field names.
- `analysis_review_status.publishability` is the canonical final publication outcome.
- In trust mode, `accepted_with_warnings` does not guarantee `FINAL_ANSWER.*`.
- Trust-mode final publication is allowed only when the content verdict is `accepted` or `accepted_with_warnings`, provenance is fully bound, no topic IDs remain `open`, no topic IDs remain `carried_forward`, and no final semantic warnings remain.
- Only the exact warning strings `strengths contains both concrete items and none_reason; prefer one or the other.` and `uncertainties contains both concrete items and none_reason; prefer one or the other.` are advisory carveouts. They remain visible warnings, but by themselves they do not add a publishability blocker.
- If the content verdict is not fully accepted, `blocking_causes` must contain exactly one verdict blocker: `content verdict is not fully accepted: <verdict>`.
- `summary.json["artifacts"]["final_artifact"]`, `final_artifact_json`, and `final_artifact_kind` remain the source of truth for what actually shipped.
- Artifact projection finalizes `publishability`; `final_answer_publishable` is `true` exactly when `summary.json["artifacts"]["final_artifact_kind"] == "final_answer"`.
- If trust mode is content-accepted but not final-publishable, artifact selection skips `FINAL_ANSWER.*` and falls through to the existing partial-answer path when eligible, otherwise `BEST_DRAFT.*`.
- Reports and fallback deliverables freeze their wording to `Final publication: publishable|blocked`, `Publication blockers:`, and `Recommendation indices withheld from FINAL_ANSWER.*:`.
- Partial-answer scope lines are frozen only for `PARTIAL_ANSWER.*`: `Recommendation indices included in PARTIAL_ANSWER.*: 1, 2`, `Recommendation indices withheld from FINAL_ANSWER.*: 2`, and `Recommendation indices excluded from PARTIAL_ANSWER.*: none`.
- `REPORT.md` freezes only final-publication / final-withholding wording and does not render `Recommendation indices included in PARTIAL_ANSWER.*` or `Recommendation indices excluded from PARTIAL_ANSWER.*`.
- Topic lifecycle summaries keep `Open topics:` and `Carried-forward topics:` as separate labels; carried-forward items are not folded into open wording.
- Reviewer or model-authored prose may describe quality, caveats, or evidence gaps, but only runner-owned `analysis_review_status.publishability`, `analysis_review_status.recommendation_admissibility`, and `summary.json["artifacts"]` decide artifact eligibility and publication state.

For fully accepted trust runs, `blocking_causes` is deterministic. The list is emitted in this order:

1. provenance blocker first, when present
2. open topic IDs in sorted order
3. carried-forward topic IDs in sorted order
4. one semantic-warning blocker whose summaries preserve `_final_semantic_warning_records()` order and are joined with `; `

This separation is intentional: `content_verdict` classifies the review outcome, `recommendation_admissibility` records which indices remain publishable in `FINAL_ANSWER.*` versus withheld to fallback subsets, and `publishability` is finalized after artifact projection to record whether `FINAL_ANSWER.*` actually ships.

## Bounded-review policy

The bounded-review policy remains the single source of truth for review caps. Prompts must render these values from the contract, and semantic validation must enforce the same values.

Current defaults:

- bounded-mode recommendation evidence refs: `1..3`
- `review_surface.must_check_files`: `1..3`
- `review_surface.optional_check_files`: `0..2`
- evidence cap policy: `trim_to_cap` by default, with task-level `strict` override support
- critic issue cap: `5`
- critic new-topic cap: `2`
- auditor new medium-or-higher issue cap after round 0: `1`
- scope escapes require non-empty reasons

Trust-mode recommendation evidence is intentionally uncapped. Trust runs should preserve every concrete workspace ref needed to support auditability; they do not trim or reject a recommendation solely for carrying more than three evidence refs.

Markdown compaction is renderer-owned and preview-only:

- deliverable markdown previews at most the first `3` recommendation evidence refs
- `REPORT.md` previews at most the first `2` `checked_files` values and the first `2` `verified_evidence_refs` values in review-provenance cells
- omitted items render as deterministic `(+N more)` previews
- JSON artifacts, including the selected deliverable JSON and `summary.json`, remain full fidelity and must not gain parallel `display_*` or `audit_*` field families

## Shared payload family

Do not split bounded and trust mode into separate JSON payload families.

Use one additive recommendation payload shape:

```json
{
  "classification": "confirmed_issue",
  "priority": "high",
  "title": "Tighten prompt-surface contract wording",
  "rationale": "The prompts duplicate trust assumptions instead of deriving them from the contract.",
  "evidence": [
    "anvil/harness/prompts.py",
    "anvil/harness/contracts.py"
  ],
  "verified_evidence_refs": [
    "anvil/harness/prompts.py"
  ],
  "checked_files": [
    "anvil/harness/prompts.py"
  ],
  "affected_files": [
    "anvil/harness/prompts.py",
    "anvil/harness/schemas.py"
  ],
  "grounding_mode": "direct",
  "proposed_change": "Render trust behavior from the contract blocks instead of duplicating it in each role prompt.",
  "confidence": 0.93,
  "review_surface": {
    "must_check_files": [
      "anvil/harness/prompts.py"
    ],
    "optional_check_files": [
      "anvil/harness/schemas.py"
    ],
    "scope_note": "Validate prompt/schema alignment only."
  }
}
```

Bounded mode and trust mode share that shape. The difference is policy:

- bounded mode populates the shared admissibility fields without using trust-only `partial_only` downgrades
- trust mode populates the same shape and is expected to enforce stricter downstream semantics

Critic and auditor issue payloads stay on the same shared family and add `blocking_class_override_reason` when they intentionally override the default blocking class implied by issue kind:

```json
{
  "issue_id": "AR-003",
  "severity": "medium",
  "kind": "confidence_calibration",
  "blocking_class": "actionability",
  "blocking_class_override_reason": "The confidence overstatement changes whether the recommendation is safe to act on.",
  "title": "Recommendation confidence overstates observed evidence",
  "evidence": "The recommendation cites only one file but claims a repo-wide invariant.",
  "repair_hint": "Downgrade confidence or narrow the claim."
}
```

Review-stage critic and auditor payloads also support structured review refs on the shared family:

- required top-level `files_reviewed`
- `recommendation_reviews[*].checked_files`
- `recommendation_reviews[*].verified_evidence_refs`
- required top-level `issue_closure_reviews`
- required top-level `topic_closure_reviews`

Those refs are the path-based audit surface for review provenance. `files_reviewed` records review-stage context, not proof by itself. The contract now has two closure-proof paths:

- `recommendation_reviews[*]` prove recommendation-linked closures for issues or topics whose `recommendation_index` points at the reviewed recommendation
- `issue_closure_reviews[*]` and `topic_closure_reviews[*]` prove global closures when the closed issue or topic has `recommendation_index = null`

Additional rules:

- one scoped closure review maps to exactly one ID: one `issue_closure_reviews[*]` entry per `issue_id`, one `topic_closure_reviews[*]` entry per `topic_id`
- unrelated recommendation review refs do not satisfy global issue/topic closure proof
- recommendation-linked closures do not need extra scoped proof when their recommendation is already covered by the matching `recommendation_reviews[*]` entry
- human-readable issue/topic `evidence` text remains narrative; closure proof binds to the structured path refs above
- `issue_closure_reviews` and `topic_closure_reviews` are required top-level arrays but may be empty when no `recommendation_index = null` closures are being proven

## Trust semantics

Trust mode is stricter, but it is still the same harness path.

What trust mode adds conceptually:

- provenance-aware evidence accounting
- explicit direct vs mixed vs inferred grounding via `grounding_mode`
- clearer distinction between files checked and files claimed to be affected
- justification when issue taxonomy is intentionally overridden
- cleaner caveat semantics for accepted recommendations

What trust mode does **not** add in this contract alone:

- hard read sandboxing
- a second subgraph
- a second runner implementation

## Semantic validation expectations

JSON schema validation is necessary but not sufficient. The harness runs semantic validation after structured output is produced.

Examples of the existing and intended v4 semantic checks:

- proposer/reviser outputs must satisfy the task minimum recommendation count
- in bounded mode, recommendation evidence counts must stay within the bounded-review cap
- in trust mode, recommendation evidence counts are uncapped, but every evidence ref must still remain concrete, normalized, in-workspace, and included in `files_reviewed`
- recommendation evidence refs must exist in the workspace snapshot
- recommendation evidence refs must remain a subset of `files_reviewed`
- line-qualified refs such as `path:12-18` should canonicalize to workspace paths before semantic validation
- in bounded mode, oversize evidence lists may be trimmed to cap before semantic validation when the task uses `evidence_cap_policy=trim_to_cap`
- `review_surface.must_check_files` must stay within cap and remain a subset of `files_reviewed`
- `review_surface.optional_check_files` must stay within cap
- critics must stay within the issue cap and new-topic cap
- revisers must return an `issue_resolution_map` entry for every open issue ID
- auditors must explicitly classify every prior open issue as resolved, carried forward, or waived
- new medium-or-higher auditor issues after round 0 must include `why_not_raised_earlier`
- every `scope_escapes[].reason` must be non-empty
- in trust mode, `verified_evidence_refs` should stay a subset of `evidence`
- in trust mode, non-inferred `affected_files` should be covered by evidence or checked files
- in trust mode, `blocking_class_override_reason` should explain intentional taxonomy overrides
- in trust mode, `files_reviewed` is review context only; closure proof must bind to `recommendation_reviews[*]` for recommendation-linked closures or to `issue_closure_reviews[*]` / `topic_closure_reviews[*]` for `recommendation_index = null` closures
- in trust mode, each scoped closure review must bind exactly one ID, and unrelated recommendation refs do not satisfy global closure proof

Semantic validation failures are surfaced as stage errors and written to a per-stage `semantic_validation.json` artifact.

## Prompt and contract change policy

Contract changes should be reviewed in code review, not approved manually at run time.

When changing the contract:

1. update `anvil/harness/contracts.py`
2. update any affected prompts in `anvil/harness/prompts.py`
3. update runtime enforcement in `anvil/harness/runner.py` or `anvil/harness/semantic_validation.py`
4. update schemas in `anvil/harness/schemas.py` if the payload shape changed
5. update tests and prompt-consistency checks in the same PR
6. update example strategies or docs when defaults or recommended settings change

The contract is the source of truth. Prompts, runner logic, schema expectations, semantic validation, and reporting should derive from it instead of duplicating trust and bounded-review rules in parallel.
