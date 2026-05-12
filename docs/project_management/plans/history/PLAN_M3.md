# PLAN: M3 Attestation-First Trust Cutover

Status: draft for review
Branch: `feat/bounded-work-redesign`
Design source: `/Users/spensermcconnell/.gstack/projects/forge/spensermcconnell-feat-bounded-work-redesign-design-20260507-082505.md`
Supersedes: none

## Plan Summary

M2 is effectively complete on the current tree.

Validated on 2026-05-07:

- `poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"` -> `5 passed, 24 deselected`
- `poetry run pytest -q tests/test_harness_prompt_consistency.py -k "attestation or trust"` -> `3 passed, 5 deselected`
- `poetry run pytest -q tests/test_harness_runner.py -k "attestation or bounded_attestation_input"` -> `12 passed, 109 deselected`
- `poetry run pytest -q tests/test_harness_semantic_validation.py -k "attestation or bounded_attestation_input"` -> `13 passed, 76 deselected`
- `poetry run pytest -q tests/test_harness_reporting.py -k "apply_final_artifacts"` -> `23 passed, 29 deselected`

The important consequence is that M3 is smaller than the original design doc made
it sound.

M2 already moved the hard publication inputs into runner-owned status sourced from
the attestation path. `apply_final_artifacts(...)` is still untouched, but it is
already consuming runner-owned status rather than a second trust-authored answer
payload.

So M3 should not be a broad publication rewrite. It should be an attestation-first
public cutover:

- make attestation the canonical trust surface in examples and docs
- make legacy trust explicit compatibility rather than the default mental model
- tighten operator-facing report wording around publication outcomes
- keep artifact semantics and request-gate behavior stable

## M2 Validation Verdict

What landed matches the M2 contract:

- `analysis_review_trust_v1` stayed public
- `trust_review.execution_mode` is a real parsed strategy input
- `attestation_over_bounded` runs bounded production first
- the bounded handoff is frozen as `bounded_attestation_input`
- trust attestation reuses bounded `final_analysis`
- no reporting or artifact-selection changes were required for M2

Observed branch extras that are not M3 by default:

- `scripts/run_m2_focus_gate_live_acceptance.py`
- `examples/harness/live_acceptance/m2_focus_gate_local.template.yaml`
- `tests/test_run_m2_focus_gate_live_acceptance.py`

Treat those as compatibility surfaces, not as drivers of M3 scope.

## Premise Challenge

1. **M3 is primarily a product-surface cutover, not a semantic publication rewrite.**
   Agree. The repo already centralized most publication truth in runner-owned
   status during M2.

2. **The current confusion is mostly at the repo surface.**
   Agree. Canonical trust examples still read as legacy trust, and the README still
   teaches trust as a mode swap rather than an attestation story.

3. **Silently changing trust defaults would be riskier than renaming the public surface.**
   Agree. Existing user configs may rely on omitted `trust_review` implying legacy.
   Do not break them silently just to make the code feel cleaner.

4. **Compatibility-shim cleanup is tempting but not core.**
   Agree. The M2 helper and template can stay explicit legacy compatibility until
   the attestation-first surface is stable.

5. **The right M3 shape is two sub-slices inside one milestone.**
   Agree.
   - `M3A`: public-surface cutover plus reporting wording cleanup
   - `M3B`: legacy retirement, only after post-cutover acceptance is green

## Approaches Considered

### Approach A: Minimal Docs-Only Promotion

Summary: update prose only, leave canonical trust example filenames and legacy
behavior untouched.

Effort: S
Risk: Low

Pros:
- smallest diff
- easy to land

Cons:
- repo surface stays contradictory
- old lane still looks canonical
- does not really close the milestone

### Approach B: Attestation-First Public Surface, Legacy As Explicit Compatibility

Summary: move the canonical trust examples, docs, and operator-facing wording onto
the attestation story while preserving explicit legacy-named surfaces.

Effort: M
Risk: Medium

Pros:
- matches the product story to the runtime shape
- avoids silent breaks
- isolates the milestone to the files users actually read

Cons:
- requires careful example migration
- leaves final legacy deletion for a follow-up slice

### Approach C: Immediate Default Flip And Legacy Deletion

Summary: change trust defaults to attestation and remove `legacy_full_review` in
the same branch.

