from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..state import HarnessState
from ..types import (
    ANALYSIS_REVIEW_BOUNDED_KIND,
    ANALYSIS_REVIEW_LEGACY_KIND,
    PLANNING_RUNTIME_TARGET,
    StrategyConfig,
    TaskSpec,
    is_analysis_review_strategy_kind,
)
from ..validation import preflight_validators


def _copy_role_if_missing(strategy_spec: dict[str, Any], missing_role: str, source_roles: list[str]) -> None:
    roles = strategy_spec.setdefault("roles", {})
    if missing_role in roles:
        return
    for source in source_roles:
        if source in roles:
            roles[missing_role] = deepcopy(roles[source])
            return


def _mark_invalid_preflight(
    state: HarnessState,
    *,
    warnings: list[str],
    errors: list[str],
    stop_reason: str,
) -> HarnessState:
    state["warnings"] = warnings
    state["errors"] = errors
    state["config_verdict"] = "invalid_config"
    state["validator_verdict"] = "misconfigured"
    state["content_verdict"] = "rejected"
    state["run_verdict"] = "invalid_config"
    state["summary_text"] = errors[0]
    state["stop_reason"] = stop_reason
    state["validator_preflight"] = []
    return state


def validator_preflight_node(state: HarnessState) -> HarnessState:
    strategy_spec_dict = deepcopy(dict(state.get("strategy_spec") or {}))
    strategy_kind = str(state.get("strategy_kind") or strategy_spec_dict.get("kind") or "single_pass")
    auto_fit = bool(state.get("auto_fit_strategy", True))

    warnings = list(state.get("warnings") or [])
    errors = list(state.get("errors") or [])
    try:
        task_spec = TaskSpec.from_dict(dict(state.get("task_spec") or {}))
    except ValueError as exc:
        errors.append(str(exc))
        return _mark_invalid_preflight(
            state,
            warnings=warnings,
            errors=errors,
            stop_reason="task_spec_parse",
        )

    if strategy_kind == ANALYSIS_REVIEW_LEGACY_KIND:
        strategy_spec_dict["kind"] = ANALYSIS_REVIEW_BOUNDED_KIND
        strategy_kind = ANALYSIS_REVIEW_BOUNDED_KIND
        warnings.append(
            "Strategy kind analysis_review_v1 is deprecated and now resolves to analysis_review_bounded_v1."
        )

    try:
        strategy_spec = StrategyConfig.from_dict(strategy_spec_dict)
    except ValueError as exc:
        errors.append(str(exc))
        return _mark_invalid_preflight(
            state,
            warnings=warnings,
            errors=errors,
            stop_reason="strategy_spec_parse",
        )

    runtime_target = str(strategy_spec.runtime_target or "").strip()

    if task_spec.task_kind == "planning":
        if runtime_target != PLANNING_RUNTIME_TARGET:
            errors.append(
                "planning tasks require a strategy with runtime_target 'planning_v1'; auto-fit is not supported."
            )
    elif runtime_target == PLANNING_RUNTIME_TARGET:
        errors.append(
            f"{task_spec.task_kind} tasks are incompatible with runtime_target 'planning_v1'; auto-fit is not supported."
        )
    elif task_spec.task_kind == "analysis_review" and strategy_kind == "pfr_v1":
        if auto_fit:
            strategy_spec_dict["kind"] = ANALYSIS_REVIEW_BOUNDED_KIND
            _copy_role_if_missing(strategy_spec_dict, "critic", ["falsifier"])
            _copy_role_if_missing(strategy_spec_dict, "reviser", ["patcher", "proposer"])
            _copy_role_if_missing(strategy_spec_dict, "auditor", ["critic", "falsifier"])
            strategy_kind = ANALYSIS_REVIEW_BOUNDED_KIND
            warnings.append(
                "Auto-fit changed strategy kind from pfr_v1 to analysis_review_bounded_v1 for an analysis_review task."
            )
            strategy_spec = StrategyConfig.from_dict(strategy_spec_dict)
        else:
            errors.append(
                "analysis_review tasks are incompatible with pfr_v1 unless auto-fit is enabled."
            )
    elif task_spec.task_kind == "patch" and is_analysis_review_strategy_kind(strategy_kind):
        if auto_fit:
            original_kind = strategy_kind
            strategy_spec_dict["kind"] = "pfr_v1"
            _copy_role_if_missing(strategy_spec_dict, "falsifier", ["critic", "auditor"])
            _copy_role_if_missing(strategy_spec_dict, "patcher", ["reviser", "proposer"])
            strategy_kind = "pfr_v1"
            warnings.append(
                f"Auto-fit changed strategy kind from {original_kind} to pfr_v1 for a patch task."
            )
            strategy_spec = StrategyConfig.from_dict(strategy_spec_dict)
        else:
            errors.append(
                f"patch tasks are incompatible with {strategy_kind} unless auto-fit is enabled."
            )
    preflight = preflight_validators(
        strategy_spec.validators,
        Path(str(state.get("workspace_root") or ".")),
        task=task_spec,
        strategy=strategy_spec,
        workspace_changed=False,
    )
    for item in preflight:
        if item.get("required") and item.get("status") in {"failed", "not_applicable"}:
            reason = str(item.get("reason") or f"Validator {item.get('name')} is not applicable")
            errors.append(reason)

    state["task_spec"] = task_spec.to_dict()
    state["strategy_spec"] = strategy_spec.to_dict()
    state["strategy_kind"] = strategy_kind  # type: ignore[assignment]
    state["warnings"] = warnings
    state["errors"] = errors

    if errors:
        state["config_verdict"] = "invalid_config"
        state["validator_verdict"] = "misconfigured"
        state["content_verdict"] = "rejected"
        state["run_verdict"] = "invalid_config"
        state["summary_text"] = errors[0]
        state["stop_reason"] = "validator_preflight"
    else:
        state.setdefault("config_verdict", "pass")
        if preflight and any(item.get("required") for item in preflight):
            state.setdefault("validator_verdict", "not_applicable")
    state["validator_preflight"] = preflight
    return state
