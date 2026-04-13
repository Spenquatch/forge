# anvil/orchestration/nodes/orchestrator.py
"""Orchestrator node for LangGraph - determines strategy and provider selection."""

import time

from anvil import leadership_analysis as la
from anvil import leadership_prompts as lp
from anvil.leadership_interface import ProviderSelectionStrategy
from anvil.orchestration.state import ForgeState


async def orchestrator_node(state: ForgeState) -> ForgeState:
    """
    Orchestrator node that analyzes the task and sets up execution strategy.

    Args:
        state: Current ForgeState

    Returns:
        Updated ForgeState with strategy, prompts, and provider pipeline
    """
    start_time = time.time()

    try:
        # Analyze task characteristics
        task_type = la.analyze_task_type(state.task)
        complexity = la.estimate_complexity(state.task)

        # Provider selection per role (simple policy for v1.2)
        strategy = ProviderSelectionStrategy()
        pipeline = state.pipeline.copy() if state.pipeline else {}

        # Assign providers for each role if not already set
        for role in ["execute", "critique", "refine", "review", "reflect"]:
            if role not in pipeline:
                decision = strategy.make_decision(
                    context=la.provider_context(state, role)
                )
                # Extract provider from decision
                recommended_provider = decision.recommended_action.get(
                    "provider", "openai"
                )
                pipeline[role] = recommended_provider

        # Select prompts based on task analysis
        prompts = lp.select_prompts(task_type=task_type, complexity=complexity)

        # Update state with orchestration decisions
        state.pipeline = pipeline
        state.prompts = prompts
        state.task_metadata = {"type": task_type, "complexity": complexity}
        state.strategy = f"{task_type}_{complexity}"

        # Record history and timing
        duration = time.time() - start_time
        state.add_to_history(
            "orchestrator",
            {"duration": duration, "info": f"Set strategy: {state.strategy}"},
        )
        state.log_node_timing("orchestrator", duration)

    except Exception as e:
        # Record error in history
        duration = time.time() - start_time
        state.add_to_history(
            "orchestrator", {"duration": duration, "info": f"Error: {str(e)[:100]}"}
        )
        raise

    return state
