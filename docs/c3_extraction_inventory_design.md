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

### Extraction Invariant: All Behavior-Affecting References Must Resolve

Every behavior-affecting reference used by a row must itself either be:

- a real inventory item, or
- a real generated/static catalog entry that is linted for integrity

No dangling conceptual references such as `data_mapping.*`, `schema.*`,
`provider.*`, `role_binding.*`, or `trace_event.*` should appear unless those
kind names exist and the reference is validated.

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
- port membership
- edge membership
- loop membership
- branch membership
- terminal outcome membership

This catalog exists so topology does not collapse into opaque strings on node
rows.

### 2a. Port / Interface Catalog

Purpose: make node boundaries typed and compilable.

Includes:

- input ports
- output ports
- interface contracts
- port cardinality
- stream/batch semantics
- compatibility aliases

Edges connect ports, not just nodes. Without first-class ports, topology can be
 inventoried but not safely validated or compiled.

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
- route groups
- data mapping references
- alternate/failure routing

This is required because a rebuild cannot be driven from `incoming` / `outgoing`
strings alone.

### 4a. Data Mapping Catalog

Purpose: represent output-to-input projection separately from state mutation.

Includes:

- edge-level payload projection
- schema adaptation
- mixed input assembly from ports and state
- lossless/lossy mapping behavior
- mapping failure behavior

Use `state_transform` for runtime state mutation and `data_mapping` for
edge/output-to-input projection.

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

### 8a. Prompt / Model I/O Catalog

Purpose: inventory the behavior-shaping surfaces for model-backed nodes.

Includes:

- prompt surfaces
- model I/O contracts
- output parsers
- repair strategies
- redaction rules
- response-schema validation

If prompts and parsers are not inventoried, the registry can prove that a node
ran, but not that it ran the same behavior.

### 8b. Capability / Tool / Bridge Catalog

Purpose: inventory boundary-crossing capabilities as first-class surfaces.

Includes:

- provider calls
- tool calls
- bridge calls
- filesystem access
- network access
- secret references

These are more than execution-binding details. They are trust-boundary and
runtime-capability crossings.

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

### 12a. Scheduler / Run Semantics Catalog

Purpose: inventory how the graph actually runs, not just what is connected.

Includes:

- scheduler policies
- run policies
- cancellation policies
- checkpoint policies
- fork/join/barrier behavior
- state/artifact commit boundaries
- retry scope

Even for a mostly serial first slice, runtime scheduling semantics need to be
truthfully recorded.

### 12b. Validation / Lint / Invariant Catalog

Purpose: make the registry mechanically enforceable.

Includes:

- validation rules
- static lint rules
- runtime invariants
- migration validation
- promotion validation

Validators exist at multiple layers and should not be smuggled into unrelated
row kinds.

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

### 13a. Equivalence / Golden Catalog

Purpose: define what “behaviorally equivalent” means for promotion.

Includes:

- equivalence rules
- behavior delta records
- golden traces
- golden artifacts

This distinguishes “the proof passed once” from “we know exactly what passing
means and what may differ.”

### 13b. Extraction Coverage Catalog

Purpose: prove extraction completeness rather than assuming it.

Includes:

- extraction scopes
- extraction gaps
- orphan surfaces
- code symbols without rows
- rows without source evidence

Completeness needs first-class tracking, not only aspiration.

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
  - subgraph
  - node
  - port
  - interface_contract
  - edge
  - route_group
  - condition
  - gate
  - loop
  - fork
  - join
  - scheduler_policy
  - run_policy
  - cancellation_policy
  - checkpoint_policy
  - state_field
  - state_transform
  - data_mapping
  - execution_binding
  - role_binding
  - provider
  - model_binding
  - prompt_surface
  - model_io_contract
  - output_parser
  - repair_strategy
  - capability
  - tool_call
  - bridge_call
  - filesystem_access
  - network_access
  - secret_ref
  - artifact
  - artifact_write
  - persistence_policy
  - retention_policy
  - contract
  - schema
  - validation_rule
  - static_lint_rule
  - invariant
  - compatibility_shim
  - terminal_outcome
  - failure_behavior
  - failure_mode
  - retry_policy
  - trace_event
  - trace_policy
  - proof
  - equivalence_rule
  - behavior_delta
  - golden_trace
  - golden_artifact
  - extraction_scope
  - extraction_gap
  - orphan_surface

