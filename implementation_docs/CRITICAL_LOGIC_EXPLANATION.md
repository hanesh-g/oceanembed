# OceanEmbed: Critical Logic Explanation

This document provides a deep dive into the most critical algorithms and architectural patterns in the OceanEmbed backend. If you are joining the project or maintaining the code, these are the core concepts you absolutely must understand.

---

## 1. Zero-Downtime Data Swapping (ZarrStoreResolver)

### The Problem
The inference worker produces a massive 3D dataset every week (e.g., `2025-W01`). The backend API needs to serve this data to users. If the API opens the file directly, it locks the file. When the next week's data (`2025-W02`) arrives, how do we switch the API to the new data without shutting down the server or restarting the FastAPI process?

### The Logic (Symlink + TTL Cache)
1. **Immutable Folders**: The worker writes every week to a completely separate, immutable folder (`week=2025-W01/`, `week=2025-W02/`).
2. **The Symlink**: The worker atomically creates a symlink named `latest` that points to the newest folder.
3. **The TTL (Time-To-Live)**: 
   - The API (`resolver.py`) receives a request.
   - It checks a stopwatch. Has it been > 30 seconds since we last checked the symlink?
   - If YES: It uses `os.path.realpath` to read the `latest` symlink. If the symlink now points to `2025-W02`, the resolver detects the change.
   - It opens the new folder using `xr.open_zarr()` and saves it in a dictionary cache, keyed by the absolute path (`/path/to/week=2025-W02`).
   - If NO (TTL hasn't expired): It instantly returns the cached `xarray.Dataset`.

**Why this is brilliant**: The API stays online 100% of the time. The moment the worker finishes generation, it updates the symlink. Within 30 seconds, all API requests seamlessly transition to the new week's data with zero dropped HTTP requests.

---

## 2. Vectorized 3D Data Slicing (`field.py`)

### The Problem
The frontend map needs the surface temperature of the entire ocean. The Earth grid at 0.25° resolution is roughly 1440 x 720 = 1,036,800 pixels. If you use Python `for` loops to extract these values and build a JSON list, the request will take several seconds and block the entire server.

### The Logic (Vectorization)
Instead of loops, we use **Numpy Vectorization**.

```python
# 1. Slice a 2D horizontal sheet from the 3D cube instantly
slice_2d = store["temp"].sel(depth=0.0, method="nearest")

# 2. Downsample (stride) to reduce resolution (e.g. take every 4th pixel)
# This reduces 1 million points to ~64,000 points instantly
ds = slice_2d.isel(lat=slice(None, None, 4), lon=slice(None, None, 4))

# 3. Create grid coordinates
# meshgrid turns 1D lat/lon arrays into 2D matrices that match the data
lon_grid, lat_grid = np.meshgrid(ds.lon.values, ds.lat.values)

# 4. Flatten and Zip
# .ravel() flattens a 2D matrix into a 1D list in C-memory speed
lats = lat_grid.ravel()
lons = lon_grid.ravel()
vals = ds.values.ravel()

# Python zip() iterates through them simultaneously
results = [
    {"lat": float(lat), "lon": float(lon), "value": float(val)}
    for lat, lon, val in zip(lats, lons, vals)
]
```

**Why this is brilliant**: `xarray` and `numpy` execute these operations in highly optimized C/C++ code. Slicing 1 million pixels takes milliseconds.

---

## 3. The Quality Gate Algorithm (`quality_gate.py`)

### The Problem
AI models can hallucinate. If the model accidentally predicts that the ocean temperature in the Caribbean is 150°C, we cannot send that data to users. We need an automated QA layer to intercept corrupt data.

### The Logic (Two-Pass Verification)
1. **Pass 1: Physical Integrity**
   - We check the data against the physical bounds defined in `constants.py`.
   - Temperature must be between -2°C and 36°C.
   - We also check for `NaN` (null/missing) values. If a satellite image was corrupt and the AI generated a blank map, the `NaN` fraction will spike. We fail the gate if > 5% of the map is missing.

2. **Pass 2: Distribution Drift (Z-Scores)**
   - Even if the water is 35°C (which is physically possible), it would be a hallucination if it happened in Antarctica.
   - We load a `scaler.json` file containing the historical *mean* and *standard deviation* for every pixel on Earth.
   - We calculate the Z-score for the new prediction: `z = |prediction - mean| / std`.
   - A Z-score of 4.0 means the prediction is a 4-sigma anomaly (a 1 in 31,000 statistical event).
   - If more than 1% of the ocean has a Z-score > 4.0, we assume the AI has drifted/hallucinated and we fail the gate.

**Why this is brilliant**: It combines hard physics limits with localized statistical anomaly detection, ensuring safety even if the AI silently deteriorates.

---

## 4. Geospatial K-Nearest Neighbors (`postgis_queries.py`)

### The Problem
When a user clicks on the map (e.g., `Lat: 10.5, Lon: -40.2`), we need to find the real-world ARGO float closest to that click to compare it to our AI model. Checking the distance to every float in Python is too slow.

### The Logic (PostGIS `<->` Operator)
We push the math into the PostgreSQL database using the PostGIS extension.

```sql
SELECT platform_id
FROM argo_profiles
ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
LIMIT 1;
```

1. **`ST_MakePoint(:lon, :lat)`**: Creates a spatial point from the user's click.
2. **`4326`**: Tells the database this is WGS84 GPS coordinates (Earth degrees).
3. **`<->` Operator**: This is the magic. It calculates the 2D bounding box distance using the GiST spatial index on the table. It does *not* scan every row; it uses a spatial R-tree to instantly traverse to the nearest neighbor.

**Why this is brilliant**: The database leverages spatial indexing, dropping the query time from hundreds of milliseconds to under 2 milliseconds, regardless of how many floats are in the database.
