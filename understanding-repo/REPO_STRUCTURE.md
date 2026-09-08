# OceanEmbed Monorepo Structure Guide

Welcome to the OceanEmbed monorepo! This repository contains multiple loosely-coupled but highly-integrated components that together form the OceanEmbed platform: a full-stack AI ocean forecasting system.

Below is a breakdown of every top-level directory in the repository, explaining its purpose and how it fits into the broader architecture.

---

## 🏗️ 1. `backend/`
**The Core API Gateway**

This folder contains the **FastAPI Python backend**. It serves as the read-only data plane for the frontend application.
- **Responsibility**: It handles HTTP requests, authenticates admin users, queries the PostGIS database for ARGO float locations, and reads the massive 3D Zarr datasets from the disk.
- **Key Concepts**: It uses a highly optimized `ZarrStoreResolver` to dynamically read the newest weekly data without downtime. It uses `xarray` and `numpy` to serve vectorized data to the frontend at lightning speed.
- **Sub-folders**: 
  - `src/interfaces/`: Entry points (FastAPI `main.py`, routers).
  - `src/infrastructure/`: Database connections, settings, Zarr configuration.
  - `src/modules/ocean/`: The core OceanEmbed business logic (routes, schemas, queries).

## 🖥️ 2. `frontend/`
**The User Dashboard**

This folder houses the **React + Vite + TypeScript frontend**.
- **Responsibility**: Provides the interactive, 3D/2D visual map interface for scientists and operators to explore the ocean forecasts. 
- **Key Concepts**: It fetches vectorized JSON grids and profile cross-sections from the `backend/` API and renders them using mapping libraries (like MapLibre/Deck.gl).
- **Architecture**: Contains its own `Dockerfile` to compile the static assets and serve them via an Nginx proxy.

## ⚙️ 3. `worker/`
**The Heavy Lifting AI Engine**

This folder contains the out-of-process **inference worker**. 
- **Responsibility**: It runs on a scheduled basis (e.g., weekly) to execute the AI models. It is designed to run on GPU-enabled hardware.
- **Key Concepts**:
  - Pulls satellite data.
  - Runs the PyTorch AI models.
  - Executes the **Quality Gate** (`quality_gate.py`) to prevent corrupt or hallucinated data from being published.
  - Writes the final output to the `data/` folder as Zarr stores.
  - Automatically updates the `latest` symlink for zero-downtime deployments.

## 🧠 4. `core/`
**Shared Machine Learning Utilities**

This folder is a standalone Python package (`oceanembed-core`).
- **Responsibility**: To provide shared utility functions that both the `backend/` and `worker/` might need. 
- **Key Concepts**: Contains logic for data preprocessing, spatial regridding, gapfilling, channel normalization, and any core mathematical operations that span across multiple services.

## 🗄️ 5. `data/`
**The Data Volume**

This folder acts as the storage volume for the application.
- **Responsibility**: Holds the massive published ocean datasets.
- **Key Concepts**:
  - `data/published/`: Contains subdirectories like `week=2025-W01/`, which hold the `.zarr` chunked data arrays.
  - Holds the `latest` symlink that tells the API which week is currently active.
  - **Permissions**: The `backend/` container mounts this directory as Read-Only (`:ro`), while the `worker/` mounts it as Read/Write (`:rw`).

## 🛠️ 6. `cli/`
**Operator Tooling**

This folder contains the **OceanEmbed Operator CLI (`oe`)**.
- **Responsibility**: Provides command-line tools for system administrators to manage the platform.
- **Key Concepts**:
  - Useful for debugging Zarr stores, manually triggering pipeline runs, forcefully swapping the data pointer, or seeding fake data.
  - Built with Typer/Click.

## 📦 7. `model-registry/`
**The AI Model Catalog**

This folder acts as an internal registry for the trained AI models.
- **Responsibility**: Stores the configuration and manifests of different AI models.
- **Key Concepts**: For example, `oceanembed-v1.0.0/manifest.json` defines what variables the model predicts, its resolution, and where its PyTorch weights are stored. The worker dynamically reads this registry to know how to execute the forecast.

## 📚 8. `implementation_docs/` (and `implementation-docs/`)
**Project Documentation & Architecture Reports**

These folders contain Markdown files generated during the design and audit phases.
- **Responsibility**: Acts as the project's brain trust.
- **Key Concepts**: You'll find master plans, architecture diagrams, backend validation reports, and comprehensive task lists detailing technical debt, scalability hardening, and bug fixes.

## 🤖 9. `.github/`
**Continuous Integration (CI/CD)**

This folder handles automation.
- **Responsibility**: Defines GitHub Actions workflows.
- **Key Concepts**: Automatically runs `pytest` suites against the backend, tests the PostGIS integrations, and ensures code quality via `pre-commit` hooks.

---

### How it all connects:
1. The **`worker/`** reads AI model configs from **`model-registry/`** and utilities from **`core/`**.
2. The **`worker/`** generates forecasts and saves them into the **`data/`** directory.
3. The **`backend/`** (API) reads the Zarr files from **`data/`** and connects to the PostgreSQL database.
4. The **`frontend/`** queries the **`backend/`** via HTTP and renders the interface for the user.
5. The **`cli/`** provides an administrative backdoor to manage the data state.
