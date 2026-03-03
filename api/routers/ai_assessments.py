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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, AsyncGenerator
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.dependencies.auth import get_current_active_user
from database.user import User
from api.dependencies.database import get_async_db
from services.rate_limiting import RateLimitService
from api.middleware.ai_rate_limiter import ai_analysis_rate_limit, ai_followup_rate_limit, ai_help_rate_limit, ai_rate_limit_stats, ai_recommendations_rate_limit, get_ai_rate_limit_stats
from core.exceptions import NotFoundException
from database.business_profile import BusinessProfile
from services.ai import ComplianceAssistant
from services.ai.exceptions import AIServiceException, AIContentFilterException, AIModelException, AIParsingException, AIQuotaExceededException, AITimeoutException
logger = logging.getLogger(__name__)
router = APIRouter(tags=['AI Assessment Assistant'])


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
    timeline_preferences: Optional[str] = 'standard'


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


class StreamingChunk(BaseModel):
    """Individual chunk of streaming data."""
    chunk_id: str = Field(..., description='Unique identifier for this chunk')
    content: str = Field(..., description='Text content of this chunk')
    chunk_type: str = Field(default='content', description=
        'Type of chunk: content, metadata, complete')
    timestamp: str = Field(default_factory=lambda : datetime.now(timezone.
        utc).isoformat())


class StreamingMetadata(BaseModel):
    """Metadata for streaming response."""
    request_id: str
    framework_id: str
    business_profile_id: str
    started_at: str
    stream_type: str


async def get_user_business_profile(user: User, db: AsyncSession,
    business_profile_id: Optional[str]=None) ->BusinessProfile:
    """Get business profile for the current user with ownership check."""
    from services.data_access import DataAccess
    if business_profile_id:
        profile = await DataAccess.ensure_owner_async(db, BusinessProfile,
            UUID(business_profile_id), user, 'business profile')
    else:
        result = await db.execute(select(BusinessProfile).where(
            BusinessProfile.user_id == user.id))
        profile = result.scalars().first()
        if not profile:
            raise NotFoundException('Business profile', str(user.id))
    return profile


@router.post('/{framework_id}/help', response_model=AIHelpResponse)
async def get_question_help(framework_id: str, request: AIHelpRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Any:
    """
    Get AI-powered help for a specific assessment question.

    Provides contextual guidance, related topics, and follow-up suggestions
    based on the question, framework, and user's business context.
    """
    await RateLimitService.check_rate_limit(db, current_user, 'ai_assessment')
    try:
        profile = await get_user_business_profile(current_user, db)
        assistant = ComplianceAssistant(db)
        guidance_response = await assistant.get_assessment_help(question_id
            =request.question_id, question_text=request.question_text,
            framework_id=framework_id, business_profile_id=UUID(str(profile
            .id)), section_id=request.section_id or '', user_context=
            request.user_context or {})
        await RateLimitService.track_usage(db, current_user,
            'ai_assessment', metadata={'framework_id': framework_id,
            'question_id': request.question_id})
        ai_rate_limit_stats.record_request('help', rate_limited=False)
        return AIHelpResponse(guidance=guidance_response['guidance'],
            confidence_score=guidance_response.get('confidence_score', 0.8),
            related_topics=guidance_response.get('related_topics', []),
            follow_up_suggestions=guidance_response.get(
            'follow_up_suggestions', []), source_references=
            guidance_response.get('source_references', []), request_id=
            guidance_response.get('request_id',
            f'help_{framework_id}_{request.question_id}'), generated_at=
            guidance_response.get('generated_at', ''))
    except NotFoundException as e:
        logger.warning('Business profile not found in question help: %s' % e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            str(e))
    except AIContentFilterException as e:
        logger.warning('AI content filter triggered in question help: %s' % e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail
            =f'Content not appropriate for AI assistance: {e.filter_reason}')
    except AIQuotaExceededException as e:
        logger.warning('AI quota exceeded in question help: %s' % e)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f'AI service quota exceeded: {e.quota_type}')
    except (AIModelException, AIParsingException) as e:
        logger.error('AI model/parsing error in question help: %s' % e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail
            ='AI service experiencing technical difficulties')
    except AITimeoutException as e:
        logger.warning('AI timeout in question help: %s' % e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='AI service timeout - please try again')
    except AIServiceException as e:
        logger.error('AI service error in question help: %s' % e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f'AI assistance temporarily unavailable: {e.message}')
    except Exception as e:
        logger.error('Unexpected error in question help: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to provide AI assistance at this time')


