"""Persisted compliance risk register for tracking identified risks."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from .db_setup import Base


class ComplianceRisk(Base):
    """Compliance risk register entries tracked per user and framework."""

    __tablename__ = "compliance_risks"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False
    )
    framework_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("compliance_frameworks.id"), nullable=False
    )

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    severity = Column(String, nullable=False, default="medium")
    likelihood = Column(String, nullable=False, default="medium")
    impact = Column(String, nullable=False, default="medium")

    risk_score = Column(Float, nullable=False, default=5.0)

    status = Column(String, nullable=False, default="open")
    mitigation_plan = Column(Text, nullable=True)
    mitigation_status = Column(String, nullable=False, default="not_started")

    category = Column(String, nullable=True)
    control_reference = Column(String, nullable=True)

    owner = Column(String, nullable=True)
    due_date = Column(DateTime, nullable=True)

    ai_metadata = Column(PG_JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", backref="compliance_risks")
    business_profile = relationship("BusinessProfile", backref="compliance_risks")
    framework = relationship("ComplianceFramework", backref="compliance_risks")
