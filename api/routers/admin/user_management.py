"""

Admin User Management API

Comprehensive admin interface for managing users, roles, and permissions.
Provides full CRUD operations with RBAC enforcement and audit logging.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, distinct
from api.dependencies.rbac_auth import UserWithRoles, require_permission
from database.db_setup import get_db
from database.user import User
from database.rbac import Role, Permission, UserRole, RolePermission, AuditLog
from services.rbac_service import RBACService, initialize_rbac_system

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin", "user-management"])


class UserCreateRequest(BaseModel):
    """Request model for creating a new user."""

    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=8)
    is_active: bool = True
    is_verified: bool = False
    roles: List[str] = Field(default_factory=list, description="List of role names to assign")


class UserUpdateRequest(BaseModel):
    """Request model for updating a user."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(BaseModel):
    """Response model for user information."""

    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    roles: List[Dict[str, Any]]
    permissions: List[str]

    class Config:
        from_attributes = True


class RoleCreateRequest(BaseModel):
    """Request model for creating a new role."""

    name: str = Field(..., pattern="^[a-z][a-z0-9_]*$")
    display_name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    """Request model for updating a role."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    """Response model for role information."""

    id: str
    name: str
    display_name: str
    description: Optional[str]
    is_active: bool
    is_system_role: bool
    created_at: datetime
    permissions: List[Dict[str, Any]]
    user_count: int

    class Config:
        from_attributes = True


class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment."""

    user_id: UUID
    role_id: UUID
    expires_at: Optional[datetime] = None


class PermissionResponse(BaseModel):
    """Response model for permission information."""

    id: str
    name: str
    display_name: str
    description: Optional[str]
    category: str
    resource_type: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class AdminStatsResponse(BaseModel):
    """Response model for admin statistics."""

    total_users: int
    active_users: int
    verified_users: int
    total_roles: int
    system_roles: int
    custom_roles: int
    total_permissions: int
    recent_logins: int
    recent_registrations: int


class AuditLogResponse(BaseModel):
    """Response model for audit log entries."""

    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    severity: str
    created_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]

    class Config:
        from_attributes = True


@router.get("/", response_model=List[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by email or name"),
    role: Optional[str] = Query(None, description="Filter by role name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: UserWithRoles = Depends(require_permission("user_list")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all users with filtering and pagination."""
    rbac = RBACService(db)
    query = db.query(User)
    if search:
        search_filter = or_(User.email.ilike(f"%{search}%"), User.full_name.ilike(f"%{search}%"))
        query = query.filter(search_filter)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if role:
        query = query.join(UserRole).join(Role).filter(and_(Role.name == role, UserRole.is_active))
    offset = (page - 1) * limit
    users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
    user_responses = []
    for user in users:
        roles = rbac.get_user_roles(user.id)
        permissions = rbac.get_user_permissions(user.id)
        user_responses.append(
            UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_verified=user.is_verified,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login=user.last_login,
                roles=roles,
                permissions=permissions,
            )
        )
    return user_responses


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("user_list")),
    db: Session = Depends(get_db),
) -> Any:
    """Get a specific user by ID."""
    rbac = RBACService(db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    roles = rbac.get_user_roles(user.id)
    permissions = rbac.get_user_permissions(user.id)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        roles=roles,
        permissions=permissions,
    )


@router.post("/", response_model=UserResponse)
async def create_user(
    request: UserCreateRequest,
    current_user: UserWithRoles = Depends(require_permission("user_create")),
    db: Session = Depends(get_db),
) -> Any:
    """Create a new user with optional role assignments."""
    rbac = RBACService(db)
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists"
        )
    from api.dependencies.auth import get_password_hash

    hashed_password = get_password_hash(request.password)
    user = User(
        id=uuid4(),
        email=request.email,
        full_name=request.full_name,
        hashed_password=hashed_password,
        is_active=request.is_active,
        is_verified=request.is_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    roles_assigned = []
    for role_name in request.roles:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role:
            try:
                rbac.assign_role_to_user(
                    user_id=user.id, role_id=role.id, granted_by=current_user.id
                )
                roles_assigned.append(role_name)
            except ValueError as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning("Failed to assign role %s to user %s: %s" % (role_name, user.id, e))
    roles = rbac.get_user_roles(user.id)
    permissions = rbac.get_user_permissions(user.id)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        roles=roles,
        permissions=permissions,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    current_user: UserWithRoles = Depends(require_permission("user_update")),
    db: Session = Depends(get_db),
) -> Any:
    """Update a user's information."""
    rbac = RBACService(db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if request.email is not None:
        existing = (
            db.query(User).filter(and_(User.email == request.email, User.id != user_id)).first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use"
            )
        user.email = request.email
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.is_active is not None:
        user.is_active = request.is_active
    if request.is_verified is not None:
        user.is_verified = request.is_verified
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    roles = rbac.get_user_roles(user.id)
    permissions = rbac.get_user_permissions(user.id)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        roles=roles,
        permissions=permissions,
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("user_delete")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a user (soft delete by deactivating)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account"
        )
    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    rbac = RBACService(db)
    user_roles = (
        db.query(UserRole).filter(and_(UserRole.user_id == user_id, UserRole.is_active)).all()
    )
    for user_role in user_roles:
        rbac.revoke_role_from_user(
            user_id=user_id, role_id=user_role.role_id, revoked_by=current_user.id
        )
    db.commit()
    return {"message": "User deleted successfully"}


