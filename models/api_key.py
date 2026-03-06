"""
Database models for API Key Management
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    JSON,
    ForeignKey,
    Index,
    ARRAY,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from database.db_setup import Base


class APIKey(Base):
    """API Key model for B2B integrations"""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_id = Column(String(50), unique=True, nullable=False, index=True)
    key_hash = Column(String(255), nullable=False)  # Hashed secret

    # Organization information
    organization_id = Column(String(100), nullable=False, index=True)
    organization_name = Column(String(255), nullable=False)

    # Key properties
    key_type = Column(String(50), nullable=False)  # standard, premium, enterprise, internal
    status = Column(
        String(50), nullable=False, default="active"
    )  # active, suspended, revoked, expired

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    # Security settings
    allowed_ips = Column(ARRAY(String), default=[])
    allowed_origins = Column(ARRAY(String), default=[])

    # Rate limiting
    rate_limit = Column(Integer, nullable=False, default=100)
    rate_limit_window = Column(Integer, nullable=False, default=60)  # seconds

    # Metadata
    key_metadata = Column(JSON, default={})

    # Relationships
    scopes = relationship("APIKeyScope", back_populates="api_key", cascade="all, delete-orphan")
    usage_logs = relationship("APIKeyUsage", back_populates="api_key", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_api_keys_org_status", "organization_id", "status"),
        Index("idx_api_keys_expires", "expires_at"),
    )


class APIKeyScope(Base):
    """API Key scope/permission model"""

    __tablename__ = "api_key_scopes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_id = Column(String(50), ForeignKey("api_keys.key_id", ondelete="CASCADE"), nullable=False)
    scope = Column(String(100), nullable=False)
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    granted_by = Column(String(100), nullable=True)

    # Relationship
    api_key = relationship("APIKey", back_populates="scopes")

    # Indexes
    __table_args__ = (Index("idx_api_key_scopes_key_scope", "key_id", "scope", unique=True),)


class APIKeyUsage(Base):
    """API Key usage tracking model"""

    __tablename__ = "api_key_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_id = Column(String(50), ForeignKey("api_keys.key_id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Request information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(255), nullable=True)
    method = Column(String(10), nullable=True)

    # Response information
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    # Additional metadata
    usage_metadata = Column(JSON, default={})

    # Relationship
    api_key = relationship("APIKey", back_populates="usage_logs")

    # Indexes
    __table_args__ = (
        Index("idx_api_key_usage_key_timestamp", "key_id", "timestamp"),
        Index("idx_api_key_usage_timestamp", "timestamp"),
    )
