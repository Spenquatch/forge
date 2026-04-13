# anvil/leadership_adjustments.py
"""Leadership adjustments module for failure analysis and strategy adjustment."""

from typing import Any, Dict


def analyze_failure(exe: Any, cri: Any, refi: Any, rev: Any) -> Dict[str, Any]:
    """
    Analyze execution failure to determine adjustments.

    Args:
        exe: Execute node result
        cri: Critique node result
        refi: Refine node result
        rev: Review node result

    Returns:
        Analysis dictionary with failure reason and hints
    """
    text = "" if not isinstance(rev, dict) else (rev.get("result") or "")
    return {
        "reason": (text[:200] or "Unspecified"),
        "hints": ["Consider lowering temperature", "Try alternative provider"],
    }


def adjust_pipeline(
    pipeline: Dict[str, str], analysis: Dict[str, Any]
) -> Dict[str, str]:
    """
    Adjust provider pipeline based on failure analysis.

    Args:
        pipeline: Current provider pipeline
        analysis: Failure analysis

    Returns:
        Adjusted provider pipeline
    """
    # Simple provider flip between two common options
    new = dict(pipeline)
    for role in new:
        if new[role] == "openai":
            new[role] = "anthropic"
        elif new[role] == "anthropic":
            new[role] = "openai"
    return new


def adjust_prompts(prompts: Dict[str, str], analysis: Dict[str, Any]) -> Dict[str, str]:
    """
    Adjust prompts based on failure analysis.

    Args:
        prompts: Current prompts
        analysis: Failure analysis

    Returns:
        Adjusted prompts
    """
    return dict(prompts)  # no-op v1.2


def adjust_parameters(state, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adjust execution parameters based on failure analysis.

    Args:
        state: ForgeState instance
        analysis: Failure analysis

    Returns:
        Adjusted parameters
    """
    # Nudge temperature down for execute/critique
    return {
        "execute": {"temperature": 0.2},
        "critique": {"temperature": 0.2},
    }
