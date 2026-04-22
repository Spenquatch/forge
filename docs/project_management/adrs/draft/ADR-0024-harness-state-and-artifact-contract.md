# ADR-0024 — HarnessState, Shared Channels, and Artifact Contract

## Status
- Status: Draft
- Date (UTC): 2026-04-01
- Owner(s): Forge maintainers

## Scope
- `anvil/harness/state.py`
- `anvil/harness/types.py`
- `anvil/harness/artifacts.py`
- `anvil/harness/reporting.py`
- `anvil/harness/policy.py`
- `anvil/harness/validation.py`
- `anvil/harness/selection.py`
- prompt projection helpers and structured schemas

## Context
The harness needs explicit shared state between nodes. It also needs to avoid over-sharing.

The previous imperative mini-harness used a mix of:
- task/strategy objects
- in-memory runner fields
- on-disk artifacts
- ad hoc per-stage payload passing

Moving the harness onto LangGraph should make state sharing explicit, but only if we define a clear contract for:
- what lives in graph state
- what stays private to subgraphs/nodes
- what must be written to artifacts instead of shared state

## Decision
Use a **typed `HarnessState` schema** for durable, decision-relevant run data, plus a strict artifact boundary for large/raw payloads.

### Core rules
1. Graph state must remain JSON-serializable.
2. Graph state should store small to medium structured data only.
3. Raw prompts, raw transcripts, large file contents, and verbose tool traces belong in artifacts on disk.
4. Nodes must return partial state updates; no node may mutate shared state in place and reuse it silently.
5. State channels are explicit and typed; append-only histories use reducers.
6. Strategy-local scratch state may be private to a subgraph and mapped back to parent state.

## Decision detail: use a native LangGraph state schema
Implement `HarnessState` as a `TypedDict` with `Annotated[..., reducer]` for append-only channels.

Use small record types (TypedDict or dataclass-to-dict) for complex entries.

### Required state shape

```python
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal
from typing_extensions import TypedDict


class ArtifactRef(TypedDict, total=False):
    kind: str
    path: str
    description: str


class StageRecord(TypedDict, total=False):
    stage_id: str
    role_name: str
    provider_name: str
    model: str | None
    requested_access: str
    effective_access: str
    stage_index: int
    round_index: int
    ok: bool
    verdict: str | None
    text_path: str | None
    json_path: str | None
    prompt_path: str | None
    schema_path: str | None
    duration_sec: float | None
    usage: dict[str, Any] | None
    warnings: list[str]
    error: str | None


class DraftRecord(TypedDict, total=False):
    draft_id: str
    source_stage_id: str
    role_name: str
    task_kind: str
    round_index: int
    text_path: str
    json_path: str | None
    summary: str
    review_status: Literal["candidate", "accepted", "rejected", "best"]
    scores: dict[str, float]
    issue_counts: dict[str, int]
    metadata: dict[str, Any]


class IssueRecord(TypedDict, total=False):
    issue_id: str
    source_stage_id: str
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    summary: str
    rationale: str
    evidence: list[dict[str, Any]]
    resolution_status: Literal["open", "fixed", "partial", "disagreed", "waived"]
    resolution_note: str


class ValidatorResult(TypedDict, total=False):
    name: str
    status: Literal["passed", "failed", "error", "skipped", "not_applicable"]
    required: bool
    run_when: str
    reason: str | None
    command: str
    exit_code: int | None
    log_path: str | None
    duration_sec: float | None


class ValidatorRound(TypedDict, total=False):
    round_index: int
    results: list[ValidatorResult]


class PolicyCheck(TypedDict, total=False):
    checkpoint: str
    final: bool
    ok: bool
    mode: str
    touched_files: list[str]
    violations: list[str]
    git_snapshot_path: str | None


class ReviewScores(TypedDict, total=False):
    grounding_score: float
    actionability_score: float
    scope_compliance_score: float


class HarnessState(TypedDict, total=False):
    # identity / config
    run_id: str
    thread_id: str
    task_spec: dict[str, Any]
    strategy_spec: dict[str, Any]
    task_kind: Literal["patch", "analysis_review"]
    strategy_kind: Literal["single_pass", "pfr_v1", "analysis_review_v1"]
    workspace_root: str
    out_root: str
    run_dir: str
    created_at: str

    # snapshots and deterministic checks
    initial_git_snapshot: dict[str, Any]
    initial_workspace_state: dict[str, Any] | None
    current_git_snapshot: dict[str, Any]
    current_workspace_state: dict[str, Any] | None

    # stage / draft / review histories
    stage_history: Annotated[list[StageRecord], operator.add]
    drafts: Annotated[list[DraftRecord], operator.add]
    validator_rounds: Annotated[list[ValidatorRound], operator.add]
    policy_checks: Annotated[list[PolicyCheck], operator.add]
    issue_history: Annotated[list[IssueRecord], operator.add]
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

    # current working set
    stage_counter: int
    revision_round: int
    current_draft_id: str | None
    best_draft_id: str | None
    selected_draft_id: str | None
    open_issue_ids: list[str]
    latest_review_scores: ReviewScores
    stop_reason: str | None

    # verdict axes
    content_verdict: str | None
    validator_verdict: str | None
    policy_verdict: str | None
    config_verdict: str | None
    run_verdict: str | None
    summary_text: str | None

    # artifact references
    artifact_index: dict[str, ArtifactRef]
```

