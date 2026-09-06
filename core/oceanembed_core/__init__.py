"""
oceanembed_core — shared preprocessing package.

Both the offline training pipeline and the inference worker import from here.
This package is the single source of truth for:
  - the canonical channel order (channels.json)
  - regridding logic (0.25° target grid)
  - gap-filling strategy
  - input normalisation (scaler.json)

Install with:
    pip install -e ./core          # from repo root
    pip install -e ../core         # from worker/ or backend/

Never copy these files into a training notebook or a separate repo.
One implementation, installed everywhere.
"""

from .preprocessing import channels, gapfill, normalize, regrid

__all__ = ["channels", "gapfill", "normalize", "regrid"]
