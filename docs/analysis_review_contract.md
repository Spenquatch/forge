# Analysis-review contract

The analysis-review harness is driven by a typed contract in `anvil/harness/contracts.py`.

## Why this exists

The contract keeps the proposer, critic, reviser, auditor, runner stop logic, and reporting aligned. Without a shared contract, prompt text and runtime behavior drift into contradictory expectations.

`analysis_review_v1_contract_v10` keeps the seam-selection contract from v9, widens the typed focus-gate family to allow exactly one public focus type (`seam` or `artifact`), and freezes the runner-owned downstream seam bridge that later analysis stages must consume.

## What the contract governs

The current contract covers:

- effective strategy surface: `strategy_kind` plus explicit `mode`
- focus-gate policy and rerun-answer matching
- stop policy and loop limits
- partial-acceptance policy
- required analysis sections
- bounded-review policy
- trust-review policy
- issue-ledger requirements
- recommendation-level review requirements
- the shared confidence rubric
- the issue taxonomy and default blocking classes

The contract now serializes:

```json
{
  "contract_version": "analysis_review_v1_contract_v10",
  "strategy_kind": "analysis_review_v1",
  "mode": "bounded",
  "effective_strategy": {
    "kind": "analysis_review_v1",
    "mode": "bounded"
  }
}
```

Today the legacy `analysis_review_v1` surface still resolves to bounded behavior. When explicit public strategy kinds land, `analysis_review_bounded_v1` and `analysis_review_trust_v1` should serialize through the same contract with different `mode` and `trust_review` values.

## Unified policy model

The v10 contract keeps one analysis-review contract type and adds one `TrustReviewPolicy`.

Why this is preferable to mode-specific contract classes:

- one source of truth for prompts and validation
- bounded and trust stay comparable
- mode-specific behavior lives in policy fields instead of branching the whole type system

The trust policy covers:

- whether blocking-class overrides require a reason
- whether `verified_evidence_refs` must stay a subset of recommendation evidence
- whether non-inferred `affected_files` require evidence or checked-file coverage
- whether payload provenance binding is expected
- whether clean acceptance should be downgraded on semantic warnings
- whether inference-backed acceptance should be downgraded to a caveated acceptance
- whether late auditor medium-or-higher issues are treated as errors or warnings

For M3A, the public trust strategy kind remains `analysis_review_trust_v1`. The only cutover knob is the optional `trust_review` block on `StrategyConfig`, and that block allows exactly one key:

```yaml
trust_review:
  execution_mode: legacy_full_review | attestation_over_bounded
```

`trust_review.execution_mode` semantics are frozen as:

- `legacy_full_review`: today's trust lane. The trust run executes the existing end-to-end trust review flow.
- `attestation_over_bounded`: trust attestation over the frozen bounded draft handed off through runner-owned `bounded_attestation_input`.

M3A does not change publication ownership. Publication semantics remain runner-owned and unchanged, including `analysis_review_status.publishability`, `analysis_review_status.recommendation_admissibility`, and final artifact selection.

Example policy for M3A:

- canonical `analysis_review_trust_*.yaml` filenames are attestation-first and opt into `trust_review.execution_mode: attestation_over_bounded`
- explicit `analysis_review_trust_legacy_*.yaml` filenames are compatibility-only and pin `trust_review.execution_mode: legacy_full_review`
- additive `analysis_review_trust_attestation_*.yaml` filenames may remain as mirrors of the attestation lane, but they are not the canonical operator-facing entrypoints

## `bounded_attestation_input` handoff

`bounded_attestation_input` is runner-owned. It is not a public deliverable.

This M1 payload exists to freeze the future trust-attestation review object emitted from a finalized bounded run. It intentionally excludes final publication truth such as `analysis_review_status`, `publishability`, `recommendation_admissibility`, and `final_answer_publishable`.

Milestone timing is explicit: M1 emits `bounded_attestation_input`, M2 consumes it. `analysis_review_schema()` remains unchanged in M1, and the handoff uses its own `bounded_attestation_input_schema()` helper.

## Focus-gate contract

The contract version is now `analysis_review_v1_contract_v10`. Focus gating remains part of the shared analysis-review contract family, but v10 changes the typed public surface enough that the version bump is mandatory.

The effective contract now also resolves a typed `focus_gate` policy:

```yaml
focus_gate:
  enabled: true
  default_path: adjudicate
  allowed_focus_types: [seam]
  clarification_policy: block_for_clarification
```

Precedence and validation rules:

