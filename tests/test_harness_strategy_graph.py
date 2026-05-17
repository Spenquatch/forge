from __future__ import annotations

from pathlib import Path

import pytest

from anvil.harness.files import load_structured_file
from anvil.harness.nodes.prepare_run import prepare_run_node
from anvil.harness.nodes.select_strategy import select_strategy_node
from anvil.harness.nodes.validator_preflight import validator_preflight_node
from anvil.harness.strategy_graph import (
    STRATEGY_GRAPH_SUBSET,
    build_strategy_graph_spec,
    route_after_strategy_selection,
)
from anvil.harness.types import (
    DETERMINISTIC_FEATURE_PLANNING_KIND,
    PLANNING_RUNTIME_TARGET,
    StrategyConfig,
    TaskSpec,
)


def _example_strategy(path: str) -> dict[str, object]:
    return load_structured_file(Path(path))


def _planning_task_payload() -> dict[str, object]:
    return {
        "id": "plan-release-watch-parity",
        "task_kind": "planning",
        "objective": "Produce a deterministic execution plan for the release-watch seam.",
        "workspace_write_policy": {"mode": "forbid"},
        "acceptance": ["Emit seams, workstreams, and slices."],
    }


def _planning_strategy_payload() -> dict[str, object]:
    return {
        "name": "deterministic-feature-planning",
        "kind": DETERMINISTIC_FEATURE_PLANNING_KIND,
        "runtime_target": PLANNING_RUNTIME_TARGET,
        "roles": {
            "planner": {
                "provider": "codex_cli",
                "effort": "high",
                "access": "read",
            }
        },
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
        "determinism_policy": "stable_structure_v1",
        "discovery_policy": "bounded_repo_scan_v1",
        "rubric_policy": "design_doc_gate_v1",
        "stop_policy": "clarification_or_stop_v1",
    }


def _preflight_state(
    task_spec: dict[str, object], strategy_spec: dict[str, object]
) -> dict[str, object]:
    return {
        "task_spec": task_spec,
        "strategy_spec": strategy_spec,
        "strategy_kind": str(strategy_spec.get("kind") or "single_pass"),
        "workspace_root": ".",
        "warnings": [],
        "errors": [],
        "auto_fit_strategy": True,
    }


def test_route_after_strategy_selection_preserves_runtime_family_routing():
    assert route_after_strategy_selection({"strategy_kind": "single_pass"}) == "single_pass"
    assert route_after_strategy_selection({"strategy_kind": "pfr_v1"}) == "pfr_v1"
    assert (
        route_after_strategy_selection(
            {"strategy_kind": "analysis_review_bounded_v1"}
        )
        == "analysis_review_v1"
    )
    assert (
        route_after_strategy_selection(
            {
                "strategy_kind": "analysis_review_trust_v1",
                "config_verdict": "invalid_config",
            }
        )
        == "write_artifacts"
    )
    assert (
        route_after_strategy_selection(
            {"strategy_graph_spec": {"runtime_target": PLANNING_RUNTIME_TARGET}}
        )
        == PLANNING_RUNTIME_TARGET
    )


def test_planning_task_spec_does_not_inherit_analysis_review_defaults():
    task = TaskSpec.from_dict(_planning_task_payload())

    assert task.task_kind == "planning"
    assert task.review_requirements.require_evidence_per_recommendation is False
    assert task.review_requirements.require_classification is False
    assert task.review_requirements.require_priority is False
    assert task.review_requirements.min_recommendations == 0


def test_planning_strategy_config_requires_explicit_runtime_target():
    with pytest.raises(
        ValueError,
        match="planning strategies must declare runtime_target 'planning_v1'",
    ):
        StrategyConfig.from_dict(
            {
                key: value
                for key, value in _planning_strategy_payload().items()
                if key != "runtime_target"
            }
        )


def test_planning_strategy_config_rejects_out_of_order_declared_phases():
    payload = _planning_strategy_payload()
    payload["phases"] = [
        payload["phases"][1],
        payload["phases"][0],
        payload["phases"][2],
        payload["phases"][3],
    ]

    with pytest.raises(ValueError, match="planning phases must appear in canonical order"):
        StrategyConfig.from_dict(payload)


