# anvil/orchestration/nodes/meta_learning.py
"""Meta-learning node for LangGraph - learns from execution and updates policies."""

import time

from anvil.orchestration.state import ForgeState
from anvil.rl.policy import summarize_policy_updates, update_model_selection_policy
from anvil.rl.rewards import calculate_rewards


async def meta_learning_node(state: ForgeState) -> ForgeState:
    """
    Meta-learning node that learns from execution results.

    Args:
        state: Current ForgeState

    Returns:
        Updated ForgeState with learning logs
    """
    start_time = time.time()

    try:
        # Calculate rewards based on execution results
        rewards = calculate_rewards(state)

        # Update model selection policy based on rewards
        update_model_selection_policy(state, rewards)

        # Log meta-learning results
        state.logs["meta_learning"] = {
            "rewards": rewards,
            "policy_updates": summarize_policy_updates(),
        }

        # Record history and timing
        duration = time.time() - start_time
        reward_value = rewards.get("reward", 0.0) if isinstance(rewards, dict) else 0.0
        state.add_to_history(
            "meta_learning",
            {"duration": duration, "info": f"Reward: {reward_value:.2f}"},
        )
        state.log_node_timing("meta_learning", duration)

    except Exception as e:
        # Record error in history
        duration = time.time() - start_time
        state.add_to_history(
            "meta_learning", {"duration": duration, "info": f"Error: {str(e)[:100]}"}
        )
        # Don't raise - meta-learning is optional

    return state
