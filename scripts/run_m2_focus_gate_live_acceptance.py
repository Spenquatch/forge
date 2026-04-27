#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from anvil.harness.files import load_structured_file
from anvil.harness.types import canonical_workspace_ref_list

DEFAULT_CONFIG_PATH = REPO_ROOT / "examples/harness/live_acceptance/m2_focus_gate_local.yaml"
DEFAULT_OUT_ROOT = ".forge-harness-runs-live"
EXPECTED_TASK = "examples/harness/tasks/recommend_automation_improvements.yaml"
EXPECTED_STRATEGIES = {
    "bounded": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
    "trust": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
}
REQUIRED_ARTIFACTS = (
    "artifacts/01_focus_gate/structured_output.raw.json",
    "artifacts/01_focus_gate/structured_output.normalized.json",
    "artifacts/01_focus_gate/run.envelope.json",
    "artifacts/02_proposer/structured_output.raw.json",
    "artifacts/02_proposer/structured_output.normalized.json",
    "artifacts/02_proposer/run.envelope.json",
    "summary.json",
    "REPORT.md",
)
REVIEW_ROLE_NAMES = {
    "critic",
    "reviser_round_1",
    "reviser_round_2",
    "reviser_round_3",
    "auditor",
}
SELECTED_SEAM_DRIFT_TEXT = (
    "primary_seam.paths drifted from the selected focus gate paths after normalization"
)


class AcceptanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManifestConfig:
    task: Path
    workspace: Path
    out_root: Path
    strategies: dict[str, Path]


@dataclass(frozen=True)
class CaseResult:
    case: str
    verdict: str
    summary: str
    report: str
    error: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the exact M2 focus-gate bounded/trust adjudicate acceptance surface."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH.relative_to(REPO_ROOT)),
        help="Path to the local M2 acceptance manifest.",
    )
    parser.add_argument(
        "--workspace",
        help="Absolute workspace override. Overrides the manifest workspace.",
    )
    parser.add_argument(
        "--out-root",
        help="Output-root override. Overrides the manifest out_root.",
    )
    return parser.parse_args()


def _resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve(strict=False)


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


def _resolve_frozen_repo_file(path_value: str, expected: str, *, field_name: str) -> Path:
    if str(path_value).strip() != expected:
        raise ValueError(f"{field_name} must be exactly {expected}.")
    path = _resolve_repo_path(expected)
    if not path.is_file():
        raise ValueError(f"{field_name} resolved to a missing repo file: {path}")
    return path


def load_manifest_config(path_value: str | Path) -> ManifestConfig:
    manifest_path = _resolve_repo_path(path_value)
    payload = load_structured_file(manifest_path)

    task = _resolve_frozen_repo_file(
        str(payload.get("task") or ""),
        EXPECTED_TASK,
        field_name="task",
    )

    strategies = payload.get("strategies")
    if not isinstance(strategies, dict):
        raise ValueError("strategies must be a mapping.")
    bounded_strategy = _resolve_frozen_repo_file(
        str(strategies.get("bounded") or ""),
        EXPECTED_STRATEGIES["bounded"],
        field_name="strategies.bounded",
    )
    trust_strategy = _resolve_frozen_repo_file(
        str(strategies.get("trust") or ""),
        EXPECTED_STRATEGIES["trust"],
        field_name="strategies.trust",
    )

    workspace = _resolve_workspace_path(
        str(payload.get("workspace") or ""),
        field_name="workspace",
    )
    out_root = _resolve_out_root_path(payload.get("out_root"))

    return ManifestConfig(
        task=task,
        workspace=workspace,
        out_root=out_root,
        strategies={"bounded": bounded_strategy, "trust": trust_strategy},
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


def validate_acceptance_run(
    *,
    summary_path: Path,
    report_path: Path,
    workspace: Path,
) -> None:
    _require_file(summary_path)
    _require_file(report_path)

    run_dir = summary_path.parent
    for relative_path in REQUIRED_ARTIFACTS:
        _require_file(run_dir / relative_path)

    summary = _load_json(summary_path)
    focus_decision = summary.get("focus_decision")
    if not isinstance(focus_decision, dict):
        raise AcceptanceError("summary.json is missing focus_decision.")
    if focus_decision.get("gate_path") != "adjudicate":
        raise AcceptanceError("focus_decision.gate_path must be adjudicate.")
    if focus_decision.get("decision_state") != "selected":
        raise AcceptanceError("focus_decision.decision_state must be selected.")

    stages = summary.get("agent_stages")
    if not isinstance(stages, list):
        raise AcceptanceError("summary.json is missing agent_stages.")

    role_names = [
        str(stage.get("role_name") or "").strip()
        for stage in stages
        if isinstance(stage, dict)
    ]
    if "proposer" not in role_names:
        raise AcceptanceError("agent_stages must include proposer.")
    proposer_index = role_names.index("proposer")
    if not any(role in REVIEW_ROLE_NAMES for role in role_names[proposer_index + 1 :]):
        raise AcceptanceError("agent_stages must include a downstream review role after proposer.")

    failure_details = summary.get("failure_details")
    if isinstance(failure_details, dict) and failure_details.get("stage") == "focus_gate":
        raise AcceptanceError("summary.json records a focus_gate failure.")

    for stage in stages:
        if not isinstance(stage, dict):
            continue
        if stage.get("failure_kind") != "semantic_validation_error":
            continue
        for error in stage.get("semantic_validation_errors") or []:
            if SELECTED_SEAM_DRIFT_TEXT in str(error):
                raise AcceptanceError("selected-seam drift semantic validation failure is present.")

    proposer_raw = _load_json(run_dir / "artifacts/02_proposer/structured_output.raw.json")
    proposer_normalized = _load_json(
        run_dir / "artifacts/02_proposer/structured_output.normalized.json"
    )
    proposer_envelope = _load_json(run_dir / "artifacts/02_proposer/run.envelope.json")
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
            "proposer normalized payload and run.envelope.json structured_output primary_seam.paths do not match."
        )


def run_acceptance_case(
    *,
    case_name: str,
    strategy_path: Path,
    task_path: Path,
    workspace: Path,
    out_root: Path,
) -> CaseResult:
    command = [
        sys.executable,
        "-m",
        "anvil.cli",
        "harness-run",
        "--task",
        str(task_path),
        "--strategy",
        str(strategy_path),
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

    if result.returncode != 0:
        return CaseResult(
            case=case_name,
            verdict="FAIL",
            summary=summary_path,
            report=report_path,
            error=f"harness-run exited with {result.returncode}.",
        )

    if parse_error is not None:
        return CaseResult(
            case=case_name,
            verdict="FAIL",
            summary=summary_path,
            report=report_path,
            error=parse_error,
        )

    try:
        validate_acceptance_run(
            summary_path=Path(summary_path),
            report_path=Path(report_path),
            workspace=workspace,
        )
    except AcceptanceError as exc:
        return CaseResult(
            case=case_name,
            verdict="FAIL",
            summary=summary_path,
            report=report_path,
            error=str(exc),
        )

    return CaseResult(
        case=case_name,
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


def main() -> int:
    args = _parse_args()
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

    results: list[CaseResult] = []
    overall_pass = True
    for case_name in ("bounded", "trust"):
        result = run_acceptance_case(
            case_name=case_name,
            strategy_path=manifest.strategies[case_name],
            task_path=manifest.task,
            workspace=workspace,
            out_root=out_root,
        )
        _print_case_result(result)
        results.append(result)
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
