"""

Advanced retry mechanism with exponential backoff for ComplianceGPT.
Supports both synchronous and asynchronous functions with comprehensive error handling.
"""

import asyncio
import functools
import inspect
import logging
import random
import time
from typing import Awaitable, Callable, Optional, TypeVar, Any

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: tuple = (Exception,),
        on_retry: Optional[Callable] = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
        self.on_retry = on_retry


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, attempts: int, last_exception: Exception) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"Retry exhausted after {attempts} attempts. Last exception: {type(last_exception).__name__}: {last_exception}",
        )


class RetryManager:
    """Manages retry logic for both sync and async functions."""

    def __init__(self, config: RetryConfig) -> None:
        self.config = config

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        delay = self.config.base_delay * self.config.exponential_base ** (attempt - 1)
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        return max(0, delay)

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if we should retry based on the exception and attempt count."""
        if attempt >= self.config.max_attempts:
            return False
        return isinstance(exception, self.config.exceptions)

    def log_retry_attempt(self, attempt: int, exception: Exception, delay: float) -> None:
        """Log retry attempt details."""
        logger.warning(
            "Retry attempt %s/%s after %s: %s. Retrying in %s seconds..."
            % (attempt, self.config.max_attempts, type(exception).__name__, exception, delay)
        )

    async def execute_async(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute async function with retry logic."""
        last_exception = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                if attempt > 1:
                    logger.info("Function succeeded on attempt %s" % attempt)
                return result
            except Exception as e:
                last_exception = e
                if not self.should_retry(e, attempt):
                    if attempt >= self.config.max_attempts:
                        raise RetryExhaustedError(attempt, e)
                    else:
                        raise
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    self.log_retry_attempt(attempt, e, delay)
                    if self.config.on_retry:
                        try:
                            if inspect.iscoroutinefunction(self.config.on_retry):
                                await self.config.on_retry(attempt, e, delay)
                            else:
                                self.config.on_retry(attempt, e, delay)
                        except Exception as callback_error:
                            logger.warning("Retry callback failed: %s" % callback_error)
                    await asyncio.sleep(delay)
        raise RetryExhaustedError(self.config.max_attempts, last_exception)

    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute sync function with retry logic."""
        last_exception = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info("Function succeeded on attempt %s" % attempt)
                return result
            except Exception as e:
                last_exception = e
                if not self.should_retry(e, attempt):
                    if attempt >= self.config.max_attempts:
                        raise RetryExhaustedError(attempt, e)
                    else:
                        raise
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    self.log_retry_attempt(attempt, e, delay)
                    if self.config.on_retry:
                        try:
                            self.config.on_retry(attempt, e, delay)
                        except Exception as callback_error:
                            logger.warning("Retry callback failed: %s" % callback_error)
                    time.sleep(delay)
        raise RetryExhaustedError(self.config.max_attempts, last_exception)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
) -> Any:
    """
    Decorator for adding retry logic to functions.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        exceptions: Tuple of exceptions that should trigger retries
        on_retry: Optional callback function called on each retry

    Example:
        @retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
        async def api_call():
            # Your API call here
            pass
    """

    def decorator(func: Callable) -> Callable:
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            exceptions=exceptions,
            on_retry=on_retry,
        )
        retry_manager = RetryManager(config)
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await retry_manager.execute_async(func, *args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                return retry_manager.execute_sync(func, *args, **kwargs)

            return sync_wrapper

    return decorator


network_retry = retry(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exceptions=(ConnectionError, TimeoutError, OSError),
)
api_retry = retry(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=1.5,
    exceptions=(ConnectionError, TimeoutError, OSError),
)
database_retry = retry(
    max_attempts=3, base_delay=0.5, max_delay=10.0, exceptions=(ConnectionError, OSError)
)


async def retry_async(func: Callable[..., Awaitable[T]], config: RetryConfig, *args, **kwargs) -> T:
    """Manually retry an async function with the given configuration."""
    return await RetryManager(config).execute_async(func, *args, **kwargs)


def retry_sync(func: Callable[..., T], config: RetryConfig, *args, **kwargs) -> T:
    """Manually retry a sync function with the given configuration."""
    return RetryManager(config).execute_sync(func, *args, **kwargs)
