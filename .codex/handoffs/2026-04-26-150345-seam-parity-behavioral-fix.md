# Handoff: Seam Parity Behavioral Fix

## Session Metadata
- Created: 2026-04-26 15:03:45
- Project: /Users/spensermcconnell/__Active_Code/forge
- Branch: feat/bounded-work-redesign
- Session duration: ~2 hours

### Recent Commits (for context)
  - c1b90d0 Add seam parity checker and docs
  - 898c2a6 Tighten seam parity closure plan
  - 30e46f5 Implement reviewer-specific seam guidance in prompts
  - 2c876e5 Split seam review guidance by role
  - ca68a52 Implement analysis-stage scope escapes for bounded overflow

## Handoff Chain

- **Continues from**: None (fresh start)
- **Supersedes**: None

> This is the first handoff for this task.

## Current State Summary

This session implemented the missing behavioral fix for seam parity at the harness runtime layer. The core change is in the analysis payload normalization path: seam IDs are now canonicalized from normalized seam path sets before schema revalidation, semantic validation, provenance binding, and downstream review stages. This means bounded and trust runs that inspect the same seam should now serialize the same seam identity even if the model originally used different labels. The targeted code/test suites are green. The branch is not fully closed yet because fresh live bounded reruns against `/Users/spensermcconnell/__Active_Code/atomize-hq/unified-agent-api` are currently failing earlier for a separate bounded payload-discipline issue, so a full fresh bounded+trust parity proof was not completed in this session.

## Codebase Understanding

### Architecture Overview

The analysis-review harness accepts model payloads in `anvil/harness/runner.py`, normalizes them, revalidates them against schema, then runs semantic validation before carrying stage outputs forward. Before this session, seam identity was model-authored free text and the runner merely copied it into `analysis_review_status`. The new runtime fix inserts seam canonicalization into `_normalize_analysis_review_payload`, which is the right point because it runs before semantic validation and before later review stages see the payload. Prompt guidance in `anvil/harness/prompts.py` now explicitly says seam identity is path-set identity, but the real enforcement is runner-owned. Tests in `tests/test_harness_runner.py` are the main behavioral regression surface for this work.

### Critical Files

| File | Purpose | Relevance |
|------|---------|-----------|
| /Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py | Harness runtime, payload normalization, semantic validation wiring, final summary construction | Main implementation point for canonical seam identity and later normalizer hardening |
| /Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py | Prompt construction for proposer/critic/reviser/auditor | Added explicit seam-identity guidance so the model instructions match the runtime invariant |
| /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py | End-to-end and normalization regressions for harness behavior | Most of the new coverage and adapted expectations live here |
| /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py | Prompt contract consistency checks | Updated to assert the new seam-identity guidance line |
| /Users/spensermcconnell/__Active_Code/forge/scripts/check_seam_parity.py | Cross-run checker comparing canonical seam state across summaries | Already landed before this session; used as the acceptance surface |
| /Users/spensermcconnell/__Active_Code/forge/PLAN.md | Closure plan for live seam parity acceptance | Defines the intended closure condition and manual acceptance loop |

### Key Patterns Discovered

- Analysis payload normalization in `HarnessRunner._normalize_analysis_review_payload()` is the natural place for runner-owned corrections. It already normalizes workspace refs, evidence lists, and review-surface refs before semantic validation.
- Semantic validation is strict and catches real model-output drift quickly. A live run can fail well before parity checking if the proposer or critic emits malformed bounded-review metadata.
- The trust and bounded strategy YAML files are nearly identical; the real policy divergence is contract/prompt behavior, not separate orchestration.
- The seam parity checker is offline and reads only `summary.json`. It is not the source of the current remaining failure.

## Work Completed

### Tasks Finished

- [x] Diagnosed the missing behavioral fix as runtime seam identity, not reporting or checker logic
- [x] Implemented runner-owned seam-ID canonicalization from normalized seam path sets
- [x] Updated prompt guidance so seam identity is explicitly framed as normalized path-set identity
- [x] Added regressions proving relabeled trust seams canonicalize back onto bounded seam identity
- [x] Hardened workspace-ref normalization for `/.github/...` style outputs from live critic runs
- [x] Hardened closure-review normalization to drop bogus closure records referencing unknown prior-open IDs
- [x] Ran targeted test suites and got them green
- [x] Attempted fresh live reruns against the atomize workspace and captured the new failure mode

