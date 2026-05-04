#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_focus_gate_acceptance as _CANONICAL

DEFAULT_CONFIG_PATH = _CANONICAL.LEGACY_DEFAULT_CONFIG_PATH


def main(argv: Sequence[str] | None = None) -> int:
    return _CANONICAL.main(argv, default_config_path=DEFAULT_CONFIG_PATH)


if __name__ == "__main__":
    raise SystemExit(main())
