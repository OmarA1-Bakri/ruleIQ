"""
Comprehensive Test Suite for Advanced Caching System

This module provides extensive unit and integration tests for the multi-level caching system,
covering all requirements specified in Priority 3.1: Implement Advanced Caching Strategy.

Tests cover:
- Multi-level caching architecture (L1 in-memory, L2 Redis)
- Cache invalidation policies (time-based, event-based, dependency-based)
- Cache warming strategies (startup, background, priority-based)
- Performance monitoring and metrics
- Fallback mechanisms for Redis unavailability
- Cache key management and versioning
- Integration with database, API, and service layers
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from uuid import uuid4

import redis.asyncio as redis
from pydantic import BaseModel

from config.settings import settings
import contextlib


class MockRedisClient:
    """Mock Redis client for testing when Redis is unavailable"""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.ttl_data: Dict[str, float] = {}

    async def get(self, key: str) -> Optional[str]:
        """Mock get operation"""
        if key in self.ttl_data and time.time() > self.ttl_data[key]:
            # Expired
            del self.data[key]
            del self.ttl_data[key]
            return None
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Mock set operation"""
        self.data[key] = value
        if ex:
            self.ttl_data[key] = time.time() + ex
        return True

    async def delete(self, key: str) -> int:
        """Mock delete operation"""
        if key in self.data:
            del self.data[key]
            if key in self.ttl_data:
                del self.ttl_data[key]
            return 1
        return 0

    async def exists(self, key: str) -> int:
        """Mock exists operation"""
        return 1 if key in self.data else 0

    async def expire(self, key: str, time: int) -> int:
        """Mock expire operation"""
        if key in self.data:
            self.ttl_data[key] = time.time() + time
            return 1
        return 0

    async def keys(self, pattern: str) -> List[str]:
        """Mock keys operation"""
        import fnmatch

        return [k for k in self.data if fnmatch.fnmatch(k, pattern)]


class TestDataModel(BaseModel):
    """Test data model for caching"""

    id: str
    name: str
    value: int
    tags: List[str]


