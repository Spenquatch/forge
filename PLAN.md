# Next Iteration Plan: Bounded Discovery Completeness Backfill

## Purpose

The current `PLAN.md` targets the publication-state contradiction from the April 24 trust replay. That was previous item 1.

This plan replaces it with previous item 2.

The bug now is narrower and more important to day-to-day usage: bounded mode is producing a cleaner artifact, but it is also missing directly grounded recommendations that trust mode is finding from the same repo-local evidence.

That is not a good product distinction.

Bounded should stay simpler than trust. It should not stay blinder than trust.

## Accepted Premises

These are locked for this slice:

1. `analysis_review_bounded_v1` and `analysis_review_trust_v1` remain separate strategy kinds.
2. Trust keeps its stronger provenance and publication gates.
3. Bounded keeps its cleaner final-answer semantics and evidence caps.
4. Missing a nearby, repo-local, spec-backed recommendation is a bounded-mode bug, not an acceptable tradeoff.
5. This slice fixes recommendation discovery completeness, not artifact publication state.

## The Exact Failure

The April 24 pair makes the gap concrete:

- bounded run: `.forge-harness-runs/20260424T191006Z-recommend_automation_improvements-6a97899b`
- trust run: `.forge-harness-runs/20260424T191008Z-recommend_automation_improvements-838bd449`

Observed difference:

1. bounded ships a `FINAL_ANSWER.md` with 3 recommendations
2. trust produces a `PARTIAL_ANSWER.md` with 4 recommendations
3. the extra trust recommendation is not a weird provenance-only artifact, it is a repo-local, spec-backed release-watch issue-tracking recommendation grounded in `docs/project_management/next/codex-cli-parity/C1-spec.md`
4. trust also frames timeout and parity issues across the full sibling workflow seam more completely than bounded

So the harness is currently teaching users the wrong lesson:

```text
bounded = cleaner artifact, but maybe incomplete repo understanding
trust   = fuller repo understanding, but stricter publication semantics
```

That is the whole problem.

The product distinction should be:

```text
bounded = same core repo understanding, lighter-weight audit contract
trust   = same or deeper understanding, stronger provenance and final-publication rules
```

## Step 0: Scope Challenge

### Recommended review mode

Use **HOLD SCOPE**.

This slice is one seam:

- bounded-mode recommendation discovery around prioritized files
- bounded prompt guidance for repo-local corroboration
- regression coverage that proves bounded may carry the fuller recommendation set

Do not reopen:

- trust publication semantics
- recommendation admissibility semantics
- payload provenance
- new strategy kinds
- a new rule engine that auto-discovers recommendations without model work

### What already exists

| Sub-problem | Existing code | Why it is enough |
|---|---|---|
| task starting slice | `anvil/harness/prompts.py:_task_block()` | already injects `files_hint` into every analysis prompt |
| bounded review discipline | `anvil/harness/prompts.py` critic/auditor/reviser guidance | already tells bounded reviewers to stay inside `review_surface` and record `scope_escapes` |
| bounded caps | `anvil/harness/contracts.py:BoundedReviewPolicy` and `anvil/harness/semantic_validation.py` | already cap evidence and review-surface size |
| evidence trimming | `anvil/harness/runner.py:3316-3327` | already trims bounded evidence to cap, so this slice must stay within cap instead of removing it |
| scope-escape reporting | `anvil/harness/runner.py:1307-1414` | already records and renders bounded scope escapes |
| prompt regression coverage | `tests/test_harness_prompt_consistency.py` | already locks bounded vs trust prompt differences |
| bounded harness acceptance coverage | `tests/test_harness_runner.py` | already has offline adapters and bounded-summary assertions |
| contract docs | `README.md`, `docs/analysis_review_contract.md`, `tests/test_harness_analysis_contract.py` | already freeze user-facing semantics and are the right place to document bounded corroboration expectations |

### Minimum change that achieves the goal

Do not add a new model stage.

Do not add a new strategy kind.

Do not add a repo-wide heuristic file discovery engine.

The minimum complete fix is:

1. teach bounded prompts that `files_hint` is the starting slice, not the total truth
2. require one-hop, repo-local corroboration when a recommendation depends on:
   - a normative requirement claim
   - a sibling-workflow parity claim
3. keep that corroboration inside the existing bounded caps by using `must_check_files` and `optional_check_files` correctly
4. add regression tests that prove bounded mode can emit the fuller recommendation set without changing bounded publication semantics

