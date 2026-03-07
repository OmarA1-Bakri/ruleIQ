"""

# Constants
MAX_RETRIES = 3


RBAC Middleware for Automatic API Protection

Provides middleware that automatically enforces role-based access control
on API endpoints based on route patterns and HTTP methods.
"""

import logging
import time
from typing import Dict, List, Optional, Pattern, Any
from uuid import UUID
import re
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from api.dependencies.rbac_auth import UserWithRoles
from database.db_setup import get_db
from services.rbac_service import RBACService

logger = logging.getLogger(__name__)


class RBACMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic RBAC enforcement and audit logging.

    Automatically checks permissions for protected API routes based on
    HTTP method and path patterns. Logs access attempts for audit purposes.
    """

    def __init__(self, app, enable_audit_logging: bool = True) -> None:
        super().__init__(app)
        self.enable_audit_logging = enable_audit_logging
        self.route_permissions = self._configure_route_permissions()
        self.public_routes = {
            "/api/v1/auth/login",
            "/api/v1/auth/login-form",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/health",
            "/api/monitoring/health",
            "/api/monitoring/prometheus",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/freemium/leads",
            "/api/v1/freemium/sessions",
            "/api/v1/freemium/health",
        }
        self.public_route_patterns = [
            re.compile("/api/v1/freemium/sessions/[^/]+$"),
            re.compile("/api/v1/freemium/sessions/[^/]+/answers$"),
            re.compile("/api/v1/freemium/sessions/[^/]+/results$"),
        ]
        self.authenticated_only_routes = {
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/auth/permissions",
            "/api/v1/auth/framework-access",
        }

    def _configure_route_permissions(self) -> Dict[Pattern, Dict[str, List[str]]]:
        """
        Configure route patterns and their required permissions by HTTP method.

        Returns:
            Dictionary mapping compiled regex patterns to method permissions
        """
        route_config = {
            "/api/admin/.*": {
                "GET": ["admin_roles", "admin_permissions", "admin_audit"],
                "POST": ["admin_roles", "admin_permissions"],
                "PUT": ["admin_roles", "admin_permissions"],
                "DELETE": ["admin_roles", "admin_permissions"],
                "PATCH": ["admin_roles", "admin_permissions"],
            },
            "/api/monitoring/database.*": {
                "GET": ["admin_roles", "monitoring_view"],
                "POST": ["admin_roles", "monitoring_admin"],
            },
            "/api/monitoring/status.*": {"GET": ["admin_roles", "monitoring_view"]},
            "/api/users/?$": {"GET": ["user_list"], "POST": ["user_create"]},
            "/api/users/[^/]+/?$": {
                "GET": ["user_list"],
                "PUT": ["user_update"],
                "DELETE": ["user_delete"],
                "PATCH": ["user_update"],
            },
            "/api/frameworks/?$": {"GET": ["framework_list"], "POST": ["framework_create"]},
            "/api/frameworks/[^/]+/?$": {
                "GET": ["framework_list"],
                "PUT": ["framework_update"],
                "DELETE": ["framework_delete"],
                "PATCH": ["framework_update"],
            },
            "/api/assessments/?$": {"GET": ["assessment_list"], "POST": ["assessment_create"]},
            "/api/assessments/[^/]+/?$": {
                "GET": ["assessment_list"],
                "PUT": ["assessment_update"],
                "DELETE": ["assessment_delete"],
                "PATCH": ["assessment_update"],
            },
            "/api/policies.*": {
                "GET": ["policy_generate"],
                "POST": ["policy_generate", "policy_refine"],
                "PUT": ["policy_refine"],
                "PATCH": ["policy_refine"],
            },
            "/api/reports.*": {
                "GET": ["report_view"],
                "POST": ["report_export", "report_schedule"],
            },
            "/api/business-profiles/?$": {"GET": ["user_list"], "POST": []},
            "/api/business-profiles/[^/]+/?$": {
                "GET": [],
                "PUT": [],
                "DELETE": ["user_delete"],
                "PATCH": [],
            },
        }
        return {re.compile(pattern): permissions for pattern, permissions in route_config.items()}

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Main middleware dispatch method.

        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain

        Returns:
            Response from downstream handler
        """
        start_time = time.time()
        try:
            if request.method == "OPTIONS":
                return await call_next(request)
            if self._is_public_route(request.url.path):
                return await call_next(request)
            current_user = await self._get_current_user(request)
            if self._is_authenticated_only_route(request.url.path):
                if current_user is None:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Authentication required"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return await call_next(request)
            required_permissions = self._get_required_permissions(request.url.path, request.method)
            if required_permissions:
                if current_user is None:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Authentication required"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                if not self._check_permissions(current_user, required_permissions, request):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Insufficient permissions"},
                    )
            if current_user:
                request.state.current_user = current_user
            response = await call_next(request)
            if self.enable_audit_logging and current_user:
                await self._log_access(
                    current_user, request, response.status_code, time.time() - start_time
                )
            return response
        except HTTPException as e:
            if self.enable_audit_logging:
                await self._log_access_failure(
                    request, e.status_code, str(e.detail), time.time() - start_time
                )
            raise
        except Exception as e:
            logger.error("RBAC middleware error: %s" % e, exc_info=True)
            if self.enable_audit_logging:
                await self._log_access_failure(
                    request, 500, f"Internal error: {str(e)}", time.time() - start_time
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
            )

    def _is_public_route(self, path: str) -> bool:
        """Check if route is public (no authentication required)."""
        if any(path.startswith(route) for route in self.public_routes):
            return True
        return any(pattern.match(path) for pattern in self.public_route_patterns)

    def _is_authenticated_only_route(self, path: str) -> bool:
        """Check if route requires authentication but no specific permissions."""
        return any(path.startswith(route) for route in self.authenticated_only_routes)

    async def _get_current_user(self, request: Request) -> Optional[UserWithRoles]:
        """
        Extract current user from request token.

        Args:
            request: FastAPI request object

        Returns:
            UserWithRoles instance or None if not authenticated
        """
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            token = auth_header.split(" ")[1]
            db = next(get_db())
            try:
                from api.dependencies.auth import decode_token

                payload = decode_token(token)
                if not payload or payload.get("type") != "access":
                    return None
                user_id_str = payload.get("sub")
                if not user_id_str:
                    return None
                try:
                    user_id = UUID(user_id_str)
                except ValueError:
                    return None
                from database.user import User

                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.is_active:
                    return None
                rbac = RBACService(db)
                roles = rbac.get_user_roles(user.id)
                permissions = rbac.get_user_permissions(user.id)
                accessible_frameworks = rbac.get_accessible_frameworks(user.id)
                return UserWithRoles(user, roles, permissions, accessible_frameworks)
            finally:
                db.close()
        except Exception as e:
            logger.debug("Failed to get current user: %s" % e)
            return None

    def _get_required_permissions(self, path: str, method: str) -> List[str]:
        """
        Get required permissions for a route and method.

        Args:
            path: Request path
            method: HTTP method

        Returns:
            List of required permissions
        """
        for pattern, method_permissions in self.route_permissions.items():
            if pattern.match(path):
                return method_permissions.get(method, [])
        return []

    def _check_permissions(
        self, user: UserWithRoles, required_permissions: List[str], request: Request
    ) -> bool:
        """
        Check if user has required permissions for the request.

        Args:
            user: User with roles and permissions
            required_permissions: List of required permissions
            request: FastAPI request object

        Returns:
            True if user has required permissions
        """
        if not required_permissions:
            return True
        if "/business-profiles/" in request.url.path and request.method in ["GET", "PUT", "PATCH"]:
            return self._check_business_profile_access(user, request)
        return user.has_any_permission(required_permissions)

    def _check_business_profile_access(self, user: UserWithRoles, request: Request) -> bool:
        """
        Check business profile access - users can access their own profiles,
        admins can access any profile.

        Args:
            user: User with roles
            request: FastAPI request object

        Returns:
            True if access allowed
        """
        if user.has_any_permission(["admin_roles", "user_list"]):
            return True
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) >= MAX_RETRIES and path_parts[-1]:
            try:
                profile_user_id = UUID(path_parts[-1])
                return profile_user_id == user.id
            except ValueError:
                return False
        return False

    async def _log_access(
        self, user: UserWithRoles, request: Request, status_code: int, duration: float
    ) -> None:
        """
        Log successful access for audit purposes.

        Args:
            user: User who made the request
            request: FastAPI request object
            status_code: HTTP response status code
            duration: Request processing duration in seconds
        """
        try:
            db = next(get_db())
            try:
                rbac = RBACService(db)
                rbac._log_audit(
                    user_id=user.id,
                    action="api_access",
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": round(duration * 1000, 2),
                        "user_agent": request.headers.get("user-agent"),
                        "ip_address": getattr(request.client, "host", None),
                        "roles": [role["name"] for role in user.roles],
                        "permissions_count": len(user.permissions),
                    },
                )
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to log access: %s" % e)

    async def _log_access_failure(
        self, request: Request, status_code: int, reason: str, duration: float
    ) -> None:
        """
        Log failed access attempts for security monitoring.

        Args:
            request: FastAPI request object
            status_code: HTTP response status code
            reason: Failure reason
            duration: Request processing duration in seconds
        """
        try:
            db = next(get_db())
            try:
                rbac = RBACService(db)
                rbac._log_audit(
                    user_id=None,
                    action="api_access_denied",
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "reason": reason,
                        "duration_ms": round(duration * 1000, 2),
                        "user_agent": request.headers.get("user-agent"),
                        "ip_address": getattr(request.client, "host", None),
                    },
                )
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to log access failure: %s" % e)