class TestCacheMetrics:
    """Test cache metrics collector"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.response_times: List[float] = []

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    def record_set(self):
        self.sets += 1

    def record_delete(self):
        self.deletes += 1

    def record_response_time(self, time: float):
        self.response_times.append(time)

    def get_hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_avg_response_time(self) -> float:
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0


class TestMultiLevelCache:
    """Test multi-level cache implementation"""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client"""
        return MockRedisClient()

    @pytest.fixture
    def cache_metrics(self):
        """Create cache metrics collector"""
        return TestCacheMetrics()

    @pytest.fixture
    async def cache_system(self, mock_redis, cache_metrics):
        """Create cache system instance for testing"""
        # Import here to avoid circular imports
        from services.caching.cache_manager import CacheManager

        # Mock the Redis client
        with patch("database.redis_client.get_redis_client", return_value=mock_redis):
            cache = CacheManager(metrics=cache_metrics)
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_l1_cache_hit(self, cache_system, cache_metrics):
        """Test L1 cache hit scenario"""
        key = "test:key:l1"
        value = {"data": "test_value", "ttl": 300}

        # Set value in cache
        await cache_system.set(key, value, ttl=300)

        # Get value (should hit L1)
        start_time = time.time()
        result = await cache_system.get(key)
        response_time = time.time() - start_time

        assert result == value
        assert cache_metrics.hits == 1
        assert cache_metrics.misses == 0
        assert response_time < 0.01  # L1 should be very fast

    @pytest.mark.asyncio
    async def test_l2_cache_hit_after_l1_miss(self, cache_system, cache_metrics):
        """Test L2 cache hit after L1 miss"""
        key = "test:key:l2"
        value = {"data": "l2_value", "ttl": 300}

        # Manually set in L2 (simulating background set)
        await cache_system._redis.set(key, cache_system._serialize(value), ex=300)

        # Clear L1 to force L2 lookup
        if key in cache_system._l1_cache:
            del cache_system._l1_cache[key]

        # Get value (should miss L1, hit L2, promote to L1)
        result = await cache_system.get(key)

        assert result == value
        assert cache_metrics.hits == 1
        assert cache_metrics.misses == 1  # L1 miss

        # Second get should hit L1
        result2 = await cache_system.get(key)
        assert result2 == value
        assert cache_metrics.hits == 2

    @pytest.mark.asyncio
    async def test_cache_miss_both_levels(self, cache_system, cache_metrics):
        """Test cache miss in both L1 and L2"""
        key = "test:key:miss"

        result = await cache_system.get(key)

        assert result is None
        assert cache_metrics.misses == 1
        assert cache_metrics.hits == 0

    @pytest.mark.asyncio
    async def test_cache_promotion_l1_to_l2(self, cache_system):
        """Test that L1 hits promote data to L2 for sharing"""
        key = "test:key:promote"
        value = {"data": "promote_value"}

        # Set in L1 only
        cache_system._l1_cache[key] = value

        # Get should promote to L2
        result = await cache_system.get(key)
        assert result == value

        # Verify in L2
        l2_value = await cache_system._redis.get(key)
        assert l2_value is not None

    @pytest.mark.asyncio
    async def test_ttl_expiration_l1(self, cache_system):
        """Test TTL expiration in L1 cache"""
        key = "test:key:ttl"
        value = {"data": "ttl_value"}

        # Set with short TTL
        await cache_system.set(key, value, ttl=1)

        # Immediate get should work
        result = await cache_system.get(key)
        assert result == value

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired
        result = await cache_system.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration_l2(self, cache_system):
        """Test TTL expiration in L2 cache"""
        key = "test:key:ttl2"
        value = {"data": "ttl2_value"}

        # Set with short TTL
        await cache_system.set(key, value, ttl=1)

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Clear L1
        if key in cache_system._l1_cache:
            del cache_system._l1_cache[key]

        # Should be expired in L2 too
        result = await cache_system.get(key)
        assert result is None


