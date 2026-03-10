"""Unit tests for compliance router helper behavior."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from api.routers.compliance import (
    ComplianceQueryRequest,
    _build_risk_records,
    _build_task_record,
    _build_timeline,
    _estimate_effort_hours,
    _fallback_response,
)


def _make_evidence_item(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid4(),
        "framework_id": uuid4(),
        "evidence_name": "Security policy",
        "evidence_type": "policy",
        "control_reference": "CTRL-1",
        "description": "Document and approve the security policy.",
        "status": "pending_review",
        "priority": "high",
        "collected_by": "owner@ruleiq.dev",
        "reviewed_by": None,
        "approved_by": None,
        "effort_estimate": "2 4 hours",
        "ai_metadata": {
            "due_date": (now + timedelta(days=14)).isoformat(),
            "dependencies": ["task-1"],
            "evidence_required": ["policy", "approval record"],
        },
        "created_at": now - timedelta(days=3),
        "updated_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_assessment(framework_id, **overrides):
    defaults = {
        "framework_id": framework_id,
        "overall_score": 58.0,
        "priority_actions": ["Close access-control gaps", "Approve missing evidence"],
        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_estimate_effort_hours_averages_ranges():
    assert _estimate_effort_hours("2 4 hours") == 3
    assert _estimate_effort_hours("5 hours") == 5
    assert _estimate_effort_hours(None) == 3


def test_build_task_record_maps_evidence_item_to_task_shape():
    evidence_item = _make_evidence_item()

    task = _build_task_record(evidence_item, "ISO 27001")

    assert task["title"] == "Security policy"
    assert task["framework"] == "ISO 27001"
    assert task["status"] == "in_progress"
    assert task["priority"] == "high"
    assert task["assigned_to"] == "owner@ruleiq.dev"
    assert task["dependencies"] == ["task-1"]
    assert task["evidence_required"] == ["policy", "approval record"]
    assert task["effort_hours"] == 3


def test_build_risk_records_derives_risks_from_assessment_and_open_evidence():
    framework_id = uuid4()
    framework_lookup = {
        str(framework_id): SimpleNamespace(name="iso27001", display_name="ISO 27001")
    }
    evidence_item = _make_evidence_item(framework_id=framework_id, control_reference="A.5.1")
    assessment = _make_assessment(framework_id)

    risks = _build_risk_records([assessment], [evidence_item], framework_lookup)

    assert len(risks) == 1
    risk = risks[0]
    assert risk["title"] == "ISO 27001 readiness gap"
    assert risk["severity"] == "high"
    assert risk["likelihood"] in {"likely", "possible", "very_likely"}
    assert risk["status"] == "mitigating"
    assert risk["affected_controls"] == ["A.5.1"]
    assert "Close access-control gaps" in risk["mitigation_plan"]


def test_build_timeline_uses_task_due_dates_and_assessment_events():
    now = datetime.now(timezone.utc)
    tasks = [
        {
            "title": "Review supplier due diligence",
            "description": "Complete the annual supplier review.",
            "status": "pending",
            "due_date": (now + timedelta(days=10)).isoformat(),
        },
        {
            "title": "Approve access review",
            "description": "Finalize quarterly access review.",
            "status": "completed",
            "due_date": (now - timedelta(days=1)).isoformat(),
        },
    ]
    risks = [
        {
            "title": "GDPR readiness gap",
            "description": "Low readiness score",
            "assessment_date": (now - timedelta(days=5)).isoformat(),
        }
    ]

    timeline = _build_timeline(tasks, risks)

    assert len(timeline["milestones"]) == 3
    assert timeline["upcoming_deadlines"][0]["item"] == "Review supplier due diligence"
    assert timeline["upcoming_deadlines"][0]["type"] == "task"


# --- ComplianceQueryRequest Pydantic model tests ---


def test_compliance_query_request_rejects_empty_question():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ComplianceQueryRequest(question="")


def test_compliance_query_request_accepts_valid_question():
    req = ComplianceQueryRequest(question="What is GDPR?", framework="GDPR")
    assert req.question == "What is GDPR?"
    assert req.framework == "GDPR"


def test_compliance_query_request_framework_is_optional():
    req = ComplianceQueryRequest(question="Tell me about ISO 27001")
    assert req.framework is None


# --- _fallback_response helper tests ---


def test_fallback_response_gdpr():
    result = _fallback_response("What is GDPR?", "GDPR")
    assert "GDPR" in result["answer"]
    assert result["confidence"] == "low"
    assert result["ai_generated"] is False
    assert result["framework"] == "GDPR"


def test_fallback_response_iso27001():
    result = _fallback_response("ISO question", "ISO 27001")
    assert "ISO 27001" in result["answer"]
    assert result["ai_generated"] is False


def test_fallback_response_generic():
    result = _fallback_response("General question", None)
    assert "various" in result["answer"].lower()
    assert result["framework"] == ""
    assert result["ai_generated"] is False