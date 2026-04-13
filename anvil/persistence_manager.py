# anvil/persistence_manager.py
"""
Persistence Manager for AI/ML Pipeline State Management.

This module provides a singleton implementation for persisting state between
CLI invocations, including:
- Performance metrics
- Leadership learning events
- Decision history
- Provider statistics

Follows industry best practices:
- Singleton pattern for global persistence
- Serialization of complex objects
- Thread-safe operations
- Automatic periodic saving
- Resilient error handling
"""

import json
import logging
import os
import pickle
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default storage location - in user's home directory
DEFAULT_STORAGE_DIR = os.path.join(str(Path.home()), ".atomize", "forge")


class PersistenceManager:
    """
    Singleton manager for persisting state between CLI invocations.

    This class ensures that important state information like performance metrics,
    leadership decisions, and provider statistics are preserved across multiple
    command-line executions.
    """

    _instance: Optional["PersistenceManager"] = None
    _lock = threading.RLock()
    _initialized: bool
    _shutdown: bool
    _save_thread: Optional[threading.Thread]
    _auto_save_interval: int

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PersistenceManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the persistence manager.

        Args:
            storage_dir: Directory to store persistence files
        """
        with self._lock:
            if self._initialized:
                return

            self.storage_dir = storage_dir or DEFAULT_STORAGE_DIR

            # Create storage directory if it doesn't exist
            os.makedirs(self.storage_dir, exist_ok=True)

            # File paths for different data stores
            self.performance_path = os.path.join(self.storage_dir, "performance.pkl")
            self.leadership_path = os.path.join(self.storage_dir, "leadership.pkl")
            self.provider_stats_path = os.path.join(
                self.storage_dir, "provider_stats.json"
            )

            # Auto-save thread
            self._shutdown = False
            self._save_thread = None
            self._auto_save_interval = 60  # seconds

            logger.info(
                f"Persistence manager initialized with storage at: {self.storage_dir}"
            )
            self._initialized = True

            # Start auto-save thread
            self._start_auto_save()

    def _start_auto_save(self):
        """Start the auto-save background thread."""
        if self._save_thread is None:
            self._save_thread = threading.Thread(
                target=self._auto_save_loop, daemon=True
            )
            self._save_thread.start()
            logger.debug("Auto-save thread started")

    def _auto_save_loop(self):
        """Background thread for auto-saving data."""
        while not self._shutdown:
            # Sleep first to allow initial data loading
            time.sleep(self._auto_save_interval)

            if self._shutdown:
                break

            try:
                self.save_all()
                logger.debug("Auto-saved all persistence data")
            except Exception as e:
                logger.error(f"Error during auto-save: {e}")

    def shutdown(self):
        """Shutdown the persistence manager."""
        with self._lock:
            # Signal thread to stop
            self._shutdown = True

            # Final save
            try:
                self.save_all()
                logger.info("Final persistence save completed during shutdown")
            except Exception as e:
                logger.error(f"Error during shutdown save: {e}")

            # Wait for thread to terminate
            if self._save_thread:
                self._save_thread.join(timeout=5.0)
                logger.debug("Auto-save thread terminated")

    def save_performance_data(self, monitor):
        """
        Save performance monitor data.

        Args:
            monitor: PerformanceMonitor instance to save
        """
        with self._lock:
            try:
                # Pickle the essential data - avoid saving functions/callbacks
                data_to_save = {
                    "_metrics": monitor._metrics,
                    "_events": list(monitor._events),
                    "max_history_size": monitor.max_history_size,
                    "aggregation_interval": monitor.aggregation_interval,
                    "enable_alerts": monitor.enable_alerts,
                }

                with open(self.performance_path, "wb") as f:
                    pickle.dump(data_to_save, f)

                logger.debug(
                    f"Saved performance data: {len(data_to_save['_metrics'])} components"
                )
                return True
            except Exception as e:
                logger.error(f"Error saving performance data: {e}")
                return False

    def load_performance_data(self, monitor):
        """
        Load performance data into monitor.

        Args:
            monitor: PerformanceMonitor instance to load data into

        Returns:
            bool: True if data was loaded successfully
        """
        with self._lock:
            if not os.path.exists(self.performance_path):
                logger.info("No performance data to load")
                return False

            try:
                with open(self.performance_path, "rb") as f:
                    data = pickle.load(f)

                # Restore data to monitor
                with monitor._metrics_lock:
                    monitor._metrics = data["_metrics"]

                with monitor._events_lock:
                    # Convert list back to deque
                    monitor._events.clear()
                    for event in data["_events"]:
                        monitor._events.append(event)

                # Restore configuration
                monitor.max_history_size = data["max_history_size"]
                monitor.aggregation_interval = data["aggregation_interval"]
                monitor.enable_alerts = data["enable_alerts"]

                logger.info(
                    f"Loaded performance data: {len(monitor._metrics)} components, {len(monitor._events)} events"
                )
                return True
            except Exception as e:
                logger.error(f"Error loading performance data: {e}")
                return False

    def save_leadership_data(self, leadership):
        """
        Save leadership orchestrator data.

        Args:
            leadership: LeadershipOrchestrator instance to save
        """
        with self._lock:
            try:
                # Pickle the essential data - avoid saving functions/callbacks
                # Get DecisionContext enum from leadership module
                from anvil.leadership_interface import DecisionContext

                data_to_save = {
                    "decision_history": leadership.decision_history,
                    "learning_events": leadership.learning_events,
                    # Save strategy state without functions
                    "strategy_state": {
                        DecisionContext.PROVIDER_SELECTION.value: {
                            "performance_history": leadership.strategies[
                                DecisionContext.PROVIDER_SELECTION
                            ].performance_history,
                            "failure_counts": leadership.strategies[
                                DecisionContext.PROVIDER_SELECTION
                            ].failure_counts,
                            "success_rates": leadership.strategies[
                                DecisionContext.PROVIDER_SELECTION
                            ].success_rates,
                        },
                        DecisionContext.PARAMETER_TUNING.value: {
                            "parameter_experiments": leadership.strategies[
                                DecisionContext.PARAMETER_TUNING
                            ].parameter_experiments,
                            "optimal_configs": leadership.strategies[
                                DecisionContext.PARAMETER_TUNING
                            ].optimal_configs,
                        },
                    },
                }

                with open(self.leadership_path, "wb") as f:
                    pickle.dump(data_to_save, f)

                logger.debug(
                    f"Saved leadership data: {len(data_to_save['decision_history'])} decisions"
                )
                return True
            except Exception as e:
                logger.error(f"Error saving leadership data: {e}")
                return False

    def load_leadership_data(self, leadership):
        """
        Load leadership data into orchestrator.

        Args:
            leadership: LeadershipOrchestrator instance to load data into

        Returns:
            bool: True if data was loaded successfully
        """
        with self._lock:
            if not os.path.exists(self.leadership_path):
                logger.info("No leadership data to load")
                return False

            try:
                with open(self.leadership_path, "rb") as f:
                    data = pickle.load(f)

                # Restore data to leadership
                with leadership._lock:
                    leadership.decision_history = data["decision_history"]
                    leadership.learning_events = data["learning_events"]

                    # Get DecisionContext enum from leadership module
                    from anvil.leadership_interface import DecisionContext

                    # Restore strategy state
                    provider_selection = leadership.strategies[
                        DecisionContext.PROVIDER_SELECTION
                    ]
                    provider_selection.performance_history = data["strategy_state"][
                        DecisionContext.PROVIDER_SELECTION.value
                    ]["performance_history"]
                    provider_selection.failure_counts = data["strategy_state"][
                        DecisionContext.PROVIDER_SELECTION.value
                    ]["failure_counts"]
                    provider_selection.success_rates = data["strategy_state"][
                        DecisionContext.PROVIDER_SELECTION.value
                    ]["success_rates"]

                    parameter_tuning = leadership.strategies[
                        DecisionContext.PARAMETER_TUNING
                    ]
                    parameter_tuning.parameter_experiments = data["strategy_state"][
                        DecisionContext.PARAMETER_TUNING.value
                    ]["parameter_experiments"]
                    parameter_tuning.optimal_configs = data["strategy_state"][
                        DecisionContext.PARAMETER_TUNING.value
                    ]["optimal_configs"]

                logger.info(
                    f"Loaded leadership data: {len(leadership.decision_history)} decisions, {len(leadership.learning_events)} events"
                )
                return True
            except Exception as e:
                logger.error(f"Error loading leadership data: {e}")
                return False

    def save_provider_stats(self, stats_dict: Dict[str, Any]):
        """
        Save provider factory statistics.

        Args:
            stats_dict: Dictionary of provider statistics
        """
        with self._lock:
            try:
                # Use JSON for human-readable stats
                with open(self.provider_stats_path, "w") as f:
                    json.dump(stats_dict, f, indent=2)

                logger.debug(f"Saved provider stats: {len(stats_dict)} providers")
                return True
            except Exception as e:
                logger.error(f"Error saving provider stats: {e}")
                return False

    def load_provider_stats(self) -> Optional[Dict[str, Any]]:
        """
        Load provider factory statistics.

        Returns:
            Dict of provider statistics or None if loading failed
        """
        with self._lock:
            if not os.path.exists(self.provider_stats_path):
                logger.info("No provider stats to load")
                return None

            try:
                with open(self.provider_stats_path, "r") as f:
                    stats = json.load(f)

                if not isinstance(stats, dict):
                    return None

                logger.info(f"Loaded provider stats: {len(stats)} providers")
                return stats
            except Exception as e:
                logger.error(f"Error loading provider stats: {e}")
                return None

    def save_all(self):
        """Save all persistence data."""
        with self._lock:
            try:
                # Import here to avoid circular imports
                from anvil.leadership_interface import (
                    get_leadership_orchestrator,
                )
                from anvil.performance_monitor import get_performance_monitor
                from anvil.provider_factory import get_provider_factory

                # Save performance data
                monitor = get_performance_monitor()
                self.save_performance_data(monitor)

                # Save leadership data
                leadership = get_leadership_orchestrator()
                self.save_leadership_data(leadership)

                # Save provider stats
                factory = get_provider_factory()

                # Get provider names from stats dictionary
                all_stats = factory.get_provider_stats()
                provider_names = list(all_stats.keys())

                # Only attempt to save if we have provider stats
                if provider_names:
                    stats = {
                        name: factory.get_provider_stats(name)
                        for name in provider_names
                    }
                    self.save_provider_stats(stats)

                logger.info("All persistence data saved successfully")
                return True
            except Exception as e:
                logger.error(f"Error saving all persistence data: {e}")
                return False

    def load_all(self):
        """Load all persistence data."""
        with self._lock:
            try:
                # Import here to avoid circular imports
                from anvil.leadership_interface import (
                    get_leadership_orchestrator,
                )
                from anvil.performance_monitor import get_performance_monitor

                # Load performance data
                monitor = get_performance_monitor()
                self.load_performance_data(monitor)

                # Load leadership data
                leadership = get_leadership_orchestrator()
                self.load_leadership_data(leadership)

                # Load provider stats (future implementation)

                logger.info("All persistence data loaded successfully")
                return True
            except Exception as e:
                logger.error(f"Error loading all persistence data: {e}")
                return False


# Global instance
_persistence_manager = None


def get_persistence_manager() -> PersistenceManager:
    """Get the global persistence manager instance."""
    global _persistence_manager
    if _persistence_manager is None:
        _persistence_manager = PersistenceManager()
    return _persistence_manager
