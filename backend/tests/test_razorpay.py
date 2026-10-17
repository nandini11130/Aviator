import hashlib
import hmac
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.api.routes_payments import (
    _create_order,
    activate_local_demo_pass,
    create_booking_order,
    create_demo_pass_order,
    verify_payment,
)
from app.api.routes_bookings import create_booking, dev_confirm_booking
from app.api.schemas import CreateBookingRequest, RazorpayOrderOut, RazorpayVerifyRequest
from app.application.use_cases import CreateBookingUseCase, ManageSubscriptionUseCase
from app.domain.entities import BookingStatus, DemoPass
from app.domain.value_objects import CabinClass
from app.infrastructure.flight_data_providers import MockFlightDataProvider
from app.infrastructure.memory_repositories import (
    InMemoryBookingRepository,
    InMemoryDemoPassRepository,
    InMemoryFlightRepository,
    InMemorySubscriptionRepository,
)
from app.infrastructure.payment_gateways import RazorpayPaymentGateway
from app.infrastructure.tax_calculators import IndiaGstCalculator
from app.infrastructure.payment_gateways import MockPaymentGateway


@pytest.mark.parametrize("endpoint", [create_booking, dev_confirm_booking])
def test_free_booking_endpoints_are_gone(endpoint):
    with pytest.raises(HTTPException) as raised:
        endpoint()

    assert raised.value.status_code == 410


@pytest.mark.parametrize(
    ("upstream_status", "expected_status"),
    [(401, 401), (400, 502)],
)
def test_create_order_reports_razorpay_http_errors(upstream_status, expected_status):
    request = httpx.Request("POST", "https://api.razorpay.com/v1/orders")
    response = httpx.Response(
        upstream_status,
        json={"error": {"code": "BAD_REQUEST_ERROR", "description": "Invalid request."}},
        request=request,
    )
    gateway = RazorpayPaymentGateway("key", "secret", "", "")
    gateway.create_order = lambda *args: response.raise_for_status()

    with pytest.raises(HTTPException) as raised:
        _create_order(
            gateway,
            amount=49900,
            currency="INR",
            receipt="sub-test",
            notes={"kind": "subscription"},
        )

    assert raised.value.status_code == expected_status


def test_create_order_rejects_amount_below_razorpay_minimum():
    gateway = RazorpayPaymentGateway("key", "secret", "", "")

    with pytest.raises(ValueError, match="at least 100 paise"):
        gateway.create_order(99, "INR", "receipt", {})


def booking_payment_fixture():
    flight_repo = InMemoryFlightRepository(MockFlightDataProvider(seed=24))
    booking_repo = InMemoryBookingRepository()
    subscription_repo = InMemorySubscriptionRepository()
    demo_pass_repo = InMemoryDemoPassRepository()
    gateway = MockPaymentGateway()
    tax_calculator = IndiaGstCalculator()
    manage_subscription = ManageSubscriptionUseCase(subscription_repo, gateway, "INR")
    manage_subscription.activate("user-1", CabinClass.ECONOMY)
    use_case = CreateBookingUseCase(
        flight_repo,
        booking_repo,
        subscription_repo,
        tax_calculator,
        gateway,
        demo_pass_repo,
    )
    deal = flight_repo.list_empty_seat_deals(CabinClass.ECONOMY)[0][0]
    container = SimpleNamespace(
        create_booking=use_case,
        booking_repo=booking_repo,
        subscription_repo=subscription_repo,
        demo_pass_repo=demo_pass_repo,
    )
    return container, flight_repo, deal


