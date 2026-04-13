# anvil/orchestration/nodes/review.py
import logging
import re
import time
from typing import Any

from anvil.text_sanitize import strip_think

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"\[(pass|fail)\]", flags=re.IGNORECASE)


def _parse_review_pass(text: str) -> bool:
    """
    Determine PASS/FAIL from a model response.

    Many local models emit `<think>...</think>` before the actual answer; strip it
    so PASS/FAIL tags are detected correctly and we don't trigger unnecessary retries.
    """
    s = strip_think(text)
    if not s:
        return False

    head = s[:200]
    if head.upper().startswith("[PASS]") or head.upper().startswith("PASS"):
        return True
    if head.upper().startswith("[FAIL]") or head.upper().startswith("FAIL"):
        return False

    match = _TAG_RE.search(head)
    if match:
        return match.group(1).lower() == "pass"

    return "PASS" in head.upper()


async def review_node(state: Any) -> Any:
    """
    Review the refined solution and determine if it passes or fails.

    Args:
        state: The current state object containing task and configuration

    Returns:
        Updated state with review results
    """
    start_time = time.time()

    try:
        provider, kwargs = state.get_provider_for_role("review")
        if not provider:
            raise RuntimeError("No provider available for review role")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a reviewer determining if a solution passes or fails.\n\n"
                    "Output format:\n"
                    "1) First line: [PASS] or [FAIL]\n"
                    "2) Then 1-2 short sentences explaining why (no step-by-step reasoning).\n\n"
                    "Do not include <think> tags or hidden reasoning."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: {state.prompt}\n\n"
                    f"Original solution:\n{state.logs.get('execute', '(No execution result)')}\n\n"
                    f"Critique:\n{state.logs.get('critique', '(No critique provided)')}\n\n"
                    f"Refined solution:\n{state.logs.get('refine', '(No refined solution)')}\n\n"
                    "Does this solution pass or fail? Begin your response with either ['PASS'] or "
                    "['FAIL'] and then provide your reasoning."
                ),
            },
        ]

        result = await provider.chat(messages, role="review", **kwargs)
        usage = getattr(provider, "last_usage", None)
        sanitized = strip_think(result)
        passes = _parse_review_pass(sanitized)

        state.logs["review"] = {"result": sanitized, "pass": passes}

        duration = time.time() - start_time
        state.log_node_timing("review", duration)

        resolution = getattr(state, "resolution_cache", {}).get("review", {})
        state.add_to_history(
            "review",
            {
                "provider_name": resolution.get("provider_name", "unknown"),
                "model_name": resolution.get("model_name", "unknown"),
                "kwargs": kwargs,
                "duration": duration,
                "usage": (
                    {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    if usage is not None
                    else None
                ),
                "pass": passes,
                "raw_result_length": len(result) if result else 0,
                "result_length": len(sanitized) if sanitized else 0,
            },
        )

        return state
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Review failed: {str(e)}"
        state.logs["review"] = {"result": error_msg, "pass": False, "failed": True}
        state.log_node_timing("review", duration)
        state.add_to_history(
            "review", {"error": str(e), "duration": duration, "failed": True}
        )
        logger.error(error_msg)
        return state
