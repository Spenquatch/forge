from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_seam_parity.py"
CHECK_NAMES = (
    "primary_seam_id",
    "primary_seam_paths",
    "secondary_seam_ids",
    "recommendation_seam_bindings",
)


def _summary_payload(
    *,
    primary_seam_id: str = "seam-primary",
    primary_paths: list[str] | None = None,
    secondary_seams: list[dict[str, Any]] | None = None,
    recommendation_bindings: list[dict[str, Any]] | None = None,
    final_artifact_kind: str = "final_answer",
    publishability: str = "publishable",
    recommendation_admissibility: str = "admissible",
) -> dict[str, Any]:
    return {
        "analysis_review_status": {
            "primary_seam": {
                "seam_id": primary_seam_id,
                "paths": (
                    primary_paths
                    if primary_paths is not None
                    else ["anvil/harness/runner.py", "anvil/harness/report.py"]
                ),
            },
            "secondary_seams_considered": (
                secondary_seams
                if secondary_seams is not None
                else [{"seam_id": "seam-report"}, {"seam_id": "seam-reporting"}]
            ),
            "recommendation_seam_bindings": (
                recommendation_bindings
                if recommendation_bindings is not None
                else [
                    {"recommendation_index": 1, "seam_id": "seam-primary"},
                    {"recommendation_index": 2, "seam_id": "seam-reporting"},
                ]
            ),
        },
        "publishability": {"status": publishability},
        "recommendation_admissibility": {"status": recommendation_admissibility},
        "final_artifact_kind": final_artifact_kind,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_checker(
    *,
    bounded_summary: Path,
    trust_summary: Path,
    cwd: Path,
    out: str | Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, dict[str, Any]]:
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--bounded-summary",
        str(bounded_summary),
        "--trust-summary",
        str(trust_summary),
    ]
    if out is not None:
        command.extend(["--out", str(out)])

    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )

    if out is None:
        report_path = (cwd / "seam_parity_report.json").resolve()
    else:
        report_path = Path(out)
        if not report_path.is_absolute():
            report_path = (cwd / report_path).resolve()
        else:
            report_path = report_path.resolve()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    return result, report_path, report


