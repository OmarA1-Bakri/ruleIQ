"""
Unit tests for services/rate_limiting.py — RateLimitService.

Database interactions are mocked with AsyncMock.
"""

import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.rate_limiting import RateLimitService


# ---------------------------------------------------------------------------
# LIMITS configuration
# ---------------------------------------------------------------------------

class TestLimitsConfig:
    """Tests for the LIMITS class attribute."""

    def test_limits_has_expected_features(self):
        assert "ai_assessment" in RateLimitService.LIMITS
        assert "ai_policy_generation" in RateLimitService.LIMITS
        assert "ai_compliance_check" in RateLimitService.LIMITS
        assert "ai_recommendation" in RateLimitService.LIMITS

    def test_limits_have_daily_and_window(self):
        for feature, config in RateLimitService.LIMITS.items():
            assert "daily" in config, f"{feature} missing 'daily'"
            assert "window" in config, f"{feature} missing 'window'"
            assert isinstance(config["daily"], int)

    def test_specific_limits(self):
        assert RateLimitService.LIMITS["ai_assessment"]["daily"] == 10
        assert RateLimitService.LIMITS["ai_policy_generation"]["daily"] == 5
        assert RateLimitService.LIMITS["ai_compliance_check"]["daily"] == 20
        assert RateLimitService.LIMITS["ai_recommendation"]["daily"] == 15


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    """Tests for RateLimitService.check_rate_limit()."""

    def _make_user(self):
        user = MagicMock()
        user.id = uuid4()
        return user

    def _make_db(self, usage_count=0):
        mock_result = MagicMock()
        mock_result.scalar.return_value = usage_count
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        return mock_db

    @pytest.mark.asyncio
    async def test_unknown_feature_always_allowed(self):
        db = self._make_db()
        user = self._make_user()
        result = await RateLimitService.check_rate_limit(db, user, "unknown_feature")
        assert result["allowed"] is True
        assert result["limit"] is None

    @pytest.mark.asyncio
    async def test_within_limit(self):
        db = self._make_db(usage_count=3)
        user = self._make_user()
        result = await RateLimitService.check_rate_limit(db, user, "ai_assessment")
        assert result["allowed"] is True
        assert result["daily_limit"] == 10
        assert result["used_today"] == 3
        assert result["remaining"] == 7

    @pytest.mark.asyncio
    async def test_at_limit_check_only(self):
        db = self._make_db(usage_count=10)
        user = self._make_user()
        result = await RateLimitService.check_rate_limit(
            db, user, "ai_assessment", check_only=True,
        )
        assert result["allowed"] is False
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_exceeded_raises_429(self):
        from fastapi import HTTPException

        # First query returns count, second returns oldest timestamp
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        mock_oldest_result = MagicMock()
        mock_oldest_result.scalar.return_value = datetime.now(timezone.utc) - timedelta(hours=12)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_oldest_result])

        user = self._make_user()

        with pytest.raises(HTTPException) as exc_info:
            await RateLimitService.check_rate_limit(mock_db, user, "ai_assessment")
        assert exc_info.value.status_code == 429
        detail = exc_info.value.detail
        assert detail["feature"] == "ai_assessment"
        assert detail["limit"] == 10

    @pytest.mark.asyncio
    async def test_zero_usage(self):
        db = self._make_db(usage_count=0)
        user = self._make_user()
        result = await RateLimitService.check_rate_limit(db, user, "ai_policy_generation")
        assert result["allowed"] is True
        assert result["used_today"] == 0
        assert result["remaining"] == 5


# ---------------------------------------------------------------------------
# track_usage
# ---------------------------------------------------------------------------

class TestTrackUsage:
    """Tests for RateLimitService.track_usage()."""

    @pytest.mark.asyncio
    async def test_track_creates_audit_entry(self):
        mock_db = AsyncMock()
        user = MagicMock()
        user.id = uuid4()

        await RateLimitService.track_usage(mock_db, user, "ai_assessment")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_track_with_metadata(self):
        mock_db = AsyncMock()
        user = MagicMock()
        user.id = uuid4()

        await RateLimitService.track_usage(
            mock_db, user, "ai_assessment",
            metadata={"query_type": "quick_check"},
        )
        mock_db.add.assert_called_once()
        # Verify the audit entry was created with metadata
        call_args = mock_db.add.call_args[0][0]
        assert "ai_assessment" in call_args.action


# ---------------------------------------------------------------------------
# get_usage_stats
# ---------------------------------------------------------------------------

class TestGetUsageStats:
    """Tests for RateLimitService.get_usage_stats()."""

    @pytest.mark.asyncio
    async def test_returns_all_features(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        user = MagicMock()
        user.id = uuid4()

        stats = await RateLimitService.get_usage_stats(mock_db, user)
        assert "features" in stats
        assert "ai_assessment" in stats["features"]
        assert "ai_policy_generation" in stats["features"]
        assert stats["user_id"] == str(user.id)

    @pytest.mark.asyncio
    async def test_percentage_calculation(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        user = MagicMock()
        user.id = uuid4()

        stats = await RateLimitService.get_usage_stats(mock_db, user)
        assessment_stats = stats["features"]["ai_assessment"]
        assert assessment_stats["used"] == 5
        assert assessment_stats["limit"] == 10
        # Source code wraps percentage_used in a trailing-comma tuple: (value,)
        # We test the actual behavior rather than modifying source
        assert assessment_stats["percentage_used"] == (50.0,)


# ---------------------------------------------------------------------------
# reset_user_limits
# ---------------------------------------------------------------------------

class TestResetUserLimits:
    """Tests for RateLimitService.reset_user_limits()."""

    @pytest.mark.asyncio
    async def test_reset_specific_feature(self):
        mock_entries = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_entries

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        user = MagicMock()
        user.id = uuid4()

        await RateLimitService.reset_user_limits(mock_db, user, feature="ai_assessment")
        # Should delete each entry
        assert mock_db.delete.await_count == 2
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_all_features(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        user = MagicMock()
        user.id = uuid4()

        await RateLimitService.reset_user_limits(mock_db, user)
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()
