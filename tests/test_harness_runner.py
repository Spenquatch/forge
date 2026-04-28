from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from anvil.config_loader import ProviderCfg
from anvil.harness.contracts import canonical_seam_id_for_paths
from anvil.harness.files import load_structured_file
from anvil.harness.providers import ForgeProviderAdapter, _soft_validate_schema
from anvil.harness.runner import HarnessRunner
from anvil.harness.schemas import analysis_review_schema
from anvil.harness.selection import extract_drafts_from_summary
from anvil.harness.types import ProviderRun

_PRIMARY_SEAM_PATHS = [
    ".github/workflows/codex-cli-release-watch.yml",
    "docs/project_management/next/codex-cli-parity/C1-spec.md",
]
_SIMPLE_PRIMARY_SEAM_PATHS = [".github/workflows/codex-cli-release-watch.yml"]
_SECONDARY_RELEASE_WATCH_SEAM_PATHS = [
    ".github/workflows/claude-code-release-watch.yml"
]
_SECONDARY_SNAPSHOT_SEAM_PATHS = [
    ".github/workflows/claude-code-release-watch.yml",
    ".github/workflows/claude-code-update-snapshot.yml",
    ".github/workflows/codex-cli-update-snapshot.yml",
]
_OVERFLOW_OWNER_SEAM_PATHS = [".github/workflows/codex-cli-update-snapshot.yml"]
_OVERFLOW_SPEC_SEAM_PATHS = ["docs/project_management/next/codex-cli-parity/C1-spec.md"]
_PRIMARY_SEAM_ID = "release-watch-governing"
_SECONDARY_RELEASE_WATCH_SEAM_ID = "release-watch-sibling-parity"
_SECONDARY_SNAPSHOT_SEAM_ID = "snapshot-prepare-parity"
_SIMPLE_PRIMARY_CANONICAL_SEAM_ID = canonical_seam_id_for_paths(_SIMPLE_PRIMARY_SEAM_PATHS)
_CORROBORATION_PRIMARY_CANONICAL_SEAM_ID = canonical_seam_id_for_paths(_PRIMARY_SEAM_PATHS)
_SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID = canonical_seam_id_for_paths(
    _SECONDARY_RELEASE_WATCH_SEAM_PATHS
)
_SECONDARY_SNAPSHOT_CANONICAL_SEAM_ID = canonical_seam_id_for_paths(
    _SECONDARY_SNAPSHOT_SEAM_PATHS
)
_OVERFLOW_OWNER_CANONICAL_SEAM_ID = canonical_seam_id_for_paths(
    _OVERFLOW_OWNER_SEAM_PATHS
)
_OVERFLOW_SPEC_CANONICAL_SEAM_ID = canonical_seam_id_for_paths(
    _OVERFLOW_SPEC_SEAM_PATHS
)
_FOCUS_GATE_QUESTION_PROMPT = HarnessRunner._canonical_focus_gate_question_prompt()
_CORROBORATION_FILES_REVIEWED = [
    ".github/workflows/codex-cli-release-watch.yml",
    ".github/workflows/claude-code-release-watch.yml",
    ".github/workflows/claude-code-update-snapshot.yml",
    ".github/workflows/codex-cli-update-snapshot.yml",
    "docs/project_management/next/codex-cli-parity/C1-spec.md",
]


def _failed_provider_run(
    request, *, message: str, failure_kind: str = "provider_unavailable"
) -> ProviderRun:
    out_dir = Path(request.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "response.txt").write_text("", encoding="utf-8")
    (out_dir / "error.txt").write_text(message, encoding="utf-8")
    return ProviderRun(
        role_name=request.role_name,
        provider="fake",
        model="fake-model",
        access=request.role_config.access,
        ok=False,
        exit_code=1,
        duration_sec=0.01,
        cwd=request.cwd,
        command=["fake"],
        stdout_path=str(out_dir / "response.txt"),
        stderr_path=str(out_dir / "error.txt"),
        prompt_path=str(out_dir / "prompt.txt"),
        schema_path=str(out_dir / "schema.json"),
        output_path=None,
        raw_output_path=None,
        normalized_output_path=None,
        structured_output=None,
        raw_meta={},
        error=message,
        failure_kind=failure_kind,
        failure_summary=message,
    )


def _successful_provider_run(request, *, payload: dict[str, object]) -> ProviderRun:
    out_dir = Path(request.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.txt").write_text(request.prompt_text, encoding="utf-8")
    (out_dir / "response.txt").write_text("ok", encoding="utf-8")
    (out_dir / "error.txt").write_text("", encoding="utf-8")
    (out_dir / "structured_output.raw.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return ProviderRun(
        role_name=request.role_name,
        provider="fake",
        model="fake-model",
        access=request.role_config.access,
        ok=True,
        exit_code=0,
        duration_sec=0.01,
        cwd=request.cwd,
        command=["fake"],
        stdout_path=str(out_dir / "response.txt"),
        stderr_path=str(out_dir / "error.txt"),
        prompt_path=str(out_dir / "prompt.txt"),
        schema_path=str(out_dir / "schema.json"),
        output_path=str(out_dir / "structured_output.normalized.json"),
        raw_output_path=str(out_dir / "structured_output.raw.json"),
        normalized_output_path=str(out_dir / "structured_output.normalized.json"),
        structured_output=payload,
        raw_meta={},
        error=None,
    )


def _load_run_summary_json(runner: HarnessRunner) -> dict[str, object]:
    return json.loads((runner.run_dir / "summary.json").read_text(encoding="utf-8"))


def _assert_canonical_analysis_review_status(
    summary: dict[str, object],
    *,
    expected_primary_seam_id: str,
    expected_secondary_seam_ids: list[str],
    expected_binding_seam_ids: list[str],
    expected_scope_escape_paths: list[str] | None = None,
) -> None:
    status = summary["analysis_review_status"]
    assert "primary_seam_projection_status" not in status
    assert set(status["primary_seam"]) == {"seam_id", "summary", "why_primary", "paths"}
    assert status["primary_seam"]["seam_id"] == expected_primary_seam_id
    assert [item["seam_id"] for item in status["secondary_seams_considered"]] == (
        expected_secondary_seam_ids
    )
    bindings = status["recommendation_seam_bindings"]
    assert [item["recommendation_index"] for item in bindings] == list(
        range(1, len(expected_binding_seam_ids) + 1)
    )
    assert [item["seam_id"] for item in bindings] == expected_binding_seam_ids
    assert all(
        set(item) == {"recommendation_index", "seam_id", "seam_expansion_reason"}
        for item in bindings
    )
    expected_scope_escape_paths = expected_scope_escape_paths or []
    assert [
        item["path"] for item in status["scope_escapes"]
    ] == expected_scope_escape_paths
    nested_status = summary["run_details"].get("analysis_review_status")
    if isinstance(nested_status, dict):
        assert nested_status == status


def _assert_summary_json_mirrors_analysis_review_status(
    runner: HarnessRunner,
    summary: dict[str, object],
) -> None:
    summary_json = _load_run_summary_json(runner)
    assert summary_json["analysis_review_status"] == summary["analysis_review_status"]
    nested_status = summary_json["run_details"].get("analysis_review_status")
    if isinstance(nested_status, dict):
        assert nested_status == summary_json["analysis_review_status"]


def _canonical_seam_context(summary: dict[str, object]) -> dict[str, object]:
    status = summary["analysis_review_status"]
    return {
        "primary_seam": status["primary_seam"],
        "secondary_seams_considered": status["secondary_seams_considered"],
        "recommendation_seam_bindings": status["recommendation_seam_bindings"],
        "scope_escapes": status["scope_escapes"],
    }


def _corroboration_analysis_files_reviewed() -> list[str]:
    return list(_CORROBORATION_FILES_REVIEWED)


def _corroboration_recommendations() -> list[dict[str, object]]:
    return [
        {
            "classification": "recommendation",
            "priority": "high",
            "title": "Track release-watch issues against the parity spec",
            "rationale": "The release-watch workflow should carry issue-tracking guidance that matches the nearest governing parity spec.",
            "evidence": [
                ".github/workflows/codex-cli-release-watch.yml",
                "docs/project_management/next/codex-cli-parity/C1-spec.md",
            ],
            "proposed_change": "Add release-watch issue-tracking guidance that points operators back to the parity spec expectations.",
            "confidence": 0.9,
            "review_surface": _AcceptingHarnessAdapter._review_surface(
                must_check_files=[
                    ".github/workflows/codex-cli-release-watch.yml",
                    "docs/project_management/next/codex-cli-parity/C1-spec.md",
                ],
                optional_check_files=[
                    ".github/workflows/claude-code-release-watch.yml"
                ],
                scope_note="Start from the prioritized release-watch workflow, then corroborate the governing requirement against the nearest repo-local parity spec.",
            ),
        },
        {
            "classification": "risk",
            "priority": "high",
            "title": "Add concurrency controls",
            "rationale": "Overlapping release-watch runs can duplicate work.",
            "evidence": [".github/workflows/codex-cli-release-watch.yml"],
            "proposed_change": "Add a workflow-level concurrency group keyed by workflow and ref.",
            "confidence": 0.91,
            "review_surface": _AcceptingHarnessAdapter._review_surface(
                must_check_files=[".github/workflows/codex-cli-release-watch.yml"],
                optional_check_files=[
                    ".github/workflows/claude-code-release-watch.yml"
                ],
                scope_note="Limit review to the release-watch workflow concurrency behavior.",
            ),
        },
        {
            "classification": "recommendation",
            "priority": "high",
            "title": "Align timeout handling across the full snapshot parity seam",
            "rationale": "Timeout recommendations should compare the release path to the sibling snapshot workflows so the prepare seam stays aligned too.",
            "evidence": [
                ".github/workflows/claude-code-release-watch.yml",
                ".github/workflows/claude-code-update-snapshot.yml",
                ".github/workflows/codex-cli-update-snapshot.yml",
            ],
            "proposed_change": "Compare timeout-minutes and prepare-stage behavior across the sibling snapshot workflows, then align the release-watch timeout guidance to that broader parity seam.",
            "confidence": 0.87,
            "review_surface": _AcceptingHarnessAdapter._review_surface(
                must_check_files=[
                    ".github/workflows/claude-code-release-watch.yml",
                    ".github/workflows/claude-code-update-snapshot.yml",
                    ".github/workflows/codex-cli-update-snapshot.yml",
                ],
                optional_check_files=[".github/workflows/codex-cli-release-watch.yml"],
                scope_note="Compare the release-watch timeout guidance against the sibling snapshot pair so the like-for-like parity seam includes the prepare path.",
            ),
        },
        {
            "classification": "recommendation",
            "priority": "medium",
            "title": "Document alert routing ownership",
            "rationale": "Operators need a clear escalation target when release automation fails.",
            "evidence": [".github/workflows/codex-cli-release-watch.yml"],
            "proposed_change": "Add the alert-routing owner and escalation path to the release-watch documentation.",
            "confidence": 0.76,
            "review_surface": _AcceptingHarnessAdapter._review_surface(
                must_check_files=[".github/workflows/codex-cli-release-watch.yml"],
                optional_check_files=[],
                scope_note="Keep the review bounded to the existing release-watch escalation path.",
            ),
        },
    ]


def _build_corroboration_analysis_payload(*, revised: bool) -> dict[str, object]:
    payload = {
        "status": "revised" if revised else "done",
        "summary": "Review the automation seam and keep bounded recommendations repo-local and complete.",
        "workspace_write_intent": "none",
        "recommendations": _corroboration_recommendations(),
        "strengths": {
            "items": [
                "Bounded recommendations include their nearby repo-local corroboration."
            ],
            "none_reason": "",
        },
        "uncertainties": {
            "items": [],
            "none_reason": "No material uncertainties remained after checking the governing spec and sibling workflow seam.",
        },
        "files_reviewed": _corroboration_analysis_files_reviewed(),
        "confidence": 0.89,
    }
    if revised:
        payload["issue_resolution_map"] = []
    return payload


def _build_corroboration_review_payload(
    *, summary: str, files_reviewed: list[str], recommendation_count: int
) -> dict[str, object]:
    payload = {
        "verdict": "accept",
        "summary": summary,
        "workspace_write_intent": "none",
        "files_reviewed": list(files_reviewed),
        "issues": [],
        "resolved_issue_ids": [],
        "carried_forward_issue_ids": [],
        "waived_issue_ids": [],
        "recommendation_reviews": [
            {
                "recommendation_index": index,
                "verdict": "accept",
                "open_issue_ids": [],
                "summary": f"Recommendation {index} is adequately corroborated for this mode.",
                "confidence_assessment": "well_calibrated",
            }
            for index in range(1, recommendation_count + 1)
        ],
        "grounding_score": 0.95,
        "actionability_score": 0.9,
        "scope_compliance_score": 0.95,
        "confidence": 0.9,
        "scope_escapes": [],
    }
    payload.update(_AcceptingHarnessAdapter._empty_topic_state())
    return payload


def _trust_recommendation_metadata(
    *, inference_backed_indices: set[int]
) -> dict[int, dict[str, object]]:
    direct_grounding = {
        1: {
            "verified_evidence_refs": [
                ".github/workflows/codex-cli-release-watch.yml",
                "docs/project_management/next/codex-cli-parity/C1-spec.md",
            ],
            "checked_files": [
                ".github/workflows/codex-cli-release-watch.yml",
                "docs/project_management/next/codex-cli-parity/C1-spec.md",
            ],
            "affected_files": [
                ".github/workflows/codex-cli-release-watch.yml",
                "docs/project_management/next/codex-cli-parity/C1-spec.md",
            ],
        },
        2: {
            "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
            "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
            "affected_files": [".github/workflows/codex-cli-release-watch.yml"],
        },
        3: {
            "verified_evidence_refs": [
                ".github/workflows/claude-code-release-watch.yml",
                ".github/workflows/claude-code-update-snapshot.yml",
                ".github/workflows/codex-cli-update-snapshot.yml",
            ],
            "checked_files": [
                ".github/workflows/claude-code-release-watch.yml",
                ".github/workflows/claude-code-update-snapshot.yml",
                ".github/workflows/codex-cli-update-snapshot.yml",
            ],
            "affected_files": [
                ".github/workflows/claude-code-release-watch.yml",
                ".github/workflows/claude-code-update-snapshot.yml",
                ".github/workflows/codex-cli-update-snapshot.yml",
                ".github/workflows/codex-cli-release-watch.yml",
            ],
        },
        4: {
            "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
            "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
            "affected_files": [".github/workflows/codex-cli-release-watch.yml"],
        },
    }
    metadata: dict[int, dict[str, object]] = {}
    for index, item in direct_grounding.items():
        grounding_mode = "inferred" if index in inference_backed_indices else "direct"
        affected_files = list(item["affected_files"])
        if index == 3 and grounding_mode == "direct":
            affected_files = list(item["checked_files"])
        metadata[index] = {
            "verified_evidence_refs": list(item["verified_evidence_refs"]),
            "checked_files": list(item["checked_files"]),
            "affected_files": affected_files,
            "grounding_mode": grounding_mode,
        }
    return metadata


def _apply_trust_grounding_metadata(
    payload: dict[str, object],
    *,
    metadata_by_index: dict[int, dict[str, object]],
) -> dict[str, object]:
    recommendations = payload.get("recommendations") or []
    for index, metadata in metadata_by_index.items():
        recommendation = recommendations[index - 1]
        recommendation["verified_evidence_refs"] = list(
            metadata["verified_evidence_refs"]
        )
        recommendation["checked_files"] = list(metadata["checked_files"])
        recommendation["affected_files"] = list(metadata["affected_files"])
        recommendation["grounding_mode"] = metadata["grounding_mode"]
    return payload


class _AcceptingHarnessAdapter:
    @staticmethod
    def _empty_topic_state() -> dict:
        return {
            "topics": [],
            "resolved_topic_ids": [],
            "carried_forward_topic_ids": [],
            "waived_topic_ids": [],
            "issue_closure_reviews": [],
            "topic_closure_reviews": [],
        }

    @staticmethod
    def _review_files_reviewed() -> list[str]:
        return [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/claude-code-release-watch.yml",
        ]

    @staticmethod
    def _review_surface(
        *, must_check_files: list[str], optional_check_files: list[str], scope_note: str
    ) -> dict:
        return {
            "must_check_files": must_check_files,
            "optional_check_files": optional_check_files,
            "scope_note": scope_note,
        }

    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seam_id": _PRIMARY_SEAM_ID,
            "summary": "The governing release-watch workflow seam for this task.",
            "why_primary": "It is the nearest governing workflow surface for the requested review.",
            "paths": [".github/workflows/codex-cli-release-watch.yml"],
        }

    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return [
            {
                "seam_id": _SECONDARY_RELEASE_WATCH_SEAM_ID,
                "summary": "The sibling release-watch workflow used for parity checks.",
                "why_not_primary": "It is corroborating parity context rather than the governing seam.",
                "paths": [".github/workflows/claude-code-release-watch.yml"],
            }
        ]

    def _recommendation_seam_binding(
        self,
        *,
        recommendation_index: int,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        if recommendation_index == 2:
            return (
                _SECONDARY_RELEASE_WATCH_SEAM_ID,
                "Cross-check the sibling release-watch workflow before widening this recommendation.",
            )
        return (_PRIMARY_SEAM_ID, "")

    def _analysis_scope_escapes(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return []

    def _apply_analysis_seams(self, payload: dict[str, object]) -> dict[str, object]:
        payload["primary_seam"] = self._primary_seam(payload=payload)
        payload["secondary_seams_considered"] = self._secondary_seams_considered(
            payload=payload
        )
        payload["scope_escapes"] = self._analysis_scope_escapes(payload=payload)
        for recommendation_index, item in enumerate(
            payload.get("recommendations") or [],
            start=1,
        ):
            if not isinstance(item, dict):
                continue
            seam_id, seam_expansion_reason = self._recommendation_seam_binding(
                recommendation_index=recommendation_index,
                payload=payload,
            )
            item["seam_id"] = seam_id
            item["seam_expansion_reason"] = seam_expansion_reason
        return payload

    def run(self, request):
        out_dir = Path(request.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "response.txt").write_text("ok", encoding="utf-8")
        (out_dir / "error.txt").write_text("", encoding="utf-8")
        payload = self._payload_for_role(request.role_name)
        if request.role_name in {"critic", "auditor"} and isinstance(payload, dict):
            payload.setdefault("issue_closure_reviews", [])
            payload.setdefault("topic_closure_reviews", [])
        return ProviderRun(
            role_name=request.role_name,
            provider="fake",
            model="fake-model",
            access=request.role_config.access,
            ok=True,
            exit_code=0,
            duration_sec=0.01,
            cwd=request.cwd,
            command=["fake"],
            stdout_path=str(out_dir / "response.txt"),
            stderr_path=str(out_dir / "error.txt"),
            prompt_path=str(out_dir / "prompt.txt"),
            schema_path=str(out_dir / "schema.json"),
            output_path=str(out_dir / "structured_output.normalized.json"),
            raw_output_path=str(out_dir / "structured_output.raw.json"),
            normalized_output_path=str(out_dir / "structured_output.normalized.json"),
            structured_output=payload,
            raw_meta={},
            error=None,
        )

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = {
            "status": "revised" if revised else "done",
            "summary": "Review the workflows and improve the recommendation set.",
            "workspace_write_intent": "none",
            "recommendations": [
                {
                    "classification": "risk",
                    "priority": "high",
                    "title": "Add concurrency controls",
                    "rationale": "Overlapping release watch runs can duplicate work.",
                    "evidence": [".github/workflows/codex-cli-release-watch.yml"],
                    "proposed_change": "Add a workflow-level concurrency group keyed by workflow and ref.",
                    "confidence": 0.91,
                    "review_surface": self._review_surface(
                        must_check_files=[
                            ".github/workflows/codex-cli-release-watch.yml"
                        ],
                        optional_check_files=[
                            ".github/workflows/claude-code-release-watch.yml"
                        ],
                        scope_note="Limit review to the release-watch workflow concurrency behavior.",
                    ),
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Align timeout handling",
                    "rationale": "Uneven timeout settings make failures harder to compare.",
                    "evidence": [".github/workflows/claude-code-release-watch.yml"],
                    "proposed_change": "Use explicit timeout-minutes consistently across both release paths.",
                    "confidence": 0.81,
                    "review_surface": self._review_surface(
                        must_check_files=[
                            ".github/workflows/claude-code-release-watch.yml"
                        ],
                        optional_check_files=[
                            ".github/workflows/codex-cli-release-watch.yml"
                        ],
                        scope_note="Focus on timeout settings in the release-watch workflows.",
                    ),
                },
            ],
            "strengths": {
                "items": ["Grounded in workflow files"],
                "none_reason": "",
            },
            "uncertainties": {
                "items": [],
                "none_reason": "No material uncertainties remained after comparing the relevant workflow files.",
            },
            "files_reviewed": [
                ".github/workflows/codex-cli-release-watch.yml",
                ".github/workflows/claude-code-release-watch.yml",
            ],
            "confidence": 0.87,
        }
        if revised:
            payload["issue_resolution_map"] = []
        return self._apply_analysis_seams(payload)

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "reviser_round_1":
            return self._base_analysis(revised=True)
        if role_name in {"critic", "auditor"}:
            payload = {
                "verdict": "accept",
                "summary": "Grounded and actionable analysis.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Strong and concrete recommendation.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Actionable and adequately supported.",
                        "confidence_assessment": "well_calibrated",
                    },
                ],
                "grounding_score": 0.93,
                "actionability_score": 0.89,
                "scope_compliance_score": 0.95,
                "confidence": 0.88,
                "scope_escapes": [],
            }
            payload.update(self._empty_topic_state())
            return payload
        raise AssertionError(f"Unexpected role: {role_name}")


