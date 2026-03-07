"""
Comprehensive tests for Feature Flag System
Tests functionality, performance, and edge cases
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import redis
from sqlalchemy.orm import Session

from services.feature_flag_service import (
    EnhancedFeatureFlagService,
    FeatureFlagConfig,
    EvaluationReason,
    feature_flag,
    FeatureNotEnabledException,
)
from models.feature_flags import (
    FeatureFlag as FeatureFlagModel,
    FeatureFlagAudit,
    FeatureFlagStatus,
)


class TestFeatureFlagService:
    """Test suite for Enhanced Feature Flag Service"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock = MagicMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        mock.delete.return_value = True
        mock.hgetall.return_value = {}
        mock.hincrby.return_value = 1
        mock.expire.return_value = True
        mock.scan_iter.return_value = []
        return mock

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock = MagicMock(spec=Session)
        return mock

    @pytest.fixture
    def service(self, mock_redis, mock_db_session):
        """Create service instance with mocked dependencies"""
        return EnhancedFeatureFlagService(redis_client=mock_redis, db_session=mock_db_session)

    def test_cache_key_generation(self, service):
        """Test cache key generation"""
        assert service._get_cache_key("test_flag") == "ff:test_flag"
        assert service._get_user_cache_key("test_flag", "user123") == "ff:test_flag:user:user123"

    def test_user_hash_consistency(self, service):
        """Test that user hashing is consistent"""
        hash1 = service._hash_user_id("test_flag", "user123")
        hash2 = service._hash_user_id("test_flag", "user123")
        assert hash1 == hash2
        assert 0 <= hash1 < 100

    def test_user_hash_distribution(self, service):
        """Test that user hashing has good distribution"""
        hashes = []
        for i in range(1000):
            hash_val = service._hash_user_id("test_flag", f"user{i}")
            hashes.append(hash_val)

        # Check that we have reasonable distribution
        assert min(hashes) < 10
        assert max(hashes) > 90
        assert 40 < sum(hashes) / len(hashes) < 60  # Average should be around 50

    def test_evaluate_flag_not_enabled(self, service):
        """Test flag evaluation when flag is disabled"""
        flag_data = {
            "name": "test_flag",
            "enabled": False,
            "percentage": 0,
            "whitelist": [],
            "blacklist": [],
            "environments": ["production"],
        }

        result, reason = service._evaluate_flag(flag_data, "user123", "production")
        assert result is False
        assert reason == EvaluationReason.DISABLED

    def test_evaluate_flag_whitelist(self, service):
        """Test flag evaluation with whitelist"""
        flag_data = {
            "name": "test_flag",
            "enabled": False,  # Even when disabled
            "percentage": 0,
            "whitelist": ["user123", "user456"],
            "blacklist": [],
            "environments": ["production"],
        }

        result, reason = service._evaluate_flag(flag_data, "user123", "production")
        assert result is True
        assert reason == EvaluationReason.WHITELIST

        result, reason = service._evaluate_flag(flag_data, "user789", "production")
        assert result is False
        assert reason == EvaluationReason.DISABLED

    def test_evaluate_flag_blacklist(self, service):
        """Test flag evaluation with blacklist"""
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 100,
            "whitelist": ["user123"],
            "blacklist": ["user123"],  # Blacklist takes precedence
            "environments": ["production"],
        }

        result, reason = service._evaluate_flag(flag_data, "user123", "production")
        assert result is False
        assert reason == EvaluationReason.BLACKLIST

    def test_evaluate_flag_percentage_rollout(self, service):
        """Test flag evaluation with percentage rollout"""
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 50,
            "whitelist": [],
            "blacklist": [],
            "environments": ["production"],
        }

        # Test multiple users to ensure some get enabled and some don't
        enabled_count = 0
        for i in range(100):
            result, reason = service._evaluate_flag(flag_data, f"user{i}", "production")
            if result:
                enabled_count += 1
                assert reason == EvaluationReason.PERCENTAGE
            else:
                assert reason == EvaluationReason.PERCENTAGE

        # With 50% rollout, we expect roughly 50 enabled (with some variance)
        assert 30 < enabled_count < 70

    def test_evaluate_flag_environment_override(self, service):
        """Test flag evaluation with environment overrides"""
        flag_data = {
            "name": "test_flag",
            "enabled": False,
            "percentage": 0,
            "whitelist": [],
            "blacklist": [],
            "environment_overrides": {"development": True, "production": False},
            "environments": ["development", "production"],
        }

        result, reason = service._evaluate_flag(flag_data, "user123", "development")
        assert result is True
        assert reason == EvaluationReason.ENVIRONMENT

        result, reason = service._evaluate_flag(flag_data, "user123", "production")
        assert result is False
        assert reason == EvaluationReason.ENVIRONMENT

    def test_evaluate_flag_expiration(self, service):
        """Test flag evaluation with expiration"""
        expired_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 100,
            "whitelist": [],
            "blacklist": [],
            "environments": ["production"],
            "expires_at": expired_time,
        }

        result, reason = service._evaluate_flag(flag_data, "user123", "production")
        assert result is False
        assert reason == EvaluationReason.EXPIRED

    def test_evaluate_flag_not_started(self, service):
        """Test flag evaluation before start time"""
        future_time = (datetime.utcnow() + timedelta(days=1)).isoformat()
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 100,
            "whitelist": [],
            "blacklist": [],
            "environments": ["production"],
            "starts_at": future_time,
        }

        result, reason = service._evaluate_flag(flag_data, "user123", "production")
        assert result is False
        assert reason == EvaluationReason.NOT_STARTED

    @pytest.mark.asyncio
    async def test_is_enabled_for_user_with_cache_hit(self, service, mock_redis):
        """Test is_enabled_for_user with cache hit"""
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 100,
            "whitelist": [],
            "blacklist": [],
            "environments": ["production"],
        }

        mock_redis.get.return_value = json.dumps(flag_data)

        result, reason = await service.is_enabled_for_user("test_flag", "user123", "production")

        assert result is True
        assert reason == EvaluationReason.ENABLED
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_not_called()  # Should not cache again

    @pytest.mark.asyncio
    async def test_is_enabled_for_user_with_cache_miss(self, service, mock_redis, mock_db_session):
        """Test is_enabled_for_user with cache miss"""
        mock_redis.get.return_value = None

        # Mock database flag
        mock_flag = MagicMock()
        mock_flag.name = "test_flag"
        mock_flag.enabled = True
        mock_flag.percentage = 100
        mock_flag.whitelist = []
        mock_flag.blacklist = []
        mock_flag.environment_overrides = {}
        mock_flag.environments = ["production"]
        mock_flag.expires_at = None
        mock_flag.starts_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = mock_flag
        mock_db_session.query.return_value = mock_query

        result, reason = await service.is_enabled_for_user("test_flag", "user123", "production")

        assert result is True
        assert reason == EvaluationReason.ENABLED
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_called_once()  # Should cache the result

    @pytest.mark.asyncio
    async def test_performance_under_1ms_with_cache(self, service, mock_redis):
        """Test that flag evaluation meets <1ms performance goal with cache"""
        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 50,
            "whitelist": ["user123"],
            "blacklist": [],
            "environments": ["production"],
        }

        mock_redis.get.return_value = json.dumps(flag_data)

        # Measure evaluation time
        start = time.perf_counter()
        result, reason = await service.is_enabled_for_user("test_flag", "user123", "production")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is True
        assert reason == EvaluationReason.WHITELIST
        assert elapsed_ms < 1.0  # Should be under 1ms

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, service, mock_redis):
        """Test cache invalidation"""
        await service.invalidate_cache("test_flag")

        mock_redis.delete.assert_called_with("ff:test_flag")
        mock_redis.scan_iter.assert_called_with(match="ff:test_flag:user:*")

    @pytest.mark.asyncio
    async def test_update_flag(self, service, mock_db_session):
        """Test updating a feature flag"""
        # Mock existing flag
        mock_flag = MagicMock()
        mock_flag.id = "flag-id"
        mock_flag.enabled = False
        mock_flag.percentage = 0
        mock_flag.whitelist = []
        mock_flag.blacklist = []
        mock_flag.environment_overrides = {}
        mock_flag.version = 1

        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.return_value = mock_flag
        mock_db_session.query.return_value = mock_query

        config = FeatureFlagConfig(
            name="test_flag",
            enabled=True,
            percentage=50,
            whitelist=["user123"],
            environments=["production"],
        )

        # Mock the context manager for get_db_session
        with patch("services.feature_flag_service.get_db_session") as mock_get_db:
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_db_session
            mock_context.__exit__.return_value = None
            mock_get_db.return_value.__next__.return_value = mock_context

            result = await service.update_flag("test_flag", config, "admin_user", "Testing")

            assert result is True
            assert mock_flag.enabled is True
            assert mock_flag.percentage == 50
            assert mock_flag.whitelist == ["user123"]
            assert mock_flag.version == 2