- runner default: `enabled = false`
- strategy-level `focus_gate` may set only `enabled` and `default_path`
- task-level `focus_gate` may set `enabled`, `allowed_focus_types`, and `clarification_policy`
- the resolved canonical surface lives at `analysis_review_contract.focus_gate`
- v10 rejects unknown task or strategy `focus_gate` keys
- `allowed_focus_types` remains a list in the public task shape, but v10 accepts exactly one value
- the only allowed singleton values are `["seam"]` and `["artifact"]`
- mixed-type lists such as `["seam", "artifact"]` are rejected explicitly

Rerun-answer rules:

- `task.focus_gate_answer` is optional and is meaningful only when `focus_gate.enabled = true`
- rerun answers are deliberate-only: a run whose resolved `focus_gate.default_path` is `adjudicate` must not consume `task.focus_gate_answer`
- deliberate runs always execute the internal `focus_gate_probe` stage before the public `focus_gate` decision stage
- the public decision stage uses split prompt builders: `build_focus_gate_adjudicate_prompt(...)` for direct adjudication and `build_focus_gate_deliberate_prompt(...)` for probe-backed shortlist / rerun handling
- `focus_gate_answer.question_prompt` must equal the canonical deliberate clarification prompt after trimming leading and trailing whitespace
- `focus_gate_answer.selected_option` is matched against the current live probe shortlist after trimming; the runner does not persist a prior clarification snapshot as the source of truth
- `focus_gate_answer.freeform_answer` is optional supporting text and is never the primary matcher
- when the canonical prompt matches and the selected option is still valid, the gate stays on the deliberate path and evaluates that answer against the live repo-backed shortlist instead of skipping the probe
- if the selected option disappears from the live shortlist, or the live shortlist now makes a different candidate clearly dominant, the answer is stale
- when a stale answer is detected and `clarification_policy = never_ask`, the runner must normalize the public result to `decision_state = no_viable_focus` with an added stale-answer warning instead of emitting a fresh question
- when the canonical prompt does not match or the selected option is no longer valid and `clarification_policy != never_ask`, the runner may re-ask once and then terminate again as `blocked_for_clarification`
- the canonical clarification prompt text is generic, not seam-specific: `Which focus should this run prioritize?`

## Focus-decision artifact

`focus_decision` is runner-owned state. It is not a model-authored review-status field and must not be buried under `analysis_review_status`.

Persist it at top-level `summary.json["focus_decision"]` with this v10 shape:

```json
{
  "gate_path": "adjudicate | deliberate",
  "focus_type": "seam | artifact",
  "decision_state": "selected | clarification_requested | no_viable_focus",
  "decision_basis": "request_only | repo_probe | rerun_answer",
  "selected_focus_id": "string|null",
  "selected_focus_summary": "string|null",
  "selected_focus_paths": [],
  "confidence": 0.0,
  "confidence_band": "high | medium | low",
  "files_hint_disposition": "helped | hurt | ignored | absent",
  "checked_files": [],
  "candidates": [],
  "question": {
    "prompt": "string",
    "options": ["string"]
  },
  "warnings": [],
  "adapter_plan": {
    "primary_focus_id": "string|null",
    "secondary_focus_ids": [],
    "downstream_primary_seam_id": "string|null",
    "downstream_primary_seam_paths": [],
    "adaptation_basis": "selected_focus_paths | artifact_singleton | null"
  }
}
```

Artifact rules:

