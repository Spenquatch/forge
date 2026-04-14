"""Provider wrappers for headless CLI agents."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Optional, Sequence

from anvil.cli_agents import BaseCliAgent, render_messages_as_transcript
from anvil.config_loader import ProviderCfg
from anvil.usage import TokenUsage

from .base import ModelProvider

logger = logging.getLogger(__name__)


class CliProviderBase(ModelProvider, ABC):
    """ModelProvider wrapper around a headless CLI adapter."""

    def __init__(self, cfg: ProviderCfg) -> None:
        super().__init__(cfg)
        self.model_name = cfg.model_name or next(iter(cfg.models.keys()), "") or ""
        self.role_configs = self._extract_role_configs()
        self.last_usage: Optional[TokenUsage] = None
        self.last_run_metadata: Dict[str, Any] = {}
        self.last_command: List[str] = []
        self.last_structured_output: Any | None = None
        self.last_cli_result: Any | None = None
        self._agent = self.build_agent(cfg)

    @abstractmethod
    def build_agent(self, cfg: ProviderCfg) -> BaseCliAgent:
        """Construct the low-level CLI adapter."""

    def _extract_role_configs(self) -> Dict[str, Dict[str, Any]]:
        role_configs: Dict[str, Dict[str, Any]] = {}
        for model_role_key, config in self.cfg.models.items():
            if "/" in model_role_key:
                model_part, role_part = model_role_key.rsplit("/", 1)
                if "*" in model_part or model_part == self.model_name:
                    if isinstance(config, Mapping):
                        role_configs[role_part] = dict(config)
            elif model_role_key == self.model_name and isinstance(config, Mapping):
                role_configs["default"] = dict(config)
        return role_configs

    def _get_role_config(self, role: str = "default") -> Dict[str, Any]:
        return dict(self.role_configs.get(role, self.role_configs.get("default", {})))

    def forces_default_model_arg(self) -> bool:
        """Whether the provider default should be passed as an explicit CLI model arg."""
        return True

    def reported_model_name(self, explicit_model: str | None = None) -> str | None:
        if explicit_model:
            return explicit_model
        if self.forces_default_model_arg():
            return self.model_name or None
        return None

    def _resolve_model_arg(self, merged_kwargs: Dict[str, Any]) -> str | None:
        if "model" in merged_kwargs:
            value = str(merged_kwargs.pop("model", "")) or None
            return value
        if self.forces_default_model_arg():
            return self.model_name or None
        return None

    def _merge_kwargs(self, role: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._get_role_config(role)
        merged.update(kwargs)
        if self.model_name and "model" not in merged and self.forces_default_model_arg():
            merged["model"] = self.model_name
        return merged

    async def generate(self, prompt: str, role: str = "execute", **kwargs: Any) -> str:
        system = kwargs.pop("system", None)
        messages: list[dict[str, Any]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, role=role, **kwargs)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        role: str = "execute",
        **kwargs: Any,
    ) -> str:
        merged_kwargs = self._merge_kwargs(role, dict(kwargs))
        model = self._resolve_model_arg(merged_kwargs)
        cwd = merged_kwargs.pop("cwd", None)
        prompt_text = render_messages_as_transcript(messages)

        result = await asyncio.to_thread(
            self._agent.run,
            prompt_text,
            model=model,
            options=merged_kwargs,
            cwd=cwd,
        )

        self.last_cli_result = result
        self.last_usage = result.usage
        self.last_run_metadata = dict(result.metadata)
        self.last_command = list(result.command)
        self.last_structured_output = result.structured_output

        if not result.ok:
            detail = result.error or result.stderr_text or result.stdout_text or "CLI agent failed"
            raise RuntimeError(detail)

        return result.text

    async def embed(self, text: str, **kwargs: Any) -> List[float]:
        logger.warning("CLI providers do not support embeddings. Returning empty vector.")
        return []

    async def get_model_info(self, **kwargs: Any) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "provider": self.__class__.__name__.replace("Provider", "").lower(),
            "provider_type": self.cfg.type,
            "binary": self.cfg.binary,
            "capabilities": ["text", "chat", "structured_output"],
            "supports_embeddings": False,
        }
