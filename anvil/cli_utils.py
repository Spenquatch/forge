from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

ROLE_ORDER: tuple[str, ...] = ("execute", "critique", "refine", "review", "reflect")


def normalize_requested_pipeline(
    base_provider: str, role_providers: Optional[Mapping[str, str]]
) -> dict[str, str]:
    normalized_base = base_provider or "auto"
    pipeline = {role: normalized_base for role in ROLE_ORDER}
    if role_providers:
        for role in ROLE_ORDER:
            override = role_providers.get(role)
            if override:
                pipeline[role] = override
    return pipeline


def build_state_pipeline(
    *, base_provider: str, role_providers: Optional[Mapping[str, str]]
) -> dict[str, str]:
    pipeline: dict[str, str] = {}
    if base_provider and base_provider != "auto":
        pipeline = {role: base_provider for role in ROLE_ORDER}
    if role_providers:
        for role, provider_name in role_providers.items():
            if provider_name:
                pipeline[role] = provider_name
    return pipeline


def format_pipeline_map(pipeline: Mapping[str, str]) -> str:
    return ", ".join(f"{role}={pipeline.get(role, '(default)')}" for role in ROLE_ORDER)


def format_role_overrides(overrides: Mapping[str, str]) -> str:
    return ", ".join(
        f"{role}={overrides[role]}" for role in ROLE_ORDER if role in overrides
    )


def provider_selection_status(
    *,
    base_provider: str,
    enable_leadership: bool,
    role_providers: Optional[Mapping[str, str]],
) -> str:
    if not enable_leadership:
        return "disabled"
    if role_providers:
        return "skipped (role overrides provided)"
    if base_provider != "auto":
        return "skipped (base provider specified)"
    return "active"


def format_mapping_diff(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> list[str]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    changes: list[str] = []
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            changes.append(f"{key} {before_value!r} → {after_value!r}")
    return changes
