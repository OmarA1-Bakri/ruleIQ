from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.compliance_framework import ComplianceFramework
from database.report_schedule import ReportSchedule
from database.user import User
from services.launch_metrics import get_owned_business_profile
from services.reporting.pdf_generator import PDFGenerator
from services.reporting.report_generator import ReportGenerator
from services.reporting.report_scheduler import ReportScheduler
from services.reporting.template_manager import TemplateManager


REPORT_TYPE_MAP = {
    "executive": "executive_summary",
    "compliance": "compliance_status",
    "assessment": "gap_analysis",
    "evidence": "evidence_report",
    "audit": "audit_readiness",
}

REPORT_STATUS_GENERATING = "generating"
REPORT_STATUS_COMPLETED = "completed"


class ReportStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.template_manager = TemplateManager()
        self.pdf_generator = PDFGenerator()
        self.generator = ReportGenerator(db)
        self.scheduler = ReportScheduler(db)
        self.root = Path(settings.report_directory)
        self.root.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: UUID) -> Path:
        path = self.root / str(user_id)
        path.mkdir(parents=True, exist_ok=True)
        (path / "metadata").mkdir(exist_ok=True)
        (path / "artifacts").mkdir(exist_ok=True)
        (path / "bundles").mkdir(exist_ok=True)
        return path

    def _metadata_path(self, user_id: UUID, report_id: str) -> Path:
        return self._user_dir(user_id) / "metadata" / f"{report_id}.json"

    def _artifact_path(self, user_id: UUID, report_id: str, extension: str) -> Path:
        return self._user_dir(user_id) / "artifacts" / f"{report_id}.{extension}"

    def _bundle_path(self, user_id: UUID, bundle_id: str) -> Path:
        return self._user_dir(user_id) / "bundles" / f"{bundle_id}.zip"

    def _write_metadata(self, user_id: UUID, metadata: Dict[str, Any]) -> None:
        self._metadata_path(user_id, metadata["id"]).write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

    def _read_metadata(self, user_id: UUID, report_id: str) -> Optional[Dict[str, Any]]:
        path = self._metadata_path(user_id, report_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_reports(
        self,
        user_id: UUID,
        report_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        metadata_dir = self._user_dir(user_id) / "metadata"
        items: List[Dict[str, Any]] = []
        for path in metadata_dir.glob("*.json"):
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if report_type and metadata.get("report_type") != report_type:
                continue
            items.append(metadata)

        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        return {"items": items[start:end], "total": len(items)}

    async def generate_report(
        self,
        user: User,
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        profile = await get_owned_business_profile(
            self.db, user.id, request_data.get("business_profile_id")
        )
        if not profile:
            raise ValueError("Business profile not found for report generation")

        report_type = str(request_data.get("report_type", "compliance"))
        generator_type = REPORT_TYPE_MAP.get(report_type, "compliance_status")
        framework_id = request_data.get("framework_id")
        if generator_type == "gap_analysis" and not framework_id:
            framework_result = await self.db.execute(
                select(ComplianceFramework)
                .where(ComplianceFramework.is_active.is_(True))
                .order_by(ComplianceFramework.display_name.asc())
            )
            default_framework = framework_result.scalars().first()
            framework_id = str(default_framework.id) if default_framework else None

        generator_params = {
            "framework_id": framework_id,
            "include_sections": request_data.get("include_sections", []),
            "date_range": request_data.get("date_range"),
        }
        report_payload = await self.generator.generate_report(
            user_id=user.id,
            business_profile_id=profile.id,
            report_type=generator_type,
            parameters=generator_params,
        )
        report_payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
        report_payload.setdefault("business_profile", profile.to_dict())
        report_payload["report_type"] = generator_type

        requested_format = str(request_data.get("format") or "pdf").lower()
        final_format = "pdf" if requested_format not in {"html", "json", "excel"} else requested_format

        report_id = str(uuid4())
        title = f"{profile.company_name} {report_type.title()} Report"
        description = f"{report_type.title()} report generated for {profile.company_name}"

        if final_format == "pdf":
            artifact_bytes = await self.pdf_generator.generate_pdf(report_payload, output_format="bytes")
            extension = "pdf"
            content_type = "application/pdf"
        elif final_format == "excel":
            extension = "csv"
            content_type = "text/csv"
            artifact_buffer = io.StringIO()
            writer = csv.writer(artifact_buffer)
            writer.writerow(["section", "value"])
            for key, value in report_payload.items():
                writer.writerow([key, json.dumps(value) if isinstance(value, (dict, list)) else value])
            artifact_bytes = artifact_buffer.getvalue().encode("utf-8")
        elif final_format == "html":
            extension = "html"
            content_type = "text/html"
            artifact_bytes = (
                "<html><body><pre>"
                + json.dumps(report_payload, indent=2)
                + "</pre></body></html>"
            ).encode("utf-8")
        else:
            extension = "json"
            content_type = "application/json"
            artifact_bytes = json.dumps(report_payload, indent=2).encode("utf-8")

        artifact_path = self._artifact_path(user.id, report_id, extension)
        artifact_path.write_bytes(artifact_bytes)

        metadata = {
            "id": report_id,
            "title": title,
            "description": description,
            "report_type": report_type,
            "status": REPORT_STATUS_COMPLETED,
            "format": final_format,
            "business_profile_id": str(profile.id),
            "framework_id": str(framework_id) if framework_id else None,
            "date_range": request_data.get("date_range"),
            "file_path": str(artifact_path),
            "file_url": f"/api/v1/reports/{report_id}/download",
            "file_size": artifact_path.stat().st_size,
            "generated_by": str(user.id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested_format": requested_format,
            "content_type": content_type,
            "template_sections": request_data.get("include_sections", []),
        }
        self._write_metadata(user.id, metadata)
        return metadata

    def get_report(self, user_id: UUID, report_id: str) -> Optional[Dict[str, Any]]:
        return self._read_metadata(user_id, report_id)

    def delete_report(self, user_id: UUID, report_id: str) -> bool:
        metadata = self._read_metadata(user_id, report_id)
        if not metadata:
            return False

        artifact_path = Path(metadata["file_path"])
        if artifact_path.exists():
            artifact_path.unlink()

        metadata_path = self._metadata_path(user_id, report_id)
        if metadata_path.exists():
            metadata_path.unlink()

        return True

    def preview_report(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        report_type = str(request_data.get("report_type", "compliance"))
        template_name = {
            "executive": "executive_summary",
            "compliance": "detailed_gap_analysis",
            "assessment": "detailed_gap_analysis",
            "evidence": "evidence_collection",
            "audit": "audit_readiness",
        }.get(report_type, "executive_summary")
        template = self.template_manager.get_template(template_name) or {}
        sections = request_data.get("include_sections") or template.get("sections", [])

        return {
            "preview": {
                "title": f"{report_type.title()} Report Preview",
                "sections": [
                    {
                        "name": section.replace("_", " ").title(),
                        "content_summary": f"Launch-ready {section.replace('_', ' ')} section",
                        "data_points": 3,
                    }
                    for section in sections
                ],
                "estimated_pages": max(6, len(sections) * 2),
                "estimated_generation_time": max(15, len(sections) * 10),
            }
        }

    async def create_schedule(self, user: User, schedule_request: Dict[str, Any]) -> Dict[str, Any]:
        report_config = schedule_request.get("report_config", {})
        profile = await get_owned_business_profile(
            self.db, user.id, report_config.get("business_profile_id")
        )
        if not profile:
            raise ValueError("Business profile not found for report schedule")

        schedule_info = schedule_request.get("schedule", {})
        time_of_day = str(schedule_info.get("time", "09:00"))
        frequency = str(schedule_info.get("frequency", "weekly"))
        recipients = schedule_request.get("recipients", [])

        schedule = await self.scheduler.create_schedule(
            user_id=user.id,
            business_profile_id=profile.id,
            report_type=report_config.get("report_type", "compliance"),
            frequency=frequency,
            parameters={
                **report_config,
                "schedule": schedule_info,
                "time": time_of_day,
            },
            recipients=recipients,
            active=True,
        )
        next_run = self._calculate_next_run(schedule.created_at, schedule_info)
        return {
            "schedule_id": str(schedule.id),
            "message": "Report schedule created",
            "next_run": next_run.isoformat(),
        }

    async def list_schedules(self, user_id: UUID) -> Dict[str, Any]:
        result = await self.db.execute(
            select(ReportSchedule)
            .where(ReportSchedule.user_id == user_id)
            .order_by(ReportSchedule.created_at.desc())
        )
        schedules = result.scalars().all()
        return {
            "schedules": [
                {
                    "id": str(schedule.id),
                    "report_config": {
                        **(schedule.parameters or {}),
                        "report_type": schedule.report_type,
                        "business_profile_id": str(schedule.business_profile_id),
                    },
                    "schedule": {
                        "frequency": schedule.frequency,
                        **((schedule.parameters or {}).get("schedule") or {}),
                    },
                    "recipients": schedule.recipients or [],
                    "active": schedule.active,
                    "last_run": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
                    "next_run": self._calculate_next_run(
                        schedule.last_run_at or schedule.created_at,
                        (schedule.parameters or {}).get("schedule") or {},
                    ).isoformat(),
                }
                for schedule in schedules
            ]
        }

    async def update_schedule(
        self, schedule_id: UUID | str, updates: Dict[str, Any], user_id: UUID
    ) -> None:
        schedule = await self.scheduler.get_schedule(UUID(str(schedule_id)))
        if schedule.user_id != user_id:
            raise ValueError("Schedule not found")

        patched_updates: Dict[str, Any] = {}
        if "recipients" in updates:
            patched_updates["recipients"] = updates["recipients"]
        if "active" in updates:
            patched_updates["active"] = updates["active"]
        if "report_config" in updates or "schedule" in updates:
            patched_parameters = dict(schedule.parameters or {})
            if "report_config" in updates:
                patched_parameters.update(updates["report_config"])
                if "report_type" in updates["report_config"]:
                    patched_updates["report_type"] = updates["report_config"]["report_type"]
            if "schedule" in updates:
                patched_parameters["schedule"] = updates["schedule"]
                if "frequency" in updates["schedule"]:
                    patched_updates["frequency"] = updates["schedule"]["frequency"]
            patched_updates["parameters"] = patched_parameters

        await self.scheduler.update_schedule(UUID(str(schedule_id)), patched_updates)

    async def delete_schedule(self, schedule_id: UUID | str, user_id: UUID) -> None:
        schedule = await self.scheduler.get_schedule(UUID(str(schedule_id)))
        if schedule.user_id != user_id:
            raise ValueError("Schedule not found")
        await self.scheduler.delete_schedule(UUID(str(schedule_id)))

    def build_analytics(self, user_id: UUID, days: int = 30) -> Dict[str, Any]:
        listed = self.list_reports(user_id, page=1, page_size=1000)["items"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [
            report
            for report in listed
            if datetime.fromisoformat(report["created_at"]) >= cutoff
        ]

        by_type: Dict[str, int] = {}
        by_format: Dict[str, int] = {}
        usage_trend: Dict[str, int] = {}
        for report in recent:
            by_type[report["report_type"]] = by_type.get(report["report_type"], 0) + 1
            by_format[report["format"]] = by_format.get(report["format"], 0) + 1
            day = report["created_at"][:10]
            usage_trend[day] = usage_trend.get(day, 0) + 1

        return {
            "total_reports_generated": len(recent),
            "by_type": by_type,
            "by_format": by_format,
            "average_generation_time": 30,
            "most_generated_sections": ["Executive Overview", "Key Metrics", "Recommendations"],
            "usage_trend": [
                {"date": date, "count": usage_trend[date]}
                for date in sorted(usage_trend.keys())
            ],
        }

    def export_bundle(self, user_id: UUID, report_ids: List[str]) -> Dict[str, Any]:
        bundle_id = str(uuid4())
        bundle_path = self._bundle_path(user_id, bundle_id)
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for report_id in report_ids:
                metadata = self._read_metadata(user_id, report_id)
                if not metadata:
                    continue
                file_path = Path(metadata["file_path"])
                if file_path.exists():
                    archive.write(file_path, arcname=file_path.name)

        return {
            "bundle_id": bundle_id,
            "download_url": f"/api/v1/reports/export-bundle/{bundle_id}/download",
        }

    def get_bundle_path(self, user_id: UUID, bundle_id: str) -> Optional[Path]:
        path = self._bundle_path(user_id, bundle_id)
        return path if path.exists() else None

    def _calculate_next_run(self, anchor: datetime, schedule_info: Dict[str, Any]) -> datetime:
        frequency = str(schedule_info.get("frequency", "weekly"))
        increment_days = {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "quarterly": 90,
        }.get(frequency, 7)
        return anchor + timedelta(days=increment_days)