Effort: M/L
Risk: High

Pros:
- cleanest end state

Cons:
- easy to surprise existing configs
- harder to diagnose regressions
- combines cutover and retirement in one blast radius

## Recommendation

Choose **Approach B**.

That gives the repo one honest public trust story now, while keeping a narrow and
explicit compatibility door open until the next acceptance pass says it can be
closed.

## Scope Challenge

### What already exists

| Sub-problem | Existing code | M3 decision |
|---|---|---|
| Final artifact selection | `apply_final_artifacts(...)` in `anvil/harness/reporting.py` | Keep semantic logic stable unless tests prove a real attestation gap. |
| Final-answer source payload | `_derive_final_answer_payload(...)` in `anvil/harness/runner.py` | Reuse bounded `final_analysis` path already proven by M2. |
| Runner-owned publication truth | `_build_analysis_review_status(...)` in `anvil/harness/runner.py` plus publishability helpers in `anvil/harness/reporting.py` | Keep runner ownership. Expose it more clearly in reports. |
| Operator report wording | `render_report(...)` in `anvil/harness/report.py` and reporting note helpers in `anvil/harness/reporting.py` | Tighten wording and surface execution mode explicitly. |
| Canonical trust examples | `examples/harness/strategies/analysis_review_trust_*.yaml` | Repoint canonical examples at attestation or create attestation-first canonical replacements. |
| Legacy examples | current additive `analysis_review_trust_attestation_*` examples and old trust examples | Invert the naming story: attestation becomes canonical, legacy becomes explicit. |
| Public docs | `README.md`, `docs/analysis_review_contract.md` | Rewrite the trust explanation around attestation-first behavior. |

### Complexity verdict

This is a medium slice, not a tiny one, because public surface changes cut across
examples, docs, reporting wording, and regression coverage.

It is still smaller than a true architecture milestone because it should avoid:

- new schema families
- new runner classes
- request-gate changes
- publication-logic reinvention

### Non-goals

- rewriting `anvil/harness/runner.py` orchestration again
- changing bounded semantics
- request-gate redesign
- compatibility-shim retirement unless it materially simplifies the canonical docs
- flipping omitted trust configs to attestation without an explicit decision

## Locked Decisions

| Decision | Locked choice | Why |
|---|---|---|
| Canonical trust story | trust = attestation over bounded output | This is what M2 now proves in code. |
| Legacy trust availability | keep it explicit and compatibility-only in M3A | Avoid silent breakage while demoting the old path. |
| Default parser behavior | leave unchanged unless a dedicated cutover step proves safe | Existing user configs may rely on omitted `trust_review`. |
| Publication semantics | preserve current runner-owned logic in `apply_final_artifacts(...)` | M2 already moved most of the hard logic into status assembly. |
| Reporting work | wording and visibility cleanup only | Do not smuggle in semantic rewrites. |
| Compatibility shim | not part of the critical path | Nice cleanup, wrong milestone center. |

## File-by-File Plan

### 1. Canonical trust example cutover

Expected files:

- `examples/harness/strategies/analysis_review_trust_codex_claude.yaml`
- `examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml`
- `examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml`
- additive legacy-named replacements if needed

Plan:

- make the canonical trust example filenames attestation-first
- move legacy semantics behind explicitly legacy-named example files if the repo
  still needs runnable coverage for them
- update any helper/template surfaces that are meant to teach the canonical trust
  path

Guardrails:

- do not delete legacy coverage before the acceptance matrix is green
- do not leave canonical filenames teaching legacy behavior

### 2. Public docs and README rewrite

Expected files:

- `README.md`
- `docs/analysis_review_contract.md`

Plan:

- describe bounded in one sentence: bounded produces the best draft
- describe trust in one sentence: trust attests bounded output and governs what is
  safe to publish
- update strategy examples so the attestation-first path is the main path users see
- make legacy trust read as compatibility, not as the default story

Guardrails:

- no new product claims that the code does not support
- no M4/request-gate rewrite while touching trust docs

### 3. Operator-facing report cleanup

Expected files:

- `anvil/harness/report.py`
- `anvil/harness/reporting.py`
- `tests/test_harness_reporting.py`

Plan:

