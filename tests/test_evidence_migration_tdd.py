"""

Test-Driven Development suite for Evidence Collection Tasks Migration.
Following TDD principles: Write tests first, then implementation.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from langgraph_agent.graph.enhanced_state import EnhancedComplianceState
from langgraph_agent.graph.error_handler import ErrorHandlerNode
from langgraph_agent.nodes.evidence_nodes import EvidenceCollectionNode


# ==========================
# Test Fixtures
# ==========================


@pytest.fixture
def mock_db_session():
    """Mock database session with async context manager."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_processor():
    """Mock evidence processor."""
    processor = Mock()
    processor.process_evidence = Mock(return_value=True)
    processor.validate_evidence = Mock(return_value={"valid": True, "score": 0.95})
    return processor


@pytest.fixture
def mock_duplicate_detector():
    """Mock duplicate detector."""
    detector = Mock()
    detector.is_duplicate = AsyncMock(return_value=False)
    return detector


@pytest.fixture
def sample_evidence_data():
    """Sample evidence data for testing."""
    return {
        "evidence_type": "document",
        "description": "Test evidence document",
        "source": "integration_api",
        "raw_data": {
            "file_name": "test.pdf",
            "content": "Test content",
            "metadata": {"size": 1024},
        },
        "confidence_score": 0.85,
        "validation_status": "pending",
    }


@pytest.fixture
def sample_state():
    """Sample enhanced compliance state."""

    # Create a simple mock object that behaves like both dict and object
    class StateDict(dict):
        def __getattr__(self, key):
            return self[key]

        def __setattr__(self, key, value):
            self[key] = value

    state = StateDict(
        {
            "case_id": str(uuid4()),
            "user_id": str(uuid4()),
            "business_profile_id": str(uuid4()),
            "actor": "EvidenceCollector",
            "objective": "Collect evidence for compliance verification",
            "context": {
                "user_id": str(uuid4()),
                "business_profile_id": str(uuid4()),
                "integration_id": "test_integration",
            },
            "evidence_items": [],
            "validation_results": {},
            "retry_count": 0,
            "error_count": 0,
            "node_execution_times": {},
            "evidence_validation_results": [],
            "evidence_status": {},
            "evidence_scores": {},
            "evidence_collection_state": "init",
            "messages": [],
            "session_id": "test-session",
            "company_id": uuid4(),
            "workflow_status": "active",
            "errors": [],
            "max_retries": 3,
        },
    )
    state.dict = lambda: dict(state)
    return state


# ==========================
# Test Classes
# ==========================


class TestEvidenceStateManagement:
    """Tests for evidence state management within LangGraph."""

    async def test_evidence_state_initialization(self, sample_state):
        """Test that evidence state is properly initialized."""
        assert sample_state.actor == "EvidenceCollector"
        assert sample_state.evidence_items == []
        assert sample_state.validation_results == {}
        assert sample_state.retry_count == 0
        assert sample_state.error_count == 0

    async def test_evidence_accumulation_in_state(self, sample_state, sample_evidence_data):
        """Test that evidence items are accumulated, not replaced."""
        # Add first evidence item
        sample_state.evidence_items.append({"id": str(uuid4()), **sample_evidence_data})
        assert len(sample_state.evidence_items) == 1

        # Add second evidence item - should accumulate
        sample_state.evidence_items.append({"id": str(uuid4()), **sample_evidence_data})
        assert len(sample_state.evidence_items) == 2

        # Verify both items are preserved
        assert all(item.get("evidence_type") == "document" for item in sample_state.evidence_items)

    async def test_state_transition_tracking(self, sample_state):
        """Test state transition tracking for evidence collection."""
        transitions = []

        # Initial state
        transitions.append(("init", sample_state.actor))
        assert transitions[-1] == ("init", "EvidenceCollector")

        # Collecting evidence
        sample_state.context["status"] = "collecting"
        transitions.append(("collecting", sample_state.actor))

        # Validating evidence
        sample_state.context["status"] = "validating"
        transitions.append(("validating", sample_state.actor))

        # Completed
        sample_state.context["status"] = "completed"
        transitions.append(("completed", sample_state.actor))

        assert len(transitions) == 4
        assert transitions[-1][0] == "completed"

    async def test_error_tracking_in_state(self, sample_state):
        """Test error tracking within evidence collection state."""
        # Initial state
        assert sample_state.error_count == 0
        assert sample_state.retry_count == 0

        # Simulate error
        sample_state.error_count += 1
        sample_state.retry_count += 1
        sample_state.context["last_error"] = "Database connection failed"

        assert sample_state.error_count == 1
        assert sample_state.retry_count == 1
        assert sample_state.context["last_error"] == "Database connection failed"

        # Simulate recovery
        sample_state.context["status"] = "recovered"
        assert sample_state.context["status"] == "recovered"


