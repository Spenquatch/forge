from __future__ import annotations

import asyncio

from anvil.harness.subgraphs.analysis_review_v1 import analysis_review_v1_subgraph
from anvil.harness.state import (
    HARNESS_STATE_SERIALIZATION_VERSION,
    SUMMARY_BOUNDARY_VERSION,
    state_from_summary,
    summary_read_adapter_v1,
)


def _focus_decision() -> dict[str, object]:
    return {
        "decision_state": "selected",
        "selected_focus_id": "focus-1",
        "selected_focus_paths": ["src/focus.py"],
        "question": {"prompt": "", "options": []},
        "warnings": [],
    }


def test_summary_read_adapter_v1_reads_b1_boundary_fields(tmp_path):
    summary = {
        "run_id": "run-123",
        "thread_id": "thread-123",
        "workspace": "/tmp/workspace",
        "task": {"id": "task-123", "task_kind": "analysis_review"},
        "strategy_name": "analysis_review_v1",
        "strategy_kind": "analysis_review_v1",
        "serialization_version": "custom-serialization-v1",
        "summary_boundary_version": "summary_projection_v1",
        "bridge_boundary_version": "legacy_bridge_boundary_v1",
        "strategy_graph_spec": {"runtime_target": "analysis_review_v1"},
        "strategy_graph_spec_id": "analysis-review-spec",
        "strategy_graph_subset": "bounded_strategy_graph_v1",
        "artifacts": {"run_dir": str(tmp_path / "run")},
        "run_details": {
            "revisions_completed": 2,
            "analysis_review_contract": {"mode": "bounded"},
            "focus_decision": _focus_decision(),
            "topic_ledger": [
                {"topic_id": "TOPIC-1", "resolution_status": "open"}
            ],
        },
    }

    state = summary_read_adapter_v1(summary)

    assert state["serialization_version"] == "custom-serialization-v1"
    assert state["analysis_review_contract"] == {"mode": "bounded"}
    assert state["strategy_graph_spec"] == {"runtime_target": "analysis_review_v1"}
    assert state["strategy_graph_spec_id"] == "analysis-review-spec"
    assert state["strategy_graph_subset"] == "bounded_strategy_graph_v1"
    assert state["focus_decision"]["selected_focus_id"] == "focus-1"
    assert state["topic_ledger"] == [
        {"topic_id": "TOPIC-1", "resolution_status": "open"}
    ]
    assert state["summary_boundary_version"] == "summary_projection_v1"
    assert state["bridge_boundary_version"] == "legacy_bridge_boundary_v1"
    assert state["revision_round"] == 2
    assert state["summary_payload"] == summary


def test_state_from_summary_is_a_compatibility_wrapper():
    summary = {
        "run_id": "run-legacy",
        "workspace": "/tmp/workspace",
        "task": {"id": "task-legacy"},
        "strategy_kind": "single_pass",
        "artifacts": {"run_dir": ".forge-harness-runs/run-legacy"},
    }

    adapted = summary_read_adapter_v1(summary, fallback_thread_id="fallback-thread")
    wrapped = state_from_summary(summary, fallback_thread_id="fallback-thread")

    assert wrapped["run_id"] == adapted["run_id"]
    assert wrapped["thread_id"] == adapted["thread_id"]
    assert wrapped["task_spec"] == adapted["task_spec"]
    assert wrapped["strategy_kind"] == adapted["strategy_kind"]
    assert wrapped["summary_payload"] == adapted["summary_payload"]
    assert wrapped["thread_id"] == "fallback-thread"
    assert wrapped["serialization_version"] == HARNESS_STATE_SERIALIZATION_VERSION
    assert wrapped["summary_boundary_version"] == SUMMARY_BOUNDARY_VERSION
    assert wrapped["bridge_boundary_version"] is None


def test_state_from_summary_reads_historical_contract_fields_after_freeze(tmp_path):
    summary = {
        "run_id": "run-historical",
        "workspace": "/tmp/workspace",
        "task": {"id": "task-historical", "task_kind": "analysis_review"},
        "strategy_kind": "analysis_review_v1",
        "artifacts": {"run_dir": str(tmp_path / "run")},
        "run_details": {
            "analysis_review_contract": {"mode": "bounded"},
            "focus_decision": _focus_decision(),
            "topic_ledger": [
                {"topic_id": "TOPIC-1", "resolution_status": "open"}
            ],
        },
    }

    wrapped = state_from_summary(summary, fallback_thread_id="fallback-thread")

    assert wrapped["thread_id"] == "fallback-thread"
    assert wrapped["analysis_review_contract"] == {"mode": "bounded"}
    assert wrapped["focus_decision"]["selected_focus_id"] == "focus-1"
    assert wrapped["topic_ledger"] == [
        {"topic_id": "TOPIC-1", "resolution_status": "open"}
    ]
    assert wrapped["summary_boundary_version"] == SUMMARY_BOUNDARY_VERSION
    assert wrapped["bridge_boundary_version"] is None
    assert wrapped["summary_payload"] == summary


class _FakeFocusGate:
    enabled = False


class _FakeTrustReview:
    execution_mode = "legacy_full_review"


class _FakeStopPolicy:
    def to_dict(self) -> dict[str, object]:
        return {"max_loops": 1}


class _FakeContract:
    mode = "bounded"
    focus_gate = _FakeFocusGate()
    trust_review = _FakeTrustReview()
    stop_policy = _FakeStopPolicy()

    def to_dict(self) -> dict[str, object]:
        return {"mode": "bounded"}


