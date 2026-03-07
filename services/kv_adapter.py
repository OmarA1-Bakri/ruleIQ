"""
Vercel KV adapter for cache operations.
Provides a unified interface for Redis and Vercel KV with feature flags.
"""

import os
import json
import logging
from typing import Any, Optional, List, Dict
import httpx
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CacheAdapter(ABC):
    """Abstract base class for cache adapters."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value with optional expiration in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key."""
        pass

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """Get TTL for key in seconds."""
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        pass

    @abstractmethod
    async def flush_all(self) -> bool:
        """Flush all keys."""
        pass

    @abstractmethod
    async def close(self):
        """Close connection."""
        pass


class VercelKVAdapter(CacheAdapter):
    """Adapter for Vercel KV using REST API."""

    def __init__(self) -> None:
        """Initialize Vercel KV adapter."""
        self.api_url = os.getenv("VERCEL_KV_REST_API_URL", "")
        self.api_token = os.getenv("VERCEL_KV_REST_API_TOKEN", "")

        if not self.api_url or not self.api_token:
            logger.warning("Vercel KV credentials not found. Cache operations will fail.")

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _execute(self, command: List[str]) -> Any:
        """Execute a Redis command via Vercel KV REST API."""
        if not self.api_url:
            logger.error("Vercel KV not configured")
            return None

        try:
            response = await self.client.post(self.api_url, json=command)

            if response.status_code == 200:
                result = response.json()
                return result.get("result")
            else:
                logger.error(f"Vercel KV error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Vercel KV request failed: {str(e)}")
            return None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Vercel KV."""
        result = await self._execute(["GET", key])

        if result is None:
            return None

        # Try to deserialize JSON
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in Vercel KV with optional expiration."""
        # Serialize value to JSON if needed
        if not isinstance(value, (str, int, float)):
            value = json.dumps(value)

        if expire:
            # SET with EX option
            result = await self._execute(["SET", key, value, "EX", str(expire)])
        else:
            result = await self._execute(["SET", key, value])

        return result == "OK"

    async def delete(self, key: str) -> bool:
        """Delete key from Vercel KV."""
        result = await self._execute(["DEL", key])
        return bool(result)

    async def exists(self, key: str) -> bool:
        """Check if key exists in Vercel KV."""
        result = await self._execute(["EXISTS", key])
        return bool(result)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key in Vercel KV."""
        result = await self._execute(["EXPIRE", key, str(seconds)])
        return bool(result)

    async def ttl(self, key: str) -> int:
        """Get TTL for key from Vercel KV."""
        result = await self._execute(["TTL", key])
        return int(result) if result else -1

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern from Vercel KV."""
        result = await self._execute(["KEYS", pattern])
        return result if isinstance(result, list) else []

    async def flush_all(self) -> bool:
        """Flush all keys in Vercel KV."""
        result = await self._execute(["FLUSHALL"])
        return result == "OK"

    async def incr(self, key: str) -> int:
        """Increment counter in Vercel KV."""
        result = await self._execute(["INCR", key])
        return int(result) if result else 0

    async def decr(self, key: str) -> int:
        """Decrement counter in Vercel KV."""
        result = await self._execute(["DECR", key])
        return int(result) if result else 0

    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field in Vercel KV."""
        if not isinstance(value, (str, int, float)):
            value = json.dumps(value)
        result = await self._execute(["HSET", key, field, value])
        return bool(result)

    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field from Vercel KV."""
        result = await self._execute(["HGET", key, field])
        if result is None:
            return None

        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields from Vercel KV."""
        result = await self._execute(["HGETALL", key])

        if not result or not isinstance(result, dict):
            return {}

        # Deserialize values
        decoded = {}
        for k, v in result.items():
            try:
                decoded[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                decoded[k] = v

        return decoded

    async def lpush(self, key: str, *values) -> int:
        """Push values to list in Vercel KV."""
        serialized = []
        for value in values:
            if not isinstance(value, (str, int, float)):
                serialized.append(json.dumps(value))
            else:
                serialized.append(value)

        result = await self._execute(["LPUSH", key] + serialized)
        return int(result) if result else 0

    async def rpop(self, key: str) -> Optional[Any]:
        """Pop value from list in Vercel KV."""
        result = await self._execute(["RPOP", key])

        if result is None:
            return None

        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    async def lrange(self, key: str, start: int, stop: int) -> List[Any]:
        """Get range of values from list in Vercel KV."""
        result = await self._execute(["LRANGE", key, str(start), str(stop)])

        if not result or not isinstance(result, list):
            return []

        # Deserialize values
        decoded = []
        for item in result:
            try:
                decoded.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                decoded.append(item)

        return decoded

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class RedisAdapter(CacheAdapter):
    """Adapter for Redis (for local/dev environments)."""

    def __init__(self) -> None:
        """Initialize Redis adapter."""
        import redis.asyncio as redis

        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        result = await self.client.get(key)

        if result is None:
            return None

        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in Redis with optional expiration."""
        if not isinstance(value, (str, int, float)):
            value = json.dumps(value)

        return await self.client.set(key, value, ex=expire)

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        result = await self.client.delete(key)
        return bool(result)

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        result = await self.client.exists(key)
        return bool(result)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key in Redis."""
        return await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get TTL for key from Redis."""
        result = await self.client.ttl(key)
        return result

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern from Redis."""
        return await self.client.keys(pattern)

    async def flush_all(self) -> bool:
        """Flush all keys in Redis."""
        await self.client.flushall()
        return True

    async def close(self):
        """Close Redis connection."""
        await self.client.close()


def get_cache_adapter() -> CacheAdapter:
    """
    Get appropriate cache adapter based on environment.

    Returns:
        CacheAdapter instance (VercelKV for production, Redis for dev)
    """
    use_vercel_kv = os.getenv("USE_VERCEL_KV", "false").lower() == "true"
    is_production = os.getenv("VERCEL_ENV") == "production"

    if use_vercel_kv or is_production:
        logger.info("Using Vercel KV adapter for cache")
        return VercelKVAdapter()
    else:
        logger.info("Using Redis adapter for cache")
        return RedisAdapter()


# Singleton instance
_cache_adapter: Optional[CacheAdapter] = None


async def get_cache() -> CacheAdapter:
    """Get or create singleton cache adapter."""
    global _cache_adapter
    if _cache_adapter is None:
        _cache_adapter = get_cache_adapter()
    return _cache_adapter
