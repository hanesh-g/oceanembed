# OceanEmbed Backend: File-by-File Explanation

This document explains every core file in the OceanEmbed backend from first principles. It focuses on why the file exists, where it fits in the architecture, and how its business logic operates.

---

## 1. `backend/src/infrastructure/zarr/resolver.py` (ZarrStoreResolver)

### 1. File Purpose
*   **Why it exists:** To act as the single source of truth for loading oceanographic data. Zarr stores are massive, so we cannot open and close them on every request.
*   **Where it fits:** It sits at the lowest layer of the API, right above the filesystem, abstracting away directory structures and symlinks from the route handlers.
*   **Dependencies:** Used by `dependencies.py`, which injects it into every route in `modules/ocean/routes/`.

### 2. Business Logic Breakdown
*   **Inputs:** An optional `week` string (e.g., `"2025-W01"`).
*   **Outputs:** A cached `xarray.Dataset` object ready for slicing.
*   **Execution Flow:**
    1.  If a `week` is provided, it directly constructs the path `<root>/week=<week>` and opens it.
    2.  If no week is provided, it aims for the "latest" data. It checks a TTL (Time-To-Live). If the TTL has expired (e.g., 30 seconds passed), it reads the filesystem symlink `<root>/latest` to see where it points.
    3.  It resolves the absolute path of the symlink.
    4.  It checks its in-memory dictionary cache. If the `xarray.Dataset` for that path is already open, it returns it instantly. Otherwise, it opens it via `xr.open_zarr()` and caches it.
*   **Edge Cases Handled:** Detects broken symlinks, missing week directories, and transparently handles zero-downtime hot-swaps of the `latest` pointer.

---

## 2. `backend/src/infrastructure/dependencies.py`

### 1. File Purpose
*   **Why it exists:** FastAPI uses dependency injection for shared resources. Instead of each route opening its own database connection or Zarr resolver, they "request" it from this file.
*   **Where it fits:** Middleware layer between the core application state and the HTTP routes.
*   **Dependencies:** Used by all routes in `backend/src/modules/ocean/routes/`.

### 2. Business Logic Breakdown
*   **Inputs:** The FastAPI `Request` object.
*   **Outputs:** Instantiated resource (e.g., `AsyncSession` or `ZarrStoreResolver`).
*   **Execution Flow (Zarr Resolver):**
    1.  Extracts the `zarr_resolver` that was attached to the global application state during server startup (`request.app.state.zarr_resolver`).
    2.  Returns it to the caller route.
*   **Important Algorithms:** None (pure plumbing).

---

## 3. `backend/src/interfaces/main.py`

### 1. File Purpose
*   **Why it exists:** It is the application entry point where FastAPI is instantiated and configured.
*   **Where it fits:** The very top of the application stack. This is what the ASGI server (Uvicorn) executes.
*   **Dependencies:** Depends on all routers, dependencies, and middleware.

### 2. Business Logic Breakdown
*   **Execution Flow:**
    1.  Registers the `lifespan` context manager. When the server boots, it creates the `ZarrStoreResolver` and attaches it to `app.state`. When the server shuts down, it calls `.invalidate()` to clean up cache.
    2.  Adds CORS middleware (Cross-Origin Resource Sharing) to allow requests from the Vite frontend (`localhost:5173`).
    3.  Includes the `ocean_router`, mapping it to the `/v1/ocean` prefix.

---

## 4. `backend/src/modules/ocean/constants.py`

### 1. File Purpose
*   **Why it exists:** To prevent "magic strings" and ensure the inference worker, API, and quality gate all agree on variable names, physical bounds, and standard depths.
*   **Where it fits:** Domain core. A pure configuration file with zero side effects.

### 2. Business Logic Breakdown
*   **Important Algorithms:** Defines the `OCEAN_VARIABLES` catalogue (e.g., `temp`, `sal`, `d26`, `tchp`) with strict min/max boundaries, and `MODEL_REGISTRY` to support future AI models.

---

## 5. `backend/src/modules/ocean/routes/field.py`

### 1. File Purpose
*   **Why it exists:** To serve 2D horizontal slices of the ocean data (e.g., surface temperature across the entire globe) to the frontend map.
*   **Where it fits:** API presentation layer.

