"""
import logging


logger = logging.getLogger(__name__)
# Constants
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

MINUTE_SECONDS = 60

CONFIDENCE_THRESHOLD = 0.8
HALF_RATIO = 0.5


Performance Monitoring API Endpoints
Provides real-time performance metrics and optimization recommendations
"""

from datetime import datetime, timezone
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from services.performance_monitor import get_performance_monitor, monitor_performance
from api.middleware.rbac_middleware import require_permissions
from api.dependencies.auth import get_current_active_user
from database.user import User
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["performance-monitoring"])


class PerformanceOverview(BaseModel):
    """Performance overview response model."""

    performance_score: float
    status: str
    critical_issues: int
    recommendations_count: int
    last_updated: datetime


class DatabasePerformanceResponse(BaseModel):
    """Database performance metrics response."""

    connection_pool_size: int
    active_connections: int
    connection_pool_utilization: float
    avg_query_time: float
    slow_queries_count: int
    performance_rating: str


class CachePerformanceResponse(BaseModel):
    """Cache performance metrics response."""

    hit_rate: float
    miss_rate: float
    memory_usage: int
    total_requests: int
    avg_response_time: float
    performance_rating: str


class APIPerformanceResponse(BaseModel):
    """API performance metrics response."""

    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    slowest_endpoints: List[Dict[str, Any]]
    performance_rating: str


class SystemMetricsResponse(BaseModel):
    """System metrics response."""

    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: float
    status: str


class OptimizationRecommendation(BaseModel):
    """Performance optimization recommendation."""

    category: str
    priority: str
    issue: str
    recommendation: str
    current_value: str
    suggested_value: str
    impact: str


class PerformanceTrendsResponse(BaseModel):
    """Performance trends response."""

    hours: int
    data_points: int
    trends: Dict[str, Dict[str, float]]


@router.get("/overview", response_model=PerformanceOverview)
@monitor_performance("performance_overview")
async def get_performance_overview(
    current_user: User = Depends(get_current_active_user),
) -> PerformanceOverview:
    """
    Get overall performance overview with key metrics.

    Returns:
        - Performance score (0-100)
        - System status
        - Critical issues count
        - Available recommendations
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        metrics = await monitor.collect_comprehensive_metrics()
        recommendations = await monitor.generate_optimization_recommendations()
        critical_issues = len([r for r in recommendations if r["priority"] == "high"])
        score = metrics["performance_score"]
        if score >= 90:
            status = "excellent"
        elif score >= 75:
            status = "good"
        elif score >= MINUTE_SECONDS:
            status = "warning"
        else:
            status = "critical"
        return PerformanceOverview(
            performance_score=score,
            status=status,
            critical_issues=critical_issues,
            recommendations_count=len(recommendations),
            last_updated=datetime.fromisoformat(metrics["timestamp"]),
        )
    except Exception as e:
        logger.error("Error getting performance overview: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get performance overview"
        )


@router.get("/database", response_model=DatabasePerformanceResponse)
@monitor_performance("database_performance")
async def get_database_performance(
    current_user: User = Depends(get_current_active_user),
) -> DatabasePerformanceResponse:
    """
    Get detailed database performance metrics.

    Includes:
    - Connection pool utilization
    - Query performance
    - Slow query analysis
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        db_metrics = await monitor.get_database_metrics()
        if db_metrics.avg_query_time < 0.05 and db_metrics.connection_pool_utilization < 0.7:
            rating = "excellent"
        elif (
            db_metrics.avg_query_time < 0.1
            and db_metrics.connection_pool_utilization < CONFIDENCE_THRESHOLD
        ):
            rating = "good"
        elif db_metrics.avg_query_time < 0.2 and db_metrics.connection_pool_utilization < 0.9:
            rating = "warning"
        else:
            rating = "critical"
        return DatabasePerformanceResponse(
            connection_pool_size=db_metrics.connection_pool_size,
            active_connections=db_metrics.active_connections,
            connection_pool_utilization=db_metrics.connection_pool_utilization,
            avg_query_time=db_metrics.avg_query_time,
            slow_queries_count=db_metrics.slow_queries_count,
            performance_rating=rating,
        )
    except Exception as e:
        logger.error("Error getting database performance: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get database metrics"
        )


