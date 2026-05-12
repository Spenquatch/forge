from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Optional

from anvil.providers import get_provider_config, get_provider_exact

from .files import write_json, write_text
from .types import ProviderRun, StageRequest

PROVIDER_ALIASES: dict[str, str] = {
    "codex": "codex_cli",
    "claude": "claude_code",
}

ROLE_TO_FORGE_ROLE: dict[str, str] = {
    "solver": "execute",
    "proposer": "execute",
    "falsifier": "critique",
    "critic": "critique",
    "patcher": "refine",
    "reviser": "refine",
    "auditor": "review",
}


def _map_role_name_to_provider_role(role_name: str) -> str:
    normalized_role_name = str(role_name or "").strip().lower()
    if normalized_role_name in ROLE_TO_FORGE_ROLE:
        return ROLE_TO_FORGE_ROLE[normalized_role_name]
    if normalized_role_name.startswith("reviser") or normalized_role_name.startswith(
        "patcher"
    ):
        return "refine"
    if normalized_role_name.startswith("critic") or normalized_role_name.startswith(
        "falsifier"
    ):
        return "critique"
    if normalized_role_name.startswith("auditor"):
        return "review"
    if normalized_role_name.startswith("proposer") or normalized_role_name.startswith(
        "solver"
    ):
        return "execute"
    return "execute"


class BaseProviderAdapter:
    name: str

    def run(self, request: StageRequest) -> ProviderRun:
        raise NotImplementedError


