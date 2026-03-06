"""

# Constants
MAX_RETRIES = 3


AIQuestionBank model for storing and managing AI-generated assessment questions.
Supports dynamic question generation with context tags and difficulty weighting.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from .db_setup import Base


class AIQuestionBank(Base):
    """
    Model for AI-generated assessment questions with context-aware categorization.
    Stores questions, options, metadata, and compliance weighting for dynamic selection.
    """

    __tablename__ = "ai_question_bank"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)
    options = Column(JSONB, nullable=True)
    correct_answers = Column(JSONB, nullable=True)
    context_tags = Column(JSONB, nullable=False, default=list)
    difficulty_level = Column(Integer, default=5, nullable=False)
    compliance_weight = Column(Numeric(4, 3), default=Decimal("0.500"), nullable=False)
    usage_frequency = Column(Integer, default=0, nullable=False)
    ai_model_version = Column(String(50), nullable=True)
    generation_prompt = Column(Text, nullable=True)
    generation_cost = Column(Integer, default=0, nullable=False)
    is_validated = Column(Boolean, default=False, nullable=False)
    validation_score = Column(Numeric(3, 2), nullable=True)
    human_reviewed = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs) -> None:
        """Initialize question with default values and validation."""
        super().__init__(**kwargs)
        if not self.context_tags:
            self.context_tags = []
        if self.difficulty_level is not None:
            if self.difficulty_level < 1:
                self.difficulty_level = 1
            elif self.difficulty_level > 10:
                self.difficulty_level = 10
        else:
            self.difficulty_level = 5

    def add_context_tag(self, tag: str) -> None:
        """Add a context tag to the question."""
        if not self.context_tags:
            self.context_tags = []
        if tag not in self.context_tags:
            self.context_tags.append(tag)

    def increment_usage(self) -> None:
        """Increment usage frequency counter."""
        self.usage_frequency += 1

    def mark_validated(self, score: float = None) -> None:
        """Mark question as validated with optional score."""
        self.is_validated = True
        if score is not None:
            self.validation_score = Decimal(str(score))

    def mark_human_reviewed(self) -> None:
        """Mark question as reviewed by human expert."""
        self.human_reviewed = True

    def deactivate(self) -> None:
        """Deactivate question (soft delete)."""
        self.is_active = False
        self.expiry_date = datetime.now(timezone.utc)

    def is_applicable_for_context(self, context_tags: list) -> bool:
        """Check if question is applicable for given context tags."""
        if not self.is_active:
            return False
        if self.expiry_date and datetime.now(timezone.utc) > self.expiry_date:
            return False
        if not context_tags:
            return True
        question_tags = set(self.context_tags or [])
        context_tag_set = set(context_tags)
        return bool(question_tags.intersection(context_tag_set))

    def get_difficulty_category(self) -> str:
        """Get human-readable difficulty category."""
        if self.difficulty_level <= MAX_RETRIES:
            return "Easy"
        elif self.difficulty_level <= 6:
            return "Medium"
        elif self.difficulty_level <= 8:
            return "Hard"
        else:
            return "Expert"

    def __repr__(self) -> str:
        return f"<AIQuestionBank(category='{self.category}', type='{self.question_type}', difficulty={self.difficulty_level})>"
