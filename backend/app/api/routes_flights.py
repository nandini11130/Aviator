from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_container
from app.api.schemas import DealOut
from app.application.use_cases import parse_departure_datetime
from app.config import get_settings
from app.container import Container
from app.domain.value_objects import CabinClass
from app.infrastructure.firestore_repositories import FlightDataRefreshError

router = APIRouter(prefix="/api/flights", tags=["flights"])


@router.get("/empty-seats", response_model=list[DealOut])
def list_empty_seat_deals(
    cabin_class: CabinClass | None = None,
    origin: str = Query(default="", max_length=3),
    destination: str = Query(default="", max_length=3),
    airline: str = Query(default="", max_length=80),
    departure_after: str | None = None,
    departure_before: str | None = None,
    container: Container = Depends(get_container),
) -> list[DealOut]:
    try:
        parsed_departure_after = parse_departure_datetime(departure_after)
        parsed_departure_before = parse_departure_datetime(
            departure_before, end_of_day=True
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Departure filters must be ISO-8601 timestamps or dates.",
        ) from exc
    if (
        parsed_departure_after
        and parsed_departure_before
        and parsed_departure_after > parsed_departure_before
    ):
        raise HTTPException(
            status_code=422,
            detail="departure_after must be earlier than departure_before.",
        )
    try:
        container.refresh_flights()
    except (httpx.HTTPError, FlightDataRefreshError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Flight schedules could not be refreshed. Please try again later.",
        ) from exc
    deals = container.search_deals.execute(
        cabin_class,
        origin=origin,
        destination=destination,
        airline=airline,
        departure_after=parsed_departure_after,
        departure_before=parsed_departure_before,
    )
    return [
        DealOut.from_domain(deal, get_settings().flight_data_provider)
        for deal in deals
    ]
