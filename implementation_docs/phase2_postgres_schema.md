# Phase 2 Implementation: Postgres Schema Extension

This document outlines the implementation details for Phase 2 of the OceanEmbed project, which extends the PostgreSQL database schema with PostGIS support for spatial data tracking.

## Overview

The database has been extended to support the operational storage and indexing requirements for the `oceanembed-backend`. This primarily involves the `model_runs` table for auditing the Quality Gate outputs, and the `argo_profiles` table for tracking the oceanic float observations using robust spatial queries.

## Components Implemented

### 1. SQLAlchemy Models (`backend/src/modules/ocean/db/models.py`)
- Created `ModelRun` to store:
  - `week_label`: The ISO week (e.g. `2025-W01`).
  - `gate_status`: Pass/Fail status from the Quality Gate.
  - `gate_log`: The detailed JSONB audit trail.
- Created `ArgoProfile` with:
  - Positional data with an explicit PostGIS Geometry column `Geometry(geometry_type='POINT', srid=4326)`.
  - JSONB arrays for `depth_levels`, `temp_values`, and `sal_values`.

### 2. Alembic Migration Script (`backend/migrations/versions/0001_add_ocean_tables.py`)
- Generated the database migration script.
- **Manual Patching**: Explicitly added the command `CREATE EXTENSION IF NOT EXISTS postgis;` to ensure the required spatial functions are available.
- Added explicit creation of GiST spatial indexes for `geom` on the `argo_profiles` table to heavily optimize nearest-neighbour `<->` distance queries.

## Summary

The database is now equipped with the schema required to securely store the operational audit trail and perform extremely fast spatial proximity queries for aligning observations to our simulated model fields.
