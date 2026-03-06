"""Query optimization utilities for ruleIQ database."""

from sqlalchemy import select, func, and_, or_, update, delete, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import logging

# Constants
HTTP_OK = 200

CONFIDENCE_THRESHOLD = 0.8
DEFAULT_LIMIT = 100
MAX_ITEMS = 1000

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Enhanced database query optimizer with performance monitoring."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_evidence_with_relations(
        self, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get evidence items with all related data in a single query.

        Prevents N+1 queries when accessing related data.
        """
        from database.evidence_item import EvidenceItem

        query = (
            select(EvidenceItem)
            .options(
                selectinload(EvidenceItem.user),
                selectinload(EvidenceItem.business_profile),
                selectinload(EvidenceItem.framework),
            )
            .where(EvidenceItem.user_id == user_id)
            .order_by(EvidenceItem.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        evidence_items = result.scalars().all()
        return [
            {
                "id": str(item.id),
                "evidence_name": item.evidence_name,
                "description": item.description,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "business_profile": {
                    "id": str(item.business_profile.id),
                    "company_name": item.business_profile.company_name,
                    "industry": item.business_profile.industry,
                }
                if item.business_profile
                else None,
                "framework": {
                    "id": str(item.framework.id),
                    "name": item.framework.name,
                    "category": item.framework.category,
                }
                if item.framework
                else None,
            }
            for item in evidence_items
        ]

    async def get_business_profile_with_counts(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get business profile with aggregated counts in a single query.

        Prevents multiple queries for counting related items.
        """
        from database.business_profile import BusinessProfile
        from database.evidence_item import EvidenceItem
        from database.assessment_session import AssessmentSession

        query = (
            select(
                BusinessProfile,
                func.count(EvidenceItem.id).label("evidence_count"),
                func.count(AssessmentSession.id).label("assessment_count"),
            )
            .outerjoin(EvidenceItem, EvidenceItem.business_profile_id == BusinessProfile.id)
            .outerjoin(
                AssessmentSession, AssessmentSession.business_profile_id == BusinessProfile.id
            )
            .where(BusinessProfile.user_id == user_id)
            .group_by(BusinessProfile.id)
        )
        result = await self.db.execute(query)
        row = result.first()
        if not row:
            return None
        profile, evidence_count, assessment_count = row
        return {
            "id": str(profile.id),
            "company_name": profile.company_name,
            "industry": profile.industry,
            "company_size": profile.company_size,
            "evidence_count": evidence_count,
            "assessment_count": assessment_count,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
        }

    async def get_frameworks_with_usage_counts(self) -> List[Dict[str, Any]]:
        """
        Get frameworks with usage counts for analytics.

        Prevents N+1 queries when calculating framework usage.
        """
        from database.compliance_framework import ComplianceFramework
        from database.assessment_session import AssessmentSession

        query = (
            select(ComplianceFramework, func.count(AssessmentSession.id).label("usage_count"))
            .outerjoin(AssessmentSession, AssessmentSession.framework_id == ComplianceFramework.id)
            .where(ComplianceFramework.is_active)
            .group_by(ComplianceFramework.id)
            .order_by(func.count(AssessmentSession.id).desc())
        )
        result = await self.db.execute(query)
        rows = result.all()
        return [
            {
                "id": str(framework.id),
                "name": framework.name,
                "category": framework.category,
                "description": framework.description,
                "usage_count": usage_count,
                "is_active": framework.is_active,
            }
            for framework, usage_count in rows
        ]

    async def search_evidence_efficiently(
        self,
        user_id: str,
        query: str,
        status: Optional[str] = None,
        framework_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search evidence with full-text search and filters.

        Uses GIN indexes for efficient text search.
        """
        from database.evidence_item import EvidenceItem

        base_query = (
            select(EvidenceItem)
            .options(
                selectinload(EvidenceItem.business_profile), selectinload(EvidenceItem.framework)
            )
            .where(EvidenceItem.user_id == user_id)
        )
        conditions = []
        if query:
            conditions.append(
                or_(
                    EvidenceItem.evidence_name.ilike(f"%{query}%"),
                    EvidenceItem.description.ilike(f"%{query}%"),
                )
            )
        if status:
            conditions.append(EvidenceItem.status == status)
        if framework_id:
            conditions.append(EvidenceItem.framework_id == framework_id)
        if conditions:
            base_query = base_query.where(and_(*conditions))
        base_query = base_query.order_by(EvidenceItem.created_at.desc()).limit(limit)
        result = await self.db.execute(base_query)
        evidence_items = result.scalars().all()
        return [
            {
                "id": str(item.id),
                "evidence_name": item.evidence_name,
                "description": item.description,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "business_profile": {
                    "id": str(item.business_profile.id),
                    "company_name": item.business_profile.company_name,
                }
                if item.business_profile
                else None,
                "framework": {"id": str(item.framework.id), "name": item.framework.name}
                if item.framework
                else None,
            }
            for item in evidence_items
        ]

    async def analyze_query(self, query: str, params: dict = None) -> Dict[str, Any]:
        """
        Analyze query performance using EXPLAIN ANALYZE.

        Returns execution plan and performance metrics.
        """
        import time

        try:
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            start_time = time.time()
            result = await self.db.execute(text(explain_query), params or {})
            execution_time = time.time() - start_time
            plan_data = result.fetchone()[0][0]
            total_cost = plan_data.get("Plan", {}).get("Total Cost", 0)
            actual_time = plan_data.get("Plan", {}).get("Actual Total Time", 0)
            rows_returned = plan_data.get("Plan", {}).get("Actual Rows", 0)
            suggestions = []
            if actual_time > DEFAULT_LIMIT:
                suggestions.append("Query is slow - consider adding indexes")
            if "Seq Scan" in str(plan_data):
                suggestions.append("Sequential scan detected - consider adding appropriate indexes")
            if "Nested Loop" in str(plan_data) and rows_returned > MAX_ITEMS:
                suggestions.append("Nested loop with many rows - consider hash join optimization")
            return {
                "execution_time": execution_time,
                "actual_time_ms": actual_time,
                "total_cost": total_cost,
                "rows_returned": rows_returned,
                "query_plan": plan_data,
                "index_suggestions": suggestions,
                "performance_rating": "slow" if actual_time > DEFAULT_LIMIT else "fast",
            }
        except Exception as e:
            logger.error("Query analysis failed: %s" % e)
            return {
                "execution_time": 0,
                "error": str(e),
                "index_suggestions": ["Unable to analyze query"],
            }

    async def get_slow_queries(self, threshold_ms: float = 100) -> List[Dict[str, Any]]:
        """
        Get slow queries from pg_stat_statements.

        Requires pg_stat_statements extension to be enabled.
        """
        try:
            query = text(
                """
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    max_exec_time,
                    rows,
                    100.0 * shared_blks_hit /
                    nullif(shared_blks_hit + shared_blks_read, 0) as hit_percent
                FROM pg_stat_statements
                WHERE mean_exec_time > :threshold
                ORDER BY mean_exec_time DESC
                LIMIT 20
            """
            )
            result = await self.db.execute(query, {"threshold": threshold_ms})
            rows = result.fetchall()
            return [
                {
                    "query": row.query[:200] + "..." if len(row.query) > HTTP_OK else row.query,
                    "calls": row.calls,
                    "total_time_ms": float(row.total_exec_time),
                    "avg_time_ms": float(row.mean_exec_time),
                    "max_time_ms": float(row.max_exec_time),
                    "rows_avg": float(row.rows) if row.rows else 0,
                    "cache_hit_percent": float(row.hit_percent) if row.hit_percent else 0,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(
                "Could not get slow queries (pg_stat_statements may not be enabled): %s" % e
            )
            return []

    async def get_index_usage_stats(self) -> List[Dict[str, Any]]:
        """
        Get index usage statistics to identify unused indexes.
        """
        try:
            query = text(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    idx_scan,
                    pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
            """
            )
            result = await self.db.execute(query)
            rows = result.fetchall()
            return [
                {
                    "schema": row.schemaname,
                    "table": row.tablename,
                    "index": row.indexname,
                    "scans": row.idx_scan,
                    "tuples_read": row.idx_tup_read,
                    "tuples_fetched": row.idx_tup_fetch,
                    "size": row.size,
                    "usage_status": "unused" if row.idx_scan < 10 else "active",
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("Could not get index usage stats: %s" % e)
            return []

    async def optimize_connection_pool(self) -> Dict[str, Any]:
        """
        Analyze connection pool usage and suggest optimizations.
        """
        try:
            query = text(
                """
                SELECT
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                FROM pg_stat_activity
                WHERE datname = current_database()
            """
            )
            result = await self.db.execute(query)
            row = result.fetchone()
            total = row.total_connections
            active = row.active_connections
            idle = row.idle_connections
            idle_in_tx = row.idle_in_transaction
            utilization = active / max(total, 1)
            recommendations = []
            if utilization > CONFIDENCE_THRESHOLD:
                recommendations.append(
                    "High connection pool utilization - consider increasing pool size"
                )
            if idle_in_tx > total * 0.1:
                recommendations.append(
                    "Many idle-in-transaction connections - check for connection leaks"
                )
            if idle > total * 0.5:
                recommendations.append("Many idle connections - consider reducing pool size")
            return {
                "total_connections": total,
                "active_connections": active,
                "idle_connections": idle,
                "idle_in_transaction": idle_in_tx,
                "utilization_percent": utilization * 100,
                "recommendations": recommendations,
                "pool_health": "good" if 0.3 <= utilization <= 0.7 else "needs_attention",
            }
        except Exception as e:
            logger.error("Could not analyze connection pool: %s" % e)
            return {"error": str(e)}

    async def suggest_performance_improvements(self) -> List[Dict[str, Any]]:
        """
        Generate comprehensive performance improvement suggestions.
        """
        suggestions = []
        slow_queries = await self.get_slow_queries()
        if slow_queries:
            suggestions.append(
                {
                    "category": "queries",
                    "priority": "high",
                    "issue": f"Found {len(slow_queries)} slow queries",
                    "recommendation": "Review and optimize slow queries with indexes or query restructuring",
                    "impact": "Significant improvement in API response times",
                }
            )
        index_stats = await self.get_index_usage_stats()
        unused_indexes = [idx for idx in index_stats if idx["usage_status"] == "unused"]
        if unused_indexes:
            suggestions.append(
                {
                    "category": "indexes",
                    "priority": "medium",
                    "issue": f"Found {len(unused_indexes)} unused indexes",
                    "recommendation": "Consider dropping unused indexes to improve write performance",
                    "impact": "Faster INSERT/UPDATE operations, reduced storage",
                }
            )
        pool_analysis = await self.optimize_connection_pool()
        if pool_analysis.get("pool_health") == "needs_attention":
            suggestions.append(
                {
                    "category": "connections",
                    "priority": "high",
                    "issue": "Connection pool needs optimization",
                    "recommendation": "; ".join(pool_analysis.get("recommendations", [])),
                    "impact": "Better concurrency handling and resource utilization",
                }
            )
        return suggestions


class BatchQueryOptimizer:
    """Batch operations to reduce database round trips."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def batch_update_evidence_status(self, evidence_ids: List[str], new_status: str) -> int:
        """
        Update multiple evidence items in a single query.

        Returns number of updated records.
        """
        from database.evidence_item import EvidenceItem

        query = (
            update(EvidenceItem)
            .where(EvidenceItem.id.in_(evidence_ids))
            .values(status=new_status)
            .execution_options(synchronize_session=False)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount

    async def batch_delete_evidence(self, evidence_ids: List[str]) -> int:
        """
        Delete multiple evidence items in a single query.

        Returns number of deleted records.
        """
        from database.evidence_item import EvidenceItem

        query = (
            delete(EvidenceItem)
            .where(EvidenceItem.id.in_(evidence_ids))
            .execution_options(synchronize_session=False)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount

    async def get_evidence_batch_by_ids(self, evidence_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get multiple evidence items by IDs in a single query.

        Prevents N+1 queries when loading evidence by ID.
        """
        from database.evidence_item import EvidenceItem

        query = (
            select(EvidenceItem)
            .options(
                selectinload(EvidenceItem.business_profile), selectinload(EvidenceItem.framework)
            )
            .where(EvidenceItem.id.in_(evidence_ids))
        )
        result = await self.db.execute(query)
        evidence_items = result.scalars().all()
        return [
            {
                "id": str(item.id),
                "evidence_name": item.evidence_name,
                "description": item.description,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "business_profile_id": str(item.business_profile_id),
                "framework_id": str(item.framework_id),
            }
            for item in evidence_items
        ]


class QueryCache:
    """Simple query caching to reduce database load."""

    def __init__(self) -> None:
        self._cache = {}

    def get(self, key: str) -> Any:
        """Get cached result."""
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set cached result with TTL (default 5 minutes)."""
        import time

        self._cache[key] = {"value": value, "expires": time.time() + ttl}

    def is_valid(self, key: str) -> bool:
        """Check if cached result is still valid."""
        import time

        if key not in self._cache:
            return False
        cached = self._cache[key]
        return time.time() < cached["expires"]

    def invalidate(self, key: str) -> None:
        """Invalidate specific cache entry."""
        self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        import re

        keys_to_remove = [key for key in self._cache if re.search(pattern, key)]
        for key in keys_to_remove:
            self.invalidate(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


query_cache = QueryCache()
