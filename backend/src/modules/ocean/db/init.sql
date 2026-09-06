-- OceanEmbed PostGIS schema initialisation.
-- Runs once when the postgres container starts (mounted in docker-entrypoint-initdb.d/).

-- Extensions (idempotent)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- model_runs: one row per weekly inference run (pass or fail).
-- The gate_log column is JSONB so per-channel Z-score results can be
-- queried efficiently without deserialising on the application side.
CREATE TABLE IF NOT EXISTS model_runs (
    uuid          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,
    week_label    VARCHAR(20) NOT NULL,
    run_date      TIMESTAMPTZ NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    gate_status   VARCHAR(8)  NOT NULL CHECK (gate_status IN ('pass', 'fail')),
    gate_log      JSONB,
    published_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS model_runs_week_label_idx ON model_runs (week_label);
CREATE INDEX IF NOT EXISTS model_runs_gate_status_idx ON model_runs (gate_status);

-- argo_profiles: ARGO float profiles with PostGIS geometry.
--
-- GeoAlchemy2 / PostGIS note:
--   The geometry column is typed GEOMETRY(POINT, 4326) — NOT plain GEOMETRY.
--   The explicit SRID is required for the <-> nearest-neighbour operator to
--   work correctly as a planar distance in EPSG:4326.  Without it, PostGIS
--   may implicitly cast to GEOGRAPHY and use spherical distance, which:
--     (a) changes the distance metric silently, and
--     (b) prevents the GiST index from being used for <-> in some PG versions.
--
--   Query pattern (note: x=lon BEFORE y=lat — PostGIS uses (x, y) = (lon, lat)):
--       ORDER BY geom <-> ST_Point(:lon, :lat, 4326)  LIMIT 1
--
CREATE TABLE IF NOT EXISTS argo_profiles (
    uuid          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id   VARCHAR(32) NOT NULL,
    profile_date  TIMESTAMPTZ NOT NULL,
    lat           FLOAT       NOT NULL,
    lon           FLOAT       NOT NULL,
    geom          GEOMETRY(POINT, 4326) NOT NULL,
    depth_levels  JSONB       NOT NULL,  -- [float, ...] observed depth levels
    temp_values   JSONB       NOT NULL,  -- [float | null, ...] temperature (°C)
    sal_values    JSONB       NOT NULL   -- [float | null, ...] salinity (PSU)
);

-- GiST spatial index — mandatory for <-> to use the index rather than a seq scan.
CREATE INDEX IF NOT EXISTS argo_geom_gist_idx ON argo_profiles USING GIST (geom);
CREATE INDEX IF NOT EXISTS argo_platform_idx  ON argo_profiles (platform_id);
CREATE INDEX IF NOT EXISTS argo_date_idx      ON argo_profiles (profile_date);
