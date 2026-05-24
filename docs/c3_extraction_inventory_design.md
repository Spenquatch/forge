# C3 Extraction Inventory Design

This document defines the concrete shape of the extraction inventory that will
drive the `C3` rebuild from current `analysis_review_v1` and `planning_v1`
reality toward a truthful, reusable, bounded graph system.

It is intentionally an extraction-and-proof design, not an attempt to
implement the full rebuilt system in one packet.

## Purpose

The inventory must be complete in coverage, while staying narrow in immediate
implementation scope.

That means:

- extract every materially real execution surface from the current families
- classify what each thing actually is and who owns it
- record exact evidence for its existence and behavior
- define what can be promoted, what must remain family-private, and what needs
  proof before promotion
- rebuild only tiny verified slices at first

The inventory is not just documentation. It is the source of truth for:

- extraction completeness
- rebuild work queues
- proof gating
- compatibility/migration decisions
- public-vs-internal boundary discipline

## Design Rules

The inventory must obey these rules:

- Extract first, classify second, prove third, promote last.
- Completeness is required for extraction coverage, not for initial
  implementation breadth.
- No row may be promoted by vibes. Promotion requires evidence and proof.
- Graph topology is not allowed to hide inside prose strings.
- Failure behavior is part of graph behavior and must be inventoried.
- Observability is a first-class rebuild surface, not a post-hoc concern.
- Family-private scratch state must not accidentally become public graph
  semantics.
- Public DSL candidates must only come from proven shared internal primitives.

## Inventory Package

The inventory should live as a small package with three coordinated surfaces:

1. Human-readable design and catalog documentation:
   [`docs/c3_extraction_inventory_design.md`](/home/azureuser/__Active_Code/forge/docs/c3_extraction_inventory_design.md)
2. Machine-readable extraction registry:
   `anvil/harness/inventory/c3_inventory.yaml`
3. Tiny executable proof fixtures:
   `tests/fixtures/harness/c3_microstrategies/`

This separation preserves:

- human readability
- machine indexability
- executable proofability

## Extraction Invariants

The inventory must be able to answer the following questions for every item
without code spelunking:

- What is it?
- Where does it exist today?
- Who owns it today?
- What does it read?
- What does it write?
- What does it emit?
- What can fail?
- What happens when it fails?
- Is it deterministic?
- Does it call a model, provider, tool, bridge, or filesystem?
- What depends on it?
- What does it depend on?
- What proof demonstrates it?
- What is its target disposition?
- What compatibility aliases or shims are needed?
- Is it public DSL, shared internal, family-private, artifact-only, or
  deprecated?

If a proposed row shape cannot answer those questions, it is not sufficient for
the rebuild.

### Extraction Invariant: First-Class Graph Behavior

Inventory rows must not be node-centric. Nodes are only one kind of graph
primitive.

Edges, gates, loops, state mutations/transforms, terminal outcomes, retries,
failure routes, artifact writes, and trace emissions must each be inventoryable
as first-class items when they carry independent behavior.

Do not bury rebuild-critical behavior inside prose notes or string-only
`incoming` / `outgoing` fields. If a behavior affects execution order,
branching, state shape, artifacts, failure handling, observability, or
promotion safety, it must get its own inventory row or an explicit referenced
catalog item.

## Top-Level Catalogs

The inventory should be organized into the following top-level catalogs.

### 1. Family Map

Purpose: top-level understanding of current runtime ownership and routing.

Includes:

- parent builder routing
- runtime families
- graph-owned versus bridge behavior
- family entrypoints
- post-runtime routing ownership
- family-to-contract relationships

### 2. Graph Topology Catalog

Purpose: explicit inventory of graph membership and topology.

Includes:

- graph and subgraph definitions
- entrypoints
- node membership
- edge membership
- loop membership
- branch membership
- terminal outcome membership

This catalog exists so topology does not collapse into opaque strings on node
rows.

### 3. Node Catalog

Purpose: inventory every execution node as a first-class executable unit.

Includes:

- execution nodes
- validators
- routers
- hydrators
- adapter entrypoints
- artifact writers
- model-backed stages

