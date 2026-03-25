from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.database import get_async_db
from database.compliance_framework import ComplianceFramework
from database.readiness_assessment import ReadinessAssessment
from database.user import User
from services.launch_metrics import (
    build_framework_controls,
    build_trend_projection,
    calculate_framework_status,
    get_owned_business_profile,
    get_profile_frameworks,
    load_profile_framework_state,
)
from services.readiness_service import generate_readiness_assessment
from services.reporting.report_store import ReportStore

router = APIRouter()


async def _load_profile_statuses(
    db: AsyncSession, current_user: User, business_profile_id: UUID | str
) -> tuple[Any, list[ComplianceFramework], list[Dict[str, Any]], Dict[str, Dict[Any, Any]]]:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    frameworks = await get_profile_frameworks(db, profile)
    state = await load_profile_framework_state(db, current_user.id, profile, frameworks)
    statuses = [
        calculate_framework_status(
            framework,
            state["evidence"].get(framework.id, []),
            state["policies"].get(framework.id, []),
            state["plans"].get(framework.id, []),
            state["assessments"].get(framework.id),
        )
        for framework in frameworks
    ]
    return profile, frameworks, statuses, state


@router.get("/assessment")
async def get_readiness_assessment(
    framework_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    if not framework_id:
        framework_result = await db.execute(
            select(ComplianceFramework)
            .where(ComplianceFramework.is_active.is_(True))
            .order_by(ComplianceFramework.display_name.asc())
        )
        framework = framework_result.scalars().first()
        if not framework:
            raise HTTPException(status_code=400, detail="No compliance frameworks available")
        framework_id = framework.id

    assessment = await generate_readiness_assessment(db=db, user=current_user, framework_id=framework_id)
    return {
        "id": str(assessment.id),
        "user_id": str(assessment.user_id),
        "framework_id": str(assessment.framework_id),
        "business_profile_id": str(assessment.business_profile_id),
        "overall_score": assessment.overall_score,
        "score_breakdown": assessment.score_breakdown,
        "priority_actions": assessment.priority_actions or [],
        "quick_wins": assessment.quick_wins or [],
        "score_trend": assessment.score_trend,
        "estimated_readiness_date": assessment.estimated_readiness_date.isoformat()
        if assessment.estimated_readiness_date
        else None,
        "created_at": assessment.created_at.isoformat(),
        "updated_at": assessment.updated_at.isoformat(),
    }


@router.get("/history")
async def get_assessment_history(
    business_profile_id: UUID,
    framework_id: Optional[UUID] = None,
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    statement = (
        select(ReadinessAssessment)
        .where(
            ReadinessAssessment.user_id == current_user.id,
            ReadinessAssessment.business_profile_id == profile.id,
        )
        .order_by(ReadinessAssessment.created_at.desc())
        .limit(limit)
    )
    if framework_id:
        statement = statement.where(ReadinessAssessment.framework_id == framework_id)

    result = await db.execute(statement)
    assessments = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "framework_id": str(item.framework_id),
            "overall_score": item.overall_score,
            "score_breakdown": item.score_breakdown,
            "priority_actions": item.priority_actions or [],
            "quick_wins": item.quick_wins or [],
            "created_at": item.created_at.isoformat(),
        }
        for item in assessments
    ]


