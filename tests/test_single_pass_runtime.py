from __future__ import annotations

from pathlib import Path

from anvil.harness.single_pass_runtime import execute_single_pass_runtime
from anvil.harness.state import initialize_harness_state


def test_single_pass_runtime_consumes_compiled_graph_stage_surface(
    tmp_path: Path, monkeypatch
) -> None:
    state = initialize_harness_state(
        task_path=str(tmp_path / "task.yaml"),
        strategy_path=str(tmp_path / "strategy.yaml"),
        workspace_root=str(tmp_path / "workspace"),
        out_root=str(tmp_path / "out"),
    )
    state["strategy_graph_spec"] = {
        "runtime_target": "single_pass",
        "stages": [
            {
                "stage_id": "solver",
                "role_name": "solver",
                "stage_type": "single_pass_solution",
            }
        ],
    }

    def _fake_bridge(payload):
        payload = dict(payload)
        payload["summary_payload"] = {"verdict": "success"}
        payload["run_details"] = {"bridge_used": True}
        return payload

    monkeypatch.setattr(
        "anvil.harness.single_pass_runtime.run_harness_runner",
        _fake_bridge,
    )

    result = execute_single_pass_runtime(state)

    assert result["summary_payload"] == {"verdict": "success"}
    assert result["run_details"]["bridge_used"] is True
    assert result["run_details"]["single_pass_runtime_stage_id"] == "solver"
    assert result["run_details"]["single_pass_runtime_stage_type"] == (
        "single_pass_solution"
    )
