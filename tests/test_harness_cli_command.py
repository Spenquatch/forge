from __future__ import annotations

import asyncio

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
