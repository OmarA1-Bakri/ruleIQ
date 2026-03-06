"""
Session Manager Service - Manages agent sessions and context.

Handles session lifecycle, context persistence, and timeout management.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import json
import asyncio
from enum import Enum

from models.agentic_models import AgentSession, SessionContext
from services.agents.trust_algorithm import TrustLevel

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session status states."""

    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    COMPLETED = "completed"
    ERROR = "error"


class SessionManager:
    """Manages agent session lifecycle and context."""

    def __init__(
        self, db_session: Session, max_session_duration: int = 3600, max_context_size: int = 100000
    ) -> None:
        """Initialize session manager."""
        self.db = db_session
        self.max_session_duration = timedelta(seconds=max_session_duration)
        self.max_context_size = max_context_size
        self.active_sessions: Dict[UUID, SessionStatus] = {}
        self._cleanup_task = None

    async def create_session(
        self,
        agent_id: UUID,
        user_id: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
        trust_level: TrustLevel = TrustLevel.L0_OBSERVED,
    ) -> AgentSession:
        """Create a new agent session."""
        try:
            session = AgentSession(
                session_id=uuid4(),
                agent_id=agent_id,
                user_id=user_id,
                started_at=datetime.utcnow(),
                context=initial_context or {},
                session_metadata={"created_by": "session_manager", "version": "1.0"},
                trust_level=trust_level,
            )

            self.db.add(session)

            # Create initial context record
            context = SessionContext(
                context_id=uuid4(),
                session_id=session.session_id,
                context_data=initial_context or {},
                sequence_number=0,
            )
            self.db.add(context)

            self.db.commit()
            self.db.refresh(session)

            self.active_sessions[session.session_id] = SessionStatus.ACTIVE
            logger.info(f"Created session {session.session_id}")

            # Start cleanup task if not running
            if not self._cleanup_task:
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

            return session

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create session: {e}")
            raise

    async def update_context(
        self, session_id: UUID, context_updates: Dict[str, Any], merge: bool = True
    ) -> bool:
        """Update session context."""
        try:
            session = (
                self.db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
            )

            if not session:
                logger.warning(f"Session {session_id} not found")
                return False

            # Check context size
            context_str = json.dumps(context_updates)
            if len(context_str) > self.max_context_size:
                logger.warning(f"Context too large: {len(context_str)} bytes")
                return False

            # Get latest context
            latest_context = (
                self.db.query(SessionContext)
                .filter(SessionContext.session_id == session_id)
                .order_by(SessionContext.sequence_number.desc())
                .first()
            )

            if merge and latest_context:
                # Merge with existing context
                merged_context = latest_context.context_data.copy()
                merged_context.update(context_updates)
                new_context_data = merged_context
            else:
                new_context_data = context_updates

            # Create new context record
            new_context = SessionContext(
                context_id=uuid4(),
                session_id=session_id,
                context_data=new_context_data,
                sequence_number=(latest_context.sequence_number + 1) if latest_context else 0,
            )
            self.db.add(new_context)

            # Update session context
            session.context = new_context_data
            session.updated_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Updated context for session {session_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update context: {e}")
            return False

    async def get_context(
        self, session_id: UUID, sequence_number: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get session context."""
        try:
            if sequence_number is not None:
                # Get specific context version
                context = (
                    self.db.query(SessionContext)
                    .filter(
                        SessionContext.session_id == session_id,
                        SessionContext.sequence_number == sequence_number,
                    )
                    .first()
                )
            else:
                # Get latest context
                context = (
                    self.db.query(SessionContext)
                    .filter(SessionContext.session_id == session_id)
                    .order_by(SessionContext.sequence_number.desc())
                    .first()
                )

            if context:
                return context.context_data

            # Fallback to session context
            session = (
                self.db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
            )

            return session.context if session else None

        except SQLAlchemyError as e:
            logger.error(f"Failed to get context: {e}")
            return None

    async def serialize_context(self, session_id: UUID) -> Optional[str]:
        """Serialize session context to JSON."""
        context = await self.get_context(session_id)
        if context:
            try:
                return json.dumps(context, indent=2)
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to serialize context: {e}")
                return None
        return None

    async def deserialize_context(self, session_id: UUID, context_str: str) -> bool:
        """Deserialize and update session context from JSON."""
        try:
            context_data = json.loads(context_str)
            return await self.update_context(session_id, context_data, merge=False)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to deserialize context: {e}")
            return False

    async def pause_session(self, session_id: UUID) -> bool:
        """Pause an active session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id] = SessionStatus.PAUSED
            logger.info(f"Paused session {session_id}")
            return True
        return False

    async def resume_session(self, session_id: UUID) -> bool:
        """Resume a paused session."""
        if session_id in self.active_sessions:
            if self.active_sessions[session_id] == SessionStatus.PAUSED:
                self.active_sessions[session_id] = SessionStatus.ACTIVE
                logger.info(f"Resumed session {session_id}")
                return True
        return False

    async def end_session(self, session_id: UUID, reason: str = "normal") -> bool:
        """End an active session."""
        try:
            session = (
                self.db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
            )

            if not session:
                logger.warning(f"Session {session_id} not found")
                return False

            session.ended_at = datetime.utcnow()
            session.session_metadata["end_reason"] = reason

            self.db.commit()

            if session_id in self.active_sessions:
                self.active_sessions[session_id] = SessionStatus.COMPLETED
                del self.active_sessions[session_id]

            logger.info(f"Ended session {session_id}: {reason}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to end session: {e}")
            return False

    async def check_session_timeout(self, session_id: UUID) -> bool:
        """Check if session has timed out."""
        try:
            session = (
                self.db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
            )

            if not session:
                return True

            if session.ended_at:
                return True

            elapsed = datetime.utcnow() - session.started_at
            return elapsed > self.max_session_duration

        except SQLAlchemyError as e:
            logger.error(f"Failed to check session timeout: {e}")
            return True

    async def extend_session(self, session_id: UUID, extension_minutes: int = 30) -> bool:
        """Extend session timeout."""
        try:
            session = (
                self.db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
            )

            if not session or session.ended_at:
                return False

            # Update metadata with extension
            session.session_metadata["extended_at"] = datetime.utcnow().isoformat()
            session.session_metadata["extension_minutes"] = extension_minutes
            session.updated_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Extended session {session_id} by {extension_minutes} minutes")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to extend session: {e}")
            return False

    async def get_session_history(self, session_id: UUID) -> List[SessionContext]:
        """Get full context history for a session."""
        try:
            contexts = (
                self.db.query(SessionContext)
                .filter(SessionContext.session_id == session_id)
                .order_by(SessionContext.sequence_number.asc())
                .all()
            )

            return contexts

        except SQLAlchemyError as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    async def recover_context(self, session_id: UUID, sequence_number: int) -> bool:
        """Recover context from a specific point."""
        try:
            context = (
                self.db.query(SessionContext)
                .filter(
                    SessionContext.session_id == session_id,
                    SessionContext.sequence_number == sequence_number,
                )
                .first()
            )

            if not context:
                logger.warning(f"Context not found at sequence {sequence_number}")
                return False

            session = (
                self.db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
            )

            if session:
                session.context = context.context_data
                session.updated_at = datetime.utcnow()
                self.db.commit()

                logger.info(
                    f"Recovered context for session {session_id} to sequence {sequence_number}"
                )
                return True

            return False

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to recover context: {e}")
            return False

    async def _periodic_cleanup(self):
        """Periodically clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                expired_sessions = []
                for session_id in list(self.active_sessions.keys()):
                    if await self.check_session_timeout(session_id):
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    await self.end_session(session_id, "timeout")

                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def get_active_sessions(self, agent_id: Optional[UUID] = None) -> List[AgentSession]:
        """Get all active sessions."""
        try:
            query = self.db.query(AgentSession).filter(AgentSession.ended_at is None)

            if agent_id:
                query = query.filter(AgentSession.agent_id == agent_id)

            return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
