"""
Database health monitoring and metrics.

This module provides comprehensive health monitoring, metrics collection,
and alerting capabilities for database providers.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Protocol
from enum import Enum
import contextlib

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthMetrics:
    """Health metrics data class."""

    status: HealthStatus
    response_time: float
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "response_time": self.response_time,
            "timestamp": self.timestamp,
            "details": self.details,
            "error_message": self.error_message,
        }


class HealthCheckCallback(Protocol):
    """Protocol for health check callbacks."""

    async def __call__(self, metrics: HealthMetrics) -> None:
        """Callback for health check results."""
        ...


class AlertCallback(Protocol):
    """Protocol for alert callbacks."""

    async def __call__(self, service_name: str, status: HealthStatus, message: str) -> None:
        """Callback for alerts."""
        ...


class DatabaseHealthMonitor(ABC):
    """Abstract base class for database health monitors."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self._health_callbacks: List[HealthCheckCallback] = []
        self._alert_callbacks: List[AlertCallback] = []
        self._last_health_check: Optional[HealthMetrics] = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

    @abstractmethod
    async def check_health(self) -> HealthMetrics:
        """Perform health check and return metrics."""
        pass

    def add_health_callback(self, callback: HealthCheckCallback) -> None:
        """Add a health check callback."""
        self._health_callbacks.append(callback)

    def add_alert_callback(self, callback: AlertCallback) -> None:
        """Add an alert callback."""
        self._alert_callbacks.append(callback)

    async def _notify_health_callbacks(self, metrics: HealthMetrics) -> None:
        """Notify all health callbacks."""
        for callback in self._health_callbacks:
            try:
                await callback(metrics)
            except (TypeError, ValueError, AttributeError):
                logger.exception("Health callback error")

    async def _notify_alert_callbacks(self, status: HealthStatus, message: str) -> None:
        """Notify all alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                await callback(self.provider_name, status, message)
            except (TypeError, ValueError, AttributeError):
                logger.exception("Alert callback error")

    def get_last_health_check(self) -> Optional[HealthMetrics]:
        """Get the last health check result."""
        return self._last_health_check

    def is_healthy(self) -> bool:
        """Check if the service is currently healthy."""
        if self._last_health_check is None:
            return False
        return self._last_health_check.status == HealthStatus.HEALTHY

    async def perform_health_check(self) -> HealthMetrics:
        """Perform health check with callbacks and alerting."""
        try:
            metrics = await self.check_health()
            self._last_health_check = metrics

            # Notify health callbacks
            await self._notify_health_callbacks(metrics)

            # Handle status changes and alerting
            if metrics.status == HealthStatus.UNHEALTHY:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    message = "Service %s is unhealthy after %d consecutive failures" % (
                        self.provider_name,
                        self._consecutive_failures,
                    )
                    await self._notify_alert_callbacks(HealthStatus.UNHEALTHY, message)
            else:
                if self._consecutive_failures > 0:
                    # Service recovered
                    await self._notify_alert_callbacks(
                        HealthStatus.HEALTHY,
                        "Service %s has recovered after %d failures"
                        % (self.provider_name, self._consecutive_failures),
                    )
                self._consecutive_failures = 0

            return metrics

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.exception("Health check failed for %s", self.provider_name)
            error_metrics = HealthMetrics(
                status=HealthStatus.UNHEALTHY,
                response_time=0.0,
                timestamp=time.time(),
                error_message=str(e),
            )
            self._last_health_check = error_metrics
            await self._notify_health_callbacks(error_metrics)
            return error_metrics


class PostgreSQLHealthMonitor(DatabaseHealthMonitor):
    """Health monitor for PostgreSQL database provider."""

    def __init__(self, postgres_provider) -> None:
        super().__init__("postgres")
        self.provider = postgres_provider

    async def check_health(self) -> HealthMetrics:
        """Check PostgreSQL health."""
        start_time = time.time()

        try:
            # Perform basic connectivity test
            result = await self.provider.execute_query(
                "SELECT 1 as health_check, pg_postmaster_start_time() as start_time"
            )

            if not result or len(result) == 0:
                raise ValueError("No response from health check query")

            row = result[0]
            if row.get("health_check") != 1:
                raise ValueError("Health check query returned unexpected result")

            response_time = time.time() - start_time

            # Get additional PostgreSQL-specific metrics
            details = await self._get_postgres_metrics()

            return HealthMetrics(
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                details={
                    "connection_status": "connected",
                    "server_start_time": str(row.get("start_time")),
                    **details,
                },
            )

        except (ConnectionError, TimeoutError, ValueError) as e:
            response_time = time.time() - start_time
            return HealthMetrics(
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                error_message=str(e),
                details={"connection_status": "failed"},
            )

    async def _get_postgres_metrics(self) -> Dict[str, Any]:
        """Get PostgreSQL-specific metrics."""
        try:
            metrics = {}

            # Connection count
            conn_result = await self.provider.execute_query("""
                SELECT count(*) as active_connections
                FROM pg_stat_activity
                WHERE state != 'idle'
            """)
            if conn_result:
                metrics["active_connections"] = conn_result[0]["active_connections"]

            # Database size
            size_result = await self.provider.execute_query("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size
            """)
            if size_result:
                metrics["database_size"] = size_result[0]["db_size"]

            # Long running queries
            long_queries = await self.provider.execute_query("""
                SELECT count(*) as long_running_queries
                FROM pg_stat_activity
                WHERE state != 'idle'
                AND query_start < now() - interval '30 seconds'
            """)
            if long_queries:
                metrics["long_running_queries"] = long_queries[0]["long_running_queries"]

            return metrics

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning("Failed to collect PostgreSQL metrics: %s", e)
            return {}


