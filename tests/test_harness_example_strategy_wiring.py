from __future__ import annotations

from pathlib import Path

from anvil.harness.contracts import build_analysis_review_contract
from anvil.harness.files import load_structured_file
from anvil.harness.strategy_graph import STRATEGY_GRAPH_SUBSET, build_strategy_graph_spec
from anvil.harness.types import StrategyConfig, TaskSpec


def _task() -> TaskSpec:
    return TaskSpec.from_dict(
        {
            "id": "recommend_automation_improvements",
            "task_kind": "analysis_review",
            "objective": "Review the repo and recommend workflow improvements.",
            "workspace_write_policy": {"mode": "forbid"},
        }
    )


def _resolved_execution_mode(strategy_path: Path) -> str:
    strategy = StrategyConfig.from_dict(load_structured_file(strategy_path))
    contract = build_analysis_review_contract(_task(), strategy)
    return contract.trust_review.execution_mode


def _scenario_names(scenarios: list[dict[str, object]]) -> list[str]:
    return [str(scenario["name"]) for scenario in scenarios]


def test_focus_gate_adjudicate_examples_clone_base_analysis_review_strategies():
    cases = [
        (
            Path(
                "examples/harness/strategies/analysis_review_bounded_codex_claude.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-bounded-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude-focus-gate-adjudicate",
        ),
    ]

    for base_path, derived_path, expected_name in cases:
        base_strategy = load_structured_file(base_path)
        derived_strategy = load_structured_file(derived_path)

        expected_strategy = dict(base_strategy)
        expected_strategy["name"] = expected_name
        expected_strategy["focus_gate"] = {
            "enabled": True,
            "default_path": "adjudicate",
        }

        assert derived_strategy == expected_strategy


def test_canonical_trust_examples_match_attestation_source_of_truth():
    cases = [
        (
            Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
            Path(
                "examples/harness/strategies/analysis_review_trust_attestation_codex_claude.yaml"
            ),
            "analysis-review-trust-codex-claude",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_attestation_codex_claude_focus_gate_deliberate.yaml"
            ),
            "analysis-review-trust-codex-claude-focus-gate-deliberate",
        ),
    ]

    for canonical_path, source_path, expected_name in cases:
        canonical_strategy = load_structured_file(canonical_path)
        source_strategy = load_structured_file(source_path)

        expected_strategy = dict(source_strategy)
        expected_strategy["name"] = expected_name

        assert canonical_strategy == expected_strategy
        assert _resolved_execution_mode(canonical_path) == "attestation_over_bounded"


def test_explicit_legacy_trust_compatibility_examples_resolve_legacy_full_review():
    cases = [
        (
            Path("examples/harness/strategies/analysis_review_trust_codex_claude.yaml"),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude_focus_gate_adjudicate.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude-focus-gate-adjudicate",
        ),
        (
            Path(
                "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml"
            ),
            Path(
                "examples/harness/strategies/analysis_review_trust_legacy_codex_claude_focus_gate_deliberate.yaml"
            ),
            "analysis-review-trust-legacy-codex-claude-focus-gate-deliberate",
        ),
    ]

    for canonical_path, compatibility_path, expected_name in cases:
        canonical_strategy = load_structured_file(canonical_path)
        compatibility_strategy = load_structured_file(compatibility_path)

        expected_strategy = dict(canonical_strategy)
        expected_strategy["name"] = expected_name
        expected_strategy["trust_review"] = {"execution_mode": "legacy_full_review"}

        assert compatibility_strategy == expected_strategy
        assert _resolved_execution_mode(compatibility_path) == "legacy_full_review"


def test_analysis_review_entry_points_document_attestation_first_canonical_trust():
    examples_readme = Path("examples/README.md").read_text(encoding="utf-8")
    root_readme = Path("README.md").read_text(encoding="utf-8")
    run_script = Path("examples/harness/run_analysis_review_codex_claude.sh").read_text(
        encoding="utf-8"
    )
    canonical_template = Path(
        "examples/harness/live_acceptance/focus_gate_acceptance.template.yaml"
    ).read_text(encoding="utf-8")
    local_template = Path(
        "examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml"
    ).read_text(encoding="utf-8")
    compatibility_template = Path(
        "examples/harness/live_acceptance/m2_focus_gate_local.template.yaml"
    ).read_text(encoding="utf-8")

    canonical_trust_path = (
        "examples/harness/strategies/"
        "analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
    )

    assert canonical_trust_path in examples_readme
    assert "attestation-first" in examples_readme
    assert "analysis_review_trust_legacy_*" in examples_readme
    assert "legacy_full_review" in examples_readme
    assert "[Examples](examples/README.md)" in root_readme
    assert canonical_trust_path in run_script
    assert "attestation-first" in run_script
    assert "analysis_review_trust_legacy_*" in run_script
    assert "poetry run python -m anvil.cli harness-run" in run_script
    assert canonical_trust_path in canonical_template
    assert canonical_trust_path in local_template
    assert canonical_trust_path in compatibility_template
    assert "attestation-first" in canonical_template
    assert "attestation-first" in local_template
    assert "attestation-first" in compatibility_template
    assert "analysis_review_trust_legacy_*" in canonical_template
    assert "analysis_review_trust_legacy_*" in local_template
    assert "analysis_review_trust_legacy_*" in compatibility_template