def test_checker_writes_default_report_and_ignores_allowed_divergence(
    tmp_path: Path,
) -> None:
    bounded_summary = tmp_path / "bounded-summary.json"
    trust_summary = tmp_path / "trust-summary.json"

    _write_json(
        bounded_summary,
        _summary_payload(
            primary_paths=[
                " anvil/harness/report.py ",
                "anvil/harness/runner.py",
                "anvil/harness/report.py",
            ],
            secondary_seams=[
                {"seam_id": " seam-reporting "},
                {"seam_id": "seam-report"},
                {"seam_id": "seam-report"},
            ],
            recommendation_bindings=[
                {
                    "recommendation_index": 2,
                    "seam_id": " seam-reporting ",
                    "seam_expansion_reason": "Kept only in the full report.",
                },
                {
                    "recommendation_index": 1,
                    "seam_id": "seam-primary",
                    "seam_expansion_reason": "",
                },
            ],
            final_artifact_kind="final_answer",
            publishability="publishable",
            recommendation_admissibility="admissible",
        ),
    )
    _write_json(
        trust_summary,
        _summary_payload(
            primary_paths=["anvil/harness/runner.py", "anvil/harness/report.py"],
            secondary_seams=[
                {"seam_id": "seam-report"},
                {"seam_id": "seam-reporting"},
            ],
            recommendation_bindings=[
                {
                    "recommendation_index": 1,
                    "seam_id": "seam-primary",
                    "seam_expansion_reason": "Different text should be ignored.",
                },
                {
                    "recommendation_index": 2,
                    "seam_id": "seam-reporting",
                    "seam_expansion_reason": "",
                },
            ],
            final_artifact_kind="partial_only",
            publishability="blocked",
            recommendation_admissibility="rejected",
        ),
    )

    result, report_path, report = _run_checker(
        bounded_summary=bounded_summary,
        trust_summary=trust_summary,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert report_path == (tmp_path / "seam_parity_report.json").resolve()
    assert report == {
        "ok": True,
        "bounded_summary": str(bounded_summary.resolve()),
        "trust_summary": str(trust_summary.resolve()),
        "checks": {
            "primary_seam_id": {
                "ok": True,
                "bounded": "seam-primary",
                "trust": "seam-primary",
            },
            "primary_seam_paths": {
                "ok": True,
                "bounded": [
                    "anvil/harness/report.py",
                    "anvil/harness/runner.py",
                ],
                "trust": [
                    "anvil/harness/report.py",
                    "anvil/harness/runner.py",
                ],
            },
            "secondary_seam_ids": {
                "ok": True,
                "bounded": ["seam-report", "seam-reporting"],
                "trust": ["seam-report", "seam-reporting"],
            },
            "recommendation_seam_bindings": {
                "ok": True,
                "bounded": [
                    {"recommendation_index": 1, "seam_id": "seam-primary"},
                    {"recommendation_index": 2, "seam_id": "seam-reporting"},
                ],
                "trust": [
                    {"recommendation_index": 1, "seam_id": "seam-primary"},
                    {"recommendation_index": 2, "seam_id": "seam-reporting"},
                ],
            },
        },
        "mismatches": [],
    }


def test_checker_honors_custom_out_path(tmp_path: Path) -> None:
    bounded_summary = tmp_path / "bounded-summary.json"
    trust_summary = tmp_path / "trust-summary.json"
    out_path = Path("reports/custom/seam-report.json")

    _write_json(bounded_summary, _summary_payload())
    _write_json(
        trust_summary,
        _summary_payload(final_artifact_kind="partial_only"),
    )

    result, report_path, report = _run_checker(
        bounded_summary=bounded_summary,
        trust_summary=trust_summary,
        cwd=tmp_path,
        out=out_path,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert report_path == (tmp_path / out_path).resolve()
    assert report_path.is_file()
    assert report["ok"] is True


def test_checker_reports_invalid_json_as_missing_canonical_state(
    tmp_path: Path,
) -> None:
    bounded_summary = tmp_path / "bounded-summary.json"
    trust_summary = tmp_path / "trust-summary.json"

    bounded_summary.write_text("{not valid json\n", encoding="utf-8")
    _write_json(trust_summary, _summary_payload())

    result, _, report = _run_checker(
        bounded_summary=bounded_summary,
        trust_summary=trust_summary,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "invalid JSON" in result.stderr
    assert report["ok"] is False
    assert report["mismatches"] == ["missing_canonical_state"]
    assert all(report["checks"][name]["ok"] is False for name in CHECK_NAMES)
    assert report["checks"]["primary_seam_id"] == {
        "ok": False,
        "bounded": None,
        "trust": "seam-primary",
    }


def test_checker_reports_missing_canonical_state_when_analysis_status_absent(
    tmp_path: Path,
) -> None:
    bounded_summary = tmp_path / "bounded-summary.json"
    trust_summary = tmp_path / "trust-summary.json"

    _write_json(bounded_summary, {"final_artifact_kind": "final_answer"})
    _write_json(trust_summary, _summary_payload())

    result, _, report = _run_checker(
        bounded_summary=bounded_summary,
        trust_summary=trust_summary,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "analysis_review_status must be an object." in result.stderr
    assert report["ok"] is False
    assert report["mismatches"] == ["missing_canonical_state"]
    assert report["checks"]["primary_seam_id"] == {
        "ok": False,
        "bounded": None,
        "trust": "seam-primary",
    }


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        (
            "primary_seam_id",
            lambda summary: summary["analysis_review_status"][
                "primary_seam"
            ].__setitem__("seam_id", "seam-drifted"),
        ),
        (
            "primary_seam_paths",
            lambda summary: summary["analysis_review_status"][
                "primary_seam"
            ].__setitem__("paths", ["anvil/harness/cli.py"]),
        ),
        (
            "secondary_seam_ids",
            lambda summary: summary["analysis_review_status"].__setitem__(
                "secondary_seams_considered", [{"seam_id": "seam-drifted"}]
            ),
        ),
        (
            "recommendation_seam_bindings",
            lambda summary: summary["analysis_review_status"].__setitem__(
                "recommendation_seam_bindings",
                [{"recommendation_index": 1, "seam_id": "seam-drifted"}],
            ),
        ),
    ],
)
def test_checker_reports_exact_mismatch_labels_for_seam_drift(
    tmp_path: Path,
    label: str,
    mutate,
) -> None:
    bounded_summary = tmp_path / "bounded-summary.json"
    trust_summary = tmp_path / "trust-summary.json"

    bounded_payload = _summary_payload()
    trust_payload = copy.deepcopy(bounded_payload)
    mutate(trust_payload)

    _write_json(bounded_summary, bounded_payload)
    _write_json(trust_summary, trust_payload)

    result, _, report = _run_checker(
        bounded_summary=bounded_summary,
        trust_summary=trust_summary,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == ""
    assert report["ok"] is False
    assert report["mismatches"] == [label]

    for check_name in CHECK_NAMES:
        assert report["checks"][check_name]["ok"] is (check_name != label)
