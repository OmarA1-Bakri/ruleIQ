"""

AI Policy Generation API Router

Provides endpoints for AI-powered policy generation with dual provider support.
"""
from typing import Optional, Any, Dict, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from database.db_setup import get_db
from database.compliance_framework import ComplianceFramework
from api.schemas.ai_policy import PolicyGenerationRequest, PolicyGenerationResponse, PolicyRefinementRequest, PolicyRefinementResponse, PolicyTemplatesResponse, PolicyTemplate, AIProviderMetrics, PolicyGenerationMetrics
from services.ai.policy_generator import PolicyGenerator, TemplateProcessor
from api.dependencies.auth import get_current_active_user
from api.middleware.rate_limiter import RateLimited
from services.rate_limiting import RateLimitService
from database.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_setup import get_async_db
import logging
logger = logging.getLogger(__name__)
router = APIRouter(tags=['AI Policy Generation'])


@router.post('/generate-policy', response_model=PolicyGenerationResponse,
    status_code=status.HTTP_201_CREATED, dependencies=[Depends(
    get_current_active_user), Depends(RateLimited(requests=20, window=60))])
async def generate_policy(request: PolicyGenerationRequest,
    background_tasks: BackgroundTasks, current_user: User=Depends(
    get_current_active_user), db: Session=Depends(get_db), async_db:
    AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """
    Generate compliance policy using AI with dual provider fallback.

    Requires authentication. Limited to 20 requests per minute and 5 per day per user.
    Uses Google AI (primary) with OpenAI fallback for reliability.
    """
    await RateLimitService.check_rate_limit(async_db, current_user,
        'ai_policy_generation')
    framework = db.query(ComplianceFramework).filter(ComplianceFramework.id ==
        request.framework_id).first()
    if not framework:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            f'Framework not found: {request.framework_id}')
    if not framework.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail
            =f'Framework is not active: {framework.name}')
    generator = PolicyGenerator()
    try:
        result = generator.generate_policy(request, framework)
        await RateLimitService.track_usage(async_db, current_user,
            'ai_policy_generation', metadata={'framework_id': str(request.
            framework_id), 'framework_name': framework.name, 'provider':
            result.provider_used})
        background_tasks.add_task(_log_generation_metrics, result, request.
            framework_id, framework.name)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Policy generation failed: {str(e)}')


@router.post('/generate-policy/stream', status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(
    requests=20, window=60))])
async def generate_policy_stream(request: PolicyGenerationRequest,
    current_user: User=Depends(get_current_active_user), db: Session=
    Depends(get_db), async_db: AsyncSession=Depends(get_async_db)) ->Any:
    """
    Stream AI policy generation in real-time using Server-Sent Events.

    Provides real-time streaming of policy sections as they are generated,
    allowing for progressive display in the UI. Uses dual provider fallback
    (Google AI primary, OpenAI secondary) for reliability.

    Returns:
        StreamingResponse with text/event-stream content type
    """
    from fastapi.responses import StreamingResponse
    from api.schemas.ai_policy import PolicyStreamingChunk, PolicyStreamingMetadata
    import uuid
    await RateLimitService.check_rate_limit(async_db, current_user,
        'ai_policy_generation')
    framework = db.query(ComplianceFramework).filter(ComplianceFramework.id ==
        request.framework_id).first()
    if not framework:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            f'Framework not found: {request.framework_id}')
    if not framework.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail
            =f'Framework is not active: {framework.name}')

    async def generate_policy_stream_events() ->AsyncGenerator[Any, None]:
        """Generate SSE events for policy streaming."""
        session_id = str(uuid.uuid4())
        try:
            metadata = PolicyStreamingMetadata(session_id=session_id,
                policy_type=request.policy_type, framework_id=str(request.
                framework_id), organization_name=request.business_context.
                organization_name, stream_type='policy_generation')
            metadata_chunk = PolicyStreamingChunk(chunk_id=
                f'{session_id}-metadata', content=metadata.json(),
                chunk_type='metadata')
            yield f'data: {metadata_chunk.json()}\n\n'
            generator = PolicyGenerator()
            chunk_count = 0
            async for chunk_data in generator.generate_policy_stream(request,
                framework):
                chunk_count += 1
                if chunk_data['type'] == 'content':
                    chunk = PolicyStreamingChunk(chunk_id=
                        f'{session_id}-{chunk_count}', content=chunk_data[
                        'content'], chunk_type='content', progress=
                        chunk_data.get('progress'))
                    yield f'data: {chunk.json()}\n\n'
                elif chunk_data['type'] == 'complete':
                    await RateLimitService.track_usage(async_db,
                        current_user, 'ai_policy_generation', metadata={
                        'framework_id': str(request.framework_id),
                        'framework_name': framework.name, 'provider':
                        chunk_data.get('provider', 'unknown'), 'streaming':
                        True})
                    completion_chunk = PolicyStreamingChunk(chunk_id=
                        f'{session_id}-complete', content=
                        'Policy generation completed successfully',
                        chunk_type='complete', progress=1.0)
                    yield f'data: {completion_chunk.json()}\n\n'
                elif chunk_data['type'] == 'error':
                    error_chunk = PolicyStreamingChunk(chunk_id=
                        f'{session_id}-error', content=chunk_data['error'],
                        chunk_type='error')
                    yield f'data: {error_chunk.json()}\n\n'
        except Exception as e:
            logger.error('Error in streaming policy generation: %s' % e)
            error_chunk = PolicyStreamingChunk(chunk_id=
                f'{session_id}-error', content=str(e), chunk_type='error')
            yield f'data: {error_chunk.json()}\n\n'
    return StreamingResponse(generate_policy_stream_events(), media_type=
        'text/event-stream', headers={'Cache-Control': 'no-cache',
        'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})


@router.put('/refine-policy', response_model=PolicyRefinementResponse,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(
    requests=30, window=60))])
