"""
Evidence recommendation and analysis endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from api.utils.security_validation import SecurityValidator
from database.user import User
from api.schemas.chat import (
    ComplianceAnalysisRequest,
    ComplianceAnalysisResponse,
    EvidenceRecommendationRequest,
    EvidenceRecommendationResponse,
)
from database.business_profile import BusinessProfile
from database.db_setup import get_async_db, get_db
from services.ai import ComplianceAssistant

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/evidence-recommendations",
    response_model=List[EvidenceRecommendationResponse],
    dependencies=[Depends(validate_request)],
)
async def get_evidence_recommendations(
    request: EvidenceRecommendationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get AI-powered evidence collection recommendations."""
    try:
        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        recommendations = await assistant.get_evidence_recommendations(
            user=current_user,
            business_profile_id=UUID(str(business_profile.id)),
            target_framework=request.framework or "unknown",
        )

        return [EvidenceRecommendationResponse(**rec) for rec in recommendations]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evidence recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.post(
    "/compliance-analysis",
    response_model=ComplianceAnalysisResponse,
    dependencies=[Depends(validate_request)],
)
async def analyze_compliance_gap(
    request: ComplianceAnalysisRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Analyze compliance gaps for a specific framework."""
    try:
        from sqlalchemy import select

        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        analysis = await assistant.analyze_evidence_gap(
            business_profile_id=UUID(str(business_profile.id)),
            framework=request.framework,
        )

        return ComplianceAnalysisResponse(**analysis)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing compliance gap: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze compliance gap")


@router.post("/context-aware-recommendations", dependencies=[Depends(validate_request)])
async def get_context_aware_recommendations(
    framework: str = Query(..., min_length=1, description="Framework to get recommendations for"),
    context_type: str = Query(default="comprehensive", description="Type of context analysis"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get enhanced context-aware evidence recommendations that consider:
    - Business profile and industry specifics
    - Existing evidence and gaps
    - User behavior patterns
    - Compliance maturity level
    - Risk assessment
    """
    try:
        # Sanitize query parameters
        framework = SecurityValidator.validate_no_dangerous_content(framework, "framework")
        context_type = SecurityValidator.validate_no_dangerous_content(context_type, "context_type")

        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        recommendations = await assistant.get_context_aware_recommendations(
            user=current_user,
            business_profile_id=UUID(str(business_profile.id)),
            framework=framework,
            context_type=context_type,
        )

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting context-aware recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get context-aware recommendations")


@router.post("/evidence-collection-workflow", dependencies=[Depends(validate_request)])
async def generate_evidence_collection_workflow(
    framework: str = Query(..., min_length=1, description="Framework for workflow generation"),
    control_id: Optional[str] = Query(None, description="Specific control ID (optional)"),
    workflow_type: str = Query(default="comprehensive", description="Type of workflow"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate intelligent, step-by-step evidence collection workflows
    tailored to specific frameworks, controls, and business contexts.
    """
    try:
        # Sanitize query parameters
        framework = SecurityValidator.validate_no_dangerous_content(framework, "framework")
        workflow_type = SecurityValidator.validate_no_dangerous_content(
            workflow_type, "workflow_type"
        )
        if control_id:
            control_id = SecurityValidator.validate_no_dangerous_content(control_id, "control_id")

        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        workflow = await assistant.generate_evidence_collection_workflow(
            user=current_user,
            business_profile_id=UUID(str(business_profile.id)),
            framework=framework,
            control_id=control_id or "general",
            workflow_type=workflow_type,
        )

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating evidence collection workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate evidence collection workflow",
        )


async def generate_customized_policy(
    framework: str = Query(..., description="Framework for policy generation"),
    policy_type: str = Query(..., description="Type of policy to generate"),
    tone: str = Query(default="Professional", description="Policy tone"),
    detail_level: str = Query(default="Standard", description="Level of detail"),
    include_templates: bool = Query(default=True, description="Include implementation templates"),
    geographic_scope: str = Query(default="Single location", description="Geographic scope"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate AI-powered, customized compliance policies based on:
    - Business profile and industry specifics
    - Framework requirements
    - Organizational size and maturity
    - Industry best practices
    - Regulatory requirements
    """
    try:
        # Sanitize query parameters
        framework = SecurityValidator.validate_no_dangerous_content(framework, "framework")
        policy_type = SecurityValidator.validate_no_dangerous_content(policy_type, "policy_type")
        tone = SecurityValidator.validate_no_dangerous_content(tone, "tone")
        detail_level = SecurityValidator.validate_no_dangerous_content(detail_level, "detail_level")
        geographic_scope = SecurityValidator.validate_no_dangerous_content(
            geographic_scope, "geographic_scope"
        )

        business_profile = (
            db.query(BusinessProfile)
            .filter(BusinessProfile.user_id == str(str(current_user.id)))
            .first()
        )

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        customization_options = {
            "tone": tone,
            "detail_level": detail_level,
            "include_templates": include_templates,
            "geographic_scope": geographic_scope,
            "industry_focus": business_profile.industry,
        }

        assistant = ComplianceAssistant(db)
        policy = await assistant.generate_customized_policy(
            user=current_user,
            business_profile_id=business_profile.id,
            framework=framework,
            policy_type=policy_type,
            customization_options=customization_options,
        )

        return policy

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating customized policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate customized policy")


@router.get("/smart-guidance/{framework}", dependencies=[Depends(validate_request)])
async def get_smart_compliance_guidance(
    framework: str,
    guidance_type: str = Query(default="getting_started", description="Type of guidance needed"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get intelligent, context-aware compliance guidance based on:
    - Current compliance status
    - Business maturity level
    - Industry requirements
    - Best practices
    """
    try:
        # Sanitize path and query parameters
        framework = SecurityValidator.validate_no_dangerous_content(framework, "framework")
        guidance_type = SecurityValidator.validate_no_dangerous_content(
            guidance_type, "guidance_type"
        )

        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)

        # Get comprehensive analysis
        recommendations = await assistant.get_context_aware_recommendations(
            user=current_user,
            business_profile_id=business_profile.id,
            framework=framework,
            context_type="guidance",
        )

        # Get gap analysis
        gap_analysis = await assistant.analyze_evidence_gap(
            business_profile_id=business_profile.id,
            framework=framework,
        )

        # Combine into smart guidance
        guidance = {
            "framework": framework,
            "guidance_type": guidance_type,
            "current_status": {
                "completion_percentage": gap_analysis.get("completion_percentage", 0),
                "maturity_level": recommendations.get("business_context", {}).get(
                    "maturity_level",
                    "Basic",
                ),
                "critical_gaps_count": len(gap_analysis.get("critical_gaps", [])),
            },
            "personalized_roadmap": recommendations.get("recommendations", [])[:5],
            "next_immediate_steps": recommendations.get("next_steps", []),
            "effort_estimation": recommendations.get("estimated_effort", {}),
            "quick_wins": [
                rec
                for rec in recommendations.get("recommendations", [])
                if rec.get("effort_hours", 4) <= 2
            ][:3],
            "automation_opportunities": [
                rec
                for rec in recommendations.get("recommendations", [])
                if rec.get("automation_possible", False)
            ][:3],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return guidance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting smart compliance guidance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get smart compliance guidance")


@router.post("/smart-evidence/create-plan", dependencies=[Depends(validate_request)])
async def create_smart_evidence_plan(
    framework: str = Query(..., description="Compliance framework"),
    target_weeks: int = Query(default=12, description="Target completion weeks"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create an intelligent evidence collection plan with AI-driven prioritization.

    Features:
    - AI-powered task prioritization
    - Automation opportunity identification
    - Intelligent scheduling and resource allocation
    - Business context-aware planning
    """
    try:
        # Sanitize query parameters
        framework = SecurityValidator.validate_no_dangerous_content(framework, "framework")

        business_profile = (
            db.query(BusinessProfile)
            .filter(BusinessProfile.user_id == str(str(current_user.id)))
            .first()
        )

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        from services.ai.smart_evidence_collector import get_smart_evidence_collector

        # Get business context
        business_context = {
            "company_name": business_profile.company_name,
            "industry": business_profile.industry,
            "employee_count": business_profile.employee_count or 0,
            "description": business_profile.description,
        }

        # Get existing evidence (simplified - would integrate with actual evidence database)
        existing_evidence = []  # This would query the actual evidence database

        collector = await get_smart_evidence_collector()
        plan = await collector.create_collection_plan(
            business_profile_id=str(business_profile.id),
            framework=framework,
            business_context=business_context,
            existing_evidence=existing_evidence,
            target_completion_weeks=target_weeks,
        )

        return {
            "plan_id": plan.plan_id,
            "framework": plan.framework,
            "total_tasks": plan.total_tasks,
            "estimated_total_hours": plan.estimated_total_hours,
            "completion_target_date": plan.completion_target_date.isoformat(),
            "automation_opportunities": plan.automation_opportunities,
            "next_priority_tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "priority": task.priority.value,
                    "automation_level": task.automation_level.value,
                    "estimated_effort_hours": task.estimated_effort_hours,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                }
                for task in plan.tasks[:5]  # First 5 tasks
            ],
            "created_at": plan.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating smart evidence plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to create smart evidence plan")


@router.get("/smart-evidence/plan/{id}", dependencies=[Depends(validate_request)])
async def get_smart_evidence_plan(id: str, current_user: User = Depends(get_current_active_user)):
    """
    Get details of a smart evidence collection plan.
    """
    try:
        from services.ai.smart_evidence_collector import get_smart_evidence_collector

        collector = await get_smart_evidence_collector()
        plan = await collector.get_collection_plan(id)

        if not plan:
            raise HTTPException(status_code=404, detail="Collection plan not found")

        return {
            "plan_id": plan.plan_id,
            "framework": plan.framework,
            "total_tasks": plan.total_tasks,
            "estimated_total_hours": plan.estimated_total_hours,
            "completion_target_date": plan.completion_target_date.isoformat(),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "control_id": task.control_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority.value,
                    "automation_level": task.automation_level.value,
                    "estimated_effort_hours": task.estimated_effort_hours,
                    "status": task.status.value,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "automation_tools": task.metadata.get("automation_tools", []),
                }
                for task in plan.tasks
            ],
            "automation_opportunities": plan.automation_opportunities,
            "created_at": plan.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting smart evidence plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to get smart evidence plan")


@router.get("/smart-evidence/next-tasks/{id}", dependencies=[Depends(validate_request)])
async def get_next_priority_tasks(
    id: str,
    limit: int = Query(default=5, description="Number of tasks to return"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the next priority tasks for execution from a collection plan.
    """
    try:
        from services.ai.smart_evidence_collector import get_smart_evidence_collector

        collector = await get_smart_evidence_collector()
        tasks = await collector.get_next_priority_tasks(id, limit)

        return {
            "plan_id": id,
            "next_tasks": [
                {
                    "task_id": task.task_id,
                    "control_id": task.control_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority.value,
                    "automation_level": task.automation_level.value,
                    "estimated_effort_hours": task.estimated_effort_hours,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "automation_tools": task.metadata.get("automation_tools", []),
                    "success_rate": task.metadata.get("success_rate", 0.5),
                }
                for task in tasks
            ],
            "total_pending_tasks": len(tasks),
        }

    except Exception as e:
        logger.error(f"Error getting next priority tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get next priority tasks")


@router.post(
    "/smart-evidence/update-task/{plan_id}/{task_id}", dependencies=[Depends(validate_request)]
)
async def update_evidence_task_status(
    plan_id: str,
    task_id: str,
    status: str = Query(..., description="New task status"),
    completion_notes: Optional[str] = Query(None, description="Completion notes"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update the status of an evidence collection task.
    """
    try:
        from services.ai.smart_evidence_collector import (
            CollectionStatus,
            get_smart_evidence_collector,
        )

        # Validate status
        try:
            task_status = CollectionStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        collector = await get_smart_evidence_collector()
        success = await collector.update_task_status(
            plan_id,
            task_id,
            task_status,
            completion_notes,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Plan or task not found")

        return {
            "plan_id": plan_id,
            "task_id": task_id,
            "status": status,
            "completion_notes": completion_notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update task status")
