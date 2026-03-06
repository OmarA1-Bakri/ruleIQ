"""

ConversionEvent model for tracking freemium to paid conversions.
Records conversion events, revenue attribution, and funnel analytics.
"""

from typing import Any
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from .db_setup import Base


class ConversionEvent(Base):
    """
    Model for tracking freemium to paid conversion events.
    Records conversion types, revenue attribution, and source tracking for ROI analysis.
    """

    __tablename__ = "conversion_events"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("assessment_leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("freemium_assessment_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversion_type = Column(String(100), nullable=False, index=True)
    conversion_stage = Column(String(50), nullable=False, default="initial")
    conversion_source = Column(String(200), nullable=False)
    conversion_value = Column(Numeric(10, 2), nullable=True)
    currency_code = Column(String(3), default="GBP", nullable=False)
    subscription_plan = Column(String(100), nullable=True)
    billing_frequency = Column(String(20), nullable=True)
    attribution_model = Column(String(50), default="first_touch", nullable=False)
    conversion_path = Column(JSONB, nullable=True)
    days_to_convert = Column(Integer, nullable=True)
    touchpoint_count = Column(Integer, default=1, nullable=False)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    utm_term = Column(String(100), nullable=True)
    utm_content = Column(String(100), nullable=True)
    conversion_metadata = Column(JSONB, nullable=True)
    referral_code = Column(String(50), nullable=True)
    discount_applied = Column(String(100), nullable=True)
    conversion_url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    def __init__(self, **kwargs) -> None:
        """Initialize conversion event with default values."""
        super().__init__(**kwargs)
        if not self.conversion_metadata:
            self.conversion_metadata = {}
        if not self.conversion_path:
            self.conversion_path = []

    def add_metadata(self, key: str, value) -> None:
        """Add metadata to the conversion event."""
        if not self.conversion_metadata:
            self.conversion_metadata = {}
        self.conversion_metadata[key] = value

    def add_touchpoint(self, touchpoint: dict) -> None:
        """Add a touchpoint to conversion path."""
        if not self.conversion_path:
            self.conversion_path = []
        self.conversion_path.append(
            {"timestamp": datetime.now(timezone.utc).isoformat(), **touchpoint}
        )
        self.touchpoint_count = len(self.conversion_path)

    def confirm_conversion(self) -> None:
        """Mark conversion as confirmed."""
        self.conversion_stage = "confirmed"
        self.confirmed_at = datetime.now(timezone.utc)

    def complete_conversion(self) -> None:
        """Mark conversion as completed."""
        self.conversion_stage = "completed"
        self.completed_at = datetime.now(timezone.utc)

    def cancel_conversion(self, reason: str = None) -> None:
        """Mark conversion as cancelled."""
        self.conversion_stage = "cancelled"
        self.cancelled_at = datetime.now(timezone.utc)
        if reason:
            self.add_metadata("cancellation_reason", reason)

    def calculate_days_to_convert(self, first_touch_date: datetime) -> None:
        """Calculate days from first touch to conversion."""
        if first_touch_date:
            delta = self.created_at - first_touch_date
            self.days_to_convert = delta.days

    def get_conversion_value_formatted(self) -> str:
        """Get formatted conversion value with currency."""
        if self.conversion_value:
            return f"{self.currency_code} {self.conversion_value:.2f}"
        return "No value"

    def is_high_value_conversion(self, threshold: Decimal = Decimal("100.00")) -> bool:
        """Check if this is a high-value conversion."""
        return self.conversion_value and self.conversion_value >= threshold

    def is_completed(self) -> bool:
        """Check if conversion is completed."""
        return self.conversion_stage == "completed"

    def is_cancelled(self) -> bool:
        """Check if conversion was cancelled."""
        return self.conversion_stage == "cancelled"

    @classmethod
    def create_trial_signup(
        cls,
        lead_id: uuid.UUID,
        session_id: uuid.UUID = None,
        source: str = "freemium_results",
        metadata: dict = None,
    ) -> Any:
        """Factory method for trial signup conversions."""
        return cls(
            lead_id=lead_id,
            session_id=session_id,
            conversion_type="trial_signup",
            conversion_source=source,
            conversion_value=Decimal("0.00"),
            conversion_metadata=metadata or {},
        )

    @classmethod
    def create_paid_subscription(
        cls,
        lead_id: uuid.UUID,
        plan: str,
        value: Decimal,
        frequency: str = "monthly",
        metadata: dict = None,
    ) -> Any:
        """Factory method for paid subscription conversions."""
        return cls(
            lead_id=lead_id,
            conversion_type="paid_subscription",
            conversion_source="subscription_signup",
            conversion_value=value,
            subscription_plan=plan,
            billing_frequency=frequency,
            conversion_metadata=metadata or {},
        )

    @classmethod
    def create_consultation_request(
        cls, lead_id: uuid.UUID, session_id: uuid.UUID = None, metadata: dict = None
    ) -> Any:
        """Factory method for consultation request conversions."""
        return cls(
            lead_id=lead_id,
            session_id=session_id,
            conversion_type="consultation_request",
            conversion_source="freemium_consultation_cta",
            conversion_metadata=metadata or {},
        )

    def __repr__(self) -> str:
        return f"<ConversionEvent(type='{self.conversion_type}', stage='{self.conversion_stage}', value={self.conversion_value})>"
