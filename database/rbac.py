"""
Role-Based Access Control (RBAC) Database Models

Implements RBAC system for controlling access to compliance frameworks,
assessments, and administrative functions.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .db_setup import Base

# Forward reference imports for relationships
# These will be resolved at runtime by SQLAlchemy


class Role(Base):
    """
    System roles that define user permissions.

    Built-in roles:
    - admin: Full system access
    - framework_manager: Manage compliance frameworks
    - assessor: Create and manage assessments
    - viewer: Read-only access
    - business_user: Standard business user access
    """

    __tablename__ = "roles"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system_role = Column(Boolean, default=False)  # Built-in vs custom roles
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user_roles = relationship("UserRole", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role")
    framework_access = relationship("FrameworkAccess", back_populates="role")


class Permission(Base):
    """
    System permissions that can be assigned to roles.

    Permission categories:
    - user_management: Create, update, delete users
    - framework_management: Manage compliance frameworks
    - assessment_management: Create, update assessments
    - policy_generation: Generate AI policies
    - report_access: View and generate reports
    - admin_functions: System administration
    """

    __tablename__ = "permissions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # Group related permissions
    resource_type = Column(String(50), nullable=True)  # What resource type this applies to
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")


class UserRole(Base):
    """
    Assignment of roles to users with optional constraints.
    """

    __tablename__ = "user_roles"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_id = Column(PG_UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    granted_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Optional role expiration
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")
    granted_by_user = relationship("User", foreign_keys=[granted_by])

    # Ensure one role assignment per user-role combination
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)


class RolePermission(Base):
    """
    Assignment of permissions to roles.
    """

    __tablename__ = "role_permissions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(PG_UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    permission_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("permissions.id"),
        nullable=False,
    )
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")
    granted_by_user = relationship("User")

    # Ensure one permission assignment per role-permission combination
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


class FrameworkAccess(Base):
    """
    Framework-specific access control.
    Controls which roles can access specific compliance frameworks.
    """

    __tablename__ = "framework_access"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(PG_UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    framework_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("compliance_frameworks.id"),
        nullable=False,
    )
    access_level = Column(
        Enum("read", "write", "admin", name="access_level_enum"),
        nullable=False,
        default="read",
    )
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    role = relationship("Role", back_populates="framework_access")
    framework = relationship("ComplianceFramework")
    granted_by_user = relationship("User")

    # Ensure one access level per role-framework combination
    __table_args__ = (UniqueConstraint("role_id", "framework_id", name="uq_role_framework_access"),)


class UserSession(Base):
    """
    Track user sessions for security and audit purposes.
    Extended to include role context.
    """

    __tablename__ = "user_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), nullable=False, unique=True)
    roles_at_login = Column(String(500), nullable=True)  # JSON string of role names
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    logout_reason = Column(String(50), nullable=True)  # manual, timeout, forced

    # Relationships
    user = relationship("User", foreign_keys=[user_id])


class AuditLog(Base):
    """
    Comprehensive audit logging for RBAC operations and security events.
    """

    __tablename__ = "audit_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_sessions.id"),
        nullable=True,
    )
    action = Column(String(100), nullable=False)  # login, role_granted, permission_denied, etc.
    resource_type = Column(String(50), nullable=True)  # user, role, framework, assessment
    resource_id = Column(String(100), nullable=True)  # ID of affected resource
    details = Column(Text, nullable=True)  # JSON string with additional context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    severity = Column(
        Enum("info", "warning", "error", "critical", name="severity_enum"),
        nullable=False,
        default="info",
    )
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    session = relationship("UserSession")


class DataAccess(Base):
    """
    Control data visibility based on user roles and organizational context.
    """

    __tablename__ = "data_access"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("business_profiles.id"),
        nullable=True,
    )
    access_type = Column(
        Enum("own_data", "organization_data", "all_data", name="data_access_enum"),
        nullable=False,
        default="own_data",
    )
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    business_profile = relationship("BusinessProfile")
    granted_by_user = relationship("User", foreign_keys=[granted_by])

    # Ensure one data access level per user-business profile combination
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "business_profile_id",
            name="uq_user_business_data_access",
        ),
    )
