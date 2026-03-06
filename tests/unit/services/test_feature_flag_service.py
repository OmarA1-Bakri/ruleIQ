"""
Unit tests for services/feature_flag_service.py — EnhancedFeatureFlagService
_evaluate_flag pure function, hash consistency, and FeatureFlagConfig.

All Redis and DB interactions are mocked.
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.feature_flag_service import (
    EnhancedFeatureFlagService,
    FeatureFlagConfig,
    EvaluationReason,
    FeatureNotEnabledException,
)


# ---------------------------------------------------------------------------
# FeatureFlagConfig validation
# ---------------------------------------------------------------------------

class TestFeatureFlagConfig:
    """Tests for FeatureFlagConfig Pydantic model."""

    def test_defaults(self):
        cfg = FeatureFlagConfig(name="test_flag")
        assert cfg.enabled is False
        assert cfg.percentage == 0.0
        assert cfg.whitelist == []
        assert cfg.blacklist == []
        assert cfg.environments == ["development"]

    def test_percentage_validation_min(self):
        cfg = FeatureFlagConfig(name="test", percentage=0.0)
        assert cfg.percentage == 0.0

    def test_percentage_validation_max(self):
        cfg = FeatureFlagConfig(name="test", percentage=100.0)
        assert cfg.percentage == 100.0

    def test_percentage_out_of_range(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeatureFlagConfig(name="test", percentage=101.0)

    def test_percentage_negative(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeatureFlagConfig(name="test", percentage=-1.0)

    def test_full_config(self):
        cfg = FeatureFlagConfig(
            name="advanced_flag",
            enabled=True,
            percentage=50.0,
            whitelist=["user1"],
            blacklist=["user2"],
            environment_overrides={"staging": False},
            environments=["production", "staging"],
            metadata={"description": "A test flag"},
        )
        assert cfg.enabled is True
        assert cfg.percentage == 50.0


# ---------------------------------------------------------------------------
# EvaluationReason enum
# ---------------------------------------------------------------------------

class TestEvaluationReason:
    """Tests for EvaluationReason enum values."""

    def test_all_reasons_exist(self):
        assert EvaluationReason.WHITELIST == "whitelist"
        assert EvaluationReason.BLACKLIST == "blacklist"
        assert EvaluationReason.PERCENTAGE == "percentage"
        assert EvaluationReason.ENVIRONMENT == "environment"
        assert EvaluationReason.EXPIRED == "expired"
        assert EvaluationReason.NOT_STARTED == "not_started"
        assert EvaluationReason.ENABLED == "enabled"
        assert EvaluationReason.DISABLED == "disabled"
        assert EvaluationReason.NOT_FOUND == "not_found"


# ---------------------------------------------------------------------------
# _evaluate_flag — pure function tests
# ---------------------------------------------------------------------------

class TestEvaluateFlag:
    """Tests for _evaluate_flag() pure function."""

    def _make_service(self):
        mock_redis = MagicMock()
        mock_config = MagicMock()
        mock_config.REDIS_URL = "redis://localhost:6379"
        return EnhancedFeatureFlagService(
            redis_client=mock_redis,
            db_session=MagicMock(),
            config=mock_config,
        )

    def test_disabled_flag(self):
        svc = self._make_service()
        flag_data = {"enabled": False, "percentage": 0}
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is False
        assert reason == EvaluationReason.DISABLED

    def test_enabled_100_percent(self):
        svc = self._make_service()
        flag_data = {"enabled": True, "percentage": 100}
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is True
        assert reason == EvaluationReason.ENABLED

    def test_enabled_0_percent(self):
        svc = self._make_service()
        flag_data = {"enabled": True, "percentage": 0}
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        # No user_id and enabled, but percentage is 0 -> disabled
        assert result is False
        assert reason == EvaluationReason.DISABLED

    def test_blacklisted_user(self):
        svc = self._make_service()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "blacklist": ["blocked_user"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id="blocked_user", environment="production")
        assert result is False
        assert reason == EvaluationReason.BLACKLIST

    def test_whitelisted_user(self):
        svc = self._make_service()
        flag_data = {
            "enabled": False,
            "percentage": 0,
            "whitelist": ["vip_user"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id="vip_user", environment="production")
        assert result is True
        assert reason == EvaluationReason.WHITELIST

    def test_blacklist_takes_priority_over_whitelist(self):
        svc = self._make_service()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "whitelist": ["user1"],
            "blacklist": ["user1"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id="user1", environment="production")
        assert result is False
        assert reason == EvaluationReason.BLACKLIST

    def test_wrong_environment(self):
        svc = self._make_service()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "environments": ["staging"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is False
        assert reason == EvaluationReason.ENVIRONMENT

    def test_correct_environment(self):
        svc = self._make_service()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "environments": ["production"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is True

    def test_environment_override_true(self):
        svc = self._make_service()
        flag_data = {
            "enabled": False,
            "percentage": 0,
            "environment_overrides": {"staging": True},
            "environments": ["staging"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="staging")
        assert result is True
        assert reason == EvaluationReason.ENVIRONMENT

    def test_environment_override_false(self):
        svc = self._make_service()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "environment_overrides": {"production": False},
            "environments": ["production"],
        }
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is False
        assert reason == EvaluationReason.ENVIRONMENT

    def test_expired_flag(self):
        svc = self._make_service()
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "expires_at": past,
        }
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is False
        assert reason == EvaluationReason.EXPIRED

    def test_not_started_flag(self):
        svc = self._make_service()
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        flag_data = {
            "enabled": True,
            "percentage": 100,
            "starts_at": future,
        }
        result, reason = svc._evaluate_flag(flag_data, user_id=None, environment="production")
        assert result is False
        assert reason == EvaluationReason.NOT_STARTED

    def test_percentage_rollout_deterministic(self):
        svc = self._make_service()
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 50,
        }
        # Same user should always get same result
        r1, _ = svc._evaluate_flag(flag_data, user_id="user123", environment="production")
        r2, _ = svc._evaluate_flag(flag_data, user_id="user123", environment="production")
        assert r1 == r2

    def test_percentage_rollout_varies_by_user(self):
        svc = self._make_service()
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 50,
        }
        # Test with many users — should get a mix
        results = set()
        for i in range(100):
            r, _ = svc._evaluate_flag(flag_data, user_id=f"user_{i}", environment="production")
            results.add(r)
        # With 100 users at 50%, both True and False should appear
        assert True in results
        assert False in results


# ---------------------------------------------------------------------------
# Hash consistency
# ---------------------------------------------------------------------------

class TestHashUserID:
    """Tests for _hash_user_id consistency."""

    def _make_service(self):
        mock_redis = MagicMock()
        mock_config = MagicMock()
        mock_config.REDIS_URL = "redis://localhost:6379"
        return EnhancedFeatureFlagService(redis_client=mock_redis, db_session=MagicMock(), config=mock_config)

    def test_deterministic(self):
        svc = self._make_service()
        h1 = svc._hash_user_id("flag1", "user1")
        h2 = svc._hash_user_id("flag1", "user1")
        assert h1 == h2

    def test_different_users(self):
        svc = self._make_service()
        h1 = svc._hash_user_id("flag1", "user1")
        h2 = svc._hash_user_id("flag1", "user2")
        # May be different (not guaranteed, but highly likely)
        # Just check they're in range
        assert 0 <= h1 < 100
        assert 0 <= h2 < 100

    def test_different_flags(self):
        svc = self._make_service()
        h1 = svc._hash_user_id("flagA", "user1")
        h2 = svc._hash_user_id("flagB", "user1")
        assert 0 <= h1 < 100
        assert 0 <= h2 < 100

    def test_range(self):
        svc = self._make_service()
        for i in range(200):
            h = svc._hash_user_id("flag", f"user_{i}")
            assert 0 <= h < 100


# ---------------------------------------------------------------------------
# Cache key generation
# ---------------------------------------------------------------------------

class TestCacheKeys:
    """Tests for cache key generation."""

    def _make_service(self):
        mock_config = MagicMock()
        mock_config.REDIS_URL = "redis://localhost:6379"
        return EnhancedFeatureFlagService(
            redis_client=MagicMock(), db_session=MagicMock(), config=mock_config,
        )

    def test_flag_cache_key(self):
        svc = self._make_service()
        assert svc._get_cache_key("my_flag") == "ff:my_flag"

    def test_user_cache_key(self):
        svc = self._make_service()
        assert svc._get_user_cache_key("my_flag", "user1") == "ff:my_flag:user:user1"


# ---------------------------------------------------------------------------
# FeatureNotEnabledException
# ---------------------------------------------------------------------------

class TestFeatureNotEnabledException:
    """Tests for custom exception."""

    def test_exception_message(self):
        exc = FeatureNotEnabledException("Feature X is disabled")
        assert str(exc) == "Feature X is disabled"

    def test_inherits_from_exception(self):
        assert issubclass(FeatureNotEnabledException, Exception)
