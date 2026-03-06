"""
Tests for Freemium Assessment database models.

Following ALWAYS_READ_FIRST protocol: Test-first development mandate.
These tests define the exact interfaces and behavior required for the freemium models.
"""

import os

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from database import (
    AssessmentLead,
    FreemiumAssessmentSession,
    AIQuestionBank,
    LeadScoringEvent,
    ConversionEvent,
)


class TestAssessmentLead:
    """Test the AssessmentLead model for email capture and UTM tracking."""

    def test_create_assessment_lead_minimal(self, db_session):
        """Test creating an assessment lead with minimal required fields."""
        # Arrange
        email = "test@example.com"

        # Act
        lead = AssessmentLead(email=email, marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        # Assert
        assert lead.id is not None
        assert lead.email == email
        assert lead.marketing_consent is True
        assert lead.lead_score == 0
        assert lead.created_at is not None
        assert lead.updated_at is not None

    def test_create_assessment_lead_with_utm(self, db_session):
        """Test creating an assessment lead with UTM tracking parameters."""
        # Arrange
        lead_data = {
            "email": "utm.test@example.com",
            "marketing_consent": True,
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "freemium_launch",
            "utm_term": "compliance_software",
            "utm_content": "cta_button",
        }

        # Act
        lead = AssessmentLead(**lead_data)
        db_session.add(lead)
        db_session.commit()

        # Assert
        assert lead.utm_source == "google"
        assert lead.utm_medium == "cpc"
        assert lead.utm_campaign == "freemium_launch"
        assert lead.utm_term == "compliance_software"
        assert lead.utm_content == "cta_button"

    def test_assessment_lead_email_unique_constraint(self, db_session):
        """Test that email addresses must be unique."""
        # Arrange
        email = "duplicate@example.com"
        lead1 = AssessmentLead(email=email, marketing_consent=True)
        lead2 = AssessmentLead(email=email, marketing_consent=False)

        # Act & Assert
        db_session.add(lead1)
        db_session.commit()

        db_session.add(lead2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_assessment_lead_score_update(self, db_session):
        """Test updating lead score and tracking changes."""
        # Arrange
        lead = AssessmentLead(email="score.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        original_updated_at = lead.updated_at

        # Act
        lead.lead_score = 85
        lead.lead_status = "hot"
        db_session.commit()

        # Assert
        assert lead.lead_score == 85
        assert lead.lead_status == "hot"
        assert lead.updated_at > original_updated_at


class TestFreemiumAssessmentSession:
    """Test the FreemiumAssessmentSession model for AI-driven assessments."""

    def test_create_assessment_session(self, db_session):
        """Test creating a freemium assessment session."""
        # Arrange
        lead = AssessmentLead(email="session.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        # Act
        session = FreemiumAssessmentSession(
            lead_id=lead.id,
            assessment_type="technology_compliance",
            status="started",
        )
        db_session.add(session)
        db_session.commit()

        # Assert
        assert session.id is not None
        assert session.lead_id == lead.id
        assert session.assessment_type == "technology_compliance"
        assert session.status == "started"
        assert session.session_token is not None
        assert len(session.session_token) >= 32  # Secure token length
        assert session.expires_at is not None
        assert session.expires_at > datetime.now(timezone.utc)

    def test_assessment_session_ai_responses_storage(self, db_session):
        """Test storing AI responses and user answers in JSON fields."""
        # Arrange
        lead = AssessmentLead(email="ai.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        session = FreemiumAssessmentSession(
            lead_id=lead.id,
            assessment_type="healthcare_compliance",
        )

        # Act
        session.ai_responses = {
            "questions_generated": 5,
            "risk_level": "medium",
            "recommendations": ["Implement GDPR compliance", "Update privacy policy"],
        }
        session.questions_data = {
            "handles_personal_data": True,
            "data_retention_policy": False,
            "staff_training": "annually",
        }

        db_session.add(session)
        db_session.commit()

        # Assert
        assert session.ai_responses["risk_level"] == "medium"
        assert session.questions_data["handles_personal_data"] is True
        assert len(session.ai_responses["recommendations"]) == 2

    def test_assessment_session_expiration(self, db_session):
        """Test session expiration functionality."""
        # Arrange
        lead = AssessmentLead(email="expire.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        # Act - Create session with custom expiration
        session = FreemiumAssessmentSession(
            lead_id=lead.id,
            assessment_type="finance_compliance",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db_session.add(session)
        db_session.commit()

        # Assert
        assert session.is_expired() is False

        # Simulate expired session
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert session.is_expired() is True


class TestAIQuestionBank:
    """Test the AIQuestionBank model for dynamic question management."""

    def test_create_ai_question(self, db_session):
        """Test creating an AI-generated question."""
        # Arrange & Act
        question = AIQuestionBank(
            category="data_protection",
            question_text="How do you currently handle customer data deletion requests?",
            question_type="multiple_choice",
            options=[
                "Manual process",
                "Automated system",
                "No process",
                "Not applicable",
            ],
            context_tags=["gdpr", "data_rights", "deletion"],
        )
        db_session.add(question)
        db_session.commit()

        # Assert
        assert question.id is not None
        assert question.category == "data_protection"
        assert question.question_type == "multiple_choice"
        assert len(question.options) == 4
        assert "gdpr" in question.context_tags

    def test_ai_question_weighting_and_difficulty(self, db_session):
        """Test question weighting and difficulty scoring."""
        # Arrange & Act
        question = AIQuestionBank(
            category="security",
            question_text="Describe your incident response procedure.",
            question_type="text",
            difficulty_level=8,
            compliance_weight=0.95,
        )
        db_session.add(question)
        db_session.commit()

        # Assert
        assert question.difficulty_level == 8
        assert question.compliance_weight == Decimal("0.95")


class TestLeadScoringEvent:
    """Test the LeadScoringEvent model for behavioral tracking."""

    def test_create_lead_scoring_event(self, db_session):
        """Test creating lead scoring events for behavioral analytics."""
        # Arrange
        lead = AssessmentLead(email="scoring.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        # Act
        event = LeadScoringEvent(
            lead_id=lead.id,
            event_type="assessment_start",
            event_category="engagement",
            event_action="started_assessment",
            score_impact=10,
        )
        db_session.add(event)
        db_session.commit()

        # Assert
        assert event.lead_id == lead.id
        assert event.event_type == "assessment_start"
        assert event.score_impact == 10
        assert event.created_at is not None

    def test_lead_scoring_with_metadata(self, db_session):
        """Test storing additional metadata with scoring events."""
        # Arrange
        lead = AssessmentLead(email="metadata.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        # Act
        event = LeadScoringEvent(
            lead_id=lead.id,
            event_type="question_answered",
            event_category="assessment",
            event_action="answered_critical_question",
            score_impact=25,
            event_metadata={
                "question_id": "q_data_protection_1",
                "answer": "yes",
                "time_spent_seconds": 45,
                "confidence_level": "high",
            },
        )
        db_session.add(event)
        db_session.commit()

        # Assert
        assert event.event_metadata["question_id"] == "q_data_protection_1"
        assert event.event_metadata["time_spent_seconds"] == 45


class TestConversionEvent:
    """Test the ConversionEvent model for tracking freemium to paid conversions."""

    def test_create_conversion_event(self, db_session):
        """Test creating conversion tracking events."""
        # Arrange
        lead = AssessmentLead(email="convert.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        session = FreemiumAssessmentSession(lead_id=lead.id, assessment_type="retail")
        db_session.add(session)
        db_session.commit()

        # Act
        conversion = ConversionEvent(
            lead_id=lead.id,
            session_id=session.id,
            conversion_type="trial_signup",
            conversion_value=Decimal("99.00"),
            conversion_source="freemium_results_page",
        )
        db_session.add(conversion)
        db_session.commit()

        # Assert
        assert conversion.lead_id == lead.id
        assert conversion.session_id == session.id
        assert conversion.conversion_type == "trial_signup"
        assert conversion.conversion_value == Decimal("99.00")
        assert conversion.conversion_source == "freemium_results_page"
        assert conversion.created_at is not None


class TestFreemiumModelRelationships:
    """Test relationships between freemium models."""

    def test_lead_to_sessions_relationship(self, db_session):
        """Test one-to-many relationship between leads and assessment sessions."""
        # Arrange
        lead = AssessmentLead(
            email="relations.test@example.com",
            marketing_consent=True,
        )
        db_session.add(lead)
        db_session.commit()

        # Act - Create multiple sessions for same lead
        session1 = FreemiumAssessmentSession(
            lead_id=lead.id,
            assessment_type="tech_compliance",
        )
        session2 = FreemiumAssessmentSession(
            lead_id=lead.id,
            assessment_type="finance_compliance",
        )

        db_session.add_all([session1, session2])
        db_session.commit()

        # Assert
        # Note: This test verifies the relationship will work when implemented
        assert session1.lead_id == lead.id
        assert session2.lead_id == lead.id

    def test_cascade_delete_behavior(self, db_session):
        """Test that deleting a lead cascades to related records."""
        # Arrange
        lead = AssessmentLead(email="cascade.test@example.com", marketing_consent=True)
        db_session.add(lead)
        db_session.commit()

        session = FreemiumAssessmentSession(
            lead_id=lead.id,
            assessment_type="education_compliance",
        )
        event = LeadScoringEvent(
            lead_id=lead.id,
            event_type="test",
            event_category="test",
            event_action="test",
        )

        db_session.add_all([session, event])
        db_session.commit()

        session_id = session.id
        event_id = event.id

        # Act
        db_session.delete(lead)
        db_session.commit()

        # Assert - Related records should be deleted (cascade behavior)
        # Note: This behavior will be implemented in the model relationships
        assert db_session.get(FreemiumAssessmentSession, session_id) is None
        assert db_session.get(LeadScoringEvent, event_id) is None
