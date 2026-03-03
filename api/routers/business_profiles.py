from typing import Any, Dict
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from api.dependencies.database import get_async_db
from api.dependencies.auth import get_current_user, require_auth
from services.data_access import DataAccess
from services.security.audit_logging import AuditLoggingService as AuditLogger
from database.db_setup import get_db
from api.schemas.models import BusinessProfileCreate, BusinessProfileResponse, BusinessProfileUpdate
from database.business_profile import BusinessProfile
from utils.input_validation import validate_business_profile_update, ValidationError

# Constants
HTTP_BAD_REQUEST = 400

router = APIRouter()


@router.post('/', response_model=BusinessProfileResponse, status_code=
    status.HTTP_201_CREATED)
@require_auth
async def create_business_profile(profile: BusinessProfileCreate,
    current_user=Depends(get_current_user), db: AsyncSession=Depends(
    get_async_db)) ->Any:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id ==
        current_user.id)
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing:
        profile_data = profile.model_dump()
        try:
            validated_data = validate_business_profile_update(profile_data)
        except ValidationError as e:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
        ALLOWED_FIELDS = ['company_name', 'industry', 'company_size',
            'description', 'data_sensitivity', 'geographic_scope',
            'target_frameworks']
        for key, value in validated_data.items():
            if key in ALLOWED_FIELDS:
                setattr(existing, key, value)
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        profile_data = profile.model_dump()
        try:
            validated_data = validate_business_profile_update(profile_data)
        except ValidationError as e:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
        db_profile = BusinessProfile(id=uuid4(), user_id=current_user.id,
            **validated_data)
        db.add(db_profile)
        await db.commit()
        await db.refresh(db_profile)
        return db_profile


@router.get('/', response_model=BusinessProfileResponse)
@require_auth
async def get_business_profile(current_user=Depends(get_current_user), db:
    AsyncSession=Depends(get_async_db)) ->Any:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id ==
        current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            'Business profile not found')
    return profile


@router.get('/{id}', response_model=BusinessProfileResponse)
@require_auth
async def get_business_profile_by_id(id: UUID, current_user=Depends(
    get_current_user), db: AsyncSession=Depends(get_async_db), sync_db:
    Session=Depends(get_db)) ->Any:
    """Get a specific business profile by ID - ownership check for SMBs."""
    profile = await DataAccess.ensure_owner_async(db, BusinessProfile, id,
        current_user, 'business profile')
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='business_profile', resource_id=str(id), action='read', db
        =sync_db)
    return profile


@router.put('/', response_model=BusinessProfileResponse)
@require_auth
async def update_business_profile(profile_update: BusinessProfileUpdate,
    current_user=Depends(get_current_user), db: AsyncSession=Depends(
    get_async_db), sync_db: Session=Depends(get_db)) ->Any:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id ==
        current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=
            'Business profile not found')
    update_data = profile_update.model_dump(exclude_unset=True)
    update_data.pop('data_sensitivity', None)
    try:
        validated_data = validate_business_profile_update(update_data)
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    ALLOWED_FIELDS = ['company_name', 'industry', 'company_size',
        'description', 'data_sensitivity', 'geographic_scope',
        'target_frameworks']
    for key, value in validated_data.items():
        if key in ALLOWED_FIELDS:
            setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put('/{id}', response_model=BusinessProfileResponse)
@require_auth
async def update_business_profile_by_id(profile_id: UUID, profile_update:
    BusinessProfileUpdate, current_user=Depends(get_current_user), db:
    AsyncSession=Depends(get_async_db), sync_db: Session=Depends(get_db)
    ) ->Any:
    """Update a specific business profile by ID - SMB ownership check."""
    profile = await DataAccess.ensure_owner_async(db, BusinessProfile,
        profile_id, current_user, 'business profile')
    update_data = profile_update.model_dump(exclude_unset=True)
    update_data.pop('data_sensitivity', None)
    try:
        validated_data = validate_business_profile_update(update_data)
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    ALLOWED_FIELDS = ['company_name', 'industry', 'company_size',
        'description', 'data_sensitivity', 'geographic_scope',
        'target_frameworks']
    for key, value in validated_data.items():
        if key in ALLOWED_FIELDS:
            setattr(profile, key, value)
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='business_profile', resource_id=str(profile_id), action=
        'update', metadata={'changed_fields': list(validated_data.keys())},
        db=sync_db)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete('/{id}')
