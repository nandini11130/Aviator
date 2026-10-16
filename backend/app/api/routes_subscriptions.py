from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_container, get_current_user_id
from app.api.schemas import CheckoutOut, SubscribeRequest, SubscriptionOut
from app.config import get_settings
from app.container import Container
from app.domain.entities import SubscriptionStatus

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.post("", response_model=CheckoutOut)
def start_subscription_checkout(
    request: SubscribeRequest,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> CheckoutOut:
    checkout = container.manage_subscription.start_subscription_checkout(user_id, request.tier)
    return CheckoutOut(session_id=checkout.session_id, checkout_url=checkout.url)


@router.get("/me", response_model=SubscriptionOut | None)
def get_my_subscription(
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> SubscriptionOut | None:
    subscription = container.subscription_repo.get_active(user_id)
    if not subscription:
        return None
    return SubscriptionOut(
        tier=subscription.tier,
        status=subscription.status.value,
        started_at=subscription.started_at,
        renews_at=subscription.renews_at,
    )


@router.post("/dev-activate", response_model=SubscriptionOut)
def dev_activate_subscription(
    request: SubscribeRequest,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> SubscriptionOut:
    """Local-only shortcut that activates a tier without a real payment, so
    the booking flow can be exercised end-to-end without Stripe webhooks.
    """
    settings = get_settings()
    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev-activate is disabled outside local development.",
        )
    subscription = container.manage_subscription.activate(user_id, request.tier)
    return SubscriptionOut(
        tier=subscription.tier,
        status=subscription.status.value,
        started_at=subscription.started_at,
        renews_at=subscription.renews_at,
    )