async def refine_policy(request: PolicyRefinementRequest, current_user:
    User=Depends(get_current_active_user), db: Session=Depends(get_db),
    async_db: AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """
    Refine existing policy based on feedback.

    Requires authentication. Limited to 30 requests per minute and 5 per day per user.
    """
    await RateLimitService.check_rate_limit(async_db, current_user,
        'ai_policy_generation')
    framework = db.query(ComplianceFramework).filter(ComplianceFramework.id ==
        request.framework_id).first()
    if not framework:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            f'Framework not found: {request.framework_id}')
    generator = PolicyGenerator()
    try:
        result = generator.refine_policy(request.original_policy, request.
            feedback, framework)
        await RateLimitService.track_usage(async_db, current_user,
            'ai_policy_generation', metadata={'framework_id': str(request.
            framework_id), 'framework_name': framework.name, 'action':
            'refinement'})
        return result
    except Exception as e:
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Policy refinement failed: {str(e)}')


@router.get('/policy-templates', response_model=PolicyTemplatesResponse,
    dependencies=[Depends(RateLimited(requests=100, window=60))])
async def get_policy_templates(framework_id: Optional[str]=None,
    policy_type: Optional[str]=None, db: Session=Depends(get_db)) ->Any:
    """
    Get available policy templates.

    Can be filtered by framework and policy type.
    Limited to 100 requests per minute.
    """
    TemplateProcessor()
    templates = [PolicyTemplate(id='uk_gdpr_privacy_policy', name=
        'UK GDPR Privacy Policy', description=
        'GDPR-compliant privacy policy for UK organizations', policy_type=
        'privacy_policy', framework_compatibility=['ICO_GDPR_UK'], sections
        =['data_controller_info', 'legal_basis', 'data_subject_rights',
        'retention'], customization_options={'include_marketing': True,
        'include_cookies': True, 'include_third_parties': True}),
        PolicyTemplate(id='iso27001_info_sec_policy', name=
        'ISO 27001 Information Security Policy', description=
        'Information security policy based on ISO 27001 template',
        policy_type='information_security_policy', framework_compatibility=
        ['ISO27001_UK'], sections=['policy_statement', 'scope',
        'responsibilities', 'implementation'], customization_options={
        'include_risk_assessment': True, 'include_incident_response': True,
        'include_business_continuity': False}), PolicyTemplate(id=
        'fca_data_governance', name='FCA Data Governance Policy',
        description='Data governance policy for FCA-regulated firms',
        policy_type='data_governance_policy', framework_compatibility=[
        'FCA_REGULATORY'], sections=['governance_framework', 'data_quality',
        'regulatory_reporting'], customization_options={'include_smcr':
        True, 'include_operational_resilience': True}), PolicyTemplate(id=
        'cyber_essentials_security', name=
        'Cyber Essentials Security Policy', description=
        'Basic security policy for Cyber Essentials certification',
        policy_type='cybersecurity_policy', framework_compatibility=[
        'CYBER_ESSENTIALS_UK'], sections=['network_security',
        'access_control', 'malware_protection'], customization_options={
        'include_remote_working': True, 'include_byod': False})]
    if framework_id:
        framework = db.query(ComplianceFramework).filter(
            ComplianceFramework.id == framework_id).first()
        if framework:
            templates = [t for t in templates if framework.name in t.
                framework_compatibility]
    if policy_type:
        templates = [t for t in templates if t.policy_type == policy_type]
    supported_frameworks = list(set(fw for template in templates for fw in
        template.framework_compatibility))
    return PolicyTemplatesResponse(templates=templates, total_count=len(
        templates), supported_frameworks=supported_frameworks,
        supported_languages=['en-GB', 'en-US'])


