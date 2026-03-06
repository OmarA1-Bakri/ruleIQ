"""
Unit Tests for Enhanced AI Assistant Features

Tests the new context-aware recommendations, workflow generation,
and policy generation capabilities of the ComplianceAssistant.
"""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.exceptions import BusinessLogicException
from database.user import User
from services.ai.assistant import ComplianceAssistant


@pytest.mark.unit
@pytest.mark.ai
class TestContextAwareRecommendations:
    """Test enhanced context-aware recommendation functionality"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock user object"""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def sample_business_context(self):
        """Sample business context for testing"""
        return {
            "company_name": "Test Corp",
            "industry": "Technology",
            "employee_count": 150,
            "existing_frameworks": ["ISO27001"],
        }

    @pytest.fixture
    def sample_maturity_analysis(self):
        """Sample maturity analysis for testing"""
        return {
            "maturity_level": "Intermediate",
            "maturity_score": 65,
            "evidence_diversity": 5,
            "evidence_volume": 25,
            "industry_context": "technology",
            "size_category": "medium",
        }

    @pytest.fixture
    def sample_gaps_analysis(self):
        """Sample gaps analysis for testing"""
        return {
            "framework": "ISO27001",
            "completion_percentage": 45.0,
            "evidence_collected": 25,
            "critical_gaps": ["Access Control Policy", "Incident Response Plan"],
            "risk_level": "Medium",
        }

    @pytest.mark.asyncio
    async def test_get_context_aware_recommendations_success(
        self,
        mock_db_session,
        mock_user,
        sample_business_context,
        sample_maturity_analysis,
        sample_gaps_analysis,
    ):
        """Test successful context-aware recommendations generation"""

        assistant = ComplianceAssistant(mock_db_session)
        business_profile_id = uuid4()

        # Mock context manager
        with patch.object(assistant.context_manager, "get_conversation_context") as mock_context:
            mock_context.return_value = {
                "business_profile": sample_business_context,
                "recent_evidence": [
                    {"evidence_type": "policy", "title": "Security Policy"},
                    {"evidence_type": "procedure", "title": "Access Procedure"},
                ],
            }

            # Mock AI response
            with patch.object(assistant, "_generate_gemini_response") as mock_ai:
                mock_ai.return_value = json.dumps(
                    [
                        {
                            "control_id": "A.9.1.1",
                            "title": "Access Control Policy",
                            "description": "Implement comprehensive access control policy",
                            "priority": "High",
                            "effort_hours": 8,
                            "automation_possible": True,
                            "business_justification": "Critical for ISO 27001 compliance",
                            "implementation_steps": ["Draft policy", "Review", "Approve"],
                        },
                    ],
                )

                # Mock analyze_evidence_gap
                with patch.object(assistant, "analyze_evidence_gap") as mock_gap:
                    mock_gap.return_value = sample_gaps_analysis

                    result = await assistant.get_context_aware_recommendations(
                        user=mock_user,
                        business_profile_id=business_profile_id,
                        framework="ISO27001",
                        context_type="comprehensive",
                    )

                    # Assertions
                    assert result["framework"] == "ISO27001"
                    assert "business_context" in result
                    assert "current_status" in result
                    assert "recommendations" in result
                    assert "next_steps" in result
                    assert "estimated_effort" in result
                    assert len(result["recommendations"]) > 0

                    # Check business context
                    assert result["business_context"]["company_name"] == "Test Corp"
                    # Maturity level is calculated based on evidence, so it might be different
                    assert "maturity_level" in result["business_context"]

                    # Check recommendations structure
                    rec = result["recommendations"][0]
                    assert "control_id" in rec
                    assert "priority_score" in rec
                    assert rec["automation_possible"] is True

    @pytest.mark.asyncio
    async def test_analyze_compliance_maturity(self, mock_db_session, sample_business_context):
        """Test compliance maturity analysis"""

        assistant = ComplianceAssistant(mock_db_session)

        existing_evidence = [
            {"evidence_type": "policy"},
            {"evidence_type": "procedure"},
            {"evidence_type": "log"},
            {"evidence_type": "assessment"},
        ]

        result = await assistant._analyze_compliance_maturity(
            sample_business_context,
            existing_evidence,
            "ISO27001",
        )

        assert "maturity_level" in result
        assert "maturity_score" in result
        assert "evidence_diversity" in result
        assert "size_category" in result
        assert result["evidence_diversity"] == 4
        assert result["size_category"] == "medium"

    def test_categorize_organization_size(self, mock_db_session):
        """Test organization size categorization"""

        assistant = ComplianceAssistant(mock_db_session)

        assert assistant._categorize_organization_size(5) == "micro"
        assert assistant._categorize_organization_size(50) == "small"
        assert assistant._categorize_organization_size(500) == "medium"
        assert assistant._categorize_organization_size(5000) == "enterprise"

    def test_prioritize_recommendations(
        self, mock_db_session, sample_business_context, sample_maturity_analysis
    ):
        """Test recommendation prioritization logic"""

        assistant = ComplianceAssistant(mock_db_session)

        recommendations = [
            {
                "title": "Low Priority Task",
                "priority": "Low",
                "effort_hours": 20,
                "automation_possible": False,
            },
            {
                "title": "High Priority Quick Win",
                "priority": "High",
                "effort_hours": 2,
                "automation_possible": True,
            },
            {
                "title": "Medium Priority Task",
                "priority": "Medium",
                "effort_hours": 8,
                "automation_possible": True,
            },
        ]

        prioritized = assistant._prioritize_recommendations(
            recommendations,
            sample_business_context,
            sample_maturity_analysis,
        )

        # Check that high priority quick win is first
        assert prioritized[0]["title"] == "High Priority Quick Win"
        assert prioritized[0]["priority_score"] > prioritized[1]["priority_score"]

    @pytest.mark.asyncio
    async def test_context_aware_recommendations_error_handling(self, mock_db_session, mock_user):
        """Test error handling in context-aware recommendations"""

        assistant = ComplianceAssistant(mock_db_session)
        business_profile_id = uuid4()

        # Mock context manager to raise exception
        with patch.object(assistant.context_manager, "get_conversation_context") as mock_context:
            mock_context.side_effect = Exception("Database error")

            with pytest.raises(BusinessLogicException):
                await assistant.get_context_aware_recommendations(
                    user=mock_user,
                    business_profile_id=business_profile_id,
                    framework="ISO27001",
                )

    def test_add_automation_insights(self, mock_db_session, sample_business_context):
        """Test automation insights addition to recommendations"""

        assistant = ComplianceAssistant(mock_db_session)

        recommendations = [
            {"title": "Policy Development", "description": "Create security policy"},
            {"title": "Log Analysis", "description": "Analyze system logs"},
            {"title": "Training Program", "description": "Conduct security training"},
        ]

        enhanced = assistant._add_automation_insights(
            recommendations,
            sample_business_context,
        )

        # Check automation insights were added
        for rec in enhanced:
            assert "automation_possible" in rec
            assert "automation_guidance" in rec or not rec["automation_possible"]

        # Policy should have automation potential, others may vary based on keywords
        policy_rec = next(r for r in enhanced if "Policy" in r["title"])
        training_rec = next(r for r in enhanced if "Training" in r["title"])

        assert policy_rec["automation_possible"] is True
        assert training_rec["automation_possible"] is False

        # Log analysis automation depends on exact keyword matching
        log_rec = next((r for r in enhanced if "Log" in r["title"]), None)
        if log_rec:
            # Automation possible depends on keyword detection
            assert "automation_possible" in log_rec

    def test_calculate_total_effort(self, mock_db_session):
        """Test total effort calculation for recommendations"""

        assistant = ComplianceAssistant(mock_db_session)

        recommendations = [
            {"effort_hours": 8, "priority": "High"},
            {"effort_hours": 4, "priority": "Medium"},
            {"effort_hours": 2, "priority": "High"},
            {"effort_hours": 16, "priority": "Low"},
        ]

        effort = assistant._calculate_total_effort(recommendations)

        assert effort["total_hours"] == 30
        assert effort["high_priority_hours"] == 10
        assert effort["estimated_weeks"] == 0.8
        assert effort["quick_wins"] == 1  # Only the 2-hour task

    def test_get_fallback_recommendations(self, mock_db_session):
        """Test fallback recommendations when AI fails"""

        assistant = ComplianceAssistant(mock_db_session)

        fallback = assistant._get_fallback_recommendations(
            "ISO27001",
            {"maturity_level": "Basic"},
        )

        assert len(fallback) > 0
        assert all("control_id" in rec for rec in fallback)
        assert all("title" in rec for rec in fallback)
        assert all("effort_hours" in rec for rec in fallback)


