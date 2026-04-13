# anvil/orchestration/nodes/execute.py
"""
Execute node with hot-swappable provider support.
Uses the new configuration resolver for dynamic provider selection.
"""

import logging
import time
from typing import Any

from anvil.text_sanitize import extract_final

logger = logging.getLogger(__name__)


async def execute_node(state: Any) -> Any:
    """
    Execute the task using dynamically resolved provider configuration.

    This node demonstrates the hot-swap capabilities:
    - Provider can be changed at runtime
    - Model can be overridden per execution
    - Kwargs can be adjusted dynamically

    Args:
        state: ForgeState object with task and configuration

    Returns:
        Updated state with execution results
    """
    start_time = time.time()

    try:
        logger.info(f"Starting execution for task: {state.task[:50]}...")

        # Get provider and configuration using the new resolver
        provider, kwargs = state.get_provider_for_role("execute")

        if not provider:
            raise RuntimeError("No provider available for execute role")

        logger.debug(f"Using provider with kwargs: {kwargs}")

        system = (getattr(state, "prompts", {}) or {}).get(
            "execute", "You are a helpful assistant."
        )
        system = (
            system
            + "\n\nRespond with ONLY the final answer.\n"
            + "Start your response with a line containing exactly `FINAL:`.\n"
            + "Put the answer on the following lines.\n\n"
            + "Do not include reasoning, analysis, or <think> tags."
        )

        # Prefer chat for "execute" so local models get a proper chat template.
        result = await provider.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": state.prompt},
            ],
            role="execute",
            **kwargs,
        )
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
        state.logs["execute"] = result

        # Log timing
        duration = time.time() - start_time
        state.log_node_timing("execute", duration)

        # Add to history with metadata
        resolution = getattr(state, "resolution_cache", {}).get("execute", {})
        state.add_to_history(
            "execute",
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

        logger.info(f"Execution completed in {duration:.2f}s")
        logger.debug(f"Result preview: {result[:100] if result else 'No result'}...")

        return state

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Execution failed: {str(e)}"

        # Store error in logs
        state.logs["execute"] = error_msg
        state.log_node_timing("execute", duration)

        # Add to history with error metadata
        state.add_to_history(
            "execute", {"error": str(e), "duration": duration, "failed": True}
        )

        logger.error(f"Execute node error: {error_msg}")

        # Don't raise - let the pipeline continue to handle the error
        return state