class Neo4jHealthMonitor(DatabaseHealthMonitor):
    """Health monitor for Neo4j database provider."""

    def __init__(self, neo4j_provider) -> None:
        super().__init__("neo4j")
        self.provider = neo4j_provider

    async def check_health(self) -> HealthMetrics:
        """Check Neo4j health."""
        start_time = time.time()

        try:
            # Perform basic connectivity test
            result = await self.provider.execute_query(
                "RETURN 1 as health_check, timestamp() as current_time"
            )

            if not result or len(result) == 0:
                raise ValueError("No response from health check query")

            record = result[0]
            if record.get("health_check") != 1:
                raise ValueError("Health check query returned unexpected result")

            response_time = time.time() - start_time

            # Get additional Neo4j-specific metrics
            details = await self._get_neo4j_metrics()

            return HealthMetrics(
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                details={
                    "connection_status": "connected",
                    "server_time": record.get("current_time"),
                    **details,
                },
            )

        except (ConnectionError, TimeoutError, ValueError) as e:
            response_time = time.time() - start_time
            return HealthMetrics(
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                error_message=str(e),
                details={"connection_status": "failed"},
            )

    async def _get_neo4j_metrics(self) -> Dict[str, Any]:
        """Get Neo4j-specific metrics."""
        try:
            metrics = {}

            # Node count
            node_result = await self.provider.execute_query(
                "MATCH (n) RETURN count(n) as node_count"
            )
            if node_result:
                metrics["node_count"] = node_result[0]["node_count"]

            # Relationship count
            rel_result = await self.provider.execute_query(
                "MATCH ()-[r]->() RETURN count(r) as relationship_count"
            )
            if rel_result:
                metrics["relationship_count"] = rel_result[0]["relationship_count"]

            # Database info
            db_result = await self.provider.execute_query(
                "CALL db.info() YIELD name, edition, version"
            )
            if db_result:
                info = db_result[0]
                metrics["database_name"] = info.get("name")
                metrics["edition"] = info.get("edition")
                metrics["version"] = info.get("version")

            return metrics

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning("Failed to collect Neo4j metrics: %s", e)
            return {}


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""

    interval_seconds: float = 30.0
    timeout_seconds: float = 10.0
    max_consecutive_failures: int = 3
    enable_alerts: bool = True


