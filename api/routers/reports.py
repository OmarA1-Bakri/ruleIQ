from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from database.db_setup import get_async_db
from database.user import User
from services.launch_metrics import get_owned_business_profile
from services.reporting.report_store import ReportStore

router = APIRouter()


class GenerateReportRequest(BaseModel):
    report_type: str = Field(default="compliance")
    framework_id: Optional[str] = None
    business_profile_id: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None
    include_sections: list[str] = Field(default_factory=list)
    format: Optional[str] = "pdf"


class ScheduleReportRequest(BaseModel):
    report_config: GenerateReportRequest
    schedule: Dict[str, Any]
    recipients: list[str] = Field(default_factory=list)


def _get_store(db: AsyncSession) -> ReportStore:
    return ReportStore(db)


@router.get("/history", summary="Get report history")
async def get_report_history(
    report_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    return store.list_reports(current_user.id, report_type=report_type, page=page, page_size=page_size)


@router.post("/generate", summary="Generate a report")
async def generate_report(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    try:
        return await store.generate_report(current_user, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/templates", summary="List report templates")
async def get_report_templates(
    report_type: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    templates = store.template_manager.list_templates()
    filtered = [
        {
            "id": template["name"],
            "name": template["display_name"],
            "description": template["description"],
            "report_type": report_type or "compliance",
            "sections": (store.template_manager.get_template(template["name"]) or {}).get(
                "sections", []
            ),
        }
        for template in templates
        if not report_type or report_type in template["name"]
    ]
    return {"templates": filtered}


@router.post("/preview", summary="Preview report")
async def preview_report(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    return store.preview_report(request.model_dump())


@router.post("/schedule", summary="Create report schedule")
async def schedule_report(
    request: ScheduleReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    try:
        return await store.create_schedule(current_user, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scheduled", summary="List scheduled reports")
async def list_scheduled_reports(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    return await store.list_schedules(current_user.id)


@router.patch("/scheduled/{schedule_id}", summary="Update scheduled report")
async def update_scheduled_report(
    schedule_id: UUID,
    updates: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    try:
        await store.update_schedule(schedule_id, updates, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Schedule updated"}


@router.delete("/scheduled/{schedule_id}", summary="Delete scheduled report")
async def delete_scheduled_report(
    schedule_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    try:
        await store.delete_schedule(schedule_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Schedule deleted"}


@router.get("/analytics", summary="Get report analytics")
async def get_report_analytics(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    return store.build_analytics(current_user.id, days=days)


@router.post("/export-bundle", summary="Export report bundle")
async def export_report_bundle(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    report_ids = request.get("report_ids") or []
    if not report_ids:
        raise HTTPException(status_code=400, detail="report_ids is required")
    store = _get_store(db)
    return store.export_bundle(current_user.id, report_ids)


@router.get("/export-bundle/{bundle_id}/download", summary="Download report bundle")
async def download_report_bundle(
    bundle_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> FileResponse:
    store = _get_store(db)
    bundle_path = store.get_bundle_path(current_user.id, bundle_id)
    if not bundle_path:
        raise HTTPException(status_code=404, detail="Report bundle not found")
    return FileResponse(bundle_path, media_type="application/zip", filename=f"{bundle_id}.zip")


@router.post("/upload", summary="Upload external report")
async def upload_external_report(
    file: UploadFile = File(...),
    report_type: str = Query(default="custom"),
    business_profile_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    profile = await get_owned_business_profile(db, current_user.id, business_profile_id)
    if not profile:
        raise HTTPException(status_code=400, detail="Business profile not found")

    store = _get_store(db)
    report_id = f"upload-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    extension = Path(file.filename or "report.pdf").suffix.lstrip(".") or "bin"
    artifact_path = store._artifact_path(current_user.id, report_id, extension)
    artifact_path.write_bytes(await file.read())

    metadata = {
        "id": report_id,
        "title": Path(file.filename or "Uploaded Report").stem.replace("_", " ").title(),
        "description": "Externally uploaded compliance report",
        "report_type": report_type,
        "status": "completed",
        "format": "pdf" if extension == "pdf" else "html" if extension == "html" else "excel",
        "business_profile_id": str(profile.id),
        "framework_id": None,
        "date_range": None,
        "file_path": str(artifact_path),
        "file_url": f"/api/v1/reports/{report_id}/download",
        "file_size": artifact_path.stat().st_size,
        "generated_by": str(current_user.id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requested_format": extension,
        "content_type": file.content_type or "application/octet-stream",
    }
    store._write_metadata(current_user.id, metadata)
    return metadata


@router.get("/{report_id}", summary="Get report details")
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    report = store.get_report(current_user.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/download", summary="Download report")
async def download_report(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> FileResponse:
    store = _get_store(db)
    report = store.get_report(current_user.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    artifact_path = Path(report["file_path"])
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Report artifact not found")

    filename = f"{report['title'].replace(' ', '_')}.{artifact_path.suffix.lstrip('.')}"
    return FileResponse(
        artifact_path,
        media_type=report.get("content_type", "application/octet-stream"),
        filename=filename,
    )


@router.delete("/{report_id}", summary="Delete report")
async def delete_report(
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    store = _get_store(db)
    deleted = store.delete_report(current_user.id, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted"}
