# Tooling & CLI Adaptation Plan (Backlog)

> **Status**: Parked for future review  
> **Target Components**: `cli/`, `.pre-commit-config.yaml`, `.github/workflows/`

This document details the blueprint for converting the retained boilerplate tooling into tailored, production-grade OceanEmbed developer and operator utilities.

---

## 1. Transforming `cli/` into `oe` (OceanEmbed Operator CLI)

The inherited `cli/` package is currently a Typer-based tool (`bp`) configured for boilerplate deployments. It can be restructured into an operator tool (`oe`) to manage data generation, Zarr store inspection, pointer swaps, and ARGO ingestion.

### Desired CLI Commands

```bash
# Data & Pointer Management
oe zarr seed --weeks 2              # Generate synthetic test datasets in data/published/
oe zarr inspect --week latest       # Print dimensions, coordinates, variables, and chunking
oe zarr swap-pointer --to 2026-W36  # Safely trigger atomic pointer swap to week directory

# PostGIS / In-Situ Data
oe argo ingest <path-to-nc-dir>     # Parse NetCDF ARGO profile floats and populate PostGIS
oe argo stats                       # Show active float count and geographic bounding box

# Inference Pipeline (Worker Integration)
oe pipeline run --week 2026-W36     # Trigger weekly inference run locally or in container
oe pipeline quality-check --week latest # Run QualityGate integrity + Z-score validation
```

### Implementation Steps
1. **Rename Package**: Update `cli/pyproject.toml` project name to `oceanembed-cli` with script entry point `oe = "cli.app:app"`.
2. **Commands Layout**:
   ```
   cli/src/cli/
   ├── app.py                 # Main Typer entry point
   ├── commands/
   │   ├── zarr.py            # Subcommands: seed, inspect, swap-pointer
   │   ├── argo.py            # Subcommands: ingest, stats
   │   └── pipeline.py        # Subcommands: run, quality-check
   └── lib/
       └── console.py         # Rich table formatting and status logs
   ```
3. **Workspace Integration**: Keep `members = ["backend", "cli"]` in root `pyproject.toml`. Run via `uv run oe --help`.

---

## 2. Adapting `.pre-commit-config.yaml` for OceanEmbed

Currently contains boilerplate hooks. Adapt to enforce uniform linting and formatting across the monorepo:

### Target Configuration
- **Ruff (Python)**:
  - Scope: `backend/`, `core/`, `worker/`, `cli/`
  - Runs `ruff check --fix` and `ruff format`.
- **Prettier (JavaScript/TypeScript/CSS/JSON)**:
  - Scope: `frontend/`
  - Runs formatting across `.tsx`, `.ts`, `.css`, and `.json` files.
- **Codespell**: Exclude scientific variable names (e.g., `sst`, `sss`, `sla`, `uo`, `vo`).

---

## 3. Adapting `.github/workflows/` for Automated CI

The retained CI templates (`tests.yml`, `linting.yml`, `type-checking.yml`) can be customized for OceanEmbed:

### Workflows
1. **`tests.yml`**:
   - Spawns PostgreSQL + PostGIS service container (`postgis/postgis:16-3.4`).
   - Runs `uv sync` on `backend`.
   - Executes `uv run pytest backend/tests/unit/ocean/` and `uv run pytest core/`.
2. **`linting.yml`**:
   - Runs `uv run ruff check .` and `uv run ruff format --check .`.
   - Runs `cd frontend && npm ci && npm run build` to verify frontend TypeScript compilation.
3. **`type-checking.yml`**:
   - Runs `uv run mypy backend/src/modules/ocean/` to ensure zero type regressions in spatial routes and data resolvers.
