"""

RBAC-Enhanced Authentication Router

Provides authentication endpoints with role-based access control integration.
Extends base authentication with role claims in JWT tokens.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from api.dependencies.auth import verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from api.dependencies.rbac_auth import (
    create_access_token_with_roles,
    create_refresh_token_with_roles,
    get_current_active_user_with_roles,
    UserWithRoles,
    require_permission,
    require_any_permission,
)
from api.middleware.rate_limiter import auth_rate_limit, RateLimited
from database.db_setup import get_db
from database.user import User
from services.rbac_service import RBACService

router = APIRouter(tags=["RBAC Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


class UserInfoResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    created_at: str
    roles: List[Dict]
    permissions: List[str]
    accessible_frameworks: List[Dict]


class RoleAssignmentRequest(BaseModel):
    user_id: UUID
    role_id: UUID
    expires_at: Optional[str] = None


class RoleAssignmentResponse(BaseModel):
    success: bool
    message: str
    assignment_id: Optional[str] = None


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit())])
async def login_with_roles(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Any:
    """
    Authenticate user and return JWT tokens with role claims.

    The access token includes user roles and permissions for client-side
    authorization checks and server-side RBAC enforcement.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    rbac = RBACService(db)
    roles = rbac.get_user_roles(user.id)
    permissions = rbac.get_user_permissions(user.id)
    access_token = create_access_token_with_roles(user.id, roles, permissions)
    refresh_token = create_refresh_token_with_roles(user.id)
    rbac._log_audit(
        user_id=user.id,
        action="login_success",
        details={
            "email": user.email,
            "roles": [role["name"] for role in roles],
            "permissions_count": len(permissions),
        },
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login-form", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit())])
async def login_with_json(login_data: LoginRequest, db: Session = Depends(get_db)) -> Any:
    """
    Alternative login endpoint that accepts JSON payload.
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    rbac = RBACService(db)
    roles = rbac.get_user_roles(user.id)
    permissions = rbac.get_user_permissions(user.id)
    access_token = create_access_token_with_roles(user.id, roles, permissions)
    refresh_token = create_refresh_token_with_roles(user.id)
    rbac._log_audit(
        user_id=user.id,
        action="login_success",
        details={
            "email": user.email,
            "roles": [role["name"] for role in roles],
            "permissions_count": len(permissions),
        },
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: UserWithRoles = Depends(get_current_active_user_with_roles),
) -> Any:
    """
    Get current user information including roles and permissions.
    """
    return UserInfoResponse(
        id=str(current_user.id),
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
        roles=current_user.roles,
        permissions=current_user.permissions,
        accessible_frameworks=current_user.accessible_frameworks,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimited(requests=10, window=60))],
)
async def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)) -> Any:
    """
    Refresh access token using refresh token.

    Re-evaluates user roles and permissions to ensure token is up-to-date.
    """
    from api.dependencies.auth import decode_token

    try:
        payload = decode_token(refresh_token)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = UUID(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    rbac = RBACService(db)
    roles = rbac.get_user_roles(user.id)
    permissions = rbac.get_user_permissions(user.id)
    access_token = create_access_token_with_roles(user.id, roles, permissions)
    new_refresh_token = create_refresh_token_with_roles(user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/admin/assign-role",
    response_model=RoleAssignmentResponse,
    dependencies=[Depends(require_permission("admin_roles"))],
)
async def assign_role_to_user(
    assignment: RoleAssignmentRequest,
    current_user: UserWithRoles = Depends(get_current_active_user_with_roles),
    db: Session = Depends(get_db),
) -> Any:
    """
    Assign a role to a user. Requires admin_roles permission.
    """
    from datetime import datetime

    rbac = RBACService(db)
    try:
        expires_at = None
        if assignment.expires_at:
            expires_at = datetime.fromisoformat(assignment.expires_at)
        user_role = rbac.assign_role_to_user(
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            granted_by=current_user.id,
            expires_at=expires_at,
        )
        return RoleAssignmentResponse(
            success=True, message="Role assigned successfully", assignment_id=str(user_role.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/admin/revoke-role",
    response_model=RoleAssignmentResponse,
    dependencies=[Depends(require_permission("admin_roles"))],
)
async def revoke_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current_user: UserWithRoles = Depends(get_current_active_user_with_roles),
    db: Session = Depends(get_db),
) -> Any:
    """
    Revoke a role from a user. Requires admin_roles permission.
    """
    rbac = RBACService(db)
    success = rbac.revoke_role_from_user(
        user_id=user_id, role_id=role_id, revoked_by=current_user.id
    )
    if success:
        return RoleAssignmentResponse(success=True, message="Role revoked successfully")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found"
        )


@router.get(
    "/admin/user-roles/{user_id}",
    dependencies=[Depends(require_any_permission(["admin_roles", "user_list"]))],
)
async def get_user_roles(user_id: UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get roles for a specific user. Requires admin_roles or user_list permission.
    """
    rbac = RBACService(db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    roles = rbac.get_user_roles(user_id)
    permissions = rbac.get_user_permissions(user_id)
    accessible_frameworks = rbac.get_accessible_frameworks(user_id)
    return {
        "user_id": str(user_id),
        "email": user.email,
        "roles": roles,
        "permissions": permissions,
        "accessible_frameworks": accessible_frameworks,
    }


@router.post(
    "/admin/cleanup-expired-roles", dependencies=[Depends(require_permission("admin_roles"))]
)
async def cleanup_expired_roles(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Clean up expired role assignments. Requires admin_roles permission.
    """
    rbac = RBACService(db)

    def cleanup_task() -> int:
        expired_count = rbac.cleanup_expired_roles()
        return expired_count

    background_tasks.add_task(cleanup_task)
    return {"message": "Expired role cleanup initiated", "background_task": True}


@router.get("/permissions", dependencies=[Depends(get_current_active_user_with_roles)])
async def list_user_permissions(
    current_user: UserWithRoles = Depends(get_current_active_user_with_roles),
) -> Dict[str, Any]:
    """
    List current user's permissions for client-side authorization.
    """
    return {
        "permissions": current_user.permissions,
        "roles": [role["name"] for role in current_user.roles],
    }


@router.get("/framework-access", dependencies=[Depends(get_current_active_user_with_roles)])
async def list_accessible_frameworks(
    current_user: UserWithRoles = Depends(get_current_active_user_with_roles),
) -> Dict[str, Any]:
    """
    List frameworks accessible to current user.
    """
    return {"frameworks": current_user.accessible_frameworks}
