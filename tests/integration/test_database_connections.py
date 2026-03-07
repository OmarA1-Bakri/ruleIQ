"""
Integration tests for database connections.
Verifies PostgreSQL and Redis connections work correctly in test environment.
"""

import pytest
import os
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis
import asyncio


class TestDatabaseConnections:
    """Test database connection functionality."""

    def test_environment_is_test(self):
        """Ensure we're in test environment."""
        assert os.getenv("TESTING") == "true"
        assert os.getenv("ENVIRONMENT") == "testing"

    def test_postgres_connection(self, db_session: Session):
        """Test basic PostgreSQL connection."""
        # Execute a simple query
        result = db_session.execute(text("SELECT 1 as num"))
        row = result.fetchone()
        assert row[0] == 1

        # Test database name
        result = db_session.execute(text("SELECT current_database()"))
        db_name = result.scalar()
        assert "test" in db_name.lower() or "compliance" in db_name.lower()

    def test_postgres_transaction_rollback(self, db_session: Session):
        """Test that transactions are properly rolled back between tests."""
        from database import User

        # Create a user in this test
        user = User(
            email="rollback_test@example.com",
            full_name="Rollback Test",
            hashed_password="test_hash",
        )
        db_session.add(user)
        db_session.commit()

        # Verify user exists in this session
        found = db_session.query(User).filter_by(email="rollback_test@example.com").first()
        assert found is not None

        # User should be rolled back after test completes

    def test_postgres_no_persistence_between_tests(self, db_session: Session):
        """Verify data doesn't persist between tests."""
        from database import User

        # User from previous test should not exist
        found = db_session.query(User).filter_by(email="rollback_test@example.com").first()
        assert found is None

    def test_postgres_table_creation(self, db_session: Session):
        """Verify all required tables exist."""
        # Get list of tables
        result = db_session.execute(
            text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
        )
        tables = [row[0] for row in result]

        # Check for essential tables
        essential_tables = [
            "users",
            "business_profiles",
            "compliance_frameworks",
            "assessment_sessions",
            "evidence_items",
        ]

        for table in essential_tables:
            assert table in tables, f"Table {table} not found"

    def test_redis_connection(self, redis_client):
        """Test basic Redis connection."""
        # Test ping
        assert redis_client.ping() is True

        # Test set/get
        redis_client.set("test_key", "test_value")
        value = redis_client.get("test_key")
        assert value == "test_value"

        # Test delete
        result = redis_client.delete("test_key")
        assert result == 1

        # Verify deleted
        value = redis_client.get("test_key")
        assert value is None

    def test_redis_expiration(self, redis_client):
        """Test Redis key expiration."""
        # Set key with 1 second expiration
        redis_client.set("expire_test", "value", ex=1)

        # Should exist immediately
        assert redis_client.get("expire_test") == "value"

        # Wait for expiration
        import time

        time.sleep(1.1)

        # Should be expired
        assert redis_client.get("expire_test") is None

    def test_redis_data_types(self, redis_client):
        """Test various Redis data types."""
        # List operations
        redis_client.lpush("test_list", "item1", "item2")
        items = redis_client.lrange("test_list", 0, -1)
        assert items == ["item2", "item1"]

        # Hash operations
        redis_client.hset("test_hash", "field1", "value1")
        redis_client.hset("test_hash", "field2", "value2")
        hash_data = redis_client.hgetall("test_hash")
        assert hash_data == {"field1": "value1", "field2": "value2"}

        # Set operations
        redis_client.sadd("test_set", "member1", "member2", "member1")
        members = redis_client.smembers("test_set")
        assert members == {"member1", "member2"}

        # Cleanup
        redis_client.delete("test_list", "test_hash", "test_set")

    @pytest.mark.asyncio
    async def test_async_postgres_connection(self, async_db_session):
        """Test async PostgreSQL connection."""
        # Execute async query
        result = await async_db_session.execute(text("SELECT 2 + 2 as sum"))
        row = result.fetchone()
        assert row[0] == 4

    def test_connection_pool_settings(self, test_db_engine):
        """Verify connection pool is configured correctly."""
        pool = test_db_engine.pool

        # Check pool settings
        assert pool.size() <= 5  # Pool size for tests
        assert hasattr(pool, "_overflow")  # Has overflow capability

    def test_fixtures_work_together(self, db_session, redis_client, sample_user):
        """Test that multiple fixtures can work together."""
        # Use database
        assert sample_user.email == "test@example.com"

        # Cache user ID in Redis
        redis_client.set(f"user:{sample_user.id}", sample_user.email)

        # Retrieve from cache
        cached_email = redis_client.get(f"user:{sample_user.id}")
        assert cached_email == sample_user.email

        # Clean up
        redis_client.delete(f"user:{sample_user.id}")


class TestConnectionResilience:
    """Test connection resilience and error handling."""

    def test_postgres_connection_recovery(self, db_session: Session):
        """Test that connections can recover from errors."""
        try:
            # Intentionally cause an error
            db_session.execute(text("SELECT * FROM nonexistent_table"))
        except Exception:
            # Rollback the failed transaction
            db_session.rollback()

        # Should be able to continue using the session
        result = db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_redis_connection_recovery(self, redis_client):
        """Test Redis connection recovery."""
        # Even if a command fails, client should remain usable
        try:
            # Try an invalid operation
            redis_client.get(None)
        except Exception:
            pass

        # Should still work
        redis_client.set("recovery_test", "works")
        assert redis_client.get("recovery_test") == "works"
        redis_client.delete("recovery_test")


class TestMockFixtures:
    """Test mock fixtures for unit tests."""

    def test_mock_redis_client(self, mock_redis_client):
        """Test the mock Redis client fixture."""
        # Test basic operations
        assert mock_redis_client.set("key1", "value1") is True
        assert mock_redis_client.get("key1") == "value1"
        assert mock_redis_client.exists("key1") is True
        assert mock_redis_client.delete("key1") == 1
        assert mock_redis_client.exists("key1") is False

        # Test nx (not exists) flag
        mock_redis_client.set("key2", "value2")
        assert mock_redis_client.set("key2", "new_value", nx=True) is False
        assert mock_redis_client.get("key2") == "value2"

        # Test xx (exists) flag
        assert mock_redis_client.set("key3", "value3", xx=True) is False
        mock_redis_client.set("key3", "initial")
        assert mock_redis_client.set("key3", "updated", xx=True) is True
        assert mock_redis_client.get("key3") == "updated"
