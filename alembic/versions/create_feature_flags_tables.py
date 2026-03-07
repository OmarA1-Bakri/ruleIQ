"""Create feature flags tables

Revision ID: create_feature_flags_tables
Revises:
Create Date: 2025-01-09

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = "create_feature_flags_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create feature flag related tables"""

    # Create feature_flags table
    op.create_table(
        "feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), default=False, nullable=False),
        sa.Column("status", sa.String(50), default="disabled"),
        sa.Column("percentage", sa.Float(), default=0.0, nullable=False),
        sa.Column("whitelist", postgresql.JSONB(), default=list),
        sa.Column("blacklist", postgresql.JSONB(), default=list),
        sa.Column("environment_overrides", postgresql.JSONB(), default=dict),
        sa.Column("environments", postgresql.JSONB(), default=list),
        sa.Column("tags", postgresql.JSONB(), default=list),
        sa.Column("metadata", postgresql.JSONB(), default=dict),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
    )

    # Create index on name for fast lookups
    op.create_index("ix_feature_flags_name", "feature_flags", ["name"])

    # Create feature_flag_audits table
    op.create_table(
        "feature_flag_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "feature_flag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_flags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("changes", postgresql.JSONB(), default=dict),
        sa.Column("previous_state", postgresql.JSONB(), default=dict),
        sa.Column("new_state", postgresql.JSONB(), default=dict),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("user_role", sa.String(100), nullable=True),
        sa.Column("environment", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ticket_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create index on feature_flag_id for audit trail queries
    op.create_index("ix_feature_flag_audits_flag_id", "feature_flag_audits", ["feature_flag_id"])
    op.create_index("ix_feature_flag_audits_created_at", "feature_flag_audits", ["created_at"])

    # Create feature_flag_evaluations table
    op.create_table(
        "feature_flag_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "feature_flag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_flags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("evaluated_value", sa.Boolean(), nullable=False),
        sa.Column("evaluation_reason", sa.String(255), nullable=True),
        sa.Column("evaluation_time_ms", sa.Float(), nullable=True),
        sa.Column("cached", sa.Boolean(), default=False),
        sa.Column("cache_hit", sa.Boolean(), default=False),
        sa.Column("context", postgresql.JSONB(), default=dict),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for analytics queries
    op.create_index(
        "ix_feature_flag_evaluations_flag_id", "feature_flag_evaluations", ["feature_flag_id"]
    )
    op.create_index("ix_feature_flag_evaluations_user_id", "feature_flag_evaluations", ["user_id"])
    op.create_index(
        "ix_feature_flag_evaluations_evaluated_at", "feature_flag_evaluations", ["evaluated_at"]
    )

    # Create feature_flag_groups table
    op.create_table(
        "feature_flag_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("priority", sa.Integer(), default=0),
        sa.Column("feature_flag_names", postgresql.JSONB(), default=list),
        sa.Column("tags", postgresql.JSONB(), default=list),
        sa.Column("metadata", postgresql.JSONB(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
    )

    # Create index on group name
    op.create_index("ix_feature_flag_groups_name", "feature_flag_groups", ["name"])

    # Insert default feature flags
    op.execute("""
        INSERT INTO feature_flags (id, name, description, enabled, status, percentage, environments, created_by, updated_by)
        VALUES
        (gen_random_uuid(), 'AUTH_MIDDLEWARE_V2_ENABLED', 'Enhanced JWT authentication middleware', true, 'enabled', 100, '["development", "testing", "staging", "production"]'::jsonb, 'system', 'system'),
        (gen_random_uuid(), 'RATE_LIMITING_ENABLED', 'API rate limiting feature', true, 'enabled', 100, '["production", "staging"]'::jsonb, 'system', 'system'),
        (gen_random_uuid(), 'AI_COST_OPTIMIZATION', 'AI cost optimization features', true, 'percentage_rollout', 50, '["production"]'::jsonb, 'system', 'system'),
        (gen_random_uuid(), 'ADVANCED_ANALYTICS', 'Advanced analytics dashboard', false, 'disabled', 0, '["development"]'::jsonb, 'system', 'system')
    """)


def downgrade() -> None:
    """Drop feature flag related tables"""

    # Drop indexes
    op.drop_index("ix_feature_flag_groups_name", "feature_flag_groups")
    op.drop_index("ix_feature_flag_evaluations_evaluated_at", "feature_flag_evaluations")
    op.drop_index("ix_feature_flag_evaluations_user_id", "feature_flag_evaluations")
    op.drop_index("ix_feature_flag_evaluations_flag_id", "feature_flag_evaluations")
    op.drop_index("ix_feature_flag_audits_created_at", "feature_flag_audits")
    op.drop_index("ix_feature_flag_audits_flag_id", "feature_flag_audits")
    op.drop_index("ix_feature_flags_name", "feature_flags")

    # Drop tables in reverse order (due to foreign keys)
    op.drop_table("feature_flag_groups")
    op.drop_table("feature_flag_evaluations")
    op.drop_table("feature_flag_audits")
    op.drop_table("feature_flags")
