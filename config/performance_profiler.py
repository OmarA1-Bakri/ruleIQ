"""

Performance Profiling and Monitoring for ruleIQ

Provides detailed performance metrics, bottleneck identification,
and optimization recommendations for API endpoints and database operations.
"""

import time
import psutil
import asyncio
import statistics
from typing import Dict, List, Any, Optional, AsyncGenerator, Generator
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance measurement"""

    operation: str
    duration_ms: float
    timestamp: float
    memory_usage_mb: float
    cpu_percent: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceStats:
    """Aggregated performance statistics"""

    operation: str
    count: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    total_duration_ms: float
    avg_memory_mb: float
    avg_cpu_percent: float
    error_count: int = 0


class PerformanceProfiler:
    """Real-time performance profiler"""

    def __init__(self, max_samples: int = 1000) -> None:
        self.max_samples = max_samples
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self.active_operations: Dict[str, float] = {}
        self.error_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._process = psutil.Process()

    def record_metric(self, metric: PerformanceMetric) -> None:
        """Record a performance metric"""
        with self._lock:
            self.metrics[metric.operation].append(metric)

    def get_stats(self, operation: str) -> Optional[PerformanceStats]:
        """Get aggregated statistics for an operation"""
        with self._lock:
            if operation not in self.metrics or not self.metrics[operation]:
                return None
            metrics_list = list(self.metrics[operation])
            durations = [m.duration_ms for m in metrics_list]
            memory_usage = [m.memory_usage_mb for m in metrics_list]
            cpu_usage = [m.cpu_percent for m in metrics_list]
            return PerformanceStats(
                operation=operation,
                count=len(durations),
                avg_duration_ms=statistics.mean(durations),
                min_duration_ms=min(durations),
                max_duration_ms=max(durations),
                p50_duration_ms=statistics.median(durations),
                p95_duration_ms=self._percentile(durations, 0.95),
                p99_duration_ms=self._percentile(durations, 0.99),
                total_duration_ms=sum(durations),
                avg_memory_mb=statistics.mean(memory_usage) if memory_usage else 0,
                avg_cpu_percent=statistics.mean(cpu_usage) if cpu_usage else 0,
                error_count=self.error_counts[operation],
            )

    def get_all_stats(self) -> Dict[str, PerformanceStats]:
        """Get statistics for all operations"""
        with self._lock:
            return {
                operation: self.get_stats(operation)
                for operation in self.metrics
                if self.get_stats(operation) is not None
            }

    def get_slowest_operations(self, limit: int = 10) -> List[PerformanceStats]:
        """Get the slowest operations by average duration"""
        all_stats = self.get_all_stats()
        return sorted(all_stats.values(), key=lambda s: s.avg_duration_ms, reverse=True)[:limit]

    def get_most_frequent_operations(self, limit: int = 10) -> List[PerformanceStats]:
        """Get the most frequently called operations"""
        all_stats = self.get_all_stats()
        return sorted(all_stats.values(), key=lambda s: s.count, reverse=True)[:limit]

    def record_error(self, operation: str) -> None:
        """Record an error for an operation"""
        with self._lock:
            self.error_counts[operation] += 1

    def clear_metrics(self, operation: Optional[str] = None) -> None:
        """Clear metrics for a specific operation or all operations"""
        with self._lock:
            if operation:
                self.metrics[operation].clear()
                self.error_counts[operation] = 0
            else:
                self.metrics.clear()
                self.error_counts.clear()

    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile value"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    @contextmanager
    def profile_operation(
        self, operation: str, context: Optional[Dict[str, Any]] = None
    ) -> Generator[Any, None, None]:
        """Context manager to profile a synchronous operation"""
        start_time = time.perf_counter()
        self._process.memory_info().rss / 1024 / 1024
        self._process.cpu_percent()
        try:
            yield
        except (ValueError, TypeError):
            self.record_error(operation)
            raise
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            end_memory = self._process.memory_info().rss / 1024 / 1024
            end_cpu = self._process.cpu_percent()
            metric = PerformanceMetric(
                operation=operation,
                duration_ms=duration_ms,
                timestamp=end_time,
                memory_usage_mb=end_memory,
                cpu_percent=end_cpu,
                context=context or {},
            )
            self.record_metric(metric)

    @asynccontextmanager
    async def profile_async_operation(
        self, operation: str, context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Any, None]:
        """Context manager to profile an asynchronous operation"""
        start_time = time.perf_counter()
        self._process.memory_info().rss / 1024 / 1024
        self._process.cpu_percent()
        try:
            yield
        except (ValueError, TypeError):
            self.record_error(operation)
            raise
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            end_memory = self._process.memory_info().rss / 1024 / 1024
            end_cpu = self._process.cpu_percent()
            metric = PerformanceMetric(
                operation=operation,
                duration_ms=duration_ms,
                timestamp=end_time,
                memory_usage_mb=end_memory,
                cpu_percent=end_cpu,
                context=context or {},
            )
            self.record_metric(metric)


class APIPerformanceMonitor:
    """Monitor API endpoint performance specifically"""

    def __init__(self, profiler: PerformanceProfiler) -> None:
        self.profiler = profiler
        self.endpoint_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def profile_endpoint(self, endpoint: str, method: str = "GET") -> Any:
        """Decorator to profile API endpoint performance"""

        def decorator(func) -> Any:
            if asyncio.iscoroutinefunction(func):

                @wraps(func)
                async def async_wrapper(*args, **kwargs) -> Dict[str, Any]:
                    operation = f"{method} {endpoint}"
                    context = {
                        "endpoint": endpoint,
                        "method": method,
                        "args_count": len(args),
                        "kwargs_count": len(kwargs),
                    }
                    async with self.profiler.profile_async_operation(operation, context):
                        result = await func(*args, **kwargs)
                    self._update_endpoint_stats(endpoint, method)
                    return result

                return async_wrapper
            else:

                @wraps(func)
                def sync_wrapper(*args, **kwargs) -> Dict[str, Any]:
                    operation = f"{method} {endpoint}"
                    context = {
                        "endpoint": endpoint,
                        "method": method,
                        "args_count": len(args),
                        "kwargs_count": len(kwargs),
                    }
                    with self.profiler.profile_operation(operation, context):
                        result = func(*args, **kwargs)
                    self._update_endpoint_stats(endpoint, method)
                    return result

                return sync_wrapper

        return decorator

    def _update_endpoint_stats(self, endpoint: str, method: str):
        """Update endpoint-specific statistics"""
        key = f"{method} {endpoint}"
        if key not in self.endpoint_stats:
            self.endpoint_stats[key] = {"call_count": 0, "last_called": None}
        self.endpoint_stats[key]["call_count"] += 1
        self.endpoint_stats[key]["last_called"] = time.time()

    def get_endpoint_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive endpoint performance report"""
        all_stats = self.profiler.get_all_stats()
        report = {
            "slowest_endpoints": [],
            "most_called_endpoints": [],
            "error_prone_endpoints": [],
            "performance_summary": {
                "total_operations": sum((s.count for s in all_stats.values())),
                "total_errors": sum((s.error_count for s in all_stats.values())),
                "avg_response_time": statistics.mean(
                    [s.avg_duration_ms for s in all_stats.values()]
                )
                if all_stats
                else 0,
            },
        }
        slowest = sorted(all_stats.values(), key=lambda s: s.avg_duration_ms, reverse=True)[:10]
        report["slowest_endpoints"] = [
            {
                "endpoint": s.operation,
                "avg_duration_ms": s.avg_duration_ms,
                "p95_duration_ms": s.p95_duration_ms,
                "call_count": s.count,
            }
            for s in slowest
        ]
        most_called = sorted(all_stats.values(), key=lambda s: s.count, reverse=True)[:10]
        report["most_called_endpoints"] = [
            {
                "endpoint": s.operation,
                "call_count": s.count,
                "avg_duration_ms": s.avg_duration_ms,
                "total_time_ms": s.total_duration_ms,
            }
            for s in most_called
        ]
        error_prone = [s for s in all_stats.values() if s.error_count > 0]
        error_prone.sort(key=lambda s: s.error_count, reverse=True)
        report["error_prone_endpoints"] = [
            {
                "endpoint": s.operation,
                "error_count": s.error_count,
                "total_calls": s.count,
                "error_rate": s.error_count / s.count * 100 if s.count > 0 else 0,
            }
            for s in error_prone[:10]
        ]
        return report


