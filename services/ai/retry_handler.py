"""

Retry Handler with Exponential Backoff for AI Services

Provides sophisticated retry mechanisms with exponential backoff, jitter,
and model fallback capabilities for resilient AI service operations.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from services.ai.exceptions import (
    AIServiceException,
    CircuitBreakerException,
    ModelOverloadedException,
    ModelRetryExhaustedException,
    ModelTimeoutException,
    ModelUnavailableException,
)


class RetryStrategy(Enum):
    """Available retry strategies"""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retryable_exceptions: List[type] = None
    non_retryable_exceptions: List[type] = None
    enable_model_fallback: bool = True
    fallback_on_timeout: bool = True
    fallback_on_overload: bool = True

    def __post_init__(self) -> None:
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [
                ModelTimeoutException,
                ModelOverloadedException,
                AIServiceException,
            ]
        if self.non_retryable_exceptions is None:
            self.non_retryable_exceptions = [
                ModelUnavailableException,
                CircuitBreakerException,
                ValueError,
                TypeError,
            ]


@dataclass
class RetryAttempt:
    """Information about a retry attempt"""

    attempt_number: int
    model_name: str
    delay: float
    exception: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    success: bool = False

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class RetryHandler:
    """
    Advanced retry handler with exponential backoff and model fallback
    """

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
        self.retry_history: List[RetryAttempt] = []

    def should_retry(self, exception: Exception, attempt_number: int) -> bool:
        """
        Determine if an operation should be retried based on the exception
        and current attempt number.
        """
        if attempt_number >= self.config.max_attempts:
            return False
        for non_retryable in self.config.non_retryable_exceptions:
            if isinstance(exception, non_retryable):
                return False
        for retryable in self.config.retryable_exceptions:
            if isinstance(exception, retryable):
                return True
        return False

    def calculate_delay(self, attempt_number: int) -> float:
        """Calculate delay for the given attempt number"""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * self.config.exponential_base ** (attempt_number - 1)
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt_number
        elif self.config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = self.config.base_delay * self._fibonacci(attempt_number)
        else:
            delay = self.config.base_delay
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay)
        return delay

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number for backoff"""
        if n <= 2:
            return 1
        a, b = 1, 1
        for _ in range(2, n):
            a, b = b, a + b
        return b

    async def retry_async(
        self,
        operation: Callable,
        *args,
        model_name: str = "unknown",
        operation_name: str = "ai_operation",
        **kwargs,
    ) -> Any:
        """
        Execute an async operation with retry logic

        Args:
            operation: Async function to execute
            *args, **kwargs: Arguments for the operation
            model_name: Name of the AI model being used
            operation_name: Name of the operation for logging

        Returns:
            Result of the successful operation

        Raises:
            ModelRetryExhaustedException: If all retry attempts fail
        """
        last_exception = None
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_info = RetryAttempt(
                attempt_number=attempt,
                model_name=model_name,
                delay=0.0 if attempt == 1 else self.calculate_delay(attempt - 1),
            )
            try:
                if attempt > 1:
                    await asyncio.sleep(attempt_info.delay)
                    self.logger.info(
                        "Retrying %s (attempt %s/%s) for model %s after %ss delay"
                        % (
                            operation_name,
                            attempt,
                            self.config.max_attempts,
                            model_name,
                            attempt_info.delay,
                        )
                    )
                attempt_info.start_time = time.time()
                result = await operation(*args, **kwargs)
                attempt_info.end_time = time.time()
                attempt_info.success = True
                self.retry_history.append(attempt_info)
                if attempt > 1:
                    self.logger.info(
                        "Operation %s succeeded on attempt %s for model %s (duration: %ss)"
                        % (operation_name, attempt, model_name, attempt_info.duration)
                    )
                return result
            except Exception as e:
                attempt_info.end_time = time.time()
                attempt_info.exception = e
                last_exception = e
                self.retry_history.append(attempt_info)
                if not self.should_retry(e, attempt):
                    self.logger.error(
                        "Operation %s failed for model %s with non-retryable exception: %s"
                        % (operation_name, model_name, e)
                    )
                    break
                self.logger.warning(
                    "Operation %s failed for model %s (attempt %s/%s): %s"
                    % (operation_name, model_name, attempt, self.config.max_attempts, e)
                )
        raise ModelRetryExhaustedException(
            model_name=model_name,
            attempts=self.config.max_attempts,
            last_error=str(last_exception),
            context={
                "operation": operation_name,
                "retry_history": [
                    {
                        "attempt": a.attempt_number,
                        "delay": a.delay,
                        "duration": a.duration,
                        "exception": str(a.exception) if a.exception else None,
                    }
                    for a in self.retry_history[-self.config.max_attempts :]
                ],
            },
        )

    def retry_sync(
        self,
        operation: Callable,
        *args,
        model_name: str = "unknown",
        operation_name: str = "ai_operation",
        **kwargs,
    ) -> Any:
        """
        Execute a sync operation with retry logic

        Args:
            operation: Function to execute
            *args, **kwargs: Arguments for the operation
            model_name: Name of the AI model being used
            operation_name: Name of the operation for logging

        Returns:
            Result of the successful operation

        Raises:
            ModelRetryExhaustedException: If all retry attempts fail
        """
        last_exception = None
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_info = RetryAttempt(
                attempt_number=attempt,
                model_name=model_name,
                delay=0.0 if attempt == 1 else self.calculate_delay(attempt - 1),
            )
            try:
                if attempt > 1:
                    time.sleep(attempt_info.delay)
                    self.logger.info(
                        "Retrying %s (attempt %s/%s) for model %s after %ss delay"
                        % (
                            operation_name,
                            attempt,
                            self.config.max_attempts,
                            model_name,
                            attempt_info.delay,
                        )
                    )
                attempt_info.start_time = time.time()
                result = operation(*args, **kwargs)
                attempt_info.end_time = time.time()
                attempt_info.success = True
                self.retry_history.append(attempt_info)
                if attempt > 1:
                    self.logger.info(
                        "Operation %s succeeded on attempt %s for model %s (duration: %ss)"
                        % (operation_name, attempt, model_name, attempt_info.duration)
                    )
                return result
            except Exception as e:
                attempt_info.end_time = time.time()
                attempt_info.exception = e
                last_exception = e
                self.retry_history.append(attempt_info)
                if not self.should_retry(e, attempt):
                    self.logger.error(
                        "Operation %s failed for model %s with non-retryable exception: %s"
                        % (operation_name, model_name, e)
                    )
                    break
                self.logger.warning(
                    "Operation %s failed for model %s (attempt %s/%s): %s"
                    % (operation_name, model_name, attempt, self.config.max_attempts, e)
                )
        raise ModelRetryExhaustedException(
            model_name=model_name,
            attempts=self.config.max_attempts,
            last_error=str(last_exception),
            context={
                "operation": operation_name,
                "retry_history": [
                    {
                        "attempt": a.attempt_number,
                        "delay": a.delay,
                        "duration": a.duration,
                        "exception": str(a.exception) if a.exception else None,
                    }
                    for a in self.retry_history[-self.config.max_attempts :]
                ],
            },
        )

    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get statistics about retry operations"""
        if not self.retry_history:
            return {"total_attempts": 0}
        successful_attempts = [a for a in self.retry_history if a.success]
        failed_attempts = [a for a in self.retry_history if not a.success]
        return {
            "total_attempts": len(self.retry_history),
            "successful_attempts": len(successful_attempts),
            "failed_attempts": len(failed_attempts),
            "success_rate": len(successful_attempts) / len(self.retry_history),
            "average_attempts_to_success": sum(a.attempt_number for a in successful_attempts)
            / len(successful_attempts)
            if successful_attempts
            else 0,
            "common_exceptions": self._get_common_exceptions(),
            "average_delay": sum(a.delay for a in self.retry_history) / len(self.retry_history),
            "total_retry_time": sum(a.delay for a in self.retry_history),
        }

    def _get_common_exceptions(self) -> Dict[str, int]:
        """Get count of common exceptions in retry history"""
        exception_counts = {}
        for attempt in self.retry_history:
            if attempt.exception:
                exception_type = type(attempt.exception).__name__
                exception_counts[exception_type] = exception_counts.get(exception_type, 0) + 1
        return dict(sorted(exception_counts.items(), key=lambda x: x[1], reverse=True))

    def clear_history(self) -> None:
        """Clear retry history (useful for testing)"""
        self.retry_history.clear()


def retry_on_failure(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    model_name: str = "unknown",
) -> Any:
    """
    Decorator for automatic retry on function failure

    Example:
        @retry_on_failure(max_attempts=5, base_delay=2.0)
        async def my_ai_operation():
            # ... operation code
    """

    def decorator(func) -> Any:
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs) -> Any:
                config = RetryConfig(
                    max_attempts=max_attempts, base_delay=base_delay, strategy=strategy
                )
                handler = RetryHandler(config)
                return await handler.retry_async(
                    func, *args, model_name=model_name, operation_name=func.__name__, **kwargs
                )

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs) -> Any:
                config = RetryConfig(
                    max_attempts=max_attempts, base_delay=base_delay, strategy=strategy
                )
                handler = RetryHandler(config)
                return handler.retry_sync(
                    func, *args, model_name=model_name, operation_name=func.__name__, **kwargs
                )

            return sync_wrapper

    return decorator


DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3, base_delay=1.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)
AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5, base_delay=0.5, max_delay=30.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)
CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=2, base_delay=2.0, max_delay=10.0, strategy=RetryStrategy.LINEAR_BACKOFF
)
_default_retry_handler: Optional[RetryHandler] = None
_aggressive_retry_handler: Optional[RetryHandler] = None
_conservative_retry_handler: Optional[RetryHandler] = None


def get_retry_handler(config_type: str = "default") -> RetryHandler:
    """Get a configured retry handler instance"""
    global _default_retry_handler, _aggressive_retry_handler, _conservative_retry_handler
    if config_type == "aggressive":
        if _aggressive_retry_handler is None:
            _aggressive_retry_handler = RetryHandler(AGGRESSIVE_RETRY_CONFIG)
        return _aggressive_retry_handler
    elif config_type == "conservative":
        if _conservative_retry_handler is None:
            _conservative_retry_handler = RetryHandler(CONSERVATIVE_RETRY_CONFIG)
        return _conservative_retry_handler
    else:
        if _default_retry_handler is None:
            _default_retry_handler = RetryHandler(DEFAULT_RETRY_CONFIG)
        return _default_retry_handler
