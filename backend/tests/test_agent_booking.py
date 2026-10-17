from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from google.genai.errors import ClientError

from app.agents import tools
from app.api import routes_agent
from app.api.routes_agent import chat
from app.api.schemas import ChatRequest
from app.application.use_cases import (
    CalculatePriceUseCase,
    ConfirmPaymentUseCase,
    CreateBookingUseCase,
    ManageSubscriptionUseCase,
    SearchEmptySeatDealsUseCase,
)
from app.container import Container
from app.domain.value_objects import CabinClass
from app.infrastructure.flight_data_providers import MockFlightDataProvider
from app.infrastructure.memory_repositories import (
    InMemoryBookingRepository,
    InMemoryDemoPassRepository,
    InMemoryFlightRepository,
    InMemorySubscriptionRepository,
)
from app.infrastructure.payment_gateways import MockPaymentGateway
from app.infrastructure.tax_calculators import IndiaGstCalculator


@pytest.fixture
def agent_booking_container():
    flight_repo = InMemoryFlightRepository(MockFlightDataProvider(seed=42))
    booking_repo = InMemoryBookingRepository()
    subscription_repo = InMemorySubscriptionRepository()
    demo_pass_repo = InMemoryDemoPassRepository()
    gateway = MockPaymentGateway()
    tax_calculator = IndiaGstCalculator()
    manage_subscription = ManageSubscriptionUseCase(subscription_repo, gateway, "INR")
    manage_subscription.activate("authenticated-user", CabinClass.ECONOMY)
    container = Container(
        search_deals=SearchEmptySeatDealsUseCase(flight_repo, tax_calculator),
        calculate_price=CalculatePriceUseCase(tax_calculator),
        create_booking=CreateBookingUseCase(
            flight_repo,
            booking_repo,
            subscription_repo,
            tax_calculator,
            gateway,
            demo_pass_repo,
        ),
        confirm_payment=ConfirmPaymentUseCase(booking_repo, subscription_repo),
        manage_subscription=manage_subscription,
        booking_repo=booking_repo,
        subscription_repo=subscription_repo,
        demo_pass_repo=demo_pass_repo,
        payment_gateway=gateway,
        refresh_flights=lambda: None,
    )
    previous_container = tools._container
    tools.bind_container(container)
    try:
        yield container
    finally:
        tools._container = previous_container


def test_agent_booking_directs_user_to_paid_checkout_without_saving_a_booking(
    agent_booking_container,
):
    deal = agent_booking_container.search_deals.execute(CabinClass.ECONOMY)[0]

    with tools.authenticated_user("authenticated-user"):
        result = tools.book_empty_seat(deal.flight.id, "ECONOMY")

    assert result["error"] == "checkout_required"
    assert "Razorpay checkout" in result["message"]
    assert "estimated total" in result["message"]
    assert (
        agent_booking_container.booking_repo.list_for_user("authenticated-user")
        == []
    )


def test_agent_booking_cannot_choose_another_user_id(agent_booking_container):
    deal = agent_booking_container.search_deals.execute(CabinClass.ECONOMY)[0]

    with tools.authenticated_user("authenticated-user"):
        with pytest.raises(TypeError):
            tools.book_empty_seat(
                "attacker-selected-user",
                deal.flight.id,
                "ECONOMY",
            )

    assert agent_booking_container.booking_repo.list_for_user("attacker-selected-user") == []


def test_chat_runner_booking_uses_authenticated_request_identity(agent_booking_container):
    deal = agent_booking_container.search_deals.execute(CabinClass.ECONOMY)[0]

    class SessionService:
        async def get_session(self, **kwargs):
            return None

        async def create_session(self, **kwargs):
            return SimpleNamespace(id=kwargs["session_id"])

    class BookingRunner:
        session_service = SessionService()

        async def run_async(self, **kwargs):
            tools.book_empty_seat(deal.flight.id, "ECONOMY")
            yield SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            text="Select Book to open secure demo checkout."
                        )
                    ]
                )
            )

    response = asyncio.run(
        chat(
            ChatRequest(message="Book this flight"),
            user_id="authenticated-user",
            runner=BookingRunner(),
        )
    )

    bookings = agent_booking_container.booking_repo.list_for_user("authenticated-user")
    assert response.reply == "Select Book to open secure demo checkout."
    assert bookings == []


def test_chat_returns_retryable_error_when_vertex_ai_is_at_capacity(
    agent_booking_container,
):
    class SessionService:
        async def get_session(self, **kwargs):
            return None

        async def create_session(self, **kwargs):
            return SimpleNamespace(id=kwargs["session_id"])

    class CapacityLimitedRunner:
        session_service = SessionService()

        async def run_async(self, **kwargs):
            if False:
                yield
            raise ClientError(
                429,
                {
                    "error": {
                        "code": 429,
                        "message": "Resource exhausted.",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                },
            )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            chat(
                ChatRequest(message="Hello"),
                user_id="authenticated-user",
                runner=CapacityLimitedRunner(),
            )
        )

    assert raised.value.status_code == 503
    assert raised.value.detail == (
        "Aviator AI is temporarily at capacity. Please try again in a minute."
    )
    assert raised.value.headers == {"Retry-After": "60"}


def test_chat_rejects_empty_agent_reply(agent_booking_container):
    class SessionService:
        async def get_session(self, **kwargs):
            return None

        async def create_session(self, **kwargs):
            return SimpleNamespace(id=kwargs["session_id"])

    class EmptyReplyRunner:
        session_service = SessionService()

        async def run_async(self, **kwargs):
            yield SimpleNamespace(content=None)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            chat(
                ChatRequest(message="Hello"),
                user_id="authenticated-user",
                runner=EmptyReplyRunner(),
            )
        )

    assert raised.value.status_code == 502
    assert raised.value.detail == "Aviator AI did not return an answer. Please try again."


def test_agent_booking_requires_signed_in_user_to_start_paid_checkout(
    agent_booking_container,
):
    deal = agent_booking_container.search_deals.execute(CabinClass.ECONOMY)[0]

    with tools.authenticated_user("user-without-membership"):
        result = tools.book_empty_seat(deal.flight.id, "ECONOMY")

    assert result["error"] == "checkout_required"
    assert (
        agent_booking_container.booking_repo.list_for_user("user-without-membership")
        == []
    )


def test_agent_flight_search_applies_natural_language_search_arguments(
    agent_booking_container,
):
    target = agent_booking_container.search_deals.execute(CabinClass.ECONOMY)[0]

    result = tools.search_empty_seat_deals(
        cabin_class="ECONOMY",
        origin=target.flight.origin.lower(),
        destination=target.flight.destination.lower(),
        airline=target.flight.airline,
        departure_after=target.flight.departure_time.isoformat(),
        departure_before=target.flight.departure_time.isoformat(),
        priority="lowest_price",
    )

    assert result["priority"] == "lowest_price"
    assert result["result_count"] > 0
    assert all(
        deal["origin"] == target.flight.origin
        and deal["destination"] == target.flight.destination
        and deal["airline"] == target.flight.airline
        for deal in result["deals"]
    )
    assert [
        deal["price"]["total"]["amount_minor"] for deal in result["deals"]
    ] == sorted(
        deal["price"]["total"]["amount_minor"] for deal in result["deals"]
    )
