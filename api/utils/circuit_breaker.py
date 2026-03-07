"""

Circuit breaker implementation for ComplianceGPT.
Protects external services from cascading failures.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Awaitable, Callable, Optional, Tuple, Type, TypeVar, Any
from core.exceptions import APIError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: Tuple[Type[Exception], ...] = (ConnectionError, TimeoutError, OSError)
    success_threshold: int = 3
    timeout_seconds: Optional[float] = 30.0


class CircuitBreakerOpenException(APIError):
    """Exception when circuit breaker is open."""

    def __init__(
        self, service_name: str, failure_count: int, recovery_time: Optional[float] = None
    ) -> None:
        message = f"Circuit breaker open for {service_name} (failures: {failure_count})"
        if recovery_time:
            message += f", recovery in {recovery_time:.1f}s"
        super().__init__(message=message, status_code=503)
        self.details = {
            "service_name": service_name,
            "failure_count": failure_count,
            "recovery_time": recovery_time,
        }


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(self, name: str, config: CircuitBreakerConfig = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._last_state_change = time.time()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state, checking for recovery."""
        if (
            self._state == CircuitBreakerState.OPEN
            and time.time() - self._last_failure_time > self.config.recovery_timeout
        ):
            self._state = CircuitBreakerState.HALF_OPEN
            self._success_count = 0
        return self._state

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                recovery_time = self.config.recovery_timeout - (
                    time.time() - self._last_failure_time
                )
                raise CircuitBreakerOpenException(self.name, self._failure_count, recovery_time)
        try:
            if self.config.timeout_seconds:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=self.config.timeout_seconds
                )
            else:
                result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.expected_exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._last_success_time = time.time()
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker %s closed after recovery" % self.name)

    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.config.failure_threshold:
                if self._state != CircuitBreakerState.OPEN:
                    self._state = CircuitBreakerState.OPEN
                    logger.error(
                        "Circuit breaker %s opened after %s failures"
                        % (self.name, self._failure_count)
                    )

    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Decorator usage."""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await self.call(func, *args, **kwargs)

        return wrapper


openai_breaker = CircuitBreaker(
    "OpenAI", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0, timeout_seconds=60.0)
)
google_breaker = CircuitBreaker(
    "Google", CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0, timeout_seconds=30.0)
)
aws_breaker = CircuitBreaker(
    "AWS", CircuitBreakerConfig(failure_threshold=5, recovery_timeout=45.0, timeout_seconds=30.0)
)
