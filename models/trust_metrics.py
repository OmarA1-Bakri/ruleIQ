"""Trust metrics models for trust progression system."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import IntEnum
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4

Base = declarative_base()


class TrustLevelEnum(IntEnum):
    """Trust levels for database storage."""

    L0_OBSERVED = 0
    L1_ASSISTED = 1
    L2_SUPERVISED = 2
    L3_AUTONOMOUS = 3


class TrustMetrics(Base):
    """SQLAlchemy model for user trust metrics."""

    __tablename__ = "trust_metrics"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User identification
    user_id = Column(String(255), nullable=False, index=True, unique=True)
    session_id = Column(String(255), nullable=True, index=True)

    # Current trust state
    current_trust_level = Column(Integer, nullable=False, default=0)
    trust_score = Column(Float, nullable=False, default=0.0, index=True)
    last_calculated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Action statistics
    total_actions = Column(Integer, nullable=False, default=0)
    approved_actions = Column(Integer, nullable=False, default=0)
    rejected_actions = Column(Integer, nullable=False, default=0)
    successful_actions = Column(Integer, nullable=False, default=0)
    failed_actions = Column(Integer, nullable=False, default=0)

    # Behavioral scores
    approval_rate = Column(Float, nullable=False, default=0.0)
    success_rate = Column(Float, nullable=False, default=0.0)
    consistency_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    error_rate = Column(Float, nullable=False, default=0.0)

    # Time-based metrics
    account_created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_action_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_promotion_at = Column(DateTime(timezone=True), nullable=True)
    last_demotion_at = Column(DateTime(timezone=True), nullable=True)
    days_active = Column(Integer, nullable=False, default=0)

    # Average performance
    avg_response_time_ms = Column(Float, nullable=True)
    avg_complexity_handled = Column(Float, nullable=True)

    # Violation tracking
    total_violations = Column(Integer, nullable=False, default=0)
    recent_violations_30d = Column(Integer, nullable=False, default=0)
    critical_errors = Column(Integer, nullable=False, default=0)
    security_violations = Column(Integer, nullable=False, default=0)

    # Override information
    manual_override_active = Column(Boolean, nullable=False, default=False)
    override_reason = Column(Text, nullable=True)
    override_by = Column(String(255), nullable=True)
    override_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata = Column(JSON, nullable=False, default=dict)

    # Indexes for queries
    __table_args__ = (
        Index("idx_trust_metrics_score", "trust_score", "current_trust_level"),
        Index("idx_trust_metrics_activity", "last_action_at", "days_active"),
        Index("idx_trust_metrics_violations", "total_violations", "recent_violations_30d"),
    )


class TrustActionLog(Base):
    """SQLAlchemy model for detailed action logging."""

    __tablename__ = "trust_action_logs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Action identification
    action_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    # Action details
    action_type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    trust_level_at_time = Column(Integer, nullable=False)

    # Action outcome
    was_suggested = Column(Boolean, nullable=False, default=True)
    was_approved = Column(Boolean, nullable=False)
    was_executed = Column(Boolean, nullable=False, default=False)
    was_successful = Column(Boolean, nullable=True)

    # Risk and complexity
    risk_level = Column(String(20), nullable=True)
    risk_score = Column(Float, nullable=True)
    complexity_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Performance
    decision_time_ms = Column(Float, nullable=True)
    execution_time_ms = Column(Float, nullable=True)

    # Error information
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    metadata = Column(JSON, nullable=False, default=dict)

    # Indexes for analysis
    __table_args__ = (
        Index("idx_action_log_user_time", "user_id", "timestamp"),
        Index("idx_action_log_type_outcome", "action_type", "was_successful"),
        Index("idx_action_log_session", "session_id", "timestamp"),
    )


class TrustTransitionLog(Base):
    """SQLAlchemy model for trust level transitions."""

    __tablename__ = "trust_transition_logs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Transition identification
    user_id = Column(String(255), nullable=False, index=True)
    transition_id = Column(String(255), nullable=False, unique=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    # Transition details
    from_level = Column(Integer, nullable=False)
    to_level = Column(Integer, nullable=False)
    transition_type = Column(String(20), nullable=False)  # promotion, demotion, override

    # Scores at transition
    trust_score_before = Column(Float, nullable=False)
    trust_score_after = Column(Float, nullable=True)
    approval_rate = Column(Float, nullable=True)
    success_rate = Column(Float, nullable=True)

    # Authorization
    authorized_by = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    is_manual_override = Column(Boolean, nullable=False, default=False)

    # Supporting metrics
    total_actions_at_transition = Column(Integer, nullable=False)
    days_at_previous_level = Column(Integer, nullable=True)
    violations_since_last_transition = Column(Integer, nullable=False, default=0)

    # Metadata
    metadata = Column(JSON, nullable=False, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_transition_log_user", "user_id", "timestamp"),
        Index("idx_transition_log_type", "transition_type", "timestamp"),
    )


# Pydantic models for API


class TrustMetricsResponse(BaseModel):
    """Response model for trust metrics API."""

    model_config = ConfigDict(use_enum_values=True)

    user_id: str
    current_trust_level: int
    trust_score: float

    # Statistics
    total_actions: int
    approval_rate: float
    success_rate: float
    consistency_score: float
    complexity_score: float

    # Time metrics
    account_age_days: int
    last_action: Optional[datetime] = None
    last_promotion: Optional[datetime] = None

    # Violations
    recent_violations: int
    total_violations: int

    # Eligibility
    eligible_for_promotion: bool
    next_level_requirements: Optional[Dict[str, Any]] = None


class TrustProgressionRequest(BaseModel):
    """Request model for trust progression changes."""

    user_id: str
    action: str  # promote, demote, override
    reason: str
    authorized_by: str
    severity: Optional[str] = None  # For demotions
    target_level: Optional[int] = None  # For overrides
    expires_at: Optional[datetime] = None  # For temporary overrides


class TrustActionRequest(BaseModel):
    """Request model for logging trust actions."""

    user_id: str
    session_id: Optional[str] = None
    action_type: str
    description: Optional[str] = None
    was_approved: bool
    was_successful: Optional[bool] = None
    complexity: float = Field(ge=0.0, le=1.0, default=0.5)
    risk_score: Optional[float] = Field(ge=0.0, le=1.0, default=None)
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrustAuditReport(BaseModel):
    """Comprehensive audit report for trust system."""

    user_id: str
    report_generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Current state
    current_trust_level: int
    trust_score: float
    is_manually_overridden: bool

    # Historical data
    promotion_count: int
    demotion_count: int
    transitions: List[Dict[str, Any]]

    # Action summary
    total_actions: int
    actions_last_30_days: int
    approval_rate_30d: float
    success_rate_30d: float

    # Violations
    total_violations: int
    recent_violations: List[Dict[str, Any]]
    critical_incidents: List[Dict[str, Any]]

    # Recommendations
    recommended_action: Optional[str] = None
    risk_assessment: str  # low, medium, high
    notes: List[str] = Field(default_factory=list)
