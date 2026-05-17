#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from anvil.harness.contracts import (
    canonical_artifact_focus_id,
    canonical_seam_id_for_paths,
)
from anvil.harness.files import load_structured_file
from anvil.harness.types import (
    GENERIC_FOCUS_GATE_QUESTION_PROMPT,
    canonical_seam_path_list,
)

DEFAULT_CONFIG_PATH = (
    REPO_ROOT / ".gstack/m4-request-gate/orch/focus_gate_acceptance.yaml"
)
CANONICAL_TEMPLATE_PATH = (
    REPO_ROOT / "examples/harness/live_acceptance/focus_gate_acceptance.template.yaml"
)
LEGACY_DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "examples/harness/live_acceptance/m2_focus_gate_local.yaml"
)
DEFAULT_OUT_ROOT = ".forge-harness-runs-live"
DEFAULT_PREFLIGHT_TIMEOUT_SEC = 60
DEFAULT_SHARD_TIMEOUT_SEC = 12 * 60
EXAMPLE_TASK_PATH = "examples/harness/tasks/recommend_automation_improvements.yaml"
EXAMPLE_STRATEGIES = {
    "bounded": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
    "trust": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
}
CANONICAL_STRATEGY_ROOT = REPO_ROOT / "examples/harness/strategies"
MODELS_CONFIG_PATH = REPO_ROOT / "config/models.yaml"
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
class AcceptanceShard:
    name: str
    scenarios: tuple[AcceptanceScenario, ...]


@dataclass(frozen=True)
class ShardManifestConfig:
    default_task: Path
    workspace_seed: Path
    out_root: Path
    shards: tuple[AcceptanceShard, ...]
    preflight_timeout_sec: int
    shard_timeout_sec: int


@dataclass(frozen=True)
class LegacyManifestConfig:
    task: Path
    workspace: Path
    out_root: Path
    scenarios: tuple[AcceptanceScenario, ...]


@dataclass(frozen=True)
class ProvisionedWorkspace:
    temp_root: Path
    workspace: Path
    baseline_commit: str
    verification: dict[str, Any]


@dataclass(frozen=True)
class CaseResult:
    case: str
    verdict: str
    summary: str
    report: str
    error: str | None = None
    returncode: int | None = None
    command: tuple[str, ...] = ()
    duration_sec: float = 0.0


ManifestConfig = ShardManifestConfig | LegacyManifestConfig


def _parse_args(
    argv: Sequence[str] | None = None,
    *,
    default_config_path: Path = DEFAULT_CONFIG_PATH,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run shard-based focus-gate acceptance checks against harness-run output."
        )
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path.relative_to(REPO_ROOT)),
        help="Path to the focus-gate acceptance manifest.",
    )
    parser.add_argument(
        "--shard",
        help="Shard name to execute for the canonical shard manifest.",
    )
    parser.add_argument(
        "--pass-id",
        help="Pass identifier used to group shard outputs for one final closeout pass.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run prereq checks only and exit before provisioning or shard execution.",
    )
    parser.add_argument(
        "--workspace",
        help="Legacy-only absolute workspace override. Unsupported for the shard manifest.",
    )
    parser.add_argument(
        "--out-root",
        help="Optional output-root override.",
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


def _resolve_existing_dir(path_value: str | Path, *, field_name: str) -> Path:
    path = _resolve_repo_path(path_value)
    if not path.is_dir():
        raise ValueError(f"{field_name} must point to an existing directory.")
    return path


def _resolve_workspace_path(path_value: str | Path, *, field_name: str) -> Path:
    workspace = Path(path_value).expanduser()
    if not workspace.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path.")
    workspace = workspace.resolve(strict=False)
    if not workspace.is_dir():
        raise ValueError(f"{field_name} must point to an existing directory.")
    return workspace


def _resolve_out_root_path(path_value: str | Path | None, *, default: str) -> Path:
    raw_value = default if path_value in {None, ""} else path_value
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


def _parse_positive_int(
    value: Any,
    *,
    field_name: str,
    default: int,
) -> int:
    if value in {None, ""}:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return parsed


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
        strategy=_resolve_existing_file(
            strategy_value, field_name=f"scenario {name!r}.strategy"
        ),
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
            _parse_scenario(item, index=index)
            for index, item in enumerate(raw_scenarios)
        )
    else:
        strategies = payload.get("strategies")
        if not isinstance(strategies, dict) or not strategies:
            raise ValueError(
                "manifest must define either scenarios or legacy strategies."
            )
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


