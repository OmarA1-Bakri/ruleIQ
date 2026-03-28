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


class TestPaymentRouterCoreFlows:
    @pytest.mark.asyncio
    async def test_create_checkout_session_appends_session_placeholder(self, monkeypatch):
        user = _make_user()
        monkeypatch.setenv("STRIPE_PROFESSIONAL_PRICE_ID", "price_pro")
        payload = payment.CheckoutSessionRequest(
            plan_id="professional",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            trial_days=14,
        )

        with (
            patch.object(payment, "_require_stripe_config", return_value=None),
            patch.object(
                payment,
                "_find_or_create_customer",
                AsyncMock(return_value={"id": "cus_owner"}),
            ),
            patch.object(
                payment,
                "_stripe_call",
                AsyncMock(return_value={"id": "cs_test", "url": "https://checkout.example"}),
            ) as stripe_call,
        ):
            result = await payment.create_checkout_session(payload, current_user=user)

        assert result == {"session_id": "cs_test", "url": "https://checkout.example"}
        assert stripe_call.await_count == 1
        assert stripe_call.await_args.kwargs["success_url"] == (
            "https://example.com/success?session_id={CHECKOUT_SESSION_ID}"
        )
        assert stripe_call.await_args.kwargs["line_items"] == [{"price": "price_pro", "quantity": 1}]
        assert stripe_call.await_args.kwargs["subscription_data"] == {
            "trial_period_days": 14,
            "metadata": {"ruleiq_user_id": str(user.id), "plan_id": "professional"},
        }

    @pytest.mark.asyncio
    async def test_get_subscription_limits_uses_enterprise_capacities(self, monkeypatch):
        user = _make_user()
        monkeypatch.setenv("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise")

        current_subscription = {
            "id": "sub_123",
            "status": "active",
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": "price_enterprise"}}]},
        }
        framework = SimpleNamespace(id=uuid4())
        framework_result = SimpleNamespace(
            scalars=lambda: SimpleNamespace(first=lambda: framework),
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=framework_result))

        with (
            patch.object(
                payment,
                "_find_or_create_customer",
                AsyncMock(return_value={"id": "cus_owner"}),
            ),
            patch.object(
                payment,
                "_get_current_subscription",
                AsyncMock(return_value=current_subscription),
            ),
            patch.object(
                payment,
                "_count_subscription_usage",
                AsyncMock(return_value={"business_profiles": 2, "frameworks": 4, "users": 1}),
            ),
        ):
            result = await payment.get_subscription_limits(current_user=user, db=db)

        assert result["plan_id"] == "enterprise"
        assert result["limits"] == {
            "business_profiles": {"current": 2, "max": 999999},
            "frameworks": {"current": 4, "max": 999999},
            "users": {"current": 1, "max": 999999},
        }
        assert result["can_upgrade"] is False


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
