"""
AI Assessment Assistant API Router

Dedicated endpoints for AI-powered assessment features including:
- Question help and guidance
- Follow-up question generation
- Assessment analysis and insights
- Personalized recommendations
- Performance metrics and feedback
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies.auth import get_current_active_user
from database.user import User
from api.dependencies.database import get_async_db
from api.middleware.ai_rate_limiter import (
    ai_analysis_rate_limit,
    ai_followup_rate_limit,
    ai_help_rate_limit,
    ai_rate_limit_stats,
    ai_recommendations_rate_limit,
    get_ai_rate_limit_stats,
)
from core.exceptions import NotFoundException
from database.business_profile import BusinessProfile
from services.ai import ComplianceAssistant
from services.ai.exceptions import (
    AIServiceException,
    AIContentFilterException,
    AIModelException,
    AIParsingException,
    AIQuotaExceededException,
    AITimeoutException,
)

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["AI Assessment Assistant"])


# Request/Response Models
class AIHelpRequest(BaseModel):
    question_id: str
    question_text: str
    framework_id: str
    section_id: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None


class AIHelpResponse(BaseModel):
    guidance: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    related_topics: Optional[List[str]] = None
    follow_up_suggestions: Optional[List[str]] = None
    source_references: Optional[List[str]] = None
    request_id: str
    generated_at: str


class AIFollowUpRequest(BaseModel):
    framework_id: str
    current_answers: Dict[str, Any]
    business_context: Optional[Dict[str, Any]] = None
    max_questions: int = Field(default=3, ge=1, le=10)


class AIFollowUpQuestion(BaseModel):
    id: str
    text: str
    type: str
    options: Optional[List[Dict[str, str]]] = None
    reasoning: str
    priority: str


class AIFollowUpResponse(BaseModel):
    questions: List[AIFollowUpQuestion]
    total_generated: int
    request_id: str
    generated_at: str


class AIAnalysisRequest(BaseModel):
    assessment_results: Dict[str, Any]
    framework_id: str
    business_profile_id: str


class Gap(BaseModel):
    id: str
    section: str
    severity: str
    description: str
    impact: str
    current_state: str
    target_state: str


class Recommendation(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    effort_estimate: str
    impact_score: float
    resources: Optional[List[str]] = None
    implementation_steps: Optional[List[str]] = None


class AIAnalysisResponse(BaseModel):
    gaps: List[Gap]
    recommendations: List[Recommendation]
    risk_assessment: Dict[str, Any]
    compliance_insights: Dict[str, Any]
    evidence_requirements: List[Dict[str, Any]]
    request_id: str
    generated_at: str


class AIRecommendationRequest(BaseModel):
    gaps: List[Dict[str, Any]]
    business_profile: Dict[str, Any]
    existing_policies: Optional[List[str]] = None
    industry_context: Optional[str] = None
    timeline_preferences: Optional[str] = "standard"


class ImplementationPhase(BaseModel):
    phase_number: int
    phase_name: str
    duration_weeks: int
    tasks: List[str]
    dependencies: List[str]


class ImplementationPlan(BaseModel):
    phases: List[ImplementationPhase]
    total_timeline_weeks: int
    resource_requirements: List[str]


class AIRecommendationResponse(BaseModel):
    recommendations: List[Recommendation]
    implementation_plan: ImplementationPlan
    success_metrics: List[str]
    request_id: str
    generated_at: str


class AIFeedbackRequest(BaseModel):
    interaction_id: str
    helpful: bool
    rating: Optional[int] = Field(None, ge=1, le=5)
    comments: Optional[str] = None
    improvement_suggestions: Optional[List[str]] = None


class AIMetricsResponse(BaseModel):
    response_times: Dict[str, float]
    accuracy_score: float
    user_satisfaction: float
    total_interactions: int
    quota_usage: Dict[str, Any]


# Streaming Response Models
class StreamingChunk(BaseModel):
    """Individual chunk of streaming data."""

    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    content: str = Field(..., description="Text content of this chunk")
    chunk_type: str = Field(
        default="content", description="Type of chunk: content, metadata, complete"
    )
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class StreamingMetadata(BaseModel):
    """Metadata for streaming response."""

    request_id: str
    framework_id: str
    business_profile_id: str
    started_at: str
    stream_type: str  # "analysis", "recommendations", "help"


# Helper function to get business profile
async def get_user_business_profile(
    user: User, db: AsyncSession, business_profile_id: Optional[str] = None
) -> BusinessProfile:
    """Get business profile for the current user."""
    if business_profile_id:
        # Get specific business profile
        result = await db.execute(
            select(BusinessProfile).where(
                BusinessProfile["id"] == business_profile_id, BusinessProfile.user_id == str(user["id"])
            )
        )
        profile = result.scalars().first()
    else:
        # Get user's default business profile
        result = await db.execute(
            select(BusinessProfile).where(BusinessProfile.user_id == str(user["id"]))
        )
        profile = result.scalars().first()

    if not profile:
        raise NotFoundException("Business profile", business_profile_id or str(user["id"]))

    return profile


# AI Assessment Endpoints


@router.post("/{framework_id}/help", response_model=AIHelpResponse)
async def get_question_help(
    framework_id: str,
    request: AIHelpRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_help_rate_limit),
):
    """
    Get AI-powered help for a specific assessment question.

    Provides contextual guidance, related topics, and follow-up suggestions
    based on the question, framework, and user's business context.
    """
    try:
        # Get business profile for context
        profile = await get_user_business_profile(current_user, db)

        # Initialize AI assistant
        assistant = ComplianceAssistant(db)

        # Generate AI guidance using ComplianceAssistant (Phase 2.2 integration)
        guidance_response = await assistant.get_assessment_help(
            question_id=request.question_id,
            question_text=request.question_text,
            framework_id=framework_id,
            business_profile_id=UUID(str(profile.id)),
            section_id=request.section_id or "",
            user_context=request.user_context or {},
        )

        # Record request for statistics
        ai_rate_limit_stats.record_request("help", rate_limited=False)

        return AIHelpResponse(
            guidance=guidance_response["guidance"],
            confidence_score=guidance_response.get("confidence_score", 0.8),
            related_topics=guidance_response.get("related_topics", []),
            follow_up_suggestions=guidance_response.get("follow_up_suggestions", []),
            source_references=guidance_response.get("source_references", []),
            request_id=guidance_response.get(
                "request_id", f"help_{framework_id}_{request.question_id}"
            ),
            generated_at=guidance_response.get("generated_at", ""),
        )

    except NotFoundException as e:
        logger.warning(f"Business profile not found in question help: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AIContentFilterException as e:
        logger.warning(f"AI content filter triggered in question help: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content not appropriate for AI assistance: {e.filter_reason}",
        )
    except AIQuotaExceededException as e:
        logger.warning(f"AI quota exceeded in question help: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI service quota exceeded: {e.quota_type}",
        )
    except (AIModelException, AIParsingException) as e:
        logger.error(f"AI model/parsing error in question help: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service experiencing technical difficulties",
        )
    except AITimeoutException as e:
        logger.warning(f"AI timeout in question help: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service timeout - please try again",
        )
    except AIServiceException as e:
        logger.error(f"AI service error in question help: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI assistance temporarily unavailable: {e.message}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in question help: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to provide AI assistance at this time",
        )


@router.post("/{framework_id}/help/stream")
async def get_question_help_stream(
    framework_id: str,
    request: AIHelpRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_help_rate_limit),
):
    """
    Stream AI-powered help for a specific assessment question.

    Provides real-time streaming contextual guidance, related topics, and follow-up suggestions
    based on the question, framework, and user's business context.
    Returns Server-Sent Events (SSE) for real-time updates.
    """

    async def generate_help_stream():
        try:
            # Get business profile for context
            profile = await get_user_business_profile(current_user, db)

            # Initialize AI assistant
            assistant = ComplianceAssistant(db)

            # Create metadata chunk
            metadata = StreamingMetadata(
                request_id=f"help_{framework_id}_{request.question_id}_{datetime.utcnow().timestamp()}",
                framework_id=framework_id,
                business_profile_id=str(profile.id),
                started_at=datetime.utcnow().isoformat(),
                stream_type="help",
            )

            # Send metadata chunk
            metadata_chunk = StreamingChunk(
                chunk_id="metadata", content=metadata.model_dump_json(), chunk_type="metadata"
            )
            yield f"data: {metadata_chunk.model_dump_json()}\n\n"

            # Stream AI help using the streaming method
            chunk_counter = 0
            async for chunk_content in assistant.get_assessment_help_stream(
                question_id=request.question_id,
                question_text=request.question_text,
                framework_id=framework_id,
                business_profile_id=UUID(str(profile.id)),
                section_id=request.section_id or "",
                user_context=request.user_context or {},
            ):
                chunk_counter += 1
                chunk = StreamingChunk(
                    chunk_id=f"help_chunk_{chunk_counter}",
                    content=chunk_content,
                    chunk_type="content",
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

            # Send completion chunk
            completion_chunk = StreamingChunk(
                chunk_id="complete", content="Help guidance complete", chunk_type="complete"
            )
            yield f"data: {completion_chunk.model_dump_json()}\n\n"

        except AIServiceException as e:
            logger.error(f"AI service error in streaming question help: {e}")
            error_chunk = StreamingChunk(
                chunk_id="error", content=f"Unable to provide help: {e.message}", chunk_type="error"
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"Unexpected error in streaming question help: {e}")
            error_chunk = StreamingChunk(
                chunk_id="error",
                content="Unable to provide AI assistance at this time",
                chunk_type="error",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate_help_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/followup", response_model=AIFollowUpResponse)
async def generate_followup_questions(
    request: AIFollowUpRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_followup_rate_limit),
):
    """
    Generate AI-powered follow-up questions based on current assessment responses.

    Analyzes user's answers to suggest additional questions that could provide
    deeper insights into their compliance posture.
    """
    try:
        # Get business profile for context
        profile = await get_user_business_profile(current_user, db)

        # Initialize AI assistant
        assistant = ComplianceAssistant(db)

        # Generate follow-up questions using ComplianceAssistant (Phase 2.2 integration)
        followup_response = await assistant.generate_assessment_followup(
            current_answers=request.current_answers,
            framework_id=request.framework_id,
            business_profile_id=UUID(str(profile.id)),
            assessment_context=request.business_context or {},
        )

        # Convert to response format
        questions = [
            AIFollowUpQuestion(
                id=q["id"],
                text=q["text"],
                type=q["type"],
                options=q.get("options"),
                reasoning=q["reasoning"],
                priority=q["priority"],
            )
            for q in followup_response["questions"]
        ]

        # Record request for statistics
        ai_rate_limit_stats.record_request("followup", rate_limited=False)

        return AIFollowUpResponse(
            questions=questions,
            total_generated=len(questions),
            request_id=followup_response.get("request_id", f"followup_{request.framework_id}"),
            generated_at=followup_response.get("generated_at", ""),
        )

    except NotFoundException as e:
        logger.warning(f"Business profile not found in followup generation: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AIContentFilterException as e:
        logger.warning(f"AI content filter triggered in followup generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content not appropriate for AI assistance: {e.filter_reason}",
        )
    except AIQuotaExceededException as e:
        logger.warning(f"AI quota exceeded in followup generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI service quota exceeded: {e.quota_type}",
        )
    except (AIModelException, AIParsingException) as e:
        logger.error(f"AI model/parsing error in followup generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service experiencing technical difficulties",
        )
    except AITimeoutException as e:
        logger.warning(f"AI timeout in followup generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service timeout - please try again",
        )
    except AIServiceException as e:
        logger.error(f"AI service error in follow-up generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to generate follow-up questions: {e.message}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in follow-up generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate follow-up questions at this time",
        )
    except Exception as e:
        logger.error(f"Unexpected error in follow-up generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate follow-up questions at this time",
        )


@router.post("/analysis", response_model=AIAnalysisResponse)
async def analyze_assessment_results(
    request: AIAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_analysis_rate_limit),
):
    """
    Perform comprehensive AI analysis of assessment results.

    Analyzes completed assessment to identify gaps, risks, and provide
    detailed compliance insights with evidence requirements.
    """
    try:
        # Get business profile
        profile = await get_user_business_profile(current_user, db, request.business_profile_id)

        # Initialize AI assistant
        assistant = ComplianceAssistant(db)

        # Perform comprehensive analysis using ComplianceAssistant (Phase 2.2 integration)
        analysis_response = await assistant.analyze_assessment_results(
            assessment_results=request.assessment_results,
            framework_id=request.framework_id,
            business_profile_id=UUID(str(profile.id)),
        )

        # Convert gaps to response format
        gaps = [
            Gap(
                id=gap["id"],
                section=gap["section"],
                severity=gap["severity"],
                description=gap["description"],
                impact=gap["impact"],
                current_state=gap["current_state"],
                target_state=gap["target_state"],
            )
            for gap in analysis_response["gaps"]
        ]

        # Convert recommendations to response format
        recommendations = [
            Recommendation(
                id=rec["id"],
                title=rec["title"],
                description=rec["description"],
                priority=rec["priority"],
                effort_estimate=rec["effort_estimate"],
                impact_score=rec["impact_score"],
                resources=rec.get("resources"),
                implementation_steps=rec.get("implementation_steps"),
            )
            for rec in analysis_response["recommendations"]
        ]

        return AIAnalysisResponse(
            gaps=gaps,
            recommendations=recommendations,
            risk_assessment=analysis_response["risk_assessment"],
            compliance_insights=analysis_response["compliance_insights"],
            evidence_requirements=analysis_response["evidence_requirements"],
            request_id=analysis_response.get("request_id", f"analysis_{request.framework_id}"),
            generated_at=analysis_response.get("generated_at", ""),
        )

    except NotFoundException as e:
        logger.warning(f"Business profile not found in assessment analysis: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AIServiceException as e:
        logger.error(f"AI service error in assessment analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to analyze assessment: {e.message}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in assessment analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to analyze assessment results at this time",
        )


@router.post("/analysis/stream")
async def analyze_assessment_results_stream(
    request: AIAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_analysis_rate_limit),
):
    """
    Stream comprehensive AI analysis of assessment results.

    Provides real-time streaming analysis of completed assessment to identify
    gaps, risks, and provide detailed compliance insights with evidence requirements.
    Returns Server-Sent Events (SSE) for real-time updates.
    """

    async def generate_analysis_stream():
        try:
            # Get business profile
            profile = await get_user_business_profile(current_user, db, request.business_profile_id)

            # Initialize AI assistant
            assistant = ComplianceAssistant(db)

            # Create metadata chunk
            metadata = StreamingMetadata(
                request_id=f"analysis_{request.framework_id}_{datetime.utcnow().timestamp()}",
                framework_id=request.framework_id,
                business_profile_id=str(profile.id),
                started_at=datetime.utcnow().isoformat(),
                stream_type="analysis",
            )

            # Send metadata chunk
            metadata_chunk = StreamingChunk(
                chunk_id="metadata", content=metadata.model_dump_json(), chunk_type="metadata"
            )
            yield f"data: {metadata_chunk.model_dump_json()}\n\n"

            # Stream AI analysis using the new streaming method
            chunk_counter = 0
            async for chunk_content in assistant.analyze_assessment_results_stream(
                assessment_responses=request.assessment_results,
                framework_id=request.framework_id,
                business_profile_id=UUID(str(profile.id)),
            ):
                chunk_counter += 1
                chunk = StreamingChunk(
                    chunk_id=f"analysis_chunk_{chunk_counter}",
                    content=chunk_content,
                    chunk_type="content",
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

            # Send completion chunk
            completion_chunk = StreamingChunk(
                chunk_id="complete", content="Analysis complete", chunk_type="complete"
            )
            yield f"data: {completion_chunk.model_dump_json()}\n\n"

        except AIServiceException as e:
            logger.error(f"AI service error in streaming assessment analysis: {e}")
            error_chunk = StreamingChunk(
                chunk_id="error",
                content=f"Unable to analyze assessment: {e.message}",
                chunk_type="error",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"Unexpected error in streaming assessment analysis: {e}")
            error_chunk = StreamingChunk(
                chunk_id="error",
                content="Unable to analyze assessment results at this time",
                chunk_type="error",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate_analysis_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/recommendations", response_model=AIRecommendationResponse)
async def generate_personalized_recommendations(
    request: AIRecommendationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_recommendations_rate_limit),
):
    """
    Generate personalized compliance recommendations with implementation plans.

    Creates detailed, actionable recommendations based on identified gaps,
    business context, and timeline preferences.
    """
    try:
        # Initialize AI assistant
        assistant = ComplianceAssistant(db)

        # Generate personalized recommendations using ComplianceAssistant (Phase 2.2 integration)
        rec_response = await assistant.get_assessment_recommendations(
            gaps=request.gaps,
            business_profile=request.business_profile,
            framework_id="general",  # Extract from request if available
            existing_policies=request.existing_policies or [],
            industry_context=request.industry_context or "",
            timeline_preferences=request.timeline_preferences or "standard",
        )

        # Convert recommendations
        recommendations = [
            Recommendation(
                id=rec["id"],
                title=rec["title"],
                description=rec["description"],
                priority=rec["priority"],
                effort_estimate=rec["effort_estimate"],
                impact_score=rec["impact_score"],
                resources=rec.get("resources"),
                implementation_steps=rec.get("implementation_steps"),
            )
            for rec in rec_response["recommendations"]
        ]

        # Convert implementation plan
        phases = [
            ImplementationPhase(
                phase_number=phase["phase_number"],
                phase_name=phase["phase_name"],
                duration_weeks=phase["duration_weeks"],
                tasks=phase["tasks"],
                dependencies=phase["dependencies"],
            )
            for phase in rec_response["implementation_plan"]["phases"]
        ]

        implementation_plan = ImplementationPlan(
            phases=phases,
            total_timeline_weeks=rec_response["implementation_plan"]["total_timeline_weeks"],
            resource_requirements=rec_response["implementation_plan"]["resource_requirements"],
        )

        return AIRecommendationResponse(
            recommendations=recommendations,
            implementation_plan=implementation_plan,
            success_metrics=rec_response["success_metrics"],
            request_id=rec_response.get("request_id", f"recommendations_{current_user.id}"),
            generated_at=rec_response.get("generated_at", ""),
        )

    except AIServiceException as e:
        logger.error(f"AI service error in recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to generate recommendations: {e.message}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate recommendations at this time",
        )


@router.post("/recommendations/stream")
async def generate_personalized_recommendations_stream(
    request: AIRecommendationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(ai_recommendations_rate_limit),
):
    """
    Stream personalized AI recommendations based on assessment gaps.

    Provides real-time streaming recommendations based on identified compliance gaps.
    Returns Server-Sent Events (SSE) for real-time updates including implementation
    steps and prioritized action items.
    """

    async def generate_recommendations_stream():
        try:
            # Get business profile
            profile = await get_user_business_profile(
                current_user, db, getattr(request, "business_profile_id", None)
            )

            # Initialize AI assistant
            assistant = ComplianceAssistant(db)

            # Create metadata chunk
            metadata = StreamingMetadata(
                request_id=f"recommendations_{datetime.utcnow().timestamp()}",
                framework_id=getattr(request, "framework_id", "unknown"),
                business_profile_id=str(profile.id),
                started_at=datetime.utcnow().isoformat(),
                stream_type="recommendations",
            )

            # Send metadata chunk
            metadata_chunk = StreamingChunk(
                chunk_id="metadata", content=metadata.model_dump_json(), chunk_type="metadata"
            )
            yield f"data: {metadata_chunk.model_dump_json()}\n\n"

            # Stream AI recommendations using the new streaming method
            chunk_counter = 0
            async for chunk_content in assistant.get_assessment_recommendations_stream(
                assessment_gaps=request.gaps,
                framework_id=getattr(request, "framework_id", "unknown"),
                business_profile_id=UUID(str(profile.id)),
                priority_level="high",
            ):
                chunk_counter += 1
                chunk = StreamingChunk(
                    chunk_id=f"recommendations_chunk_{chunk_counter}",
                    content=chunk_content,
                    chunk_type="content",
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

            # Send completion chunk
            completion_chunk = StreamingChunk(
                chunk_id="complete", content="Recommendations complete", chunk_type="complete"
            )
            yield f"data: {completion_chunk.model_dump_json()}\n\n"

        except AIServiceException as e:
            logger.error(f"AI service error in streaming recommendations: {e}")
            error_chunk = StreamingChunk(
                chunk_id="error",
                content=f"Unable to generate recommendations: {e.message}",
                chunk_type="error",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"Unexpected error in streaming recommendations: {e}")
            error_chunk = StreamingChunk(
                chunk_id="error",
                content="Unable to generate recommendations at this time",
                chunk_type="error",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        generate_recommendations_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/feedback")
async def submit_ai_feedback(
    request: AIFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Submit feedback on AI assistance quality.

    Collects user feedback to improve AI performance and track satisfaction metrics.
    """
    try:
        # Log feedback for analytics
        logger.info(
            f"AI feedback received from user {current_user.id}: "
            f"helpful={request.helpful}, rating={request.rating}"
        )

        # In a full implementation, you would:
        # 1. Store feedback in database
        # 2. Update AI performance metrics
        # 3. Trigger model retraining if needed

        return {"message": "Feedback submitted successfully", "status": "received"}

    except Exception as e:
        logger.error(f"Error submitting AI feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to submit feedback at this time",
        )


