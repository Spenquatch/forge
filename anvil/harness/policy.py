from __future__ import annotations

"""Workspace write-policy helpers for the harness surface."""

from typing import Any

from .git_utils import (
    capture_git_snapshot,
    capture_non_git_workspace_state,
    evaluate_workspace_write_policy,
    git_snapshot_is_dirty,
)

__all__ = [
    "capture_git_snapshot",
    "capture_non_git_workspace_state",
    "evaluate_workspace_write_policy",
    "git_snapshot_is_dirty",
    "classify_policy_verdict",
]


def classify_policy_verdict(policy_check: dict[str, Any] | None) -> str:
    if not policy_check:
        return "pass"
    return "policy_violation" if policy_check.get("violations") else "pass"
