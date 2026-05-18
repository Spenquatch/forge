from pathlib import Path

ROOT = Path(".")
README = ROOT / "README.md"
EXAMPLES_README = ROOT / "examples" / "README.md"
DOCS_ROADMAP = ROOT / "docs" / "roadmap.md"
CONTRIBUTING = ROOT / "docs" / "contributing.md"
PM_README = ROOT / "docs" / "project_management" / "README.md"

CANONICAL_PLANNING_COMMAND = """poetry run python -m anvil.cli harness-run \\
  --task examples/harness/tasks/deterministic_feature_planning_success.yaml \\
  --strategy examples/harness/strategies/deterministic_feature_planning_v1.yaml \\
  --out-root .forge-harness-runs \\
  --json"""

BANNED_DOC_LINKS = [
    "docs/installation.md",
    "docs/getting_started.md",
    "docs/architecture_overview.md",
    "docs/leadership_architecture.md",
    "docs/configuration_system.md",
    "docs/provider_system.md",
    "docs/provider_support.md",
    "docs/role_based_configuration.md",
    "docs/testing_guide.md",
    "docs/checkpointing.md",
]


def test_readme_links_only_current_canonical_docs():
    readme = README.read_text(encoding="utf-8")

    assert "[Contributing guide](docs/contributing.md)" in readme
    assert "[Analysis-review contract](docs/analysis_review_contract.md)" in readme
    assert "[Roadmap](docs/roadmap.md)" in readme
    for banned_link in BANNED_DOC_LINKS:
        assert banned_link not in readme


def test_docs_roadmap_is_canonical():
    docs_roadmap = DOCS_ROADMAP.read_text(encoding="utf-8")

    assert "## Current focus" in docs_roadmap
    assert "## Future directions" in docs_roadmap
    assert not (ROOT / "roadmap.md").exists()


def test_contributor_and_project_management_indexes_exist():
    assert CONTRIBUTING.is_file()
    assert PM_README.is_file()


def test_planning_docs_surface_uses_repo_root_command_and_bounded_language():
    readme = README.read_text(encoding="utf-8")
    examples_readme = EXAMPLES_README.read_text(encoding="utf-8")
    contributing = CONTRIBUTING.read_text(encoding="utf-8")

    for text in (readme, examples_readme, contributing):
        assert CANONICAL_PLANNING_COMMAND in text

    assert "omitting `--workspace` uses the current working directory" in readme
    assert "omitting `--workspace` uses the current working directory" in examples_readme
    assert "omitting `--workspace` defaults to the current working directory" in contributing

    assert "bounded deterministic existing-repo planning runs" in readme
    assert "one existing repo" in readme
    assert "clarification_needed" in readme
    assert "failed" in readme
    assert "publish `summary.json` only with truthful coverage payloads" in readme

    assert "codex_cli" in readme
    assert "claude_code" in readme
    assert "FORGE_CODEX_BIN" in readme
    assert "FORGE_CLAUDE_BIN" in readme

    assert "explicit stop-path fixtures" in examples_readme
    assert "summary.json` only with truthful coverage payloads" in examples_readme
    assert "codex_cli" in examples_readme
    assert "claude_code" in examples_readme
    assert "FORGE_CODEX_BIN" in examples_readme
    assert "FORGE_CLAUDE_BIN" in examples_readme


def test_history_and_future_files_live_under_project_management():
    assert (
        ROOT / "docs/project_management/history/feature_specification_vnext_roadmap.md"
    ).is_file()
    assert (
        ROOT / "docs/project_management/history/notes/CLI_PROVIDER_UPDATE_NOTES.md"
    ).is_file()
    assert (
        ROOT
        / "docs/project_management/history/notes/FORGE_HARNESS_SURFACE_UPDATE_NOTES.md"
    ).is_file()
    assert (ROOT / "docs/project_management/plans/history/PLAN_M3.md").is_file()
    assert (ROOT / "docs/project_management/plans/history/ORCH_PLAN.md").is_file()
    assert (ROOT / "docs/project_management/future/TODOS.md").is_file()


def test_root_history_files_are_removed():
    assert not (ROOT / "PLAN_M3.md").exists()
    assert not (ROOT / "CLI_PROVIDER_UPDATE_NOTES.md").exists()
    assert not (ROOT / "FORGE_HARNESS_SURFACE_UPDATE_NOTES.md").exists()
    assert not (ROOT / "TODOS.md").exists()
