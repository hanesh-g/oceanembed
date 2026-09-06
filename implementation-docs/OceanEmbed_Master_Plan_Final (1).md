# OceanEmbed Backend — Master Plan (Final)
### Architecture + Learning + Implementation — supersedes the earlier draft

**How to use this document:** this replaces the previous master plan. It keeps everything from that version that held up, folds in the stronger patterns your team's architecture diagram already introduced (immutable weekly storage, atomic publish, frozen artifact bundling, per-member downstream products), and explicitly fixes the handful of things the earlier draft got wrong or left open. Work top to bottom; Part A is understanding before code, B–E are locked decisions, F–H are what you execute, I is what you carry into the INCOIS conversation.

---

## Part A — First-principles understanding

### A.1 What the backend is, in one sentence
A read-only serving layer that turns pre-computed, versioned weekly model outputs into JSON for a dashboard. **It never runs the model, never imports PyTorch, and never trusts a single in-memory reference to "the current data" for longer than it takes to double-check that reference is still current.** That last clause is new relative to the earlier draft — it's the fix for the biggest gap in that version, explained in A.3.

### A.2 The three-lane shape, confirmed correct
Your architecture diagram validated the shape from the earlier plan and made it concrete:

```
OFFLINE TRAINING LANE (isolated, GPU, runs rarely)
  historical data → shared preprocessing → train 5-member ensemble
  → evaluate & calibrate uncertainty → package model bundle
        (member_0..4.pt, scaler.json, channels.json, calibration.json)
                        ↓
                  MODEL REGISTRY (frozen artifact store)
                        ↓
INFERENCE WORKER (batch, weekly, GPU, loads frozen bundle only)
  cron trigger → ingest weekly satellite feeds → harmonize (same
  shared preprocessing package used in training) → ensemble forward
  pass → derive T/S/D26/TCHP/MLD PER MEMBER → aggregate mean+spread
  with calibrated variance inflation → quality gate
        ↓ pass                              ↓ fail
  write immutable Zarr                 failure alert,
  (week=YYYY-Www)                      previous week stays live
        ↓
  atomically swap published/latest symlink
        ↓
STORAGE LAYER (read-only boundary)
  published Zarr (immutable, one dir per week) + Postgres/PostGIS
  (run metadata, gate status, ARGO markers)
        ↓
API SERVER (FastAPI, zero PyTorch, pure reader) → dashboard
```

Keep this shape. It is not "the hackathon version of a real system" — it is the real system, already correctly specified. Your job is implementation, not redesign.

### A.3 The one correction to internalize: don't cache "current" forever
The earlier draft told you to open the Zarr store once at API startup and hold that handle for the process lifetime. **That advice is wrong given the atomic-symlink publish pattern, and it's important to understand why**, not just patch it mechanically:

`published/latest` is a symlink that gets atomically repointed once a week, after a successful publish. If your API resolves that symlink once at startup and never again, it will keep serving last week's data correctly right up until a new week publishes — and then keep serving the *old* week forever afterward, silently, with no error, because nothing ever told the API to look again. This is worse than a crash: a crash gets noticed immediately; this gets noticed whenever someone happens to check the date on the dashboard.