### 2. Business Logic Breakdown
*   **Inputs:** `variable` (e.g., "temp"), `depth` (float), `stride` (int for downsampling).
*   **Outputs:** A JSON array of `{lat, lon, value, uncertainty}` points.
*   **Execution Flow:**
    1.  Requests the live Zarr dataset from `ZarrStoreResolver`.
    2.  Slices the dataset by the requested `depth` using `.sel(depth=...)`.
    3.  Downsamples the grid using `.isel(stride)` to reduce the data payload for the browser.
    4.  Extracts the raw numpy arrays for lat, lon, variable values, and spread (uncertainty) values.
    5.  Uses `np.meshgrid` to generate coordinates, flattens the arrays, and zips them into JSON objects.
*   **Important Algorithms:** `np.meshgrid` and `.ravel()` are used to combine 1D lat/lon arrays into a 2D coordinate grid instantly without Python `for` loops.

---

## 6. `backend/src/modules/ocean/routes/profile.py`

### 1. File Purpose
*   **Why it exists:** To provide vertical cross-sections (depth profiles) when a user clicks a specific point on the map, comparing model predictions against the nearest real-world ARGO float.

### 2. Business Logic Breakdown
*   **Inputs:** `lat`, `lon` (coordinates of the user's click).
*   **Outputs:** Complex JSON object containing depth arrays, temperature arrays, and nearest ARGO float comparisons.
*   **Execution Flow:**
    1.  Queries PostGIS via `get_nearest_argo_profile` to find the geographically closest float.
    2.  Uses `.sel(lat=lat, lon=lon, method="nearest")` to extract a vertical "core sample" from the 3D Zarr array.
    3.  Extracts 15 standard depth layers from that core sample.
    4.  Assembles the data and returns it.

---

## 7. `backend/src/modules/ocean/routes/health.py`

### 1. File Purpose
*   **Why it exists:** To tell the frontend and operators whether the pipeline is running correctly and what data week is currently active.

### 2. Business Logic Breakdown
*   **Execution Flow:** Queries the `model_runs` PostgreSQL table to find the most recent successful pipeline execution and returns its `week_label`.

---

## 8. `backend/src/modules/ocean/routes/argo.py`

### 1. File Purpose
*   **Why it exists:** To serve the coordinates of all active ARGO floats so the frontend can render them as markers on the MapLibre globe.

### 2. Business Logic Breakdown
*   **Execution Flow:** Executes a `SELECT DISTINCT ON (platform_id) lat, lon FROM argo_profiles` query in PostGIS to get the most recent known location of every distinct physical float hardware unit.

---

## 9. `backend/src/modules/ocean/services/postgis_queries.py`

### 1. File Purpose
*   **Why it exists:** Encapsulates raw SQL and geospatial queries so the route handlers don't have to write SQL strings.

### 2. Business Logic Breakdown
*   **Important Algorithms:** Uses the PostGIS `<->` (K-Nearest Neighbors) operator to find the shortest spatial distance between the user's clicked `lat`/`lon` and the `ST_Point` locations of floats in the database.

---

## 10. `worker/quality_gate.py`

### 1. File Purpose
*   **Why it exists:** Acts as an automated QA engineer. It prevents corrupted or hallucinated AI outputs from being published to the live API.

### 2. Business Logic Breakdown
*   **Inputs:** A newly generated `xarray.Dataset` from the AI model.
*   **Outputs:** Boolean `True` (passed) or `False` (failed).
*   **Execution Flow:**
    1.  **Integrity Check**: Scans every variable. If any variable has > 5% `NaN` (null) values, or if its min/max exceed strict physical bounds (e.g., water colder than -2°C), it fails.
    2.  **Drift Check**: Loads historical mean/std from `scaler.json`. Calculates Z-scores. If > 1% of the pixels deviate by more than 4 standard deviations from historical norms (indicating a model hallucination or extreme anomaly), it fails.

---

## 11. `worker/run_weekly_inference.py`

### 1. File Purpose
*   **Why it exists:** The orchestrator script that runs as a cron job every week.

### 2. Business Logic Breakdown
*   **Execution Flow:**
    1.  Downloads/prepares input satellite data.
    2.  Runs the PyTorch AI model to generate 3D forecasts.
    3.  Passes the output to `QualityGate`.
    4.  If it passes, saves it as a Zarr store (`week=YYYY-Www`).
    5.  Atomically swaps the `<root>/latest` symlink to point to the new folder, executing a zero-downtime deployment.
    6.  Logs the result to PostgreSQL.
