from __future__ import annotations

from typing import Any, Dict


def calculate_rewards(state: Any) -> Dict[str, float]:
    """Compute simple rewards from the current state.

    Lightweight meta-learning signal until a full skrl trainer is added.
    Based on review outcome, refined output length, and retries.
    """
    review = state.logs.get("review", {})
    passed = bool(isinstance(review, dict) and review.get("pass", False))

    # Base reward
    reward = 1.0 if passed else -1.0

    # Shaping by refined length
    refined = state.logs.get("refine") or ""
    length = len(refined)
    if length:
        if length < 800:
            reward += 0.1
        elif length > 4000:
            reward -= 0.1

    # Penalize retries slightly
    retries = getattr(state, "retry_count", 0)
    reward -= 0.05 * max(0, int(retries))

    return {
        "reward": float(reward),
        "pass": 1.0 if passed else 0.0,
        "refine_length": float(length),
        "retries": float(retries),
    }
