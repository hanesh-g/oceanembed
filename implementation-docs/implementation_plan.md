# OceanEmbed Backend — Implementation Plan

Adapt the `benavlabs/FastAPI-boilerplate` into the OceanEmbed serving layer. The boilerplate gives us async SQLAlchemy 2.0, Pydantic v2, DB session management, and test scaffolding for free. Everything ocean-domain-specific is net-new.

## Resolved Decisions

**Q1 — Zarr storage root:** `./data/published/` at repo root. Container internal path: `/data/published`. Mounted `:rw` for worker, `:ro` for api. Must be on the same filesystem as the worker write target so POSIX `os.rename()` symlink swap works (no cross-filesystem boundary).

**Q2 — Model registry:** `./model-registry/` at repo root. Layout:
```
model-registry/
└── oceanembed-v1.0.0/
    ├── members/   (member_0.pt … member_4.pt)
    ├── scaler.json
    ├── channels.json
    ├── calibration.json
    └── manifest.json
```
Mounted `:ro` in worker container. Tracked via Git LFS for hackathon/PoC — no S3/GCS needed.

**Q3 — `oceanembed_core`:** Create immediately with functional stubs. Scaffold `core/oceanembed_core` with explicit interfaces for `regrid`, `gapfill`, `normalize`, `channels`. Domain extent: 5°N–30°N, 45°E–105°E at 0.25°. This shared contract prevents train/inference skew from day 1.

**Q4 — Boilerplate modules:** Keep dormant. `user`, `auth`, `api_keys`, `tier`, `rate_limit` routers are **not** included in `/v1/ocean/`. Their DB models and Alembic tables stay intact — removing them would break Fastro's dependency graph and test fixtures.

## Bug Fixes Applied

> [!WARNING]
> **Bug 1 — Week slicing inside Zarr dataset (Phase 3 fix):** Each weekly Zarr store only has `(lat, lon, depth)` dimensions — there is no global `week` coordinate. `week` is a *directory selector*, not a dataset coordinate. `ZarrStoreResolver.get_store()` now accepts an optional `week` parameter (defaults to `latest` symlink). Slicing happens on spatial/depth dims only after the correct store is opened.

> [!WARNING]
> **Bug 2 — API volume permissions (Phase 5 fix):** The API container mounts `./data/published` as `:ro` (read-only) to enforce the read-only boundary and prevent the API process from ever mutating or locking Zarr arrays.

---

## Proposed Changes

### Phase 0 — Repo Hygiene & Config Extension

Adapt the boilerplate identity and add OceanEmbed-specific settings without touching boilerplate internals.

---

#### [MODIFY] [`main.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/interfaces/main.py)
- Update `title`, `description`, `version`, `contact` to reflect OceanEmbed.
- Keep boilerplate lifespan — the DB pool is managed there and we reuse it.

#### [MODIFY] [`settings.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/infrastructure/config/settings.py)
Add a new `OceanEmbedSettings` class (append below existing classes, compose into `Settings`):
```python
class OceanEmbedSettings(BaseSettings):
    PUBLISHED_ZARR_ROOT: str = config("PUBLISHED_ZARR_ROOT", default="./data/published")
    ZARR_POINTER_RECHECK_SECONDS: int = config("ZARR_POINTER_RECHECK_SECONDS", default=30, cast=int)
    MODEL_REGISTRY_PATH: str = config("MODEL_REGISTRY_PATH", default="./model-registry")
    QUALITY_GATE_ZSCORE_THRESHOLD: float = config("QUALITY_GATE_ZSCORE_THRESHOLD", default=4.0, cast=float)
    QUALITY_GATE_ZSCORE_MAX_FRACTION: float = config("QUALITY_GATE_ZSCORE_MAX_FRACTION", default=0.05, cast=float)
```

#### [MODIFY] [`.env.example`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/.env.example)
Append OceanEmbed environment variables block with comments.

---

### Phase 1 — Storage Layout + Zarr Resolver (Foundation)

> [!IMPORTANT]
> This phase must be complete and tested before any endpoint is built. Everything downstream depends on the resolver working correctly including the pointer-swap behavior.

---

