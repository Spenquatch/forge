"""
utils.py - Utility functions for Forge.
"""

from typing import Any, Dict, Optional

from anvil.config_loader import ProviderCfg


def merged_kwargs(
    role: str,
    provider_cfg: ProviderCfg,
    state_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merges keyword arguments from different configuration sources with the following precedence:
    1. State override (highest priority)
    2. Role-specific config for the model
    3. Default role configuration

    Args:
        role: The role (e.g., 'execute', 'critique')
        provider_cfg: The provider configuration
        state_override: Optional runtime overrides

    Returns:
        Merged kwargs dictionary with None values filtered out
    """
    result = {}

    # First try with the actual model name
    model_name = provider_cfg.model_name or "default"

    # We need to check both the model_name and "default" for wildcard configurations
    for lookup_name in [model_name, "default"]:
        # Check for wildcard config first (name/*)
        wildcard_key = f"{lookup_name}/*"
        if wildcard_key in provider_cfg.models:
            wildcard_config = provider_cfg.models[wildcard_key]
            if isinstance(wildcard_config, dict) and role in wildcard_config:
                result.update(wildcard_config[role])

        # Check for specific role config (name/role)
        specific_key = f"{lookup_name}/{role}"
        if specific_key in provider_cfg.models:
            result.update(provider_cfg.models[specific_key])

    # Apply state overrides if any
    if state_override:
        result.update(state_override)

    # Filter out None values
    return {k: v for k, v in result.items() if v is not None}
