"""Tests for api.schemas.reporting — enums, Pydantic models, validators."""
import pytest
from datetime import date, datetime
from uuid import uuid4

from api.schemas.reporting import (
    ReportFormat,
    ReportType,
    ReportFrequency,
    ReportParameters,
    ScheduleConfig,
    GenerateReportRequest,
    ReportResponse,
    CreateScheduleRequest,
    ScheduleResponse,
    UpdateScheduleRequest,
    ScheduleListResponse,
    ReportHistoryItem,
    ReportHistoryResponse,
    ReportStatsResponse,
    ExecuteScheduleResponse,
)


# ── Enums ────────────────────────────────────────────────────────

class TestReportingEnums:
    def test_report_format(self):
        assert ReportFormat.PDF is not None
        assert ReportFormat.JSON is not None
        assert ReportFormat.HTML is not None
        assert ReportFormat.CSV is not None
        assert len(ReportFormat) == 4

    def test_report_type(self):
        assert ReportType.EXECUTIVE_SUMMARY is not None
        assert ReportType.GAP_ANALYSIS is not None
        assert ReportType.EVIDENCE_REPORT is not None
        assert ReportType.AUDIT_READINESS is not None
        assert ReportType.COMPLIANCE_STATUS is not None
        assert ReportType.CONTROL_MATRIX is not None
        assert ReportType.RISK_ASSESSMENT is not None
        assert len(ReportType) == 7

    def test_report_frequency(self):
        assert ReportFrequency.DAILY is not None
        assert ReportFrequency.WEEKLY is not None
        assert ReportFrequency.MONTHLY is not None
        assert ReportFrequency.CUSTOM is not None
        assert len(ReportFrequency) == 4


# ── ReportParameters ────────────────────────────────────────────

class TestReportParameters:
    def test_defaults(self):
        r = ReportParameters()
        assert r.frameworks is None
        assert r.start_date is None
        assert r.end_date is None
        assert r.include_evidence is False

    def test_valid_date_range(self):
        r = ReportParameters(
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        )
        assert r.start_date == date(2024, 1, 1)

    def test_invalid_date_range(self):
        with pytest.raises(Exception):
            ReportParameters(
                start_date=date(2024, 12, 31), end_date=date(2024, 1, 1),
            )

    def test_same_date(self):
        r = ReportParameters(start_date=date(2024, 6, 1), end_date=date(2024, 6, 1))
        assert r.start_date == r.end_date


# ── ScheduleConfig ──────────────────────────────────────────────

class TestScheduleConfig:
    def test_defaults(self):
        r = ScheduleConfig()
        assert r.day_of_week is None
        assert r.time_of_day == "09:00"
        assert r.cron_expression is None

    def test_day_of_week_range(self):
        r = ScheduleConfig(day_of_week=0)
        assert r.day_of_week == 0
        r = ScheduleConfig(day_of_week=6)
        assert r.day_of_week == 6

    def test_day_of_week_out_of_range(self):
        with pytest.raises(Exception):
            ScheduleConfig(day_of_week=7)

    def test_day_of_month_range(self):
        ScheduleConfig(day_of_month=1)
        ScheduleConfig(day_of_month=31)

    def test_day_of_month_out_of_range(self):
        with pytest.raises(Exception):
            ScheduleConfig(day_of_month=0)
        with pytest.raises(Exception):
            ScheduleConfig(day_of_month=32)


# ── GenerateReportRequest ───────────────────────────────────────

class TestGenerateReportRequest:
    def test_valid(self):
        r = GenerateReportRequest(
            business_profile_id=uuid4(),
            report_type=ReportType.EXECUTIVE_SUMMARY,
        )
        assert r.format == ReportFormat.PDF


# ── ReportResponse ──────────────────────────────────────────────

class TestReportResponse:
    def test_valid(self):
        r = ReportResponse(
            report_id="r1", report_type=ReportType.GAP_ANALYSIS,
            format=ReportFormat.JSON, content={"data": "test"},
            content_type="application/json", generated_at=datetime.now(),
        )
        assert r.size_bytes is None

    def test_string_content(self):
        r = ReportResponse(
            report_id="r2", report_type=ReportType.EVIDENCE_REPORT,
            format=ReportFormat.HTML, content="<html></html>",
            content_type="text/html", generated_at=datetime.now(),
        )
        assert isinstance(r.content, str)


# ── CreateScheduleRequest ───────────────────────────────────────

class TestCreateScheduleRequest:
    def test_valid(self):
        r = CreateScheduleRequest(
            business_profile_id=uuid4(),
            report_type=ReportType.COMPLIANCE_STATUS,
            format=ReportFormat.PDF,
            frequency=ReportFrequency.WEEKLY,
            recipients=["test@example.com"],
        )
        assert len(r.recipients) == 1

    def test_invalid_email(self):
        with pytest.raises(Exception):
            CreateScheduleRequest(
                business_profile_id=uuid4(),
                report_type=ReportType.COMPLIANCE_STATUS,
                format=ReportFormat.PDF,
                frequency=ReportFrequency.WEEKLY,
                recipients=["not-an-email"],
            )


# ── ScheduleResponse ────────────────────────────────────────────

class TestScheduleResponse:
    def test_valid(self):
        now = datetime.now()
        r = ScheduleResponse(
            id=uuid4(), business_profile_id=uuid4(),
            report_type=ReportType.AUDIT_READINESS,
            format=ReportFormat.PDF,
            frequency=ReportFrequency.MONTHLY,
            recipients=["a@b.com"],
            parameters=ReportParameters(),
            schedule_config=ScheduleConfig(),
            active=True, created_at=now, updated_at=now,
        )
        assert r.last_execution is None
        assert r.next_execution is None


# ── UpdateScheduleRequest ───────────────────────────────────────

class TestUpdateScheduleRequest:
    def test_all_none(self):
        r = UpdateScheduleRequest()
        assert r.frequency is None
        assert r.recipients is None
        assert r.active is None

    def test_valid_email_update(self):
        r = UpdateScheduleRequest(recipients=["new@example.com"])
        assert r.recipients == ["new@example.com"]

    def test_invalid_email_update(self):
        with pytest.raises(Exception):
            UpdateScheduleRequest(recipients=["bad"])


# ── List & History ──────────────────────────────────────────────

class TestListAndHistory:
    def test_schedule_list(self):
        r = ScheduleListResponse(schedules=[], total=0)
        assert r.total == 0

    def test_report_history_item(self):
        r = ReportHistoryItem(
            report_id="r1", report_type=ReportType.RISK_ASSESSMENT,
            format=ReportFormat.CSV, generated_at=datetime.now(),
            status="completed",
        )
        assert r.size_bytes is None
        assert r.download_url is None

    def test_report_history_response(self):
        r = ReportHistoryResponse(reports=[], total=0, page=1, per_page=10)
        assert r.page == 1


# ── ReportStatsResponse ─────────────────────────────────────────

class TestReportStatsResponse:
    def test_valid(self):
        r = ReportStatsResponse(
            total_reports_generated=100, reports_this_month=15,
            active_schedules=5, most_popular_report_type="COMPLIANCE_STATUS",
            total_recipients=25, success_rate=0.95,
            by_report_type={"COMPLIANCE_STATUS": 40},
            by_frequency={"WEEKLY": 3},
        )
        assert r.total_reports_generated == 100


# ── ExecuteScheduleResponse ─────────────────────────────────────

class TestExecuteScheduleResponse:
    def test_valid(self):
        r = ExecuteScheduleResponse(
            status="queued", schedule_id="s1",
            executed_at=datetime.now(),
        )
        assert r.task_id is None
        assert r.message is None
