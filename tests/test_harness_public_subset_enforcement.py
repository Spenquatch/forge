from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

import anvil.cli as cli_module
import anvil.harness.cli as harness_cli_module
from anvil.harness.executor import HarnessLangGraphExecutor
from anvil.harness.files import load_structured_file
from anvil.harness.nodes.validator_preflight import validator_preflight_node
from anvil.harness.public_subset_validation import classify_public_strategy_surface
from anvil.harness.strategy_graph import (
    build_strategy_graph_spec,
    route_after_strategy_selection,
)
from anvil.harness.types import StrategyConfig

PUBLIC_SUBSET_ROOT = Path("examples/harness/public_subset")
COMPATIBILITY_ROOT = PUBLIC_SUBSET_ROOT / "compatibility"
NEGATIVE_ROOT = PUBLIC_SUBSET_ROOT / "negative"
PLANNING_FIXTURE = Path("examples/harness/strategies/deterministic_feature_planning_v1.yaml")

LEGACY_WARNING = (
    "Strategy kind analysis_review_v1 is deprecated and now resolves to "
    "analysis_review_bounded_v1."
)

NEGATIVE_CASES = (
    (
        "invalid_kind.yaml",
        "canonical public strategies must declare kind as one of: "
        "analysis_review_bounded_v1, analysis_review_trust_v1, "
        "deterministic_feature_planning_v1.",
    ),
    (
        "unknown_top_level_key.yaml",
        "canonical public strategies must not declare unsupported top-level key "
        "'unsupported_top_level_key'.",
    ),
    (
        "invalid_stage_family.yaml",
        "canonical public strategies must use only public stage families; "
        "unsupported role key 'navigator'.",
    ),
    (
        "runtime_owned_phase_inputs.yaml",
        "canonical public strategies must not declare runtime-owned field "
        "'phase_inputs'.",
    ),
    (
        "metadata_only_schema_version.yaml",
        "canonical public strategies must not declare metadata-only field "
        "'schema_version'.",
    ),
)


def _analysis_review_task_spec() -> dict[str, object]:
    return {
        "id": "public-subset-analysis-review",
        "task_kind": "analysis_review",
        "objective": "Verify bounded public strategy enforcement.",
        "workspace_write_policy": {"mode": "forbid"},
        "review_requirements": {
            "require_evidence_per_recommendation": True,
            "require_classification": True,
            "require_priority": True,
            "min_recommendations": 1,
        },
    }


def _planning_task_spec() -> dict[str, object]:
    return {
        "id": "public-subset-planning",
        "task_kind": "planning",
        "objective": "Verify internal planning fixture preservation.",
        "workspace_write_policy": {"mode": "forbid"},
        "acceptance": ["Emit a deterministic planning package."],
    }


def _preflight_state(
    task_spec: dict[str, object], strategy_spec: dict[str, object]
) -> dict[str, object]:
    return {
        "task_spec": task_spec,
        "strategy_spec": strategy_spec,
        "strategy_kind": str(strategy_spec.get("kind") or "single_pass"),
        "workspace_root": ".",
        "warnings": [],
        "errors": [],
        "auto_fit_strategy": True,
    }


def _write_invalid_public_specs(tmp_path: Path) -> tuple[Path, Path, Path]:
    task_path = tmp_path / "task.yaml"
    strategy_path = tmp_path / "strategy.yaml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    task_path.write_text(
        "id: invalid-public\n"
        "task_kind: analysis_review\n"
        "objective: Check invalid public authoring stops before model work.\n"
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
        "name: invalid-public\n"
        "dsl_version: c3_strategy_v1\n"
        "kind: analysis_review_v1\n"
        "roles:\n"
        "  solver:\n"
        "    provider: codex_cli\n",
        encoding="utf-8",
    )
    return task_path, strategy_path, workspace


def _extract_output_path(output: str, prefix: str) -> Path:
    for line in output.splitlines():
        if line.startswith(prefix):
            return Path(line.split("=", 1)[1].strip())
    raise AssertionError(f"Could not find {prefix!r} in output:\n{output}")


