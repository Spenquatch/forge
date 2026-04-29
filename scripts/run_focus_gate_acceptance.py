#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from anvil.harness.files import load_structured_file
from anvil.harness.contracts import (
    canonical_artifact_focus_id,
    canonical_seam_id_for_paths,
)
from anvil.harness.types import (
    GENERIC_FOCUS_GATE_QUESTION_PROMPT,
    canonical_workspace_ref_list,
)

DEFAULT_CONFIG_PATH = REPO_ROOT / "examples/harness/live_acceptance/focus_gate_acceptance_local.yaml"
LEGACY_DEFAULT_CONFIG_PATH = REPO_ROOT / "examples/harness/live_acceptance/m2_focus_gate_local.yaml"
DEFAULT_OUT_ROOT = ".forge-harness-runs-live"
EXAMPLE_TASK_PATH = "examples/harness/tasks/recommend_automation_improvements.yaml"
EXAMPLE_STRATEGIES = {
    "bounded": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
    "trust": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
}
LEGACY_SCENARIO_DEFAULTS = {
    "bounded": {
        "expected_gate_path": "adjudicate",
        "expected_focus_type": "seam",
        "expected_decision_state": "selected",
        "expect_proposer_artifacts": True,
        "expect_downstream_bridge": True,
    },
    "trust": {
        "expected_gate_path": "adjudicate",
        "expected_focus_type": "seam",
        "expected_decision_state": "selected",
        "expect_proposer_artifacts": True,
        "expect_downstream_bridge": True,
    },
}
REQUIRED_PROPOSER_ARTIFACTS = (
    "structured_output.raw.json",
    "structured_output.normalized.json",
    "run.envelope.json",
)
REVIEW_ROLE_NAMES = {
    "critic",
    "reviser_round_1",
    "reviser_round_2",
    "reviser_round_3",
    "auditor",
}
BLOCKED_DECISION_STATES = {"clarification_requested", "no_viable_focus"}
SELECTED_SEAM_DRIFT_TEXT = (
    "primary_seam.paths drifted from the selected focus gate paths after normalization"
)


class AcceptanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class AcceptanceScenario:
    name: str
    task: Path | None
    strategy: Path
    expected_gate_path: str
    expected_focus_type: str
    expected_decision_state: str
    expect_proposer_artifacts: bool
    expect_downstream_bridge: bool
    expected_warning_substrings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManifestConfig:
    task: Path
    workspace: Path
    out_root: Path
    scenarios: tuple[AcceptanceScenario, ...]


@dataclass(frozen=True)
class CaseResult:
    case: str
    verdict: str
    summary: str
    report: str
    error: str | None = None


def _parse_args(
    argv: Sequence[str] | None = None,
    *,
    default_config_path: Path = DEFAULT_CONFIG_PATH,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run scenario-driven focus-gate acceptance checks against harness-run output."
        )
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path.relative_to(REPO_ROOT)),
        help="Path to the local focus-gate acceptance manifest.",
    )
    parser.add_argument(
        "--workspace",
        help="Absolute workspace override. Overrides the manifest workspace.",
    )
    parser.add_argument(
        "--out-root",
        help="Output-root override. Overrides the manifest out_root.",
    )
    return parser.parse_args(argv)


def _resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve(strict=False)


def _resolve_existing_file(path_value: str | Path, *, field_name: str) -> Path:
    path = _resolve_repo_path(path_value)
    if not path.is_file():
        raise ValueError(f"{field_name} must point to an existing file.")
    return path


def _resolve_workspace_path(path_value: str | Path, *, field_name: str) -> Path:
    workspace = Path(path_value).expanduser()
    if not workspace.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path.")
    workspace = workspace.resolve(strict=False)
    if not workspace.is_dir():
        raise ValueError(f"{field_name} must point to an existing directory.")
    return workspace


def _resolve_out_root_path(path_value: str | Path | None) -> Path:
    raw_value = DEFAULT_OUT_ROOT if path_value in {None, ""} else path_value
    out_root = Path(str(raw_value)).expanduser()
    if not out_root.is_absolute():
        out_root = REPO_ROOT / out_root
    return out_root.resolve(strict=False)


