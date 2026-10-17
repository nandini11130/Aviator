"""Unit tests exercising the application layer entirely through in-memory /
mock adapters - no network, no cloud credentials, no Stripe account needed.
This is the direct payoff of depending on ports (ABCs) instead of concrete
infrastructure (Dependency Inversion Principle).
"""
from __future__ import annotations

import pytest

from app.application.use_cases import (
    CreateBookingUseCase,
    ManageSubscriptionUseCase,
    SearchEmptySeatDealsUseCase,
    SeatUnavailableError,
    SubscriptionRequiredError,
)
from app.domain.value_objects import CabinClass
from app.infrastructure.flight_data_providers import MockFlightDataProvider
from app.infrastructure.memory_repositories import (
    InMemoryBookingRepository,
    InMemoryFlightRepository,
    InMemorySubscriptionRepository,
)
from app.infrastructure.payment_gateways import MockPaymentGateway
from app.infrastructure.tax_calculators import IndiaGstCalculator


@pytest.fixture
def flight_repo():
    return InMemoryFlightRepository(MockFlightDataProvider(seed=42))


@pytest.fixture
def booking_repo():
    return InMemoryBookingRepository()


@pytest.fixture
def subscription_repo():
    return InMemorySubscriptionRepository()


def test_economy_gst_is_five_percent(flight_repo):
    deals = SearchEmptySeatDealsUseCase(flight_repo, IndiaGstCalculator()).execute(
        CabinClass.ECONOMY
    )
    assert deals, "mock provider should always produce at least one economy deal"
    deal = deals[0]
    assert deal.price.token_amount.amount_minor == 50_000
    assert deal.price.tax_amount.amount_minor == 2_500  # 5% of 500 INR
    assert deal.price.total.amount_minor == 52_500


def test_booking_requires_matching_active_subscription(flight_repo, booking_repo, subscription_repo):
    use_case = CreateBookingUseCase(
        flight_repo, booking_repo, subscription_repo, IndiaGstCalculator(), MockPaymentGateway()
    )
    some_deal = flight_repo.list_empty_seat_deals(CabinClass.ECONOMY)[0]

    with pytest.raises(SubscriptionRequiredError):
        use_case.execute("user-1", some_deal[0].id, CabinClass.ECONOMY)


def test_booking_succeeds_and_decrements_inventory(flight_repo, booking_repo, subscription_repo):
    manage_subscription = ManageSubscriptionUseCase(subscription_repo, MockPaymentGateway(), "INR")
    manage_subscription.activate("user-1", CabinClass.ECONOMY)

    use_case = CreateBookingUseCase(
        flight_repo, booking_repo, subscription_repo, IndiaGstCalculator(), MockPaymentGateway()
    )
    flight, inventory_before = flight_repo.list_empty_seat_deals(CabinClass.ECONOMY)[0]
    seats_before = inventory_before.empty_seats

    booking = use_case.execute("user-1", flight.id, CabinClass.ECONOMY)

    assert booking.status.value == "PENDING_PAYMENT"
    assert booking.checkout_url is not None
    remaining = flight_repo.get_seat_inventory(flight.id, CabinClass.ECONOMY)
    assert remaining.empty_seats == seats_before - 1


def test_demo_booking_requires_membership_but_does_not_charge_or_decrement_inventory(
    flight_repo, booking_repo, subscription_repo
):
    manage_subscription = ManageSubscriptionUseCase(subscription_repo, MockPaymentGateway(), "INR")
    manage_subscription.activate("user-1", CabinClass.ECONOMY)

    use_case = CreateBookingUseCase(
        flight_repo, booking_repo, subscription_repo, IndiaGstCalculator(), MockPaymentGateway()
    )
    flight, inventory_before = flight_repo.list_empty_seat_deals(CabinClass.ECONOMY)[0]
    seats_before = inventory_before.empty_seats

    booking = use_case.execute(
        "user-1", flight.id, CabinClass.ECONOMY, demo=True
    )

    assert booking.status.value == "DEMO_CONFIRMED"
    assert booking.checkout_url is None
    assert booking.payment_reference is None
    assert flight_repo.get_seat_inventory(flight.id, CabinClass.ECONOMY).empty_seats == seats_before


def test_booking_fails_once_seats_are_exhausted(flight_repo, booking_repo, subscription_repo):
    manage_subscription = ManageSubscriptionUseCase(subscription_repo, MockPaymentGateway(), "INR")
    manage_subscription.activate("user-1", CabinClass.FIRST)

    use_case = CreateBookingUseCase(
        flight_repo, booking_repo, subscription_repo, IndiaGstCalculator(), MockPaymentGateway()
    )
    first_class_deals = flight_repo.list_empty_seat_deals(CabinClass.FIRST)
    flight_id = first_class_deals[0][0].id
    inventory = flight_repo.get_seat_inventory(flight_id, CabinClass.FIRST)

    for _ in range(inventory.empty_seats):
        use_case.execute("user-1", flight_id, CabinClass.FIRST)

    with pytest.raises(SeatUnavailableError):
        use_case.execute("user-1", flight_id, CabinClass.FIRST)
