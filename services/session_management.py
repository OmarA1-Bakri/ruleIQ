"""

# Constants
FIVE_MINUTES_SECONDS = 300

MAX_RETRIES = 3


Enhanced Session Management Service for ruleIQ

Provides advanced session management with:
- Concurrent session limits
- Device tracking and fingerprinting
- Session activity monitoring
- Automatic session cleanup
- Security event tracking
"""

from datetime import timezone
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging
from enum import Enum
from fastapi import Request, HTTPException, status
import redis.asyncio as redis
from user_agents import parse
from config.settings import settings

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    """Session status enumeration"""


class DeviceType(str, Enum):
    """Device type enumeration"""


class SessionManager:
    """
    Advanced session management with security features
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        max_concurrent_sessions: int = 5,
        session_timeout_minutes: int = 60,
        enable_device_tracking: bool = True,
        enable_geo_tracking: bool = True,
    ) -> None:
        """
        Initialize session manager

        Args:
            redis_client: Redis client for session storage
            max_concurrent_sessions: Maximum concurrent sessions per user
            session_timeout_minutes: Session timeout in minutes
            enable_device_tracking: Enable device fingerprinting
            enable_geo_tracking: Enable geographical tracking
        """
        self.redis_client = redis_client
        self.max_concurrent_sessions = max_concurrent_sessions
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.enable_device_tracking = enable_device_tracking
        self.enable_geo_tracking = enable_geo_tracking
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
        self.device_prefix = "device:"

    async def create_session(
        self, user_id: str, request: Request, additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for a user

        Args:
            user_id: User identifier
            request: FastAPI request object
            additional_data: Additional session data

        Returns:
            Session information dictionary
        """
        session_id = secrets.token_urlsafe(32)
        device_info = self._extract_device_info(request)
        device_fingerprint = self._generate_device_fingerprint(device_info)
        location_info = self._extract_location_info(request)
        await self._check_concurrent_sessions(user_id)
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + self.session_timeout).isoformat(),
            "status": SessionStatus.ACTIVE.value,
            "device_info": device_info,
            "device_fingerprint": device_fingerprint,
            "location_info": location_info,
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "additional_data": additional_data or {},
        }
        if self.redis_client:
            await self._store_session_redis(session_id, user_id, session_data)
        if self.enable_device_tracking:
            await self._track_device(user_id, device_fingerprint, device_info)
        logger.info("Session created for user %s: %s" % (user_id, session_id))
        return {
            "session_id": session_id,
            "expires_at": session_data["expires_at"],
            "device_fingerprint": device_fingerprint,
        }

    async def validate_session(
        self, session_id: str, request: Optional[Request] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate a session

        Args:
            session_id: Session identifier
            request: Optional request for additional validation

        Returns:
            Tuple of (is_valid, session_data)
        """
        if not self.redis_client:
            return False, None
        session_key = f"{self.session_prefix}{session_id}"
        session_data = await self.redis_client.get(session_key)
        if not session_data:
            return False, None
        session_data = json.loads(session_data)
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            await self.revoke_session(session_id, "expired")
            return False, None
        if session_data["status"] != SessionStatus.ACTIVE.value:
            return False, None
        if request:
            if settings.strict_session_validation:
                if request.client and request.client.host != session_data["ip_address"]:
                    logger.warning("Session %s IP mismatch" % session_id)
                    session_data["status"] = SessionStatus.SUSPICIOUS.value
                    await self._update_session(session_id, session_data)
            if self.enable_device_tracking:
                device_info = self._extract_device_info(request)
                current_fingerprint = self._generate_device_fingerprint(device_info)
                if current_fingerprint != session_data["device_fingerprint"]:
                    logger.warning("Session %s device fingerprint mismatch" % session_id)
                    session_data["status"] = SessionStatus.SUSPICIOUS.value
                    await self._update_session(session_id, session_data)
        session_data["last_activity"] = datetime.now(timezone.utc).isoformat()
        await self._update_session(session_id, session_data)
        return True, session_data

    async def revoke_session(self, session_id: str, reason: str = "manual") -> bool:
        """
        Revoke a session

        Args:
            session_id: Session identifier
            reason: Revocation reason

        Returns:
            Success status
        """
        if not self.redis_client:
            return False
        session_key = f"{self.session_prefix}{session_id}"
        session_data = await self.redis_client.get(session_key)
        if not session_data:
            return False
        session_data = json.loads(session_data)
        session_data["status"] = SessionStatus.REVOKED.value
        session_data["revoked_at"] = datetime.now(timezone.utc).isoformat()
        session_data["revocation_reason"] = reason
        await self.redis_client.setex(session_key, 60, json.dumps(session_data))
        user_sessions_key = f"{self.user_sessions_prefix}{session_data['user_id']}"
        await self.redis_client.srem(user_sessions_key, session_id)
        logger.info("Session revoked: %s (reason: %s)" % (session_id, reason))
        return True

    async def revoke_all_user_sessions(
        self, user_id: str, except_current: Optional[str] = None
    ) -> int:
        """
        Revoke all sessions for a user

        Args:
            user_id: User identifier
            except_current: Optional session ID to keep active

        Returns:
            Number of revoked sessions
        """
        if not self.redis_client:
            return 0
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        session_ids = await self.redis_client.smembers(user_sessions_key)
        revoked_count = 0
        for session_id in session_ids:
            session_id = session_id.decode() if isinstance(session_id, bytes) else session_id
            if session_id != except_current:
                if await self.revoke_session(session_id, "bulk_revocation"):
                    revoked_count += 1
        return revoked_count

    async def get_user_sessions(
        self, user_id: str, include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user

        Args:
            user_id: User identifier
            include_expired: Include expired sessions

        Returns:
            List of session data
        """
        if not self.redis_client:
            return []
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        session_ids = await self.redis_client.smembers(user_sessions_key)
        sessions = []
        for session_id in session_ids:
            session_id = session_id.decode() if isinstance(session_id, bytes) else session_id
            session_key = f"{self.session_prefix}{session_id}"
            session_data = await self.redis_client.get(session_key)
            if session_data:
                session_data = json.loads(session_data)
                expires_at = datetime.fromisoformat(session_data["expires_at"])
                is_expired = datetime.now(timezone.utc) > expires_at
                if not is_expired or include_expired:
                    sessions.append(session_data)
        sessions.sort(key=lambda x: x["last_activity"], reverse=True)
        return sessions

    async def get_active_session_count(self, user_id: str) -> int:
        """
        Get count of active sessions for a user

        Args:
            user_id: User identifier

        Returns:
            Number of active sessions
        """
        sessions = await self.get_user_sessions(user_id, include_expired=False)
        return len([s for s in sessions if s["status"] == SessionStatus.ACTIVE.value])

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions

        Returns:
            Number of cleaned sessions
        """
        if not self.redis_client:
            return 0
        pattern = f"{self.session_prefix}*"
        cursor = 0
        cleaned_count = 0
        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                key = key.decode() if isinstance(key, bytes) else key
                session_data = await self.redis_client.get(key)
                if session_data:
                    session_data = json.loads(session_data)
                    expires_at = datetime.fromisoformat(session_data["expires_at"])
                    if datetime.now(timezone.utc) > expires_at:
                        session_id = key.replace(self.session_prefix, "")
                        await self.revoke_session(session_id, "expired")
                        cleaned_count += 1
            if cursor == 0:
                break
        logger.info("Cleaned %s expired sessions" % cleaned_count)
        return cleaned_count

    def _extract_device_info(self, request: Request) -> Dict[str, Any]:
        """Extract device information from request"""
        user_agent_string = request.headers.get("User-Agent", "")
        user_agent = parse(user_agent_string)
        if user_agent.is_bot:
            device_type = DeviceType.BOT
        elif user_agent.is_mobile:
            device_type = DeviceType.MOBILE
        elif user_agent.is_tablet:
            device_type = DeviceType.TABLET
        elif user_agent.is_pc:
            device_type = DeviceType.DESKTOP
        else:
            device_type = DeviceType.UNKNOWN
        return {
            "type": device_type.value,
            "browser": {
                "family": user_agent.browser.family,
                "version": user_agent.browser.version_string,
            },
            "os": {"family": user_agent.os.family, "version": user_agent.os.version_string},
            "device": {
                "family": user_agent.device.family,
                "brand": user_agent.device.brand,
                "model": user_agent.device.model,
            },
        }

    def _generate_device_fingerprint(self, device_info: Dict[str, Any]) -> str:
        """Generate device fingerprint"""
        fingerprint_data = json.dumps(device_info, sort_keys=True)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    def _extract_location_info(self, request: Request) -> Dict[str, Any]:
        """Extract location information from request"""
        location_info = {
            "ip": request.client.host if request.client else "unknown",
            "country": "unknown",
            "city": "unknown",
            "timezone": "unknown",
        }
        cf_country = request.headers.get("CF-IPCountry")
        if cf_country:
            location_info["country"] = cf_country
        x_forwarded = request.headers.get("X-Forwarded-For")
        if x_forwarded:
            location_info["forwarded_ips"] = x_forwarded.split(",")
        return location_info

    async def _check_concurrent_sessions(self, user_id: str) -> None:
        """Check and enforce concurrent session limits"""
        active_count = await self.get_active_session_count(user_id)
        if active_count >= self.max_concurrent_sessions:
            sessions = await self.get_user_sessions(user_id)
            if sessions:
                oldest_session = min(sessions, key=lambda x: x["created_at"])
                await self.revoke_session(oldest_session["session_id"], "concurrent_limit_exceeded")

    async def _store_session_redis(
        self, session_id: str, user_id: str, session_data: Dict[str, Any]
    ) -> None:
        """Store session in Redis"""
        if not self.redis_client:
            return
        session_key = f"{self.session_prefix}{session_id}"
        await self.redis_client.setex(
            session_key, int(self.session_timeout.total_seconds()), json.dumps(session_data)
        )
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        await self.redis_client.sadd(user_sessions_key, session_id)
        await self.redis_client.expire(user_sessions_key, int(self.session_timeout.total_seconds()))

    async def _update_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Update session in Redis"""
        if not self.redis_client:
            return
        session_key = f"{self.session_prefix}{session_id}"
        ttl = await self.redis_client.ttl(session_key)
        if ttl > 0:
            await self.redis_client.setex(session_key, ttl, json.dumps(session_data))

    async def _track_device(
        self, user_id: str, device_fingerprint: str, device_info: Dict[str, Any]
    ) -> None:
        """Track device usage"""
        if not self.redis_client:
            return
        device_key = f"{self.device_prefix}{user_id}:{device_fingerprint}"
        device_data = {
            "fingerprint": device_fingerprint,
            "info": device_info,
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "access_count": 1,
        }
        existing = await self.redis_client.get(device_key)
        if existing:
            existing_data = json.loads(existing)
            device_data["first_seen"] = existing_data["first_seen"]
            device_data["access_count"] = existing_data.get("access_count", 0) + 1
        await self.redis_client.setex(device_key, 86400 * 30, json.dumps(device_data))

    async def get_user_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all tracked devices for a user

        Args:
            user_id: User identifier

        Returns:
            List of device information
        """
        if not self.redis_client:
            return []
        pattern = f"{self.device_prefix}{user_id}:*"
        cursor = 0
        devices = []
        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                key = key.decode() if isinstance(key, bytes) else key
                device_data = await self.redis_client.get(key)
                if device_data:
                    devices.append(json.loads(device_data))
            if cursor == 0:
                break
        devices.sort(key=lambda x: x["last_seen"], reverse=True)
        return devices

    async def detect_suspicious_activity(self, user_id: str, request: Request) -> List[str]:
        """
        Detect suspicious session activity

        Args:
            user_id: User identifier
            request: Current request

        Returns:
            List of suspicious indicators
        """
        indicators = []
        sessions = await self.get_user_sessions(user_id)
        recent_sessions = [
            s
            for s in sessions
            if (
                datetime.now(timezone.utc) - datetime.fromisoformat(s["created_at"])
            ).total_seconds()
            < FIVE_MINUTES_SECONDS
        ]
        if len(recent_sessions) > MAX_RETRIES:
            indicators.append("rapid_session_creation")
        if sessions:
            unique_ips = set(s["ip_address"] for s in sessions)
            if len(unique_ips) > MAX_RETRIES:
                indicators.append("multiple_locations")
        user_agent = request.headers.get("User-Agent", "")
        if not user_agent or "bot" in user_agent.lower():
            indicators.append("suspicious_user_agent")
        if request.client:
            ip = request.client.host
            if self._is_tor_exit_node(ip):
                indicators.append("tor_exit_node")
        return indicators

    def _is_tor_exit_node(self, ip: str) -> bool:
        """Check if IP is a TOR exit node (simplified)"""
        tor_ranges = ["198.96.155.3"]
        return ip in tor_ranges


_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """
    Get or create session manager instance

    Returns:
        SessionManager instance
    """
    global _session_manager
    if _session_manager is None:
        redis_client = None
        if settings.redis_url:
            try:
                redis_client = await redis.from_url(
                    settings.redis_url, encoding="utf-8", decode_responses=True
                )
                await redis_client.ping()
                logger.info("Session manager connected to Redis")
            except Exception as e:
                logger.warning("Failed to connect to Redis for session management: %s" % e)
                redis_client = None
        _session_manager = SessionManager(
            redis_client=redis_client,
            max_concurrent_sessions=settings.max_concurrent_sessions,
            session_timeout_minutes=settings.session_timeout_minutes,
            enable_device_tracking=settings.enable_device_tracking,
            enable_geo_tracking=settings.enable_geo_tracking,
        )
    return _session_manager


async def validate_session_dependency(
    request: Request, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    FastAPI dependency for session validation

    Args:
        request: FastAPI request
        session_id: Optional session ID from header/cookie

    Returns:
        Session data if valid

    Raises:
        HTTPException if session invalid
    """
    if not session_id:
        session_id = request.headers.get("X-Session-ID")
    if not session_id:
        session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session provided")
    session_manager = await get_session_manager()
    is_valid, session_data = await session_manager.validate_session(session_id, request)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        )
    return session_data
