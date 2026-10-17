"""Unit tests exercising the application layer entirely through in-memory /
mock adapters - no network, no cloud credentials, no Stripe account needed.
This is the direct payoff of depending on ports (ABCs) instead of concrete
infrastructure (Dependency Inversion Principle).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.entities import DemoPass
from app.application.use_cases import (
    CreateBookingUseCase,
    ManageSubscriptionUseCase,
    SearchEmptySeatDealsUseCase,
    SeatUnavailableError,
    SubscriptionRequiredError,
    parse_departure_datetime,
)
from app.domain.value_objects import CabinClass
from app.infrastructure.flight_data_providers import MockFlightDataProvider
from app.infrastructure.memory_repositories import (
    InMemoryBookingRepository,
    InMemoryDemoPassRepository,
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


@pytest.fixture
def demo_pass_repo():
    return InMemoryDemoPassRepository()


def test_economy_gst_is_five_percent(flight_repo):
    deals = SearchEmptySeatDealsUseCase(flight_repo, IndiaGstCalculator()).execute(
        CabinClass.ECONOMY
    )
    assert deals, "mock provider should always produce at least one economy deal"
    deal = deals[0]
    assert deal.price.token_amount.amount_minor == 50_000
    assert deal.price.tax_amount.amount_minor == 2_500  # 5% of 500 INR
    assert deal.price.total.amount_minor == 52_500


def test_schedule_search_filters_by_route_airline_and_departure_window(flight_repo):
    flight, _ = flight_repo.list_empty_seat_deals(CabinClass.ECONOMY)[0]
    use_case = SearchEmptySeatDealsUseCase(flight_repo, IndiaGstCalculator())

    matching = use_case.execute(
        CabinClass.ECONOMY,
        origin=flight.origin.lower(),
        destination=flight.destination.lower(),
        airline=flight.airline[:4].lower(),
        departure_after=flight.departure_time,
        departure_before=flight.departure_time,
    )

    assert matching
    assert all(
        deal.flight.origin == flight.origin
        and deal.flight.destination == flight.destination
        and deal.flight.airline == flight.airline
        and deal.flight.departure_time == flight.departure_time
        for deal in matching
    )


def test_schedule_search_rejects_inverted_departure_window(flight_repo):
    use_case = SearchEmptySeatDealsUseCase(flight_repo, IndiaGstCalculator())

    with pytest.raises(ValueError, match="departure_after"):
        use_case.execute(
            departure_after=datetime(2026, 10, 20, tzinfo=timezone.utc),
            departure_before=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )


def test_date_only_departure_bounds_cover_the_full_utc_day():
    start = parse_departure_datetime("2026-10-20")
    end = parse_departure_datetime("2026-10-20", end_of_day=True)

    assert start == datetime(2026, 10, 20, tzinfo=timezone.utc)
    assert end == datetime(
        2026, 10, 20, 23, 59, 59, 999999, tzinfo=timezone.utc
    )


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

    assert booking.status.value == "DEMO_PENDING_PAYMENT"
    assert booking.checkout_url is None
    assert booking.payment_reference is None
    assert flight_repo.get_seat_inventory(flight.id, CabinClass.ECONOMY).empty_seats == seats_before


def test_paid_demo_pass_allows_no_charge_demo_booking_without_membership(
    flight_repo, booking_repo, subscription_repo, demo_pass_repo
):
    demo_pass_repo.save(
        DemoPass(
            user_id="user-with-pass",
            payment_reference="pay_demo_pass",
            purchased_at=datetime.now(timezone.utc),
        )
    )
    use_case = CreateBookingUseCase(
        flight_repo,
        booking_repo,
        subscription_repo,
        IndiaGstCalculator(),
        MockPaymentGateway(),
        demo_pass_repo,
    )
    flight, inventory_before = flight_repo.list_empty_seat_deals(CabinClass.BUSINESS)[0]
    seats_before = inventory_before.empty_seats

    booking = use_case.execute(
        "user-with-pass", flight.id, CabinClass.BUSINESS, demo=True
    )

    assert booking.status.value == "DEMO_PENDING_PAYMENT"
    assert booking.checkout_url is None
    assert flight_repo.get_seat_inventory(flight.id, CabinClass.BUSINESS).empty_seats == seats_before


def test_demo_pass_does_not_authorize_paid_booking(
    flight_repo, booking_repo, subscription_repo, demo_pass_repo
):
    demo_pass_repo.save(
        DemoPass(
            user_id="user-with-pass",
            payment_reference="pay_demo_pass",
            purchased_at=datetime.now(timezone.utc),
        )
    )
    use_case = CreateBookingUseCase(
        flight_repo,
        booking_repo,
        subscription_repo,
        IndiaGstCalculator(),
        MockPaymentGateway(),
        demo_pass_repo,
    )
    flight = flight_repo.list_empty_seat_deals(CabinClass.ECONOMY)[0][0]

    with pytest.raises(SubscriptionRequiredError):
        use_case.execute("user-with-pass", flight.id, CabinClass.ECONOMY)


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
