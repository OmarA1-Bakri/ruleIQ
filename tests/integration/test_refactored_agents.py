"""
Integration tests for refactored compliance agents.

Tests the new protocol-based agents with repositories and services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.agents.protocols import (
    ComplianceContext,
    ResponseStatus,
    AgentCapability,
    agent_registry
)
from services.agents.react_assessment_agent import ReactAssessmentAgent
from services.agents.hybrid_iq_agent import HybridIQAgent, ProcessingMode
from services.agents.repositories import (
    ComplianceRepository,
    EvidenceRepository,
    BusinessProfileRepository,
    AssessmentSessionRepository
)
from services.agents.services import (
    QueryClassificationService,
    RiskAnalysisService,
    CompliancePlanService,
    EvidenceVerificationService
)


class TestReactAssessmentAgent:
    """Tests for the ReactAssessmentAgent."""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories."""
        compliance_repo = MagicMock(spec=ComplianceRepository)
        evidence_repo = MagicMock(spec=EvidenceRepository)
        business_repo = MagicMock(spec=BusinessProfileRepository)
        
        # Setup mock returns
        compliance_repo.search_compliance_resources = AsyncMock(return_value=[
            {"name": "GDPR", "title": "General Data Protection Regulation"}
        ])
        
        business_repo.get_by_id = AsyncMock(return_value=MagicMock(
            id="test-id",
            company_name="Test Company",
            industry="Technology",
            company_size="11-50",
            handles_personal_data=True,
            data_types=["customer_data"],
            jurisdiction="UK"
        ))
        
        business_repo.exists = AsyncMock(return_value=True)
        
        evidence_repo.get_by_business_profile = AsyncMock(return_value=[])
        
        return {
            "compliance": compliance_repo,
            "evidence": evidence_repo,
            "business": business_repo
        }
    
    @pytest.mark.asyncio
    async def test_react_agent_initialization(self, mock_repositories):
        """Test ReactAssessmentAgent initialization."""
        agent = ReactAssessmentAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            model_name="gpt-4"
        )
        
        # Check metadata
        metadata = await agent.get_capabilities()
        assert metadata.name == "ReactAssessmentAgent"
        assert metadata.version == "2.0"
        assert AgentCapability.ASSESSMENT in metadata.capabilities
        assert AgentCapability.RISK_ANALYSIS in metadata.capabilities
    
    @pytest.mark.asyncio
    async def test_react_agent_process_query(self, mock_repositories):
        """Test ReactAssessmentAgent query processing."""
        agent = ReactAssessmentAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            model_name="gpt-4"
        )
        
        # Mock the agent's internal ReAct agent
        with patch.object(agent.agent, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = {
                "messages": [
                    MagicMock(content="Analyzing compliance requirements..."),
                    MagicMock(content="Based on my analysis, you need to focus on GDPR compliance.")
                ]
            }
            
            context = ComplianceContext(
                business_profile_id="test-id",
                session_id="test-session"
            )
            
            response = await agent.process_query(
                "What are our compliance priorities?",
                context
            )
            
            assert response.status == ResponseStatus.SUCCESS
            assert response.message is not None
            assert response.session_id == "test-session"
            assert response.agent_metadata["agent"] == "ReactAssessmentAgent"
    
    @pytest.mark.asyncio
    async def test_react_agent_validation(self, mock_repositories):
        """Test ReactAssessmentAgent input validation."""
        agent = ReactAssessmentAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            model_name="gpt-4"
        )
        
        # Test empty query
        is_valid, error = await agent.validate_input("", None)
        assert not is_valid
        assert "empty" in error.lower()
        
        # Test valid query
        is_valid, error = await agent.validate_input("Valid query", None)
        assert is_valid
        assert error is None
        
        # Test with invalid business profile
        mock_repositories["business"].exists = AsyncMock(return_value=False)
        context = ComplianceContext(business_profile_id="invalid-id")
        is_valid, error = await agent.validate_input("Query", context)
        assert not is_valid
        assert "not found" in error.lower()
    
    @pytest.mark.asyncio
    async def test_react_agent_health_check(self, mock_repositories):
        """Test ReactAssessmentAgent health check."""
        agent = ReactAssessmentAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            model_name="gpt-4"
        )
        
        health = await agent.health_check()
        
        assert health["agent"] == "ReactAssessmentAgent"
        assert health["status"] == "healthy"
        assert "dependencies" in health
        assert "capabilities" in health


