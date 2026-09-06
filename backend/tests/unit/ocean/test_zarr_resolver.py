"""
Unit tests for ZarrStoreResolver.

These tests use a synthetic two-week Zarr layout created by fake_data.py
and do NOT require a live database or running FastAPI server.

The critical test is ``test_picks_up_pointer_swap_without_restart`` — this
is the exact test that would have caught the caching bug described in A.3
of the master plan.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
# pyrefly: ignore [missing-import]
import xarray as xr

# pyrefly: ignore [missing-import]
from src.infrastructure.zarr.fake_data import create_fake_published_layout, swap_latest
# pyrefly: ignore [missing-import]
from src.infrastructure.zarr.resolver import ZarrStoreResolver


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fake_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a fake two-week Zarr layout in a temp directory."""
    root = tmp_path_factory.mktemp("published")
    create_fake_published_layout(str(root), overwrite=True)
    return root


@pytest.fixture
def resolver(fake_root: Path) -> ZarrStoreResolver:
    """ZarrStoreResolver pointed at the fake layout; recheck TTL = 0 (always recheck)."""
    return ZarrStoreResolver(root=str(fake_root), recheck_seconds=0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestZarrStoreResolver:
    """Tests for the symlink resolution and per-week caching behaviour."""

    def test_resolves_latest_pointer(self, resolver: ZarrStoreResolver, fake_root: Path) -> None:
        """get_store(None) should open the dataset pointed to by 'latest'."""
        import asyncio
        ds = asyncio.get_event_loop().run_until_complete(resolver.get_store())
        assert isinstance(ds, xr.Dataset)
        # Default latest → week=2025-W01
        assert ds.attrs.get("week_label") == "2025-W01"

    def test_explicit_week_bypasses_symlink(self, resolver: ZarrStoreResolver, fake_root: Path) -> None:
        """get_store(week='2025-W02') opens W02 regardless of where 'latest' points."""
        import asyncio
        ds = asyncio.get_event_loop().run_until_complete(resolver.get_store(week="2025-W02"))
        assert ds.attrs.get("week_label") == "2025-W02"

    def test_caches_opened_store_per_week(self, resolver: ZarrStoreResolver, fake_root: Path) -> None:
        """Calling get_store twice for the same week returns the identical object."""
        import asyncio

        async def _run() -> tuple[xr.Dataset, xr.Dataset]:
            a = await resolver.get_store(week="2025-W01")
            b = await resolver.get_store(week="2025-W01")
            return a, b

        a, b = asyncio.get_event_loop().run_until_complete(_run())
        assert a is b, "Expected the same cached Dataset object on the second call"

    def test_picks_up_pointer_swap_without_restart(
        self, resolver: ZarrStoreResolver, fake_root: Path
    ) -> None:
        """
        THE CRITICAL TEST — validates the fix for master plan bug A.3.

        After the 'latest' symlink is swapped to week=2025-W02, the resolver
        must return the new dataset WITHOUT the process being restarted.

        A resolver that cached the opened store at process start and never
        re-checked the symlink would fail this test by returning W01 data.
        """
        import asyncio

        async def _get_latest() -> xr.Dataset:
            return await resolver.get_store()

        # Confirm we start on W01.
        ds_before = asyncio.get_event_loop().run_until_complete(_get_latest())
        assert ds_before.attrs.get("week_label") == "2025-W01"

        # Atomically swap the symlink to W02 (simulates a successful weekly publish).
        swap_latest(str(fake_root), "2025-W02")

        # The resolver TTL is 0, so the next call re-checks the symlink.
        # It must now return W02 data — no process restart.
        ds_after = asyncio.get_event_loop().run_until_complete(_get_latest())
        assert ds_after.attrs.get("week_label") == "2025-W02", (
            "Resolver returned stale W01 data after the symlink was swapped to W02. "
            "The resolver must re-check the symlink on each request (within TTL)."
        )

    def test_missing_week_raises_file_not_found(self, resolver: ZarrStoreResolver) -> None:
        """Requesting a non-existent explicit week should raise FileNotFoundError."""
        import asyncio
        with pytest.raises(FileNotFoundError, match="week=9999-W99"):
            asyncio.get_event_loop().run_until_complete(resolver.get_store(week="9999-W99"))

    def test_missing_latest_symlink_raises_runtime_error(self, tmp_path: Path) -> None:
        """A resolver whose root has no 'latest' symlink should raise RuntimeError."""
        import asyncio
        root = tmp_path / "empty_published"
        root.mkdir()
        r = ZarrStoreResolver(root=str(root), recheck_seconds=0)
        with pytest.raises(RuntimeError, match="latest.*symlink missing"):
            asyncio.get_event_loop().run_until_complete(r.get_store())
