"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_redis_client
from app.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
) -> HealthResponse:
    """Return service health status."""

    database_status = "ok"
    redis_status = "ok"

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    try:
        await redis_client.ping()
    except Exception:
        redis_status = "error"

    status = "ok" if database_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(status=status, database=database_status, redis=redis_status)
