"""
Advanced Multi-Level Cache Manager for RuleIQ

This module implements a comprehensive caching system with:
- L1 in-memory LRU cache for hot data
- L2 Redis distributed cache for shared data
- Intelligent cache invalidation policies
- Performance monitoring and metrics
- Fallback mechanisms for Redis unavailability
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable
from collections import OrderedDict
import hashlib
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
    RedisError
)


logger = logging.getLogger(__name__)

# Security Constants
CACHE_KEY_HASH_LENGTH = 32  # SHA-256 truncated for cache keys
API_CACHE_KEY_LENGTH = 32
COMPUTE_CACHE_KEY_LENGTH = 32

# TTL Constants
DEFAULT_API_TTL = 300  # Default TTL for API responses
DEFAULT_COMPUTE_TTL = 3600  # Default TTL for computations
DEFAULT_EXTERNAL_API_TTL = 600  # Default TTL for external API calls
DEFAULT_STARTUP_TTL = 3600  # Default TTL for startup cache
DEFAULT_BACKGROUND_TTL = 1800  # Default TTL for background cache
DEFAULT_DB_QUERY_TTL = 300  # Default TTL for database queries

# Performance Constants
CACHE_MISS_PENALTY = 0.1  # Wait time penalty for cache misses
RETRY_BACKOFF_BASE = 2  # Exponential backoff base for retries
RETRY_JITTER_FACTOR = 0.1  # Jitter factor for retry logic
BACKGROUND_WARMING_INTERVAL = 300  # Background warming interval

# Compatibility Constants
ENABLE_CACHE_HASH_COMPAT = True  # Enable dual-read for MD5->SHA256 migration
LEGACY_MD5_HASH_LENGTH = 32  # Length of legacy MD5 hash


class CacheMetrics:
    """Cache performance metrics collector"""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.response_times: List[float] = []
        self.errors = 0

    def record_hit(self):
        """Record cache hit"""
        self.hits += 1

    def record_miss(self):
        """Record cache miss"""
        self.misses += 1

    def record_set(self):
        """Record cache set operation"""
        self.sets += 1

    def record_delete(self):
        """Record cache delete operation"""
        self.deletes += 1

    def record_response_time(self, response_time: float):
        """Record response time"""
        self.response_times.append(response_time)

    def record_error(self):
        """Record cache error"""
        self.errors += 1

    def get_hit_rate(self) -> float:
        """Calculate hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_avg_response_time(self) -> float:
        """Calculate average response time"""
        if self.response_times:
            return sum(self.response_times) / len(self.response_times)
        return 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "hit_rate": self.get_hit_rate(),
            "avg_response_time": self.get_avg_response_time(),
            "errors": self.errors,
            "total_requests": self.hits + self.misses
        }


