"""
import logging


logger = logging.getLogger(__name__)
FastAPI router for Freemium Assessment Strategy endpoints.

Implements the email-gated AI assessment funnel with 5 core endpoints:
1. POST /freemium/leads - Email capture and UTM tracking
2. POST /freemium/sessions - Start AI assessment session
3. GET /freemium/sessions/{token} - Get session progress
4. POST /freemium/sessions/{token}/answers - Submit answers
5. GET /freemium/sessions/{token}/results - Get assessment results

Following ruleIQ patterns: Rate limiting, RBAC middleware, field mappers, error handling.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel, EmailStr, Field
from api.dependencies.database import get_async_db
from api.middleware.rate_limiter import rate_limit
from database import AssessmentLead, FreemiumAssessmentSession
from services.freemium_assessment_service import FreemiumAssessmentService
from services.lead_scoring_service import LeadScoringService
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/freemium",
    tags=["Freemium Assessment"],
    responses={
        (429): {"description": "Rate limit exceeded"},
        (500): {"description": "Internal server error"},
    },
)


class LeadCaptureRequest(BaseModel):
    """Schema for email capture and lead generation."""

    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=200)
    company_size: Optional[str] = Field(None, pattern="^(1-10|11-50|51-200|201-500|500+)$")
    industry: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=200)
    utm_term: Optional[str] = Field(None, max_length=200)
    utm_content: Optional[str] = Field(None, max_length=200)
    referrer_url: Optional[str] = Field(None, max_length=500)
    landing_page: Optional[str] = Field(None, max_length=500)
    user_agent: Optional[str] = None
    marketing_consent: bool = Field(default=False)
    newsletter_subscribed: bool = Field(default=False)


class SessionStartRequest(BaseModel):
    """Schema for starting an assessment session."""

    lead_email: EmailStr
    business_type: str = Field(..., max_length=100)
    company_size: Optional[str] = Field(None, pattern="^(1-10|11-50|51-200|201-500|500+)$")
    assessment_type: str = Field(default="general", pattern="^(general|gdpr|security|compliance)$")
    industry_focus: Optional[str] = Field(None, max_length=100)
    compliance_frameworks: Optional[List[str]] = Field(default_factory=list)
    priority_areas: Optional[List[str]] = Field(default_factory=list)


class AnswerSubmissionRequest(BaseModel):
    """Schema for submitting assessment answers."""

    question_id: str
    answer: str
    answer_confidence: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    time_spent_seconds: Optional[int] = Field(None, ge=0)
    skip_reason: Optional[str] = Field(None, max_length=200)


class LeadResponse(BaseModel):
    """Response schema for lead capture."""

    lead_id: UUID
    email: str
    lead_score: int
    lead_status: str
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj) -> Any:
        """Custom from_orm to handle field mapping."""
        return cls(
            lead_id=obj.id,
            email=obj.email,
            lead_score=obj.lead_score,
            lead_status=obj.lead_status,
            created_at=obj.created_at,
        )


class SessionResponse(BaseModel):
    """Response schema for assessment sessions."""

    session_id: UUID
    session_token: str
    lead_id: UUID
    status: str
    progress_percentage: float
    current_question_id: Optional[str]
    current_question: Optional[Dict[str, Any]] = None
    total_questions: int
    questions_answered: int
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj) -> Any:
        """Custom from_orm to handle field mapping."""
        current_question = None
        if hasattr(obj, "ai_responses") and obj.ai_responses:
            if "questions" in obj.ai_responses:
                questions = obj.ai_responses.get("questions", [])
                if questions and obj.current_question_id:
                    for q in questions:
                        if q.get("question_id") == obj.current_question_id:
                            current_question = q
                            break
        return cls(
            session_id=obj.id,
            session_token=obj.session_token,
            lead_id=obj.lead_id,
            status=obj.status or "active",
            progress_percentage=obj.progress_percentage or 0.0,
            current_question_id=obj.current_question_id,
            current_question=current_question,
            total_questions=obj.total_questions or 0,
            questions_answered=obj.questions_answered or 0,
            expires_at=obj.expires_at,
            created_at=obj.created_at,
        )


class QuestionResponse(BaseModel):
    """Response schema for AI-generated questions."""

    question_id: str
    question_text: str
    question_type: str
    options: Optional[List[str]]
    context: Optional[str]
    category: str
    difficulty_level: int

    class Config:
        from_attributes = True


class AssessmentResultsResponse(BaseModel):
    """Response schema for assessment results."""

    session_id: UUID
    compliance_score: Optional[float]
    risk_level: str
    completed_at: Optional[datetime]
    risk_assessment: dict
    recommendations: List[dict]
    gaps_identified: List[dict]
    results_summary: str
    conversion_opportunities: List[dict]
    next_steps: List[str]

    class Config:
        from_attributes = True


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture lead and track UTM parameters",
    description="Email capture endpoint with UTM tracking for freemium funnel conversion analytics",
    dependencies=[Depends(rate_limit(requests_per_minute=20))],
)
async def capture_lead(
    request: Request, lead_data: LeadCaptureRequest, db: AsyncSession = Depends(get_async_db)
) -> LeadResponse:
    """
    Capture lead information and UTM parameters for freemium assessment funnel.

    Creates or updates an AssessmentLead record with:
    - Email validation and deduplication
    - UTM parameter tracking for attribution
    - Initial lead scoring (engagement = +10 points)
    - GDPR-compliant consent management
    """
    try:
        client_ip = request.client.host
        result = await db.execute(
            select(AssessmentLead).where(AssessmentLead.email == lead_data.email)
        )
        existing_lead = result.scalar_one_or_none()
        if existing_lead:
            logger.info("Updating existing lead: %s" % lead_data.email)
            for field, value in lead_data.dict(exclude_unset=True).items():
                if hasattr(existing_lead, field) and value is not None:
                    setattr(existing_lead, field, value)
            existing_lead.last_activity_at = datetime.now(timezone.utc)
            existing_lead.lead_score += 5
            await db.commit()
            await db.refresh(existing_lead)
            scoring_service = LeadScoringService(db)
            await scoring_service.track_event(
                lead_id=existing_lead.id,
                event_type="lead_return",
                event_category="engagement",
                event_action="returned_visitor",
                score_impact=5,
                metadata={"source": "freemium_capture"},
            )
            return LeadResponse.from_orm(existing_lead)
        else:
            logger.info("Creating new lead: %s" % lead_data.email)
            new_lead = AssessmentLead(
                **lead_data.dict(exclude_unset=True),
                ip_address=client_ip,
                lead_score=10,
                lead_status="new",
                last_activity_at=datetime.now(timezone.utc),
            )
            if lead_data.marketing_consent:
                new_lead.consent_date = datetime.now(timezone.utc)
            db.add(new_lead)
            await db.commit()
            await db.refresh(new_lead)
            scoring_service = LeadScoringService(db)
            await scoring_service.track_event(
                lead_id=new_lead.id,
                event_type="lead_capture",
                event_category="conversion",
                event_action="email_submitted",
                score_impact=10,
                metadata={
                    "utm_source": lead_data.utm_source,
                    "utm_campaign": lead_data.utm_campaign,
                    "consent_given": lead_data.marketing_consent,
                },
            )
            logger.info("New lead created successfully: %s" % new_lead.id)
            return LeadResponse.from_orm(new_lead)
    except Exception as e:
        logger.error("Error capturing lead %s: %s" % (lead_data.email, str(e)))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture lead information",
        )


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start AI assessment session",
    description="Initialize personalized AI assessment session with dynamic question generation",
    dependencies=[Depends(rate_limit(requests_per_minute=10))],
)
async def start_assessment_session(
    request: Request, session_data: SessionStartRequest, db: AsyncSession = Depends(get_async_db)
) -> SessionResponse:
    """
    Start a new freemium assessment session for a lead.

    Creates a FreemiumAssessmentSession with:
    - Secure session token generation
    - AI-driven question personalization
    - Progress tracking initialization
    - Lead scoring event tracking
    """
    try:
        result = await db.execute(
            select(AssessmentLead).where(AssessmentLead.email == session_data.lead_email)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found. Please capture lead information first.",
            )
        logger.info("Starting assessment session for lead: %s" % lead.id)
        assessment_service = await FreemiumAssessmentService.create(db)
        session = await assessment_service.create_session(
            lead_id=lead.id,
            business_type=session_data.business_type,
            company_size=session_data.company_size,
            assessment_type=session_data.assessment_type,
            personalization_data={
                "industry_focus": session_data.industry_focus,
                "compliance_frameworks": session_data.compliance_frameworks,
                "priority_areas": session_data.priority_areas,
            },
        )
        lead.last_activity_at = datetime.now(timezone.utc)
        lead.lead_score += 15
        await db.commit()
        scoring_service = LeadScoringService(db)
        await scoring_service.track_event(
            lead_id=lead.id,
            event_type="assessment_start",
            event_category="engagement",
            event_action="started_assessment",
            score_impact=15,
            session_id=str(session.id),
            metadata={
                "business_type": session_data.business_type,
                "assessment_type": session_data.assessment_type,
            },
        )
        logger.info("Assessment session created: %s" % session.id)
        return SessionResponse.from_orm(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error starting assessment session: %s" % str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start assessment session",
        )


@router.get(
    "/sessions/{token}",
    response_model=SessionResponse,
    summary="Get assessment session progress",
    description="Retrieve current session state, progress, and next question",
    dependencies=[Depends(rate_limit(requests_per_minute=30))],
)
async def get_session_progress(
    session_token: str, db: AsyncSession = Depends(get_async_db)
) -> SessionResponse:
    """
    Get current assessment session progress and state.

    Returns:
    - Session progress percentage
    - Current question information
    - Questions answered count
    - Session expiration status
    """
    try:
        result = await db.execute(
            select(FreemiumAssessmentSession).where(
                FreemiumAssessmentSession.session_token == session_token
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found"
            )
        if session.is_expired():
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Assessment session has expired"
            )
        logger.info("Retrieved session progress: %s" % session.id)
        return SessionResponse.from_orm(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving session %s: %s" % (session_token, str(e)))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session progress",
        )


@router.post(
    "/sessions/{token}/answers",
    response_model=dict,
    summary="Submit assessment answers",
    description="Submit answers and get next AI-generated question with scoring",
    dependencies=[Depends(rate_limit(requests_per_minute=25))],
)
async def submit_assessment_answer(
    session_token: str,
    answer_data: AnswerSubmissionRequest,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Submit an answer to the current assessment question.

    Processes:
    - Answer validation and storage
    - AI-driven question progression
    - Dynamic lead scoring based on responses
    - Next question generation
    """
    try:
        result = await db.execute(
            select(FreemiumAssessmentSession).where(
                FreemiumAssessmentSession.session_token == session_token
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found"
            )
        if session.is_expired():
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Assessment session has expired"
            )
        logger.info("Processing answer for session: %s" % session.id)
        assessment_service = await FreemiumAssessmentService.create(db)
        result = await assessment_service.process_answer(
            session_id=session.id,
            question_id=answer_data.question_id,
            answer=answer_data.answer,
            answer_confidence=answer_data.answer_confidence,
            time_spent_seconds=answer_data.time_spent_seconds,
        )
        score_impact = await assessment_service.calculate_answer_score_impact(
            question_id=answer_data.question_id,
            answer=answer_data.answer,
            confidence=answer_data.answer_confidence,
        )
        scoring_service = LeadScoringService(db)
        await scoring_service.track_event(
            lead_id=session.lead_id,
            event_type="question_answered",
            event_category="assessment",
            event_action="submitted_answer",
            score_impact=score_impact,
            session_id=str(session.id),
            metadata={
                "question_id": answer_data.question_id,
                "answer_length": len(str(answer_data.answer)),
                "time_spent_seconds": answer_data.time_spent_seconds,
                "confidence": answer_data.answer_confidence,
            },
        )
        logger.info("Answer processed successfully for session: %s" % session.id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing answer for session %s: %s" % (session_token, str(e)))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process assessment answer",
        )