class ForgeProviderAdapter(BaseProviderAdapter):
    def __init__(self, provider_name: str) -> None:
        self.requested_name = provider_name
        self.name = resolve_provider_name(provider_name)

    def run(self, request: StageRequest) -> ProviderRun:
        out_dir = Path(request.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = out_dir / "prompt.txt"
        schema_path = out_dir / "schema.json"
        stdout_path = out_dir / "response.txt"
        stderr_path = out_dir / "error.txt"
        raw_output_path = out_dir / "structured_output.raw.json"
        normalized_output_path = out_dir / "structured_output.normalized.json"

        write_text(prompt_path, request.prompt_text)
        write_json(schema_path, request.schema)

        provider = get_provider_exact(self.name)
        cfg = get_provider_config(self.name)
        if provider is None or cfg is None:
            message = (
                f"Provider '{self.requested_name}' resolved to '{self.name}', but it is not configured or could not be initialized."
            )
            write_text(stdout_path, "")
            write_text(stderr_path, message)
            return ProviderRun(
                role_name=request.role_name,
                provider=self.name,
                model=request.role_config.model,
                access=request.role_config.access,
                ok=False,
                exit_code=127,
                duration_sec=0.0,
                cwd=request.cwd,
                command=[self.name],
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                prompt_path=str(prompt_path),
                schema_path=str(schema_path),
                output_path=None,
                raw_output_path=None,
                normalized_output_path=None,
                structured_output=None,
                raw_meta={"requested_provider": self.requested_name},
                error=message,
            )

        provider_type = (cfg.type or "").lower()
        mapped_role = _map_role_name_to_provider_role(request.role_name)
        kwargs = _build_provider_kwargs(request, provider_type)
        prompt_text = _render_prompt_for_provider(
            request.prompt_text,
            request.schema,
            provider_type=provider_type,
        )

        started = time.monotonic()
        raw_text = ""
        error_text: Optional[str] = None
        stderr_text: Optional[str] = None
        exit_code = 0
        structured_output: Optional[dict[str, Any]] = None
        failure_kind: Optional[str] = None
        failure_summary: Optional[str] = None
        raw_meta: dict[str, Any] = {
            "requested_provider": self.requested_name,
            "resolved_provider": self.name,
            "provider_type": provider_type,
            "mapped_role": mapped_role,
        }
        command: list[str] = []

        try:
            raw_text = _run_provider_call(provider, prompt_text, mapped_role, kwargs)
        except Exception as exc:  # pragma: no cover - exercised in integration scenarios
            raw_text = getattr(provider, "last_response_text", "") or ""
            cli_result = getattr(provider, "last_cli_result", None)
            if cli_result is not None:
                exit_code = int(getattr(cli_result, "exit_code", 1) or 1)
                raw_text = getattr(cli_result, "stdout_text", raw_text) or raw_text
                stderr_text = getattr(cli_result, "stderr_text", None) or None
                error_text = stderr_text or str(exc)
                command = list(getattr(cli_result, "command", []) or [])
                raw_meta.update(_cli_result_meta(cli_result))
                try:
                    maybe_structured = cli_result.structured_output
                except AttributeError:
                    maybe_structured = None
                if isinstance(maybe_structured, dict):
                    structured_output = maybe_structured
            else:
                exit_code = 1
                error_text = str(exc)

        duration = round(time.monotonic() - started, 3)

        if provider_type == "cli":
            cli_result = getattr(provider, "last_cli_result", None)
            if cli_result is not None:
                exit_code = int(getattr(cli_result, "exit_code", exit_code) or exit_code)
                raw_text = getattr(cli_result, "stdout_text", raw_text) or raw_text
                command = list(getattr(cli_result, "command", []) or command)
                raw_meta.update(_cli_result_meta(cli_result))
                cli_stderr_text = getattr(cli_result, "stderr_text", "") or ""
                stderr_text = cli_stderr_text or stderr_text
                if error_text is None and exit_code != 0:
                    error_text = stderr_text or None
                maybe_structured = getattr(cli_result, "structured_output", None)
                if structured_output is None and isinstance(maybe_structured, dict):
                    structured_output = maybe_structured
        else:
            command = [self.name]
            if error_text is None:
                error_text = None

        if structured_output is None and raw_text:
            structured_output, parse_error = _extract_structured_output(raw_text)
            if parse_error and error_text is None:
                error_text = parse_error

        provider_failure = _classify_provider_failure(
            structured_output,
            error_text=error_text,
            raw_text=raw_text,
            exit_code=exit_code,
        )
        validation_errors: list[str] = []
        if provider_failure is not None:
            failure_kind, failure_summary = provider_failure
            raw_meta["provider_failure_kind"] = failure_kind
            raw_meta["provider_failure_summary"] = failure_summary
            error_text = failure_summary
        else:
            validation_errors = _soft_validate_schema(structured_output, request.schema)
            if validation_errors:
                error_text = "\n".join(validation_errors)

        if (
            provider_type == "cli"
            and exit_code == 0
            and structured_output is not None
            and not validation_errors
            and failure_kind is None
        ):
            error_text = None
            failure_summary = None

        write_text(stdout_path, raw_text)
        write_text(
            stderr_path,
            (stderr_text if provider_type == "cli" else error_text) or "",
        )
        if structured_output is not None:
            write_json(raw_output_path, structured_output)
            write_json(normalized_output_path, structured_output)

        if request.role_config.model and provider_type != "cli":
            raw_meta["model_override_ignored"] = request.role_config.model
        if hasattr(provider, "last_run_metadata"):
            last_meta = getattr(provider, "last_run_metadata", None)
            if isinstance(last_meta, Mapping):
                raw_meta.update({f"provider_{k}": v for k, v in last_meta.items()})
        if hasattr(provider, "last_command") and not command:
            maybe_command = getattr(provider, "last_command", None)
            if isinstance(maybe_command, list):
                command = list(maybe_command)

        ok = (
            exit_code == 0
            and structured_output is not None
            and not validation_errors
            and failure_kind is None
        )
        return ProviderRun(
            role_name=request.role_name,
            provider=self.name,
            model=_reported_model_name(provider, request.role_config.model),
            access=request.role_config.access,
            ok=ok,
            exit_code=exit_code,
            duration_sec=duration,
            cwd=request.cwd,
            command=command,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            prompt_path=str(prompt_path),
            schema_path=str(schema_path),
            output_path=(
                str(normalized_output_path) if structured_output is not None else None
            ),
            raw_output_path=(
                str(raw_output_path) if structured_output is not None else None
            ),
            normalized_output_path=(
                str(normalized_output_path) if structured_output is not None else None
            ),
            structured_output=structured_output,
            raw_meta=raw_meta,
            error=error_text,
            failure_kind=failure_kind,
            failure_summary=failure_summary,
            schema_validation_errors=validation_errors,
        )


def resolve_provider_name(name: str) -> str:
    key = str(name).strip()
    lowered = key.lower()
    return PROVIDER_ALIASES.get(lowered, lowered)


def get_provider(name: str) -> BaseProviderAdapter:
    return ForgeProviderAdapter(name)


def _run_provider_call(provider: Any, prompt_text: str, mapped_role: str, kwargs: dict[str, Any]) -> str:
    async def _invoke() -> str:
        if hasattr(provider, "generate"):
            return await provider.generate(prompt_text, role=mapped_role, **kwargs)
        if hasattr(provider, "chat"):
            return await provider.chat(
                [{"role": "user", "content": prompt_text}],
                role=mapped_role,
                **kwargs,
            )
        raise RuntimeError(f"Provider {type(provider).__name__} does not expose generate/chat")

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_invoke())

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(_invoke()))
        return future.result()


