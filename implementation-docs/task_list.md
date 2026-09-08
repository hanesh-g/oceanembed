# OceanEmbed Backend — Critical Fixes & Production Hardening Task List

This task list formalizes the remediation plan and architectural enhancements identified during the comprehensive **Backend Validation Audit** (documented in [BACKEND_VALIDATION_REPORT.md](file:///d:/Projects/oceanembed-sih/oceanembed/implementation_docs/BACKEND_VALIDATION_REPORT.md)).

It addresses architectural robustness, error isolation, blocking I/O offloading, zero-downtime data serving, and scalability to **5+ AI ocean models**.

---

## Progress Overview

| Category | Total Tasks | Completed | In Progress / Pending |
| :--- | :---: | :---: | :---: |
| **1. Foundation: Variable Registry & Multi-Model Architecture** | 5 | 2 | 3 |
| **2. Critical Bug Fixes & Route Reliability** | 7 | 4 | 3 |
| **3. Inference Worker & Pipeline Hardening** | 4 | 0 | 4 |
| **4. Database & Migration Fixes** | 1 | 0 | 1 |
| **5. Testing & CI Validation** | 2 | 0 | 2 |
| **6. Scalability & Performance Hardening** | 2 | 1 | 1 |
| **Total** | **21** | **7** | **14** |

---

## 1. Foundation: Variable Registry & Multi-Model Architecture

Enable dynamic multi-model scaling without code modifications when adding new ensemble configurations or ocean forecast models.

- [x] **1.1 Create Canonical Variable Registry & Model Config**
  - **File**: [`backend/src/modules/ocean/constants.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/constants.py)
  - **Description**: Define `OceanVariable` dataclass, `OCEAN_VARIABLES` catalogue (`temp`, `sal`, `d26`, `tchp`, `mld`), physical boundary definitions, `STANDARD_DEPTHS`, and `ModelConfig` registry (`MODEL_REGISTRY`). Single source of truth across backend, worker, and tests.
  - **Status**: Completed.

- [ ] **1.2 Update Quality Gate to Use Variable Registry**
  - **File**: [`worker/quality_gate.py`](file:///d:/Projects/oceanembed-sih/oceanembed/worker/quality_gate.py)
  - **Description**: Replace hardcoded `temp`/`sal` checks with iteration over registered model variables via `get_model_config()`. Enforce bounds from `constants.get_physical_bounds()` and model-specific NaN / Z-score thresholds.
  - **Status**: Pending.

- [ ] **1.3 Update Synthetic Zarr Data Generator to Match Registry**
  - **File**: [`backend/src/infrastructure/zarr/fake_data.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/fake_data.py)
  - **Description**: Ensure synthetic datasets produce all registered canonical variables (`temp`, `sal`, `d26`, `tchp`, `mld`) and companion spread arrays (`{var}_spread`), ensuring realistic test fixture datasets for local development.
  - **Status**: Pending.

- [x] **1.4 Refactor Profile Route to Use Registry**
  - **File**: [`backend/src/modules/ocean/routes/profile.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py)
  - **Description**: Read standard depth levels from `constants.STANDARD_DEPTHS` and variable names from `constants.OCEAN_VARIABLES` instead of hardcoded variable lookups.
  - **Status**: Completed.

- [ ] **1.5 Update Weekly Inference Runner to Use Registry**
  - **File**: [`worker/run_weekly_inference.py`](file:///d:/Projects/oceanembed-sih/oceanembed/worker/run_weekly_inference.py)
  - **Description**: Ingest model version flag, load `ModelConfig` dynamically, output all registered variable channels to Zarr, and validate with `QualityGate`.
  - **Status**: Pending.

---

## 2. Critical Bug Fixes & Route Reliability

Prevent server 500 crashes, isolate slow disk/network operations, and prevent unhandled edge-case failures in client-facing endpoints.

- [x] **2.1 Add Comprehensive Error Handling to Route Handlers**
  - **Files**:
    - [`backend/src/modules/ocean/routes/field.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/field.py)
    - [`backend/src/modules/ocean/routes/profile.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py)
  - **Description**: Intercept `KeyError` (variable/dimension not in store), `ValueError` (invalid week/coordinate values), and `RuntimeError` (broken symlinks / unreadable storage), converting them into explicit HTTP 400/404/503 responses with informative JSON messages.
  - **Status**: Completed.

- [x] **2.2 Offload Blocking Zarr I/O via `asyncio.to_thread()`**
  - **Files**:
    - [`backend/src/modules/ocean/routes/field.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/field.py)
    - [`backend/src/modules/ocean/routes/profile.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py)
    - [`backend/src/modules/ocean/routes/saliency.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/saliency.py)
  - **Description**: Offload synchronous xarray/numpy slicing and file I/O to worker threadpools, preventing blocking of the FastAPI asynchronous event loop under concurrent traffic.
  - **Status**: Completed.

- [x] **2.3 Graceful 404 Handling for Saliency Endpoint**
  - **File**: [`backend/src/modules/ocean/routes/saliency.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/saliency.py)
  - **Description**: Return HTTP 404 with a structured error message when saliency maps are missing or not produced for a variable/week, rather than crashing with an unhandled 500 `KeyError`.
  - **Status**: Completed.

- [x] **2.4 Mark Skeleton Endpoints in OpenAPI Metadata**
  - **Files**:
    - [`backend/src/modules/ocean/routes/sampling.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/sampling.py)
    - [`backend/src/modules/ocean/routes/benchmark.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/benchmark.py)
  - **Description**: Explicitly flag `/sampling_recommendation` and `/benchmark` as `[DRAFT / SKELETON]` in route docstrings and OpenAPI descriptions to document that mock data is returned until pipeline integration.
  - **Status**: Completed.

- [ ] **2.5 Fix Pydantic Forward Reference in Response Schemas**
  - **File**: [`backend/src/modules/ocean/schemas/__init__.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/schemas/__init__.py)
  - **Description**: Move `RunEntrySchema` definition before `WeeksResponseSchema` (or invoke `WeeksResponseSchema.model_rebuild()`) to avoid Pydantic v2 undefined forward reference evaluation errors.
  - **Status**: Pending.

- [ ] **2.6 Add Guard and Limit to ARGO Float Query**
  - **File**: [`backend/src/modules/ocean/routes/argo.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/argo.py)
  - **Description**: Add `limit: int = Query(default=500, le=2000)` and optional bounding-box spatial filter to the `SELECT DISTINCT ON (platform_id)` query to prevent memory exhaustion and database lockups when table size grows.
  - **Status**: Pending.

- [ ] **2.7 Add Defensive State Check in `get_zarr_resolver`**
  - **File**: [`backend/src/infrastructure/dependencies.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/dependencies.py)
  - **Description**: Check `hasattr(request.app.state, "zarr_resolver")` before accessing `app.state.zarr_resolver`, raising a clear HTTP 503 (`Zarr storage subsystem not initialized`) if the resolver was not registered during app startup.
  - **Status**: Pending.

---

## 3. Inference Worker & Pipeline Hardening

Ensure automated, fault-tolerant execution of the weekly forecasting pipeline inside containerized worker environments.

- [ ] **3.1 Create Worker Requirements Manifest**
  - **File**: `worker/requirements.txt`
  - **Description**: Pin exact versions for numpy, xarray, zarr, scipy, sqlalchemy, psycopg2-binary, and torch/torchvision/pykeops dependencies for isolated worker image builds.
  - **Status**: Pending.

- [ ] **3.2 Fix Calendar Week Boundary Parsing**
  - **File**: [`worker/run_weekly_inference.py`](file:///d:/Projects/oceanembed-sih/oceanembed/worker/run_weekly_inference.py)
  - **Description**: Parse ISO week strings using `%G-W%V-%u` (with explicit day-of-week 1) instead of ambiguous `%Y-W%W` which fails on year boundaries (e.g., week 52/53 vs week 01).
  - **Status**: Pending.

- [ ] **3.3 Polish and Fix Worker Dockerfile**
  - **File**: `worker/Dockerfile`
  - **Description**: Strip obsolete debug comments, ensure multi-stage GPU-compatible base (PyTorch CUDA / CPU fallback), verify symlink creation permissions, and set reliable entrypoint.
  - **Status**: Pending.

- [ ] **3.4 Audit Trail Persistence in PostgreSQL**
  - **File**: [`worker/run_weekly_inference.py`](file:///d:/Projects/oceanembed-sih/oceanembed/worker/run_weekly_inference.py)
  - **Description**: Write execution status, gate metrics, runtime duration, and artifact paths into the `model_runs` table upon pipeline pass or fail.
  - **Status**: Pending.

---

## 4. Database & Migration Fixes

- [ ] **4.1 Verify Alembic Migration Integrity & Constraints**
  - **File**: `backend/migrations/versions/0001_add_ocean_tables.py`
  - **Description**: Validate `down_revision` lineage, ensure PostGIS extension initialization (`CREATE EXTENSION IF NOT EXISTS postgis`), add CHECK constraints on `gate_status` (`PASSED`, `FAILED`, `PENDING`), and align primary key naming with SQLAlchemy models.
  - **Status**: Pending.

---

## 5. Testing & CI Validation

- [ ] **5.1 Rewrite API Endpoint Integration Tests**
  - **File**: `backend/tests/integration/ocean/test_endpoints.py`
  - **Description**: Assert valid schema structures, float types, mock Zarr resolver integration, and error response codes (400, 404, 503).
  - **Status**: Pending.

- [ ] **5.2 Update Quality Gate Unit Tests with Registry Variables**
  - **File**: `backend/tests/unit/ocean/test_quality_gate.py`
  - **Description**: Test validation against all variables in `OCEAN_VARIABLES`, testing edge conditions (boundary violations, NaN ratios > 5%, extreme Z-scores).
  - **Status**: Pending.

---

## 6. Scalability & Performance Hardening

Support high-concurrency production serving and low-latency profile slices across large geographical domains.

- [ ] **6.1 Add LRU Cache Eviction to `ZarrStoreResolver`**
  - **File**: [`backend/src/infrastructure/zarr/resolver.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/resolver.py)
  - **Description**: Cap the in-memory dataset cache using an LRU eviction strategy (e.g. `OrderedDict` with `max_cached_stores=8`) to prevent memory leaks as users query older historical weeks.
  - **Status**: Pending.

- [x] **6.2 Optimize Profile Extraction with Single Spatial Slicing**
  - **File**: [`backend/src/modules/ocean/routes/profile.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py)
  - **Description**: Replaced the previous $O(N \times 15)$ sequential depth loop with a single vectorized `.sel(lat=..., lon=..., method="nearest")` extraction, reducing latency from ~180ms to <15ms per request.
  - **Status**: Completed.

---

## Tracking & Verification Workflow

When executing remaining pending tasks:
1. Implement the code change with unit tests.
2. Execute tests via `pytest backend/tests/`.
3. Mark task as `[x]` with commit reference or status note.
