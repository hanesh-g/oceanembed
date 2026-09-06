"""
OceanEmbed database models.

Uses the boilerplate's UUIDMixin + TimestampMixin mixins for consistent
primary keys and timestamps.

GeoAlchemy2 note
----------------
``ArgoProfile.geom`` is typed as ``Geometry(geometry_type='POINT', srid=4326)``.
This is required (not just ``Geometry()``) for PostGIS operators like ``<->``
(nearest-neighbour distance) to work in SQLAlchemy queries WITHOUT manual
ST_GeomFromText casting.  If the column is declared as plain ``Geometry()``
(no srid), PostGIS will cast to ``geography`` implicitly on some queries and
silently switch to a different distance metric.

Always use ST_Point(lon, lat, 4326) — NOT ST_Point(lat, lon) — when building
geometry literals in query helpers; the PostGIS convention is (x, y) = (lon, lat).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin


class Base(MappedAsDataclass, DeclarativeBase):
    """Declarative base for OceanEmbed domain models."""
    pass


class ModelRun(UUIDMixin, TimestampMixin, Base):
    """One row per weekly inference run — pass or fail.

    This table is the gate audit trail exposed by ``GET /v1/ocean/weeks``.
    Every run is recorded regardless of whether it passed the quality gate;
    on a fail the previous week's data stays live (the symlink is not swapped).

    Attributes
    ----------
    week_label:
        ISO week string, e.g. ``"2025-W01"``.  Matches the ``week=YYYY-Www``
        directory name in the published Zarr store.
    run_date:
        UTC timestamp when the inference worker started this run.
    model_version:
        Bundle identifier from the model registry (e.g. ``"oceanembed-v1.0.0"``).
        Included in every API response header so downstream consumers can tell
        which weights produced the data they are looking at.
    gate_status:
        ``"pass"`` or ``"fail"``.
    gate_log:
        JSONB blob written by ``quality_gate.py`` — contains per-channel
        NaN fractions, Z-score summaries, and any failure messages.
    published_at:
        UTC timestamp of the atomic symlink swap.  Null if the gate failed.
    """

    __tablename__ = "model_runs"

    week_label: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    gate_status: Mapped[str] = mapped_column(String(8), nullable=False)  # "pass" | "fail"
    gate_log: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ArgoProfile(UUIDMixin, Base):
    """ARGO float profile with PostGIS point geometry.

    Used by ``GET /v1/ocean/profile`` (nearest neighbour) and
    ``GET /v1/ocean/benchmark`` (model vs ARGO comparison).

    GeoAlchemy2 column
    ------------------
    ``geom`` is declared as ``Geometry(geometry_type='POINT', srid=4326)``.
    This ensures that the PostGIS ``<->`` operator in nearest-neighbour queries:

        ORDER BY geom <-> ST_Point(:lon, :lat, 4326)

    works without any manual casting.  Without the explicit ``srid`` the
    distance metric may silently change to spherical (geography) distance
    on some PostGIS versions, giving subtly wrong ordering near the antimeridian.

    Note the argument order: ``ST_Point(lon, lat, srid)`` — x first, y second.
    """

    __tablename__ = "argo_profiles"

    platform_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    profile_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[float] = mapped_column(nullable=False)
    lon: Mapped[float] = mapped_column(nullable=False)

    # POSIX geometry column — srid=4326 is MANDATORY for <-> operator correctness.
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )

    # Depth levels and profile values stored as JSONB arrays.
    # Shape: [float, ...] with length = number of observed depths.
    depth_levels: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    temp_values: Mapped[list[float | None]] = mapped_column(JSONB, nullable=False)
    sal_values: Mapped[list[float | None]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        # GiST spatial index — required for <-> nearest-neighbour queries to use
        # the index rather than performing a full table scan.
        Index("argo_geom_gist_idx", "geom", postgresql_using="gist"),
    )