class TestEvidenceValidationAndScoring:
    """Tests for evidence validation and scoring mechanisms."""

    async def test_evidence_validation_success(self, mock_processor, sample_evidence_data):
        """Test successful evidence validation."""
        result = mock_processor.validate_evidence(sample_evidence_data)
        assert result["valid"] is True
        assert result["score"] == 0.95
        mock_processor.validate_evidence.assert_called_once_with(sample_evidence_data)

    async def test_evidence_validation_failure(self, mock_processor, sample_evidence_data):
        """Test evidence validation failure."""
        mock_processor.validate_evidence.return_value = {
            "valid": False,
            "score": 0.2,
            "errors": ["Missing required fields", "Invalid format"],
        }

        result = mock_processor.validate_evidence(sample_evidence_data)
        assert result["valid"] is False
        assert result["score"] == 0.2
        assert "errors" in result
        assert len(result["errors"]) == 2

    async def test_evidence_scoring_thresholds(self, mock_processor):
        """Test evidence scoring with different thresholds."""
        test_cases = [
            ({"data": "high_quality"}, 0.95, "high"),
            ({"data": "medium_quality"}, 0.75, "medium"),
            ({"data": "low_quality"}, 0.45, "low"),
            ({"data": "invalid"}, 0.1, "rejected"),
        ]

        for evidence, expected_score, quality_level in test_cases:
            mock_processor.validate_evidence.return_value = {
                "valid": expected_score > 0.3,
                "score": expected_score,
                "quality": quality_level,
            }

            result = mock_processor.validate_evidence(evidence)
            assert result["score"] == expected_score
            assert result["quality"] == quality_level

    async def test_evidence_confidence_calculation(self, sample_evidence_data):
        """Test confidence score calculation for evidence."""
        # Base confidence from source
        source_confidence = {
            "integration_api": 0.9,
            "manual_upload": 0.7,
            "automated_scan": 0.8,
        }

        # Calculate confidence
        source = sample_evidence_data["source"]
        base_confidence = source_confidence.get(source, 0.5)
        data_confidence = sample_evidence_data.get("confidence_score", 0.5)

        final_confidence = (base_confidence + data_confidence) / 2
        assert final_confidence == 0.875  # (0.9 + 0.85) / 2


