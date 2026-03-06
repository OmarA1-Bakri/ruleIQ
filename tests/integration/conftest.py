"""
Integration test configuration and fixtures.
Provides comprehensive setup for integration testing including database transactions,
external service mocking, and parallel execution support.
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator, Optional
from contextlib import asynccontextmanager
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import MagicMock, patch
import fakeredis
import time

# Import base fixtures
from tests.conftest import *
from tests.fixtures.database import get_test_db_manager
from tests.fixtures.external_services import *


# ==================== Database Transaction Management ====================


@pytest.fixture(scope="function")
def integration_db_session(test_db_engine) -> Generator[Session, None, None]:
    """
    Provide a database session with automatic rollback for integration tests.
    Each test runs in its own transaction that's rolled back after completion.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()

    # Create session factory bound to this connection
    SessionMaker = sessionmaker(bind=connection)
    session = SessionMaker()

    # Setup savepoint for nested transactions
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        """Restart savepoint after each nested transaction."""
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        # Rollback all changes
        session.close()
        if nested.is_active:
            nested.rollback()
        transaction.rollback()
        connection.close()


@pytest.fixture
async def async_integration_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session with automatic rollback for async integration tests.
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
        db_url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True
    )

    # Create session factory
    async_session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_engine.begin() as conn:
        # Start transaction
        async with async_session_factory(bind=conn) as session:
            async with session.begin():
                yield session
                # Automatic rollback on context exit

    await async_engine.dispose()


# ==================== External Service Mocks ====================


@pytest.fixture
def mock_all_external_services():
    """
    Comprehensively mock all external services for integration tests.
    """
    mocks = {}

    # Mock Stripe
    with patch("stripe.Customer") as mock_customer:
        mock_customer.create.return_value = MagicMock(id="cus_test123", email="test@example.com")
        mock_customer.retrieve.return_value = MagicMock(
            id="cus_test123", subscriptions=MagicMock(data=[])
        )
        mocks["stripe_customer"] = mock_customer

    # Mock SendGrid
    with patch("sendgrid.SendGridAPIClient") as mock_sendgrid:
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = MagicMock(
            status_code=202, body="", headers={"X-Message-Id": "test-msg-id"}
        )
        mock_sendgrid.return_value = mock_sg_instance
        mocks["sendgrid"] = mock_sendgrid

    # Mock AWS S3
    with patch("boto3.client") as mock_boto:
        s3_mock = MagicMock()
        s3_mock.put_object.return_value = {"ETag": '"test-etag"'}
        s3_mock.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"test content"),
            "ContentType": "application/pdf",
        }
        s3_mock.generate_presigned_url.return_value = "https://s3.test.url"

        def boto_client_factory(service_name, **kwargs):
            if service_name == "s3":
                return s3_mock
            return MagicMock()

        mock_boto.side_effect = boto_client_factory
        mocks["boto"] = mock_boto
        mocks["s3"] = s3_mock

    # Mock OpenAI
    with patch("openai.OpenAI") as mock_openai_class:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(message=MagicMock(content="Test AI response"), finish_reason="stop")
            ],
            usage=MagicMock(total_tokens=100),
        )
        mock_openai_class.return_value = mock_openai
        mocks["openai"] = mock_openai

    # Mock Redis with fakeredis
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    with patch("redis.Redis", return_value=fake_redis):
        mocks["redis"] = fake_redis

    # Mock Celery tasks
    with patch("celery.Task.delay") as mock_delay:
        mock_delay.return_value = MagicMock(
            id="test-task-id", state="SUCCESS", result={"status": "completed"}
        )
        mocks["celery"] = mock_delay

    yield mocks

    # Cleanup
    if "redis" in mocks:
        mocks["redis"].flushall()


# ==================== API Testing Fixtures ====================


@pytest.fixture
def integration_client(integration_db_session, mock_all_external_services):
    """
    Create a test client with database transaction and external service mocking.
    """
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    # Override database dependency
    def override_get_db():
        try:
            yield integration_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


@pytest.fixture
async def async_integration_client(async_integration_db_session, mock_all_external_services):
    """
    Create an async test client with database transaction and external service mocking.
    """
    from httpx import AsyncClient
    from main import app
    from database import get_db

    # Override database dependency
    async def override_get_db():
        try:
            yield async_integration_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


# ==================== Authentication Fixtures ====================


@pytest.fixture
def integration_auth_headers(integration_db_session):
    """
    Create authenticated headers with a real user in the test database.
    """
    from database import User
    from utils.auth import create_access_token, get_password_hash

    # Create test user
    user = User(
        email="integration@test.com",
        full_name="Integration Test User",
        hashed_password=get_password_hash("TestPassword123!"),
        is_active=True,
        is_verified=True,
    )
    integration_db_session.add(user)
    integration_db_session.commit()

    # Create JWT token
    token = create_access_token(data={"sub": user.email})

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Request-ID": "integration-test",
    }


@pytest.fixture
def integration_admin_headers(integration_db_session):
    """
    Create admin authenticated headers for integration tests.
    """
    from database import User
    from utils.auth import create_access_token, get_password_hash

    # Create admin user
    admin = User(
        email="admin@integration.test",
        full_name="Admin Integration User",
        hashed_password=get_password_hash("AdminPassword123!"),
        is_active=True,
        is_verified=True,
        is_admin=True,
    )
    integration_db_session.add(admin)
    integration_db_session.commit()

    # Create JWT token with admin claim
    token = create_access_token(data={"sub": admin.email, "admin": True})

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Request-ID": "admin-integration-test",
    }