Each node row must record what kind of node it actually is, not just that it
is “a node.”

### 4. Edge / Transition Catalog

Purpose: treat transitions as first-class rebuild surfaces.

Includes:

- linear edges
- conditional edges
- default edges
- branch-priority routing
- fallthrough behavior
- data mapping references
- alternate/failure routing

This is required because a rebuild cannot be driven from `incoming` / `outgoing`
strings alone.

### 5. Condition / Gate / Loop Catalog

Purpose: inventory control-flow predicates and bounded repetition semantics as
independent behavior.

Includes:

- branch conditions
- gate predicates
- terminal conditions
- loop continuation conditions
- loop exit conditions
- validation predicates
- permission/policy predicates
- loop membership and bounds

This prevents fake genericity where a “branch” might actually be a pure
predicate, a config lookup, an LLM judgment, or a bridge escape hatch.

### 6. State Surface Catalog

Purpose: fully specify runtime and artifact-facing state.

Includes:

- state fields
- runtime-owned state
- family-private scratch keys
- frozen artifact state
- carry-through fields
- bridge-only fields

Every state row must capture ownership, scope, schema, lifecycle, visibility,
and migration aliases.

### 7. State Transform Catalog

Purpose: represent how values move and change between nodes.

Includes:

- copy
- merge
- normalize
- append
- reduce
- hydrate
- freeze
- redact

Graph execution is not just node-to-node; it is output contract to state
projection to next-node input.

### 8. Execution Binding Catalog

Purpose: inventory config/provider/model/runtime binding surfaces.

Includes:

- role declarations
- role-family bindings
- provider-family selection
- model resolution
- adapter entrypoints
- config precedence
- execution-mode knobs
- runtime contract resolution

This is the correct place to capture `config`, `provider`, and `model`
dependencies without pretending they are graph primitives.

### 9. Artifact & Persistence Catalog

Purpose: inventory what gets written, read, persisted, and retained.

Includes:

- `PLAN.md`
- `plan.json`
- `summary.json`
- stage outputs
- per-iteration outputs
- validator outputs
- append versus overwrite behavior
- retention and lifecycle

### 10. Contract / Schema / Compatibility Catalog

Purpose: inventory parser-owned, runtime-owned, and compatibility-governed
surfaces.

Includes:

- typed strategy fields
- raw YAML carry-through
- resolved runtime contracts
- compatibility aliases
- schema references
- public/internal classification
- behavior-version and migration semantics

### 11. Failure / Recovery / Terminal Catalog

Purpose: treat failure routing as part of the executable graph.

Includes:

- failure modes
- retry policies
- fallback routing
- degraded behavior
- terminal success outcomes
- terminal failure outcomes
- user-visible and machine-visible error surfaces

Behavioral equivalence is not real if only the happy path matches.

### 12. Trace / Observability Catalog

Purpose: make the rebuild inspectable and provable.

Includes:

- run started/completed/failed
- node started/completed/failed
- edge selected
- branch/gate evaluated
- loop iteration started/completed
- model call started/completed/failed
- artifact written
- validation/proof result emitted

This catalog should capture CLI, trace, JSONL, and artifact visibility.

### 13. Promotion & Proof Catalog

Purpose: convert extraction into a disciplined work queue.

Includes:

- disposition
- promotion target
- prerequisites
- proof fixture
- proof assertions
- proof status
- dependency order
- behavior delta expectations

No item should become public DSL or shared internal reusable infrastructure
without passing through this catalog.

## Inventory-Level Schema

The machine-readable inventory should have a top-level shape like:

```yaml
inventory:
  schema_version: c3_inventory.v1
  source_project: forge
  extracted_at: 2026-05-24
  extraction_status: in_progress

families:
  - analysis_review_v1
  - planning_v1

allowed_kinds:
  - graph
  - node
  - edge
  - condition
  - gate
  - loop
  - state_field
  - state_transform
  - execution_binding
  - artifact
  - artifact_write
  - contract
  - terminal_outcome
  - failure_behavior
  - trace_event
  - proof

items:
  - id: node.analysis_review.proposer
  - id: edge.analysis_review.proposer_to_critic
  - id: state.analysis_review.current_analysis_payload

indexes:
  by_family: {}
  build_queue: {}
  proof_queue: []
```