- `decision_state` is always `selected`, `clarification_requested`, or `no_viable_focus`
- `decision_basis` is always `request_only`, `repo_probe`, or `rerun_answer`
- `selected_focus_id` and `selected_focus_summary` are required for `selected` and must be `null` otherwise
- `selected_focus_paths` is required for `selected`, must be empty otherwise, and is compared using normalized workspace-path equality rather than raw string equality
- for `focus_type = seam`, seam identity is path-set identity: after normalization, two path sets that compare equal describe the same seam, and `selected_focus_id` must stay aligned with the canonical seam ID derived from that normalized path set
- for `focus_type = artifact`, `selected_focus_paths` must normalize to exactly one workspace path, each `candidates[*].candidate_paths` must normalize to exactly one workspace path, and `selected_focus_id` must stay aligned with the canonical artifact focus ID derived from that singleton path
- `decision_basis=request_only` requires `gate_path=adjudicate` and `checked_files=[]`
- `decision_basis=repo_probe` and `decision_basis=rerun_answer` require `gate_path=deliberate` and non-empty `checked_files`
- `files_hint_disposition` is always one of `helped`, `hurt`, `ignored`, or `absent`
- `question.prompt` and `question.options` are required for `clarification_requested`; otherwise `question` serializes as `{ "prompt": "", "options": [] }`
- for `clarification_requested`, `question.prompt` is frozen to `Which focus should this run prioritize?`
- `candidates` may be empty only for `no_viable_focus`
- every `candidates[*]` item carries `candidate_paths`, `why_candidate`, `evidence_refs`, and `score`; when `selected`, the chosen candidate's normalized `candidate_paths` must equal `selected_focus_paths`
- model-authored candidate shortlists must not include multiple entries whose normalized `candidate_paths` collapse to the same canonical focus identity for the active `focus_type`
- runner normalization collapses duplicate canonical candidate groups before semantic validation, then caps the final normalized `candidates` list at 3 total items
- `adapter_plan.primary_focus_id` must equal `selected_focus_id` for `selected` and must be `null` otherwise
- `adapter_plan.secondary_focus_ids` is the shortlisted remainder and must stay a subset of candidate IDs
- `adapter_plan.downstream_primary_seam_id` and `adapter_plan.downstream_primary_seam_paths` are the runner-owned authoritative seam bridge for downstream proposer / reviser validation
- for `focus_type = seam`, `adapter_plan.downstream_primary_seam_id = selected_focus_id`, `adapter_plan.downstream_primary_seam_paths = selected_focus_paths`, and `adapter_plan.adaptation_basis = selected_focus_paths`
- for `focus_type = artifact`, `adapter_plan.downstream_primary_seam_id = canonical_seam_id_for_paths(selected_focus_paths)`, `adapter_plan.downstream_primary_seam_paths = selected_focus_paths`, and `adapter_plan.adaptation_basis = artifact_singleton`
- for `decision_state != selected`, `adapter_plan.downstream_primary_seam_id = null`, `adapter_plan.downstream_primary_seam_paths = []`, and `adapter_plan.adaptation_basis = null`
- hard rule: for artifact runs, `selected_focus_*` is not downstream seam truth; downstream seam truth comes only from `adapter_plan.downstream_primary_seam_*`
- blocked runs may omit `analysis_review_status`, but they still persist `focus_decision`, emit `summary.json`, and emit `REPORT.md`
- deliberate runs persist three focus-stage artifacts with exact filenames: `structured_output.raw.json`, `structured_output.normalized.json`, and `run.envelope.json`
- `run.envelope.json["structured_output"]` is the canonical persisted stage snapshot after runner normalization; `structured_output.raw.json` captures the provider-emitted JSON before normalization, and `structured_output.normalized.json` captures the post-normalization public artifact payload
- `REPORT.md` renders `focus_decision` in its own runner-owned `## Focus Decision` section before review-status/runtime-detail sections

Terminal focus-gate outcomes:

- `selected` continues into proposer and later review stages
- `clarification_requested` terminates the run as `run_verdict = blocked_for_clarification`, `content_verdict = blocked_for_clarification`, `validator_verdict = not_run`, and `final_summary = "Focus gate blocked the run pending clarification."`
- `no_viable_focus` terminates the run as `run_verdict = no_viable_focus`, `content_verdict = no_viable_focus`, `validator_verdict = not_run`, and `final_summary = "Focus gate could not identify a viable focus target."`
- for blocked outcomes, `failure_details.stage` is `focus_gate` and carries the runner-owned `question`, `candidates`, and `warnings` payload needed for rerun or diagnosis
- `no_viable_focus` must not fabricate a clarification block; when `question` is empty, reports should explain the block as no-viable / never-ask behavior rather than rendering fake prompt text

Prompt handoff rule:

- v10 still hands the selected focus into proposer and reviser by prompt text only
- the prompt block must include `selected_focus_id`, `selected_focus_summary`, `selected_focus_paths`, and the shortlisted candidate IDs
- for artifact runs, downstream prompts must treat `adapter_plan.downstream_primary_seam_*` as the authoritative seam bridge rather than assuming `selected_focus_*` is already seam truth
- v10 does not add a new provider-protocol field for focus-gate context

Probe-stage behavior:

- `focus_gate_probe` is runner-owned repo inspection, not the public decision artifact
- the probe emits a shortlist artifact with `checked_files`, `candidates`, and `files_hint_disposition`
- the later public `focus_gate` stage consumes that probe artifact, plus any rerun answer, and emits the persisted `focus_decision`
- only the public `focus_gate` stage is copied into `summary.json["focus_decision"]`; the probe remains visible through stage artifacts and metadata

