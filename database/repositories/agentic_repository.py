"""Repository pattern implementation for Agentic AI models."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from models.agentic_models import (
    Agent,
    AgentSession,
    AgentDecision,
    TrustMetric,
    AgentKnowledge,
    ConversationHistory,
    AgentAuditLog,
)
from database.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    """Repository for Agent model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(Agent, session)

    def get_by_persona_type(self, persona_type: str) -> List[Agent]:
        """Get all agents of a specific persona type."""
        return (
            self.session.query(Agent)
            .filter(and_(Agent.persona_type == persona_type, Agent.is_active))
            .all()
        )

    def get_active_agents(self) -> List[Agent]:
        """Get all active agents."""
        return self.session.query(Agent).filter(Agent.is_active).all()

    def update_capabilities(self, agent_id: UUID, capabilities: Dict[str, Any]) -> Optional[Agent]:
        """Update agent capabilities."""
        agent = self.get(agent_id)
        if agent:
            agent.capabilities = capabilities
            agent.version += 1
            self.session.commit()
            self.session.refresh(agent)
        return agent


class AgentSessionRepository(BaseRepository[AgentSession]):
    """Repository for AgentSession model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(AgentSession, session)

    def get_active_sessions(self, user_id: Optional[UUID] = None) -> List[AgentSession]:
        """Get active sessions, optionally filtered by user."""
        query = self.session.query(AgentSession).filter(AgentSession.session_state == "active")
        if user_id:
            query = query.filter(AgentSession.user_id == user_id)
        return query.all()

    def get_sessions_by_trust_level(self, min_trust: int) -> List[AgentSession]:
        """Get sessions with minimum trust level."""
        return self.session.query(AgentSession).filter(AgentSession.trust_level >= min_trust).all()

    def update_trust_level(self, session_id: UUID, new_trust_level: int) -> Optional[AgentSession]:
        """Update session trust level."""
        agent_session = self.get(session_id)
        if agent_session and 0 <= new_trust_level <= 4:
            agent_session.trust_level = new_trust_level
            agent_session.version += 1
            self.session.commit()
            self.session.refresh(agent_session)
        return agent_session

    def end_session(self, session_id: UUID) -> Optional[AgentSession]:
        """End an active session."""
        agent_session = self.get(session_id)
        if agent_session and agent_session.session_state == "active":
            agent_session.session_state = "completed"
            agent_session.ended_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(agent_session)
        return agent_session


class AgentDecisionRepository(BaseRepository[AgentDecision]):
    """Repository for AgentDecision model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(AgentDecision, session)

    def get_session_decisions(self, session_id: UUID) -> List[AgentDecision]:
        """Get all decisions for a session."""
        return (
            self.session.query(AgentDecision)
            .filter(AgentDecision.session_id == session_id)
            .order_by(desc(AgentDecision.created_at))
            .all()
        )

    def get_decisions_by_type(self, decision_type: str) -> List[AgentDecision]:
        """Get decisions by type."""
        return (
            self.session.query(AgentDecision)
            .filter(AgentDecision.decision_type == decision_type)
            .all()
        )

    def get_high_confidence_decisions(self, min_confidence: float = 0.8) -> List[AgentDecision]:
        """Get decisions with high confidence scores."""
        return (
            self.session.query(AgentDecision)
            .filter(AgentDecision.confidence_score >= min_confidence)
            .all()
        )

    def update_user_feedback(self, decision_id: UUID, feedback: str) -> Optional[AgentDecision]:
        """Update user feedback for a decision."""
        decision = self.get(decision_id)
        if decision and feedback in ["approved", "rejected", "modified"]:
            decision.user_feedback = feedback
            self.session.commit()
            self.session.refresh(decision)
        return decision


