"""

# Constants



Test Suite for RBAC System

Comprehensive tests for role-based access control including:
- Database models and relationships
- RBAC service functionality
- Authentication with role claims
- API route protection
- Middleware enforcement
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from api.dependencies.rbac_auth import (
    UserWithRoles,
    create_access_token_with_roles,
    require_permission,
    require_any_permission,
)
from database.rbac import Role, Permission, UserRole, RolePermission, FrameworkAccess
from database.user import User
from services.rbac_service import RBACService

from tests.test_constants import HTTP_FORBIDDEN, MAX_RETRIES


class TestRBACModels:
    """Test RBAC database models and relationships."""

    def test_role_model_creation(self, db: Session):
        """Test Role model creation and basic properties."""
        role = Role(
            name="test_role",
            display_name="Test Role",
            description="Test role for unit testing",
            is_active=True,
        )
        db.add(role)
        db.commit()
        assert role.id is not None
        assert role.name == "test_role"
        assert role.description == "Test role for unit testing"
        assert role.is_active is True
        assert role.created_at is not None

    def test_permission_model_creation(self, db: Session):
        """Test Permission model creation."""
        permission = Permission(
            name="test_permission",
            display_name="Test Permission",
            description="Test permission for unit testing",
            category="test_category",
            resource_type="test_resource",
        )
        db.add(permission)
        db.commit()
        assert permission.id is not None
        assert permission.name == "test_permission"
        assert permission.category == "test_category"
        assert permission.resource_type == "test_resource"

    def test_user_role_assignment(self, db: Session):
        """Test UserRole relationship and assignment."""
        user = User(
            id=uuid4(), email="test@example.com", hashed_password="hashed_password", is_active=True
        )
        db.add(user)
        role = Role(name="test_role", display_name="Test Role", description="Test role")
        db.add(role)
        db.commit()
        user_role = UserRole(
            user_id=user.id,
            role_id=role.id,
            granted_by=user.id,
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(user_role)
        db.commit()
        assert user_role.id is not None
        assert user_role.user_id == user.id
        assert user_role.role_id == role.id
        assert user_role.is_active is True
        assert user_role.expires_at is not None

    def test_role_permission_assignment(self, db: Session):
        """Test RolePermission relationship."""
        role = Role(name="test_role", display_name="Test Role", description="Test role")
        permission = Permission(
            name="test_permission",
            display_name="Test Permission",
            description="Test permission",
            category="test",
            resource_type="test",
        )
        db.add_all([role, permission])
        db.commit()
        role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
        db.add(role_permission)
        db.commit()
        assert role_permission.id is not None
        assert role_permission.role_id == role.id
        assert role_permission.permission_id == permission.id

    def test_framework_access_model(self, db: Session):
        """Test FrameworkAccess model."""
        user = User(
            id=uuid4(), email="test@example.com", hashed_password="hashed_password", is_active=True
        )
        role = Role(name="test_role", display_name="Test Role", description="Test role")
        db.add_all([user, role])
        db.commit()
        from database.compliance_framework import ComplianceFramework

        framework = db.query(ComplianceFramework).filter_by(name="ISO27001").first()
        if not framework:
            framework = ComplianceFramework(
                name="ISO27001",
                display_name="ISO/IEC 27001:2022",
                description="Information security management systems",
                category="Information Security",
            )
            db.add(framework)
            db.commit()
        framework_access = FrameworkAccess(
            role_id=role.id, framework_id=framework.id, access_level="read", granted_by=user.id
        )
        db.add(framework_access)
        db.commit()
        assert framework_access.id is not None
        assert framework_access.framework_id == framework.id
        assert framework_access.access_level == "read"


class TestRBACService:
    """Test RBAC service functionality."""

    @pytest.fixture
    def rbac_service(self, db: Session):
        """Create RBAC service instance."""
        return RBACService(db)

    @pytest.fixture
    def test_user(self, db: Session):
        """Create test user."""
        user = User(
            id=uuid4(), email="test@example.com", hashed_password="hashed_password", is_active=True
        )
        db.add(user)
        db.commit()
        return user

    @pytest.fixture
    def test_role_with_permissions(self, db: Session):
        """Create test role with permissions."""
        role = Role(name="test_role", display_name="Test Role", description="Test role")
        db.add(role)
        db.flush()
        permissions = [
            Permission(
                name="user_list",
                display_name="List Users",
                description="List users",
                category="user_management",
                resource_type="user",
            ),
            Permission(
                name="user_create",
                display_name="Create User",
                description="Create user",
                category="user_management",
                resource_type="user",
            ),
        ]
        db.add_all(permissions)
        db.flush()
        for permission in permissions:
            role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
            db.add(role_permission)
        db.commit()
        return role

    def test_assign_role_to_user(
        self, rbac_service: RBACService, test_user: User, test_role_with_permissions: Role
    ):
        """Test assigning role to user."""
        user_role = rbac_service.assign_role_to_user(
            user_id=test_user.id, role_id=test_role_with_permissions.id, granted_by=test_user.id
        )
        assert user_role is not None
        assert user_role.user_id == test_user.id
        assert user_role.role_id == test_role_with_permissions.id
        assert user_role.is_active is True

    def test_get_user_roles(
        self, rbac_service: RBACService, test_user: User, test_role_with_permissions: Role
    ):
        """Test getting user roles."""
        rbac_service.assign_role_to_user(
            user_id=test_user.id, role_id=test_role_with_permissions.id, granted_by=test_user.id
        )
        roles = rbac_service.get_user_roles(test_user.id)
        assert len(roles) == 1
        assert roles[0]["name"] == "test_role"
        assert roles[0]["id"] == str(test_role_with_permissions.id)

    def test_get_user_permissions(
        self, rbac_service: RBACService, test_user: User, test_role_with_permissions: Role
    ):
        """Test getting user permissions."""
        rbac_service.assign_role_to_user(
            user_id=test_user.id, role_id=test_role_with_permissions.id, granted_by=test_user.id
        )
        permissions = rbac_service.get_user_permissions(test_user.id)
        assert len(permissions) == 2
        assert "user_list" in permissions
        assert "user_create" in permissions

    def test_user_has_permission(
        self, rbac_service: RBACService, test_user: User, test_role_with_permissions: Role
    ):
        """Test checking if user has specific permission."""
        rbac_service.assign_role_to_user(
            user_id=test_user.id, role_id=test_role_with_permissions.id, granted_by=test_user.id
        )
        assert rbac_service.user_has_permission(test_user.id, "user_list") is True
        assert rbac_service.user_has_permission(test_user.id, "user_create") is True
        assert rbac_service.user_has_permission(test_user.id, "admin_roles") is False

    def test_revoke_role_from_user(
        self, rbac_service: RBACService, test_user: User, test_role_with_permissions: Role
    ):
        """Test revoking role from user."""
        rbac_service.assign_role_to_user(
            user_id=test_user.id, role_id=test_role_with_permissions.id, granted_by=test_user.id
        )
        assert len(rbac_service.get_user_roles(test_user.id)) == 1
        success = rbac_service.revoke_role_from_user(
            user_id=test_user.id, role_id=test_role_with_permissions.id, revoked_by=test_user.id
        )
        assert success is True
        assert len(rbac_service.get_user_roles(test_user.id)) == 0

    def test_expired_role_cleanup(
        self, rbac_service: RBACService, test_user: User, test_role_with_permissions: Role
    ):
        """Test cleanup of expired roles."""
        user_role = rbac_service.assign_role_to_user(
            user_id=test_user.id,
            role_id=test_role_with_permissions.id,
            granted_by=test_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        roles = rbac_service.get_user_roles(test_user.id)
        assert len(roles) == 0
        expired_count = rbac_service.cleanup_expired_roles()
        assert expired_count >= 1


class TestUserWithRoles:
    """Test UserWithRoles class functionality."""

    @pytest.fixture
    def user_with_roles(self):
        """Create UserWithRoles instance for testing."""
        user = User(
            id=uuid4(), email="test@example.com", hashed_password="hashed_password", is_active=True
        )
        roles = [
            {"id": str(uuid4()), "name": "admin", "description": "Administrator"},
            {"id": str(uuid4()), "name": "user", "description": "Regular user"},
        ]
        permissions = ["user_list", "user_create", "admin_roles"]
        accessible_frameworks = [
            {"id": "iso27001", "name": "ISO 27001", "access_level": "admin"},
            {"id": "gdpr", "name": "GDPR", "access_level": "read"},
        ]
        return UserWithRoles(user, roles, permissions, accessible_frameworks)

    def test_has_permission(self, user_with_roles: UserWithRoles):
        """Test permission checking."""
        assert user_with_roles.has_permission("user_list") is True
        assert user_with_roles.has_permission("user_create") is True
        assert user_with_roles.has_permission("nonexistent_permission") is False

    def test_has_any_permission(self, user_with_roles: UserWithRoles):
        """Test checking for any of multiple permissions."""
        assert user_with_roles.has_any_permission(["user_list", "admin_roles"]) is True
        assert (user_with_roles.has_any_permission(["nonexistent1", "nonexistent2"]) is False,)
        assert user_with_roles.has_any_permission(["nonexistent", "user_list"]) is True

    def test_has_all_permissions(self, user_with_roles: UserWithRoles):
        """Test checking for all of multiple permissions."""
        assert user_with_roles.has_all_permissions(["user_list", "user_create"]) is True
        assert (user_with_roles.has_all_permissions(["user_list", "nonexistent"]) is False,)
        assert user_with_roles.has_all_permissions(["admin_roles"]) is True

    def test_has_role(self, user_with_roles: UserWithRoles):
        """Test role checking."""
        assert user_with_roles.has_role("admin") is True
        assert user_with_roles.has_role("user") is True
        assert user_with_roles.has_role("nonexistent_role") is False

    def test_has_any_role(self, user_with_roles: UserWithRoles):
        """Test checking for any of multiple roles."""
        assert user_with_roles.has_any_role(["admin", "manager"]) is True
        assert user_with_roles.has_any_role(["manager", "auditor"]) is False
        assert user_with_roles.has_any_role(["user"]) is True

    def test_can_access_framework(self, user_with_roles: UserWithRoles):
        """Test framework access checking."""
        assert user_with_roles.can_access_framework("iso27001", "read") is True
        assert user_with_roles.can_access_framework("iso27001", "write") is True
        assert user_with_roles.can_access_framework("iso27001", "admin") is True
        assert user_with_roles.can_access_framework("gdpr", "read") is True
        assert user_with_roles.can_access_framework("gdpr", "write") is False
        assert user_with_roles.can_access_framework("gdpr", "admin") is False
        assert user_with_roles.can_access_framework("nonexistent", "read") is False

    def test_to_dict(self, user_with_roles: UserWithRoles):
        """Test dictionary conversion."""
        data = user_with_roles.to_dict()
        assert "id" in data
        assert "email" in data
        assert "roles" in data
        assert "permissions" in data
        assert "accessible_frameworks" in data
        assert data["email"] == "test@example.com"
        assert len(data["roles"]) == 2
        assert len(data["permissions"]) == MAX_RETRIES
        assert len(data["accessible_frameworks"]) == 2


class TestRBACAuthentication:
    """Test RBAC authentication and token handling."""

    def test_create_access_token_with_roles(self):
        """Test creating access token with role claims."""
        user_id = uuid4()
        roles = [{"id": str(uuid4()), "name": "admin", "description": "Administrator"}]
        permissions = ["user_list", "admin_roles"]
        token = create_access_token_with_roles(user_id, roles, permissions)
        assert token is not None
        assert isinstance(token, str)
        from api.dependencies.auth import decode_token

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert "roles" in payload
        assert "permissions" in payload
        assert payload["roles"] == ["admin"]
        assert payload["permissions"] == permissions

    @pytest.mark.asyncio
    async def test_require_permission_decorator(self):
        """Test permission requirement decorator."""
        user_with_permission = UserWithRoles(
            user=MagicMock(),
            roles=[{"name": "admin"}],
            permissions=["user_list"],
            accessible_frameworks=[],
        )
        user_without_permission = UserWithRoles(
            user=MagicMock(), roles=[{"name": "user"}], permissions=[], accessible_frameworks=[]
        )
        check_permission = require_permission("user_list")
        result = await check_permission(user_with_permission)
        assert result == user_with_permission
        with pytest.raises(HTTPException) as exc_info:
            await check_permission(user_without_permission)
        assert exc_info.value.status_code == HTTP_FORBIDDEN
        assert "Permission 'user_list' required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_require_any_permission_decorator(self):
        """Test any permission requirement decorator."""
        user_with_one_permission = UserWithRoles(
            user=MagicMock(),
            roles=[{"name": "user"}],
            permissions=["user_list"],
            accessible_frameworks=[],
        )
        user_without_permissions = UserWithRoles(
            user=MagicMock(), roles=[{"name": "user"}], permissions=[], accessible_frameworks=[]
        )
        check_permissions = require_any_permission(["user_list", "admin_roles"])
        result = await check_permissions(user_with_one_permission)
        assert result == user_with_one_permission
        with pytest.raises(HTTPException) as exc_info:
            await check_permissions(user_without_permissions)
        assert exc_info.value.status_code == HTTP_FORBIDDEN


class TestRBACMiddleware:
    """Test RBAC middleware functionality."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app."""
        from fastapi import FastAPI

        app = FastAPI()
        return app

    @pytest.fixture
    def rbac_middleware(self, mock_app):
        """Create RBAC middleware instance."""
        from api.middleware.rbac_middleware import RBACMiddleware

        return RBACMiddleware(mock_app, enable_audit_logging=False)

    def test_is_public_route(self, rbac_middleware):
        """Test public route detection."""
        assert rbac_middleware._is_public_route("/api/v1/auth/login") is True
        assert rbac_middleware._is_public_route("/api/v1/auth/register") is True
        assert rbac_middleware._is_public_route("/docs") is True
        assert rbac_middleware._is_public_route("/api/v1/users") is False
        assert rbac_middleware._is_public_route("/api/v1/admin/roles") is False

    def test_is_authenticated_only_route(self, rbac_middleware):
        """Test authenticated-only route detection."""
        assert rbac_middleware._is_authenticated_only_route("/api/v1/auth/me") is True
        assert (rbac_middleware._is_authenticated_only_route("/api/v1/auth/logout") is True,)
        assert rbac_middleware._is_authenticated_only_route("/api/v1/users") is False

    def test_get_required_permissions(self, rbac_middleware):
        """Test getting required permissions for routes."""
        admin_permissions = rbac_middleware._get_required_permissions("/api/v1/admin/users", "GET")
        assert len(admin_permissions) > 0
        assert any("admin" in perm for perm in admin_permissions)
        user_permissions = rbac_middleware._get_required_permissions("/api/v1/users", "GET")
        assert "user_list" in user_permissions
        public_permissions = rbac_middleware._get_required_permissions("/api/v1/auth/login", "POST")
        assert len(public_permissions) == 0