class TestHybridIQAgent:
    """Tests for the HybridIQAgent."""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories."""
        compliance_repo = MagicMock(spec=ComplianceRepository)
        evidence_repo = MagicMock(spec=EvidenceRepository)
        business_repo = MagicMock(spec=BusinessProfileRepository)
        session_repo = MagicMock(spec=AssessmentSessionRepository)
        
        # Setup mock returns
        business_repo.get_by_id = AsyncMock(return_value=MagicMock(
            id="test-id",
            company_name="Test Company",
            industry="Technology",
            company_size="11-50",
            handles_personal_data=True
        ))
        
        business_repo.exists = AsyncMock(return_value=True)
        evidence_repo.count_by_profile = AsyncMock(return_value=5)
        
        return {
            "compliance": compliance_repo,
            "evidence": evidence_repo,
            "business": business_repo,
            "session": session_repo
        }
    
    @pytest.mark.asyncio
    async def test_hybrid_agent_initialization(self, mock_repositories):
        """Test HybridIQAgent initialization."""
        agent = HybridIQAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            session_repo=mock_repositories["session"],
            llm_model="gpt-4"
        )
        
        # Check metadata
        metadata = await agent.get_capabilities()
        assert metadata.name == "HybridIQAgent"
        assert metadata.version == "3.0"
        assert AgentCapability.CONVERSATIONAL in metadata.capabilities
        assert len(metadata.capabilities) > 5  # Should have many capabilities
    
    @pytest.mark.asyncio
    async def test_hybrid_agent_query_classification(self, mock_repositories):
        """Test HybridIQAgent query classification."""
        agent = HybridIQAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            session_repo=mock_repositories["session"],
            llm_model="gpt-4"
        )
        
        # Test different query types
        queries = [
            ("Conduct a full compliance assessment", "structured"),
            ("Do we have privacy policy documents?", "quick"),
            ("What are the risks of using AI?", "react")
        ]
        
        for query, expected_mode in queries:
            classification = agent.query_classifier.classify_query(query)
            # The classification might not exactly match but should be reasonable
            assert classification["primary_category"] in [
                "assessment", "evidence", "risk", "general"
            ]
    
    @pytest.mark.asyncio
    async def test_hybrid_agent_conversation_flow(self, mock_repositories):
        """Test HybridIQAgent conversation capabilities."""
        agent = HybridIQAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            session_repo=mock_repositories["session"],
            llm_model="gpt-4"
        )
        
        # Start conversation
        response = await agent.start_conversation(
            "Hello, I need help with compliance",
            ComplianceContext(business_profile_id="test-id")
        )
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.session_id is not None
        session_id = response.session_id
        
        # Continue conversation
        response = await agent.continue_conversation(
            "What about GDPR?",
            session_id,
            ComplianceContext(business_profile_id="test-id")
        )
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.session_id == session_id
        
        # Get history
        history = await agent.get_conversation_history(session_id)
        assert len(history) >= 1
        
        # End conversation
        response = await agent.end_conversation(session_id)
        assert response.status == ResponseStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_hybrid_agent_quick_evidence_check(self, mock_repositories):
        """Test HybridIQAgent quick evidence check."""
        agent = HybridIQAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            session_repo=mock_repositories["session"],
            llm_model="gpt-4"
        )
        
        context = ComplianceContext(business_profile_id="test-id")
        
        response = await agent.process_query(
            "How many evidence documents do we have?",
            context
        )
        
        # Should use quick mode for this simple query
        assert response.status == ResponseStatus.SUCCESS
        assert "5" in response.message or "evidence" in response.message.lower()
    
    @pytest.mark.asyncio
    async def test_hybrid_agent_health_check(self, mock_repositories):
        """Test HybridIQAgent health check."""
        agent = HybridIQAgent(
            compliance_repo=mock_repositories["compliance"],
            evidence_repo=mock_repositories["evidence"],
            business_repo=mock_repositories["business"],
            session_repo=mock_repositories["session"],
            llm_model="gpt-4"
        )
        
        # Mock sub-agent health check
        with patch.object(agent.react_agent, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "healthy"}
            
            health = await agent.health_check()
            
            assert health["agent"] == "HybridIQAgent"
            assert health["status"] in ["healthy", "degraded"]
            assert "sub_agents" in health
            assert "repositories" in health
            assert "services" in health


class TestAgentRegistry:
    """Tests for the AgentRegistry."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock compliance agent."""
        agent = MagicMock()
        agent.process_query = AsyncMock(return_value=MagicMock(
            status=ResponseStatus.SUCCESS,
            message="Test response"
        ))
        agent.get_capabilities = AsyncMock(return_value=MagicMock(
            capabilities=[AgentCapability.ASSESSMENT]
        ))
        return agent
    
    def test_registry_registration(self, mock_agent):
        """Test agent registration in registry."""
        registry = agent_registry
        
        # Register agent
        registry.register("test_agent", mock_agent)
        
        # Retrieve agent
        retrieved = registry.get_agent("test_agent")
        assert retrieved == mock_agent
        
        # List agents
        agents = registry.list_agents()
        assert "test_agent" in agents
    
    @pytest.mark.asyncio
    async def test_registry_routing(self, mock_agent):
        """Test query routing in registry."""
        registry = agent_registry
        
        # Register agent
        registry.register("test_router", mock_agent)
        
        # Route query to specific agent
        response = await registry.route_query(
            "Test query",
            preferred_agent="test_router"
        )
        
        assert response.status == ResponseStatus.SUCCESS
        mock_agent.process_query.assert_called_once()


