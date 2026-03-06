"""

Enhanced Authentication Service
Implements MFA, password complexity, account lockout, and secure session management
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import pyotp
import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import re

from config.settings import settings
from services.cache_service import CacheService


class AuthenticationService:
    """Enhanced authentication with security hardening"""

    # Security constants
    PASSWORD_MIN_LENGTH = 12
    PASSWORD_MAX_LENGTH = 128
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    SESSION_TIMEOUT_MINUTES = 60
    TOKEN_EXPIRY_MINUTES = 15
    REFRESH_TOKEN_DAYS = 7
    MFA_CODE_LENGTH = 6
    BACKUP_CODES_COUNT = 10

    # Password complexity regex patterns
    PASSWORD_PATTERNS = {
        "uppercase": r"[A-Z]",
        "lowercase": r"[a-z]",
        "digit": r"\d",
        "special": r'[!@#$%^&*(),.?":{}|<>]',
    }

    def __init__(self, cache_service: Optional[CacheService] = None) -> None:
        """Initialize authentication service"""
        self.cache = cache_service or CacheService()
        self.jwt_secret = settings.jwt_secret_key
        self.jwt_algorithm = settings.jwt_algorithm

    def validate_password_complexity(self, password: str) -> Tuple[bool, str]:
        """
        Validate password meets complexity requirements

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(password) < self.PASSWORD_MIN_LENGTH:
            return (
                False,
                f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters",
            )

        if len(password) > self.PASSWORD_MAX_LENGTH:
            return (
                False,
                f"Password must not exceed {self.PASSWORD_MAX_LENGTH} characters",
            )

        # Check complexity requirements
        missing = []
        for requirement, pattern in self.PASSWORD_PATTERNS.items():
            if not re.search(pattern, password):
                missing.append(requirement)

        if missing:
            return False, f"Password must contain: {', '.join(missing)} characters"

        # Check for common patterns
        if self._contains_common_patterns(password):
            return False, "Password contains common patterns or dictionary words"

        return True, "Password meets complexity requirements"

    def _contains_common_patterns(self, password: str) -> bool:
        """Check for common weak password patterns"""
        common_patterns = [
            "password",
            "12345",
            "qwerty",
            "abc123",
            "admin",
            "letmein",
            "welcome",
            "monkey",
            "dragon",
        ]

        password_lower = password.lower()
        return any(pattern in password_lower for pattern in common_patterns)

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt with salt"""
        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    async def check_account_lockout(self, user_id: str, db: Session) -> bool:
        """Check if account is locked due to failed attempts"""
        lockout_key = f"lockout:{user_id}"
        lockout_data = await self.cache.get(lockout_key)

        if lockout_data:
            lockout_until = datetime.fromisoformat(lockout_data["until"])
            if datetime.now(timezone.utc) < lockout_until:
                return True
            else:
                # Lockout expired, clear it
                await self.cache.delete(lockout_key)

        return False

    async def record_failed_attempt(self, user_id: str, db: Session) -> None:
        """Record failed login attempt and enforce lockout if needed"""
        attempts_key = f"login_attempts:{user_id}"

        # Get current attempts
        attempts = await self.cache.get(attempts_key) or 0
        attempts += 1

        # Store updated attempts with TTL
        await self.cache.set(
            attempts_key,
            attempts,
            expire_seconds=self.LOCKOUT_DURATION_MINUTES * 60,
        )

        # Check if lockout needed
        if attempts >= self.MAX_LOGIN_ATTEMPTS:
            lockout_until = datetime.now(timezone.utc) + timedelta(
                minutes=self.LOCKOUT_DURATION_MINUTES,
            )

            lockout_data = {"until": lockout_until.isoformat(), "attempts": attempts}

            await self.cache.set(
                f"lockout:{user_id}",
                lockout_data,
                expire_seconds=self.LOCKOUT_DURATION_MINUTES * 60,
            )

    async def clear_failed_attempts(self, user_id: str) -> None:
        """Clear failed login attempts after successful login"""
        await self.cache.delete(f"login_attempts:{user_id}")
        await self.cache.delete(f"lockout:{user_id}")

    def generate_mfa_secret(self) -> str:
        """Generate TOTP secret for MFA"""
        return pyotp.random_base32()

    def generate_totp_uri(self, secret: str, email: str) -> str:
        """Generate TOTP URI for QR code"""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name="RuleIQ",
        )

    def verify_totp(self, secret: str, code: str) -> bool:
        """Verify TOTP code"""
        totp = pyotp.TOTP(secret)
        # Allow for time drift (±1 time step)
        return totp.verify(code, valid_window=1)

    def generate_backup_codes(self) -> list[str]:
        """Generate backup codes for MFA recovery"""
        codes = []
        for _ in range(self.BACKUP_CODES_COUNT):
            # Generate cryptographically secure code
            code = secrets.token_hex(4).upper()
            # Format as XXXX-XXXX
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes

    def hash_backup_code(self, code: str) -> str:
        """Hash backup code for storage"""
        # Remove formatting
        clean_code = code.replace("-", "")
        # Hash with SHA256
        return hashlib.sha256(clean_code.encode()).hexdigest()

    def verify_backup_code(self, code: str, hashed: str) -> bool:
        """Verify backup code against hash"""
        clean_code = code.replace("-", "")
        code_hash = hashlib.sha256(clean_code.encode()).hexdigest()
        return secrets.compare_digest(code_hash, hashed)

    def create_access_token(
        self, user_id: str, additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create JWT access token"""
        payload = {
            "sub": user_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=self.TOKEN_EXPIRY_MINUTES),
            "type": "access",
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token"""
        payload = {
            "sub": user_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_DAYS),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),  # Unique token ID for revocation
        }

        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise jwt.InvalidTokenError("Invalid token type")

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )

    async def create_session(self, user_id: str, ip_address: str, user_agent: str) -> str:
        """Create secure session"""
        session_id = secrets.token_urlsafe(32)

        session_data = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        # Store session with timeout
        await self.cache.set(
            f"session:{session_id}",
            session_data,
            expire_seconds=self.SESSION_TIMEOUT_MINUTES * 60,
        )

        return session_id

    async def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Validate and update session"""
        session_key = f"session:{session_id}"
        session_data = await self.cache.get(session_key)

        if not session_data:
            return None

        # Update last activity
        session_data["last_activity"] = datetime.now(timezone.utc).isoformat()

        # Refresh session TTL
        await self.cache.set(
            session_key,
            session_data,
            expire_seconds=self.SESSION_TIMEOUT_MINUTES * 60,
        )

        return session_data

    async def invalidate_session(self, session_id: str) -> None:
        """Invalidate session on logout"""
        await self.cache.delete(f"session:{session_id}")

    async def invalidate_all_sessions(self, user_id: str) -> None:
        """Invalidate all sessions for a user"""
        # This would require tracking sessions per user
        # Implementation depends on session storage strategy
        # Would need to iterate and check user_id in session data
        # Simplified for now
        pass

    async def enforce_concurrent_session_limit(self, user_id: str, max_sessions: int = 3) -> None:
        """Enforce maximum concurrent sessions per user"""
        # Track active sessions per user
        sessions_key = f"user_sessions:{user_id}"
        sessions = await self.cache.get(sessions_key) or []

        # Remove oldest sessions if limit exceeded
        if len(sessions) >= max_sessions:
            # Remove oldest session
            oldest = sessions[0]
            await self.invalidate_session(oldest)
            sessions = sessions[1:]

        return sessions

    def validate_oauth_state(self, state: str, stored_state: str) -> bool:
        """Validate OAuth2 state parameter for CSRF protection"""
        return secrets.compare_digest(state, stored_state)

    def generate_pkce_challenge(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        # Generate code verifier
        verifier = (base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("utf-8"),)

        # Generate code challenge (SHA256)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode("utf-8"),
        )

        return verifier, challenge

    def verify_pkce(self, verifier: str, challenge: str) -> bool:
        """Verify PKCE code verifier against challenge"""
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode("utf-8"),
        )

        return secrets.compare_digest(expected, challenge)


# Singleton instance
_auth_service: Optional[AuthenticationService] = None


def get_auth_service() -> AuthenticationService:
    """Get authentication service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service
