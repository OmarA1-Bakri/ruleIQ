from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import DatabaseException, NotFoundException
from database.compliance_framework import ComplianceFramework
from services.framework_service import (
    calculate_framework_relevance,
    get_all_frameworks,
    get_framework_by_id,
    get_framework_by_name,
    get_relevant_frameworks,
    initialize_default_frameworks,
)


def _mock_scalar_result(first_value=None, all_value=None):
    scalar_result = Mock()
    scalar_result.first.return_value = first_value
    scalar_result.all.return_value = all_value if all_value is not None else []
    result = Mock()
    result.scalars.return_value = scalar_result
    return result


@pytest.mark.asyncio
async def test_get_all_frameworks_returns_active_frameworks():
    db = AsyncMock()
    frameworks = [SimpleNamespace(name="GDPR"), SimpleNamespace(name="ISO 27001")]
    db.execute.return_value = _mock_scalar_result(all_value=frameworks)

    result = await get_all_frameworks(db)

    assert result == frameworks
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_framework_by_id_returns_framework():
    db = AsyncMock()
    framework_id = uuid4()
    framework = SimpleNamespace(id=framework_id, name="GDPR")
    db.execute.return_value = _mock_scalar_result(first_value=framework)
    user = SimpleNamespace(id="user-123")

    result = await get_framework_by_id(db, user, framework_id)

    assert result is framework


@pytest.mark.asyncio
async def test_get_framework_by_id_raises_not_found_for_missing_framework():
    db = AsyncMock()
    framework_id = uuid4()
    db.execute.return_value = _mock_scalar_result(first_value=None)
    user = SimpleNamespace(id="user-123")

    with pytest.raises(NotFoundException, match=str(framework_id)):
        await get_framework_by_id(db, user, framework_id)


@pytest.mark.asyncio
async def test_get_framework_by_name_raises_database_exception_on_error():
    db = AsyncMock()
    db.execute.side_effect = SQLAlchemyError("select failed")

    with pytest.raises(DatabaseException, match="Failed to retrieve framework by name"):
        await get_framework_by_name(db, "GDPR")


def test_calculate_framework_relevance_combines_all_scoring_inputs():
    profile = SimpleNamespace(industry="Technology", employee_count=75, data_sensitivity="High")
    framework = SimpleNamespace(
        applicable_indu=["Technology", "Financial Services"],
        employee_thresh=50,
        category="Data Protection",
    )

    score = calculate_framework_relevance(profile, framework)

    assert score == 100.0


@pytest.mark.asyncio
async def test_get_relevant_frameworks_returns_sorted_matches():
    db = AsyncMock()
    user = SimpleNamespace(id="user-123")
    profile = SimpleNamespace(industry="Technology", employee_count=80, data_sensitivity="High")
    db.execute.return_value = _mock_scalar_result(first_value=profile)

    top_framework = Mock()
    top_framework.applicable_indu = ["Technology"]
    top_framework.employee_thresh = 50
    top_framework.category = "Data Protection"
    top_framework.to_dict.return_value = {"name": "GDPR"}

    lower_framework = Mock()
    lower_framework.applicable_indu = ["Technology"]
    lower_framework.employee_thresh = 200
    lower_framework.category = "Cybersecurity"
    lower_framework.to_dict.return_value = {"name": "Cyber Essentials"}

    irrelevant_framework = Mock()
    irrelevant_framework.applicable_indu = ["Healthcare"]
    irrelevant_framework.employee_thresh = 500
    irrelevant_framework.category = "Other"
    irrelevant_framework.to_dict.return_value = {"name": "HIPAA"}

    with patch(
        "services.framework_service.get_all_frameworks",
        AsyncMock(return_value=[lower_framework, irrelevant_framework, top_framework]),
    ):
        result = await get_relevant_frameworks(db, user)

    assert result == [
        {"framework": {"name": "GDPR"}, "relevance_score": 100.0},
        {"framework": {"name": "Cyber Essentials"}, "relevance_score": 50.0},
    ]


@pytest.mark.asyncio
async def test_get_relevant_frameworks_returns_empty_list_without_profile():
    db = AsyncMock()
    db.execute.return_value = _mock_scalar_result(first_value=None)
    user = SimpleNamespace(id="user-123")

    result = await get_relevant_frameworks(db, user)

    assert result == []


@pytest.mark.asyncio
async def test_initialize_default_frameworks_adds_only_missing_frameworks():
    db = AsyncMock()
    db.add = Mock()

    with patch(
        "services.framework_service.get_framework_by_name",
        AsyncMock(side_effect=[None, SimpleNamespace(name="Cyber Essentials"), None]),
    ):
        await initialize_default_frameworks(db)

    db.commit.assert_awaited_once()
    assert db.add.call_count == 2
    added_frameworks = [call.args[0] for call in db.add.call_args_list]
    assert all(isinstance(framework, ComplianceFramework) for framework in added_frameworks)
    assert {framework.name for framework in added_frameworks} == {"GDPR", "ISO 27001"}


@pytest.mark.asyncio
async def test_initialize_default_frameworks_rolls_back_on_database_error():
    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = SQLAlchemyError("commit failed")

    with patch(
        "services.framework_service.get_framework_by_name",
        AsyncMock(return_value=None),
    ):
        with pytest.raises(DatabaseException, match="Failed to initialize default frameworks"):
            await initialize_default_frameworks(db)

    db.rollback.assert_awaited_once()