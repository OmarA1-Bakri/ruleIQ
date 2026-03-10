"""Tests for api.schemas.chat — 36 Pydantic models for chat/conversation endpoints."""
import pytest
from datetime import datetime
from uuid import uuid4, UUID

from api.schemas.chat import (
    SendMessageRequest,
    MessageResponse,
    ConversationSummary,
    ConversationResponse,
    CreateConversationRequest,
    ConversationListResponse,
    EvidenceRecommendationRequest,
    EvidenceRecommendationResponse,
    ComplianceAnalysisRequest,
    ComplianceAnalysisResponse,
    ContextAwareRecommendationRequest,
    BusinessContextSummary,
    CurrentStatusSummary,
    RecommendationItem,
    EffortEstimation,
    ContextAwareRecommendationResponse,
    WorkflowGenerationRequest,
    WorkflowStep,
    WorkflowPhase,
    AutomationSummary,
    WorkflowEffortEstimation,
    WorkflowResponse,
    PolicyGenerationRequest,
    PolicySubsection,
    PolicySection,
    RoleResponsibility,
    PolicyProcedure,
    ComplianceRequirement,
    BusinessContextInfo,
    ImplementationPhase,
    PolicyImplementationGuidance,
    ComplianceMapping,
    PolicyResponse,
    SmartGuidanceRequest,
    GuidanceCurrentStatus,
    SmartGuidanceResponse,
)


# ── SendMessageRequest ──────────────────────────────────────────

class TestSendMessageRequest:
    def test_valid(self):
        r = SendMessageRequest(message="Hello")
        assert r.message == "Hello"

    def test_empty_message_rejected(self):
        with pytest.raises(Exception):
            SendMessageRequest(message="")

    def test_max_length(self):
        r = SendMessageRequest(message="x" * 2000)
        assert len(r.message) == 2000

    def test_exceeds_max_length(self):
        with pytest.raises(Exception):
            SendMessageRequest(message="x" * 2001)


# ── MessageResponse ─────────────────────────────────────────────

class TestMessageResponse:
    def test_valid(self):
        uid = uuid4()
        r = MessageResponse(
            id=uid, role="user", content="hi",
            sequence_number=1, created_at=datetime.now(),
        )
        assert r.id == uid
        assert r.role == "user"

    def test_assistant_role(self):
        r = MessageResponse(
            id=uuid4(), role="assistant", content="hey",
            sequence_number=2, created_at=datetime.now(),
        )
        assert r.role == "assistant"

    def test_invalid_role(self):
        with pytest.raises(Exception):
            MessageResponse(
                id=uuid4(), role="admin", content="hi",
                sequence_number=1, created_at=datetime.now(),
            )

    def test_metadata_alias(self):
        r = MessageResponse(
            id=uuid4(), role="user", content="hi",
            message_metadata={"key": "val"},
            sequence_number=1, created_at=datetime.now(),
        )
        assert r.metadata == {"key": "val"}


# ── ConversationSummary ─────────────────────────────────────────

class TestConversationSummary:
    def test_valid(self):
        r = ConversationSummary(
            id=uuid4(), title="Chat", status="active",
            message_count=5, created_at=datetime.now(),
        )
        assert r.message_count == 5
        assert r.last_message_at is None

    def test_with_last_message(self):
        now = datetime.now()
        r = ConversationSummary(
            id=uuid4(), title="T", status="active",
            message_count=1, last_message_at=now, created_at=now,
        )
        assert r.last_message_at == now


# ── ConversationResponse ────────────────────────────────────────

class TestConversationResponse:
    def test_valid(self):
        now = datetime.now()
        r = ConversationResponse(
            id=uuid4(), title="T", status="active",
            messages=[], created_at=now, updated_at=now,
        )
        assert r.messages == []


# ── CreateConversationRequest ───────────────────────────────────

class TestCreateConversationRequest:
    def test_defaults(self):
        r = CreateConversationRequest()
        assert r.title is None
        assert r.initial_message is None

    def test_with_values(self):
        r = CreateConversationRequest(title="My Chat", initial_message="Hello")
        assert r.title == "My Chat"

    def test_title_too_long(self):
        with pytest.raises(Exception):
            CreateConversationRequest(title="x" * 256)

    def test_message_too_long(self):
        with pytest.raises(Exception):
            CreateConversationRequest(initial_message="x" * 2001)


# ── ConversationListResponse ────────────────────────────────────

class TestConversationListResponse:
    def test_valid(self):
        r = ConversationListResponse(conversations=[], total=0, page=1, per_page=10)
        assert r.total == 0


# ── Evidence Recommendation ─────────────────────────────────────

class TestEvidenceRecommendation:
    def test_request_defaults(self):
        r = EvidenceRecommendationRequest()
        assert r.framework is None

    def test_response(self):
        r = EvidenceRecommendationResponse(
            framework="ISO27001", recommendations="Do X",
            generated_at=datetime.now(),
        )
        assert r.framework == "ISO27001"


