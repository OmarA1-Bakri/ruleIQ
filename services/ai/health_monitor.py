"""

# Constants
HTTP_OK = 200

DEFAULT_LIMIT = 100


Service Health Monitoring for AI Services

Provides comprehensive health monitoring, service discovery, and
automated failover capabilities for AI services with detailed
health metrics and recovery procedures.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import aiohttp
from config.ai_config import ModelType, ai_config


class ServiceStatus(Enum):
    """Service health status levels"""


class HealthCheckType(Enum):
    """Types of health checks"""


@dataclass
class HealthMetrics:
    """Health metrics for a service"""

    status: ServiceStatus = ServiceStatus.UNKNOWN
    response_time: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    uptime: float = 0.0
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    recent_errors: List[str] = field(default_factory=list)
    error_patterns: Dict[str, int] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Configuration for a health check"""

    name: str
    check_type: HealthCheckType
    endpoint: Optional[str] = None
    test_function: Optional[Callable] = None
    interval: int = 30
    timeout: int = 10
    retries: int = 2
    success_threshold: int = 2
    failure_threshold: int = 3


class ServiceHealthMonitor:
    """
    Comprehensive health monitoring for AI services
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.services: Dict[str, HealthMetrics] = {}
        self.health_checks: Dict[str, HealthCheck] = {}
        self.is_monitoring = False
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.health_history: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history_size = 1000
        self._initialize_default_checks()

    def _initialize_default_checks(self) -> None:
        """Initialize default health checks for AI services"""
        self.add_health_check(
            HealthCheck(
                name="google_ai_api",
                check_type=HealthCheckType.FUNCTIONAL,
                test_function=self._check_google_ai_health,
                interval=60,
                timeout=15,
                failure_threshold=3,
            )
        )
        for model_type in ModelType:
            self.add_health_check(
                HealthCheck(
                    name=f"model_{model_type.name.lower()}",
                    check_type=HealthCheckType.FUNCTIONAL,
                    test_function=lambda mt=model_type: self._check_model_health(mt),
                    interval=120,
                    timeout=30,
                    failure_threshold=2,
                )
            )
        self.add_health_check(
            HealthCheck(
                name="circuit_breaker",
                check_type=HealthCheckType.FUNCTIONAL,
                test_function=self._check_circuit_breaker_health,
                interval=30,
                timeout=5,
                failure_threshold=1,
            )
        )

    def add_health_check(self, health_check: HealthCheck) -> None:
        """Add a new health check"""
        self.health_checks[health_check.name] = health_check
        self.services[health_check.name] = HealthMetrics()
        self.health_history[health_check.name] = []
        self.logger.info("Added health check: %s" % health_check.name)

    def remove_health_check(self, service_name: str) -> None:
        """Remove a health check"""
        if service_name in self.health_checks:
            del self.health_checks[service_name]
            del self.services[service_name]
            del self.health_history[service_name]
            if service_name in self.monitoring_tasks:
                self.monitoring_tasks[service_name].cancel()
                del self.monitoring_tasks[service_name]
            self.logger.info("Removed health check: %s" % service_name)

    async def start_monitoring(self) -> None:
        """Start health monitoring for all services"""
        if self.is_monitoring:
            self.logger.warning("Health monitoring is already running")
            return
        self.is_monitoring = True
        for service_name, health_check in self.health_checks.items():
            task = asyncio.create_task(self._monitoring_loop(service_name, health_check))
            self.monitoring_tasks[service_name] = task
        self.logger.info("Started health monitoring for %s services" % len(self.health_checks))

    async def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        self.is_monitoring = False
        for task in self.monitoring_tasks.values():
            task.cancel()
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        self.monitoring_tasks.clear()
        self.logger.info("Stopped health monitoring")

    async def _monitoring_loop(self, service_name: str, health_check: HealthCheck) -> None:
        """Main monitoring loop for a service"""
        try:
            while self.is_monitoring:
                await self._perform_health_check(service_name, health_check)
                await asyncio.sleep(health_check.interval)
        except asyncio.CancelledError:
            self.logger.info("Health monitoring stopped for %s" % service_name)
        except Exception as e:
            self.logger.error("Error in health monitoring loop for %s: %s" % (service_name, e))

    async def _perform_health_check(self, service_name: str, health_check: HealthCheck) -> None:
        """Perform a single health check"""
        self.services[service_name]
        start_time = time.time()
        try:
            if health_check.test_function:
                result = await health_check.test_function()
            elif health_check.endpoint:
                result = await self._check_endpoint_health(
                    health_check.endpoint, health_check.timeout
                )
            else:
                result = {"healthy": False, "error": "No test function or endpoint configured"}
            response_time = (time.time() - start_time) * 1000
            await self._update_health_metrics(service_name, result, response_time)
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.error("Health check failed for %s: %s" % (service_name, e))
            await self._update_health_metrics(
                service_name, {"healthy": False, "error": str(e)}, response_time
            )

    async def _update_health_metrics(
        self, service_name: str, result: Dict[str, Any], response_time: float
    ) -> None:
        """Update health metrics for a service"""
        metrics = self.services[service_name]
        health_check = self.health_checks[service_name]
        metrics.last_check = datetime.now()
        metrics.response_time = response_time
        is_healthy = result.get("healthy", False)
        if is_healthy:
            metrics.consecutive_successes += 1
            metrics.consecutive_failures = 0
            if metrics.consecutive_successes >= health_check.success_threshold:
                if metrics.status in [ServiceStatus.UNHEALTHY, ServiceStatus.DEGRADED]:
                    self.logger.info("Service %s recovered - marking as healthy" % service_name)
                metrics.status = ServiceStatus.HEALTHY
        else:
            metrics.consecutive_failures += 1
            metrics.consecutive_successes = 0
            error_msg = result.get("error", "Unknown error")
            metrics.recent_errors.append(error_msg)
            if len(metrics.recent_errors) > 10:
                metrics.recent_errors = metrics.recent_errors[-10:]
            error_type = type(result.get("exception", Exception())).__name__
            metrics.error_patterns[error_type] = metrics.error_patterns.get(error_type, 0) + 1
            if metrics.consecutive_failures >= health_check.failure_threshold:
                if metrics.status != ServiceStatus.UNHEALTHY:
                    self.logger.warning(
                        "Service %s is unhealthy - %s consecutive failures"
                        % (service_name, metrics.consecutive_failures)
                    )
                metrics.status = ServiceStatus.UNHEALTHY
            elif metrics.consecutive_failures > 1:
                metrics.status = ServiceStatus.DEGRADED
        await self._update_performance_metrics(service_name, response_time, is_healthy)
        self._store_health_history(service_name, metrics, result)

    async def _update_performance_metrics(
        self, service_name: str, response_time: float, success: bool
    ) -> None:
        """Update performance metrics"""
        metrics = self.services[service_name]
        history = self.health_history[service_name]
        recent_checks = history[-50:] if len(history) >= 50 else history
        if recent_checks:
            successful_checks = sum(1 for check in recent_checks if check.get("success", False))
            metrics.success_rate = successful_checks / len(recent_checks) * 100
            metrics.error_rate = 100 - metrics.success_rate
            response_times = [check.get("response_time", 0) for check in recent_checks]
            if response_times:
                metrics.avg_response_time = sum(response_times) / len(response_times)
                sorted_times = sorted(response_times)
                p95_index = int(len(sorted_times) * 0.95)
                p99_index = int(len(sorted_times) * 0.99)
                metrics.p95_response_time = (
                    sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
                )
                metrics.p99_response_time = (
                    sorted_times[p99_index] if p99_index < len(sorted_times) else sorted_times[-1]
                )

    def _store_health_history(
        self, service_name: str, metrics: HealthMetrics, result: Dict[str, Any]
    ) -> None:
        """Store health check result in history"""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "status": metrics.status.value,
            "response_time": metrics.response_time,
            "success": result.get("healthy", False),
            "error": result.get("error"),
            "consecutive_failures": metrics.consecutive_failures,
            "consecutive_successes": metrics.consecutive_successes,
        }
        self.health_history[service_name].append(history_entry)
        if len(self.health_history[service_name]) > self.max_history_size:
            self.health_history[service_name] = self.health_history[service_name][
                -self.max_history_size :
            ]

    async def _check_endpoint_health(self, endpoint: str, timeout: int) -> Dict[str, Any]:
        """Check health of an HTTP endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == HTTP_OK:
                        return {"healthy": True, "status_code": response.status}
                    else:
                        return {
                            "healthy": False,
                            "error": f"HTTP {response.status}",
                            "status_code": response.status,
                        }
        except Exception as e:
            return {"healthy": False, "error": str(e), "exception": e}

    async def _check_google_ai_health(self) -> Dict[str, Any]:
        """Check Google AI API health"""
        try:
            client = ai_config._get_genai_client()
            models = list(client.models.list())
            if models:
                return {"healthy": True, "models_available": len(models)}
            else:
                return {"healthy": False, "error": "No models available"}
        except Exception as e:
            return {"healthy": False, "error": str(e), "exception": e}

    async def _check_model_health(self, model_type: ModelType) -> Dict[str, Any]:
        """Check health of a specific AI model"""
        try:
            model = ai_config.get_model(model_type)
            test_prompt = "Hello, this is a health check. Please respond with 'OK'."
            response = model.generate_content(test_prompt)
            if response and response.text:
                return {
                    "healthy": True,
                    "model": model_type.value,
                    "response_length": len(response.text),
                }
            else:
                return {
                    "healthy": False,
                    "error": "No response generated",
                    "model": model_type.value,
                }
        except Exception as e:
            return {"healthy": False, "error": str(e), "model": model_type.value, "exception": e}

    async def _check_circuit_breaker_health(self) -> Dict[str, Any]:
        """Check circuit breaker health"""
        try:
            from services.ai.circuit_breaker import get_circuit_breaker

            circuit_breaker = get_circuit_breaker()
            health_status = circuit_breaker.get_health_status()
            is_healthy = health_status["overall_state"] != "open"
            return {
                "healthy": is_healthy,
                "overall_state": health_status["overall_state"],
                "total_requests": health_status["metrics"]["total_requests"],
                "failure_rate": health_status["metrics"]["failure_rate"],
            }
        except Exception as e:
            return {"healthy": False, "error": str(e), "exception": e}

    def get_service_health(self, service_name: str) -> Optional[HealthMetrics]:
        """Get health metrics for a specific service"""
        return self.services.get(service_name)

    def get_all_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status for all services"""
        overall_status = ServiceStatus.HEALTHY
        unhealthy_services = []
        degraded_services = []
        service_statuses = {}
        for service_name, metrics in self.services.items():
            service_statuses[service_name] = {
                "status": metrics.status.value,
                "response_time": metrics.response_time,
                "success_rate": metrics.success_rate,
                "consecutive_failures": metrics.consecutive_failures,
                "last_check": metrics.last_check.isoformat() if metrics.last_check else None,
            }
            if metrics.status == ServiceStatus.UNHEALTHY:
                unhealthy_services.append(service_name)
                overall_status = ServiceStatus.UNHEALTHY
            elif metrics.status == ServiceStatus.DEGRADED:
                degraded_services.append(service_name)
                if overall_status == ServiceStatus.HEALTHY:
                    overall_status = ServiceStatus.DEGRADED
        return {
            "overall_status": overall_status.value,
            "services": service_statuses,
            "summary": {
                "total_services": len(self.services),
                "healthy_services": len(
                    [s for s in self.services.values() if s.status == ServiceStatus.HEALTHY]
                ),
                "degraded_services": len(degraded_services),
                "unhealthy_services": len(unhealthy_services),
            },
            "issues": {
                "unhealthy_services": unhealthy_services,
                "degraded_services": degraded_services,
            },
            "last_updated": datetime.now().isoformat(),
        }

    def get_service_history(self, service_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health history for a service"""
        if service_name not in self.health_history:
            return []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            entry
            for entry in self.health_history[service_name]
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
        ]

    def get_health_trends(self) -> Dict[str, Any]:
        """Get health trends and patterns"""
        trends = {}
        for service_name, metrics in self.services.items():
            history = self.health_history[service_name]
            recent_history = history[-100:] if len(history) >= DEFAULT_LIMIT else history
            if len(recent_history) >= 10:
                first_half = recent_history[: len(recent_history) // 2]
                second_half = recent_history[len(recent_history) // 2 :]
                first_half_success = sum(1 for h in first_half if h.get("success", False)) / len(
                    first_half
                )
                second_half_success = sum(1 for h in second_half if h.get("success", False)) / len(
                    second_half
                )
                trend_direction = (
                    "improving"
                    if second_half_success > first_half_success
                    else "declining"
                    if second_half_success < first_half_success
                    else "stable"
                )
                trends[service_name] = {
                    "trend_direction": trend_direction,
                    "success_rate_change": (second_half_success - first_half_success) * 100,
                    "current_success_rate": metrics.success_rate,
                    "avg_response_time": metrics.avg_response_time,
                }
        return trends

    async def perform_manual_check(self, service_name: str) -> Dict[str, Any]:
        """Perform a manual health check for a specific service"""
        if service_name not in self.health_checks:
            return {"error": f"Service {service_name} not found"}
        health_check = self.health_checks[service_name]
        await self._perform_health_check(service_name, health_check)
        metrics = self.services[service_name]
        return {
            "service": service_name,
            "status": metrics.status.value,
            "response_time": metrics.response_time,
            "last_check": metrics.last_check.isoformat() if metrics.last_check else None,
            "consecutive_failures": metrics.consecutive_failures,
            "consecutive_successes": metrics.consecutive_successes,
        }


_health_monitor: Optional[ServiceHealthMonitor] = None


def get_health_monitor() -> ServiceHealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = ServiceHealthMonitor()
    return _health_monitor


def reset_health_monitor() -> None:
    """Reset global health monitor (for testing)"""
    global _health_monitor
    _health_monitor = None
