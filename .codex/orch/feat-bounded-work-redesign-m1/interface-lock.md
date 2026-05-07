# Interface Lock

## M1 Scope
- M1 only
- `PLAN.md` is authoritative
- no trust consumption
- no prompt/reporting/example/public-surface changes

## Locked Literals
- handoff key: `bounded_attestation_input`
- schema version: `analysis_review_bounded_attestation_input_v1`
- trust execution modes:
  - `legacy_full_review`
  - `attestation_over_bounded`

## Locked Invariants
- bounded-only emission
- build from finalized bounded analysis only
- same payload mirrored in top-level summary and `run_details`
- semantic validation must fail loudly
- forbidden publication fields must be absent
- recommendation order is frozen
- `analysis_review_schema()` remains unchanged

## File Ownership
- M1-T02:
  - `anvil/harness/contracts.py`
  - `anvil/harness/schemas.py`
  - `docs/analysis_review_contract.md`
  - `tests/test_harness_analysis_contract.py`
- M1-T03:
  - `anvil/harness/runner.py`
  - `anvil/harness/semantic_validation.py`
  - `tests/test_harness_runner.py`
  - `tests/test_harness_semantic_validation.py`
