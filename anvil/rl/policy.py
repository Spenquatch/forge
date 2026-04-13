from __future__ import annotations

from typing import Any, Dict

_LAST_UPDATE: Dict[str, Any] = {}


def update_model_selection_policy(state: Any, rewards: Dict[str, float]) -> None:
    """Placeholder hook to record a simple policy update signal.

    In a future iteration, this will delegate to a skrl PPO agent that
    learns a mapping from task features to provider choices and parameters.
    """
    global _LAST_UPDATE
    _LAST_UPDATE = {
        "reward": float(rewards.get("reward", 0.0)),
        "passed": bool(rewards.get("pass", 0.0) > 0.5),
        "provider_choices": dict(state.pipeline or {}),
    }


def summarize_policy_updates() -> Dict[str, Any]:
    """Return a short summary of the latest policy update."""
    return dict(_LAST_UPDATE)
