"""SQLAlchemy models for Agentic AI system."""

from enum import IntEnum
from typing import Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Text,
    ForeignKey,
    Float,
    DECIMAL,
    CheckConstraint,
    TIMESTAMP,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


Base = declarative_base()


class TrustLevel(IntEnum):
    """Trust levels for agent autonomy (re-exported for convenience)."""

    L0_OBSERVED = 0
    L1_ASSISTED = 1
    L2_SUPERVISED = 2
    L3_AUTONOMOUS = 3


class SchemaVersion(Base):
    """Track database schema versions."""

    __tablename__ = "schema_versions"

    version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    version_number = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    applied_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    applied_by = Column(String(100))
    execution_time_ms = Column(Integer)


class Agent(Base):
    """AI Agent configuration and metadata."""

    __tablename__ = "agents"

    agent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    persona_type = Column(String(50), nullable=False)
    capabilities = Column(JSONB, nullable=False)
    config = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    sessions = relationship("AgentSession", back_populates="agent", cascade="all, delete-orphan")
    knowledge_items = relationship(
        "AgentKnowledge", back_populates="agent", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AgentAuditLog", back_populates="agent")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "persona_type IN ('developer', 'qa', 'architect', 'security', 'compliance', 'documentation', 'orchestrator')",
            name="check_valid_persona_type",
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "agent_id": str(self.agent_id),
            "name": self.name,
            "persona_type": self.persona_type,
            "capabilities": self.capabilities,
            "config": self.config,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentSession(Base):
    """Agent interaction sessions with users."""

    __tablename__ = "agent_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"))
    trust_level = Column(Integer, default=0)
    context = Column(JSONB)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    ended_at = Column(TIMESTAMP(timezone=True))
    session_state = Column(String(20), default="active")
    session_metadata = Column("metadata", JSONB)  # Map to 'metadata' column in DB
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    agent = relationship("Agent", back_populates="sessions")
    user = relationship("User", backref="agent_sessions")
    decisions = relationship(
        "AgentDecision", back_populates="session", cascade="all, delete-orphan"
    )
    trust_metrics = relationship(
        "TrustMetric", back_populates="session", cascade="all, delete-orphan"
    )
    messages = relationship(
        "ConversationHistory", back_populates="session", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AgentAuditLog", back_populates="session")

    # Constraints
    __table_args__ = (
        CheckConstraint("trust_level >= 0 AND trust_level <= 4", name="check_trust_level_range"),
        CheckConstraint(
            "session_state IN ('active', 'paused', 'completed', 'terminated')",
            name="check_session_state",
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "session_id": str(self.session_id),
            "agent_id": str(self.agent_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "trust_level": self.trust_level,
            "context": self.context,
            "session_state": self.session_state,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "metadata": self.session_metadata,
        }


class SessionContext(Base):
    """Agent session context."""

    __tablename__ = "session_contexts"

    context_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"))
    current_task = Column(Text)
    context_data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # Relationships
    session = relationship("AgentSession", backref="contexts")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "context_id": str(self.context_id),
            "session_id": str(self.session_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "current_task": self.current_task,
            "context_data": self.context_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentDecision(Base):
    """Agent decisions and actions taken."""

    __tablename__ = "agent_decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    decision_type = Column(String(50), nullable=False)
    input_context = Column(JSONB, nullable=False)
    decision_rationale = Column(Text)
    action_taken = Column(JSONB, nullable=False)
    confidence_score = Column(DECIMAL(3, 2))
    user_feedback = Column(String(20))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    execution_time_ms = Column(Integer)

    # Relationships
    session = relationship("AgentSession", back_populates="decisions")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", name="check_confidence_score_range"
        ),
        CheckConstraint(
            "user_feedback IN ('approved', 'rejected', 'modified', 'pending')",
            name="check_user_feedback",
        ),
        CheckConstraint(
            "decision_type IN ('code_generation', 'review', 'test', 'refactor', 'design', 'documentation', 'security_check')",
            name="check_decision_type",
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "decision_id": str(self.decision_id),
            "session_id": str(self.session_id),
            "decision_type": self.decision_type,
            "input_context": self.input_context,
            "decision_rationale": self.decision_rationale,
            "action_taken": self.action_taken,
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "user_feedback": self.user_feedback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "execution_time_ms": self.execution_time_ms,
        }


class TrustMetric(Base):
    """Trust metrics for agent performance."""

    __tablename__ = "trust_metrics"

    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_type = Column(String(50), nullable=False)
    metric_value = Column(DECIMAL(5, 2), nullable=False)
    measurement_context = Column(JSONB)
    recorded_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())

    # Relationships
    session = relationship("AgentSession", back_populates="trust_metrics")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "metric_type IN ('accuracy', 'autonomy', 'complexity', 'reliability', 'efficiency')",
            name="check_metric_type",
        ),
        CheckConstraint(
            """
            (metric_type = 'accuracy' AND metric_value >= 0 AND metric_value <= 100) OR
            (metric_type = 'autonomy' AND metric_value >= 0 AND metric_value <= 100) OR
            (metric_type = 'complexity' AND metric_value >= 0 AND metric_value <= 10) OR
            (metric_type = 'reliability' AND metric_value >= 0 AND metric_value <= 100) OR
            (metric_type = 'efficiency' AND metric_value >= 0 AND metric_value <= 100)
        """,
            name="check_metric_value_ranges",
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "metric_id": str(self.metric_id),
            "session_id": str(self.session_id),
            "metric_type": self.metric_type,
            "metric_value": float(self.metric_value),
            "measurement_context": self.measurement_context,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class AgentKnowledge(Base):
    """Agent knowledge base and patterns."""

    __tablename__ = "agent_knowledge"

    knowledge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_type = Column(String(50), nullable=False)
    domain = Column(String(100), nullable=False)
    content = Column(JSONB, nullable=False)
    embedding = Column(ARRAY(Float))  # Vector embedding for RAG
    usage_count = Column(Integer, default=0)
    success_rate = Column(DECIMAL(3, 2))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    last_used_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    agent = relationship("Agent", back_populates="knowledge_items")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "knowledge_type IN ('pattern', 'solution', 'preference', 'constraint', 'example')",
            name="check_knowledge_type",
        ),
        CheckConstraint(
            "domain IN ('frontend', 'backend', 'testing', 'security', 'infrastructure', 'documentation')",
            name="check_domain",
        ),
        CheckConstraint("success_rate >= 0 AND success_rate <= 1", name="check_success_rate_range"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "knowledge_id": str(self.knowledge_id),
            "agent_id": str(self.agent_id),
            "knowledge_type": self.knowledge_type,
            "domain": self.domain,
            "content": self.content,
            "usage_count": self.usage_count,
            "success_rate": float(self.success_rate) if self.success_rate else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


class ConversationHistory(Base):
    """Conversation history between users and agents."""

    __tablename__ = "conversation_history"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(30))
    parent_message_id = Column(
        UUID(as_uuid=True), ForeignKey("conversation_history.message_id", ondelete="SET NULL")
    )
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    tokens_used = Column(Integer)
    model_used = Column(String(50))

    # Relationships
    session = relationship("AgentSession", back_populates="messages")
    parent_message = relationship(
        "ConversationHistory", remote_side=[message_id], backref="replies"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("role IN ('user', 'agent', 'system', 'tool')", name="check_role"),
        CheckConstraint(
            "message_type IN ('text', 'code', 'command', 'file', 'error', 'warning', 'info')",
            name="check_message_type",
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "message_id": str(self.message_id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type,
            "parent_message_id": str(self.parent_message_id) if self.parent_message_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
        }


class AgentState(Base):
    """Agent state persistence."""

    __tablename__ = "agent_states"

    state_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False
    )
    state_data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # Relationships
    agent = relationship("Agent", backref="states")

    # Indexes
    __table_args__ = (Index("idx_agent_state_agent_version", "agent_id", "version"),)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "state_id": str(self.state_id),
            "agent_id": str(self.agent_id),
            "state_data": self.state_data,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentAuditLog(Base):
    """Audit log for agent actions."""

    __tablename__ = "agent_audit_log"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="RESTRICT"), nullable=False
    )
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.session_id", ondelete="SET NULL")
    )
    action_type = Column(String(50), nullable=False)
    action_details = Column(JSONB, nullable=False)
    risk_level = Column(String(20))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"))
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    ip_address = Column(INET)
    user_agent = Column(Text)

    # Relationships
    agent = relationship("Agent", back_populates="audit_logs")
    session = relationship("AgentSession", back_populates="audit_logs")
    user = relationship("User", backref="agent_audit_logs")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')", name="check_risk_level"
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "audit_id": str(self.audit_id),
            "agent_id": str(self.agent_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "action_type": self.action_type,
            "action_details": self.action_details,
            "risk_level": self.risk_level,
            "user_id": str(self.user_id) if self.user_id else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
        }


class Decision(Base):
    """Agent decision record for tracking and validation."""

    __tablename__ = "decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False
    )
    decision_type = Column(String(50), nullable=False)
    decision_data = Column(JSONB, nullable=False)
    confidence = Column(Float, default=0.5)
    trust_level_required = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())
    executed_at = Column(TIMESTAMP(timezone=True))

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "decision_id": str(self.decision_id),
            "session_id": str(self.session_id),
            "agent_id": str(self.agent_id),
            "decision_type": self.decision_type,
            "decision_data": self.decision_data,
            "confidence": self.confidence,
            "trust_level_required": self.trust_level_required,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class DecisionFeedback(Base):
    """Feedback on agent decisions."""

    __tablename__ = "decision_feedback"

    feedback_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    decision_id = Column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id", ondelete="CASCADE"),
        nullable=False,
    )
    feedback_type = Column(String(50), nullable=False)
    feedback_value = Column(JSONB)
    user_id = Column(String(100))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp())

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "feedback_id": str(self.feedback_id),
            "decision_id": str(self.decision_id),
            "feedback_type": self.feedback_type,
            "feedback_value": self.feedback_value,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
