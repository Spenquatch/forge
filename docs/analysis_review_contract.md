# Analysis-review contract

The analysis-review harness is driven by a typed contract in `anvil/harness/contracts.py`.

## Why this exists

The contract keeps the proposer, critic, reviser, auditor, runner stop logic, and reporting aligned. Without a shared contract, prompt text and runtime behavior drift into contradictory expectations.

`analysis_review_v1_contract_v3` adds bounded-review semantics so review depth comes from explicit harness rules instead of open-ended reviewer behavior.

## What the contract governs

The current contract covers:

- stop policy and loop limits
- partial-acceptance policy
- required analysis sections
- bounded-review policy
- issue-ledger requirements
- recommendation-level review requirements
- the shared confidence rubric
- the issue taxonomy and default blocking classes

## Bounded-review policy

The bounded-review policy is the single source of truth for review caps. Prompts must render these values from the contract, and semantic validation must enforce the same values.

Current defaults:

- recommendation evidence refs: `1..3`
- `review_surface.must_check_files`: `1..3`
- `review_surface.optional_check_files`: `0..2`
- critic issue cap: `5`
- critic new-topic cap: `2`
- auditor new medium-or-higher issue cap after round 0: `1`
- scope escapes require non-empty reasons

The proposer and reviser now emit a bounded `review_surface` on each recommendation:

```json
{
  "must_check_files": ["path/a.py"],
  "optional_check_files": ["path/b.py"],
  "scope_note": "Validate timeout handling only."
}
```

Critic and auditor payloads also carry explicit `scope_escapes` when they leave the bounded surface:

```json
{
  "scope_escapes": [
    {
      "path": "anvil/harness/state.py",
      "reason": "Cited evidence was contradictory, so adjacent state logic had to be checked."
    }
  ]
}
```

## Semantic validation

JSON schema validation is necessary but not sufficient. The harness runs semantic validation after structured output is produced.

Examples of semantic checks:

- proposer/reviser outputs must satisfy the task minimum recommendation count
- recommendation evidence counts must stay within the bounded-review cap
- `review_surface.must_check_files` must stay within cap and remain a subset of `files_reviewed`
- `review_surface.optional_check_files` must stay within cap
- critics must stay within the issue cap and new-topic cap
- revisers must return an `issue_resolution_map` entry for every open issue ID
- auditors must explicitly classify every prior open issue as resolved, carried forward, or waived
- new medium-or-higher auditor issues after round 0 must include `why_not_raised_earlier`
- every `scope_escapes[].reason` must be non-empty

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

The contract is the source of truth. Prompts, runner logic, schema expectations, semantic validation, and reporting should derive from it instead of duplicating cap numbers.
