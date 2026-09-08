# OceanEmbed Backend — Task List

## Phase 0 — Repo Hygiene & Config Extension
- [x] Update `main.py` title/description/version to OceanEmbed
- [x] Add `OceanEmbedSettings` class to `settings.py`
- [x] Append OceanEmbed env vars block to `.env.example`
- [x] Create repo-root directories: `data/published/`, `model-registry/`, `core/`, `worker/`
- [x] Add `.gitkeep` files and update `.gitignore` for data dirs

## Phase 1 — Storage Layout + Zarr Resolver
- [x] Create `backend/src/infrastructure/zarr/__init__.py`
- [x] Create `backend/src/infrastructure/zarr/resolver.py` (ZarrStoreResolver)
- [x] Create `backend/src/infrastructure/zarr/fake_data.py` (two fake weeks: 2025-W01, 2025-W02)
- [x] Add `get_zarr_resolver` dependency to `backend/src/infrastructure/dependencies.py`
- [x] Add `xarray`, `zarr` to `backend/pyproject.toml` dependencies
- [x] Write `tests/unit/ocean/test_zarr_resolver.py`
  - [x] `test_resolves_latest_pointer`
  - [x] `test_picks_up_pointer_swap_without_restart`
  - [x] `test_caches_opened_store_per_week`
  - [x] `test_explicit_week_bypasses_symlink`

## Phase 2 — Postgres Schema Extension
- [x] Create `backend/src/modules/ocean/db/models.py` (ModelRun, ArgoProfile)
- [x] Create `backend/src/modules/ocean/db/init.sql` (PostGIS ext, spatial index)
- [x] Add `geoalchemy2` to `backend/pyproject.toml`
- [x] Create `backend/src/modules/ocean/services/postgis_queries.py`
- [ ] Generate Alembic migration `add_ocean_tables`
- [ ] Manually patch migration: add PostGIS extension + spatial index

## Phase 3 — OceanEmbed API Endpoints
- [x] Create `backend/src/modules/ocean/schemas/` (all Pydantic response models)
- [x] Create routers: `field.py` (binary + vectorized JSON), `profile.py`, `health.py`, `argo.py`
- [x] Register `ocean_router` in `backend/src/interfaces/api/v1/__init__.py`
- [x] Add CORS middleware for Vite dev server (localhost:5173)
- [ ] Create `saliency.py`, `sampling.py`, `benchmark.py` routes (future phase)
- [ ] Integration tests for all endpoints

## Phase 4 — core/ Package + Worker
- [x] Scaffold `core/pyproject.toml` (name=oceanembed-core)
- [x] Create `core/oceanembed_core/preprocessing/regrid.py` (stub)
- [x] Create `core/oceanembed_core/preprocessing/gapfill.py` (stub)
- [x] Create `core/oceanembed_core/preprocessing/normalize.py` (stub)
- [x] Create `core/oceanembed_core/preprocessing/channels.py` (reads channels.json)
- [x] Create `model-registry/oceanembed-v1.0.0/manifest.json` (placeholder)
- [ ] Create `worker/Dockerfile` (GPU-capable base, pip install -e ../core)
- [ ] Create `worker/quality_gate.py` (QualityGate: integrity + Z-score)
- [ ] Create `worker/run_weekly_inference.py` (full pipeline skeleton)

## Phase 5 — Tests, Docker, CI
- [x] Create `docker-compose.yml` at repo root (with :ro/:rw volume flags)
- [x] Create `frontend/Dockerfile` (multi-stage: Vite build → nginx)
- [ ] Extend `backend/tests/conftest.py` with OceanEmbed fixtures
- [ ] Write `tests/unit/ocean/test_quality_gate.py`
- [ ] Write `tests/integration/ocean/test_pointer_swap_integration.py`
- [ ] Create `backend/Dockerfile` (verify no torch)
- [ ] Create/update `.github/workflows/ci.yml`
- [ ] Verify `docker-compose up` starts clean on a second machine

## Phase 6 — Tooling & Operator CLI (Backlog)
*See [tooling_and_cli_adaptation_plan.md](tooling_and_cli_adaptation_plan.md) for full specification*
- [ ] Transform `cli/` from `bp` to `oe` (OceanEmbed Operator CLI)
  - [ ] Add `oe zarr seed` and `oe zarr swap-pointer` commands
  - [ ] Add `oe argo ingest` command for NetCDF profile import
