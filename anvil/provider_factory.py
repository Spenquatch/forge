# anvil/provider_factory.py
"""
Advanced ProviderFactory with caching, performance monitoring, and lifecycle management.

Follows industry best practices:
- Factory pattern for object creation
- LRU caching with TTL
- Thread-safe operations
- Performance metrics collection
- Resource management
- Dependency injection support
"""

import logging
import threading
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Type, Union, cast

from anvil.config_loader import ProviderCfg
from anvil.providers.base import LangChainProvider, ModelProvider

logger = logging.getLogger(__name__)


@dataclass
class ProviderCacheEntry:
    """Cache entry for provider instances with metadata."""

    provider: Union[ModelProvider, LangChainProvider]
    created_at: float
    last_accessed: float
    access_count: int = 0
    model_name: str = ""
    config_hash: str = ""

    def touch(self):
        """Update last accessed time and increment counter."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class ProviderStats:
    """Performance statistics for a provider."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    last_used: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    def record_request(self, duration: float, success: bool = True):
        """Record a request with timing and success status."""
        self.total_requests += 1
        self.total_duration += duration
        self.last_used = time.time()

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.avg_duration = (
            self.total_duration / self.total_requests
            if self.total_requests > 0
            else 0.0
        )

    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_misses += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100.0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total_cache_requests = self.cache_hits + self.cache_misses
        if total_cache_requests == 0:
            return 0.0
        return (self.cache_hits / total_cache_requests) * 100.0


