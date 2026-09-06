"""
ZarrStoreResolver — the single source of truth for which weekly dataset is live.

Design notes
------------
* Each weekly Zarr store lives in its own immutable directory:
      <root>/week=YYYY-Www/
  and contains only (lat, lon, depth) dimensions.  There is NO global 'week'
  coordinate inside the dataset — week is a *directory selector*, not an
  xarray coordinate.

* The inference worker atomically swaps the `<root>/latest` symlink once a
  week after a successful quality gate pass.  If the API resolved the symlink
  once at startup and cached the handle forever it would silently serve stale
  data after the swap.

* The fix: re-check the symlink target every ZARR_POINTER_RECHECK_SECONDS.
  Cache the opened xr.Dataset *keyed by the resolved absolute path*, so a
  path that hasn't changed doesn't re-open the store unnecessarily.

* Explicit week requests (e.g. GET /field?week=2025-W01) bypass the symlink
  entirely and open the named directory directly — no re-check required.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

# pyrefly: ignore [missing-import]
import xarray as xr

logger = logging.getLogger(__name__)


class ZarrStoreResolver:
    """Resolve and cache weekly Zarr stores.

    Parameters
    ----------
    root:
        Absolute path to the published Zarr root directory.  Must contain
        ``week=YYYY-Www/`` subdirectories and a ``latest`` symlink.
    recheck_seconds:
        How often to re-read the ``latest`` symlink when serving the current
        live week.  Explicit week requests always bypass this interval.

    Platform notes
    --------------
    Reading symlinks works on all platforms (Windows, Linux, macOS).
    *Writing* symlinks atomically (inference worker) requires POSIX — run
    the worker in WSL2 or a Linux Docker container on Windows hosts.
    The API process is read-only and works on any OS.
    """

    def __init__(self, root: str, recheck_seconds: int = 30) -> None:
        self._root = Path(root)
        self._recheck_seconds = recheck_seconds

        # Cache: absolute resolved path → opened xr.Dataset
        self._store_cache: dict[str, xr.Dataset] = {}

        # State for 'latest' symlink re-resolution
        self._latest_resolved: str | None = None
        self._last_check_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_store(self, week: str | None = None) -> xr.Dataset:
        """Return an opened xr.Dataset for the requested week.

        Parameters
        ----------
        week:
            Week label in ``YYYY-Www`` format, e.g. ``"2025-W01"``.
            When ``None`` the resolver opens whichever week ``latest``
            currently points to, re-checking the symlink periodically.

        Returns
        -------
        xr.Dataset
            Lazily-loaded Zarr dataset.  Dimensions: (lat, lon, depth).

        Raises
        ------
        FileNotFoundError
            If the requested week directory does not exist.
        RuntimeError
            If the ``latest`` symlink is missing or broken.
        """
        week_path = self._resolve_week_path(week)
        return self._open_store(week_path)

    def invalidate(self) -> None:
        """Drop all cached stores and force re-resolution on next call."""
        self._store_cache.clear()
        self._latest_resolved = None
        self._last_check_time = 0.0
        logger.info("ZarrStoreResolver: cache invalidated.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_week_path(self, week: str | None) -> Path:
        """Return the absolute path to the week directory.

        * ``week`` provided → ``<root>/week=<week>`` (no symlink involved).
        * ``week`` is None → re-resolve ``<root>/latest`` symlink if the
          TTL has expired; otherwise return the last known resolved path.
        """
        if week is not None:
            # Explicit week: direct path, no symlink involved.
            week_dir = self._root / f"week={week}"
            if not week_dir.exists():
                raise FileNotFoundError(
                    f"Week directory not found: {week_dir}"
                )
            return week_dir

        # Implicit latest: re-check symlink if TTL expired.
        now = time.monotonic()
        if self._should_recheck(now):
            resolved = self._read_latest_symlink()
            if resolved != self._latest_resolved:
                logger.info(
                    "ZarrStoreResolver: latest changed %s → %s",
                    self._latest_resolved,
                    resolved,
                )
            self._latest_resolved = resolved
            self._last_check_time = now

        if self._latest_resolved is None:
            raise RuntimeError(
                "ZarrStoreResolver: 'latest' symlink not yet resolved. "
                "Ensure the published Zarr root is mounted and the symlink exists."
            )

        return Path(self._latest_resolved)

    def _should_recheck(self, now: float) -> bool:
        """True if the recheck TTL has expired or we haven't checked yet."""
        return (now - self._last_check_time) >= self._recheck_seconds

    def _read_latest_symlink(self) -> str:
        """Read and validate the ``latest`` symlink, returning its absolute target.

        Uses ``os.path.realpath`` so the returned path is always absolute,
        regardless of whether the symlink target is relative or absolute.
        """
        latest_link = self._root / "latest"
        if not latest_link.exists():
            raise RuntimeError(
                f"ZarrStoreResolver: 'latest' symlink missing at {latest_link}. "
                "Run the inference worker to publish the first week."
            )
        resolved = os.path.realpath(str(latest_link))
        if not Path(resolved).exists():
            raise RuntimeError(
                f"ZarrStoreResolver: 'latest' symlink is broken → {resolved}"
            )
        return resolved

    def _open_store(self, week_path: Path) -> xr.Dataset:
        """Return a cached xr.Dataset for ``week_path``, opening it if needed."""
        key = str(week_path.resolve())
        if key not in self._store_cache:
            logger.info("ZarrStoreResolver: opening store at %s", key)
            self._store_cache[key] = xr.open_zarr(key)  # type: ignore[arg-type]
        return self._store_cache[key]
