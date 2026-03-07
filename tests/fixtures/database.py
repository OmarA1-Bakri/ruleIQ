"""
Database test fixtures with improved connection management.
Provides reliable database fixtures for all test types.
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Import test connection utilities
from database.test_connection import get_test_db_manager, setup_test_database


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Automatically set up test environment for all tests."""
    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["ENVIRONMENT"] = "testing"

    # Setup test database
    success, error = setup_test_database()
    if not success:
        pytest.skip(f"Test database setup failed: {error}")

    yield

    # Cleanup
    manager = get_test_db_manager()
    manager.cleanup()


@pytest.fixture(scope="session")
def test_db_engine():
    """Provide a shared test database engine."""
    manager = get_test_db_manager()

    # Create or get existing engine
    engine = manager.create_test_engine() if not manager.test_engine else manager.test_engine

    # Verify connection
    if not manager.verify_connection(engine):
        pytest.skip("Database connection failed")

    yield engine

    # Cleanup handled by setup_test_environment


@pytest.fixture(scope="session")
def SessionLocal(test_db_engine):
    """Create a session factory for tests."""
    return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine))


@pytest.fixture
def db_session(SessionLocal, test_db_engine) -> Generator[Session, None, None]:
    """
    Provide a transactional database session for tests.
    Each test runs in a transaction that's rolled back after.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()

    # Create session bound to the connection
    session = SessionLocal(bind=connection)

    # Setup nested transaction for savepoints
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            nonlocal nested
            nested = connection.begin_nested()

    yield session

    # Rollback and cleanup
    session.close()
    SessionLocal.remove()
    transaction.rollback()
    connection.close()


@pytest.fixture
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session for async tests.
    """
    manager = get_test_db_manager()
    db_url = manager.get_test_db_url()

    # Convert to async URL
    if "+asyncpg" not in db_url:
        if "+psycopg2" in db_url:
            db_url = db_url.replace("+psycopg2", "+asyncpg")
        elif "postgresql://" in db_url and "+" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create async engine
    async_engine = create_async_engine(
        db_url, echo=False, pool_size=5, max_overflow=10, pool_pre_ping=True
    )

    # Create session
    async_session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()

    await async_engine.dispose()


@pytest.fixture
def clean_db(db_session):
    """
    Ensure a clean database state for tests that need it.
    Deletes all data from tables without dropping them.
    """
    # Import all models to ensure they're registered
    from database import User, BusinessProfile, ComplianceFramework, AssessmentSession, EvidenceItem

    # Clear data in reverse dependency order
    db_session.query(EvidenceItem).delete()
    db_session.query(AssessmentSession).delete()
    db_session.query(ComplianceFramework).delete()
    db_session.query(BusinessProfile).delete()
    db_session.query(User).delete()
    db_session.commit()

    yield db_session

    # Data will be rolled back by db_session fixture


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for tests."""
    from database import User
    from utils.auth import get_password_hash

    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("TestPassword123!"),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def sample_business_profile(db_session, sample_user):
    """Create a sample business profile for tests."""
    from database import BusinessProfile

    profile = BusinessProfile(
        user_id=sample_user.id,
        company_name="Test Company Inc.",
        industry="Technology",
        size="Medium",
        employee_count="100-500",
        location="United States",
        existing_frameworks=["ISO 27001"],
        planned_frameworks=["SOC 2", "GDPR"],
        handles_personal_data=True,
        processes_payments=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    return profile


@pytest.fixture
def authenticated_user(db_session, sample_user):
    """Provide an authenticated user context."""
    from utils.auth import create_access_token

    token = create_access_token(data={"sub": sample_user.email})

    return {"user": sample_user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


# Redis fixtures
@pytest.fixture
def redis_client():
    """Provide a Redis client for tests."""
    import redis
    from database.test_connection import get_test_db_manager

    manager = get_test_db_manager()
    redis_url = manager.get_redis_test_url()

    # Parse URL and create client
    import re

    pattern = r"redis://(?:([^:]+):([^@]+)@)?([^:/]+)(?::(\d+))?(?:/(\d+))?"
    match = re.match(pattern, redis_url)

    if not match:
        pytest.skip(f"Could not parse Redis URL: {redis_url}")

    _, _, host, port, db = match.groups()

    client = redis.Redis(host=host, port=int(port or 6379), db=int(db or 0), decode_responses=True)

    # Test connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available")

    yield client

    # Clean up keys created during test
    client.flushdb()


@pytest.fixture
def mock_redis_client(monkeypatch):
    """Provide a mock Redis client that doesn't require a real Redis server."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    mock.exists.return_value = False
    mock.expire.return_value = True
    mock.ttl.return_value = -1
    mock.ping.return_value = True
    mock.flushdb.return_value = True

    # Store data in memory for more realistic mocking
    mock._data = {}

    def mock_set(key, value, ex=None, px=None, nx=False, xx=False):
        if nx and key in mock._data:
            return False
        if xx and key not in mock._data:
            return False
        mock._data[key] = value
        return True

    def mock_get(key):
        return mock._data.get(key)

    def mock_delete(key):
        if key in mock._data:
            del mock._data[key]
            return 1
        return 0

    def mock_exists(key):
        return key in mock._data

    mock.set = mock_set
    mock.get = mock_get
    mock.delete = mock_delete
    mock.exists = mock_exists

    return mock
