"""Create freemium tables for AI Assessment Strategy


Revision ID: freemium_001
Revises:
Create Date: 2025-08-05

This migration creates the necessary tables for the AI Assessment Freemium Strategy:
- AssessmentLead: Email capture and UTM tracking
- FreemiumAssessmentSession: AI assessment sessions
- AIQuestionBank: Dynamic questions for assessments
- LeadScoringEvent: Behavioral tracking and conversion analytics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = "freemium_001"
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AssessmentLead table for email capture and UTM tracking
    op.create_table(
        "assessment_leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("company_size", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        # UTM and tracking parameters
        sa.Column("utm_source", sa.String(100), nullable=True),
        sa.Column("utm_medium", sa.String(100), nullable=True),
        sa.Column("utm_campaign", sa.String(200), nullable=True),
        sa.Column("utm_term", sa.String(200), nullable=True),
        sa.Column("utm_content", sa.String(200), nullable=True),
        sa.Column("referrer_url", sa.Text, nullable=True),
        sa.Column("landing_page", sa.String(500), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),  # IPv6 compatible
        # Lead scoring and status
        sa.Column("lead_score", sa.Integer, default=0),
        sa.Column("lead_status", sa.String(20), default="new"),  # new, qualified, converted, lost
        sa.Column("conversion_probability", sa.Float, nullable=True),
        sa.Column("engagement_score", sa.Integer, default=0),
        # Newsletter and marketing consent
        sa.Column("newsletter_subscribed", sa.Boolean, default=True),
        sa.Column("marketing_consent", sa.Boolean, default=False),
        sa.Column("consent_date", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.UniqueConstraint("email", name="uq_assessment_leads_email"),
    )

    # FreemiumAssessmentSession table for AI assessment sessions
    op.create_table(
        "freemium_assessment_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_token", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Assessment progress
        # started, in_progress, completed, abandoned
        sa.Column("status", sa.String(20), default="started"),
        sa.Column("current_question_id", sa.String(100), nullable=True),
        sa.Column("total_questions", sa.Integer, default=0),
        sa.Column("questions_answered", sa.Integer, default=0),
        sa.Column("progress_percentage", sa.Float, default=0.0),
        # AI-generated content
        # general, specific_industry, etc.
        sa.Column("assessment_type", sa.String(50), default="general"),
        sa.Column("questions_data", sa.JSON, nullable=True),  # Serialized questions and answers
        sa.Column("ai_responses", sa.JSON, nullable=True),  # AI-generated responses
        sa.Column("personalization_data", sa.JSON, nullable=True),  # User preferences for AI
        # Results and analysis
        sa.Column("compliance_score", sa.Float, nullable=True),
        sa.Column("risk_assessment", sa.JSON, nullable=True),  # AI risk analysis
        sa.Column("recommendations", sa.JSON, nullable=True),  # AI recommendations
        sa.Column("gaps_identified", sa.JSON, nullable=True),  # Compliance gaps
        sa.Column("results_summary", sa.Text, nullable=True),
        # Conversion tracking
        sa.Column("results_viewed", sa.Boolean, default=False),
        sa.Column("results_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conversion_cta_clicked", sa.Boolean, default=False),
        sa.Column("conversion_cta_clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_to_paid", sa.Boolean, default=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        # Session metadata
        sa.Column("time_spent_seconds", sa.Integer, default=0),
        sa.Column("device_type", sa.String(20), nullable=True),  # desktop, mobile, tablet
        sa.Column("browser", sa.String(50), nullable=True),
        sa.Column("session_data", sa.JSON, nullable=True),  # Additional session info
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),  # Session expiration
        # Indexes for performance
        sa.Index("ix_freemium_sessions_status", "status"),
        sa.Index("ix_freemium_sessions_created_at", "created_at"),
        sa.Index("ix_freemium_sessions_lead_id", "lead_id"),
    )

    # AIQuestionBank table for dynamic questions
    op.create_table(
        "ai_question_bank",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("question_id", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False),  # gdpr, security, data_handling, etc.
        sa.Column("subcategory", sa.String(50), nullable=True),
        # multiple_choice, yes_no, text, scale
        sa.Column("question_type", sa.String(20), nullable=False),
        # Question content
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("question_context", sa.Text, nullable=True),  # Additional context for AI
        sa.Column("answer_options", sa.JSON, nullable=True),  # For multiple choice questions
        # string, integer, boolean, json
        sa.Column("expected_answer_type", sa.String(20), nullable=True),
        # AI generation parameters
        sa.Column("ai_prompt_template", sa.Text, nullable=True),
        # Rules for personalizing questions
        sa.Column("personalization_rules", sa.JSON, nullable=True),
        sa.Column("follow_up_logic", sa.JSON, nullable=True),  # Logic for follow-up questions
        # Scoring and weighting
        sa.Column("risk_weight", sa.Float, default=1.0),  # Weight in risk calculation
        # low, medium, high, critical
        sa.Column("compliance_impact", sa.String(20), default="medium"),
        sa.Column("scoring_rules", sa.JSON, nullable=True),  # How to score different answers
        # Usage and performance tracking
        sa.Column("usage_count", sa.Integer, default=0),
        sa.Column("completion_rate", sa.Float, default=0.0),
        sa.Column("average_answer_time", sa.Float, nullable=True),  # Average time to answer
        sa.Column("skip_rate", sa.Float, default=0.0),
        # Question metadata
        sa.Column("difficulty_level", sa.String(20), default="medium"),  # easy, medium, hard
        sa.Column("industry_specific", sa.Boolean, default=False),
        sa.Column("target_industries", sa.JSON, nullable=True),  # Specific industries
        sa.Column("company_size_relevance", sa.JSON, nullable=True),  # Company sizes
        sa.Column("regulatory_framework", sa.String(50), nullable=True),  # GDPR, CCPA, etc.
        # Status and versioning
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        # Indexes
        sa.Index("ix_ai_questions_category", "category"),
        sa.Index("ix_ai_questions_active", "is_active"),
        sa.Index("ix_ai_questions_industry", "industry_specific"),
    )

    # LeadScoringEvent table for behavioral tracking
    op.create_table(
        "lead_scoring_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("freemium_assessment_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # Event details
        # page_view, button_click, form_submit, etc.
        sa.Column("event_type", sa.String(50), nullable=False),
        # engagement, conversion, assessment
        sa.Column("event_category", sa.String(50), nullable=False),
        sa.Column("event_action", sa.String(100), nullable=False),  # specific action taken
        sa.Column("event_label", sa.String(200), nullable=True),  # additional context
        sa.Column("event_value", sa.Float, nullable=True),  # numeric value if applicable
        # Page/context information
        sa.Column("page_url", sa.String(500), nullable=True),
        sa.Column("page_title", sa.String(200), nullable=True),
        sa.Column("referrer_url", sa.String(500), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        # Scoring impact
        sa.Column("score_impact", sa.Integer, default=0),  # Points added/subtracted
        sa.Column("score_reason", sa.String(200), nullable=True),  # Why this score was applied
        sa.Column("engagement_type", sa.String(30), nullable=True),  # positive, negative, neutral
        # Conversion tracking
        sa.Column("is_conversion_event", sa.Boolean, default=False),
        # email_signup, assessment_complete, etc.
        sa.Column("conversion_type", sa.String(50), nullable=True),
        sa.Column("conversion_value", sa.Float, nullable=True),  # Monetary or score value
        # Session context
        sa.Column("session_duration", sa.Integer, nullable=True),  # Duration up to this event
        sa.Column("page_view_count", sa.Integer, nullable=True),  # Number of pages viewed
        # Link to previous event
        sa.Column("previous_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Device and environment
        sa.Column("device_type", sa.String(20), nullable=True),
        sa.Column("browser", sa.String(50), nullable=True),
        sa.Column("os", sa.String(50), nullable=True),
        sa.Column("screen_resolution", sa.String(20), nullable=True),
        sa.Column("viewport_size", sa.String(20), nullable=True),
        # Additional metadata
        sa.Column("custom_properties", sa.JSON, nullable=True),  # Flexible additional data
        sa.Column("ab_test_variant", sa.String(50), nullable=True),  # A/B testing variant
        sa.Column("campaign_id", sa.String(100), nullable=True),  # Marketing campaign ID
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "event_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Indexes for analytics queries
        sa.Index("ix_lead_events_lead_id", "lead_id"),
        sa.Index("ix_lead_events_session_id", "session_id"),
        sa.Index("ix_lead_events_type", "event_type"),
        sa.Index("ix_lead_events_timestamp", "event_timestamp"),
        sa.Index("ix_lead_events_conversion", "is_conversion_event"),
        sa.Index("ix_lead_events_category_action", "event_category", "event_action"),
    )

    # Create additional indexes for performance
    op.create_index("ix_assessment_leads_score", "assessment_leads", ["lead_score"])
    op.create_index("ix_assessment_leads_status", "assessment_leads", ["lead_status"])
    # Remove function-based index causing PostgreSQL immutable function error
    op.create_index("ix_freemium_sessions_expires", "freemium_assessment_sessions", ["expires_at"])
    # Remove non-existent column index


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table("lead_scoring_events")
    op.drop_table("ai_question_bank")
    op.drop_table("freemium_assessment_sessions")
    op.drop_table("assessment_leads")