**The fix:** re-resolve the `published/latest` pointer on a short interval (a cheap `os.readlink()` check every N seconds, or on every request if that's cheap enough — resolving a symlink is not expensive) rather than once at process start. Cache the *opened* Zarr handle for a given resolved week, but always re-check whether the pointer still points where you think it does before trusting that cache.

### A.4 Why the frozen-artifact-bundle pattern matters more than it looks
Bundling `member_0..4.pt` + `scaler.json` + `channels.json` + `calibration.json` together in the model registry directly closes a real bug class: the earlier conversation surfaced an actual inconsistency across your own docs about whether the model takes 5 or 12 input channels. Writing `channels.json` once, at training time, and having the inference worker read it rather than assume it, makes that class of bug structurally impossible going forward — whatever the model actually saw during training is the only source of truth, checked in as data, not re-typed from memory in a second document.

### A.5 What's still genuinely open (carry this forward, don't let the diagram's polish hide it)
Three real gaps survive even in the corrected design — not backend bugs, but things the backend should be honest about rather than paper over:

1. **A per-channel Z-score check (against `scaler.json`'s training mean/std) is cheap enough to make mandatory, and F.10 now builds it alongside the integrity checks — but it only catches univariate outliers, not novel combinations.** If every individual channel falls within its historically-seen range, but the *joint pattern* across channels is one the model never saw (a genuinely novel cyclone or heatwave signature built from otherwise-ordinary-looking individual values), this check still waves it through. That residual gap is real and worth naming honestly — it's the systems-level version of the ensemble-overconfidence problem, and a per-channel bounds check narrows it without closing it.
2. **Variance inflation calibrated against ARGO matchups is a real fix, not a full one.** It corrects for the ensemble being systematically underdispersed *on average, on historical data*. It does not make the ensemble members disagree more on a genuinely novel input they were all equally unequipped to predict — that failure mode is about the ensemble's shared blind spot, not its calibration constant.
3. **"Harmonize & Check Drift" being labeled a "shared package" between the training and inference lanes needs an explicit confirmation, not an assumption.** If gap-fill/regridding code genuinely is byte-for-byte identical in both lanes, this is exactly right. If it's two separate implementations that happen to do similar things, that's a train/serve skew risk that shows up as slow, hard-to-diagnose accuracy drift rather than an obvious bug — worth a five-minute check against the actual codebase, the same way the channel-order question was.

---

## Part B — Final tech stack (locked)

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite | already decided, no change |
| Map | MapLibre GL JS + deck.gl | no token/billing lock-in vs. Mapbox |
| Charts | Plotly.js | built-in error-band rendering for uncertainty profiles |
| **API server** | FastAPI, Python — **zero PyTorch dependency** | reads Zarr + Postgres only, ever |
| **Inference worker** | separate process/container, PyTorch, GPU | runs weekly, loads frozen bundle, writes results |
| Gridded data store | Zarr, **one immutable directory per week** (`week=YYYY-Www`) | chunked slicing, never overwritten in place |
| Publish mechanism | **atomic symlink swap** (`published/latest → week=...`) | readers never observe a half-written week |
| Model artifacts | frozen bundle: `member_0..4.pt`, `scaler.json`, `channels.json`, `calibration.json` in a **model registry** | single source of truth for what the model expects, versioned like the data |
| Metadata + spatial store | PostgreSQL + PostGIS | run status, gate status, model version, ARGO markers, nearest-neighbor queries |
| Scheduling | cron or scheduled GitHub Action | one weekly job, no orchestrator needed |
| Testing | pytest + FastAPI `TestClient` | fixtures, not the real dataset |
| Linting/formatting | ruff + black | prevents merge-conflict drift across the team |
| Containerization | Docker + docker-compose, from day one | not "later" |
| CI | GitHub Actions | test + build image on every push |
| Config | pydantic-settings + `.env` | no hardcoded paths anywhere |

---

## Part C — Starting point: the boilerplate

Clone **`benavlabs/FastAPI-boilerplate` ("Fastro")** as your literal starting point — async SQLAlchemy 2.0 + PostgreSQL + Pydantic v2 + Docker + pytest, no frontend or unrelated scaffolding to strip first.

On cloning:
- Leave any Redis wiring dormant if present — don't spend time removing it, just don't connect it to anything yet.
- Do not pull in JWT/RBAC/rate-limiting/OpenTelemetry variants — solving problems you don't have yet costs hackathon hours you do need.
- Confirm the base image has no `torch` in it. If it does, that's the first deletion.
- What it won't give you, regardless: Zarr reading logic, PostGIS nearest-neighbor queries, symlink re-resolution logic, or anything domain-specific. That's the real work, same as before.

---

## Part D — Learning plan (in dependency order)

### D.1 FastAPI core concepts (~half day)
- Pydantic response models for every endpoint — never a raw `dict`.
- Dependency injection for sharing the DB pool and the (re-resolvable) Zarr handle across endpoints.
- Lifespan events — open the DB pool once; **do not treat the Zarr "latest" resolution the same way** (see D.2).
- Exception handlers — typed JSON errors, never a raw traceback.
- Skip for now: OAuth2/security, WebSockets, GraphQL.

### D.2 xarray + Zarr, including the publish-pointer pattern and the payload format (~half day + 2 extra hours)
- `xr.open_zarr(path)`, `.sel(depth=..., time=..., method="nearest")` for slicing.
- **`/field` must NOT serialize via `.values.tolist()` → JSON.** A full domain slice — 0.25° over the North Indian Ocean (~100×240 cells) across all 15 depths — is on the order of 360,000 floats. As ASCII JSON that inflates past ~12 MB per response, which blocks the FastAPI worker on encoding and spikes browser memory on decode. Serve it instead as a **raw binary buffer**: cast to `float32`, call `.tobytes()`, return it with `Content-Type: application/octet-stream` (or use Apache Arrow if you want typed multi-array columns in one response). This keeps the full 15-depth payload under ~1.5 MB and makes client-side depth-slider slicing an in-memory array read instead of a JSON re-parse on every drag.
- **`/profile` and other single-point endpoints stay plain JSON.** A 15-depth profile at one lat/lon is a few hundred floats — small enough that JSON's readability and easy debugging are worth keeping. The binary-payload fix is specifically for full-grid responses, not a blanket rule for every endpoint.
- Chunking matched to your actual query pattern.
- **New, specific to this design:** `os.readlink()` (or equivalent) to resolve `published/latest` cheaply, and a small pattern for "cache the opened store keyed by resolved week, re-check the pointer before trusting the cache." This is a short, mechanical thing to learn, but it's the exact fix for A.3 — don't skip it just because it seems minor.

### D.3 PostgreSQL + PostGIS (~half day if SQL is new)
- Schema: `model_runs` (run date, model version, **gate status**, gate log), `argo_profiles` (lat, lon, date, `geometry(Point)`).
- Nearest-neighbor query: `ORDER BY geom <-> ST_Point(lon, lat) LIMIT 1`.
- SQLAlchemy async or asyncpg — pick one, move on.

### D.4 Testing: pytest + FastAPI `TestClient` (~2–3 hrs)
- Tiny synthetic fixtures — a fake multi-week Zarr layout (at least two weeks, so you can actually test that pointer-swapping works) and a handful of fake DB rows.
- Per endpoint: happy path, missing-date 404, bad-param 422, **plus one test that publishes a second fake week and confirms the API picks it up without a restart** — this is the test that would have caught the caching bug in the earlier draft.

### D.5 Docker + docker-compose (~2–3 hrs if new)
- Separate Dockerfiles for `api` and `worker` — API image has no `torch`.
- `docker-compose.yml`: `api`, `worker`, `postgres` (postgis image), a shared volume laid out as `published/week=YYYY-Www/...` with a `published/latest` symlink inside it.

### D.6 Config management (~30 min)
- `pydantic-settings` reading `.env` — DB connection string, root path to the published storage volume, log level, and the re-resolution interval for the `latest` pointer.

### D.7 CI (~30 min)
- GitHub Actions: pytest on push, then build both Docker images.

---

## Part E — Project structure

```
oceanembed-backend/
├── docker-compose.yml
├── .env.example
├── core/                              # oceanembed_core — installable shared package,
│   ├── pyproject.toml                 # NOT nested under worker/ — both worker/ and
│   └── oceanembed_core/               # the offline training code install this the
│       ├── __init__.py                # same way (editable install / pinned dep),
│       └── preprocessing/             # so there is exactly one implementation of
│           └── ...                    # regrid, gap-fill, channel order, normalization
├── api/
│   ├── Dockerfile                    # NO torch in requirements
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                   # app instance + lifespan (db pool only)
│   │   ├── config.py                 # pydantic-settings
│   │   ├── deps.py                   # db session, zarr-store resolver dependency
│   │   ├── routers/
│   │   │   ├── field.py              # GET /field
│   │   │   ├── profile.py            # GET /profile
│   │   │   ├── saliency.py           # GET /saliency
│   │   │   ├── sampling.py           # GET /sampling_recommendation
│   │   │   ├── benchmark.py          # GET /benchmark
│   │   │   └── health.py             # GET /health, GET /weeks (gate audit trail)
│   │   ├── schemas/                   # pydantic response models
│   │   ├── services/
│   │   │   ├── zarr_reader.py         # resolves published/latest, re-checks pointer
│   │   │   └── postgis_queries.py     # nearest-argo, run metadata lookups
│   │   └── db/
│   │       ├── models.py
│   │       └── init.sql               # schema + PostGIS extension
│   └── tests/
│       ├── conftest.py                # fixtures incl. multi-week fake zarr layout
│       └── test_*.py
├── worker/
│   ├── Dockerfile                     # has torch, GPU-capable base; `pip install
│   │                                  # -e ../core` at build time — never copies
│   │                                  # preprocessing/ into this directory
│   ├── requirements.txt               # includes the local editable install of core/
│   ├── run_weekly_inference.py        # imports oceanembed_core.preprocessing directly,
│   │                                  # loads bundle, ensemble pass, per-member
│   │                                  # T/S/D26/TCHP/MLD, aggregate, quality gate,
│   │                                  # write immutable week dir, atomic symlink swap
│   └── quality_gate.py                # NaNs/coverage/bounds — AND a mandatory
│                                      # per-channel Z-score check against the mean/std
│                                      # already sitting in scaler.json (see F.10)
└── .github/workflows/ci.yml
```

Two structural notes worth calling out explicitly, since they're the physical form of A.3 and A.5:
- `core/` is a real installable package (`pip install -e ./core` or a pinned path/git dependency), imported by *both* the offline training code and `run_weekly_inference.py`. It is deliberately **not** nested under `worker/` — that placement would have made it trivial for someone to copy-paste it into a separate training repo "just this once," which is exactly how the two implementations quietly diverge and cause train/serve skew. If your training code lives in a different repository or a notebook environment, it installs `core/` the same way — not by copying files in.
- `quality_gate.py` runs the Z-score check by default, not as an optional add-on — see F.10 for why this is cheap enough that there's no good reason to defer it.

---

## Part F — Build order

1. **Skeleton** — `docker-compose up` with `api` (`/health`) and `postgres`. Confirm connectivity.
2. **Storage layout first, before any endpoint** — create the `published/week=YYYY-Www/` + `published/latest` symlink convention with **two** fake weeks of tiny synthetic data. Write and test the resolver (`zarr_reader.py`) in isolation — confirm it (a) resolves the current pointer, (b) picks up a pointer swap without a process restart, before building anything on top of it.
3. **Data layer / worker skeleton** — a minimal `run_weekly_inference.py` that writes a properly-shaped immutable week directory and performs the atomic symlink swap. It's fine for this to use dummy predictions at first — the goal is validating the *publish mechanism*, not the model, at this step.
4. **Postgres schema + seed data** — `model_runs` (including gate status), `argo_profiles` with PostGIS geometry, via `init.sql`.
5. **First endpoint: `/field`** — reads through the resolver from step 2. Validates the full loop, and specifically validates that re-resolution actually works against real (if fake) data.
6. **`/profile`** — nearest grid cell + nearest real ARGO profile.
7. **`/saliency` + `/sampling_recommendation`** — same read pattern, different stored variable.
8. **`/benchmark`** — PostGIS nearest-ARGO query, model vs. ARMOR3D.
9. **`/weeks`** — a small endpoint exposing the gate-status audit trail from Postgres (pass/fail history, which week is currently live) — cheap to build, and directly useful for demonstrating the reliability story to a technical reviewer.
10. **Real quality gate — build both checks together, not integrity-then-maybe-drift.** NaNs/coverage/bounds, *and* a per-channel Z-score check against the training mean/std already sitting in `scaler.json` (`z = (x - μ_train) / σ_train`, flag if `|z|` exceeds a threshold for a meaningful fraction of the channel). This is not a stretch goal: `scaler.json` already exists as a frozen artifact by the time you reach this step, so the check is a handful of lines and negligible compute — there's no real cost reason to defer it. It won't catch every distribution-shift scenario (see the residual caveat in A.5), but it catches univariate outliers — an input channel silently out of the range the model ever saw — which integrity checks alone will happily wave through.
11. **Tests**, including the multi-week pointer-swap test from D.4.
12. **Full containerization + CI.**
13. **Polish** — structured logging, `model_version` + publish date in every response, README.

---

## Part G — Production habits checklist

- [ ] Every endpoint has a typed Pydantic response model
- [ ] DB pool opened once at startup; **Zarr "latest" pointer re-resolved periodically, never cached for process lifetime**
- [ ] No hardcoded paths or connection strings — all through `config.py`/`.env`
- [ ] Every response includes `model_version` + the publish date of the underlying week
- [ ] Zero `import torch` anywhere under `api/`
- [ ] `oceanembed_core` lives at the repo root and is installed (not copied) by both `worker/` and the offline training code — one implementation, not two that started identical
- [ ] `/field` returns a binary buffer (`float32.tobytes()`, `application/octet-stream`), not `.values.tolist()` → JSON; single-point endpoints like `/profile` stay JSON
- [ ] `quality_gate.py` runs the per-channel Z-score check against `scaler.json` by default, alongside NaN/coverage/bounds — not gated behind "if time allows"
- [ ] `docker-compose up` stands up the entire demo, including two fake published weeks, in one command, tested on a second machine
- [ ] Typed errors (404/422) everywhere
- [ ] A test exists that publishes a new week and asserts the API serves it without a restart

---

## Part H — What changed from the earlier draft, and why (keep this for your own records)

| Earlier draft said | Corrected to | Reason |
|---|---|---|
| Open the Zarr store once at API startup | Re-resolve `published/latest` on an interval; cache per resolved week, not forever | The atomic-symlink publish pattern means "current" changes weekly; a permanent handle silently goes stale |
| Data store = "Zarr for grids, Postgres for metadata" | Same, plus: Zarr is **immutable per week**, published via **atomic symlink swap**; Postgres also tracks **gate status**, not just run metadata | Prevents readers from ever observing a partially-written week |
| Model artifacts = "frozen `.pt` files on disk" | A versioned **model registry** bundling weights + `scaler.json` + `channels.json` + `calibration.json` together | Closes the 5-channel-vs-12-channel discrepancy structurally, not just by convention |
| Ensemble uncertainty = raw spread across members | Spread, **calibrated with a variance inflation factor** fit against ARGO matchups | Corrects average underdispersion — explicitly still not a fix for novel-input blind spots (see A.5) |
| (not addressed) | Quality gate builds a mandatory per-channel Z-score check against `scaler.json` alongside the integrity checks, from the same build step | It's a handful of lines against an artifact you already have — no real reason to defer it; still doesn't catch novel multivariate combinations, which stays an honest residual gap |
| `preprocessing/` nested under `worker/` | Pulled out to a root-level installable `core/` package (`oceanembed_core`), installed by both `worker/` and the offline training code | Nesting it under `worker/` made copy-pasting into a separate training repo the path of least resistance — exactly how train/serve skew happens silently |
| `/field` returns `.values.tolist()` → JSON | `/field` returns a raw binary buffer (`float32.tobytes()`); `/profile` and other single-point endpoints stay JSON | A full 15-depth domain grid is ~360k floats — ASCII JSON inflates that past 12 MB and blocks the event loop; binary keeps it under ~1.5 MB |

---

## Part I — What to carry into the INCOIS conversation, not the demo

Unchanged from before, plus one addition:

- The model is weakest at the thermocline and during extreme events — exactly where TCHP/cyclone use cases need it most.
- GLORYS and ARMOR3D likely share correlated biases as related reanalysis products — a favorable comparison partly reflects that, not pure independent skill.
- Ensemble spread, even calibrated, is unlikely to flag genuinely novel inputs the way it flags routine underdispersion.
- Physics-informed loss can smooth away real, physically valid anomalies in favor of "typical" profiles.
- Cloud-gap infilling is currently optional in the plan, but monsoon cloud cover is seasonal-norm over your exact domain and season of interest.
- **New:** the quality gate now includes a mandatory per-channel Z-score check, not just integrity checks — but it catches univariate outliers, not novel *combinations* of otherwise-ordinary-looking values. State that distinction plainly rather than implying the gate catches everything a reviewer might assume it does.

None of this blocks shipping. It's the difference between presenting a demo and presenting a system whose limits you can state precisely when asked — which is the stronger position either way.
