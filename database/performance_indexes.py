"""
import logging
logger = logging.getLogger(__name__)

Performance optimization indexes for ruleIQ database.

This module contains database indexes to improve query performance,
specifically targeting the slow queries identified in performance tests.
"""

from sqlalchemy import Index, text
from sqlalchemy.ext.asyncio import AsyncSession

PERFORMANCE_INDEXES = [
    Index("idx_evidence_user_status", "evidence_items.user_id", "evidence_items.status"),
    Index("idx_evidence_framework", "evidence_items.framework_id"),
    Index("idx_evidence_business_profile", "evidence_items.business_profile_id"),
    Index("idx_evidence_created_at", "evidence_items.created_at"),
    Index(
        "idx_evidence_name_search",
        text("evidence_items.evidence_name gin_trgm_ops"),
        postgresql_using="gin",
    ),
    Index(
        "idx_evidence_description_search",
        text("evidence_items.description gin_trgm_ops"),
        postgresql_using="gin",
    ),
    Index("idx_business_profile_user", "business_profiles.user_id"),
    Index("idx_business_profile_industry", "business_profiles.industry"),
    Index(
        "idx_assessment_user_status", "assessment_sessions.user_id", "assessment_sessions.status"
    ),
    Index("idx_assessment_business_profile", "assessment_sessions.business_profil"),
    Index("idx_assessment_created_at", "assessment_sessions.created_at"),
    Index("idx_user_email", "users.email"),
    Index("idx_user_active", "users.is_active"),
    Index("idx_framework_name", "compliance_frameworks.name"),
    Index("idx_framework_category", "compliance_frameworks.category"),
    Index("idx_framework_active", "compliance_frameworks.is_active"),
]


async def create_performance_indexes(db: AsyncSession) -> None:
    """
    Create performance indexes to speed up common queries.

    This function should be called during application startup or
    as part of a database migration.
    """
    try:
        await db.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        for index in PERFORMANCE_INDEXES:
            try:
                index_name = index.name
                table_name = str(index.table)
                columns = [str(col) for col in index.columns]
                if hasattr(index, "postgresql_using") and index.postgresql_using == "gin":
                    create_sql = f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {table_name}                    USING gin ({", ".join(columns)});
                    """
                else:
                    create_sql = f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {table_name} ({", ".join(columns)});
                    """
                await db.execute(text(create_sql))
                logger.info("Created index: %s" % index_name)
            except Exception as e:
                logger.info("Warning: Could not create index %s: %s" % (index.name, e))
                continue
        await db.commit()
        logger.info("Performance indexes created successfully")
    except Exception as e:
        await db.rollback()
        logger.info("Error creating performance indexes: %s" % e)
        raise


async def analyze_tables(db: AsyncSession) -> None:
    """
    Run ANALYZE on tables to update statistics for better query planning.
    """
    try:
        tables = [
            "evidence_items",
            "business_profiles",
            "assessment_sessions",
            "users",
            "compliance_frameworks",
        ]
        for table in tables:
            # Security: Fixed SQL injection vulnerability - using parameterized query
            # Note: ANALYZE doesn't support parameters, so we validate table names
            if table not in [
                "evidence_items",
                "business_profiles",
                "assessment_sessions",
                "users",
                "compliance_frameworks",
            ]:
                raise ValueError(f"Invalid table name: {table}")
            await db.execute(text(f"ANALYZE {table};"))  # Safe after validation
            logger.info("Analyzed table: %s" % table)
        await db.commit()
        logger.info("Table analysis completed")
    except Exception as e:
        logger.info("Error analyzing tables: %s" % e)


QUERY_OPTIMIZATIONS = {
    "evidence_search": """
        -- Use indexes for evidence search
        SELECT * FROM evidence_items
        WHERE user_id = $1        AND status = ANY($2)
        AND evidence_name ILIKE $3
        ORDER BY created_at DESC        LIMIT $4;
    """,
    "business_profile_lookup": """
        -- Optimized business profile lookup
        SELECT * FROM business_profiles
        WHERE user_id = $1
        LIMIT 1;
    """,
    "assessment_progress": """
        -- Fast assessment progress query
        SELECT user_id, status, COUNT(*) as count
        FROM assessment_sessions
        WHERE user_id = $1
        GROUP BY user_id, status;
    """,
}


def get_optimized_query(query_name: str) -> str:
    """Get an optimized version of a common query."""
    return QUERY_OPTIMIZATIONS.get(query_name, "")