@router.get("/cache", response_model=CachePerformanceResponse)
@monitor_performance("cache_performance")
async def get_cache_performance(
    current_user: User = Depends(get_current_active_user),
) -> CachePerformanceResponse:
    """
    Get cache performance metrics.

    Includes:
    - Hit/miss rates
    - Memory usage
    - Response times
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        cache_metrics = await monitor.get_cache_metrics()
        if cache_metrics.hit_rate >= 0.9:
            rating = "excellent"
        elif cache_metrics.hit_rate >= CONFIDENCE_THRESHOLD:
            rating = "good"
        elif cache_metrics.hit_rate >= 0.7:
            rating = "warning"
        else:
            rating = "critical"
        return CachePerformanceResponse(
            hit_rate=cache_metrics.hit_rate,
            miss_rate=cache_metrics.miss_rate,
            memory_usage=cache_metrics.memory_usage,
            total_requests=cache_metrics.total_requests,
            avg_response_time=cache_metrics.avg_response_time,
            performance_rating=rating,
        )
    except Exception as e:
        logger.error("Error getting cache performance: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get cache metrics"
        )


@router.get("/api", response_model=APIPerformanceResponse)
@monitor_performance("api_performance")
async def get_api_performance(
    current_user: User = Depends(get_current_active_user),
) -> APIPerformanceResponse:
    """
    Get API performance metrics.

    Includes:
    - Response time percentiles
    - Requests per second
    - Slowest endpoints
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        api_metrics = await monitor.get_api_metrics()
        if api_metrics.avg_response_time < 0.1 and api_metrics.p95_response_time < HALF_RATIO:
            rating = "excellent"
        elif api_metrics.avg_response_time < 0.2 and api_metrics.p95_response_time < 1.0:
            rating = "good"
        elif api_metrics.avg_response_time < HALF_RATIO and api_metrics.p95_response_time < 2.0:
            rating = "warning"
        else:
            rating = "critical"
        return APIPerformanceResponse(
            avg_response_time=api_metrics.avg_response_time,
            p95_response_time=api_metrics.p95_response_time,
            p99_response_time=api_metrics.p99_response_time,
            requests_per_second=api_metrics.requests_per_second,
            slowest_endpoints=api_metrics.slowest_endpoints,
            performance_rating=rating,
        )
    except Exception as e:
        logger.error("Error getting API performance: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get API metrics"
        )


@router.get("/system", response_model=SystemMetricsResponse)
@monitor_performance("system_metrics")
async def get_system_metrics(
    current_user: User = Depends(get_current_active_user),
) -> SystemMetricsResponse:
    """
    Get system resource metrics.

    Includes:
    - CPU usage
    - Memory usage
    - Disk usage
    - Load average
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        system_metrics = monitor.get_system_metrics()
        cpu_ok = system_metrics["cpu_percent"] < 80
        memory_ok = system_metrics["memory_percent"] < 80
        disk_ok = system_metrics["disk_percent"] < 90
        if cpu_ok and memory_ok and disk_ok:
            status = "healthy"
        elif system_metrics["cpu_percent"] > 90 or system_metrics["memory_percent"] > 90:
            status = "critical"
        else:
            status = "warning"
        return SystemMetricsResponse(
            cpu_percent=system_metrics["cpu_percent"],
            memory_percent=system_metrics["memory_percent"],
            disk_percent=system_metrics["disk_percent"],
            load_average=system_metrics["load_average"],
            status=status,
        )
    except Exception as e:
        logger.error("Error getting system metrics: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get system metrics"
        )


@monitor_performance("performance_recommendations")
async def get_optimization_recommendations(
    current_user: User = Depends(get_current_active_user),
) -> List[OptimizationRecommendation]:
    """
    Get performance optimization recommendations.

    Returns prioritized list of actionable performance improvements.
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        recommendations = await monitor.generate_optimization_recommendations()
        return [OptimizationRecommendation(**rec) for rec in recommendations]
    except Exception as e:
        logger.error("Error getting optimization recommendations: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get recommendations"
        )


