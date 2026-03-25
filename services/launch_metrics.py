from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.business_profile import BusinessProfile
from database.compliance_framework import ComplianceFramework
from database.evidence_item import EvidenceItem
from database.generated_policy import GeneratedPolicy
from database.implementation_plan import ImplementationPlan
from database.readiness_assessment import ReadinessAssessment


COMPLETED_EVIDENCE_STATUSES = {"approved", "active", "collected", "completed"}
PARTIAL_EVIDENCE_STATUSES = {"pending", "pending_review", "needs_review", "in_review"}
ACTIVE_POLICY_STATUSES = {"approved", "active"}
ACTIVE_PLAN_STATUSES = {"in_progress", "active"}


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("_", "-")
        .replace(".", "")
    )


async def get_owned_business_profile(
    db: AsyncSession, user_id: UUID, business_profile_id: Optional[UUID | str] = None
) -> Optional[BusinessProfile]:
    statement = select(BusinessProfile).where(BusinessProfile.user_id == user_id)
    if business_profile_id:
        statement = statement.where(BusinessProfile.id == UUID(str(business_profile_id)))

    result = await db.execute(statement.order_by(BusinessProfile.created_at.asc()))
    return result.scalars().first()


async def get_profile_frameworks(
    db: AsyncSession, profile: BusinessProfile
) -> List[ComplianceFramework]:
    result = await db.execute(
        select(ComplianceFramework)
        .where(ComplianceFramework.is_active.is_(True))
        .order_by(ComplianceFramework.display_name.asc(), ComplianceFramework.name.asc())
    )
    frameworks = result.scalars().all()

    selected_names = {
        str(name).strip().lower()
        for name in (_as_list(profile.existing_frameworks) + _as_list(profile.planned_frameworks))
        if str(name).strip()
    }
    if not selected_names:
        return frameworks

    selected_frameworks = [
        framework
        for framework in frameworks
        if framework.name.lower() in selected_names or framework.display_name.lower() in selected_names
    ]
    return selected_frameworks or frameworks


async def load_profile_framework_state(
    db: AsyncSession,
    user_id: UUID,
    profile: BusinessProfile,
    frameworks: Sequence[ComplianceFramework],
) -> Dict[str, Dict[UUID, List[Any] | Any]]:
    framework_ids = [framework.id for framework in frameworks]
    empty_list_map: Dict[UUID, List[Any]] = {framework.id: [] for framework in frameworks}
    empty_item_map: Dict[UUID, Any] = {framework.id: None for framework in frameworks}

    if not framework_ids:
        return {
            "evidence": empty_list_map,
            "policies": empty_list_map,
            "plans": empty_list_map,
            "assessments": empty_item_map,
        }

    evidence_result = await db.execute(
        select(EvidenceItem).where(
            EvidenceItem.user_id == user_id,
            EvidenceItem.business_profile_id == profile.id,
            EvidenceItem.framework_id.in_(framework_ids),
        )
    )
    evidence_map: Dict[UUID, List[EvidenceItem]] = defaultdict(list)
    for item in evidence_result.scalars().all():
        evidence_map[item.framework_id].append(item)

    policy_result = await db.execute(
        select(GeneratedPolicy).where(
            GeneratedPolicy.user_id == user_id,
            GeneratedPolicy.business_profil == profile.id,
            GeneratedPolicy.framework_id.in_(framework_ids),
        )
    )
    policy_map: Dict[UUID, List[GeneratedPolicy]] = defaultdict(list)
    for item in policy_result.scalars().all():
        policy_map[item.framework_id].append(item)

    plan_result = await db.execute(
        select(ImplementationPlan).where(
            ImplementationPlan.user_id == user_id,
            ImplementationPlan.business_profile_id == profile.id,
            ImplementationPlan.framework_id.in_(framework_ids),
        )
    )
    plan_map: Dict[UUID, List[ImplementationPlan]] = defaultdict(list)
    for item in plan_result.scalars().all():
        plan_map[item.framework_id].append(item)

    assessment_result = await db.execute(
        select(ReadinessAssessment)
        .where(
            ReadinessAssessment.user_id == user_id,
            ReadinessAssessment.business_profile_id == profile.id,
            ReadinessAssessment.framework_id.in_(framework_ids),
        )
        .order_by(ReadinessAssessment.created_at.desc())
    )
    assessment_map: Dict[UUID, ReadinessAssessment] = {}
    for item in assessment_result.scalars().all():
        assessment_map.setdefault(item.framework_id, item)

    return {
        "evidence": {**empty_list_map, **evidence_map},
        "policies": {**empty_list_map, **policy_map},
        "plans": {**empty_list_map, **plan_map},
        "assessments": {**empty_item_map, **assessment_map},
    }


