<!-- /autoplan restore point: /Users/spensermcconnell/.gstack/projects/forge/feat-bounded-work-redesign-autoplan-restore-20260417-193342.md -->

# Unified Plan: `analysis_review_bounded_v1` + `analysis_review_trust_v1`

## Purpose

Unify the bounded-work and trust-hardening threads into one implementable plan.

The repo already landed most of the bounded-review contract under `analysis_review_v1`. The remaining work is not "finish bounded review" in isolation. The real remaining delta is:

1. make bounded and trust behavior explicit, user-selectable strategy kinds
2. keep one harness/subgraph/runner path instead of forking the system
3. harden accepted-run semantics so `accepted` means something reproducible and honest

This plan is the single source of truth for that combined rollout.

## End State

After this plan lands:

- users can choose `analysis_review_bounded_v1` for the cheaper bounded workflow
- users can choose `analysis_review_trust_v1` for stricter accepted-run semantics
- `analysis_review_v1` remains a temporary alias to bounded mode for one release window, with a migration warning
- both modes reuse the same subgraph and almost all of the same payload shape
- trust mode adds stricter validation, provenance, and verdict downgrade rules without inventing a second harness

## Step 0: Scope Challenge

### Current repo truth

The bounded-review tranche is mostly already present in code:

| Existing surface | Evidence in repo | What it already solves |
|---|---|---|
| `anvil/harness/contracts.py` | `analysis_review_v1_contract_v3` + `BoundedReviewPolicy` | bounded review caps and shared contract defaults |
| `anvil/harness/schemas.py` | `review_surface`, `scope_escapes`, recommendation review schemas | bounded structured payload shape |
| `anvil/harness/prompts.py` | bounded-review proposer / critic / auditor / reviser instructions | reviewer bounded-work guidance |
| `anvil/harness/semantic_validation.py` | evidence caps, `files_reviewed`, `review_surface`, issue-cap checks | bounded semantic enforcement |
| `anvil/harness/runner.py` | analysis review loop, issue ledger, accepted-with-warnings handling, bounded summary | one working orchestration path |
| `anvil/harness/report.py` | bounded review reporting section | human-readable bounded metrics |
| `tests/test_harness_*` | contract, prompt, semantic validation, runner coverage | baseline regression rails for v3 behavior |

### What is not solved yet

The repo does **not** yet provide the public bounded/trust split or trustworthy accepted-run semantics:

- strategy kinds are still hard-coded around `analysis_review_v1` in `anvil/harness/types.py`, `anvil/harness/state.py`, `anvil/harness/builder.py`, `anvil/harness/nodes/validator_preflight.py`, and `anvil/harness/runner.py`
- there is no trust-focused contract surface for provenance, grounding, or taxonomy override enforcement
- `semantic_validation.json` is not bound to the exact payload it validated
- `files_reviewed` is still model-authored, not authoritative proof
- verdict downgrade rules are still too optimistic for inference-backed accepted output
- examples and docs still present one public mode

### Minimum viable scope

The minimum complete scope is:

1. explicit public mode split with alias migration
2. one additive contract/schema/prompt extension for trust semantics
3. semantic validation, verdict, and report rewrites for trust mode
4. tests, fixtures, examples, docs, and one replay comparison

### Scope reduction decisions

This plan intentionally does **not** do these larger moves:

- no second subgraph or second harness runner
- no packet subsystem beyond the landed `review_surface`
- no hard reviewer sandbox or read-tracing platform project in this tranche
- no benchmark dashboard product build
- no provider-turn tuning as the primary correctness mechanism

### Search check

- **[Layer 1]** Reuse the existing analysis-review subgraph, runner, issue ledger, and report surface.
- **[Layer 1]** Reuse the current bounded payload shape, then add mode-specific enforcement.
- **[Layer 3]** Keep trust mode honest by tightening validation and verdict semantics instead of pretending prompt text alone creates proof.

No framework built-in replaces this cleanly. This is harness-specific policy, so first-principles design on top of the existing surfaces is the right move.

