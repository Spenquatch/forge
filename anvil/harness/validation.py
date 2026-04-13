from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from .files import tail_text, write_text
from .types import StrategyConfig, TaskSpec, ValidationRun, ValidatorConfig


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
    if run_when == "mode_allow" and task.workspace_write_policy.mode not in {"allow", "require"}:
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

    missing_paths = [pattern for pattern in validator.requires_paths if not _pattern_matches_any(cwd, pattern)]
    if missing_paths:
        status = _status_from_missing_policy(validator.on_missing_surface)
        return (
            status,
            f"Required workspace surface for validator was not found: {', '.join(missing_paths)}",
            missing_paths,
            missing_binaries,
        )

    missing_binaries = [binary for binary in validator.required_binaries if shutil.which(binary) is None]
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
            stdout_text = exc.stdout or ""
            stderr_text = exc.stderr or ""
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