@router.get("/roles/", response_model=List[RoleResponse])
async def list_roles(
    current_user: UserWithRoles = Depends(require_permission("admin_roles")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all roles with permission and user count information."""
    roles_with_counts = (
        db.query(Role, func.count(distinct(UserRole.id)).label("user_count"))
        .outerjoin(UserRole, and_(Role.id == UserRole.role_id, UserRole.is_active))
        .filter(Role.is_active)
        .group_by(Role.id)
        .all()
    )
    role_responses = []
    for role, user_count in roles_with_counts:
        permissions = (
            db.query(Permission)
            .join(RolePermission)
            .filter(and_(RolePermission.role_id == role.id, Permission.is_active))
            .all()
        )
        permission_data = [
            {
                "id": str(perm.id),
                "name": perm.name,
                "display_name": perm.display_name,
                "category": perm.category,
            }
            for perm in permissions
        ]
        role_responses.append(
            RoleResponse(
                id=str(role.id),
                name=role.name,
                display_name=role.display_name,
                description=role.description,
                is_active=role.is_active,
                is_system_role=role.is_system_role,
                created_at=role.created_at,
                permissions=permission_data,
                user_count=user_count,
            )
        )
    return role_responses


@router.post("/roles/", response_model=RoleResponse)
async def create_role(
    request: RoleCreateRequest,
    current_user: UserWithRoles = Depends(require_permission("admin_roles")),
    db: Session = Depends(get_db),
) -> Any:
    """Create a new role with permissions."""
    rbac = RBACService(db)
    try:
        role = rbac.create_role(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            created_by=current_user.id,
        )
        permissions_assigned = []
        for permission_name in request.permissions:
            permission = db.query(Permission).filter(Permission.name == permission_name).first()
            if permission:
                try:
                    rbac.assign_permission_to_role(
                        role_id=role.id,
                        permission_id=permission.id,
                        granted_by=current_user.id,
                    )
                    permissions_assigned.append(
                        {
                            "id": str(permission.id),
                            "name": permission.name,
                            "display_name": permission.display_name,
                            "category": permission.category,
                        }
                    )
                except ValueError:
                    pass
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            is_active=role.is_active,
            is_system_role=role.is_system_role,
            created_at=role.created_at,
            permissions=permissions_assigned,
            user_count=0,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{user_id}/roles")
async def assign_role_to_user(
    user_id: UUID,
    request: RoleAssignmentRequest,
    current_user: UserWithRoles = Depends(require_permission("admin_roles")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Assign a role to a user."""
    rbac = RBACService(db)
    try:
        user_role = rbac.assign_role_to_user(
            user_id=request.user_id or user_id,
            role_id=request.role_id,
            granted_by=current_user.id,
            expires_at=request.expires_at,
        )
        return {
            "message": "Role assigned successfully",
            "assignment_id": str(user_role.id),
            "expires_at": user_role.expires_at.isoformat() if user_role.expires_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{user_id}/roles/{role_id}")
async def revoke_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current_user: UserWithRoles = Depends(require_permission("admin_roles")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Revoke a role from a user."""
    rbac = RBACService(db)
    success = rbac.revoke_role_from_user(
        user_id=user_id, role_id=role_id, revoked_by=current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found"
        )
    return {"message": "Role revoked successfully"}


@router.get("/statistics", response_model=AdminStatsResponse)
async def get_admin_statistics(
    current_user: UserWithRoles = Depends(require_permission("admin_audit")),
    db: Session = Depends(get_db),
) -> Any:
    """Get comprehensive admin statistics."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active).count()
    verified_users = db.query(User).filter(User.is_verified).count()
    total_roles = db.query(Role).filter(Role.is_active).count()
    system_roles = db.query(Role).filter(and_(Role.is_active, Role.is_system_role)).count()
    custom_roles = total_roles - system_roles
    total_permissions = db.query(Permission).filter(Permission.is_active).count()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_logins = db.query(User).filter(User.last_login >= week_ago).count()
    recent_registrations = db.query(User).filter(User.created_at >= week_ago).count()
    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        verified_users=verified_users,
        total_roles=total_roles,
        system_roles=system_roles,
        custom_roles=custom_roles,
        total_permissions=total_permissions,
        recent_logins=recent_logins,
        recent_registrations=recent_registrations,
    )


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    action: Optional[str] = Query(None, description="Filter by action type"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    current_user: UserWithRoles = Depends(require_permission("admin_audit")),
    db: Session = Depends(get_db),
) -> Any:
    """Get audit logs with filtering and pagination."""
    query = db.query(AuditLog)
    since_date = datetime.now(timezone.utc) - timedelta(days=days)
    query = query.filter(AuditLog.created_at >= since_date)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    offset = (page - 1) * limit
    audit_logs = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
    return [
        AuditLogResponse(
            id=str(log.id),
            user_id=str(log.user_id) if log.user_id else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            severity=log.severity,
            created_at=log.created_at,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
        )
        for log in audit_logs
    ]


@router.post("/initialize-rbac")
async def initialize_rbac_system_endpoint(
    current_user: UserWithRoles = Depends(require_permission("admin_roles")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Initialize RBAC system with default roles and permissions."""
    try:
        initialize_rbac_system(db)
        return {"message": "RBAC system initialized successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize RBAC system: {str(e)}",
        )


@router.post("/cleanup-expired-roles")
async def cleanup_expired_roles(
    current_user: UserWithRoles = Depends(require_permission("admin_roles")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Clean up expired role assignments."""
    rbac = RBACService(db)
    expired_count = rbac.cleanup_expired_roles()
    return {
        "message": f"Cleaned up {expired_count} expired role assignments",
        "expired_count": expired_count,
    }
