# anvil/leadership_interface.py
"""
Leadership Team Integration System for AI/ML Pipeline Self-Management.

Provides integration points for:
- Strategic decision making
- Dynamic configuration adjustment
- Learning from execution patterns
- A/B testing capabilities
- Escalation handling

Follows industry best practices:
- Strategy pattern for decision algorithms
- Observer pattern for event handling
- Command pattern for actions
- Policy pattern for rules
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Import will be resolved at runtime to avoid circular imports
_persistence_manager = None

logger = logging.getLogger(__name__)


class DecisionContext(Enum):
    """Contexts in which leadership decisions are made."""

    PROVIDER_SELECTION = "provider_selection"
    MODEL_SELECTION = "model_selection"
    PARAMETER_TUNING = "parameter_tuning"
    FAILURE_RECOVERY = "failure_recovery"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    ESCALATION = "escalation"


class DecisionOutcome(Enum):
    """Possible outcomes of leadership decisions."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    RETRY_NEEDED = "retry_needed"
    ESCALATION_REQUIRED = "escalation_required"


@dataclass
class ExecutionContext:
    """Context information for leadership decision making."""

    task: str
    role: str
    current_provider: Optional[str] = None
    current_model: Optional[str] = None
    current_kwargs: Dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 0
    previous_results: List[Any] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    error_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionResult:
    """Result of a leadership decision."""

    decision_id: str
    context: DecisionContext
    recommended_action: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    rationale: str
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class LearningEvent:
    """Event for the learning system."""

    event_id: str
    context: ExecutionContext
    decision_made: DecisionResult
    actual_outcome: DecisionOutcome
    performance_impact: Dict[str, float]
    lessons_learned: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class DecisionStrategy(ABC):
    """Abstract base for decision-making strategies."""

    @abstractmethod
    def make_decision(self, context: ExecutionContext) -> DecisionResult:
        """Make a strategic decision based on context."""
        pass

    @abstractmethod
    def learn_from_outcome(self, event: LearningEvent) -> None:
        """Learn from the outcome of a previous decision."""
        pass


class ProviderSelectionStrategy(DecisionStrategy):
    """Strategy for selecting optimal providers."""

    def __init__(self):
        self.performance_history: Dict[str, List[float]] = {}
        self.failure_counts: Dict[str, int] = {}
        self.success_rates: Dict[str, float] = {}

    def make_decision(self, context: ExecutionContext) -> DecisionResult:
        """Select the best provider based on performance history and context."""
        from anvil.performance_monitor import get_performance_monitor
        from anvil.providers import get_available_providers

        available_providers = get_available_providers()
        if not available_providers:
            return DecisionResult(
                decision_id=f"provider_sel_{int(time.time())}",
                context=DecisionContext.PROVIDER_SELECTION,
                recommended_action={
                    "action": "error",
                    "message": "No providers available",
                },
                confidence=0.0,
                rationale="No providers are currently available",
            )

        # Get performance data
        monitor = get_performance_monitor()
        provider_scores = {}

        for provider in available_providers:
            metrics = monitor.get_metrics(provider)

            # Calculate composite score based on multiple factors
            success_rate = (
                metrics.successful_requests / max(metrics.total_requests, 1)
            ) * 100
            avg_latency = metrics.avg_duration

            # Higher score is better
            score = (success_rate / 100) * 0.7 + (1.0 / max(avg_latency, 0.1)) * 0.3
            provider_scores[provider] = score

        # Select best provider
        best_provider = max(provider_scores, key=lambda k: provider_scores[k])
        confidence = provider_scores[best_provider] / max(
            sum(provider_scores.values()), 1.0
        )

        # Prepare alternatives
        alternatives = []
        for provider, score in sorted(
            provider_scores.items(), key=lambda x: x[1], reverse=True
        )[1:3]:
            alternatives.append(
                {
                    "provider": provider,
                    "score": score,
                    "reason": f"Alternative with score {score:.3f}",
                }
            )

        return DecisionResult(
            decision_id=f"provider_sel_{int(time.time())}",
            context=DecisionContext.PROVIDER_SELECTION,
            recommended_action={
                "action": "select_provider",
                "provider": best_provider,
                "score": provider_scores[best_provider],
            },
            confidence=confidence,
            rationale=f"Selected {best_provider} with highest composite score ({provider_scores[best_provider]:.3f})",
            alternatives=alternatives,
            metadata={"all_scores": provider_scores},
        )

    def learn_from_outcome(self, event: LearningEvent) -> None:
        """Update provider performance assessments."""
        provider = event.decision_made.recommended_action.get("provider")
        if not provider:
            return

        # Update performance history
        if provider not in self.performance_history:
            self.performance_history[provider] = []

        # Use performance impact as learning signal
        performance_score = event.performance_impact.get("success_rate", 0.0)
        self.performance_history[provider].append(performance_score)

        # Keep only recent history
        if len(self.performance_history[provider]) > 100:
            self.performance_history[provider] = self.performance_history[provider][
                -100:
            ]

        # Update failure tracking
        if event.actual_outcome == DecisionOutcome.FAILURE:
            self.failure_counts[provider] = self.failure_counts.get(provider, 0) + 1

        logger.debug(
            f"Updated learning for provider {provider}: outcome={event.actual_outcome}"
        )


