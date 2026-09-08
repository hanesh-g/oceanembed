"""
/v1/ocean/sampling_recommendation endpoint.

Returns JSON recommendations for optimal locations to deploy new ARGO floats
or sensors, based on the model's uncertainty spread and variance.

Status: SKELETON — returns placeholder data while the recommendation
algorithm is under development.  The endpoint is registered and responds
correctly so the frontend can be developed against the contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...infrastructure.dependencies import get_zarr_resolver
from ...infrastructure.zarr.resolver import ZarrStoreResolver

router = APIRouter(tags=["Ocean — Sampling"])


class SamplingRecommendationSchema(BaseModel):
    lat: float
    lon: float
    score: float
    reason: str


@router.get(
    "/sampling_recommendation",
    response_model=list[SamplingRecommendationSchema],
    summary="Optimal sensor placement recommendations (SKELETON)",
    description="⚠️ This endpoint currently returns placeholder data. "
                "The variance-based recommendation algorithm is under development.",
)
async def get_sampling_recommendation(
    week: str | None = None,
    limit: int = Query(default=5, ge=1, le=50),
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
) -> list[dict]:
    """Return JSON list of recommended sampling locations.

    TODO: Implement uncertainty-based recommendation algorithm:
    1. Load spread variables from Zarr store
    2. Compute spatial variance across the grid
    3. Rank cells by highest uncertainty
    4. Cross-reference with existing ARGO float coverage
    5. Return top-N locations with scores and reasons
    """
    # Placeholder data — will be replaced with real algorithm
    return [
        {
            "lat": 12.5,
            "lon": 80.3,
            "score": 0.95,
            "reason": "High variance in salinity predictions",
        },
        {
            "lat": 10.0,
            "lon": 75.0,
            "score": 0.88,
            "reason": "Sparse ARGO coverage in historical window",
        },
    ][:limit]