### Complexity check

This is still a multi-module change. Treat it as a smell and keep the implementation boxed into four slices:

- public mode split
- contract/schema/prompt hardening
- validation/verdict/reporting hardening
- tests/examples/docs/replay

That keeps structural and behavioral changes understandable and reviewable.

### Completeness check

The complete version is worth doing now. Shipping only the public mode split without trust semantics would produce a cleaner config surface but would still leave `accepted` too soft. Shipping only trust semantics under `analysis_review_v1` would hide materially different user behavior behind one name. Both halves are required for a clean result.

### Distribution check

No new binary, package, or container is introduced. Distribution work is not applicable.

## What Already Exists

The plan should build on these existing invariants, not rebuild them:

- stable `AR-###` issue IDs
- proposer -> critic -> reviser -> auditor loop
- recommendation-level review verdicts
- bounded `review_surface`
- `scope_escapes`
- semantic validation hooks
- report rendering for bounded review summaries
- existing harness CLI flow:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_codex_claude.yaml \
  --workspace /path/to/repo \
  --out-root .forge-harness-runs
```

## Unified Architecture Review

### Core architecture decision

Keep **one** analysis-review implementation path, then make the mode explicit at the strategy/config layer.

That means:

- the graph still routes to one analysis-review subgraph
- the runner still owns one analysis-review execution loop
- the contract becomes mode-aware
- schemas stay mostly additive
- semantic validation and reporting become mode-sensitive

This is the boring architecture. That is why it is right.

### Mode model

| Strategy kind | Goal | What it guarantees | What it does not guarantee |
|---|---|---|---|
| `analysis_review_bounded_v1` | predictable review scope and cost | bounded evidence, bounded `review_surface`, bounded issue counts, scoped reporting | authoritative proof of actual reads |
| `analysis_review_trust_v1` | honest accepted-run semantics | bounded review **plus** provenance binding, grounding coverage checks, taxonomy enforcement, verdict downgrades on caveats | hard read sandboxing |
| `analysis_review_v1` | migration alias for one release window | resolves to bounded mode with warning | long-term stable behavior name |

### Contract model

Move from a bounded-only contract to a unified contract version that carries both bounded and trust policy.

Recommended shape:

```python
@dataclass
class TrustReviewPolicy:
    require_taxonomy_override_reason: bool = True
    require_verified_evidence_refs_subset: bool = True
    require_affected_file_coverage: bool = True
    payload_provenance_mode: Literal["none", "payload_hash_and_refs"] = "payload_hash_and_refs"
    downgrade_on_semantic_warnings: bool = True
    downgrade_on_inferred_acceptance: bool = True
    late_auditor_medium_or_higher_policy: Literal["error", "warn"] = "warn"
```

Recommended contract bump:

- current: `analysis_review_v1_contract_v3`
- target: `analysis_review_v1_contract_v4`

Why one contract version instead of mode-specific contract classes:

- minimal diff
- one source of truth
- mode-specific policy can be toggled via explicit fields instead of branching the whole type system

### Unified payload principle

Do **not** split into two unrelated JSON payload families.

Use one additive payload shape where trust mode turns more fields from advisory to required:

- `verified_evidence_refs`
- `checked_files`
- `affected_files`
- `grounding_mode`
- `blocking_class_override_reason`
- payload provenance metadata attached by the runner to semantic-validation artifacts

That keeps bounded and trust modes comparable and avoids duplicated schema churn.

### Target flow

```text
task + strategy kind
        │
        ▼
validator_preflight
  ├── `analysis_review_v1` -> alias warning -> bounded mode
  ├── `analysis_review_bounded_v1`
  └── `analysis_review_trust_v1`
        │
        ▼
unified analysis-review subgraph
        │
        ▼
contract builder
  ├── bounded_review policy
  └── trust_review policy
        │
        ▼
proposer / critic / reviser / auditor
        │
        ▼
