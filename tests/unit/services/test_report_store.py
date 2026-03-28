from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.reporting import report_store as report_store_module


def _make_user():
    return SimpleNamespace(id=uuid4(), email="owner@example.com")


def _make_profile():
    profile = SimpleNamespace(id=uuid4(), company_name="Acme Ltd")
    profile.to_dict = lambda: {"id": str(profile.id), "company_name": profile.company_name}
    return profile


class TestReportStoreGeneration:
    @pytest.mark.asyncio
    async def test_generate_report_writes_pdf_metadata(self, tmp_path):
        user = _make_user()
        profile = _make_profile()
        default_framework = SimpleNamespace(id=uuid4())
        framework_result = SimpleNamespace(
            scalars=lambda: SimpleNamespace(first=lambda: default_framework),
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=framework_result))

        mock_template_manager = MagicMock()
        mock_pdf_generator = MagicMock()
        mock_generator = MagicMock()
        mock_scheduler = MagicMock()
        mock_generator.generate_report = AsyncMock(
            return_value={"sections": ["overview"], "title": "Report"}
        )
        mock_pdf_generator.generate_pdf = AsyncMock(return_value=b"pdf-bytes")

        with (
            patch.object(
                report_store_module,
                "settings",
                SimpleNamespace(report_directory=str(tmp_path)),
            ),
            patch.object(report_store_module, "TemplateManager", return_value=mock_template_manager),
            patch.object(report_store_module, "PDFGenerator", return_value=mock_pdf_generator),
            patch.object(report_store_module, "ReportGenerator", return_value=mock_generator),
            patch.object(report_store_module, "ReportScheduler", return_value=mock_scheduler),
            patch.object(
                report_store_module,
                "get_owned_business_profile",
                AsyncMock(return_value=profile),
            ),
        ):
            store = report_store_module.ReportStore(db)
            metadata = await store.generate_report(
                user,
                {
                    "business_profile_id": str(profile.id),
                    "report_type": "assessment",
                    "format": "pdf",
                    "include_sections": ["overview", "controls"],
                },
            )

        assert metadata["report_type"] == "assessment"
        assert metadata["format"] == "pdf"
        assert metadata["content_type"] == "application/pdf"
        assert metadata["framework_id"] == str(default_framework.id)
        assert metadata["file_path"].endswith(".pdf")
        assert Path(metadata["file_path"]).read_bytes() == b"pdf-bytes"
        assert store.get_report(user.id, metadata["id"]) == metadata
        assert mock_generator.generate_report.await_count == 1
        assert mock_generator.generate_report.await_args.kwargs == {
            "user_id": user.id,
            "business_profile_id": profile.id,
            "report_type": "gap_analysis",
            "parameters": {
                "framework_id": str(default_framework.id),
                "include_sections": ["overview", "controls"],
                "date_range": None,
            },
        }
        assert mock_pdf_generator.generate_pdf.await_count == 1

    def test_preview_report_uses_template_sections(self, tmp_path):
        mock_template_manager = MagicMock()
        mock_template_manager.get_template.return_value = {
            "sections": ["executive_overview", "risk_summary"]
        }

        with (
            patch.object(
                report_store_module,
                "settings",
                SimpleNamespace(report_directory=str(tmp_path)),
            ),
            patch.object(report_store_module, "TemplateManager", return_value=mock_template_manager),
            patch.object(report_store_module, "PDFGenerator", return_value=MagicMock()),
            patch.object(report_store_module, "ReportGenerator", return_value=MagicMock()),
            patch.object(report_store_module, "ReportScheduler", return_value=MagicMock()),
        ):
            store = report_store_module.ReportStore(SimpleNamespace())
            preview = store.preview_report({"report_type": "compliance"})

        sections = preview["preview"]["sections"]
        assert [section["name"] for section in sections] == ["Executive Overview", "Risk Summary"]
        assert [section["content_summary"] for section in sections] == [
            "Launch-ready executive overview section",
            "Launch-ready risk summary section",
        ]
        assert preview["preview"]["estimated_pages"] == 6
        assert preview["preview"]["estimated_generation_time"] == 20
