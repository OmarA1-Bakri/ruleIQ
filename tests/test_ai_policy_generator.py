"""
Test specifications for AI Policy Generation Assistant.

Following Agent Operating Protocol: Tests first, implementation after approval.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import Dict, Any, List

from services.ai.policy_generator import PolicyGenerator, TemplateProcessor
from services.ai.circuit_breaker import AICircuitBreaker
from api.schemas.ai_policy import (
    PolicyGenerationRequest,
    PolicyGenerationResponse,
    BusinessContext,
    PolicyType,
    CustomizationLevel,
    TargetAudience,
)
from database.compliance_framework import ComplianceFramework


class TestPolicyGenerationService:
    """Test suite for AI-powered policy generation"""

    @pytest.fixture
    def sample_uk_gdpr_framework(self):
        """Sample UK GDPR framework for testing"""
        return ComplianceFramework(
            id="test-uk-gdpr-id",
            name="ICO_GDPR_UK",
            display_name="UK GDPR (ICO Implementation)",
            description="Data Protection Act 2018 & UK GDPR requirements",
            category="Data Protection",
            geographic_scop=["UK"],
            key_requirement=[
                "Lawful basis for processing",
                "Data subject rights",
                "Data Protection Impact Assessments",
                "Breach notification (72 hours to ICO)",
            ],
            policy_template="""
            # UK GDPR Privacy Policy Template
            ## 1. Data Controller Information
            [Organization Name]
            ## 2. Legal Basis for Processing
            We process personal data under the following legal bases:
            - Consent (Article 6(1)(a))
            - Contract performance (Article 6(1)(b))
            """,
        )

    @pytest.fixture
    def sample_business_context(self):
        """Sample business context for policy generation"""
        return BusinessContext(
            organization_name="TechCorp Ltd",
            industry="fintech",
            employee_count=50,
            processes_personal_data=True,
            data_types=["customer_data", "financial_data", "employee_data"],
            geographic_operations=["UK", "EU"],
            third_party_processors=True,
            data_retention_period="7 years",
        )

    @pytest.fixture
    def policy_generation_request(self, sample_business_context):
        """Sample policy generation request"""
        return PolicyGenerationRequest(
            framework_id="test-uk-gdpr-id",
            business_context=sample_business_context,
            policy_type=PolicyType.PRIVACY_POLICY,
            customization_level=CustomizationLevel.DETAILED,
            include_templates=True,
            target_audience=TargetAudience.GENERAL_PUBLIC,
        )

    def test_policy_generator_initialization(self):
        """Test PolicyGenerator initializes with dual AI providers"""
        generator = PolicyGenerator()

        assert generator.primary_provider == "google"
        assert generator.fallback_provider == "openai"
        assert generator.circuit_breaker is not None
        assert generator.template_processor is not None

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker properly configured for AI providers"""
        circuit_breaker = AICircuitBreaker()

        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 60
        assert circuit_breaker.half_open_max_calls == 5

        # Test state transitions
        assert circuit_breaker.state == "CLOSED"

        # Simulate failures
        for _ in range(3):
            circuit_breaker.record_failure("google")

        assert circuit_breaker.get_state("google") == "OPEN"

    @patch("services.ai.policy_generator.GoogleAIClient")
    def test_policy_generation_success_google(
        self, mock_google, policy_generation_request, sample_uk_gdpr_framework
    ):
        """Test successful policy generation using Google AI (primary)"""
        # Mock Google AI response
        mock_google.return_value.generate_policy.return_value = {
            "policy_content": """
            # TechCorp Ltd Privacy Policy

            ## 1. Data Controller Information
            TechCorp Ltd
            123 Tech Street, London, UK
            ICO Registration: ZA123456

            ## 2. Legal Basis for Processing
            We process personal data under the following legal bases:
            - Consent for marketing communications
            - Contract performance for service delivery
            - Legal obligation for regulatory compliance
            """,
            "confidence_score": 0.92,
            "generated_sections": [
                "data_controller_info",
                "legal_basis",
                "data_subject_rights",
                "retention_policy",
            ],
            "compliance_checklist": [
                "ICO registration mentioned",
                "Legal bases clearly stated",
                "Data subject rights included",
            ],
        }

        generator = PolicyGenerator()
        result = generator.generate_policy(
            policy_generation_request,
            sample_uk_gdpr_framework,
        )

        assert result.success is True
        assert result.provider_used == "google"
        assert result.confidence_score == 0.92
        assert "TechCorp Ltd" in result.policy_content
        assert "ICO Registration" in result.policy_content
        assert len(result.generated_sections) == 4
        assert len(result.compliance_checklist) == 3

    @patch("services.ai.policy_generator.GoogleAIClient")
    @patch("services.ai.policy_generator.OpenAIClient")
    def test_policy_generation_fallback_to_openai(
        self,
        mock_openai,
        mock_google,
        policy_generation_request,
        sample_uk_gdpr_framework,
    ):
        """Test fallback to OpenAI when Google AI fails"""
        # Mock Google AI failure
        mock_google.return_value.generate_policy.side_effect = Exception(
            "Google AI service unavailable",
        )

        # Mock OpenAI success
        mock_openai.return_value.generate_policy.return_value = {
            "policy_content": "# TechCorp Ltd Privacy Policy (Generated by OpenAI)\n\nFallback policy content...",
            "confidence_score": 0.88,
            "generated_sections": ["basic_policy"],
            "compliance_checklist": ["Basic compliance met"],
        }

        generator = PolicyGenerator()
        result = generator.generate_policy(
            policy_generation_request,
            sample_uk_gdpr_framework,
        )

        assert result.success is True
        assert result.provider_used == "openai"
        assert result.confidence_score == 0.88
        assert "Generated by OpenAI" in result.policy_content

    def test_policy_generation_both_providers_fail(
        self, policy_generation_request, sample_uk_gdpr_framework
    ):
        """Test graceful failure when both AI providers fail"""
        with (
            patch("services.ai.policy_generator.GoogleAIClient") as mock_google,
            patch("services.ai.policy_generator.OpenAIClient") as mock_openai,
        ):
            # Mock both providers failing
            mock_google.return_value.generate_policy.side_effect = Exception(
                "Google AI failed",
            )
            mock_openai.return_value.generate_policy.side_effect = Exception(
                "OpenAI failed",
            )

            generator = PolicyGenerator()
            result = generator.generate_policy(
                policy_generation_request,
                sample_uk_gdpr_framework,
            )

            assert result.success is False
            assert result.error_message == "All AI providers failed"
            assert result.fallback_content is not None
            assert "template-based policy" in result.fallback_content

    def test_template_processor_iso27001_integration(self):
        """Test template processor parses ISO 27001 templates correctly"""
        processor = TemplateProcessor()

        # Test parsing ISO 27001 Information Security Policy template
        iso_template_path = "iso27001-templates/03. Information Security Policy.docx"

        result = processor.parse_iso27001_template(iso_template_path)

        assert result.success is True
        assert result.template_type == "information_security_policy"
        assert len(result.sections) > 0
        assert "policy_statement" in result.sections
        assert "scope" in result.sections
        assert "responsibilities" in result.sections

    def test_policy_customization_levels(self, policy_generation_request, sample_uk_gdpr_framework):
        """Test different customization levels produce appropriate content"""
        generator = PolicyGenerator()

        with patch("services.ai.policy_generator.GoogleAIClient") as mock_google:
            mock_google.return_value.generate_policy.return_value = {
                "policy_content": "Basic policy content",
                "confidence_score": 0.9,
                "generated_sections": ["basic"],
                "compliance_checklist": ["basic_compliance"],
            }

            # Test basic customization
            basic_request = policy_generation_request
            basic_request.customization_level = CustomizationLevel.BASIC

            result = generator.generate_policy(basic_request, sample_uk_gdpr_framework)

            # Verify basic customization produces minimal content
            assert result.success is True
            assert len(result.generated_sections) >= 1

            # Test detailed customization
            detailed_request = policy_generation_request
            detailed_request.customization_level = CustomizationLevel.DETAILED

            # Mock detailed response
            mock_google.return_value.generate_policy.return_value = {
                "policy_content": "Detailed comprehensive policy content",
                "confidence_score": 0.95,
                "generated_sections": [
                    "detailed_section_1",
                    "detailed_section_2",
                    "detailed_section_3",
                ],
                "compliance_checklist": [
                    "detailed_compliance_1",
                    "detailed_compliance_2",
                ],
            }

            result = generator.generate_policy(
                detailed_request,
                sample_uk_gdpr_framework,
            )

            assert result.success is True
            assert len(result.generated_sections) >= 3

    def test_policy_validation_uk_specific(self, sample_uk_gdpr_framework):
        """Test policy validation for UK-specific requirements"""
        generator = PolicyGenerator()

        # Test policy missing ICO registration
        invalid_policy = """
        # Privacy Policy
        We process data according to GDPR.
        """

        validation_result = generator.validate_uk_policy(
            invalid_policy,
            sample_uk_gdpr_framework,
        )

        assert validation_result.is_valid is False
        assert "ICO registration number missing" in validation_result.errors
        assert "Contact details incomplete" in validation_result.errors

        # Test valid UK policy
        valid_policy = """
        # Privacy Policy

        ## Data Controller
        TechCorp Ltd
        123 Tech Street, London, UK
        ICO Registration: ZA123456

        ## Legal Basis
        We process personal data under Article 6(1)(b) GDPR.

        ## Data Subject Rights
        You have the right to access, rectify, and erase your personal data.
        """

        validation_result = generator.validate_uk_policy(
            valid_policy,
            sample_uk_gdpr_framework,
        )

        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0
        assert validation_result.compliance_score >= 0.8

    def test_cost_optimization_caching(self, policy_generation_request, sample_uk_gdpr_framework):
        """Test caching reduces AI API calls for similar requests"""
        generator = PolicyGenerator()

        with patch("services.ai.policy_generator.GoogleAIClient") as mock_google:
            mock_response = {
                "policy_content": "Cached policy content",
                "confidence_score": 0.9,
                "generated_sections": ["cached"],
                "compliance_checklist": ["cached_compliance"],
            }
            mock_google.return_value.generate_policy.return_value = mock_response

            # First request - should call AI
            result1 = generator.generate_policy(
                policy_generation_request,
                sample_uk_gdpr_framework,
            )
            assert result1.success is True
            assert mock_google.return_value.generate_policy.call_count == 1

            # Second identical request - should use cache
            result2 = generator.generate_policy(
                policy_generation_request,
                sample_uk_gdpr_framework,
            )
            assert result2.success is True
            assert result2.was_cached is True
            assert mock_google.return_value.generate_policy.call_count == 1  # No additional call

    def test_policy_refinement_iterative(self, sample_uk_gdpr_framework):
        """Test iterative policy refinement functionality"""
        generator = PolicyGenerator()

        original_policy = "Basic privacy policy content"
        refinement_feedback = [
            "Add more detail about data retention",
            "Include specific contact information",
            "Clarify legal basis for processing",
        ]

        with patch("services.ai.policy_generator.GoogleAIClient") as mock_google:
            mock_google.return_value.refine_policy.return_value = {
                "refined_content": "Enhanced privacy policy with requested improvements",
                "changes_made": [
                    "Added retention details",
                    "Added contact info",
                    "Clarified legal basis",
                ],
                "confidence_score": 0.94,
            }

            result = generator.refine_policy(
                original_policy,
                refinement_feedback,
                sample_uk_gdpr_framework,
            )

            assert result.success is True
            assert len(result.changes_made) == 3
            assert "Enhanced privacy policy" in result.refined_content
            assert result.confidence_score == 0.94


