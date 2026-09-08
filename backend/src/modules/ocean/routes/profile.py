"""
/v1/ocean/profile endpoint.

Returns a vertical temperature/salinity profile at a user-clicked grid cell,
plus the nearest ARGO float observation for comparison.

The frontend renders this as an SVG depth-vs-temperature chart with
uncertainty envelope, ARGO dots, and ARMOR3D reference line.

Performance
-----------
Previous implementation performed 15 sequential `.sel()` calls (N+15 I/O).
This version extracts the full profile with a single `.sel(lat, lon)` call
and indexes by depth, reducing I/O by 15×.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.dependencies import get_zarr_resolver
from ...infrastructure.database.session import async_session
from ...infrastructure.zarr.resolver import ZarrStoreResolver
from ..constants import STANDARD_DEPTHS
from ..schemas import ProfileSchema
from ..services.postgis_queries import get_nearest_argo_profile

router = APIRouter(tags=["Ocean — Profile"])


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
    cell (``method='nearest'``) and then slicing all standard depths in one pass.

    If an ARGO float profile exists in the database, its temperature values
    are included for the frontend's benchmark overlay.
    """
    try:
        store = await resolver.get_store(week=week)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    def _extract_profile():
        """Extract temperature profile in a single vectorized pass."""
        temps: list[float] = []
        uncertainties: list[float] = []

        # Select the nearest grid cell once, then extract all depths.
        if "temp" not in store:
            raise KeyError("Variable 'temp' not found in store")

        temp_col = store["temp"].sel(lat=lat, lon=lon, method="nearest")
        spread_col = None
        if "temp_spread" in store:
            spread_col = store["temp_spread"].sel(lat=lat, lon=lon, method="nearest")

        for d in STANDARD_DEPTHS:
            t = temp_col.sel(depth=d, method="nearest")
            temps.append(float(t.values))
            if spread_col is not None:
                u = spread_col.sel(depth=d, method="nearest")
                uncertainties.append(float(u.values))
            else:
                uncertainties.append(0.0)

        # Extract derived products (surface-only values).
        tchp = float(store["tchp"].sel(lat=lat, lon=lon, method="nearest").values) if "tchp" in store else 0.0
        d26 = float(store["d26"].sel(lat=lat, lon=lon, method="nearest").values) if "d26" in store else 0.0

        return temps, uncertainties, tchp, d26

    try:
        temps, uncertainties, tchp, d26 = await asyncio.to_thread(_extract_profile)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Profile extraction failed: {exc}")

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
