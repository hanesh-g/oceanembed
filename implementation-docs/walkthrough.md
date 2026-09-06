# OceanEmbed — Implementation Walkthrough

## Monorepo Layout (Final)

```
oceanembed/
├── backend/                    ← FastAPI API server
│   ├── src/
│   │   ├── infrastructure/
│   │   │   ├── zarr/
│   │   │   │   ├── resolver.py     ← ZarrStoreResolver (symlink TTL, per-week cache)
│   │   │   │   └── fake_data.py    ← synthetic 2-week layout + swap_latest()
│   │   │   ├── dependencies.py     ← ZarrResolverDep added
│   │   │   └── config/settings.py  ← OceanEmbedSettings added
│   │   ├── modules/ocean/
│   │   │   ├── db/
│   │   │   │   ├── models.py       ← ModelRun, ArgoProfile (GeoAlchemy2)
│   │   │   │   └── init.sql        ← PostGIS schema + spatial index
│   │   │   ├── schemas/            ← Pydantic response models
│   │   │   ├── services/
│   │   │   │   └── postgis_queries.py  ← ST_Point(lon, lat, 4326)
│   │   │   └── routes/
│   │   │       ├── field.py        ← /field (binary) + /field_json (vectorized)
│   │   │       ├── profile.py      ← 15-depth + nearest ARGO
│   │   │       ├── health.py       ← current live week + gate audit
│   │   │       └── argo.py         ← ARGO float positions for map
│   │   └── interfaces/
│   │       ├── main.py             ← CORS + Zarr resolver in lifespan
│   │       └── api/v1/__init__.py  ← ocean_router registered
│   └── tests/unit/ocean/
│       └── test_zarr_resolver.py   ← 6 tests incl. pointer-swap
├── frontend/                   ← React + Vite + MapLibre dashboard
│   ├── src/
│   │   ├── api/
│   │   │   ├── types.ts        ← OceanEmbedApi interface (unchanged)
│   │   │   ├── mockOceanApi.ts ← original mock (kept as fallback)
│   │   │   ├── liveOceanApi.ts ← real fetch client → backend
│   │   │   └── index.ts       ← toggle: VITE_USE_MOCK=true → mock
│   │   ├── App.tsx             ← imports from api/index.ts now
│   │   └── map/OceanMap.tsx    ← MapLibre GL (unchanged)
│   ├── vite.config.ts          ← /api proxy → localhost:8000
│   ├── Dockerfile              ← multi-stage: Vite build → nginx
│   └── .env                    ← VITE_USE_MOCK=true default
├── core/                       ← shared preprocessing package
│   ├── pyproject.toml
│   └── oceanembed_core/preprocessing/
│       ├── channels.py, regrid.py, gapfill.py, normalize.py
├── worker/                     ← inference worker (future)
├── model-registry/             ← frozen model bundles
│   └── oceanembed-v1.0.0/manifest.json
├── data/published/             ← immutable weekly Zarr stores
└── docker-compose.yml          ← db + api + frontend
```

---

## Trap Fixes Applied

| Trap | Where | Fix |
|---|---|---|
| **POSIX symlink on Windows** | [`fake_data.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/infrastructure/zarr/fake_data.py) | `_safe_symlink()` branches on `os.name`; atomic rename on POSIX, unlink+create on Windows |
| **GeoAlchemy2 srid** | [`models.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/modules/ocean/db/models.py) | `Geometry(geometry_type='POINT', srid=4326)` — not plain `Geometry()` |
| **X-Shape 3D header** | [`field.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/modules/ocean/routes/field.py) | `depth` is optional; header always encodes all returned dimensions |
| **0.25° JSON bottleneck** | [`field.py`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/backend/src/modules/ocean/routes/field.py) | `/field_json` downsamples by stride=4 (~1,500 points), vectorized via NumPy meshgrid |
| **Volume permissions** | [`docker-compose.yml`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/docker-compose.yml) | `data/published:/data/published:ro` — API never writes |

---

## Frontend ↔ Backend Integration

The frontend's `OceanEmbedApi` interface is preserved exactly:

```
getStatus()     → GET /v1/ocean/health
getField()      → GET /v1/ocean/field_json?variable=...&depth=...&stride=4
getProfile()    → GET /v1/ocean/profile?lat=...&lon=...
getArgoFloats() → GET /v1/ocean/argo_floats
```

Field name mapping happens in [`liveOceanApi.ts`](file:///d:/Projects/oceanembed-sih/oceanembed-backend/frontend/src/api/liveOceanApi.ts):
`temperature → temp`, `salinity → sal`, `uncertainty → temp_spread`.

---

## What Remains

| Item | Phase | Effort |
|---|---|---|
| Alembic migration for ocean tables | 2 | 30 min |
| Saliency, sampling, benchmark endpoints | 3 | 3 hrs |
| Worker: quality_gate.py + run_weekly_inference.py | 4 | 4 hrs |
| Backend Dockerfile | 5 | 30 min |
| CI workflow | 5 | 1 hr |
| Integration tests | 5 | 2 hrs |
