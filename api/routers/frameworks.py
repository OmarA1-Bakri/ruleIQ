import logging

# Constants
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404

logger = logging.getLogger(__name__)
from typing import List, Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.database import get_async_db
from api.dependencies.rbac_auth import UserWithRoles, require_permission
from api.schemas.models import ComplianceFrameworkResponse, FrameworkRecommendation
from services.framework_service import get_framework_by_id, get_relevant_frameworks
router = APIRouter()


@router.get('/', response_model=List[ComplianceFrameworkResponse])
async def list_frameworks(current_user: UserWithRoles=Depends(
    require_permission('user_list')), db: AsyncSession=Depends(get_async_db)
    ) ->Any:
    """List all available frameworks - simplified for compliance wizard."""
    from database.compliance_framework import ComplianceFramework
    from sqlalchemy.future import select
    result = await db.execute(select(ComplianceFramework))
    frameworks = result.scalars().all()
    logger.info('DEBUG: Found %s total frameworks' % len(frameworks))
    active_frameworks = [fw for fw in frameworks if fw.is_active]
    logger.info('DEBUG: Found %s active frameworks' % len(active_frameworks))
    return [ComplianceFrameworkResponse(id=fw.id, name=fw.name, description
        =fw.description or '', category=fw.category or 'general', version=
        fw.version or '1.0', controls=[]) for fw in active_frameworks]


@router.get('/recommendations', response_model=List[FrameworkRecommendation])
async def get_framework_recommendations(current_user: UserWithRoles=Depends
    (require_permission('framework_list')), db: AsyncSession=Depends(
    get_async_db)) ->Any:
    """Get framework recommendations filtered by user's access permissions."""
    recommendations = await get_relevant_frameworks(db, current_user)
    accessible_recommendations = []
    for rec in recommendations:
        framework = rec['framework']
        framework_id = str(framework.id)
        has_access = any(af['id'] == framework_id for af in current_user.
            accessible_frameworks)
        if has_access:
            accessible_recommendations.append(FrameworkRecommendation(
                framework=framework, relevance_score=rec['relevance_score'],
                reasons=rec.get('reasons', []), priority=rec.get('priority',
                'medium')))
    return accessible_recommendations


@router.get('/recommendations/{business_profile_id}', response_model=List[
    FrameworkRecommendation])
async def get_framework_recommendations_for_profile(business_profile_id:
    UUID, current_user: UserWithRoles=Depends(require_permission(
    'framework_list')), db: AsyncSession=Depends(get_async_db)) ->Any:
    """Get framework recommendations for a specific business profile."""
    recommendations = await get_relevant_frameworks(db, current_user)
    accessible_recommendations = []
    for rec in recommendations:
        framework = rec['framework']
        framework_id = str(framework.id)
        has_access = any(af['id'] == framework_id for af in current_user.
            accessible_frameworks)
        if has_access:
            accessible_recommendations.append(FrameworkRecommendation(
                framework=framework, relevance_score=rec['relevance_score'],
                reasons=rec.get('reasons', []), priority=rec.get('priority',
                'medium')))
    return accessible_recommendations


@router.get('/all-public', response_model=List[ComplianceFrameworkResponse])
async def list_all_public_frameworks(current_user: UserWithRoles=Depends(
    require_permission('user_list')), db: AsyncSession=Depends(get_async_db)
    ) ->Any:
    """List all available frameworks without RBAC restrictions - for compliance wizard."""
    from database.compliance_framework import ComplianceFramework
    from sqlalchemy.future import select
    result = await db.execute(select(ComplianceFramework).where(
        ComplianceFramework.is_active))
    frameworks = result.scalars().all()
    return [ComplianceFrameworkResponse(id=fw.id, name=fw.name, description
        =fw.description or '', category=fw.category or 'general', version=
        fw.version or '1.0', controls=[]) for fw in frameworks]


@router.get('/{id}', response_model=ComplianceFrameworkResponse)
async def get_framework(id: UUID, current_user: UserWithRoles=Depends(
    require_permission('framework_list')), db: AsyncSession=Depends(
    get_async_db)) ->Any:
    """Get a specific framework if user has access to it."""
    framework_id = id
    has_access = any(af['id'] == str(framework_id) for af in current_user.
        accessible_frameworks)
    if not has_access:
        raise HTTPException(status_code=HTTP_FORBIDDEN, detail=
            "Access denied: You don't have permission to access this framework"
            )
    framework = await get_framework_by_id(db, current_user, framework_id)
    if not framework:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
            'Framework not found')
    controls = []
    if framework.control_domains:
        controls = [{'name': domain, 'description': f'{domain} controls'} for
            domain in framework.control_domains]
    return ComplianceFrameworkResponse(id=framework.id, name=framework.name,
        description=framework.description, category=framework.category,
        version=framework.version, controls=controls)


