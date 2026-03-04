"""

RBAC-Enhanced Authentication Dependencies

Extends the base authentication system with role-based access control,
including role claims in JWT tokens and permission-based access control.
"""
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import create_access_token, create_refresh_token, decode_token, oauth2_scheme, get_current_user as base_get_current_user
from core.exceptions import NotAuthenticatedException
from database.db_setup import get_async_db, get_db
from database.user import User
from services.rbac_service import RBACService
logger = logging.getLogger(__name__)


class UserWithRoles:
    """
    Enhanced user object that includes role and permission information.
    """

    def __init__(self, user: User, roles: List[Dict], permissions: List[str
        ], accessible_frameworks: List[Dict]) ->None:
        self.user = user
        self.roles = roles
        self.permissions = permissions
        self.accessible_frameworks = accessible_frameworks
        self.id = user.id
        self.email = user.email
        self.is_active = user.is_active
        self.created_at = user.created_at

    def has_permission(self, permission: str) ->bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def has_any_permission(self, permissions: List[str]) ->bool:
        """Check if user has any of the specified permissions."""
        return any(perm in self.permissions for perm in permissions)

    def has_all_permissions(self, permissions: List[str]) ->bool:
        """Check if user has all of the specified permissions."""
        return all(perm in self.permissions for perm in permissions)

    def has_role(self, role_name: str) ->bool:
        """Check if user has a specific role."""
        return any(role['name'] == role_name for role in self.roles)

    def has_any_role(self, role_names: List[str]) ->bool:
        """Check if user has any of the specified roles."""
        return any(self.has_role(role) for role in role_names)

    def can_access_framework(self, framework_id: str, required_level: str=
        'read') ->bool:
        """Check if user can access a specific framework."""
        level_hierarchy = {'read': 1, 'write': 2, 'admin': 3}
        required_level_value = level_hierarchy.get(required_level, 1)
        for framework in self.accessible_frameworks:
            if framework['id'] == framework_id:
                access_level_value = level_hierarchy.get(framework[
                    'access_level'], 1)
                return access_level_value >= required_level_value
        return False

    def to_dict(self) ->Dict:
        """Convert to dictionary for JSON serialization."""
        return {'id': str(self.id), 'email': self.email, 'is_active': self.
            is_active, 'created_at': self.created_at.isoformat() if self.
            created_at else None, 'roles': self.roles, 'permissions': self.
            permissions, 'accessible_frameworks': self.accessible_frameworks}


def create_access_token_with_roles(user_id: UUID, roles: List[Dict],
    permissions: List[str]) ->str:
    """
    Create access token with embedded role and permission claims.

    Args:
        user_id: User ID
        roles: List of user roles
        permissions: List of user permissions

    Returns:
        JWT access token with role claims
    """
    role_claims = {'roles': [role['name'] for role in roles], 'permissions':
        permissions, 'role_details': roles}
    token_data = {'sub': str(user_id), 'roles': role_claims['roles'],
        'permissions': permissions, 'role_details': role_claims['role_details'],
        }
    return create_access_token(token_data)


def create_refresh_token_with_roles(user_id: UUID) ->str:
    """
    Create refresh token (roles will be re-evaluated on refresh).

    Args:
        user_id: User ID

    Returns:
        JWT refresh token
    """
    return create_refresh_token({'sub': str(user_id)})


async def get_current_user_with_roles(token: Optional[str]=Depends(
    oauth2_scheme), async_db: AsyncSession=Depends(get_async_db)) ->Optional[
    UserWithRoles]:
    """
    Get current user with role and permission information from token.

    Args:
        token: JWT access token
        async_db: Async database session

    Returns:
        UserWithRoles instance or None if not authenticated
    """
    if token is None:
        return None
    try:
        user = await base_get_current_user(token, async_db)
        if not user:
            return None
        sync_db = next(get_db())
        try:
            rbac = RBACService(sync_db)
            roles = rbac.get_user_roles(user.id)
            permissions = rbac.get_user_permissions(user.id)
            accessible_frameworks = rbac.get_accessible_frameworks(user.id)
            payload = decode_token(token)
            token_roles = set(payload.get('roles', []))
            current_roles = set(role['name'] for role in roles)
            if token_roles != current_roles:
                logger.warning(
                    'Token roles mismatch for user %s: token=%s, db=%s' % (
                    user.id, token_roles, current_roles))
            return UserWithRoles(user, roles, permissions,
                accessible_frameworks)
        finally:
            sync_db.close()
    except NotAuthenticatedException:
        return None


