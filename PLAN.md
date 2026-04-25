# Next Iteration Plan: Shared Repo-Local Discovery Between Bounded and Trust

## Purpose

The current `PLAN.md` is for the previous trust mixed-grounding atomicity slice.

This plan replaces it with the next slice from the April 24 review feedback.

The next bug is not publication-state semantics and it is not another runner change.

It is a prompt-contract mismatch:

- `README.md:212-227` and `docs/analysis_review_contract.md:205-213` already say bounded and trust should differ in audit depth and publication rules, not in core repo understanding.
- `anvil/harness/prompts.py:394-465` still implements the repo-local corroboration rules as a bounded-only helper.
- `anvil/harness/prompts.py:276-358` already gives trust its downstream atomicity rules, but trust is not being told to start from the same governing seam first.

So the docs are already describing the right product distinction, but the prompt surface is still asymmetric.

This slice fixes that.

The target behavior is:

```text
bounded and trust start from the same repo-local discovery seam
→ both inspect the same governing doc / manifest / sibling workflow when needed
→ both ground the same core recommendation seam
→ bounded diverges only on caps and scope discipline
→ trust diverges only on provenance completeness, evidence completeness, atomicity, and publication
```

## Accepted Premises

These are locked for this slice:

1. No new strategy kind.
2. No runner-owned discovery engine.
3. No trust admissibility change.
4. No cap change.
5. `anvil/harness/prompts.py:394-465` already contains the right repo-local discovery rules. They are just gated to bounded mode today.
6. `anvil/harness/prompts.py:276-358` already contains the trust-only atomicity guidance and should remain downstream of shared discovery, not be folded into it.
7. The bounded four-recommendation seam in `tests/test_harness_runner.py:1858-1888` is the correct offline seam to reuse for trust.
8. This slice changes prompt composition, docs, and tests. It does not change runner logic or payload schema.

## The Exact Failure

The current repo surface says one thing and prompts another:

1. `README.md:212-227` says bounded and trust should not differ in core repo understanding.
2. `docs/analysis_review_contract.md:205-213` says bounded-mode discovery is repo-local and trust is stricter because of provenance and publication, not because bounded tolerates discovery blind spots.
3. `anvil/harness/prompts.py:394-465` puts those discovery rules behind `_bounded_corroboration_guidance_block()`, which returns `""` unless `contract.mode == "bounded"`.
4. `anvil/harness/prompts.py:775-966` wires both `_trust_recommendation_atomicity_block()` and `_bounded_corroboration_guidance_block()` into every prompt builder, but in practice trust only receives the atomicity block.
5. `tests/test_harness_prompt_consistency.py:252-340` freezes that asymmetry by asserting the discovery block only for bounded mode and not for trust.
6. `tests/test_harness_runner.py:1858-1888` proves bounded can keep the fuller four-recommendation seam, but the trust-side offline regressions around `tests/test_harness_runner.py:2841-2885` only prove partial-only admissibility on a smaller two-recommendation fixture.

That means the runner and docs already describe a downstream difference, but the prompt contract still teaches an upstream discovery difference.

That is the bug.

## Step 0: Scope Challenge

### Recommended review mode

Use **HOLD SCOPE**.

This is one seam:

- shared repo-local discovery guidance in prompts
- trust-specific downstream divergence after shared discovery
- prompt/docs/test alignment
- one trust offline regression on the same four-recommendation seam already used by bounded

Do not reopen:

- trust publication-state semantics
- trust recommendation admissibility semantics
- trust atomicity semantics themselves
- runner-owned discovery
- payload schema changes
- evidence-cap expansion
- new strategy kinds

### What already exists

