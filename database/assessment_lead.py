"""

AssessmentLead model for capturing leads through the freemium assessment flow.
Stores email capture, UTM tracking, and lead scoring data.
"""

import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .db_setup import Base


class AssessmentLead(Base):
    """
    Model for capturing leads through the freemium assessment flow.
    Stores email capture, UTM tracking, and lead scoring data.
    """

    __tablename__ = "assessment_leads"

    # Primary identifiers
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company_name = Column(String(200), nullable=True)
    company_size = Column(String(50), nullable=True)
    industry = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)

    # UTM tracking parameters
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    utm_term = Column(String(200), nullable=True)
    utm_content = Column(String(200), nullable=True)
    referrer_url = Column(Text, nullable=True)
    landing_page = Column(String(500), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible

    # Lead scoring and status
    lead_score = Column(Integer, default=0)
    lead_status = Column(String(20), default="new")  # new, qualified, converted, lost
    conversion_probability = Column(Float, nullable=True)
    engagement_score = Column(Integer, default=0)

    # Newsletter and marketing consent
    newsletter_subscribed = Column(Boolean, default=False)
    marketing_consent = Column(Boolean, default=False)  # Note: this is the correct column name
    consent_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_activity_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AssessmentLead(email='{self.email}', score={self.lead_score})>"