class TestCacheInvalidation:
    """Test cache invalidation policies"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for invalidation testing"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_time_based_invalidation(self, cache_system):
        """Test time-based cache invalidation"""
        key = "test:invalidate:time"
        value = {"data": "time_value"}

        # Set with TTL
        await cache_system.set(key, value, ttl=60)

        # Should exist
        result = await cache_system.get(key)
        assert result == value

        # Manually expire
        await cache_system.invalidate(key)

        # Should be gone
        result = await cache_system.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_pattern_based_invalidation(self, cache_system):
        """Test pattern-based cache invalidation"""
        # Set multiple keys with pattern
        keys = ["user:123:profile", "user:123:settings", "user:456:profile", "post:789:content"]

        for key in keys:
            await cache_system.set(key, {"data": f"value_{key}"}, ttl=300)

        # Invalidate user 123 keys
        await cache_system.invalidate_pattern("user:123:*")

        # User 123 keys should be gone
        assert await cache_system.get("user:123:profile") is None
        assert await cache_system.get("user:123:settings") is None

        # Other keys should remain
        assert await cache_system.get("user:456:profile") is not None
        assert await cache_system.get("post:789:content") is not None

    @pytest.mark.asyncio
    async def test_dependency_based_invalidation(self, cache_system):
        """Test dependency-based cache invalidation"""
        # Set related data
        await cache_system.set("user:123", {"name": "John"}, ttl=300)
        await cache_system.set("user:123:posts", [{"id": 1}, {"id": 2}], ttl=300)
        await cache_system.set("post:1", {"title": "Post 1"}, ttl=300)
        await cache_system.set("post:2", {"title": "Post 2"}, ttl=300)

        # Invalidate user and dependencies
        await cache_system.invalidate_with_dependencies("user:123", ["user:123:*", "post:*"])

        # All related data should be gone
        assert await cache_system.get("user:123") is None
        assert await cache_system.get("user:123:posts") is None
        assert await cache_system.get("post:1") is None
        assert await cache_system.get("post:2") is None

    @pytest.mark.asyncio
    async def test_event_based_invalidation(self, cache_system):
        """Test event-based cache invalidation"""
        # Set user data
        await cache_system.set("user:123:profile", {"name": "John"}, ttl=300)
        await cache_system.set("user:123:sessions", ["session1"], ttl=300)

        # Simulate user update event
        await cache_system.invalidate_on_event("user_updated", {"user_id": "123"})

        # User-related caches should be invalidated
        assert await cache_system.get("user:123:profile") is None
        assert await cache_system.get("user:123:sessions") is None


class TestCacheWarming:
    """Test cache warming strategies"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for warming testing"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_startup_warming(self, cache_system):
        """Test startup cache warming"""
        # Mock data source
        mock_data = {
            "critical:key1": {"data": "critical1", "priority": 10},
            "critical:key2": {"data": "critical2", "priority": 9},
            "normal:key3": {"data": "normal3", "priority": 5},
        }

        # Warm critical data
        await cache_system.warm_startup_cache(mock_data, min_priority=8)

        # High priority data should be cached
        result1 = await cache_system.get("critical:key1")
        result2 = await cache_system.get("critical:key2")
        result3 = await cache_system.get("normal:key3")

        assert result1 == mock_data["critical:key1"]
        assert result2 == mock_data["critical:key2"]
        assert result3 is None  # Below priority threshold

    @pytest.mark.asyncio
    async def test_background_warming(self, cache_system):
        """Test background cache warming"""
        # Start background warming
        warming_task = asyncio.create_task(
            cache_system.background_warming(
                data_source=lambda: {"bg:key1": {"data": "bg1"}}, interval=1
            )
        )

        # Wait a bit
        await asyncio.sleep(1.5)

        # Stop warming
        warming_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warming_task

        # Data should be warmed
        result = await cache_system.get("bg:key1")
        assert result == {"data": "bg1"}

    @pytest.mark.asyncio
    async def test_priority_based_warming(self, cache_system):
        """Test priority-based cache warming"""
        data_items = [
            {"key": "low:key", "data": "low", "priority": 1},
            {"key": "medium:key", "data": "medium", "priority": 5},
            {"key": "high:key", "data": "high", "priority": 10},
        ]

        # Warm by priority
        await cache_system.warm_by_priority(data_items, batch_size=2)

        # All should be cached (no filtering)
        assert await cache_system.get("low:key") == {"data": "low"}
        assert await cache_system.get("medium:key") == {"data": "medium"}
        assert await cache_system.get("high:key") == {"data": "high"}

    @pytest.mark.asyncio
    async def test_lazy_warming(self, cache_system):
        """Test lazy loading cache warming"""
        access_pattern = ["lazy:key1", "lazy:key2", "lazy:key1"]  # key1 accessed twice

        # Simulate access pattern
        for key in access_pattern:
            # On miss, warm the data
            result = await cache_system.get(key)
            if result is None:
                # Lazy load and cache
                data = {"data": f"lazy_{key.split(':')[1]}"}
                await cache_system.set(key, data, ttl=300)
                result = data

            assert result is not None

        # Frequently accessed key should be in L1
        assert "lazy:key1" in cache_system._l1_cache


