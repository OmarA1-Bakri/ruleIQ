"""
Comprehensive Test Suite for UK Compliance Integration
Following TDD principles with complete coverage
"""

import unittest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

import pytest
from freezegun import freeze_time

from services.compliance.uk_compliance_engine import (
    UKComplianceManifest,
    UKComplianceAssessmentEngine,
    ComplianceObligation,
    ComplianceStatus,
    RiskLevel,
)
from services.compliance.graphrag_research_engine import (
    GraphRAGResearchEngine,
    ResearchQuery,
    ResearchType,
    ResearchResult,
)


class TestUKComplianceManifest(unittest.TestCase):
    """Test UK compliance manifest implementation"""

    def setUp(self):
        """Set up test fixtures"""
        self.manifest_path = "data/manifests/uk_compliance_manifest.json"
        self.manifest = UKComplianceManifest(self.manifest_path)

    def test_manifest_loads_successfully(self):
        """Test manifest loads without errors"""
        self.assertIsNotNone(self.manifest)
        self.assertIsNotNone(self.manifest.regulations)
        self.assertIsNotNone(self.manifest.obligations)

    def test_all_uk_regulations_present(self):
        """Verify all 10 UK regulations are present"""
        expected_regulations = [
            "UK_GDPR",
            "FCA_REGULATIONS",
            "MONEY_LAUNDERING_REGULATIONS",
            "DATA_PROTECTION_ACT",
            "PECR",
            "BRIBERY_ACT",
            "MODERN_SLAVERY_ACT",
            "COMPANIES_ACT",
            "EQUALITY_ACT",
            "HEALTH_SAFETY_ACT",
        ]

        for reg in expected_regulations:
            self.assertIn(reg, self.manifest.regulations, f"Missing regulation: {reg}")

    def test_uk_gdpr_complete_coverage(self):
        """Test UK GDPR has all required chapters"""
        gdpr = self.manifest.regulations.get("UK_GDPR")
        self.assertIsNotNone(gdpr)

        # Check for key chapters
        self.assertIn("chapters", gdpr)
        chapters = gdpr["chapters"]

        chapter_titles = [ch["title"] for ch in chapters]
        expected_chapters = [
            "General provisions",
            "Principles",
            "Rights of the data subject",
        ]

        for expected in expected_chapters:
            self.assertIn(expected, chapter_titles, f"Missing GDPR chapter: {expected}")

    def test_fca_regulations_components(self):
        """Test FCA regulations have all components"""
        fca = self.manifest.regulations.get("FCA_REGULATIONS")
        self.assertIsNotNone(fca)
        self.assertIn("components", fca)

        components = fca["components"]
        expected_components = ["CONSUMER_DUTY", "SMCR"]

        for comp in expected_components:
            self.assertIn(comp, components, f"Missing FCA component: {comp}")

    def test_obligation_indexing(self):
        """Test obligations are properly indexed"""
        # Should have at least 108 obligations as per requirements
        self.assertGreaterEqual(
            len(self.manifest.obligations),
            108,
            "Should have at least 108 obligations",
        )

        # Check obligation structure
        for _ob_id, obligation in self.manifest.obligations.items():
            self.assertIsInstance(obligation, ComplianceObligation)
            self.assertIsNotNone(obligation.obligation_id)
            self.assertIsNotNone(obligation.description)
            self.assertIsNotNone(obligation.regulation_ref)

    def test_automation_potential_calculation(self):
        """Test automation potential is calculated correctly"""
        for obligation in self.manifest.obligations.values():
            self.assertGreaterEqual(obligation.automation_potential, 0.0)
            self.assertLessEqual(obligation.automation_potential, 1.0)

    def test_get_obligations_by_regulation(self):
        """Test filtering obligations by regulation"""
        gdpr_obligations = self.manifest.get_obligations_by_regulation("UK_GDPR")
        self.assertGreater(len(gdpr_obligations), 0)

        for ob in gdpr_obligations:
            self.assertEqual(ob.regulation_ref, "UK_GDPR")

    def test_get_applicable_obligations(self):
        """Test filtering obligations by entity type"""
        controller_obligations = self.manifest.get_applicable_obligations(
            "data_controllers",
        )
        self.assertGreater(len(controller_obligations), 0)

        for ob in controller_obligations:
            self.assertIn("data_controllers", ob.applicable_entities)

    @freeze_time("2025-01-31")
    def test_get_critical_deadlines(self):
        """Test deadline detection and sorting"""
        deadlines = self.manifest.get_critical_deadlines(days_ahead=30)

        # Check deadlines are sorted chronologically
        if len(deadlines) > 1:
            for i in range(len(deadlines) - 1):
                self.assertLessEqual(deadlines[i][1], deadlines[i + 1][1])

    def test_cross_regulation_mappings(self):
        """Test cross-regulation relationships are defined"""
        self.assertGreater(len(self.manifest.cross_mappings), 0)

        # Check GDPR-DPA mapping exists
        gdpr_dpa_mapping = next(
            (
                m
                for m in self.manifest.cross_mappings
                if "UK_GDPR" in m["regulations"] and "DATA_PROTECTION_ACT" in m["regulations"]
            ),
            None,
        )
        self.assertIsNotNone(gdpr_dpa_mapping, "GDPR-DPA mapping should exist")


