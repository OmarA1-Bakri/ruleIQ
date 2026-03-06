"""
Unit tests for services/rbac_service.py — RBACService.

All database interactions are mocked via MagicMock.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
from unittest.mock import MagicMock, patch, PropertyMock

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.rbac_service import RBACService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db():
    """Create a mock database session."""
    return MagicMock()


def _make_role(name="admin", role_id=None, is_active=True):
    """Create a mock Role."""
    role = MagicMock()
    role.id = role_id or uuid4()
    role.name = name
    role.display_name = name.title()
    role.description = f"Description for {name}"
    role.is_active = is_active
    role.is_system_role = False
    return role


def _make_user(user_id=None, is_active=True):
    """Create a mock User."""
    user = MagicMock()
    user.id = user_id or uuid4()
    user.is_active = is_active
    return user


# ---------------------------------------------------------------------------
# create_role
# ---------------------------------------------------------------------------

class TestCreateRole:
    """Tests for RBACService.create_role()."""

    def test_create_role_success(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = RBACService(db)

        role = svc.create_role("editor", "Editor", "Can edit content")
        db.add.assert_called()
        db.commit.assert_called()

    def test_create_role_duplicate_raises(self):
        db = _make_mock_db()
        existing = _make_role("editor")
        db.query.return_value.filter.return_value.first.return_value = existing
        svc = RBACService(db)

        with pytest.raises(ValueError, match="already exists"):
            svc.create_role("editor", "Editor")


# ---------------------------------------------------------------------------
# assign_role_to_user
# ---------------------------------------------------------------------------

class TestAssignRole:
    """Tests for RBACService.assign_role_to_user()."""

    def test_assign_new_role(self):
        db = _make_mock_db()
        user = _make_user()
        role = _make_role("viewer")

        # First query returns user, second returns role, third returns no existing assignment
        call_count = [0]
        def side_effect(*args, **kwargs):
            chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                chain.filter.return_value.first.return_value = user
            elif call_count[0] == 2:
                chain.filter.return_value.first.return_value = role
            else:
                chain.filter.return_value.first.return_value = None
            return chain

        db.query.side_effect = side_effect
        svc = RBACService(db)

        result = svc.assign_role_to_user(user.id, role.id)
        db.add.assert_called()
        db.commit.assert_called()

    def test_assign_to_nonexistent_user(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = RBACService(db)

        with pytest.raises(ValueError, match="User not found"):
            svc.assign_role_to_user(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# revoke_role_from_user
# ---------------------------------------------------------------------------

class TestRevokeRole:
    """Tests for RBACService.revoke_role_from_user()."""

    def test_revoke_existing_role(self):
        db = _make_mock_db()
        user_role = MagicMock()
        user_role.id = uuid4()
        user_role.is_active = True

        role = _make_role("viewer")

        call_count = [0]
        def side_effect(*args, **kwargs):
            chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                chain.filter.return_value.first.return_value = user_role
            else:
                chain.filter.return_value.first.return_value = role
            return chain

        db.query.side_effect = side_effect
        svc = RBACService(db)

        result = svc.revoke_role_from_user(uuid4(), uuid4())
        assert result is True
        assert user_role.is_active is False

    def test_revoke_nonexistent_returns_false(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = RBACService(db)

        result = svc.revoke_role_from_user(uuid4(), uuid4())
        assert result is False


# ---------------------------------------------------------------------------
# create_permission
# ---------------------------------------------------------------------------

class TestCreatePermission:
    """Tests for RBACService.create_permission()."""

    def test_create_permission_success(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = RBACService(db)

        perm = svc.create_permission("user_create", "Create Users", "user_management")
        db.add.assert_called()
        db.commit.assert_called()

    def test_create_duplicate_raises(self):
        db = _make_mock_db()
        existing = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing
        svc = RBACService(db)

        with pytest.raises(ValueError, match="already exists"):
            svc.create_permission("user_create", "Create Users", "user_management")


# ---------------------------------------------------------------------------
# grant_framework_access
# ---------------------------------------------------------------------------

class TestGrantFrameworkAccess:
    """Tests for RBACService.grant_framework_access()."""

    def test_invalid_access_level(self):
        db = _make_mock_db()
        svc = RBACService(db)

        with pytest.raises(ValueError, match="Access level"):
            svc.grant_framework_access(uuid4(), uuid4(), access_level="superuser")

    def test_valid_access_levels(self):
        for level in ["read", "write", "admin"]:
            db = _make_mock_db()
            db.query.return_value.filter.return_value.first.return_value = None
            svc = RBACService(db)
            # Should not raise
            svc.grant_framework_access(uuid4(), uuid4(), access_level=level)


# ---------------------------------------------------------------------------
# user_has_permission
# ---------------------------------------------------------------------------

class TestUserHasPermission:
    """Tests for RBACService.user_has_permission()."""

    def test_no_roles_returns_false(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = RBACService(db)

        assert svc.user_has_permission(uuid4(), "user_create") is False

    def test_with_matching_permission(self):
        db = _make_mock_db()
        user_role = MagicMock()
        user_role.role_id = uuid4()

        call_count = [0]
        def side_effect(*args, **kwargs):
            chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                chain.filter.return_value.all.return_value = [user_role]
            else:
                chain.join.return_value.filter.return_value.count.return_value = 1
            return chain

        db.query.side_effect = side_effect
        svc = RBACService(db)

        assert svc.user_has_permission(uuid4(), "user_create") is True


# ---------------------------------------------------------------------------
# user_has_framework_access
# ---------------------------------------------------------------------------

class TestUserHasFrameworkAccess:
    """Tests for RBACService.user_has_framework_access()."""

    def test_no_roles_returns_false(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = RBACService(db)

        assert svc.user_has_framework_access(uuid4(), uuid4()) is False

    def test_with_sufficient_access(self):
        db = _make_mock_db()
        user_role = MagicMock()
        user_role.role_id = uuid4()

        access = MagicMock()
        access.access_level = "admin"

        call_count = [0]
        def side_effect(*args, **kwargs):
            chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                chain.filter.return_value.all.return_value = [user_role]
            else:
                chain.filter.return_value.all.return_value = [access]
            return chain

        db.query.side_effect = side_effect
        svc = RBACService(db)

        assert svc.user_has_framework_access(uuid4(), uuid4(), required_level="write") is True

    def test_insufficient_access(self):
        db = _make_mock_db()
        user_role = MagicMock()
        user_role.role_id = uuid4()

        access = MagicMock()
        access.access_level = "read"

        call_count = [0]
        def side_effect(*args, **kwargs):
            chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                chain.filter.return_value.all.return_value = [user_role]
            else:
                chain.filter.return_value.all.return_value = [access]
            return chain

        db.query.side_effect = side_effect
        svc = RBACService(db)

        assert svc.user_has_framework_access(uuid4(), uuid4(), required_level="admin") is False


# ---------------------------------------------------------------------------
# get_user_roles / get_user_permissions
# ---------------------------------------------------------------------------

class TestGetUserRoles:
    """Tests for RBACService.get_user_roles()."""

    def test_no_roles(self):
        db = _make_mock_db()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        svc = RBACService(db)

        result = svc.get_user_roles(uuid4())
        assert result == []

    def test_with_roles(self):
        db = _make_mock_db()
        role = _make_role("editor")
        user_role = MagicMock()
        user_role.role = role
        user_role.granted_at = datetime.now(timezone.utc)
        user_role.expires_at = None

        db.query.return_value.join.return_value.filter.return_value.all.return_value = [user_role]
        svc = RBACService(db)

        result = svc.get_user_roles(uuid4())
        assert len(result) == 1
        assert result[0]["name"] == "editor"


class TestGetUserPermissions:
    """Tests for RBACService.get_user_permissions()."""

    def test_no_roles_returns_empty(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = RBACService(db)

        result = svc.get_user_permissions(uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# cleanup_expired_roles
# ---------------------------------------------------------------------------

class TestCleanupExpiredRoles:
    """Tests for RBACService.cleanup_expired_roles()."""

    def test_no_expired(self):
        db = _make_mock_db()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = RBACService(db)

        count = svc.cleanup_expired_roles()
        assert count == 0
        # commit should NOT be called when count is 0
        # (actually it may be called for audit log, but the if count > 0 guards the main commit)

    def test_with_expired_roles(self):
        db = _make_mock_db()
        expired_role = MagicMock()
        expired_role.id = uuid4()
        expired_role.user_id = uuid4()
        expired_role.role_id = uuid4()
        expired_role.is_active = True

        db.query.return_value.filter.return_value.all.return_value = [expired_role]
        svc = RBACService(db)

        count = svc.cleanup_expired_roles()
        assert count == 1
        assert expired_role.is_active is False


# ---------------------------------------------------------------------------
# _log_audit
# ---------------------------------------------------------------------------

class TestLogAudit:
    """Tests for RBACService._log_audit()."""

    def test_creates_audit_log(self):
        db = _make_mock_db()
        svc = RBACService(db)

        svc._log_audit(
            action="test_action",
            user_id=uuid4(),
            resource_type="role",
            resource_id="abc-123",
            details={"key": "value"},
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
