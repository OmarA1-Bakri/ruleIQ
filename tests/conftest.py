"""
Pytest configuration and fixtures for the test suite.
Task 799f27b3: Properly configured test fixtures and mocks.
"""

# Setup test environment before anything else
import os

# Load .env.test if it exists (for Neon test database configuration)
from pathlib import Path
from dotenv import load_dotenv

env_test_path = Path(__file__).parent.parent / ".env.test"
if env_test_path.exists():
    load_dotenv(env_test_path, override=True)
    print(f"✓ Loaded environment from {env_test_path}")

os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "testing"

# Load test environment configuration
from tests.setup_test_env import setup_test_database_urls

setup_test_database_urls()

import pytest
import asyncio
from typing import Generator, Optional
from unittest.mock import MagicMock, patch
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from contextlib import contextmanager

# Import test database fixtures
from tests.fixtures.database import (
    setup_test_environment,
    test_db_engine,
    SessionLocal,
    db_session,
    async_db_session,
    clean_db,
    sample_user,
    sample_business_profile,
    authenticated_user,
    redis_client,
    mock_redis_client,
)

# Import external service mocks
from tests.fixtures.external_services import (
    mock_openai,
    mock_anthropic,
    mock_google_ai,
    mock_sendgrid,
    mock_smtp,
    mock_s3,
    mock_secrets_manager,
    mock_cloudwatch,
    mock_stripe,
    mock_google_oauth,
    mock_neo4j,
    mock_elasticsearch,
    mock_sentry,
    mock_datadog,
    mock_http_client,
    mock_webhook_client,
    mock_celery_task,
    mock_file_storage,
    auto_mock_external_services,
)

# Import and activate the service proxy BEFORE any tests run
from tests.mock_service_proxy import setup_test_services

setup_test_services()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm():
    """Provide a mock LLM for testing without API calls."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="Mock response")
    mock.ainvoke.return_value = MagicMock(content="Mock async response")
    return mock


@pytest.fixture
def mock_ai_client():
    """Provide a mock AI client for testing without API calls."""
    from utils.test_helpers import create_smart_mock_ai_client

    return create_smart_mock_ai_client()


@pytest.fixture
def mock_openai_client():
    """Provide a mock OpenAI client for testing."""
    from utils.test_helpers import create_smart_mock_openai

    return create_smart_mock_openai()


@pytest.fixture
def mock_anthropic_client():
    """Provide a mock Anthropic client for testing."""
    mock = MagicMock()
    mock.messages.create = MagicMock()
    mock.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Mock Anthropic response")],
    )
    return mock


@pytest.fixture
def mock_neo4j_session():
    """Provide a mock Neo4j session for testing."""
    mock = MagicMock()
    mock.run.return_value = MagicMock(data=MagicMock(return_value=[]))
    mock.close = MagicMock()
    return mock


@pytest.fixture
def postgres_test_url():
    """Get PostgreSQL test connection URL."""
    # Use the configured test database URL
    return os.getenv(
        "TEST_DATABASE_URL", "postgresql://test_user:test_password@localhost:5433/ruleiq_test"
    )


@pytest.fixture
def postgres_checkpointer(postgres_test_url):
    """
    Create a PostgreSQL checkpointer for LangGraph state persistence.

    This fixture handles:
    - Connection setup with proper parameters
    - Table creation if needed
    - Cleanup after tests
    """
    try:
        # Create connection with proper settings for PostgresSaver
        conn = psycopg.connect(
            postgres_test_url,
            autocommit=True,  # Required for PostgresSaver
            row_factory=dict_row,  # Required for PostgresSaver
        )

        # Create checkpointer
        checkpointer = PostgresSaver(conn)

        # Setup tables (idempotent - won't error if tables exist)
        checkpointer.setup()

        yield checkpointer

        # Cleanup: Close connection
        conn.close()

    except Exception as e:
        pytest.skip(f"PostgreSQL checkpointer not available: {e}")


@pytest.fixture
def postgres_connection(postgres_test_url):
    """
    Provide a raw PostgreSQL connection for tests that need direct DB access.
    """
    try:
        conn = psycopg.connect(postgres_test_url)
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL connection failed: {e}")


@pytest.fixture
def clean_test_db(postgres_connection):
    """
    Ensure a clean database state for each test.
    Drops and recreates checkpointing tables.
    """
    with postgres_connection.cursor() as cursor:
        # Drop existing checkpointing tables if they exist
        cursor.execute(
            """
            DROP TABLE IF EXISTS checkpoints CASCADE;
            DROP TABLE IF EXISTS checkpoint_blobs CASCADE;
            DROP TABLE IF EXISTS checkpoint_metadata CASCADE;
        """,
        )
        postgres_connection.commit()

    yield

    # Cleanup after test
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            DROP TABLE IF EXISTS checkpoints CASCADE;
            DROP TABLE IF EXISTS checkpoint_blobs CASCADE;
            DROP TABLE IF EXISTS checkpoint_metadata CASCADE;
        """,
        )
        postgres_connection.commit()


@contextmanager
def temporary_env_var(key: str, value: str):
    """
    Temporarily set an environment variable for testing.
    """
    old_value = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_value