class TestRBACIntegration:
    """Integration tests for RBAC system."""

    @pytest.mark.asyncio
    async def test_end_to_end_rbac_flow(self, db: Session):
        """Test complete RBAC flow from user creation to permission checking."""
        rbac = RBACService(db)
        user = User(
            id=uuid4(),
            email="integration@example.com",
            hashed_password="hashed_password",
            is_active=True,
        )
        db.add(user)
        role = Role(
            name="integration_role",
            display_name="Integration Role",
            description="Integration test role",
        )
        db.add(role)
        db.flush()
        permission = Permission(
            name="integration_permission",
            display_name="Integration Permission",
            description="Integration test permission",
            category="test_category",
            resource_type="test",
        )
        db.add(permission)
        db.flush()
        role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
        db.add(role_permission)
        db.commit()
        user_role = rbac.assign_role_to_user(user_id=user.id, role_id=role.id, granted_by=user.id)
        assert user_role is not None
        assert rbac.user_has_permission(user.id, "integration_permission") is True
        roles = rbac.get_user_roles(user.id)
        permissions = rbac.get_user_permissions(user.id)
        frameworks = rbac.get_accessible_frameworks(user.id)
        user_with_roles = UserWithRoles(user, roles, permissions, frameworks)
        assert user_with_roles.has_permission("integration_permission") is True
        assert user_with_roles.has_role("integration_role") is True
        token = create_access_token_with_roles(user.id, roles, permissions)
        assert token is not None
        success = rbac.revoke_role_from_user(user_id=user.id, role_id=role.id, revoked_by=user.id)
        assert success is True
        assert rbac.user_has_permission(user.id, "integration_permission") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
