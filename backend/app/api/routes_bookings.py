from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_container, get_current_user_id
from app.api.schemas import BookingOut
from app.container import Container

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", status_code=status.HTTP_410_GONE)
def create_booking() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Use /api/payments/booking-order to start the verified demo checkout.",
    )


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
def dev_confirm_booking() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Bookings can only be marked paid after Razorpay payment verification.",
    )
