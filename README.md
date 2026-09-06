# OceanEmbed

**AI-Driven Weekly 3D Ocean Subsurface Forecasting & High-Resolution Synthesis Pipeline**

> Built for the Smart India Hackathon (SIH). OceanEmbed reconstructs full 3D ocean state profiles (Temperature, Salinity, Velocity, Uncertainty) across the Indian Ocean basin from surface satellite observations and validates predictions against in-situ ARGO profiling floats.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────────────┐
                      │              Surface Observations              │
                      │       (SSH, SST, SSS, Wind Stress)             │
                      └───────────────────────┬────────────────────────┘
                                              │
                                              ▼
                                 ┌────────────────────────┐
                                 │     Inference Worker   │
                                 │   (weekly cron / GPU)  │
                                 └───────────┬────────────┘
                                             │  writes & validates
                                             ▼
                     ┌────────────────────────────────────────────────┐
                     │          Published Zarr Storage & PostGIS      │
                     │  data/published/week=YYYY-Www/ (0.25° grid)    │
                     │  PostGIS: ARGO float index & ModelRun audit    │
                     └───────────────────────┬────────────────────────┘
                                             │  reads (:ro)
                                             ▼
                                 ┌────────────────────────┐
                                 │    FastAPI Backend     │
                                 │ (zero-copy Zarr slices)│
                                 └───────────┬────────────┘
                                             │  REST / Binary stream
                                             ▼
                                 ┌────────────────────────┐
                                 │    React + MapLibre    │
                                 │   Interactive Client   │
                                 └────────────────────────┘
```

---

## Monorepo Layout

```
oceanembed/
├── backend/                  # FastAPI high-performance API server
│   ├── src/
│   │   ├── infrastructure/
│   │   │   ├── zarr/         # ZarrStoreResolver (symlink TTL, cache, fake data)
│   │   │   ├── config/       # Pydantic v2 settings (OceanEmbedSettings)
│   │   │   └── dependencies. # Dependency injection (db, zarr, auth)
│   │   └── modules/
│   │       ├── ocean/        # Core OceanEmbed domain (routes, models, schemas)
│   │       │   ├── db/       # PostGIS GeoAlchemy2 models (ModelRun, ArgoProfile)
│   │       │   ├── routes/   # /field, /field_json, /profile, /argo_floats, /health
│   │       │   ├── schemas/  # Pydantic output schemas & metadata headers
│   │       │   └── services/ # PostGIS spatial distance & ARGO matching queries
│   │       └── [dormant]/    # user, auth, api_keys, tier, rate_limit (retained)
│   └── tests/                # Pytest unit & integration suites
├── frontend/                 # React 18 + Vite + MapLibre GL Dashboard
│   ├── src/
│   │   ├── api/              # liveOceanApi (real backend) & mockOceanApi toggle
│   │   ├── components/       # MapView, DepthSlider, ProfileChart, MetricsBar
│   │   └── types/            # TypeScript domain types & state schemas
│   └── nginx.conf            # Production static server with /api reverse proxy
├── core/                     # Shared ocean processing package (oceanembed-core)
│   └── oceanembed_core/      # Regridding, gap-filling, normalization, channels
├── worker/                   # Weekly inference automation & quality gating
├── data/
│   └── published/            # Partitioned weekly Zarr stores (week=YYYY-Www)
├── implementation-docs/      # SIH Master Plan, architecture diagrams & audit docs
└── docker-compose.yml        # Orchestrated multi-service local & production stack
```

---

## Key Features

- **Partitioned Zarr Storage**: Fast, multi-dimensional array access partitioned by week directory (`week=YYYY-Www`). Supports zero-downtime updates via atomic symlink pointer swaps (`latest -> week=YYYY-Www`).
- **High-Performance Slicing**:
  - `/v1/ocean/field`: Returns raw binary `float32` byte streams for canvas rendering with dimensional metadata in `X-Shape`, `X-Min`, and `X-Max` headers.
  - `/v1/ocean/field_json`: Optimized vector-strided GeoJSON-friendly payload for web maps without blocking the event loop.
- **In-Situ ARGO Matching**: GeoAlchemy2 PostGIS `<->` spherical distance operator queries profiles nearest to any clicked coordinate.
- **Uncertainty Envelopes**: Full 15-depth profile depth synthesis with $2\sigma$ error bars and ARMOR3D climatological baselines.
- **Zero PyTorch Dependency in API**: The serving API container is lightweight (~180MB) and reads published Zarr stores in read-only mode (`:ro`), keeping GPU dependencies isolated inside worker nodes.

---

## Quickstart

### Option 1: Docker Compose (Full Stack)

Run the backend, PostGIS database, and frontend dashboard with one command:

```bash
docker compose up --build
```

- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/v1/ocean/health](http://localhost:8000/v1/ocean/health)

### Option 2: Local Development

#### Backend
```bash
cd backend
uv sync
uv run python -m src.infrastructure.zarr.fake_data  # Generate sample Zarr stores
uv run uvicorn src.interfaces.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

*Note: The frontend defaults to live API mode with a fallback mock toggle (`VITE_USE_MOCK=false` in `frontend/.env`).*

---

## Testing

Run unit tests for the Zarr resolver and API endpoints:

```bash
cd backend
uv run pytest tests/unit/ocean/ -v
```

---

## License

This project is licensed under the MIT License — see the [LICENSE.md](LICENSE.md) file for details.
