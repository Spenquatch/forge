from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .files import tail_text, write_text
from .types import StrategyConfig, TaskSpec, ValidationRun, ValidatorConfig


def _coerce_subprocess_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _pattern_matches_any(cwd: Path, pattern: str) -> bool:
    pattern = str(pattern).strip()
    if not pattern:
        return True
    if any(ch in pattern for ch in "*?["):
        return any(True for _ in cwd.glob(pattern))
    return (cwd / pattern).exists()


def _status_from_missing_policy(policy: str) -> str:
    return {
        "fail": "failed",
        "skip": "skipped",
        "not_applicable": "not_applicable",
    }[policy]


def _applicability_for_validator(
    validator: ValidatorConfig,
    *,
    task: TaskSpec,
    strategy: StrategyConfig,
    cwd: Path,
    workspace_changed: bool,
) -> tuple[str, str | None, list[str], list[str]]:
    missing_paths: list[str] = []
    missing_binaries: list[str] = []

    run_when = validator.run_when
    if run_when == "patch_only" and task.task_kind != "patch":
        return (
            "not_applicable",
            f"Validator is patch-only, but task_kind is {task.task_kind}.",
            missing_paths,
            missing_binaries,
        )
    if run_when == "analysis_only" and task.task_kind != "analysis_review":
        return (
            "not_applicable",
            f"Validator is analysis-only, but task_kind is {task.task_kind}.",
            missing_paths,
            missing_binaries,
        )
    if run_when == "workspace_changed" and not workspace_changed:
        return (
            "skipped",
            "Validator runs only when the workspace changed relative to the start of the run.",
            missing_paths,
            missing_binaries,
        )
    if run_when == "mode_allow" and task.workspace_write_policy.mode not in {
        "allow",
        "require",
    }:
        return (
            "skipped",
            f"Validator runs only when workspace_write_policy.mode allows writes; current mode is {task.workspace_write_policy.mode}.",
            missing_paths,
            missing_binaries,
        )
    if run_when == "mode_require" and task.workspace_write_policy.mode != "require":
        return (
            "skipped",
            f"Validator runs only when workspace_write_policy.mode=require; current mode is {task.workspace_write_policy.mode}.",
            missing_paths,
            missing_binaries,
        )

    missing_paths = [
        pattern
        for pattern in validator.requires_paths
        if not _pattern_matches_any(cwd, pattern)
    ]
    if missing_paths:
        status = _status_from_missing_policy(validator.on_missing_surface)
        return (
            status,
            f"Required workspace surface for validator was not found: {', '.join(missing_paths)}",
            missing_paths,
            missing_binaries,
        )

    missing_binaries = [
        binary for binary in validator.required_binaries if shutil.which(binary) is None
    ]
    if missing_binaries:
        status = _status_from_missing_policy(validator.on_missing_binary)
        return (
            status,
            f"Required validator binary was not found on PATH: {', '.join(missing_binaries)}",
            missing_paths,
            missing_binaries,
        )

    return ("run", None, missing_paths, missing_binaries)


def run_validators(
    validators: list[ValidatorConfig],
    cwd: str | Path,
    out_dir: str | Path,
    round_index: int,
    *,
    task: TaskSpec,
    strategy: StrategyConfig,
    workspace_changed: bool,
) -> list[ValidationRun]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(cwd)
    results: list[ValidationRun] = []

    for idx, validator in enumerate(validators, start=1):
        step_dir = out / f"validator_{round_index:02d}_{idx:02d}_{validator.name}"
        step_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = step_dir / "stdout.txt"
        stderr_path = step_dir / "stderr.txt"

        status, reason, missing_paths, missing_binaries = _applicability_for_validator(
            validator,
            task=task,
            strategy=strategy,
            cwd=root,
            workspace_changed=workspace_changed,
        )

        if status != "run":
            write_text(stdout_path, "")
            write_text(stderr_path, reason or "")
            results.append(
                ValidationRun(
                    name=validator.name,
                    command=validator.run,
                    required=validator.required,
                    status=status,
                    ok=False,
                    applicable=False,
                    exit_code=None,
                    duration_sec=0.0,
                    stdout_path=str(stdout_path),
                    stderr_path=str(stderr_path),
                    stdout_tail="",
                    stderr_tail=reason or "",
                    error=None,
                    skip_reason=reason,
                    missing_paths=missing_paths,
                    missing_binaries=missing_binaries,
                )
            )
            continue

        started = time.monotonic()
        error = None
        status = "failed"
        try:
            proc = subprocess.run(
                [validator.shell, "-lc", validator.run],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=validator.timeout_sec,
                check=False,
            )
            stdout_text = proc.stdout
            stderr_text = proc.stderr
            exit_code = proc.returncode
            status = "passed" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired as exc:
            stdout_text = _coerce_subprocess_text(exc.stdout)
            stderr_text = _coerce_subprocess_text(exc.stderr)
            exit_code = 124
            error = f"Validator timed out after {validator.timeout_sec} seconds."
            status = "error"
        except Exception as exc:  # pragma: no cover - defensive path
            stdout_text = ""
            stderr_text = ""
            exit_code = None
            error = f"Validator execution raised an exception: {exc}"
            status = "error"
        duration = time.monotonic() - started

        write_text(stdout_path, stdout_text)
        write_text(stderr_path, stderr_text)

        results.append(
            ValidationRun(
                name=validator.name,
                command=validator.run,
                required=validator.required,
                status=status,
                ok=(status == "passed"),
                applicable=True,
                exit_code=exit_code,
                duration_sec=round(duration, 3),
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                stdout_tail=tail_text(stdout_text),
                stderr_tail=tail_text(stderr_text),
                error=error,
                skip_reason=None,
                missing_paths=missing_paths,
                missing_binaries=missing_binaries,
            )
        )
    return results