def test_booking_order_uses_server_estimated_total_and_demo_status(monkeypatch):
    captured = {}
    container, flight_repo, deal = booking_payment_fixture()
    inventory_before = flight_repo.get_seat_inventory(deal.id, CabinClass.ECONOMY).empty_seats

    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", lambda: object())

    def create_order(gateway, **kwargs):
        captured.update(kwargs)
        return RazorpayOrderOut(
            key_id="rzp_test_key",
            order_id="order_booking",
            amount=kwargs["amount"],
            currency=kwargs["currency"],
        )

    monkeypatch.setattr("app.api.routes_payments._create_order", create_order)
    response = create_booking_order(
        CreateBookingRequest(flight_id=deal.id, cabin_class=CabinClass.ECONOMY),
        "user-1",
        container,
    )

    booking = container.booking_repo.get(response.booking_id)
    assert response.demo_only is True
    assert response.amount == booking.total_amount.amount_minor
    assert response.currency == "INR"
    assert response.estimated_total.amount_minor == booking.total_amount.amount_minor
    assert captured["notes"]["booking_id"] == booking.id
    assert captured["notes"]["user_id"] == "user-1"
    assert booking.status == BookingStatus.DEMO_PENDING_PAYMENT
    assert booking.payment_reference == "order_booking"
    assert (
        flight_repo.get_seat_inventory(deal.id, CabinClass.ECONOMY).empty_seats
        == inventory_before
    )


def test_booking_payment_verification_marks_demo_paid_without_ticket(monkeypatch):
    container, _, deal = booking_payment_fixture()
    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", lambda: object())
    monkeypatch.setattr(
        "app.api.routes_payments._create_order",
        lambda gateway, **kwargs: RazorpayOrderOut(
            key_id="rzp_test_key",
            order_id="order_booking",
            amount=kwargs["amount"],
            currency=kwargs["currency"],
        ),
    )
    pending = create_booking_order(
        CreateBookingRequest(flight_id=deal.id, cabin_class=CabinClass.ECONOMY),
        "user-1",
        container,
    )
    booking = container.booking_repo.get(pending.booking_id)
    payment_id = "pay_demo_booking"

    class Gateway:
        def verify_order_payment(self, order_id, verified_payment_id, signature):
            assert order_id == "order_booking"
            assert verified_payment_id == payment_id
            return {
                "amount": booking.total_amount.amount_minor,
                "amount_paid": booking.total_amount.amount_minor,
                "currency": "INR",
                "status": "paid",
                "notes": {
                    "kind": "booking",
                    "user_id": "user-1",
                    "booking_id": booking.id,
                },
            }

    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", Gateway)
    result = verify_payment(
        RazorpayVerifyRequest(
            razorpay_order_id="order_booking",
            razorpay_payment_id=payment_id,
            razorpay_signature="valid",
        ),
        "user-1",
        container,
    )

    paid_booking = container.booking_repo.get(booking.id)
    assert result == {"status": "verified", "kind": "booking"}
    assert paid_booking.status == BookingStatus.DEMO_PAID
    assert paid_booking.payment_reference == payment_id


def test_booking_payment_verification_rejects_wrong_paid_amount(monkeypatch):
    container, _, deal = booking_payment_fixture()
    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", lambda: object())
    monkeypatch.setattr(
        "app.api.routes_payments._create_order",
        lambda gateway, **kwargs: RazorpayOrderOut(
            key_id="rzp_test_key",
            order_id="order_booking",
            amount=kwargs["amount"],
            currency=kwargs["currency"],
        ),
    )
    pending = create_booking_order(
        CreateBookingRequest(flight_id=deal.id, cabin_class=CabinClass.ECONOMY),
        "user-1",
        container,
    )
    booking = container.booking_repo.get(pending.booking_id)

    class Gateway:
        def verify_order_payment(self, order_id, payment_id, signature):
            return {
                "amount": booking.total_amount.amount_minor + 100,
                "amount_paid": booking.total_amount.amount_minor + 100,
                "currency": "INR",
                "status": "paid",
                "notes": {
                    "kind": "booking",
                    "user_id": "user-1",
                    "booking_id": booking.id,
                },
            }

    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", Gateway)
    with pytest.raises(HTTPException) as raised:
        verify_payment(
            RazorpayVerifyRequest(
                razorpay_order_id="order_booking",
                razorpay_payment_id="pay_wrong_amount",
                razorpay_signature="valid",
            ),
            "user-1",
            container,
        )

    assert raised.value.status_code == 400
    assert container.booking_repo.get(booking.id).status == BookingStatus.DEMO_PENDING_PAYMENT


