import hashlib
import hmac

import httpx
import pytest

from app.infrastructure.payment_gateways import RazorpayPaymentGateway


def test_create_order_rejects_amount_below_razorpay_minimum():
    gateway = RazorpayPaymentGateway("key", "secret", "", "")

    with pytest.raises(ValueError, match="at least 100 paise"):
        gateway.create_order(99, "INR", "receipt", {})


def test_verify_order_payment_checks_signature_and_paid_order(monkeypatch):
    key_secret = "test-secret"
    order_id = "order_123"
    payment_id = "pay_456"
    signature = hmac.new(
        key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    expected_order = {
        "id": order_id,
        "amount": 49900,
        "amount_paid": 49900,
        "status": "paid",
        "notes": {"kind": "subscription"},
    }
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200,
            json=expected_order,
            request=httpx.Request("GET", "https://api.razorpay.com/v1/orders/order_123"),
        ),
    )
    gateway = RazorpayPaymentGateway("key", key_secret, "", "")

    assert gateway.verify_order_payment(order_id, payment_id, signature) == expected_order


def test_verify_order_payment_rejects_invalid_signature(monkeypatch):
    gateway = RazorpayPaymentGateway("key", "secret", "", "")
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: pytest.fail("Razorpay order must not be fetched."),
    )

    with pytest.raises(ValueError, match="Invalid Razorpay payment signature"):
        gateway.verify_order_payment("order_123", "pay_456", "invalid")
