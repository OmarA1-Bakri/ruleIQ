"""

Cache Service for ruleIQ

Provides a unified caching interface using Vercel KV or Redis with fallback to in-memory cache.
Supports TTL, automatic serialization/deserialization, and proper error handling.
"""

import json
import logging
from typing import Any, Optional, Dict, Union
from datetime import timedelta
from services.kv_adapter import get_cache, CacheAdapter

logger = logging.getLogger(__name__)


class CacheService:
    """
    Unified cache service with Redis backend and in-memory fallback

    Features:
    - Automatic JSON serialization/deserialization
    - TTL support
    - Graceful fallback to in-memory cache when Redis unavailable
    - Connection pooling and health monitoring
    """

    def __init__(self) -> None:
        self._cache_adapter: Optional[CacheAdapter] = None
        self._cache_available = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._max_memory_items = 1000

    async def _get_cache_adapter(self) -> Optional[CacheAdapter]:
        """Get or create cache adapter with connection testing."""
        if self._cache_available is False:
            return None
        if self._cache_adapter is None:
            try:
                self._cache_adapter = await get_cache()
                # Test connection
                await self._cache_adapter.set("_test", "1", expire=1)
                self._cache_available = True
                logger.info("Cache service connected")
            except Exception as e:
                logger.warning(
                    "Cache unavailable, using in-memory cache fallback: %s" % e,
                )
                self._cache_available = False
                self._cache_adapter = None
                return None
        return self._cache_adapter

    async def set(self, key: str, value: Any, ttl: Optional[Union[int, timedelta]] = None) -> bool:
        """
        Set a value in cache with optional TTL

        Args:
            key: Cache key
            value: Value to cache (automatically serialized to JSON)
            ttl: Time to live in seconds or timedelta

        Returns:
            bool: Success status
        """
        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            cache_adapter = await self._get_cache_adapter()
            if cache_adapter:
                if ttl:
                    await cache_adapter.setex(key, ttl, serialized_value)
                else:
                    await cache_adapter.set(key, serialized_value)
                return True
            import time

            cache_entry = {
                "value": serialized_value,
                "expires_at": time.time() + ttl if ttl else None,
            }
            if len(self._memory_cache) >= self._max_memory_items:
                oldest_keys = list(self._memory_cache.keys())[:100]
                for old_key in oldest_keys:
                    del self._memory_cache[old_key]
            self._memory_cache[key] = cache_entry
            return True
        except Exception as e:
            logger.error("Failed to set cache key %s: %s" % (key, e))
            return False

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        try:
            cache_adapter = await self._get_cache_adapter()
            if cache_adapter:
                value = await cache_adapter.get(key)
                if value:
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
                return None
            import time

            cache_entry = self._memory_cache.get(key)
            if not cache_entry:
                return None
            if cache_entry["expires_at"] and time.time() > cache_entry["expires_at"]:
                del self._memory_cache[key]
                return None
            value = cache_entry["value"]
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error("Failed to get cache key %s: %s" % (key, e))
            return None

    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache

        Args:
            key: Cache key to delete

        Returns:
            bool: Success status
        """
        try:
            success = False
            cache_adapter = await self._get_cache_adapter()
            if cache_adapter:
                result = await cache_adapter.delete(key)
                success = result > 0
            if key in self._memory_cache:
                del self._memory_cache[key]
                success = True
            return success
        except Exception as e:
            logger.error("Failed to delete cache key %s: %s" % (key, e))
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache

        Args:
            key: Cache key

        Returns:
            bool: True if key exists and not expired
        """
        try:
            cache_adapter = await self._get_cache_adapter()
            if cache_adapter:
                return await cache_adapter.exists(key) > 0
            import time

            cache_entry = self._memory_cache.get(key)
            if not cache_entry:
                return False
            if cache_entry["expires_at"] and time.time() > cache_entry["expires_at"]:
                del self._memory_cache[key]
                return False
            return True
        except Exception as e:
            logger.error("Failed to check cache key %s: %s" % (key, e))
            return False

    async def clear(self, pattern: Optional[str] = None) -> bool:
        """
        Clear cache entries matching pattern

        Args:
            pattern: Optional pattern to match keys (e.g., "user:*")
                    If None, clears all cache

        Returns:
            bool: Success status
        """
        try:
            cache_adapter = await self._get_cache_adapter()
            if cache_adapter:
                if pattern:
                    keys = await cache_adapter.keys(pattern)
                    if keys:
                        await cache_adapter.delete(*keys)
                else:
                    await cache_adapter.flushdb()
            if pattern:
                keys_to_delete = [
                    key for key in self._memory_cache if pattern.replace("*", "") in key
                ]
                for key in keys_to_delete:
                    del self._memory_cache[key]
            else:
                self._memory_cache.clear()
            return True
        except Exception as e:
            logger.error("Failed to clear cache with pattern %s: %s" % (pattern, e))
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Get cache service health status

        Returns:
            Dict with health information
        """
        try:
            redis_status = "unavailable"
            cache_adapter = await self._get_cache_adapter()
            if cache_adapter:
                await cache_adapter.ping()
                redis_status = "connected"
            return {
                "redis_status": redis_status,
                "memory_cache_entries": len(self._memory_cache),
                "max_memory_entries": self._max_memory_items,
                "fallback_active": self._redis_available is False,
            }
        except Exception as e:
            logger.error("Failed to get cache health status: %s" % e)
            return {
                "redis_status": "error",
                "memory_cache_entries": len(self._memory_cache),
                "error": str(e),
            }

    async def cleanup_expired(self) -> int:
        """
        Clean up expired entries from memory cache

        Returns:
            int: Number of entries cleaned up
        """
        try:
            import time

            current_time = time.time()
            expired_keys = []
            for key, entry in self._memory_cache.items():
                if entry["expires_at"] and current_time > entry["expires_at"]:
                    expired_keys.append(key)
            for key in expired_keys:
                del self._memory_cache[key]
            if expired_keys:
                logger.debug("Cleaned up %s expired cache entries" % len(expired_keys))
            return len(expired_keys)
        except Exception as e:
            logger.error("Failed to cleanup expired cache entries: %s" % e)
            return 0


_cache_service = None


async def get_cache_service() -> CacheService:
    """Get or create the cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


async def cache_get(key: str) -> Optional[Any]:
    """Helper function to get from cache"""
    service = await get_cache_service()
    return await service.get(key)


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Helper function to set cache"""
    service = await get_cache_service()
    return await service.set(key, value, ttl)


async def cache_delete(key: str) -> bool:
    """Helper function to delete from cache"""
    service = await get_cache_service()
    return await service.delete(key)
