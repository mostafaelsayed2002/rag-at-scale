from typing import Annotated

from fastapi import APIRouter, Query

from ...db.pool import pool
from ...services.analytics import overview

router = APIRouter(tags=["analytics"])


@router.get("/analytics")
async def analytics(hours: Annotated[int, Query(ge=1, le=720)] = 24):
    """Chat analytics for the last `hours`: latency percentiles, trends, cost and corpus stats."""
    return await overview(pool, hours)
