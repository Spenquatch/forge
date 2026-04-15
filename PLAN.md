# Analysis Review Bounded-Work Redesign Plan

## Purpose

This document is a planning handoff for redesigning the `analysis_review_v1` harness shape so critic and auditor stages finish in a predictable amount of time without depending on fragile provider turn semantics. It is intentionally not implementation-ready. The goal is to capture context, intent, affected surfaces, requirement shifts, and rollout considerations for a follow-on planning/implementation pass.

## Problem Statement

The current `analysis_review_v1` flow asks the critic and auditor to perform broad review work over the proposer output plus the live repository. In practice this has a few failure modes:

- runtime is dominated by open-ended file inspection rather than bounded work
- `max_turns` is provider-specific and unstable as a control mechanism
- `timeout_sec` is only a hard subprocess kill and does not guarantee useful output
- broad prompts encourage redundant file reads and repeated repo exploration
- later review stages can act like full re-reviews instead of issue-closure checks

The desired redesign is to make timeliness come from narrower work contracts, smaller review packets, and more deterministic stage responsibilities.

## Desired Outcome

The future `analysis_review` flow should:

- bound each stage by explicit work scope rather than conversation length
- reduce unnecessary repo exploration in critic/auditor stages
- preserve grounding and recommendation-level review quality
- keep `timeout_sec` only as a final safety fuse
- work across CLI providers without assuming identical turn-budget semantics
- remain compatible with the current harness artifact/reporting model unless an explicit migration is approved

## Current State Summary

Today the analysis-review path is driven by:

- strategy selection and role wiring in [examples/harness/strategies/analysis_review_codex_claude.yaml](/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/analysis_review_codex_claude.yaml:1)
- contract defaults in [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:1)
- prompt builders in [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:320)
- runtime loop orchestration in [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:456)
- review payload schema in [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:305)
- semantic validation in [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:226)
- contract guidance docs in [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md:1)

The current prompt shape still instructs the critic to:

- audit the prior analysis broadly for grounding, omissions, actionability, and scope
- review every recommendation individually
- inspect the live workspace directly as needed

The current auditor prompt still allows the auditor to:

- verify issue closure
- raise new issues
- perform effectively a broad re-review after revisions

The current reviser prompt still tells the reviser to inspect the current workspace directly and revise the full analysis package, which can expand the scope of later review rounds.

## Design Direction

The redesign should shift from "full repo re-review at every stage" to "bounded packet review with narrowly scoped verification."

### High-Level Shape

Recommended future shape:

1. Proposer produces a bounded analysis draft plus a review packet.
2. Critic validates the packet, not the whole repo.
3. Reviser resolves only the issue ledger.
4. Auditor verifies issue closure first and only escalates when a true new blocker appears.

### Key Principle

Stage runtime should be bounded by:

- explicit review surfaces
- evidence budgets
- issue budgets
- narrower schemas and output expectations

Stage runtime should not primarily be bounded by:

- provider turn caps
- hard subprocess timeout
- open-ended "inspect whatever looks relevant" prompting

## Recommended Requirement Changes

### 1. Add Review Packet Semantics

The proposer output should be extended with an explicit review packet concept. This may be encoded directly in proposer output or split into a derived intermediate artifact.

Recommended new concepts:

- `primary_evidence`: 1-3 canonical evidence refs per recommendation
- `review_surface`: explicit file sets per recommendation
- `must_check_files`: files the critic must validate
- `optional_check_files`: files the critic may consult only if needed
- `evidence_budget` or equivalent guidance: cap on extra exploration

Intent:

- make critic work deterministic
- prevent the critic from rediscovering the whole repo
- make later stages review the proposer's grounding decisions, not restart the task

### 2. Narrow Critic Scope

The critic should no longer be treated as an open-ended repo auditor.

Recommended critic contract changes:

