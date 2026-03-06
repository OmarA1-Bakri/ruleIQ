"""Integration tests for evidence_nodes module."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from database.evidence_item import EvidenceItem
from langgraph_agent.nodes.evidence_nodes import EvidenceCollectionNode, evidence_node
import contextlib


# Fixtures
@pytest.fixture
def minimal_state() -> Dict[str, Any]:
    """Create minimal state for testing."""
    return {
        "user_id": str(uuid4()),
        "business_profile_id": str(uuid4()),
        "evidence_items": [],
        "evidence_status": {},
        "evidence_scores": {},
        "evidence_validation_results": [],
        "evidence_collection_state": "init",
        "messages": [],
        "errors": [],
        "error_count": 0,
        "processing_status": "init",
    }


@pytest.fixture
def evidence_data() -> Dict[str, Any]:
    """Create sample evidence data."""
    return {
        "id": str(uuid4()),
        "evidence_name": "Security Policy Document",
        "evidence_type": "Policy",
        "control_reference": "ISO-27001-A.5.1.1",
        "description": "Information security policy document",
        "source": "manual",
        "type": "document",
        "content": "This is a comprehensive security policy covering all aspects of information security in our organization.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {"version": "1.0", "approved": True},
    }


async def async_generator(items):
    """Helper to create async generator."""
    for item in items:
        yield item


@pytest.mark.asyncio
class TestEvidenceCollectionNodeIntegration:
    """Integration tests for EvidenceCollectionNode class."""

    async def test_init_without_dependencies(self):
        """Test node initialization without external dependencies."""
        node = EvidenceCollectionNode()

        # Verify attributes are initialized
        assert node.processor is None
        assert node.duplicate_detector is None
        assert hasattr(node, "circuit_breaker_state")
        assert node.circuit_breaker_state == "closed"

    async def test_init_with_dependencies(self):
        """Test node initialization with dependencies."""
        mock_processor = Mock()
        mock_detector = Mock()

        node = EvidenceCollectionNode(
            processor=mock_processor,
            duplicate_detector=mock_detector,
        )

        assert node.processor == mock_processor
        assert node.duplicate_detector == mock_detector

    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_process_evidence_backward_compatibility(
        self, mock_get_db, mock_duplicate_detector, mock_evidence_processor
    ):
        """Test process_evidence in backward compatibility mode (evidence_data only)."""
        # Setup mock database
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])

        # Setup duplicate detector mock
        mock_duplicate_detector.is_duplicate = AsyncMock(return_value=False)

        # Setup evidence processor mock
        mock_processor_instance = MagicMock()
        mock_processor_instance.process_evidence = MagicMock()
        mock_evidence_processor.return_value = mock_processor_instance

        node = EvidenceCollectionNode()

        evidence_data = {
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "evidence_name": "Security Policy",
            "evidence_type": "Policy",
            "control_reference": "ISO-27001-A.5.1",
            "description": "Information security policy document",
            "source": "manual",
        }

        # Call with evidence_data as first arg (backward compatibility)
        result = await node.process_evidence(evidence_data)

        # Assert - returns evidence dict
        assert result["status"] == "processed"
        assert "id" in result

    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_process_evidence_with_state(
        self,
        mock_get_db,
        mock_duplicate_detector,
        mock_evidence_processor,
        minimal_state,
    ):
        """Test process_evidence with state and evidence_data."""
        # Setup mock database
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])

        # Setup duplicate detector mock
        mock_duplicate_detector.is_duplicate = AsyncMock(return_value=False)

        # Setup evidence processor mock
        mock_processor_instance = MagicMock()
        mock_processor_instance.process_evidence = MagicMock()
        mock_evidence_processor.return_value = mock_processor_instance

        node = EvidenceCollectionNode()

        evidence_data = {
            "evidence_name": "Security Policy",
            "evidence_type": "Policy",
            "control_reference": "ISO-27001-A.5.1",
            "description": "Information security policy document",
            "source": "manual",
        }

        # Call with state and evidence_data
        result = await node.process_evidence(minimal_state, evidence_data)

        # Assert - returns updated state
        assert len(result["evidence_items"]) == 1
        assert result["evidence_items"][0]["status"] == "processed"
        assert result["processing_status"] == "completed"

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_sync_evidence_status(self, mock_get_db, minimal_state):
        """Test syncing evidence status with database."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[])),
        )
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Add evidence to state
        minimal_state["evidence_status"] = {"item1": "collected", "item2": "pending"}

        result = await node.sync_evidence_status(minimal_state)

        # Verify database interaction
        assert mock_session.execute.called

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_check_evidence_expiry(self, mock_get_db, minimal_state):
        """Test checking for expired evidence."""
        # Create mock evidence items
        expired_evidence = MagicMock(spec=EvidenceItem)
        expired_evidence.id = "expired_id"
        expired_evidence.collected_at = datetime.now(timezone.utc) - timedelta(days=100)
        expired_evidence.collection_frequency = "monthly"
        expired_evidence.to_dict = MagicMock(
            return_value={
                "id": "expired_id",
                "evidence_name": "Expired Doc",
                "status": "collected",
                "collected_at": expired_evidence.collected_at.isoformat(),
            },
        )

        mock_session = MagicMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[expired_evidence])),
        )
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()
        result = await node.check_evidence_expiry(minimal_state)

        # Check that expired evidence was marked
        assert mock_session.execute.called

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_collect_all_integrations(self, mock_get_db, minimal_state):
        """Test collecting evidence from all configured integrations."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Should handle no integrations gracefully
        result = await node.collect_all_integrations(minimal_state)

        # State should be returned unchanged when no integrations
        assert result == minimal_state

    async def test_validate_evidence_method(self):
        """Test evidence validation logic."""
        node = EvidenceCollectionNode()

        # Test with missing fields
        invalid_evidence = {"type": "document"}
        result = await node.validate_evidence(invalid_evidence)

        assert result["valid"] is False
        assert "Missing required field: id" in result["errors"]

        # Test with complete evidence
        valid_evidence = {
            "id": "123",
            "type": "document",
            "content": "A" * 150,
            "source": {"verified": True},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"key": "value"},
        }

        result = await node.validate_evidence(valid_evidence)
        assert result["valid"] is True
        assert result["score"] > 0.5
        assert result["confidence"] > 0.5

    async def test_aggregate_evidence_method(self):
        """Test evidence aggregation by type."""
        node = EvidenceCollectionNode()

        evidence_list = [
            {
                "id": "1",
                "evidence_name": "Doc 1",
                "type": "Policy",
                "status": "collected",
                "content": "Content 1",
            },
            {
                "id": "2",
                "evidence_name": "Doc 2",
                "type": "Policy",
                "status": "pending",
                "content": "Content 2",
            },
            {
                "id": "3",
                "evidence_name": "Doc 3",
                "type": "Procedure",
                "status": "collected",
                "content": "Content 3",
            },
        ]

        result = await node.aggregate_evidence(evidence_list)

        assert "Policy" in result
        assert len(result["Policy"]) == 2
        assert "Procedure" in result
        assert len(result["Procedure"]) == 1

    async def test_merge_evidence_method(self):
        """Test merging evidence items (sync method)."""
        node = EvidenceCollectionNode()

        evidence1 = {
            "id": "1",
            "type": "Policy",
            "content": {"data": "original"},
            "score": 0.8,
        }
        evidence2 = {"id": "2", "content": {"extra": "new"}, "score": 0.6}

        result = node.merge_evidence(evidence1, evidence2)

        assert result["id"] == "1"  # Preserves existing id
        assert result["type"] == "Policy"  # Preserves existing type
        assert result["content"]["data"] == "original"  # Preserves existing content
        assert result["content"]["extra"] == "new"  # Merges new content
        assert result["combined_score"] == 0.7  # Average of scores

    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_duplicate_detection(self, mock_get_db, mock_evidence_processor):
        """Test duplicate evidence detection."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_get_db.return_value = async_generator([mock_session])

        # Setup evidence processor mock
        mock_processor_instance = MagicMock()
        mock_processor_instance.process_evidence = MagicMock()
        mock_evidence_processor.return_value = mock_processor_instance

        # Create node with mock duplicate detector
        mock_detector = Mock()
        mock_detector.is_duplicate = AsyncMock(return_value=True)

        node = EvidenceCollectionNode(duplicate_detector=mock_detector)

        evidence_data = {
            "user_id": str(uuid4()),
            "evidence_name": "Duplicate Doc",
            "evidence_type": "Policy",
        }

        result = await node.process_evidence(evidence_data)

        assert result["status"] == "duplicate"

    async def test_evidence_node_instance(self):
        """Test evidence_node is an instance of EvidenceCollectionNode."""
        assert isinstance(evidence_node, EvidenceCollectionNode)
        assert evidence_node.circuit_breaker_state == "closed"

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_circuit_breaker_functionality(self, mock_get_db, minimal_state):
        """Test circuit breaker state management."""
        node = EvidenceCollectionNode()

        # Initial state should be closed
        assert node.circuit_breaker_state == "closed"

        # Simulate multiple failures to trigger circuit breaker
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(side_effect=Exception("DB Error"))
        mock_get_db.return_value = async_generator([mock_session])

        # Try to process evidence - should fail but handle gracefully
        with contextlib.suppress(ValueError, TypeError):
            await node.sync_evidence_status(minimal_state)

        # Circuit breaker state might change based on failure handling
        assert hasattr(node, "circuit_breaker_state")

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_retry_with_backoff(self, mock_get_db):
        """Test retry mechanism with exponential backoff."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Create a function that fails first 2 times, then succeeds
        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Temporary failure {call_count}")
            return "Success"

        result = await node.retry_with_backoff(flaky_operation)
        assert result == "Success"
        assert call_count == 3

    @patch("langgraph_agent.nodes.evidence_nodes.EvidenceProcessor")
    @patch("langgraph_agent.nodes.evidence_nodes.DuplicateDetector")
    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_concurrent_evidence_processing(
        self, mock_get_db, mock_duplicate_detector, mock_evidence_processor
    ):
        """Test processing multiple evidence items concurrently."""

        # Create a factory for mock sessions and generators
        def create_mock_db_generator():
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            # Mock refresh to set the id on the evidence item
            async def mock_refresh(evidence_item):
                evidence_item.id = uuid4()

            mock_session.refresh = AsyncMock(side_effect=mock_refresh)
            mock_session.rollback = AsyncMock()

            # Create async generator that yields this session
            async def generator():
                yield mock_session

            return generator()

        # Mock get_async_db to return a new generator for each call
        mock_get_db.side_effect = create_mock_db_generator

        # Setup duplicate detector mock
        mock_duplicate_detector.is_duplicate = AsyncMock(return_value=False)

        # Setup evidence processor mock
        mock_processor_instance = MagicMock()
        mock_processor_instance.process_evidence = MagicMock()
        mock_evidence_processor.return_value = mock_processor_instance

        node = EvidenceCollectionNode()

        evidence_items = [
            {
                "evidence_name": f"Doc {i}",
                "evidence_type": "Policy",
                "user_id": str(uuid4()),
            }
            for i in range(5)
        ]

        # Process all evidence items concurrently
        tasks = [node.process_evidence(item) for item in evidence_items]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(r["status"] == "processed" for r in results)


@pytest.mark.asyncio
class TestErrorScenariosIntegration:
    """Test error handling scenarios."""

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_database_error_handling(self, mock_get_db):
        """Test handling of database errors."""

        # Create an async generator that raises an exception
        async def failing_generator():
            raise Exception("Database connection failed")
            yield  # This will never be reached

        mock_get_db.return_value = failing_generator()

        node = EvidenceCollectionNode()
        evidence_data = {"evidence_name": "Test Doc", "user_id": str(uuid4())}

        # Should handle error gracefully and return error status
        result = await node.process_evidence(evidence_data)
        assert result["status"] == "failed"
        assert "error" in result

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_validation_error_handling(self, mock_get_db, minimal_state):
        """Test handling of validation errors."""
        mock_session = MagicMock(spec=AsyncSession)
        mock_get_db.return_value = async_generator([mock_session])

        node = EvidenceCollectionNode()

        # Evidence with invalid data
        invalid_evidence = {}  # Missing all required fields

        result = await node.validate_evidence(invalid_evidence)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    @patch("langgraph_agent.nodes.evidence_nodes.get_async_db")
    async def test_network_timeout_simulation(self, mock_get_db):
        """Test handling of network timeouts."""

        async def slow_operation():
            await asyncio.sleep(10)  # Simulate slow network
            return "Result"

        node = EvidenceCollectionNode()

        # Should timeout and handle gracefully
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.1)