class TestPerformanceMonitoring:
    """Test performance monitoring and metrics"""

    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector"""
        return TestCacheMetrics()

    @pytest.fixture
    async def cache_system(self, metrics_collector):
        """Create cache system with metrics"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager(metrics=metrics_collector)
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_hit_miss_metrics(self, cache_system, metrics_collector):
        """Test hit/miss ratio metrics"""
        # Generate hits and misses
        await cache_system.set("hit:key", {"data": "hit"}, ttl=300)

        # 3 hits
        for _ in range(3):
            await cache_system.get("hit:key")

        # 2 misses
        await cache_system.get("miss:key1")
        await cache_system.get("miss:key2")

        assert metrics_collector.hits == 3
        assert metrics_collector.misses == 2
        assert metrics_collector.get_hit_rate() == 0.6  # 3/5

    @pytest.mark.asyncio
    async def test_response_time_monitoring(self, cache_system, metrics_collector):
        """Test response time monitoring"""
        await cache_system.set("timing:key", {"data": "timing"}, ttl=300)

        # Measure response time
        start = time.time()
        result = await cache_system.get("timing:key")
        response_time = time.time() - start

        assert result is not None
        assert len(metrics_collector.response_times) == 1
        assert metrics_collector.response_times[0] > 0
        assert abs(metrics_collector.response_times[0] - response_time) < 0.001

    @pytest.mark.asyncio
    async def test_memory_usage_tracking(self, cache_system):
        """Test memory usage tracking"""
        # Add data to cache
        large_data = {"data": "x" * 1000}  # 1KB data
        await cache_system.set("memory:key", large_data, ttl=300)

        # Get memory stats
        stats = await cache_system.get_memory_stats()

        assert "l1_items" in stats
        assert "l2_memory_bytes" in stats
        assert stats["l1_items"] > 0

    @pytest.mark.asyncio
    async def test_cache_size_metrics(self, cache_system):
        """Test cache size metrics"""
        # Add multiple items
        for i in range(10):
            await cache_system.set(f"size:key{i}", {"data": f"value{i}"}, ttl=300)

        stats = await cache_system.get_cache_stats()

        assert stats["total_items"] >= 10
        assert "l1_hit_rate" in stats
        assert "l2_hit_rate" in stats


