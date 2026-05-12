from __future__ import annotations

import copy
import importlib.util
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.harness.runner import HarnessRunner

_OUTPUT_DIR_NAME = ".forge-harness-runs"
_SNAPSHOT_EXCLUDES = (
    ".git",
    ".forge-harness-runs",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    ".codex-subagents",
    ".gstack",
    "__pycache__",
    ".DS_Store",
)
_WORKFLOW_FIXTURE_PATHS = (
    ".github/workflows/codex-cli-release-watch.yml",
    ".github/workflows/claude-code-release-watch.yml",
    ".github/workflows/codex-cli-update-snapshot.yml",
    ".github/workflows/claude-code-update-snapshot.yml",
)
_TOPIC_ID = "TOPIC-001"
_SCOPED_TOPIC_CLOSURE_REVIEW = [
    {
        "topic_id": _TOPIC_ID,
        "checked_files": [".github/workflows/claude-code-release-watch.yml"],
        "verified_evidence_refs": [".github/workflows/claude-code-release-watch.yml"],
        "summary": "The global topic was re-checked directly against scoped evidence.",
    }
]


@dataclass(frozen=True)
class ReplayScenario:
    slug: str
    proof_mode: str
    topic_status: str


_SCENARIOS = (
    ReplayScenario(
        slug="topic_closure_missing_scoped_proof",
        proof_mode="missing_scoped_proof",
        topic_status="carried_forward",
    ),
    ReplayScenario(
        slug="topic_closure_scoped_proof_complete_carried_forward",
        proof_mode="scoped_proof_complete",
        topic_status="carried_forward",
    ),
    ReplayScenario(
        slug="topic_closure_scoped_proof_complete_resolved",
        proof_mode="scoped_proof_complete",
        topic_status="resolved",
    ),
)


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_test_harness_runner_module(repo_root: Path) -> ModuleType:
    return _load_module_from_path(
        "forge_test_harness_runner",
        repo_root / "tests" / "test_harness_runner.py",
    )


def _write_task_and_strategy(
    temp_root: Path,
    *,
    task_id: str,
    min_recommendations: int = 2,
    evidence_cap_policy: str = "trim_to_cap",
    strategy_kind: str = "analysis_review_trust_v1",
) -> tuple[Path, Path]:
    task_path = temp_root / "task.yaml"
    task_path.write_text(
        f"""
id: {task_id}
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
""".strip()
        + "\n",
        encoding="utf-8",
    )

    strategy_path = temp_root / "strategy.yaml"
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
validators: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return task_path, strategy_path


def _workflow_fixture_text(fixture_name: str) -> str:
    return (
        f"name: {fixture_name}\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  fixture:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f'      - run: echo "{fixture_name}"\n'
    )


def _seed_workflow_fixtures(snapshot_root: Path) -> None:
    # The fake adapters only care that these paths are real and human-readable.
    for relative_path in _WORKFLOW_FIXTURE_PATHS:
        workflow_path = snapshot_root / relative_path
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(
            _workflow_fixture_text(workflow_path.stem),
            encoding="utf-8",
        )


def _create_workspace_snapshot(repo_root: Path, snapshot_root: Path) -> Path:
    shutil.copytree(
        repo_root,
        snapshot_root,
        ignore=shutil.ignore_patterns(*_SNAPSHOT_EXCLUDES),
    )
    _seed_workflow_fixtures(snapshot_root)
    return snapshot_root


