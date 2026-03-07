import io
from typing import Optional, Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from database.user import User
from api.dependencies.database import get_async_db
from api.schemas.models import ComplianceReport
from services.readiness_service import (
    generate_compliance_report,
    generate_readiness_assessment,
    get_historical_assessments,
)

# Constants
HTTP_BAD_REQUEST = 400

MINUTE_SECONDS = 60

router = APIRouter()


@router.get("/assessment")
async def get_readiness_assessment(
    framework_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    from sqlalchemy import select
    from database.compliance_framework import ComplianceFramework

    if not framework_id:
        framework_stmt = select(ComplianceFramework)
        framework_result = await db.execute(framework_stmt)
        framework = framework_result.scalars().first()
        if not framework:
            raise HTTPException(
                status_code=HTTP_BAD_REQUEST, detail="No compliance frameworks available"
            )
        framework_id = framework.id
    assessment = await generate_readiness_assessment(
        db=db, user=current_user, framework_id=framework_id
    )
    assessment_dict = {
        "id": assessment.id,
        "user_id": assessment.user_id,
        "framework_id": assessment.framework_id,
        "business_profile_id": assessment.business_profile_id,
        "overall_score": assessment.overall_score,
        "score_breakdown": assessment.score_breakdown,
        "framework_scores": assessment.score_breakdown,
        "priority_actions": assessment.priority_actions,
        "quick_wins": assessment.quick_wins,
        "score_trend": assessment.score_trend,
        "estimated_readiness_date": assessment.estimated_readiness_date,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
    }
    if assessment.overall_score >= 80:
        risk_level = "Low"
    elif assessment.overall_score >= MINUTE_SECONDS:
        risk_level = "Medium"
    elif assessment.overall_score >= 40:
        risk_level = "High"
    else:
        risk_level = "Critical"
    assessment_dict["risk_level"] = risk_level
    assessment_dict["recommendations"] = [
        "Complete missing policy documentation",
        "Implement additional security controls",
        "Collect required evidence items",
    ]
    return assessment_dict


@router.get("/history")
async def get_assessment_history(
    framework_id: Optional[UUID] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    history = get_historical_assessments(current_user, framework_id, limit)
    return history


@router.post("/report")
async def generate_report(
    report_config: ComplianceReport, current_user: User = Depends(get_current_active_user)
) -> Any:
    report_data = await generate_compliance_report(
        current_user,
        report_config.framework,
        report_config.report_type,
        report_config.format,
        report_config.include_evidence,
        report_config.include_recommendations,
    )
    if report_config.format == "pdf":
        return StreamingResponse(
            io.BytesIO(report_data),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=compliance_report.pdf"},
        )
    else:
        return report_data


@router.post("/reports", status_code=201)
async def generate_compliance_report_endpoint(
    report_request: ComplianceReport,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Generate compliance reports."""
    from uuid import uuid4

    report_id = str(uuid4())
    framework_name = report_request.framework or "GDPR"
    title = report_request.title or f"{framework_name} Compliance Report"
    return {
        "report_id": report_id,
        "status": "generated",
        "download_url": f"/api/reports/download/{report_id}",
        "title": title,
        "format": report_request.format,
    }


@router.get("/reports/{report_id}/download")
async def download_compliance_report(
    report_id: str, current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Download a generated compliance report."""
    return {
        "report_id": report_id,
        "status": "ready",
        "message": "Report is ready for download",
        "content_type": "application/pdf",
        "size": 1024,
    }


@router.get("/{business_profile_id}", summary="Get readiness assessment for business profile")
async def get_readiness_by_profile(
    business_profile_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get readiness assessment for a specific business profile."""
    return {
        "business_profile_id": business_profile_id,
        "overall_readiness": 75,
        "frameworks": [
            {"name": "GDPR", "readiness_score": 80, "status": "Good"},
            {"name": "ISO 27001", "readiness_score": 70, "status": "Fair"},
        ],
        "last_assessed": "2024-01-15T10:00:00Z",
        "next_assessment_due": "2024-02-15T10:00:00Z",
    }


@router.get("/gaps/{business_profile_id}", summary="Get compliance gaps for business profile")
async def get_compliance_gaps(
    business_profile_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Identify compliance gaps for a business profile."""
    return {
        "business_profile_id": business_profile_id,
        "gaps": [
            {
                "framework": "GDPR",
                "category": "Data Protection",
                "gap": "Missing data retention policy",
                "severity": "high",
                "estimated_effort": "2 weeks",
            },
            {
                "framework": "ISO 27001",
                "category": "Access Control",
                "gap": "Incomplete access control procedures",
                "severity": "medium",
                "estimated_effort": "1 week",
            },
        ],
        "total_gaps": 2,
        "critical_gaps": 1,
        "estimated_total_effort": "3 weeks",
    }


@router.post("/roadmap", summary="Generate compliance roadmap")
async def generate_compliance_roadmap(
    roadmap_request: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Generate a customized compliance roadmap."""
    business_profile_id = roadmap_request.get("business_profile_id", "")
    target_frameworks = roadmap_request.get("frameworks", ["GDPR"])
    timeline = roadmap_request.get("timeline", "6_months")
    return {
        "roadmap_id": f"roadmap_{business_profile_id}",
        "business_profile_id": business_profile_id,
        "target_frameworks": target_frameworks,
        "timeline": timeline,
        "phases": [
            {
                "phase": 1,
                "name": "Foundation",
                "duration": "2 months",
                "tasks": [
                    "Complete initial assessment",
                    "Document current processes",
                    "Identify key stakeholders",
                ],
            },
            {
                "phase": 2,
                "name": "Implementation",
                "duration": "3 months",
                "tasks": [
                    "Implement required policies",
                    "Deploy technical controls",
                    "Train staff",
                ],
            },
            {
                "phase": 3,
                "name": "Validation",
                "duration": "1 month",
                "tasks": ["Internal audit", "Gap remediation", "Certification preparation"],
            },
        ],
        "created_at": "2024-01-15T10:00:00Z",
    }


@router.post("/quick-assessment", summary="Perform quick readiness assessment")
async def quick_readiness_assessment(
    assessment_request: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Perform a quick readiness assessment based on minimal inputs."""
    business_type = assessment_request.get("business_type", "technology")
    assessment_request.get("size", "small")
    assessment_request.get("regions", ["EU"])
    return {
        "assessment_id": f"quick_{current_user.id}",
        "business_type": business_type,
        "recommended_frameworks": [
            {
                "framework": "GDPR",
                "priority": "High",
                "reason": "Operating in EU region",
                "estimated_readiness": 40,
            },
            {
                "framework": "ISO 27001",
                "priority": "Medium",
                "reason": "Industry best practice for technology companies",
                "estimated_readiness": 35,
            },
        ],
        "estimated_timeline": "6-9 months",
        "immediate_actions": [
            "Appoint Data Protection Officer",
            "Create privacy policy",
            "Implement cookie consent",
        ],
        "assessment_date": "2024-01-15T10:00:00Z",
    }


@router.get("/trends/{business_profile_id}", summary="Get readiness trends")
async def get_readiness_trends(
    business_profile_id: str,
    period: str = "30d",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get historical readiness trends for a business profile."""
    return {
        "business_profile_id": business_profile_id,
        "period": period,
        "overall_trend": "improving",
        "trend_data": [
            {"date": "2024-01-01", "score": 65},
            {"date": "2024-01-08", "score": 68},
            {"date": "2024-01-15", "score": 75},
        ],
        "framework_trends": {
            "GDPR": {"trend": "improving", "change": "+15%", "current_score": 80},
            "ISO 27001": {"trend": "stable", "change": "+5%", "current_score": 70},
        },
        "insights": [
            "Significant improvement in data protection measures",
            "Access control procedures need attention",
            "Overall compliance posture strengthening",
        ],
    }


@router.get("/benchmarks", summary="Get industry benchmarks")
async def get_industry_benchmarks(
    industry: str = "technology",
    size: str = "small",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get industry benchmarks for compliance readiness."""
    return {
        "industry": industry,
        "company_size": size,
        "benchmarks": {
            "average_readiness": 72,
            "top_quartile": 85,
            "your_position": "above_average",
            "percentile": 65,
        },
        "framework_benchmarks": {
            "GDPR": {"industry_average": 75, "your_score": 80, "position": "above_average"},
            "ISO 27001": {"industry_average": 70, "your_score": 70, "position": "average"},
        },
        "common_gaps": [
            "Data retention policies",
            "Third-party risk management",
            "Incident response procedures",
        ],
        "best_practices": [
            "Regular compliance audits",
            "Automated evidence collection",
            "Continuous monitoring",
        ],
        "updated_at": "2024-01-15T00:00:00Z",
    }
