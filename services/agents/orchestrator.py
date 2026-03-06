"""
Agent Orchestrator Service - Core orchestration logic for multi-agent system.

This service manages agent lifecycles, sessions, and coordination.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from enum import Enum

from models.agentic_models import Agent, AgentSession
from services.agents.trust_algorithm import TrustLevel

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent lifecycle states."""

    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class OrchestratorService:
    """Main orchestrator service for agent management."""

    def __init__(self, db_session: Session) -> None:
        """Initialize orchestrator with database session."""
        self.db = db_session
        self.agent_registry: Dict[UUID, Agent] = {}
        self.active_sessions: Dict[UUID, AgentSession] = {}
        self.max_concurrent_agents = 10
        self.session_timeout = timedelta(hours=1)

    async def create_agent(
        self,
        name: str,
        persona_type: str,
        capabilities: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Create and register a new agent."""
        try:
            agent = Agent(
                agent_id=uuid4(),
                name=name,
                persona_type=persona_type,
                capabilities=capabilities,
                config=config or {},
                is_active=True,
            )

            self.db.add(agent)
            self.db.commit()
            self.db.refresh(agent)

            self.agent_registry[agent.agent_id] = agent
            logger.info(f"Created agent {agent.agent_id}: {name}")

            return agent

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create agent: {e}")
            raise

    async def activate_agent(self, agent_id: UUID) -> bool:
        """Activate an agent for use."""
        try:
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if not agent:
                logger.warning(f"Agent {agent_id} not found")
                return False

            if len(self.agent_registry) >= self.max_concurrent_agents:
                logger.warning("Max concurrent agents reached")
                return False

            agent.is_active = True
            self.db.commit()

            self.agent_registry[agent_id] = agent
            logger.info(f"Activated agent {agent_id}")

            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to activate agent: {e}")
            return False

    async def suspend_agent(self, agent_id: UUID, reason: str = "") -> bool:
        """Suspend an agent temporarily."""
        try:
            if agent_id in self.agent_registry:
                agent = self.agent_registry[agent_id]
                agent.is_active = False

                # End any active sessions
                for session_id, session in self.active_sessions.items():
                    if session.agent_id == agent_id:
                        await self.end_session(session_id)

                self.db.commit()
                del self.agent_registry[agent_id]

                logger.info(f"Suspended agent {agent_id}: {reason}")
                return True

            return False

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to suspend agent: {e}")
            return False

    async def terminate_agent(self, agent_id: UUID) -> bool:
        """Permanently terminate an agent."""
        try:
            # First suspend the agent
            await self.suspend_agent(agent_id, "Termination requested")

            # Mark as terminated in database
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if agent:
                agent.is_active = False
                self.db.commit()
                logger.info(f"Terminated agent {agent_id}")
                return True

            return False

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to terminate agent: {e}")
            return False

    async def create_session(
        self,
        agent_id: UUID,
        user_id: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> AgentSession:
        """Create a new agent session."""
        try:
            if agent_id not in self.agent_registry:
                raise ValueError(f"Agent {agent_id} not active")

            session = AgentSession(
                session_id=uuid4(),
                agent_id=agent_id,
                user_id=user_id,
                started_at=datetime.utcnow(),
                context=initial_context or {},
                session_metadata={},
                trust_level=TrustLevel.L0_OBSERVED,
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            self.active_sessions[session.session_id] = session
            logger.info(f"Created session {session.session_id} for agent {agent_id}")

            return session

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create session: {e}")
            raise

    async def end_session(self, session_id: UUID) -> bool:
        """End an active session."""
        try:
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.ended_at = datetime.utcnow()

                self.db.commit()
                del self.active_sessions[session_id]

                logger.info(f"Ended session {session_id}")
                return True

            return False

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to end session: {e}")
            return False

    async def get_active_agents(self) -> List[Agent]:
        """Get all currently active agents."""
        return list(self.agent_registry.values())

    async def get_active_sessions(self) -> List[AgentSession]:
        """Get all currently active sessions."""
        return list(self.active_sessions.values())

    async def cleanup_expired_sessions(self):
        """Clean up sessions that have exceeded timeout."""
        now = datetime.utcnow()
        expired_sessions = []

        for session_id, session in self.active_sessions.items():
            if now - session.started_at > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            await self.end_session(session_id)
            logger.info(f"Cleaned up expired session {session_id}")

    async def get_agent_metrics(self, agent_id: UUID) -> Dict[str, Any]:
        """Get performance metrics for an agent."""
        try:
            sessions = self.db.query(AgentSession).filter(AgentSession.agent_id == agent_id).all()

            total_sessions = len(sessions)
            active_sessions = len([s for s in sessions if s.ended_at is None])
            avg_session_duration = 0

            if sessions:
                durations = []
                for session in sessions:
                    if session.ended_at:
                        duration = (session.ended_at - session.started_at).total_seconds()
                        durations.append(duration)

                if durations:
                    avg_session_duration = sum(durations) / len(durations)

            return {
                "agent_id": str(agent_id),
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "avg_session_duration_seconds": avg_session_duration,
                "is_active": agent_id in self.agent_registry,
            }

        except SQLAlchemyError as e:
            logger.error(f"Failed to get agent metrics: {e}")
            return {}
