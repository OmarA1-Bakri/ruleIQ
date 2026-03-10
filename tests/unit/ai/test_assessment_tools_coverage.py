"""
Tests for services.ai.assessment_tools module.

Covers ComplianceGap and ComplianceRecommendation dataclasses,
GapAnalysisTool class with execute(), _calculate_priority(),
_analyze_severity_breakdown(), and _generate_gap_recommendations().
"""

import pytest

# Inject constants trapped in module docstrings
import services.ai.tools as _tools_mod
if not hasattr(_tools_mod, "MAX_ITEMS"):
    _tools_mod.MAX_ITEMS = 1000
import services.ai.assessment_tools as _assess_mod
if not hasattr(_assess_mod, "DEFAULT_RETRIES"):
    _assess_mod.DEFAULT_RETRIES = 5

from services.ai.assessment_tools import (
    ComplianceGap,
    ComplianceRecommendation,
    GapAnalysisTool,
)
from services.ai.tools import ToolResult


# =====================================================================
# Dataclass Tests
# =====================================================================


class TestComplianceGap:
    def test_creation(self):
        gap = ComplianceGap(
            id="gap_1",
            section="GDPR Art. 32",
            severity="high",
            description="Missing encryption",
            impact="Data breach risk",
            current_state="No encryption",
            target_state="AES-256",
        )
        assert gap.id == "gap_1"
        assert gap.priority == 0

    def test_custom_priority(self):
        gap = ComplianceGap(
            id="gap_2",
            section="ISO 27001 A.5",
            severity="critical",
            description="No policy",
            impact="Audit failure",
            current_state="None",
            target_state="Approved policy",
            priority=100,
        )
        assert gap.priority == 100

    def test_to_dict(self):
        gap = ComplianceGap(
            id="gap_1",
            section="GDPR Art. 32",
            severity="high",
            description="Missing encryption",
            impact="Data breach risk",
            current_state="No encryption",
            target_state="AES-256",
            priority=75,
        )
        d = gap.to_dict()
        assert d["id"] == "gap_1"
        assert d["section"] == "GDPR Art. 32"
        assert d["severity"] == "high"
        assert d["priority"] == 75
        assert len(d) == 8


class TestComplianceRecommendation:
    def test_creation(self):
        rec = ComplianceRecommendation(
            id="rec_1",
            title="Implement encryption",
            description="Deploy AES-256",
            priority="high",
            implementation_effort="2-4 weeks",
            cost_impact="medium",
            timeline="Q1 2025",
            dependencies=["key_management"],
            resources_required=["Security engineer"],
        )
        assert rec.id == "rec_1"
        assert rec.dependencies == ["key_management"]

    def test_to_dict(self):
        rec = ComplianceRecommendation(
            id="rec_1",
            title="Test",
            description="Test desc",
            priority="low",
            implementation_effort="1 day",
            cost_impact="low",
            timeline="Immediate",
            dependencies=[],
            resources_required=[],
        )
        d = rec.to_dict()
        assert d["id"] == "rec_1"
        assert d["title"] == "Test"
        assert len(d) == 9


# =====================================================================
# GapAnalysisTool Tests
# =====================================================================


