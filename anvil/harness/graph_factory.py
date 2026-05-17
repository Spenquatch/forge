from __future__ import annotations

"""Factory for the new harness execution surface."""

import os

from .executor import HarnessLangGraphExecutor


def _env_with_fallback(primary: str, fallback: str, default: str) -> str:
    return os.getenv(primary) or os.getenv(fallback) or default


def create_harness_graph():
    checkpoint = _env_with_fallback(
        "FORGE_HARNESS_LG_CHECKPOINT", "FORGE_LG_CHECKPOINT", "memory"
    )
    db_path = _env_with_fallback(
        "FORGE_HARNESS_LG_DB_PATH",
        "FORGE_LG_DB_PATH",
        "forge_harness_checkpoints.db",
    )
    max_attempts = int(
        _env_with_fallback("FORGE_HARNESS_MAX_ATTEMPTS", "FORGE_LG_MAX_ATTEMPTS", "3")
    )
    return HarnessLangGraphExecutor(
        max_attempts=max_attempts,
        checkpoint=checkpoint,
        db_path=db_path,
    )
