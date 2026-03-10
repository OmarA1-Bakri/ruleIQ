"""Unit tests for services.caching.cache_metrics."""

import pytest

from services.caching.cache_metrics import CacheMetrics


class TestCacheMetricsCounters:
    def test_records_basic_operations_and_usage_tracking(self):
        metrics = CacheMetrics()

        metrics.record_hit()
        metrics.record_miss()
        metrics.record_set()
        metrics.record_delete()
        metrics.record_error()
        metrics.record_response_time(0.02)
        metrics.record_response_time(0.04)
        metrics.update_memory_usage(2048)
        metrics.update_memory_usage(1024)
        metrics.update_item_count(5)
        metrics.update_item_count(3)

        assert metrics.hits == 1
        assert metrics.misses == 1
        assert metrics.sets == 1
        assert metrics.deletes == 1
        assert metrics.errors == 1
        assert metrics.response_times == [0.02, 0.04]
        assert metrics.memory_usage_bytes == 1024
        assert metrics.max_memory_bytes == 2048
        assert metrics.total_items == 3
        assert metrics.max_items == 5

    def test_rate_calculations_handle_empty_state(self):
        metrics = CacheMetrics()

        assert metrics.get_hit_rate() == 0.0
        assert metrics.get_avg_response_time() == 0.0
        assert metrics.get_error_rate() == 0.0
        assert metrics.get_memory_efficiency() == 0.0

    def test_rate_calculations_return_expected_values(self):
        metrics = CacheMetrics(hits=8, misses=2, sets=3, deletes=1, errors=1)
        metrics.record_response_time(0.02)
        metrics.record_response_time(0.06)
        metrics.update_memory_usage(2 * 1024 * 1024)

        assert metrics.get_hit_rate() == pytest.approx(0.8)
        assert metrics.get_avg_response_time() == pytest.approx(0.04)
        assert metrics.get_error_rate() == pytest.approx(1 / 14)
        assert metrics.get_memory_efficiency() == pytest.approx(4.0)


class TestCacheMetricsAnalysis:
    def test_get_stats_returns_derived_metrics(self):
        metrics = CacheMetrics(hits=7, misses=3, sets=2, deletes=1, errors=1)
        metrics.response_times = [0.02] * 5 + [0.021] * 5
        metrics.update_memory_usage(1024 * 1024)
        metrics.update_item_count(9)

        stats = metrics.get_stats()

        assert stats["total_requests"] == 10
        assert stats["hit_rate"] == pytest.approx(0.7)
        assert stats["avg_response_time"] == pytest.approx(0.0205)
        assert stats["error_rate"] == pytest.approx(1 / 13)
        assert stats["memory_usage_mb"] == pytest.approx(1.0)
        assert stats["memory_efficiency"] == pytest.approx(7.0)
        assert stats["cache_effectiveness_score"] == pytest.approx(65.1923076923077)
        assert stats["performance_trend"] == "stable"

    def test_effectiveness_score_is_capped_at_100(self):
        metrics = CacheMetrics(hits=100)
        metrics.response_times = [0.0]

        assert metrics._calculate_effectiveness_score() == 100.0

    @pytest.mark.parametrize(
        ("response_times", "expected"),
        [
            ([0.1] * 9, "insufficient_data"),
            ([0.2] * 5 + [0.1] * 5, "improving"),
            ([0.1] * 5 + [0.2] * 5, "degrading"),
            ([0.1] * 5 + [0.105] * 5, "stable"),
        ],
    )
    def test_analyze_performance_trend(self, response_times: list[float], expected: str):
        metrics = CacheMetrics(response_times=response_times)

        assert metrics._analyze_performance_trend() == expected


class TestCacheMetricsHealth:
    def test_get_health_status_reports_critical_with_urgent_recommendation(self):
        metrics = CacheMetrics(hits=2, misses=8, sets=5, deletes=5, errors=3)
        metrics.response_times = [0.2] * 10

        health = metrics.get_health_status()

        assert health["status"] == "critical"
        assert health["recommendations"][0] == "URGENT: Cache system experiencing critical failures"
        assert "Investigate cache backend connectivity issues" in health["recommendations"]
        assert "Consider cache warming to reduce cold start times" in health["recommendations"]

    def test_get_health_status_reports_warning(self):
        metrics = CacheMetrics(hits=2, misses=8)
        metrics.response_times = [0.15] * 10

        health = metrics.get_health_status()

        assert health["status"] == "warning"
        assert "Review cache key generation to reduce cache misses" in health["recommendations"]

    def test_get_health_status_reports_healthy(self):
        metrics = CacheMetrics(hits=9, misses=1)
        metrics.response_times = [0.01] * 10

        health = metrics.get_health_status()

        assert health["status"] == "healthy"
        assert health["recommendations"] == ["Cache performance is optimal"]

    def test_reset_clears_all_state(self):
        metrics = CacheMetrics(
            hits=1,
            misses=1,
            sets=1,
            deletes=1,
            errors=1,
            response_times=[0.02],
            memory_usage_bytes=512,
            max_memory_bytes=1024,
            total_items=2,
            max_items=4,
        )

        metrics.reset()

        assert metrics == CacheMetrics()
