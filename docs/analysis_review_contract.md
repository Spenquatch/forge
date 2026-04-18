# Analysis-review contract

The analysis-review harness is driven by a typed contract in `anvil/harness/contracts.py`.

## Why this exists

The contract keeps the proposer, critic, reviser, auditor, runner stop logic, and reporting aligned. Without a shared contract, prompt text and runtime behavior drift into contradictory expectations.

`analysis_review_v1_contract_v5` keeps the bounded-review rules from v4, makes evidence-cap handling explicit, and keeps one unified trust policy instead of inventing a second payload family.

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
  "contract_version": "analysis_review_v1_contract_v5",
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

The v4 contract keeps one analysis-review contract type and adds one `TrustReviewPolicy`.

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

## Bounded-review policy

The bounded-review policy remains the single source of truth for review caps. Prompts must render these values from the contract, and semantic validation must enforce the same values.

Current defaults:

- recommendation evidence refs: `1..3`
- `review_surface.must_check_files`: `1..3`
- `review_surface.optional_check_files`: `0..2`
- evidence cap policy: `trim_to_cap` by default, with task-level `strict` override support
- critic issue cap: `5`
- critic new-topic cap: `2`
- auditor new medium-or-higher issue cap after round 0: `1`
- scope escapes require non-empty reasons

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

- bounded mode may omit the trust-oriented fields
- trust mode should populate them deliberately and is expected to enforce stricter semantics downstream

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
- recommendation evidence counts must stay within the bounded-review cap
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
