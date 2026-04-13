# anvil/orchestration/nodes/refine.py
import logging
import time
from typing import Any

from anvil.text_sanitize import extract_final

logger = logging.getLogger(__name__)


async def refine_node(state: Any) -> Any:
    """
    Refine the solution based on the critique using dynamically resolved provider configuration.

    Args:
        state: The current state object containing task and configuration

    Returns:
        Updated state with refined solution
    """
    start_time = time.time()

    try:
        logger.info("Starting solution refinement...")

        # Get provider and configuration using the new resolver
        provider, kwargs = state.get_provider_for_role("refine")

        if not provider:
            raise RuntimeError("No provider available for refine role")

        system = (getattr(state, "prompts", {}) or {}).get(
            "refine", "You are tasked with improving a solution based on critique."
        )
        system = (
            system
            + "\n\nRespond with ONLY the improved solution.\n"
            + "Start your response with a line containing exactly `FINAL:`.\n"
            + "Put the improved solution on the following lines.\n\n"
            + "Do not include reasoning, analysis, or <think> tags."
        )

        # Create chat messages with the execution result and critique
        messages = [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": f"Task: {state.prompt}\n\nOriginal solution:\n{state.logs.get('execute', '(No execution result)')}\n\nCritique:\n{state.logs.get('critique', '(No critique provided)')}\n\nPlease provide an improved solution addressing the critique.",
            },
        ]

        # Generate refined solution using chat with role-specific configuration
        result = await provider.chat(messages, role="refine", **kwargs)
        result = extract_final(result)

        usage = getattr(provider, "last_usage", None)
        usage_meta = (
            {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            }
            if usage is not None
            else None
        )

        # Store the result
        state.logs["refine"] = result

        # Log timing and history
        duration = time.time() - start_time
        state.log_node_timing("refine", duration)
        resolution = getattr(state, "resolution_cache", {}).get("refine", {})
        state.add_to_history(
            "refine",
            {
                "provider_name": resolution.get("provider_name", "unknown"),
                "model_name": resolution.get(
                    "model_name", getattr(provider, "model_name", "unknown")
                ),
                "kwargs": kwargs,
                "duration": duration,
                "usage": usage_meta,
                "result_length": len(result) if result else 0,
            },
        )

        logger.info(f"Refinement completed in {duration:.2f}s")

        return state

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Refinement failed: {str(e)}"

        state.logs["refine"] = error_msg
        state.log_node_timing("refine", duration)
        state.add_to_history(
            "refine", {"error": str(e), "duration": duration, "failed": True}
        )

        logger.error(f"Refine node error: {error_msg}")
        return state