id_namespaces:
  graph:
    kind: graph
  subgraph:
    kind: subgraph
  node:
    kind: node
  port:
    kind: port
  edge:
    kind: edge
  interface_contract:
    kind: interface_contract
  route_group:
    kind: route_group
  condition:
    kind: condition
  gate:
    kind: gate
  loop:
    kind: loop
  fork:
    kind: fork
  join:
    kind: join
  scheduler_policy:
    kind: scheduler_policy
  run_policy:
    kind: run_policy
  cancellation_policy:
    kind: cancellation_policy
  checkpoint_policy:
    kind: checkpoint_policy
  state:
    kind: state_field
  state_transform:
    kind: state_transform
  data_mapping:
    kind: data_mapping
  execution_binding:
    kind: execution_binding
  role_binding:
    kind: role_binding
  provider:
    kind: provider
  model_binding:
    kind: model_binding
  prompt_surface:
    kind: prompt_surface
  model_io_contract:
    kind: model_io_contract
  output_parser:
    kind: output_parser
  repair_strategy:
    kind: repair_strategy
  capability:
    kind: capability
  tool_call:
    kind: tool_call
  bridge_call:
    kind: bridge_call
  filesystem_access:
    kind: filesystem_access
  network_access:
    kind: network_access
  secret_ref:
    kind: secret_ref
  artifact:
    kind: artifact
  artifact_write:
    kind: artifact_write
  persistence_policy:
    kind: persistence_policy
  retention_policy:
    kind: retention_policy
  contract:
    kind: contract
  schema:
    kind: schema
  invariant:
    kind: invariant
  static_lint_rule:
    kind: static_lint_rule
  validation_rule:
    kind: validation_rule
  compatibility_shim:
    kind: compatibility_shim
  terminal:
    kind: terminal_outcome
  failure_behavior:
    kind: failure_behavior
  failure_mode:
    kind: failure_mode
  retry_policy:
    kind: retry_policy
  trace_event:
    kind: trace_event
  trace_policy:
    kind: trace_policy
  proof:
    kind: proof
  equivalence_rule:
    kind: equivalence_rule
  behavior_delta:
    kind: behavior_delta
  golden_trace:
    kind: golden_trace
  golden_artifact:
    kind: golden_artifact
  extraction_scope:
    kind: extraction_scope
  extraction_gap:
    kind: extraction_gap
  orphan_surface:
    kind: orphan_surface

reference_sources:
  inventory_items:
    source: inventory.items
  static_catalogs:
    - id: catalog.common_schemas
      path: anvil/harness/inventory/static/schemas.yaml
      kinds:
        - schema
        - invariant
        - validation_rule
    - id: catalog.common_policies
      path: anvil/harness/inventory/static/policies.yaml
      kinds:
        - retention_policy
        - trace_policy
        - scheduler_policy
    - id: catalog.common_lint_rules
      path: anvil/harness/inventory/static/lint_rules.yaml
      kinds:
        - static_lint_rule
        - validation_rule
        - invariant
  generated_catalogs:
    - id: catalog.generated_indexes
      path: anvil/harness/inventory/generated/indexes.yaml
      generated_from: inventory.items

enums:
  classification.status:
    - extracted
    - planned
    - verified
    - deprecated
  classification.confidence:
    - low
    - medium
    - high
  classification.target_scope:
    - family_private
    - shared_internal
    - public_dsl
    - artifact_only
    - deprecated
  promotion.proof_status:
    - unproved
    - planned
    - running
    - passed
    - failed
    - waived
  promotion.disposition:
    - family_private_until_proven
    - family_private
    - shared_internal_candidate
    - shared_internal_primitive
    - public_dsl_candidate
    - public_dsl
    - artifact_only
    - deprecated
  transition.type:
    - always
    - conditional
    - default
    - failure_route