class TestUKComplianceAssessmentEngine(unittest.IsolatedAsyncioTestCase):
    """Test compliance assessment engine"""

    async def asyncSetUp(self):
        """Set up async test fixtures"""
        self.manifest = UKComplianceManifest()
        self.engine = UKComplianceAssessmentEngine(self.manifest)

        self.test_organization = {
            "name": "Test Corp Ltd",
            "industry": "financial_services",
            "size": "large",
            "jurisdiction": "UK",
        }

    async def test_assess_compliance_basic(self):
        """Test basic compliance assessment"""
        result = await self.engine.assess_compliance(
            self.test_organization,
            "UK_GDPR",
            "full",
        )

        self.assertIsNotNone(result)
        self.assertIn("organization", result)
        self.assertIn("regulation", result)
        self.assertIn("overall_score", result)
        self.assertIn("risk_rating", result)

    async def test_risk_rating_calculation(self):
        """Test risk rating is calculated correctly"""
        test_cases = [
            (0.95, RiskLevel.MINIMAL.value),
            (0.80, RiskLevel.LOW.value),
            (0.65, RiskLevel.MEDIUM.value),
            (0.45, RiskLevel.HIGH.value),
            (0.30, RiskLevel.CRITICAL.value),
        ]

        for score, expected_rating in test_cases:
            rating = self.engine._determine_risk_rating(score)
            self.assertEqual(
                rating,
                expected_rating,
                f"Score {score} should give rating {expected_rating}",
            )

    async def test_recommendation_generation(self):
        """Test recommendations are generated and prioritized"""
        # Create mock results with gaps
        mock_results = [
            {
                "obligation_id": "TEST-01",
                "score": 0.3,
                "gaps": ["Missing policy", "No training program"],
            },
            {"obligation_id": "TEST-02", "score": 0.7, "gaps": ["Outdated procedure"]},
        ]

        recommendations = self.engine._generate_recommendations(mock_results)

        self.assertGreater(len(recommendations), 0)

        # Check prioritization (lower score = higher priority)
        if len(recommendations) > 1:
            self.assertLessEqual(
                recommendations[0]["priority"],
                recommendations[-1]["priority"],
            )

    async def test_assessment_prompts_loaded(self):
        """Test all assessment prompts are loaded"""
        expected_prompts = [
            "risk_assessment",
            "gap_analysis",
            "control_effectiveness",
            "board_reporting",
        ]

        for prompt_name in expected_prompts:
            self.assertIn(prompt_name, self.engine.assessment_prompts)


