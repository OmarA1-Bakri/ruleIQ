from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.database import get_async_db
from api.schemas.models import ComplianceStatusResponse
from database.business_profile import BusinessProfile
from database.compliance_framework import ComplianceFramework
from database.evidence_item import EvidenceItem
from database.readiness_assessment import ReadinessAssessment
from database.compliance_risk import ComplianceRisk
from database.user import User
from pydantic import BaseModel, Field
from services.ai import ComplianceAssistant
from services.evidence_service import EvidenceService
from config.logging_config import get_logger

logger = get_logger(__name__)

# Constants
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

STATUS_COLUMN = "status"
UPDATED_AT_COLUMN = "updated_at"
router = APIRouter()

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
COMPLETED_EVIDENCE_STATUSES = {"approved"}
IN_PROGRESS_EVIDENCE_STATUSES = {"collected", "submitted", "pending_review", "in_review"}
BLOCKED_EVIDENCE_STATUSES = {"rejected", "needs_revision"}


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _normalize_priority(value: Optional[str]) -> str:
    if not value:
        return "medium"
    normalized = str(value).strip().lower()
    if normalized in {"critical", "high", "medium", "low"}:
        return normalized
    return "medium"


def _estimate_effort_hours(effort_estimate: Optional[str]) -> int:
    if not effort_estimate:
        return 3
    numbers = [int(chunk) for chunk in str(effort_estimate).replace("+", " ").split() if chunk.isdigit()]
    if len(numbers) >= 2:
        return max(1, round(sum(numbers[:2]) / 2))
    if len(numbers) == 1:
        return max(1, numbers[0])
    if "hour" in str(effort_estimate).lower():
        return 2
    return 3


def _derive_task_status(evidence_status: Optional[str]) -> str:
    normalized = (evidence_status or "not_started").strip().lower()
    if normalized in COMPLETED_EVIDENCE_STATUSES:
        return "completed"
    if normalized in IN_PROGRESS_EVIDENCE_STATUSES:
        return "in_progress"
    if normalized in BLOCKED_EVIDENCE_STATUSES:
        return "blocked"
    return "pending"


def _task_status_to_evidence_status(task_status: Optional[str]) -> str:
    mapping = {
        "completed": "approved",
        "in_progress": "pending_review",
        "blocked": "needs_revision",
        "pending": "not_started",
    }
    return mapping.get((task_status or "pending").strip().lower(), "not_started")


def _normalize_risk_status(value: Optional[str]) -> str:
    normalized = (value or "identified").strip().lower()
    if normalized in {"identified", "mitigating", "accepted", "resolved"}:
        return normalized
    return "identified"


def _clamp_page_size(page_size: int) -> int:
    return max(1, min(page_size, MAX_PAGE_SIZE))


def _build_task_record(evidence_item: EvidenceItem, framework_name: str) -> Dict[str, Any]:
    metadata = evidence_item.ai_metadata or {}
    assigned_to = (
        evidence_item.collected_by or evidence_item.reviewed_by or evidence_item.approved_by
    )
    due_date = metadata.get("due_date")
    if not due_date and evidence_item.updated_at and _derive_task_status(evidence_item.status) != "completed":
        due_date = (evidence_item.updated_at + timedelta(days=30)).isoformat()

    dependencies = metadata.get("dependencies") or []
    if not isinstance(dependencies, list):
        dependencies = []

    evidence_required = metadata.get("evidence_required") or []
    if not isinstance(evidence_required, list):
        evidence_required = []
    if not evidence_required:
        evidence_required = [evidence_item.evidence_type]

    return {
        "id": str(evidence_item.id),
        "title": evidence_item.evidence_name,
        "description": evidence_item.description,
        "control_id": evidence_item.control_reference,
        "framework": framework_name,
        "priority": _normalize_priority(evidence_item.priority),
        STATUS_COLUMN: _derive_task_status(evidence_item.status),
        "assigned_to": assigned_to,
        "due_date": due_date,
        "effort_hours": _estimate_effort_hours(evidence_item.effort_estimate),
        "dependencies": dependencies,
        "evidence_required": evidence_required,
        "created_at": _isoformat(evidence_item.created_at),
        UPDATED_AT_COLUMN: _isoformat(evidence_item.updated_at),
    }


