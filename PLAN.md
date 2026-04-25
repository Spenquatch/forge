<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260425-110806.md -->
# Next Iteration Plan: Deterministic Seam Selection for Analysis Review

## Purpose

The shared repo-local discovery slice is already landed.

That work shipped in commit `050ec28` and now exists in:

- [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:395)
- [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md:205)
- [tests/test_harness_prompt_consistency.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py:252)
- [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:1997)

So the next bug is not "trust lacks bounded discovery guidance" anymore.

The remaining failure is a seam-selection and prioritization bug:

- multiple repo-local seams can all look valid
- bounded and trust can still choose different primary seams while both appearing compliant
- the contract does not record which seam won
- the critic and auditor do not have an explicit seam choice to challenge
- semantic validation cannot reject seam drift because the payload does not declare seam state

This slice fixes that.

The target behavior is:

```text
task.files_hint
→ build candidate seams from the hinted files plus nearest governing/sibling evidence
→ rank seams deterministically
→ pick one primary seam
→ exhaust that primary seam before expanding
→ bind every recommendation to a seam
→ critic/auditor challenge seam correctness first
→ bounded and trust share the same primary seam on the same task/workspace
→ bounded still diverges only by caps
→ trust still diverges only by admissibility, provenance, atomicity, and publication
```

## Accepted Premises

These are locked for this slice:

1. Shared repo-local discovery is already fixed. Do not reopen the old prompt-symmetry slice.
2. The remaining bug is seam prioritization and seam enforcement, not publication semantics.
3. No new strategy kind.
4. No runner-owned discovery engine.
5. The right implementation surface is explicit contract + payload + semantic validation, not more generic prompt prose.
6. The current semantic validation layer is strong enough to enforce seam structure once the payload exposes it.
7. Trust atomicity remains downstream behavior and must not be folded into seam selection.
8. The current trust seam regression is too synthetic because [_TrustCorroborationHarnessAdapter](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:365) inherits the bounded seam directly.
9. The next slice changes contract, prompt composition, schemas, semantic validation, docs, and regressions. It does not add a new orchestration subsystem.

## The Exact Failure

The current repo now says the right high-level thing but still cannot force the right seam:

1. Shared repo-local discovery is present in [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:395).
2. The contract still has no explicit seam-priority policy in [anvil/harness/contracts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/contracts.py:96).
3. The analysis payload schema still has no `primary_seam`, `secondary_seams_considered`, or recommendation seam binding in [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:120).
4. Semantic validation can enforce evidence caps and review-surface structure, but it cannot reject seam drift because no seam metadata exists in [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:104).
5. The trust regression currently preserves the bounded seam by inheritance in [_TrustCorroborationHarnessAdapter](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:365), so it proves artifact behavior more than real seam choice.
6. Live runs can still diverge when there are several plausible nearby seams, because the model is being guided to inspect good evidence but not forced to commit to one ranked seam first.

That is the bug.

## Step 0: Scope Challenge

### Recommended review mode

Use **HOLD SCOPE**.

This is one seam:

- deterministic seam ranking
- explicit seam declaration in the payload
- semantic validation for seam binding
- review-stage enforcement of wrong-seam detection
- harder regressions that tempt the model toward the wrong seam

Do not reopen:

- trust publication semantics
- recommendation admissibility rules
- topic-ledger behavior
- new strategy kinds
- runner-owned discovery engines
- artifact format redesign

### What already exists

| Sub-problem | Existing code | Why it is enough |
|---|---|---|
| repo-local discovery guidance | [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:395) | already teaches governing-doc and sibling-parity inspection |
| trust-only downstream divergence | [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py:277) | already covers trust atomicity without needing a new seam system |
| payload contract extension point | [anvil/harness/schemas.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/schemas.py:391) | already centralizes analysis payload shape |
| structural enforcement layer | [anvil/harness/semantic_validation.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/semantic_validation.py:104) | can enforce seam metadata once fields exist |
| shared bounded/trust seam fixture family | [_BoundedCorroborationHarnessAdapter](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:209) and [_TrustCorroborationHarnessAdapter](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py:365) | gives a stable offline harness seam to evolve into harder tests |
| contract doc surface | [docs/analysis_review_contract.md](/Users/spensermcconnell/__Active_Code/forge/docs/analysis_review_contract.md:205) | already explains shared discovery and can absorb seam-priority rules |

