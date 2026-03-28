from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.database import get_async_db
from api.schemas.models import ComplianceFrameworkResponse
from database.compliance_framework import ComplianceFramework
from database.user import User
from services.launch_metrics import (
    build_framework_controls,
    calculate_framework_status,
    get_owned_business_profile,
    get_profile_frameworks,
    load_profile_framework_state,
)

router = APIRouter()


def _serialize_framework(framework: ComplianceFramework) -> ComplianceFrameworkResponse:
    return ComplianceFrameworkResponse(
        id=framework.id,
        name=framework.display_name,
        description=framework.description or "",
        category=framework.category or "general",
        version=framework.version or "1.0",
        controls=build_framework_controls(framework),
    )


def _framework_relevance(profile: Any, framework: ComplianceFramework) -> tuple[float, List[str], str]:
    score = 25.0
    reasons: List[str] = []

    if profile.industry and profile.industry in (framework.applicable_indu or []):
        score += 30
        reasons.append(f"Relevant to the {profile.industry} industry.")
    if profile.employee_count and framework.employee_thresh and profile.employee_count >= framework.employee_thresh:
        score += 20
        reasons.append("Company size meets the framework applicability threshold.")
    if profile.has_international_operations and any(
        location in {"EU", "Global", "UK"} for location in (framework.geographic_scop or [])
    ):
        score += 15
        reasons.append("Framework aligns with international operating footprint.")
    if profile.handles_personal_data and framework.category.lower() in {"data protection", "information security"}:
        score += 20
        reasons.append("Business handles personal or regulated information.")
    if profile.processes_payments and "PCI" in framework.display_name.upper():
        score += 25
        reasons.append("Framework is relevant to payment-processing obligations.")

    priority = "high" if score >= 70 else "medium" if score >= 50 else "low"
    return score, reasons or ["General launch relevance for the current business profile."], priority


@router.get("/", response_model=List[ComplianceFrameworkResponse])
async def list_frameworks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    result = await db.execute(
        select(ComplianceFramework)
        .where(ComplianceFramework.is_active.is_(True))
        .order_by(ComplianceFramework.display_name.asc(), ComplianceFramework.name.asc())
    )
    frameworks = result.scalars().all()
    return [_serialize_framework(framework) for framework in frameworks]