items:
  # Abbreviated for illustration; real item rows use c3_inventory_item.v1.
  - id: node.analysis_review.proposer
  - id: edge.analysis_review.proposer_to_critic
  - id: state.analysis_review.current_analysis_payload

indexes:
  generated: true
  source_of_truth: items
  must_match_items: true
  by_family: {}
  by_kind: {}
  by_disposition: {}
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

Indexes should be generated from `items`, not hand-maintained as primary
source-of-truth data.

## Canonical Row Shape

Every item row should share one common core, with optional facets layered on
top by kind. This keeps rows strict without making every row null-heavy.

```yaml
schema_version: c3_inventory_item.v1

identity:
  id: node.analysis_review.proposer
  label: proposer
  kind: node
  source_families:
    - analysis_review_v1

classification:
  status: extracted
  confidence: high
  target_scope: shared_internal
  publicness:
    current: internal
    target: shared_internal
    public_candidate: false

evidence:
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
  observed_runs: []
  artifacts: []
  owner: family_runtime
  verified_against_runtime: false

semantics:
  summary: "Produces the initial analysis payload before critic review."
  phase_or_stage_type: proposer
  invariant_refs:
    - invariant.analysis_review.proposer_before_critic
  preconditions:
    - invariant.common.task_spec_exists
    - invariant.common.strategy_spec_exists
  postconditions:
    - invariant.analysis_review.latest_payload_exists
  semantic_notes:
    - "Must produce payload before critic executes."

relationships:
  generated_from_refs: true
  declared:
    equivalent_to: []
    supersedes: []
    superseded_by: []

# generated.relationships is emitted into generated/indexes.yaml or another
# compiler-owned output, not hand-authored source data.

resource_profile:
  timeout_ms: null
  token_budget:
    input_max: null
    output_max: null
  cost_class: model_call
  memory_class: small
  artifact_size_limit_bytes: null
  max_retries: inherited_from_runner

security:
  sensitivity:
    input: user_content
    output: internal_analysis
    artifacts: internal
  secret_access:
    required: true
    refs:
      - secret_ref.openai_api_key
  redaction_required:
    - trace_payload
  data_retention:
    policy_ref: retention_policy.internal_default

compile_behavior:
  required_at_compile_time: true
  compile_checks:
    - static_lint_rule.c3.all_references_resolve
    - static_lint_rule.c3.no_model_node_without_prompt_surface
  on_compile_failure: compile_error

facets:
  executable:
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
    capability_refs:
      - capability.analysis_review.model_call.openai

  graph_member:
    graph_id: graph.analysis_review_v1
    input_port_ids:
      - port.analysis_review.proposer.input
    output_port_ids:
      - port.analysis_review.proposer.output
    incoming_edge_ids:
      - edge.analysis_review.focus_gate_selected_to_proposer
    outgoing_edge_ids:
      - edge.analysis_review.proposer_to_critic
    loop_ids:
      - loop.analysis_review.revision_loop

  state_io:
    reads:
      - state.task_spec
      - state.strategy_spec
      - state.focus_decision
    writes:
      - state.__analysis_review_latest_analysis_payload
      - state.analysis_review_runtime.current_analysis_payload
    transforms:
      - state_transform.analysis_review.proposer_payload_to_runtime

  llm_behavior:
    execution_binding_ref: execution_binding.analysis_review.proposer_execute
    prompt_surface_ref: prompt_surface.analysis_review.proposer.v1
    model_io_contract_ref: model_io_contract.analysis_review.analysis_payload
    output_parser_ref: output_parser.analysis_review.analysis_payload
    validation_refs:
      - validation_rule.analysis_review.proposer_output_schema

  artifacts:
    emits: []
    writes: []
    reads: []

  observability:
    emits_events:
      - trace_event.node.started
      - trace_event.node.completed
      - trace_event.node.failed
    trace_payload_fields:
      - run_id
      - graph_id
      - node_id
      - role_name
      - model
      - attempt

  failure:
    failure_behavior_ref: failure_behavior.analysis_review.proposer

  promotion:
    disposition: shared_internal_primitive
    target_form: reusable_node
    prerequisite_ids:
      - role_binding.analysis_review.proposer_execute
      - state.analysis_review_runtime
      - schema.analysis_review.analysis_payload
    proof_strategy: proof.micro_linear_analysis_v1
    equivalence_rule_ref: equivalence_rule.analysis_review.proposer_to_reusable_node
    behavior_delta_ref: behavior_delta.analysis_review.proposer_to_reusable_node
    proof_status: unproved
    behavior_delta_summary:
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
  coverage_ref: extraction_scope.analysis_review_v1

notes:
  - "Currently executed through imperative family flow, not generic compiled graph."
```

