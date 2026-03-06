"""

Monitoring endpoints for health checks and metrics.
"""

from typing import Any, Dict
from fastapi import APIRouter, status, HTTPException
from fastapi.responses import PlainTextResponse

from app.core.monitoring.health import (
    run_health_checks,
    register_health_check,
    DatabaseHealthCheck,
    RedisHealthCheck,
    DiskSpaceHealthCheck,
    MemoryHealthCheck,
    ExternalServiceHealthCheck,
)
from app.core.monitoring.metrics import get_metrics
from config.settings import settings

router = APIRouter()


def setup_health_checks() -> None:
    """Setup health checks for the application."""
    # Database health check
    if hasattr(settings, "database_url") and settings.database_url:
        from database.db_setup import get_db_session as get_session

        register_health_check(DatabaseHealthCheck(get_session, name="database"))

    # Redis health check
    if hasattr(settings, "redis_url") and settings.redis_url:
        register_health_check(RedisHealthCheck(settings.redis_url, name="redis"))

    # Disk space health check
    register_health_check(
        DiskSpaceHealthCheck(
            path="/", warning_threshold=80.0, critical_threshold=90.0, name="disk_space"
        )
    )

    # Memory health check
    register_health_check(
        MemoryHealthCheck(warning_threshold=85.0, critical_threshold=95.0, name="memory")
    )

    # External service health checks (optional)
    if hasattr(settings, "openai_api_base") and settings.openai_api_base:
        register_health_check(
            ExternalServiceHealthCheck(
                url=f"{settings.openai_api_base}/models", timeout=5.0, name="openai"
            )
        )


@router.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns overall system health status and individual component statuses.
    """
    return await run_health_checks(use_cache=True)


@router.get("/health/live", tags=["health"])
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint.

    Returns a simple response indicating the service is alive.
    """
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
async def readiness_check() -> Dict[str, Any]:
    """
    Kubernetes readiness probe endpoint.

    Checks if the service is ready to accept traffic.
    """
    result = await run_health_checks(use_cache=False)

    # Return 503 if not healthy
    if result["status"] != "healthy":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result)

    return result


@router.get("/metrics", tags=["monitoring"])
async def metrics_endpoint() -> PlainTextResponse:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    metrics_data = get_metrics()

    # Convert to Prometheus format
    prometheus_output = []

    for metric in metrics_data["metrics"]:
        name = metric["name"]
        value = metric["value"]
        labels = metric.get("labels", {})

        # Format labels
        label_str = ""
        if labels:
            label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"

        # Add metric line
        prometheus_output.append(f"{name}{label_str} {value}")

    return PlainTextResponse(content="\n".join(prometheus_output), media_type="text/plain")


@router.get("/metrics/json", tags=["monitoring"])
async def metrics_json() -> Dict[str, Any]:
    """
    Get metrics in JSON format.

    Returns all collected metrics as JSON for debugging or custom monitoring.
    """
    return get_metrics()


@router.post("/metrics/reset", tags=["monitoring"])
async def reset_metrics() -> Dict[str, str]:
    """
    Reset all metrics counters.

    This endpoint should be protected in production.
    """
    from app.core.monitoring.metrics import get_metrics_collector

    collector = get_metrics_collector()

    # Reset all counters
    for metric in collector.metrics.values():
        if hasattr(metric, "reset"):
            metric.reset()
        elif hasattr(metric, "value"):
            metric.value = 0

    return {"status": "metrics reset"}


@router.get("/debug/info", tags=["debug"])
async def debug_info() -> Dict[str, Any]:
    """
    Get debug information about the application.

    This endpoint should be disabled in production.
    """
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoint disabled in production",
        )

    import sys
    import platform
    import os

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "process_id": os.getpid(),
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "cors_origins": settings.cors_origins,
        "database_connected": hasattr(settings, "database_url") and bool(settings.database_url),
        "redis_connected": hasattr(settings, "redis_url") and bool(settings.redis_url),
    }


# Initialize health checks when module is imported
setup_health_checks()
