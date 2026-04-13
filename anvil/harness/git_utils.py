from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import WorkspaceWritePolicy


def _run_git(cwd: str | Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _normalize_relpath(path: str) -> str:
    value = path.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def _normalize_ignored_rel_paths(paths: list[str] | None) -> list[str]:
    return [value for value in (_normalize_relpath(p) for p in (paths or [])) if value]


def _path_is_ignored(rel_path: str, ignored_rel_paths: list[str]) -> bool:
    path = _normalize_relpath(rel_path)
    for ignored in ignored_rel_paths:
        if path == ignored or path.startswith(f"{ignored}/"):
            return True
    return False


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _capture_file_hashes(cwd: str | Path, rel_paths: list[str]) -> dict[str, str]:
    root = Path(cwd)
    hashes: dict[str, str] = {}
    for rel_path in sorted(set(_normalize_relpath(p) for p in rel_paths if str(p).strip())):
        full_path = root / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue
        hashes[rel_path] = _hash_file(full_path)
    return hashes


def parse_status_porcelain(status_porcelain: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw_line in status_porcelain.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("?? "):
            path = _normalize_relpath(raw_line[3:])
            entries.append(
                {
                    "raw": raw_line,
                    "x": "?",
                    "y": "?",
                    "path": path,
                    "orig_path": None,
                    "kind": "untracked",
                }
            )
            continue
        if raw_line.startswith("!! "):
            continue

        xy = raw_line[:2]
        payload = raw_line[3:]
        orig_path = None
        path = payload
        if " -> " in payload:
            orig_path, path = payload.split(" -> ", 1)
        path = _normalize_relpath(path)
        orig_path = None if orig_path is None else _normalize_relpath(orig_path)
        kind = "renamed" if "R" in xy else "changed"
        entries.append(
            {
                "raw": raw_line,
                "x": xy[0],
                "y": xy[1],
                "path": path,
                "orig_path": orig_path,
                "kind": kind,
            }
        )
    return entries


def _filter_status_entries(
    entries: list[dict[str, Any]],
    ignored_rel_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    ignored = _normalize_ignored_rel_paths(ignored_rel_paths)
    if not ignored:
        return entries
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        path = entry.get("path") or ""
        orig_path = entry.get("orig_path") or ""
        if _path_is_ignored(path, ignored):
            continue
        if orig_path and _path_is_ignored(orig_path, ignored):
            continue
        filtered.append(entry)
    return filtered


def is_git_repo(cwd: str | Path) -> bool:
    result = _run_git(cwd, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip() == "true"


def capture_git_snapshot(
    cwd: str | Path,
    ignored_rel_paths: list[str] | None = None,
) -> dict[str, Any]:
    ignored = _normalize_ignored_rel_paths(ignored_rel_paths)
    if not is_git_repo(cwd):
        return {"is_git": False, "ignored_rel_paths": ignored}

    branch = _run_git(cwd, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    head = _run_git(cwd, ["rev-parse", "HEAD"])
    status = _run_git(cwd, ["status", "--porcelain=v1"])
    diff_stat = _run_git(cwd, ["diff", "--stat"])
    diff_name_status = _run_git(cwd, ["diff", "--name-status"])
    status_entries = _filter_status_entries(parse_status_porcelain(status.stdout), ignored)
    dirty_hash_paths: list[str] = []
    for entry in status_entries:
        dirty_hash_paths.append(str(entry.get("path") or ""))
        if entry.get("orig_path"):
            dirty_hash_paths.append(str(entry["orig_path"]))
    dirty_file_hashes = _capture_file_hashes(cwd, dirty_hash_paths)
    return {
        "is_git": True,
        "branch": branch.stdout.strip() if branch.returncode == 0 else "DETACHED",
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "status_porcelain": status.stdout,
        "status_entries": status_entries,
        "dirty_file_hashes": dirty_file_hashes,
        "diff_stat": diff_stat.stdout,
        "diff_name_status": diff_name_status.stdout,
        "ignored_rel_paths": ignored,
    }


def _walk_workspace_files(
    cwd: str | Path,
    ignored_rel_paths: list[str] | None = None,
) -> dict[str, str]:
    root = Path(cwd)
    ignored = _normalize_ignored_rel_paths(ignored_rel_paths)
    file_hashes: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        rel_dir = _normalize_relpath(str(current_dir.relative_to(root)))
        if rel_dir == ".git" or rel_dir.startswith(".git/"):
            dirnames[:] = []
            continue
        dirnames[:] = [
            name
            for name in dirnames
            if not _path_is_ignored(
                _normalize_relpath(str((current_dir / name).relative_to(root))),
                ignored,
            )
            and name != ".git"
        ]
        for filename in filenames:
            rel_path = _normalize_relpath(str((current_dir / filename).relative_to(root)))
            if _path_is_ignored(rel_path, ignored):
                continue
            full_path = root / rel_path
            if full_path.is_file():
                file_hashes[rel_path] = _hash_file(full_path)
    return file_hashes


def capture_non_git_workspace_state(
    cwd: str | Path,
    ignored_rel_paths: list[str] | None = None,
) -> dict[str, Any]:
    ignored = _normalize_ignored_rel_paths(ignored_rel_paths)
    file_hashes = _walk_workspace_files(cwd, ignored)
    return {
        "is_git": False,
        "ignored_rel_paths": ignored,
        "file_hashes": file_hashes,
    }


def changed_files(snapshot: dict[str, Any]) -> list[str]:
    if not snapshot.get("is_git"):
        return []
    if snapshot.get("status_entries"):
        result: list[str] = []
        for entry in snapshot["status_entries"]:
            if entry.get("kind") == "renamed" and entry.get("orig_path"):
                result.append(f"{entry['orig_path']} -> {entry['path']}")
            else:
                result.append(str(entry.get("path") or "").strip())
        return [value for value in result if value]

    result = []
    for line in snapshot.get("diff_name_status", "").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            result.append(parts[1].strip())
    return result


def git_snapshot_is_dirty(snapshot: dict[str, Any]) -> bool:
    if not snapshot.get("is_git"):
        return False
    return bool(snapshot.get("status_entries"))


def _entry_signature(entry: dict[str, Any]) -> tuple[str, str, str | None, str | None]:
    return (
        str(entry.get("x") or ""),
        str(entry.get("y") or ""),
        None if entry.get("orig_path") is None else str(entry.get("orig_path")),
        None if entry.get("kind") is None else str(entry.get("kind")),
    )


def _classify_entry(entry: dict[str, Any]) -> str:
    if entry.get("kind") == "untracked":
        return "add"
    x = str(entry.get("x") or "")
    y = str(entry.get("y") or "")
    if entry.get("kind") == "renamed" or "R" in {x, y} or entry.get("orig_path"):
        return "rename"
    if "D" in {x, y}:
        return "delete"
    if "A" in {x, y}:
        return "add"
    return "modify"


def _path_allowed(policy: WorkspaceWritePolicy, rel_path: str) -> bool:
    path = _normalize_relpath(rel_path)
    denied_patterns = [p for p in policy.denied_paths if str(p).strip()]
    allowed_patterns = [p for p in policy.allowed_paths if str(p).strip()]
    if any(fnmatch.fnmatchcase(path, pattern) for pattern in denied_patterns):
        return False
    if not allowed_patterns:
        return True
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in allowed_patterns)


def _summarize_items(items: list[str], limit: int = 8) -> str:
    if not items:
        return "none"
    if len(items) <= limit:
        return ", ".join(items)
    visible = ", ".join(items[:limit])
    return f"{visible}, ... (+{len(items) - limit} more)"


def evaluate_workspace_write_policy(
    *,
    cwd: str | Path,
    initial_git_snapshot: dict[str, Any] | None,
    current_git_snapshot: dict[str, Any] | None,
    initial_non_git_state: dict[str, Any] | None,
    current_non_git_state: dict[str, Any] | None,
    policy: WorkspaceWritePolicy,
    final: bool,
    checkpoint: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "checkpoint": checkpoint,
        "final": final,
        "policy_mode": policy.mode,
        "touched_files": [],
        "modified_files": [],
        "added_files": [],
        "deleted_files": [],
        "renamed_files": [],
        "new_untracked_files": [],
        "violations": [],
        "notes": [],
        "ok": True,
    }

    if current_git_snapshot and current_git_snapshot.get("is_git"):
        initial_entries = {
            str(entry.get("path") or ""): entry
            for entry in (initial_git_snapshot or {}).get("status_entries", [])
            if str(entry.get("path") or "").strip()
        }
        current_entries = {
            str(entry.get("path") or ""): entry
            for entry in current_git_snapshot.get("status_entries", [])
            if str(entry.get("path") or "").strip()
        }
        initial_hashes = dict((initial_git_snapshot or {}).get("dirty_file_hashes", {}))
        current_hashes = dict(current_git_snapshot.get("dirty_file_hashes", {}))

        renamed_from_paths: set[str] = set()
        touched_files: set[str] = set()
        modified_files: set[str] = set()
        added_files: set[str] = set()
        deleted_files: set[str] = set()
        new_untracked_files: set[str] = set()
        renamed_files: list[dict[str, str]] = []

        for path, entry in current_entries.items():
            initial_entry = initial_entries.get(path)
            current_hash = current_hashes.get(path)
            initial_hash = initial_hashes.get(path)
            touched = False
            if initial_entry is None:
                touched = True
            else:
                if _entry_signature(initial_entry) != _entry_signature(entry):
                    touched = True
                elif initial_hash != current_hash:
                    touched = True
            if not touched:
                continue

            classification = _classify_entry(entry)
            if classification == "rename":
                renamed_files.append(
                    {
                        "from": str(entry.get("orig_path") or ""),
                        "to": path,
                    }
                )
                if entry.get("orig_path"):
                    renamed_from_paths.add(str(entry["orig_path"]))
                touched_files.add(f"{entry.get('orig_path') or '?'} -> {path}")
            elif classification == "delete":
                deleted_files.add(path)
                touched_files.add(path)
            elif classification == "add":
                added_files.add(path)
                touched_files.add(path)
                if entry.get("kind") == "untracked":
                    new_untracked_files.add(path)
            else:
                modified_files.add(path)
                touched_files.add(path)

        for path, entry in initial_entries.items():
            if path in current_entries:
                continue
            if path in renamed_from_paths:
                continue
            touched_files.add(path)
            full_path = Path(cwd) / path
            if not full_path.exists():
                deleted_files.add(path)
            else:
                modified_files.add(path)
                result["notes"].append(
                    f"{path} was dirty at start and no longer appears in git status; it was still changed relative to the initial workspace snapshot."
                )

        result.update(
            {
                "touched_files": sorted(touched_files),
                "modified_files": sorted(modified_files),
                "added_files": sorted(added_files),
                "deleted_files": sorted(deleted_files),
                "renamed_files": sorted(renamed_files, key=lambda item: (item.get("from", ""), item.get("to", ""))),
                "new_untracked_files": sorted(new_untracked_files),
            }
        )
    else:
        initial_hashes = dict((initial_non_git_state or {}).get("file_hashes", {}))
        current_hashes = dict((current_non_git_state or {}).get("file_hashes", {}))
        initial_paths = set(initial_hashes)
        current_paths = set(current_hashes)
        added_files = sorted(current_paths - initial_paths)
        deleted_files = sorted(initial_paths - current_paths)
        modified_files = sorted(
            path for path in (initial_paths & current_paths) if initial_hashes[path] != current_hashes[path]
        )
        result.update(
            {
                "touched_files": sorted(set(added_files) | set(deleted_files) | set(modified_files)),
                "modified_files": modified_files,
                "added_files": added_files,
                "deleted_files": deleted_files,
                "renamed_files": [],
                "new_untracked_files": added_files,
                "notes": result["notes"] + [
                    "Workspace policy was enforced with a full file-hash snapshot because the workspace is not a git repository."
                ],
            }
        )

    violations: list[str] = []
    touched_files = list(result["touched_files"])
    added_files = list(result["added_files"])
    deleted_files = list(result["deleted_files"])
    new_untracked_files = list(result["new_untracked_files"])
    renamed_files = list(result["renamed_files"])

    if policy.mode == "forbid":
        if touched_files:
            violations.append(
                "Workspace writes are forbidden for this task, but changes were detected: "
                + _summarize_items(touched_files)
            )
    else:
        disallowed_paths: list[str] = []
        for path in result["modified_files"] + result["added_files"] + result["deleted_files"]:
            if not _path_allowed(policy, path):
                disallowed_paths.append(path)
        for rename in renamed_files:
            source = str(rename.get("from") or "")
            target = str(rename.get("to") or "")
            if not _path_allowed(policy, source) or not _path_allowed(policy, target):
                disallowed_paths.append(f"{source} -> {target}")
        if disallowed_paths:
            violations.append(
                "Changes touched paths outside workspace_write_policy.allowed_paths or inside denied_paths: "
                + _summarize_items(sorted(disallowed_paths))
            )
        if new_untracked_files and not policy.allow_untracked:
            violations.append(
                "New untracked files are not allowed by workspace_write_policy: "
                + _summarize_items(new_untracked_files)
            )
        if deleted_files and not policy.allow_deletions:
            violations.append(
                "File deletions are not allowed by workspace_write_policy: "
                + _summarize_items(deleted_files)
            )
        if renamed_files and not policy.allow_renames:
            rename_display = [f"{item.get('from')} -> {item.get('to')}" for item in renamed_files]
            violations.append(
                "File renames are not allowed by workspace_write_policy: "
                + _summarize_items(rename_display)
            )
        if policy.max_touched_files is not None and len(touched_files) > policy.max_touched_files:
            violations.append(
                f"workspace_write_policy.max_touched_files={policy.max_touched_files}, "
                f"but {len(touched_files)} file(s) were touched."
            )
        if final and policy.requires_workspace_writes() and not touched_files:
            violations.append(
                "This task requires a workspace patch, but no target-workspace file changes were detected."
            )

    result["violations"] = violations
    result["ok"] = not violations
    return result


def render_git_snapshot(snapshot: dict[str, Any], max_chars: int = 4000) -> str:
    if not snapshot.get("is_git"):
        return "Current workspace is not a Git repository."

    status_entries = snapshot.get("status_entries", [])
    status_text = "\n".join(str(entry.get("raw") or "").rstrip() for entry in status_entries if entry.get("raw"))
    diff_stat = snapshot.get("diff_stat", "").strip()
    changed = changed_files(snapshot)

    parts = [
        f"Branch: {snapshot.get('branch')}",
        f"HEAD: {snapshot.get('head')}",
        "Changed files: " + (", ".join(changed) if changed else "none"),
        "Git status:\n" + (status_text or "clean"),
        "Git diff --stat:\n" + (diff_stat or "no unstaged diff"),
    ]
    text = "\n\n".join(parts)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"
