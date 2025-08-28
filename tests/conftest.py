"""
Pytest configuration and fixtures for the test suite.
"""
import os
import pytest
import asyncio
from typing import Generator, Optional
from unittest.mock import MagicMock
from uuid import UUID, uuid4
from datetime import datetime
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Database imports
from database import (
    Base, User, BusinessProfile, ComplianceFramework, EvidenceItem,
    AssessmentSession, AssessmentQuestion, GeneratedPolicy,
    AssessmentLead, FreemiumAssessmentSession, AIQuestionBank,
    LeadScoringEvent, ConversionEvent
)

# =============================================================================
# DATABASE SETUP FOR SYNC TESTS
# =============================================================================

# Get database URL and ensure it's using psycopg2 for sync tests
def get_sync_db_url():
    """Get synchronous database URL for testing."""
    # Try to get a real database URL first
    db_url = os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL")
    )
    
    if db_url:
        # Convert async URL to sync if needed
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "+psycopg2")
        elif "postgresql://" in db_url and "+psycopg2" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return db_url
    else:
        # Fall back to in-memory SQLite for testing if no PostgreSQL is available
        return "sqlite:///:memory:"

# Create test engine and session factory
sync_db_url = get_sync_db_url()
if sync_db_url.startswith("sqlite"):
    test_engine = create_engine(
        sync_db_url,
        poolclass=StaticPool,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    test_engine = create_engine(
        sync_db_url,
        poolclass=StaticPool,
        echo=False,
        connect_args={"connect_timeout": 10},
    )

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up database for entire test session."""
    try:
        # Create all tables
        Base.metadata.create_all(bind=test_engine)
        
        # Initialize default frameworks
        session = TestSessionLocal()
        try:
            frameworks = [
                {
                    "name": "GDPR",
                    "display_name": "General Data Protection Regulation",
                    "description": "EU data protection and privacy regulation",
                    "category": "Data Protection",
                },
                {
                    "name": "ISO27001",
                    "display_name": "ISO/IEC 27001:2022",
                    "description": "Information security management systems",
                    "category": "Information Security",
                },
                {
                    "name": "SOC2",
                    "display_name": "SOC 2 Type II",
                    "description": "Service Organization Control 2",
                    "category": "Security & Compliance",
                },
            ]
            
            for fw_data in frameworks:
                existing = session.query(ComplianceFramework).filter_by(name=fw_data["name"]).first()
                if not existing:
                    framework = ComplianceFramework(**fw_data)
                    session.add(framework)
            
            session.commit()
        finally:
            session.close()
        
        yield
        
        # Clean up
        Base.metadata.drop_all(bind=test_engine)
    except Exception as e:
        pytest.skip(f"Database setup failed: {e}")


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    session = TestSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def async_db_session(db_session):
    """Provide sync session for async fixtures (compatibility)."""
    return db_session


# Test user constants
TEST_USER_ID = UUID("12345678-1234-5678-9012-123456789012")
TEST_BUSINESS_PROFILE_ID = UUID("87654321-4321-8765-4321-876543218765")


@pytest.fixture
def sample_user(db_session):
    """Create a test user."""
    existing = db_session.query(User).filter_by(email="test@example.com").first()
    if existing:
        return existing
    
    user = User(
        id=TEST_USER_ID,
        email="test@example.com",
        hashed_password="$2b$12$test_hashed_password",
        is_active=True,
        first_name="Test",
        last_name="User",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_business_profile(db_session, sample_user):
    """Create a test business profile."""
    existing = db_session.query(BusinessProfile).filter_by(user_id=sample_user.id).first()
    if existing:
        return existing
    
    profile = BusinessProfile(
        id=TEST_BUSINESS_PROFILE_ID,
        user_id=sample_user.id,
        company_name="Test Company Ltd",
        industry="Technology",
        business_type="Software Development",
        employee_count=50,
        annual_revenue="1M-10M",
        primary_location="United Kingdom",
        data_handling_countries=["UK", "EU"],
        regulatory_environment="UK_GDPR",
        existing_frameworks=["ISO27001"],
        compliance_priorities=["Data Protection", "Information Security"],
        current_maturity_level="Developing",
        target_completion_date=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


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
def postgres_test_url():
    """Get PostgreSQL test connection URL."""
    # Priority order:
    # 1. TEST_DATABASE_URL environment variable
    # 2. DATABASE_URL environment variable (for CI/CD)
    # 3. Default local test database
    return os.getenv(
        "TEST_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5433/compliance_test"
        )
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
    # Skip if no PostgreSQL is available
    if not os.getenv("DATABASE_URL") and not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("PostgreSQL test database not configured")
    
    try:
        # Create connection with proper settings for PostgresSaver
        conn = psycopg.connect(
            postgres_test_url,
            autocommit=True,  # Required for PostgresSaver
            row_factory=dict_row  # Required for PostgresSaver
        )
        
        # Create checkpointer
        checkpointer = PostgresSaver(conn)
        
        # Setup tables (idempotent - won't error if tables exist)
        checkpointer.setup()
        
        yield checkpointer
        
        # Cleanup: Close connection
        conn.close()
        
    except Exception as e:
        pytest.skip(f"PostgreSQL connection failed: {e}")


@pytest.fixture
def postgres_connection(postgres_test_url):
    """
    Provide a raw PostgreSQL connection for tests that need direct DB access.
    """
    if not os.getenv("DATABASE_URL") and not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("PostgreSQL test database not configured")
    
    try:
        conn = psycopg.connect(postgres_test_url)
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL connection failed: {e}")


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


@pytest.fixture
def clean_test_db(postgres_connection):
    """
    Ensure a clean database state for each test.
    Drops and recreates checkpointing tables.
    """
    with postgres_connection.cursor() as cursor:
        # Drop existing checkpointing tables if they exist
        cursor.execute("""
            DROP TABLE IF EXISTS checkpoints CASCADE;
            DROP TABLE IF EXISTS checkpoint_blobs CASCADE;
            DROP TABLE IF EXISTS checkpoint_metadata CASCADE;
        """)
        postgres_connection.commit()
    
    yield
    
    # Cleanup after test
    with postgres_connection.cursor() as cursor:
        cursor.execute("""
            DROP TABLE IF EXISTS checkpoints CASCADE;
            DROP TABLE IF EXISTS checkpoint_blobs CASCADE;
            DROP TABLE IF EXISTS checkpoint_metadata CASCADE;
        """)
        postgres_connection.commit()


# Mark slow tests
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_db: mark test as requiring database connection"
    )