class RBACRouteProtector:
    """
    Decorator-based route protection for specific endpoints.

    Use this for fine-grained permission control on individual routes
    that need custom logic beyond the middleware patterns.
    """

    @staticmethod
    def require_permissions(permissions: List[str]) -> Any:
        """
        Decorator to require specific permissions for a route.

        Args:
            permissions: List of required permissions

        Returns:
            Route decorator
        """

        def decorator(func) -> Any:
            func._required_permissions = permissions
            return func

        return decorator

    @staticmethod
    def require_framework_access(framework_id: str, access_level: str = "read") -> Any:
        """
        Decorator to require framework access for a route.

        Args:
            framework_id: Framework ID to check
            access_level: Required access level

        Returns:
            Route decorator
        """

        def decorator(func) -> Any:
            func._required_framework_access = framework_id, access_level
            return func

        return decorator

    @staticmethod
    def admin_only(func) -> Any:
        """
        Decorator to restrict route to admin users only.

        Args:
            func: Route function

        Returns:
            Decorated function
        """
        func._admin_only = True
        return func


def require_admin(func) -> Any:
    """Decorator for admin-only routes."""
    return RBACRouteProtector.admin_only(func)


def require_permissions(*permissions) -> Any:
    """Decorator for routes requiring specific permissions."""
    return RBACRouteProtector.require_permissions(list(permissions))


def require_framework_access(framework_id: str, access_level: str = "read") -> Any:
    """Decorator for routes requiring framework access."""
    return RBACRouteProtector.require_framework_access(framework_id, access_level)