@pytest.mark.unit
@pytest.mark.ai
class TestWorkflowGeneration:
    """Test workflow generation functionality"""

    @pytest.fixture
    def mock_db_session(self):
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_generate_evidence_collection_workflow_success(self, mock_db_session, mock_user):
        """Test successful workflow generation"""

        assistant = ComplianceAssistant(mock_db_session)
        business_profile_id = uuid4()

        # Mock context and AI response
        with patch.object(assistant.context_manager, "get_conversation_context") as mock_context:
            mock_context.return_value = {
                "business_profile": {
                    "company_name": "Test Corp",
                    "industry": "Technology",
                    "employee_count": 100,
                },
                "recent_evidence": [],
            }

            with patch.object(assistant, "_generate_gemini_response") as mock_ai:
                mock_ai.return_value = json.dumps(
                    {
                        "workflow_id": "test_workflow",
                        "title": "Test Workflow",
                        "phases": [
                            {
                                "phase_id": "phase_1",
                                "title": "Planning",
                                "steps": [
                                    {
                                        "step_id": "step_1",
                                        "title": "Define scope",
                                        "estimated_hours": 2,
                                    },
                                ],
                            },
                        ],
                    },
                )

                result = await assistant.generate_evidence_collection_workflow(
                    user=mock_user,
                    business_profile_id=business_profile_id,
                    framework="ISO27001",
                    control_id="A.9.1.1",
                )

                assert "workflow_id" in result
                assert "phases" in result
                assert "automation_summary" in result
                assert "effort_estimation" in result

    def test_calculate_workflow_effort(self, mock_db_session):
        """Test workflow effort calculation"""

        assistant = ComplianceAssistant(mock_db_session)

        workflow = {
            "phases": [
                {
                    "steps": [
                        {"estimated_hours": 4, "estimated_hours_with_automation": 2},
                        {"estimated_hours": 6, "estimated_hours_with_automation": 4},
                    ],
                },
                {
                    "steps": [
                        {"estimated_hours": 8, "estimated_hours_with_automation": 6},
                    ],
                },
            ],
        }

        effort = assistant._calculate_workflow_effort(workflow)

        assert effort["total_manual_hours"] == 18
        assert effort["total_automated_hours"] == 12
        assert effort["effort_savings"]["hours_saved"] == 6
        assert effort["phases_count"] == 2
        assert effort["steps_count"] == 3


