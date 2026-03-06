"""
import requests
import logging


logger = logging.getLogger(__name__)
# Constants
CONFIDENCE_THRESHOLD = 0.8
MAX_ITEMS = 1000


Comprehensive Performance Monitoring Service
Tracks API response times, database performance, and system metrics
"""

import asyncio
import time
import psutil
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, AsyncGenerator
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from sqlalchemy import text
from database.db_setup import get_async_db, get_engine_info
from config.cache import get_cache_manager
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""

    timestamp: datetime
    api_response_time: float
    database_query_time: float
    cache_hit_rate: float
    memory_usage_percent: float
    cpu_usage_percent: float
    active_connections: int
    requests_per_second: float


@dataclass
class DatabaseMetrics:
    """Database-specific performance metrics."""

    connection_pool_size: int
    active_connections: int
    connection_pool_utilization: float
    avg_query_time: float
    slow_queries_count: int
    deadlocks_count: int


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hit_rate: float
    miss_rate: float
    eviction_rate: float
    memory_usage: int
    total_requests: int
    avg_response_time: float


@dataclass
class APIMetrics:
    """API performance metrics."""

    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    slowest_endpoints: List[Dict[str, Any]]


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.

    Tracks and analyzes:
    - API response times
    - Database performance
    - Cache efficiency
    - System resource usage
    - Performance trends
    """

    def __init__(self) -> None:
        self.response_times: List[float] = []
        self.api_metrics: Dict[str, List[float]] = {}
        self.slow_query_threshold = 0.1
        self.performance_history: List[PerformanceMetrics] = []
        self.monitoring_active = False

    async def initialize(self) -> None:
        """Initialize performance monitoring."""
        self.cache_manager = await get_cache_manager()
        logger.info("Performance monitoring initialized")

    @asynccontextmanager
    async def track_api_call(self, endpoint: str) -> AsyncGenerator[Any, None]:
        """Context manager to track API call performance."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            await self.record_api_call(endpoint, duration)

    async def record_api_call(self, endpoint: str, duration: float) -> None:
        """Record API call performance metrics."""
        if endpoint not in self.api_metrics:
            self.api_metrics[endpoint] = []
        self.api_metrics[endpoint].append(duration)
        if len(self.api_metrics[endpoint]) > MAX_ITEMS:
            self.api_metrics[endpoint] = self.api_metrics[endpoint][-1000:]
        if duration > 2.0:
            logger.warning("Slow API call detected: %s took %ss" % (endpoint, duration))
        await self.cache_manager.set(
            f"api_metrics:{endpoint}:recent",
            {
                "avg_time": statistics.mean(self.api_metrics[endpoint][-100:]),
                "count": len(self.api_metrics[endpoint]),
                "last_call": duration,
            },
            ttl=60,
        )

    async def get_database_metrics(self) -> DatabaseMetrics:
        """Collect database performance metrics."""
        engine_info = get_engine_info()
        pool_info = engine_info.get("pool", {})
        pool_size = pool_info.get("size", 0)
        active_connections = pool_info.get("checked_out", 0)
        pool_utilization = active_connections / pool_size if pool_size > 0 else 0
        async with get_async_db() as db:
            try:
                slow_queries_result = await db.execute(
                    text(
                        """
                    SELECT count(*) as slow_count
                    FROM pg_stat_statements
                    WHERE mean_exec_time > :threshold
                """
                    ),
                    {"threshold": self.slow_query_threshold * 1000},
                )
                slow_queries_count = slow_queries_result.scalar() or 0
            except Exception:
                slow_queries_count = 0
            start_time = time.time()
            await db.execute(text("SELECT 1"))
            sample_query_time = time.time() - start_time
        return DatabaseMetrics(
            connection_pool_size=pool_size,
            active_connections=active_connections,
            connection_pool_utilization=pool_utilization,
            avg_query_time=sample_query_time,
            slow_queries_count=slow_queries_count,
            deadlocks_count=0,
        )

    async def get_cache_metrics(self) -> CacheMetrics:
        """Collect cache performance metrics."""
        try:
            if hasattr(self.cache_manager, "redis_client") and self.cache_manager.redis_client:
                info = await self.cache_manager.redis_client.info()
                keyspace_hits = info.get("keyspace_hits", 0)
                keyspace_misses = info.get("keyspace_misses", 0)
                total_requests = keyspace_hits + keyspace_misses
                hit_rate = keyspace_hits / total_requests if total_requests > 0 else 0
                miss_rate = keyspace_misses / total_requests if total_requests > 0 else 0
                return CacheMetrics(
                    hit_rate=hit_rate,
                    miss_rate=miss_rate,
                    eviction_rate=info.get("evicted_keys", 0) / total_requests
                    if total_requests > 0
                    else 0,
                    memory_usage=info.get("used_memory", 0),
                    total_requests=total_requests,
                    avg_response_time=0.001,
                )
            else:
                return CacheMetrics(
                    hit_rate=0.8,
                    miss_rate=0.2,
                    eviction_rate=0.0,
                    memory_usage=len(self.cache_manager.memory_cache) * 1024,
                    total_requests=1000,
                    avg_response_time=0.0001,
                )
        except requests.RequestException as e:
            logger.warning("Failed to get cache metrics: %s" % e)
            return CacheMetrics(0, 0, 0, 0, 0, 0.001)

    async def get_api_metrics(self) -> APIMetrics:
        """Collect API performance metrics."""
        if not self.api_metrics:
            return APIMetrics(0, 0, 0, 0, 0, [])
        all_response_times = []
        slowest_endpoints = []
        for endpoint, times in self.api_metrics.items():
            if times:
                all_response_times.extend(times)
                avg_time = statistics.mean(times)
                slowest_endpoints.append(
                    {
                        "endpoint": endpoint,
                        "avg_response_time": avg_time,
                        "call_count": len(times),
                        "p95_time": sorted(times)[int(len(times) * 0.95)]
                        if len(times) > 20
                        else avg_time,
                    }
                )
        if not all_response_times:
            return APIMetrics(0, 0, 0, 0, 0, [])
        slowest_endpoints.sort(key=lambda x: x["avg_response_time"], reverse=True)
        return APIMetrics(
            avg_response_time=statistics.mean(all_response_times),
            p95_response_time=sorted(all_response_times)[int(len(all_response_times) * 0.95)],
            p99_response_time=sorted(all_response_times)[int(len(all_response_times) * 0.99)],
            requests_per_second=len(all_response_times) / 60,
            error_rate=0.0,
            slowest_endpoints=slowest_endpoints[:10],
        )

    def get_system_metrics(self) -> Dict[str, float]:
        """Get system resource metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "load_average": psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0,
        }

    async def collect_comprehensive_metrics(self) -> Dict[str, Any]:
        """Collect all performance metrics."""
        db_metrics = await self.get_database_metrics()
        cache_metrics = await self.get_cache_metrics()
        api_metrics = await self.get_api_metrics()
        system_metrics = self.get_system_metrics()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": asdict(db_metrics),
            "cache": asdict(cache_metrics),
            "api": asdict(api_metrics),
            "system": system_metrics,
            "performance_score": self.calculate_performance_score(
                db_metrics, cache_metrics, api_metrics, system_metrics
            ),
        }

    def calculate_performance_score(
        self,
        db_metrics: DatabaseMetrics,
        cache_metrics: CacheMetrics,
        api_metrics: APIMetrics,
        system_metrics: Dict[str, float],
    ) -> float:
        """Calculate overall performance score (0-100)."""
        scores = []
        db_score = 100
        if db_metrics.connection_pool_utilization > CONFIDENCE_THRESHOLD:
            db_score -= 20
        if db_metrics.avg_query_time > 0.1:
            db_score -= 30
        if db_metrics.slow_queries_count > 10:
            db_score -= 20
        scores.append(max(0, db_score))
        cache_score = cache_metrics.hit_rate * 100
        scores.append(cache_score)
        api_score = 100
        if api_metrics.avg_response_time > 0.2:
            api_score -= 40
        if api_metrics.p95_response_time > 1.0:
            api_score -= 30
        scores.append(max(0, api_score))
        system_score = 100
        if system_metrics["cpu_percent"] > 80:
            system_score -= 30
        if system_metrics["memory_percent"] > 80:
            system_score -= 30
        scores.append(max(0, system_score))
        return statistics.mean(scores)

    async def generate_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Generate performance optimization recommendations."""
        metrics = await self.collect_comprehensive_metrics()
        recommendations = []
        if metrics["database"]["connection_pool_utilization"] > CONFIDENCE_THRESHOLD:
            recommendations.append(
                {
                    "category": "database",
                    "priority": "high",
                    "issue": "Connection pool utilization high",
                    "recommendation": "Increase database connection pool size",
                    "current_value": metrics["database"]["connection_pool_size",],
                    "suggested_value": int(metrics["database"]["connection_pool_size"] * 1.5),
                    "impact": "Prevents connection timeouts under load",
                }
            )
        if metrics["database"]["avg_query_time"] > 0.1:
            recommendations.append(
                {
                    "category": "database",
                    "priority": "high",
                    "issue": "Slow average query time",
                    "recommendation": "Review and optimize slow queries, add indexes",
                    "current_value": f"{metrics['database']['avg_query_time']:.3f}s",
                    "suggested_value": "<0.1s",
                    "impact": "Improves overall API response times",
                }
            )
        if metrics["cache"]["hit_rate"] < 0.85:
            recommendations.append(
                {
                    "category": "cache",
                    "priority": "medium",
                    "issue": "Low cache hit rate",
                    "recommendation": "Optimize cache keys and TTL strategies",
                    "current_value": f"{metrics['cache']['hit_rate']:.2%}",
                    "suggested_value": ">85%",
                    "impact": "Reduces database load and improves response times",
                }
            )
        if metrics["api"]["avg_response_time"] > 0.2:
            recommendations.append(
                {
                    "category": "api",
                    "priority": "high",
                    "issue": "Slow API response times",
                    "recommendation": "Implement response caching and optimize slow endpoints",
                    "current_value": f"{metrics['api']['avg_response_time']:.3f}s",
                    "suggested_value": "<0.2s",
                    "impact": "Better user experience and system efficiency",
                }
            )
        if metrics["system"]["memory_percent"] > 80:
            recommendations.append(
                {
                    "category": "system",
                    "priority": "medium",
                    "issue": "High memory usage",
                    "recommendation": "Investigate memory leaks, optimize data structures",
                    "current_value": f"{metrics['system']['memory_percent']:.1f}%",
                    "suggested_value": "<80%",
                    "impact": "Prevents system instability and improves performance",
                }
            )
        return recommendations

    async def start_monitoring(self, interval: int = 60) -> None:
        """Start continuous performance monitoring."""
        self.monitoring_active = True
        logger.info("Starting performance monitoring with %ss interval" % interval)
        while self.monitoring_active:
            try:
                metrics = await self.collect_comprehensive_metrics()
                await self.cache_manager.set("performance_metrics:latest", metrics, ttl=300)
                if metrics["performance_score"] < 70:
                    logger.warning("Performance score low: %s/100" % metrics["performance_score"])
                self.performance_history.append(
                    PerformanceMetrics(
                        timestamp=datetime.now(timezone.utc),
                        api_response_time=metrics["api"]["avg_response_time"],
                        database_query_time=metrics["database"]["avg_query_time"],
                        cache_hit_rate=metrics["cache"]["hit_rate"],
                        memory_usage_percent=metrics["system"]["memory_percent"],
                        cpu_usage_percent=metrics["system"]["cpu_percent"],
                        active_connections=metrics["database"]["active_connections"],
                        requests_per_second=metrics["api"]["requests_per_second"],
                    )
                )
                if len(self.performance_history) > 1440:
                    self.performance_history = self.performance_history[-1440:]
            except (requests.RequestException, Exception, KeyError) as e:
                logger.error("Error in performance monitoring: %s" % e)
            await asyncio.sleep(interval)

    def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        self.monitoring_active = False
        logger.info("Performance monitoring stopped")

    async def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over time."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = [m for m in self.performance_history if m.timestamp > cutoff_time]
        if not recent_metrics:
            return {"status": "no_data", "hours": hours}
        return {
            "hours": hours,
            "data_points": len(recent_metrics),
            "trends": {
                "api_response_time": {
                    "avg": statistics.mean([m.api_response_time for m in recent_metrics]),
                    "min": min([m.api_response_time for m in recent_metrics]),
                    "max": max([m.api_response_time for m in recent_metrics]),
                },
                "cache_hit_rate": {
                    "avg": statistics.mean([m.cache_hit_rate for m in recent_metrics]),
                    "min": min([m.cache_hit_rate for m in recent_metrics]),
                    "max": max([m.cache_hit_rate for m in recent_metrics]),
                },
                "database_query_time": {
                    "avg": statistics.mean([m.database_query_time for m in recent_metrics]),
                    "min": min([m.database_query_time for m in recent_metrics]),
                    "max": max([m.database_query_time for m in recent_metrics]),
                },
            },
        }


performance_monitor = PerformanceMonitor()


async def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    if not performance_monitor.monitoring_active:
        await performance_monitor.initialize()
    return performance_monitor


def monitor_performance(endpoint_name: str = None) -> Any:
    """Decorator to monitor function performance."""

    def decorator(func) -> Any:

        async def wrapper(*args, **kwargs) -> Any:
            monitor = await get_performance_monitor()
            name = endpoint_name or f"{func.__module__}.{func.__name__}"
            async with monitor.track_api_call(name):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