## Topic lifecycle artifact contract

Slice A topic lifecycle is exported through the run summary, not inferred ad hoc from stage-local payloads.

`summary.json["topic_ledger"]` is the canonical machine-readable contract and each entry uses this shape:

```json
{
  "topic_id": "TOPIC-001",
  "title": "Recommendation 1 needs a concrete fallback classification.",
  "severity": "medium",
  "evidence": "The draft names the operator path but not the fallback state taxonomy.",
  "recommendation_index": 1,
  "introduced_by": "critic",
  "introduced_in_stage_index": 2,
  "resolution_status": "addressed",
  "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
  "resolved_in_stage_index": 4
}
```

Rules:

- `introduced_by` is the role that first raised the topic.
- `introduced_in_stage_index` is the concrete stage index where the topic entered the ledger.
- `resolution_status` uses the Slice A vocabulary: `open | addressed | carried_forward | waived | disagree`.
- `resolved_in_stage_index` is nullable and is only set when the topic reaches a non-open terminal classification such as `addressed`, `waived`, or `disagree`.

`analysis_review_status` keeps the existing ID lists for compatibility, but they derive from the canonical ledger:

- `open_topic_ids` = topics whose ledger status is `open`
- `carried_forward_topic_ids` = topics whose ledger status is `carried_forward`
- `resolved_topic_ids` = topics whose ledger status is `addressed`
- `waived_topic_ids` = topics whose ledger status is `waived`
- `disagreed_topic_ids` = topics whose ledger status is `disagree`

For `accepted_partial`, the shipped subset must also be topic-clean:

- a recommendation can only remain in the partial artifact when its linked topics are terminal (`addressed`, `waived`, or `disagree`)
- a topic left `open` or `carried_forward` removes its `recommendation_index` from the partial subset
- an unresolved topic without a usable `recommendation_index` blocks partial acceptance entirely, because no clean subset can be proven

`REPORT.md` renders the same ledger in a row-shaped `## Topic Lifecycle` table, while `FINAL_ANSWER.md` keeps a compact bullet summary of the same canonical records.

## Recommendation withholding and artifact selection

Slice D adds a runner-owned recommendation withholding ledger under `analysis_review_status.recommendation_admissibility`:

```json
{
  "analysis_review_status": {
    "recommendation_admissibility": {
      "final_answer_recommendation_indices": [1],
      "partial_only_recommendation_indices": [2],
      "excluded_recommendation_indices": [3],
      "reasons_by_recommendation_index": {
        "2": ["accepted_with_caveat"],
        "3": ["not_accepted"]
      }
    }
  }
}
```

Rules:

- `final_answer_recommendation_indices`, `partial_only_recommendation_indices`, `excluded_recommendation_indices`, and `reasons_by_recommendation_index` are the frozen field names.
- `recommendation_admissibility` is runner-owned status, not a model-authored payload field. The payload shape remains unchanged.
- `recommendation_admissibility` is canonical in both bounded mode and trust mode, and both modes share the same status object shape.
- `final_answer_recommendation_indices` is the runner-owned canonical published-final subset in both modes.
- In bounded mode, accepted recommendations, including `accept_with_caveat`, stay in `final_answer_recommendation_indices` unless they are topic-blocked.
- In bounded mode, `partial_only_recommendation_indices` stays empty.
- In trust mode, `FINAL_ANSWER.*` is all-or-nothing. Recommendations outside `final_answer_recommendation_indices` are withheld from `FINAL_ANSWER.*`.
- A recommendation stays in `final_answer_recommendation_indices` only when its review verdict is `accept`, its grounding is not `inferred`, and no runner-known per-index topic blocker applies.
- `accepted_with_caveat` and accepted recommendations with `grounding_mode = inferred` move to `partial_only_recommendation_indices`; they are withheld from `FINAL_ANSWER.*` in trust mode.
- Trust admissibility remains recommendation-level, so independently actionable direct or spec-backed guidance should be split from weaker inferred or optional hardening before review.
- Reserve `grounding_mode = mixed` for genuinely inseparable single-action recommendations, not bundles that could be split cleanly.
- Avoidable mixed-grounding bundles are an authoring and review defect, not a runner-state feature.
- Non-accepted recommendations and per-index topic-blocked recommendations move to `excluded_recommendation_indices`.
- `reasons_by_recommendation_index` uses only the canonical reasons `accepted_with_caveat`, `inferred_grounding`, `not_accepted`, and `topic_blocked`.
- The candidate partial subset comes from `final_answer_recommendation_indices + partial_only_recommendation_indices`, but publishing `PARTIAL_ANSWER.*` still reuses the existing partial gates.
- Global topic blockers, provenance gating, and minimum-threshold fallout remain whole-artifact promotion rules. This withholding ledger does not replace them.
- When that scoped partial fallback is rendered, freeze the partial-answer scope lines to `Recommendation indices included in PARTIAL_ANSWER.*: 1, 2`, `Recommendation indices withheld from FINAL_ANSWER.*: 2`, and `Recommendation indices excluded from PARTIAL_ANSWER.*: none`.

