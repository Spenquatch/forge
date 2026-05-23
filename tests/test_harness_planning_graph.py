from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from anvil.harness.builder import build_harness_langgraph
from anvil.harness.state import initialize_harness_state
from anvil.harness.types import ProviderRun


def _write_workspace_file(workspace: Path, relative_path: str, content: str) -> None:
    path = workspace / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_planning_workspace(
    workspace: Path,
    *,
    include_hint_matches: bool = True,
) -> None:
    if not include_hint_matches:
        _write_workspace_file(workspace, "README.md", "# workspace\n")
        return

    _write_workspace_file(workspace, "PLAN.md", "# C1 planning package\n")
    _write_workspace_file(
        workspace,
        "anvil/harness/builder.py",
        "def build_harness_langgraph():\n    return 'planning_v1'\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/strategy_graph.py",
        "PLANNING_RUNTIME_TARGET = 'planning_v1'\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/planning_runtime.py",
        "def execute_planning_runtime(state):\n    return state\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/reporting.py",
        "def publish_state_artifacts_v1(state):\n    return state\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/artifacts.py",
        "def artifact_description(name):\n    return name\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/report.py",
        "def render_report(summary):\n    return summary\n",
    )
    _write_workspace_file(
        workspace,
        "anvil/harness/subgraphs/planning_v1.py",
        "def planning_v1_subgraph(state):\n    return state\n",
    )


