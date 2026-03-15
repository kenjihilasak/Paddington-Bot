"""Listing routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_listing_service
from app.db.models import ListingCategory, RecordStatus
from app.schemas.listing import ListingCreate, ListingRead
from app.services.exceptions import ResourceNotFoundError
from app.services.listing_service import ListingService


router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("", response_model=list[ListingRead])
async def list_listings(
    category: ListingCategory | None = Query(default=None),
    location: str | None = Query(default=None),
    search_text: str | None = Query(default=None),
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
    active_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ListingService = Depends(get_listing_service),
) -> list[ListingRead]:
    listings = await service.list_listings(
        category=category,
        location=location,
        search_text=search_text,
        status=status_filter,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return [ListingRead.model_validate(item) for item in listings]


@router.post("", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    service: ListingService = Depends(get_listing_service),
) -> ListingRead:
    try:
        listing = await service.create_listing(payload)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ListingRead.model_validate(listing)
