"""Ports: abstract boundaries the application layer depends on.

Every infrastructure concern (Firestore, Stripe, an external flight API) is
represented here as an `ABC`. Concrete adapters live in `app/infrastructure`
and are wired together only in `app/api/deps.py` (the composition root).
This is what makes the use cases substitutable and unit-testable without a
network, a database, or a cloud account (Liskov Substitution + Dependency
Inversion in practice).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .entities import Booking, Flight, SeatInventory, Subscription
from .value_objects import CabinClass, Money


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    """Result of starting a hosted payment flow (Stripe Checkout)."""

    session_id: str
    url: str


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    """Normalised payment webhook event, independent of the gateway's SDK."""

    type: str
    payment_reference: str | None
    metadata: dict[str, str]


class FlightRepository(ABC):
    """Read/write access to flights + their live empty-seat inventory."""

    @abstractmethod
    def list_empty_seat_deals(
        self, cabin_class: CabinClass | None = None
    ) -> list[tuple[Flight, SeatInventory]]: ...

    @abstractmethod
    def get_flight(self, flight_id: str) -> Flight | None: ...

    @abstractmethod
    def get_seat_inventory(
        self, flight_id: str, cabin_class: CabinClass
    ) -> SeatInventory | None: ...

    @abstractmethod
    def decrement_seat(self, flight_id: str, cabin_class: CabinClass) -> bool:
        """Atomically reserve one seat. Returns False if none were left."""
        ...


class BookingRepository(ABC):
    @abstractmethod
    def save(self, booking: Booking) -> None: ...

    @abstractmethod
    def get(self, booking_id: str) -> Booking | None: ...

    @abstractmethod
    def get_by_payment_reference(self, payment_reference: str) -> Booking | None: ...

    @abstractmethod
    def list_for_user(self, user_id: str) -> list[Booking]: ...


class SubscriptionRepository(ABC):
    @abstractmethod
    def get_active(self, user_id: str) -> Subscription | None: ...

    @abstractmethod
    def save(self, subscription: Subscription) -> None: ...


class TaxCalculator(ABC):
    @abstractmethod
    def calculate(self, base_amount: Money, cabin_class: CabinClass) -> Money: ...


class PaymentGateway(ABC):
    @abstractmethod
    def create_checkout_session(
        self,
        amount: Money,
        description: str,
        metadata: dict[str, str],
    ) -> CheckoutSession: ...

    @abstractmethod
    def parse_webhook_event(self, payload: bytes, signature: str) -> WebhookEvent: ...


class FlightDataProvider(ABC):
    """Adapter boundary for a real-time external data source (e.g. an
    aviation schedules API). Swappable independently of persistence.
    """

    @abstractmethod
    def fetch_live_inventory(self) -> list[tuple[Flight, SeatInventory]]: ...
