from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import DatabaseException, NotFoundException
from database.business_profile import BusinessProfile
from services.business_service import (
    create_or_update_business_profile,
    get_business_profile,
    update_assessment_status,
)


def _build_profile_data():
    return {
        "company_name": "RuleIQ",
        "industry": "Technology",
        "employee_count": 42,
        "annual_revenue": "1m-5m",
        "country": "UK",
        "data_sensitivity": "High",
        "handles_personal_data": True,
        "processes_payments": True,
        "stores_health_data": False,
        "provides_financial_services": True,
        "operates_critical_infrastructure": False,
        "has_international_operations": True,
        "cloud_providers": ["AWS (Amazon Web Services)"],
        "saas_tools": ["Slack"],
        "development_tools": ["GitHub"],
        "existing_frameworks": ["GDPR"],
        "planned_frameworks": ["ISO 27001"],
        "compliance_budget": "50k",
        "compliance_timeline": "6 months",
    }


def _mock_scalar_result(profile):
    scalar_result = Mock()
    scalar_result.first.return_value = profile
    result = Mock()
    result.scalars.return_value = scalar_result
    return result


@pytest.mark.asyncio
async def test_create_or_update_business_profile_creates_new_profile():
    db = AsyncMock()
    db.add = Mock()
    db.execute.return_value = _mock_scalar_result(None)
    user = SimpleNamespace(id="user-123")
    profile_data = _build_profile_data()

    profile = await create_or_update_business_profile(db, user, profile_data)

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(profile)
    assert isinstance(profile, BusinessProfile)
    assert profile.user_id == "user-123"
    assert profile.company_name == "RuleIQ"
    assert profile.planned_frameworks == ["ISO 27001"]


@pytest.mark.asyncio
async def test_create_or_update_business_profile_updates_existing_profile():
    db = AsyncMock()
    db.add = Mock()
    existing_profile = SimpleNamespace(
        company_name="Old Name",
        industry="Retail",
        employee_count=10,
        updated_at=None,
    )
    db.execute.return_value = _mock_scalar_result(existing_profile)
    user = SimpleNamespace(id="user-123")

    profile = await create_or_update_business_profile(
        db,
        user,
        {"company_name": "New Name", "employee_count": 25, "unknown_field": "ignored"},
    )

    db.add.assert_not_called()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(existing_profile)
    assert profile is existing_profile
    assert existing_profile.company_name == "New Name"
    assert existing_profile.employee_count == 25
    assert not hasattr(existing_profile, "unknown_field")
    assert existing_profile.updated_at is not None


@pytest.mark.asyncio
async def test_create_or_update_business_profile_rolls_back_on_database_error():
    db = AsyncMock()
    db.execute.side_effect = SQLAlchemyError("select failed")
    user = SimpleNamespace(id="user-123")

    with pytest.raises(DatabaseException, match="Failed to create or update business profile"):
        await create_or_update_business_profile(db, user, _build_profile_data())

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_business_profile_returns_profile():
    db = AsyncMock()
    profile = SimpleNamespace(company_name="RuleIQ")
    db.execute.return_value = _mock_scalar_result(profile)
    user = SimpleNamespace(id="user-123")

    result = await get_business_profile(db, user)

    assert result is profile
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_business_profile_raises_database_exception_on_error():
    db = AsyncMock()
    db.execute.side_effect = SQLAlchemyError("select failed")
    user = SimpleNamespace(id="user-123")

    with pytest.raises(DatabaseException, match="Failed to retrieve business profile"):
        await get_business_profile(db, user)


@pytest.mark.asyncio
async def test_update_assessment_status_updates_profile():
    db = AsyncMock()
    profile = SimpleNamespace(assessment_completed=False, assessment_data={}, updated_at=None)
    user = SimpleNamespace(id="user-123")
    assessment_data = {"score": 87, "frameworks": ["GDPR"]}

    with patch("services.business_service.get_business_profile", AsyncMock(return_value=profile)):
        result = await update_assessment_status(db, user, True, assessment_data)

    assert result is profile
    assert profile.assessment_completed is True
    assert profile.assessment_data == assessment_data
    assert profile.updated_at is not None
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(profile)


@pytest.mark.asyncio
async def test_update_assessment_status_raises_not_found_when_profile_missing():
    db = AsyncMock()
    user = SimpleNamespace(id="user-123")

    with patch("services.business_service.get_business_profile", AsyncMock(return_value=None)):
        with pytest.raises(NotFoundException):
            await update_assessment_status(db, user, True, {"score": 87})


@pytest.mark.asyncio
async def test_update_assessment_status_rolls_back_on_database_error():
    db = AsyncMock()
    db.commit.side_effect = SQLAlchemyError("commit failed")
    profile = SimpleNamespace(assessment_completed=False, assessment_data={}, updated_at=None)
    user = SimpleNamespace(id="user-123")

    with patch("services.business_service.get_business_profile", AsyncMock(return_value=profile)):
        with pytest.raises(DatabaseException, match="Failed to update assessment status"):
            await update_assessment_status(db, user, True, {"score": 87})

    db.rollback.assert_awaited_once()