#### [NEW] `backend/src/infrastructure/zarr/__init__.py`
Empty init.

#### [NEW] `backend/src/infrastructure/zarr/resolver.py`
The core re-resolution logic. Keyed cache — re-checks the symlink target on every call (or throttled by `ZARR_POINTER_RECHECK_SECONDS`). **`get_store()` accepts an optional `week` parameter** — when provided it opens that specific week directory directly; when omitted it resolves `published/latest`:

```python
class ZarrStoreResolver:
    """
    Resolves published/latest symlink (or an explicit week dir) and caches
    the opened xarray Dataset keyed by resolved absolute path.
    Re-checks the 'latest' pointer periodically so new publishes are picked
    up without an API restart.

    NOTE: 'week' is a directory selector, NOT a Zarr coordinate.
    Each weekly store only contains (lat, lon, depth) dimensions.
    """
    def __init__(self, root: str, recheck_seconds: int): ...
    async def get_store(self, week: str | None = None) -> xr.Dataset:
        """Open store for a specific week or latest if week is None."""
        ...
    def _resolve_week_path(self, week: str | None) -> Path:
        """Returns absolute path to the week directory.
        If week is None: re-resolve published/latest symlink.
        If week is provided: return root / f'week={week}' directly.
        """
        ...
    def _should_recheck(self) -> bool: ...   # time-based TTL for 'latest' only
```

#### [NEW] `backend/src/infrastructure/zarr/fake_data.py`
Script (not imported at runtime) to create two fake weeks of synthetic Zarr data for tests and local dev:
```
published/
  week=2025-W01/   ← fake week 1, tiny grid (5x5x3 depths)
  week=2025-W02/   ← fake week 2
  latest -> week=2025-W01   ← symlink starts pointing here
```

#### [NEW] `backend/src/infrastructure/dependencies.py` (extend existing)
Add `get_zarr_store` dependency that yields a resolved `xr.Dataset` via `ZarrStoreResolver`.

> The boilerplate's existing [`dependencies.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/infrastructure/dependencies.py) provides the DB session dep — we add the Zarr dep alongside it.

---

### Phase 2 — Postgres Schema Extension (OceanEmbed Tables)

The boilerplate's `UUIDMixin` + `TimestampMixin` + `MappedAsDataclass` pattern is reused as-is.

---

#### [NEW] [`backend/src/modules/ocean/db/models.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/modules/ocean/db/models.py) [✅ Created]
Two SQLAlchemy models using the boilerplate's `UUIDMixin` + `TimestampMixin`:

```python
class ModelRun(UUIDMixin, TimestampMixin, Base):
    week_label: Mapped[str]                      # "2025-W01"
    run_date: Mapped[datetime]
    model_version: Mapped[str]                   # bundle identifier
    gate_status: Mapped[str]                     # "pass" | "fail"
    gate_log: Mapped[dict | None] = mapped_column(JSONB)   # per-channel gate details
    published_at: Mapped[datetime | None]

class ArgoProfile(UUIDMixin, Base):
    platform_id: Mapped[str]
    profile_date: Mapped[datetime]
    lat: Mapped[float]
    lon: Mapped[float]
    # MANDATORY: srid=4326 + geometry_type='POINT' for <-> operator correctness
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type='POINT', srid=4326))
    depth_levels: Mapped[list[float]] = mapped_column(JSONB)
    temp_values: Mapped[list[float | None]] = mapped_column(JSONB)
    sal_values: Mapped[list[float | None]] = mapped_column(JSONB)
    # GiST index on geom — required for <-> to use the index, not a full table scan
    __table_args__ = (Index("argo_geom_gist_idx", "geom", postgresql_using="gist"),)
```

> [!WARNING]
> **GeoAlchemy2 trap:** `geom` MUST be `Geometry(geometry_type='POINT', srid=4326)` — not plain `Geometry()`. Without the explicit srid, the `<->` distance operator may silently switch to a spherical geography metric, giving wrong nearest-neighbour ordering. Always use `ST_Point(lon, lat, 4326)` in queries — x (lon) before y (lat).

