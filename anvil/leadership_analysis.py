# anvil/leadership_analysis.py
"""Leadership analysis module for task type and complexity analysis."""

from anvil.leadership_interface import ExecutionContext


def analyze_task_type(task: str) -> str:
    """
    Analyze the task to determine its type.

    Args:
        task: The task description

    Returns:
        Task type string (coding, analytical, creative, general)
    """
    t = task.lower()
    if any(
        k in t
        for k in ["code", "function", "refactor", "bug", "implement", "class", "method"]
    ):
        return "coding"
    if any(k in t for k in ["explain", "analyze", "summarize", "review", "compare"]):
        return "analytical"
    if any(k in t for k in ["write", "story", "poem", "creative", "haiku", "essay"]):
        return "creative"
    return "general"


def estimate_complexity(task: str) -> str:
    """
    Estimate task complexity based on task description.

    Args:
        task: The task description

    Returns:
        Complexity level (low, medium, high)
    """
    n = len(task)
    if n < 60:
        return "low"
    if n < 200:
        return "medium"
    return "high"


def provider_context(state, role: str) -> ExecutionContext:
    """
    Create execution context for provider selection.

    Args:
        state: ForgeState instance
        role: The role (execute, critique, refine, review, reflect)

    Returns:
        ExecutionContext for provider selection
    """
    return ExecutionContext(
        task=state.task,
        role=role,
        current_provider=state.pipeline.get(role),
        attempt_count=int(getattr(state, "retry_count", 0)),
        previous_results=[
            state.logs.get(r)
            for r in ("execute", "critique", "refine", "review")
            if state.logs.get(r)
        ],
        performance_metrics={},
        error_history=(
            [str(state.logs.get("review", {}).get("result", ""))]
            if state.logs.get("review")
            else []
        ),
        metadata={"strategy": getattr(state, "strategy", "default")},
    )
