"""
Pydantic response schemas for the OceanEmbed /v1/ocean/* endpoints.

These are the wire-format contracts consumed by the React frontend.
The frontend's TypeScript types (in api/types.ts) must stay in sync.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /field_json
# ---------------------------------------------------------------------------

class FieldPointSchema(BaseModel):
    """Single grid cell for GeoJSON rendering in MapLibre."""
    lat: float
    lon: float
    value: float | None
    uncertainty: float | None


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------

class ProfileSchema(BaseModel):
    """Vertical temperature / salinity profile at a single grid cell.

    Matches the frontend's ``Profile`` TypeScript type exactly.
    """
    location: dict[str, float]  # {lat, lon}
    depths: list[float]
    temperature: list[float]
    uncertainty: list[float]
    argo: list[float] | None = None
    armor3d: list[float] | None = None
    tchp: float
    d26: float
    nearestArgoKm: float = Field(alias="nearest_argo_km", default=0.0)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# /argo_floats
# ---------------------------------------------------------------------------

class ArgoFloatSchema(BaseModel):
    """ARGO float position for the map overlay."""
    lat: float
    lon: float
    id: str
    lastProfile: str = Field(alias="last_profile", default="")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# /health  (maps to frontend RunStatus)
# ---------------------------------------------------------------------------

class WeekStatusSchema(BaseModel):
    """Current live week status — returned by GET /v1/ocean/health."""
    week_label: str
    model_version: str
    gate_status: str
    source_window: str = ""
    published_at: str = ""


class WeeksResponseSchema(BaseModel):
    """Gate audit trail — returned by GET /v1/ocean/weeks."""
    runs: list[RunEntrySchema]


class RunEntrySchema(BaseModel):
    """Single entry in the gate audit trail."""
    week_label: str
    run_date: str
    model_version: str
    gate_status: str
    published_at: str | None = None