## Why this schema shape
- `task_spec` and `strategy_spec` are persisted in-state so checkpoints are self-describing.
- `stage_history`, `drafts`, `validator_rounds`, `policy_checks`, and `issue_history` are append-only and reducer-friendly.
- `current_draft_id`, `best_draft_id`, `selected_draft_id`, and verdict keys are overwrite fields for the latest control decision.
- Artifact refs let nodes find on-disk data without copying large payloads into state.

## State-sharing rules

### What is shared in parent graph state
The following are global, durable channels:
- loaded task / strategy specs
- workspace snapshot and policy checks
- stage records
- draft records
- issue history and current open issue IDs
- validator rounds
- verdict axes
- artifact index

### What may be private to strategy subgraphs
Subgraphs may keep strategy-local values private and translate them in/out through wrapper nodes, for example:
- local loop counters
- private reviewer scratch structures
- transient routing hints
- per-strategy normalized working payloads

### What must stay out of graph state
Do **not** store these directly in `HarnessState` except as paths/refs:
- raw prompt text
- raw provider transcripts
- raw file contents copied from the workspace
- large structured outputs when the same data is already written to disk
- validator stdout/stderr bodies
- screenshot/image blobs

## Node prompt projection rules
Nodes must not receive the entire world by default.

Each node gets a projected view of state.

### Proposer
Input projection:
- task objective / acceptance / constraints / files_hint
- workspace policy summary
- selected file summaries or relevant repo facts
- optionally prior accepted issues if revising an existing draft

### Critic / falsifier / auditor
Input projection:
- current draft text or structured output
- relevant evidence refs
- validator/advisory results relevant to the draft
- applicable review requirements / stop criteria

### Reviser / patcher
Input projection:
- current draft
- open issues with issue IDs
- issue-resolution requirements
- validator failures relevant to the next revision

Rule: nodes get the **smallest state slice necessary**. They do not get all prior raw transcripts by default.

## Draft contract
Every stage that produces a candidate deliverable must emit a `DraftRecord`.

A draft record is the canonical unit for:
- review
- comparison
- best-draft selection
- final artifact writing

### Draft artifact rules
For each draft, write:
- markdown/text representation
- JSON structured output when available
- a short summary / metadata entry in state

### Draft IDs
Use deterministic IDs when possible:
- `draft-proposer-r0`
- `draft-reviser-r1`
- `draft-patcher-r1`

