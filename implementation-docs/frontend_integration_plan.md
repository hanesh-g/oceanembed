# Frontend ↔ Backend Integration Plan

## What Your Friend Built

The frontend (`Chatradhara007/inc`) is a **React + Vite + MapLibre GL** ocean dashboard. Already cloned to [`frontend/`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/frontend).

| Piece | Stack |
|---|---|
| Framework | React 18, TypeScript, Vite 6 |
| Map | MapLibre GL JS — GeoJSON point grid, per-cell colouring |
| Profile chart | Hand-rolled SVG — temperature vs depth, uncertainty band, ARGO dots, ARMOR3D line |
| API layer | [`OceanEmbedApi`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/frontend/src/api/types.ts) interface + [`mockOceanApi.ts`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/frontend/src/api/mockOceanApi.ts) generating fake data client-side |

### The API Contract the Frontend Expects

```typescript
interface OceanEmbedApi {
  getStatus(): Promise<RunStatus>;
  getField(field: FieldId, depth: number): Promise<FieldPoint[]>;
  getProfile(location: Coordinate): Promise<Profile>;
  getArgoFloats(): Promise<ArgoFloat[]>;
}
```

**4 endpoints, 4 types:**

| Frontend Method | Returns | Backend Endpoint |
|---|---|---|
| `getStatus()` | `RunStatus` | `GET /v1/ocean/health` |
| `getField(field, depth)` | `FieldPoint[]` | `GET /v1/ocean/field?variable=...&depth=...` |
| `getProfile(location)` | `Profile` | `GET /v1/ocean/profile?lat=...&lon=...` |
| `getArgoFloats()` | `ArgoFloat[]` | `GET /v1/ocean/argo_floats` (new endpoint) |

---

## Key Mismatches to Resolve

### Mismatch 1 — `/field` returns binary, but frontend expects JSON `FieldPoint[]`

The backend plan serves `/field` as a raw `float32` binary buffer (for performance). But the frontend renders GeoJSON points, each with `{lat, lon, value, uncertainty}` — it expects a **JSON array**, not a typed array.

**Two options:**

> [!IMPORTANT]
> **Option A (Recommended): Add a `/v1/ocean/field_json` endpoint** that returns `FieldPoint[]` as JSON. Keep the binary `/field` for any future high-performance clients. The grid is ~17×25 at 1.5° spacing (the frontend's mock uses 1.5° steps, not the backend's 0.25°), so JSON is under 100KB — fine for a dashboard.

> Option B: Keep binary-only and parse `float32` + `X-Shape` header on the frontend. Requires frontend changes to the MapLibre rendering pipeline. More work, less debugging-friendly.

### Mismatch 2 — Frontend field names ≠ backend variable names

| Frontend `FieldId` | Backend `variable` name |
|---|---|
| `"temperature"` | `"temp"` |
| `"salinity"` | `"sal"` |
| `"uncertainty"` | `"temp_spread"` |
| `"tchp"` | `"tchp"` ✅ |
| `"d26"` | `"d26"` ✅ |
| `"mld"` | `"mld"` ✅ |

**Fix: Map in the API client** (`liveOceanApi.ts`) — translate frontend FieldIds to backend variable names before the fetch.

### Mismatch 3 — `RunStatus` vs backend `/health` response shape

Frontend expects:
```typescript
type RunStatus = {
  analysisWeek: string;       // "2026-W35"
  modelVersion: string;       // "oceanembed-v1.0.0"
  gateStatus: "published" | "stale" | "blocked";
  sourceWindow: string;       // "27 Aug – 02 Sep 2026"
  lastUpdated: string;        // "03 Sep 2026 · 06:18 UTC"
};
```

Backend currently returns `{week_label, model_version, gate_status, published_at}`.

**Fix: Shape the response in the backend's `/health` Pydantic schema** or map in the API client.

---

## Proposed Changes

### 1. Monorepo Layout

```
oceanembed-backend/
├── backend/        ← FastAPI API server (unchanged)
├── frontend/       ← React + Vite dashboard (cloned ✅)
├── core/           ← shared Python preprocessing package
├── worker/         ← inference worker
├── data/published/ ← Zarr stores
└── docker-compose.yml
```

### 2. New File: `frontend/src/api/liveOceanApi.ts`

Replace `mockOceanApi` with a real `fetch`-based client implementing the same `OceanEmbedApi` interface:

