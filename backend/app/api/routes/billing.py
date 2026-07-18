import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.entitlements import is_pro
from app.db.session import get_db
from app.models.user import User
from app.services.stripe_client import StripeError, create_checkout_session, verify_webhook

router = APIRouter()


@router.get("/status", response_model=dict)
def billing_status(user: Annotated[User, Depends(get_current_user)]) -> dict:
    return {
        "plan": "pro" if is_pro(user) else "free",
        "is_pro": is_pro(user),
        "billing_enabled": get_settings().billing_enabled,
    }


@router.post("/checkout", response_model=dict)
def checkout(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = get_settings()
    if not settings.billing_enabled:
        raise HTTPException(status_code=503, detail="Billing is not configured yet")
    if is_pro(user):
        raise HTTPException(status_code=409, detail="You already have Pro")
    base = settings.app_base_url.rstrip("/")
    try:
        session = create_checkout_session(
            secret_key=settings.stripe_secret_key,
            price_id=settings.stripe_price_id,
            success_url=f"{base}/pricing?upgraded=1",
            cancel_url=f"{base}/pricing",
            client_reference_id=str(user.id),
            customer_email=user.email,
            customer_id=user.stripe_customer_id,
        )
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc
    url = session.get("url")
    if not url:
        raise HTTPException(status_code=502, detail="Stripe did not return a checkout URL")
    return {"url": url}


def _period_end(obj: dict) -> datetime | None:
    end = obj.get("current_period_end")
    return datetime.fromtimestamp(end, tz=UTC) if end else None


@router.post("/webhook")
async def webhook(request: Request, db: Annotated[Session, Depends(get_db)]) -> dict:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    payload = await request.body()
    try:
        event = verify_webhook(
            payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret
        )
    except StripeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    kind = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if kind == "checkout.session.completed":
        ref = obj.get("client_reference_id")
        user = _user_by_id(db, ref)
        if user is not None:
            user.plan = "pro"
            user.plan_expires_at = None
            if obj.get("customer"):
                user.stripe_customer_id = obj["customer"]
            if obj.get("subscription"):
                user.stripe_subscription_id = obj["subscription"]
            db.commit()
    elif kind in ("customer.subscription.updated", "customer.subscription.deleted"):
        user = db.scalar(
            select(User).where(User.stripe_customer_id == obj.get("customer"))
        )
        if user is not None:
            active = kind != "customer.subscription.deleted" and obj.get("status") in (
                "active",
                "trialing",
            )
            if active and not obj.get("cancel_at_period_end"):
                user.plan = "pro"
                user.plan_expires_at = None
            else:
                # Cancelled or lapsed — keep Pro until the paid period ends.
                user.plan = "pro"
                user.plan_expires_at = _period_end(obj) or datetime.now(UTC)
            db.commit()

    return {"received": True}


def _user_by_id(db: Session, ref: str | None) -> User | None:
    if not ref:
        return None
    try:
        return db.get(User, uuid.UUID(ref))
    except (ValueError, TypeError):
        return None
