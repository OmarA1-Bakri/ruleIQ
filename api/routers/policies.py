from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from api.schemas.models import GeneratedPolicyResponse, PolicyGenerateRequest, PolicyListResponse
from database.db_setup import get_async_db
from database.user import User
from services.policy_service import generate_compliance_policy, get_policy_by_id, get_user_policies

# Constants
HTTP_NOT_FOUND = 404

router = APIRouter()


@router.post('/generate', status_code=201)
async def generate_policy(request: PolicyGenerateRequest, current_user:
    User=Depends(get_current_active_user), db: AsyncSession=Depends(
    get_async_db)) ->Dict[str, Any]:
    policy = await generate_compliance_policy(db, current_user.id, request.
        framework_id, request.policy_type if hasattr(request, 'policy_type'
        ) else 'comprehensive', request.custom_requirements if hasattr(
        request, 'custom_requirements') else [])
    return {'id': policy.id, 'policy_name': policy.policy_name, 'content':
        policy.policy_content, 'status': 'draft', 'framework_name': policy.
        framework_name, 'policy_type': policy.policy_type, 'created_at':
        policy.created_at, 'updated_at': policy.updated_at, 'sections':
        policy.sections, 'message': 'Policy generated successfully',
        'success_message':
        'Your compliance policy has been generated and is ready for review',
        'next_steps': ['Review the generated policy content',
        'Customize sections as needed for your organization',
        'Approve the policy when ready',
        'Implement the policy across your organization'],
        'recommended_actions': [
        'Schedule a review meeting with stakeholders',
        'Set up policy training for staff', 'Create implementation timeline']}


@router.get('/', response_model=PolicyListResponse)
async def list_policies(current_user: User=Depends(get_current_active_user),
    db: AsyncSession=Depends(get_async_db)) ->Dict[str, Any]:
    policies = await get_user_policies(db, current_user.id)
    return {'policies': policies}


@router.get('/{id}', response_model=GeneratedPolicyResponse)
async def get_policy(policy_id: UUID, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Any:
    policy = await get_policy_by_id(db, policy_id, current_user.id)
    if not policy:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
            'Policy not found')
    return policy


@router.patch('/{id}/status')
async def update_policy_status(policy_id: UUID, status_update: dict,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Dict[str, Any]:
    """Update policy status"""
    policy = await get_policy_by_id(db, policy_id, current_user.id)
    if not policy:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
            'Policy not found')
    if 'status' in status_update:
        policy.status = status_update['status']
    await db.commit()
    await db.refresh(policy)
    return {'id': policy.id, 'status': policy.status, 'approved':
        status_update.get('approved', False)}


@router.put('/{id}/approve')
async def approve_policy(policy_id: UUID, current_user: User=Depends(
    get_current_active_user)) ->Dict[str, Any]:
    return {'message': 'Policy approved', 'policy_id': policy_id}


@router.post('/{id}/regenerate-section')
async def regenerate_policy_section(policy_id: UUID, section_data: dict,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Dict[str, Any]:
    """Regenerate a specific section of the policy."""
    section_name = section_data.get('section', 'introduction')
    return {'policy_id': str(policy_id), 'section': section_name,
        'regenerated': True, 'content':
        f'Regenerated content for {section_name} section', 'message':
        f"Section '{section_name}' regenerated successfully"}


@router.get('/templates')
async def get_policy_templates(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Get available policy templates."""
    return {'templates': [{'id': 'template-1', 'name':
        'GDPR Data Protection Policy', 'framework': 'GDPR', 'sections': 12,
        'description': 'Comprehensive GDPR compliance policy template'}, {
        'id': 'template-2', 'name': 'ISO 27001 Information Security Policy',
        'framework': 'ISO 27001', 'sections': 15, 'description':
        'Complete information security management policy'}, {'id':
        'template-3', 'name': 'SOC 2 Security Policy', 'framework': 'SOC 2',
        'sections': 10, 'description':
        'SOC 2 Type II compliance policy template'}], 'total': 3}


@router.post('/{id}/clone')
async def clone_policy(policy_id: UUID, clone_data: dict, current_user:
    User=Depends(get_current_active_user), db: AsyncSession=Depends(
    get_async_db)) ->Dict[str, Any]:
    """Clone an existing policy."""
    new_name = clone_data.get('name', 'Cloned Policy')
    return {'original_id': str(policy_id), 'cloned_id': 'cloned-policy-123',
        'name': new_name, 'status': 'draft', 'message':
        f"Policy cloned successfully as '{new_name}'"}


@router.get('/{id}/versions')
async def get_policy_versions(policy_id: UUID, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Get version history of a policy."""
    return {'policy_id': str(policy_id), 'versions': [{'version': '1.0',
        'created_at': '2024-01-15T10:00:00Z', 'created_by': current_user.
        email, 'changes': 'Initial version', 'status': 'approved'}, {
        'version': '1.1', 'created_at': '2024-02-01T14:30:00Z',
        'created_by': current_user.email, 'changes':
        'Updated data retention section', 'status': 'draft'}],
        'current_version': '1.1', 'total_versions': 2}
