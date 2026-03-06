"""
Graceful Degradation Middleware for RuleIQ

Implements circuit breaker pattern, fallback responses, and
service health checks to ensure system resilience.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Set
from enum import Enum

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ServiceState(str, Enum):
    """Service operational state."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"
    READ_ONLY = "read_only"


class CircuitState(str, Enum):
    """Circuit breaker state."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for service protection.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self._half_open_calls = 0
        self._max_half_open_calls = 3

    def call(self, func: Callable) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            else:
                raise HTTPException(
                    status_code=503, detail=f"Service {self.name} is temporarily unavailable"
                )

        try:
            result = func()
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    async def async_call(self, func: Callable) -> Any:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            else:
                raise HTTPException(
                    status_code=503, detail=f"Service {self.name} is temporarily unavailable"
                )

        try:
            result = await func()
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if self.last_failure_time is None:
            return False

        now = datetime.now(timezone.utc)
        time_since_failure = (now - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self._max_half_open_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker {self.name} closed")
        else:
            self.failure_count = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker {self.name} opened after {self.failure_count} failures"
            )

        # Track metrics
        from monitoring.metrics import get_metrics_collector

        metrics = get_metrics_collector()
        metrics.track_request_metrics


class ServiceHealthChecker:
    """
    Monitors service health and manages degradation states.
    """

    def __init__(self) -> None:
        self.services: Dict[str, ServiceState] = {}
        self.health_checks: Dict[str, Callable] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.cached_responses: Dict[str, Dict[str, Any]] = {}
        self.read_only_mode = False
        self.degraded_features: Set[str] = set()

    def register_service(
        self, name: str, health_check: Callable, circuit_breaker: Optional[CircuitBreaker] = None
    ):
        """Register a service for health monitoring."""
        self.services[name] = ServiceState.HEALTHY
        self.health_checks[name] = health_check

        if circuit_breaker:
            self.circuit_breakers[name] = circuit_breaker
        else:
            self.circuit_breakers[name] = CircuitBreaker(name)

    async def check_health(self, service_name: str) -> bool:
        """Check health of a specific service."""
        if service_name not in self.health_checks:
            return True

        try:
            health_check = self.health_checks[service_name]
            if asyncio.iscoroutinefunction(health_check):
                result = await health_check()
            else:
                result = health_check()

            self.services[service_name] = ServiceState.HEALTHY if result else ServiceState.DEGRADED

            # Update metrics
            from monitoring.metrics import get_metrics_collector

            metrics = get_metrics_collector()
            metrics.update_service_availability(service_name, result)

            return result

        except Exception as e:
            logger.error(f"Health check failed for {service_name}: {e}")
            self.services[service_name] = ServiceState.CIRCUIT_OPEN

            # Update metrics
            from monitoring.metrics import get_metrics_collector

            metrics = get_metrics_collector()
            metrics.update_service_availability(service_name, False)

            return False

    async def check_all_services(self) -> Dict[str, bool]:
        """Check health of all registered services."""
        results = {}
        for service_name in self.services:
            results[service_name] = await self.check_health(service_name)
        return results

    def enable_read_only_mode(self):
        """Enable read-only mode for the application."""
        self.read_only_mode = True
        logger.warning("Read-only mode enabled")

    def disable_read_only_mode(self):
        """Disable read-only mode."""
        self.read_only_mode = False
        logger.info("Read-only mode disabled")

    def degrade_feature(self, feature_name: str):
        """Mark a feature as degraded."""
        self.degraded_features.add(feature_name)
        logger.warning(f"Feature {feature_name} degraded")

    def restore_feature(self, feature_name: str):
        """Restore a degraded feature."""
        self.degraded_features.discard(feature_name)
        logger.info(f"Feature {feature_name} restored")

    def cache_response(self, key: str, response: Dict[str, Any], ttl: int = 300):
        """Cache a response for fallback."""
        self.cached_responses[key] = {
            "data": response,
            "cached_at": datetime.now(timezone.utc),
            "ttl": ttl,
        }

    def get_cached_response(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        if key not in self.cached_responses:
            return None

        cached = self.cached_responses[key]
        age = (datetime.now(timezone.utc) - cached["cached_at"]).total_seconds()

        if age > cached["ttl"]:
            del self.cached_responses[key]
            return None

        return cached["data"]


class GracefulDegradationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling graceful degradation of services.
    """

    def __init__(self, app, health_checker: Optional[ServiceHealthChecker] = None) -> None:
        super().__init__(app)
        self.health_checker = health_checker or ServiceHealthChecker()
        self._initialize_health_checks()

    def _initialize_health_checks(self):
        """Initialize default health checks."""

        # Database health check
        async def check_database():
            try:
                from database.db_setup import get_async_db

                async for db in get_async_db():
                    await db.execute("SELECT 1")
                    return True
            except:
                return False

        # Redis health check
        async def check_redis():
            try:
                from config.cache import get_redis_client

                redis_client = await get_redis_client()
                await redis_client.ping()
                return True
            except:
                return False

        # Register services
        self.health_checker.register_service("database", check_database)
        self.health_checker.register_service("redis", check_redis)

    async def dispatch(self, request: Request, call_next):
        """Process request with degradation handling."""
        # Check if read-only mode
        if self.health_checker.read_only_mode and request.method not in ["GET", "HEAD", "OPTIONS"]:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service is in read-only mode",
                    "message": "Only read operations are currently available",
                },
            )

        # Check for degraded features
        feature = self._extract_feature_from_path(request.url.path)
        if feature in self.health_checker.degraded_features:
            # Try to return cached response
            cache_key = f"{request.method}:{request.url.path}"
            cached = self.health_checker.get_cached_response(cache_key)
            if cached:
                return JSONResponse(
                    status_code=200, content={**cached, "_cached": True, "_degraded": True}
                )
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": f"Feature {feature} is temporarily unavailable",
                        "message": "Please try again later",
                    },
                )

        # Process request with circuit breaker
        service = self._extract_service_from_path(request.url.path)
        if service in self.health_checker.circuit_breakers:
            breaker = self.health_checker.circuit_breakers[service]
            try:
                response = await breaker.async_call(lambda: call_next(request))

                # Cache successful responses for fallback
                if response.status_code == 200:
                    cache_key = f"{request.method}:{request.url.path}"
                    # Note: In production, you'd parse the response body
                    # self.health_checker.cache_response(cache_key, response_data)

                return response
            except HTTPException as e:
                # Return cached response if available
                cache_key = f"{request.method}:{request.url.path}"
                cached = self.health_checker.get_cached_response(cache_key)
                if cached:
                    return JSONResponse(
                        status_code=200, content={**cached, "_cached": True, "_fallback": True}
                    )
                raise e

        return await call_next(request)

    def _extract_feature_from_path(self, path: str) -> str:
        """Extract feature name from request path."""
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[1]  # e.g., /api/feature/endpoint -> feature
        return ""

    def _extract_service_from_path(self, path: str) -> str:
        """Extract service name from request path."""
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            # Map paths to services
            service_map = {
                "auth": "authentication",
                "users": "database",
                "ai": "ai_service",
                "compliance": "compliance_engine",
            }
            return service_map.get(parts[1], parts[1])
        return ""


# Feature flag automatic disabling
class FeatureFlagDegradation:
    """
    Automatically disable feature flags based on error rates.
    """

    def __init__(self) -> None:
        self.error_counts: Dict[str, int] = {}
        self.error_threshold = 10
        self.monitoring_window = 60  # seconds
        self.disabled_flags: Set[str] = set()

    def track_error(self, flag_name: str):
        """Track error for a feature flag."""
        if flag_name not in self.error_counts:
            self.error_counts[flag_name] = 0

        self.error_counts[flag_name] += 1

        if self.error_counts[flag_name] >= self.error_threshold:
            self.disable_flag(flag_name)

    def disable_flag(self, flag_name: str):
        """Automatically disable a feature flag."""
        self.disabled_flags.add(flag_name)
        logger.error(f"Feature flag {flag_name} automatically disabled due to errors")

        # Update feature flag system
        from config.feature_flags import feature_flags

        if hasattr(feature_flags, "disable_flag"):
            feature_flags.disable_flag(flag_name)

    def enable_flag(self, flag_name: str):
        """Re-enable a feature flag."""
        self.disabled_flags.discard(flag_name)
        self.error_counts[flag_name] = 0

        # Update feature flag system
        from config.feature_flags import feature_flags

        if hasattr(feature_flags, "enable_flag"):
            feature_flags.enable_flag(flag_name)

    def reset_error_count(self, flag_name: str):
        """Reset error count for a flag."""
        self.error_counts[flag_name] = 0

    async def monitor_loop(self):
        """Monitor and reset error counts periodically."""
        while True:
            await asyncio.sleep(self.monitoring_window)
            # Reset error counts for non-disabled flags
            for flag_name in list(self.error_counts.keys()):
                if flag_name not in self.disabled_flags:
                    self.error_counts[flag_name] = 0


# Global instances
_health_checker: Optional[ServiceHealthChecker] = None
_flag_degradation: Optional[FeatureFlagDegradation] = None


def get_health_checker() -> ServiceHealthChecker:
    """Get or create the global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = ServiceHealthChecker()
    return _health_checker


def get_flag_degradation() -> FeatureFlagDegradation:
    """Get or create the global flag degradation manager."""
    global _flag_degradation
    if _flag_degradation is None:
        _flag_degradation = FeatureFlagDegradation()
    return _flag_degradation
