"""Summary routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_summary_service
from app.schemas.summary import SummaryResponse
from app.services.summary_service import SummaryService


router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=SummaryResponse)
async def get_summary(service: SummaryService = Depends(get_summary_service)) -> SummaryResponse:
    """Return an aggregated summary of active offers, listings, and events."""

    return await service.get_summary()