## Issue contract
All reviewer/falsifier issues must have stable IDs.

The reviser must return an **issue closure table**:
- `issue_id`
- `status`: `fixed | partial | disagreed | waived`
- `note`
- optional evidence of fix

This is required so the harness can detect regressions and incomplete fixes.

## Verdict-axis contract
The harness must keep verdict axes separate.

Required axes:
- `content_verdict`
- `validator_verdict`
- `policy_verdict`
- `config_verdict`
- `run_verdict`

Recommended values:

```text
content_verdict:
  accepted
  accepted_with_warnings
  needs_revision
  best_effort_exhausted
  rejected

validator_verdict:
  pass
  failed
  misconfigured
  not_applicable

policy_verdict:
  pass
  policy_violation

config_verdict:
  pass
  invalid_config

run_verdict:
  accepted
  accepted_with_warnings
  needs_revision
  best_effort_exhausted
  rejected
  invalid_config
  policy_violation
```

## Final artifact contract

Write:
- `REPORT.md`
- `summary.json`
- `FINAL_ANSWER.md` / `FINAL_ANSWER.json` only when the selected primary deliverable is a publishable final answer
- `PARTIAL_ANSWER.md` / `PARTIAL_ANSWER.json` when the run has a publishable accepted subset
- `BEST_DRAFT.md` / `BEST_DRAFT.json` when neither a final nor partial deliverable may ship

Rules:
- `summary.json["artifacts"]["final_artifact"]`, `final_artifact_json`, and `final_artifact_kind` are the source of truth for what actually shipped.
- In trust mode, `accepted_with_warnings` does not guarantee `FINAL_ANSWER.*`.
- `analysis_review_status.publishability.final_answer_publishable` and `blocking_causes` decide whether `FINAL_ANSWER.*` may ship for trust-mode runs.
- When trust final publication is blocked, artifact selection falls through to `PARTIAL_ANSWER.*` when eligible, otherwise `BEST_DRAFT.*`.
- Markdown deliverables that are not the publishable final answer must carry a prominent banner explaining the artifact status.

## Best-draft selection contract
Before writing the final deliverable, the harness must run a dedicated best-draft selector.

Selection order:
1. prefer drafts with no remaining medium+ issues
2. then prefer accepted drafts over non-accepted drafts
3. then prefer higher grounding score
4. then prefer higher actionability score
5. then prefer higher scope-compliance score
6. then prefer the most recent draft only as a tie-breaker

The selector must not assume “latest draft == best draft”.

## Workspace policy contract
The task-level `workspace_write_policy` remains authoritative.

State must persist:
- initial snapshot
- after-stage policy checks
- final policy check
- touched file list
- violation reasons

Required behavior:
- policy checks run after every stage that could have caused workspace changes
- final policy check always runs
- policy violations override content success

## Validator contract
Validator results must be persisted per round.

Validator applicability fields to support:
- `run_when`
- `requires_paths`
- `required_binaries`
- `on_missing_surface`
- `on_missing_binary`

For analysis tasks, validators that do not apply must produce `not_applicable`, not a misleading failure.

## Serialization rules
- Everything in `HarnessState` must be JSON-serializable.
- Use dataclasses or pydantic internally if helpful, but convert to plain dicts before writing to state.
- Artifact paths in state must be absolute or run-dir-relative; choose one convention and keep it consistent.

## Validation plan
- unit tests for reducers / serialization / draft selection
- policy violation tests
- validator applicability tests
- artifact naming tests for publishable final vs partial vs best-draft outcomes
- issue-closure table tests in analysis-review loops

## Acceptance criteria
- `HarnessState` is explicit, typed, and reducer-aware.
- Large/raw payloads are written to disk and referenced from state instead of copied into state.
- Drafts, issues, validators, and policy checks are all first-class state channels.
- The harness can select the best draft independently of stage order.
