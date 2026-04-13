# anvil/configuration_resolver.py
"""
Configuration Resolution Service for Hot-Swappable AI Pipeline.

This service implements the complete fallback hierarchy:
1. Runtime overrides (highest priority)
2. Role-specific configuration for model
3. Default role configuration
4. Provider defaults (lowest priority)

Industry best practices:
- Thread-safe singleton
- Lazy evaluation
- Comprehensive logging
- Error recovery
"""

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional

from anvil.config_loader import ProviderCfg, load_config
from anvil.providers import get_provider, is_provider_available

logger = logging.getLogger(__name__)


@dataclass
class ResolvedConfiguration:
    """Result of configuration resolution."""

    provider_name: str
    model_name: str
    kwargs: Dict[str, Any]
    fallback_used: bool = False
    resolution_path: list[str] = field(default_factory=list)


class ConfigurationResolver:
    """
    Thread-safe configuration resolver with hot-swap support.
    Implements the complete fallback hierarchy for providers, models, and kwargs.
    """

    _instance: Optional["ConfigurationResolver"] = None
    _lock = RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._providers_config: Dict[str, ProviderCfg] = {}
            self._default_pipeline: Dict[str, str] = {}
            self._cache: Dict[tuple[str, str], ResolvedConfiguration] = {}
            self._cache_lock = RLock()
            self._reload_config()
            self._initialized = True

    def _reload_config(self):
        """Reload configuration from disk."""
        try:
            self._providers_config, self._default_pipeline = load_config()
            with self._cache_lock:
                self._cache.clear()  # Invalidate cache on reload
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            # Keep existing config if reload fails

    def resolve_configuration(
        self, role: str, runtime_overrides: Optional[Dict[str, Any]] = None
    ) -> ResolvedConfiguration:
        """
        Resolve complete configuration for a role with full fallback hierarchy.

        Args:
            role: The role (execute, critique, etc.)
            runtime_overrides: Optional runtime overrides from leadership team

        Returns:
            Resolved configuration with provider, model, and kwargs
        """
        runtime_overrides = runtime_overrides or {}

        # Create cache key
        cache_key: tuple[str, str] = (role, str(sorted(runtime_overrides.items())))

        # Check cache first
        with self._cache_lock:
            if cache_key in self._cache:
                logger.debug(f"Using cached configuration for {role}")
                return self._cache[cache_key]

        # Resolve step by step
        resolution_path: list[str] = []

        # 1. Resolve provider
        provider_name = self._resolve_provider(role, runtime_overrides, resolution_path)

        # 2. Resolve model
        model_name = self._resolve_model(
            provider_name, role, runtime_overrides, resolution_path
        )

        # 3. Resolve kwargs
        kwargs = self._resolve_kwargs(
            provider_name, model_name, role, runtime_overrides, resolution_path
        )

        # Create result
        result = ResolvedConfiguration(
            provider_name=provider_name,
            model_name=model_name,
            kwargs=kwargs,
            fallback_used=len([p for p in resolution_path if "fallback" in p.lower()])
            > 0,
            resolution_path=resolution_path,
        )

        # Cache the result
        with self._cache_lock:
            self._cache[cache_key] = result

        logger.debug(f"Resolved configuration for {role}: {provider_name}/{model_name}")
        return result

    def _resolve_provider(
        self, role: str, runtime_overrides: Dict[str, Any], resolution_path: list[str]
    ) -> str:
        """Resolve which provider to use."""

        # 1. Check runtime overrides first
        if "provider" in runtime_overrides:
            provider = str(runtime_overrides["provider"])
            if is_provider_available(provider):
                resolution_path.append(f"provider: runtime override -> {provider}")
                return provider
            else:
                resolution_path.append(
                    f"provider: runtime override {provider} not available"
                )

        # 2. Check role-specific provider override
        if (
            role in runtime_overrides
            and isinstance(runtime_overrides[role], dict)
            and "provider" in runtime_overrides[role]
        ):
            provider = str(runtime_overrides[role]["provider"])
            if is_provider_available(provider):
                resolution_path.append(f"provider: role override -> {provider}")
                return provider

        # 3. Check default pipeline configuration
        if role in self._default_pipeline:
            provider = self._default_pipeline[role]
            if is_provider_available(provider):
                resolution_path.append(f"provider: default pipeline -> {provider}")
                return provider
            else:
                resolution_path.append(
                    f"provider: default pipeline {provider} not available"
                )

        # 4. Use fallback provider (OpenAI -> Anthropic -> first available)
        fallback_order = ["openai", "anthropic"]
        for provider in fallback_order:
            if is_provider_available(provider):
                resolution_path.append(f"provider: fallback -> {provider}")
                return provider

        # 5. Use any available provider
        from anvil.providers import get_available_providers

        available = get_available_providers()
        if available:
            provider = available[0]
            resolution_path.append(f"provider: emergency fallback -> {provider}")
            return provider

        # 6. Final fallback to openai (even if not available - let it fail gracefully)
        resolution_path.append("provider: final fallback -> openai")
        return "openai"

    def _resolve_model(
        self,
        provider_name: str,
        role: str,
        runtime_overrides: Dict[str, Any],
        resolution_path: list[str],
    ) -> str:
        """Resolve which model to use."""

        # 1. Check runtime overrides
        if "model" in runtime_overrides:
            model = str(runtime_overrides["model"])
            resolution_path.append(f"model: runtime override -> {model}")
            return model

        # 2. Check role-specific model override
        if (
            role in runtime_overrides
            and isinstance(runtime_overrides[role], dict)
            and "model" in runtime_overrides[role]
        ):
            model = str(runtime_overrides[role]["model"])
            resolution_path.append(f"model: role override -> {model}")
            return model

        # 3. Use provider's default model
        if provider_name in self._providers_config:
            provider_cfg = self._providers_config[provider_name]
            if provider_cfg.model_name:
                resolution_path.append(
                    f"model: provider default -> {provider_cfg.model_name}"
                )
                return provider_cfg.model_name

        # 4. Fallback based on provider
        fallback_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307",
            "phi3-mini": "microsoft/phi-3-mini",
            "tinyllama": "tinyllama",
        }

        if provider_name in fallback_models:
            model = fallback_models[provider_name]
            resolution_path.append(f"model: fallback -> {model}")
            return model

        # 5. Generic fallback
        resolution_path.append("model: generic fallback -> default")
        return "default"

    def _resolve_kwargs(
        self,
        provider_name: str,
        model_name: str,
        role: str,
        runtime_overrides: Dict[str, Any],
        resolution_path: list[str],
    ) -> Dict[str, Any]:
        """Resolve final kwargs with complete hierarchy."""

        result: Dict[str, Any] = {}

        # 1. Start with provider defaults (if any)
        if provider_name in self._providers_config:
            provider_cfg = self._providers_config[provider_name]

            # Check for model-wide defaults
            if model_name in provider_cfg.models:
                if isinstance(provider_cfg.models[model_name], dict):
                    result.update(provider_cfg.models[model_name])
                    resolution_path.append("kwargs: model defaults")

            # Check for wildcard role config (model_name/*)
            wildcard_key = f"{model_name}/*"
            if wildcard_key in provider_cfg.models:
                wildcard_config = provider_cfg.models[wildcard_key]
                if isinstance(wildcard_config, dict) and role in wildcard_config:
                    result.update(wildcard_config[role])
                    resolution_path.append("kwargs: wildcard role config")

            # Check for specific role config (model_name/role)
            specific_key = f"{model_name}/{role}"
            if specific_key in provider_cfg.models:
                role_config = provider_cfg.models[specific_key]
                if isinstance(role_config, dict):
                    result.update(role_config)
                    resolution_path.append("kwargs: specific role config")

        # 2. Apply runtime overrides
        if "kwargs" in runtime_overrides:
            result.update(runtime_overrides["kwargs"])
            resolution_path.append("kwargs: runtime override")

        # 3. Apply role-specific runtime overrides
        if role in runtime_overrides:
            role_overrides = runtime_overrides[role]
            if isinstance(role_overrides, dict):
                # Filter out non-kwargs keys
                kwargs_overrides = {
                    k: v
                    for k, v in role_overrides.items()
                    if k not in ["provider", "model"]
                }
                if kwargs_overrides:
                    result.update(kwargs_overrides)
                    resolution_path.append("kwargs: role-specific runtime override")

        # 4. Apply common defaults if nothing was set
        if not result:
            result = {"temperature": 0.7, "max_tokens": 512}
            resolution_path.append("kwargs: system defaults")

        # Filter out None values
        result = {k: v for k, v in result.items() if v is not None}

        return result

    def hot_reload(self):
        """Hot-reload configuration (for leadership team adjustments)."""
        self._reload_config()
        logger.info("Configuration hot-reloaded")

    def get_provider_for_role(
        self, role: str, runtime_overrides: Optional[Dict] = None
    ):
        """Get the actual provider instance for a role."""
        config = self.resolve_configuration(role, runtime_overrides)
        provider = get_provider(config.provider_name)

        if not provider:
            logger.error(
                f"Provider {config.provider_name} not available despite resolution"
            )
            # Try fallback
            from anvil.orchestrator import get_fallback_provider

            fallback_name = get_fallback_provider()
            if fallback_name:
                provider = get_provider(fallback_name)

        return provider, config

    def invalidate_cache(self):
        """Invalidate resolution cache (for hot-swapping)."""
        with self._cache_lock:
            self._cache.clear()
        logger.debug("Configuration cache invalidated")


# Global instance
_resolver = ConfigurationResolver()


def get_resolver() -> ConfigurationResolver:
    """Get the global configuration resolver instance."""
    return _resolver
