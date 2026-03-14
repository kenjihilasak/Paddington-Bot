"""Exchange offer routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_exchange_service
from app.db.models import RecordStatus
from app.schemas.exchange_offer import ExchangeOfferCreate, ExchangeOfferRead
from app.services.exchange_service import ExchangeService


router = APIRouter(prefix="/api/exchange-offers", tags=["exchange-offers"])


@router.get("", response_model=list[ExchangeOfferRead])
async def list_exchange_offers(
    offer_currency: str | None = Query(default=None),
    want_currency: str | None = Query(default=None),
    location: str | None = Query(default=None),
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
    active_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ExchangeService = Depends(get_exchange_service),
) -> list[ExchangeOfferRead]:
    offers = await service.list_offers(
        offer_currency=offer_currency,
        want_currency=want_currency,
        location=location,
        status=status_filter,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return [ExchangeOfferRead.model_validate(item) for item in offers]


@router.post("", response_model=ExchangeOfferRead, status_code=status.HTTP_201_CREATED)
async def create_exchange_offer(
    payload: ExchangeOfferCreate,
    service: ExchangeService = Depends(get_exchange_service),
) -> ExchangeOfferRead:
    offer = await service.create_offer(payload)
    return ExchangeOfferRead.model_validate(offer)

