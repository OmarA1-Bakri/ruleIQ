"""
Enhanced Rate Limiting Middleware with Token Bucket Algorithm
Implements burst allowance, IP/user-based limiting, and hot-reload configuration
"""

import time
import asyncio
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
import json
from config.security_settings import get_security_settings
from services.redis_circuit_breaker import get_redis_circuit_breaker

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket algorithm for rate limiting with burst support"""

    def __init__(
        self, capacity: int, refill_rate: float, initial_tokens: Optional[int] = None
    ) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket"""
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill bucket based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def to_dict(self) -> Dict[str, Any]:
        """Serialize bucket state"""
        return {
            "capacity": self.capacity,
            "refill_rate": self.refill_rate,
            "tokens": self.tokens,
            "last_refill": self.last_refill,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenBucket":
        """Deserialize bucket state"""
        bucket = cls(
            capacity=data["capacity"],
            refill_rate=data["refill_rate"],
            initial_tokens=data["tokens"],
        )
        bucket.last_refill = data["last_refill"]
        return bucket


class EnhancedRateLimiter(BaseHTTPMiddleware):
    """
    Enhanced rate limiting middleware with:
    - Token bucket algorithm for burst allowance
    - IP-based and user-based limiting
    - Endpoint-specific limits
    - Configuration hot-reload
    - Detailed rate limit headers
    """

    def __init__(self, app: ASGIApp, **kwargs) -> None:
        super().__init__(app)
        self.security_settings = get_security_settings()
        self.rate_config = self.security_settings.rate_limit

        # Rate limiting configuration
        self.default_rate_limit = self.rate_config.default_rate_limit
        self.default_burst_size = self.rate_config.default_burst_size
        self.endpoint_limits = self.rate_config.endpoint_limits

        # Strategy settings
        self.use_ip_based = self.rate_config.use_ip_based
        self.use_user_based = self.rate_config.use_user_based
        self.combine_limits = self.rate_config.combine_limits

        # Token bucket settings
        self.refill_rate = self.rate_config.refill_rate
        self.bucket_capacity = self.rate_config.bucket_capacity

        # Configuration hot-reload
        self.enable_hot_reload = self.rate_config.enable_hot_reload
        self.config_refresh_interval = self.rate_config.config_refresh_interval
        self.last_config_reload = time.time()

        # Response headers
        self.include_headers = self.rate_config.include_headers
        self.header_prefix = self.rate_config.header_prefix

        # Redis for distributed rate limiting
        self.redis_breaker = None

        # Local cache for degraded mode
        self.local_buckets: Dict[str, TokenBucket] = {}

        # Start hot-reload task if enabled
        if self.enable_hot_reload:
            asyncio.create_task(self._config_reload_loop())

        logger.info("Enhanced rate limiter initialized with token bucket algorithm")

    async def __call__(self, scope, receive, send):
        """Process requests with rate limiting"""
        if scope["type"] == "http":
            # Initialize Redis if not done
            if not self.redis_breaker:
                try:
                    self.redis_breaker = await get_redis_circuit_breaker()
                except Exception as e:
                    logger.warning(f"Redis initialization failed, using local buckets: {e}")

            await super().__call__(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to requests"""

        # Check if hot-reload is needed
        if self.enable_hot_reload:
            await self._check_config_reload()

        # Get rate limit for this endpoint
        limit_config = self._get_endpoint_limit(request.url.path)

        # Get client identifiers
        ip_address = self._get_client_ip(request)
        user_id = await self._get_user_id(request)

        # Apply rate limiting
        rate_limit_result = await self._check_rate_limit(
            request=request, ip_address=ip_address, user_id=user_id, limit_config=limit_config
        )

        if not rate_limit_result["allowed"]:
            # Add rate limit headers
            headers = self._create_rate_limit_headers(rate_limit_result)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers=headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful response
        if self.include_headers:
            headers = self._create_rate_limit_headers(rate_limit_result)
            for header, value in headers.items():
                response.headers[header] = value

        return response

    async def _check_rate_limit(
        self,
        request: Request,
        ip_address: str,
        user_id: Optional[str],
        limit_config: Dict[str, int],
    ) -> Dict[str, Any]:
        """Check if request is within rate limits"""

        results = []

        # Check IP-based limit
        if self.use_ip_based and ip_address:
            ip_result = await self._check_bucket(
                key=f"rate:ip:{ip_address}:{request.url.path}",
                limit=limit_config["limit"],
                burst=limit_config["burst"],
            )
            results.append(ip_result)

        # Check user-based limit
        if self.use_user_based and user_id:
            user_result = await self._check_bucket(
                key=f"rate:user:{user_id}:{request.url.path}",
                limit=limit_config["limit"],
                burst=limit_config["burst"],
            )
            results.append(user_result)

        # If no specific limiting, use default IP-based
        if not results:
            ip_result = await self._check_bucket(
                key=f"rate:ip:{ip_address}:{request.url.path}",
                limit=limit_config["limit"],
                burst=limit_config["burst"],
            )
            results.append(ip_result)

        # Combine results based on strategy
        if self.combine_limits and len(results) > 1:
            # Both limits must pass
            allowed = all(r["allowed"] for r in results)
            # Use the most restrictive limit for headers
            result = min(results, key=lambda r: r["remaining"])
            result["allowed"] = allowed
        else:
            # Use the first result (IP or user)
            result = results[0]

        return result

    async def _check_bucket(self, key: str, limit: int, burst: int) -> Dict[str, Any]:
        """Check token bucket for rate limiting"""

        # Calculate bucket parameters
        capacity = limit + burst  # Total capacity including burst
        refill_rate = limit / 60.0  # Convert per-minute to per-second

        # Try Redis first
        if self.redis_breaker:
            try:
                bucket_data = await self._get_redis_bucket(key)

                if bucket_data:
                    bucket = TokenBucket.from_dict(bucket_data)
                else:
                    bucket = TokenBucket(capacity, refill_rate)

                # Try to consume token
                allowed = bucket.consume()

                # Save updated bucket
                await self._save_redis_bucket(key, bucket.to_dict())

                return {
                    "allowed": allowed,
                    "limit": limit,
                    "burst": burst,
                    "remaining": int(bucket.tokens),
                    "reset": int(time.time() + (capacity - bucket.tokens) / refill_rate),
                }

            except Exception as e:
                logger.warning(f"Redis bucket check failed, using local: {e}")

        # Fallback to local buckets
        if key not in self.local_buckets:
            self.local_buckets[key] = TokenBucket(capacity, refill_rate)

        bucket = self.local_buckets[key]
        allowed = bucket.consume()

        return {
            "allowed": allowed,
            "limit": limit,
            "burst": burst,
            "remaining": int(bucket.tokens),
            "reset": int(time.time() + (capacity - bucket.tokens) / refill_rate),
        }

    async def _get_redis_bucket(self, key: str) -> Optional[Dict[str, Any]]:
        """Get bucket data from Redis"""
        if not self.redis_breaker:
            return None

        data = await self.redis_breaker.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    async def _save_redis_bucket(self, key: str, bucket_data: Dict[str, Any]) -> None:
        """Save bucket data to Redis"""
        if not self.redis_breaker:
            return

        # Set with TTL of 1 hour (buckets reset if not used)
        await self.redis_breaker.set(key, json.dumps(bucket_data), ex=3600)

    def _get_endpoint_limit(self, path: str) -> Dict[str, int]:
        """Get rate limit configuration for endpoint"""

        # Check exact match first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]

        # Check wildcard patterns
        for pattern, config in self.endpoint_limits.items():
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return config

        # Return default limits
        return {"limit": self.default_rate_limit, "burst": self.default_burst_size}

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""

        # Check X-Forwarded-For header (for proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get first IP in chain
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Use direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _get_user_id(self, request: Request) -> Optional[str]:
        """Get user ID from request (if authenticated)"""

        # Check if user is set by authentication middleware
        if hasattr(request.state, "user_id"):
            return request.state.user_id

        # Try to decode JWT from cookie or header
        # (This would integrate with JWT middleware)
        return None

    def _create_rate_limit_headers(self, result: Dict[str, Any]) -> Dict[str, str]:
        """Create rate limit headers for response"""

        headers = {}

        if self.include_headers:
            headers[f"{self.header_prefix}-Limit"] = str(result["limit"])
            headers[f"{self.header_prefix}-Remaining"] = str(max(0, result["remaining"]))
            headers[f"{self.header_prefix}-Reset"] = str(result["reset"])
            headers[f"{self.header_prefix}-Burst"] = str(result["burst"])

            # Add retry-after header if rate limited
            if not result["allowed"]:
                retry_after = result["reset"] - int(time.time())
                headers["Retry-After"] = str(max(1, retry_after))

        return headers

    async def _check_config_reload(self) -> None:
        """Check if configuration should be reloaded"""

        now = time.time()
        if now - self.last_config_reload > self.config_refresh_interval:
            await self._reload_configuration()
            self.last_config_reload = now

    async def _reload_configuration(self) -> None:
        """Reload rate limiting configuration"""

        try:
            # Reload security settings
            self.security_settings = get_security_settings()
            self.rate_config = self.security_settings.rate_limit

            # Update configuration
            self.default_rate_limit = self.rate_config.default_rate_limit
            self.default_burst_size = self.rate_config.default_burst_size
            self.endpoint_limits = self.rate_config.endpoint_limits
            self.use_ip_based = self.rate_config.use_ip_based
            self.use_user_based = self.rate_config.use_user_based
            self.combine_limits = self.rate_config.combine_limits

            logger.info("Rate limiting configuration reloaded")

        except Exception as e:
            logger.error(f"Failed to reload rate limiting configuration: {e}")

    async def _config_reload_loop(self) -> None:
        """Background task for configuration hot-reload"""

        while self.enable_hot_reload:
            try:
                await asyncio.sleep(self.config_refresh_interval)
                await self._reload_configuration()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in config reload loop: {e}")


def setup_rate_limiter(app: ASGIApp) -> ASGIApp:
    """Setup enhanced rate limiter middleware"""
    app.add_middleware(EnhancedRateLimiter)
    return app
