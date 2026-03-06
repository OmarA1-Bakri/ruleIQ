"""

Real implementation of compliance nodes that connects to actual services.
This replaces the mocked version with actual database operations.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.business_profile import BusinessProfile as BusinessProfileModel
from database.compliance_framework import (
    ComplianceFramework as ComplianceFrameworkModel,
)
from database.user import User as UserModel
from services.readiness_service import generate_readiness_assessment
from database.db_setup import get_async_db
from langgraph_agent.graph.unified_state import UnifiedComplianceState
from config.langsmith_config import with_langsmith_tracing

logger = logging.getLogger(__name__)


async def get_default_framework(db: AsyncSession) -> Optional[ComplianceFrameworkModel]:
    """Get the default compliance framework (usually the first one)."""
    result = await db.execute(select(ComplianceFrameworkModel).limit(1))
    return result.scalars().first()


async def get_user_for_profile(
    db: AsyncSession, profile: BusinessProfileModel
) -> Optional[UserModel]:
    """Get the user associated with a business profile."""
    result = await db.execute(select(UserModel).where(UserModel.id == profile.user_id))
    return result.scalars().first()


async def update_compliance_for_profile(
    db: AsyncSession, profile: BusinessProfileModel
) -> Dict[str, Any]:
    """
    Update compliance score for a single business profile.
    This handles the mismatch between how workers call the function
    and what the actual service expects.
    """
    try:
        # Get the user for this profile
        user = await get_user_for_profile(db, profile)
        if not user:
            logger.error(f"No user found for profile {profile.id}")
            return {
                "profile_id": str(profile.id),
                "error": "No user found",
                "overall_score": 0,
            }

        # Get a default framework (in real implementation, this might be configurable)
        framework = await get_default_framework(db)
        if not framework:
            logger.error(f"No compliance framework found for profile {profile.id}")
            return {
                "profile_id": str(profile.id),
                "error": "No framework found",
                "overall_score": 0,
            }

        # Now call the actual readiness assessment with proper parameters
        assessment = await generate_readiness_assessment(
            db=db, user=user, framework_id=framework.id, assessment_type="full"
        )

        # Extract the relevant data
        return {
            "profile_id": str(profile.id),
            "overall_score": assessment.overall_score,
            "framework_scores": getattr(assessment, "framework_scores", {}),
            "risk_level": getattr(assessment, "risk_level", "Unknown"),
            "priority_actions": assessment.priority_actions,
            "quick_wins": assessment.quick_wins,
            "estimated_readiness_date": assessment.estimated_readiness_date,
        }

    except Exception as e:
        logger.error(f"Failed to update compliance for profile {profile.id}: {e}")
        return {"profile_id": str(profile.id), "error": str(e), "overall_score": 0}


@with_langsmith_tracing("compliance.batch_update")
async def batch_compliance_update_node(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Node that updates compliance scores for ALL business profiles in the database.
    This is the real implementation that replaces the Celery task.
    """
    logger.info("Starting batch compliance update for all profiles")

    updated_profiles = []
    alerts = []
    errors = []

    try:
        async for db in get_async_db():
            # Get all business profiles
            profiles_res = await db.execute(select(BusinessProfileModel))
            profiles = profiles_res.scalars().all()

            total_profiles = len(profiles)
            logger.info(f"Found {total_profiles} profiles to update")

            # Update compliance for each profile
            for profile in profiles:
                result = await update_compliance_for_profile(db, profile)
                updated_profiles.append(result)

                # Check if we need to create an alert
                score = result.get("overall_score", 100)
                if score < 70 and "error" not in result:
                    alert = {
                        "profile_id": result["profile_id"],
                        "score": score,
                        "message": "Compliance score is below threshold",
                        "risk_level": result.get("risk_level", "Unknown"),
                    }
                    alerts.append(alert)
                    logger.warning(f"Compliance alert for profile {profile.id}: Score is {score}")

                if "error" in result:
                    errors.append(result)

            # Update state with results
            state["compliance_data"] = {
                "batch_update_results": {
                    "total_profiles": total_profiles,
                    "updated_count": len(updated_profiles) - len(errors),
                    "error_count": len(errors),
                    "alerts": alerts,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "profiles": updated_profiles,
            }

            if alerts:
                state["metadata"]["alerts_generated"] = True
                state["metadata"]["alert_count"] = len(alerts)

            # Add to history
            state["history"].append(
                {
                    "action": "batch_compliance_update",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": {
                        "profiles_updated": len(updated_profiles) - len(errors),
                        "errors": len(errors),
                        "alerts": len(alerts),
                    },
                }
            )

            logger.info(
                f"Batch compliance update completed: {len(updated_profiles) - len(errors)} successful, {len(errors)} errors"
            )

    except Exception as e:
        logger.error(f"Failed to perform batch compliance update: {e}")
        state["errors"].append(
            {
                "type": "BatchUpdateError",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["error_count"] += 1

    return state


@with_langsmith_tracing("compliance.single_check")
async def single_compliance_check_node(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Node that checks compliance for a single company/profile.
    This is used for on-demand checks.
    """
    company_id = state.get("company_id") or state.get("metadata", {}).get("company_id")

    if not company_id:
        logger.error("No company_id provided for compliance check")
        state["errors"].append(
            {
                "type": "ValidationError",
                "message": "company_id required for compliance check",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    logger.info(f"Starting compliance check for company {company_id}")

    try:
        async for db in get_async_db():
            # Get the business profile for this company
            profile_res = await db.execute(
                select(BusinessProfileModel).where(BusinessProfileModel.company_id == company_id)
            )
            profile = profile_res.scalars().first()

            if not profile:
                logger.error(f"No business profile found for company {company_id}")
                state["errors"].append(
                    {
                        "type": "NotFoundError",
                        "message": f"No business profile found for company {company_id}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                state["error_count"] += 1
                return state

            # Update compliance for this profile
            result = await update_compliance_for_profile(db, profile)

            if "error" in result:
                state["errors"].append(
                    {
                        "type": "ComplianceCheckError",
                        "message": result["error"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                state["error_count"] += 1
            else:
                state["compliance_data"] = {
                    "check_results": result,
                    "regulation": state.get("metadata", {}).get("regulation", "Unknown"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Check if we need to trigger notifications
                if result["overall_score"] < 70:
                    state["metadata"]["notify_required"] = True
                    state["metadata"]["violation_count"] = 1

                # Add to history
                state["history"].append(
                    {
                        "action": "compliance_check",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "details": {
                            "company_id": company_id,
                            "score": result["overall_score"],
                            "risk_level": result.get("risk_level", "Unknown"),
                        },
                    }
                )

            logger.info(f"Compliance check completed for company {company_id}")

    except Exception as e:
        logger.error(f"Failed to check compliance for company {company_id}: {e}")
        state["errors"].append(
            {
                "type": "ComplianceCheckError",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["error_count"] += 1

    return state


@with_langsmith_tracing("compliance.monitoring")
async def compliance_monitoring_node(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Node that monitors compliance scores and generates alerts.
    This replaces the monitor_compliance_scores Celery task.
    """
    logger.info("Starting compliance monitoring")

    alerts = []
    low_score_profiles = []

    try:
        async for db in get_async_db():
            # Get all business profiles
            profiles_res = await db.execute(select(BusinessProfileModel))
            profiles = profiles_res.scalars().all()

            for profile in profiles:
                # Get the latest compliance score
                result = await update_compliance_for_profile(db, profile)

                if "error" not in result:
                    score = result.get("overall_score", 100)
                    if score < 70:
                        alert = {
                            "profile_id": result["profile_id"],
                            "score": score,
                            "risk_level": result.get("risk_level", "Unknown"),
                            "priority_actions": result.get("priority_actions", []),
                            "message": f"Compliance score ({score}%) is below threshold (70%)",
                        }
                        alerts.append(alert)
                        low_score_profiles.append(result)
                        logger.warning(
                            f"Compliance alert for profile {profile.id}: Score is {score}"
                        )

            # Update state with monitoring results
            state["compliance_data"]["monitoring_results"] = {
                "total_profiles": len(profiles),
                "alerts_generated": len(alerts),
                "low_score_profiles": low_score_profiles,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if alerts:
                state["metadata"]["alerts"] = alerts
                state["metadata"]["alert_count"] = len(alerts)
                state["metadata"]["notify_required"] = True

            # Add to history
            state["history"].append(
                {
                    "action": "compliance_monitoring",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": {
                        "profiles_monitored": len(profiles),
                        "alerts_generated": len(alerts),
                    },
                }
            )

            logger.info(
                f"Compliance monitoring completed: {len(profiles)} profiles monitored, {len(alerts)} alerts generated"
            )

    except Exception as e:
        logger.error(f"Failed to monitor compliance: {e}")
        state["errors"].append(
            {
                "type": "MonitoringError",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["error_count"] += 1

    return state


# Export the nodes for use in the workflow
__all__ = [
    "batch_compliance_update_node",
    "single_compliance_check_node",
    "compliance_monitoring_node",
]
