"""

RBAC Configuration for Route Protection

Centralized configuration for role-based access control including
route permissions, framework access rules, and security policies.
"""

from typing import Dict, List, Set
from enum import Enum


class AccessLevel(Enum):
    """Framework access levels in order of privilege."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class RBACConfig:
    """
    Centralized RBAC configuration.

    Modify these settings to adjust permissions and access control
    throughout the application.
    """

    # Public routes that don't require authentication
    PUBLIC_ROUTES: Set[str] = {
        "/api/v1/auth/login",
        "/api/v1/auth/login-form",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/health",
        "/api/v1/compliance/frameworks",  # Public framework listing
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    # Routes that require authentication but no specific permissions
    AUTHENTICATED_ONLY_ROUTES: Set[str] = {
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/permissions",
        "/api/v1/auth/framework-access",
    }

    # Default permissions for each role
    ROLE_PERMISSIONS: Dict[str, List[str]] = {
        "admin": [
            # User management
            "user_create",
            "user_update",
            "user_delete",
            "user_list",
            # Framework management
            "framework_create",
            "framework_update",
            "framework_delete",
            "framework_list",
            # Assessment management
            "assessment_create",
            "assessment_update",
            "assessment_delete",
            "assessment_list",
            # AI policy generation
            "policy_generate",
            "policy_refine",
            "policy_validate",
            # Reporting
            "report_view",
            "report_export",
            "report_schedule",
            # Admin functions
            "admin_roles",
            "admin_permissions",
            "admin_audit",
        ],
        "compliance_manager": [
            # Framework access
            "framework_list",
            # Assessment management
            "assessment_create",
            "assessment_update",
            "assessment_list",
            # AI policy generation
            "policy_generate",
            "policy_refine",
            # Reporting
            "report_view",
            "report_export",
        ],
        "assessor": [
            # Framework viewing
            "framework_list",
            # Assessment operations
            "assessment_create",
            "assessment_update",
            "assessment_list",
            # Basic policy generation
            "policy_generate",
            # Report viewing
            "report_view",
        ],
        "auditor": [
            # Read-only access to frameworks
            "framework_list",
            # Read-only assessment access
            "assessment_list",
            # Report access
            "report_view",
            "report_export",
        ],
        "user": [
            # Basic framework listing
            "framework_list",
            # Own assessments only (enforced at business logic level)
            "assessment_create",
            "assessment_list",
            # Basic report viewing
            "report_view",
        ],
    }

    # Route permission matrix - maps URL patterns to required permissions by HTTP method
    ROUTE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
        # Admin routes - strict admin access
        r"/api/v1/admin/.*": {
            "GET": ["admin_roles", "admin_permissions", "admin_audit"],
            "POST": ["admin_roles", "admin_permissions"],
            "PUT": ["admin_roles", "admin_permissions"],
            "DELETE": ["admin_roles", "admin_permissions"],
            "PATCH": ["admin_roles", "admin_permissions"],
        },
        # User management
        r"/api/v1/users/?$": {"GET": ["user_list"], "POST": ["user_create"]},
        r"/api/v1/users/[^/]+/?$": {
            "GET": ["user_list"],
            "PUT": ["user_update"],
            "DELETE": ["user_delete"],
            "PATCH": ["user_update"],
        },
        # Framework management
        r"/api/v1/frameworks/?$": {
            "GET": ["framework_list"],
            "POST": ["framework_create"],
        },
        r"/api/v1/frameworks/[^/]+/?$": {
            "GET": ["framework_list"],
            "PUT": ["framework_update"],
            "DELETE": ["framework_delete"],
            "PATCH": ["framework_update"],
        },
        r"/api/v1/compliance/frameworks/?$": {
            "GET": [],  # Public endpoint
            "POST": ["framework_create"],
        },
        r"/api/v1/compliance/frameworks/[^/]+/?$": {
            "GET": [],  # Public endpoint
            "PUT": ["framework_update"],
            "DELETE": ["framework_delete"],
            "PATCH": ["framework_update"],
        },
        # Assessment management
        r"/api/v1/assessments/?$": {
            "GET": ["assessment_list"],
            "POST": ["assessment_create"],
        },
        r"/api/v1/assessments/[^/]+/?$": {
            "GET": ["assessment_list"],
            "PUT": ["assessment_update"],
            "DELETE": ["assessment_delete"],
            "PATCH": ["assessment_update"],
        },
        r"/api/v1/ai-assessments/?$": {
            "GET": ["assessment_list"],
            "POST": ["assessment_create"],
        },
        r"/api/v1/ai-assessments/[^/]+/?$": {
            "GET": ["assessment_list"],
            "PUT": ["assessment_update"],
            "DELETE": ["assessment_delete"],
            "PATCH": ["assessment_update"],
        },
        # AI Policy generation
        r"/api/v1/policies.*": {
            "GET": ["policy_generate"],
            "POST": ["policy_generate", "policy_refine"],
            "PUT": ["policy_refine"],
            "PATCH": ["policy_refine"],
        },
        # Reporting
        r"/api/v1/reports.*": {
            "GET": ["report_view"],
            "POST": ["report_export", "report_schedule"],
        },
        # Business profiles - ownership-based access
        r"/api/v1/business-profiles/?$": {
            "GET": ["user_list"],  # Admin level for listing all
            "POST": [],  # Users can create their own,
        },
        r"/api/v1/business-profiles/[^/]+/?$": {
            "GET": [],  # Ownership check in middleware
            "PUT": [],  # Ownership check in middleware
            "DELETE": ["user_delete"],  # Admin only
            "PATCH": [],  # Ownership check in middleware,
        },
    }

    # Framework access permissions - which roles can access which frameworks
    FRAMEWORK_ACCESS_RULES: Dict[str, Dict[str, str]] = {
        "iso27001": {
            "admin": AccessLevel.ADMIN.value,
            "compliance_manager": AccessLevel.ADMIN.value,
            "assessor": AccessLevel.WRITE.value,
            "auditor": AccessLevel.READ.value,
            "user": AccessLevel.READ.value,
        },
        "soc2": {
            "admin": AccessLevel.ADMIN.value,
            "compliance_manager": AccessLevel.ADMIN.value,
            "assessor": AccessLevel.WRITE.value,
            "auditor": AccessLevel.READ.value,
            "user": AccessLevel.READ.value,
        },
        "gdpr": {
            "admin": AccessLevel.ADMIN.value,
            "compliance_manager": AccessLevel.ADMIN.value,
            "assessor": AccessLevel.WRITE.value,
            "auditor": AccessLevel.READ.value,
            "user": AccessLevel.READ.value,
        },
        "cyber_essentials": {
            "admin": AccessLevel.ADMIN.value,
            "compliance_manager": AccessLevel.ADMIN.value,
            "assessor": AccessLevel.WRITE.value,
            "auditor": AccessLevel.READ.value,
            "user": AccessLevel.READ.value,
        },
        "fca_guidelines": {
            "admin": AccessLevel.ADMIN.value,
            "compliance_manager": AccessLevel.ADMIN.value,
            "assessor": AccessLevel.WRITE.value,
            "auditor": AccessLevel.READ.value,
            "user": AccessLevel.READ.value,
        },
    }

    # Rate limiting rules by role
    RATE_LIMIT_RULES: Dict[str, Dict[str, int]] = {
        "admin": {
            "requests_per_minute": 200,
            "ai_requests_per_minute": 50,
            "auth_requests_per_minute": 20,
        },
        "compliance_manager": {
            "requests_per_minute": 150,
            "ai_requests_per_minute": 30,
            "auth_requests_per_minute": 10,
        },
        "assessor": {
            "requests_per_minute": 100,
            "ai_requests_per_minute": 20,
            "auth_requests_per_minute": 10,
        },
        "auditor": {
            "requests_per_minute": 80,
            "ai_requests_per_minute": 10,
            "auth_requests_per_minute": 5,
        },
        "user": {
            "requests_per_minute": 60,
            "ai_requests_per_minute": 10,
            "auth_requests_per_minute": 5,
        },
    }

    # Audit logging configuration
    AUDIT_CONFIG: Dict[str, any] = {
        "enabled": True,
        "log_successful_access": True,
        "log_failed_access": True,
        "log_admin_actions": True,
        "retention_days": 365,
        "sensitive_fields": ["password", "token", "secret", "key", "hash"],
    }

    # Security policies
    SECURITY_POLICIES: Dict[str, any] = {
        "token_expiry_minutes": 30,
        "refresh_token_expiry_days": 7,
        "max_failed_login_attempts": 5,
        "account_lockout_duration_minutes": 15,
        "require_mfa_for_admin": False,  # MFA implementation planned for Phase 2
        "mfa_methods": ["totp", "sms"],  # Supported MFA methods when implemented
        "mfa_backup_codes": True,  # Generate backup codes for MFA recovery
        "password_min_length": 8,
        "password_require_special_chars": True,
        "session_timeout_minutes": 120,
    }

    @classmethod
    def get_role_permissions(cls, role_name: str) -> List[str]:
        """Get permissions for a specific role."""
        return cls.ROLE_PERMISSIONS.get(role_name, [])

    @classmethod
    def get_framework_access(cls, role_name: str, framework_id: str) -> str:
        """Get framework access level for a role."""
        framework_rules = cls.FRAMEWORK_ACCESS_RULES.get(framework_id, {})
        return framework_rules.get(role_name, AccessLevel.READ.value)

    @classmethod
    def get_rate_limits(cls, role_name: str) -> Dict[str, int]:
        """Get rate limits for a specific role."""
        return cls.RATE_LIMIT_RULES.get(role_name, cls.RATE_LIMIT_RULES["user"])

    @classmethod
    def is_public_route(cls, path: str) -> bool:
        """Check if a route is public."""
        return any(path.startswith(route) for route in cls.PUBLIC_ROUTES)

    @classmethod
    def is_authenticated_only_route(cls, path: str) -> bool:
        """Check if a route requires authentication only."""
        return any(path.startswith(route) for route in cls.AUTHENTICATED_ONLY_ROUTES)