class LRUCache:
    """Thread-safe LRU cache implementation"""

    def __init__(self, max_items: int = 1000, max_memory_mb: int = 50) -> None:
        self.max_items = max_items
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.expirations: Dict[str, float] = {}
        self.memory_usage = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self._lock:
            # Check expiration
            if key in self.expirations and time.time() > self.expirations[key]:
                await self._delete_no_lock(key)
                return None

            if key in self.cache:
                # Move to end (most recently used)
                value = self.cache[key]
                self.cache.move_to_end(key)
                return value
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Set value in cache"""
        async with self._lock:
            # Remove if exists
            if key in self.cache:
                await self._delete_no_lock(key)

            # Check memory limits
            value_size = self._estimate_size(value)
            while (
                self.memory_usage + value_size > self.max_memory_bytes
                and self.cache
            ):
                # Remove least recently used
                oldest_key, _ = self.cache.popitem(last=False)
                if oldest_key in self.expirations:
                    del self.expirations[oldest_key]

            # Check item limits
            while len(self.cache) >= self.max_items and self.cache:
                oldest_key, _ = self.cache.popitem(last=False)
                if oldest_key in self.expirations:
                    del self.expirations[oldest_key]

            # Add new item
            self.cache[key] = value
            self.memory_usage += value_size

            if ttl:
                self.expirations[key] = time.time() + ttl

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        async with self._lock:
            return await self._delete_no_lock(key)

    async def _delete_no_lock(self, key: str) -> bool:
        """Delete without acquiring lock"""
        if key in self.cache:
            value = self.cache[key]
            del self.cache[key]
            self.memory_usage -= self._estimate_size(value)
            if key in self.expirations:
                del self.expirations[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self.cache.clear()
            self.expirations.clear()
            self.memory_usage = 0

    def _estimate_size(self, obj: Any) -> int:
        """Estimate memory usage of object"""
        try:
            # Rough estimation based on JSON serialization
            return len(json.dumps(obj, default=str).encode('utf-8'))
        except (TypeError, ValueError, OverflowError) as e:
            # Fallback for non-serializable objects
            logger.debug("Size estimation failed: %s", e)
            return 1024  # 1KB estimate

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "items": len(self.cache),
            "memory_usage_bytes": self.memory_usage,
            "memory_usage_mb": self.memory_usage / (1024 * 1024),
            "max_items": self.max_items,
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "hit_rate": 0.0  # Would need to track hits/misses separately
        }


class CacheManager:
    """
    Advanced multi-level cache manager with L1 in-memory and L2 Redis caching.

    Features:
    - Multi-level caching (L1 fast in-memory, L2 distributed Redis)
    - Intelligent cache invalidation policies
    - Performance monitoring and metrics
    - Fallback mechanisms for Redis unavailability
    - Cache warming strategies
    - TTL management and expiration
    """

    def __init__(
        self,
        enable_caching: bool = True,
        l1_max_items: int = 10000,
        l1_max_memory_mb: int = 100,
        ttl_config: Optional[Dict[str, int]] = None,
        metrics: Optional[CacheMetrics] = None
    ) -> None:
        self.enable_caching = enable_caching
        self.ttl_config = ttl_config or {}
        self.metrics = metrics or CacheMetrics()

        # L1 Cache (in-memory LRU)
        self._l1_cache = LRUCache(
            max_items=l1_max_items,
            max_memory_mb=l1_max_memory_mb
        )

        # L2 Cache (Redis)
        self._redis = None
        self._redis_available = False

        # Initialization flag
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the cache manager"""
        if not self.enable_caching:
            logger.info("Caching disabled")
            self._initialized = True
            return

        # Initialize L1 cache
        await self._l1_cache.clear()

        # Initialize L2 cache (Redis)
        try:
            from database.redis_client import get_redis_client
            self._redis = await get_redis_client()
            self._redis_available = True
            logger.info("Redis cache initialized successfully")
        except (
            ImportError, RedisConnectionError, RedisTimeoutError, OSError
        ) as e:
            logger.warning(
                "Redis unavailable, falling back to L1 only: %s", e
            )
            self._redis_available = False

        self._initialized = True
        logger.info("Cache manager initialized")

    async def close(self) -> None:
        """Close cache connections"""
        if self._redis and hasattr(self._redis, 'close'):
            await self._redis.close()
        self._initialized = False

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with L1 -> L2 fallback.

        Returns None if key not found or caching disabled.
        """
        if not self.enable_caching or not self._initialized:
            return None

        start_time = time.time()

        try:
            # Try L1 cache first
            value = await self._l1_cache.get(key)
            if value is not None:
                self.metrics.record_hit()
                self.metrics.record_response_time(time.time() - start_time)
                return value

            # Try L2 cache if available
            if self._redis_available and self._redis:
                try:
                    serialized = await self._redis.get(key)
                    if serialized:
                        value = self._deserialize(serialized)
                        if value is not None:
                            # Promote to L1
                            await self._l1_cache.set(key, value)
                            self.metrics.record_hit()
                            self.metrics.record_response_time(
                                time.time() - start_time
                            )
                            return value
                except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                    logger.warning(
                        "Redis connection error for key %s: %s", key, e
                    )
                    self.metrics.record_error()
                except ValueError as e:
                    logger.warning(
                        "Redis serialization error for key %s: %s", key, e
                    )
                    self.metrics.record_error()
                except RedisError:
                    logger.exception("Redis get error for key %s", key)
                    self.metrics.record_error()
                    # Re-raise in debug mode for development
                    if logger.isEnabledFor(logging.DEBUG):
                        raise

            # Cache miss - no further fallback needed in base get method
            # Dual-read fallback is handled in cache_api_response
            # and cache_service_computation

            # Cache miss
            self.metrics.record_miss()
            self.metrics.record_response_time(time.time() - start_time)
            return None

        except (TypeError, ValueError, AttributeError):
            logger.exception("Cache get error for key %s", key)
            self.metrics.record_error()
            self.metrics.record_response_time(time.time() - start_time)
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.

        Returns True if successful, False otherwise.
        """
        if not self.enable_caching or not self._initialized:
            return False

        try:
            # Set in L1 cache
            await self._l1_cache.set(key, value, ttl)

            # Set in L2 cache if available
            if self._redis_available and self._redis:
                try:
                    serialized = self._serialize(value)
                    await self._redis.set(key, serialized, ex=ttl)
                except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                    logger.warning(
                        "Redis connection error for key %s: %s", key, e
                    )
                    self.metrics.record_error()
                except ValueError as e:
                    logger.warning(
                        "Redis serialization error for key %s: %s", key, e
                    )
                    self.metrics.record_error()
                except RedisError:
                    logger.exception("Redis set error for key %s", key)
                    self.metrics.record_error()
                    # Re-raise in debug mode for development
                    if logger.isEnabledFor(logging.DEBUG):
                        raise

            self.metrics.record_set()
            return True

        except (TypeError, ValueError, AttributeError):
            logger.exception("Cache set error for key %s", key)
            self.metrics.record_error()
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Returns True if key was deleted, False otherwise.
        """
        if not self.enable_caching or not self._initialized:
            return False

        try:
            deleted = False

            # Delete from L1
            if await self._l1_cache.delete(key):
                deleted = True

            # Delete from L2 if available
            if self._redis_available and self._redis:
                try:
                    if await self._redis.delete(key):
                        deleted = True
                except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                    logger.warning(
                        "Redis connection error for key %s: %s", key, e
                    )
                    self.metrics.record_error()
                except ValueError as e:
                    logger.warning(
                        "Redis serialization error for key %s: %s", key, e
                    )
                    self.metrics.record_error()
                except RedisError:
                    logger.exception("Redis delete error for key %s", key)
                    self.metrics.record_error()
                    # Re-raise in debug mode for development
                    if logger.isEnabledFor(logging.DEBUG):
                        raise

            if deleted:
                self.metrics.record_delete()

            return deleted

        except (TypeError, ValueError, AttributeError):
            logger.exception("Cache delete error for key %s", key)
            self.metrics.record_error()
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate keys matching pattern.

        Returns number of keys invalidated.
        """
        if not self.enable_caching or not self._initialized:
            return 0

        try:
            invalidated = 0

            # Clear L1 cache
            # (simplified - in production would need pattern matching)
            await self._l1_cache.clear()

            # Invalidate L2 patterns if available
            if self._redis_available and self._redis:
                try:
                    # Get keys matching pattern
                    if hasattr(self._redis, 'keys'):
                        keys = await self._redis.keys(pattern)
                        if keys:
                            await self._redis.delete(*keys)
                            invalidated += len(keys)
                except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                    logger.warning(
                        "Redis connection error for pattern %s: %s",
                        pattern, e
                    )
                    self.metrics.record_error()
                except ValueError as e:
                    logger.warning(
                        "Redis serialization error for pattern %s: %s",
                        pattern, e
                    )
                    self.metrics.record_error()
                except RedisError:
                    logger.exception(
                        "Redis pattern invalidation error for pattern %s",
                        pattern
                    )
                    self.metrics.record_error()
                    # Re-raise in debug mode for development
                    if logger.isEnabledFor(logging.DEBUG):
                        raise

            return invalidated

        except (TypeError, ValueError, AttributeError):
            logger.exception(
                "Pattern invalidation error for %s", pattern
            )
            self.metrics.record_error()
            return 0

    async def invalidate(self, key: str) -> bool:
        """
        Invalidate specific key.

        Returns True if invalidated, False otherwise.
        """
        return await self.delete(key)

    def _serialize(self, value: Any) -> str:
        """Serialize value for storage"""
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            logger.exception("Serialization error")
            raise

    def _deserialize(self, value: str) -> Any:
        """Deserialize value from storage"""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.exception("Deserialization error")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        l1_stats = self._l1_cache.get_stats()

        return {
            "enabled": self.enable_caching,
            "initialized": self._initialized,
            "redis_available": self._redis_available,
            "l1_cache": l1_stats,
            "metrics": self.metrics.get_stats()
        }

    # Integration methods for different layers

    async def get_or_set_db_query(
        self,
        query_key: str,
        query_func: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None
    ) -> Any:
        """Get database query result from cache or execute query"""
        # Try cache first
        cached = await self.get(query_key)
        if cached is not None:
            return cached

        # Execute query
        result = await query_func()

        # Cache result
        if result is not None:
            actual_ttl = ttl or self.ttl_config.get(
                'db_query', DEFAULT_DB_QUERY_TTL
            )
            await self.set(query_key, result, actual_ttl)

        return result

    async def cache_api_response(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any],
        api_func: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None
    ) -> Any:
        """Cache API response"""
        # Create cache key from method, endpoint, and params
        key_data = {"method": method, "endpoint": endpoint, "params": params}
        # Use SHA-256 for secure cache key generation
        # (truncated to maintain key length)
        # Generate SHA-256 hash for cache key
        key_hash = hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:API_CACHE_KEY_LENGTH]
        cache_key = f"api:{key_hash}"

        # Try cache first
        cached = await self.get(cache_key)
        if cached is not None:
            return cached

        # Dual-read fallback for legacy MD5 keys during migration
        # This ensures no cache hit regression during the hash transition
        # TODO: Remove this dual-read logic after migration is complete
        if ENABLE_CACHE_HASH_COMPAT:
            try:
                # Compute legacy MD5 key using same key_data structure
                # noqa: S324 - MD5 needed for backward compatibility
                legacy_hash = hashlib.md5(
                    json.dumps(key_data, sort_keys=True).encode(),
                    usedforsecurity=False,
                ).hexdigest()[:LEGACY_MD5_HASH_LENGTH]
                legacy_key = f"api:{legacy_hash}"

                # Try to get value from legacy key
                # (direct Redis fetch to avoid recursion)
                legacy_value = None
                if self._redis_available and self._redis:
                    try:
                        serialized = await self._redis.get(legacy_key)
                        if serialized:
                            legacy_value = self._deserialize(serialized)
                    except (
                        RedisConnectionError,
                        RedisTimeoutError,
                        RedisError,
                        OSError,
                        ValueError
                    ) as e:
                        logger.debug(
                            "Legacy MD5 fetch failed for %s: %s",
                            legacy_key, e
                        )
                else:
                    # Fallback to L1 cache
                    legacy_value = await self._l1_cache.get(legacy_key)
                if legacy_value is not None:
                    logger.debug(
                        "Found value in legacy MD5 key %s, "
                        "promoting to SHA-256 key %s",
                        legacy_key, cache_key
                    )
                    # Promote to new SHA-256 key
                    actual_ttl = ttl or self.ttl_config.get(
                        'api_response', DEFAULT_API_TTL
                    )
                    await self.set(cache_key, legacy_value, actual_ttl)
                    # Note: set() already records the metric internally
                    return legacy_value
            except (
                RedisConnectionError, RedisTimeoutError,
                RedisError, OSError, ValueError
            ) as e:
                logger.debug("Legacy key check failed: %s", e)

        # Execute API call
        result = await api_func()

        # Cache result
        if result is not None:
            actual_ttl = ttl or self.ttl_config.get(
                'api_response', DEFAULT_API_TTL
            )
            await self.set(cache_key, result, actual_ttl)

        return result

    async def cache_service_computation(
        self,
        computation_key: str,
        params: Dict[str, Any],
        compute_func: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None
    ) -> Any:
        """Cache expensive service computation"""
        # Create cache key from computation key and params
        key_data = {"key": computation_key, "params": params}
        # Use SHA-256 for secure cache key generation
        # (truncated to maintain key length)
        # Generate SHA-256 hash for cache key
        key_hash = hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:COMPUTE_CACHE_KEY_LENGTH]
        cache_key = f"compute:{key_hash}"

        # Try cache first
        cached = await self.get(cache_key)
        if cached is not None:
            return cached

        # Dual-read fallback for legacy MD5 keys during migration
        # This ensures no cache hit regression during the hash transition
        # TODO: Remove this dual-read logic after migration is complete
        if ENABLE_CACHE_HASH_COMPAT:
            try:
                # Compute legacy MD5 key using same key_data structure
                # noqa: S324 - MD5 needed for backward compatibility
                legacy_hash = hashlib.md5(
                    json.dumps(key_data, sort_keys=True).encode(),
                    usedforsecurity=False,
                ).hexdigest()[:LEGACY_MD5_HASH_LENGTH]
                legacy_key = f"compute:{legacy_hash}"

                # Try to get value from legacy key
                # (direct Redis fetch to avoid recursion)
                legacy_value = None
                if self._redis_available and self._redis:
                    try:
                        serialized = await self._redis.get(legacy_key)
                        if serialized:
                            legacy_value = self._deserialize(serialized)
                    except (
                        RedisConnectionError,
                        RedisTimeoutError,
                        RedisError,
                        OSError,
                        ValueError
                    ) as e:
                        logger.debug(
                            "Legacy MD5 fetch failed for %s: %s",
                            legacy_key, e
                        )
                else:
                    # Fallback to L1 cache
                    legacy_value = await self._l1_cache.get(legacy_key)
                if legacy_value is not None:
                    logger.debug(
                        "Found value in legacy MD5 key %s, "
                        "promoting to SHA-256 key %s",
                        legacy_key, cache_key
                    )
                    # Promote to new SHA-256 key
                    actual_ttl = ttl or self.ttl_config.get(
                        'computation', DEFAULT_COMPUTE_TTL
                    )
                    await self.set(cache_key, legacy_value, actual_ttl)
                    # Note: set() already records the metric internally
                    return legacy_value
            except (
                RedisConnectionError, RedisTimeoutError,
                RedisError, OSError, ValueError
            ) as e:
                logger.debug("Legacy key check failed: %s", e)

        # Execute computation
        result = await compute_func()

        # Cache result
        if result is not None:
            actual_ttl = ttl or self.ttl_config.get(
                'computation', DEFAULT_COMPUTE_TTL
            )
            await self.set(cache_key, result, actual_ttl)

        return result

    async def cache_external_api(
        self,
        service: str,
        endpoint: str,
        api_func: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None
    ) -> Any:
        """Cache external API calls"""
        cache_key = f"external:{service}:{endpoint}"

        # Try cache first
        cached = await self.get(cache_key)
        if cached is not None:
            return cached

        # Execute API call
        result = await api_func()

        # Cache result
        if result is not None:
            actual_ttl = ttl or self.ttl_config.get(
                'external_api', DEFAULT_EXTERNAL_API_TTL
            )
            await self.set(cache_key, result, actual_ttl)

        return result

    async def invalidate_db_entity(
        self, entity_type: str, entity_id: str
    ) -> None:
        """Invalidate cache for database entity"""
        pattern = f"db:{entity_type}:{entity_id}:*"
        await self.invalidate_pattern(pattern)

    async def invalidate_api_caches(
        self, resource: str, method: Optional[str] = None
    ) -> None:
        """Invalidate API caches for resource"""
        if method in ['POST', 'PUT', 'DELETE']:
            # Invalidate list caches
            pattern = f"api:*{resource}*list*"
            await self.invalidate_pattern(pattern)
            # Invalidate individual resource caches
            pattern = f"api:*{resource}*"
            await self.invalidate_pattern(pattern)

    # Cache warming methods

    async def warm_startup_cache(
        self,
        data_source: Dict[str, Any],
        min_priority: int = 0
    ) -> int:
        """Warm cache with startup data based on priority"""
        warmed = 0

        for key, data in data_source.items():
            if isinstance(data, dict) and 'priority' in data:
                if data['priority'] >= min_priority:
                    ttl = self.ttl_config.get('startup', DEFAULT_STARTUP_TTL)
                    await self.set(key, data['data'], ttl=ttl)
                    warmed += 1
            else:
                # No priority specified, include by default
                ttl = self.ttl_config.get('startup', DEFAULT_STARTUP_TTL)
                await self.set(key, data, ttl=ttl)
                warmed += 1

        logger.info("Warmed %d cache entries on startup", warmed)
        return warmed

    async def background_warming(
        self,
        data_source: Callable[[], Dict[str, Any]],
        interval: int = BACKGROUND_WARMING_INTERVAL
    ) -> None:
        """Background cache warming task"""
        while True:
            try:
                data = data_source()
                for key, value in data.items():
                    # Only set if not already cached
                    existing = await self.get(key)
                    if existing is None:
                        ttl = self.ttl_config.get(
                            'background', DEFAULT_BACKGROUND_TTL
                        )
                        await self.set(key, value, ttl=ttl)
                await asyncio.sleep(interval)
            except (TypeError, ValueError, AttributeError):
                logger.exception("Background warming error")
                await asyncio.sleep(interval)

    # Utility methods

    def build_key(self, *parts: str) -> str:
        """Build structured cache key"""
        return f"cache:{':'.join(str(p) for p in parts)}"

    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute and cache"""
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute
        result = await compute_func()

        # Cache result
        if result is not None:
            await self.set(key, result, ttl)

        return result
