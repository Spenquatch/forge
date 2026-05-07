# ORCH_PLAN: Trust Attestation Over Bounded Output (M2)

## Summary

Target branch: `feat/bounded-work-redesign`  
Implementation source of truth: `/Users/spensermcconnell/__Active_Code/forge/PLAN.md`

This orchestration plan supersedes the prior M1-only orchestration document.

M2 outcome:

- trust execution mode becomes a real strategy-level switch
- legacy trust remains available
- attestation-mode trust runs a bounded producer lane first
- trust then reviews the frozen `bounded_attestation_input`
- publication and artifact-selection logic remain unchanged

## Hard Guards

1. `PLAN.md` is authoritative. If this file conflicts with `PLAN.md`, follow `PLAN.md`.
2. M2 only. Do not rewrite reporting, artifact selection, or README product copy.
3. Old trust behavior must remain available through `legacy_full_review`.
4. The public trust strategy kind stays `analysis_review_trust_v1`.
5. Do not invent a second cutover knob. Use `trust_review.execution_mode`.
6. Do not create a second trust-authored `final_analysis` in attestation mode.
7. If work requires `anvil/harness/report.py` or `anvil/harness/reporting.py`, stop and prove the regression first.
8. If full-suite failures are unrelated or ambiguous, stop and surface evidence.

## Expected File Surfaces

Primary implementation files:

- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/types.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py`
- `/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md`

Example strategies:

- `/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/analysis_review_trust_attestation_codex_claude.yaml`
- `/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml`
- `/Users/spensermcconnell/__Active_Code/forge/examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml`

Required tests:

- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_semantic_validation.py`
- `/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_analysis_contract.py`

## Workstreams

### WS1: Strategy + Contract Surface

Owner scope:

- `types.py`
- `contracts.py`
- attestation example strategies
- contract tests that assert config parsing and contract serialization

Required outcome:

- `trust_review.execution_mode` parses, round-trips, defaults to `legacy_full_review`, and reaches the contract

### WS2: Runner + Prompt Cutover

Owner scope:

- `runner.py`
- `prompts.py`
- runner tests
- prompt-consistency tests

Required outcome:

- `legacy_full_review` uses today's path
- `attestation_over_bounded` runs bounded producer first, then trust attestation review
- attestation mode reuses bounded `final_analysis`
- stage bookkeeping does not confuse bounded producer review stages with final trust attestation stages

### WS3: Validation + Parity

Owner scope:

- `semantic_validation.py`
- semantic-validation tests
- fixture or matrix-style runner tests for seam/artifact request-gate parity

Required outcome:

- attestation review coverage is dense across bounded recommendations
- provenance and closure proof still work
- legacy trust remains green

## Suggested Task Order

1. Land WS1 first.
2. Land WS2 second.
3. Land WS3 after the runner branch exists.
4. Run the targeted parity matrix only after all three are merged.

This order matters. Runner branching without a real execution-mode input is fake progress.

## Verification Gate

Minimum commands before closeout:

- `poetry run pytest -q tests/test_harness_analysis_contract.py`
- `poetry run pytest -q tests/test_harness_prompt_consistency.py`
- `poetry run pytest -q tests/test_harness_semantic_validation.py`
- `poetry run pytest -q tests/test_harness_runner.py -k "trust or bounded_attestation or execution_mode"`

If the runner tests require narrower targeting because of runtime, the closeout note must list the exact filters used.

## Closeout Criteria

Do not call the orchestration complete until:

- attestation strategies exist and load
- legacy trust still passes
- attestation trust persists and consumes `bounded_attestation_input`
- attestation trust does not produce a second trust-authored analysis payload
- parity tests cover seam and artifact request-gate cases
- no report/artifact-selection file had to change

That is the M2 line. Stay on it.
