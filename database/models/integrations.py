"""

Database models for enterprise integrations and evidence storage
"""

from sqlalchemy import (
    Column,
    String,
    JSON,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    Integer,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database.db_setup import Base


class Integration(Base):
    """
    Stores enterprise integration configurations with encrypted credentials
    """

    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # aws, okta, google_workspace, microsoft_365
    encrypted_credentials = Column(Text, nullable=False)  # AES-256 encrypted JSON
    health_status = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    last_health_check = Column(DateTime)
    configuration_metadata = Column(JSON, default={})  # Provider-specific config
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    evidence_collections = relationship(
        "EvidenceCollection",
        back_populates="integration",
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_user_provider", "user_id", "provider"),
        Index("idx_provider_active", "provider", "is_active"),
        Index("idx_user_active", "user_id", "is_active"),
        UniqueConstraint("user_id", "provider", name="unique_user_provider"),
    )

    def __repr__(self) -> str:
        return f"<Integration {self.provider} for user {self.user_id}>"


class EvidenceCollection(Base):
    """
    Tracks evidence collection requests and their status
    """

    __tablename__ = "evidence_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    framework_id = Column(String(50), nullable=False)  # soc2_type2, iso27001, etc.
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, running, completed, failed
    progress_percentage = Column(Integer, default=0)
    evidence_types_requested = Column(JSON, default=[])
    evidence_types_completed = Column(JSON, default=[])
    quality_score = Column(JSON, default={})  # Per evidence type quality scores
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_completion = Column(DateTime)
    current_activity = Column(String(200))
    errors = Column(JSON, default=[])
    business_profile = Column(JSON, default={})  # Business context for collection
    collection_mode = Column(String(20), default="immediate")  # immediate, scheduled, streaming
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    integration = relationship("Integration", back_populates="evidence_collections")
    evidence_items = relationship(
        "IntegrationEvidenceItem",
        back_populates="collection",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_collection_status", "status"),
        Index("idx_collection_user", "user_id"),
        Index("idx_collection_integration", "integration_id"),
        Index("idx_collection_framework", "framework_id"),
        Index("idx_collection_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EvidenceCollection {self.id} - {self.status}>"


class IntegrationEvidenceItem(Base):
    """
    Individual evidence items collected from integrations
    """

    __tablename__ = "integration_evidence_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_collections.id"),
        nullable=False,
    )
    evidence_type = Column(String(100), nullable=False)  # iam_policies, users, etc.
    source_system = Column(String(50), nullable=False)  # aws, okta, etc.
    resource_id = Column(String(500), nullable=False)  # External resource identifier
    resource_name = Column(String(500), nullable=False)
    evidence_data = Column(JSON, nullable=False)  # The actual evidence content
    compliance_controls = Column(JSONB, default=[])  # CC6.1, CC6.2, etc.
    quality_score = Column(JSON, default={})  # Quality assessment
    data_classification = Column(
        String(50), default="internal"
    )  # public, internal, confidential, restricted
    retention_policy = Column(String(50), default="standard")  # How long to keep this evidence
    checksum = Column(String(64))  # SHA-256 hash for integrity verification
    collected_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    collection = relationship("EvidenceCollection", back_populates="evidence_items")

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_evidence_collection", "collection_id"),
        Index("idx_evidence_type", "evidence_type"),
        Index("idx_evidence_source", "source_system"),
        Index("idx_evidence_resource", "resource_id"),
        Index("idx_evidence_collected", "collected_at"),
        Index(
            "idx_evidence_controls",
            text("compliance_controls jsonb_path_ops"),
            postgresql_using="gin",
        ),  # GIN index for JSON array,
    )

    def __repr__(self) -> str:
        return f"<EvidenceItem {self.evidence_type}:{self.resource_id}>"


class IntegrationHealthLog(Base):
    """
    Historical health check data for integrations
    """

    __tablename__ = "integration_health_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id"),
        nullable=False,
    )
    status = Column(String(20), nullable=False)  # healthy, unhealthy, degraded
    response_time = Column(JSON)  # Response time metrics
    error_details = Column(JSON)  # Error information if unhealthy
    health_data = Column(JSON)  # Additional health metrics
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_health_integration", "integration_id"),
        Index("idx_health_checked", "checked_at"),
        Index("idx_health_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<HealthLog {self.integration_id} - {self.status}>"


class EvidenceAuditLog(Base):
    """
    Audit trail for all evidence-related operations
    """

    __tablename__ = "evidence_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"))
    collection_id = Column(UUID(as_uuid=True), ForeignKey("evidence_collections.id"))
    evidence_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_evidence_items.id"),
    )
    action = Column(String(50), nullable=False)  # create, read, update, delete, export
    resource_type = Column(String(50), nullable=False)  # integration, collection, evidence
    resource_id = Column(String(100), nullable=False)
    details = Column(JSON)  # Additional action details
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(String(500))
    request_id = Column(String(100))  # For tracing requests
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes for audit querying
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_request", "request_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.resource_type}:{self.resource_id}>"
