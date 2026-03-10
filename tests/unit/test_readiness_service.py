from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from database.readiness_assessment import ReadinessAssessment
from services.readiness_service import (
    analyze_readiness_details,
    calculate_evidence_score,
    calculate_implementation_score,
    calculate_policy_score,
    generate_compliance_report,
    generate_readiness_assessment,
    get_readiness_dashboard,
)


def _mock_scalar_result(first_value=None, all_value=None):
    scalar_result = Mock()
    scalar_result.first.return_value = first_value
    scalar_result.all.return_value = all_value if all_value is not None else []
    result = Mock()
    result.scalars.return_value = scalar_result
    return result


def test_readiness_scoring_helpers_return_expected_defaults():
    assert calculate_policy_score([]) == 0.0
    assert calculate_policy_score([object()]) == 75.0
    assert calculate_implementation_score([]) == 0.0
    assert calculate_implementation_score([object()]) == 60.0
    assert calculate_evidence_score([]) == 0.0
    assert calculate_evidence_score([object()]) == 80.0


def test_analyze_readiness_details_returns_expected_shape():
    analysis = analyze_readiness_details(75.0, 60.0, 80.0)

    assert analysis["priority_actions"][0]["action"] == "Improve policy coverage"
    assert analysis["quick_wins"][0]["effort"] == "low"
    assert analysis["estimated_readiness_date"] > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_generate_compliance_report_supports_pdf_and_json():
    user = SimpleNamespace(id=uuid4())

    pdf_report = await generate_compliance_report(user, "GDPR", "full", "pdf", True, True)
    json_report = await generate_compliance_report(user, "GDPR", "summary", "json", False, True)

    assert pdf_report.startswith(b"%PDF")
    assert json_report["report_metadata"]["framework"] == "GDPR"
    assert json_report["recommendations"] == "Implement all the things."
    assert json_report["evidence"] == "N/A"


@pytest.mark.asyncio
async def test_generate_readiness_assessment_creates_assessment_with_scores():
    db = AsyncMock()
    db.add = Mock()
    user = SimpleNamespace(id=uuid4())
    framework_id = uuid4()
    profile = SimpleNamespace(id=uuid4())
    framework = SimpleNamespace(id=framework_id)
    db.execute.side_effect = [
        _mock_scalar_result(first_value=profile),
        _mock_scalar_result(first_value=framework),
        _mock_scalar_result(all_value=[SimpleNamespace()]),
        _mock_scalar_result(all_value=[SimpleNamespace()]),
        _mock_scalar_result(all_value=[SimpleNamespace()]),
    ]

    assessment = await generate_readiness_assessment(db, user, framework_id)

    assert isinstance(assessment, ReadinessAssessment)
    assert assessment.user_id == user.id
    assert assessment.business_profile_id == profile.id
    assert assessment.framework_id == framework_id
    assert assessment.overall_score == pytest.approx((75.0 + 60.0 + 80.0) / 3)
    assert assessment.score_breakdown == {
        "policy": 75.0,
        "implementation": 60.0,
        "evidence": 80.0,
    }
    assert assessment.framework_scores == {
        "policy": 75.0,
        "implementation": 60.0,
        "evidence": 80.0,
    }
    assert assessment.risk_level == "Medium"
    assert len(assessment.recommendations) == 3
    db.add.assert_called_once_with(assessment)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(assessment)


@pytest.mark.asyncio
async def test_generate_readiness_assessment_requires_business_profile():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    db.execute.return_value = _mock_scalar_result(first_value=None)

    with pytest.raises(ValueError, match="Business profile not found"):
        await generate_readiness_assessment(db, user, uuid4())


@pytest.mark.asyncio
async def test_get_readiness_dashboard_aggregates_latest_assessments():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    framework_one = SimpleNamespace(id=uuid4(), display_name="GDPR")
    framework_two = SimpleNamespace(id=uuid4(), display_name="ISO 27001")
    assessment_one = SimpleNamespace(
        overall_score=80.0,
        priority_actions=[{"action": "Fix gaps", "urgency": "high", "impact": "high"}],
        score_trend="up",
    )
    assessment_two = SimpleNamespace(
        overall_score=60.0,
        priority_actions=[{"action": "Collect evidence", "urgency": "medium", "impact": "medium"}],
        score_trend="stable",
    )
    db.execute.side_effect = [
        _mock_scalar_result(all_value=[framework_one, framework_two]),
        _mock_scalar_result(first_value=assessment_one),
        _mock_scalar_result(first_value=assessment_two),
    ]

    dashboard = await get_readiness_dashboard(db, user)

    assert dashboard == {
        "total_frameworks": 2,
        "average_score": 70.0,
        "framework_scores": [
            {"name": "GDPR", "score": 80.0, "trend": "up"},
            {"name": "ISO 27001", "score": 60.0, "trend": "stable"},
        ],
        "priority_actions": [
            {"framework": "GDPR", "action": "Fix gaps", "urgency": "high", "impact": "high"},
            {
                "framework": "ISO 27001",
                "action": "Collect evidence",
                "urgency": "medium",
                "impact": "medium",
            },
        ],
    }


@pytest.mark.asyncio
async def test_get_readiness_dashboard_returns_message_without_assessments():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    framework = SimpleNamespace(id=uuid4(), display_name="GDPR")
    db.execute.side_effect = [
        _mock_scalar_result(all_value=[framework]),
        _mock_scalar_result(first_value=None),
    ]

    dashboard = await get_readiness_dashboard(db, user)

    assert dashboard == {"message": "No readiness assessments found."}