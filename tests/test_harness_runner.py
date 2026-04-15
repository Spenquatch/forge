from __future__ import annotations

import json
from pathlib import Path

from anvil.harness.files import load_structured_file

from anvil.harness.runner import HarnessRunner
from anvil.harness.types import ProviderRun


class _AcceptingHarnessAdapter:
    @staticmethod
    def _review_surface(*, must_check_files: list[str], optional_check_files: list[str], scope_note: str) -> dict:
        return {
            "must_check_files": must_check_files,
            "optional_check_files": optional_check_files,
            "scope_note": scope_note,
        }

    def run(self, request):
        out_dir = Path(request.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "response.txt").write_text("ok", encoding="utf-8")
        (out_dir / "error.txt").write_text("", encoding="utf-8")
        payload = self._payload_for_role(request.role_name)
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
            output_path=str(out_dir / "structured_output.json"),
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
                        must_check_files=[".github/workflows/codex-cli-release-watch.yml"],
                        optional_check_files=[".github/workflows/claude-code-release-watch.yml"],
                        scope_note="Limit review to the release-watch workflow concurrency behavior.",
                    ),
                },
                {
                    "classification": "recommendation",
                    "priority": "medium",
                    "title": "Align timeout handling",
                    "rationale": "Uneven timeout settings make failures harder to compare.",
                    "evidence": [".github/workflows/claude-code-update-snapshot.yml"],
                    "proposed_change": "Use explicit timeout-minutes consistently across both release paths.",
                    "confidence": 0.81,
                    "review_surface": self._review_surface(
                        must_check_files=[".github/workflows/claude-code-release-watch.yml"],
                        optional_check_files=[".github/workflows/codex-cli-release-watch.yml"],
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
        return payload

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "reviser_round_1":
            return self._base_analysis(revised=True)
        if role_name in {"critic", "auditor"}:
            return {
                "verdict": "accept",
                "summary": "Grounded and actionable analysis.",
                "workspace_write_intent": "none",
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
                "missing_topics": [],
                "grounding_score": 0.93,
                "actionability_score": 0.89,
                "scope_compliance_score": 0.95,
                "confidence": 0.88,
                "scope_escapes": [],
            }
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
                    must_check_files=[".github/workflows/claude-code-release-watch.yml"],
                    optional_check_files=[],
                    scope_note="Keep the review bounded to existing release-watch failure-path handling.",
                ),
            }
        )
        return payload

    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            return self._base_analysis(revised=False)
        if role_name == "critic":
            return {
                "verdict": "revise",
                "summary": "Two recommendations are good, but recommendation 3 needs more specificity.",
                "workspace_write_intent": "none",
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
                "missing_topics": [],
                "grounding_score": 0.90,
                "actionability_score": 0.71,
                "scope_compliance_score": 0.94,
                "confidence": 0.82,
                "scope_escapes": [],
            }
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
            return {
                "verdict": "accept_partial",
                "summary": "Recommendations 1 and 2 are usable. Recommendation 3 still needs more specificity.",
                "workspace_write_intent": "none",
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
                "missing_topics": [],
                "grounding_score": 0.88,
                "actionability_score": 0.73,
                "scope_compliance_score": 0.95,
                "confidence": 0.84,
                "scope_escapes": [],
            }
        return super()._payload_for_role(role_name)


class _InvalidSemanticHarnessAdapter(_AcceptingHarnessAdapter):
    def _payload_for_role(self, role_name: str):
        if role_name == "proposer":
            payload = self._base_analysis(revised=False)
            payload["strengths"] = {"items": [], "none_reason": ""}
            payload["uncertainties"] = {"items": [], "none_reason": ""}
            payload["files_reviewed"] = []
            return payload
        return super()._payload_for_role(role_name)


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
            (out_dir / "structured_output.json").write_text(json.dumps(payload), encoding="utf-8")
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
                output_path=str(out_dir / "structured_output.json"),
                structured_output=payload,
                raw_meta={},
                error="Provider quota exhausted: You've hit your limit · resets 1pm (America/Indiana/Indianapolis)",
                failure_kind="quota_exhausted",
                failure_summary="Provider quota exhausted: You've hit your limit · resets 1pm (America/Indiana/Indianapolis)",
            )
        return super().run(request)