def _framework_display_name(
    framework_lookup: Dict[str, ComplianceFramework], framework_id: Any
) -> str:
    framework = framework_lookup.get(str(framework_id))
    if not framework:
        return str(framework_id)
    return framework.display_name or framework.name


def _score_to_risk_severity(score: float) -> str:
    if score < 50:
        return "critical"
    if score < 65:
        return "high"
    if score < 80:
        return "medium"
    return "low"


def _score_to_likelihood(score: float, pending_count: int) -> str:
    if score < 50 or pending_count >= 5:
        return "very_likely"
    if score < 65 or pending_count >= 3:
        return "likely"
    if score < 80 or pending_count >= 1:
        return "possible"
    return "unlikely"


def _build_risk_records(
    assessments: Iterable[ReadinessAssessment],
    evidence_items: Iterable[EvidenceItem],
    framework_lookup: Dict[str, ComplianceFramework],
) -> list[Dict[str, Any]]:
    evidence_by_framework: Dict[str, list[EvidenceItem]] = {}
    for item in evidence_items:
        evidence_by_framework.setdefault(str(item.framework_id), []).append(item)

    risks: list[Dict[str, Any]] = []
    for assessment in assessments:
        framework_key = str(assessment.framework_id)
        framework = framework_lookup.get(framework_key)
        framework_name = getattr(framework, "display_name", None) or getattr(framework, "name", framework_key)
        framework_evidence = evidence_by_framework.get(framework_key, [])
        open_items = [
            item for item in framework_evidence if _derive_task_status(item.status) != "completed"
        ]
        affected_controls = [item.control_reference for item in open_items[:5] if item.control_reference]
        mitigation_steps = assessment.priority_actions or []
        if not isinstance(mitigation_steps, list):
            mitigation_steps = []

        score = float(assessment.overall_score)
        if score >= 85 and not open_items:
            continue

        risks.append(
            {
                "id": f"risk-{framework_key}",
                "title": f"{framework_name} readiness gap",
                "description": (
                    f"{framework_name} readiness is {round(score, 1)} with {len(open_items)} open evidence items."
                ),
                "severity": _score_to_risk_severity(score),
                "likelihood": _score_to_likelihood(score, len(open_items)),
                "impact": (
                    "Open readiness gaps may delay audits, certifications, or regulatory reviews."
                ),
                "affected_controls": affected_controls,
                "mitigation_plan": "; ".join(str(step) for step in mitigation_steps[:3])
                or "Complete open evidence items and address the highest-priority readiness actions.",
                STATUS_COLUMN: "mitigating" if open_items else "identified",
                "framework_id": framework_key,
                "framework": framework_name,
                "assessment_date": _isoformat(assessment.created_at),
            }
        )

    return risks