| Sub-problem | Existing code | Why it is enough |
|---|---|---|
| shared discovery rules | `anvil/harness/prompts.py:394-465` | already states `files_hint` starting-slice, governing-doc, sibling-parity, and review-surface rules |
| trust-only downstream divergence | `anvil/harness/prompts.py:276-358` and `anvil/harness/prompts.py:247-273` | already covers trust atomicity and runner-owned final-artifact posture |
| bounded fuller recommendation seam | `_BoundedCorroborationHarnessAdapter` plus `tests/test_harness_runner.py:1858-1888` | already locks the spec-backed and sibling-parity four-recommendation surface |
| user-facing product wording | `README.md:212-227` | already states the intended shared-understanding / downstream-divergence split |
| contract wording | `docs/analysis_review_contract.md:205-213` | already says trust is stricter because of provenance and publication, not discovery blindness |
| phrase-freeze coverage | `tests/test_harness_analysis_contract.py:270-400` | already exercises README and contract-doc phrasing and can absorb the new shared-discovery wording |

### Minimum change that achieves the goal

Do not invent a new discovery subsystem.

Do not duplicate the bounded discovery paragraph into a second trust-only helper.

Do not move trust atomicity into runner logic.

The minimum complete fix is:

1. Replace `_bounded_corroboration_guidance_block()` with one shared cross-mode helper.
2. Move the common repo-local discovery rules into that shared helper for both bounded and trust.
3. Keep mode-specific tails in the same helper:
   - bounded: current `3 / 3 / 2` cap language, `must_check_files` vs `optional_check_files`, `scope_escapes`
   - trust: uncapped evidence/provenance completeness and an explicit "prefer nearer governing/spec/workflow evidence over farther plan/runbook prose" rule
4. Keep `_trust_recommendation_atomicity_block()` intact and clearly downstream of shared discovery.
5. Rewrite prompt consistency tests so shared discovery is asserted in both modes, with bounded-only and trust-only tails tested separately.
6. Add one trust offline regression using the same four-recommendation seam already used by bounded.
7. Update README, contract docs, and phrase-freeze tests so the written contract matches the prompt contract.

Anything bigger is overbuilt.

### Complexity check

Target touched files:

- `anvil/harness/prompts.py`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_runner.py`
- `README.md`
- `docs/analysis_review_contract.md`
- `tests/test_harness_analysis_contract.py`

This is below the 8-file smell threshold.

It adds no new runtime service, no new strategy, and no new schema family.

### Search check

- **[Layer 1]** reuse the existing bounded corroboration rules instead of re-describing them from scratch
- **[Layer 1]** reuse the existing trust atomicity block instead of fusing concerns into one helper
- **[Layer 1]** reuse the existing bounded four-recommendation harness seam instead of inventing a second synthetic workspace
- **[Layer 3]** fix the mismatch where it lives, in prompt composition and contract tests, not in new orchestration logic

No external web search is needed. This is repo-local contract work.

### TODOS cross-reference

`TODOS.md` already carries the broader product questions about bounded vs trust shape, attestation posture, and long-term runner structure.

No current TODO blocks this slice.

No new TODO should be created unless implementation uncovers a genuinely separate follow-up.

### Completeness check

Take the complete version.

Prompt refactor without runner regression is not enough.

Runner regression without doc and phrase-freeze alignment is not enough.

This is a boil-the-lake slice, not an ocean:

- same helper surface
- same docs seam
- same test suite family

### Distribution check

No new artifact type.

No CI/CD or packaging work is part of this slice.

## Architecture Review

### Current flow

```text
task.files_hint
    │
    ▼
prompt builders render common contract blocks
    │
    ├── bounded mode also gets `_bounded_corroboration_guidance_block()`
    │      ├── inspect nearest governing doc or manifest
    │      ├── inspect sibling workflow for parity claims
    │      └── record corroboration in files_reviewed/evidence/review_surface
    │
    └── trust mode skips that helper entirely
           ├── gets trust review policy
           └── gets trust atomicity rules
                    │
                    ▼
bounded and trust can diverge before they even inspect the governing seam
```

### Target flow

```text
task.files_hint
    │
    ▼