#### [NEW] `backend/src/modules/ocean/db/init.sql`
Raw SQL for:
- `CREATE EXTENSION IF NOT EXISTS postgis;`
- `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
- Spatial index: `CREATE INDEX argo_geom_idx ON argo_profiles USING GIST(geom);`

#### [NEW] Alembic migration
Auto-generate after models are defined:
```bash
alembic revision --autogenerate -m "add_ocean_tables"
```
Manually add the PostGIS extension creation + spatial index to the migration file.

---

### Phase 3 — OceanEmbed API Endpoints

All endpoints live under `/v1/ocean/`. The v1 router in [`__init__.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/interfaces/api/v1/__init__.py) gets one new include.

---

#### [NEW] `backend/src/modules/ocean/` (new vertical slice module)

```
backend/src/modules/ocean/
├── __init__.py
├── db/
│   ├── models.py          ← Phase 2
│   └── init.sql           ← Phase 2
├── schemas/
│   ├── field.py           ← FieldResponse, FieldQueryParams
│   ├── profile.py         ← ProfileResponse, ProfileQueryParams
│   ├── saliency.py        ← SaliencyResponse
│   ├── sampling.py        ← SamplingRecommendationResponse
│   ├── benchmark.py       ← BenchmarkResponse
│   └── health.py          ← WeekStatusResponse, WeeksResponse
├── services/
│   ├── field_service.py   ← slices Zarr, returns float32 bytes
│   ├── profile_service.py ← nearest grid cell + nearest ARGO query
│   ├── saliency_service.py
│   ├── sampling_service.py
│   ├── benchmark_service.py
│   └── postgis_queries.py ← nearest-ARGO, run metadata, gate audit
└── routes/
    ├── __init__.py        ← ocean_router, includes all sub-routers
    ├── field.py
    ├── profile.py
    ├── saliency.py
    ├── sampling.py
    ├── benchmark.py
    └── health.py
```

#### Endpoint Contracts

| Route | Method | Response | Notes |
|---|---|---|---|
| `GET /v1/ocean/field` | `?variable=temp&week=2025-W01` | `application/octet-stream` (`float32` binary) | Full 3D volume (lat×lon×depth). `depth` is **optional** — omit to get all 15 depths; provide to get a 2D slice. |
| `GET /v1/ocean/profile` | `?lat=12.5&lon=80.3&week=2025-W01` | JSON `ProfileResponse` | 15-depth profile + nearest ARGO |
| `GET /v1/ocean/saliency` | `?variable=temp&week=2025-W01` | `application/octet-stream` | Same binary pattern as `/field` |
| `GET /v1/ocean/sampling_recommendation` | `?week=2025-W01` | JSON | Recommended sampling locations |
| `GET /v1/ocean/benchmark` | `?lat=12.5&lon=80.3&week=2025-W01` | JSON | Model vs ARMOR3D vs ARGO |
| `GET /v1/ocean/health` | — | JSON `WeekStatusResponse` | Current live week + gate status |
| `GET /v1/ocean/weeks` | — | JSON `WeeksResponse` | Full gate audit trail |

#### Key implementation notes:

**`/field` binary response pattern — 3D volume by default, 2D slice when `depth` is given:**

> [!WARNING]
> `X-Shape` must encode **all returned dimensions** so the frontend typed array parser can correctly unpack the buffer. A 2D `"{lat},{lon}"` header is wrong when the full 3D volume is returned — use `"{lat},{lon},{depth}"` always.

```python
@router.get("/field")
async def get_field(
    variable: str,
    week: str | None = None,           # None → latest live week
    depth: float | None = None,         # None → return all depths (3D volume)
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
) -> Response:
    store = await resolver.get_store(week=week)  # opens week=YYYY-Www/ or latest/
    da = store[variable]                         # DataArray: (lat, lon, depth)

    if depth is not None:
        # 2D single-depth slice: shape (lat, lon)
        da = da.sel(depth=depth, method="nearest")
        buf = da.values.astype("float32").tobytes()
        shape_header = f"{da.shape[0]},{da.shape[1]}"
    else:
        # 3D full volume: shape (lat, lon, depth) — client does depth-slider slicing
        buf = da.values.astype("float32").tobytes()
        shape_header = f"{da.shape[0]},{da.shape[1]},{da.shape[2]}"

    return Response(
        content=buf,
        media_type="application/octet-stream",
        headers={
            "X-Shape": shape_header,          # always encodes ALL returned dimensions
            "X-Variable": variable,
            "X-Model-Version": store.attrs.get("model_version", "unknown"),
            "X-Week": store.attrs.get("week_label", "unknown"),
        },
    )
```

