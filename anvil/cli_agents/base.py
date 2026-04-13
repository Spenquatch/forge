from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from anvil.config_loader import ProviderCfg
from anvil.usage import TokenUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CliInvocationPlan:
    """A concrete command invocation for a CLI agent."""

    command: list[str]
    safe_command: list[str]
    stdin_text: str | None = None
    output_path: Path | None = None
    schema_path: Path | None = None


@dataclass
class CliRunResult:
    """Normalized result from a headless CLI agent run."""

    ok: bool
    exit_code: int
    text: str
    stdout_text: str
    stderr_text: str
    duration_sec: float
    command: list[str]
    resolved_binary: str
    metadata: dict[str, Any] = field(default_factory=dict)
    usage: TokenUsage | None = None
    structured_output: Any | None = None
    error: str | None = None


class BaseCliAgent(ABC):
    """Base helper for invoking headless CLI agents."""

    family: str = "cli"
    default_binary: str = ""
    binary_env_var: str | None = None

    def __init__(self, cfg: ProviderCfg):
        self.cfg = cfg

    def resolve_binary(self) -> str:
        binary_name = (
            os.getenv(self.binary_env_var, "") if self.binary_env_var else ""
        ) or self.cfg.binary or self.default_binary
        if not binary_name:
            raise FileNotFoundError(
                f"No binary configured for {self.family}; set ProviderCfg.binary or {self.binary_env_var}."
            )

        resolved = shutil.which(binary_name)
        if not resolved:
            raise FileNotFoundError(
                f"Could not find {self.family} binary '{binary_name}' on PATH."
            )
        return resolved

    def build_env(self, extra_env: Mapping[str, Any] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env.update({k: str(v) for k, v in self.cfg.env.items()})
        if extra_env:
            env.update({k: str(v) for k, v in extra_env.items()})
        return env

    def run(
        self,
        prompt_text: str,
        *,
        model: str | None = None,
        options: Mapping[str, Any] | None = None,
        cwd: str | None = None,
    ) -> CliRunResult:
        options_dict = dict(options or {})
        resolved_binary = self.resolve_binary()
        env = self.build_env(_pop_mapping(options_dict, "env"))
        timeout_sec = _coerce_timeout(options_dict.pop("timeout_sec", None))

        with tempfile.TemporaryDirectory(prefix=f"forge-{self.family}-") as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            plan = self.build_invocation(
                resolved_binary=resolved_binary,
                prompt_text=prompt_text,
                model=model,
                options=options_dict,
                tmpdir=tmpdir,
            )
            started = time.monotonic()
            try:
                proc = subprocess.run(
                    plan.command,
                    input=plan.stdin_text,
                    text=True,
                    capture_output=True,
                    cwd=cwd,
                    env=env,
                    timeout=timeout_sec,
                    check=False,
                )
                exit_code = int(proc.returncode)
                stdout_text = proc.stdout or ""
                stderr_text = proc.stderr or ""
                error = None
            except subprocess.TimeoutExpired as exc:
                exit_code = 124
                stdout_text = exc.stdout or ""
                stderr_text = exc.stderr or ""
                error = (
                    f"{self.family} command timed out after {timeout_sec} seconds"
                    if timeout_sec is not None
                    else f"{self.family} command timed out"
                )
            duration_sec = round(time.monotonic() - started, 3)

            result = self.parse_result(
                exit_code=exit_code,
                stdout_text=stdout_text,
                stderr_text=stderr_text,
                duration_sec=duration_sec,
                command=plan.safe_command,
                resolved_binary=resolved_binary,
                output_path=plan.output_path,
                schema_path=plan.schema_path,
            )

        if error:
            result.error = f"{error}\n{result.error}" if result.error else error
            result.ok = False
        return result

    @abstractmethod
    def build_invocation(
        self,
        *,
        resolved_binary: str,
        prompt_text: str,
        model: str | None,
        options: dict[str, Any],
        tmpdir: Path,
    ) -> CliInvocationPlan:
        """Return the command plan for a single invocation."""

    @abstractmethod
    def parse_result(
        self,
        *,
        exit_code: int,
        stdout_text: str,
        stderr_text: str,
        duration_sec: float,
        command: list[str],
        resolved_binary: str,
        output_path: Path | None,
        schema_path: Path | None,
    ) -> CliRunResult:
        """Parse a completed CLI invocation into a normalized result."""


def render_messages_as_transcript(messages: Sequence[Any]) -> str:
    """Flatten chat messages into a transcript string for single-shot CLIs."""

    parts: list[str] = [
        "Use the transcript below as the full conversation context. Follow any system instructions exactly and answer the latest user request.",
    ]
    for message in messages:
        role, content = normalize_message(message)
        if not role and not content:
            continue
        parts.append(f"[{role.upper() or 'MESSAGE'}]\n{content}")
    return "\n\n".join(parts).strip()


def normalize_message(message: Any) -> tuple[str, str]:
    if isinstance(message, Mapping):
        role = str(message.get("role", "")).strip().lower()
        content = stringify_content(message.get("content", ""))
        return role, content

    role = ""
    if hasattr(message, "type"):
        role = str(getattr(message, "type", "")).strip().lower()
    if not role:
        name = message.__class__.__name__.lower()
        if "system" in name:
            role = "system"
        elif "human" in name or "user" in name:
            role = "user"
        elif "ai" in name or "assistant" in name:
            role = "assistant"
        else:
            role = "message"
    content = stringify_content(getattr(message, "content", ""))
    return role, content


def stringify_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("text", "content", "result", "value"):
            if key in value:
                text = stringify_content(value[key])
                if text:
                    return text
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        chunks = [stringify_content(item) for item in value]
        return "\n".join(chunk for chunk in chunks if chunk)
    return str(value)


def extract_text_from_mapping(value: Mapping[str, Any]) -> str:
    for key in (
        "text",
        "result",
        "message",
        "content",
        "output",
        "response",
        "final_message",
    ):
        if key not in value:
            continue
        text = stringify_content(value[key])
        if text:
            return text
    return ""


def _coerce_timeout(value: Any) -> int | None:
    if value is None:
        return None
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced > 0 else None


def _pop_mapping(options: dict[str, Any], key: str) -> dict[str, Any]:
    raw = options.pop(key, None)
    if isinstance(raw, Mapping):
        return {str(k): v for k, v in raw.items()}
    return {}


def normalize_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        result: list[str] = []
        for item in value:
            if item is None:
                continue
            result.append(str(item))
        return result
    return [str(value)]
