"""Sync AIQuestionBank schema with model definition

Revision ID: aca23a693098
Revises: 7a680f130f6a
Create Date: 2025-08-15 13:48:38.195545

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "aca23a693098"
down_revision = "7a680f130f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_question_bank",
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("correct_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("context_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("compliance_weight", sa.Numeric(precision=4, scale=3), nullable=False),
    )
    op.add_column("ai_question_bank", sa.Column("usage_frequency", sa.Integer(), nullable=False))
    op.add_column(
        "ai_question_bank", sa.Column("ai_model_version", sa.String(length=50), nullable=True)
    )
    op.add_column("ai_question_bank", sa.Column("generation_prompt", sa.Text(), nullable=True))
    op.add_column("ai_question_bank", sa.Column("generation_cost", sa.Integer(), nullable=False))
    op.add_column("ai_question_bank", sa.Column("is_validated", sa.Boolean(), nullable=False))
    op.add_column(
        "ai_question_bank",
        sa.Column("validation_score", sa.Numeric(precision=3, scale=2), nullable=True),
    )
    op.add_column("ai_question_bank", sa.Column("human_reviewed", sa.Boolean(), nullable=False))
    op.add_column("ai_question_bank", sa.Column("effective_date", sa.DateTime(), nullable=False))
    op.add_column("ai_question_bank", sa.Column("expiry_date", sa.DateTime(), nullable=True))
    op.alter_column(
        "ai_question_bank",
        "category",
        existing_type=sa.VARCHAR(length=50),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_question_bank",
        "question_type",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_question_bank",
        "difficulty_level",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Integer(),
        nullable=False,
        postgresql_using="CASE WHEN difficulty_level ~ '^\\d+$' THEN difficulty_level::integer ELSE 5 END",
    )
    op.alter_column("ai_question_bank", "is_active", existing_type=sa.BOOLEAN(), nullable=False)
    op.alter_column(
        "ai_question_bank",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "ai_question_bank",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.drop_index(op.f("ix_ai_questions_active"), table_name="ai_question_bank")
    op.drop_index(op.f("ix_ai_questions_category"), table_name="ai_question_bank")
    op.drop_index(op.f("ix_ai_questions_industry"), table_name="ai_question_bank")
    op.drop_constraint(op.f("uq_ai_question_bank_question_id"), "ai_question_bank", type_="unique")
    op.create_index(
        op.f("ix_ai_question_bank_category"), "ai_question_bank", ["category"], unique=False
    )
    op.drop_column("ai_question_bank", "question_id")
    op.drop_column("ai_question_bank", "ai_prompt_template")
    op.drop_column("ai_question_bank", "skip_rate")
    op.drop_column("ai_question_bank", "usage_count")
    op.drop_column("ai_question_bank", "industry_specific")
    op.drop_column("ai_question_bank", "completion_rate")
    op.drop_column("ai_question_bank", "follow_up_logic")
    op.drop_column("ai_question_bank", "compliance_impact")
    op.drop_column("ai_question_bank", "regulatory_framework")
    op.drop_column("ai_question_bank", "version")
    op.drop_column("ai_question_bank", "personalization_rules")
    op.drop_column("ai_question_bank", "target_industries")
    op.drop_column("ai_question_bank", "company_size_relevance")
    op.drop_column("ai_question_bank", "answer_options")
    op.drop_column("ai_question_bank", "risk_weight")
    op.drop_column("ai_question_bank", "subcategory")
    op.drop_column("ai_question_bank", "average_answer_time")
    op.drop_column("ai_question_bank", "deprecated_at")
    op.drop_column("ai_question_bank", "scoring_rules")
    op.drop_column("ai_question_bank", "question_context")
    op.drop_column("ai_question_bank", "expected_answer_type")
    op.alter_column(
        "assessment_leads",
        "consent_date",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "assessment_leads",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "assessment_leads",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "assessment_leads",
        "last_activity_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.drop_index(op.f("ix_assessment_leads_score"), table_name="assessment_leads")
    op.drop_index(op.f("ix_assessment_leads_status"), table_name="assessment_leads")
    op.drop_constraint(op.f("uq_assessment_leads_email"), "assessment_leads", type_="unique")
    op.drop_index(op.f("ix_assessment_leads_email"), table_name="assessment_leads")
    op.create_index(op.f("ix_assessment_leads_email"), "assessment_leads", ["email"], unique=True)
    op.alter_column(
        "freemium_assessment_sessions",
        "session_token",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "expires_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "status",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "progress_percentage",
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "questions_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "ai_responses",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "personalization_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "compliance_score",
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "risk_assessment",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "recommendations",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "gaps_identified",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "results_viewed_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "conversion_cta_clicked_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "converted_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "device_type",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "browser",
        existing_type=sa.VARCHAR(length=50),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "session_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "completed_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )
    op.drop_index(
        op.f("ix_freemium_sessions_created_at"), table_name="freemium_assessment_sessions"
    )
    op.drop_index(op.f("ix_freemium_sessions_expires"), table_name="freemium_assessment_sessions")
    op.drop_index(op.f("ix_freemium_sessions_lead_id"), table_name="freemium_assessment_sessions")
    op.drop_index(op.f("ix_freemium_sessions_status"), table_name="freemium_assessment_sessions")
    op.drop_index(op.f("idx_provider_status"), table_name="integrations")
    op.drop_index(op.f("idx_user_enabled"), table_name="integrations")
    op.drop_column("integrations", "status")
    op.drop_column("integrations", "last_sync_status")
    op.drop_column("integrations", "last_sync_at")
    op.drop_column("integrations", "is_enabled")
    op.alter_column(
        "lead_scoring_events",
        "event_type",
        existing_type=sa.VARCHAR(length=50),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
    op.alter_column(
        "lead_scoring_events", "score_impact", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "lead_scoring_events",
        "user_agent",
        existing_type=sa.TEXT(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "lead_scoring_events",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.drop_index(op.f("ix_lead_events_category_action"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_events_conversion"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_events_lead_id"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_events_session_id"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_events_timestamp"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_events_type"), table_name="lead_scoring_events")
    op.create_index(
        op.f("ix_lead_scoring_events_created_at"),
        "lead_scoring_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_scoring_events_event_category"),
        "lead_scoring_events",
        ["event_category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_scoring_events_event_type"),
        "lead_scoring_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_scoring_events_lead_id"), "lead_scoring_events", ["lead_id"], unique=False
    )
    op.drop_constraint(
        op.f("fk_lead_scoring_events_session_id_freemium_assessment_sessions"),
        "lead_scoring_events",
        type_="foreignkey",
    )
    op.drop_column("lead_scoring_events", "browser")
    op.drop_column("lead_scoring_events", "page_view_count")
    op.drop_column("lead_scoring_events", "conversion_type")
    op.drop_column("lead_scoring_events", "custom_properties")
    op.drop_column("lead_scoring_events", "session_duration")
    op.drop_column("lead_scoring_events", "viewport_size")
    op.drop_column("lead_scoring_events", "score_reason")
    op.drop_column("lead_scoring_events", "page_title")
    op.drop_column("lead_scoring_events", "campaign_id")
    op.drop_column("lead_scoring_events", "device_type")
    op.drop_column("lead_scoring_events", "conversion_value")
    op.drop_column("lead_scoring_events", "event_value")
    op.drop_column("lead_scoring_events", "is_conversion_event")
    op.drop_column("lead_scoring_events", "os")
    op.drop_column("lead_scoring_events", "ab_test_variant")
    op.drop_column("lead_scoring_events", "previous_event_id")
    op.drop_column("lead_scoring_events", "screen_resolution")
    op.drop_column("lead_scoring_events", "event_timestamp")
    op.drop_column("lead_scoring_events", "engagement_type")


def downgrade() -> None:
    op.add_column(
        "lead_scoring_events",
        sa.Column("engagement_type", sa.VARCHAR(length=30), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column(
            "event_timestamp",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("screen_resolution", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("previous_event_id", sa.UUID(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("ab_test_variant", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("os", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("is_conversion_event", sa.BOOLEAN(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column(
            "event_value", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column(
            "conversion_value",
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("device_type", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("campaign_id", sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("page_title", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("score_reason", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("viewport_size", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("session_duration", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column(
            "custom_properties",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("conversion_type", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("page_view_count", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("browser", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_lead_scoring_events_session_id_freemium_assessment_sessions"),
        "lead_scoring_events",
        "freemium_assessment_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(op.f("ix_lead_scoring_events_lead_id"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_scoring_events_event_type"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_scoring_events_event_category"), table_name="lead_scoring_events")
    op.drop_index(op.f("ix_lead_scoring_events_created_at"), table_name="lead_scoring_events")
    op.create_index(
        op.f("ix_lead_events_type"), "lead_scoring_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_lead_events_timestamp"), "lead_scoring_events", ["event_timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_lead_events_session_id"), "lead_scoring_events", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_lead_events_lead_id"), "lead_scoring_events", ["lead_id"], unique=False
    )
    op.create_index(
        op.f("ix_lead_events_conversion"),
        "lead_scoring_events",
        ["is_conversion_event"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_events_category_action"),
        "lead_scoring_events",
        ["event_category", "event_action"],
        unique=False,
    )
    op.alter_column(
        "lead_scoring_events",
        "created_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "lead_scoring_events",
        "user_agent",
        existing_type=sa.String(length=500),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column(
        "lead_scoring_events", "score_impact", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "lead_scoring_events",
        "event_type",
        existing_type=sa.String(length=100),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.add_column(
        "integrations",
        sa.Column(
            "is_enabled",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "integrations",
        sa.Column("last_sync_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "integrations",
        sa.Column("last_sync_status", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.add_column(
        "integrations",
        sa.Column(
            "status",
            sa.VARCHAR(length=50),
            server_default=sa.text("'not_configured'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.create_index(
        op.f("idx_user_enabled"), "integrations", ["user_id", "is_enabled"], unique=False
    )
    op.create_index(
        op.f("idx_provider_status"), "integrations", ["provider", "status"], unique=False
    )
    op.create_index(
        op.f("ix_freemium_sessions_status"),
        "freemium_assessment_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_freemium_sessions_lead_id"),
        "freemium_assessment_sessions",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_freemium_sessions_expires"),
        "freemium_assessment_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_freemium_sessions_created_at"),
        "freemium_assessment_sessions",
        ["created_at"],
        unique=False,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "completed_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "created_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "session_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "browser",
        existing_type=sa.String(length=100),
        type_=sa.VARCHAR(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "device_type",
        existing_type=sa.String(length=50),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "converted_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "conversion_cta_clicked_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "results_viewed_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "gaps_identified",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "recommendations",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "risk_assessment",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "compliance_score",
        existing_type=sa.Integer(),
        type_=sa.DOUBLE_PRECISION(precision=53),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "personalization_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "ai_responses",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "questions_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "progress_percentage",
        existing_type=sa.Integer(),
        type_=sa.DOUBLE_PRECISION(precision=53),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "status",
        existing_type=sa.String(length=50),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "expires_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "freemium_assessment_sessions",
        "session_token",
        existing_type=sa.String(length=64),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
    op.drop_index(op.f("ix_assessment_leads_email"), table_name="assessment_leads")
    op.create_index(op.f("ix_assessment_leads_email"), "assessment_leads", ["email"], unique=False)
    op.create_unique_constraint(
        op.f("uq_assessment_leads_email"),
        "assessment_leads",
        ["email"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(
        op.f("ix_assessment_leads_status"), "assessment_leads", ["lead_status"], unique=False
    )
    op.create_index(
        op.f("ix_assessment_leads_score"), "assessment_leads", ["lead_score"], unique=False
    )
    op.alter_column(
        "assessment_leads",
        "last_activity_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "assessment_leads",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "assessment_leads",
        "created_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "assessment_leads",
        "consent_date",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "expected_answer_type", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("question_context", sa.TEXT(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "scoring_rules",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "deprecated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "average_answer_time",
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("subcategory", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "risk_weight", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "answer_options",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "company_size_relevance",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "target_industries",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "personalization_rules",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank", sa.Column("version", sa.INTEGER(), autoincrement=False, nullable=True)
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "regulatory_framework", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("compliance_impact", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "follow_up_logic",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "completion_rate", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("industry_specific", sa.BOOLEAN(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("usage_count", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column(
            "skip_rate", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("ai_prompt_template", sa.TEXT(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "ai_question_bank",
        sa.Column("question_id", sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    )
    op.drop_index(op.f("ix_ai_question_bank_category"), table_name="ai_question_bank")
    op.create_unique_constraint(
        op.f("uq_ai_question_bank_question_id"),
        "ai_question_bank",
        ["question_id"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(
        op.f("ix_ai_questions_industry"), "ai_question_bank", ["industry_specific"], unique=False
    )
    op.create_index(
        op.f("ix_ai_questions_category"), "ai_question_bank", ["category"], unique=False
    )
    op.create_index(op.f("ix_ai_questions_active"), "ai_question_bank", ["is_active"], unique=False)
    op.alter_column(
        "ai_question_bank",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "ai_question_bank",
        "created_at",
        existing_type=sa.DateTime(),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column("ai_question_bank", "is_active", existing_type=sa.BOOLEAN(), nullable=True)
    op.alter_column(
        "ai_question_bank",
        "difficulty_level",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=20),
        nullable=True,
    )
    op.alter_column(
        "ai_question_bank",
        "question_type",
        existing_type=sa.String(length=50),
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_question_bank",
        "category",
        existing_type=sa.String(length=100),
        type_=sa.VARCHAR(length=50),
        existing_nullable=False,
    )
    op.drop_column("ai_question_bank", "expiry_date")
    op.drop_column("ai_question_bank", "effective_date")
    op.drop_column("ai_question_bank", "human_reviewed")
    op.drop_column("ai_question_bank", "validation_score")
    op.drop_column("ai_question_bank", "is_validated")
    op.drop_column("ai_question_bank", "generation_cost")
    op.drop_column("ai_question_bank", "generation_prompt")
    op.drop_column("ai_question_bank", "ai_model_version")
    op.drop_column("ai_question_bank", "usage_frequency")
    op.drop_column("ai_question_bank", "compliance_weight")
    op.drop_column("ai_question_bank", "context_tags")
    op.drop_column("ai_question_bank", "correct_answers")
    op.drop_column("ai_question_bank", "options")
