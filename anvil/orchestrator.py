"""
Central orchestration module for the Forge system.
Handles configuration loading, provider registration, and system initialization.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from anvil.config_loader import ProviderCfg, load_config
from anvil.providers import (
    clear_registry,
    get_registry_status,
    initialize_provider,
    register_provider_config,
)

logger = logging.getLogger(__name__)


def reload_config(
    path: str = "config/models.yaml",
) -> Tuple[Dict[str, ProviderCfg], Dict[str, str]]:
    """
    Reload the configuration and register all providers.

    Args:
        path: Path to the config file

    Returns:
        Tuple of (providers, default_pipeline)
    """
    # Load environment variables from .env file if it exists
    _load_environment_variables()

    # Load configuration
    providers, default_pipeline = load_config(path)

    # Clear existing registry
    clear_registry()

    # Register providers
    registered_providers = []
    failed_providers = []

    for name, cfg in providers.items():
        # Register configuration for all providers
        register_provider_config(name, cfg)

        # Try to initialize non-conflicting providers immediately
        # but don't worry if they fail - they'll be initialized on first use
        try:
            if initialize_provider(name):
                registered_providers.append(name)
            else:
                failed_providers.append(name)
        except Exception as e:
            logger.debug(
                "Provider %s will be initialized when first used: %s", name, str(e)
            )
            failed_providers.append(name)

    # Log registration results
    if registered_providers:
        logger.debug(
            "Successfully registered %s of %s providers",
            len(registered_providers),
            len(providers),
        )
    if failed_providers:
        logger.debug(
            "Failed to register %s providers: %s",
            len(failed_providers),
            ", ".join(failed_providers),
        )

    # Return the loaded configuration
    return providers, default_pipeline


def _load_environment_variables() -> None:
    """Load environment variables from .env file."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
    else:
        logger.debug(
            ".env file not found. Environment variables may not be loaded correctly."
        )


def get_provider_status() -> Dict[str, Dict[str, Any]]:
    """
    Get the status of all registered providers.

    Returns:
        Dictionary of provider status information
    """
    # Use the new registry status function
    status = get_registry_status()

    # Convert to the expected format
    result = {}

    # Include initialized providers
    for name in status["initialized"]:
        result[name] = {
            "initialized": True,
            "available": True,
            "type": "unknown",  # We'd need to get this from config
            "model": "unknown",
        }

    # Include providers that are configured but not initialized
    for name in status["configured"]:
        if name not in result:
            available = name in status["available"]
            result[name] = {
                "initialized": False,
                "available": available,
                "type": "unknown",
                "model": "unknown",
            }

    return result


def check_env_variables() -> Dict[str, bool]:
    """
    Check if required environment variables are set.

    Returns:
        Dictionary with environment variable status
    """
    providers, _ = load_config()
    required_vars = {}

    for name, cfg in providers.items():
        if cfg.key_env:
            is_set = bool(os.getenv(cfg.key_env))
            required_vars[cfg.key_env] = is_set

            if not is_set:
                logger.warning(
                    "Required environment variable %s for provider %s is not set",
                    cfg.key_env,
                    name,
                )

    return required_vars


def get_available_providers() -> List[str]:
    """
    Get a list of available (successfully registered) providers.

    Returns:
        List of provider names
    """
    status = get_registry_status()
    available = status.get("available")
    if isinstance(available, list):
        return [str(item) for item in available]
    return []


def get_fallback_provider() -> Optional[str]:
    """
    Get a fallback provider from the registry.
    Prioritizes first-class CLI providers, then API providers, then locals.

    Returns:
        Provider name or None if no providers are available
    """
    available = get_available_providers()
    if not available:
        return None

    # Priority order for fallbacks
    for provider in ["codex_cli", "claude_code", "openai", "anthropic"]:
        if provider in available:
            return provider

    # Return the first available provider
    return available[0]
