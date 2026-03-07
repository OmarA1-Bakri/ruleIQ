"""Database migration to add performance indexes for ruleIQ."""

from alembic import op

# revision identifiers, used by Alembic.
revision = "010_add_performance_indexes"
down_revision = "009_fix_assessment_sessions_truncation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes to improve query performance."""

    # Enable pg_trgm extension for text search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Evidence table indexes
    op.create_index("idx_evidence_user_status", "evidence_items", ["user_id", "status"])

    op.create_index("idx_evidence_framework", "evidence_items", ["framework_id"])

    op.create_index("idx_evidence_business_profile", "evidence_items", ["business_profile_id"])

    op.create_index("idx_evidence_created_at", "evidence_items", ["created_at"])

    # GIN indexes for text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_evidence_name_search
        ON evidence_items USING gin (evidence_name gin_trgm_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_evidence_description_search
        ON evidence_items USING gin (description gin_trgm_ops);
    """)

    # Business profile indexes
    op.create_index("idx_business_profile_user", "business_profiles", ["user_id"])

    op.create_index("idx_business_profile_industry", "business_profiles", ["industry"])

    # Assessment session indexes
    op.create_index("idx_assessment_user_status", "assessment_sessions", ["user_id", "status"])

    op.create_index(
        "idx_assessment_business_profile",
        "assessment_sessions",
        ["business_profile_id"],
    )

    op.create_index("idx_assessment_created_at", "assessment_sessions", ["created_at"])

    # User table indexes
    op.create_index("idx_user_email", "users", ["email"])

    op.create_index("idx_user_active", "users", ["is_active"])

    # Framework indexes
    op.create_index("idx_framework_name", "compliance_frameworks", ["name"])

    op.create_index("idx_framework_category", "compliance_frameworks", ["category"])

    op.create_index("idx_framework_active", "compliance_frameworks", ["is_active"])

    # Chat conversation indexes
    op.create_index("idx_chat_user_created", "chat_conversations", ["user_id", "created_at"])

    # Integration configuration indexes
    op.create_index(
        "idx_integration_user_type",
        "integration_configurations",
        ["user_id", "integration_type"],
    )

    # Evidence metadata indexes
    op.create_index("idx_evidence_metadata_evidence", "evidence_metadata", ["evidence_item_id"])

    # Implementation plan indexes
    op.create_index(
        "idx_implementation_assessment",
        "implementation_plans",
        ["assessment_session_id"],
    )

    # Generated policy indexes
    op.create_index("idx_policy_business_profile", "generated_policies", ["business_profile_id"])

    # Update table statistics
    op.execute("ANALYZE evidence_items;")
    op.execute("ANALYZE business_profiles;")
    op.execute("ANALYZE assessment_sessions;")
    op.execute("ANALYZE users;")
    op.execute("ANALYZE compliance_frameworks;")
    op.execute("ANALYZE chat_conversations;")
    op.execute("ANALYZE integration_configurations;")
    op.execute("ANALYZE evidence_metadata;")
    op.execute("ANALYZE implementation_plans;")
    op.execute("ANALYZE generated_policies;")


def downgrade() -> None:
    """Remove performance indexes."""

    # Evidence table indexes
    op.drop_index("idx_evidence_user_status", table_name="evidence_items")
    op.drop_index("idx_evidence_framework", table_name="evidence_items")
    op.drop_index("idx_evidence_business_profile", table_name="evidence_items")
    op.drop_index("idx_evidence_created_at", table_name="evidence_items")
    op.execute("DROP INDEX IF EXISTS idx_evidence_name_search;")
    op.execute("DROP INDEX IF EXISTS idx_evidence_description_search;")

    # Business profile indexes
    op.drop_index("idx_business_profile_user", table_name="business_profiles")
    op.drop_index("idx_business_profile_industry", table_name="business_profiles")

    # Assessment session indexes
    op.drop_index("idx_assessment_user_status", table_name="assessment_sessions")
    op.drop_index("idx_assessment_business_profile", table_name="assessment_sessions")
    op.drop_index("idx_assessment_created_at", table_name="assessment_sessions")

    # User table indexes
    op.drop_index("idx_user_email", table_name="users")
    op.drop_index("idx_user_active", table_name="users")

    # Framework indexes
    op.drop_index("idx_framework_name", table_name="compliance_frameworks")
    op.drop_index("idx_framework_category", table_name="compliance_frameworks")
    op.drop_index("idx_framework_active", table_name="compliance_frameworks")

    # Chat conversation indexes
    op.drop_index("idx_chat_user_created", table_name="chat_conversations")

    # Integration configuration indexes
    op.drop_index("idx_integration_user_type", table_name="integration_configurations")

    # Evidence metadata indexes
    op.drop_index("idx_evidence_metadata_evidence", table_name="evidence_metadata")

    # Implementation plan indexes
    op.drop_index("idx_implementation_assessment", table_name="implementation_plans")

    # Generated policy indexes
    op.drop_index("idx_policy_business_profile", table_name="generated_policies")
