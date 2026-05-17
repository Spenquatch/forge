from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from anvil.usage import TokenUsage, extract_token_usage

from .base import (
    BaseCliAgent,
    CliInvocationPlan,
    CliRunResult,
    extract_text_from_mapping,
    normalize_str_list,
    stringify_content,
)


class ClaudeCodeCliAgent(BaseCliAgent):
    family = "claude_code"
    default_binary = "claude"
    binary_env_var = "FORGE_CLAUDE_BIN"

    def build_invocation(
        self,
        *,
        resolved_binary: str,
        prompt_text: str,
        model: str | None,
        options: dict[str, Any],
        tmpdir: Path,
    ) -> CliInvocationPlan:
        cmd: list[str] = [resolved_binary]
        safe_cmd: list[str] = [resolved_binary]

        _ = options.pop("disable_bare", False)

        cmd.extend(["-p", prompt_text, "--output-format", "json"])
        safe_cmd.extend(["-p", "<prompt omitted>", "--output-format", "json"])

        output_schema = options.pop("output_schema", None)
        if output_schema is not None:
            schema_inline = json.dumps(output_schema, separators=(",", ":"))
            cmd.extend(["--json-schema", schema_inline])
            safe_cmd.extend(["--json-schema", "<schema omitted>"])

        access = str(options.pop("access", "read")).strip().lower()
        default_tools = {
            "read": "Read",
            "write": "Bash,Read,Edit",
            "danger": "Bash,Read,Edit",
        }.get(access, "Read")
        tools = str(options.pop("tools", default_tools))
        allowed_tools = (
            str(options.pop("allowed_tools", tools)) if tools != "default" else None
        )
        if tools:
            cmd.extend(["--tools", tools])
            safe_cmd.extend(["--tools", tools])
        if allowed_tools:
            cmd.extend(["--allowedTools", allowed_tools])
            safe_cmd.extend(["--allowedTools", allowed_tools])
        if access == "danger":
            cmd.append("--dangerously-skip-permissions")
            safe_cmd.append("--dangerously-skip-permissions")

        permission_mode = options.pop("permission_mode", None)
        if permission_mode:
            cmd.extend(["--permission-mode", str(permission_mode)])
            safe_cmd.extend(["--permission-mode", str(permission_mode)])

        if model:
            cmd.extend(["--model", model])
            safe_cmd.extend(["--model", model])

        effort = options.pop("effort", None)
        if effort:
            cmd.extend(["--effort", str(effort)])
            safe_cmd.extend(["--effort", str(effort)])

        max_turns = options.pop("max_turns", None)
        if max_turns is not None:
            cmd.extend(["--max-turns", str(max_turns)])
            safe_cmd.extend(["--max-turns", str(max_turns)])

        max_budget_usd = options.pop("max_budget_usd", None)
        if max_budget_usd is not None:
            budget_text = f"{float(max_budget_usd):.2f}"
            cmd.extend(["--max-budget-usd", budget_text])
            safe_cmd.extend(["--max-budget-usd", budget_text])

        for add_dir in normalize_str_list(options.pop("add_dirs", None)):
            cmd.extend(["--add-dir", add_dir])
            safe_cmd.extend(["--add-dir", add_dir])

        extra_args = self.cfg.default_args + normalize_str_list(
            options.pop("extra_args", None)
        )
        cmd.extend(extra_args)
        safe_cmd.extend(extra_args)

        return CliInvocationPlan(command=cmd, safe_command=safe_cmd)

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
        payload: dict[str, Any] | None = None
        structured_output: Any | None = None
        text = stdout_text.strip()
        usage: TokenUsage | None = None
        error = None

        try:
            maybe = json.loads(stdout_text) if stdout_text.strip() else None
            if isinstance(maybe, dict):
                payload = maybe
        except json.JSONDecodeError:
            payload = None

        if payload is not None:
            if "usage" in payload:
                usage = extract_token_usage(payload.get("usage"))
            if usage is None:
                usage = extract_token_usage(payload)
            if "structured_output" in payload:
                structured_output = payload.get("structured_output")
                if structured_output is not None:
                    text = json.dumps(structured_output, ensure_ascii=False, indent=2)
            if structured_output is None:
                candidate = _extract_payload_text(payload)
                if candidate:
                    text = candidate

        if exit_code != 0:
            tail = (
                stderr_text.strip()
                or stdout_text.strip()
                or "Claude Code exited with an error"
            )
            error = tail[-2000:]

        ok = exit_code == 0 and bool(text or structured_output is not None)
        metadata: dict[str, Any] = {"family": self.family}
        if payload is not None:
            metadata.update(
                {
                    k: v
                    for k, v in payload.items()
                    if k
                    not in {
                        "result",
                        "structured_output",
                        "message",
                        "messages",
                        "content",
                    }
                }
            )

        return CliRunResult(
            ok=ok,
            exit_code=exit_code,
            text=text,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
            duration_sec=duration_sec,
            command=command,
            resolved_binary=resolved_binary,
            metadata=metadata,
            usage=usage,
            structured_output=structured_output,
            error=error,
        )


def _extract_payload_text(payload: Mapping[str, Any]) -> str:
    direct = extract_text_from_mapping(payload)
    if direct:
        return direct

    message = payload.get("message")
    if isinstance(message, Mapping):
        text = _extract_text_from_message(message)
        if text:
            return text

    messages = payload.get("messages")
    if isinstance(messages, Sequence) and not isinstance(
        messages, (str, bytes, bytearray)
    ):
        for item in reversed(messages):
            if isinstance(item, Mapping):
                text = _extract_text_from_message(item)
                if text:
                    return text

    content = payload.get("content")
    text = stringify_content(content)
    return text.strip()


def _extract_text_from_message(message: Mapping[str, Any]) -> str:
    if "content" in message:
        return stringify_content(message["content"]).strip()
    return extract_text_from_mapping(message).strip()
