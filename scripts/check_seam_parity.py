#!/usr/bin/env python3
"""Cross-run seam parity checker for bounded vs trust summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CHECK_NAMES = (
    "primary_seam_id",
    "primary_seam_paths",
    "secondary_seam_ids",
    "recommendation_seam_bindings",
)
MISSING_CANONICAL_STATE = "missing_canonical_state"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare canonical seam state between bounded and trust summary.json runs."
        )
    )
    parser.add_argument("--bounded-summary", required=True)
    parser.add_argument("--trust-summary", required=True)
    parser.add_argument("--out", default="./seam_parity_report.json")
    return parser


def _read_summary(path_str: str) -> tuple[Path, dict[str, Any] | None, list[str]]:
    path = Path(path_str).expanduser().resolve()
    errors: list[str] = []

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return path, None, [f"{path}: unable to read summary file: {exc}"]

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return path, None, [f"{path}: invalid JSON: {exc}"]

    if not isinstance(payload, dict):
        errors.append(f"{path}: summary root must be a JSON object.")
        return path, None, errors

    return path, payload, errors


def _trimmed_string(value: Any, *, field_name: str, errors: list[str]) -> str | None:
    if not isinstance(value, str):
        errors.append(f"{field_name} must be a string.")
        return None
    trimmed = value.strip()
    if not trimmed:
        errors.append(f"{field_name} must not be empty.")
        return None
    return trimmed


def _is_repo_relative_path(value: str) -> bool:
    if not value:
        return False
    if Path(value).is_absolute():
        return False
    if value == ".." or value.startswith("../"):
        return False
    return True


def _normalize_primary_paths(value: Any, *, errors: list[str]) -> list[str] | None:
    if not isinstance(value, list):
        errors.append("analysis_review_status.primary_seam.paths must be a list.")
        return None

    seen: set[str] = set()
    normalized: list[str] = []
    for index, item in enumerate(value):
        trimmed = _trimmed_string(
            item,
            field_name=f"analysis_review_status.primary_seam.paths[{index}]",
            errors=errors,
        )
        if trimmed is None:
            continue
        if not _is_repo_relative_path(trimmed):
            errors.append(
                "analysis_review_status.primary_seam.paths"
                f"[{index}] must be repo-relative: {trimmed!r}."
            )
            continue
        if trimmed not in seen:
            seen.add(trimmed)
            normalized.append(trimmed)
    return sorted(normalized) if not errors else None


def _normalize_secondary_seam_ids(value: Any, *, errors: list[str]) -> list[str] | None:
    if not isinstance(value, list):
        errors.append(
            "analysis_review_status.secondary_seams_considered must be a list."
        )
        return None

    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(
                "analysis_review_status.secondary_seams_considered"
                f"[{index}] must be an object."
            )
            continue
        trimmed = _trimmed_string(
            item.get("seam_id"),
            field_name=(
                "analysis_review_status.secondary_seams_considered"
                f"[{index}].seam_id"
            ),
            errors=errors,
        )
        if trimmed is not None:
            seen.add(trimmed)
    return sorted(seen) if not errors else None


def _normalize_recommendation_seam_bindings(
    value: Any, *, errors: list[str]
) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        errors.append(
            "analysis_review_status.recommendation_seam_bindings must be a list."
        )
        return None

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(
                "analysis_review_status.recommendation_seam_bindings"
                f"[{index}] must be an object."
            )
            continue

        recommendation_index = item.get("recommendation_index")
        if isinstance(recommendation_index, bool) or not isinstance(
            recommendation_index, int
        ):
            errors.append(
                "analysis_review_status.recommendation_seam_bindings"
                f"[{index}].recommendation_index must be an integer."
            )
            continue

        seam_id = _trimmed_string(
            item.get("seam_id"),
            field_name=(
                "analysis_review_status.recommendation_seam_bindings"
                f"[{index}].seam_id"
            ),
            errors=errors,
        )
        if seam_id is None:
            continue

        normalized.append(
            {
                "recommendation_index": recommendation_index,
                "seam_id": seam_id,
            }
        )

    return (
        sorted(normalized, key=lambda item: item["recommendation_index"])
        if not errors
        else None
    )


def _extract_canonical_state(summary: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    state = {
        "primary_seam_id": None,
        "primary_seam_paths": None,
        "secondary_seam_ids": None,
        "recommendation_seam_bindings": None,
    }
    errors: list[str] = []

    analysis_review_status = summary.get("analysis_review_status")
    if not isinstance(analysis_review_status, dict):
        errors.append("analysis_review_status must be an object.")
        return state, errors

    primary_seam = analysis_review_status.get("primary_seam")
    if not isinstance(primary_seam, dict):
        errors.append("analysis_review_status.primary_seam must be an object.")
        return state, errors

    primary_seam_id = primary_seam.get("seam_id")
    if not isinstance(primary_seam_id, str):
        errors.append("analysis_review_status.primary_seam.seam_id must be a string.")
    elif not primary_seam_id.strip():
        errors.append(
            "analysis_review_status.primary_seam.seam_id must not be empty."
        )
    else:
        state["primary_seam_id"] = primary_seam_id

    state["primary_seam_paths"] = _normalize_primary_paths(
        primary_seam.get("paths"),
        errors=errors,
    )
    state["secondary_seam_ids"] = _normalize_secondary_seam_ids(
        analysis_review_status.get("secondary_seams_considered"),
        errors=errors,
    )
    state["recommendation_seam_bindings"] = _normalize_recommendation_seam_bindings(
        analysis_review_status.get("recommendation_seam_bindings"),
        errors=errors,
    )
    return state, errors


def _build_check(bounded: Any, trust: Any, *, allow_compare: bool) -> dict[str, Any]:
    ok = allow_compare and bounded == trust
    return {"ok": ok, "bounded": bounded, "trust": trust}


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = _build_parser().parse_args()

    bounded_path, bounded_summary, bounded_read_errors = _read_summary(
        args.bounded_summary
    )
    trust_path, trust_summary, trust_read_errors = _read_summary(args.trust_summary)

    bounded_state = {name: None for name in CHECK_NAMES}
    trust_state = {name: None for name in CHECK_NAMES}
    extraction_errors: list[str] = []

    if bounded_summary is not None:
        bounded_state, bounded_errors = _extract_canonical_state(bounded_summary)
        extraction_errors.extend(f"{bounded_path}: {error}" for error in bounded_errors)
    if trust_summary is not None:
        trust_state, trust_errors = _extract_canonical_state(trust_summary)
        extraction_errors.extend(f"{trust_path}: {error}" for error in trust_errors)

    missing_canonical_state = bool(
        bounded_read_errors
        or trust_read_errors
        or extraction_errors
        or bounded_summary is None
        or trust_summary is None
    )

    allow_compare = not missing_canonical_state
    checks = {
        name: _build_check(
            bounded_state.get(name),
            trust_state.get(name),
            allow_compare=allow_compare,
        )
        for name in CHECK_NAMES
    }

    mismatches: list[str] = []
    if missing_canonical_state:
        mismatches.append(MISSING_CANONICAL_STATE)
    else:
        mismatches.extend(name for name in CHECK_NAMES if not checks[name]["ok"])

    report = {
        "ok": not mismatches,
        "bounded_summary": str(bounded_path),
        "trust_summary": str(trust_path),
        "checks": checks,
        "mismatches": mismatches,
    }

    out_path = Path(args.out).expanduser().resolve()
    try:
        _write_report(out_path, report)
    except OSError as exc:
        print(f"{out_path}: unable to write report: {exc}", file=sys.stderr)
        return 1

    for error in bounded_read_errors + trust_read_errors + extraction_errors:
        print(error, file=sys.stderr)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
