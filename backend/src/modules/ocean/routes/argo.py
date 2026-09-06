"""
/v1/ocean/argo_floats endpoint.

Returns all ARGO float positions for the MapLibre map overlay layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database.session import async_session
from ..schemas import ArgoFloatSchema

router = APIRouter(tags=["Ocean — ARGO"])


@router.get("/argo_floats", response_model=list[ArgoFloatSchema])
async def get_argo_floats(
    session: AsyncSession = Depends(async_session),
) -> list[dict]:
    """Return all ARGO float positions for the map overlay.

    Each float is returned with its WMO platform ID and the ISO week string
    of its most recent profile.
    """
    result = await session.execute(text("""
        SELECT DISTINCT ON (platform_id)
            platform_id, lat, lon, profile_date
        FROM argo_profiles
        ORDER BY platform_id, profile_date DESC
    """))

    return [
        {
            "lat": float(row.lat),
            "lon": float(row.lon),
            "id": row.platform_id,
            "last_profile": row.profile_date.strftime("%G-W%V") if row.profile_date else "",
        }
        for row in result.all()
    ]
