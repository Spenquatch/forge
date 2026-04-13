# anvil/config_loader.py
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ProviderCfg(BaseModel):
    """Configuration for a model provider."""

    type: str
    class_path: str
    key_env: Optional[str] = None
    framework: Optional[str] = None
    model_name: Optional[str] = None
    model_path: Optional[str] = None
    device: Optional[str] = None
    binary: Optional[str] = None
    default_args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    models: Dict[str, Any] = Field(default_factory=dict)


def _load_yaml_module():
    try:
        return importlib.import_module("yaml")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML is required to load Forge YAML config files. "
            "Install project dependencies with `poetry install` or run the CLI "
            "via `poetry run python -m anvil.cli ...`."
        ) from exc


def load_config(
    path: str = "config/models.yaml",
) -> Tuple[Dict[str, ProviderCfg], Dict[str, str]]:
    """
    Load the configuration from the yaml file.

    Args:
        path: Path to the configuration file

    Returns:
        Tuple of (providers, default_pipeline)
    """
    try:
        yaml = _load_yaml_module()

        # Load and parse the YAML file
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        raw = yaml.safe_load(config_path.read_text())

        # Process provider configurations
        providers = {
            name: ProviderCfg(**cfg) for name, cfg in raw.get("providers", {}).items()
        }

        # Get default pipeline if present
        default_pipeline = raw.get("default_pipeline", {})

        return providers, default_pipeline
    except RuntimeError:
        raise
    except Exception as e:
        print(f"Error loading configuration: {e}")
        # Return empty defaults in case of error
        return {}, {}