Slice C also keeps an explicit publishability layer under `analysis_review_status`:

```json
{
  "analysis_review_status": {
    "content_verdict": "accepted_partial",
    "publishability": {
      "final_answer_publishable": false,
      "blocking_causes": [
        "content verdict is not fully accepted: accepted_partial"
      ]
    }
  }
}
```

Rules:

- `final_answer_publishable` and `blocking_causes` are the frozen field names.
- `analysis_review_status.publishability` is the canonical final publication outcome.
- In trust mode, `accepted_with_warnings` does not guarantee `FINAL_ANSWER.*`.
- Trust-mode final publication is allowed only when the content verdict is `accepted` or `accepted_with_warnings`, provenance is fully bound, no topic IDs remain `open`, no topic IDs remain `carried_forward`, and no final semantic warnings remain.
- Only the exact warning strings `strengths contains both concrete items and none_reason; prefer one or the other.` and `uncertainties contains both concrete items and none_reason; prefer one or the other.` are advisory carveouts. They remain visible warnings, but by themselves they do not add a publishability blocker.
- If the content verdict is not fully accepted, `blocking_causes` must contain exactly one verdict blocker: `content verdict is not fully accepted: <verdict>`.
- `summary.json["artifacts"]["final_artifact"]`, `final_artifact_json`, and `final_artifact_kind` remain the source of truth for what actually shipped.
- Artifact projection finalizes `publishability`; `final_answer_publishable` is `true` exactly when `summary.json["artifacts"]["final_artifact_kind"] == "final_answer"`.
- If trust mode is content-accepted but not final-publishable, artifact selection skips `FINAL_ANSWER.*` and falls through to the existing partial-answer path when eligible, otherwise `BEST_DRAFT.*`.
- Reports and fallback deliverables freeze their wording to `Final publication: publishable|blocked`, `Publication blockers:`, and `Recommendation indices withheld from FINAL_ANSWER.*:`.
- Partial-answer scope lines are frozen only for `PARTIAL_ANSWER.*`: `Recommendation indices included in PARTIAL_ANSWER.*: 1, 2`, `Recommendation indices withheld from FINAL_ANSWER.*: 2`, and `Recommendation indices excluded from PARTIAL_ANSWER.*: none`.
- `REPORT.md` freezes only final-publication / final-withholding wording and does not render `Recommendation indices included in PARTIAL_ANSWER.*` or `Recommendation indices excluded from PARTIAL_ANSWER.*`.
- Topic lifecycle summaries keep `Open topics:` and `Carried-forward topics:` as separate labels; carried-forward items are not folded into open wording.
- Reviewer or model-authored prose may describe quality, caveats, or evidence gaps, but only runner-owned `analysis_review_status.publishability`, `analysis_review_status.recommendation_admissibility`, and `summary.json["artifacts"]` decide artifact eligibility and publication state.

For fully accepted trust runs, `blocking_causes` is deterministic. The list is emitted in this order:

1. provenance blocker first, when present
2. open topic IDs in sorted order
3. carried-forward topic IDs in sorted order
4. one semantic-warning blocker whose summaries preserve `_final_semantic_warning_records()` order and are joined with `; `

This separation is intentional: `content_verdict` classifies the review outcome, `recommendation_admissibility` records which indices remain publishable in `FINAL_ANSWER.*` versus withheld to fallback subsets, and `publishability` is finalized after artifact projection to record whether `FINAL_ANSWER.*` actually ships.

## Bounded-review policy

The bounded-review policy remains the single source of truth for review caps. Prompts must render these values from the contract, and semantic validation must enforce the same values.

Current defaults:

