from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.business_profile import BusinessProfile as BusinessProfileModel
from database.compliance_framework import ComplianceFramework as ComplianceFrameworkModel
from database.evidence_item import EvidenceItem as EvidenceItemModel
from database.generated_policy import GeneratedPolicy as GeneratedPolicyModel
from database.implementation_plan import ImplementationPlan as ImplementationPlanModel
from database.readiness_assessment import ReadinessAssessment as ReadinessAssessmentModel
from database.user import User as UserModel

# Constants
MINUTE_SECONDS = 60


def calculate_policy_score(policies: List[GeneratedPolicyModel]) -> float:
    if not policies:
        return 0.0
    return 75.0


def calculate_implementation_score(plans: List[ImplementationPlanModel]) -> float:
    if not plans:
        return 0.0
    return 60.0


def calculate_evidence_score(evidence: List[EvidenceItemModel]) -> float:
    if not evidence:
        return 0.0
    return 80.0


def analyze_readiness_details(policy_score, implementation_score, evidence_score) -> Dict[str, Any]:
    return {
        "priority_actions": [
            {"action": "Improve policy coverage", "urgency": "high", "impact": "high"}
        ],
        "quick_wins": [{"action": "Upload missing evidence for control X", "effort": "low"}],
        "estimated_readiness_date": datetime.now(timezone.utc) + timedelta(days=90),
    }


async def generate_compliance_report(
    user: UserModel,
    framework: str,
    report_type: str,
    format: str,
    include_evidence: bool,
    include_recommendations: bool,
) -> bytes | Dict[str, Any]:
    """
    Generates a compliance report based on the latest readiness assessment.
    Placeholder implementation.
    """
    if format == "pdf":
        return b"%PDF-1.4...minimal pdf..."
    else:
        return {
            "report_metadata": {
                "user_id": user.id,
                "framework": framework,
                "report_type": report_type,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "summary": "This is a placeholder compliance report.",
            "recommendations": "Implement all the things." if include_recommendations else "N/A",
            "evidence": "Evidence included." if include_evidence else "N/A",
        }


async def get_historical_assessments(
    db: AsyncSession, user: UserModel, business_profile_id: UUID
) -> List[ReadinessAssessmentModel]:
    """Placeholder for retrieving historical readiness assessments."""
    return []


async def generate_readiness_assessment(
    db: AsyncSession, user: UserModel, framework_id: UUID, assessment_type: str = "full"
) -> ReadinessAssessmentModel:
    """Generate a comprehensive compliance readiness assessment asynchronously."""
    profile_stmt = select(BusinessProfileModel).where(BusinessProfileModel.user_id == user.id)
    profile_res = await db.execute(profile_stmt)
    profile = profile_res.scalars().first()
    if not profile:
        raise ValueError("Business profile not found")
    framework_stmt = select(ComplianceFrameworkModel).where(
        ComplianceFrameworkModel.id == framework_id
    )
    framework_res = await db.execute(framework_stmt)
    framework = framework_res.scalars().first()
    if not framework:
        raise ValueError("Compliance framework not found")
    policies_stmt = select(GeneratedPolicyModel).where(
        GeneratedPolicyModel.user_id == user.id, GeneratedPolicyModel.framework_id == framework_id
    )
    policies_res = await db.execute(policies_stmt)
    policies = policies_res.scalars().all()
    impl_plans_stmt = select(ImplementationPlanModel).where(
        ImplementationPlanModel.user_id == user.id,
        ImplementationPlanModel.framework_id == framework_id,
    )
    impl_plans_res = await db.execute(impl_plans_stmt)
    implementation_plans = impl_plans_res.scalars().all()
    evidence_stmt = select(EvidenceItemModel).where(
        EvidenceItemModel.user_id == user.id, EvidenceItemModel.framework_id == framework_id
    )
    evidence_res = await db.execute(evidence_stmt)
    evidence_items = evidence_res.scalars().all()
    policy_score = calculate_policy_score(policies)
    implementation_score = calculate_implementation_score(implementation_plans)
    evidence_score = calculate_evidence_score(evidence_items)
    overall_score = (policy_score + implementation_score + evidence_score) / 3
    analysis = analyze_readiness_details(policy_score, implementation_score, evidence_score)
    new_assessment = ReadinessAssessmentModel(
        user_id=user.id,
        business_profile_id=profile.id,
        framework_id=framework_id,
        overall_score=overall_score,
        score_breakdown={
            "policy": policy_score,
            "implementation": implementation_score,
            "evidence": evidence_score,
        },
        priority_actions=analysis["priority_actions"],
        quick_wins=analysis["quick_wins"],
        estimated_readiness_date=analysis["estimated_readiness_date"],
    )
    db.add(new_assessment)
    await db.commit()
    await db.refresh(new_assessment)
    new_assessment.framework_scores = {
        "policy": policy_score,
        "implementation": implementation_score,
        "evidence": evidence_score,
    }
    if overall_score >= 80:
        risk_level = "Low"
    elif overall_score >= MINUTE_SECONDS:
        risk_level = "Medium"
    elif overall_score >= 40:
        risk_level = "High"
    else:
        risk_level = "Critical"
    new_assessment.risk_level = risk_level
    new_assessment.recommendations = [
        "Complete missing policy documentation",
        "Implement additional security controls",
        "Collect required evidence items",
    ]
    return new_assessment


async def get_readiness_dashboard(db: AsyncSession, user: UserModel) -> Dict[str, Any]:
    """Get a high-level readiness dashboard for the user."""
    frameworks_stmt = select(ComplianceFrameworkModel)
    frameworks_res = await db.execute(frameworks_stmt)
    all_frameworks = frameworks_res.scalars().all()
    framework_data = []
    for fw in all_frameworks:
        assessment_stmt = (
            select(ReadinessAssessmentModel)
            .where(
                ReadinessAssessmentModel.user_id == user.id,
                ReadinessAssessmentModel.framework_id == fw.id,
            )
            .order_by(ReadinessAssessmentModel.created_at.desc())
        )
        assessment_res = await db.execute(assessment_stmt)
        latest_assessment = assessment_res.scalars().first()
        if latest_assessment:
            framework_data.append({"framework": fw, "assessment": latest_assessment})
    if not framework_data:
        return {"message": "No readiness assessments found."}
    total_frameworks = len(framework_data)
    avg_score = (
        sum(f["assessment"].overall_score for f in framework_data) / total_frameworks
        if total_frameworks > 0
        else 0
    )
    all_priority_actions = []
    for fw_data in framework_data:
        for action in fw_data["assessment"].priority_actions[:3]:
            all_priority_actions.append(
                {
                    "framework": fw_data["framework"].display_name,
                    "action": action.get("action", "N/A"),
                    "urgency": action.get("urgency", "N/A"),
                    "impact": action.get("impact", "N/A"),
                }
            )
    return {
        "total_frameworks": total_frameworks,
        "average_score": round(avg_score, 2),
        "framework_scores": [
            {
                "name": fw["framework"].display_name,
                "score": fw["assessment"].overall_score,
                "trend": fw["assessment"].score_trend,
            }
            for fw in framework_data
        ],
        "priority_actions": all_priority_actions[:10],
    }
