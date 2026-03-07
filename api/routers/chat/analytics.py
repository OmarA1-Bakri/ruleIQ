"""
Analytics, performance, and quality metrics endpoints.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from database.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/cache/clear", dependencies=[Depends(validate_request)])
async def clear_ai_cache(
    pattern: str = Query(default="*", description="Cache pattern to clear"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Clear AI response cache entries matching a pattern.
    Requires appropriate permissions for cache management.
    """
    try:
        from services.ai.response_cache import get_ai_cache

        ai_cache = await get_ai_cache()
        cleared_count = await ai_cache.clear_cache_pattern(pattern)

        return {
            "cleared_entries": cleared_count,
            "pattern": pattern,
            "cleared_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/performance/metrics", dependencies=[Depends(validate_request)])
async def get_ai_performance_metrics(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get comprehensive AI performance metrics including:
    - Response time statistics
    - Optimization effectiveness
    - Cost analysis and savings
    - System health indicators
    """
    try:
        from services.ai.performance_optimizer import get_performance_optimizer
        from services.ai.response_cache import get_ai_cache

        # Get performance metrics
        optimizer = await get_performance_optimizer()
        performance_metrics = await optimizer.get_performance_metrics()

        # Get cache metrics
        ai_cache = await get_ai_cache()
        cache_metrics = await ai_cache.get_cache_metrics()

        return {
            "performance_metrics": performance_metrics,
            "cache_metrics": cache_metrics,
            "system_status": "optimal",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.post("/performance/optimize", dependencies=[Depends(validate_request)])
async def optimize_ai_performance(
    enable_batching: bool = Query(default=True, description="Enable request batching"),
    enable_compression: bool = Query(default=True, description="Enable prompt compression"),
    max_concurrent: int = Query(default=10, description="Maximum concurrent requests"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Configure AI performance optimization settings.
    Allows fine-tuning of performance parameters for optimal system operation.
    """
    try:
        from services.ai.performance_optimizer import get_performance_optimizer

        optimizer = await get_performance_optimizer()

        # Update optimization settings
        optimizer.enable_batching = enable_batching
        optimizer.enable_compression = enable_compression
        optimizer.max_concurrent_requests = max_concurrent

        # Update semaphore if concurrent limit changed
        if max_concurrent != optimizer.request_semaphore._value:
            optimizer.request_semaphore = asyncio.Semaphore(max_concurrent)

        return {
            "optimization_settings": {
                "batching_enabled": enable_batching,
                "compression_enabled": enable_compression,
                "max_concurrent_requests": max_concurrent,
            },
            "status": "updated",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error updating performance settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update performance settings")


@router.get("/analytics/dashboard", dependencies=[Depends(validate_request)])
async def get_analytics_dashboard(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get comprehensive analytics dashboard data including:
    - Real-time performance metrics
    - Usage analytics and trends
    - Cost analysis and optimization insights
    - Quality metrics and feedback
    - System alerts and health status
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        dashboard_data = await monitor.get_dashboard_data()

        return dashboard_data

    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics dashboard")


@router.get("/analytics/usage", dependencies=[Depends(validate_request)])
async def get_usage_analytics(
    days: int = Query(default=7, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get detailed usage analytics including:
    - Framework usage patterns
    - Content type distribution
    - User activity trends
    - Daily usage patterns
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        usage_data = await monitor.get_usage_analytics(days)

        return usage_data

    except Exception as e:
        logger.error(f"Error getting usage analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage analytics")


@router.get("/analytics/cost", dependencies=[Depends(validate_request)])
async def get_cost_analytics(
    days: int = Query(default=30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get comprehensive cost analytics including:
    - Total cost breakdown
    - Cost trends and patterns
    - Optimization opportunities
    - ROI analysis
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        cost_data = await monitor.get_cost_analytics(days)

        return cost_data

    except Exception as e:
        logger.error(f"Error getting cost analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cost analytics")


@router.get("/analytics/alerts", dependencies=[Depends(validate_request)])
async def get_system_alerts(
    resolved: Optional[bool] = Query(default=None, description="Filter by resolution status"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get system alerts and notifications.
    Optionally filter by resolution status.
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        alerts = await monitor.get_alerts(resolved)

        return {
            "alerts": alerts,
            "total_count": len(alerts),
            "filter_applied": {"resolved": resolved} if resolved is not None else None,
        }

    except Exception as e:
        logger.error(f"Error getting system alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system alerts")


@router.post("/analytics/alerts/{alert_id}/resolve", dependencies=[Depends(validate_request)])
async def resolve_system_alert(
    alert_id: str, current_user: User = Depends(get_current_active_user)
):
    """
    Mark a system alert as resolved.
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        success = await monitor.resolve_alert(alert_id)

        if success:
            return {
                "alert_id": alert_id,
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            raise HTTPException(status_code=404, detail="Alert not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.get("/quality/metrics", dependencies=[Depends(validate_request)])
async def get_quality_metrics(current_user: User = Depends(get_current_active_user)):
    """
    Get comprehensive quality metrics and performance indicators.
    """
    try:
        from services.ai.quality_monitor import get_quality_monitor

        monitor = await get_quality_monitor()

        return {
            "overall_metrics": monitor.metrics,
            "quality_thresholds": {
                level.value: threshold for level, threshold in monitor.quality_thresholds.items()
            },
            "total_assessments": len(monitor.quality_assessments),
            "total_feedback_items": len(monitor.feedback_history),
            "recent_trends": await monitor.get_quality_trends(7),  # Last 7 days
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting quality metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quality metrics")
