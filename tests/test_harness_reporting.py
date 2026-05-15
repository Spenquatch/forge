from __future__ import annotations

import copy
import json
from pathlib import Path

from anvil.harness.contracts import (
    canonical_artifact_focus_id,
    canonical_seam_id_for_paths,
)
from anvil.harness.nodes.write_artifacts import write_artifacts_node
from anvil.harness.report import render_report
from anvil.harness.reporting import (
    _artifact_label_for_kind,
    apply_final_artifacts,
    build_partial_answer_payload,
    render_deliverable_markdown,
    summary_projection_v1,
    write_state_artifacts,
)
from anvil.harness.state import state_from_summary


def _rendered_section(markdown: str, heading_prefix: str) -> str:
    section = markdown.split(heading_prefix, 1)[1]
    if "\n### " in section:
        section = section.split("\n### ", 1)[0]
    return section


def _top_level_section(markdown: str, heading: str) -> str:
    section = markdown.split(heading, 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    return section


def _best_draft_record(payload: dict[str, object]) -> dict[str, object]:
    return {
        "draft_id": "draft-clean",
        "review_status": "accepted",
        "review_state": "evaluated",
        "round_index": 0,
        "summary": str(payload.get("summary") or ""),
        "issue_counts": {
            "blocking_medium_or_higher": 0,
            "medium_or_higher": 0,
            "accepted_recommendations": len(payload.get("recommendations") or []),
            "required_validator_failures": 0,
            "topics": 0,
            "open_topics": 0,
        },
        "scores": {
            "grounding_score": 0.72,
            "actionability_score": 0.81,
            "scope_compliance_score": 0.88,
        },
        "metadata": {"stage_index": 1, "payload": payload},
    }


def _section_payload_with_redundant_none_reason() -> dict[str, object]:
    return {
        "summary": "Payload with populated and empty analysis sections.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Document fallback handling",
                "rationale": "Operators need an explicit fallback path.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
        "strengths": {
            "items": ["Grounded in workflow files"],
            "none_reason": "This stale schema text should not leak.",
        },
        "uncertainties": {
            "items": [],
            "none_reason": "No material uncertainties remained after comparing the relevant files.",
        },
    }


def _first_line(path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0]


def _with_nested_analysis_status(summary: dict[str, object]) -> dict[str, object]:
    enriched = copy.deepcopy(summary)
    analysis_status = enriched.get("analysis_review_status")
    if isinstance(analysis_status, dict):
        run_details = dict(enriched.get("run_details") or {})
        run_details["analysis_review_status"] = copy.deepcopy(analysis_status)
        enriched["run_details"] = run_details
    return enriched


def _summary_json(tmp_path) -> dict[str, object]:
    return json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))


def _focus_stage_record(
    tmp_path, *, raw_payload: dict[str, object], normalized_payload: dict[str, object]
) -> dict[str, object]:
    stage_dir = tmp_path / "01_focus_gate"
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_path = stage_dir / "structured_output.raw.json"
    normalized_path = stage_dir / "structured_output.normalized.json"
    stdout_path = stage_dir / "response.txt"
    raw_path.write_text(
        json.dumps(raw_payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    normalized_path.write_text(
        json.dumps(normalized_payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    stdout_path.write_text("ok", encoding="utf-8")
    (stage_dir / "run.envelope.json").write_text(
        json.dumps(
            {
                "role_name": "focus_gate",
                "structured_output": {
                    **normalized_payload,
                    "confidence_band": "medium",
                },
                "metadata": {
                    "focus_gate": {
                        "gate_path": normalized_payload["gate_path"],
                        "focus_type": normalized_payload["focus_type"],
                        "decision_state": normalized_payload["decision_state"],
                    }
                },
            },
            indent=2,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return {
        "stage_index": 1,
        "role_name": "focus_gate",
        "stdout_path": str(stdout_path),
        "raw_output_path": str(raw_path),
        "normalized_output_path": str(normalized_path),
        "output_path": str(normalized_path),
    }


def _analysis_publishability(summary: dict[str, object]) -> dict[str, object]:
    return (summary.get("analysis_review_status") or {}).get("publishability") or {}


def _nested_analysis_publishability(summary: dict[str, object]) -> dict[str, object]:
    return ((summary.get("run_details") or {}).get("analysis_review_status") or {}).get(
        "publishability"
    ) or {}


def _selected_focus_decision() -> dict[str, object]:
    selected_focus_paths = [".github/workflows/codex-cli-release-watch.yml"]
    return {
        "gate_path": "adjudicate",
        "focus_type": "seam",
        "decision_state": "selected",
        "decision_basis": "request_only",
        "selected_focus_id": "release-trigger-automation",
        "selected_focus_summary": "Use the release trigger automation seam as the primary focus.",
        "selected_focus_paths": selected_focus_paths,
        "confidence": 0.91,
        "confidence_band": "high",
        "files_hint_disposition": "absent",
        "checked_files": [],
        "candidates": [
            {
                "focus_id": "release-trigger-automation",
                "focus_summary": "Primary release trigger workflow seam.",
                "candidate_paths": [".github/workflows/codex-cli-release-watch.yml"],
                "why_candidate": "The release workflow remains the governing seam.",
                "evidence_refs": [],
                "score": 0.91,
            },
            {
                "focus_id": "rollback-runbook",
                "focus_summary": "Fallback operational seam.",
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "The rollback path remains a plausible sibling seam.",
                "evidence_refs": [],
                "score": 0.62,
            },
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [],
        "adapter_plan": {
            "primary_focus_id": "release-trigger-automation",
            "secondary_focus_ids": ["rollback-runbook"],
            "downstream_primary_seam_id": canonical_seam_id_for_paths(
                selected_focus_paths
            ),
            "downstream_primary_seam_paths": selected_focus_paths,
            "adaptation_basis": "selected_focus_paths",
        },
    }


def _artifact_selected_focus_decision() -> dict[str, object]:
    selected_focus_path = ".github/workflows/codex-cli-release-watch.yml"
    return {
        "gate_path": "adjudicate",
        "focus_type": "artifact",
        "decision_state": "selected",
        "decision_basis": "request_only",
        "selected_focus_id": canonical_artifact_focus_id(selected_focus_path),
        "selected_focus_summary": "Use the release trigger workflow artifact as the primary focus.",
        "selected_focus_paths": [selected_focus_path],
        "confidence": 0.91,
        "confidence_band": "high",
        "files_hint_disposition": "absent",
        "checked_files": [],
        "candidates": [
            {
                "focus_id": canonical_artifact_focus_id(selected_focus_path),
                "focus_summary": "Primary release trigger workflow artifact.",
                "candidate_paths": [selected_focus_path],
                "why_candidate": "The release workflow file remains the governing artifact.",
                "evidence_refs": [],
                "score": 0.91,
            }
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [],
        "adapter_plan": {
            "primary_focus_id": canonical_artifact_focus_id(selected_focus_path),
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": canonical_seam_id_for_paths(
                [selected_focus_path]
            ),
            "downstream_primary_seam_paths": [selected_focus_path],
            "adaptation_basis": "artifact_singleton",
        },
    }


def _clarification_focus_decision() -> dict[str, object]:
    return {
        "gate_path": "deliberate",
        "focus_type": "seam",
        "decision_state": "clarification_requested",
        "decision_basis": "repo_probe",
        "selected_focus_id": None,
        "selected_focus_summary": None,
        "selected_focus_paths": [],
        "confidence": 0.41,
        "confidence_band": "low",
        "files_hint_disposition": "helped",
        "checked_files": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/rollback-runbook.md",
        ],
        "candidates": [
            {
                "focus_id": "release-trigger-automation",
                "focus_summary": "Release workflow seam.",
                "candidate_paths": [".github/workflows/codex-cli-release-watch.yml"],
                "why_candidate": "The release workflow still looks dominant.",
                "evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
                "score": 0.54,
            },
            {
                "focus_id": "rollback-runbook",
                "focus_summary": "Rollback workflow seam.",
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "The rollback seam is still plausible.",
                "evidence_refs": [".github/workflows/rollback-runbook.md"],
                "score": 0.47,
            },
        ],
        "question": {
            "prompt": "Which focus should this run prioritize?",
            "options": [
                "release-trigger-automation",
                "rollback-runbook",
            ],
        },
        "warnings": ["The task mixes release and rollback concerns."],
        "adapter_plan": {
            "primary_focus_id": None,
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        },
    }


def _no_viable_focus_decision() -> dict[str, object]:
    return {
        "gate_path": "adjudicate",
        "focus_type": "seam",
        "decision_state": "no_viable_focus",
        "decision_basis": "request_only",
        "selected_focus_id": None,
        "selected_focus_summary": None,
        "selected_focus_paths": [],
        "confidence": 0.18,
        "confidence_band": "low",
        "files_hint_disposition": "absent",
        "checked_files": [],
        "candidates": [],
        "question": {"prompt": "", "options": []},
        "warnings": [
            "No seam candidate had enough direct workspace evidence.",
        ],
        "adapter_plan": {
            "primary_focus_id": None,
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        },
    }


def _stale_no_viable_focus_decision() -> dict[str, object]:
    return {
        "gate_path": "deliberate",
        "focus_type": "seam",
        "decision_state": "no_viable_focus",
        "decision_basis": "rerun_answer",
        "selected_focus_id": None,
        "selected_focus_summary": None,
        "selected_focus_paths": [],
        "confidence": 0.54,
        "confidence_band": "low",
        "files_hint_disposition": "helped",
        "checked_files": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/rollback-runbook.md",
        ],
        "candidates": [
            {
                "focus_id": "release-trigger-automation",
                "focus_summary": "Release workflow seam.",
                "candidate_paths": [".github/workflows/codex-cli-release-watch.yml"],
                "why_candidate": "The release seam still exists, but the rerun answer went stale.",
                "evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
                "score": 0.54,
            },
            {
                "focus_id": "rollback-runbook",
                "focus_summary": "Rollback workflow seam.",
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "The rollback seam remains a plausible sibling.",
                "evidence_refs": [".github/workflows/rollback-runbook.md"],
                "score": 0.49,
            },
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [
            "Prior focus_gate_answer went stale: current probe is ambiguous under selection thresholds.",
        ],
        "adapter_plan": {
            "primary_focus_id": None,
            "secondary_focus_ids": [
                "release-trigger-automation",
                "rollback-runbook",
            ],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        },
    }


def _auto_refined_selected_focus_decision() -> dict[str, object]:
    selected_focus_paths = [".github/workflows/codex-cli-release-watch.yml"]
    return {
        "gate_path": "deliberate",
        "focus_type": "seam",
        "decision_state": "selected",
        "decision_basis": "repo_probe",
        "selected_focus_id": "release-watch-slice",
        "selected_focus_summary": "Use the narrowed release watch workflow slice as the primary focus.",
        "selected_focus_paths": selected_focus_paths,
        "confidence": 0.74,
        "confidence_band": "medium",
        "files_hint_disposition": "helped",
        "checked_files": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/rollback-runbook.md",
        ],
        "candidates": [
            {
                "focus_id": "release-watch-slice",
                "focus_summary": "Narrowed release watch workflow slice.",
                "candidate_paths": selected_focus_paths,
                "why_candidate": "This is the narrowest codex-specific slice of the winning umbrella seam.",
                "evidence_refs": selected_focus_paths,
                "score": 0.74,
            },
            {
                "focus_id": "rollback-runbook-slice",
                "focus_summary": "Fallback rollback slice.",
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "This is the next-best bounded slice inside the same winning umbrella seam.",
                "evidence_refs": [".github/workflows/rollback-runbook.md"],
                "score": 0.71,
            },
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [],
        "adapter_plan": {
            "primary_focus_id": "release-watch-slice",
            "secondary_focus_ids": ["rollback-runbook-slice"],
            "downstream_primary_seam_id": canonical_seam_id_for_paths(
                selected_focus_paths
            ),
            "downstream_primary_seam_paths": selected_focus_paths,
            "adaptation_basis": "selected_focus_paths",
        },
    }


def _applied_focus_refinement() -> dict[str, object]:
    return {
        "status": "applied",
        "trigger_reason": "umbrella_selected_checked_files",
        "source_selected_focus_id": "release-automation-umbrella",
        "source_selected_focus_paths": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/rollback-runbook.md",
        ],
        "candidate_shortlist_ids": [
            "release-watch-slice",
            "rollback-runbook-slice",
        ],
        "attempted_candidate_ids": ["release-watch-slice"],
        "rejected_candidates": [],
        "selected_candidate_id": "release-watch-slice",
        "selected_candidate_paths": [
            ".github/workflows/codex-cli-release-watch.yml",
        ],
        "exhausted_reason": None,
        "rerun_guidance": [
            {
                "focus_id": "release-watch-slice",
                "score": 0.74,
                "candidate_paths": [
                    ".github/workflows/codex-cli-release-watch.yml",
                ],
                "why_candidate": "This is the narrowest codex-specific slice of the winning umbrella seam.",
            },
            {
                "focus_id": "rollback-runbook-slice",
                "score": 0.71,
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "This is the next-best bounded slice inside the same winning umbrella seam.",
            },
        ],
    }


def _exhausted_refinement_no_viable_focus_decision() -> dict[str, object]:
    return {
        "gate_path": "deliberate",
        "focus_type": "seam",
        "decision_state": "no_viable_focus",
        "decision_basis": "repo_probe",
        "selected_focus_id": None,
        "selected_focus_summary": None,
        "selected_focus_paths": [],
        "confidence": 0.18,
        "confidence_band": "low",
        "files_hint_disposition": "helped",
        "checked_files": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/rollback-runbook.md",
        ],
        "candidates": [
            {
                "focus_id": "release-watch-slice",
                "focus_summary": "Narrowed release watch workflow slice.",
                "candidate_paths": [".github/workflows/codex-cli-release-watch.yml"],
                "why_candidate": "This is the narrowest codex-specific slice of the winning umbrella seam.",
                "evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
                "score": 0.74,
            },
            {
                "focus_id": "rollback-runbook-slice",
                "focus_summary": "Fallback rollback slice.",
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "This is the next-best bounded slice inside the same winning umbrella seam.",
                "evidence_refs": [".github/workflows/rollback-runbook.md"],
                "score": 0.71,
            },
        ],
        "question": {"prompt": "", "options": []},
        "warnings": [
            "Selected repo-probe focus remained too broad after bounded refinement; rerun with one of the narrower files_hint slices.",
        ],
        "adapter_plan": {
            "primary_focus_id": None,
            "secondary_focus_ids": [],
            "downstream_primary_seam_id": None,
            "downstream_primary_seam_paths": [],
            "adaptation_basis": None,
        },
    }


def _exhausted_focus_refinement() -> dict[str, object]:
    return {
        "status": "exhausted",
        "trigger_reason": "collapsed_narrower_subset",
        "source_selected_focus_id": "release-automation-umbrella",
        "source_selected_focus_paths": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/rollback-runbook.md",
        ],
        "candidate_shortlist_ids": [
            "release-watch-slice",
            "rollback-runbook-slice",
        ],
        "attempted_candidate_ids": [
            "release-watch-slice",
            "rollback-runbook-slice",
        ],
        "rejected_candidates": [
            {
                "focus_id": "release-watch-slice",
                "reason": "downstream_bridge_drift",
            },
            {
                "focus_id": "rollback-runbook-slice",
                "reason": "canonical_drift",
            },
        ],
        "selected_candidate_id": None,
        "selected_candidate_paths": [],
        "exhausted_reason": "no_candidate_survived_validation",
        "rerun_guidance": [
            {
                "focus_id": "release-watch-slice",
                "score": 0.74,
                "candidate_paths": [
                    ".github/workflows/codex-cli-release-watch.yml",
                ],
                "why_candidate": "This is the narrowest codex-specific slice of the winning umbrella seam.",
            },
            {
                "focus_id": "rollback-runbook-slice",
                "score": 0.71,
                "candidate_paths": [".github/workflows/rollback-runbook.md"],
                "why_candidate": "This is the next-best bounded slice inside the same winning umbrella seam.",
            },
        ],
    }


def _assert_publication_parity(summary: dict[str, object]) -> None:
    expected_publishable = (summary.get("artifacts") or {}).get(
        "final_artifact_kind"
    ) == "final_answer"
    assert (
        _analysis_publishability(summary).get("final_answer_publishable")
        == expected_publishable
    )
    nested_publishability = _nested_analysis_publishability(summary)
    if nested_publishability:
        assert (
            nested_publishability.get("final_answer_publishable")
            == expected_publishable
        )


def _assert_report_publication_state(report: str, expected_state: str) -> None:
    expected_line = f"- Publication outcome: `{expected_state}`"
    assert expected_line in _top_level_section(report, "## Overview")
    assert expected_line in _top_level_section(report, "## Analysis Review Status")


def _assert_report_execution_mode(report: str, expected_mode: str) -> None:
    expected_line = f"- Execution mode: `{expected_mode}`"
    assert expected_line in _top_level_section(report, "## Overview")
    analysis_review_status_section = _top_level_section(
        report, "## Analysis Review Status"
    )
    if analysis_review_status_section:
        assert expected_line in analysis_review_status_section


def test_render_deliverable_markdown_attaches_caveats_to_affected_recommendations():
    payload = {
        "summary": "Prioritized recommendations.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "high",
                "title": "Tighten retry policy",
                "rationale": "Current retries can duplicate releases.",
                "evidence": ["a.py"],
                "proposed_change": "Reduce retry fanout.",
                "confidence": 0.78,
            },
            {
                "classification": "risk",
                "priority": "medium",
                "title": "Document fallback path",
                "rationale": "Fallback behavior is inferred from adjacent workflow logic.",
                "evidence": ["b.py"],
                "proposed_change": "Describe the fallback explicitly.",
                "confidence": 0.64,
            },
            {
                "classification": "recommendation",
                "priority": "low",
                "title": "Normalize logging labels",
                "rationale": "Labels diverge across handlers.",
                "evidence": ["c.py"],
                "proposed_change": "Align the label set.",
                "confidence": 0.82,
            },
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "recommendation_reviews": [
            {
                "recommendation_index": 1,
                "verdict": "accept_with_caveat",
                "summary": "Useful recommendation with a caveat about rollout timing.",
            },
            {
                "recommendation_index": 2,
                "verdict": "accept",
                "summary": "Acceptable, but grounded by inference.",
            },
            {
                "recommendation_index": 3,
                "verdict": "accept",
                "summary": "Fully grounded.",
            },
        ],
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "downgrade_causes": [
                "accepted recommendations rely on inference-only grounding: 2"
            ],
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "accepted_recommendations_with_inferred_grounding": [2],
        },
    }

    markdown = render_deliverable_markdown(
        "task-123",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    recommendation_one = _rendered_section(markdown, "### 1. Tighten retry policy")
    recommendation_two = _rendered_section(markdown, "### 2. Document fallback path")
    recommendation_three = _rendered_section(
        markdown, "### 3. Normalize logging labels"
    )

    assert "This recommendation carries review caveats:" in recommendation_one
    assert (
        "Useful recommendation with a caveat about rollout timing."
        in recommendation_one
    )
    assert "inference-only grounding" not in recommendation_one

    assert "This recommendation carries review caveats:" in recommendation_two
    assert (
        "This recommendation relies on inference-only grounding rather than direct verified evidence."
        in recommendation_two
    )

    assert "This recommendation carries review caveats:" not in recommendation_three


def test_render_deliverable_markdown_uses_original_indices_for_partial_answers():
    payload = {
        "summary": "Partial acceptance output.",
        "included_recommendation_indices": [2, 3],
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Second original recommendation",
                "rationale": "Carries a reviewer caveat.",
                "evidence": ["b.py"],
                "proposed_change": "Adjust rollout docs.",
                "confidence": 0.66,
            },
            {
                "classification": "risk",
                "priority": "medium",
                "title": "Third original recommendation",
                "rationale": "Accepted with inference-only grounding.",
                "evidence": ["c.py"],
                "proposed_change": "Narrow the claim.",
                "confidence": 0.59,
            },
        ],
    }
    summary = {
        "verdict": "accepted_partial",
        "recommendation_reviews": [
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Retain this recommendation, but validate rollout ordering before landing it.",
            },
            {
                "recommendation_index": 3,
                "verdict": "accept",
                "summary": "Grounding is weaker than the first item.",
            },
        ],
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "downgrade_causes": [
                "accepted recommendations rely on inference-only grounding: 3"
            ],
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "accepted_recommendations_with_inferred_grounding": [3],
        },
    }

    markdown = render_deliverable_markdown(
        "task-456",
        payload,
        artifact_kind="partial_answer",
        artifact_label="PARTIAL_ANSWER",
        accepted=False,
        summary=summary,
    )

    recommendation_one = _rendered_section(
        markdown, "### 2. Second original recommendation"
    )
    recommendation_two = _rendered_section(
        markdown, "### 3. Third original recommendation"
    )

    assert "validate rollout ordering before landing it" in recommendation_one
    assert (
        "This recommendation relies on inference-only grounding rather than direct verified evidence."
        in recommendation_two
    )


