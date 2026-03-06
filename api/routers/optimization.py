from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from services.ai.circuit_breaker import AICircuitBreaker
from services.ai.assistant import ComplianceAssistant
from models.ai import ModelSelectionRequest
from auth.dependencies import get_current_user

# Constants
HTTP_INTERNAL_SERVER_ERROR = 500

router = APIRouter(prefix="/api/ai", tags=["AI Optimization"])
circuit_breaker = AICircuitBreaker()


@router.post("/model-selection")
async def model_selection(
    request: ModelSelectionRequest, current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """Select the optimal AI model based on task requirements."""
    try:
        selected_model = ComplianceAssistant.select_optimal_model(
            task_type=request.task_type,
            complexity=request.complexity,
            prefer_speed=request.prefer_speed,
        )
        return {
            "model": selected_model.model_name,
            "fallback_used": selected_model.is_fallback,
            "estimated_response_time": selected_model.estimated_response_time,
        }
    except Exception as e:
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/model-health")
async def model_health_check(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Check health status of all AI models."""
    health_statuses = circuit_breaker.get_all_model_health()
    return {"models": health_statuses, "timestamp": circuit_breaker.last_health_check}


@router.get("/performance-metrics")
async def performance_metrics(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Get AI performance metrics."""
    metrics = ComplianceAssistant.get_performance_metrics()
    return {
        "response_times": metrics.response_times,
        "success_rates": metrics.success_rates,
        "token_usage": metrics.token_usage,
        "cost_metrics": metrics.cost_metrics,
    }