Anything bigger is overbuilt.

### Complexity check

Target touched files:

- `anvil/harness/prompts.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_runner.py`
- `README.md`
- `docs/analysis_review_contract.md`
- `tests/test_harness_analysis_contract.py`

This is under the 8-file smell threshold and does not add a new class or service.

### Search check

- **[Layer 1]** reuse `files_hint`
- **[Layer 1]** reuse `review_surface.must_check_files` / `optional_check_files`
- **[Layer 1]** reuse `scope_escapes`
- **[Layer 1]** reuse existing bounded evidence caps
- **[Layer 3]** fix bounded-mode blindness with prompt and regression work, not with a new orchestration stage

No external web search is needed. This is entirely repo-local.

### Completeness check

Take the complete version.

Prompt-only without regression tests is not enough.

Regression tests without contract docs is not enough.

The extra work to update docs and contract assertions is minutes, not a real tradeoff.

### Distribution check

No new artifact type. No CI/release pipeline work. No distribution change.

## Architecture Review

### Current flow

```text
task.files_hint
    │
    ▼
bounded proposer starts from prioritized files
    │
    ├── recommendation must stay inside bounded evidence caps
    ├── recommendation review_surface is usually authored from the same starting slice
    └── no prompt rule forces repo-local corroboration for spec or parity claims
            │
            ▼
bounded critic/auditor mostly validate the authored slice
    │
    └── result can be locally grounded but still incomplete
```

### Target flow

```text
task.files_hint
    │
    ▼
bounded proposer starts from prioritized files
    │
    ├── if claim is requirement/spec-backed:
    │      inspect one governing repo-local doc or manifest
    │
    ├── if claim is sibling-parity-backed:
    │      inspect the sibling workflow and compare the full like-for-like pipeline seam
    │
    ├── include corroborating files in evidence + review_surface within existing caps
    └── reserve scope_escapes for later-stage review that must leave the declared surface
            │
            ▼
bounded critic/auditor verify the fuller surface
    │
    └── bounded can discover the same core recommendation set as trust,
        while trust still owns the stricter provenance/publication layer
```

### Canonical rules

Freeze these rules for this slice:

1. `files_hint` remains a prioritization input, not a hard boundary.
2. Bounded mode may inspect repo-local corroborating files outside `files_hint`.
3. Corroboration is limited to one hop:
   - governing spec/manifest/doc for requirement claims
   - sibling workflow or sibling implementation for parity claims
4. Bounded mode must keep corroboration inside the current caps:
   - evidence cap stays 3
   - `must_check_files` cap stays 3
   - `optional_check_files` cap stays 2
5. This slice does not change:
   - trust provenance rules
   - trust partial-only semantics
   - bounded final-answer admissibility semantics
   - runner-owned recommendation admissibility

### File-by-file implementation plan

#### 1. `anvil/harness/prompts.py`

This is the primary implementation file.

Add one shared bounded-corroboration guidance block and use it in proposer, critic, reviser, and auditor prompts.

Required prompt behavior:

1. `files_hint` is the starting slice.
2. When a recommendation depends on repo-local requirements, the model must inspect and cite the nearest governing doc or manifest.
3. When a recommendation depends on parity or symmetry, the model must inspect and cite the sibling implementation that establishes the baseline.
4. For parity claims, the model must compare the full like-for-like pipeline seam, not just one convenient step.
5. The corroborating files must be included in `files_reviewed`, `evidence`, and `review_surface` within existing caps.
6. `scope_escapes` stay for later review stages that leave the authored review surface, not for proposer laziness.

Concrete prompt updates:

- proposer:
  - add a bounded-mode instruction that requirement claims must pull in one governing repo-local doc or manifest
  - add a bounded-mode instruction that parity claims must pull in the sibling workflow or sibling implementation
  - add a bounded-mode instruction to use `must_check_files` for directly governing corroboration and `optional_check_files` for supporting corroboration
- critic:
  - add a bounded-mode instruction to flag missing repo-local corroboration when a recommendation makes a requirement or parity claim without the governing file in evidence/review surface
- reviser:
  - add a bounded-mode instruction to repair missing corroboration by widening `review_surface` within cap before inventing new recommendations
- auditor:
  - add a bounded-mode instruction to reject clean closure when spec/parity-backed claims still lack the needed corroborating file

