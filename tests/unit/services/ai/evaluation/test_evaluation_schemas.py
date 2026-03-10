"""Tests for services/ai/evaluation/schemas/ - Golden Dataset evaluation schemas."""

import pytest
from datetime import datetime, timedelta

from services.ai.evaluation.schemas.common import (
    RegCitation,
    SourceMetaOld,
    SourceMeta,
    TemporalValidity,
    ExpectedOutcome,
    GoldenDoc,
    GoldenChunk,
)
from services.ai.evaluation.schemas.compliance_scenario import ComplianceScenario
from services.ai.evaluation.schemas.evidence_case import (
    EvidenceItem,
    FrameworkMap,
    EvidenceCase,
)
from services.ai.evaluation.schemas.regulatory_qa import RegulatoryQAPair


# --- common.py ---
class TestRegCitation:
    def test_full(self):
        c = RegCitation(
            framework="GDPR",
            citation="Article 5",
            url="https://gdpr.eu/article-5",
            jurisdiction="EU",
            notes="Data principles",
        )
        assert c.framework == "GDPR"
        assert c.citation == "Article 5"
        assert c.url == "https://gdpr.eu/article-5"

    def test_minimal(self):
        c = RegCitation(framework="ISO27001", citation="A.5.1")
        assert c.framework == "ISO27001"
        assert c.url is None
        assert c.jurisdiction is None


class TestSourceMetaOld:
    def test_full(self):
        s = SourceMetaOld(
            source_kind="regulatory_document",
            method="manual_extraction",
            created_by="admin",
            created_at=datetime(2024, 1, 1),
            version="2.0.0",
            metadata={"key": "value"},
        )
        assert s.source_kind == "regulatory_document"
        assert s.version == "2.0.0"

    def test_defaults(self):
        s = SourceMetaOld(
            source_kind="manual",
            method="import",
            created_by="system",
            created_at=datetime.now(),
        )
        assert s.version == "1.0.0"


class TestSourceMeta:
    def test_full(self):
        s = SourceMeta(
            origin="https://legislation.gov.uk/ukpga/2018/12",
            domain="legislation.gov.uk",
            trust_score=0.95,
            sha256="abc123" * 10 + "ab",
            fetched_at=datetime.now(),
        )
        assert s.trust_score == 0.95
        assert s.domain == "legislation.gov.uk"

    def test_defaults(self):
        s = SourceMeta(
            origin="file://local",
            domain="local",
            sha256="def456" * 10 + "de",
        )
        assert s.trust_score == 0.5
        assert s.fetched_at is None


class TestTemporalValidity:
    def test_valid_range(self):
        now = datetime.now()
        tv = TemporalValidity(
            effective_from=now,
            effective_to=now + timedelta(days=365),
        )
        assert tv.effective_to > tv.effective_from

    def test_no_end(self):
        tv = TemporalValidity(effective_from=datetime.now())
        assert tv.effective_to is None

    def test_invalid_range(self):
        now = datetime.now()
        with pytest.raises(Exception):
            TemporalValidity(
                effective_from=now,
                effective_to=now - timedelta(days=1),
            )


class TestExpectedOutcome:
    def test_valid(self):
        eo = ExpectedOutcome(
            outcome_code="COMPLIANT",
            details={"confidence": 0.95},
        )
        assert eo.outcome_code == "COMPLIANT"

    def test_empty_code(self):
        with pytest.raises(Exception):
            ExpectedOutcome(outcome_code="", details={})


class TestGoldenDoc:
    def test_full(self):
        source = SourceMeta(
            origin="https://example.com",
            domain="example.com",
            sha256="a" * 64,
        )
        doc = GoldenDoc(
            doc_id="doc_001",
            content="Sample regulatory content",
            source_meta=source,
            reg_citations=[],
            expected_outcomes=[],
        )
        assert doc.doc_id == "doc_001"
        assert doc.content == "Sample regulatory content"


class TestGoldenChunk:
    def test_full(self):
        source = SourceMeta(
            origin="https://example.com",
            domain="example.com",
            sha256="b" * 64,
        )
        chunk = GoldenChunk(
            chunk_id="chunk_001",
            doc_id="doc_001",
            chunk_index=0,
            content="First chunk of content",
            source_meta=source,
        )
        assert chunk.chunk_id == "chunk_001"
        assert chunk.chunk_index == 0


