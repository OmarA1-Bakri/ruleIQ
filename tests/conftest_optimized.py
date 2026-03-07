"""
Optimized test fixtures for fast test execution.

This module provides performance-optimized fixtures using:
- In-memory SQLite for unit tests
- Transaction rollback for integration tests
- Session-scoped caching for expensive resources
"""

import pytest
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import time
from functools import lru_cache
from typing import Generator, Dict, Any

# Import base models
from database import Base

# Performance monitoring
test_durations = {}


@pytest.fixture(scope="session")
def sqlite_engine():
    """
    In-memory SQLite engine for unit tests.

    Uses StaticPool to maintain single connection across threads,
    ensuring database persists throughout test session.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Set to True for debugging
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(engine)

    return engine


@pytest.fixture(scope="function")
def fast_db_session(sqlite_engine) -> Generator[Session, None, None]:
    """
    Fast database session using transaction rollback.

    Each test runs in a transaction that's rolled back after completion,
    ensuring test isolation without expensive table drops/creates.
    """
    connection = sqlite_engine.connect()
    transaction = connection.begin()

    # Configure session with connection
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()

    # Begin nested transaction for additional safety
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session

    # Rollback and cleanup
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def postgres_engine():
    """
    PostgreSQL engine for integration tests.

    Uses real PostgreSQL with optimized pool settings.
    """
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql://test:test@localhost/test_ruleiq")

    engine = create_engine(
        database_url, pool_size=5, max_overflow=10, pool_pre_ping=True, echo=False
    )

    # Create schema if needed
    Base.metadata.create_all(engine)

    return engine


@pytest.fixture(scope="function")
def integration_db_session(postgres_engine) -> Generator[Session, None, None]:
    """
    PostgreSQL session for integration tests with transaction rollback.
    """
    connection = postgres_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def cached_test_data() -> Dict[str, Any]:
    """
    Pre-computed test data cached for entire test session.

    Generate expensive test data once and reuse across all tests.
    """
    return {
        "users": _generate_test_users(),
        "compliance_frameworks": _generate_compliance_frameworks(),
        "ai_responses": _generate_ai_responses(),
        "business_profiles": _generate_business_profiles(),
        "regulations": _generate_regulations(),
    }


@lru_cache(maxsize=128)
def _generate_test_users():
    """Generate test user data (cached)."""
    return [
        {
            "id": f"user_{i}",
            "email": f"test{i}@example.com",
            "name": f"Test User {i}",
            "role": "admin" if i == 0 else "user",
        }
        for i in range(10)
    ]


@lru_cache(maxsize=128)
def _generate_compliance_frameworks():
    """Generate compliance framework test data (cached)."""
    frameworks = ["GDPR", "CCPA", "HIPAA", "SOC2", "ISO27001"]
    return [
        {
            "id": f"framework_{i}",
            "name": framework,
            "version": "2024.1",
            "requirements_count": 50 + i * 10,
        }
        for i, framework in enumerate(frameworks)
    ]


@lru_cache(maxsize=128)
def _generate_ai_responses():
    """Generate AI response test data (cached)."""
    return [
        {
            "query": f"Test query {i}",
            "response": f"AI response for query {i}",
            "confidence": 0.85 + (i * 0.01),
            "sources": [f"source_{j}" for j in range(3)],
        }
        for i in range(20)
    ]


@lru_cache(maxsize=128)
def _generate_business_profiles():
    """Generate business profile test data (cached)."""
    industries = ["Technology", "Healthcare", "Finance", "Retail", "Manufacturing"]
    return [
        {
            "id": f"business_{i}",
            "name": f"Test Company {i}",
            "industry": industries[i % len(industries)],
            "size": ["Small", "Medium", "Large"][i % 3],
            "compliance_needs": ["GDPR", "SOC2"] if i % 2 == 0 else ["HIPAA", "CCPA"],
        }
        for i in range(15)
    ]


@lru_cache(maxsize=128)
def _generate_regulations():
    """Generate regulation test data (cached)."""
    return [
        {
            "id": f"reg_{i}",
            "title": f"Regulation {i}",
            "category": ["Data Protection", "Security", "Privacy"][i % 3],
            "jurisdiction": ["EU", "US", "Global"][i % 3],
            "effective_date": "2024-01-01",
        }
        for i in range(30)
    ]


@pytest.fixture(scope="function")
def mock_ai_client():
    """
    Mock AI client for unit tests.

    Provides predictable responses without external API calls.
    """

    class MockAIClient:
        def __init__(self):
            self.call_count = 0

        def generate_response(self, prompt: str) -> str:
            self.call_count += 1
            return f"Mock response {self.call_count} for: {prompt[:50]}"

        def analyze_compliance(self, text: str) -> Dict[str, Any]:
            return {
                "compliant": True,
                "confidence": 0.95,
                "issues": [],
                "recommendations": ["Continue current practices"],
            }

    return MockAIClient()


@pytest.fixture(scope="session")
def redis_mock():
    """
    Mock Redis client for unit tests.

    Provides in-memory caching without Redis dependency.
    """

    class MockRedis:
        def __init__(self):
            self.store = {}
            self.ttls = {}

        def get(self, key: str):
            return self.store.get(key)

        def set(self, key: str, value: Any, ex: int = None):
            self.store[key] = value
            if ex:
                self.ttls[key] = time.time() + ex
            return True

        def delete(self, key: str):
            self.store.pop(key, None)
            self.ttls.pop(key, None)
            return True

        def exists(self, key: str):
            if key in self.ttls and time.time() > self.ttls[key]:
                self.delete(key)
                return False
            return key in self.store

    return MockRedis()


@pytest.fixture(autouse=True)
def measure_test_duration(request):
    """
    Automatically measure test execution time.

    Helps identify slow tests for optimization.
    """
    start_time = time.time()

    def finalizer():
        duration = time.time() - start_time
        test_name = request.node.name
        test_durations[test_name] = duration

        # Mark slow tests
        if duration > 1.0:
            request.node.add_marker(pytest.mark.slow)
        elif duration > 0.1:
            request.node.add_marker(pytest.mark.medium)
        else:
            request.node.add_marker(pytest.mark.fast)

    request.addfinalizer(finalizer)


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """
    Configure optimal test environment settings.
    """
    # Disable debug logging for speed
    import logging

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_POOL_SIZE"] = "5"
    os.environ["REDIS_POOL_SIZE"] = "5"

    yield

    # Cleanup
    os.environ.pop("TESTING", None)


@contextmanager
def temporary_database():
    """
    Context manager for temporary test database.

    Useful for tests that need isolated database state.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# Performance helpers
def get_slowest_tests(n: int = 10) -> list:
    """Get the N slowest tests from the last run."""
    sorted_tests = sorted(test_durations.items(), key=lambda x: x[1], reverse=True)
    return sorted_tests[:n]


def print_performance_summary():
    """Print test performance summary."""
    if not test_durations:
        return

    total_time = sum(test_durations.values())
    avg_time = total_time / len(test_durations)

    print(f"\n{'=' * 60}")
    print("Test Performance Summary")
    print(f"{'=' * 60}")
    print(f"Total tests: {len(test_durations)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time: {avg_time:.4f}s")
    print("\nSlowest tests:")

    for test_name, duration in get_slowest_tests():
        print(f"  {test_name}: {duration:.4f}s")
