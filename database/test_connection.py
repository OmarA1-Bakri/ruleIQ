"""
Test database connection utilities.
Provides robust connection handling for test environments.
"""

import os
import logging
from typing import Optional, Tuple
from sqlalchemy import create_engine, text, pool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

try:
    import psycopg
    from psycopg import OperationalError as PsycopgOperationalError
except ImportError:  # pragma: no cover - optional in minimal test env
    psycopg = None
    PsycopgOperationalError = OperationalError

logger = logging.getLogger(__name__)


class TestDatabaseManager:
    """Manages test database connections and setup."""

    def __init__(self) -> None:
        self.test_engine: Optional[Engine] = None
        self.is_test_env = os.getenv("TESTING", "").lower() == "true"

    def get_test_db_url(self) -> str:
        """Get the test database URL."""
        # Priority order:
        # 1. TEST_DATABASE_URL
        # 2. DATABASE_URL (if in test mode)
        # 3. Default test database
        if self.is_test_env:
            return os.getenv(
                "TEST_DATABASE_URL",
                os.getenv(
                    "DATABASE_URL",
                    "postgresql://test_user:test_password@localhost:5433/ruleiq_test",
                ),
            )
        return os.getenv("DATABASE_URL", "")

    def get_redis_test_url(self) -> str:
        """Get the test Redis URL."""
        if self.is_test_env:
            return os.getenv("REDIS_URL", "redis://localhost:6380/0")
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")

    def create_test_engine(self, **kwargs) -> Engine:
        """Create a test database engine with optimized settings."""
        db_url = self.get_test_db_url()

        # Convert URL format if needed
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "+psycopg")
        elif "postgresql://" in db_url and "+" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://")

        # Test-optimized settings
        engine_kwargs = {
            "echo": os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
            "poolclass": pool.StaticPool if "sqlite" in db_url else pool.QueuePool,
            "pool_size": 5,  # Smaller pool for tests
            "max_overflow": 10,
            "pool_timeout": 10,
            "pool_recycle": 1800,
            "pool_pre_ping": True,  # Important for test reliability
            **kwargs,
        }

        # Remove poolclass for SQLite
        if "sqlite" in db_url:
            engine_kwargs.pop("pool_size", None)
            engine_kwargs.pop("max_overflow", None)
            engine_kwargs.pop("pool_timeout", None)
            engine_kwargs.pop("pool_recycle", None)

        try:
            self.test_engine = create_engine(db_url, **engine_kwargs)
            logger.info(
                f"Test engine created for: {db_url.split('@')[-1] if '@' in db_url else 'memory'}"
            )
            return self.test_engine
        except Exception as e:
            logger.error(f"Failed to create test engine: {e}")
            raise

    def verify_connection(self, engine: Optional[Engine] = None) -> bool:
        """Verify database connection is working."""
        engine = engine or self.test_engine
        if not engine:
            logger.error("No engine available for connection test")
            return False

        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.scalar()
                logger.info("✓ Database connection verified")
                return True
        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def ensure_database_exists(self) -> bool:
        """Ensure the test database exists."""
        if psycopg is None:
            logger.info("psycopg is not installed; skipping database creation check")
            return False

        db_url = self.get_test_db_url()

        # Skip database creation for Neon (managed service)
        if "neon.tech" in db_url:
            logger.info("✓ Using Neon managed database - skipping database creation check")
            return True

        # Parse connection parameters
        if "postgresql" in db_url:
            # Extract components from URL
            import re

            pattern = r"postgresql(?:\+\w+)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)"
            match = re.match(pattern, db_url)

            if not match:
                logger.error(f"Could not parse database URL: {db_url}")
                return False

            user, password, host, port, database = match.groups()
            port = port or "5432"

            try:
                # Connect to postgres database to create test database
                conn = psycopg.connect(
                    host=host, port=port, user=user, password=password, database="postgres"
                )
                conn.autocommit = True

                with conn.cursor() as cursor:
                    # Check if database exists
                    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
                    if not cursor.fetchone():
                        cursor.execute(f"CREATE DATABASE {database}")
                        logger.info(f"Created test database: {database}")
                    else:
                        logger.info(f"Test database already exists: {database}")

                conn.close()
                return True

            except PsycopgOperationalError as e:
                logger.error(f"Failed to ensure database exists: {e}")
                return False

        return True  # SQLite doesn't need database creation

    def create_tables(self, base_metadata) -> bool:
        """Create all tables in the test database."""
        if not self.test_engine:
            logger.error("No test engine available")
            return False

        try:
            base_metadata.create_all(bind=self.test_engine)
            logger.info("✓ All tables created/verified")
            return True
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up test database connections."""
        if self.test_engine:
            self.test_engine.dispose()
            logger.info("Test engine connections disposed")
            self.test_engine = None


def get_test_db_manager() -> TestDatabaseManager:
    """Get a singleton test database manager."""
    if not hasattr(get_test_db_manager, "_instance"):
        get_test_db_manager._instance = TestDatabaseManager()
    return get_test_db_manager._instance


def setup_test_database() -> Tuple[bool, Optional[str]]:
    """
    Complete test database setup.

    Returns:
        Tuple of (success, error_message)
    """
    manager = get_test_db_manager()

    # 1. Ensure database exists
    if not manager.ensure_database_exists():
        return False, "Failed to ensure database exists"

    # 2. Create engine
    try:
        engine = manager.create_test_engine()
    except Exception as e:
        return False, f"Failed to create engine: {e}"

    # 3. Verify connection
    if not manager.verify_connection(engine):
        return False, "Failed to verify connection"

    # 4. Create tables
    from database import Base

    if not manager.create_tables(Base.metadata):
        return False, "Failed to create tables"

    return True, None


def test_redis_connection() -> bool:
    """Test Redis connection."""
    import redis

    manager = get_test_db_manager()
    redis_url = manager.get_redis_test_url()

    # Parse Redis URL
    import re

    pattern = r"redis://(?:([^:]+):([^@]+)@)?([^:/]+)(?::(\d+))?(?:/(\d+))?"
    match = re.match(pattern, redis_url)

    if not match:
        logger.error(f"Could not parse Redis URL: {redis_url}")
        return False

    _, _, host, port, db = match.groups()
    port = int(port or 6379)
    db = int(db or 0)

    try:
        r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        r.ping()

        # Test basic operations
        r.set("test_key", "test_value", ex=10)
        value = r.get("test_key")
        r.delete("test_key")

        if value == "test_value":
            logger.info(f"✓ Redis connection verified on {host}:{port}")
            return True
        else:
            logger.error("Redis test operations failed")
            return False

    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        return False