The inventory file should also include deterministic indexes such as:

- `by_family`
- `by_kind`
- `by_disposition`
- `build_queue`
- `proof_queue`
- `public_candidates`
- `compatibility_shims`

These indexes allow the registry to drive scripts, reviews, and promotion
checks.

## Canonical Row Shape

Every item row should share one base schema, with kind-specific required
fields layered on top.

```yaml
schema_version: c3_inventory_item.v1

identity:
  id: node.analysis_review.proposer
  label: proposer
  kind: node
  family: analysis_review_v1
  status: extracted
  confidence: high

current_source:
  files:
    - path: anvil/harness/subgraphs/analysis_review_v1.py
      symbols:
        - _graph_owned_proposer
      evidence_type: code
    - path: anvil/harness/analysis_review_runtime.py
      symbols:
        - runtime_snapshot
      evidence_type: code
  tests:
    - path: tests/test_harness_analysis_review_graph.py
      evidence_type: behavioral_test
  artifacts: []
  owner: family_runtime

semantics:
  summary: "Produces the initial analysis payload before critic review."
  phase_or_stage_type: proposer
  invariants:
    - "Must produce payload before critic executes."
  preconditions:
    - state.task_spec.exists
    - state.strategy_spec.exists
  postconditions:
    - state.__analysis_review_latest_analysis_payload.exists

execution_profile:
  node_type: llm_call
  deterministic: false
  idempotent: false
  side_effects:
    - model_call
    - runtime_state_write
  external_dependencies:
    - provider.openai
  timeout_ms: null
  cancellation_safe: unknown

state_io:
  reads:
    - state.task_spec
    - state.strategy_spec
    - state.focus_decision
  writes:
    - state.__analysis_review_latest_analysis_payload
    - state.analysis_review_runtime.current_analysis_payload
  transforms:
    - transform.analysis_review.proposer_payload_to_runtime

execution_binding:
  role_name: proposer
  role_family: execute
  provider_surface: runner_resolved
  model_surface: runner_resolved
  config_inputs:
    - roles.proposer
    - config/models.yaml
    - resolved_analysis_review_contract
  resolution_owner: HarnessRunner

graph_shape:
  graph_id: graph.analysis_review_v1
  incoming_edge_ids:
    - edge.analysis_review.focus_gate_selected_to_proposer
  outgoing_edge_ids:
    - edge.analysis_review.proposer_to_critic
  loop_ids:
    - loop.analysis_review.revision_loop

artifacts:
  emits: []
  writes: []
  reads: []

failure_behavior:
  can_fail: true
  failure_modes:
    - model_call_failed
    - invalid_output_schema
  retry_policy:
    retryable: true
    max_attempts: inherited_from_runner
  fallback_terminal: terminal.analysis_review.proposer_failed

observability:
  emits_events:
    - event.node.started
    - event.node.completed
    - event.node.failed
  trace_payload_fields:
    - node_id
    - role_name
    - model
    - attempt

policy:
  trust_boundary: model_provider
  user_content_exposure: prompt
  requires_secret: true
  secret_sources:
    - provider_api_key

publicness:
  current: internal
  target: shared_internal
  public_candidate: false

promotion:
  disposition: shared_internal_primitive
  target_form: reusable_node
  prerequisite_ids:
    - role_binding.proposer_execute
    - state.analysis_review_runtime
    - schema.analysis_review.analysis_payload
  proof_strategy: proof.micro_linear_analysis_v1
  proof_status: unproved
  behavior_delta:
    expected: none

versioning:
  introduced_in: c3_inventory_v1
  source_behavior_version: analysis_review_v1
  target_contract_version: graph_contract_v0
  backward_compatible: true
  compatibility_aliases: []
  migration_required: false
  breaking_change_risk: low

extraction:
  extracted_by: manual_review
  confidence: high
  open_questions: []
  verified_against_runtime: false

notes:
  - "Currently executed through imperative family flow, not generic compiled graph."
```

