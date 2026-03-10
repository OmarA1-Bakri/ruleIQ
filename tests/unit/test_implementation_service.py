from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from database.implementation_plan import ImplementationPlan
from services.implementation_service import (
    generate_implementation_plan,
    get_implementation_plan,
    get_plan_dashboard,
    list_implementation_plans,
    update_task_status,
)


def _mock_scalar_result(first_value=None, all_value=None):
    scalar_result = Mock()
    scalar_result.first.return_value = first_value
    scalar_result.all.return_value = all_value if all_value is not None else []
    result = Mock()
    result.scalars.return_value = scalar_result
    return result


@pytest.mark.asyncio
async def test_generate_implementation_plan_creates_plan_from_ai_output():
    db = AsyncMock()
    db.add = Mock()
    user = SimpleNamespace(id=uuid4())
    framework_id = uuid4()
    profile = SimpleNamespace(id=uuid4())
    framework = SimpleNamespace(id=framework_id, display_name="ISO 27001")
    db.execute.side_effect = [
        _mock_scalar_result(first_value=profile),
        _mock_scalar_result(first_value=framework),
    ]
    plan_data = {"title": "Initial rollout", "phases": [{"name": "Phase 1", "tasks": []}]}

    with patch(
        "services.implementation_service.generate_plan_with_ai",
        AsyncMock(return_value=plan_data),
    ):
        plan = await generate_implementation_plan(db, user, framework_id, timeline_weeks=4)

    assert isinstance(plan, ImplementationPlan)
    assert plan.user_id == user.id
    assert plan.business_profile_id == profile.id
    assert plan.framework_id == framework_id
    assert plan.title == "Initial rollout"
    assert plan.phases == plan_data["phases"]
    assert plan.status == "not_started"
    db.add.assert_called_once_with(plan)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(plan)


@pytest.mark.asyncio
async def test_generate_implementation_plan_requires_business_profile():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    db.execute.return_value = _mock_scalar_result(first_value=None)

    with pytest.raises(ValueError, match="Business profile not found"):
        await generate_implementation_plan(db, user, uuid4())


@pytest.mark.asyncio
async def test_get_and_list_implementation_plans_return_query_results():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    plan = SimpleNamespace(id=uuid4())
    db.execute.side_effect = [
        _mock_scalar_result(first_value=plan),
        _mock_scalar_result(all_value=[plan]),
    ]

    fetched = await get_implementation_plan(db, user, plan.id)
    listed = await list_implementation_plans(db, user)

    assert fetched is plan
    assert listed == [plan]


@pytest.mark.asyncio
async def test_update_task_status_updates_matching_task_and_flags_json():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    plan = SimpleNamespace(
        phases=[
            {"tasks": [{"id": "task-1", "status": "not_started"}]},
            {"tasks": [{"task_id": "task-2", "status": "not_started"}]},
        ]
    )

    with patch(
        "services.implementation_service.get_implementation_plan",
        AsyncMock(return_value=plan),
    ), patch("services.implementation_service.flag_modified") as mock_flag_modified:
        result = await update_task_status(db, user, uuid4(), "task-2", "completed")

    assert result is plan
    assert plan.phases[1]["tasks"][0]["status"] == "completed"
    mock_flag_modified.assert_called_once_with(plan, "phases")
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(plan)


@pytest.mark.asyncio
async def test_update_task_status_raises_when_task_missing():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    plan = SimpleNamespace(phases=[{"tasks": [{"id": "task-1", "status": "not_started"}]}])

    with patch(
        "services.implementation_service.get_implementation_plan",
        AsyncMock(return_value=plan),
    ):
        with pytest.raises(ValueError, match="Task not found in plan"):
            await update_task_status(db, user, uuid4(), "missing-task", "completed")


@pytest.mark.asyncio
async def test_get_plan_dashboard_computes_progress_and_timeline():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())
    now = datetime.now(timezone.utc)
    plan = SimpleNamespace(
        title="ISO Rollout",
        phases=[
            {"tasks": [{"status": "completed"}, {"status": "not_started"}]},
            {"tasks": [{"status": "completed"}]},
        ],
        created_at=now - timedelta(days=5),
        planned_end_date=now + timedelta(days=7),
    )

    with patch(
        "services.implementation_service.get_implementation_plan",
        AsyncMock(return_value=plan),
    ):
        dashboard = await get_plan_dashboard(db, user, uuid4())

    assert dashboard == {
        "plan_title": "ISO Rollout",
        "overall_progress": 66.67,
        "timeline": {
            "days_elapsed": 5,
            "days_remaining": 7,
            "on_track": True,
        },
        "total_tasks": 3,
        "completed_tasks": 2,
    }


@pytest.mark.asyncio
async def test_get_plan_dashboard_returns_none_when_plan_missing():
    db = AsyncMock()
    user = SimpleNamespace(id=uuid4())

    with patch(
        "services.implementation_service.get_implementation_plan",
        AsyncMock(return_value=None),
    ):
        dashboard = await get_plan_dashboard(db, user, uuid4())

    assert dashboard is None