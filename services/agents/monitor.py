"""
Agent Monitor Service - Performance monitoring and health checks.

Implements metrics collection, resource tracking, and health monitoring.
"""

from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio
import logging
import psutil
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of metrics to collect."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    AVAILABILITY = "availability"
    DECISION_ACCURACY = "decision_accuracy"


@dataclass
class PerformanceMetric:
    """Represents a performance metric."""

    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent_id: Optional[UUID] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Represents a health check result."""

    agent_id: UUID
    status: HealthStatus
    checks: Dict[str, bool] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""


@dataclass
class ResourceUsage:
    """Tracks resource usage."""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    active_threads: int = 0
    open_files: int = 0


class CircuitBreaker:
    """Circuit breaker for error handling."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: timedelta = timedelta(seconds=60),
        half_open_requests: int = 3,
    ) -> None:
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
        self.half_open_attempts = 0

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.half_open_attempts = 0
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if self.last_failure_time:
            elapsed = datetime.utcnow() - self.last_failure_time
            return elapsed >= self.recovery_timeout
        return False

    def _on_success(self):
        """Handle successful call."""
        if self.state == "half_open":
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_requests:
                self.state = "closed"
                self.failure_count = 0
                logger.info("Circuit breaker closed")

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        elif self.state == "half_open":
            self.state = "open"
            logger.warning("Circuit breaker reopened")