def test_single_pass_graph_spec_is_linear_and_terminal():
    spec = build_strategy_graph_spec(
        "single_pass", _example_strategy("examples/harness/strategies/single_pass_codex.yaml")
    )

    assert spec.subset == STRATEGY_GRAPH_SUBSET
    assert spec.runtime_target == "single_pass"
    assert spec.spec_id == "single_pass.direct"
    assert [stage.stage_id for stage in spec.stages] == ["solver"]
    assert spec.linear_edges == ()
    assert spec.loops == ()
    assert [outcome.outcome_id for outcome in spec.terminal_outcomes] == [
        "solution_complete"
    ]


def test_pfr_graph_spec_emits_single_back_edge_loop_metadata():
    spec = build_strategy_graph_spec(
        "pfr_v1", _example_strategy("examples/harness/strategies/pfr_codex_claude.yaml")
    )
    spec_dict = spec.to_dict()

    assert spec.subset == STRATEGY_GRAPH_SUBSET
    assert spec.runtime_target == "pfr_v1"
    assert [stage["stage_id"] for stage in spec_dict["stages"]] == [
        "proposer",
        "falsifier",
        "patcher",
    ]
    assert spec_dict["loops"] == [
        {
            "loop_id": "pfr_repair_loop",
            "kind": "single_back_edge",
            "from_stage_id": "patcher",
            "to_stage_id": "falsifier",
            "min_iterations": 0,
            "max_iterations": 1,
            "continue_when": "falsifier_or_validator_requests_patch",
        }
    ]
    assert spec_dict["conditional_branches"][0]["stage_id"] == "falsifier"


def test_analysis_review_graph_spec_emits_focus_gate_and_revision_metadata():
    spec = build_strategy_graph_spec(
        "analysis_review_bounded_v1",
        _example_strategy(
            "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml"
        ),
    )
    spec_dict = spec.to_dict()

    assert spec.subset == STRATEGY_GRAPH_SUBSET
    assert spec.runtime_target == "analysis_review_v1"
    assert spec.spec_id == "analysis_review_bounded_v1.focus_gate_adjudicate.loops_1_3"
    assert [stage["stage_id"] for stage in spec_dict["stages"]] == [
        "focus_gate",
        "proposer",
        "critic",
        "reviser",
        "auditor",
    ]
    assert spec_dict["loops"] == [
        {
            "loop_id": "analysis_review_revision_loop",
            "kind": "single_back_edge",
            "from_stage_id": "auditor",
            "to_stage_id": "reviser",
            "min_iterations": 1,
            "max_iterations": 3,
            "continue_when": "review_requests_revision",
        }
    ]
    assert [
        branch["branch_id"] for branch in spec_dict["conditional_branches"]
    ] == [
        "focus_gate_decision",
        "critic_revision_gate",
        "auditor_revision_gate",
    ]
    assert [outcome["outcome_id"] for outcome in spec_dict["terminal_outcomes"]] == [
        "analysis_review_complete",
        "focus_gate_blocked",
        "focus_gate_no_viable_focus",
    ]


