"""Payment webhook receivers. Signature verification happens inside each
`PaymentGateway` adapter, so these routes never touch the Stripe/Razorpay
SDKs directly - they only translate HTTP <-> the normalised `WebhookEvent`
the application layer understands.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_container
from app.container import Container
from app.infrastructure.payment_gateways import RazorpayPaymentGateway, StripePaymentGateway

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post(
    "/stripe",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def stripe_webhook(
    request: Request,
    container: Container = Depends(get_container),
) -> Response:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    gateway = container.payment_gateway
    if not isinstance(gateway, StripePaymentGateway):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe is not configured on this deployment.",
        )
    try:
        event = gateway.parse_webhook_event(payload, signature)
    except Exception as exc:  # noqa: BLE001 - Stripe SDK raises several types
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook: {exc}"
        ) from exc
    container.confirm_payment.execute(event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/razorpay",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def razorpay_webhook(
    request: Request,
    container: Container = Depends(get_container),
) -> Response:
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    gateway = container.payment_gateway
    if not isinstance(gateway, RazorpayPaymentGateway):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Razorpay is not configured on this deployment.",
        )
    try:
        event = gateway.parse_webhook_event(payload, signature)
    except Exception as exc:  # noqa: BLE001 - signature/JSON errors both land here
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook: {exc}"
        ) from exc
    container.confirm_payment.execute(event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
