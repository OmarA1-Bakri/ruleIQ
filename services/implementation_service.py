from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database.business_profile import BusinessProfile
from database.compliance_framework import ComplianceFramework
from database.generated_policy import GeneratedPolicy
from database.implementation_plan import ImplementationPlan
from database.user import User

# Assuming the AI function is awaitable or wrapped to be non-blocking
from services.ai.plan_generator import generate_plan_with_ai


async def generate_implementation_plan(
    db: AsyncSession,
    user: User,
    framework_id: UUID,
    policy_id: Optional[UUID] = None,
    control_domain: str = "All Domains",
    timeline_weeks: int = 12,
) -> ImplementationPlan:
    """Generate a detailed implementation plan for compliance controls."""

    # Get business profile
    profile_stmt = select(BusinessProfile).where(BusinessProfile.user_id == user.id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalars().first()
    if not profile:
        raise ValueError("Business profile not found")

    # Get compliance framework
    framework_stmt = select(ComplianceFramework).where(
        ComplianceFramework.id == framework_id,
    )
    framework_result = await db.execute(framework_stmt)
    framework = framework_result.scalars().first()
    if not framework:
        raise ValueError("Compliance framework not found")

    # Get policy if provided
    if policy_id:
        policy_stmt = select(GeneratedPolicy).where(
            GeneratedPolicy.id == policy_id,
            GeneratedPolicy.user_id == user.id,
        )
        policy_result = await db.execute(policy_stmt)
        policy_result.scalars().first()

    # Generate implementation plan using AI
    plan_data = await generate_plan_with_ai(db, profile, framework.id, user.id)

    # Calculate timeline dates
    start_datetime = datetime.now(timezone.utc)
    end_datetime = start_datetime + timedelta(weeks=timeline_weeks)
    start_date = start_datetime.date()
    end_date = end_datetime.date()

    # Create and save the new plan
    default_title = f"Implementation Plan for {framework.display_name}"
    if control_domain != "All Domains":
        default_title = f"{control_domain} Implementation Plan for {framework.display_name}"

    new_plan = ImplementationPlan(
        user_id=user.id,
        business_profile_id=profile.id,
        framework_id=framework.id,
        title=plan_data.get(
            "title",
            default_title,
        ),
        phases=plan_data.get("phases", []),
        planned_start_date=start_date,
        planned_end_date=end_date,
        status="not_started",
    )

    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)

    return new_plan


async def get_implementation_plan(
    db: AsyncSession, user: User, plan_id: UUID
) -> Optional[ImplementationPlan]:
    """Get a specific implementation plan by its ID."""
    stmt = select(ImplementationPlan).where(
        ImplementationPlan.id == plan_id,
        ImplementationPlan.user_id == user.id,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_implementation_plans(db: AsyncSession, user: User) -> List[ImplementationPlan]:
    """List all implementation plans for a user."""
    stmt = select(ImplementationPlan).where(ImplementationPlan.user_id == user.id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_task_status(
    db: AsyncSession, user: User, plan_id: UUID, task_id: str, status: str
) -> Optional[ImplementationPlan]:
    """Update the status of a single task in a plan."""
    plan = await get_implementation_plan(db, user, plan_id)
    if not plan:
        return None

    task_found = False
    for phase in plan.phases:
        for task in phase.get("tasks", []):
            # Check both 'id' and 'task_id' for compatibility
            if task.get("id") == task_id or task.get("task_id") == task_id:
                task["status"] = status
                task_found = True
                break
        if task_found:
            break

    if not task_found:
        raise ValueError("Task not found in plan")

    # Flag the 'phases' attribute as modified so SQLAlchemy knows to update the JSON field.
    flag_modified(plan, "phases")

    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan_dashboard(
    db: AsyncSession, user: User, plan_id: UUID
) -> Optional[Dict[str, Any]]:
    """Get dashboard data for a specific implementation plan."""
    plan = await get_implementation_plan(db, user, plan_id)
    if not plan:
        return None

    total_tasks = sum(len(phase.get("tasks", [])) for phase in plan.phases)
    completed_tasks = 0
    for phase in plan.phases:
        for task in phase.get("tasks", []):
            if task.get("status") == "completed":
                completed_tasks += 1

    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Calculate timeline status
    now = datetime.now(timezone.utc)
    today = now.date()
    created_date = plan.created_at.date() if hasattr(plan.created_at, "date") else plan.created_at
    planned_end_date = (
        plan.planned_end_date.date()
        if plan.planned_end_date and hasattr(plan.planned_end_date, "date")
        else plan.planned_end_date
    )
    days_elapsed = (today - created_date).days
    days_remaining = (planned_end_date - today).days if planned_end_date else 0

    return {
        "plan_title": plan.title,
        "overall_progress": round(completion_percentage, 2),
        "timeline": {
            "days_elapsed": days_elapsed,
            "days_remaining": max(0, days_remaining),
            "on_track": days_remaining >= 0,
        },
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
    }