def _build_topic_closure_adapter(
    test_harness_runner: ModuleType,
    *,
    proof_mode: str,
    topic_status: str,
):
    base_adapter_cls = test_harness_runner._TrustInferenceHarnessAdapter
    scoped_reviews = (
        copy.deepcopy(_SCOPED_TOPIC_CLOSURE_REVIEW)
        if proof_mode == "scoped_proof_complete"
        else []
    )

    class TopicClosureReplayHarnessAdapter(base_adapter_cls):
        def _payload_for_role(self, role_name: str):
            if role_name == "critic":
                payload = copy.deepcopy(super()._payload_for_role(role_name))
                payload["verdict"] = "revise"
                payload["summary"] = (
                    "A global topic remains open and needs explicit tracking."
                )
                payload["topics"] = [
                    {
                        "topic_id": _TOPIC_ID,
                        "severity": "medium",
                        "title": "A global fallback classification policy remains unresolved.",
                        "evidence": (
                            "The review still depends on a repo-wide fallback policy "
                            "that is not fully closed."
                        ),
                        "repair_hint": (
                            "Keep the global topic tracked until the policy is proven "
                            "or explicitly narrowed."
                        ),
                        "recommendation_index": None,
                    }
                ]
                payload["resolved_topic_ids"] = []
                payload["carried_forward_topic_ids"] = []
                payload["waived_topic_ids"] = []
                payload["topic_closure_reviews"] = []
                return payload

            if role_name == "reviser_round_1":
                payload = copy.deepcopy(self._base_analysis(revised=True))
                if topic_status == "resolved":
                    resolution = {
                        "topic_id": _TOPIC_ID,
                        "status": "addressed",
                        "recommendation_index": None,
                        "change_summary": (
                            "The revision closed the global fallback policy by grounding "
                            "it in scoped workflow evidence."
                        ),
                        "residual_risk": "",
                    }
                else:
                    resolution = {
                        "topic_id": _TOPIC_ID,
                        "status": "not_addressed",
                        "recommendation_index": None,
                        "change_summary": (
                            "The revision improved the recommendations but did not close "
                            "the global fallback policy."
                        ),
                        "residual_risk": (
                            "The run still depends on a global fallback classification "
                            "claim."
                        ),
                    }
                payload["topic_resolution_map"] = [resolution]
                return payload

            if role_name == "auditor":
                payload = copy.deepcopy(super()._payload_for_role(role_name))
                if topic_status == "resolved":
                    payload["verdict"] = "accept"
                    payload["summary"] = (
                        "The recommendations are usable, and the scoped review closes "
                        "the global topic."
                    )
                else:
                    payload["verdict"] = "accept_partial"
                    payload["summary"] = (
                        "The recommendations are usable, and the remaining global topic "
                        "is explicitly classified."
                    )
                payload["topics"] = []
                if topic_status == "resolved":
                    payload["resolved_topic_ids"] = [_TOPIC_ID]
                    payload["carried_forward_topic_ids"] = []
                else:
                    payload["resolved_topic_ids"] = []
                    payload["carried_forward_topic_ids"] = [_TOPIC_ID]
                payload["waived_topic_ids"] = []
                payload["topic_closure_reviews"] = copy.deepcopy(scoped_reviews)
                return payload

            return copy.deepcopy(super()._payload_for_role(role_name))

    return TopicClosureReplayHarnessAdapter()


def _run_replay(
    *,
    repo_root: Path,
    out_root: Path,
    test_harness_runner: ModuleType,
    scenario: ReplayScenario,
) -> Path:
    with tempfile.TemporaryDirectory(prefix=f"{scenario.slug}-") as temp_dir_raw:
        temp_root = Path(temp_dir_raw)
        workspace = _create_workspace_snapshot(repo_root, temp_root / "workspace")
        task_path, strategy_path = _write_task_and_strategy(
            temp_root,
            task_id=f"recommend_automation_improvements-{scenario.slug}",
        )
        adapter = _build_topic_closure_adapter(
            test_harness_runner,
            proof_mode=scenario.proof_mode,
            topic_status=scenario.topic_status,
        )
        with patch("anvil.harness.runner.reload_config", lambda path: ({}, {})):
            with patch(
                "anvil.harness.runner.get_provider",
                lambda name, adapter=adapter: adapter,
            ):
                runner = HarnessRunner(
                    task_path=task_path,
                    strategy_path=strategy_path,
                    workspace=workspace,
                    out_root=out_root,
                )
                summary = runner.run()
    return Path(summary["artifacts"]["run_dir"])


def generate_replays(repo_root: Path, out_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    test_harness_runner = _load_test_harness_runner_module(repo_root)

    run_dirs: list[Path] = []
    for scenario in _SCENARIOS:
        run_dirs.append(
            _run_replay(
                repo_root=repo_root,
                out_root=out_root,
                test_harness_runner=test_harness_runner,
                scenario=scenario,
            )
        )
    return run_dirs


def main() -> int:
    out_root = _REPO_ROOT / _OUTPUT_DIR_NAME
    run_dirs = generate_replays(_REPO_ROOT, out_root)
    for scenario, run_dir in zip(_SCENARIOS, run_dirs, strict=True):
        print(f"{scenario.slug}: {run_dir / 'summary.json'}")
        print(f"{scenario.slug}: {run_dir / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