# Mark slow tests
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line(
        "markers",
        "requires_db: mark test as requiring database connection",
    )
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "external: mark test as requiring external services")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def assert_api_response_security(response):
    """Assert API response has proper security headers."""
    # Check for security headers
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    # Additional security checks can be added here
    pass


@pytest.fixture
def client():
    """Create a test client for FastAPI application."""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client, authenticated_headers):
    """Create an authenticated test client."""
    client.headers.update(authenticated_headers)
    return client


@pytest.fixture
def authenticated_headers(sample_user, db_session):
    """Create authenticated headers for testing."""
    from utils.auth import create_access_token

    # Create a real JWT token for the sample user
    token = create_access_token(data={"sub": sample_user.email})

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def admin_headers(db_session):
    """Create admin authenticated headers for testing."""
    from database import User
    from utils.auth import get_password_hash, create_access_token

    # Create admin user
    admin_user = User(
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=get_password_hash("AdminPassword123!"),
        is_active=True,
        is_verified=True,
        is_admin=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    # Create token
    token = create_access_token(data={"sub": admin_user.email, "admin": True})

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def sample_user_data():
    """Create sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "company": "Test Company",
        "role": "compliance_manager",
    }


@pytest.fixture
def sample_framework_data():
    """Create sample compliance framework data for testing."""
    return {
        "name": "GDPR",
        "description": "General Data Protection Regulation",
        "version": "2016/679",
        "categories": ["Privacy", "Data Protection"],
        "requirements": [
            {
                "id": "GDPR-1",
                "title": "Lawful basis for processing",
                "description": "Must have a lawful basis for processing personal data",
            },
            {
                "id": "GDPR-2",
                "title": "Data minimization",
                "description": "Only process data that is necessary",
            },
        ],
    }


@pytest.fixture
def sample_assessment_data():
    """Create sample assessment data for testing."""
    return {
        "framework_id": 1,
        "name": "Q1 2024 GDPR Assessment",
        "description": "Quarterly GDPR compliance assessment",
        "status": "in_progress",
        "responses": {},
    }


# API testing fixtures
@pytest.fixture
def api_headers():
    """Basic API headers for testing."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": "test-request-id",
    }


@pytest.fixture
def multipart_headers():
    """Headers for multipart form data."""
    return {
        "Accept": "application/json",
        "X-Request-ID": "test-request-id",
        # Content-Type will be set automatically for multipart
    }


# Async fixtures
@pytest.fixture
async def async_client():
    """Create an async test client for FastAPI application."""
    from httpx import AsyncClient
    from main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def async_authenticated_client(async_client, authenticated_headers):
    """Create an authenticated async test client."""
    async_client.headers.update(authenticated_headers)
    return async_client


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_uploads(tmp_path):
    """Ensure upload directory is clean for each test."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)

    # Set upload directory for tests
    os.environ["UPLOAD_DIRECTORY"] = str(upload_dir)

    yield upload_dir

    # Cleanup after test
    import shutil

    if upload_dir.exists():
        shutil.rmtree(upload_dir)


@pytest.fixture(autouse=True)
def reset_singleton_instances():
    """Reset singleton instances between tests."""
    # Reset any singleton patterns used in the codebase
    yield

    # Clear any module-level caches
    import sys

    modules_to_reload = [
        m for m in sys.modules if m.startswith("agents.") or m.startswith("utils.")
    ]
    for module in modules_to_reload:
        if hasattr(sys.modules[module], "_instance"):
            delattr(sys.modules[module], "_instance")


# Re-export all fixtures for backward compatibility
__all__ = [
    # Database fixtures
    "setup_test_environment",
    "test_db_engine",
    "SessionLocal",
    "db_session",
    "async_db_session",
    "clean_db",
    "sample_user",
    "sample_business_profile",
    "authenticated_user",
    "redis_client",
    "mock_redis_client",
    # External service mocks
    "mock_openai",
    "mock_anthropic",
    "mock_google_ai",
    "mock_sendgrid",
    "mock_smtp",
    "mock_s3",
    "mock_secrets_manager",
    "mock_cloudwatch",
    "mock_stripe",
    "mock_google_oauth",
    "mock_neo4j",
    "mock_elasticsearch",
    "mock_sentry",
    "mock_datadog",
    "mock_http_client",
    "mock_webhook_client",
    "mock_celery_task",
    "mock_file_storage",
    "auto_mock_external_services",
    # Test fixtures
    "event_loop",
    "mock_llm",
    "mock_ai_client",
    "mock_openai_client",
    "mock_anthropic_client",
    "mock_neo4j_session",
    "postgres_test_url",
    "postgres_checkpointer",
    "postgres_connection",
    "clean_test_db",
    "temporary_env_var",
    "client",
    "authenticated_client",
    "authenticated_headers",
    "admin_headers",
    "sample_user_data",
    "sample_framework_data",
    "sample_assessment_data",
    "api_headers",
    "multipart_headers",
    "async_client",
    "async_authenticated_client",
    "cleanup_uploads",
    "reset_singleton_instances",
]
