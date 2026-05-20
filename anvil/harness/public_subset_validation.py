from __future__ import annotations

from typing import Any, Literal

from anvil.harness.public_subset_registry import (
    C3_GRAPH_DSL_KINDS,
    CANONICAL_PLANNING_PHASE_STAGE_TYPES,
    CANONICAL_PLANNING_RUNTIME_TARGET,
    CANONICAL_PUBLIC_TOP_LEVEL_FIELDS,
    COMPATIBILITY_ONLY_KINDS,
    METADATA_ONLY_FIELDS,
    PLANNING_REQUIRED_POLICY_FIELDS,
    PUBLIC_STAGE_FAMILIES,
    PUBLIC_SUBSET_DSL_VERSION,
    RUNTIME_OWNED_EXCLUDED_FIELDS,
)

_PublicStrategySurface = Literal[
    "canonical_public",
    "compatibility_only",
    "internal_or_private",
]


def _require_mapping(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        raise ValueError("strategy payload must be a mapping.")
    return raw_payload


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _first_present_field(
    payload: dict[str, Any], field_names: tuple[str, ...]
) -> str | None:
    for field_name in field_names:
        if field_name in payload:
            return field_name
    return None


def _validate_public_stage_families(payload: dict[str, Any]) -> None:
    roles = payload.get("roles")
    if roles is None:
        return
    if not isinstance(roles, dict):
        return
    invalid_stage_families = sorted(
        str(role_name).strip()
        for role_name in roles
        if str(role_name).strip() not in PUBLIC_STAGE_FAMILIES
    )
    if invalid_stage_families:
        raise ValueError(
            "canonical public strategies must use only public stage families; "
            f"unsupported role key {invalid_stage_families[0]!r}."
        )


def _validate_planning_payload(payload: dict[str, Any]) -> None:
    runtime_target = _normalized_text(payload.get("runtime_target"))
    if runtime_target != CANONICAL_PLANNING_RUNTIME_TARGET:
        raise ValueError(
            "canonical planning strategies must declare runtime_target "
            f"{CANONICAL_PLANNING_RUNTIME_TARGET!r}."
        )

    missing_policy_fields = [
        field_name
        for field_name in PLANNING_REQUIRED_POLICY_FIELDS
        if not _normalized_text(payload.get(field_name))
    ]
    if missing_policy_fields:
        raise ValueError(
            "canonical planning strategies must declare "
            f"{missing_policy_fields[0]!r}."
        )

    raw_phases = payload.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValueError("canonical planning strategies must declare phases[].")

    declared_stage_types = tuple(
        _normalized_text(phase.get("stage_type")) if isinstance(phase, dict) else ""
        for phase in raw_phases
    )
    if declared_stage_types != CANONICAL_PLANNING_PHASE_STAGE_TYPES:
        raise ValueError(
            "canonical planning strategies must declare phases[].stage_type in "
            "canonical order: " + ", ".join(CANONICAL_PLANNING_PHASE_STAGE_TYPES) + "."
        )


def _validate_non_planning_payload(payload: dict[str, Any]) -> None:
    if "runtime_target" in payload:
        raise ValueError(
            "canonical analysis-review strategies must omit runtime_target."
        )

    planning_only_fields = (
        "phases",
        *PLANNING_REQUIRED_POLICY_FIELDS,
    )
    first_planning_field = _first_present_field(payload, planning_only_fields)
    if first_planning_field is not None:
        raise ValueError(
            "canonical analysis-review strategies must not declare planning-only "
            f"field {first_planning_field!r}."
        )


def classify_public_strategy_surface(raw_payload: Any) -> _PublicStrategySurface:
    payload = _require_mapping(raw_payload)
    if "dsl_version" in payload:
        return "canonical_public"

    kind = _normalized_text(payload.get("kind"))
    if kind in COMPATIBILITY_ONLY_KINDS:
        return "compatibility_only"

    return "internal_or_private"


def validate_public_strategy_payload(raw_payload: Any) -> None:
    payload = _require_mapping(raw_payload)
    if classify_public_strategy_surface(payload) != "canonical_public":
        return

    dsl_version = _normalized_text(payload.get("dsl_version"))
    if dsl_version != PUBLIC_SUBSET_DSL_VERSION:
        raise ValueError(
            "canonical public strategies must declare dsl_version "
            f"{PUBLIC_SUBSET_DSL_VERSION!r}."
        )

    kind = _normalized_text(payload.get("kind"))
    if kind not in C3_GRAPH_DSL_KINDS:
        raise ValueError(
            "canonical public strategies must declare kind as one of: "
            + ", ".join(C3_GRAPH_DSL_KINDS)
            + "."
        )

    runtime_owned_field = _first_present_field(payload, RUNTIME_OWNED_EXCLUDED_FIELDS)
    if runtime_owned_field is not None:
        raise ValueError(
            "canonical public strategies must not declare runtime-owned field "
            f"{runtime_owned_field!r}."
        )

    metadata_only_field = _first_present_field(payload, METADATA_ONLY_FIELDS)
    if metadata_only_field is not None:
        raise ValueError(
            "canonical public strategies must not declare metadata-only field "
            f"{metadata_only_field!r}."
        )

    unknown_keys = sorted(set(payload) - set(CANONICAL_PUBLIC_TOP_LEVEL_FIELDS))
    if unknown_keys:
        raise ValueError(
            "canonical public strategies must not declare unsupported top-level "
            f"key {unknown_keys[0]!r}."
        )

    _validate_public_stage_families(payload)

    if kind == "deterministic_feature_planning_v1":
        _validate_planning_payload(payload)
        return

    _validate_non_planning_payload(payload)


__all__ = (
    "classify_public_strategy_surface",
    "validate_public_strategy_payload",
)
