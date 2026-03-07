from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.exceptions import DatabaseException, NotFoundException
from database.assessment_session import AssessmentSession
from database.business_profile import BusinessProfile
from database.user import User
from services.framework_service import get_relevant_frameworks


class AssessmentService:
    def __init__(self) -> None:
        pass  # db session will be passed to methods

    async def start_assessment_session(
        self,
        db: AsyncSession,
        user: User,
        session_type: str = "compliance_scoping",
        business_profile_id: Optional[UUID] = None,
    ) -> AssessmentSession:
        """Start a new assessment session for the user."""
        try:
            # Check if there's an active session
            stmt_existing = (
                select(AssessmentSession)
                .where(AssessmentSession.user_id == user.id)
                .where(AssessmentSession.status == "in_progress")
                .order_by(AssessmentSession.created_at.desc()),
            )
            result_existing = await db.execute(stmt_existing)
            existing_session = result_existing.scalars().first()

            if existing_session:
                return existing_session

            # Get business profile if not provided
            if not business_profile_id:
                stmt_profile = select(BusinessProfile).where(
                    BusinessProfile.user_id == user.id,
                )
                result_profile = await db.execute(stmt_profile)
                business_profile = result_profile.scalars().first()
                business_profile_id = business_profile.id if business_profile else None

            # Create new session
            new_session = AssessmentSession(
                user_id=user.id,
                business_profil=business_profile_id,  # Note: column name is truncated in model
                session_type=session_type,
                status="in_progress",  # Ensure status is set
                total_stages=5,  # Basic info, Industry, Data handling, Tech stack, Compliance goals
                current_stage=1,  # Start at stage 1
                responses={},
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            return new_session
        except sa.exc.SQLAlchemyError as e:
            await db.rollback()
            raise DatabaseException(f"Error starting assessment session: {e}")

    async def get_assessment_session(
        self, db: AsyncSession, user: User, session_id: UUID
    ) -> Optional[AssessmentSession]:
        """Get a specific assessment session."""
        try:
            stmt = (
                select(AssessmentSession)
                .where(AssessmentSession.id == session_id)
                .where(AssessmentSession.user_id == user.id),
            )
            result = await db.execute(stmt)
            session = result.scalars().first()
            # if not session:
            #     raise NotFoundException(f"Assessment session {session_id} not found for user {user.id}")
            return session
        except sa.exc.SQLAlchemyError as e:
            # Log error appropriately
            raise DatabaseException(
                f"Error retrieving assessment session {session_id}: {e}",
            )

    async def get_current_assessment_session(
        self, db: AsyncSession, user: User
    ) -> Optional[AssessmentSession]:
        """Get the current active assessment session for the user."""
        try:
            stmt = (
                select(AssessmentSession)
                .where(AssessmentSession.user_id == user.id)
                .where(AssessmentSession.status == "in_progress")
                .order_by(AssessmentSession.created_at.desc()),
            )
            result = await db.execute(stmt)
            session = result.scalars().first()
            return session  # Can be None if no active session, handled by caller
        except sa.exc.SQLAlchemyError as e:
            # Log error appropriately
            raise DatabaseException(
                f"Error retrieving current assessment session for user {user.id}: {e}",
            )

    async def get_user_assessment_sessions(
        self, db: AsyncSession, user: User
    ) -> List[AssessmentSession]:
        """Get all assessment sessions for the user."""
        try:
            stmt = (
                select(AssessmentSession)
                .where(AssessmentSession.user_id == user.id)
                .order_by(AssessmentSession.created_at.desc()),
            )
            result = await db.execute(stmt)
            sessions = result.scalars().all()
            return sessions
        except sa.exc.SQLAlchemyError as e:
            # Log error appropriately
            raise DatabaseException(
                f"Error retrieving assessment sessions for user {user.id}: {e}",
            )

    async def update_assessment_response(
        self,
        db: AsyncSession,
        user: User,
        session_id: UUID,
        question_id: str,
        answer: Dict,
    ) -> AssessmentSession:
        """Update an assessment response."""
        try:
            session = await self.get_assessment_session(db, user, session_id)
            if not session:
                # Consider using NotFoundException if get_assessment_session can return None and it's an error here
                raise NotFoundException(
                    f"Assessment session {session_id} not found for user {user.id} during update.",
                )

            if session.status != "in_progress":
                raise ValueError(
                    "Assessment session is not in progress and cannot be updated."
                )  # Or a custom domain exception

            # Ensure responses is initialized if it's None (though model default should handle this)
            if session.responses is None:
                session.responses = {}

            session.responses[question_id] = answer
            session.updated_at = datetime.now(timezone.utc)
            # Potentially update current_stage based on answered questions
            # For example: session.current_stage = calculate_next_stage(session.responses)

            db.add(session)  # Add to session for SQLAlchemy to track changes
            await db.commit()
            await db.refresh(session)
            return session
        except sa.exc.SQLAlchemyError as e:
            await db.rollback()
            # Log error appropriately
            raise DatabaseException(
                f"Error updating assessment response for session {session_id}: {e}",
            )
        except NotFoundException:  # Re-raise if we want it to propagate
            raise
        except ValueError:  # Catch specific domain errors
            # Log error appropriately
            raise  # Or wrap in a custom API error

    async def complete_assessment_session(
        self, db: AsyncSession, user: User, session_id: UUID
    ) -> AssessmentSession:
        """Complete an assessment session and generate recommendations."""
        try:
            session = await self.get_assessment_session(db, user, session_id)
            if not session:
                raise NotFoundException(
                    f"Assessment session {session_id} not found for user {user.id} to complete.",
                )

            if session.status != "in_progress":
                # Consider a more specific exception, e.g., InvalidSessionStateError
                raise ValueError(
                    f"Assessment session {session_id} is not 'in_progress' (status: {session.status}). Cannot complete."
                )

            # Perform any final validation or processing
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)

            # Generate recommendations based on responses
            # This would typically involve analyzing session.responses
            relevant_frameworks_data = await get_relevant_frameworks(db, user)
            recommendations = []
            if relevant_frameworks_data:
                for framework_info in relevant_frameworks_data:
                    # Basic recommendation: suggest frameworks with high relevance
                    # Ensure framework_info structure is as expected by get_relevant_frameworks
                    # It returns a list of dicts like: {"framework": framework_object.to_dict(), "relevance_score": score} # noqa: E501
                    if (
                        framework_info.get("relevance_score", 0) > 50
                    ):  # Adjusted threshold based on calculate_framework_relevance logic
                        framework_details = framework_info.get("framework", {})
                        recommendations.append(
                            {
                                "framework_id": str(framework_details.get("id")),
                                "framework_name": framework_details.get("name"),
                                "reason": f"High relevance score: {framework_info['relevance_score']}",
                            }
                        )

            session.recommendations = recommendations  # Ensure AssessmentSession model has this field as JSON or similar  # noqa: E501

            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session
        except sa.exc.SQLAlchemyError as e:
            await db.rollback()
            # Log error appropriately
            raise DatabaseException(
                f"Error completing assessment session {session_id}: {e}",
            )
        except NotFoundException:  # Re-raise
            raise
        except ValueError:  # Re-raise specific domain error
            # Log error appropriately
            raise

    def get_assessment_questions(self, user: User, stage: int) -> List[Dict]:
        """Get assessment questions for a specific stage."""

        questions = {
            1: [  # Basic Information
                {
                    "question_id": "company_name",
                    "text": "What is your company's name?",
                    "question_type": "free_text",
                    "required": True,
                },
                {
                    "question_id": "industry",
                    "text": "What industry is your company in?",
                    "question_type": "multiple_choice",
                    "options": [
                        {"value": "technology", "label": "Technology"},
                        {"value": "finance", "label": "Finance"},
                        {"value": "healthcare", "label": "Healthcare"},
                        {"value": "retail", "label": "Retail"},
                        {"value": "manufacturing", "label": "Manufacturing"},
                        {"value": "other", "label": "Other"},
                    ],
                    "required": True,
                },
                {
                    "question_id": "company_size",
                    "text": "What is the size of your company (number of employees)?",
                    "question_type": "multiple_choice",
                    "options": [
                        {"value": "1-50", "label": "1-50"},
                        {"value": "51-200", "label": "51-200"},
                        {"value": "201-1000", "label": "201-1000"},
                        {"value": "1000+", "label": "1000+"},
                    ],
                    "required": True,
                },
            ],
            2: [  # Data Handling
                {
                    "id": "data_types_handled",
                    "question": "What types of sensitive data does your company handle?",
                    "type": "checkbox",
                    "options": [
                        "Personally Identifiable Information (PII)",
                        "Payment Card Industry (PCI) data",
                        "Protected Health Information (PHI)",
                        "Intellectual Property",
                        "Financial Data (non-PCI)",
                        "None of the above",
                    ],
                    "required": True,
                },
                {
                    "id": "data_storage_location",
                    "question": "Where is this sensitive data primarily stored?",
                    "type": "select",
                    "options": [
                        "Cloud (e.g., AWS, Azure, GCP)",
                        "On-premise servers",
                        "Hybrid (Cloud and On-premise)",
                        "Third-party SaaS applications",
                    ],
                    "required": True,
                },
            ],
            3: [  # Technology Stack
                {
                    "id": "cloud_providers",
                    "question": "Which cloud providers do you use (if any)?",
                    "type": "checkbox",
                    "options": [
                        "AWS",
                        "Azure",
                        "Google Cloud Platform (GCP)",
                        "Oracle Cloud",
                        "Other",
                        "None",
                    ],
                    "required": False,
                },
                {
                    "id": "saas_tools",
                    "question": "List key SaaS tools critical to your operations (e.g., Salesforce, Office 365, Slack).",
                    "type": "textarea",
                    "required": False,
                },
                {
                    "id": "development_practices",
                    "question": "Does your company follow secure software development practices (e.g., OWASP, DevSecOps)?",
                    "type": "radio",
                    "options": ["Yes", "No", "Partially", "Unsure"],
                    "required": True,
                },
            ],
            4: [  # Current Compliance Posture
                {
                    "id": "existing_certifications",
                    "question": "Does your company currently hold any compliance certifications?",
                    "type": "checkbox",
                    "options": [
                        "ISO 27001",
                        "SOC 2",
                        "PCI DSS",
                        "HIPAA Compliant",
                        "GDPR Compliant",
                        "None",
                    ],
                    "required": False,
                },
                {
                    "id": "planned_frameworks",
                    "question": "Which compliance frameworks is your company planning to achieve?",
                    "type": "checkbox",
                    "options": [
                        "GDPR",
                        "ISO 27001",
                        "Cyber Essentials",
                        "FCA",
                        "PCI DSS",
                        "SOC 2",
                    ],
                    "required": False,
                },
                {
                    "id": "compliance_budget",
                    "question": "What is your budget range for compliance initiatives?",
                    "type": "select",
                    "options": [
                        "Under £10K",
                        "£10K-£25K",
                        "£25K-£50K",
                        "£50K-£100K",
                        "Over £100K",
                    ],
                    "required": False,
                },
            ],
            5: [  # Goals and Timeline
                {
                    "id": "compliance_timeline",
                    "question": "What is your target timeline for achieving compliance?",
                    "type": "select",
                    "options": ["3 months", "6 months", "12 months", "18+ months"],
                    "required": True,
                },
                {
                    "id": "primary_driver",
                    "question": "What is the primary driver for your compliance initiative?",
                    "type": "select",
                    "options": [
                        "Customer requirements",
                        "Regulatory requirement",
                        "Business growth",
                        "Risk management",
                        "Competitive advantage",
                    ],
                    "required": True,
                },
                {
                    "id": "biggest_challenge",
                    "question": "What do you expect to be your biggest compliance challenge?",
                    "type": "select",
                    "options": [
                        "Understanding requirements",
                        "Resource allocation",
                        "Technical implementation",
                        "Policy development",
                        "Evidence collection",
                        "Ongoing maintenance",
                    ],
                    "required": False,
                },
            ],
        }

        return questions.get(stage, [])