def test_demo_pass_order_is_exactly_one_inr_and_one_time(monkeypatch):
    captured = {}

    class Gateway:
        def create_order(self, amount, currency, receipt, notes):
            captured.update(amount=amount, currency=currency, notes=notes)
            return {"id": "order_demo", "amount": amount, "currency": currency}

    class DemoPassRepo:
        def get(self, user_id):
            return None

    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", Gateway)
    monkeypatch.setattr(
        "app.api.routes_payments.get_settings",
        lambda: SimpleNamespace(razorpay_key_id="rzp_test_key"),
    )

    order = create_demo_pass_order("user-1", SimpleNamespace(demo_pass_repo=DemoPassRepo()))

    assert order.amount == 100
    assert order.currency == "INR"
    assert captured == {
        "amount": 100,
        "currency": "INR",
        "notes": {"kind": "demo_pass", "user_id": "user-1"},
    }


def test_demo_pass_order_cannot_be_purchased_twice():
    repo = InMemoryDemoPassRepository()
    repo.save(
        DemoPass(
            user_id="user-1",
            payment_reference="pay_demo",
            purchased_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(HTTPException) as raised:
        create_demo_pass_order("user-1", SimpleNamespace(demo_pass_repo=repo))

    assert raised.value.status_code == 409


def test_local_demo_pass_activation_is_development_only(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_payments.get_settings",
        lambda: SimpleNamespace(is_local=True),
    )
    repo = InMemoryDemoPassRepository()
    container = SimpleNamespace(demo_pass_repo=repo)

    result = activate_local_demo_pass("user-1", container)

    assert result.active is True
    assert repo.get("user-1").payment_reference.startswith("local-test-")

    monkeypatch.setattr(
        "app.api.routes_payments.get_settings",
        lambda: SimpleNamespace(is_local=False),
    )
    with pytest.raises(HTTPException) as raised:
        activate_local_demo_pass("user-2", container)
    assert raised.value.status_code == 403


def test_verified_one_rupee_demo_pass_is_granted_once(monkeypatch):
    repo = InMemoryDemoPassRepository()

    class Gateway:
        def verify_order_payment(self, order_id, payment_id, signature):
            return {
                "amount": 100,
                "amount_paid": 100,
                "currency": "INR",
                "status": "paid",
                "notes": {"kind": "demo_pass", "user_id": "user-1"},
            }

    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", Gateway)
    monkeypatch.setattr(
        "app.api.routes_payments.get_settings",
        lambda: SimpleNamespace(gst_currency="INR"),
    )
    request = RazorpayVerifyRequest(
        razorpay_order_id="order_demo",
        razorpay_payment_id="pay_demo",
        razorpay_signature="valid",
    )

    result = verify_payment(request, "user-1", SimpleNamespace(demo_pass_repo=repo))

    assert result == {"status": "verified", "kind": "demo_pass"}
    demo_pass = repo.get("user-1")
    assert demo_pass.payment_reference == "pay_demo"
    assert demo_pass.purchased_at.tzinfo == timezone.utc


def test_demo_pass_verification_rejects_wrong_amount(monkeypatch):
    repo = InMemoryDemoPassRepository()

    class Gateway:
        def verify_order_payment(self, order_id, payment_id, signature):
            return {
                "amount": 49900,
                "amount_paid": 49900,
                "currency": "INR",
                "status": "paid",
                "notes": {"kind": "demo_pass", "user_id": "user-1"},
            }

    monkeypatch.setattr("app.api.routes_payments._razorpay_gateway", Gateway)
    request = RazorpayVerifyRequest(
        razorpay_order_id="order_demo",
        razorpay_payment_id="pay_demo",
        razorpay_signature="valid",
    )

    with pytest.raises(HTTPException) as raised:
        verify_payment(request, "user-1", SimpleNamespace(demo_pass_repo=repo))

    assert raised.value.status_code == 400
    assert repo.get("user-1") is None


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