### Minimum change that achieves the goal

Do not build a discovery engine.

Do not let seam choice stay prompt-only.

Do not introduce a second review-state subsystem just for seam tracking.

The minimum complete fix is:

1. Add an explicit `DiscoveryPolicy` to the analysis-review contract.
2. Extend the analysis payload to declare one `primary_seam`, zero or more `secondary_seams_considered`, and a `seam_id` on every recommendation.
3. Require an explicit `seam_expansion_reason` when a recommendation leaves the primary seam.
4. Add semantic validation for seam declaration, seam binding, and expansion reason coverage.
5. Add prompt instructions that make seam choice the first-class operating procedure for proposer, critic, reviser, and auditor.
6. Replace the current synthetic trust seam regression with harder fixtures that can choose the wrong seam unless the contract pulls them back.
7. Update the contract docs and phrase-freeze tests so the written contract matches the executable contract.

Anything bigger is overbuilt.

### Complexity check

Expected touched files:

- `anvil/harness/contracts.py`
- `anvil/harness/prompts.py`
- `anvil/harness/schemas.py`
- `anvil/harness/semantic_validation.py`
- `anvil/harness/report.py`
- `anvil/harness/reporting.py`
- `docs/analysis_review_contract.md`
- `tests/test_harness_prompt_consistency.py`
- `tests/test_harness_semantic_validation.py`
- `tests/test_harness_runner.py`
- `tests/test_harness_reporting.py`
- `tests/test_harness_analysis_contract.py`

That is 12 files, which crosses the smell threshold.

This still passes the smell test because:

- it adds no new runtime service
- it adds no new strategy kind
- it adds no new artifact family
- the extra file count comes from contract, schema, validation, reporting, docs, and test alignment on the same seam

Reducing below this would reintroduce prompt/docs/test drift, which is how we got here.

### Search check

- **[Layer 1]** reuse the existing semantic validation layer instead of inventing runner-side seam analysis
- **[Layer 1]** reuse the current shared discovery guidance instead of rewriting discovery from scratch
- **[Layer 1]** reuse the existing bounded/trust harness fixture family instead of inventing an unrelated synthetic workspace
- **[Layer 3]** make seam choice explicit and validated, because prompt guidance alone cannot prove priority

No external web search is needed. This is repo-local contract work.

### TODOS cross-reference

[TODOS.md](/Users/spensermcconnell/__Active_Code/forge/TODOS.md:1) already carries the broader product questions about bounded vs trust shape.

No current TODO blocks this slice.

No new TODO should be created unless implementation exposes a separate follow-up, such as report-side seam visualization that is useful but not needed for correctness.

### Completeness check

Take the complete version.

Prompt guidance without payload declaration is not enough.

Payload fields without semantic validation are not enough.

Semantic validation without harder wrong-seam regressions is not enough.

This is a lake:

- contract
- payload
- validation
- prompts
- docs
- regressions

### Distribution check

No new artifact type.

No packaging or CI pipeline change is required.

## Architecture Review

### Current flow

```text
task.files_hint
    │
    ▼
shared repo-local discovery guidance
    │
    ├── inspect governing doc when needed
    ├── inspect sibling workflow when needed
    └── keep corroborating files in evidence/review_surface
            │
            ▼
model still chooses whichever plausible seam feels most salient
            │
            ├── no primary seam recorded
            ├── no secondary seam rationale recorded
            ├── no recommendation-to-seam binding
            └── no validator can reject seam drift
```

### Target flow

