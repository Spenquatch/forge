# anvil/orchestration/nodes/critique.py
import logging
import time
from typing import Any

from anvil.text_sanitize import extract_final

logger = logging.getLogger(__name__)


async def critique_node(state: Any) -> Any:
    """
    Critique the execution result using dynamically resolved provider configuration.

    Args:
        state: The current state object containing task and configuration

    Returns:
        Updated state with critique results
    """
    start_time = time.time()

    try:
        logger.info("Starting critique analysis...")

        # Get provider and configuration using the new resolver
        provider, kwargs = state.get_provider_for_role("critique")

        if not provider:
            raise RuntimeError("No provider available for critique role")

        system = (getattr(state, "prompts", {}) or {}).get(
            "critique",
            "You are a critical reviewer analyzing the quality of the provided solution.",
        )
        system = (
            system
            + "\n\nRespond with ONLY the critique.\n"
            + "Start your response with a line containing exactly `FINAL:`.\n"
            + "Put the critique on the following lines.\n\n"
            + "Do not include reasoning traces, analysis, or <think> tags."
        )

        # Create chat messages with the execution result
        messages = [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": f"Task: {state.prompt}\n\nSolution:\n{state.logs.get('execute', '(No execution result)')}",
            },
        ]

        # Generate critique using chat with role-specific configuration
        result = await provider.chat(messages, role="critique", **kwargs)
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
        state.logs["critique"] = result

        # Log timing and history
        duration = time.time() - start_time
        state.log_node_timing("critique", duration)
        resolution = getattr(state, "resolution_cache", {}).get("critique", {})
        state.add_to_history(
            "critique",
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

        logger.info(f"Critique completed in {duration:.2f}s")

        return state

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Critique failed: {str(e)}"

        state.logs["critique"] = error_msg
        state.log_node_timing("critique", duration)
        state.add_to_history(
            "critique", {"error": str(e), "duration": duration, "failed": True}
        )

        logger.error(f"Critique node error: {error_msg}")
        return state
