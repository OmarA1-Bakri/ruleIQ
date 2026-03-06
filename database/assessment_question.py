import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .db_setup import Base


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("assessment_sessions.id"),
        nullable=False,
    )
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    question_type = Column(
        String(50), nullable=False
    )  # e.g., 'multiple_choice', 'free_text', 'yes_no'
    options = Column(JSON, nullable=True)  # For multiple choice options
    order = Column(Integer, nullable=False, default=0)  # To maintain question order
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = relationship("AssessmentSession", back_populates="questions")
