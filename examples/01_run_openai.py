#!/usr/bin/env python
"""
Runs a simple task using the OpenAI provider.

Requires:
  OPENAI_API_KEY
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY; set it in your environment or .env and retry.")
        return 2

    return subprocess.call(
        [
            sys.executable,
            "-m",
            "anvil",
            "run",
            "Write a haiku about test automation",
            "--provider",
            "openai",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