Do not add repo-specific hardcoded filenames to prompt code.

Keep the rule generic.

#### 2. `tests/test_harness_prompt_consistency.py`

Lock the new behavior explicitly.

Required assertions:

- bounded prompts say `files_hint` is a starting slice, not the total review universe
- bounded prompts require one-hop repo-local corroboration for requirement/spec claims
- bounded prompts require sibling corroboration for parity claims
- bounded prompts tell the model to keep corroboration inside current caps
- trust prompt expectations remain unchanged for provenance and uncapped evidence

Do not loosen existing trust assertions to make this test pass.

#### 3. `tests/test_harness_runner.py`

Add one new bounded offline regression using a fake adapter.

Scenario to encode:

- same automation-review task shape
- bounded proposer returns 4 recommendations
- recommendation 1 includes a workflow plus a governing spec doc in evidence/review surface
- recommendation 3 includes both sibling snapshot workflows so the timeout recommendation covers `prepare` and the broader parity seam
- bounded run still publishes `FINAL_ANSWER.*`

Required assertions:

- `summary["analysis_review_contract"]["mode"] == "bounded"`
- `summary["artifacts"]["final_artifact_kind"] == "final_answer"`
- bounded final answer contains 4 recommendations
- the spec-backed release-watch recommendation is preserved in bounded mode
- the fuller timeout/parity recommendation is preserved in bounded mode
- every recommendation still respects the bounded evidence/review-surface caps
- bounded summary still renders valid review-surface coverage

This test is not trying to prove live-model determinism.

It is proving the bounded contract allows the fuller shape we want.

#### 4. `docs/analysis_review_contract.md`

Add one explicit bounded-corroboration section.

Must document:

- bounded mode is discovery-bounded, not workflow-file-only
- bounded may use repo-local corroboration outside `files_hint`
- requirement claims need a governing repo-local doc/manifest when one exists
- parity claims need a sibling implementation when one exists
- bounded still stays inside current evidence and review-surface caps
- trust remains stricter on provenance and publication, not just broader on discovery

#### 5. `README.md`

Add one concise paragraph in the harness surface section:

- bounded and trust should differ in audit depth and publication rules
- bounded is still expected to make repo-local, spec-backed recommendations when the corroboration is one hop away

Keep it short.

#### 6. `tests/test_harness_analysis_contract.py`

Update contract-doc assertions for the new bounded-corroboration wording in `README.md` and `docs/analysis_review_contract.md`.

Do not add brittle full-paragraph string asserts if a shorter stable phrase will do.

## Code Quality Review

### Engineering constraints

1. Do not add a new `analysis_review_*_v2` strategy kind.
2. Do not add runner-owned recommendation-discovery state.
3. Keep the change DRY by using one prompt helper block, not four copy-pasted paragraphs.
4. Do not push repo-specific filenames into prompt code.
5. Do not change semantic validation caps in this slice.

### Minimal-diff recommendation

Use prompt guidance plus regression coverage.

Do not touch `anvil/harness/runner.py` or `anvil/harness/semantic_validation.py` unless the new bounded runner regression exposes a real contract hole.

## Test Review

### Test framework

This repo uses `pytest`.

### Code path coverage

```text
PLAN CHANGE COVERAGE
===========================
[+] anvil/harness/prompts.py
    │
    ├── bounded proposer guidance
    │   ├── [GAP] starting-slice wording
    │   ├── [GAP] requirement/spec corroboration rule
    │   └── [GAP] parity corroboration rule
    │
    ├── bounded critic guidance
    │   └── [GAP] missing-corroboration rejection rule
    │
    ├── bounded reviser guidance
    │   └── [GAP] widen review_surface-within-cap repair rule
    │
    └── bounded auditor guidance
        └── [GAP] no clean closure without corroboration rule

[+] tests/test_harness_prompt_consistency.py
    │
    ├── [GAP] bounded corroboration text locked
    └── [★★★ TESTED after change] trust text unchanged

[+] tests/test_harness_runner.py
    │
    ├── [GAP] bounded can emit 4-rec fuller recommendation set
    ├── [GAP] bounded final answer still publishes
    └── [GAP] bounded caps still enforced with corroborating files present

─────────────────────────────────
COVERAGE TARGET: 8/8 paths tested
QUALITY TARGET: all new assertions ★★★
─────────────────────────────────
```

### Required test commands

Run exactly these:

