from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from ..artifacts import create_run_id
from ..files import load_structured_file
from ..state import HarnessState, initialize_harness_state
from ..types import StrategyConfig, TaskSpec


def prepare_run_node(state: dict[str, Any]) -> HarnessState:
    task_path = str(state.get("task_path") or "")
    strategy_path = str(state.get("strategy_path") or "")
    workspace_root = str(Path(state.get("workspace_root") or state.get("workspace") or ".").resolve())
    out_root = str(Path(state.get("out_root") or ".forge-harness-runs").resolve())
    config_path = str(state.get("config_path") or "config/models.yaml")
    auto_fit_strategy = bool(state.get("auto_fit_strategy", True))
    requested_execution_mode = str(
        state.get("analysis_review_execution_mode") or "legacy_bridge"
    )
    analysis_review_execution_mode: Literal["legacy_bridge", "graph_owned"] = (
        "graph_owned" if requested_execution_mode == "graph_owned" else "legacy_bridge"
    )
    base = initialize_harness_state(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace_root=workspace_root,
        out_root=out_root,
        config_path=config_path,
        thread_id=(str(state.get("thread_id")) if state.get("thread_id") else None),
        auto_fit_strategy=auto_fit_strategy,
        analysis_review_execution_mode=analysis_review_execution_mode,
    )

    try:
        raw_task_spec = load_structured_file(task_path)
        task_spec = TaskSpec.from_dict(raw_task_spec)
    except FileNotFoundError as exc:
        raise ValueError(f"Task spec file not found: {task_path}") from exc

    try:
        raw_strategy_spec = load_structured_file(strategy_path)
        strategy_spec = StrategyConfig.from_dict(raw_strategy_spec)
    except FileNotFoundError as exc:
        raise ValueError(f"Strategy spec file not found: {strategy_path}") from exc
    run_id = create_run_id(task_spec.id)
    base["run_id"] = run_id
    base["run_dir"] = str(Path(out_root) / run_id)
    base["task_spec"] = {**dict(raw_task_spec), **task_spec.to_dict()}
    base["strategy_spec"] = {**dict(raw_strategy_spec), **strategy_spec.to_dict()}
    base["task_kind"] = task_spec.task_kind  # type: ignore[assignment]
    base["strategy_kind"] = strategy_spec.kind  # type: ignore[assignment]
    return base