def preflight_validators(
    validators: list[ValidatorConfig],
    cwd: str | Path,
    *,
    task: TaskSpec,
    strategy: StrategyConfig,
    workspace_changed: bool = False,
) -> list[dict[str, Any]]:
    """Return applicability-only validator records without executing commands."""

    root = Path(cwd)
    preflight: list[dict[str, Any]] = []
    for validator in validators:
        status, reason, missing_paths, missing_binaries = _applicability_for_validator(
            validator,
            task=task,
            strategy=strategy,
            cwd=root,
            workspace_changed=workspace_changed,
        )
        preflight.append(
            {
                "name": validator.name,
                "required": validator.required,
                "run_when": validator.run_when,
                "status": status,
                "reason": reason,
                "missing_paths": missing_paths,
                "missing_binaries": missing_binaries,
                "command": validator.run,
            }
        )
    return preflight


_PLANNING_MARKDOWN_SECTION_HEADINGS = (
    "## Problem Statement",
    "## Rubric Results",
    "## Architectural Seams",
    "## Parallel Workstreams/Worktrees",
    "## Executable Slices",
)


def _string_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _workspace_root_path(workspace_root: str | Path | None) -> Path | None:
    if workspace_root in (None, ""):
        return None
    root = Path(workspace_root)
    if not root.exists() or not root.is_dir():
        return None
    return root.resolve()


def _validate_workspace_relative_path(
    path_value: Any,
    *,
    workspace_root: Path | None,
    label: str,
) -> list[str]:
    path_text = _string_or_empty(path_value)
    if not path_text:
        return [f"{label} must be a non-empty workspace-relative path."]
    if workspace_root is None:
        return [f"{label} cannot be validated because workspace_root is missing."]
    candidate = Path(path_text)
    resolved = (
        candidate.resolve(strict=False)
        if candidate.is_absolute()
        else (workspace_root / candidate).resolve(strict=False)
    )
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        return [f"{label} must stay within workspace_root: {path_text}"]
    if not resolved.exists():
        return [f"{label} was not found in workspace_root: {path_text}"]
    return []


