"""Application layer: one class per use case, each with a single public
`execute` method and dependencies injected through the constructor as
abstract ports. No framework imports here (no FastAPI, no Firestore, no
Stripe SDK) - that keeps this layer trivially unit-testable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from app.domain.entities import (
    Booking,
    BookingStatus,
    Flight,
    SeatInventory,
    Subscription,
    SubscriptionStatus,
)
from app.domain.ports import (
    BookingRepository,
    CheckoutSession,
    DemoPassRepository,
    FlightRepository,
    PaymentGateway,
    SubscriptionRepository,
    TaxCalculator,
    WebhookEvent,
)
from app.domain.value_objects import CabinClass, Money, PriceBreakdown


class SubscriptionRequiredError(PermissionError):
    """Raised when a user tries to book without an active matching tier."""


class SeatUnavailableError(ValueError):
    """Raised when the last empty seat was taken by someone else first."""


def parse_departure_datetime(
    value: str | None, *, end_of_day: bool = False
) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if len(raw) == 10:
        parsed_date = date.fromisoformat(raw)
        parsed_time = time.max if end_of_day else time.min
        return datetime.combine(parsed_date, parsed_time, tzinfo=timezone.utc)
    parsed_datetime = datetime.fromisoformat(raw)
    if parsed_datetime.tzinfo is None:
        return parsed_datetime.replace(tzinfo=timezone.utc)
    return parsed_datetime.astimezone(timezone.utc)


@dataclass(slots=True)
class DealView:
    flight: Flight
    inventory: SeatInventory
    price: PriceBreakdown


class SearchEmptySeatDealsUseCase:
    """Lists schedules filtered by a traveller's route and timing preferences."""

    def __init__(self, flight_repo: FlightRepository, tax_calculator: TaxCalculator):
        self._flight_repo = flight_repo
        self._tax_calculator = tax_calculator

    def execute(
        self,
        cabin_class: CabinClass | None = None,
        origin: str = "",
        destination: str = "",
        airline: str = "",
        departure_after: datetime | None = None,
        departure_before: datetime | None = None,
    ) -> list[DealView]:
        def as_utc(value: datetime | None) -> datetime | None:
            if value is None:
                return None
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        earliest = as_utc(departure_after)
        latest = as_utc(departure_before)
        if earliest and latest and earliest > latest:
            raise ValueError("departure_after must be earlier than departure_before.")

        deals = self._flight_repo.list_empty_seat_deals(cabin_class)
        views: list[DealView] = []
        for flight, inventory in deals:
            if origin and origin.upper() not in flight.origin.upper():
                continue
            if destination and destination.upper() not in flight.destination.upper():
                continue
            if airline and airline.casefold() not in flight.airline.casefold():
                continue
            scheduled_departure = as_utc(flight.departure_time)
            if scheduled_departure is None:
                continue
            if earliest and scheduled_departure < earliest:
                continue
            if latest and scheduled_departure > latest:
                continue
            tax = self._tax_calculator.calculate(
                inventory.base_token_amount, inventory.cabin_class
            )
            price = PriceBreakdown(inventory.base_token_amount, tax)
            views.append(DealView(flight=flight, inventory=inventory, price=price))
        return views


class CalculatePriceUseCase:
    """Pure pricing: token amount + GST for a given cabin class."""

    def __init__(self, tax_calculator: TaxCalculator):
        self._tax_calculator = tax_calculator

    def execute(self, base_amount: Money, cabin_class: CabinClass) -> PriceBreakdown:
        tax = self._tax_calculator.calculate(base_amount, cabin_class)
        return PriceBreakdown(token_amount=base_amount, tax_amount=tax)