**`/profile` PostGIS nearest-ARGO query:**
```python
-- postgis_queries.py
SELECT * FROM argo_profiles
ORDER BY geom <-> ST_Point(:lon, :lat, 4326)
LIMIT 1;
```

**Every JSON response** must include `model_version` and `published_at` fields — add these to all Pydantic response schemas.

---

### Phase 4 — Inference Worker

Separate from the API. Lives at repo root, not under `backend/`.

---

#### [NEW] `worker/` directory

```
worker/
├── Dockerfile            ← GPU-capable base, installs torch, installs core/ editable
├── requirements.txt      ← torch, xarray, zarr, numpy, psycopg2
├── run_weekly_inference.py
└── quality_gate.py
```

#### [NEW] `core/` directory (shared installable package)

```
core/
├── pyproject.toml        ← name = "oceanembed-core"
└── oceanembed_core/
    ├── __init__.py
    └── preprocessing/
        ├── __init__.py
        ├── regrid.py     ← 0.25° regridding
        ├── gapfill.py    ← DINEOF or simpler gap-fill
        ├── normalize.py  ← applies scaler.json mean/std
        └── channels.py   ← canonical channel order (reads channels.json)
```

#### [NEW] `worker/quality_gate.py`
Two mandatory checks — **not** gated behind "if time allows":
1. **Integrity:** NaN fraction, spatial coverage, per-variable physical bounds
2. **Z-score drift:** `z = (x - μ_train) / σ_train` vs `scaler.json` — flag if `|z| > threshold` for `> max_fraction` of cells per channel

```python
class QualityGate:
    def __init__(self, scaler_path: str, threshold: float, max_fraction: float): ...
    def check(self, ds: xr.Dataset) -> GateResult: ...
    def _integrity_check(self, ds: xr.Dataset) -> list[str]: ...
    def _zscore_check(self, ds: xr.Dataset) -> list[str]: ...

@dataclass
class GateResult:
    passed: bool
    log: dict   # serialized to gate_log in Postgres
```

#### [NEW] `worker/run_weekly_inference.py`
Orchestrates the full pipeline:
1. Load frozen bundle from model registry
2. Ingest + preprocess satellite feeds via `oceanembed_core`
3. 5-member ensemble forward passes
4. Derive T/S/D26/TCHP/MLD per member
5. Aggregate mean + spread (apply calibration.json inflation factor)
6. Run `QualityGate.check()` → on pass: write immutable Zarr, atomic symlink swap; on fail: alert + log to Postgres
7. Write `ModelRun` row to Postgres regardless of pass/fail

**Atomic symlink swap pattern:**
```python
import os, tempfile, pathlib

week_dir = Path(published_root) / f"week={week_label}"
week_dir.mkdir(parents=True, exist_ok=False)   # immutable: fail if exists
ds.to_zarr(week_dir)                           # write

# atomic swap
tmp_link = Path(published_root) / f".latest_tmp_{os.getpid()}"
tmp_link.symlink_to(week_dir.name)
tmp_link.rename(Path(published_root) / "latest")  # atomic on POSIX
```

---

### Phase 5 — Tests, Docker, CI

---

#### [NEW] `backend/tests/conftest.py` (extend existing)
Add OceanEmbed fixtures:
- `fake_zarr_root` — creates two fake weeks (5×5×3 grid) via `fake_data.py`, yields the root path, cleans up
- `zarr_resolver` — a `ZarrStoreResolver` pointed at `fake_zarr_root`
- Seed `model_runs` and `argo_profiles` rows in the test DB