def _parse_shard(payload: Any, *, index: int) -> AcceptanceShard:
    if not isinstance(payload, dict):
        raise ValueError("shards entries must be mappings.")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError(f"shards[{index}].name must be a non-empty string.")
    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError(f"shards[{index}].scenarios must be a non-empty list.")
    scenarios = tuple(
        _parse_scenario(item, index=scenario_index)
        for scenario_index, item in enumerate(raw_scenarios)
    )
    scenario_names = [scenario.name for scenario in scenarios]
    if len(set(scenario_names)) != len(scenario_names):
        raise ValueError(f"shard {name!r} must not repeat scenario names.")
    return AcceptanceShard(name=name, scenarios=scenarios)


def load_manifest_config(path_value: str | Path) -> ManifestConfig:
    manifest_path = _resolve_repo_path(path_value)
    payload = load_structured_file(manifest_path)

    if "shards" in payload:
        default_task = _resolve_existing_file(
            str(payload.get("default_task") or payload.get("task") or ""),
            field_name="default_task",
        )
        workspace_seed = _resolve_existing_dir(
            str(payload.get("workspace_seed") or ""),
            field_name="workspace_seed",
        )
        out_root = _resolve_out_root_path(
            payload.get("out_root"),
            default=".forge-harness-runs-live/m4-request-gate/shards",
        )
        raw_shards = payload.get("shards")
        if not isinstance(raw_shards, list) or not raw_shards:
            raise ValueError("shards must be a non-empty list.")
        shards = tuple(
            _parse_shard(item, index=index) for index, item in enumerate(raw_shards)
        )
        shard_names = [shard.name for shard in shards]
        if len(set(shard_names)) != len(shard_names):
            raise ValueError("shard names must be unique.")
        return ShardManifestConfig(
            default_task=default_task,
            workspace_seed=workspace_seed,
            out_root=out_root,
            shards=shards,
            preflight_timeout_sec=_parse_positive_int(
                payload.get("preflight_timeout_sec"),
                field_name="preflight_timeout_sec",
                default=DEFAULT_PREFLIGHT_TIMEOUT_SEC,
            ),
            shard_timeout_sec=_parse_positive_int(
                payload.get("shard_timeout_sec"),
                field_name="shard_timeout_sec",
                default=DEFAULT_SHARD_TIMEOUT_SEC,
            ),
        )

    task = _resolve_existing_file(str(payload.get("task") or ""), field_name="task")
    workspace = _resolve_workspace_path(
        str(payload.get("workspace") or ""),
        field_name="workspace",
    )
    out_root = _resolve_out_root_path(payload.get("out_root"), default=DEFAULT_OUT_ROOT)
    scenarios = _load_scenarios(payload)
    return LegacyManifestConfig(
        task=task,
        workspace=workspace,
        out_root=out_root,
        scenarios=scenarios,
    )


def resolve_runtime_paths(
    manifest: LegacyManifestConfig,
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
        _resolve_out_root_path(out_root_override, default=str(manifest.out_root))
        if out_root_override
        else manifest.out_root
    )
    return workspace, out_root


def parse_harness_run_output(stdout: str) -> tuple[Path, Path]:
    summary_path: Path | None = None
    report_path: Path | None = None
    for line in stdout.splitlines():
        if line.startswith("summary="):
            emitted_path = line.split("=", 1)[1].strip()
            if not emitted_path:
                raise AcceptanceError(
                    "harness-run output emitted an empty summary= path."
                )
            summary_path = _resolve_repo_path(emitted_path)
        elif line.startswith("report="):
            emitted_path = line.split("=", 1)[1].strip()
            if not emitted_path:
                raise AcceptanceError(
                    "harness-run output emitted an empty report= path."
                )
            report_path = _resolve_repo_path(emitted_path)
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
    return canonical_seam_path_list(
        primary_seam.get("paths"),
        workspace_root=workspace,
    )


