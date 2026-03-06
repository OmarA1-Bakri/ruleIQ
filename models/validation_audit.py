"""Validation audit models for compliance tracking."""

from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


class ValidationAudit(Base):
    """SQLAlchemy model for validation audit logs."""

    __tablename__ = "validation_audits"

    # Primary key
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Request identification
    validation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    request_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    # User context
    user_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    assessment_id = Column(String(255), nullable=True, index=True)

    # Request details
    original_response = Column(Text, nullable=False)
    response_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash for deduplication
    context = Column(JSON, nullable=True)

    # Validation results
    confidence_score = Column(Float, nullable=False, index=True)
    is_valid = Column(Boolean, nullable=False, index=True)
    requires_review = Column(Boolean, nullable=False, index=True)
    failure_reasons = Column(JSON, nullable=False, default=list)

    # Detailed scores
    semantic_similarity_score = Column(Float, nullable=True)
    citation_coverage_score = Column(Float, nullable=True)
    fact_consistency_score = Column(Float, nullable=True)

    # Performance metrics
    processing_time_ms = Column(Float, nullable=False)
    cache_hit = Column(Boolean, nullable=False, default=False)

    # Regulatory matches
    matched_regulations = Column(JSON, nullable=False, default=list)
    regulation_count = Column(Integer, nullable=False, default=0)

    # Review status
    review_status = Column(String(50), nullable=True)  # pending, in_progress, completed
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    # Additional metadata
    metadata = Column(JSON, nullable=False, default=dict)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_validation_audit_user_timestamp", "user_id", "timestamp"),
        Index("idx_validation_audit_confidence", "confidence_score", "requires_review"),
        Index("idx_validation_audit_review_status", "review_status", "reviewed_at"),
        Index("idx_validation_audit_session", "session_id", "timestamp"),
    )


class HumanReviewQueue(Base):
    """SQLAlchemy model for human review queue."""

    __tablename__ = "human_review_queue"

    # Primary key
    review_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link to validation
    validation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    audit_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Priority and status
    priority = Column(String(20), nullable=False, index=True)  # low, medium, high, critical
    priority_score = Column(Float, nullable=False, index=True)  # Numeric score for sorting
    status = Column(String(50), nullable=False, default="pending", index=True)

    # Review details
    confidence_score = Column(Float, nullable=False)
    failure_reasons = Column(JSON, nullable=False)
    response_text = Column(Text, nullable=False)
    suggested_corrections = Column(JSON, nullable=True)

    # Assignment
    assigned_to = Column(String(255), nullable=True, index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Review outcome
    review_decision = Column(String(50), nullable=True)  # approved, rejected, corrected
    reviewer_notes = Column(Text, nullable=True)
    corrections_applied = Column(JSON, nullable=True)

    # SLA tracking
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    sla_breached = Column(Boolean, nullable=False, default=False)

    # Indexes for queue management
    __table_args__ = (
        Index("idx_review_queue_priority", "status", "priority", "priority_score"),
        Index("idx_review_queue_assignment", "assigned_to", "status"),
        Index("idx_review_queue_sla", "sla_deadline", "sla_breached"),
    )


class ValidationMetricsHistory(Base):
    """SQLAlchemy model for historical validation metrics."""

    __tablename__ = "validation_metrics_history"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Timestamp for this snapshot
    snapshot_timestamp = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Validation counts
    total_validations = Column(Integer, nullable=False)
    successful_validations = Column(Integer, nullable=False)
    failed_validations = Column(Integer, nullable=False)
    human_review_required = Column(Integer, nullable=False)

    # Performance metrics
    average_confidence = Column(Float, nullable=False)
    min_confidence = Column(Float, nullable=True)
    max_confidence = Column(Float, nullable=True)
    median_confidence = Column(Float, nullable=True)

    average_processing_time_ms = Column(Float, nullable=False)
    p50_processing_time_ms = Column(Float, nullable=True)
    p95_processing_time_ms = Column(Float, nullable=True)
    p99_processing_time_ms = Column(Float, nullable=True)
    max_processing_time_ms = Column(Float, nullable=True)

    # Cache metrics
    cache_hit_rate = Column(Float, nullable=False)
    cache_size = Column(Integer, nullable=False)
    cache_evictions = Column(Integer, nullable=True)

    # Error metrics
    error_count = Column(Integer, nullable=False, default=0)
    error_rate = Column(Float, nullable=False, default=0.0)
    timeout_count = Column(Integer, nullable=False, default=0)
    timeout_rate = Column(Float, nullable=False, default=0.0)

    # Regulatory coverage
    unique_regulations_matched = Column(Integer, nullable=False)
    most_common_regulations = Column(JSON, nullable=True)
    most_common_failures = Column(JSON, nullable=True)

    # Review metrics
    reviews_completed = Column(Integer, nullable=False, default=0)
    average_review_time_hours = Column(Float, nullable=True)
    sla_breaches = Column(Integer, nullable=False, default=0)

    # System health
    circuit_breaker_trips = Column(Integer, nullable=False, default=0)
    availability_percentage = Column(Float, nullable=False, default=100.0)

    # Indexes for reporting
    __table_args__ = (
        Index("idx_metrics_history_period", "period_start", "period_end"),
        Index("idx_metrics_history_snapshot", "snapshot_timestamp"),
    )
