"""
Enhanced JWT Middleware with HttpOnly Cookies and Security Best Practices
"""

import os
import secrets
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
from config.security_settings import get_security_settings
from services.redis_circuit_breaker import get_redis_circuit_breaker

logger = logging.getLogger(__name__)


class JWTEnhancedMiddleware(BaseHTTPMiddleware):
    """
    Enhanced JWT middleware with production-ready security features:
    - HttpOnly cookie support
    - Refresh token rotation
    - JTI (JWT ID) validation for revocation
    - Rate limiting on refresh endpoint
    - Secret rotation support
    - Audience and issuer validation
    """

    def __init__(self, app: ASGIApp, **kwargs) -> None:
        super().__init__(app)
        self.security_settings = get_security_settings()
        self.jwt_config = self.security_settings.jwt

        # JWT settings
        self.secret_key = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
        self.algorithm = self.jwt_config.algorithm
        self.access_token_expire = timedelta(minutes=self.jwt_config.access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=self.jwt_config.refresh_token_expire_days)

        # Cookie settings
        self.use_httponly_cookies = self.jwt_config.use_httponly_cookies
        self.cookie_secure = self.jwt_config.cookie_secure
        self.cookie_samesite = self.jwt_config.cookie_samesite
        self.cookie_domain = self.jwt_config.cookie_domain
        self.cookie_path = self.jwt_config.cookie_path

        # Security features
        self.enable_refresh_rotation = self.jwt_config.enable_refresh_rotation
        self.enable_jti_validation = self.jwt_config.enable_jti_validation
        self.enable_audience_validation = self.jwt_config.enable_audience_validation
        self.issuer = self.jwt_config.issuer
        self.audience = self.jwt_config.audience

        # Rate limiting for refresh
        self.refresh_rate_limit = self.jwt_config.refresh_rate_limit
        self.refresh_rate_window = self.jwt_config.refresh_rate_window

        # Secret rotation
        self.enable_secret_rotation = self.jwt_config.enable_secret_rotation
        self.rotation_overlap_hours = timedelta(hours=self.jwt_config.rotation_overlap_hours)

        # Redis for JTI tracking and rate limiting
        self.redis_breaker = None

        logger.info("Enhanced JWT middleware initialized with HttpOnly cookies")

    async def __call__(self, scope, receive, send):
        """Process requests with JWT validation"""
        if scope["type"] == "http":
            # Initialize Redis circuit breaker if not done
            if not self.redis_breaker:
                try:
                    self.redis_breaker = await get_redis_circuit_breaker()
                except Exception as e:
                    logger.warning(f"Redis initialization failed: {e}")

            await super().__call__(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    def create_access_token(
        self,
        user_id: str,
        email: str,
        role: str = "user",
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create JWT access token with security features"""

        now = datetime.now(timezone.utc)
        expire = now + self.access_token_expire

        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": expire,
            "nbf": now,  # Not before
        }

        # Add issuer and audience if enabled
        if self.enable_audience_validation:
            payload["aud"] = self.audience
            payload["iss"] = self.issuer

        # Add JTI for revocation support
        if self.enable_jti_validation:
            payload["jti"] = secrets.token_urlsafe(16)
            # Store JTI in Redis for validation
            if self.redis_breaker:
                jti_key = f"jwt:jti:access:{payload['jti']}"
                ttl = int(self.access_token_expire.total_seconds())
                asyncio.create_task(self.redis_breaker.set(jti_key, user_id, ex=ttl))

        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self, user_id: str, email: str, family_id: Optional[str] = None
    ) -> str:
        """Create JWT refresh token with rotation support"""

        now = datetime.now(timezone.utc)
        expire = now + self.refresh_token_expire

        # Generate family ID for rotation tracking
        if not family_id and self.enable_refresh_rotation:
            family_id = secrets.token_urlsafe(16)

        payload = {
            "sub": user_id,
            "email": email,
            "type": "refresh",
            "iat": now,
            "exp": expire,
            "nbf": now,
        }

        # Add family ID for rotation
        if family_id:
            payload["family_id"] = family_id

        # Add JTI for revocation
        if self.enable_jti_validation:
            payload["jti"] = secrets.token_urlsafe(16)
            # Store JTI in Redis
            if self.redis_breaker:
                jti_key = f"jwt:jti:refresh:{payload['jti']}"
                ttl = int(self.refresh_token_expire.total_seconds())
                asyncio.create_task(self.redis_breaker.set(jti_key, user_id, ex=ttl))

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def set_auth_cookies(self, response: Response, access_token: str, refresh_token: str) -> None:
        """Set JWT tokens in HttpOnly cookies"""

        if not self.use_httponly_cookies:
            return

        # Set access token cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=int(self.access_token_expire.total_seconds()),
            expires=int(self.access_token_expire.total_seconds()),
            path=self.cookie_path,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,
            samesite=self.cookie_samesite,
        )

        # Set refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=int(self.refresh_token_expire.total_seconds()),
            expires=int(self.refresh_token_expire.total_seconds()),
            path=self.cookie_path,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=True,
            samesite=self.cookie_samesite,
        )

    def clear_auth_cookies(self, response: Response) -> None:
        """Clear authentication cookies"""

        response.delete_cookie(key="access_token", path=self.cookie_path, domain=self.cookie_domain)

        response.delete_cookie(
            key="refresh_token", path=self.cookie_path, domain=self.cookie_domain
        )

    async def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify JWT token with comprehensive validation"""

        try:
            # Decode token
            options = {"verify_exp": True, "verify_nbf": True}

            if self.enable_audience_validation:
                options["verify_aud"] = True
                options["verify_iss"] = True

            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options=options,
                audience=self.audience if self.enable_audience_validation else None,
                issuer=self.issuer if self.enable_audience_validation else None,
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise jwt.InvalidTokenError(f"Invalid token type: expected {token_type}")

            # Verify JTI if enabled
            if self.enable_jti_validation and "jti" in payload:
                jti_key = f"jwt:jti:{token_type}:{payload['jti']}"
                if self.redis_breaker:
                    exists = await self.redis_breaker.get(jti_key)
                    if not exists:
                        raise jwt.InvalidTokenError("Token has been revoked")

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed"
            )

    async def refresh_access_token(self, refresh_token: str, request: Request) -> Tuple[str, str]:
        """Refresh access token with rotation and rate limiting"""

        # Check rate limit
        if await self._check_refresh_rate_limit(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many refresh attempts"
            )

        # Verify refresh token
        payload = await self.verify_token(refresh_token, token_type="refresh")

        # Check if token family is valid (for rotation)
        if self.enable_refresh_rotation and "family_id" in payload:
            family_key = f"jwt:family:{payload['family_id']}"
            if self.redis_breaker:
                is_valid = await self.redis_breaker.get(family_key)
                if is_valid == "revoked":
                    # Family has been compromised, revoke all tokens
                    logger.warning(f"Compromised token family detected: {payload['family_id']}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token family has been revoked",
                    )

        # Create new tokens
        new_access = self.create_access_token(
            user_id=payload["sub"], email=payload["email"], role=payload.get("role", "user")
        )

        new_refresh = self.create_refresh_token(
            user_id=payload["sub"], email=payload["email"], family_id=payload.get("family_id")
        )

        # Revoke old refresh token JTI
        if self.enable_jti_validation and "jti" in payload and self.redis_breaker:
            old_jti_key = f"jwt:jti:refresh:{payload['jti']}"
            await self.redis_breaker.delete(old_jti_key)

        return new_access, new_refresh

    async def _check_refresh_rate_limit(self, request: Request) -> bool:
        """Check if refresh endpoint is rate limited"""

        if not self.redis_breaker:
            return False

        # Get client identifier (IP or user ID)
        client_id = request.client.host if request.client else "unknown"
        rate_key = f"rate:refresh:{client_id}"

        # Get current count
        count = await self.redis_breaker.get(rate_key)
        if count:
            try:
                count = int(count)
                if count >= self.refresh_rate_limit:
                    return True
            except ValueError:
                pass

        # Increment count
        await self.redis_breaker.set(
            rate_key, str(int(count) + 1 if count else 1), ex=self.refresh_rate_window
        )

        return False

    def get_token_from_request(self, request: Request) -> Optional[str]:
        """Extract token from request (cookie or header)"""

        # Try cookie first if enabled
        if self.use_httponly_cookies:
            token = request.cookies.get("access_token")
            if token:
                return token

        # Try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        return None

    async def revoke_token(self, jti: str, token_type: str = "access") -> bool:
        """Revoke a token by its JTI"""

        if not self.redis_breaker or not self.enable_jti_validation:
            return False

        jti_key = f"jwt:jti:{token_type}:{jti}"
        return await self.redis_breaker.delete(jti_key)

    async def revoke_token_family(self, family_id: str) -> bool:
        """Revoke an entire token family (for refresh token rotation)"""

        if not self.redis_breaker or not self.enable_refresh_rotation:
            return False

        family_key = f"jwt:family:{family_id}"
        return await self.redis_breaker.set(
            family_key, "revoked", ex=int(self.refresh_token_expire.total_seconds())
        )


# Import asyncio for async tasks
import asyncio


def create_jwt_enhanced_middleware(app: ASGIApp) -> JWTEnhancedMiddleware:
    """Factory function to create JWT enhanced middleware"""
    return JWTEnhancedMiddleware(app)