```text
task.files_hint
    │
    ▼
DiscoveryPolicy defines seam-ordering rules
    │
    ▼
proposer builds candidate seams
    │
    ├── direct files_hint seam
    ├── nearest governing spec/manifest seam
    └── sibling parity seam when parity claims exist
    │
    ▼
proposer ranks seams and declares one primary_seam
    │
    ├── recommendations bind to seam_id
    ├── off-primary recommendations require seam_expansion_reason
    └── secondary_seams_considered records rejected alternatives
    │
    ▼
semantic validation enforces structural seam correctness
    │
    ▼
critic and auditor challenge wrong-seam choice before polishing recommendation wording
    │
    ▼
bounded and trust share the same primary seam
    │
    ├── bounded diverges by caps
    └── trust diverges by admissibility/publication
```

### Canonical rules

Freeze these rules for this slice:

1. `files_hint` is the starting slice for seam construction, not the entire universe.
2. Candidate seams are built from the hinted file path plus nearest governing repo-local sources and sibling parity sources when relevant.
3. Requirement or spec claims must prefer the nearest governing repo-local source over farther plan/runbook prose.
4. Parity or symmetry claims must prefer the nearest sibling implementation/workflow seam over generic process prose.
5. The proposer must declare exactly one `primary_seam`.
6. Every recommendation must bind to a declared `seam_id`.
7. Recommendations outside the primary seam require a non-empty `seam_expansion_reason`.
8. Critic and auditor must challenge seam choice first when a recommendation skipped a higher-ranked seam.
9. Trust atomicity stays downstream of seam choice.
10. `secondary_seams_considered` must not become an uncapped side channel around bounded review discipline.
11. This slice does not decide artifact eligibility from seam metadata, but canonical seam metadata must remain coherent in rendered reports and projected partial artifacts.

### Exact seam-ordering rule

Use this deterministic ordering:

1. Start from the file(s) in `task.files_hint`.
2. If a recommendation depends on a requirement, policy, or spec claim, inspect the nearest governing repo-local doc or manifest for that seam.
3. If a recommendation depends on parity or symmetry, inspect the sibling implementation/workflow that defines the like-for-like baseline.
4. Rank nearer repo-local governing/sibling evidence above farther plan/runbook prose.
5. Pick the seam with the strongest nearest governing support as `primary_seam`.
6. Expand only after the primary seam is exhausted.
7. In bounded mode, secondary seam consideration stays bounded. Recording a seam as "considered" is not permission to inspect an unlimited number of extra files.

For this slice, "primary seam exhausted" means:

- the directly hinted file was inspected
- the nearest governing repo-local source for the claim was inspected when one exists
- the sibling parity baseline was inspected when one exists
- the resulting recommendation family has been evaluated before switching to a different seam

### Canonical data shape

Add this payload family:

```json
{
  "primary_seam": {
    "seam_id": "SEAM-001",
    "summary": "release-watch workflow plus the nearest parity spec",
    "why_primary": "This is the nearest governing seam for the requested automation guidance.",
    "paths": [
      ".github/workflows/codex-cli-release-watch.yml",
      "docs/project_management/next/codex-cli-parity/C1-spec.md"
    ]
  },
  "secondary_seams_considered": [
    {
      "seam_id": "SEAM-002",
      "summary": "snapshot parity workflow seam",
      "why_not_primary": "Useful for parity follow-up, but secondary to the nearer governing release-watch seam.",
      "paths": [
        ".github/workflows/claude-code-update-snapshot.yml",
        ".github/workflows/codex-cli-update-snapshot.yml"
      ]
    }
  ]
}
```

And every recommendation adds:

```json
{
  "seam_id": "SEAM-001",
  "seam_expansion_reason": ""
}
```

If `seam_id != primary_seam.seam_id`, `seam_expansion_reason` must be non-empty.

For bounded mode, also add explicit discipline:

- `secondary_seams_considered` is capped at `2` seam objects in bounded mode
- if more than `2` viable non-primary seams exist, keep only the two highest-ranked secondary seams; inspecting or declaring a third secondary seam requires a recorded `scope_escape`
- secondary seam paths must stay inside the same bounded corroboration discipline rather than becoming a free `files_reviewed` side channel
- if a bounded run needs to leave that discipline, it must use the existing scope-escape path with a reason

### File-by-file implementation plan

#### 1. `anvil/harness/contracts.py`

Add a new `DiscoveryPolicy` dataclass and include it in `AnalysisReviewContract`.

Required fields:

- `prioritize_files_hint`
- `require_primary_seam`
- `require_primary_seam_exhaustion_before_expansion`
- `require_nearest_governing_source_for_spec_claims`
- `require_sibling_baseline_for_parity_claims`
- `prefer_nearer_sources_over_plan_prose`
- `allow_secondary_seams_only_with_reason`
- `require_recommendation_seam_binding`
- `max_secondary_seams_considered_bounded` with default value `2`

Add the policy to `to_dict()` and `build_analysis_review_contract()`.

Do not add mode-specific contract classes.

#### 2. `anvil/harness/schemas.py`

Extend the analysis output schema.

Add:

- `primary_seam`
- `secondary_seams_considered`
- recommendation-level `seam_id`
- recommendation-level `seam_expansion_reason`

Use one shared seam object schema instead of duplicating structure.

Keep the rest of the recommendation payload family intact.

#### 3. `anvil/harness/semantic_validation.py`

Add seam validation.

Required checks:

1. `primary_seam` must exist and contain a non-empty `seam_id`, `summary`, `why_primary`, and `paths`.
2. `primary_seam.paths` must be a subset of `files_reviewed` and the workspace snapshot.
3. `secondary_seams_considered[*].paths` must also be covered by `files_reviewed` and the workspace snapshot.
4. Every recommendation must carry a non-empty `seam_id`.
5. Every recommendation `seam_id` must match either `primary_seam.seam_id` or a declared secondary seam.
6. Recommendations bound to a non-primary seam must carry a non-empty `seam_expansion_reason`.
7. At least one recommendation must remain bound to the primary seam.
8. In bounded mode, `secondary_seams_considered` must contain at most `2` declared secondary seams and cannot introduce extra inspected paths without a scope escape.

This is structural validation only.

It does not try to prove the model picked the objectively correct seam. That stays with critic/auditor review.

#### 4. `anvil/harness/prompts.py`

Add a new seam-selection operating-procedure block separate from repo-local discovery guidance.

Required proposer instructions:

1. Build candidate seams from `files_hint`, nearest governing sources, and sibling parity sources.
2. Rank them before drafting recommendations.
3. Declare one `primary_seam`.
4. Record `secondary_seams_considered` for viable but rejected seams.
5. Bind each recommendation to a `seam_id`.
6. Do not leave the primary seam without an explicit `seam_expansion_reason`.
7. In bounded mode, keep seam exploration inside bounded corroboration policy; declare at most `2` secondary seams unless a `scope_escape` is recorded, and do not dump exploratory seams into `files_reviewed` just because they were tempting.

Required critic instructions:

1. Challenge seam choice before recommendation polish.
2. Raise `scope_drift` or `missing_evidence` when a recommendation skipped a higher-ranked governing/sibling seam.
3. Reject reviews that justify a farther plan/runbook seam while nearer repo-local evidence exists.
4. In bounded mode, flag secondary seam exploration that silently widened the review beyond bounded discipline.

Required reviser instructions:

1. Repair wrong-seam drafts by returning to the higher-ranked seam first.
2. Preserve recommendation order where possible while rebinding seam metadata.
3. Collapse gratuitous secondary seams instead of carrying them forward as audit clutter.

Required auditor instructions:

1. Do not return clean acceptance while the wrong seam remains primary.
2. Do not accept off-primary recommendations without a justified seam expansion.
3. Do not return clean acceptance when bounded mode used seam metadata to bypass corroboration limits.

