"""Test validators and metrics."""

from __future__ import annotations

import pytest
from datetime import date, datetime, timedelta, timezone

from ..schemas.common import RegCitation, SourceMeta, TemporalValidity
from ..schemas.compliance_scenario import ComplianceScenario, ExpectedOutcome
from ..golden_datasets.validators import (
    DeepValidator,
    ExternalDataValidator,
    AUTHORITATIVE_DOMAINS,
    KNOWN_FRAMEWORKS,
)
from ..metrics.quality_metrics import dataset_quality_summary
from ..metrics.coverage_metrics import coverage_summary


class TestDeepValidator:
    """Test DeepValidator multi-layer validation."""

    @pytest.fixture
    def validator(self) -> Any:
        """Create DeepValidator instance."""
        return DeepValidator()

    @pytest.fixture
    def valid_scenario(self) -> Any:
        """Create a valid compliance scenario."""
        return ComplianceScenario(
            id="CS-001",
            triggers=["data_breach"],
            regulation_refs=[
                RegCitation(
                    framework="GDPR",
                    article="Article 33",
                    url="https://eur-lex.europa.eu/legal",
                ),
            ],
            expected_outcome=ExpectedOutcome(
                obligations=["notify_authority"], risk_level="high",
            ),
            temporal=TemporalValidity(effective_from=date(2018, 5, 25)),
            version="0.1.0",
            source=SourceMeta(
                origin="external",
                domain="ico.org.uk",
                fetched_at=datetime.now(timezone.utc),
                confidence=0.9,
            ),
        )

    def test_validate_all_layers_pass(self, validator: Any, valid_scenario: Any) -> Any:
        """Test all validation layers pass with valid data."""
        dataset = [valid_scenario]
        results = validator.validate(dataset)

        assert results["overall_valid"] is True
        assert results["semantic"]["valid"] is True
        assert results["cross_ref"]["valid"] is True
        assert results["regulatory"]["valid"] is True
        assert results["temporal"]["valid"] is True

    def test_semantic_validation_missing_fields(self, validator: Any) -> Any:
        """Test semantic validation catches missing required fields."""
        # Scenario missing triggers
        scenario = ComplianceScenario(
            id="CS-002",
            triggers=[],  # Empty triggers should fail
            regulation_refs=[RegCitation(framework="GDPR", article="Art 5")],
            expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
            temporal=TemporalValidity(effective_from=date.today()),
            version="0.1.0",
            source=SourceMeta(
                origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
            ),
        )

        results = validator.validate([scenario])
        assert results["semantic"]["valid"] is False
        assert any(
            "Missing triggers" in error for error in results["semantic"]["errors"]
        )

    def test_regulatory_accuracy_unknown_framework(self, validator: Any) -> Any:
        """Test regulatory accuracy validation warns on unknown frameworks."""
        scenario = ComplianceScenario(
            id="CS-003",
            triggers=["test"],
            regulation_refs=[
                RegCitation(framework="UNKNOWN_FRAMEWORK", article="Section 1"),
            ],
            expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
            temporal=TemporalValidity(effective_from=date.today()),
            version="0.1.0",
            source=SourceMeta(
                origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
            ),
        )

        results = validator.validate([scenario])
        # Unknown framework is a warning, not an error
        assert results["regulatory"]["valid"] is True
        assert any(
            "Unknown framework" in warning
            for warning in results["regulatory"]["warnings"]
        )

    def test_regulatory_accuracy_non_authoritative_url(self, validator: Any) -> Any:
        """Test regulatory accuracy validation catches non-authoritative URLs."""
        scenario = ComplianceScenario(
            id="CS-004",
            triggers=["test"],
            regulation_refs=[
                RegCitation(
                    framework="GDPR",
                    article="Article 5",
                    url="https://random-blog.com/gdpr-guide",  # Non-authoritative,
                ),
            ],
            expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
            temporal=TemporalValidity(effective_from=date.today()),
            version="0.1.0",
            source=SourceMeta(
                origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
            ),
        )

        results = validator.validate([scenario])
        assert results["regulatory"]["valid"] is False
        assert any(
            "Non-authoritative URL" in error
            for error in results["regulatory"]["errors"]
        )

    def test_temporal_validation_expired(self, validator: Any) -> Any:
        """Test temporal validation warns on expired items."""
        scenario = ComplianceScenario(
            id="CS-005",
            triggers=["test"],
            regulation_refs=[RegCitation(framework="GDPR", article="Art 5")],
            expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
            temporal=TemporalValidity(
                effective_from=date(2020, 1, 1),
                effective_to=date(2023, 1, 1),  # Expired,
            ),
            version="0.1.0",
            source=SourceMeta(
                origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
            ),
        )

        results = validator.validate([scenario])
        # Expiry is a warning, not an error
        assert results["temporal"]["valid"] is True
        assert any("Expired" in warning for warning in results["temporal"]["warnings"])

    def test_temporal_validation_future(self, validator: Any) -> Any:
        """Test temporal validation warns on future effective dates."""
        future_date = date.today() + timedelta(days=365)
        scenario = ComplianceScenario(
            id="CS-006",
            triggers=["test"],
            regulation_refs=[RegCitation(framework="GDPR", article="Art 5")],
            expected_outcome=ExpectedOutcome(obligations=["test"], risk_level="low"),
            temporal=TemporalValidity(effective_from=future_date),  # Future date
            version="0.1.0",
            source=SourceMeta(
                origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
            ),
        )

        results = validator.validate([scenario])
        assert results["temporal"]["valid"] is True
        assert any(
            "Not yet effective" in warning
            for warning in results["temporal"]["warnings"]
        )


