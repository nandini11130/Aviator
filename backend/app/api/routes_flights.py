from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.api.schemas import DealOut
from app.container import Container
from app.domain.value_objects import CabinClass

router = APIRouter(prefix="/api/flights", tags=["flights"])


@router.get("/empty-seats", response_model=list[DealOut])
def list_empty_seat_deals(
    cabin_class: CabinClass | None = None,
    container: Container = Depends(get_container),
) -> list[DealOut]:
    deals = container.search_deals.execute(cabin_class)
    return [DealOut.from_domain(deal) for deal in deals]