class TestCacheKeyManagement:
    """Test cache key management and versioning"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for key management testing"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_structured_key_generation(self, cache_system):
        """Test structured key generation"""
        # Test different key patterns
        user_key = cache_system.build_key("user", "profile", user_id="123")
        assert user_key == "cache:user:profile:123"

        session_key = cache_system.build_key("session", "data", session_id="abc", version="v1")
        assert session_key == "cache:session:data:abc:v1"

    @pytest.mark.asyncio
    async def test_key_compression(self, cache_system):
        """Test key compression for efficiency"""
        long_key = cache_system.build_key("very", "long", "namespace", "with", "many", "parts")
        compressed = cache_system.compress_key(long_key)

        # Compressed key should be shorter but still unique
        assert len(compressed) <= len(long_key)
        assert compressed.startswith("cache:")

    @pytest.mark.asyncio
    async def test_key_versioning(self, cache_system):
        """Test cache key versioning for deployments"""
        key = "cache:user:profile:123"

        # Set data with version
        await cache_system.set_with_version(key, {"name": "John"}, version="v1", ttl=300)

        # Get with same version should work
        result = await cache_system.get_with_version(key, version="v1")
        assert result == {"name": "John"}

        # Get with different version should miss
        result = await cache_system.get_with_version(key, version="v2")
        assert result is None

    @pytest.mark.asyncio
    async def test_bulk_key_operations(self, cache_system):
        """Test bulk key operations"""
        # Set multiple keys
        keys_data = {
            "bulk:key1": {"data": "value1"},
            "bulk:key2": {"data": "value2"},
            "bulk:key3": {"data": "value3"},
        }

        await cache_system.set_bulk(keys_data, ttl=300)

        # Get multiple keys
        results = await cache_system.get_bulk(["bulk:key1", "bulk:key2", "bulk:key3"])
        assert len(results) == 3
        assert all(result is not None for result in results.values())


class TestFallbackMechanisms:
    """Test fallback mechanisms for Redis unavailability"""

    @pytest.mark.asyncio
    async def test_redis_unavailable_fallback(self):
        """Test graceful fallback when Redis is unavailable"""
        from services.caching.cache_manager import CacheManager

        # Mock Redis failure
        with patch("database.redis_client.get_redis_client", side_effect=Exception("Redis down")):
            cache = CacheManager()

            # Should initialize with fallback
            await cache.initialize()

            # Should work with L1 only
            await cache.set("fallback:key", {"data": "fallback"}, ttl=300)
            result = await cache.get("fallback:key")

            assert result == {"data": "fallback"}

            await cache.close()

    @pytest.mark.asyncio
    async def test_redis_reconnection(self):
        """Test Redis reconnection after failure"""
        from services.caching.cache_manager import CacheManager

        mock_redis = MockRedisClient()

        # Start with failure
        call_count = 0

        def mock_get_redis():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Redis temporarily down")
            return mock_redis

        with patch("database.redis_client.get_redis_client", side_effect=mock_get_redis):
            cache = CacheManager()

            # First initialization fails but falls back
            await cache.initialize()

            # Set data in L1
            await cache.set("reconnect:key", {"data": "reconnect"}, ttl=300)

            # Simulate reconnection
            cache._redis_available = True
            cache._redis = mock_redis

            # Data should sync to L2
            result = await cache.get("reconnect:key")
            assert result == {"data": "reconnect"}

            # Verify in L2
            l2_data = await mock_redis.get("reconnect:key")
            assert l2_data is not None

            await cache.close()

    @pytest.mark.asyncio
    async def test_degraded_mode_operations(self):
        """Test operations in degraded mode (L1 only)"""
        from services.caching.cache_manager import CacheManager

        with patch(
            "database.redis_client.get_redis_client",
            side_effect=Exception("Redis permanently down"),
        ):
            cache = CacheManager()
            await cache.initialize()

            # All operations should work in L1-only mode
            await cache.set("degraded:key", {"data": "degraded"}, ttl=300)
            result = await cache.get("degraded:key")
            assert result == {"data": "degraded"}

            # Invalidation should work
            await cache.invalidate("degraded:key")
            result = await cache.get("degraded:key")
            assert result is None

            await cache.close()


class TestIntegrationDatabaseLayer:
    """Test integration with database layer"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for database integration testing"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_database_query_result_caching(self, cache_system):
        """Test caching database query results"""

        # Mock database query
        async def mock_db_query(query_id: str):
            # Simulate DB load
            await asyncio.sleep(0.01)
            return {"id": query_id, "results": [1, 2, 3]}

        # First call - cache miss, DB query
        start_time = time.time()
        result1 = await cache_system.get_or_set_db_query(
            "query:users:active", mock_db_query, ttl=300
        )
        first_call_time = time.time() - start_time

        # Second call - cache hit
        start_time = time.time()
        result2 = await cache_system.get_or_set_db_query(
            "query:users:active", mock_db_query, ttl=300
        )
        second_call_time = time.time() - start_time

        assert result1 == result2
        assert result1["results"] == [1, 2, 3]
        # Second call should be significantly faster
        assert second_call_time < first_call_time * 0.5

    @pytest.mark.asyncio
    async def test_database_invalidation_on_update(self, cache_system):
        """Test cache invalidation when database is updated"""
        # Cache some data
        await cache_system.set("db:user:123", {"name": "John"}, ttl=300)

        # Simulate database update
        await cache_system.invalidate_db_entity("user", "123")

        # Cache should be invalidated
        result = await cache_system.get("db:user:123")
        assert result is None


