import asyncio
import ctypes
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from llama_cpp import Llama, llama_log_callback, llama_log_set

from anvil.config_loader import ProviderCfg

from .base import ModelProvider


def _llama_log_sink(level: int, text: bytes, user_data: ctypes.c_void_p) -> None:
    try:
        msg = text.decode("utf-8", errors="ignore").rstrip("\n")
    except Exception:
        msg = str(text)
    if not msg:
        return
    logger.debug("llama.cpp: %s", msg)


_LLAMA_LOG_CALLBACK = llama_log_callback(_llama_log_sink)


class LlamaCppProvider(ModelProvider):
    """
    Wraps llama-cpp-python into the unified ModelProvider interface.
    """

    _llama_logging_configured = False

    def __init__(self, cfg: ProviderCfg):
        """
        Initialize the llama-cpp provider with configuration.

        Args:
            cfg: Provider configuration from config_loader
        """
        super().__init__(cfg)
        self.cfg = cfg
        if not cfg.model_path:
            raise ValueError("llama-cpp provider requires `model_path` in config")
        self.model_path = cfg.model_path

        # Configuration registered; model will be loaded lazily on first use
        logger.debug("Registered llama-cpp provider (model_path=%s)", self.model_path)

        # Lazy initialization - we'll load the model when it's first used
        self._model = None

    @classmethod
    def _configure_llama_logging(cls) -> None:
        if cls._llama_logging_configured:
            return

        # By default, route llama.cpp logs to Python debug logging to keep CLI output clean.
        # Opt-out by setting `FORGE_LLAMA_CPP_VERBOSE=1` to keep llama.cpp stderr logging.
        if os.getenv("FORGE_LLAMA_CPP_VERBOSE", "0") == "1":
            cls._llama_logging_configured = True
            return

        llama_log_set(_LLAMA_LOG_CALLBACK, ctypes.c_void_p())
        cls._llama_logging_configured = True

    def _init_kwargs(self) -> Dict[str, Any]:
        """
        Build kwargs for `llama_cpp.Llama(...)`.

        Uses environment variables for local tuning without changing config schema:
        - `FORGE_LLAMA_CPP_N_CTX` (default: 2048)
        - `FORGE_LLAMA_CPP_N_BATCH` (default: 512)
        - `FORGE_LLAMA_CPP_N_GPU_LAYERS` (default: 0)
        - `FORGE_LLAMA_CPP_CHAT_FORMAT` (optional)
        """
        kwargs: Dict[str, Any] = {
            "n_ctx": int(os.getenv("FORGE_LLAMA_CPP_N_CTX", "2048")),
            "n_batch": int(os.getenv("FORGE_LLAMA_CPP_N_BATCH", "512")),
            "n_gpu_layers": int(os.getenv("FORGE_LLAMA_CPP_N_GPU_LAYERS", "0")),
            "verbose": os.getenv("FORGE_LLAMA_CPP_VERBOSE", "0") == "1",
        }
        chat_format = os.getenv("FORGE_LLAMA_CPP_CHAT_FORMAT")
        if chat_format:
            kwargs["chat_format"] = chat_format
        return kwargs

    def _ensure_model_loaded(self):
        """Ensure the model is loaded."""
        if self._model is None:
            try:
                if not os.path.exists(self.model_path):
                    raise FileNotFoundError(f"Model file not found: {self.model_path}")

                self._configure_llama_logging()

                # Load the model
                self._model = Llama(
                    model_path=self.model_path,
                    **self._init_kwargs(),
                )

                logger.info(
                    "LlamaCpp model loaded successfully from %s", self.model_path
                )
            except Exception as e:
                logger.error(
                    "Error loading LlamaCpp model from %s: %s", self.model_path, e
                )
                raise

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Simple text-generation call.

        Args:
            prompt: The raw prompt string
            **kwargs: Additional parameters for the API call

        Returns:
            Generated text response
        """
        # Ensure model is loaded
        self._ensure_model_loaded()

        # Set defaults
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)

        # Run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._model(
                prompt, max_tokens=max_tokens, temperature=temperature, echo=False
            ),
        )

        # Extract and return generated text
        return result["choices"][0]["text"].strip()

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Chat-style call with a list of message dictionaries.

        Args:
            messages: List of message dicts, e.g. [{"role":"user","content":"..."}]
            **kwargs: Additional parameters for the API call

        Returns:
            Assistant's reply as text
        """
        # Prefer llama.cpp's chat API when available (uses model's chat format).
        self._ensure_model_loaded()
        if hasattr(self._model, "create_chat_completion"):
            max_tokens = kwargs.get("max_tokens", 512)
            temperature = kwargs.get("temperature", 0.7)
            top_p = kwargs.get("top_p")
            top_k = kwargs.get("top_k")
            stop = kwargs.get("stop")

            payload: Dict[str, Any] = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if top_p is not None:
                payload["top_p"] = top_p
            if top_k is not None:
                payload["top_k"] = top_k
            if stop is not None:
                payload["stop"] = stop

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None, lambda: self._model.create_chat_completion(**payload)
            )

            try:
                return resp["choices"][0]["message"]["content"].strip()
            except Exception:
                return str(resp)

        # Fallback: format messages to a single prompt and use completion-style API.
        prompt = self._format_chat_messages(messages)
        return await self.generate(prompt, **kwargs)

    def _format_chat_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format chat messages into a prompt string for llama.cpp.

        Args:
            messages: List of message dictionaries

        Returns:
            Formatted prompt string
        """
        formatted = []

        # Add a system message if not present
        has_system = any(msg.get("role") == "system" for msg in messages)
        if not has_system:
            formatted.append("<|system|>\nYou are a helpful AI assistant.\n")

        # Add the messages
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                formatted.append(f"<|system|>\n{content}")
            elif role == "user":
                formatted.append(f"<|user|>\n{content}")
            elif role == "assistant":
                formatted.append(f"<|assistant|>\n{content}")

        # Add the assistant prompt
        formatted.append("<|assistant|>")

        return "\n".join(formatted)

    async def embed(self, text: str, **kwargs) -> List[float]:
        """
        Generate embeddings for input text.

        Args:
            text: Input text to embed
            **kwargs: Additional parameters for the API call

        Returns:
            List of floats representing the embedding vector
        """
        # llama-cpp doesn't have built-in embeddings, so return a placeholder
        logger.warning("LlamaCpp does not provide embeddings. Returning placeholder.")
        return [0.0] * 10  # Return a placeholder embedding

    async def get_model_info(self, **kwargs) -> Dict[str, Any]:
        """
        Get model information.

        Args:
            **kwargs: Additional parameters

        Returns:
            Dictionary with model information
        """
        # Basic model info
        return {
            "model_path": self.model_path,
            "provider": "llama_cpp",
            "capabilities": ["text", "chat"],
        }
