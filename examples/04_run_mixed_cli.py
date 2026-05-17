#!/usr/bin/env python
"""
Runs Forge with Codex CLI for execution/refinement and Claude Code for critique/review.

Requires:
  - Codex CLI installed (`codex`) or FORGE_CODEX_BIN set
  - Claude Code installed (`claude`) or FORGE_CLAUDE_BIN set
  - Authentication already configured for both CLIs
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    codex_bin = os.getenv("FORGE_CODEX_BIN", "codex")
    claude_bin = os.getenv("FORGE_CLAUDE_BIN", "claude")
    missing = [
        binary for binary in (codex_bin, claude_bin) if shutil.which(binary) is None
    ]
    if missing:
        print("Missing CLI binaries: " + ", ".join(missing))
        return 2

    return subprocess.call(
        [
            sys.executable,
            "-m",
            "anvil",
            "run",
            "Review the current project architecture and propose a safer retry policy.",
            "--execute",
            "codex_cli",
            "--critique",
            "claude_code",
            "--refine",
            "codex_cli",
            "--review",
            "claude_code",
            "--reflect",
            "claude_code",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
