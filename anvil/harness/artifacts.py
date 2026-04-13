from __future__ import annotations

"""Run-directory and artifact reference helpers for harness executions."""

import datetime as dt
from pathlib import Path
from typing import Any
from uuid import uuid4

from .files import slugify


def create_run_id(task_id: str) -> str:
    return f"{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}-{slugify(task_id)}-{uuid4().hex[:8]}"


def ensure_run_dirs(out_root: str | Path, task_id: str, run_id: str | None = None) -> dict[str, str]:
    root = Path(out_root).resolve()
    run_identifier = run_id or create_run_id(task_id)
    run_dir = root / run_identifier
    validators_dir = run_dir / "validators"
    artifacts_dir = run_dir / "artifacts"
    validators_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": run_identifier,
        "run_dir": str(run_dir),
        "validators_dir": str(validators_dir),
        "artifacts_dir": str(artifacts_dir),
    }


def register_artifact(
    artifact_index: dict[str, dict[str, str]],
    key: str,
    path: str | Path,
    *,
    kind: str,
    description: str,
) -> None:
    artifact_index[key] = {
        "kind": kind,
        "path": str(path),
        "description": description,
    }


def build_artifact_index(artifacts: dict[str, Any]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for key, value in artifacts.items():
        if not value:
            continue
        register_artifact(index, str(key), str(value), kind=str(key), description=str(key).replace("_", " "))
    return index