runner normalization layer
  ├── canonicalize repo-relative paths
  ├── attach payload hash + normalized refs
  └── preserve issue ledger and review summary
        │
        ▼
semantic validation
  ├── bounded caps
  ├── taxonomy invariants
  ├── verified-evidence subset rules
  ├── affected-file coverage
  └── late-auditor warning policy
        │
        ▼
verdict engine
  ├── accepted
  ├── accepted_with_warnings
  ├── accepted_partial
  └── rejected / needs_revision
        │
        ▼
report + artifacts
```

### Module boundaries

| Module | Responsibility after change |
|---|---|
| `anvil/harness/types.py` | explicit strategy-kind defaults for bounded vs trust modes |
| `anvil/harness/state.py` | expanded `strategy_kind` typing |
| `anvil/harness/builder.py` | route both public strategy kinds to the same analysis-review subgraph |
| `anvil/harness/nodes/validator_preflight.py` | alias migration and auto-fit behavior |
| `anvil/harness/contracts.py` | v4 unified contract, bounded + trust policy |
| `anvil/harness/schemas.py` | additive trust metadata fields |
| `anvil/harness/prompts.py` | mode-specific wording, same payload family |
| `anvil/harness/semantic_validation.py` | mode-sensitive trust enforcement |
| `anvil/harness/runner.py` | provenance binding, honest verdict downgrade, migration warnings |
| `anvil/harness/report.py` / `anvil/harness/reporting.py` | mode-aware and warning-aware summaries |
| `examples/harness/strategies/` | explicit bounded + trust example strategies |
| `docs/analysis_review_contract.md` | public contract and migration docs |

### Architecture-specific production failure scenarios

| Surface | Real failure mode | Plan response |
|---|---|---|
| Strategy split | old configs silently land in the wrong mode | alias warning, explicit tests, docs |
| Contract drift | prompts and validation disagree on trust requirements | contract remains source of truth, prompt-consistency tests updated |
| Provenance artifact | `semantic_validation.json` claims a payload it did not validate | bind artifact to payload hash + normalized refs |
| Taxonomy drift | `blocking_class` mutates issue meaning without explanation | require override reason in trust mode |
| Trust overclaim | trust mode still accepts inference-heavy output as clean | auto-downgrade to `accepted_with_warnings` |

## Code Quality Review

### DRY rules

Do not hard-code the same rule in three places.

The clean version is:

- contract stores defaults and mode policy
- prompts render that contract
- semantic validation enforces that contract
- runner/report explain the resulting decisions

The messy version is:

- prompts invent one trust rule
- semantic validation invents a second
- runner quietly applies a third

That version will rot immediately. Do not build it.

### Explicit-over-clever rules

- add one `TrustReviewPolicy` instead of sprinkling booleans through the runner
- keep one payload family instead of separate bounded/trust schemas
- canonicalize paths once in the runner and reuse that representation everywhere
- keep alias migration behavior obvious and temporary

### Minimal-diff rules

- keep the current `analysis_review_v1` subgraph file
- keep the current issue ledger model
- keep the current report file structure
- avoid new helper modules unless one existing file becomes unreadable

## Implementation Plan

### Slice 1: Public mode split and migration path

**Modules:** `types`, `state`, `builder`, `nodes/validator_preflight`, `runner`, `examples`, `docs`

**Changes**

- add public strategy kinds:
  - `analysis_review_bounded_v1`
  - `analysis_review_trust_v1`
- keep `analysis_review_v1` as a temporary alias to bounded mode
- route both new public kinds to the existing analysis-review subgraph
- update auto-fit logic and warnings so patch tasks still flip to `pfr_v1`, while analysis-review tasks choose bounded mode
- rename the current example strategy to bounded mode and add a trust-mode example
- document the alias removal trigger

**Acceptance**

- users can choose bounded vs trust explicitly
- old configs still run with a clear migration warning
- no second subgraph or second runner path exists

### Slice 2: Unified contract, schema, and prompt hardening

**Modules:** `contracts`, `schemas`, `prompts`, `docs`

**Changes**

- bump to contract v4
- add `TrustReviewPolicy`
- make mode explicit in the contract or derive it from strategy kind once, not ad hoc in prompts
- add additive schema fields:
  - `verified_evidence_refs`
  - `checked_files`
  - `affected_files`
  - `grounding_mode`
  - `blocking_class_override_reason`
- render bounded and trust prompt rules from the same contract
- state clearly in prompt text that trust mode is stricter about coverage, overrides, and warning downgrades

**Acceptance**

- one contract describes both modes
- schema additions are additive where possible
- prompts and docs explain the mode difference concretely

### Slice 3: Semantic validation, verdict engine, and reporting hardening

**Modules:** `semantic_validation`, `runner`, `report`, `reporting`

**Changes**

- bind every semantic-validation artifact to the exact payload it validated
- enforce taxonomy invariants in trust mode:
  - default `blocking_class` must match `kind`
  - override requires explicit reason
- enforce grounding coverage in trust mode:
  - `verified_evidence_refs` must be a subset of normalized evidence refs
  - every non-inferred `affected_file` must be covered by evidence or verified checks
- change late auditor overflow from hard semantic failure to warning policy
- downgrade top-level verdict to `accepted_with_warnings` when:
  - semantic warnings remain
  - any accepted recommendation review is `accept_with_caveat`
  - accepted recommendations rely on inference-only grounding
- clean up section-shape noise so successful runs stop leaking avoidable `none_reason` warnings
- report mode, warning causes, direct-vs-inferred grounding, and provenance binding clearly

**Acceptance**

- trust-mode accepted runs are auditable after the fact
- real late issues survive as warnings instead of being hidden by hard caps
- reports explain caveats instead of pretending everything is clean

### Slice 4: Tests, fixtures, examples, docs, and replay validation

**Modules:** `tests`, `tests/fixtures`, `examples`, `docs`

**Changes**

- add contract serialization coverage for bounded + trust modes and alias migration
- add prompt-consistency coverage for both public modes
- add semantic-validation fixtures for taxonomy override, provenance mismatch, affected-file coverage, verified-evidence subset, canonical path normalization, and late-auditor warning behavior
- add runner coverage for alias warnings, trust verdict downgrades, and report summaries
- add bounded and trust example strategies
- run one bounded replay and one trust replay against the same task, then compare verdict, warnings, accepted recommendation count, and runtime

**Acceptance**

- test suite proves the new semantics
- examples are copyable without reading the implementation
- one replay confirms trust mode is stricter without becoming unusable

## Test Review

### Code path coverage

```text
CODE PATH COVERAGE
===========================
[+] strategy kind routing
    │
    ├── [GAP] `analysis_review_bounded_v1` selects the existing analysis-review path
    ├── [GAP] `analysis_review_trust_v1` selects the existing analysis-review path
    └── [GAP] `analysis_review_v1` aliases to bounded mode with warning

