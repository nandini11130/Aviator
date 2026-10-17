"""Core domain entities. Plain dataclasses on purpose: the domain layer must
not depend on FastAPI, Firestore, or any delivery/infrastructure concern
(Dependency Inversion - inner layers know nothing about outer layers).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .value_objects import CabinClass, Money


@dataclass(slots=True)
class Flight:
    id: str
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime


@dataclass(slots=True)
class SeatInventory:
    flight_id: str
    cabin_class: CabinClass
    empty_seats: int
    base_token_amount: Money
    updated_at: datetime


class BookingStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    DEMO_CONFIRMED = "DEMO_CONFIRMED"
    DEMO_PENDING_PAYMENT = "DEMO_PENDING_PAYMENT"
    DEMO_PAID = "DEMO_PAID"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(slots=True)
class Booking:
    id: str
    user_id: str
    flight_id: str
    cabin_class: CabinClass
    token_amount: Money
    tax_amount: Money
    status: BookingStatus
    payment_reference: str | None
    checkout_url: str | None
    created_at: datetime

    @property
    def total_amount(self) -> Money:
        return self.token_amount + self.tax_amount


class SubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class Subscription:
    user_id: str
    tier: CabinClass
    status: SubscriptionStatus
    started_at: datetime
    renews_at: datetime | None
    payment_reference: str | None = None


@dataclass(slots=True)
class DemoPass:
    user_id: str
    payment_reference: str
    purchased_at: datetime
