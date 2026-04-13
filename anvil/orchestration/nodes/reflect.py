# anvil/orchestration/nodes/reflect.py
import logging
import time
from typing import Any

from anvil.text_sanitize import extract_final

logger = logging.getLogger(__name__)


async def reflect_node(state: Any) -> Any:
    """
    Reflect on a failed solution and provide strategy adjustments.

    Args:
        state: The current state object containing task and configuration

    Returns:
        Updated state with reflection results
    """
    start_time = time.time()

    try:
        provider, kwargs = state.get_provider_for_role("reflect")
        if not provider:
            raise RuntimeError("No provider available for reflect role")

        retry_count = int(getattr(state, "retry_count", 0))
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI strategist. Analyze previous attempts and suggest strategic "
                    "adjustments.\n\n"
                    "Respond with ONLY the next steps.\n"
                    "Start your response with a line containing exactly `FINAL:`.\n"
                    "Put the next steps on the following lines.\n\n"
                    "Do not include reasoning, analysis, or <think> tags."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: {state.prompt}\n\n"
                    f"Attempt #{retry_count + 1}:\n"
                    f"Original solution: {state.logs.get('execute', '(No execution result)')}\n"
                    f"Critique: {state.logs.get('critique', '(No critique provided)')}\n"
                    f"Refined solution: {state.logs.get('refine', '(No refined solution)')}\n"
                    f"Review: {state.logs.get('review', {}).get('result', '(No review provided)')}\n\n"
                    "Please reflect on what went wrong and suggest a better strategy for the next "
                    "attempt."
                ),
            },
        ]

        result = await provider.chat(messages, role="reflect", **kwargs)
        result = extract_final(result)
        usage = getattr(provider, "last_usage", None)
        state.logs["reflect"] = result

        if hasattr(state, "retry_count"):
            state.retry_count += 1
        else:
            state.retry_count = 1

        duration = time.time() - start_time
        state.log_node_timing("reflect", duration)

        resolution = getattr(state, "resolution_cache", {}).get("reflect", {})
        state.add_to_history(
            "reflect",
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
                "result_length": len(result) if result else 0,
            },
        )
        return state
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Reflect failed: {str(e)}"
        state.logs["reflect"] = error_msg
        state.log_node_timing("reflect", duration)
        state.add_to_history(
            "reflect", {"error": str(e), "duration": duration, "failed": True}
        )
        logger.error(error_msg)
        return state
