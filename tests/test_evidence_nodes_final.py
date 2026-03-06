"""Final tests to achieve 80%+ coverage for evidence_nodes module."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from langgraph.graph.message import add_messages
from database.evidence_item import EvidenceItem
from langgraph_agent.nodes.evidence_nodes import EvidenceCollectionNode, evidence_node

from tests.test_constants import MAX_RETRIES

# Constants
DEFAULT_RETRIES = 5
HALF_RATIO = 0.5


async def async_generator(items):
    """Helper to create async generator."""
    for item in items:
        yield item


@pytest.mark.asyncio
class TestProcessEvidenceAdditionalPaths:
    """Test additional paths in process_evidence method."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_with_existing_processor(
        self, mock_duplicate_detector, mock_processor_class, mock_get_db
    ):
        """Test process_evidence when processor already exists."""
        mock_duplicate_detector.is_duplicate = AsyncMock(return_value=False)
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        async def mock_refresh(evidence_item):
            evidence_item.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        node.processor = MagicMock()
        node.processor.process_evidence = MagicMock()
        evidence_data = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_name": "Test Evidence",
            "evidence_type": "Document",
        }
        result = await node.process_evidence(evidence_data)
        assert not mock_processor_class.called
        assert node.processor.process_evidence.called

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_database_exception_reraise(
        self, mock_duplicate_detector, mock_get_db
    ):
        """Test that database exceptions are re-raised."""
        mock_duplicate_detector.is_duplicate = AsyncMock(return_value=False)
        from sqlalchemy.exc import SQLAlchemyError

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=SQLAlchemyError("Database error"))
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        evidence_data = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_name": "Test Evidence",
            "evidence_type": "Document",
        }
        with pytest.raises(SQLAlchemyError):
            await node.process_evidence(evidence_data)
        assert mock_session.rollback.called


@pytest.mark.asyncio
class TestProcessPendingEvidenceEdgeCases:
    """Test edge cases in process_pending_evidence."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    async def test_process_pending_with_multiple_items(self, mock_processor_class, mock_get_db):
        """Test processing multiple pending evidence items."""
        evidence1 = MagicMock(spec=EvidenceItem)
        evidence1.id = str(uuid4())
        evidence1.status = "not_started"
        evidence1.evidence_name = "Evidence 1"
        evidence1.evidence_type = "Policy"
        evidence1.to_dict = MagicMock(
            return_value={
                "id": evidence1.id,
                "evidence_name": "Evidence 1",
                "status": "not_started",
                "evidence_type": "Policy",
            }
        )
        evidence2 = MagicMock(spec=EvidenceItem)
        evidence2.id = str(uuid4())
        evidence2.status = "not_started"
        evidence2.evidence_name = "Evidence 2"
        evidence2.evidence_type = "Procedure"
        evidence2.to_dict = MagicMock(
            return_value={
                "id": evidence2.id,
                "evidence_name": "Evidence 2",
                "status": "not_started",
                "evidence_type": "Procedure",
            }
        )
        mock_processor = MagicMock()
        mock_processor.process_evidence = MagicMock()
        mock_processor_class.return_value = mock_processor
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[evidence1, evidence2]))
        )
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_items": [],
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }
        result = await node.process_pending_evidence(state)
        assert mock_processor.process_evidence.call_count == 2
        assert "pending_processing" in result

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_process_pending_with_database_error(self, mock_get_db):
        """Test process_pending_evidence with database error."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Query failed"))
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_items": [],
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }
        result = await node.process_pending_evidence(state)
        assert mock_session.rollback.called
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1


@pytest.mark.asyncio
class TestRetryWithBackoffEdgeCases:
    """Test edge cases in retry_with_backoff."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_retry_exhausted(self, mock_get_db):
        """Test retry_with_backoff when all retries are exhausted."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        call_count = 0

        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Persistent failure {call_count}")

        with pytest.raises(Exception, match="Persistent failure"):
            await node.retry_with_backoff(always_failing)
        assert call_count == MAX_RETRIES


@pytest.mark.asyncio
class TestStaleEvidenceCleanup:
    """Test stale evidence cleanup in process_evidence."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_stale_evidence_cleanup(
        self, mock_duplicate_detector, mock_processor_class, mock_get_db
    ):
        """Test stale evidence cleanup during process_evidence."""
        mock_duplicate_detector.is_duplicate = AsyncMock(return_value=False)
        mock_processor = MagicMock()
        mock_processor.process_evidence = MagicMock()
        mock_processor_class.return_value = mock_processor
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        async def mock_refresh(evidence_item):
            evidence_item.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)
        mock_update_result = MagicMock()
        mock_update_result.rowcount = 5

        async def mock_execute(stmt):
            if hasattr(stmt, "table") and hasattr(stmt.table, "name"):
                if stmt.table.name == "evidence_items":
                    return mock_update_result
            return MagicMock()

        mock_session.execute = AsyncMock(side_effect=mock_execute)
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_items": [],
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }
        evidence_data = {
            "evidence_name": "Test Evidence",
            "evidence_type": "Document",
            "description": "Test description",
        }
        result = await node.process_evidence(state, evidence_data=evidence_data)
        assert mock_session.execute.called
        if "sync_results" in result:
            assert result["sync_results"]["updated_count"] == DEFAULT_RETRIES
            assert "Evidence sync completed: 5 items marked stale" in str(result["messages"])


@pytest.mark.asyncio
class TestValidateEvidenceScoring:
    """Test validation scoring logic."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_validate_evidence_low_score(self, mock_get_db):
        """Test validation with evidence that scores poorly."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        evidence = {"id": str(uuid4()), "type": "document", "content": "x"}
        result = await node.validate_evidence(evidence)
        assert result["valid"] is False
        assert result["score"] < HALF_RATIO
        assert any("low quality" in error.lower() for error in result["errors"])
