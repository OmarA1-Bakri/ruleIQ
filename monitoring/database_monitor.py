"""Database Connection Pool Monitoring Service

Provides comprehensive monitoring for database connection pools including:
- Real-time pool metrics
- Connection health checks
- Performance tracking
- Alert threshold monitoring
- Prometheus-compatible metrics export
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from sqlalchemy import text

from database.db_setup import get_engine_info, _ENGINE, _ASYNC_ENGINE


logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Database pool metrics snapshot."""

    timestamp: datetime
    pool_type: str  # 'sync' or 'async'
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    total_connections: int
    utilization_percent: float
    overflow_percent: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class ConnectionHealthCheck:
    """Database connection health check result."""

    timestamp: datetime
    pool_type: str
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class AlertThresholds:
    """Alert thresholds for database monitoring."""

    pool_utilization_warning: float = 70.0  # %
    pool_utilization_critical: float = 85.0  # %
    overflow_warning: float = 50.0  # %
    overflow_critical: float = 80.0  # %
    connection_timeout_warning: float = 1000.0  # ms
    connection_timeout_critical: float = 2000.0  # ms
    failed_connections_threshold: int = 5  # consecutive failures


class DatabaseMonitor:
    """Database connection pool monitoring service."""

    def __init__(self, alert_thresholds: Optional[AlertThresholds] = None) -> None:
        self.alert_thresholds = alert_thresholds or AlertThresholds()
        self.metrics_history: List[PoolMetrics] = []
        self.health_history: List[ConnectionHealthCheck] = []
        self.max_history_size = 1000  # Keep last 1000 entries
        self.consecutive_failures = {"sync": 0, "async": 0}

    def get_pool_metrics(self) -> Dict[str, PoolMetrics]:
        """Get current pool metrics for both sync and async pools."""
        metrics = {}
        engine_info = get_engine_info()
        timestamp = datetime.now(timezone.utc)

        # Sync pool metrics
        if engine_info.get("sync_engine_initialized") and _ENGINE:
            pool_size = engine_info.get("sync_pool_size", 0)
            checked_out = engine_info.get("sync_pool_checked_out", 0)
            overflow = engine_info.get("sync_pool_overflow", 0)
            total_connections = checked_out + overflow

            metrics["sync"] = PoolMetrics(
                timestamp=timestamp,
                pool_type="sync",
                pool_size=pool_size,
                checked_in=engine_info.get("sync_pool_checked_in", 0),
                checked_out=checked_out,
                overflow=overflow,
                total_connections=total_connections,
                utilization_percent=((checked_out / pool_size * 100) if pool_size > 0 else 0),
                overflow_percent=(overflow / pool_size * 100) if pool_size > 0 else 0,
            )

        # Async pool metrics
        if engine_info.get("async_engine_initialized") and _ASYNC_ENGINE:
            pool_size = engine_info.get("async_pool_size", 0)
            checked_out = engine_info.get("async_pool_checked_out", 0)
            overflow = engine_info.get("async_pool_overflow", 0)
            total_connections = checked_out + overflow

            metrics["async"] = PoolMetrics(
                timestamp=timestamp,
                pool_type="async",
                pool_size=pool_size,
                checked_in=engine_info.get("async_pool_checked_in", 0),
                checked_out=checked_out,
                overflow=overflow,
                total_connections=total_connections,
                utilization_percent=((checked_out / pool_size * 100) if pool_size > 0 else 0),
                overflow_percent=(overflow / pool_size * 100) if pool_size > 0 else 0,
            )

        # Store metrics in history
        for metric in metrics.values():
            self.metrics_history.append(metric)

        # Trim history if needed
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size :]

        return metrics

    def check_connection_health(self) -> Dict[str, ConnectionHealthCheck]:
        """Perform health checks on database connections."""
        results = {}
        timestamp = datetime.now(timezone.utc)

        # Sync connection health check
        if _ENGINE:
            try:
                start_time = time.time()
                with _ENGINE.connect() as conn:
                    conn.execute(text("SELECT 1"))
                response_time = (time.time() - start_time) * 1000  # Convert to ms

                results["sync"] = ConnectionHealthCheck(
                    timestamp=timestamp,
                    pool_type="sync",
                    success=True,
                    response_time_ms=response_time,
                )
                self.consecutive_failures["sync"] = 0

            except Exception as e:
                results["sync"] = ConnectionHealthCheck(
                    timestamp=timestamp,
                    pool_type="sync",
                    success=False,
                    response_time_ms=0.0,
                    error_message=str(e),
                )
                self.consecutive_failures["sync"] += 1
                logger.error(f"Sync database health check failed: {e}")

        # Store health check results
        for result in results.values():
            self.health_history.append(result)

        # Trim history if needed
        if len(self.health_history) > self.max_history_size:
            self.health_history = self.health_history[-self.max_history_size :]

        return results

    async def check_async_connection_health(self) -> Optional[ConnectionHealthCheck]:
        """Perform async health check on database connection."""
        if not _ASYNC_ENGINE:
            return None

        timestamp = datetime.now(timezone.utc)
        try:
            start_time = time.time()
            async with _ASYNC_ENGINE.connect() as conn:
                await conn.execute(text("SELECT 1"))
            response_time = (time.time() - start_time) * 1000  # Convert to ms

            result = ConnectionHealthCheck(
                timestamp=timestamp,
                pool_type="async",
                success=True,
                response_time_ms=response_time,
            )
            self.consecutive_failures["async"] = 0

        except Exception as e:
            result = ConnectionHealthCheck(
                timestamp=timestamp,
                pool_type="async",
                success=False,
                response_time_ms=0.0,
                error_message=str(e),
            )
            self.consecutive_failures["async"] += 1
            logger.error(f"Async database health check failed: {e}")

        self.health_history.append(result)

        # Trim history if needed
        if len(self.health_history) > self.max_history_size:
            self.health_history = self.health_history[-self.max_history_size :]

        return result

    def check_alerts(self, metrics: Dict[str, PoolMetrics]) -> List[Dict[str, Any]]:
        """Check for alert conditions based on current metrics."""
        alerts = []

        for pool_type, metric in metrics.items():
            # Pool utilization alerts
            if metric.utilization_percent >= self.alert_thresholds.pool_utilization_critical:
                alerts.append(
                    {
                        "severity": "critical",
                        "pool_type": pool_type,
                        "alert_type": "pool_utilization",
                        "message": f"{pool_type.title()} pool utilization critical: {metric.utilization_percent:.1f}%",
                        "value": metric.utilization_percent,
                        "threshold": self.alert_thresholds.pool_utilization_critical,
                        "timestamp": metric.timestamp.isoformat(),
                    }
                )
            elif metric.utilization_percent >= self.alert_thresholds.pool_utilization_warning:
                alerts.append(
                    {
                        "severity": "warning",
                        "pool_type": pool_type,
                        "alert_type": "pool_utilization",
                        "message": f"{pool_type.title()} pool utilization warning: {metric.utilization_percent:.1f}%",
                        "value": metric.utilization_percent,
                        "threshold": self.alert_thresholds.pool_utilization_warning,
                        "timestamp": metric.timestamp.isoformat(),
                    }
                )

            # Overflow alerts
            if metric.overflow_percent >= self.alert_thresholds.overflow_critical:
                alerts.append(
                    {
                        "severity": "critical",
                        "pool_type": pool_type,
                        "alert_type": "overflow",
                        "message": f"{pool_type.title()} pool overflow critical: {metric.overflow_percent:.1f}%",
                        "value": metric.overflow_percent,
                        "threshold": self.alert_thresholds.overflow_critical,
                        "timestamp": metric.timestamp.isoformat(),
                    }
                )
            elif metric.overflow_percent >= self.alert_thresholds.overflow_warning:
                alerts.append(
                    {
                        "severity": "warning",
                        "pool_type": pool_type,
                        "alert_type": "overflow",
                        "message": f"{pool_type.title()} pool overflow warning: {metric.overflow_percent:.1f}%",
                        "value": metric.overflow_percent,
                        "threshold": self.alert_thresholds.overflow_warning,
                        "timestamp": metric.timestamp.isoformat(),
                    }
                )

        # Connection failure alerts
        for pool_type, failures in self.consecutive_failures.items():
            if failures >= self.alert_thresholds.failed_connections_threshold:
                alerts.append(
                    {
                        "severity": "critical",
                        "pool_type": pool_type,
                        "alert_type": "connection_failures",
                        "message": f"{pool_type.title()} pool has {failures} consecutive connection failures",
                        "value": failures,
                        "threshold": self.alert_thresholds.failed_connections_threshold,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        return alerts

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary."""
        metrics = self.get_pool_metrics()
        health_checks = self.check_connection_health()
        alerts = self.check_alerts(metrics)

        # Calculate recent averages (last 10 minutes)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= recent_cutoff]

        recent_averages = {}
        if recent_metrics:
            for pool_type in ["sync", "async"]:
                pool_metrics = [m for m in recent_metrics if m.pool_type == pool_type]
                if pool_metrics:
                    recent_averages[f"{pool_type}_avg_utilization"] = sum(
                        m.utilization_percent for m in pool_metrics
                    ) / len(pool_metrics)
                    recent_averages[f"{pool_type}_avg_overflow"] = sum(
                        m.overflow_percent for m in pool_metrics
                    ) / len(pool_metrics)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_metrics": {k: v.to_dict() for k, v in metrics.items()},
            "health_checks": {k: v.to_dict() for k, v in health_checks.items()},
            "alerts": alerts,
            "recent_averages": recent_averages,
            "alert_thresholds": asdict(self.alert_thresholds),
            "history_size": {
                "metrics": len(self.metrics_history),
                "health_checks": len(self.health_history),
            },
        }

    async def start_monitoring_loop(self, interval_seconds: int = 30) -> None:
        """Start continuous monitoring loop."""
        logger.info(f"Starting database monitoring loop with {interval_seconds}s interval")

        while True:
            try:
                # Get metrics and perform health checks
                metrics = self.get_pool_metrics()
                await self.check_async_connection_health()
                alerts = self.check_alerts(metrics)

                # Log alerts
                for alert in alerts:
                    if alert["severity"] == "critical":
                        logger.critical(alert["message"])
                    else:
                        logger.warning(alert["message"])

                # Log summary every 5 minutes (10 cycles at 30s interval)
                if len(self.metrics_history) % 10 == 0:
                    self.get_monitoring_summary()
                    logger.info(f"Database monitoring summary: {len(alerts)} active alerts")

                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Database monitoring loop error: {e}")
                await asyncio.sleep(interval_seconds)


# Global monitor instance
_monitor: Optional[DatabaseMonitor] = None


def get_database_monitor() -> DatabaseMonitor:
    """Get or create global database monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = DatabaseMonitor()
    return _monitor


async def start_database_monitoring(interval_seconds: int = 30) -> None:
    """Start database monitoring service."""
    monitor = get_database_monitor()
    await monitor.start_monitoring_loop(interval_seconds)


def get_database_health_status() -> Dict[str, Any]:
    """Get current database health status for API endpoints."""
    monitor = get_database_monitor()
    return monitor.get_monitoring_summary()
