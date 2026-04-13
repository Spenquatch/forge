# anvil/performance_monitor.py
"""
Advanced Performance Monitoring System for AI/ML Pipelines.

Follows industry best practices:
- Observer pattern for event handling
- Real-time metrics collection
- Aggregation and reporting
- Alert system for anomalies
- Export capabilities for external systems
- Thread-safe operations
"""

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union, overload

# Import will be resolved at runtime to avoid circular imports
_persistence_manager = None

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics we can collect."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMING = "timing"


@dataclass
class MetricEvent:
    """Represents a single metric event."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics for a component."""

    component: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0
    p50_duration: float = 0.0
    p95_duration: float = 0.0
    p99_duration: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0  # requests per second
    last_updated: float = field(default_factory=time.time)
    durations: deque = field(default_factory=lambda: deque(maxlen=1000))
    _start_time: float = field(default_factory=time.time, init=False, repr=False)

    def update(self, duration: float, success: bool = True) -> None:
        """Update metrics with new request data."""
        self.total_requests += 1
        self.durations.append(duration)

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Update duration statistics
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)

        if len(self.durations) > 0:
            sorted_durations = sorted(self.durations)
            self.avg_duration = statistics.mean(sorted_durations)

            # Always calculate median
            self.p50_duration = statistics.median(sorted_durations)

            # Only calculate percentiles if we have sufficient data
            if len(sorted_durations) >= 10:  # Reduced from 20 for better UX
                try:
                    # Use proper percentile calculation
                    n = len(sorted_durations)
                    p95_idx = min(int(n * 0.95), n - 1)
                    p99_idx = min(int(n * 0.99), n - 1)

                    self.p95_duration = sorted_durations[p95_idx]
                    self.p99_duration = sorted_durations[p99_idx]
                except (IndexError, ValueError):
                    # Fallback to max if calculation fails
                    self.p95_duration = self.max_duration
                    self.p99_duration = self.max_duration
            else:
                # Use max duration as approximation for small datasets
                self.p95_duration = self.max_duration
                self.p99_duration = self.max_duration

        # Calculate error rate
        self.error_rate = (
            (self.failed_requests / self.total_requests) * 100
            if self.total_requests > 0
            else 0
        )

        # Calculate throughput (requests per second over last hour)
        current_time = time.time()
        elapsed = current_time - self._start_time
        if elapsed <= 0:
            elapsed = 1

        self.throughput = self.total_requests / max(elapsed, 1)
        self.last_updated = current_time


