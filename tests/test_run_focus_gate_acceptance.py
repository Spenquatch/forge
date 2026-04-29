from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_focus_gate_acceptance.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "run_focus_gate_acceptance",
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


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _scenario_payload(
    *,
    name: str,
    strategy: str,
    task: str | None = None,
    expected_gate_path: str = "adjudicate",
    expected_focus_type: str = "seam",
    expected_decision_state: str = "selected",
    expect_proposer_artifacts: bool = True,
    expect_downstream_bridge: bool = True,
    expected_warning_substrings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        **({"task": task} if task else {}),
        "strategy": strategy,
        "expected_gate_path": expected_gate_path,
        "expected_focus_type": expected_focus_type,
        "expected_decision_state": expected_decision_state,
        "expect_proposer_artifacts": expect_proposer_artifacts,
        "expect_downstream_bridge": expect_downstream_bridge,
        "expected_warning_substrings": expected_warning_substrings or [],
    }


def _manifest_payload(
    workspace: Path,
    *,
    task: str | None = None,
    scenarios: list[dict[str, Any]] | None = None,
    out_root: str = ".forge-harness-runs-live",
) -> dict[str, Any]:
    return {
        "task": task or SCRIPT.EXAMPLE_TASK_PATH,
        "workspace": str(workspace),
        "out_root": out_root,
        "scenarios": scenarios
        or [
            _scenario_payload(
                name="bounded",
                strategy=SCRIPT.EXAMPLE_STRATEGIES["bounded"],
            )
        ],
    }


def _legacy_manifest_payload(
    workspace: Path,
    *,
    task: str | None = None,
    out_root: str = ".forge-harness-runs-live",
) -> dict[str, Any]:
    return {
        "task": task or SCRIPT.EXAMPLE_TASK_PATH,
        "workspace": str(workspace),
        "out_root": out_root,
        "strategies": dict(SCRIPT.EXAMPLE_STRATEGIES),
    }


