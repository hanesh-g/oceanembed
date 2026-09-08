# Mock Data Pipeline — Reliability Audit

I traced the entire request path from `docker compose up` → API startup → every endpoint response. Here's the honest verdict:

## ✅ What Works Right Now (No Changes Needed)

| Component | Status | Notes |
|-----------|--------|-------|
| [`docker-compose.yml`](file:///d:/Projects/oceanembed-sih/oceanembed/docker-compose.yml) | ✅ Solid | PostGIS + API + Frontend, correct volume mounts, healthchecks |
| [`init.sql`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/db/init.sql) | ✅ Solid | Schema, indexes, PostGIS extensions — all correct |
| [`resolver.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/resolver.py) | ✅ Solid | TTL-based symlink re-resolution, cache, error handling |
| [`fake_data.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/fake_data.py) | ✅ Solid | Generates 2 valid Zarr stores with correct variable names + spreads |
| [`field.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/field.py) | ✅ Solid | Binary + JSON endpoints, proper validation, asyncio.to_thread |
| [`saliency.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/saliency.py) | ✅ Safe | Returns 404 gracefully when saliency data doesn't exist |
| [`sampling.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/sampling.py) | ✅ Safe | Returns hardcoded placeholder — won't crash |
| [`benchmark.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/benchmark.py) | ✅ Safe | Returns hardcoded placeholder — won't crash |
| [`constants.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/constants.py) | ✅ Solid | Clean registry pattern, variables match fake_data.py |
| [`.gitignore`](file:///d:/Projects/oceanembed-sih/oceanembed/.gitignore) | ✅ Solid | `.env` is ignored, no secrets will leak |

---

## 🔴 Issues That WILL Crash or Break the Demo

### Issue 1: No mock data exists — API crashes on startup

[`data/published/`](file:///d:/Projects/oceanembed-sih/oceanembed/data/published) is **empty** (just `.gitkeep`). When the API starts, [`main.py` line 24](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/interfaces/main.py#L24) creates the `ZarrStoreResolver`, which is fine. But the **first request** to `/field_json` or `/profile` calls `resolver.get_store(week=None)` → [`_read_latest_symlink()`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/resolver.py#L150-L167), which raises `RuntimeError` because there's no `latest` symlink.

> [!CAUTION]
> **Every Zarr-dependent endpoint will return `503 Service Unavailable`** until someone runs `fake_data.py` to generate the mock stores.

**Fix needed:** Auto-generate mock data on first `docker compose up`, OR add a startup script to the API container.

---

### Issue 2: `fake_data.py` dimensions don't match `STANDARD_DEPTHS`

| Source | Depths |
|--------|--------|
| [`fake_data.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/fake_data.py#L33) | `[0.0, 50.0, 200.0]` (3 depths) |
| [`constants.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/constants.py#L31-L33) | `[0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]` (15 depths) |

The [`/profile` endpoint](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py#L69) loops over all 15 `STANDARD_DEPTHS` and calls `.sel(depth=d, method="nearest")`. With only 3 depths in the store, xarray will silently snap to the nearest available depth. This means:
- Depths 0, 5, 10, 20, 30 all snap to `0.0`
- Depths 50, 75, 100, 125 snap to `50.0`
- Depths 150, 200, 300, 500, 700, 1000 snap to `200.0`

> [!WARNING]
> **The profile chart will show a staircase pattern with only 3 unique values** instead of a smooth temperature curve. It won't crash, but it looks obviously broken to a reviewer.

**Fix needed:** Update `fake_data.py` to use all 15 `STANDARD_DEPTHS`.

---

### Issue 3: `/health` and `/weeks` crash if PostGIS tables are empty

[`health.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/health.py#L28-L36) handles the "no data" case gracefully (returns `"week_label": "no-data"`), so this won't crash.

But [`/argo_floats`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/argo.py#L19-L43) hits `argo_profiles` directly. If the table is empty, it returns `[]` — which is fine.

The [`/profile`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py#L90-L96) endpoint also handles `argo_row = None` gracefully.

> [!NOTE]
> **PostGIS endpoints are actually safe** with empty tables. No fix needed here.

---

### Issue 4: `FieldPointSchema` doesn't allow `None` values

[`field.py` line 153](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/field.py#L153) explicitly converts NaN → `None`, but [`FieldPointSchema`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/schemas/__init__.py#L19-L24) declares:
```python
value: float       # ← does NOT allow None
uncertainty: float  # ← does NOT allow None
```

If any grid cell has NaN (which happens in real ocean data along coastlines), Pydantic validation will **reject** the response with a 500 error.

> [!WARNING]
> **This won't crash with the current synthetic data** (numpy random never produces NaN), but it WILL crash when you switch to real Copernicus data with land masks.

**Fix needed:** Change schema to `value: float | None` and `uncertainty: float | None`.

---

### Issue 5: `data/published/` is gitignored — clones get no mock data

The `.gitignore` doesn't explicitly list `data/published/`, but `data/published/week=2025-W01/` Zarr directories contain `.zarray`, `.zattrs`, and binary chunk files that would be committed. However, since `data/published/` is currently empty (just `.gitkeep`), anyone cloning the repo gets an empty data directory and a broken API.

> [!IMPORTANT]
> **Anyone who clones the repo must manually run `fake_data.py` before the API works.** This should be automated or documented.

---

## 🟡 Non-Critical Improvements (Nice to Have)

### Issue 6: Worker uses different variable names than the backend

| Worker ([`run_weekly_inference.py`](file:///d:/Projects/oceanembed-sih/oceanembed/worker/run_weekly_inference.py#L39-L40)) | Backend ([`constants.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/constants.py#L71-L78)) |
|---|---|
| `thetao`, `so` | `temp`, `sal` |
| `thetao_spread`, `so_spread` | `temp_spread`, `sal_spread` |

The worker generates `thetao` and `so` (CMIP6 naming), but the API expects `temp` and `sal`. If you ever run the worker instead of `fake_data.py`, every `/field` and `/profile` request will return 404 ("Variable 'temp' not found").

> [!WARNING]
> **The worker and the backend are completely disconnected.** The worker's output is incompatible with the API.

---

### Issue 7: No `.env.example` file

There's no `.env.example` in the repo. The settings file has sensible defaults, but a teammate cloning the repo won't know about `PUBLISHED_ZARR_ROOT`, `DATABASE_URL`, etc.

---

## Summary Verdict

| Category | Count |
|----------|-------|
| 🔴 **Will crash/break the demo** | 2 (no mock data on startup, schema NaN rejection) |
| 🟡 **Looks broken but won't crash** | 1 (3 depths instead of 15 — staircase profile) |
| 🟡 **Future landmine** | 2 (worker variable mismatch, no .env.example) |
| ✅ **Works correctly** | Everything else |

## Recommended Fixes Before Pushing

These are the **minimum changes** to make the mock pipeline reliable for a demo:

### Fix 1: Auto-seed mock data on API startup
Add a startup check in [`main.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/interfaces/main.py) that calls `create_fake_published_layout()` if the `latest` symlink doesn't exist.

### Fix 2: Use all 15 depths in `fake_data.py`
Replace `DEPTHS = np.array([0.0, 50.0, 200.0])` with the full `STANDARD_DEPTHS` list.

### Fix 3: Allow None in `FieldPointSchema`
Change `value: float` → `value: float | None` and `uncertainty: float` → `uncertainty: float | None`.

### Fix 4: Align worker variable names
Change `thetao` → `temp` and `so` → `sal` in `run_weekly_inference.py`, or add a rename mapping.

### Fix 5: Add `.env.example`
Create a template with all required env vars and sensible defaults.

> [!TIP]
> Shall I apply these 5 fixes now? They're all small, surgical changes — none of them restructure the codebase. You can push a clean, demo-ready repo right after.