class PerformanceMonitor:
    """
    Advanced performance monitoring system for AI/ML pipelines.

    Features:
    - Real-time metrics collection
    - Automatic aggregation and statistics
    - Configurable alerts and thresholds
    - Export capabilities
    - Thread-safe operations
    - Memory-efficient storage
    """

    def __init__(
        self,
        max_history_size: int = 10000,
        aggregation_interval: int = 60,  # seconds
        enable_alerts: bool = True,
        auto_persist: bool = True,
    ):
        """
        Initialize the performance monitor.

        Args:
            max_history_size: Maximum number of events to keep in memory
            aggregation_interval: How often to aggregate metrics (seconds)
            enable_alerts: Whether to enable alerting system
        """
        self.max_history_size = max_history_size
        self.aggregation_interval = aggregation_interval
        self.enable_alerts = enable_alerts
        self.auto_persist = auto_persist

        # Thread-safe storage
        self._metrics: Dict[str, PerformanceMetrics] = {}
        self._metrics_lock = threading.RLock()

        self._events: deque = deque(maxlen=max_history_size)
        self._events_lock = threading.RLock()

        # Event observers
        self._observers: List[Callable[[MetricEvent], None]] = []
        self._observers_lock = threading.RLock()

        # Background aggregation
        self._last_aggregation = time.time()

        logger.info(
            f"PerformanceMonitor initialized: history_size={max_history_size}, "
            f"interval={aggregation_interval}s, alerts={enable_alerts}, auto_persist={auto_persist}"
        )

    def record_event(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a performance event."""
        event = MetricEvent(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=time.time(),
            labels=labels or {},
            metadata=metadata or {},
        )

        with self._events_lock:
            self._events.append(event)

        # Notify observers
        self._notify_observers(event)

        # Trigger persistence if enabled
        if self.auto_persist and name.endswith(".request_duration"):
            self._trigger_persistence()

        logger.debug(f"Recorded event: {name}={value} ({metric_type.value})")

    def record_request(
        self,
        component: str,
        duration: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a request performance event."""
        with self._metrics_lock:
            if component not in self._metrics:
                self._metrics[component] = PerformanceMetrics(component=component)

            self._metrics[component].update(duration, success)

        # Record individual events for detailed analysis
        self.record_event(
            name=f"{component}.request_duration",
            value=duration,
            metric_type=MetricType.TIMING,
            labels={"component": component, "success": str(success)},
            metadata=metadata,
        )

        # Trigger persistence after recording request
        if self.auto_persist:
            self._trigger_persistence()

    @overload
    def get_metrics(self, component: str) -> PerformanceMetrics: ...

    @overload
    def get_metrics(self, component: None = None) -> Dict[str, PerformanceMetrics]: ...

    def get_metrics(
        self, component: Optional[str] = None
    ) -> Union[PerformanceMetrics, Dict[str, PerformanceMetrics]]:
        """Get performance metrics."""
        with self._metrics_lock:
            if component:
                return self._metrics.get(
                    component, PerformanceMetrics(component=component)
                )
            else:
                return self._metrics.copy()

    def get_performance_report(
        self, time_window: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        current_time = time.time()
        cutoff_time = current_time - time_window if time_window else 0

        with self._metrics_lock:
            components: Dict[str, Any] = {}
            summary: Dict[str, Any] = {
                "total_components": len(self._metrics),
                "total_requests": 0,
                "total_failures": 0,
                "avg_success_rate": 0.0,
                "avg_response_time": 0.0,
            }
            report: Dict[str, Any] = {
                "timestamp": current_time,
                "time_window_seconds": time_window,
                "components": components,
                "summary": summary,
            }

            total_requests = 0
            total_failures = 0
            total_durations: List[float] = []

            for component, metrics in self._metrics.items():
                if time_window is None or metrics.last_updated >= cutoff_time:
                    component_data = {
                        "total_requests": metrics.total_requests,
                        "successful_requests": metrics.successful_requests,
                        "failed_requests": metrics.failed_requests,
                        "success_rate": 100 - metrics.error_rate,
                        "avg_duration": metrics.avg_duration,
                        "min_duration": (
                            metrics.min_duration
                            if metrics.min_duration != float("inf")
                            else 0
                        ),
                        "max_duration": metrics.max_duration,
                        "p50_duration": metrics.p50_duration,
                        "p95_duration": metrics.p95_duration,
                        "p99_duration": metrics.p99_duration,
                        "throughput": metrics.throughput,
                        "last_updated": metrics.last_updated,
                    }

                    components[component] = component_data

                    total_requests += metrics.total_requests
                    total_failures += metrics.failed_requests
                    if metrics.durations:
                        total_durations.extend(metrics.durations)

            # Calculate summary statistics
            summary["total_requests"] = total_requests
            summary["total_failures"] = total_failures
            summary["avg_success_rate"] = (
                ((total_requests - total_failures) / total_requests * 100)
                if total_requests > 0
                else 0
            )
            summary["avg_response_time"] = (
                statistics.mean(total_durations) if total_durations else 0
            )

            return report

    def add_observer(self, observer: Callable[[MetricEvent], None]) -> None:
        """Add an event observer."""
        with self._observers_lock:
            self._observers.append(observer)
        logger.info("Added performance observer")

    def _notify_observers(self, event: MetricEvent) -> None:
        """Notify all registered observers of an event."""
        with self._observers_lock:
            for observer in self._observers:
                try:
                    observer(event)
                except Exception as e:
                    logger.error(f"Error in performance observer: {e}")

    def _trigger_persistence(self) -> None:
        """Trigger persistence of performance data."""
        global _persistence_manager

        # Import here to avoid circular imports if needed
        if _persistence_manager is None:
            try:
                from anvil.persistence_manager import get_persistence_manager

                _persistence_manager = get_persistence_manager()
            except ImportError as e:
                logger.error(f"Could not import persistence manager: {e}")
                return

        # Save performance data
        try:
            _persistence_manager.save_performance_data(self)
            logger.debug("Performance data persisted successfully")
        except Exception as e:
            logger.error(f"Error persisting performance data: {e}")


# Global monitor instance with lazy initialization
_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance with persistence."""
    global _monitor, _persistence_manager

    # Initialize monitor if needed
    if _monitor is None:
        _monitor = PerformanceMonitor()

        # Initialize persistence manager if needed
        if _persistence_manager is None:
            # Import here to avoid circular imports
            from anvil.persistence_manager import get_persistence_manager

            _persistence_manager = get_persistence_manager()

        # Load persisted data
        try:
            _persistence_manager.load_performance_data(_monitor)
            logger.info("Loaded persisted performance data")
        except Exception as e:
            logger.error(f"Error loading persisted performance data: {e}")

    return _monitor
