"""Conversational entry point: a single endpoint that forwards chat messages
to the ADK root agent (`aviator_concierge`), which in turn routes to the four
specialist sub-agents. The REST endpoints in the other route modules remain
available for a traditional UI; this one powers the chat widget.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from google.adk.runners import InMemoryRunner
from google.genai.errors import APIError
from google.genai import types

from app.api.deps import get_agent_runner, get_container, get_current_user_id
from app.api.schemas import ChatRequest, ChatResponse
from app.application.airport_codes import find_airport_codes
from app.agents.tools import authenticated_user
from app.domain.value_objects import CabinClass
from app.container import Container
from app.infrastructure.firestore_repositories import FlightDataRefreshError

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)

_APP_NAME = "aviator"
_AGENT_TIMEOUT_SECONDS = 60
_FLIGHT_INTENT = re.compile(r"\b(flights?|airfare|fly|flying|route)\b", re.IGNORECASE)
_BOOKING_INTENT = re.compile(
    r"\b(book|reserve|purchase|buy|checkout|pay)\b", re.IGNORECASE
)
_DETAILED_FLIGHT_FILTER = re.compile(
    r"\b(?:airline|depart|departure|arrive|arrival|morning|afternoon|evening|"
    r"night|today|tomorrow|tonight|after|before|earliest|latest|most seats|"
    r"more seats|flight number|next week|next month)\b"
    r"|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_ROUTE_SEPARATOR = re.compile(r"\bfrom\b(.*?)\bto\b(.*)", re.IGNORECASE)
_BETWEEN_SEPARATOR = re.compile(r"\bbetween\b(.*?)\band\b(.*)", re.IGNORECASE)
_DESTINATION_ONLY = re.compile(r"\b(?:to|toward|towards)\b(.*)", re.IGNORECASE)
_ORIGIN_ONLY = re.compile(r"\bfrom\b(.*)", re.IGNORECASE)
_FILTER_WORDS = re.compile(
    r"\b(?:in|on|after|before|with|by|departing|leaving|tomorrow|today|next|this)\b",
    re.IGNORECASE,
)


def _airport_filter(text: str, *, last: bool = False) -> str:
    phrase = _FILTER_WORDS.split(text, maxsplit=1)[0]
    airports = find_airport_codes(phrase)
    if not airports:
        return ""
    return airports[-1 if last else 0][0]


def _extract_flight_route(message: str) -> tuple[str, str, CabinClass | None] | None:
    if (
        not _FLIGHT_INTENT.search(message)
        or _BOOKING_INTENT.search(message)
        or _DETAILED_FLIGHT_FILTER.search(message)
    ):
        return None

    route = _ROUTE_SEPARATOR.search(message)
    between = _BETWEEN_SEPARATOR.search(message)
    if route or between:
        route_parts = route or between
        assert route_parts is not None
        origin = _airport_filter(route_parts.group(1), last=True)
        destination = _airport_filter(route_parts.group(2))
    else:
        origin_match = _ORIGIN_ONLY.search(message)
        destination_match = _DESTINATION_ONLY.search(message)
        origin = _airport_filter(origin_match.group(1), last=True) if origin_match else ""
        destination = (
            _airport_filter(destination_match.group(1))
            if destination_match
            else ""
        )
        if (
            not origin
            and not _ORIGIN_ONLY.search(message)
            and re.search(r"\bto\b", message, re.IGNORECASE)
        ):
            airports = find_airport_codes(message)
            if len(airports) >= 2:
                origin, destination = airports[0][0], airports[-1][0]

    if not origin and not destination:
        return None

    cabin = None
    if re.search(r"\bfirst(?:\s+class)?\b", message, re.IGNORECASE):
        cabin = CabinClass.FIRST
    elif re.search(r"\bbusiness(?:\s+class)?\b", message, re.IGNORECASE):
        cabin = CabinClass.BUSINESS
    elif re.search(r"\beconomy(?:\s+class)?\b", message, re.IGNORECASE):
        cabin = CabinClass.ECONOMY
    return origin, destination, cabin


def _format_flight_search(
    container: Container,
    origin: str,
    destination: str,
    cabin: CabinClass | None,
) -> str:
    try:
        container.refresh_flights()
    except (httpx.HTTPError, FlightDataRefreshError) as exc:
        logger.warning("Flight schedule refresh failed during concierge search: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flight schedules are temporarily unavailable. Please try again.",
            headers={"Retry-After": "60"},
        ) from exc

    deals = container.search_deals.execute(
        cabin,
        origin=origin,
        destination=destination,
    )
    if not deals:
        route = " → ".join(code for code in (origin, destination) if code)
        return (
            f"I couldn’t find scheduled flights for **{route}** in the current "
            "schedule data. Try another airport code or route. Seat availability "
            "and prices are estimates, not confirmed airline inventory or fares."
        )

    deals.sort(key=lambda deal: deal.price.total.amount_minor)
    rows = [
        "| Flight | Route | Departure (IST) | Cabin | Estimated seats | Estimated total |",
        "|---|---|---|---|---:|---:|",
    ]
    for deal in deals[:10]:
        departure = deal.flight.departure_time.astimezone(
            ZoneInfo("Asia/Kolkata")
        ).strftime("%d %b %Y, %I:%M %p")
        rows.append(
            f"| {deal.flight.flight_number} · {deal.flight.airline} "
            f"| {deal.flight.origin} → {deal.flight.destination} "
            f"| {departure} | {deal.inventory.cabin_class.value} "
            f"| {deal.inventory.empty_seats} "
            f"| {deal.price.total.currency} "
            f"{deal.price.total.amount_minor / 100:,.2f} |"
        )

    if len(deals) > 10:
        rows.append(f"\nShowing 10 of {len(deals)} matching options.")
    rows.append(
        "\nThese are scheduled flights with estimated seat counts and prices, "
        "not confirmed airline availability or fares. Which cabin or date "
        "would you like to compare?"
    )
    return "\n".join(rows)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    runner: InMemoryRunner = Depends(get_agent_runner),
    container: Container = Depends(get_container),
) -> ChatResponse:
    flight_route = _extract_flight_route(request.message)
    if flight_route:
        origin, destination, cabin = flight_route
        return ChatResponse(
            session_id=request.session_id or str(uuid.uuid4()),
            reply=_format_flight_search(container, origin, destination, cabin),
        )

    session_id = request.session_id or str(uuid.uuid4())
    session = await runner.session_service.get_session(
        app_name=_APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await runner.session_service.create_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )

    message = types.Content(
        role="user", parts=[types.Part.from_text(text=request.message)]
    )

    reply_parts: list[str] = []
    try:
        async with asyncio.timeout(_AGENT_TIMEOUT_SECONDS):
            with authenticated_user(user_id):
                async for event in runner.run_async(
                    user_id=user_id, session_id=session.id, new_message=message
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                reply_parts.append(part.text)
    except TimeoutError as exc:
        logger.warning("ADK chat timed out after %s seconds.", _AGENT_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Aviator AI took too long to respond. Please try again.",
        ) from exc
    except APIError as exc:
        if exc.code in (429, 503):
            logger.warning("Vertex AI is temporarily at capacity (status=%s).", exc.code)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Aviator AI is temporarily at capacity. Please try again in a minute.",
                headers={"Retry-After": "60"},
            ) from exc
        logger.exception("The ADK chat request failed (AI provider status=%s).", exc.code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Aviator AI could not process that request. Please try again.",
        ) from exc

    reply = "".join(reply_parts).strip()
    if not reply:
        logger.warning("ADK chat completed without returning a text response.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Aviator AI did not return an answer. Please try again.",
        )

    return ChatResponse(session_id=session.id, reply=reply)