[+] contract / schema / prompt surface
    │
    ├── [GAP] unified contract v4 serializes bounded + trust policy correctly
    ├── [GAP] trust metadata fields are rendered consistently in prompts
    └── [GAP] bounded mode and trust mode differ only where intended

[+] semantic validation
    │
    ├── [GAP] taxonomy override without reason fails in trust mode
    ├── [GAP] invalid `verified_evidence_refs` fails
    ├── [GAP] uncovered non-inferred `affected_files` fails
    ├── [GAP] payload hash mismatch fails or warns loudly
    └── [GAP] late auditor overflow warns instead of hard-failing

[+] verdict engine + reporting
    │
    ├── [GAP] semantic warnings downgrade `accepted` -> `accepted_with_warnings`
    ├── [GAP] inference-backed accepted output downgrades honestly
    ├── [GAP] reports show mode + caveat causes
    └── [GAP] canonical repo-relative paths render consistently
```

### User flow coverage

```text
USER FLOW COVERAGE
===========================
[+] Bounded mode
    ├── [GAP] [->INT] explicit bounded strategy runs with current bounded behavior
    ├── [GAP] [->INT] legacy `analysis_review_v1` config aliases to bounded mode with warning
    └── [GAP] [->INT] report identifies bounded mode clearly

[+] Trust mode
    ├── [GAP] [->INT] direct-observation accepted run stays `accepted`
    ├── [GAP] [->INT] inference-backed accepted run downgrades to `accepted_with_warnings`
    ├── [GAP] [->INT] semantic warning on accepted run downgrades verdict
    └── [GAP] [->INT] report explains exactly why the downgrade happened