Keep the existing shared repo-local discovery guidance block. The new seam-selection block should sit above it.

#### 5. `tests/test_harness_prompt_consistency.py`

Freeze the new seam-selection procedure.

Required assertions:

- proposer instructions include candidate-seam ranking and primary-seam declaration
- critic instructions challenge wrong seam before wording polish
- reviser instructions return to the higher-ranked seam
- auditor instructions block clean acceptance on wrong-seam persistence
- the existing shared repo-local discovery block still exists
- trust atomicity remains a separate downstream block
- bounded-mode seam exploration discipline is frozen explicitly

#### 6. `tests/test_harness_semantic_validation.py`

Add seam-validation coverage.

Required cases:

- valid payload with `primary_seam`, `secondary_seams_considered`, and recommendation `seam_id`
- reject missing `primary_seam`
- reject recommendation `seam_id` that does not match a declared seam
- reject non-primary recommendation without `seam_expansion_reason`
- reject seam paths outside `files_reviewed`
- reject bounded payloads that declare more than `2` secondary seams without a scope escape
- reject bounded payloads where a third-seam path was inspected without a scope escape
- accept trust payloads that carry seam metadata plus existing trust metadata

#### 7. `tests/test_harness_runner.py`

Replace the current synthetic seam proof with harder regressions.

Required changes:

1. Keep the existing bounded/trust seam fixture family, but stop treating inheritance alone as proof of seam correctness.
2. Add seam metadata to the bounded/trust fixture payloads.
3. Add one wrong-seam fixture where farther plan/runbook prose is tempting but a nearer governing spec exists.
4. Add one review-stage fixture where critic raises the seam-selection defect.
5. Add one audit-stage fixture where clean acceptance is blocked because accepted recommendations stayed on the wrong seam.
6. Keep the bounded/trust parity test, but assert they share the same `primary_seam` on the same task/workspace even if trust later withholds one recommendation.
7. Add a bounded-mode regression where exploratory third-secondary-seam inspection exceeds the hard `2`-seam policy unless the validator or reviewer pushes back.

Required summary assertions:

- bounded and trust expose the same `primary_seam.seam_id`
- recommendation titles may differ in admissibility outcome, not in the chosen primary seam
- trust withholding still comes from existing admissibility rules, not a different seam family

#### 8. `anvil/harness/report.py` and `anvil/harness/reporting.py`

Surface canonical seam state in human-readable artifacts.

Required behavior:

1. `REPORT.md` renders run-canonical seam state: the declared `primary_seam` and any run-canonical `secondary_seams_considered`.
2. `PARTIAL_ANSWER.json` keeps the original `primary_seam` object unchanged and filters `secondary_seams_considered` down to only seams that still back at least one included recommendation.
3. If a partial artifact excludes every recommendation bound to a secondary seam, that seam must not remain in the projected `secondary_seams_considered` list.
4. If the canonical `primary_seam` remains part of the run context but no included recommendation in the projected subset still binds to it, `PARTIAL_ANSWER.json` must add `"primary_seam_projection_status": "retained_without_included_recommendations"`.
5. When `primary_seam_projection_status == "retained_without_included_recommendations"`, `PARTIAL_ANSWER.md` must render this exact sentence in the seam section: `Canonical primary seam retained for run context; no included recommendation in this artifact binds to it.`

This keeps seam state inspectable where users actually read results.

#### 9. `docs/analysis_review_contract.md`

Document the deterministic seam-selection contract.

Required doc shape:

1. Shared discovery remains the cross-mode rule.
2. Add `DiscoveryPolicy` as the seam-ordering contract.
3. State that one primary seam is declared per draft.
4. State that recommendations bind to declared seams.
5. State that leaving the primary seam requires explicit reason.
6. State that bounded mode cannot use secondary seams as an uncapped discovery side channel.
7. Keep trust atomicity and publication sections intact and downstream.

#### 10. `tests/test_harness_reporting.py`

Add reporting and projection coverage.

