from __future__ import annotations

from pathlib import Path

from anvil.harness.files import load_structured_file
from anvil.harness.planning_runtime import PLANNING_PHASE_ORDER, PLANNING_POLICY_FIELDS
from anvil.harness.providers import _map_role_name_to_provider_role
from anvil.harness.public_subset_registry import (
    BROADER_PUBLIC_BUILTIN_KINDS,
    C3_GRAPH_DSL_KINDS,
    CANONICAL_PLANNING_PHASE_STAGE_TYPES,
    COMPATIBILITY_ONLY_KINDS,
    METADATA_ONLY_FIELDS,
    PLANNING_REQUIRED_POLICY_FIELDS,
    PUBLIC_GRAPH_PRIMITIVES,
    PUBLIC_ROLE_FAMILIES,
    PUBLIC_STAGE_FAMILIES,
    PUBLIC_SUBSET_DSL_VERSION,
    PUBLIC_TRANSITION_FORMS,
    RUNTIME_OWNED_EXCLUDED_FIELDS,
    STAGE_FAMILY_ROLE_BINDINGS,
)
from anvil.harness.strategy_graph import (
    STRATEGY_GRAPH_SCHEMA_VERSION,
    STRATEGY_GRAPH_SUBSET,
    build_strategy_graph_spec,
)
from anvil.harness.types import (
    ANALYSIS_REVIEW_BOUNDED_KIND,
    ANALYSIS_REVIEW_LEGACY_KIND,
    ANALYSIS_REVIEW_TRUST_KIND,
    DETERMINISTIC_FEATURE_PLANNING_KIND,
    PLANNING_PHASE_STAGE_TYPES,
    PLANNING_RUNTIME_TARGET,
    StrategyConfig,
)

CONTRACT_DOC = Path("docs/strategy_dsl_public_subset_contract.md")
PUBLIC_SUBSET_ROOT = Path("examples/harness/public_subset")
CANONICAL_ROOT = PUBLIC_SUBSET_ROOT / "canonical"
COMPATIBILITY_ROOT = PUBLIC_SUBSET_ROOT / "compatibility"
NEGATIVE_ROOT = PUBLIC_SUBSET_ROOT / "negative"


def _load_example(path: Path) -> dict[str, object]:
    return load_structured_file(path)


def _contract_violations(payload: dict[str, object]) -> list[str]:
    violations: list[str] = []
    allowed_top_level_keys = {
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
        "coverage_policy",
        "phase_inputs",
        "schema_version",
        "subset",
    }
    kind = str(payload.get("kind") or "")
    allowed_kinds = {
        *C3_GRAPH_DSL_KINDS,
        *BROADER_PUBLIC_BUILTIN_KINDS,
        *COMPATIBILITY_ONLY_KINDS,
    }
    if kind not in allowed_kinds:
        violations.append("kind")

    unknown_keys = set(payload) - allowed_top_level_keys
    if unknown_keys:
        violations.append("top_level_key")

    roles = payload.get("roles")
    if isinstance(roles, dict):
        invalid_stage_families = {
            str(role_name) for role_name in roles if str(role_name) not in PUBLIC_STAGE_FAMILIES
        }
        if invalid_stage_families:
            violations.append("stage_family")

    if any(field in payload for field in RUNTIME_OWNED_EXCLUDED_FIELDS):
        violations.append("runtime_owned")

    if any(field in payload for field in METADATA_ONLY_FIELDS):
        violations.append("metadata_only")

    return violations


