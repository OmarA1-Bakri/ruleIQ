import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .db_setup import Base


class AssessmentSession(Base):
    """User assessment sessions for compliance scoping"""

    __tablename__ = "assessment_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("business_profiles.id"),
        nullable=True,
    )

    # Session metadata
    session_type = Column(String, default="compliance_scoping")  # scoping, readiness, etc.
    status = Column(String, default="in_progress")  # in_progress, completed, abandoned

    # Assessment progress
    current_stage = Column(Integer, default=1)
    total_stages = Column(Integer, default=5)
    questions_answered = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)

    # Assessment data
    responses = Column(PG_JSONB, default=dict)  # Question ID -> Answer mapping
    calculated_scores = Column(PG_JSONB, default=dict)
    recommendations = Column(PG_JSONB, default=list)  # Recommended frameworks with scores

    # Session state
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Results
    recommended_frameworks = Column(PG_JSONB, default=list)
    priority_order = Column(PG_JSONB, default=list)
    next_steps = Column(PG_JSONB, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    questions = relationship(
        "AssessmentQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
    )
