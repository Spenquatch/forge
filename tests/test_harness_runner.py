from __future__ import annotations

import json
from pathlib import Path

from anvil.harness.runner import HarnessRunner
from anvil.harness.types import ProviderRun


class _FakeHarnessAdapter:
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

    def _payload_for_role(self, role_name: str):
        if role_name in {"proposer", "reviser_round_1"}:
            return {
                "status": "revised" if role_name.startswith("reviser") else "done",
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
                        "confidence": 0.86,
                    },
                    {
                        "classification": "recommendation",
                        "priority": "medium",
                        "title": "Align timeout handling",
                        "rationale": "Uneven timeout settings make failures harder to compare.",
                        "evidence": [".github/workflows/claude-code-update-snapshot.yml"],
                        "proposed_change": "Use explicit timeout-minutes consistently across both release paths.",
                        "confidence": 0.78,
                    },
                ],
                "strengths": ["Grounded in workflow files"],
                "uncertainties": [],
                "files_reviewed": [
                    ".github/workflows/codex-cli-release-watch.yml",
                    ".github/workflows/claude-code-release-watch.yml",
                ],
                "confidence": 0.84,
            }
        if role_name in {"critic", "auditor"}:
            return {
                "verdict": "accept",
                "summary": "Grounded and actionable analysis.",
                "workspace_write_intent": "none",
                "issues": [],
                "missing_topics": [],
                "grounding_score": 0.93,
                "actionability_score": 0.89,
                "scope_compliance_score": 0.95,
                "confidence": 0.88,
            }
        raise AssertionError(f"Unexpected role: {role_name}")


def test_analysis_review_runner_creates_final_answer_and_enforces_read_only(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".github").mkdir()
    (workspace / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (workspace / ".github" / "workflows" / "codex-cli-release-watch.yml").write_text(
        "name: codex\n", encoding="utf-8"
    )

    task_path = tmp_path / "task.yaml"
    task_path.write_text(
        """
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
  min_recommendations: 2
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

    monkeypatch.setattr("anvil.harness.runner.reload_config", lambda path: ({}, {}))
    monkeypatch.setattr("anvil.harness.runner.get_provider", lambda name: _FakeHarnessAdapter())

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
    assert summary["final_answer"]["recommendations"][0]["title"] == "Add concurrency controls"

    proposer_stage = summary["agent_stages"][0]
    reviser_stage = summary["agent_stages"][2]
    assert proposer_stage["requested_access"] == "write"
    assert proposer_stage["effective_access"] == "read"
    assert reviser_stage["requested_access"] == "write"
    assert reviser_stage["effective_access"] == "read"
