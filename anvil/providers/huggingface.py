import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:
    logger.debug(
        'Transformers not installed. Install with: poetry install --extras "transformers"'
    )

from anvil.config_loader import ProviderCfg

from .base import ModelProvider


class HuggingFaceProvider(ModelProvider):
    """
    Wraps HuggingFace Transformers into the unified ModelProvider interface.
    """

    def __init__(self, cfg: ProviderCfg):
        """
        Initialize the HuggingFace provider with configuration.

        Args:
            cfg: Provider configuration from config_loader
        """
        super().__init__(cfg)
        self.cfg = cfg
        self.model_name = cfg.model_name
        self.device = (cfg.device or "cpu").lower()

        # Configuration registered; model will be loaded lazily on first use
        logger.debug(
            "Registered HuggingFace provider: %s (device=%s)",
            self.model_name,
            self.device,
        )

        # Lazy initialization of the model - we'll load it when it's first used
        self._model = None
        self._tokenizer = None
        self._generation_pipeline = None
        self._embedding_pipeline = None

    def _resolve_device(self):
        """Resolve a valid torch.device from config, with fallbacks."""
        try:
            if self.device in ("auto", "auto_device"):
                if torch.cuda.is_available():
                    return torch.device("cuda")
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return torch.device("mps")
                return torch.device("cpu")
            if self.device in ("cuda", "gpu"):
                if torch.cuda.is_available():
                    return torch.device("cuda")
                else:
                    logger.debug("CUDA not available, falling back to CPU")
                    return torch.device("cpu")
            if self.device == "mps":
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return torch.device("mps")
                else:
                    logger.debug("MPS not available, falling back to CPU")
                    return torch.device("cpu")
        except Exception:
            pass
        return torch.device("cpu")

    def _ensure_model_loaded(self):
        """Ensure the model is loaded."""
        if self._model is None:
            try:
                target_device = self._resolve_device()
                # Load tokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)

                # Load model (avoid device_map to prevent requiring accelerate)
                self._model = AutoModelForCausalLM.from_pretrained(self.model_name)
                # Move model to resolved device
                try:
                    self._model.to(target_device)
                except Exception as e:
                    logger.warning(
                        "Failed to move model to %s: %s. Using CPU.", target_device, e
                    )
                    self._model.to(torch.device("cpu"))
                self._model.eval()

                # Create text generation pipeline
                self._generation_pipeline = pipeline(
                    "text-generation",
                    model=self._model,
                    tokenizer=self._tokenizer,
                )

                logger.info("HuggingFace model %s loaded successfully", self.model_name)
            except Exception as e:
                logger.error(
                    "Error loading HuggingFace model %s: %s", self.model_name, e
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
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._generation_pipeline(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                num_return_sequences=1,
            ),
        )

        # Extract and return generated text
        generated_text = result[0]["generated_text"]

        # Remove the prompt from the beginning if it's included
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt) :].strip()

        return generated_text

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Chat-style call with a list of message dictionaries.

        Args:
            messages: List of message dicts, e.g. [{"role":"user","content":"..."}]
            **kwargs: Additional parameters for the API call

        Returns:
            Assistant's reply as text
        """
        # Convert chat messages to a single prompt
        prompt = self._format_chat_messages(messages)

        # Use generate to get the response
        return await self.generate(prompt, **kwargs)

    def _format_chat_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format chat messages into a prompt string that the model can understand.

        Args:
            messages: List of message dictionaries

        Returns:
            Formatted prompt string
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                formatted.append(f"<|system|>\n{content}\n<|endoftext|>")
            elif role == "user":
                formatted.append(f"<|user|>\n{content}\n<|endoftext|>")
            elif role == "assistant":
                formatted.append(f"<|assistant|>\n{content}\n<|endoftext|>")

        # Add an empty assistant message at the end to prompt for completion
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
        # Lazy load the embedding model if needed
        if self._embedding_pipeline is None:
            try:
                # Create a feature extraction pipeline for embeddings
                self._embedding_pipeline = pipeline(
                    "feature-extraction",
                    model=self._model or self.model_name,
                    tokenizer=self._tokenizer,
                )
            except Exception as e:
                logger.error("Error creating embedding pipeline: %s", e)
                # Return a placeholder embedding if the model doesn't support it
                return [0.0] * 10

        # Run in executor to avoid blocking
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._embedding_pipeline(text)
        )

        # Average the token embeddings to get a single vector
        import numpy as np

        embedding = np.mean(result[0], axis=0).tolist()

        return embedding

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
            "model": self.model_name,
            "provider": "huggingface",
            "device": self.device,
            "capabilities": ["text", "chat", "embeddings"],
        }