class TestIntegrationAPILayer:
    """Test integration with API layer"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for API integration testing"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_api_response_caching(self, cache_system):
        """Test caching API responses"""

        # Mock API call
        async def mock_api_call(endpoint: str, params: dict):
            await asyncio.sleep(0.02)  # Simulate network delay
            return {"endpoint": endpoint, "data": params, "timestamp": datetime.now().isoformat()}

        # Cache API response
        response1 = await cache_system.cache_api_response(
            "GET", "/api/users", {"page": 1}, mock_api_call, ttl=300
        )

        # Second call should be cached
        response2 = await cache_system.cache_api_response(
            "GET", "/api/users", {"page": 1}, mock_api_call, ttl=300
        )

        assert response1 == response2
        assert response1["endpoint"] == "/api/users"

    @pytest.mark.asyncio
    async def test_api_cache_invalidation_on_mutation(self, cache_system):
        """Test API cache invalidation on data mutations"""
        # Cache some API data
        await cache_system.set("api:users:list", [{"id": 1, "name": "John"}], ttl=300)

        # Simulate POST/PUT/DELETE - should invalidate related caches
        await cache_system.invalidate_api_caches("users", method="POST")

        # List cache should be invalidated
        result = await cache_system.get("api:users:list")
        assert result is None


class TestIntegrationServiceLayer:
    """Test integration with service layer"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for service integration testing"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_service_computation_caching(self, cache_system):
        """Test caching expensive service computations"""

        # Mock expensive computation
        async def expensive_calculation(x: int, y: int):
            await asyncio.sleep(0.05)  # Simulate heavy computation
            return x * y * 42

        # First call - compute and cache
        start_time = time.time()
        result1 = await cache_system.cache_service_computation(
            "calc", {"x": 10, "y": 20}, expensive_calculation, ttl=300
        )
        first_call_time = time.time() - start_time

        # Second call - cache hit
        start_time = time.time()
        result2 = await cache_system.cache_service_computation(
            "calc", {"x": 10, "y": 20}, expensive_calculation, ttl=300
        )
        second_call_time = time.time() - start_time

        assert result1 == result2 == 10 * 20 * 42
        assert second_call_time < first_call_time * 0.1  # Much faster

    @pytest.mark.asyncio
    async def test_external_api_caching(self, cache_system):
        """Test caching external API calls"""

        # Mock external API call
        async def external_api_call(service: str, endpoint: str):
            await asyncio.sleep(0.03)  # Simulate network delay
            return {"service": service, "endpoint": endpoint, "status": "success"}

        # Cache external API response
        response1 = await cache_system.cache_external_api(
            "stripe",
            "customers/list",
            external_api_call,
            ttl=600,  # External APIs cached longer
        )

        # Second call cached
        response2 = await cache_system.cache_external_api(
            "stripe", "customers/list", external_api_call, ttl=600
        )

        assert response1 == response2
        assert response1["service"] == "stripe"


