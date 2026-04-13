"""
Dependency audit helper for Forge (Poetry).

Generates a Markdown report that snapshots:
- Python and Poetry versions
- Top-level main/dev dependencies (locked)
- Outdated packages (locked -> latest)

Usage (from repo root):
  poetry run python scripts/deps_audit.py > /tmp/deps-audit.md
  poetry run python scripts/deps_audit.py --output docs/adr/_deps_audit.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}"
        )
    return proc.stdout.rstrip()


def _poetry(*args: str) -> str:
    return _run(["poetry", *args])


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a dependency audit report.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write Markdown output to this file instead of stdout.",
    )
    return parser.parse_args(argv)


def _render_report() -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    poetry_version = _poetry("--version")

    top_main = _poetry("show", "--top-level", "--only", "main", "--no-truncate")
    top_dev = _poetry("show", "--top-level", "--only", "dev", "--no-truncate")
    outdated = _poetry("show", "--outdated", "--no-truncate")

    return "\n".join(
        [
            "# Forge dependency audit snapshot",
            "",
            f"- Generated: `{now}`",
            f"- Python: `{sys.version.splitlines()[0]}`",
            f"- Poetry: `{poetry_version.strip()}`",
            "",
            "## Top-level (main)",
            "```",
            top_main,
            "```",
            "",
            "## Top-level (dev)",
            "```",
            top_dev,
            "```",
            "",
            "## Outdated (locked → latest)",
            "```",
            outdated,
            "```",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = _render_report()

    if args.output is None:
        sys.stdout.write(report)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