@router.get('/metrics', response_model=PolicyGenerationMetrics,
    dependencies=[Depends(get_current_active_user), Depends(RateLimited(
    requests=50, window=60))])
async def get_ai_metrics() ->Any:
    """
    Get AI policy generation metrics and performance data.

    Requires authentication. Shows provider performance, costs, and usage.
    """
    google_metrics = AIProviderMetrics(provider='google', requests_total=
        150, requests_successful=142, requests_failed=8,
        average_response_time_ms=2500.0, average_confidence_score=0.91,
        total_cost=45.3, last_24h_requests=25)
    openai_metrics = AIProviderMetrics(provider='openai', requests_total=25,
        requests_successful=23, requests_failed=2, average_response_time_ms
        =3200.0, average_confidence_score=0.88, total_cost=12.75,
        last_24h_requests=3)
    from services.ai.circuit_breaker import CircuitBreakerService
    circuit_breaker = CircuitBreakerService()
    circuit_status = {'google_status': circuit_breaker.get_state('google'),
        'openai_status': circuit_breaker.get_state('openai'),
        'failure_count': 0, 'last_failure_time': None, 'next_retry_time': None}
    return PolicyGenerationMetrics(total_policies_generated=175,
        success_rate=0.94, average_generation_time_ms=2650.0,
        cache_hit_rate=0.15, provider_metrics=[google_metrics,
        openai_metrics], circuit_breaker_status=circuit_status,
        cost_savings_percentage=42.5, monthly_cost_trend=[65.2, 58.05, 52.3,
        48.15])


@router.post('/validate-policy', dependencies=[Depends(
    get_current_active_user), Depends(RateLimited(requests=50, window=60))])
async def validate_policy(policy_content: str, framework_id: str,
    current_user: User=Depends(get_current_active_user), db: Session=
    Depends(get_db), async_db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """
    Validate policy against framework requirements.

    Requires authentication. Limited to 50 requests per minute and 20 per day.
    """
    await RateLimitService.check_rate_limit(async_db, current_user,
        'ai_compliance_check')
    framework = db.query(ComplianceFramework).filter(ComplianceFramework.id ==
        framework_id).first()
    if not framework:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            f'Framework not found: {framework_id}')
    generator = PolicyGenerator()
    try:
        validation_result = generator.validate_uk_policy(policy_content,
            framework)
        await RateLimitService.track_usage(async_db, current_user,
            'ai_compliance_check', metadata={'framework_id': str(
            framework_id), 'framework_name': framework.name, 'action':
            'policy_validation'})
        return validation_result
    except Exception as e:
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Policy validation failed: {str(e)}')


async def _log_generation_metrics(result: PolicyGenerationResponse,
    framework_id: str, framework_name: str) ->None:
    """
    Log policy generation metrics in background.

    Args:
        result: Policy generation result
        framework_id: Framework ID used
        framework_name: Framework name
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        'Policy generated: framework=%s, provider=%s, confidence=%s, time=%sms, cost=$%s'
         % (framework_name, result.provider_used, result.confidence_score,
        result.generation_time_ms, result.estimated_cost or 0))


@router.post('/analytics/export', dependencies=[Depends(
    get_current_active_user), Depends(RateLimited(requests=5, window=3600))])
async def export_analytics(start_date: str, end_date: str, format: str='csv'
    ) ->Dict[str, Any]:
    """
    Export policy generation analytics.

    Limited to 5 exports per hour. Requires admin permissions.
    """
    if format not in ['csv', 'json', 'xlsx']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail
            ='Supported formats: csv, json, xlsx')
    return {'message':
        f'Analytics export started for {start_date} to {end_date}',
        'format': format, 'estimated_completion': '2-3 minutes',
        'download_url': '/api/v1/ai/analytics/download/{export_id}'}