# --- compliance_scenario.py ---
class TestComplianceScenario:
    def _make_scenario(self, **overrides):
        now = datetime.now()
        defaults = dict(
            id="scenario_001",
            title="GDPR Data Breach",
            description="Scenario testing data breach response",
            obligation_id="obl_001",
            triggers=["data_breach", "notification_required"],
            expected_outcome=ExpectedOutcome(
                outcome_code="REQUIRES_NOTIFICATION",
                details={"within_hours": 72},
            ),
            temporal=TemporalValidity(effective_from=now),
            version="1.0.0",
            source=SourceMeta(
                origin="https://gdpr.eu",
                domain="gdpr.eu",
                sha256="c" * 64,
            ),
            created_at=now,
        )
        defaults.update(overrides)
        return ComplianceScenario(**defaults)

    def test_valid(self):
        s = self._make_scenario()
        assert s.id == "scenario_001"
        assert len(s.triggers) == 2

    def test_with_sector(self):
        s = self._make_scenario(sector="healthcare", jurisdiction="UK")
        assert s.sector == "healthcare"

    def test_empty_triggers(self):
        with pytest.raises(Exception):
            self._make_scenario(triggers=[])


# --- evidence_case.py ---
class TestEvidenceItem:
    def test_valid(self):
        e = EvidenceItem(
            name="Audit Log",
            kind="document",
            acceptance_criteria=["Must be dated", "Must be signed"],
        )
        assert e.name == "Audit Log"
        assert len(e.acceptance_criteria) == 2

    def test_with_locator(self):
        e = EvidenceItem(
            name="Certificate",
            kind="certificate",
            acceptance_criteria=["Valid"],
            example_locator="s3://bucket/cert.pdf",
        )
        assert e.example_locator == "s3://bucket/cert.pdf"


class TestFrameworkMap:
    def test_valid(self):
        fm = FrameworkMap(framework="NIST", control_id="AC-2")
        assert fm.framework == "NIST"
        assert fm.control_id == "AC-2"


class TestEvidenceCase:
    def test_valid(self):
        now = datetime.now()
        ec = EvidenceCase(
            id="ec_001",
            title="Access Control Evidence",
            obligation_id="obl_002",
            required_evidence=[
                EvidenceItem(
                    name="Access Log",
                    kind="log",
                    acceptance_criteria=["Must include timestamps"],
                )
            ],
            temporal=TemporalValidity(effective_from=now),
            version="1.0.0",
            source=SourceMeta(
                origin="https://example.com",
                domain="example.com",
                sha256="d" * 64,
            ),
            created_at=now,
        )
        assert ec.id == "ec_001"
        assert len(ec.required_evidence) == 1

    def test_with_control_mappings(self):
        now = datetime.now()
        ec = EvidenceCase(
            id="ec_002",
            title="Encryption Evidence",
            obligation_id="obl_003",
            required_evidence=[
                EvidenceItem(name="Config", kind="document", acceptance_criteria=["Valid"])
            ],
            control_mappings=[FrameworkMap(framework="ISO27001", control_id="A.10.1")],
            temporal=TemporalValidity(effective_from=now),
            version="1.0.0",
            source=SourceMeta(origin="x", domain="x", sha256="e" * 64),
            created_at=now,
        )
        assert len(ec.control_mappings) == 1


# --- regulatory_qa.py ---
class TestRegulatoryQAPair:
    def test_valid(self):
        now = datetime.now()
        qa = RegulatoryQAPair(
            id="qa_001",
            question="What is GDPR Article 5?",
            authoritative_answer="Article 5 sets out the principles for data processing.",
            regulation_refs=[RegCitation(framework="GDPR", citation="Article 5")],
            temporal=TemporalValidity(effective_from=now),
            version="1.0.0",
            source=SourceMeta(origin="x", domain="x", sha256="f" * 64),
            created_at=now,
        )
        assert qa.id == "qa_001"
        assert "GDPR" in qa.question

    def test_with_optional_fields(self):
        now = datetime.now()
        qa = RegulatoryQAPair(
            id="qa_002",
            question="What is PCI DSS?",
            authoritative_answer="Payment Card Industry Data Security Standard.",
            regulation_refs=[],
            temporal=TemporalValidity(effective_from=now),
            topic="payment_security",
            difficulty="beginner",
            version="1.0.0",
            source=SourceMeta(origin="x", domain="x", sha256="g" * 64),
            created_at=now,
        )
        assert qa.topic == "payment_security"
        assert qa.difficulty == "beginner"