def _canonical_path_list(
    payload: dict[str, Any], key: str, *, workspace: Path
) -> list[str]:
    return canonical_seam_path_list(payload.get(key), workspace_root=workspace)


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
            raise AcceptanceError(
                f"focus_gate stage metadata {key} does not match focus_decision."
            )

    if scenario.expected_decision_state == "clarification_requested":
        question = focus_decision.get("question")
        if not isinstance(question, dict):
            raise AcceptanceError(
                "clarification scenarios must record focus_decision.question."
            )
        if (
            str(question.get("prompt") or "").strip()
            != GENERIC_FOCUS_GATE_QUESTION_PROMPT
        ):
            raise AcceptanceError(
                "clarification scenarios must use the canonical focus gate question prompt."
            )

    failure_details = summary.get("failure_details")
    if scenario.expected_decision_state in BLOCKED_DECISION_STATES:
        if (
            not isinstance(failure_details, dict)
            or failure_details.get("stage") != "focus_gate"
        ):
            raise AcceptanceError(
                "blocked focus-gate scenarios must record focus_gate failure_details."
            )
        if failure_details.get("decision_state") != scenario.expected_decision_state:
            raise AcceptanceError(
                "failure_details.decision_state must match "
                f"{scenario.expected_decision_state}."
            )
    elif (
        isinstance(failure_details, dict)
        and failure_details.get("stage") == "focus_gate"
    ):
        raise AcceptanceError(
            "selected focus-gate scenarios must not record a focus_gate failure."
        )

    for stage in stage_records:
        if stage.get("failure_kind") != "semantic_validation_error":
            continue
        for error in stage.get("semantic_validation_errors") or []:
            if SELECTED_SEAM_DRIFT_TEXT in str(error):
                raise AcceptanceError(
                    "selected-seam drift semantic validation failure is present."
                )

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
        expected_selected_focus_id = canonical_artifact_focus_id(
            selected_focus_paths[0]
        )
        if focus_decision.get("selected_focus_id") != expected_selected_focus_id:
            raise AcceptanceError(
                "focus_decision.selected_focus_id must be the canonical artifact "
                "focus ID when focus_type=artifact and decision_state=selected."
            )
        if adapter_plan.get("primary_focus_id") != focus_decision.get(
            "selected_focus_id"
        ):
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
    downstream_primary_seam_paths = canonical_seam_path_list(
        adapter_plan.get("downstream_primary_seam_paths") or [],
        workspace_root=workspace,
    )
    if scenario.expect_downstream_bridge:
        if not downstream_primary_seam_id:
            raise AcceptanceError(
                "adapter_plan.downstream_primary_seam_id is required."
            )
        if not downstream_primary_seam_paths:
            raise AcceptanceError(
                "adapter_plan.downstream_primary_seam_paths is required."
            )
        expected_bridge_id = canonical_seam_id_for_paths(downstream_primary_seam_paths)
        if downstream_primary_seam_id != expected_bridge_id:
            raise AcceptanceError(
                "adapter_plan.downstream_primary_seam_id does not match "
                "adapter_plan.downstream_primary_seam_paths."
            )
        if (
            selected_focus_paths
            and selected_focus_paths != downstream_primary_seam_paths
        ):
            raise AcceptanceError(
                "adapter_plan.downstream_primary_seam_paths do not match selected_focus_paths."
            )
    elif downstream_primary_seam_id or downstream_primary_seam_paths:
        raise AcceptanceError(
            "adapter_plan downstream bridge must be empty when expect_downstream_bridge=false."
        )

    if scenario.expect_proposer_artifacts:
        proposer_index, proposer_stage = _require_stage(
            stage_records, role_name="proposer"
        )
        if not any(
            role in REVIEW_ROLE_NAMES for role in role_names[proposer_index + 1 :]
        ):
            raise AcceptanceError(
                "agent_stages must include a downstream review role after proposer."
            )

        proposer_artifact_dir = _stage_artifact_dir(
            proposer_stage, role_name="proposer"
        )
        for relative_path in REQUIRED_PROPOSER_ARTIFACTS:
            _require_file(proposer_artifact_dir / relative_path)

        proposer_raw = _load_json(proposer_artifact_dir / "structured_output.raw.json")
        proposer_normalized = _load_json(
            proposer_artifact_dir / "structured_output.normalized.json"
        )
        proposer_envelope = _load_json(proposer_artifact_dir / "run.envelope.json")
        envelope_structured_output = proposer_envelope.get("structured_output")
        if not isinstance(envelope_structured_output, dict):
            raise AcceptanceError(
                "proposer run.envelope.json is missing structured_output."
            )

        raw_paths = _canonical_primary_paths(proposer_raw, workspace=workspace)
        normalized_paths = _canonical_primary_paths(
            proposer_normalized, workspace=workspace
        )
        envelope_paths = _canonical_primary_paths(
            envelope_structured_output,
            workspace=workspace,
        )
        if raw_paths != normalized_paths:
            raise AcceptanceError(
                "proposer raw and normalized primary_seam.paths do not match."
            )
        if normalized_paths != envelope_paths:
            raise AcceptanceError(
                "proposer normalized payload and run.envelope.json structured_output "
                "primary_seam.paths do not match."
            )
        if (
            scenario.expect_downstream_bridge
            and normalized_paths != downstream_primary_seam_paths
        ):
            raise AcceptanceError(
                "proposer primary_seam.paths do not match the focus gate downstream bridge."
            )
    elif "proposer" in role_names:
        raise AcceptanceError(
            "blocked focus-gate scenarios must not advance to proposer."
        )


