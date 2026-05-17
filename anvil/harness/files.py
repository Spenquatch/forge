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
