"""
JWT Authentication Decorators for RuleIQ API

Provides decorator-based authentication for route protection.
Part of SEC-005: Complete JWT Coverage Extension
"""

from functools import wraps
from typing import Optional, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timezone
import logging

from api.dependencies.auth import is_token_blacklisted, SECRET_KEY, ALGORITHM
from database.user import User

logger = logging.getLogger(__name__)

# HTTPBearer for extracting token from Authorization header
security = HTTPBearer(auto_error=False)


class JWTMiddleware:
    """
    JWT Middleware decorator class for route-level authentication.

    Provides decorator methods to require authentication on specific routes.
    Works in conjunction with JWTAuthMiddlewareV2 for comprehensive coverage.
    """

    @staticmethod
    def require_auth(func: Callable) -> Callable:
        """
        Decorator to require JWT authentication for a route.

        Usage:
            @router.get("/protected")
            @JWTMiddleware.require_auth
            async def protected_route(current_user: User = Depends(get_current_user)):
                return {"user": current_user.email}
        """

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # The actual authentication is handled by get_current_user dependency
            # This decorator serves as a clear marker that the route requires auth
            return await func(*args, **kwargs)

        # Mark the function as requiring authentication
        wrapper.__requires_auth__ = True
        return wrapper

    @staticmethod
    def require_admin(func: Callable) -> Callable:
        """
        Decorator to require admin privileges for a route.

        Usage:
            @router.get("/admin/users")
            @JWTMiddleware.require_admin
            async def admin_route(current_user: User = Depends(get_current_user)):
                return {"admin": True}
        """

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if current_user is in kwargs (injected by FastAPI)
            current_user = kwargs.get("current_user")
            if current_user and not getattr(current_user, "is_admin", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
                )
            return await func(*args, **kwargs)

        wrapper.__requires_auth__ = True
        wrapper.__requires_admin__ = True
        return wrapper

    @staticmethod
    def require_roles(*allowed_roles: str) -> Callable:
        """
        Decorator to require specific roles for a route.

        Usage:
            @router.get("/moderator/content")
            @JWTMiddleware.require_roles("moderator", "admin")
            async def moderator_route(current_user: User = Depends(get_current_user)):
                return {"role": current_user.role}
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                current_user = kwargs.get("current_user")
                if current_user:
                    user_role = getattr(current_user, "role", None)
                    if user_role not in allowed_roles:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Role required: {', '.join(allowed_roles)}",
                        )
                return await func(*args, **kwargs)

            wrapper.__requires_auth__ = True
            wrapper.__required_roles__ = allowed_roles
            return wrapper

        return decorator

    @staticmethod
    def optional_auth(func: Callable) -> Callable:
        """
        Decorator for routes that can work with or without authentication.

        Usage:
            @router.get("/public-or-personalized")
            @JWTMiddleware.optional_auth
            async def flexible_route(current_user: Optional[User] = Depends(get_current_user_optional)):
                if current_user:
                    return {"personalized": True, "user": current_user.email}
                return {"personalized": False}
        """

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapper.__optional_auth__ = True
        return wrapper

    @staticmethod
    async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        """
        Validate JWT token from Authorization header.

        This is a dependency function that can be used directly in routes.

        Args:
            credentials: Bearer token from Authorization header

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid or missing
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials

        try:
            # Check if token is blacklisted
            if await is_token_blacklisted(token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Decode and validate token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # Check token type
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check expiration
            exp = payload.get("exp")
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                if exp_datetime < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            return payload

        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db=Depends(get_async_db),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.

    For use with optional authentication routes.
    """
    if not credentials:
        return None

    try:
        payload = await JWTMiddleware.validate_token(credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None

        from sqlalchemy.future import select

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()
    except:
        return None


# Export for backward compatibility
require_auth = JWTMiddleware.require_auth
require_admin = JWTMiddleware.require_admin
require_roles = JWTMiddleware.require_roles
optional_auth = JWTMiddleware.optional_auth