def test_focus_gate_live_acceptance_templates_still_target_canonical_trust_example():
    canonical_manifest = load_structured_file(
        Path("examples/harness/live_acceptance/focus_gate_acceptance.template.yaml")
    )
    local_manifest = load_structured_file(
        Path("examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml")
    )
    compatibility_manifest = load_structured_file(
        Path("examples/harness/live_acceptance/m2_focus_gate_local.template.yaml")
    )

    canonical_shards = {
        shard["name"]: shard["scenarios"] for shard in canonical_manifest["shards"]
    }
    seam_deliberate = canonical_shards["seam-deliberate"]
    assert _scenario_names(seam_deliberate) == [
        "deliberate-refined-success",
        "deliberate-refinement-exhausted",
        "stale-rerun",
    ]
    assert seam_deliberate[0]["expected_decision_state"] == "selected"
    assert seam_deliberate[0]["expect_proposer_artifacts"] is True
    assert seam_deliberate[0]["expect_downstream_bridge"] is True
    assert seam_deliberate[1]["task"] == (
        "examples/harness/tasks/recommend_automation_improvements_never_ask.yaml"
    )
    assert seam_deliberate[1]["expected_decision_state"] == "no_viable_focus"
    assert seam_deliberate[1]["expect_proposer_artifacts"] is False
    assert seam_deliberate[1]["expect_downstream_bridge"] is False
    assert _scenario_names(canonical_shards["artifact-deliberate"]) == [
        "artifact-deliberate-ambiguity",
        "artifact-never-ask",
        "artifact-stale-rerun",
    ]

    local_seam_deliberate = [
        scenario
        for scenario in local_manifest["scenarios"]
        if scenario["expected_gate_path"] == "deliberate"
        and scenario["expected_focus_type"] == "seam"
    ]
    assert _scenario_names(local_seam_deliberate) == [
        "deliberate-refined-success",
        "deliberate-refinement-exhausted",
        "stale-rerun",
    ]

    assert (
        canonical_manifest["default_task"]
        == "examples/harness/tasks/recommend_automation_improvements.yaml"
    )
    assert local_manifest["task"] == canonical_manifest["default_task"]
    assert compatibility_manifest["task"] == canonical_manifest["default_task"]
    assert compatibility_manifest["strategies"] == {
        "bounded": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
        "trust": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
    }
    assert (
        _resolved_execution_mode(Path(compatibility_manifest["strategies"]["trust"]))
        == "attestation_over_bounded"
    )


def test_m2_focus_gate_fixture_wiring_triads_resolve_task_strategy_and_workspace():
    triads = load_structured_file(
        Path("tests/fixtures/harness/m2_focus_gate_fixture_wiring/triads.yaml")
    )

    assert triads["fixture_namespace"] == "m2_focus_gate_fixture_wiring"
    assert triads["fixture_purpose"] == "seam_regression_only_wiring_coverage"

    for case in triads["cases"]:
        task_path = Path(case["task"])
        strategy_path = Path(case["strategy"])
        workspace_path = Path(case["workspace"])

        assert task_path.exists(), case["name"]
        assert strategy_path.exists(), case["name"]
        assert workspace_path.exists(), case["name"]

        task = load_structured_file(task_path)
        strategy = load_structured_file(strategy_path)

        assert task["id"] == "recommend_automation_improvements"
        assert task["task_kind"] == "analysis_review"
        assert strategy["kind"] == case["expected_strategy_kind"]
        assert strategy["focus_gate"] == {
            "enabled": True,
            "default_path": "adjudicate",
        }

        for workspace_ref in task["files_hint"]:
            matches = list(workspace_path.glob(workspace_ref))
            assert matches, (case["name"], workspace_ref)


def test_example_strategies_resolve_to_expected_internal_graph_family_metadata():
    cases = [
        (
            "examples/harness/strategies/single_pass_codex.yaml",
            "single_pass",
            "single_pass",
            ["solver"],
        ),
        (
            "examples/harness/strategies/pfr_codex_claude.yaml",
            "pfr_v1",
            "pfr_v1",
            ["proposer", "falsifier", "patcher"],
        ),
        (
            "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
            "analysis_review_bounded_v1",
            "analysis_review_v1",
            ["focus_gate", "proposer", "critic", "reviser", "auditor"],
        ),
        (
            "examples/harness/strategies/analysis_review_trust_codex_claude.yaml",
            "analysis_review_trust_v1",
            "analysis_review_v1",
            ["proposer", "critic", "reviser", "auditor", "attestation_auditor"],
        ),
    ]

    for path, expected_kind, expected_runtime_target, expected_stage_ids in cases:
        strategy = load_structured_file(Path(path))
        spec = build_strategy_graph_spec(expected_kind, strategy).to_dict()

        assert spec["subset"] == STRATEGY_GRAPH_SUBSET
        assert spec["strategy_kind"] == expected_kind
        assert spec["runtime_target"] == expected_runtime_target
        assert [stage["stage_id"] for stage in spec["stages"]] == expected_stage_ids