@pytest.mark.parametrize(("fixture_name", "expected_message"), NEGATIVE_CASES)
def test_negative_public_examples_fail_at_parser_and_preflight_with_targeted_reason(
    fixture_name: str, expected_message: str
) -> None:
    payload = load_structured_file(NEGATIVE_ROOT / fixture_name)

    with pytest.raises(ValueError, match=re.escape(expected_message)):
        StrategyConfig.from_dict(payload)

    result = validator_preflight_node(
        _preflight_state(_analysis_review_task_spec(), payload)
    )

    assert result["config_verdict"] == "invalid_config"
    assert result["run_verdict"] == "invalid_config"
    assert result["stop_reason"] == "strategy_spec_parse"
    assert result["errors"] == [expected_message]
    assert result["summary_text"] == expected_message
    assert result["warnings"] == []
    assert result["validator_preflight"] == []


def test_compatibility_example_keeps_legacy_kind_warning_and_runtime_family() -> None:
    payload = load_structured_file(COMPATIBILITY_ROOT / "analysis_review_v1.yaml")

    parsed = StrategyConfig.from_dict(payload)
    result = validator_preflight_node(
        _preflight_state(_analysis_review_task_spec(), payload)
    )
    graph_spec = build_strategy_graph_spec(parsed.kind, payload).to_dict()

    assert classify_public_strategy_surface(payload) == "compatibility_only"
    assert parsed.kind == "analysis_review_v1"
    assert result["config_verdict"] == "pass"
    assert result["warnings"] == [LEGACY_WARNING]
    assert result["strategy_kind"] == "analysis_review_v1"
    assert graph_spec["strategy_kind"] == "analysis_review_bounded_v1"
    assert graph_spec["runtime_target"] == "analysis_review_v1"
    assert (
        route_after_strategy_selection({"strategy_kind": parsed.kind})
        == "analysis_review_v1"
    )


def test_internal_planning_fixture_remains_parseable_and_preflight_clean() -> None:
    payload = load_structured_file(PLANNING_FIXTURE)

    parsed = StrategyConfig.from_dict(payload)
    result = validator_preflight_node(_preflight_state(_planning_task_spec(), payload))

    assert classify_public_strategy_surface(payload) == "internal_or_private"
    assert parsed.kind == "deterministic_feature_planning_v1"
    assert parsed.runtime_target == "planning_v1"
    assert result["config_verdict"] == "pass"
    assert "run_verdict" not in result
    assert result["warnings"] == []


def test_main_cli_invalid_public_authoring_surfaces_invalid_config_summary_before_model_work(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_path, strategy_path, workspace = _write_invalid_public_specs(tmp_path)

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
            ]
        )
    )

    captured = capsys.readouterr()
    expected_message = "canonical public strategies must declare kind as one of:"

    assert exit_code == 1
    assert "run_verdict=invalid_config" in captured.out
    assert "config_verdict=invalid_config" in captured.out
    assert f"final_summary={expected_message}" in captured.out
    assert "FORGE_CODEX_BIN" not in captured.out
    assert "OPENAI_API_KEY" not in captured.out
    assert captured.err == ""

    report_path = _extract_output_path(captured.out, "report=")
    summary_path = _extract_output_path(captured.out, "summary=")
    assert report_path.exists()
    assert summary_path.exists()

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["verdict"] == "invalid_config"
    assert summary_payload["verdicts"]["run_verdict"] == "invalid_config"
    assert summary_payload["verdicts"]["config_verdict"] == "invalid_config"
    assert expected_message in summary_payload["final_summary"]
    assert expected_message in report_path.read_text(encoding="utf-8")


