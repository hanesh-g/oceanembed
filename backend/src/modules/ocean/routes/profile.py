"""
/v1/ocean/profile endpoint.

Returns a vertical temperature/salinity profile at a user-clicked grid cell,
plus the nearest ARGO float observation for comparison.

The frontend renders this as an SVG depth-vs-temperature chart with
uncertainty envelope, ARGO dots, and ARMOR3D reference line.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.dependencies import get_zarr_resolver
from ...infrastructure.database.session import async_session
from ...infrastructure.zarr.resolver import ZarrStoreResolver
from ..schemas import ProfileSchema
from ..services.postgis_queries import get_nearest_argo_profile

router = APIRouter(tags=["Ocean — Profile"])

# Standard depth levels matching the frontend's DEPTHS constant.
STANDARD_DEPTHS = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]


@router.get("/profile", response_model=ProfileSchema)
async def get_profile(
    lat: float,
    lon: float,
    week: str | None = None,
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
    session: AsyncSession = Depends(async_session),
) -> dict:
    """Return a 15-depth vertical profile at (lat, lon) with nearest ARGO comparison.

    The profile is extracted from the Zarr store by selecting the nearest grid
    cell (``method='nearest'``) at each of the 15 standard depth levels.

    If an ARGO float profile exists in the database, its temperature values
    are included for the frontend's benchmark overlay.
    """
    store = await resolver.get_store(week=week)

    # Extract temperature and spread at each standard depth.
    temps: list[float] = []
    uncertainties: list[float] = []
    for d in STANDARD_DEPTHS:
        t = store["temp"].sel(lat=lat, lon=lon, depth=d, method="nearest")
        temps.append(float(t.values))
        if "temp_spread" in store:
            u = store["temp_spread"].sel(lat=lat, lon=lon, depth=d, method="nearest")
            uncertainties.append(float(u.values))
        else:
            uncertainties.append(0.0)

    # Extract derived products (surface-only values).
    tchp = float(store["tchp"].sel(lat=lat, lon=lon, method="nearest").values) if "tchp" in store else 0.0
    d26 = float(store["d26"].sel(lat=lat, lon=lon, method="nearest").values) if "d26" in store else 0.0

    # Nearest ARGO profile from PostGIS.
    argo_row = await get_nearest_argo_profile(session, lat=lat, lon=lon)
    argo_temps: list[float] | None = None
    nearest_argo_km = 0.0
    if argo_row:
        argo_temps = argo_row.get("temp_values")
        # dist_deg is approximate degrees; convert to km (1° ≈ 111 km)
        nearest_argo_km = (argo_row.get("dist_deg", 0.0) or 0.0) * 111.0

    return {
        "location": {"lat": lat, "lon": lon},
        "depths": STANDARD_DEPTHS,
        "temperature": temps,
        "uncertainty": uncertainties,
        "argo": argo_temps,
        "armor3d": None,  # ARMOR3D comparison is a future phase
        "tchp": tchp,
        "d26": d26,
        "nearest_argo_km": nearest_argo_km,
    }
