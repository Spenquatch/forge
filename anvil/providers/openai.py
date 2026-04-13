"""
OpenAI provider using LangChain with role-based configuration support.
"""

import os
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

try:  # pragma: no cover - exercised when langchain-openai is installed
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    _HAS_LANGCHAIN_OPENAI = True
except ImportError:  # pragma: no cover - lightweight fallback for tests
    _HAS_LANGCHAIN_OPENAI = False

    class ChatOpenAI:  # type: ignore[override]
        model_fields = {
            "model": None,
            "temperature": None,
            "max_tokens": None,
            "stop": None,
            "top_p": None,
            "frequency_penalty": None,
            "presence_penalty": None,
            "model_kwargs": None,
            "api_key": None,
            "system": None,
        }

        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = dict(kwargs)

        def model_copy(self, *, update=None, **_kwargs):
            if isinstance(update, dict):
                self.kwargs.update(update)
            return self

        def copy(self, *, update=None, **_kwargs):  # pragma: no cover
            return self.model_copy(update=update)

        def invoke(self, _messages):
            raise ImportError(
                "langchain-openai is not installed; install the OpenAI extras to use this provider"
            )

    class OpenAIEmbeddings:  # type: ignore[override]
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = dict(kwargs)

        def embed_query(self, _text: str) -> list[float]:
            raise ImportError(
                "langchain-openai is not installed; install the OpenAI extras to use embeddings"
            )


