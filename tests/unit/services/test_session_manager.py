"""Unit tests for services/session_manager.py."""

# pyright: reportPrivateUsage=false, reportMissingImports=false, reportUnusedImport=false

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services import session_manager as session_manager_module
from services.session_manager import SessionData, SessionManager


class FakeRedis:
    """Small async Redis stub for session manager tests."""

    def __init__(self):
        self.store = {}
        self.ttls = {}
        self.scan_sequences = []

    @staticmethod
    def _normalize_key(key):
        if isinstance(key, bytes):
            return key.decode()
        return key

    @staticmethod
    def _encode(value):
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode()
        return str(value).encode()

    async def scan(self, cursor, match=None, count=100):
        _ = (cursor, count)
        if self.scan_sequences:
            return self.scan_sequences.pop(0)

        prefix = None
        if match and match.endswith("*"):
            prefix = match[:-1]

        keys = []
        for key in self.store:
            if prefix is None or key.startswith(prefix):
                keys.append(key.encode())
        return 0, keys

    async def get(self, key):
        return self.store.get(self._normalize_key(key))

    async def setex(self, key, ttl, value):
        normalized_key = self._normalize_key(key)
        self.store[normalized_key] = self._encode(value)
        self.ttls[normalized_key] = ttl

    async def delete(self, key):
        normalized_key = self._normalize_key(key)
        self.store.pop(normalized_key, None)
        self.ttls.pop(normalized_key, None)

    async def ttl(self, key):
        return self.ttls.get(self._normalize_key(key), -1)


@pytest.fixture
def redis_stub():
    return FakeRedis()


@pytest.fixture(autouse=True)
def reset_global_session_manager():
    original = session_manager_module._session_manager
    session_manager_module._session_manager = None
    yield
    session_manager_module._session_manager = original


class TestSessionData:
    def test_calculate_checksum_is_stable_for_sorted_data(self):
        left = SessionData(session_id="s1", user_id="u1", data={"b": 2, "a": 1})
        right = SessionData(session_id="s2", user_id="u2", data={"a": 1, "b": 2})

        assert left.calculate_checksum() == right.calculate_checksum()

    def test_verify_integrity_detects_tampered_data(self):
        session = SessionData(session_id="s1", user_id="u1", data={"a": 1})
        session.checksum = session.calculate_checksum()

        assert session.verify_integrity() is True

        session.data["a"] = 2

        assert session.verify_integrity() is False