- surface trust execution mode explicitly in `REPORT.md`
- make the publication explanation easier to scan:
  - what artifact was published
  - whether final publication was blocked
  - which recommendation indices were withheld and why
- keep the underlying admissibility and publishability rules unchanged unless a
  test proves a real mismatch with attestation mode

Guardrails:

- wording cleanup, not semantic reinvention
- preserve `FINAL_ANSWER.*`, `PARTIAL_ANSWER.*`, and `BEST_DRAFT.*` determinism

### 4. Compatibility boundary for legacy trust

Expected files:

- `anvil/harness/types.py` only if a warning/deprecation path is added
- tests covering legacy explicit use

Plan:

- keep `legacy_full_review` runnable
- decide whether M3A should emit a warning when legacy is explicitly selected
- do not flip omitted `trust_review` to attestation in the same slice unless the
  user explicitly wants the stronger cutover

Guardrails:

- avoid silent breaking changes
- keep one narrow compatibility proof path alive

## Architecture Review

### M2 runtime shape already achieved

```text
focus gate (optional)
  ->
bounded producer lane
  ->
frozen bounded_attestation_input
  ->
trust attestation review
  ->
runner-owned publication decision
```

### M3 target shape

```text
same runtime shape
  +
canonical example files, docs, and reports that describe it honestly
  +
legacy trust hidden behind explicit compatibility naming
```

### Important insight

The design doc's original M3 wording implied deeper publication rewiring than the
current repo now needs.

After reading `anvil/harness/runner.py`, `anvil/harness/reporting.py`, and the M2
tests, the better plan is:

- keep artifact-selection semantics stable
- make the public surface reflect the attestation reality
- reserve true legacy-lane deletion for the end of the milestone, not the start

That is the whole leverage point.

## Test Plan

Minimum required gates for `M3A`:

- `poetry run pytest -q tests/test_harness_reporting.py -k "apply_final_artifacts or final publication or withheld"`
- `poetry run pytest -q tests/test_harness_runner.py -k "attestation or legacy_full_review or focus_gate"`
- `poetry run pytest -q tests/test_harness_analysis_contract.py -k "execution_mode or trust_review"`

Additional checks:

- verify canonical trust example files serialize `trust_review.execution_mode: attestation_over_bounded`
- verify explicit legacy examples still serialize `legacy_full_review`
- verify `REPORT.md` exposes the active trust execution mode and unchanged artifact outcome

Optional post-cutover acceptance before `M3B`:

- rerun the focus-gate acceptance helper on canonical trust examples
- compare canonical attestation trust against explicit legacy trust on the same
  shard matrix

## Risks And Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Canonical-example rename breaks helper scripts or docs | users copy canonical filenames first | update helpers/templates in the same slice and keep legacy aliases explicit |
| Reporting cleanup accidentally changes artifact semantics | M3 would leak into a semantic rewrite | pin behavior with existing `apply_final_artifacts` regression tests |
| Leaving parser default unchanged feels half-done | old configs still silently mean legacy | compensate with canonical examples, docs, and optional deprecation warning |
| Legacy retirement creeps into M3A | blast radius grows for little user value | split retirement into `M3B` and gate it on acceptance |

## Completion Criteria

Do not call M3 done until all of these are true:

- the canonical trust examples are attestation-first
- legacy trust is explicit compatibility, not the main story
- README and contract docs describe trust as attestation over bounded output
- reports make publication outcome and execution mode easier to explain
- `apply_final_artifacts(...)` behavior is unchanged unless a real attestation bug
  forced a targeted fix
- legacy retirement is either completed under a separate acceptance gate or left as
  an explicit deferred follow-up

## Auto-Review Summary

### CEO review

The right problem is repo legibility, not more harness capability. M2 already did
the hard architecture move. Pretending M3 is a giant publication rewrite would be
fake work.

### Design review

Skipped. No user-facing UI surface is involved.

### Eng review

The clean cut is `M3A` plus optional `M3B`. Do not mix public-surface cutover with
irreversible legacy deletion. Keep the semantic center of gravity in existing
runner-owned status and regression coverage.

### DX review

This is where the user value is concentrated. The repo is a developer tool. The
first examples and README lines matter more than a clever internal cleanup nobody
sees. Make canonical trust usage guessable. Make legacy explicit.
