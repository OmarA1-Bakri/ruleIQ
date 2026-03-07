"""
Integration tests for LangGraph implementation with golden datasets.

This test suite verifies:
1. LangGraph workflow initialization and execution
2. Golden dataset loading and versioning
3. IQ Agent integration with Neo4j
4. Complete workflow from query to response
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# Test imports
from services.iq_agent import IQComplianceAgent, IQAgentState, create_iq_agent
from services.ai.evaluation.golden_datasets.loaders import (
    GoldenDatasetLoader,
    JSONLLoader,
    DatasetRegistry,
)
from services.ai.evaluation.schemas import ComplianceScenario, EvidenceCase, RegulatoryQAPair


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service for testing."""
    service = AsyncMock()
    service.execute_query = AsyncMock(
        return_value={
            "data": [
                {
                    "regulation": "GDPR",
                    "requirements": [
                        {"id": "req-1", "title": "Data Protection", "risk_level": "HIGH"}
                    ],
                }
            ]
        }
    )
    return service


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=Mock(content="This is a compliance guidance response."))
    return llm


@pytest.fixture
def golden_dataset_path(tmp_path):
    """Create temporary golden dataset structure."""
    dataset_dir = tmp_path / "golden_datasets"
    dataset_dir.mkdir()

    # Create v1.0.0 directory
    version_dir = dataset_dir / "v1.0.0"
    version_dir.mkdir()

    # Create sample dataset
    dataset_file = version_dir / "dataset.jsonl"
    sample_data = [
        {
            "type": "compliance_scenario",
            "data": {
                "scenario_id": "test-scenario-1",
                "description": "GDPR compliance test",
                "expected_compliance": True,
                "regulations": ["GDPR"],
                "tags": ["privacy", "data_protection"],
            },
        },
        {
            "type": "regulatory_qa",
            "data": {
                "qa_id": "test-qa-1",
                "question": "What are GDPR requirements?",
                "expected_answer": "GDPR requires data protection.",
                "regulation": "GDPR",
                "confidence_threshold": 0.8,
            },
        },
    ]

    with open(dataset_file, "w") as f:
        for item in sample_data:
            f.write(json.dumps(item) + "\n")

    # Create metadata
    metadata_file = version_dir / "metadata.json"
    metadata = {
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "test",
        "description": "Test golden dataset",
        "dataset_counts": {"compliance_scenarios": 1, "regulatory_qa": 1},
    }
    with open(metadata_file, "w") as f:
        json.dump(metadata, f)

    return dataset_dir


class TestLangGraphWorkflow:
    """Test LangGraph workflow integration."""

    @pytest.mark.asyncio
    async def test_iq_agent_initialization(self, mock_neo4j_service):
        """Test IQ agent can be initialized with dependencies."""
        agent = IQComplianceAgent(
            neo4j_service=mock_neo4j_service, postgres_session=None, llm_model="gpt-4"
        )

        assert agent is not None
        assert agent.neo4j == mock_neo4j_service
        assert agent.workflow is not None
        assert agent.memory_manager is not None

    @pytest.mark.asyncio
    async def test_workflow_execution(self, mock_neo4j_service, mock_llm):
        """Test complete workflow execution."""
        agent = IQComplianceAgent(neo4j_service=mock_neo4j_service, postgres_session=None)
        agent.llm = mock_llm

        # Execute query
        result = await agent.process_query(
            user_query="What are GDPR requirements?", context={"test": True}
        )

        assert result["status"] == "success"
        assert "summary" in result
        assert "artifacts" in result
        assert "llm_response" in result
        assert result["llm_response"] == "This is a compliance guidance response."

    @pytest.mark.asyncio
    async def test_perceive_node(self, mock_neo4j_service):
        """Test the perceive node in workflow."""
        agent = IQComplianceAgent(neo4j_service=mock_neo4j_service, postgres_session=None)

        state = IQAgentState(
            current_query="Check GDPR compliance",
            graph_context={},
            compliance_posture={},
            risk_assessment={},
            action_plan=[],
            evidence_collected=[],
            memories_accessed=[],
            patterns_detected=[],
            messages=[],
        )

        # Mock the compliance query execution
        with patch("services.iq_agent.execute_compliance_query") as mock_exec:
            mock_exec.return_value = Mock(
                data={"coverage": 0.85}, metadata={"overall_coverage": 0.85, "total_gaps": 3}
            )

            updated_state = await agent._perceive_node(state)

            assert "coverage_analysis" in updated_state.graph_context
            assert updated_state.compliance_posture["overall_coverage"] == 0.85
            assert updated_state.compliance_posture["total_gaps"] == 3


