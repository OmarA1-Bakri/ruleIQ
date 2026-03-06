"""

Redis-based rate limiting middleware for production use.

This module provides distributed rate limiting using Redis as the backend,
which is essential for production environments with multiple server instances.
"""

import time
from typing import Optional, Tuple, Any
import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from config.settings import get_settings

settings = get_settings()


class RedisRateLimiter:
    """Redis-based rate limiter for distributed environments."""

    def __init__(
        self,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        redis_url: Optional[str] = None,
        key_prefix: str = "rate_limit",
    ) -> None:
        """
        Initialize Redis rate limiter.

        Args:
            requests_per_window: Maximum requests allowed per time window
            window_seconds: Time window in seconds
            redis_url: Redis connection URL (defaults to settings.redis_url)
            key_prefix: Prefix for Redis keys
        """
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.redis_url = redis_url or settings.redis_url
        self.redis_client = None

    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client connection."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
        return self.redis_client

    async def check_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.

        Args:
            identifier: Unique identifier (e.g., IP address, user ID)

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        try:
            redis_client = await self._get_redis_client()
            key = f"{self.key_prefix}:{identifier}"
            current_time = int(time.time())
            window_start = current_time - self.window_seconds
            await redis_client.zremrangebyscore(key, 0, window_start)
            current_count = await redis_client.zcard(key)
            if current_count >= self.requests_per_window:
                oldest_requests = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_requests:
                    oldest_time = int(oldest_requests[0][1])
                    retry_after = max(1, self.window_seconds - (current_time - oldest_time))
                else:
                    retry_after = self.window_seconds
                return False, retry_after
            await redis_client.zadd(key, {str(current_time): current_time})
            await redis_client.expire(key, self.window_seconds)
            return True, 0
        except redis.RedisError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error("Redis rate limiter error: %s" % e)
            return True, 0

    async def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for the identifier."""
        try:
            redis_client = await self._get_redis_client()
            key = f"{self.key_prefix}:{identifier}"
            current_time = int(time.time())
            window_start = current_time - self.window_seconds
            await redis_client.zremrangebyscore(key, 0, window_start)
            current_count = await redis_client.zcard(key)
            return max(0, self.requests_per_window - current_count)
        except redis.RedisError:
            return self.requests_per_window

    async def reset_limit(self, identifier: str) -> bool:
        """Reset rate limit for the identifier."""
        try:
            redis_client = await self._get_redis_client()
            key = f"{self.key_prefix}:{identifier}"
            await redis_client.delete(key)
            return True
        except redis.RedisError:
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


general_limiter = RedisRateLimiter(
    requests_per_window=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window,
    key_prefix="general",
)
auth_limiter = RedisRateLimiter(requests_per_window=10, window_seconds=60, key_prefix="auth")
api_limiter = RedisRateLimiter(requests_per_window=100, window_seconds=60, key_prefix="api")


async def redis_rate_limit_middleware(request: Request, call_next) -> Any:
    """Redis-based rate limiting middleware."""
    skip_paths = ["/docs", "/redoc", "/openapi.json", "/health", "/ready"]
    if any(request.url.path.startswith(path) for path in skip_paths):
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    identifier = client_ip
    allowed, retry_after = await general_limiter.check_rate_limit(identifier)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "message": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": retry_after,
                }
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(general_limiter.requests_per_window),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + retry_after),
            },
        )
    response = await call_next(request)
    remaining = await general_limiter.get_remaining_requests(identifier)
    response.headers["X-RateLimit-Limit"] = str(general_limiter.requests_per_window)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + general_limiter.window_seconds)
    return response


def redis_rate_limit(
    requests_per_window: int = 60, window_seconds: int = 60, key_prefix: str = "custom"
) -> Any:
    """Create a custom Redis rate limit dependency."""
    limiter = RedisRateLimiter(
        requests_per_window=requests_per_window,
        window_seconds=window_seconds,
        key_prefix=key_prefix,
    )

    async def check_limit(request: Request) -> None:
        if settings.is_testing:
            return
        client_ip = request.client.host if request.client else "unknown"
        identifier = client_ip
        allowed, retry_after = await limiter.check_rate_limit(identifier)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {requests_per_window} requests per {window_seconds} seconds. Try again in {retry_after} seconds",
                headers={"Retry-After": str(retry_after)},
            )

    return check_limit


def auth_redis_rate_limit() -> Any:
    """Redis-based auth endpoint rate limiting."""

    async def check_auth_limit(request: Request) -> None:
        if settings.is_testing:
            return
        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = await auth_limiter.check_rate_limit(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many authentication attempts. Try again in {retry_after} seconds",
                headers={"Retry-After": str(retry_after)},
            )

    return check_auth_limit
