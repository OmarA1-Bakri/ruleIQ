"""Stripe-backed payment and subscription management endpoints."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from config.logging_config import get_logger
from config.settings import settings
from database.business_profile import BusinessProfile
from database.db_setup import get_async_db
from database.generated_policy import GeneratedPolicy
from database.user import User

logger = get_logger(__name__)
router = APIRouter()


@dataclass(frozen=True)
class PlanDefinition:
    plan_id: str
    display_name: str
    price_env: str
    business_profiles: int
    frameworks: int
    users: int


PLANS: dict[str, PlanDefinition] = {
    "starter": PlanDefinition("starter", "Starter", "STRIPE_STARTER_PRICE_ID", 1, 3, 1),
    "professional": PlanDefinition("professional", "Professional", "STRIPE_PROFESSIONAL_PRICE_ID", 5, 10, 10),
    "enterprise": PlanDefinition("enterprise", "Enterprise", "STRIPE_ENTERPRISE_PRICE_ID", 999999, 999999, 999999),
}


class CheckoutSessionRequest(BaseModel):
    plan_id: str
    success_url: str
    cancel_url: str
    trial_days: int | None = 30


class PortalSessionRequest(BaseModel):
    return_url: str


class PaymentMethodAttachRequest(BaseModel):
    payment_method_id: str | None = None
    type: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class CancelSubscriptionRequest(BaseModel):
    at_period_end: bool = True


class ReactivateSubscriptionRequest(BaseModel):
    plan_id: str | None = None


class CouponApplyRequest(BaseModel):
    coupon_code: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_stripe_config() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured.",
        )
    stripe.api_key = settings.stripe_secret_key


def _resolve_price_id(plan_id: str) -> str:
    plan = PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan_id.")

    return os.getenv(plan.price_env) or os.getenv(f"NEXT_PUBLIC_{plan.price_env}") or ""


async def _stripe_call(func, *args, **kwargs):
    _require_stripe_config()
    return await asyncio.to_thread(func, *args, **kwargs)


def _subscription_plan_id(subscription: Any) -> str:
    price_id = (
        subscription.get("items", {})
        .get("data", [{}])[0]
        .get("price", {})
        .get("id")
    )
    for plan_id, definition in PLANS.items():
        resolved = os.getenv(definition.price_env) or os.getenv(f"NEXT_PUBLIC_{definition.price_env}")
        if resolved and resolved == price_id:
            return plan_id
    return "starter"


def _iso_from_unix(timestamp: int | None) -> str | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _map_subscription(subscription: Any) -> dict[str, Any]:
    customer_id = subscription.get("customer")
    return {
        "id": subscription.get("id"),
        "status": subscription.get("status"),
        "plan_id": _subscription_plan_id(subscription),
        "current_period_start": _iso_from_unix(subscription.get("current_period_start")),
        "current_period_end": _iso_from_unix(subscription.get("current_period_end")),
        "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
        "trial_end": _iso_from_unix(subscription.get("trial_end")),
        "stripe_subscription_id": subscription.get("id"),
        "stripe_customer_id": customer_id,
    }


def _map_payment_method(payment_method: Any, default_payment_method_id: str | None = None) -> dict[str, Any]:
    card = payment_method.get("card", {})
    return {
        "id": payment_method.get("id"),
        "brand": card.get("brand", "unknown"),
        "last4": card.get("last4", "0000"),
        "exp_month": card.get("exp_month", 0),
        "exp_year": card.get("exp_year", 0),
        "is_default": payment_method.get("id") == default_payment_method_id,
    }


def _map_invoice(invoice: Any) -> dict[str, Any]:
    return {
        "id": invoice.get("id"),
        "number": invoice.get("number") or invoice.get("id"),
        "amount_paid": invoice.get("amount_paid", 0),
        "amount_due": invoice.get("amount_due", 0),
        "currency": invoice.get("currency", "gbp"),
        "status": invoice.get("status", "open"),
        "created": _iso_from_unix(invoice.get("created")) or _utcnow().isoformat(),
        "due_date": _iso_from_unix(invoice.get("due_date")),
        "pdf_url": invoice.get("invoice_pdf"),
    }


def _resource_customer_id(resource: Any) -> str | None:
    customer = resource.get("customer")
    if isinstance(customer, dict):
        return customer.get("id")
    return customer


async def _find_or_create_customer(current_user: User) -> Any:
    customers = await _stripe_call(stripe.Customer.list, email=current_user.email, limit=10)
    for customer in customers.get("data", []):
        metadata = customer.get("metadata", {})
        if metadata.get("ruleiq_user_id") == str(current_user.id):
            return customer

    return await _stripe_call(
        stripe.Customer.create,
        email=current_user.email,
        metadata={"ruleiq_user_id": str(current_user.id)},
        name=getattr(current_user, "full_name", None) or current_user.email,
    )


async def _get_customer_payment_method(customer_id: str, payment_method_id: str) -> Any:
    try:
        payment_method = await _stripe_call(stripe.PaymentMethod.retrieve, payment_method_id)
    except stripe.error.InvalidRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found.",
        ) from exc

    if _resource_customer_id(payment_method) != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found.",
        )

    return payment_method


async def _get_customer_invoice(customer_id: str, invoice_id: str) -> Any:
    try:
        invoice = await _stripe_call(stripe.Invoice.retrieve, invoice_id)
    except stripe.error.InvalidRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        ) from exc

    if _resource_customer_id(invoice) != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    return invoice


async def _get_current_subscription(customer_id: str) -> Any | None:
    subscriptions = await _stripe_call(
        stripe.Subscription.list,
        customer=customer_id,
        status="all",
        limit=1,
        expand=["data.default_payment_method"],
    )
    data = subscriptions.get("data", [])
    return data[0] if data else None


async def _count_subscription_usage(db: AsyncSession, current_user: User) -> dict[str, int]:
    profile_count = (
        await db.execute(
            select(func.count(BusinessProfile.id)).where(BusinessProfile.user_id == current_user.id)
        )
    ).scalar_one()
    framework_count = (
        await db.execute(
            select(func.count(func.distinct(GeneratedPolicy.framework_id))).where(
                GeneratedPolicy.user_id == current_user.id
            )
        )
    ).scalar_one()

    return {
        "business_profiles": int(profile_count or 0),
        "frameworks": int(framework_count or 0),
        "users": 1,
    }


@router.post(
    "/create-checkout-session",
    dependencies=[Depends(validate_request)],
    summary="Create Stripe checkout session",
)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    price_id = _resolve_price_id(payload.plan_id)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Billing price for plan '{payload.plan_id}' is not configured.",
        )

    customer = await _find_or_create_customer(current_user)
    success_url = payload.success_url
    if "{CHECKOUT_SESSION_ID}" not in success_url:
        separator = "&" if "?" in success_url else "?"
        success_url = f"{success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"

    session = await _stripe_call(
        stripe.checkout.Session.create,
        mode="subscription",
        customer=customer.get("id"),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=payload.cancel_url,
        allow_promotion_codes=True,
        metadata={"ruleiq_user_id": str(current_user.id), "plan_id": payload.plan_id},
        subscription_data={
            "trial_period_days": payload.trial_days or 0,
            "metadata": {"ruleiq_user_id": str(current_user.id), "plan_id": payload.plan_id},
        },
    )
    return {"session_id": session["id"], "url": session["url"]}


@router.post(
    "/create-portal-session",
    dependencies=[Depends(validate_request)],
    summary="Create Stripe billing portal session",
)
async def create_portal_session(
    payload: PortalSessionRequest,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    customer = await _find_or_create_customer(current_user)
    session = await _stripe_call(
        stripe.billing_portal.Session.create,
        customer=customer.get("id"),
        return_url=payload.return_url,
    )
    return {"url": session["url"]}


@router.get("/subscription", dependencies=[Depends(validate_request)], summary="Get subscription")
async def get_subscription(current_user: User = Depends(get_current_active_user)) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    subscription = await _get_current_subscription(customer.get("id"))
    return {"subscription": _map_subscription(subscription) if subscription else None}


@router.post(
    "/subscription/cancel",
    dependencies=[Depends(validate_request)],
    summary="Cancel subscription",
)
async def cancel_subscription(
    payload: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    subscription = await _get_current_subscription(customer.get("id"))
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

    updated = await _stripe_call(
        stripe.Subscription.modify,
        subscription["id"],
        cancel_at_period_end=payload.at_period_end,
    )
    return _map_subscription(updated)


@router.post(
    "/subscription/reactivate",
    dependencies=[Depends(validate_request)],
    summary="Reactivate subscription",
)
async def reactivate_subscription(
    payload: ReactivateSubscriptionRequest | None = None,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    subscription = await _get_current_subscription(customer.get("id"))
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

    if subscription.get("cancel_at_period_end"):
        updated = await _stripe_call(
            stripe.Subscription.modify,
            subscription["id"],
            cancel_at_period_end=False,
        )
        return _map_subscription(updated)

    if subscription.get("status") == "canceled":
        price_id = _resolve_price_id(payload.plan_id if payload and payload.plan_id else _subscription_plan_id(subscription))
        customer_record = await _stripe_call(stripe.Customer.retrieve, customer.get("id"))
        default_payment_method = customer_record.get("invoice_settings", {}).get("default_payment_method")
        if not default_payment_method:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No default payment method available to reactivate this subscription.",
            )
        recreated = await _stripe_call(
            stripe.Subscription.create,
            customer=customer.get("id"),
            items=[{"price": price_id}],
            default_payment_method=default_payment_method,
            metadata={"ruleiq_user_id": str(current_user.id)},
        )
        return _map_subscription(recreated)

    return _map_subscription(subscription)


@router.get(
    "/payment-methods",
    dependencies=[Depends(validate_request)],
    summary="List payment methods",
)
async def list_payment_methods(
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    customer_record = await _stripe_call(stripe.Customer.retrieve, customer.get("id"))
    default_payment_method = customer_record.get("invoice_settings", {}).get("default_payment_method")
    methods = await _stripe_call(
        stripe.PaymentMethod.list,
        customer=customer.get("id"),
        type="card",
    )
    return {
        "payment_methods": [
            _map_payment_method(payment_method, default_payment_method)
            for payment_method in methods.get("data", [])
        ]
    }


@router.post(
    "/payment-methods",
    dependencies=[Depends(validate_request)],
    summary="Attach payment method",
)
async def add_payment_method(
    payload: PaymentMethodAttachRequest,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    payment_method_id = payload.payment_method_id or payload.details.get("payment_method_id")
    if not payment_method_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payment_method_id is required.",
        )

    customer = await _find_or_create_customer(current_user)
    payment_method = await _stripe_call(
        stripe.PaymentMethod.attach,
        payment_method_id,
        customer=customer.get("id"),
    )
    if payload.is_default:
        await _stripe_call(
            stripe.Customer.modify,
            customer.get("id"),
            invoice_settings={"default_payment_method": payment_method_id},
        )
    return _map_payment_method(payment_method, payment_method_id if payload.is_default else None)


@router.delete(
    "/payment-methods/{payment_method_id}",
    dependencies=[Depends(validate_request)],
    summary="Detach payment method",
)
async def remove_payment_method(
    payment_method_id: str,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    customer = await _find_or_create_customer(current_user)
    await _get_customer_payment_method(customer.get("id"), payment_method_id)
    await _stripe_call(stripe.PaymentMethod.detach, payment_method_id)
    return {"message": "Payment method removed."}


@router.post(
    "/payment-methods/{payment_method_id}/default",
    dependencies=[Depends(validate_request)],
    summary="Set default payment method",
)
async def set_default_payment_method(
    payment_method_id: str,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    payment_method = await _get_customer_payment_method(customer.get("id"), payment_method_id)
    await _stripe_call(
        stripe.Customer.modify,
        customer.get("id"),
        invoice_settings={"default_payment_method": payment_method_id},
    )
    return _map_payment_method(payment_method, payment_method_id)


@router.get("/invoices", dependencies=[Depends(validate_request)], summary="List invoices")
async def get_invoices(
    limit: int = 10,
    starting_after: str | None = None,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    invoices = await _stripe_call(
        stripe.Invoice.list,
        customer=customer.get("id"),
        limit=limit,
        starting_after=starting_after,
    )
    return {"invoices": [_map_invoice(invoice) for invoice in invoices.get("data", [])]}


@router.get(
    "/invoices/{invoice_id}/download",
    dependencies=[Depends(validate_request)],
    summary="Download invoice",
)
async def download_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
):
    customer = await _find_or_create_customer(current_user)
    invoice = await _get_customer_invoice(customer.get("id"), invoice_id)
    destination = invoice.get("invoice_pdf") or invoice.get("hosted_invoice_url")
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice download is not available.",
        )
    return RedirectResponse(destination)


@router.get(
    "/invoices/upcoming",
    dependencies=[Depends(validate_request)],
    summary="Get upcoming invoice",
)
async def get_upcoming_invoice(
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    try:
        invoice = await _stripe_call(stripe.Invoice.upcoming, customer=customer.get("id"))
    except stripe.error.InvalidRequestError:
        return {"invoice": None}
    return {"invoice": _map_invoice(invoice)}


@router.post(
    "/coupons/apply",
    dependencies=[Depends(validate_request)],
    summary="Validate coupon",
)
async def apply_coupon(
    payload: CouponApplyRequest,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    _ = current_user
    promotion_codes = await _stripe_call(
        stripe.PromotionCode.list, code=payload.coupon_code, active=True, limit=1
    )
    code = (promotion_codes.get("data") or [None])[0]
    if code:
        coupon = code.get("coupon", {})
        return {
            "success": True,
            "discount": {
                "percent_off": coupon.get("percent_off"),
                "amount_off": coupon.get("amount_off"),
                "duration": coupon.get("duration"),
                "duration_in_months": coupon.get("duration_in_months"),
            },
        }

    try:
        coupon = await _stripe_call(stripe.Coupon.retrieve, payload.coupon_code)
    except stripe.error.InvalidRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired coupon code.",
        ) from exc

    return {
        "success": True,
        "discount": {
            "percent_off": coupon.get("percent_off"),
            "amount_off": coupon.get("amount_off"),
            "duration": coupon.get("duration"),
            "duration_in_months": coupon.get("duration_in_months"),
        },
    }


@router.get(
    "/subscription/limits",
    dependencies=[Depends(validate_request)],
    summary="Get subscription limits",
)
async def get_subscription_limits(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    customer = await _find_or_create_customer(current_user)
    subscription = await _get_current_subscription(customer.get("id"))
    plan_id = _subscription_plan_id(subscription) if subscription else "starter"
    plan = PLANS[plan_id]
    usage = await _count_subscription_usage(db, current_user)
    return {
        "plan_id": plan_id,
        "limits": {
            "business_profiles": {"current": usage["business_profiles"], "max": plan.business_profiles},
            "frameworks": {"current": usage["frameworks"], "max": plan.frameworks},
            "users": {"current": usage["users"], "max": plan.users},
        },
        "can_upgrade": plan_id != "enterprise",
    }
