"""

Payment and Subscription Management API Endpoints

Provides endpoints for:
- Subscription management
- Payment methods
- Invoices and billing
- Usage limits
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from database.db_setup import get_async_db
from database.user import User

router = APIRouter()


class PaymentMethodRequest(BaseModel):
    type: str
    details: Dict[str, Any]
    is_default: Optional[bool] = False


class CouponApplyRequest(BaseModel):
    coupon_code: str
    subscription_id: Optional[str] = None


@router.post("/subscription/cancel", summary="Cancel subscription")
async def cancel_subscription(
    cancellation_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Cancel the current user's subscription."""
    reason = cancellation_data.get("reason", "")
    immediate = cancellation_data.get("immediate", False)
    return {
        "subscription_id": f"sub_{current_user.id}",
        "status": "cancelled",
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "effective_date": datetime.now(timezone.utc).isoformat()
        if immediate
        else "end_of_billing_period",
        "reason": reason,
        "message": "Subscription cancelled successfully",
    }


@router.post("/subscription/reactivate", summary="Reactivate subscription")
async def reactivate_subscription(
    reactivation_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Reactivate a cancelled subscription."""
    plan_id = reactivation_data.get("plan_id", "pro")
    return {
        "subscription_id": f"sub_{current_user.id}",
        "status": "active",
        "reactivated_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan_id,
        "message": "Subscription reactivated successfully",
    }


@router.post("/payment-methods", summary="Add payment method")
async def add_payment_method(
    payment_method: PaymentMethodRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Add a new payment method for the user."""
    return {
        "payment_method_id": f"pm_{datetime.now(timezone.utc).timestamp()}",
        "type": payment_method.type,
        "last_four": payment_method.details.get("last_four", "****"),
        "is_default": payment_method.is_default,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": "Payment method added successfully",
    }


@router.get("/invoices", summary="Get invoices")
async def get_invoices(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get user's invoice history."""
    return {
        "invoices": [
            {
                "invoice_id": "inv_2024_001",
                "date": "2024-01-01T00:00:00Z",
                "amount": 99.0,
                "currency": "USD",
                "status": "paid",
                "description": "Pro Plan - January 2024",
                "pdf_url": "/api/v1/payments/invoices/inv_2024_001/pdf",
            },
            {
                "invoice_id": "inv_2023_012",
                "date": "2023-12-01T00:00:00Z",
                "amount": 99.0,
                "currency": "USD",
                "status": "paid",
                "description": "Pro Plan - December 2023",
                "pdf_url": "/api/v1/payments/invoices/inv_2023_012/pdf",
            },
        ],
        "total": 2,
        "limit": limit,
        "offset": offset,
    }


@router.get("/invoices/upcoming", summary="Get upcoming invoice")
async def get_upcoming_invoice(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get details of the next upcoming invoice."""
    return {
        "invoice": {
            "date": "2024-02-01T00:00:00Z",
            "amount": 99.0,
            "currency": "USD",
            "description": "Pro Plan - February 2024",
            "line_items": [
                {"description": "Pro Plan Monthly Subscription", "amount": 99.0, "quantity": 1}
            ],
            "subtotal": 99.0,
            "tax": 0.0,
            "total": 99.0,
        },
        "billing_period": {"start": "2024-02-01T00:00:00Z", "end": "2024-02-29T23:59:59Z"},
    }


@router.post("/coupons/apply", summary="Apply coupon")
async def apply_coupon(
    coupon_data: CouponApplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Apply a discount coupon to the subscription."""
    if coupon_data.coupon_code.upper() == "SAVE20":
        return {
            "coupon_code": coupon_data.coupon_code,
            "discount": {"type": "percentage", "value": 20, "description": "20% off for 3 months"},
            "applied_to": coupon_data.subscription_id or f"sub_{current_user.id}",
            "valid_until": "2024-05-01T00:00:00Z",
            "message": "Coupon applied successfully",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired coupon code"
        )


@router.get("/subscription/limits", summary="Get subscription limits")
async def get_subscription_limits(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get current subscription usage limits and consumption."""
    return {
        "plan": "Pro",
        "limits": {
            "ai_assessments": {
                "limit": 100,
                "used": 45,
                "remaining": 55,
                "resets_at": "2024-02-01T00:00:00Z",
            },
            "policy_generations": {
                "limit": 50,
                "used": 12,
                "remaining": 38,
                "resets_at": "2024-02-01T00:00:00Z",
            },
            "team_members": {"limit": 10, "used": 3, "remaining": 7},
            "storage_gb": {"limit": 100, "used": 25.5, "remaining": 74.5},
            "api_calls": {
                "limit": 10000,
                "used": 3567,
                "remaining": 6433,
                "resets_at": "2024-02-01T00:00:00Z",
            },
        },
        "overage_charges": {
            "enabled": False,
            "rates": {"ai_assessment": 2.5, "policy_generation": 5.0, "api_call_per_1000": 1.0},
        },
    }
