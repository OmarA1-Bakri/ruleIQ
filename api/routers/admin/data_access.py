"""

Data Access Management Router

Provides admin endpoints for managing data visibility and access controls.
Part of the RBAC system for UK compliance requirements.
"""

from typing import List, Optional, Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from api.dependencies.rbac_auth import UserWithRoles, require_permission
from database.db_setup import get_db
from services.data_access_service import DataAccessService

router = APIRouter(prefix="/api/v1/data-access", tags=["Data Access Management"])


class DataAccessRequest(BaseModel):
    user_id: UUID
    access_type: str
    business_profile_id: Optional[UUID] = None


class DataAccessResponse(BaseModel):
    id: str
    user_id: str
    access_type: str
    business_profile_id: Optional[str] = None
    granted_at: str
    granted_by: Optional[str] = None
    is_active: bool


class UserDataAccessInfo(BaseModel):
    user_id: str
    email: str
    access_level: str
    accessible_profiles: List[str]


@router.post("/grant", response_model=DataAccessResponse)
async def grant_data_access(
    request: DataAccessRequest,
    current_user: UserWithRoles = Depends(require_permission("admin_permissions")),
    db: Session = Depends(get_db),
) -> Any:
    """
    Grant data access to a user. Requires admin_permissions.
    """
    data_access_service = DataAccessService(db)
    try:
        data_access = data_access_service.grant_data_access(
            user_id=request.user_id,
            access_type=request.access_type,
            business_profile_id=request.business_profile_id,
            granted_by=current_user.id,
        )
        return DataAccessResponse(
            id=str(data_access.id),
            user_id=str(data_access.user_id),
            access_type=data_access.access_type,
            business_profile_id=str(data_access.business_profile_id)
            if data_access.business_profile_id
            else None,
            granted_at=data_access.granted_at.isoformat(),
            granted_by=str(data_access.granted_by) if data_access.granted_by else None,
            is_active=data_access.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/revoke")
async def revoke_data_access(
    user_id: UUID,
    business_profile_id: Optional[UUID] = None,
    current_user: UserWithRoles = Depends(require_permission("admin_permissions")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Revoke data access from a user. Requires admin_permissions.
    """
    data_access_service = DataAccessService(db)
    success = data_access_service.revoke_data_access(
        user_id=user_id, business_profile_id=business_profile_id
    )
    if success:
        return {"message": "Data access revoked successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data access record not found"
        )


@router.get("/user/{user_id}", response_model=UserDataAccessInfo)
async def get_user_data_access(
    user_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("admin_audit")),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get data access information for a specific user. Requires admin_audit permission.
    """
    from database.user import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data_access_service = DataAccessService(db)
    access_level = data_access_service.get_user_data_access_level(user_id)
    from services.rbac_service import RBACService

    rbac = RBACService(db)
    roles = rbac.get_user_roles(user_id)
    permissions = rbac.get_user_permissions(user_id)
    accessible_frameworks = rbac.get_accessible_frameworks(user_id)
    target_user_with_roles = UserWithRoles(user, roles, permissions, accessible_frameworks)
    accessible_profiles = data_access_service.get_accessible_business_profiles(
        target_user_with_roles
    )
    return UserDataAccessInfo(
        user_id=str(user_id),
        email=user.email,
        access_level=access_level,
        accessible_profiles=[str(profile_id) for profile_id in accessible_profiles],
    )


@router.get("/levels")
async def list_access_levels(
    current_user: UserWithRoles = Depends(require_permission("admin_audit")),
) -> Dict[str, Any]:
    """
    List available data access levels and their descriptions.
    """
    return {
        "access_levels": [
            {"level": "own_data", "description": "User can only access their own data"},
            {
                "level": "organization_data",
                "description": "User can access data within their organization",
            },
            {"level": "all_data", "description": "User can access all data (admin level)"},
        ]
    }


@router.get("/audit")
async def audit_data_access(
    current_user: UserWithRoles = Depends(require_permission("admin_audit")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get audit information about data access permissions.
    """
    from database.rbac import DataAccess
    from sqlalchemy import func

    total_access_records = db.query(func.count(DataAccess.id)).scalar()
    active_access_records = (
        db.query(func.count(DataAccess.id)).filter(DataAccess.is_active).scalar()
    )
    access_distribution = (
        db.query(DataAccess.access_type, func.count(DataAccess.id).label("count"))
        .filter(DataAccess.is_active)
        .group_by(DataAccess.access_type)
        .all()
    )
    return {
        "summary": {
            "total_access_records": total_access_records,
            "active_access_records": active_access_records,
        },
        "access_distribution": [
            {"access_type": item.access_type, "count": item.count} for item in access_distribution
        ],
    }
