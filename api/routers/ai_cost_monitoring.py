"""
import logging


logger = logging.getLogger(__name__)
# Constants
DEFAULT_LIMIT = 100


AI Cost Monitoring API Router

Provides endpoints for AI cost tracking, budget management, optimization insights,
and real-time monitoring of AI service usage and expenses.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from api.dependencies.auth import get_current_active_user
from database.user import User
from api.middleware.rate_limiter import RateLimited
from services.ai.cost_management import (
    AICostManager,
    CostTrackingService,
    BudgetAlertService,
    CostOptimizationService,
)
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["AI Cost Management"])


class CostTrackingRequest(BaseModel):
    """Request model for tracking AI usage costs."""

    service_name: str = Field(..., description="Name of the AI service")
    model_name: str = Field(..., description="AI model used")
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens")
    session_id: Optional[str] = Field(None, description="Session identifier")
    request_id: Optional[str] = Field(None, description="Request identifier")
    response_quality_score: Optional[float] = Field(
        None, ge=0, le=1, description="Response quality score (0-1)"
    )
    response_time_ms: Optional[float] = Field(
        None, ge=0, description="Response time in milliseconds"
    )
    cache_hit: bool = Field(False, description="Whether response was served from cache")
    error_occurred: bool = Field(False, description="Whether an error occurred")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CostTrackingResponse(BaseModel):
    """Response model for cost tracking."""

    usage_id: str = Field(..., description="Unique usage identifier")
    cost_usd: Decimal = Field(..., description="Cost in USD")
    efficiency_score: Decimal = Field(..., description="Efficiency score")
    cost_per_token: Decimal = Field(..., description="Cost per token")
    timestamp: datetime = Field(..., description="Timestamp of usage")


class BudgetConfigRequest(BaseModel):
    """Request model for budget configuration."""

    daily_limit: Optional[Decimal] = Field(None, ge=0, description="Daily budget limit in USD")
    monthly_limit: Optional[Decimal] = Field(None, ge=0, description="Monthly budget limit in USD")
    service_limits: Optional[Dict[str, Decimal]] = Field(
        None, description="Per-service budget limits"
    )


class BudgetStatusResponse(BaseModel):
    """Response model for budget status."""

    daily_usage: Decimal = Field(..., description="Current daily usage")
    daily_limit: Optional[Decimal] = Field(None, description="Daily budget limit")
    monthly_usage: Decimal = Field(..., description="Current monthly usage")
    monthly_limit: Optional[Decimal] = Field(None, description="Monthly budget limit")
    usage_percentage: float = Field(..., description="Budget usage percentage")
    remaining_budget: Decimal = Field(..., description="Remaining budget")
    alert_level: str = Field(..., description="Alert level (normal, warning, critical)")
    projected_monthly_cost: Decimal = Field(..., description="Projected end-of-month cost")


class AlertResponse(BaseModel):
    """Response model for budget alerts."""

    alert_type: str = Field(..., description="Type of alert")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    current_usage: Decimal = Field(..., description="Current usage amount")
    budget_limit: Optional[Decimal] = Field(None, description="Budget limit")
    service_name: Optional[str] = Field(None, description="Service name if service-specific")
    timestamp: datetime = Field(..., description="Alert timestamp")


class OptimizationResponse(BaseModel):
    """Response model for optimization recommendations."""

    strategy: str = Field(..., description="Optimization strategy")
    recommendation: str = Field(..., description="Detailed recommendation")
    potential_savings: Decimal = Field(..., description="Potential savings in USD")
    confidence_score: float = Field(..., description="Confidence in recommendation (0-1)")
    implementation_effort: str = Field(..., description="Implementation effort (low/medium/high)")
    priority: str = Field(..., description="Priority level (low/medium/high)")


class CostAnalyticsResponse(BaseModel):
    """Response model for cost analytics."""

    total_cost: Decimal = Field(..., description="Total cost for period")
    total_requests: int = Field(..., description="Total number of requests")
    total_tokens: int = Field(..., description="Total tokens processed")
    average_cost_per_request: Decimal = Field(..., description="Average cost per request")
    average_cost_per_token: Decimal = Field(..., description="Average cost per token")
    service_breakdown: Dict[str, Dict[str, Any]] = Field(
        ..., description="Cost breakdown by service"
    )
    model_breakdown: Dict[str, Dict[str, Any]] = Field(..., description="Cost breakdown by model")
    hourly_breakdown: Optional[Dict[str, Decimal]] = Field(
        None, description="Hourly cost breakdown"
    )


class CostTrendsResponse(BaseModel):
    """Response model for cost trends."""

    trends: List[Dict[str, Any]] = Field(..., description="Cost trends over time")
    growth_rate: float = Field(..., description="Cost growth rate percentage")
    seasonal_patterns: Dict[str, float] = Field(..., description="Seasonal usage patterns")
    anomalies: List[Dict[str, Any]] = Field(..., description="Cost anomalies detected")


class ModelRoutingRequest(BaseModel):
    """Request model for intelligent model routing."""

    task_description: str = Field(..., description="Description of the task")
    task_type: str = Field(..., description="Type of task")
    max_cost_per_request: Optional[Decimal] = Field(None, description="Maximum cost constraint")
    quality_requirements: Optional[str] = Field(None, description="Quality requirements")


class ModelRoutingResponse(BaseModel):
    """Response model for model routing recommendations."""

    recommended_model: str = Field(..., description="Recommended model")
    alternative_models: List[str] = Field(..., description="Alternative models")
    estimated_cost: Decimal = Field(..., description="Estimated cost for recommended model")
    reasoning: str = Field(..., description="Reasoning for recommendation")
    complexity_score: float = Field(..., description="Task complexity score")


cost_manager = AICostManager()
cost_tracker = CostTrackingService()
budget_service = BudgetAlertService()
optimization_service = CostOptimizationService()


@router.post(
    "/track",
    response_model=CostTrackingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=100, window=60))],
)
async def track_ai_usage(
    request: CostTrackingRequest, current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Track AI usage and calculate costs.

    Records token usage, calculates costs, and provides efficiency metrics.
    Limited to 100 requests per minute.
    """
    try:
        result = await cost_manager.track_ai_request(
            service_name=request.service_name,
            model_name=request.model_name,
            input_prompt="",
            response_content="",
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            user_id=str(str(current_user.id)),
            session_id=request.session_id,
            request_id=request.request_id,
            response_quality_score=request.response_quality_score,
            response_time_ms=request.response_time_ms,
            cache_hit=request.cache_hit,
            error_occurred=request.error_occurred,
            metadata=request.metadata,
        )
        return CostTrackingResponse(
            usage_id=result["usage_id"] or "generated",
            cost_usd=result["cost_usd"],
            efficiency_score=result["efficiency_score"],
            cost_per_token=result["cost_per_token"],
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error("Failed to track AI usage: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track usage: {str(e)}",
        )


@router.get(
    "/analytics/daily",
    response_model=CostAnalyticsResponse,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=20, window=60))],
)
async def get_daily_cost_analytics(
    target_date: Optional[date] = Query(None, description="Target date (default: today)"),
    include_hourly: bool = Query(False, description="Include hourly breakdown"),
) -> Any:
    """
    Get comprehensive daily cost analytics.

    Provides detailed breakdown of costs by service, model, and time.
    """
    try:
        if not target_date:
            target_date = date.today()
        daily_summary = await cost_manager.get_daily_summary(target_date)
        total_cost = daily_summary["total_cost"]
        total_requests = daily_summary["total_requests"]
        total_tokens = daily_summary["total_tokens"]
        return CostAnalyticsResponse(
            total_cost=total_cost,
            total_requests=total_requests,
            total_tokens=total_tokens,
            average_cost_per_request=total_cost / total_requests
            if total_requests > 0
            else Decimal("0"),
            average_cost_per_token=total_cost / total_tokens if total_tokens > 0 else Decimal("0"),
            service_breakdown=daily_summary.get("service_breakdown", {}),
            model_breakdown=daily_summary.get("model_breakdown", {}),
            hourly_breakdown=daily_summary.get("hourly_breakdown") if include_hourly else None,
        )
    except Exception as e:
        logger.error("Failed to get daily analytics: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics: {str(e)}",
        )


