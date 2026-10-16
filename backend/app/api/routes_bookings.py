from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_container, get_current_user_id
from app.api.schemas import BookingOut, CreateBookingRequest
from app.application.use_cases import SeatUnavailableError, SubscriptionRequiredError
from app.config import get_settings
from app.container import Container
from app.domain.entities import BookingStatus

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    request: CreateBookingRequest,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> BookingOut:
    try:
        booking = container.create_booking.execute(
            user_id=user_id,
            flight_id=request.flight_id,
            cabin_class=request.cabin_class,
        )
    except SubscriptionRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except SeatUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BookingOut.from_domain(booking)


@router.get("", response_model=list[BookingOut])
def list_my_bookings(
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> list[BookingOut]:
    bookings = container.booking_repo.list_for_user(user_id)
    return [BookingOut.from_domain(b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: str,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> BookingOut:
    booking = container.booking_repo.get(booking_id)
    if not booking or booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return BookingOut.from_domain(booking)


@router.post("/{booking_id}/dev-confirm", response_model=BookingOut)
def dev_confirm_booking(
    booking_id: str,
    user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> BookingOut:
    """Local-only shortcut that marks a booking CONFIRMED without a real
    Stripe webhook, so the end-to-end flow is demoable with zero payment
    credentials configured.
    """
    settings = get_settings()
    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev-confirm is disabled outside local development.",
        )
    booking = container.booking_repo.get(booking_id)
    if not booking or booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    booking.status = BookingStatus.CONFIRMED
    container.booking_repo.save(booking)
    return BookingOut.from_domain(booking)
