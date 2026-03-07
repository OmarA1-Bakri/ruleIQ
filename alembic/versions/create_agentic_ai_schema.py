"""Create agentic AI database schema

Revision ID: agentic_ai_schema_v1
Revises: 802adb6d1be8
Create Date: 2025-01-10

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "agentic_ai_schema_v1"
down_revision = "802adb6d1be8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension if not exists
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create schema version tracking table
    op.create_table(
        "schema_versions",
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("version_number", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "applied_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("applied_by", sa.String(100), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("version_id"),
        sa.UniqueConstraint("version_number"),
    )

    # Insert initial version
    op.execute(
        text("""
        INSERT INTO schema_versions (version_number, description)
        VALUES ('1.0.0', 'Initial agentic AI schema implementation')
    """)
    )

    # Create agents table
    op.create_table(
        "agents",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("persona_type", sa.String(50), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=text("1"), nullable=False),
        sa.PrimaryKeyConstraint("agent_id"),
        sa.CheckConstraint(
            "persona_type IN ('developer', 'qa', 'architect', 'security', 'compliance', 'documentation', 'orchestrator')",
            name="check_valid_persona_type",
        ),
    )

    # Create agent_sessions table
    op.create_table(
        "agent_sessions",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trust_level", sa.Integer(), server_default=text("0"), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("session_state", sa.String(20), server_default=text("'active'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version", sa.Integer(), server_default=text("1"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.agent_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.CheckConstraint("trust_level >= 0 AND trust_level <= 4", name="check_trust_level_range"),
        sa.CheckConstraint(
            "session_state IN ('active', 'paused', 'completed', 'terminated')",
            name="check_session_state",
        ),
    )

    # Create agent_decisions table
    op.create_table(
        "agent_decisions",
        sa.Column(
            "decision_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_type", sa.String(50), nullable=False),
        sa.Column("input_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("action_taken", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.DECIMAL(3, 2), nullable=True),
        sa.Column("user_feedback", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1", name="check_confidence_score_range"
        ),
        sa.CheckConstraint(
            "user_feedback IN ('approved', 'rejected', 'modified', 'pending')",
            name="check_user_feedback",
        ),
        sa.CheckConstraint(
            "decision_type IN ('code_generation', 'review', 'test', 'refactor', 'design', 'documentation', 'security_check')",
            name="check_decision_type",
        ),
    )

    # Create trust_metrics table with enhanced validation
    op.create_table(
        "trust_metrics",
        sa.Column(
            "metric_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("metric_value", sa.DECIMAL(5, 2), nullable=False),
        sa.Column("measurement_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("metric_id"),
        sa.CheckConstraint(
            "metric_type IN ('accuracy', 'autonomy', 'complexity', 'reliability', 'efficiency')",
            name="check_metric_type",
        ),
        sa.CheckConstraint(
            """
            (metric_type = 'accuracy' AND metric_value >= 0 AND metric_value <= 100) OR
            (metric_type = 'autonomy' AND metric_value >= 0 AND metric_value <= 100) OR
            (metric_type = 'complexity' AND metric_value >= 0 AND metric_value <= 10) OR
            (metric_type = 'reliability' AND metric_value >= 0 AND metric_value <= 100) OR
            (metric_type = 'efficiency' AND metric_value >= 0 AND metric_value <= 100)
        """,
            name="check_metric_value_ranges",
        ),
    )

    # Create agent_knowledge table with vector embeddings
    op.create_table(
        "agent_knowledge",
        sa.Column(
            "knowledge_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_type", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),  # Vector embedding
        sa.Column("usage_count", sa.Integer(), server_default=text("0"), nullable=False),
        sa.Column("success_rate", sa.DECIMAL(3, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.agent_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("knowledge_id"),
        sa.CheckConstraint(
            "knowledge_type IN ('pattern', 'solution', 'preference', 'constraint', 'example')",
            name="check_knowledge_type",
        ),
        sa.CheckConstraint(
            "domain IN ('frontend', 'backend', 'testing', 'security', 'infrastructure', 'documentation')",
            name="check_domain",
        ),
        sa.CheckConstraint(
            "success_rate >= 0 AND success_rate <= 1", name="check_success_rate_range"
        ),
    )

    # Create conversation_history table with partitioning support
    op.create_table(
        "conversation_history",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(30), nullable=True),
        sa.Column("parent_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_message_id"], ["conversation_history.message_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id"),
        sa.CheckConstraint("role IN ('user', 'agent', 'system', 'tool')", name="check_role"),
        sa.CheckConstraint(
            "message_type IN ('text', 'code', 'command', 'file', 'error', 'warning', 'info')",
            name="check_message_type",
        ),
    )

    # Create agent_audit_log table
    op.create_table(
        "agent_audit_log",
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.agent_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.session_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("audit_id"),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')", name="check_risk_level"
        ),
    )

    # Create indexes for optimal performance
    op.create_index("idx_agent_sessions_agent_id", "agent_sessions", ["agent_id"])
    op.create_index("idx_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index(
        "idx_agent_sessions_state",
        "agent_sessions",
        ["session_state"],
        postgresql_where=text("session_state = 'active'"),
    )

    op.create_index("idx_agent_decisions_session_id", "agent_decisions", ["session_id"])
    op.create_index("idx_agent_decisions_type", "agent_decisions", ["decision_type"])
    op.create_index("idx_agent_decisions_created_at", "agent_decisions", ["created_at"])

    op.create_index("idx_trust_metrics_session_id", "trust_metrics", ["session_id"])
    op.create_index("idx_trust_metrics_type", "trust_metrics", ["metric_type"])

    op.create_index("idx_agent_knowledge_agent_id", "agent_knowledge", ["agent_id"])
    op.create_index("idx_agent_knowledge_domain", "agent_knowledge", ["domain"])
    op.create_index("idx_agent_knowledge_type", "agent_knowledge", ["knowledge_type"])

    op.create_index(
        "idx_conversation_history_session_id_created",
        "conversation_history",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_conversation_history_parent", "conversation_history", ["parent_message_id"]
    )

    op.create_index("idx_agent_audit_log_agent_id", "agent_audit_log", ["agent_id"])
    op.create_index("idx_agent_audit_log_risk_level", "agent_audit_log", ["risk_level"])
    op.create_index("idx_agent_audit_log_timestamp", "agent_audit_log", ["timestamp"])

    # Create composite indexes for common queries
    op.create_index("idx_agents_active_persona", "agents", ["is_active", "persona_type"])
    op.create_index(
        "idx_agent_sessions_agent_created", "agent_sessions", ["agent_id", "started_at"]
    )
    op.create_index(
        "idx_agent_decisions_session_type", "agent_decisions", ["session_id", "decision_type"]
    )

    # Create GIN indexes for JSONB fields
    op.execute(text("CREATE INDEX idx_agents_capabilities_gin ON agents USING GIN (capabilities)"))
    op.execute(
        text("CREATE INDEX idx_agent_sessions_context_gin ON agent_sessions USING GIN (context)")
    )
    op.execute(
        text(
            "CREATE INDEX idx_agent_decisions_input_gin ON agent_decisions USING GIN (input_context)"
        )
    )
    op.execute(
        text("CREATE INDEX idx_agent_knowledge_content_gin ON agent_knowledge USING GIN (content)")
    )

    # Create trigger for updated_at column
    op.execute(
        text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    )

    op.execute(
        text("""
        CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    )


