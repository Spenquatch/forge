# tests/test_langgraph_parity.py
"""Validation tests to ensure the LangGraph backend produces expected results."""


import pytest

from anvil.orchestration.langgraph_executor import LangGraphExecutor


@pytest.mark.asyncio
async def test_execution_basic(mock_providers):
    """Test that the LangGraph backend produces a non-empty result and runs core nodes."""
    task = "Write a haiku about Python"
    lg = LangGraphExecutor()
    lg_result = await lg.execute(task)
    assert lg_result.task == task
    assert "execute" in lg_result.logs
    assert lg_result.result is not None
    # Key nodes should be present
    for node in ["execute", "critique", "refine", "review"]:
        assert node in lg_result.logs, f"LangGraph missing {node} node"
    print(f"✅ LangGraph execution test passed! Result: {lg_result.result[:50]}...")


@pytest.mark.asyncio
async def test_state_fields_parity(mock_providers):
    """Test that new ForgeState fields are properly set by LangGraph."""
    task = "Calculate 2 + 2"

    # Run with LangGraphExecutor
    lg = LangGraphExecutor()
    result = await lg.execute(task)

    # Check new fields are set
    assert result.completion_status in ["pending", "success", "failed"]
    assert result.thread_id is not None
    assert result.strategy is not None
    assert isinstance(result.prompts, dict)
    assert isinstance(result.task_metadata, dict)

    print("✅ State fields test passed!")
    print(f"  Status: {result.completion_status}")
    print(f"  Strategy: {result.strategy}")
    print(f"  Thread ID: {result.thread_id}")


@pytest.mark.asyncio
async def test_retry_mechanism_parity(mock_providers):
    """Test that retry mechanism works in LangGraph."""
    task = "Complex task that might fail"

    # Create executor with low max attempts for testing
    lg = LangGraphExecutor(max_attempts=2)
    result = await lg.execute(task)

    # Check that result is set regardless of success/failure
    assert result.completion_status in ["success", "failed"]
    assert result.result is not None or result.error_state is not None

    # If retries happened, check retry count
    if result.retry_count > 0:
        assert result.retry_count <= 2  # Should not exceed max_attempts
        assert "monitor" in result.logs  # Monitor node should have run

    print("✅ Retry mechanism test passed!")
    print(f"  Retry count: {result.retry_count}")
    print(f"  Final status: {result.completion_status}")
