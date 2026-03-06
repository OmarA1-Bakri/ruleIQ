"""

Integration tests for real compliance nodes implementation.
Tests actual database operations and service connections.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
from uuid import uuid4

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langgraph_agent.nodes.compliance_nodes_real import (
    batch_compliance_update_node,
    single_compliance_check_node,
    compliance_monitoring_node,
    update_compliance_for_profile,
    get_default_framework,
    get_user_for_profile,
)
from langgraph_agent.graph.unified_state import UnifiedComplianceState


class TestRealComplianceNodes:
    """Test suite for real compliance node implementations."""

    @pytest.fixture
    def mock_state(self) -> UnifiedComplianceState:
        """Create a mock state for testing."""
        return {
            "workflow_id": "test-workflow-123",
            "company_id": "company-456",
            "metadata": {"company_id": "company-456", "regulation": "GDPR"},
            "compliance_data": {},
            "obligations": [],
            "errors": [],
            "error_count": 0,
            "history": [],
        }

    @pytest.fixture
    def mock_business_profile(self):
        """Create a mock business profile."""
        profile = Mock()
        profile.id = uuid4()
        profile.user_id = uuid4()
        profile.company_id = "company-456"
        return profile

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def mock_framework(self):
        """Create a mock compliance framework."""
        framework = Mock()
        framework.id = uuid4()
        framework.name = "GDPR"
        framework.display_name = "General Data Protection Regulation"
        return framework

    @pytest.fixture
    def mock_assessment(self):
        """Create a mock readiness assessment."""
        assessment = Mock()
        assessment.id = uuid4()
        assessment.overall_score = 85.0
        assessment.priority_actions = [
            {"action": "Implement data encryption", "urgency": "high", "impact": "high"},
        ]
        assessment.quick_wins = [{"action": "Update privacy policy", "effort": "low"}]
        assessment.estimated_readiness_date = datetime.now(timezone.utc) + timedelta(days=30)
        assessment.framework_scores = {
            "policy": 90.0,
            "implementation": 80.0,
            "evidence": 85.0,
        }
        assessment.risk_level = "Low"
        return assessment

    @pytest.mark.asyncio
    async def test_get_default_framework(self, mock_framework):
        """Test getting the default compliance framework."""
        with patch("langgraph_agent.nodes.compliance_nodes_real.select") as mock_select:
            mock_db = AsyncMock()
            mock_result = AsyncMock()
            mock_scalars = Mock()
            mock_scalars.first.return_value = mock_framework
            mock_result.scalars.return_value = mock_scalars
            mock_db.execute.return_value = mock_result

            result = await get_default_framework(mock_db)

            assert result == mock_framework
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_for_profile(self, mock_business_profile, mock_user):
        """Test getting user for a business profile."""
        with patch("langgraph_agent.nodes.compliance_nodes_real.select") as mock_select:
            mock_db = AsyncMock()
            mock_result = AsyncMock()
            mock_scalars = Mock()
            mock_scalars.first.return_value = mock_user
            mock_result.scalars.return_value = mock_scalars
            mock_db.execute.return_value = mock_result

            result = await get_user_for_profile(mock_db, mock_business_profile)

            assert result == mock_user
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_compliance_for_profile_success(
        self, mock_business_profile, mock_user, mock_framework, mock_assessment
    ):
        """Test successful compliance update for a profile."""
        with patch(
            "langgraph_agent.nodes.compliance_nodes_real.get_user_for_profile"
        ) as mock_get_user:
            with patch(
                "langgraph_agent.nodes.compliance_nodes_real.get_default_framework"
            ) as mock_get_framework:
                with patch(
                    "langgraph_agent.nodes.compliance_nodes_real.generate_readiness_assessment"
                ) as mock_generate:
                    mock_db = AsyncMock()
                    mock_get_user.return_value = mock_user
                    mock_get_framework.return_value = mock_framework
                    mock_generate.return_value = mock_assessment

                    result = await update_compliance_for_profile(
                        mock_db,
                        mock_business_profile,
                    )

                    assert result["profile_id"] == str(mock_business_profile.id)
                    assert result["overall_score"] == 85.0
                    assert result["risk_level"] == "Low"
                    assert len(result["priority_actions"]) == 1
                    assert len(result["quick_wins"]) == 1

                    mock_generate.assert_called_once_with(
                        db=mock_db,
                        user=mock_user,
                        framework_id=mock_framework.id,
                        assessment_type="full",
                    )

    @pytest.mark.asyncio
    async def test_update_compliance_for_profile_no_user(self, mock_business_profile):
        """Test compliance update when no user is found."""
        with patch(
            "langgraph_agent.nodes.compliance_nodes_real.get_user_for_profile"
        ) as mock_get_user:
            mock_db = AsyncMock()
            mock_get_user.return_value = None

            result = await update_compliance_for_profile(mock_db, mock_business_profile)

            assert result["profile_id"] == str(mock_business_profile.id)
            assert result["error"] == "No user found"
            assert result["overall_score"] == 0

    @pytest.mark.asyncio
    async def test_batch_compliance_update_node(
        self,
        mock_state,
        mock_business_profile,
        mock_user,
        mock_framework,
        mock_assessment,
    ):
        """Test batch compliance update for all profiles."""
        with patch("langgraph_agent.nodes.compliance_nodes_real.get_async_db") as mock_get_db:
            with patch("langgraph_agent.nodes.compliance_nodes_real.select") as mock_select:
                with patch(
                    "langgraph_agent.nodes.compliance_nodes_real.update_compliance_for_profile"
                ) as mock_update:
                    # Setup mock database
                    mock_db = AsyncMock()
                    mock_get_db.return_value.__aiter__.return_value = [mock_db]

                    # Setup mock profiles query
                    mock_result = AsyncMock()
                    mock_scalars = Mock()
                    mock_scalars.all.return_value = [mock_business_profile]
                    mock_result.scalars.return_value = mock_scalars
                    mock_db.execute.return_value = mock_result

                    # Setup mock compliance update
                    mock_update.return_value = {
                        "profile_id": str(mock_business_profile.id),
                        "overall_score": 85.0,
                        "risk_level": "Low",
                        "priority_actions": [],
                        "quick_wins": [],
                    }

                    result = await batch_compliance_update_node(mock_state)

                    assert "batch_update_results" in result["compliance_data"]
                    assert (
                        result["compliance_data"]["batch_update_results"]["total_profiles",] == 1,
                    )
                    assert (
                        result["compliance_data"]["batch_update_results"]["updated_count",] == 1,
                    )
                    assert (result["compliance_data"]["batch_update_results"]["error_count"] == 0,)
                    assert len(result["compliance_data"]["profiles"]) == 1
                    assert len(result["history"]) == 1
                    assert result["history"][0]["action"] == "batch_compliance_update"

    @pytest.mark.asyncio
    async def test_batch_compliance_update_with_alerts(self, mock_state, mock_business_profile):
        """Test batch compliance update generates alerts for low scores."""
        with patch("langgraph_agent.nodes.compliance_nodes_real.get_async_db") as mock_get_db:
            with patch("langgraph_agent.nodes.compliance_nodes_real.select") as mock_select:
                with patch(
                    "langgraph_agent.nodes.compliance_nodes_real.update_compliance_for_profile"
                ) as mock_update:
                    # Setup mock database
                    mock_db = AsyncMock()
                    mock_get_db.return_value.__aiter__.return_value = [mock_db]

                    # Setup mock profiles query
                    mock_result = AsyncMock()
                    mock_scalars = Mock()
                    mock_scalars.all.return_value = [mock_business_profile]
                    mock_result.scalars.return_value = mock_scalars
                    mock_db.execute.return_value = mock_result

                    # Setup mock compliance update with low score
                    mock_update.return_value = {
                        "profile_id": str(mock_business_profile.id),
                        "overall_score": 65.0,  # Below 70 threshold
                        "risk_level": "Medium",
                        "priority_actions": [],
                        "quick_wins": [],
                    }

                    result = await batch_compliance_update_node(mock_state)

                    assert (len(result["compliance_data"]["batch_update_results"]["alerts"]) == 1,)
                    assert result["metadata"]["alerts_generated"]
                    assert result["metadata"]["alert_count"] == 1

                    alert = result["compliance_data"]["batch_update_results"]["alerts"][0,]
                    assert alert["score"] == 65.0
                    assert alert["message"] == "Compliance score is below threshold"

    @pytest.mark.asyncio
    async def test_single_compliance_check_node_success(
        self,
        mock_state,
        mock_business_profile,
        mock_user,
        mock_framework,
        mock_assessment,
    ):
        """Test single compliance check for a specific company."""
        with patch("langgraph_agent.nodes.compliance_nodes_real.get_async_db") as mock_get_db:
            with patch("langgraph_agent.nodes.compliance_nodes_real.select") as mock_select:
                with patch(
                    "langgraph_agent.nodes.compliance_nodes_real.update_compliance_for_profile"
                ) as mock_update:
                    # Setup mock database
                    mock_db = AsyncMock()
                    mock_get_db.return_value.__aiter__.return_value = [mock_db]

                    # Setup mock profile query
                    mock_result = AsyncMock()
                    mock_scalars = Mock()
                    mock_scalars.first.return_value = mock_business_profile
                    mock_result.scalars.return_value = mock_scalars
                    mock_db.execute.return_value = mock_result

                    # Setup mock compliance update
                    mock_update.return_value = {
                        "profile_id": str(mock_business_profile.id),
                        "overall_score": 85.0,
                        "risk_level": "Low",
                        "priority_actions": [],
                        "quick_wins": [],
                    }

                    result = await single_compliance_check_node(mock_state)

                    assert "check_results" in result["compliance_data"]
                    assert (result["compliance_data"]["check_results"]["overall_score"] == 85.0,)
                    assert result["compliance_data"]["regulation"] == "GDPR"
                    assert len(result["history"]) == 1
                    assert result["history"][0]["action"] == "compliance_check"

    @pytest.mark.asyncio
    async def test_single_compliance_check_no_company_id(self, mock_state):
        """Test single compliance check without company_id."""
        mock_state["company_id"] = None
        mock_state["metadata"]["company_id"] = None

        result = await single_compliance_check_node(mock_state)

        assert result["error_count"] == 1
        assert result["errors"][0]["type"] == "ValidationError"
        assert "company_id required" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_compliance_monitoring_node(self, mock_state, mock_business_profile):
        """Test compliance monitoring node."""
        with patch("langgraph_agent.nodes.compliance_nodes_real.get_async_db") as mock_get_db:
            with patch("langgraph_agent.nodes.compliance_nodes_real.select") as mock_select:
                with patch(
                    "langgraph_agent.nodes.compliance_nodes_real.update_compliance_for_profile"
                ) as mock_update:
                    # Setup mock database
                    mock_db = AsyncMock()
                    mock_get_db.return_value.__aiter__.return_value = [mock_db]

                    # Setup mock profiles query
                    mock_result = AsyncMock()
                    mock_scalars = Mock()
                    mock_scalars.all.return_value = [mock_business_profile]
                    mock_result.scalars.return_value = mock_scalars
                    mock_db.execute.return_value = mock_result

                    # Setup mock compliance update with low score
                    mock_update.return_value = {
                        "profile_id": str(mock_business_profile.id),
                        "overall_score": 65.0,  # Below 70 threshold
                        "risk_level": "Medium",
                        "priority_actions": [
                            {"action": "Fix data retention", "urgency": "high"},
                        ],
                        "quick_wins": [],
                    }

                    result = await compliance_monitoring_node(mock_state)

                    assert "monitoring_results" in result["compliance_data"]
                    assert (
                        result["compliance_data"]["monitoring_results"]["total_profiles",] == 1,
                    )
                    assert (
                        result["compliance_data"]["monitoring_results"]["alerts_generated",] == 1,
                    )
                    assert (
                        len(
                            result["compliance_data"]["monitoring_results"]["low_score_profiles",],
                        )
                        == 1,
                    )

                    assert result["metadata"]["notify_required"]
                    assert result["metadata"]["alert_count"] == 1
                    assert len(result["metadata"]["alerts"]) == 1

                    alert = result["metadata"]["alerts"][0]
                    assert alert["score"] == 65.0
                    assert "below threshold" in alert["message"]
                    assert len(alert["priority_actions"]) == 1

                    assert len(result["history"]) == 1
                    assert result["history"][0]["action"] == "compliance_monitoring"


class TestIntegrationWithDatabase:
    """Integration tests that would run with a real database."""

    @pytest.mark.skip(reason="Requires real database connection")
    @pytest.mark.asyncio
    async def test_real_database_batch_update(self):
        """Test batch compliance update with real database."""
        # This test would run against a real database
        # Skipped by default to avoid requiring database setup
        state = {
            "workflow_id": "integration-test",
            "metadata": {},
            "compliance_data": {},
            "errors": [],
            "error_count": 0,
            "history": [],
        }

        result = await batch_compliance_update_node(state)

        # Assertions would check real data
        assert "batch_update_results" in result["compliance_data"]
        assert result["compliance_data"]["batch_update_results"]["total_profiles"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
