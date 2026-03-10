"""Tests for langgraph_agent/services/evidence_collector.py."""

from uuid import uuid4

import pytest

from langgraph_agent.services.evidence_collector import EvidenceCollector


@pytest.mark.asyncio
async def test_collect_evidence_builds_items_for_obligations_and_frameworks():
    collector = EvidenceCollector()
    company_id = uuid4()

    result = await collector.collect_evidence(
        company_id,
        {
            "obligations": [
                {"id": "ob-1", "title": "Encryption", "framework": "GDPR"},
                {"id": "ob-2", "title": "Access Control", "framework": "ISO-27001"},
            ],
            "frameworks": ["GDPR", "ISO-27001"],
        },
    )

    assert len(result) == 4
    assert result[0]["obligation_id"] == "ob-1"
    assert result[0]["status"] == "collected"
    assert result[-1]["status"] == "pending_review"
    assert len(result[0]["hash"]) == 16
    assert collector.collected_evidence == result


@pytest.mark.asyncio
async def test_collect_evidence_limits_obligations_and_frameworks():
    collector = EvidenceCollector()

    obligations = [
        {"id": f"ob-{index}", "title": f"Req {index}", "framework": "SOC2"}
        for index in range(8)
    ]
    frameworks = ["GDPR", "ISO-27001", "SOC2", "HIPAA"]

    result = await collector.collect_evidence(uuid4(), {"obligations": obligations, "frameworks": frameworks})

    document_items = [item for item in result if item["type"] == "document"]
    framework_items = [item for item in result if item["type"] == "certification"]

    assert len(document_items) == 5
    assert len(framework_items) == 3


@pytest.mark.asyncio
async def test_verify_evidence_marks_existing_item_and_reports_missing_items():
    collector = EvidenceCollector()
    collected = await collector.collect_evidence(
        uuid4(),
        {"obligations": [{"id": "ob-1", "title": "Encryption", "framework": "GDPR"}], "frameworks": []},
    )

    verified = await collector.verify_evidence(collected[0]["id"])
    missing = await collector.verify_evidence("missing-id")

    assert verified["status"] == "verified"
    assert "verified_at" in verified
    assert missing == {
        "id": "missing-id",
        "status": "not_found",
        "error": "Evidence not found in collection",
    }
