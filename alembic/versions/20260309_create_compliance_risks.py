"""create compliance_risks table

Revision ID: 20260309_risk_register
Revises:
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260309_risk_register"
down_revision = None  # TODO: set to latest existing migration revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_risks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "business_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_profiles.id"),
            nullable=False,
        ),
        sa.Column(
            "framework_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_frameworks.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("likelihood", sa.String(), nullable=False, server_default="medium"),
        sa.Column("impact", sa.String(), nullable=False, server_default="medium"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("mitigation_plan", sa.Text(), nullable=True),
        sa.Column(
            "mitigation_status",
            sa.String(),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("control_reference", sa.String(), nullable=True),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("ai_metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for common queries
    op.create_index(
        "ix_compliance_risks_user_id",
        "compliance_risks",
        ["user_id"],
    )
    op.create_index(
        "ix_compliance_risks_framework_id",
        "compliance_risks",
        ["framework_id"],
    )
    op.create_index(
        "ix_compliance_risks_status",
        "compliance_risks",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_risks_status", table_name="compliance_risks")
    op.drop_index("ix_compliance_risks_framework_id", table_name="compliance_risks")
    op.drop_index("ix_compliance_risks_user_id", table_name="compliance_risks")
    op.drop_table("compliance_risks")