def test_render_deliverable_markdown_adds_admissibility_withholding_note_for_partial_fallback():
    payload = {
        "summary": "Partial fallback output.",
        "included_recommendation_indices": [1, 2],
        "excluded_recommendation_indices": [3],
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "First recommendation",
                "rationale": "Final-admissible.",
                "evidence": ["a.py"],
                "proposed_change": "Ship it.",
                "confidence": 0.66,
            },
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Second recommendation",
                "rationale": "Only partial-admissible.",
                "evidence": ["b.py"],
                "proposed_change": "Ship with caveat.",
                "confidence": 0.62,
            },
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[3],
            reasons_by_index={
                "2": ["accepted_with_caveat"],
                "3": ["topic_blocked"],
            },
        ),
    }

    markdown = render_deliverable_markdown(
        "task-789",
        payload,
        artifact_kind="partial_answer",
        artifact_label="PARTIAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert markdown.index(
        "> Recommendation indices withheld from `FINAL_ANSWER.*`:"
    ) < markdown.index("## Review Status")
    assert "> - `2`: `accepted_with_caveat`" in markdown
    assert "> - `3`: `topic_blocked`" in markdown
    assert "> Publication blockers:" not in markdown


def test_render_deliverable_markdown_sanitizes_recommendation_caveat_claims():
    payload = {
        "summary": "Accepted recommendations.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "high",
                "title": "Clarify release policy",
                "rationale": "The rollout policy still needs tightening.",
                "evidence": ["release.py"],
                "proposed_change": "Document the exact release gate.",
                "confidence": 0.81,
            }
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "recommendation_reviews": [
            {
                "recommendation_index": 1,
                "verdict": "accept_with_caveat",
                "summary": "This recommendation is publication-ready and can ship as the final artifact.",
            }
        ],
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "downgrade_causes": [],
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
        },
    }

    markdown = render_deliverable_markdown(
        "task-authority-caveat",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    recommendation = _rendered_section(markdown, "### 1. Clarify release policy")

    assert "publication-ready" not in recommendation.lower()
    assert "final artifact" not in recommendation.lower()
    assert (
        "Runner note: review summary withheld because publication eligibility is runner-owned."
        in recommendation
    )


def test_render_deliverable_markdown_omits_none_reason_label_in_analysis_sections():
    markdown = render_deliverable_markdown(
        "task-sections",
        _section_payload_with_redundant_none_reason(),
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary={"analysis_review_status": {"mode": "bounded"}},
    )

    strengths = _rendered_section(markdown, "## Strengths")
    uncertainties = _rendered_section(markdown, "## Uncertainties")

    assert "- Grounded in workflow files" in strengths
    assert "This stale schema text should not leak." not in strengths
    assert (
        "No material uncertainties remained after comparing the relevant files."
        in uncertainties
    )
    assert "none_reason:" not in markdown


def test_render_deliverable_markdown_compacts_recommendation_evidence_preview():
    payload = {
        "summary": "Accepted recommendations with long evidence lists.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify fallback handling",
                "rationale": "Operators need a direct fallback rule.",
                "evidence": ["a.py", "b.py", "c.py", "d.py"],
                "proposed_change": "Document the fallback rule explicitly.",
                "confidence": 0.74,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-evidence-preview",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary={"analysis_review_status": {"mode": "bounded"}},
    )

    recommendation = _rendered_section(markdown, "### 1. Clarify fallback handling")

    assert "- a.py" in recommendation
    assert "- b.py" in recommendation
    assert "- c.py" in recommendation
    assert "- (+1 more)" in recommendation
    assert "- d.py" not in recommendation


def test_build_partial_answer_payload_filters_topic_blocked_accepted_recommendations():
    payload = {
        "summary": "Partial acceptance output.",
        "recommendations": [
            {
                "title": "First",
                "classification": "recommendation",
                "priority": "medium",
            },
            {
                "title": "Second",
                "classification": "recommendation",
                "priority": "medium",
            },
            {
                "title": "Third",
                "classification": "recommendation",
                "priority": "medium",
            },
        ],
    }
    summary = {
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Carries topic debt.",
            },
            {"recommendation_index": 3, "verdict": "accept", "summary": "Clean."},
        ],
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "resolution_status": "carried_forward",
                "recommendation_index": 2,
            }
        ],
    }

    partial_payload = build_partial_answer_payload(summary, payload)

    assert partial_payload is not None
    assert partial_payload["included_recommendation_indices"] == [1, 3]
    assert partial_payload["excluded_recommendation_indices"] == [2]
    assert [item["title"] for item in partial_payload["recommendations"]] == [
        "First",
        "Third",
    ]
    assert [
        item["recommendation_index"]
        for item in partial_payload["recommendation_reviews"]
    ] == [1, 3]


def test_build_partial_answer_payload_returns_none_when_trust_provenance_is_incomplete():
    payload = {
        "summary": "Partial acceptance output.",
        "recommendations": [
            {
                "title": "First",
                "classification": "recommendation",
                "priority": "medium",
            },
            {
                "title": "Second",
                "classification": "recommendation",
                "priority": "medium",
            },
        ],
    }
    summary = {
        "verdict": "accepted_partial",
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept", "summary": "Also clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
        },
        "topic_ledger": [],
    }

    partial_payload = build_partial_answer_payload(summary, payload)

    assert partial_payload is None


def test_render_deliverable_markdown_names_uncovered_recommendation_indices_in_trust_mode():
    payload = {
        "summary": "Accepted recommendations with incomplete trust provenance.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify operator fallback path",
                "rationale": "Operators need a concrete fallback path.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "analysis_review_status": {
            "mode": "trust",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "uncovered_recommendation_indices": [1, 2],
                "uncovered_global_issue_ids": ["AR-001"],
                "uncovered_global_topic_ids": ["TOPIC-001"],
            },
            "topic_ledger_count": 0,
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
    }

    markdown = render_deliverable_markdown(
        "task-trust-incomplete",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert (
        "- Closure proof incomplete: recommendation-linked closures for recommendation indices 1, 2; uncovered global issue closures: AR-001; uncovered global topic closures: TOPIC-001"
        in markdown
    )


def test_apply_final_artifacts_scopes_partial_answer_review_status_to_included_recommendations(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-scope"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "strengths": {
                "items": ["Grounded in workflow files"],
                "none_reason": "This stale schema text should not leak.",
            },
            "summary": "Partial acceptance output.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Clean recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Carries excluded topic debt.",
                    "evidence": ["b.py"],
                    "proposed_change": "Do not ship this one.",
                    "confidence": 0.62,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Third",
                    "rationale": "Included, but inference-backed.",
                    "evidence": ["c.py"],
                    "proposed_change": "Ship with narrower claim.",
                    "confidence": 0.58,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Carries topic debt.",
            },
            {
                "recommendation_index": 3,
                "verdict": "accept",
                "summary": "Inference-backed.",
            },
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "accepted_recommendations_with_inferred_grounding": [3],
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": [
                "review topics are carried forward: TOPIC-001",
                "accepted recommendation reviews include accept_with_caveat: 2",
                "accepted recommendations rely on inference-only grounding: 3",
            ],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 2 still needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The second recommendation still leaves fallback handling implicit.",
                "recommendation_index": 2,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "carried_forward",
                "resolution_note": "not_addressed | Still unresolved.",
                "resolved_in_stage_index": None,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["partial_answer"]["included_recommendation_indices"] == [1, 3]
    assert (
        _first_line(tmp_path / "PARTIAL_ANSWER.md")
        == "# Partial Answer: task-partial-scope"
    )
    assert "- Review status scope: `included recommendations only`" in markdown
    assert "- Run-level provenance status: `bound`" in markdown
    assert "- Run-level semantic warnings: `1`" in markdown
    assert "accepted recommendations rely on inference-only grounding: 3" in markdown
    assert "TOPIC-001" not in markdown
    assert "accept_with_caveat: 2" not in markdown
    assert "## Topic Lifecycle" not in markdown
    assert "none_reason:" not in markdown


