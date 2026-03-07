"""
import logging


logger = logging.getLogger(__name__)
Asynchronous service for detecting and handling duplicate evidence items.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID
from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from config.logging_config import get_logger
from core.exceptions import BusinessLogicException, DatabaseException
from database.evidence_item import EvidenceItem

logger = get_logger(__name__)


class DuplicateDetector:
    """Detects duplicate evidence based on content and context asynchronously."""

    @staticmethod
    def _generate_content_hash(evidence_data: Dict[str, Any]) -> str:
        """Generate a SHA256 hash for the core content of the evidence."""
        try:
            content_to_hash = {
                "evidence_type": evidence_data.get("evidence_type"),
                "description": evidence_data.get("description"),
                "raw_data": evidence_data.get("raw_data"),
            }
            return hashlib.sha256(
                json.dumps(content_to_hash, sort_keys=True, default=str).encode()
            ).hexdigest()
        except (TypeError, AttributeError) as e:
            logger.warning("Could not generate content hash due to invalid data: %s" % e)
            return hashlib.sha256(
                str(datetime.now(timezone.utc)).encode(),
            ).hexdigest()

    @staticmethod
    async def is_duplicate(
        db: AsyncSession, user_id: UUID, evidence_data: Dict[str, Any], time_window_hours: int = 24
    ) -> bool:
        """Checks if an evidence item is a likely duplicate of one already stored."""
        try:
            content_hash = DuplicateDetector._generate_content_hash(evidence_data)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
            stmt = (
                select(EvidenceItem)
                .where(
                    and_(
                        EvidenceItem.user_id == user_id,
                        EvidenceItem.created_at > cutoff_time,
                        EvidenceItem.metadata["content_hash"].as_string() == content_hash,
                    )
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            return result.scalars().first() is not None
        except SQLAlchemyError as e:
            logger.error(
                "Database error while checking for duplicates for user %s: %s" % (user_id, e),
                exc_info=True,
            )
            raise DatabaseException(
                "Failed to check for duplicate evidence.",
            ) from e

    @staticmethod
    async def get_duplicate_statistics(
        db: AsyncSession, user_id: UUID, days: int = 30
    ) -> Dict[str, Any]:
        """Gets statistics about duplicate evidence detection asynchronously."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            total_stmt = select(func.count(EvidenceItem.id)).where(
                and_(EvidenceItem.user_id == user_id, EvidenceItem.created_at > cutoff_date)
            )
            total_res = await db.execute(total_stmt)
            total_items = total_res.scalar_one()
            duplicate_stmt = select(func.count(EvidenceItem.id)).where(
                and_(
                    EvidenceItem.user_id == user_id,
                    EvidenceItem.created_at > cutoff_date,
                    EvidenceItem.status == "duplicate",
                )
            )
            duplicate_res = await db.execute(duplicate_stmt)
            duplicate_items = duplicate_res.scalar_one()
            duplicate_rate = duplicate_items / total_items * 100 if total_items > 0 else 0
            return {
                "total_items": total_items,
                "duplicate_items": duplicate_items,
                "unique_items": total_items - duplicate_items,
                "duplicate_rate_percent": round(duplicate_rate, 2),
                "analysis_period_days": days,
            }
        except SQLAlchemyError as e:
            logger.error(
                "Database error getting duplicate stats for user %s: %s" % (user_id, e),
                exc_info=True,
            )
            raise DatabaseException(
                "Failed to retrieve duplicate statistics.",
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error getting duplicate stats for user %s: %s" % (user_id, e),
                exc_info=True,
            )
            raise BusinessLogicException(
                "An unexpected error occurred while calculating duplicate statistics.",
            ) from e