### Files Modified

| File | Changes | Rationale |
|------|---------|-----------|
| /Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py | Added `_canonicalize_analysis_payload_seams()`, `_canonical_seam_id_for_paths()`, leading-slash workspace-ref handling, and dropping of unknown closure-review records during normalization | Make seam identity deterministic at runtime and harden unrelated live normalization fragility discovered while trying to prove parity |
| /Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py | Added one seam-guidance line: same normalized paths means same seam | Keep model instructions aligned with the runtime invariant |
| /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py | Added canonical seam-ID constants derived from path sets, relabeled-trust parity regression, normalizer hardening tests, and updated expectations for canonical IDs | Cover the new runtime behavior and keep tests aligned with path-derived seam identity |
| /Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py | Added assertion for new seam-identity guidance line | Lock prompt consistency |

### Decisions Made

| Decision | Options Considered | Rationale |
|----------|-------------------|-----------|
| Fix seam parity in the runner normalization path | Prompt-only fix, final-summary-only rewrite, stage-level runtime canonicalization | Prompt-only is stochastic, final-summary-only leaves reviewer stages on unstable labels, normalization path is early enough and already owns payload cleanup |
| Canonicalize seam IDs from normalized seam paths | Keep free-text seam labels and hope prompts converge, introduce a manual registry, derive identity from path-set | Same path set should mean same seam regardless of wording; path-set derivation is deterministic and minimal |
| Keep the implementation local instead of parallel worker agents | Parallel subagents, single local implementation | The work touched one coupled path (`runner.py` + tests) and parallel workers would mostly conflict |
| Harden unrelated live failures found during rerun attempts | Ignore them and stop at offline green, patch only the seam logic | The goal was plan closure, and the live rerun exposed concrete normalizer weaknesses that blocked proof before parity checking even ran |

## Pending Work

### Immediate Next Steps

1. Fix the new bounded live proposer failure in `.forge-harness-runs/20260426T183303Z-recommend_automation_improvements-376965c6`: `recommendations[3].review_surface.must_check_files exceeds the bounded-review cap of 3 item(s).`
2. Re-run the bounded live harness command against `/Users/spensermcconnell/__Active_Code/atomize-hq/unified-agent-api` until it produces a valid `summary=` output.
3. Run the matching trust live command on the same commit/workspace and then run `scripts/check_seam_parity.py` on the fresh pair to see whether the plan is actually closed.

### Blockers/Open Questions

- [ ] Fresh live parity proof is still missing because the newest bounded rerun failed before parity checking.
- [ ] It is not yet proven whether the remaining bounded live failure is newly exposed by stronger seam guidance or was already latent in the external repo/task combination.
- [ ] The trust half of the fresh live pair was not rerun after the runtime canonicalization because the bounded half did not complete successfully.

### Deferred Items

- No additional documentation updates were made beyond prompt consistency because the branch is not yet fully closed.
- No commit was created in this session.
- No new TODOs were added; the remaining work is part of the existing closure plan, not a new follow-up.

## Context for Resuming Agent

### Important Context

The core behavioral fix from this session is already in code and tested. Do not re-litigate whether the seam checker or report layer is the problem. The live bug was that bounded and trust could inspect the same seam but persist different `seam_id` labels; that is now addressed by runner-owned canonicalization from normalized seam path sets in `anvil/harness/runner.py`. The remaining problem is different: fresh live bounded runs against the atomize workspace are failing semantic validation before a parity check can happen. There were two live failure modes observed in sequence. Older run `.forge-harness-runs/20260426T182511Z-recommend_automation_improvements-3887f3cb` failed at critic-stage semantic validation due to a leading-slash workspace path (`/.github/...`) and an `issue_closure_reviews` entry referencing a just-raised issue ID (`AR-002`) instead of a prior-open ID; those are the exact fragilities hardened in this session. The newer run `.forge-harness-runs/20260426T183303Z-recommend_automation_improvements-376965c6` failed earlier at proposer-stage semantic validation because `recommendations[3].review_surface.must_check_files` exceeded the bounded cap of 3. That newer failure is the next thing to solve if the goal is true end-to-end closure. The fresh parity report was not rerun because there was no successful fresh bounded/trust pair to compare.

