"""
Feature Flag Database Models
Provides persistent storage for feature flags with audit trail
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, Boolean, Float, DateTime, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from database.db_setup import Base


class FeatureFlagStatus(str, Enum):
    """Feature flag status enumeration"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    PERCENTAGE_ROLLOUT = "percentage_rollout"
    USER_TARGETED = "user_targeted"


class FeatureFlag(Base):
    """
    Feature Flag Model with comprehensive configuration
    Stores feature flags with environment-specific overrides and user targeting
    """

    __tablename__ = "feature_flags"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Flag identification
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Basic configuration
    enabled = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default=FeatureFlagStatus.DISABLED.value)

    # Percentage rollout (0.0 to 100.0)
    percentage = Column(Float, default=0.0, nullable=False)

    # User targeting
    whitelist = Column(JSONB, default=list)  # List of user IDs to always enable
    blacklist = Column(JSONB, default=list)  # List of user IDs to always disable

    # Environment configuration
    environment_overrides = Column(JSONB, default=dict)  # {"production": True, "staging": False}
    environments = Column(JSONB, default=list)  # List of allowed environments

    # Additional configuration
    tags = Column(JSONB, default=list)  # Tags for categorization
    flag_metadata = Column(JSONB, default=dict)  # Additional metadata

    # Temporal configuration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)

    # Audit fields
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Version control
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    audit_logs = relationship(
        "FeatureFlagAudit", back_populates="feature_flag", cascade="all, delete-orphan"
    )
    evaluations = relationship(
        "FeatureFlagEvaluation", back_populates="feature_flag", cascade="all, delete-orphan"
    )


class FeatureFlagAudit(Base):
    """
    Audit trail for feature flag changes
    Tracks all modifications to feature flags for compliance and debugging
    """

    __tablename__ = "feature_flag_audits"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to feature flag
    feature_flag_id = Column(UUID(as_uuid=True), ForeignKey("feature_flags.id"), nullable=False)

    # Change information
    action = Column(String(50), nullable=False)  # created, updated, deleted, evaluated
    changes = Column(JSONB, default=dict)  # JSON diff of changes
    previous_state = Column(JSONB, default=dict)  # Previous configuration
    new_state = Column(JSONB, default=dict)  # New configuration

    # User information
    user_id = Column(String(255), nullable=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(100), nullable=True)

    # Context
    environment = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Metadata
    reason = Column(Text, nullable=True)  # Reason for change
    ticket_id = Column(String(100), nullable=True)  # Associated ticket/issue

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationship
    feature_flag = relationship("FeatureFlag", back_populates="audit_logs")


class FeatureFlagEvaluation(Base):
    """
    Feature flag evaluation cache and analytics
    Stores evaluation results for performance and analytics
    """

    __tablename__ = "feature_flag_evaluations"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to feature flag
    feature_flag_id = Column(UUID(as_uuid=True), ForeignKey("feature_flags.id"), nullable=False)

    # Evaluation context
    user_id = Column(String(255), nullable=True, index=True)
    environment = Column(String(50), nullable=False)

    # Result
    evaluated_value = Column(Boolean, nullable=False)
    evaluation_reason = Column(String(255), nullable=True)  # whitelist, blacklist, percentage, etc.

    # Performance metrics
    evaluation_time_ms = Column(Float, nullable=True)  # Time taken to evaluate

    # Cache information
    cached = Column(Boolean, default=False)
    cache_hit = Column(Boolean, default=False)

    # Metadata
    context = Column(JSONB, default=dict)  # Additional context data

    # Timestamp
    evaluated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationship
    feature_flag = relationship("FeatureFlag", back_populates="evaluations")


class FeatureFlagGroup(Base):
    """
    Feature flag groups for organized management
    Groups related feature flags together
    """

    __tablename__ = "feature_flag_groups"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Group information
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    # Configuration
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority groups evaluated first

    # Feature flags in this group
    feature_flag_names = Column(JSONB, default=list)

    # Metadata
    tags = Column(JSONB, default=list)
    audit_metadata = Column(JSONB, default=dict)

    # Audit fields
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
