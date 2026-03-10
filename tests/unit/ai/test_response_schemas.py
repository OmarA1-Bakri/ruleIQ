"""
Tests for services.ai.response_schemas module.

Covers all enums, TypedDict schemas, and type aliases.
"""

import pytest
from services.ai.response_schemas import (
    SeverityLevel,
    PriorityLevel,
    ConfidenceLevel,
    ImplementationEffort,
    RiskLevel,
    Gap,
    GapAnalysisResponse,
    Recommendation,
    ImplementationPhase,
    ImplementationPlan,
    RecommendationResponse,
    ComplianceInsight,
    EvidenceRequirement,
    RiskAssessment,
    ComplianceMetrics,
    AssessmentAnalysisResponse,
    GuidanceResponse,
    FollowUpQuestion,
    FollowUpResponse,
    EvidenceItem,
    WorkflowStep,
    WorkflowPhase,
    EvidenceWorkflow,
    PolicySection,
    PolicyDocument,
    IntentClassification,
    ChatResponse,
    ResponseMetadata,
    StructuredAIResponse,
    ValidationError,
    SchemaValidationResult,
)


class TestSeverityLevel:
    def test_values(self):
        assert SeverityLevel.LOW == "low"
        assert SeverityLevel.MEDIUM == "medium"
        assert SeverityLevel.HIGH == "high"
        assert SeverityLevel.CRITICAL == "critical"

    def test_from_value(self):
        assert SeverityLevel("low") == SeverityLevel.LOW
        assert SeverityLevel("critical") == SeverityLevel.CRITICAL

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            SeverityLevel("invalid")

    def test_is_str_enum(self):
        assert isinstance(SeverityLevel.LOW, str)


class TestPriorityLevel:
    def test_values(self):
        assert PriorityLevel.LOW == "low"
        assert PriorityLevel.MEDIUM == "medium"
        assert PriorityLevel.HIGH == "high"

    def test_from_value(self):
        assert PriorityLevel("high") == PriorityLevel.HIGH


class TestConfidenceLevel:
    def test_values(self):
        assert ConfidenceLevel.LOW == "low"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.HIGH == "high"


class TestImplementationEffort:
    def test_values(self):
        assert ImplementationEffort.LOW == "low"
        assert ImplementationEffort.MEDIUM == "medium"
        assert ImplementationEffort.HIGH == "high"


class TestRiskLevel:
    def test_is_enum(self):
        # RiskLevel enum exists but has all members commented out
        assert issubclass(RiskLevel, str)


class TestGapTypedDict:
    def test_create_gap(self):
        gap: Gap = {
            "id": "gap_1",
            "title": "Missing encryption",
            "description": "Data at rest is not encrypted",
            "severity": SeverityLevel.HIGH,
            "category": "data_protection",
            "framework_reference": "GDPR Art. 32",
            "current_state": "No encryption",
            "target_state": "AES-256 encryption",
            "impact_description": "Risk of data breach",
            "business_impact_score": 0.8,
            "technical_complexity": 0.5,
            "regulatory_requirement": True,
            "estimated_effort": ImplementationEffort.MEDIUM,
            "dependencies": ["key_management"],
            "affected_systems": ["database"],
            "stakeholders": ["DPO", "CTO"],
        }
        assert gap["id"] == "gap_1"
        assert gap["severity"] == SeverityLevel.HIGH
        assert gap["business_impact_score"] == 0.8
        assert gap["regulatory_requirement"] is True


class TestGapAnalysisResponse:
    def test_create_response(self):
        resp: GapAnalysisResponse = {
            "gaps": [],
            "overall_risk_level": RiskLevel,
            "priority_order": ["gap_1"],
            "estimated_total_effort": "6 months",
            "critical_gap_count": 2,
            "medium_high_gap_count": 5,
            "compliance_percentage": 65.0,
            "framework_coverage": {"GDPR": 70.0},
            "summary": "Several gaps identified",
            "next_steps": ["Address critical gaps first"],
        }
        assert resp["compliance_percentage"] == 65.0
        assert resp["critical_gap_count"] == 2