@router.get('/{framework_id}/controls')
async def get_framework_controls(framework_id: UUID, current_user:
    UserWithRoles=Depends(require_permission('framework_list')), db:
    AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """Get controls for a specific framework."""
    return {'framework_id': str(framework_id), 'controls': [{'id': 'ctrl-1',
        'name': 'Access Control', 'description':
        'Implement proper access control mechanisms', 'category':
        'Security', 'required': True}, {'id': 'ctrl-2', 'name':
        'Data Encryption', 'description':
        'Encrypt data at rest and in transit', 'category': 'Security',
        'required': True}, {'id': 'ctrl-3', 'name': 'Audit Logging',
        'description': 'Maintain comprehensive audit logs', 'category':
        'Compliance', 'required': False}], 'total': 3}


@router.get('/{framework_id}/implementation-guide')
async def get_framework_implementation_guide(framework_id: UUID,
    current_user: UserWithRoles=Depends(require_permission('framework_list'
    )), db: AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """Get implementation guide for a framework."""
    return {'framework_id': str(framework_id), 'guide': {'overview':
        'Step-by-step guide to implement this framework', 'phases': [{
        'phase': 1, 'name': 'Assessment', 'duration': '2-4 weeks', 'tasks':
        ['Gap analysis', 'Risk assessment', 'Resource planning']}, {'phase':
        2, 'name': 'Implementation', 'duration': '8-12 weeks', 'tasks': [
        'Control implementation', 'Process documentation', 'Training']}, {
        'phase': 3, 'name': 'Validation', 'duration': '2-3 weeks', 'tasks':
        ['Internal audit', 'Remediation', 'Certification prep']}],
        'resources': ['Implementation checklist', 'Control templates',
        'Policy templates']}}


@router.get('/{framework_id}/compliance-status')
async def get_framework_compliance_status(framework_id: UUID, current_user:
    UserWithRoles=Depends(require_permission('framework_list')), db:
    AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """Get compliance status for a specific framework."""
    return {'framework_id': str(framework_id), 'overall_compliance': 75.5,
        'status': 'in_progress', 'controls_status': {'compliant': 15,
        'partial': 5, 'non_compliant': 3, 'not_applicable': 2},
        'last_assessment': '2024-01-15T10:00:00Z', 'next_review':
        '2024-04-15T10:00:00Z'}


@router.post('/compare')
async def compare_frameworks(comparison_data: dict, current_user:
    UserWithRoles=Depends(require_permission('framework_list')), db:
    AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """Compare multiple frameworks."""
    framework_ids = comparison_data.get('framework_ids', [])
    return {'frameworks': framework_ids, 'comparison': {'common_controls':
        45, 'unique_controls': {(framework_ids[0] if len(framework_ids) > 0
         else 'framework1'): 12, (framework_ids[1] if len(framework_ids) >
        1 else 'framework2'): 8}, 'complexity': {(framework_ids[0] if len(
        framework_ids) > 0 else 'framework1'): 'High', (framework_ids[1] if
        len(framework_ids) > 1 else 'framework2'): 'Medium'},
        'implementation_time': {(framework_ids[0] if len(framework_ids) > 0
         else 'framework1'): '6-8 months', (framework_ids[1] if len(
        framework_ids) > 1 else 'framework2'): '4-6 months'}},
        'recommendation': 'Consider implementing both frameworks in phases'}


@router.get('/{framework_id}/maturity-assessment')
async def get_framework_maturity_assessment(framework_id: UUID,
    current_user: UserWithRoles=Depends(require_permission('framework_list'
    )), db: AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    """Get maturity assessment for a framework."""
    return {'framework_id': str(framework_id), 'maturity_level': 3,
        'maturity_name': 'Defined', 'levels': {'1': {'name': 'Initial',
        'achieved': True}, '2': {'name': 'Managed', 'achieved': True}, '3':
        {'name': 'Defined', 'achieved': True}, '4': {'name':
        'Quantitatively Managed', 'achieved': False}, '5': {'name':
        'Optimizing', 'achieved': False}}, 'recommendations': [
        'Implement continuous monitoring', 'Automate compliance checks',
        'Establish metrics and KPIs'], 'next_steps':
        'Focus on quantitative management and metrics'}