class OpenAIProvider(LangChainProvider):
    """
    Wraps OpenAI models using LangChain with role-based configuration support.
    """

    def __init__(self, cfg: ProviderCfg):
        """
        Initialize the OpenAI provider with configuration.

        Args:
            cfg: Provider configuration
        """
        super().__init__(cfg)

        # Default models
        self.embed_model_name = "text-embedding-3-small"

        # Lazy-loaded LangChain models
        self._llm = None
        self._embedding_model = None

        # Role-based configuration adapter
        self.role_configs = self._extract_role_configs()
        self.last_usage: Optional[TokenUsage] = None

    def _extract_role_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract role-specific configurations from the provider config.

        Returns:
            Dictionary mapping roles to their configurations
        """
        role_configs = {}

        # Extract role-specific configs from the models section
        for model_role_key, config in self.cfg.models.items():
            # Parse model/role combinations like "gpt-4o-mini/execute"
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

    def _convert_openai_params(
        self, kwargs: Dict[str, Any], role: str = "default"
    ) -> Dict[str, Any]:
        """
        Convert and merge parameters for OpenAI, handling role-specific overrides.

        Args:
            kwargs: Input parameters
            role: Role-specific configuration to apply

        Returns:
            Converted parameters suitable for ChatOpenAI
        """
        # Get role-specific configuration
        role_config = self._get_role_config(role)

        # Start with role defaults
        merged_params = role_config.copy()

        # Override with provided kwargs
        merged_params.update(kwargs)

        return self._normalize_langchain_params(merged_params)

    def _normalize_langchain_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = dict(params)

        system = normalized.pop("system", None)

        model_kwargs = normalized.get("model_kwargs")
        if model_kwargs is None:
            model_kwargs = {}
            normalized["model_kwargs"] = model_kwargs
        if not isinstance(model_kwargs, dict):
            model_kwargs = {}
            normalized["model_kwargs"] = model_kwargs

        model_fields = getattr(ChatOpenAI, "model_fields", None)
        if isinstance(model_fields, dict) and model_fields:
            allowed = set(model_fields)
            for key in list(normalized.keys()):
                if key in allowed:
                    continue
                model_kwargs[key] = normalized.pop(key)

        if not model_kwargs:
            normalized.pop("model_kwargs", None)

        if system is not None:
            normalized["system"] = system

        return normalized

    @property
    def llm(self) -> BaseChatModel:
        """
        Get the ChatOpenAI model.

        Returns:
            ChatOpenAI instance

        Raises:
            ImportError: If langchain-openai is not installed
            RuntimeError: If API key is not set
        """
        if self._llm is None:
            if not _HAS_LANGCHAIN_OPENAI:
                raise ImportError(
                    "Error using OpenAI provider: langchain-openai is not installed. "
                    "Please install the OpenAI extras via Poetry: "
                    'poetry install --extras "openai"'
                )

            # Get API key
            key_env = self.cfg.key_env
            if not key_env:
                raise RuntimeError("OpenAI provider misconfigured: key_env is not set")
            api_key = os.getenv(key_env)
            if not api_key:
                raise RuntimeError(f"Environment variable {key_env} not set")

            # Initialize LangChain model
            try:
                self._llm = ChatOpenAI(
                    model=self.model_name,
                    api_key=SecretStr(api_key),
                    temperature=0.7,  # Default, will be overridden by role-specific configs
                )
            except ImportError as e:
                raise ImportError(
                    f"Error using OpenAI provider: {str(e)}. "
                    "Please install the OpenAI extras via Poetry: "
                    'poetry install --extras "openai"'
                ) from e

        return self._llm

    @property
    def embedding_model(self) -> Embeddings:
        """
        Get the OpenAI embeddings model.

        Returns:
            OpenAIEmbeddings instance

        Raises:
            ImportError: If langchain-openai is not installed
            RuntimeError: If API key is not set
        """
        if self._embedding_model is None:
            if not _HAS_LANGCHAIN_OPENAI:
                raise ImportError(
                    "Error initializing OpenAI embeddings: langchain-openai is not installed. "
                    "Please install the OpenAI extras via Poetry: "
                    'poetry install --extras "openai"'
                )

            # Get API key
            key_env = self.cfg.key_env
            if not key_env:
                raise RuntimeError("OpenAI provider misconfigured: key_env is not set")
            api_key = os.getenv(key_env)
            if not api_key:
                raise RuntimeError(f"Environment variable {key_env} not set")

            # Initialize LangChain embedding model
            try:
                self._embedding_model = OpenAIEmbeddings(
                    model=self.embed_model_name,
                    api_key=SecretStr(api_key),
                )
            except ImportError as e:
                raise ImportError(
                    f"Error initializing OpenAI embeddings: {str(e)}. "
                    "Please install the OpenAI extras via Poetry: "
                    'poetry install --extras "openai"'
                ) from e

        return self._embedding_model

    async def generate(self, prompt: str, role: str = "execute", **kwargs) -> str:
        """
        Simple text-generation call with role-based configuration.

        Args:
            prompt: The raw prompt string
            role: Role for configuration (e.g., "execute", "critique")
            **kwargs: Additional parameters for the API call

        Returns:
            Generated text response
        """
        # Convert parameters using role-specific configuration
        converted_params = self._convert_openai_params(kwargs, role)

        # Create a messages format for the completion API
        messages: List[BaseMessage] = [HumanMessage(content=prompt)]

        # Handle system message if present
        if "system" in converted_params:
            system_content = cast(str, converted_params.pop("system"))
            messages.insert(0, SystemMessage(content=system_content))

        # Call the LLM with converted parameters
        llm = self.llm
        if converted_params:
            # Use a copied model instance so fields like `model_kwargs` are treated
            # as model configuration rather than invocation-time kwargs.
            if hasattr(llm, "model_copy"):
                llm = llm.model_copy(update=converted_params)
            else:  # pragma: no cover
                llm = llm.copy(update=converted_params)

        # Invoke the model
        import asyncio

        response = await asyncio.to_thread(lambda: llm.invoke(messages))
        self.last_usage = extract_token_usage(response)
        content = cast(Any, getattr(response, "content", ""))
        if isinstance(content, str):
            return content.strip()
        return str(content).strip()

    async def chat(
        self,
        messages: List[Union[Dict[str, Any], BaseMessage]],
        role: str = "execute",
        **kwargs,
    ) -> str:
        """
        Chat-style call with role-based configuration.

        Args:
            messages: List of message dicts or LangChain message objects
            role: Role for configuration (e.g., "execute", "critique")
            **kwargs: Additional parameters for the API call

        Returns:
            Assistant's reply as text
        """
        # Convert parameters using role-specific configuration
        converted_params = self._convert_openai_params(kwargs, role)

        # Convert dict messages to LangChain message objects
        lc_messages: List[BaseMessage] = []
        for msg in messages:
            if isinstance(msg, dict):
                role_name = cast(str, msg.get("role", ""))
                content = cast(str, msg.get("content", ""))

                if role_name == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role_name == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role_name == "assistant":
                    lc_messages.append(AIMessage(content=content))
            else:
                # Already a LangChain message
                lc_messages.append(msg)

        # Handle system message from converted_params
        if "system" in converted_params:
            system_content = cast(str, converted_params.pop("system"))
            lc_messages.insert(0, SystemMessage(content=system_content))

        # Call the LLM with converted parameters
        llm = self.llm
        if converted_params:
            # Use a copied model instance so fields like `model_kwargs` are treated
            # as model configuration rather than invocation-time kwargs.
            if hasattr(llm, "model_copy"):
                llm = llm.model_copy(update=converted_params)
            else:  # pragma: no cover
                llm = llm.copy(update=converted_params)

        # Invoke the model
        import asyncio

        response = await asyncio.to_thread(lambda: llm.invoke(lc_messages))
        self.last_usage = extract_token_usage(response)
        content = cast(Any, getattr(response, "content", ""))
        if isinstance(content, str):
            return content.strip()
        return str(content).strip()

    async def embed(self, text: str, **kwargs) -> List[float]:
        """
        Generate embeddings for input text.

        Args:
            text: Input text to embed
            **kwargs: Additional parameters for the API call

        Returns:
            List of floats representing the embedding vector
        """
        import asyncio

        try:
            resp = await asyncio.to_thread(
                lambda: self.embedding_model.embed_query(text)
            )
            return resp
        except ImportError as e:
            raise ImportError(
                f"Error using OpenAI provider: {str(e)}. "
                "Please install the OpenAI extras via Poetry: "
                'poetry install --extras "openai"'
            ) from e

    async def get_model_info(self, **kwargs) -> Dict[str, Any]:
        """
        Get model information.

        Args:
            **kwargs: Additional parameters

        Returns:
            Dictionary with model information
        """
        info = {
            "model": self.model_name,
            "provider": "openai",
            "capabilities": ["text", "chat", "embeddings"],
            "embedding_model": self.embed_model_name,
            "role_configs": list(self.role_configs.keys()),
        }
        return info
