"""
import requests

Authentication service for session management and security.
"""

import contextlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config.settings import settings
from database.user import User


class SessionManager:
    """Manages user sessions with Redis backend and in-memory fallback."""

    def __init__(self) -> None:
        self._redis_client: Optional[redis.Redis] = None
        self._redis_available: Optional[bool] = None
        # Fallback in-memory session store
        self._memory_sessions: Dict[str, Dict] = {}

    async def get_redis_client(self) -> Optional[redis.Redis]:
        """Get or create Redis client for session management."""
        if self._redis_available is False:
            return None

        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                )
                # Test the connection
                await self._redis_client.ping()
                self._redis_available = True
            except (ValueError, TypeError):
                self._redis_available = False
                self._redis_client = None
                return None

        return self._redis_client

    async def create_session(
        self, user_id: UUID, token: str, metadata: Optional[Dict] = None
    ) -> str:
        """Create a new user session."""
        session_id = str(uuid4())
        session_data = {
            "user_id": str(user_id),
            "token": token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        redis_client = await self.get_redis_client()

        if redis_client:
            try:
                # Store session with 30-day TTL
                await redis_client.setex(
                    f"session:{session_id}",
                    30 * 24 * 60 * 60,  # 30 days
                    json.dumps(session_data),
                )
                # Also store user -> sessions mapping
                await redis_client.sadd(f"user_sessions:{user_id}", session_id)
                await redis_client.expire(f"user_sessions:{user_id}", 30 * 24 * 60 * 60)
                return session_id
            except json.JSONDecodeError:
                # Fall back to in-memory
                pass

        # Fallback to in-memory storage
        self._memory_sessions[session_id] = session_data
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve session data."""
        redis_client = await self.get_redis_client()

        if redis_client:
            try:
                session_data = await redis_client.get(f"session:{session_id}")
                if session_data:
                    return json.loads(session_data)
            except (json.JSONDecodeError, requests.RequestException):
                pass

        # Fallback to in-memory
        return self._memory_sessions.get(session_id)

    async def update_session_activity(self, session_id: str) -> bool:
        """Update last activity timestamp for a session."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False

        session_data["last_activity"] = datetime.now(timezone.utc).isoformat()

        redis_client = await self.get_redis_client()

        if redis_client:
            try:
                await redis_client.setex(
                    f"session:{session_id}",
                    30 * 24 * 60 * 60,  # 30 days
                    json.dumps(session_data),
                )
                return True
            except json.JSONDecodeError:
                pass

        # Fallback to in-memory
        self._memory_sessions[session_id] = session_data
        return True

    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a specific session."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False

        user_id = session_data.get("user_id")

        redis_client = await self.get_redis_client()

        if redis_client:
            try:
                await redis_client.delete(f"session:{session_id}")
                if user_id:
                    await redis_client.srem(f"user_sessions:{user_id}", session_id)
                return True
            except (ValueError, TypeError):
                pass

        # Fallback to in-memory
        self._memory_sessions.pop(session_id, None)
        return True

    async def get_user_sessions(self, user_id: UUID) -> List[str]:
        """Get all active sessions for a user."""
        redis_client = await self.get_redis_client()

        if redis_client:
            try:
                sessions = await redis_client.smembers(f"user_sessions:{user_id}")
                return list(sessions)
            except (ValueError, TypeError):
                pass

        # Fallback to in-memory
        user_id_str = str(user_id)
        return [
            session_id
            for session_id, data in self._memory_sessions.items()
            if data.get("user_id") == user_id_str
        ]

    async def invalidate_all_user_sessions(self, user_id: UUID) -> int:
        """Invalidate all sessions for a user."""
        sessions = await self.get_user_sessions(user_id)
        count = 0

        for session_id in sessions:
            if await self.invalidate_session(session_id):
                count += 1

        redis_client = await self.get_redis_client()
        if redis_client:
            with contextlib.suppress(Exception):
                await redis_client.delete(f"user_sessions:{user_id}")

        return count

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (for in-memory fallback)."""
        if not self._memory_sessions:
            return 0

        current_time = datetime.now(timezone.utc)
        expired_sessions = []

        for session_id, data in self._memory_sessions.items():
            try:
                last_activity = datetime.fromisoformat(data["last_activity"])
                if (current_time - last_activity).days > 30:
                    expired_sessions.append(session_id)
            except (KeyError, ValueError):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self._memory_sessions.pop(session_id, None)

        return len(expired_sessions)


class AuthService:
    """Main authentication service with session management."""

    def __init__(self) -> None:
        self.session_manager = SessionManager()

    async def create_user_session(
        self, user: User, token: str, metadata: Optional[Dict] = None
    ) -> str:
        """Create a new session for a user after successful authentication."""
        session_metadata = {
            "user_agent": metadata.get("user_agent", "") if metadata else "",
            "ip_address": metadata.get("ip_address", "") if metadata else "",
            "login_time": datetime.now(timezone.utc).isoformat(),
        }

        return await self.session_manager.create_session(
            user.id,
            token,
            session_metadata,
        )

    async def validate_session(self, session_id: str, db: AsyncSession) -> Optional[User]:
        """Validate a session and return the associated user."""
        session_data = await self.session_manager.get_session(session_id)
        if not session_data:
            return None

        # Update last activity
        await self.session_manager.update_session_activity(session_id)

        # Get user from database
        user_id = UUID(session_data["user_id"])
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user or not user.is_active:
            # Invalidate session if user is inactive or not found
            await self.session_manager.invalidate_session(session_id)
            return None

        return user

    async def logout_user(self, user_id: UUID, session_id: Optional[str] = None) -> int:
        """Logout user - invalidate specific session or all sessions."""
        if session_id:
            success = await self.session_manager.invalidate_session(session_id)
            return 1 if success else 0
        else:
            return await self.session_manager.invalidate_all_user_sessions(user_id)

    async def get_user_active_sessions(self, user_id: UUID) -> List[Dict]:
        """Get all active sessions for a user with metadata."""
        session_ids = await self.session_manager.get_user_sessions(user_id)
        sessions = []

        for session_id in session_ids:
            session_data = await self.session_manager.get_session(session_id)
            if session_data:
                sessions.append(
                    {
                        "session_id": session_id,
                        "created_at": session_data.get("created_at"),
                        "last_activity": session_data.get("last_activity"),
                        "metadata": session_data.get("metadata", {}),
                    },
                )

        return sessions

    async def enforce_session_limits(self, user_id: UUID, max_sessions: int = 5) -> int:
        """Enforce maximum number of concurrent sessions per user."""
        sessions = await self.get_user_active_sessions(user_id)

        if len(sessions) <= max_sessions:
            return 0

        # Sort by last activity (oldest first)
        sessions.sort(key=lambda x: x.get("last_activity", ""))

        # Remove oldest sessions
        sessions_to_remove = sessions[: len(sessions) - max_sessions]
        removed_count = 0

        for session in sessions_to_remove:
            if await self.session_manager.invalidate_session(session["session_id"]):
                removed_count += 1

        return removed_count


# Global auth service instance
auth_service = AuthService()
