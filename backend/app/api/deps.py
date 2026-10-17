"""Composition root: the one place that decides which concrete adapters
(in-memory vs Firestore, mock vs Stripe) satisfy each domain port, and wires
them into use cases. FastAPI route handlers and ADK agent tools only ever see
the abstract `Container`/ports, never these concrete classes directly.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException, status

from app.agents import tools as agent_tools
from app.agents.concierge_agent import build_root_agent
from app.application.use_cases import (
    CalculatePriceUseCase,
    ConfirmPaymentUseCase,
    CreateBookingUseCase,
    ManageSubscriptionUseCase,
    SearchEmptySeatDealsUseCase,
)
from app.config import Settings, get_settings
from app.container import Container
from app.domain.ports import FlightDataProvider, PaymentGateway
from app.infrastructure.auth import init_firebase, verify_firebase_token
from app.infrastructure.flight_data_providers import (
    AmadeusFlightOffersProvider,
    AviationStackFlightDataProvider,
    MockFlightDataProvider,
)
from app.infrastructure.memory_repositories import (
    InMemoryBookingRepository,
    InMemoryFlightRepository,
    InMemorySubscriptionRepository,
)
from app.infrastructure.payment_gateways import (
    MockPaymentGateway,
    RazorpayPaymentGateway,
    StripePaymentGateway,
)
from app.infrastructure.tax_calculators import IndiaGstCalculator
from google.adk.runners import InMemoryRunner


def _build_flight_provider(settings: Settings) -> FlightDataProvider:
    if settings.flight_data_provider == "amadeus":
        if not settings.amadeus_api_key or not settings.amadeus_api_secret:
            raise ValueError("Amadeus is selected but its API credentials are not configured.")
        return AmadeusFlightOffersProvider(
            settings.amadeus_api_key,
            settings.amadeus_api_secret,
            settings.amadeus_environment,
        )
    if settings.flight_data_provider == "aviationstack":
        if not settings.aviationstack_api_key:
            raise ValueError(
                "AviationStack is selected but AVIATIONSTACK_API_KEY is not configured."
            )
        return AviationStackFlightDataProvider(settings.aviationstack_api_key)
    return MockFlightDataProvider()


def _build_payment_gateway(settings: Settings) -> PaymentGateway:
    if settings.razorpay_key_id:
        return RazorpayPaymentGateway(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret,
            webhook_secret=settings.razorpay_webhook_secret,
            callback_url=settings.razorpay_callback_url,
        )
    if settings.stripe_secret_key:
        return StripePaymentGateway(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
            success_url=settings.stripe_success_url,
            cancel_url=settings.stripe_cancel_url,
        )
    return MockPaymentGateway()


@lru_cache
def get_container() -> Container:
    settings = get_settings()
    tax_calculator = IndiaGstCalculator()
    provider = _build_flight_provider(settings)
    payment_gateway = _build_payment_gateway(settings)

    if settings.is_local:
        flight_repo = InMemoryFlightRepository(provider)
        booking_repo = InMemoryBookingRepository()
        subscription_repo = InMemorySubscriptionRepository()
        refresh_flights = lambda: None
    else:
        from google.cloud import firestore

        from app.infrastructure.firestore_repositories import (
            FirestoreBookingRepository,
            FirestoreFlightRepository,
            FirestoreSubscriptionRepository,
        )

        client = firestore.Client(project=settings.google_cloud_project)
        flight_repo = FirestoreFlightRepository(client, settings.flight_data_provider)
        refresh_flights = lambda: flight_repo.refresh_if_stale(provider)
        booking_repo = FirestoreBookingRepository(client)
        subscription_repo = FirestoreSubscriptionRepository(client)
        init_firebase(settings.firebase_project_id)

    container = Container(
        search_deals=SearchEmptySeatDealsUseCase(flight_repo, tax_calculator),
        calculate_price=CalculatePriceUseCase(tax_calculator),
        create_booking=CreateBookingUseCase(
            flight_repo, booking_repo, subscription_repo, tax_calculator, payment_gateway
        ),
        confirm_payment=ConfirmPaymentUseCase(booking_repo, subscription_repo),
        manage_subscription=ManageSubscriptionUseCase(
            subscription_repo, payment_gateway, settings.gst_currency
        ),
        booking_repo=booking_repo,
        subscription_repo=subscription_repo,
        payment_gateway=payment_gateway,
        refresh_flights=refresh_flights,
    )
    agent_tools.bind_container(container)
    return container


@lru_cache
def get_agent_runner() -> InMemoryRunner:
    get_container()  # ensure agent tools are bound to the container first
    settings = get_settings()
    root_agent = build_root_agent(settings)
    return InMemoryRunner(agent=root_agent, app_name="aviator")


def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    """Resolves the caller's user id. Production verifies a real Firebase ID
    token; local development trusts an `X-User-Id` header so the whole stack
    runs without any Firebase project configured.
    """
    settings = get_settings()
    if settings.is_local:
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-User-Id header (local dev auth mode).",
            )
        return x_user_id

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    return verify_firebase_token(authorization.removeprefix("Bearer "))
