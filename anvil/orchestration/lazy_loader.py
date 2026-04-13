"""
Lazy Provider Initialization Logic

This module implements lazy provider initialization with prewarm option to reduce CLI startup time.
"""

import logging
from typing import Any, Dict, Tuple

from anvil.config_loader import ProviderCfg, load_config
from anvil.providers import (
    clear_registry,
    get_registry_status,
    initialize_provider,
    register_provider_config,
)

logger = logging.getLogger(__name__)


def reload_config_lazy(
    path: str = "config/models.yaml",
    prewarm: bool = False,
) -> Tuple[Dict[str, ProviderCfg], Dict[str, str]]:
    """
    Reload the configuration and optionally prewarm all providers.

    Args:
        path: Path to the config file
        prewarm: If True, initialize all providers immediately.
                 If False, only register configurations without initialization.

    Returns:
        Tuple of (providers, default_pipeline)
    """
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

        # If prewarm is requested, try to initialize the provider immediately
        if prewarm:
            try:
                if initialize_provider(name):
                    registered_providers.append(name)
                else:
                    failed_providers.append(name)
            except Exception as e:
                logger.debug("Provider %s failed to prewarm: %s", name, str(e))
                failed_providers.append(name)
        else:
            # When not prewarming, we don't initialize providers but they will
            # be initialized on first use (lazy loading)
            logger.debug("Provider %s registered but not initialized (lazy mode)", name)

    # Log registration results
    if registered_providers:
        logger.debug(
            "Successfully prewarmed %s of %s providers",
            len(registered_providers),
            len(providers),
        )
    if failed_providers:
        logger.debug(
            "Failed to prewarm %s providers: %s",
            len(failed_providers),
            ", ".join(failed_providers),
        )

    # Return the loaded configuration
    return providers, default_pipeline


def get_provider_status_lazy() -> Dict[str, Dict[str, Any]]:
    """
    Get the status of all registered providers with lazy initialization support.

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
