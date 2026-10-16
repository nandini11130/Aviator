"""Stripe-backed payment gateway, plus a zero-dependency mock used for local
development when no Stripe keys are configured. Both implement the same
`PaymentGateway` port, so swapping between them is a one-line change in the
composition root (`app/api/deps.py`). The `stripe` SDK is imported lazily so
unit tests and the mock-only local path never need it installed.
"""
from __future__ import annotations

import uuid

from app.domain.ports import CheckoutSession, PaymentGateway, WebhookEvent
from app.domain.value_objects import Money


class StripePaymentGateway(PaymentGateway):
    def __init__(self, secret_key: str, webhook_secret: str, success_url: str, cancel_url: str):
        import stripe

        self._webhook_secret = webhook_secret
        self._success_url = success_url
        self._cancel_url = cancel_url
        stripe.api_key = secret_key

    def create_checkout_session(
        self, amount: Money, description: str, metadata: dict[str, str]
    ) -> CheckoutSession:
        import stripe

        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": amount.currency.lower(),
                        "product_data": {"name": description},
                        "unit_amount": amount.amount_minor,
                    },
                    "quantity": 1,
                }
            ],
            metadata=metadata,
            success_url=self._success_url,
            cancel_url=self._cancel_url,
        )
        return CheckoutSession(session_id=session.id, url=session.url)

    def parse_webhook_event(self, payload: bytes, signature: str) -> WebhookEvent:
        import stripe

        event = stripe.Webhook.construct_event(
            payload, signature, self._webhook_secret
        )
        data = event["data"]["object"]
        return WebhookEvent(
            type=event["type"],
            payment_reference=data.get("id"),
            metadata=dict(data.get("metadata") or {}),
        )


class RazorpayPaymentGateway(PaymentGateway):
    """Razorpay-backed gateway for personal/India accounts that can't pass
    Stripe's business-entity requirements. Uses the Payment Links API (a
    hosted payment page + `short_url`, like Stripe Checkout) instead of the
    client-side Checkout.js widget, so the rest of the app's "redirect to
    checkout_url" flow needs no changes. No `razorpay` SDK needed - it's
    plain HTTP with basic auth, which keeps this adapter dependency-free
    beyond `httpx` (already required project-wide).
    """

    _API_BASE = "https://api.razorpay.com/v1"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str, callback_url: str):
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._callback_url = callback_url

    def create_checkout_session(
        self, amount: Money, description: str, metadata: dict[str, str]
    ) -> CheckoutSession:
        import httpx

        response = httpx.post(
            f"{self._API_BASE}/payment_links",
            auth=(self._key_id, self._key_secret),
            json={
                "amount": amount.amount_minor,
                "currency": amount.currency,
                "description": description,
                "notes": metadata,
                "callback_url": self._callback_url,
                "callback_method": "get",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        return CheckoutSession(session_id=payload["id"], url=payload["short_url"])

    def parse_webhook_event(self, payload: bytes, signature: str) -> WebhookEvent:
        import hashlib
        import hmac
        import json

        expected_signature = hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            raise ValueError("Invalid Razorpay webhook signature.")

        body = json.loads(payload)
        event_type = body.get("event", "")
        link_entity = body.get("payload", {}).get("payment_link", {}).get("entity", {})

        # Normalise to the same "type" string ConfirmPaymentUseCase already
        # understands, so no application-layer code needs to know which
        # payment gateway is active.
        normalised_type = (
            "checkout.session.completed" if event_type == "payment_link.paid" else event_type
        )
        return WebhookEvent(
            type=normalised_type,
            payment_reference=link_entity.get("id"),
            metadata=dict(link_entity.get("notes") or {}),
        )


class MockPaymentGateway(PaymentGateway):
    """No external calls at all - returns a fake checkout URL that the
    frontend can show in a banner during local development.
    """

    def create_checkout_session(
        self, amount: Money, description: str, metadata: dict[str, str]
    ) -> CheckoutSession:
        session_id = f"mock_{uuid.uuid4().hex[:12]}"
        fake_url = (
            "about:blank#mock-checkout"
            f"?amount={amount.amount_minor}&currency={amount.currency}"
            f"&desc={description}"
        )
        return CheckoutSession(session_id=session_id, url=fake_url)

    def parse_webhook_event(self, payload: bytes, signature: str) -> WebhookEvent:
        raise NotImplementedError(
            "MockPaymentGateway has no webhooks; use the dev-only "
            "'confirm immediately' endpoints instead."
        )
