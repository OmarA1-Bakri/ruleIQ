"""Tests for langgraph_agent/services/compliance_analyzer.py."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from langgraph_agent.services.compliance_analyzer import ComplianceAnalyzer


@pytest.mark.asyncio
async def test_analyze_compliance_detects_frameworks_and_limits_recommendations():
    analyzer = ComplianceAnalyzer()

    async def get_framework_obligations(*, framework_name: str):
        return [
            {
                "id": f"{framework_name.lower()}_001",
                "title": f"{framework_name} obligation",
                "framework": framework_name,
            }
        ]

    analyzer.compliance_queries = SimpleNamespace(get_framework_obligations=get_framework_obligations)

    result = await analyzer.analyze_compliance(
        uuid4(),
        {"industry": "Healthcare Finance Tech", "location": "California, Europe", "size": "large"},
    )

    assert result["frameworks"] == ["HIPAA", "SOX", "PCI-DSS", "SOC2", "CCPA", "GDPR"]
    assert len(result["obligations"]) == 6
    assert len(result["recommendations"]) == 3
    assert result["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_analyze_compliance_uses_default_frameworks_when_no_match():
    analyzer = ComplianceAnalyzer()

    async def get_framework_obligations(*, framework_name: str):
        return [{"id": framework_name, "title": framework_name, "framework": framework_name}]

    analyzer.compliance_queries = SimpleNamespace(get_framework_obligations=get_framework_obligations)

    result = await analyzer.analyze_compliance(uuid4(), {"industry": "Retail", "location": "Global"})

    assert result["frameworks"] == ["GDPR", "ISO-27001"]
    assert [item["framework"] for item in result["obligations"]] == ["GDPR", "ISO-27001"]


@pytest.mark.asyncio
async def test_analyze_compliance_falls_back_to_placeholder_obligations_on_query_errors():
    analyzer = ComplianceAnalyzer()

    async def failing_query(*, framework_name: str):
        raise RuntimeError(f"failed for {framework_name}")

    analyzer.compliance_queries = SimpleNamespace(get_framework_obligations=failing_query)

    result = await analyzer.analyze_compliance(uuid4(), {"industry": "Finance", "location": "Global"})

    assert result["frameworks"] == ["SOX", "PCI-DSS"]
    assert len(result["obligations"]) == 2
    assert all(item["priority"] == "high" for item in result["obligations"])
