"""

API Key Management Service for B2B Integrations

This module provides secure API key generation, validation, and management
for B2B partner integrations with comprehensive security features.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
from dataclasses import dataclass, asdict
import redis.asyncio as redis
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import ipaddress

from models.api_key import APIKey, APIKeyScope, APIKeyUsage
from config.settings import settings
from services.security.audit_logging import get_audit_service
from services.security.encryption import EncryptionService


class APIKeyStatus(str, Enum):
    """API key status enumeration"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIKeyType(str, Enum):
    """API key type enumeration"""

    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    INTERNAL = "internal"


@dataclass
class APIKeyMetadata:
    """API key metadata structure"""

    key_id: str
    organization_id: str
    organization_name: str
    key_type: APIKeyType
    status: APIKeyStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    allowed_ips: List[str]
    allowed_origins: List[str]
    scopes: List[str]
    rate_limit: int
    rate_limit_window: int
    metadata: Dict[str, Any]


class APIKeyManager:
    """
    Manages API keys for B2B integrations with comprehensive security features.

    Features:
    - Secure key generation with cryptographic randomness
    - Key rotation and versioning
    - Scope-based access control
    - Rate limiting per key
    - IP whitelist/blacklist
    - Usage tracking and analytics
    - Automatic expiration
    - Key suspension and revocation
    - Audit logging
    """

    def __init__(self, db_session: AsyncSession, redis_client: redis.Redis) -> None:
        self.db = db_session
        self.redis = redis_client
        self.encryption = EncryptionService()
        self._key_prefix = "api_key:"
        self._usage_prefix = "api_key_usage:"
        self._rate_limit_prefix = "api_key_rate:"

    async def generate_api_key(
        self,
        organization_id: str,
        organization_name: str,
        key_type: APIKeyType = APIKeyType.STANDARD,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
        scopes: Optional[List[str]] = None,
        rate_limit: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, APIKeyMetadata]:
        """
        Generate a new API key for an organization.

        Returns:
            Tuple of (api_key, key_id, metadata)
        """
        # Generate cryptographically secure key components
        key_id = f"ak_{secrets.token_urlsafe(16)}"
        key_secret = secrets.token_urlsafe(32)
        api_key = f"{key_id}.{key_secret}"

        # Hash the secret for storage
        key_hash = self._hash_key_secret(key_secret)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Set default rate limits based on key type
        if rate_limit is None:
            rate_limit = self._get_default_rate_limit(key_type)

        # Set default scopes based on key type
        if scopes is None:
            scopes = self._get_default_scopes(key_type)

        # Create database record
        db_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            organization_id=organization_id,
            organization_name=organization_name,
            key_type=key_type.value,
            status=APIKeyStatus.ACTIVE.value,
            expires_at=expires_at,
            allowed_ips=allowed_ips or [],
            allowed_origins=allowed_origins or [],
            rate_limit=rate_limit,
            rate_limit_window=60,  # 1 minute window
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(db_key)

        # Add scopes
        for scope in scopes:
            db_scope = APIKeyScope(
                key_id=key_id,
                scope=scope,
                granted_at=datetime.now(timezone.utc),
            )
            self.db.add(db_scope)

        await self.db.commit()

        # Cache key metadata in Redis
        metadata = APIKeyMetadata(
            key_id=key_id,
            organization_id=organization_id,
            organization_name=organization_name,
            key_type=key_type,
            status=APIKeyStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            last_used_at=None,
            allowed_ips=allowed_ips or [],
            allowed_origins=allowed_origins or [],
            scopes=scopes,
            rate_limit=rate_limit,
            rate_limit_window=60,
            metadata=metadata or {},
        )

        await self._cache_key_metadata(key_id, metadata)

        # Audit log
        await get_audit_service().log_security_event(
            event_type="api_key_created",
            user_id=organization_id,
            details={
                "key_id": key_id,
                "organization": organization_name,
                "key_type": key_type.value,
                "scopes": scopes,
                "expires_in_days": expires_in_days,
            },
        )

        return api_key, key_id, metadata

    async def validate_api_key(
        self,
        api_key: str,
        required_scope: Optional[str] = None,
        request_ip: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Tuple[bool, Optional[APIKeyMetadata], Optional[str]]:
        """
        Validate an API key and check permissions.

        Returns:
            Tuple of (is_valid, metadata, error_message)
        """
        try:
            # Parse API key
            if "." not in api_key:
                return False, None, "Invalid API key format"

            key_id, key_secret = api_key.split(".", 1)

            # Check cache first
            metadata = await self._get_cached_metadata(key_id)

            if not metadata:
                # Load from database
                metadata = await self._load_key_metadata(key_id)
                if not metadata:
                    return False, None, "Invalid API key"

                # Cache for next time
                await self._cache_key_metadata(key_id, metadata)

            # Verify key secret
            db_key = await self.db.execute(
                select(APIKey).where(APIKey.key_id == key_id),
            )
            db_key = db_key.scalar_one_or_none()

            if not db_key:
                return False, None, "Invalid API key"

            if not self._verify_key_secret(key_secret, db_key.key_hash):
                return False, None, "Invalid API key"

            # Check status
            if metadata.status != APIKeyStatus.ACTIVE:
                return False, None, f"API key is {metadata.status}"

            # Check expiration
            if metadata.expires_at and metadata.expires_at < datetime.now(timezone.utc):
                await self._update_key_status(key_id, APIKeyStatus.EXPIRED)
                return False, None, "API key has expired"

            # Check IP whitelist
            if metadata.allowed_ips and request_ip:
                if not self._check_ip_allowed(request_ip, metadata.allowed_ips):
                    await get_audit_service().log_security_event(
                        event_type="api_key_ip_denied",
                        user_id=metadata.organization_id,
                        details={
                            "key_id": key_id,
                            "request_ip": request_ip,
                            "allowed_ips": metadata.allowed_ips,
                        },
                    )
                    return False, None, "Request IP not allowed"

            # Check origin whitelist
            if (
                metadata.allowed_origins
                and origin
                and not any(origin.startswith(allowed) for allowed in metadata.allowed_origins)
            ):
                return False, None, "Origin not allowed"

            # Check scope
            if required_scope and required_scope not in metadata.scopes:
                return False, None, f"Missing required scope: {required_scope}"

            # Check rate limit
            if not await self._check_rate_limit(
                key_id, metadata.rate_limit, metadata.rate_limit_window
            ):
                return False, None, "Rate limit exceeded"

            # Update usage
            await self._track_usage(key_id, request_ip)

            return True, metadata, None

        except Exception as e:
            await get_audit_service().log_error(
                error_type="api_key_validation_error",
                error_message=str(e),
                context={"api_key_prefix": api_key[:10] if api_key else None},
            )
            return False, None, "Internal validation error"

    async def rotate_api_key(
        self, key_id: str, expires_old_in_hours: int = 24
    ) -> Tuple[str, str, APIKeyMetadata]:
        """
        Rotate an API key, creating a new one and scheduling old key expiration.
        """
        # Get existing key metadata
        metadata = await self._load_key_metadata(key_id)
        if not metadata:
            raise ValueError(f"API key not found: {key_id}")

        # Generate new key
        new_api_key, new_key_id, new_metadata = await self.generate_api_key(
            organization_id=metadata.organization_id,
            organization_name=metadata.organization_name,
            key_type=metadata.key_type,
            expires_in_days=None,  # Use same expiration as original
            allowed_ips=metadata.allowed_ips,
            allowed_origins=metadata.allowed_origins,
            scopes=metadata.scopes,
            rate_limit=metadata.rate_limit,
            metadata={
                **metadata.key_metadata,
                "rotated_from": key_id,
                "rotated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Schedule old key expiration
        expiration_time = datetime.now(timezone.utc) + timedelta(
            hours=expires_old_in_hours,
        )
        await self.db.execute(
            update(APIKey)
            .where(APIKey.key_id == key_id)
            .values(
                expires_at=expiration_time,
                metadata={
                    **metadata.key_metadata,
                    "rotated_to": new_key_id,
                    "rotation_scheduled": expiration_time.isoformat(),
                },
            ),
        )
        await self.db.commit()

        # Audit log
        await get_audit_service().log_security_event(
            event_type="api_key_rotated",
            user_id=metadata.organization_id,
            details={
                "old_key_id": key_id,
                "new_key_id": new_key_id,
                "expires_old_in_hours": expires_old_in_hours,
            },
        )

        return new_api_key, new_key_id, new_metadata

    async def revoke_api_key(self, key_id: str, reason: str) -> bool:
        """Revoke an API key immediately."""
        success = await self._update_key_status(key_id, APIKeyStatus.REVOKED)

        if success:
            # Clear cache
            await self.redis.delete(f"{self._key_prefix}{key_id}")

            # Audit log
            metadata = await self._load_key_metadata(key_id)
            if metadata:
                await get_audit_service().log_security_event(
                    event_type="api_key_revoked",
                    user_id=metadata.organization_id,
                    details={"key_id": key_id, "reason": reason},
                )

        return success

    async def suspend_api_key(self, key_id: str, reason: str) -> bool:
        """Temporarily suspend an API key."""
        success = await self._update_key_status(key_id, APIKeyStatus.SUSPENDED)

        if success:
            # Update cache
            metadata = await self._load_key_metadata(key_id)
            if metadata:
                metadata.status = APIKeyStatus.SUSPENDED
                await self._cache_key_metadata(key_id, metadata)

                await get_audit_service().log_security_event(
                    event_type="api_key_suspended",
                    user_id=metadata.organization_id,
                    details={"key_id": key_id, "reason": reason},
                )

        return success

    async def reactivate_api_key(self, key_id: str) -> bool:
        """Reactivate a suspended API key."""
        # Check current status
        metadata = await self._load_key_metadata(key_id)
        if not metadata:
            return False

        if metadata.status != APIKeyStatus.SUSPENDED:
            return False

        success = await self._update_key_status(key_id, APIKeyStatus.ACTIVE)

        if success:
            # Update cache
            metadata.status = APIKeyStatus.ACTIVE
            await self._cache_key_metadata(key_id, metadata)

            await get_audit_service().log_security_event(
                event_type="api_key_reactivated",
                user_id=metadata.organization_id,
                details={"key_id": key_id},
            )

        return success

    async def list_organization_keys(
        self, organization_id: str, include_revoked: bool = False
    ) -> List[APIKeyMetadata]:
        """List all API keys for an organization."""
        query = select(APIKey).where(APIKey.organization_id == organization_id)

        if not include_revoked:
            query = query.where(APIKey.status != APIKeyStatus.REVOKED.value)

        result = await self.db.execute(query)
        keys = result.scalars().all()

        metadata_list = []
        for key in keys:
            # Get scopes
            scopes_result = await self.db.execute(
                select(APIKeyScope.scope).where(APIKeyScope.key_id == key.key_id),
            )
            scopes = [s for s in scopes_result.scalars()]

            metadata = APIKeyMetadata(
                key_id=key.key_id,
                organization_id=key.organization_id,
                organization_name=key.organization_name,
                key_type=APIKeyType(key.key_type),
                status=APIKeyStatus(key.status),
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_used_at=key.last_used_at,
                allowed_ips=key.allowed_ips,
                allowed_origins=key.allowed_origins,
                scopes=scopes,
                rate_limit=key.rate_limit,
                rate_limit_window=key.rate_limit_window,
                metadata=key.key_metadata,
            )
            metadata_list.append(metadata)

        return metadata_list

    async def get_usage_statistics(self, key_id: str, days: int = 30) -> Dict[str, Any]:
        """Get usage statistics for an API key."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(APIKeyUsage)
            .where(and_(APIKeyUsage.key_id == key_id, APIKeyUsage.timestamp >= since))
            .order_by(APIKeyUsage.timestamp.desc()),
        )

        usage_records = result.scalars().all()

        # Calculate statistics
        total_requests = len(usage_records)
        unique_ips = len(set(r.ip_address for r in usage_records if r.ip_address))

        # Group by endpoint
        endpoint_counts = {}
        for record in usage_records:
            endpoint = record.endpoint or "unknown"
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

        # Group by day
        daily_counts = {}
        for record in usage_records:
            day = record.timestamp.date().isoformat()
            daily_counts[day] = daily_counts.get(day, 0) + 1

        return {
            "key_id": key_id,
            "period_days": days,
            "total_requests": total_requests,
            "unique_ips": unique_ips,
            "endpoints": endpoint_counts,
            "daily_usage": daily_counts,
            "last_used": usage_records[0].timestamp.isoformat() if usage_records else None,
        }

    # Private helper methods

    def _hash_key_secret(self, secret: str) -> str:
        """Hash API key secret for storage."""
        salt = (
            settings.API_KEY_SALT.encode()
            if hasattr(settings, "API_KEY_SALT")
            else b"default_salt"
        )
        return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 100000).hex()

    def _verify_key_secret(self, secret: str, stored_hash: str) -> bool:
        """Verify API key secret against stored hash."""
        return self._hash_key_secret(secret) == stored_hash

    def _get_default_rate_limit(self, key_type: APIKeyType) -> int:
        """Get default rate limit based on key type."""
        limits = {
            APIKeyType.STANDARD: 100,
            APIKeyType.PREMIUM: 500,
            APIKeyType.ENTERPRISE: 2000,
            APIKeyType.INTERNAL: 10000,
        }
        return limits.get(key_type, 100)

    def _get_default_scopes(self, key_type: APIKeyType) -> List[str]:
        """Get default scopes based on key type."""
        scopes = {
            APIKeyType.STANDARD: ["read:assessments", "read:compliance"],
            APIKeyType.PREMIUM: [
                "read:assessments",
                "read:compliance",
                "write:assessments",
            ],
            APIKeyType.ENTERPRISE: ["read:*", "write:*", "admin:organization"],
            APIKeyType.INTERNAL: ["*"],
        }
        return scopes.get(key_type, ["read:assessments"])

    def _check_ip_allowed(self, request_ip: str, allowed_ips: List[str]) -> bool:
        """Check if request IP is in allowed list (supports CIDR notation)."""
        try:
            request_addr = ipaddress.ip_address(request_ip)

            for allowed in allowed_ips:
                if "/" in allowed:
                    # CIDR notation
                    if request_addr in ipaddress.ip_network(allowed):
                        return True
                # Single IP
                elif request_addr == ipaddress.ip_address(allowed):
                    return True

            return False
        except (ValueError, ipaddress.AddressValueError):
            return False

    async def _check_rate_limit(self, key_id: str, limit: int, window: int) -> bool:
        """Check if API key has exceeded rate limit."""
        key = f"{self._rate_limit_prefix}{key_id}"

        # Increment counter
        count = await self.redis.incr(key)

        # Set expiration on first request
        if count == 1:
            await self.redis.expire(key, window)

        return count <= limit

    async def _track_usage(self, key_id: str, request_ip: Optional[str]) -> None:
        """Track API key usage."""
        # Update last used timestamp in database
        await self.db.execute(
            update(APIKey)
            .where(APIKey.key_id == key_id)
            .values(last_used_at=datetime.now(timezone.utc)),
        )

        # Record usage
        usage = APIKeyUsage(
            key_id=key_id,
            timestamp=datetime.now(timezone.utc),
            ip_address=request_ip,
            endpoint=None,  # Will be set by middleware,
        )
        self.db.add(usage)

        # Commit asynchronously
        await self.db.commit()

    async def _update_key_status(self, key_id: str, status: APIKeyStatus) -> bool:
        """Update API key status in database."""
        result = await self.db.execute(
            update(APIKey).where(APIKey.key_id == key_id).values(status=status.value),
        )
        await self.db.commit()
        return result.rowcount > 0

    async def _cache_key_metadata(self, key_id: str, metadata: APIKeyMetadata) -> None:
        """Cache API key metadata in Redis."""
        key = f"{self._key_prefix}{key_id}"
        data = json.dumps(asdict(metadata), default=str)
        await self.redis.setex(key, 3600, data)  # Cache for 1 hour

    async def _get_cached_metadata(self, key_id: str) -> Optional[APIKeyMetadata]:
        """Get cached API key metadata from Redis."""
        key = f"{self._key_prefix}{key_id}"
        data = await self.redis.get(key)

        if not data:
            return None

        try:
            metadata_dict = json.loads(data)
            # Convert string dates back to datetime
            for field in ["created_at", "expires_at", "last_used_at"]:
                if metadata_dict.get(field):
                    metadata_dict[field] = datetime.fromisoformat(metadata_dict[field])

            # Convert string enums back
            metadata_dict["key_type"] = APIKeyType(metadata_dict["key_type"])
            metadata_dict["status"] = APIKeyStatus(metadata_dict["status"])

            return APIKeyMetadata(**metadata_dict)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    async def _load_key_metadata(self, key_id: str) -> Optional[APIKeyMetadata]:
        """Load API key metadata from database."""
        result = await self.db.execute(select(APIKey).where(APIKey.key_id == key_id))
        key = result.scalar_one_or_none()

        if not key:
            return None

        # Get scopes
        scopes_result = await self.db.execute(
            select(APIKeyScope.scope).where(APIKeyScope.key_id == key_id),
        )
        scopes = [s for s in scopes_result.scalars()]

        return APIKeyMetadata(
            key_id=key.key_id,
            organization_id=key.organization_id,
            organization_name=key.organization_name,
            key_type=APIKeyType(key.key_type),
            status=APIKeyStatus(key.status),
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            allowed_ips=key.allowed_ips,
            allowed_origins=key.allowed_origins,
            scopes=scopes,
            rate_limit=key.rate_limit,
            rate_limit_window=key.rate_limit_window,
            metadata=key.key_metadata,
        )


# FastAPI dependency for API key authentication
async def get_api_key_auth(
    api_key: str,
    required_scope: Optional[str] = None,
    request_ip: Optional[str] = None,
    origin: Optional[str] = None,
    db_session: AsyncSession = None,
    redis_client: redis.Redis = None,
) -> APIKeyMetadata:
    """
    FastAPI dependency for API key authentication.

    Usage:
        @router.get("/api/endpoint")
        async def endpoint(api_key: APIKeyMetadata = Depends(get_api_key_auth)):
            # api_key contains validated metadata
    """
    manager = APIKeyManager(db_session, redis_client)

    is_valid, metadata, error = await manager.validate_api_key(
        api_key=api_key,
        required_scope=required_scope,
        request_ip=request_ip,
        origin=origin,
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return metadata
