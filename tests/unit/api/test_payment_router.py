import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from api.routers import payment
from services.reporting.report_store import ReportStore


def _make_user():
    return SimpleNamespace(id=uuid4(), email="owner@example.com", full_name="Owner")


class TestPaymentRouterOwnership:
    @pytest.mark.asyncio
    async def test_remove_payment_method_rejects_unowned_method(self):
        user = _make_user()

        with (
            patch.object(
                payment,
                "_find_or_create_customer",
                AsyncMock(return_value={"id": "cus_owner"}),
            ),
            patch.object(
                payment,
                "_stripe_call",
                AsyncMock(return_value={"id": "pm_123", "customer": "cus_other"}),
            ) as stripe_call,
        ):
            with pytest.raises(HTTPException, match="Payment method not found"):
                await payment.remove_payment_method("pm_123", current_user=user)

        assert stripe_call.await_count == 1

    @pytest.mark.asyncio
    async def test_set_default_payment_method_requires_owned_method(self):
        user = _make_user()
        payment_method = {
            "id": "pm_123",
            "customer": "cus_owner",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 1, "exp_year": 2030},
        }

        with (
            patch.object(
                payment,
                "_find_or_create_customer",
                AsyncMock(return_value={"id": "cus_owner"}),
            ),
            patch.object(
                payment,
                "_stripe_call",
                AsyncMock(side_effect=[payment_method, {"id": "cus_owner"}]),
            ) as stripe_call,
        ):
            result = await payment.set_default_payment_method("pm_123", current_user=user)

        assert result["id"] == "pm_123"
        assert result["is_default"] is True
        assert stripe_call.await_count == 2
        assert stripe_call.await_args_list[1].args[1] == "cus_owner"
        assert stripe_call.await_args_list[1].kwargs["invoice_settings"] == {
            "default_payment_method": "pm_123"
        }

    @pytest.mark.asyncio
    async def test_download_invoice_rejects_unowned_invoice(self):
        user = _make_user()

        with (
            patch.object(
                payment,
                "_find_or_create_customer",
                AsyncMock(return_value={"id": "cus_owner"}),
            ),
            patch.object(
                payment,
                "_stripe_call",
                AsyncMock(return_value={"id": "in_123", "customer": "cus_other"}),
            ) as stripe_call,
        ):
            with pytest.raises(HTTPException, match="Invoice not found"):
                await payment.download_invoice("in_123", current_user=user)

        assert stripe_call.await_count == 1


class TestReportStoreAnalytics:
    def test_build_analytics_filters_by_day_window(self):
        store = object.__new__(ReportStore)
        now = datetime.now(timezone.utc)
        recent_report = {
            "created_at": now.isoformat(),
            "report_type": "compliance",
            "format": "pdf",
        }
        old_report = {
            "created_at": (now - timedelta(days=45)).isoformat(),
            "report_type": "audit",
            "format": "csv",
        }
        store.list_reports = lambda user_id, page=1, page_size=1000: {
            "items": [recent_report, old_report]
        }

        analytics = ReportStore.build_analytics(store, uuid4(), days=30)

        assert analytics["total_reports_generated"] == 1
        assert analytics["by_type"] == {"compliance": 1}
        assert analytics["by_format"] == {"pdf": 1}
