"""

# Constants
MINUTE_SECONDS = 60



Comprehensive test suite for compliance nodes.
Tests migration from Celery compliance_tasks to LangGraph nodes.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from langgraph_agent.nodes.compliance_nodes import (
    compliance_check_node,
    extract_requirements_from_rag,
    check_compliance_status,
    assess_compliance_risk,
)
from langgraph_agent.graph.unified_state import UnifiedComplianceState

from tests.test_constants import DEFAULT_LIMIT


class TestComplianceCheckNode:
    """Test suite for compliance_check_node function."""

    @pytest.fixture
    def mock_state(self) -> UnifiedComplianceState:
        """Create a mock state for testing."""
        return {
            "workflow_id": "test-workflow-123",
            "company_id": "company-456",
            "metadata": {"company_id": "company-456", "regulation": "GDPR"},
            "relevant_documents": [
                {
                    "content": "The company must implement data encryption requirements.",
                    "metadata": {"source": "GDPR Article 32", "category": "security"},
                }
            ],
            "compliance_data": {},
            "obligations": [],
            "errors": [],
            "error_count": 0,
            "history": [],
        }

    @pytest.mark.asyncio
    async def test_compliance_check_successful(self, mock_state):
        """Test successful compliance check."""
        with patch("langgraph_agent.nodes.compliance_nodes.check_compliance_status") as mock_check:
            mock_check.return_value = {
                "obligations": [
                    {"id": "1", "title": "Data Encryption", "satisfied": True},
                    {"id": "2", "title": "Data Retention", "satisfied": False},
                ],
                "violations": [{"id": "2", "title": "Data Retention", "satisfied": False}],
                "total_obligations": 2,
                "satisfied_obligations": 1,
                "compliance_score": 50.0,
            }
            result = await compliance_check_node(mock_state)
            assert (result["compliance_data"]["check_results"]["compliance_score"] == 50.0,)
            assert result["compliance_data"]["regulation"] == "GDPR"
            assert "timestamp" in result["compliance_data"]
            assert len(result["obligations"]) == 2
            assert result["metadata"]["notify_required"]
            assert result["metadata"]["violation_count"] == 1
            assert len(result["history"]) == 1

    @pytest.mark.asyncio
    async def test_compliance_check_no_violations(self, mock_state):
        """Test compliance check with no violations."""
        with patch("langgraph_agent.nodes.compliance_nodes.check_compliance_status") as mock_check:
            mock_check.return_value = {
                "obligations": [{"id": "1", "title": "Data Encryption", "satisfied": True}],
                "violations": [],
                "total_obligations": 1,
                "satisfied_obligations": 1,
                "compliance_score": 100.0,
            }
            result = await compliance_check_node(mock_state)
            assert result["compliance_data"]["compliance_score"] == DEFAULT_LIMIT
            assert not result.get("metadata", {}).get("notify_required")
            assert "violation_count" not in result.get("metadata", {})

    @pytest.mark.asyncio
    async def test_compliance_check_missing_company_id(self):
        """Test compliance check with missing company_id."""
        state = {
            "workflow_id": "test-workflow-123",
            "metadata": {"regulation": "GDPR"},
            "compliance_data": {},
            "errors": [],
            "error_count": 0,
            "history": [],
        }
        result = await compliance_check_node(state)
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["type"] == "ValidationError"
        assert "company_id required" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_compliance_check_exception_handling(self, mock_state):
        """Test exception handling in compliance check."""
        with patch("langgraph_agent.nodes.compliance_nodes.check_compliance_status") as mock_check:
            mock_check.side_effect = Exception("Database connection failed")
            with pytest.raises(Exception) as exc_info:
                await compliance_check_node(mock_state)
            assert "Database connection failed" in str(exc_info.value)


class TestExtractRequirements:
    """Test suite for extract_requirements_from_rag function."""

    def test_extract_requirements_with_keywords(self):
        """Test extraction with requirement keywords."""
        documents = [
            {
                "content": "The organization must implement proper access controls.",
                "metadata": {"source": "ISO 27001", "category": "security"},
            },
            {
                "content": "Data retention requirement: 7 years for financial records.",
                "metadata": {"source": "SOX", "category": "retention"},
            },
            {
                "content": "General information about compliance.",
                "metadata": {"source": "Guide", "category": "info"},
            },
        ]
        requirements = extract_requirements_from_rag(documents)
        assert len(requirements) == 2
        assert requirements[0]["source"] == "ISO 27001"
        assert requirements[1]["source"] == "SOX"
        assert all("id" in req for req in requirements)

    def test_extract_requirements_empty_documents(self):
        """Test extraction with empty documents list."""
        requirements = extract_requirements_from_rag([])
        assert requirements == []

    def test_extract_requirements_no_matching_content(self):
        """Test extraction when no requirements found."""
        documents = [
            {"content": "General compliance information.", "metadata": {"source": "Guide"}}
        ]
        requirements = extract_requirements_from_rag(documents)
        assert len(requirements) == 0


class TestCheckComplianceStatus:
    """Test suite for check_compliance_status function."""

    @pytest.mark.asyncio
    async def test_check_compliance_status_successful(self):
        """Test successful compliance status check."""
        mock_records = [
            {
                "o": {"id": "ob1", "title": "Data Protection", "description": "Protect data"},
                "evidence": [{"id": "ev1"}],
            },
            {
                "o": {"id": "ob2", "title": "Data Retention", "description": "Retain data"},
                "evidence": [],
            },
        ]
        with patch(
            "langgraph_agent.nodes.compliance_nodes.get_neo4j_service", new_callable=AsyncMock
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.driver = MagicMock()
            mock_service.execute_query = AsyncMock(return_value=mock_records)
            mock_get_service.return_value = mock_service
            result = await check_compliance_status(
                company_id="company-123", regulation="GDPR", requirements=[]
            )
            assert result["total_obligations"] == 2
            assert result["satisfied_obligations"] == 1
            assert result["compliance_score"] == 50.0
            assert len(result["violations"]) == 1
            assert result["violations"][0]["id"] == "ob2"

    @pytest.mark.asyncio
    async def test_check_compliance_status_all_satisfied(self):
        """Test compliance status when all obligations are satisfied."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_records = [
            {"o": {"id": "ob1", "title": "Data Protection"}, "evidence": [{"id": "ev1"}]},
            {"o": {"id": "ob2", "title": "Data Retention"}, "evidence": [{"id": "ev2"}]},
        ]
        with patch(
            "langgraph_agent.nodes.compliance_nodes.get_neo4j_service", new_callable=AsyncMock
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.driver = MagicMock()
            mock_service.execute_query = AsyncMock(return_value=mock_records)
            mock_get_service.return_value = mock_service
            result = await check_compliance_status(
                company_id="company-123", regulation="GDPR", requirements=[]
            )
            assert result["compliance_score"] == DEFAULT_LIMIT
            assert len(result["violations"]) == 0

    @pytest.mark.asyncio
    async def test_check_compliance_status_database_error(self):
        """Test handling of database errors."""
        with patch(
            "langgraph_agent.nodes.compliance_nodes.get_neo4j_service", new_callable=AsyncMock
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.driver = None
            mock_get_service.return_value = mock_service
            result = await check_compliance_status(
                company_id="company-123", regulation="GDPR", requirements=[]
            )
            assert result["compliance_score"] == 0
            assert "error" in result
            assert "Database service not available" in result["error"]


class TestAssessComplianceRisk:
    """Test suite for assess_compliance_risk function."""

    @pytest.mark.asyncio
    async def test_assess_risk_no_violations(self):
        """Test risk assessment with no violations."""
        state = {"compliance_data": {"check_results": {"violations": []}}}
        result = await assess_compliance_risk(state)
        assert result["compliance_data"]["risk_assessment"]["score"] == 0
        assert result["compliance_data"]["risk_assessment"]["level"] == "LOW"
        assert result["compliance_data"]["risk_assessment"]["violation_count"] == 0

    @pytest.mark.asyncio
    async def test_assess_risk_low_level(self):
        """Test risk assessment with low risk level."""
        state = {"compliance_data": {"check_results": {"violations": [{"id": "1"}]}}}
        result = await assess_compliance_risk(state)
        assert result["compliance_data"]["risk_assessment"]["score"] == 20
        assert result["compliance_data"]["risk_assessment"]["level"] == "LOW"

    @pytest.mark.asyncio
    async def test_assess_risk_medium_level(self):
        """Test risk assessment with medium risk level."""
        state = {
            "compliance_data": {"check_results": {"violations": [{"id": str(i)} for i in range(2)]}}
        }
        result = await assess_compliance_risk(state)
        assert result["compliance_data"]["risk_assessment"]["score"] == 40
        assert result["compliance_data"]["risk_assessment"]["level"] == "MEDIUM"

    @pytest.mark.asyncio
    async def test_assess_risk_high_level(self):
        """Test risk assessment with high risk level."""
        state = {
            "compliance_data": {"check_results": {"violations": [{"id": str(i)} for i in range(3)]}}
        }
        result = await assess_compliance_risk(state)
        assert result["compliance_data"]["risk_assessment"]["score"] == MINUTE_SECONDS
        assert result["compliance_data"]["risk_assessment"]["level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_assess_risk_critical_level(self):
        """Test risk assessment with critical risk level."""
        state = {
            "compliance_data": {"check_results": {"violations": [{"id": str(i)} for i in range(4)]}}
        }
        result = await assess_compliance_risk(state)
        assert result["compliance_data"]["risk_assessment"]["score"] == 80
        assert result["compliance_data"]["risk_assessment"]["level"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_assess_risk_capped_at_100(self):
        """Test risk score is capped at 100."""
        state = {
            "compliance_data": {
                "check_results": {"violations": [{"id": str(i)} for i in range(10)]}
            }
        }
        result = await assess_compliance_risk(state)
        assert result["compliance_data"]["risk_assessment"]["score"] == DEFAULT_LIMIT
        assert result["compliance_data"]["risk_assessment"]["level"] == "CRITICAL"


class TestIntegration:
    """Integration tests for compliance workflow."""

    @pytest.mark.asyncio
    async def test_full_compliance_workflow(self):
        """Test complete compliance workflow from check to risk assessment."""
        initial_state = {
            "workflow_id": "integration-test",
            "company_id": "test-company",
            "metadata": {"regulation": "GDPR"},
            "relevant_documents": [
                {
                    "content": "Must implement data protection requirements.",
                    "metadata": {"source": "GDPR"},
                }
            ],
            "compliance_data": {},
            "obligations": [],
            "errors": [],
            "error_count": 0,
            "history": [],
        }
        with patch("langgraph_agent.nodes.compliance_nodes.check_compliance_status") as mock_check:
            mock_check.return_value = {
                "obligations": [
                    {"id": "1", "title": "Obligation 1", "satisfied": False},
                    {"id": "2", "title": "Obligation 2", "satisfied": False},
                ],
                "violations": [
                    {"id": "1", "title": "Obligation 1", "satisfied": False},
                    {"id": "2", "title": "Obligation 2", "satisfied": False},
                ],
                "total_obligations": 2,
                "satisfied_obligations": 0,
                "compliance_score": 0.0,
            }
            state_after_check = await compliance_check_node(initial_state)
            final_state = await assess_compliance_risk(state_after_check)
            assert final_state["compliance_data"]["compliance_score"] == 0.0
            assert (final_state["compliance_data"]["risk_assessment"]["level"] == "MEDIUM",)
            assert final_state["metadata"]["notify_required"]
            assert len(final_state["history"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
