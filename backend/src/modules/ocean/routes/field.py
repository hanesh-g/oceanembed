"""
/v1/ocean/field and /v1/ocean/field_json endpoints.

Two flavours:
  - /field       → raw float32 binary (future high-performance clients)
  - /field_json  → JSON FieldPoint[] (dashboard GeoJSON rendering)

Performance
-----------
The 0.25° domain is 100×240 = 24,000 cells per depth.  Serializing all 24K
as JSON objects produces ~3.5 MB — too heavy for dashboard slider drags.

The /field_json endpoint downsamples by a stride factor (default 4 → ~1.0°)
to produce ~1,500 points (< 120 KB), which MapLibre renders at 60 FPS.

The downsampling is done via xarray .isel() striding, then vectorized via
NumPy .flat iteration — NO nested Python loops in the event loop.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ...infrastructure.dependencies import get_zarr_resolver
from ...infrastructure.zarr.resolver import ZarrStoreResolver
from ..schemas import FieldPointSchema

router = APIRouter(tags=["Ocean — Field"])


@router.get("/field")
async def get_field(
    variable: str,
    week: str | None = None,
    depth: float | None = None,
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
) -> Response:
    """Return raw float32 binary for the requested variable.

    - ``depth`` omitted → full 3D volume (lat × lon × depth)
    - ``depth`` provided → 2D slice (lat × lon)

    X-Shape header always encodes ALL returned dimensions.
    """
    store = await resolver.get_store(week=week)
    da = store[variable]

    if depth is not None:
        da = da.sel(depth=depth, method="nearest")
        buf = da.values.astype("float32").tobytes()
        shape_header = f"{da.shape[0]},{da.shape[1]}"
    else:
        buf = da.values.astype("float32").tobytes()
        shape_header = ",".join(str(s) for s in da.shape)

    return Response(
        content=buf,
        media_type="application/octet-stream",
        headers={
            "X-Shape": shape_header,
            "X-Variable": variable,
            "X-Model-Version": store.attrs.get("model_version", "unknown"),
            "X-Week": store.attrs.get("week_label", "unknown"),
        },
    )


@router.get("/field_json", response_model=list[FieldPointSchema])
async def get_field_json(
    variable: str,
    depth: float,
    week: str | None = None,
    stride: int = Query(default=4, ge=1, le=20, description="Spatial stride factor for downsampling"),
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
) -> list[dict]:
    """Return a downsampled JSON grid for MapLibre GeoJSON rendering.

    Downsamples the 0.25° grid by ``stride`` (default 4 → ~1.0° → ~1,500 points).
    Each point has {lat, lon, value, uncertainty}.

    The frontend maps FieldId names to backend variable names in the API client;
    this endpoint receives the backend variable name directly.
    """
    store = await resolver.get_store(week=week)
    da = store[variable].sel(depth=depth, method="nearest")

    # Downsample via stride — no interpolation, fast and exact.
    da_sub = da.isel(lat=slice(None, None, stride), lon=slice(None, None, stride))

    # Try to find the matching uncertainty/spread variable.
    spread_var = f"{variable}_spread"
    if spread_var in store:
        spread = store[spread_var].sel(depth=depth, method="nearest")
        spread_sub = spread.isel(lat=slice(None, None, stride), lon=slice(None, None, stride))
    else:
        spread_sub = None

    # Vectorized meshgrid — NO nested Python loops.
    lats, lons = np.meshgrid(
        da_sub.coords["lat"].values,
        da_sub.coords["lon"].values,
        indexing="ij",
    )

    values = da_sub.values
    uncertainties = spread_sub.values if spread_sub is not None else np.zeros_like(values)

    return [
        {"lat": float(lat), "lon": float(lon), "value": float(val), "uncertainty": float(unc)}
        for lat, lon, val, unc in zip(
            lats.flat, lons.flat, values.flat, uncertainties.flat
        )
    ]
