"""Add API key management tables


Revision ID: add_api_key_tables
Revises: latest
Create Date: 2025-01-01

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = "add_api_key_tables"
down_revision = None  # Update this with the latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create API key management tables."""

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("key_id", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("organization_id", sa.String(100), nullable=False, index=True),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("key_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("allowed_ips", postgresql.ARRAY(sa.String), default=[]),
        sa.Column("allowed_origins", postgresql.ARRAY(sa.String), default=[]),
        sa.Column("rate_limit", sa.Integer(), nullable=False, default=100),
        sa.Column("rate_limit_window", sa.Integer(), nullable=False, default=60),
        sa.Column("metadata", postgresql.JSON(), default={}),
    )

    # Create indexes for api_keys
    op.create_index("idx_api_keys_org_status", "api_keys", ["organization_id", "status"])
    op.create_index("idx_api_keys_expires", "api_keys", ["expires_at"])

    # Create api_key_scopes table
    op.create_table(
        "api_key_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "key_id",
            sa.String(50),
            sa.ForeignKey("api_keys.key_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column("granted_by", sa.String(100), nullable=True),
    )

    # Create unique constraint for key_id + scope combination
    op.create_index(
        "idx_api_key_scopes_key_scope",
        "api_key_scopes",
        ["key_id", "scope"],
        unique=True,
    )

    # Create api_key_usage table
    op.create_table(
        "api_key_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "key_id",
            sa.String(50),
            sa.ForeignKey("api_keys.key_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            nullable=False,
            default=sa.func.now(),
            index=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("endpoint", sa.String(255), nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), default={}),
    )

    # Create indexes for api_key_usage
    op.create_index("idx_api_key_usage_key_timestamp", "api_key_usage", ["key_id", "timestamp"])
    op.create_index("idx_api_key_usage_timestamp", "api_key_usage", ["timestamp"])


def downgrade() -> None:
    """Drop API key management tables."""

    # Drop tables in reverse order due to foreign key constraints
    op.drop_table("api_key_usage")
    op.drop_table("api_key_scopes")
    op.drop_table("api_keys")