Required cases:

- report renders primary seam metadata
- report renders retained secondary seam metadata
- partial artifact projection keeps seam metadata coherent with included recommendations
- projected artifacts do not preserve stale secondary seams that no longer back any included recommendation
- projected partial JSON sets `primary_seam_projection_status` exactly to `retained_without_included_recommendations` when the canonical primary seam has no included recommendation bindings
- projected partial markdown renders the exact retained-primary note sentence when that status is present

#### 11. `tests/test_harness_analysis_contract.py`

Add phrase-freeze checks for:

- `DiscoveryPolicy`
- one declared `primary_seam`
- recommendation seam binding
- required reason when leaving the primary seam
- trust/bounded shared primary-seam principle
- bounded secondary seams are not an uncapped side channel

## Code Quality Review

### Engineering constraints

1. Keep seam choice explicit and boring.
2. Reuse the existing semantic validation layer.
3. Do not hide seam state inside freeform rationale text.
4. Do not add a new runner-owned discovery subsystem.
5. Keep trust atomicity separate from seam choice.
6. Use one shared seam object schema instead of duplicating payload shapes.
7. Keep the diff local to contract/prompt/schema/validation/test surfaces.
8. If seam metadata is canonical, render it in reports where humans can see it.

### Opinionated recommendation

Make seam state model-authored and validator-enforced.

Not runner-derived only, because the review stages need something explicit to challenge.

Not prompt-only, because that is the bug we are fixing.

The right split is:

- model-authored declaration of seam choice
- semantic validation for structural correctness
- critic/auditor for semantic correctness
- report/projection rendering for audit visibility

That is engineered enough.

## Test Review

### Test framework

This repo uses `pytest`.

### Code path coverage

```text
PLAN CHANGE COVERAGE
===========================
[+] anvil/harness/contracts.py
    │
    ├── [GAP] DiscoveryPolicy exists in the contract
    └── [GAP] contract serialization exposes seam-ordering rules

[+] anvil/harness/schemas.py
    │
    ├── [GAP] analysis payload accepts primary_seam
    ├── [GAP] analysis payload accepts secondary_seams_considered
    └── [GAP] recommendation payload accepts seam_id + seam_expansion_reason

[+] anvil/harness/semantic_validation.py
    │
    ├── [GAP] reject missing primary_seam
    ├── [GAP] reject unknown recommendation seam_id
    ├── [GAP] reject non-primary seam without expansion reason
    ├── [GAP] reject seam paths outside files_reviewed/workspace
    └── [GAP] reject bounded secondary-seam sprawl without policy coverage

[+] anvil/harness/prompts.py
    │
    ├── [GAP] proposer ranks candidate seams and declares primary_seam
    ├── [GAP] critic challenges wrong-seam choice first
    ├── [GAP] reviser rebinds recommendations to the higher-ranked seam
    └── [GAP] auditor blocks clean acceptance on persistent wrong-seam choice

[+] tests/test_harness_runner.py
    │
    ├── [GAP] bounded and trust expose the same primary_seam
    ├── [GAP] wrong-seam proposer fixture is pulled back by review
    ├── [GAP] auditor blocks wrong-seam clean acceptance
    ├── [GAP] bounded secondary seams cannot silently bypass caps
    └── [★★★ EXISTING] trust withholding still runs through admissibility rules

[+] anvil/harness/report.py + anvil/harness/reporting.py + tests/test_harness_reporting.py
    │
    ├── [GAP] primary seam rendered in REPORT.md
    ├── [GAP] retained secondary seams rendered in REPORT.md
    └── [GAP] partial artifact projection keeps seam metadata coherent

[+] docs/analysis_review_contract.md + tests/test_harness_analysis_contract.py
    │
    ├── [GAP] DiscoveryPolicy wording frozen
    ├── [GAP] primary seam wording frozen
    ├── [GAP] seam-expansion requirement frozen
    └── [GAP] bounded secondary-seam discipline frozen

─────────────────────────────────
COVERAGE TARGET: 21/21 paths locked
QUALITY TARGET: all new assertions ★★★
─────────────────────────────────
```