class TestGoldenDatasets:
    """Test golden dataset functionality."""

    def test_jsonl_loader(self, tmp_path):
        """Test JSONL file loading and saving."""
        file_path = tmp_path / "test.jsonl"
        loader = JSONLLoader(str(file_path))

        # Test save
        data = [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
        loader.save(data)

        # Test load
        loaded_data = loader.load()
        assert len(loaded_data) == 2
        assert loaded_data[0]["id"] == 1
        assert loaded_data[1]["name"] == "test2"

    def test_golden_dataset_loader(self, golden_dataset_path):
        """Test golden dataset loader with versions."""
        loader = GoldenDatasetLoader(str(golden_dataset_path))

        # Load latest version
        data = loader.load_latest()
        assert len(data) == 2
        assert data[0]["type"] == "compliance_scenario"
        assert data[1]["type"] == "regulatory_qa"

        # Parse dataset
        parsed = loader.parse_dataset(data)
        assert len(parsed["compliance_scenarios"]) == 1
        assert len(parsed["regulatory_qa"]) == 1
        assert parsed["evidence_cases"] == []

    def test_dataset_registry(self, golden_dataset_path):
        """Test dataset registry management."""
        registry = DatasetRegistry()

        # Register dataset
        registry.register_dataset(
            name="test_dataset", path=str(golden_dataset_path), version="1.0.0"
        )

        assert "test_dataset" in registry.datasets
        assert registry.datasets["test_dataset"]["path"] == str(golden_dataset_path)

        # Load dataset through registry
        loader = registry.loaders["test_dataset"]
        data = loader.load_latest()
        assert len(data) == 2


class TestIntegrationWithAPI:
    """Test integration with API endpoints."""

    @pytest.mark.asyncio
    async def test_iq_agent_api_integration(self, mock_neo4j_service):
        """Test IQ agent can be created and used in API context."""
        with patch("services.iq_agent.Neo4jGraphRAGService") as mock_neo4j_class:
            mock_neo4j_class.return_value = mock_neo4j_service

            # Test agent creation
            agent = await create_iq_agent(mock_neo4j_service)
            assert agent is not None
            assert isinstance(agent, IQComplianceAgent)

    @pytest.mark.asyncio
    async def test_langgraph_state_management(self, mock_neo4j_service):
        """Test LangGraph state management through workflow."""
        agent = IQComplianceAgent(neo4j_service=mock_neo4j_service, postgres_session=None)

        # Create initial state
        initial_state = IQAgentState(
            current_query="Test query",
            graph_context={},
            compliance_posture={},
            risk_assessment={},
            action_plan=[],
            evidence_collected=[],
            memories_accessed=[],
            patterns_detected=[],
            messages=[],
            step_count=0,
        )

        # Verify state fields
        assert initial_state.current_query == "Test query"
        assert initial_state.step_count == 0
        assert initial_state.max_steps == 10
        assert len(initial_state.messages) == 0


class TestGoldenDatasetIntegration:
    """Test golden dataset integration with evaluation system."""

    def test_golden_dataset_structure(self, golden_dataset_path):
        """Verify golden dataset structure matches expected format."""
        loader = GoldenDatasetLoader(str(golden_dataset_path))
        data = loader.load_version("1.0.0")

        # Check structure
        for item in data:
            assert "type" in item
            assert "data" in item
            assert item["type"] in ["compliance_scenario", "regulatory_qa", "evidence_case"]

    def test_sample_golden_dataset_exists(self):
        """Verify sample golden dataset file exists."""
        sample_path = Path("services/ai/evaluation/data/sample_golden_dataset.json")
        assert sample_path.exists(), "Sample golden dataset should exist"

        # Load and verify structure
        with open(sample_path) as f:
            data = json.load(f)

        assert "documents" in data
        assert len(data["documents"]) > 0

        # Check document structure
        for doc in data["documents"]:
            assert "doc_id" in doc
            assert "content" in doc
            assert "source_meta" in doc
            assert "reg_citations" in doc
            assert "expected_outcomes" in doc


@pytest.mark.asyncio
async def test_end_to_end_workflow():
    """Test complete end-to-end workflow with mocked dependencies."""
    # Setup mocks
    mock_neo4j = AsyncMock()
    mock_neo4j.execute_query = AsyncMock(
        return_value={
            "data": [
                {
                    "regulation": "ISO 27001",
                    "requirements": [
                        {"id": "iso-1", "title": "Access Control", "risk_level": "MEDIUM"}
                    ],
                }
            ]
        }
    )

    # Create agent
    agent = IQComplianceAgent(neo4j_service=mock_neo4j, postgres_session=None)

    # Mock LLM response
    with patch.object(agent.llm, "ainvoke") as mock_llm:
        mock_llm.return_value = Mock(
            content="Based on ISO 27001, you need to implement access controls."
        )

        # Process query
        result = await agent.process_query(
            user_query="What are ISO 27001 access control requirements?"
        )

        # Verify result
        assert result["status"] == "success"
        assert "ISO 27001" in str(result["artifacts"]["compliance_data"])
        assert "access control" in result["llm_response"].lower()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