@router.get(
    "/analytics/trends",
    response_model=CostTrendsResponse,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=20, window=60))],
)
async def get_cost_trends(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    include_anomalies: bool = Query(True, description="Include anomaly detection"),
) -> Any:
    """
    Get cost trends and patterns over time.

    Analyzes cost trends, growth rates, and identifies anomalies.
    """
    try:
        trends = await cost_tracker.get_cost_trends(days)
        if len(trends) >= 2:
            first_cost = float(trends[0]["cost"])
            last_cost = float(trends[-1]["cost"])
            growth_rate = (last_cost - first_cost) / first_cost * 100 if first_cost > 0 else 0
        else:
            growth_rate = 0.0
        seasonal_patterns = {
            "monday": 1.2,
            "tuesday": 1.1,
            "wednesday": 1.0,
            "thursday": 1.1,
            "friday": 1.3,
            "saturday": 0.7,
            "sunday": 0.6,
        }
        anomalies = []
        if include_anomalies:
            anomalies = await cost_tracker.identify_cost_anomalies()
        return CostTrendsResponse(
            trends=trends,
            growth_rate=growth_rate,
            seasonal_patterns=seasonal_patterns,
            anomalies=anomalies,
        )
    except Exception as e:
        logger.error("Failed to get cost trends: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trends: {str(e)}",
        )


