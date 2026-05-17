"""Codex CLI provider."""

from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path
from typing import Any, Dict, List

from anvil.cli_agents import (
    BaseCliAgent,
    CliRunResult,
    CodexCliAgent,
    render_messages_as_transcript,
)
from anvil.config_loader import ProviderCfg

from .cli_provider import CliProviderBase


class CodexCliProvider(CliProviderBase):
    def __init__(self, cfg: ProviderCfg) -> None:
        super().__init__(cfg)
        self._last_reported_model: str | None = None

    def forces_default_model_arg(self) -> bool:
        # Codex model selection needs provider-specific precedence and retry logic.
        return False

    def reported_model_name(self, explicit_model: str | None = None) -> str | None:
        if self._last_reported_model:
            return self._last_reported_model
        if explicit_model:
            return explicit_model
        return self.model_name or _configured_codex_default_model()

    def build_agent(self, cfg: ProviderCfg) -> BaseCliAgent:
        return CodexCliAgent(cfg)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        role: str = "execute",
        **kwargs: Any,
    ) -> str:
        explicit_model = _normalize_optional_str(kwargs.get("model"))
        merged_kwargs = self._merge_kwargs(role, dict(kwargs))
        cwd = merged_kwargs.pop("cwd", None)
        prompt_text = render_messages_as_transcript(messages)
        configured_codex_model = _configured_codex_default_model()

        initial_model = explicit_model or _normalize_optional_str(self.model_name)
        initial_source = (
            "strategy"
            if explicit_model
            else (
                "models_yaml"
                if initial_model
                else ("codex_config" if configured_codex_model else "codex_cli")
            )
        )

        attempts: list[dict[str, Any]] = []
        fallback_used = False
        fallback_reason: str | None = None

        result = await self._run_attempt(
            prompt_text=prompt_text,
            cwd=cwd,
            options=merged_kwargs,
            model=initial_model,
        )
        attempts.append(
            {
                "model": initial_model,
                "source": initial_source,
                "used_model_arg": initial_model is not None,
                "ok": bool(result.ok),
                "exit_code": int(result.exit_code),
            }
        )

        effective_model = initial_model
        effective_source = initial_source

        if (
            explicit_model is None
            and initial_model is not None
            and _is_codex_model_selection_failure(result)
        ):
            fallback_used = True
            fallback_reason = _extract_codex_model_failure_reason(result)
            result = await self._run_attempt(
                prompt_text=prompt_text,
                cwd=cwd,
                options=merged_kwargs,
                model=None,
            )
            effective_model = configured_codex_model
            effective_source = "codex_config" if configured_codex_model else "codex_cli"
            attempts.append(
                {
                    "model": effective_model,
                    "source": effective_source,
                    "used_model_arg": False,
                    "ok": bool(result.ok),
                    "exit_code": int(result.exit_code),
                }
            )

        self._record_attempt_result(
            result,
            explicit_model=explicit_model,
            initial_model=initial_model,
            initial_source=initial_source,
            effective_model=effective_model,
            effective_source=effective_source,
            configured_codex_model=configured_codex_model,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            attempts=attempts,
        )

        if not result.ok:
            detail = (
                result.error
                or result.stderr_text
                or result.stdout_text
                or "CLI agent failed"
            )
            raise RuntimeError(detail)

        return result.text

    async def _run_attempt(
        self,
        *,
        prompt_text: str,
        cwd: str | None,
        options: dict[str, Any],
        model: str | None,
    ) -> CliRunResult:
        return await asyncio.to_thread(
            self._agent.run,
            prompt_text,
            model=model,
            options=dict(options),
            cwd=cwd,
        )

    def _record_attempt_result(
        self,
        result: CliRunResult,
        *,
        explicit_model: str | None,
        initial_model: str | None,
        initial_source: str,
        effective_model: str | None,
        effective_source: str,
        configured_codex_model: str | None,
        fallback_used: bool,
        fallback_reason: str | None,
        attempts: list[dict[str, Any]],
    ) -> None:
        self.last_cli_result = result
        self.last_usage = result.usage
        self.last_command = list(result.command)
        self.last_structured_output = result.structured_output
        self._last_reported_model = effective_model
        self.last_run_metadata = dict(result.metadata)
        self.last_run_metadata.update(
            {
                "model_requested_explicit": explicit_model,
                "model_initial_attempt": initial_model,
                "model_initial_source": initial_source,
                "model_effective": effective_model,
                "model_effective_source": effective_source,
                "model_configured_codex_default": configured_codex_model,
                "model_fallback_used": fallback_used,
                "model_fallback_reason": fallback_reason,
                "model_attempt_count": len(attempts),
                "model_attempts": attempts,
            }
        )


def _configured_codex_default_model() -> str | None:
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return None
    model = data.get("model")
    if model in (None, ""):
        return None
    return str(model)


def _normalize_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _is_codex_model_selection_failure(result: CliRunResult) -> bool:
    lowered = _codex_result_text(result).lower()
    if not lowered or "timed out" in lowered:
        return False
    if "invalid_request_error" in lowered and "model" in lowered:
        return True
    return any(
        marker in lowered
        for marker in (
            "model is not supported",
            "unsupported model",
            "unknown model",
            "invalid model",
            "unknown model name",
            "no such model",
        )
    )


def _extract_codex_model_failure_reason(result: CliRunResult) -> str | None:
    text = _codex_result_text(result).strip()
    return text or None


def _codex_result_text(result: CliRunResult) -> str:
    return "\n".join(
        part.strip()
        for part in (result.error, result.stderr_text, result.stdout_text)
        if isinstance(part, str) and part.strip()
    )
