"""

Test utilities router for cleaning up test data.
Only enabled in development/testing environments.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.db_setup import get_db
from database import User

# Remove unused import

router = APIRouter()


def is_test_environment() -> bool:
    """Check if we're running in a test environment."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    return env in ["development", "test", "testing", "local"]


@router.delete("/cleanup-test-users")
async def cleanup_test_users(email_pattern: str = "@example.com", db: Session = Depends(get_db)):
    """
    Clean up test users from the database.
    Only works in test/development environments.

    Args:
        email_pattern: Pattern to match test user emails (default: @example.com)

    Returns:
        dict: Number of users deleted
    """
    if not is_test_environment():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in test environments",
        )

    try:
        # Find test users
        test_users = db.query(User).filter(User.email.like(f"%{email_pattern}%")).all()
        count = len(test_users)

        if count == 0:
            return {"deleted_users": 0, "pattern": email_pattern}

        # Clean up related data first to avoid foreign key constraints
        from database import (
            AuditLog,
            UserSession,
            UserRole,
            BusinessProfile,
            AssessmentSession,
            GeneratedPolicy,
            ChatConversation,
            ReportSchedule,
            EvidenceItem,
            ImplementationPlan,
            ReadinessAssessment,
        )

        for user in test_users:
            # Delete business-related data
            db.query(BusinessProfile).filter(BusinessProfile.user_id == user.id).delete()
            db.query(AssessmentSession).filter(AssessmentSession.user_id == user.id).delete()
            db.query(GeneratedPolicy).filter(GeneratedPolicy.user_id == user.id).delete()
            db.query(ChatConversation).filter(ChatConversation.user_id == user.id).delete()
            db.query(ReportSchedule).filter(ReportSchedule.user_id == user.id).delete()
            db.query(EvidenceItem).filter(EvidenceItem.user_id == user.id).delete()
            db.query(ImplementationPlan).filter(ImplementationPlan.user_id == user.id).delete()
            db.query(ReadinessAssessment).filter(ReadinessAssessment.user_id == user.id).delete()

            # Delete RBAC and audit data
            db.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
            db.query(UserSession).filter(UserSession.user_id == user.id).delete()
            db.query(UserRole).filter(UserRole.user_id == user.id).delete()

            # Delete the user
            db.delete(user)

        db.commit()

        return {"deleted_users": count, "pattern": email_pattern}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup test users: {str(e)}",
        )


@router.post("/create-test-user")
async def create_test_user(
    email: str, password: str = "TestPassword123!", db: Session = Depends(get_db)
):
    """
    Create a test user for testing purposes.
    Only works in test/development environments.

    Args:
        email: Email for the test user
        password: Password for the test user (default: TestPassword123!)

    Returns:
        dict: Created user info
    """
    if not is_test_environment():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in test environments",
        )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        # Delete existing user
        db.delete(existing_user)
        db.commit()

    # Create new test user
    from uuid import uuid4
    from api.auth.security import get_password_hash

    hashed_password = get_password_hash(password)
    db_user = User(id=uuid4(), email=email, hashed_password=hashed_password, is_active=True)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "id": str(db_user.id),
        "email": db_user.email,
        "is_active": db_user.is_active,
    }


@router.post("/clear-rate-limits")
async def clear_rate_limits():
    """
    Clear all rate limit data.
    Only works in test/development environments.

    Returns:
        dict: Success status
    """
    if not is_test_environment():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in test environments",
        )

    # Import rate limiters
    from api.middleware.rate_limiter import general_limiter, auth_limiter

    # Clear rate limit data
    general_limiter.requests.clear()
    auth_limiter.requests.clear()

    return {"status": "success", "message": "Rate limits cleared"}