@router.get(
    "/sessions/{token}/results",
    response_model=AssessmentResultsResponse,
    summary="Get AI assessment results",
    description="Generate comprehensive assessment results with AI insights and conversion opportunities",
    dependencies=[Depends(rate_limit(requests_per_minute=15))],
)
async def get_assessment_results(
    session_token: str, db: AsyncSession = Depends(get_async_db)
) -> AssessmentResultsResponse:
    """
    Generate and return comprehensive assessment results.

    Provides:
    - AI-generated compliance score and risk assessment
    - Personalized recommendations based on answers
    - Identified compliance gaps and priorities
    - Conversion opportunities and next steps
    """
    try:
        result = await db.execute(
            select(FreemiumAssessmentSession).where(
                FreemiumAssessmentSession.session_token == session_token
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found"
            )
        if session.is_expired():
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Assessment session has expired"
            )
        logger.info("Generating results for session: %s" % session.id)
        assessment_service = await FreemiumAssessmentService.create(db)
        results = await assessment_service.generate_results(session.id)
        if not session.results_viewed:
            session.results_viewed = True
            session.results_viewed_at = datetime.now(timezone.utc)
            await db.commit()
            scoring_service = LeadScoringService(db)
            await scoring_service.track_event(
                lead_id=session.lead_id,
                event_type="results_viewed",
                event_category="conversion",
                event_action="viewed_assessment_results",
                score_impact=25,
                session_id=str(session.id),
                metadata={
                    "completion_status": session.completion_status,
                    "questions_answered": session.questions_answered,
                    "compliance_score": results.get("compliance_score"),
                },
            )
            result = await db.execute(
                select(AssessmentLead).where(AssessmentLead.id == session.lead_id)
            )
            lead = result.scalar_one_or_none()
            if lead:
                lead.lead_score += 25
                lead.lead_status = "qualified"
                lead.last_activity_at = datetime.now(timezone.utc)
                await db.commit()
        logger.info("Results generated successfully for session: %s" % session.id)
        return AssessmentResultsResponse(**results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating results for session %s: %s" % (session_token, str(e)))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate assessment results",
        )


@router.get(
    "/health",
    summary="Freemium API health check",
    description="Check freemium API health and database connectivity",
)
async def health_check(db: AsyncSession = Depends(get_async_db)) -> dict:
    """Health check endpoint for freemium API router."""
    try:
        await db.execute(text("SELECT 1"))
        lead_result = await db.execute(select(func.count(AssessmentLead.id)))
        lead_count = lead_result.scalar()
        session_result = await db.execute(select(func.count(FreemiumAssessmentSession.id)))
        session_count = session_result.scalar()
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected",
            "leads_count": lead_count,
            "sessions_count": session_count,
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error("Health check failed: %s" % str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