@router.get("/metrics", response_model=AIMetricsResponse)
async def get_ai_metrics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to include in metrics"),
):
    """
    Get AI performance metrics for admin users.

    Returns response times, accuracy scores, user satisfaction, and quota usage.
    """
    try:
        # Check if user has admin permissions (implement based on your auth system)
        # if not current_user.is_admin:
        #     raise HTTPException(status_code=403, detail="Admin access required")

        # Mock metrics - in production, fetch from analytics database
        metrics = {
            "response_times": {"avg": 1.2, "p95": 3.5, "p99": 8.1},
            "accuracy_score": 0.87,
            "user_satisfaction": 4.2,
            "total_interactions": 1247,
            "quota_usage": {
                "requests_used": 8432,
                "requests_limit": 10000,
                "tokens_used": 245678,
                "tokens_limit": 500000,
                "cost_usd": 12.34,
            },
        }

        return AIMetricsResponse(**metrics)

    except Exception as e:
        logger.error(f"Error retrieving AI metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve AI metrics at this time",
        )


@router.get("/rate-limit-stats")
async def get_rate_limit_statistics(current_user: User = Depends(get_current_active_user)):
    """
    Get AI rate limiting statistics.

    Returns current rate limiting statistics including total requests,
    rate limited requests, and per-operation breakdowns.
    """
    try:
        stats = get_ai_rate_limit_stats()

        return {
            "rate_limit_stats": stats,
            "current_limits": {
                "ai_help": "10 requests/minute",
                "ai_followup": "5 requests/minute",
                "ai_analysis": "3 requests/minute",
                "ai_recommendations": "3 requests/minute",
            },
            "burst_allowances": {
                "ai_help": 2,
                "ai_followup": 1,
                "ai_analysis": 1,
                "ai_recommendations": 1,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving rate limit stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rate limit statistics",
        )


# Helper methods for AI service integration
async def _get_mock_guidance_response(question_text: str, framework: str) -> Dict[str, Any]:
    """Mock AI guidance response - replace with actual AI service call"""
    return {
        "guidance": (
            f"For the question '{question_text}' in {framework}, consider implementing "
            "proper documentation and regular reviews. Ensure you have clear policies in place "
            "and that all stakeholders understand their responsibilities."
        ),
        "confidence_score": 0.85,
        "related_topics": ["Documentation", "Policy Management", "Stakeholder Training"],
        "follow_up_suggestions": [
            "Do you have documented procedures for this process?",
            "How often do you review and update these policies?",
            "Who is responsible for ensuring compliance in this area?",
        ],
        "source_references": [f"{framework} Article 5", "Best Practice Guidelines"],
        "request_id": f"help_{framework}_{hash(question_text) % 10000}",
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _get_mock_help_response(question_text: str, framework: str) -> Dict[str, Any]:
    """Mock AI help response for fallback scenarios"""
    return {
        "guidance": (
            f"For the question '{question_text}' in {framework}, please refer to the "
            "official documentation or consult with a compliance expert. This question "
            "requires careful consideration of your business context."
        ),
        "confidence_score": 0.5,
        "related_topics": [framework, "compliance guidance"],
        "follow_up_suggestions": ["Review framework documentation", "Consult compliance expert"],
        "source_references": [f"{framework} official documentation"],
        "request_id": f"mock_help_{framework}_{hash(question_text) % 10000}",
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _get_mock_followup_response(framework: str, answers: Dict[str, Any]) -> Dict[str, Any]:
    """Mock follow-up questions response - replace with actual AI service call"""
    return {
        "questions": [
            {
                "id": f"followup_{framework}_1",
                "text": (
                    "Based on your previous answers, do you have automated monitoring "
                    "in place for data processing activities?"
                ),
                "type": "radio",
                "options": [
                    {"value": "yes", "label": "Yes, fully automated"},
                    {"value": "partial", "label": "Partially automated"},
                    {"value": "no", "label": "No automation"},
                ],
                "reasoning": "Your responses indicate potential gaps in monitoring capabilities",
                "priority": "high",
            }
        ],
        "request_id": f"followup_{framework}_{hash(str(answers)) % 10000}",
        "generated_at": datetime.utcnow().isoformat(),
    }


# AI Health and Circuit Breaker Endpoints


@router.get("/health")
async def get_ai_service_health(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Get comprehensive AI service health status including circuit breaker states.
    """
    try:
        assistant = ComplianceAssistant(db)

        # Get circuit breaker status
        circuit_status = assistant.circuit_breaker.get_health_status()

        # Get overall health
        health_status = {
            "service_status": "healthy"
            if circuit_status["overall_state"] == "CLOSED"
            else "degraded",
            "circuit_breaker": circuit_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_percentage": 99.5,  # Mock - calculate from actual metrics
            "last_incident": None,
        }

        return {"status": "success", "data": health_status}

    except Exception as e:
        logger.error(f"Error getting AI service health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI service health",
        )


# REMOVED: Duplicate endpoint
# REMOVED: Duplicate endpoint
# # @router.get("/circuit-breaker/status")
# # async def get_circuit_breaker_status(
# #     current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
# # ) -> Dict[str, Any]:
# #     """
# #     Get detailed circuit breaker status for all AI models.
# #     """
# #     try:
# #         assistant = ComplianceAssistant(db)
# #         circuit_status = assistant.circuit_breaker.get_health_status()
# #
#

        return {
            "status": "success",
            "data": circuit_status,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve circuit breaker status",
        )


# REMOVED: Duplicate endpoint
# REMOVED: Duplicate endpoint
# # @router.post("/circuit-breaker/reset")
# # async def reset_circuit_breaker(
# #     model_name: str = Query(..., description="Model name to reset circuit breaker for"),
# #     current_user: User = Depends(get_current_active_user),
# #     db: AsyncSession = Depends(get_async_db),
# # ) -> Dict[str, Any]:
# #     """
# #     Manually reset circuit breaker for a specific model.
# #     """
# #     try:
# #         assistant = ComplianceAssistant(db)
# #         assistant.circuit_breaker.reset_circuit(model_name)
# #
#

        return {
            "status": "success",
            "message": f"Circuit breaker reset for model: {model_name}",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error resetting circuit breaker: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset circuit breaker",
        )


@router.get("/models/{model_name}/health")
async def get_model_health(
    model_name: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """
    Get health status for a specific AI model.
    """
    try:
        assistant = ComplianceAssistant(db)

        # Check if model is available
        is_available = assistant.circuit_breaker.is_model_available(model_name)
        model_state = assistant.circuit_breaker.get_model_state(model_name)

        health_data = {
            "model_name": model_name,
            "healthy": is_available,
            "circuit_state": model_state.value if model_state else "UNKNOWN",
            "last_check": datetime.utcnow().isoformat(),
        }

        return {"status": "success", "data": health_data}

    except Exception as e:
        logger.error(f"Error getting model health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model health",
        )


async def _get_mock_analysis_response(
    framework: str, assessment_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Mock analysis response - replace with actual AI service call"""
    return {
        "gaps": [
            {
                "id": "gap_1",
                "section": "Data Retention",
                "severity": "high",
                "description": "No documented data retention policy found",
                "impact": "Potential compliance violations and legal risks",
                "current_state": "Ad-hoc data deletion",
                "target_state": "Formal retention policy with automated enforcement",
            }
        ],
        "recommendations": [
            {
                "id": "rec_1",
                "title": "Implement Data Retention Policy",
                "description": "Create and implement a comprehensive data retention policy",
                "priority": "high",
                "effort_estimate": "2-4 weeks",
                "impact_score": 8.5,
                "resources": ["DPO", "Legal Team", "IT Team"],
                "implementation_steps": [
                    "Audit current data storage practices",
                    "Define retention periods by data category",
                    "Implement automated deletion systems",
                ],
            }
        ],
        "risk_assessment": {
            "overall_risk_level": "medium",
            "risk_score": 6.5,
            "key_risk_areas": ["Data Retention", "Access Controls", "Documentation"],
        },
        "compliance_insights": {
            "maturity_level": "Developing",
            "score_breakdown": {"Data Processing": 75, "Subject Rights": 82},
            "improvement_priority": ["Data Retention", "Security Controls"],
        },
        "evidence_requirements": [
            {
                "priority": "high",
                "evidence_type": "Policy Documentation",
                "description": "Documented data retention policy",
                "control_mapping": ["GDPR Article 5"],
            }
        ],
        "request_id": f"analysis_{framework}_{hash(str(assessment_results)) % 10000}",
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _get_mock_recommendations_response(gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mock recommendations response - replace with actual AI service call"""
    return {
        "recommendations": [
            {
                "id": "rec_1",
                "title": "Implement Data Retention Policy",
                "description": (
                    "Create comprehensive data retention policy with automated enforcement"
                ),
                "priority": "high",
                "effort_estimate": "2-4 weeks",
                "impact_score": 8.5,
                "resources": ["DPO", "Legal Team"],
                "implementation_steps": [
                    "Audit current data storage",
                    "Define retention periods",
                    "Implement automation",
                ],
            }
        ],
        "implementation_plan": {
            "phases": [
                {
                    "phase_number": 1,
                    "phase_name": "Foundation & Documentation",
                    "duration_weeks": 4,
                    "tasks": ["Document current practices", "Create policy", "Get approval"],
                    "dependencies": [],
                }
            ],
            "total_timeline_weeks": 10,
            "resource_requirements": ["DPO (0.5 FTE)", "Legal Counsel"],
        },
        "success_metrics": [
            "100% of data categories have documented retention periods",
            "Automated deletion operational for 80% of data types",
        ],
        "request_id": f"recommendations_{hash(str(gaps)) % 10000}",
        "generated_at": datetime.utcnow().isoformat(),
    }


# REMOVED: Duplicate endpoint
# REMOVED: Duplicate endpoint
# # @router.get("/cache/metrics")
# # async def get_ai_cache_metrics(
# #     current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
# # ) -> Dict[str, Any]:
# #     """
# #     Get AI caching performance metrics and status.
# #
#

    Returns:
        Cache performance metrics including hit rates, cost savings, and status
    """
    try:
        # Initialize AI assistant to access cache managers
        assistant = ComplianceAssistant(db)

        # Get both legacy cache and Google cached content metrics
        metrics = {}

        # Google Cached Content metrics with strategy optimization
        try:
            cached_content_manager = await assistant._get_cached_content_manager()
            google_cache_metrics = cached_content_manager.get_cache_metrics()

            # Add cache strategy optimization metrics
            strategy_metrics = cached_content_manager.get_cache_strategy_metrics()
            google_cache_metrics["strategy_optimization"] = strategy_metrics

            metrics["google_cached_content"] = google_cache_metrics
        except Exception as e:
            logger.warning(f"Failed to get Google cached content metrics: {e}")
            metrics["google_cached_content"] = {"error": "Metrics unavailable"}

        # Legacy AI cache metrics (if still in use)
        try:
            from services.ai.response_cache import get_ai_cache

            ai_cache = await get_ai_cache()
            legacy_cache_metrics = await ai_cache.get_cache_metrics()
            metrics["legacy_cache"] = legacy_cache_metrics
        except Exception as e:
            logger.warning(f"Failed to get legacy cache metrics: {e}")
            metrics["legacy_cache"] = {"error": "Metrics unavailable"}

        # Overall cache status
        metrics["cache_status"] = {
            "google_cached_content_enabled": "google_cached_content" in metrics
            and "error" not in metrics["google_cached_content"],
            "legacy_cache_enabled": "legacy_cache" in metrics
            and "error" not in metrics["legacy_cache"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Calculate combined hit rate if both caches are available
        if (
            metrics["cache_status"]["google_cached_content_enabled"]
            and metrics["cache_status"]["legacy_cache_enabled"]
        ):
            google_hits = metrics["google_cached_content"].get("cache_hits", 0)
            google_total = metrics["google_cached_content"].get("total_requests", 0)
            legacy_hits = metrics["legacy_cache"].get("total_hits", 0)
            legacy_total = metrics["legacy_cache"].get("total_requests", 0)

            total_hits = google_hits + legacy_hits
            total_requests = google_total + legacy_total

            if total_requests > 0:
                metrics["combined_hit_rate"] = round(total_hits / total_requests * 100, 2)
            else:
                metrics["combined_hit_rate"] = 0.0

        return {
            "cache_metrics": metrics,
            "request_id": f"cache_metrics_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving cache metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve cache metrics",
        )