def _run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_sec: int | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        raise AcceptanceError(
            f"command timed out after {timeout_sec} seconds: {' '.join(command)}"
        ) from exc


def _git_stdout(command: Sequence[str], *, cwd: Path) -> str:
    result = _run_subprocess(command, cwd=cwd)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise AcceptanceError(
            f"git command failed ({' '.join(command)}): {stderr or result.returncode}"
        )
    return result.stdout.strip()


def _select_shard(manifest: ShardManifestConfig, shard_name: str) -> AcceptanceShard:
    for shard in manifest.shards:
        if shard.name == shard_name:
            return shard
    available = ", ".join(shard.name for shard in manifest.shards)
    raise AcceptanceError(f"unknown shard {shard_name!r}; expected one of: {available}")


def _provider_checks_for_strategy(
    strategy_path: Path,
    *,
    providers: dict[str, Any],
) -> list[dict[str, Any]]:
    if not strategy_path.is_relative_to(CANONICAL_STRATEGY_ROOT):
        raise AcceptanceError(
            "authoritative shard execution requires committed canonical strategies "
            f"under {CANONICAL_STRATEGY_ROOT.relative_to(REPO_ROOT)}."
        )
    if strategy_path.name.endswith(".local.yaml"):
        raise AcceptanceError(
            f"authoritative shard execution forbids local strategy overrides: {strategy_path}"
        )

    strategy_payload = load_structured_file(strategy_path)
    roles = strategy_payload.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise AcceptanceError(f"strategy {strategy_path} must define roles.")

    checks: list[dict[str, Any]] = []
    seen_provider_names: set[str] = set()
    for role_name, role_payload in roles.items():
        if not isinstance(role_payload, dict):
            raise AcceptanceError(f"strategy role {role_name!r} must be a mapping.")
        if role_payload.get("skip_git_repo_check") is True:
            raise AcceptanceError(
                "authoritative shard execution forbids skip_git_repo_check=true "
                f"({strategy_path}, role {role_name})."
            )
        provider_name = str(role_payload.get("provider") or "").strip()
        if not provider_name:
            raise AcceptanceError(f"strategy role {role_name!r} must define provider.")
        provider_cfg = providers.get(provider_name)
        if not isinstance(provider_cfg, dict):
            raise AcceptanceError(
                f"provider {provider_name!r} referenced by {strategy_path} is not configured."
            )
        if provider_name in seen_provider_names:
            continue
        seen_provider_names.add(provider_name)

        provider_type = str(provider_cfg.get("type") or "").strip()
        provider_check: dict[str, Any] = {
            "provider": provider_name,
            "type": provider_type,
        }
        if provider_type == "cli":
            binary = str(provider_cfg.get("binary") or "").strip()
            if not binary:
                raise AcceptanceError(
                    f"CLI provider {provider_name!r} must define binary in config/models.yaml."
                )
            resolved_binary = shutil.which(binary)
            if resolved_binary is None:
                raise AcceptanceError(
                    f"required CLI binary {binary!r} for provider {provider_name!r} was not found on PATH."
                )
            provider_check["binary"] = binary
            provider_check["resolved_binary"] = resolved_binary
        elif provider_type == "api":
            key_env = str(provider_cfg.get("key_env") or "").strip()
            if not key_env:
                raise AcceptanceError(
                    f"API provider {provider_name!r} must define key_env in config/models.yaml."
                )
            if not os.environ.get(key_env):
                raise AcceptanceError(
                    f"required environment variable {key_env!r} for provider {provider_name!r} is not set."
                )
            provider_check["key_env"] = key_env
        elif provider_type == "local":
            model_path_value = provider_cfg.get("model_path") or provider_cfg.get(
                "model_name"
            )
            if isinstance(model_path_value, str) and (
                model_path_value.startswith("models/") or "/" in model_path_value
            ):
                model_path = _resolve_repo_path(model_path_value)
                if not model_path.exists():
                    raise AcceptanceError(
                        f"required local model path for provider {provider_name!r} does not exist: {model_path}"
                    )
                provider_check["model_path"] = str(model_path)
        checks.append(provider_check)
    return checks


