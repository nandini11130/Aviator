from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_container, get_current_user_id
from app.api.schemas import (
    RazorpayOrderOut,
    RazorpayBookingOrderRequest,
    RazorpayVerifyRequest,
    SubscribeRequest,
)
from app.config import get_settings
from app.container import Container
from app.domain.entities import BookingStatus
from app.domain.value_objects import CabinClass
from app.infrastructure.payment_gateways import RazorpayPaymentGateway

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _razorpay_gateway() -> RazorpayPaymentGateway:
    settings = get_settings()
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay checkout is not configured.",
        )
    return RazorpayPaymentGateway(
        settings.razorpay_key_id,
        settings.razorpay_key_secret,
        settings.razorpay_webhook_secret,
        settings.razorpay_callback_url,
    )


def _create_order(
    gateway: RazorpayPaymentGateway,
    *,
    amount: int,
    currency: str,
    receipt: str,
    notes: dict[str, str],
) -> RazorpayOrderOut:
    try:
        order = gateway.create_order(amount, currency, receipt, notes)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create Razorpay order.",
        ) from exc
    return RazorpayOrderOut(
        key_id=get_settings().razorpay_key_id,
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
    )


@router.post("/subscription-order", response_model=RazorpayOrderOut)
def create_subscription_order(
    request: SubscribeRequest,
    user_id: str = Depends(get_current_user_id),
) -> RazorpayOrderOut:
    settings = get_settings()
    from app.application.use_cases import ManageSubscriptionUseCase

    amount_minor = ManageSubscriptionUseCase.MEMBERSHIP_FEES_MINOR[request.tier]
    return _create_order(
        _razorpay_gateway(),
        amount=amount_minor,
        currency=settings.gst_currency,
        receipt=f"sub-{uuid.uuid4().hex}",
        notes={
            "kind": "subscription",
            "user_id": user_id,
            "tier": request.tier.value,
        },
    )


@router.post("/booking-order", response_model=RazorpayOrderOut)
def create_booking_order(
    request: RazorpayBookingOrderRequest,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> RazorpayOrderOut:
    booking = container.booking_repo.get(request.booking_id)
    if not booking or booking.user_id != user_id:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.status != BookingStatus.PENDING_PAYMENT or booking.payment_reference:
        raise HTTPException(status_code=409, detail="Booking is not awaiting payment.")

    order = _create_order(
        _razorpay_gateway(),
        amount=booking.total_amount.amount_minor,
        currency=booking.total_amount.currency,
        receipt=f"book-{uuid.uuid4().hex}",
        notes={
            "kind": "booking",
            "user_id": user_id,
            "booking_id": booking.id,
        },
    )
    booking.payment_reference = order.order_id
    container.booking_repo.save(booking)
    return order


@router.post("/verify")
def verify_payment(
    request: RazorpayVerifyRequest,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> dict[str, str]:
    if not all(
        (
            request.razorpay_order_id,
            request.razorpay_payment_id,
            request.razorpay_signature,
        )
    ):
        raise HTTPException(status_code=400, detail="Razorpay payment fields are required.")

    gateway = _razorpay_gateway()
    try:
        order = gateway.verify_order_payment(
            request.razorpay_order_id,
            request.razorpay_payment_id,
            request.razorpay_signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not verify Razorpay payment.",
        ) from exc

    notes = order.get("notes") or {}
    if notes.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Payment belongs to another user.")
    if (
        order.get("status") != "paid"
        or order.get("amount_paid") != order.get("amount")
    ):
        raise HTTPException(status_code=400, detail="Razorpay order is not fully paid.")

    kind = notes.get("kind")
    if kind == "subscription":
        try:
            tier = CabinClass(notes["tier"])
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid subscription order.") from exc

        from app.application.use_cases import ManageSubscriptionUseCase

        expected_amount = ManageSubscriptionUseCase.MEMBERSHIP_FEES_MINOR[tier]
        if (
            order.get("amount") != expected_amount
            or order.get("currency") != get_settings().gst_currency
        ):
            raise HTTPException(status_code=400, detail="Subscription order amount mismatch.")

        existing = container.subscription_repo.get_active(user_id)
        if not existing or existing.payment_reference != request.razorpay_payment_id:
            container.manage_subscription.activate(
                user_id, tier, payment_reference=request.razorpay_payment_id
            )
    elif kind == "booking":
        booking = container.booking_repo.get(notes.get("booking_id", ""))
        if not booking or booking.user_id != user_id:
            raise HTTPException(status_code=404, detail="Booking not found.")
        if (
            order.get("amount") != booking.total_amount.amount_minor
            or order.get("currency") != booking.total_amount.currency
        ):
            raise HTTPException(status_code=400, detail="Booking order amount mismatch.")
        if (
            booking.status == BookingStatus.CONFIRMED
            and booking.payment_reference == request.razorpay_payment_id
        ):
            return {"status": "verified", "kind": "booking"}
        if (
            booking.status != BookingStatus.PENDING_PAYMENT
            or booking.payment_reference != request.razorpay_order_id
        ):
            raise HTTPException(status_code=409, detail="Booking is not awaiting this payment.")
        booking.status = BookingStatus.CONFIRMED
        booking.payment_reference = request.razorpay_payment_id
        container.booking_repo.save(booking)
    else:
        raise HTTPException(status_code=400, detail="Unknown Razorpay order type.")

    return {"status": "verified", "kind": kind}
