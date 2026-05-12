from __future__ import annotations

from pathlib import Path

import anvil.harness.cli as harness_cli_module


class _AcceptedRunner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self):
        return {
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
            "artifacts": {},
        }


def test_harness_standalone_cli_returns_zero_for_accepted(monkeypatch) -> None:
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _AcceptedRunner)

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


def test_harness_standalone_cli_returns_nonzero_for_harness_error(monkeypatch) -> None:
    monkeypatch.setattr(harness_cli_module, "HarnessRunner", _HarnessErrorRunner)

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