[+] Provenance honesty
    ├── [GAP] [->UNIT] payload hash mismatch is caught
    ├── [GAP] [->UNIT] invalid affected-file coverage is caught
    └── [GAP] [->INT] canonicalized path rendering stays stable across artifacts

[+] Late-auditor behavior
    ├── [GAP] [->UNIT] one justified late issue stays valid
    ├── [GAP] [->UNIT] two justified late issues produce warnings, not false cleanliness
    └── [GAP] [->INT] summary surfaces review churn honestly
```

```text
---------------------------------
COVERAGE TARGET
  Existing bounded-review rails remain green
  New trust-hardening semantics get direct unit + integration coverage
GAPS TO CLOSE
  mode split, alias migration, provenance binding, taxonomy enforcement,
  grounding coverage, warning downgrade, trust-mode reporting
---------------------------------
```

### Required tests

1. `tests/test_harness_analysis_contract.py`
   Cover explicit public kinds, alias migration defaults, unified contract v4 serialization, and trust policy defaults.

2. `tests/test_harness_prompt_consistency.py`
   Assert bounded vs trust prompts render the right guarantees, downgrade rules, and coverage language.

3. `tests/test_harness_semantic_validation.py`
   Add fixtures for taxonomy override without reason, invalid `verified_evidence_refs`, uncovered `affected_files`, payload provenance mismatch, canonical path collisions, and late-auditor warning behavior.

4. `tests/test_harness_runner.py`
   Add integration coverage for explicit bounded mode, trust mode, legacy alias warning, verdict downgrade rules, and report summaries.

5. `tests/fixtures/harness/analysis_review_semantic_cases.json`
   Add positive and negative trust-mode fixtures plus alias-migration fixtures.

6. Replay validation
   Run the same task once with bounded mode and once with trust mode, then compare:
   - top-level verdict
   - warnings
   - accepted recommendation count
   - runtime

### Verification commands

```bash
poetry run pytest -q \
  tests/test_harness_analysis_contract.py \
  tests/test_harness_prompt_consistency.py \
  tests/test_harness_semantic_validation.py \
  tests/test_harness_runner.py
```

After the new example strategies exist:

```bash
poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_bounded_codex_claude.yaml \
  --workspace /Users/spensermcconnell/__Active_Code/forge \
  --out-root .forge-harness-runs

poetry run python -m anvil.cli harness-run \
  --task examples/harness/tasks/recommend_automation_improvements.yaml \
  --strategy examples/harness/strategies/analysis_review_trust_codex_claude.yaml \
  --workspace /Users/spensermcconnell/__Active_Code/forge \
  --out-root .forge-harness-runs
