"""
import logging


logger = logging.getLogger(__name__)
# Constants
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_NOT_FOUND = 404


Evidence Collection Plan API Router

Endpoints for AI-driven evidence collection planning and task management.
"""

from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from database.user import User
from api.schemas.evidence_collection import (
    AutomationOpportunities,
    CollectionPlanCreate,
    CollectionPlanResponse,
    CollectionPlanSummary,
    EvidenceTaskResponse,
    TaskStatusUpdate,
)
from config.logging_config import get_logger
from database.db_setup import get_async_db
from services.ai.smart_evidence_collector import CollectionStatus, smart_evidence_collector
from services.business_service import get_business_profile

logger = get_logger(__name__)
router = APIRouter()


async def create_collection_plan(
    plan_request: CollectionPlanCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create an AI-driven evidence collection plan.

    This endpoint analyzes your business profile and compliance framework requirements
    to generate a prioritized, optimized collection plan with automation recommendations.
    """
    try:
        profile = await get_business_profile(db, current_user)
        if not profile:
            raise HTTPException(
                status_code=HTTP_BAD_REQUEST,
                detail="Business profile not found. Please complete your business profile first.",
            )
        existing_evidence = []
        if plan_request.include_existing_evidence:
            from sqlalchemy import select
            from database.models import Evidence

            evidence_query = select(Evidence).where(Evidence.business_profile_id == profile.id)
            if plan_request.framework:
                evidence_query = evidence_query.join("compliance_frameworks").where(
                    Evidence.framework_id.in_(
                        select("compliance_frameworks.id").where(
                            plan_request.framework == "compliance_frameworks.name"
                        )
                    )
                )
            result = await db.execute(evidence_query)
            evidence_records = result.scalars().all()
            existing_evidence = [
                {
                    "evidence_id": str(evidence.id),
                    "control_id": evidence.control_id,
                    "title": evidence.title,
                    "description": evidence.description,
                    "source": evidence.source,
                    "status": evidence.status,
                    "tags": evidence.tags or [],
                    "created_at": evidence.created_at,
                    "metadata": evidence.ai_metadata or {},
                }
                for evidence in evidence_records
            ]
        business_context = {
            "industry": profile.industry,
            "employee_count": profile.employee_count,
            "country": profile.country,
            "data_sensitivity": profile.data_sensitivity,
            "handles_personal_data": profile.handles_personal_data,
            "processes_payments": profile.processes_payments,
            "stores_health_data": profile.stores_health_data,
            "provides_financial_services": profile.provides_financial_services,
            "operates_critical_infrastructure": profile.operates_critical_infrastructure,
            "has_international_operations": profile.has_international_operations,
        }
        plan = await smart_evidence_collector.create_collection_plan(
            business_profile_id=str(profile.id),
            framework=plan_request.framework,
            business_context=business_context,
            existing_evidence=existing_evidence,
            target_completion_weeks=plan_request.target_completion_weeks or 12,
        )
        return CollectionPlanResponse(
            plan_id=plan.plan_id,
            business_profile_id=plan.business_profile_id,
            framework=plan.framework,
            total_tasks=plan.total_tasks,
            estimated_total_hours=plan.estimated_total_hours,
            completion_target_date=plan.completion_target_date,
            tasks=[
                EvidenceTaskResponse(
                    task_id=task.task_id,
                    framework=task.framework,
                    control_id=task.control_id,
                    evidence_type=task.evidence_type,
                    title=task.title,
                    description=task.description,
                    priority=task.priority.value,
                    automation_level=task.automation_level.value,
                    estimated_effort_hours=task.estimated_effort_hours,
                    dependencies=task.dependencies,
                    assigned_to=task.assigned_to,
                    due_date=task.due_date,
                    status=task.status.value,
                    created_at=task.created_at,
                    metadata=task.metadata,
                )
                for task in plan.tasks
            ],
            automation_opportunities=AutomationOpportunities(**plan.automation_opportunities),
            created_at=plan.created_at,
        )
    except Exception as e:
        logger.error("Error creating collection plan: %s" % e)
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/plans/{plan_id}", response_model=CollectionPlanResponse)
async def get_collection_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get a specific collection plan by ID."""
    plan = await smart_evidence_collector.get_collection_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail="Collection plan not found")
    profile = await get_business_profile(db, current_user)
    if not profile or str(profile.id) != plan.business_profile_id:
        raise HTTPException(status_code=HTTP_FORBIDDEN, detail="Access denied")
    return CollectionPlanResponse(
        plan_id=plan.plan_id,
        business_profile_id=plan.business_profile_id,
        framework=plan.framework,
        total_tasks=plan.total_tasks,
        estimated_total_hours=plan.estimated_total_hours,
        completion_target_date=plan.completion_target_date,
        tasks=[
            EvidenceTaskResponse(
                task_id=task.task_id,
                framework=task.framework,
                control_id=task.control_id,
                evidence_type=task.evidence_type,
                title=task.title,
                description=task.description,
                priority=task.priority.value,
                automation_level=task.automation_level.value,
                estimated_effort_hours=task.estimated_effort_hours,
                dependencies=task.dependencies,
                assigned_to=task.assigned_to,
                due_date=task.due_date,
                status=task.status.value,
                created_at=task.created_at,
                metadata=task.metadata,
            )
            for task in plan.tasks
        ],
        automation_opportunities=AutomationOpportunities(**plan.automation_opportunities),
        created_at=plan.created_at,
    )