The key rule is that references must point to IDs, not prose strings. Nodes
must reference edge IDs. State IO must reference state IDs. Transforms must
reference transform IDs. Artifacts must reference artifact IDs. All `*_ref`,
`*_refs`, and `*_ids` fields should be checked by static lint rules.

That makes the inventory a real registry instead of a prose-adjacent list.

## Kind-Specific Required Fields

One base schema is acceptable, but each kind still needs required fields.

Minimum default requirements for kinds that do not yet have richer schemas:

- `identity.id`
- `identity.kind`
- `identity.source_families`
- `classification.status`
- `evidence`
- `semantics.summary`

### `node`

Required:

- `facets.executable.execution_profile`
- `facets.graph_member.input_port_ids`
- `facets.graph_member.output_port_ids`
- `facets.graph_member.incoming_edge_ids`
- `facets.graph_member.outgoing_edge_ids`
- `facets.state_io.reads`
- `facets.state_io.writes`
- `facets.failure.failure_behavior_ref`
- `facets.observability`
- `facets.promotion`

Additional required fields for `llm_call` nodes:

- `facets.llm_behavior.prompt_surface_ref`
- `facets.llm_behavior.model_io_contract_ref`
- `facets.llm_behavior.output_parser_ref`
- `facets.llm_behavior.validation_refs`
- `facets.executable.capability_refs`

### `graph`

Required:

- `entrypoints`
- `terminal_outcomes`
- `members.nodes`
- `members.ports`
- `members.edges`
- `members.conditions`
- `members.route_groups`
- `members.loops`
- `members.terminal_outcomes`
- `scheduler_policy_ref`
- `trace_policy_ref`
- `compile_validation_refs`

### `port`

Required:

- `owner.node_id`
- `direction`
- `contract.schema_ref`
- `contract.required`
- `contract.cardinality`

Additional required fields for input ports:

- `input_semantics.accepts`
- `state_projection`

Additional required fields for output ports:

- `output_semantics.emits`
- `payload_source`

### `edge`

Required:

- `from`
- `to`
- `transition.type`
- `transition.data_mapping_ref`
- `failure_behavior_ref`
- `promotion`

Additional required fields for conditional edges:

- `transition.condition_ref`
- `control_flow.route_group_id`
- `control_flow.priority`
- `control_flow.exclusive_with`
- `control_flow.default_edge`
- `control_flow.fallthrough_behavior`

Example:

```yaml
identity:
  id: edge.analysis_review.focus_gate_selected_to_proposer
  label: focus_gate_selected_to_proposer
  kind: edge
  source_families:
    - analysis_review_v1

from:
  port_id: port.analysis_review.focus_gate.selected

to:
  port_id: port.analysis_review.proposer.input

transition:
  type: conditional
  condition_ref: condition.analysis_review.focus_selected
  data_mapping_ref: data_mapping.analysis_review.focus_to_proposer_input

control_flow:
  route_group_id: route_group.analysis_review.focus_gate_exit
  priority: 10
  exclusive_with:
    - edge.analysis_review.focus_gate_skipped_to_terminal
  default_edge: false
  fallthrough_behavior: error

failure_behavior_ref: failure_behavior.analysis_review.focus_gate_selected_to_proposer

promotion:
  disposition: family_private_until_proven
  proof_status: unproved
```

### `condition`

Required:

- `inputs`
- `output_domain`
- `true_means`
- `false_means`
- `deterministic`
- `side_effect_free`
- `failure_behavior_ref`

Conditions should support error-aware domains such as `true`, `false`,
`unknown`, and `error`, rather than silently coercing uncertainty to `false`.

### `loop`

Required:

- `members`
- `entry_edge`
- `continue_condition`
- `exit_condition`
- `bounds.max_iterations_source`
- `bounds.counter_initial_value`
- `bounds.max_iterations_inclusive`
- `bounds.evaluate_continue_before_first_iteration`
- `bounds.evaluate_exit_after_each_iteration`
- `bounds.on_zero_iterations`
- `failure_behavior_ref`

Loops should also capture counter initialization and off-by-one semantics:

- `counter_initial_value`
- `max_iterations_inclusive`
- `evaluate_continue_before_first_iteration`
- `evaluate_exit_after_each_iteration`
- `on_zero_iterations`

Example:

```yaml
identity:
  id: loop.analysis_review.revision_loop
  label: revision_loop
  kind: loop
  source_families:
    - analysis_review_v1

members:
  - node.analysis_review.critic
  - node.analysis_review.reviser

entry_edge: edge.analysis_review.proposer_to_critic
continue_condition: condition.analysis_review.revision_required
exit_condition: condition.analysis_review.no_revision_required

bounds:
  max_iterations_source:
    contract_ref: contract.analysis_review.resolved_runtime
    field_path: max_revisions
  counter_initial_value: 0
  max_iterations_inclusive: false
  evaluate_continue_before_first_iteration: false
  evaluate_exit_after_each_iteration: true
  on_zero_iterations: allowed

state:
  iteration_counter: state.analysis_review.revision_count
  per_iteration_artifacts:
    - artifact.analysis_review.review_iteration_json

failure_behavior_ref: failure_behavior.analysis_review.revision_loop
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

### `data_mapping`

Required:

- `inputs`
- `outputs`
- `mapping.type`
- `mapping.deterministic`
- `mapping.lossy`
- `failure_behavior_ref`

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

Artifacts should also capture:

- `write_mode`
- `atomic_write`
- `conflict_policy`
- `encoding`
- `path_root_ref`

### `execution_binding`

Required:

- `role_name`
- `role_family`
- `provider_resolution`
- `model_resolution`
- `config_precedence`
- `adapter_entrypoint`
- `runtime_contract_refs`
- `failure_behavior_ref`

### `failure_behavior`

Required:

- `can_fail`
- `failure_modes`
- `retry_policy`
- `fallback`
- `error_surface`

### `scheduler_policy`

Required:

- `execution.mode`
- `execution.state_commit_boundary`
- `ordering`
- `cancellation`

### `trace_policy`

Required:

- `emits`
- `payload_defaults`
- `redaction_policy_ref`

### `prompt_surface`

Required:

- `used_by`
- `prompt_parts`
- `inputs`
- `output_contract`

### `model_io_contract`

Required:

- `schema_ref`
- `parser_ref`
- `validation_refs`

### `output_parser`

Required:

- `input_format`
- `output_schema_ref`
- `repair_strategy_ref`

### `capability`

Required:

- `capability_type`
- `used_by`
- `access`
- `policy`
- `failure_behavior_ref`

### `provider`

Required:

- `provider_type`
- `secret_refs`
- `network_egress`

### `static_lint_rule`

Required:

- `applies_to`
- `assertion`
- `failure_behavior_ref`

### `extraction_scope`

Required:

- `source_roots`
- `expected_surface_types`
- `coverage`
- `orphan_detection`

### `behavior_delta`

Required:

- `source_ref`
- `target_ref`
- `expected`
- `allowed_differences`

### `trace_event`

Required:

- `event_name`
- `payload_schema_ref`
- `correlation_fields`
- `timestamp_required`
- `monotonic_sequence_required`
- `redaction_policy_ref`

### `validation_rule`

Required:

- `applies_to`
- `assertion`
- `failure_behavior_ref`

### `equivalence_rule`

Required:

- `compares.source_behavior`
- `compares.target_behavior`
- `must_match`
- `allowed_to_differ`
- `requires_failure_cases`

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
- `assertion_notes`
- `assertion_refs`
- `required_before_promotion`

Proof rows should also capture:

- `proof_environment`
- `negative_cases`
- `goldens`

## Provenance Requirements

`evidence.files` is necessary but not sufficient.

Every extracted row should record precise evidence anchors where possible:

- file path
- symbol name
- behavioral test
- observed output artifact
- extraction confidence
- whether it has been verified against a runtime execution

This protects the inventory from “inventory by vibes.”

## Generated Indexes and Registry Lint

Indexes should be generated from item rows and checked by lint, not manually
maintained as an independent truth surface.

Minimum static lint rules should include:

- `static_lint_rule.c3.all_references_resolve`
- `static_lint_rule.c3.allowed_kind_prefixes_resolve`
- `static_lint_rule.c3.no_duplicate_ids`
- `static_lint_rule.c3.item_identity_matches_id_namespace`
- `static_lint_rule.c3.required_fields_by_kind_present`
- `static_lint_rule.c3.enum_values_valid`
- `static_lint_rule.c3.generated_indexes_match_items`
- `static_lint_rule.c3.graph_membership_is_reciprocal`
- `static_lint_rule.c3.edge_ports_exist`
- `static_lint_rule.c3.edge_port_contracts_compatible`
- `static_lint_rule.c3.no_public_candidate_without_passed_proof`
- `static_lint_rule.c3.no_edge_without_port_contracts`
- `static_lint_rule.c3.no_model_node_without_prompt_surface`
- `static_lint_rule.c3.no_promoted_row_without_failure_behavior_ref`
- `static_lint_rule.c3.no_promoted_row_without_equivalence_rule_ref`
- `static_lint_rule.c3.no_artifact_write_without_schema`
- `static_lint_rule.c3.no_state_write_without_owner`

## Failure and Recovery Requirements

Failure behavior must be treated as a top-level concern across rows, not hidden
inside notes.

For early extraction notes, inline failure blocks are acceptable. For
compilable or promoted rows, failure handling should normalize to first-class
`failure_behavior` items referenced by `failure_behavior_ref`.

Minimum expectation for executable rows:

```yaml
identity:
  id: failure_behavior.analysis_review.proposer
  label: proposer
  kind: failure_behavior
  source_families:
    - analysis_review_v1

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

