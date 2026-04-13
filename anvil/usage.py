from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_usage_mapping(raw: Mapping[str, Any]) -> Optional[TokenUsage]:
    input_tokens = _to_int(raw.get("input_tokens", raw.get("prompt_tokens")))
    output_tokens = _to_int(raw.get("output_tokens", raw.get("completion_tokens")))

    # OpenAI-style token_usage dict: prompt/completion/total.
    if input_tokens is None and "prompt_tokens" in raw:
        input_tokens = _to_int(raw.get("prompt_tokens"))
    if output_tokens is None and "completion_tokens" in raw:
        output_tokens = _to_int(raw.get("completion_tokens"))

    if input_tokens is None and output_tokens is None:
        return None

    if input_tokens is None:
        input_tokens = 0
    if output_tokens is None:
        output_tokens = 0

    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)


def extract_token_usage(obj: Any) -> Optional[TokenUsage]:
    """
    Best-effort extraction of token usage from provider/library responses.

    Supports:
    - LangChain AIMessage response_metadata/usage_metadata
    - Anthropic SDK response.usage
    - Plain dict payloads containing common usage keys
    """
    if obj is None:
        return None

    if isinstance(obj, Mapping):
        return _normalize_usage_mapping(obj)

    # Anthropic SDK: response.usage.{input_tokens, output_tokens}
    usage_attr = getattr(obj, "usage", None)
    if usage_attr is not None:
        if isinstance(usage_attr, Mapping):
            usage = _normalize_usage_mapping(usage_attr)
            if usage is not None:
                return usage
        else:
            usage = _normalize_usage_mapping(
                {
                    "input_tokens": getattr(usage_attr, "input_tokens", None),
                    "output_tokens": getattr(usage_attr, "output_tokens", None),
                }
            )
            if usage is not None:
                return usage

    # LangChain message: .usage_metadata (newer) or .response_metadata (common)
    usage_metadata = getattr(obj, "usage_metadata", None)
    if usage_metadata is not None:
        if isinstance(usage_metadata, Mapping):
            usage = _normalize_usage_mapping(usage_metadata)
            if usage is not None:
                return usage
        else:
            usage = _normalize_usage_mapping(
                {
                    "input_tokens": getattr(usage_metadata, "input_tokens", None),
                    "output_tokens": getattr(usage_metadata, "output_tokens", None),
                    "prompt_tokens": getattr(usage_metadata, "prompt_tokens", None),
                    "completion_tokens": getattr(
                        usage_metadata, "completion_tokens", None
                    ),
                }
            )
            if usage is not None:
                return usage

    response_metadata = getattr(obj, "response_metadata", None)
    if isinstance(response_metadata, Mapping):
        token_usage = response_metadata.get("token_usage")
        if isinstance(token_usage, Mapping):
            usage = _normalize_usage_mapping(token_usage)
            if usage is not None:
                return usage

        usage_dict = response_metadata.get("usage")
        if isinstance(usage_dict, Mapping):
            usage = _normalize_usage_mapping(usage_dict)
            if usage is not None:
                return usage

    return None


@dataclass(frozen=True)
class ModelPricing:
    input_per_1m: float
    output_per_1m: float


_PRICING_USD_PER_1M_TOKENS: dict[str, ModelPricing] = {
    # Best-effort defaults for common configured models; update as needed.
    "gpt-4o-mini": ModelPricing(input_per_1m=0.15, output_per_1m=0.60),
    "gpt-4o": ModelPricing(input_per_1m=5.00, output_per_1m=15.00),
    "claude-3-haiku-20240307": ModelPricing(input_per_1m=0.25, output_per_1m=1.25),
    "claude-3-sonnet-20240229": ModelPricing(input_per_1m=3.00, output_per_1m=15.00),
}


def estimate_cost_usd(
    model_name: Optional[str], usage: Optional[TokenUsage]
) -> Optional[float]:
    if not model_name or usage is None:
        return None
    pricing = _PRICING_USD_PER_1M_TOKENS.get(model_name)
    if pricing is None:
        return None

    cost = (usage.input_tokens / 1_000_000) * pricing.input_per_1m + (
        usage.output_tokens / 1_000_000
    ) * pricing.output_per_1m
    return round(cost, 8)
