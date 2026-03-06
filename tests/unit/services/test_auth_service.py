"""
Unit tests for services/auth_service.py — SessionManager and AuthService.

Redis is mocked; tests exercise the in-memory fallback path
and the Redis-backed path (via mock).
"""

import os
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")


# ---------------------------------------------------------------------------
# SessionManager — in-memory fallback
# ---------------------------------------------------------------------------

class TestSessionManagerInMemory:
    """Tests for SessionManager using in-memory fallback (no Redis)."""

    def _make_manager(self):
        from services.auth_service import SessionManager
        mgr = SessionManager()
        mgr._redis_available = False  # Force in-memory mode
        return mgr

    @pytest.mark.asyncio
    async def test_create_session(self):
        mgr = self._make_manager()
        session_id = await mgr.create_session(
            user_id=uuid4(),
            token="fake-token",
            metadata={"ip": "127.0.0.1"},
        )
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID length

    @pytest.mark.asyncio
    async def test_get_session_returns_data(self):
        mgr = self._make_manager()
        uid = uuid4()
        session_id = await mgr.create_session(uid, "tok")
        data = await mgr.get_session(session_id)
        assert data is not None
        assert data["user_id"] == str(uid)
        assert data["token"] == "tok"
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_none(self):
        mgr = self._make_manager()
        data = await mgr.get_session("nonexistent-id")
        assert data is None

    @pytest.mark.asyncio
    async def test_update_session_activity(self):
        mgr = self._make_manager()
        session_id = await mgr.create_session(uuid4(), "tok")
        old_data = await mgr.get_session(session_id)
        old_activity = old_data["last_activity"]

        result = await mgr.update_session_activity(session_id)
        assert result is True

        new_data = await mgr.get_session(session_id)
        # Activity timestamp should be updated
        assert new_data["last_activity"] >= old_activity

    @pytest.mark.asyncio
    async def test_update_nonexistent_session_returns_false(self):
        mgr = self._make_manager()
        result = await mgr.update_session_activity("fake-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_session(self):
        mgr = self._make_manager()
        session_id = await mgr.create_session(uuid4(), "tok")
        result = await mgr.invalidate_session(session_id)
        assert result is True

        # Session should be gone
        data = await mgr.get_session(session_id)
        assert data is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_session_returns_false(self):
        mgr = self._make_manager()
        result = await mgr.invalidate_session("fake-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_sessions(self):
        mgr = self._make_manager()
        uid = uuid4()
        s1 = await mgr.create_session(uid, "tok1")
        s2 = await mgr.create_session(uid, "tok2")
        _ = await mgr.create_session(uuid4(), "tok3")  # Different user

        sessions = await mgr.get_user_sessions(uid)
        assert s1 in sessions
        assert s2 in sessions
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions(self):
        mgr = self._make_manager()
        uid = uuid4()
        await mgr.create_session(uid, "tok1")
        await mgr.create_session(uid, "tok2")

        count = await mgr.invalidate_all_user_sessions(uid)
        assert count == 2

        sessions = await mgr.get_user_sessions(uid)
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_no_expired(self):
        mgr = self._make_manager()
        await mgr.create_session(uuid4(), "tok")
        count = await mgr.cleanup_expired_sessions()
        assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_with_expired(self):
        mgr = self._make_manager()
        # Manually insert an expired session
        old_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        mgr._memory_sessions["old-session"] = {
            "user_id": str(uuid4()),
            "token": "old",
            "last_activity": old_time,
        }
        count = await mgr.cleanup_expired_sessions()
        assert count == 1
        assert "old-session" not in mgr._memory_sessions

    @pytest.mark.asyncio
    async def test_cleanup_sessions_with_bad_timestamp(self):
        mgr = self._make_manager()
        mgr._memory_sessions["bad-session"] = {
            "user_id": str(uuid4()),
            "token": "bad",
            "last_activity": "not-a-date",
        }
        count = await mgr.cleanup_expired_sessions()
        assert count == 1

    @pytest.mark.asyncio
    async def test_cleanup_empty_returns_zero(self):
        mgr = self._make_manager()
        count = await mgr.cleanup_expired_sessions()
        assert count == 0


# ---------------------------------------------------------------------------
# SessionManager — Redis path (mocked)
# ---------------------------------------------------------------------------

class TestSessionManagerRedis:
    """Tests for SessionManager with mocked Redis."""

    def _make_manager_with_redis(self):
        from services.auth_service import SessionManager
        mgr = SessionManager()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mgr._redis_client = mock_redis
        mgr._redis_available = True
        return mgr, mock_redis

    @pytest.mark.asyncio
    async def test_create_session_calls_redis_setex(self):
        mgr, mock_redis = self._make_manager_with_redis()
        session_id = await mgr.create_session(uuid4(), "tok")

        mock_redis.setex.assert_awaited_once()
        mock_redis.sadd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_session_from_redis(self):
        mgr, mock_redis = self._make_manager_with_redis()
        uid = uuid4()
        session_data = {
            "user_id": str(uid),
            "token": "tok",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(session_data))

        result = await mgr.get_session("some-session-id")
        assert result is not None
        assert result["user_id"] == str(uid)

    @pytest.mark.asyncio
    async def test_invalidate_session_redis(self):
        mgr, mock_redis = self._make_manager_with_redis()
        uid = uuid4()
        session_data = {
            "user_id": str(uid),
            "token": "tok",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(session_data))

        result = await mgr.invalidate_session("sess-id")
        assert result is True
        mock_redis.delete.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_user_sessions_redis(self):
        mgr, mock_redis = self._make_manager_with_redis()
        mock_redis.smembers = AsyncMock(return_value={"s1", "s2"})
        sessions = await mgr.get_user_sessions(uuid4())
        assert len(sessions) == 2


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------

class TestAuthService:
    """Tests for AuthService top-level methods."""

    def _make_service(self):
        from services.auth_service import AuthService
        svc = AuthService()
        svc.session_manager._redis_available = False  # Use in-memory
        return svc

    @pytest.mark.asyncio
    async def test_create_user_session(self):
        svc = self._make_service()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        session_id = await svc.create_user_session(
            user=mock_user,
            token="access-token",
            metadata={"user_agent": "Mozilla", "ip_address": "10.0.0.1"},
        )
        assert isinstance(session_id, str)

    @pytest.mark.asyncio
    async def test_logout_specific_session(self):
        svc = self._make_service()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        session_id = await svc.create_user_session(mock_user, "tok")
        count = await svc.logout_user(mock_user.id, session_id=session_id)
        assert count == 1

    @pytest.mark.asyncio
    async def test_logout_all_sessions(self):
        svc = self._make_service()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        await svc.create_user_session(mock_user, "tok1")
        await svc.create_user_session(mock_user, "tok2")

        count = await svc.logout_user(mock_user.id)
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_user_active_sessions(self):
        svc = self._make_service()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        await svc.create_user_session(mock_user, "tok1")
        await svc.create_user_session(mock_user, "tok2")

        sessions = await svc.get_user_active_sessions(mock_user.id)
        assert len(sessions) == 2
        assert "session_id" in sessions[0]
        assert "created_at" in sessions[0]

    @pytest.mark.asyncio
    async def test_enforce_session_limits_within_limit(self):
        svc = self._make_service()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        await svc.create_user_session(mock_user, "tok1")
        await svc.create_user_session(mock_user, "tok2")

        removed = await svc.enforce_session_limits(mock_user.id, max_sessions=5)
        assert removed == 0

    @pytest.mark.asyncio
    async def test_enforce_session_limits_exceeds(self):
        svc = self._make_service()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        # Create 4 sessions
        for i in range(4):
            await svc.create_user_session(mock_user, f"tok{i}")

        # Enforce limit of 2
        removed = await svc.enforce_session_limits(mock_user.id, max_sessions=2)
        assert removed == 2

        # Should only have 2 left
        sessions = await svc.get_user_active_sessions(mock_user.id)
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_validate_session_no_session(self):
        svc = self._make_service()
        mock_db = AsyncMock()
        result = await svc.validate_session("nonexistent", mock_db)
        assert result is None