def _selected_focus_decision() -> dict[str, Any]:
    selected_paths = ["src/main.py", "src/lib.py"]
    seam_id = SCRIPT.canonical_seam_id_for_paths(selected_paths)
    return {
        "gate_path": "adjudicate",
        "focus_type": "seam",
        "decision_state": "selected",
        "decision_basis": "request_only",
        "selected_focus_id": seam_id,
        "selected_focus_summary": "Main entrypoints stay coupled.",
        "selected_focus_paths": list(selected_paths),
        "confidence": 0.88,
        "confidence_band": "high",
        "files_hint_disposition": "helped",
        "checked_files": list(selected_paths),
        "candidates": [
            {
                "focus_id": seam_id,
                "focus_summary": "Main entrypoints stay coupled.",
                "candidate_paths": list(selected_paths),
                "why_candidate": "The task routes through these paths.",
                "evidence_refs": [],
                "score": 0.88,
            }
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [],
        "adapter_plan": {
            "primary_focus_id": seam_id,
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": seam_id,
            "downstream_primary_seam_paths": list(selected_paths),
            "adaptation_basis": "selected_focus_paths",
        },
    }


def _clarification_focus_decision() -> dict[str, Any]:
    return {
        "gate_path": "deliberate",
        "focus_type": "artifact",
        "decision_state": "clarification_requested",
        "decision_basis": "repo_probe",
        "selected_focus_id": None,
        "selected_focus_summary": None,
        "selected_focus_paths": [],
        "confidence": 0.41,
        "confidence_band": "low",
        "files_hint_disposition": "helped",
        "checked_files": ["src/main.py", "docs/spec.md"],
        "candidates": [
            {
                "focus_id": "artifact:src/main.py",
                "focus_summary": "Main runtime path",
                "candidate_paths": ["src/main.py"],
                "why_candidate": "This file is a plausible primary focus.",
                "evidence_refs": [],
                "score": 0.41,
            },
            {
                "focus_id": "artifact:docs/spec.md",
                "focus_summary": "Spec drift investigation",
                "candidate_paths": ["docs/spec.md"],
                "why_candidate": "The request also touches governing spec text.",
                "evidence_refs": [],
                "score": 0.4,
            },
        ],
        "question": {
            "prompt": SCRIPT.GENERIC_FOCUS_GATE_QUESTION_PROMPT,
            "options": ["artifact:src/main.py", "artifact:docs/spec.md"],
        },
        "warnings": [
            "Prior focus_gate_answer went stale: candidate set changed after repo probe.",
        ],
        "adapter_plan": {
            "primary_focus_id": None,
            "secondary_focus_ids": ["artifact:src/main.py", "artifact:docs/spec.md"],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        },
    }


def _create_selected_run_dir(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "selected-run"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    (tmp_path / "workspace/src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace/src/main.py").write_text("print('main')\n", encoding="utf-8")
    (tmp_path / "workspace/src/lib.py").write_text("print('lib')\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Report\n", encoding="utf-8")

    focus_decision = _selected_focus_decision()
    _write_structured(
        summary_path,
        {
            "focus_decision": focus_decision,
            "agent_stages": [
                {
                    "role_name": "focus_gate",
                    "metadata": {
                        "focus_gate": {
                            "gate_path": "adjudicate",
                            "focus_type": "seam",
                            "decision_state": "selected",
                        }
                    },
                    "stdout_path": str(run_dir / "artifacts/01_focus_gate/stdout.txt"),
                },
                {
                    "role_name": "proposer",
                    "stdout_path": str(run_dir / "artifacts/02_proposer/stdout.txt"),
                },
                {
                    "role_name": "critic",
                    "stdout_path": str(run_dir / "artifacts/03_critic/stdout.txt"),
                },
            ],
            "warnings": [],
        },
    )

    proposer_payload = {
        "primary_seam": {
            "paths": ["src/main.py", "src/lib.py"],
        }
    }
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


def _create_clarification_run_dir(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "clarification-run"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    (tmp_path / "workspace/src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace/docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace/src/main.py").write_text("print('main')\n", encoding="utf-8")
    (tmp_path / "workspace/docs/spec.md").write_text("# Spec\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Report\n", encoding="utf-8")

    focus_decision = _clarification_focus_decision()
    _write_structured(
        summary_path,
        {
            "focus_decision": focus_decision,
            "failure_details": {
                "stage": "focus_gate",
                "decision_state": "clarification_requested",
                "question": focus_decision["question"],
                "candidates": focus_decision["candidates"],
                "warnings": focus_decision["warnings"],
            },
            "agent_stages": [
                {
                    "role_name": "focus_gate_probe",
                    "stdout_path": str(
                        run_dir / "artifacts/01_focus_gate_probe/stdout.txt"
                    ),
                },
                {
                    "role_name": "focus_gate",
                    "metadata": {
                        "focus_gate": {
                            "gate_path": "deliberate",
                            "focus_type": "artifact",
                            "decision_state": "clarification_requested",
                        }
                    },
                    "warnings": list(focus_decision["warnings"]),
                    "stdout_path": str(run_dir / "artifacts/02_focus_gate/stdout.txt"),
                },
            ],
            "warnings": [],
        },
    )
    return summary_path, report_path


def test_load_manifest_config_accepts_scenario_driven_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "focus_gate_acceptance_local.yaml"
    _write_manifest(
        manifest_path,
        _manifest_payload(
            workspace,
            scenarios=[
                _scenario_payload(
                    name="deliberate-blocked",
                    strategy=SCRIPT.EXAMPLE_STRATEGIES["trust"],
                    expected_gate_path="deliberate",
                    expected_focus_type="artifact",
                    expected_decision_state="clarification_requested",
                    expect_proposer_artifacts=False,
                    expect_downstream_bridge=False,
                    expected_warning_substrings=["went stale"],
                )
            ],
        ),
    )

    manifest = SCRIPT.load_manifest_config(manifest_path)

    assert manifest.task == (REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(strict=False)
    assert manifest.workspace == workspace.resolve(strict=False)
    assert manifest.out_root == (REPO_ROOT / ".forge-harness-runs-live").resolve(
        strict=False
    )
    assert manifest.scenarios == (
        SCRIPT.AcceptanceScenario(
            name="deliberate-blocked",
            task=None,
            strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["trust"]).resolve(
                strict=False
            ),
            expected_gate_path="deliberate",
            expected_focus_type="artifact",
            expected_decision_state="clarification_requested",
            expect_proposer_artifacts=False,
            expect_downstream_bridge=False,
            expected_warning_substrings=("went stale",),
        ),
    )


def test_load_manifest_config_supports_legacy_strategy_shorthand(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "m2_focus_gate_local.yaml"
    _write_manifest(manifest_path, _legacy_manifest_payload(workspace))

    manifest = SCRIPT.load_manifest_config(manifest_path)

    assert [scenario.name for scenario in manifest.scenarios] == ["bounded", "trust"]
    assert all(scenario.task is None for scenario in manifest.scenarios)
    assert all(scenario.expected_gate_path == "adjudicate" for scenario in manifest.scenarios)
    assert all(scenario.expected_focus_type == "seam" for scenario in manifest.scenarios)
    assert all(scenario.expected_decision_state == "selected" for scenario in manifest.scenarios)
    assert all(scenario.expect_proposer_artifacts for scenario in manifest.scenarios)
    assert all(scenario.expect_downstream_bridge for scenario in manifest.scenarios)


def test_resolve_runtime_paths_honors_cli_override_precedence(tmp_path: Path) -> None:
    manifest_workspace = tmp_path / "manifest-workspace"
    override_workspace = tmp_path / "override-workspace"
    manifest_workspace.mkdir()
    override_workspace.mkdir()
    manifest = SCRIPT.ManifestConfig(
        task=(REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(strict=False),
        workspace=manifest_workspace,
        out_root=(REPO_ROOT / ".forge-harness-runs-live").resolve(strict=False),
        scenarios=(
            SCRIPT.AcceptanceScenario(
                name="bounded",
                task=None,
                strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["bounded"]).resolve(
                    strict=False
                ),
                expected_gate_path="adjudicate",
                expected_focus_type="seam",
                expected_decision_state="selected",
                expect_proposer_artifacts=True,
                expect_downstream_bridge=True,
            ),
        ),
    )

    workspace, out_root = SCRIPT.resolve_runtime_paths(
        manifest,
        workspace_override=str(override_workspace),
        out_root_override="custom-live-runs",
    )

    assert workspace == override_workspace.resolve(strict=False)
    assert out_root == (REPO_ROOT / "custom-live-runs").resolve(strict=False)


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


def test_validate_acceptance_run_accepts_selected_bridge_and_proposer(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_selected_run_dir(tmp_path)

    SCRIPT.validate_acceptance_run(
        summary_path=summary_path,
        report_path=report_path,
        workspace=workspace,
        scenario=SCRIPT.AcceptanceScenario(
            name="bounded",
            strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["bounded"]).resolve(
                strict=False
            ),
            task=None,
            expected_gate_path="adjudicate",
            expected_focus_type="seam",
            expected_decision_state="selected",
            expect_proposer_artifacts=True,
            expect_downstream_bridge=True,
        ),
    )


def test_validate_acceptance_run_accepts_blocked_deliberate_without_proposer(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_clarification_run_dir(tmp_path)

    SCRIPT.validate_acceptance_run(
        summary_path=summary_path,
        report_path=report_path,
        workspace=workspace,
        scenario=SCRIPT.AcceptanceScenario(
            name="artifact-blocked",
            strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["trust"]).resolve(
                strict=False
            ),
            task=None,
            expected_gate_path="deliberate",
            expected_focus_type="artifact",
            expected_decision_state="clarification_requested",
            expect_proposer_artifacts=False,
            expect_downstream_bridge=False,
            expected_warning_substrings=("went stale",),
        ),
    )


def test_validate_acceptance_run_rejects_missing_expected_warning(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_clarification_run_dir(tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["focus_decision"]["warnings"] = []
    summary["failure_details"]["warnings"] = []
    summary["agent_stages"][1]["warnings"] = []
    _write_structured(summary_path, summary)

    with pytest.raises(SCRIPT.AcceptanceError, match="expected warning substring"):
        SCRIPT.validate_acceptance_run(
            summary_path=summary_path,
            report_path=report_path,
            workspace=workspace,
            scenario=SCRIPT.AcceptanceScenario(
                name="artifact-blocked",
                strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["trust"]).resolve(
                    strict=False
                ),
                task=None,
                expected_gate_path="deliberate",
                expected_focus_type="artifact",
                expected_decision_state="clarification_requested",
                expect_proposer_artifacts=False,
                expect_downstream_bridge=False,
                expected_warning_substrings=("went stale",),
            ),
        )


def test_run_acceptance_case_uses_sys_executable_and_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_selected_run_dir(tmp_path)
    scenario = SCRIPT.AcceptanceScenario(
        name="trust",
        task=(REPO_ROOT / "examples/harness/tasks/recommend_release_workflow_artifact_improvements.yaml").resolve(strict=False),
        strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["trust"]).resolve(strict=False),
        expected_gate_path="adjudicate",
        expected_focus_type="seam",
        expected_decision_state="selected",
        expect_proposer_artifacts=True,
        expect_downstream_bridge=True,
    )

    def _fake_run(command, cwd, capture_output, text, check):
        assert command[0] == sys.executable
        assert command[1:4] == ["-m", "anvil.cli", "harness-run"]
        assert cwd == REPO_ROOT
        assert capture_output is True
        assert text is True
        assert check is False
        assert command[command.index("--task") + 1] == str(scenario.task)
        assert command[command.index("--strategy") + 1] == str(scenario.strategy)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"summary={summary_path}\nreport={report_path}\n",
            stderr="",
        )

    monkeypatch.setattr(SCRIPT.subprocess, "run", _fake_run)
    result = SCRIPT.run_acceptance_case(
        scenario=scenario,
        task_path=(REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(strict=False),
        workspace=workspace,
        out_root=tmp_path / "out",
    )

    assert result.verdict == "PASS"
    assert result.summary == str(summary_path)
    assert result.report == str(report_path)


def test_run_acceptance_case_accepts_blocked_focus_gate_with_nonzero_exit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    summary_path, report_path = _create_clarification_run_dir(tmp_path)
    scenario = SCRIPT.AcceptanceScenario(
        name="artifact-blocked",
        task=None,
        strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["trust"]).resolve(strict=False),
        expected_gate_path="deliberate",
        expected_focus_type="artifact",
        expected_decision_state="clarification_requested",
        expect_proposer_artifacts=False,
        expect_downstream_bridge=False,
        expected_warning_substrings=("went stale",),
    )

    def _fake_run(command, cwd, capture_output, text, check):
        assert command[0] == sys.executable
        assert cwd == REPO_ROOT
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=f"summary={summary_path}\nreport={report_path}\n",
            stderr="blocked",
        )

    monkeypatch.setattr(SCRIPT.subprocess, "run", _fake_run)
    result = SCRIPT.run_acceptance_case(
        scenario=scenario,
        task_path=(REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(strict=False),
        workspace=workspace,
        out_root=tmp_path / "out",
    )

    assert result.verdict == "PASS"
    assert result.summary == str(summary_path)
    assert result.report == str(report_path)


def test_load_manifest_config_parses_scenario_task_overrides(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "focus_gate_acceptance_local.yaml"
    artifact_task = "examples/harness/tasks/recommend_release_workflow_artifact_improvements.yaml"
    _write_manifest(
        manifest_path,
        _manifest_payload(
            workspace,
            scenarios=[
                _scenario_payload(
                    name="artifact-bounded",
                    task=artifact_task,
                    strategy=SCRIPT.EXAMPLE_STRATEGIES["bounded"],
                    expected_focus_type="artifact",
                )
            ],
        ),
    )

    manifest = SCRIPT.load_manifest_config(manifest_path)

    assert manifest.task == (REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(strict=False)
    assert manifest.scenarios == (
        SCRIPT.AcceptanceScenario(
            name="artifact-bounded",
            task=(REPO_ROOT / artifact_task).resolve(strict=False),
            strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["bounded"]).resolve(
                strict=False
            ),
            expected_gate_path="adjudicate",
            expected_focus_type="artifact",
            expected_decision_state="selected",
            expect_proposer_artifacts=True,
            expect_downstream_bridge=True,
            expected_warning_substrings=(),
        ),
    )
