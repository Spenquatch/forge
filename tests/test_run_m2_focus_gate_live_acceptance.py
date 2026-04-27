from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_m2_focus_gate_live_acceptance.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "run_m2_focus_gate_live_acceptance",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script_module()


def _write_structured(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _manifest_payload(workspace: Path, *, out_root: str = ".forge-harness-runs-live"):
    return {
        "task": SCRIPT.EXPECTED_TASK,
        "workspace": str(workspace),
        "out_root": out_root,
        "strategies": dict(SCRIPT.EXPECTED_STRATEGIES),
    }


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _create_valid_run_dir(tmp_path: Path, workspace: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "run"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"

    summary = {
        "focus_decision": {
            "gate_path": "adjudicate",
            "decision_state": "selected",
        },
        "agent_stages": [
            {"role_name": "focus_gate"},
            {"role_name": "proposer"},
            {"role_name": "critic"},
        ],
    }
    _write_structured(summary_path, summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Report\n", encoding="utf-8")

    focus_payload = {
        "gate_path": "adjudicate",
        "decision_state": "selected",
    }
    proposer_payload = {"primary_seam": {"paths": ["src/main.py", "src/lib.py"]}}

    _write_structured(run_dir / "artifacts/01_focus_gate/structured_output.raw.json", focus_payload)
    _write_structured(
        run_dir / "artifacts/01_focus_gate/structured_output.normalized.json",
        focus_payload,
    )
    _write_structured(
        run_dir / "artifacts/01_focus_gate/run.envelope.json",
        {"structured_output": focus_payload},
    )
    _write_structured(
        run_dir / "artifacts/02_proposer/structured_output.raw.json",
        proposer_payload,
    )
    _write_structured(
        run_dir / "artifacts/02_proposer/structured_output.normalized.json",
        proposer_payload,
    )
    _write_structured(
        run_dir / "artifacts/02_proposer/run.envelope.json",
        {"structured_output": proposer_payload},
    )
    return summary_path, report_path


def test_load_manifest_config_resolves_relative_out_root_against_repo_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "m2_focus_gate_local.yaml"
    _write_manifest(manifest_path, _manifest_payload(workspace))

    manifest = SCRIPT.load_manifest_config(manifest_path)

    assert manifest.task == (REPO_ROOT / SCRIPT.EXPECTED_TASK).resolve(strict=False)
    assert manifest.strategies["bounded"] == (
        REPO_ROOT / SCRIPT.EXPECTED_STRATEGIES["bounded"]
    ).resolve(strict=False)
    assert manifest.strategies["trust"] == (
        REPO_ROOT / SCRIPT.EXPECTED_STRATEGIES["trust"]
    ).resolve(strict=False)
    assert manifest.workspace == workspace.resolve(strict=False)
    assert manifest.out_root == (REPO_ROOT / ".forge-harness-runs-live").resolve(
        strict=False
    )


def test_resolve_runtime_paths_honors_cli_override_precedence(tmp_path: Path) -> None:
    manifest_workspace = tmp_path / "manifest-workspace"
    override_workspace = tmp_path / "override-workspace"
    manifest_workspace.mkdir()
    override_workspace.mkdir()
    manifest = SCRIPT.ManifestConfig(
        task=(REPO_ROOT / SCRIPT.EXPECTED_TASK).resolve(strict=False),
        workspace=manifest_workspace,
        out_root=(REPO_ROOT / ".forge-harness-runs-live").resolve(strict=False),
        strategies={
            name: (REPO_ROOT / path).resolve(strict=False)
            for name, path in SCRIPT.EXPECTED_STRATEGIES.items()
        },
    )

    workspace, out_root = SCRIPT.resolve_runtime_paths(
        manifest,
        workspace_override=str(override_workspace),
        out_root_override="custom-live-runs",
    )

    assert workspace == override_workspace.resolve(strict=False)
    assert out_root == (REPO_ROOT / "custom-live-runs").resolve(strict=False)


@pytest.mark.parametrize(
    ("field_name", "payload_mutator", "message"),
    [
        (
            "task",
            lambda payload: payload.__setitem__(
                "task",
                "examples/harness/tasks/another_task.yaml",
            ),
            "task must be exactly",
        ),
        (
            "strategies.bounded",
            lambda payload: payload["strategies"].__setitem__(
                "bounded",
                "examples/harness/strategies/other_bounded.yaml",
            ),
            "strategies.bounded must be exactly",
        ),
        (
            "strategies.trust",
            lambda payload: payload["strategies"].__setitem__(
                "trust",
                "examples/harness/strategies/other_trust.yaml",
            ),
            "strategies.trust must be exactly",
        ),
    ],
)
def test_load_manifest_config_rejects_mutated_frozen_paths(
    tmp_path: Path,
    field_name: str,
    payload_mutator,
    message: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "m2_focus_gate_local.yaml"
    payload = _manifest_payload(workspace)
    payload_mutator(payload)
    _write_manifest(manifest_path, payload)

    with pytest.raises(ValueError, match=message):
        SCRIPT.load_manifest_config(manifest_path)


@pytest.mark.parametrize(
    ("workspace_value", "message"),
    [
        ("relative/workspace", "workspace must be an absolute path."),
        ("/definitely/missing/workspace", "workspace must point to an existing directory."),
    ],
)
def test_load_manifest_config_rejects_invalid_workspace(
    tmp_path: Path,
    workspace_value: str,
    message: str,
) -> None:
    manifest_path = tmp_path / "m2_focus_gate_local.yaml"
    payload = _manifest_payload(tmp_path)
    payload["workspace"] = workspace_value
    _write_manifest(manifest_path, payload)

    with pytest.raises(ValueError, match=message):
        SCRIPT.load_manifest_config(manifest_path)


@pytest.mark.parametrize(
    ("stdout", "message"),
    [
        ("report=/tmp/report.md\n", "summary=..."),
        ("summary=/tmp/summary.json\n", "report=..."),
    ],
)
def test_parse_harness_run_output_requires_summary_and_report(
    stdout: str,
    message: str,
) -> None:
    with pytest.raises(SCRIPT.AcceptanceError, match=message):
        SCRIPT.parse_harness_run_output(stdout)


def test_run_acceptance_case_fails_on_non_zero_exit(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 2, stdout="", stderr="boom")

    monkeypatch.setattr(SCRIPT.subprocess, "run", _fake_run)
    result = SCRIPT.run_acceptance_case(
        case_name="bounded",
        strategy_path=(REPO_ROOT / SCRIPT.EXPECTED_STRATEGIES["bounded"]).resolve(strict=False),
        task_path=(REPO_ROOT / SCRIPT.EXPECTED_TASK).resolve(strict=False),
        workspace=workspace,
        out_root=tmp_path / "out",
    )

    assert result.verdict == "FAIL"
    assert result.summary == ""
    assert result.report == ""


def test_run_acceptance_case_uses_sys_executable_and_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)

    def _fake_run(command, cwd, capture_output, text, check):
        assert command[0] == sys.executable
        assert command[1:4] == ["-m", "anvil.cli", "harness-run"]
        assert cwd == REPO_ROOT
        assert capture_output is True
        assert text is True
        assert check is False
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"summary={summary_path}\nreport={report_path}\n",
            stderr="",
        )

    monkeypatch.setattr(SCRIPT.subprocess, "run", _fake_run)
    result = SCRIPT.run_acceptance_case(
        case_name="trust",
        strategy_path=(REPO_ROOT / SCRIPT.EXPECTED_STRATEGIES["trust"]).resolve(strict=False),
        task_path=(REPO_ROOT / SCRIPT.EXPECTED_TASK).resolve(strict=False),
        workspace=workspace,
        out_root=tmp_path / "out",
    )

    assert result.verdict == "PASS"
    assert result.summary == str(summary_path)
    assert result.report == str(report_path)


def test_validate_acceptance_run_rejects_missing_proposer(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["agent_stages"] = [{"role_name": "focus_gate"}, {"role_name": "critic"}]
    _write_structured(summary_path, summary)

    with pytest.raises(SCRIPT.AcceptanceError, match="include proposer"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
        )


def test_validate_acceptance_run_rejects_missing_downstream_review_role(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["agent_stages"] = [{"role_name": "focus_gate"}, {"role_name": "proposer"}]
    _write_structured(summary_path, summary)

    with pytest.raises(SCRIPT.AcceptanceError, match="downstream review role"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
        )


def test_validate_acceptance_run_rejects_focus_gate_failure_details(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["failure_details"] = {"stage": "focus_gate"}
    _write_structured(summary_path, summary)

    with pytest.raises(SCRIPT.AcceptanceError, match="focus_gate failure"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
        )


def test_validate_acceptance_run_rejects_selected_seam_drift(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["agent_stages"].append(
        {
            "role_name": "proposer",
            "failure_kind": "semantic_validation_error",
            "semantic_validation_errors": [SCRIPT.SELECTED_SEAM_DRIFT_TEXT],
        }
    )
    _write_structured(summary_path, summary)

    with pytest.raises(SCRIPT.AcceptanceError, match="selected-seam drift"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
        )


def test_validate_acceptance_run_rejects_missing_required_artifact(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)
    (summary_path.parent / "artifacts/02_proposer/run.envelope.json").unlink()

    with pytest.raises(SCRIPT.AcceptanceError, match="required artifact is missing"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
        )


def test_validate_acceptance_run_rejects_proposer_seam_basis_mismatch(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_valid_run_dir(tmp_path, workspace)
    mismatch_payload = {"primary_seam": {"paths": ["src/other.py"]}}
    _write_structured(
        summary_path.parent / "artifacts/02_proposer/structured_output.normalized.json",
        mismatch_payload,
    )

    with pytest.raises(SCRIPT.AcceptanceError, match="raw and normalized primary_seam.paths do not match"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
        )
