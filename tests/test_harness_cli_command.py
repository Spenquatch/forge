from __future__ import annotations

import asyncio
from pathlib import Path

import anvil.cli as cli_module


class _FakeRunner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self):
        return {
            "verdict": "accepted",
            "artifacts": {
                "run_dir": "/tmp/run",
                "report_md": "/tmp/run/REPORT.md",
                "summary_json": "/tmp/run/summary.json",
                "final_answer_md": "/tmp/run/FINAL_ANSWER.md",
            },
        }


class _FailingRunner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self):
        raise RuntimeError("PyYAML is required to load Forge YAML config files.")


def test_harness_run_cli_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "HarnessRunner", _FakeRunner)
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
    monkeypatch.setattr(cli_module, "HarnessRunner", _FailingRunner)
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



class _PartialRunner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self):
        return {
            "verdict": "accepted_partial",
            "artifacts": {
                "run_dir": "/tmp/run",
                "report_md": "/tmp/run/REPORT.md",
                "summary_json": "/tmp/run/summary.json",
                "partial_answer_md": "/tmp/run/PARTIAL_ANSWER.md",
            },
        }


def test_harness_run_cli_dispatch_partial_answer(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "HarnessRunner", _PartialRunner)
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


class _HarnessErrorRunner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self):
        return {
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


def test_harness_run_cli_returns_nonzero_for_failed_run_verdict(monkeypatch):
    monkeypatch.setattr(cli_module, "HarnessRunner", _HarnessErrorRunner)

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