def build_framework_controls(framework: ComplianceFramework) -> List[Dict[str, Any]]:
    domains = _as_list(framework.control_domains)
    requirements = _as_list(framework.key_requirement)
    evidence_types = _as_list(framework.evidence_types) or [
        "policy_document",
        "evidence_record",
        "configuration_export",
    ]

    controls: List[Dict[str, Any]] = []
    source_items = requirements or domains or [framework.display_name]
    for index, item in enumerate(source_items, start=1):
        category = domains[(index - 1) % len(domains)] if domains else framework.category
        control_id = f"{_slug(framework.name)}-ctrl-{index:02d}"
        title = str(item)
        controls.append(
            {
                "control_id": control_id,
                "control_name": title,
                "description": f"{framework.display_name} requirement for {title}",
                "category": category,
                "priority": "high" if index <= max(1, len(source_items) // 3) else "medium",
                "evidence_required": evidence_types[:3],
            }
        )

    return controls


def calculate_plan_progress(plans: Iterable[ImplementationPlan]) -> float:
    plans = list(plans)
    if not plans:
        return 0.0

    progress_values: List[float] = []
    for plan in plans:
        phases = _as_list(plan.phases)
        phase_progress: List[float] = []
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            if isinstance(phase.get("progress"), (int, float)):
                phase_progress.append(float(phase["progress"]))
                continue
            tasks = _as_list(phase.get("tasks"))
            if tasks:
                completed = sum(
                    1
                    for task in tasks
                    if isinstance(task, dict) and str(task.get("status", "")).lower() == "completed"
                )
                phase_progress.append(round(completed / max(len(tasks), 1) * 100, 2))

        if phase_progress:
            progress_values.append(sum(phase_progress) / len(phase_progress))
            continue

        status = str(plan.status or "").lower()
        if status == "completed":
            progress_values.append(100.0)
        elif status in ACTIVE_PLAN_STATUSES:
            progress_values.append(50.0)
        else:
            progress_values.append(10.0)

    return round(sum(progress_values) / len(progress_values), 2)


def _map_status(score: float) -> str:
    if score >= 85:
        return "compliant"
    if score >= 60:
        return "partial"
    if score > 0:
        return "non_compliant"
    return "not_assessed"


def _map_maturity(score: float) -> str:
    if score >= 85:
        return "optimized"
    if score >= 70:
        return "managed"
    if score >= 55:
        return "defined"
    if score >= 35:
        return "developing"
    return "initial"


def calculate_framework_status(
    framework: ComplianceFramework,
    evidence_items: Sequence[EvidenceItem],
    policies: Sequence[GeneratedPolicy],
    plans: Sequence[ImplementationPlan],
    assessment: Optional[ReadinessAssessment] = None,
) -> Dict[str, Any]:
    controls = build_framework_controls(framework)
    total_controls = max(len(controls), 1)

    approved_evidence = sum(1 for item in evidence_items if item.status in COMPLETED_EVIDENCE_STATUSES)
    partial_evidence = sum(1 for item in evidence_items if item.status in PARTIAL_EVIDENCE_STATUSES)
    evidence_ratio = min(approved_evidence / total_controls, 1.0)
    partial_ratio = min(partial_evidence / total_controls, 1.0)

    active_policies = sum(1 for item in policies if str(item.status).lower() in ACTIVE_POLICY_STATUSES)
    policy_target = max(1, min(total_controls, max(len(_as_list(framework.control_domains)), 3)))
    policy_ratio = min(active_policies / policy_target, 1.0)

    plan_progress = calculate_plan_progress(plans)
    plan_ratio = min(plan_progress / 100, 1.0)

    base_score = (evidence_ratio * 0.45 + policy_ratio * 0.30 + plan_ratio * 0.25) * 100
    overall_score = round(
        assessment.overall_score if assessment and assessment.overall_score else base_score,
        2,
    )

    compliant_controls = min(total_controls, round(total_controls * evidence_ratio))
    partial_controls = min(
        max(total_controls - compliant_controls, 0),
        round(total_controls * partial_ratio),
    )
    non_compliant_controls = max(total_controls - compliant_controls - partial_controls, 0)

    domain_names = _as_list(framework.control_domains) or [framework.category]
    by_domain = []
    for domain in domain_names:
        domain_controls = max(1, round(total_controls / len(domain_names)))
        domain_compliant = min(domain_controls, round(domain_controls * evidence_ratio))
        domain_score = round(
            min(
                100.0,
                (evidence_ratio * 0.5 + policy_ratio * 0.25 + plan_ratio * 0.25) * 100,
            ),
            2,
        )
        by_domain.append(
            {
                "domain": domain,
                "compliance_percentage": domain_score,
                "controls_compliant": domain_compliant,
                "controls_total": domain_controls,
                "critical_findings": 1 if domain_score < 50 else 0,
            }
        )

    recommendations: List[str] = []
    if evidence_ratio < 0.7:
        recommendations.append("Collect and approve additional framework evidence.")
    if policy_ratio < 0.7:
        recommendations.append("Expand policy coverage for the framework control domains.")
    if plan_ratio < 0.7:
        recommendations.append("Advance implementation plan tasks to reduce delivery risk.")
    if not recommendations:
        recommendations.append("Maintain the current control, policy, and evidence cadence.")

    strengths: List[str] = []
    weaknesses: List[str] = []
    if evidence_ratio >= 0.7:
        strengths.append("Evidence coverage is tracking well.")
    else:
        weaknesses.append("Evidence coverage is below launch target.")
    if policy_ratio >= 0.7:
        strengths.append("Policy coverage supports the framework baseline.")
    else:
        weaknesses.append("Policy coverage is incomplete for this framework.")
    if plan_ratio >= 0.7:
        strengths.append("Implementation execution is progressing consistently.")
    else:
        weaknesses.append("Implementation execution is lagging behind roadmap expectations.")

    return {
        "framework_id": str(framework.id),
        "framework": framework.display_name,
        "framework_name": framework.display_name,
        "overall_compliance_percentage": overall_score,
        "overall_compliance": overall_score,
        "status": _map_status(overall_score),
        "by_domain": by_domain,
        "controls_status": {
            "compliant": compliant_controls,
            "partial": partial_controls,
            "non_compliant": non_compliant_controls,
            "not_assessed": max(total_controls - compliant_controls - partial_controls, 0),
        },
        "risk_summary": {
            "high_risk_items": non_compliant_controls,
            "medium_risk_items": partial_controls,
            "low_risk_items": compliant_controls,
            "remediation_in_progress": round(total_controls * plan_ratio),
        },
        "last_assessment_date": assessment.created_at.isoformat() if assessment else None,
        "next_review_date": (
            (assessment.created_at + timedelta(days=90)).isoformat() if assessment else None
        ),
        "maturity_level": _map_maturity(overall_score),
        "maturity_score": overall_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "control_count": total_controls,
        "estimated_effort": f"{max(1, framework.implementation_ // 4)}-{max(2, framework.implementation_ // 2)} months",
        "key_features": _as_list(framework.key_requirement)[:5],
        "industry_alignment": _as_list(framework.applicable_indu),
    }


def build_recommended_tasks(
    profile_id: UUID | str, framework_statuses: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for index, status in enumerate(framework_statuses, start=1):
        if status["overall_compliance_percentage"] >= 75:
            continue
        framework_name = status["framework"]
        tasks.append(
            {
                "id": f"task-{_slug(framework_name)}-{index}",
                "title": f"Close priority gaps for {framework_name}",
                "description": "Resolve the highest-value evidence, policy, and implementation gaps.",
                "control_id": f"{_slug(framework_name)}-priority",
                "framework": framework_name,
                "framework_id": status["framework_id"],
                "business_profile_id": str(profile_id),
                "priority": "high" if status["overall_compliance_percentage"] < 50 else "medium",
                "status": "pending",
                "effort_hours": 8 if status["overall_compliance_percentage"] < 50 else 4,
                "dependencies": [],
                "evidence_required": ["policy_document", "evidence_record"],
            }
        )
    return tasks


def build_recommended_risks(
    profile_id: UUID | str, framework_statuses: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []
    for index, status in enumerate(framework_statuses, start=1):
        risk_summary = status["risk_summary"]
        if risk_summary["high_risk_items"] <= 0:
            continue
        framework_name = status["framework"]
        risks.append(
            {
                "id": f"risk-{_slug(framework_name)}-{index}",
                "title": f"{framework_name} control exposure",
                "description": "Open control gaps could delay audit readiness or certification milestones.",
                "severity": "high" if risk_summary["high_risk_items"] > 2 else "medium",
                "likelihood": "likely" if status["overall_compliance_percentage"] < 60 else "possible",
                "impact": "Launch-critical framework controls remain partially implemented.",
                "affected_controls": [status["framework_id"]],
                "status": "identified",
                "framework": framework_name,
                "framework_id": status["framework_id"],
                "business_profile_id": str(profile_id),
            }
        )
    return risks


def build_trend_projection(assessments: Sequence[ReadinessAssessment]) -> Dict[str, Any]:
    ordered = sorted(assessments, key=lambda item: item.created_at)
    if len(ordered) < 2:
        latest_date = datetime.now(timezone.utc) + timedelta(days=90)
        return {
            "estimated_compliance_date": latest_date.date().isoformat(),
            "required_improvement_rate": 1.0,
            "risk_areas": ["Evidence coverage", "Policy coverage", "Implementation progress"],
        }

    delta_score = ordered[-1].overall_score - ordered[0].overall_score
    delta_days = max((ordered[-1].created_at - ordered[0].created_at).days, 1)
    daily_rate = delta_score / delta_days
    latest_score = ordered[-1].overall_score
    days_to_target = 0 if latest_score >= 85 else int(max((85 - latest_score) / max(daily_rate, 0.1), 1))
    target_date = ordered[-1].created_at + timedelta(days=days_to_target)
    return {
        "estimated_compliance_date": target_date.date().isoformat(),
        "required_improvement_rate": round(max((85 - latest_score) / max(days_to_target, 1), 0.1), 2),
        "risk_areas": ["Evidence coverage", "Policy coverage", "Implementation progress"],
    }