- bounded-mode recommendation evidence refs: `1..3`
- `review_surface.must_check_files`: `1..3`
- `review_surface.optional_check_files`: `0..2`
- evidence cap policy: `trim_to_cap` by default, with task-level `strict` override support
- critic issue cap: `5`
- critic new-topic cap: `2`
- auditor new medium-or-higher issue cap after round 0: `1`
- scope escapes require non-empty reasons

Shared repo-local discovery applies to both bounded mode and trust mode:

- `files_hint` is a starting slice, not a hard boundary on repo-local inspection
- requirement or spec claims should cite the nearest governing repo-local doc or manifest when one exists
- parity or symmetry claims should cite the sibling implementation or workflow that establishes the baseline when one exists
- corroborating files should land in `files_reviewed`, `evidence`, and `review_surface`

Bounded differs by caps and scope discipline:

- bounded mode is discovery-bounded, not workflow-file-only
- bounded mode may inspect one-hop repo-local corroboration outside `files_hint`
- corroboration must still stay inside the current caps: evidence max `3`, `review_surface.must_check_files` max `3`, `review_surface.optional_check_files` max `2`

Trust differs by provenance completeness, evidence completeness, atomicity, and publication:

- trust-mode recommendation evidence is intentionally uncapped; trust runs should preserve every concrete workspace ref needed to support auditability and should not trim or reject a recommendation solely for carrying more than three evidence refs
- when both exist, prefer nearer governing/spec/workflow evidence over farther plan/runbook prose
- trust mode remains stricter because of provenance and publication rules, not because bounded mode is expected to tolerate repo-local discovery blind spots

Markdown compaction is renderer-owned and preview-only:

- deliverable markdown previews at most the first `3` recommendation evidence refs
- `REPORT.md` previews at most the first `2` `checked_files` values and the first `2` `verified_evidence_refs` values in review-provenance cells
- omitted items render as deterministic `(+N more)` previews
- JSON artifacts, including the selected deliverable JSON and `summary.json`, remain full fidelity and must not gain parallel `display_*` or `audit_*` field families

## Seam-selection contract

The seam-selection contract is additive to the shared payload family and does not introduce review-schema changes.

Analysis/proposer/reviser payload fields are frozen to:

- `primary_seam`
- `secondary_seams_considered`
- `scope_escapes`
- `recommendations[*].seam_id`
- `recommendations[*].seam_expansion_reason`

Canonical status fields are frozen to:

- `analysis_review_status.primary_seam`
- `analysis_review_status.secondary_seams_considered`
- `analysis_review_status.scope_escapes`
- `analysis_review_status.recommendation_seam_bindings`

Canonical `analysis_review_status.recommendation_seam_bindings[*]` objects are frozen to:

- `recommendation_index`
- `seam_id`
- `seam_expansion_reason`

Seam-selection rules:

- `primary_seam` remains the canonical run-context seam.
- `secondary_seams_considered` records only seams actually declared or inspected beyond the primary seam.
- analysis/proposer/reviser payloads now include `scope_escapes`.
- `recommendations[*].seam_id` binds each recommendation to its seam, and `recommendations[*].seam_expansion_reason` explains why that recommendation expands beyond the primary seam when it does.
- in bounded analysis outputs, `scope_escapes` may justify exactly one third secondary seam and nothing beyond that.
- review-stage `scope_escapes` semantics remain separate: critic/auditor still use them for later review-surface escapes rather than analysis-stage seam declaration.
- default bounded cap is 2; declaring or inspecting a third secondary seam requires a recorded scope_escape; overflow beyond that third seam is never silently normalized away.

Role-specific seam-review duties are separate from the shared seam-selection rules and do not apply to proposer.

Critic seam-review duties:

- In the critic stage, challenge seam choice before recommendation polish.
- In the critic stage, when a recommendation relies on farther plan/runbook prose while a nearer governing spec/manifest or sibling workflow exists, raise the seam defect before polishing wording.
- In the critic stage, in bounded mode, flag secondary-seam exploration that silently widened review beyond bounded discipline, even if the recommendation text looks reasonable.
- In the critic stage, use `kind=scope_drift` for wrong seam selection, unjustified off-primary expansion, and bounded widening abuse.
- In the critic stage, use `kind=missing_evidence` only when corroboration is actually absent.

Auditor seam-review duties:

- In the auditor stage, do not return clean acceptance while the wrong seam remains primary.
- In the auditor stage, do not accept off-primary recommendations without justified seam expansion.
- In the auditor stage, do not return clean acceptance when seam metadata was used to bypass bounded corroboration limits.
- In the auditor stage, use `kind=scope_drift` for wrong seam selection, unjustified off-primary expansion, and bounded widening abuse.
- In the auditor stage, use `kind=missing_evidence` only when corroboration is actually absent.

