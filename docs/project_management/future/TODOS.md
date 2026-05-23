# TODOs

## Optional Backlog: Post-Iteration Ideas

These are intentionally **not** the first implementation slice for the current branch. They came out of the 2026-04-20 next-iteration planning pass and should stay visible so they do not disappear into conversation history.

### Product and architecture follow-ups

- After the request-gate milestone lands, evaluate whether the measured wrong-route, latency, and token deltas justify widening into a generalized intent-intake layer instead of continuing to polish analysis-review-local routing.
- Defer full M2 compatibility shim retirement until after the request-gate branch proves user-visible value, then decide whether to remove `run_m2_focus_gate_live_acceptance.py`, rename fixture namespaces, and collapse docs onto the canonical focus-gate surface.
- Explore whether bounded and trust should diverge earlier in generation strategy, not just in validation/verdict posture, so the two modes feel operationally distinct.
- Revisit whether the current single unified runner is still the right long-term shape after the topic-ledger and review-evidence work lands.
- Validate that bounded vs trust is a product distinction users actually feel, not just an internal contract distinction with cleaner caveat language.
- After the next planning-runtime packet lands, decide whether the long-term public execution contract should stay inside `planning_v1` as explicit execution modes or graduate into a broader cross-family graph execution taxonomy.
- Once planning provider semantics are made truthful, add a second bounded reusable topology proof so the repo can demonstrate graph-surface reuse beyond analysis-review plus one special planning lane.

### Prompt and contract cleanup

- Consider a richer trust contract for line-level review refs once path-level refs are stable and low-noise.
- Decide whether late medium-or-higher auditor findings in trust mode should produce more hard failures or fewer caveated accepts before tightening the default policy.

### Auditability and provenance depth

- Investigate authoritative read tracing or sandbox-backed reviewer proof as a later project if payload-hash plus normalized refs still feels too weak.
- Consider a separate audit artifact for review-surface evidence summaries if `summary.json` and `REPORT.md` become too crowded.
- Add cross-run comparison tooling for bounded vs trust replay deltas so changes in honesty posture are visible without hand-reading artifacts.
- Revisit whether scoped closure proof should eventually match recommendation-evidence strength instead of staying review-attested metadata.
- Consider deprecating `accepted_recommendation_count` once downstream consumers fully migrate to `analysis_review_status.recommendation_admissibility` as the canonical published-subset truth.
- Add a saved-run consistency checker that compares `summary.json`, `REPORT.md`, and emitted artifact payloads for canonical recommendation-index parity before a replay is accepted.

### Reporting and UX polish

- Add a compact topic-lifecycle summary block to final deliverables if the full topic ledger becomes too verbose for `FINAL_ANSWER.md`.
- Consider a clearer distinction between user-facing caveats and internal semantic-validation notes in rendered markdown.
- Add report-side grouping for downgrade causes so provenance, topic carry-forward, and acceptance caveats are easier to scan.