def _seed_workspace_files(workspace: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        _write_workspace_file(workspace, relative_path, content)


def _planning_state(tmp_path: Path) -> dict[str, Any]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    state = initialize_harness_state(
        task_path=str(tmp_path / "task.yaml"),
        strategy_path=str(tmp_path / "strategy.yaml"),
        workspace_root=str(workspace),
        out_root=str(out_root),
    )
    state["run_id"] = "planning-run"
    state["thread_id"] = "thread-planning"
    state["run_dir"] = str(out_root / "planning-run")
    state["created_at"] = "2026-05-17T00:00:00+00:00"
    state["task_spec"] = {
        "id": "task-plan",
        "objective": "Plan a deterministic rollout for the planning runtime.",
        "task_kind": "planning",
        "workspace_write_policy": {"mode": "forbid"},
        "acceptance": ["Emit seams, workstreams, and slices."],
        "files_hint": ["PLAN.md", "anvil/harness/*"],
    }
    state["task_kind"] = "planning"  # type: ignore[assignment]
    state["strategy_spec"] = {
        "name": "deterministic planning",
        "kind": "deterministic_feature_planning_v1",
        "runtime_target": "planning_v1",
        "phases": [
            {"id": "design_doc", "stage_type": "rubric_design_doc"},
            {
                "id": "seam_decomposition",
                "stage_type": "architecture_seam_decomposition",
            },
            {
                "id": "parallel_planning",
                "stage_type": "parallel_workstream_planning",
            },
            {"id": "slice_emission", "stage_type": "executable_slice_emission"},
        ],
        "artifact_policy": "planning_package_v1",
        "coverage_policy": "measurable_coverage_v1",
        "determinism_policy": "stable_structure_v1",
        "discovery_policy": "bounded_repo_scan_v1",
        "rubric_policy": "design_doc_gate_v1",
        "stop_policy": "clarification_or_stop_v1",
        "planning_execution": {"mode": "graph_owned"},
    }
    state["strategy_kind"] = "deterministic_feature_planning_v1"  # type: ignore[assignment]
    state["config_verdict"] = "pass"
    state["validator_verdict"] = "not_applicable"
    state["policy_verdict"] = "pass"
    return state


def _planning_graph_state(
    tmp_path: Path,
    *,
    phase_inputs: dict[str, Any] | None = None,
    include_hint_matches: bool = True,
) -> dict[str, Any]:
    state = _planning_state(tmp_path)
    _seed_planning_workspace(
        Path(str(state["workspace_root"])),
        include_hint_matches=include_hint_matches,
    )
    if phase_inputs is not None:
        state["strategy_spec"] = {
            **dict(state["strategy_spec"]),
            "phase_inputs": phase_inputs,
        }
    state["strategy_graph_spec"] = {
        "runtime_target": "planning_v1",
        "post_runtime_action": "write_artifacts",
        "planning_execution": {"mode": "graph_owned"},
    }
    state["strategy_graph_spec_id"] = "planning_v1.test"
    state["strategy_graph_subset"] = "bounded_strategy_graph_v1"
    return state


def _run_graph(
    state: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    monkeypatch.setattr(
        "anvil.harness.builder.prepare_run_node",
        lambda payload: deepcopy(state),
    )
    monkeypatch.setattr(
        "anvil.harness.builder.validator_preflight_node",
        lambda payload: payload,
    )
    monkeypatch.setattr(
        "anvil.harness.builder.select_strategy_node",
        lambda payload: payload,
    )
    graph = build_harness_langgraph()
    return asyncio.run(
        graph.ainvoke(
            {
                "task_path": state["task_path"],
                "strategy_path": state["strategy_path"],
                "workspace_root": state["workspace_root"],
                "out_root": state["out_root"],
                "thread_id": state["thread_id"],
            },
            {"configurable": {"thread_id": str(state.get("thread_id") or "thread")}},
        )
    )


def test_planning_runtime_success_populates_frozen_state_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"
    assert result["planning_stop_reason"] is None
    assert result["run_verdict"] == "success"
    assert result["content_verdict"] == "success"
    assert result["clarification_requests"] == []
    assert "anvil/harness/subgraphs/planning_v1.py" in result["repo_evidence_refs"]
    assert result["planning_phase_results"][0]["primary_cut_summary"].startswith(
        "Selected primary cut `anvil/harness`"
    )
    assert [item["seam_id"] for item in result["planning_seams"]] == [
        "seam-01-anvil-harness"
    ]
    assert [item["workstream_id"] for item in result["planning_workstreams"]] == [
        "workstream-01-anvil-harness"
    ]
    assert [item["slice_id"] for item in result["planning_slices"]] == [
        "slice-01-anvil-harness"
    ]
    assert result["planning_workstreams"][0]["seam_ids"] == ["seam-01-anvil-harness"]
    assert (
        result["planning_slices"][0]["workstream_id"] == "workstream-01-anvil-harness"
    )
    assert result["planning_slices"][0]["seam_ids"] == ["seam-01-anvil-harness"]
    assert len(result["planning_slices"][0]["acceptance_criteria"]) == 2
    assert [item["stage_type"] for item in result["planning_phase_results"]] == [
        "rubric_design_doc",
        "architecture_seam_decomposition",
        "parallel_workstream_planning",
        "executable_slice_emission",
    ]
    assert result["planning_policy_versions"] == {
        "artifact_policy": "planning_package_v1",
        "coverage_policy": "measurable_coverage_v1",
        "determinism_policy": "stable_structure_v1",
        "discovery_policy": "bounded_repo_scan_v1",
        "rubric_policy": "design_doc_gate_v1",
        "stop_policy": "clarification_or_stop_v1",
    }
    assert result["planning_execution_mode"] == "graph_owned"
    assert result["planning_execution_contract"] == {
        "family": "planning_v1",
        "mode": "graph_owned",
        "provider_participation": "none",
    }
    assert result["planning_coverage_status"] == "success"
    assert [item["coverage_id"] for item in result["planning_coverage_ledger"]] == [
        "coverage-01-problem_frame",
        "coverage-02-repo_surface",
        "coverage-03-seam_selection",
        "coverage-04-dependency_shape",
        "coverage-05-execution_partitioning",
        "coverage-06-acceptance_shape",
        "coverage-07-risk_and_unknowns",
    ]
    assert all(row["status"] == "covered" for row in result["planning_coverage_ledger"])
    assert result["planning_assumptions_register"] == []
    assert result["planning_uncovered_delta"] == []
    assert all(
        phase_id
        in {"design_doc", "seam_decomposition", "parallel_planning", "slice_emission"}
        for row in result["planning_coverage_ledger"]
        for phase_id in row["source_phase_ids"]
    )
    assert result["search_pass_count"] == 2
    assert result["inspected_file_count"] == 8
    assert result["discovery_budget_escalated"] is True
    assert result["drafts"] == []
    assert Path(result["summary_payload"]["artifacts"]["summary_json"]).exists()
    assert result["run_details"]["planning_run_mode"] == "deterministic-live"
    assert result["run_details"]["planning_execution_mode"] == "graph_owned"


def test_planning_runtime_consumes_compiled_graph_phase_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)
    state["strategy_spec"] = {
        **dict(state["strategy_spec"]),
        "phases": [
            {"id": "raw_wrong_design", "stage_type": "rubric_design_doc"},
            {
                "id": "raw_wrong_seams",
                "stage_type": "architecture_seam_decomposition",
            },
            {
                "id": "raw_wrong_parallel",
                "stage_type": "parallel_workstream_planning",
            },
            {
                "id": "raw_wrong_slices",
                "stage_type": "executable_slice_emission",
            },
        ],
    }
    state["strategy_graph_spec"] = {
        **dict(state["strategy_graph_spec"]),
        "phases": [
            {"id": "design_doc", "stage_type": "rubric_design_doc"},
            {
                "id": "seam_decomposition",
                "stage_type": "architecture_seam_decomposition",
            },
            {
                "id": "parallel_planning",
                "stage_type": "parallel_workstream_planning",
            },
            {"id": "slice_emission", "stage_type": "executable_slice_emission"},
        ],
    }

    result = _run_graph(state, monkeypatch)

    assert [item["phase_id"] for item in result["planning_phase_results"]] == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]


