"""
regrid.py — Regrid satellite / model fields to the standard 0.25° OceanEmbed grid.

STUB — replace body with real implementation once the training team hands off
the preprocessing code.  The interface (function signatures + return types) is
final and must not change; only the body changes.

Domain: 5°N – 30°N, 45°E – 105°E at 0.25° resolution.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from .channels import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, RESOLUTION


def target_grid() -> tuple[np.ndarray, np.ndarray]:
    """Return the (lats, lons) arrays for the standard OceanEmbed 0.25° grid."""
    lats = np.arange(LAT_MIN, LAT_MAX + RESOLUTION / 2, RESOLUTION, dtype="float32")
    lons = np.arange(LON_MIN, LON_MAX + RESOLUTION / 2, RESOLUTION, dtype="float32")
    return lats, lons


def regrid_to_standard(ds: xr.Dataset) -> xr.Dataset:
    """Regrid *ds* to the standard OceanEmbed 0.25° lat/lon grid.

    Parameters
    ----------
    ds:
        Input xr.Dataset with ``lat`` and ``lon`` coordinates.  May be on an
        arbitrary grid (e.g. native CMEMS 1/12° or satellite swath).

    Returns
    -------
    xr.Dataset
        Dataset interpolated / regridded to the standard target grid.

    Notes
    -----
    STUB: currently performs a simple nearest-neighbour interpolation via
    ``xr.Dataset.interp``.  Replace with a proper conservative or bilinear
    regridder (e.g. xesmf) once validated against the training pipeline.
    """
    lats, lons = target_grid()
    return ds.interp(lat=lats, lon=lons, method="nearest")