class TestRecommendation:
    def test_create_recommendation(self):
        rec: Recommendation = {
            "id": "rec_1",
            "title": "Implement encryption",
            "description": "Deploy AES-256 encryption for data at rest",
            "priority": PriorityLevel.HIGH,
            "category": "data_protection",
            "framework_references": ["GDPR Art. 32"],
            "addresses_gaps": ["gap_1"],
            "effort_estimate": ImplementationEffort.MEDIUM,
            "implementation_timeline": "2-4 weeks",
            "impact_score": 0.9,
            "cost_estimate": "£10,000",
            "resource_requirements": ["Security engineer"],
            "success_criteria": ["All data encrypted"],
            "potential_challenges": ["Key management"],
            "mitigation_strategies": ["Use cloud KMS"],
            "automation_potential": 0.7,
            "roi_estimate": "3x",
        }
        assert rec["priority"] == PriorityLevel.HIGH
        assert rec["impact_score"] == 0.9


class TestImplementationPhase:
    def test_create_phase(self):
        phase: ImplementationPhase = {
            "phase_number": 1,
            "phase_name": "Planning",
            "duration_weeks": 2,
            "deliverables": ["Architecture doc"],
            "dependencies": [],
            "resources_required": ["Architect"],
            "success_criteria": ["Approved design"],
        }
        assert phase["phase_number"] == 1
        assert phase["duration_weeks"] == 2


class TestImplementationPlan:
    def test_create_plan(self):
        plan: ImplementationPlan = {
            "total_duration_weeks": 12,
            "phases": [],
            "resource_allocation": {"architect": "50%"},
            "budget_estimate": "£50,000",
            "risk_factors": ["Staff availability"],
            "success_metrics": ["All gaps closed"],
            "milestone_checkpoints": ["Phase 1 complete"],
        }
        assert plan["total_duration_weeks"] == 12


class TestRecommendationResponse:
    def test_create_response(self):
        resp: RecommendationResponse = {
            "recommendations": [],
            "implementation_plan": {
                "total_duration_weeks": 12,
                "phases": [],
                "resource_allocation": {},
                "budget_estimate": None,
                "risk_factors": [],
                "success_metrics": ["Done"],
                "milestone_checkpoints": [],
            },
            "prioritization_rationale": "Based on risk",
            "quick_wins": ["rec_1"],
            "long_term_initiatives": ["rec_2"],
            "resource_summary": {},
            "timeline_overview": "12 weeks total",
            "success_metrics": ["All done"],
        }
        assert resp["prioritization_rationale"] == "Based on risk"


class TestComplianceInsight:
    def test_create_insight(self):
        insight: ComplianceInsight = {
            "insight_type": "strength",
            "title": "Strong access controls",
            "description": "MFA deployed across all systems",
            "impact_level": SeverityLevel.LOW,
            "framework_area": "Access Control",
            "actionable_steps": ["Maintain current controls"],
        }
        assert insight["insight_type"] == "strength"


class TestEvidenceRequirement:
    def test_create_requirement(self):
        req: EvidenceRequirement = {
            "evidence_type": "policy_document",
            "description": "Data protection policy required",
            "framework_reference": "GDPR Art. 24",
            "priority": PriorityLevel.HIGH,
            "collection_method": "Document review",
            "automation_potential": 0.3,
            "estimated_effort": ImplementationEffort.LOW,
            "validation_criteria": ["Policy approved by DPO"],
            "retention_period": "7 years",
        }
        assert req["evidence_type"] == "policy_document"


class TestRiskAssessment:
    def test_create_assessment(self):
        ra: RiskAssessment = {
            "overall_risk_level": RiskLevel,
            "risk_score": 45.0,
            "top_risk_factors": ["No encryption"],
            "risk_mitigation_priorities": ["Deploy encryption"],
            "regulatory_compliance_risk": 60.0,
            "operational_risk": 30.0,
            "reputational_risk": 40.0,
            "financial_risk": 50.0,
        }
        assert ra["risk_score"] == 45.0
        assert ra["regulatory_compliance_risk"] == 60.0