### Required test commands

Run exactly these:

```bash
poetry run pytest -q tests/test_harness_prompt_consistency.py
poetry run pytest -q tests/test_harness_semantic_validation.py
poetry run pytest -q tests/test_harness_runner.py
poetry run pytest -q tests/test_harness_reporting.py
poetry run pytest -q tests/test_harness_analysis_contract.py
```

### Manual acceptance

After the patch, rerun bounded and trust on the same task and workspace.

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

1. bounded and trust declare the same `primary_seam`
2. both modes inspect the same governing seam before any secondary expansion
3. divergence is allowed only in admissibility/publication, not in primary seam choice
4. any recommendation outside the primary seam has an explicit expansion reason
5. trust may still publish `PARTIAL_ANSWER.*`, but not because it switched to a different primary seam
6. `REPORT.md` and any projected partial artifact still expose coherent seam metadata

## Performance Review

No meaningful runtime risk is expected.

This is contract, schema, validation, prompt, and regression work.

The only runtime cost is small extra payload surface and validation checks, which is negligible relative to existing semantic validation.

## Failure Modes Registry

| Failure mode | Test covers it | Error handling exists | User-visible impact | Required mitigation |
|---|---|---|---|---|
| proposer declares no primary seam | yes | yes | review stages cannot prove what seam won | semantic validation rejects payload |
| bounded mode uses secondary seams as an uncapped `files_reviewed` side channel | yes | no | bounded silently stops being bounded, making trust/bounded comparisons noisy | DiscoveryPolicy cap plus semantic-validation and runner regressions |
| recommendations bind to an undeclared seam | yes | yes | seam drift becomes invisible under valid-looking evidence | semantic validation rejects unknown seam_id |
| wrong-seam recommendation leaves primary seam without justification | yes | yes | farther runbook/prose seams keep displacing nearer governing seams | require seam_expansion_reason |
| critic polishes recommendation wording without challenging wrong seam | yes | no | the system accepts well-worded but mis-prioritized advice | prompt consistency coverage plus review-stage regression |
| projected partial artifacts keep stale seam metadata after recommendation filtering | yes | no | users read an audit trail that no longer matches the visible recommendation subset | report/projection tests and rendering updates |
| trust and bounded still diverge on primary seam in live reruns | yes | no | trust feels arbitrarily different from bounded for the same task | bounded/trust primary-seam parity regression plus manual rerun |

Critical gap to avoid: a payload that contains seam fields but still allows wrong-seam recommendations to pass clean review because no review-stage prompt ever challenges seam correctness.

## What Already Exists

Use these instead of rebuilding anything:

- the current shared repo-local discovery block
- the current trust atomicity block
- the current semantic validation layer
- the current report/projection surfaces
- the current bounded/trust regression fixture family
- the current contract-doc and phrase-freeze surfaces

## NOT in Scope

- new strategy kinds
- runner-owned discovery engine
- trust admissibility redesign
- publication-state redesign
- topic-ledger redesign
- new artifact families
- CI or packaging work

## TODOS.md

No new TODO should be added from this slice.

If report-side seam visualization becomes desirable after the contract lands, that can be proposed as a separate follow-up.

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|------|-----------------|------------|
| DiscoveryPolicy + schema + validation | `anvil/harness/` | — |
| Prompt seam-procedure updates | `anvil/harness/` | DiscoveryPolicy contract shape |
| Report/projection seam rendering | `anvil/harness/` | schema fields settled |
| Contract doc update | `docs/` | DiscoveryPolicy naming settled |
| Test convergence | `tests/` | contract, prompt, schema, validation, reporting settled |

### Parallel lanes

