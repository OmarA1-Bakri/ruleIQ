"""
Unit tests for services/token_blacklist_service.py — TokenBlacklistService.

All Redis interactions are mocked.
"""

import os
import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.token_blacklist_service import TokenBlacklistService


# ---------------------------------------------------------------------------
# add_to_blacklist
# ---------------------------------------------------------------------------

class TestAddToBlacklist:
    """Tests for TokenBlacklistService.add_to_blacklist()."""

    def _make_service(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [True, True, True, True]
        mock_redis.pipeline.return_value = mock_pipe
        svc = TokenBlacklistService(redis_client=mock_redis)
        return svc, mock_redis, mock_pipe

    def test_successful_blacklist(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        result = svc.add_to_blacklist("jti-123", expiry, user_id="user-1")
        assert result is True
        pipe.setex.assert_called_once()
        pipe.sadd.assert_called_once()
        pipe.execute.assert_called_once()

    def test_expired_token_not_blacklisted(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        result = svc.add_to_blacklist("jti-old", expiry)
        assert result is True
        # Pipeline should NOT be used for already-expired tokens
        pipe.execute.assert_not_called()

    def test_redis_error_returns_false(self):
        import redis as redis_module
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = redis_module.RedisError("connection failed")
        svc = TokenBlacklistService(redis_client=mock_redis)
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        result = svc.add_to_blacklist("jti-fail", expiry)
        assert result is False

    def test_blacklist_data_includes_reason(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.add_to_blacklist("jti-reason", expiry, reason="security_breach")
        # Check the setex call payload
        call_args = pipe.setex.call_args
        payload = json.loads(call_args[0][2])
        assert payload["reason"] == "security_breach"
        assert payload["jti"] == "jti-reason"

    def test_blacklist_data_includes_user_id(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.add_to_blacklist("jti-user", expiry, user_id="usr-42")
        call_args = pipe.setex.call_args
        payload = json.loads(call_args[0][2])
        assert payload["user_id"] == "usr-42"

    def test_pipeline_uses_correct_key_prefix(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.add_to_blacklist("jti-prefix", expiry)
        call_args = pipe.setex.call_args
        key = call_args[0][0]
        assert key == "token_blacklist:jti-prefix"

    def test_pipeline_adds_to_active_set(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.add_to_blacklist("jti-set", expiry)
        pipe.sadd.assert_called_once_with("token_blacklist:active", "jti-set")

    def test_pipeline_increments_stats(self):
        svc, redis, pipe = self._make_service()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.add_to_blacklist("jti-stats", expiry, reason="logout")
        hincrby_calls = pipe.hincrby.call_args_list
        assert len(hincrby_calls) == 2
        # First: total_blacklisted
        assert hincrby_calls[0] == call("token_blacklist:stats", "total_blacklisted", 1)
        # Second: reason count
        assert hincrby_calls[1] == call("token_blacklist:stats", "reason:logout", 1)


# ---------------------------------------------------------------------------
# is_blacklisted
# ---------------------------------------------------------------------------

class TestIsBlacklisted:
    """Tests for TokenBlacklistService.is_blacklisted()."""

    def test_token_in_set_and_exists(self):
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = True
        mock_redis.exists.return_value = True
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.is_blacklisted("jti-active") is True
        mock_redis.hincrby.assert_called_with("token_blacklist:stats", "check_hits", 1)

    def test_token_in_set_but_expired(self):
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = True
        mock_redis.exists.return_value = False
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.is_blacklisted("jti-expired") is False
        # Should remove stale entry from set
        mock_redis.srem.assert_called_once_with("token_blacklist:active", "jti-expired")

    def test_token_not_in_set(self):
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.is_blacklisted("jti-unknown") is False
        mock_redis.hincrby.assert_called_with("token_blacklist:stats", "check_misses", 1)

    def test_redis_error_returns_false_by_default(self):
        import redis as redis_module
        mock_redis = MagicMock()
        mock_redis.sismember.side_effect = redis_module.RedisError("down")
        svc = TokenBlacklistService(redis_client=mock_redis)
        # Default fail-open behavior
        assert svc.is_blacklisted("jti-error") is False


# ---------------------------------------------------------------------------
# remove_from_blacklist
# ---------------------------------------------------------------------------

class TestRemoveFromBlacklist:
    """Tests for TokenBlacklistService.remove_from_blacklist()."""

    def test_remove_existing_token(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [1, 1, 1]  # delete, srem, hincrby
        mock_redis.pipeline.return_value = mock_pipe
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.remove_from_blacklist("jti-rm") is True

    def test_remove_nonexistent_token(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 0, 1]  # nothing deleted
        mock_redis.pipeline.return_value = mock_pipe
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.remove_from_blacklist("jti-gone") is False

    def test_remove_redis_error(self):
        import redis as redis_module
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = redis_module.RedisError("down")
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.remove_from_blacklist("jti-err") is False


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------

class TestCleanupExpired:
    """Tests for TokenBlacklistService.cleanup_expired()."""

    def test_cleanup_no_expired(self):
        mock_redis = MagicMock()
        mock_redis.smembers.return_value = {"jti-1", "jti-2"}
        mock_redis.exists.return_value = True  # All still valid
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.cleanup_expired() == 0

    def test_cleanup_some_expired(self):
        mock_redis = MagicMock()
        mock_redis.smembers.return_value = {"jti-good", "jti-bad"}
        mock_redis.exists.side_effect = [True, False]  # second is expired
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.cleanup_expired() == 1
        mock_redis.srem.assert_called_once()

    def test_cleanup_all_expired(self):
        mock_redis = MagicMock()
        mock_redis.smembers.return_value = {"jti-1", "jti-2", "jti-3"}
        mock_redis.exists.return_value = False
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.cleanup_expired() == 3

    def test_cleanup_empty_set(self):
        mock_redis = MagicMock()
        mock_redis.smembers.return_value = set()
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.cleanup_expired() == 0

    def test_cleanup_redis_error(self):
        import redis as redis_module
        mock_redis = MagicMock()
        mock_redis.smembers.side_effect = redis_module.RedisError("down")
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.cleanup_expired() == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Tests for TokenBlacklistService.get_stats()."""

    def test_returns_stats(self):
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "total_blacklisted": "42",
            "check_hits": "100",
            "check_misses": "50",
        }
        # scard returns a string-like value to match hgetall behavior
        mock_redis.scard.return_value = "10"
        svc = TokenBlacklistService(redis_client=mock_redis)
        stats = svc.get_stats()
        assert stats["total_blacklisted"] == 42
        assert stats["check_hits"] == 100
        assert stats["active_count"] == 10

    def test_redis_error_returns_empty(self):
        import redis as redis_module
        mock_redis = MagicMock()
        mock_redis.hgetall.side_effect = redis_module.RedisError("down")
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.get_stats() == {}


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------

class TestClearAll:
    """Tests for TokenBlacklistService.clear_all()."""

    def test_clear_with_keys(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter(["token_blacklist:jti-1", "token_blacklist:jti-2"])
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.clear_all() is True
        mock_redis.delete.assert_called()

    def test_clear_empty(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter([])
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.clear_all() is True

    def test_clear_redis_error(self):
        import redis as redis_module
        mock_redis = MagicMock()
        mock_redis.scan_iter.side_effect = redis_module.RedisError("down")
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.clear_all() is False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestConfiguration:
    """Tests for service configuration."""

    def test_default_prefixes(self):
        mock_redis = MagicMock()
        svc = TokenBlacklistService(redis_client=mock_redis)
        assert svc.blacklist_prefix == "token_blacklist:"
        assert svc.blacklist_set_key == "token_blacklist:active"
        assert svc.stats_key == "token_blacklist:stats"