class ProviderFactory:
    """
    Advanced factory for creating and managing provider instances.

    Features:
    - LRU caching with TTL
    - Performance monitoring
    - Thread-safe operations
    - Resource lifecycle management
    - Hot-swapping support
    - Memory pressure handling
    """

    def __init__(
        self,
        max_cache_size: int = 50,
        default_ttl: int = 3600,  # 1 hour
        enable_stats: bool = True,
    ):
        """
        Initialize the provider factory.

        Args:
            max_cache_size: Maximum number of cached providers
            default_ttl: Default time-to-live in seconds
            enable_stats: Whether to collect performance statistics
        """
        self.max_cache_size = max_cache_size
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats

        # Thread-safe cache using OrderedDict for LRU behavior
        self._cache: OrderedDict[str, ProviderCacheEntry] = OrderedDict()
        self._cache_lock = threading.RLock()

        # Performance statistics
        self._stats: Dict[str, ProviderStats] = {}
        self._stats_lock = threading.RLock()

        # Configuration tracking for hot-reload detection
        self._config_hashes: Dict[str, str] = {}

        # Weak references for cleanup
        self._provider_refs: List[weakref.ref] = []

        logger.info(
            f"ProviderFactory initialized: cache_size={max_cache_size}, ttl={default_ttl}s"
        )

    def get_or_create_provider(
        self,
        provider_name: str,
        config: ProviderCfg,
        model_name: Optional[str] = None,
        force_recreate: bool = False,
    ) -> Optional[Union[ModelProvider, LangChainProvider]]:
        """
        Get or create a provider instance with caching.

        Args:
            provider_name: Name of the provider
            config: Provider configuration
            model_name: Optional specific model name
            force_recreate: Force recreation even if cached

        Returns:
            Provider instance or None if creation failed
        """
        cache_key = self._generate_cache_key(provider_name, config, model_name)
        config_hash = self._hash_config(config, model_name)

        # Check cache first (unless forced recreation)
        if not force_recreate:
            cached_provider = self._get_from_cache(cache_key, config_hash)
            if cached_provider:
                self._record_cache_hit(provider_name)
                return cached_provider

        # Cache miss - create new provider
        self._record_cache_miss(provider_name)

        start_time = time.time()
        success = False

        try:
            provider = self._create_provider(config, model_name)
            if provider:
                # Cache the new provider
                self._add_to_cache(
                    cache_key,
                    provider,
                    config_hash,
                    model_name or config.model_name or "",
                )
                success = True

                logger.debug(f"Created and cached provider: {provider_name}")
                return provider
            else:
                logger.warning(f"Failed to create provider: {provider_name}")
                return None

        except Exception as e:
            logger.error(f"Error creating provider {provider_name}: {e}", exc_info=True)
            return None

        finally:
            # Record performance stats
            duration = time.time() - start_time
            self._record_request_stats(provider_name, duration, success)

    def invalidate_provider(self, provider_name: str, model_name: Optional[str] = None):
        """Invalidate a specific provider from the cache."""
        with self._cache_lock:
            keys_to_remove = []
            for key in self._cache:
                if key.startswith(f"{provider_name}:"):
                    if model_name is None or model_name in key:
                        keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]
                logger.debug(f"Invalidated cached provider: {key}")

    def get_provider_stats(
        self, provider_name: Optional[str] = None
    ) -> Union[ProviderStats, Dict[str, ProviderStats]]:
        """Get performance statistics for providers."""
        if not self.enable_stats:
            return ProviderStats() if provider_name else {}

        with self._stats_lock:
            if provider_name:
                return self._stats.get(provider_name, ProviderStats())
            else:
                return self._stats.copy()

    def _generate_cache_key(
        self, provider_name: str, config: ProviderCfg, model_name: Optional[str]
    ) -> str:
        """Generate unique cache key for provider configuration."""
        model = model_name or config.model_name or "default"
        config_hash = self._hash_config(config, model_name)[:8]
        return f"{provider_name}:{model}:{config_hash}"

    def _hash_config(self, config: ProviderCfg, model_name: Optional[str]) -> str:
        """Generate hash of configuration for change detection."""
        import hashlib

        config_repr = (
            f"{config.class_path}:{config.type}:{model_name or config.model_name}"
        )
        return hashlib.md5(config_repr.encode()).hexdigest()

    def _get_from_cache(
        self, cache_key: str, config_hash: str
    ) -> Optional[Union[ModelProvider, LangChainProvider]]:
        """Get provider from cache if valid."""
        with self._cache_lock:
            if cache_key in self._cache:
                entry = self._cache[cache_key]

                # Check if configuration changed
                if entry.config_hash != config_hash:
                    del self._cache[cache_key]
                    return None

                # Check TTL
                if time.time() - entry.created_at > self.default_ttl:
                    del self._cache[cache_key]
                    return None

                # Update access info and move to end (LRU behavior)
                entry.touch()
                self._cache.move_to_end(cache_key)
                return entry.provider

            return None

    def _add_to_cache(
        self,
        cache_key: str,
        provider: Union[ModelProvider, LangChainProvider],
        config_hash: str,
        model_name: str,
    ):
        """Add provider to cache."""
        with self._cache_lock:
            # Remove oldest entries if at capacity
            while len(self._cache) >= self.max_cache_size:
                self._cache.popitem(last=False)

            # Create cache entry
            entry = ProviderCacheEntry(
                provider=provider,
                created_at=time.time(),
                last_accessed=time.time(),
                model_name=model_name,
                config_hash=config_hash,
            )

            self._cache[cache_key] = entry

    def _create_provider(
        self, config: ProviderCfg, model_name: Optional[str]
    ) -> Optional[Union[ModelProvider, LangChainProvider]]:
        """Create a new provider instance."""
        try:
            import importlib

            module_path, cls_name = config.class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            provider_cls = getattr(module, cls_name)
            if not isinstance(provider_cls, type):
                return None
            typed_cls = cast(
                Type[Union[ModelProvider, LangChainProvider]], provider_cls
            )
            return typed_cls(config)
        except Exception as e:
            logger.error(f"Failed to create provider from {config.class_path}: {e}")
            return None

    def _record_cache_hit(self, provider_name: str):
        """Record cache hit statistics."""
        if not self.enable_stats:
            return

        with self._stats_lock:
            if provider_name not in self._stats:
                self._stats[provider_name] = ProviderStats()
            self._stats[provider_name].record_cache_hit()

    def _record_cache_miss(self, provider_name: str):
        """Record cache miss statistics."""
        if not self.enable_stats:
            return

        with self._stats_lock:
            if provider_name not in self._stats:
                self._stats[provider_name] = ProviderStats()
            self._stats[provider_name].record_cache_miss()

    def _record_request_stats(self, provider_name: str, duration: float, success: bool):
        """Record request performance statistics."""
        if not self.enable_stats:
            return

        with self._stats_lock:
            if provider_name not in self._stats:
                self._stats[provider_name] = ProviderStats()
            self._stats[provider_name].record_request(duration, success)


# Global factory instance
_factory = ProviderFactory()


def get_provider_factory() -> ProviderFactory:
    """Get the global provider factory instance."""
    return _factory
