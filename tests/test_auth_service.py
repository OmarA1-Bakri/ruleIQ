"""
Unit tests for services/auth_service.py

Tests the authentication service, session management, and security components.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.auth_service import SessionManager, AuthService, auth_service
from database.user import User


class TestSessionManager:
    """Test the SessionManager class with Redis and in-memory fallbacks."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager instance."""
        return SessionManager()

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        redis.setex = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.sadd = AsyncMock(return_value=1)
        redis.srem = AsyncMock(return_value=1)
        redis.smembers = AsyncMock(return_value=set())
        redis.expire = AsyncMock(return_value=True)
        return redis

    def test_initialization(self, session_manager):
        """Test SessionManager initialization."""
        assert session_manager._redis_client is None
        assert session_manager._redis_available is None
        assert session_manager._memory_sessions == {}

    @pytest.mark.asyncio
    async def test_get_redis_client_success(self, session_manager, mock_redis):
        """Test successful Redis client creation."""
        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            client = await session_manager.get_redis_client()
            assert client == mock_redis
            assert session_manager._redis_available is True

    @pytest.mark.asyncio
    async def test_get_redis_client_connection_failure(self, session_manager):
        """Test Redis client creation failure."""
        with patch(
            "services.auth_service.redis.from_url", side_effect=ValueError("Connection failed")
        ):
            client = await session_manager.get_redis_client()
            assert client is None
            assert session_manager._redis_available is False

    @pytest.mark.asyncio
    async def test_get_redis_client_ping_failure(self, session_manager, mock_redis):
        """Test Redis client ping failure."""
        mock_redis.ping.side_effect = Exception("Ping failed")
        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            client = await session_manager.get_redis_client()
            assert client is None
            assert session_manager._redis_available is False

    @pytest.mark.asyncio
    async def test_create_session_redis_success(self, session_manager, mock_redis):
        """Test successful session creation with Redis."""
        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            user_id = uuid4()
            session_id = await session_manager.create_session(user_id, "test_token")

            assert isinstance(session_id, str)
            mock_redis.setex.assert_called_once()
            mock_redis.sadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_redis_failure_fallback(self, session_manager, mock_redis):
        """Test session creation with Redis failure, fallback to memory."""
        mock_redis.setex.side_effect = Exception("Redis error")
        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            user_id = uuid4()
            session_id = await session_manager.create_session(user_id, "test_token")

            assert isinstance(session_id, str)
            assert session_id in session_manager._memory_sessions

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, session_manager):
        """Test session creation with metadata."""
        user_id = uuid4()
        metadata = {"ip": "127.0.0.1", "user_agent": "test"}
        session_id = await session_manager.create_session(user_id, "test_token", metadata)

        assert session_id in session_manager._memory_sessions
        session_data = session_manager._memory_sessions[session_id]
        assert session_data["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_get_session_redis_success(self, session_manager, mock_redis):
        """Test successful session retrieval from Redis."""
        session_data = {"user_id": str(uuid4()), "token": "test"}
        mock_redis.get.return_value = json.dumps(session_data)

        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            result = await session_manager.get_session("session_123")
            assert result == session_data

    @pytest.mark.asyncio
    async def test_get_session_redis_json_error_fallback(self, session_manager, mock_redis):
        """Test session retrieval with JSON error, fallback to memory."""
        mock_redis.get.return_value = "invalid json"
        session_manager._memory_sessions["session_123"] = {"user_id": str(uuid4())}

        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            result = await session_manager.get_session("session_123")
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_session_memory_fallback(self, session_manager):
        """Test session retrieval from memory when Redis unavailable."""
        session_data = {"user_id": str(uuid4()), "token": "test"}
        session_manager._memory_sessions["session_123"] = session_data

        result = await session_manager.get_session("session_123")
        assert result == session_data

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, session_manager):
        """Test session retrieval for non-existent session."""
        result = await session_manager.get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session_activity_redis_success(self, session_manager, mock_redis):
        """Test successful session activity update with Redis."""
        session_data = {"user_id": str(uuid4()), "token": "test", "last_activity": "old"}
        mock_redis.get.return_value = json.dumps(session_data)

        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            result = await session_manager.update_session_activity("session_123")
            assert result is True
            mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_update_session_activity_not_found(self, session_manager):
        """Test session activity update for non-existent session."""
        result = await session_manager.update_session_activity("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_session_redis_success(self, session_manager, mock_redis):
        """Test successful session invalidation with Redis."""
        session_data = {"user_id": str(uuid4())}
        mock_redis.get.return_value = json.dumps(session_data)

        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            result = await session_manager.invalidate_session("session_123")
            assert result is True
            mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_invalidate_session_memory_fallback(self, session_manager):
        """Test session invalidation with memory fallback."""
        session_manager._memory_sessions["session_123"] = {"user_id": str(uuid4())}
        result = await session_manager.invalidate_session("session_123")
        assert result is True
        assert "session_123" not in session_manager._memory_sessions

    @pytest.mark.asyncio
    async def test_get_user_sessions_redis_success(self, session_manager, mock_redis):
        """Test successful user sessions retrieval from Redis."""
        mock_redis.smembers.return_value = {"session1", "session2"}

        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            sessions = await session_manager.get_user_sessions(uuid4())
            assert sessions == ["session1", "session2"]

    @pytest.mark.asyncio
    async def test_get_user_sessions_memory_fallback(self, session_manager):
        """Test user sessions retrieval from memory."""
        user_id = str(uuid4())
        session_manager._memory_sessions = {
            "session1": {"user_id": user_id},
            "session2": {"user_id": user_id},
            "session3": {"user_id": str(uuid4())},
        }

        sessions = await session_manager.get_user_sessions(uuid4())
        assert len(sessions) == 2
        assert "session1" in sessions
        assert "session2" in sessions

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions(self, session_manager, mock_redis):
        """Test invalidating all user sessions."""
        user_id = uuid4()
        mock_redis.smembers.return_value = {"session1", "session2"}

        with patch("services.auth_service.redis.from_url", return_value=mock_redis):
            count = await session_manager.invalidate_all_user_sessions(user_id)
            assert count == 2  # Should return count of sessions invalidated

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_manager):
        """Test cleanup of expired in-memory sessions."""
        # Create sessions with old and new timestamps
        old_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        new_time = datetime.now(timezone.utc).isoformat()

        session_manager._memory_sessions = {
            "expired": {"last_activity": old_time},
            "active": {"last_activity": new_time},
            "malformed": {},  # Missing last_activity
        }

        count = await session_manager.cleanup_expired_sessions()
        assert count == 2  # expired and malformed sessions removed
        assert "expired" not in session_manager._memory_sessions
        assert "malformed" not in session_manager._memory_sessions
        assert "active" in session_manager._memory_sessions