@router.get("/trends", response_model=PerformanceTrendsResponse)
@monitor_performance("performance_trends")
async def get_performance_trends(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to analyze (1-168)"),
    current_user: User = Depends(get_current_active_user),
) -> PerformanceTrendsResponse:
    """
    Get performance trends over time.

    Args:
        hours: Number of hours to analyze (1-168, default 24)

    Returns:
        Performance trends and statistics
    """
    try:
        await require_permissions(current_user, "performance:read")
        monitor = await get_performance_monitor()
        trends = await monitor.get_performance_trends(hours=hours)
        return PerformanceTrendsResponse(**trends)
    except Exception as e:
        logger.error("Error getting performance trends: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to get performance trends"
        )


@router.post("/alerts/configure")
@monitor_performance("configure_performance_alerts")
async def configure_performance_alerts(
    alerts_config: Dict[str, Any], current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Configure performance alerting thresholds.

    Args:
        alerts_config: Alert configuration with thresholds
    """
    try:
        await require_permissions(current_user, "performance:admin")
        required_fields = ["response_time_threshold", "cache_hit_rate_threshold", "cpu_threshold"]
        for field in required_fields:
            if field not in alerts_config:
                raise HTTPException(
                    status_code=HTTP_BAD_REQUEST, detail=f"Missing required field: {field}"
                )
        from config.cache import get_cache_manager

        cache = await get_cache_manager()
        await cache.set("performance_alerts_config", alerts_config, ttl=86400)
        logger.info("Performance alerts configured by user %s" % current_user.id)
        return {"status": "success", "message": "Performance alerts configured"}
    except Exception as e:
        logger.error("Error configuring performance alerts: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to configure alerts"
        )


async def performance_monitoring_health() -> Any:
    """
    Health check for performance monitoring system.
    """
    try:
        monitor = await get_performance_monitor()
        health_status = {
            "status": "healthy",
            "monitoring_active": monitor.monitoring_active,
            "metrics_available": len(monitor.performance_history) > 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return health_status
    except Exception as e:
        logger.error("Performance monitoring health check failed: %s" % e)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/monitoring/start")
async def start_performance_monitoring(
    interval: int = Query(60, ge=10, le=300, description="Monitoring interval in seconds"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Start continuous performance monitoring.

    Args:
        interval: Monitoring interval in seconds (10-300)
    """
    try:
        await require_permissions(current_user, "performance:admin")
        monitor = await get_performance_monitor()
        if monitor.monitoring_active:
            return {
                "status": "already_running",
                "message": "Performance monitoring is already active",
            }
        import asyncio

        asyncio.create_task(monitor.start_monitoring(interval=interval))
        logger.info(
            "Performance monitoring started by user %s with %ss interval"
            % (current_user.id, interval)
        )
        return {
            "status": "started",
            "interval": interval,
            "message": "Performance monitoring started",
        }
    except Exception as e:
        logger.error("Error starting performance monitoring: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to start monitoring"
        )


@router.post("/monitoring/stop")
async def stop_performance_monitoring(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Stop continuous performance monitoring.
    """
    try:
        await require_permissions(current_user, "performance:admin")
        monitor = await get_performance_monitor()
        monitor.stop_monitoring()
        logger.info("Performance monitoring stopped by user %s" % current_user.id)
        return {"status": "stopped", "message": "Performance monitoring stopped"}
    except Exception as e:
        logger.error("Error stopping performance monitoring: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail="Failed to stop monitoring"
        )