def _parse_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean.")


def _parse_string_list(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings.")
    parsed: list[str] = []
    for index, item in enumerate(value):
        text = str(item or "").strip()
        if not text:
            raise ValueError(f"{field_name}[{index}] must be a non-empty string.")
        parsed.append(text)
    return tuple(parsed)


def _parse_enum(value: Any, *, field_name: str, allowed: set[str]) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {allowed_values}.")
    return text


def _legacy_scenario_defaults(name: str) -> dict[str, Any]:
    defaults = LEGACY_SCENARIO_DEFAULTS.get(name)
    if defaults is not None:
        return dict(defaults)
    return {
        "expected_gate_path": "adjudicate",
        "expected_focus_type": "seam",
        "expected_decision_state": "selected",
        "expect_proposer_artifacts": True,
        "expect_downstream_bridge": True,
    }


def _parse_scenario(
    payload: Any,
    *,
    fallback_name: str | None = None,
    defaults: dict[str, Any] | None = None,
    index: int | None = None,
) -> AcceptanceScenario:
    if not isinstance(payload, dict):
        raise ValueError("scenario entries must be mappings.")

    name = str(payload.get("name") or fallback_name or "").strip()
    if not name:
        label = f"scenarios[{index}]" if index is not None else "scenario"
        raise ValueError(f"{label}.name must be a non-empty string.")

    merged = dict(defaults or {})
    merged.update(payload)
    task_value = merged.get("task")
    strategy_value = merged.get("strategy")
    if not str(strategy_value or "").strip():
        raise ValueError(f"scenario {name!r} must define strategy.")

    return AcceptanceScenario(
        name=name,
        task=(
            _resolve_existing_file(task_value, field_name=f"scenario {name!r}.task")
            if str(task_value or "").strip()
            else None
        ),
        strategy=_resolve_existing_file(strategy_value, field_name=f"scenario {name!r}.strategy"),
        expected_gate_path=_parse_enum(
            merged.get("expected_gate_path"),
            field_name=f"scenario {name!r}.expected_gate_path",
            allowed={"adjudicate", "deliberate"},
        ),
        expected_focus_type=_parse_enum(
            merged.get("expected_focus_type"),
            field_name=f"scenario {name!r}.expected_focus_type",
            allowed={"seam", "artifact"},
        ),
        expected_decision_state=_parse_enum(
            merged.get("expected_decision_state"),
            field_name=f"scenario {name!r}.expected_decision_state",
            allowed={"selected", "clarification_requested", "no_viable_focus"},
        ),
        expect_proposer_artifacts=_parse_bool(
            merged.get("expect_proposer_artifacts"),
            field_name=f"scenario {name!r}.expect_proposer_artifacts",
        ),
        expect_downstream_bridge=_parse_bool(
            merged.get("expect_downstream_bridge"),
            field_name=f"scenario {name!r}.expect_downstream_bridge",
        ),
        expected_warning_substrings=_parse_string_list(
            merged.get("expected_warning_substrings"),
            field_name=f"scenario {name!r}.expected_warning_substrings",
        ),
    )


def _load_scenarios(payload: dict[str, Any]) -> tuple[AcceptanceScenario, ...]:
    raw_scenarios = payload.get("scenarios")
    if raw_scenarios is not None:
        if not isinstance(raw_scenarios, list) or not raw_scenarios:
            raise ValueError("scenarios must be a non-empty list.")
        scenarios = tuple(
            _parse_scenario(item, index=index) for index, item in enumerate(raw_scenarios)
        )
    else:
        strategies = payload.get("strategies")
        if not isinstance(strategies, dict) or not strategies:
            raise ValueError("manifest must define either scenarios or legacy strategies.")
        parsed: list[AcceptanceScenario] = []
        for name, strategy_path in strategies.items():
            parsed.append(
                _parse_scenario(
                    {"strategy": strategy_path},
                    fallback_name=str(name).strip(),
                    defaults=_legacy_scenario_defaults(str(name).strip()),
                )
            )
        scenarios = tuple(parsed)

    names = [scenario.name for scenario in scenarios]
    if len(set(names)) != len(names):
        raise ValueError("scenario names must be unique.")
    return scenarios


def load_manifest_config(path_value: str | Path) -> ManifestConfig:
    manifest_path = _resolve_repo_path(path_value)
    payload = load_structured_file(manifest_path)

    task = _resolve_existing_file(str(payload.get("task") or ""), field_name="task")
    workspace = _resolve_workspace_path(
        str(payload.get("workspace") or ""),
        field_name="workspace",
    )
    out_root = _resolve_out_root_path(payload.get("out_root"))
    scenarios = _load_scenarios(payload)

    return ManifestConfig(
        task=task,
        workspace=workspace,
        out_root=out_root,
        scenarios=scenarios,
    )


def resolve_runtime_paths(
    manifest: ManifestConfig,
    *,
    workspace_override: str | None,
    out_root_override: str | None,
) -> tuple[Path, Path]:
    workspace = (
        _resolve_workspace_path(workspace_override, field_name="--workspace")
        if workspace_override
        else manifest.workspace
    )
    out_root = (
        _resolve_out_root_path(out_root_override)
        if out_root_override
        else manifest.out_root
    )
    return workspace, out_root


def parse_harness_run_output(stdout: str) -> tuple[Path, Path]:
    summary_path: Path | None = None
    report_path: Path | None = None
    for line in stdout.splitlines():
        if line.startswith("summary="):
            summary_path = _resolve_repo_path(line.split("=", 1)[1].strip())
        elif line.startswith("report="):
            report_path = _resolve_repo_path(line.split("=", 1)[1].strip())
    if summary_path is None:
        raise AcceptanceError("harness-run output did not emit summary=...")
    if report_path is None:
        raise AcceptanceError("harness-run output did not emit report=...")
    return summary_path, report_path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AcceptanceError(f"unable to read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AcceptanceError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AcceptanceError(f"{path} must contain a JSON object.")
    return payload


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise AcceptanceError(f"required artifact is missing: {path}")


def _canonical_primary_paths(payload: dict[str, Any], *, workspace: Path) -> list[str]:
    primary_seam = payload.get("primary_seam")
    if not isinstance(primary_seam, dict):
        raise AcceptanceError("primary_seam must be an object.")
    return canonical_workspace_ref_list(
        primary_seam.get("paths"),
        workspace_root=workspace,
    )


def _canonical_path_list(payload: dict[str, Any], key: str, *, workspace: Path) -> list[str]:
    return canonical_workspace_ref_list(payload.get(key), workspace_root=workspace)


def _stage_role_names(stages: list[dict[str, Any]]) -> list[str]:
    return [
        str(stage.get("role_name") or "").strip()
        for stage in stages
        if isinstance(stage, dict)
    ]


def _require_stage(
    stages: list[dict[str, Any]],
    *,
    role_name: str,
) -> tuple[int, dict[str, Any]]:
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        if str(stage.get("role_name") or "").strip() == role_name:
            return index, stage
    raise AcceptanceError(f"agent_stages must include {role_name}.")


def _stage_artifact_dir(stage: dict[str, Any], *, role_name: str) -> Path:
    stdout_path = str(stage.get("stdout_path") or "").strip()
    if not stdout_path:
        raise AcceptanceError(f"{role_name} stage is missing stdout_path.")
    return Path(stdout_path).expanduser().resolve(strict=False).parent


def _warning_pool(
    *,
    summary: dict[str, Any],
    focus_decision: dict[str, Any],
    focus_stage: dict[str, Any],
) -> list[str]:
    warning_sources = []
    warning_sources.extend(focus_decision.get("warnings") or [])
    warning_sources.extend(summary.get("warnings") or [])
    failure_details = summary.get("failure_details")
    if isinstance(failure_details, dict):
        warning_sources.extend(failure_details.get("warnings") or [])
    warning_sources.extend(focus_stage.get("warnings") or [])
    warning_sources.extend(focus_stage.get("semantic_validation_warnings") or [])
    return [str(item).strip() for item in warning_sources if str(item).strip()]


def validate_acceptance_run(
    *,
    summary_path: Path,
    report_path: Path,
    workspace: Path,
    scenario: AcceptanceScenario,
) -> None:
    _require_file(summary_path)
    _require_file(report_path)

    summary = _load_json(summary_path)
    focus_decision = summary.get("focus_decision")
    if not isinstance(focus_decision, dict):
        raise AcceptanceError("summary.json is missing focus_decision.")

    if focus_decision.get("gate_path") != scenario.expected_gate_path:
        raise AcceptanceError(
            "focus_decision.gate_path must match "
            f"{scenario.expected_gate_path}; got {focus_decision.get('gate_path')}."
        )
    if focus_decision.get("focus_type") != scenario.expected_focus_type:
        raise AcceptanceError(
            "focus_decision.focus_type must match "
            f"{scenario.expected_focus_type}; got {focus_decision.get('focus_type')}."
        )
    if focus_decision.get("decision_state") != scenario.expected_decision_state:
        raise AcceptanceError(
            "focus_decision.decision_state must match "
            f"{scenario.expected_decision_state}; got {focus_decision.get('decision_state')}."
        )

    stages = summary.get("agent_stages")
    if not isinstance(stages, list):
        raise AcceptanceError("summary.json is missing agent_stages.")
    stage_records = [stage for stage in stages if isinstance(stage, dict)]
    role_names = _stage_role_names(stage_records)

    focus_index, focus_stage = _require_stage(stage_records, role_name="focus_gate")
    if scenario.expected_gate_path == "deliberate":
        probe_index, _ = _require_stage(stage_records, role_name="focus_gate_probe")
        if probe_index > focus_index:
            raise AcceptanceError("focus_gate_probe must run before focus_gate.")

    focus_metadata = (focus_stage.get("metadata") or {}).get("focus_gate")
    if not isinstance(focus_metadata, dict):
        raise AcceptanceError("focus_gate stage metadata is missing focus_gate.")
    for key in ("gate_path", "focus_type", "decision_state"):
        if focus_metadata.get(key) != focus_decision.get(key):
            raise AcceptanceError(f"focus_gate stage metadata {key} does not match focus_decision.")

    if scenario.expected_decision_state == "clarification_requested":
        question = focus_decision.get("question")
        if not isinstance(question, dict):
            raise AcceptanceError("clarification scenarios must record focus_decision.question.")
        if (
            str(question.get("prompt") or "").strip()
            != GENERIC_FOCUS_GATE_QUESTION_PROMPT
        ):
            raise AcceptanceError(
                "clarification scenarios must use the canonical focus gate question prompt."
            )

    failure_details = summary.get("failure_details")
    if scenario.expected_decision_state in BLOCKED_DECISION_STATES:
        if not isinstance(failure_details, dict) or failure_details.get("stage") != "focus_gate":
            raise AcceptanceError("blocked focus-gate scenarios must record focus_gate failure_details.")
        if failure_details.get("decision_state") != scenario.expected_decision_state:
            raise AcceptanceError(
                "failure_details.decision_state must match "
                f"{scenario.expected_decision_state}."
            )
    elif isinstance(failure_details, dict) and failure_details.get("stage") == "focus_gate":
        raise AcceptanceError("selected focus-gate scenarios must not record a focus_gate failure.")

    for stage in stage_records:
        if stage.get("failure_kind") != "semantic_validation_error":
            continue
        for error in stage.get("semantic_validation_errors") or []:
            if SELECTED_SEAM_DRIFT_TEXT in str(error):
                raise AcceptanceError("selected-seam drift semantic validation failure is present.")

    warnings = _warning_pool(
        summary=summary,
        focus_decision=focus_decision,
        focus_stage=focus_stage,
    )
    for substring in scenario.expected_warning_substrings:
        if not any(substring in warning for warning in warnings):
            raise AcceptanceError(
                f"expected warning substring was not present: {substring!r}."
            )

    adapter_plan = focus_decision.get("adapter_plan")
    if not isinstance(adapter_plan, dict):
        raise AcceptanceError("focus_decision.adapter_plan must be an object.")
    selected_focus_paths = _canonical_path_list(
        focus_decision,
        "selected_focus_paths",
        workspace=workspace,
    )
    if (
        scenario.expected_focus_type == "artifact"
        and scenario.expected_decision_state == "selected"
    ):
        if len(selected_focus_paths) != 1:
            raise AcceptanceError(
                "focus_decision.selected_focus_paths must contain exactly one path "
                "when focus_type=artifact and decision_state=selected."
            )
        expected_selected_focus_id = canonical_artifact_focus_id(selected_focus_paths[0])
        if focus_decision.get("selected_focus_id") != expected_selected_focus_id:
            raise AcceptanceError(
                "focus_decision.selected_focus_id must be the canonical artifact "
                "focus ID when focus_type=artifact and decision_state=selected."
            )
        if adapter_plan.get("primary_focus_id") != focus_decision.get("selected_focus_id"):
            raise AcceptanceError(
                "adapter_plan.primary_focus_id must equal "
                "focus_decision.selected_focus_id when focus_type=artifact and "
                "decision_state=selected."
            )
        if adapter_plan.get("adaptation_basis") != "artifact_singleton":
            raise AcceptanceError(
                "adapter_plan.adaptation_basis must equal 'artifact_singleton' "
                "when focus_type=artifact and decision_state=selected."
            )
    downstream_primary_seam_id = str(
        adapter_plan.get("downstream_primary_seam_id") or ""
    ).strip()
    downstream_primary_seam_paths = canonical_workspace_ref_list(
        adapter_plan.get("downstream_primary_seam_paths") or [],
        workspace_root=workspace,
    )
    if scenario.expect_downstream_bridge:
        if not downstream_primary_seam_id:
            raise AcceptanceError("adapter_plan.downstream_primary_seam_id is required.")
        if not downstream_primary_seam_paths:
            raise AcceptanceError("adapter_plan.downstream_primary_seam_paths is required.")
        expected_bridge_id = canonical_seam_id_for_paths(downstream_primary_seam_paths)
        if downstream_primary_seam_id != expected_bridge_id:
            raise AcceptanceError(
                "adapter_plan.downstream_primary_seam_id does not match "
                "adapter_plan.downstream_primary_seam_paths."
            )
        if selected_focus_paths and selected_focus_paths != downstream_primary_seam_paths:
            raise AcceptanceError(
                "adapter_plan.downstream_primary_seam_paths do not match selected_focus_paths."
            )
    elif downstream_primary_seam_id or downstream_primary_seam_paths:
        raise AcceptanceError(
            "adapter_plan downstream bridge must be empty when expect_downstream_bridge=false."
        )

    if scenario.expect_proposer_artifacts:
        proposer_index, proposer_stage = _require_stage(stage_records, role_name="proposer")
        if not any(role in REVIEW_ROLE_NAMES for role in role_names[proposer_index + 1 :]):
            raise AcceptanceError("agent_stages must include a downstream review role after proposer.")

        proposer_artifact_dir = _stage_artifact_dir(proposer_stage, role_name="proposer")
        for relative_path in REQUIRED_PROPOSER_ARTIFACTS:
            _require_file(proposer_artifact_dir / relative_path)

        proposer_raw = _load_json(proposer_artifact_dir / "structured_output.raw.json")
        proposer_normalized = _load_json(
            proposer_artifact_dir / "structured_output.normalized.json"
        )
        proposer_envelope = _load_json(proposer_artifact_dir / "run.envelope.json")
        envelope_structured_output = proposer_envelope.get("structured_output")
        if not isinstance(envelope_structured_output, dict):
            raise AcceptanceError("proposer run.envelope.json is missing structured_output.")

        raw_paths = _canonical_primary_paths(proposer_raw, workspace=workspace)
        normalized_paths = _canonical_primary_paths(proposer_normalized, workspace=workspace)
        envelope_paths = _canonical_primary_paths(
            envelope_structured_output,
            workspace=workspace,
        )
        if raw_paths != normalized_paths:
            raise AcceptanceError("proposer raw and normalized primary_seam.paths do not match.")
        if normalized_paths != envelope_paths:
            raise AcceptanceError(
                "proposer normalized payload and run.envelope.json structured_output "
                "primary_seam.paths do not match."
            )
        if scenario.expect_downstream_bridge and normalized_paths != downstream_primary_seam_paths:
            raise AcceptanceError(
                "proposer primary_seam.paths do not match the focus gate downstream bridge."
            )
    elif "proposer" in role_names:
        raise AcceptanceError("blocked focus-gate scenarios must not advance to proposer.")


def run_acceptance_case(
    *,
    scenario: AcceptanceScenario,
    task_path: Path,
    workspace: Path,
    out_root: Path,
) -> CaseResult:
    effective_task_path = scenario.task or task_path
    command = [
        sys.executable,
        "-m",
        "anvil.cli",
        "harness-run",
        "--task",
        str(effective_task_path),
        "--strategy",
        str(scenario.strategy),
        "--workspace",
        str(workspace),
        "--out-root",
        str(out_root),
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    summary_path = ""
    report_path = ""
    parse_error: str | None = None
    try:
        parsed_summary, parsed_report = parse_harness_run_output(result.stdout)
        summary_path = str(parsed_summary)
        report_path = str(parsed_report)
    except AcceptanceError as exc:
        parse_error = str(exc)

    if parse_error is not None:
        return CaseResult(
            case=scenario.name,
            verdict="FAIL",
            summary=summary_path,
            report=report_path,
            error=parse_error,
        )

    if (
        result.returncode != 0
        and scenario.expected_decision_state not in BLOCKED_DECISION_STATES
    ):
        return CaseResult(
            case=scenario.name,
            verdict="FAIL",
            summary=summary_path,
            report=report_path,
            error=f"harness-run exited with {result.returncode}.",
        )

    try:
        validate_acceptance_run(
            summary_path=Path(summary_path),
            report_path=Path(report_path),
            workspace=workspace,
            scenario=scenario,
        )
    except AcceptanceError as exc:
        return CaseResult(
            case=scenario.name,
            verdict="FAIL",
            summary=summary_path,
            report=report_path,
            error=str(exc),
        )

    return CaseResult(
        case=scenario.name,
        verdict="PASS",
        summary=summary_path,
        report=report_path,
    )


def _print_case_result(result: CaseResult) -> None:
    print(
        json.dumps(
            {
                "case": result.case,
                "verdict": result.verdict,
                "summary": result.summary,
                "report": result.report,
            },
            separators=(",", ":"),
        )
    )
    if result.error:
        print(result.error, file=sys.stderr)


def main(
    argv: Sequence[str] | None = None,
    *,
    default_config_path: Path = DEFAULT_CONFIG_PATH,
) -> int:
    args = _parse_args(argv, default_config_path=default_config_path)
    try:
        manifest = load_manifest_config(args.config)
        workspace, out_root = resolve_runtime_paths(
            manifest,
            workspace_override=args.workspace,
            out_root_override=args.out_root,
        )
    except (AcceptanceError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps({"overall": "FAIL"}, separators=(",", ":")))
        return 1

    overall_pass = True
    for scenario in manifest.scenarios:
        result = run_acceptance_case(
            scenario=scenario,
            task_path=manifest.task,
            workspace=workspace,
            out_root=out_root,
        )
        _print_case_result(result)
        if result.verdict != "PASS":
            overall_pass = False

    print(
        json.dumps(
            {"overall": "PASS" if overall_pass else "FAIL"},
            separators=(",", ":"),
        )
    )
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