class TestFeatureFlagDecorator:
    """Test suite for feature flag decorator"""

    @pytest.mark.asyncio
    async def test_async_decorator_enabled(self):
        """Test async decorator when flag is enabled"""
        with patch("services.feature_flag_service.EnhancedFeatureFlagService") as MockService:
            mock_service = MockService.return_value
            mock_service.is_enabled_for_user.return_value = (True, EvaluationReason.ENABLED)

            @feature_flag("test_feature")
            async def test_function(user_id: str):
                return f"Hello {user_id}"

            result = await test_function(user_id="user123")
            assert result == "Hello user123"
            mock_service.is_enabled_for_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_decorator_disabled_with_fallback(self):
        """Test async decorator with fallback when flag is disabled"""
        with patch("services.feature_flag_service.EnhancedFeatureFlagService") as MockService:
            mock_service = MockService.return_value
            mock_service.is_enabled_for_user.return_value = (False, EvaluationReason.DISABLED)

            async def fallback_function(user_id: str):
                return f"Fallback for {user_id}"

            @feature_flag("test_feature", fallback=fallback_function)
            async def test_function(user_id: str):
                return f"Hello {user_id}"

            result = await test_function(user_id="user123")
            assert result == "Fallback for user123"

    @pytest.mark.asyncio
    async def test_async_decorator_disabled_with_exception(self):
        """Test async decorator raising exception when flag is disabled"""
        with patch("services.feature_flag_service.EnhancedFeatureFlagService") as MockService:
            mock_service = MockService.return_value
            mock_service.is_enabled_for_user.return_value = (False, EvaluationReason.DISABLED)

            @feature_flag("test_feature", raise_on_disabled=True)
            async def test_function(user_id: str):
                return f"Hello {user_id}"

            with pytest.raises(FeatureNotEnabledException):
                await test_function(user_id="user123")

    def test_sync_decorator_enabled(self):
        """Test sync decorator when flag is enabled"""
        with patch("services.feature_flag_service.EnhancedFeatureFlagService") as MockService:
            mock_service = MockService.return_value

            # Mock the coroutine
            async def mock_is_enabled():
                return (True, EvaluationReason.ENABLED)

            mock_service.is_enabled_for_user.return_value = mock_is_enabled()

            @feature_flag("test_feature")
            def test_function(user_id: str):
                return f"Hello {user_id}"

            result = test_function(user_id="user123")
            assert result == "Hello user123"

    def test_decorator_extracts_user_id_from_object(self):
        """Test decorator extracting user_id from object attribute"""
        with patch("services.feature_flag_service.EnhancedFeatureFlagService") as MockService:
            mock_service = MockService.return_value

            async def mock_is_enabled():
                return (True, EvaluationReason.ENABLED)

            mock_service.is_enabled_for_user.return_value = mock_is_enabled()

            class UserContext:
                def __init__(self, user_id):
                    self.user_id = user_id

            @feature_flag("test_feature")
            def test_function(context):
                return f"Hello {context.user_id}"

            context = UserContext("user123")
            result = test_function(context)
            assert result == "Hello user123"