# ── ComplianceAnalysis ──────────────────────────────────────────

class TestComplianceAnalysis:
    def test_request_valid(self):
        r = ComplianceAnalysisRequest(framework="GDPR")
        assert r.framework == "GDPR"

    def test_request_empty_framework(self):
        with pytest.raises(Exception):
            ComplianceAnalysisRequest(framework="")

    def test_response(self):
        r = ComplianceAnalysisResponse(
            framework="GDPR", completion_percentage=85.0,
            evidence_collected=10, evidence_types=["doc"],
            recent_activity=5, recommendations=[],
            critical_gaps=[], risk_level="LOW",
        )
        assert r.completion_percentage == 85.0


# ── ContextAwareRecommendation ──────────────────────────────────

class TestContextAwareRecommendation:
    def test_request_defaults(self):
        r = ContextAwareRecommendationRequest(framework="ISO27001")
        assert r.context_type == "comprehensive"

    def test_business_context_summary(self):
        r = BusinessContextSummary(
            company_name="Acme", industry="tech",
            employee_count=50, maturity_level="basic",
        )
        assert r.company_name == "Acme"

    def test_current_status_summary(self):
        r = CurrentStatusSummary(
            completion_percentage=50.0, evidence_collected=5,
            critical_gaps_count=3,
        )
        assert r.critical_gaps_count == 3

    def test_recommendation_item(self):
        r = RecommendationItem(
            control_id="A.5.1", title="Policy", description="Create policy",
            priority="HIGH", effort_hours=10, automation_possible=True,
            business_justification="Required", implementation_steps=["Do it"],
        )
        assert r.automation_possible is True
        assert r.priority_score is None

    def test_effort_estimation(self):
        r = EffortEstimation(
            total_hours=100, high_priority_hours=40,
            estimated_weeks=5.0, quick_wins=3,
        )
        assert r.quick_wins == 3

    def test_full_response(self):
        biz = BusinessContextSummary(
            company_name="X", industry="fin", employee_count=10, maturity_level="low",
        )
        status = CurrentStatusSummary(
            completion_percentage=20.0, evidence_collected=2, critical_gaps_count=5,
        )
        effort = EffortEstimation(
            total_hours=80, high_priority_hours=30, estimated_weeks=4.0, quick_wins=2,
        )
        r = ContextAwareRecommendationResponse(
            framework="SOC2", business_context=biz, current_status=status,
            recommendations=[], next_steps=["Step 1"], estimated_effort=effort,
            generated_at="2024-01-01",
        )
        assert r.framework == "SOC2"


# ── Workflow Models ─────────────────────────────────────────────

class TestWorkflowModels:
    def test_workflow_generation_request(self):
        r = WorkflowGenerationRequest(framework="GDPR")
        assert r.control_id is None
        assert r.workflow_type == "comprehensive"

    def test_workflow_step(self):
        r = WorkflowStep(
            step_id="s1", title="Plan", description="Planning phase",
            deliverables=["doc"], responsible_role="PM",
            estimated_hours=8, dependencies=[], tools_needed=[],
            validation_criteria=["Complete"],
        )
        assert r.automation_opportunities is None
        assert r.estimated_hours_with_automation is None

    def test_workflow_phase(self):
        step = WorkflowStep(
            step_id="s1", title="X", description="Y",
            deliverables=[], responsible_role="Dev",
            estimated_hours=4, dependencies=[], tools_needed=[],
            validation_criteria=[],
        )
        phase = WorkflowPhase(
            phase_id="p1", title="Phase 1", description="Init",
            estimated_hours=4, steps=[step],
        )
        assert len(phase.steps) == 1

    def test_automation_summary(self):
        r = AutomationSummary(
            automation_percentage=60.0, effort_savings_percentage=40.0,
            manual_hours=100, automated_hours=60, hours_saved=40,
            high_automation_steps=3, total_steps=10,
        )
        assert r.hours_saved == 40

    def test_workflow_effort_estimation(self):
        r = WorkflowEffortEstimation(
            total_manual_hours=200, total_automated_hours=120,
            estimated_weeks_manual=10.0, estimated_weeks_automated=6.0,
            phases_count=3, steps_count=15,
            effort_savings={"hours": 80},
        )
        assert r.phases_count == 3

    def test_workflow_response(self):
        auto = AutomationSummary(
            automation_percentage=50.0, effort_savings_percentage=30.0,
            manual_hours=80, automated_hours=40, hours_saved=40,
            high_automation_steps=2, total_steps=8,
        )
        effort = WorkflowEffortEstimation(
            total_manual_hours=80, total_automated_hours=40,
            estimated_weeks_manual=4.0, estimated_weeks_automated=2.0,
            phases_count=2, steps_count=8, effort_savings={},
        )
        r = WorkflowResponse(
            workflow_id="w1", title="WF", description="Desc",
            framework="ISO27001", control_id="A.5", created_at="now",
            phases=[], automation_summary=auto, effort_estimation=effort,
        )
        assert r.workflow_id == "w1"