@require_auth
async def delete_business_profile_by_id(profile_id: UUID, current_user=
    Depends(get_current_user), db: AsyncSession=Depends(get_async_db),
    sync_db: Session=Depends(get_db)) ->Dict[str, Any]:
    """Delete a specific business profile by ID - SMB ownership check."""
    await DataAccess.delete_owned_async(db, BusinessProfile, profile_id,
        current_user, 'business profile')
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='business_profile', resource_id=str(profile_id), action=
        'delete', db=sync_db)
    return {'message': 'Business profile deleted successfully'}


@router.get('/list', summary='List all business profiles')
@require_auth
async def list_business_profiles(limit: int=10, offset: int=0, current_user
    =Depends(get_current_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """List all business profiles owned by the current user (SMB model)."""
    profiles = await DataAccess.list_owned_async(db, BusinessProfile,
        current_user, limit, offset)
    return {'profiles': [{'id': str(profile.id), 'company_name': profile.
        company_name, 'industry': profile.industry, 'company_size': profile
        .company_size, 'created_at': profile.created_at.isoformat() if
        hasattr(profile, 'created_at') else None, 'updated_at': profile.
        updated_at.isoformat() if hasattr(profile, 'updated_at') else None} for
        profile in profiles], 'total': len(profiles), 'limit': limit,
        'offset': offset}


@router.get('/{id}/compliance-status', summary=
    'Get compliance status for profile')
@require_auth
async def get_profile_compliance_status(profile_id: UUID, current_user=
    Depends(get_current_user), db: AsyncSession=Depends(get_async_db),
    sync_db: Session=Depends(get_db)) ->Dict[str, Any]:
    """Get compliance status for a specific business profile."""
    await DataAccess.ensure_owner_async(db, BusinessProfile, profile_id,
        current_user, 'business profile')
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='compliance_status', resource_id=str(profile_id), action=
        'read', db=sync_db)
    return {'profile_id': str(profile_id), 'overall_compliance': 75,
        'frameworks': [{'name': 'GDPR', 'compliance_level': 80, 'status':
        'Good', 'last_assessment': '2024-01-10T10:00:00Z'}, {'name':
        'ISO 27001', 'compliance_level': 70, 'status': 'Fair',
        'last_assessment': '2024-01-08T14:30:00Z'}], 'risk_level': 'Medium',
        'action_items': 5}


@router.get('/{id}/team', summary='Get team members for profile')
@require_auth
async def get_profile_team(profile_id: UUID, current_user=Depends(
    get_current_user), db: AsyncSession=Depends(get_async_db)) ->Dict[str, Any
    ]:
    """Get team members associated with a business profile (SMB: typically 1-5 users)."""
    await DataAccess.ensure_owner_async(db, BusinessProfile, profile_id,
        current_user, 'business profile')
    return {'profile_id': str(profile_id), 'team_members': [{'user_id': str
        (current_user.id), 'email': current_user.email, 'role': 'Owner',
        'permissions': ['full_access'], 'joined_at': '2024-01-01T00:00:00Z'
        }], 'total_members': 1, 'pending_invites': 0}


@router.post('/{id}/invite', summary='Invite team member to profile')
@require_auth
async def invite_team_member(profile_id: UUID, invite_data: dict,
    current_user=Depends(get_current_user), db: AsyncSession=Depends(
    get_async_db), sync_db: Session=Depends(get_db)) ->Dict[str, Any]:
    """Invite a team member to a business profile (future feature for SMBs)."""
    await DataAccess.ensure_owner_async(db, BusinessProfile, profile_id,
        current_user, 'business profile')
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='team_invite', resource_id=str(profile_id), action=
        'create', metadata={'invited_email': invite_data.get('email', '')},
        db=sync_db)
    email = invite_data.get('email', '')
    role = invite_data.get('role', 'viewer')
    from uuid import uuid4
    from datetime import datetime, timezone
    invite_id = str(uuid4())
    return {'invite_id': invite_id, 'profile_id': str(profile_id),
        'invited_email': email, 'role': role, 'status': 'pending',
        'invited_by': current_user.email, 'invited_at': datetime.now(
        timezone.utc).isoformat(), 'expires_at': '2024-01-22T00:00:00Z',
        'note': 'Team invites coming soon for SMB collaboration'}


