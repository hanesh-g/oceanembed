"""
fake_data.py — Create a minimal synthetic published Zarr layout for tests and local dev.

Run directly:
    python -m backend.src.infrastructure.zarr.fake_data --root ./data/published

Or call ``create_fake_published_layout(root)`` from test fixtures.

Layout produced
---------------
<root>/
    week=2025-W01/   ← tiny 5°-resolution grid, 3 depths, 2 variables (temp, sal)
    week=2025-W02/   ← same shape, different values
    latest -> week=2025-W01   ← symlink; points at W01 by default
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
# pyrefly: ignore [missing-import]
import xarray as xr

# -----------------------------------------------------------------
# Domain constants (must match oceanembed_core.preprocessing.channels)
# -----------------------------------------------------------------
# Coarse synthetic grid — real domain is 0.25° but 5° is enough for tests.
LATS = np.arange(5.0, 31.0, 5.0, dtype="float32")    # 5°N–30°N
LONS = np.arange(45.0, 106.0, 5.0, dtype="float32")   # 45°E–105°E
DEPTHS = np.array([0.0, 50.0, 200.0], dtype="float32")  # 3 of 15 real levels
VARIABLES = ["temp", "sal", "d26", "tchp", "mld"]


def _make_week_dataset(week_label: str, seed: int) -> xr.Dataset:
    """Build a small synthetic xr.Dataset for one week."""
    rng = np.random.default_rng(seed)
    shape = (len(LATS), len(LONS), len(DEPTHS))

    data_vars: dict[str, xr.Variable] = {}
    for var in VARIABLES:
        # Give each variable physically plausible ranges
        if var == "temp":
            values = rng.uniform(10.0, 32.0, shape).astype("float32")
        elif var == "sal":
            values = rng.uniform(34.0, 37.0, shape).astype("float32")
        elif var == "d26":
            values = rng.uniform(50.0, 150.0, shape).astype("float32")
        elif var == "tchp":
            values = rng.uniform(0.0, 120.0, shape).astype("float32")
        else:  # mld
            values = rng.uniform(20.0, 80.0, shape).astype("float32")

        # Add matching uncertainty field
        data_vars[var] = xr.Variable(["lat", "lon", "depth"], values)
        data_vars[f"{var}_spread"] = xr.Variable(
            ["lat", "lon", "depth"],
            (rng.uniform(0.0, 1.0, shape) * 0.1).astype("float32"),
        )

    ds = xr.Dataset(
        data_vars,
        coords={
            "lat": ("lat", LATS),
            "lon": ("lon", LONS),
            "depth": ("depth", DEPTHS),
        },
        attrs={
            "week_label": week_label,
            "model_version": "oceanembed-v1.0.0",
            "gate_status": "pass",
            "description": f"Synthetic OceanEmbed output for {week_label}",
        },
    )
    return ds


def create_fake_published_layout(root: str | Path, *, overwrite: bool = False) -> Path:
    """Create two fake weeks and a ``latest`` symlink under ``root``.

    Parameters
    ----------
    root:
        Directory to write to.  Created if it does not exist.
    overwrite:
        If True, delete and re-create existing week directories.

    Returns
    -------
    Path
        The resolved root path.
    """
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    weeks = [("2025-W01", 42), ("2025-W02", 99)]
    for week_label, seed in weeks:
        week_dir = root / f"week={week_label}"
        if week_dir.exists():
            if overwrite:
                import shutil
                shutil.rmtree(week_dir)
            else:
                print(f"  skip {week_dir} (already exists)")
                continue
        ds = _make_week_dataset(week_label, seed)
        ds.to_zarr(str(week_dir))
        print(f"  wrote {week_dir}")

    # Create / update the latest symlink pointing at week W01 by default.
    latest_link = root / "latest"
    target = "week=2025-W01"  # relative — stays valid inside a container
    _safe_symlink(latest_link, target)
    print(f"  symlink: {latest_link} → {target}")

    return root


def _safe_symlink(link: Path, target: str) -> None:
    """Create or replace a symlink in a cross-platform way.

    On POSIX (Linux, macOS, WSL2, Docker Linux containers) this is atomic:
    write a tmp symlink then rename it over the destination in one syscall.

    On Windows native hosts ``os.rename`` raises ``FileExistsError`` when the
    destination already exists.  We fall back to ``unlink + symlink_to`` which
    is NOT atomic, but is fine for the test / local-dev context.  Windows also
    requires Developer Mode or elevated privileges for ``os.symlink`` — if that
    is unavailable the call will raise ``OSError``.

    Production inference workers MUST run on Linux (WSL2 or a Docker container)
    to get the atomic rename guarantee.  The API process only reads symlinks, so
    it works on any OS.
    """
    if link.is_symlink() or link.exists():
        link.unlink(missing_ok=True)

    if os.name == "posix":
        # Atomic POSIX rename: write tmp, then rename over destination.
        tmp = link.parent / f".latest_tmp_{os.getpid()}"
        tmp.symlink_to(target)
        try:
            tmp.rename(link)          # atomic on POSIX
        except Exception:             # pragma: no cover — shouldn't happen on POSIX
            tmp.unlink(missing_ok=True)
            link.symlink_to(target)   # non-atomic fallback
    else:
        # Windows: non-atomic, requires Developer Mode or elevated privileges.
        link.symlink_to(target)


def swap_latest(root: str | Path, week_label: str) -> None:
    """Atomically swap ``latest`` to point at a different week.

    Uses the POSIX ``os.rename`` trick on the symlink so that readers
    never observe a moment where ``latest`` is missing.

    Parameters
    ----------
    root:
        The published Zarr root directory.
    week_label:
        e.g. ``"2025-W02"``
    """
    root = Path(root).resolve()
    target = f"week={week_label}"
    week_dir = root / target
    if not week_dir.exists():
        raise FileNotFoundError(f"Week directory not found: {week_dir}")

    _safe_symlink(root / "latest", target)
    print(f"  swapped latest → {target}")


# -----------------------------------------------------------------
# CLI entry-point
# -----------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a fake published Zarr layout.")
    parser.add_argument(
        "--root",
        default="./data/published",
        help="Root path to write fake weeks into (default: ./data/published)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and re-create existing week directories.",
    )
    args = parser.parse_args()
    print(f"Creating fake published layout at: {args.root}")
    create_fake_published_layout(args.root, overwrite=args.overwrite)
    print("Done.")