class TrustMetricRepository(BaseRepository[TrustMetric]):
    """Repository for TrustMetric model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(TrustMetric, session)

    def get_session_metrics(self, session_id: UUID) -> List[TrustMetric]:
        """Get all metrics for a session."""
        return (
            self.session.query(TrustMetric)
            .filter(TrustMetric.session_id == session_id)
            .order_by(desc(TrustMetric.recorded_at))
            .all()
        )

    def get_average_metric(self, session_id: UUID, metric_type: str) -> Optional[float]:
        """Get average value for a specific metric type."""
        result = (
            self.session.query(func.avg(TrustMetric.metric_value))
            .filter(
                and_(TrustMetric.session_id == session_id, TrustMetric.metric_type == metric_type)
            )
            .scalar()
        )
        return float(result) if result else None

    def get_latest_metrics(self, session_id: UUID) -> Dict[str, float]:
        """Get latest value for each metric type."""
        subquery = (
            self.session.query(
                TrustMetric.metric_type, func.max(TrustMetric.recorded_at).label("max_recorded")
            )
            .filter(TrustMetric.session_id == session_id)
            .group_by(TrustMetric.metric_type)
            .subquery()
        )

        results = (
            self.session.query(TrustMetric)
            .join(
                subquery,
                and_(
                    TrustMetric.metric_type == subquery.c.metric_type,
                    TrustMetric.recorded_at == subquery.c.max_recorded,
                    TrustMetric.session_id == session_id,
                ),
            )
            .all()
        )

        return {metric.metric_type: float(metric.metric_value) for metric in results}


class AgentKnowledgeRepository(BaseRepository[AgentKnowledge]):
    """Repository for AgentKnowledge model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(AgentKnowledge, session)

    def get_agent_knowledge(
        self, agent_id: UUID, domain: Optional[str] = None
    ) -> List[AgentKnowledge]:
        """Get knowledge items for an agent, optionally filtered by domain."""
        query = self.session.query(AgentKnowledge).filter(AgentKnowledge.agent_id == agent_id)
        if domain:
            query = query.filter(AgentKnowledge.domain == domain)
        return query.order_by(desc(AgentKnowledge.usage_count)).all()

    def get_successful_patterns(self, min_success_rate: float = 0.7) -> List[AgentKnowledge]:
        """Get knowledge patterns with high success rates."""
        return (
            self.session.query(AgentKnowledge)
            .filter(
                and_(
                    AgentKnowledge.success_rate >= min_success_rate,
                    AgentKnowledge.usage_count > 5,  # Minimum usage for reliability
                )
            )
            .all()
        )

    def increment_usage(self, knowledge_id: UUID, was_successful: bool) -> Optional[AgentKnowledge]:
        """Increment usage count and update success rate."""
        knowledge = self.get(knowledge_id)
        if knowledge:
            knowledge.usage_count += 1
            knowledge.last_used_at = datetime.utcnow()

            # Update success rate
            if knowledge.success_rate is None:
                knowledge.success_rate = Decimal("1.0") if was_successful else Decimal("0.0")
            else:
                # Calculate new success rate
                total_successes = float(knowledge.success_rate) * (knowledge.usage_count - 1)
                if was_successful:
                    total_successes += 1
                knowledge.success_rate = Decimal(str(total_successes / knowledge.usage_count))

            self.session.commit()
            self.session.refresh(knowledge)
        return knowledge


class ConversationHistoryRepository(BaseRepository[ConversationHistory]):
    """Repository for ConversationHistory model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(ConversationHistory, session)

    def get_session_conversation(
        self, session_id: UUID, limit: int = 100
    ) -> List[ConversationHistory]:
        """Get conversation history for a session."""
        return (
            self.session.query(ConversationHistory)
            .filter(ConversationHistory.session_id == session_id)
            .order_by(desc(ConversationHistory.created_at))
            .limit(limit)
            .all()
        )

    def get_conversation_thread(self, message_id: UUID) -> List[ConversationHistory]:
        """Get conversation thread from a specific message."""
        messages = []
        current_message = self.get(message_id)

        # Get parent messages
        while current_message and current_message.parent_message_id:
            messages.append(current_message)
            current_message = self.get(current_message.parent_message_id)
        if current_message:
            messages.append(current_message)

        # Reverse to get chronological order
        messages.reverse()

        # Get child messages
        children = (
            self.session.query(ConversationHistory)
            .filter(ConversationHistory.parent_message_id == message_id)
            .order_by(ConversationHistory.created_at)
            .all()
        )

        messages.extend(children)
        return messages

    def get_token_usage_summary(self, session_id: UUID) -> Dict[str, int]:
        """Get token usage summary for a session."""
        result = (
            self.session.query(
                func.sum(ConversationHistory.tokens_used).label("total_tokens"),
                func.count(ConversationHistory.message_id).label("message_count"),
            )
            .filter(ConversationHistory.session_id == session_id)
            .first()
        )

        return {
            "total_tokens": result.total_tokens or 0,
            "message_count": result.message_count or 0,
            "average_tokens": (result.total_tokens or 0) / (result.message_count or 1),
        }


class AgentAuditLogRepository(BaseRepository[AgentAuditLog]):
    """Repository for AgentAuditLog model operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(AgentAuditLog, session)

    def get_agent_audit_logs(
        self, agent_id: UUID, risk_level: Optional[str] = None
    ) -> List[AgentAuditLog]:
        """Get audit logs for an agent, optionally filtered by risk level."""
        query = self.session.query(AgentAuditLog).filter(AgentAuditLog.agent_id == agent_id)
        if risk_level:
            query = query.filter(AgentAuditLog.risk_level == risk_level)
        return query.order_by(desc(AgentAuditLog.timestamp)).all()

    def get_high_risk_actions(self, since: Optional[datetime] = None) -> List[AgentAuditLog]:
        """Get high and critical risk actions."""
        query = self.session.query(AgentAuditLog).filter(
            AgentAuditLog.risk_level.in_(["high", "critical"])
        )
        if since:
            query = query.filter(AgentAuditLog.timestamp >= since)
        return query.order_by(desc(AgentAuditLog.timestamp)).all()

    def get_user_audit_trail(self, user_id: UUID, limit: int = 100) -> List[AgentAuditLog]:
        """Get audit trail for a specific user."""
        return (
            self.session.query(AgentAuditLog)
            .filter(AgentAuditLog.user_id == user_id)
            .order_by(desc(AgentAuditLog.timestamp))
            .limit(limit)
            .all()
        )

    def log_action(
        self,
        agent_id: UUID,
        action_type: str,
        action_details: Dict[str, Any],
        risk_level: Optional[str] = None,
        session_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AgentAuditLog:
        """Create an audit log entry."""
        audit_log = AgentAuditLog(
            agent_id=agent_id,
            session_id=session_id,
            action_type=action_type,
            action_details=action_details,
            risk_level=risk_level,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(audit_log)
        self.session.commit()
        self.session.refresh(audit_log)
        return audit_log