def test_apply_final_artifacts_blocks_partial_answer_when_trust_provenance_is_incomplete(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-blocked"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "summary": "Draft that should not be published as a partial artifact.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Supported recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Also supported.",
                    "evidence": ["b.py"],
                    "proposed_change": "Ship that too.",
                    "confidence": 0.69,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert "partial_answer" not in updated
    assert "partial_answer_json" not in updated["artifacts"]
    assert "partial_answer_md" not in updated["artifacts"]
    assert updated["artifacts"]["final_artifact"] == ""
    assert updated["artifacts"]["final_artifact_kind"] == "none"
    assert "final_artifact_json" not in updated["artifacts"]
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.md").exists()


def test_apply_final_artifacts_blocks_trust_final_answer_and_falls_back_to_partial_answer(
    tmp_path,
):
    summary = {
        "task": {"id": "task-final-blocked-partial"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "summary": "Accepted content that is not publishable as a final answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Clean recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Carries topic debt.",
                    "evidence": ["b.py"],
                    "proposed_change": "Do not ship this one.",
                    "confidence": 0.62,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Third",
                    "rationale": "Still acceptable.",
                    "evidence": ["c.py", "d.py", "e.py", "f.py"],
                    "proposed_change": "Ship with a narrower claim.",
                    "confidence": 0.58,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Carries topic debt.",
            },
            {"recommendation_index": 3, "verdict": "accept", "summary": "Usable."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["review topics are carried forward: TOPIC-001"],
            },
            "accepted_recommendations_with_inferred_grounding": [],
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": [
                "review topics are carried forward: TOPIC-001",
                "accepted recommendation reviews include accept_with_caveat: 2",
            ],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 2 still needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The second recommendation still leaves fallback handling implicit.",
                "recommendation_index": 2,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "carried_forward",
                "resolution_note": "not_addressed | Still unresolved.",
                "resolved_in_stage_index": None,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("PARTIAL_ANSWER.md")
    assert updated["artifacts"]["final_artifact_json"].endswith("PARTIAL_ANSWER.json")
    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert "final_answer_md" not in updated["artifacts"]
    assert "final_answer_json" not in updated["artifacts"]
    assert updated["partial_answer"]["included_recommendation_indices"] == [1, 3]
    assert markdown.index("> Publication blockers:") < markdown.index(
        "## Review Status"
    )
    assert "> - review topics are carried forward: TOPIC-001" in markdown
    assert "- (+1 more)" in markdown
    assert "- f.py" not in markdown


def test_apply_final_artifacts_clears_stale_partial_metadata_and_falls_back_to_best_draft(
    tmp_path,
):
    best_payload = {
        "summary": "Fallback best draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "Safe fallback.",
                "evidence": ["draft.py"],
                "proposed_change": "Publish the fallback draft.",
                "confidence": 0.75,
            }
        ],
    }
    summary = {
        "task": {"id": "task-stale-partial"},
        "verdict": "accepted_partial",
        "artifacts": {
            "run_dir": str(tmp_path),
            "partial_answer_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "partial_answer_md": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "final_artifact_kind": "partial_answer",
        },
        "partial_answer": {
            "summary": "Stale partial answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Stale recommendation",
                }
            ],
            "included_recommendation_indices": [1],
            "excluded_recommendation_indices": [],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "drafts": [_best_draft_record(best_payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert "partial_answer" not in updated
    assert "partial_answer_json" not in updated["artifacts"]
    assert "partial_answer_md" not in updated["artifacts"]
    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert updated["artifacts"]["final_artifact_json"].endswith("BEST_DRAFT.json")
    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert updated["best_draft"]["summary"] == "Fallback best draft."
    assert (tmp_path / "BEST_DRAFT.json").exists()
    assert (tmp_path / "BEST_DRAFT.md").exists()
    assert _first_line(tmp_path / "BEST_DRAFT.md") == "# Best Draft: task-stale-partial"
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.md").exists()


def test_apply_final_artifacts_non_accepted_partial_does_not_render_blocked_publication_note(
    tmp_path,
):
    summary = {
        "task": {"id": "task-partial-no-blocked-note"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "partial_answer": {
            "summary": "Partial answer remains the right artifact.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Included recommendation",
                    "rationale": "Safe subset.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship the clean subset.",
                    "confidence": 0.66,
                }
            ],
            "included_recommendation_indices": [1],
            "excluded_recommendation_indices": [2],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "reject", "summary": "Excluded."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [
                    "content verdict is not fully accepted: accepted_partial"
                ],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 0,
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("PARTIAL_ANSWER.md")
    assert "> This run did not reach a fully accepted verdict." in markdown
    assert "> Publication blockers:" not in markdown
    assert "content verdict is not fully accepted: accepted_partial" not in markdown


def test_apply_final_artifacts_non_accepted_best_draft_does_not_render_blocked_publication_note(
    tmp_path,
):
    best_payload = {
        "summary": "Best draft remains the fallback artifact.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "No clean partial subset exists.",
                "evidence": ["draft.py"],
                "proposed_change": "Keep as best-effort draft.",
                "confidence": 0.61,
            }
        ],
    }
    summary = {
        "task": {"id": "task-best-draft-no-blocked-note"},
        "verdict": "best_effort_exhausted",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "best_effort_exhausted",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [
                    "content verdict is not fully accepted: best_effort_exhausted"
                ],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 0,
            "downgrade_causes": [],
        },
        "drafts": [_best_draft_record(best_payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert "> This run did not reach a fully accepted verdict." in markdown
    assert "> Publication blockers:" not in markdown
    assert (
        "content verdict is not fully accepted: best_effort_exhausted" not in markdown
    )


def test_apply_final_artifacts_blocks_trust_final_answer_and_falls_back_to_best_draft(
    tmp_path,
):
    best_payload = {
        "summary": "Fallback best draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "Safe fallback.",
                "evidence": ["draft.py"],
                "proposed_change": "Publish the fallback draft.",
                "confidence": 0.75,
            }
        ],
    }
    summary = {
        "task": {"id": "task-final-blocked-best-draft"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "final_answer": {
            "summary": "Accepted content that is not publishable as a final answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "First",
                    "rationale": "Supported recommendation.",
                    "evidence": ["a.py"],
                    "proposed_change": "Ship it.",
                    "confidence": 0.71,
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Second",
                    "rationale": "Also supported.",
                    "evidence": ["b.py"],
                    "proposed_change": "Ship that too.",
                    "confidence": 0.69,
                },
            ],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {"recommendation_index": 2, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
            },
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["review topics are carried forward: TOPIC-001"],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": ["review topics are carried forward: TOPIC-001"],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "The final answer still needs a concrete fallback classification policy.",
                "severity": "medium",
                "evidence": "The analysis never states the fallback classification policy.",
                "recommendation_index": None,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "carried_forward",
                "resolution_note": "not_addressed | Still unresolved.",
                "resolved_in_stage_index": None,
            }
        ],
        "drafts": [_best_draft_record(best_payload)],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    markdown = (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert updated["artifacts"]["final_artifact_json"].endswith("BEST_DRAFT.json")
    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert "partial_answer_json" not in updated["artifacts"]
    assert "partial_answer_md" not in updated["artifacts"]
    assert "final_answer_json" not in updated["artifacts"]
    assert "final_answer_md" not in updated["artifacts"]
    assert markdown.index("> Publication blockers:") < markdown.index(
        "## Review Status"
    )
    assert "> - review topics are carried forward: TOPIC-001" in markdown
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert (
        "Recommendation indices included in `PARTIAL_ANSWER.*`" not in report_markdown
    )


def test_write_artifacts_node_clears_ineligible_partial_artifacts_and_falls_back_to_best_draft(
    tmp_path,
):
    best_payload = {
        "summary": "Fallback best draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Best draft recommendation",
                "rationale": "Safe fallback.",
                "evidence": ["draft.py"],
                "proposed_change": "Publish the fallback draft.",
                "confidence": 0.75,
            }
        ],
    }
    summary = {
        "task": {"id": "task-write-node"},
        "verdict": "accepted_partial",
        "artifacts": {
            "run_dir": str(tmp_path),
            "partial_answer_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "partial_answer_md": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact": str(tmp_path / "PARTIAL_ANSWER.md"),
            "final_artifact_json": str(tmp_path / "PARTIAL_ANSWER.json"),
            "final_artifact_kind": "partial_answer",
        },
        "partial_answer": {
            "summary": "Stale partial answer.",
            "recommendations": [
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Stale recommendation",
                }
            ],
            "included_recommendation_indices": [1],
            "excluded_recommendation_indices": [],
        },
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
        ],
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 1,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
            },
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "drafts": [_best_draft_record(best_payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }
    state = {
        "thread_id": "thread-123",
        "task_path": "task.md",
        "strategy_path": "strategy.md",
        "summary_payload": summary,
    }

    updated_state = write_artifacts_node(state)
    updated_summary = updated_state["summary_payload"]

    assert "partial_answer" not in updated_summary
    assert "partial_answer_json" not in updated_summary["artifacts"]
    assert "partial_answer_md" not in updated_summary["artifacts"]
    assert updated_summary["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert updated_summary["artifacts"]["final_artifact_json"].endswith(
        "BEST_DRAFT.json"
    )
    assert updated_summary["artifacts"]["final_artifact_kind"] == "best_draft"
    assert updated_state["artifact_index"]["best_draft_md"]["path"].endswith(
        "BEST_DRAFT.md"
    )
    assert "partial_answer_md" not in updated_state["artifact_index"]
    assert (tmp_path / "BEST_DRAFT.md").exists()
    assert _first_line(tmp_path / "BEST_DRAFT.md") == "# Best Draft: task-write-node"
    assert not (tmp_path / "PARTIAL_ANSWER.md").exists()


def test_apply_final_artifacts_prefers_clean_accepted_draft_over_caveated_accepted_draft(
    tmp_path,
):
    clean_payload = {
        "strengths": {
            "items": ["Grounded in workflow files"],
            "none_reason": "This stale schema text should not leak.",
        },
        "summary": "Clean accepted draft.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clean recommendation",
                "rationale": "Grounded and caveat-free.",
                "evidence": ["clean.py"],
                "proposed_change": "Apply the clean change.",
                "confidence": 0.61,
            }
        ],
    }
    caveated_payload = {
        "summary": "Accepted draft with carried-forward topic debt.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Caveated recommendation",
                "rationale": "Higher grounding but still caveated.",
                "evidence": ["caveated.py"],
                "proposed_change": "Apply the caveated change.",
                "confidence": 0.92,
            }
        ],
    }
    summary = {
        "task": {"id": "task-selection"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "drafts": [
            {
                "draft_id": "draft-clean",
                "review_status": "accepted",
                "review_state": "evaluated",
                "round_index": 0,
                "summary": clean_payload["summary"],
                "issue_counts": {
                    "blocking_medium_or_higher": 0,
                    "medium_or_higher": 0,
                    "accepted_recommendations": 1,
                    "required_validator_failures": 0,
                    "topics": 0,
                    "open_topics": 0,
                },
                "scores": {
                    "grounding_score": 0.62,
                    "actionability_score": 0.80,
                    "scope_compliance_score": 0.90,
                },
                "metadata": {"stage_index": 1, "payload": clean_payload},
            },
            {
                "draft_id": "draft-caveated",
                "review_status": "accepted",
                "review_state": "evaluated",
                "round_index": 1,
                "summary": caveated_payload["summary"],
                "issue_counts": {
                    "blocking_medium_or_higher": 0,
                    "medium_or_higher": 0,
                    "accepted_recommendations": 1,
                    "required_validator_failures": 0,
                    "topics": 1,
                    "open_topics": 1,
                    "carried_forward_topics": 1,
                },
                "scores": {
                    "grounding_score": 0.99,
                    "actionability_score": 0.83,
                    "scope_compliance_score": 0.92,
                },
                "metadata": {"stage_index": 3, "payload": caveated_payload},
            },
        ],
    }

    updated = apply_final_artifacts(summary)

    assert updated["best_draft_id"] == "draft-clean"
    assert updated["selected_draft_id"] == "draft-clean"
    assert updated["final_answer"]["summary"] == "Clean accepted draft."
    assert _first_line(tmp_path / "FINAL_ANSWER.md") == "# Final Answer: task-selection"
    assert "none_reason:" not in (tmp_path / "FINAL_ANSWER.md").read_text(
        encoding="utf-8"
    )


def test_apply_final_artifacts_graph_owned_uses_frozen_selection_ids(tmp_path):
    summary = {
        "task": {"id": "task-selection-frozen"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "best_draft_id": "draft-caveated",
        "selected_draft_id": "draft-caveated",
        "run_details": {
            "graph_execution": {
                "execution_mode": "graph_owned",
                "graph_owned": True,
                "fallback_used": False,
            }
        },
        "drafts": [
            {
                "draft_id": "draft-clean",
                "review_status": "accepted",
                "review_state": "evaluated",
                "round_index": 0,
                "summary": "Cleaner but not graph-selected draft.",
                "issue_counts": {
                    "blocking_medium_or_higher": 0,
                    "medium_or_higher": 0,
                    "accepted_recommendations": 1,
                    "required_validator_failures": 0,
                    "topics": 0,
                    "open_topics": 0,
                },
                "scores": {
                    "grounding_score": 0.62,
                    "actionability_score": 0.80,
                    "scope_compliance_score": 0.90,
                },
                "metadata": {
                    "stage_index": 1,
                    "payload": _recommendation_payload("Clean recommendation"),
                },
            },
            {
                "draft_id": "draft-caveated",
                "review_status": "accepted",
                "review_state": "evaluated",
                "round_index": 1,
                "summary": "Graph-selected draft.",
                "issue_counts": {
                    "blocking_medium_or_higher": 0,
                    "medium_or_higher": 0,
                    "accepted_recommendations": 1,
                    "required_validator_failures": 0,
                    "topics": 1,
                    "open_topics": 1,
                },
                "scores": {
                    "grounding_score": 0.55,
                    "actionability_score": 0.79,
                    "scope_compliance_score": 0.88,
                },
                "metadata": {
                    "stage_index": 2,
                    "payload": _recommendation_payload("Frozen graph-owned recommendation"),
                },
            },
        ],
    }

    updated = apply_final_artifacts(summary)

    assert updated["best_draft_id"] == "draft-caveated"
    assert updated["selected_draft_id"] == "draft-caveated"
    assert updated["final_answer"]["recommendations"][0]["title"] == (
        "Frozen graph-owned recommendation"
    )


def test_state_from_summary_preserves_explicit_selection_ids_without_reranking():
    summary = {
        "run_id": "run-selection-frozen",
        "thread_id": "thread-selection-frozen",
        "task": {"id": "task-selection-frozen", "task_kind": "analysis_review"},
        "strategy_kind": "analysis_review_v1",
        "agent_stages": [
            {
                "stage_index": 1,
                "role_name": "proposer_round_0",
                "ok": True,
                "structured_output": {"summary": "First draft."},
                "stdout_path": "draft-1.txt",
            },
            {
                "stage_index": 2,
                "role_name": "critic_round_0",
                "ok": True,
                "structured_output": {
                    "verdict": "accept",
                    "issues": [],
                    "recommendation_reviews": [
                        {"recommendation_index": 0, "verdict": "accept"}
                    ],
                    "grounding_score": 0.95,
                    "actionability_score": 0.90,
                    "scope_compliance_score": 0.93,
                },
            },
            {
                "stage_index": 3,
                "role_name": "proposer_round_1",
                "ok": True,
                "structured_output": {"summary": "Second draft."},
                "stdout_path": "draft-2.txt",
            },
            {
                "stage_index": 4,
                "role_name": "critic_round_1",
                "ok": True,
                "structured_output": {
                    "verdict": "accept",
                    "issues": [],
                    "recommendation_reviews": [
                        {"recommendation_index": 0, "verdict": "accept"}
                    ],
                    "grounding_score": 0.40,
                    "actionability_score": 0.50,
                    "scope_compliance_score": 0.60,
                    "topics": [{"topic_id": "TOPIC-1"}],
                },
            },
        ],
        "best_draft_id": "draft-proposer-round-1",
        "selected_draft_id": "draft-proposer-round-1",
        "verdicts": {"content_verdict": "accepted"},
    }

    state = state_from_summary(summary)

    assert state["best_draft_id"] == "draft-proposer-round-1"
    assert state["selected_draft_id"] == "draft-proposer-round-1"


def test_state_from_summary_backfills_missing_selection_ids_for_legacy_summaries():
    summary = {
        "run_id": "run-selection-legacy",
        "thread_id": "thread-selection-legacy",
        "task": {"id": "task-selection-legacy", "task_kind": "analysis_review"},
        "strategy_kind": "analysis_review_v1",
        "agent_stages": [
            {
                "stage_index": 1,
                "role_name": "proposer_round_0",
                "ok": True,
                "structured_output": {"summary": "First draft."},
                "stdout_path": "draft-1.txt",
            },
            {
                "stage_index": 2,
                "role_name": "critic_round_0",
                "ok": True,
                "structured_output": {
                    "verdict": "accept",
                    "issues": [],
                    "recommendation_reviews": [
                        {"recommendation_index": 0, "verdict": "accept"}
                    ],
                    "grounding_score": 0.80,
                    "actionability_score": 0.75,
                    "scope_compliance_score": 0.77,
                },
            },
        ],
        "verdicts": {"content_verdict": "accepted"},
    }

    state = state_from_summary(summary)

    assert state["best_draft_id"] == "draft-proposer_round_0"
    assert state["selected_draft_id"] == "draft-proposer_round_0"


def test_artifact_label_for_kind_rejects_unknown_values():
    try:
        _artifact_label_for_kind("mystery_artifact")
    except ValueError as exc:
        assert "Unsupported artifact kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown artifact kind")


def test_apply_final_artifacts_best_draft_markdown_omits_none_reason_label(tmp_path):
    summary = {
        "task": {"id": "task-best-draft-sections"},
        "verdict": "revise",
        "artifacts": {"run_dir": str(tmp_path)},
        "drafts": [_best_draft_record(_section_payload_with_redundant_none_reason())],
        "analysis_review_status": {"mode": "bounded"},
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact"].endswith("BEST_DRAFT.md")
    assert "none_reason:" not in (tmp_path / "BEST_DRAFT.md").read_text(
        encoding="utf-8"
    )


def test_render_deliverable_markdown_renders_compact_topic_lifecycle_when_topics_exist():
    payload = {
        "summary": "Accepted recommendations with a resolved review topic.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify operator fallback path",
                "rationale": "Operators need an explicit fallback classification.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
    }
    summary = {
        "verdict": "accepted",
        "analysis_review_status": {
            "mode": "bounded",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
            },
            "topic_ledger_count": 1,
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": ["TOPIC-001"],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "addressed",
                "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
                "resolved_in_stage_index": 4,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-789",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert "## Topic Lifecycle" in markdown
    assert (
        "- `TOPIC-001` `addressed` via `critic`: Recommendation 1 needs a concrete fallback classification. — addressed | Added the fallback classification note to recommendation 1."
        in markdown
    )


def test_render_deliverable_markdown_renders_carried_forward_topic_resolution_note():
    payload = {
        "summary": "Accepted recommendations with a carried-forward review topic.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify operator fallback path",
                "rationale": "Operators need an explicit fallback classification.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
    }
    summary = {
        "verdict": "accepted_with_warnings",
        "analysis_review_status": {
            "mode": "bounded",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
            },
            "topic_ledger_count": 1,
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["review topics are carried forward: TOPIC-001"],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "resolution_status": "carried_forward",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_note": "not_addressed | The recommendation improved, but the fallback label is still implicit. | Operators still need a concrete fallback label.",
                "resolved_in_stage_index": None,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-790",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert (
        "- `TOPIC-001` `carried_forward` via `critic`: Recommendation 1 needs a concrete fallback classification. — not_addressed | The recommendation improved, but the fallback label is still implicit. | Operators still need a concrete fallback label."
        in markdown
    )


def test_render_deliverable_markdown_renders_disagreed_topic_rollups():
    payload = {
        "summary": "Accepted recommendations with a disagreed review topic.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Clarify operator fallback path",
                "rationale": "Operators need an explicit fallback classification.",
                "evidence": ["docs/runbook.md"],
                "proposed_change": "Document the fallback handling path.",
                "confidence": 0.74,
            }
        ],
    }
    summary = {
        "verdict": "accepted",
        "analysis_review_status": {
            "mode": "bounded",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
            },
            "topic_ledger_count": 1,
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": ["TOPIC-001"],
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "resolution_status": "disagree",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_note": "disagree | The requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label.",
                "resolved_in_stage_index": 4,
            }
        ],
    }

    markdown = render_deliverable_markdown(
        "task-791",
        payload,
        artifact_kind="final_answer",
        artifact_label="FINAL_ANSWER",
        accepted=True,
        summary=summary,
    )

    assert "- Disagreed topic IDs: `TOPIC-001`" in markdown
    assert (
        "- `TOPIC-001` `disagree` via `critic`: Recommendation 1 needs a concrete fallback classification. — disagree | The requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label."
        in markdown
    )