def _build_provider_kwargs(request: StageRequest, provider_type: str) -> dict[str, Any]:
    cfg = request.role_config
    kwargs: dict[str, Any] = {
        "timeout_sec": cfg.timeout_sec,
    }
    if provider_type == "cli":
        kwargs.update(
            {
                "cwd": request.cwd,
                "access": cfg.access,
                "env": dict(cfg.env),
                "extra_args": list(cfg.extra_args),
                "disable_bare": cfg.disable_bare,
                "skip_git_repo_check": cfg.skip_git_repo_check,
                "output_schema": request.schema,
            }
        )
        if cfg.model:
            kwargs["model"] = cfg.model
        if cfg.effort:
            kwargs["effort"] = cfg.effort
        if cfg.max_turns is not None:
            kwargs["max_turns"] = cfg.max_turns
        if cfg.max_budget_usd is not None:
            kwargs["max_budget_usd"] = cfg.max_budget_usd
    return kwargs


def _reported_model_name(provider: Any, explicit_model: str | None) -> str | None:
    if hasattr(provider, "reported_model_name"):
        maybe = provider.reported_model_name(explicit_model)
        return str(maybe) if maybe not in (None, "") else None
    if explicit_model:
        return explicit_model
    fallback = getattr(provider, "model_name", None)
    return str(fallback) if fallback not in (None, "") else None


def _render_prompt_for_provider(prompt_text: str, schema: dict[str, Any], *, provider_type: str) -> str:
    if provider_type == "cli":
        return prompt_text
    schema_text = json.dumps(schema, indent=2, sort_keys=False)
    return (
        prompt_text.rstrip()
        + "\n\nReturn ONLY a valid JSON object matching this schema. Do not use Markdown fences.\n"
        + "JSON schema:\n"
        + schema_text
        + "\n"
    )


