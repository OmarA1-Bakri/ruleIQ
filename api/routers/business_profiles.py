import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.dependencies.database import get_async_db
from api.dependencies.auth import get_current_user, require_auth
from services.data_access import DataAccess
from services.security.audit_logging import AuditLoggingService as AuditLogger
from services.launch_metrics import (
    build_recommended_risks,
    build_recommended_tasks,
    calculate_framework_status,
    get_profile_frameworks,
    load_profile_framework_state,
)
from database.db_setup import get_db
from database.rbac import AuditLog
from api.schemas.models import BusinessProfileCreate, BusinessProfileResponse, BusinessProfileUpdate
from database.business_profile import BusinessProfile
from utils.input_validation import (
    FieldValidator,
    ValidationError,
    validate_business_profile_update,
)

# Constants
HTTP_BAD_REQUEST = 400
PROFILE_UPDATE_FIELDS = [
    "company_name",
    "industry",
    "employee_count",
    "annual_revenue",
    "country",
    "data_sensitivity",
    "handles_personal_data",
    "processes_payments",
    "stores_health_data",
    "provides_financial_services",
    "operates_critical_infrastructure",
    "has_international_operations",
    "cloud_providers",
    "saas_tools",
    "development_tools",
    "existing_frameworks",
    "planned_frameworks",
    "compliance_budget",
    "compliance_timeline",
    "assessment_completed",
    "assessment_data",
]
ACTIVITY_LOG_LIMIT = 50

router = APIRouter()


