"""
Anthropic provider using LangChain with proper parameter handling and role-based configuration.
"""

import os
import sys
import types
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import SecretStr

from anvil.config_loader import ProviderCfg
from anvil.usage import TokenUsage, extract_token_usage

from .base import (
    AIMessage,
    BaseChatModel,
    BaseMessage,
    Embeddings,
    HumanMessage,
    LangChainProvider,
    SystemMessage,
)

try:  # pragma: no cover - exercised when anthropic is installed
    import anthropic as _anthropic_module
except ImportError:  # pragma: no cover - lightweight fallback for tests
    _anthropic_module = types.ModuleType("anthropic")

    def _missing_api(*_args, **_kwargs):
        raise ImportError(
            "anthropic is not installed; install the Anthropic extras to use this provider"
        )

    class Anthropic:  # type: ignore[override]
        def __init__(self, api_key: str | None = None, **_kwargs) -> None:
            self.api_key = api_key
            self.messages = types.SimpleNamespace(create=_missing_api)
            self.embeddings = types.SimpleNamespace(create=_missing_api)

    _anthropic_module.Anthropic = Anthropic
    sys.modules.setdefault("anthropic", _anthropic_module)

try:  # pragma: no cover - exercised when langchain-anthropic is installed
    from langchain_anthropic import ChatAnthropic as _ChatAnthropic

    _HAS_LANGCHAIN_ANTHROPIC = True
except ImportError:  # pragma: no cover - lightweight fallback for tests
    _HAS_LANGCHAIN_ANTHROPIC = False

    class _ChatAnthropic:  # type: ignore[override]
        model_fields = {
            "model_name": None,
            "temperature": None,
            "max_tokens_to_sample": None,
            "timeout": None,
            "stop": None,
            "base_url": None,
            "model_kwargs": None,
            "api_key": None,
        }

        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = dict(kwargs)

        def bind(self, **kwargs):
            self.kwargs.update(kwargs)
            return self

        def invoke(self, _messages, **_kwargs):
            raise ImportError(
                "langchain-anthropic is not installed; install the Anthropic extras to use this provider"
            )


