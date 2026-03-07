"""
import logging


logger = logging.getLogger(__name__)
Metrics collection and monitoring implementation.
"""

import time
import asyncio
from typing import Any, Dict, List, Optional, AsyncGenerator, Generator
from datetime import datetime, timezone
from collections import deque
from contextlib import contextmanager, asynccontextmanager
import psutil
import threading
from .logger import get_logger

logger = get_logger(__name__)


class MetricType:
    """Metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Metric:
    """Base metric class."""

    def __init__(
        self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Initialize metric."""
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.value = 0
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "labels": self.labels,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }


class Counter(Metric):
    """Counter metric - only increases."""

    def increment(self, value: float = 1.0) -> None:
        """Increment counter."""
        if value < 0:
            raise ValueError("Counter can only be incremented with positive values")
        self.value += value
        self.timestamp = datetime.now(timezone.utc)

    def reset(self) -> None:
        """Reset counter to zero."""
        self.value = 0
        self.timestamp = datetime.now(timezone.utc)


class Gauge(Metric):
    """Gauge metric - can go up and down."""

    def set(self, value: float) -> None:
        """Set gauge value."""
        self.value = value
        self.timestamp = datetime.now(timezone.utc)

    def increment(self, value: float = 1.0) -> None:
        """Increment gauge."""
        self.value += value
        self.timestamp = datetime.now(timezone.utc)

    def decrement(self, value: float = 1.0) -> None:
        """Decrement gauge."""
        self.value -= value
        self.timestamp = datetime.now(timezone.utc)


class Histogram(Metric):
    """Histogram metric for distributions."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> None:
        """Initialize histogram."""
        super().__init__(name, description, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self.bucket_counts = {b: 0 for b in self.buckets}
        self.bucket_counts[float("inf")] = 0
        self.sum = 0
        self.count = 0
        self._values = deque(maxlen=1000)

    def observe(self, value: float) -> None:
        """Observe a value."""
        self.sum += value
        self.count += 1
        self._values.append(value)
        self.timestamp = datetime.now(timezone.utc)
        for bucket in sorted(self.buckets + [float("inf")]):
            if value <= bucket:
                self.bucket_counts[bucket] += 1

    def get_percentile(self, percentile: float) -> Optional[float]:
        """Get percentile value."""
        if not self._values:
            return None
        sorted_values = sorted(self._values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = super().to_dict()
        result.update(
            {
                "sum": self.sum,
                "count": self.count,
                "mean": self.sum / self.count if self.count > 0 else 0,
                "buckets": self.bucket_counts,
                "p50": self.get_percentile(50),
                "p95": self.get_percentile(95),
                "p99": self.get_percentile(99),
            }
        )
        return result


class Summary(Histogram):
    """Summary metric - like histogram but with time windows."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        window_size: int = 300,
    ) -> None:
        """Initialize summary."""
        super().__init__(name, description, labels, buckets=None)
        self.window_size = window_size
        self._time_values = deque()

    def observe(self, value: float) -> None:
        """Observe a value with timestamp."""
        current_time = time.time()
        self._time_values.append((current_time, value))
        cutoff_time = current_time - self.window_size
        while self._time_values and self._time_values[0][0] < cutoff_time:
            self._time_values.popleft()
        self._values = deque([v for _, v in self._time_values], maxlen=1000)
        self.sum = sum((v for _, v in self._time_values))
        self.count = len(self._time_values)
        self.timestamp = datetime.now(timezone.utc)