Reviser seam-review duties:

- In the reviser stage, return to the higher-ranked seam first.
- In the reviser stage, when an open issue shows the current seam choice is wrong, update `primary_seam`, `secondary_seams_considered`, `recommendations[*].seam_id`, `recommendations[*].seam_expansion_reason`, `review_surface`, and evidence together.
- In the reviser stage, preserve recommendation order where possible while rebinding to the higher-ranked seam.
- In the reviser stage, collapse gratuitous secondary seams after rebinding instead of carrying stale seam declarations forward.
- In the reviser stage, keep at least one recommendation bound to `primary_seam` after rebinding.

Projection-only retained-primary status is frozen to:

- `primary_seam_projection_status: "retained_without_included_recommendations"`

When projection retains the canonical primary seam even though no included recommendation binds to it, the retained-primary note sentence is frozen exactly to:

`Canonical primary seam retained for run context; no included recommendation in this artifact binds to it.`

## Shared payload family

Do not split bounded and trust mode into separate JSON payload families.

Use one additive recommendation payload shape:

```json
{
  "classification": "confirmed_issue",
  "priority": "high",
  "title": "Tighten prompt-surface contract wording",
  "rationale": "The prompts duplicate trust assumptions instead of deriving them from the contract.",
  "evidence": [
    "anvil/harness/prompts.py",
    "anvil/harness/contracts.py"
  ],
  "verified_evidence_refs": [
    "anvil/harness/prompts.py"
  ],
  "checked_files": [
    "anvil/harness/prompts.py"
  ],
  "affected_files": [
    "anvil/harness/prompts.py",
    "anvil/harness/schemas.py"
  ],
  "grounding_mode": "direct",
  "proposed_change": "Render trust behavior from the contract blocks instead of duplicating it in each role prompt.",
  "confidence": 0.93,
  "review_surface": {
    "must_check_files": [
      "anvil/harness/prompts.py"
    ],
    "optional_check_files": [
      "anvil/harness/schemas.py"
    ],
    "scope_note": "Validate prompt/schema alignment only."
  }
}
```

Bounded mode and trust mode share that shape. The difference is policy:

- bounded mode populates the shared admissibility fields without using trust-only `partial_only` downgrades
- trust mode populates the same shape and is expected to enforce stricter downstream semantics

Critic and auditor issue payloads stay on the same shared family and add `blocking_class_override_reason` when they intentionally override the default blocking class implied by issue kind:

```json
{
  "issue_id": "AR-003",
  "severity": "medium",
  "kind": "confidence_calibration",
  "blocking_class": "actionability",
  "blocking_class_override_reason": "The confidence overstatement changes whether the recommendation is safe to act on.",
  "title": "Recommendation confidence overstates observed evidence",
  "evidence": "The recommendation cites only one file but claims a repo-wide invariant.",
  "repair_hint": "Downgrade confidence or narrow the claim."
}
```

Review-stage critic and auditor payloads also support structured review refs on the shared family:

- required top-level `files_reviewed`
- `recommendation_reviews[*].checked_files`
- `recommendation_reviews[*].verified_evidence_refs`
- required top-level `issue_closure_reviews`
- required top-level `topic_closure_reviews`

Those refs are the path-based audit surface for review provenance. `files_reviewed` records review-stage context, not proof by itself. The contract now has two closure-proof paths:

- `recommendation_reviews[*]` prove recommendation-linked closures for issues or topics whose `recommendation_index` points at the reviewed recommendation
- `issue_closure_reviews[*]` and `topic_closure_reviews[*]` prove global closures when the closed issue or topic has `recommendation_index = null`

Additional rules:

- one scoped closure review maps to exactly one ID: one `issue_closure_reviews[*]` entry per `issue_id`, one `topic_closure_reviews[*]` entry per `topic_id`
- unrelated recommendation review refs do not satisfy global issue/topic closure proof
- recommendation-linked closures do not need extra scoped proof when their recommendation is already covered by the matching `recommendation_reviews[*]` entry
- human-readable issue/topic `evidence` text remains narrative; closure proof binds to the structured path refs above
- `issue_closure_reviews` and `topic_closure_reviews` are required top-level arrays but may be empty when no `recommendation_index = null` closures are being proven

## Trust semantics

Trust mode is stricter, but it is still the same harness path.

What trust mode adds conceptually:

- provenance-aware evidence accounting
- explicit direct vs mixed vs inferred grounding via `grounding_mode`
- clearer distinction between files checked and files claimed to be affected
- justification when issue taxonomy is intentionally overridden
- cleaner caveat semantics for accepted recommendations

What trust mode does **not** add in this contract alone:

- hard read sandboxing
- a second subgraph
- a second runner implementation

## Trust execution modes

M3A introduces attestation-first canonical trust entrypoints without changing the public trust strategy kind. `analysis_review_trust_v1` remains the public trust surface for both lanes.

`trust_review.execution_mode` is the only M3A mode switch:

- at the raw config level, omitting `trust_review` still resolves to `legacy_full_review`
- set `execution_mode: attestation_over_bounded` to run trust attestation against the frozen bounded draft
- canonical operator-facing `analysis_review_trust_*.yaml` examples do not rely on that implicit legacy default anymore
- explicit `analysis_review_trust_legacy_*.yaml` examples are the compatibility-only way to stay on `legacy_full_review`

Attestation mode uses the bounded draft handoff already described in this contract:

- the bounded run freezes the draft into runner-owned `bounded_attestation_input`
- the trust lane consumes that frozen bounded draft rather than regenerating it
- publication semantics still stay runner-owned and unchanged in M2

This split is intentionally narrow:

- `analysis_review_trust_v1` stays public and unchanged
- `trust_review.execution_mode` is the only allowed M3A cutover knob
- canonical `analysis_review_trust_*.yaml` filenames are attestation-first
- explicit `analysis_review_trust_legacy_*.yaml` filenames are compatibility-only
- additive `analysis_review_trust_attestation_*.yaml` filenames remain mirrors, not the canonical entrypoints

## Semantic validation expectations

JSON schema validation is necessary but not sufficient. The harness runs semantic validation after structured output is produced.

Examples of the existing and intended v4 semantic checks:

- proposer/reviser outputs must satisfy the task minimum recommendation count
- in bounded mode, recommendation evidence counts must stay within the bounded-review cap
- in trust mode, recommendation evidence counts are uncapped, but every evidence ref must still remain concrete, normalized, in-workspace, and included in `files_reviewed`
- recommendation evidence refs must exist in the workspace snapshot
- recommendation evidence refs must remain a subset of `files_reviewed`
- line-qualified refs such as `path:12-18` should canonicalize to workspace paths before semantic validation
- in bounded mode, oversize evidence lists may be trimmed to cap before semantic validation when the task uses `evidence_cap_policy=trim_to_cap`
- `review_surface.must_check_files` must stay within cap and remain a subset of `files_reviewed`
- `review_surface.optional_check_files` must stay within cap
- critics must stay within the issue cap and new-topic cap
- revisers must return an `issue_resolution_map` entry for every open issue ID
- auditors must explicitly classify every prior open issue as resolved, carried forward, or waived
- new medium-or-higher auditor issues after round 0 must include `why_not_raised_earlier`
- every `scope_escapes[].reason` must be non-empty
- in bounded analysis outputs, `secondary_seams_considered[3].paths` must be fully covered by `scope_escapes[*].path`, and extraneous overflow escape paths are invalid
- in trust mode, `verified_evidence_refs` should stay a subset of `evidence`
- in trust mode, non-inferred `affected_files` should be covered by evidence or checked files
- in trust mode, `blocking_class_override_reason` should explain intentional taxonomy overrides
- in trust mode, `files_reviewed` is review context only; closure proof must bind to `recommendation_reviews[*]` for recommendation-linked closures or to `issue_closure_reviews[*]` / `topic_closure_reviews[*]` for `recommendation_index = null` closures
- in trust mode, each scoped closure review must bind exactly one ID, and unrelated recommendation refs do not satisfy global closure proof

Semantic validation failures are surfaced as stage errors and written to a per-stage `semantic_validation.json` artifact.

## Prompt and contract change policy

Contract changes should be reviewed in code review, not approved manually at run time.

When changing the contract:

1. update `anvil/harness/contracts.py`
2. update any affected prompts in `anvil/harness/prompts.py`
3. update runtime enforcement in `anvil/harness/runner.py` or `anvil/harness/semantic_validation.py`
4. update schemas in `anvil/harness/schemas.py` if the payload shape changed
5. update tests and prompt-consistency checks in the same PR
6. update example strategies or docs when defaults or recommended settings change

The contract is the source of truth. Prompts, runner logic, schema expectations, semantic validation, and reporting should derive from it instead of duplicating trust and bounded-review rules in parallel.
