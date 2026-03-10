"""

FreemiumAssessmentSession model for managing AI-driven assessment sessions.
Stores session data, AI responses, and user interactions for freemium flow.
"""

from typing import Any
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from .db_setup import Base


class FreemiumAssessmentSession(Base):
    """
    Model for managing freemium assessment sessions with AI integration.
    Stores session state, AI responses, and user answers with secure tokens.
    """

    __tablename__ = "freemium_assessment_sessions"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_leads.id", ondelete="CASCADE"), nullable=False
    )
    session_token = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=True)
    current_question_id = Column(String(100), nullable=True)
    total_questions = Column(Integer, nullable=True)
    questions_answered = Column(Integer, nullable=True)
    progress_percentage = Column("progress_percentage", Integer, nullable=True)
    assessment_type = Column(String(50), nullable=True)
    questions_data = Column(JSONB, nullable=True)
    ai_responses = Column(JSONB, nullable=True)
    personalization_data = Column(JSONB, nullable=True)
    compliance_score = Column("compliance_score", Integer, nullable=True)
    risk_assessment = Column(JSONB, nullable=True)
    recommendations = Column(JSONB, nullable=True)
    gaps_identified = Column(JSONB, nullable=True)
    results_summary = Column(Text, nullable=True)
    results_viewed = Column(Boolean, nullable=True, default=False)
    results_viewed_at = Column(DateTime, nullable=True)
    conversion_cta_clicked = Column(Boolean, nullable=True, default=False)
    conversion_cta_clicked_at = Column(DateTime, nullable=True)
    converted_to_paid = Column(Boolean, nullable=True, default=False)
    converted_at = Column(DateTime, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    device_type = Column(String(50), nullable=True)
    browser = Column(String(100), nullable=True)
    session_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    def __init__(self, **kwargs) -> None:
        """Initialize session with secure token and default expiration."""
        super().__init__(**kwargs)
        if not self.session_token:
            self.session_token = self._generate_secure_token()
        if not self.expires_at:
            self.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    def _generate_secure_token(self) -> str:
        """Generate a cryptographically secure session token."""
        return uuid.uuid4().hex + uuid.uuid4().hex

    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def is_active(self) -> bool:
        """Check if session is active (not expired and not completed)."""
        return not self.is_expired() and self.status not in ["completed", "expired"]

    def mark_completed(self) -> None:
        """Mark session as completed and set completion timestamp."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)

    def extend_expiry(self, hours: int = 2) -> None:
        """Extend session expiry by specified hours."""
        if self.is_active():
            self.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)

    @property
    def completion_status(self) -> Any:
        """Alias for status to match service expectations."""
        return self.status

    @completion_status.setter
    def completion_status(self, value) -> None:
        """Alias setter for status."""
        self.status = value

    @property
    def user_answers(self) -> Any:
        """Alias for session_data to match service expectations."""
        return self.session_data or {}

    @user_answers.setter
    def user_answers(self, value) -> None:
        """Alias setter for session_data."""
        self.session_data = value

    def __repr__(self) -> str:
        return f"<FreemiumAssessmentSession(id='{self.id}', status='{self.status}', assessment_type='{self.assessment_type}')>"
