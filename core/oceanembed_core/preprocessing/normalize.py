"""
normalize.py — Apply scaler.json training statistics to input fields.

STUB — replace body with real implementation.  Interface is final.

scaler.json format (one entry per input channel):
{
  "SST": {"mean": 28.5, "std": 2.1},
  "SSS": {"mean": 35.1, "std": 0.8},
  ...
}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr


def load_scaler(scaler_json_path: str | Path) -> dict[str, dict[str, float]]:
    """Load training mean/std from a model bundle's scaler.json.

    Parameters
    ----------
    scaler_json_path:
        Path to ``scaler.json`` inside the model registry bundle.

    Returns
    -------
    dict mapping channel name → {"mean": float, "std": float}
    """
    path = Path(scaler_json_path)
    if not path.exists():
        raise FileNotFoundError(f"scaler.json not found at: {path}")
    return json.loads(path.read_text())  # type: ignore[return-value]


def normalize(ds: xr.Dataset, scaler: dict[str, dict[str, float]]) -> xr.Dataset:
    """Z-score normalise each variable in *ds* using training statistics.

    Parameters
    ----------
    ds:
        Input dataset.  Each variable name must appear in *scaler*.
    scaler:
        Output of ``load_scaler()``.

    Returns
    -------
    xr.Dataset
        Normalised dataset with the same variables and coordinates.

    Notes
    -----
    STUB: performs ``(x - mean) / std`` per variable.
    """
    normalized_vars: dict[str, xr.DataArray] = {}
    for var in ds.data_vars:
        if var not in scaler:
            raise KeyError(f"Variable '{var}' not found in scaler.json")
        mean = scaler[var]["mean"]
        std = scaler[var]["std"]
        normalized_vars[var] = (ds[var] - mean) / std
    return ds.assign(normalized_vars)


def compute_zscore(
    ds: xr.Dataset, scaler: dict[str, dict[str, float]]
) -> dict[str, np.ndarray]:
    """Compute absolute Z-scores for each variable against training statistics.

    Used by the quality gate to detect distribution-shifted inputs.

    Parameters
    ----------
    ds:
        Input dataset (un-normalised raw values).
    scaler:
        Output of ``load_scaler()``.

    Returns
    -------
    dict mapping variable name → float32 ndarray of |z| values, same shape as ds[var].
    """
    result: dict[str, np.ndarray] = {}
    for var in ds.data_vars:
        if var in scaler:
            mean = scaler[var]["mean"]
            std = scaler[var]["std"]
            z = np.abs((ds[var].values.astype("float64") - mean) / std)
            result[var] = z.astype("float32")
    return result