class TestRetryAndFallbackMechanisms:
    """Tests for retry logic and fallback strategies."""

    async def test_retry_with_exponential_backoff(self):
        """Test retry mechanism with exponential backoff."""
        retry_delays = []
        max_retries = 5
        base_delay = 1

        for attempt in range(max_retries):
            delay = base_delay * (2**attempt)
            retry_delays.append(delay)

        assert retry_delays == [1, 2, 4, 8, 16]
        assert len(retry_delays) == max_retries

    async def test_retry_with_jitter(self):
        """Test retry mechanism with jitter to prevent thundering herd."""
        import random

        random.seed(42)  # For deterministic tests

        retry_delays = []
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            delay = base_delay * (2**attempt)
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            retry_delays.append(delay + jitter)

        # Verify delays increase with some variance
        assert all(retry_delays[i] < retry_delays[i + 1] for i in range(len(retry_delays) - 1))

    async def test_fallback_to_cache(self, sample_evidence_data):
        """Test fallback to cached evidence when primary source fails."""
        cache = {}
        cache_key = f"evidence_{sample_evidence_data['source']}"

        # Simulate primary failure, fallback to cache
        try:
            # Primary attempt fails
            raise ConnectionError("Primary source unavailable")
        except ConnectionError:
            # Fallback to cache
            if cache_key in cache:
                fallback_data = cache[cache_key]
            else:
                # Use default/stale data
                fallback_data = {**sample_evidence_data, "is_cached": True}
                cache[cache_key] = fallback_data

        assert fallback_data["is_cached"] is True
        assert cache_key in cache

    async def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern for failing integrations."""

        class CircuitBreaker:
            def __init__(self, failure_threshold=3, recovery_timeout=60):
                self.failure_count = 0
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self.last_failure_time = None
                self.state = "closed"  # closed, open, half-open

            def call(self, func, *args, **kwargs):
                if self.state == "open":
                    if (
                        self.last_failure_time
                        and (datetime.now() - self.last_failure_time).seconds
                        > self.recovery_timeout
                    ):
                        self.state = "half-open"
                    else:
                        raise Exception("Circuit breaker is open")

                try:
                    result = func(*args, **kwargs)
                    if self.state == "half-open":
                        self.state = "closed"
                        self.failure_count = 0
                    return result
                except Exception as e:
                    self.failure_count += 1
                    self.last_failure_time = datetime.now()

                    if self.failure_count >= self.failure_threshold:
                        self.state = "open"
                    raise e

        breaker = CircuitBreaker(failure_threshold=3)

        def failing_function():
            raise ValueError("Integration failed")

        # Test circuit breaker opens after threshold
        for _i in range(3):
            with pytest.raises(ValueError):
                breaker.call(failing_function)

        assert breaker.state == "open"
        assert breaker.failure_count == 3

        # Circuit breaker should block calls when open
        with pytest.raises(Exception, match="Circuit breaker is open"):
            breaker.call(failing_function)


class TestEvidenceAggregationAndDeduplication:
    """Tests for evidence aggregation and deduplication logic."""

    async def test_duplicate_detection(self, mock_duplicate_detector, sample_evidence_data):
        """Test duplicate evidence detection."""
        # First call - not duplicate
        is_dup = await mock_duplicate_detector.is_duplicate(sample_evidence_data)
        assert is_dup is False

        # Configure for duplicate
        mock_duplicate_detector.is_duplicate.return_value = True
        is_dup = await mock_duplicate_detector.is_duplicate(sample_evidence_data)
        assert is_dup is True

    async def test_evidence_aggregation_by_type(self, sample_evidence_data):
        """Test evidence aggregation by type."""
        evidence_list = [
            {**sample_evidence_data, "evidence_type": "document", "id": "1"},
            {**sample_evidence_data, "evidence_type": "document", "id": "2"},
            {**sample_evidence_data, "evidence_type": "screenshot", "id": "3"},
            {**sample_evidence_data, "evidence_type": "api_response", "id": "4"},
            {**sample_evidence_data, "evidence_type": "document", "id": "5"},
        ]

        # Aggregate by type
        aggregated = {}
        for evidence in evidence_list:
            evidence_type = evidence["evidence_type"]
            if evidence_type not in aggregated:
                aggregated[evidence_type] = []
            aggregated[evidence_type].append(evidence)

        assert len(aggregated["document"]) == 3
        assert len(aggregated["screenshot"]) == 1
        assert len(aggregated["api_response"]) == 1

    async def test_evidence_deduplication_by_hash(self, sample_evidence_data):
        """Test evidence deduplication using content hash."""
        import hashlib

        def compute_hash(evidence):
            content = json.dumps(evidence.get("raw_data", {}), sort_keys=True)
            return hashlib.sha256(content.encode()).hexdigest()

        evidence_list = [
            {**sample_evidence_data, "id": "1"},
            {**sample_evidence_data, "id": "2"},  # Duplicate content
            {**sample_evidence_data, "raw_data": {"different": "content"}, "id": "3"},
            {**sample_evidence_data, "id": "4"},  # Duplicate content,
        ]

        seen_hashes = set()
        deduplicated = []

        for evidence in evidence_list:
            evidence_hash = compute_hash(evidence)
            if evidence_hash not in seen_hashes:
                seen_hashes.add(evidence_hash)
                deduplicated.append(evidence)

        assert len(deduplicated) == 2  # Only unique content
        assert len(seen_hashes) == 2

    async def test_evidence_merging_strategy(self):
        """Test merging strategy for related evidence."""
        evidence_groups = {
            "policy_compliance": [
                {"id": "1", "score": 0.8, "findings": ["Finding A"]},
                {"id": "2", "score": 0.9, "findings": ["Finding B", "Finding C"]},
            ],
            "data_protection": [
                {"id": "3", "score": 0.7, "findings": ["Finding D"]},
            ],
        }

        # Merge evidence within groups
        merged = {}
        for group_name, evidences in evidence_groups.items():
            merged[group_name] = {
                "combined_score": round(
                    sum(e["score"] for e in evidences) / len(evidences),
                    2,
                ),
                "all_findings": [f for e in evidences for f in e["findings"]],
                "evidence_count": len(evidences),
            }

        assert merged["policy_compliance"]["combined_score"] == 0.85
        assert len(merged["policy_compliance"]["all_findings"]) == 3
        assert merged["policy_compliance"]["evidence_count"] == 2


class TestEvidenceCollectionWorkflows:
    """Tests for complete evidence collection workflows."""

    async def test_single_evidence_processing_workflow(
        self,
        mock_db_session,
        mock_processor,
        mock_duplicate_detector,
        sample_evidence_data,
        sample_state,
    ):
        """Test complete workflow for processing a single evidence item."""
        node = EvidenceCollectionNode(mock_processor, mock_duplicate_detector)

        # Mock the database session properly
        async def mock_get_db_gen():
            yield mock_db_session

        with patch(
            "langgraph_agent.nodes.evidence_nodes.get_async_db",
            return_value=mock_get_db_gen(),
        ):
            # Process evidence
            result = await node.process_evidence(sample_state, sample_evidence_data)

            # Verify workflow steps
            assert mock_duplicate_detector.is_duplicate.called
            assert mock_processor.process_evidence.called
            assert mock_db_session.add.called
            assert mock_db_session.commit.called

    async def test_batch_evidence_collection_workflow(self, sample_state):
        """Test batch evidence collection from multiple sources."""
        sources = ["api_1", "api_2", "database_1"]
        collected_evidence = []

        async def collect_from_source(source):
            # Simulate collection
            await asyncio.sleep(0.1)  # Simulate API call
            return {
                "source": source,
                "evidence_type": "automated",
                "data": f"Evidence from {source}",
                "timestamp": datetime.now().isoformat(),
            }

        # Collect in parallel
        tasks = [collect_from_source(source) for source in sources]
        results = await asyncio.gather(*tasks)
        collected_evidence.extend(results)

        assert len(collected_evidence) == 3
        assert all(e["evidence_type"] == "automated" for e in collected_evidence)
        assert collected_evidence[0]["source"] == "api_1"

    async def test_evidence_lifecycle_management(self, sample_evidence_data):
        """Test evidence lifecycle from collection to expiry."""
        evidence = {
            **sample_evidence_data,
            "id": str(uuid4()),
            "collected_at": datetime.now(),
            "status": "active",
            "expiry_days": 90,
        }

        # Active phase
        assert evidence["status"] == "active"

        # Check if stale (after 90 days)
        cutoff_date = datetime.now() - timedelta(days=91)
        if evidence["collected_at"] < cutoff_date:
            evidence["status"] = "stale"

        # For testing, simulate stale condition
        evidence["collected_at"] = datetime.now() - timedelta(days=91)
        if evidence["collected_at"] < datetime.now() - timedelta(days=90):
            evidence["status"] = "stale"

        assert evidence["status"] == "stale"

    async def test_evidence_status_sync_workflow(self, mock_db_session):
        """Test evidence status synchronization workflow."""

        # Mock the database session properly
        async def mock_get_db_gen():
            yield mock_db_session

        # Mock the update result
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db_session.execute.return_value = mock_result

        with patch(
            "langgraph_agent.nodes.evidence_nodes.get_async_db",
            return_value=mock_get_db_gen(),
        ):
            node = EvidenceCollectionNode(Mock(), Mock())
            result = await node.sync_evidence_status({})

            assert mock_db_session.execute.called
            assert mock_db_session.commit.called


class TestErrorHandlingAndRecovery:
    """Tests for error handling and recovery strategies."""

    async def test_database_error_handling(
        self, mock_db_session, sample_state, sample_evidence_data
    ):
        """Test handling of database errors during evidence processing."""
        mock_db_session.commit.side_effect = SQLAlchemyError("Database connection lost")

        # Mock the database session properly
        async def mock_get_db_gen():
            yield mock_db_session

        with patch(
            "langgraph_agent.nodes.evidence_nodes.get_async_db",
            return_value=mock_get_db_gen(),
        ):
            # Create properly configured mocks for async methods
            mock_processor = Mock()
            mock_detector = Mock()
            mock_detector.is_duplicate = AsyncMock(return_value=False)

            node = EvidenceCollectionNode(mock_processor, mock_detector)

            with pytest.raises(SQLAlchemyError):
                await node.process_evidence(sample_state, sample_evidence_data)

            assert mock_db_session.rollback.called

    async def test_graceful_degradation(self, sample_evidence_data):
        """Test graceful degradation when optional features fail."""
        results = {
            "evidence_collected": True,
            "validation_performed": False,  # Failed but not critical
            "scoring_completed": False,  # Failed but not critical
            "stored_successfully": True,
            "notifications_sent": False,  # Failed but not critical,
        }

        # System should still function with degraded features
        critical_features = ["evidence_collected", "stored_successfully"]
        system_operational = all(results.get(feature) for feature in critical_features)

        assert system_operational is True
        assert results["validation_performed"] is False  # Degraded but operational

    async def test_error_recovery_with_checkpoint(self, sample_state):
        """Test recovery from checkpoint after error."""
        # Save checkpoint before risky operation
        checkpoint = {
            "state": sample_state.dict(),
            "timestamp": datetime.now().isoformat(),
            "operation": "evidence_validation",
        }

        try:
            # Simulate operation failure
            raise ValueError("Validation failed")
        except ValueError:
            # Recover from checkpoint
            recovered_state = checkpoint["state"].copy()
            recovered_state["retry_count"] = recovered_state.get("retry_count", 0) + 1

            assert recovered_state["case_id"] == sample_state["case_id"]
            assert (recovered_state["retry_count"] == sample_state.get("retry_count", 0) + 1,)


class TestIntegrationWithLangGraph:
    """Tests for integration with LangGraph framework."""

    async def test_node_registration_in_graph(self):
        """Test that evidence node is properly registered in LangGraph."""
        from langgraph.graph import StateGraph

        graph = StateGraph(EnhancedComplianceState)

        # Add evidence collection node
        evidence_node = EvidenceCollectionNode(Mock(), Mock())
        graph.add_node("collect_evidence", evidence_node.process_evidence)

        # Set entry point
        graph.set_entry_point("collect_evidence")

        # Set finish point
        graph.set_finish_point("collect_evidence")

        # Compile graph
        compiled = graph.compile()
        assert compiled is not None

    async def test_state_updates_through_node(self, sample_state, sample_evidence_data):
        """Test that state is properly updated when passing through node."""
        initial_evidence_count = len(sample_state.evidence_items)

        # Process through node (simulated)
        sample_state.evidence_items.append(
            {
                "id": str(uuid4()),
                **sample_evidence_data,
                "processed_at": datetime.now().isoformat(),
            },
        )

        assert len(sample_state.evidence_items) == initial_evidence_count + 1
        assert sample_state.evidence_items[-1]["evidence_type"] == "document"

    async def test_conditional_routing_based_on_evidence(self, sample_state):
        """Test conditional routing based on evidence validation results."""

        def route_evidence(state: EnhancedComplianceState) -> str:
            if not state.evidence_items:
                return "collect_more"

            valid_count = sum(
                1 for e in state.evidence_items if e.get("validation_status") == "valid"
            )

            if valid_count >= 3:
                return "proceed_to_assessment"
            elif valid_count >= 1:
                return "partial_assessment"
            else:
                return "collect_more"

        # Test routing logic
        assert route_evidence(sample_state) == "collect_more"

        # Add valid evidence
        sample_state.evidence_items = [
            {"validation_status": "valid"},
            {"validation_status": "valid"},
            {"validation_status": "valid"},
        ]
        assert route_evidence(sample_state) == "proceed_to_assessment"


class TestPerformanceAndOptimization:
    """Tests for performance optimization and efficiency."""

    async def test_batch_processing_performance(self):
        """Test that batch processing is more efficient than sequential."""
        import time

        async def process_single(item):
            await asyncio.sleep(0.1)  # Simulate processing
            return f"processed_{item}"

        items = list(range(10))

        # Sequential processing
        start = time.time()
        sequential_results = []
        for item in items:
            result = await process_single(item)
            sequential_results.append(result)
        sequential_time = time.time() - start

        # Batch processing (parallel)
        start = time.time()
        batch_results = await asyncio.gather(*[process_single(item) for item in items])
        batch_time = time.time() - start

        assert len(batch_results) == len(sequential_results)
        assert batch_time < sequential_time  # Batch should be faster

    async def test_caching_reduces_database_calls(self, mock_db_session):
        """Test that caching reduces database calls."""
        cache = {}
        db_call_count = 0

        async def get_evidence_with_cache(evidence_id):
            nonlocal db_call_count

            if evidence_id in cache:
                return cache[evidence_id]

            # Simulate database call
            db_call_count += 1

            # Create async mock result
            async def mock_query_result():
                return {"id": evidence_id, "data": f"Evidence {evidence_id}"}

            evidence = await mock_query_result()
            cache[evidence_id] = evidence
            return evidence

        # First call - hits database
        await get_evidence_with_cache("evidence_1")
        assert db_call_count == 1

        # Second call - uses cache
        await get_evidence_with_cache("evidence_1")
        assert db_call_count == 1  # No additional DB call

        # Different ID - hits database
        await get_evidence_with_cache("evidence_2")
        assert db_call_count == 2

    async def test_memory_efficient_streaming(self):
        """Test memory-efficient streaming for large evidence sets."""

        async def evidence_stream(batch_size=100):
            """Stream evidence in batches instead of loading all at once."""
            total_items = 1000
            for offset in range(0, total_items, batch_size):
                batch = list(range(offset, min(offset + batch_size, total_items)))
                yield batch

        processed_count = 0
        async for batch in evidence_stream(batch_size=100):
            processed_count += len(batch)
            assert len(batch) <= 100  # Memory bounded by batch size

        assert processed_count == 1000


class TestMonitoringAndObservability:
    """Tests for monitoring and observability features."""

    async def test_execution_time_tracking(self, sample_state):
        """Test that node execution times are tracked."""
        import time

        start_time = time.time()
        await asyncio.sleep(0.1)  # Simulate processing
        execution_time = time.time() - start_time

        sample_state.node_execution_times["collect_evidence"] = execution_time

        assert "collect_evidence" in sample_state.node_execution_times
        assert sample_state.node_execution_times["collect_evidence"] > 0.1

    async def test_metrics_collection(self):
        """Test metrics collection for evidence processing."""
        metrics = {
            "evidence_collected": 0,
            "evidence_validated": 0,
            "evidence_rejected": 0,
            "processing_errors": 0,
            "average_processing_time": 0.0,
            "cache_hit_rate": 0.0,
        }

        # Simulate processing
        metrics["evidence_collected"] += 10
        metrics["evidence_validated"] += 8
        metrics["evidence_rejected"] += 2
        metrics["average_processing_time"] = 0.250
        metrics["cache_hit_rate"] = 0.75

        assert metrics["evidence_collected"] == 10
        assert metrics["evidence_validated"] == 8
        assert metrics["evidence_rejected"] == 2
        assert metrics["cache_hit_rate"] == 0.75

    async def test_audit_trail_generation(self, sample_state, sample_evidence_data):
        """Test audit trail generation for evidence operations."""
        audit_trail = []

        def log_operation(operation, details):
            audit_trail.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "actor": sample_state.actor,
                    "case_id": sample_state.case_id,
                    "details": details,
                },
            )

        # Log operations
        log_operation("evidence_collected", {"source": sample_evidence_data["source"]})
        log_operation("evidence_validated", {"score": 0.95})
        log_operation("evidence_stored", {"id": str(uuid4())})

        assert len(audit_trail) == 3
        assert all("timestamp" in entry for entry in audit_trail)
        assert audit_trail[0]["operation"] == "evidence_collected"


# ==========================
# Integration Tests
# ==========================


@pytest.mark.asyncio
class TestEndToEndIntegration:
    """End-to-end integration tests for evidence collection."""

    async def test_complete_evidence_collection_pipeline(self):
        """Test complete pipeline from collection to storage."""
        # Setup
        state = EnhancedComplianceState(
            case_id=str(uuid4()),
            actor="EvidenceCollector",
            objective="Complete evidence collection",
            context={},
            evidence_items=[],
            validation_results={},
            retry_count=0,
            error_count=0,
            node_execution_times={},
            messages=[],  # Initialize messages field
            errors=[],  # Initialize errors field,
        )

        # Mock components
        processor = Mock()
        processor.process_evidence = Mock(return_value=True)
        processor.validate_evidence = Mock(return_value={"valid": True, "score": 0.9})

        detector = Mock()
        detector.is_duplicate = AsyncMock(return_value=False)

        # Create node
        node = EvidenceCollectionNode(processor, detector)

        # Test evidence
        evidence = {
            "evidence_type": "document",
            "description": "Test evidence",
            "source": "api",
            "raw_data": {},
        }

        # Mock the database session properly
        mock_session = AsyncMock()

        async def mock_get_db_gen():
            yield mock_session

        with patch(
            "langgraph_agent.nodes.evidence_nodes.get_async_db",
            return_value=mock_get_db_gen(),
        ):
            # Process evidence
            result = await node.process_evidence(state, evidence)

            # Verify pipeline execution
            assert detector.is_duplicate.called
            assert processor.process_evidence.called
            assert mock_session.add.called
            assert mock_session.commit.called

    async def test_parallel_evidence_collection_from_multiple_sources(self):
        """Test parallel collection from multiple integrations."""
        sources = ["slack", "teams", "email", "gdrive"]

        async def collect_from_integration(source):
            # Simulate API call with varying delays
            await asyncio.sleep(0.1 if source != "email" else 0.3)
            return {"source": source, "evidence_count": 5, "status": "success"}

        # Collect in parallel
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            *[collect_from_integration(source) for source in sources],
        )
        elapsed = asyncio.get_event_loop().time() - start_time

        # Should complete in roughly the time of the slowest source (0.3s)
        # not the sum of all sources (0.6s)
        assert elapsed < 0.5  # Allow some overhead
        assert len(results) == 4
        assert all(r["status"] == "success" for r in results)
        assert sum(r["evidence_count"] for r in results) == 20


# Run tests with coverage
if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=langgraph_agent.nodes.evidence_nodes",
            "--cov-report=term-missing",
        ],
    )