@router.get("/recommendations")
async def get_framework_recommendations(
    business_profile_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        return []

    frameworks = await get_profile_frameworks(db, profile)
    recommendations = []
    for framework in frameworks:
        relevance_score, reasons, priority = _framework_relevance(profile, framework)
        recommendations.append(
            {
                "framework": _serialize_framework(framework).model_dump(mode="json"),
                "relevance_score": round(relevance_score, 2),
                "reasons": reasons,
                "estimated_effort": f"{max(1, framework.implementation_ // 4)}-{max(2, framework.implementation_ // 2)} months",
                "priority": priority,
            }
        )

    recommendations.sort(key=lambda item: item["relevance_score"], reverse=True)
    return recommendations


@router.get("/recommendations/{business_profile_id}")
async def get_framework_recommendations_for_profile(
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    return await get_framework_recommendations(business_profile_id, current_user, db)


@router.get("/all-public", response_model=List[ComplianceFrameworkResponse])
async def list_all_public_frameworks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    return await list_frameworks(current_user, db)


@router.get("/{id}", response_model=ComplianceFrameworkResponse)
async def get_framework(
    id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    result = await db.execute(select(ComplianceFramework).where(ComplianceFramework.id == id))
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found")
    return _serialize_framework(framework)


@router.get("/{framework_id}/controls")
async def get_framework_controls(
    framework_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    result = await db.execute(select(ComplianceFramework).where(ComplianceFramework.id == framework_id))
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found")

    controls = build_framework_controls(framework)
    return {
        "framework": framework.display_name,
        "total_controls": len(controls),
        "controls": controls,
    }


@router.get("/{framework_id}/implementation-guide")
async def get_framework_implementation_guide(
    framework_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    result = await db.execute(select(ComplianceFramework).where(ComplianceFramework.id == framework_id))
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found")

    controls = build_framework_controls(framework)
    phases = [
        {
            "phase": 1,
            "name": "Scope and baseline",
            "duration": "2-3 weeks",
            "tasks": [
                "Confirm framework scope",
                "Identify owners",
                "Baseline current evidence and policy coverage",
            ],
            "deliverables": ["Scope document", "Owner matrix", "Baseline assessment"],
        },
        {
            "phase": 2,
            "name": "Control implementation",
            "duration": f"{max(4, framework.implementation_ // 3)} weeks",
            "tasks": [control["control_name"] for control in controls[:5]],
            "deliverables": ["Implemented controls", "Updated policies", "Collected evidence"],
        },
        {
            "phase": 3,
            "name": "Validation and launch readiness",
            "duration": "2-4 weeks",
            "tasks": [
                "Run readiness assessment",
                "Resolve critical gaps",
                "Prepare executive reporting",
            ],
            "deliverables": ["Readiness assessment", "Gap register", "Launch evidence pack"],
        },
    ]

    return {
        "framework": framework.display_name,
        "estimated_duration": f"{max(2, framework.implementation_ // 4)}-{max(4, framework.implementation_ // 2)} months",
        "phases": phases,
        "resources_required": [
            "Compliance owner",
            "Policy approver",
            "Technical implementation lead",
        ],
        "key_milestones": [phase["name"] for phase in phases],
    }


@router.get("/{framework_id}/compliance-status")
async def get_framework_compliance_status(
    framework_id: UUID,
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    result = await db.execute(select(ComplianceFramework).where(ComplianceFramework.id == framework_id))
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found")

    state = await load_profile_framework_state(db, current_user.id, profile, [framework])
    status = calculate_framework_status(
        framework,
        state["evidence"].get(framework.id, []),
        state["policies"].get(framework.id, []),
        state["plans"].get(framework.id, []),
        state["assessments"].get(framework.id),
    )
    return {
        "framework": status["framework"],
        "overall_compliance": status["overall_compliance_percentage"],
        "by_category": {item["domain"]: item["compliance_percentage"] for item in status["by_domain"]},
        "controls_status": status["controls_status"],
        "last_assessment_date": status["last_assessment_date"],
        "next_review_date": status["next_review_date"],
    }


@router.post("/compare")
async def compare_frameworks(
    comparison_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    framework_ids = comparison_data.get("framework_ids", [])
    if len(framework_ids) < 2:
        raise HTTPException(status_code=400, detail="At least two framework_ids are required")

    result = await db.execute(
        select(ComplianceFramework).where(ComplianceFramework.id.in_([UUID(item) for item in framework_ids]))
    )
    frameworks = result.scalars().all()
    if len(frameworks) < 2:
        raise HTTPException(status_code=404, detail="Unable to load requested frameworks")

    controls_by_framework = {str(framework.id): build_framework_controls(framework) for framework in frameworks}
    common_controls = min(len(controls) for controls in controls_by_framework.values())
    unique_controls = {
        str(framework.id): max(len(controls_by_framework[str(framework.id)]) - common_controls, 0)
        for framework in frameworks
    }

    return {
        "frameworks": [
            {
                "id": str(framework.id),
                "name": framework.display_name,
                "control_count": len(controls_by_framework[str(framework.id)]),
                "estimated_effort": f"{max(2, framework.implementation_ // 4)}-{max(4, framework.implementation_ // 2)} months",
                "industry_alignment": framework.applicable_indu or [],
                "key_features": (framework.key_requirement or [])[:5],
            }
            for framework in frameworks
        ],
        "overlap_analysis": {
            "common_controls": common_controls,
            "unique_controls": unique_controls,
            "compatibility_score": round(common_controls / max(sum(len(v) for v in controls_by_framework.values()) / len(frameworks), 1) * 100, 2),
        },
        "recommendation": "Use the higher-overlap framework first, then extend evidence and policies to the second framework.",
    }


@router.get("/{framework_id}/maturity-assessment")
async def get_framework_maturity_assessment(
    framework_id: UUID,
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    result = await db.execute(select(ComplianceFramework).where(ComplianceFramework.id == framework_id))
    framework = result.scalars().first()
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found")

    state = await load_profile_framework_state(db, current_user.id, profile, [framework])
    status = calculate_framework_status(
        framework,
        state["evidence"].get(framework.id, []),
        state["policies"].get(framework.id, []),
        state["plans"].get(framework.id, []),
        state["assessments"].get(framework.id),
    )
    return {
        "framework": framework.display_name,
        "maturity_level": status["maturity_level"],
        "maturity_score": status["maturity_score"],
        "strengths": status["strengths"],
        "weaknesses": status["weaknesses"],
        "improvement_areas": [
            {
                "area": domain["domain"],
                "current_level": round(domain["compliance_percentage"] / 20, 2),
                "target_level": 5,
                "recommendations": status["recommendations"][:2],
            }
            for domain in status["by_domain"]
        ],
    }
