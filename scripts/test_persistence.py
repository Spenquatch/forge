#!/usr/bin/env python
"""
Test script for persistence functionality.

This script verifies that the persistence mechanisms for performance metrics
and leadership decisions are working correctly, by:
1. Recording test metrics
2. Making test leadership decisions
3. Showing the data is saved between runs
"""

import argparse
import asyncio
import os
import sys

# Ensure repo root is on sys.path when executing this script directly.
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Import required modules
from anvil.leadership_interface import (
    DecisionContext,
    DecisionOutcome,
    ExecutionContext,
    get_leadership_orchestrator,
)
from anvil.performance_monitor import get_performance_monitor
from anvil.persistence_manager import get_persistence_manager


async def test_record_data():
    """Record test data for both performance and leadership."""
    print("🧪 TEST PERSISTENCE: RECORDING DATA")
    print("=" * 60)

    # Initialize persistence manager
    persistence = get_persistence_manager()
    print(f"Storage directory: {persistence.storage_dir}")

    # Get monitor instance
    monitor = get_performance_monitor()
    print(f"Monitor instance ID: {id(monitor)}")

    # Record test performance data
    print("\n📊 Recording test performance data...")
    for i in range(3):
        provider = f"test_provider_{i}"
        monitor.record_request(provider, 0.5 + i * 0.1, True)
        print(
            f"  Recorded request for {provider}: duration={0.5 + i * 0.1}s, success=True"
        )

    # Verify performance data was recorded
    metrics = monitor.get_metrics()
    print(f"  Recorded metrics for {len(metrics)} providers")
    for provider, data in metrics.items():
        print(
            f"  • {provider}: {data.total_requests} requests, {data.avg_duration:.2f}s avg"
        )

    # Get leadership instance
    leadership = get_leadership_orchestrator()
    print(f"\nLeadership instance ID: {id(leadership)}")

    # Make test leadership decisions
    print("🧠 Making test leadership decisions...")

    # Create test execution context
    context = ExecutionContext(task="Test persistence", role="execute", attempt_count=1)

    # Make provider selection decision
    provider_decision = leadership.request_decision(
        DecisionContext.PROVIDER_SELECTION, context
    )
    print(f"  Made provider selection decision: {provider_decision.decision_id}")

    # Make parameter tuning decision
    param_decision = leadership.request_decision(
        DecisionContext.PARAMETER_TUNING, context
    )
    print(f"  Made parameter tuning decision: {param_decision.decision_id}")

    # Report success for first decision
    leadership.report_outcome(
        provider_decision.decision_id,
        DecisionOutcome.SUCCESS,
        {"success_rate": 100.0, "execution_time": 1.5},
    )
    print(f"  Reported success for decision: {provider_decision.decision_id}")

    # Verify leadership data was recorded
    summary = leadership.get_learning_summary()
    print(f"  Decisions recorded: {summary['total_decisions']}")
    print(f"  Learning events recorded: {summary['total_learning_events']}")

    # Save all data
    print("\n💾 Saving all persistence data...")
    persistence.save_all()
    print("  Data saved successfully")

    print("\n✅ Test data recording complete")
    print(
        "Now run 'poetry run python scripts/test_persistence.py verify' to check persistence"
    )


async def test_verify_data():
    """Verify test data was correctly persisted."""
    print("🧪 TEST PERSISTENCE: VERIFYING DATA")
    print("=" * 60)

    # Initialize persistence manager
    persistence = get_persistence_manager()
    print(f"Storage directory: {persistence.storage_dir}")

    # Get monitor instance - should load persisted data
    monitor = get_performance_monitor()
    print(f"Monitor instance ID: {id(monitor)}")

    # Verify performance data was loaded
    metrics = monitor.get_metrics()
    print(f"\n📊 Loaded metrics for {len(metrics)} providers")

    if not metrics:
        print("❌ No performance metrics were loaded!")
    else:
        for provider, data in metrics.items():
            print(
                f"  • {provider}: {data.total_requests} requests, {data.avg_duration:.2f}s avg"
            )
        print("✅ Performance metrics were correctly persisted and loaded")

    # Get leadership instance - should load persisted data
    leadership = get_leadership_orchestrator()
    print(f"\n🧠 Leadership instance ID: {id(leadership)}")

    # Verify leadership data was loaded
    summary = leadership.get_learning_summary()
    print(f"  Decisions loaded: {summary['total_decisions']}")
    print(f"  Learning events loaded: {summary['total_learning_events']}")

    if summary["total_decisions"] == 0:
        print("❌ No leadership decisions were loaded!")
    else:
        print("✅ Leadership decisions were correctly persisted and loaded")

    print("\n📈 PERSISTENCE TEST SUMMARY")
    print("=" * 60)
    if len(metrics) > 0 and summary["total_decisions"] > 0:
        print(
            "✅ Persistence test PASSED: Both performance and leadership data were correctly persisted"
        )
    elif len(metrics) > 0:
        print(
            "⚠️  Persistence test PARTIAL: Only performance data was correctly persisted"
        )
    elif summary["total_decisions"] > 0:
        print(
            "⚠️  Persistence test PARTIAL: Only leadership data was correctly persisted"
        )
    else:
        print("❌ Persistence test FAILED: No data was persisted")


async def main():
    """Main function for persistence tests."""
    parser = argparse.ArgumentParser(description="Test persistence functionality")
    parser.add_argument(
        "action",
        choices=["record", "verify"],
        help="Action to perform (record test data or verify persistence)",
    )

    args = parser.parse_args()

    if args.action == "record":
        await test_record_data()
    else:
        await test_verify_data()


if __name__ == "__main__":
    asyncio.run(main())
