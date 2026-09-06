"""
channels.py — Canonical input channel order for the OceanEmbed ensemble model.

The model's channels.json (in the model registry bundle) is the *authoritative*
source; this module reads that file and exposes it as a typed list so that both
the inference worker and the training pipeline use exactly the same ordering.

NEVER hardcode channel indices in training notebooks or inference scripts.
Always call ``load_channels(path_to_channels_json)`` and index by name.

Domain
------
North Indian Ocean: 5°N – 30°N, 45°E – 105°E at 0.25° resolution.
15 standard depth levels (to be defined in channels.json).

Channels (placeholder — replace with actual model input channels once
channels.json is packaged with the first model bundle):
    0: SST        — sea surface temperature (°C)
    1: SSS        — sea surface salinity (PSU)
    2: SLA        — sea level anomaly (m)
    3: U10        — 10-m zonal wind (m/s)
    4: V10        — 10-m meridional wind (m/s)
    ...
"""

from __future__ import annotations

import json
from pathlib import Path

# Domain constants — shared with fake_data.py and tests.
LAT_MIN: float = 5.0
LAT_MAX: float = 30.0
LON_MIN: float = 45.0
LON_MAX: float = 105.0
RESOLUTION: float = 0.25  # degrees

# Standard depth levels (metres) matching GLORYS target field.
STANDARD_DEPTHS: list[float] = [
    0.49, 1.54, 2.65, 3.82, 5.08, 6.44, 7.93, 9.57,
    11.41, 13.47, 15.81, 18.50, 21.60, 25.21, 29.44,
]


def load_channels(channels_json_path: str | Path) -> list[str]:
    """Load the canonical channel list from a model bundle's channels.json.

    Parameters
    ----------
    channels_json_path:
        Path to the ``channels.json`` file inside the model registry bundle.

    Returns
    -------
    list[str]
        Ordered list of channel names as they appear in the model's input tensor.

    Raises
    ------
    FileNotFoundError
        If ``channels_json_path`` does not exist.
    KeyError
        If the JSON file does not contain a ``"channels"`` key.
    """
    path = Path(channels_json_path)
    if not path.exists():
        raise FileNotFoundError(f"channels.json not found at: {path}")
    data = json.loads(path.read_text())
    return data["channels"]  # type: ignore[return-value]