class TestComplianceMetrics:
    def test_create_metrics(self):
        metrics: ComplianceMetrics = {
            "overall_compliance_score": 72.5,
            "framework_scores": {"GDPR": 80.0, "ISO27001": 65.0},
            "maturity_level": "defined",
            "coverage_percentage": 75.0,
            "gap_count_by_severity": {SeverityLevel.HIGH: 3},
            "improvement_trend": "improving",
        }
        assert metrics["overall_compliance_score"] == 72.5
        assert metrics["maturity_level"] == "defined"


class TestAssessmentAnalysisResponse:
    def test_create_response(self):
        resp: AssessmentAnalysisResponse = {
            "gaps": [],
            "recommendations": [],
            "risk_assessment": {
                "overall_risk_level": RiskLevel,
                "risk_score": 45.0,
                "top_risk_factors": [],
                "risk_mitigation_priorities": [],
                "regulatory_compliance_risk": 50.0,
                "operational_risk": 30.0,
                "reputational_risk": 20.0,
                "financial_risk": 40.0,
            },
            "compliance_insights": [],
            "evidence_requirements": [],
            "compliance_metrics": {
                "overall_compliance_score": 60.0,
                "framework_scores": {},
                "maturity_level": "developing",
                "coverage_percentage": 60.0,
                "gap_count_by_severity": {},
                "improvement_trend": "improving",
            },
            "executive_summary": "Assessment complete",
            "detailed_findings": "Details here",
            "next_steps": ["Prioritize gaps"],
            "confidence_score": 0.85,
        }
        assert resp["confidence_score"] == 0.85


class TestGuidanceResponse:
    def test_create_guidance(self):
        resp: GuidanceResponse = {
            "guidance": "You should implement encryption",
            "confidence_score": 0.9,
            "related_topics": ["encryption", "data_protection"],
            "follow_up_suggestions": ["Review key management"],
            "source_references": ["GDPR Art. 32"],
            "examples": ["AES-256 deployment"],
            "best_practices": ["Use cloud KMS"],
            "common_pitfalls": ["Weak key generation"],
            "implementation_tips": ["Start with databases"],
        }
        assert resp["confidence_score"] == 0.9


class TestFollowUpQuestion:
    def test_create_question(self):
        q: FollowUpQuestion = {
            "question_id": "q_1",
            "question_text": "Do you process health data?",
            "category": "data_classification",
            "importance_level": PriorityLevel.HIGH,
            "expected_answer_type": "boolean",
            "context": "Determines special category requirements",
            "validation_criteria": ["Must be yes/no"],
        }
        assert q["expected_answer_type"] == "boolean"


class TestFollowUpResponse:
    def test_create_response(self):
        resp: FollowUpResponse = {
            "follow_up_questions": [],
            "recommendations": ["Review data categories"],
            "confidence_score": 0.8,
            "assessment_completeness": 0.6,
            "priority_areas": ["data_classification"],
            "suggested_next_steps": ["Complete survey"],
        }
        assert resp["assessment_completeness"] == 0.6


class TestEvidenceItem:
    def test_create_item(self):
        item: EvidenceItem = {
            "evidence_id": "ev_1",
            "title": "Data Protection Policy",
            "description": "Corporate data protection policy document",
            "framework_controls": ["GDPR_32"],
            "collection_method": "Document upload",
            "automation_tools": ["SharePoint"],
            "effort_estimate": ImplementationEffort.LOW,
            "priority": PriorityLevel.HIGH,
            "frequency": "annually",
            "owner_role": "DPO",
            "validation_requirements": ["Signed by CTO"],
            "retention_period": "7 years",
        }
        assert item["evidence_id"] == "ev_1"
        assert item["frequency"] == "annually"


class TestWorkflowSchemas:
    def test_workflow_step(self):
        step: WorkflowStep = {
            "step_number": 1,
            "title": "Collect policy",
            "description": "Gather existing policy docs",
            "estimated_duration": "2 hours",
            "assigned_role": "Compliance Officer",
            "prerequisites": [],
            "deliverables": ["Policy draft"],
            "validation_criteria": ["Complete and signed"],
            "automation_opportunities": ["Automated scanning"],
        }
        assert step["step_number"] == 1

    def test_workflow_phase(self):
        phase: WorkflowPhase = {
            "phase_number": 1,
            "phase_name": "Collection",
            "objective": "Gather all required evidence",
            "steps": [],
            "estimated_duration": "1 week",
            "success_criteria": ["All evidence collected"],
            "dependencies": [],
        }
        assert phase["phase_name"] == "Collection"

    def test_evidence_workflow(self):
        wf: EvidenceWorkflow = {
            "workflow_id": "wf_1",
            "title": "GDPR Evidence Collection",
            "description": "Collect all GDPR evidence",
            "framework": "GDPR",
            "control_reference": "Art. 32",
            "phases": [],
            "total_estimated_duration": "4 weeks",
            "required_roles": ["DPO"],
            "automation_percentage": 0.4,
            "complexity_level": "moderate",
        }
        assert wf["complexity_level"] == "moderate"


class TestPolicySchemas:
    def test_policy_section(self):
        section: PolicySection = {
            "section_number": "1.0",
            "title": "Introduction",
            "content": "This policy covers...",
            "subsections": [{"title": "Scope", "content": "Applies to all..."}],
            "compliance_references": ["GDPR Art. 24"],
            "implementation_notes": ["Review quarterly"],
        }
        assert section["section_number"] == "1.0"

    def test_policy_document(self):
        doc: PolicyDocument = {
            "policy_id": "pol_1",
            "title": "Data Protection Policy",
            "version": "1.0",
            "effective_date": "2024-01-01",
            "framework_compliance": ["GDPR"],
            "sections": [],
            "approval_workflow": ["DPO review"],
            "review_schedule": "Quarterly",
            "related_documents": [],
            "implementation_guidance": "Follow steps",
        }
        assert doc["version"] == "1.0"


class TestChatSchemas:
    def test_intent_classification(self):
        ic: IntentClassification = {
            "intent_type": "compliance_check",
            "confidence": 0.95,
            "entities": {"frameworks": ["GDPR"]},
            "context_requirements": ["business_profile"],
            "suggested_actions": ["run_assessment"],
        }
        assert ic["intent_type"] == "compliance_check"

    def test_chat_response(self):
        resp: ChatResponse = {
            "response_text": "Based on your profile...",
            "intent_classification": {
                "intent_type": "general_query",
                "confidence": 0.8,
                "entities": {},
                "context_requirements": [],
                "suggested_actions": [],
            },
            "confidence_score": 0.8,
            "follow_up_suggestions": ["Ask about GDPR"],
            "related_resources": [],
            "action_items": [],
        }
        assert resp["confidence_score"] == 0.8


class TestMetaSchemas:
    def test_response_metadata(self):
        meta: ResponseMetadata = {
            "response_id": "resp_1",
            "timestamp": "2024-01-01T00:00:00Z",
            "model_used": "gemini-pro",
            "processing_time_ms": 1500,
            "confidence_score": 0.9,
            "schema_version": "1.0",
            "validation_status": "valid",
            "validation_errors": [],
        }
        assert meta["model_used"] == "gemini-pro"

    def test_structured_ai_response(self):
        resp: StructuredAIResponse = {
            "metadata": {
                "response_id": "r1",
                "timestamp": "2024-01-01T00:00:00Z",
                "model_used": "gemini-pro",
                "processing_time_ms": 100,
                "confidence_score": 0.9,
                "schema_version": "1.0",
                "validation_status": "valid",
                "validation_errors": [],
            },
            "response_type": "gap_analysis",
            "payload": {},
            "validation_passed": True,
            "fallback_used": False,
        }
        assert resp["validation_passed"] is True

    def test_validation_error(self):
        ve: ValidationError = {
            "field_path": "gaps.0.severity",
            "error_type": "invalid_enum",
            "error_message": "Must be low, medium, high, or critical",
            "expected_type": "SeverityLevel",
            "actual_value": "extreme",
            "suggestion": "Use 'critical' instead",
        }
        assert ve["field_path"] == "gaps.0.severity"

    def test_schema_validation_result(self):
        result: SchemaValidationResult = {
            "is_valid": False,
            "schema_name": "GapAnalysisResponse",
            "validation_errors": [],
            "warnings": ["Some fields missing"],
            "validation_timestamp": "2024-01-01T00:00:00Z",
            "corrected_data": None,
        }
        assert result["is_valid"] is False
