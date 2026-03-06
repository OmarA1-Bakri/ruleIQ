"""
Unit test conftest — overrides parent fixtures that require DB connections.

Pure unit tests do NOT need database, Redis, or external services.
All dependencies are mocked within individual test files.
"""

import os
import pytest
import asyncio

os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "testing"


# Override the session-scoped autouse fixture from parent conftest
# that tries to connect to the database and skips everything on failure.
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Override parent database setup — unit tests don't need database."""
    yield


@pytest.fixture(scope="session")
def test_db_engine():
    """Override parent database engine — not needed for unit tests."""
    pytest.skip("Database not required for pure unit tests")


@pytest.fixture
def db_session():
    """Override parent db_session — not needed for unit tests."""
    return None


@pytest.fixture
async def async_db_session():
    """Override parent async_db_session — not needed for unit tests."""
    return None


@pytest.fixture(autouse=True)
def auto_mock_external_services():
    """Override parent auto_mock — unit tests handle their own mocking."""
    yield


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def cleanup_uploads(tmp_path):
    """Override parent cleanup_uploads — no file uploads in unit tests."""
    yield tmp_path


@pytest.fixture(autouse=True)
def reset_singleton_instances():
    """Override parent singleton reset — lighter version for unit tests."""
    yield


# Override database fixtures that would otherwise cause skips
@pytest.fixture
def clean_db():
    """Override parent clean_db."""
    yield


@pytest.fixture
def sample_user():
    """Override parent sample_user."""
    return None


@pytest.fixture
def sample_business_profile():
    """Override parent sample_business_profile."""
    return None


@pytest.fixture
def authenticated_user():
    """Override parent authenticated_user."""
    return None


@pytest.fixture
def redis_client():
    """Override parent redis_client."""
    return None


@pytest.fixture
def mock_redis_client():
    """Override parent mock_redis_client."""
    from unittest.mock import AsyncMock
    return AsyncMock()
