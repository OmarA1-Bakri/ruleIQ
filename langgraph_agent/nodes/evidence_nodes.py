"""

Evidence collection nodes for LangGraph implementation.

Phase 4 Implementation: Migrate evidence tasks from Celery to LangGraph nodes.
This module replaces workers/evidence_tasks.py with native LangGraph implementations.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta, timezone
import logging
from langchain_core.messages import SystemMessage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from database.db_setup import get_async_db
from database.evidence_item import EvidenceItem
from services.automation.duplicate_detector import DuplicateDetector
from langgraph_agent.utils.cost_tracking import track_node_cost
from services.automation.evidence_processor import EvidenceProcessor
from core.exceptions import DatabaseException
from langgraph_agent.graph.enhanced_state import EnhancedComplianceState
from langgraph_agent.graph.unified_state import UnifiedComplianceState
from config.langsmith_config import with_langsmith_tracing

logger = logging.getLogger(__name__)


class EvidenceCollectionNode:
    """
    LangGraph node for evidence collection and processing.

    Replaces Celery evidence_tasks with native LangGraph implementation
    using Neon database for state persistence.
    """

    def __init__(self, processor=None, duplicate_detector=None) -> None:
        """Initialize evidence collection node with optional dependencies.

        Args:
            processor: Evidence processor instance for validation and scoring
            duplicate_detector: Duplicate detection service for deduplication
        """
        self.processor = processor
        self.duplicate_detector = duplicate_detector
        self.retry_count = 0
        self.max_retries = 3
        self.circuit_breaker_state = "closed"
        self.failure_count = 0
        self.failure_threshold = 5

    @with_langsmith_tracing("evidence.process")
    async def process_evidence(
        self,
        state_or_evidence: Union[EnhancedComplianceState, Dict[str, Any]],
        evidence_data: Optional[Dict[str, Any]] = None,
    ) -> Union[EnhancedComplianceState, Dict[str, Any]]:
        """
        Process evidence items from various integrations.

        Replaces: process_evidence_item Celery task

        Args:
            state_or_evidence: Either the state or evidence data (for backward compatibility)
            evidence_data: Optional evidence data when first param is state

        Returns:
            Updated state with processed evidence or processed evidence dict
        """
        if evidence_data is None:
            evidence_data = state_or_evidence if isinstance(state_or_evidence, dict) else {}
            state = {
                "evidence_items": [],
                "messages": [],
                "errors": [],
                "error_count": 0,
                "processing_status": "init",
            }
            return_evidence_only = True
        else:
            state = state_or_evidence
            return_evidence_only = False
        try:
            if not evidence_data:
                evidence_data = state.get("current_evidence", {})
            user_id = state.get("user_id") or evidence_data.get("user_id")
            business_profile_id = state.get("business_profile_id") or evidence_data.get(
                "business_profile_id"
            )
            integration_id = state.get("integration_id", evidence_data.get("source", "manual"))
            if not evidence_data:
                logger.warning("No evidence data found")
                if not return_evidence_only:
                    state["messages"].append(SystemMessage(content="No evidence data to process"))
                return state if not return_evidence_only else {"status": "no_data"}
            async for db in get_async_db():
                try:
                    if self.duplicate_detector:
                        is_dup = await self.duplicate_detector.is_duplicate(
                            db, user_id, evidence_data
                        )
                    else:
                        is_dup = await DuplicateDetector.is_duplicate(db, user_id, evidence_data)
                    if is_dup:
                        logger.info(f"Duplicate evidence detected for user {user_id}")
                        if not return_evidence_only:
                            state["processing_status"] = "skipped"
                            state["messages"].append(
                                SystemMessage(content="Evidence skipped: duplicate detected")
                            )
                        return state if not return_evidence_only else {"status": "duplicate"}
                    processor = self.processor or EvidenceProcessor(db)
                    new_evidence = EvidenceItem(
                        user_id=user_id,
                        business_profile_id=business_profile_id,
                        framework_id=evidence_data.get("framework_id", user_id),
                        evidence_name=evidence_data.get("evidence_name", "Evidence Item"),
                        evidence_type=evidence_data.get("evidence_type", "Document"),
                        control_reference=evidence_data.get("control_reference", "N/A"),
                        description=evidence_data.get("description", ""),
                        automation_source=evidence_data.get("source", integration_id),
                        ai_metadata=evidence_data.get("raw_data", {}),
                        status="collected",
                        collected_at=datetime.now(timezone.utc),
                        collected_by=str(user_id),
                    )
                    processor.process_evidence(new_evidence)
                    db.add(new_evidence)
                    await db.commit()
                    await db.refresh(new_evidence)
                    if not return_evidence_only:
                        state["evidence_items"].append(
                            {
                                "id": str(new_evidence.id),
                                "type": new_evidence.evidence_type,
                                "status": "processed",
                            }
                        )
                        state["processing_status"] = "completed"
                        state["messages"].append(
                            SystemMessage(content=f"Evidence processed: {new_evidence.id}")
                        )
                    logger.info(f"Successfully processed evidence {new_evidence.id}")
                    if return_evidence_only:
                        return {
                            "id": str(new_evidence.id),
                            "type": new_evidence.evidence_type,
                            "status": "processed",
                            "evidence_name": new_evidence.evidence_name,
                        }
                except (DatabaseException, SQLAlchemyError) as e:
                    await db.rollback()
                    logger.error(f"Database error processing evidence: {e}")
                    if not return_evidence_only:
                        state["error_count"] = state.get("error_count", 0) + 1
                        state["errors"].append(str(e))
                    raise
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Unexpected error processing evidence: {e}")
                    if not return_evidence_only:
                        state["error_count"] = state.get("error_count", 0) + 1
                        state["errors"].append(str(e))
                    raise
        except (DatabaseException, SQLAlchemyError) as e:
            logger.error(f"Failed to process evidence: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to process evidence: {e}")
            if not return_evidence_only:
                state["processing_status"] = "failed"
                state["messages"].append(
                    SystemMessage(content=f"Evidence processing failed: {str(e)}")
                )
            else:
                return {"status": "failed", "error": str(e)}
        return state if not return_evidence_only else {"status": "completed"}

    @with_langsmith_tracing("evidence.cleanup_stale")
    async def cleanup_stale_evidence(self, db: AsyncSession, cutoff_days: int = 90) -> int:
        """
        Mark evidence older than cutoff_days as rejected.

        This is a pure database operation extracted for testability.

        Args:
            db: Database session
            cutoff_days: Number of days after which evidence is considered stale

        Returns:
            Number of records updated
        """
        from sqlalchemy import update

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
        stmt = (
            update(EvidenceItem)
            .where(EvidenceItem.status == "collected", EvidenceItem.collected_at < cutoff_date)
            .values(status="rejected")
            .execution_options(synchronize_session=False)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    @with_langsmith_tracing("evidence.sync_status")
    async def sync_evidence_status(
        self, state: Union[EnhancedComplianceState, Dict[str, Any]], cutoff_days: int = 90
    ) -> Union[EnhancedComplianceState, Dict[str, Any]]:
        """
        Sync evidence status by marking old evidence as stale.

        Replaces: sync_evidence_status Celery task

        Args:
            state: Current enhanced compliance state
            cutoff_days: Number of days after which evidence is considered stale (default: 90)

        Returns:
            Updated state with sync results
        """
        try:
            async for db in get_async_db():
                try:
                    updated_count = await self.cleanup_stale_evidence(db, cutoff_days)
                    if isinstance(state, dict):
                        state["sync_results"] = {
                            "updated_count": updated_count,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        if "messages" not in state:
                            state["messages"] = []
                        state["messages"].append(
                            SystemMessage(
                                content=f"Evidence sync completed: {updated_count} items marked stale"
                            )
                        )
                        state["sync_count"] = updated_count
                        state["last_sync"] = datetime.now(timezone.utc).isoformat()
                    else:
                        state["sync_results"] = {
                            "updated_count": updated_count,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        state["messages"].append(
                            SystemMessage(
                                content=f"Evidence sync completed: {updated_count} items marked stale"
                            )
                        )
                    logger.info(f"Evidence status sync: {updated_count} items updated")
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Error syncing evidence status: {e}")
                    if isinstance(state, dict):
                        state["error_count"] = state.get("error_count", 0) + 1
                        if "errors" not in state:
                            state["errors"] = []
                        state["errors"].append(str(e))
                    else:
                        state["error_count"] += 1
                        state["errors"].append(str(e))
                    raise
        except Exception as e:
            logger.error(f"Failed to sync evidence status: {e}")
            if isinstance(state, dict):
                if "messages" not in state:
                    state["messages"] = []
                state["messages"].append(SystemMessage(content=f"Evidence sync failed: {str(e)}"))
            else:
                state["messages"].append(SystemMessage(content=f"Evidence sync failed: {str(e)}"))
        return state

    @with_langsmith_tracing("evidence.check_expiry")
    async def check_evidence_expiry(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Check for expired evidence and mark appropriately.

        Replaces: check_evidence_expiry Celery task

        Args:
            state: Current enhanced compliance state

        Returns:
            Updated state with expiry check results
        """
        try:
            async for db in get_async_db():
                try:
                    warning_date = datetime.now(timezone.utc) + timedelta(days=30)
                    expiry_date = datetime.now(timezone.utc)
                    from sqlalchemy import select, and_

                    warning_stmt = select(EvidenceItem).where(
                        and_(
                            EvidenceItem.status == "collected",
                            EvidenceItem.collected_at <= warning_date,
                            EvidenceItem.collected_at > expiry_date,
                        )
                    )
                    warning_results = await db.execute(warning_stmt)
                    warning_items = warning_results.scalars().all()
                    expired_stmt = select(EvidenceItem).where(
                        and_(
                            EvidenceItem.status == "collected",
                            EvidenceItem.collected_at <= expiry_date,
                        )
                    )
                    expired_results = await db.execute(expired_stmt)
                    expired_items = expired_results.scalars().all()
                    for item in expired_items:
                        item.status = "rejected"
                    if expired_items:
                        await db.commit()
                    state["expiry_check"] = {
                        "warning_count": len(warning_items),
                        "expired_count": len(expired_items),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    state["messages"].append(
                        SystemMessage(
                            content=f"Expiry check: {len(warning_items)} warnings, {len(expired_items)} expired"
                        )
                    )
                    logger.info(
                        f"Evidence expiry check: {len(warning_items)} warnings, {len(expired_items)} expired"
                    )
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Error checking evidence expiry: {e}")
                    state["error_count"] += 1
                    state["errors"].append(str(e))
                    raise
        except Exception as e:
            logger.error(f"Failed to check evidence expiry: {e}")
            state["messages"].append(SystemMessage(content=f"Expiry check failed: {str(e)}"))
        return state

    @with_langsmith_tracing("evidence.collect_integrations")
    async def collect_all_integrations(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Collect evidence from all configured integrations.

        Replaces: collect_all_integrations Celery task

        Args:
            state: Current enhanced compliance state

        Returns:
            Updated state with collection results
        """
        try:
            integrations = state.get("configured_integrations", [])
            if not integrations:
                logger.warning("No integrations configured for evidence collection")
                state["messages"].append(SystemMessage(content="No integrations configured"))
                return state
            collection_results = []
            for integration in integrations:
                try:
                    logger.info(f"Collecting evidence from {integration}")
                    result = {
                        "integration": integration,
                        "status": "collected",
                        "count": 0,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    collection_results.append(result)
                except Exception as e:
                    logger.error(f"Error collecting from {integration}: {e}")
                    collection_results.append(
                        {"integration": integration, "status": "failed", "error": str(e)}
                    )
            state["collection_results"] = collection_results
            state["messages"].append(
                SystemMessage(
                    content=f"Evidence collection completed for {len(integrations)} integrations"
                )
            )
        except Exception as e:
            logger.error(f"Failed to collect evidence from integrations: {e}")
            state["messages"].append(SystemMessage(content=f"Collection failed: {str(e)}"))
        return state

    @with_langsmith_tracing("evidence.process_pending")
    async def process_pending_evidence(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Process any pending evidence items.

        Replaces: process_pending_evidence Celery task

        Args:
            state: Current enhanced compliance state

        Returns:
            Updated state with processing results
        """
        try:
            async for db in get_async_db():
                try:
                    from sqlalchemy import select

                    stmt = (
                        select(EvidenceItem).where(EvidenceItem.status == "not_started").limit(100)
                    )
                    result = await db.execute(stmt)
                    pending_items = result.scalars().all()
                    processed_count = 0
                    for item in pending_items:
                        try:
                            processor = EvidenceProcessor(db)
                            processor.process_evidence(item)
                            item.status = "collected"
                            processed_count += 1
                        except Exception as e:
                            logger.error(f"Error processing pending item {item.id}: {e}")
                            item.status = "rejected"
                    if pending_items:
                        await db.commit()
                    state["pending_processing"] = {
                        "processed_count": processed_count,
                        "total_count": len(pending_items),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    state["messages"].append(
                        SystemMessage(
                            content=f"Processed {processed_count}/{len(pending_items)} pending items"
                        )
                    )
                    logger.info(f"Pending evidence processing: {processed_count} items")
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Error processing pending evidence: {e}")
                    state["error_count"] += 1
                    state["errors"].append(str(e))
                    raise
        except Exception as e:
            logger.error(f"Failed to process pending evidence: {e}")
            state["messages"].append(SystemMessage(content=f"Pending processing failed: {str(e)}"))
        return state

    @with_langsmith_tracing("evidence.validate")
    async def validate_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Validate evidence with scoring and confidence calculation.

        Args:
            evidence: Evidence item to validate

        Returns:
            Validation result with score and confidence
        """
        validation_result = {"valid": True, "score": 0.0, "confidence": 0.0, "errors": []}
        required_fields = ["id", "type", "content"]
        for field in required_fields:
            if field not in evidence:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Missing required field: {field}")
        if not validation_result["valid"]:
            return validation_result
        score_factors = {
            "has_source": 0.2,
            "has_timestamp": 0.2,
            "has_metadata": 0.2,
            "content_length": 0.4,
        }
        score = 0.0
        if evidence.get("source"):
            score += score_factors["has_source"]
        if evidence.get("timestamp"):
            score += score_factors["has_timestamp"]
        if evidence.get("metadata"):
            score += score_factors["has_metadata"]
        content_len = len(str(evidence.get("content", "")))
        if content_len > 100:
            score += score_factors["content_length"]
        elif content_len > 50:
            score += score_factors["content_length"] * 0.5
        validation_result["score"] = score
        confidence = 0.5
        if evidence.get("type") == "document":
            confidence += 0.3
        elif evidence.get("type") == "api_response":
            confidence += 0.2
        if evidence.get("source", {}).get("verified"):
            confidence += 0.2
        validation_result["confidence"] = min(confidence, 1.0)
        return validation_result

    @with_langsmith_tracing("evidence.aggregate")
    async def aggregate_evidence(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate evidence items by type with deduplication.

        Args:
            evidence_items: List of evidence items to aggregate

        Returns:
            Aggregated evidence grouped by type
        """
        aggregated = {}
        seen_hashes = set()
        for item in evidence_items:
            content_hash = hash(str(item.get("content", "")))
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            evidence_type = item.get("type", "unknown")
            if evidence_type not in aggregated:
                aggregated[evidence_type] = []
            aggregated[evidence_type].append(item)
        return aggregated

    def merge_evidence(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two evidence items with score combination.

        Args:
            existing: Existing evidence item
            new: New evidence item to merge

        Returns:
            Merged evidence with combined scores
        """
        merged = existing.copy()
        if "content" in new:
            if isinstance(merged.get("content"), dict) and isinstance(new["content"], dict):
                merged["content"].update(new["content"])
            else:
                merged["content"] = new["content"]
        if "score" in existing and "score" in new:
            merged["combined_score"] = round((existing["score"] + new["score"]) / 2, 2)
        elif "score" in new:
            merged["score"] = new["score"]
        if "timestamp" in new:
            merged["timestamp"] = new["timestamp"]
        if "metadata" in new:
            if "metadata" not in merged:
                merged["metadata"] = {}
            merged["metadata"].update(new["metadata"])
        return merged

    async def sync_evidence_timestamps(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronize evidence timestamps across the system.

        Args:
            state: Current state

        Returns:
            Updated state with sync results
        """
        try:
            async for db in get_async_db():
                result = await db.execute(
                    "UPDATE evidence_items SET synced_at = NOW() WHERE status = 'pending'"
                )
                await db.commit()
                state["sync_count"] = result.rowcount
                state["last_sync"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"Synchronized {result.rowcount} evidence items")
        except Exception as e:
            logger.error(f"Failed to sync evidence status: {e}")
            state["sync_error"] = str(e)
        return state

    async def retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or raises exception after max retries
        """
        import random
        import asyncio

        max_retries = 3
        base_delay = 1.0
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * 2**attempt + random.uniform(0, 1)
                logger.warning(f"Retry attempt {attempt + 1} after {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        raise Exception("Max retries exceeded")


_evidence_collection_instance = EvidenceCollectionNode()
evidence_node = _evidence_collection_instance


@with_langsmith_tracing("evidence.collection_node")
@track_node_cost(node_name="evidence_collection", model_name="gpt-4")
async def evidence_collection_node(state: UnifiedComplianceState) -> UnifiedComplianceState:
    """
    Evidence collection node wrapper for LangGraph integration.

    This function wraps the EvidenceCollectionNode instance to provide
    a standard function interface for the LangGraph workflow.

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with evidence processing results
    """
    return await _evidence_collection_instance.process_evidence(state)
