# Implementation Plan: Phase 4 (Worker Package & Quality Gate)

This plan outlines the implementation of Phase 4 of the OceanEmbed pipeline, which focuses on building the **Inference Worker** lane. This worker is responsible for running the weekly batch inference, applying the dual-check quality gate, and atomically publishing the resulting Zarr store.

## Proposed Changes

We will implement the following components inside the `worker/` directory:

### Worker Architecture & Dockerization

#### [NEW] `worker/Dockerfile`
- Create a multi-stage Dockerfile based on a GPU-capable PyTorch image (e.g., `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`).
- Install `xarray`, `zarr`, and required dependencies.
- Install the shared `oceanembed-core` package via `pip install -e /app/core` to prevent train/serve skew.
- Set the entrypoint to `run_weekly_inference.py`.

### Quality Gate Implementation

#### [NEW] `worker/quality_gate.py`
- Implement the `QualityGate` class with a dual-check verification system:
  1. **Data Integrity Check**: Ensure NaN fractions are below 5% and variables fall within strict physical bounds (e.g., $T \in [-2.0, 36.0]^\circ\text{C}$, $S \in [10.0, 42.0]\,\text{PSU}$).
  2. **Distribution Drift Check**: Compute per-channel Z-scores using `scaler.json` from the model registry. Flag anomalous distributions where $|z| > 4.0$ on more than 1% of the cells.
- Return a detailed JSON-serializable audit log (`gate_log`) to be persisted in PostgreSQL.

### Weekly Inference Pipeline

#### [NEW] `worker/run_weekly_inference.py`
- Implement the end-to-end batch script that simulates the weekly operational cron job:
  - Load the frozen model bundle (`channels.json`, `scaler.json`, `calibration.json`, and weights) from the model registry.
  - Perform the 5-member ensemble forward pass (using dummy data arrays for the initial skeleton, maintaining the architecture flow).
  - Aggregate ensemble mean and raw spread.
  - Apply the calibrated Variance Inflation Factor (VIF) from `calibration.json` to the spread.
  - Execute the `QualityGate`.
  - On pass: Write the resulting arrays to an immutable Zarr directory (`data/published/week=YYYY-Www`).
  - Perform the atomic symlink swap (`published/latest -> week=YYYY-Www`).

## Verification Plan

### Automated Tests
- The existing `test_zarr_resolver.py` will verify that the API gracefully handles the symlink swap performed by the worker.
- We will add tests for the `QualityGate` logic to ensure out-of-bounds data and anomalous Z-scores are correctly flagged.

### Manual Verification
- We will execute `run_weekly_inference.py` manually and verify that:
  - A new `week=YYYY-Www` directory is correctly provisioned in `data/published`.
  - The `latest` symlink is atomically repointed.
  - The API continues to serve data seamlessly across the swap.
