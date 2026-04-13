# anvil/orchestration/nodes/finalize.py
"""Finalize node for LangGraph - sets final result and completion status."""

import time

from anvil.orchestration.state import ForgeState
from anvil.text_sanitize import extract_final


async def finalize_node(state: ForgeState) -> ForgeState:
    """
    Finalize node that sets the final result and completion status.

    Args:
        state: Current ForgeState

    Returns:
        Updated ForgeState with final result
    """
    start_time = time.time()

    try:
        # Check if review passed
        passed = bool(state.logs.get("review", {}).get("pass"))

        # Get the final result text (prefer refined version, fallback to execute)
        result_text = state.logs.get("refine") or state.logs.get("execute") or ""
        result_text = extract_final(result_text)

        # Set the final result with appropriate status
        state.set_result(result_text, status=("success" if passed else "failed"))

        # Record history and timing
        duration = time.time() - start_time
        state.add_to_history(
            "finalize",
            {"duration": duration, "info": f"Status: {state.completion_status}"},
        )
        state.log_node_timing("finalize", duration)

    except Exception as e:
        # Record error in history
        duration = time.time() - start_time
        state.add_to_history(
            "finalize", {"duration": duration, "info": f"Error: {str(e)[:100]}"}
        )
        raise

    return state