def test_render_report_renders_full_topic_lifecycle_section():
    summary = {
        "verdict": "accepted_partial",
        "task": {"id": "task-789"},
        "verdicts": {
            "content_verdict": "accepted_partial",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {
            "bounded_review_summary": {
                "mode": "recommendation_review_surface",
                "recommendation_count": 1,
                "recommendations_with_review_surface": 1,
                "scope_escape_count": 0,
                "scope_escapes": [],
                "review_stages": [
                    {
                        "role_name": "critic",
                        "round_index": 0,
                        "issue_count": 0,
                        "issue_cap": 5,
                        "missing_topic_count": 1,
                        "missing_topic_cap": 2,
                        "new_topic_count": 1,
                        "new_topic_cap": 2,
                        "resolved_topic_count": 0,
                        "carried_forward_topic_count": 0,
                        "waived_topic_count": 0,
                        "open_topic_count": 1,
                        "new_medium_or_higher_issue_count": 0,
                        "new_medium_or_higher_issue_cap": None,
                        "topic_ledger_count": 1,
                        "scope_escape_count": 0,
                    },
                    {
                        "role_name": "auditor",
                        "round_index": 1,
                        "issue_count": 0,
                        "issue_cap": None,
                        "missing_topic_count": 0,
                        "missing_topic_cap": None,
                        "new_topic_count": 0,
                        "new_topic_cap": None,
                        "resolved_topic_count": 1,
                        "carried_forward_topic_count": 0,
                        "waived_topic_count": 0,
                        "open_topic_count": 0,
                        "new_medium_or_higher_issue_count": 0,
                        "new_medium_or_higher_issue_cap": 1,
                        "topic_ledger_count": 1,
                        "scope_escape_count": 0,
                    },
                ],
            }
        },
        "analysis_review_contract": {
            "mode": "bounded",
            "bounded_review": {
                "critic_issue_cap": 5,
                "critic_new_topic_cap": 2,
                "auditor_new_medium_or_higher_issue_cap_after_round0": 1,
            },
        },
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "bounded",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
                "required": False,
                "stages": [],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": ["TOPIC-001"],
            "waived_topic_ids": [],
            "topic_ledger_count": 1,
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "addressed",
                "resolution_note": "addressed | Added the fallback classification note to recommendation 1.",
                "resolved_in_stage_index": 4,
            }
        ],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "## Topic Lifecycle" in report
    assert "- Topic ledger entries: `1`" in report
    assert "- Resolved topics: `1` (`TOPIC-001`)" in report
    assert (
        "| Topic ID | Title | Severity | Introduced By | Status | Recommendation | Resolution Note |"
        in report
    )
    assert (
        "| `TOPIC-001` | Recommendation 1 needs a concrete fallback classification. | `medium` | `critic` | `addressed` | `1` | addressed \\| Added the fallback classification note to recommendation 1. |"
        in report
    )


def test_render_report_renders_disagreed_topic_status_section():
    summary = {
        "verdict": "accepted",
        "task": {"id": "task-790"},
        "verdicts": {
            "content_verdict": "accepted",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "bounded", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "bounded",
            "content_verdict": "accepted",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "not_required",
                "policy_mode": "none",
                "required": False,
                "stages": [],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "disagreed_topic_ids": ["TOPIC-001"],
            "topic_ledger_count": 1,
            "downgrade_causes": [],
        },
        "topic_ledger": [
            {
                "topic_id": "TOPIC-001",
                "title": "Recommendation 1 needs a concrete fallback classification.",
                "severity": "medium",
                "evidence": "The draft names the operator path but not the fallback state taxonomy.",
                "recommendation_index": 1,
                "introduced_by": "critic",
                "introduced_in_stage_index": 2,
                "resolution_status": "disagree",
                "resolution_note": "disagree | The requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label.",
                "resolved_in_stage_index": 4,
            }
        ],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "- Disagreed topic IDs: `TOPIC-001`" in report
    assert "- Disagreed topics: `1` (`TOPIC-001`)" in report


def test_render_report_sanitizes_recommendation_review_and_draft_summaries():
    payload = _recommendation_payload("First")
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-report-sanitized"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[],
            excluded_indices=[],
        ),
        "drafts": [
            _best_draft_record(
                {
                    **payload,
                    "summary": "This draft is publication-ready and can be used as the final artifact.",
                }
            )
        ],
        "recommendation_reviews": [
            {
                "recommendation_index": 1,
                "verdict": "accept_with_caveat",
                "summary": "This recommendation is publication-ready and acceptable as the final artifact.",
                "confidence_assessment": "well_calibrated",
            }
        ],
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": payload,
    }

    report = render_report(summary)

    assert "publication-ready" not in report.lower()
    assert "final artifact" not in report.lower()
    assert (
        "Runner note: review summary withheld because publication eligibility is runner-owned."
        in report
    )
    assert (
        "Runner note: draft summary withheld because publication eligibility is runner-owned."
        in report
    )


def test_render_report_renders_review_provenance_section_for_scoped_global_closure():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-provenance"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
                "issue_closure_review_ref_count": 0,
                "topic_closure_review_ref_count": 2,
                "closure_complete_issue_ids": [],
                "closure_complete_topic_ids": ["TOPIC-001"],
                "uncovered_recommendation_indices": [2],
                "uncovered_global_issue_ids": [],
                "uncovered_global_topic_ids": ["TOPIC-002"],
                "closure_proof_by_id": {
                    "TOPIC-001": {
                        "proof_path": "scoped",
                        "classification_status": "carried_forward",
                        "checked_files": [
                            ".github/workflows/claude-code-release-watch.yml"
                        ],
                        "verified_evidence_refs": [
                            ".github/workflows/claude-code-release-watch.yml"
                        ],
                        "proof_strength": "review_attested",
                    }
                },
                "stages": [
                    {
                        "surface": "review",
                        "status": "insufficient",
                        "policy_mode": "payload_hash_and_refs",
                        "recommendation_review_ref_count": 4,
                        "issue_closure_review_ref_count": 0,
                        "topic_closure_review_ref_count": 2,
                        "closure_complete_issue_ids": [],
                        "closure_complete_topic_ids": ["TOPIC-001"],
                        "uncovered_recommendation_indices": [2],
                        "uncovered_global_issue_ids": [],
                        "uncovered_global_topic_ids": ["TOPIC-002"],
                        "closure_proof_by_id": {
                            "TOPIC-001": {
                                "proof_path": "scoped",
                                "classification_status": "carried_forward",
                                "checked_files": [
                                    ".github/workflows/claude-code-release-watch.yml"
                                ],
                                "verified_evidence_refs": [
                                    ".github/workflows/claude-code-release-watch.yml"
                                ],
                                "proof_strength": "review_attested",
                            }
                        },
                    }
                ],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "## Review Provenance" in report
    assert "- Topic closure review refs: `2`" in report
    assert "- Closure-complete topic IDs: `TOPIC-001`" in report
    assert "- Uncovered recommendation indices: `2`" in report
    assert "- Uncovered global topic IDs: `TOPIC-002`" in report
    assert (
        "| `TOPIC-001` | `scoped` | `review_attested` | `carried_forward` | .github/workflows/claude-code-release-watch.yml | .github/workflows/claude-code-release-watch.yml |"
        in report
    )


