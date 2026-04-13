# anvil/orchestration/state.py
"""
Enhanced ForgeState with hot-swappable configuration support.
Implements industry-standard state management with runtime override capabilities.
"""

import datetime
import logging
import uuid
from typing import Any, Dict, Literal, Optional, Tuple

logger = logging.getLogger(__name__)


class ForgeState:
    """
    Enhanced state object with hot-swappable configuration support.

    Supports runtime overrides for providers, models, and kwargs - enabling
    the leadership team to adjust strategies dynamically.
    """

    def __init__(
        self,
        task: str,
        pipeline: Optional[Dict[str, str]] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize state with task and configuration.

        Args:
            task: The task to be performed
            pipeline: Optional provider assignments by role
            runtime_overrides: Optional runtime configuration overrides
        """
        self.task: str = task
        self.prompt: str = task  # Backward compatibility

        # Configuration management
        self.pipeline: Dict[str, str] = pipeline or {}  # Role -> Provider mapping
        self.runtime_overrides: Dict[str, Any] = (
            runtime_overrides or {}
        )  # Hot-swap overrides

        # Execution tracking
        self.logs: Dict[str, Any] = {}  # Results from each node
        self.history: list[dict[str, Any]] = []  # Execution history
        self.result: Optional[str] = None  # Final result
        self.retry_count: int = 0
        self.created_at: str = datetime.datetime.now().isoformat()

        # Performance tracking
        self.node_timings: Dict[str, float] = {}
        self.resolution_cache: Dict[str, Dict[str, Any]] = (
            {}
        )  # Cache resolved configurations

        # New fields for LangGraph migration
        self.prompts: Dict[str, str] = {}
        self.task_metadata: Dict[str, Any] = {}
        self.strategy: str = "default"
        self.completion_status: Literal["pending", "success", "failed"] = "pending"
        self.error_state: Optional[str] = None
        self.thread_id: str = str(uuid.uuid4())

        logger.debug(f"Created ForgeState for task: {task[:50]}...")

    def get_provider_for_role(self, role: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Get the provider and configuration for a specific role.

        Args:
            role: The role (execute, critique, refine, etc.)

        Returns:
            Tuple of (provider_instance, resolved_config_dict)
        """
        from anvil.configuration_resolver import get_resolver

        # Merge pipeline and runtime overrides
        combined_overrides = self.runtime_overrides.copy()

        # Add pipeline-specific provider if set
        if role in self.pipeline:
            if role not in combined_overrides:
                combined_overrides[role] = {}
            combined_overrides[role]["provider"] = self.pipeline[role]

        # Get resolver and resolve configuration
        resolver = get_resolver()
        provider, config = resolver.get_provider_for_role(role, combined_overrides)

        # Cache the resolution for debugging
        self.resolution_cache[role] = {
            "provider_name": config.provider_name,
            "model_name": config.model_name,
            "kwargs": config.kwargs,
            "fallback_used": config.fallback_used,
            "resolution_path": config.resolution_path,
        }

        logger.debug(f"Resolved {role}: {config.provider_name}/{config.model_name}")

        return provider, config.kwargs

    def update_strategy(self, new_overrides: Dict[str, Any]) -> None:
        """
        Hot-update the execution strategy (leadership team capability).

        Args:
            new_overrides: New runtime overrides to apply
        """
        self.runtime_overrides.update(new_overrides)
        self.resolution_cache.clear()  # Clear cache to force re-resolution

        logger.info(f"Strategy updated with overrides: {list(new_overrides.keys())}")

    def set_provider_for_role(self, role: str, provider_name: str) -> None:
        """
        Set a specific provider for a role (hot-swap capability).

        Args:
            role: The role to update
            provider_name: The provider to use for this role
        """
        self.pipeline[role] = provider_name

        # Clear cache for this role
        if role in self.resolution_cache:
            del self.resolution_cache[role]

        logger.info(f"Set provider for {role}: {provider_name}")

    def set_kwargs_for_role(self, role: str, **kwargs: Any) -> None:
        """
        Set specific kwargs for a role (hot-swap capability).

        Args:
            role: The role to update
            **kwargs: Keyword arguments to set for this role
        """
        if role not in self.runtime_overrides:
            self.runtime_overrides[role] = {}

        self.runtime_overrides[role].update(kwargs)

        # Clear cache for this role
        if role in self.resolution_cache:
            del self.resolution_cache[role]

        logger.info(f"Updated kwargs for {role}: {list(kwargs.keys())}")

    def role_kwargs(
        self, role: str, overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get merged kwargs for a specific role (backward compatibility method).

        Args:
            role: The role to get kwargs for
            overrides: Optional additional overrides

        Returns:
            Merged kwargs for the role
        """
        _, base_kwargs = self.get_provider_for_role(role)

        if overrides:
            result = base_kwargs.copy()
            result.update(overrides)
            return result

        return base_kwargs

    def add_to_history(
        self, node_name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a node execution to the history with optional metadata.

        Args:
            node_name: Name of the node that executed
            metadata: Optional metadata about the execution
        """
        entry = {
            "node": node_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "retry_count": self.retry_count,
        }

        if metadata:
            entry["metadata"] = metadata

        self.history.append(entry)
        logger.debug(f"Added to history: {node_name}")

    def log_node_timing(self, node_name: str, duration: float) -> None:
        """
        Log execution timing for a node.

        Args:
            node_name: Name of the node
            duration: Execution duration in seconds
        """
        self.node_timings[node_name] = duration
        logger.debug(f"Node {node_name} executed in {duration:.2f}s")

    def set_result(
        self, value: str, status: Literal["success", "failed"] = "success"
    ) -> None:
        """
        Set the result and completion status (LangGraph helper).

        Args:
            value: The result value
            status: The completion status ('success' or 'failed')
        """
        self.result = value
        self.completion_status = status
        logger.debug(f"Set result with status: {status}")

    def mark_error(self, err: str) -> None:
        """
        Mark the state with an error (LangGraph helper).

        Args:
            err: Error description
        """
        self.error_state = err
        self.completion_status = "failed"
        logger.debug(f"Marked error: {err[:100]}...")

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the execution state.

        Returns:
            Dictionary with execution summary
        """
        return {
            "task": self.task,
            "nodes_executed": len(self.history),
            "retry_count": self.retry_count,
            "has_result": self.result is not None,
            "node_timings": self.node_timings,
            "resolution_cache": self.resolution_cache,
            "runtime_overrides": self.runtime_overrides,
            "created_at": self.created_at,
        }

    def get_debug_info(self) -> Dict[str, Any]:
        """
        Get detailed debug information about configuration resolution.

        Returns:
            Dictionary with debug information
        """
        return {
            "pipeline": self.pipeline,
            "runtime_overrides": self.runtime_overrides,
            "resolution_cache": self.resolution_cache,
            "logs_keys": list(self.logs.keys()),
            "history": self.history[-5:],  # Last 5 entries
            "node_timings": self.node_timings,
        }

    def __str__(self) -> str:
        """String representation of the state."""
        return f"ForgeState(task='{self.task[:30]}...', nodes={len(self.history)}, result={self.result is not None})"

    def __repr__(self) -> str:
        """Detailed representation of the state."""
        return (
            f"ForgeState(task='{self.task[:30]}...', "
            f"nodes_executed={len(self.history)}, "
            f"providers={list(self.pipeline.values())}, "
            f"overrides={bool(self.runtime_overrides)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize state to dictionary for persistence (Phase 6).

        Returns:
            Dictionary representation of state
        """
        return {
            "task": self.task,
            "prompt": self.prompt,
            "pipeline": self.pipeline,
            "runtime_overrides": self.runtime_overrides,
            "logs": self.logs,
            "history": self.history,
            "result": self.result,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "node_timings": self.node_timings,
            "resolution_cache": self.resolution_cache,
            "prompts": self.prompts,
            "task_metadata": self.task_metadata,
            "strategy": self.strategy,
            "completion_status": self.completion_status,
            "error_state": self.error_state,
            "thread_id": self.thread_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ForgeState":
        """
        Deserialize state from dictionary (Phase 6).

        Args:
            d: Dictionary representation

        Returns:
            ForgeState instance
        """
        fs = cls(
            task=d.get("task", ""),
            pipeline=d.get("pipeline", {}),
            runtime_overrides=d.get("runtime_overrides", {}),
        )
        fs.prompt = d.get("prompt", fs.task)
        fs.logs = d.get("logs", {})
        fs.history = d.get("history", [])
        fs.result = d.get("result")
        fs.retry_count = int(d.get("retry_count", 0))
        fs.created_at = d.get("created_at", fs.created_at)
        fs.node_timings = d.get("node_timings", {})
        fs.resolution_cache = d.get("resolution_cache", {})
        fs.prompts = d.get("prompts", {})
        fs.task_metadata = d.get("task_metadata", {})
        fs.strategy = d.get("strategy", "default")
        fs.completion_status = d.get("completion_status", "pending")
        fs.error_state = d.get("error_state")
        fs.thread_id = d.get("thread_id", fs.thread_id)
        return fs


# Convenience functions for backward compatibility


def create_state(task: str, provider: Optional[str] = None) -> ForgeState:
    """
    Create a ForgeState with a single provider for all roles.

    Args:
        task: The task to execute
        provider: Provider name to use for all roles

    Returns:
        Configured ForgeState instance
    """
    if provider:
        pipeline = {
            "execute": provider,
            "critique": provider,
            "refine": provider,
            "review": provider,
            "reflect": provider,
        }
    else:
        pipeline = {}

    return ForgeState(task, pipeline)


def create_mixed_state(task: str, role_providers: Dict[str, str]) -> ForgeState:
    """
    Create a ForgeState with different providers for different roles.

    Args:
        task: The task to execute
        role_providers: Dictionary mapping roles to provider names

    Returns:
        Configured ForgeState instance
    """
    return ForgeState(task, role_providers)
