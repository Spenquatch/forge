# Analysis-review contract

The analysis-review harness is driven by a typed contract in `anvil/harness/contracts.py`.

## Why this exists

The contract keeps the proposer, critic, reviser, auditor, runner stop logic, and reporting aligned. Without a shared contract, stage prompts can drift into contradictory expectations such as:

- the reviser prioritizing only the "strongest" issues
- the auditor requiring zero remaining medium blockers
- the report treating useful-but-imperfect runs as total failures

## What the contract governs

The current contract covers:

- stop policy and loop limits
- partial-acceptance policy
- required analysis sections
- issue-ledger requirements
- recommendation-level review requirements
- the shared confidence rubric
- the issue taxonomy and default blocking classes

## Semantic validation

JSON schema validation is necessary but not sufficient. The harness now runs semantic validation after structured output is produced.

Examples of semantic checks:

- proposer/reviser outputs must satisfy the task minimum recommendation count
- `strengths` and `uncertainties` must either contain concrete items or explain why they are empty with `none_reason`
- `files_reviewed` must contain real inspected paths
- revisers must return an `issue_resolution_map` entry for every open issue ID
- critics/auditors must review every recommendation individually
- auditors must explicitly classify every prior open issue as resolved, carried forward, or waived

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

The contract is the source of truth. Prompts, runner logic, schema expectations, and reporting should all derive from it or agree with it.

## Current tuned defaults

After the Priority 0/1 structural fixes landed, the recommended analysis-review example strategy now uses:

- proposer effort: `medium`
- max review loops: `3`

These tuning changes are intentionally secondary to the contract and semantic-validation changes. They improve first-draft quality and convergence, but they are not a substitute for issue-ledger enforcement or partial-acceptance semantics.
