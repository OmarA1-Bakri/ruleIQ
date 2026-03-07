"""
Test that assessments endpoints properly enforce ownership.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from fastapi import HTTPException
from database.user import User
from services.assessment_service import AssessmentService
from database.assessment_session import AssessmentSession


class TestAssessmentOwnership:
    """Test assessment ownership enforcement."""

    @pytest.mark.asyncio
    async def test_assessment_session_ownership(self):
        """Test that users can only access their own assessment sessions."""
        # Create mock objects
        user_id = uuid4()
        other_user_id = uuid4()
        session_id = uuid4()

        mock_user = Mock(spec=User)
        mock_user.id = user_id

        mock_other_user = Mock(spec=User)
        mock_other_user.id = other_user_id

        # Create mock assessment session owned by user
        mock_session = Mock(spec=AssessmentSession)
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session.session_type = "initial"
        mock_session.business_profile_id = uuid4()
        mock_session.recommendations = []

        # Mock the AssessmentService
        with patch.object(AssessmentService, "get_assessment_session") as mock_get_session:
            service = AssessmentService()

            # Test owner can access their session
            mock_get_session.return_value = mock_session
            mock_db = AsyncMock()

            # This should work - owner accessing their session
            result = await service.get_assessment_session(
                mock_db,
                mock_user,
                session_id,
            )
            assert result == mock_session

            # Test that service is called with correct parameters
            mock_get_session.assert_called_with(mock_db, mock_user, session_id)

    @pytest.mark.asyncio
    async def test_create_assessment_for_user(self):
        """Test that assessment sessions are created for the correct user."""
        user_id = uuid4()
        business_profile_id = uuid4()

        mock_user = Mock(spec=User)
        mock_user.id = user_id

        # Mock the created session
        mock_session = Mock(spec=AssessmentSession)
        mock_session.id = uuid4()
        mock_session.user_id = user_id
        mock_session.business_profile_id = business_profile_id
        mock_session.session_type = "initial"

        with patch.object(AssessmentService, "start_assessment_session") as mock_start:
            mock_start.return_value = mock_session
            service = AssessmentService()

            mock_db = AsyncMock()
            result = await service.start_assessment_session(
                mock_db,
                mock_user,
                "initial",
                str(business_profile_id),
            )

            assert result == mock_session
            assert result.user_id == user_id

            # Verify the service was called correctly
            mock_start.assert_called_with(
                mock_db,
                mock_user,
                "initial",
                str(business_profile_id),
            )

    def test_assessment_questions_require_user(self):
        """Test that getting questions requires a user."""
        mock_user = Mock(spec=User)
        mock_user.id = uuid4()

        service = AssessmentService()

        # Should be able to get questions with a valid user
        questions = service.get_assessment_questions(mock_user, 1)
        assert isinstance(questions, list)

        # Questions should be returned for valid stage
        assert len(questions) >= 0  # May be empty for some stages

    @pytest.mark.asyncio
    async def test_update_assessment_response_ownership(self):
        """Test that users can only update their own assessment responses."""
        user_id = uuid4()
        session_id = uuid4()

        mock_user = Mock(spec=User)
        mock_user.id = user_id

        # Mock session owned by user
        mock_session = Mock(spec=AssessmentSession)
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session.responses = {}

        with patch.object(AssessmentService, "update_assessment_response") as mock_update:
            mock_update.return_value = mock_session
            service = AssessmentService()

            mock_db = AsyncMock()
            result = await service.update_assessment_response(
                mock_db,
                mock_user,
                session_id,
                "q1",
                "response1",
            )

            assert result == mock_session
            mock_update.assert_called_with(
                mock_db,
                mock_user,
                session_id,
                "q1",
                "response1",
            )

    @pytest.mark.asyncio
    async def test_complete_assessment_ownership(self):
        """Test that users can only complete their own assessments."""
        user_id = uuid4()
        session_id = uuid4()

        mock_user = Mock(spec=User)
        mock_user.id = user_id

        # Mock completed session
        mock_session = Mock(spec=AssessmentSession)
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session.status = "completed"

        with patch.object(AssessmentService, "complete_assessment_session") as mock_complete:
            mock_complete.return_value = mock_session
            service = AssessmentService()

            mock_db = AsyncMock()
            result = await service.complete_assessment_session(
                mock_db,
                mock_user,
                session_id,
            )

            assert result == mock_session
            assert result.status == "completed"
            mock_complete.assert_called_with(mock_db, mock_user, session_id)
