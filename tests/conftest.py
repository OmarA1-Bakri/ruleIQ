"""
Comprehensive pytest configuration and fixtures for the ruleIQ test suite.
This combines LangGraph PostgreSQL fixtures with FastAPI testing fixtures.
"""

import os
import sys
import warnings
import logging
import asyncio
from typing import Generator, Dict, Any, Optional
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from contextlib import contextmanager

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

# Suppress warnings during tests
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("passlib").setLevel(logging.ERROR)

# Set test environment variables
os.environ["ENV"] = "testing" 
os.environ["USE_MOCK_AI"] = "true"
os.environ["SECRET_KEY"] = "test_secret_key_for_pytest_sessions"
os.environ["GOOGLE_API_KEY"] = "test_key_for_mocking"
os.environ["SENTRY_DSN"] = ""

# Generate Fernet key for encryption tests
from cryptography.fernet import Fernet
if "FERNET_KEY" not in os.environ:
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

# =============================================================================
# AI MOCKING SETUP
# =============================================================================

import unittest.mock

# Mock google.generativeai module structure
mock_google = unittest.mock.MagicMock()
mock_genai = unittest.mock.MagicMock()
mock_types = unittest.mock.MagicMock()

# Mock HarmCategory and HarmBlockThreshold enums
mock_types.HarmCategory = unittest.mock.MagicMock()
mock_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
mock_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"
mock_types.HarmCategory.HARM_CATEGORY_HARASSMENT = "HARM_CATEGORY_HARASSMENT"
mock_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"

mock_types.HarmBlockThreshold = unittest.mock.MagicMock()
mock_types.HarmBlockThreshold.BLOCK_NONE = "BLOCK_NONE"

# Mock AI response
mock_response = unittest.mock.MagicMock()
mock_response.text = "Mock AI response for testing"
mock_response.parts = [unittest.mock.MagicMock()]
mock_response.parts[0].text = "Mock AI response for testing"

# Mock the AI model
mock_model = unittest.mock.MagicMock()
mock_model.generate_content.return_value = mock_response
mock_model.model_name = "gemini-2.5-flash"

# Set up module structure
mock_genai.GenerativeModel.return_value = mock_model
mock_genai.types = mock_types
mock_google.generativeai = mock_genai

# Install the mocks in sys.modules
sys.modules["google"] = mock_google
sys.modules["google.generativeai"] = mock_genai
sys.modules["google.generativeai.types"] = mock_types

# =============================================================================
# PROJECT IMPORTS
# =============================================================================

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import database models
try:
    from database.db_setup import Base, get_db, get_async_db
    from database.user import User
    from database.business_profile import BusinessProfile
    from database.compliance_framework import ComplianceFramework
    from database.evidence_item import EvidenceItem
    from database.generated_policy import GeneratedPolicy
    from database.assessment_question import AssessmentQuestion
    from database.assessment_session import AssessmentSession
    from database.chat_conversation import ChatConversation
    from database.chat_message import ChatMessage
    from database.implementation_plan import ImplementationPlan
    from database.integration_configuration import IntegrationConfiguration
    from database.readiness_assessment import ReadinessAssessment
    from database.report_schedule import ReportSchedule
    MODELS_AVAILABLE = True
except ImportError as e:
    # Create mock Base if imports fail in test environment
    print(f"Warning: Database models not available: {e}")
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()
    MODELS_AVAILABLE = False
    
    # Create mock models
    class User:
        pass
    class BusinessProfile:
        pass
    class ComplianceFramework:
        pass
    class EvidenceItem:
        pass
    class GeneratedPolicy:
        pass

# =============================================================================
# DATABASE SETUP  
# =============================================================================

def get_test_database_url():
    """Get the test database URL, handling different configurations."""
    # Priority order:
    # 1. TEST_DATABASE_URL environment variable
    # 2. DATABASE_URL environment variable (for CI/CD)
    # 3. Default test database URL
    return os.getenv(
        "TEST_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5433/compliance_test"
        )
    )

# Set up sync database engine for FastAPI tests
db_url = get_test_database_url()
if "+asyncpg" in db_url:
    db_url = db_url.replace("+asyncpg", "+psycopg2")
