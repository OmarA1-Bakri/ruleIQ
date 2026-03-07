"""

Database models for AI cost tracking and management.

Provides persistent storage for cost metrics, budget configurations,
alerts, and optimization insights.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    Numeric,
    JSON,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base


class AIUsageLog(Base):
    """Log of individual AI API usage events."""

    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Request identification
    request_id = Column(String(255), unique=True, index=True, nullable=False)
    session_id = Column(String(255), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)

    # Service and model information
    service_name = Column(String(100), index=True, nullable=False)
    model_name = Column(String(100), index=True, nullable=False)
    provider = Column(String(50), nullable=False)  # google, openai, etc.

    # Token usage
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Cost information
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    cost_per_token = Column(Numeric(10, 8), nullable=False, default=0)

    # Performance metrics
    response_time_ms = Column(Numeric(10, 2), nullable=True)
    response_quality_score = Column(Numeric(3, 2), nullable=True)  # 0.00 - 1.00
    cache_hit = Column(Boolean, nullable=False, default=False)
    error_occurred = Column(Boolean, nullable=False, default=False)

    # Timing
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    date_key = Column(Date, nullable=False, index=True)  # For efficient daily queries
    hour_key = Column(Integer, nullable=False, index=True)  # 0-23 for hourly analysis

    # Additional context
    endpoint = Column(String(255), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    metadata = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="ai_usage_logs")

    # Constraints
    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="check_input_tokens_positive"),
        CheckConstraint("output_tokens >= 0", name="check_output_tokens_positive"),
        CheckConstraint("total_tokens >= 0", name="check_total_tokens_positive"),
        CheckConstraint("cost_usd >= 0", name="check_cost_positive"),
        CheckConstraint(
            "response_quality_score >= 0 AND response_quality_score <= 1",
            name="check_quality_score_range",
        ),
        Index("idx_usage_service_date", "service_name", "date_key"),
        Index("idx_usage_model_date", "model_name", "date_key"),
        Index("idx_usage_user_date", "user_id", "date_key"),
        Index("idx_usage_timestamp", "timestamp"),
        Index(
            "idx_usage_cost_analysis",
            "service_name",
            "model_name",
            "date_key",
            "cost_usd",
        ),
    )


class AIModelConfig(Base):
    """Configuration for AI model costs and capabilities."""

    __tablename__ = "ai_model_configs"

    id = Column(Integer, primary_key=True, index=True)

    # Model identification
    model_name = Column(String(100), unique=True, nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model_family = Column(String(100), nullable=True)  # e.g., "gemini", "gpt-4"

    # Cost configuration (per million tokens)
    input_cost_per_million = Column(Numeric(10, 6), nullable=False)
    output_cost_per_million = Column(Numeric(10, 6), nullable=False)

    # Model capabilities
    context_window = Column(Integer, nullable=False)
    max_output_tokens = Column(Integer, nullable=False)
    supports_streaming = Column(Boolean, nullable=False, default=False)
    supports_function_calling = Column(Boolean, nullable=False, default=False)

    # Performance characteristics
    average_response_time_ms = Column(Numeric(10, 2), nullable=True)
    reliability_score = Column(Numeric(3, 2), nullable=True)  # 0.00 - 1.00
    quality_score = Column(Numeric(3, 2), nullable=True)  # 0.00 - 1.00

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    deprecation_date = Column(Date, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    description = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "input_cost_per_million >= 0",
            name="check_input_cost_positive",
        ),
        CheckConstraint(
            "output_cost_per_million >= 0",
            name="check_output_cost_positive",
        ),
        CheckConstraint("context_window > 0", name="check_context_window_positive"),
        CheckConstraint("max_output_tokens > 0", name="check_max_output_positive"),
        CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="check_reliability_range",
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="check_quality_range",
        ),
    )


class BudgetConfiguration(Base):
    """Budget configuration and limits."""

    __tablename__ = "budget_configurations"

    id = Column(Integer, primary_key=True, index=True)

    # Scope
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    service_name = Column(String(100), nullable=True, index=True)
    is_global = Column(Boolean, nullable=False, default=False)

    # Budget limits
    daily_limit = Column(Numeric(10, 2), nullable=True)
    weekly_limit = Column(Numeric(10, 2), nullable=True)
    monthly_limit = Column(Numeric(10, 2), nullable=True)
    yearly_limit = Column(Numeric(10, 2), nullable=True)

    # Alert thresholds (percentages)
    warning_threshold = Column(Numeric(5, 2), nullable=False, default=80.0)  # 80%
    critical_threshold = Column(Numeric(5, 2), nullable=False, default=95.0)  # 95%

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="budget_configs")
    creator = relationship("User", foreign_keys=[created_by])

    # Constraints
    __table_args__ = (
        CheckConstraint("daily_limit >= 0", name="check_daily_limit_positive"),
        CheckConstraint("weekly_limit >= 0", name="check_weekly_limit_positive"),
        CheckConstraint("monthly_limit >= 0", name="check_monthly_limit_positive"),
        CheckConstraint("yearly_limit >= 0", name="check_yearly_limit_positive"),
        CheckConstraint(
            "warning_threshold >= 0 AND warning_threshold <= 100",
            name="check_warning_threshold_range",
        ),
        CheckConstraint(
            "critical_threshold >= 0 AND critical_threshold <= 100",
            name="check_critical_threshold_range",
        ),
        Index("idx_budget_user_service", "user_id", "service_name"),
        Index("idx_budget_global", "is_global", "is_active"),
    )


class CostAlert(Base):
    """Cost-related alerts and notifications."""

    __tablename__ = "cost_alerts"

    id = Column(Integer, primary_key=True, index=True)

    # Alert identification
    alert_type = Column(
        String(50), nullable=False, index=True
    )  # budget_warning, budget_exceeded, etc.
    severity = Column(String(20), nullable=False, index=True)  # info, warning, critical

    # Scope
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    service_name = Column(String(100), nullable=True, index=True)
    model_name = Column(String(100), nullable=True, index=True)

    # Alert details
    message = Column(Text, nullable=False)
    current_usage = Column(Numeric(10, 2), nullable=False)
    budget_limit = Column(Numeric(10, 2), nullable=True)
    threshold_percentage = Column(Numeric(5, 2), nullable=True)

    # Status
    is_resolved = Column(Boolean, nullable=False, default=False)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    date_key = Column(Date, nullable=False, index=True)

    # Notification tracking
    email_sent = Column(Boolean, nullable=False, default=False)
    slack_sent = Column(Boolean, nullable=False, default=False)
    webhook_sent = Column(Boolean, nullable=False, default=False)

    # Additional context
    metadata = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

    # Constraints
    __table_args__ = (
        CheckConstraint("current_usage >= 0", name="check_current_usage_positive"),
        CheckConstraint("budget_limit >= 0", name="check_budget_limit_positive"),
        CheckConstraint(
            "threshold_percentage >= 0 AND threshold_percentage <= 100",
            name="check_threshold_range",
        ),
        Index("idx_alert_status_date", "is_resolved", "date_key"),
        Index("idx_alert_severity_type", "severity", "alert_type"),
        Index("idx_alert_user_date", "user_id", "date_key"),
    )


class CostOptimizationInsight(Base):
    """Cost optimization insights and recommendations."""

    __tablename__ = "cost_optimization_insights"

    id = Column(Integer, primary_key=True, index=True)

    # Optimization details
    strategy = Column(String(50), nullable=False, index=True)  # model_switch, caching, etc.
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)

    # Impact analysis
    potential_savings_usd = Column(Numeric(10, 2), nullable=False)
    confidence_score = Column(Numeric(3, 2), nullable=False)  # 0.00 - 1.00
    implementation_effort = Column(String(20), nullable=False)  # low, medium, high
    priority = Column(String(20), nullable=False)  # low, medium, high

    # Scope
    service_name = Column(String(100), nullable=True, index=True)
    model_name = Column(String(100), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Analysis period
    analysis_start_date = Column(Date, nullable=False)
    analysis_end_date = Column(Date, nullable=False)

    # Status
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, implemented, dismissed
    implemented_at = Column(DateTime, nullable=True)
    implemented_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    actual_savings_usd = Column(Numeric(10, 2), nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Supporting data
    supporting_data = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    implementer = relationship("User", foreign_keys=[implemented_by])
    creator = relationship("User", foreign_keys=[created_by])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "potential_savings_usd >= 0",
            name="check_potential_savings_positive",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_confidence_range",
        ),
        CheckConstraint(
            "actual_savings_usd >= 0",
            name="check_actual_savings_positive",
        ),
        Index("idx_optimization_status_priority", "status", "priority"),
        Index("idx_optimization_strategy_date", "strategy", "created_at"),
        Index("idx_optimization_service_date", "service_name", "analysis_start_date"),
    )


class CostAggregation(Base):
    """Pre-calculated cost aggregations for efficient reporting."""

    __tablename__ = "cost_aggregations"

    id = Column(Integer, primary_key=True, index=True)

    # Aggregation scope
    aggregation_type = Column(String(20), nullable=False, index=True)  # daily, weekly, monthly
    date_key = Column(Date, nullable=False, index=True)
    service_name = Column(String(100), nullable=True, index=True)
    model_name = Column(String(100), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Aggregated metrics
    total_cost = Column(Numeric(12, 6), nullable=False, default=0)
    total_requests = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_input_tokens = Column(Integer, nullable=False, default=0)
    total_output_tokens = Column(Integer, nullable=False, default=0)

    # Performance metrics
    average_response_time_ms = Column(Numeric(10, 2), nullable=True)
    average_quality_score = Column(Numeric(3, 2), nullable=True)
    cache_hit_rate = Column(Numeric(5, 2), nullable=True)  # Percentage
    error_rate = Column(Numeric(5, 2), nullable=True)  # Percentage

    # Efficiency metrics
    cost_per_request = Column(Numeric(10, 6), nullable=False, default=0)
    cost_per_token = Column(Numeric(10, 8), nullable=False, default=0)
    tokens_per_request = Column(Numeric(10, 2), nullable=True)

    # Metadata
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_final = Column(Boolean, nullable=False, default=False)  # False for partial day calculations

    # Relationships
    user = relationship("User", back_populates="cost_aggregations")

    # Constraints
    __table_args__ = (
        CheckConstraint("total_cost >= 0", name="check_total_cost_positive"),
        CheckConstraint("total_requests >= 0", name="check_total_requests_positive"),
        CheckConstraint("total_tokens >= 0", name="check_total_tokens_positive"),
        CheckConstraint(
            "cost_per_request >= 0",
            name="check_cost_per_request_positive",
        ),
        CheckConstraint("cost_per_token >= 0", name="check_cost_per_token_positive"),
        CheckConstraint(
            "cache_hit_rate >= 0 AND cache_hit_rate <= 100",
            name="check_cache_hit_rate_range",
        ),
        CheckConstraint(
            "error_rate >= 0 AND error_rate <= 100",
            name="check_error_rate_range",
        ),
        Index("idx_agg_type_date", "aggregation_type", "date_key"),
        Index("idx_agg_service_date", "service_name", "date_key"),
        Index("idx_agg_user_date", "user_id", "date_key"),
        Index(
            "idx_agg_cost_analysis",
            "service_name",
            "model_name",
            "date_key",
            "total_cost",
        ),
    )


class CostForecast(Base):
    """Cost forecasting and predictions."""

    __tablename__ = "cost_forecasts"

    id = Column(Integer, primary_key=True, index=True)

    # Forecast scope
    forecast_type = Column(String(20), nullable=False, index=True)  # daily, weekly, monthly
    service_name = Column(String(100), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Forecast period
    forecast_date = Column(Date, nullable=False, index=True)
    forecast_period_start = Column(Date, nullable=False)
    forecast_period_end = Column(Date, nullable=False)

    # Predictions
    predicted_cost = Column(Numeric(12, 6), nullable=False)
    predicted_requests = Column(Integer, nullable=True)
    predicted_tokens = Column(Integer, nullable=True)

    # Confidence intervals
    lower_bound_cost = Column(Numeric(12, 6), nullable=False)
    upper_bound_cost = Column(Numeric(12, 6), nullable=False)
    confidence_level = Column(Numeric(5, 2), nullable=False, default=95.0)  # 95%

    # Model information
    forecasting_model = Column(String(50), nullable=False)  # linear, arima, etc.
    model_parameters = Column(JSON, nullable=True)
    training_data_points = Column(Integer, nullable=False)
    model_accuracy = Column(Numeric(5, 2), nullable=True)  # Percentage

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    actual_cost = Column(Numeric(12, 6), nullable=True)  # Filled after period ends
    accuracy_score = Column(Numeric(5, 2), nullable=True)  # Actual vs predicted

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])

    # Constraints
    __table_args__ = (
        CheckConstraint("predicted_cost >= 0", name="check_predicted_cost_positive"),
        CheckConstraint("lower_bound_cost >= 0", name="check_lower_bound_positive"),
        CheckConstraint("upper_bound_cost >= 0", name="check_upper_bound_positive"),
        CheckConstraint(
            "lower_bound_cost <= predicted_cost",
            name="check_bounds_logical",
        ),
        CheckConstraint(
            "predicted_cost <= upper_bound_cost",
            name="check_bounds_logical2",
        ),
        CheckConstraint(
            "confidence_level > 0 AND confidence_level <= 100",
            name="check_confidence_level_range",
        ),
        CheckConstraint(
            "training_data_points > 0",
            name="check_training_points_positive",
        ),
        Index("idx_forecast_date_type", "forecast_date", "forecast_type"),
        Index("idx_forecast_service_date", "service_name", "forecast_date"),
        Index("idx_forecast_accuracy", "forecasting_model", "model_accuracy"),
    )


# Extend User model to include cost-related relationships
def extend_user_model() -> None:
    """Extend the User model with cost-related relationships."""
    from database.user import User

    if not hasattr(User, "ai_usage_logs"):
        User.ai_usage_logs = relationship("AIUsageLog", back_populates="user")
        User.budget_configs = relationship(
            "BudgetConfiguration",
            foreign_keys="BudgetConfiguration.user_id",
            back_populates="user",
        )
        User.cost_aggregations = relationship("CostAggregation", back_populates="user")


# Call the extension function
extend_user_model()