class TestPolicyGeneratorAPIIntegration:
    """Test API integration for policy generation"""

    def test_generate_policy_endpoint(self, client, db_session):
        """Test POST /api/v1/ai/generate-policy endpoint"""
        # Pre-populate UK GDPR framework
        uk_framework = ComplianceFramework(
            name="ICO_GDPR_UK",
            display_name="UK GDPR",
            description="UK GDPR implementation",
            category="Data Protection",
        )
        db_session.add(uk_framework)
        db_session.commit()

        request_data = {
            "framework_id": str(uk_framework.id),
            "business_context": {
                "organization_name": "Test Corp",
                "industry": "technology",
                "employee_count": 25,
            },
            "policy_type": "privacy_policy",
            "customization_level": "detailed",
        }

        with patch("services.ai.policy_generator.PolicyGenerator") as mock_generator:
            mock_generator.return_value.generate_policy.return_value = (
                PolicyGenerationResponse(
                    success=True,
                    policy_content="Generated test policy",
                    confidence_score=0.9,
                    provider_used="google",
                    generated_sections=["test_section"],
                    compliance_checklist=["test_compliance"],
                ),
            )

            response = client.post("/api/v1/ai/generate-policy", json=request_data)

            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True
            assert "Generated test policy" in data["policy_content"]
            assert data["confidence_score"] == 0.9

    def test_refine_policy_endpoint(self, client):
        """Test PUT /api/v1/ai/refine-policy endpoint"""
        request_data = {
            "original_policy": "Basic policy content",
            "feedback": ["Add more detail", "Improve clarity"],
            "framework_id": "test-framework-id",
        }

        with patch("services.ai.policy_generator.PolicyGenerator") as mock_generator:
            mock_generator.return_value.refine_policy.return_value = Mock(
                success=True,
                refined_content="Improved policy content",
                changes_made=["Added detail", "Improved clarity"],
                confidence_score=0.92,
            )

            response = client.put("/api/v1/ai/refine-policy", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "Improved policy content" in data["refined_content"]

    def test_policy_templates_endpoint(self, client):
        """Test GET /api/v1/ai/policy-templates endpoint"""
        response = client.get("/api/v1/ai/policy-templates")

        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert len(data["templates"]) > 0
        assert any(t["name"] == "UK_GDPR_Privacy_Policy" for t in data["templates"])


class TestPolicyGeneratorPerformance:
    """Performance tests for policy generation"""

    def test_policy_generation_response_time(
        self, policy_generation_request, sample_uk_gdpr_framework
    ):
        """Test policy generation meets performance SLA (<30 seconds)"""
        import time

        generator = PolicyGenerator()

        with patch("services.ai.policy_generator.GoogleAIClient") as mock_google:
            # Simulate realistic AI response time
            def slow_generate(*args, **kwargs):
                time.sleep(0.5)  # Simulate AI processing
                return {
                    "policy_content": "Performance test policy",
                    "confidence_score": 0.9,
                    "generated_sections": ["perf_test"],
                    "compliance_checklist": ["perf_compliance"],
                }

            mock_google.return_value.generate_policy.side_effect = slow_generate

            start_time = time.time()
            result = generator.generate_policy(
                policy_generation_request,
                sample_uk_gdpr_framework,
            )
            end_time = time.time()

            generation_time = end_time - start_time

            assert result.success is True
            assert generation_time < 30.0  # Must complete within 30 seconds
            assert generation_time > 0.4  # Should take some realistic time

    def test_concurrent_policy_generation(
        self, policy_generation_request, sample_uk_gdpr_framework
    ):
        """Test concurrent policy generation requests"""
        import asyncio
        import concurrent.futures

        generator = PolicyGenerator()

        with patch("services.ai.policy_generator.GoogleAIClient") as mock_google:
            mock_google.return_value.generate_policy.return_value = {
                "policy_content": "Concurrent test policy",
                "confidence_score": 0.9,
                "generated_sections": ["concurrent"],
                "compliance_checklist": ["concurrent_compliance"],
            }

            def generate_policy_sync():
                return generator.generate_policy(
                    policy_generation_request,
                    sample_uk_gdpr_framework,
                )

            # Test 5 concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(generate_policy_sync) for _ in range(5)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            assert len(results) == 5
            assert all(result.success for result in results)
            assert all("Concurrent test policy" in result.policy_content for result in results)