def _profile_state(profile: BusinessProfile) -> Dict[str, Any]:
    if isinstance(profile.assessment_data, dict):
        return dict(profile.assessment_data)
    return {}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_invite_emails(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        candidates = value
    else:
        normalized = str(value).replace(";", ",").replace("\n", ",")
        candidates = [item.strip() for item in normalized.split(",")]

    emails: List[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        validated = FieldValidator.validate_email(candidate)
        if validated not in emails:
            emails.append(validated)
    return emails


def _merge_assessment_state(
    current_state: Dict[str, Any], incoming_state: Dict[str, Any], current_user_email: str
) -> Dict[str, Any]:
    merged_state = {**current_state, **incoming_state}
    existing_invites = {
        invite.get("invited_email"): invite
        for invite in merged_state.get("team_invites", [])
        if isinstance(invite, dict) and invite.get("invited_email")
    }
    answers = incoming_state.get("answers") if isinstance(incoming_state.get("answers"), dict) else {}
    for email in _parse_invite_emails(answers.get("invite_emails")):
        if email in existing_invites:
            continue
        invited_at = datetime.now(timezone.utc)
        existing_invites[email] = {
            "invite_id": str(uuid4()),
            "invited_email": email,
            "role": "viewer",
            "status": "pending",
            "invited_by": current_user_email,
            "invited_at": invited_at.isoformat(),
            "expires_at": (invited_at + timedelta(days=7)).isoformat(),
        }
    merged_state["team_invites"] = list(existing_invites.values())
    return merged_state


def _append_profile_activity(
    profile: BusinessProfile,
    activity_type: str,
    description: str,
    user_email: str,
    metadata: Dict[str, Any] | None = None,
) -> None:
    state = _profile_state(profile)
    activity_log = state.get("activity_log", [])
    if not isinstance(activity_log, list):
        activity_log = []
    activity_log.insert(
        0,
        {
            "activity_id": f"act_{uuid4().hex[:12]}",
            "type": activity_type,
            "description": description,
            "user": user_email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        },
    )
    state["activity_log"] = activity_log[:ACTIVITY_LOG_LIMIT]
    profile.assessment_data = state


async def _build_compliance_snapshot(
    profile: BusinessProfile,
    current_user: Any,
    db: AsyncSession,
) -> Dict[str, Any]:
    frameworks = await get_profile_frameworks(db, profile)
    framework_state = await load_profile_framework_state(db, current_user.id, profile, frameworks)
    framework_statuses = [
        calculate_framework_status(
            framework,
            framework_state["evidence"].get(framework.id, []),
            framework_state["policies"].get(framework.id, []),
            framework_state["plans"].get(framework.id, []),
            framework_state["assessments"].get(framework.id),
        )
        for framework in frameworks
    ]

    overall_compliance = round(
        sum(item["overall_compliance_percentage"] for item in framework_statuses)
        / max(len(framework_statuses), 1),
        2,
    )
    risks = build_recommended_risks(profile.id, framework_statuses)
    tasks = build_recommended_tasks(profile.id, framework_statuses)
    recommendations: List[str] = []
    for item in framework_statuses:
        for recommendation in item.get("recommendations", []):
            if recommendation not in recommendations:
                recommendations.append(recommendation)

    return {
        "overall_compliance": overall_compliance,
        "framework_statuses": framework_statuses,
        "tasks": tasks,
        "risks": risks,
        "recommendations": recommendations,
    }


def _team_snapshot(profile: BusinessProfile, current_user: Any) -> Dict[str, Any]:
    state = _profile_state(profile)
    stored_members = state.get("team_members", [])
    members = [
        {
            "user_id": str(current_user.id),
            "email": current_user.email,
            "role": "owner",
            "permissions": ["full_access"],
            "joined_at": _iso(profile.created_at),
        }
    ]
    if isinstance(stored_members, list):
        for member in stored_members:
            if isinstance(member, dict) and member.get("email") != current_user.email:
                members.append(member)

    pending_invites = state.get("team_invites", [])
    if not isinstance(pending_invites, list):
        pending_invites = []

    return {
        "profile_id": str(profile.id),
        "team_members": members,
        "total_members": len(members),
        "pending_invites": len(pending_invites),
        "invites": pending_invites,
    }


@router.post("/", response_model=BusinessProfileResponse, status_code=status.HTTP_201_CREATED)
@require_auth
async def create_business_profile(
    profile: BusinessProfileCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    existing = result.scalars().first()
    profile_data = profile.model_dump()
    if existing:
        try:
            validated_data = validate_business_profile_update(profile_data)
            validated_data["assessment_data"] = _merge_assessment_state(
                _profile_state(existing),
                validated_data.get("assessment_data", {}),
                current_user.email,
            )
        except ValidationError as e:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
        for key, value in validated_data.items():
            if key in PROFILE_UPDATE_FIELDS:
                setattr(existing, key, value)
        _append_profile_activity(
            existing,
            activity_type="profile_updated",
            description="Business profile updated during onboarding setup.",
            user_email=current_user.email,
        )
        await db.commit()
        await db.refresh(existing)
        return existing

    try:
        validated_data = validate_business_profile_update(profile_data)
        validated_data["assessment_data"] = _merge_assessment_state(
            {},
            validated_data.get("assessment_data", {}),
            current_user.email,
        )
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    db_profile = BusinessProfile(id=uuid4(), user_id=current_user.id, **validated_data)
    _append_profile_activity(
        db_profile,
        activity_type="profile_created",
        description="Business profile created.",
        user_email=current_user.email,
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile


@router.get("/", response_model=BusinessProfileResponse)
@require_auth
async def get_business_profile(
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_async_db)
) -> Any:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )
    return profile


@router.get("/owned", summary="List all business profiles")
@require_auth
async def list_owned_business_profiles(
    limit: int = 10,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    return await _list_business_profiles_impl(limit=limit, offset=offset, current_user=current_user, db=db)


@router.get("/{id}", response_model=BusinessProfileResponse)
@require_auth
async def get_business_profile_by_id(
    id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Any:
    """Get a specific business profile by ID - ownership check for SMBs."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, id, current_user, "business profile"
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="business_profile",
        resource_id=str(id),
        action="read",
        db=sync_db,
    )
    return profile


@router.put("/", response_model=BusinessProfileResponse)
@require_auth
async def update_business_profile(
    profile_update: BusinessProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Any:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found"
        )
    update_data = profile_update.model_dump(exclude_unset=True)
    try:
        validated_data = validate_business_profile_update(update_data)
        if "assessment_data" in validated_data:
            validated_data["assessment_data"] = _merge_assessment_state(
                _profile_state(profile),
                validated_data["assessment_data"],
                current_user.email,
            )
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    for key, value in validated_data.items():
        if key in PROFILE_UPDATE_FIELDS:
            setattr(profile, key, value)
    _append_profile_activity(
        profile,
        activity_type="profile_updated",
        description="Business profile details updated.",
        user_email=current_user.email,
    )
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("/{profile_id}", response_model=BusinessProfileResponse)
@require_auth
async def update_business_profile_by_id(
    profile_id: UUID,
    profile_update: BusinessProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Any:
    """Update a specific business profile by ID - SMB ownership check."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    update_data = profile_update.model_dump(exclude_unset=True)
    try:
        validated_data = validate_business_profile_update(update_data)
        if "assessment_data" in validated_data:
            validated_data["assessment_data"] = _merge_assessment_state(
                _profile_state(profile),
                validated_data["assessment_data"],
                current_user.email,
            )
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    for key, value in validated_data.items():
        if key in PROFILE_UPDATE_FIELDS:
            setattr(profile, key, value)
    _append_profile_activity(
        profile,
        activity_type="profile_updated",
        description="Business profile updated from the profile detail view.",
        user_email=current_user.email,
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="business_profile",
        resource_id=str(profile_id),
        action="update",
        metadata={"changed_fields": list(validated_data.keys())},
        db=sync_db,
    )
    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
@require_auth
async def delete_business_profile_by_id(
    profile_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a specific business profile by ID - SMB ownership check."""
    await DataAccess.delete_owned_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="business_profile",
        resource_id=str(profile_id),
        action="delete",
        db=sync_db,
    )
    return {"message": "Business profile deleted successfully"}


async def _list_business_profiles_impl(
    limit: int = 10,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """List all business profiles owned by the current user (SMB model)."""
    profiles = await DataAccess.list_owned_async(db, BusinessProfile, current_user, limit, offset)
    return {
        "profiles": [
            {
                "id": str(profile.id),
                "company_name": profile.company_name,
                "industry": profile.industry,
                "employee_count": profile.employee_count,
                "created_at": profile.created_at.isoformat()
                if hasattr(profile, "created_at")
                else None,
                "updated_at": profile.updated_at.isoformat()
                if hasattr(profile, "updated_at")
                else None,
            }
            for profile in profiles
        ],
        "total": len(profiles),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{profile_id}/compliance-status", summary="Get compliance status for profile")
@require_auth
async def get_profile_compliance_status(
    profile_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get compliance status for a specific business profile."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="compliance_status",
        resource_id=str(profile_id),
        action="read",
        db=sync_db,
    )
    snapshot = await _build_compliance_snapshot(profile, current_user, db)
    highest_risk = next((risk for risk in snapshot["risks"] if risk["severity"] == "high"), None)
    return {
        "profile_id": str(profile_id),
        "overall_compliance": snapshot["overall_compliance"],
        "frameworks": [
            {
                "name": item["framework"],
                "compliance_level": item["overall_compliance_percentage"],
                "status": str(item["status"]).replace("_", " ").title(),
                "last_assessment": item["last_assessment_date"],
            }
            for item in snapshot["framework_statuses"]
        ],
        "risk_level": "High" if highest_risk else ("Medium" if snapshot["risks"] else "Low"),
        "action_items": len(snapshot["tasks"]),
    }


@router.get("/{profile_id}/team", summary="Get team members for profile")
@require_auth
async def get_profile_team(
    profile_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get team members associated with a business profile (SMB: typically 1-5 users)."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    return _team_snapshot(profile, current_user)


@router.post("/{profile_id}/invite", summary="Invite team member to profile")
@require_auth
async def invite_team_member(
    profile_id: UUID,
    invite_data: dict,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Invite a team member to a business profile."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    try:
        invited_email = FieldValidator.validate_email(invite_data.get("email", ""))
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    role = str(invite_data.get("role", "viewer")).strip().lower() or "viewer"
    state = _profile_state(profile)
    invites = state.get("team_invites", [])
    if not isinstance(invites, list):
        invites = []
    existing_invite = next(
        (invite for invite in invites if isinstance(invite, dict) and invite.get("invited_email") == invited_email),
        None,
    )
    if existing_invite:
        return existing_invite

    invited_at = datetime.now(timezone.utc)
    invite_record = {
        "invite_id": str(uuid4()),
        "profile_id": str(profile_id),
        "invited_email": invited_email,
        "role": role,
        "status": "pending",
        "invited_by": current_user.email,
        "invited_at": invited_at.isoformat(),
        "expires_at": (invited_at + timedelta(days=7)).isoformat(),
    }
    invites.append(invite_record)
    state["team_invites"] = invites
    profile.assessment_data = state
    _append_profile_activity(
        profile,
        activity_type="team_invited",
        description=f"Invited {invited_email} to collaborate on the business profile.",
        user_email=current_user.email,
        metadata={"role": role},
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="team_invite",
        resource_id=str(profile_id),
        action="create",
        metadata={"invited_email": invited_email, "role": role},
        db=sync_db,
    )
    await db.commit()
    await db.refresh(profile)
    return invite_record


@router.get("/{profile_id}/activity", summary="Get activity log for profile")
@require_auth
async def get_profile_activity(
    profile_id: UUID,
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get activity log for a business profile."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    state = _profile_state(profile)
    stored_activities = state.get("activity_log", [])
    if not isinstance(stored_activities, list):
        stored_activities = []
    audit_rows = (
        sync_db.query(AuditLog)
        .filter(AuditLog.resource_id == str(profile_id))
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    audit_activities = []
    for row in audit_rows:
        details = {}
        if row.details:
            try:
                details = json.loads(row.details)
            except json.JSONDecodeError:
                details = {}
        audit_activities.append(
            {
                "activity_id": str(row.id),
                "type": row.action.replace(":", "."),
                "description": f"{row.action.replace('_', ' ').title()} on {row.resource_type or 'resource'}",
                "user": current_user.email if row.user_id == current_user.id else "system",
                "timestamp": _iso(row.timestamp),
                "metadata": details.get("metadata", {}),
            }
        )
    activities = sorted(
        [*stored_activities, *audit_activities],
        key=lambda item: item.get("timestamp") or "",
        reverse=True,
    )[:limit]
    return {
        "profile_id": str(profile_id),
        "activities": activities,
        "total": len(activities),
        "limit": limit,
    }


@router.patch("/{profile_id}", response_model=BusinessProfileResponse)
@require_auth
async def patch_business_profile(
    profile_id: UUID,
    profile_update: BusinessProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Any:
    """Update a specific business profile by ID with partial data - SMB ownership check."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    update_data = profile_update.model_dump(exclude_unset=True)
    if "version" in update_data:
        expected_version = update_data.pop("version")
        current_version = getattr(profile, "version", 1)
        if expected_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {"message": "Conflict: Profile has been modified by another user"}
                },
            )
    try:
        validated_data = validate_business_profile_update(update_data)
        if "assessment_data" in validated_data:
            validated_data["assessment_data"] = _merge_assessment_state(
                _profile_state(profile),
                validated_data["assessment_data"],
                current_user.email,
            )
    except ValidationError as e:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))
    for key, value in validated_data.items():
        if key in PROFILE_UPDATE_FIELDS:
            setattr(profile, key, value)
    _append_profile_activity(
        profile,
        activity_type="profile_updated",
        description="Business profile patched with partial updates.",
        user_email=current_user.email,
        metadata={"changed_fields": list(validated_data.keys())},
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="business_profile",
        resource_id=str(profile_id),
        action="update",
        metadata={"changed_fields": list(validated_data.keys())},
        db=sync_db,
    )
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{profile_id}/compliance", summary="Get compliance status for business profile")
@require_auth
async def get_profile_compliance(
    profile_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get compliance status for a specific business profile."""
    profile = await DataAccess.ensure_owner_async(
        db, BusinessProfile, profile_id, current_user, "business profile"
    )
    audit_service = AuditLogger(sync_db)
    await audit_service.log_data_access(
        user_id=str(current_user.id),
        resource="compliance_report",
        resource_id=str(profile_id),
        action="view",
        db=sync_db,
    )
    snapshot = await _build_compliance_snapshot(profile, current_user, db)
    compliance_status = {
        item["framework_name"].lower().replace(" ", "_"): {
            "score": item["overall_compliance_percentage"],
            "status": item["status"],
            "last_assessment": item["last_assessment_date"],
        }
        for item in snapshot["framework_statuses"]
    }
    high_risk_areas = [risk["title"] for risk in snapshot["risks"][:3]]
    return {
        "profile_id": str(profile_id),
        "compliance_status": compliance_status,
        "overall_score": snapshot["overall_compliance"],
        "high_risk_areas": high_risk_areas,
        "recommendations": snapshot["recommendations"],
    }