class ParameterTuningStrategy(DecisionStrategy):
    """Strategy for tuning model parameters."""

    def __init__(self):
        self.parameter_experiments: Dict[str, List[Dict[str, Any]]] = {}
        self.optimal_configs: Dict[str, Dict[str, Any]] = {}

    def make_decision(self, context: ExecutionContext) -> DecisionResult:
        """Decide on parameter adjustments based on performance and task type."""
        current_kwargs = context.current_kwargs.copy()

        # Analyze task complexity
        task_complexity = self._assess_task_complexity(context.task)

        # Adjust parameters based on context
        adjustments = {}
        rationale_parts = []

        # Temperature adjustments with proper rounding
        if context.role in ["execute", "critique"]:
            # Lower temperature for analytical tasks
            new_temp = max(0.1, current_kwargs.get("temperature", 0.7) - 0.2)
            new_temp = round(new_temp, 2)  # Fix precision
            if new_temp != current_kwargs.get("temperature", 0.7):
                adjustments["temperature"] = new_temp
                rationale_parts.append(
                    f"reduced temperature to {new_temp} for {context.role}"
                )
        elif context.role == "creative":
            # Higher temperature for creative tasks
            new_temp = min(1.0, current_kwargs.get("temperature", 0.7) + 0.1)
            new_temp = round(new_temp, 2)  # Fix precision
            if new_temp != current_kwargs.get("temperature", 0.7):
                adjustments["temperature"] = new_temp
                rationale_parts.append(
                    f"increased temperature to {new_temp} for creativity"
                )

        # Token adjustments based on task complexity
        current_tokens = current_kwargs.get("max_tokens", 512)
        if task_complexity == "high" and current_tokens < 1024:
            adjustments["max_tokens"] = min(2048, current_tokens * 2)
            rationale_parts.append("increased tokens for complex task")
        elif task_complexity == "low" and current_tokens > 256:
            adjustments["max_tokens"] = max(256, current_tokens // 2)
            rationale_parts.append("reduced tokens for simple task")

        # Error-based adjustments with precision
        if context.attempt_count > 1:
            # Make parameters more conservative on retries
            if "temperature" in adjustments:
                adjustments["temperature"] = round(
                    max(0.1, adjustments["temperature"] - 0.1), 2
                )
            else:
                adjustments["temperature"] = round(
                    max(0.1, current_kwargs.get("temperature", 0.7) - 0.1), 2
                )
            rationale_parts.append("reduced temperature due to previous failures")

        confidence = 0.8 if adjustments else 0.3

        return DecisionResult(
            decision_id=f"param_tune_{int(time.time())}",
            context=DecisionContext.PARAMETER_TUNING,
            recommended_action={
                "action": "adjust_parameters",
                "adjustments": adjustments,
                "new_kwargs": {**current_kwargs, **adjustments},
            },
            confidence=confidence,
            rationale=(
                "; ".join(rationale_parts)
                if rationale_parts
                else "No adjustments needed"
            ),
            metadata={
                "task_complexity": task_complexity,
                "attempt_count": context.attempt_count,
                "original_kwargs": current_kwargs,
            },
        )

    def learn_from_outcome(self, event: LearningEvent) -> None:
        """Learn from parameter adjustment outcomes."""
        adjustments = event.decision_made.recommended_action.get("adjustments", {})
        if not adjustments:
            return

        # Track successful parameter combinations
        key = f"{event.context.role}_{event.context.current_provider}"
        if key not in self.parameter_experiments:
            self.parameter_experiments[key] = []

        experiment = {
            "adjustments": adjustments,
            "outcome": event.actual_outcome,
            "performance": event.performance_impact,
            "timestamp": event.timestamp,
        }

        self.parameter_experiments[key].append(experiment)

        # Update optimal configurations for successful outcomes
        if event.actual_outcome == DecisionOutcome.SUCCESS:
            if key not in self.optimal_configs:
                self.optimal_configs[key] = adjustments.copy()
            else:
                # Blend with existing optimal config
                for param, value in adjustments.items():
                    if param in self.optimal_configs[key]:
                        # Take weighted average
                        self.optimal_configs[key][param] = (
                            self.optimal_configs[key][param] * 0.7 + value * 0.3
                        )
                    else:
                        self.optimal_configs[key][param] = value

        logger.debug(f"Learned from parameter tuning: {key} -> {event.actual_outcome}")

    def _assess_task_complexity(self, task: str) -> str:
        """Assess task complexity based on content."""
        task_lower = task.lower()

        # Simple heuristics for complexity assessment
        if any(
            word in task_lower for word in ["explain", "analyze", "compare", "evaluate"]
        ):
            return "high"
        elif any(word in task_lower for word in ["calculate", "convert", "simple"]):
            return "low"
        else:
            return "medium"


class LeadershipOrchestrator:
    """
    Central orchestrator for leadership team decisions.

    Coordinates between different decision strategies and provides
    a unified interface for the pipeline to interact with leadership.
    """

    def __init__(self, auto_persist: bool = True):
        self.strategies: Dict[DecisionContext, DecisionStrategy] = {
            DecisionContext.PROVIDER_SELECTION: ProviderSelectionStrategy(),
            DecisionContext.PARAMETER_TUNING: ParameterTuningStrategy(),
        }
        self.auto_persist = auto_persist

        self.decision_history: List[DecisionResult] = []
        self.learning_events: List[LearningEvent] = []
        self.observers: List[Callable[[DecisionResult], None]] = []

        self._lock = threading.RLock()

        logger.info(f"Leadership orchestrator initialized: auto_persist={auto_persist}")

    def request_decision(
        self, context: DecisionContext, execution_context: ExecutionContext
    ) -> DecisionResult:
        """
        Request a leadership decision.

        Args:
            context: Type of decision needed
            execution_context: Current execution context

        Returns:
            DecisionResult with recommended action
        """
        with self._lock:
            if context not in self.strategies:
                return DecisionResult(
                    decision_id=f"unknown_{int(time.time())}",
                    context=context,
                    recommended_action={
                        "action": "no_strategy",
                        "message": f"No strategy for {context}",
                    },
                    confidence=0.0,
                    rationale=f"No decision strategy available for {context}",
                )

            strategy = self.strategies[context]
            decision = strategy.make_decision(execution_context)

            # Store decision
            self.decision_history.append(decision)

            # Notify observers
            for observer in self.observers:
                try:
                    observer(decision)
                except Exception as e:
                    logger.error(f"Error in decision observer: {e}")

            # Trigger persistence if enabled
            if self.auto_persist:
                self._trigger_persistence()

            logger.info(
                f"Leadership decision made: {context} -> {decision.recommended_action.get('action', 'unknown')}"
            )
            return decision

    def report_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        performance_impact: Dict[str, float],
        lessons_learned: Optional[List[str]] = None,
    ):
        """
        Report the outcome of a leadership decision for learning.

        Args:
            decision_id: ID of the original decision
            outcome: Actual outcome that occurred
            performance_impact: Measured performance impact
            lessons_learned: Optional lessons learned
        """
        with self._lock:
            # Find the original decision
            decision = None
            for d in self.decision_history:
                if d.decision_id == decision_id:
                    decision = d
                    break

            if not decision:
                logger.warning(
                    f"Could not find decision {decision_id} for outcome reporting"
                )
                return

            # Create learning event
            learning_event = LearningEvent(
                event_id=f"learn_{int(time.time())}",
                context=ExecutionContext(
                    task="", role="", metadata=decision.metadata
                ),  # Simplified context for learning
                decision_made=decision,
                actual_outcome=outcome,
                performance_impact=performance_impact,
                lessons_learned=lessons_learned or [],
            )

            self.learning_events.append(learning_event)

            # Update strategies with learning
            if decision.context in self.strategies:
                strategy = self.strategies[decision.context]
                strategy.learn_from_outcome(learning_event)

            # Trigger persistence if enabled
            if self.auto_persist:
                self._trigger_persistence()

            logger.info(f"Reported outcome for decision {decision_id}: {outcome}")

    def add_observer(self, observer: Callable[[DecisionResult], None]):
        """Add a decision observer."""
        with self._lock:
            self.observers.append(observer)
            logger.info("Added leadership observer")

    def _trigger_persistence(self):
        """Trigger persistence of leadership data."""
        global _persistence_manager

        # Import here to avoid circular imports if needed
        if _persistence_manager is None:
            try:
                from anvil.persistence_manager import get_persistence_manager

                _persistence_manager = get_persistence_manager()
            except ImportError as e:
                logger.error(f"Could not import persistence manager: {e}")
                return

        # Save leadership data
        try:
            _persistence_manager.save_leadership_data(self)
            logger.debug("Leadership data persisted successfully")
        except Exception as e:
            logger.error(f"Error persisting leadership data: {e}")

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning outcomes."""
        with self._lock:
            outcomes_by_type: Dict[str, int] = {}
            summary = {
                "total_decisions": len(self.decision_history),
                "total_learning_events": len(self.learning_events),
                "outcomes_by_type": outcomes_by_type,
                "strategies_active": [s.value for s in self.strategies.keys()],
                "recent_performance": {},
            }

            # Analyze outcomes
            for event in self.learning_events:
                outcome = event.actual_outcome.value
                outcomes_by_type[outcome] = outcomes_by_type.get(outcome, 0) + 1

            return summary


# Global orchestrator instance with lazy initialization
_leadership = None


def get_leadership_orchestrator() -> LeadershipOrchestrator:
    """Get the global leadership orchestrator instance with persistence."""
    global _leadership, _persistence_manager

    # Initialize leadership if needed
    if _leadership is None:
        _leadership = LeadershipOrchestrator()

        # Initialize persistence manager if needed
        if _persistence_manager is None:
            # Import here to avoid circular imports
            from anvil.persistence_manager import get_persistence_manager

            _persistence_manager = get_persistence_manager()

        # Load persisted data
        try:
            _persistence_manager.load_leadership_data(_leadership)
            logger.info("Loaded persisted leadership data")
        except Exception as e:
            logger.error(f"Error loading persisted leadership data: {e}")

    return _leadership


def request_leadership_decision(
    context: DecisionContext, execution_context: ExecutionContext
) -> DecisionResult:
    """Convenience function to request a leadership decision."""
    return get_leadership_orchestrator().request_decision(context, execution_context)


def report_decision_outcome(
    decision_id: str, outcome: DecisionOutcome, performance_impact: Dict[str, float]
):
    """Convenience function to report decision outcomes."""
    get_leadership_orchestrator().report_outcome(
        decision_id, outcome, performance_impact
    )
