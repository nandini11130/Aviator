"""Function tools used by the Google ADK agents.

Each function is a thin adapter: it validates/parses primitive LLM-provided
arguments, delegates to an application-layer use case, and returns a plain
dict the model can read back. No business logic lives here (Single
Responsibility) - that keeps the agent layer swappable/testable independently
from pricing, booking, and inventory rules.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Literal

from app.application.use_cases import (
    ManageSubscriptionUseCase,
    parse_departure_datetime,
)
from app.container import Container
from app.domain.value_objects import CabinClass, Money

_container: Container | None = None
_authenticated_user_id: ContextVar[str | None] = ContextVar(
    "aviator_authenticated_user_id", default=None
)


@contextmanager
def authenticated_user(user_id: str) -> Iterator[None]:
    token: Token[str | None] = _authenticated_user_id.set(user_id)
    try:
        yield
    finally:
        _authenticated_user_id.reset(token)


def _require_authenticated_user_id() -> str:
    user_id = _authenticated_user_id.get()
    if user_id is None:
        raise RuntimeError("Booking tools require an authenticated chat user.")
    return user_id


def bind_container(container: Container) -> None:
    """Called once at FastAPI startup to give these tools access to the
    composition root's use cases.
    """
    global _container
    _container = container


def _require_container() -> Container:
    if _container is None:
        raise RuntimeError("Agent tools used before bind_container() was called.")
    return _container


def search_empty_seat_deals(
    cabin_class: str = "",
    origin: str = "",
    destination: str = "",
    airline: str = "",
    departure_after: str = "",
    departure_before: str = "",
    priority: Literal["lowest_price", "earliest_departure", "most_estimated_seats"] = "lowest_price",
) -> dict:
    """Find the best matching scheduled flights for a traveller.

    Args:
        cabin_class: Optional filter - one of "ECONOMY", "BUSINESS", "FIRST".
            Leave empty to search every cabin class.
        origin: Optional departure airport IATA code, e.g. "DEL".
        destination: Optional arrival airport IATA code, e.g. "LHR".
        airline: Optional airline name or code substring.
        departure_after: Optional ISO-8601 earliest departure date or datetime.
        departure_before: Optional inclusive latest departure date or datetime.
        priority: Rank results by "lowest_price", "earliest_departure", or
            "most_estimated_seats". Seat counts and prices are estimates.
    """
    container = _require_container()
    container.refresh_flights()
    parsed_cabin_class = CabinClass(cabin_class.upper()) if cabin_class else None
    parsed_after = parse_departure_datetime(departure_after)
    parsed_before = parse_departure_datetime(departure_before, end_of_day=True)
    deals = container.search_deals.execute(
        parsed_cabin_class,
        origin=origin.strip(),
        destination=destination.strip(),
        airline=airline.strip(),
        departure_after=parsed_after,
        departure_before=parsed_before,
    )
    if priority == "lowest_price":
        deals.sort(key=lambda deal: deal.price.total.amount_minor)
    elif priority == "earliest_departure":
        deals.sort(key=lambda deal: deal.flight.departure_time)
    else:
        deals.sort(key=lambda deal: deal.inventory.empty_seats, reverse=True)
    return {
        "priority": priority,
        "result_count": len(deals),
        "ranking_note": {
            "lowest_price": "Ranked by estimated total price, lowest first.",
            "earliest_departure": "Ranked by scheduled departure time, earliest first.",
            "most_estimated_seats": "Ranked by estimated seat count, highest first.",
        }[priority],
        "deals": [
            {
                "flight_id": deal.flight.id,
                "flight_number": deal.flight.flight_number,
                "airline": deal.flight.airline,
                "origin": deal.flight.origin,
                "destination": deal.flight.destination,
                "departure_time": deal.flight.departure_time.isoformat(),
                "cabin_class": deal.inventory.cabin_class.value,
                "empty_seats": deal.inventory.empty_seats,
                "price": deal.price.to_dict(),
                "data_source": "AviationStack schedule; estimated seats and price",
                "data_updated_at": deal.inventory.updated_at.isoformat(),
            }
            for deal in deals
        ]
    }


def calculate_total_price(base_token_amount_minor: int, cabin_class: str) -> dict:
    """Calculate the total price (token amount + GST) for a booking.

    Args:
        base_token_amount_minor: The token/base amount in paise (1 INR = 100 paise).
        cabin_class: One of "ECONOMY", "BUSINESS", "FIRST".
    """
    container = _require_container()
    price = container.calculate_price.execute(
        Money(base_token_amount_minor), CabinClass(cabin_class.upper())
    )
    return price.to_dict()


def book_empty_seat(flight_id: str, cabin_class: str) -> dict:
    """Direct the traveller to secure Razorpay checkout for a demo booking.

    Args:
        flight_id: The id of the flight to book, from `search_empty_seat_deals`.
        cabin_class: One of "ECONOMY", "BUSINESS", "FIRST".
    """
    _require_container()
    _require_authenticated_user_id()
    parsed_cabin = CabinClass(cabin_class.upper())
    return {
        "error": "checkout_required",
        "message": (
            f"To continue with {flight_id} in {parsed_cabin.value}, the traveller "
            "must select Book on the flight card and complete Razorpay checkout "
            "for the displayed estimated total. This is a paid demo only; it "
            "does not reserve airline inventory or issue a ticket."
        ),
    }


def get_booking_status(booking_id: str) -> dict:
    """Look up the current status of a booking by id."""
    container = _require_container()
    booking = container.booking_repo.get(booking_id)
    if not booking:
        return {"error": "not_found", "message": f"No booking with id {booking_id}."}
    return {
        "booking_id": booking.id,
        "status": booking.status.value,
        "flight_id": booking.flight_id,
        "cabin_class": booking.cabin_class.value,
        "demo_booking": booking.status.value.startswith("DEMO_"),
        "message": (
            "Demo only; payment does not reserve a real airline seat or issue a ticket."
            if booking.status.value.startswith("DEMO_")
            else "Booking status retrieved."
        ),
    }


def get_subscription_policy() -> dict:
    """Return the Aviator subscription tiers, their membership fees, and the
    explanation of the current demo booking flow.
    """
    return {
        "tiers": [
            {"tier": tier.value, "monthly_fee_minor": fee}
            for tier, fee in ManageSubscriptionUseCase.MEMBERSHIP_FEES_MINOR.items()
        ],
        "gst_rules": {
            "ECONOMY": "5% GST on the token amount",
            "BUSINESS": "12% GST on the token amount",
            "FIRST": "12% GST on the token amount",
        },
        "note": (
            "Membership fees, the one-time ₹1 demo pass, and demo booking "
            "payments are charged through Razorpay. A matching active member "
            "or demo-pass holder can pay the displayed estimated total for a "
            "demo booking. The payment does not reserve airline inventory or "
            "issue a ticket."
        ),
    }