class TestExternalDataValidator:
    """Test ExternalDataValidator trust scoring."""

    @pytest.fixture
    def validator(self) -> Any:
        """Create ExternalDataValidator instance."""
        return ExternalDataValidator()

    @pytest.fixture
    def sample_dataset(self) -> Any:
        """Create sample dataset for testing."""
        return [
            ComplianceScenario(
                id=f"CS-{i:03d}",
                triggers=["test"],
                regulation_refs=[RegCitation(framework="GDPR", article=f"Article {i}")],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="ico.org.uk", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i in range(1, 6)
        ]

    def test_source_reputation_authoritative(self, validator: Any) -> Any:
        """Test source reputation scoring for authoritative domains."""
        metadata = {"domain": "eur-lex.europa.eu"}
        score = validator._check_source_reputation(metadata)
        assert score == 1.0

        metadata = {"domain": "ico.org.uk"}
        score = validator._check_source_reputation(metadata)
        assert score == 1.0

    def test_source_reputation_gov_org(self, validator: Any) -> Any:
        """Test source reputation scoring for .gov and .org domains."""
        metadata = {"domain": "example.gov"}
        score = validator._check_source_reputation(metadata)
        assert score == 0.7

        metadata = {"domain": "example.org"}
        score = validator._check_source_reputation(metadata)
        assert score == 0.7

    def test_source_reputation_other(self, validator: Any) -> Any:
        """Test source reputation scoring for other domains."""
        metadata = {"domain": "random-blog.com"}
        score = validator._check_source_reputation(metadata)
        assert score == 0.4

    def test_data_age_fresh(self, validator: Any) -> Any:
        """Test data age scoring for fresh data."""
        metadata = {"fetched_at": datetime.now(timezone.utc) - timedelta(days=30)}
        score = validator._check_data_age(metadata)
        assert score == 1.0

    def test_data_age_moderate(self, validator: Any) -> Any:
        """Test data age scoring for moderately aged data."""
        # 9 months old
        metadata = {"fetched_at": datetime.now(timezone.utc) - timedelta(days=270)}
        score = validator._check_data_age(metadata)
        assert score == 0.8

        # 18 months old
        metadata = {"fetched_at": datetime.now(timezone.utc) - timedelta(days=540)}
        score = validator._check_data_age(metadata)
        assert score == 0.6

    def test_data_age_old(self, validator: Any) -> Any:
        """Test data age scoring for old data."""
        metadata = {"fetched_at": datetime.now(timezone.utc) - timedelta(days=1000)}
        score = validator._check_data_age(metadata)
        assert score == 0.4

    def test_regulatory_accuracy_known_frameworks(self, validator: Any, sample_dataset: Any) -> Any:
        """Test regulatory accuracy scoring with known frameworks."""
        score = validator._check_regulatory_accuracy(sample_dataset)
        assert score == 1.0  # All GDPR which is known

    def test_consistency_unique_ids(self, validator: Any, sample_dataset: Any) -> Any:
        """Test consistency scoring with unique IDs."""
        score = validator._check_consistency(sample_dataset)
        assert score > 0.8  # Should be high with unique IDs

    def test_consistency_duplicate_ids(self, validator: Any) -> Any:
        """Test consistency scoring with duplicate IDs."""
        dataset = [
            ComplianceScenario(
                id="CS-001",  # Duplicate ID
                triggers=["test"],
                regulation_refs=[],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for _ in range(3)
        ]

        score = validator._check_consistency(dataset)
        assert (
            score < 0.7
        )  # Should be low with duplicate IDs (unique_ratio=1/3=0.33, field_score=1.0, total=(0.33+1.0)/2=0.67)

    def test_coverage_diversity(self, validator: Any) -> Any:
        """Test coverage scoring for framework and jurisdiction diversity."""
        dataset = [
            ComplianceScenario(
                id=f"CS-{i:03d}",
                triggers=["test"],
                regulation_refs=[RegCitation(framework=framework, article="Test")],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i, framework in enumerate(["GDPR", "HIPAA", "SOX", "UK GDPR", "CCPA"])
        ]

        score = validator._check_coverage(dataset)
        assert score == 1.0  # Maximum diversity achieved

    def test_overall_trust_score(self, validator: Any, sample_dataset: Any) -> float:
        """Test overall trust score calculation."""
        metadata = {
            "domain": "ico.org.uk",
            "fetched_at": datetime.now(timezone.utc) - timedelta(days=30),
        }

        scores = validator.score_trustworthiness(sample_dataset, metadata)

        assert "overall" in scores
        assert 0 <= scores["overall"] <= 1.0
        assert scores["source_reputation"] == 1.0  # Authoritative domain
        assert scores["data_freshness"] == 1.0  # Very fresh data


class TestQualityMetrics:
    """Test quality metrics calculation."""

    def test_empty_dataset(self) -> Any:
        """Test quality metrics for empty dataset."""
        metrics = dataset_quality_summary([])

        assert metrics["completeness"] == 0.0
        assert metrics["uniqueness"] == 0.0
        assert metrics["overall_score"] == 0.0
        assert metrics["total_items"] == 0

    def test_perfect_quality(self) -> Any:
        """Test quality metrics for perfect dataset."""
        dataset = [
            ComplianceScenario(
                id=f"CS-{i:03d}",
                triggers=["test"],
                regulation_refs=[RegCitation(framework="GDPR", article="Test")],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i in range(10)
        ]

        metrics = dataset_quality_summary(dataset)

        assert metrics["completeness"] > 0.6  # All required fields present
        assert metrics["uniqueness"] == 1.0  # All IDs unique
        assert metrics["unique_ids"] == 10
        assert metrics["duplicate_ids"] == 0

    def test_duplicate_detection(self) -> Any:
        """Test duplicate ID detection."""
        dataset = [
            ComplianceScenario(
                id="CS-001" if i < 3 else f"CS-{i:03d}",  # First 3 have same ID
                triggers=["test"],
                regulation_refs=[],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i in range(5)
        ]

        metrics = dataset_quality_summary(dataset)

        assert metrics["unique_ids"] == 3  # CS-001, CS-003, CS-004
        assert metrics["duplicate_ids"] == 2  # 2 extra CS-001s
        assert metrics["uniqueness"] == 3 / 5  # 60% unique


class TestCoverageMetrics:
    """Test coverage metrics calculation."""

    def test_empty_dataset(self) -> Any:
        """Test coverage metrics for empty dataset."""
        metrics = coverage_summary([])

        assert metrics["frameworks"] == {}
        assert metrics["jurisdictions"] == {}
        assert metrics["triggers"] == {}
        assert metrics["total_items"] == 0

    def test_framework_counting(self) -> Any:
        """Test framework coverage counting."""
        dataset = [
            ComplianceScenario(
                id=f"CS-{i:03d}",
                triggers=["test"],
                regulation_refs=(
                    [
                        RegCitation(framework="GDPR", article="Test"),
                        RegCitation(framework="HIPAA", article="Test"),
                    ]
                    if i < 3
                    else [RegCitation(framework="GDPR", article="Test")],
                ),
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i in range(5)
        ]

        metrics = coverage_summary(dataset)

        assert metrics["frameworks"]["GDPR"] == 5  # All 5 have GDPR
        assert metrics["frameworks"]["HIPAA"] == 3  # First 3 have HIPAA
        assert metrics["framework_count"] == 2
        assert metrics["most_common_framework"] == ("GDPR", 5)

    def test_jurisdiction_inference(self) -> Any:
        """Test jurisdiction inference from frameworks."""
        dataset = [
            ComplianceScenario(
                id=f"CS-{i:03d}",
                triggers=["test"],
                regulation_refs=[RegCitation(framework=framework, article="Test")],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i, framework in enumerate(
                ["GDPR", "UK GDPR", "HIPAA", "SOX", "ISO27001", "CCPA"],
            )
        ]

        metrics = coverage_summary(dataset)

        assert metrics["jurisdictions"]["EU"] == 1  # GDPR
        assert metrics["jurisdictions"]["UK"] == 1  # UK GDPR
        assert metrics["jurisdictions"]["US"] == 3  # HIPAA, SOX, CCPA
        assert metrics["jurisdictions"]["International"] == 1  # ISO27001

    def test_trigger_counting(self) -> Any:
        """Test trigger coverage counting."""
        dataset = [
            ComplianceScenario(
                id=f"CS-{i:03d}",
                triggers=["data_breach", "user_request"] if i < 2 else ["data_breach"],
                regulation_refs=[],
                expected_outcome=ExpectedOutcome(
                    obligations=["test"], risk_level="low",
                ),
                temporal=TemporalValidity(effective_from=date.today()),
                version="0.1.0",
                source=SourceMeta(
                    origin="external", domain="test.com", fetched_at=datetime.now(timezone.utc),
                ),
            )
            for i in range(5)
        ]

        metrics = coverage_summary(dataset)

        assert metrics["triggers"]["data_breach"] == 5  # All have this
        assert metrics["triggers"]["user_request"] == 2  # First 2 have this
        assert metrics["trigger_count"] == 2
        assert metrics["most_common_trigger"] == ("data_breach", 5)


class TestKnownConstants:
    """Test the known frameworks and authoritative domains constants."""

    def test_authoritative_domains_present(self) -> Any:
        """Test that key authoritative domains are present."""
        expected_domains = {
            "eur-lex.europa.eu",  # EU legislation
            "ico.org.uk",  # UK data protection
            "hhs.gov",  # US health
            "nist.gov",  # NIST standards
            "pcisecuritystandards.org",  # PCI DSS,
        }

        assert expected_domains.issubset(AUTHORITATIVE_DOMAINS)

    def test_known_frameworks_present(self) -> Any:
        """Test that key frameworks are present."""
        expected_frameworks = {
            "GDPR",
            "UK GDPR",
            "HIPAA",
            "SOX",
            "ISO27001",
            "SOC2",
            "PCI DSS",
            "NIST 800-53",
        }

        assert expected_frameworks.issubset(KNOWN_FRAMEWORKS)
