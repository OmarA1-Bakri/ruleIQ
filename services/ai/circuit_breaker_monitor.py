"""

# Constants
HTTP_OK = 200

DEFAULT_LIMIT = 100


Circuit Breaker Monitoring and Alerting System

Provides comprehensive monitoring, alerting, and dashboard capabilities
for AI circuit breaker health and performance metrics.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from services.ai.circuit_breaker import AICircuitBreaker


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Circuit breaker alert"""

    id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    message: str
    model_name: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class MonitoringConfig:
    """Configuration for circuit breaker monitoring"""

    failure_rate_warning_threshold: float = 0.1
    failure_rate_error_threshold: float = 0.25
    consecutive_failures_threshold: int = 3
    health_check_interval: int = 30
    metrics_collection_interval: int = 60
    alert_cooldown_period: int = 300
    enable_logging: bool = True
    enable_webhook: bool = False
    webhook_url: Optional[str] = None


class CircuitBreakerMonitor:
    """
    Comprehensive monitoring system for AI circuit breakers
    """

    def __init__(
        self, circuit_breaker: AICircuitBreaker, config: Optional[MonitoringConfig] = None
    ) -> None:
        self.circuit_breaker = circuit_breaker
        self.config = config or MonitoringConfig()
        self.logger = logging.getLogger(__name__)
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self.last_alert_times: Dict[str, datetime] = {}
        self.metrics_history: List[Dict[str, Any]] = []
        self.performance_trends: Dict[str, List[float]] = {}
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None

    async def start_monitoring(self) -> None:
        """Start continuous monitoring"""
        if self.is_monitoring:
            self.logger.warning("Monitoring is already running")
            return
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Circuit breaker monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring"""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitoring_task
        self.logger.info("Circuit breaker monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        try:
            while self.is_monitoring:
                await self._collect_metrics()
                await self._check_health()
                await self._evaluate_alerts()
                await asyncio.sleep(self.config.health_check_interval)
        except asyncio.CancelledError:
            self.logger.info("Monitoring loop cancelled")
        except Exception as e:
            self.logger.error("Error in monitoring loop: %s" % e)

    async def _collect_metrics(self) -> None:
        """Collect current metrics from circuit breaker"""
        try:
            health_status = self.circuit_breaker.get_health_status()
            metrics = {
                "timestamp": datetime.now(),
                "health_status": health_status,
                "overall_state": health_status["overall_state"],
                "failure_rate": health_status["metrics"]["failure_rate"],
                "total_requests": health_status["metrics"]["total_requests"],
                "failed_requests": health_status["metrics"]["failed_requests"],
                "circuit_trips": health_status["metrics"]["circuit_trips"],
            }
            self.metrics_history.append(metrics)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.metrics_history = [m for m in self.metrics_history if m["timestamp"] > cutoff_time]
            self._update_performance_trends(metrics)
        except Exception as e:
            self.logger.error("Error collecting metrics: %s" % e)

    def _update_performance_trends(self, metrics: Dict[str, Any]) -> None:
        """Update performance trend analysis"""
        metrics["timestamp"]
        if "failure_rate" not in self.performance_trends:
            self.performance_trends["failure_rate"] = []
        self.performance_trends["failure_rate"].append(metrics["failure_rate"])
        if len(self.performance_trends["failure_rate"]) > DEFAULT_LIMIT:
            self.performance_trends["failure_rate"] = self.performance_trends["failure_rate"][-100:]

    async def _check_health(self) -> None:
        """Perform health checks and generate alerts if needed"""
        try:
            health_status = self.circuit_breaker.get_health_status()
            failure_rate = health_status["metrics"]["failure_rate"]
            if failure_rate >= self.config.failure_rate_error_threshold:
                await self._create_alert(
                    severity=AlertSeverity.ERROR,
                    title="High Failure Rate Detected",
                    message=f"AI service failure rate is {failure_rate:.1%}, exceeding error threshold of {self.config.failure_rate_error_threshold:.1%}",
                    context={"failure_rate": failure_rate},
                )
            elif failure_rate >= self.config.failure_rate_warning_threshold:
                await self._create_alert(
                    severity=AlertSeverity.WARNING,
                    title="Elevated Failure Rate",
                    message=f"AI service failure rate is {failure_rate:.1%}, exceeding warning threshold of {self.config.failure_rate_warning_threshold:.1%}",
                    context={"failure_rate": failure_rate},
                )
            for model_name, model_info in health_status["models"].items():
                if not model_info["available"]:
                    await self._create_alert(
                        severity=AlertSeverity.CRITICAL,
                        title=f"Model Unavailable: {model_name}",
                        message=f"AI model {model_name} is unavailable due to circuit breaker trip",
                        model_name=model_name,
                        context=model_info,
                    )
                elif model_info["failure_count"] >= self.config.consecutive_failures_threshold:
                    await self._create_alert(
                        severity=AlertSeverity.WARNING,
                        title=f"Model Degraded: {model_name}",
                        message=f"AI model {model_name} has {model_info['failure_count']} recent failures",
                        model_name=model_name,
                        context=model_info,
                    )
        except Exception as e:
            self.logger.error("Error during health check: %s" % e)

    async def _evaluate_alerts(self) -> None:
        """Evaluate and process pending alerts"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.alerts = [
            alert for alert in self.alerts if not alert.resolved or alert.timestamp > cutoff_time
        ]
        resolved_alerts = [alert for alert in self.alerts if alert.resolved]
        self.alert_history.extend(resolved_alerts)
        self.alerts = [alert for alert in self.alerts if not alert.resolved]

    async def _create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        model_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create and process a new alert"""
        alert_key = f"{title}_{model_name or 'global'}"
        if alert_key in self.last_alert_times:
            last_time = self.last_alert_times[alert_key]
            if (datetime.now() - last_time).total_seconds() < self.config.alert_cooldown_period:
                return
        alert = Alert(
            id=f"cb_{int(datetime.now().timestamp())}_{alert_key}",
            timestamp=datetime.now(),
            severity=severity,
            title=title,
            message=message,
            model_name=model_name,
            context=context or {},
        )
        self.alerts.append(alert)
        self.last_alert_times[alert_key] = alert.timestamp
        await self._send_alert(alert)

    async def _send_alert(self, alert: Alert) -> None:
        """Send alert through configured channels"""
        try:
            if self.config.enable_logging:
                log_level = {
                    AlertSeverity.INFO: logging.INFO,
                    AlertSeverity.WARNING: logging.WARNING,
                    AlertSeverity.ERROR: logging.ERROR,
                    AlertSeverity.CRITICAL: logging.CRITICAL,
                }.get(alert.severity, logging.INFO)
                self.logger.log(
                    log_level,
                    "CIRCUIT BREAKER ALERT [%s]: %s - %s"
                    % (alert.severity.value.upper(), alert.title, alert.message),
                    extra={
                        "alert_id": alert.id,
                        "model_name": alert.model_name,
                        "context": alert.context,
                    },
                )
            if self.config.enable_webhook and self.config.webhook_url:
                await self._send_webhook_alert(alert)
        except Exception as e:
            self.logger.error("Error sending alert: %s" % e)

    async def _send_webhook_alert(self, alert: Alert) -> None:
        """Send alert via webhook"""
        import aiohttp

        payload = {
            "alert_id": alert.id,
            "timestamp": alert.timestamp.isoformat(),
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "model_name": alert.model_name,
            "context": alert.context,
        }
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.config.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response,
            ):
                if response.status == HTTP_OK:
                    self.logger.debug("Webhook alert sent successfully for %s" % alert.id)
                else:
                    self.logger.warning("Webhook alert failed with status %s" % response.status)
        except Exception as e:
            self.logger.error("Error sending webhook alert: %s" % e)

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get list of active alerts, optionally filtered by severity"""
        alerts = [alert for alert in self.alerts if not alert.resolved]
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self.logger.info("Alert %s acknowledged" % alert_id)
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                self.logger.info("Alert %s resolved" % alert_id)
                return True
        return False

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        health_status = self.circuit_breaker.get_health_status()
        recent_metrics = self.metrics_history[-10:] if self.metrics_history else []
        failure_rate_trend = "stable"
        if len(recent_metrics) >= 2:
            recent_rate = recent_metrics[-1]["failure_rate"]
            previous_rate = recent_metrics[-2]["failure_rate"]
            if recent_rate > previous_rate * 1.1:
                failure_rate_trend = "increasing"
            elif recent_rate < previous_rate * 0.9:
                failure_rate_trend = "decreasing"
        return {
            "circuit_breaker_health": health_status,
            "active_alerts": len(self.get_active_alerts()),
            "critical_alerts": len(self.get_active_alerts(AlertSeverity.CRITICAL)),
            "metrics_summary": {
                "total_requests_24h": sum(m["total_requests"] for m in recent_metrics[-24:]),
                "failure_rate_trend": failure_rate_trend,
                "average_failure_rate": sum(m["failure_rate"] for m in recent_metrics)
                / len(recent_metrics)
                if recent_metrics
                else 0,
            },
            "model_availability": {
                model: info["available"] for model, info in health_status["models"].items()
            },
            "performance_trends": self.performance_trends,
            "last_updated": datetime.now().isoformat(),
        }


_monitor_instance: Optional[CircuitBreakerMonitor] = None


def get_circuit_breaker_monitor(circuit_breaker: AICircuitBreaker) -> CircuitBreakerMonitor:
    """Get global circuit breaker monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = CircuitBreakerMonitor(circuit_breaker)
    return _monitor_instance


def reset_monitor() -> None:
    """Reset global monitor (for testing)"""
    global _monitor_instance
    _monitor_instance = None