class TestGraphRAGResearchEngine(unittest.IsolatedAsyncioTestCase):
    """Test GraphRAG research engine"""

    async def asyncSetUp(self):
        """Set up async test fixtures"""
        self.mock_neo4j = AsyncMock()
        self.mock_llm = AsyncMock()

        with patch("services.compliance.graphrag_research_engine.AsyncGraphDatabase"):
            self.engine = GraphRAGResearchEngine(
                "bolt://localhost:7687",
                ("neo4j", "password"),
                self.mock_llm,
            )

    async def test_research_query_creation(self):
        """Test research query is created correctly"""
        query = ResearchQuery(
            query_id="test_001",
            research_type=ResearchType.OBLIGATION_EXTRACTION,
            query_text="Extract GDPR obligations",
            context={"regulation": "UK_GDPR"},
            filters={},
            max_results=10,
        )

        self.assertEqual(query.query_id, "test_001")
        self.assertEqual(query.research_type, ResearchType.OBLIGATION_EXTRACTION)

    async def test_conduct_research_workflow(self):
        """Test complete research workflow"""
        query = ResearchQuery(
            query_id="test_002",
            research_type=ResearchType.RISK_ASSESSMENT,
            query_text="Assess GDPR risks",
            context={"organization": "Test Corp"},
            filters={},
        )

        # Mock LLM response
        self.mock_llm.agenerate.return_value = AsyncMock(
            generations=[
                [
                    Mock(
                        text=json.dumps(
                            {"findings": ["Risk 1", "Risk 2"], "confidence": 0.85},
                        ),
                    ),
                ],
            ],
        )

        result = await self.engine.conduct_research(query)

        self.assertIsInstance(result, ResearchResult)
        self.assertEqual(result.query_id, query.query_id)
        self.assertGreater(result.confidence_score, 0)

    async def test_research_caching(self):
        """Test research results are cached"""
        query = ResearchQuery(
            query_id="test_003",
            research_type=ResearchType.CONTROL_MAPPING,
            query_text="Map controls",
            context={},
            filters={},
        )

        # First call
        self.mock_llm.agenerate.return_value = AsyncMock(
            generations=[[Mock(text=json.dumps({"findings": ["Control 1"]}))]],
        )

        result1 = await self.engine.conduct_research(query, use_cache=True)

        # Second call should use cache
        result2 = await self.engine.conduct_research(query, use_cache=True)

        self.assertEqual(result1.result_id, result2.result_id)
        # LLM should only be called once due to caching
        self.assertEqual(self.mock_llm.agenerate.call_count, 1)

    async def test_research_prompt_templates(self):
        """Test all research prompt templates are defined"""
        expected_templates = [
            "obligation_extraction",
            "control_mapping",
            "risk_assessment_research",
            "cross_regulation_analysis",
            "regulatory_change_detection",
            "enforcement_pattern_analysis",
        ]

        for template_name in expected_templates:
            self.assertIn(template_name, GraphRAGResearchEngine.RESEARCH_PROMPTS)

    async def test_confidence_score_calculation(self):
        """Test confidence score calculation logic"""
        test_cases = [
            ({"evidence_sources": ["s1", "s2", "s3"]}, 0.8),  # High confidence
            ({"conflicts": ["c1", "c2"]}, 0.3),  # Low confidence
            ({"consistency_score": 0.9}, 0.68),  # Medium-high confidence,
        ]

        for synthesized, min_expected in test_cases:
            confidence = self.engine._calculate_confidence(synthesized)
            self.assertGreaterEqual(confidence, min_expected)
            self.assertLessEqual(confidence, 1.0)


