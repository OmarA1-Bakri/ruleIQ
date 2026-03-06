import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.db_setup import Base


class ReadinessAssessment(Base):
    __tablename__ = "readiness_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    framework_id = Column(
        UUID(as_uuid=True),
        ForeignKey("compliance_frameworks.id"),
        nullable=False,
    )
    business_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business_profiles.id"),
        nullable=False,
    )

    overall_score = Column(Float, nullable=False)
    score_breakdown = Column(JSON, nullable=False)
    priority_actions = Column(JSON, nullable=True)
    quick_wins = Column(JSON, nullable=True)
    score_trend = Column(String, default="stable")
    estimated_readiness_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="readiness_assessments",
        overlaps="readiness_assessments",
    )
    framework = relationship("ComplianceFramework")
    business_profile = relationship("BusinessProfile")

    def __repr__(self) -> str:
        return f"<ReadinessAssessment(id={self.id}, user_id={self.user_id}, framework_id={self.framework_id}, score={self.overall_score})>"