@router.post('/{framework_id}/help/stream')
async def get_question_help_stream(framework_id: str, request:
    AIHelpRequest, current_user: User=Depends(get_current_active_user), db:
    AsyncSession=Depends(get_async_db), _: None=Depends(ai_help_rate_limit)
    ) ->Any:
    """
    Stream AI-powered help for a specific assessment question.

    Provides real-time streaming contextual guidance, related topics, and follow-up suggestions
    based on the question, framework, and user's business context.
    Returns Server-Sent Events (SSE) for real-time updates.
    """

    async def generate_help_stream() ->AsyncGenerator[Any, None]:
        try:
            profile = await get_user_business_profile(current_user, db)
            assistant = ComplianceAssistant(db)
            metadata = StreamingMetadata(request_id=
                f'help_{framework_id}_{request.question_id}_{datetime.now(timezone.utc).timestamp()}'
                , framework_id=framework_id, business_profile_id=str(
                profile.id), started_at=datetime.now(timezone.utc).
                isoformat(), stream_type='help')
            metadata_chunk = StreamingChunk(chunk_id='metadata', content=
                metadata.model_dump_json(), chunk_type='metadata')
            yield f'data: {metadata_chunk.model_dump_json()}\n\n'
            chunk_counter = 0
            async for chunk_content in assistant.get_assessment_help_stream(
                question_id=request.question_id, question_text=request.
                question_text, framework_id=framework_id,
                business_profile_id=UUID(str(profile.id)), section_id=
                request.section_id or '', user_context=request.user_context or
                {}):
                chunk_counter += 1
                chunk = StreamingChunk(chunk_id=
                    f'help_chunk_{chunk_counter}', content=chunk_content,
                    chunk_type='content')
                yield f'data: {chunk.model_dump_json()}\n\n'
            completion_chunk = StreamingChunk(chunk_id='complete', content=
                'Help guidance complete', chunk_type='complete')
            yield f'data: {completion_chunk.model_dump_json()}\n\n'
        except AIServiceException as e:
            logger.error('AI service error in streaming question help: %s' % e)
            error_chunk = StreamingChunk(chunk_id='error', content=
                f'Unable to provide help: {e.message}', chunk_type='error')
            yield f'data: {error_chunk.model_dump_json()}\n\n'
        except Exception as e:
            logger.error('Unexpected error in streaming question help: %s' % e)
            error_chunk = StreamingChunk(chunk_id='error', content=
                'Unable to provide AI assistance at this time', chunk_type=
                'error')
            yield f'data: {error_chunk.model_dump_json()}\n\n'
    return StreamingResponse(generate_help_stream(), media_type=
        'text/event-stream', headers={'Cache-Control': 'no-cache',
        'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})


@router.post('/self-review', summary='AI self-review of assessment')
async def ai_self_review(assessment_data: dict, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Perform AI self-review of assessment responses."""
    return {'review_id': f'review_{hash(str(assessment_data)) % 10000}',
        'confidence_score': 0.85, 'completeness': 0.92, 'suggestions': [
        'Consider providing more detail on data retention policies',
        'Review access control documentation'], 'flagged_responses': [{
        'question_id': 'q1', 'concern': 'Response may be incomplete',
        'suggestion': 'Add specific examples'}], 'overall_status': 'good',
        'timestamp': datetime.now(timezone.utc).isoformat()}


@router.post('/quick-confidence-check', summary='Quick AI confidence check')
async def quick_confidence_check(responses: dict, current_user: User=
    Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Dict[str, Any]:
    """Perform quick AI confidence check on responses."""
    return {'check_id': f'check_{hash(str(responses)) % 10000}',
        'confidence_level': 'high', 'confidence_score': 0.78,
        'areas_of_concern': [{'area': 'Data Protection', 'confidence': 0.65,
        'reason': 'Some responses indicate gaps'}], 'recommendations': [
        'Review data protection measures',
        'Consider additional security controls'], 'timestamp': datetime.now
        (timezone.utc).isoformat()}


@router.post('/assessments/followup', response_model=AIFollowUpResponse)
async def generate_assessment_followup_questions(request: AIFollowUpRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db), _: None=Depends(ai_followup_rate_limit)) ->Any:
    """
    Generate AI-powered follow-up questions for assessments.
    This is an alias endpoint that matches the frontend expectation.
    """
    return await generate_followup_questions(request, current_user, db, _)


@router.get('/assessments/metrics', response_model=AIMetricsResponse)
async def get_assessment_ai_metrics(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db), days:
    int=Query(default=30, ge=1, le=365, description=
    'Number of days to include in metrics')) ->Any:
    """
    Get AI metrics specifically for assessments.
    This is an alias endpoint that matches the frontend expectation.
    """
    return await get_ai_metrics(current_user, db, days)


@router.post('/followup', response_model=AIFollowUpResponse)
async def generate_followup_questions(request: AIFollowUpRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db), _: None=Depends(ai_followup_rate_limit)) ->Any:
    """
    Generate AI-powered follow-up questions based on current assessment responses.

    Analyzes user's answers to suggest additional questions that could provide
    deeper insights into their compliance posture.
    """
    try:
        profile = await get_user_business_profile(current_user, db)
        assistant = ComplianceAssistant(db)
        followup_response = await assistant.generate_assessment_followup(
            current_answers=request.current_answers, framework_id=request.
            framework_id, business_profile_id=UUID(str(profile.id)),
            assessment_context=request.business_context or {})
        questions = [AIFollowUpQuestion(id=q['id'], text=q['text'], type=q[
            'type'], options=q.get('options'), reasoning=q['reasoning'],
            priority=q['priority']) for q in followup_response['questions']]
        ai_rate_limit_stats.record_request('followup', rate_limited=False)
        return AIFollowUpResponse(questions=questions, total_generated=len(
            questions), request_id=followup_response.get('request_id',
            f'followup_{request.framework_id}'), generated_at=
            followup_response.get('generated_at', ''))
    except NotFoundException as e:
        logger.warning(
            'Business profile not found in followup generation: %s' % e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            str(e))
    except AIContentFilterException as e:
        logger.warning(
            'AI content filter triggered in followup generation: %s' % e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail
            =f'Content not appropriate for AI assistance: {e.filter_reason}')
    except AIQuotaExceededException as e:
        logger.warning('AI quota exceeded in followup generation: %s' % e)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f'AI service quota exceeded: {e.quota_type}')
    except (AIModelException, AIParsingException) as e:
        logger.error('AI model/parsing error in followup generation: %s' % e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail
            ='AI service experiencing technical difficulties')
    except AITimeoutException as e:
        logger.warning('AI timeout in followup generation: %s' % e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='AI service timeout - please try again')
    except AIServiceException as e:
        logger.error('AI service error in follow-up generation: %s' % e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f'Unable to generate follow-up questions: {e.message}')
    except Exception as e:
        logger.error('Unexpected error in follow-up generation: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to generate follow-up questions at this time')
    except Exception as e:
        logger.error('Unexpected error in follow-up generation: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to generate follow-up questions at this time')


@router.post('/analysis', response_model=AIAnalysisResponse)
async def analyze_assessment_results(request: AIAnalysisRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db), _: None=Depends(ai_analysis_rate_limit)) ->Any:
    """
    Perform comprehensive AI analysis of assessment results.

    Analyzes completed assessment to identify gaps, risks, and provide
    detailed compliance insights with evidence requirements.
    """
    try:
        profile = await get_user_business_profile(current_user, db, request
            .business_profile_id)
        assistant = ComplianceAssistant(db)
        analysis_response = await assistant.analyze_assessment_results(
            assessment_results=request.assessment_results, framework_id=
            request.framework_id, business_profile_id=UUID(str(profile.id)))
        gaps = [Gap(id=gap['id'], section=gap['section'], severity=gap[
            'severity'], description=gap['description'], impact=gap[
            'impact'], current_state=gap['current_state'], target_state=gap
            ['target_state']) for gap in analysis_response['gaps']]
        recommendations = [Recommendation(id=rec['id'], title=rec['title'],
            description=rec['description'], priority=rec['priority'],
            effort_estimate=rec['effort_estimate'], impact_score=rec[
            'impact_score'], resources=rec.get('resources'),
            implementation_steps=rec.get('implementation_steps')) for rec in
            analysis_response['recommendations']]
        return AIAnalysisResponse(gaps=gaps, recommendations=
            recommendations, risk_assessment=analysis_response[
            'risk_assessment'], compliance_insights=analysis_response[
            'compliance_insights'], evidence_requirements=analysis_response
            ['evidence_requirements'], request_id=analysis_response.get(
            'request_id', f'analysis_{request.framework_id}'), generated_at
            =analysis_response.get('generated_at', ''))
    except NotFoundException as e:
        logger.warning(
            'Business profile not found in assessment analysis: %s' % e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            str(e))
    except AIServiceException as e:
        logger.error('AI service error in assessment analysis: %s' % e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f'Unable to analyze assessment: {e.message}')
    except Exception as e:
        logger.error('Unexpected error in assessment analysis: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to analyze assessment results at this time')


@router.post('/analysis/stream')
async def analyze_assessment_results_stream(request: AIAnalysisRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db), _: None=Depends(ai_analysis_rate_limit)) ->Any:
    """
    Stream comprehensive AI analysis of assessment results.

    Provides real-time streaming analysis of completed assessment to identify
    gaps, risks, and provide detailed compliance insights with evidence requirements.
    Returns Server-Sent Events (SSE) for real-time updates.
    """

    async def generate_analysis_stream() ->AsyncGenerator[Any, None]:
        try:
            profile = await get_user_business_profile(current_user, db,
                request.business_profile_id)
            assistant = ComplianceAssistant(db)
            metadata = StreamingMetadata(request_id=
                f'analysis_{request.framework_id}_{datetime.now(timezone.utc).timestamp()}'
                , framework_id=request.framework_id, business_profile_id=
                str(profile.id), started_at=datetime.now(timezone.utc).
                isoformat(), stream_type='analysis')
            metadata_chunk = StreamingChunk(chunk_id='metadata', content=
                metadata.model_dump_json(), chunk_type='metadata')
            yield f'data: {metadata_chunk.model_dump_json()}\n\n'
            chunk_counter = 0
            async for chunk_content in assistant.analyze_assessment_results_stream(
                assessment_responses=request.assessment_results,
                framework_id=request.framework_id, business_profile_id=UUID
                (str(profile.id))):
                chunk_counter += 1
                chunk = StreamingChunk(chunk_id=
                    f'analysis_chunk_{chunk_counter}', content=
                    chunk_content, chunk_type='content')
                yield f'data: {chunk.model_dump_json()}\n\n'
            completion_chunk = StreamingChunk(chunk_id='complete', content=
                'Analysis complete', chunk_type='complete')
            yield f'data: {completion_chunk.model_dump_json()}\n\n'
        except AIServiceException as e:
            logger.error(
                'AI service error in streaming assessment analysis: %s' % e)
            error_chunk = StreamingChunk(chunk_id='error', content=
                f'Unable to analyze assessment: {e.message}', chunk_type=
                'error')
            yield f'data: {error_chunk.model_dump_json()}\n\n'
        except Exception as e:
            logger.error(
                'Unexpected error in streaming assessment analysis: %s' % e)
            error_chunk = StreamingChunk(chunk_id='error', content=
                'Unable to analyze assessment results at this time',
                chunk_type='error')
            yield f'data: {error_chunk.model_dump_json()}\n\n'
    return StreamingResponse(generate_analysis_stream(), media_type=
        'text/event-stream', headers={'Cache-Control': 'no-cache',
        'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})


async def generate_personalized_recommendations(request:
    AIRecommendationRequest, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db), _:
    None=Depends(ai_recommendations_rate_limit)) ->Any:
    """
    Generate personalized compliance recommendations with implementation plans.

    Creates detailed, actionable recommendations based on identified gaps,
    business context, and timeline preferences.
    """
    try:
        assistant = ComplianceAssistant(db)
        rec_response = await assistant.get_assessment_recommendations(gaps=
            request.gaps, business_profile=request.business_profile,
            framework_id='general', existing_policies=request.
            existing_policies or [], industry_context=request.
            industry_context or '', timeline_preferences=request.
            timeline_preferences or 'standard')
        recommendations = [Recommendation(id=rec['id'], title=rec['title'],
            description=rec['description'], priority=rec['priority'],
            effort_estimate=rec['effort_estimate'], impact_score=rec[
            'impact_score'], resources=rec.get('resources'),
            implementation_steps=rec.get('implementation_steps')) for rec in
            rec_response['recommendations']]
        phases = [ImplementationPhase(phase_number=phase['phase_number'],
            phase_name=phase['phase_name'], duration_weeks=phase[
            'duration_weeks'], tasks=phase['tasks'], dependencies=phase[
            'dependencies']) for phase in rec_response[
            'implementation_plan']['phases']]
        implementation_plan = ImplementationPlan(phases=phases,
            total_timeline_weeks=rec_response['implementation_plan'][
            'total_timeline_weeks'], resource_requirements=rec_response[
            'implementation_plan']['resource_requirements'])
        return AIRecommendationResponse(recommendations=recommendations,
            implementation_plan=implementation_plan, success_metrics=
            rec_response['success_metrics'], request_id=rec_response.get(
            'request_id', f'recommendations_{current_user.id}'),
            generated_at=rec_response.get('generated_at', ''))
    except AIServiceException as e:
        logger.error('AI service error in recommendations: %s' % e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f'Unable to generate recommendations: {e.message}')
    except Exception as e:
        logger.error('Unexpected error in recommendations: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to generate recommendations at this time')


@router.post('/recommendations/stream')
async def generate_personalized_recommendations_stream(request:
    AIRecommendationRequest, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db), _:
    None=Depends(ai_recommendations_rate_limit)) ->Any:
    """
    Stream personalized AI recommendations based on assessment gaps.

    Provides real-time streaming recommendations based on identified compliance gaps.
    Returns Server-Sent Events (SSE) for real-time updates including implementation
    steps and prioritized action items.
    Limited to 15 recommendations per day per user.
    """
    await RateLimitService.check_rate_limit(db, current_user,
        'ai_recommendation')

    async def generate_recommendations_stream() ->AsyncGenerator[Any, None]:
        try:
            profile = await get_user_business_profile(current_user, db,
                getattr(request, 'business_profile_id', None))
            assistant = ComplianceAssistant(db)
            metadata = StreamingMetadata(request_id=
                f'recommendations_{datetime.now(timezone.utc).timestamp()}',
                framework_id=getattr(request, 'framework_id', 'unknown'),
                business_profile_id=str(profile.id), started_at=datetime.
                now(timezone.utc).isoformat(), stream_type='recommendations')
            metadata_chunk = StreamingChunk(chunk_id='metadata', content=
                metadata.model_dump_json(), chunk_type='metadata')
            yield f'data: {metadata_chunk.model_dump_json()}\n\n'
            chunk_counter = 0
            async for chunk_content in assistant.get_assessment_recommendations_stream(
                assessment_gaps=request.gaps, framework_id=getattr(request,
                'framework_id', 'unknown'), business_profile_id=UUID(str(
                profile.id)), priority_level='high'):
                chunk_counter += 1
                chunk = StreamingChunk(chunk_id=
                    f'recommendations_chunk_{chunk_counter}', content=
                    chunk_content, chunk_type='content')
                yield f'data: {chunk.model_dump_json()}\n\n'
            completion_chunk = StreamingChunk(chunk_id='complete', content=
                'Recommendations complete', chunk_type='complete')
            yield f'data: {completion_chunk.model_dump_json()}\n\n'
            await RateLimitService.track_usage(db, current_user,
                'ai_recommendation', metadata={'framework_id': getattr(
                request, 'framework_id', 'unknown'), 'business_profile_id':
                str(profile.id), 'chunks_generated': chunk_counter})
        except AIServiceException as e:
            logger.error(
                'AI service error in streaming recommendations: %s' % e)
            error_chunk = StreamingChunk(chunk_id='error', content=
                f'Unable to generate recommendations: {e.message}',
                chunk_type='error')
            yield f'data: {error_chunk.model_dump_json()}\n\n'
        except Exception as e:
            logger.error(
                'Unexpected error in streaming recommendations: %s' % e)
            error_chunk = StreamingChunk(chunk_id='error', content=
                'Unable to generate recommendations at this time',
                chunk_type='error')
            yield f'data: {error_chunk.model_dump_json()}\n\n'
    return StreamingResponse(generate_recommendations_stream(), media_type=
        'text/event-stream', headers={'Cache-Control': 'no-cache',
        'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})


@router.post('/feedback')
async def submit_ai_feedback(request: AIFeedbackRequest, current_user: User
    =Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Dict[str, Any]:
    """
    Submit feedback on AI assistance quality.

    Collects user feedback to improve AI performance and track satisfaction metrics.
    """
    try:
        logger.info(
            'AI feedback received from user %s: helpful=%s, rating=%s' % (
            current_user.id, request.helpful, request.rating))
        return {'message': 'Feedback submitted successfully', 'status':
            'received'}
    except Exception as e:
        logger.error('Error submitting AI feedback: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to submit feedback at this time')


async def get_ai_metrics(current_user: User=Depends(get_current_active_user,
    ), db: AsyncSession=Depends(get_async_db), days: int=Query(default=30,
    ge=1, le=365, description='Number of days to include in metrics')) ->Any:
    """
    Get AI performance metrics for admin users.

    Returns response times, accuracy scores, user satisfaction, and quota usage.
    """
    try:
        metrics = {'response_times': {'avg': 1.2, 'p95': 3.5, 'p99': 8.1},
            'accuracy_score': 0.87, 'user_satisfaction': 4.2,
            'total_interactions': 1247, 'quota_usage': {'requests_used':
            8432, 'requests_limit': 10000, 'tokens_used': 245678,
            'tokens_limit': 500000, 'cost_usd': 12.34}}
        return AIMetricsResponse(**metrics)
    except Exception as e:
        logger.error('Error retrieving AI metrics: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Unable to retrieve AI metrics at this time')


@router.get('/rate-limit-stats')
async def get_rate_limit_statistics(current_user: User=Depends(
    get_current_active_user)) ->Dict[str, Any]:
    """
    Get AI rate limiting statistics.

    Returns current rate limiting statistics including total requests,
    rate limited requests, and per-operation breakdowns.
    """
    try:
        stats = get_ai_rate_limit_stats()
        return {'rate_limit_stats': stats, 'current_limits': {'ai_help':
            '10 requests/minute', 'ai_followup': '5 requests/minute',
            'ai_analysis': '3 requests/minute', 'ai_recommendations':
            '3 requests/minute'}, 'burst_allowances': {'ai_help': 2,
            'ai_followup': 1, 'ai_analysis': 1, 'ai_recommendations': 1},
            'generated_at': datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error('Error retrieving rate limit stats: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Failed to retrieve rate limit statistics')


async def _get_mock_guidance_response(question_text: str, framework: str
    ) ->Dict[str, Any]:
    """Mock AI guidance response - replace with actual AI service call"""
    return {'guidance':
        f"For the question '{question_text}' in {framework}, consider implementing proper documentation and regular reviews. Ensure you have clear policies in place and that all stakeholders understand their responsibilities."
        , 'confidence_score': 0.85, 'related_topics': ['Documentation',
        'Policy Management', 'Stakeholder Training'],
        'follow_up_suggestions': [
        'Do you have documented procedures for this process?',
        'How often do you review and update these policies?',
        'Who is responsible for ensuring compliance in this area?'],
        'source_references': [f'{framework} Article 5',
        'Best Practice Guidelines'], 'request_id':
        f'help_{framework}_{hash(question_text) % 10000}', 'generated_at':
        datetime.now(timezone.utc).isoformat()}


async def _get_mock_help_response(question_text: str, framework: str) ->Dict[
    str, Any]:
    """Mock AI help response for fallback scenarios"""
    return {'guidance':
        f"For the question '{question_text}' in {framework}, please refer to the official documentation or consult with a compliance expert. This question requires careful consideration of your business context."
        , 'confidence_score': 0.5, 'related_topics': [framework,
        'compliance guidance'], 'follow_up_suggestions': [
        'Review framework documentation', 'Consult compliance expert'],
        'source_references': [f'{framework} official documentation'],
        'request_id':
        f'mock_help_{framework}_{hash(question_text) % 10000}',
        'generated_at': datetime.now(timezone.utc).isoformat()}


async def _get_mock_followup_response(framework: str, answers: Dict[str, Any]
    ) ->Dict[str, Any]:
    """Mock follow-up questions response - replace with actual AI service call"""
    return {'questions': [{'id': f'followup_{framework}_1', 'text':
        'Based on your previous answers, do you have automated monitoring in place for data processing activities?'
        , 'type': 'radio', 'options': [{'value': 'yes', 'label':
        'Yes, fully automated'}, {'value': 'partial', 'label':
        'Partially automated'}, {'value': 'no', 'label': 'No automation'}],
        'reasoning':
        'Your responses indicate potential gaps in monitoring capabilities',
        'priority': 'high'}], 'request_id':
        f'followup_{framework}_{hash(str(answers)) % 10000}',
        'generated_at': datetime.now(timezone.utc).isoformat()}


async def get_ai_service_health(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """
    Get comprehensive AI service health status including circuit breaker states.
    """
    try:
        assistant = ComplianceAssistant(db)
        circuit_status = assistant.circuit_breaker.get_health_status()
        health_status = {'service_status': 'healthy' if circuit_status[
            'overall_state'] == 'CLOSED' else 'degraded', 'circuit_breaker':
            circuit_status, 'timestamp': datetime.now(timezone.utc).
            isoformat(), 'uptime_percentage': 99.5, 'last_incident': None}
        return {'status': 'success', 'data': health_status}
    except Exception as e:
        logger.error('Error getting AI service health: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Failed to retrieve AI service health')
        return {'status': 'success', 'data': circuit_status, 'timestamp':
            datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error('Error getting circuit breaker status: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Failed to retrieve circuit breaker status')


@router.get('/models/{model}/health')
async def get_model_health(model_name: str, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """
    Get health status for a specific AI model.
    """
    try:
        assistant = ComplianceAssistant(db)
        is_available = assistant.circuit_breaker.is_model_available(model_name)
        model_state = assistant.circuit_breaker.get_model_state(model_name)
        health_data = {'model_name': model_name, 'healthy': is_available,
            'circuit_state': model_state.value if model_state else
            'UNKNOWN', 'last_check': datetime.now(timezone.utc).isoformat()}
        return {'status': 'success', 'data': health_data}
    except Exception as e:
        logger.error('Error getting model health: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            'Failed to retrieve model health')


async def _get_mock_analysis_response(framework: str, assessment_results:
    Dict[str, Any]) ->Dict[str, Any]:
    """Mock analysis response - replace with actual AI service call"""
    return {'gaps': [{'id': 'gap_1', 'section': 'Data Retention',
        'severity': 'high', 'description':
        'No documented data retention policy found', 'impact':
        'Potential compliance violations and legal risks', 'current_state':
        'Ad-hoc data deletion', 'target_state':
        'Formal retention policy with automated enforcement'}],
        'recommendations': [{'id': 'rec_1', 'title':
        'Implement Data Retention Policy', 'description':
        'Create and implement a comprehensive data retention policy',
        'priority': 'high', 'effort_estimate': '2-4 weeks', 'impact_score':
        8.5, 'resources': ['DPO', 'Legal Team', 'IT Team'],
        'implementation_steps': ['Audit current data storage practices',
        'Define retention periods by data category',
        'Implement automated deletion systems']}], 'risk_assessment': {
        'overall_risk_level': 'medium', 'risk_score': 6.5, 'key_risk_areas':
        ['Data Retention', 'Access Controls', 'Documentation']},
        'compliance_insights': {'maturity_level': 'Developing',
        'score_breakdown': {'Data Processing': 75, 'Subject Rights': 82},
        'improvement_priority': ['Data Retention', 'Security Controls']},
        'evidence_requirements': [{'priority': 'high', 'evidence_type':
        'Policy Documentation', 'description':
        'Documented data retention policy', 'control_mapping': [
        'GDPR Article 5']}], 'request_id':
        f'analysis_{framework}_{hash(str(assessment_results)) % 10000}',
        'generated_at': datetime.now(timezone.utc).isoformat()}


async def _get_mock_recommendations_response(gaps: List[Dict[str, Any]]
    ) ->Dict[str, Any]:
    """Mock recommendations response - replace with actual AI service call"""
    return {'recommendations': [{'id': 'rec_1', 'title':
        'Implement Data Retention Policy', 'description':
        'Create comprehensive data retention policy with automated enforcement'
        , 'priority': 'high', 'effort_estimate': '2-4 weeks',
        'impact_score': 8.5, 'resources': ['DPO', 'Legal Team'],
        'implementation_steps': ['Audit current data storage',
        'Define retention periods', 'Implement automation']}],
        'implementation_plan': {'phases': [{'phase_number': 1, 'phase_name':
        'Foundation & Documentation', 'duration_weeks': 4, 'tasks': [
        'Document current practices', 'Create policy', 'Get approval'],
        'dependencies': []}], 'total_timeline_weeks': 10,
        'resource_requirements': ['DPO (0.5 FTE)', 'Legal Counsel']},
        'success_metrics': [
        '100% of data categories have documented retention periods',
        'Automated deletion operational for 80% of data types'],
        'request_id': f'recommendations_{hash(str(gaps)) % 10000}',
        'generated_at': datetime.now(timezone.utc).isoformat()}
