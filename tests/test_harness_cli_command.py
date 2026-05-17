from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import anvil.cli as cli_module


class _FakeExecutor:
    summary_payload = {
        "verdict": "accepted",
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "final_answer_md": "/tmp/run/FINAL_ANSWER.md",
        },
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
            "HarnessRunner should not be constructed when harness-run routes through the graph."
        )


def test_harness_run_cli_dispatch(monkeypatch, capsys):
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "verdict": "accepted",
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "final_answer_md": "/tmp/run/FINAL_ANSWER.md",
        },
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)
    asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )
    captured = capsys.readouterr()
    assert "verdict=accepted" in captured.out
    assert "final_answer=/tmp/run/FINAL_ANSWER.md" in captured.out


def test_harness_run_cli_dispatches_native_artifact_index_fallback(monkeypatch, capsys):
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

    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _NativeStateExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)
    asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )

    captured = capsys.readouterr()
    assert "verdict=accepted" in captured.out
    assert "final_answer=/tmp/run/FINAL_ANSWER.md" in captured.out


def test_harness_run_cli_reports_runtime_dependency_errors(monkeypatch, capsys):
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = RuntimeError(
        "PyYAML is required to load Forge YAML config files."
    )
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)
    asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )
    captured = capsys.readouterr()
    assert "❌ HARNESS RUN FAILED: PyYAML is required" in captured.out


def test_harness_run_cli_dispatch_partial_answer(monkeypatch, capsys):
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "verdict": "accepted_partial",
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "partial_answer_md": "/tmp/run/PARTIAL_ANSWER.md",
        },
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)
    asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )
    captured = capsys.readouterr()
    assert "verdict=accepted_partial" in captured.out
    assert "partial_answer=/tmp/run/PARTIAL_ANSWER.md" in captured.out


def test_harness_run_cli_returns_nonzero_for_failed_run_verdict(monkeypatch):
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
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
        },
    }
    _FakeExecutor.execute_error = None
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )

    assert exit_code == 1


def test_harness_run_cli_prints_planning_surface(monkeypatch, capsys):
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
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "terminal_status=success" in captured.out
    assert "plan=/tmp/run/PLAN.md" in captured.out
    assert "plan_json=/tmp/run/plan.json" in captured.out


def test_harness_run_cli_returns_nonzero_for_planning_clarification(monkeypatch):
    _FakeExecutor.instances.clear()
    _FakeExecutor.summary_payload = {
        "terminal_status": "clarification_needed",
        "stop_reason": "needs_scope",
        "clarification_requests": ["Which seam is in scope?"],
        "verdict": "clarification_needed",
        "verdicts": {
            "run_verdict": "clarification_needed",
            "content_verdict": "clarification_needed",
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
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )

    assert exit_code == 1


def test_harness_run_cli_reports_missing_task_file_without_traceback(
    tmp_path: Path, capsys
) -> None:
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        "name: qa-single-pass\n"
        "kind: single_pass\n"
        "roles:\n"
        "  solver:\n"
        "    provider: codex_gpt_5_4_mini\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                str(tmp_path / "missing-task.yaml"),
                "--strategy",
                str(strategy_path),
                "--workspace",
                str(workspace),
            ]
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "❌ HARNESS RUN FAILED: Task spec file not found:" in captured.out
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
def test_harness_run_cli_accepts_analysis_review_execution_mode_via_executor(
    monkeypatch, tmp_path: Path, checkpoint: str, execution_mode: str
) -> None:
    task_path, strategy_path, workspace = _write_harness_specs(
        tmp_path, task_kind="analysis_review"
    )
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = None
    _FakeExecutor.summary_payload = {
        "verdict": "accepted",
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "final_answer_md": "/tmp/run/FINAL_ANSWER.md",
        },
    }
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
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
def test_harness_run_cli_tolerates_execution_mode_for_non_analysis_review_tasks(
    monkeypatch, tmp_path: Path, checkpoint: str, execution_mode: str
) -> None:
    task_path, strategy_path, workspace = _write_harness_specs(
        tmp_path, task_kind="patch"
    )
    _FakeExecutor.instances.clear()
    _FakeExecutor.execute_error = None
    _FakeExecutor.summary_payload = {
        "verdict": "accepted",
        "artifacts": {
            "run_dir": "/tmp/run",
            "report_md": "/tmp/run/REPORT.md",
            "summary_json": "/tmp/run/summary.json",
            "final_answer_md": "/tmp/run/FINAL_ANSWER.md",
        },
    }
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
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


def test_harness_run_cli_prints_planning_success(monkeypatch, capsys) -> None:
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
            "final_artifact": "/tmp/run/PLAN.md",
        },
    }
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
            ]
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "terminal_status=success" in captured.out
    assert "plan=/tmp/run/PLAN.md" in captured.out
    assert "plan_json=/tmp/run/plan.json" in captured.out


def test_harness_run_cli_json_returns_planning_payload(monkeypatch, capsys) -> None:
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
    monkeypatch.setattr(cli_module, "HarnessLangGraphExecutor", _FakeExecutor)
    monkeypatch.setattr(cli_module, "HarnessRunner", _UnexpectedRunner)

    exit_code = asyncio.run(
        cli_module.main_async(
            [
                "harness-run",
                "--task",
                "task.yaml",
                "--strategy",
                "strategy.yaml",
                "--workspace",
                "/tmp/workspace",
                "--json",
            ]
        )
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["terminal_status"] == "clarification_needed"
    assert payload["clarification_requests"] == [
        "Which submodule owns the compiler wedge?"
    ]