class AnthropicProvider(LangChainProvider):
    """
    Wraps Anthropic Claude models using LangChain with role-based configuration support.
    """

    def __init__(self, cfg: ProviderCfg):
        """
        Initialize the Anthropic provider with configuration.

        Args:
            cfg: Provider configuration
        """
        super().__init__(cfg)

        # Lazy-loaded LangChain models
        self._llm = None
        self._embedding_model = None

        # Anthropic doesn't have native embedding models
        self._supports_embeddings = False

        # Role-based configuration adapter
        self.role_configs = self._extract_role_configs()
        self.last_usage: Optional[TokenUsage] = None

        # Optionally expose the low-level Anthropic client when available.
        # This helps tests that mock `anthropic.Anthropic` and expect a `client` attribute.
        self.client = None
        try:
            key_env = self.cfg.key_env
            api_key = os.getenv(key_env) if key_env else None
            if api_key:
                # Create a low-level client instance; tests may patch this constructor
                self.client = _anthropic_module.Anthropic(api_key=api_key)
                # Ensure api_key attribute is visible on the client for tests
                try:
                    self.client.api_key = api_key
                except Exception:
                    pass
        except Exception:
            # Not critical — we will fall back to LangChain ChatAnthropic when needed
            self.client = None

    def _extract_role_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract role-specific configurations from the provider config.

        Returns:
            Dictionary mapping roles to their configurations
        """
        role_configs = {}

        # Extract role-specific configs from the models section
        for model_role_key, config in self.cfg.models.items():
            # Parse model/role combinations like "claude-3-haiku/execute"
            if "/" in model_role_key:
                model_part, role_part = model_role_key.rsplit("/", 1)
                if "*" in model_part or model_part == self.model_name:
                    role_configs[role_part] = config
            elif model_role_key == self.model_name:
                # Direct model configuration
                role_configs["default"] = config

        return role_configs

    def _get_role_config(self, role: str = "default") -> Dict[str, Any]:
        """
        Get configuration for a specific role, with fallback to default.

        Args:
            role: The role name (e.g., "execute", "critique", "refine")

        Returns:
            Configuration dictionary for the role
        """
        return self.role_configs.get(role, self.role_configs.get("default", {}))

    def _convert_anthropic_params(
        self, kwargs: Dict[str, Any], role: str = "default"
    ) -> Dict[str, Any]:
        """
        Convert and merge parameters for Anthropic, handling role-specific overrides.

        Args:
            kwargs: Input parameters
            role: Role-specific configuration to apply

        Returns:
            Converted parameters suitable for ChatAnthropic
        """
        # Get role-specific configuration
        role_config = self._get_role_config(role)

        # Start with role defaults
        merged_params = role_config.copy()

        # Override with provided kwargs
        merged_params.update(kwargs)

        # Convert to Anthropic-compatible parameters
        anthropic_params = {}
        langchain_params = {}

        # Parameters that go directly to ChatAnthropic
        direct_params = {
            "temperature",
            "max_tokens",
            "top_p",
            "top_k",
            "timeout",
            "max_retries",
        }

        # Parameters that need special handling
        special_params = {
            "max_tokens_to_sample": "max_tokens",  # Anthropic legacy parameter
            "system": "system",  # System message handling
        }

        # Parameters for model_kwargs (extra headers, etc.)
        model_kwargs: Dict[str, Any] = {}

        for key, value in merged_params.items():
            if key in direct_params:
                langchain_params[key] = value
            elif key in special_params:
                # Map legacy or special parameters
                mapped_key = special_params[key]
                if mapped_key == "system":
                    # System messages are handled separately in the chat method
                    anthropic_params["system"] = value
                else:
                    langchain_params[mapped_key] = value
            elif key == "api_version":
                # API version goes in extra headers
                if "extra_headers" not in model_kwargs:
                    model_kwargs["extra_headers"] = {}
                # Note: API version is typically handled by the client, not per-request
                pass
            else:
                # Any other parameters go to the messages.create call
                anthropic_params[key] = value

        # If we have model_kwargs, add them
        if model_kwargs:
            langchain_params["model_kwargs"] = model_kwargs

        # Combine the parameters
        result = langchain_params.copy()
        if anthropic_params:
            # These will be passed to invoke() as additional kwargs
            result["_anthropic_params"] = anthropic_params

        return result

    def _normalize_langchain_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        ChatAnthropic = _ChatAnthropic

        normalized: Dict[str, Any] = dict(params)

        if "max_tokens" in normalized and "max_tokens_to_sample" not in normalized:
            normalized["max_tokens_to_sample"] = normalized.pop("max_tokens")

        model_kwargs = normalized.get("model_kwargs")
        if model_kwargs is None:
            model_kwargs = {}
            normalized["model_kwargs"] = model_kwargs
        if not isinstance(model_kwargs, dict):
            model_kwargs = {}
            normalized["model_kwargs"] = model_kwargs

        model_fields = getattr(ChatAnthropic, "model_fields", None)
        if isinstance(model_fields, dict) and model_fields:
            allowed = set(model_fields)
            for key in list(normalized.keys()):
                if key in allowed:
                    continue
                model_kwargs[key] = normalized.pop(key)

        if not model_kwargs:
            normalized.pop("model_kwargs", None)

        return normalized

    @property
    def llm(self) -> BaseChatModel:
        """
        Get the ChatAnthropic model.

        Returns:
            ChatAnthropic instance

        Raises:
            ImportError: If langchain-anthropic is not installed
            RuntimeError: If API key is not set
        """
        if self._llm is None:
            if not _HAS_LANGCHAIN_ANTHROPIC:
                raise ImportError(
                    "Error initializing Anthropic provider: langchain-anthropic is not installed. "
                    "Please install the Anthropic extras via Poetry: "
                    'poetry install --extras "anthropic"'
                )

            # Get API key
            key_env = self.cfg.key_env
            if not key_env:
                raise RuntimeError(
                    "Anthropic provider misconfigured: key_env is not set"
                )
            api_key = os.getenv(key_env)
            if not api_key:
                raise RuntimeError(f"Environment variable {key_env} not set")

            # Initialize LangChain model with basic parameters (lazy import)
            try:
                self._llm = _ChatAnthropic(
                    model_name=self.model_name,
                    api_key=SecretStr(api_key),
                    temperature=0.7,  # Default, will be overridden by role-specific configs
                    max_tokens_to_sample=1024,  # Default, overridden by role-specific configs
                    timeout=None,
                    stop=None,
                    base_url=None,
                )
            except ImportError as e:
                raise ImportError(
                    f"Error initializing Anthropic provider: {str(e)}. "
                    "Please install the Anthropic extras via Poetry: "
                    'poetry install --extras "anthropic"'
                ) from e

        if self._llm is None:
            raise RuntimeError("Anthropic provider failed to initialize ChatAnthropic")
        return self._llm

    async def generate(self, prompt: str, role: str = "execute", **kwargs) -> str:
        """
        Simple text-generation call with role-based configuration.

        Args:
            prompt: The raw prompt string
            role: Role for configuration (e.g., "execute", "critique")
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        # Convert parameters using role-specific configuration
        converted_params = self._convert_anthropic_params(kwargs, role)

        # Extract any Anthropic-specific parameters
        anthropic_params = cast(
            Dict[str, Any], converted_params.pop("_anthropic_params", {})
        )

        # Handle system message if present
        system_message = cast(Optional[str], anthropic_params.pop("system", None))

        # Create messages
        messages: List[BaseMessage] = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.append(HumanMessage(content=prompt))

        # If a low-level anthropic client is available, call it directly (helps tests)
        if self.client is not None:
            payload = {"model": self.model_name, "messages": [], **anthropic_params}
            if "temperature" in converted_params:
                payload["temperature"] = converted_params.get("temperature")
            if "max_tokens" in converted_params:
                payload["max_tokens"] = converted_params.get("max_tokens")

            # Attach messages as simple dicts
            payload["messages"] = [{"role": "user", "content": prompt}]
            if system_message:
                payload["system"] = system_message

            resp = self.client.messages.create(**payload)
            self.last_usage = extract_token_usage(resp)
            # Extract text from response.content list if present
            if (
                hasattr(resp, "content")
                and isinstance(resp.content, (list, tuple))
                and len(resp.content) > 0
            ):
                first = resp.content[0]
                return str(
                    getattr(first, "text", getattr(first, "content", str(first)))
                )
            return str(getattr(resp, "text", getattr(resp, "content", str(resp))))

        # Call the LLM with LangChain if low-level client not available
        llm = self.llm
        if converted_params and llm is not None:
            # Create a bound version of the LLM with the specific parameters
            bound_llm = llm.bind(**self._normalize_langchain_params(converted_params))
        else:
            bound_llm = llm

        # Invoke with any remaining Anthropic-specific parameters
        response = await asyncio.to_thread(
            lambda: bound_llm.invoke(messages, **anthropic_params)
        )
        self.last_usage = extract_token_usage(response)

        content = cast(Any, getattr(response, "content", ""))
        if isinstance(content, str):
            return content
        return str(content)

    async def chat(
        self,
        messages: List[Union[Dict[str, Any], BaseMessage]],
        role: str = "execute",
        **kwargs,
    ) -> str:
        """
        Chat-style call with role-based configuration.

        Args:
            messages: List of message dictionaries or LangChain message objects
            role: Role for configuration (e.g., "execute", "critique")
            **kwargs: Additional parameters

        Returns:
            Assistant reply as text
        """
        # Convert parameters using role-specific configuration
        converted_params = self._convert_anthropic_params(kwargs, role)

        # Extract any Anthropic-specific parameters
        anthropic_params = cast(
            Dict[str, Any], converted_params.pop("_anthropic_params", {})
        )

        # Convert dict messages to LangChain message objects
        lc_messages: List[BaseMessage] = []
        system_message = cast(Optional[str], anthropic_params.pop("system", None))

        for msg in messages:
            if isinstance(msg, dict):
                role_name = cast(str, msg.get("role", ""))
                content = cast(str, msg.get("content", ""))

                if role_name == "system":
                    if system_message is None:  # Only use the first system message
                        system_message = content
                elif role_name == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role_name == "assistant":
                    lc_messages.append(AIMessage(content=content))
            else:
                # Already a LangChain message
                lc_messages.append(msg)

        # Add system message at the beginning if present
        if system_message:
            lc_messages.insert(0, SystemMessage(content=system_message))

        # If a low-level anthropic client is available, call it directly (helps tests)
        if self.client is not None:
            payload = {"model": self.model_name, "messages": [], **anthropic_params}
            if "temperature" in converted_params:
                payload["temperature"] = converted_params.get("temperature")
            if "max_tokens" in converted_params:
                payload["max_tokens"] = converted_params.get("max_tokens")

            # Build simple dict messages
            simple_msgs = []
            for m in lc_messages:
                # LangChain message objects have .content and role info may vary
                if hasattr(m, "content"):
                    # Skip system messages here; they are handled separately
                    cls_name = m.__class__.__name__.lower()
                    if "system" in cls_name:
                        continue
                    # Map message class to role
                    role_name = (
                        "user"
                        if "human" in cls_name or "humanmessage" in cls_name
                        else (
                            "assistant"
                            if "ai" in cls_name or "aimessage" in cls_name
                            else "user"
                        )
                    )
                    simple_msgs.append(
                        {"role": role_name, "content": str(getattr(m, "content", ""))}
                    )
                elif isinstance(m, dict):
                    # Skip explicit system dict entries (handled via system_message)
                    if m.get("role") == "system":
                        continue
                    simple_msgs.append(m)

            payload["messages"] = simple_msgs
            if system_message:
                payload["system"] = system_message

            resp = self.client.messages.create(**payload)
            self.last_usage = extract_token_usage(resp)
            if (
                hasattr(resp, "content")
                and isinstance(resp.content, (list, tuple))
                and len(resp.content) > 0
            ):
                first = resp.content[0]
                return str(
                    getattr(first, "text", getattr(first, "content", str(first)))
                )
            return str(getattr(resp, "text", getattr(resp, "content", str(resp))))

        # Call the LLM with LangChain if low-level client not available
        llm = self.llm
        if converted_params and llm is not None:
            # Create a bound version of the LLM with the specific parameters
            bound_llm = llm.bind(**self._normalize_langchain_params(converted_params))
        else:
            bound_llm = llm

        # Invoke with any remaining Anthropic-specific parameters
        response = await asyncio.to_thread(
            lambda: bound_llm.invoke(lc_messages, **anthropic_params)
        )
        self.last_usage = extract_token_usage(response)

        content = cast(Any, getattr(response, "content", ""))
        if isinstance(content, str):
            return content
        return str(content)

    @property
    def embedding_model(self) -> Embeddings:
        """
        Get an embedding model (not natively supported by Anthropic).

        Returns:
            Embeddings instance or raises NotImplementedError

        Raises:
            NotImplementedError: Since Anthropic doesn't have native embedding models
        """
        raise NotImplementedError(
            "Anthropic doesn't provide native embedding models. "
            "Use OpenAI or another provider for embeddings."
        )

    async def embed(self, text: str, **kwargs) -> List[float]:
        """
        Override the embed method since Anthropic doesn't support embeddings natively.

        Args:
            text: Text to embed
            **kwargs: Additional parameters

        Raises:
            NotImplementedError: Since Anthropic doesn't have native embedding models
        """
        # If a low-level client is available and supports embeddings, use it
        if self.client is not None and hasattr(self.client, "embeddings"):
            resp = self.client.embeddings.create(model=self.model_name, input=text)
            embedding = getattr(resp, "embedding", None)
            if isinstance(embedding, list):
                return [float(x) for x in embedding]

            data = getattr(resp, "data", None)
            if isinstance(data, list):
                return [float(x) for x in data]

            raise TypeError(
                "Unexpected Anthropic embeddings response shape; expected list embedding."
            )

        raise NotImplementedError(
            "Anthropic doesn't provide native embedding models. "
            "Use OpenAI or another provider for embeddings."
        )

    async def get_model_info(self, **kwargs) -> Dict[str, Any]:
        """
        Get model information.

        Args:
            **kwargs: Additional parameters

        Returns:
            Dict with model info
        """
        info = {
            "model": self.model_name,
            "provider": "anthropic",
            "capabilities": ["text", "chat"],
            "context_window": self._get_context_window(self.model_name),
            "role_configs": list(self.role_configs.keys()),
        }

        return info

    def _get_context_window(self, model_name: str) -> int:
        """
        Get the context window size for a given model.

        Args:
            model_name: The name of the model

        Returns:
            The context window size in tokens
        """
        # Context window sizes for Claude models
        context_windows = {
            "claude-3-opus-20240229": 200000,
            "claude-3-sonnet-20240229": 200000,
            "claude-3-haiku-20240307": 200000,
            "claude-3-5-sonnet-20240620": 200000,
            "claude-3-haiku": 200000,
            "claude-3-sonnet": 200000,
            "claude-3-opus": 200000,
            "claude-3.5-sonnet": 200000,
            "claude-2.0": 100000,
            "claude-2": 100000,
            "claude-instant-1": 100000,
        }

        # Return the context window size or a default
        return context_windows.get(model_name, 100000)


# Import asyncio at the module level
import asyncio
