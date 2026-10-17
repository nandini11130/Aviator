"""The composition root's output type: a single immutable bag of use cases
that both the REST API layer and the ADK agent tools depend on. Building one
`Container` (see `app/api/deps.py`) is the only place in the codebase that
knows which concrete infrastructure adapters are in play.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.application.use_cases import (
    CalculatePriceUseCase,
    ConfirmPaymentUseCase,
    CreateBookingUseCase,
    ManageSubscriptionUseCase,
    SearchEmptySeatDealsUseCase,
)
from app.domain.ports import BookingRepository, PaymentGateway, SubscriptionRepository


@dataclass(frozen=True, slots=True)
class Container:
    search_deals: SearchEmptySeatDealsUseCase
    calculate_price: CalculatePriceUseCase
    create_booking: CreateBookingUseCase
    confirm_payment: ConfirmPaymentUseCase
    manage_subscription: ManageSubscriptionUseCase
    booking_repo: BookingRepository
    subscription_repo: SubscriptionRepository
    payment_gateway: PaymentGateway
    refresh_flights: Callable[[], None]