### Assumptions Made

- Same normalized seam path set should imply the same canonical seam identity across bounded and trust.
- Stage-level canonicalization is preferable to final-summary-only rewriting because reviewer stages should also see stable seam IDs.
- The current external workspace used for live acceptance remains `/Users/spensermcconnell/__Active_Code/atomize-hq/unified-agent-api`.
- Local Codex/Claude CLI adapters are sufficient to run the harness even though standard `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` env vars were missing.

### Potential Gotchas

- `tests/test_harness_runner.py` now distinguishes between legacy model-authored seam labels and runtime canonical seam IDs. Some adapters still emit legacy labels intentionally so the runner can rewrite them.
- The simple base adapter uses a different primary seam path set than the corroboration adapters, so not every test should expect the same canonical seam ID.
- A “new” seam with the same normalized path set as an existing seam is no longer a real new seam under this invariant. Some older overflow-style tests had to be adjusted for that.
- Live harness failures can happen before parity checking. Do not assume a non-zero live run means the seam canonicalizer failed.
- The rerun shell pipeline is sensitive because it relies on `awk -F= '/^summary=/{print $2}'`; if the harness exits before printing `summary=`, the shell command will fail with no captured summary path.

## Environment State

### Tools/Services Used

- `poetry run pytest`
- `poetry run python -m anvil.cli harness-run`
- `poetry run python scripts/check_seam_parity.py`
- Local Codex CLI provider adapter
- Local Claude Code CLI provider adapter

### Active Processes

- No known long-running project processes were intentionally left running.
- Recent live harness run artifacts were created under `.forge-harness-runs/`.

### Environment Variables

- `OPENAI_API_KEY` was checked and not present in the shell environment used during this session
- `ANTHROPIC_API_KEY` was checked and not present in the shell environment used during this session

## Related Resources

- Closure plan: [PLAN.md](/Users/spensermcconnell/__Active_Code/forge/PLAN.md)
- Behavioral fix implementation: [anvil/harness/runner.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/runner.py)
- Prompt alignment: [anvil/harness/prompts.py](/Users/spensermcconnell/__Active_Code/forge/anvil/harness/prompts.py)
- Main regression file: [tests/test_harness_runner.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_runner.py)
- Prompt consistency regression: [tests/test_harness_prompt_consistency.py](/Users/spensermcconnell/__Active_Code/forge/tests/test_harness_prompt_consistency.py)
- Parity checker: [scripts/check_seam_parity.py](/Users/spensermcconnell/__Active_Code/forge/scripts/check_seam_parity.py)
- Last failed fresh bounded live run: [.forge-harness-runs/20260426T183303Z-recommend_automation_improvements-376965c6](/Users/spensermcconnell/__Active_Code/forge/.forge-harness-runs/20260426T183303Z-recommend_automation_improvements-376965c6)
- Earlier critic-stage live failure now partly hardened: [.forge-harness-runs/20260426T182511Z-recommend_automation_improvements-3887f3cb](/Users/spensermcconnell/__Active_Code/forge/.forge-harness-runs/20260426T182511Z-recommend_automation_improvements-3887f3cb)
- Last old failing parity report before this session: [.forge-harness-runs/20260426T155412Z-recommend_automation_improvements-c2f1ccb5-vs-20260426T155414Z-recommend_automation_improvements-38357c96.parity.json](/Users/spensermcconnell/__Active_Code/forge/.forge-harness-runs/20260426T155412Z-recommend_automation_improvements-c2f1ccb5-vs-20260426T155414Z-recommend_automation_improvements-38357c96.parity.json)

---

**Security Reminder**: Before finalizing, run `validate_handoff.py` to check for accidental secret exposure.
