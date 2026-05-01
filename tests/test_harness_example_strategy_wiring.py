from __future__ import annotations

from pathlib import Path

from anvil.harness.files import load_structured_file


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


def test_analysis_review_entry_points_reference_focus_gate_adjudicate_examples():
    examples_readme = Path("examples/README.md").read_text(encoding="utf-8")
    root_readme = Path("README.md").read_text(encoding="utf-8")
    run_script = Path("examples/harness/run_analysis_review_codex_claude.sh").read_text(
        encoding="utf-8"
    )

    bounded_path = (
        "examples/harness/strategies/"
        "analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml"
    )
    trust_path = (
        "examples/harness/strategies/"
        "analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml"
    )

    assert bounded_path in examples_readme
    assert trust_path in examples_readme
    assert bounded_path in root_readme
    assert trust_path in root_readme
    assert bounded_path in run_script
    assert "scripts/run_focus_gate_acceptance.py" in examples_readme
    assert "scripts/run_focus_gate_acceptance.py" in root_readme
    assert "scripts/run_m2_focus_gate_live_acceptance.py" in examples_readme
    assert "scripts/run_m2_focus_gate_live_acceptance.py" in root_readme
    assert "seam-regression-only wiring coverage" in examples_readme
    assert "seam-regression-only wiring coverage" in root_readme


def test_focus_gate_live_acceptance_templates_cover_canonical_and_compatibility_surfaces():
    canonical_manifest = load_structured_file(
        Path(
            "examples/harness/live_acceptance/focus_gate_acceptance_local.template.yaml"
        )
    )
    compatibility_manifest = load_structured_file(
        Path("examples/harness/live_acceptance/m2_focus_gate_local.template.yaml")
    )

    assert (
        canonical_manifest["task"]
        == "examples/harness/tasks/recommend_automation_improvements.yaml"
    )
    assert canonical_manifest["scenarios"] == [
        {
            "name": "bounded",
            "strategy": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
            "expected_gate_path": "adjudicate",
            "expected_focus_type": "seam",
            "expected_decision_state": "selected",
            "expect_proposer_artifacts": True,
            "expect_downstream_bridge": True,
        },
        {
            "name": "trust",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
            "expected_gate_path": "adjudicate",
            "expected_focus_type": "seam",
            "expected_decision_state": "selected",
            "expect_proposer_artifacts": True,
            "expect_downstream_bridge": True,
        },
        {
            "name": "deliberate-ambiguity",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml",
            "expected_gate_path": "deliberate",
            "expected_focus_type": "seam",
            "expected_decision_state": "clarification_requested",
            "expect_proposer_artifacts": False,
            "expect_downstream_bridge": False,
        },
        {
            "name": "never-ask",
            "task": "examples/harness/tasks/recommend_automation_improvements_never_ask.yaml",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml",
            "expected_gate_path": "deliberate",
            "expected_focus_type": "seam",
            "expected_decision_state": "no_viable_focus",
            "expect_proposer_artifacts": False,
            "expect_downstream_bridge": False,
        },
        {
            "name": "stale-rerun",
            "task": "examples/harness/tasks/recommend_automation_improvements_stale_focus_gate_answer.yaml",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml",
            "expected_gate_path": "deliberate",
            "expected_focus_type": "seam",
            "expected_decision_state": "clarification_requested",
            "expect_proposer_artifacts": False,
            "expect_downstream_bridge": False,
            "expected_warning_substrings": ["went stale"],
        },
        {
            "name": "artifact-bounded",
            "task": "examples/harness/tasks/recommend_release_workflow_artifact_improvements.yaml",
            "strategy": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
            "expected_gate_path": "adjudicate",
            "expected_focus_type": "artifact",
            "expected_decision_state": "selected",
            "expect_proposer_artifacts": True,
            "expect_downstream_bridge": True,
        },
        {
            "name": "artifact-trust",
            "task": "examples/harness/tasks/recommend_release_workflow_artifact_improvements.yaml",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
            "expected_gate_path": "adjudicate",
            "expected_focus_type": "artifact",
            "expected_decision_state": "selected",
            "expect_proposer_artifacts": True,
            "expect_downstream_bridge": True,
        },
        {
            "name": "artifact-deliberate-ambiguity",
            "task": "examples/harness/tasks/recommend_release_workflow_artifact_improvements.yaml",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml",
            "expected_gate_path": "deliberate",
            "expected_focus_type": "artifact",
            "expected_decision_state": "clarification_requested",
            "expect_proposer_artifacts": False,
            "expect_downstream_bridge": False,
        },
        {
            "name": "artifact-never-ask",
            "task": "examples/harness/tasks/recommend_release_workflow_artifact_improvements_never_ask.yaml",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml",
            "expected_gate_path": "deliberate",
            "expected_focus_type": "artifact",
            "expected_decision_state": "no_viable_focus",
            "expect_proposer_artifacts": False,
            "expect_downstream_bridge": False,
        },
        {
            "name": "artifact-stale-rerun",
            "task": "examples/harness/tasks/recommend_release_workflow_artifact_improvements_stale_rerun_answer.yaml",
            "strategy": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_deliberate.yaml",
            "expected_gate_path": "deliberate",
            "expected_focus_type": "artifact",
            "expected_decision_state": "clarification_requested",
            "expect_proposer_artifacts": False,
            "expect_downstream_bridge": False,
            "expected_warning_substrings": ["went stale"],
        },
    ]

    assert compatibility_manifest["task"] == canonical_manifest["task"]
    assert compatibility_manifest["strategies"] == {
        "bounded": "examples/harness/strategies/analysis_review_bounded_codex_claude_focus_gate_adjudicate.yaml",
        "trust": "examples/harness/strategies/analysis_review_trust_codex_claude_focus_gate_adjudicate.yaml",
    }


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
