"""
/v1/ocean/benchmark endpoint.

Returns JSON comparison between OceanEmbed Model, ARMOR3D (climatology),
and In-Situ ARGO ground truth for a specific spatial location.

Status: SKELETON — returns placeholder data while the multi-source
comparison pipeline is under development.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...infrastructure.dependencies import get_zarr_resolver
from ...infrastructure.zarr.resolver import ZarrStoreResolver

router = APIRouter(tags=["Ocean — Benchmark"])


class BenchmarkResponseSchema(BaseModel):
    lat: float
    lon: float
    depths: list[float]
    model_values: list[float]
    argo_values: list[float | None]
    armor3d_values: list[float | None]


@router.get(
    "/benchmark",
    response_model=BenchmarkResponseSchema,
    summary="Model vs ARMOR3D vs ARGO comparison (SKELETON)",
    description="⚠️ This endpoint currently returns placeholder data. "
                "The multi-source comparison pipeline is under development.",
)
async def get_benchmark(
    lat: float,
    lon: float,
    week: str | None = None,
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
) -> dict:
    """Return JSON comparison between Model, ARMOR3D, and ARGO.

    TODO: Implement real comparison:
    1. Query Zarr store for OceanEmbed model profile at (lat, lon)
    2. Query PostGIS for nearest ARGO profile
    3. Query ARMOR3D climatology dataset
    4. Align all three on the same depth levels
    5. Return comparison data
    """
    depths = [0.0, 5.0, 10.0, 20.0, 50.0]
    return {
        "lat": lat,
        "lon": lon,
        "depths": depths,
        "model_values": [28.5, 28.2, 27.9, 27.1, 25.4],
        "argo_values": [28.4, 28.3, 27.8, None, 25.1],
        "armor3d_values": [28.0, 28.0, 27.5, 27.0, 26.0],
    }
