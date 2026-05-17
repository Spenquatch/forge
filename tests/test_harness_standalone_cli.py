from __future__ import annotations

import json
from pathlib import Path

import pytest

import anvil.harness.cli as harness_cli_module


class _FakeExecutor:
    summary_payload = {
        "verdict": "accepted",
        "verdicts": {
            "run_verdict": "accepted",
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {},
    }
    execute_error: Exception | None = None
    instances: list["_FakeExecutor"] = []

    def __init__(self, *, checkpoint: str = "memory", **kwargs):
        self.checkpoint = checkpoint
        self.kwargs = kwargs
        self.execute_calls: list[dict[str, object]] = []
        type(self).instances.append(self)

    async def execute(self, **kwargs):
        self.execute_calls.append(dict(kwargs))
        if self.execute_error is not None:
            raise self.execute_error
        return {"summary_payload": self.summary_payload}


class _UnexpectedRunner:
    def __init__(self, **kwargs):
        raise AssertionError(
            "HarnessRunner should not be constructed when the standalone harness CLI routes through the graph."
        )


def test_harness_standalone_cli_returns_zero_for_accepted(monkeypatch) -> None:
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "verdict": "accepted",
        "verdicts": {
            "run_verdict": "accepted",
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {},
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    assert exit_code == 0


def test_harness_standalone_cli_uses_native_artifact_index_fallback(
    monkeypatch, capsys
) -> None:
    class _NativeStateExecutor:
        def __init__(self, *, checkpoint: str = "memory", **kwargs):
            self.checkpoint = checkpoint
            self.kwargs = kwargs

        async def execute(self, **kwargs):
            return {
                "run_verdict": "accepted",
                "content_verdict": "accepted",
                "validator_verdict": "pass",
                "policy_verdict": "pass",
                "config_verdict": "pass",
                "artifact_index": {
                    "run_dir": {"path": "/tmp/run"},
                    "report_md": {"path": "/tmp/run/REPORT.md"},
                    "summary_json": {"path": "/tmp/run/summary.json"},
                    "final_answer_md": {"path": "/tmp/run/FINAL_ANSWER.md"},
                },
            }

    monkeypatch.setattr(
        harness_cli_module, "HarnessLangGraphExecutor", _NativeStateExecutor
    )
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_verdict=accepted" in captured.out
    assert "final_answer=/tmp/run/FINAL_ANSWER.md" in captured.out


def test_harness_standalone_cli_returns_nonzero_for_harness_error(monkeypatch) -> None:
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "verdict": "harness_error",
        "verdicts": {
            "run_verdict": "harness_error",
            "content_verdict": "harness_error",
            "validator_verdict": "not_configured",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {},
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    assert exit_code == 1


def test_harness_standalone_cli_prints_planning_surface(
    monkeypatch, capsys
) -> None:
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "terminal_status": "success",
        "stop_reason": "",
        "verdict": "success",
        "verdicts": {
            "run_verdict": "success",
            "content_verdict": "success",
            "validator_verdict": "not_applicable",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "strategy": {"runtime_target": "planning_v1"},
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "plan_md": "/tmp/run/PLAN.md",
            "plan_json": "/tmp/run/plan.json",
        },
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "terminal_status=success" in captured.out
    assert "plan=/tmp/run/PLAN.md" in captured.out


def test_harness_standalone_cli_returns_nonzero_for_planning_failed(
    monkeypatch,
) -> None:
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "terminal_status": "failed",
        "stop_reason": "rubric_failed",
        "verdict": "failed",
        "verdicts": {
            "run_verdict": "failed",
            "content_verdict": "failed",
            "validator_verdict": "not_applicable",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "strategy": {"runtime_target": "planning_v1"},
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
        },
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    assert exit_code == 1


def test_harness_standalone_cli_reports_missing_workspace_without_traceback(
    tmp_path: Path, capsys
) -> None:
    task_path = tmp_path / "task.yaml"
    strategy_path = tmp_path / "strategy.yaml"
    task_path.write_text(
        "id: qa-task\n"
        "task_kind: analysis_review\n"
        "objective: Check missing workspace handling.\n"
        "workspace_write_policy:\n"
        "  mode: forbid\n"
        "review_requirements:\n"
        "  require_evidence_per_recommendation: true\n"
        "  require_classification: true\n"
        "  require_priority: true\n"
        "  min_recommendations: 1\n",
        encoding="utf-8",
    )
    strategy_path.write_text(
        "name: qa-single-pass\n"
        "kind: single_pass\n"
        "roles:\n"
        "  solver:\n"
        "    provider: codex_gpt_5_4_mini\n",
        encoding="utf-8",
    )

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            str(task_path),
            "--strategy",
            str(strategy_path),
            "--workspace",
            str(tmp_path / "missing-workspace"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error=Workspace directory not found:" in captured.err
    assert "Traceback" not in captured.err


def test_harness_standalone_cli_reports_yaml_parse_errors_without_traceback(
    tmp_path: Path, capsys
) -> None:
    task_path = tmp_path / "task.yaml"
    strategy_path = tmp_path / "strategy.yaml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    task_path.write_text(
        "id: broken\n"
        "objective: [unterminated\n",
        encoding="utf-8",
    )
    strategy_path.write_text(
        "name: qa-single-pass\n"
        "kind: single_pass\n"
        "roles:\n"
        "  solver:\n"
        "    provider: codex_gpt_5_4_mini\n",
        encoding="utf-8",
    )

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            str(task_path),
            "--strategy",
            str(strategy_path),
            "--workspace",
            str(workspace),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error=Failed to parse" in captured.err
    assert "Traceback" not in captured.err


def _write_harness_specs(tmp_path: Path, *, task_kind: str) -> tuple[Path, Path, Path]:
    task_path = tmp_path / "task.yaml"
    strategy_path = tmp_path / "strategy.yaml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    if task_kind == "analysis_review":
        task_path.write_text(
            "id: qa-task\n"
            "task_kind: analysis_review\n"
            "objective: Verify CLI execution mode plumbing.\n"
            "workspace_write_policy:\n"
            "  mode: forbid\n"
            "review_requirements:\n"
            "  require_evidence_per_recommendation: true\n"
            "  require_classification: true\n"
            "  require_priority: true\n"
            "  min_recommendations: 1\n",
            encoding="utf-8",
        )
        strategy_path.write_text(
            "name: qa-analysis\n"
            "kind: analysis_review_v1\n"
            "roles:\n"
            "  solver:\n"
            "    provider: codex_gpt_5_4_mini\n",
            encoding="utf-8",
        )
    else:
        task_path.write_text(
            "id: qa-task\n"
            "task_kind: patch\n"
            "objective: Verify non-analysis_review CLI stability.\n"
            "instructions:\n"
            "  - Keep behavior stable.\n",
            encoding="utf-8",
        )
        strategy_path.write_text(
            "name: qa-single-pass\n"
            "kind: single_pass\n"
            "roles:\n"
            "  solver:\n"
            "    provider: codex_gpt_5_4_mini\n",
            encoding="utf-8",
        )

    return task_path, strategy_path, workspace


@pytest.mark.parametrize("checkpoint", ["memory", "sqlite"])
@pytest.mark.parametrize("execution_mode", ["legacy_bridge", "graph_owned"])
def test_harness_standalone_cli_accepts_analysis_review_execution_mode_via_executor(
    monkeypatch, tmp_path: Path, checkpoint: str, execution_mode: str
) -> None:
    task_path, strategy_path, workspace = _write_harness_specs(
        tmp_path, task_kind="analysis_review"
    )
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = None
    _FakeExecutor.summary_payload = {
        "verdict": "accepted",
        "verdicts": {
            "run_verdict": "accepted",
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {},
    }
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            str(task_path),
            "--strategy",
            str(strategy_path),
            "--workspace",
            str(workspace),
            "--checkpoint",
            checkpoint,
            "--analysis-review-execution-mode",
            execution_mode,
        ]
    )

    assert exit_code == 0
    executor = _FakeExecutor.instances[-1]
    assert executor.checkpoint == checkpoint
    assert executor.execute_calls == [
        {
            "task_path": str(task_path),
            "strategy_path": str(strategy_path),
            "workspace": str(workspace),
            "out_root": ".forge-harness-runs",
            "config_path": "config/models.yaml",
            "thread_id": None,
            "auto_fit_strategy": True,
            "analysis_review_execution_mode": execution_mode,
        }
    ]


@pytest.mark.parametrize("checkpoint", ["memory", "sqlite"])
@pytest.mark.parametrize("execution_mode", ["legacy_bridge", "graph_owned"])
def test_harness_standalone_cli_tolerates_execution_mode_for_non_analysis_review_tasks(
    monkeypatch, tmp_path: Path, checkpoint: str, execution_mode: str
) -> None:
    task_path, strategy_path, workspace = _write_harness_specs(
        tmp_path, task_kind="patch"
    )
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = None
    _FakeExecutor.summary_payload = {
        "verdict": "accepted",
        "verdicts": {
            "run_verdict": "accepted",
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {},
    }
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            str(task_path),
            "--strategy",
            str(strategy_path),
            "--workspace",
            str(workspace),
            "--checkpoint",
            checkpoint,
            "--analysis-review-execution-mode",
            execution_mode,
        ]
    )

    assert exit_code == 0
    executor = _FakeExecutor.instances[-1]
    assert executor.checkpoint == checkpoint
    assert executor.execute_calls == [
        {
            "task_path": str(task_path),
            "strategy_path": str(strategy_path),
            "workspace": str(workspace),
            "out_root": ".forge-harness-runs",
            "config_path": "config/models.yaml",
            "thread_id": None,
            "auto_fit_strategy": True,
            "analysis_review_execution_mode": execution_mode,
        }
    ]


def test_harness_standalone_cli_prints_planning_success(
    monkeypatch, capsys
) -> None:
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = None
    _FakeExecutor.summary_payload = {
        "terminal_status": "success",
        "stop_reason": "",
        "verdict": "success",
        "verdicts": {
            "run_verdict": "success",
            "content_verdict": "success",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "plan_md": "/tmp/run/PLAN.md",
            "plan_json": "/tmp/run/plan.json",
        },
    }
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "terminal_status=success" in captured.out
    assert "plan=/tmp/run/PLAN.md" in captured.out
    assert "plan_json=/tmp/run/plan.json" in captured.out


def test_harness_standalone_cli_json_returns_planning_payload(
    monkeypatch, capsys
) -> None:
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = None
    _FakeExecutor.summary_payload = {
        "terminal_status": "clarification_needed",
        "stop_reason": "Need repository scope clarification.",
        "clarification_requests": ["Which submodule owns the compiler wedge?"],
        "verdict": "clarification_needed",
        "verdicts": {
            "run_verdict": "clarification_needed",
            "content_verdict": "clarification_needed",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
        },
    }
    monkeypatch.setattr(harness_cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            "task.yaml",
            "--strategy",
            "strategy.yaml",
            "--workspace",
            "/tmp/workspace",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["terminal_status"] == "clarification_needed"
    assert payload["clarification_requests"] == [
        "Which submodule owns the compiler wedge?"
    ]
