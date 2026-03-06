"""Test Golden Dataset schemas."""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from services.ai.evaluation.schemas.common import RegCitation, SourceMeta, TemporalValidity
from services.ai.evaluation.schemas.compliance_scenario import ComplianceScenario, ExpectedOutcome
from services.ai.evaluation.schemas.evidence_case import EvidenceCase, EvidenceItem, FrameworkMap
from services.ai.evaluation.schemas.regulatory_qa import RegulatoryQAPair

from tests.test_constants import MAX_RETRIES

# Constants


class TestCommonSchemas:
    """Test common schema definitions."""

    def test_reg_citation_minimal(self):
        """Test RegCitation with minimal required fields."""
        citation = RegCitation(framework="GDPR", citation="Article 5")
        assert citation.framework == "GDPR"
        assert citation.citation == "Article 5"
        assert citation.url is None
        assert citation.jurisdiction is None
        assert citation.notes is None

    def test_reg_citation_full(self):
        """Test RegCitation with all fields."""
        citation = RegCitation(
            framework="GDPR",
            citation="Article 5",
            url="https://gdpr.eu/article-5",
            jurisdiction="EU",
            notes="Processing principles",
        )
        assert citation.framework == "GDPR"
        assert citation.url == "https://gdpr.eu/article-5"
        assert citation.jurisdiction == "EU"
        assert citation.notes == "Processing principles"

    def test_source_meta(self):
        """Test SourceMeta schema."""
        now = datetime.now()
        meta = SourceMeta(
            source_kind="regulatory_document",
            method="manual_extraction",
            created_by="compliance_team",
            created_at=now,
            version="1.0.0",
        )
        assert meta.source_kind == "regulatory_document"
        assert meta.method == "manual_extraction"
        assert meta.created_by == "compliance_team"
        assert meta.created_at == now
        assert meta.version == "1.0.0"

    def test_temporal_validity_valid(self):
        """Test TemporalValidity with valid dates."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        temporal = TemporalValidity(effective_from=start, effective_to=end)
        assert temporal.effective_from == start
        assert temporal.effective_to == end

    def test_temporal_validity_no_end(self):
        """Test TemporalValidity without end date."""
        start = datetime(2024, 1, 1)
        temporal = TemporalValidity(effective_from=start)
        assert temporal.effective_from == start
        assert temporal.effective_to is None

    def test_temporal_validity_invalid(self):
        """Test TemporalValidity with invalid dates (end before start)."""
        start = datetime(2024, 12, 31)
        end = datetime(2024, 1, 1)
        with pytest.raises(ValueError, match="effective_to must be >= effective_from"):
            TemporalValidity(effective_from=start, effective_to=end)


class TestComplianceScenario:
    """Test ComplianceScenario schema."""

    def test_compliance_scenario_minimal(self):
        """Test ComplianceScenario with minimal required fields."""
        scenario = ComplianceScenario(
            id="CS001",
            title="Data retention compliance",
            description="Ensure data is retained for required period",
            obligation_id="OBL001",
            triggers=["data_collection", "data_storage"],
            expected_outcome=ExpectedOutcome(
                outcome_code="COMPLIANT", details={"retention_period": "7_years"}
            ),
            temporal=TemporalValidity(effective_from=datetime.now()),
            version="1.0.0",
            source=SourceMeta(
                source_kind="manual",
                method="expert_review",
                created_by="compliance_team",
                created_at=datetime.now(),
            ),
            created_at=datetime.now(),
        )
        assert scenario.id == "CS001"
        assert scenario.obligation_id == "OBL001"
        assert len(scenario.triggers) == 2
        assert scenario.expected_outcome.outcome_code == "COMPLIANT"

    def test_compliance_scenario_full(self):
        """Test ComplianceScenario with all fields."""
        scenario = ComplianceScenario(
            id="CS002",
            title="GDPR consent management",
            description="Manage user consent under GDPR",
            obligation_id="OBL002",
            sector="healthcare",
            jurisdiction="EU",
            regulation_refs=[RegCitation(framework="GDPR", citation="Article 7")],
            triggers=["user_registration", "consent_update"],
            expected_outcome=ExpectedOutcome(
                outcome_code="REQUIRES_CONSENT",
                details={"consent_type": "explicit", "retention": "until_withdrawn"},
            ),
            temporal=TemporalValidity(effective_from=datetime(2024, 1, 1)),
            tags=["gdpr", "consent", "privacy"],
            version="1.0.0",
            source=SourceMeta(
                source_kind="regulatory_document",
                method="automated_extraction",
                created_by="ai_system",
                created_at=datetime.now(),
            ),
            created_at=datetime.now(),
        )
        assert scenario.sector == "healthcare"
        assert scenario.jurisdiction == "EU"
        assert len(scenario.regulation_refs) == 1
        assert len(scenario.tags) == MAX_RETRIES

    def test_compliance_scenario_missing_triggers(self):
        """Test ComplianceScenario validation - requires triggers."""
        with pytest.raises(ValueError, match="triggers cannot be empty"):
            ComplianceScenario(
                id="CS003",
                title="Invalid scenario",
                description="Missing triggers",
                obligation_id="OBL003",
                triggers=[],
                expected_outcome=ExpectedOutcome(outcome_code="COMPLIANT", details={}),
                temporal=TemporalValidity(effective_from=datetime.now()),
                version="1.0.0",
                source=SourceMeta(
                    source_kind="manual",
                    method="expert_review",
                    created_by="compliance_team",
                    created_at=datetime.now(),
                ),
                created_at=datetime.now(),
            )

    def test_compliance_scenario_missing_outcome_code(self):
        """Test ComplianceScenario validation - requires outcome_code."""
        with pytest.raises(ValueError, match="outcome_code is required"):
            ComplianceScenario(
                id="CS004",
                title="Invalid scenario",
                description="Missing outcome code",
                obligation_id="OBL004",
                triggers=["trigger1"],
                expected_outcome=ExpectedOutcome(outcome_code="", details={}),
                temporal=TemporalValidity(effective_from=datetime.now()),
                version="1.0.0",
                source=SourceMeta(
                    source_kind="manual",
                    method="expert_review",
                    created_by="compliance_team",
                    created_at=datetime.now(),
                ),
                created_at=datetime.now(),
            )


class TestEvidenceCase:
    """Test EvidenceCase schema."""

    def test_evidence_case_minimal(self):
        """Test EvidenceCase with minimal required fields."""
        case = EvidenceCase(
            id="EC001",
            title="Data processing evidence",
            obligation_id="OBL001",
            required_evidence=[
                EvidenceItem(
                    name="Processing records",
                    kind="document",
                    acceptance_criteria=["Must show processing purpose", "Must include timestamps"],
                )
            ],
            temporal=TemporalValidity(effective_from=datetime.now()),
            version="1.0.0",
            source=SourceMeta(
                source_kind="manual",
                method="expert_review",
                created_by="compliance_team",
                created_at=datetime.now(),
            ),
            created_at=datetime.now(),
        )
        assert case.id == "EC001"
        assert case.obligation_id == "OBL001"
        assert len(case.required_evidence) == 1
        assert case.required_evidence[0].kind == "document"

    def test_evidence_case_full(self):
        """Test EvidenceCase with all fields."""
        case = EvidenceCase(
            id="EC002",
            title="HIPAA compliance evidence",
            obligation_id="OBL002",
            required_evidence=[
                EvidenceItem(
                    name="Access logs",
                    kind="log",
                    acceptance_criteria=["Must include user ID", "Must include timestamp"],
                    example_locator="s3://bucket/logs/access.log",
                ),
                EvidenceItem(
                    name="Encryption certificate",
                    kind="certificate",
                    acceptance_criteria=["Must be valid", "Must use AES-256"],
                ),
            ],
            control_mappings=[
                FrameworkMap(framework="NIST", control_id="AC-2"),
                FrameworkMap(framework="ISO27001", control_id="A.9.2.1"),
            ],
            regulation_refs=[RegCitation(framework="HIPAA", citation="164.312(a)(1)")],
            temporal=TemporalValidity(
                effective_from=datetime(2024, 1, 1), effective_to=datetime(2024, 12, 31)
            ),
            tags=["hipaa", "healthcare", "security"],
            version="1.0.0",
            source=SourceMeta(
                source_kind="regulatory_document",
                method="manual_extraction",
                created_by="compliance_team",
                created_at=datetime.now(),
            ),
            created_at=datetime.now(),
        )
        assert len(case.required_evidence) == 2
        assert len(case.control_mappings) == 2
        assert case.control_mappings[0].framework == "NIST"
        assert (case.required_evidence[0].example_locator == "s3://bucket/logs/access.log",)


class TestRegulatoryQAPair:
    """Test RegulatoryQAPair schema."""

    def test_regulatory_qa_minimal(self):
        """Test RegulatoryQAPair with minimal required fields."""
        qa = RegulatoryQAPair(
            id="QA001",
            question="What is the data retention period under GDPR?",
            authoritative_answer="Personal data should be kept for no longer than necessary for the purposes for which it is processed.",
            regulation_refs=[RegCitation(framework="GDPR", citation="Article 5(1)(e)")],
            temporal=TemporalValidity(effective_from=datetime.now()),
            version="1.0.0",
            source=SourceMeta(
                source_kind="regulatory_document",
                method="expert_review",
                created_by="legal_team",
                created_at=datetime.now(),
            ),
            created_at=datetime.now(),
        )
        assert qa.id == "QA001"
        assert "retention period" in qa.question
        assert len(qa.regulation_refs) == 1

    def test_regulatory_qa_full(self):
        """Test RegulatoryQAPair with all fields."""
        qa = RegulatoryQAPair(
            id="QA002",
            question="How should healthcare providers handle patient consent under HIPAA?",
            authoritative_answer="Healthcare providers must obtain written authorization from patients before using or disclosing PHI for purposes not related to treatment, payment, or healthcare operations.",
            regulation_refs=[
                RegCitation(
                    framework="HIPAA",
                    citation="164.508",
                    url="https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html",
                )
            ],
            temporal=TemporalValidity(
                effective_from=datetime(2024, 1, 1), effective_to=datetime(2025, 12, 31)
            ),
            topic="consent_management",
            difficulty="intermediate",
            version="1.0.0",
            source=SourceMeta(
                source_kind="official_guidance",
                method="manual_extraction",
                created_by="legal_team",
                created_at=datetime.now(),
                version="2.0.0",
            ),
            created_at=datetime.now(),
        )
        assert qa.topic == "consent_management"
        assert qa.difficulty == "intermediate"
        assert qa.regulation_refs[0].url is not None