class _FakeTask:
    def to_dict(self) -> dict[str, object]:
        return {"id": "task-graph", "task_kind": "analysis_review"}


class _FakeRun:
    def __init__(self, payload: dict[str, object]) -> None:
        self.ok = True
        self.structured_output = payload


class _FakeRunner:
    def __init__(self) -> None:
        self.task = _FakeTask()
        self.agent_stages: list[dict[str, object]] = []
        self.validator_rounds: list[dict[str, object]] = []
        self.workspace_policy_checks: list[dict[str, object]] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.stage_counter = 0

    def _analysis_contract(self) -> _FakeContract:
        return _FakeContract()

    def _analysis_review_max_loops(self) -> int:
        return 1

    def _run_analysis_proposer_stage(self, *, contract, focus_decision):
        del contract, focus_decision
        self.stage_counter += 1
        payload = {"summary": "candidate analysis", "recommendations": [{"title": "A"}]}
        self.agent_stages.append(
            {
                "role_name": "proposer",
                "stage_index": self.stage_counter,
                "ok": True,
                "structured_output": payload,
                "stdout_path": "run/proposer.md",
                "output_path": "run/proposer.json",
                "raw_output_path": "run/proposer.raw.json",
                "normalized_output_path": "run/proposer.json",
            }
        )
        return _FakeRun(payload)

    def _run_validator_round(self, round_index: int):
        self.validator_rounds.append({"round_index": round_index, "results": []})
        return []

    def _run_analysis_critic_stage(self, *, contract, prior_output, validation_runs):
        del contract, prior_output, validation_runs
        self.stage_counter += 1
        payload = {
            "verdict": "accept",
            "issues": [],
            "recommendation_reviews": [{"recommendation_index": 1, "verdict": "accept"}],
            "grounding_score": 0.9,
            "actionability_score": 0.9,
            "scope_compliance_score": 0.9,
        }
        self.agent_stages.append(
            {
                "role_name": "critic",
                "stage_index": self.stage_counter,
                "ok": True,
                "structured_output": payload,
                "stdout_path": "run/critic.md",
                "output_path": "run/critic.json",
                "raw_output_path": "run/critic.raw.json",
                "normalized_output_path": "run/critic.json",
            }
        )
        return _FakeRun(payload)

    def _ingest_review_payload(self, review_payload, *, round_index, role_name, reviser_output):
        del review_payload, round_index, role_name, reviser_output
        return None

    def _analysis_needs_revision(self, review_payload: dict[str, object], revisions_completed: int) -> bool:
        del review_payload, revisions_completed
        return False

    def _classify_validator_verdict(self, results) -> str:
        del results
        return "not_configured"

    def _analysis_content_verdict(
        self,
        review_payload,
        *,
        final_analysis_payload,
        revisions_completed,
        max_loops,
    ) -> str:
        del review_payload, final_analysis_payload, revisions_completed, max_loops
        return "accepted"

    def _build_analysis_review_status(
        self,
        *,
        final_analysis_payload,
        final_review_payload,
        content_verdict,
    ) -> dict[str, object]:
        del final_analysis_payload, final_review_payload, content_verdict
        return {"mode": "bounded"}

    def _analysis_final_summary(
        self,
        review_payload,
        *,
        final_analysis_payload,
        content_verdict,
        revisions_completed,
        max_loops,
        validator_verdict,
    ) -> str:
        del (
            review_payload,
            final_analysis_payload,
            content_verdict,
            revisions_completed,
            max_loops,
            validator_verdict,
        )
        return "graph-owned success"

    def _combine_run_verdict(self, content_verdict: str, validator_verdict: str) -> str:
        del validator_verdict
        return content_verdict

    def _serialized_issue_ledger(self) -> list[dict[str, object]]:
        return []

    def _serialized_topic_ledger(self) -> list[dict[str, object]]:
        return []

    def _recommendation_reviews(self, review_payload: dict[str, object]) -> list[dict[str, object]]:
        return list(review_payload.get("recommendation_reviews") or [])

    def _accepted_recommendation_reviews(
        self, review_payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return list(review_payload.get("recommendation_reviews") or [])


def test_analysis_review_v1_graph_owned_success_carries_native_state(monkeypatch):
    monkeypatch.setattr(
        "anvil.harness.subgraphs.analysis_review_v1._build_graph_owned_runner",
        lambda state: _FakeRunner(),
    )
    monkeypatch.setattr(
        "anvil.harness.subgraphs._bridge.summary_read_adapter_v1",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("graph-owned path must not rehydrate via summary_read_adapter_v1")
        ),
    )

    state = {
        "analysis_review_execution_mode": "graph_owned",
        "analysis_review_runtime": {},
        "warnings": [],
        "errors": [],
        "summary_payload": {},
    }

    result = asyncio.run(analysis_review_v1_subgraph(state))

    assert result["run_verdict"] == "accepted"
    assert result.get("bridge_boundary_version") is None
    assert result["summary_payload"] == {}
    assert "bridge_boundary_version" not in result["summary_payload"]
    assert result["analysis_review_contract"] == {"mode": "bounded"}
    assert result["analysis_review_runtime"]["transition_reason"] == "stop_policy_satisfied"
    assert result["drafts"][0]["draft_id"] == "draft-proposer"
    assert result["drafts"][0]["review_state"] == "evaluated"
    assert result["drafts"][0]["issue_counts"]["accepted_recommendations"] == 1
