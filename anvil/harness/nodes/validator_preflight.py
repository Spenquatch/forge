from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..state import HarnessState
from ..types import StrategyConfig, TaskSpec
from ..validation import preflight_validators


def _copy_role_if_missing(strategy_spec: dict[str, Any], missing_role: str, source_roles: list[str]) -> None:
    roles = strategy_spec.setdefault("roles", {})
    if missing_role in roles:
        return
    for source in source_roles:
        if source in roles:
            roles[missing_role] = deepcopy(roles[source])
            return


def validator_preflight_node(state: HarnessState) -> HarnessState:
    task_spec = TaskSpec.from_dict(dict(state.get("task_spec") or {}))
    strategy_spec_dict = deepcopy(dict(state.get("strategy_spec") or {}))
    strategy_kind = str(state.get("strategy_kind") or strategy_spec_dict.get("kind") or "single_pass")
    auto_fit = bool(state.get("auto_fit_strategy", True))

    warnings = list(state.get("warnings") or [])
    errors = list(state.get("errors") or [])

    if task_spec.task_kind == "analysis_review" and strategy_kind == "pfr_v1":
        if auto_fit:
            strategy_spec_dict["kind"] = "analysis_review_v1"
            _copy_role_if_missing(strategy_spec_dict, "critic", ["falsifier"])
            _copy_role_if_missing(strategy_spec_dict, "reviser", ["patcher", "proposer"])
            _copy_role_if_missing(strategy_spec_dict, "auditor", ["critic", "falsifier"])
            strategy_kind = "analysis_review_v1"
            warnings.append(
                "Auto-fit changed strategy kind from pfr_v1 to analysis_review_v1 for an analysis_review task."
            )
        else:
            errors.append(
                "analysis_review tasks are incompatible with pfr_v1 unless auto-fit is enabled."
            )
    elif task_spec.task_kind == "patch" and strategy_kind == "analysis_review_v1":
        if auto_fit:
            strategy_spec_dict["kind"] = "pfr_v1"
            _copy_role_if_missing(strategy_spec_dict, "falsifier", ["critic", "auditor"])
            _copy_role_if_missing(strategy_spec_dict, "patcher", ["reviser", "proposer"])
            strategy_kind = "pfr_v1"
            warnings.append(
                "Auto-fit changed strategy kind from analysis_review_v1 to pfr_v1 for a patch task."
            )
        else:
            errors.append(
                "patch tasks are incompatible with analysis_review_v1 unless auto-fit is enabled."
            )

    strategy_spec = StrategyConfig.from_dict(strategy_spec_dict)
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