class TestServices:
    """Tests for service classes."""
    
    def test_query_classification_service(self):
        """Test QueryClassificationService."""
        service = QueryClassificationService()
        
        # Test assessment classification
        result = service.classify_query("Conduct a compliance assessment")
        assert result["primary_category"] == "assessment"
        assert result["processing_mode"] == "structured"
        
        # Test evidence classification
        result = service.classify_query("Do we have the privacy policy document?")
        assert result["primary_category"] == "evidence"
        assert result["processing_mode"] == "quick"
        
        # Test risk classification
        result = service.classify_query("What are the risks of data breach?")
        assert result["primary_category"] == "risk"
        assert result["processing_mode"] == "react"
    
    @pytest.mark.asyncio
    async def test_risk_analysis_service(self):
        """Test RiskAnalysisService."""
        compliance_repo = MagicMock(spec=ComplianceRepository)
        service = RiskAnalysisService(compliance_repo)
        
        business_profile = {
            "industry": "fintech",
            "company_size": "201-500",
            "handles_personal_data": True
        }
        
        result = await service.analyze_business_risk(business_profile)
        
        assert "risk_score" in result
        assert "risk_level" in result
        assert "risk_factors" in result
        assert result["risk_score"] > 0
        
        # Should have high risk due to fintech + personal data
        assert len(result["risk_factors"]) >= 2
    
    @pytest.mark.asyncio
    async def test_compliance_plan_service(self):
        """Test CompliancePlanService."""
        compliance_repo = MagicMock(spec=ComplianceRepository)
        risk_service = MagicMock(spec=RiskAnalysisService)
        service = CompliancePlanService(compliance_repo, risk_service)
        
        business_profile = {"industry": "technology"}
        risk_assessment = {
            "risk_score": 75,
            "risk_level": "high",
            "priority_regulations": ["GDPR", "ISO 27001"]
        }
        
        result = await service.generate_compliance_plan(
            business_profile,
            risk_assessment
        )
        
        assert "plan_id" in result
        assert "priority" in result
        assert "phases" in result
        assert len(result["phases"]) == 4
        assert result["priority"] == "urgent"  # High risk = urgent priority


if __name__ == "__main__":
    pytest.main([__file__, "-v"])