prompt builders render one shared repo-local discovery helper
    │
    ├── common rules in both modes
    │      ├── files_hint is a starting slice
    │      ├── spec/requirement claims inspect nearest governing repo-local doc or manifest
    │      ├── parity/symmetry claims inspect sibling implementation/workflow
    │      └── corroborating files land in files_reviewed/evidence/review_surface
    │
    ├── bounded tail
    │      ├── evidence <= 3
    │      ├── must_check_files <= 3
    │      ├── optional_check_files <= 2
    │      └── scope_escapes discipline
    │
    └── trust tail
           ├── keep evidence/provenance complete
           ├── prefer nearer governing/spec/workflow evidence over farther prose
           └── then apply trust atomicity rules downstream
                    │
                    ▼
both modes start from the same core recommendation seam
```

### Canonical rules

Freeze these rules for this slice:

1. `files_hint` is a starting slice, not a hard boundary, in both bounded and trust.
2. Requirement, policy, and spec claims must inspect the nearest governing repo-local doc or manifest in both modes.
3. Parity, symmetry, and sibling-workflow claims must inspect the sibling implementation or workflow and compare the full like-for-like seam in both modes.
4. Corroborating files must appear in `files_reviewed`, `evidence`, and `review_surface` in both modes.
5. Bounded still owns the current `3 / 3 / 2` caps, `must_check_files` vs `optional_check_files`, and `scope_escapes` discipline.
6. Trust still owns uncapped evidence completeness, provenance completeness, atomicity, and publication semantics.
7. Trust must explicitly prefer nearer governing/spec/workflow evidence over farther plan/runbook prose when both exist.
8. Trust atomicity remains downstream of shared discovery. The order is:
   - discover the same governing seam first
   - then split direct/spec-backed guidance from weaker hardening if needed
9. This slice does not change runner-owned admissibility, final publication rules, or canonical reason codes.

### File-by-file implementation plan

#### 1. `anvil/harness/prompts.py`

This is the core implementation file.

Replace `_bounded_corroboration_guidance_block()` with one shared helper, for example `_repo_local_discovery_guidance_block(contract, role)`.

Required common rules in that helper for both modes:

1. `files_hint` is a starting slice, not the total review universe.
2. Requirement, policy, or spec claims inspect and cite the nearest governing repo-local doc or manifest.
3. Parity, symmetry, or sibling-workflow claims inspect and cite the sibling implementation or workflow that establishes the baseline, then compare the full like-for-like seam.
4. Corroborating files must be present in `files_reviewed`, `evidence`, and `review_surface`.

Required bounded tail in that same helper:

- keep the existing `Bounded corroboration guidance` cap language
- keep `review_surface.must_check_files` for directly governing corroboration
- keep `review_surface.optional_check_files` for supporting corroboration
- keep the current `scope_escapes` discipline
- keep the role-specific bounded enforcement lines

Required trust tail in that same helper:

- trust evidence stays uncapped and complete
- trust still records the corroborating files in `files_reviewed`, `evidence`, and `review_surface`
- add one explicit rule that nearer governing/spec/workflow evidence beats farther plan/runbook prose when both exist
- add role-specific trust lines that enforce discovery quality, not publication behavior

Keep `_trust_recommendation_atomicity_block()` separate.

Keep it downstream of the shared helper in every prompt builder so the intended trust flow becomes:

```text
shared discovery first
→ trust-only atomicity second
→ runner-owned admissibility/publication last
```

Do not duplicate the common discovery paragraph in multiple helpers.

#### 2. `tests/test_harness_prompt_consistency.py`

Refactor the assertions so the contract structure matches the new helper shape.

Required changes:

1. Move the current `bounded_corroboration_lines` into shared assertions that run for both `mode == "bounded"` and `mode == "trust"`.
2. Rename the test-local assertion groups so they distinguish:
   - shared discovery lines
   - bounded-only tail lines
   - trust-only discovery tail lines
   - trust-only atomicity lines
3. Keep the existing trust final-artifact and atomicity assertions.
4. Keep the bounded-only cap, `must_check_files` / `optional_check_files`, and `scope_escapes` assertions bounded-only.
5. Add trust assertions for the "prefer nearer governing/spec/workflow evidence over farther plan/runbook prose" rule.

This test should prove shared discovery is now symmetric while downstream trust strictness remains asymmetric.

#### 3. `tests/test_harness_runner.py`

Add one trust offline regression on the same four-recommendation seam already used by bounded.

Implementation shape:

1. Reuse `_BoundedCorroborationHarnessAdapter` as the content seam for trust instead of inventing a different recommendation family.
2. Add a trust-oriented adapter that keeps the same four recommendation titles and core evidence anchors, but adds trust metadata such as:
   - `verified_evidence_refs`
   - `checked_files`
   - `affected_files`
   - `grounding_mode`
3. Make the trust-only downgrade come from trust semantics, not from changing the discovered seam.
4. Freeze one exact fixture shape so implementation does not have to guess:
   - recommendation 1, `Track release-watch issues against the parity spec`, is direct and accepted
   - recommendation 2, `Add concurrency controls`, is direct and accepted
   - recommendation 3, `Align timeout handling across the full snapshot parity seam`, is the trust-only downgraded item and should be marked `grounding_mode = inferred`
   - recommendation 4, `Document alert routing ownership`, is direct and accepted

Required assertions:

- `summary["verdict"] == "accepted_with_warnings"`
- `summary["analysis_review_contract"]["mode"] == "trust"`
- trust mode starts from this exact four-title seam, in this exact order:
  - `Track release-watch issues against the parity spec`
  - `Add concurrency controls`
  - `Align timeout handling across the full snapshot parity seam`
  - `Document alert routing ownership`
- `summary["analysis_review_status"]["recommendation_admissibility"]["final_answer_recommendation_indices"] == [1, 2, 4]`
- `summary["analysis_review_status"]["recommendation_admissibility"]["partial_only_recommendation_indices"] == [3]`
- `summary["analysis_review_status"]["recommendation_admissibility"]["excluded_recommendation_indices"] == []`
- `summary["analysis_review_status"]["recommendation_admissibility"]["reasons_by_recommendation_index"] == {"3": ["inferred_grounding"]}`
- `summary["artifacts"]["final_artifact_kind"] == "partial_answer"`
- `summary["partial_answer"]["included_recommendation_indices"] == [1, 2, 3, 4]`
- the `partial_answer` recommendation titles still match the same bounded four-title seam in the same order
- `REPORT.md` freezes `Recommendation indices withheld from FINAL_ANSWER.*: 3`
- the downgraded recommendation is withheld because of the existing trust admissibility reason code, not because trust switched to a different governing seam
- no new canonical reason codes are introduced

This test is the real product regression:

```text
bounded and trust may still publish different artifacts
but they should not discover different core seams for the same repo-local task
```

#### 4. `README.md`

Update the harness section around `README.md:212-227`.

Required doc shape:

1. State shared repo-local discovery across bounded and trust, not bounded-only discovery.
2. State that both modes should inspect the same governing doc / manifest / sibling workflow when those are needed to support a recommendation.
3. Restate that bounded differs by caps and scope discipline.
4. Restate that trust differs by provenance completeness, evidence completeness, atomicity, and publication.
5. Keep the trust atomicity paragraph, but position it clearly as downstream of shared discovery.

Keep it concise.

#### 5. `docs/analysis_review_contract.md`

Update the discovery policy section around `docs/analysis_review_contract.md:205-213`.

Required doc shape:

1. Rewrite the section so shared repo-local discovery is the cross-mode rule.
2. Preserve the bounded cap details explicitly.
3. Add the trust-only "prefer nearer governing/spec/workflow evidence over farther plan/runbook prose" rule.
4. State plainly that trust is stricter because of provenance, evidence completeness, atomicity, and publication, not because it gets a different discovery universe.
5. Keep the later admissibility and atomicity sections intact.

#### 6. `tests/test_harness_analysis_contract.py`

Add short stable phrase checks for the new shared-discovery wording.

Required assertions:

- README documents shared repo-local discovery across both modes
- README documents bounded-only cap differences
- README documents trust-only provenance/evidence/atomicity/publication differences
- contract doc documents the same shared-discovery principle
- contract doc documents the nearer-governing-evidence-over-farther-prose rule in trust mode

Use phrase-level checks, not brittle paragraph matches.

## Code Quality Review

### Engineering constraints

1. Use one shared discovery helper, not copy-pasted bounded and trust paragraphs.
2. Keep trust atomicity separate from discovery so the two concepts do not get entangled.
3. Do not add runner logic for something the prompt contract can already express.
4. Do not let docs get ahead of prompts again. The prompt helper, docs, and phrase-freeze tests need to land together.
5. Reuse the existing bounded four-recommendation seam for trust regression to stay DRY.
6. Prefer the smallest naming diff that makes the cross-mode behavior obvious.

### Minimal-diff recommendation

Implement this as prompt-helper refactoring plus test/doc realignment.

The runner is not the bottleneck.

The prompt composition is.

## Test Review

### Test framework

This repo uses `pytest`.

### Code path coverage

```text
PLAN CHANGE COVERAGE
===========================
[+] anvil/harness/prompts.py
    │
    ├── [GAP] shared discovery helper renders common repo-local rules in bounded mode
    ├── [GAP] shared discovery helper renders common repo-local rules in trust mode
    ├── [GAP] bounded tail keeps 3 / 3 / 2 caps and scope_escapes discipline
    ├── [GAP] trust tail adds nearer-governing-evidence preference
    └── [★★★ EXISTING] trust atomicity remains a separate downstream block