class CreateBookingUseCase:
    """Creates bookings, with demo access controlled by membership or pass."""

    def __init__(
        self,
        flight_repo: FlightRepository,
        booking_repo: BookingRepository,
        subscription_repo: SubscriptionRepository,
        tax_calculator: TaxCalculator,
        payment_gateway: PaymentGateway,
        demo_pass_repo: DemoPassRepository | None = None,
    ):
        self._flight_repo = flight_repo
        self._booking_repo = booking_repo
        self._subscription_repo = subscription_repo
        self._tax_calculator = tax_calculator
        self._payment_gateway = payment_gateway
        self._demo_pass_repo = demo_pass_repo

    def execute(
        self,
        user_id: str,
        flight_id: str,
        cabin_class: CabinClass,
        create_checkout: bool = True,
        demo: bool = False,
    ) -> Booking:
        subscription = self._subscription_repo.get_active(user_id)
        has_matching_subscription = (
            subscription is not None
            and subscription.status == SubscriptionStatus.ACTIVE
            and subscription.tier == cabin_class
        )
        has_demo_pass = (
            demo
            and self._demo_pass_repo is not None
            and self._demo_pass_repo.get(user_id) is not None
        )
        if not has_matching_subscription and not has_demo_pass:
            raise SubscriptionRequiredError(
                f"An active {cabin_class.value} subscription or a paid demo pass "
                "is required to book this cabin class."
            )

        inventory = self._flight_repo.get_seat_inventory(flight_id, cabin_class)
        if not inventory or inventory.empty_seats <= 0:
            raise SeatUnavailableError("No empty seats left on this flight.")

        if not demo and not self._flight_repo.decrement_seat(flight_id, cabin_class):
            raise SeatUnavailableError("Seat was just taken by another traveller.")

        price = CalculatePriceUseCase(self._tax_calculator).execute(
            inventory.base_token_amount, cabin_class
        )
        booking = Booking(
            id=str(uuid.uuid4()),
            user_id=user_id,
            flight_id=flight_id,
            cabin_class=cabin_class,
            token_amount=price.token_amount,
            tax_amount=price.tax_amount,
            status=(
                BookingStatus.DEMO_PENDING_PAYMENT
                if demo
                else BookingStatus.PENDING_PAYMENT
            ),
            payment_reference=None,
            checkout_url=None,
            created_at=datetime.now(timezone.utc),
        )

        if create_checkout and not demo:
            flight = self._flight_repo.get_flight(flight_id)
            description = (
                f"Aviator last-minute {cabin_class.value.title()} seat "
                f"{flight.flight_number if flight else flight_id}"
            )
            checkout: CheckoutSession = self._payment_gateway.create_checkout_session(
                amount=price.total,
                description=description,
                metadata={
                    "booking_id": booking.id,
                    "user_id": user_id,
                    "flight_id": flight_id,
                    "cabin_class": cabin_class.value,
                    "kind": "booking",
                },
            )
            booking.payment_reference = checkout.session_id
            booking.checkout_url = checkout.url
        self._booking_repo.save(booking)
        return booking


class ConfirmPaymentUseCase:
    """Handles a Stripe webhook event and confirms/cancels the matching
    booking or subscription. Keeps webhook parsing (infrastructure) fully
    separate from the state transitions it triggers (application logic).
    """

    def __init__(
        self,
        booking_repo: BookingRepository,
        subscription_repo: SubscriptionRepository,
    ):
        self._booking_repo = booking_repo
        self._subscription_repo = subscription_repo

    def execute(self, event: WebhookEvent) -> None:
        if event.type != "checkout.session.completed":
            return
        kind = event.metadata.get("kind")
        if kind == "booking":
            booking_id = event.metadata.get("booking_id")
            booking = self._booking_repo.get(booking_id) if booking_id else None
            if not booking:
                return
            booking.status = BookingStatus.CONFIRMED
            self._booking_repo.save(booking)
        elif kind == "subscription":
            user_id = event.metadata.get("user_id")
            tier_value = event.metadata.get("tier")
            if not user_id or not tier_value:
                return
            subscription = Subscription(
                user_id=user_id,
                tier=CabinClass(tier_value),
                status=SubscriptionStatus.ACTIVE,
                started_at=datetime.now(timezone.utc),
                renews_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            self._subscription_repo.save(subscription)


class ManageSubscriptionUseCase:
    """Subscribing is modelled as a paid membership activation (via the same
    Checkout flow as bookings) rather than Stripe recurring billing, keeping
    the payments integration surface small for the MVP.
    """

    MEMBERSHIP_FEES_MINOR: dict[CabinClass, int] = {
        CabinClass.ECONOMY: 49900,
        CabinClass.BUSINESS: 99900,
        CabinClass.FIRST: 199900,
    }

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        payment_gateway: PaymentGateway,
        currency: str,
    ):
        self._subscription_repo = subscription_repo
        self._payment_gateway = payment_gateway
        self._currency = currency

    def start_subscription_checkout(
        self, user_id: str, tier: CabinClass
    ) -> CheckoutSession:
        fee = Money(self.MEMBERSHIP_FEES_MINOR[tier], self._currency)
        return self._payment_gateway.create_checkout_session(
            amount=fee,
            description=f"Aviator {tier.value.title()} membership (30 days)",
            metadata={"user_id": user_id, "tier": tier.value, "kind": "subscription"},
        )

    def activate(
        self, user_id: str, tier: CabinClass, payment_reference: str | None = None
    ) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            renews_at=datetime.now(timezone.utc) + timedelta(days=30),
            payment_reference=payment_reference,
        )
        self._subscription_repo.save(subscription)
        return subscription

    def cancel(self, user_id: str) -> None:
        subscription = self._subscription_repo.get_active(user_id)
        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            self._subscription_repo.save(subscription)