@router.post("/report")
async def generate_report(
    report_config: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    store = ReportStore(db)
    metadata = await store.generate_report(
        current_user,
        {
            "report_type": "audit",
            "framework_id": report_config.get("framework_id"),
            "business_profile_id": report_config.get("business_profile_id"),
            "format": report_config.get("format", "pdf"),
        },
    )
    return FileResponse(metadata["file_path"], media_type=metadata["content_type"])


@router.get("/{business_profile_id}", summary="Get readiness assessment for business profile")
async def get_readiness_by_profile(
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    _, _, statuses, _ = await _load_profile_statuses(db, current_user, business_profile_id)
    if not statuses:
        return {
            "overall_score": 0,
            "category_scores": {"policies": 0, "processes": 0, "technology": 0, "people": 0},
            "maturity_level": "initial",
            "strengths": [],
            "weaknesses": ["No frameworks are configured for this business profile yet."],
            "recommendations": [
                {
                    "category": "planning",
                    "priority": "high",
                    "description": "Select target frameworks and begin evidence collection.",
                    "effort": "medium",
                    "impact": "high",
                }
            ],
        }

    overall_score = round(
        sum(status["overall_compliance_percentage"] for status in statuses) / len(statuses),
        2,
    )
    category_scores = {
        "policies": round(sum(status["maturity_score"] for status in statuses) / len(statuses), 2),
        "processes": round(
            sum(status["risk_summary"]["remediation_in_progress"] for status in statuses)
            / max(sum(status["control_count"] for status in statuses), 1)
            * 100,
            2,
        ),
        "technology": round(
            sum(
                status["controls_status"]["compliant"] / max(status["control_count"], 1) * 100
                for status in statuses
            )
            / len(statuses),
            2,
        ),
        "people": round(
            sum(max(0, 100 - status["risk_summary"]["medium_risk_items"] * 10) for status in statuses)
            / len(statuses),
            2,
        ),
    }

    strengths = sorted(
        {
            strength
            for status in statuses
            for strength in status.get("strengths", [])
        }
    )[:5]
    weaknesses = sorted(
        {
            weakness
            for status in statuses
            for weakness in status.get("weaknesses", [])
        }
    )[:5]

    recommendation_items = []
    for status in statuses:
        for description in status.get("recommendations", [])[:2]:
            recommendation_items.append(
                {
                    "category": status["framework"],
                    "priority": "high"
                    if status["overall_compliance_percentage"] < 60
                    else "medium",
                    "description": description,
                    "effort": "medium",
                    "impact": "high" if status["overall_compliance_percentage"] < 60 else "medium",
                }
            )

    maturity_level = (
        "optimized"
        if overall_score >= 85
        else "managed"
        if overall_score >= 70
        else "defined"
        if overall_score >= 55
        else "developing"
        if overall_score >= 35
        else "initial"
    )

    return {
        "overall_score": overall_score,
        "category_scores": category_scores,
        "maturity_level": maturity_level,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendation_items[:8],
    }


@router.get("/gaps/{business_profile_id}", summary="Get compliance gaps for business profile")
async def get_compliance_gaps(
    business_profile_id: UUID,
    framework_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    _, frameworks, statuses, _ = await _load_profile_statuses(db, current_user, business_profile_id)
    if not frameworks:
        return {
            "framework": "none",
            "gaps": [],
            "summary": {
                "total_gaps": 0,
                "critical_gaps": 0,
                "estimated_remediation_time": "0 weeks",
                "quick_wins": [],
            },
        }

    target_index = 0
    if framework_id:
        for index, framework in enumerate(frameworks):
            if str(framework.id) == framework_id:
                target_index = index
                break

    framework = frameworks[target_index]
    status = statuses[target_index]
    controls = build_framework_controls(framework)
    gaps = []
    missing_count = max(status["controls_status"]["non_compliant"], 1)
    partial_count = status["controls_status"]["partial"]

    for index, control in enumerate(controls[: missing_count + partial_count], start=1):
        gap_type = "missing" if index <= missing_count else "partial"
        priority = "critical" if gap_type == "missing" and index <= 2 else "high"
        gaps.append(
            {
                "control_id": control["control_id"],
                "control_name": control["control_name"],
                "gap_type": gap_type,
                "current_state": "Control evidence and implementation are incomplete.",
                "target_state": "Control is evidenced, governed by policy, and operationalized.",
                "remediation_steps": [
                    "Collect required evidence",
                    "Confirm policy coverage",
                    "Complete implementation task",
                ],
                "priority": priority,
                "estimated_effort": "1-2 weeks" if gap_type == "missing" else "3-5 days",
            }
        )

    return {
        "framework": framework.display_name,
        "gaps": gaps,
        "summary": {
            "total_gaps": len(gaps),
            "critical_gaps": sum(1 for gap in gaps if gap["priority"] == "critical"),
            "estimated_remediation_time": f"{max(len(gaps), 1)} weeks",
            "quick_wins": [gap["control_name"] for gap in gaps[:3]],
        },
    }


@router.post("/roadmap", summary="Generate compliance roadmap")
async def generate_compliance_roadmap(
    roadmap_request: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile, frameworks, statuses, _ = await _load_profile_statuses(
        db, current_user, roadmap_request.get("business_profile_id")
    )
    requested_frameworks = set(roadmap_request.get("target_frameworks") or [])
    roadmap_frameworks = [
        (framework, status)
        for framework, status in zip(frameworks, statuses)
        if not requested_frameworks
        or str(framework.id) in requested_frameworks
        or framework.name in requested_frameworks
        or framework.display_name in requested_frameworks
    ]

    start_date = datetime.now(timezone.utc).date()
    phases = []
    milestones = []
    for index, (framework, status) in enumerate(roadmap_frameworks[:4], start=1):
        phase_start = start_date + timedelta(days=(index - 1) * 30)
        phase_end = phase_start + timedelta(days=29)
        phases.append(
            {
                "phase": index,
                "name": f"{framework.display_name} remediation sprint",
                "duration": "4 weeks",
                "objectives": [
                    "Increase control coverage",
                    "Close evidence gaps",
                    "Advance implementation progress",
                ],
                "key_activities": [
                    {
                        "activity": "Resolve high-priority compliance gaps",
                        "owner": "Compliance lead",
                        "effort": "medium",
                        "dependencies": [],
                    },
                    {
                        "activity": "Approve missing policies",
                        "owner": "Policy owner",
                        "effort": "medium",
                        "dependencies": ["Resolve high-priority compliance gaps"],
                    },
                ],
                "deliverables": [
                    f"{framework.display_name} control evidence pack",
                    f"{framework.display_name} remediation review",
                ],
                "success_criteria": [
                    f"Reach at least {min(85, int(status['overall_compliance_percentage']) + 15)}% compliance",
                    "All launch-critical gaps have owners and due dates",
                ],
            }
        )
        milestones.append(
            {
                "date": phase_end.isoformat(),
                "milestone": f"{framework.display_name} phase complete",
                "phase": index,
            }
        )

    return {
        "phases": phases,
        "timeline": {
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=max(len(phases), 1) * 30)).isoformat(),
            "milestones": milestones,
        },
        "resource_requirements": {
            "internal_hours": max(len(phases), 1) * 40,
            "external_support_needed": any(
                status["overall_compliance_percentage"] < 50 for _, status in roadmap_frameworks
            ),
            "budget_estimate": profile.compliance_budget or "TBD",
            "tools_required": sorted(
                {
                    tool
                    for tool in (profile.cloud_providers or []) + (profile.development_tools or [])
                }
            )[:8],
        },
    }


@router.post("/quick-assessment", summary="Perform quick readiness assessment")
async def quick_readiness_assessment(
    assessment_request: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    answers = assessment_request.get("answers") or {}
    positive_signals = 0
    scored_answers = 0
    for value in answers.values():
        if isinstance(value, bool):
            positive_signals += 1 if value else 0
            scored_answers += 1
        elif isinstance(value, (int, float)):
            positive_signals += min(max(float(value), 0.0), 5.0) / 5.0
            scored_answers += 1
        elif isinstance(value, str):
            scored_answers += 1
            positive_signals += 1 if value.lower() in {"yes", "true", "implemented", "complete"} else 0

    score = round((positive_signals / max(scored_answers, 1)) * 100, 2)
    interpretation = (
        "Strong starting point"
        if score >= 75
        else "Moderate readiness with clear remediation work"
        if score >= 50
        else "Early-stage readiness requiring structured remediation"
    )
    return {
        "score": score,
        "interpretation": interpretation,
        "next_steps": [
            "Complete a full readiness assessment",
            "Prioritize framework evidence collection",
            "Create implementation owners for high-risk gaps",
        ],
        "detailed_report_available": True,
    }


@router.get("/trends/{business_profile_id}", summary="Get readiness trends")
async def get_readiness_trends(
    business_profile_id: UUID,
    days: int = Query(default=90, ge=7, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(ReadinessAssessment)
        .where(
            ReadinessAssessment.user_id == current_user.id,
            ReadinessAssessment.business_profile_id == profile.id,
            ReadinessAssessment.created_at >= cutoff,
        )
        .order_by(ReadinessAssessment.created_at.asc())
    )
    assessments = result.scalars().all()
    trends = [
        {
            "date": item.created_at.date().isoformat(),
            "overall_score": item.overall_score,
            "category_scores": item.score_breakdown or {},
        }
        for item in assessments
    ]
    if not trends:
        trends = [
            {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "overall_score": 0,
                "category_scores": {"policy": 0, "implementation": 0, "evidence": 0},
            }
        ]

    improvements = []
    latest_breakdown = trends[-1]["category_scores"]
    earliest_breakdown = trends[0]["category_scores"]
    for category in sorted(set(latest_breakdown) | set(earliest_breakdown)):
        latest_value = float(latest_breakdown.get(category, 0))
        earliest_value = float(earliest_breakdown.get(category, 0))
        improvements.append(
            {
                "category": category,
                "improvement_percentage": round(latest_value - earliest_value, 2),
                "key_changes": [f"{category.title()} improved from {earliest_value} to {latest_value}"],
            }
        )

    return {
        "trends": trends,
        "improvements": improvements,
        "projections": build_trend_projection(assessments),
    }


@router.get("/benchmarks", summary="Get industry benchmarks")
async def get_industry_benchmarks(
    industry: str,
    company_size: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile_result = await db.execute(select(ComplianceFramework).where(ComplianceFramework.is_active.is_(True)))
    framework_count = len(profile_result.scalars().all())

    size_baseline = {
        "micro": 45,
        "small": 55,
        "medium": 65,
        "large": 72,
        "enterprise": 78,
    }.get(company_size.lower(), 60)
    industry_adjustment = 5 if industry.lower() in {"finance", "healthcare", "technology"} else 0
    industry_average = min(size_baseline + industry_adjustment, 85)
    top_performers = min(industry_average + 15, 95)
    your_position = (
        "above_average"
        if industry_average >= 65
        else "average"
        if industry_average >= 50
        else "below_average"
    )

    peer_comparison = [
        {
            "category": "policies",
            "your_score": industry_average,
            "industry_average": industry_average,
            "gap": 0,
        },
        {
            "category": "technology",
            "your_score": max(industry_average - 5, 0),
            "industry_average": industry_average,
            "gap": round(industry_average - max(industry_average - 5, 0), 2),
        },
        {
            "category": "processes",
            "your_score": min(industry_average + framework_count, 100),
            "industry_average": industry_average,
            "gap": round(industry_average - min(industry_average + framework_count, 100), 2),
        },
    ]
    return {
        "industry_average": industry_average,
        "top_performers": top_performers,
        "your_position": your_position,
        "improvement_opportunities": [
            "Automate evidence collection for high-frequency controls",
            "Tighten policy review cadences",
            "Add milestone tracking to implementation plans",
        ],
        "peer_comparison": peer_comparison,
    }


@router.get("/export/{business_profile_id}", summary="Export readiness report")
async def export_readiness_report(
    business_profile_id: UUID,
    format: str = Query(default="pdf"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    store = ReportStore(db)
    metadata = await store.generate_report(
        current_user,
        {
            "report_type": "audit",
            "business_profile_id": business_profile_id,
            "format": format,
        },
    )
    if metadata["format"] == "pdf":
        return FileResponse(metadata["file_path"], media_type=metadata["content_type"])

    content = Path(metadata["file_path"]).read_bytes()
    return StreamingResponse(
        BytesIO(content),
        media_type=metadata["content_type"],
        headers={"Content-Disposition": f"attachment; filename=readiness-report.{metadata['format']}"},
    )
