"""

Testing Configuration
Settings for test environment
"""

from config.base import BaseConfig, Environment
import tempfile
from pathlib import Path
from typing import Optional
from pydantic import Field


class TestingConfig(BaseConfig):
    """Testing-specific configuration"""

    # Override environment
    ENVIRONMENT: Environment = Environment.TESTING

    # Testing settings
    DEBUG: bool = True
    TESTING: bool = True

    # Testing server
    HOST: str = "127.0.0.1"
    PORT: int = 5555  # Different port for testing

    # Security - Simple defaults for testing, but allow env override
    # These will use environment variables if set, otherwise use test defaults
    SECRET_KEY: str = Field(default="test-secret-key", env="SECRET_KEY")
    JWT_SECRET_KEY: str = Field(default="test-jwt-secret", env="JWT_SECRET_KEY")
    JWT_EXPIRATION_DELTA_SECONDS: int = 60  # Short expiration for tests

    # Database - Allow environment override with test default
    DATABASE_URL: str = Field(
        default="postgresql://localhost/ruleiq_test",
        env="DATABASE_URL",
    )
    DB_POOL_SIZE: int = 1
    DB_MAX_OVERFLOW: int = 0

    # Redis - Allow environment override with test default
    REDIS_URL: str = Field(default="redis://localhost:6379/15", env="REDIS_URL")
    REDIS_MAX_CONNECTIONS: int = 5

    # Neo4j - Allow environment override with test defaults
    NEO4J_URI: str = Field(default="neo4j+s://12e71bc4.databases.neo4j.io", env="NEO4J_URI")
    NEO4J_USERNAME: str = Field(default="neo4j", env="NEO4J_USERNAME")
    NEO4J_PASSWORD: str = Field(default="test", env="NEO4J_PASSWORD")

    # Logging - Minimal for tests
    LOG_LEVEL: str = "ERROR"
    LOG_FILE: None = None

    # CORS - Disabled for testing
    CORS_ORIGINS: list = []

    # Rate Limiting - Disabled for testing
    RATE_LIMIT_ENABLED: bool = False

    # Testing features
    ENABLE_DEBUG_TOOLBAR: bool = False
    ENABLE_PROFILING: bool = False
    ENABLE_SQL_ECHO: bool = False
    ENABLE_MONITORING: bool = False

    # AI Services - Mock defaults for testing, but allow override
    OPENAI_API_KEY: Optional[str] = Field(default="test-api-key", env="OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = Field(
        default="test-google-key",
        env="GOOGLE_API_KEY",
    )
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default="test-anthropic-key",
        env="ANTHROPIC_API_KEY",
    )
    USE_AI_MOCKS: bool = True  # Use mocked AI responses

    # File uploads - Temp directory for testing
    UPLOAD_DIR: Path = Field(default_factory=lambda: Path(tempfile.mkdtemp()))
    MAX_FILE_SIZE: int = 1 * 1024 * 1024  # 1MB for tests

    # Test specific
    TEST_RUNNER: str = "pytest"
    TEST_COVERAGE: bool = True
    TEST_PARALLEL: bool = False  # Run tests sequentially

    class Config:
        """Pydantic configuration"""

        env_file = ".env.testing"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def setup_test_database(self) -> None:
        """Setup test database"""
        # This would contain logic to create test database
        pass

    def teardown_test_database(self) -> None:
        """Teardown test database"""
        # This would contain logic to clean up test database
        pass
