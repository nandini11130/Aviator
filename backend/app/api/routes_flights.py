from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_container
from app.api.schemas import DealOut
from app.config import get_settings
from app.container import Container
from app.domain.value_objects import CabinClass
from app.infrastructure.firestore_repositories import FlightDataRefreshError

router = APIRouter(prefix="/api/flights", tags=["flights"])


@router.get("/empty-seats", response_model=list[DealOut])
def list_empty_seat_deals(
    cabin_class: CabinClass | None = None,
    container: Container = Depends(get_container),
) -> list[DealOut]:
    try:
        container.refresh_flights()
    except (httpx.HTTPError, FlightDataRefreshError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Flight schedules could not be refreshed. Please try again later.",
        ) from exc
    deals = container.search_deals.execute(cabin_class)
    return [
        DealOut.from_domain(deal, get_settings().flight_data_provider)
        for deal in deals
    ]
