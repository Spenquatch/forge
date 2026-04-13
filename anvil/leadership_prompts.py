# anvil/leadership_prompts.py
"""Leadership prompts module for role-based prompt selection."""

from typing import Dict

BASE = {
    "execute": "You are a precise code generator. Favor correctness and clarity.",
    "critique": "You are a critical reviewer. Identify flaws and suggest fixes.",
    "refine": "You are an editor improving the solution based on critique.",
    "review": "You are a QA reviewer. Start with ['PASS'] or ['FAIL'].",
    "reflect": "You are an AI strategist. Propose better next steps.",
}


def select_prompts(task_type: str, complexity: str) -> Dict[str, str]:
    """
    Select prompts based on task type and complexity.

    Args:
        task_type: Type of task (coding, analytical, creative, general)
        complexity: Complexity level (low, medium, high)

    Returns:
        Dictionary of role-specific prompts
    """
    # Simple mapping for v1.2; can be expanded by type/complexity
    return dict(BASE)
