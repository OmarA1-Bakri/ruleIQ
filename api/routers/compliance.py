from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.database import get_async_db
from database.business_profile import BusinessProfile
from database.readiness_assessment import ReadinessAssessment
from database.user import User
from services.launch_metrics import (
    build_recommended_risks,
    build_recommended_tasks,
    calculate_framework_status,
    get_owned_business_profile,
    get_profile_frameworks,
    load_profile_framework_state,
)

router = APIRouter()


def _get_profile_state_container(profile: BusinessProfile) -> Dict[str, Any]:
    assessment_data = profile.assessment_data if isinstance(profile.assessment_data, dict) else {}
    assessment_data.setdefault("compliance_tasks", [])
    assessment_data.setdefault("compliance_risks", [])
    return assessment_data


async def _load_statuses(
    db: AsyncSession, current_user: User, business_profile_id: UUID | str
) -> tuple[BusinessProfile, List[Dict[str, Any]]]:
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
    return profile, statuses


async def _persist_profile_state(db: AsyncSession, profile: BusinessProfile, data: Dict[str, Any]) -> None:
    profile.assessment_data = data
    profile.updated_at = datetime.utcnow()
    db.add(profile)
    await db.commit()
    await db.refresh(profile)


@router.get("/status")
async def get_compliance_status(
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> List[Dict[str, Any]]:
    _, statuses = await _load_statuses(db, current_user, business_profile_id)
    return statuses


@router.get("/status/{framework_id}")
async def get_framework_compliance_status(
    framework_id: UUID,
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    _, statuses = await _load_statuses(db, current_user, business_profile_id)
    for status in statuses:
        if status["framework_id"] == str(framework_id):
            return status
    raise HTTPException(status_code=404, detail="Framework status not found")


@router.get("/tasks")
async def get_compliance_tasks(
    business_profile_id: UUID,
    framework_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile, statuses = await _load_statuses(db, current_user, business_profile_id)
    state = _get_profile_state_container(profile)
    generated_tasks = build_recommended_tasks(profile.id, statuses)
    stored_tasks = state.get("compliance_tasks", [])

    merged_tasks = {task["id"]: task for task in generated_tasks}
    for task in stored_tasks:
        merged_tasks[task["id"]] = task

    tasks = list(merged_tasks.values())
    if framework_id:
        tasks = [task for task in tasks if task.get("framework_id") == framework_id]
    if status:
        tasks = [task for task in tasks if task.get("status") == status]
    if priority:
        tasks = [task for task in tasks if task.get("priority") == priority]
    if assigned_to:
        tasks = [task for task in tasks if task.get("assigned_to") == assigned_to]

    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {"tasks": tasks[start:end], "total": len(tasks)}


@router.post("/tasks")
async def create_compliance_task(
    task_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    business_profile_id = task_data.get("business_profile_id")
    if not business_profile_id:
        raise HTTPException(status_code=400, detail="business_profile_id is required")

    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    state = _get_profile_state_container(profile)
    task = {
        "id": str(uuid4()),
        "title": task_data.get("title", "New compliance task"),
        "description": task_data.get("description", ""),
        "control_id": task_data.get("control_id", "general"),
        "framework": task_data.get("framework", "General"),
        "framework_id": task_data.get("framework_id"),
        "business_profile_id": str(profile.id),
        "priority": task_data.get("priority", "medium"),
        "status": task_data.get("status", "pending"),
        "assigned_to": task_data.get("assigned_to"),
        "due_date": task_data.get("due_date"),
        "effort_hours": task_data.get("effort_hours", 4),
        "dependencies": task_data.get("dependencies", []),
        "evidence_required": task_data.get("evidence_required", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    state["compliance_tasks"].append(task)
    await _persist_profile_state(db, profile, state)
    return task


@router.patch("/tasks/{task_id}")
async def update_compliance_task(
    task_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    business_profile_id = update_data.get("business_profile_id")
    if not business_profile_id:
        raise HTTPException(status_code=400, detail="business_profile_id is required")

    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    state = _get_profile_state_container(profile)
    for task in state["compliance_tasks"]:
        if task["id"] == task_id:
            task.update({key: value for key, value in update_data.items() if value is not None})
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            await _persist_profile_state(db, profile, state)
            return task

    raise HTTPException(status_code=404, detail="Compliance task not found")


@router.get("/risks")
async def get_compliance_risks(
    business_profile_id: UUID,
    framework_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile, statuses = await _load_statuses(db, current_user, business_profile_id)
    state = _get_profile_state_container(profile)
    generated_risks = build_recommended_risks(profile.id, statuses)
    stored_risks = state.get("compliance_risks", [])

    merged_risks = {risk["id"]: risk for risk in generated_risks}
    for risk in stored_risks:
        merged_risks[risk["id"]] = risk

    risks = list(merged_risks.values())
    if framework_id:
        risks = [risk for risk in risks if risk.get("framework_id") == framework_id]
    if severity:
        risks = [risk for risk in risks if risk.get("severity") == severity]
    if status:
        risks = [risk for risk in risks if risk.get("status") == status]

    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {"risks": risks[start:end], "total": len(risks)}


@router.post("/risks")
async def create_compliance_risk(
    risk_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    business_profile_id = risk_data.get("business_profile_id")
    if not business_profile_id:
        raise HTTPException(status_code=400, detail="business_profile_id is required")

    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    state = _get_profile_state_container(profile)
    risk = {
        "id": str(uuid4()),
        "title": risk_data.get("title", "New compliance risk"),
        "description": risk_data.get("description", ""),
        "severity": risk_data.get("severity", "medium"),
        "likelihood": risk_data.get("likelihood", "possible"),
        "impact": risk_data.get("impact", ""),
        "affected_controls": risk_data.get("affected_controls", []),
        "mitigation_plan": risk_data.get("mitigation_plan"),
        "status": risk_data.get("status", "identified"),
        "framework": risk_data.get("framework", "General"),
        "framework_id": risk_data.get("framework_id"),
        "business_profile_id": str(profile.id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    state["compliance_risks"].append(risk)
    await _persist_profile_state(db, profile, state)
    return risk


@router.patch("/risks/{risk_id}")
async def update_compliance_risk(
    risk_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    business_profile_id = update_data.get("business_profile_id")
    if not business_profile_id:
        raise HTTPException(status_code=400, detail="business_profile_id is required")

    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    state = _get_profile_state_container(profile)
    for risk in state["compliance_risks"]:
        if risk["id"] == risk_id:
            risk.update({key: value for key, value in update_data.items() if value is not None})
            risk["updated_at"] = datetime.now(timezone.utc).isoformat()
            await _persist_profile_state(db, profile, state)
            return risk

    raise HTTPException(status_code=404, detail="Compliance risk not found")


@router.get("/timeline")
async def get_compliance_timeline(
    business_profile_id: UUID,
    framework_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile, statuses = await _load_statuses(db, current_user, business_profile_id)
    state = _get_profile_state_container(profile)
    tasks = state.get("compliance_tasks", []) or build_recommended_tasks(profile.id, statuses)
    if framework_id:
        tasks = [task for task in tasks if task.get("framework_id") == framework_id]

    milestones = []
    today = datetime.now(timezone.utc).date()
    for index, status in enumerate(statuses[:6], start=1):
        milestone_date = today + timedelta(days=index * 14)
        milestones.append(
            {
                "date": milestone_date.isoformat(),
                "title": f"{status['framework']} review checkpoint",
                "type": "review",
                "status": "completed" if status["overall_compliance_percentage"] >= 75 else "upcoming",
                "description": "Framework readiness and remediation checkpoint.",
            }
        )

    upcoming_deadlines = []
    for task in tasks[:10]:
        if task.get("due_date"):
            deadline = datetime.fromisoformat(str(task["due_date"])).date()
        else:
            deadline = today + timedelta(days=21)
        upcoming_deadlines.append(
            {
                "date": deadline.isoformat(),
                "item": task["title"],
                "type": "task",
                "days_remaining": (deadline - today).days,
            }
        )

    return {"milestones": milestones, "upcoming_deadlines": upcoming_deadlines}


@router.get("/dashboard")
async def get_compliance_dashboard(
    business_profile_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile, statuses = await _load_statuses(db, current_user, business_profile_id)
    state = _get_profile_state_container(profile)
    tasks = state.get("compliance_tasks", []) or build_recommended_tasks(profile.id, statuses)
    risks = state.get("compliance_risks", []) or build_recommended_risks(profile.id, statuses)

    assessment_result = await db.execute(
        select(ReadinessAssessment)
        .where(
            ReadinessAssessment.user_id == current_user.id,
            ReadinessAssessment.business_profile_id == profile.id,
        )
        .order_by(ReadinessAssessment.created_at.asc())
        .limit(20)
    )
    assessments = assessment_result.scalars().all()
    compliance_trends = [
        {"date": item.created_at.date().isoformat(), "score": item.overall_score}
        for item in assessments
    ]
    if not compliance_trends:
        compliance_trends = [
            {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "score": round(
                    sum(status["overall_compliance_percentage"] for status in statuses) / max(len(statuses), 1),
                    2,
                ),
            }
        ]

    return {
        "overall_score": round(
            sum(status["overall_compliance_percentage"] for status in statuses) / max(len(statuses), 1),
            2,
        ),
        "frameworks_status": statuses,
        "pending_tasks": len([task for task in tasks if task.get("status") != "completed"]),
        "open_risks": len([risk for risk in risks if risk.get("status") != "resolved"]),
        "upcoming_audits": [
            {
                "framework": status["framework"],
                "date": (datetime.now(timezone.utc) + timedelta(days=45)).date().isoformat(),
                "type": "readiness_review",
            }
            for status in statuses[:3]
        ],
        "recent_activity": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "framework_status",
                "description": f"{status['framework']} is currently {status['status'].replace('_', ' ')}.",
                "user": current_user.email,
            }
            for status in statuses[:5]
        ],
        "compliance_trends": compliance_trends,
    }


@router.post("/certificate/generate")
async def generate_compliance_certificate(
    request_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    business_profile_id = request_data.get("business_profile_id")
    framework_id = request_data.get("framework_id")
    if not business_profile_id or not framework_id:
        raise HTTPException(status_code=400, detail="business_profile_id and framework_id are required")

    _, statuses = await _load_statuses(db, current_user, business_profile_id)
    status = next((item for item in statuses if item["framework_id"] == framework_id), None)
    if not status:
        raise HTTPException(status_code=404, detail="Framework status not found")

    issued = datetime.now(timezone.utc)
    return {
        "certificate_id": str(uuid4()),
        "issued_date": issued.isoformat(),
        "valid_until": (issued + timedelta(days=365)).isoformat(),
        "download_url": f"/api/v1/compliance/certificate/{framework_id}/download",
        "framework": status["framework"],
        "score": status["overall_compliance_percentage"],
        "status": status["status"],
    }


@router.post("/query")
async def query_compliance(
    request: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    question = str(request.get("question", "")).strip()
    framework = str(request.get("framework", "")).strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    business_profile_id = request.get("business_profile_id")
    response_prefix = "Compliance guidance"
    if business_profile_id:
        _, statuses = await _load_statuses(db, current_user, business_profile_id)
        matching_status = next(
            (item for item in statuses if framework.lower() in item["framework"].lower()),
            statuses[0] if statuses else None,
        )
        if matching_status:
            response_prefix = (
                f"{matching_status['framework']} is currently {matching_status['status']} "
                f"at {matching_status['overall_compliance_percentage']}%."
            )

    return {
        "answer": (
            f"{response_prefix} Prioritise evidence completion, policy approvals, and implementation execution "
            f"to answer: {question}"
        ),
        "framework": framework or None,
        "confidence": "medium",
        "sources": ["Internal compliance status", "Framework guidance"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