- [ ] Adapt `.pre-commit-config.yaml` to enforce Ruff across backend/core and Prettier across frontend
- [ ] Adapt `.github/workflows/tests.yml` with PostGIS container service for automated CI

## Frontend Integration
- [x] Clone `Chatradhara007/inc` repo into `frontend/`
- [x] Remove `frontend/.git` (monorepo)
- [x] Create `frontend/src/api/liveOceanApi.ts` (real fetch-based client)
- [x] Create `frontend/src/api/index.ts` (mock/live toggle via VITE_USE_MOCK)
- [x] Update `frontend/vite.config.ts` (proxy /api → localhost:8000)
- [x] Update `frontend/src/App.tsx` (import from toggle instead of mock)
- [x] Create `frontend/.env` (VITE_USE_MOCK=true default)
- [x] Create `frontend/Dockerfile` (nginx with /api proxy)
- [x] Add `GET /v1/ocean/field_json` — vectorized, downsampled by stride=4
- [x] Add `GET /v1/ocean/argo_floats` — PostGIS distinct floats
- [x] Add `GET /v1/ocean/profile` — 15-depth + nearest ARGO
- [x] Add `GET /v1/ocean/health` — current live week status

## Phase 7 — Critical Fixes, Hardening & Multi-Model Scalability
*Detailed breakdown and tracking available in [task_list.md](file:///d:/Projects/oceanembed-sih/oceanembed/implementation_docs/task_list.md)*

### 1. Foundation: Variable Registry & Multi-Model Architecture
- [x] Create `backend/src/modules/ocean/constants.py` — canonical variable catalogue (`OCEAN_VARIABLES`), physical bounds, `STANDARD_DEPTHS`, and `ModelConfig` registry (`MODEL_REGISTRY`)
- [ ] Update `worker/quality_gate.py` to use dynamic bounds and variable lists from `constants.py`
- [ ] Update `backend/src/infrastructure/zarr/fake_data.py` to generate canonical variables and uncertainty companions
- [x] Update `backend/src/modules/ocean/routes/profile.py` to use standard depths and variables from registry
- [ ] Update `worker/run_weekly_inference.py` to read `ModelConfig` and write registered variables

### 2. Critical Bug Fixes & Route Reliability
- [x] Add error handling across routes (`field.py`, `profile.py`) for `KeyError`, `ValueError`, `RuntimeError`
- [x] Offload blocking Zarr array and disk I/O in route handlers to worker threads via `asyncio.to_thread()`
- [x] Graceful 404 response in `saliency.py` when saliency variable/mask is absent instead of 500 error
- [x] Mark `sampling.py` and `benchmark.py` draft/skeleton endpoints clearly in OpenAPI schema docs
- [ ] Fix Pydantic forward reference in `backend/src/modules/ocean/schemas/__init__.py` (`RunEntrySchema` before `WeeksResponseSchema`)
- [ ] Add `LIMIT` and pagination to `SELECT DISTINCT ON (platform_id)` query in `backend/src/modules/ocean/routes/argo.py`
- [ ] Add defensive `hasattr` state check in `get_zarr_resolver` in `backend/src/infrastructure/dependencies.py`

### 3. Inference Worker & Pipeline Hardening
- [ ] Create `worker/requirements.txt` with pinned dependencies for containerized execution
- [ ] Fix ISO calendar week boundary parsing (`%G-W%V-%u`) in `worker/run_weekly_inference.py`
- [ ] Clean up `worker/Dockerfile` (remove debug comments, fix permissions and entrypoint)
- [ ] Persist run audit trail and gate metrics to PostgreSQL `model_runs` table upon execution

### 4. Database & Migration Fixes
- [ ] Fix Alembic migration `down_revision`, add CHECK constraint on `gate_status`, align primary key names

### 5. Testing & CI Validation
- [ ] Rewrite `backend/tests/integration/ocean/test_endpoints.py` with schema validations and mock resolver
- [ ] Update `backend/tests/unit/ocean/test_quality_gate.py` with `OCEAN_VARIABLES` bounds

### 6. Scalability & Performance Hardening
- [ ] Add LRU cache eviction to `ZarrStoreResolver` to prevent unbounded memory growth
- [x] Optimize profile extraction in `profile.py` from sequential depth loop to single vectorized `.sel(lat, lon)` slice

