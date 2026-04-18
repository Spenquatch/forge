from __future__ import annotations

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
