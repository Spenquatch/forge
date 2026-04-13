#!/usr/bin/env python
"""
Runs a simple task using the Codex CLI provider.

Requires:
  - Codex CLI installed (`codex`) or FORGE_CODEX_BIN set
  - Codex authentication already configured (for example via `codex login`)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main() -> int:
    binary = os.getenv("FORGE_CODEX_BIN", "codex")
    if shutil.which(binary) is None:
        print(f"Missing Codex CLI binary: {binary}")
        return 2

    return subprocess.call(
        [
            sys.executable,
            "-m",
            "anvil",
            "run",
            "Summarize the repository and suggest the top three next engineering improvements.",
            "--provider",
            "codex_cli",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
