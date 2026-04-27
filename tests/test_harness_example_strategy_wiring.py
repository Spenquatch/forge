from __future__ import annotations

from pathlib import Path

from anvil.harness.files import load_structured_file


def test_focus_gate_adjudicate_examples_clone_base_analysis_review_strategies():
    cases = [
        (
            Path("examples/harness/strategies/analysis_review_bounded_codex_claude.yaml"),
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


def test_m2_focus_gate_live_triads_resolve_task_strategy_and_workspace():
    triads = load_structured_file(
        Path("tests/fixtures/harness/m2_focus_gate_live/triads.yaml")
    )

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
            assert (workspace_path / workspace_ref).exists(), (
                case["name"],
                workspace_ref,
            )
