from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
import sqlalchemy as sa

from core.exceptions import DatabaseException, NotFoundException
from database.assessment_session import AssessmentSession
from services.assessment_service import AssessmentService


def _mock_scalar_result(first_value=None, all_value=None):
    scalar_result = Mock()
    scalar_result.first.return_value = first_value
    scalar_result.all.return_value = all_value if all_value is not None else []
    result = Mock()
    result.scalars.return_value = scalar_result
    return result


@pytest.mark.asyncio
async def test_start_assessment_session_returns_existing_in_progress_session():
    service = AssessmentService()
    db = AsyncMock()
    db.add = Mock()
    existing_session = SimpleNamespace(id=uuid4(), status="in_progress")
    db.execute.return_value = _mock_scalar_result(first_value=existing_session)
    user = SimpleNamespace(id="user-123")

    result = await service.start_assessment_session(db, user)

    assert result is existing_session
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_assessment_session_creates_new_session_with_business_profile_lookup():
    service = AssessmentService()
    db = AsyncMock()
    db.add = Mock()
    profile_id = uuid4()
    db.execute.side_effect = [
        _mock_scalar_result(first_value=None),
        _mock_scalar_result(first_value=SimpleNamespace(id=profile_id)),
    ]
    user = SimpleNamespace(id="user-123")

    session = await service.start_assessment_session(db, user)

    assert isinstance(session, AssessmentSession)
    assert session.user_id == "user-123"
    assert session.business_profile_id == profile_id
    assert session.status == "in_progress"
    assert session.current_stage == 1
    assert session.total_stages == 5
    assert session.responses == {}
    db.add.assert_called_once_with(session)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_start_assessment_session_raises_database_exception_on_sqlalchemy_error():
    service = AssessmentService()
    db = AsyncMock()
    db.add = Mock()
    db.execute.side_effect = sa.exc.SQLAlchemyError("select failed")
    user = SimpleNamespace(id="user-123")

    with pytest.raises(DatabaseException, match="Error starting assessment session"):
        await service.start_assessment_session(db, user)

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_assessment_session_returns_matching_session():
    service = AssessmentService()
    db = AsyncMock()
    session_id = uuid4()
    session = SimpleNamespace(id=session_id)
    db.execute.return_value = _mock_scalar_result(first_value=session)
    user = SimpleNamespace(id="user-123")

    result = await service.get_assessment_session(db, user, session_id)

    assert result is session


@pytest.mark.asyncio
async def test_get_user_assessment_sessions_returns_all_sessions():
    service = AssessmentService()
    db = AsyncMock()
    sessions = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
    db.execute.return_value = _mock_scalar_result(all_value=sessions)
    user = SimpleNamespace(id="user-123")

    result = await service.get_user_assessment_sessions(db, user)

    assert result == sessions


@pytest.mark.asyncio
async def test_update_assessment_response_updates_in_progress_session():
    service = AssessmentService()
    db = AsyncMock()
    db.add = Mock()
    session_id = uuid4()
    session = SimpleNamespace(status="in_progress", responses={}, updated_at=None)
    user = SimpleNamespace(id="user-123")

    with patch.object(service, "get_assessment_session", AsyncMock(return_value=session)):
        result = await service.update_assessment_response(
            db,
            user,
            session_id,
            "company_name",
            {"value": "RuleIQ"},
        )

    assert result is session
    assert session.responses == {"company_name": {"value": "RuleIQ"}}
    assert session.updated_at is not None
    db.add.assert_called_once_with(session)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_update_assessment_response_raises_not_found_when_session_missing():
    service = AssessmentService()
    db = AsyncMock()
    user = SimpleNamespace(id="user-123")
    session_id = uuid4()

    with patch.object(service, "get_assessment_session", AsyncMock(return_value=None)):
        with pytest.raises(NotFoundException):
            await service.update_assessment_response(
                db,
                user,
                session_id,
                "company_name",
                {"value": "RuleIQ"},
            )


@pytest.mark.asyncio
async def test_complete_assessment_session_sets_completed_and_recommendations():
    service = AssessmentService()
    db = AsyncMock()
    db.add = Mock()
    session_id = uuid4()
    session = SimpleNamespace(
        status="in_progress",
        completed_at=None,
        recommendations=[],
    )
    user = SimpleNamespace(id="user-123")
    relevant_frameworks = [
        {"framework": {"id": uuid4(), "name": "GDPR"}, "relevance_score": 100.0},
        {"framework": {"id": uuid4(), "name": "Cyber Essentials"}, "relevance_score": 50.0},
    ]

    with patch.object(service, "get_assessment_session", AsyncMock(return_value=session)), patch(
        "services.assessment_service.get_relevant_frameworks",
        AsyncMock(return_value=relevant_frameworks),
    ):
        result = await service.complete_assessment_session(db, user, session_id)

    assert result is session
    assert session.status == "completed"
    assert session.completed_at is not None
    assert session.recommendations == [
        {
            "framework_id": str(relevant_frameworks[0]["framework"]["id"]),
            "framework_name": "GDPR",
            "reason": "High relevance score: 100.0",
        }
    ]
    db.add.assert_called_once_with(session)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_complete_assessment_session_raises_not_found_when_session_missing():
    service = AssessmentService()
    db = AsyncMock()
    user = SimpleNamespace(id="user-123")
    session_id = uuid4()

    with patch.object(service, "get_assessment_session", AsyncMock(return_value=None)):
        with pytest.raises(NotFoundException):
            await service.complete_assessment_session(db, user, session_id)


def test_get_assessment_questions_returns_stage_questions_and_defaults_to_empty():
    service = AssessmentService()
    user = SimpleNamespace(id="user-123")

    stage_one_questions = service.get_assessment_questions(user, 1)
    unknown_stage_questions = service.get_assessment_questions(user, 99)

    assert len(stage_one_questions) == 3
    assert stage_one_questions[0]["question_id"] == "company_name"
    assert unknown_stage_questions == []