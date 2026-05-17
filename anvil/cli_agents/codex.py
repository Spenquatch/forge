from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anvil.usage import TokenUsage, extract_token_usage

from .base import (
    BaseCliAgent,
    CliInvocationPlan,
    CliRunResult,
    normalize_str_list,
    stringify_content,
)


class CodexCliAgent(BaseCliAgent):
    family = "codex"
    default_binary = "codex"
    binary_env_var = "FORGE_CODEX_BIN"

    def build_invocation(
        self,
        *,
        resolved_binary: str,
        prompt_text: str,
        model: str | None,
        options: dict[str, Any],
        tmpdir: Path,
    ) -> CliInvocationPlan:
        cmd: list[str] = [
            resolved_binary,
            "exec",
            "--ephemeral",
            "--json",
            "--color",
            "never",
        ]
        safe_cmd: list[str] = list(cmd)

        access = str(options.pop("access", "read")).strip().lower()
        sandbox = {
            "read": "read-only",
            "write": "workspace-write",
            "danger": "danger-full-access",
        }.get(access, "read-only")
        cmd.extend(["--sandbox", sandbox])
        safe_cmd.extend(["--sandbox", sandbox])

        approval_mode = options.pop("approval_mode", None)
        if approval_mode:
            cmd.extend(["--ask-for-approval", str(approval_mode)])
            safe_cmd.extend(["--ask-for-approval", str(approval_mode)])

        if model:
            cmd.extend(["--model", model])
            safe_cmd.extend(["--model", model])

        effort = options.pop("effort", None)
        if effort:
            cfg_expr = f'model_reasoning_effort="{effort}"'
            cmd.extend(["-c", cfg_expr])
            safe_cmd.extend(["-c", cfg_expr])

        if bool(options.pop("skip_git_repo_check", False)):
            cmd.append("--skip-git-repo-check")
            safe_cmd.append("--skip-git-repo-check")

        for add_dir in normalize_str_list(options.pop("add_dirs", None)):
            cmd.extend(["--add-dir", add_dir])
            safe_cmd.extend(["--add-dir", add_dir])

        output_schema = options.pop("output_schema", None)
        schema_path: Path | None = None
        output_path: Path | None = None
        if output_schema is not None:
            schema_path = tmpdir / "schema.json"
            output_path = tmpdir / "structured_output.raw.json"
            schema_path.write_text(
                json.dumps(_codex_compatible_schema(output_schema), indent=2),
                encoding="utf-8",
            )
            cmd.extend(["--output-schema", str(schema_path), "-o", str(output_path)])
            safe_cmd.extend(
                ["--output-schema", str(schema_path), "-o", str(output_path)]
            )

        extra_args = self.cfg.default_args + normalize_str_list(
            options.pop("extra_args", None)
        )
        cmd.extend(extra_args)
        safe_cmd.extend(extra_args)

        cmd.append("-")
        safe_cmd.append("-")
        return CliInvocationPlan(
            command=cmd,
            safe_command=safe_cmd,
            stdin_text=prompt_text,
            output_path=output_path,
            schema_path=schema_path,
        )

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
        events: list[dict[str, Any]] = []
        event_count = 0
        parse_errors = 0
        thread_id = None
        usage: TokenUsage | None = None
        last_agent_message = ""
        item_type_counts: dict[str, int] = {}

        for raw_line in stdout_text.splitlines():
            if not raw_line.strip():
                continue
            event_count += 1
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            if isinstance(payload, dict):
                events.append(payload)
                event_type = payload.get("type")
                if event_type == "thread.started":
                    thread_id = payload.get("thread_id") or payload.get("threadId")
                elif event_type == "turn.completed":
                    usage = extract_token_usage(payload.get("usage")) or usage
                elif event_type == "item.completed" and isinstance(
                    payload.get("item"), dict
                ):
                    item = payload["item"]
                    item_type = item.get("type")
                    if item_type:
                        item_type_counts[str(item_type)] = (
                            item_type_counts.get(str(item_type), 0) + 1
                        )
                    if item_type in {"agent_message", "assistant_message"}:
                        candidate = stringify_content(
                            item.get("text") or item.get("content") or item
                        )
                        if candidate:
                            last_agent_message = candidate

        structured_output = None
        text = last_agent_message.strip()
        if output_path and output_path.exists():
            raw_output = output_path.read_text(encoding="utf-8", errors="replace")
            try:
                structured_output = json.loads(raw_output)
                text = json.dumps(structured_output, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                text = raw_output.strip()

        error = None
        if exit_code != 0:
            tail = (
                stderr_text.strip()
                or stdout_text.strip()
                or "Codex CLI exited with an error"
            )
            error = tail[-2000:]

        ok = exit_code == 0 and bool(text or structured_output is not None)
        metadata = {
            "family": self.family,
            "thread_id": thread_id,
            "event_count": event_count,
            "item_type_counts": item_type_counts,
            "json_parse_errors": parse_errors,
            "raw_event_count": len(events),
        }
        if schema_path is not None:
            metadata["schema_path"] = str(schema_path)
        if output_path is not None:
            metadata["output_path"] = str(output_path)

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


def _codex_compatible_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema

    if isinstance(schema.get("anyOf"), list):
        normalized = dict(schema)
        normalized["anyOf"] = [
            _codex_compatible_schema(option) for option in schema["anyOf"]
        ]
        return normalized

    schema_type = schema.get("type")
    if schema_type == "array":
        normalized = dict(schema)
        normalized["items"] = _codex_compatible_schema(schema.get("items"))
        return normalized

    if schema_type != "object":
        return dict(schema)

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return dict(schema)

    required = schema.get("required")
    required_list = list(required) if isinstance(required, list) else []
    required_set = set(required_list)

    normalized_props: dict[str, Any] = {}
    for key, child_schema in properties.items():
        normalized_child = _codex_compatible_schema(child_schema)
        if key not in required_set:
            normalized_child = _make_nullable_schema(normalized_child)
            required_list.append(key)
            required_set.add(key)
        normalized_props[key] = normalized_child

    normalized = dict(schema)
    normalized["properties"] = normalized_props
    normalized["required"] = required_list
    return normalized


def _make_nullable_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return {"anyOf": [schema, {"type": "null"}]}

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        if any(
            isinstance(option, dict) and option.get("type") == "null"
            for option in any_of
        ):
            return schema
        return {"anyOf": [*any_of, {"type": "null"}]}

    if schema.get("type") == "null":
        return schema

    return {"anyOf": [schema, {"type": "null"}]}