def _extract_structured_output(text: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    cleaned = text.strip()
    if not cleaned:
        return None, "Provider returned no text to parse."

    fenced = cleaned
    if fenced.startswith("```"):
        parts = fenced.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            if cleaned.lstrip().startswith("json"):
                cleaned = cleaned.lstrip()[4:]
            cleaned = cleaned.strip()

    direct = _try_json_load(cleaned)
    if isinstance(direct, dict):
        return direct, None

    extracted = _extract_first_json_object(cleaned)
    if extracted is None:
        return None, "Could not parse a JSON object from the provider response."
    payload = _try_json_load(extracted)
    if isinstance(payload, dict):
        return payload, None
    return None, "Parsed JSON was not an object."


def _try_json_load(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_first_json_object(text: str) -> Optional[str]:
    in_string = False
    escape = False
    depth = 0
    start_idx: Optional[int] = None
    for idx, ch in enumerate(text):
        if start_idx is None:
            if ch == "{":
                start_idx = idx
                depth = 1
            continue

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : idx + 1]
    return None


def _soft_validate_schema(payload: Optional[dict[str, Any]], schema: Mapping[str, Any]) -> list[str]:
    if payload is None:
        return ["Structured output is missing."]
    errors: list[str] = []
    _validate_node(payload, schema, path="$", errors=errors)
    return errors


def _validate_node(value: Any, schema: Mapping[str, Any], *, path: str, errors: list[str]) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object")
            return
        required = schema.get("required") or []
        if isinstance(required, list):
            for field in required:
                if field not in value:
                    errors.append(f"{path}.{field}: missing required field")
        props = schema.get("properties") or {}
        if isinstance(props, Mapping):
            for field, child_schema in props.items():
                if field not in value:
                    continue
                if isinstance(child_schema, Mapping):
                    _validate_node(value[field], child_schema, path=f"{path}.{field}", errors=errors)
        enum = schema.get("enum")
        if isinstance(enum, list) and value not in enum:
            errors.append(f"{path}: value must be one of {enum}")
        return

    if schema_type == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array")
            return
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for idx, item in enumerate(value):
                _validate_node(item, item_schema, path=f"{path}[{idx}]", errors=errors)
        return

    if schema_type == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string")
            return
        enum = schema.get("enum")
        if isinstance(enum, list) and value not in enum:
            errors.append(f"{path}: value must be one of {enum}")
        return

    if schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: expected number")
            return
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and float(value) < float(minimum):
            errors.append(f"{path}: expected >= {minimum}")
        if maximum is not None and float(value) > float(maximum):
            errors.append(f"{path}: expected <= {maximum}")
        return

    if schema_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected boolean")
        return

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: value must be one of {enum}")


def _classify_provider_failure(
    payload: Optional[dict[str, Any]],
    *,
    error_text: Optional[str],
    raw_text: str,
    exit_code: int,
) -> tuple[str, str] | None:
    message = _provider_failure_message(payload, error_text=error_text, raw_text=raw_text)
    lowered = message.lower()
    looks_like_provider_envelope = _looks_like_provider_result_envelope(payload)

    if exit_code == 0 and not looks_like_provider_envelope:
        return None

    if not message and exit_code == 0:
        return None

    kind = "provider_error"
    if any(token in lowered for token in ("hit your limit", "quota", "rate limit", "too many requests", "429")):
        kind = "quota_exhausted"
    elif any(token in lowered for token in ("authentication", "unauthorized", "api key", "not logged in", "login")):
        kind = "authentication_error"
    elif any(token in lowered for token in ("permission denied", "forbidden", "permission")):
        kind = "permission_denied"
    elif any(
        token in lowered
        for token in ("not configured", "could not be initialized", "unavailable", "not installed")
    ):
        kind = "provider_unavailable"

    summary = _format_provider_failure_summary(kind, message or f"Provider exited with code {exit_code}.")
    return kind, summary


def _looks_like_provider_result_envelope(payload: Optional[dict[str, Any]]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    if payload.get("type") in {"result", "error"}:
        return True
    if "is_error" in payload:
        return True
    if payload.get("subtype") and payload.get("session_id"):
        return True
    return False


def _provider_failure_message(
    payload: Optional[dict[str, Any]],
    *,
    error_text: Optional[str],
    raw_text: str,
) -> str:
    candidate_bits: list[str] = []
    if isinstance(payload, dict):
        for field_name in ("result", "error", "message", "stderr", "stdout"):
            value = payload.get(field_name)
            if isinstance(value, str) and value.strip():
                candidate_bits.append(value.strip())
    candidate_bits.extend(_extract_provider_event_messages(raw_text))
    if error_text and error_text.strip():
        candidate_bits.append(error_text.strip())
    cleaned_raw = raw_text.strip()
    if cleaned_raw and cleaned_raw not in candidate_bits and len(cleaned_raw) <= 400:
        candidate_bits.append(cleaned_raw)
    return next((item for item in candidate_bits if item), "")


def _extract_provider_event_messages(raw_text: str) -> list[str]:
    messages: list[str] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        direct_message = payload.get("message")
        if isinstance(direct_message, str) and direct_message.strip():
            messages.append(direct_message.strip())

        nested_error = payload.get("error")
        if isinstance(nested_error, dict):
            nested_message = nested_error.get("message")
            if isinstance(nested_message, str) and nested_message.strip():
                messages.append(nested_message.strip())

        item = payload.get("item")
        if isinstance(item, dict):
            item_message = item.get("message")
            if isinstance(item_message, str) and item_message.strip():
                messages.append(item_message.strip())
    return messages


def _format_provider_failure_summary(kind: str, message: str) -> str:
    prefix_map = {
        "quota_exhausted": "Provider quota exhausted",
        "authentication_error": "Provider authentication error",
        "permission_denied": "Provider permission error",
        "provider_unavailable": "Provider unavailable",
        "provider_error": "Provider execution error",
    }
    prefix = prefix_map.get(kind, "Provider execution error")
    text = message.strip()
    return f"{prefix}: {text}" if text else prefix


def _cli_result_meta(cli_result: Any) -> dict[str, Any]:
    meta = getattr(cli_result, "metadata", None)
    result = dict(meta) if isinstance(meta, Mapping) else {}
    try:
        usage = cli_result.usage
    except AttributeError:
        usage = None
    if usage is not None:
        try:
            result["usage"] = asdict(usage)
        except Exception:
            result["usage"] = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
    return result
