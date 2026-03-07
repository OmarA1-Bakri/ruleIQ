"""
Cache Performance Metrics and Monitoring

This module provides comprehensive metrics collection for cache performance monitoring,
including hit/miss ratios, response times, memory usage, and error tracking.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field

# Security and Performance Constants
CRITICAL_ERROR_RATE_THRESHOLD = 0.1  # 10% error rate threshold
WARNING_HIT_RATE_THRESHOLD = 0.5  # 50% hit rate threshold
WARNING_RESPONSE_TIME_THRESHOLD = 0.1  # 100ms response time threshold
HEALTHY_HIT_RATE_THRESHOLD = 0.7  # 70% hit rate for recommendations
ACCEPTABLE_ERROR_RATE = 0.05  # 5% acceptable error rate
ACCEPTABLE_RESPONSE_TIME = 0.05  # 50ms acceptable response time

# Effectiveness Score Weights
HIT_RATE_WEIGHT = 40  # 40% weight for hit rate
RESPONSE_TIME_WEIGHT = 30  # 30% weight for response time
ERROR_RATE_WEIGHT = 30  # 30% weight for error rate
MAX_RESPONSE_TIME_PENALTY = 30  # Maximum penalty for response time

# Trend Analysis Constants
TREND_IMPROVEMENT_THRESHOLD = 0.9  # 90% threshold for improvement
TREND_DEGRADATION_THRESHOLD = 1.1  # 110% threshold for degradation
MIN_SAMPLES_FOR_TREND = 10  # Minimum samples for trend analysis


@dataclass
class CacheMetrics:
    """
    Comprehensive cache performance metrics collector.

    Tracks hits, misses, response times, memory usage, and error rates
    to provide insights into cache effectiveness and system health.
    """

    # Basic counters
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0

    # Response time tracking
    response_times: List[float] = field(default_factory=list)

    # Memory tracking
    memory_usage_bytes: int = 0
    max_memory_bytes: int = 0

    # Cache size tracking
    total_items: int = 0
    max_items: int = 0

    def record_hit(self) -> None:
        """Record a cache hit"""
        self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss"""
        self.misses += 1

    def record_set(self) -> None:
        """Record a cache set operation"""
        self.sets += 1

    def record_delete(self) -> None:
        """Record a cache delete operation"""
        self.deletes += 1

    def record_error(self) -> None:
        """Record a cache error"""
        self.errors += 1

    def record_response_time(self, response_time: float) -> None:
        """Record response time for an operation"""
        self.response_times.append(response_time)

    def update_memory_usage(self, bytes_used: int) -> None:
        """Update memory usage tracking"""
        self.memory_usage_bytes = bytes_used
        self.max_memory_bytes = max(self.max_memory_bytes, bytes_used)

    def update_item_count(self, item_count: int) -> None:
        """Update item count tracking"""
        self.total_items = item_count
        self.max_items = max(self.max_items, item_count)

    def get_hit_rate(self) -> float:
        """Calculate current hit rate"""
        total_requests = self.hits + self.misses
        return self.hits / total_requests if total_requests > 0 else 0.0

    def get_avg_response_time(self) -> float:
        """Calculate average response time"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    def get_error_rate(self) -> float:
        """Calculate error rate"""
        total_operations = self.hits + self.misses + self.sets + self.deletes
        return self.errors / total_operations if total_operations > 0 else 0.0

    def get_memory_efficiency(self) -> float:
        """Calculate memory efficiency (hits per MB)"""
        memory_mb = self.memory_usage_bytes / (1024 * 1024)
        return self.hits / memory_mb if memory_mb > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            # Basic metrics
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            # Derived metrics
            "total_requests": self.hits + self.misses,
            "hit_rate": self.get_hit_rate(),
            "avg_response_time": self.get_avg_response_time(),
            "error_rate": self.get_error_rate(),
            # Memory metrics
            "memory_usage_bytes": self.memory_usage_bytes,
            "memory_usage_mb": self.memory_usage_bytes / (1024 * 1024),
            "max_memory_bytes": self.max_memory_bytes,
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "memory_efficiency": self.get_memory_efficiency(),
            # Size metrics
            "total_items": self.total_items,
            "max_items": self.max_items,
            # Performance indicators
            "cache_effectiveness_score": self._calculate_effectiveness_score(),
            "performance_trend": self._analyze_performance_trend(),
        }

    def _calculate_effectiveness_score(self) -> float:
        """
        Calculate overall cache effectiveness score (0-100).

        Combines hit rate, response time, and error rate into a single score.
        """
        hit_rate_score = self.get_hit_rate() * HIT_RATE_WEIGHT  # Hit rate contribution
        # Response time contribution (convert to ms)
        response_time_score = max(
            0, MAX_RESPONSE_TIME_PENALTY - (self.get_avg_response_time() * 1000)
        )
        error_score = (1 - self.get_error_rate()) * ERROR_RATE_WEIGHT  # Error rate contribution

        return min(100.0, hit_rate_score + response_time_score + error_score)

    def _analyze_performance_trend(self) -> str:
        """Analyze recent performance trend"""
        if len(self.response_times) < MIN_SAMPLES_FOR_TREND:
            return "insufficient_data"

        # Check last 10 response times vs previous 10
        mid_point = len(self.response_times) // 2
        recent_avg = sum(self.response_times[mid_point:]) / len(self.response_times[mid_point:])
        earlier_avg = sum(self.response_times[:mid_point]) / len(self.response_times[:mid_point])

        if recent_avg < earlier_avg * TREND_IMPROVEMENT_THRESHOLD:
            return "improving"
        elif recent_avg > earlier_avg * TREND_DEGRADATION_THRESHOLD:
            return "degrading"
        else:
            return "stable"

    def reset(self) -> None:
        """Reset all metrics"""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.response_times.clear()
        self.memory_usage_bytes = 0
        self.max_memory_bytes = 0
        self.total_items = 0
        self.max_items = 0

    def get_health_status(self) -> Dict[str, Any]:
        """Get cache health status assessment"""
        hit_rate = self.get_hit_rate()
        error_rate = self.get_error_rate()
        avg_response_time = self.get_avg_response_time()

        # Determine health status
        if error_rate > CRITICAL_ERROR_RATE_THRESHOLD:  # Critical error threshold
            status = "critical"
        elif (
            hit_rate < WARNING_HIT_RATE_THRESHOLD
            or avg_response_time > WARNING_RESPONSE_TIME_THRESHOLD
        ):
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "hit_rate": hit_rate,
            "error_rate": error_rate,
            "avg_response_time": avg_response_time,
            "recommendations": self._get_health_recommendations(
                status, hit_rate, error_rate, avg_response_time
            ),
        }

    def _get_health_recommendations(
        self, status: str, hit_rate: float, error_rate: float, avg_response_time: float
    ) -> List[str]:
        """Generate health recommendations based on metrics"""
        recommendations = []

        if hit_rate < HEALTHY_HIT_RATE_THRESHOLD:
            recommendations.append("Consider increasing cache TTL values for better hit rates")
            recommendations.append("Review cache key generation to reduce cache misses")

        if error_rate > ACCEPTABLE_ERROR_RATE:
            recommendations.append("Investigate cache backend connectivity issues")
            recommendations.append("Check Redis/memory configuration and limits")

        if avg_response_time > ACCEPTABLE_RESPONSE_TIME:
            recommendations.append("Consider cache warming to reduce cold start times")
            recommendations.append("Review cache size limits and memory allocation")

        if status == "critical":
            recommendations.insert(0, "URGENT: Cache system experiencing critical failures")

        if not recommendations:
            recommendations.append("Cache performance is optimal")

        return recommendations
