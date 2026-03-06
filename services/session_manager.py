"""
Session Preservation System for RuleIQ

Ensures zero data loss during deployments and rollbacks by
preserving user sessions in Redis with automatic backup and restore.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from enum import Enum
import hashlib
from contextlib import asynccontextmanager

import redis.asyncio as redis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Session state enumeration."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    BACKING_UP = "backing_up"
    RESTORING = "restoring"
    EXPIRED = "expired"


class SessionData(BaseModel):
    """User session data model."""

    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: SessionState = SessionState.ACTIVE
    data: Dict[str, Any] = Field(default_factory=dict)
    checksum: Optional[str] = None
    backup_version: int = 0

    def calculate_checksum(self) -> str:
        """Calculate data integrity checksum."""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify session data integrity."""
        if not self.checksum:
            return True
        return self.calculate_checksum() == self.checksum

    class Config:
        use_enum_values = True


class SessionManager:
    """
    Manages user sessions with automatic backup and restoration.
    Ensures zero data loss during deployments and rollbacks.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        self.redis = redis_client
        self.session_ttl = 3600 * 24  # 24 hours
        self.backup_ttl = 3600 * 72  # 72 hours for backups
        self._active_sessions: Set[str] = set()
        self._backup_in_progress = False
        self._restore_in_progress = False

    async def initialize(self):
        """Initialize session manager and connect to Redis."""
        if not self.redis:
            from config.cache import get_redis_client

            self.redis = await get_redis_client()

        # Load active sessions from Redis
        await self._load_active_sessions()
        logger.info("Session manager initialized")

    async def _load_active_sessions(self):
        """Load active session IDs from Redis."""
        try:
            pattern = "session:*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    session_id = key.decode().replace("session:", "")
                    self._active_sessions.add(session_id)
                if cursor == 0:
                    break
            logger.info(f"Loaded {len(self._active_sessions)} active sessions")
        except Exception as e:
            logger.error(f"Failed to load active sessions: {e}")

    async def create_session(self, user_id: str, data: Dict[str, Any] = None) -> SessionData:
        """Create a new user session."""
        import uuid

        session_id = str(uuid.uuid4())

        session = SessionData(
            session_id=session_id, user_id=user_id, data=data or {}, state=SessionState.ACTIVE
        )
        session.checksum = session.calculate_checksum()

        # Store in Redis
        await self._store_session(session)
        self._active_sessions.add(session_id)

        # Track metrics
        from monitoring.metrics import get_metrics_collector

        metrics = get_metrics_collector()
        metrics.update_session_count(len(self._active_sessions))

        logger.info(f"Created session {session_id} for user {user_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieve a session by ID."""
        try:
            key = f"session:{session_id}"
            data = await self.redis.get(key)

            if not data:
                return None

            session_dict = json.loads(data)
            session = SessionData(**session_dict)

            # Verify integrity
            if not session.verify_integrity():
                logger.warning(f"Session {session_id} integrity check failed")
                # Try to restore from backup
                session = await self._restore_from_backup(session_id)

            # Update last activity
            if session and session.state == SessionState.ACTIVE:
                session.last_activity = datetime.now(timezone.utc)
                await self._store_session(session)

            return session

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data."""
        session = await self.get_session(session_id)
        if not session:
            return False

        # Backup before update
        await self._backup_session(session)

        # Update data
        session.data.update(data)
        session.checksum = session.calculate_checksum()
        session.last_activity = datetime.now(timezone.utc)

        await self._store_session(session)
        return True

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            # Backup before deletion
            session = await self.get_session(session_id)
            if session:
                await self._backup_session(session)

            key = f"session:{session_id}"
            await self.redis.delete(key)
            self._active_sessions.discard(session_id)

            # Update metrics
            from monitoring.metrics import get_metrics_collector

            metrics = get_metrics_collector()
            metrics.update_session_count(len(self._active_sessions))

            logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def _store_session(self, session: SessionData):
        """Store session in Redis."""
        key = f"session:{session.session_id}"
        value = session.json()
        await self.redis.setex(key, self.session_ttl, value)

    async def _backup_session(self, session: SessionData):
        """Create a backup of the session."""
        try:
            session.backup_version += 1
            backup_key = f"backup:session:{session.session_id}:v{session.backup_version}"
            backup_data = session.json()

            # Store backup with longer TTL
            await self.redis.setex(backup_key, self.backup_ttl, backup_data)

            # Keep track of latest backup version
            version_key = f"backup:version:{session.session_id}"
            await self.redis.setex(version_key, self.backup_ttl, session.backup_version)

            logger.debug(f"Backed up session {session.session_id} (v{session.backup_version})")

        except Exception as e:
            logger.error(f"Failed to backup session {session.session_id}: {e}")

    async def _restore_from_backup(self, session_id: str) -> Optional[SessionData]:
        """Restore session from backup."""
        try:
            # Get latest backup version
            version_key = f"backup:version:{session_id}"
            version = await self.redis.get(version_key)

            if not version:
                logger.warning(f"No backup version found for session {session_id}")
                return None

            # Restore from backup
            backup_key = f"backup:session:{session_id}:v{version.decode()}"
            backup_data = await self.redis.get(backup_key)

            if not backup_data:
                logger.warning(f"No backup data found for session {session_id}")
                return None

            session_dict = json.loads(backup_data)
            session = SessionData(**session_dict)

            logger.info(f"Restored session {session_id} from backup v{version.decode()}")
            return session

        except Exception as e:
            logger.error(f"Failed to restore session {session_id} from backup: {e}")
            return None

    async def backup_all_sessions(self) -> Dict[str, Any]:
        """Backup all active sessions before deployment."""
        if self._backup_in_progress:
            return {"status": "already_in_progress"}

        self._backup_in_progress = True
        stats = {
            "total": len(self._active_sessions),
            "backed_up": 0,
            "failed": 0,
            "start_time": datetime.now(timezone.utc),
        }

        try:
            for session_id in self._active_sessions:
                session = await self.get_session(session_id)
                if session:
                    await self._backup_session(session)
                    stats["backed_up"] += 1
                else:
                    stats["failed"] += 1

            stats["end_time"] = datetime.now(timezone.utc)
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"Backed up {stats['backed_up']}/{stats['total']} sessions")
            return stats

        finally:
            self._backup_in_progress = False

    async def restore_all_sessions(self) -> Dict[str, Any]:
        """Restore all sessions after rollback."""
        if self._restore_in_progress:
            return {"status": "already_in_progress"}

        self._restore_in_progress = True
        stats = {"total": 0, "restored": 0, "failed": 0, "start_time": datetime.now(timezone.utc)}

        try:
            # Find all backup versions
            pattern = "backup:version:*"
            cursor = 0
            session_ids = []

            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    session_id = key.decode().replace("backup:version:", "")
                    session_ids.append(session_id)
                if cursor == 0:
                    break

            stats["total"] = len(session_ids)

            # Restore each session
            for session_id in session_ids:
                session = await self._restore_from_backup(session_id)
                if session:
                    await self._store_session(session)
                    self._active_sessions.add(session_id)
                    stats["restored"] += 1
                else:
                    stats["failed"] += 1

            stats["end_time"] = datetime.now(timezone.utc)
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            # Update metrics
            from monitoring.metrics import get_metrics_collector

            metrics = get_metrics_collector()
            metrics.update_session_count(len(self._active_sessions))

            logger.info(f"Restored {stats['restored']}/{stats['total']} sessions")
            return stats

        finally:
            self._restore_in_progress = False

    async def suspend_session(self, session_id: str) -> bool:
        """Suspend a session during maintenance."""
        session = await self.get_session(session_id)
        if not session:
            return False

        # Backup before suspension
        await self._backup_session(session)

        session.state = SessionState.SUSPENDED
        await self._store_session(session)

        logger.info(f"Suspended session {session_id}")
        return True

    async def resume_session(self, session_id: str) -> bool:
        """Resume a suspended session."""
        session = await self.get_session(session_id)
        if not session:
            return False

        session.state = SessionState.ACTIVE
        session.last_activity = datetime.now(timezone.utc)
        await self._store_session(session)

        logger.info(f"Resumed session {session_id}")
        return True

    async def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        expired_count = 0
        now = datetime.now(timezone.utc)

        for session_id in list(self._active_sessions):
            session = await self.get_session(session_id)
            if session:
                # Check if session is expired (24 hours of inactivity)
                if (now - session.last_activity).total_seconds() > self.session_ttl:
                    await self.delete_session(session_id)
                    expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired sessions")

    @asynccontextmanager
    async def preserve_sessions(self):
        """Context manager for session preservation during deployments."""
        # Backup all sessions
        backup_stats = await self.backup_all_sessions()
        logger.info(f"Session backup completed: {backup_stats}")

        try:
            yield
        except Exception as e:
            # On error, restore sessions
            logger.error(f"Deployment failed: {e}, restoring sessions...")
            restore_stats = await self.restore_all_sessions()
            logger.info(f"Session restore completed: {restore_stats}")
            raise
        finally:
            # Clean up old backups
            await self._cleanup_old_backups()

    async def _cleanup_old_backups(self):
        """Clean up old backup data."""
        try:
            pattern = "backup:session:*"
            cursor = 0
            cleaned = 0

            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    ttl = await self.redis.ttl(key)
                    # Remove backups older than 72 hours
                    if ttl < 0 or ttl > self.backup_ttl:
                        await self.redis.delete(key)
                        cleaned += 1
                if cursor == 0:
                    break

            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old session backups")

        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")

    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        active_count = len(self._active_sessions)

        # Calculate average session age
        total_age = 0
        now = datetime.now(timezone.utc)

        for session_id in list(self._active_sessions)[:100]:  # Sample first 100
            session = await self.get_session(session_id)
            if session:
                age = (now - session.created_at).total_seconds()
                total_age += age

        avg_age = total_age / min(100, active_count) if active_count > 0 else 0

        return {
            "active_sessions": active_count,
            "average_session_age_seconds": avg_age,
            "backup_in_progress": self._backup_in_progress,
            "restore_in_progress": self._restore_in_progress,
        }


# Global session manager instance
_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
        await _session_manager.initialize()
    return _session_manager
