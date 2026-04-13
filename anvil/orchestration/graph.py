# anvil/orchestration/graph.py
def create_forge_graph():
    """Always create and return the LangGraph executor (Simple graph deprecated)."""
    import os

    from anvil.orchestration.langgraph_executor import LangGraphExecutor

    checkpoint = os.getenv("FORGE_LG_CHECKPOINT", "memory")
    db_path = os.getenv("FORGE_LG_DB_PATH", "forge_checkpoints.db")
    max_attempts = int(os.getenv("FORGE_LG_MAX_ATTEMPTS", "3"))

    print("Using LangGraph backend")
    return LangGraphExecutor(
        max_attempts=max_attempts,
        checkpoint=checkpoint,
        db_path=db_path,
    )
