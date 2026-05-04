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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


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


def _shard_manifest_payload(
    *,
    shard_name: str = "seam-adjudicate",
    scenarios: list[dict[str, Any]] | None = None,
    workspace_seed: str = "tests/fixtures/harness/m2_focus_gate_fixture_wiring/workspace",
    out_root: str = ".forge-harness-runs-live/m4-request-gate/shards",
) -> dict[str, Any]:
    return {
        "default_task": SCRIPT.EXAMPLE_TASK_PATH,
        "workspace_seed": workspace_seed,
        "out_root": out_root,
        "preflight_timeout_sec": 60,
        "shard_timeout_sec": 1800,
        "shards": [
            {
                "name": shard_name,
                "scenarios": scenarios
                or [
                    _scenario_payload(
                        name="bounded",
                        strategy=SCRIPT.EXAMPLE_STRATEGIES["bounded"],
                    )
                ],
            }
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


def _artifact_selected_focus_decision() -> dict[str, Any]:
    selected_path = ".github/workflows/codex-cli-release-watch.yml"
    artifact_id = SCRIPT.canonical_artifact_focus_id(selected_path)
    seam_id = SCRIPT.canonical_seam_id_for_paths([selected_path])
    return {
        "gate_path": "adjudicate",
        "focus_type": "artifact",
        "decision_state": "selected",
        "decision_basis": "request_only",
        "selected_focus_id": artifact_id,
        "selected_focus_summary": "The release workflow artifact is the chosen focus.",
        "selected_focus_paths": [selected_path],
        "confidence": 0.88,
        "confidence_band": "high",
        "files_hint_disposition": "helped",
        "checked_files": [selected_path],
        "candidates": [
            {
                "focus_id": artifact_id,
                "focus_summary": "Release workflow artifact.",
                "candidate_paths": [selected_path],
                "why_candidate": "The task explicitly narrows to the governing workflow.",
                "evidence_refs": [selected_path],
                "score": 0.88,
            }
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [],
        "adapter_plan": {
            "primary_focus_id": artifact_id,
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": seam_id,
            "downstream_primary_seam_paths": [selected_path],
            "adaptation_basis": "artifact_singleton",
        },
    }


def _blocked_focus_decision(
    *,
    focus_type: str,
    decision_state: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    checked_files = ["src/main.py", "docs/spec.md"]
    if focus_type == "artifact":
        candidate_ids = ["artifact:src/main.py", "artifact:docs/spec.md"]
    else:
        candidate_ids = [
            SCRIPT.canonical_seam_id_for_paths(["src/main.py"]),
            SCRIPT.canonical_seam_id_for_paths(["docs/spec.md"]),
        ]

    question = (
        {
            "prompt": SCRIPT.GENERIC_FOCUS_GATE_QUESTION_PROMPT,
            "options": list(candidate_ids),
        }
        if decision_state == "clarification_requested"
        else {"prompt": "", "options": []}
    )
    return {
        "gate_path": "deliberate",
        "focus_type": focus_type,
        "decision_state": decision_state,
        "decision_basis": "repo_probe",
        "selected_focus_id": None,
        "selected_focus_summary": None,
        "selected_focus_paths": [],
        "confidence": 0.41,
        "confidence_band": "low",
        "files_hint_disposition": "helped",
        "checked_files": list(checked_files),
        "candidates": [
            {
                "focus_id": candidate_ids[0],
                "focus_summary": "Main runtime path",
                "candidate_paths": ["src/main.py"],
                "why_candidate": "This file is a plausible primary focus.",
                "evidence_refs": [],
                "score": 0.41,
            },
            {
                "focus_id": candidate_ids[1],
                "focus_summary": "Spec drift investigation",
                "candidate_paths": ["docs/spec.md"],
                "why_candidate": "The request also touches governing spec text.",
                "evidence_refs": [],
                "score": 0.4,
            },
        ],
        "question": question,
        "warnings": list(warnings or []),
        "adapter_plan": {
            "primary_focus_id": None,
            "secondary_focus_ids": list(candidate_ids),
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        },
    }


def _acceptance_scenario(
    *,
    name: str,
    strategy_key: str,
    expected_gate_path: str,
    expected_focus_type: str,
    expected_decision_state: str,
    expect_proposer_artifacts: bool,
    expect_downstream_bridge: bool,
    expected_warning_substrings: tuple[str, ...] = (),
) -> Any:
    return SCRIPT.AcceptanceScenario(
        name=name,
        task=None,
        strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES[strategy_key]).resolve(
            strict=False
        ),
        expected_gate_path=expected_gate_path,
        expected_focus_type=expected_focus_type,
        expected_decision_state=expected_decision_state,
        expect_proposer_artifacts=expect_proposer_artifacts,
        expect_downstream_bridge=expect_downstream_bridge,
        expected_warning_substrings=expected_warning_substrings,
    )


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
    _write_json(
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

    proposer_payload = {"primary_seam": {"paths": ["src/main.py", "src/lib.py"]}}
    _write_json(
        run_dir / "artifacts/02_proposer/structured_output.raw.json",
        proposer_payload,
    )
    _write_json(
        run_dir / "artifacts/02_proposer/structured_output.normalized.json",
        proposer_payload,
    )
    _write_json(
        run_dir / "artifacts/02_proposer/run.envelope.json",
        {"structured_output": proposer_payload},
    )
    return summary_path, report_path


def _create_blocked_run_dir(
    tmp_path: Path,
    *,
    focus_type: str,
    decision_state: str,
    warnings: list[str] | None = None,
) -> tuple[Path, Path]:
    run_dir = tmp_path / "blocked-run"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    (tmp_path / "workspace/src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace/docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace/src/main.py").write_text("print('main')\n", encoding="utf-8")
    (tmp_path / "workspace/docs/spec.md").write_text("# Spec\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Report\n", encoding="utf-8")

    focus_decision = _blocked_focus_decision(
        focus_type=focus_type,
        decision_state=decision_state,
        warnings=warnings,
    )
    _write_json(
        summary_path,
        {
            "focus_decision": focus_decision,
            "failure_details": {
                "stage": "focus_gate",
                "decision_state": decision_state,
                "warnings": list(warnings or []),
            },
            "agent_stages": [
                {
                    "role_name": "focus_gate_probe",
                    "stdout_path": str(run_dir / "artifacts/01_focus_gate_probe/stdout.txt"),
                },
                {
                    "role_name": "focus_gate",
                    "metadata": {
                        "focus_gate": {
                            "gate_path": "deliberate",
                            "focus_type": focus_type,
                            "decision_state": decision_state,
                        }
                    },
                    "stdout_path": str(run_dir / "artifacts/02_focus_gate/stdout.txt"),
                },
            ],
            "warnings": [],
        },
    )
    return summary_path, report_path


def _create_artifact_selected_run_dir(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "artifact-run"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "REPORT.md"
    (tmp_path / "workspace/.github/workflows").mkdir(parents=True, exist_ok=True)
    workflow_path = tmp_path / "workspace/.github/workflows/codex-cli-release-watch.yml"
    workflow_path.write_text("name: release-watch\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Report\n", encoding="utf-8")

    focus_decision = _artifact_selected_focus_decision()
    _write_json(
        summary_path,
        {
            "focus_decision": focus_decision,
            "agent_stages": [
                {
                    "role_name": "focus_gate",
                    "metadata": {
                        "focus_gate": {
                            "gate_path": "adjudicate",
                            "focus_type": "artifact",
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
        "primary_seam": {"paths": [".github/workflows/codex-cli-release-watch.yml"]}
    }
    _write_json(
        run_dir / "artifacts/02_proposer/structured_output.raw.json",
        proposer_payload,
    )
    _write_json(
        run_dir / "artifacts/02_proposer/structured_output.normalized.json",
        proposer_payload,
    )
    _write_json(
        run_dir / "artifacts/02_proposer/run.envelope.json",
        {"structured_output": proposer_payload},
    )
    return summary_path, report_path


def _fake_which_factory(mapping: dict[str, str | None]):
    def _fake_which(binary: str) -> str | None:
        return mapping.get(binary)

    return _fake_which


def test_default_config_path_points_to_canonical_closeout_manifest() -> None:
    assert SCRIPT.DEFAULT_CONFIG_PATH == (
        REPO_ROOT / ".gstack/m4-request-gate/orch/focus_gate_acceptance.yaml"
    )
    assert SCRIPT.CANONICAL_TEMPLATE_PATH == (
        REPO_ROOT / "examples/harness/live_acceptance/focus_gate_acceptance.template.yaml"
    )


def test_load_manifest_config_accepts_shard_manifest() -> None:
    manifest = SCRIPT.load_manifest_config(SCRIPT.DEFAULT_CONFIG_PATH)

    assert isinstance(manifest, SCRIPT.ShardManifestConfig)
    assert manifest.default_task == (REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(
        strict=False
    )
    assert manifest.workspace_seed == (
        REPO_ROOT / "tests/fixtures/harness/m2_focus_gate_fixture_wiring/workspace"
    ).resolve(strict=False)
    assert [shard.name for shard in manifest.shards] == [
        "seam-adjudicate",
        "seam-deliberate",
        "artifact-adjudicate",
        "artifact-deliberate",
    ]


def test_load_manifest_config_supports_legacy_workspace_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest_path = tmp_path / "m2_focus_gate_local.yaml"
    _write_json(manifest_path, _legacy_manifest_payload(workspace))

    manifest = SCRIPT.load_manifest_config(manifest_path)

    assert isinstance(manifest, SCRIPT.LegacyManifestConfig)
    assert manifest.workspace == workspace.resolve(strict=False)
    assert [scenario.name for scenario in manifest.scenarios] == ["bounded", "trust"]


def test_preflight_rejects_local_strategy_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy_root = tmp_path / "strategies"
    local_strategy = strategy_root / "bad.local.yaml"
    _write_yaml(
        local_strategy,
        """
        name: bad-local
        kind: analysis_review_bounded_v1
        roles:
          proposer:
            provider: codex_gpt_5_4
        validators: []
        """,
    )
    manifest_path = tmp_path / "manifest.yaml"
    _write_json(
        manifest_path,
        _shard_manifest_payload(
            scenarios=[
                _scenario_payload(
                    name="bounded",
                    strategy=str(local_strategy),
                )
            ]
        ),
    )
    manifest = SCRIPT.load_manifest_config(manifest_path)
    monkeypatch.setattr(SCRIPT, "CANONICAL_STRATEGY_ROOT", strategy_root)
    monkeypatch.setattr(
        SCRIPT.shutil,
        "which",
        _fake_which_factory({"git": "/usr/bin/git", "codex": "/usr/bin/codex"}),
    )

    with pytest.raises(SCRIPT.AcceptanceError, match="local strategy overrides"):
        SCRIPT.preflight_shard_manifest(
            manifest,
            shard_name="seam-adjudicate",
            out_root=tmp_path / "out",
        )


def test_preflight_rejects_skip_git_repo_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy_root = tmp_path / "strategies"
    strategy = strategy_root / "bad.yaml"
    _write_yaml(
        strategy,
        """
name: bad
kind: analysis_review_bounded_v1
roles:
  proposer:
    provider: codex_gpt_5_4
    skip_git_repo_check: true
validators: []
        """,
    )
    manifest_path = tmp_path / "manifest.yaml"
    _write_json(
        manifest_path,
        _shard_manifest_payload(
            scenarios=[
                _scenario_payload(
                    name="bounded",
                    strategy=str(strategy),
                )
            ]
        ),
    )
    manifest = SCRIPT.load_manifest_config(manifest_path)
    monkeypatch.setattr(SCRIPT, "CANONICAL_STRATEGY_ROOT", strategy_root)
    monkeypatch.setattr(
        SCRIPT.shutil,
        "which",
        _fake_which_factory({"git": "/usr/bin/git", "codex": "/usr/bin/codex"}),
    )

    with pytest.raises(SCRIPT.AcceptanceError, match="skip_git_repo_check=true"):
        SCRIPT.preflight_shard_manifest(
            manifest,
            shard_name="seam-adjudicate",
            out_root=tmp_path / "out",
        )


def test_preflight_returns_provider_and_git_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = SCRIPT.load_manifest_config(SCRIPT.DEFAULT_CONFIG_PATH)
    monkeypatch.setattr(
        SCRIPT.shutil,
        "which",
        _fake_which_factory({"git": "/usr/bin/git", "codex": "/usr/bin/codex"}),
    )

    result = SCRIPT.preflight_shard_manifest(
        manifest,
        shard_name="seam-adjudicate",
        out_root=(REPO_ROOT / ".forge-harness-runs-live/test-preflight").resolve(
            strict=False
        ),
    )

    assert result["git_binary"] == "/usr/bin/git"
    assert result["shard"] == "seam-adjudicate"
    assert {check["provider"] for check in result["provider_checks"]} == {
        "codex_gpt_5_4",
        "codex_gpt_5_4_mini",
        "codex_gpt_5_2",
    }


def test_provision_git_workspace_creates_clean_git_repo() -> None:
    manifest = SCRIPT.load_manifest_config(SCRIPT.DEFAULT_CONFIG_PATH)

    provisioned = SCRIPT.provision_git_workspace(
        manifest,
        shard_name="seam-adjudicate",
        pass_id="test-pass",
    )

    assert provisioned.workspace.is_dir()
    assert provisioned.baseline_commit
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=provisioned.workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.returncode == 0
    assert status.stdout.strip() == ""


def test_prepare_shard_out_root_rejects_repo_head_change(tmp_path: Path) -> None:
    shard_root = tmp_path / "pass-1" / "seam-adjudicate"
    shard_root.mkdir(parents=True)
    _write_json(shard_root / "shard_result.json", {"repo_head": "old-head"})

    with pytest.raises(SCRIPT.AcceptanceError, match="different commit SHA"):
        SCRIPT._prepare_shard_out_root(
            out_root=tmp_path,
            pass_id="pass-1",
            shard_name="seam-adjudicate",
            repo_head="new-head",
        )


def test_run_acceptance_case_selected_seam_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary_path, report_path = _create_selected_run_dir(tmp_path)
    workspace = tmp_path / "workspace"
    scenario = _acceptance_scenario(
        name="bounded",
        strategy_key="bounded",
        expected_gate_path="adjudicate",
        expected_focus_type="seam",
        expected_decision_state="selected",
        expect_proposer_artifacts=True,
        expect_downstream_bridge=True,
    )

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            kwargs.get("args", args[0]),
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
        timeout_sec=30,
    )

    assert result.verdict == "PASS"
    assert result.returncode == 0


def test_run_acceptance_case_blocked_nonzero_exit_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary_path, report_path = _create_blocked_run_dir(
        tmp_path,
        focus_type="artifact",
        decision_state="clarification_requested",
        warnings=["Prior focus_gate_answer went stale: candidate set changed after repo probe."],
    )
    workspace = tmp_path / "workspace"
    scenario = SCRIPT.AcceptanceScenario(
        name="artifact-deliberate-ambiguity",
        task=None,
        strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["trust"]).resolve(strict=False),
        expected_gate_path="deliberate",
        expected_focus_type="artifact",
        expected_decision_state="clarification_requested",
        expect_proposer_artifacts=False,
        expect_downstream_bridge=False,
        expected_warning_substrings=("went stale",),
    )

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            kwargs.get("args", args[0]),
            1,
            stdout=f"summary={summary_path}\nreport={report_path}\n",
            stderr="",
        )

    monkeypatch.setattr(SCRIPT.subprocess, "run", _fake_run)

    result = SCRIPT.run_acceptance_case(
        scenario=scenario,
        task_path=(REPO_ROOT / SCRIPT.EXAMPLE_TASK_PATH).resolve(strict=False),
        workspace=workspace,
        out_root=tmp_path / "out",
        timeout_sec=30,
    )

    assert result.verdict == "PASS"
    assert result.returncode == 1


def test_run_acceptance_case_selected_artifact_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary_path, report_path = _create_artifact_selected_run_dir(tmp_path)
    workspace = tmp_path / "workspace"
    scenario = SCRIPT.AcceptanceScenario(
        name="artifact-bounded",
        task=None,
        strategy=(REPO_ROOT / SCRIPT.EXAMPLE_STRATEGIES["bounded"]).resolve(strict=False),
        expected_gate_path="adjudicate",
        expected_focus_type="artifact",
        expected_decision_state="selected",
        expect_proposer_artifacts=True,
        expect_downstream_bridge=True,
    )

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            kwargs.get("args", args[0]),
            0,
            stdout=f"summary={summary_path}\nreport={report_path}\n",
            stderr="",
        )

    monkeypatch.setattr(SCRIPT.subprocess, "run", _fake_run)

    result = SCRIPT.run_acceptance_case(
        scenario=scenario,
        task_path=(
            REPO_ROOT
            / "examples/harness/tasks/recommend_release_workflow_artifact_improvements.yaml"
        ).resolve(strict=False),
        workspace=workspace,
        out_root=tmp_path / "out",
        timeout_sec=30,
    )

    assert result.verdict == "PASS"


def test_main_shard_manifest_rejects_workspace_override() -> None:
    exit_code = SCRIPT.main(
        [
            "--config",
            str(SCRIPT.DEFAULT_CONFIG_PATH.relative_to(REPO_ROOT)),
            "--shard",
            "seam-adjudicate",
            "--pass-id",
            "pass-1",
            "--workspace",
            "/tmp/workspace",
        ]
    )

    assert exit_code == 1


def test_main_preflight_only_succeeds_with_stubbed_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SCRIPT,
        "preflight_shard_manifest",
        lambda manifest, shard_name, out_root: {
            "shard": shard_name,
            "git_binary": "/usr/bin/git",
            "provider_checks": [],
            "elapsed_sec": 0.01,
            "workspace_seed": str(manifest.workspace_seed),
            "out_root": str(out_root),
        },
    )

    exit_code = SCRIPT.main(
        [
            "--config",
            str(SCRIPT.DEFAULT_CONFIG_PATH.relative_to(REPO_ROOT)),
            "--shard",
            "seam-adjudicate",
            "--preflight-only",
        ]
    )

    assert exit_code == 0