# ==================== Performance Testing Fixtures ====================


@pytest.fixture
def performance_monitor():
    """
    Monitor performance metrics during integration tests.
    """

    class PerformanceMonitor:
        def __init__(self):
            self.metrics = {}
            self.start_time = None
            self.end_time = None

        def start(self, operation: str):
            """Start timing an operation."""
            self.metrics[operation] = {"start": time.time()}

        def end(self, operation: str):
            """End timing an operation."""
            if operation in self.metrics:
                self.metrics[operation]["end"] = time.time()
                self.metrics[operation]["duration"] = (
                    self.metrics[operation]["end"] - self.metrics[operation]["start"]
                )

        def get_duration(self, operation: str) -> float:
            """Get duration of an operation in seconds."""
            return self.metrics.get(operation, {}).get("duration", 0)

        def assert_performance(self, operation: str, max_duration: float):
            """Assert that an operation completed within the specified time."""
            duration = self.get_duration(operation)
            assert duration <= max_duration, (
                f"Operation '{operation}' took {duration:.2f}s, expected <= {max_duration}s"
            )

        def get_report(self) -> dict:
            """Get a performance report."""
            return {
                op: {
                    "duration": data.get("duration", 0),
                    "status": "completed" if "duration" in data else "incomplete",
                }
                for op, data in self.metrics.items()
            }

    return PerformanceMonitor()


# ==================== Data Fixtures ====================


@pytest.fixture
def sample_integration_data(integration_db_session):
    """
    Create comprehensive sample data for integration tests.
    """
    from database import User, BusinessProfile, ComplianceFramework, AssessmentSession
    from utils.auth import get_password_hash
    import json

    # Create users
    users = []
    for i in range(3):
        user = User(
            email=f"user{i}@integration.test",
            full_name=f"Test User {i}",
            hashed_password=get_password_hash(f"Password{i}123!"),
            is_active=True,
            is_verified=True,
        )
        integration_db_session.add(user)
        users.append(user)

    integration_db_session.commit()

    # Create business profiles
    profiles = []
    for user in users:
        profile = BusinessProfile(
            user_id=user.id,
            company_name=f"{user.full_name} Company",
            industry="Technology",
            size="Medium",
            employee_count="100-500",
            location="United States",
        )
        integration_db_session.add(profile)
        profiles.append(profile)

    integration_db_session.commit()

    # Create compliance frameworks
    frameworks = []
    framework_data = [
        ("GDPR", "General Data Protection Regulation"),
        ("SOC 2", "Service Organization Control 2"),
        ("ISO 27001", "Information Security Management"),
    ]

    for name, description in framework_data:
        framework = ComplianceFramework(
            name=name,
            description=description,
            version="latest",
            requirements=json.dumps(
                [
                    {"id": f"{name}-1", "title": f"{name} Requirement 1"},
                    {"id": f"{name}-2", "title": f"{name} Requirement 2"},
                ]
            ),
        )
        integration_db_session.add(framework)
        frameworks.append(framework)

    integration_db_session.commit()

    # Create assessment sessions
    assessments = []
    for user, framework in zip(users, frameworks):
        assessment = AssessmentSession(
            user_id=user.id,
            framework_id=framework.id,
            status="in_progress",
            responses=json.dumps({}),
        )
        integration_db_session.add(assessment)
        assessments.append(assessment)

    integration_db_session.commit()

    return {
        "users": users,
        "profiles": profiles,
        "frameworks": frameworks,
        "assessments": assessments,
    }


# ==================== Parallel Execution Support ====================


@pytest.fixture(scope="session")
def worker_id(request):
    """
    Get the worker ID for parallel test execution.
    Returns 'master' for non-parallel execution.
    """
    return getattr(request.config, "workerinput", {}).get("workerid", "master")


@pytest.fixture
def unique_test_id(worker_id, request):
    """
    Generate a unique ID for each test in parallel execution.
    """
    test_name = request.node.name
    return f"{worker_id}_{test_name}_{time.time()}"


@pytest.fixture
def isolated_test_db(worker_id):
    """
    Create an isolated database schema for parallel test execution.
    """

    manager = get_test_db_manager()
    base_url = manager.get_test_db_url()

    # Create a schema name based on worker ID
    schema_name = f"test_{worker_id}_{int(time.time())}"

    # Create engine without specifying schema
    engine = create_engine(base_url)

    # Create schema
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        conn.commit()

    # Update search path to use the new schema
    schema_url = f"{base_url}?options=-csearch_path={schema_name}"
    schema_engine = create_engine(schema_url)

    yield schema_engine

    # Cleanup: Drop schema
    with engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        conn.commit()

    engine.dispose()
    schema_engine.dispose()


# ==================== Test Markers ====================


def pytest_configure(config):
    """Register integration test markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow_integration: mark test as slow integration test")
    config.addinivalue_line(
        "markers", "requires_external: mark test as requiring external service mocks"
    )
    config.addinivalue_line("markers", "transaction: mark test as requiring database transaction")


# ==================== Test Utilities ====================


def assert_api_success(response, expected_status: int = 200):
    """Assert API response is successful."""
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
    )
    return response.json() if response.text else None


def assert_database_changes(session: Session, model, expected_count: int):
    """Assert expected number of records in database."""
    actual_count = session.query(model).count()
    assert actual_count == expected_count, (
        f"Expected {expected_count} {model.__name__} records, found {actual_count}"
    )


async def assert_async_operation(coro, timeout: float = 5.0):
    """Assert an async operation completes within timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        pytest.fail(f"Async operation timed out after {timeout}s")