async def get_current_active_user_with_roles(current_user: Optional[
    UserWithRoles]=Depends(get_current_user_with_roles)) ->UserWithRoles:
    """
    Get current active user with roles, raising exception if not authenticated.

    Args:
        current_user: Current user with roles

    Returns:
        UserWithRoles instance

    Raises:
        HTTPException: If not authenticated or user is inactive
    """
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Not authenticated', headers={'WWW-Authenticate': 'Bearer'})
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=
            'Inactive user')
    return current_user


def require_permission(permission: str) ->Any:
    """
    Dependency factory for requiring specific permissions.

    Args:
        permission: Required permission name

    Returns:
        FastAPI dependency function
    """

    async def check_permission(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not current_user.has_permission(permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required")
        return current_user
    return check_permission


def require_any_permission(permissions: List[str]) ->Any:
    """
    Dependency factory for requiring any of the specified permissions.

    Args:
        permissions: List of permission names (user needs at least one)

    Returns:
        FastAPI dependency function
    """

    async def check_permissions(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not current_user.has_any_permission(permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=
                f"One of these permissions required: {', '.join(permissions)}")
        return current_user
    return check_permissions


def require_all_permissions(permissions: List[str]) ->Any:
    """
    Dependency factory for requiring all of the specified permissions.

    Args:
        permissions: List of permission names (user needs all)

    Returns:
        FastAPI dependency function
    """

    async def check_permissions(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not current_user.has_all_permissions(permissions):
            missing = [p for p in permissions if not current_user.
                has_permission(p)]
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}")
        return current_user
    return check_permissions


def require_role(role: str) ->Any:
    """
    Dependency factory for requiring specific roles.

    Args:
        role: Required role name

    Returns:
        FastAPI dependency function
    """

    async def check_role(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not current_user.has_role(role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required")
        return current_user
    return check_role


def require_any_role(roles: List[str]) ->Any:
    """
    Dependency factory for requiring any of the specified roles.

    Args:
        roles: List of role names (user needs at least one)

    Returns:
        FastAPI dependency function
    """

    async def check_roles(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not current_user.has_any_role(roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(roles)}")
        return current_user
    return check_roles


def require_framework_access(framework_id: str, access_level: str='read'
    ) ->Any:
    """
    Dependency factory for requiring framework access.

    Args:
        framework_id: Framework ID to check access for
        access_level: Required access level (read, write, admin)

    Returns:
        FastAPI dependency function
    """

    async def check_framework_access(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not current_user.can_access_framework(framework_id, access_level):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=
                f'Framework access required: {framework_id} ({access_level})')
        return current_user
    return check_framework_access


def check_framework_access_permission(user: UserWithRoles, framework_id:
    str, required_level: str='read') ->bool:
    """
    Check if user has access to a specific framework with the required level.

    Args:
        user: User with roles and permissions
        framework_id: Framework ID to check
        required_level: Required access level (read, write, admin)

    Returns:
        True if user has required access level
    """
    level_hierarchy = {'read': 1, 'write': 2, 'admin': 3}
    required_level_value = level_hierarchy.get(required_level, 1)
    for framework in user.accessible_frameworks:
        if framework['id'] == str(framework_id):
            user_level_value = level_hierarchy.get(framework.get(
                'access_level', 'read'), 1)
            return user_level_value >= required_level_value
    return False


def require_framework_access_level(framework_id: str, access_level: str='read'
    ) ->Any:
    """
    Dependency factory for requiring framework access with specific level.

    Args:
        framework_id: Framework ID to check access for
        access_level: Required access level (read, write, admin)

    Returns:
        FastAPI dependency function
    """

    async def check_access(current_user: UserWithRoles=Depends(
        get_current_active_user_with_roles)) ->UserWithRoles:
        if not check_framework_access_permission(current_user, framework_id,
            access_level):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=
                f'Framework access required: {framework_id} ({access_level} level)',
                )
        return current_user
    return check_access


class RBACMiddleware:
    """
    Middleware for automatic RBAC enforcement and audit logging.
    """

    def __init__(self) ->None:
        self.protected_paths = {'/api/v1/admin': ['admin_roles',
            'admin_permissions', 'admin_audit'], '/api/v1/frameworks': [
            'framework_list'], '/api/v1/assessments': ['assessment_list'],
            '/api/v1/policies': ['policy_generate'], '/api/v1/reports': [
            'report_view']}

    async def check_path_permissions(self, path: str, user: UserWithRoles
        ) ->bool:
        """
        Check if user has permission to access a specific path.

        Args:
            path: Request path
            user: User with roles

        Returns:
            True if access allowed
        """
        for protected_path, required_permissions in self.protected_paths.items(
            ):
            if path.startswith(protected_path):
                return user.has_any_permission(required_permissions)
        return True


get_current_user = get_current_user_with_roles
get_current_active_user = get_current_active_user_with_roles