## Equivalence and Golden Requirements

Promotion proofs should be backed by explicit equivalence rules whenever a row
is being replaced, normalized, or promoted into a reusable primitive.

An equivalence rule should record:

- what source behavior and target behavior are being compared
- what must match
- what may differ
- which failure cases must also be exercised

Golden traces and golden artifacts are acceptable proof anchors when exact
behavioral boundaries need to be preserved across a migration.

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

## Extraction Coverage and Orphan Tracking

Because extraction completeness is a core promise, the registry should also
track:

- source roots covered by each extraction scope
- expected surface kinds
- known extraction gaps
- code symbols without inventory rows
- inventory rows without source evidence

This is how the system proves completeness instead of only claiming it.

## Promotion and Proof Rules

The inventory is also the promotion gate.

Do not promote anything unless it has:

```yaml
promotion:
  disposition: shared_internal_primitive
  prerequisite_ids: []
  proof_strategy: proof.micro_linear_analysis_v1
  equivalence_rule_ref: equivalence_rule.analysis_review.proposer_to_reusable_node
  behavior_delta_ref: behavior_delta.analysis_review.proposer_to_reusable_node
  proof_status: passed
  behavior_delta_summary:
    expected: none
```

`behavior_delta_ref` is authoritative for promoted rows. Inline
`behavior_delta_summary` is only a readability aid.

If the authoritative behavior delta is `unknown`, the item must not become
public DSL. It may only remain family-private or experimental shared internal.

Promotion blockers should include:

- unresolved references
- missing source evidence
- missing runtime verification
- missing failure behavior
- missing trace events
- missing port contracts
- missing state ownership
- missing prompt surface for model-backed nodes
- missing artifact schema for artifact writes
- unknown behavior delta
- unproved equivalence