def preflight_shard_manifest(
    manifest: ShardManifestConfig,
    *,
    shard_name: str,
    out_root: Path,
) -> dict[str, Any]:
    start = time.monotonic()
    git_binary = shutil.which("git")
    if git_binary is None:
        raise AcceptanceError(
            "git is required for shard execution and was not found on PATH."
        )
    if not manifest.workspace_seed.is_dir():
        raise AcceptanceError(
            f"workspace_seed is missing or not a directory: {manifest.workspace_seed}"
        )
    out_root.mkdir(parents=True, exist_ok=True)
    if not out_root.is_dir():
        raise AcceptanceError(f"out_root is not a directory: {out_root}")

    models_payload = load_structured_file(MODELS_CONFIG_PATH)
    providers = models_payload.get("providers")
    if not isinstance(providers, dict):
        raise AcceptanceError("config/models.yaml is missing providers.")

    shard = _select_shard(manifest, shard_name)
    provider_checks: list[dict[str, Any]] = []
    for scenario in shard.scenarios:
        provider_checks.extend(
            _provider_checks_for_strategy(scenario.strategy, providers=providers)
        )

    elapsed = time.monotonic() - start
    if elapsed > manifest.preflight_timeout_sec:
        raise AcceptanceError(
            "preflight exceeded the configured timeout "
            f"({elapsed:.2f}s > {manifest.preflight_timeout_sec}s)."
        )

    return {
        "git_binary": git_binary,
        "workspace_seed": str(manifest.workspace_seed),
        "out_root": str(out_root),
        "shard": shard.name,
        "provider_checks": provider_checks,
        "elapsed_sec": round(elapsed, 3),
    }