@pytest.mark.asyncio
class TestSessionManager:
    async def test_load_active_sessions_scans_multiple_batches(self, redis_stub):
        redis_stub.scan_sequences = [
            (1, [b"session:one", b"session:two"]),
            (0, [b"session:three"]),
        ]
        manager = SessionManager(redis_client=redis_stub)

        await manager._load_active_sessions()

        assert manager._active_sessions == {"one", "two", "three"}

    async def test_create_session_stores_session_and_updates_metrics(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        collector = MagicMock()

        with patch("monitoring.metrics.get_metrics_collector", return_value=collector):
            session = await manager.create_session("user-1", {"role": "admin"})

        stored = redis_stub.store[f"session:{session.session_id}"]

        assert session.user_id == "user-1"
        assert session.data == {"role": "admin"}
        assert session.session_id in manager._active_sessions
        assert b'"role":"admin"' in stored
        collector.update_session_count.assert_called_once_with(1)

    async def test_get_session_restores_from_backup_after_integrity_failure(self, redis_stub):
        session = SessionData(session_id="broken", user_id="u1", data={"x": 1})
        session.checksum = "invalid"
        await redis_stub.setex("session:broken", 60, session.json())

        restored = SessionData(session_id="broken", user_id="u1", data={"x": 99})
        manager = SessionManager(redis_client=redis_stub)
        manager._restore_from_backup = AsyncMock(return_value=restored)
        manager._store_session = AsyncMock()

        result = await manager.get_session("broken")

        assert result is restored
        manager._restore_from_backup.assert_awaited_once_with("broken")
        manager._store_session.assert_awaited_once()

    async def test_update_session_backs_up_and_merges_data(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        session = SessionData(session_id="sess-1", user_id="u1", data={"a": 1})
        session.checksum = session.calculate_checksum()
        manager.get_session = AsyncMock(return_value=session)
        manager._backup_session = AsyncMock()
        manager._store_session = AsyncMock()

        result = await manager.update_session("sess-1", {"b": 2})

        assert result is True
        assert session.data == {"a": 1, "b": 2}
        assert session.checksum == session.calculate_checksum()
        manager._backup_session.assert_awaited_once_with(session)
        manager._store_session.assert_awaited_once_with(session)

    async def test_delete_session_backs_up_removes_key_and_updates_metrics(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        manager._active_sessions.add("sess-1")
        session = SessionData(session_id="sess-1", user_id="u1")
        manager.get_session = AsyncMock(return_value=session)
        manager._backup_session = AsyncMock()
        collector = MagicMock()

        with patch("monitoring.metrics.get_metrics_collector", return_value=collector):
            result = await manager.delete_session("sess-1")

        assert result is True
        assert "sess-1" not in manager._active_sessions
        manager._backup_session.assert_awaited_once_with(session)
        collector.update_session_count.assert_called_once_with(0)

    async def test_backup_all_sessions_counts_missing_sessions_as_failures(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        manager._active_sessions.update({"good", "missing"})
        good_session = SessionData(session_id="good", user_id="u1")

        async def get_session_side_effect(session_id):
            if session_id == "good":
                return good_session
            return None

        manager.get_session = AsyncMock(side_effect=get_session_side_effect)
        manager._backup_session = AsyncMock()

        stats = await manager.backup_all_sessions()

        assert stats["total"] == 2
        assert stats["backed_up"] == 1
        assert stats["failed"] == 1
        assert "duration" in stats
        manager._backup_session.assert_awaited_once_with(good_session)

    async def test_restore_all_sessions_restores_scanned_backups(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        redis_stub.scan_sequences = [(0, [b"backup:version:one", b"backup:version:two"])]
        first = SessionData(session_id="one", user_id="u1")

        async def restore_side_effect(session_id):
            if session_id == "one":
                return first
            return None

        manager._restore_from_backup = AsyncMock(side_effect=restore_side_effect)
        manager._store_session = AsyncMock()
        collector = MagicMock()

        with patch("monitoring.metrics.get_metrics_collector", return_value=collector):
            stats = await manager.restore_all_sessions()

        assert stats["total"] == 2
        assert stats["restored"] == 1
        assert stats["failed"] == 1
        assert manager._active_sessions == {"one"}
        manager._store_session.assert_awaited_once_with(first)
        collector.update_session_count.assert_called_once_with(1)

    async def test_preserve_sessions_restores_and_re_raises_on_error(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        manager.backup_all_sessions = AsyncMock(return_value={"backed_up": 1})
        manager.restore_all_sessions = AsyncMock(return_value={"restored": 1})
        manager._cleanup_old_backups = AsyncMock()

        with pytest.raises(RuntimeError, match="boom"):
            async with manager.preserve_sessions():
                raise RuntimeError("boom")

        manager.backup_all_sessions.assert_awaited_once()
        manager.restore_all_sessions.assert_awaited_once()
        manager._cleanup_old_backups.assert_awaited_once()

    async def test_cleanup_old_backups_deletes_invalid_ttl_entries(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        redis_stub.store.update(
            {
                "backup:session:old": b"x",
                "backup:session:future": b"y",
                "backup:session:good": b"z",
            }
        )
        redis_stub.ttls.update(
            {
                "backup:session:old": -1,
                "backup:session:future": manager.backup_ttl + 1,
                "backup:session:good": manager.backup_ttl,
            }
        )

        await manager._cleanup_old_backups()

        assert "backup:session:old" not in redis_stub.store
        assert "backup:session:future" not in redis_stub.store
        assert "backup:session:good" in redis_stub.store

    async def test_get_session_stats_calculates_average_age(self, redis_stub):
        manager = SessionManager(redis_client=redis_stub)
        manager._active_sessions.update({"young", "old"})
        now = datetime.now(timezone.utc)
        young = SessionData(session_id="young", user_id="u1", created_at=now - timedelta(seconds=10))
        old = SessionData(session_id="old", user_id="u2", created_at=now - timedelta(seconds=30))

        async def get_session_side_effect(session_id):
            return {"young": young, "old": old}[session_id]

        manager.get_session = AsyncMock(side_effect=get_session_side_effect)

        stats = await manager.get_session_stats()

        assert stats["active_sessions"] == 2
        assert 15 <= stats["average_session_age_seconds"] <= 35
        assert stats["backup_in_progress"] is False
        assert stats["restore_in_progress"] is False


@pytest.mark.asyncio
async def test_get_session_manager_initializes_singleton_once():
    fake_manager = SessionManager(redis_client=FakeRedis())

    with patch.object(SessionManager, "initialize", new=AsyncMock()) as initialize_mock:
        with patch.object(session_manager_module, "SessionManager", return_value=fake_manager):
            first = await session_manager_module.get_session_manager()
            second = await session_manager_module.get_session_manager()

    assert first is second is fake_manager
    initialize_mock.assert_awaited_once()