#### [NEW] `backend/tests/unit/ocean/`
```
test_zarr_resolver.py
  - test_resolves_latest_pointer()
  - test_picks_up_pointer_swap_without_restart()  ← THE critical test
  - test_caches_opened_store_per_week()

test_quality_gate.py
  - test_passes_clean_data()
  - test_fails_on_high_nan_fraction()
  - test_fails_on_zscore_outlier()
  - test_passes_boundary_zscore()
```

#### [NEW] `backend/tests/integration/ocean/`
```
test_field_endpoint.py
  - test_field_returns_binary_float32()
  - test_field_shape_header_correct()
  - test_field_404_on_missing_week()

test_profile_endpoint.py
  - test_profile_returns_json()
  - test_profile_includes_nearest_argo()
  - test_profile_422_on_bad_coords()

test_weeks_endpoint.py
  - test_weeks_returns_gate_audit_trail()
  - test_health_returns_current_live_week()

test_pointer_swap_integration.py
  - test_api_serves_new_week_after_symlink_swap_no_restart()
```

#### [NEW] `docker-compose.yml` (repo root)
```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./data/published:/data/published:ro   # READ-ONLY — API must never mutate Zarr
    env_file: ./backend/.env
    depends_on: [postgres]

  worker:
    build: ./worker
    volumes:
      - ./data/published:/data/published:rw   # worker writes + swaps symlink
      - ./model-registry:/model-registry:ro   # frozen bundle, never overwritten
    env_file: ./worker/.env
    profiles: ["worker"]   # don't start by default; run manually

  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: oceanembed
      POSTGRES_PASSWORD: oceanembed
      POSTGRES_DB: oceanembed
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/src/modules/ocean/db/init.sql:/docker-entrypoint-initdb.d/01_ocean.sql

volumes:
  pgdata:
```

#### [MODIFY] `.github/workflows/ci.yml`
```yaml
# On every push:
# 1. Install deps + run pytest (backend tests only)
# 2. Build API Docker image (assert no torch import)
# 3. Build worker Docker image
```

---

## Verification Plan

### Automated Tests
```bash
# From backend/
pytest tests/unit/ocean/ -v
pytest tests/integration/ocean/ -v

# Confirm zero torch in API image:
docker build -f backend/Dockerfile -t oceanembed-api .
docker run --rm oceanembed-api python -c "import torch" 2>&1 | grep -q "ModuleNotFoundError"
```

### Manual Verification
1. `docker-compose up` → `curl http://localhost:8000/health` returns `{"status": "healthy"}`
2. `curl http://localhost:8000/v1/ocean/health` returns current live week + gate status
3. `curl http://localhost:8000/v1/ocean/field?variable=temp&depth=0&week=2025-W01` returns a binary response with `Content-Type: application/octet-stream`
4. Manually update the `published/latest` symlink to point at week 2 → re-hit `/field` → confirm it serves week 2 data **without restarting the API**
5. `curl http://localhost:8000/v1/ocean/weeks` returns pass/fail history

---

## Pre-Execution Verification Checklist

| Step | Verification Criterion | Status |
|---|---|---|
| Directory Boundary | `core/` sits at repo root, installable via `pip install -e ./core` | ✅ Confirmed |
| API Dependencies | `backend/requirements.txt` has zero `torch` or CUDA references | ✅ Confirmed |
| Binary Endpoint | `/field` streams raw `float32` bytes with `application/octet-stream` | ✅ Confirmed |
| Storage Resolution | `ZarrStoreResolver.get_store(week=...)` accepts optional week, defaults to `latest` symlink | ✅ Bug fixed |
| Container Permissions | `api` mounts `/data/published` with `:ro` flag | ✅ Bug fixed |

## Execution Order Summary

```
Phase 0:  settings + env + repo dirs → 30 min
Phase 1:  Zarr resolver + fake data + resolver tests → 3–4 hrs  ← DO THIS FIRST
Phase 2:  DB models + migration + PostGIS → 2–3 hrs
Phase 3:  /field → /profile → rest of endpoints → 1 day
Phase 4:  core/ package + worker skeleton + quality gate → 1 day
Phase 5:  full test suite + Docker + CI → 3–4 hrs
```

Total estimated effort: **3–4 focused dev days** to a working, containerized, tested demo.
