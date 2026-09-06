"""
PostGIS query helpers for OceanEmbed API endpoints.

All raw SQL is written here and nowhere else.  Endpoints call these functions
rather than constructing SQL strings inline.

Critical conventions
--------------------
1. Argument order in ST_Point: ``ST_Point(lon, lat, srid)`` — x (longitude)
   BEFORE y (latitude).  This is the PostGIS convention (x, y) and is the
   inverse of the common intuition (lat, lon).  Getting this wrong silently
   gives nearest-neighbour results from the wrong hemisphere.

2. The ``<->`` operator requires a GiST index on the ``geom`` column AND the
   column type must be ``GEOMETRY(POINT, 4326)``.  Without the srid, Postgres
   may not use the index for <-> and will fall back to a full table scan.

3. Queries return SQLAlchemy ``Row`` objects; callers are responsible for
   mapping them to Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# ARGO float queries
# ---------------------------------------------------------------------------

async def get_nearest_argo_profile(
    session: AsyncSession,
    lat: float,
    lon: float,
    *,
    before_date: datetime | None = None,
) -> dict[str, Any] | None:
    """Return the ARGO profile geographically closest to (lat, lon).

    Parameters
    ----------
    session:
        Active async SQLAlchemy session.
    lat:
        Target latitude in decimal degrees (positive = North).
    lon:
        Target longitude in decimal degrees (positive = East).
    before_date:
        If provided, only consider profiles with ``profile_date <= before_date``.
        Use this to ensure benchmark comparisons are not contaminated with
        future observations.

    Returns
    -------
    dict | None
        Row as a dict, or None if the table is empty.

    Notes
    -----
    ``ST_Point(lon, lat, 4326)`` — longitude (x) is the FIRST argument.
    """
    if before_date is not None:
        q = text("""
            SELECT
                uuid, platform_id, profile_date, lat, lon,
                depth_levels, temp_values, sal_values,
                ST_Distance(geom, ST_Point(:lon, :lat, 4326)) AS dist_deg
            FROM argo_profiles
            WHERE profile_date <= :before_date
            ORDER BY geom <-> ST_Point(:lon, :lat, 4326)
            LIMIT 1
        """)
        result = await session.execute(
            q, {"lon": lon, "lat": lat, "before_date": before_date}
        )
    else:
        q = text("""
            SELECT
                uuid, platform_id, profile_date, lat, lon,
                depth_levels, temp_values, sal_values,
                ST_Distance(geom, ST_Point(:lon, :lat, 4326)) AS dist_deg
            FROM argo_profiles
            ORDER BY geom <-> ST_Point(:lon, :lat, 4326)
            LIMIT 1
        """)
        result = await session.execute(q, {"lon": lon, "lat": lat})

    row = result.mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Model run / gate audit queries
# ---------------------------------------------------------------------------

async def get_current_live_week(session: AsyncSession) -> dict[str, Any] | None:
    """Return the most recently published (gate=pass) model run."""
    q = text("""
        SELECT uuid, week_label, run_date, model_version, gate_status, published_at
        FROM model_runs
        WHERE gate_status = 'pass' AND published_at IS NOT NULL
        ORDER BY published_at DESC
        LIMIT 1
    """)
    result = await session.execute(q)
    row = result.mappings().first()
    return dict(row) if row else None


async def get_all_runs(
    session: AsyncSession,
    *,
    limit: int = 52,
) -> list[dict[str, Any]]:
    """Return the gate audit trail, most recent first.

    Parameters
    ----------
    limit:
        Maximum rows to return.  Default 52 covers one year of weekly runs.
    """
    q = text("""
        SELECT
            uuid, week_label, run_date, model_version,
            gate_status, gate_log, published_at, created_at
        FROM model_runs
        ORDER BY run_date DESC
        LIMIT :limit
    """)
    result = await session.execute(q, {"limit": limit})
    return [dict(row) for row in result.mappings().all()]


async def get_run_by_week(
    session: AsyncSession, week_label: str
) -> dict[str, Any] | None:
    """Return the model run record for a specific week label (e.g. '2025-W01')."""
    q = text("""
        SELECT uuid, week_label, run_date, model_version, gate_status, gate_log, published_at
        FROM model_runs
        WHERE week_label = :week_label
        ORDER BY run_date DESC
        LIMIT 1
    """)
    result = await session.execute(q, {"week_label": week_label})
    row = result.mappings().first()
    return dict(row) if row else None
