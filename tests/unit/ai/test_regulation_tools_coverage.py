"""
Tests for services.ai.regulation_tools module.

Covers RegulationInfo and ComplianceRequirement dataclasses,
IndustryRegulationLookupTool with all industry types.
"""

import pytest

# Inject constants trapped in module docstrings
import services.ai.tools as _tools_mod
if not hasattr(_tools_mod, "MAX_ITEMS"):
    _tools_mod.MAX_ITEMS = 1000

from services.ai.regulation_tools import (
    RegulationInfo,
    ComplianceRequirement,
    IndustryRegulationLookupTool,
)
from services.ai.tools import ToolResult


# =====================================================================
# Dataclass Tests
# =====================================================================


class TestRegulationInfo:
    def test_creation(self):
        info = RegulationInfo(
            name="GDPR",
            description="Data protection regulation",
            applicability="All orgs processing personal data",
            key_requirements=["Lawful basis", "Data rights"],
            penalties="Up to 4% of turnover",
            enforcement_body="ICO",
            last_updated="2021-01-01",
        )
        assert info.name == "GDPR"
        assert len(info.key_requirements) == 2

    def test_to_dict(self):
        info = RegulationInfo(
            name="Test",
            description="Test regulation",
            applicability="All",
            key_requirements=["Req1"],
            penalties="£100",
            enforcement_body="FCA",
            last_updated="2024-01-01",
        )
        d = info.to_dict()
        assert d["name"] == "Test"
        assert d["enforcement_body"] == "FCA"
        assert len(d) == 7


class TestComplianceRequirement:
    def test_creation(self):
        req = ComplianceRequirement(
            requirement_id="REQ_001",
            title="Data encryption",
            description="All data at rest must be encrypted",
            mandatory=True,
            framework="GDPR",
            section="Article 32",
            implementation_guidance="Use AES-256",
            evidence_required=["Encryption config", "Key management docs"],
        )
        assert req.requirement_id == "REQ_001"
        assert req.mandatory is True

    def test_to_dict(self):
        req = ComplianceRequirement(
            requirement_id="REQ_002",
            title="Test",
            description="Test desc",
            mandatory=False,
            framework="ISO27001",
            section="A.10",
            implementation_guidance="Guide",
            evidence_required=["Evidence"],
        )
        d = req.to_dict()
        assert d["requirement_id"] == "REQ_002"
        assert d["mandatory"] is False
        assert len(d) == 8


# =====================================================================
# IndustryRegulationLookupTool Tests
# =====================================================================