def test_trust_graph_spec_emits_attestation_stage_after_bounded_review():
    spec = build_strategy_graph_spec(
        "analysis_review_trust_v1",
        _example_strategy("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
    )
    spec_dict = spec.to_dict()

    assert spec.subset == STRATEGY_GRAPH_SUBSET
    assert spec.runtime_target == "analysis_review_v1"
    assert (
        spec.spec_id
        == "analysis_review_trust_v1.focus_gate_off.loops_1_3.trust_attestation_over_bounded"
    )
    assert [stage["stage_id"] for stage in spec_dict["stages"]] == [
        "proposer",
        "critic",
        "reviser",
        "auditor",
        "attestation_auditor",
    ]
    review_complete_paths = [
        path
        for branch in spec_dict["conditional_branches"]
        if branch["stage_id"] in {"critic", "auditor"}
        for path in branch["paths"]
        if path["path_id"] == "complete"
    ]
    assert all(
        path["target_stage_id"] == "attestation_auditor"
        for path in review_complete_paths
    )


def test_planning_graph_spec_emits_runtime_target_phases_and_post_runtime_action():
    strategy = _planning_strategy_payload()
    spec = build_strategy_graph_spec(
        DETERMINISTIC_FEATURE_PLANNING_KIND, strategy
    ).to_dict()

    assert spec["runtime_target"] == PLANNING_RUNTIME_TARGET
    assert spec["phases"] == strategy["phases"]
    assert [stage["stage_id"] for stage in spec["stages"]] == [
        "design_doc",
        "seam_decomposition",
        "parallel_planning",
        "slice_emission",
    ]
    assert spec["post_runtime_action"] == "write_artifacts"


def test_validator_preflight_rejects_invalid_planning_declarations_before_model_work():
    result = validator_preflight_node(
        _preflight_state(
            _planning_task_payload(),
            {
                key: value
                for key, value in _planning_strategy_payload().items()
                if key != "runtime_target"
            },
        )
    )

    assert result["config_verdict"] == "invalid_config"
    assert result["run_verdict"] == "invalid_config"
    assert result["stop_reason"] == "strategy_spec_parse"
    assert result["summary_text"] == (
        "planning strategies must declare runtime_target 'planning_v1'."
    )
    assert result["validator_preflight"] == []


@pytest.mark.parametrize(
    ("task_spec", "strategy_spec", "expected_error"),
    [
        (
            _planning_task_payload(),
            {
                "kind": "pfr_v1",
                "roles": {
                    "proposer": {"provider": "codex_cli"},
                    "falsifier": {"provider": "codex_cli"},
                    "patcher": {"provider": "codex_cli"},
                },
            },
            "planning tasks require a strategy with runtime_target 'planning_v1'; auto-fit is not supported.",
        ),
        (
            {
                "id": "patch-release-watch",
                "task_kind": "patch",
                "objective": "Patch the release-watch seam.",
                "workspace_write_policy": {"mode": "allow"},
            },
            _planning_strategy_payload(),
            "patch tasks are incompatible with runtime_target 'planning_v1'; auto-fit is not supported.",
        ),
    ],
)
def test_validator_preflight_blocks_planning_auto_fit_rewrites(
    task_spec: dict[str, object],
    strategy_spec: dict[str, object],
    expected_error: str,
):
    result = validator_preflight_node(_preflight_state(task_spec, strategy_spec))

    assert result["config_verdict"] == "invalid_config"
    assert result["run_verdict"] == "invalid_config"
    assert expected_error in result["errors"]


def test_select_strategy_node_stamps_graph_metadata_for_lane_smoke():
    state = prepare_run_node(
        {
            "task_path": "examples/harness/tasks/recommend_automation_improvements.yaml",
            "strategy_path": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
            "workspace_root": ".",
            "out_root": ".tmp/b1-lane-a-smoke",
        }
    )
    state = validator_preflight_node(state)
    state = select_strategy_node(state)

    assert state["strategy_graph_spec_id"] == (
        "analysis_review_bounded_v1.focus_gate_adjudicate.loops_1_3"
    )
    assert state["strategy_graph_subset"] == STRATEGY_GRAPH_SUBSET
    assert isinstance(state["strategy_graph_spec"], dict)
    assert state["strategy_graph_spec"]["runtime_target"] == "analysis_review_v1"


def test_select_strategy_node_stamps_planning_graph_metadata():
    state = validator_preflight_node(
        _preflight_state(_planning_task_payload(), _planning_strategy_payload())
    )
    state = select_strategy_node(state)

    assert state["config_verdict"] == "pass"
    assert state["strategy_graph_spec_id"] == (
        f"{DETERMINISTIC_FEATURE_PLANNING_KIND}.{PLANNING_RUNTIME_TARGET}"
    )
    assert state["strategy_graph_spec"]["runtime_target"] == PLANNING_RUNTIME_TARGET
    assert state["strategy_graph_spec"]["post_runtime_action"] == "write_artifacts"
    assert state["strategy_graph_spec"]["phases"] == _planning_strategy_payload()["phases"]