def _dict_records(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _string_list(raw_items: Any) -> list[str]:
    if not isinstance(raw_items, list):
        return []
    values: list[str] = []
    for item in raw_items:
        text = _string_or_empty(item)
        if text:
            values.append(text)
    return values


def _find_section(markdown: str, heading: str) -> str:
    if heading not in markdown:
        return ""
    section = markdown.split(heading, 1)[1]
    for next_heading in _PLANNING_MARKDOWN_SECTION_HEADINGS:
        if next_heading == heading:
            continue
        marker = f"\n{next_heading}"
        if marker in section:
            section = section.split(marker, 1)[0]
            break
    return section


def _validate_markdown_item_order(
    section_text: str,
    *,
    label: str,
    expected_prefixes: list[str],
) -> list[str]:
    errors: list[str] = []
    cursor = 0
    for prefix in expected_prefixes:
        index = section_text.find(prefix, cursor)
        if index < 0:
            errors.append(f"{label} is missing markdown entry for {prefix}")
            continue
        cursor = index + len(prefix)
    return errors


def validate_planning_success_artifacts(
    plan_payload: dict[str, Any],
    *,
    workspace_root: str | Path | None,
    markdown_text: str,
) -> list[str]:
    errors: list[str] = []
    root = _workspace_root_path(workspace_root)
    if root is None:
        errors.append("Planning success publication requires a valid workspace_root.")

    repo_evidence_refs = _string_list(plan_payload.get("repo_evidence_refs"))
    for index, path_value in enumerate(repo_evidence_refs, start=1):
        errors.extend(
            _validate_workspace_relative_path(
                path_value,
                workspace_root=root,
                label=f"repo_evidence_refs[{index}]",
            )
        )

    seams = _dict_records(plan_payload.get("seams"))
    declared_seam_ids: set[str] = set()
    for index, seam in enumerate(seams, start=1):
        seam_id = _string_or_empty(seam.get("seam_id"))
        if not seam_id:
            errors.append(f"seams[{index}] is missing seam_id.")
        elif seam_id in declared_seam_ids:
            errors.append(f"Duplicate seam_id in plan payload: {seam_id}")
        else:
            declared_seam_ids.add(seam_id)
        seam_paths = _string_list(seam.get("paths"))
        if not seam_paths:
            errors.append(
                f"seams[{index}] must include at least one workspace path for publication."
            )
        for path_index, path_value in enumerate(seam_paths, start=1):
            errors.extend(
                _validate_workspace_relative_path(
                    path_value,
                    workspace_root=root,
                    label=f"seams[{index}].paths[{path_index}]",
                )
            )

    workstreams = _dict_records(plan_payload.get("workstreams"))
    declared_workstream_ids: set[str] = set()
    for index, workstream in enumerate(workstreams, start=1):
        workstream_id = _string_or_empty(workstream.get("workstream_id"))
        if not workstream_id:
            errors.append(f"workstreams[{index}] is missing workstream_id.")
        elif workstream_id in declared_workstream_ids:
            errors.append(f"Duplicate workstream_id in plan payload: {workstream_id}")
        else:
            declared_workstream_ids.add(workstream_id)
        seam_ids = _string_list(workstream.get("seam_ids"))
        if not seam_ids:
            errors.append(
                f"workstreams[{index}] must reference at least one declared seam_id."
            )
        for seam_id in seam_ids:
            if seam_id not in declared_seam_ids:
                errors.append(
                    f"workstreams[{index}] references unknown seam_id: {seam_id}"
                )

    slices = _dict_records(plan_payload.get("slices"))
    declared_slice_ids: set[str] = set()
    for index, slice_payload in enumerate(slices, start=1):
        slice_id = _string_or_empty(slice_payload.get("slice_id"))
        if not slice_id:
            errors.append(f"slices[{index}] is missing slice_id.")
        elif slice_id in declared_slice_ids:
            errors.append(f"Duplicate slice_id in plan payload: {slice_id}")
        else:
            declared_slice_ids.add(slice_id)
        workstream_id = _string_or_empty(slice_payload.get("workstream_id"))
        if not workstream_id:
            errors.append(f"slices[{index}] is missing workstream_id.")
        elif workstream_id not in declared_workstream_ids:
            errors.append(
                f"slices[{index}] references unknown workstream_id: {workstream_id}"
            )
        seam_ids = _string_list(slice_payload.get("seam_ids"))
        if not seam_ids:
            errors.append(f"slices[{index}] must reference at least one declared seam_id.")
        for seam_id in seam_ids:
            if seam_id not in declared_seam_ids:
                errors.append(f"slices[{index}] references unknown seam_id: {seam_id}")
        if not _string_list(slice_payload.get("acceptance_criteria")):
            errors.append(
                f"slices[{index}] must include at least one concrete acceptance criterion."
            )

    heading_positions: list[int] = []
    for heading in _PLANNING_MARKDOWN_SECTION_HEADINGS:
        index = markdown_text.find(heading)
        if index < 0:
            errors.append(f"PLAN.md is missing canonical section heading: {heading}")
            continue
        heading_positions.append(index)
    if heading_positions and heading_positions != sorted(heading_positions):
        errors.append("PLAN.md canonical section headings are out of order.")

    terminal_status = _string_or_empty(plan_payload.get("terminal_status"))
    if terminal_status and f"- Terminal status: `{terminal_status}`" not in markdown_text:
        errors.append("PLAN.md terminal status does not match the canonical plan payload.")
    run_mode = _string_or_empty(plan_payload.get("run_mode"))
    if run_mode and f"- Run mode: `{run_mode}`" not in markdown_text:
        errors.append("PLAN.md run mode does not match the canonical plan payload.")

    section_expectations = (
        (
            "## Architectural Seams",
            "PLAN.md architectural seams",
            [f"- `{_string_or_empty(item.get('seam_id'))}`:" for item in seams],
        ),
        (
            "## Parallel Workstreams/Worktrees",
            "PLAN.md workstreams",
            [
                f"- `{_string_or_empty(item.get('workstream_id'))}`:"
                for item in workstreams
            ],
        ),
        (
            "## Executable Slices",
            "PLAN.md executable slices",
            [f"- `{_string_or_empty(item.get('slice_id'))}`:" for item in slices],
        ),
    )
    for heading, label, prefixes in section_expectations:
        if not prefixes:
            continue
        section_text = _find_section(markdown_text, heading)
        if not section_text:
            continue
        errors.extend(
            _validate_markdown_item_order(
                section_text,
                label=label,
                expected_prefixes=prefixes,
            )
        )

    return errors
