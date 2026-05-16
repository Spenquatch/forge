"""
Enhanced Anvil CLI entrypoint (Phase 2 features).
Includes leadership decisions, performance monitoring, validation, and rich logs.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any, Optional, cast

from dotenv import load_dotenv

# Ensure package root is on path (defensive when executed directly)
pkg_root = os.path.dirname(os.path.abspath(__file__))
if pkg_root not in sys.path:
    sys.path.insert(0, os.path.dirname(pkg_root))

# Load environment variables
load_dotenv()

from anvil.cli_utils import (
    build_state_pipeline,
    format_mapping_diff,
    format_pipeline_map,
    format_role_overrides,
    normalize_requested_pipeline,
    provider_selection_status,
)
from anvil.config_validator import (
    ConfigurationValidator,
    ValidationLevel,
    ValidationReport,
    ValidationResult,
    ValidationType,
    get_config_validator,
    validate_config,
)
from anvil.leadership_interface import (
    DecisionContext,
    DecisionOutcome,
    ExecutionContext,
    get_leadership_orchestrator,
)
try:
    from anvil.orchestration.graph import create_forge_graph
    from anvil.orchestration.langgraph_executor import LangGraphExecutor
    from anvil.orchestration.state import ForgeState, create_state
except Exception:  # pragma: no cover - handled at command runtime
    create_forge_graph = None
    LangGraphExecutor = None
    ForgeState = None
    create_state = None

from anvil.orchestrator import reload_config

# Enhanced Phase 2 modules
from anvil.performance_monitor import MetricType, get_performance_monitor
from anvil.persistence_manager import get_persistence_manager
from anvil.providers import get_provider_exact
from anvil.usage import TokenUsage, estimate_cost_usd
from anvil.harness.cli import _summary_exit_code
from anvil.harness.executor import HarnessLangGraphExecutor
from anvil.harness.runner import HarnessError, HarnessRunner

ROLE_NODES = ["execute", "critique", "refine", "review", "reflect"]
_STREAM_PROGRESS_EVENTS = {"on_chain_start", "on_chain_end"}
_STREAM_PROGRESS_NODES = {
    "LangGraph",
    "orchestrator",
    "execute",
    "critique",
    "refine",
    "review",
    "monitor",
    "reflect",
    "finalize",
}


def _validate_requested_provider_configurations(
    validator: ConfigurationValidator,
    providers_config: dict[str, Any],
    requested_pipeline: dict[str, str],
) -> ValidationReport:
    selected = {
        provider_name
        for provider_name in requested_pipeline.values()
        if isinstance(provider_name, str) and provider_name and provider_name != "auto"
    }
    if not selected:
        return validate_config(providers_config)

    report = ValidationReport()
    for provider_name in sorted(selected):
        config = providers_config.get(provider_name)
        if config is None:
            report.add_result(
                ValidationResult(
                    valid=False,
                    level=ValidationLevel.CRITICAL,
                    validation_type=ValidationType.SCHEMA,
                    message="Provider is not configured",
                    component=provider_name,
                    suggestion="Choose a configured provider or add it to config/models.yaml",
                )
            )
            continue
        provider_report = validator.validate_provider_config(provider_name, config)
        for result in provider_report.results:
            report.add_result(result)
    return report


def _should_print_stream_event(event: dict[str, Any], *, verbose: bool) -> bool:
    if verbose:
        return True

    ev = event.get("event")
    node = event.get("node")
    if ev not in _STREAM_PROGRESS_EVENTS:
        return False
    if not isinstance(node, str) or not node:
        return False

    # In non-verbose mode, only show high-level node transitions.
    return node in _STREAM_PROGRESS_NODES or node in ROLE_NODES


def _role_failed(history: list[dict[str, Any]], role: str) -> bool:
    for entry in reversed(history):
        if entry.get("node") != role:
            continue
        metadata = entry.get("metadata") or {}
        return bool(metadata.get("failed") or metadata.get("error"))
    return False


def _role_usage(history: list[dict[str, Any]], role: str) -> Optional[dict[str, Any]]:
    for entry in reversed(history):
        if entry.get("node") != role:
            continue
        metadata = entry.get("metadata") or {}
        usage = metadata.get("usage")
        if isinstance(usage, dict):
            return usage
        return None
    return None


def _ensure_orchestration_runtime() -> None:
    """Fail with a clear message when orchestration deps are unavailable."""
    if create_forge_graph is None or LangGraphExecutor is None or ForgeState is None:
        raise RuntimeError(
            "Forge orchestration dependencies are unavailable. Install the project "
            "dependencies (including langgraph) before using run/stream/hotswap commands."
        )


async def run_command(
    task: str,
    provider: str = "auto",
    enable_leadership: bool = True,
    role_providers: Optional[dict[str, str]] = None,
) -> None:
    _ensure_orchestration_runtime()
    base_provider_arg = provider
    print(f"🚀 Enhanced Forge Run: '{task}'")
    print(
        f"Base provider (--provider): {base_provider_arg} | Leadership: {'✅' if enable_leadership else '❌'}"
    )
    if role_providers:
        print(f"Role overrides: {format_role_overrides(role_providers)}")
    print(
        "Leadership provider selection: "
        + provider_selection_status(
            base_provider=base_provider_arg,
            enable_leadership=enable_leadership,
            role_providers=role_providers,
        )
    )
    print("=" * 60)

    # Load configuration
    print("📋 Loading and validating configuration...")
    providers_config, _ = reload_config()
    validator = get_config_validator()

    # Initialize persistence/monitor/leadership
    get_persistence_manager()
    monitor = get_performance_monitor()
    leadership = get_leadership_orchestrator()

    decision_info: dict[str, Any] = {
        "decision_id": None,
        "made_decision": False,
        "param_decision_id": None,
    }

    # Leadership provider selection
    if provider == "auto" and enable_leadership and not role_providers:
        print("\n🧠 Requesting leadership decision for provider selection...")
        exec_ctx = ExecutionContext(task=task, role="execute", attempt_count=0)
        decision = leadership.request_decision(
            DecisionContext.PROVIDER_SELECTION, exec_ctx
        )
        decision_info["decision_id"] = decision.decision_id
        decision_info["made_decision"] = True
        if decision.recommended_action.get("action") == "select_provider":
            provider = decision.recommended_action["provider"]
            print(f"🎯 Leadership selected: {provider}")
            print(f"   Decision ID: {decision.decision_id}")
            print(f"   Rationale: {decision.rationale}")
            print(f"   Confidence: {decision.confidence:.2%}")
        else:
            provider = "openai"
            print(f"⚠️  Leadership couldn't select provider, using fallback: {provider}")

    # Create state with base provider + per-role overrides (if provided)
    requested_pipeline = normalize_requested_pipeline(provider, role_providers)
    print(f"Effective pipeline: {format_pipeline_map(requested_pipeline)}")

    validation_report = _validate_requested_provider_configurations(
        validator,
        providers_config,
        requested_pipeline,
    )
    if not validation_report.is_valid:
        print("❌ Configuration validation failed!")
        print(validation_report.format_report())
        return
    elif validation_report.has_warnings:
        print("⚠️  Configuration has warnings:")
        for warning in validation_report.get_results_by_level(ValidationLevel.WARNING):
            print(f"  • {warning}")
            if warning.suggestion:
                print(f"    💡 {warning.suggestion}")
    else:
        print("✅ Configuration validation passed!")

    pipeline = build_state_pipeline(
        base_provider=provider, role_providers=role_providers
    )
    state = ForgeState(task, pipeline=pipeline)
    run_id = state.thread_id
    print(f"🆔 Run ID: {run_id}")

    # Optional leadership parameter tuning
    roles_to_tune = ["execute", "critique", "refine"]

    if not enable_leadership:
        print("🔧 Leadership parameter tuning: skipped (leadership disabled)")
    elif os.getenv("FORGE_DISABLE_PARAM_TUNING", "0") == "1":
        print("🔧 Leadership parameter tuning: skipped (FORGE_DISABLE_PARAM_TUNING=1)")
    elif role_providers:
        print("🔧 Leadership parameter tuning: skipped (role overrides provided)")
    else:
        before_kwargs_by_role = {
            role: state.role_kwargs(role) for role in roles_to_tune
        }
        param_ctx = ExecutionContext(
            task=task,
            role="execute",
            current_provider=provider,
            current_kwargs=before_kwargs_by_role["execute"],
        )
        param_decision = leadership.request_decision(
            DecisionContext.PARAMETER_TUNING, param_ctx
        )
        decision_info["param_decision_id"] = param_decision.decision_id
        print(
            f"🔧 Leadership parameter tuning: requested (Decision ID: {param_decision.decision_id})"
        )

        adjustments = param_decision.recommended_action.get("adjustments", {}) or {}
        if not adjustments:
            print("🔧 Leadership parameter adjustments: none")
        else:
            for role in roles_to_tune:
                state.set_kwargs_for_role(role, **adjustments)

            after_kwargs_by_role = {
                role: state.role_kwargs(role) for role in roles_to_tune
            }

            role_lines: list[str] = []
            for role in roles_to_tune:
                changes = format_mapping_diff(
                    before_kwargs_by_role[role], after_kwargs_by_role[role]
                )
                if changes:
                    role_lines.append(f"{role}: " + ", ".join(changes))

            if role_lines:
                print("🔧 Leadership parameter adjustments:")
                for line in role_lines:
                    print(f"   {line}")
            else:
                print("🔧 Leadership parameter adjustments: none")

    # Run graph and record performance
    print("\n⚡ Starting enhanced execution...")
    start_time = time.time()
    graph = create_forge_graph()
    success = False
    execution_time = 0.0
    actual_provider = provider
    try:
        heartbeat_seconds = float(os.getenv("FORGE_CLI_HEARTBEAT_SECONDS", "15"))
        run_task = asyncio.create_task(graph.run(state))
        last_heartbeat = time.time()
        while not run_task.done():
            if heartbeat_seconds <= 0:
                break
            await asyncio.sleep(min(heartbeat_seconds, 5.0))
            now = time.time()
            if now - last_heartbeat >= heartbeat_seconds and not run_task.done():
                elapsed = now - start_time
                print(
                    f"… still running ({elapsed:.0f}s). Tip: add `--stream` for live progress.",
                    flush=True,
                )
                last_heartbeat = now

        result_state = await run_task
        execution_time = time.time() - start_time
        success = True

        run_id = getattr(result_state, "thread_id", run_id)
        monitor.record_event(
            name="forge.run_total_duration",
            value=execution_time,
            metric_type=MetricType.TIMING,
            labels={"success": str(success)},
            metadata={
                "run_id": run_id,
                "provider_selection_decision_id": decision_info["decision_id"],
                "parameter_tuning_decision_id": decision_info["param_decision_id"],
            },
        )

        provider_totals: dict[str, float] = {}
        provider_role_counts: dict[str, int] = {}
        provider_token_totals: dict[str, dict[str, Any]] = {}
        provider_cost_totals: dict[str, float] = {}
        provider_role_token_totals: dict[str, dict[str, dict[str, Any]]] = {}
        provider_role_cost_totals: dict[str, dict[str, float]] = {}

        if getattr(result_state, "node_timings", None) and getattr(
            result_state, "resolution_cache", None
        ):
            for role in ROLE_NODES:
                duration = result_state.node_timings.get(role)
                resolution = result_state.resolution_cache.get(role, {})
                provider_name = resolution.get("provider_name")
                model_name = resolution.get("model_name")

                if duration is None or not provider_name:
                    continue

                role_success = not _role_failed(result_state.history, role)
                usage = _role_usage(result_state.history, role) or {}
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total_tokens = usage.get("total_tokens")

                if provider_name not in provider_role_token_totals:
                    provider_role_token_totals[provider_name] = {}
                if role not in provider_role_token_totals[provider_name]:
                    provider_role_token_totals[provider_name][role] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "has_usage": False,
                        "model_name": model_name,
                    }

                estimated_cost = None
                if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                    estimated_cost = estimate_cost_usd(
                        model_name,
                        TokenUsage(
                            input_tokens=input_tokens, output_tokens=output_tokens
                        ),
                    )
                    if estimated_cost is not None:
                        provider_cost_totals[provider_name] = (
                            provider_cost_totals.get(provider_name, 0.0)
                            + estimated_cost
                        )
                        if provider_name not in provider_role_cost_totals:
                            provider_role_cost_totals[provider_name] = {}
                        provider_role_cost_totals[provider_name][role] = (
                            provider_role_cost_totals[provider_name].get(role, 0.0)
                            + estimated_cost
                        )

                if provider_name not in provider_token_totals:
                    provider_token_totals[provider_name] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "has_usage": False,
                    }
                if (
                    isinstance(input_tokens, int)
                    and isinstance(output_tokens, int)
                    and isinstance(total_tokens, int)
                ):
                    provider_token_totals[provider_name]["input_tokens"] += input_tokens
                    provider_token_totals[provider_name][
                        "output_tokens"
                    ] += output_tokens
                    provider_token_totals[provider_name]["total_tokens"] += total_tokens
                    provider_token_totals[provider_name]["has_usage"] = True

                    provider_role_token_totals[provider_name][role][
                        "input_tokens"
                    ] += input_tokens
                    provider_role_token_totals[provider_name][role][
                        "output_tokens"
                    ] += output_tokens
                    provider_role_token_totals[provider_name][role][
                        "total_tokens"
                    ] += total_tokens
                    provider_role_token_totals[provider_name][role]["has_usage"] = True

                monitor.record_request(
                    provider_name,
                    duration,
                    role_success,
                    metadata={
                        "run_id": run_id,
                        "role": role,
                        "model_name": model_name,
                        "metric_scope": "role",
                        "provider_selection_decision_id": decision_info["decision_id"],
                        "parameter_tuning_decision_id": decision_info[
                            "param_decision_id"
                        ],
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "estimated_cost_usd": estimated_cost,
                    },
                )

                provider_totals[provider_name] = (
                    provider_totals.get(provider_name, 0.0) + duration
                )
                provider_role_counts[provider_name] = (
                    provider_role_counts.get(provider_name, 0) + 1
                )

        if enable_leadership and bool(decision_info.get("made_decision")):
            perf = {
                "success_rate": 100.0,
                "execution_time": execution_time,
                "result_quality": min(len(result_state.result or "") / 100, 10.0),
            }
            decision_id = decision_info.get("decision_id")
            if isinstance(decision_id, str):
                print(f"📈 Reporting success to leadership: {decision_id}")
                leadership.report_outcome(decision_id, DecisionOutcome.SUCCESS, perf)
            summary = leadership.get_learning_summary()
            print(
                f"✅ Learning recorded: {summary['total_decisions']} decisions, {summary['total_learning_events']} events"
            )

        # Enhanced results display
        print("\n" + "=" * 60)
        print("🎉 EXECUTION RESULTS")
        print("=" * 60)
        print("✅ Status: SUCCESS")
        print(f"🆔 Run ID: {run_id}")
        print(f"⏱️  Total Time: {execution_time:.2f}s")
        print(f"🔄 Nodes Executed: {len(result_state.history)}")
        if provider_totals:
            providers_used = ", ".join(sorted(provider_totals.keys()))
            print(f"🎯 Providers: {providers_used}")
            print("\n📊 Provider Breakdown (this run):")
            for provider_name in sorted(provider_totals.keys()):
                count = provider_role_counts.get(provider_name, 0)
                total = provider_totals[provider_name]
                print(f"   • {provider_name}: {count} role(s), {total:.2f}s")

            print("\n💸 Token/Cost Summary (this run):")
            for provider_name in sorted(provider_totals.keys()):
                tokens = provider_token_totals.get(provider_name, {})
                if tokens.get("has_usage"):
                    cost = provider_cost_totals.get(provider_name)
                    cost_str = f"${cost:.6f}" if cost is not None else "unknown"
                    print(
                        f"   • {provider_name}: input={tokens['input_tokens']}, output={tokens['output_tokens']}, total={tokens['total_tokens']}, cost={cost_str}"
                    )
                    role_tokens = provider_role_token_totals.get(provider_name, {})
                    for role in ROLE_NODES:
                        rt = role_tokens.get(role)
                        if not rt or not rt.get("has_usage"):
                            continue
                        role_cost = provider_role_cost_totals.get(
                            provider_name, {}
                        ).get(role)
                        role_cost_str = (
                            f"${role_cost:.6f}" if role_cost is not None else "unknown"
                        )
                        model_label = rt.get("model_name") or "unknown-model"
                        print(
                            f"     - {role} ({model_label}): input={rt['input_tokens']}, output={rt['output_tokens']}, total={rt['total_tokens']}, cost={role_cost_str}"
                        )
                else:
                    print(f"   • {provider_name}: tokens/cost unknown")

        history_nodes = [
            entry.get("node")
            for entry in getattr(result_state, "history", [])
            if entry.get("node")
        ]
        if history_nodes:
            print("\n🧭 Execution Path:")
            print("   • " + " → ".join(history_nodes))

            executed = set(history_nodes)
            skipped: list[str] = []
            passed = bool(
                getattr(result_state, "logs", {}).get("review", {}).get("pass")
            )
            max_attempts = int(os.getenv("FORGE_LG_MAX_ATTEMPTS", "3"))
            retry_count = int(getattr(result_state, "retry_count", 0))

            for node in ["monitor", "reflect"]:
                if node in executed:
                    continue
                if passed:
                    skipped.append(f"{node} skipped: review passed")
                elif retry_count >= max_attempts:
                    skipped.append(f"{node} skipped: max attempts reached")
                else:
                    skipped.append(f"{node} skipped: route not taken")

            if skipped:
                print("   • " + "; ".join(skipped))

        if getattr(result_state, "node_timings", None):
            print("\n📊 Node Performance:")
            for node, timing in result_state.node_timings.items():
                print(f"   • {node}: {timing:.2f}s")

        print("\n📝 Result:")
        print("-" * 40)
        print(result_state.result)

        if getattr(result_state, "resolution_cache", None):
            print("\n🔍 Configuration Resolutions:")
            for role, resolution in result_state.resolution_cache.items():
                print(
                    f"   • {role}: {resolution['provider_name']}/{resolution['model_name']}"
                )
                if resolution.get("fallback_used"):
                    print("     ⚠️  Used fallback")

        # RL meta-learning summary (if present)
        if "meta_learning" in result_state.logs:
            print("\n=== Meta-Learning ===")
            ml = result_state.logs["meta_learning"]
            rewards = ml.get("rewards", {})
            print(f"Reward: {rewards.get('reward')}")
            print(f"Pass: {bool(rewards.get('pass'))}")
            print(f"Refine length: {rewards.get('refine_length')}")
            print(f"Retries: {rewards.get('retries')}")

    except Exception as e:
        execution_time = time.time() - start_time
        success = False
        print(
            f"\n📊 Recording failure: provider={actual_provider}, time={execution_time:.2f}s, success={success}"
        )
        monitor.record_request(
            actual_provider,
            execution_time,
            success,
            metadata={
                "run_id": run_id,
                "metric_scope": "run_total",
                "provider_selection_decision_id": decision_info["decision_id"],
                "parameter_tuning_decision_id": decision_info["param_decision_id"],
            },
        )
        if enable_leadership and bool(decision_info.get("made_decision")):
            decision_id = decision_info.get("decision_id")
            if isinstance(decision_id, str):
                leadership.report_outcome(
                    decision_id,
                    DecisionOutcome.FAILURE,
                    {"success_rate": 0.0, "execution_time": execution_time},
                )
        print(f"\n❌ EXECUTION FAILED: {e}")


async def run_stream_command(
    task: str,
    provider: str = "auto",
    enable_leadership: bool = True,
    role_providers: Optional[dict[str, str]] = None,
    *,
    verbose_events: bool = False,
) -> None:
    """
    Stream execution events from LangGraph while still applying provider selection logic.

    Notes:
    - Streaming uses the LangGraph executor directly.
    - If a final output state is present in the end event, it is printed.
    """
    base_provider_arg = provider
    run_id = str(uuid.uuid4())
    print(f"📡 Forge Stream: '{task}'")
    print(
        f"Base provider (--provider): {base_provider_arg} | Leadership: {'✅' if enable_leadership else '❌'}"
    )
    print(f"🆔 Run ID: {run_id}")
    if role_providers:
        print(f"Role overrides: {format_role_overrides(role_providers)}")
    print(
        "Leadership provider selection: "
        + provider_selection_status(
            base_provider=base_provider_arg,
            enable_leadership=enable_leadership,
            role_providers=role_providers,
        )
    )
    print("=" * 60)

    # Load configuration
    print("📋 Loading and validating configuration...")
    providers_config, _ = reload_config()
    validator = get_config_validator()

    # Initialize persistence/monitor/leadership so data is saved during exit.
    get_persistence_manager()
    get_performance_monitor()
    leadership = get_leadership_orchestrator()

    # Leadership provider selection
    if provider == "auto" and enable_leadership and not role_providers:
        print("\n🧠 Requesting leadership decision for provider selection...")
        exec_ctx = ExecutionContext(task=task, role="execute", attempt_count=0)
        decision = leadership.request_decision(
            DecisionContext.PROVIDER_SELECTION, exec_ctx
        )
        if decision.recommended_action.get("action") == "select_provider":
            provider = decision.recommended_action["provider"]
            print(f"🎯 Leadership selected: {provider}")
            print(f"   Decision ID: {decision.decision_id}")
            print(f"   Rationale: {decision.rationale}")
            print(f"   Confidence: {decision.confidence:.2%}")
        else:
            provider = "openai"
            print(f"⚠️  Leadership couldn't select provider, using fallback: {provider}")

    # Build pipeline for streaming; if roles are set here, orchestrator node will not overwrite them.
    requested_pipeline = normalize_requested_pipeline(provider, role_providers)
    print(f"Effective pipeline: {format_pipeline_map(requested_pipeline)}")

    validation_report = _validate_requested_provider_configurations(
        validator,
        providers_config,
        requested_pipeline,
    )
    if not validation_report.is_valid:
        print("❌ Configuration validation failed!")
        print(validation_report.format_report())
        return
    elif validation_report.has_warnings:
        print("⚠️  Configuration has warnings:")
        for warning in validation_report.get_results_by_level(ValidationLevel.WARNING):
            print(f"  • {warning}")
            if warning.suggestion:
                print(f"    💡 {warning.suggestion}")
    else:
        print("✅ Configuration validation passed!")

    pipeline = build_state_pipeline(
        base_provider=provider, role_providers=role_providers
    )

    # Stream execution via LangGraphExecutor.
    executor = LangGraphExecutor(
        max_attempts=int(os.getenv("FORGE_LG_MAX_ATTEMPTS", "3")),
        checkpoint=os.getenv("FORGE_LG_CHECKPOINT", "memory"),
        db_path=os.getenv("FORGE_LG_DB_PATH", "forge_checkpoints.db"),
    )

    overrides: dict[str, Any] = {}

    if verbose_events:
        print("\n📡 Streaming execution events (verbose):\n")
    else:
        print(
            "\n📡 Streaming execution (node-level). Tip: add `--stream-verbose` for full trace.\n"
        )
    final_state: Optional[ForgeState] = None
    stream_start = time.time()
    node_start_times: dict[str, float] = {}
    node_end_times: dict[str, float] = {}
    node_counts: dict[str, int] = {}
    async for event in executor.stream_execution(
        task, overrides, pipeline=pipeline, thread_id=run_id
    ):
        if _should_print_stream_event(event, verbose=verbose_events):
            print(f"[{event.get('event')}] {event.get('node')}")
        node_name = event.get("node")
        if isinstance(node_name, str):
            node_counts[node_name] = node_counts.get(node_name, 0) + 1

        ev = event.get("event")
        now = float(event.get("time") or time.time())
        if ev == "on_chain_start" and isinstance(node_name, str):
            node_start_times[node_name] = now
        elif ev == "on_chain_end" and isinstance(node_name, str):
            node_end_times[node_name] = now

        if isinstance(event.get("final_state"), ForgeState):
            final_state = event["final_state"]

    stream_elapsed = time.time() - stream_start

    if final_state is not None:
        print("\n" + "=" * 60)
        print("🎉 STREAM COMPLETE (FINAL RESULT)")
        print("=" * 60)
        print(final_state.result)

        # Basic execution summary (stream mode)
        history = getattr(final_state, "history", []) or []
        history_nodes: list[str] = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            node = entry.get("node")
            if isinstance(node, str) and node:
                history_nodes.append(node)
        nodes_executed = len(history_nodes)
        execute_attempts = sum(1 for n in history_nodes if n == "execute")
        loops = max(0, execute_attempts - 1)

        print("\n📊 Stream Summary:")
        status = getattr(final_state, "completion_status", None) or (
            "success"
            if bool(getattr(final_state, "logs", {}).get("review", {}).get("pass"))
            else "failed"
        )
        print(f"   • Status: {str(status).upper()}")
        print(f"   • Run ID: {getattr(final_state, 'thread_id', run_id)}")
        print(f"   • Total Time: {stream_elapsed:.2f}s")
        print(f"   • Nodes Executed: {nodes_executed}")
        print(f"   • Attempts: {execute_attempts} (loops: {loops})")
        print(f"   • Retry Count: {int(getattr(final_state, 'retry_count', 0))}")

        if history_nodes:
            print("\n🧭 Execution Path:")
            print("   • " + " → ".join(history_nodes))

        if getattr(final_state, "node_timings", None):
            print("\n📊 Node Performance:")
            for node, timing in final_state.node_timings.items():
                print(f"   • {node}: {timing:.2f}s")
        else:
            # Fallback: best-effort timings from stream events.
            known_nodes = [
                "orchestrator",
                "execute",
                "critique",
                "refine",
                "review",
                "monitor",
                "reflect",
                "finalize",
            ]
            rows: list[tuple[str, float]] = []
            for node in known_nodes:
                start_t = node_start_times.get(node)
                end_t = node_end_times.get(node)
                if start_t is None or end_t is None or end_t < start_t:
                    continue
                rows.append((node, end_t - start_t))
            if rows:
                print("\n📊 Node Performance (approx):")
                for node, timing in rows:
                    print(f"   • {node}: {timing:.2f}s")

        # Provider breakdown (time + roles) using final state's resolved configs.
        provider_totals: dict[str, float] = {}
        provider_role_counts: dict[str, int] = {}
        if getattr(final_state, "node_timings", None) and getattr(
            final_state, "resolution_cache", None
        ):
            for role in ROLE_NODES:
                duration = final_state.node_timings.get(role)
                resolution = final_state.resolution_cache.get(role, {})
                provider_name = resolution.get("provider_name")
                if duration is None or not provider_name:
                    continue
                provider_totals[provider_name] = provider_totals.get(
                    provider_name, 0.0
                ) + float(duration)
                provider_role_counts[provider_name] = (
                    provider_role_counts.get(provider_name, 0) + 1
                )

        if provider_totals:
            print("\n📊 Provider Breakdown (this run):")
            for provider_name in sorted(provider_totals):
                print(
                    f"   • {provider_name}: {provider_role_counts.get(provider_name, 0)} role(s), {provider_totals[provider_name]:.2f}s"
                )

        providers: set[str] = set()
        if getattr(final_state, "resolution_cache", None):
            for role in ROLE_NODES:
                provider_name = final_state.resolution_cache.get(role, {}).get(
                    "provider_name"
                )
                if isinstance(provider_name, str) and provider_name:
                    providers.add(provider_name)

        if providers:
            provider_cost_totals: dict[str, float] = {}
            provider_token_totals: dict[str, dict[str, Any]] = {}
            provider_role_token_totals: dict[str, dict[str, dict[str, Any]]] = {}
            provider_role_cost_totals: dict[str, dict[str, float]] = {}

            for role in ROLE_NODES:
                resolution = getattr(final_state, "resolution_cache", {}).get(role, {})
                provider_name = resolution.get("provider_name")
                if not isinstance(provider_name, str) or not provider_name:
                    continue
                model_name_value = resolution.get("model_name")
                model_name = (
                    model_name_value if isinstance(model_name_value, str) else None
                )

                usage = _role_usage(getattr(final_state, "history", []), role) or {}
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total_tokens = usage.get("total_tokens")

                if provider_name not in provider_role_token_totals:
                    provider_role_token_totals[provider_name] = {}
                if role not in provider_role_token_totals[provider_name]:
                    provider_role_token_totals[provider_name][role] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "has_usage": False,
                        "model_name": model_name,
                    }

                if provider_name not in provider_token_totals:
                    provider_token_totals[provider_name] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "has_usage": False,
                    }
                if (
                    isinstance(input_tokens, int)
                    and isinstance(output_tokens, int)
                    and isinstance(total_tokens, int)
                ):
                    provider_token_totals[provider_name]["input_tokens"] += input_tokens
                    provider_token_totals[provider_name][
                        "output_tokens"
                    ] += output_tokens
                    provider_token_totals[provider_name]["total_tokens"] += total_tokens
                    provider_token_totals[provider_name]["has_usage"] = True

                    provider_role_token_totals[provider_name][role][
                        "input_tokens"
                    ] += input_tokens
                    provider_role_token_totals[provider_name][role][
                        "output_tokens"
                    ] += output_tokens
                    provider_role_token_totals[provider_name][role][
                        "total_tokens"
                    ] += total_tokens
                    provider_role_token_totals[provider_name][role]["has_usage"] = True

                    estimated_cost = estimate_cost_usd(
                        model_name,
                        TokenUsage(
                            input_tokens=input_tokens, output_tokens=output_tokens
                        ),
                    )
                    if estimated_cost is not None:
                        provider_cost_totals[provider_name] = (
                            provider_cost_totals.get(provider_name, 0.0)
                            + estimated_cost
                        )
                        if provider_name not in provider_role_cost_totals:
                            provider_role_cost_totals[provider_name] = {}
                        provider_role_cost_totals[provider_name][role] = (
                            provider_role_cost_totals[provider_name].get(role, 0.0)
                            + estimated_cost
                        )

            print("\n💸 Token/Cost Summary (this run):")
            for provider_name in sorted(providers):
                tokens = provider_token_totals.get(provider_name, {})
                if tokens.get("has_usage"):
                    cost = provider_cost_totals.get(provider_name)
                    cost_str = f"${cost:.6f}" if cost is not None else "unknown"
                    print(
                        f"   • {provider_name}: input={tokens['input_tokens']}, output={tokens['output_tokens']}, total={tokens['total_tokens']}, cost={cost_str}"
                    )
                    role_tokens = provider_role_token_totals.get(provider_name, {})
                    for role in ROLE_NODES:
                        rt = role_tokens.get(role)
                        if not rt or not rt.get("has_usage"):
                            continue
                        role_cost = provider_role_cost_totals.get(
                            provider_name, {}
                        ).get(role)
                        role_cost_str = (
                            f"${role_cost:.6f}" if role_cost is not None else "unknown"
                        )
                        model_label = rt.get("model_name") or "unknown-model"
                        print(
                            f"     - {role} ({model_label}): input={rt['input_tokens']}, output={rt['output_tokens']}, total={rt['total_tokens']}, cost={role_cost_str}"
                        )
                else:
                    print(f"   • {provider_name}: tokens/cost unknown")
    else:
        print("\n✅ Stream completed (no final output captured).")
        if node_counts:
            print(f"📊 Stream Summary: Total time {stream_elapsed:.2f}s")
            for node_name in sorted(node_counts):
                print(f"   • {node_name}: {node_counts[node_name]} event(s)")


async def test_provider(provider_name: str) -> int:
    print(f"Testing provider: {provider_name}")
    providers, _ = reload_config()
    if provider_name not in providers:
        print(f"Error testing provider {provider_name}: provider is not configured")
        return 2
    try:
        provider = get_provider_exact(provider_name)
        if provider is None:
            raise RuntimeError(f"Provider not available: {provider_name}")
        info = await provider.get_model_info()
        print(f"Provider info: {info}")
        test_kwargs: dict[str, Any] = {}
        if provider_name == "codex_cli":
            test_kwargs["skip_git_repo_check"] = True

        prompt = "Write a short poem about AI"
        print(f"\nTesting generate with prompt: '{prompt}'")
        result = await provider.generate(prompt, max_tokens=50, **test_kwargs)
        print(f"Result: {result}")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is reinforcement learning?"},
        ]
        print("\nTesting chat with messages about reinforcement learning")
        result = await provider.chat(cast(Any, messages), max_tokens=50, **test_kwargs)
        print(f"Result: {result}")
        return 0
    except Exception as e:
        print(f"Error testing provider {provider_name}: {e}")
        return 2


async def list_providers() -> None:
    print("Listing configured providers:")
    providers, _ = reload_config()
    validator = get_config_validator()
    for name, cfg in providers.items():
        readiness = validator.get_provider_readiness(name, cfg)
        print(f"  - {name}: {cfg.type} ({cfg.model_name or 'no default model'})")
        print(f"    Status: {readiness.status}")
        print(f"    Class: {cfg.class_path}")
        if cfg.binary:
            print(f"    Binary: {cfg.binary}")
        if cfg.key_env:
            print(f"    Key env: {cfg.key_env}")
        if cfg.default_args:
            print(f"    Default args: {cfg.default_args}")
        print(f"    Models: {list(cfg.models.keys())}")
        print()


async def performance_report() -> None:
    print("📊 COMPREHENSIVE PERFORMANCE REPORT")
    print("=" * 60)
    monitor = get_performance_monitor()
    report = monitor.get_performance_report()
    print(f"Report timestamp: {time.ctime(report['timestamp'])}")
    print(f"Total requests in report: {report['summary']['total_requests']}")
    print(f"Average success rate: {report['summary']['avg_success_rate']:.1f}%")
    print(f"Average response time: {report['summary']['avg_response_time']:.3f}s")


async def leadership_report() -> None:
    print("🧠 LEADERSHIP LEARNING REPORT")
    print("=" * 60)
    leadership = get_leadership_orchestrator()
    summary = leadership.get_learning_summary()
    print(json.dumps(summary, indent=2))


async def hot_swap_demo(task: str) -> None:
    _ensure_orchestration_runtime()
    print("🔄 HOT-SWAP DEMO")
    print("=" * 60)
    state = create_state(task, "openai")
    try:
        _, kwargs = state.get_provider_for_role("execute")
        print(f"Initial execute config: {kwargs}")
    except Exception as e:
        print(f"⚠️  Initial config error: {e}")
    state.set_provider_for_role("execute", "anthropic")
    state.set_kwargs_for_role("execute", temperature=0.1, max_tokens=256)
    try:
        _, new_kwargs = state.get_provider_for_role("execute")
        print(f"New execute config: {new_kwargs}")
    except Exception as e:
        print(f"⚠️  New config error: {e}")


async def harness_run_command(
    task_path: str,
    strategy_path: str,
    workspace: str,
    out_root: str = ".forge-harness-runs",
    config_path: str = "config/models.yaml",
    *,
    json_output: bool = False,
    thread_id: str | None = None,
    checkpoint: str = "memory",
    auto_fit_strategy: bool = True,
    analysis_review_execution_mode: str = "legacy_bridge",
) -> int:
    try:
        executor = HarnessLangGraphExecutor(checkpoint=checkpoint)
        state = await executor.execute(
            task_path=task_path,
            strategy_path=strategy_path,
            workspace=workspace,
            out_root=out_root,
            config_path=config_path,
            thread_id=thread_id,
            auto_fit_strategy=auto_fit_strategy,
            analysis_review_execution_mode=analysis_review_execution_mode,
        )
        summary = state.get("summary_payload") or {
            "verdict": state.get("run_verdict"),
            "verdicts": {
                "run_verdict": state.get("run_verdict"),
                "content_verdict": state.get("content_verdict"),
                "validator_verdict": state.get("validator_verdict"),
                "policy_verdict": state.get("policy_verdict"),
                "config_verdict": state.get("config_verdict"),
            },
            "artifacts": {
                key: value.get("path")
                for key, value in dict(state.get("artifact_index") or {}).items()
                if isinstance(value, dict) and value.get("path")
            },
        }
    except (HarnessError, RuntimeError, ValueError, KeyError, FileNotFoundError) as exc:
        print(f"❌ HARNESS RUN FAILED: {exc}")
        return 2

    if json_output:
        print(json.dumps(summary, indent=2, sort_keys=False))
        return _summary_exit_code(summary)

    verdicts = summary.get("verdicts") or {}
    artifacts = summary.get("artifacts") or {}
    print(f"run_verdict={verdicts.get('run_verdict', summary.get('verdict'))}")
    print(f"content_verdict={verdicts.get('content_verdict')}")
    print(f"validator_verdict={verdicts.get('validator_verdict')}")
    print(f"policy_verdict={verdicts.get('policy_verdict')}")
    print(f"config_verdict={verdicts.get('config_verdict', 'pass')}")
    print(f"run_dir={artifacts.get('run_dir')}")
    print(f"report={artifacts.get('report_md')}")
    print(f"summary={artifacts.get('summary_json')}")
    final_artifact = artifacts.get('final_artifact')
    if final_artifact:
        print(f"final_artifact={final_artifact}")
    final_answer_md = artifacts.get('final_answer_md')
    if final_answer_md:
        print(f"final_answer={final_answer_md}")
    partial_answer_md = artifacts.get('partial_answer_md')
    if partial_answer_md:
        print(f"partial_answer={partial_answer_md}")
    return _summary_exit_code(summary)


async def main_async(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Anvil CLI (Enhanced)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    run_parser = subparsers.add_parser("run", help="Run a task (enhanced)")
    run_parser.add_argument("task", help="Task to run")
    run_parser.add_argument(
        "--provider",
        "-p",
        default="auto",
        help="Provider ('auto' to let leadership choose)",
    )
    run_parser.add_argument(
        "--no-leadership", action="store_true", help="Disable leadership team decisions"
    )
    run_parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream execution progress (node-level by default)",
    )
    run_parser.add_argument(
        "--stream-verbose",
        action="store_true",
        help="Show all LangGraph/LangChain callback events (very noisy)",
    )
    run_parser.add_argument("--execute", help="Provider override for execute role")
    run_parser.add_argument("--critique", help="Provider override for critique role")
    run_parser.add_argument("--refine", help="Provider override for refine role")
    run_parser.add_argument("--review", help="Provider override for review role")
    run_parser.add_argument("--reflect", help="Provider override for reflect role")

    subparsers.add_parser("perf-report", help="Show performance report")
    subparsers.add_parser("leadership-report", help="Show leadership learning report")

    hotswap_parser = subparsers.add_parser(
        "hotswap-demo", help="Demonstrate hot-swapping"
    )
    hotswap_parser.add_argument("task", help="Task for demo")

    subparsers.add_parser("save", help="Persist data")

    harness_parser = subparsers.add_parser(
        "harness-run",
        help="Run the mini-harness task/strategy surface",
    )
    harness_parser.add_argument("--task", required=True, help="Path to task YAML/JSON")
    harness_parser.add_argument("--strategy", required=True, help="Path to strategy YAML/JSON")
    harness_parser.add_argument("--workspace", required=True, help="Target workspace directory")
    harness_parser.add_argument(
        "--out-root",
        default=".forge-harness-runs",
        help="Directory that will receive run artifacts",
    )
    harness_parser.add_argument(
        "--config",
        default="config/models.yaml",
        help="Path to the Forge provider config file",
    )
    harness_parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional stable thread ID to use for checkpointed runs",
    )
    harness_parser.add_argument(
        "--checkpoint",
        choices=["memory", "sqlite"],
        default="memory",
        help="Harness checkpoint backend",
    )
    harness_parser.add_argument(
        "--auto-fit-strategy",
        choices=["true", "false"],
        default="true",
        help="Auto-fit obviously mismatched task/strategy pairs before model work",
    )
    harness_parser.add_argument(
        "--analysis-review-execution-mode",
        choices=["legacy_bridge", "graph_owned"],
        default="legacy_bridge",
        help="Runtime entrypoint for analysis_review strategies",
    )
    harness_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final harness summary JSON to stdout",
    )

    test_parser = subparsers.add_parser("test", help="Test a provider")
    test_parser.add_argument("provider", help="Provider to test")

    subparsers.add_parser("list", help="List available providers")

    args = parser.parse_args(argv)

    if args.command == "run":
        raw_role_overrides = {
            "execute": getattr(args, "execute", None),
            "critique": getattr(args, "critique", None),
            "refine": getattr(args, "refine", None),
            "review": getattr(args, "review", None),
            "reflect": getattr(args, "reflect", None),
        }
        role_overrides: dict[str, str] = {}
        for role, value in raw_role_overrides.items():
            if isinstance(value, str) and value:
                role_overrides[role] = value
        if args.stream:
            await run_stream_command(
                args.task,
                args.provider,
                not args.no_leadership,
                role_overrides,
                verbose_events=bool(getattr(args, "stream_verbose", False)),
            )
        else:
            await run_command(
                args.task, args.provider, not args.no_leadership, role_overrides
            )
        return 0
    elif args.command == "perf-report":
        await performance_report()
        return 0
    elif args.command == "leadership-report":
        await leadership_report()
        return 0
    elif args.command == "hotswap-demo":
        await hot_swap_demo(args.task)
        return 0
    elif args.command == "save":
        get_persistence_manager().save_all()
        print("✅ Manually saved all persistence data")
        return 0
    elif args.command == "harness-run":
        return await harness_run_command(
            task_path=args.task,
            strategy_path=args.strategy,
            workspace=args.workspace,
            out_root=args.out_root,
            config_path=args.config,
            json_output=bool(args.json),
            thread_id=args.thread_id,
            checkpoint=args.checkpoint,
            auto_fit_strategy=(args.auto_fit_strategy == "true"),
            analysis_review_execution_mode=args.analysis_review_execution_mode,
        )
    elif args.command == "test":
        return await test_provider(args.provider)
    elif args.command == "list":
        await list_providers()
        return 0
    else:
        parser.print_help()
        return 0


def main(argv=None) -> None:
    exit_code = 0
    try:
        exit_code = asyncio.run(main_async(argv))
    finally:
        try:
            get_persistence_manager().save_all()
            print("✅ Performance and leadership data saved successfully")
        except Exception as e:
            print(f"⚠️  Error saving persistence data: {e}")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