async def list_collection_plans(
    framework: Optional[str] = Query(None, description="Filter by framework"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List all collection plans for the current user."""
    profile = await get_business_profile(db, current_user)
    if not profile:
        return []
    user_plans = []
    for _plan_id, plan in smart_evidence_collector.active_plans.items():
        if plan.business_profile_id == str(profile.id):
            if framework and plan.framework != framework:
                continue
            completed_tasks = len([t for t in plan.tasks if t.status == CollectionStatus.COMPLETED])
            if completed_tasks == plan.total_tasks:
                plan_status = "completed"
            elif any(t.status == CollectionStatus.IN_PROGRESS for t in plan.tasks):
                plan_status = "in_progress"
            else:
                plan_status = "pending"
            if status and plan_status != status:
                continue
            summary = CollectionPlanSummary(
                plan_id=plan.plan_id,
                framework=plan.framework,
                total_tasks=plan.total_tasks,
                completed_tasks=completed_tasks,
                estimated_total_hours=plan.estimated_total_hours,
                completion_target_date=plan.completion_target_date,
                status=plan_status,
                created_at=plan.created_at,
            )
            user_plans.append(summary)
    return user_plans


@router.get("/plans/{plan_id}/priority-tasks", response_model=List[EvidenceTaskResponse])
async def get_priority_tasks(
    plan_id: str,
    limit: int = Query(5, ge=1, le=20, description="Number of tasks to return"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get the next priority tasks for a collection plan."""
    plan = await smart_evidence_collector.get_collection_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail="Collection plan not found")
    profile = await get_business_profile(db, current_user)
    if not profile or str(profile.id) != plan.business_profile_id:
        raise HTTPException(status_code=HTTP_FORBIDDEN, detail="Access denied")
    priority_tasks = await smart_evidence_collector.get_next_priority_tasks(plan_id, limit)
    return [
        EvidenceTaskResponse(
            task_id=task.task_id,
            framework=task.framework,
            control_id=task.control_id,
            evidence_type=task.evidence_type,
            title=task.title,
            description=task.description,
            priority=task.priority.value,
            automation_level=task.automation_level.value,
            estimated_effort_hours=task.estimated_effort_hours,
            dependencies=task.dependencies,
            assigned_to=task.assigned_to,
            due_date=task.due_date,
            status=task.status.value,
            created_at=task.created_at,
            metadata=task.metadata,
        )
        for task in priority_tasks
    ]


@router.patch("/plans/{plan_id}/tasks/{task_id}", response_model=EvidenceTaskResponse)
async def update_task_status(
    plan_id: str,
    task_id: str,
    status_update: TaskStatusUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update the status of a specific task."""
    plan = await smart_evidence_collector.get_collection_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail="Collection plan not found")
    profile = await get_business_profile(db, current_user)
    if not profile or str(profile.id) != plan.business_profile_id:
        raise HTTPException(status_code=HTTP_FORBIDDEN, detail="Access denied")
    success = await smart_evidence_collector.update_task_status(
        plan_id=plan_id,
        task_id=task_id,
        status=CollectionStatus(status_update.status),
        completion_notes=status_update.completion_notes,
    )
    if not success:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail="Task not found")
    for task in plan.tasks:
        if task.task_id == task_id:
            return EvidenceTaskResponse(
                task_id=task.task_id,
                framework=task.framework,
                control_id=task.control_id,
                evidence_type=task.evidence_type,
                title=task.title,
                description=task.description,
                priority=task.priority.value,
                automation_level=task.automation_level.value,
                estimated_effort_hours=task.estimated_effort_hours,
                dependencies=task.dependencies,
                assigned_to=task.assigned_to,
                due_date=task.due_date,
                status=task.status.value,
                created_at=task.created_at,
                metadata=task.metadata,
            )
    raise HTTPException(status_code=HTTP_NOT_FOUND, detail="Task not found")


@router.get("/automation-recommendations/{framework}")
async def get_automation_recommendations(
    framework: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get automation recommendations for a specific framework."""
    profile = await get_business_profile(db, current_user)
    if not profile:
        raise HTTPException(
            status_code=HTTP_BAD_REQUEST,
            detail="Business profile not found. Please complete your business profile first.",
        )
    automation_rules = smart_evidence_collector.automation_rules
    recommendations = {
        "framework": framework,
        "automation_opportunities": [],
        "recommended_tools": set(),
        "estimated_time_savings": 0.0,
    }
    for evidence_type, rules in automation_rules.items():
        if rules["automation_level"].value in ["fully_automated", "semi_automated"]:
            opportunity = {
                "evidence_type": evidence_type,
                "automation_level": rules["automation_level"].value,
                "effort_reduction": f"{rules['effort_reduction'] * 100:.0f}%",
                "success_rate": f"{rules['success_rate'] * 100:.0f}%",
                "recommended_tools": rules["tools"],
            }
            recommendations["automation_opportunities"].append(opportunity)
            recommendations["recommended_tools"].update(rules["tools"])
            recommendations["estimated_time_savings"] += rules["effort_reduction"] * 8
    recommendations["recommended_tools"] = list(recommendations["recommended_tools"])
    return recommendations
