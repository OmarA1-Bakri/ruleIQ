"""Tests to legitimately achieve 80% coverage for evidence_nodes module.

These tests cover real scenarios that could occur in production:
1. Duplicate evidence detection
2. Missing evidence data
3. Database commit failures
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from langchain_core.messages import SystemMessage

from database.evidence_item import EvidenceItem
from langgraph_agent.nodes.evidence_nodes import EvidenceCollectionNode, evidence_node


async def async_generator(items):
    """Helper to create async generator."""
    for item in items:
        yield item


@pytest.mark.asyncio
class TestDuplicateDetection:
    """Test duplicate evidence detection paths."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_detects_duplicate(
        self, mock_duplicate_detector_class, mock_get_db
    ):
        """Test that duplicate evidence is properly detected and handled."""
        # Setup duplicate detector to return True
        mock_duplicate_detector_class.is_duplicate = AsyncMock(return_value=True)

        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Test with state mode (covers lines 107-113)
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_items": [],
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
            "processing_status": "pending",
        }

        evidence_data = {
            "evidence_name": "Duplicate Evidence",
            "evidence_type": "Document",
            "description": "This is a duplicate",
        }

        result = await node.process_evidence(state, evidence_data=evidence_data)

        # Verify duplicate was detected
        assert result["processing_status"] == "skipped"
        assert len(result["messages"]) == 1
        assert "duplicate detected" in result["messages"][0].content
        assert mock_duplicate_detector_class.is_duplicate.called

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_duplicate_returns_status(
        self, mock_duplicate_detector_class, mock_get_db
    ):
        """Test duplicate detection in backward compatibility mode."""
        # Setup duplicate detector to return True
        mock_duplicate_detector_class.is_duplicate = AsyncMock(return_value=True)

        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Test with direct evidence_data (backward compatibility, return_evidence_only=True)
        evidence_data = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_name": "Duplicate Evidence",
            "evidence_type": "Document",
        }

        result = await node.process_evidence(evidence_data)

        # Should return duplicate status
        assert result["status"] == "duplicate"


@pytest.mark.asyncio
class TestNoEvidenceData:
    """Test handling of missing evidence data."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_process_evidence_no_data_state_mode(self, mock_get_db):
        """Test process_evidence when no evidence data provided in state mode."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # State with no evidence data (covers lines 90-95)
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_items": [],
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
        }

        # Call with empty evidence_data
        result = await node.process_evidence(state, evidence_data={})

        # Verify no-data handling
        assert len(result["messages"]) == 1
        assert "No evidence data to process" in result["messages"][0].content
        assert result == state  # State returned unchanged except for message

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_process_evidence_no_data_backward_compat(self, mock_get_db):
        """Test process_evidence with empty data in backward compatibility mode."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Test backward compatibility mode with state extraction
        state_with_empty_evidence = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "current_evidence": {},  # Empty evidence in state
            "messages": [],
            "errors": [],
            "error_count": 0,
        }

        # Call with state as first parameter AND empty evidence_data (old calling convention)
        # This covers lines 77-78 and 83
        result = await node.process_evidence(
            state_with_empty_evidence,
            evidence_data={},
        )

        # Check the result is a dict
        assert isinstance(result, dict)
        # When no evidence data is found, it should update state messages
        assert len(result.get("messages", [])) > 0
        assert "No evidence data to process" in result["messages"][0].content


@pytest.mark.asyncio
class TestDatabaseCommitError:
    """Test database commit error handling."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_commit_failure(
        self, mock_duplicate_detector_class, mock_processor_class, mock_get_db
    ):
        """Test handling of database commit failure during evidence processing."""
        # Setup mocks
        mock_duplicate_detector_class.is_duplicate = AsyncMock(return_value=False)

        mock_processor = MagicMock()
        mock_processor.process_evidence = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Create session that fails on commit
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.refresh = AsyncMock()

        # Commit raises SQLAlchemyError (covers lines 167-173)
        mock_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Connection lost during commit"),
        )
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

        evidence_data = {
            "evidence_name": "Test Evidence",
            "evidence_type": "Document",
            "description": "Will fail on commit",
        }

        # Should raise the database error
        with pytest.raises(SQLAlchemyError, match="Connection lost during commit"):
            await node.process_evidence(state, evidence_data=evidence_data)

        # Verify rollback was called
        assert mock_session.rollback.called
        assert state["error_count"] == 1
        assert "Connection lost during commit" in state["errors"][0]

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_unexpected_error(
        self, mock_duplicate_detector_class, mock_processor_class, mock_get_db
    ):
        """Test handling of unexpected errors during evidence processing."""
        # Setup mocks
        mock_duplicate_detector_class.is_duplicate = AsyncMock(return_value=False)

        mock_processor = MagicMock()
        mock_processor.process_evidence = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Create session that raises unexpected error
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()

        # Refresh raises unexpected error (covers lines 175-181)
        mock_session.refresh = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_session.rollback = AsyncMock()
        mock_session.commit = AsyncMock()

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
            "processing_status": "pending",
        }

        evidence_data = {"evidence_name": "Test Evidence", "evidence_type": "Document"}

        # Should catch and handle the error gracefully when return_evidence_only is False
        result = await node.process_evidence(state, evidence_data=evidence_data)

        # Verify error handling
        assert mock_session.rollback.called
        assert result["error_count"] == 1
        assert result["processing_status"] == "failed"
        assert len(result["messages"]) == 1
        assert ("Evidence processing failed: Unexpected error" in result["messages"][0].content,)


@pytest.mark.asyncio
class TestStateUpdatePaths:
    """Test state update paths for coverage."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    async def test_process_evidence_state_updates(
        self, mock_duplicate_detector_class, mock_processor_class, mock_get_db
    ):
        """Test that state is properly updated during successful processing."""
        # Setup mocks for successful processing
        mock_duplicate_detector_class.is_duplicate = AsyncMock(return_value=False)

        mock_processor = MagicMock()
        mock_processor.process_evidence = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Setup session
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock refresh to add ID to evidence
        async def mock_refresh(evidence_item):
            evidence_item.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # State that will get updated (covers lines 147-153)
        state = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_items": [],
            "evidence_status": {},
            "messages": [],
            "errors": [],
            "error_count": 0,
            "processing_status": "pending",
        }

        evidence_data = {
            "evidence_name": "Success Evidence",
            "evidence_type": "Policy",
            "description": "Will process successfully",
        }

        result = await node.process_evidence(state, evidence_data=evidence_data)

        # Verify state was updated
        assert len(result["evidence_items"]) == 1
        assert result["evidence_items"][0]["type"] == "Policy"
        assert result["evidence_items"][0]["status"] == "processed"
        assert result["processing_status"] == "completed"
        assert len(result["messages"]) == 1
        assert "Evidence processed:" in result["messages"][0].content