@router.get('/{id}/activity', summary='Get activity log for profile')
@require_auth
async def get_profile_activity(profile_id: UUID, limit: int=20,
    current_user=Depends(get_current_user), db: AsyncSession=Depends(
    get_async_db), sync_db: Session=Depends(get_db)) ->Dict[str, Any]:
    """Get activity log for a business profile."""
    await DataAccess.ensure_owner_async(db, BusinessProfile, profile_id,
        current_user, 'business profile')
    return {'profile_id': str(profile_id), 'activities': [{'activity_id':
        'act_001', 'type': 'profile_updated', 'description':
        'Business profile information updated', 'user': current_user.email,
        'timestamp': '2024-01-15T14:30:00Z'}, {'activity_id': 'act_002',
        'type': 'assessment_completed', 'description':
        'GDPR compliance assessment completed', 'user': current_user.email,
        'timestamp': '2024-01-14T10:00:00Z'}, {'activity_id': 'act_003',
        'type': 'evidence_uploaded', 'description':
        'New evidence document uploaded', 'user': current_user.email,
        'timestamp': '2024-01-13T16:45:00Z'}], 'total': 3, 'limit': limit}


@router.patch('/{id}', response_model=BusinessProfileResponse)
@require_auth
async def patch_business_profile(profile_id: UUID, profile_update:
    BusinessProfileUpdate, current_user=Depends(get_current_user), db:
    AsyncSession=Depends(get_async_db), sync_db: Session=Depends(get_db)
    ) ->Any:
    """Update a specific business profile by ID with partial data - SMB ownership check."""
    profile = await DataAccess.ensure_owner_async(db, BusinessProfile,
        profile_id, current_user, 'business profile')
    update_data = profile_update.model_dump(exclude_unset=True)
    update_data.pop('data_sensitivity', None)
    if 'version' in update_data:
        expected_version = update_data.pop('version')
        current_version = getattr(profile, 'version', 1)
        if expected_version != current_version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                detail={'error': {'message':
                'Conflict: Profile has been modified by another user'}})
    try:
        validated_data = validate_business_profile_update(update_data)
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    ALLOWED_FIELDS = ['company_name', 'industry', 'company_size',
        'description', 'data_sensitivity', 'geographic_scope',
        'target_frameworks']
    for key, value in validated_data.items():
        if key in ALLOWED_FIELDS:
            setattr(profile, key, value)
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='business_profile', resource_id=str(profile_id), action=
        'update', metadata={'changed_fields': list(validated_data.keys())},
        db=sync_db)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get('/{id}/compliance', summary=
    'Get compliance status for business profile')
@require_auth
async def get_profile_compliance(id: UUID, current_user=Depends(
    get_current_user), db: AsyncSession=Depends(get_async_db), sync_db:
    Session=Depends(get_db)) ->Dict[str, Any]:
    """Get compliance status for a specific business profile."""
    await DataAccess.ensure_owner_async(db, BusinessProfile, id,
        current_user, 'business profile')
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(user_id=str(current_user.id),
        resource='compliance_report', resource_id=str(id), action='view',
        db=sync_db)
    return {'profile_id': str(id), 'compliance_status': {'gdpr': {'score':
        75, 'status': 'partial', 'last_assessment': '2024-01-15T10:30:00Z'},
        'iso27001': {'score': 82, 'status': 'partial', 'last_assessment':
        '2024-01-10T14:20:00Z'}, 'pci_dss': {'score': 65, 'status':
        'non_compliant', 'last_assessment': '2024-01-05T09:15:00Z'}},
        'overall_score': 74, 'high_risk_areas': ['data_retention',
        'access_controls', 'encryption'], 'recommendations': [
        'Implement data retention policies',
        'Strengthen access control mechanisms',
        'Enable encryption at rest for sensitive data']}
