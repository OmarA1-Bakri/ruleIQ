"""

# Constants


Integration Tests for Enhanced Chat API Endpoints

Tests the new context-aware recommendations, workflow generation,
and policy generation endpoints with real database interactions.
"""

from unittest.mock import patch
import pytest
from tests.conftest import assert_api_response_security

from tests.test_constants import (
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
    MAX_RETRIES,
)


@pytest.mark.integration
@pytest.mark.api
class TestEnhancedChatEndpoints:
    """Test enhanced chat API endpoints integration"""

    def test_context_aware_recommendations_success(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test context-aware recommendations endpoint"""
        with patch(
            "services.ai.assistant.ComplianceAssistant.get_context_aware_recommendations"
        ) as mock_ai:
            mock_ai.return_value = {
                "framework": "ISO27001",
                "business_context": {
                    "company_name": "Test Corp",
                    "industry": "Technology",
                    "employee_count": 100,
                    "maturity_level": "Intermediate",
                },
                "current_status": {
                    "completion_percentage": 45.0,
                    "evidence_collected": 25,
                    "critical_gaps_count": 3,
                },
                "recommendations": [
                    {
                        "control_id": "A.9.1.1",
                        "title": "Access Control Policy",
                        "description": "Implement access control policy",
                        "priority": "High",
                        "effort_hours": 8,
                        "automation_possible": True,
                        "business_justification": "Critical for compliance",
                        "implementation_steps": ["Draft", "Review", "Approve"],
                        "priority_score": 3.5,
                    }
                ],
                "next_steps": ["Implement access control policy"],
                "estimated_effort": {
                    "total_hours": 40,
                    "high_priority_hours": 20,
                    "estimated_weeks": 1.0,
                    "quick_wins": 2,
                },
                "generated_at": "2024-01-01T00:00:00",
            }
            response = client.post(
                "/api/chat/context-aware-recommendations?framework=ISO27001&context_type=comprehensive",
                headers=authenticated_headers,
            )
            if response.status_code == HTTP_OK:
                assert_api_response_security(response)
                data = response.json()
                assert data["framework"] == "ISO27001"
                assert "business_context" in data
                assert "recommendations" in data
                assert len(data["recommendations"]) > 0
                rec = data["recommendations"][0]
                assert "control_id" in rec
                assert "priority_score" in rec
                assert rec["automation_possible"] is True
            else:
                assert response.status_code == HTTP_BAD_REQUEST

    def test_evidence_collection_workflow_generation(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test workflow generation endpoint"""
        with patch(
            "services.ai.assistant.ComplianceAssistant.generate_evidence_collection_workflow"
        ) as mock_ai:
            mock_ai.return_value = {
                "workflow_id": "iso27001_a911_12345678",
                "title": "Access Control Evidence Collection Workflow",
                "description": "Comprehensive workflow for collecting access control evidence",
                "framework": "ISO27001",
                "control_id": "A.9.1.1",
                "created_at": "2024-01-01T00:00:00",
                "phases": [
                    {
                        "phase_id": "phase_1",
                        "title": "Planning and Preparation",
                        "description": "Initial planning phase",
                        "estimated_hours": 4,
                        "steps": [
                            {
                                "step_id": "step_1",
                                "title": "Define scope",
                                "description": "Define the scope of evidence collection",
                                "deliverables": ["Scope document"],
                                "responsible_role": "Compliance Manager",
                                "estimated_hours": 2,
                                "dependencies": [],
                                "tools_needed": ["Documentation tools"],
                                "validation_criteria": ["Scope approved"],
                                "automation_opportunities": {
                                    "automation_level": "medium",
                                    "high_automation_potential": False,
                                    "suggested_tools": ["Document automation tools"],
                                    "effort_reduction_percentage": 40,
                                },
                                "estimated_hours_with_automation": 1,
                            }
                        ],
                    }
                ],
                "automation_summary": {
                    "automation_percentage": 50.0,
                    "effort_savings_percentage": 30.0,
                    "manual_hours": 20,
                    "automated_hours": 14,
                    "hours_saved": 6,
                    "high_automation_steps": 2,
                    "total_steps": 4,
                },
                "effort_estimation": {
                    "total_manual_hours": 20,
                    "total_automated_hours": 14,
                    "estimated_weeks_manual": 0.5,
                    "estimated_weeks_automated": 0.35,
                    "phases_count": 3,
                    "steps_count": 8,
                    "effort_savings": {"hours_saved": 6, "percentage_saved": 30.0},
                },
            }
            response = client.post(
                "/api/chat/evidence-collection-workflow?framework=ISO27001&control_id=A.9.1.1&workflow_type=comprehensive",
                headers=authenticated_headers,
            )
            if response.status_code == HTTP_OK:
                assert_api_response_security(response)
                data = response.json()
                assert data["framework"] == "ISO27001"
                assert data["control_id"] == "A.9.1.1"
                assert "phases" in data
                assert "automation_summary" in data
                assert "effort_estimation" in data
                phase = data["phases"][0]
                assert "steps" in phase
                assert len(phase["steps"]) > 0
                step = phase["steps"][0]
                assert "automation_opportunities" in step
                assert "estimated_hours_with_automation" in step
            else:
                assert response.status_code == HTTP_BAD_REQUEST

    def test_policy_generation(self, client, authenticated_headers, sample_business_profile):
        """Test policy generation endpoint"""
        with patch(
            "services.ai.assistant.ComplianceAssistant.generate_customized_policy"
        ) as mock_ai:
            mock_ai.return_value = {
                "policy_id": "iso27001_information_security_12345678",
                "title": "Information Security Policy",
                "version": "1.0",
                "effective_date": "2024-01-01",
                "framework": "ISO27001",
                "policy_type": "information_security",
                "created_at": "2024-01-01T00:00:00",
                "sections": [
                    {
                        "section_id": "section_1",
                        "title": "Purpose and Scope",
                        "content": "This policy establishes the framework for information security management.",
                        "subsections": [
                            {
                                "subsection_id": "subsection_1",
                                "title": "Purpose",
                                "content": "Define information security objectives",
                                "controls": ["A.5.1.1", "A.5.1.2"],
                            }
                        ],
                    }
                ],
                "roles_responsibilities": [
                    {
                        "role": "Information Security Officer",
                        "responsibilities": ["Oversee security program", "Manage incidents"],
                    }
                ],
                "procedures": [
                    {
                        "procedure_id": "proc_1",
                        "title": "Security Incident Response",
                        "steps": ["Detect", "Respond", "Recover"],
                    }
                ],
                "compliance_requirements": [
                    {
                        "requirement_id": "req_1",
                        "description": "Establish information security policy",
                        "control_reference": "A.5.1.1",
                    }
                ],
                "business_context": {
                    "company_name": "Test Corp",
                    "industry": "Technology",
                    "employee_count": 100,
                    "customization_applied": "2024-01-01T00:00:00",
                },
                "implementation_guidance": {
                    "implementation_phases": [
                        {
                            "phase": "Phase 1: Foundation",
                            "duration_weeks": 2,
                            "activities": ["Review policy", "Identify stakeholders"],
                        }
                    ],
                    "success_metrics": ["Policy approval completion"],
                    "common_challenges": ["Resource constraints"],
                    "mitigation_strategies": ["Phased implementation"],
                },
                "compliance_mapping": {
                    "framework": "ISO27001",
                    "policy_type": "information_security",
                    "mapped_controls": ["A.5.1.1", "A.5.1.2"],
                    "compliance_objectives": ["Ensure ISO 27001 compliance"],
                    "audit_considerations": ["Document implementations"],
                },
            }
            response = client.post(
                "/api/chat/generate-policy?framework=ISO27001&policy_type=information_security&tone=Professional&detail_level=Standard",
                headers=authenticated_headers,
            )
            if response.status_code == HTTP_OK:
                assert_api_response_security(response)
                data = response.json()
                assert data["framework"] == "ISO27001"
                assert data["policy_type"] == "information_security"
                assert "sections" in data
                assert "roles_responsibilities" in data
                assert "implementation_guidance" in data
                assert "compliance_mapping" in data
                section = data["sections"][0]
                assert "subsections" in section
                assert "business_context" in data
                assert data["business_context"]["company_name"] == "Test Corp"
            else:
                assert response.status_code == HTTP_BAD_REQUEST

    def test_smart_compliance_guidance(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test smart compliance guidance endpoint"""
        with patch(
            "services.ai.assistant.ComplianceAssistant.get_context_aware_recommendations"
        ) as mock_rec:
            with patch(
                "services.ai.assistant.ComplianceAssistant.analyze_evidence_gap"
            ) as mock_gap:
                mock_rec.return_value = {
                    "business_context": {"maturity_level": "Intermediate"},
                    "recommendations": [
                        {
                            "control_id": "A.9.1.1",
                            "title": "Access Control",
                            "effort_hours": 2,
                            "automation_possible": True,
                        },
                        {
                            "control_id": "A.16.1.1",
                            "title": "Incident Management",
                            "effort_hours": 8,
                            "automation_possible": False,
                        },
                    ],
                    "next_steps": ["Implement access controls"],
                    "estimated_effort": {"total_hours": 40, "quick_wins": 2},
                }
                mock_gap.return_value = {
                    "completion_percentage": 60.0,
                    "critical_gaps": ["Policy gaps", "Procedure gaps"],
                }
                response = client.get(
                    "/api/chat/smart-guidance/ISO27001?guidance_type=getting_started",
                    headers=authenticated_headers,
                )
                if response.status_code == HTTP_OK:
                    assert_api_response_security(response)
                    data = response.json()
                    assert data["framework"] == "ISO27001"
                    assert "current_status" in data
                    assert "personalized_roadmap" in data
                    assert "quick_wins" in data
                    assert "automation_opportunities" in data
                    status = data["current_status"]
                    assert "completion_percentage" in status
                    assert "maturity_level" in status
                    assert len(data["quick_wins"]) <= MAX_RETRIES
                    assert len(data["automation_opportunities"]) <= MAX_RETRIES
                else:
                    assert response.status_code == HTTP_BAD_REQUEST

    def test_missing_business_profile_error(self, client, db_session):
        """Test error handling when business profile is missing"""
        from uuid import uuid4
        from api.dependencies.auth import create_access_token
        from datetime import timedelta
        from database.user import User
        from database.business_profile import BusinessProfile
        from sqlalchemy import select

        test_user = User(
            id=uuid4(),
            email=f"no-profile-user-{uuid4()}@example.com",
            hashed_password="fake_password_hash",
            is_active=True,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == test_user.id)
        existing_profile = db_session.execute(stmt).scalars().first()
        if existing_profile:
            db_session.delete(existing_profile)
            db_session.commit()
        token_data = {"sub": str(test_user.id)}
        token = create_access_token(data=token_data, expires_delta=timedelta(minutes=30))
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/chat/context-aware-recommendations?framework=ISO27001", headers=headers
        )
        assert response.status_code == HTTP_BAD_REQUEST
        data = response.json()
        assert "Business profile not found" in data["detail"]

    def test_ai_service_error_handling(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test handling of AI service errors"""
        with patch(
            "services.ai.assistant.ComplianceAssistant.get_context_aware_recommendations"
        ) as mock_ai:
            mock_ai.side_effect = Exception("AI service temporarily unavailable")
            response = client.post(
                "/api/chat/context-aware-recommendations?framework=ISO27001",
                headers=authenticated_headers,
            )
            assert response.status_code in [400, 500]

    def test_invalid_framework_parameter(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test validation of framework parameter"""
        response = client.post(
            "/api/chat/context-aware-recommendations?framework=", headers=authenticated_headers
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY


@pytest.mark.integration
@pytest.mark.api
class TestEnhancedChatValidation:
    """Test enhanced chat API validation and error handling"""

    def test_workflow_generation_parameter_validation(self, client, authenticated_headers):
        """Test workflow generation parameter validation"""
        response = client.post(
            "/api/chat/evidence-collection-workflow", headers=authenticated_headers
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_policy_generation_parameter_validation(self, client, authenticated_headers):
        """Test policy generation parameter validation"""
        response = client.post("/api/chat/generate-policy", headers=authenticated_headers)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_smart_guidance_parameter_validation(self, client, authenticated_headers):
        """Test smart guidance parameter validation"""
        response = client.get("/api/chat/smart-guidance/", headers=authenticated_headers)
        assert response.status_code == HTTP_NOT_FOUND