class TestConfigurationAndFeatures:
    """Test configuration options and feature flags"""

    @pytest.mark.asyncio
    async def test_cache_enablement_config(self):
        """Test cache enablement configuration"""
        from services.caching.cache_manager import CacheManager

        # Test with caching enabled
        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager(enable_caching=True)
            await cache.initialize()

            await cache.set("config:test", {"enabled": True}, ttl=300)
            result = await cache.get("config:test")
            assert result == {"enabled": True}

            await cache.close()

    @pytest.mark.asyncio
    async def test_cache_disablement_config(self):
        """Test cache disablement configuration"""
        from services.caching.cache_manager import CacheManager

        # Test with caching disabled
        cache = CacheManager(enable_caching=False)
        await cache.initialize()

        # Operations should be no-ops
        await cache.set("disabled:test", {"disabled": True}, ttl=300)
        result = await cache.get("disabled:test")
        assert result is None  # No caching

        await cache.close()

    @pytest.mark.asyncio
    async def test_ttl_configuration(self):
        """Test configurable TTL values"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            # Custom TTL config
            ttl_config = {
                "user_profile": 1800,  # 30 minutes
                "api_response": 300,  # 5 minutes
                "computation": 3600,  # 1 hour
            }

            cache = CacheManager(ttl_config=ttl_config)
            await cache.initialize()

            # Set with named TTL
            await cache.set_with_named_ttl("user_profile", "user:123", {"name": "John"})
            result = await cache.get("user:123")
            assert result == {"name": "John"}

            await cache.close()

    @pytest.mark.asyncio
    async def test_memory_limits_configuration(self):
        """Test memory limits configuration"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            # Configure memory limits
            cache = CacheManager(l1_max_items=100, l1_max_memory_mb=10)
            await cache.initialize()

            # Verify configuration applied
            assert cache._l1_max_items == 100

            await cache.close()


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_corrupted_cache_data_handling(self):
        """Test handling of corrupted cache data"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()

            # Manually corrupt L2 data
            await mock_redis.set("corrupt:key", "invalid json", ex=300)

            # Get should handle corruption gracefully
            result = await cache.get("corrupt:key")
            assert result is None  # Should return None on corruption

            await cache.close()

    @pytest.mark.asyncio
    async def test_concurrent_access_handling(self):
        """Test concurrent cache access"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()

            # Simulate concurrent access
            async def concurrent_operation(key_suffix: int):
                key = f"concurrent:key{key_suffix}"
                await cache.set(key, {"data": f"value{key_suffix}"}, ttl=300)
                return await cache.get(key)

            # Run multiple concurrent operations
            tasks = [concurrent_operation(i) for i in range(10)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 10
            assert all(result is not None for result in results)

            await cache.close()

    @pytest.mark.asyncio
    async def test_large_data_handling(self):
        """Test handling of large cache values"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()

            # Large data (1MB)
            large_data = {"data": "x" * (1024 * 1024)}
            await cache.set("large:key", large_data, ttl=300)

            result = await cache.get("large:key")
            assert result == large_data

            await cache.close()

    @pytest.mark.asyncio
    async def test_cache_stampede_prevention(self):
        """Test prevention of cache stampede (thundering herd)"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()

            # Simulate multiple requests for same missing key
            async def stampede_request():
                return await cache.get_or_compute(
                    "stampede:key", lambda: {"computed": True}, ttl=300
                )

            # All concurrent requests should get same result
            tasks = [stampede_request() for _ in range(20)]
            results = await asyncio.gather(*tasks)

            # All should return same computed value
            assert len(results) == 20
            assert all(result == {"computed": True} for result in results)

            await cache.close()


class TestPerformanceBenchmarks:
    """Performance benchmark tests"""

    @pytest.fixture
    async def cache_system(self):
        """Create cache system for benchmarking"""
        from services.caching.cache_manager import CacheManager

        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            mock_redis = MockRedisClient()
            mock_get_redis.return_value = mock_redis

            cache = CacheManager()
            await cache.initialize()
            yield cache
            await cache.close()

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, cache_system, benchmark):
        """Benchmark cache hit performance"""
        # Setup: Pre-populate cache
        for i in range(1000):
            await cache_system.set(f"bench:hit:{i}", {"data": f"value{i}"}, ttl=300)

        # Benchmark hits
        async def benchmark_hits():
            for i in range(1000):
                result = await cache_system.get(f"bench:hit:{i % 1000}")
                assert result is not None

        benchmark(benchmark_hits)

    @pytest.mark.asyncio
    async def test_cache_miss_performance(self, cache_system, benchmark):
        """Benchmark cache miss performance"""

        async def benchmark_misses():
            for i in range(100):
                result = await cache_system.get(f"bench:miss:{i}")
                assert result is None

        benchmark(benchmark_misses)

    @pytest.mark.asyncio
    async def test_cache_write_performance(self, cache_system, benchmark):
        """Benchmark cache write performance"""

        async def benchmark_writes():
            for i in range(1000):
                await cache_system.set(f"bench:write:{i}", {"data": f"value{i}"}, ttl=300)

        benchmark(benchmark_writes)

    @pytest.mark.asyncio
    async def test_concurrent_load_performance(self, cache_system, benchmark):
        """Benchmark concurrent load performance"""

        async def concurrent_load(worker_id: int):
            for i in range(100):
                key = f"concurrent:{worker_id}:{i}"
                await cache_system.set(key, {"worker": worker_id, "index": i}, ttl=300)
                result = await cache_system.get(key)
                assert result is not None

        async def benchmark_concurrent():
            tasks = [concurrent_load(i) for i in range(10)]
            await asyncio.gather(*tasks)

        benchmark(benchmark_concurrent)


# Integration test fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def cleanup_cache():
    """Clean up cache between tests"""
    # This would be implemented to clean test cache data
    yield
    # Cleanup code here