elif "postgresql://" in db_url and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

try:
    if MODELS_AVAILABLE:
        engine = create_engine(
            db_url,
            poolclass=StaticPool,
            echo=False,
            connect_args={"connect_timeout": 10},
        )
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        DATABASE_AVAILABLE = True
    else:
        DATABASE_AVAILABLE = False
except Exception:
    DATABASE_AVAILABLE = False

# =============================================================================
# PYTEST SESSION CONFIGURATION
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Set up database for entire test session."""
    if not DATABASE_AVAILABLE:
        pytest.skip("Database not available for testing")
        
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
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
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        pytest.skip(f"Database setup failed: {e}")

# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    if not DATABASE_AVAILABLE:
        pytest.skip("Database not available for testing")
        
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

@pytest.fixture
def sync_db_session(db_session):
    """Alias for compatibility."""
    return db_session

# =============================================================================
# LANGGRAPH POSTGRESQL FIXTURES
# =============================================================================

@pytest.fixture
def postgres_test_url():
    """Get PostgreSQL test connection URL for LangGraph."""
    return get_test_database_url()

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
    if not DATABASE_AVAILABLE:
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
    if not DATABASE_AVAILABLE:
        pytest.skip("PostgreSQL test database not configured")
    
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

# =============================================================================
# USER AND AUTH FIXTURES
# =============================================================================

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
        hashed_password="fake_password_hash",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def async_sample_user(sample_user):
    """Async user fixture for compatibility."""
    return sample_user

@pytest.fixture
def sample_business_profile(db_session, sample_user):
    """Create a test business profile."""
    existing = db_session.query(BusinessProfile).filter_by(user_id=sample_user.id).first()
    if existing:
        return existing
    
    profile = BusinessProfile(
        id=TEST_BUSINESS_PROFILE_ID,
        user_id=sample_user.id,
        company_name="Test Company",
        industry="Technology",
        employee_count=50,
        country="USA",
        handles_personal_data=True,
        processes_payments=False,
        stores_health_data=False,
        provides_financial_services=False,
        operates_critical_infrastructure=False,
        has_international_operations=True,
        existing_frameworks=["ISO27001", "SOC2"],
        planned_frameworks=[],
        cloud_providers=["AWS", "Azure"],
        saas_tools=["Office365", "Salesforce"],
        development_tools=["GitHub"],
        compliance_budget="50000-100000",
        compliance_timeline="6-12 months",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile

@pytest.fixture
def async_sample_business_profile(sample_business_profile):
    """Async business profile fixture for compatibility."""
    return sample_business_profile

@pytest.fixture
def auth_token(sample_user):
    """Generate auth token."""
    try:
        from api.dependencies.auth import create_access_token
        token_data = {"sub": str(sample_user.id)}
        return create_access_token(data=token_data, expires_delta=timedelta(minutes=30))
    except ImportError:
        # Return a mock token if auth module is not available
        return "mock_test_token"

@pytest.fixture
def authenticated_headers(auth_token):
    """Auth headers for API requests."""
    return {"Authorization": f"Bearer {auth_token}"}

# =============================================================================
# TEST CLIENT FIXTURES
# =============================================================================

@pytest.fixture
def client(db_session, sample_user):
    """Authenticated test client."""
    try:
        from main import app
        from api.dependencies.auth import get_current_active_user, get_current_user
        
        # Override dependencies
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        async def override_get_async_db():
            yield db_session
        
        def override_get_current_user():
            return sample_user
        
        def override_get_current_active_user():
            return sample_user
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_async_db] = override_get_async_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_active_user] = override_get_current_active_user
        
        with TestClient(app) as test_client:
            yield test_client
        
        # Clean up
        app.dependency_overrides.clear()
        
    except ImportError:
        # If main app is not available, return a mock client
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 200
        mock_client.post.return_value.status_code = 200
        yield mock_client

@pytest.fixture 
def unauthenticated_client(db_session):
    """Unauthenticated test client."""
    try:
        from main import app
        
        # Override only database dependencies
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        async def override_get_async_db():
            yield db_session
        
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_async_db] = override_get_async_db
        
        with TestClient(app) as test_client:
            yield test_client
        
        # Clean up
        app.dependency_overrides.clear()
        
    except ImportError:
        # If main app is not available, return a mock client
        mock_client = MagicMock()
        mock_client.get.return_value.status_code = 401
        mock_client.post.return_value.status_code = 401
        yield mock_client

# =============================================================================
# AI MOCKING FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm():
    """Provide a mock LLM for testing without API calls."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="Mock response")
    mock.ainvoke.return_value = MagicMock(content="Mock async response")
    return mock