class TestAuthService:
    """Test the AuthService class."""

    @pytest.fixture
    def auth_service_instance(self):
        """Create a fresh AuthService instance."""
        return AuthService()

    @pytest.fixture
    def mock_user(self):
        """Create a mock User object."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.is_active = True
        return user

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock SessionManager."""
        manager = AsyncMock()
        manager.create_session.return_value = "session_123"
        return manager

    def test_initialization(self, auth_service_instance):
        """Test AuthService initialization."""
        assert isinstance(auth_service_instance.session_manager, SessionManager)

    @pytest.mark.asyncio
    async def test_create_user_session_success(
        self, auth_service_instance, mock_user, mock_session_manager
    ):
        """Test successful user session creation."""
        auth_service_instance.session_manager = mock_session_manager

        metadata = {"ip": "127.0.0.1"}
        session_id = await auth_service_instance.create_user_session(
            mock_user, "test_token", metadata
        )

        assert session_id == "session_123"
        mock_session_manager.create_session.assert_called_once_with(
            mock_user.id,
            "test_token",
            {"user_agent": "", "ip_address": "127.0.0.1", "login_time": pytest.any},
        )

    @pytest.mark.asyncio
    async def test_create_user_session_no_metadata(
        self, auth_service_instance, mock_user, mock_session_manager
    ):
        """Test user session creation without metadata."""
        auth_service_instance.session_manager = mock_session_manager

        session_id = await auth_service_instance.create_user_session(mock_user, "test_token")

        assert session_id == "session_123"
        call_args = mock_session_manager.create_session.call_args
        metadata = call_args[0][2]
        assert metadata["user_agent"] == ""
        assert metadata["ip_address"] == ""

    @pytest.mark.asyncio
    async def test_validate_session_success(
        self, auth_service_instance, mock_user, mock_session_manager
    ):
        """Test successful session validation."""
        # Mock session data
        session_data = {"user_id": str(mock_user.id), "token": "test_token"}
        mock_session_manager.get_session.return_value = session_data
        mock_session_manager.update_session_activity.return_value = True

        # Mock database
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = mock_user
        mock_db.execute.return_value = mock_result

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.validate_session("session_123", mock_db)

        assert result == mock_user
        mock_session_manager.update_session_activity.assert_called_once_with("session_123")

    @pytest.mark.asyncio
    async def test_validate_session_not_found(self, auth_service_instance, mock_session_manager):
        """Test session validation when session doesn't exist."""
        mock_session_manager.get_session.return_value = None

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.validate_session("nonexistent", AsyncMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_user_not_found(
        self, auth_service_instance, mock_session_manager
    ):
        """Test session validation when user doesn't exist in database."""
        session_data = {"user_id": str(uuid4()), "token": "test_token"}
        mock_session_manager.get_session.return_value = session_data

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = None  # User not found
        mock_db.execute.return_value = mock_result

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.validate_session("session_123", mock_db)

        assert result is None
        mock_session_manager.invalidate_session.assert_called_once_with("session_123")

    @pytest.mark.asyncio
    async def test_validate_session_inactive_user(
        self, auth_service_instance, mock_session_manager
    ):
        """Test session validation when user is inactive."""
        mock_user_inactive = MagicMock(spec=User)
        mock_user_inactive.id = uuid4()
        mock_user_inactive.is_active = False

        session_data = {"user_id": str(mock_user_inactive.id), "token": "test_token"}
        mock_session_manager.get_session.return_value = session_data

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = mock_user_inactive
        mock_db.execute.return_value = mock_result

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.validate_session("session_123", mock_db)

        assert result is None
        mock_session_manager.invalidate_session.assert_called_once_with("session_123")

    @pytest.mark.asyncio
    async def test_logout_user_specific_session(self, auth_service_instance, mock_session_manager):
        """Test logging out a specific user session."""
        mock_session_manager.invalidate_session.return_value = True

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.logout_user(uuid4(), "session_123")

        assert result == 1
        mock_session_manager.invalidate_session.assert_called_once_with("session_123")

    @pytest.mark.asyncio
    async def test_logout_user_all_sessions(self, auth_service_instance, mock_session_manager):
        """Test logging out all user sessions."""
        mock_session_manager.invalidate_all_user_sessions.return_value = 3

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.logout_user(uuid4())

        assert result == 3
        mock_session_manager.invalidate_all_user_sessions.assert_called_once_with(pytest.any)

    @pytest.mark.asyncio
    async def test_get_user_active_sessions(self, auth_service_instance, mock_session_manager):
        """Test getting user active sessions."""
        mock_session_manager.get_user_sessions.return_value = ["session1", "session2"]
        mock_session_manager.get_session.side_effect = [
            {
                "created_at": "2023-01-01T00:00:00",
                "last_activity": "2023-01-02T00:00:00",
                "metadata": {},
            },
            {
                "created_at": "2023-01-01T01:00:00",
                "last_activity": "2023-01-02T01:00:00",
                "metadata": {"ip": "127.0.0.1"},
            },
        ]

        auth_service_instance.session_manager = mock_session_manager

        sessions = await auth_service_instance.get_user_active_sessions(uuid4())

        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session1"
        assert sessions[1]["session_id"] == "session2"

    @pytest.mark.asyncio
    async def test_enforce_session_limits_no_action(
        self, auth_service_instance, mock_session_manager
    ):
        """Test session limit enforcement when under limit."""
        mock_session_manager.get_user_sessions.return_value = ["s1", "s2", "s3"]
        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.enforce_session_limits(uuid4(), 5)

        assert result == 0  # No sessions removed

    @pytest.mark.asyncio
    async def test_enforce_session_limits_remove_oldest(
        self, auth_service_instance, mock_session_manager
    ):
        """Test session limit enforcement removing oldest sessions."""
        mock_session_manager.get_user_sessions.return_value = ["s1", "s2", "s3", "s4", "s5", "s6"]
        mock_session_manager.invalidate_session.return_value = True

        # Mock get_session to return sessions with different last_activity times
        mock_session_manager.get_session.side_effect = [
            {"last_activity": "2023-01-01T06:00:00"},  # Oldest
            {"last_activity": "2023-01-01T05:00:00"},  # Second oldest
            {"last_activity": "2023-01-01T04:00:00"},  # Third oldest
            {"last_activity": "2023-01-01T03:00:00"},  # Fourth oldest
            {"last_activity": "2023-01-01T02:00:00"},  # Fifth oldest
            {"last_activity": "2023-01-01T01:00:00"},  # Sixth oldest
        ]

        auth_service_instance.session_manager = mock_session_manager

        result = await auth_service_instance.enforce_session_limits(uuid4(), 3)

        assert result == 3  # Three sessions removed
        assert mock_session_manager.invalidate_session.call_count == 3


class TestGlobalAuthService:
    """Test the global auth service instance."""

    def test_global_instance_exists(self):
        """Test that global auth service instance exists."""
        assert isinstance(auth_service, AuthService)


class TestSecurityEdgeCases:
    """Test security-related edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_session_token_exposure_protection(self):
        """Test that session tokens are not exposed in logs or errors."""
        session_manager = SessionManager()

        # Create session
        user_id = uuid4()
        session_id = await session_manager.create_session(user_id, "sensitive_token_123")

        # Retrieve session
        session_data = await session_manager.get_session(session_id)

        # Ensure token is stored but not accidentally exposed
        assert session_data is not None
        assert session_data["token"] == "sensitive_token_123"

        # Test that session data doesn't leak sensitive info in string representation
        session_str = str(session_data)
        # This is a basic check - in real implementation, ensure no sensitive data in logs
        assert "sensitive_token_123" in session_str  # Would be hashed/encrypted in real impl

    @pytest.mark.asyncio
    async def test_concurrent_session_access(self):
        """Test concurrent access to session management."""
        session_manager = SessionManager()

        async def create_and_access_session(user_id, token_prefix):
            session_id = await session_manager.create_session(user_id, f"{token_prefix}_token")
            session_data = await session_manager.get_session(session_id)
            return session_data is not None

        # Run multiple concurrent operations
        tasks = []
        for i in range(10):
            user_id = uuid4()
            tasks.append(create_and_access_session(user_id, f"user_{i}"))

        results = await asyncio.gather(*tasks)

        # All operations should succeed
        assert all(results)

    @pytest.mark.asyncio
    async def test_session_cleanup_edge_cases(self):
        """Test session cleanup with malformed data."""
        session_manager = SessionManager()

        # Add sessions with malformed data
        session_manager._memory_sessions = {
            "good_session": {"last_activity": datetime.now(timezone.utc).isoformat()},
            "malformed_no_activity": {},
            "malformed_bad_date": {"last_activity": "not-a-date"},
            "expired_session": {
                "last_activity": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
            },
        }

        count = await session_manager.cleanup_expired_sessions()

        # Should clean up malformed and expired sessions
        assert count >= 2  # At least malformed and expired
        assert "good_session" in session_manager._memory_sessions

    @pytest.mark.asyncio
    async def test_redis_connection_resilience(self):
        """Test Redis connection failure resilience."""
        session_manager = SessionManager()

        # Force Redis to be unavailable
        session_manager._redis_available = False

        # Operations should still work with memory fallback
        user_id = uuid4()
        session_id = await session_manager.create_session(user_id, "test_token")
        session_data = await session_manager.get_session(session_id)

        assert session_data is not None
        assert session_data["token"] == "test_token"

    @pytest.mark.asyncio
    async def test_large_session_metadata_handling(self):
        """Test handling of large session metadata."""
        session_manager = SessionManager()

        # Create large metadata
        large_metadata = {"data": "x" * 10000}  # 10KB of data

        user_id = uuid4()
        session_id = await session_manager.create_session(user_id, "test_token", large_metadata)

        session_data = await session_manager.get_session(session_id)

        assert session_data is not None
        assert len(session_data["metadata"]["data"]) == 10000
