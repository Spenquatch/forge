from __future__ import annotations

"""Frozen C2.9 public subset registry for future C3 strategy authoring."""

PUBLIC_SUBSET_DSL_VERSION = "c3_strategy_v1"

C3_GRAPH_DSL_KINDS = (
    "analysis_review_bounded_v1",
    "analysis_review_trust_v1",
    "deterministic_feature_planning_v1",
)

BROADER_PUBLIC_BUILTIN_KINDS = (
    "single_pass",
    "pfr_v1",
)

COMPATIBILITY_ONLY_KINDS = ("analysis_review_v1",)

PUBLIC_GRAPH_PRIMITIVES = (
    "stage",
    "linear_edge",
    "conditional_branch",
    "bounded_loop",
    "terminal_outcome",
    "planning_phase",
)

PUBLIC_TRANSITION_FORMS = (
    "linear_next",
    "enumerated_branch",
    "bounded_loop_back_edge",
    "terminal_exit",
)

PUBLIC_STAGE_FAMILIES = (
    "solver",
    "proposer",
    "falsifier",
    "patcher",
    "critic",
    "reviser",
    "auditor",
    "focus_gate",
    "planner",
)

PUBLIC_ROLE_FAMILIES = (
    "execute",
    "critique",
    "refine",
    "review",
)

STAGE_FAMILY_ROLE_BINDINGS = {
    "solver": "execute",
    "proposer": "execute",
    "planner": "execute",
    "focus_gate": "execute",
    "falsifier": "critique",
    "critic": "critique",
    "patcher": "refine",
    "reviser": "refine",
    "auditor": "review",
}

CANONICAL_PLANNING_PHASE_STAGE_TYPES = (
    "rubric_design_doc",
    "architecture_seam_decomposition",
    "parallel_workstream_planning",
    "executable_slice_emission",
)

PLANNING_REQUIRED_POLICY_FIELDS = (
    "artifact_policy",
    "determinism_policy",
    "discovery_policy",
    "rubric_policy",
    "stop_policy",
)

CANONICAL_PUBLIC_TOP_LEVEL_FIELDS = (
    "dsl_version",
    "name",
    "kind",
    "roles",
    "runtime_target",
    "phases",
    "artifact_policy",
    "determinism_policy",
    "discovery_policy",
    "rubric_policy",
    "stop_policy",
    "trust_review",
)

CANONICAL_PLANNING_RUNTIME_TARGET = "planning_v1"

RUNTIME_OWNED_EXCLUDED_FIELDS = (
    "coverage_policy",
    "phase_inputs",
)

METADATA_ONLY_FIELDS = (
    "schema_version",
    "subset",
)

__all__ = (
    "PUBLIC_SUBSET_DSL_VERSION",
    "C3_GRAPH_DSL_KINDS",
    "BROADER_PUBLIC_BUILTIN_KINDS",
    "COMPATIBILITY_ONLY_KINDS",
    "PUBLIC_GRAPH_PRIMITIVES",
    "PUBLIC_TRANSITION_FORMS",
    "PUBLIC_STAGE_FAMILIES",
    "PUBLIC_ROLE_FAMILIES",
    "STAGE_FAMILY_ROLE_BINDINGS",
    "CANONICAL_PLANNING_PHASE_STAGE_TYPES",
    "PLANNING_REQUIRED_POLICY_FIELDS",
    "CANONICAL_PUBLIC_TOP_LEVEL_FIELDS",
    "CANONICAL_PLANNING_RUNTIME_TARGET",
    "RUNTIME_OWNED_EXCLUDED_FIELDS",
    "METADATA_ONLY_FIELDS",
)
