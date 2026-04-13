#!/usr/bin/env python
"""
Runs a task with per-role provider overrides.

Requires:
  OPENAI_API_KEY and ANTHROPIC_API_KEY
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print("Missing: " + ", ".join(missing))
        return 2

    return subprocess.call(
        [
            sys.executable,
            "-m",
            "anvil",
            "run",
            "Explain binary search in 5 bullet points",
            "--execute",
            "openai",
            "--critique",
            "anthropic",
            "--refine",
            "openai",
            "--review",
            "anthropic",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
