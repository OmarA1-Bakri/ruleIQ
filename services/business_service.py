"""

Asynchronous service for managing business profiles and assessments.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseException, NotFoundException
from database.business_profile import BusinessProfile
from database.user import User


async def create_or_update_business_profile(
    db: AsyncSession, user: User, profile_data: Dict[str, Any]
) -> BusinessProfile:
    """Create or update a business profile for the authenticated user."""
    try:
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == user.id)
        result = await db.execute(stmt)
        existing_profile = result.scalars().first()

        if existing_profile:
            # Update existing profile
            for key, value in profile_data.items():
                if hasattr(existing_profile, key):
                    setattr(existing_profile, key, value)
            existing_profile.updated_at = datetime.now(timezone.utc)
            profile = existing_profile
        else:
            # Create new profile
            profile = BusinessProfile(user_id=user.id, **profile_data)
            db.add(profile)

        await db.commit()
        await db.refresh(profile)
        return profile
    except SQLAlchemyError as e:
        await db.rollback()
        raise DatabaseException("Failed to create or update business profile.") from e


async def get_business_profile(db: AsyncSession, user: User) -> Optional[BusinessProfile]:
    """Get the business profile for the authenticated user."""
    try:
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == user.id)
        result = await db.execute(stmt)
        return result.scalars().first()
    except SQLAlchemyError as e:
        raise DatabaseException("Failed to retrieve business profile.") from e


async def update_assessment_status(
    db: AsyncSession, user: User, assessment_completed: bool, assessment_data: Dict
) -> BusinessProfile:
    """Update the assessment completion status and data."""
    profile = await get_business_profile(db, user)
    if not profile:
        raise NotFoundException("Business profile", user.id)

    try:
        profile.assessment_completed = assessment_completed
        profile.assessment_data = assessment_data
        profile.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(profile)

        return profile
    except SQLAlchemyError as e:
        await db.rollback()
        raise DatabaseException("Failed to update assessment status.") from e


def get_supported_industries() -> List[str]:
    """Get list of supported industries for business profiles."""
    return [
        "Financial Services",
        "Healthcare",
        "Technology",
        "Manufacturing",
        "Retail",
        "Education",
        "Government",
        "Non-profit",
        "Professional Services",
        "Real Estate",
        "Transportation",
        "Energy",
        "Media",
        "Hospitality",
        "Other",
    ]


def get_cloud_provider_options() -> List[str]:
    """Get list of supported cloud providers."""
    return [
        "AWS (Amazon Web Services)",
        "Microsoft Azure",
        "Google Cloud Platform",
        "IBM Cloud",
        "Oracle Cloud",
        "DigitalOcean",
        "Linode",
        "Vultr",
        "Other",
    ]


def get_saas_tool_options() -> List[str]:
    """Get list of common SaaS tools for integration guidance."""
    return [
        "Microsoft 365",
        "Google Workspace",
        "Salesforce",
        "Slack",
        "Zoom",
        "Atlassian (Jira/Confluence)",
        "HubSpot",
        "Zendesk",
        "DocuSign",
        "Dropbox",
        "Box",
        "ServiceNow",
        "Other",
    ]
