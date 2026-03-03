from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from api.schemas.models import ImplementationPlanCreate, ImplementationPlanListResponse, ImplementationPlanResponse, ImplementationTaskUpdate
from database.db_setup import get_async_db
from database.user import User
from services.implementation_service import generate_implementation_plan, get_implementation_plan, list_implementation_plans, update_task_status

# Constants
HTTP_NOT_FOUND = 404

router = APIRouter()


@router.post('/plans', response_model=ImplementationPlanResponse,
    status_code=201)
async def create_plan(plan_data: ImplementationPlanCreate, current_user:
    User=Depends(get_current_active_user), db: AsyncSession=Depends(
    get_async_db)) ->Any:
    plan = await generate_implementation_plan(db, current_user, plan_data.
        framework_id, control_domain=plan_data.control_domain,
        timeline_weeks=plan_data.timeline_weeks)
    total_phases = len(plan.phases) if plan.phases else 0
    total_tasks = sum(len(phase.get('tasks', [])) for phase in plan.phases
        ) if plan.phases else 0
    estimated_duration_weeks = plan_data.timeline_weeks or 12
    plan_dict = {'id': plan.id, 'user_id': plan.user_id,
        'business_profile_id': plan.business_profile_id, 'framework_id':
        plan.framework_id, 'title': plan.title, 'status': plan.status,
        'phases': plan.phases, 'planned_start_date': plan.
        planned_start_date, 'planned_end_date': plan.planned_end_date,
        'actual_start_date': plan.actual_start_date, 'actual_end_date':
        plan.actual_end_date, 'created_at': plan.created_at, 'updated_at':
        plan.updated_at, 'total_phases': total_phases, 'total_tasks':
        total_tasks, 'estimated_duration_weeks': estimated_duration_weeks}
    return plan_dict


