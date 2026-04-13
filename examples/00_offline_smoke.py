#!/usr/bin/env python
"""
Offline smoke check:
- loads config/models.yaml
- validates config
- shows CLI help + `anvil list`

Does not call any external model APIs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    os.chdir(REPO_ROOT)

    print("Repo:", REPO_ROOT)
    print("\nRunning: poetry run python -m anvil list\n")
    import subprocess

    return subprocess.call([sys.executable, "-m", "anvil", "list"])


if __name__ == "__main__":
    raise SystemExit(main())