def provision_git_workspace(
    manifest: ShardManifestConfig,
    *,
    shard_name: str,
    pass_id: str,
) -> ProvisionedWorkspace:
    temp_root = Path(
        tempfile.mkdtemp(prefix=f"forge-focus-gate-{shard_name}-{pass_id}-")
    ).resolve(strict=False)
    workspace = temp_root / "workspace"
    shutil.copytree(manifest.workspace_seed, workspace)
    copied_git_dir = workspace / ".git"
    if copied_git_dir.exists():
        shutil.rmtree(copied_git_dir)

    _git_stdout(["git", "init"], cwd=workspace)
    _git_stdout(
        ["git", "config", "user.name", "forge-acceptance"],
        cwd=workspace,
    )
    _git_stdout(
        ["git", "config", "user.email", "forge-acceptance@example.invalid"],
        cwd=workspace,
    )
    _git_stdout(["git", "add", "."], cwd=workspace)
    _git_stdout(["git", "commit", "-m", "baseline fixture seed"], cwd=workspace)

    is_work_tree = _git_stdout(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=workspace
    )
    status_short = _git_stdout(["git", "status", "--short"], cwd=workspace)
    baseline_commit = _git_stdout(["git", "rev-parse", "HEAD"], cwd=workspace)
    if is_work_tree != "true":
        raise AcceptanceError("provisioned workspace did not become a git work tree.")
    if status_short:
        raise AcceptanceError(
            "provisioned workspace is not clean after baseline commit."
        )

    verification = {
        "temp_root": str(temp_root),
        "workspace": str(workspace),
        "seed_source": str(manifest.workspace_seed),
        "git_is_work_tree": is_work_tree,
        "git_status_short": status_short,
        "baseline_commit": baseline_commit,
    }
    return ProvisionedWorkspace(
        temp_root=temp_root,
        workspace=workspace,
        baseline_commit=baseline_commit,
        verification=verification,
    )


def _repo_head() -> str:
    return _git_stdout(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)


def _prepare_shard_out_root(
    *,
    out_root: Path,
    pass_id: str,
    shard_name: str,
    repo_head: str,
) -> Path:
    shard_root = out_root / pass_id / shard_name
    metadata_path = shard_root / "shard_result.json"
    if metadata_path.is_file():
        existing = _load_json(metadata_path)
        existing_head = str(existing.get("repo_head") or "").strip()
        if existing_head and existing_head != repo_head:
            raise AcceptanceError(
                "existing shard metadata for this pass-id was produced from a "
                "different commit SHA; start a new pass-id."
            )
    if shard_root.exists():
        shutil.rmtree(shard_root)
    shard_root.mkdir(parents=True, exist_ok=True)
    return shard_root


def run_acceptance_case(
    *,
    scenario: AcceptanceScenario,
    task_path: Path,
    workspace: Path,
    out_root: Path,
    timeout_sec: int | None = None,
) -> CaseResult:
    effective_task_path = scenario.task or task_path
    command = (
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
    )
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(command),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        duration_sec = time.monotonic() - started
        return CaseResult(
            case=scenario.name,
            verdict="FAIL",
            summary="",
            report="",
            error=f"harness-run timed out after {timeout_sec} seconds.",
            returncode=None,
            command=command,
            duration_sec=duration_sec,
        )

    duration_sec = time.monotonic() - started
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
            returncode=result.returncode,
            command=command,
            duration_sec=duration_sec,
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
            returncode=result.returncode,
            command=command,
            duration_sec=duration_sec,
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
            returncode=result.returncode,
            command=command,
            duration_sec=duration_sec,
        )

    return CaseResult(
        case=scenario.name,
        verdict="PASS",
        summary=summary_path,
        report=report_path,
        returncode=result.returncode,
        command=command,
        duration_sec=duration_sec,
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


def _case_result_payload(result: CaseResult) -> dict[str, Any]:
    return {
        "case": result.case,
        "verdict": result.verdict,
        "summary": result.summary,
        "report": result.report,
        "error": result.error,
        "returncode": result.returncode,
        "command": list(result.command),
        "duration_sec": round(result.duration_sec, 3),
    }


def run_shard(
    manifest: ShardManifestConfig,
    *,
    shard_name: str,
    pass_id: str,
    out_root: Path,
) -> int:
    shard = _select_shard(manifest, shard_name)
    preflight = preflight_shard_manifest(
        manifest, shard_name=shard_name, out_root=out_root
    )
    if not pass_id.strip():
        raise AcceptanceError("--pass-id must be a non-empty string.")
    repo_head = _repo_head()
    shard_root = _prepare_shard_out_root(
        out_root=out_root,
        pass_id=pass_id,
        shard_name=shard.name,
        repo_head=repo_head,
    )
    provisioned = provision_git_workspace(
        manifest, shard_name=shard.name, pass_id=pass_id
    )

    started_at = time.time()
    deadline = time.monotonic() + manifest.shard_timeout_sec
    overall_pass = True
    case_results: list[CaseResult] = []
    for scenario in shard.scenarios:
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            timeout_result = CaseResult(
                case=scenario.name,
                verdict="FAIL",
                summary="",
                report="",
                error=(
                    "shard wall-clock limit expired before the scenario could start."
                ),
            )
            case_results.append(timeout_result)
            _print_case_result(timeout_result)
            overall_pass = False
            break

        result = run_acceptance_case(
            scenario=scenario,
            task_path=manifest.default_task,
            workspace=provisioned.workspace,
            out_root=shard_root,
            timeout_sec=remaining,
        )
        case_results.append(result)
        _print_case_result(result)
        if result.verdict != "PASS":
            overall_pass = False

    final_workspace_status = _git_stdout(
        ["git", "status", "--short"],
        cwd=provisioned.workspace,
    )
    metadata = {
        "mode": "shard",
        "shard": shard.name,
        "pass_id": pass_id,
        "repo_head": repo_head,
        "started_at_epoch_sec": started_at,
        "completed_at_epoch_sec": time.time(),
        "overall": "PASS" if overall_pass else "FAIL",
        "workspace_prep_method": "copy-seed-then-git-init-baseline-commit",
        "workspace_seed": str(manifest.workspace_seed),
        "workspace": str(provisioned.workspace),
        "temp_root": str(provisioned.temp_root),
        "baseline_workspace_commit": provisioned.baseline_commit,
        "workspace_verification": provisioned.verification,
        "final_workspace_git_status_short": final_workspace_status,
        "out_root": str(shard_root),
        "preflight": preflight,
        "scenarios": [_case_result_payload(result) for result in case_results],
    }
    metadata_path = shard_root / "shard_result.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "overall": metadata["overall"],
                "shard": shard.name,
                "pass_id": pass_id,
                "metadata": str(metadata_path),
            },
            separators=(",", ":"),
        )
    )
    return 0 if overall_pass else 1


