"""
import logging


logger = logging.getLogger(__name__)
# Constants
DEFAULT_RETRIES = 5


Asynchronous report generation service for ComplianceGPT.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from config.logging_config import get_logger
from core.exceptions import BusinessLogicException, DatabaseException, NotFoundException
from database.business_profile import BusinessProfile
from database.compliance_framework import ComplianceFramework
from database.evidence_item import EvidenceItem
from database.generated_policy import GeneratedPolicy

logger = get_logger(__name__)


class ReportGenerator:
    """Generate compliance reports asynchronously."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_report(
        self,
        user_id: UUID,
        business_profile_id: UUID,
        report_type: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a report based on type and parameters."""
        try:
            profile_res = await self.db.execute(
                select(BusinessProfile).where(
                    and_(
                        BusinessProfile.id == business_profile_id,
                        BusinessProfile.user_id == user_id,
                    )
                )
            )
            profile = profile_res.scalars().first()
            if not profile:
                raise NotFoundException(
                    f"Business profile with ID {business_profile_id} not found for this user."
                )
            report_builders = {
                "executive_summary": self._generate_executive_summary,
                "compliance_status": self._generate_compliance_status,
                "gap_analysis": self._generate_gap_analysis,
                "evidence_report": self._generate_evidence_report,
                "audit_readiness": self._generate_audit_readiness,
            }
            builder = report_builders.get(report_type)
            if not builder:
                raise BusinessLogicException(f"Report type '{report_type}' is not supported.")
            logger.info(
                "Generating report '%s' for business profile %s"
                % (report_type, business_profile_id)
            )
            return await builder(profile, parameters or {})
        except SQLAlchemyError as e:
            logger.error(
                "Database error during report generation for profile %s: %s"
                % (business_profile_id, e),
                exc_info=True,
            )
            raise DatabaseException("A database error occurred while generating the report.") from e
        except BusinessLogicException as e:
            logger.warning(
                "Business logic error during report generation for profile %s: %s"
                % (business_profile_id, e)
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during report generation for profile %s: %s"
                % (business_profile_id, e),
                exc_info=True,
            )
            raise BusinessLogicException(
                "An unexpected error occurred during report generation."
            ) from e

    async def _generate_executive_summary(
        self, profile: BusinessProfile, params: Dict
    ) -> Dict[str, Any]:
        """Generates a high-level executive summary."""
        key_metrics = await self._calculate_key_metrics(profile.id)
        recommendations = await self._generate_recommendations(profile.id)
        return {
            "report_title": "Executive Compliance Summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "business_profile": profile.to_dict(),
            "key_metrics": key_metrics,
            "top_recommendations": recommendations[:3],
        }

    async def _generate_compliance_status(
        self, profile: BusinessProfile, params: Dict
    ) -> Dict[str, Any]:
        """Generates a detailed compliance status report."""
        metrics = await self._calculate_key_metrics(profile.id)
        return {
            "report_title": "Compliance Status Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
        }

    async def _generate_gap_analysis(
        self, profile: BusinessProfile, params: Dict
    ) -> Dict[str, Any]:
        """Generates a gap analysis report showing missing evidence or policies."""
        framework_id = params.get("framework_id")
        if not framework_id:
            raise BusinessLogicException("Framework ID is required for gap analysis report.")
        all_controls = await self._get_all_controls(UUID(framework_id))
        linked_evidence = await self._get_linked_evidence(profile.id)
        gaps = []
        linked_control_ids = {e.control_id for e in linked_evidence if e.control_id}
        for control in all_controls:
            if control.get("id") not in linked_control_ids:
                gaps.append(
                    {
                        "control_id": control.get("id"),
                        "control_name": control.get("name"),
                        "gap_type": "Missing Evidence",
                        "description": "No evidence has been linked to this control.",
                    }
                )
        return {
            "report_title": "Gap Analysis Report",
            "framework_id": framework_id,
            "total_gaps": len(gaps),
            "gaps": gaps,
        }

    async def _get_all_controls(self, framework_id: UUID) -> List[Dict]:
        """Helper to get all controls for a framework."""
        try:
            framework_res = await self.db.execute(
                select(ComplianceFramework).where(ComplianceFramework.id == framework_id)
            )
            framework = framework_res.scalars().first()
            if not framework or not framework.controls:
                return []
            return framework.controls
        except SQLAlchemyError as e:
            logger.error(
                "Failed to get controls for framework %s: %s" % (framework_id, e), exc_info=True
            )
            raise DatabaseException("Failed to retrieve framework controls.") from e

    async def _get_linked_evidence(self, profile_id: UUID) -> List[EvidenceItem]:
        """Helper to get all evidence linked to a business profile."""
        try:
            evidence_res = await self.db.execute(
                select(EvidenceItem).where(EvidenceItem.business_profile_id == profile_id)
            )
            return evidence_res.scalars().all()
        except SQLAlchemyError as e:
            logger.error(
                "Failed to get evidence for profile %s: %s" % (profile_id, e), exc_info=True
            )
            raise DatabaseException("Failed to retrieve linked evidence.") from e

    async def _generate_evidence_report(
        self, profile: BusinessProfile, params: Dict
    ) -> Dict[str, Any]:
        """Generates a report detailing all collected evidence."""
        evidence_items = await self._get_linked_evidence(profile.id)
        return {
            "report_title": "Collected Evidence Report",
            "total_items": len(evidence_items),
            "evidence": [item.to_dict() for item in evidence_items],
        }

    async def _generate_audit_readiness(
        self, profile: BusinessProfile, params: Dict
    ) -> Dict[str, Any]:
        """Generates an audit readiness report with scores and recommendations."""
        metrics = await self._calculate_key_metrics(profile.id)
        recommendations = await self._generate_recommendations(profile.id)
        return {
            "report_title": "Audit Readiness Report",
            "readiness_score": metrics.get("overall_compliance_score", 0),
            "summary": "The organization's readiness for an audit is assessed based on policy coverage and evidence completeness.",
            "recommendations": recommendations,
        }

    async def _calculate_key_metrics(self, profile_id: UUID) -> Dict[str, Any]:
        """Calculates key compliance metrics for a business profile."""
        try:
            total_evidence_res = await self.db.execute(
                select(func.count(EvidenceItem.id)).where(
                    EvidenceItem.business_profile_id == profile_id
                )
            )
            active_evidence_res = await self.db.execute(
                select(func.count(EvidenceItem.id)).where(
                    and_(
                        EvidenceItem.business_profile_id == profile_id,
                        EvidenceItem.status == "active",
                    )
                )
            )
            policies_res = await self.db.execute(
                select(func.count(GeneratedPolicy.id)).where(
                    GeneratedPolicy.business_profil == profile_id
                )
            )
            total_evidence = total_evidence_res.scalar_one()
            active_evidence = active_evidence_res.scalar_one()
            total_policies = policies_res.scalar_one()
            evidence_score = active_evidence / total_evidence * 100 if total_evidence > 0 else 0
            policy_score = 100 if total_policies > DEFAULT_RETRIES else total_policies / 5 * 100
            overall_score = (evidence_score + policy_score) / 2
            return {
                "overall_compliance_score": round(overall_score, 2),
                "evidence_completeness_score": round(evidence_score, 2),
                "policy_coverage_score": round(policy_score, 2),
                "total_evidence_items": total_evidence,
                "total_policies": total_policies,
            }
        except SQLAlchemyError as e:
            logger.error(
                "Failed to calculate key metrics for profile %s: %s" % (profile_id, e),
                exc_info=True,
            )
            raise DatabaseException("Failed to calculate key metrics.") from e

    async def _generate_recommendations(self, profile_id: UUID) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on compliance data."""
        try:
            recommendations = []
            metrics = await self._calculate_key_metrics(profile_id)
            if metrics["policy_coverage_score"] < 80:
                recommendations.append(
                    {
                        "area": "Policies",
                        "recommendation": "Generate additional policies to cover all framework controls.",
                        "priority": "High",
                    }
                )
            if metrics["evidence_completeness_score"] < 90:
                recommendations.append(
                    {
                        "area": "Evidence",
                        "recommendation": "Review and refresh stale evidence items to ensure all controls are covered.",
                        "priority": "High",
                    }
                )
            if not recommendations:
                recommendations.append(
                    {
                        "area": "General",
                        "recommendation": "Compliance posture is strong. Schedule a quarterly compliance review to maintain status.",
                        "priority": "Medium",
                    }
                )
            return recommendations
        except (DatabaseException, BusinessLogicException) as e:
            logger.warning(
                "Could not generate recommendations for profile %s due to upstream error: %s"
                % (profile_id, e)
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error generating recommendations for profile %s: %s" % (profile_id, e),
                exc_info=True,
            )
            raise BusinessLogicException(
                "Failed to generate recommendations due to an unexpected error."
            ) from e
