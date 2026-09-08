# Phase 3 Implementation: OceanEmbed API Endpoints

This document outlines the implementation details for Phase 3 of the OceanEmbed project, which focuses on exposing the backend functionalities via RESTful endpoints.

## Overview

The API endpoints serve as the interface for the frontend application (Vite/React) and downstream services to query the ocean data, check backend health, and fetch nearest-neighbour ARGO float profiles.

## Components Implemented

### 1. API Routers (`backend/src/modules/ocean/api/`)
- **Health Endpoint (`health.py`)**: `GET /v1/ocean/health` verifies that the backend is online and resolves the currently active/live data week pointer (e.g., `2025-W01`).
- **Field Data Endpoint (`field.py`)**: `GET /v1/ocean/field_json` returns vectorized, stride-downsampled fields for frontend visualization (e.g., surface temperature arrays).
- **Argo Floats (`argo.py`)**: `GET /v1/ocean/argo_floats` returns the distinct ARGO floats tracked in the PostGIS spatial database for rendering map markers.
- **Profile Endpoint (`profile.py`)**: `GET /v1/ocean/profile` computes the nearest ARGO float dynamically using PostGIS and returns its 15-depth vertical slice alongside the predicted model values.

### 2. Pydantic Schemas (`backend/src/modules/ocean/schemas/`)
- Designed structured Pydantic response models ensuring strict validation and auto-generating robust OpenAPI schema documentation for all OceanEmbed endpoints.

### 3. Middleware and Integration
- **CORS Configuration**: Explicitly configured CORS middleware for the Vite development server (`http://localhost:5173`) allowing smooth frontend integration.
- **Integration Tests**: Added `backend/tests/integration/ocean/test_endpoints.py` to assert the correct behavior, HTTP statuses, and JSON payload structures for all the newly created endpoints using FastAPI's test client.

## Summary

The core readout API layer is fully operational and thoroughly integrated, providing a high-performance vector pipeline to power the frontend interface.