def _write_task_and_strategy(tmp_path: Path, *, min_recommendations: int = 2) -> tuple[Path, Path]:
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
""".strip()
        + "\n",
        encoding="utf-8",
    )

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        """
name: analysis-review-fake
kind: analysis_review_v1
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
validators: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return task_path, strategy_path



def _prepare_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (workspace / ".github" / "workflows" / "codex-cli-release-watch.yml").write_text(
        "name: codex\n",
        encoding="utf-8",
    )
    (workspace / ".github" / "workflows" / "claude-code-release-watch.yml").write_text(
        "name: claude\n",
        encoding="utf-8",
    )
    return workspace



def test_analysis_review_runner_creates_final_answer_and_enforces_read_only(
    tmp_path,
    monkeypatch,
):
    workspace = _prepare_workspace(tmp_path)
    task_path, strategy_path = _write_task_and_strategy(tmp_path)

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: _AcceptingHarnessAdapter())

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
    assert summary["analysis_review_contract"]["contract_version"] == "analysis_review_v1_contract_v3"
    assert summary["analysis_review_contract"]["partial_acceptance"]["min_accepted_recommendations"] == 2
    assert summary["analysis_review_contract"]["bounded_review"]["critic_issue_cap"] == 5
    assert summary["final_answer"]["recommendations"][0]["title"] == "Add concurrency controls"
    assert summary["final_answer"]["recommendations"][0]["review_surface"]["must_check_files"] == [
        ".github/workflows/codex-cli-release-watch.yml"
    ]
    assert summary["final_answer"]["strengths"]["items"] == ["Grounded in workflow files"]
    assert summary["recommendation_reviews"][0]["verdict"] == "accept"
    assert summary["issue_ledger"] == []
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
            "new_medium_or_higher_issue_count": 0,
            "new_medium_or_higher_issue_cap": None,
            "scope_escape_count": 0,
        },
        {
            "role_name": "auditor",
            "round_index": 1,
            "issue_count": 0,
            "issue_cap": None,
            "missing_topic_count": 0,
            "missing_topic_cap": None,
            "new_medium_or_higher_issue_count": 0,
            "new_medium_or_higher_issue_cap": 1,
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
    proposer_semantic = load_structured_file(Path(proposer_stage["semantic_validation_path"]))
    assert proposer_semantic["ok"] is True
    assert proposer_semantic["skipped"] is False
    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "## Bounded Review" in report_text
    assert "- Review surfaces declared: `2` / `2` recommendations" in report_text
    assert '"rendered_in_report_section": true' in report_text
    assert '"bounded_review_summary": {' in report_text
    assert '"review_stages"' not in report_text.split('"bounded_review_summary": {', 1)[1].split("}", 1)[0]



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
        "strengths must contain at least one concrete item or a non-empty none_reason" in error
        for error in proposer_stage["semantic_validation_errors"]
    )
    assert any(
        "files_reviewed must contain at least 1 non-empty path" in error
        for error in proposer_stage["semantic_validation_errors"]
    )
    assert Path(proposer_stage["semantic_validation_path"]).exists()


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
    assert summary["analysis_review_coverage"]["review_loop_exercised"] is False
    assert summary["analysis_review_coverage"]["review_stages_attempted"] == 1
    assert summary["analysis_review_coverage"]["review_stages_completed"] == 0

    critic_stage = summary["agent_stages"][1]
    assert critic_stage["failure_kind"] == "quota_exhausted"
    assert "$.verdict: missing required field" not in critic_stage["error"]
    semantic_payload = load_structured_file(Path(critic_stage["semantic_validation_path"]))
    assert semantic_payload["skipped"] is True
    assert semantic_payload["skipped_reason"] == "provider_failure:quota_exhausted"

    draft = summary["drafts"][0]
    assert draft["review_state"] == "not_evaluated"
    assert "medium_or_higher" not in draft["issue_counts"]
    assert "review_failure_summary" in draft["metadata"]

    report_text = Path(summary["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "Review loop exercised: `False`" in report_text
    assert "Review issue counts: `not evaluated`" in report_text
    best_draft_text = Path(summary["artifacts"]["best_draft_md"]).read_text(encoding="utf-8")
    assert "not evaluated by a successful critic/auditor stage" in best_draft_text