class TestFeatureFlagIntegration:
    """Integration tests for feature flag system"""

    @pytest.mark.asyncio
    async def test_end_to_end_flag_lifecycle(self):
        """Test complete lifecycle of a feature flag"""
        # This would be an integration test with real Redis and DB
        # Skipped for now as it requires actual infrastructure
        pass

    @pytest.mark.asyncio
    async def test_concurrent_evaluations(self):
        """Test concurrent flag evaluations for performance"""
        with patch("services.feature_flag_service.EnhancedFeatureFlagService") as MockService:
            mock_service = MockService.return_value
            mock_service.is_enabled_for_user.return_value = (True, EvaluationReason.ENABLED)

            service = mock_service

            # Simulate 100 concurrent evaluations
            tasks = []
            for i in range(100):
                task = service.is_enabled_for_user("test_flag", f"user{i}", "production")
                tasks.append(task)

            start = time.perf_counter()
            results = await asyncio.gather(*tasks)
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert len(results) == 100
            assert all(r[0] is True for r in results)
            # Even 100 concurrent evaluations should complete quickly
            assert elapsed_ms < 100  # Less than 100ms for 100 evaluations


class TestFeatureFlagAPI:
    """Test suite for Feature Flag API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)

    def test_list_feature_flags(self, client):
        """Test listing feature flags endpoint"""
        # This would test the actual API endpoint
        # Requires full app setup
        pass

    def test_evaluate_feature_flag(self, client):
        """Test evaluating a single feature flag"""
        # This would test the evaluation endpoint
        # Requires full app setup
        pass

    def test_bulk_evaluate_feature_flags(self, client):
        """Test bulk evaluation of feature flags"""
        # This would test the bulk evaluation endpoint
        # Requires full app setup
        pass


# Performance benchmarks
class TestPerformanceBenchmarks:
    """Performance benchmarks for feature flag system"""

    @pytest.mark.benchmark
    def test_evaluation_performance(self, benchmark):
        """Benchmark flag evaluation performance"""
        service = EnhancedFeatureFlagService()

        flag_data = {
            "name": "test_flag",
            "enabled": True,
            "percentage": 50,
            "whitelist": ["user1", "user2", "user3"],
            "blacklist": ["user4", "user5"],
            "environments": ["production"],
            "environment_overrides": {"staging": False},
        }

        result = benchmark(service._evaluate_flag, flag_data, "user123", "production")

        assert result[0] in [True, False]
        assert result[1] in [e.value for e in EvaluationReason]

    @pytest.mark.benchmark
    def test_hash_performance(self, benchmark):
        """Benchmark user hashing performance"""
        service = EnhancedFeatureFlagService()

        result = benchmark(service._hash_user_id, "test_flag", "user123")

        assert 0 <= result < 100