class _FocusGateHarnessAdapter(_AcceptingHarnessAdapter):
    selected_focus_id = _SIMPLE_PRIMARY_CANONICAL_SEAM_ID
    secondary_focus_id = _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID
    selected_focus_paths = [".github/workflows/codex-cli-release-watch.yml"]
    secondary_focus_paths = [".github/workflows/claude-code-release-watch.yml"]
    probe_checked_files = [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
    ]

    def __init__(self) -> None:
        self.prompt_texts: dict[str, list[str]] = {}

    def _focus_gate_candidate_summary(self, focus_id: str) -> str:
        if focus_id == self.selected_focus_id:
            return "Primary release trigger workflow seam."
        return "Rollback workflow seam."

    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": self.selected_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.selected_focus_id
                ),
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow remains the governing seam.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.74,
            },
            {
                "focus_id": self.secondary_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.secondary_focus_id
                ),
                "candidate_paths": list(self.secondary_focus_paths),
                "why_candidate": "The rollback workflow is still a plausible sibling seam.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.61,
            },
        ]

    def _focus_gate_probe_payload(self) -> dict[str, object]:
        return {
            "focus_type": "seam",
            "files_hint_disposition": "helped",
            "checked_files": list(self.probe_checked_files),
            "candidates": self._probe_candidates(),
            "warnings": ["The task mixes release and rollback concerns."],
        }

    def _selected_focus_decision(
        self,
        *,
        gate_path: str,
        decision_basis: str,
        checked_files: list[str],
        files_hint_disposition: str,
        focus_id: str | None = None,
    ) -> dict[str, object]:
        candidates = self._probe_candidates()
        selected_focus_id = focus_id or self.selected_focus_id
        if selected_focus_id == self.selected_focus_id:
            selected_focus_paths = list(self.selected_focus_paths)
            selected_focus_summary = (
                "Use the release trigger workflow seam as the run focus."
            )
        else:
            selected_focus_paths = list(self.secondary_focus_paths)
            selected_focus_summary = "Use the rollback workflow seam as the run focus."
        if not checked_files:
            candidates = [{**item, "evidence_refs": []} for item in candidates]
        return {
            "gate_path": gate_path,
            "focus_type": "seam",
            "decision_state": "selected",
            "decision_basis": decision_basis,
            "selected_focus_id": selected_focus_id,
            "selected_focus_summary": selected_focus_summary,
            "selected_focus_paths": selected_focus_paths,
            "confidence": 0.92,
            "confidence_band": "high",
            "files_hint_disposition": files_hint_disposition,
            "checked_files": checked_files,
            "candidates": candidates,
            "question": {"prompt": "", "options": []},
            "warnings": [],
            "adapter_plan": {
                "primary_focus_id": selected_focus_id,
                "secondary_focus_ids": [
                    candidate["focus_id"]
                    for candidate in candidates
                    if candidate["focus_id"] != selected_focus_id
                ],
            },
        }

    def _clarification_focus_decision(self) -> dict[str, object]:
        return {
            "gate_path": "deliberate",
            "focus_type": "seam",
            "decision_state": "clarification_requested",
            "decision_basis": "repo_probe",
            "selected_focus_id": None,
            "selected_focus_summary": None,
            "selected_focus_paths": [],
            "confidence": 0.42,
            "confidence_band": "low",
            "files_hint_disposition": "helped",
            "checked_files": list(self.probe_checked_files),
            "candidates": self._probe_candidates(),
            "question": {
                "prompt": _FOCUS_GATE_QUESTION_PROMPT,
                "options": [self.selected_focus_id, self.secondary_focus_id],
            },
            "warnings": ["The task mixes release and rollback concerns."],
            "adapter_plan": {
                "primary_focus_id": None,
                "secondary_focus_ids": [
                    self.selected_focus_id,
                    self.secondary_focus_id,
                ],
            },
        }

    def _no_viable_focus_decision(self) -> dict[str, object]:
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
            "warnings": ["No seam candidate had enough direct workspace evidence."],
            "adapter_plan": {
                "primary_focus_id": None,
                "secondary_focus_ids": [],
            },
        }

    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seam_id": self.selected_focus_id,
            "summary": "The selected release trigger workflow seam.",
            "why_primary": "The focus gate selected this seam before proposer.",
            "paths": [".github/workflows/codex-cli-release-watch.yml"],
        }

    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return [
            {
                "seam_id": self.secondary_focus_id,
                "summary": "Rollback workflow seam.",
                "why_not_primary": "It remained shortlisted but secondary after the focus gate.",
                "paths": [".github/workflows/claude-code-release-watch.yml"],
            }
        ]

    def _recommendation_seam_binding(
        self,
        *,
        recommendation_index: int,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        return (self.selected_focus_id, "")

    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        if "Gate path: adjudicate" in prompt_text:
            return self._selected_focus_decision(
                gate_path="adjudicate",
                decision_basis="request_only",
                checked_files=[],
                files_hint_disposition="absent",
            )
        if '"question_prompt": "Which seam is stale?"' in prompt_text:
            return self._clarification_focus_decision()
        if f'"selected_option": "{self.selected_focus_id}"' in prompt_text:
            return self._selected_focus_decision(
                gate_path="deliberate",
                decision_basis="rerun_answer",
                checked_files=list(self.probe_checked_files),
                files_hint_disposition="helped",
            )
        if "Gate path: deliberate" in prompt_text:
            return self._clarification_focus_decision()
        raise AssertionError(f"Unexpected focus gate prompt: {prompt_text}")

    def run(self, request):
        self.prompt_texts.setdefault(request.role_name, []).append(request.prompt_text)
        if request.role_name == "focus_gate_probe":
            return _successful_provider_run(
                request,
                payload=self._focus_gate_probe_payload(),
            )
        if request.role_name == "focus_gate":
            return _successful_provider_run(
                request,
                payload=self._focus_gate_payload(request.prompt_text),
            )
        payload = self._payload_for_role(request.role_name)
        if request.role_name in {"critic", "auditor"} and isinstance(payload, dict):
            payload.setdefault("issue_closure_reviews", [])
            payload.setdefault("topic_closure_reviews", [])
        return _successful_provider_run(request, payload=payload)


class _NoViableFocusHarnessAdapter(_FocusGateHarnessAdapter):
    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        return self._no_viable_focus_decision()


class _ThresholdValidRerunWinnerHarnessAdapter(_FocusGateHarnessAdapter):
    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": self.selected_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.selected_focus_id
                ),
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow remains the governing seam.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.74,
            },
            {
                "focus_id": self.secondary_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.secondary_focus_id
                ),
                "candidate_paths": list(self.secondary_focus_paths),
                "why_candidate": "The rollback workflow is still a plausible sibling seam.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.58,
            },
        ]


class _AdjudicateConfiguredReturnsDeliberateHarnessAdapter(_FocusGateHarnessAdapter):
    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        return self._selected_focus_decision(
            gate_path="deliberate",
            decision_basis="repo_probe",
            checked_files=list(self.probe_checked_files),
            files_hint_disposition="helped",
        )


class _AdjudicateNonCanonicalRepoProbeHarnessAdapter(_FocusGateHarnessAdapter):
    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        payload = self._selected_focus_decision(
            gate_path="adjudicate",
            decision_basis="repo_probe",
            checked_files=list(self.probe_checked_files),
            files_hint_disposition="helped",
        )
        payload["selected_focus_id"] = "release_watch_and_snapshot_automation"
        payload["adapter_plan"][
            "primary_focus_id"
        ] = "release_watch_and_snapshot_automation"
        payload["candidates"][0]["focus_id"] = "release_watch_and_snapshot_automation"
        payload["candidates"][1]["focus_id"] = "release_watch_automation"
        return payload


class _DeliberateHumanQuestionOptionsHarnessAdapter(_FocusGateHarnessAdapter):
    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        del prompt_text
        payload = self._clarification_focus_decision()
        payload["question"] = {
            "prompt": "Which seam should this run prioritize?",
            "options": [
                "Prioritize Codex CLI release automation",
                "Prioritize Claude Code release automation",
            ],
        }
        return payload


class _DuplicateProbeCandidatesHarnessAdapter(_FocusGateHarnessAdapter):
    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": "release-trigger-low",
                "focus_summary": "Lower-confidence release trigger seam.",
                "candidate_paths": ["./.github/workflows/codex-cli-release-watch.yml"],
                "why_candidate": "The release workflow still appears relevant.",
                "evidence_refs": ["./.github/workflows/codex-cli-release-watch.yml"],
                "score": 0.63,
            },
            {
                "focus_id": "release-trigger-high",
                "focus_summary": "Highest-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow is the dominant seam after inspection.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.91,
            },
            {
                "focus_id": "release-trigger-supporting",
                "focus_summary": "Supporting duplicate release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "Additional evidence points at the same seam.",
                "evidence_refs": [
                    self.probe_checked_files[0],
                    self.probe_checked_files[1],
                ],
                "score": 0.52,
            },
        ]

    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        del prompt_text
        return self._selected_focus_decision(
            gate_path="deliberate",
            decision_basis="repo_probe",
            checked_files=list(self.probe_checked_files),
            files_hint_disposition="helped",
        )


class _ClarificationDuplicateFocusGateHarnessAdapter(_FocusGateHarnessAdapter):
    def _clarification_focus_decision(self) -> dict[str, object]:
        payload = super()._clarification_focus_decision()
        payload["candidates"] = [
            {
                "focus_id": "release-trigger-low",
                "focus_summary": "Lower-confidence release trigger seam.",
                "candidate_paths": ["./.github/workflows/codex-cli-release-watch.yml"],
                "why_candidate": "The release workflow remains plausible.",
                "evidence_refs": ["./.github/workflows/codex-cli-release-watch.yml"],
                "score": 0.41,
            },
            {
                "focus_id": "release-trigger-high",
                "focus_summary": "Highest-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow remains the best focus.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.83,
            },
            {
                "focus_id": "rollback-sibling",
                "focus_summary": "Rollback workflow seam.",
                "candidate_paths": list(self.secondary_focus_paths),
                "why_candidate": "The rollback workflow is still a plausible sibling seam.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.61,
            },
        ]
        payload["question"] = {
            "prompt": "Which seam should this run prioritize?",
            "options": ["stale-option", "another-stale-option"],
        }
        payload["adapter_plan"]["secondary_focus_ids"] = ["stale-secondary-id"]
        return payload


class _ProbeCandidateOverflowHarnessAdapter(_FocusGateHarnessAdapter):
    probe_checked_files = list(_CORROBORATION_FILES_REVIEWED)

    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": "release-trigger-low",
                "focus_summary": "Lower-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow remains plausible.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.41,
            },
            {
                "focus_id": "release-trigger-medium",
                "focus_summary": "Medium-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "Repeated evidence still points at the same seam.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.58,
            },
            {
                "focus_id": "release-trigger-high",
                "focus_summary": "Highest-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow is still the dominant seam.",
                "evidence_refs": [
                    self.probe_checked_files[0],
                    self.probe_checked_files[1],
                ],
                "score": 0.81,
            },
            {
                "focus_id": "snapshot-owner",
                "focus_summary": "Snapshot owner workflow seam.",
                "candidate_paths": list(_OVERFLOW_OWNER_SEAM_PATHS),
                "why_candidate": "Snapshot automation is a distinct downstream seam.",
                "evidence_refs": [self.probe_checked_files[3]],
                "score": 0.52,
            },
        ]

    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        del prompt_text
        return self._selected_focus_decision(
            gate_path="deliberate",
            decision_basis="repo_probe",
            checked_files=list(self.probe_checked_files),
            files_hint_disposition="helped",
        )


class _InvalidProbeCandidateSlotsHarnessAdapter(_FocusGateHarnessAdapter):
    probe_checked_files = list(_CORROBORATION_FILES_REVIEWED)

    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": "",
                "focus_summary": "Invalid empty-path candidate.",
                "candidate_paths": [],
                "why_candidate": "This invalid candidate should still consume a slot.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.11,
            },
            {
                "focus_id": "release-trigger-low",
                "focus_summary": "Lower-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow remains plausible.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.44,
            },
            {
                "focus_id": "release-trigger-high",
                "focus_summary": "Highest-confidence release trigger seam.",
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "Repeated evidence still points at the same seam.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.79,
            },
            {
                "focus_id": "snapshot-owner",
                "focus_summary": "Snapshot owner workflow seam.",
                "candidate_paths": list(_OVERFLOW_OWNER_SEAM_PATHS),
                "why_candidate": "Snapshot automation is a distinct downstream seam.",
                "evidence_refs": [self.probe_checked_files[3]],
                "score": 0.52,
            },
            {
                "focus_id": "spec-focus",
                "focus_summary": "Codex CLI parity spec seam.",
                "candidate_paths": list(_OVERFLOW_SPEC_SEAM_PATHS),
                "why_candidate": "The planning spec is another distinct seam.",
                "evidence_refs": [self.probe_checked_files[4]],
                "score": 0.5,
            },
        ]


class _MismatchSelectsOnRecordedReaskHarnessAdapter(_FocusGateHarnessAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.focus_gate_calls = 0

    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        if "Gate path: adjudicate" in prompt_text:
            return self._selected_focus_decision(
                gate_path="adjudicate",
                decision_basis="request_only",
                checked_files=[],
                files_hint_disposition="absent",
            )
        self.focus_gate_calls += 1
        if self.focus_gate_calls == 1:
            return self._clarification_focus_decision()
        return self._selected_focus_decision(
            gate_path="deliberate",
            decision_basis="rerun_answer",
            checked_files=list(self.probe_checked_files),
            files_hint_disposition="helped",
        )


class _DifferentWinnerRerunStaleHarnessAdapter(_FocusGateHarnessAdapter):
    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": self.selected_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.selected_focus_id
                ),
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow still exists but is no longer dominant.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.63,
            },
            {
                "focus_id": self.secondary_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.secondary_focus_id
                ),
                "candidate_paths": list(self.secondary_focus_paths),
                "why_candidate": "The rollback workflow now dominates the repo-backed evidence.",
                "evidence_refs": [self.probe_checked_files[1]],
                "score": 0.82,
            },
        ]


class _HardeningMismatchedRerunWinnerHarnessAdapter(
    _ThresholdValidRerunWinnerHarnessAdapter
):
    def _focus_gate_payload(self, prompt_text: str) -> dict[str, object]:
        if "Gate path: adjudicate" in prompt_text:
            return self._selected_focus_decision(
                gate_path="adjudicate",
                decision_basis="request_only",
                checked_files=[],
                files_hint_disposition="absent",
            )
        if f'"selected_option": "{self.selected_focus_id}"' in prompt_text:
            return self._selected_focus_decision(
                gate_path="deliberate",
                decision_basis="rerun_answer",
                checked_files=list(self.probe_checked_files),
                files_hint_disposition="helped",
                focus_id=self.secondary_focus_id,
            )
        if "Gate path: deliberate" in prompt_text:
            return self._clarification_focus_decision()
        raise AssertionError(f"Unexpected focus gate prompt: {prompt_text}")


class _SingleCandidateMediumRerunHarnessAdapter(_FocusGateHarnessAdapter):
    def _probe_candidates(self) -> list[dict[str, object]]:
        return [
            {
                "focus_id": self.selected_focus_id,
                "focus_summary": self._focus_gate_candidate_summary(
                    self.selected_focus_id
                ),
                "candidate_paths": list(self.selected_focus_paths),
                "why_candidate": "The release workflow is the only surfaced seam, but not at high confidence.",
                "evidence_refs": [self.probe_checked_files[0]],
                "score": 0.74,
            }
        ]


class _DriftingFocusGateHarnessAdapter(_FocusGateHarnessAdapter):
    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        seam = super()._primary_seam(payload=payload)
        seam["paths"] = [".github/workflows/claude-code-release-watch.yml"]
        return seam


class _BoundedCorroborationHarnessAdapter(_AcceptingHarnessAdapter):
    @staticmethod
    def _analysis_files_reviewed() -> list[str]:
        return _corroboration_analysis_files_reviewed()

    @staticmethod
    def _review_files_reviewed() -> list[str]:
        return _corroboration_analysis_files_reviewed()

    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seam_id": _PRIMARY_SEAM_ID,
            "summary": "The governing release-watch seam anchored to the nearest parity spec.",
            "why_primary": "The release-watch workflow plus its nearest governing parity spec are the primary review surface for this task.",
            "paths": list(_PRIMARY_SEAM_PATHS),
        }

    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return [
            {
                "seam_id": _SECONDARY_RELEASE_WATCH_SEAM_ID,
                "summary": "The sibling release-watch workflow used for parity corroboration.",
                "why_not_primary": "It corroborates the governing release-watch seam but does not set the governing requirement.",
                "paths": list(_SECONDARY_RELEASE_WATCH_SEAM_PATHS),
            },
            {
                "seam_id": _SECONDARY_SNAPSHOT_SEAM_ID,
                "summary": "The sibling snapshot and prepare-path parity seam.",
                "why_not_primary": "It broadens the review beyond the governing release-watch seam and therefore remains secondary.",
                "paths": list(_SECONDARY_SNAPSHOT_SEAM_PATHS),
            },
        ]

    def _recommendation_seam_binding(
        self,
        *,
        recommendation_index: int,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        if recommendation_index == 3:
            return (
                _SECONDARY_SNAPSHOT_SEAM_ID,
                "Compare the sibling snapshot prepare seam before broadening the timeout recommendation.",
            )
        return (_PRIMARY_SEAM_ID, "")

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = _build_corroboration_analysis_payload(revised=revised)
        return self._apply_analysis_seams(payload)

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "reviser_round_1":
            return self._base_analysis(revised=True)
        if role_name in {"critic", "auditor"}:
            return _build_corroboration_review_payload(
                summary="The bounded draft keeps the fuller recommendation set grounded inside the declared caps.",
                files_reviewed=self._review_files_reviewed(),
                recommendation_count=len(
                    self._base_analysis(revised=False)["recommendations"]
                ),
            )
        raise AssertionError(f"Unexpected role: {role_name}")


class _TrustCorroborationHarnessAdapter(_AcceptingHarnessAdapter):
    @staticmethod
    def _analysis_files_reviewed() -> list[str]:
        return _corroboration_analysis_files_reviewed()

    @staticmethod
    def _review_files_reviewed() -> list[str]:
        return _corroboration_analysis_files_reviewed()

    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seam_id": _PRIMARY_SEAM_ID,
            "summary": "The governing release-watch seam anchored to the nearest parity spec.",
            "why_primary": "The release-watch workflow plus its nearest governing parity spec are the primary review surface for this task.",
            "paths": list(_PRIMARY_SEAM_PATHS),
        }

    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return [
            {
                "seam_id": _SECONDARY_RELEASE_WATCH_SEAM_ID,
                "summary": "The sibling release-watch workflow used for parity corroboration.",
                "why_not_primary": "It corroborates the governing release-watch seam but does not set the governing requirement.",
                "paths": list(_SECONDARY_RELEASE_WATCH_SEAM_PATHS),
            },
            {
                "seam_id": _SECONDARY_SNAPSHOT_SEAM_ID,
                "summary": "The sibling snapshot and prepare-path parity seam.",
                "why_not_primary": "It broadens the review beyond the governing release-watch seam and therefore remains secondary.",
                "paths": list(_SECONDARY_SNAPSHOT_SEAM_PATHS),
            },
        ]

    def _recommendation_seam_binding(
        self,
        *,
        recommendation_index: int,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        if recommendation_index == 3:
            return (
                _SECONDARY_SNAPSHOT_SEAM_ID,
                "Compare the sibling snapshot prepare seam before broadening the timeout recommendation.",
            )
        return (_PRIMARY_SEAM_ID, "")

    def _apply_analysis_seams(self, payload: dict[str, object]) -> dict[str, object]:
        payload["primary_seam"] = self._primary_seam(payload=payload)
        payload["secondary_seams_considered"] = self._secondary_seams_considered(
            payload=payload
        )
        payload["scope_escapes"] = []
        for recommendation_index, item in enumerate(
            payload.get("recommendations") or [],
            start=1,
        ):
            if not isinstance(item, dict):
                continue
            seam_id, seam_expansion_reason = self._recommendation_seam_binding(
                recommendation_index=recommendation_index,
                payload=payload,
            )
            item["seam_id"] = seam_id
            item["seam_expansion_reason"] = seam_expansion_reason
        return payload

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = _build_corroboration_analysis_payload(revised=revised)
        payload = _apply_trust_grounding_metadata(
            payload,
            metadata_by_index=_trust_recommendation_metadata(
                inference_backed_indices={3}
            ),
        )
        return self._apply_analysis_seams(payload)

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "reviser_round_1":
            return self._base_analysis(revised=True)
        if role_name in {"critic", "auditor"}:
            payload = _build_corroboration_review_payload(
                summary=(
                    "The trust draft keeps the same repo-local recommendation seam; "
                    "only recommendation 3 remains inference-backed."
                ),
                files_reviewed=self._review_files_reviewed(),
                recommendation_count=len(
                    self._base_analysis(revised=False)["recommendations"]
                ),
            )
            metadata_by_index = _trust_recommendation_metadata(
                inference_backed_indices={3}
            )
            for item in payload["recommendation_reviews"]:
                metadata = metadata_by_index[int(item["recommendation_index"])]
                item["checked_files"] = list(metadata["checked_files"])
                item["verified_evidence_refs"] = list(
                    metadata["verified_evidence_refs"]
                )
            return payload
        raise AssertionError(f"Unexpected role: {role_name}")


class _RelabeledTrustCorroborationHarnessAdapter(_TrustCorroborationHarnessAdapter):
    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        seam = super()._primary_seam(payload=payload)
        seam["seam_id"] = "release-watch-update-snapshot-ci"
        return seam

    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        seams = super()._secondary_seams_considered(payload=payload)
        if seams:
            seams[0]["seam_id"] = "release-watch-snapshot-automation"
        if len(seams) > 1:
            seams[1]["seam_id"] = "snapshot-release-sibling-surface"
        return seams

    def _recommendation_seam_binding(
        self,
        *,
        recommendation_index: int,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        if recommendation_index == 3:
            return (
                "snapshot-release-sibling-surface",
                "Compare the sibling snapshot prepare seam before broadening the timeout recommendation.",
            )
        return ("release-watch-update-snapshot-ci", "")


class _PublishableDriftTrustCorroborationHarnessAdapter(_AcceptingHarnessAdapter):
    @staticmethod
    def _analysis_files_reviewed() -> list[str]:
        return _corroboration_analysis_files_reviewed()

    @staticmethod
    def _review_files_reviewed() -> list[str]:
        return _corroboration_analysis_files_reviewed()

    def _primary_seam(self, *, payload: dict[str, object]) -> dict[str, object]:
        return {
            "seam_id": _PRIMARY_SEAM_ID,
            "summary": "The governing release-watch seam anchored to the sibling workflow plus the parity spec.",
            "why_primary": "This run treats the sibling release-watch workflow and the parity spec as the governing cross-check surface.",
            "paths": [
                ".github/workflows/claude-code-release-watch.yml",
                "docs/project_management/next/codex-cli-parity/C1-spec.md",
            ],
        }

    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return [
            {
                "seam_id": _SECONDARY_RELEASE_WATCH_SEAM_ID,
                "summary": "The codex release-watch workflow remains a corroborating sibling seam.",
                "why_not_primary": "It corroborates the governing release-watch interpretation without setting the primary cross-check surface.",
                "paths": [".github/workflows/codex-cli-release-watch.yml"],
            },
            {
                "seam_id": _SECONDARY_SNAPSHOT_SEAM_ID,
                "summary": "The sibling snapshot and prepare-path parity seam.",
                "why_not_primary": "It broadens the review beyond the governing release-watch seam and therefore remains secondary.",
                "paths": [
                    ".github/workflows/claude-code-release-watch.yml",
                    ".github/workflows/claude-code-update-snapshot.yml",
                    ".github/workflows/codex-cli-update-snapshot.yml",
                ],
            },
        ]

    def _recommendation_seam_binding(
        self,
        *,
        recommendation_index: int,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        if recommendation_index == 2:
            return (
                _SECONDARY_RELEASE_WATCH_SEAM_ID,
                "Corroborate the codex release-watch workflow directly before changing concurrency guidance.",
            )
        return (_PRIMARY_SEAM_ID, "")

    def _apply_analysis_seams(self, payload: dict[str, object]) -> dict[str, object]:
        payload["primary_seam"] = self._primary_seam(payload=payload)
        payload["secondary_seams_considered"] = self._secondary_seams_considered(
            payload=payload
        )
        payload["scope_escapes"] = []
        for recommendation_index, item in enumerate(
            payload.get("recommendations") or [],
            start=1,
        ):
            if not isinstance(item, dict):
                continue
            seam_id, seam_expansion_reason = self._recommendation_seam_binding(
                recommendation_index=recommendation_index,
                payload=payload,
            )
            item["seam_id"] = seam_id
            item["seam_expansion_reason"] = seam_expansion_reason
        return payload

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = _build_corroboration_analysis_payload(revised=revised)
        payload = _apply_trust_grounding_metadata(
            payload,
            metadata_by_index=_trust_recommendation_metadata(
                inference_backed_indices=set()
            ),
        )
        return self._apply_analysis_seams(payload)

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "reviser_round_1":
            return self._base_analysis(revised=True)
        if role_name in {"critic", "auditor"}:
            payload = _build_corroboration_review_payload(
                summary=(
                    "The trust draft is publishable on its own, but it grounds the "
                    "canonical seam differently from the bounded run."
                ),
                files_reviewed=self._review_files_reviewed(),
                recommendation_count=len(
                    self._base_analysis(revised=False)["recommendations"]
                ),
            )
            metadata_by_index = _trust_recommendation_metadata(
                inference_backed_indices=set()
            )
            for item in payload["recommendation_reviews"]:
                metadata = metadata_by_index[int(item["recommendation_index"])]
                item["checked_files"] = list(metadata["checked_files"])
                item["verified_evidence_refs"] = list(
                    metadata["verified_evidence_refs"]
                )
            return payload
        raise AssertionError(f"Unexpected role: {role_name}")


class _PartialAcceptanceHarnessAdapter(_AcceptingHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"].append(
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Add release failure categorization",
                "rationale": "Operators would benefit from clearer failure bucketing.",
                "evidence": [".github/workflows/claude-code-release-watch.yml"],
                "proposed_change": "Document or annotate the distinct failure paths.",
                "confidence": 0.69 if not revised else 0.58,
                "review_surface": self._review_surface(
                    must_check_files=[
                        ".github/workflows/claude-code-release-watch.yml"
                    ],
                    optional_check_files=[],
                    scope_note="Keep the review bounded to existing release-watch failure-path handling.",
                ),
            }
        )
        return self._apply_analysis_seams(payload)

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "critic":
            payload = {
                "verdict": "revise",
                "summary": "Two recommendations are good, but recommendation 3 needs more specificity.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [
                    {
                        "issue_id": "AR-001",
                        "severity": "medium",
                        "kind": "insufficient_specificity",
                        "blocking_class": "actionability",
                        "recommendation_index": 3,
                        "title": "Recommendation 3 needs a more concrete implementation path.",
                        "evidence": "The proposed change stays at a conceptual level and does not say what to edit or check.",
                        "repair_hint": "Name the exact workflow or documentation target and the failure-path distinction to capture.",
                        "why_not_raised_earlier": None,
                    }
                ],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Strong recommendation.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Useful recommendation.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 3,
                        "verdict": "revise",
                        "open_issue_ids": ["AR-001"],
                        "summary": "Needs more concrete implementation guidance.",
                        "confidence_assessment": "not_assessed",
                    },
                ],
                "grounding_score": 0.90,
                "actionability_score": 0.71,
                "scope_compliance_score": 0.94,
                "confidence": 0.82,
                "scope_escapes": [],
            }
            payload.update(self._empty_topic_state())
            return payload
        if role_name == "reviser_round_1":
            payload = self._base_analysis(revised=True)
            payload["issue_resolution_map"] = [
                {
                    "issue_id": "AR-001",
                    "status": "not_addressed",
                    "change_summary": "Kept the recommendation but could not make it more specific without overclaiming.",
                    "residual_risk": "The recommendation remains somewhat conceptual.",
                }
            ]
            return payload
        if role_name == "auditor":
            payload = {
                "verdict": "accept_partial",
                "summary": "Recommendations 1 and 2 are usable. Recommendation 3 still needs more specificity.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [
                    {
                        "issue_id": "AR-001",
                        "severity": "medium",
                        "kind": "insufficient_specificity",
                        "blocking_class": "actionability",
                        "recommendation_index": 3,
                        "title": "Recommendation 3 remains too conceptual.",
                        "evidence": "The revision did not identify a concrete implementation target or check path.",
                        "repair_hint": "Point to the exact workflow, script, or documentation surface that should change.",
                        "why_not_raised_earlier": None,
                    }
                ],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": ["AR-001"],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Strong recommendation.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "accept_with_caveat",
                        "open_issue_ids": [],
                        "summary": "Useful recommendation with minor caveat about repo-specific rollout details.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 3,
                        "verdict": "revise",
                        "open_issue_ids": ["AR-001"],
                        "summary": "Still too abstract to include in a final answer.",
                        "confidence_assessment": "too_low",
                    },
                ],
                "grounding_score": 0.88,
                "actionability_score": 0.73,
                "scope_compliance_score": 0.95,
                "confidence": 0.84,
                "scope_escapes": [],
            }
            payload.update(self._empty_topic_state())
            return payload
        return super()._payload_for_role(role_name)