def _run_legacy_manifest(
    manifest: LegacyManifestConfig,
    *,
    workspace_override: str | None,
    out_root_override: str | None,
) -> int:
    workspace, out_root = resolve_runtime_paths(
        manifest,
        workspace_override=workspace_override,
        out_root_override=out_root_override,
    )
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


def main(
    argv: Sequence[str] | None = None,
    *,
    default_config_path: Path = DEFAULT_CONFIG_PATH,
) -> int:
    args = _parse_args(argv, default_config_path=default_config_path)
    try:
        manifest = load_manifest_config(args.config)
        if isinstance(manifest, ShardManifestConfig):
            if args.workspace:
                raise AcceptanceError(
                    "--workspace is unsupported for the shard manifest; shard runs provision their own isolated git-backed workspace."
                )
            if not args.shard:
                raise AcceptanceError("--shard is required for the shard manifest.")
            effective_out_root = (
                _resolve_out_root_path(
                    args.out_root,
                    default=str(manifest.out_root),
                )
                if args.out_root
                else manifest.out_root
            )
            if args.preflight_only:
                preflight = preflight_shard_manifest(
                    manifest,
                    shard_name=args.shard,
                    out_root=effective_out_root,
                )
                print(
                    json.dumps(
                        {
                            "overall": "PASS",
                            "mode": "preflight",
                            "shard": args.shard,
                            "preflight": preflight,
                        },
                        separators=(",", ":"),
                    )
                )
                return 0
            if not args.pass_id:
                raise AcceptanceError("--pass-id is required for the shard manifest.")
            return run_shard(
                manifest,
                shard_name=args.shard,
                pass_id=args.pass_id,
                out_root=effective_out_root,
            )

        if args.shard:
            raise AcceptanceError(
                "--shard is only supported by the shard manifest, not the legacy compatibility manifest."
            )
        if args.pass_id:
            raise AcceptanceError(
                "--pass-id is only supported by the shard manifest, not the legacy compatibility manifest."
            )
        if args.preflight_only:
            raise AcceptanceError(
                "--preflight-only is only supported by the shard manifest."
            )
        return _run_legacy_manifest(
            manifest,
            workspace_override=args.workspace,
            out_root_override=args.out_root,
        )
    except (AcceptanceError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps({"overall": "FAIL"}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