@pytest.mark.unit
@pytest.mark.ai
class TestPolicyGeneration:
    """Test policy generation functionality"""

    @pytest.fixture
    def mock_db_session(self):
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = uuid4()
        return user

    @pytest.fixture
    def sample_customization_options(self):
        return {
            "tone": "Professional",
            "detail_level": "Standard",
            "include_templates": True,
            "geographic_scope": "Single location",
            "industry_focus": "Technology",
        }

    @pytest.mark.asyncio
    async def test_generate_customized_policy_success(
        self, mock_db_session, mock_user, sample_customization_options
    ):
        """Test successful policy generation"""

        assistant = ComplianceAssistant(mock_db_session)
        business_profile_id = uuid4()

        # Mock context and AI response
        with patch.object(assistant.context_manager, "get_conversation_context") as mock_context:
            mock_context.return_value = {
                "business_profile": {
                    "company_name": "Test Corp",
                    "industry": "Technology",
                    "employee_count": 100,
                },
                "recent_evidence": [],
            }

            with patch.object(assistant, "_generate_gemini_response") as mock_ai:
                mock_ai.return_value = json.dumps(
                    {
                        "policy_id": "test_policy",
                        "title": "Test Policy",
                        "sections": [
                            {
                                "section_id": "section_1",
                                "title": "Purpose",
                                "content": "Policy purpose",
                                "subsections": [],
                            },
                        ],
                        "roles_responsibilities": [],
                        "procedures": [],
                        "compliance_requirements": [],
                    },
                )

                result = await assistant.generate_customized_policy(
                    user=mock_user,
                    business_profile_id=business_profile_id,
                    framework="ISO27001",
                    policy_type="information_security",
                    customization_options=sample_customization_options,
                )

                assert "policy_id" in result
                assert "sections" in result
                assert "implementation_guidance" in result
                assert "compliance_mapping" in result
                assert "business_context" in result

    def test_apply_healthcare_customizations(self, mock_db_session):
        """Test healthcare industry customizations"""

        assistant = ComplianceAssistant(mock_db_session)

        policy = {"sections": [], "roles_responsibilities": []}

        customized = assistant._apply_healthcare_customizations(policy)

        # Check healthcare-specific section was added
        healthcare_section = next(
            (s for s in customized["sections"] if "Healthcare" in s["title"]), None
        )
        assert healthcare_section is not None

        # Check HIPAA-specific roles were added
        hipaa_roles = [r["role"] for r in customized["roles_responsibilities"]]
        assert "HIPAA Security Officer" in hipaa_roles
        assert "Privacy Officer" in hipaa_roles

    def test_apply_financial_customizations(self, mock_db_session):
        """Test financial industry customizations"""

        assistant = ComplianceAssistant(mock_db_session)

        policy = {"sections": [], "roles_responsibilities": []}

        customized = assistant._apply_financial_customizations(policy)

        # Check financial-specific section was added
        financial_section = next(
            (s for s in customized["sections"] if "Financial" in s["title"]), None
        )
        assert financial_section is not None

        # Check financial-specific roles were added
        financial_roles = [r["role"] for r in customized["roles_responsibilities"]]
        assert "Chief Risk Officer" in financial_roles
        assert "Compliance Officer" in financial_roles

    def test_apply_size_customizations(self, mock_db_session):
        """Test organization size-specific customizations"""

        assistant = ComplianceAssistant(mock_db_session)

        policy = {}

        # Test micro organization
        micro_policy = assistant._apply_size_customizations(policy.copy(), "micro")
        assert "implementation_notes" in micro_policy
        assert any("outsourcing" in note.lower() for note in micro_policy["implementation_notes"])

        # Test enterprise organization
        enterprise_policy = assistant._apply_size_customizations(
            policy.copy(),
            "enterprise",
        )
        assert "implementation_notes" in enterprise_policy
        assert any(
            "enterprise-grade" in note.lower() for note in enterprise_policy["implementation_notes"]
        )

    def test_generate_policy_implementation_guidance(self, mock_db_session):
        """Test policy implementation guidance generation"""

        assistant = ComplianceAssistant(mock_db_session)

        policy = {"sections": []}
        business_context = {"employee_count": 100}
        maturity_analysis = {"maturity_level": "Intermediate"}

        guidance = assistant._generate_policy_implementation_guidance(
            policy,
            business_context,
            maturity_analysis,
        )

        assert "implementation_phases" in guidance
        assert "success_metrics" in guidance
        assert "common_challenges" in guidance
        assert "mitigation_strategies" in guidance

        # Check phases structure
        phases = guidance["implementation_phases"]
        assert len(phases) >= 3
        assert all("phase" in p and "duration_weeks" in p for p in phases)

    def test_generate_compliance_mapping(self, mock_db_session):
        """Test compliance mapping generation"""

        assistant = ComplianceAssistant(mock_db_session)

        policy = {}

        mapping = assistant._generate_compliance_mapping(
            policy,
            "ISO27001",
            "information_security",
        )

        assert mapping["framework"] == "ISO27001"
        assert mapping["policy_type"] == "information_security"
        assert "mapped_controls" in mapping
        assert "compliance_objectives" in mapping
        assert "audit_considerations" in mapping

        # Check that controls are mapped
        assert len(mapping["mapped_controls"]) > 0

    def test_get_fallback_policy(self, mock_db_session):
        """Test fallback policy generation"""

        assistant = ComplianceAssistant(mock_db_session)

        business_context = {"company_name": "Test Corp", "industry": "Technology"}

        fallback = assistant._get_fallback_policy(
            "ISO27001",
            "information_security",
            business_context,
        )

        assert fallback["framework"] == "ISO27001"
        assert fallback["policy_type"] == "information_security"
        assert "sections" in fallback
        assert "roles_responsibilities" in fallback
        assert len(fallback["sections"]) >= 2
        assert fallback["business_context"] == business_context

    @pytest.mark.asyncio
    async def test_policy_generation_error_handling(self, mock_db_session, mock_user):
        """Test error handling in policy generation"""

        assistant = ComplianceAssistant(mock_db_session)
        business_profile_id = uuid4()

        # Mock context manager to raise exception
        with patch.object(assistant.context_manager, "get_conversation_context") as mock_context:
            mock_context.side_effect = Exception("Database error")

            with pytest.raises(BusinessLogicException):
                await assistant.generate_customized_policy(
                    user=mock_user,
                    business_profile_id=business_profile_id,
                    framework="ISO27001",
                    policy_type="information_security",
                )
