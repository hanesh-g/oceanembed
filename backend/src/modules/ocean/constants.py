"""
Canonical variable registry and model configuration for OceanEmbed.

This module is the **single source of truth** for variable names, physical
bounds, standard depth levels, and model metadata across the entire stack
(API routes, quality gate, inference worker, fake data generator, tests).

Design for Scale
----------------
When integrating multiple models (e.g., 5 different ensemble members or
different forecast products), each model registers its own variable set
and physical bounds here.  The quality gate, API routes, and worker all
reference this registry rather than hardcoding variable names.

Adding a new model
~~~~~~~~~~~~~~~~~~
1. Create a new ``ModelConfig`` entry in ``MODEL_REGISTRY``.
2. Ensure the inference worker writes Zarr stores with matching variable names.
3. The quality gate will automatically validate against the new model's bounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Standard depth levels (metres) — shared by API, fake data, and frontend
# ---------------------------------------------------------------------------
STANDARD_DEPTHS: list[float] = [
    0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000,
]


# ---------------------------------------------------------------------------
# Variable Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OceanVariable:
    """Describes a single oceanographic variable.

    Attributes
    ----------
    name:
        Internal/canonical name used in Zarr stores and API endpoints.
    display_name:
        Human-readable label for frontend rendering.
    unit:
        Physical unit string.
    bounds:
        (min, max) physical bounds for quality gate integrity checks.
    has_spread:
        Whether the inference worker produces a ``{name}_spread`` uncertainty
        companion variable.
    has_saliency:
        Whether the inference worker produces a ``saliency_{name}`` map.
    """
    name: str
    display_name: str
    unit: str
    bounds: tuple[float, float]
    has_spread: bool = True
    has_saliency: bool = False


# Canonical variable catalogue — used everywhere.
# Names match what the inference worker and Zarr stores actually produce.
OCEAN_VARIABLES: dict[str, OceanVariable] = {
    v.name: v for v in [
        OceanVariable("temp",  "Temperature",        "°C",  (-2.0, 36.0)),
        OceanVariable("sal",   "Salinity",           "PSU", (10.0, 42.0)),
        OceanVariable("d26",   "Depth of 26°C Iso.", "m",   (0.0, 300.0)),
        OceanVariable("tchp",  "Tropical Cyclone HP", "kJ/cm²", (0.0, 200.0)),
        OceanVariable("mld",   "Mixed Layer Depth",  "m",   (0.0, 500.0)),
    ]
}

# Quick lookup: set of all valid variable names (for input validation).
VALID_VARIABLE_NAMES: frozenset[str] = frozenset(OCEAN_VARIABLES.keys())

# Variables that have spread (uncertainty) companions.
SPREAD_VARIABLES: frozenset[str] = frozenset(
    v.name for v in OCEAN_VARIABLES.values() if v.has_spread
)


# ---------------------------------------------------------------------------
# Model Configuration (multi-model scaling)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a single model version in the registry.

    When scaling to 5+ models, each gets its own entry here.
    The worker reads this config to know which variables to produce,
    the quality gate reads it to know what bounds to enforce, and
    the API can serve data from any registered model.
    """
    model_id: str                          # e.g. "oceanembed-v1.0.0"
    variables: list[str]                   # subset of OCEAN_VARIABLES keys
    ensemble_members: int = 5
    resolution_deg: float = 0.25
    depth_levels: list[float] = field(default_factory=lambda: STANDARD_DEPTHS.copy())

    # Quality gate thresholds — can be overridden per model
    nan_threshold: float = 0.05            # max NaN fraction
    zscore_threshold: float = 4.0          # outlier Z-score cutoff
    zscore_max_fraction: float = 0.01      # max fraction of outlier cells


# Registry of all known model versions.
# The inference worker selects which model to run; the API can serve any.
MODEL_REGISTRY: dict[str, ModelConfig] = {
    "oceanembed-v1.0.0": ModelConfig(
        model_id="oceanembed-v1.0.0",
        variables=["temp", "sal", "d26", "tchp", "mld"],
    ),
    # Example: future model with additional variables
    # "oceanembed-v2.0.0": ModelConfig(
    #     model_id="oceanembed-v2.0.0",
    #     variables=["temp", "sal", "d26", "tchp", "mld", "ssh", "u", "v"],
    #     ensemble_members=10,
    #     resolution_deg=0.1,
    # ),
}

DEFAULT_MODEL_VERSION = "oceanembed-v1.0.0"


def get_model_config(model_version: str | None = None) -> ModelConfig:
    """Return the ModelConfig for a given version, or the default."""
    version = model_version or DEFAULT_MODEL_VERSION
    if version not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model version '{version}'. "
            f"Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[version]


def get_physical_bounds() -> dict[str, tuple[float, float]]:
    """Return {variable_name: (min, max)} for all registered variables."""
    return {v.name: v.bounds for v in OCEAN_VARIABLES.values()}