```typescript
import type { OceanEmbedApi, FieldId, FieldPoint, Profile, ... } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

const FIELD_MAP: Record<FieldId, string> = {
  temperature: "temp",
  salinity: "sal",
  uncertainty: "temp_spread",
  tchp: "tchp",
  d26: "d26",
  mld: "mld",
};

export const liveOceanApi: OceanEmbedApi = {
  getStatus: async () => {
    const res = await fetch(`${API_BASE}/v1/ocean/health`);
    const data = await res.json();
    return {
      analysisWeek: data.week_label,
      modelVersion: data.model_version,
      gateStatus: mapGateStatus(data.gate_status),
      sourceWindow: data.source_window ?? "",
      lastUpdated: data.published_at ?? "",
    };
  },

  getField: async (field, depth) => {
    const res = await fetch(
      `${API_BASE}/v1/ocean/field_json?variable=${FIELD_MAP[field]}&depth=${depth}`
    );
    return res.json();  // FieldPoint[]
  },

  getProfile: async (location) => {
    const res = await fetch(
      `${API_BASE}/v1/ocean/profile?lat=${location.lat}&lon=${location.lon}`
    );
    return res.json();  // Profile
  },

  getArgoFloats: async () => {
    const res = await fetch(`${API_BASE}/v1/ocean/argo_floats`);
    return res.json();  // ArgoFloat[]
  },
};
```

### 3. New Backend Endpoint: `GET /v1/ocean/field_json`

Returns `FieldPoint[]` as JSON for the dashboard's GeoJSON rendering:

```python
@router.get("/field_json")
async def get_field_json(
    variable: str,
    depth: float,
    week: str | None = None,
    resolver: ZarrStoreResolver = Depends(get_zarr_resolver),
) -> list[FieldPointSchema]:
    store = await resolver.get_store(week=week)
    da = store[variable].sel(depth=depth, method="nearest")
    spread_var = f"{variable}_spread"
    spread = store[spread_var].sel(depth=depth, method="nearest") if spread_var in store else None

    points = []
    for i, lat in enumerate(da.coords["lat"].values):
        for j, lon in enumerate(da.coords["lon"].values):
            points.append(FieldPointSchema(
                lat=float(lat), lon=float(lon),
                value=float(da.values[i, j]),
                uncertainty=float(spread.values[i, j]) if spread is not None else 0.0,
            ))
    return points
```

### 4. New Backend Endpoint: `GET /v1/ocean/argo_floats`

Returns all ARGO floats as JSON for the map layer:

```python
@router.get("/argo_floats")
async def get_argo_floats(session: AsyncSessionDep) -> list[ArgoFloatSchema]:
    result = await session.execute(text("SELECT platform_id, lat, lon, profile_date FROM argo_profiles"))
    return [ArgoFloatSchema(id=r.platform_id, lat=r.lat, lon=r.lon, lastProfile=r.profile_date.strftime("%Y-W%V")) for r in result.all()]
```

### 5. Vite Proxy → FastAPI (dev only)

Update [`vite.config.ts`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/frontend/vite.config.ts) to proxy `/api` to the backend:

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

### 6. Update `App.tsx`

Switch the import from `mockOceanApi` to `liveOceanApi`:

```diff
-import { mockOceanApi } from "./api/mockOceanApi";
+import { liveOceanApi as api } from "./api/liveOceanApi";
+// import { mockOceanApi as api } from "./api/mockOceanApi"; // fallback for offline dev
```

### 7. Update `docker-compose.yml`

Add a `frontend` service:

```yaml
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    environment:
      VITE_API_BASE: "http://api:8000"
    depends_on: [api]
```

### 8. Backend CORS

Add `http://localhost:5173` to `CORS_ORIGINS` in `.env.example` so the Vite dev server can hit the API directly during development.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Grid resolution for the dashboard:** The mock uses 1.5° spacing (~680 points). The real backend stores data at 0.25° (~10,000+ points at 15 depths). Should the JSON endpoint downsample to the frontend's 1.5° grid for performance, or serve the full 0.25° grid and let MapLibre handle it?

> [!IMPORTANT]
> **Q2 — Keep `mockOceanApi.ts` as a fallback?** Useful for frontend-only development without a running backend. Recommend: keep it, toggle via an env var `VITE_USE_MOCK=true`.

> [!IMPORTANT]
> **Q3 — Frontend's `DEPTHS` constant vs backend's `STANDARD_DEPTHS`:** The frontend uses `[0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]` but the backend's `channels.py` defines `[0.49, 1.54, 2.65, ...]` (15 GLORYS levels). These are different sets. The backend's `sel(method="nearest")` will snap to the closest stored level, which is fine — but the depth slider labels in the frontend should reflect the actual stored depths, not the mock's arbitrary ones.

---

## Execution Priority

| Step | Effort | Blocks |
|---|---|---|
| Create `liveOceanApi.ts` | 1 hr | Nothing (frontend-only) |
| Add Vite proxy config | 5 min | Nothing |
| Add `field_json` + `argo_floats` endpoints to backend | 2 hrs | Phase 3 routers |
| Shape `/health` response to match `RunStatus` | 30 min | Phase 3 health router |
| Switch `App.tsx` import | 1 min | `liveOceanApi.ts` done |
| Add CORS config | 5 min | Nothing |
| Docker frontend service | 30 min | Dockerfile |