class TestIndustryRegulationLookupTool:
    def setup_method(self):
        self.tool = IndustryRegulationLookupTool()

    def test_init(self):
        assert self.tool.name == "lookup_industry_regulations"
        assert "regulations" in self.tool.description.lower()

    def test_regulation_database_has_industries(self):
        assert "technology" in self.tool.regulation_database
        assert "financial" in self.tool.regulation_database
        assert "healthcare" in self.tool.regulation_database
        assert "general" in self.tool.regulation_database

    def test_technology_has_gdpr(self):
        tech = self.tool.regulation_database["technology"]
        assert "GDPR" in tech
        assert tech["GDPR"].name == "General Data Protection Regulation (UK GDPR)"

    def test_technology_has_dpa2018(self):
        tech = self.tool.regulation_database["technology"]
        assert "DPA2018" in tech

    def test_financial_has_fca(self):
        financial = self.tool.regulation_database["financial"]
        assert "FCA" in financial

    def test_financial_has_pci_dss(self):
        financial = self.tool.regulation_database["financial"]
        assert "PCI_DSS" in financial

    def test_healthcare_has_mhra(self):
        healthcare = self.tool.regulation_database["healthcare"]
        assert "MHRA" in healthcare

    def test_general_has_health_safety(self):
        general = self.tool.regulation_database["general"]
        assert "HEALTH_SAFETY" in general

    def test_general_has_equality_act(self):
        general = self.tool.regulation_database["general"]
        assert "EQUALITY_ACT" in general

    def test_get_function_schema(self):
        schema = self.tool.get_function_schema()
        assert schema["name"] == "lookup_industry_regulations"
        assert "industry" in schema["parameters"]["properties"]
        assert "business_size" in schema["parameters"]["properties"]
        assert "data_processing" in schema["parameters"]["properties"]
        assert "required" in schema["parameters"]

    # ---- Async execute tests ----

    @pytest.mark.asyncio
    async def test_execute_technology_industry(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["regulation_count"] > 0
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "GDPR" in reg_names
        assert "HEALTH_SAFETY" in reg_names

    @pytest.mark.asyncio
    async def test_execute_financial_industry(self):
        params = {
            "industry": "financial",
            "business_size": "medium",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        assert result.success is True
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "FCA" in reg_names
        # Financial + data processing should include GDPR
        assert "GDPR" in reg_names

    @pytest.mark.asyncio
    async def test_execute_financial_no_data_processing(self):
        params = {
            "industry": "financial",
            "business_size": "large",
            "data_processing": False,
        }
        result = await self.tool.execute(params)
        assert result.success is True
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "FCA" in reg_names
        # Should NOT include GDPR since not processing data (financial ≠ technology)
        assert "GDPR" not in reg_names

    @pytest.mark.asyncio
    async def test_execute_healthcare_industry(self):
        params = {
            "industry": "healthcare",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        assert result.success is True
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "MHRA" in reg_names
        assert "GDPR" in reg_names  # healthcare + data processing

    @pytest.mark.asyncio
    async def test_execute_unknown_industry_fallback(self):
        params = {
            "industry": "mining",
            "business_size": "micro",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        assert result.success is True
        # Unknown industry still gets general regs + GDPR (data processing)
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "HEALTH_SAFETY" in reg_names
        assert "GDPR" in reg_names

    @pytest.mark.asyncio
    async def test_execute_defaults(self):
        result = await self.tool.execute({})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_with_geographic_scope(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
            "geographic_scope": "international",
        }
        result = await self.tool.execute(params)
        assert result.success is True
        assert result.data["industry_context"]["geographic_scope"] == "international"

    # ---- Business size filtering ----

    @pytest.mark.asyncio
    async def test_micro_size_guidance(self):
        params = {
            "industry": "technology",
            "business_size": "micro",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        regs = result.data["applicable_regulations"]
        assert all("size_guidance" in r for r in regs)
        assert any("Simplified" in r["size_guidance"] for r in regs)

    @pytest.mark.asyncio
    async def test_large_size_guidance(self):
        params = {
            "industry": "technology",
            "business_size": "large",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        regs = result.data["applicable_regulations"]
        assert any("Full regulatory scrutiny" in r["size_guidance"] for r in regs)

    # ---- Activity-specific regulations ----

    @pytest.mark.asyncio
    async def test_payment_activity_adds_pci(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
            "specific_activities": ["payment processing"],
        }
        result = await self.tool.execute(params)
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "PCI_DSS" in reg_names

    @pytest.mark.asyncio
    async def test_card_activity_adds_pci(self):
        params = {
            "industry": "general",
            "business_size": "small",
            "data_processing": False,
            "specific_activities": ["credit card handling"],
        }
        result = await self.tool.execute(params)
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "PCI_DSS" in reg_names

    @pytest.mark.asyncio
    async def test_marketing_activity_adds_pecr(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
            "specific_activities": ["email marketing"],
        }
        result = await self.tool.execute(params)
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "PECR" in reg_names

    @pytest.mark.asyncio
    async def test_advertising_activity_adds_pecr(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
            "specific_activities": ["digital advertising"],
        }
        result = await self.tool.execute(params)
        reg_names = [r["regulation"] for r in result.data["applicable_regulations"]]
        assert "PECR" in reg_names

    # ---- Output structure ----

    @pytest.mark.asyncio
    async def test_result_structure(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        data = result.data
        assert "applicable_regulations" in data
        assert "regulation_count" in data
        assert "priority_breakdown" in data
        assert "compliance_timeline" in data
        assert "industry_context" in data
        assert "next_steps" in data
        assert "analysis_timestamp" in data

    @pytest.mark.asyncio
    async def test_priority_breakdown_structure(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        breakdown = result.data["priority_breakdown"]
        assert "critical" in breakdown
        assert "high" in breakdown
        assert "medium" in breakdown
        assert "low" in breakdown

    @pytest.mark.asyncio
    async def test_compliance_timeline_structure(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        timeline = result.data["compliance_timeline"]
        assert "immediate" in timeline
        assert "short_term" in timeline
        assert "medium_term" in timeline
        assert "long_term" in timeline

    @pytest.mark.asyncio
    async def test_next_steps_includes_standard_advice(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        next_steps = result.data["next_steps"]
        assert any("gap analysis" in step.lower() for step in next_steps)

    @pytest.mark.asyncio
    async def test_metadata(self):
        params = {
            "industry": "technology",
            "business_size": "small",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        assert result.metadata["tool_type"] == "regulation_lookup"
        assert result.metadata["industry"] == "technology"
        assert result.metadata["regulation_count"] > 0

    # ---- Sorting ----

    @pytest.mark.asyncio
    async def test_regulations_sorted_by_priority(self):
        params = {
            "industry": "financial",
            "business_size": "medium",
            "data_processing": True,
        }
        result = await self.tool.execute(params)
        regs = result.data["applicable_regulations"]
        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        priorities = [priority_order.get(r["priority"], 2) for r in regs]
        assert priorities == sorted(priorities, reverse=True)
