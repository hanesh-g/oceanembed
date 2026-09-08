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

## How the Simulation Works (Mock vs Real)

The platform supports two modes of operation to decouple frontend development from heavy AI/Data pipelines:

1. **Mock Baseline Mode (Current Default)**:
   - Driven by `fake_data.py`. 
   - Instantly generates structurally perfect, 15-depth synthetic Zarr arrays without needing PyTorch, model weights, or satellite downloads.
   - Allows the frontend team to build and test the UI, API connectivity, and payloads seamlessly. 
   - *Auto-seeds on startup* if no data exists so you never get a 503 error on a fresh clone.

2. **Real Year-Long Simulation Mode**:
   - Driven by the worker pipeline (Implementation Pending Phase).
   - Will download 52 weeks of real Copernicus/ERA5 data (SST, SSS, SLA, Winds) for 2025.
   - Preprocesses and passes data through 5 PyTorch ensemble `.pt` models.
   - Computes derived products (D26, TCHP, MLD) and writes production Zarr stores.
   - *Requires Copernicus API keys and trained model weights.*

---

## Frontend Integration Guide

If your team has already built the React frontend, here is exactly how to drop it into this monorepo so everything works together:

1. **Move your code**: Delete the placeholder contents of the `frontend/` directory and copy your team's entire React project into the `frontend/` folder.
2. **Environment Variables**: Ensure your frontend points its API calls to the FastAPI backend. Create or update your `.env` in the `frontend/` directory:
   ```env
   VITE_API_BASE_URL=http://localhost:8000/v1
   ```
3. **API Endpoints to Connect**:
   - **Status Indicator**: Call `GET /v1/ocean/health` on load to get the current `week_label`.
   - **Map Rendering**: Call `GET /v1/ocean/field_json?variable=temp&depth=0` (or `sal`, `d26`, etc.). Returns `[{lat, lon, value, uncertainty}]` which is highly optimized for MapLibre/Deck.gl.
   - **Depth Profile Chart**: Call `GET /v1/ocean/profile?lat=X&lon=Y` when the user clicks the map. It instantly returns the 15-depth arrays for the temperature/salinity profile chart.
4. **Docker Integration**: Your frontend will automatically be served at `http://localhost:3000` via the existing `docker-compose.yml`. Just ensure your `package.json` scripts (`npm run dev` and `npm run build`) match standard Vite/React conventions, and the existing `docker-compose.yml` will handle the rest.

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