def test_planning_runtime_executes_optional_provider_review_without_replacing_structure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)
    state["strategy_spec"] = {
        **dict(state["strategy_spec"]),
        "roles": {"planner": {"provider": "codex_cli", "access": "read"}},
        "planning_execution": {"mode": "graph_owned_with_planner_review"},
    }
    state["strategy_graph_spec"] = {
        **dict(state["strategy_graph_spec"]),
        "planning_execution": {
            "mode": "graph_owned_with_planner_review",
            "provider_participation": "planner_review",
            "provider_role_name": "planner",
        },
        "stages": [
            {
                "stage_id": "design_doc",
                "role_name": "planner",
                "stage_type": "rubric_design_doc",
            },
            {
                "stage_id": "seam_decomposition",
                "role_name": "planner",
                "stage_type": "architecture_seam_decomposition",
            },
            {
                "stage_id": "parallel_planning",
                "role_name": "planner",
                "stage_type": "parallel_workstream_planning",
            },
            {
                "stage_id": "slice_emission",
                "role_name": "planner",
                "stage_type": "executable_slice_emission",
            },
            {
                "stage_id": "planner_review",
                "role_name": "planner",
                "stage_type": "planner_review",
            },
        ],
    }

    class _FakePlannerAdapter:
        def run(self, request):
            assert request.role_name == "planner"
            assert request.role_config.provider == "codex_cli"
            return ProviderRun(
                role_name="planner",
                provider="codex_cli",
                model="gpt-5.4",
                access="read",
                ok=True,
                exit_code=0,
                duration_sec=0.01,
                cwd=request.cwd,
                command=["codex"],
                stdout_path=str(tmp_path / "stdout.txt"),
                stderr_path=str(tmp_path / "stderr.txt"),
                prompt_path=str(tmp_path / "prompt.txt"),
                schema_path=str(tmp_path / "schema.json"),
                output_path=str(tmp_path / "output.json"),
                raw_output_path=str(tmp_path / "output.raw.json"),
                normalized_output_path=str(tmp_path / "output.normalized.json"),
                structured_output={
                    "verdict": "accept_with_caveat",
                    "summary": "The deterministic plan is sound but should call out one residual risk.",
                    "strengths": ["Repo evidence stays bounded."],
                    "risks": [
                        "One acceptance criterion could cite a stronger file anchor."
                    ],
                    "coverage_challenges": [
                        "Clarify whether artifact publication needs CLI output examples."
                    ],
                    "follow_up_questions": [],
                    "referenced_seam_ids": ["seam-01-anvil-harness"],
                    "referenced_workstream_ids": ["workstream-01-anvil-harness"],
                    "referenced_slice_ids": ["slice-01-anvil-harness"],
                    "confidence": 0.79,
                },
            )

    monkeypatch.setattr(
        "anvil.harness.planning_runtime.get_provider",
        lambda name: _FakePlannerAdapter(),
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"
    assert result["planning_execution_mode"] == "graph_owned_with_planner_review"
    assert result["planning_execution_contract"] == {
        "family": "planning_v1",
        "mode": "graph_owned_with_planner_review",
        "provider_participation": "planner_review",
    }
    assert result["planning_provider_review"]["verdict"] == "accept_with_caveat"
    assert result["planning_provider_disagreement_count"] == 1
    assert len(result["planning_provider_stage_results"]) == 1
    assert result["planning_provider_stage_results"][0]["status"] == "success"
    assert result["planning_run_mode"] == "provider-reviewed"
    assert result["run_details"]["planning_run_mode"] == "provider-reviewed"
    assert [item["seam_id"] for item in result["planning_seams"]] == [
        "seam-01-anvil-harness"
    ]


def test_planning_runtime_fails_closed_when_provider_review_cannot_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)
    state["strategy_spec"] = {
        **dict(state["strategy_spec"]),
        "roles": {"planner": {"provider": "codex_cli", "access": "read"}},
        "planning_execution": {"mode": "graph_owned_with_planner_review"},
    }
    state["strategy_graph_spec"] = {
        **dict(state["strategy_graph_spec"]),
        "planning_execution": {
            "mode": "graph_owned_with_planner_review",
            "provider_participation": "planner_review",
            "provider_role_name": "planner",
        },
        "stages": [
            {
                "stage_id": "design_doc",
                "role_name": "planner",
                "stage_type": "rubric_design_doc",
            },
            {
                "stage_id": "seam_decomposition",
                "role_name": "planner",
                "stage_type": "architecture_seam_decomposition",
            },
            {
                "stage_id": "parallel_planning",
                "role_name": "planner",
                "stage_type": "parallel_workstream_planning",
            },
            {
                "stage_id": "slice_emission",
                "role_name": "planner",
                "stage_type": "executable_slice_emission",
            },
            {
                "stage_id": "planner_review",
                "role_name": "planner",
                "stage_type": "planner_review",
            },
        ],
    }

    class _FailingPlannerAdapter:
        def run(self, request):
            return ProviderRun(
                role_name="planner",
                provider="codex_cli",
                model="gpt-5.4",
                access="read",
                ok=False,
                exit_code=1,
                duration_sec=0.01,
                cwd=request.cwd,
                command=["codex"],
                stdout_path=str(tmp_path / "stdout.txt"),
                stderr_path=str(tmp_path / "stderr.txt"),
                prompt_path=str(tmp_path / "prompt.txt"),
                schema_path=str(tmp_path / "schema.json"),
                output_path=None,
                raw_output_path=None,
                normalized_output_path=None,
                structured_output=None,
                error="provider auth missing",
                failure_kind="auth_missing",
                failure_summary="provider auth missing",
            )

    monkeypatch.setattr(
        "anvil.harness.planning_runtime.get_provider",
        lambda name: _FailingPlannerAdapter(),
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "failed"
    assert result["planning_stop_reason"] == (
        "planning_provider_review_failed:auth_missing"
    )
    assert result["planning_provider_failure"]["failure_kind"] == "auth_missing"
    assert result["planning_provider_stage_results"][0]["status"] == "failed"
    assert result["planning_run_mode"] == "provider-reviewed"


def test_planning_runtime_stops_for_clarification_without_fake_downstream_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(
        tmp_path,
        include_hint_matches=False,
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "clarification_needed"
    assert result["planning_stop_reason"] == "files_hint_unresolved"
    assert result["run_verdict"] == "clarification_needed"
    assert result["content_verdict"] == "clarification_needed"
    assert [item["question"] for item in result["clarification_requests"]] == [
        "Which concrete repository path or seam should the planning package inspect first?"
    ]
    assert len(result["planning_phase_results"]) == 1
    assert result["planning_phase_results"][0]["status"] == "clarification_needed"
    assert result["planning_phase_results"][0]["repo_evidence_refs"] == []
    assert result["planning_seams"] == []
    assert result["planning_workstreams"] == []
    assert result["planning_slices"] == []
    assert result["planning_coverage_status"] == "clarification_needed"
    assert len(result["planning_coverage_ledger"]) == 7
    assert [
        row["dimension"]
        for row in result["planning_coverage_ledger"]
        if row["status"] in {"partial", "uncovered"}
    ] == [
        "problem_frame",
        "repo_surface",
        "seam_selection",
        "dependency_shape",
        "execution_partitioning",
        "acceptance_shape",
        "risk_and_unknowns",
    ]
    assert len(result["planning_assumptions_register"]) == 7
    assert len(result["planning_uncovered_delta"]) == 7
    assert all(
        row["recommended_next_phase"]
        in {
            "design_doc",
            "seam_decomposition",
            "parallel_planning",
            "slice_emission",
            "clarify",
        }
        for row in result["planning_uncovered_delta"]
    )
    assert result["drafts"] == []
    assert result.get("best_draft_id") is None
    assert result.get("selected_draft_id") is None


def test_planning_runtime_emits_repo_derived_structure_for_credible_live_cuts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_state(tmp_path)
    workspace = Path(str(state["workspace_root"]))
    _seed_workspace_files(
        workspace,
        {
            "gsd-browser/src/gsd_browser/optionb/task_backend.py": (
                "TASK_STATUS = 'queued'\n"
                "def update_task_status(task_id, status):\n"
                "    return {'task_id': task_id, 'status': status}\n"
            ),
            "gsd-browser/src/gsd_browser/optionb/progress.py": (
                "def stream_task_status(task_id):\n"
                "    return {'task_id': task_id, 'status': 'running'}\n"
            ),
            "gsd-dashboard/src/hooks/useSession.ts": (
                "export function useSessionStatus() {\n"
                "  return { status: 'running' };\n"
                "}\n"
            ),
            "gsd-dashboard/src/components/SessionViewer.tsx": (
                "export function SessionViewer() {\n"
                "  return <div>task status</div>;\n"
                "}\n"
            ),
        },
    )
    state["task_spec"]["objective"] = (
        "Plan a bounded slice for the Option B task status contract and dashboard "
        "session status flow."
    )
    state["task_spec"]["acceptance"] = [
        "Keep backend task status ownership explicit.",
        "Keep dashboard session status consumption explicit.",
    ]
    state["task_spec"]["files_hint"] = [
        "gsd-browser/src/gsd_browser/optionb/*.py",
        "gsd-dashboard/src/hooks/*.ts",
        "gsd-dashboard/src/components/*.tsx",
    ]
    state["strategy_graph_spec"] = {
        "runtime_target": "planning_v1",
        "post_runtime_action": "write_artifacts",
    }

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"
    assert result["planning_stop_reason"] is None
    assert result["planning_phase_results"][0]["primary_cut_summary"].startswith(
        "Selected primary cut `gsd-browser/src/gsd_browser/optionb`"
    )
    assert result["clarification_requests"] == []
    seam_ids = [item["seam_id"] for item in result["planning_seams"]]
    assert seam_ids[0] == "seam-01-gsd-browser-src-gsd-browser-optionb"
    assert "seam-runtime-routing" not in seam_ids
    assert "seam-artifact-publication" not in seam_ids
    assert [item["workstream_id"] for item in result["planning_workstreams"]] == [
        "workstream-01-gsd-browser-src-gsd-browser-optionb",
        "workstream-02-gsd-dashboard-src-components",
        "workstream-03-gsd-dashboard-src-hooks",
    ]
    assert [item["slice_id"] for item in result["planning_slices"]] == [
        "slice-01-gsd-browser-src-gsd-browser-optionb",
        "slice-02-gsd-dashboard-src-components",
        "slice-03-gsd-dashboard-src-hooks",
    ]
    assert result["planning_workstreams"][1]["depends_on_workstream_ids"] == [
        "workstream-01-gsd-browser-src-gsd-browser-optionb"
    ]
    assert result["planning_workstreams"][2]["depends_on_workstream_ids"] == [
        "workstream-02-gsd-dashboard-src-components"
    ]
    assert all(item["acceptance_criteria"] for item in result["planning_slices"])


def test_planning_runtime_failed_sets_explicit_stop_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _planning_graph_state(tmp_path)
    state["task_spec"]["objective"] = "Plan a brand-new system from scratch."

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "failed"
    assert result["planning_stop_reason"] == "planning_request_out_of_corpus"
    assert result["run_verdict"] == "failed"
    assert result["content_verdict"] == "failed"
    assert [item["status"] for item in result["planning_phase_results"]] == ["failed"]
    assert result["planning_seams"] == []
    assert result["planning_workstreams"] == []
    assert result["planning_slices"] == []
    assert result["planning_coverage_status"] == "failed"
    assert len(result["planning_coverage_ledger"]) == 7
    assert all(
        row["status"] in {"partial", "uncovered"}
        for row in result["planning_coverage_ledger"]
    )
    assert len(result["planning_assumptions_register"]) == 7
    assert len(result["planning_uncovered_delta"]) == 7


def test_planning_runtime_bypasses_select_best_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _planning_graph_state(tmp_path)

    monkeypatch.setattr(
        "anvil.harness.builder.select_best_draft_node",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("planning_v1 should route directly to write_artifacts")
        ),
    )

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == "success"


@pytest.mark.parametrize(
    ("fixture_mode", "expected_terminal_status"),
    [
        ("clarification_needed", "clarification_needed"),
        ("failed", "failed"),
    ],
)
def test_planning_runtime_allows_task_fixture_modes_to_override_success_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixture_mode: str,
    expected_terminal_status: str,
) -> None:
    state = _planning_graph_state(
        tmp_path,
        phase_inputs={
            "design_doc": {"repo_evidence_refs": ["PLAN.md"]},
            "seam_decomposition": {
                "planning_seams": [{"title": "Seam A", "summary": "A"}],
            },
            "parallel_planning": {
                "planning_workstreams": [{"title": "Workstream A", "summary": "A"}],
            },
            "slice_emission": {
                "planning_slices": [{"title": "Slice A", "summary": "A"}],
            },
        },
    )
    state["task_spec"]["notes"] = f"planning_fixture_mode={fixture_mode}"

    result = _run_graph(state, monkeypatch)

    assert result["planning_terminal_status"] == expected_terminal_status
