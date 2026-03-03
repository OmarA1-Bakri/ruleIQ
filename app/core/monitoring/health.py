"""
Health check implementation with multiple check types.
"""

import asyncio
import psutil
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
import aiohttp
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from .logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult:
    """Health check result."""

    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Initialize health check result."""
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.duration_ms = duration_ms
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.details:
            result["details"] = self.details
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        return result


class HealthCheck:
    """Base health check class."""

    def __init__(self, name: str, critical: bool = False) -> None:
        """Initialize health check."""
        self.name = name
        self.critical = critical

    async def check(self) -> HealthCheckResult:
        """Perform health check."""
        raise NotImplementedError


class DatabaseHealthCheck(HealthCheck):
    """Database health check."""

    def __init__(
        self, session_factory: Callable[[], AsyncSession], name: str = "database"
    ) -> None:
        """Initialize database health check."""
        super().__init__(name, critical=True)
        self.session_factory = session_factory

    async def check(self) -> HealthCheckResult:
        """Check database connectivity."""
        start_time = asyncio.get_event_loop().time()
        try:
            async with self.session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"Database health check failed: {str(e)}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                duration_ms=duration_ms,
            )


class RedisHealthCheck(HealthCheck):
    """Redis health check."""

    def __init__(self, redis_url: str, name: str = "redis") -> None:
        """Initialize Redis health check."""
        super().__init__(name, critical=False)
        self.redis_url = redis_url

    async def check(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        start_time = asyncio.get_event_loop().time()
        try:
            client = await redis.from_url(self.redis_url)
            await client.ping()
            await client.aclose()

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.warning(f"Redis health check failed: {str(e)}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message=f"Redis connection failed: {str(e)}",
                duration_ms=duration_ms,
            )


class DiskSpaceHealthCheck(HealthCheck):
    """Disk space health check."""

    def __init__(
        self,
        path: str = "/",
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
        name: str = "disk_space",
    ) -> None:
        """Initialize disk space health check."""
        super().__init__(name, critical=False)
        self.path = path
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthCheckResult:
        """Check disk space usage."""
        try:
            usage = psutil.disk_usage(self.path)
            usage_percent = usage.percent

            details = {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": usage_percent,
            }

            if usage_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Disk usage at {usage_percent:.1f}%"
            elif usage_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Warning: Disk usage at {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage at {usage_percent:.1f}%"

            return HealthCheckResult(
                name=self.name, status=status, message=message, details=details
            )
        except Exception as e:
            logger.error(f"Disk space health check failed: {str(e)}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check disk space: {str(e)}",
            )


class MemoryHealthCheck(HealthCheck):
    """Memory usage health check."""

    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
        name: str = "memory",
    ) -> None:
        """Initialize memory health check."""
        super().__init__(name, critical=False)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()

            details = {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent_used": memory.percent,
            }

            if memory.percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Memory usage at {memory.percent:.1f}%"
            elif memory.percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Warning: Memory usage at {memory.percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage at {memory.percent:.1f}%"

            return HealthCheckResult(
                name=self.name, status=status, message=message, details=details
            )
        except Exception as e:
            logger.error(f"Memory health check failed: {str(e)}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check memory: {str(e)}",
            )


class ExternalServiceHealthCheck(HealthCheck):
    """External service health check."""

    def __init__(self, url: str, timeout: float = 5.0, name: Optional[str] = None) -> None:
        """Initialize external service health check."""
        super().__init__(name or f"external_{url}", critical=False)
        self.url = url
        self.timeout = timeout

    async def check(self) -> HealthCheckResult:
        """Check external service availability."""
        start_time = asyncio.get_event_loop().time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, timeout=self.timeout) as response:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                    if response.status < 400:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthStatus.HEALTHY,
                            message=f"Service responding with status {response.status}",
                            details={"status_code": response.status},
                            duration_ms=duration_ms,
                        )
                    else:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthStatus.DEGRADED,
                            message=f"Service returned error status {response.status}",
                            details={"status_code": response.status},
                            duration_ms=duration_ms,
                        )
        except asyncio.TimeoutError:
            duration_ms = self.timeout * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Service timeout after {self.timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.warning(f"External service health check failed: {str(e)}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Service check failed: {str(e)}",
                duration_ms=duration_ms,
            )


class HealthCheckRegistry:
    """Registry for health checks."""

    def __init__(self) -> None:
        """Initialize health check registry."""
        self.checks: List[HealthCheck] = []
        self._last_results: Optional[List[HealthCheckResult]] = None
        self._last_check_time: Optional[datetime] = None
        self._cache_duration = timedelta(seconds=10)

    def register(self, check: HealthCheck) -> None:
        """Register a health check."""
        self.checks.append(check)
        logger.info(f"Registered health check: {check.name}")

    async def run_checks(self, use_cache: bool = True) -> List[HealthCheckResult]:
        """Run all registered health checks."""
        # Use cached results if available and fresh
        if use_cache and self._last_results and self._last_check_time:
            if datetime.now(timezone.utc) - self._last_check_time < self._cache_duration:
                return self._last_results

        # Run checks in parallel
        results = await asyncio.gather(
            *[check.check() for check in self.checks], return_exceptions=True
        )

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Health check {self.checks[i].name} raised exception: {str(result)}"
                )
                processed_results.append(
                    HealthCheckResult(
                        name=self.checks[i].name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Check failed with error: {str(result)}",
                    )
                )
            else:
                processed_results.append(result)

        # Cache results
        self._last_results = processed_results
        self._last_check_time = datetime.now(timezone.utc)

        return processed_results

    def get_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Get overall health status from individual results."""
        # If any critical check is unhealthy, overall is unhealthy
        critical_checks = [c for c in self.checks if c.critical]
        for check in critical_checks:
            result = next((r for r in results if r.name == check.name), None)
            if result and result.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # If any check is unhealthy, overall is degraded
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.DEGRADED

        # If any check is degraded, overall is degraded
        if any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY


# Global registry
_registry = HealthCheckRegistry()


def register_health_check(check: HealthCheck) -> None:
    """Register a health check."""
    _registry.register(check)


async def run_health_checks(use_cache: bool = True) -> Dict[str, Any]:
    """Run all registered health checks and return results."""
    results = await _registry.run_checks(use_cache)
    overall_status = _registry.get_overall_status(results)

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": [r.to_dict() for r in results],
    }