class _HallucinatedEvidenceHarnessAdapter(_AcceptingHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"][1]["evidence"] = ["does/not/exist.py"]
        return payload


class _InvalidSemanticHarnessAdapter(_AcceptingHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            payload = self._base_analysis(revised=False)
            payload["strengths"] = {"items": [], "none_reason": ""}
            payload["uncertainties"] = {"items": [], "none_reason": ""}
            return payload
        return super()._payload_for_role(role_name)


class _InvalidSemanticWithProviderNoiseHarnessAdapter(_AcceptingHarnessAdapter):
    def run(self, request):
        run = super().run(request)
        if request.role_name != "proposer":
            return run
        payload = dict(run.structured_output or {})
        payload["strengths"] = {"items": [], "none_reason": ""}
        payload["uncertainties"] = {"items": [], "none_reason": ""}
        return ProviderRun(
            role_name=run.role_name,
            provider=run.provider,
            model=run.model,
            access=run.access,
            ok=run.ok,
            exit_code=run.exit_code,
            duration_sec=run.duration_sec,
            cwd=run.cwd,
            command=run.command,
            stdout_path=run.stdout_path,
            stderr_path=run.stderr_path,
            prompt_path=run.prompt_path,
            schema_path=run.schema_path,
            output_path=run.output_path,
            structured_output=payload,
            raw_meta=run.raw_meta,
            error="WARN codex_core::plugins::manifest: noisy provider warning",
        )


class _FakeSuccessfulCliWarningResult:
    def __init__(self, payload: dict[str, object]):
        self.exit_code = 0
        self.stdout_text = json.dumps(payload)
        self.stderr_text = (
            "WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt"
        )
        self.command = ["fake-cli"]
        self.structured_output = payload
        self.metadata = {}
        self.usage = None


class _SuccessfulCliWarningProvider:
    model_name = "fake-cli-model"

    def __init__(self):
        self._payload_adapter = _AcceptingHarnessAdapter()
        self.last_cli_result = None

    async def generate(self, prompt: str, role: str = "execute", **kwargs):
        role_name = {
            "execute": "proposer",
            "critique": "critic",
            "review": "auditor",
            "refine": "reviser_round_1",
        }[role]
        payload = self._payload_adapter._payload_for_role(role_name)
        self.last_cli_result = _FakeSuccessfulCliWarningResult(payload)
        return self.last_cli_result.stdout_text


class _InvalidSchemaHarnessAdapter(_AcceptingHarnessAdapter):
    def run(self, request):
        run = super().run(request)
        if request.role_name != "proposer":
            return run
        payload = dict(run.structured_output or {})
        if (
            isinstance(payload.get("recommendations"), list)
            and payload["recommendations"]
        ):
            payload["recommendations"][0] = dict(payload["recommendations"][0])
            payload["recommendations"][0]["confidence"] = "not-a-number"
        return ProviderRun(
            role_name=run.role_name,
            provider=run.provider,
            model=run.model,
            access=run.access,
            ok=False,
            exit_code=run.exit_code,
            duration_sec=run.duration_sec,
            cwd=run.cwd,
            command=run.command,
            stdout_path=run.stdout_path,
            stderr_path=run.stderr_path,
            prompt_path=run.prompt_path,
            schema_path=run.schema_path,
            output_path=run.output_path,
            structured_output=payload,
            raw_meta=run.raw_meta,
            error="Schema validation failed.",
            schema_validation_errors=[
                "$.recommendations[0].affected_files: expected array"
            ],
        )


class _ScopeEscapeHarnessAdapter(_AcceptingHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name == "critic":
            payload["scope_escapes"] = [
                {
                    "path": "anvil/harness/state.py",
                    "reason": "The cited evidence conflicted with the adjacent state transition logic.",
                }
            ]
        return payload


class _SecondarySeamOverflowHarnessAdapter(_AcceptingHarnessAdapter):
    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        secondary_seams = super()._secondary_seams_considered(payload=payload)
        secondary_seams.append(
            {
                "seam_id": "release-watch-owner-overflow",
                "summary": "A second overflow seam that broadens the bounded review past the default cap.",
                "why_not_primary": "It introduces another secondary branch beyond the bounded default seam cap.",
                "paths": [".github/workflows/codex-cli-update-snapshot.yml"],
            }
        )
        secondary_seams.append(
            {
                "seam_id": "release-watch-spec-overflow",
                "summary": "An extra declared seam that exceeds the bounded secondary seam cap.",
                "why_not_primary": "It broadens the bounded review beyond the allowed default secondary seam cap.",
                "paths": ["docs/project_management/next/codex-cli-parity/C1-spec.md"],
            }
        )
        return secondary_seams

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["files_reviewed"] = [
            *payload["files_reviewed"],
            ".github/workflows/codex-cli-update-snapshot.yml",
            "docs/project_management/next/codex-cli-parity/C1-spec.md",
        ]
        return self._apply_analysis_seams(payload)


class _ScopedSecondarySeamOverflowHarnessAdapter(_SecondarySeamOverflowHarnessAdapter):
    def _analysis_scope_escapes(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        return [
            {
                "path": "docs/project_management/next/codex-cli-parity/C1-spec.md",
                "reason": "The bounded run needs exactly one third secondary seam to compare the parity spec against the governing workflow seam.",
            }
        ]


class _ReviserOnlyScopedOverflowHarnessAdapter(_AcceptingHarnessAdapter):
    def _secondary_seams_considered(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        secondary_seams = super()._secondary_seams_considered(payload=payload)
        if str(payload.get("status") or "").strip() == "revised":
            secondary_seams.append(
                {
                    "seam_id": "release-watch-owner-overflow",
                    "summary": "A second bounded secondary seam for ownership corroboration.",
                    "why_not_primary": "It broadens the bounded review but remains secondary.",
                    "paths": [".github/workflows/codex-cli-update-snapshot.yml"],
                }
            )
            secondary_seams.append(
                {
                    "seam_id": "release-watch-spec-overflow",
                    "summary": "A third bounded secondary seam anchored to the parity spec.",
                    "why_not_primary": "It is only needed after the revision expands the corroboration seam to the governing parity spec.",
                    "paths": [
                        "docs/project_management/next/codex-cli-parity/C1-spec.md"
                    ],
                }
            )
        return secondary_seams

    def _analysis_scope_escapes(
        self, *, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        if str(payload.get("status") or "").strip() != "revised":
            return []
        return [
            {
                "path": "docs/project_management/next/codex-cli-parity/C1-spec.md",
                "reason": "The revision needs exactly one third secondary seam to compare the governing parity spec against the widened bounded seam.",
            }
        ]

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        if revised:
            payload["files_reviewed"] = [
                *payload["files_reviewed"],
                ".github/workflows/codex-cli-update-snapshot.yml",
                "docs/project_management/next/codex-cli-parity/C1-spec.md",
            ]
        return self._apply_analysis_seams(payload)


class _LateAuditorIssueHarnessAdapter(_PartialAcceptanceHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "auditor":
            payload = {
                "verdict": "revise",
                "summary": "The auditor found a new medium-severity issue after the revision rewrote recommendation 2.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [
                    {
                        "issue_id": "AR-001",
                        "severity": "medium",
                        "kind": "insufficient_specificity",
                        "blocking_class": "actionability",
                        "recommendation_index": 3,
                        "title": "Recommendation 3 remains too conceptual.",
                        "evidence": "The revision did not identify a concrete implementation target or check path.",
                        "repair_hint": "Point to the exact workflow, script, or documentation surface that should change.",
                        "why_not_raised_earlier": None,
                    },
                    {
                        "issue_id": "AR-002",
                        "severity": "medium",
                        "kind": "missing_evidence",
                        "blocking_class": "correctness",
                        "recommendation_index": 2,
                        "title": "Recommendation 2 now needs explicit evidence after the rewrite.",
                        "evidence": "The revised recommendation no longer names the workflow file backing the timeout claim.",
                        "repair_hint": "Reattach the concrete workflow evidence for the timeout recommendation.",
                        "why_not_raised_earlier": "The missing evidence was introduced by the revision that rewrote recommendation 2.",
                    },
                ],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": ["AR-001"],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 1 remains acceptable.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "revise",
                        "open_issue_ids": ["AR-002"],
                        "summary": "Recommendation 2 introduced a new evidence gap during revision.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 3,
                        "verdict": "revise",
                        "open_issue_ids": ["AR-001"],
                        "summary": "Recommendation 3 remains too abstract to include.",
                        "confidence_assessment": "too_low",
                    },
                ],
                "grounding_score": 0.80,
                "actionability_score": 0.69,
                "scope_compliance_score": 0.95,
                "confidence": 0.79,
                "scope_escapes": [],
            }
            payload.update(self._empty_topic_state())
            return payload
        return super()._payload_for_role(role_name)


class _TopicLifecycleHarnessAdapter(_AcceptingHarnessAdapter):
    _TOPIC_ID = "TOPIC-001"

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "critic":
            return {
                "verdict": "revise",
                "summary": "Recommendation 2 still needs an explicit operator fallback classification.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 1 is acceptable.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "revise",
                        "open_issue_ids": [],
                        "summary": "Recommendation 2 needs an explicit fallback classification before acceptance.",
                        "confidence_assessment": "well_calibrated",
                    },
                ],
                "topics": [
                    {
                        "topic_id": self._TOPIC_ID,
                        "severity": "medium",
                        "title": "Recommendation 2 needs a concrete fallback classification.",
                        "evidence": "The workflow recommendation names the operator path but leaves the fallback state implicit.",
                        "repair_hint": "Name the fallback classification directly in recommendation 2.",
                        "recommendation_index": 2,
                    }
                ],
                "resolved_topic_ids": [],
                "carried_forward_topic_ids": [],
                "waived_topic_ids": [],
                "grounding_score": 0.91,
                "actionability_score": 0.76,
                "scope_compliance_score": 0.95,
                "confidence": 0.85,
                "scope_escapes": [],
            }
        if role_name == "reviser_round_1":
            payload = self._base_analysis(revised=True)
            payload["recommendations"][1][
                "proposed_change"
            ] = "Use explicit timeout-minutes consistently across both release paths and name the operator fallback classification."
            payload["topic_resolution_map"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "status": "addressed",
                    "recommendation_index": 2,
                    "change_summary": "Added the fallback classification note to recommendation 2.",
                    "residual_risk": "",
                }
            ]
            return payload
        if role_name == "auditor":
            return {
                "verdict": "accept",
                "summary": "The revision resolved the open topic without introducing new issues.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 1 remains acceptable.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 2 now includes the fallback classification.",
                        "confidence_assessment": "well_calibrated",
                    },
                ],
                "topics": [],
                "resolved_topic_ids": [self._TOPIC_ID],
                "carried_forward_topic_ids": [],
                "waived_topic_ids": [],
                "grounding_score": 0.94,
                "actionability_score": 0.89,
                "scope_compliance_score": 0.96,
                "confidence": 0.9,
                "scope_escapes": [],
            }
        return super()._payload_for_role(role_name)


class _LegacyMissingTopicsHarnessAdapter(_AcceptingHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "critic":
            return {
                "verdict": "revise",
                "summary": "Legacy critic payload still emits missing_topics for recommendation 2.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 1 is acceptable.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "revise",
                        "open_issue_ids": [],
                        "summary": "Recommendation 2 still needs a concrete fallback classification.",
                        "confidence_assessment": "well_calibrated",
                    },
                ],
                "missing_topics": [
                    "Recommendation 2 still needs a concrete fallback classification."
                ],
                "grounding_score": 0.9,
                "actionability_score": 0.75,
                "scope_compliance_score": 0.94,
                "confidence": 0.82,
                "scope_escapes": [],
            }
        return super()._payload_for_role(role_name)


class _LegacyMissingTopicsFullRunHarnessAdapter(_TopicLifecycleHarnessAdapter):
    _TOPIC_ID = "AT-001"

    def _payload_for_role(self, role_name: str):
        if role_name == "critic":
            payload = super()._payload_for_role(role_name)
            topic = payload.pop("topics")[0]
            payload["missing_topics"] = [topic["title"]]
            return payload
        return super()._payload_for_role(role_name)

    def run(self, request):
        run = super().run(request)
        if request.role_name != "critic":
            return run
        return replace(
            run,
            ok=False,
            error="Schema validation failed.",
            schema_validation_errors=[
                "$.missing_topics: additional properties not allowed",
                "$.topics: required property missing",
            ],
        )


class _TopicCarryForwardHarnessAdapter(_TopicLifecycleHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "reviser_round_1":
            payload = self._base_analysis(revised=True)
            payload["topic_resolution_map"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "status": "not_addressed",
                    "recommendation_index": 2,
                    "change_summary": "The recommendation text improved, but the fallback classification is still too implicit.",
                    "residual_risk": "Operators still need a concrete fallback label.",
                }
            ]
            return payload
        if role_name == "auditor":
            return {
                "verdict": "accept",
                "summary": "The revision improved recommendation 2, but the topic remains open.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 1 remains acceptable.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "accept_with_caveat",
                        "open_issue_ids": [],
                        "summary": "Recommendation 2 improved, but the fallback classification is still implicit.",
                        "confidence_assessment": "well_calibrated",
                    },
                ],
                "topics": [],
                "resolved_topic_ids": [],
                "carried_forward_topic_ids": [self._TOPIC_ID],
                "waived_topic_ids": [],
                "grounding_score": 0.92,
                "actionability_score": 0.83,
                "scope_compliance_score": 0.95,
                "confidence": 0.88,
                "scope_escapes": [],
            }
        return super()._payload_for_role(role_name)


class _TopicDisagreeHarnessAdapter(_TopicLifecycleHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "reviser_round_1":
            payload = self._base_analysis(revised=True)
            payload["topic_resolution_map"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "status": "disagree",
                    "recommendation_index": 2,
                    "change_summary": "Kept the original recommendation because the requested fallback classification is not directly supported by the inspected workflow evidence.",
                    "residual_risk": "Operators may still want an explicit fallback label, but the evidence does not justify inventing one.",
                }
            ]
            return payload
        if role_name == "auditor":
            return {
                "verdict": "accept",
                "summary": "The recommendation remains usable and the open topic is being recorded as a disagreement rather than a waiver.",
                "workspace_write_intent": "none",
                "files_reviewed": self._review_files_reviewed(),
                "issues": [],
                "resolved_issue_ids": [],
                "carried_forward_issue_ids": [],
                "waived_issue_ids": [],
                "recommendation_reviews": [
                    {
                        "recommendation_index": 1,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 1 remains acceptable.",
                        "confidence_assessment": "well_calibrated",
                    },
                    {
                        "recommendation_index": 2,
                        "verdict": "accept",
                        "open_issue_ids": [],
                        "summary": "Recommendation 2 is acceptable, but the fallback classification request is recorded as a disagreement.",
                        "confidence_assessment": "well_calibrated",
                    },
                ],
                "topics": [],
                "resolved_topic_ids": [],
                "carried_forward_topic_ids": [],
                "waived_topic_ids": [self._TOPIC_ID],
                "grounding_score": 0.93,
                "actionability_score": 0.86,
                "scope_compliance_score": 0.96,
                "confidence": 0.89,
                "scope_escapes": [],
            }
        return super()._payload_for_role(role_name)


class _PartialAcceptanceWithTopicDebtHarnessAdapter(_PartialAcceptanceHarnessAdapter):
    _TOPIC_ID = "TOPIC-001"

    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"].append(
            {
                "classification": "recommendation",
                "priority": "medium",
                "title": "Document alert routing ownership",
                "rationale": "Operators need a clear escalation target when release automation fails.",
                "evidence": [".github/workflows/codex-cli-release-watch.yml"],
                "proposed_change": "Add the alert-routing owner and escalation path to the release-watch documentation.",
                "confidence": 0.72 if not revised else 0.76,
                "review_surface": self._review_surface(
                    must_check_files=[".github/workflows/codex-cli-release-watch.yml"],
                    optional_check_files=[],
                    scope_note="Keep the review bounded to the existing release-watch escalation path.",
                ),
            }
        )
        return self._apply_analysis_seams(payload)

    def _payload_for_role(self, role_name: str):
        if role_name == "critic":
            payload = super()._payload_for_role(role_name)
            payload["summary"] = (
                "Recommendations 1 and 4 are good, recommendation 2 still has a topic, and recommendation 3 needs more specificity."
            )
            payload["recommendation_reviews"].append(
                {
                    "recommendation_index": 4,
                    "verdict": "accept",
                    "open_issue_ids": [],
                    "summary": "Recommendation 4 is acceptable.",
                    "confidence_assessment": "well_calibrated",
                }
            )
            payload["topics"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "severity": "medium",
                    "title": "Recommendation 2 still needs an explicit operator fallback classification.",
                    "evidence": "The timeout recommendation still leaves the operator fallback label implicit.",
                    "repair_hint": "Name the fallback classification directly in recommendation 2.",
                    "recommendation_index": 2,
                }
            ]
            return payload
        if role_name == "reviser_round_1":
            payload = super()._payload_for_role(role_name)
            payload["topic_resolution_map"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "status": "not_addressed",
                    "recommendation_index": 2,
                    "change_summary": "The revision kept recommendation 2 high level and did not add a concrete fallback classification.",
                    "residual_risk": "Operators still do not have an explicit fallback label to follow.",
                }
            ]
            return payload
        if role_name == "auditor":
            payload = super()._payload_for_role(role_name)
            payload["summary"] = (
                "Recommendations 1 and 4 are usable. Recommendation 2 still carries topic debt and recommendation 3 still needs more specificity."
            )
            payload["recommendation_reviews"].append(
                {
                    "recommendation_index": 4,
                    "verdict": "accept",
                    "open_issue_ids": [],
                    "summary": "Recommendation 4 remains acceptable.",
                    "confidence_assessment": "well_calibrated",
                }
            )
            payload["carried_forward_topic_ids"] = [self._TOPIC_ID]
            return payload
        return super()._payload_for_role(role_name)


class _PartialAcceptanceWithGlobalTopicDebtHarnessAdapter(
    _PartialAcceptanceHarnessAdapter
):
    _TOPIC_ID = "TOPIC-001"

    def _payload_for_role(self, role_name: str):
        if role_name == "critic":
            payload = super()._payload_for_role(role_name)
            payload["summary"] = (
                "Recommendations 1 and 2 are usable, recommendation 3 needs more specificity, and one global topic remains unresolved."
            )
            payload["topics"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "severity": "medium",
                    "title": "The final answer still needs a concrete fallback classification policy.",
                    "evidence": "The analysis never states the fallback classification policy, so no clean subset can be proven yet.",
                    "repair_hint": "State the fallback classification policy or explicitly justify why none should be named.",
                    "recommendation_index": None,
                }
            ]
            return payload
        if role_name == "reviser_round_1":
            payload = super()._payload_for_role(role_name)
            payload["topic_resolution_map"] = [
                {
                    "topic_id": self._TOPIC_ID,
                    "status": "not_addressed",
                    "recommendation_index": None,
                    "change_summary": "The revision improved individual recommendations but did not establish a shared fallback classification policy.",
                    "residual_risk": "A global ambiguity still spans the accepted subset.",
                }
            ]
            return payload
        if role_name == "auditor":
            payload = super()._payload_for_role(role_name)
            payload["summary"] = (
                "Recommendations 1 and 2 would otherwise be usable, but the unresolved global topic blocks a clean partial subset."
            )
            payload["carried_forward_topic_ids"] = [self._TOPIC_ID]
            return payload
        return super()._payload_for_role(role_name)


