"""
Unit test configuration for AI domain tests.

These are pure unit tests with mocked dependencies - no database required.
"""

import pytest
import asyncio


# Override the database setup fixture from parent conftest
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Override parent database setup - unit tests don't need database."""
    import os

    os.environ["TESTING"] = "true"
    os.environ["ENVIRONMENT"] = "testing"
    # No database setup needed - all dependencies are mocked
    yield
    # No cleanup needed


@pytest.fixture(scope="session")
def test_db_engine():
    """Override parent database engine - not needed for unit tests."""
    pytest.skip("Database not required for pure unit tests")


@pytest.fixture
def db_session():
    """Override parent db_session - not needed for unit tests."""
    return None


@pytest.fixture
async def async_db_session():
    """Override parent async_db_session - not needed for unit tests."""
    return None


@pytest.fixture(autouse=True)
def auto_mock_external_services():
    """Override parent auto_mock - these unit tests handle their own mocking."""
    # Tests have their own mock fixtures, don't need global auto-mocking
    yield


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Configure anyio to only use asyncio (skip trio tests)
def pytest_configure(config):
    """Configure pytest to only run asyncio backend."""
    # Set anyio backends to asyncio only
    if not hasattr(config.option, "anyio_backends"):
        config.option.anyio_backends = []
    config.option.anyio_backends = ["asyncio"]


@pytest.fixture(scope="session")
def anyio_backend():
    """Force anyio to use asyncio backend only."""
    return "asyncio"
