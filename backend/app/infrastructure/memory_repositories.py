"""In-memory repository implementations backing local development and unit
tests. They satisfy the exact same ports as the Firestore adapters, so use
cases and API routes do not know (or care) which one is active.
"""
from __future__ import annotations

import threading

from app.domain.entities import Booking, DemoPass, SeatInventory, Subscription
from app.domain.ports import (
    BookingRepository,
    DemoPassRepository,
    FlightDataProvider,
    FlightRepository,
    SubscriptionRepository,
)
from app.domain.value_objects import CabinClass


class InMemoryFlightRepository(FlightRepository):
    def __init__(self, provider: FlightDataProvider):
        self._lock = threading.Lock()
        flights_and_inventory = provider.fetch_live_inventory()
        self._flights = {f.id: f for f, _ in flights_and_inventory}
        self._inventory: dict[tuple[str, CabinClass], SeatInventory] = {
            (inv.flight_id, inv.cabin_class): inv for _, inv in flights_and_inventory
        }

    def list_empty_seat_deals(self, cabin_class: CabinClass | None = None):
        with self._lock:
            results = []
            for (flight_id, inv_cabin_class), inventory in self._inventory.items():
                if cabin_class is not None and inv_cabin_class != cabin_class:
                    continue
                if inventory.empty_seats <= 0:
                    continue
                results.append((self._flights[flight_id], inventory))
            results.sort(key=lambda pair: pair[0].departure_time)
            return results

    def get_flight(self, flight_id: str):
        return self._flights.get(flight_id)

    def get_seat_inventory(self, flight_id: str, cabin_class: CabinClass):
        return self._inventory.get((flight_id, cabin_class))

    def decrement_seat(self, flight_id: str, cabin_class: CabinClass) -> bool:
        with self._lock:
            inventory = self._inventory.get((flight_id, cabin_class))
            if not inventory or inventory.empty_seats <= 0:
                return False
            inventory.empty_seats -= 1
            return True


class InMemoryBookingRepository(BookingRepository):
    def __init__(self):
        self._lock = threading.Lock()
        self._bookings: dict[str, Booking] = {}

    def save(self, booking: Booking) -> None:
        with self._lock:
            self._bookings[booking.id] = booking

    def get(self, booking_id: str):
        return self._bookings.get(booking_id)

    def get_by_payment_reference(self, payment_reference: str):
        return next(
            (b for b in self._bookings.values() if b.payment_reference == payment_reference),
            None,
        )

    def list_for_user(self, user_id: str):
        return [b for b in self._bookings.values() if b.user_id == user_id]


class InMemorySubscriptionRepository(SubscriptionRepository):
    def __init__(self):
        self._lock = threading.Lock()
        self._subscriptions: dict[str, Subscription] = {}

    def get_active(self, user_id: str):
        return self._subscriptions.get(user_id)

    def save(self, subscription: Subscription) -> None:
        with self._lock:
            self._subscriptions[subscription.user_id] = subscription


class InMemoryDemoPassRepository(DemoPassRepository):
    def __init__(self):
        self._lock = threading.Lock()
        self._demo_passes: dict[str, DemoPass] = {}

    def get(self, user_id: str):
        with self._lock:
            return self._demo_passes.get(user_id)

    def save(self, demo_pass: DemoPass) -> None:
        with self._lock:
            self._demo_passes[demo_pass.user_id] = demo_pass
