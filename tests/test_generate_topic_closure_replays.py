from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_script_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "generate_topic_closure_replays.py"
    spec = importlib.util.spec_from_file_location(
        "forge_generate_topic_closure_replays",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load replay generator from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["forge_generate_topic_closure_replays"] = module
    spec.loader.exec_module(module)
    return module


def _load_summary(run_dir: Path) -> dict:
    return json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _single_run_dir(out_root: Path, pattern: str) -> Path:
    matches = list(out_root.glob(pattern))
    assert len(matches) == 1
    return matches[0]


def _assert_artifact_exists(run_dir: Path, artifact_label: str) -> None:
    assert (run_dir / f"{artifact_label}.json").exists()
    assert (run_dir / f"{artifact_label}.md").exists()


def _assert_contains_exact_line(text: str, expected_line: str) -> None:
    assert expected_line in text.splitlines()


def test_generate_topic_closure_replays_produces_expected_artifacts(tmp_path):
    module = _load_script_module()
    repo_root = Path(__file__).resolve().parents[1]
    out_root = tmp_path / "runs"

    run_dirs = module.generate_replays(repo_root, out_root)

    assert len(run_dirs) == 3
    assert all(run_dir.exists() for run_dir in run_dirs)

    missing_proof_run_dir = _single_run_dir(
        out_root, "*topic_closure_missing_scoped_proof*"
    )
    missing_proof_summary = _load_summary(missing_proof_run_dir)
    missing_proof_report = missing_proof_run_dir / "REPORT.md"

    assert (missing_proof_run_dir / "summary.json").exists()
    assert missing_proof_report.exists()
    assert missing_proof_summary["verdict"] == "harness_error"
    assert missing_proof_summary["artifacts"]["final_artifact_kind"] == "best_draft"
    _assert_artifact_exists(missing_proof_run_dir, "BEST_DRAFT")
    assert missing_proof_summary.get("analysis_review_status") is None

    missing_proof_auditor_stage = next(
        stage
        for stage in missing_proof_summary["agent_stages"]
        if stage["role_name"] == "auditor"
    )
    missing_proof_provenance = missing_proof_auditor_stage[
        "semantic_validation_payload_provenance"
    ]
    assert missing_proof_auditor_stage["failure_kind"] == "semantic_validation_error"
    assert missing_proof_provenance["status"] == "insufficient"
    assert missing_proof_provenance["closure_complete_topic_ids"] == []
    assert missing_proof_provenance["uncovered_global_topic_ids"] == ["TOPIC-001"]
    assert missing_proof_summary["topic_ledger"][0]["resolution_status"] == "open"

    carried_forward_run_dir = _single_run_dir(
        out_root, "*topic_closure_scoped_proof_complete_carried_forward*"
    )
    carried_forward_summary = _load_summary(carried_forward_run_dir)
    carried_forward_report_text = _load_text(carried_forward_run_dir / "REPORT.md")
    carried_forward_status = carried_forward_summary["analysis_review_status"]
    carried_forward_provenance = carried_forward_status["provenance"]

    assert (carried_forward_run_dir / "summary.json").exists()
    assert carried_forward_summary["verdict"] == "needs_revision"
    assert carried_forward_summary["artifacts"]["final_artifact_kind"] == "best_draft"
    _assert_artifact_exists(carried_forward_run_dir, "BEST_DRAFT")
    assert carried_forward_provenance["status"] == "bound"
    assert carried_forward_provenance["closure_complete_topic_ids"] == ["TOPIC-001"]
    assert (
        carried_forward_provenance["closure_proof_by_id"]["TOPIC-001"]["proof_path"]
        == "scoped"
    )
    assert (
        carried_forward_provenance["closure_proof_by_id"]["TOPIC-001"][
            "classification_status"
        ]
        == "carried_forward"
    )
    assert carried_forward_status["carried_forward_topic_ids"] == ["TOPIC-001"]
    assert carried_forward_status["resolved_topic_ids"] == []
    assert (
        carried_forward_summary["topic_ledger"][0]["resolution_status"]
        == "carried_forward"
    )
    _assert_contains_exact_line(
        carried_forward_report_text,
        "  - review topics are carried forward: TOPIC-001",
    )
    assert "review topics remain open: TOPIC-001" not in carried_forward_report_text
    assert "`PARTIAL_ANSWER.*`" not in carried_forward_report_text

    resolved_run_dir = _single_run_dir(
        out_root, "*topic_closure_scoped_proof_complete_resolved*"
    )
    resolved_summary = _load_summary(resolved_run_dir)
    resolved_status = resolved_summary["analysis_review_status"]
    resolved_provenance = resolved_status["provenance"]
    partial_answer_json = _load_json(resolved_run_dir / "PARTIAL_ANSWER.json")
    partial_answer_text = _load_text(resolved_run_dir / "PARTIAL_ANSWER.md")
    resolved_report_text = _load_text(resolved_run_dir / "REPORT.md")

    assert (resolved_run_dir / "summary.json").exists()
    assert resolved_summary["verdict"] == "accepted_with_warnings"
    assert resolved_summary["artifacts"]["final_artifact_kind"] == "partial_answer"
    _assert_artifact_exists(resolved_run_dir, "PARTIAL_ANSWER")
    assert resolved_provenance["status"] == "bound"
    assert resolved_provenance["closure_complete_topic_ids"] == ["TOPIC-001"]
    assert resolved_provenance["closure_proof_by_id"]["TOPIC-001"]["proof_path"] == (
        "scoped"
    )
    assert (
        resolved_provenance["closure_proof_by_id"]["TOPIC-001"][
            "classification_status"
        ]
        == "resolved"
    )
    assert resolved_status["resolved_topic_ids"] == ["TOPIC-001"]
    assert resolved_status["carried_forward_topic_ids"] == []
    assert resolved_summary["topic_ledger"][0]["resolution_status"] == "addressed"
    assert partial_answer_json["included_recommendation_indices"] == [1, 2]
    assert partial_answer_json["excluded_recommendation_indices"] == []
    _assert_contains_exact_line(
        partial_answer_text,
        "- Recommendation indices included in `PARTIAL_ANSWER.*`: `1`, `2`",
    )
    _assert_contains_exact_line(
        partial_answer_text,
        "- Recommendation indices withheld from `FINAL_ANSWER.*`: `2`",
    )
    _assert_contains_exact_line(
        partial_answer_text,
        "- Recommendation indices excluded from `PARTIAL_ANSWER.*`: none",
    )
    _assert_contains_exact_line(
        resolved_report_text,
        "- Recommendation indices withheld from `FINAL_ANSWER.*`: `2`",
    )
    assert "Recommendation indices included in `PARTIAL_ANSWER.*`" not in resolved_report_text
    assert "Recommendation indices excluded from `PARTIAL_ANSWER.*`" not in resolved_report_text