[+] tests/test_harness_prompt_consistency.py
    │
    ├── [GAP] shared discovery wording locked for both modes
    ├── [GAP] bounded-only tail locked separately
    ├── [GAP] trust-only discovery tail locked separately
    └── [★★★ EXISTING] trust atomicity assertions remain in place

[+] tests/test_harness_runner.py
    │
    ├── [★★★ EXISTING] bounded mode ships the four-recommendation seam
    ├── [GAP] trust mode starts from that same four-recommendation seam
    ├── [GAP] trust partial artifact remains a subset of that seam, not a different seam
    └── [GAP] withholding reasons stay canonical and runner-owned

[+] README.md + docs/analysis_review_contract.md + tests/test_harness_analysis_contract.py
    │
    ├── [GAP] shared-discovery wording frozen in README
    ├── [GAP] shared-discovery wording frozen in contract docs
    └── [★★★ EXISTING] trust admissibility / atomicity wording remains covered

─────────────────────────────────
COVERAGE TARGET: 12/12 paths locked
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

### Manual acceptance

After the patch, rerun bounded and trust on the same task and the same workspace.

Use the same task file and only swap the strategy:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_bounded_codex_claude.yaml \
  --workspace /path/to/workspace \
  --out-root .forge-harness-runs

poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_trust_codex_claude.yaml \
  --workspace /path/to/workspace \
  --out-root .forge-harness-runs
