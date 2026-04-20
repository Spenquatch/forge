# TODOs

## Optional Backlog: Post-Iteration Ideas

These are intentionally **not** the first implementation slice for the current branch. They came out of the 2026-04-20 next-iteration planning pass and should stay visible so they do not disappear into conversation history.

### Product and architecture follow-ups

- Evaluate reshaping trust mode into an attestation layer over bounded output, where bounded produces `BEST_DRAFT` and trust re-audits that draft instead of running as a separate proposer flow from scratch.
- Explore whether bounded and trust should diverge earlier in generation strategy, not just in validation/verdict posture, so the two modes feel operationally distinct.
- Revisit whether the current single unified runner is still the right long-term shape after the topic-ledger and review-evidence work lands.

### Prompt and contract cleanup

- Remove trust-only boilerplate from bounded prompts when every trust flag is effectively false, so bounded mode carries less no-op cognitive overhead.
- Consider a richer trust contract for line-level review refs once path-level refs are stable and low-noise.
- Review whether high-priority mixed-grounding recommendations should always require explicit caveat language, even when they are not inference-only.

### Auditability and provenance depth

- Investigate authoritative read tracing or sandbox-backed reviewer proof as a later project if payload-hash plus normalized refs still feels too weak.
- Consider a separate audit artifact for review-surface evidence summaries if `summary.json` and `REPORT.md` become too crowded.
- Add cross-run comparison tooling for bounded vs trust replay deltas so changes in honesty posture are visible without hand-reading artifacts.

### Reporting and UX polish

- Add a compact topic-lifecycle summary block to final deliverables if the full topic ledger becomes too verbose for `FINAL_ANSWER.md`.
- Consider a clearer distinction between user-facing caveats and internal semantic-validation notes in rendered markdown.
- Add report-side grouping for downgrade causes so provenance, topic carry-forward, and acceptance caveats are easier to scan.