class _TopicResolutionRecommendationHarnessAdapter(_TopicLifecycleHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "critic":
            payload = super()._payload_for_role(role_name)
            payload["topics"][0]["recommendation_index"] = None
            return payload
        return super()._payload_for_role(role_name)


class _TrustTopicResolutionRecommendationHarnessAdapter(
    _TopicResolutionRecommendationHarnessAdapter
):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"][0]["verified_evidence_refs"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["checked_files"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["affected_files"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["grounding_mode"] = "direct"
        payload["recommendations"][1]["verified_evidence_refs"] = []
        payload["recommendations"][1]["checked_files"] = []
        payload["recommendations"][1]["affected_files"] = [
            ".github/workflows/claude-code-release-watch.yml"
        ]
        payload["recommendations"][1]["grounding_mode"] = "inferred"
        return payload

    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name in {"critic", "auditor"}:
            payload["files_reviewed"] = [
                ".github/workflows/codex-cli-release-watch.yml",
                ".github/workflows/claude-code-release-watch.yml",
            ]
            payload["recommendation_reviews"][0]["checked_files"] = [
                ".github/workflows/codex-cli-release-watch.yml"
            ]
            payload["recommendation_reviews"][0]["verified_evidence_refs"] = [
                ".github/workflows/codex-cli-release-watch.yml"
            ]
            payload["recommendation_reviews"][1]["checked_files"] = [
                ".github/workflows/claude-code-release-watch.yml"
            ]
            payload["recommendation_reviews"][1]["verified_evidence_refs"] = [
                ".github/workflows/claude-code-release-watch.yml"
            ]
        return payload


class _TrustInferenceHarnessAdapter(_AcceptingHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"][0]["verified_evidence_refs"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["checked_files"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["affected_files"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["grounding_mode"] = "direct"
        payload["recommendations"][1]["verified_evidence_refs"] = []
        payload["recommendations"][1]["checked_files"] = []
        payload["recommendations"][1]["affected_files"] = [
            ".github/workflows/claude-code-release-watch.yml"
        ]
        payload["recommendations"][1]["grounding_mode"] = "inferred"
        return payload

    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name in {"critic", "auditor"}:
            payload["files_reviewed"] = [
                ".github/workflows/codex-cli-release-watch.yml",
                ".github/workflows/claude-code-release-watch.yml",
            ]
            payload["recommendation_reviews"][0]["checked_files"] = [
                ".github/workflows/codex-cli-release-watch.yml"
            ]
            payload["recommendation_reviews"][0]["verified_evidence_refs"] = [
                ".github/workflows/codex-cli-release-watch.yml"
            ]
            payload["recommendation_reviews"][1]["checked_files"] = [
                ".github/workflows/claude-code-release-watch.yml"
            ]
            payload["recommendation_reviews"][1]["verified_evidence_refs"] = [
                ".github/workflows/claude-code-release-watch.yml"
            ]
        return payload


class _TrustSemanticWarningHarnessAdapter(_TrustInferenceHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["strengths"][
            "none_reason"
        ] = "The summary section still includes a redundant none_reason."
        return payload


class _TrustZeroRefReviewHarnessAdapter(_TopicLifecycleHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"][0]["verified_evidence_refs"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["checked_files"] = [
            ".github/workflows/codex-cli-release-watch.yml"
        ]
        payload["recommendations"][0]["grounding_mode"] = "direct"
        payload["recommendations"][1]["verified_evidence_refs"] = [
            ".github/workflows/claude-code-release-watch.yml"
        ]
        payload["recommendations"][1]["checked_files"] = [
            ".github/workflows/claude-code-release-watch.yml"
        ]
        payload["recommendations"][1]["grounding_mode"] = "direct"
        return payload

    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name in {"critic", "auditor"}:
            payload["files_reviewed"] = []
        return payload


class _TrustTopLevelOnlyRefReviewHarnessAdapter(_TrustZeroRefReviewHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        payload = _TopicLifecycleHarnessAdapter._payload_for_role(self, role_name)
        if role_name in {"critic", "auditor"}:
            payload["files_reviewed"] = [
                ".github/workflows/codex-cli-release-watch.yml",
                ".github/workflows/claude-code-release-watch.yml",
            ]
            for item in payload.get("recommendation_reviews", []):
                if not isinstance(item, dict):
                    continue
                item.pop("checked_files", None)
                item.pop("verified_evidence_refs", None)
        return payload


class _TrustGlobalTopicClosureHarnessAdapter(_TrustInferenceHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name in {"critic", "auditor"}:
            payload["topics"] = []
            payload["carried_forward_topic_ids"] = ["TOPIC-001"]
            payload["topic_closure_reviews"] = []
        return payload


class _TrustGlobalIssueClosureHarnessAdapter(_TrustInferenceHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name in {"critic", "auditor"}:
            payload["issues"] = []
            payload["carried_forward_issue_ids"] = ["AR-001"]
            payload["issue_closure_reviews"] = []
        return payload


class _TrustGlobalIssueLifecycleHarnessAdapter(_TrustInferenceHarnessAdapter):
    _ISSUE_ID = "AR-001"

    def _payload_for_role(self, role_name: str):
        if role_name == "critic":
            payload = super()._payload_for_role(role_name)
            payload["verdict"] = "revise"
            payload["summary"] = (
                "A global issue remains open and needs explicit tracking."
            )
            payload["issues"] = [
                {
                    "issue_id": self._ISSUE_ID,
                    "severity": "medium",
                    "kind": "missing_evidence",
                    "blocking_class": "correctness",
                    "recommendation_index": None,
                    "title": "A global evidence invariant remains unresolved.",
                    "evidence": "The review still depends on a repo-wide workflow invariant that is not fully closed.",
                    "repair_hint": "Keep the global issue tracked until the invariant is proven or explicitly narrowed.",
                    "blocking_class_override_reason": None,
                    "why_not_raised_earlier": None,
                }
            ]
            payload["resolved_issue_ids"] = []
            payload["carried_forward_issue_ids"] = []
            payload["waived_issue_ids"] = []
            payload["issue_closure_reviews"] = []
            return payload
        if role_name == "reviser_round_1":
            payload = self._base_analysis(revised=True)
            payload["issue_resolution_map"] = [
                {
                    "issue_id": self._ISSUE_ID,
                    "status": "not_addressed",
                    "change_summary": "The revision improved the recommendations but did not close the global invariant.",
                    "residual_risk": "The run still depends on a global workflow claim.",
                }
            ]
            return payload
        if role_name == "auditor":
            payload = super()._payload_for_role(role_name)
            payload["verdict"] = "accept_partial"
            payload["summary"] = (
                "The recommendations are usable, and the remaining global issue is explicitly carried forward with scoped proof."
            )
            payload["issues"] = []
            payload["resolved_issue_ids"] = []
            payload["carried_forward_issue_ids"] = [self._ISSUE_ID]
            payload["waived_issue_ids"] = []
            payload["issue_closure_reviews"] = [
                {
                    "issue_id": self._ISSUE_ID,
                    "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
                    "verified_evidence_refs": [
                        ".github/workflows/codex-cli-release-watch.yml"
                    ],
                    "summary": "The carried-forward global issue was re-checked directly.",
                }
            ]
            return payload
        return super()._payload_for_role(role_name)


class _TrustVerdictWithoutRefsHarnessAdapter(_AcceptingHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name in {"critic", "auditor"}:
            payload["files_reviewed"] = self._review_files_reviewed()
            payload.update(self._empty_topic_state())
        return payload


class _PartialAcceptanceLocalizedAcceptedIssueHarnessAdapter(
    _PartialAcceptanceHarnessAdapter
):
    def __init__(self, *, blocking_class: str) -> None:
        self.blocking_class = blocking_class

    def _payload_for_role(self, role_name: str):
        payload = super()._payload_for_role(role_name)
        if role_name != "auditor":
            return payload
        payload["issues"] = [
            {
                "issue_id": "AR-001",
                "severity": "medium",
                "kind": (
                    "insufficient_specificity"
                    if self.blocking_class != "correctness"
                    else "missing_evidence"
                ),
                "blocking_class": self.blocking_class,
                "recommendation_index": 2,
                "title": "Recommendation 2 still carries localized review debt.",
                "evidence": "The accepted recommendation still has one bounded review gap.",
                "repair_hint": "Close the remaining localized gap before clean acceptance.",
                "why_not_raised_earlier": None,
            }
        ]
        payload["recommendation_reviews"] = [
            {
                "recommendation_index": 1,
                "verdict": "accept",
                "open_issue_ids": [],
                "summary": "Strong recommendation.",
                "confidence_assessment": "well_calibrated",
            },
            {
                "recommendation_index": 2,
                "verdict": "accept_with_caveat",
                "open_issue_ids": ["AR-001"],
                "summary": "Usable recommendation with one bounded issue still open.",
                "confidence_assessment": "well_calibrated",
            },
            {
                "recommendation_index": 3,
                "verdict": "revise",
                "open_issue_ids": [],
                "summary": "Still excluded from the accepted subset.",
                "confidence_assessment": "too_low",
            },
        ]
        payload["carried_forward_issue_ids"] = ["AR-001"]
        return payload


class _QuotaFailingReviewHarnessAdapter(_AcceptingHarnessAdapter):
    def run(self, request):
        if request.role_name == "critic":
            out_dir = Path(request.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "result": "You've hit your limit · resets 1pm (America/Indiana/Indianapolis)",
            }
            (out_dir / "response.txt").write_text("quota", encoding="utf-8")
            (out_dir / "error.txt").write_text(payload["result"], encoding="utf-8")
            (out_dir / "structured_output.raw.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            return ProviderRun(
                role_name=request.role_name,
                provider="fake-claude",
                model="fake-model",
                access=request.role_config.access,
                ok=False,
                exit_code=1,
                duration_sec=0.01,
                cwd=request.cwd,
                command=["fake-claude"],
                stdout_path=str(out_dir / "response.txt"),
                stderr_path=str(out_dir / "error.txt"),
                prompt_path=str(out_dir / "prompt.txt"),
                schema_path=str(out_dir / "schema.json"),
                output_path=str(out_dir / "structured_output.normalized.json"),
                raw_output_path=str(out_dir / "structured_output.raw.json"),
                normalized_output_path=str(
                    out_dir / "structured_output.normalized.json"
                ),
                structured_output=payload,
                raw_meta={},
                error="Provider quota exhausted: You've hit your limit · resets 1pm (America/Indiana/Indianapolis)",
                failure_kind="quota_exhausted",
                failure_summary="Provider quota exhausted: You've hit your limit · resets 1pm (America/Indiana/Indianapolis)",
            )
        return super().run(request)


class _ReviserFailingHarnessAdapter(_PartialAcceptanceHarnessAdapter):
    def run(self, request):
        if request.role_name == "reviser_round_1":
            return _failed_provider_run(
                request,
                message="Reviser provider unavailable during round 1.",
            )
        return super().run(request)


class _AuditorFailingHarnessAdapter(_PartialAcceptanceHarnessAdapter):
    def run(self, request):
        if request.role_name == "auditor":
            return _failed_provider_run(
                request,
                message="Auditor provider unavailable during round 1.",
            )
        return super().run(request)


class _LineQualifiedEvidenceHarnessAdapter(_AcceptingHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"][0]["evidence"] = [
            ".github/workflows/claude-code-release-watch.yml:10-18",
            ".github/workflows/codex-cli-release-watch.yml:20-28",
            ".github/workflows/claude-code-update-snapshot.yml:30-44",
            ".github/workflows/codex-cli-update-snapshot.yml:50-68",
        ]
        payload["files_reviewed"] = [
            ".github/workflows/claude-code-release-watch.yml:10-18",
            ".github/workflows/codex-cli-release-watch.yml:20-28",
            ".github/workflows/claude-code-update-snapshot.yml:30-44",
            ".github/workflows/codex-cli-update-snapshot.yml:50-68",
        ]
        payload["recommendations"][0]["review_surface"]["must_check_files"] = [
            ".github/workflows/claude-code-release-watch.yml:10-18",
            ".github/workflows/codex-cli-release-watch.yml:20-28",
            ".github/workflows/claude-code-update-snapshot.yml:30-44",
        ]
        payload["recommendations"][0]["review_surface"]["optional_check_files"] = [
            ".github/workflows/codex-cli-update-snapshot.yml:50-68"
        ]
        return payload


class _TrustLineQualifiedEvidenceHarnessAdapter(_TrustInferenceHarnessAdapter):
    def _base_analysis(self, *, revised: bool) -> dict:
        payload = super()._base_analysis(revised=revised)
        payload["recommendations"][0]["evidence"] = [
            ".github/workflows/claude-code-release-watch.yml:10-18",
            ".github/workflows/codex-cli-release-watch.yml:20-28",
            ".github/workflows/claude-code-update-snapshot.yml:30-44",
            ".github/workflows/codex-cli-update-snapshot.yml:50-68",
        ]
        payload["files_reviewed"] = [
            ".github/workflows/claude-code-release-watch.yml:10-18",
            ".github/workflows/codex-cli-release-watch.yml:20-28",
            ".github/workflows/claude-code-update-snapshot.yml:30-44",
            ".github/workflows/codex-cli-update-snapshot.yml:50-68",
        ]
        payload["recommendations"][0]["review_surface"]["must_check_files"] = [
            ".github/workflows/claude-code-release-watch.yml:10-18",
            ".github/workflows/codex-cli-release-watch.yml:20-28",
            ".github/workflows/claude-code-update-snapshot.yml:30-44",
        ]
        payload["recommendations"][0]["review_surface"]["optional_check_files"] = [
            ".github/workflows/codex-cli-update-snapshot.yml:50-68"
        ]
        return payload


def _write_task_and_strategy(
    tmp_path: Path,
    *,
    min_recommendations: int = 2,
    evidence_cap_policy: str = "trim_to_cap",
    review_max_loops: int | None = None,
    strategy_kind: str = "analysis_review_bounded_v1",
    task_focus_gate: str = "",
    task_focus_gate_answer: str = "",
    strategy_focus_gate: str = "",
    include_focus_gate_role: bool = False,
) -> tuple[Path, Path]:
    task_path = tmp_path / "task.yaml"
    task_path.write_text(
        f"""
id: recommend_automation_improvements
task_kind: analysis_review
objective: Review the CI/CD automation and recommend improvements.
workspace_write_policy:
  mode: forbid
  allow_untracked: false
  allow_renames: false
  allow_deletions: false
  max_touched_files: 0
acceptance:
  - Ground each recommendation in repo evidence.
review_requirements:
  require_evidence_per_recommendation: true
  require_classification: true
  require_priority: true
  min_recommendations: {min_recommendations}
  evidence_cap_policy: {evidence_cap_policy}
{task_focus_gate}{task_focus_gate_answer}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    strategy_path = tmp_path / "strategy.yaml"
    review_loops = ""
    if review_max_loops is not None:
        review_loops = f"""
review_loops:
  max_loops: {review_max_loops}
"""
    focus_gate_role = ""
    if include_focus_gate_role:
        focus_gate_role = """
  focus_gate:
    provider: fake
    access: write
"""
    strategy_path.write_text(
        f"""
name: analysis-review-fake
kind: {strategy_kind}
roles:
  proposer:
    provider: fake
    access: write
  critic:
    provider: fake
    access: read
  reviser:
    provider: fake
    access: write
  auditor:
    provider: fake
    access: read
{focus_gate_role}{strategy_focus_gate}
validators: []
{review_loops}""".strip()
        + "\n",
        encoding="utf-8",
    )
    return task_path, strategy_path


def _task_focus_gate_block(
    *,
    enabled: bool = True,
    clarification_policy: str = "block_for_clarification",
) -> str:
    return (
        "focus_gate:\n"
        f"  enabled: {'true' if enabled else 'false'}\n"
        "  allowed_focus_types:\n"
        "    - seam\n"
        f"  clarification_policy: {clarification_policy}\n"
    )


def _task_focus_gate_answer_block(
    *, question_prompt: str, selected_option: str, freeform_answer: str = ""
) -> str:
    return (
        "focus_gate_answer:\n"
        f'  question_prompt: "{question_prompt}"\n'
        f'  selected_option: "{selected_option}"\n'
        f'  freeform_answer: "{freeform_answer}"\n'
    )


def _strategy_focus_gate_block(*, enabled: bool = True, default_path: str) -> str:
    return (
        "focus_gate:\n"
        f"  enabled: {'true' if enabled else 'false'}\n"
        f"  default_path: {default_path}\n"
    )


def _prepare_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (workspace / "docs" / "project_management" / "next" / "codex-cli-parity").mkdir(
        parents=True, exist_ok=True
    )
    (workspace / ".github" / "workflows" / "codex-cli-release-watch.yml").write_text(
        "name: codex\n",
        encoding="utf-8",
    )
    (workspace / ".github" / "workflows" / "claude-code-release-watch.yml").write_text(
        "name: claude\n",
        encoding="utf-8",
    )
    (
        workspace / ".github" / "workflows" / "claude-code-update-snapshot.yml"
    ).write_text(
        "name: claude-update\n",
        encoding="utf-8",
    )
    (workspace / ".github" / "workflows" / "codex-cli-update-snapshot.yml").write_text(
        "name: codex-update\n",
        encoding="utf-8",
    )
    (
        workspace
        / "docs"
        / "project_management"
        / "next"
        / "codex-cli-parity"
        / "C1-spec.md"
    ).write_text(
        "# Codex CLI parity spec\n",
        encoding="utf-8",
    )
    return workspace


def _make_analysis_status_runner(
    tmp_path: Path,
    *,
    strategy_kind: str = "analysis_review_trust_v1",
) -> HarnessRunner:
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind=strategy_kind,
    )
    return HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )


def _run_analysis_review_summary(
    tmp_path: Path,
    monkeypatch,
    *,
    provider_factory,
    workspace: Path,
    strategy_kind: str,
    specs_dir_name: str,
    runs_dir_name: str,
) -> tuple[HarnessRunner, dict[str, object]]:
    specs_dir = tmp_path / specs_dir_name
    specs_dir.mkdir()
    task_path, strategy_path = _write_task_and_strategy(
        specs_dir,
        strategy_kind=strategy_kind,
    )
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", provider_factory)
    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / runs_dir_name,
    )
    return runner, runner.run()


def _stage_with_provenance(
    *,
    stage_index: int,
    role_name: str,
    payload: dict[str, object],
    provenance_status: str = "bound",
    closure_provenance_satisfied: bool = True,
    semantic_validation_warnings: list[str] | None = None,
) -> dict[str, object]:
    return {
        "stage_index": stage_index,
        "role_name": role_name,
        "ok": True,
        "structured_output": payload,
        "semantic_validation_warnings": list(semantic_validation_warnings or []),
        "semantic_validation_payload_provenance": {
            "status": provenance_status,
            "policy_mode": "payload_hash_and_refs",
            "closure_provenance_satisfied": closure_provenance_satisfied,
            "normalized_ref_field_count": 1,
            "normalized_ref_count": 1,
        },
    }


def _build_recommendation_admissibility_status(
    runner: HarnessRunner,
    *,
    final_analysis_payload: dict[str, object],
    final_review_payload: dict[str, object],
    content_verdict: str = "accepted_with_warnings",
) -> dict[str, object]:
    runner.agent_stages = [
        _stage_with_provenance(
            stage_index=1,
            role_name="reviser_round_1",
            payload=final_analysis_payload,
        ),
        _stage_with_provenance(
            stage_index=2,
            role_name="auditor",
            payload=final_review_payload,
        ),
    ]
    return runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict=content_verdict,
    )


def test_analysis_review_runner_focus_gate_selected_records_stage_and_prompt_handoff(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="adjudicate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]
    focus_stage = summary["agent_stages"][0]
    proposer_stage = summary["agent_stages"][1]
    summary_json = _load_run_summary_json(runner)

    assert summary["verdict"] == "accepted"
    assert focus_decision["decision_state"] == "selected"
    assert focus_decision["decision_basis"] == "request_only"
    assert summary["run_details"]["focus_decision"] == focus_decision
    assert summary_json["focus_decision"] == focus_decision
    assert [stage["role_name"] for stage in summary["agent_stages"][:2]] == [
        "focus_gate",
        "proposer",
    ]
    assert focus_stage["role_name"] == "focus_gate"
    assert focus_stage["requested_access"] == "read"
    assert focus_stage["effective_access"] == "read"
    assert focus_stage["round_index"] == 0
    assert focus_stage["stage_index"] < proposer_stage["stage_index"]
    assert focus_stage["metadata"]["focus_gate"] == {
        "gate_path": "adjudicate",
        "focus_type": "seam",
        "decision_state": "selected",
    }
    assert "focus_gate_probe" not in adapter.prompt_texts
    assert "Focus Gate Decision:" in adapter.prompt_texts["proposer"][-1]
    assert (
        f"selected_focus_id: {_SIMPLE_PRIMARY_CANONICAL_SEAM_ID}"
        in adapter.prompt_texts["proposer"][-1]
    )


def test_analysis_review_runner_focus_gate_clarification_blocks_before_proposer(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]
    probe_stage, focus_stage = summary["agent_stages"]

    assert summary["verdict"] == "blocked_for_clarification"
    assert summary["verdicts"]["content_verdict"] == "blocked_for_clarification"
    assert summary["verdicts"]["validator_verdict"] == "not_run"
    assert (
        summary["final_summary"] == "Focus gate blocked the run pending clarification."
    )
    assert summary["failure_details"] == {
        "stage": "focus_gate",
        "decision_state": "clarification_requested",
        "question": focus_decision["question"],
        "candidates": focus_decision["candidates"],
        "warnings": focus_decision["warnings"],
    }
    assert [stage["role_name"] for stage in summary["agent_stages"]] == [
        "focus_gate_probe",
        "focus_gate",
    ]
    assert focus_stage["round_index"] == 0
    assert summary["validator_rounds"] == []
    assert not summary.get("analysis_review_status")
    assert Path(summary["artifacts"]["summary_json"]).exists()
    assert Path(summary["artifacts"]["report_md"]).exists()


def test_analysis_review_runner_focus_gate_no_viable_blocks_before_proposer(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="adjudicate"),
    )

    adapter = _NoViableFocusHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "no_viable_focus"
    assert summary["verdicts"]["content_verdict"] == "no_viable_focus"
    assert summary["verdicts"]["validator_verdict"] == "not_run"
    assert (
        summary["final_summary"]
        == "Focus gate could not identify a viable focus target."
    )
    assert summary["failure_details"] == {
        "stage": "focus_gate",
        "decision_state": "no_viable_focus",
        "candidates": focus_decision["candidates"],
        "warnings": focus_decision["warnings"],
    }
    assert [stage["role_name"] for stage in summary["agent_stages"]] == ["focus_gate"]
    assert summary["validator_rounds"] == []
    assert not summary.get("analysis_review_status")
    assert Path(summary["artifacts"]["summary_json"]).exists()
    assert Path(summary["artifacts"]["report_md"]).exists()


def test_analysis_review_runner_focus_gate_matching_threshold_valid_rerun_answer_uses_deliberate(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _ThresholdValidRerunWinnerHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    _, focus_stage = summary["agent_stages"][:2]

    assert summary["verdict"] == "accepted"
    assert [stage["role_name"] for stage in summary["agent_stages"][:2]] == [
        "focus_gate_probe",
        "focus_gate",
    ]
    assert focus_stage["structured_output"]["gate_path"] == "deliberate"
    assert focus_stage["structured_output"]["decision_basis"] == "rerun_answer"
    assert len(adapter.prompt_texts["focus_gate_probe"]) == 1
    assert len(adapter.prompt_texts["focus_gate"]) == 1
    assert "Gate path: deliberate" in adapter.prompt_texts["focus_gate"][0]


def test_analysis_review_runner_focus_gate_ambiguous_rerun_answer_blocks_before_proposer(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "blocked_for_clarification"
    assert focus_decision["decision_state"] == "clarification_requested"
    assert focus_decision["decision_basis"] == "rerun_answer"
    assert focus_decision["question"]["prompt"] == _FOCUS_GATE_QUESTION_PROMPT
    assert any(
        "current probe is ambiguous under selection thresholds" in warning
        for warning in focus_decision["warnings"]
    )
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]


def test_analysis_review_runner_focus_gate_adjudicate_config_rejects_deliberate_return(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="adjudicate"),
    )

    adapter = _AdjudicateConfiguredReturnsDeliberateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_stage = summary["agent_stages"][0]

    assert summary["verdict"] == "harness_error"
    assert summary["failure_details"]["stage"] == "focus_gate"
    assert focus_stage["role_name"] == "focus_gate"
    assert focus_stage["failure_kind"] == "semantic_validation_error"
    assert [stage["role_name"] for stage in summary["agent_stages"]] == ["focus_gate"]
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]
    assert any(
        "gate_path must match expected_gate_path=adjudicate; got deliberate." in error
        for error in focus_stage["semantic_validation_errors"]
    )


def test_analysis_review_runner_focus_gate_adjudicate_normalizes_repo_probe_payload(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="adjudicate"),
    )

    adapter = _AdjudicateNonCanonicalRepoProbeHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]
    focus_stage = summary["agent_stages"][0]

    assert summary["verdict"] == "accepted"
    assert focus_decision["gate_path"] == "adjudicate"
    assert focus_decision["decision_basis"] == "request_only"
    assert focus_decision["files_hint_disposition"] == "absent"
    assert focus_decision["checked_files"] == []
    assert focus_decision["selected_focus_id"] == _SIMPLE_PRIMARY_CANONICAL_SEAM_ID
    assert (
        focus_decision["adapter_plan"]["primary_focus_id"]
        == _SIMPLE_PRIMARY_CANONICAL_SEAM_ID
    )
    assert (
        focus_decision["candidates"][0]["focus_id"] == _SIMPLE_PRIMARY_CANONICAL_SEAM_ID
    )
    assert focus_decision["candidates"][0]["evidence_refs"] == []
    assert focus_stage["structured_output"] == focus_decision


def test_analysis_review_runner_focus_gate_probe_dedupes_duplicate_canonical_candidates(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _DuplicateProbeCandidatesHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    probe_stage = summary["agent_stages"][0]
    probe_payload = probe_stage["structured_output"]

    assert summary["verdict"] == "accepted"
    assert probe_stage["role_name"] == "focus_gate_probe"
    assert len(probe_payload["candidates"]) == 1
    assert (
        probe_payload["candidates"][0]["focus_id"] == _SIMPLE_PRIMARY_CANONICAL_SEAM_ID
    )
    assert (
        probe_payload["candidates"][0]["focus_summary"]
        == "Highest-confidence release trigger seam."
    )
    assert (
        probe_payload["candidates"][0]["why_candidate"]
        == "The release workflow is the dominant seam after inspection."
    )
    assert probe_payload["candidates"][0]["evidence_refs"] == [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
    ]
    assert probe_stage["ok"] is True


def test_analysis_review_runner_focus_gate_clarification_dedupes_decision_candidates(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _ClarificationDuplicateFocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]
    focus_stage = summary["agent_stages"][1]

    assert summary["verdict"] == "blocked_for_clarification"
    assert focus_decision["decision_state"] == "clarification_requested"
    assert [item["focus_id"] for item in focus_decision["candidates"]] == [
        _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
    ]
    assert (
        focus_decision["candidates"][0]["focus_summary"]
        == "Highest-confidence release trigger seam."
    )
    assert focus_decision["candidates"][0]["evidence_refs"] == [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
    ]
    assert focus_decision["question"]["options"] == [
        _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
    ]
    assert focus_decision["adapter_plan"]["secondary_focus_ids"] == [
        _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
    ]
    assert focus_stage["structured_output"] == focus_decision


def test_analysis_review_runner_focus_gate_probe_caps_after_canonical_dedupe(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _ProbeCandidateOverflowHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    probe_payload = summary["agent_stages"][0]["structured_output"]

    assert summary["verdict"] == "accepted"
    assert [item["focus_id"] for item in probe_payload["candidates"]] == [
        _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        _OVERFLOW_OWNER_CANONICAL_SEAM_ID,
    ]


def test_analysis_review_runner_focus_gate_probe_invalid_candidates_consume_slots(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _InvalidProbeCandidateSlotsHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    probe_stage = summary["agent_stages"][0]
    probe_payload = probe_stage["structured_output"]

    assert summary["verdict"] == "harness_error"
    assert summary["failure_details"]["stage"] == "focus_gate"
    assert probe_stage["failure_kind"] == "schema_validation_error"
    assert [stage["role_name"] for stage in summary["agent_stages"]] == [
        "focus_gate_probe"
    ]
    assert len(probe_payload["candidates"]) == 3
    assert probe_payload["candidates"][0]["candidate_paths"] == []
    assert (
        probe_payload["candidates"][1]["focus_id"] == _SIMPLE_PRIMARY_CANONICAL_SEAM_ID
    )
    assert probe_payload["candidates"][1]["evidence_refs"] == [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
    ]
    assert (
        probe_payload["candidates"][2]["focus_id"] == _OVERFLOW_OWNER_CANONICAL_SEAM_ID
    )
    assert all(
        candidate["focus_id"] != _OVERFLOW_SPEC_CANONICAL_SEAM_ID
        for candidate in probe_payload["candidates"]
        if candidate.get("focus_id")
    )
    assert any(
        "candidate_paths" in error for error in probe_stage["schema_validation_errors"]
    )


def test_analysis_review_runner_focus_gate_mismatched_rerun_answer_normalizes_recorded_reask(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option="unknown-seam",
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _MismatchSelectsOnRecordedReaskHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]
    probe_stage, focus_stage = summary["agent_stages"][:2]
    focus_envelope = json.loads(
        Path(focus_stage["stdout_path"])
        .with_name("run.envelope.json")
        .read_text(encoding="utf-8")
    )

    assert summary["verdict"] == "blocked_for_clarification"
    assert summary["verdicts"]["content_verdict"] == "blocked_for_clarification"
    assert summary["verdicts"]["validator_verdict"] == "not_run"
    assert (
        summary["final_summary"] == "Focus gate blocked the run pending clarification."
    )
    assert summary["failure_details"]["stage"] == "focus_gate"
    assert summary["failure_details"]["decision_state"] == "clarification_requested"
    assert summary["failure_details"]["question"] == focus_decision["question"]
    assert summary["failure_details"]["candidates"] == focus_decision["candidates"]
    assert summary["failure_details"]["warnings"] == focus_decision["warnings"]
    assert summary["focus_decision"]["decision_state"] == "clarification_requested"
    assert [stage["role_name"] for stage in summary["agent_stages"]] == [
        "focus_gate_probe",
        "focus_gate",
    ]
    assert focus_stage["round_index"] == 0
    assert (
        focus_stage["structured_output"]["decision_state"] == "clarification_requested"
    )
    assert focus_stage["structured_output"]["gate_path"] == "deliberate"
    assert (
        focus_stage["metadata"]["focus_gate"]["decision_state"]
        == "clarification_requested"
    )
    assert focus_stage["metadata"]["focus_gate"]["gate_path"] == "deliberate"
    assert focus_stage["metadata"]["focus_gate"]["focus_type"] == "seam"
    assert (
        focus_decision["question"]["prompt"] == _FOCUS_GATE_QUESTION_PROMPT
    )
    assert (
        focus_envelope["structured_output"]["decision_state"]
        == "clarification_requested"
    )
    assert (
        focus_envelope["metadata"]["focus_gate"]["decision_state"]
        == "clarification_requested"
    )
    assert summary["validator_rounds"] == []
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]
    assert len(adapter.prompt_texts["focus_gate_probe"]) == 1
    assert len(adapter.prompt_texts["focus_gate"]) == 1
    assert "Gate path: deliberate" in adapter.prompt_texts["focus_gate"][0]


def test_analysis_review_runner_focus_gate_normalizes_clarification_question_options(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _DeliberateHumanQuestionOptionsHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "blocked_for_clarification"
    assert focus_decision["decision_state"] == "clarification_requested"
    assert focus_decision["question"]["options"] == [
        _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
    ]
    assert focus_decision["adapter_plan"]["secondary_focus_ids"] == [
        _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
    ]


@pytest.mark.parametrize(
    ("question_prompt", "selected_option"),
    [
        (_FOCUS_GATE_QUESTION_PROMPT, "unknown-seam"),
        ("Which seam is stale?", _SIMPLE_PRIMARY_CANONICAL_SEAM_ID),
    ],
)
def test_analysis_review_runner_focus_gate_mismatched_rerun_answer_reasks_once_and_blocks(
    tmp_path,
    monkeypatch,
    question_prompt,
    selected_option,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=question_prompt,
            selected_option=selected_option,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]
    probe_stage, focus_stage = summary["agent_stages"][:2]

    assert summary["verdict"] == "blocked_for_clarification"
    assert summary["verdicts"]["content_verdict"] == "blocked_for_clarification"
    assert summary["verdicts"]["validator_verdict"] == "not_run"
    assert (
        summary["final_summary"] == "Focus gate blocked the run pending clarification."
    )
    assert summary["failure_details"]["stage"] == "focus_gate"
    assert summary["failure_details"]["decision_state"] == "clarification_requested"
    assert summary["failure_details"]["question"] == focus_decision["question"]
    assert summary["failure_details"]["candidates"] == focus_decision["candidates"]
    assert summary["failure_details"]["warnings"] == focus_decision["warnings"]
    assert summary["focus_decision"]["decision_state"] == "clarification_requested"
    assert [stage["role_name"] for stage in summary["agent_stages"]] == [
        "focus_gate_probe",
        "focus_gate",
    ]
    assert focus_stage["round_index"] == 0
    assert (
        focus_stage["structured_output"]["decision_state"] == "clarification_requested"
    )
    assert (
        focus_stage["metadata"]["focus_gate"]["decision_state"]
        == "clarification_requested"
    )
    assert focus_stage["metadata"]["focus_gate"]["gate_path"] == "deliberate"
    assert focus_stage["metadata"]["focus_gate"]["focus_type"] == "seam"
    assert summary["validator_rounds"] == []
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]
    assert focus_decision["question"]["prompt"] == _FOCUS_GATE_QUESTION_PROMPT
    assert len(adapter.prompt_texts["focus_gate_probe"]) == 1
    assert len(adapter.prompt_texts["focus_gate"]) == 1
    assert "Gate path: deliberate" in adapter.prompt_texts["focus_gate"][0]


def test_analysis_review_runner_focus_gate_stale_rerun_never_ask_blocks_without_reask(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(clarification_policy="never_ask"),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option="unknown-seam",
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "no_viable_focus"
    assert focus_decision["decision_state"] == "no_viable_focus"
    assert focus_decision["question"] == {"prompt": "", "options": []}
    assert any(
        warning.startswith("Prior focus_gate_answer went stale:")
        for warning in focus_decision["warnings"]
    )
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]


def test_analysis_review_runner_focus_gate_ambiguous_rerun_answer_never_ask_blocks_without_selection(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(clarification_policy="never_ask"),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "no_viable_focus"
    assert focus_decision["decision_state"] == "no_viable_focus"
    assert focus_decision["question"] == {"prompt": "", "options": []}
    assert any(
        "current probe is ambiguous under selection thresholds" in warning
        for warning in focus_decision["warnings"]
    )
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]


def test_analysis_review_runner_focus_gate_rerun_answer_with_different_threshold_valid_winner_blocks(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _DifferentWinnerRerunStaleHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "blocked_for_clarification"
    assert focus_decision["decision_state"] == "clarification_requested"
    assert any(
        "different threshold-valid winner" in warning
        for warning in focus_decision["warnings"]
    )
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]


def test_analysis_review_runner_focus_gate_rerun_answer_hardening_normalizes_wrong_model_selection(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _HardeningMismatchedRerunWinnerHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "blocked_for_clarification"
    assert focus_decision["decision_state"] == "clarification_requested"
    assert any(
        "runner-computed admissible rerun seam" in warning
        for warning in focus_decision["warnings"]
    )
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]


def test_analysis_review_runner_focus_gate_single_medium_candidate_rerun_answer_blocks(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        task_focus_gate_answer=_task_focus_gate_answer_block(
            question_prompt=_FOCUS_GATE_QUESTION_PROMPT,
            selected_option=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        ),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="deliberate"),
    )

    adapter = _SingleCandidateMediumRerunHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    focus_decision = summary["focus_decision"]

    assert summary["verdict"] == "blocked_for_clarification"
    assert focus_decision["decision_state"] == "clarification_requested"
    assert focus_decision["question"]["prompt"] == _FOCUS_GATE_QUESTION_PROMPT
    assert focus_decision["question"]["options"] == [_SIMPLE_PRIMARY_CANONICAL_SEAM_ID]
    assert any(
        "current probe is ambiguous under selection thresholds" in warning
        for warning in focus_decision["warnings"]
    )
    assert "proposer" not in [stage["role_name"] for stage in summary["agent_stages"]]


def test_analysis_review_runner_focus_gate_selected_seam_drift_fails_semantic_validation(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="adjudicate"),
    )

    adapter = _DriftingFocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    summary = runner.run()
    proposer_stage = summary["agent_stages"][1]

    assert summary["verdict"] == "harness_error"
    assert proposer_stage["role_name"] == "proposer"
    assert proposer_stage["failure_kind"] == "semantic_validation_error"
    assert any(
        "primary_seam.paths drifted from the selected focus gate paths after normalization"
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )


def test_analysis_review_runner_proposer_raw_and_normalized_artifacts_show_drift(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        task_focus_gate=_task_focus_gate_block(),
        strategy_focus_gate=_strategy_focus_gate_block(default_path="adjudicate"),
    )

    adapter = _FocusGateHarnessAdapter()
    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: adapter)

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    original_normalize = runner._normalize_analysis_review_payload

    def _normalize_with_drift(*args, **kwargs):
        normalized, payload_provenance, warnings = original_normalize(*args, **kwargs)
        if kwargs.get("role_name") == "proposer":
            normalized["primary_seam"] = dict(normalized["primary_seam"])
            normalized["primary_seam"]["paths"] = [
                ".github/workflows/claude-code-release-watch.yml"
            ]
        return normalized, payload_provenance, warnings

    monkeypatch.setattr(
        runner,
        "_normalize_analysis_review_payload",
        _normalize_with_drift,
    )

    summary = runner.run()
    proposer_stage = summary["agent_stages"][1]
    raw_payload = load_structured_file(Path(proposer_stage["raw_output_path"]))
    normalized_payload = load_structured_file(
        Path(proposer_stage["normalized_output_path"])
    )

    assert summary["verdict"] == "harness_error"
    assert proposer_stage["role_name"] == "proposer"
    assert proposer_stage["failure_kind"] == "semantic_validation_error"
    assert raw_payload["primary_seam"]["paths"] == [
        ".github/workflows/codex-cli-release-watch.yml"
    ]
    assert normalized_payload["primary_seam"]["paths"] == [
        ".github/workflows/claude-code-release-watch.yml"
    ]
    assert (
        raw_payload["primary_seam"]["paths"]
        != normalized_payload["primary_seam"]["paths"]
    )
    assert any(
        "primary_seam.paths drifted from the selected focus gate paths after normalization"
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )


def test_analysis_review_runner_creates_final_answer_and_enforces_read_only(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider", lambda name: _AcceptingHarnessAdapter()
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    assert summary["verdicts"]["policy_verdict"] == "pass"
    assert summary["artifacts"]["final_answer_json"]
    assert summary["artifacts"]["final_answer_md"]
    assert Path(summary["artifacts"]["final_answer_json"]).exists()
    assert Path(summary["artifacts"]["final_answer_md"]).exists()
    assert Path(summary["artifacts"]["analysis_review_contract_json"]).exists()
    assert (
        summary["analysis_review_contract"]["contract_version"]
        == "analysis_review_v1_contract_v9"
    )
    assert summary["analysis_review_contract"]["mode"] == "bounded"
    assert (
        summary["analysis_review_contract"]["partial_acceptance"][
            "min_accepted_recommendations"
        ]
        == 2
    )
    assert (
        summary["analysis_review_contract"]["bounded_review"]["critic_issue_cap"] == 5
    )
    assert (
        summary["final_answer"]["recommendations"][0]["title"]
        == "Add concurrency controls"
    )
    assert summary["final_answer"]["recommendations"][0]["review_surface"][
        "must_check_files"
    ] == [".github/workflows/codex-cli-release-watch.yml"]
    assert summary["final_answer"]["strengths"]["items"] == [
        "Grounded in workflow files"
    ]
    assert summary["recommendation_reviews"][0]["verdict"] == "accept"
    assert summary["issue_ledger"] == []
    assert summary["topic_ledger"] == []
    assert summary["analysis_review_status"]["topic_ledger_count"] == 0
    assert summary["analysis_review_status"]["open_topic_ids"] == []
    assert summary["analysis_review_status"]["resolved_topic_ids"] == []
    assert summary["analysis_review_status"]["carried_forward_topic_ids"] == []
    assert summary["analysis_review_status"]["waived_topic_ids"] == []
    _assert_canonical_analysis_review_status(
        summary,
        expected_primary_seam_id=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        expected_secondary_seam_ids=[_SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID],
        expected_binding_seam_ids=[
            _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
        ],
    )
    _assert_summary_json_mirrors_analysis_review_status(runner, summary)
    assert summary["analysis_review_status"]["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1, 2],
        "partial_only_recommendation_indices": [],
        "excluded_recommendation_indices": [],
        "reasons_by_recommendation_index": {},
    }
    assert summary["analysis_review_coverage"]["review_loop_exercised"] is True
    bounded_review_summary = summary["bounded_review_summary"]
    assert bounded_review_summary == summary["run_details"]["bounded_review_summary"]
    assert bounded_review_summary["mode"] == "recommendation_review_surface"
    assert bounded_review_summary["recommendation_count"] == 2
    assert bounded_review_summary["recommendations_with_review_surface"] == 2
    assert bounded_review_summary["scope_escape_count"] == 0
    assert bounded_review_summary["scope_escapes"] == []
    assert bounded_review_summary["review_stages"] == [
        {
            "role_name": "critic",
            "round_index": 0,
            "issue_count": 0,
            "issue_cap": 5,
            "missing_topic_count": 0,
            "missing_topic_cap": 2,
            "new_topic_count": 0,
            "new_topic_cap": 2,
            "resolved_topic_count": 0,
            "carried_forward_topic_count": 0,
            "waived_topic_count": 0,
            "open_topic_count": 0,
            "new_medium_or_higher_issue_count": 0,
            "new_medium_or_higher_issue_cap": None,
            "topic_ledger_count": 0,
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
            "resolved_topic_count": 0,
            "carried_forward_topic_count": 0,
            "waived_topic_count": 0,
            "open_topic_count": 0,
            "new_medium_or_higher_issue_count": 0,
            "new_medium_or_higher_issue_cap": 1,
            "topic_ledger_count": 0,
            "scope_escape_count": 0,
        },
    ]

    proposer_stage = summary["agent_stages"][0]
    reviser_stage = summary["agent_stages"][2]
    assert proposer_stage["requested_access"] == "write"
    assert proposer_stage["effective_access"] == "read"
    assert reviser_stage["requested_access"] == "write"
    assert reviser_stage["effective_access"] == "read"
    assert Path(proposer_stage["semantic_validation_path"]).exists()
    proposer_semantic = load_structured_file(
        Path(proposer_stage["semantic_validation_path"])
    )
    assert proposer_semantic["ok"] is True
    assert proposer_semantic["skipped"] is False
    assert proposer_semantic["payload_provenance"]["status"] == "not_required"
    assert proposer_semantic["payload_provenance"]["policy_mode"] == "none"
    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    final_answer_text = Path(summary["artifacts"]["final_answer_md"]).read_text(
        encoding="utf-8"
    )
    assert "## Review Scope" in report_text
    assert "## Bounded Review" not in report_text
    assert "## Analysis Review Status" in report_text
    assert "- Mode: `bounded`" in report_text
    assert "- Provenance status: `not_required`" in report_text
    assert (
        "- Recommendation indices withheld from `FINAL_ANSWER.*`: none" in report_text
    )
    assert "- Review surfaces declared: `2` / `2` recommendations" in report_text
    assert '"rendered_in_report_section": true' in report_text
    assert '"bounded_review_summary": {' in report_text
    assert (
        '"review_stages"'
        not in report_text.split('"bounded_review_summary": {', 1)[1].split("}", 1)[0]
    )
    assert "- Provenance status: `not_required`" in final_answer_text
    assert "- Provenance status: `bound`" not in final_answer_text


def test_analysis_review_runner_bounded_mode_can_ship_fuller_repo_local_recommendation_set(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _BoundedCorroborationHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    assert summary["analysis_review_contract"]["mode"] == "bounded"
    assert summary["artifacts"]["final_artifact_kind"] == "final_answer"
    _assert_canonical_analysis_review_status(
        summary,
        expected_primary_seam_id=_CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
        expected_secondary_seam_ids=[
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
            _SECONDARY_SNAPSHOT_CANONICAL_SEAM_ID,
        ],
        expected_binding_seam_ids=[
            _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            _SECONDARY_SNAPSHOT_CANONICAL_SEAM_ID,
            _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
        ],
    )
    _assert_summary_json_mirrors_analysis_review_status(runner, summary)

    final_recommendations = summary["final_answer"]["recommendations"]
    assert len(final_recommendations) == 4
    assert [recommendation["title"] for recommendation in final_recommendations] == [
        "Track release-watch issues against the parity spec",
        "Add concurrency controls",
        "Align timeout handling across the full snapshot parity seam",
        "Document alert routing ownership",
    ]

    spec_backed = final_recommendations[0]
    assert spec_backed["evidence"] == [
        ".github/workflows/codex-cli-release-watch.yml",
        "docs/project_management/next/codex-cli-parity/C1-spec.md",
    ]
    assert spec_backed["review_surface"]["must_check_files"] == [
        ".github/workflows/codex-cli-release-watch.yml",
        "docs/project_management/next/codex-cli-parity/C1-spec.md",
    ]

    parity = final_recommendations[2]
    assert parity["evidence"] == [
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/claude-code-update-snapshot.yml",
        ".github/workflows/codex-cli-update-snapshot.yml",
    ]
    assert parity["review_surface"]["must_check_files"] == [
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/claude-code-update-snapshot.yml",
        ".github/workflows/codex-cli-update-snapshot.yml",
    ]
    assert parity["review_surface"]["optional_check_files"] == [
        ".github/workflows/codex-cli-release-watch.yml"
    ]

    for recommendation in final_recommendations:
        assert len(recommendation["evidence"]) <= 3
        assert len(recommendation["review_surface"]["must_check_files"]) <= 3
        assert len(recommendation["review_surface"]["optional_check_files"]) <= 2

    bounded_review_summary = summary["bounded_review_summary"]
    assert bounded_review_summary["mode"] == "recommendation_review_surface"
    assert bounded_review_summary["recommendation_count"] == 4
    assert bounded_review_summary["recommendations_with_review_surface"] == 4
    assert bounded_review_summary["scope_escape_count"] == 0
    assert bounded_review_summary["scope_escapes"] == []


def test_analysis_review_runner_bounded_and_trust_modes_keep_canonical_seam_context_in_parity(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    bounded_runner, bounded_summary = _run_analysis_review_summary(
        tmp_path,
        monkeypatch,
        provider_factory=lambda name: _BoundedCorroborationHarnessAdapter(),
        workspace=workspace,
        strategy_kind="analysis_review_bounded_v1",
        specs_dir_name="bounded_specs",
        runs_dir_name="bounded_runs",
    )
    trust_runner, trust_summary = _run_analysis_review_summary(
        tmp_path,
        monkeypatch,
        provider_factory=lambda name: _TrustCorroborationHarnessAdapter(),
        workspace=workspace,
        strategy_kind="analysis_review_trust_v1",
        specs_dir_name="trust_specs",
        runs_dir_name="trust_runs",
    )

    assert _canonical_seam_context(bounded_summary) == _canonical_seam_context(
        trust_summary
    )
    assert (
        _canonical_seam_context(bounded_summary)["primary_seam"]["seam_id"]
        == _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID
    )
    assert bounded_summary["analysis_review_status"][
        "recommendation_admissibility"
    ] != (trust_summary["analysis_review_status"]["recommendation_admissibility"])
    assert bounded_summary["analysis_review_status"]["publishability"] != (
        trust_summary["analysis_review_status"]["publishability"]
    )
    assert bounded_summary["artifacts"]["final_artifact_kind"] == "final_answer"
    assert trust_summary["artifacts"]["final_artifact_kind"] == "partial_answer"
    _assert_summary_json_mirrors_analysis_review_status(bounded_runner, bounded_summary)
    _assert_summary_json_mirrors_analysis_review_status(trust_runner, trust_summary)


def test_analysis_review_runner_canonicalizes_relabeled_trust_seams_to_match_bounded(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    _, bounded_summary = _run_analysis_review_summary(
        tmp_path,
        monkeypatch,
        provider_factory=lambda name: _BoundedCorroborationHarnessAdapter(),
        workspace=workspace,
        strategy_kind="analysis_review_bounded_v1",
        specs_dir_name="relabeled_bounded_specs",
        runs_dir_name="relabeled_bounded_runs",
    )
    _, trust_summary = _run_analysis_review_summary(
        tmp_path,
        monkeypatch,
        provider_factory=lambda name: _RelabeledTrustCorroborationHarnessAdapter(),
        workspace=workspace,
        strategy_kind="analysis_review_trust_v1",
        specs_dir_name="relabeled_trust_specs",
        runs_dir_name="relabeled_trust_runs",
    )

    assert _canonical_seam_context(bounded_summary) == _canonical_seam_context(
        trust_summary
    )
    assert (
        trust_summary["analysis_review_status"]["primary_seam"]["seam_id"]
        == _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID
    )
    assert trust_summary["analysis_review_status"]["recommendation_seam_bindings"] == [
        {
            "recommendation_index": 1,
            "seam_id": _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            "seam_expansion_reason": "",
        },
        {
            "recommendation_index": 2,
            "seam_id": _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            "seam_expansion_reason": "",
        },
        {
            "recommendation_index": 3,
            "seam_id": _SECONDARY_SNAPSHOT_CANONICAL_SEAM_ID,
            "seam_expansion_reason": "Compare the sibling snapshot prepare seam before broadening the timeout recommendation.",
        },
        {
            "recommendation_index": 4,
            "seam_id": _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            "seam_expansion_reason": "",
        },
    ]


def test_analysis_review_runner_publishable_pair_can_still_drift_on_canonical_seam_context(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    _, bounded_summary = _run_analysis_review_summary(
        tmp_path,
        monkeypatch,
        provider_factory=lambda name: _BoundedCorroborationHarnessAdapter(),
        workspace=workspace,
        strategy_kind="analysis_review_bounded_v1",
        specs_dir_name="publishable_bounded_specs",
        runs_dir_name="publishable_bounded_runs",
    )
    _, trust_summary = _run_analysis_review_summary(
        tmp_path,
        monkeypatch,
        provider_factory=lambda name: _PublishableDriftTrustCorroborationHarnessAdapter(),
        workspace=workspace,
        strategy_kind="analysis_review_trust_v1",
        specs_dir_name="publishable_trust_specs",
        runs_dir_name="publishable_trust_runs",
    )

    assert bounded_summary["verdict"] == "accepted"
    assert trust_summary["verdict"] == "accepted"
    assert bounded_summary["artifacts"]["final_artifact_kind"] == "final_answer"
    assert trust_summary["artifacts"]["final_artifact_kind"] == "final_answer"
    assert (
        bounded_summary["analysis_review_status"]["publishability"][
            "final_answer_publishable"
        ]
        is True
    )
    assert (
        trust_summary["analysis_review_status"]["publishability"][
            "final_answer_publishable"
        ]
        is True
    )
    assert _canonical_seam_context(bounded_summary) != _canonical_seam_context(
        trust_summary
    )
    assert (
        bounded_summary["analysis_review_status"]["primary_seam"]["paths"]
        != trust_summary["analysis_review_status"]["primary_seam"]["paths"]
    )
    assert (
        bounded_summary["analysis_review_status"]["recommendation_seam_bindings"]
        != trust_summary["analysis_review_status"]["recommendation_seam_bindings"]
    )


def test_analysis_review_runner_trust_mode_preserves_shared_repo_local_seam_and_downgrades_only_inferred_grounding(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustCorroborationHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    expected_titles = [
        "Track release-watch issues against the parity spec",
        "Add concurrency controls",
        "Align timeout handling across the full snapshot parity seam",
        "Document alert routing ownership",
    ]

    assert summary["verdict"] == "accepted_with_warnings"
    assert summary["analysis_review_contract"]["mode"] == "trust"
    assert summary["analysis_review_status"]["mode"] == "trust"
    _assert_canonical_analysis_review_status(
        summary,
        expected_primary_seam_id=_CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
        expected_secondary_seam_ids=[
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
            _SECONDARY_SNAPSHOT_CANONICAL_SEAM_ID,
        ],
        expected_binding_seam_ids=[
            _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
            _SECONDARY_SNAPSHOT_CANONICAL_SEAM_ID,
            _CORROBORATION_PRIMARY_CANONICAL_SEAM_ID,
        ],
    )
    _assert_summary_json_mirrors_analysis_review_status(runner, summary)
    assert summary["analysis_review_status"]["provenance"]["status"] == "bound"
    assert (
        summary["analysis_review_status"]["provenance"][
            "uncovered_recommendation_indices"
        ]
        == []
    )
    assert summary["analysis_review_status"][
        "accepted_recommendations_with_inferred_grounding"
    ] == [3]
    assert (
        summary["analysis_review_status"]["accepted_recommendations_with_caveats"] == []
    )
    assert summary["analysis_review_status"]["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1, 2, 4],
        "partial_only_recommendation_indices": [3],
        "excluded_recommendation_indices": [],
        "reasons_by_recommendation_index": {
            "3": ["inferred_grounding"],
        },
    }
    assert summary["analysis_review_status"]["open_topic_ids"] == []
    assert summary["analysis_review_status"]["carried_forward_topic_ids"] == []
    assert summary["analysis_review_status"]["downgrade_causes"] == [
        "accepted recommendations rely on inference-only grounding: 3"
    ]
    assert summary["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert summary["partial_answer"]["included_recommendation_indices"] == [
        1,
        2,
        3,
        4,
    ]
    assert [item["title"] for item in summary["partial_answer"]["recommendations"]] == (
        expected_titles
    )
    assert summary["issue_ledger"] == []
    assert summary["topic_ledger"] == []
    assert all(
        item["verdict"] == "accept" for item in summary["recommendation_reviews"]
    )

    final_analysis_stage = next(
        stage
        for stage in reversed(summary["agent_stages"])
        if str(stage.get("role_name") or "") == "proposer"
        or str(stage.get("role_name") or "").startswith("reviser_round_")
    )
    final_analysis_payload = final_analysis_stage["structured_output"]
    assert [item["title"] for item in final_analysis_payload["recommendations"]] == (
        expected_titles
    )
    assert [
        item["grounding_mode"] for item in final_analysis_payload["recommendations"]
    ] == ["direct", "direct", "inferred", "direct"]

    review_stages = [
        stage
        for stage in summary["agent_stages"]
        if stage["role_name"] in {"critic", "auditor"}
    ]
    for stage in review_stages:
        recommendation_reviews = stage["structured_output"]["recommendation_reviews"]
        assert all(item["verdict"] == "accept" for item in recommendation_reviews)
        assert not any(
            item["verdict"] == "accept_with_caveat" for item in recommendation_reviews
        )

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "- Recommendation indices withheld from `FINAL_ANSWER.*`: `3`" in report_text
    assert "  - `3`: `inferred_grounding`" in report_text


def test_analysis_review_runner_legacy_alias_warns_and_normalizes_to_bounded(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider", lambda name: _AcceptingHarnessAdapter()
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    assert summary["strategy_kind"] == "analysis_review_bounded_v1"
    assert summary["analysis_review_contract"]["mode"] == "bounded"
    assert (
        "Strategy kind analysis_review_v1 is deprecated and now resolves to analysis_review_bounded_v1."
        in summary["warnings"]
    )


def test_analysis_review_runner_canonicalizes_line_qualified_refs_and_trims_evidence_by_default(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _LineQualifiedEvidenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    proposer_stage = summary["agent_stages"][0]
    proposer_payload = proposer_stage["structured_output"]
    assert proposer_payload["files_reviewed"] == [
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-update-snapshot.yml",
        ".github/workflows/codex-cli-update-snapshot.yml",
    ]
    assert proposer_payload["recommendations"][0]["evidence"] == [
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-update-snapshot.yml",
    ]
    assert proposer_payload["recommendations"][0]["review_surface"][
        "must_check_files"
    ] == [
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-update-snapshot.yml",
    ]
    proposer_semantic = load_structured_file(
        Path(proposer_stage["semantic_validation_path"])
    )
    assert proposer_semantic["ok"] is True
    assert proposer_semantic["warnings"] == [
        "recommendations[1].evidence exceeded the bounded-review cap of 3; trimmed dropped refs: .github/workflows/codex-cli-update-snapshot.yml"
    ]
    assert (
        proposer_stage["semantic_validation_warnings"] == proposer_semantic["warnings"]
    )
    assert any(
        "proposer: recommendations[1].evidence exceeded the bounded-review cap of 3; trimmed dropped refs: .github/workflows/codex-cli-update-snapshot.yml"
        == warning
        for warning in summary["warnings"]
    )


def test_analysis_review_runner_strict_evidence_cap_still_fails_fast(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        evidence_cap_policy="strict",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _LineQualifiedEvidenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    proposer_stage = summary["agent_stages"][0]
    assert any(
        "recommendations[1].evidence exceeds the bounded-review cap of 3 item(s)."
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )
    assert proposer_stage.get("semantic_validation_warnings") in (None, [])


def test_analysis_review_runner_trust_mode_preserves_uncapped_evidence_refs(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustLineQualifiedEvidenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted_with_warnings"
    proposer_stage = summary["agent_stages"][0]
    proposer_payload = proposer_stage["structured_output"]
    assert proposer_payload["recommendations"][0]["evidence"] == [
        ".github/workflows/claude-code-release-watch.yml",
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-update-snapshot.yml",
        ".github/workflows/codex-cli-update-snapshot.yml",
    ]
    assert proposer_stage.get("semantic_validation_warnings") in (None, [])
    assert not any("trimmed dropped refs" in warning for warning in summary["warnings"])


def test_analysis_review_runner_trust_mode_downgrades_inference_only_acceptance_and_reports_provenance(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustInferenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted_with_warnings"
    assert summary["analysis_review_contract"]["mode"] == "trust"
    assert summary["analysis_review_status"]["mode"] == "trust"
    assert summary["analysis_review_status"]["provenance"]["status"] == "bound"
    assert (
        summary["analysis_review_status"]["provenance"][
            "uncovered_recommendation_indices"
        ]
        == []
    )
    assert summary["analysis_review_status"][
        "accepted_recommendations_with_inferred_grounding"
    ] == [2]
    assert summary["analysis_review_status"]["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1],
        "partial_only_recommendation_indices": [2],
        "excluded_recommendation_indices": [],
        "reasons_by_recommendation_index": {
            "2": ["inferred_grounding"],
        },
    }
    assert (
        "accepted recommendations rely on inference-only grounding: 2"
        in summary["analysis_review_status"]["downgrade_causes"]
    )
    assert summary["artifacts"]["final_artifact_kind"] == "partial_answer"

    proposer_stage = summary["agent_stages"][0]
    critic_stage = next(
        stage for stage in summary["agent_stages"] if stage["role_name"] == "critic"
    )
    auditor_stage = next(
        stage for stage in summary["agent_stages"] if stage["role_name"] == "auditor"
    )
    semantic_payload = load_structured_file(
        Path(proposer_stage["semantic_validation_path"])
    )
    assert semantic_payload["payload_provenance"]["status"] == "bound"
    assert (
        semantic_payload["payload_provenance"]["policy_mode"] == "payload_hash_and_refs"
    )
    assert (
        critic_stage["semantic_validation_payload_provenance"]["normalized_ref_count"]
        > 0
    )
    assert (
        auditor_stage["semantic_validation_payload_provenance"]["normalized_ref_count"]
        > 0
    )
    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    partial_answer_text = Path(summary["artifacts"]["partial_answer_md"]).read_text(
        encoding="utf-8"
    )
    recommendation_two_section = partial_answer_text.split(
        "### 2. Align timeout handling", 1
    )[1]
    recommendation_two_section = recommendation_two_section.split("### ", 1)[0]
    recommendation_one_section = partial_answer_text.split(
        "### 1. Add concurrency controls", 1
    )[1]
    recommendation_one_section = recommendation_one_section.split("### ", 1)[0]
    assert "## Review Scope" in report_text
    assert "## Bounded Review" not in report_text
    assert "## Analysis Review Status" in report_text
    assert "- Mode: `trust`" in report_text
    assert "- Provenance status: `bound`" in report_text
    assert "- Recommendation indices withheld from `FINAL_ANSWER.*`: `2`" in report_text
    assert "Recommendation indices included in `PARTIAL_ANSWER.*`" not in report_text
    assert "Recommendation indices excluded from `PARTIAL_ANSWER.*`" not in report_text
    assert "  - `2`: `inferred_grounding`" in report_text
    assert "Accepted recommendations with inference-only grounding: 2" in report_text
    assert "This recommendation carries review caveats:" in recommendation_two_section
    assert (
        "This recommendation relies on inference-only grounding rather than direct verified evidence."
        in recommendation_two_section
    )
    assert (
        "This recommendation carries review caveats:" not in recommendation_one_section
    )


def test_analysis_review_runner_does_not_render_successful_cli_stderr_as_stage_error(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)
    fake_provider = _SuccessfulCliWarningProvider()

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: ForgeProviderAdapter(name),
    )
    monkeypatch.setattr(
        "anvil.harness.providers.get_provider_exact",
        lambda name: fake_provider,
    )
    monkeypatch.setattr(
        "anvil.harness.providers.get_provider_config",
        lambda name: ProviderCfg(
            type="cli",
            class_path="fake.Provider",
            model_name="fake-cli-model",
        ),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    proposer_stage = summary["agent_stages"][0]
    assert proposer_stage["ok"] is True
    assert proposer_stage.get("error") in (None, "")
    assert Path(proposer_stage["stderr_path"]).read_text(encoding="utf-8") == (
        "WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt"
    )
    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "- Error:" not in report_text


def test_analysis_review_runner_trust_review_normalization_binds_structured_review_refs(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustInferenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustInferenceHarnessAdapter()._payload_for_role("critic")
    normalized, payload_provenance, warnings = (
        runner._normalize_analysis_review_payload(
            payload,
            role_name="critic",
            payload_provenance_mode="payload_hash_and_refs",
            contract=runner._analysis_contract(),
        )
    )

    assert warnings == []
    assert normalized["files_reviewed"] == [
        ".github/workflows/codex-cli-release-watch.yml",
        ".github/workflows/claude-code-release-watch.yml",
    ]
    assert payload_provenance["status"] == "bound"
    assert payload_provenance["normalized_ref_count"] == 6
    assert payload_provenance["normalized_ref_field_count"] == 5
    assert payload_provenance["recommendation_review_ref_count"] == 4
    assert payload_provenance["recommendation_review_ref_field_count"] == 4
    assert payload_provenance["closure_provenance_satisfied"] is True
    assert payload_provenance["covered_recommendation_indices"] == [1, 2]
    assert payload_provenance["uncovered_recommendation_indices"] == []
    assert payload_provenance["uncovered_global_issue_ids"] == []
    assert payload_provenance["uncovered_global_topic_ids"] == []
    assert payload_provenance["normalized_refs"] == {
        "files_reviewed": [
            ".github/workflows/codex-cli-release-watch.yml",
            ".github/workflows/claude-code-release-watch.yml",
        ],
        "recommendation_reviews[1].checked_files": [
            ".github/workflows/codex-cli-release-watch.yml"
        ],
        "recommendation_reviews[1].verified_evidence_refs": [
            ".github/workflows/codex-cli-release-watch.yml"
        ],
        "recommendation_reviews[2].checked_files": [
            ".github/workflows/claude-code-release-watch.yml"
        ],
        "recommendation_reviews[2].verified_evidence_refs": [
            ".github/workflows/claude-code-release-watch.yml"
        ],
    }


def test_analysis_review_runner_trust_review_backfills_missing_closure_review_arrays_before_schema_revalidation(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustInferenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustInferenceHarnessAdapter()._payload_for_role("critic")
    payload.pop("issue_closure_reviews", None)
    payload.pop("topic_closure_reviews", None)

    normalized, payload_provenance, warnings = (
        runner._normalize_analysis_review_payload(
            payload,
            role_name="critic",
            payload_provenance_mode="payload_hash_and_refs",
            contract=runner._analysis_contract(),
        )
    )
    schema_errors = _soft_validate_schema(normalized, analysis_review_schema())

    assert warnings == []
    assert normalized["issue_closure_reviews"] == []
    assert normalized["topic_closure_reviews"] == []
    assert schema_errors == []
    assert payload_provenance["status"] == "bound"


def test_analysis_review_runner_normalizes_workspace_like_leading_slash_refs(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustInferenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )

    assert (
        runner._normalize_workspace_ref(
            "/.github/workflows/codex-cli-release-watch.yml"
        )
        == ".github/workflows/codex-cli-release-watch.yml"
    )


def test_analysis_review_runner_drops_unknown_closure_reviews_during_normalization(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustGlobalIssueClosureHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustGlobalIssueClosureHarnessAdapter()._payload_for_role("critic")
    payload["issue_closure_reviews"] = [
        {
            "issue_id": "AR-999",
            "checked_files": ["/.github/workflows/codex-cli-release-watch.yml"],
            "verified_evidence_refs": [
                "/.github/workflows/codex-cli-release-watch.yml"
            ],
            "summary": "This bogus closure review should be dropped.",
        }
    ]

    normalized, _, warnings = runner._normalize_analysis_review_payload(
        payload,
        role_name="critic",
        payload_provenance_mode="payload_hash_and_refs",
        contract=runner._analysis_contract(),
        prior_open_issue_records=[{"issue_id": "AR-001"}],
        prior_open_topic_records=[],
    )

    assert normalized["issue_closure_reviews"] == []
    assert warnings == [
        "Dropped issue_closure_reviews[1] because it referenced an unknown prior open ID: AR-999."
    ]


def test_analysis_review_runner_trust_review_marks_top_level_only_refs_as_insufficient(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustTopLevelOnlyRefReviewHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    critic_stage = next(
        stage for stage in summary["agent_stages"] if stage["role_name"] == "critic"
    )
    assert critic_stage["failure_kind"] == "semantic_validation_error"
    assert (
        critic_stage["semantic_validation_payload_provenance"]["status"]
        == "insufficient"
    )
    assert (
        critic_stage["semantic_validation_payload_provenance"]["normalized_ref_count"]
        == 2
    )
    assert (
        critic_stage["semantic_validation_payload_provenance"][
            "recommendation_review_ref_count"
        ]
        == 0
    )
    assert critic_stage["semantic_validation_payload_provenance"][
        "uncovered_recommendation_indices"
    ] == [1, 2]
    assert (
        critic_stage["semantic_validation_payload_provenance"][
            "closure_provenance_satisfied"
        ]
        is False
    )
    assert (
        "trust review payload lacks provenance-complete structured review refs for recommendation-linked closures for recommendation indices 1, 2."
        in "\n".join(critic_stage["semantic_validation_errors"])
    )


def test_analysis_review_runner_status_surfaces_uncovered_recommendation_indices(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustTopLevelOnlyRefReviewHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    contract = runner._analysis_contract()
    final_analysis_payload = (
        _TrustTopLevelOnlyRefReviewHarnessAdapter()._payload_for_role("proposer")
    )
    final_review_payload = (
        _TrustTopLevelOnlyRefReviewHarnessAdapter()._payload_for_role("critic")
    )
    _, review_provenance, warnings = runner._normalize_analysis_review_payload(
        final_review_payload,
        role_name="critic",
        payload_provenance_mode="payload_hash_and_refs",
        contract=contract,
    )

    assert warnings == []
    runner.agent_stages = [
        {
            "stage_index": 1,
            "role_name": "critic",
            "ok": True,
            "structured_output": final_review_payload,
            "semantic_validation_payload_provenance": review_provenance,
        }
    ]

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["provenance"]["status"] == "insufficient"
    assert status["provenance"]["uncovered_recommendation_indices"] == [1, 2]
    assert status["provenance"]["uncovered_global_issue_ids"] == []
    assert status["provenance"]["uncovered_global_topic_ids"] == []
    assert "final payload provenance is not fully bound" in status["downgrade_causes"]
    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": ["final payload provenance is not fully bound"],
    }


def test_analysis_review_status_publishability_blocks_open_topics_in_sorted_order(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    runner.topic_ledger = [
        {"topic_id": "TOPIC-010", "resolution_status": "open"},
        {"topic_id": "TOPIC-002", "resolution_status": "open"},
    ]
    runner.agent_stages = [
        _stage_with_provenance(
            stage_index=1,
            role_name="reviser_round_1",
            payload=final_analysis_payload,
        ),
        _stage_with_provenance(
            stage_index=2,
            role_name="auditor",
            payload=final_review_payload,
        ),
    ]

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": ["open review topics remain: TOPIC-002, TOPIC-010"],
    }


def test_analysis_review_status_publishability_blocks_carried_forward_topics_in_sorted_order(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    runner.topic_ledger = [
        {"topic_id": "TOPIC-020", "resolution_status": "carried_forward"},
        {"topic_id": "TOPIC-003", "resolution_status": "carried_forward"},
    ]
    runner.agent_stages = [
        _stage_with_provenance(
            stage_index=1,
            role_name="reviser_round_1",
            payload=final_analysis_payload,
        ),
        _stage_with_provenance(
            stage_index=2,
            role_name="auditor",
            payload=final_review_payload,
        ),
    ]

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": ["review topics are carried forward: TOPIC-003, TOPIC-020"],
    }


def test_analysis_review_status_publishability_blocks_semantic_warnings_in_record_order(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    runner.agent_stages = [
        _stage_with_provenance(
            stage_index=1,
            role_name="reviser_round_1",
            payload=final_analysis_payload,
            semantic_validation_warnings=["analysis warning"],
        ),
        _stage_with_provenance(
            stage_index=2,
            role_name="auditor",
            payload=final_review_payload,
            semantic_validation_warnings=["review warning one", "review warning two"],
        ),
    ]

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": [
            "semantic validation warnings remain: analysis warning; review warning one; review warning two"
        ],
    }


def test_analysis_review_status_publishability_ignores_advisory_section_warnings(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    advisory_strengths_warning = "strengths contains both concrete items and none_reason; prefer one or the other."
    advisory_uncertainties_warning = "uncertainties contains both concrete items and none_reason; prefer one or the other."
    runner.agent_stages = [
        _stage_with_provenance(
            stage_index=1,
            role_name="reviser_round_1",
            payload=final_analysis_payload,
            semantic_validation_warnings=[advisory_strengths_warning],
        ),
        _stage_with_provenance(
            stage_index=2,
            role_name="auditor",
            payload=final_review_payload,
            semantic_validation_warnings=[advisory_uncertainties_warning],
        ),
    ]

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["semantic_warning_count"] == 2
    assert status["semantic_warnings"] == [
        {
            "stage_index": 1,
            "role_name": "reviser_round_1",
            "warning": advisory_strengths_warning,
        },
        {
            "stage_index": 2,
            "role_name": "auditor",
            "warning": advisory_uncertainties_warning,
        },
    ]
    assert status["publishability"] == {
        "final_answer_publishable": True,
        "blocking_causes": [],
    }


def test_analysis_review_status_publishability_blocks_only_non_advisory_semantic_warnings(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    runner.agent_stages = [
        _stage_with_provenance(
            stage_index=1,
            role_name="reviser_round_1",
            payload=final_analysis_payload,
            semantic_validation_warnings=[
                "strengths contains both concrete items and none_reason; prefer one or the other.",
                "analysis warning",
            ],
        ),
        _stage_with_provenance(
            stage_index=2,
            role_name="auditor",
            payload=final_review_payload,
            semantic_validation_warnings=[
                "uncertainties contains both concrete items and none_reason; prefer one or the other.",
                "review warning",
            ],
        ),
    ]

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["semantic_warning_count"] == 4
    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": [
            "semantic validation warnings remain: analysis warning; review warning"
        ],
    }


def test_analysis_review_status_publishability_blocks_non_accepted_partial_verdicts(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": ["content verdict is not fully accepted: accepted_partial"],
    }


def test_analysis_review_status_publishability_blocks_best_effort_verdicts(tmp_path):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")

    status = runner._build_analysis_review_status(
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="best_effort_exhausted",
    )

    assert status["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": [
            "content verdict is not fully accepted: best_effort_exhausted"
        ],
    }


def test_analysis_review_status_publishability_keeps_advisory_trust_warnings_out_of_blockers(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustSemanticWarningHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted_with_warnings"
    assert summary["analysis_review_status"]["semantic_warning_count"] == 1
    assert summary["analysis_review_status"]["semantic_warnings"] == [
        {
            "stage_index": 3,
            "role_name": "reviser_round_1",
            "warning": "strengths contains both concrete items and none_reason; prefer one or the other.",
        }
    ]
    assert any(
        "semantic validation warnings remain: strengths contains both concrete items and none_reason; prefer one or the other."
        in cause
        for cause in summary["analysis_review_status"]["downgrade_causes"]
    )
    assert summary["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert summary["analysis_review_status"]["publishability"] == {
        "final_answer_publishable": False,
        "blocking_causes": [
            "final answer payload includes recommendation indices withheld from FINAL_ANSWER.*: 2"
        ],
    }


def test_analysis_review_status_marks_trust_accept_with_direct_grounding_as_final(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][1]["verdict"] = "revise"

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert status["recommendation_admissibility"][
        "final_answer_recommendation_indices"
    ] == [1]
    assert (
        status["recommendation_admissibility"]["partial_only_recommendation_indices"]
        == []
    )
    assert status["recommendation_admissibility"][
        "excluded_recommendation_indices"
    ] == [2]
    assert status["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ] == {
        "2": ["not_accepted"],
    }


def test_analysis_review_status_marks_trust_accept_with_caveat_as_partial_only(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][0]["verdict"] = "accept_with_caveat"
    final_review_payload["recommendation_reviews"][1]["verdict"] = "revise"

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert (
        status["recommendation_admissibility"]["final_answer_recommendation_indices"]
        == []
    )
    assert status["recommendation_admissibility"][
        "partial_only_recommendation_indices"
    ] == [1]
    assert status["recommendation_admissibility"][
        "excluded_recommendation_indices"
    ] == [2]
    assert status["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ] == {
        "1": ["accepted_with_caveat"],
        "2": ["not_accepted"],
    }


def test_analysis_review_status_marks_trust_inferred_acceptance_as_partial_only(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][0]["verdict"] = "revise"

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert (
        status["recommendation_admissibility"]["final_answer_recommendation_indices"]
        == []
    )
    assert status["recommendation_admissibility"][
        "partial_only_recommendation_indices"
    ] == [2]
    assert status["recommendation_admissibility"][
        "excluded_recommendation_indices"
    ] == [1]
    assert status["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ] == {
        "1": ["not_accepted"],
        "2": ["inferred_grounding"],
    }


@pytest.mark.parametrize(
    ("grounding_mode", "verdict", "expected_reasons"),
    [
        ("mixed", "accept_with_caveat", ["accepted_with_caveat"]),
        (
            "inferred",
            "accept_with_caveat",
            ["accepted_with_caveat", "inferred_grounding"],
        ),
    ],
)
def test_analysis_review_status_marks_split_trust_sibling_recommendation_as_partial_only(
    tmp_path,
    grounding_mode,
    verdict,
    expected_reasons,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_analysis_payload["recommendations"][1]["grounding_mode"] = grounding_mode
    final_analysis_payload["recommendations"][1]["verified_evidence_refs"] = []
    final_analysis_payload["recommendations"][1]["checked_files"] = []
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][0]["verdict"] = "accept"
    final_review_payload["recommendation_reviews"][1]["verdict"] = verdict

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["recommendation_admissibility"][
        "final_answer_recommendation_indices"
    ] == [1]
    assert status["recommendation_admissibility"][
        "partial_only_recommendation_indices"
    ] == [2]
    assert (
        status["recommendation_admissibility"]["excluded_recommendation_indices"] == []
    )
    assert status["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ] == {
        "2": expected_reasons,
    }


def test_analysis_review_status_marks_bounded_accepted_recommendations_as_final_admissible(
    tmp_path,
):
    runner = _make_analysis_status_runner(
        tmp_path,
        strategy_kind="analysis_review_bounded_v1",
    )
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1, 2],
        "partial_only_recommendation_indices": [],
        "excluded_recommendation_indices": [],
        "reasons_by_recommendation_index": {},
    }


def test_analysis_review_status_marks_bounded_accept_with_caveat_as_final_admissible(
    tmp_path,
):
    runner = _make_analysis_status_runner(
        tmp_path,
        strategy_kind="analysis_review_bounded_v1",
    )
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][0]["verdict"] = "accept_with_caveat"

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_with_warnings",
    )

    assert status["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1, 2],
        "partial_only_recommendation_indices": [],
        "excluded_recommendation_indices": [],
        "reasons_by_recommendation_index": {},
    }


def test_analysis_review_status_marks_bounded_non_accepted_recommendations_as_excluded(
    tmp_path,
):
    runner = _make_analysis_status_runner(
        tmp_path,
        strategy_kind="analysis_review_bounded_v1",
    )
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][1]["verdict"] = "revise"

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert status["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1],
        "partial_only_recommendation_indices": [],
        "excluded_recommendation_indices": [2],
        "reasons_by_recommendation_index": {"2": ["not_accepted"]},
    }


def test_analysis_review_status_excludes_non_accepted_recommendations(tmp_path):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][0]["verdict"] = "revise"
    final_review_payload["recommendation_reviews"][1]["verdict"] = "reject"

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="best_effort_exhausted",
    )

    assert (
        status["recommendation_admissibility"]["final_answer_recommendation_indices"]
        == []
    )
    assert (
        status["recommendation_admissibility"]["partial_only_recommendation_indices"]
        == []
    )
    assert status["recommendation_admissibility"][
        "excluded_recommendation_indices"
    ] == [1, 2]
    assert status["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ] == {
        "1": ["not_accepted"],
        "2": ["not_accepted"],
    }


def test_analysis_review_status_excludes_topic_blocked_recommendations_from_final_admissibility(
    tmp_path,
):
    runner = _make_analysis_status_runner(tmp_path)
    adapter = _TrustInferenceHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    final_review_payload["recommendation_reviews"][1]["verdict"] = "revise"
    runner.topic_ledger = [
        {
            "topic_id": "TOPIC-001",
            "resolution_status": "carried_forward",
            "recommendation_index": 1,
        }
    ]

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert (
        status["recommendation_admissibility"]["final_answer_recommendation_indices"]
        == []
    )
    assert (
        status["recommendation_admissibility"]["partial_only_recommendation_indices"]
        == []
    )
    assert status["recommendation_admissibility"][
        "excluded_recommendation_indices"
    ] == [1, 2]
    assert status["recommendation_admissibility"][
        "reasons_by_recommendation_index"
    ] == {
        "1": ["topic_blocked"],
        "2": ["not_accepted"],
    }


def test_analysis_review_status_marks_bounded_topic_blocked_recommendations_as_excluded(
    tmp_path,
):
    runner = _make_analysis_status_runner(
        tmp_path,
        strategy_kind="analysis_review_bounded_v1",
    )
    adapter = _AcceptingHarnessAdapter()
    final_analysis_payload = adapter._base_analysis(revised=True)
    final_review_payload = adapter._payload_for_role("auditor")
    runner.topic_ledger = [
        {
            "topic_id": "TOPIC-001",
            "resolution_status": "carried_forward",
            "recommendation_index": 1,
        }
    ]

    status = _build_recommendation_admissibility_status(
        runner,
        final_analysis_payload=final_analysis_payload,
        final_review_payload=final_review_payload,
        content_verdict="accepted_partial",
    )

    assert status["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [2],
        "partial_only_recommendation_indices": [],
        "excluded_recommendation_indices": [1],
        "reasons_by_recommendation_index": {"1": ["topic_blocked"]},
    }


def test_analysis_review_runner_trust_review_marks_global_topic_closure_as_uncovered_debt(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustGlobalTopicClosureHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustGlobalTopicClosureHarnessAdapter()._payload_for_role("critic")
    _, payload_provenance, warnings = runner._normalize_analysis_review_payload(
        payload,
        role_name="critic",
        payload_provenance_mode="payload_hash_and_refs",
        contract=runner._analysis_contract(),
    )

    assert warnings == []
    assert payload_provenance["status"] == "insufficient"
    assert payload_provenance["covered_recommendation_indices"] == [1, 2]
    assert payload_provenance["uncovered_recommendation_indices"] == []
    assert payload_provenance["uncovered_global_issue_ids"] == []
    assert payload_provenance["uncovered_global_topic_ids"] == ["TOPIC-001"]
    assert payload_provenance["closure_provenance_satisfied"] is False


def test_analysis_review_runner_trust_review_marks_global_issue_closure_as_uncovered_debt(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustGlobalIssueClosureHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustGlobalIssueClosureHarnessAdapter()._payload_for_role("critic")
    _, payload_provenance, warnings = runner._normalize_analysis_review_payload(
        payload,
        role_name="critic",
        payload_provenance_mode="payload_hash_and_refs",
        contract=runner._analysis_contract(),
    )

    assert warnings == []
    assert payload_provenance["status"] == "insufficient"
    assert payload_provenance["covered_recommendation_indices"] == [1, 2]
    assert payload_provenance["uncovered_recommendation_indices"] == []
    assert payload_provenance["uncovered_global_issue_ids"] == ["AR-001"]
    assert payload_provenance["uncovered_global_topic_ids"] == []
    assert payload_provenance["closure_provenance_satisfied"] is False


def test_analysis_review_runner_trust_review_marks_scoped_global_topic_closure_as_complete(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustGlobalTopicClosureHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustGlobalTopicClosureHarnessAdapter()._payload_for_role("critic")
    payload["topic_closure_reviews"] = [
        {
            "topic_id": "TOPIC-001",
            "checked_files": [".github/workflows/claude-code-release-watch.yml"],
            "verified_evidence_refs": [
                ".github/workflows/claude-code-release-watch.yml"
            ],
            "summary": "The carried-forward global topic was re-checked directly.",
        }
    ]
    _, payload_provenance, warnings = runner._normalize_analysis_review_payload(
        payload,
        role_name="critic",
        payload_provenance_mode="payload_hash_and_refs",
        contract=runner._analysis_contract(),
    )

    assert warnings == []
    assert payload_provenance["status"] == "bound"
    assert payload_provenance["closure_provenance_satisfied"] is True
    assert payload_provenance["closure_complete_topic_ids"] == ["TOPIC-001"]
    assert payload_provenance["uncovered_global_topic_ids"] == []
    assert payload_provenance["topic_closure_review_ref_count"] == 2
    assert payload_provenance["closure_proof_by_id"]["TOPIC-001"] == {
        "proof_path": "scoped",
        "classification_status": "carried_forward",
        "checked_files": [".github/workflows/claude-code-release-watch.yml"],
        "verified_evidence_refs": [".github/workflows/claude-code-release-watch.yml"],
        "proof_strength": "review_attested",
    }


def test_analysis_review_runner_trust_review_marks_scoped_global_issue_closure_as_complete(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustGlobalIssueClosureHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _TrustGlobalIssueClosureHarnessAdapter()._payload_for_role("critic")
    payload["issue_closure_reviews"] = [
        {
            "issue_id": "AR-001",
            "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
            "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
            "summary": "The carried-forward global issue was re-checked directly.",
        }
    ]
    _, payload_provenance, warnings = runner._normalize_analysis_review_payload(
        payload,
        role_name="critic",
        payload_provenance_mode="payload_hash_and_refs",
        contract=runner._analysis_contract(),
    )

    assert warnings == []
    assert payload_provenance["status"] == "bound"
    assert payload_provenance["closure_provenance_satisfied"] is True
    assert payload_provenance["closure_complete_issue_ids"] == ["AR-001"]
    assert payload_provenance["uncovered_global_issue_ids"] == []
    assert payload_provenance["issue_closure_review_ref_count"] == 2
    assert payload_provenance["closure_proof_by_id"]["AR-001"] == {
        "proof_path": "scoped",
        "classification_status": "carried_forward",
        "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
        "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
        "proof_strength": "review_attested",
    }


def test_analysis_review_runner_trust_review_keeps_proven_global_issue_bound_end_to_end(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustGlobalIssueLifecycleHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    provenance = summary["analysis_review_status"]["provenance"]
    assert provenance["status"] == "bound"
    assert provenance["closure_complete_issue_ids"] == ["AR-001"]
    assert provenance["uncovered_global_issue_ids"] == []
    assert provenance["issue_closure_review_ref_count"] == 2
    assert provenance["closure_proof_by_id"]["AR-001"] == {
        "proof_path": "scoped",
        "classification_status": "carried_forward",
        "checked_files": [".github/workflows/codex-cli-release-watch.yml"],
        "verified_evidence_refs": [".github/workflows/codex-cli-release-watch.yml"],
        "proof_strength": "review_attested",
    }

    issue_ledger_by_id = {item["issue_id"]: item for item in summary["issue_ledger"]}
    assert issue_ledger_by_id["AR-001"]["resolution_status"] == "carried_forward"

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "## Review Provenance" in report_text
    assert "- Uncovered recommendation indices: none" in report_text
    assert "- Issue closure review refs: `2`" in report_text
    assert "`AR-001`" in report_text
    assert "- Closure proof incomplete:" not in report_text

    drafts = extract_drafts_from_summary(summary)
    auditor_draft = next(
        draft for draft in drafts if draft["metadata"].get("reviewer_role") == "auditor"
    )
    assert auditor_draft["issue_counts"]["provenance_incomplete"] == 0
    assert auditor_draft["issue_counts"]["uncovered_closure_count"] == 0


def test_analysis_review_runner_trust_mode_rejects_concrete_verdicts_without_per_verdict_refs(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustVerdictWithoutRefsHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    critic_stage = next(
        stage for stage in summary["agent_stages"] if stage["role_name"] == "critic"
    )
    assert critic_stage["failure_kind"] == "semantic_validation_error"
    assert (
        critic_stage["semantic_validation_payload_provenance"]["status"]
        == "insufficient"
    )
    assert critic_stage["semantic_validation_payload_provenance"][
        "uncovered_recommendation_indices"
    ] == [1, 2]
    assert (
        "recommendation_reviews[1] must include checked_files or verified_evidence_refs for trust-mode verdict provenance."
        in critic_stage["semantic_validation_errors"]
    )


def test_analysis_review_runner_trust_mode_downgrades_when_semantic_warnings_remain(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustSemanticWarningHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted_with_warnings"
    assert summary["analysis_review_status"]["mode"] == "trust"
    assert summary["analysis_review_status"]["semantic_warning_count"] >= 1
    assert any(
        "semantic validation warnings remain:" in cause
        for cause in summary["analysis_review_status"]["downgrade_causes"]
    )


def test_analysis_review_runner_can_emit_partial_answer_and_issue_ledger(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _PartialAcceptanceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted_partial"
    assert summary["verdicts"]["content_verdict"] == "accepted_partial"
    assert summary["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert Path(summary["artifacts"]["partial_answer_json"]).exists()
    assert Path(summary["artifacts"]["partial_answer_md"]).exists()
    assert Path(summary["artifacts"]["issue_ledger_json"]).exists()

    partial_answer = summary["partial_answer"]
    assert len(partial_answer["recommendations"]) == 2
    assert partial_answer["included_recommendation_indices"] == [1, 2]
    assert partial_answer["excluded_recommendation_indices"] == [3]
    assert summary["recommendation_reviews"][2]["verdict"] == "revise"
    bounded_review_summary = summary["bounded_review_summary"]
    assert bounded_review_summary["recommendation_count"] == 3
    assert bounded_review_summary["recommendations_with_review_surface"] == 3
    assert bounded_review_summary["scope_escape_count"] == 0
    assert len(bounded_review_summary["review_stages"]) == 2

    issue_ledger = summary["issue_ledger"]
    assert issue_ledger[0]["issue_id"] == "AR-001"
    assert issue_ledger[0]["resolution_status"] == "carried_forward"
    assert issue_ledger[0]["blocking_class"] == "actionability"
    assert issue_ledger[0]["recommendation_index"] == 3


def test_analysis_review_runner_excludes_topic_blocked_recommendations_from_partial_answer(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _PartialAcceptanceWithTopicDebtHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted_partial"
    assert summary["artifacts"]["final_artifact_kind"] == "partial_answer"
    assert summary["analysis_review_status"]["carried_forward_topic_ids"] == [
        "TOPIC-001"
    ]
    partial_answer = summary["partial_answer"]
    assert partial_answer["included_recommendation_indices"] == [1, 4]
    assert partial_answer["excluded_recommendation_indices"] == [2, 3]
    assert [item["title"] for item in partial_answer["recommendations"]] == [
        "Add concurrency controls",
        "Document alert routing ownership",
    ]
    assert [
        item["recommendation_index"]
        for item in partial_answer["recommendation_reviews"]
    ] == [1, 4]


def test_analysis_review_runner_blocks_partial_accept_when_unresolved_topic_is_global(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        min_recommendations=2,
        review_max_loops=1,
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _PartialAcceptanceWithGlobalTopicDebtHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "best_effort_exhausted"
    assert summary["verdicts"]["content_verdict"] == "best_effort_exhausted"
    assert summary["artifacts"]["final_artifact_kind"] != "partial_answer"
    assert "partial_answer" not in summary
    assert summary["analysis_review_status"]["carried_forward_topic_ids"] == [
        "TOPIC-001"
    ]


def test_analysis_review_runner_partial_accept_allows_localized_medium_non_correctness_when_enabled(
    tmp_path,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)
    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _PartialAcceptanceLocalizedAcceptedIssueHarnessAdapter(
        blocking_class="actionability"
    )._payload_for_role("auditor")

    assert runner._analysis_can_partially_accept(payload) is True


def test_analysis_review_runner_partial_accept_rejects_localized_medium_non_correctness_when_disabled(
    tmp_path,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)
    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    runner.analysis_review_contract = replace(
        runner._analysis_contract(),
        partial_acceptance=replace(
            runner._analysis_contract().partial_acceptance,
            allow_localized_medium_non_correctness_issues=False,
        ),
    )
    payload = _PartialAcceptanceLocalizedAcceptedIssueHarnessAdapter(
        blocking_class="actionability"
    )._payload_for_role("auditor")

    assert runner._analysis_can_partially_accept(payload) is False


def test_analysis_review_runner_partial_accept_rejects_localized_medium_correctness_when_forbidden(
    tmp_path,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)
    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _PartialAcceptanceLocalizedAcceptedIssueHarnessAdapter(
        blocking_class="correctness"
    )._payload_for_role("auditor")

    assert runner._analysis_can_partially_accept(payload) is False


def test_analysis_review_runner_partial_accept_allows_localized_medium_correctness_when_policy_allows(
    tmp_path,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)
    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    runner.analysis_review_contract = replace(
        runner._analysis_contract(),
        partial_acceptance=replace(
            runner._analysis_contract().partial_acceptance,
            forbid_correctness_blockers_on_accepted_recommendations=False,
        ),
    )
    payload = _PartialAcceptanceLocalizedAcceptedIssueHarnessAdapter(
        blocking_class="correctness"
    )._payload_for_role("auditor")

    assert runner._analysis_can_partially_accept(payload) is True


def test_analysis_review_runner_preserves_topic_lifecycle_in_summary_report_and_deliverable(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TopicLifecycleHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    assert summary["issue_ledger"] == []
    assert summary["topic_ledger"] == [
        {
            "topic_id": "TOPIC-001",
            "title": "Recommendation 2 needs a concrete fallback classification.",
            "severity": "medium",
            "evidence": "The workflow recommendation names the operator path but leaves the fallback state implicit.",
            "recommendation_index": 2,
            "introduced_by": "critic",
            "introduced_in_stage_index": 2,
            "resolution_status": "addressed",
            "resolution_note": "addressed | Added the fallback classification note to recommendation 2.",
            "resolved_in_stage_index": 4,
        }
    ]
    assert summary["analysis_review_status"]["topic_ledger_count"] == 1
    assert summary["analysis_review_status"]["open_topic_ids"] == []
    assert summary["analysis_review_status"]["resolved_topic_ids"] == ["TOPIC-001"]
    assert summary["analysis_review_status"]["carried_forward_topic_ids"] == []
    assert summary["analysis_review_status"]["waived_topic_ids"] == []
    assert summary["bounded_review_summary"]["review_stages"] == [
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
    ]

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    final_answer_text = Path(summary["artifacts"]["final_answer_md"]).read_text(
        encoding="utf-8"
    )
    assert "## Topic Lifecycle" in report_text
    assert "- Topic ledger entries: `1`" in report_text
    assert "- Resolved topics: `1` (`TOPIC-001`)" in report_text
    assert (
        "| Topic ID | Title | Severity | Introduced By | Status | Recommendation | Resolution Note |"
        in report_text
    )
    assert (
        "| `TOPIC-001` | Recommendation 2 needs a concrete fallback classification. | `medium` | `critic` | `addressed` | `2` | addressed \\| Added the fallback classification note to recommendation 2. |"
        in report_text
    )
    assert (
        "Topic lifecycle: new `1`, resolved `0`, carried forward `0`, waived `0`, open `1`"
        in report_text
    )
    assert (
        "Topic lifecycle: new `0`, resolved `1`, carried forward `0`, waived `0`, open `0`"
        in report_text
    )

    assert "## Topic Lifecycle" in final_answer_text
    assert (
        "- `TOPIC-001` `addressed` via `critic`: Recommendation 2 needs a concrete fallback classification. — addressed | Added the fallback classification note to recommendation 2."
        in final_answer_text
    )
    assert "- Topic ledger count: `1`" in final_answer_text
    assert "missing_topics" not in final_answer_text


def test_analysis_review_runner_preserves_disagreed_topic_lifecycle_in_rollups(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TopicDisagreeHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    assert summary["topic_ledger"][0]["resolution_status"] == "disagree"
    assert summary["analysis_review_status"]["disagreed_topic_ids"] == ["TOPIC-001"]
    assert summary["analysis_review_status"]["waived_topic_ids"] == []

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    final_answer_text = Path(summary["artifacts"]["final_answer_md"]).read_text(
        encoding="utf-8"
    )
    assert "- Disagreed topic IDs: `TOPIC-001`" in report_text
    assert "- Disagreed topics: `1` (`TOPIC-001`)" in report_text
    assert (
        "| `TOPIC-001` | Recommendation 2 needs a concrete fallback classification. | `medium` | `critic` | `disagree` | `2` | disagree \\| Kept the original recommendation because the requested fallback classification is not directly supported by the inspected workflow evidence. \\| Operators may still want an explicit fallback label, but the evidence does not justify inventing one. |"
        in report_text
    )
    assert "- Disagreed topic IDs: `TOPIC-001`" in final_answer_text
    assert (
        "- `TOPIC-001` `disagree` via `critic`: Recommendation 2 needs a concrete fallback classification. — disagree | Kept the original recommendation because the requested fallback classification is not directly supported by the inspected workflow evidence. | Operators may still want an explicit fallback label, but the evidence does not justify inventing one."
        in final_answer_text
    )


def test_analysis_review_runner_preserves_topic_introduction_source_when_carried_forward(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TopicCarryForwardHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["topic_ledger"] == [
        {
            "topic_id": "TOPIC-001",
            "title": "Recommendation 2 needs a concrete fallback classification.",
            "severity": "medium",
            "evidence": "The workflow recommendation names the operator path but leaves the fallback state implicit.",
            "recommendation_index": 2,
            "introduced_by": "critic",
            "introduced_in_stage_index": 2,
            "resolution_status": "carried_forward",
            "resolution_note": "not_addressed | The recommendation text improved, but the fallback classification is still too implicit. | Operators still need a concrete fallback label.",
            "resolved_in_stage_index": None,
        }
    ]
    assert summary["analysis_review_status"]["open_topic_ids"] == []
    assert summary["analysis_review_status"]["carried_forward_topic_ids"] == [
        "TOPIC-001"
    ]
    assert summary["analysis_review_status"]["recommendation_admissibility"] == {
        "final_answer_recommendation_indices": [1],
        "partial_only_recommendation_indices": [],
        "excluded_recommendation_indices": [2],
        "reasons_by_recommendation_index": {"2": ["topic_blocked"]},
    }
    assert "final_answer_md" not in summary["artifacts"]
    assert "partial_answer_md" not in summary["artifacts"]

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    best_draft_text = Path(summary["artifacts"]["best_draft_md"]).read_text(
        encoding="utf-8"
    )
    assert (
        "| `TOPIC-001` | Recommendation 2 needs a concrete fallback classification. | `medium` | `critic` | `carried_forward` | `2` | not_addressed \\| The recommendation text improved, but the fallback classification is still too implicit. \\| Operators still need a concrete fallback label. |"
        in report_text
    )
    assert "- Recommendation indices withheld from `FINAL_ANSWER.*`: `2`" in report_text
    assert (
        "- `TOPIC-001` `carried_forward` via `critic`: Recommendation 2 needs a concrete fallback classification. — not_addressed | The recommendation text improved, but the fallback classification is still too implicit. | Operators still need a concrete fallback label."
        in best_draft_text
    )
    assert "- Carried-forward topic IDs: `TOPIC-001`" in best_draft_text

    runner._ingest_review_payload(
        {
            "topics": [
                {
                    "topic_id": "TOPIC-001",
                    "severity": "medium",
                    "title": "Recommendation 2 needs a concrete fallback classification.",
                    "evidence": "The updated recommendation still hints at the fallback behavior without naming the concrete classification.",
                    "repair_hint": "Name the fallback classification directly in recommendation 2.",
                    "recommendation_index": 2,
                }
            ],
            "resolved_topic_ids": [],
            "carried_forward_topic_ids": [],
            "waived_topic_ids": [],
        },
        round_index=2,
        role_name="auditor",
        reviser_output=None,
    )
    assert runner.topic_ledger[0]["introduced_by"] == "critic"
    assert runner.topic_ledger[0]["introduced_in_stage_index"] == 2


def test_analysis_review_runner_rejects_reuse_of_resolved_topic_id(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TopicLifecycleHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    runner.run()

    with pytest.raises(
        ValueError,
        match="reused historical topic ID TOPIC-001 even though it is not currently open",
    ):
        runner._ingest_review_payload(
            {
                "files_reviewed": [".github/workflows/claude-code-release-watch.yml"],
                "topics": [
                    {
                        "topic_id": "TOPIC-001",
                        "severity": "medium",
                        "title": "Recommendation 2 needs a concrete fallback classification.",
                        "evidence": "A later auditor tried to reopen the already resolved topic.",
                        "repair_hint": "Allocate a new topic ID instead of mutating the historical row.",
                        "recommendation_index": 2,
                    }
                ],
                "resolved_topic_ids": [],
                "carried_forward_topic_ids": [],
                "waived_topic_ids": [],
            },
            round_index=2,
            role_name="auditor",
            reviser_output=None,
        )

    assert runner.topic_ledger[0]["resolution_status"] == "addressed"
    assert runner.topic_ledger[0]["resolved_in_stage_index"] == 4


def test_analysis_review_runner_persists_addressed_topic_recommendation_index_from_reviser(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TopicResolutionRecommendationHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["topic_ledger"][0]["introduced_by"] == "critic"
    assert summary["topic_ledger"][0]["recommendation_index"] == 2

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert (
        "| `TOPIC-001` | Recommendation 2 needs a concrete fallback classification. | `medium` | `critic` | `addressed` | `2` | addressed \\| Added the fallback classification note to recommendation 2. |"
        in report_text
    )


def test_analysis_review_runner_trust_relinked_topic_closes_on_recommendation_proof(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        strategy_kind="analysis_review_trust_v1",
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _TrustTopicResolutionRecommendationHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    provenance = summary["analysis_review_status"]["provenance"]
    assert provenance["status"] == "bound"
    assert provenance["uncovered_global_topic_ids"] == []
    assert provenance["closure_proof_by_id"]["TOPIC-001"] == {
        "proof_path": "recommendation",
        "classification_status": "resolved",
        "checked_files": [".github/workflows/claude-code-release-watch.yml"],
        "verified_evidence_refs": [".github/workflows/claude-code-release-watch.yml"],
        "proof_strength": "recommendation_evidence",
    }

    assert summary["topic_ledger"][0]["recommendation_index"] == 2


def test_analysis_review_runner_normalizes_legacy_missing_topics_into_topics(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _LegacyMissingTopicsHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    payload = _LegacyMissingTopicsHarnessAdapter()._payload_for_role("critic")
    normalized, _, warnings = runner._normalize_analysis_review_payload(
        payload,
        role_name="critic",
        payload_provenance_mode="none",
        contract=runner._analysis_contract(),
    )

    assert (
        "Normalized legacy missing_topics into topics with stable topic IDs."
        in warnings
    )
    assert "missing_topics" not in normalized
    assert normalized["resolved_topic_ids"] == []
    assert normalized["carried_forward_topic_ids"] == []
    assert normalized["waived_topic_ids"] == []
    assert len(normalized["topics"]) == 1
    assert normalized["topics"][0]["topic_id"].startswith("AT-")
    assert (
        normalized["topics"][0]["title"]
        == "Recommendation 2 still needs a concrete fallback classification."
    )


def test_analysis_review_runner_allows_legacy_missing_topics_full_run_after_normalization(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _LegacyMissingTopicsFullRunHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    critic_stage = next(
        stage for stage in summary["agent_stages"] if stage["role_name"] == "critic"
    )
    assert critic_stage["ok"] is True
    assert critic_stage.get("failure_kind") is None
    assert critic_stage.get("schema_validation_errors") in (None, [])
    assert critic_stage["semantic_validation_warnings"] == [
        "Normalized legacy missing_topics into topics with stable topic IDs."
    ]

    semantic_payload = load_structured_file(
        Path(critic_stage["semantic_validation_path"])
    )
    assert semantic_payload["ok"] is True
    assert semantic_payload["skipped"] is False
    assert semantic_payload["errors"] == []
    assert semantic_payload["warnings"] == [
        "Normalized legacy missing_topics into topics with stable topic IDs."
    ]

    run_envelope = load_structured_file(
        Path(runner.artifacts_dir) / "02_critic" / "run.envelope.json"
    )
    assert run_envelope["ok"] is True
    assert run_envelope.get("failure_kind") is None
    assert run_envelope.get("schema_validation_errors") in (None, [])


def test_analysis_review_runner_reports_non_zero_scope_escapes(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _ScopeEscapeHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    bounded_review_summary = summary["bounded_review_summary"]
    assert bounded_review_summary["scope_escape_count"] == 1
    assert bounded_review_summary["scope_escapes"] == [
        {
            "role_name": "critic",
            "round_index": 0,
            "path": "anvil/harness/state.py",
            "reason": "The cited evidence conflicted with the adjacent state transition logic.",
        }
    ]
    assert bounded_review_summary["review_stages"][0]["role_name"] == "critic"
    assert bounded_review_summary["review_stages"][0]["scope_escape_count"] == 1
    assert bounded_review_summary["review_stages"][1]["role_name"] == "auditor"
    assert bounded_review_summary["review_stages"][1]["scope_escape_count"] == 0

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "## Review Scope" in report_text
    assert "## Bounded Review" not in report_text
    assert "- Total scope escapes: `1`" in report_text
    assert "### Scope Escapes" in report_text
    assert (
        "- `critic` round `0` — `anvil/harness/state.py`: "
        "The cited evidence conflicted with the adjacent state transition logic."
    ) in report_text


def test_analysis_review_runner_rejects_bounded_secondary_seam_overflow_without_silent_normalization(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _SecondarySeamOverflowHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    proposer_stage = summary["agent_stages"][0]
    assert (
        len(proposer_stage["structured_output"]["secondary_seams_considered"]) == 2 + 1
    )
    assert any(
        error
        == "secondary_seams_considered[3] requires scope_escapes coverage for every declared third-seam path: docs/project_management/next/codex-cli-parity/C1-spec.md"
        for error in proposer_stage["semantic_validation_errors"]
    )
    semantic_payload = load_structured_file(
        Path(proposer_stage["semantic_validation_path"])
    )
    assert semantic_payload["ok"] is False
    assert (
        "secondary_seams_considered[3] requires scope_escapes coverage for every declared third-seam path: docs/project_management/next/codex-cli-parity/C1-spec.md"
        in semantic_payload["errors"]
    )


def test_analysis_review_runner_accepts_bounded_third_secondary_seam_with_analysis_scope_escapes(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _ScopedSecondarySeamOverflowHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    _assert_canonical_analysis_review_status(
        summary,
        expected_primary_seam_id=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        expected_secondary_seam_ids=[
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
            _OVERFLOW_OWNER_CANONICAL_SEAM_ID,
            _OVERFLOW_SPEC_CANONICAL_SEAM_ID,
        ],
        expected_binding_seam_ids=[
            _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
        ],
        expected_scope_escape_paths=[
            "docs/project_management/next/codex-cli-parity/C1-spec.md"
        ],
    )
    bounded_review_summary = summary["bounded_review_summary"]
    assert bounded_review_summary["scope_escape_count"] == 1
    assert bounded_review_summary["review_stages"][0]["role_name"] == "critic"
    assert bounded_review_summary["review_stages"][1]["role_name"] == "auditor"
    assert bounded_review_summary["scope_escapes"][0]["role_name"] == "reviser_round_1"
    assert (
        bounded_review_summary["scope_escapes"][0]["path"]
        == "docs/project_management/next/codex-cli-parity/C1-spec.md"
    )


def test_analysis_review_runner_uses_final_reviser_scope_escapes_as_canonical_source(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _ReviserOnlyScopedOverflowHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "accepted"
    _assert_canonical_analysis_review_status(
        summary,
        expected_primary_seam_id=_SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
        expected_secondary_seam_ids=[
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
            _OVERFLOW_OWNER_CANONICAL_SEAM_ID,
            _OVERFLOW_SPEC_CANONICAL_SEAM_ID,
        ],
        expected_binding_seam_ids=[
            _SIMPLE_PRIMARY_CANONICAL_SEAM_ID,
            _SECONDARY_RELEASE_WATCH_CANONICAL_SEAM_ID,
        ],
        expected_scope_escape_paths=[
            "docs/project_management/next/codex-cli-parity/C1-spec.md"
        ],
    )
    proposer_payload = summary["agent_stages"][0]["structured_output"]
    assert proposer_payload["scope_escapes"] == []
    assert len(proposer_payload["secondary_seams_considered"]) == 1
    reviser_payload = next(
        stage["structured_output"]
        for stage in summary["agent_stages"]
        if stage["role_name"] == "reviser_round_1"
    )
    assert reviser_payload["scope_escapes"] == [
        {
            "path": "docs/project_management/next/codex-cli-parity/C1-spec.md",
            "reason": "The revision needs exactly one third secondary seam to compare the governing parity spec against the widened bounded seam.",
        }
    ]
    final_answer = json.loads(
        Path(summary["artifacts"]["final_answer_json"]).read_text(encoding="utf-8")
    )
    assert final_answer["scope_escapes"] == reviser_payload["scope_escapes"]
    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert (
        "- `reviser` analysis stage `1` — `docs/project_management/next/codex-cli-parity/C1-spec.md`: "
        "The revision needs exactly one third secondary seam to compare the governing parity spec against the widened bounded seam."
    ) in report_text


def test_analysis_review_runner_surfaces_semantic_validation_failures(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _InvalidSemanticHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert "Semantic validation failed" in summary["final_summary"]
    proposer_stage = summary["agent_stages"][0]
    assert proposer_stage["ok"] is False
    assert any(
        "strengths must contain at least one concrete item or a non-empty none_reason"
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )
    assert any(
        "uncertainties must contain at least one concrete item or a non-empty none_reason"
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )
    assert Path(proposer_stage["semantic_validation_path"]).exists()


def test_analysis_review_runner_prefers_semantic_failure_summary_over_provider_noise(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _InvalidSemanticWithProviderNoiseHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert "Semantic validation failed" in summary["final_summary"]
    assert "noisy provider warning" not in summary["final_summary"]


def test_analysis_review_runner_reports_schema_validation_failures_cleanly(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _InvalidSchemaHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert "Schema validation failed" in summary["final_summary"]


def test_analysis_review_runner_rejects_hallucinated_evidence_refs(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _HallucinatedEvidenceHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert "Semantic validation failed" in summary["final_summary"]
    proposer_stage = summary["agent_stages"][0]
    assert proposer_stage["ok"] is False
    assert any(
        "recommendations[2].evidence must be a subset of files_reviewed: does/not/exist.py"
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )
    assert any(
        "recommendations[2].evidence contains path(s) not present in the workspace snapshot: does/not/exist.py"
        in error
        for error in proposer_stage["semantic_validation_errors"]
    )


def test_analysis_review_runner_short_circuits_provider_failures_and_marks_review_unexercised(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _QuotaFailingReviewHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert "Review loop not exercised." in summary["final_summary"]
    assert summary["run_details"]["final_analysis"]["status"] == "done"
    assert summary["bounded_review_summary"]["recommendation_count"] == 2
    assert summary["bounded_review_summary"]["recommendations_with_review_surface"] == 2
    assert summary["bounded_review_summary"]["review_stages"] == []
    assert summary["analysis_review_coverage"]["review_loop_exercised"] is False
    assert summary["analysis_review_coverage"]["review_stages_attempted"] == 1
    assert summary["analysis_review_coverage"]["review_stages_completed"] == 0

    critic_stage = summary["agent_stages"][1]
    assert critic_stage["failure_kind"] == "quota_exhausted"
    assert "$.verdict: missing required field" not in critic_stage["error"]
    semantic_payload = load_structured_file(
        Path(critic_stage["semantic_validation_path"])
    )
    assert semantic_payload["skipped"] is True
    assert semantic_payload["skipped_reason"] == "provider_failure:quota_exhausted"

    draft = summary["drafts"][0]
    assert draft["review_state"] == "not_evaluated"
    assert "medium_or_higher" not in draft["issue_counts"]
    assert "review_failure_summary" in draft["metadata"]

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "Review loop exercised: `False`" in report_text
    assert "Review issue counts: `not evaluated`" in report_text
    assert "Review surfaces declared: `2` / `2` recommendations" in report_text
    best_draft_text = Path(summary["artifacts"]["best_draft_md"]).read_text(
        encoding="utf-8"
    )
    assert "not evaluated by a successful critic/auditor stage" in best_draft_text


def test_analysis_review_runner_preserves_proposer_payload_when_reviser_fails(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _ReviserFailingHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert summary["run_details"]["stage"] == "reviser round 1"
    assert summary["run_details"]["review_loop_exercised"] is True
    assert summary["run_details"]["final_analysis"]["status"] == "done"
    assert summary["run_details"]["final_analysis"]["recommendations"][2]["title"] == (
        "Add release failure categorization"
    )
    assert summary["run_details"]["analysis_review_contract"]["contract_version"] == (
        "analysis_review_v1_contract_v9"
    )
    assert summary["bounded_review_summary"]["recommendation_count"] == 3
    assert summary["bounded_review_summary"]["recommendations_with_review_surface"] == 3
    assert len(summary["bounded_review_summary"]["review_stages"]) == 1
    assert (
        summary["bounded_review_summary"]["review_stages"][0]["role_name"] == "critic"
    )


def test_analysis_review_runner_preserves_reviser_payload_when_auditor_fails(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _AuditorFailingHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    assert summary["verdict"] == "harness_error"
    assert summary["run_details"]["stage"] == "auditor"
    assert summary["run_details"]["review_loop_exercised"] is True
    assert summary["run_details"]["final_analysis"]["status"] == "revised"
    assert (
        summary["run_details"]["final_analysis"]["issue_resolution_map"][0]["issue_id"]
        == "AR-001"
    )
    assert summary["run_details"]["issue_ledger"][0]["issue_id"] == "AR-001"
    assert summary["bounded_review_summary"]["recommendation_count"] == 3
    assert summary["bounded_review_summary"]["recommendations_with_review_surface"] == 3
    assert len(summary["bounded_review_summary"]["review_stages"]) == 1
    assert (
        summary["bounded_review_summary"]["review_stages"][0]["role_name"] == "critic"
    )


def test_analysis_review_runner_preserves_late_auditor_issue_attribution_in_ledger_and_report(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(
        tmp_path,
        min_recommendations=2,
        review_max_loops=1,
    )

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _LateAuditorIssueHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    summary = runner.run()

    issue_ledger_by_id = {item["issue_id"]: item for item in summary["issue_ledger"]}
    assert set(issue_ledger_by_id) == {"AR-001", "AR-002"}
    assert issue_ledger_by_id["AR-001"]["resolution_status"] == "carried_forward"
    assert issue_ledger_by_id["AR-002"]["first_seen_round"] == 1
    assert issue_ledger_by_id["AR-002"]["resolution_status"] == "open"
    assert issue_ledger_by_id["AR-002"]["blocking_class"] == "correctness"
    assert issue_ledger_by_id["AR-002"]["recommendation_index"] == 2
    assert issue_ledger_by_id["AR-002"]["why_not_raised_earlier"] == (
        "The missing evidence was introduced by the revision that rewrote recommendation 2."
    )

    auditor_stage = summary["bounded_review_summary"]["review_stages"][1]
    assert auditor_stage["role_name"] == "auditor"
    assert auditor_stage["new_medium_or_higher_issue_count"] == 1

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "## Issue Ledger" in report_text
    assert "### AR-002 — medium — correctness — open" in report_text
    assert (
        "- Why not raised earlier: "
        "The missing evidence was introduced by the revision that rewrote recommendation 2."
    ) in report_text


def test_bounded_review_summary_falls_back_to_latest_successful_stage_when_final_analysis_missing(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _AcceptingHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    runner._analysis_contract()
    adapter = _PartialAcceptanceHarnessAdapter()
    runner.agent_stages = [
        {
            "role_name": "proposer",
            "ok": True,
            "structured_output": adapter._base_analysis(revised=False),
        },
        {
            "role_name": "critic",
            "ok": True,
            "structured_output": adapter._payload_for_role("critic"),
        },
        {
            "role_name": "reviser_round_1",
            "ok": True,
            "structured_output": adapter._payload_for_role("reviser_round_1"),
        },
        {
            "role_name": "auditor",
            "ok": False,
            "structured_output": None,
        },
    ]

    bounded_review_summary = runner._build_bounded_review_summary(
        {
            "analysis_review_contract": runner.analysis_review_contract.to_dict(),
            "review_loop_exercised": True,
        }
    )

    assert bounded_review_summary is not None
    assert bounded_review_summary["recommendation_count"] == 3
    assert bounded_review_summary["recommendations_with_review_surface"] == 3
    assert len(bounded_review_summary["review_stages"]) == 1
    assert bounded_review_summary["review_stages"][0]["role_name"] == "critic"


def test_bounded_review_summary_ignores_empty_final_analysis_and_recovers_from_stage_history(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path, min_recommendations=2)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr(
        "anvil.harness.runner.get_provider",
        lambda name: _AcceptingHarnessAdapter(),
    )

    runner = HarnessRunner(
        task_path=task_path,
        strategy_path=strategy_path,
        workspace=workspace,
        out_root=tmp_path / "runs",
    )
    runner._analysis_contract()
    adapter = _PartialAcceptanceHarnessAdapter()
    runner.agent_stages = [
        {
            "role_name": "proposer",
            "ok": True,
            "structured_output": adapter._base_analysis(revised=False),
        },
        {
            "role_name": "critic",
            "ok": True,
            "structured_output": adapter._payload_for_role("critic"),
        },
        {
            "role_name": "reviser_round_1",
            "ok": True,
            "structured_output": adapter._payload_for_role("reviser_round_1"),
        },
        {
            "role_name": "auditor",
            "ok": False,
            "structured_output": None,
        },
    ]

    bounded_review_summary = runner._build_bounded_review_summary(
        {
            "analysis_review_contract": runner.analysis_review_contract.to_dict(),
            "review_loop_exercised": True,
            "final_analysis": {},
        }
    )

    assert bounded_review_summary is not None
    assert bounded_review_summary["recommendation_count"] == 3
    assert bounded_review_summary["recommendations_with_review_surface"] == 3
    resolved_analysis = runner._resolve_bounded_review_analysis_payload(
        {"final_analysis": {}}
    )
    assert resolved_analysis["status"] == "revised"
    assert resolved_analysis["issue_resolution_map"][0]["issue_id"] == "AR-001"
