# anvil/orchestration/nodes/monitor.py
"""Monitor node for LangGraph - analyzes failures and adjusts strategy."""

import time

from anvil import leadership_adjustments as ladj
from anvil.orchestration.state import ForgeState


async def monitor_node(state: ForgeState) -> ForgeState:
    """
    Monitor node that analyzes execution failures and adjusts strategy.

    Args:
        state: Current ForgeState

    Returns:
        Updated ForgeState with adjusted strategy
    """
    start_time = time.time()

    try:
        # Analyze failure from execution logs
        analysis = ladj.analyze_failure(
            state.logs.get("execute"),
            state.logs.get("critique"),
            state.logs.get("refine"),
            state.logs.get("review"),
        )

        # Adjust pipeline based on failure analysis
        pipeline = ladj.adjust_pipeline(state.pipeline, analysis)

        # Adjust prompts based on failure analysis
        prompts = ladj.adjust_prompts(state.prompts, analysis)

        # Get parameter adjustments
        overrides = ladj.adjust_parameters(state, analysis)

        # Update state with adjustments
        state.pipeline = pipeline
        state.prompts = prompts
        state.update_strategy(overrides)

        # Increment retry count
        state.retry_count = int(getattr(state, "retry_count", 0)) + 1

        # Log the monitoring analysis
        state.logs["monitor"] = analysis

        # Record history and timing
        duration = time.time() - start_time
        state.add_to_history(
            "monitor",
            {
                "duration": duration,
                "info": f"Retry {state.retry_count}, adjusted strategy",
            },
        )
        state.log_node_timing("monitor", duration)

    except Exception as e:
        # Record error in history
        duration = time.time() - start_time
        state.add_to_history(
            "monitor", {"duration": duration, "info": f"Error: {str(e)[:100]}"}
        )
        raise

    return state
