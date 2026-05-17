from __future__ import annotations

import subprocess

from anvil.harness.git_utils import capture_workspace_file_inventory


def _git(cwd, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def test_capture_workspace_file_inventory_includes_tracked_and_untracked_git_files(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _git(workspace, "init")

    (workspace / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    (workspace / "untracked.py").write_text("print('untracked')\n", encoding="utf-8")
    (workspace / "artifacts").mkdir()
    (workspace / "artifacts" / "ignored.log").write_text("ignored\n", encoding="utf-8")

    _git(workspace, "add", "tracked.py")

    inventory = capture_workspace_file_inventory(
        workspace, ignored_rel_paths=["artifacts"]
    )

    assert inventory == {"tracked.py", "untracked.py"}


def test_capture_workspace_file_inventory_uses_workspace_walk_for_non_git_dirs(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "note.md").write_text("hello\n", encoding="utf-8")
    (workspace / "artifacts").mkdir()
    (workspace / "artifacts" / "ignored.log").write_text("ignored\n", encoding="utf-8")

    inventory = capture_workspace_file_inventory(
        workspace, ignored_rel_paths=["artifacts"]
    )

    assert inventory == {"docs/note.md"}
