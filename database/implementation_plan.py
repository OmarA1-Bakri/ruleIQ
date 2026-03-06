import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .db_setup import Base


class ImplementationPlan(Base):
    __tablename__ = "implementation_plans"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("business_profiles.id"),
        nullable=False,
    )
    framework_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("compliance_frameworks.id"),
        nullable=False,
    )

    title = Column(String, nullable=False)
    status = Column(String, default="not_started")  # e.g., not_started, in_progress, completed

    phases = Column(JSON, default=list)  # Stores the detailed plan phases and tasks

    planned_start_date = Column(DateTime, nullable=True)
    planned_end_date = Column(DateTime, nullable=True)
    actual_start_date = Column(DateTime, nullable=True)
    actual_end_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to User
    owner = relationship("User", back_populates="implementation_plans")
