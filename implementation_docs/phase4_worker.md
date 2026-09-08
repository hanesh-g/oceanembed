# Phase 4 Implementation: Inference Worker

This document outlines the implementation details for Phase 4 of the OceanEmbed project, focusing on the Worker lane that handles batch inference and quality assurance.

## Overview

The Inference Worker is responsible for running the weekly batch inference, applying a dual-check quality gate, and atomically publishing the resulting Zarr store to the production system.

## Components Implemented

### 1. Worker Dockerfile (`worker/Dockerfile`)
- Configured a multi-stage Docker build targeting a GPU-capable PyTorch runtime image (`pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`).
- Installed system requirements and the core inference package (`oceanembed-core`).
- Defined the entrypoint for the weekly operational job to execute `run_weekly_inference.py`.

### 2. Quality Gate (`worker/quality_gate.py`)
- Created the `QualityGate` class with a two-step validation framework:
  - **Data Integrity Check**: Validates that NaN values comprise less than 5% of the data and that variable bounds conform to strict physical constraints (e.g., $T \in [-2.0, 36.0]^\circ\text{C}$).
  - **Distribution Drift Check**: Computes standardized Z-scores using a pre-calibrated `scaler.json`. It flags any anomalous distribution drift (e.g., if $>1\%$ of cells exceed $|z| > 4.0$).

### 3. Weekly Inference Script (`worker/run_weekly_inference.py`)
- Implemented the main workflow script to load the model artifacts (channels, scalers, VIF calibration).
- Supports generating dummy output to simulate the 5-member ensemble inference step.
- Applies the calibrated Variance Inflation Factor (VIF) to the simulated spread.
- Passes generated data through the Quality Gate; if verification succeeds, it persists the data to an immutable Zarr store named after the week.
- Integrates the atomic pointer swap mechanism (`os.symlink` and `os.replace` on the `latest` pointer) ensuring the API serves updated data instantly without a restart.

## Summary

Phase 4 establishes the automated pipeline backbone for executing new model inferences and releasing them to the backend smoothly while asserting strict data quality bounds.
