"""
Redis Circuit Breaker Service
Implements circuit breaker pattern for Redis with fallback strategies
"""

import asyncio
import time
from typing import Optional, Any, Dict
from enum import Enum
from collections import OrderedDict
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError
import logging
from config.security_settings import get_security_settings, RedisFailureStrategy
import contextlib

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class LocalCache:
    """Simple LRU cache for fallback when Redis is unavailable"""

    def __init__(self, max_size: int = 1000, ttl: int = 300) -> None:
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return value
            else:
                # Expired
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with timestamp"""
        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self.cache.popitem(last=False)

        self.cache[key] = (value, time.time())
        self.cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()


class RedisCircuitBreaker:
    """
    Circuit breaker for Redis operations with fallback strategies

    Features:
    - Circuit breaker pattern to prevent cascade failures
    - Local cache fallback for degraded mode
    - Configurable failure strategies (fail open/closed/degraded)
    - Health monitoring and auto-recovery
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        failure_strategy: Optional[RedisFailureStrategy] = None,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3,
    ) -> None:
        self.settings = get_security_settings()
        self.redis_config = self.settings.redis

        # Redis client
        self.redis_client = redis_client

        # Circuit breaker configuration
        self.failure_strategy = failure_strategy or self.redis_config.failure_strategy
        self.failure_threshold = failure_threshold or self.redis_config.circuit_breaker_threshold
        self.recovery_timeout = recovery_timeout or self.redis_config.circuit_breaker_timeout
        self.half_open_requests = (
            half_open_requests or self.redis_config.circuit_breaker_half_open_requests
        )

        # Circuit breaker state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_success_count = 0

        # Local cache for degraded mode
        self.local_cache = (
            LocalCache(
                max_size=self.redis_config.local_cache_max_size,
                ttl=self.redis_config.local_cache_ttl,
            )
            if self.redis_config.enable_local_cache
            else None
        )

        # Health check task
        self.health_check_task: Optional[asyncio.Task] = None

        logger.info(f"Redis circuit breaker initialized with strategy: {self.failure_strategy}")

    async def initialize(self) -> None:
        """Initialize Redis connection and start health monitoring"""
        if not self.redis_client:
            try:
                self.redis_client = await redis.from_url(
                    f"redis://{self.redis_config.host}:{self.redis_config.port}/{self.redis_config.db}",
                    password=self.redis_config.password,
                    max_connections=self.redis_config.max_connections,
                    socket_timeout=self.redis_config.socket_timeout,
                    socket_connect_timeout=self.redis_config.socket_connect_timeout,
                    socket_keepalive=self.redis_config.socket_keepalive,
                    socket_keepalive_options=self.redis_config.socket_keepalive_options,
                )
                await self.redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._trip_circuit()

        # Start health monitoring
        if self.redis_config.health_check_interval > 0:
            self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def close(self) -> None:
        """Cleanup resources"""
        if self.health_check_task:
            self.health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.health_check_task

        if self.redis_client:
            await self.redis_client.close()

    async def _health_check_loop(self) -> None:
        """Periodic health check for Redis"""
        while True:
            try:
                await asyncio.sleep(self.redis_config.health_check_interval)

                if self.state == CircuitState.OPEN:
                    # Check if recovery timeout has passed
                    if time.time() - self.last_failure_time > self.recovery_timeout:
                        logger.info("Attempting to recover Redis connection")
                        self.state = CircuitState.HALF_OPEN
                        self.half_open_success_count = 0

                # Perform health check
                if self.redis_client and self.state != CircuitState.OPEN:
                    try:
                        await asyncio.wait_for(
                            self.redis_client.ping(), timeout=self.redis_config.health_check_timeout
                        )

                        if self.state == CircuitState.HALF_OPEN:
                            self.half_open_success_count += 1
                            if self.half_open_success_count >= self.half_open_requests:
                                self._close_circuit()
                    except Exception as e:
                        logger.warning(f"Health check failed: {e}")
                        self._record_failure()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    def _trip_circuit(self) -> None:
        """Trip the circuit breaker"""
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        logger.error(f"Circuit breaker tripped! Strategy: {self.failure_strategy}")

    def _close_circuit(self) -> None:
        """Close the circuit breaker (normal operation)"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_success_count = 0
        logger.info("Circuit breaker closed - Redis connection recovered")

    def _record_failure(self) -> None:
        """Record a failure and trip circuit if threshold reached"""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self._trip_circuit()

    def _should_allow_request(self) -> bool:
        """Determine if request should be allowed based on circuit state"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_success_count = 0
                return True

            # Apply failure strategy
            if self.failure_strategy == RedisFailureStrategy.FAIL_OPEN:
                return True  # Allow request without Redis
            elif self.failure_strategy == RedisFailureStrategy.FAIL_CLOSED:
                return False  # Deny request
            else:  # DEGRADED
                return True  # Allow with local cache

        # Half-open state - allow limited requests
        return self.half_open_success_count < self.half_open_requests

    async def get(self, key: str) -> Optional[Any]:
        """Get value with circuit breaker protection"""
        if not self._should_allow_request():
            if self.failure_strategy == RedisFailureStrategy.FAIL_CLOSED:
                raise RedisError("Circuit breaker open - Redis unavailable")
            return None

        try:
            if self.redis_client and self.state != CircuitState.OPEN:
                value = await self.redis_client.get(key)

                # Cache locally if degraded mode enabled
                if value and self.local_cache:
                    self.local_cache.set(key, value)

                # Record success in half-open state
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_success_count += 1
                    if self.half_open_success_count >= self.half_open_requests:
                        self._close_circuit()

                return value

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"Redis get failed: {e}")
            self._record_failure()

        # Fallback to local cache if available
        if self.local_cache and self.failure_strategy == RedisFailureStrategy.DEGRADED:
            return self.local_cache.get(key)

        return None

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value with circuit breaker protection"""
        if not self._should_allow_request():
            if self.failure_strategy == RedisFailureStrategy.FAIL_CLOSED:
                raise RedisError("Circuit breaker open - Redis unavailable")

            # Store in local cache if degraded mode
            if self.local_cache and self.failure_strategy == RedisFailureStrategy.DEGRADED:
                self.local_cache.set(key, value)
                return True

            return False

        try:
            if self.redis_client and self.state != CircuitState.OPEN:
                await self.redis_client.set(key, value, ex=ex)

                # Also cache locally if degraded mode enabled
                if self.local_cache:
                    self.local_cache.set(key, value)

                # Record success in half-open state
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_success_count += 1
                    if self.half_open_success_count >= self.half_open_requests:
                        self._close_circuit()

                return True

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"Redis set failed: {e}")
            self._record_failure()

            # Store in local cache if degraded mode
            if self.local_cache and self.failure_strategy == RedisFailureStrategy.DEGRADED:
                self.local_cache.set(key, value)
                return True

        return False

    async def delete(self, key: str) -> bool:
        """Delete value with circuit breaker protection"""
        if not self._should_allow_request():
            if self.failure_strategy == RedisFailureStrategy.FAIL_CLOSED:
                raise RedisError("Circuit breaker open - Redis unavailable")

            # Delete from local cache if degraded mode
            if self.local_cache and self.failure_strategy == RedisFailureStrategy.DEGRADED:
                return self.local_cache.delete(key)

            return False

        try:
            if self.redis_client and self.state != CircuitState.OPEN:
                result = await self.redis_client.delete(key)

                # Also delete from local cache
                if self.local_cache:
                    self.local_cache.delete(key)

                # Record success in half-open state
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_success_count += 1
                    if self.half_open_success_count >= self.half_open_requests:
                        self._close_circuit()

                return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"Redis delete failed: {e}")
            self._record_failure()

            # Delete from local cache if degraded mode
            if self.local_cache and self.failure_strategy == RedisFailureStrategy.DEGRADED:
                return self.local_cache.delete(key)

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_strategy": self.failure_strategy.value,
            "last_failure_time": self.last_failure_time,
            "time_until_recovery": max(
                0, self.recovery_timeout - (time.time() - self.last_failure_time)
            )
            if self.state == CircuitState.OPEN
            else 0,
            "local_cache_enabled": self.local_cache is not None,
            "local_cache_size": len(self.local_cache.cache) if self.local_cache else 0,
        }


# Global instance
_redis_circuit_breaker: Optional[RedisCircuitBreaker] = None


async def get_redis_circuit_breaker() -> RedisCircuitBreaker:
    """Get or create Redis circuit breaker singleton"""
    global _redis_circuit_breaker
    if _redis_circuit_breaker is None:
        _redis_circuit_breaker = RedisCircuitBreaker()
        await _redis_circuit_breaker.initialize()
    return _redis_circuit_breaker
