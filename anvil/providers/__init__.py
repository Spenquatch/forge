"""
Provider registry and initialization system following AI/ML best practices.
Handles dynamic loading and registration of model providers with proper error handling,
logging, and type safety.
"""

import importlib
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Type, Union, cast

from anvil.config_loader import ProviderCfg
from anvil.providers.base import LangChainProvider, ModelProvider

# Configure logging
logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Thread-safe provider registry with proper error handling and logging.
    Follows singleton pattern for global state management.
    """

    _instance: Optional["ProviderRegistry"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._providers: Dict[str, Union[ModelProvider, LangChainProvider]] = {}
            self._configs: Dict[str, ProviderCfg] = {}
            self._failed_providers: Dict[str, str] = {}
            ProviderRegistry._initialized = True

    @property
    def providers(self) -> Dict[str, Union[ModelProvider, LangChainProvider]]:
        """Get read-only view of registered providers."""
        return self._providers.copy()

    @property
    def configs(self) -> Dict[str, ProviderCfg]:
        """Get read-only view of provider configurations."""
        return self._configs.copy()

    @property
    def failed_providers(self) -> Dict[str, str]:
        """Get information about providers that failed to initialize."""
        return self._failed_providers.copy()

    def register_config(self, name: str, config: ProviderCfg) -> None:
        """
        Register a provider configuration without initializing the provider.

        Args:
            name: Provider name
            config: Provider configuration

        Raises:
            ValueError: If name is empty or config is invalid
        """
        if not name or not name.strip():
            raise ValueError("Provider name cannot be empty")

        if not isinstance(config, ProviderCfg):
            raise ValueError("Config must be a ProviderCfg instance")

        self._configs[name] = config
        logger.info(f"Registered configuration for provider: {name}")

    def initialize_provider(
        self, name: str
    ) -> Optional[Union[ModelProvider, LangChainProvider]]:
        """
        Initialize a provider from its configuration.

        Args:
            name: Provider name

        Returns:
            Provider instance or None if initialization failed
        """
        if name in self._providers:
            logger.debug(f"Provider {name} already initialized")
            return self._providers[name]

        if name not in self._configs:
            logger.error(f"No configuration found for provider: {name}")
            return None

        config = self._configs[name]

        try:
            provider_cls = self._load_provider_class(config.class_path)
            if not provider_cls:
                return None

            provider = provider_cls(config)
            self._providers[name] = provider

            # Remove from failed providers if it was there
            if name in self._failed_providers:
                del self._failed_providers[name]

            logger.info(f"Successfully initialized provider: {name}")
            return provider

        except Exception as e:
            error_msg = f"Failed to initialize provider {name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._failed_providers[name] = str(e)
            return None

    def get_provider(
        self, name: str
    ) -> Optional[Union[ModelProvider, LangChainProvider]]:
        """
        Get a provider by name, initializing it if necessary.

        Args:
            name: Provider name

        Returns:
            Provider instance or None if not available
        """
        # Try to get existing provider
        if name in self._providers:
            return self._providers[name]

        # Try to initialize if config exists
        if name in self._configs:
            return self.initialize_provider(name)

        logger.warning(f"Provider '{name}' not found in registry")
        return None

    def get_or_fallback_provider(
        self, name: str
    ) -> Optional[Union[ModelProvider, LangChainProvider]]:
        """
        Get a provider by name or return a fallback provider.

        Args:
            name: Preferred provider name

        Returns:
            Provider instance or fallback provider
        """
        provider = self.get_provider(name)
        if provider:
            return provider

        # Try fallback providers in order of preference
        fallback_order = [
            "codex_cli",
            "claude_code",
            "openai",
            "anthropic",
            "phi3-mini",
            "tinyllama",
        ]

        for fallback_name in fallback_order:
            if fallback_name != name:  # Don't try the same provider again
                fallback_provider = self.get_provider(fallback_name)
                if fallback_provider:
                    logger.warning(
                        f"Using fallback provider {fallback_name} instead of {name}"
                    )
                    return fallback_provider

        logger.error("No providers available")
        return None

    def is_provider_available(self, name: str) -> bool:
        """
        Check if a provider is available (initialized or can be initialized).

        Args:
            name: Provider name

        Returns:
            True if provider is available
        """
        import os
        import shutil
        from pathlib import Path

        # Already initialized
        if name in self._providers:
            return True

        # Must be configured and not previously failed
        if name in self._configs and name not in self._failed_providers:
            try:
                config = self._configs[name]
                provider_cls = self._load_provider_class(config.class_path)
                if provider_cls is None:
                    return False

                provider_type = (config.type or "").lower()
                if provider_type == "cli":
                    binary_name = config.binary
                    if name == "codex_cli":
                        binary_name = os.getenv("FORGE_CODEX_BIN", "") or binary_name
                    elif name == "claude_code":
                        binary_name = os.getenv("FORGE_CLAUDE_BIN", "") or binary_name
                    if not binary_name:
                        return False
                    return shutil.which(binary_name) is not None

                # Lightweight readiness checks for local frameworks
                framework = (config.framework or "").lower()
                if framework == "llama_cpp":
                    try:
                        import importlib

                        importlib.import_module("llama_cpp")
                    except Exception:
                        return False
                    # Require local model file to exist
                    if not config.model_path or not Path(config.model_path).exists():
                        return False
                elif framework == "transformers":
                    # If model_name looks like a local path, require it to exist
                    mn = config.model_name or ""
                    if any(sep in mn for sep in ("/", "\\")):
                        # Paths like 'models/foo' or '/abs/path'
                        p = Path(mn)
                        if not p.exists():
                            # Not fatal if it's a remote ID, but when it looks like a path and doesn't exist, mark unavailable
                            return False

                return True
            except Exception:
                return False

        return False

    def register_and_initialize(self, name: str, config: ProviderCfg) -> bool:
        """
        Register configuration and immediately initialize the provider.

        Args:
            name: Provider name
            config: Provider configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            self.register_config(name, config)
            provider = self.initialize_provider(name)
            return provider is not None
        except Exception as e:
            logger.error(f"Failed to register and initialize provider {name}: {e}")
            return False

    def clear(self) -> None:
        """Clear all providers and configurations."""
        self._providers.clear()
        self._configs.clear()
        self._failed_providers.clear()
        logger.info("Provider registry cleared")

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all providers.

        Returns:
            Status dictionary with provider information
        """
        available: List[str] = []
        status: Dict[str, Any] = {
            "initialized": list(self._providers.keys()),
            "configured": list(self._configs.keys()),
            "failed": dict(self._failed_providers),
            "available": available,
        }

        for name in self._configs:
            if self.is_provider_available(name):
                available.append(name)

        return status

    def _load_provider_class(
        self, class_path: str
    ) -> Optional[Type[Union[ModelProvider, LangChainProvider]]]:
        """
        Load a provider class from its path with caching.

        Args:
            class_path: Dot-separated path to the class

        Returns:
            Provider class or None if not found
        """
        if not hasattr(self, "_class_cache"):
            self._class_cache: Dict[
                str, Optional[Type[Union[ModelProvider, LangChainProvider]]]
            ] = {}

        if class_path in self._class_cache:
            return self._class_cache[class_path]

        try:
            module_path, cls_name = class_path.rsplit(".", 1)

            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                self._log_import_error(e, module_path)
                return None

            if not hasattr(module, cls_name):
                logger.error(f"Class {cls_name} not found in module {module_path}")
                return None

            provider_cls = getattr(module, cls_name)
            if not isinstance(provider_cls, type):
                logger.error(f"Class {cls_name} in {module_path} is not a type")
                self._class_cache[class_path] = None
                return None

            # Validate that it's a proper provider class
            if not (
                issubclass(provider_cls, ModelProvider)
                or issubclass(provider_cls, LangChainProvider)
            ):
                logger.error(f"Class {cls_name} is not a valid provider class")
                self._class_cache[class_path] = None
                return None

            typed_cls = cast(
                Type[Union[ModelProvider, LangChainProvider]], provider_cls
            )
            self._class_cache[class_path] = typed_cls
            return typed_cls

        except Exception as e:
            logger.error(
                f"Unexpected error loading provider class {class_path}: {e}",
                exc_info=True,
            )
            self._class_cache[class_path] = None
            return None

    def _log_import_error(self, error: ImportError, module_path: str) -> None:
        """Log import errors with helpful suggestions."""
        error_msg = str(error)

        if "No module named" in error_msg:
            missing_module = error_msg.split("'")[1] if "'" in error_msg else "unknown"

            suggestions = {
                "langchain_openai": 'poetry install --extras "openai"',
                "langchain_anthropic": 'poetry install --extras "anthropic"',
                "transformers": 'poetry install --extras "transformers"',
                "torch": 'poetry install --extras "transformers"',
                "openai": 'poetry install --extras "openai"',
                "anthropic": 'poetry install --extras "anthropic"',
                "llama_cpp": 'poetry install --extras "llama-cpp"',
            }

            suggestion = suggestions.get(missing_module, f"poetry add {missing_module}")
            logger.error(f"Missing dependency: {missing_module}. Try: {suggestion}")
        else:
            logger.error(f"Error importing module {module_path}: {error_msg}")


# Global registry instance
_registry = ProviderRegistry()

# Public API functions for backward compatibility and ease of use


def register_provider_config(name: str, config: ProviderCfg) -> None:
    """Register a provider configuration."""
    _registry.register_config(name, config)


def initialize_provider(name: str) -> Optional[Union[ModelProvider, LangChainProvider]]:
    """Initialize a provider."""
    return _registry.initialize_provider(name)


def get_provider(name: str) -> Optional[Union[ModelProvider, LangChainProvider]]:
    """Get a provider with fallback."""
    return _registry.get_or_fallback_provider(name)


def get_provider_exact(name: str) -> Optional[Union[ModelProvider, LangChainProvider]]:
    """Get a provider by name without applying fallback selection."""
    return _registry.get_provider(name)


def get_provider_config(name: str) -> Optional[ProviderCfg]:
    """Return the registered configuration for an exact provider name."""
    return _registry.configs.get(name)


def register_provider(name: str, config: ProviderCfg) -> bool:
    """Register and initialize a provider."""
    return _registry.register_and_initialize(name, config)


def clear_registry() -> None:
    """Clear the provider registry."""
    _registry.clear()


def get_available_providers() -> List[str]:
    """Get list of available provider names."""
    available = _registry.get_status().get("available")
    if isinstance(available, list):
        return [str(item) for item in available]
    return []


def get_registry_status() -> Dict[str, Any]:
    """Get comprehensive registry status."""
    return _registry.get_status()


def is_provider_available(name: str) -> bool:
    """Check if a provider is available."""
    return _registry.is_provider_available(name)


@contextmanager
def temporary_provider(name: str, config: ProviderCfg):
    """Context manager for temporary provider registration."""
    original_had_provider = name in _registry.providers
    original_provider = _registry.providers.get(name)

    try:
        _registry.register_and_initialize(name, config)
        yield _registry.get_provider(name)
    finally:
        if original_had_provider and original_provider:
            _registry._providers[name] = original_provider
        elif name in _registry._providers:
            del _registry._providers[name]
