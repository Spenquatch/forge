from __future__ import annotations

from typing import Any

from anvil.harness.bounded_stage_runtime import run_linear_stage_sequence


def test_bounded_stage_runtime_reuses_linear_stage_substrate_outside_planning() -> None:
    state: dict[str, Any] = {"observed": [], "payloads": {}}

    stage_specs = [
        {"id": "collect_repo", "stage_type": "collect"},
        {"id": "summarize_repo", "stage_type": "summarize"},
    ]

    def _payload_resolver(
        runtime_state: dict[str, Any], stage_spec: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "stage_id": stage_spec["id"],
            "summary": f"payload:{stage_spec['stage_type']}",
            "payload_index": len(runtime_state["payloads"]),
        }

    def _collect(
        runtime_state: dict[str, Any],
        stage_spec: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        runtime_state["payloads"][stage_spec["id"]] = payload["summary"]
        return {"status": "success", "stop_reason": None}

    def _summarize(
        runtime_state: dict[str, Any],
        stage_spec: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        runtime_state["payloads"][stage_spec["id"]] = payload["summary"]
        return {"status": "success", "stop_reason": None}

    def _observe(
        runtime_state: dict[str, Any],
        stage_spec: dict[str, Any],
        outcome: dict[str, Any],
    ) -> None:
        runtime_state["observed"].append((stage_spec["id"], outcome["status"]))

    outcome = run_linear_stage_sequence(
        state,
        stage_specs=stage_specs,
        handler_registry={"collect": _collect, "summarize": _summarize},
        payload_resolver=_payload_resolver,
        observe_outcome=_observe,
    )

    assert outcome == {
        "terminal_status": "success",
        "stop_reason": None,
        "failed_stage_id": None,
    }
    assert state["observed"] == [
        ("collect_repo", "success"),
        ("summarize_repo", "success"),
    ]
    assert state["payloads"] == {
        "collect_repo": "payload:collect",
        "summarize_repo": "payload:summarize",
    }


def test_bounded_stage_runtime_stops_on_first_non_success_terminal_outcome() -> None:
    state: dict[str, Any] = {"observed": []}

    def _payload_resolver(
        runtime_state: dict[str, Any], stage_spec: dict[str, Any]
    ) -> dict[str, Any]:
        del runtime_state
        return {"stage_id": stage_spec["id"]}

    def _collect(
        runtime_state: dict[str, Any],
        stage_spec: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        del runtime_state, stage_spec, payload
        return {
            "status": "clarification_needed",
            "stop_reason": "bounded_collect_needs_scope",
            "clarification_requests": [{"question": "Which repo surface is in scope?"}],
        }

    def _observe(
        runtime_state: dict[str, Any],
        stage_spec: dict[str, Any],
        outcome: dict[str, Any],
    ) -> None:
        runtime_state["observed"].append((stage_spec["id"], outcome["status"]))

    outcome = run_linear_stage_sequence(
        state,
        stage_specs=[
            {"id": "collect_repo", "stage_type": "collect"},
            {"id": "never_runs", "stage_type": "summarize"},
        ],
        handler_registry={
            "collect": _collect,
            "summarize": lambda *_args, **_kwargs: {"status": "success"},
        },
        payload_resolver=_payload_resolver,
        observe_outcome=_observe,
    )

    assert outcome["terminal_status"] == "clarification_needed"
    assert outcome["stop_reason"] == "bounded_collect_needs_scope"
    assert outcome["failed_stage_id"] == "collect_repo"
    assert state["observed"] == [("collect_repo", "clarification_needed")]
