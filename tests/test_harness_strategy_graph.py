from __future__ import annotations

from pathlib import Path

from anvil.harness.files import load_structured_file
from anvil.harness.nodes.prepare_run import prepare_run_node
from anvil.harness.nodes.select_strategy import select_strategy_node
from anvil.harness.nodes.validator_preflight import validator_preflight_node
from anvil.harness.strategy_graph import (
    STRATEGY_GRAPH_SUBSET,
    build_strategy_graph_spec,
    route_after_strategy_selection,
)


def _example_strategy(path: str) -> dict[str, object]:
    return load_structured_file(Path(path))


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