```bash
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_analysis_contract.py
```

### Manual dogfood acceptance

After tests pass, rerun the automation task in both modes against the same target repo:

```bash
poetry run python -m anvil.harness.cli run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_bounded_codex_claude.yaml \
  --workspace /Users/spensermcconnell/__Active_Code/atomize-hq/unified-agent-api \
  --out-root .forge-harness-runs

poetry run python -m anvil.harness.cli run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_trust_codex_claude.yaml \
  --workspace /Users/spensermcconnell/__Active_Code/atomize-hq/unified-agent-api \
  --out-root .forge-harness-runs
```

Manual acceptance criteria:

1. bounded discovers the release-watch issue-tracking recommendation
2. bounded discovers the fuller timeout/parity recommendation
3. bounded still ships `FINAL_ANSWER.*`
4. trust may still differ on caveat language and final publication, but not by omitting those core recommendations from bounded

Live-model wording does not need to match byte-for-byte.

The recommendation set does.

## Performance Review

No meaningful runtime risk is expected.

This slice adds prompt text and tests. The only operational cost is slightly longer prompt bodies, which is negligible relative to current harness round-trip time.

## Failure Modes Registry

| Failure mode | Test covers it | Error handling exists | User-visible impact | Required mitigation |
|---|---|---|---|---|
| bounded prompt still treats `files_hint` as a hard boundary | yes | no | bounded keeps missing spec-backed recommendations | prompt consistency assertions |
| bounded models wander too far outside prioritized files | partial | yes, via `scope_escapes` visibility | noisier bounded recommendations | one-hop corroboration wording and existing caps |
| bounded parity claims stay shallow and miss adjacent jobs like `prepare` | yes | no | incomplete recommendation set | runner regression with fuller parity-backed recommendation |
| docs drift and future contributors reintroduce bounded-blindness as “expected” | yes | no | contract confusion | README + contract doc + contract tests |

Critical gap to avoid: shipping prompt changes without the bounded runner regression.

## What Already Exists

Use these instead of rebuilding anything:

- `files_hint` already tells models where to start
- `review_surface` already constrains bounded verification
- `scope_escapes` already make bounded expansion observable
- evidence/review-surface caps already bound the slice size
- offline fake adapters already make this behavior testable without live providers

## NOT in Scope

- publication-state parity, that is previous item 1 and already has its own plan
- trust-mode provenance or withholding semantics
- changing bounded evidence caps from 3 / 3 / 2
- automatic repo crawling to discover governing docs heuristically
- adding a new analysis stage or strategy kind
- external-search-backed recommendation discovery

## TODOS.md

No new TODOs should be added from this slice.

The existing backlog already captures the larger “bounded vs trust product distinction” questions. This slice is the tactical fix.

## Worktree Parallelization Strategy

Sequential implementation, no useful parallelization opportunity.

Everything touches the same harness planning surface:

- prompt guidance
- prompt tests
- bounded regression test
- contract docs

Splitting this across worktrees buys little and increases wording drift risk.

## Completion Summary

- Step 0: Scope Challenge, hold scope accepted
- Design Review: skipped, no UI scope
- Architecture Review: complete
- Code Quality Review: complete
- Test Review: diagram produced, 8 coverage targets identified
- Performance Review: 0 issues
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none
- Failure modes: 0 unresolved critical gaps if regression coverage lands
- Outside voice: skipped for this narrow repo-local slice
- Parallelization: sequential
- Lake Score: 4/4 key decisions chose the complete option

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Replace the current publication-state slice with a new bounded-completeness slice | mechanical | pragmatic | user explicitly asked to fix previous item 2, not item 1 | keeping the old `PLAN.md` focus |
| 2 | CEO | Keep bounded and trust as separate strategy kinds | mechanical | explicit over clever | the problem is discovery completeness, not missing strategy proliferation | `analysis_review_bounded_v2` |
| 3 | Eng | Implement via prompt guidance plus regression coverage | taste | minimal diff | runner-side recommendation discovery would be overbuilt for this seam | new analysis stage or discovery engine |
| 4 | Eng | Require one-hop repo-local corroboration for requirement and parity claims | mechanical | completeness | this is the smallest rule that closes the observed gap | workflow-file-only bounded review |
| 5 | Eng | Keep current bounded caps unchanged | mechanical | boring by default | the bug is blindness, not cap size | cap expansion as the primary fix |
