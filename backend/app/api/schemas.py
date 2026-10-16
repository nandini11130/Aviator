"""Pydantic request/response schemas for the HTTP API. Kept separate from
domain entities so the wire format can evolve independently of the domain
model (e.g. renaming a JSON field never touches `app/domain`).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.application.use_cases import DealView
from app.domain.entities import Booking
from app.domain.value_objects import CabinClass


class MoneyOut(BaseModel):
    amount_minor: int
    currency: str


class PriceOut(BaseModel):
    token_amount: MoneyOut
    tax_amount: MoneyOut
    total: MoneyOut


class DealOut(BaseModel):
    flight_id: str
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    cabin_class: CabinClass
    empty_seats: int
    price: PriceOut

    @classmethod
    def from_domain(cls, deal: DealView) -> "DealOut":
        return cls(
            flight_id=deal.flight.id,
            flight_number=deal.flight.flight_number,
            airline=deal.flight.airline,
            origin=deal.flight.origin,
            destination=deal.flight.destination,
            departure_time=deal.flight.departure_time,
            cabin_class=deal.inventory.cabin_class,
            empty_seats=deal.inventory.empty_seats,
            price=PriceOut(**deal.price.to_dict()),
        )


class CreateBookingRequest(BaseModel):
    flight_id: str
    cabin_class: CabinClass


class BookingOut(BaseModel):
    id: str
    flight_id: str
    cabin_class: CabinClass
    status: str
    token_amount: MoneyOut
    tax_amount: MoneyOut
    total_amount: MoneyOut
    checkout_url: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, booking: Booking) -> "BookingOut":
        return cls(
            id=booking.id,
            flight_id=booking.flight_id,
            cabin_class=booking.cabin_class,
            status=booking.status.value,
            token_amount=MoneyOut(**booking.token_amount.to_dict()),
            tax_amount=MoneyOut(**booking.tax_amount.to_dict()),
            total_amount=MoneyOut(**booking.total_amount.to_dict()),
            checkout_url=booking.checkout_url,
            created_at=booking.created_at,
        )


class SubscribeRequest(BaseModel):
    tier: CabinClass


class CheckoutOut(BaseModel):
    session_id: str
    checkout_url: str


class RazorpayOrderOut(BaseModel):
    key_id: str
    order_id: str
    amount: int
    currency: str


class RazorpayBookingOrderRequest(BaseModel):
    booking_id: str


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


class SubscriptionOut(BaseModel):
    tier: CabinClass
    status: str
    started_at: datetime
    renews_at: datetime | None


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