def downgrade() -> None:
    # Drop triggers
    op.execute(text("DROP TRIGGER IF EXISTS update_agents_updated_at ON agents"))
    op.execute(text("DROP FUNCTION IF EXISTS update_updated_at_column()"))

    # Drop indexes
    op.drop_index("idx_agent_knowledge_content_gin", "agent_knowledge")
    op.drop_index("idx_agent_decisions_input_gin", "agent_decisions")
    op.drop_index("idx_agent_sessions_context_gin", "agent_sessions")
    op.drop_index("idx_agents_capabilities_gin", "agents")

    op.drop_index("idx_agent_decisions_session_type", "agent_decisions")
    op.drop_index("idx_agent_sessions_agent_created", "agent_sessions")
    op.drop_index("idx_agents_active_persona", "agents")

    op.drop_index("idx_agent_audit_log_timestamp", "agent_audit_log")
    op.drop_index("idx_agent_audit_log_risk_level", "agent_audit_log")
    op.drop_index("idx_agent_audit_log_agent_id", "agent_audit_log")

    op.drop_index("idx_conversation_history_parent", "conversation_history")
    op.drop_index("idx_conversation_history_session_id_created", "conversation_history")

    op.drop_index("idx_agent_knowledge_type", "agent_knowledge")
    op.drop_index("idx_agent_knowledge_domain", "agent_knowledge")
    op.drop_index("idx_agent_knowledge_agent_id", "agent_knowledge")

    op.drop_index("idx_trust_metrics_type", "trust_metrics")
    op.drop_index("idx_trust_metrics_session_id", "trust_metrics")

    op.drop_index("idx_agent_decisions_created_at", "agent_decisions")
    op.drop_index("idx_agent_decisions_type", "agent_decisions")
    op.drop_index("idx_agent_decisions_session_id", "agent_decisions")

    op.drop_index("idx_agent_sessions_state", "agent_sessions")
    op.drop_index("idx_agent_sessions_user_id", "agent_sessions")
    op.drop_index("idx_agent_sessions_agent_id", "agent_sessions")

    # Drop tables in reverse order
    op.drop_table("agent_audit_log")
    op.drop_table("conversation_history")
    op.drop_table("agent_knowledge")
    op.drop_table("trust_metrics")
    op.drop_table("agent_decisions")
    op.drop_table("agent_sessions")
    op.drop_table("agents")
    op.drop_table("schema_versions")