@router.get('/plans', response_model=ImplementationPlanListResponse)
async def list_plans(current_user: User=Depends(get_current_active_user),
    db: AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    plans = await list_implementation_plans(db, current_user)
    return {'plans': plans}


@router.get('/plans/{id}', response_model=ImplementationPlanResponse)
async def get_plan(id: UUID, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Any:
    plan = await get_implementation_plan(db, current_user, id)
    if not plan:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
            'Implementation plan not found')
    total_phases = len(plan.phases) if plan.phases else 0
    total_tasks = sum(len(phase.get('tasks', [])) for phase in plan.phases
        ) if plan.phases else 0
    all_tasks = []
    for phase in plan.phases:
        for task in phase.get('tasks', []):
            all_tasks.append(task)
    estimated_duration_weeks = sum(phase.get('duration_weeks', 0) for phase in
        plan.phases) if plan.phases else 12
    plan_dict = {'id': plan.id, 'user_id': plan.user_id,
        'business_profile_id': plan.business_profile_id, 'framework_id':
        plan.framework_id, 'title': plan.title, 'status': plan.status,
        'phases': plan.phases, 'planned_start_date': plan.
        planned_start_date, 'planned_end_date': plan.planned_end_date,
        'actual_start_date': plan.actual_start_date, 'actual_end_date':
        plan.actual_end_date, 'created_at': plan.created_at, 'updated_at':
        plan.updated_at, 'total_phases': total_phases, 'total_tasks':
        total_tasks, 'estimated_duration_weeks': estimated_duration_weeks,
        'tasks': all_tasks}
    return plan_dict


@router.patch('/plans/{plan_id}/tasks/{task_id}')
async def update_task(plan_id: UUID, task_id: str, task_update:
    ImplementationTaskUpdate, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    plan = await update_task_status(db, current_user, plan_id, task_id,
        task_update.status)
    if not plan:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
            'Implementation plan not found')
    return {'message': 'Task updated', 'plan_id': plan_id, 'task_id': task_id}


async def get_implementation_recommendations(framework: str=None,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Dict[str, Any]:
    """Get AI-powered implementation recommendations based on current state."""
    from datetime import datetime, timezone
    return {'recommendations': [{'id': 'rec_001', 'priority': 'high',
        'category': 'quick_wins', 'title': 'Enable Audit Logging',
        'description':
        'Enable comprehensive audit logging across all systems',
        'estimated_effort_hours': 4, 'impact_score': 8, 'dependencies': [],
        'automation_available': True}, {'id': 'rec_002', 'priority':
        'medium', 'category': 'security', 'title': 'Implement MFA',
        'description':
        'Deploy multi-factor authentication for all user accounts',
        'estimated_effort_hours': 8, 'impact_score': 9, 'dependencies': [
        'user_management_system'], 'automation_available': False}, {'id':
        'rec_003', 'priority': 'low', 'category': 'documentation', 'title':
        'Update Security Policies', 'description':
        'Review and update information security policies',
        'estimated_effort_hours': 12, 'impact_score': 6, 'dependencies': [],
        'automation_available': True}], 'framework': framework,
        'total_recommendations': 3, 'estimated_total_hours': 24,
        'quick_wins_count': 1, 'automation_opportunities': 2,
        'generated_at': datetime.now(timezone.utc).isoformat()}


@router.get('/resources/{frameworkId}', summary='Get implementation resources')
async def get_implementation_resources(frameworkId: str, current_user: User
    =Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Dict[str, Any]:
    """Get resources and templates for framework implementation."""
    from datetime import datetime
    return {'framework_id': frameworkId, 'resources': {'templates': [{'id':
        'tpl_001', 'name': 'Risk Assessment Template', 'type': 'document',
        'format': 'docx', 'size_kb': 245, 'download_url':
        f'/api/v1/resources/{frameworkId}/templates/risk-assessment.docx'},
        {'id': 'tpl_002', 'name': 'Policy Templates Bundle', 'type':
        'bundle', 'format': 'zip', 'size_kb': 1024, 'download_url':
        f'/api/v1/resources/{frameworkId}/templates/policies-bundle.zip'}],
        'guides': [{'id': 'guide_001', 'title':
        f'{frameworkId} Implementation Guide', 'description':
        'Step-by-step guide for implementing {frameworkId}', 'pages': 45,
        'format': 'pdf', 'url':
        f'/api/v1/resources/{frameworkId}/guides/implementation-guide.pdf'},
        {'id': 'guide_002', 'title': 'Quick Start Checklist', 'description':
        'Essential checklist for getting started', 'pages': 5, 'format':
        'pdf', 'url':
        f'/api/v1/resources/{frameworkId}/guides/quick-start.pdf'}],
        'tools': [{'id': 'tool_001', 'name': 'Gap Analysis Spreadsheet',
        'description': 'Excel tool for conducting gap analysis', 'type':
        'spreadsheet', 'download_url':
        f'/api/v1/resources/{frameworkId}/tools/gap-analysis.xlsx'}],
        'videos': [{'id': 'vid_001', 'title':
        f'Understanding {frameworkId}', 'duration_minutes': 15, 'url':
        f'https://videos.example.com/{frameworkId}-intro', 'thumbnail':
        f'https://thumbnails.example.com/{frameworkId}-intro.jpg'}]},
        'total_resources': 7, 'last_updated': datetime.now(timezone.utc).
        isoformat()}


@router.get('/plans/{planId}/analytics', summary='Get plan analytics')
async def get_implementation_plan_analytics(planId: UUID, current_user:
    User=Depends(get_current_active_user), db: AsyncSession=Depends(
    get_async_db)) ->Dict[str, Any]:
    """Get detailed analytics for an implementation plan."""
    from datetime import datetime, timedelta
    return {'plan_id': str(planId), 'analytics': {'progress': {
        'overall_completion': 67, 'phases_completed': 2, 'phases_total': 5,
        'tasks_completed': 24, 'tasks_total': 36, 'on_track': True},
        'timeline': {'planned_start': (datetime.now(timezone.utc) -
        timedelta(days=30)).isoformat(), 'planned_end': (datetime.now(
        timezone.utc) + timedelta(days=60)).isoformat(), 'actual_start': (
        datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        'projected_end': (datetime.now(timezone.utc) + timedelta(days=65)).
        isoformat(), 'days_behind_schedule': 5}, 'effort': {'planned_hours':
        240, 'actual_hours': 165, 'remaining_hours': 75, 'efficiency_ratio':
        0.92}, 'risks': [{'id': 'risk_001', 'category': 'resource',
        'description': 'Key team member availability', 'impact': 'high',
        'likelihood': 'medium', 'mitigation': 'Cross-train team members'}],
        'recommendations': [
        'Accelerate documentation tasks to get back on schedule',
        'Consider automation for testing phase',
        'Schedule checkpoint review for next week'], 'quality_metrics': {
        'tasks_passed_review': 22, 'tasks_requiring_rework': 2,
        'quality_score': 91.7}}, 'generated_at': datetime.now(timezone.utc)
        .isoformat()}