```

Manual acceptance criteria:

1. bounded and trust start from the same core recommendation seam
2. the trust run may still publish `PARTIAL_ANSWER.*`
3. if trust publishes `PARTIAL_ANSWER.*`, it does so because of trust-only admissibility or publication posture
4. trust does not replace the bounded four-recommendation seam with a different discovery seam

## Performance Review

No meaningful runtime risk is expected.

This is prompt text, docs, and offline regression work.

Prompt size grows slightly, but not in a way that should matter relative to the existing harness prompt size.

## Failure Modes Registry

| Failure mode | Test covers it | Error handling exists | User-visible impact | Required mitigation |
|---|---|---|---|---|
| shared discovery helper still returns empty in trust mode | yes | no | trust keeps acting like it has a different discovery universe | prompt consistency assertions for shared lines in both modes |
| trust cites farther plan/runbook prose while a nearer governing spec or sibling workflow exists | yes | no | trust drifts off the real governing seam and recommendations stop matching bounded | trust discovery-tail assertions plus trust four-seam regression |
| trust atomicity gets accidentally fused into discovery helper | yes | no | future prompt edits blur discovery vs publication semantics | preserve separate atomicity helper and assert it separately |
| docs say discovery is shared but prompt builders still wire it asymmetrically | yes | no | user-facing contract stays misleading | README / contract phrase checks plus prompt consistency test |
| trust regression still uses a smaller two-recommendation seam | yes | no | bounded/trust comparison remains unproven on the real workflow seam | new trust regression reusing the bounded four-recommendation adapter |

Critical gap to avoid: any implementation that makes trust and bounded compare different recommendation families and then calls the remaining delta "publication behavior."

## What Already Exists

Use these instead of rebuilding anything:

- the current bounded discovery helper already contains the right common repo-local discovery rules
- the current trust atomicity helper already contains the trust-only downstream rule set
- the bounded four-recommendation harness fixture already expresses the exact offline seam we want
- README and contract docs already contain the product principle, they just need prompt-level alignment
- the existing phrase-freeze and prompt-consistency tests already cover the right surfaces

## NOT in Scope

- new strategy kinds
- runner-owned discovery logic
- trust admissibility changes
- trust publication changes
- evidence-cap changes
- payload schema changes
- new reason codes
- new artifact types

## TODOS.md

No new TODO should be added from this slice.

The broader product questions about bounded vs trust remain in `TODOS.md` already.

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|------|-----------------|------------|
| Shared discovery helper refactor | `anvil/harness/` | — |
| Doc contract realignment | repo root docs (`README.md`, `docs/`) | — |
| Test realignment and trust seam regression | `tests/` | shared discovery helper refactor, doc contract realignment |

### Parallel lanes

- Lane A: shared discovery helper refactor in `anvil/harness/`
- Lane B: doc contract realignment in `README.md` and `docs/`
- Lane C: test realignment and trust seam regression in `tests/` after A and B merge

### Execution order

Launch Lane A and Lane B in parallel worktrees.

Merge both.

Then run Lane C once the final helper and wording are settled.

### Conflict flags

- Lane A and Lane B are safe to parallelize. They touch different primary modules.
- Lane C should stay sequential after both land because the test files are the convergence layer for final helper structure and final wording.

## Completion Summary

- Step 0: Scope Challenge, hold scope accepted
- Design Review: skipped, no UI scope
- Architecture Review: complete
- Code Quality Review: complete
- Test Review: diagram produced, 12 coverage targets identified
- Performance Review: 0 issues
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none
- Failure modes: 0 unresolved critical gaps if shared helper, docs, and regressions all land
- Outside voice: skipped for this narrow repo-local slice
- Parallelization: 3 lanes, 2 launch in parallel, 1 convergence lane stays sequential
- Lake Score: 5/5 key decisions chose the complete option

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Replace the current trust-atomicity plan with a shared-discovery plan | mechanical | pragmatic | user explicitly asked for the next slice, not the previous one | keeping the stale atomicity-only plan |
| 2 | CEO | Keep bounded and trust aligned on discovery and divergent only downstream | mechanical | explicit over clever | the docs already describe that product distinction and the prompt contract should match it | treating discovery asymmetry as a product feature |
| 3 | Eng | Implement shared discovery as one helper and keep trust atomicity downstream | mechanical | minimal diff | it fixes the mismatch without new orchestration or runner logic | new discovery engine or helper duplication |
| 4 | Eng | Reuse the bounded four-recommendation seam for trust regression | mechanical | DRY | it is the real seam already under test and avoids synthetic drift | inventing a second trust-only seam |
| 5 | Eng | Parallelize prompt refactor and doc edits, then converge in tests | taste | pragmatic | it saves time without causing wording drift in the test layer | trying to parallelize all test edits before the helper and docs settle |