class HealthMonitorService:
    """Service for managing multiple health monitors."""

    def __init__(self, config: Optional[HealthCheckConfig] = None) -> None:
        self.config = config or HealthCheckConfig()
        self.monitors: Dict[str, DatabaseHealthMonitor] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_monitor(self, name: str, monitor: DatabaseHealthMonitor) -> None:
        """Add a health monitor."""
        self.monitors[name] = monitor
        logger.info("Added health monitor: %s", name)

    async def check_all_health(self) -> Dict[str, HealthMetrics]:
        """Check health of all monitors."""
        results = {}
        for name, monitor in self.monitors.items():
            try:
                metrics = await monitor.perform_health_check()
                results[name] = metrics
            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.exception("Health check failed for %s", name)
                results[name] = HealthMetrics(
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    timestamp=time.time(),
                    error_message=str(e),
                )
        return results

    async def get_health_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """Get health status for all or specific service."""
        if service_name:
            if service_name not in self.monitors:
                raise ValueError("Monitor '%s' not found" % service_name)

            monitor = self.monitors[service_name]
            metrics = monitor.get_last_health_check()
            if metrics is None:
                # Perform immediate check
                metrics = await monitor.perform_health_check()

            return {
                "service": service_name,
                "healthy": monitor.is_healthy(),
                "last_check": metrics.to_dict() if metrics else None,
            }
        else:
            # Check all services
            all_results = await self.check_all_health()
            overall_healthy = all(
                metrics.status == HealthStatus.HEALTHY for metrics in all_results.values()
            )

            return {
                "overall_healthy": overall_healthy,
                "services": {
                    name: {
                        "healthy": metrics.status == HealthStatus.HEALTHY,
                        "status": metrics.status.value,
                        "response_time": metrics.response_time,
                        "last_check": metrics.timestamp,
                        "details": metrics.details,
                        "error_message": metrics.error_message,
                    }
                    for name, metrics in all_results.items()
                },
            }

    async def start_monitoring(self) -> None:
        """Start periodic health monitoring."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop periodic health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Health monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self.check_all_health()
                await asyncio.sleep(self.config.interval_seconds)
            except asyncio.CancelledError:
                break
            except (ConnectionError, TimeoutError, ValueError):
                logger.exception("Monitoring loop error")
                await asyncio.sleep(self.config.interval_seconds)


# Global health monitor service instance
_health_service: Optional[HealthMonitorService] = None


async def get_health_service() -> HealthMonitorService:
    """Get the global health monitor service."""
    global _health_service
    if _health_service is None:
        _health_service = HealthMonitorService()
    return _health_service


async def initialize_health_service() -> None:
    """Initialize the global health service."""
    service = await get_health_service()

    # Import here to avoid circular imports
    from database.providers import get_postgres_provider, get_neo4j_provider

    # Add monitors for existing providers
    try:
        postgres_provider = await get_postgres_provider()
        postgres_monitor = PostgreSQLHealthMonitor(postgres_provider)
        service.add_monitor("postgres", postgres_monitor)
    except (ImportError, ConnectionError, ValueError) as e:
        logger.warning("Failed to initialize PostgreSQL health monitor: %s", e)

    try:
        neo4j_provider = await get_neo4j_provider()
        neo4j_monitor = Neo4jHealthMonitor(neo4j_provider)
        service.add_monitor("neo4j", neo4j_monitor)
    except (ImportError, ConnectionError, ValueError) as e:
        logger.warning("Failed to initialize Neo4j health monitor: %s", e)


# Utility functions for alerts and notifications


async def log_health_alert(service_name: str, status: HealthStatus, message: str) -> None:
    """Default alert callback that logs alerts."""
    if status == HealthStatus.UNHEALTHY:
        logger.error("🚨 HEALTH ALERT: %s - %s", service_name, message)
    elif status == HealthStatus.HEALTHY:
        logger.info("✅ HEALTH RECOVERY: %s - %s", service_name, message)
    else:
        logger.warning("⚠️  HEALTH WARNING: %s - %s", service_name, message)


async def collect_health_metrics(metrics: HealthMetrics) -> None:
    """Default health callback that collects metrics."""
    # This could integrate with monitoring systems like Prometheus
    logger.debug("Health metrics collected: %s", metrics.to_dict())


# Setup default callbacks
async def setup_default_callbacks() -> None:
    """Setup default health and alert callbacks."""
    service = await get_health_service()

    for monitor in service.monitors.values():
        monitor.add_health_callback(collect_health_metrics)
        monitor.add_alert_callback(log_health_alert)