class AgentMonitor:
    """Monitors agent performance and health."""

    def __init__(
        self, metrics_window: timedelta = timedelta(minutes=5), health_check_interval: float = 30.0
    ) -> None:
        """Initialize agent monitor."""
        self.metrics_window = metrics_window
        self.health_check_interval = health_check_interval
        self.metrics_buffer: Dict[UUID, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.health_status: Dict[UUID, HealthCheck] = {}
        self.resource_usage: Dict[UUID, ResourceUsage] = {}
        self.circuit_breakers: Dict[UUID, CircuitBreaker] = {}
        self.alert_handlers: List[callable] = []
        self._monitoring_task = None

    async def start_monitoring(self):
        """Start monitoring loop."""
        if not self._monitoring_task:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Started agent monitoring")

    async def stop_monitoring(self):
        """Stop monitoring loop."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None
            logger.info("Stopped agent monitoring")

    def record_metric(
        self,
        agent_id: UUID,
        metric_type: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(
            metric_type=metric_type, value=value, agent_id=agent_id, metadata=metadata or {}
        )

        self.metrics_buffer[agent_id].append(metric)

        # Check for anomalies
        if self._is_anomaly(agent_id, metric):
            self._trigger_alert(agent_id, f"Anomaly detected: {metric_type.value} = {value}")

    def _is_anomaly(self, agent_id: UUID, metric: PerformanceMetric) -> bool:
        """Detect if metric is anomalous."""
        # Simple threshold-based anomaly detection
        thresholds = {
            MetricType.LATENCY: 1000,  # ms
            MetricType.ERROR_RATE: 0.1,  # 10%
            MetricType.RESOURCE_USAGE: 80,  # 80%
            MetricType.AVAILABILITY: 0.95,  # 95%
        }

        threshold = thresholds.get(metric.metric_type)
        if threshold:
            if metric.metric_type == MetricType.AVAILABILITY:
                return metric.value < threshold
            else:
                return metric.value > threshold
        return False

    async def perform_health_check(self, agent_id: UUID) -> HealthCheck:
        """Perform health check for an agent."""
        checks = {}
        metrics = {}

        # Check responsiveness
        checks["responsive"] = await self._check_responsiveness(agent_id)

        # Check resource usage
        resource_ok, resource_usage = await self._check_resource_usage(agent_id)
        checks["resource_usage"] = resource_ok
        metrics.update(resource_usage)

        # Check error rate
        error_rate = self._calculate_error_rate(agent_id)
        checks["error_rate"] = error_rate < 0.1
        metrics["error_rate"] = error_rate

        # Check latency
        avg_latency = self._calculate_avg_latency(agent_id)
        checks["latency"] = avg_latency < 1000
        metrics["avg_latency_ms"] = avg_latency

        # Determine overall status
        failed_checks = sum(1 for ok in checks.values() if not ok)

        if failed_checks == 0:
            status = HealthStatus.HEALTHY
            message = "All checks passed"
        elif failed_checks == 1:
            status = HealthStatus.DEGRADED
            message = f"{failed_checks} check failed"
        elif failed_checks <= 2:
            status = HealthStatus.UNHEALTHY
            message = f"{failed_checks} checks failed"
        else:
            status = HealthStatus.CRITICAL
            message = f"{failed_checks} checks failed - critical"

        health_check = HealthCheck(
            agent_id=agent_id, status=status, checks=checks, metrics=metrics, message=message
        )

        self.health_status[agent_id] = health_check

        # Trigger alert if unhealthy
        if status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            self._trigger_alert(agent_id, f"Health check failed: {message}")

        return health_check

    async def _check_responsiveness(self, agent_id: UUID) -> bool:
        """Check if agent is responsive."""
        # Simulate ping check
        await asyncio.sleep(0.01)
        return True  # Placeholder

    async def _check_resource_usage(self, agent_id: UUID) -> Tuple[bool, Dict[str, float]]:
        """Check resource usage for an agent."""
        try:
            # Get system resource usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network = psutil.net_io_counters()

            usage = ResourceUsage(
                cpu_percent=cpu_percent,
                memory_mb=memory.used / (1024 * 1024),
                memory_percent=memory.percent,
                disk_io_read_mb=disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                disk_io_write_mb=disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                network_sent_mb=network.bytes_sent / (1024 * 1024) if network else 0,
                network_recv_mb=network.bytes_recv / (1024 * 1024) if network else 0,
            )

            self.resource_usage[agent_id] = usage

            # Check if within limits
            ok = cpu_percent < 80 and memory.percent < 90

            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_mb": usage.memory_mb,
            }

            return ok, metrics

        except Exception as e:
            logger.error(f"Failed to check resource usage: {e}")
            return False, {}

    def _calculate_error_rate(self, agent_id: UUID) -> float:
        """Calculate error rate for an agent."""
        metrics = self.metrics_buffer.get(agent_id, deque())

        if not metrics:
            return 0.0

        error_metrics = [
            m
            for m in metrics
            if m.metric_type == MetricType.ERROR_RATE
            and (datetime.utcnow() - m.timestamp) < self.metrics_window
        ]

        if error_metrics:
            return sum(m.value for m in error_metrics) / len(error_metrics)
        return 0.0

    def _calculate_avg_latency(self, agent_id: UUID) -> float:
        """Calculate average latency for an agent."""
        metrics = self.metrics_buffer.get(agent_id, deque())

        if not metrics:
            return 0.0

        latency_metrics = [
            m
            for m in metrics
            if m.metric_type == MetricType.LATENCY
            and (datetime.utcnow() - m.timestamp) < self.metrics_window
        ]

        if latency_metrics:
            return sum(m.value for m in latency_metrics) / len(latency_metrics)
        return 0.0

    def get_metrics_summary(
        self, agent_id: UUID, time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get metrics summary for an agent."""
        window = time_window or self.metrics_window
        cutoff_time = datetime.utcnow() - window

        metrics = self.metrics_buffer.get(agent_id, deque())
        recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]

        if not recent_metrics:
            return {}

        # Group by type
        by_type = defaultdict(list)
        for metric in recent_metrics:
            by_type[metric.metric_type].append(metric.value)

        # Calculate summaries
        summary = {}
        for metric_type, values in by_type.items():
            if values:
                summary[metric_type.value] = {
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }

        # Add resource usage
        if agent_id in self.resource_usage:
            summary["resource_usage"] = asdict(self.resource_usage[agent_id])

        # Add health status
        if agent_id in self.health_status:
            summary["health"] = {
                "status": self.health_status[agent_id].status.value,
                "checks": self.health_status[agent_id].checks,
                "message": self.health_status[agent_id].message,
            }

        return summary

    def get_circuit_breaker(self, agent_id: UUID) -> CircuitBreaker:
        """Get or create circuit breaker for an agent."""
        if agent_id not in self.circuit_breakers:
            self.circuit_breakers[agent_id] = CircuitBreaker()
        return self.circuit_breakers[agent_id]

    def register_alert_handler(self, handler: callable):
        """Register an alert handler."""
        self.alert_handlers.append(handler)

    def _trigger_alert(self, agent_id: UUID, message: str):
        """Trigger an alert."""
        alert = {
            "agent_id": str(agent_id),
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.warning(f"Alert for agent {agent_id}: {message}")

        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while True:
            try:
                # Perform health checks
                for agent_id in list(self.health_status.keys()):
                    await self.perform_health_check(agent_id)

                # Clean old metrics
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                for agent_id, metrics in self.metrics_buffer.items():
                    while metrics and metrics[0].timestamp < cutoff_time:
                        metrics.popleft()

                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.health_check_interval)

    def create_health_endpoint_data(self) -> Dict[str, Any]:
        """Create data for health check endpoint."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "agents": {
                str(agent_id): {
                    "status": health.status.value,
                    "checks": health.checks,
                    "metrics": health.metrics,
                    "last_check": health.timestamp.isoformat(),
                }
                for agent_id, health in self.health_status.items()
            },
            "overall_status": self._calculate_overall_status().value,
        }

    def _calculate_overall_status(self) -> HealthStatus:
        """Calculate overall system health status."""
        if not self.health_status:
            return HealthStatus.HEALTHY

        statuses = [h.status for h in self.health_status.values()]

        if any(s == HealthStatus.CRITICAL for s in statuses):
            return HealthStatus.CRITICAL
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