class MetricsCollector:
    """Centralized metrics collector."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
        self._setup_default_metrics()

    def _setup_default_metrics(self) -> None:
        """Setup default application metrics."""
        self.register_counter("http_requests_total", "Total HTTP requests")
        self.register_histogram("http_request_duration_seconds", "HTTP request duration")
        self.register_counter("http_requests_failed_total", "Total failed HTTP requests")
        self.register_counter("errors_total", "Total errors")
        self.register_counter("exceptions_total", "Total exceptions")
        self.register_gauge("active_connections", "Active connections")
        self.register_gauge("memory_usage_bytes", "Memory usage in bytes")
        self.register_gauge("cpu_usage_percent", "CPU usage percentage")
        self.register_counter("compliance_checks_total", "Total compliance checks")
        self.register_histogram("compliance_check_duration_seconds", "Compliance check duration")
        self.register_counter("evidence_collected_total", "Total evidence collected")
        self.register_counter("langgraph_nodes_executed", "Total LangGraph nodes executed")
        self.register_histogram(
            "langgraph_node_duration_seconds", "LangGraph node execution duration"
        )
        self.register_counter("langgraph_errors_total", "Total LangGraph errors")

    def register_counter(
        self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None
    ) -> Counter:
        """Register a counter metric."""
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self.metrics:
                self.metrics[key] = Counter(name, description, labels)
            return self.metrics[key]

    def register_gauge(
        self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None
    ) -> Gauge:
        """Register a gauge metric."""
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self.metrics:
                self.metrics[key] = Gauge(name, description, labels)
            return self.metrics[key]

    def register_histogram(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """Register a histogram metric."""
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self.metrics:
                self.metrics[key] = Histogram(name, description, labels, buckets)
            return self.metrics[key]

    def register_summary(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        window_size: int = 300,
    ) -> Summary:
        """Register a summary metric."""
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self.metrics:
                self.metrics[key] = Summary(name, description, labels, window_size)
            return self.metrics[key]

    def get_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[Metric]:
        """Get a metric by name and labels."""
        key = self._make_key(name, labels)
        return self.metrics.get(key)

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Make a unique key for metric with labels."""
        if not labels:
            return name
        label_str = ",".join((f"{k}={v}" for k, v in sorted(labels.items())))
        return f"{name}{{{label_str}}}"

    def collect_system_metrics(self) -> None:
        """Collect system metrics."""
        try:
            memory = psutil.virtual_memory()
            self.get_metric("memory_usage_bytes").set(memory.used)
            cpu_percent = psutil.cpu_percent(interval=1)
            self.get_metric("cpu_usage_percent").set(cpu_percent)
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as dictionary."""
        with self._lock:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": [metric.to_dict() for metric in self.metrics.values()],
            }

    @contextmanager
    def timer(
        self, metric_name: str, labels: Optional[Dict[str, str]] = None
    ) -> Generator[Any, None, None]:
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            metric = self.get_metric(metric_name, labels)
            if isinstance(metric, (Histogram, Summary)):
                metric.observe(duration)

    @asynccontextmanager
    async def async_timer(
        self, metric_name: str, labels: Optional[Dict[str, str]] = None
    ) -> AsyncGenerator[Any, None]:
        """Async context manager for timing operations."""
        start_time = asyncio.get_event_loop().time()
        try:
            yield
        finally:
            duration = asyncio.get_event_loop().time() - start_time
            metric = self.get_metric(metric_name, labels)
            if isinstance(metric, (Histogram, Summary)):
                metric.observe(duration)


_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return _collector


def track_request(method: str, path: str, status_code: int, duration: float) -> None:
    """Track HTTP request metrics."""
    labels = {"method": method, "path": path, "status": str(status_code)}
    _collector.register_counter("http_requests_total", labels=labels).increment()
    _collector.register_histogram("http_request_duration_seconds", labels=labels).observe(duration)
    if status_code >= 400:
        _collector.register_counter("http_requests_failed_total", labels=labels).increment()


def track_error(error_type: str, component: str = "unknown") -> None:
    """Track error metrics."""
    labels = {"type": error_type, "component": component}
    _collector.register_counter("errors_total", labels=labels).increment()


def track_exception(exception: Exception, component: str = "unknown") -> None:
    """Track exception metrics."""
    labels = {"type": type(exception).__name__, "component": component}
    _collector.register_counter("exceptions_total", labels=labels).increment()


def track_performance(operation: str, duration: float, success: bool = True) -> None:
    """Track performance metrics."""
    labels = {"operation": operation, "success": str(success)}
    _collector.register_histogram("operation_duration_seconds", labels=labels).observe(duration)


def get_metrics() -> Dict[str, Any]:
    """Get all collected metrics."""
    _collector.collect_system_metrics()
    return _collector.get_all_metrics()
