"""
Base model provider using LangChain interfaces.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, cast

try:  # pragma: no cover - exercised when langchain is installed
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - lightweight fallback for CLI/local tests
    class BaseChatModel:  # type: ignore[override]
        pass

    class Embeddings:  # type: ignore[override]
        def embed_query(self, text: str) -> list[float]:
            raise RuntimeError("Embeddings require langchain-core to be installed")

    class BaseMessage:  # type: ignore[override]
        def __init__(self, content: str = "") -> None:
            self.content = content

    class HumanMessage(BaseMessage):
        pass

    class SystemMessage(BaseMessage):
        pass

    class AIMessage(BaseMessage):
        pass

from anvil.config_loader import ProviderCfg


class LangChainProvider(ABC):
    """
    Provider that wraps LangChain model interfaces.
    This base class handles the common operations for all providers.
    """

    def __init__(self, cfg: ProviderCfg) -> None:
        """
        Initialize the provider with configuration.

        Args:
            cfg: Provider configuration
        """
        self.cfg = cfg
        self.model_name: str = cfg.model_name or next(iter(cfg.models.keys()), "") or ""
        self._llm: Optional[BaseChatModel] = None
        self._embedding_model: Optional[Embeddings] = None

    @property
    @abstractmethod
    def llm(self) -> BaseChatModel:
        """Get the LangChain language model."""
        ...

    @property
    @abstractmethod
    def embedding_model(self) -> Embeddings:
        """Get the LangChain embedding model."""
        ...

    async def generate(self, prompt: str, role: str = "execute", **kwargs: Any) -> str:
        """
        Simple text-generation call that converts to chat format.

        Args:
            prompt: The raw prompt string
            role: Role for configuration (e.g., "execute", "critique")
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        # If there's a system prompt in kwargs, use it
        system: Optional[str] = cast(Optional[str], kwargs.pop("system", None))

        # Create messages
        messages: List[Union[Dict[str, Any], BaseMessage]] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        # Call the chat method with role
        return await self.chat(messages, role=role, **kwargs)

    async def chat(
        self,
        messages: List[Union[Dict[str, Any], BaseMessage]],
        role: str = "execute",
        **kwargs: Any,
    ) -> str:
        """
        Chat-style call with message objects.

        Args:
            messages: List of message dictionaries or LangChain message objects
            role: Role for configuration (e.g., "execute", "critique")
            **kwargs: Additional parameters

        Returns:
            Assistant reply as text
        """
        # Convert dict messages to LangChain message objects if needed
        lc_messages: List[BaseMessage] = []
        for msg in messages:
            if isinstance(msg, dict):
                role_name = msg.get("role", "")
                content = cast(str, msg.get("content", ""))

                if role_name == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role_name == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role_name == "assistant":
                    lc_messages.append(AIMessage(content=content))
                # Ignore other roles
            else:
                # Already a LangChain message
                lc_messages.append(msg)

        # Convert kwargs format if needed
        lc_kwargs = self._convert_kwargs(kwargs)

        # Call LLM asynchronously
        response = await asyncio.to_thread(
            lambda: self.llm.invoke(lc_messages, **lc_kwargs)
        )

        content = cast(Any, getattr(response, "content", ""))
        if isinstance(content, str):
            return content
        return str(content)

    async def embed(self, text: str, **kwargs: Any) -> List[float]:
        """
        Embedding call.

        Args:
            text: Text to embed
            **kwargs: Additional parameters

        Returns:
            List of floats (vector)
        """
        # Call embedding model asynchronously
        embeddings = cast(
            List[float],
            await asyncio.to_thread(lambda: self.embedding_model.embed_query(text)),
        )

        return embeddings

    async def get_model_info(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Get model info.

        Args:
            **kwargs: Additional parameters

        Returns:
            Dict with model info
        """
        # Basic info that should be available for all models
        return {
            "model": self.model_name,
            "provider": self._get_provider_name(),
            "capabilities": self._get_capabilities(),
        }

    def _get_provider_name(self) -> str:
        """Get the provider name."""
        return self.__class__.__name__.replace("Provider", "").lower()

    def _get_capabilities(self) -> List[str]:
        """Get the capabilities of this provider."""
        capabilities: List[str] = []
        if self._llm is not None:
            capabilities.extend(["text", "chat"])
        if self._embedding_model is not None:
            capabilities.append("embeddings")
        return capabilities

    def _convert_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standard kwargs to LangChain-specific kwargs.

        Args:
            kwargs: Standard kwargs

        Returns:
            LangChain-compatible kwargs
        """
        # Copy kwargs to avoid modifying the original
        lc_kwargs = kwargs.copy()

        # LangChain uses different parameter names in some cases
        mapping = {
            "max_tokens": "max_tokens",  # Same in most cases
            "temperature": "temperature",  # Same in most cases
            "top_p": "top_p",  # Same in most cases
            "frequency_penalty": "frequency_penalty",  # OpenAI-specific
            "presence_penalty": "presence_penalty",  # OpenAI-specific
        }

        # Map standard kwargs to LangChain kwargs
        for standard_name, lc_name in mapping.items():
            if standard_name in lc_kwargs:
                # Only add if the model supports this parameter
                lc_kwargs[lc_name] = lc_kwargs.pop(standard_name)

        # Handle model-specific parameters
        # For OpenAI-specific parameters
        openai_params = ["frequency_penalty", "presence_penalty", "logit_bias"]
        openai_kwargs = {}
        for param in list(lc_kwargs.keys()):
            if param in openai_params and param in lc_kwargs:
                openai_kwargs[param] = lc_kwargs.pop(param)

        # For Anthropic-specific parameters
        anthropic_params = ["system", "max_tokens_to_sample"]
        anthropic_kwargs = {}
        for param in list(lc_kwargs.keys()):
            if param in anthropic_params and param in lc_kwargs:
                anthropic_kwargs[param] = lc_kwargs.pop(param)

        # Special handling for api_version which should go into anthropic_api_kwargs
        if "api_version" in lc_kwargs:
            if "anthropic_api_kwargs" not in lc_kwargs:
                lc_kwargs["anthropic_api_kwargs"] = {}
            lc_kwargs["anthropic_api_kwargs"]["api_version"] = lc_kwargs.pop(
                "api_version"
            )

        # Add model-specific kwargs if needed
        if (
            openai_kwargs
            and hasattr(self, "_llm")
            and "openai" in str(type(self._llm)).lower()
        ):
            if "model_kwargs" not in lc_kwargs:
                lc_kwargs["model_kwargs"] = {}
            lc_kwargs["model_kwargs"].update(openai_kwargs)

        if (
            anthropic_kwargs
            and hasattr(self, "_llm")
            and "anthropic" in str(type(self._llm)).lower()
        ):
            if "anthropic_api_kwargs" not in lc_kwargs:
                lc_kwargs["anthropic_api_kwargs"] = {}
            lc_kwargs["anthropic_api_kwargs"].update(anthropic_kwargs)

        return lc_kwargs

    def chat_sync(
        self, messages: List[Union[Dict[str, Any], BaseMessage]], **kwargs: Any
    ) -> str:
        """
        Synchronous wrapper for chat.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters

        Returns:
            Assistant reply
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.chat(messages, **kwargs))

    def generate_sync(self, prompt: str, **kwargs: Any) -> str:
        """
        Synchronous wrapper for generate.

        Args:
            prompt: The raw prompt string
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.generate(prompt, **kwargs))

    def embed_sync(self, text: str, **kwargs: Any) -> List[float]:
        """
        Synchronous wrapper for embed.

        Args:
            text: Text to embed
            **kwargs: Additional parameters

        Returns:
            List of floats (vector)
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.embed(text, **kwargs))


# Keep a simplified version of the abstract base for backward compatibility
class ModelProvider(ABC):
    """Abstract interface for all LLM providers (local or API)."""

    def __init__(self, cfg: ProviderCfg) -> None:
        """
        Initialize the provider with configuration.

        Args:
            cfg: Provider configuration
        """
        self.cfg = cfg

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Simple text-generation call."""
        ...

    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        """Chat-style call with message dictionaries."""
        ...

    @abstractmethod
    async def embed(self, text: str, **kwargs: Any) -> List[float]:
        """Embedding call."""
        ...

    @abstractmethod
    async def get_model_info(self, **kwargs: Any) -> Dict[str, Any]:
        """Get model info."""
        ...

    def generate_sync(self, prompt: str, **kwargs: Any) -> str:
        """Synchronous wrapper for generate."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.generate(prompt, **kwargs))

    def chat_sync(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        """Synchronous wrapper for chat."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.chat(messages, **kwargs))

    def embed_sync(self, text: str, **kwargs: Any) -> List[float]:
        """Synchronous wrapper for embed."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.embed(text, **kwargs))
