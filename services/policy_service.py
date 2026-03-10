"""

Asynchronous service for generating and managing compliance policies using AI.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils.circuit_breaker import CircuitBreakerOpenException, google_breaker
from api.utils.retry import RetryExhaustedError, api_retry
from config.ai_config import generate_compliance_content
from core.exceptions import (
    BusinessLogicException,
    DatabaseException,
    IntegrationException,
    NotFoundException,
)
from database.business_profile import BusinessProfile
from database.compliance_framework import ComplianceFramework
from database.generated_policy import GeneratedPolicy


@api_retry
@google_breaker
async def _generate_policy_with_protection(prompt: str) -> str:
    """Generates policy content with retry and circuit breaker protection."""
    return await generate_compliance_content(prompt)


def build_policy_generation_prompt(
    profile: BusinessProfile,
    framework: ComplianceFramework,
    policy_type: str,
    custom_requirements: List[str],
) -> str:
    """Builds the AI prompt for policy generation."""
    requirements_text = ""
    if custom_requirements:
        requirements_text = f" Include these custom requirements: {', '.join(custom_requirements)}."

    return (
        f"Generate a {policy_type} compliance policy for a {profile.industry} company "
        f"named {profile.company_name} aligned to {framework.name}.{requirements_text}"
    )


async def generate_compliance_policy(
    db: AsyncSession,
    user_id: UUID,
    framework_id: UUID,
    policy_type: str = "comprehensive",
    custom_requirements: Optional[List[str]] = None,
) -> GeneratedPolicy:
    """Generate a comprehensive compliance policy using AI."""
    try:
        profile_res = await db.execute(
            select(BusinessProfile).where(BusinessProfile.user_id == user_id),
        )
        profile = profile_res.scalars().first()
        if not profile:
            raise NotFoundException("Business profile", user_id)

        framework_res = await db.execute(
            select(ComplianceFramework).where(ComplianceFramework.id == framework_id),
        )
        framework = framework_res.scalars().first()
        if not framework:
            raise NotFoundException("Compliance framework", framework_id)

        prompt = build_policy_generation_prompt(
            profile,
            framework,
            policy_type,
            custom_requirements or [],
        )

        policy_content_str = await _generate_policy_with_protection(prompt)

        # Try to parse as JSON, if it fails, treat as plain text
        try:
            policy_data = json.loads(policy_content_str)
        except json.JSONDecodeError:
            # Handle plain text response from AI service
            policy_data = {
                "title": f"{framework.name} Policy for {profile.company_name}",
                "content": policy_content_str,
                "sections": [
                    {"title": "Policy Content", "content": policy_content_str},
                ],
            }

        new_policy = GeneratedPolicy(
            user_id=user_id,
            business_profil=profile.id,
            framework_id=framework.id,
            policy_name=policy_data.get("title", f"{framework.name} Policy"),
            framework_name=framework.name,
            policy_type=policy_type,
            generation_prompt=prompt,
            generation_time_seconds=1.0,  # Placeholder
            policy_content=json.dumps(policy_data),  # Store as JSON string
            sections=policy_data.get("sections", []),
        )
        db.add(new_policy)
        await db.commit()
        await db.refresh(new_policy)
        return new_policy

    except (CircuitBreakerOpenException, RetryExhaustedError) as e:
        raise IntegrationException(
            "Policy generation service is currently unavailable or failing."
        ) from e
    except json.JSONDecodeError as e:
        raise BusinessLogicException("Failed to parse AI response for policy generation.") from e
    except SQLAlchemyError as e:
        await db.rollback()
        raise DatabaseException("Failed to save the generated policy.") from e
    except NotFoundException:
        raise
    except Exception as e:
        await db.rollback()
        raise BusinessLogicException(
            f"An unexpected error occurred during policy generation: {e}"
        ) from e


async def get_policy_by_id(db: AsyncSession, policy_id: UUID, user_id: UUID) -> GeneratedPolicy:
    """Retrieves a policy by its ID, ensuring it belongs to the user."""
    try:
        res = await db.execute(
            select(GeneratedPolicy).where(
                GeneratedPolicy.id == policy_id,
                GeneratedPolicy.user_id == user_id,
            ),
        )
        policy = res.scalars().first()
        if not policy:
            raise NotFoundException("Policy", policy_id)
        return policy
    except SQLAlchemyError as e:
        raise DatabaseException("Failed to retrieve policy.") from e


async def get_user_policies(db: AsyncSession, user_id: UUID) -> List[GeneratedPolicy]:
    """Retrieves all policies for a given user."""
    try:
        result = await db.execute(
            select(GeneratedPolicy).where(GeneratedPolicy.user_id == user_id),
        )
        policies = result.scalars().all()
        return policies
    except SQLAlchemyError as e:
        # Log the error e.g., logging.error(f"Database error fetching policies for user {user_id}: {e}")
        raise DatabaseException(f"Failed to retrieve policies for user {user_id}.") from e


async def regenerate_policy_section(
    db: AsyncSession,
    user_id: UUID,
    policy_id: UUID,
    section_title: str,
    additional_context: str = "",
) -> GeneratedPolicy:
    """Regenerate a specific section of a policy."""
    policy = await get_policy_by_id(db, policy_id, user_id)

    try:
        # Assuming content is a dict with a 'sections' list
        section_content = next(
            (
                s.get("content")
                for s in policy.content.get("sections", [])
                if s.get("title") == section_title
            ),
            "Section not found",
        )

        prompt = (
            f'Regenerate the "{section_title}" section of a compliance policy. '
            f'Current content: "{section_content}". Additional context: "{additional_context}"',
        )
        new_content = await _generate_policy_with_protection(prompt)

        updated = False
        for section in policy.content.get("sections", []):
            if section.get("title") == section_title:
                section["content"] = new_content
                updated = True
                break

        if not updated:
            raise BusinessLogicException(
                f"Section '{section_title}' not found in the policy content.",
            )

        policy.updated_at = datetime.now(timezone.utc)
        # Mark the JSON field as modified for the ORM to detect the change
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(policy, "content")

        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return policy

    except (CircuitBreakerOpenException, RetryExhaustedError) as e:
        raise IntegrationException("Policy regeneration service is currently unavailable.") from e
    except SQLAlchemyError as e:
        await db.rollback()
        raise DatabaseException("Failed to save the regenerated policy section.") from e
    except Exception as e:
        await db.rollback()
        raise BusinessLogicException(f"Failed to regenerate section: {e}") from e
