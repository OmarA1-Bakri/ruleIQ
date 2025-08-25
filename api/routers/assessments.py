from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_async_db
from api.dependencies.rbac_auth import (
    UserWithRoles,
    require_permission
)
from api.schemas.models import (
    AssessmentQuestion,
    AssessmentResponseUpdate,
    AssessmentSessionCreate,
    AssessmentSessionResponse,
)
from services.assessment_service import AssessmentService


class QuickAssessmentRequest(BaseModel):
    business_profile_id: str
    assessment_type: str
    industry_standard: bool


class FrameworkInfo(BaseModel):
    name: str
    description: str = ""


class QuickRecommendation(BaseModel):
    framework: FrameworkInfo
    priority: str = "medium"
    description: str = ""


class QuickAssessmentResponse(BaseModel):
    recommendations: List[QuickRecommendation]


router = APIRouter()


@router.post("/quick", response_model=QuickAssessmentResponse)
async def quick_assessment(
    request: QuickAssessmentRequest,
    current_user: UserWithRoles = Depends(require_permission("assessment_create"))
):
    """Generate quick compliance recommendations based on business profile."""

    # For now, return basic recommendations based on industry standards
    # This would typically integrate with the assessment service for more sophisticated analysis
    recommendations = []

    # Always recommend GDPR for EU businesses or those handling EU data
    recommendations.append(
        QuickRecommendation(
            framework=FrameworkInfo(
                name="GDPR (General Data Protection Regulation)",
                description="EU data protection regulation",
            ),
            priority="high",
            description="Essential for businesses handling personal data of EU residents",
        )
    )

    # Add industry-specific recommendations
    if request.industry_standard:
        recommendations.append(
            QuickRecommendation(
                framework=FrameworkInfo(
                    name="ISO 27001", description="Information security management standard"
                ),
                priority="medium",
                description="Industry standard for information security management",
            )
        )

        recommendations.append(
            QuickRecommendation(
                framework=FrameworkInfo(
                    name="SOC 2", description="Security and availability controls"
                ),
                priority="medium",
                description="Important for service organizations handling customer data",
            )
        )

    return QuickAssessmentResponse(recommendations=recommendations)


@router.get("/", response_model=List[AssessmentSessionResponse])
async def list_assessments(
    current_user: UserWithRoles = Depends(require_permission("assessment_list")),
    db: AsyncSession = Depends(get_async_db)
):
    """List all assessment sessions for the current user"""
    assessment_service = AssessmentService()
    sessions = await assessment_service.get_user_assessment_sessions(db, current_user)
    return sessions


@router.post("/", response_model=AssessmentSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    session_data: AssessmentSessionCreate,
    current_user: UserWithRoles = Depends(require_permission("assessment_create")),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new assessment session - alias for /start endpoint for compatibility"""
    assessment_service = AssessmentService()
    session = await assessment_service.start_assessment_session(
        db, current_user, session_data.session_type, session_data.business_profile_id
    )
    return session


@router.post(
    "/start", response_model=AssessmentSessionResponse, status_code=status.HTTP_201_CREATED
)
async def start_assessment(
    session_data: AssessmentSessionCreate,
    current_user: UserWithRoles = Depends(require_permission("assessment_create")),
    db: AsyncSession = Depends(get_async_db),
):
    assessment_service = AssessmentService()
    session = await assessment_service.start_assessment_session(
        db, current_user, session_data.session_type, session_data.business_profile_id
    )
    return session


@router.get("/current", response_model=AssessmentSessionResponse)
async def get_current_session(
    current_user: UserWithRoles = Depends(require_permission("assessment_list")),
    db: AsyncSession = Depends(get_async_db)
):
    assessment_service = AssessmentService()
    session = await assessment_service.get_current_assessment_session(db, current_user)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active assessment session"
        )
    return session


@router.get("/questions/{stage}", response_model=List[AssessmentQuestion])
async def get_questions(
    stage: int,
    current_user: UserWithRoles = Depends(require_permission("assessment_list"))
):
    assessment_service = AssessmentService()
    questions = assessment_service.get_assessment_questions(current_user, stage)
    return questions


@router.put("/{id}/response")
async def update_response(
    session_id: UUID,
    response_data: AssessmentResponseUpdate,
    current_user: UserWithRoles = Depends(require_permission("assessment_update")),
    db: AsyncSession = Depends(get_async_db),
):
    assessment_service = AssessmentService()
    session = await assessment_service.update_assessment_response(
        db, current_user, session_id, response_data.question_id, response_data.response
    )
    return session


@router.post("/{id}/responses")
async def update_responses(
    session_id: UUID,
    response_data: dict,
    current_user: UserWithRoles = Depends(require_permission("assessment_update")),
    db: AsyncSession = Depends(get_async_db),
):
    """Update assessment responses - alias for compatibility"""
    assessment_service = AssessmentService()
    # Extract question_id and response from the request data
    question_id = response_data.get("question_id")
    response = response_data.get("response")

    if not question_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="question_id is required"
        )

    session = await assessment_service.update_assessment_response(
        db, current_user, session_id, question_id, response
    )
    return session


@router.get("/{id}", response_model=AssessmentSessionResponse)
async def get_assessment_session(
    session_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("assessment_list")),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific assessment session by ID."""
    assessment_service = AssessmentService()
    session = await assessment_service.get_assessment_session(db, current_user, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found"
        )
    return session


@router.get("/{id}/recommendations")
async def get_assessment_recommendations(
    session_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("assessment_list")),
    db: AsyncSession = Depends(get_async_db),
):
    """Get recommendations for an assessment session."""
    from sqlalchemy import select

    from database.compliance_framework import ComplianceFramework

    assessment_service = AssessmentService()
    session = await assessment_service.get_assessment_session(db, current_user, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found"
        )

    # Get actual frameworks from database
    frameworks_result = await db.execute(
        select(ComplianceFramework).where(ComplianceFramework.is_active)
    )
    frameworks = frameworks_result.scalars().all()

    # Return recommendations from the session or generate basic ones with proper structure
    if session.recommendations:
        recommendations = session.recommendations
    else:
        recommendations = []
        for framework in frameworks:
            if "GDPR" in framework.name or "ISO" in framework.name:
                priority = "High" if "GDPR" in framework.name else "Medium"
                recommendations.append(
                    {
                        "framework": {
                            "id": str(framework.id),
                            "name": framework.name,
                            "description": framework.description,
                        },
                        "priority": priority,
                        "description": "Recommended based on your business profile",
                    }
                )

    return {"recommendations": recommendations}


@router.post("/{id}/complete", response_model=AssessmentSessionResponse)
async def complete_assessment(
    session_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("assessment_update")),
    db: AsyncSession = Depends(get_async_db),
):
    assessment_service = AssessmentService()
    session = await assessment_service.complete_assessment_session(db, current_user, session_id)
    return session