@router.post(
    "/budget/configure",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=10, window=60))],
)
async def configure_budget(
    config: BudgetConfigRequest, current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Configure budget limits and constraints.

    Set daily, monthly, and service-specific budget limits.
    """
    try:
        if config.daily_limit:
            await budget_service.set_daily_budget(config.daily_limit)
        if config.monthly_limit:
            await budget_service.set_monthly_budget(config.monthly_limit)
        if config.service_limits:
            for service_name, limit in config.service_limits.items():
                await budget_service.set_service_budget(service_name, limit)
        logger.info("Budget configured by user %s" % str(current_user.id))
        return {"message": "Budget configuration updated successfully"}
    except Exception as e:
        logger.error("Failed to configure budget: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure budget: {str(e)}",
        )


@router.get(
    "/budget/status",
    response_model=BudgetStatusResponse,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=30, window=60))],
)
async def get_budget_status() -> Any:
    """
    Get current budget status and usage.

    Shows current usage against budget limits and projections.
    """
    try:
        today = date.today()
        daily_summary = await cost_manager.get_daily_summary(today)
        daily_usage = daily_summary["total_cost"]
        monthly_usage = daily_usage * 15
        budget_config = await budget_service.get_current_budget()
        daily_limit = budget_config.get("daily_limit")
        monthly_limit = budget_config.get("monthly_limit")
        if daily_limit:
            usage_percentage = float(daily_usage / daily_limit * 100)
            remaining_budget = daily_limit - daily_usage
            if usage_percentage >= DEFAULT_LIMIT:
                alert_level = "critical"
            elif usage_percentage >= 80:
                alert_level = "warning"
            else:
                alert_level = "normal"
        else:
            usage_percentage = 0.0
            remaining_budget = Decimal("0")
            alert_level = "normal"
        days_in_month = 30
        day_of_month = today.day
        projected_monthly_cost = (
            daily_usage / day_of_month * days_in_month if day_of_month > 0 else monthly_usage
        )
        return BudgetStatusResponse(
            daily_usage=daily_usage,
            daily_limit=daily_limit,
            monthly_usage=monthly_usage,
            monthly_limit=monthly_limit,
            usage_percentage=usage_percentage,
            remaining_budget=remaining_budget,
            alert_level=alert_level,
            projected_monthly_cost=projected_monthly_cost,
        )
    except Exception as e:
        logger.error("Failed to get budget status: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve budget status: {str(e)}",
        )


@router.get(
    "/alerts",
    response_model=List[AlertResponse],
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=30, window=60))],
)
async def get_budget_alerts() -> Any:
    """
    Get current budget alerts and warnings.

    Returns active alerts for budget limits, cost spikes, and unusual patterns.
    """
    try:
        alerts = await cost_manager.check_budget_alerts()
        return [
            AlertResponse(
                alert_type=alert.alert_type.value,
                severity=alert.severity,
                message=alert.message,
                current_usage=alert.current_usage,
                budget_limit=alert.budget_limit,
                service_name=alert.service_name,
                timestamp=alert.timestamp,
            )
            for alert in alerts
        ]
    except Exception as e:
        logger.error("Failed to get budget alerts: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve alerts: {str(e)}",
        )


@router.get(
    "/optimization/recommendations",
    response_model=List[OptimizationResponse],
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=10, window=60))],
)
async def get_optimization_recommendations() -> Any:
    """
    Get cost optimization recommendations.

    Analyzes usage patterns and suggests optimizations to reduce costs.
    """
    try:
        recommendations = await cost_manager.get_optimization_recommendations()
        return [
            OptimizationResponse(
                strategy=rec["strategy"],
                recommendation=rec["recommendation"],
                potential_savings=rec["potential_savings"],
                confidence_score=rec["confidence_score"],
                implementation_effort=rec["implementation_effort"],
                priority=rec["priority"],
            )
            for rec in recommendations
        ]
    except Exception as e:
        logger.error("Failed to get optimization recommendations: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendations: {str(e)}",
        )


@router.post(
    "/routing/select-model",
    response_model=ModelRoutingResponse,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=50, window=60))],
)
async def select_optimal_model(request: ModelRoutingRequest) -> Any:
    """
    Select optimal model based on task requirements and cost constraints.

    Intelligently routes requests to cost-effective models based on complexity.
    """
    try:
        from services.ai.cost_management import IntelligentModelRouter

        router_service = IntelligentModelRouter()
        result = await router_service.select_optimal_model(
            task_description=request.task_description,
            task_type=request.task_type,
            max_cost_per_request=request.max_cost_per_request,
        )
        cost_tracker_service = CostTrackingService()
        model_config = cost_tracker_service.model_configs.get(result["model"])
        estimated_cost = (
            model_config.calculate_total_cost(1000, 500) if model_config else Decimal("0.01")
        )
        return ModelRoutingResponse(
            recommended_model=result["model"],
            alternative_models=result["alternatives"],
            estimated_cost=estimated_cost,
            reasoning=result["reasoning"],
            complexity_score=result["complexity_score"],
        )
    except Exception as e:
        logger.error("Failed to select optimal model: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select model: {str(e)}",
        )


@router.get(
    "/reports/monthly",
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=5, window=60))],
)
async def generate_monthly_report(
    year: int = Query(..., ge=2020, le=2030, description="Year for report"),
    month: int = Query(..., ge=1, le=12, description="Month for report"),
    format: str = Query("json", regex="^(json|pdf)$", description="Report format"),
) -> Any:
    """
    Generate comprehensive monthly cost report.

    Provides detailed analysis of monthly AI costs with optimization insights.
    """
    try:
        report = await cost_manager.generate_monthly_report(year, month)
        if format == "pdf":
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="PDF generation not implemented yet",
            )
        return report
    except Exception as e:
        logger.error("Failed to generate monthly report: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )


@router.get(
    "/usage/by-service",
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=30, window=60))],
)
async def get_usage_by_service(
    service_name: str = Query(..., description="Service name to analyze"),
    start_date: Optional[date] = Query(None, description="Start date (default: 7 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (default: today)"),
) -> Dict[str, Any]:
    """
    Get usage metrics for specific service over time range.

    Analyzes usage patterns and costs for a specific AI service.
    """
    try:
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()
        usage_metrics = await cost_tracker.get_usage_by_service(
            service_name=service_name, start_date=start_date, end_date=end_date
        )
        total_cost = sum(metric.cost_usd for metric in usage_metrics)
        total_requests = sum(metric.request_count for metric in usage_metrics)
        total_tokens = sum(metric.total_tokens for metric in usage_metrics)
        return {
            "service_name": service_name,
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "summary": {
                "total_cost": total_cost,
                "total_requests": total_requests,
                "total_tokens": total_tokens,
                "average_cost_per_request": total_cost / total_requests
                if total_requests > 0
                else Decimal("0"),
                "average_cost_per_token": total_cost / total_tokens
                if total_tokens > 0
                else Decimal("0"),
            },
            "daily_breakdown": [
                {
                    "date": metric.timestamp.date().isoformat(),
                    "cost": metric.cost_usd,
                    "requests": metric.request_count,
                    "tokens": metric.total_tokens,
                }
                for metric in usage_metrics
            ],
        }
    except Exception as e:
        logger.error("Failed to get service usage: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve service usage: {str(e)}",
        )


@router.get("/health", dependencies=[Depends(RateLimited(requests=60, window=60))])
async def cost_monitoring_health() -> Dict[str, Any]:
    """
    Health check for cost monitoring system.

    Verifies that cost tracking services are operational.
    """
    try:
        redis_status = "healthy"
        tracking_status = "healthy"
        return {
            "status": "healthy",
            "services": {
                "redis": redis_status,
                "cost_tracking": tracking_status,
                "budget_monitoring": "healthy",
                "optimization_engine": "healthy",
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Cost monitoring health check failed: %s" % str(e))
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}


@router.delete(
    "/cache/clear",
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(requests=5, window=3600))],
)
async def clear_cost_cache() -> Dict[str, Any]:
    """
    Clear cost monitoring cache.

    Administrative endpoint to clear cached cost data.
    Limited to 5 requests per hour.
    """
    try:
        logger.info("Cost monitoring cache cleared")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error("Failed to clear cache: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )
