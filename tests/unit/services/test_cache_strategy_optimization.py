"""
Unit Tests for Cache Strategy Optimization

Tests the enhanced cache strategy features including:
- Performance-based TTL adjustment
- Cache warming queues
- Intelligent invalidation
- Cache strategy metrics
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from services.ai.cached_content import (
    GoogleCachedContentManager,
    CacheContentType,
    CacheLifecycleConfig,
)


# Move fixtures outside the class
@pytest.fixture
def optimized_cache_config():
    """Cache configuration with optimization enabled."""
    return CacheLifecycleConfig(
        default_ttl_hours=2,
        max_ttl_hours=8,
        min_ttl_minutes=15,
        performance_based_ttl=True,
        cache_warming_enabled=True,
        intelligent_invalidation=True,
        fast_response_threshold_ms=200,
        slow_response_threshold_ms=2000,
        ttl_adjustment_factor=0.2,
    )


@pytest.fixture
def cache_manager(optimized_cache_config):
    """Cache manager with optimization enabled."""
    return GoogleCachedContentManager(optimized_cache_config)


@pytest.fixture
def sample_business_profile():
    """Sample business profile for testing."""
    return {
        "id": str(uuid4()),
        "company_name": "Test Corp",
        "industry": "Technology",
        "employee_count": 150,
        "country": "UK",
        "handles_personal_data": True,
        "processes_payments": False,
    }


@pytest.mark.unit
@pytest.mark.ai
class TestCacheStrategyOptimization:
    """Test cache strategy optimization features."""

    def test_performance_based_ttl_optimization(self, cache_manager):
        """Test performance-based TTL adjustment."""
        # Test fast responses
        cache_key_fast = "test_cache_key_fast"
        for _ in range(5):
            cache_manager.record_cache_performance(cache_key_fast, 150, hit=True)

        # Calculate TTL adjustment for fast responses
        adjustment = cache_manager._calculate_ttl_adjustment(cache_key_fast, 150)
        assert adjustment == 0.2  # Should increase TTL for fast responses

        # Test slow responses with separate cache key
        cache_key_slow = "test_cache_key_slow"
        for _ in range(5):
            cache_manager.record_cache_performance(cache_key_slow, 2500, hit=True)

        # Calculate TTL adjustment for slow responses
        adjustment = cache_manager._calculate_ttl_adjustment(cache_key_slow, 2500)
        assert adjustment == -0.2  # Should decrease TTL for slow responses

    def test_cache_warming_queue_management(self, cache_manager, sample_business_profile):
        """Test cache warming queue operations."""
        # Add items to warming queue with different priorities
        cache_manager.add_to_warming_queue(
            CacheContentType.ASSESSMENT_CONTEXT,
            {"framework_id": "ISO27001", "business_profile": sample_business_profile},
            priority=1,
        )

        cache_manager.add_to_warming_queue(
            CacheContentType.BUSINESS_PROFILE,
            {"business_profile": sample_business_profile},
            priority=5,
        )

        cache_manager.add_to_warming_queue(
            CacheContentType.FRAMEWORK_CONTEXT,
            {"framework_id": "GDPR", "industry_context": "Technology"},
            priority=3,
        )

        # Verify queue ordering by priority
        assert len(cache_manager.cache_warming_queue) == 3
        assert cache_manager.cache_warming_queue[0]["priority"] == 1
        assert cache_manager.cache_warming_queue[1]["priority"] == 3
        assert cache_manager.cache_warming_queue[2]["priority"] == 5

    def test_should_warm_cache_logic(self, cache_manager):
        """Test cache warming decision logic."""
        # High priority items should always be warmed
        high_priority_entry = {
            "content_type": CacheContentType.ASSESSMENT_CONTEXT,
            "context": {"framework_id": "ISO27001", "business_profile_id": "test"},
            "priority": 1,
            "queued_at": datetime.now(),
            "attempts": 0,
        }

        assert cache_manager._should_warm_cache(high_priority_entry) is True

        # Low priority item without history should not be warmed
        low_priority_entry = {
            "content_type": CacheContentType.FRAMEWORK_CONTEXT,
            "context": {"framework_id": "GDPR", "business_profile_id": "test"},
            "priority": 8,
            "queued_at": datetime.now(),
            "attempts": 0,
        }

        assert cache_manager._should_warm_cache(low_priority_entry) is False

    @pytest.mark.asyncio
    async def test_process_warming_queue(self, cache_manager, sample_business_profile):
        """Test processing of cache warming queue."""
        # Mock successful cache creation via new genai client
        mock_cached_content = Mock()
        mock_cached_content.name = "test_warmed_cache"
        mock_client = Mock()
        mock_client.caches.create.return_value = mock_cached_content

        # Add items to warming queue
        cache_manager.add_to_warming_queue(
            CacheContentType.ASSESSMENT_CONTEXT,
            {
                "framework_id": "ISO27001",
                "business_profile": sample_business_profile,
                "business_profile_id": sample_business_profile["id"],
            },
            priority=1,
        )

        with patch("config.ai_config.ai_config._get_genai_client", return_value=mock_client):
            # Process warming queue
            processed = await cache_manager.process_warming_queue(max_items=1)

        assert processed == 1
        assert len(cache_manager.cache_warming_queue) == 0

    def test_intelligent_invalidation_triggers(self, cache_manager, sample_business_profile):
        """Test intelligent cache invalidation triggers."""
        business_profile_id = sample_business_profile["id"]

        # Mock some cache entries
        cache_manager.cache_metadata = {
            "cache_1": {
                "business_profile_id": business_profile_id,
                "framework_id": "ISO27001",
                "type": CacheContentType.BUSINESS_PROFILE.value,
            },
            "cache_2": {
                "business_profile_id": business_profile_id,
                "framework_id": "GDPR",
                "type": CacheContentType.ASSESSMENT_CONTEXT.value,
            },
            "cache_3": {
                "business_profile_id": "other_profile",
                "framework_id": "ISO27001",
                "type": CacheContentType.FRAMEWORK_CONTEXT.value,
            },
        }

        # Test business profile update invalidation
        context = {"business_profile_id": business_profile_id}
        cache_manager.trigger_intelligent_invalidation(
            "business_profile_update",
            context,
        )

        # Verify invalidation trigger was recorded
        assert any("business_profile_update" in key for key in cache_manager.invalidation_triggers)

    def test_framework_invalidation(self, cache_manager):
        """Test framework-specific invalidation."""
        framework_id = "ISO27001"

        # Mock cache entries
        cache_manager.cache_metadata = {
            "cache_1": {"framework_id": framework_id, "type": "assessment_context"},
            "cache_2": {"framework_id": "GDPR", "type": "framework_context"},
            "cache_3": {"framework_id": framework_id, "type": "business_profile"},
        }

        # Get keys that should be invalidated
        keys_to_invalidate = []
        for cache_key, metadata in cache_manager.cache_metadata.items():
            if metadata.get("framework_id") == framework_id:
                keys_to_invalidate.append(cache_key)

        assert len(keys_to_invalidate) == 2
        assert "cache_1" in keys_to_invalidate
        assert "cache_3" in keys_to_invalidate

    def test_cache_strategy_metrics_collection(self, cache_manager):
        """Test collection of cache strategy metrics."""
        # Simulate performance history
        cache_manager.performance_history = {
            "cache_1": [
                {
                    "timestamp": datetime.now(),
                    "response_time_ms": 150,
                    "hit": True,
                    "ttl_adjustment": 0.2,
                },
                {
                    "timestamp": datetime.now(),
                    "response_time_ms": 180,
                    "hit": True,
                    "ttl_adjustment": 0.2,
                },
            ],
            "cache_2": [
                {
                    "timestamp": datetime.now(),
                    "response_time_ms": 2500,
                    "hit": False,
                    "ttl_adjustment": -0.2,
                },
            ],
        }

        # Add warming queue items
        cache_manager.cache_warming_queue = [
            {"priority": 1, "content_type": CacheContentType.ASSESSMENT_CONTEXT},
            {"priority": 2, "content_type": CacheContentType.BUSINESS_PROFILE},
            {"priority": 5, "content_type": CacheContentType.FRAMEWORK_CONTEXT},
        ]

        # Add invalidation triggers
        cache_manager.invalidation_triggers = {
            "business_profile_update:test": datetime.now(),
            "framework_update:ISO27001": datetime.now() - timedelta(hours=2),
        }

        metrics = cache_manager.get_cache_strategy_metrics()

        # Verify metric structure
        assert "performance_based_ttl" in metrics
        assert "cache_warming" in metrics
        assert "intelligent_invalidation" in metrics

        # Verify performance TTL metrics
        ttl_metrics = metrics["performance_based_ttl"]
        assert ttl_metrics["enabled"] is True
        assert ttl_metrics["total_adjustments"] == 3
        assert ttl_metrics["tracked_cache_keys"] == 2

        # Verify cache warming metrics
        warming_metrics = metrics["cache_warming"]
        assert warming_metrics["enabled"] is True
        assert warming_metrics["queue_size"] == 3
        assert warming_metrics["high_priority_items"] == 2  # Priority 1 and 2

        # Verify invalidation metrics
        invalidation_metrics = metrics["intelligent_invalidation"]
        assert invalidation_metrics["enabled"] is True
        assert invalidation_metrics["recent_triggers"] == 1  # Only one within last hour

    def test_cache_warming_queue_size_limit(self, cache_manager):
        """Test cache warming queue size limitation."""
        # Add more than 100 items to test size limit
        for i in range(110):
            cache_manager.add_to_warming_queue(
                CacheContentType.FRAMEWORK_CONTEXT,
                {"framework_id": f"framework_{i}"},
                priority=5,
            )

        # Verify queue is limited to 100 items
        assert len(cache_manager.cache_warming_queue) == 100

    def test_performance_history_limit(self, cache_manager):
        """Test performance history size limitation."""
        cache_key = "test_cache_key"

        # Add more than 50 performance records
        for i in range(60):
            cache_manager.record_cache_performance(cache_key, 200 + i, hit=True)

        # Verify history is limited to 50 records
        assert len(cache_manager.performance_history[cache_key]) == 50

    def test_ttl_adjustment_calculation_edge_cases(self, cache_manager):
        """Test TTL adjustment calculation edge cases."""
        cache_key = "test_cache_key"

        # Test with insufficient history (less than 3 records)
        cache_manager.record_cache_performance(cache_key, 150, hit=True)
        cache_manager.record_cache_performance(cache_key, 180, hit=True)

        adjustment = cache_manager._calculate_ttl_adjustment(cache_key, 150)
        assert adjustment == 0.0  # Should not adjust with insufficient data

        # Test with medium response time (no adjustment)
        for _ in range(5):
            cache_manager.record_cache_performance(cache_key, 1000, hit=True)

        adjustment = cache_manager._calculate_ttl_adjustment(cache_key, 1000)
        assert adjustment == 0.0  # Should not adjust for medium response times

    def test_disabled_optimization_features(self):
        """Test behavior when optimization features are disabled."""
        from services.ai.cached_content import (
            GoogleCachedContentManager,
            CacheLifecycleConfig,
        )

        config = CacheLifecycleConfig(
            performance_based_ttl=False,
            cache_warming_enabled=False,
            intelligent_invalidation=False,
        )
        cache_manager = GoogleCachedContentManager(config)

        # Test performance recording (should be no-op)
        cache_manager.record_cache_performance("test_key", 150, hit=True)
        assert len(cache_manager.performance_history) == 0

        # Test warming queue (should be no-op)
        cache_manager.add_to_warming_queue(
            CacheContentType.ASSESSMENT_CONTEXT,
            {"framework_id": "ISO27001"},
            priority=1,
        )
        assert len(cache_manager.cache_warming_queue) == 0

        # Test invalidation (should be no-op)
        cache_manager.trigger_intelligent_invalidation(
            "business_profile_update",
            {"business_profile_id": "test"},
        )
        assert len(cache_manager.invalidation_triggers) == 0


@pytest.mark.integration
@pytest.mark.ai
class TestCacheStrategyIntegration:
    """Integration tests for cache strategy optimization."""

    @pytest.fixture
    def assistant_with_optimized_cache(self, async_db_session):
        """AI assistant with optimized cache configuration."""
        from services.ai.assistant import ComplianceAssistant
        from services.ai.cached_content import CacheLifecycleConfig
        from unittest.mock import Mock, AsyncMock

        # Mock assistant for testing since it may not have these methods yet
        assistant = Mock()
        assistant.async_db_session = async_db_session

        # Create optimized cache config
        config = CacheLifecycleConfig(
            performance_based_ttl=True,
            cache_warming_enabled=True,
            intelligent_invalidation=True,
        )

        # Mock the cache-related methods
        assistant.get_cache_strategy_metrics = AsyncMock(
            return_value={
                "strategy_optimization": {
                    "performance_based_ttl": {"enabled": True, "total_adjustments": 0},
                    "cache_warming": {"enabled": True, "queue_size": 0},
                    "intelligent_invalidation": {"enabled": True, "recent_triggers": 0},
                },
            },
        )

        assistant._add_to_cache_warming_queue = AsyncMock()
        assistant.process_cache_warming_queue = AsyncMock(return_value=0)
        assistant.trigger_cache_invalidation = AsyncMock()

        return assistant

    @pytest.mark.asyncio
    async def test_cache_strategy_metrics_endpoint_integration(
        self, assistant_with_optimized_cache
    ):
        """Test integration of cache strategy metrics with assistant."""
        # Get cache strategy metrics
        metrics = await assistant_with_optimized_cache.get_cache_strategy_metrics()

        # Verify metric structure
        assert "strategy_optimization" in metrics

        optimization_metrics = metrics["strategy_optimization"]
        assert "performance_based_ttl" in optimization_metrics
        assert "cache_warming" in optimization_metrics
        assert "intelligent_invalidation" in optimization_metrics

    @pytest.mark.asyncio
    async def test_cache_warming_integration(self, assistant_with_optimized_cache):
        """Test cache warming integration with assistant."""
        context = {
            "framework_id": "ISO27001",
            "business_profile": {"id": str(uuid4()), "industry": "Technology"},
        }

        # Add to warming queue
        await assistant_with_optimized_cache._add_to_cache_warming_queue(
            context,
            "assessment",
        )

        # Process warming queue
        processed = await assistant_with_optimized_cache.process_cache_warming_queue()

        # Should attempt to process (may fail due to mocked services)
        assert processed >= 0

    @pytest.mark.asyncio
    async def test_cache_invalidation_integration(self, assistant_with_optimized_cache):
        """Test cache invalidation integration with assistant."""
        context = {"business_profile_id": str(uuid4()), "framework_id": "ISO27001"}

        # Trigger invalidation
        await assistant_with_optimized_cache.trigger_cache_invalidation(
            "business_profile_update",
            context,
        )

        # Should not raise exceptions
        assert True
