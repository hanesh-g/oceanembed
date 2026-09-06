"""
/v1/ocean/health and /v1/ocean/weeks endpoints.

These expose the model run audit trail and current live week status.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database.session import async_session
from ..schemas import WeekStatusSchema, RunEntrySchema
from ..services.postgis_queries import get_current_live_week, get_all_runs

router = APIRouter(tags=["Ocean — Health"])


@router.get("/health", response_model=WeekStatusSchema)
async def get_ocean_health(
    session: AsyncSession = Depends(async_session),
) -> dict:
    """Return the current live week status.

    This is the endpoint the frontend calls on load to populate the header
    (analysis week, model version, gate status).
    """
    run = await get_current_live_week(session)
    if run is None:
        return {
            "week_label": "no-data",
            "model_version": "unknown",
            "gate_status": "stale",
            "source_window": "",
            "published_at": "",
        }

    return {
        "week_label": run["week_label"],
        "model_version": run["model_version"],
        "gate_status": run["gate_status"],
        "source_window": "",  # TODO: compute from run_date
        "published_at": str(run.get("published_at", "")),
    }


@router.get("/weeks", response_model=list[RunEntrySchema])
async def get_ocean_weeks(
    session: AsyncSession = Depends(async_session),
    limit: int = 52,
) -> list[dict]:
    """Return the gate audit trail — most recent 52 runs (one year)."""
    runs = await get_all_runs(session, limit=limit)
    return [
        {
            "week_label": r["week_label"],
            "run_date": str(r["run_date"]),
            "model_version": r["model_version"],
            "gate_status": r["gate_status"],
            "published_at": str(r.get("published_at", "")) if r.get("published_at") else None,
        }
        for r in runs
    ]
