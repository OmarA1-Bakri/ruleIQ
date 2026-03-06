"""Add missing columns to lead_scoring_events


Revision ID: 7a680f130f6a
Revises: 0717d4f5dcba
Create Date: 2025-08-06 06:46:33.669772

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7a680f130f6a"
down_revision = "0717d4f5dcba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to lead_scoring_events table to match the model
    op.add_column(
        "lead_scoring_events",
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "lead_scoring_events",
        sa.Column("session_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("lead_scoring_events", sa.Column("event_duration", sa.Integer(), nullable=True))
    op.add_column(
        "lead_scoring_events",
        sa.Column("ip_address", sa.String(length=45), nullable=True),
    )


def downgrade() -> None:
    # Remove the added columns
    op.drop_column("lead_scoring_events", "ip_address")
    op.drop_column("lead_scoring_events", "event_duration")
    op.drop_column("lead_scoring_events", "session_context")
    op.drop_column("lead_scoring_events", "event_metadata")