class TestGapAnalysisTool:
    def setup_method(self):
        self.tool = GapAnalysisTool()

    def test_init(self):
        assert self.tool.name == "extract_compliance_gaps"
        assert "compliance gaps" in self.tool.description.lower()

    def test_get_function_schema(self):
        schema = self.tool.get_function_schema()
        assert schema["name"] == "extract_compliance_gaps"
        assert "parameters" in schema
        assert "gaps" in schema["parameters"]["properties"]
        assert "overall_risk_level" in schema["parameters"]["properties"]
        assert "required" in schema["parameters"]

    def test_calculate_priority_critical(self):
        assert self.tool._calculate_priority("critical", 0) == 100

    def test_calculate_priority_high(self):
        assert self.tool._calculate_priority("high", 0) == 75

    def test_calculate_priority_medium(self):
        assert self.tool._calculate_priority("medium", 0) == 50

    def test_calculate_priority_low(self):
        assert self.tool._calculate_priority("low", 0) == 25

    def test_calculate_priority_unknown(self):
        assert self.tool._calculate_priority("unknown", 0) == 50

    def test_calculate_priority_with_index(self):
        assert self.tool._calculate_priority("critical", 5) == 90

    def test_analyze_severity_breakdown(self):
        gaps = [
            {"severity": "critical"},
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "low"},
        ]
        breakdown = self.tool._analyze_severity_breakdown(gaps)
        assert breakdown == {"critical": 2, "high": 1, "medium": 1, "low": 1}

    def test_analyze_severity_breakdown_empty(self):
        breakdown = self.tool._analyze_severity_breakdown([])
        assert breakdown == {"critical": 0, "high": 0, "medium": 0, "low": 0}

    def test_analyze_severity_breakdown_unknown_severity(self):
        gaps = [{"severity": "unknown"}]
        breakdown = self.tool._analyze_severity_breakdown(gaps)
        assert breakdown == {"critical": 0, "high": 0, "medium": 0, "low": 0}

    def test_generate_gap_recommendations_high_severity(self):
        gaps = [{"severity": "critical", "section": "GDPR Art. 32"}]
        recs = self.tool._generate_gap_recommendations(gaps)
        assert any("high-priority" in r for r in recs)

    def test_generate_gap_recommendations_gdpr(self):
        gaps = [{"severity": "medium", "section": "GDPR Art. 25"}]
        recs = self.tool._generate_gap_recommendations(gaps)
        assert any("GDPR" in r for r in recs)

    def test_generate_gap_recommendations_iso(self):
        gaps = [{"severity": "medium", "section": "ISO 27001 A.5.1"}]
        recs = self.tool._generate_gap_recommendations(gaps)
        assert any("ISO 27001" in r for r in recs)

    def test_generate_gap_recommendations_many_gaps(self):
        gaps = [{"severity": "low", "section": f"Sec_{i}"} for i in range(10)]
        recs = self.tool._generate_gap_recommendations(gaps)
        assert any("phased" in r.lower() for r in recs)

    def test_generate_gap_recommendations_empty(self):
        recs = self.tool._generate_gap_recommendations([])
        assert isinstance(recs, list)

    @pytest.mark.asyncio
    async def test_execute_success(self):
        params = {
            "gaps": [
                {
                    "section": "GDPR Art. 32",
                    "severity": "high",
                    "description": "Missing encryption",
                    "impact": "Data breach risk",
                    "current_state": "No encryption",
                    "target_state": "AES-256",
                },
                {
                    "section": "ISO 27001 A.5",
                    "severity": "critical",
                    "description": "No security policy",
                    "impact": "Audit failure",
                    "current_state": "None",
                    "target_state": "Approved policy",
                },
            ],
            "overall_risk_level": "high",
            "priority_order": ["ISO 27001 A.5", "GDPR Art. 32"],
            "estimated_effort": "3-6 months",
        }
        result = await self.tool.execute(params)
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["gap_count"] == 2
        assert result.data["overall_risk_level"] == "high"
        assert "severity_breakdown" in result.data
        assert "recommendations" in result.data
        assert result.metadata["tool_type"] == "gap_analysis"

    @pytest.mark.asyncio
    async def test_execute_empty_gaps(self):
        params = {
            "gaps": [],
            "overall_risk_level": "low",
            "priority_order": [],
            "estimated_effort": "None",
        }
        result = await self.tool.execute(params)
        assert result.success is True
        assert result.data["gap_count"] == 0

    @pytest.mark.asyncio
    async def test_execute_defaults(self):
        result = await self.tool.execute({})
        assert result.success is True
        assert result.data["gap_count"] == 0
        assert result.data["overall_risk_level"] == "medium"

    @pytest.mark.asyncio
    async def test_execute_gaps_sorted_by_priority(self):
        params = {
            "gaps": [
                {
                    "section": "Low",
                    "severity": "low",
                    "description": "Minor",
                    "impact": "Low",
                    "current_state": "A",
                    "target_state": "B",
                },
                {
                    "section": "Critical",
                    "severity": "critical",
                    "description": "Major",
                    "impact": "High",
                    "current_state": "C",
                    "target_state": "D",
                },
            ],
        }
        result = await self.tool.execute(params)
        assert result.success is True
        gaps = result.data["gaps"]
        assert gaps[0]["severity"] == "critical"
        assert gaps[1]["severity"] == "low"