- review only proposer recommendations, cited evidence, task `files_hint`, and bounded optional files
- do not perform broad repo exploration unless cited evidence is insufficient or contradictory
- cap the number of issues the critic may raise in a normal pass
- cap the number of new missed-topic discoveries
- prefer validating existing recommendations over hunting for new opportunities

Suggested operational defaults for a future design pass:

- at most 5 issues total in a critic pass
- at most 2 new missed-topic issues
- no broad repo exploration without an explicit justification field

### 3. Narrow Auditor Scope Further

The auditor should become an issue-closure verifier, not a second critic.

Recommended auditor contract changes:

- default responsibility is verifying closure of existing open issues
- only raise new medium-or-higher issues when:
  - the reviser created them, or
  - the earlier critic clearly missed them within the bounded review surface
- require a stronger explanation for new issues raised after round 0
- disallow broad repo exploration by default

### 4. Keep Reviser Focused on Open Issues

The reviser should not restart the analysis from scratch.

Recommended reviser changes:

- revise only against the open issue ledger
- preserve already-accepted recommendations wherever possible
- inspect only:
  - files referenced by proposer evidence
  - files referenced by critic issues
  - immediately adjacent lines when necessary
- avoid adding new recommendations unless needed to satisfy a logged gap

### 5. Replace Turn-Budget Dependence with Work Budgets

The redesign should not rely on `max_turns` as the primary control surface.

Preferred controls:

- prompt-level work-scope restrictions
- file review caps
- issue caps
- recommendation-count caps
- smaller structured packets
- provider-native budget controls when available
- `timeout_sec` retained only as the final hard stop

## Prompting Changes Required

The main shape change must be encoded in prompt text, not just docs.

### Prompt Surfaces

- [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:320)

Specific prompt builders expected to change:

- `build_analysis_proposer_prompt`
- `build_analysis_critic_prompt`
- `build_analysis_auditor_prompt`
- `build_analysis_reviser_prompt`

### Critic Prompt Intent Changes

The critic prompt should explicitly say:

- validate recommendations against cited evidence first
- only inspect additional files if cited evidence is insufficient or contradictory
- do not perform open-ended repo exploration
- raise at most a bounded number of issues
- prefer validating current recommendations over discovering new topics

### Auditor Prompt Intent Changes

The auditor prompt should explicitly say:

- verify closure of the issue ledger first
- do not perform broad re-review
- only raise new issues when clearly justified
- remain inside the bounded review surface unless there is a contradiction

### Reviser Prompt Intent Changes

The reviser prompt should explicitly say:

- fix the open issue ledger, not the entire analysis package
- do not restart analysis from scratch
- preserve accepted recommendations when possible

## Contract and Schema Changes Required

### Contract Surface

- [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:1)
- [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md:1)

Expected contract evolution areas:

- bounded review surface rules
- issue budget / missed-topic budget policy
- distinction between packet validation and broad workspace review
- stronger auditor constraints
- explicit review packet requirements if adopted

This likely warrants a contract version bump rather than silent in-place behavior drift.

### Schema Surface

- [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:305)

Potential schema additions:

- proposer-side packet metadata fields
- recommendation-level `primary_evidence`
- recommendation-level `review_surface`
- optional justification field when critic/auditor leaves the bounded review surface

The implementation planner should decide whether these belong in:

- the proposer schema directly
- an intermediate packet artifact
- both

## Runner and Orchestration Changes Required

### Runtime Surfaces

- [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py:456)
- [anvil/harness/subgraphs/analysis_review_v1.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/subgraphs/analysis_review_v1.py:1)

Expected runtime changes:

- pass bounded review packet context into critic/auditor stages
- preserve and surface packet metadata in artifacts and summaries
- possibly reduce default review loop behavior for normal runs
- keep a clear distinction between:
  - first-pass critique
  - issue-ledger revision
  - issue-closure audit

Potential follow-on design consideration:

- make extra review loops conditional on unresolved high-severity blockers rather than always allowing broad repeat passes