Shared-internal or public promotion should also require:

- `proof_strategy`
- `proof_status`
- `equivalence_rule_ref`
- `behavior_delta_ref`

## Proof Fixture Rows

Proof fixtures should be registry items too.

Example:

```yaml
identity:
  id: proof.micro_linear_analysis_v1
  label: micro_linear_analysis_v1
  kind: proof
  source_families:
    - analysis_review_v1

classification:
  status: planned

proves:
  - node.analysis_review.proposer
  - edge.analysis_review.proposer_to_critic
  - node.analysis_review.critic

fixture:
  path: tests/fixtures/harness/c3_microstrategies/micro_linear_analysis_v1.yaml

assertion_notes:
  - "proposer executes before critic"
  - "critic receives proposer payload"
  - "terminal payload includes summary"
  - "trace includes node.started/node.completed for both nodes"
assertion_refs:
  - validation_rule.proof.proposer_before_critic
  - validation_rule.proof.critic_receives_proposer_payload
  - validation_rule.proof.terminal_payload_includes_summary
  - validation_rule.proof.trace_includes_node_lifecycle_events

proof_environment:
  model_mode: mocked
  filesystem_mode: tempdir
  provider_mode: stubbed
  required_env: []
  forbidden_env: []

negative_cases:
  - missing_required_state
  - invalid_output_schema
  - model_call_failed

goldens:
  traces:
    - tests/fixtures/harness/c3_microstrategies/micro_linear_analysis_v1.trace.jsonl
  artifacts:
    - tests/fixtures/harness/c3_microstrategies/micro_linear_analysis_v1.summary.json

required_before_promotion:
  - shared_internal_primitive
```

This lets promotion become mechanically gated by proof.

## Tiny Common Rows

For the first linear slice, it is useful to define one tiny shared mapping row
that can back an always-on edge without inventing unnecessary conditional
semantics.

Example:

```yaml
identity:
  id: data_mapping.common.identity
  label: identity
  kind: data_mapping
  source_families:
    - common

inputs:
  - port.common.previous.output

outputs:
  - port.common.next.input

mapping:
  type: identity
  deterministic: true
  lossy: false

failure_behavior_ref: failure_behavior.common.mapping_contract_mismatch
```

An always-on edge can then use:

```yaml
transition:
  type: always
  data_mapping_ref: data_mapping.common.identity
```

This keeps the first linear proof slice simple while still exercising the
edge-to-port mapping contract.

## First Tiny Build Slice

The first executable rebuild slice should stay intentionally small.

It should prove:

- one graph
- one reusable node
- one input port
- one output port
- one reusable linear transition
- one data mapping
- one reusable terminal success outcome
- one reusable terminal failure outcome
- one minimal provider/model binding path
- one minimal prompt/model I/O contract if the node is model-backed
- one minimal state contract
- one trace event envelope
- one static lint pass proving references resolve

This is enough to prove:

- the system can run
- the system can fail honestly
- the system can be observed
- the registry can compile its own references

without pretending that the full family rebuild is already done.

## Recommended Markdown Outline

The human-readable inventory document that follows this design should use this
outline:

1. Purpose, rules, and extraction invariants
2. Current family map
3. Graph topology overview
4. Port and interface catalog
5. Node catalog
6. Edge / transition catalog
7. Condition / gate / loop catalog
8. State surface catalog
9. State transform and data mapping catalog
10. Execution binding catalog
11. Prompt / model I/O / parser catalog
12. Capability / tool / bridge / boundary catalog
13. Artifact and persistence catalog
14. Contract, schema, and compatibility catalog
15. Scheduler / run semantics catalog
16. Validation / lint / invariant catalog
17. Failure, retry, and terminal outcome catalog
18. Trace and observability catalog
19. Equivalence and golden catalog
20. Extraction coverage and orphan tracking
21. Promotion matrix
22. Proof plan and fixture index
23. Open questions, deferred items, and known behavior gaps

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
