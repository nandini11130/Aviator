"""Firestore-backed repositories used in production (Cloud Run). Firestore
client uses Application Default Credentials, so no key file is needed when
running on Cloud Run / Firebase with the right service account bound.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from app.domain.entities import (
    Booking,
    BookingStatus,
    DemoPass,
    Flight,
    SeatInventory,
    Subscription,
    SubscriptionStatus,
)
from app.domain.ports import (
    BookingRepository,
    DemoPassRepository,
    FlightDataProvider,
    FlightRepository,
    SubscriptionRepository,
)
from app.domain.value_objects import CabinClass, Money

_FLIGHTS = "flights"
_INVENTORY = "seat_inventory"
_BOOKINGS = "bookings"
_SUBSCRIPTIONS = "subscriptions"
_DEMO_PASSES = "demo_passes"
_FLIGHT_REFRESH = "flight_data_refresh"


class FlightDataRefreshError(RuntimeError):
    """Raised when the provider returns no schedule data to refresh."""


def _inventory_doc_id(flight_id: str, cabin_class: CabinClass) -> str:
    return f"{flight_id}__{cabin_class.value}"


class FirestoreFlightRepository(FlightRepository):
    """Reads cached provider schedules and refreshes them at most daily."""

    def __init__(self, client: firestore.Client, source: str):
        self._client = client
        self._source = source

    def refresh_if_stale(self, provider: FlightDataProvider) -> None:
        now = datetime.now(timezone.utc)
        refresh_ref = self._client.collection(_FLIGHT_REFRESH).document(self._source)

        @firestore.transactional
        def claim_refresh(transaction: firestore.Transaction) -> bool:
            snapshot = refresh_ref.get(transaction=transaction)
            refresh_after = snapshot.get("refresh_after") if snapshot.exists else None
            if refresh_after and refresh_after > now:
                return False
            transaction.set(
                refresh_ref,
                {"refresh_after": now + timedelta(minutes=5)},
                merge=True,
            )
            return True

        if not claim_refresh(self._client.transaction()):
            return

        entries = provider.fetch_live_inventory()
        if not entries:
            raise FlightDataRefreshError("Flight provider returned no schedules.")

        flights: dict[str, dict] = {}
        inventories: dict[str, dict] = {}
        for flight, inventory in entries:
            flights[flight.id] = {
                "flight_number": flight.flight_number,
                "airline": flight.airline,
                "origin": flight.origin,
                "destination": flight.destination,
                "departure_time": flight.departure_time,
                "arrival_time": flight.arrival_time,
                "source": self._source,
            }
            inventories[_inventory_doc_id(flight.id, inventory.cabin_class)] = {
                "flight_id": inventory.flight_id,
                "cabin_class": inventory.cabin_class.value,
                "empty_seats": inventory.empty_seats,
                "base_token_amount_minor": inventory.base_token_amount.amount_minor,
                "currency": inventory.base_token_amount.currency,
                "updated_at": inventory.updated_at,
                "source": self._source,
            }

        flight_collection = self._client.collection(_FLIGHTS)
        inventory_collection = self._client.collection(_INVENTORY)
        operations: list[tuple[firestore.DocumentReference, dict | None]] = [
            (flight_collection.document(flight_id), data)
            for flight_id, data in flights.items()
        ] + [
            (inventory_collection.document(inventory_id), data)
            for inventory_id, data in inventories.items()
        ]

        for doc in flight_collection.stream():
            if doc.to_dict().get("source") == self._source and doc.id not in flights:
                operations.append((doc.reference, None))
        for doc in inventory_collection.stream():
            if doc.to_dict().get("source") == self._source and doc.id not in inventories:
                operations.append((doc.reference, None))

        for offset in range(0, len(operations), 450):
            batch = self._client.batch()
            for reference, data in operations[offset : offset + 450]:
                if data is None:
                    batch.delete(reference)
                else:
                    batch.set(reference, data)
            batch.commit()

        refresh_ref.set(
            {
                "updated_at": now,
                "refresh_after": now + timedelta(hours=24),
            },
            merge=True,
        )

    def list_empty_seat_deals(self, cabin_class: CabinClass | None = None):
        results = []
        for doc in self._client.collection(_INVENTORY).stream():
            data = doc.to_dict()
            if (
                data.get("source") != self._source
                or data.get("empty_seats", 0) <= 0
                or (
                    cabin_class is not None
                    and data.get("cabin_class") != cabin_class.value
                )
            ):
                continue
            inventory = self._inventory_from_doc(doc)
            flight = self.get_flight(inventory.flight_id)
            if flight:
                results.append((flight, inventory))
        results.sort(key=lambda pair: pair[0].departure_time)
        return results

    def get_flight(self, flight_id: str):
        doc = self._client.collection(_FLIGHTS).document(flight_id).get()
        if not doc.exists or doc.to_dict().get("source") != self._source:
            return None
        data = doc.to_dict()
        return Flight(
            id=doc.id,
            flight_number=data["flight_number"],
            airline=data["airline"],
            origin=data["origin"],
            destination=data["destination"],
            departure_time=data["departure_time"],
            arrival_time=data["arrival_time"],
        )

    def get_seat_inventory(self, flight_id: str, cabin_class: CabinClass):
        doc = self._client.collection(_INVENTORY).document(
            _inventory_doc_id(flight_id, cabin_class)
        ).get()
        if not doc.exists or doc.to_dict().get("source") != self._source:
            return None
        return self._inventory_from_doc(doc)

    def decrement_seat(self, flight_id: str, cabin_class: CabinClass) -> bool:
        doc_ref = self._client.collection(_INVENTORY).document(
            _inventory_doc_id(flight_id, cabin_class)
        )

        @firestore.transactional
        def _txn(transaction: firestore.Transaction) -> bool:
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists or snapshot.get("empty_seats") <= 0:
                return False
            transaction.update(doc_ref, {"empty_seats": firestore.Increment(-1)})
            return True

        return _txn(self._client.transaction())

    def _inventory_from_doc(self, doc) -> SeatInventory:
        data = doc.to_dict()
        return SeatInventory(
            flight_id=data["flight_id"],
            cabin_class=CabinClass(data["cabin_class"]),
            empty_seats=data["empty_seats"],
            base_token_amount=Money(data["base_token_amount_minor"], data["currency"]),
            updated_at=data["updated_at"],
        )


class FirestoreBookingRepository(BookingRepository):
    def __init__(self, client: firestore.Client):
        self._client = client

    def save(self, booking: Booking) -> None:
        self._client.collection(_BOOKINGS).document(booking.id).set(
            {
                "user_id": booking.user_id,
                "flight_id": booking.flight_id,
                "cabin_class": booking.cabin_class.value,
                "token_amount_minor": booking.token_amount.amount_minor,
                "tax_amount_minor": booking.tax_amount.amount_minor,
                "currency": booking.token_amount.currency,
                "status": booking.status.value,
                "payment_reference": booking.payment_reference,
                "checkout_url": booking.checkout_url,
                "created_at": booking.created_at,
            }
        )

    def get(self, booking_id: str):
        doc = self._client.collection(_BOOKINGS).document(booking_id).get()
        if not doc.exists:
            return None
        return self._booking_from_doc(doc.id, doc.to_dict())

    def get_by_payment_reference(self, payment_reference: str):
        query = self._client.collection(_BOOKINGS).where(
            "payment_reference", "==", payment_reference
        ).limit(1)
        doc = next(query.stream(), None)
        return self._booking_from_doc(doc.id, doc.to_dict()) if doc else None

    def list_for_user(self, user_id: str):
        query = self._client.collection(_BOOKINGS).where("user_id", "==", user_id)
        return [self._booking_from_doc(doc.id, doc.to_dict()) for doc in query.stream()]

    def _booking_from_doc(self, doc_id: str, data: dict) -> Booking:
        currency = data["currency"]
        return Booking(
            id=doc_id,
            user_id=data["user_id"],
            flight_id=data["flight_id"],
            cabin_class=CabinClass(data["cabin_class"]),
            token_amount=Money(data["token_amount_minor"], currency),
            tax_amount=Money(data["tax_amount_minor"], currency),
            status=BookingStatus(data["status"]),
            payment_reference=data.get("payment_reference"),
            checkout_url=data.get("checkout_url"),
            created_at=data["created_at"],
        )


class FirestoreSubscriptionRepository(SubscriptionRepository):
    def __init__(self, client: firestore.Client):
        self._client = client

    def get_active(self, user_id: str):
        doc = self._client.collection(_SUBSCRIPTIONS).document(user_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Subscription(
            user_id=user_id,
            tier=CabinClass(data["tier"]),
            status=SubscriptionStatus(data["status"]),
            started_at=data["started_at"],
            renews_at=data.get("renews_at"),
            payment_reference=data.get("payment_reference"),
        )

    def save(self, subscription: Subscription) -> None:
        self._client.collection(_SUBSCRIPTIONS).document(subscription.user_id).set(
            {
                "tier": subscription.tier.value,
                "status": subscription.status.value,
                "started_at": subscription.started_at,
                "renews_at": subscription.renews_at,
                "payment_reference": subscription.payment_reference,
            }
        )


class FirestoreDemoPassRepository(DemoPassRepository):
    def __init__(self, client: firestore.Client):
        self._client = client

    def get(self, user_id: str):
        doc = self._client.collection(_DEMO_PASSES).document(user_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return DemoPass(
            user_id=user_id,
            payment_reference=data["payment_reference"],
            purchased_at=data["purchased_at"],
        )

    def save(self, demo_pass: DemoPass) -> None:
        self._client.collection(_DEMO_PASSES).document(demo_pass.user_id).set(
            {
                "payment_reference": demo_pass.payment_reference,
                "purchased_at": demo_pass.purchased_at,
            }
        )
