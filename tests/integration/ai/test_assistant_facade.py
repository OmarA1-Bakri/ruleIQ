"""
Integration tests for ComplianceAssistant Façade

Tests that the façade correctly delegates to domain services and maintains
backward compatibility with the original implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from services.ai.assistant_facade import ComplianceAssistant
from database.user import User


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_user():
    """Mock user."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def user_context():
    """User context dictionary."""
    return {"user_id": str(uuid4()), "preferences": {}}


@pytest.mark.asyncio
class TestComplianceAssistantFacade:
    """Test the ComplianceAssistant façade."""

    def test_initialization(self, mock_db_session, user_context):
        """Test façade initializes correctly."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        # Check original attributes preserved
        assert assistant.db == mock_db_session
        assert assistant.user_context == user_context
        assert assistant.context_manager is not None
        assert assistant.prompt_templates is not None

        # Check new architecture components initialized
        assert assistant.provider_factory is not None
        assert assistant.response_generator is not None
        assert assistant.response_parser is not None
        assert assistant.fallback_generator is not None

        # Check domain services initialized
        assert assistant.assessment_service is not None
        assert assistant.policy_service is not None
        assert assistant.workflow_service is not None
        assert assistant.evidence_service is not None
        assert assistant.compliance_service is not None

    async def test_get_assessment_help_delegates_to_service(self, mock_db_session, user_context):
        """Test assessment help delegates to AssessmentService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        # Mock the service method
        mock_response = {"guidance": "Test guidance", "confidence_score": 0.9}
        assistant.assessment_service.get_help = AsyncMock(return_value=mock_response)

        result = await assistant.get_assessment_help(
            question_id="Q1",
            question_text="What is GDPR?",
            framework_id="GDPR",
            business_profile_id=uuid4(),
        )

        assert result == mock_response
        assistant.assessment_service.get_help.assert_called_once()

    async def test_generate_assessment_followup_delegates(self, mock_db_session, user_context):
        """Test followup generation delegates to AssessmentService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"questions": []}
        assistant.assessment_service.generate_followup = AsyncMock(return_value=mock_response)

        result = await assistant.generate_assessment_followup(
            current_answers={"Q1": "Yes"}, framework_id="GDPR", business_profile_id=uuid4()
        )

        assert result == mock_response

    async def test_analyze_assessment_results_delegates(self, mock_db_session, user_context):
        """Test results analysis delegates to AssessmentService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"analysis": "Complete"}
        assistant.assessment_service.analyze_results = AsyncMock(return_value=mock_response)

        result = await assistant.analyze_assessment_results(
            assessment_results={"Q1": "Yes"}, framework_id="GDPR", business_profile_id=uuid4()
        )

        assert result == mock_response

    async def test_get_assessment_recommendations_delegates(self, mock_db_session, user_context):
        """Test recommendations delegate to AssessmentService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"recommendations": []}
        assistant.assessment_service.get_recommendations = AsyncMock(return_value=mock_response)

        result = await assistant.get_assessment_recommendations(
            assessment_results={"Q1": "Yes"}, framework_id="GDPR", business_profile_id=uuid4()
        )

        assert result == mock_response

    async def test_generate_customized_policy_delegates(
        self, mock_db_session, mock_user, user_context
    ):
        """Test policy generation delegates to PolicyService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"policy": "Generated"}
        assistant.policy_service.generate_policy = AsyncMock(return_value=mock_response)

        result = await assistant.generate_customized_policy(
            user=mock_user,
            business_profile_id=uuid4(),
            framework="GDPR",
            policy_type="Data Protection",
        )

        assert result == mock_response
        assistant.policy_service.generate_policy.assert_called_once()

    async def test_generate_evidence_collection_workflow_delegates(
        self, mock_db_session, mock_user, user_context
    ):
        """Test workflow generation delegates to WorkflowService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"workflow_id": "test", "phases": []}
        assistant.workflow_service.generate_workflow = AsyncMock(return_value=mock_response)

        result = await assistant.generate_evidence_collection_workflow(
            user=mock_user, business_profile_id=uuid4(), framework="ISO27001", control_id="A.9.1"
        )

        assert result == mock_response
        assistant.workflow_service.generate_workflow.assert_called_once()

    async def test_get_evidence_recommendations_delegates(
        self, mock_db_session, mock_user, user_context
    ):
        """Test evidence recommendations delegate to EvidenceService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"recommendations": []}
        assistant.evidence_service.get_recommendations = AsyncMock(return_value=mock_response)

        result = await assistant.get_evidence_recommendations(
            user=mock_user, business_profile_id=uuid4(), framework="GDPR"
        )

        assert result == mock_response

    async def test_analyze_evidence_gap_delegates(self, mock_db_session, user_context):
        """Test evidence gap analysis delegates to ComplianceAnalysisService."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        mock_response = {"gaps": []}
        assistant.compliance_service.analyze_evidence_gap = AsyncMock(return_value=mock_response)

        result = await assistant.analyze_evidence_gap(business_profile_id=uuid4(), framework="GDPR")

        assert result == mock_response

    def test_legacy_method_delegates_to_provider_factory(self, mock_db_session, user_context):
        """Test legacy _get_task_appropriate_model delegates to provider factory."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        # Mock provider factory
        mock_model = Mock()
        assistant.provider_factory.get_provider_for_task = Mock(
            return_value=(mock_model, "test_instruction")
        )

        model, instruction_id = assistant._get_task_appropriate_model("help")

        assert model == mock_model
        assert instruction_id == "test_instruction"
        assistant.provider_factory.get_provider_for_task.assert_called_once()

    async def test_legacy_generate_gemini_response_delegates(self, mock_db_session, user_context):
        """Test legacy _generate_gemini_response delegates to response generator."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        # Mock response generator
        assistant.response_generator.generate_simple = AsyncMock(return_value="Test response")

        response = await assistant._generate_gemini_response(
            prompt="Test prompt", context={"framework": "GDPR"}
        )

        assert response == "Test response"
        assistant.response_generator.generate_simple.assert_called_once()

    def test_content_type_map_preserved(self, mock_db_session, user_context):
        """Test original content_type_map is preserved."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        assert "assessment_help" in assistant.content_type_map
        assert "evidence_recommendations" in assistant.content_type_map
        assert "policy_generation" in assistant.content_type_map
        assert "compliance_analysis" in assistant.content_type_map

    def test_safety_settings_preserved(self, mock_db_session, user_context):
        """Test safety settings are preserved."""
        assistant = ComplianceAssistant(mock_db_session, user_context)

        assert assistant.safety_settings is not None
        assert len(assistant.safety_settings) > 0