- Lane A: `anvil/harness/contracts.py`, `anvil/harness/schemas.py`, `anvil/harness/semantic_validation.py`
- Lane B: `anvil/harness/prompts.py` after the contract shape is fixed
- Lane C: `anvil/harness/report.py` and `anvil/harness/reporting.py` after schema fields are fixed
- Lane D: `docs/analysis_review_contract.md` after DiscoveryPolicy naming is fixed
- Lane E: `tests/` after A, B, C, and D settle

### Execution order

Launch Lane A first.

Once the field names are stable, Lane B, Lane C, and Lane D can run in parallel.

Then run Lane E as the convergence lane.

### Conflict flags

- Lane A, Lane B, and Lane C all touch `anvil/harness/`, so parallelization there only works after field names are frozen and ownership is explicit.
- Lane E must stay last because it freezes the final contract, prompt, validator, and reporting behavior.

## Completion Summary

- Step 0: Scope Challenge, hold scope accepted
- Design Review: skipped, no UI scope
- Architecture Review: complete
- Code Quality Review: complete
- Test Review: diagram produced, 21 coverage targets identified
- Performance Review: 0 issues
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none
- Failure modes: 0 unresolved critical gaps if seam declaration, bounded secondary-seam discipline, reporting coherence, validation, and wrong-seam regressions all land
- Outside voice: skipped for this narrow repo-local slice
- Parallelization: 5 lanes, 1 foundation lane, 3 conditional parallel lanes, 1 convergence lane
- Lake Score: 8/8 key decisions chose the complete option

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Replace the old shared-discovery plan with a seam-selection enforcement plan | mechanical | pragmatic | the old slice is already landed and no longer matches the live bug | continuing to optimize the solved prompt-symmetry slice |
| 2 | CEO | Treat seam drift as a contract-and-validation bug, not a publication bug | mechanical | explicit over clever | the remaining failure is wrong primary seam choice, not artifact selection | reopening publication semantics |
| 3 | Eng | Add seam state to the payload instead of keeping it prompt-only | mechanical | explicit over clever | review stages and validators need something inspectable to challenge | more prose without structure |
| 4 | Eng | Reuse semantic validation instead of building a discovery engine | mechanical | minimal diff | the repo already has a strong structural enforcement layer | new runner-owned seam analysis subsystem |
| 5 | Eng | Keep trust atomicity separate from seam choice | mechanical | engineered enough | seam selection and admissibility are different concerns | fusing seam choice into trust publication behavior |
| 6 | Eng | Prevent bounded secondary seams from becoming an uncapped discovery side channel | mechanical | boil the lake | otherwise bounded mode silently stops being bounded | leaving `secondary_seams_considered` unlimited |
| 7 | Eng | Surface seam metadata in reports and projected partial artifacts | mechanical | explicit over clever | canonical metadata is not useful if users cannot see it in the rendered audit trail | keeping seam state JSON-only |
| 8 | Eng | Accept the 12-file slice because contract/schema/validator/reporting/docs/tests all participate in the same seam bug | taste | boil the lake | cutting reporting or cap-discipline work would recreate drift or hide it | a smaller but incomplete patch |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/autoplan` | Scope & strategy | 1 | plan_updated | Rebased the stale shared-discovery plan onto the real remaining problem: deterministic seam selection, seam binding, and validator-backed review enforcement |
| Office Hours Design Doc | `/office-hours` | Design rationale & milestone shape | 1 | approved | Approved Approach C: ship the in-loop seam contract now, but shape it so a future `adjudicate` / `deliberate` request gate can reuse the same seam model |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | Found 2 non-critical gaps and folded both into the plan: cap bounded secondary-seam exploration and keep seam metadata coherent in `REPORT.md` and projected `PARTIAL_ANSWER.*` artifacts |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No UI scope detected in `PLAN.md`, `anvil/harness/*`, or the run artifacts |

**VERDICT:** PLAN UPDATED FOR NEXT ITERATION. The slice is now locked to deterministic seam selection with explicit seam metadata, bounded secondary-seam discipline, reporting/projection coherence, and a future-compatible path to a pre-loop request gate.