# ── Policy Models ───────────────────────────────────────────────

class TestPolicyModels:
    def test_policy_generation_request(self):
        r = PolicyGenerationRequest(
            framework="GDPR", policy_type="privacy", tone="Professional",
        )
        assert r.include_templates is True
        assert r.geographic_scope == "Single location"

    def test_policy_subsection(self):
        r = PolicySubsection(
            subsection_id="ss1", title="Scope", content="All data", controls=["C1"],
        )
        assert r.subsection_id == "ss1"

    def test_policy_section(self):
        sub = PolicySubsection(subsection_id="ss1", title="T", content="C", controls=[])
        r = PolicySection(section_id="s1", title="Intro", content="Content", subsections=[sub])
        assert len(r.subsections) == 1

    def test_role_responsibility(self):
        r = RoleResponsibility(role="DPO", responsibilities=["Oversee GDPR"])
        assert r.role == "DPO"

    def test_policy_procedure(self):
        r = PolicyProcedure(procedure_id="p1", title="Breach Response", steps=["Notify", "Log"])
        assert len(r.steps) == 2

    def test_compliance_requirement(self):
        r = ComplianceRequirement(
            requirement_id="r1", description="Encrypt data",
            control_reference="A.10.1",
        )
        assert r.control_reference == "A.10.1"

    def test_business_context_info(self):
        r = BusinessContextInfo(
            company_name="Acme", industry="Finance",
            employee_count=200, customization_applied="Standard",
        )
        assert r.employee_count == 200

    def test_implementation_phase(self):
        r = ImplementationPhase(phase="Phase 1", duration_weeks=4, activities=["Plan"])
        assert r.duration_weeks == 4

    def test_policy_implementation_guidance(self):
        phase = ImplementationPhase(phase="P1", duration_weeks=2, activities=["Do"])
        r = PolicyImplementationGuidance(
            implementation_phases=[phase], success_metrics=["90% compliance"],
            common_challenges=["Budget"], mitigation_strategies=["Phased rollout"],
        )
        assert len(r.implementation_phases) == 1

    def test_compliance_mapping(self):
        r = ComplianceMapping(
            framework="GDPR", policy_type="privacy",
            mapped_controls=["Art.5"], compliance_objectives=["Lawfulness"],
            audit_considerations=["Review annually"],
        )
        assert r.framework == "GDPR"

    def test_full_policy_response(self):
        section = PolicySection(
            section_id="s1", title="T", content="C", subsections=[],
        )
        role = RoleResponsibility(role="PM", responsibilities=["Manage"])
        proc = PolicyProcedure(procedure_id="p1", title="P", steps=["S"])
        req = ComplianceRequirement(
            requirement_id="r1", description="D", control_reference="C.1",
        )
        biz = BusinessContextInfo(
            company_name="X", industry="Tech", employee_count=10,
            customization_applied="Basic",
        )
        phase = ImplementationPhase(phase="P1", duration_weeks=1, activities=["A"])
        guidance = PolicyImplementationGuidance(
            implementation_phases=[phase], success_metrics=["M"],
            common_challenges=["C"], mitigation_strategies=["S"],
        )
        mapping = ComplianceMapping(
            framework="ISO", policy_type="sec", mapped_controls=["A.1"],
            compliance_objectives=["O"], audit_considerations=["A"],
        )
        r = PolicyResponse(
            policy_id="pol1", title="Policy", version="1.0",
            effective_date="2024-01-01", framework="ISO",
            policy_type="security", created_at="2024-01-01",
            sections=[section], roles_responsibilities=[role],
            procedures=[proc], compliance_requirements=[req],
            business_context=biz, implementation_guidance=guidance,
            compliance_mapping=mapping,
        )
        assert r.implementation_notes is None


# ── Smart Guidance ──────────────────────────────────────────────

class TestSmartGuidance:
    def test_request_defaults(self):
        r = SmartGuidanceRequest(framework="GDPR")
        assert r.guidance_type == "getting_started"

    def test_guidance_current_status(self):
        r = GuidanceCurrentStatus(
            completion_percentage=30.0, maturity_level="basic",
            critical_gaps_count=7,
        )
        assert r.maturity_level == "basic"

    def test_full_response(self):
        status = GuidanceCurrentStatus(
            completion_percentage=40.0, maturity_level="mid",
            critical_gaps_count=4,
        )
        effort = EffortEstimation(
            total_hours=50, high_priority_hours=20,
            estimated_weeks=3.0, quick_wins=2,
        )
        r = SmartGuidanceResponse(
            framework="ISO27001", guidance_type="getting_started",
            current_status=status,
            personalized_roadmap=[], next_immediate_steps=["Start"],
            effort_estimation=effort, quick_wins=[],
            automation_opportunities=[], generated_at="2024-01-01",
        )
        assert len(r.next_immediate_steps) == 1