def _build_timeline(tasks: Iterable[Dict[str, Any]], risks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    milestones: list[Dict[str, Any]] = []
    upcoming_deadlines: list[Dict[str, Any]] = []

    for task in tasks:
        due_date_raw = task.get("due_date")
        if not due_date_raw:
            continue
        try:
            due_date = datetime.fromisoformat(str(due_date_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        status = task.get(STATUS_COLUMN, "pending")
        if status == "completed":
            milestone_status = "completed"
        elif due_date < now:
            milestone_status = "overdue"
        else:
            milestone_status = "upcoming"
        milestones.append(
            {
                "date": due_date.isoformat(),
                "title": task.get("title", "Compliance task"),
                "type": "review",
                STATUS_COLUMN: milestone_status,
                "description": task.get("description"),
            }
        )
        if milestone_status != "completed":
            upcoming_deadlines.append(
                {
                    "date": due_date.isoformat(),
                    "item": task.get("title", "Compliance task"),
                    "type": "task",
                    "days_remaining": max(0, (due_date - now).days),
                }
            )

    for risk in risks:
        assessment_date = risk.get("assessment_date")
        if not assessment_date:
            continue
        try:
            event_date = datetime.fromisoformat(str(assessment_date).replace("Z", "+00:00"))
        except ValueError:
            continue
        milestones.append(
            {
                "date": event_date.isoformat(),
                "title": risk.get("title", "Compliance risk review"),
                "type": "assessment",
                STATUS_COLUMN: "completed",
                "description": risk.get("description"),
            }
        )

    milestones.sort(key=lambda item: item["date"])
    upcoming_deadlines.sort(key=lambda item: item["date"])
    return {
        "milestones": milestones[:50],
        "upcoming_deadlines": upcoming_deadlines[:20],
    }


async def _get_user_business_profile(
    db: AsyncSession, current_user: User, business_profile_id: Optional[str] = None
) -> Optional[BusinessProfile]:
    stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if business_profile_id and profile and str(profile.id) != business_profile_id:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Business profile not found")
    return profile


async def _get_framework_lookup(db: AsyncSession) -> Dict[str, ComplianceFramework]:
    result = await db.execute(select(ComplianceFramework))
    frameworks = result.scalars().all()
    return {str(framework.id): framework for framework in frameworks}


async def _resolve_framework(
    db: AsyncSession, framework_identifier: Optional[str]
) -> Optional[ComplianceFramework]:
    if not framework_identifier:
        return None
    result = await db.execute(select(ComplianceFramework))
    frameworks = result.scalars().all()
    needle = framework_identifier.strip().lower()
    for framework in frameworks:
        if str(framework.id) == framework_identifier:
            return framework
        if framework.name.lower() == needle:
            return framework
        if framework.display_name.lower() == needle:
            return framework
    return None


async def _get_user_evidence_items(
    db: AsyncSession,
    current_user: User,
    business_profile: Optional[BusinessProfile],
    framework: Optional[ComplianceFramework] = None,
) -> list[EvidenceItem]:
    stmt = select(EvidenceItem).where(EvidenceItem.user_id == current_user.id)
    if business_profile:
        stmt = stmt.where(EvidenceItem.business_profile_id == business_profile.id)
    if framework:
        stmt = stmt.where(EvidenceItem.framework_id == framework.id)
    stmt = stmt.order_by(EvidenceItem.updated_at.desc(), EvidenceItem.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def _get_user_assessments(
    db: AsyncSession,
    current_user: User,
    business_profile: Optional[BusinessProfile],
    framework: Optional[ComplianceFramework] = None,
) -> list[ReadinessAssessment]:
    stmt = select(ReadinessAssessment).where(ReadinessAssessment.user_id == current_user.id)
    if business_profile:
        stmt = stmt.where(ReadinessAssessment.business_profile_id == business_profile.id)
    if framework:
        stmt = stmt.where(ReadinessAssessment.framework_id == framework.id)
    stmt = stmt.order_by(ReadinessAssessment.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/status", response_model=ComplianceStatusResponse)
async def get_compliance_status(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Get overall compliance status for the current user.

    Returns compliance metrics including:
    - Overall compliance score
    - Framework-specific scores
    - Evidence collection status
    - Recent activity summary
    """
    try:
        profile_stmt = select(BusinessProfile).where(BusinessProfile.user_id == current_user.id)
        profile_result = await db.execute(profile_stmt)
        profile = profile_result.scalars().first()
        if not profile:
            return {
                "overall_score": 0.0,
                STATUS_COLUMN: "not_started",
                "message": "Business profile not found. Please complete your business assessment first.",
                "framework_scores": {},
                "evidence_summary": {"total_items": 0, "by_status": {}, "by_type": {}},
                "recent_activity": [],
                "recommendations": [
                    "Complete your business profile assessment",
                    "Select relevant compliance frameworks",
                    "Begin evidence collection",
                ],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        evidence_stats = await EvidenceService.get_evidence_statistics(db, current_user.id)
        frameworks_stmt = select(ComplianceFramework)
        frameworks_result = await db.execute(frameworks_stmt)
        all_frameworks = frameworks_result.scalars().all()
        framework_scores = {}
        total_score = 0.0
        framework_count = 0
        for framework in all_frameworks:
            framework_evidence_stmt = select(EvidenceItem).where(
                EvidenceItem.user_id == current_user.id,
                EvidenceItem.framework_id == framework.id,
            )
            framework_evidence_result = await db.execute(framework_evidence_stmt)
            framework_evidence = framework_evidence_result.scalars().all()
            assessment_stmt = (
                select(ReadinessAssessment)
                .where(
                    ReadinessAssessment.user_id == current_user.id,
                    ReadinessAssessment.framework_id == framework.id,
                )
                .order_by(ReadinessAssessment.created_at.desc())
            )
            assessment_result = await db.execute(assessment_stmt)
            latest_assessment = assessment_result.scalars().first()
            if latest_assessment:
                framework_score = latest_assessment.overall_score
            else:
                evidence_count = len(framework_evidence)
                approved_evidence = len([e for e in framework_evidence if e.status == "approved"])
                framework_score = (
                    approved_evidence / max(evidence_count, 1) * 100 if evidence_count > 0 else 0.0
                )
            framework_scores[framework.name] = round(framework_score, 1)
            if framework_evidence:
                total_score += framework_score
                framework_count += 1
        overall_score = (
            round(total_score / max(framework_count, 1), 1) if framework_count > 0 else 0.0
        )
        if overall_score >= 90:
            status = "excellent"
        elif overall_score >= 75:
            status = "good"
        elif overall_score >= 50:
            status = "developing"
        elif overall_score > 0:
            status = "needs_improvement"
        else:
            status = "not_started"
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent_evidence_stmt = (
            select(EvidenceItem)
            .where(
                EvidenceItem.user_id == current_user.id,
                EvidenceItem.updated_at >= recent_cutoff,
            )
            .order_by(EvidenceItem.updated_at.desc())
            .limit(10)
        )
        recent_evidence_result = await db.execute(recent_evidence_stmt)
        recent_evidence = recent_evidence_result.scalars().all()
        recent_activity = [
            {
                "id": str(item.id),
                "title": item.evidence_name,
                "type": item.evidence_type,
                STATUS_COLUMN: item.status,
                UPDATED_AT_COLUMN: item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in recent_evidence
        ]
        recommendations = []
        if overall_score < 50:
            recommendations.extend(
                [
                    "Focus on collecting evidence for high-priority controls",
                    "Complete pending evidence reviews",
                    "Consider conducting a compliance gap analysis",
                ]
            )
        elif overall_score < 75:
            recommendations.extend(
                [
                    "Review and approve pending evidence items",
                    "Implement missing controls identified in assessments",
                    "Schedule regular compliance monitoring",
                ]
            )
        else:
            recommendations.extend(
                [
                    "Maintain current compliance posture",
                    "Schedule periodic compliance reviews",
                    "Consider expanding to additional frameworks",
                ]
            )
        return {
            "overall_score": overall_score,
            STATUS_COLUMN: status,
            "message": f"Compliance status: {status.replace('_', ' ').title()}",
            "framework_scores": framework_scores,
            "evidence_summary": {
                "total_items": evidence_stats.get("total_evidence_items", 0),
                "by_status": evidence_stats.get("by_status", {}),
                "by_type": evidence_stats.get("by_type", {}),
                "by_framework": evidence_stats.get("by_framework", {}),
            },
            "recent_activity": recent_activity,
            "recommendations": recommendations,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve compliance status: {e!s}",
        ) from e


@router.get("/status/{framework_id}", response_model=ComplianceStatusResponse)
async def get_framework_compliance_status(
    framework_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """
    Get compliance status for a specific framework.

    Args:
        framework_id: The ID of the compliance framework

    Returns:
        Compliance status specific to the requested framework
    """
    status_data = await get_compliance_status(current_user, db)
    framework = await _resolve_framework(db, framework_id)
    if not framework:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")

    framework_name = framework.display_name or framework.name
    framework_score = float(
        status_data.get("framework_scores", {}).get(framework.name)
        or status_data.get("framework_scores", {}).get(framework_name, 0.0)
    )
    return {
        **status_data,
        "overall_score": framework_score,
        "message": f"Compliance status for {framework_name}",
        "framework_scores": {framework_name: framework_score},
    }


@router.get("/tasks")
async def get_compliance_tasks(
    business_profile_id: Optional[str] = Query(default=None),
    framework_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Return compliance tasks backed by the user's evidence items."""
    profile = await _get_user_business_profile(db, current_user, business_profile_id)
    framework = await _resolve_framework(db, framework_id)
    if framework_id and not framework:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")

    framework_lookup = await _get_framework_lookup(db)
    evidence_items = await _get_user_evidence_items(db, current_user, profile, framework)
    tasks = [
        _build_task_record(item, _framework_display_name(framework_lookup, item.framework_id))
        for item in evidence_items
    ]

    if status:
        tasks = [task for task in tasks if task.get(STATUS_COLUMN) == status]
    if priority:
        tasks = [task for task in tasks if task.get("priority") == _normalize_priority(priority)]
    if assigned_to:
        assigned_needle = assigned_to.strip().lower()
        tasks = [
            task
            for task in tasks
            if str(task.get("assigned_to") or "").strip().lower() == assigned_needle
        ]

    total = len(tasks)
    size = _clamp_page_size(page_size)
    start = (page - 1) * size
    return {"tasks": tasks[start : start + size], "total": total}


@router.post("/tasks")
async def create_compliance_task(
    task_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Create a compliance task by storing it as an evidence work item."""
    profile = await _get_user_business_profile(db, current_user, task_data.get("business_profile_id"))
    if not profile:
        raise HTTPException(
            status_code=HTTP_BAD_REQUEST,
            detail="Business profile not found. Complete onboarding before creating tasks.",
        )

    framework = await _resolve_framework(db, task_data.get("framework_id"))
    if not framework:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")

    evidence_item = EvidenceItem(
        user_id=current_user.id,
        business_profile_id=profile.id,
        framework_id=framework.id,
        evidence_name=task_data.get("title") or "New compliance task",
        evidence_type=(task_data.get("evidence_required") or ["document"])[0],
        control_reference=task_data.get("control_id") or "general-control",
        description=task_data.get("description") or "",
        status=_task_status_to_evidence_status(task_data.get(STATUS_COLUMN)),
        priority=_normalize_priority(task_data.get("priority")),
        collected_by=task_data.get("assigned_to"),
        effort_estimate=f"{max(1, int(task_data.get('effort_hours', 3)))} hours",
        ai_metadata={
            "dependencies": task_data.get("dependencies") or [],
            "due_date": task_data.get("due_date"),
            "evidence_required": task_data.get("evidence_required") or [],
        },
    )
    db.add(evidence_item)
    await db.commit()
    await db.refresh(evidence_item)
    return _build_task_record(evidence_item, framework.display_name or framework.name)


@router.patch("/tasks/{task_id}")
async def update_compliance_task(
    task_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Update a compliance task by updating its underlying evidence item."""
    task_stmt = select(EvidenceItem).where(
        EvidenceItem.id == task_id,
        EvidenceItem.user_id == current_user.id,
    )
    task_result = await db.execute(task_stmt)
    evidence_item = task_result.scalars().first()
    if not evidence_item:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Task not found")

    if "title" in update_data:
        evidence_item.evidence_name = update_data["title"]
    if "description" in update_data:
        evidence_item.description = update_data["description"]
    if "control_id" in update_data:
        evidence_item.control_reference = update_data["control_id"]
    if STATUS_COLUMN in update_data:
        evidence_item.status = _task_status_to_evidence_status(update_data.get(STATUS_COLUMN))
    if "priority" in update_data:
        evidence_item.priority = _normalize_priority(update_data.get("priority"))
    if "assigned_to" in update_data:
        evidence_item.collected_by = update_data["assigned_to"]
    if "effort_hours" in update_data:
        evidence_item.effort_estimate = f"{max(1, int(update_data['effort_hours']))} hours"

    metadata = dict(evidence_item.ai_metadata or {})
    if "dependencies" in update_data:
        metadata["dependencies"] = update_data["dependencies"] or []
    if "due_date" in update_data:
        metadata["due_date"] = update_data["due_date"]
    if "evidence_required" in update_data:
        metadata["evidence_required"] = update_data["evidence_required"] or []
    evidence_item.ai_metadata = metadata

    await db.commit()
    await db.refresh(evidence_item)

    framework = await _resolve_framework(db, str(evidence_item.framework_id))
    framework_name = getattr(framework, "display_name", None) or getattr(framework, "name", None)
    if not framework_name:
        framework_name = str(evidence_item.framework_id)
    return _build_task_record(evidence_item, framework_name)


@router.get("/risks")
async def get_compliance_risks(
    business_profile_id: Optional[str] = Query(default=None),
    framework_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Return derived compliance risks from readiness and evidence gaps."""
    profile = await _get_user_business_profile(db, current_user, business_profile_id)
    framework = await _resolve_framework(db, framework_id)
    if framework_id and not framework:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")

    framework_lookup = await _get_framework_lookup(db)
    evidence_items = await _get_user_evidence_items(db, current_user, profile, framework)
    assessments = await _get_user_assessments(db, current_user, profile, framework)
    risks = _build_risk_records(assessments, evidence_items, framework_lookup)

    if severity:
        severity_value = severity.strip().lower()
        risks = [risk for risk in risks if risk.get("severity") == severity_value]
    if status:
        normalized_status = _normalize_risk_status(status)
        risks = [risk for risk in risks if risk.get(STATUS_COLUMN) == normalized_status]

    total = len(risks)
    size = _clamp_page_size(page_size)
    start = (page - 1) * size
    return {"risks": risks[start : start + size], "total": total}


@router.post("/risks", status_code=201)
async def create_compliance_risk(
    risk_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Create a persisted compliance risk register entry."""
    profile = await _get_user_business_profile(db, current_user, risk_data.get("business_profile_id"))
    if not profile:
        raise HTTPException(
            status_code=HTTP_BAD_REQUEST,
            detail="Business profile not found. Complete onboarding before creating risks.",
        )

    framework = await _resolve_framework(db, risk_data.get("framework_id"))
    if not framework:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")

    risk = ComplianceRisk(
        user_id=current_user.id,
        business_profile_id=profile.id,
        framework_id=framework.id,
        title=risk_data.get("title", "Untitled risk"),
        description=risk_data.get("description", ""),
        severity=risk_data.get("severity", "medium"),
        likelihood=risk_data.get("likelihood", "medium"),
        impact=risk_data.get("impact", "medium"),
        risk_score=float(risk_data.get("risk_score", 5.0)),
        status=risk_data.get("status", "open"),
        mitigation_plan=risk_data.get("mitigation_plan"),
        mitigation_status=risk_data.get("mitigation_status", "not_started"),
        category=risk_data.get("category"),
        control_reference=risk_data.get("control_reference"),
        owner=risk_data.get("owner"),
        ai_metadata=risk_data.get("ai_metadata", {}),
    )
    db.add(risk)
    await db.commit()
    await db.refresh(risk)

    return {
        "id": str(risk.id),
        "user_id": str(risk.user_id),
        "business_profile_id": str(risk.business_profile_id),
        "framework_id": str(risk.framework_id),
        "title": risk.title,
        "description": risk.description,
        "severity": risk.severity,
        "likelihood": risk.likelihood,
        "impact": risk.impact,
        "risk_score": risk.risk_score,
        "status": risk.status,
        "mitigation_plan": risk.mitigation_plan,
        "mitigation_status": risk.mitigation_status,
        "category": risk.category,
        "control_reference": risk.control_reference,
        "owner": risk.owner,
        "ai_metadata": risk.ai_metadata,
        "created_at": _isoformat(risk.created_at),
        "updated_at": _isoformat(risk.updated_at),
    }


@router.patch("/risks/{risk_id}")
async def update_compliance_risk(
    risk_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Update a persisted compliance risk register entry."""
    stmt = select(ComplianceRisk).where(
        ComplianceRisk.id == risk_id,
        ComplianceRisk.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    risk = result.scalars().first()
    if not risk:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Risk not found")

    updatable_fields = (
        "title", "description", "severity", "likelihood", "impact",
        "risk_score", "status", "mitigation_plan", "mitigation_status",
        "category", "control_reference", "owner",
    )
    for field in updatable_fields:
        if field in update_data:
            value = update_data[field]
            if field == "risk_score":
                value = float(value)
            setattr(risk, field, value)

    if "ai_metadata" in update_data:
        risk.ai_metadata = update_data["ai_metadata"]

    await db.commit()
    await db.refresh(risk)

    return {
        "id": str(risk.id),
        "user_id": str(risk.user_id),
        "business_profile_id": str(risk.business_profile_id),
        "framework_id": str(risk.framework_id),
        "title": risk.title,
        "description": risk.description,
        "severity": risk.severity,
        "likelihood": risk.likelihood,
        "impact": risk.impact,
        "risk_score": risk.risk_score,
        "status": risk.status,
        "mitigation_plan": risk.mitigation_plan,
        "mitigation_status": risk.mitigation_status,
        "category": risk.category,
        "control_reference": risk.control_reference,
        "owner": risk.owner,
        "ai_metadata": risk.ai_metadata,
        "created_at": _isoformat(risk.created_at),
        "updated_at": _isoformat(risk.updated_at),
    }


@router.get("/timeline")
async def get_compliance_timeline(
    business_profile_id: Optional[str] = Query(default=None),
    framework_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get a timeline built from evidence work items and readiness assessments."""
    profile = await _get_user_business_profile(db, current_user, business_profile_id)
    framework = await _resolve_framework(db, framework_id)
    if framework_id and not framework:
        raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")

    framework_lookup = await _get_framework_lookup(db)
    evidence_items = await _get_user_evidence_items(db, current_user, profile, framework)
    assessments = await _get_user_assessments(db, current_user, profile, framework)
    tasks = [
        _build_task_record(item, _framework_display_name(framework_lookup, item.framework_id))
        for item in evidence_items
    ]
    risks = _build_risk_records(assessments, evidence_items, framework_lookup)
    timeline = _build_timeline(tasks, risks)

    completed_tasks = sum(1 for task in tasks if task.get(STATUS_COLUMN) == "completed")
    progress_percentage = round((completed_tasks / max(len(tasks), 1)) * 100) if tasks else 0
    current_phase = "monitoring" if progress_percentage >= 90 else "remediation" if risks else "evidence_collection"
    estimated_completion = None
    if timeline["upcoming_deadlines"]:
        estimated_completion = timeline["upcoming_deadlines"][-1]["date"]

    return {
        "framework_id": str(framework.id) if framework else framework_id,
        **timeline,
        "current_phase": current_phase,
        "estimated_completion": estimated_completion,
        "progress_percentage": progress_percentage,
    }

@router.get("/dashboard")
async def get_compliance_dashboard(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get compliance dashboard data."""
    status_data = await get_compliance_status(current_user, db)
    profile = await _get_user_business_profile(db, current_user)
    framework_lookup = await _get_framework_lookup(db)
    evidence_items = await _get_user_evidence_items(db, current_user, profile)
    assessments = await _get_user_assessments(db, current_user, profile)
    tasks = [
        _build_task_record(item, _framework_display_name(framework_lookup, item.framework_id))
        for item in evidence_items
    ]
    risks = _build_risk_records(assessments, evidence_items, framework_lookup)
    timeline = _build_timeline(tasks, risks)
    evidence_summary = status_data.get("evidence_summary", {})
    framework_scores = status_data.get("framework_scores", {})
    return {
        **status_data,
        "pending_tasks": sum(1 for task in tasks if task.get(STATUS_COLUMN) != "completed"),
        "open_risks": sum(1 for risk in risks if risk.get(STATUS_COLUMN) != "resolved"),
        "upcoming_audits": [
            {
                "framework": deadline.get("item"),
                "date": deadline.get("date"),
                "type": deadline.get("type"),
            }
            for deadline in timeline.get("upcoming_deadlines", [])[:5]
        ],
        "recent_activity": [
            {
                "timestamp": item.get(UPDATED_AT_COLUMN),
                "type": item.get("framework"),
                "description": item.get("title"),
            }
            for item in tasks[:10]
        ],
        "compliance_trends": [
            {
                "date": assessment.created_at.date().isoformat(),
                "score": round(float(assessment.overall_score), 1),
            }
            for assessment in assessments[:10]
        ],
        "dashboard_metrics": {
            "active_frameworks": len(framework_scores),
            "total_evidence": evidence_summary.get("total_items", 0),
            "pending_tasks": sum(1 for task in tasks if task.get(STATUS_COLUMN) != "completed"),
            "identified_risks": sum(1 for risk in risks if risk.get(STATUS_COLUMN) != "resolved"),
            "upcoming_deadlines": len(timeline.get("upcoming_deadlines", [])),
        },
        "quick_actions": [
            {"action": "Upload Evidence", "path": "/evidence/upload"},
            {"action": "Start Assessment", "path": "/assessments/new"},
            {"action": "Review Tasks", "path": "/compliance/tasks"},
            {"action": "View Risks", "path": "/compliance/risks"},
        ],
    }


@router.post("/certificate/generate")
async def generate_compliance_certificate(
    request_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Generate a compliance attestation derived from the user's current platform data."""
    framework_id = request_data.get("framework_id")
    certificate_type = request_data.get("type", "attestation")
    allowed_types = {"attestation", "readiness", "summary"}
    if certificate_type not in allowed_types:
        raise HTTPException(
            status_code=HTTP_BAD_REQUEST,
            detail=f"Unsupported certificate type. Allowed values: {sorted(allowed_types)}",
        )

    status_data = await get_compliance_status(current_user, db)
    evidence_summary = status_data.get("evidence_summary", {})
    total_evidence = evidence_summary.get("total_items", 0)
    if total_evidence <= 0:
        raise HTTPException(
            status_code=HTTP_BAD_REQUEST,
            detail="Cannot generate an attestation without collected evidence.",
        )

    framework_name = "overall"
    compliance_score = float(status_data.get("overall_score", 0.0))
    if framework_id:
        framework_stmt = select(ComplianceFramework).where(ComplianceFramework.id == framework_id)
        framework_result = await db.execute(framework_stmt)
        framework = framework_result.scalars().first()
        if not framework:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail="Framework not found")
        framework_name = framework.name
        compliance_score = float(status_data.get("framework_scores", {}).get(framework.name, 0.0))

    if compliance_score <= 0:
        raise HTTPException(
            status_code=HTTP_BAD_REQUEST,
            detail="Compliance score is unavailable for the requested scope.",
        )

    profile_stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(current_user.id))
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalars().first()

    certificate_id = f"cert-{uuid4().hex[:12]}"
    verification_code = f"VERIFY-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}"
    return {
        "certificate_id": certificate_id,
        "framework_id": framework_id,
        "framework_name": framework_name,
        "type": certificate_type,
        STATUS_COLUMN: "generated",
        "issue_date": datetime.now(timezone.utc).isoformat(),
        "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "compliance_score": round(compliance_score, 1),
        "certificate_url": f"/api/v1/compliance/certificate/{certificate_id}/download",
        "verification_code": verification_code,
        "issuer": "RuleIQ Compliance Platform",
        "recipient": {
            "organization": getattr(profile, "company_name", None) or current_user.email,
            "contact": current_user.email,
        },
        "evidence_snapshot": {
            "total_items": total_evidence,
            "by_status": evidence_summary.get("by_status", {}),
            "by_framework": evidence_summary.get("by_framework", {}),
        },
        "disclaimer": (
            "This is an automatically generated attestation based on current RuleIQ data and does "
            "not replace independent legal, audit, or certification review."
        ),
    }


class ComplianceQueryRequest(BaseModel):
    """Request model for compliance query endpoint."""

    question: str = Field(..., min_length=1, max_length=2000)
    framework: Optional[str] = Field(default=None, max_length=100)


def _fallback_response(question: str, framework: Optional[str]) -> Dict[str, Any]:
    """Return a static fallback when the AI service is unavailable."""
    fw = (framework or "").upper()
    if fw == "GDPR":
        answer = (
            "GDPR (General Data Protection Regulation) requires organizations to implement "
            "appropriate technical and organizational measures to ensure data protection. Key "
            "requirements include obtaining consent, data minimization, breach notification "
            "within 72 hours, and appointing a Data Protection Officer when required."
        )
    elif fw == "ISO 27001":
        answer = (
            "ISO 27001 is an international standard for information security management systems. "
            "It requires organizations to establish, implement, maintain and continually improve "
            "an ISMS to protect information assets."
        )
    else:
        answer = (
            f"I can help with compliance questions about "
            f"{framework if framework else 'various '}frameworks. "
            f"Please provide more specific details about your compliance requirements."
        )
    return {
        "answer": answer,
        "framework": framework or "",
        "confidence": "low",
        "sources": [
            f"{framework} official documentation" if framework else "Compliance best practices"
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ai_generated": False,
    }


@router.post("/query")
async def query_compliance(
    request: ComplianceQueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """
    Query compliance information using AI assistant.

    This endpoint provides AI-powered compliance guidance and answers
    to compliance-related questions. Uses the ComplianceAssistant facade
    for intelligent, context-aware responses with automatic fallback to
    static answers when the AI service is unavailable.
    """
    try:
        system_prompt = (
            "You are RuleIQ, a UK compliance expert assistant. "
            "Provide accurate, actionable compliance guidance. "
            "Cite relevant regulations and standards where applicable."
        )
        framework_ctx = f" (framework: {request.framework})" if request.framework else ""
        user_prompt = f"{request.question}{framework_ctx}"

        assistant = ComplianceAssistant(db)
        answer = await assistant.response_generator.generate_simple(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            task_type="compliance_analysis",
            context={"user_id": str(current_user.id), "framework": request.framework},
        )

        if not answer or not answer.strip():
            logger.warning("AI returned empty response for compliance query, using fallback")
            return _fallback_response(request.question, request.framework)

        return {
            "answer": answer,
            "framework": request.framework or "",
            "confidence": "high",
            "sources": [
                f"{request.framework} official documentation"
                if request.framework
                else "Compliance best practices"
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_generated": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI compliance query failed: %s — falling back to static response", e)
        return _fallback_response(request.question, request.framework)
