"""

Test helper utilities for preventing hanging tests and ensuring proper cleanup.
Implementation following test-first approach per ALWAYS_READ_FIRST protocol.
"""

import asyncio
import functools
import os
import signal
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, Dict, TypeVar
from urllib.parse import urlparse
import pytest

T = TypeVar("T")


# Async timeout handling
async def async_with_timeout(coro, timeout: float):
    """
    Execute an async operation with a timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds

    Returns:
        Result of the coroutine

    Raises:
        asyncio.TimeoutError: If operation exceeds timeout
    """
    return await asyncio.wait_for(coro, timeout=timeout)


def sync_with_timeout(func: Callable, timeout: float, *args, **kwargs):
    """
    Execute a synchronous function with a timeout.

    Args:
        func: Function to execute
        timeout: Timeout in seconds
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of the function

    Raises:
        TimeoutError: If operation exceeds timeout
    """
    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError(f"Operation timed out after {timeout} seconds")

    if exception[0]:
        raise exception[0]

    return result[0]


# Connection cleanup decorators
def with_db_cleanup(async_func):
    """
    Decorator to ensure database connections are cleaned up.

    Args:
        async_func: Async function that uses a database connection

    Returns:
        Wrapped function with cleanup
    """

    @functools.wraps(async_func)
    async def wrapper(conn, *args, **kwargs):
        try:
            return await async_func(conn, *args, **kwargs)
        finally:
            if hasattr(conn, "close"):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()

    return wrapper


def with_redis_cleanup(async_func):
    """
    Decorator to ensure Redis connections are cleaned up.

    Args:
        async_func: Async function that uses a Redis connection

    Returns:
        Wrapped function with cleanup
    """

    @functools.wraps(async_func)
    async def wrapper(redis_client, *args, **kwargs):
        try:
            return await async_func(redis_client, *args, **kwargs)
        finally:
            if hasattr(redis_client, "close"):
                if asyncio.iscoroutinefunction(redis_client.close):
                    await redis_client.close()
                else:
                    redis_client.close()

    return wrapper


async def cleanup_all_connections(connections: Dict[str, Any]):
    """
    Clean up multiple connections.

    Args:
        connections: Dictionary of connection objects
    """
    for name, conn in connections.items():
        if conn and hasattr(conn, "close"):
            try:
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()
            except Exception as e:
                print(f"Error closing {name}: {e}")


# Test timeout decorator
def with_test_timeout(seconds: int):
    """
    Decorator to add timeout to test functions.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated test function with timeout
    """

    def decorator(test_func):
        # Add pytest timeout mark
        test_func = pytest.mark.timeout(seconds)(test_func)

        if asyncio.iscoroutinefunction(test_func):

            @functools.wraps(test_func)
            async def async_wrapper(*args, **kwargs):
                return await async_with_timeout(
                    test_func(*args, **kwargs),
                    timeout=seconds,
                )

            return async_wrapper
        else:

            @functools.wraps(test_func)
            def sync_wrapper(*args, **kwargs):
                return sync_with_timeout(
                    test_func,
                    timeout=seconds,
                    *args,
                    **kwargs,
                )

            return sync_wrapper

    return decorator


# Smart mock creation
def create_smart_mock_ai_client():
    """
    Create a mock AI client that returns context-specific responses.

    Returns:
        Mock AI client with intelligent responses
    """
    from unittest.mock import MagicMock

    def generate_content(prompt: str):
        response = MagicMock()

        # Return context-specific responses based on prompt
        prompt_lower = prompt.lower()

        if "gdpr" in prompt_lower:
            response.text = (
                "GDPR (General Data Protection Regulation) is a comprehensive "
                "data protection law that regulates how personal data is collected, "
                "processed, and stored.",
            )
        elif "soc2" in prompt_lower or "soc 2" in prompt_lower:
            response.text = (
                "SOC 2 is a compliance framework for service organizations "
                "that store customer data in the cloud, focusing on five "
                "trust service criteria.",
            )
        elif "compliance" in prompt_lower:
            response.text = (
                "Compliance refers to conforming to rules, regulations, "
                "standards, and laws relevant to your business processes.",
            )
        else:
            response.text = f"Response for: {prompt[:50]}"

        return response

    mock_client = MagicMock()
    mock_client.generate_content = generate_content
    mock_client.generate_content_async = lambda p: asyncio.coroutine(generate_content)(p)

    return mock_client


def create_smart_mock_openai():
    """
    Create a mock OpenAI client with intelligent responses.

    Returns:
        Mock OpenAI client
    """
    from unittest.mock import MagicMock

    def create_completion(messages, **kwargs):
        last_message = messages[-1]["content"] if messages else ""

        response = MagicMock()
        response.choices = [MagicMock()]

        # Generate context-aware response
        if "compliance" in last_message.lower():
            content = "Compliance requirements include regulatory adherence and documentation."
        elif "gdpr" in last_message.lower():
            content = "GDPR compliance requires data protection measures."
        else:
            content = f"Response to: {last_message[:50]}"

        response.choices[0].message.content = content
        return response

    mock_client = MagicMock()
    mock_client.chat.completions.create = create_completion

    return mock_client


# Environment-aware configuration
def get_redis_config() -> Dict[str, Any]:
    """
    Get Redis configuration from environment.

    Returns:
        Redis configuration dictionary
    """
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": int(os.getenv("REDIS_DB", "0")),
    }


def get_postgres_config() -> Dict[str, Any]:
    """
    Get PostgreSQL configuration from environment.

    Returns:
        PostgreSQL configuration dictionary
    """
    database_url = os.getenv("DATABASE_URL", "")

    if database_url:
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/") if parsed.path else "postgres",
            "user": parsed.username,
            "password": parsed.password,
        }

    return {
        "host": "localhost",
        "port": 5432,
        "database": "postgres",
        "user": "postgres",
        "password": "postgres",
    }


# Context managers for test isolation
@asynccontextmanager
async def isolated_test_context():
    """
    Provide an isolated context for test execution.

    Yields:
        Test context with cleanup guaranteed
    """
    connections = {}

    try:
        yield connections
    finally:
        await cleanup_all_connections(connections)


@contextmanager
def timeout_context(seconds: float):
    """
    Context manager for timeout handling.

    Args:
        seconds: Timeout in seconds

    Yields:
        None

    Raises:
        TimeoutError: If context exceeds timeout
    """

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
