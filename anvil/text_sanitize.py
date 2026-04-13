"""
Utilities for sanitizing model outputs before they are stored or displayed.

Forge uses "final-only" text in logs/results. Some local models emit reasoning
blocks (e.g. `<think>...</think>`) that should not be propagated to downstream
nodes or to the user.
"""

from __future__ import annotations

import os
import re

_THINK_BLOCK_RE = re.compile(r"(?is)<think>.*?</think>")
_LEADING_THINK_OPEN_RE = re.compile(r"(?is)^\s*<think>\s*")
_FINAL_MARKER_RE = re.compile(r"(?im)^\s*final\s*:\s*")
_FINAL_PLACEHOLDER_RE = re.compile(r"(?is)^<\s*(your (answer|critique|improved solution)|next steps)\s*>$")


def strip_think(text: str | None) -> str:
    """
    Remove leading `<think>...</think>` blocks from a model response.

    If the response starts with an unclosed `<think>` tag and strict mode is on,
    returns an empty string to avoid leaking chain-of-thought.
    """
    s = (text or "").strip()
    if not s:
        return ""

    if os.getenv("FORGE_STRIP_THINK", "1") != "1":
        return s

    # Remove one or more leading closed think blocks.
    while True:
        stripped = _THINK_BLOCK_RE.sub("", s, count=1).lstrip()
        if stripped == s:
            break
        s = stripped

    # If we still begin with an unclosed <think>, don't leak it.
    if _LEADING_THINK_OPEN_RE.match(s) and "</think>" not in s.lower():
        if os.getenv("FORGE_STRIP_THINK_STRICT", "1") == "1":
            return ""
        s = _LEADING_THINK_OPEN_RE.sub("", s, count=1).strip()

    return s.strip()


def extract_final(text: str | None) -> str:
    """
    Extract a "final" answer from a model response.

    Preferred formats:
    - A line starting with `FINAL:` (case-insensitive), returning everything after it.
    - Otherwise, content after the last `</think>` tag (if present).
    - Otherwise, falls back to `strip_think(...)`.
    """
    s = (text or "").strip()
    if not s:
        return ""

    if os.getenv("FORGE_FINAL_ONLY", "1") != "1":
        return strip_think(s)

    s = strip_think(s)
    matches = list(_FINAL_MARKER_RE.finditer(s))
    if matches:
        # Prefer the last FINAL: marker that is followed by non-placeholder content.
        for idx in range(len(matches) - 1, -1, -1):
            match = matches[idx]
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(s)
            candidate = s[match.end() : end].strip()
            if not candidate:
                continue
            if _FINAL_PLACEHOLDER_RE.match(candidate):
                continue
            return candidate

        # If all FINAL: sections are empty/placeholders, the model likely echoed a
        # template at the end; return the content before the last marker instead.
        prefix = s[: matches[-1].start()].strip()
        if prefix:
            return prefix
        return ""

    lower = s.lower()
    if "</think>" in lower:
        idx = lower.rfind("</think>")
        return s[idx + len("</think>") :].strip()

    return strip_think(s)