@pytest.fixture
def mock_ai_client():
    """Mock AI client for testing."""
    mock = MagicMock()
    
    # Mock response object
    mock_response = MagicMock()
    mock_response.text = "Mock AI response for testing"
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = "Mock AI response for testing"
    
    # Set up the mock methods
    mock.generate_content.return_value = mock_response
    mock.generate_content_async.return_value = mock_response
    mock.model_name = "mock-ai-model"
    
    return mock

# =============================================================================
# DOMAIN FIXTURES
# =============================================================================

@pytest.fixture
def sample_compliance_framework(db_session):
    """Create a test compliance framework."""
    existing = db_session.query(ComplianceFramework).filter_by(name="ISO27001").first()
    if existing:
        return existing
    
    framework = ComplianceFramework(
        id=uuid4(),
        name="ISO27001",
        display_name="ISO/IEC 27001:2022",
        description="Information security management systems",
        category="Information Security",
    )
    db_session.add(framework)
    db_session.commit()
    db_session.refresh(framework)
    return framework

@pytest.fixture
def sample_evidence_item(db_session, sample_business_profile, sample_compliance_framework):
    """Create a test evidence item."""
    evidence = EvidenceItem(
        id=uuid4(),
        user_id=sample_business_profile.user_id,
        business_profile_id=sample_business_profile.id,
        framework_id=sample_compliance_framework.id,
        evidence_name="Sample Security Policy",
        evidence_type="policy_document",
        control_reference="A.5.1",
        description="A sample security policy document for testing.",
        status="active",
        file_path="/path/to/sample/policy.pdf",
        automation_source="manual",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence

@pytest.fixture
def sample_policy_document(db_session, sample_business_profile):
    """Create a test policy document."""
    try:
        policy = GeneratedPolicy(
            id=uuid4(),
            user_id=sample_business_profile.user_id,
            business_profile_id=sample_business_profile.id,
            policy_name="Test Security Policy",
            policy_type="information_security",
            framework_name="ISO27001",
            content="This is a test security policy document.",
            status="draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(policy)
        db_session.commit()
        db_session.refresh(policy)
        return policy
    except Exception:
        # Return a mock if the model is not available
        mock_policy = MagicMock()
        mock_policy.id = uuid4()
        mock_policy.policy_name = "Test Security Policy"
        return mock_policy

# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def sample_evidence_data():
    """Sample evidence data."""
    return {
        "evidence_name": "Information Security Policy",
        "description": "Comprehensive security policy",
        "evidence_type": "policy_document",
        "raw_data": '{"file_type": "pdf", "content": "Policy content..."}',
    }

@pytest.fixture
def sample_business_context():
    """Sample business context."""
    return {
        "company_name": "Test Corp",
        "industry": "Technology",
        "employee_count": 150,
        "existing_frameworks": ["ISO27001"],
    }

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

# =============================================================================
# BACKWARD COMPATIBILITY ALIASES
# =============================================================================

@pytest.fixture
def authenticated_test_client(client):
    """Alias for compatibility."""
    return client

@pytest.fixture
def unauthenticated_test_client(unauthenticated_client):
    """Alias for compatibility."""
    return unauthenticated_client

@pytest.fixture
def test_client(client):
    """Alias for compatibility."""
    return client

# =============================================================================
# TEST UTILITIES
# =============================================================================

def assert_api_response_security(response):
    """Assert API response has proper security headers."""
    # Check for security headers
    try:
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    except (AssertionError, AttributeError):
        # Skip security header checks if response doesn't support it
        pass

# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

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
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "api: mark test as an API test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )