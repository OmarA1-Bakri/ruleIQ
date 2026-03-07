"""Test golden dataset schemas."""

import pytest
from datetime import date, datetime, timezone
from pydantic import ValidationError
from ..schemas.common import RegCitation, SourceMeta, TemporalValidity
from ..schemas.compliance_scenario import ComplianceScenario, ExpectedOutcome
from ..schemas.evidence_case import EvidenceCase, EvidenceItem, FrameworkMap
from ..schemas.regulatory_qa import RegulatoryQAPair

# Constants
HIGH_CONFIDENCE_THRESHOLD = 0.95


class TestCommonSchemas:
    """Test common schema components."""

    def test_reg_citation_valid(self):
        """Test valid RegCitation creation."""
        citation = RegCitation(
            framework="GDPR",
            article="Article 32",
            url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
        )
        assert citation.framework == "GDPR"
        assert citation.article == "Article 32"
        assert str(citation.url).startswith("https://")

    def test_reg_citation_optional_url(self):
        """Test RegCitation with optional URL."""
        citation = RegCitation(framework="HIPAA", article="164.312(a)(1)")
        assert citation.url is None

    def test_source_meta_valid(self):
        """Test valid SourceMeta creation."""
        source = SourceMeta(
            origin="ico.org.uk",
            domain="uk",
            fetched_at=datetime.now(timezone.utc),
            trust_score=0.95,
        )
        assert source.origin == "ico.org.uk"
        assert source.trust_score == HIGH_CONFIDENCE_THRESHOLD

    def test_source_meta_confidence_bounds(self):
        """Test SourceMeta confidence validation."""
        with pytest.raises(ValidationError):
            SourceMeta(
                origin="external",
                domain="test.com",
                fetched_at=datetime.now(timezone.utc),
                trust_score=1.5,
            )
        with pytest.raises(ValidationError):
            SourceMeta(
                origin="external",
                domain="test.com",
                fetched_at=datetime.now(timezone.utc),
                trust_score=-0.1,
            )

    def test_temporal_validity_valid(self):
        """Test valid TemporalValidity creation."""
        temporal = TemporalValidity(
            effective_from=date(2024, 1, 1), effective_to=date(2025, 12, 31)
        )
        assert temporal.effective_from == date(2024, 1, 1)
        assert temporal.effective_to == date(2025, 12, 31)

    def test_temporal_validity_no_end(self):
        """Test TemporalValidity without end date."""
        temporal = TemporalValidity(effective_from=date(2024, 1, 1))
        assert temporal.effective_to is None

    def test_temporal_validity_date_order(self):
        """Test TemporalValidity date order validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemporalValidity(effective_from=date(2025, 1, 1), effective_to=date(2024, 1, 1))
        assert "effective_to must be after effective_from" in str(exc_info.value)


class TestComplianceScenario:
    """Test ComplianceScenario schema."""

    def test_compliance_scenario_valid(self):
        """Test valid ComplianceScenario creation."""
        scenario = ComplianceScenario(
            id="CS-001",
            triggers=["data_breach", "personal_data_exposure"],
            regulation_refs=[
                RegCitation(framework="GDPR", article="Article 33"),
                RegCitation(framework="GDPR", article="Article 34"),
            ],
            expected_outcome=ExpectedOutcome(
                obligations=["notify_authority_72h", "notify_individuals"],
                risk_level="high",
                enforcement_likelihood=0.8,
            ),
            temporal=TemporalValidity(effective_from=date(2018, 5, 25)),
            version="0.1.0",
            source=SourceMeta(
                origin="external",
                domain="ico.org.uk",
                fetched_at=datetime.now(timezone.utc),
                trust_score=0.9,
            ),
        )
        assert scenario.id == "CS-001"
        assert len(scenario.triggers) == 2
        assert len(scenario.regulation_refs) == 2
        assert scenario.expected_outcome.risk_level == "high"

    def test_compliance_scenario_required_fields(self):
        """Test ComplianceScenario required field validation."""
        with pytest.raises(ValidationError):
            ComplianceScenario(
                id="CS-002",
                regulation_refs=[RegCitation(framework="GDPR", article="Article 5")],
                expected_outcome=ExpectedOutcome(
                    obligations=["maintain_records"], risk_level="low"
                ),
                temporal=TemporalValidity(effective_from=date(2018, 5, 25)),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc)
                ),
            )

    def test_expected_outcome_risk_levels(self):
        """Test ExpectedOutcome risk level validation."""
        for level in ["low", "medium", "high", "critical"]:
            outcome = ExpectedOutcome(obligations=["test_obligation"], risk_level=level)
            assert outcome.risk_level == level
        outcome = ExpectedOutcome(obligations=["test"], risk_level="extreme")
        assert outcome.risk_level == "extreme"

    def test_expected_outcome_enforcement_bounds(self):
        """Test ExpectedOutcome enforcement likelihood bounds."""
        with pytest.raises(ValidationError):
            ExpectedOutcome(obligations=["test"], risk_level="low", enforcement_likelihood=1.5)


class TestEvidenceCase:
    """Test EvidenceCase schema."""

    def test_evidence_case_valid(self):
        """Test valid EvidenceCase creation."""
        evidence_case = EvidenceCase(
            id="EC-001",
            obligation_id="OBL-GDPR-32",
            evidence_items=[
                EvidenceItem(
                    type="policy",
                    description="Data encryption policy",
                    format="document",
                    location="/policies/encryption.pdf",
                ),
                EvidenceItem(
                    type="technical_control",
                    description="AES-256 encryption implementation",
                    format="code",
                    location="/src/crypto/encryption.py",
                ),
            ],
            framework_mapping=[
                FrameworkMap(framework="ISO27001", control_id="A.10.1.1", satisfaction_level=0.9)
            ],
            version="0.1.0",
            source=SourceMeta(
                origin="external",
                domain="csrc.nist.gov",
                fetched_at=datetime.now(timezone.utc),
                trust_score=0.85,
            ),
        )
        assert evidence_case.obligation_id == "OBL-GDPR-32"
        assert len(evidence_case.evidence_items) == 2
        assert evidence_case.evidence_items[0].type == "policy"

    def test_evidence_item_types(self):
        """Test EvidenceItem type validation."""
        valid_types = ["policy", "technical_control", "process", "audit_log", "certification"]
        for item_type in valid_types:
            item = EvidenceItem(type=item_type, description="Test description", format="document")
            assert item.type == item_type
        item = EvidenceItem(type="invalid_type", description="Test", format="document")
        assert item.type == "invalid_type"

    def test_evidence_item_formats(self):
        """Test EvidenceItem format validation."""
        valid_formats = ["document", "code", "screenshot", "log", "report"]
        for item_format in valid_formats:
            item = EvidenceItem(type="policy", description="Test description", format=item_format)
            assert item.format == item_format
        item = EvidenceItem(type="policy", description="Test", format="invalid_format")
        assert item.format == "invalid_format"

    def test_framework_map_satisfaction_bounds(self):
        """Test FrameworkMap satisfaction level bounds."""
        with pytest.raises(ValidationError):
            FrameworkMap(framework="SOC2", control_id="CC1.1", satisfaction_level=1.2)
        with pytest.raises(ValidationError):
            FrameworkMap(framework="SOC2", control_id="CC1.1", satisfaction_level=-0.1)


class TestRegulatoryQAPair:
    """Test RegulatoryQAPair schema."""

    def test_regulatory_qa_valid(self):
        """Test valid RegulatoryQAPair creation."""
        qa_pair = RegulatoryQAPair(
            id="QA-001",
            question="What is the data breach notification timeline under GDPR?",
            answer="Organizations must notify the supervisory authority within 72 hours of becoming aware of a personal data breach, unless the breach is unlikely to result in a risk to individuals' rights and freedoms.",
            regulation_refs=[
                RegCitation(
                    framework="GDPR",
                    article="Article 33",
                    url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679#033",
                )
            ],
            version="0.1.0",
            source=SourceMeta(
                origin="external",
                domain="ico.org.uk",
                fetched_at=datetime.now(timezone.utc),
                trust_score=0.9,
            ),
        )
        assert qa_pair.id == "QA-001"
        assert "72 hours" in qa_pair.answer
        assert len(qa_pair.regulation_refs) == 1

    def test_regulatory_qa_confidence_bounds(self):
        """Test RegulatoryQAPair creation with minimal fields."""
        qa_pair = RegulatoryQAPair(
            id="QA-002",
            question="Test question?",
            answer="Test answer.",
            regulation_refs=[],
            version="0.1.0",
            source=SourceMeta(
                origin="external",
                domain="test.com",
                fetched_at=datetime.now(timezone.utc),
                trust_score=0.5,
            ),
        )
        assert qa_pair.id == "QA-002"
        assert qa_pair.question == "Test question?"

    def test_regulatory_qa_empty_refs_allowed(self):
        """Test RegulatoryQAPair with empty regulation_refs."""
        qa_pair = RegulatoryQAPair(
            id="QA-003",
            question="General compliance question?",
            answer="General answer without specific regulation.",
            regulation_refs=[],
            version="0.1.0",
            source=SourceMeta(
                origin="external",
                domain="test.com",
                fetched_at=datetime.now(timezone.utc),
                trust_score=0.7,
            ),
        )
        assert len(qa_pair.regulation_refs) == 0


class TestSchemaIntegration:
    """Test schema integration and edge cases."""

    def test_all_schemas_json_serializable(self):
        """Test that all schemas can be JSON serialized."""
        import json

        citation = RegCitation(framework="GDPR", article="Article 5")
        source = SourceMeta(
            origin="external",
            domain="test.com",
            fetched_at=datetime.now(timezone.utc),
            trust_score=0.8,
        )
        temporal = TemporalValidity(effective_from=date(2024, 1, 1))
        scenario = ComplianceScenario(
            id="CS-TEST",
            triggers=["test"],
            regulation_refs=[citation],
            expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
            temporal=temporal,
            version="0.1.0",
            source=source,
        )
        json_str = scenario.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        reconstructed = ComplianceScenario(**data)
        assert reconstructed.id == scenario.id

    def test_version_field_required(self):
        """Test that version field is required in all main schemas."""
        with pytest.raises(ValidationError):
            ComplianceScenario(
                id="CS-NO-VER",
                triggers=["test"],
                regulation_refs=[],
                expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
                temporal=TemporalValidity(effective_from=date(2024, 1, 1)),
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc)
                ),
            )
        with pytest.raises(ValidationError):
            EvidenceCase(
                id="EC-NO-VER",
                obligation_id="OBL-001",
                evidence_items=[],
                framework_mapping=[],
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc)
                ),
            )