## Semantic Validation Changes Required

### Validation Surface

- [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:226)

Expected future validation additions:

- proposer packet fields are present and internally coherent
- critic/auditor do not exceed configured issue or missed-topic budgets unless explicitly justified
- recommendation reviews align with packet recommendation indices
- reviewer outputs that claim new missed topics include bounded-scope justification

## Reporting and Artifact Changes Required

### Reporting Surfaces

- [anvil/harness/report.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/report.py:54)
- [anvil/harness/reporting.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/reporting.py:33)
- [docs/project_management/adrs/draft/ADR-0024-harness-state-and-artifact-contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/project_management/adrs/draft/ADR-0024-harness-state-and-artifact-contract.md:1)

Recommended reporting outcomes:

- show when review was packet-bounded vs. broad
- record when a reviewer stepped outside its bounded review surface
- show issue-budget and missed-topic-budget usage
- preserve enough information for operators to understand why a review was fast or slow

## Strategy and Configuration Touch Surfaces

### Strategy Surface

- [examples/harness/strategies/analysis_review_codex_claude.yaml](/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/analysis_review_codex_claude.yaml:1)

This strategy will likely need a follow-on update for:

- lower dependence on provider turn caps
- possible explicit "bounded review mode" knobs
- narrower review-loop defaults

### Provider Configuration Surface

- [config/models.yaml](/Users/spensermcconnell/__Active_Code/forge/config/models.yaml:122)

This plan does not require provider-specific behavior changes as the primary mechanism. The redesign should be provider-agnostic at the harness level. Provider-specific tuning may remain useful, but it should not be the main solution.

## Test Surfaces Likely Impacted

- [tests/test_harness_prompt_consistency.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py:49)
- [tests/test_harness_analysis_contract.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py:42)
- [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:333)
- [tests/test_harness_semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py:47)
- [tests/fixtures/harness/analysis_review_semantic_cases.json](/Users/spensermcconnell/__Active_Code/forge/tests/fixtures/harness/analysis_review_semantic_cases.json:1)

The planning pass should explicitly account for:

- prompt wording changes
- schema shape changes
- semantic validation rule updates
- report shape expectations

## Non-Goals

This planning effort is not trying to:

- redesign the entire harness architecture
- replace `timeout_sec`
- introduce provider-specific review semantics as the main control path
- guarantee identical runtime behavior across all providers
- fully specify exact schema fields or final prompt wording in this document

## Open Questions for the Planning Agent

The follow-on planning pass should resolve these:

1. Should the bounded review packet be:
   - embedded in proposer output
   - generated as a derived harness artifact
   - both

2. Should issue and missed-topic budgets live in:
   - the contract
   - strategy config
   - task config

3. Should the auditor be allowed any new issue creation after round 0 without an explicit elevated threshold?

4. Should there be a new strategy kind or contract version for bounded analysis review, or should `analysis_review_v1` evolve in place?

5. Should proposer outputs be forced to include smaller evidence sets to keep later stages bounded?

6. Should the runner support a "standard" vs "deep" review mode?

## Suggested Rollout Shape

Recommended sequencing for implementation planning:

1. Define the new contract shape and bounded-review rules.
2. Decide whether a packet artifact is explicit or implicit.
3. Update prompt builders to enforce the new role boundaries.
4. Update schemas and semantic validation.
5. Update runner/reporting to preserve the new packet metadata and bounded-scope signals.
6. Update example strategy/docs/tests.
7. Tune provider configs only after the bounded-work redesign lands.

## Summary

The central recommendation is to redesign `analysis_review` around bounded work packets and narrower stage roles. The critic should validate proposer evidence, not rediscover the repository. The auditor should verify issue closure, not act like a second broad critic. The reviser should resolve the issue ledger, not restart the task. Runtime predictability should come from work scope and packet design, with `timeout_sec` retained only as the hard safety fuse.