def test_render_report_renders_review_provenance_section_for_scoped_global_issue_closure():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-provenance-issue"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
                "issue_closure_review_ref_count": 2,
                "topic_closure_review_ref_count": 0,
                "closure_complete_issue_ids": ["AR-001"],
                "closure_complete_topic_ids": [],
                "uncovered_global_issue_ids": [],
                "uncovered_global_topic_ids": ["TOPIC-002"],
                "closure_proof_by_id": {
                    "AR-001": {
                        "proof_path": "scoped",
                        "classification_status": "carried_forward",
                        "checked_files": [
                            ".github/workflows/codex-cli-release-watch.yml"
                        ],
                        "verified_evidence_refs": [
                            ".github/workflows/codex-cli-release-watch.yml"
                        ],
                        "proof_strength": "review_attested",
                    }
                },
                "stages": [
                    {
                        "surface": "review",
                        "status": "insufficient",
                        "policy_mode": "payload_hash_and_refs",
                        "recommendation_review_ref_count": 4,
                        "issue_closure_review_ref_count": 2,
                        "topic_closure_review_ref_count": 0,
                        "closure_complete_issue_ids": ["AR-001"],
                        "closure_complete_topic_ids": [],
                        "uncovered_global_issue_ids": [],
                        "uncovered_global_topic_ids": ["TOPIC-002"],
                        "closure_proof_by_id": {
                            "AR-001": {
                                "proof_path": "scoped",
                                "classification_status": "carried_forward",
                                "checked_files": [
                                    ".github/workflows/codex-cli-release-watch.yml"
                                ],
                                "verified_evidence_refs": [
                                    ".github/workflows/codex-cli-release-watch.yml"
                                ],
                                "proof_strength": "review_attested",
                            }
                        },
                    }
                ],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["final payload provenance is not fully bound"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "## Review Provenance" in report
    assert "- Issue closure review refs: `2`" in report
    assert "- Closure-complete issue IDs: `AR-001`" in report
    assert "- Uncovered global topic IDs: `TOPIC-002`" in report
    assert (
        "| `AR-001` | `scoped` | `review_attested` | `carried_forward` | .github/workflows/codex-cli-release-watch.yml | .github/workflows/codex-cli-release-watch.yml |"
        in report
    )


def test_render_report_renders_publishability_and_compact_provenance_previews():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-publishability"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": ["review topics are carried forward: TOPIC-001"],
            },
            "provenance": {
                "status": "insufficient",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
                "issue_closure_review_ref_count": 0,
                "topic_closure_review_ref_count": 3,
                "closure_complete_issue_ids": [],
                "closure_complete_topic_ids": ["TOPIC-001"],
                "uncovered_recommendation_indices": [],
                "uncovered_global_issue_ids": [],
                "uncovered_global_topic_ids": [],
                "closure_proof_by_id": {
                    "TOPIC-001": {
                        "proof_path": "scoped",
                        "classification_status": "carried_forward",
                        "checked_files": ["a.py", "b.py", "c.py"],
                        "verified_evidence_refs": ["r1", "r2", "r3"],
                        "proof_strength": "review_attested",
                    }
                },
                "stages": [
                    {
                        "surface": "review",
                        "status": "insufficient",
                        "policy_mode": "payload_hash_and_refs",
                        "recommendation_review_ref_count": 4,
                        "issue_closure_review_ref_count": 0,
                        "topic_closure_review_ref_count": 3,
                        "closure_complete_issue_ids": [],
                        "closure_complete_topic_ids": ["TOPIC-001"],
                        "uncovered_recommendation_indices": [],
                        "uncovered_global_issue_ids": [],
                        "uncovered_global_topic_ids": [],
                        "closure_proof_by_id": {
                            "TOPIC-001": {
                                "proof_path": "scoped",
                                "classification_status": "carried_forward",
                                "checked_files": ["a.py", "b.py", "c.py"],
                                "verified_evidence_refs": ["r1", "r2", "r3"],
                                "proof_strength": "review_attested",
                            }
                        },
                    }
                ],
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": ["TOPIC-001"],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": ["review topics are carried forward: TOPIC-001"],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    _assert_report_execution_mode(report, "trust")
    assert "- Publication outcome: `blocked`" in report
    assert (
        "- Publication blockers: review topics are carried forward: TOPIC-001" in report
    )
    assert (
        "| `TOPIC-001` | `scoped` | `review_attested` | `carried_forward` | a.py, b.py (+1 more) | r1, r2 (+1 more) |"
        in report
    )
    assert "a.py, b.py, c.py" not in report
    assert "r1, r2, r3" not in report


def test_render_report_renders_non_accepted_verdict_blocker():
    summary = {
        "verdict": "accepted_partial",
        "task": {"id": "task-publishability-non-accepted"},
        "verdicts": {
            "content_verdict": "accepted_partial",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [
                    "content verdict is not fully accepted: accepted_partial"
                ],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    _assert_report_execution_mode(report, "trust")
    assert "- Publication outcome: `blocked`" in report
    assert (
        "- Publication blockers: content verdict is not fully accepted: accepted_partial"
        in report
    )


def test_render_report_surfaces_trust_execution_mode_from_contract_without_status():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-contract-trust-mode"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)
    overview = _top_level_section(report, "## Overview")

    assert "- Execution mode: `trust`" in overview
    assert "- Publication outcome: `unknown`" in overview
    assert "## Analysis Review Status" not in report


def test_render_report_uses_defensive_publishability_fallback_when_blockers_missing():
    summary = {
        "verdict": "accepted_partial",
        "task": {"id": "task-publishability-fallback"},
        "verdicts": {
            "content_verdict": "accepted_partial",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_partial",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert (
        "- Publication blockers: not applicable because content verdict is `accepted_partial`"
        in report
    )


def test_render_report_uses_generic_publishability_fallback_for_fully_accepted_runs():
    summary = {
        "verdict": "accepted_with_warnings",
        "task": {"id": "task-publishability-generic-fallback"},
        "verdicts": {
            "content_verdict": "accepted_with_warnings",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "validator_summary": {},
        "run_details": {},
        "analysis_review_contract": {"mode": "trust", "bounded_review": {}},
        "analysis_review_coverage": {},
        "analysis_review_status": {
            "mode": "trust",
            "content_verdict": "accepted_with_warnings",
            "semantic_warning_count": 0,
            "publishability": {
                "final_answer_publishable": False,
                "blocking_causes": [],
            },
            "provenance": {
                "status": "bound",
                "policy_mode": "payload_hash_and_refs",
                "required": True,
            },
            "open_topic_ids": [],
            "carried_forward_topic_ids": [],
            "resolved_topic_ids": [],
            "waived_topic_ids": [],
            "downgrade_causes": [],
        },
        "topic_ledger": [],
        "issue_ledger": [],
        "agent_stages": [],
        "warnings": [],
        "errors": [],
        "workspace_policy_checks": [],
        "artifacts": {},
        "final_answer": {},
    }

    report = render_report(summary)

    assert "- Publication blockers: withheld due to non-publishable run state" in report


def test_render_report_renders_selected_focus_decision_without_analysis_review_status(
    tmp_path,
):
    raw_focus_decision = {
        **_selected_focus_decision(),
        "selected_focus_paths": ["/.github/workflows/codex-cli-release-watch.yml"],
    }
    summary_focus_decision = _selected_focus_decision()
    summary = {
        "verdict": "accepted",
        "task": {"id": "task-focus-selected", "task_kind": "analysis_review"},
        "verdicts": {
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "focus_decision": summary_focus_decision,
        "run_details": {"focus_decision": summary_focus_decision},
        "agent_stages": [
            _focus_stage_record(
                tmp_path,
                raw_payload=raw_focus_decision,
                normalized_payload=summary_focus_decision,
            )
        ],
        "workspace_policy_checks": [],
        "validator_rounds": [],
        "artifacts": {},
    }

    report = render_report(summary)
    section = _top_level_section(report, "## Focus Decision")

    assert "## Analysis Review Status" not in report
    assert "- Decision state: `selected`" in section
    assert "- Decision basis: `request_only`" in section
    assert "- Files hint disposition: `absent`" in section
    assert "- Checked files: none" in section
    assert "- Selected focus ID: `release-trigger-automation`" in section
    assert (
        "- Selected focus summary: Use the release trigger automation seam as the primary focus."
        in section
    )
    assert (
        "- Selected focus paths: `.github/workflows/codex-cli-release-watch.yml`"
        in section
    )
    assert (
        "- Top candidate: `release-trigger-automation` (`0.91`): Primary release trigger workflow seam."
        in section
    )
    assert (
        "- Next-best candidate: `rollback-runbook` (`0.62`): Fallback operational seam."
        in section
    )
    assert "- Candidates considered:" in section
    assert (
        "`release-trigger-automation`: Primary release trigger workflow seam."
        in section
    )
    assert (
        "- Artifact divergence sources: `structured_output.raw.json`, `structured_output.normalized.json`, `run.envelope.json`"
        in section
    )
    assert "- Raw vs normalized divergence: `1` changed field(s)" in section
    assert (
        '`selected_focus_paths`: ["/.github/workflows/codex-cli-release-watch.yml"] -> [".github/workflows/codex-cli-release-watch.yml"]'
        in section
    )
    assert "- Envelope structured_output parity: `1` changed field(s)" in section
    assert '`confidence_band`: "medium" -> "high"' in section
    assert (
        "- Envelope focus_gate metadata parity: matches canonical focus decision"
        in section
    )
    assert "- Adapter secondary focus IDs: `rollback-runbook`" in section
    assert (
        "- Downstream primary seam ID: "
        f"`{canonical_seam_id_for_paths(['.github/workflows/codex-cli-release-watch.yml'])}`"
        in section
    )
    assert (
        "- Downstream primary seam paths: `.github/workflows/codex-cli-release-watch.yml`"
        in section
    )
    assert "- Focus-to-seam adaptation basis: `selected_focus_paths`" in section
    assert "- Run-details focus parity: matches canonical focus decision" in section
    assert report.index("## Focus Decision") < report.index("## Run Details")
    run_details = _top_level_section(report, "## Run Details")
    assert '"rendered_in_report_section": true' in run_details
    assert '"decision_state": "selected"' in run_details


def test_render_report_distinguishes_artifact_focus_from_downstream_seam_bridge():
    summary = {
        "verdict": "accepted",
        "task": {"id": "task-focus-artifact", "task_kind": "analysis_review"},
        "verdicts": {
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "focus_decision": _artifact_selected_focus_decision(),
        "run_details": {"focus_decision": _artifact_selected_focus_decision()},
        "workspace_policy_checks": [],
        "validator_rounds": [],
        "agent_stages": [],
        "artifacts": {},
    }

    report = render_report(summary)
    section = _top_level_section(report, "## Focus Decision")
    selected_focus_id = canonical_artifact_focus_id(
        ".github/workflows/codex-cli-release-watch.yml"
    )
    downstream_seam_id = canonical_seam_id_for_paths(
        [".github/workflows/codex-cli-release-watch.yml"]
    )

    assert f"- Focus type: `artifact`" in section
    assert f"- Selected focus ID: `{selected_focus_id}`" in section
    assert "- Artifact singleton preserved: `yes` (`1` path)" in section
    assert f"- Downstream primary seam ID: `{downstream_seam_id}`" in section
    assert "- Focus-to-seam adaptation basis: `artifact_singleton`" in section
    assert "- Run-details focus parity: matches canonical focus decision" in section
    assert selected_focus_id != downstream_seam_id


def test_render_report_renders_selected_focus_decision_with_applied_focus_refinement():
    summary = {
        "verdict": "accepted",
        "task": {"id": "task-focus-refined", "task_kind": "analysis_review"},
        "verdicts": {
            "content_verdict": "accepted",
            "validator_verdict": "pass",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "focus_decision": _auto_refined_selected_focus_decision(),
        "run_details": {
            "focus_decision": _auto_refined_selected_focus_decision(),
            "focus_refinement": _applied_focus_refinement(),
        },
        "workspace_policy_checks": [],
        "validator_rounds": [],
        "agent_stages": [],
        "artifacts": {},
    }

    report = render_report(summary)
    section = _top_level_section(report, "## Focus Decision")
    run_details = _top_level_section(report, "## Run Details")

    assert "- Focus refinement: `auto-refined and continued`" in section
    assert (
        "- Refinement trigger reason: `umbrella_selected_checked_files`" in section
    )
    assert "- Refinement source focus ID: `release-automation-umbrella`" in section
    assert (
        "- Refinement candidate shortlist: `release-watch-slice`, `rollback-runbook-slice`"
        in section
    )
    assert "- Refinement attempted candidates: `release-watch-slice`" in section
    assert "- Refinement rejected candidates: none" in section
    assert "- Refinement selected candidate ID: `release-watch-slice`" in section
    assert (
        "- Refinement selected candidate paths: `.github/workflows/codex-cli-release-watch.yml`"
        in section
    )
    assert "- Decision state: `selected`" in section
    assert "- Selected focus ID: `release-watch-slice`" in section
    assert "- Clarification prompt:" not in section
    assert '"focus_refinement": {' in run_details
    assert '"rendered_in_report_section": true' in run_details
    assert '"status": "applied"' in run_details
    assert '"trigger_reason": "umbrella_selected_checked_files"' in run_details


def test_render_report_renders_no_viable_focus_decision_from_run_details():
    summary = {
        "verdict": "no_viable_focus",
        "task": {"id": "task-focus-none", "task_kind": "analysis_review"},
        "verdicts": {
            "content_verdict": "no_viable_focus",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "run_details": {"focus_decision": _no_viable_focus_decision()},
        "workspace_policy_checks": [],
        "validator_rounds": [],
        "agent_stages": [],
        "artifacts": {},
    }

    report = render_report(summary)
    overview = _top_level_section(report, "## Overview")
    coverage = _top_level_section(report, "## Review Loop Coverage")
    section = _top_level_section(report, "## Focus Decision")

    assert "- Request-gate result: `no_viable_focus`" in overview
    assert "- Review loop status: `not_started`" in overview
    assert "- Request-gate result: `no_viable_focus`" in coverage
    assert "- Review loop status: `not_started`" in coverage
    assert (
        "- Notes: the request gate blocked the run before proposer and reviewer stages executed."
        in coverage
    )
    assert "- Decision state: `no_viable_focus`" in section
    assert "- Viable focus identified: `no`" in section
    assert (
        "- Blocking outcome: no clarification question was emitted because the gate could not identify a viable focus target."
        in section
    )
    assert "- Candidates considered: none" in section
    assert "- Warnings:" in section
    assert "No seam candidate had enough direct workspace evidence." in section
    assert "- Clarification prompt:" not in section
    assert "- Clarification options:" not in section


def test_render_report_renders_no_viable_focus_decision_with_exhausted_refinement_guidance():
    summary = {
        "verdict": "no_viable_focus",
        "task": {"id": "task-focus-exhausted", "task_kind": "analysis_review"},
        "verdicts": {
            "content_verdict": "no_viable_focus",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "focus_decision": _exhausted_refinement_no_viable_focus_decision(),
        "run_details": {
            "focus_decision": _exhausted_refinement_no_viable_focus_decision(),
        },
        "failure_details": {"focus_refinement": _exhausted_focus_refinement()},
        "workspace_policy_checks": [],
        "validator_rounds": [],
        "agent_stages": [],
        "artifacts": {},
    }

    report = render_report(summary)
    section = _top_level_section(report, "## Focus Decision")

    assert "- Focus refinement: `refinement exhausted`" in section
    assert "- Refinement trigger reason: `collapsed_narrower_subset`" in section
    assert (
        "- Refinement attempted candidates: `release-watch-slice`, `rollback-runbook-slice`"
        in section
    )
    assert "- Refinement rejected candidates:" in section
    assert "`release-watch-slice`: `downstream_bridge_drift`" in section
    assert "`rollback-runbook-slice`: `canonical_drift`" in section
    assert "- Refinement selected candidate ID: none" in section
    assert (
        "- Refinement exhausted reason: `no_candidate_survived_validation`" in section
    )
    assert "- Rerun guidance: rerun with one of these files_hint slices" in section
    assert (
        "  - `1`. `release-watch-slice` (`0.74`): `.github/workflows/codex-cli-release-watch.yml`"
        in section
    )
    assert (
        "  - `2`. `rollback-runbook-slice` (`0.71`): `.github/workflows/rollback-runbook.md`"
        in section
    )
    assert (
        "Selected repo-probe focus remained too broad after bounded refinement; rerun with one of the narrower files_hint slices."
        in section
    )
    assert (
        "- Blocking outcome: no clarification question was emitted because the gate could not identify a viable focus target."
        not in section
    )
    assert "- Clarification prompt:" not in section
    assert "- Clarification options:" not in section


def test_render_report_renders_stale_no_viable_focus_without_fake_question_block():
    summary = {
        "verdict": "no_viable_focus",
        "task": {"id": "task-focus-stale", "task_kind": "analysis_review"},
        "verdicts": {
            "content_verdict": "no_viable_focus",
            "validator_verdict": "not_run",
            "policy_verdict": "pass",
            "config_verdict": "pass",
        },
        "focus_decision": _stale_no_viable_focus_decision(),
        "workspace_policy_checks": [],
        "validator_rounds": [],
        "agent_stages": [],
        "artifacts": {},
    }

    report = render_report(summary)
    section = _top_level_section(report, "## Focus Decision")

    assert "- Decision basis: `rerun_answer`" in section
    assert "- Files hint disposition: `helped`" in section
    assert (
        "- Checked files: `.github/workflows/codex-cli-release-watch.yml`, `.github/workflows/rollback-runbook.md`"
        in section
    )
    assert (
        "- Blocking outcome: no clarification question was emitted because the prior rerun answer went stale and the gate could not safely continue."
        in section
    )
    assert "- Stale-answer warnings:" in section
    assert "Prior focus_gate_answer went stale:" in section
    assert "- Clarification prompt:" not in section
    assert "- Clarification options:" not in section
    assert (
        "- Top candidate: `release-trigger-automation` (`0.54`): Release workflow seam."
        in section
    )
    assert (
        "- Next-best candidate: `rollback-runbook` (`0.49`): Rollback workflow seam."
        in section
    )


def test_write_state_artifacts_preserves_clarification_focus_decision_and_report(
    tmp_path,
):
    state = {
        "run_id": "run-focus-clarification",
        "thread_id": "thread-focus-clarification",
        "workspace_root": "/tmp/workspace",
        "out_root": str(tmp_path),
        "run_dir": str(tmp_path),
        "task_spec": {
            "id": "task-focus-clarification",
            "task_kind": "analysis_review",
            "workspace_write_policy": {},
        },
        "strategy_spec": {"name": "analysis_review_v1"},
        "strategy_kind": "analysis_review_v1",
        "warnings": [],
        "run_verdict": "blocked_for_clarification",
        "content_verdict": "blocked_for_clarification",
        "validator_verdict": "not_run",
        "policy_verdict": "pass",
        "config_verdict": "pass",
        "summary_text": "Focus gate blocked the run pending clarification.",
        "policy_checks": [],
        "stage_history": [],
        "validator_rounds": [],
        "drafts": [],
        "issue_history": [],
        "focus_decision": _clarification_focus_decision(),
    }

    updated_state = write_state_artifacts(state)
    summary = updated_state["summary_payload"]
    summary_json = json.loads(
        Path(summary["artifacts"]["summary_json"]).read_text(encoding="utf-8")
    )
    report = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    overview = _top_level_section(report, "## Overview")
    coverage = _top_level_section(report, "## Review Loop Coverage")
    section = _top_level_section(report, "## Focus Decision")

    assert summary["focus_decision"]["decision_state"] == "clarification_requested"
    assert (
        summary["run_details"]["focus_decision"]["decision_state"]
        == "clarification_requested"
    )
    assert (
        summary_json["run_details"]["focus_decision"]["decision_state"]
        == "clarification_requested"
    )
    assert (
        summary_json["focus_decision"]["question"]["prompt"]
        == "Which focus should this run prioritize?"
    )
    assert "## Analysis Review Status" not in report
    assert "- Request-gate result: `clarification_requested`" in overview
    assert "- Review loop status: `not_started`" in overview
    assert "- Request-gate result: `clarification_requested`" in coverage
    assert "- Review loop status: `not_started`" in coverage
    assert (
        "- Notes: the request gate blocked the run before proposer and reviewer stages executed."
        in coverage
    )
    assert "- Decision state: `clarification_requested`" in section
    assert "- Decision basis: `repo_probe`" in section
    assert "- Files hint disposition: `helped`" in section
    assert (
        "- Checked files: `.github/workflows/codex-cli-release-watch.yml`, `.github/workflows/rollback-runbook.md`"
        in section
    )
    assert "- Run-details focus parity: matches canonical focus decision" in section
    assert "- Clarification prompt: Which focus should this run prioritize?" in section
    assert (
        "- Clarification options: `release-trigger-automation`, `rollback-runbook`"
        in section
    )
    assert (
        "- Top candidate: `release-trigger-automation` (`0.54`): Release workflow seam."
        in section
    )
    assert "The task mixes release and rollback concerns." in section


def test_summary_projection_v1_projects_b1_boundary_fields(tmp_path):
    summary = summary_projection_v1(
        {
            "run_id": "run-boundary",
            "thread_id": "thread-boundary",
            "workspace_root": str(tmp_path),
            "run_dir": str(tmp_path),
            "task_spec": {
                "id": "task-boundary",
                "task_kind": "analysis_review",
                "workspace_write_policy": {},
            },
            "strategy_spec": {"name": "analysis_review_v1"},
            "strategy_kind": "analysis_review_v1",
            "serialization_version": "custom-serialization-v1",
            "summary_boundary_version": "summary_projection_v1",
            "bridge_boundary_version": "legacy_bridge_boundary_v1",
            "analysis_review_contract": {"mode": "bounded"},
            "strategy_graph_spec": {"runtime_target": "analysis_review_v1"},
            "strategy_graph_spec_id": "analysis-review-spec",
            "strategy_graph_subset": "bounded_strategy_graph_v1",
            "focus_decision": _selected_focus_decision(),
            "topic_ledger": [
                {"topic_id": "TOPIC-1", "resolution_status": "open"}
            ],
            "warnings": [],
            "policy_checks": [],
            "stage_history": [],
            "validator_rounds": [],
            "drafts": [],
            "issue_history": [],
        }
    )

    assert summary["serialization_version"] == "custom-serialization-v1"
    assert summary["summary_boundary_version"] == "summary_projection_v1"
    assert summary["bridge_boundary_version"] == "legacy_bridge_boundary_v1"
    assert summary["analysis_review_contract"] == {"mode": "bounded"}
    assert summary["strategy_graph_spec"] == {"runtime_target": "analysis_review_v1"}
    assert summary["strategy_graph_spec_id"] == "analysis-review-spec"
    assert summary["strategy_graph_subset"] == "bounded_strategy_graph_v1"
    assert summary["focus_decision"]["selected_focus_id"] == "release-trigger-automation"
    assert summary["run_details"]["focus_decision"]["selected_focus_id"] == (
        "release-trigger-automation"
    )
    assert summary["topic_ledger"] == [
        {"topic_id": "TOPIC-1", "resolution_status": "open"}
    ]


def test_write_artifacts_node_round_trips_b1_boundary_fields(tmp_path):
    state = {
        "run_id": "run-boundary-roundtrip",
        "thread_id": "thread-boundary-roundtrip",
        "workspace_root": str(tmp_path),
        "out_root": str(tmp_path),
        "run_dir": str(tmp_path),
        "task_path": "task.md",
        "strategy_path": "strategy.md",
        "config_path": "config/models.yaml",
        "auto_fit_strategy": True,
        "task_spec": {
            "id": "task-boundary-roundtrip",
            "task_kind": "analysis_review",
            "workspace_write_policy": {},
        },
        "strategy_spec": {"name": "analysis_review_v1"},
        "strategy_kind": "analysis_review_v1",
        "serialization_version": "custom-serialization-v1",
        "summary_boundary_version": "summary_projection_v1",
        "bridge_boundary_version": "legacy_bridge_boundary_v1",
        "analysis_review_contract": {"mode": "bounded"},
        "strategy_graph_spec": {"runtime_target": "analysis_review_v1"},
        "strategy_graph_spec_id": "analysis-review-spec",
        "strategy_graph_subset": "bounded_strategy_graph_v1",
        "focus_decision": _selected_focus_decision(),
        "topic_ledger": [{"topic_id": "TOPIC-1", "resolution_status": "open"}],
        "warnings": [],
        "run_verdict": "blocked_for_clarification",
        "content_verdict": "blocked_for_clarification",
        "validator_verdict": "not_run",
        "policy_verdict": "pass",
        "config_verdict": "pass",
        "summary_text": "Boundary-only round trip.",
        "policy_checks": [],
        "stage_history": [],
        "validator_rounds": [],
        "drafts": [],
        "issue_history": [],
    }

    updated_state = write_artifacts_node(state)

    assert updated_state["serialization_version"] == "custom-serialization-v1"
    assert updated_state["summary_boundary_version"] == "summary_projection_v1"
    assert updated_state["bridge_boundary_version"] == "legacy_bridge_boundary_v1"
    assert updated_state["analysis_review_contract"] == {"mode": "bounded"}
    assert updated_state["strategy_graph_spec"] == {
        "runtime_target": "analysis_review_v1"
    }
    assert updated_state["strategy_graph_spec_id"] == "analysis-review-spec"
    assert updated_state["strategy_graph_subset"] == "bounded_strategy_graph_v1"
    assert updated_state["focus_decision"]["selected_focus_id"] == (
        "release-trigger-automation"
    )
    assert updated_state["topic_ledger"] == [
        {"topic_id": "TOPIC-1", "resolution_status": "open"}
    ]
    assert updated_state["task_path"] == "task.md"
    assert updated_state["summary_payload"]["bridge_boundary_version"] == (
        "legacy_bridge_boundary_v1"
    )


def test_summary_projection_v1_projects_graph_trace_metadata_and_graph_execution(
    tmp_path,
):
    state = {
        "run_id": "run-graph-trace",
        "thread_id": "thread-graph-trace",
        "workspace_root": str(tmp_path),
        "run_dir": str(tmp_path),
        "task_spec": {
            "id": "task-graph-trace",
            "task_kind": "analysis_review",
            "workspace_write_policy": {},
        },
        "strategy_spec": {"name": "analysis_review_v1"},
        "strategy_kind": "analysis_review_v1",
        "analysis_review_execution_mode": "graph_owned",
        "stage_history": [
            {
                "stage_index": 1,
                "role_name": "focus_gate",
                "semantic_validation_path": str(tmp_path / "focus_gate.semantic.json"),
                "metadata": {
                    "graph_stage_id": "focus_gate",
                    "transition_reason": "focus_gate_required",
                },
            }
        ],
    }

    summary = summary_projection_v1(state)

    stage_metadata = summary["agent_stages"][0]["metadata"]
    assert stage_metadata["graph_stage_id"] == "focus_gate"
    assert stage_metadata["graph_node_id"] == "focus_gate"
    assert stage_metadata["transition_reason"] == "focus_gate_required"
    assert stage_metadata["semantic_validation_outcome"] == "passed"
    assert stage_metadata["execution_mode"] == "graph_owned"
    assert summary["run_details"]["graph_execution"] == {
        "execution_mode": "graph_owned",
        "graph_owned": True,
        "fallback_used": False,
        "transition_log": [
            {
                "graph_node_id": "focus_gate",
                "transition_reason": "focus_gate_required",
                "semantic_validation_outcome": "passed",
                "execution_mode": "graph_owned",
            }
        ],
    }

    summary["agent_stages"][0]["metadata"]["graph_node_id"] = "mutated"
    assert state["stage_history"][0]["metadata"] == {
        "graph_stage_id": "focus_gate",
        "transition_reason": "focus_gate_required",
    }


def test_write_state_artifacts_projects_legacy_bridge_graph_execution(tmp_path):
    state = {
        "run_id": "run-legacy-trace",
        "thread_id": "thread-legacy-trace",
        "workspace_root": str(tmp_path),
        "out_root": str(tmp_path),
        "run_dir": str(tmp_path),
        "task_spec": {
            "id": "task-legacy-trace",
            "task_kind": "analysis_review",
            "workspace_write_policy": {},
        },
        "strategy_spec": {"name": "analysis_review_v1"},
        "strategy_kind": "analysis_review_v1",
        "analysis_review_execution_mode": "legacy_bridge",
        "warnings": [],
        "run_verdict": "accepted",
        "content_verdict": "accepted",
        "validator_verdict": "pass",
        "policy_verdict": "pass",
        "config_verdict": "pass",
        "summary_text": "Legacy bridge trace projection.",
        "policy_checks": [],
        "stage_history": [
            {
                "stage_index": 1,
                "role_name": "proposer",
                "metadata": {
                    "graph_stage_id": "proposer",
                    "transition_reason": "analysis_entry",
                },
            }
        ],
        "validator_rounds": [],
        "drafts": [],
        "issue_history": [],
    }

    updated_state = write_state_artifacts(state)
    summary_json = json.loads(
        Path(updated_state["summary_payload"]["artifacts"]["summary_json"]).read_text(
            encoding="utf-8"
        )
    )
    report = Path(updated_state["summary_payload"]["artifacts"]["report_md"]).read_text(
        encoding="utf-8"
    )

    assert summary_json["agent_stages"][0]["metadata"]["graph_node_id"] == "proposer"
    assert (
        summary_json["agent_stages"][0]["metadata"]["semantic_validation_outcome"]
        == "not_run"
    )
    assert summary_json["run_details"]["graph_execution"] == {
        "execution_mode": "legacy_bridge",
        "graph_owned": False,
        "fallback_used": True,
        "transition_log": [
            {
                "graph_node_id": "proposer",
                "transition_reason": "analysis_entry",
                "semantic_validation_outcome": "not_run",
                "execution_mode": "legacy_bridge",
            }
        ],
    }
    assert '"graph_execution": {' in report
    assert '"fallback_used": true' in report


def _recommendation_payload(*titles: str) -> dict[str, object]:
    return {
        "summary": "Trusted analysis payload.",
        "recommendations": [
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": title,
                "rationale": f"{title} rationale.",
                "evidence": [f"{index}.py"],
                "proposed_change": f"Ship {title.lower()}.",
                "confidence": 0.7 + (index * 0.01),
            }
            for index, title in enumerate(titles, start=1)
        ],
    }


def _canonical_seam_fields() -> dict[str, object]:
    return {
        "primary_seam": {
            "seam_id": "seam-primary",
            "summary": "The runner determines canonical review status.",
            "why_primary": "It is the narrowest governing seam for review-state derivation.",
            "paths": ["anvil/harness/runner.py"],
        },
        "secondary_seams_considered": [
            {
                "seam_id": "seam-reporting",
                "summary": "Reporting projects the canonical seam state into artifacts.",
                "why_not_primary": "It consumes runner state rather than establishing it.",
                "paths": ["anvil/harness/reporting.py"],
            },
            {
                "seam_id": "seam-report",
                "summary": "The report renders run-canonical seam context.",
                "why_not_primary": "It is presentation-only.",
                "paths": ["anvil/harness/report.py"],
            },
        ],
        "scope_escapes": [
            {
                "path": "anvil/harness/reporting.py",
                "reason": "The reporting seam is retained in the bounded overflow projection.",
            },
            {
                "path": "anvil/harness/report.py",
                "reason": "The report seam is retained only when the full final artifact is emitted.",
            },
        ],
        "recommendation_seam_bindings": [
            {
                "recommendation_index": 1,
                "seam_id": "seam-primary",
                "seam_expansion_reason": "",
            },
            {
                "recommendation_index": 2,
                "seam_id": "seam-reporting",
                "seam_expansion_reason": "Artifact projection requires the reporting seam.",
            },
            {
                "recommendation_index": 3,
                "seam_id": "seam-report",
                "seam_expansion_reason": "Canonical seam rendering requires the report seam.",
            },
        ],
    }


def _trust_status(
    *,
    final_indices: list[int],
    partial_only_indices: list[int],
    excluded_indices: list[int],
    reasons_by_index: dict[str, list[str]] | None = None,
    provenance_status: str = "bound",
    final_answer_publishable: bool = True,
    seam_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    status: dict[str, object] = {
        "mode": "trust",
        "content_verdict": "accepted_with_warnings",
        "semantic_warning_count": 0,
        "publishability": {
            "final_answer_publishable": final_answer_publishable,
            "blocking_causes": [],
        },
        "provenance": {
            "status": provenance_status,
            "policy_mode": "payload_hash_and_refs",
            "required": True,
        },
        "open_topic_ids": [],
        "carried_forward_topic_ids": [],
        "resolved_topic_ids": [],
        "waived_topic_ids": [],
        "disagreed_topic_ids": [],
        "topic_ledger_count": 0,
        "downgrade_causes": [],
        "recommendation_admissibility": {
            "final_answer_recommendation_indices": final_indices,
            "partial_only_recommendation_indices": partial_only_indices,
            "excluded_recommendation_indices": excluded_indices,
            "reasons_by_recommendation_index": reasons_by_index or {},
        },
    }
    if seam_fields:
        status.update(copy.deepcopy(seam_fields))
    return status


def _bounded_status(
    *,
    final_indices: list[int],
    partial_only_indices: list[int],
    excluded_indices: list[int],
    reasons_by_index: dict[str, list[str]] | None = None,
    content_verdict: str = "accepted_with_warnings",
    seam_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    status: dict[str, object] = {
        "mode": "bounded",
        "content_verdict": content_verdict,
        "semantic_warning_count": 0,
        "publishability": {
            "final_answer_publishable": True,
            "blocking_causes": [],
        },
        "provenance": {
            "status": "not_required",
            "policy_mode": "none",
            "required": False,
        },
        "open_topic_ids": [],
        "carried_forward_topic_ids": [],
        "resolved_topic_ids": [],
        "waived_topic_ids": [],
        "disagreed_topic_ids": [],
        "topic_ledger_count": 0,
        "downgrade_causes": [],
        "recommendation_admissibility": {
            "final_answer_recommendation_indices": final_indices,
            "partial_only_recommendation_indices": partial_only_indices,
            "excluded_recommendation_indices": excluded_indices,
            "reasons_by_recommendation_index": reasons_by_index or {},
        },
    }
    if seam_fields:
        status.update(copy.deepcopy(seam_fields))
    return status


def test_apply_final_artifacts_partial_answer_projects_canonical_seam_state(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second", "Third")
    payload["primary_seam"] = {
        "seam_id": "payload-primary",
        "summary": "This payload seam should be ignored for projection.",
        "why_primary": "Incorrect source.",
        "paths": ["payload.py"],
    }
    payload["secondary_seams_considered"] = [
        {
            "seam_id": "payload-secondary",
            "summary": "This payload secondary seam should be ignored for projection.",
            "why_not_primary": "Incorrect source.",
            "paths": ["payload.py"],
        }
    ]
    seam_fields = _canonical_seam_fields()
    summary = {
        "task": {"id": "task-partial-seam-projection"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "mode": "trust",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _trust_status(
            final_indices=[2],
            partial_only_indices=[],
            excluded_indices=[1, 3],
            reasons_by_index={
                "1": ["not_accepted"],
                "3": ["not_accepted"],
            },
            seam_fields=seam_fields,
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    partial_json = json.loads(
        (tmp_path / "PARTIAL_ANSWER.json").read_text(encoding="utf-8")
    )
    partial_markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert partial_json["primary_seam"]["seam_id"] == "seam-primary"
    assert (
        partial_json["primary_seam"]["summary"]
        == seam_fields["primary_seam"]["summary"]
    )
    assert partial_json["secondary_seams_considered"] == [
        seam_fields["secondary_seams_considered"][0]
    ]
    assert partial_json["scope_escapes"] == [seam_fields["scope_escapes"][0]]
    assert (
        partial_json["primary_seam_projection_status"]
        == "retained_without_included_recommendations"
    )
    assert "payload-primary" not in json.dumps(partial_json, sort_keys=True)
    assert "payload-secondary" not in json.dumps(partial_json, sort_keys=True)
    assert (
        "Canonical primary seam retained for run context; no included recommendation in this artifact binds to it."
        in partial_markdown
    )
    assert "`seam-reporting`" in partial_markdown
    assert "`seam-report`" not in partial_markdown
    assert "`payload-primary`" not in partial_markdown
    assert "- Primary seam: `seam-primary`" in report_markdown
    assert (
        "- Secondary seams considered: `seam-reporting`, `seam-report`"
        in report_markdown
    )
    assert "primary_seam_projection_status" not in report_markdown
    assert "`payload-primary`" not in report_markdown


def test_apply_final_artifacts_final_answer_preserves_analysis_scope_escapes_unchanged(
    tmp_path,
):
    seam_fields = _canonical_seam_fields()
    payload = _recommendation_payload("First", "Second", "Third")
    payload.update(copy.deepcopy(seam_fields))
    summary = {
        "task": {"id": "task-final-scope-escapes"},
        "verdict": "accepted",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "mode": "bounded",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _bounded_status(
            final_indices=[1, 2, 3],
            partial_only_indices=[],
            excluded_indices=[],
            seam_fields=seam_fields,
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    final_json = json.loads(
        (tmp_path / "FINAL_ANSWER.json").read_text(encoding="utf-8")
    )

    assert updated["artifacts"]["final_artifact_kind"] == "final_answer"
    assert final_json["scope_escapes"] == seam_fields["scope_escapes"]


def test_apply_final_artifacts_bounded_accepted_emits_final_answer_and_report_shows_no_withheld_indices(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    summary = _with_nested_analysis_status(
        {
            "task": {"id": "task-bounded-final-admissible"},
            "verdict": "accepted_with_warnings",
            "artifacts": {"run_dir": str(tmp_path)},
            "analysis_review_contract": {
                "contract_version": "analysis_review_v1_contract_v10",
                "mode": "bounded",
                "partial_acceptance": {"min_accepted_recommendations": 1},
            },
            "analysis_review_status": _bounded_status(
                final_indices=[1, 2],
                partial_only_indices=[],
                excluded_indices=[],
            ),
            "final_answer": payload,
            "drafts": [_best_draft_record(payload)],
            "topic_ledger": [],
            "issue_ledger": [],
        }
    )

    updated = apply_final_artifacts(summary)
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    summary_json = _summary_json(tmp_path)

    assert updated["artifacts"]["final_artifact_kind"] == "final_answer"
    _assert_publication_parity(updated)
    _assert_publication_parity(summary_json)
    assert _analysis_publishability(updated) == {
        "final_answer_publishable": True,
        "blocking_causes": [],
    }
    assert _nested_analysis_publishability(updated) == {
        "final_answer_publishable": True,
        "blocking_causes": [],
    }
    assert _analysis_publishability(summary_json) == {
        "final_answer_publishable": True,
        "blocking_causes": [],
    }
    assert _nested_analysis_publishability(summary_json) == {
        "final_answer_publishable": True,
        "blocking_causes": [],
    }
    _assert_report_publication_state(report_markdown, "publishable")
    assert (
        "- Withheld recommendation indices for `FINAL_ANSWER.*`: none"
        in report_markdown
    )
    assert (
        "Recommendation indices included in `PARTIAL_ANSWER.*`" not in report_markdown
    )
    assert (
        "Recommendation indices excluded from `PARTIAL_ANSWER.*`" not in report_markdown
    )


def test_apply_final_artifacts_emits_final_answer_when_all_accepted_recommendations_are_final_admissible(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    summary = {
        "task": {"id": "task-final-admissible"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1, 2],
            partial_only_indices=[],
            excluded_indices=[],
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact_kind"] == "final_answer"
    assert (tmp_path / "FINAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert not (tmp_path / "BEST_DRAFT.json").exists()


def test_apply_final_artifacts_uses_one_sanitized_payload_copy_per_final_answer_artifact(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    payload["summary"] = "This analysis is publication-ready and is the final artifact."
    summary = {
        "task": {"id": "task-final-sanitized"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1, 2],
            partial_only_indices=[],
            excluded_indices=[],
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    final_json = json.loads(
        (tmp_path / "FINAL_ANSWER.json").read_text(encoding="utf-8")
    )
    final_markdown = (tmp_path / "FINAL_ANSWER.md").read_text(encoding="utf-8")
    summary_json = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    summary_section = _top_level_section(final_markdown, "## Summary")

    assert updated["artifacts"]["final_artifact_kind"] == "final_answer"
    assert final_json["summary"] == (
        "Runner note: model-authored summary withheld because publication eligibility is runner-owned."
    )
    assert "publication-ready" not in summary_section.lower()
    assert "final artifact" not in summary_section.lower()
    assert final_json["summary"] in summary_section
    assert summary_json["final_answer"]["summary"] == payload["summary"]


def test_apply_final_artifacts_emits_partial_answer_from_surviving_admissible_subset(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second", "Third")
    payload_blocker = (
        "final answer payload includes recommendation indices withheld from "
        "FINAL_ANSWER.*: 2, 3"
    )
    summary = _with_nested_analysis_status(
        {
            "task": {"id": "task-partial-admissible"},
            "verdict": "accepted_with_warnings",
            "artifacts": {"run_dir": str(tmp_path)},
            "analysis_review_contract": {
                "contract_version": "analysis_review_v1_contract_v10",
                "partial_acceptance": {"min_accepted_recommendations": 2},
            },
            "analysis_review_status": _trust_status(
                final_indices=[1],
                partial_only_indices=[2],
                excluded_indices=[3],
                reasons_by_index={
                    "2": ["accepted_with_caveat"],
                    "3": ["topic_blocked"],
                },
            ),
            "final_answer": payload,
            "drafts": [_best_draft_record(payload)],
            "topic_ledger": [],
            "issue_ledger": [],
        }
    )

    updated = apply_final_artifacts(summary)
    partial_json = json.loads(
        (tmp_path / "PARTIAL_ANSWER.json").read_text(encoding="utf-8")
    )
    partial_markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    summary_json = _summary_json(tmp_path)

    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    _assert_publication_parity(updated)
    _assert_publication_parity(summary_json)
    assert _analysis_publishability(updated) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert _nested_analysis_publishability(updated) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert _analysis_publishability(summary_json) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert _nested_analysis_publishability(summary_json) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert partial_json["included_recommendation_indices"] == [1, 2]
    assert partial_json["excluded_recommendation_indices"] == [3]
    assert partial_json["excluded_recommendation_reasons_by_index"] == {
        "3": ["topic_blocked"]
    }
    assert (
        "> Final answer publication was blocked, so this deliverable is emitted as a fallback artifact."
        in partial_markdown
    )
    assert f"> - {payload_blocker}" in partial_markdown
    assert partial_markdown.index(
        "> Recommendation indices withheld from `FINAL_ANSWER.*`:"
    ) < partial_markdown.index("## Review Status")
    assert "> - `2`: `accepted_with_caveat`" in partial_markdown
    assert "> - `3`: `topic_blocked`" in partial_markdown
    assert "> Publication blockers:" in partial_markdown
    assert (
        "- Recommendation indices included in `PARTIAL_ANSWER.*`: `1`, `2`"
        in partial_markdown
    )
    assert (
        "- Recommendation indices withheld from `FINAL_ANSWER.*`: `2`, `3`"
        in partial_markdown
    )
    assert (
        "- Recommendation indices excluded from `PARTIAL_ANSWER.*`: `3`"
        in partial_markdown
    )
    assert "  - `3`: `topic_blocked`" in partial_markdown
    assert summary_json["analysis_review_status"]["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ]["3"] == ["topic_blocked"]
    _assert_report_publication_state(report_markdown, "blocked")
    assert f"- Publication blockers: {payload_blocker}" in report_markdown
    assert (
        "- Withheld recommendation indices for `FINAL_ANSWER.*`: `2`, `3`"
        in report_markdown
    )
    assert (
        "Recommendation indices included in `PARTIAL_ANSWER.*`" not in report_markdown
    )
    assert (
        "Recommendation indices excluded from `PARTIAL_ANSWER.*`" not in report_markdown
    )
    assert "  - `3`: `topic_blocked`" in report_markdown


def test_apply_final_artifacts_preserves_partial_acceptance_suffix_when_sanitizing_partial_summary(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second", "Third")
    payload["summary"] = (
        "This draft is publication-ready and should ship as the final artifact."
    )
    summary = {
        "task": {"id": "task-partial-sanitized"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[3],
            reasons_by_index={
                "2": ["accepted_with_caveat"],
                "3": ["topic_blocked"],
            },
            final_answer_publishable=False,
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "recommendation_reviews": [
            {
                "recommendation_index": 1,
                "verdict": "accept",
                "summary": "Clean.",
            },
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "This recommendation is publication-ready and fit for the final artifact.",
            },
        ],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    partial_json = json.loads(
        (tmp_path / "PARTIAL_ANSWER.json").read_text(encoding="utf-8")
    )
    partial_markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")
    summary_section = _top_level_section(partial_markdown, "## Summary")
    recommendation_two = _rendered_section(partial_markdown, "### 2. Second")

    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert "publication-ready" not in partial_json["summary"].lower()
    assert "final artifact" not in partial_json["summary"].lower()
    assert (
        "Partial acceptance: Recommendation indices included in `PARTIAL_ANSWER.*`: 1, 2; "
        "Recommendation indices withheld from `FINAL_ANSWER.*`: 2, 3; "
        "Recommendation indices excluded from `PARTIAL_ANSWER.*`: 3."
        in partial_json["summary"]
    )
    assert partial_json["recommendation_reviews"][1]["summary"] == (
        "Runner note: review summary withheld because publication eligibility is runner-owned."
    )
    assert partial_json["summary"] in summary_section
    assert "publication-ready" not in recommendation_two.lower()
    assert "final artifact" not in recommendation_two.lower()
    assert (
        "Runner note: review summary withheld because publication eligibility is runner-owned."
        in recommendation_two
    )


def test_apply_final_artifacts_writes_partial_answer_with_original_indices_in_markdown(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second", "Third")
    summary = {
        "task": {"id": "task-partial-original-indices"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[2],
            partial_only_indices=[3],
            excluded_indices=[1],
            reasons_by_index={
                "1": ["not_accepted"],
                "3": ["accepted_with_caveat"],
            },
        ),
        "final_answer": payload,
        "recommendation_reviews": [
            {"recommendation_index": 2, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 3,
                "verdict": "accept_with_caveat",
                "summary": "Usable with rollout caveat.",
            },
        ],
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    partial_markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert updated["partial_answer"]["included_recommendation_indices"] == [2, 3]
    assert "### 2. Second" in partial_markdown
    assert "### 3. Third" in partial_markdown
    assert "### 1. First" not in partial_markdown


def test_apply_final_artifacts_falls_back_to_best_draft_when_global_topic_blocker_prevents_partial_publication(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    summary = {
        "task": {"id": "task-global-blocker"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 1},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[],
            reasons_by_index={"2": ["accepted_with_caveat"]},
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [
            {
                "topic_id": "TOPIC-GLOBAL",
                "resolution_status": "carried_forward",
                "recommendation_index": None,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)

    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert (tmp_path / "BEST_DRAFT.json").exists()


def test_apply_final_artifacts_falls_back_to_best_draft_when_partial_subset_drops_below_minimum(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second")
    payload_blocker = (
        "final answer payload includes recommendation indices withheld from "
        "FINAL_ANSWER.*: 2"
    )
    summary = {
        "task": {"id": "task-minimum-partial"},
        "verdict": "accepted_with_warnings",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[2],
            excluded_indices=[],
            reasons_by_index={"2": ["accepted_with_caveat"]},
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "topic_ledger": [
            {
                "topic_id": "TOPIC-002",
                "resolution_status": "carried_forward",
                "recommendation_index": 2,
            }
        ],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    best_draft_markdown = (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert (tmp_path / "BEST_DRAFT.json").exists()
    assert best_draft_markdown.index(
        "> Recommendation indices withheld from `FINAL_ANSWER.*`:"
    ) < best_draft_markdown.index("## Review Status")
    assert "> - `2`: `accepted_with_caveat`" in best_draft_markdown
    assert "> Publication blockers:" in best_draft_markdown
    assert f"> - {payload_blocker}" in best_draft_markdown


def test_apply_final_artifacts_never_emits_final_answer_when_source_payload_omits_accepted_recommendations(
    tmp_path,
):
    incomplete_final_answer = _recommendation_payload("First")
    complete_best_draft = _recommendation_payload("First", "Second")
    incomplete_final_answer["included_recommendation_indices"] = [1]
    payload_blocker = (
        "final answer payload omits recommendation indices required for "
        "FINAL_ANSWER.*: 2"
    )
    summary = _with_nested_analysis_status(
        {
            "task": {"id": "task-no-silent-omission"},
            "verdict": "accepted_with_warnings",
            "artifacts": {"run_dir": str(tmp_path)},
            "analysis_review_contract": {
                "contract_version": "analysis_review_v1_contract_v10",
                "partial_acceptance": {"min_accepted_recommendations": 2},
            },
            "analysis_review_status": _trust_status(
                final_indices=[1, 2],
                partial_only_indices=[],
                excluded_indices=[],
            ),
            "final_answer": incomplete_final_answer,
            "drafts": [_best_draft_record(complete_best_draft)],
            "topic_ledger": [],
            "issue_ledger": [],
        }
    )

    updated = apply_final_artifacts(summary)
    best_draft_markdown = (tmp_path / "BEST_DRAFT.md").read_text(encoding="utf-8")
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    summary_json = _summary_json(tmp_path)

    assert updated["artifacts"]["final_artifact_kind"] == "best_draft"
    _assert_publication_parity(updated)
    _assert_publication_parity(summary_json)
    assert _analysis_publishability(updated) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert _nested_analysis_publishability(updated) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert _analysis_publishability(summary_json) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert _nested_analysis_publishability(summary_json) == {
        "final_answer_publishable": False,
        "blocking_causes": [payload_blocker],
    }
    assert (
        "> Final answer publication was blocked, so this deliverable is emitted as a fallback artifact."
        in best_draft_markdown
    )
    assert "> Publication blockers:" in best_draft_markdown
    assert f"> - {payload_blocker}" in best_draft_markdown
    _assert_report_publication_state(report_markdown, "blocked")
    assert f"- Publication blockers: {payload_blocker}" in report_markdown
    assert not (tmp_path / "FINAL_ANSWER.json").exists()
    assert not (tmp_path / "PARTIAL_ANSWER.json").exists()
    assert (tmp_path / "BEST_DRAFT.json").exists()


def test_apply_final_artifacts_enforces_publishability_parity_invariant_across_artifact_outcomes(
    tmp_path,
):
    final_payload = _recommendation_payload("First", "Second")
    partial_payload = _recommendation_payload("First", "Second", "Third")
    best_draft_payload = _recommendation_payload("First")
    best_draft_fallback = _recommendation_payload("First", "Second")

    cases = [
        _with_nested_analysis_status(
            {
                "task": {"id": "task-invariant-final"},
                "verdict": "accepted_with_warnings",
                "artifacts": {"run_dir": str(tmp_path / "final")},
                "analysis_review_contract": {
                    "contract_version": "analysis_review_v1_contract_v10",
                    "mode": "bounded",
                    "partial_acceptance": {"min_accepted_recommendations": 1},
                },
                "analysis_review_status": _bounded_status(
                    final_indices=[1, 2],
                    partial_only_indices=[],
                    excluded_indices=[],
                ),
                "final_answer": final_payload,
                "drafts": [_best_draft_record(final_payload)],
                "topic_ledger": [],
                "issue_ledger": [],
            }
        ),
        _with_nested_analysis_status(
            {
                "task": {"id": "task-invariant-partial"},
                "verdict": "accepted_with_warnings",
                "artifacts": {"run_dir": str(tmp_path / "partial")},
                "analysis_review_contract": {
                    "contract_version": "analysis_review_v1_contract_v10",
                    "partial_acceptance": {"min_accepted_recommendations": 2},
                },
                "analysis_review_status": _trust_status(
                    final_indices=[1],
                    partial_only_indices=[2],
                    excluded_indices=[3],
                    reasons_by_index={
                        "2": ["accepted_with_caveat"],
                        "3": ["topic_blocked"],
                    },
                ),
                "final_answer": partial_payload,
                "drafts": [_best_draft_record(partial_payload)],
                "topic_ledger": [],
                "issue_ledger": [],
            }
        ),
        _with_nested_analysis_status(
            {
                "task": {"id": "task-invariant-best-draft"},
                "verdict": "accepted_with_warnings",
                "artifacts": {"run_dir": str(tmp_path / "best-draft")},
                "analysis_review_contract": {
                    "contract_version": "analysis_review_v1_contract_v10",
                    "partial_acceptance": {"min_accepted_recommendations": 2},
                },
                "analysis_review_status": _trust_status(
                    final_indices=[1, 2],
                    partial_only_indices=[],
                    excluded_indices=[],
                ),
                "final_answer": {
                    **best_draft_payload,
                    "included_recommendation_indices": [1],
                },
                "drafts": [_best_draft_record(best_draft_fallback)],
                "topic_ledger": [],
                "issue_ledger": [],
            }
        ),
    ]

    for summary in cases:
        updated = apply_final_artifacts(summary)
        persisted_summary = json.loads(
            Path(updated["artifacts"]["summary_json"]).read_text(encoding="utf-8")
        )
        expected_publishable = (
            updated["artifacts"]["final_artifact_kind"] == "final_answer"
        )
        assert (
            _analysis_publishability(updated).get("final_answer_publishable")
            == expected_publishable
        )
        assert (
            _nested_analysis_publishability(updated).get("final_answer_publishable")
            == expected_publishable
        )
        assert (
            _analysis_publishability(persisted_summary).get("final_answer_publishable")
            == expected_publishable
        )
        assert (
            _nested_analysis_publishability(persisted_summary).get(
                "final_answer_publishable"
            )
            == expected_publishable
        )
        _assert_publication_parity(updated)
        _assert_publication_parity(persisted_summary)


def test_apply_final_artifacts_is_idempotent_for_finalized_trust_fallback_reports(
    tmp_path,
):
    payload_blocker = (
        "final answer payload omits recommendation indices required for "
        "FINAL_ANSWER.*: 2"
    )
    fallback_payload = _recommendation_payload("First")
    fallback_payload["included_recommendation_indices"] = [1]
    summary = _with_nested_analysis_status(
        {
            "task": {"id": "task-idempotent-fallback"},
            "verdict": "accepted_with_warnings",
            "artifacts": {"run_dir": str(tmp_path)},
            "analysis_review_contract": {
                "contract_version": "analysis_review_v1_contract_v10",
                "partial_acceptance": {"min_accepted_recommendations": 2},
            },
            "analysis_review_status": _trust_status(
                final_indices=[1, 2],
                partial_only_indices=[],
                excluded_indices=[],
            ),
            "final_answer": fallback_payload,
            "drafts": [_best_draft_record(_recommendation_payload("First", "Second"))],
            "topic_ledger": [],
            "issue_ledger": [],
        }
    )

    first = apply_final_artifacts(summary)
    first_report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    first_summary_json = _summary_json(tmp_path)

    second = apply_final_artifacts(first)
    second_report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    second_summary_json = _summary_json(tmp_path)

    assert second["artifacts"]["final_artifact_kind"] == "best_draft"
    assert (
        first["artifacts"]["final_artifact_kind"]
        == second["artifacts"]["final_artifact_kind"]
    )
    assert _analysis_publishability(second)["final_answer_publishable"] is False
    assert _nested_analysis_publishability(second)["final_answer_publishable"] is False
    assert (
        _analysis_publishability(second)["blocking_causes"].count(payload_blocker) == 1
    )
    assert (
        _nested_analysis_publishability(second)["blocking_causes"].count(
            payload_blocker
        )
        == 1
    )
    assert first_report == second_report
    assert (
        first_summary_json["analysis_review_status"]["publishability"]
        == second_summary_json["analysis_review_status"]["publishability"]
    )
    assert second_summary_json["analysis_review_status"][
        "publishability"
    ] == _analysis_publishability(second)
    assert second_summary_json["run_details"]["analysis_review_status"][
        "publishability"
    ] == _nested_analysis_publishability(second)


def test_build_partial_answer_payload_preserves_original_indices_and_canonical_exclusion_reasons():
    payload = _recommendation_payload("First", "Second", "Third")
    summary = {
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _trust_status(
            final_indices=[1],
            partial_only_indices=[3],
            excluded_indices=[2],
            reasons_by_index={
                "2": ["not_accepted"],
                "3": ["inferred_grounding"],
            },
        ),
        "topic_ledger": [],
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 3,
                "verdict": "accept",
                "summary": "Inference-backed.",
            },
        ],
    }

    partial_payload = build_partial_answer_payload(summary, payload)

    assert partial_payload is not None
    assert partial_payload["included_recommendation_indices"] == [1, 3]
    assert partial_payload["excluded_recommendation_indices"] == [2]
    assert partial_payload["excluded_recommendation_reasons_by_index"] == {
        "2": ["not_accepted"]
    }
    assert [item["title"] for item in partial_payload["recommendations"]] == [
        "First",
        "Third",
    ]


def test_apply_final_artifacts_bounded_partial_emits_partial_answer_without_partial_only_indices(
    tmp_path,
):
    payload = _recommendation_payload("First", "Second", "Third")
    summary = {
        "task": {"id": "task-bounded-partial-admissible"},
        "verdict": "accepted_partial",
        "artifacts": {"run_dir": str(tmp_path)},
        "analysis_review_contract": {
            "contract_version": "analysis_review_v1_contract_v10",
            "mode": "bounded",
            "partial_acceptance": {"min_accepted_recommendations": 2},
        },
        "analysis_review_status": _bounded_status(
            final_indices=[1, 2],
            partial_only_indices=[],
            excluded_indices=[3],
            reasons_by_index={"3": ["not_accepted"]},
            content_verdict="accepted_partial",
        ),
        "final_answer": payload,
        "drafts": [_best_draft_record(payload)],
        "recommendation_reviews": [
            {"recommendation_index": 1, "verdict": "accept", "summary": "Clean."},
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "summary": "Usable.",
            },
            {"recommendation_index": 3, "verdict": "revise", "summary": "Needs work."},
        ],
        "topic_ledger": [],
        "issue_ledger": [],
    }

    updated = apply_final_artifacts(summary)
    partial_json = json.loads(
        (tmp_path / "PARTIAL_ANSWER.json").read_text(encoding="utf-8")
    )
    partial_markdown = (tmp_path / "PARTIAL_ANSWER.md").read_text(encoding="utf-8")
    report_markdown = (tmp_path / "REPORT.md").read_text(encoding="utf-8")

    assert updated["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert partial_json["included_recommendation_indices"] == [1, 2]
    assert partial_json["excluded_recommendation_indices"] == [3]
    assert (
        partial_json["recommendation_admissibility"][
            "partial_only_recommendation_indices"
        ]
        == []
    )
    assert (
        "- Recommendation indices included in `PARTIAL_ANSWER.*`: `1`, `2`"
        in partial_markdown
    )
    assert (
        "- Recommendation indices excluded from `PARTIAL_ANSWER.*`: `3`"
        in partial_markdown
    )
    assert (
        "- Withheld recommendation indices for `FINAL_ANSWER.*`: `3`"
        in report_markdown
    )
    assert (
        "Recommendation indices included in `PARTIAL_ANSWER.*`" not in report_markdown
    )
    assert (
        "Recommendation indices excluded from `PARTIAL_ANSWER.*`" not in report_markdown
    )