The key rule is that references must point to IDs, not prose strings. Nodes
must reference edge IDs. State IO must reference state IDs. Transforms must
reference transform IDs. Artifacts must reference artifact IDs.

That makes the inventory a real registry instead of a prose-adjacent list.

## Kind-Specific Required Fields

One base schema is acceptable, but each kind still needs required fields.

### `node`

Required:

- `execution_profile`
- `state_io.reads`
- `state_io.writes`
- `graph_shape.incoming_edge_ids`
- `graph_shape.outgoing_edge_ids`
- `failure_behavior`
- `observability`
- `promotion`

### `edge`

Required:

- `from`
- `to`
- `transition_type`
- `condition_ref`
- `data_mapping_ref`
- `failure_behavior`
- `promotion`

Example:

```yaml
id: edge.analysis_review.focus_gate_selected_to_proposer
kind: edge
family: analysis_review_v1

from:
  node_id: node.analysis_review.focus_gate
  port: selected

to:
  node_id: node.analysis_review.proposer
  port: input

semantics:
  summary: "Routes selected focus decision into proposer execution."
  transition_type: conditional
  condition_ref: condition.analysis_review.focus_selected
  data_mapping_ref: mapping.analysis_review.focus_to_proposer_input

control_flow:
  priority: 10
  exclusive_with:
    - edge.analysis_review.focus_gate_skipped_to_terminal
  default_edge: false
  fallthrough_behavior: error

failure_behavior:
  on_condition_error: terminal_failure
  on_missing_target: compile_error
  retryable: false
```

### `condition`

Required:

- `inputs`
- `output_type`
- `true_means`
- `false_means`
- `deterministic`
- `side_effect_free`
- `failure_behavior`

### `loop`

Required:

- `members`
- `entry_edge`
- `continue_condition`
- `exit_condition`
- `max_iterations_source`
- `failure_behavior`

Example:

```yaml
id: loop.analysis_review.revision_loop
kind: loop
family: analysis_review_v1

members:
  - node.analysis_review.critic
  - node.analysis_review.reviser

entry_edge: edge.analysis_review.proposer_to_critic
continue_condition: condition.analysis_review.revision_required
exit_condition: condition.analysis_review.no_revision_required
max_iterations_source: resolved_analysis_review_contract.max_revisions

state:
  iteration_counter: state.analysis_review.revision_count
  per_iteration_artifacts:
    - artifact.analysis_review.review_iteration_json

failure_behavior:
  on_max_iterations: terminal.analysis_review.max_revisions_reached
  on_invalid_loop_state: terminal.analysis_review.runtime_error
```

### `state_field`

Required:

- `path`
- `scope`
- `owner`
- `schema`
- `lifecycle.created_by`
- `lifecycle.read_by`
- `visibility`
- `safety`
- `migration`

### `state_transform`

Required:

- `inputs`
- `outputs`
- `transform.type`
- `transform.deterministic`
- `transform.lossy`
- `side_effects`

### `artifact`

Required:

- `path_pattern`
- `writer_ids`
- `reader_ids`
- `schema_ref`
- `format`
- `lifecycle`
- `retention`
- `machine_readable`
- `human_readable`

### `execution_binding`

Required:

- `role_name`
- `role_family`
- `provider_resolution`
- `model_resolution`
- `config_precedence`
- `adapter_entrypoint`
- `runtime_contract_refs`
- `failure_behavior`

### `terminal_outcome`

Required:

- `classification`
- `requires_state`
- `emits`
- `payload_schema`
- `user_visible`
- `machine_readable`

### `proof`

Required:

- `proves`
- `fixture.path`
- `assertions`
- `required_before_promotion`

## Provenance Requirements

`current_source.files` is necessary but not sufficient.

Every extracted row should record precise evidence anchors where possible:

- file path
- symbol name
- behavioral test
- observed output artifact
- extraction confidence
- whether it has been verified against a runtime execution

This protects the inventory from “inventory by vibes.”

## Failure and Recovery Requirements

Failure behavior must be treated as a top-level concern across rows, not hidden
inside notes.

Minimum expectation for executable rows:

```yaml
failure_behavior:
  can_fail: true
  failure_modes:
    - model_timeout
    - invalid_output_schema
    - missing_required_state
    - artifact_write_failed
  retry_policy:
    retryable: true
    max_attempts: 2
    backoff: fixed
  fallback:
    type: terminal_outcome
    target_id: terminal.analysis_review.model_failure
  error_surface:
    state_keys:
      - run_status.error
    artifacts:
      - summary.json
  user_visible: true
```

Happy-path equivalence is not enough. In graph systems, failure routing is part
of the graph contract.

## Observability Requirements

The inventory must explicitly model trace events, not only persisted artifacts.

At minimum, the rebuild should be able to inventory:

- graph/run started
- graph/run completed
- graph/run failed
- node started/completed/failed
- edge selected
- branch/gate evaluated
- loop iteration started/completed
- model call started/completed/failed
- artifact written
- validation/proof result emitted

These event rows should capture:

- payload schema
- CLI visibility
- trace visibility
- artifact visibility
- promotion target

## Versioning and Compatibility Requirements

Compatibility needs to be explicit, not implied.

Every promoted or contract-governed row should include:

- `introduced_in`
- `source_behavior_version`
- `target_contract_version`
- `backward_compatible`
- `compatibility_aliases`
- `migration_required`
- `breaking_change_risk`

This allows the rebuild to distinguish:

- direct extraction
- normalization
- compatibility shim
- intentional behavior change
- deprecated behavior
- public DSL candidate

## Promotion and Proof Rules

The inventory is also the promotion gate.

Do not promote anything unless it has:

```yaml
promotion:
  disposition: shared_internal_primitive
  prerequisite_ids: []
  proof_strategy: proof.micro_linear_analysis_v1
  proof_status: passed
  behavior_delta:
    expected: none
```

If `behavior_delta.expected` is `unknown`, the item must not become public DSL.
It may only remain family-private or experimental shared internal.

## Proof Fixture Rows

Proof fixtures should be registry items too.

Example:

```yaml
id: proof.micro_linear_analysis_v1
kind: proof
status: planned

proves:
  - node.analysis_review.proposer
  - edge.analysis_review.proposer_to_critic
  - node.analysis_review.critic

fixture:
  path: tests/fixtures/harness/c3_microstrategies/micro_linear_analysis_v1.yaml

assertions:
  - "proposer executes before critic"
  - "critic receives proposer payload"
  - "terminal payload includes summary"
  - "trace includes node.started/node.completed for both nodes"

required_before_promotion:
  - shared_internal_primitive
```

This lets promotion become mechanically gated by proof.

## First Tiny Build Slice

The first executable rebuild slice should stay intentionally small.

It should prove:

- one reusable node
- one reusable linear transition
- one reusable terminal success outcome
- one reusable terminal failure outcome
- one minimal provider/model binding path
- one minimal state contract
- one trace event envelope

This is enough to prove:

- the system can run
- the system can fail honestly
- the system can be observed

without pretending that the full family rebuild is already done.

## Recommended Markdown Outline

The human-readable inventory document that follows this design should use this
outline:

1. Purpose, rules, and extraction invariants
2. Current family map
3. Graph topology overview
4. Node catalog
5. Edge / transition catalog
6. Condition / gate / loop catalog
7. State surface catalog
8. State transform catalog
9. Execution binding catalog
10. Artifact and persistence catalog
11. Contract, schema, and compatibility catalog
12. Failure, retry, and terminal outcome catalog
13. Trace and observability catalog
14. Promotion matrix
15. Proof plan and fixture index
16. Open questions, deferred items, and known behavior gaps

This is slightly heavier than the earlier 8-catalog version, but it maps
directly onto rebuild work queues and avoids overloading rows with unrelated
concerns.

## Non-Negotiable Constraint

Do not promote anything into the public DSL merely because it is visible,
documented, or emitted today.

The only safe path is:

1. extract it completely
2. classify it truthfully
3. prove it behaviorally
4. promote it only if the proof passes and the behavior delta is understood

That is the discipline required to turn the current bounded built-ins into a
real bounded graph system without faking the abstraction.