@pytest.mark.integration
@pytest.mark.skip(reason="Requires real database and API keys")
class TestComplianceAssistantFacadeRealWorld:
    """Real-world integration tests for the façade."""

    async def test_full_assessment_workflow(self):
        """Test complete assessment workflow end-to-end."""
        # Would test with real database and API
        pass

    async def test_policy_generation_workflow(self):
        """Test complete policy generation workflow."""
        # Would test with real database and API
        pass

    async def test_evidence_workflow(self):
        """Test complete evidence collection workflow."""
        # Would test with real database and API
        pass


@pytest.mark.benchmark
class TestFacadePerformance:
    """Performance benchmarks for the façade."""

    def test_initialization_performance(self, benchmark, mock_db_session):
        """Benchmark façade initialization time."""

        def create_assistant():
            return ComplianceAssistant(mock_db_session, {})

        result = benchmark(create_assistant)
        assert result is not None

    @pytest.mark.asyncio
    async def test_delegation_overhead(self, mock_db_session):
        """Test delegation overhead is minimal."""
        assistant = ComplianceAssistant(mock_db_session, {})

        # Mock service to return immediately
        assistant.assessment_service.get_help = AsyncMock(return_value={"guidance": "Fast"})

        import time

        start = time.perf_counter()
        await assistant.get_assessment_help("Q1", "Test", "GDPR", uuid4())
        elapsed = time.perf_counter() - start

        # Delegation should add <1ms overhead
        assert elapsed < 0.001  # 1ms
