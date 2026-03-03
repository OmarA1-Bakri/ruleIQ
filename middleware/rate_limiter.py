"""
Rate Limiting Middleware for RuleIQ API

Story 1.2: Rate Limiting Implementation
Provides comprehensive rate limiting with Redis-backed sliding window algorithm.
"""
from __future__ import annotations

import time
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, status
from fastapi.responses import JSONResponse
import redis
import logging
from enum import Enum

from config.settings import settings

logger = logging.getLogger(__name__)


class UserTier(str, Enum):
    """User tier levels for rate limiting."""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"


class RateLimiter:
    """
    Redis-backed rate limiter using sliding window algorithm.

    Features:
    - Tiered rate limits (anonymous, authenticated, premium, enterprise)
    - Per-endpoint configuration
    - Sliding window for accurate rate limiting
    - Distributed counting with Redis
    - Admin bypass capability
    - Rate limit headers in responses
    """

    # Default rate limits (requests per window in seconds)
    DEFAULT_LIMITS = {
        UserTier.ANONYMOUS: {"requests": 10, "window": 60},
        UserTier.AUTHENTICATED: {"requests": 100, "window": 60},
        UserTier.PREMIUM: {"requests": 1000, "window": 60},
        UserTier.ENTERPRISE: {"requests": 10000, "window": 60},
        UserTier.ADMIN: {"requests": 999999, "window": 60},  # Effectively unlimited
    }

    # Endpoint-specific overrides
    ENDPOINT_LIMITS = {
        "/api/v1/auth/login": {"requests": 5, "window": 300},  # 5 per 5 minutes
        "/api/v1/auth/register": {"requests": 3, "window": 3600},  # 3 per hour
        "/api/v1/auth/forgot-password": {"requests": 3, "window": 3600},  # 3 per hour
        "/api/v1/reports/generate": {"requests": 10, "window": 3600},  # 10 per hour
        "/api/v1/ai/assessment": {"requests": 20, "window": 3600},  # 20 per hour
        "/api/v1/payments/process": {"requests": 10, "window": 60},  # 10 per minute
    }

    # IP whitelist for bypass (internal services, monitoring)
    IP_WHITELIST = set()

    # Service account identifiers for bypass
    SERVICE_ACCOUNTS = set()

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        """Initialize the rate limiter."""
        self.redis_client = redis_client or self._get_redis_client()
        self.key_prefix = "rate_limit:"
        self.stats_prefix = "rate_limit_stats:"

        # Load configuration
        self._load_config()

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client with connection pooling."""
        pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            max_connections=100,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        return redis.Redis(connection_pool=pool, decode_responses=False)

    def _load_config(self):
        """Load rate limit configuration from settings."""
        # Load from environment or config file
        if hasattr(settings, 'RATE_LIMIT_IP_WHITELIST'):
            self.IP_WHITELIST.update(settings.RATE_LIMIT_IP_WHITELIST)

        if hasattr(settings, 'RATE_LIMIT_SERVICE_ACCOUNTS'):
            self.SERVICE_ACCOUNTS.update(settings.RATE_LIMIT_SERVICE_ACCOUNTS)

        # Override default limits if configured
        if hasattr(settings, 'RATE_LIMITS'):
            for tier, limits in settings.RATE_LIMITS.items():
                if tier in UserTier:
                    self.DEFAULT_LIMITS[UserTier(tier)] = limits

    def get_user_tier(self, request: Request) -> UserTier:
        """
        Determine the user's tier from the request.

        Args:
            request: FastAPI request object

        Returns:
            User tier level
        """
        # Check if user is authenticated
        user = getattr(request.state, "user", None)

        if not user:
            return UserTier.ANONYMOUS

        # Check for admin
        if getattr(user, "is_admin", False):
            return UserTier.ADMIN

        # Check for service account
        user_id = getattr(user, "id", None)
        if user_id and str(user_id) in self.SERVICE_ACCOUNTS:
            return UserTier.ADMIN

        # Check user subscription tier
        subscription = getattr(user, "subscription_tier", None)
        if subscription:
            if subscription == "enterprise":
                return UserTier.ENTERPRISE
            elif subscription == "premium":
                return UserTier.PREMIUM

        return UserTier.AUTHENTICATED

    def get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting.

        Args:
            request: FastAPI request object

        Returns:
            Unique identifier string
        """
        # Try to get authenticated user ID
        user = getattr(request.state, "user", None)
        if user:
            user_id = getattr(user, "id", None)
            if user_id:
                return f"user:{user_id}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"

        # Check for X-Forwarded-For header (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()

        return f"ip:{client_ip}"

    def get_rate_limit(self, endpoint: str, tier: UserTier) -> Dict[str, int]:
        """
        Get rate limit for endpoint and tier.

        Args:
            endpoint: API endpoint path
            tier: User tier

        Returns:
            Rate limit configuration
        """
        # Check for endpoint-specific override
        if endpoint in self.ENDPOINT_LIMITS:
            return self.ENDPOINT_LIMITS[endpoint]

        # Check for pattern match
        for pattern, limits in self.ENDPOINT_LIMITS.items():
            if "*" in pattern:
                # Convert pattern to regex
                import re
                regex_pattern = pattern.replace("*", ".*")
                if re.match(regex_pattern, endpoint):
                    return limits

        # Return default for tier
        return self.DEFAULT_LIMITS.get(tier, self.DEFAULT_LIMITS[UserTier.ANONYMOUS])

    def should_bypass(self, request: Request) -> bool:
        """
        Check if request should bypass rate limiting.

        Args:
            request: FastAPI request object

        Returns:
            True if should bypass
        """
        # Check IP whitelist
        client_ip = request.client.host if request.client else None
        if client_ip and client_ip in self.IP_WHITELIST:
            logger.debug(f"Bypassing rate limit for whitelisted IP: {client_ip}")
            return True

        # Check for admin bypass
        user = getattr(request.state, "user", None)
        if user and getattr(user, "is_admin", False):
            # Log admin bypass for audit
            user_id = getattr(user, "id", "unknown")
            logger.info(f"Admin bypass for user {user_id} on {request.url.path}")
            return True

        # Check service accounts
        if user:
            user_id = getattr(user, "id", None)
            if user_id and str(user_id) in self.SERVICE_ACCOUNTS:
                logger.debug(f"Service account bypass for {user_id}")
                return True

        return False

    async def check_rate_limit(self, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request exceeds rate limit.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        try:
            # Check for bypass
            if self.should_bypass(request):
                return True, {"bypassed": True}

            # Get user tier and identifier
            tier = self.get_user_tier(request)
            identifier = self.get_identifier(request)
            endpoint = request.url.path

            # Get rate limit for this endpoint/tier
            limits = self.get_rate_limit(endpoint, tier)
            max_requests = limits["requests"]
            window_seconds = limits["window"]

            # Create Redis key
            redis_key = f"{self.key_prefix}{endpoint}:{identifier}"

            # Current timestamp in milliseconds
            now_ms = int(time.time() * 1000)
            window_start_ms = now_ms - (window_seconds * 1000)

            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start_ms)

            # Count requests in current window
            pipe.zcard(redis_key)

            # Add current request
            pipe.zadd(redis_key, {str(now_ms): now_ms})

            # Set expiry on the key
            pipe.expire(redis_key, window_seconds + 1)

            # Execute pipeline
            results = pipe.execute()

            # Get request count (before adding current)
            request_count = results[1]

            # Calculate rate limit info
            remaining = max(0, max_requests - request_count - 1)
            reset_time = int((now_ms + window_seconds * 1000) / 1000)

            rate_limit_info = {
                "limit": max_requests,
                "remaining": remaining,
                "reset": reset_time,
                "window": window_seconds,
                "tier": tier.value
            }

            # Check if limit exceeded
            if request_count >= max_requests:
                # Log violation
                logger.warning(
                    f"Rate limit exceeded for {identifier} on {endpoint}: "
                    f"{request_count}/{max_requests} in {window_seconds}s"
                )

                # Update statistics
                self._update_stats(endpoint, tier, violated=True)

                # Calculate retry after
                rate_limit_info["retry_after"] = window_seconds

                return False, rate_limit_info

            # Update statistics
            self._update_stats(endpoint, tier, violated=False)

            return True, rate_limit_info

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiting: {e}")

            # Decide whether to fail open or closed
            fail_open = getattr(settings, "RATE_LIMIT_FAIL_OPEN", True)

            if fail_open:
                logger.warning("Rate limiter failing open due to Redis error")
                return True, {"error": "rate_limiter_unavailable"}
            else:
                logger.warning("Rate limiter failing closed due to Redis error")
                return False, {"error": "rate_limiter_unavailable", "retry_after": 60}

        except Exception as e:
            logger.error(f"Unexpected error in rate limiting: {e}")
            return True, {"error": "rate_limiter_error"}

    def _update_stats(self, endpoint: str, tier: UserTier, violated: bool):
        """Update rate limit statistics."""
        try:
            stats_key = f"{self.stats_prefix}{endpoint}"

            pipe = self.redis_client.pipeline()

            # Increment request counter
            pipe.hincrby(stats_key, f"requests:{tier.value}", 1)

            # Increment violation counter if applicable
            if violated:
                pipe.hincrby(stats_key, f"violations:{tier.value}", 1)

            # Set expiry (1 day)
            pipe.expire(stats_key, 86400)

            pipe.execute()

        except redis.RedisError:
            # Don't fail the request due to stats error
            pass

    def get_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limit statistics."""
        try:
            if endpoint:
                stats_key = f"{self.stats_prefix}{endpoint}"
                stats = self.redis_client.hgetall(stats_key)
                return {
                    k.decode(): int(v) for k, v in stats.items()
                }
            else:
                # Get all stats
                all_stats = {}
                for key in self.redis_client.scan_iter(f"{self.stats_prefix}*"):
                    endpoint = key.decode().replace(self.stats_prefix, "")
                    stats = self.redis_client.hgetall(key)
                    all_stats[endpoint] = {
                        k.decode(): int(v) for k, v in stats.items()
                    }
                return all_stats

        except redis.RedisError:
            return {}

    def reset_limits(self, identifier: str, endpoint: Optional[str] = None):
        """Reset rate limits for an identifier (admin action)."""
        try:
            if endpoint:
                key = f"{self.key_prefix}{endpoint}:{identifier}"
                self.redis_client.delete(key)
            else:
                # Reset all endpoints for identifier
                pattern = f"{self.key_prefix}*:{identifier}"
                for key in self.redis_client.scan_iter(pattern):
                    self.redis_client.delete(key)

            logger.info(f"Reset rate limits for {identifier} on {endpoint or 'all endpoints'}")
            return True

        except redis.RedisError as e:
            logger.error(f"Error resetting rate limits: {e}")
            return False


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None) -> None:
        """Initialize the middleware."""
        self.app = app
        self.rate_limiter = rate_limiter or RateLimiter()

    async def __call__(self, request: Request, call_next):
        """Process the request through rate limiting."""
        # Skip rate limiting for health checks and docs
        skip_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        if request.url.path in skip_paths:
            return await call_next(request)

        # Check rate limit
        allowed, rate_info = await self.rate_limiter.check_rate_limit(request)

        if not allowed:
            # Return 429 Too Many Requests
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please retry after {rate_info.get('retry_after', 60)} seconds.",
                    "retry_after": rate_info.get("retry_after", 60),
                    "limit": rate_info.get("limit"),
                    "remaining": 0,
                    "reset": rate_info.get("reset")
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info.get("limit", 0)),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(rate_info.get("reset", 0)),
                    "Retry-After": str(rate_info.get("retry_after", 60))
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        if not rate_info.get("bypassed"):
            response.headers["X-RateLimit-Limit"] = str(rate_info.get("limit", 0))
            response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
            response.headers["X-RateLimit-Reset"] = str(rate_info.get("reset", 0))

        return response
