"""Add cumulative_score to lead_scoring_events


Revision ID: 0717d4f5dcba
Revises: b405cc54d9a0
Create Date: 2025-08-06 06:41:46.805037

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0717d4f5dcba"
down_revision = "b405cc54d9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add cumulative_score column to lead_scoring_events table
    op.add_column(
        "lead_scoring_events",
        sa.Column("cumulative_score", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # Remove cumulative_score column from lead_scoring_events table
    op.drop_column("lead_scoring_events", "cumulative_score")
