"""
gapfill.py — Fill spatial gaps in satellite fields before model ingestion.

STUB — replace body with real implementation (DINEOF or simpler fallback).
Interface is final.
"""

from __future__ import annotations

import numpy as np
import xarray as xr


def fill_gaps(ds: xr.Dataset, method: str = "nearest") -> xr.Dataset:
    """Fill NaN gaps in all data variables of *ds*.

    Parameters
    ----------
    ds:
        Input dataset, may contain NaNs where satellite observations are
        missing (cloud cover, swath gaps, etc.).
    method:
        Gap-fill strategy.  Supported values:
        - ``"nearest"``  — simple nearest-neighbour interpolation (default,
          fast, adequate for sparse gaps).
        - ``"dineof"``   — DINEOF (not yet implemented; raises NotImplementedError).

    Returns
    -------
    xr.Dataset
        Dataset with NaNs replaced.  Shape and coordinates unchanged.

    Raises
    ------
    NotImplementedError
        If ``method="dineof"`` is requested (placeholder for full implementation).
    ValueError
        If an unrecognised method is requested.

    Notes
    -----
    STUB: nearest-neighbour fill is implemented via ``xr.Dataset.ffill`` +
    ``bfill`` along the lat dimension as a temporary approximation.
    Replace with a proper 2D interpolation or DINEOF once validated.
    """
    if method == "dineof":
        raise NotImplementedError(
            "DINEOF gap-filling is not yet implemented. "
            "Use method='nearest' until the training team provides the implementation."
        )
    if method != "nearest":
        raise ValueError(f"Unsupported gap-fill method: {method!r}")

    # Simple forward/backward fill along lat, then lon.
    # Good enough for small sparse gaps; not suitable for large cloud-masked regions.
    return ds.ffill("lat").bfill("lat").ffill("lon").bfill("lon")


def nan_fraction(ds: xr.Dataset) -> dict[str, float]:
    """Compute the fraction of NaN cells per variable.

    Used by the quality gate to fail runs with excessive missing data.

    Returns
    -------
    dict mapping variable name → fraction of NaN values in [0, 1].
    """
    result: dict[str, float] = {}
    for var in ds.data_vars:
        arr = ds[var].values
        total = arr.size
        if total == 0:
            result[var] = 0.0
        else:
            result[var] = float(np.isnan(arr).sum()) / total
    return result
