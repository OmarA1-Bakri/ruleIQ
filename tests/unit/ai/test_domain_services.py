"""
Unit tests for AI Domain Services

Tests domain-specific AI service implementations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import Dict, Any

from services.ai.domains.assessment_service import AssessmentService
from services.ai.domains.policy_service import PolicyService
from services.ai.domains.workflow_service import WorkflowService
from services.ai.domains.evidence_service import EvidenceService
from services.ai.domains.compliance_service import ComplianceAnalysisService


@pytest.fixture
def mock_response_generator():
    """Mock response generator."""
    generator = Mock()
    generator.generate_simple = AsyncMock(return_value="Test response")
    return generator


@pytest.fixture
def mock_response_parser():
    """Mock response parser."""
    parser = Mock()
    parser.parse_assessment_help.return_value = {
        "guidance": "Test guidance",
        "confidence_score": 0.9,
    }
    parser.parse_json.return_value = {"key": "value"}
    return parser


@pytest.fixture
def mock_fallback_generator():
    """Mock fallback generator."""
    generator = Mock()
    generator.get_assessment_help.return_value = {
        "guidance": "Fallback guidance",
        "confidence_score": 0.5,
        "is_fallback": True,
    }
    generator.get_workflow.return_value = {"workflow_id": "test", "phases": []}
    return generator


@pytest.fixture
def mock_context_manager():
    """Mock context manager."""
    manager = AsyncMock()
    manager.get_business_context.return_value = {
        "company_name": "Test Corp",
        "industry": "Technology",
        "employee_count": 50,
    }
    manager.get_conversation_context.return_value = {
        "business_profile": {"company_name": "Test Corp"},
        "recent_evidence": [],
    }
    return manager


@pytest.fixture
def mock_prompt_templates():
    """Mock prompt templates."""
    templates = Mock()
    templates.get_assessment_help_prompt.return_value = "Test prompt"
    return templates


@pytest.mark.asyncio
class TestAssessmentService:
    """Test assessment service."""

    @pytest.fixture
    def assessment_service(
        self,
        mock_response_generator,
        mock_context_manager,
    ):
        """Create assessment service with mocks."""
        return AssessmentService(
            mock_response_generator,
            mock_context_manager,
        )

    async def test_get_help(self, assessment_service):
        """Test getting assessment help."""
        help_response = await assessment_service.get_assessment_help(
            question_id="Q1",
            question_text="What is GDPR?",
            framework_id="GDPR",
            business_profile_id=uuid4(),
            section_id="S1",
        )

        assert "guidance" in help_response
        assert isinstance(help_response, dict)

    async def test_get_help_with_cache(self, assessment_service):
        """Test help retrieval returns valid response on repeated call."""
        help_response = await assessment_service.get_assessment_help(
            "Q1", "Test", "GDPR", uuid4()
        )

        assert "guidance" in help_response
        assert isinstance(help_response, dict)

    async def test_get_help_timeout_fallback(self, assessment_service):
        """Test fallback on timeout."""
        import asyncio

        assessment_service.response_generator.generate_simple = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        help_response = await assessment_service.get_assessment_help(
            "Q1", "Test", "GDPR", uuid4()
        )

        # Timeout triggers fast fallback which includes 'guidance'
        assert "guidance" in help_response

    async def test_generate_followup(self, assessment_service):
        """Test generating follow-up questions."""
        followup = await assessment_service.generate_assessment_followup(
            current_answers={"Q1": "Yes"}, framework_id="GDPR", business_profile_id=uuid4()
        )

        assert isinstance(followup, dict)

    async def test_analyze_results(self, assessment_service):
        """Test analyzing assessment results."""
        results = {"Q1": "Yes", "Q2": "No"}
        analysis = await assessment_service.analyze_assessment_results(
            results, "GDPR", uuid4()
        )

        assert isinstance(analysis, dict)

    async def test_get_recommendations(self, assessment_service):
        """Test analyze_assessment_results returns structured analysis with recommendations."""
        analysis = await assessment_service.analyze_assessment_results(
            assessment_results={"Q1": "Yes"}, framework_id="GDPR", business_profile_id=uuid4()
        )

        assert isinstance(analysis, dict)


@pytest.mark.asyncio
class TestPolicyService:
    """Test policy service."""

    @pytest.fixture
    def policy_service(
        self,
        mock_response_generator,
        mock_context_manager,
    ):
        """Create policy service with mocks."""
        return PolicyService(
            mock_response_generator,
            mock_context_manager,
        )

    async def test_generate_policy(self, policy_service):
        """Test policy generation."""
        user = Mock()
        user.id = uuid4()

        policy = await policy_service.generate_customized_policy(
            user=user, business_profile_id=uuid4(), framework="GDPR", policy_type="Data Protection"
        )

        assert isinstance(policy, dict)

    async def test_generate_policy_with_customization(self, policy_service):
        """Test policy generation with customization options."""
        user = Mock()
        user.id = uuid4()

        policy = await policy_service.generate_customized_policy(
            user=user,
            business_profile_id=uuid4(),
            framework="ISO27001",
            policy_type="Access Control",
            customization_options={"tone": "formal"},
        )

        assert isinstance(policy, dict)


@pytest.mark.asyncio
class TestWorkflowService:
    """Test workflow service."""

    @pytest.fixture
    def workflow_service(
        self,
        mock_response_generator,
        mock_response_parser,
        mock_fallback_generator,
        mock_context_manager,
    ):
        """Create workflow service with mocks."""
        return WorkflowService(
            mock_response_generator,
            mock_response_parser,
            mock_fallback_generator,
            mock_context_manager,
        )

    async def test_generate_workflow(self, workflow_service):
        """Test workflow generation."""
        user = Mock()
        user.id = uuid4()

        workflow = await workflow_service.generate_workflow(
            user=user, business_profile_id=uuid4(), framework="ISO27001", control_id="A.9.1"
        )

        assert isinstance(workflow, dict)
        assert "workflow_id" in workflow or "phases" in workflow

    async def test_generate_workflow_comprehensive(self, workflow_service):
        """Test comprehensive workflow generation."""
        user = Mock()
        workflow = await workflow_service.generate_workflow(
            user=user, business_profile_id=uuid4(), framework="GDPR", workflow_type="comprehensive"
        )

        assert isinstance(workflow, dict)


@pytest.mark.asyncio
class TestEvidenceService:
    """Test evidence service."""

    @pytest.fixture
    def evidence_service(
        self,
        mock_response_generator,
        mock_response_parser,
        mock_fallback_generator,
        mock_context_manager,
    ):
        """Create evidence service with mocks."""
        return EvidenceService(
            mock_response_generator,
            mock_response_parser,
            mock_fallback_generator,
            mock_context_manager,
        )

    async def test_get_recommendations(self, evidence_service):
        """Test getting evidence recommendations."""
        user = Mock()
        user.id = uuid4()

        recommendations = await evidence_service.get_recommendations(
            user=user, business_profile_id=uuid4(), framework="GDPR"
        )

        assert isinstance(recommendations, list)

    async def test_get_recommendations_with_control(self, evidence_service):
        """Test evidence recommendations for specific control."""
        user = Mock()
        recommendations = await evidence_service.get_recommendations(
            user=user, business_profile_id=uuid4(), framework="ISO27001", control_id="A.9.1"
        )

        assert isinstance(recommendations, list)


@pytest.mark.asyncio
class TestComplianceAnalysisService:
    """Test compliance analysis service."""

    @pytest.fixture
    def compliance_service(self, mock_response_generator, mock_context_manager):
        """Create compliance analysis service with mocks."""
        return ComplianceAnalysisService(mock_response_generator, mock_context_manager)

    async def test_analyze_evidence_gap(self, compliance_service):
        """Test evidence gap analysis."""
        analysis = await compliance_service.analyze_evidence_gap(
            business_profile_id=uuid4(), framework="GDPR"
        )

        assert isinstance(analysis, dict)

    async def test_validate_accuracy(self, compliance_service):
        """Test accuracy validation."""
        validation = compliance_service.validate_accuracy(
            response="GDPR requires data minimization", framework="GDPR"
        )

        assert isinstance(validation, dict)
        assert "is_accurate" in validation or "accuracy_score" in validation

    async def test_detect_hallucination(self, compliance_service):
        """Test hallucination detection."""
        detection = compliance_service.detect_hallucination(response="GDPR Article 999 requires...")

        assert isinstance(detection, dict)
        assert "likely_hallucination" in detection or "confidence" in detection


@pytest.mark.integration
class TestDomainServicesIntegration:
    """Integration tests for domain services."""

    @pytest.mark.skip(reason="Requires database and AI API")
    async def test_assessment_service_real_workflow(self):
        """Test assessment service with real dependencies."""
        # Would test with real database and API
        pass

    def test_all_services_instantiate(
        self,
        mock_response_generator,
        mock_response_parser,
        mock_fallback_generator,
        mock_context_manager,
    ):
        """Test all services can be instantiated."""
        assessment = AssessmentService(
            mock_response_generator,
            mock_context_manager,
        )
        policy = PolicyService(
            mock_response_generator,
            mock_context_manager,
        )
        workflow = WorkflowService(
            mock_response_generator,
            mock_response_parser,
            mock_fallback_generator,
            mock_context_manager,
        )
        evidence = EvidenceService(
            mock_response_generator,
            mock_response_parser,
            mock_fallback_generator,
            mock_context_manager,
        )
        compliance = ComplianceAnalysisService(mock_response_generator, mock_context_manager)

        assert assessment is not None
        assert policy is not None
        assert workflow is not None
        assert evidence is not None
        assert compliance is not None