def test_public_subset_registry_matches_locked_c29_contract_sets():
    assert PUBLIC_SUBSET_DSL_VERSION == "c3_strategy_v1"
    assert C3_GRAPH_DSL_KINDS == (
        ANALYSIS_REVIEW_BOUNDED_KIND,
        ANALYSIS_REVIEW_TRUST_KIND,
        DETERMINISTIC_FEATURE_PLANNING_KIND,
    )
    assert BROADER_PUBLIC_BUILTIN_KINDS == ("single_pass", "pfr_v1")
    assert COMPATIBILITY_ONLY_KINDS == (ANALYSIS_REVIEW_LEGACY_KIND,)
    assert PUBLIC_GRAPH_PRIMITIVES == (
        "stage",
        "linear_edge",
        "conditional_branch",
        "bounded_loop",
        "terminal_outcome",
        "planning_phase",
    )
    assert PUBLIC_TRANSITION_FORMS == (
        "linear_next",
        "enumerated_branch",
        "bounded_loop_back_edge",
        "terminal_exit",
    )
    assert PUBLIC_STAGE_FAMILIES == (
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
    assert PUBLIC_ROLE_FAMILIES == ("execute", "critique", "refine", "review")
    assert STAGE_FAMILY_ROLE_BINDINGS == {
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
    assert CANONICAL_PLANNING_PHASE_STAGE_TYPES == PLANNING_PHASE_STAGE_TYPES
    assert CANONICAL_PLANNING_PHASE_STAGE_TYPES == PLANNING_PHASE_ORDER
    assert PLANNING_REQUIRED_POLICY_FIELDS == tuple(
        field for field in PLANNING_POLICY_FIELDS if field != "coverage_policy"
    )
    assert RUNTIME_OWNED_EXCLUDED_FIELDS == ("coverage_policy", "phase_inputs")
    assert METADATA_ONLY_FIELDS == ("schema_version", "subset")


def test_public_subset_registry_stays_aligned_with_current_runtime_evidence():
    for stage_family, role_family in STAGE_FAMILY_ROLE_BINDINGS.items():
        assert stage_family in PUBLIC_STAGE_FAMILIES
        assert role_family in PUBLIC_ROLE_FAMILIES
        assert _map_role_name_to_provider_role(stage_family) == role_family

    single_pass_spec = build_strategy_graph_spec("single_pass", {}).to_dict()
    assert single_pass_spec["schema_version"] == STRATEGY_GRAPH_SCHEMA_VERSION
    assert single_pass_spec["subset"] == STRATEGY_GRAPH_SUBSET
    assert tuple(field for field in METADATA_ONLY_FIELDS if field in single_pass_spec) == (
        "schema_version",
        "subset",
    )


def test_contract_doc_mirrors_registry_and_boundary_language():
    contract_doc = CONTRACT_DOC.read_text(encoding="utf-8")

    for text in (
        "Scope and milestone boundary",
        "Canonical public strategy kinds versus broader public built-ins",
        "Compatibility-only kinds",
        "Public versioning via `dsl_version`",
        "Public graph primitives",
        "Public transition forms",
        "Public stage families and role-family bindings",
        "Planning-specific canonical phase order and required policy refs",
        "Runtime-owned excluded fields",
        "Metadata-only fields",
        "Canonical example taxonomy",
        "Explicit exclusions and post-`C2.9` follow-up boundary",
        PUBLIC_SUBSET_DSL_VERSION,
        "analysis_review_bounded_v1",
        "analysis_review_trust_v1",
        "deterministic_feature_planning_v1",
        "analysis_review_v1",
        "single_pass",
        "pfr_v1",
        "coverage_policy",
        "phase_inputs",
        "schema_version",
        "subset",
        "runtime_target: planning_v1",
        "Canonical non-planning examples omit `runtime_target`.",
        "It does not claim parser enforcement, preflight enforcement, or runtime",
        "wiring already exists.",
        "It does not freeze a public task-spec contract in this branch.",
    ):
        assert text in contract_doc


def test_canonical_examples_follow_the_frozen_public_subset_rules():
    canonical_examples = {
        "analysis_review_bounded_v1.yaml": CANONICAL_ROOT
        / "analysis_review_bounded_v1.yaml",
        "analysis_review_trust_v1.yaml": CANONICAL_ROOT
        / "analysis_review_trust_v1.yaml",
        "deterministic_feature_planning_v1.yaml": CANONICAL_ROOT
        / "deterministic_feature_planning_v1.yaml",
    }

    for path in canonical_examples.values():
        payload = _load_example(path)
        parsed = StrategyConfig.from_dict(payload)

        assert payload["dsl_version"] == PUBLIC_SUBSET_DSL_VERSION
        assert str(payload["kind"]) in C3_GRAPH_DSL_KINDS
        assert ANALYSIS_REVIEW_LEGACY_KIND not in str(payload["kind"])
        assert not any(field in payload for field in RUNTIME_OWNED_EXCLUDED_FIELDS)
        assert not any(field in payload for field in METADATA_ONLY_FIELDS)
        assert parsed.kind == payload["kind"]

    bounded = _load_example(canonical_examples["analysis_review_bounded_v1.yaml"])
    trust = _load_example(canonical_examples["analysis_review_trust_v1.yaml"])
    planning = _load_example(
        canonical_examples["deterministic_feature_planning_v1.yaml"]
    )

    assert "runtime_target" not in bounded
    assert "runtime_target" not in trust
    assert planning["runtime_target"] == PLANNING_RUNTIME_TARGET
    assert tuple(phase["stage_type"] for phase in planning["phases"]) == (
        CANONICAL_PLANNING_PHASE_STAGE_TYPES
    )
    for field in PLANNING_REQUIRED_POLICY_FIELDS:
        assert field in planning


def test_compatibility_example_is_explicitly_non_canonical():
    compatibility_path = COMPATIBILITY_ROOT / "analysis_review_v1.yaml"
    payload = _load_example(compatibility_path)
    text = compatibility_path.read_text(encoding="utf-8")

    assert payload["kind"] == ANALYSIS_REVIEW_LEGACY_KIND
    assert "dsl_version" not in payload
    assert "Compatibility-only accepted legacy input." in text
    assert "not the canonical public C3 v1 authoring example" in text


def test_negative_examples_each_map_to_exactly_one_contract_violation():
    expected_violations = {
        NEGATIVE_ROOT / "invalid_kind.yaml": "kind",
        NEGATIVE_ROOT / "unknown_top_level_key.yaml": "top_level_key",
        NEGATIVE_ROOT / "invalid_stage_family.yaml": "stage_family",
        NEGATIVE_ROOT / "runtime_owned_phase_inputs.yaml": "runtime_owned",
        NEGATIVE_ROOT / "metadata_only_schema_version.yaml": "metadata_only",
    }

    for path, expected_violation in expected_violations.items():
        payload = _load_example(path)
        violations = _contract_violations(payload)

        assert violations == [expected_violation], path.name