def test_main_cli_invalid_public_authoring_json_surfaces_invalid_config_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_path, strategy_path, workspace = _write_invalid_public_specs(tmp_path)

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
                "--json",
            ]
        )
    )

    captured = capsys.readouterr()
    expected_message = "canonical public strategies must declare kind as one of:"

    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["verdict"] == "invalid_config"
    assert payload["verdicts"]["run_verdict"] == "invalid_config"
    assert payload["verdicts"]["config_verdict"] == "invalid_config"
    assert expected_message in payload["final_summary"]
    assert expected_message in payload["errors"][0]
    report_path = Path(payload["artifacts"]["report_md"])
    summary_path = Path(payload["artifacts"]["summary_json"])
    assert report_path.exists()
    assert summary_path.exists()
    assert expected_message in report_path.read_text(encoding="utf-8")
    assert captured.err == ""


def test_standalone_cli_invalid_public_authoring_surfaces_invalid_config_summary_before_model_work(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_path, strategy_path, workspace = _write_invalid_public_specs(tmp_path)

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
    expected_message = "canonical public strategies must declare kind as one of:"

    assert exit_code == 1
    assert "run_verdict=invalid_config" in captured.out
    assert "config_verdict=invalid_config" in captured.out
    assert f"final_summary={expected_message}" in captured.out
    assert "FORGE_CODEX_BIN" not in captured.out
    assert "OPENAI_API_KEY" not in captured.out
    assert captured.err == ""

    report_path = _extract_output_path(captured.out, "report=")
    summary_path = _extract_output_path(captured.out, "summary=")
    assert report_path.exists()
    assert summary_path.exists()

    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["verdict"] == "invalid_config"
    assert summary_payload["verdicts"]["run_verdict"] == "invalid_config"
    assert summary_payload["verdicts"]["config_verdict"] == "invalid_config"
    assert expected_message in summary_payload["final_summary"]
    assert expected_message in report_path.read_text(encoding="utf-8")


def test_standalone_cli_invalid_public_authoring_json_surfaces_invalid_config_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_path, strategy_path, workspace = _write_invalid_public_specs(tmp_path)

    exit_code = harness_cli_module.main(
        [
            "run",
            "--task",
            str(task_path),
            "--strategy",
            str(strategy_path),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    expected_message = "canonical public strategies must declare kind as one of:"

    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["verdict"] == "invalid_config"
    assert payload["verdicts"]["run_verdict"] == "invalid_config"
    assert payload["verdicts"]["config_verdict"] == "invalid_config"
    assert expected_message in payload["final_summary"]
    assert expected_message in payload["errors"][0]
    report_path = Path(payload["artifacts"]["report_md"])
    summary_path = Path(payload["artifacts"]["summary_json"])
    assert report_path.exists()
    assert summary_path.exists()
    assert expected_message in report_path.read_text(encoding="utf-8")
    assert captured.err == ""


def test_executor_invalid_public_authoring_stops_before_model_work_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    task_path, strategy_path, workspace = _write_invalid_public_specs(tmp_path)
    out_root = tmp_path / "runs"
    executor = HarnessLangGraphExecutor(checkpoint="memory")

    state = asyncio.run(
        executor.execute(
            task_path=str(task_path),
            strategy_path=str(strategy_path),
            workspace=str(workspace),
            out_root=str(out_root),
        )
    )

    expected_message = "canonical public strategies must declare kind as one of:"
    summary_payload = state["summary_payload"]
    report_path = Path(summary_payload["artifacts"]["report_md"])
    summary_path = Path(summary_payload["artifacts"]["summary_json"])

    assert state["run_verdict"] == "invalid_config"
    assert state["config_verdict"] == "invalid_config"
    assert state["stop_reason"] == "strategy_spec_parse"
    assert expected_message in state["summary_text"]
    assert state["stage_history"] == []
    assert report_path.exists()
    assert summary_path.exists()
    assert expected_message in report_path.read_text(encoding="utf-8")

    summary_json = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_json["verdict"] == "invalid_config"
    assert summary_json["verdicts"]["config_verdict"] == "invalid_config"
    assert expected_message in summary_json["final_summary"]
