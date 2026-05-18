from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _load_yaml_module():
    try:
        return importlib.import_module("yaml")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML is required to load Forge YAML config and harness spec files. "
            "Install project dependencies with `poetry install` or run the CLI "
            "via `poetry run python -m anvil.cli ...`."
        ) from exc


def load_structured_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse {p}: {exc.msg}") from exc
    else:
        yaml = _load_yaml_module()
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {p}")
    return data


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    cleaned = SLUG_RE.sub("-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "run"


def tail_text(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return f"...[truncated to last {max_chars} chars]\n{text[-max_chars:]}"


def workspace_glob_paths(
    workspace_root: str | Path,
    pattern: str,
    *,
    include_hidden: bool = False,
) -> list[str]:
    root = Path(workspace_root).resolve()
    normalized_pattern = str(pattern or "").strip()
    if not normalized_pattern:
        return []

    matches: list[str] = []
    seen: set[str] = set()
    for path in root.glob(normalized_pattern):
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if not resolved.is_file():
            continue
        rel_path = resolved.relative_to(root).as_posix()
        if not include_hidden and any(part.startswith(".") for part in resolved.parts):
            continue
        if rel_path in seen:
            continue
        seen.add(rel_path)
        matches.append(rel_path)
    return sorted(matches)


def read_workspace_text(
    workspace_root: str | Path,
    relative_path: str,
    *,
    max_bytes: int | None = None,
) -> str:
    root = Path(workspace_root).resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{relative_path!r} is outside workspace_root") from exc

    if max_bytes is None:
        data = path.read_bytes()
    else:
        with path.open("rb") as handle:
            data = handle.read(max(0, max_bytes))
    return data.decode("utf-8", errors="ignore")
