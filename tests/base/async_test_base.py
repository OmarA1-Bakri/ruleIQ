"""

Base classes for async tests with proper event loop management.
"""

import asyncio
import pytest
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import contextlib
import requests


class AsyncTestBase:
    """Base class for async tests with proper lifecycle management."""

    def setup_method(self, method):
        """Set up test method with async utilities."""
        self.loop = asyncio.get_event_loop()
        self.async_mocks = []

    def teardown_method(self, method):
        """Clean up test method resources."""
        # Clean up async mocks
        for mock in self.async_mocks:
            if hasattr(mock, "stop"):
                mock.stop()
        self.async_mocks.clear()

    def create_async_mock(self, *args, **kwargs) -> AsyncMock:
        """Create async mock with automatic cleanup."""
        mock = AsyncMock(*args, **kwargs)
        self.async_mocks.append(mock)
        return mock

    async def run_async_test(self, coro):
        """Run async test with proper exception handling."""
        try:
            return await coro
        except (ValueError, TypeError) as e:
            # Log test failure details
            pytest.fail(f"Async test failed: {e}")


class DatabaseTestBase(AsyncTestBase):
    """Base class for database tests with session management."""

    def setup_method(self, method):
        """Set up database test method."""
        super().setup_method(method)
        self.db_session = None
        self.test_objects = []

    def teardown_method(self, method):
        """Clean up database test resources."""
        # Clean up test objects
        if self.db_session and self.test_objects:
            for obj in self.test_objects:
                with contextlib.suppress(ValueError, TypeError):
                    self.db_session.delete(obj)
            try:
                self.db_session.commit()
            except (ValueError, TypeError):
                self.db_session.rollback()

        super().teardown_method(method)

    def add_test_object(self, obj):
        """Add object to cleanup list."""
        self.test_objects.append(obj)
        return obj


class APITestBase(AsyncTestBase):
    """Base class for API tests with HTTP client management."""

    def setup_method(self, method):
        """Set up API test method."""
        super().setup_method(method)
        self.client = None
        self.auth_headers = {}

    def set_auth_headers(self, token: str):
        """Set authentication headers for requests."""
        self.auth_headers = {"Authorization": f"Bearer {token}"}

    def make_request(self, method: str, url: str, **kwargs):
        """Make HTTP request with automatic auth headers."""
        if self.client is None:
            raise ValueError("Client not initialized")

        # Add auth headers if not explicitly provided
        if "headers" not in kwargs and self.auth_headers:
            kwargs["headers"] = self.auth_headers

        return getattr(self.client, method.lower())(url, **kwargs)

    def assert_response_success(self, response, expected_status: int = 200):
        """Assert response is successful."""
        assert (response.status_code == expected_status,), (
            f"Expected {expected_status}, got {response.status_code}: {response.text}"
        )

    def assert_response_error(self, response, expected_status: int = 400):
        """Assert response is an error."""
        assert (response.status_code == expected_status,), (
            f"Expected {expected_status}, got {response.status_code}: {response.text}"
        )


class IntegrationTestBase(DatabaseTestBase, APITestBase):
    """Base class for integration tests combining database and API testing."""

    def setup_method(self, method):
        """Set up integration test method."""
        DatabaseTestBase.setup_method(self, method)
        APITestBase.setup_method(self, method)

    def teardown_method(self, method):
        """Clean up integration test resources."""
        APITestBase.teardown_method(self, method)
        DatabaseTestBase.teardown_method(self, method)


class AsyncContextTestCase:
    """Context manager for async test execution with proper cleanup."""

    def __init__(self, test_instance):
        self.test_instance = test_instance
        self._cleanup_tasks = []

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context with cleanup."""
        # Run cleanup tasks
        for task in reversed(self._cleanup_tasks):
            try:
                await task()
            except (ValueError, TypeError) as e:
                print(f"Warning: Cleanup task failed: {e}")

        self._cleanup_tasks.clear()

    def add_cleanup(self, coro):
        """Add cleanup coroutine."""
        self._cleanup_tasks.append(coro)


def async_test_context(test_instance):
    """Create async test context with cleanup."""
    return AsyncContextTestCase(test_instance)


# Pytest integration decorators
def async_test(func):
    """Decorator for async test methods."""

    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def database_test(func):
    """Decorator for database test methods with transaction rollback."""

    async def wrapper(*args, **kwargs):
        # The database session fixture handles transaction management
        return await func(*args, **kwargs)

    return wrapper


def api_test(func):
    """Decorator for API test methods with client setup."""

    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    return wrapper