class TestIntegrationEndToEnd(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration tests"""

    async def test_full_uk_gdpr_assessment_workflow(self):
        """Test complete UK GDPR assessment workflow"""
        # Load manifest
        manifest = UKComplianceManifest()

        # Initialize assessment engine
        engine = UKComplianceAssessmentEngine(manifest)

        # Create test organization
        organization = {
            "name": "Test Financial Services Ltd",
            "industry": "financial_services",
            "size": "large",
            "employees": 500,
            "data_subjects": 100000,
            "jurisdiction": "UK",
        }

        # Run assessment
        assessment = await engine.assess_compliance(organization, "UK_GDPR", "full")

        # Validate results
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment["organization"], organization["name"])
        self.assertEqual(assessment["regulation"], "UK_GDPR")
        self.assertIn("overall_score", assessment)
        self.assertIn("risk_rating", assessment)
        self.assertIn("recommendations", assessment)

        # Check obligations were assessed
        self.assertGreater(assessment["obligations_assessed"], 0)

    async def test_multi_regulation_assessment(self):
        """Test assessment across multiple regulations"""
        manifest = UKComplianceManifest()
        engine = UKComplianceAssessmentEngine(manifest)

        organization = {
            "name": "Multi-Regulated Entity",
            "industry": "financial_services",
            "regulated_activities": ["banking", "insurance", "payments"],
        }

        regulations_to_assess = [
            "UK_GDPR",
            "FCA_REGULATIONS",
            "MONEY_LAUNDERING_REGULATIONS",
        ]

        results = {}
        for reg in regulations_to_assess:
            results[reg] = await engine.assess_compliance(organization, reg, "full")

        # Verify all assessments completed
        self.assertEqual(len(results), len(regulations_to_assess))

        # Check for cross-regulation insights
        for reg, result in results.items():
            self.assertIsNotNone(result)
            self.assertIn("overall_score", result)


class TestPerformance(unittest.TestCase):
    """Performance and load tests"""

    def test_manifest_loading_performance(self):
        """Test manifest loads within acceptable time"""
        import time

        start = time.time()
        manifest = UKComplianceManifest()
        load_time = time.time() - start

        # Should load in under 2 seconds
        self.assertLess(
            load_time,
            2.0,
            f"Manifest load took {load_time:.2f}s, expected < 2s",
        )

    def test_large_obligation_search(self):
        """Test searching through large number of obligations"""
        manifest = UKComplianceManifest()

        import time

        start = time.time()

        # Search for obligations 100 times
        for _ in range(100):
            obligations = manifest.get_applicable_obligations("data_controllers")

        search_time = time.time() - start

        # Should complete 100 searches in under 1 second
        self.assertLess(
            search_time,
            1.0,
            f"100 searches took {search_time:.2f}s, expected < 1s",
        )


class TestSecurityAndValidation(unittest.TestCase):
    """Security and data validation tests"""

    def test_no_sensitive_data_in_logs(self):
        """Ensure no sensitive data is logged"""
        import logging
        import io

        # Capture logs
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger("services.compliance")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Run operations that might log sensitive data
        manifest = UKComplianceManifest()
        _ = manifest.get_obligations_by_regulation("UK_GDPR")

        # Check logs don't contain sensitive patterns
        log_contents = log_capture.getvalue()
        sensitive_patterns = ["password", "secret", "key", "token", "personal_data"]

        for pattern in sensitive_patterns:
            self.assertNotIn(
                pattern.lower(),
                log_contents.lower(),
                f"Sensitive pattern '{pattern}' found in logs",
            )

    def test_input_validation(self):
        """Test input validation and sanitization"""
        manifest = UKComplianceManifest()

        # Test with potentially malicious input
        dangerous_inputs = [
            "'; DROP TABLE obligations; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            None,
            "",
            " " * 1000,  # Very long string,
        ]

        for dangerous_input in dangerous_inputs:
            try:
                # Should handle dangerous input safely
                result = manifest.get_obligations_by_regulation(dangerous_input or "")
                # Should return empty list for invalid input
                self.assertEqual(result, [])
            except Exception as e:
                # Should not raise unhandled exceptions
                self.fail(f"Unhandled exception for input '{dangerous_input}': {e}")


if __name__ == "__main__":
    unittest.main()
