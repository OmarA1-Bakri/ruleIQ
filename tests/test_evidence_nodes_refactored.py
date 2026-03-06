"""Tests for refactored evidence_nodes methods to achieve 85%+ coverage."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4
import pytest
from sqlalchemy import select, text, update, Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage
from database.evidence_item import EvidenceItem
from langgraph_agent.nodes.evidence_nodes import EvidenceCollectionNode, evidence_node

# Constants
DEFAULT_RETRIES = 5


async def async_generator(items):
    """Helper to create async generator."""
    for item in items:
        yield item


@pytest.mark.asyncio
class TestCleanupStaleEvidence:
    """Test the newly extracted cleanup_stale_evidence method."""

    async def test_cleanup_stale_evidence_default_cutoff(self):
        """Test cleanup with default 90-day cutoff."""
        node = EvidenceCollectionNode()
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock(spec=Result)
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        updated_count = await node.cleanup_stale_evidence(mock_session)
        assert updated_count == DEFAULT_RETRIES
        assert mock_session.execute.called
        assert mock_session.commit.called
        call_args = mock_session.execute.call_args[0][0]
        assert hasattr(call_args, "table")
        assert call_args.table.name == "evidence_items"

    async def test_cleanup_stale_evidence_custom_cutoff(self):
        """Test cleanup with custom cutoff days."""
        node = EvidenceCollectionNode()
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock(spec=Result)
        mock_result.rowcount = 10
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        updated_count = await node.cleanup_stale_evidence(mock_session, cutoff_days=30)
        assert updated_count == 10
        assert mock_session.execute.called
        assert mock_session.commit.called

    async def test_cleanup_stale_evidence_no_stale_items(self):
        """Test cleanup when no items are stale."""
        node = EvidenceCollectionNode()
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock(spec=Result)
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        updated_count = await node.cleanup_stale_evidence(mock_session)
        assert updated_count == 0
        assert mock_session.execute.called
        assert mock_session.commit.called

    async def test_cleanup_stale_evidence_database_error(self):
        """Test cleanup when database error occurs."""
        node = EvidenceCollectionNode()
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database connection lost"))
        with pytest.raises(SQLAlchemyError, match="Database connection lost"):
            await node.cleanup_stale_evidence(mock_session)
        assert not mock_session.commit.called


@pytest.mark.asyncio
class TestSyncEvidenceStatusRefactored:
    """Test the refactored sync_evidence_status method."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_sync_with_custom_cutoff(self, mock_get_db):
        """Test sync_evidence_status with custom cutoff days."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        with patch.object(node, "cleanup_stale_evidence", new=AsyncMock(return_value=7)):
            state = {
                "user_id": str(uuid4()),
                "business_profile_id": str(uuid4()),
                "evidence_status": {},
                "messages": [],
                "errors": [],
                "error_count": 0,
            }
            result = await node.sync_evidence_status(state, cutoff_days=60)
            node.cleanup_stale_evidence.assert_called_once_with(mock_session, 60)
            assert result["sync_count"] == 7
            assert "last_sync" in result
            assert len(result["messages"]) == 1
            assert "7 items marked stale" in result["messages"][0].content

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_sync_with_cleanup_error(self, mock_get_db):
        """Test sync_evidence_status when cleanup raises an error."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        with patch.object(
            node,
            "cleanup_stale_evidence",
            new=AsyncMock(side_effect=SQLAlchemyError("Update failed")),
        ):
            state = {
                "user_id": str(uuid4()),
                "business_profile_id": str(uuid4()),
                "evidence_status": {},
                "messages": [],
                "errors": [],
                "error_count": 0,
            }
            result = await node.sync_evidence_status(state)
            assert mock_session.rollback.called
            assert result["error_count"] == 1
            assert len(result["errors"]) == 1
            assert "Update failed" in result["errors"][0]
            assert len(result["messages"]) == 1
            assert "Evidence sync failed" in result["messages"][0].content

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_sync_with_typed_dict_state(self, mock_get_db):
        """Test sync_evidence_status with TypedDict state (not plain dict)."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        with patch.object(node, "cleanup_stale_evidence", new=AsyncMock(return_value=3)):
            from typing import TypedDict

            class TestState(TypedDict):
                user_id: str
                business_profile_id: str
                messages: list
                error_count: int
                errors: list

            state = TestState(
                user_id=str(uuid4()),
                business_profile_id=str(uuid4()),
                messages=[],
                error_count=0,
                errors=[],
            )
            result = await node.sync_evidence_status(state)
            assert len(result["messages"]) > 0
            assert (
                "Evidence sync completed: 3 items marked stale" in result["messages"][0].content,
            )

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_sync_with_no_database_connection(self, mock_get_db):
        """Test sync_evidence_status when database connection fails."""
        mock_get_db.side_effect = Exception("Database unavailable")
        node = EvidenceCollectionNode()
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }
        result = await node.sync_evidence_status(state)
        assert len(result["messages"]) == 1
        assert "Evidence sync failed" in result["messages"][0].content
        assert "Database unavailable" in result["messages"][0].content


@pytest.mark.asyncio
class TestIntegrationWithRefactoredMethods:
    """Integration tests for the refactored methods working together."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_full_sync_workflow(self, mock_get_db):
        """Test complete workflow with refactored methods."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock(spec=Result)
        mock_result.rowcount = 15
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }
        result = await node.sync_evidence_status(state, cutoff_days=45)
        assert mock_session.execute.called
        assert mock_session.commit.called
        assert not mock_session.rollback.called
        assert result["sync_count"] == 15
        assert "last_sync" in result
        assert "sync_results" in result
        assert result["sync_results"]["updated_count"] == 15

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_sync_idempotency(self, mock_get_db):
        """Test that running sync multiple times is safe."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_result1 = MagicMock(spec=Result)
        mock_result1.rowcount = 10
        mock_result2 = MagicMock(spec=Result)
        mock_result2.rowcount = 0
        mock_session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])
        mock_session.commit = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])
        node = EvidenceCollectionNode()
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }
        result1 = await node.sync_evidence_status(state)
        assert result1["sync_count"] == 10
        mock_get_db.return_value = async_generator([mock_session])
        result2 = await node.sync_evidence_status(state)
        assert result2["sync_count"] == 0
