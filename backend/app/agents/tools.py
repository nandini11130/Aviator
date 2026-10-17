"""Function tools used by the Google ADK agents.

Each function is a thin adapter: it validates/parses primitive LLM-provided
arguments, delegates to an application-layer use case, and returns a plain
dict the model can read back. No business logic lives here (Single
Responsibility) - that keeps the agent layer swappable/testable independently
from pricing, booking, and inventory rules.
"""
from __future__ import annotations

from app.application.use_cases import (
    ManageSubscriptionUseCase,
    SeatUnavailableError,
    SubscriptionRequiredError,
)
from app.container import Container
from app.domain.value_objects import CabinClass, Money

_container: Container | None = None


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


def search_empty_seat_deals(cabin_class: str = "") -> dict:
    """Search scheduled flights and estimated seat availability.

    Args:
        cabin_class: Optional filter - one of "ECONOMY", "BUSINESS", "FIRST".
            Leave empty to search every cabin class.
    """
    container = _require_container()
    container.refresh_flights()
    parsed_cabin_class = CabinClass(cabin_class.upper()) if cabin_class else None
    deals = container.search_deals.execute(parsed_cabin_class)
    return {
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


def book_empty_seat(user_id: str, flight_id: str, cabin_class: str) -> dict:
    """Create a no-charge demo booking; this does not reserve airline inventory.

    Args:
        user_id: The authenticated user's id.
        flight_id: The id of the flight to book, from `search_empty_seat_deals`.
        cabin_class: One of "ECONOMY", "BUSINESS", "FIRST". Must match the
            user's active subscription tier.
    """
    container = _require_container()
    try:
        booking = container.create_booking.execute(
            user_id=user_id,
            flight_id=flight_id,
            cabin_class=CabinClass(cabin_class.upper()),
            create_checkout=False,
            demo=True,
        )
    except SubscriptionRequiredError as exc:
        return {"error": "subscription_required", "message": str(exc)}
    except SeatUnavailableError as exc:
        return {"error": "seat_unavailable", "message": str(exc)}

    return {
        "booking_id": booking.id,
        "status": booking.status.value,
        "demo_booking": True,
        "message": (
            "Demo booking saved. No airline seat was reserved, no ticket was "
            "issued, and no booking payment was taken."
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
        "demo_booking": booking.status.value == "DEMO_CONFIRMED",
        "message": (
            "Demo only; no ticket was issued and no booking payment was taken."
            if booking.status.value == "DEMO_CONFIRMED"
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
            "Membership fees are charged through Razorpay. Matching active "
            "members can create no-charge demo bookings. Flight availability "
            "and prices are estimates; demo bookings do not reserve airline "
            "seats or issue tickets."
        ),
    }