```

## Failure Modes

| New codepath | Real production failure | Test planned | Error handling planned | User-visible outcome |
|---|---|---|---|---|
| Alias migration | legacy config silently changes behavior | Yes | explicit warning + docs | clear migration warning |
| Trust provenance | validation artifact no longer matches final payload | Yes | fail or hard warning in trust mode | clear harness error |
| Taxonomy override | issue meaning changes silently | Yes | validation error unless override reason exists | clear harness error |
| Affected-file coverage | recommendation scope outruns proof | Yes | validation error or warning downgrade | clear warning/caveat |
| Late auditor overflow | real issues get hidden to satisfy a cap | Yes | preserve issues, warn on churn | honest warning-clean run |
| Path normalization drift | one file appears under multiple spellings | Yes | canonicalize once in runner | stable report output |
| Inference-heavy acceptance | trust mode still reports clean accept | Yes | auto-downgrade to `accepted_with_warnings` | honest trust verdict |

**Critical gap rule**

Any path with all three of these is release-blocking:

- no test
- no validation or downgrade behavior
- silent user-visible drift

## Performance Review

### Main performance constraint

Trust mode must be stricter, but it cannot become a fake "deep audit" that simply burns more tokens without higher integrity.

### Performance guidance

- keep provenance binding to payload hash + normalized refs in this tranche
- do **not** add repo-wide re-scans to simulate proof
- keep bounded mode as the intentionally cheaper path
- keep late-auditor warning handling metadata-only, not another review pass
- compare bounded vs trust mode on one replay before calling the split done

### Performance smell test

If trust mode needs repo-wide replay or heavy read tracing to feel honest, the tranche is too big. In that case, ship the payload-hash and coverage hardening now, then defer hard read provenance to a follow-up project.

## NOT in Scope

- a second analysis-review subgraph
- a second runner implementation
- hard sandboxing or authoritative read tracing for reviewer file access
- benchmark dashboard or multi-task trust analytics
- provider-turn budget tuning as the main correctness boundary
- removing `timeout_sec`
- broader harness redesign outside the analysis-review surfaces touched here

## Worktree Parallelization Strategy

### Dependency table

| Step | Modules touched | Depends on |
|---|---|---|
| A. Public mode split | `types`, `state`, `builder`, `nodes`, `runner`, `examples` | — |
| B. Unified contract + prompt/schema hardening | `contracts`, `schemas`, `prompts`, `docs` | — |
| C. Trust validation + verdict/reporting | `semantic_validation`, `runner`, `report`, `reporting` | A, B |
| D. Tests + fixtures for routing and contract/prompt behavior | `tests`, `tests/fixtures` | A, B |
| E. Replay validation + docs/examples polish | `examples`, `docs`, run artifacts | C, D |

### Parallel lanes

- **Lane A:** Step A
  Public mode split and alias migration.

- **Lane B:** Step B
  Unified contract, schema, and prompt work.

- **Lane C:** Step C
  Trust validation, verdict, and report hardening. Must wait for A + B.

- **Lane D:** Step D
  Contract/prompt/routing tests. Can start once A + B stabilize.

- **Lane E:** Step E
  Replay comparison and final docs/examples polish. Must wait for C + D.

### Execution order

Launch **Lane A** and **Lane B** in parallel worktrees.

When both land, launch **Lane C** and **Lane D**.

After C + D merge, run **Lane E**.

### Conflict flags

- Lane A and Lane C both touch `runner`, so they should not run concurrently.
- Lane B and Lane E both touch `docs` and `examples`, so keep docs finalization in E after the behavioral work lands.
- Lane D should avoid editing production modules except for tiny fixture follow-ups. Its job is to lock in behavior, not redesign interfaces.

### If you want the lowest-risk path

Run A -> B -> C -> D -> E sequentially. The core harness files are shared enough that fake parallelism is worse than one clean merge.

## Review Completion Summary

- Step 0: Scope Challenge — bounded-review cleanup was reframed into explicit public modes plus trust-hardening
- Architecture Review: one harness path, one additive payload family, one unified contract
- Code Quality Review: contract remains source of truth, path normalization happens once, no duplicate policy logic
- Test Review: explicit mode split, alias migration, provenance, taxonomy, coverage, and downgrade semantics all require new tests
- Performance Review: trust mode gets stricter semantics, not expensive fake proof
- NOT in scope: written
- What already exists: written
- TODOS.md updates: none proposed
- Failure modes: critical gaps identified and covered by the plan
- Parallelization: 5 steps, 2 early parallel lanes, then converging sequential finish
- Lake Score: the complete option is to ship explicit modes **and** honest trust semantics together