class DatabasePerformanceMonitor:
    """Monitor database operation performance"""

    def __init__(self, profiler: PerformanceProfiler) -> None:
        self.profiler = profiler
        self.query_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def profile_query(self, query_type: str, table: str = "unknown") -> Any:
        """Decorator to profile database queries"""

        def decorator(func) -> Any:
            if asyncio.iscoroutinefunction(func):

                @wraps(func)
                async def async_wrapper(*args, **kwargs) -> Any:
                    operation = f"db.{query_type}.{table}"
                    context = {"query_type": query_type, "table": table, "database": "postgresql"}
                    async with self.profiler.profile_async_operation(operation, context):
                        return await func(*args, **kwargs)

                return async_wrapper
            else:

                @wraps(func)
                def sync_wrapper(*args, **kwargs) -> Any:
                    operation = f"db.{query_type}.{table}"
                    context = {"query_type": query_type, "table": table, "database": "postgresql"}
                    with self.profiler.profile_operation(operation, context):
                        return func(*args, **kwargs)

                return sync_wrapper

        return decorator

    def get_slow_queries_report(self, threshold_ms: float = 100.0) -> List[Dict[str, Any]]:
        """Get report of slow database queries"""
        all_stats = self.profiler.get_all_stats()
        slow_queries = []
        for operation, stats in all_stats.items():
            if operation.startswith("db.") and stats.avg_duration_ms > threshold_ms:
                slow_queries.append(
                    {
                        "operation": operation,
                        "avg_duration_ms": stats.avg_duration_ms,
                        "max_duration_ms": stats.max_duration_ms,
                        "p95_duration_ms": stats.p95_duration_ms,
                        "call_count": stats.count,
                        "total_time_ms": stats.total_duration_ms,
                    }
                )
        return sorted(slow_queries, key=lambda q: q["avg_duration_ms"], reverse=True)


global_profiler = PerformanceProfiler()
api_monitor = APIPerformanceMonitor(global_profiler)
db_monitor = DatabasePerformanceMonitor(global_profiler)


def profile_api_endpoint(endpoint: str, method: str = "GET") -> Any:
    """Convenience decorator for API endpoints"""
    return api_monitor.profile_endpoint(endpoint, method)


def profile_db_query(query_type: str, table: str = "unknown") -> Any:
    """Convenience decorator for database queries"""
    return db_monitor.profile_query(query_type, table)


def get_performance_report() -> Dict[str, Any]:
    """Get comprehensive performance report"""
    return {
        "api_performance": api_monitor.get_endpoint_performance_report(),
        "database_performance": {
            "slow_queries": db_monitor.get_slow_queries_report(),
            "total_db_operations": len(
                [k for k in global_profiler.get_all_stats() if k.startswith("db.")]
            ),
        },
        "system_metrics": {
            "total_operations": len(global_profiler.get_all_stats()),
            "total_samples": sum((len(samples) for samples in global_profiler.metrics.values())),
            "total_errors": sum(global_profiler.error_counts.values()),
        },
    }


def clear_all_metrics() -> None:
    """Clear all performance metrics"""
    global_profiler.clear_metrics()
