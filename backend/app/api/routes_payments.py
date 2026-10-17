from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_container, get_current_user_id
from app.api.schemas import (
    BookingPaymentOrderOut,
    CreateBookingRequest,
    DemoPassOut,
    RazorpayOrderOut,
    RazorpayVerifyRequest,
    SubscribeRequest,
)
from app.config import get_settings
from app.container import Container
from app.domain.entities import BookingStatus, DemoPass
from app.domain.value_objects import CabinClass
from app.infrastructure.payment_gateways import RazorpayPaymentGateway

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)
DEMO_PASS_AMOUNT_MINOR = 100


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
    except httpx.HTTPStatusError as exc:
        response = exc.response
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        error_code = error.get("code") or "UPSTREAM_ERROR"
        logger.error(
            "Razorpay rejected order creation (status=%s, code=%s, description=%s)",
            response.status_code,
            error_code,
            error.get("description", "No description returned."),
        )
        if response.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Razorpay rejected this server's request. Verify the key pair "
                    "and check whether the Razorpay account restricts API access by IP."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Razorpay rejected order creation ({error_code}).",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Could not reach Razorpay while creating an order.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Razorpay to create an order.",
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


@router.get("/demo-pass", response_model=DemoPassOut)
def get_demo_pass(
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> DemoPassOut:
    demo_pass = container.demo_pass_repo.get(user_id)
    return DemoPassOut(
        active=demo_pass is not None,
        purchased_at=demo_pass.purchased_at if demo_pass else None,
    )


@router.post("/demo-pass-order", response_model=RazorpayOrderOut)
def create_demo_pass_order(
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> RazorpayOrderOut:
    if container.demo_pass_repo.get(user_id):
        raise HTTPException(status_code=409, detail="Your demo pass is already active.")
    return _create_order(
        _razorpay_gateway(),
        amount=DEMO_PASS_AMOUNT_MINOR,
        currency="INR",
        receipt=f"demo-{uuid.uuid4().hex}",
        notes={"kind": "demo_pass", "user_id": user_id},
    )


@router.post("/dev-demo-pass", response_model=DemoPassOut)
def activate_local_demo_pass(
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> DemoPassOut:
    if not get_settings().is_local:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local demo pass activation is disabled outside development.",
        )
    demo_pass = container.demo_pass_repo.get(user_id)
    if demo_pass is None:
        demo_pass = DemoPass(
            user_id=user_id,
            payment_reference=f"local-test-{uuid.uuid4().hex}",
            purchased_at=datetime.now(timezone.utc),
        )
        container.demo_pass_repo.save(demo_pass)
    return DemoPassOut(active=True, purchased_at=demo_pass.purchased_at)


@router.post("/booking-order", response_model=BookingPaymentOrderOut)
def create_booking_order(
    request: CreateBookingRequest,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> BookingPaymentOrderOut:
    from app.application.use_cases import SeatUnavailableError, SubscriptionRequiredError

    gateway = _razorpay_gateway()
    try:
        booking = container.create_booking.execute(
            user_id=user_id,
            flight_id=request.flight_id,
            cabin_class=request.cabin_class,
            create_checkout=False,
            demo=True,
        )
    except SubscriptionRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SeatUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    booking.status = BookingStatus.DEMO_PENDING_PAYMENT
    container.booking_repo.save(booking)
    order = _create_order(
        gateway,
        amount=booking.total_amount.amount_minor,
        currency=booking.total_amount.currency,
        receipt=f"book-{uuid.uuid4().hex}",
        notes={
            "kind": "booking",
            "user_id": user_id,
            "booking_id": booking.id,
            "flight_id": booking.flight_id,
            "cabin_class": booking.cabin_class.value,
        },
    )
    booking.payment_reference = order.order_id
    container.booking_repo.save(booking)
    return BookingPaymentOrderOut(
        **order.model_dump(),
        booking_id=booking.id,
        estimated_total=booking.total_amount.to_dict(),
        demo_only=True,
    )


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
            booking.status == BookingStatus.DEMO_PAID
            and booking.payment_reference == request.razorpay_payment_id
        ):
            return {"status": "verified", "kind": "booking"}
        if (
            booking.status != BookingStatus.DEMO_PENDING_PAYMENT
            or booking.payment_reference != request.razorpay_order_id
        ):
            raise HTTPException(status_code=409, detail="Booking is not awaiting this payment.")
        booking.status = BookingStatus.DEMO_PAID
        booking.payment_reference = request.razorpay_payment_id
        container.booking_repo.save(booking)
    elif kind == "demo_pass":
        if (
            order.get("amount") != DEMO_PASS_AMOUNT_MINOR
            or order.get("currency") != "INR"
        ):
            raise HTTPException(status_code=400, detail="Demo pass order amount mismatch.")
        if container.demo_pass_repo.get(user_id) is None:
            container.demo_pass_repo.save(
                DemoPass(
                    user_id=user_id,
                    payment_reference=request.razorpay_payment_id,
                    purchased_at=datetime.now(timezone.utc),
                )
            )
    else:
        raise HTTPException(status_code=400, detail="Unknown Razorpay order type.")

    return {"status": "verified", "kind": kind}
