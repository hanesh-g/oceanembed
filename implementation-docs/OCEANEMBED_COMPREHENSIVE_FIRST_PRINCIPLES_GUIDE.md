# OceanEmbed: Architectural, Oceanographic & Codebase Master Guide
### An Exhaustive First-Principles Analysis of the Weekly 3D Subsurface Ocean Forecasting Pipeline

---

## Table of Contents
1. [Executive Summary & The Mission](#1-executive-summary--the-mission)
2. [Physical Oceanography & Marine Science from First Principles](#2-physical-oceanography--marine-science-from-first-principles)
   - 2.1 The Remote Sensing Dilemma: The Surface-Skin Limitation
   - 2.2 Stratification, Vertical Gradients & The Equation of State
   - 2.3 Core Physical & Dynamic Variables ($T, S, \text{MLD}, D_{26}, \text{TCHP}$)
   - 2.4 Tropical Cyclone Rapid Intensification & Acoustic SOFAR Channels
   - 2.5 In-Situ Profiling: The ARGO Float Network & Spatial Sparsity
   - 2.6 The Governing Coupling Hypothesis: Surface Altimetry to Subsurface Baroclinic Modes
3. [Machine Learning, Statistical Ensembling & Physics Constraints](#3-machine-learning-statistical-ensembling--physics-constraints)
   - 3.1 Dual-Head 5-Member Ensemble Architecture
   - 3.2 Physics-Informed Monotonic Stability Loss ($\partial \rho / \partial z \ge 0$)
   - 3.3 Uncertainty Quantification: The Underdispersion Trap & Calibrated Variance Inflation
   - 3.4 The Frozen Artifact Bundle & Model Registry Pattern
4. [Systems Architecture: The Three-Lane Serving Paradigm](#4-systems-architecture-the-three-lane-serving-paradigm)
   - 4.1 Lane Separation & The Zero-PyTorch Serving Axiom
   - 4.2 Partitioned Weekly Storage & The Atomic Symlink Swap
   - 4.3 The "Latest-Pointer Caching" Anti-Pattern & TTL Re-Resolution
   - 4.4 Data Transmission Bottlenecks: Raw Binary Slicing vs. Strided Vectorized GeoJSON
5. [Exhaustive Codebase Anatomy & Lineage](#5-exhaustive-codebase-anatomy--lineage)
   - 5.1 Repository File Tree & Component Roles
   - 5.2 The Shared Core (`core/oceanembed_core/`)
   - 5.3 High-Performance Zarr Resolver & Synthetic Layout (`backend/src/infrastructure/zarr/`)
   - 5.4 Database Models, PostGIS Geometries & Spatial Queries (`backend/src/modules/ocean/db/` & `services/`)
   - 5.5 Fast REST Slicing Routes & Serialization (`backend/src/modules/ocean/routes/`)
   - 5.6 Application Lifespan & Settings (`backend/src/interfaces/main.py` & `infrastructure/config/`)
   - 5.7 The React + MapLibre GL Interactive Dashboard (`frontend/src/`)
   - 5.8 Containerization & Multi-Service Orchestration (`docker-compose.yml`)
6. [Operational Quality Gating & Fault Tolerance](#6-operational-quality-gating--fault-tolerance)
   - 6.1 Dual-Check Verification: Structural Integrity & Univariate Distribution Shift
   - 6.2 Rollback Prevention & Persistent Audit Trails
7. [Trap Fixes Applied, Known Limitations & Technical Reviewer Defense](#7-trap-fixes-applied-known-limitations--technical-reviewer-defense)
   - 7.1 Engineering Trap Fixes Summary Table
   - 7.2 Honest Residual Gaps & INCOIS Technical Defense

---

# 1. Executive Summary & The Mission

**OceanEmbed** is an end-to-end, AI-driven oceanographic intelligence platform developed for the **Smart India Hackathon (SIH)**. Its operational mission is to reconstruct and forecast full **three-dimensional (3D) subsurface ocean state profiles**—specifically Temperature ($T$), Salinity ($S$), Density ($\rho$), and derived thermal metrics—across the **North Indian Ocean (5°N–30°N, 45°E–105°E)** at **0.25° spatial resolution** and across **15 standard vertical depth levels (surface to 1,000 meters)** on a weekly cycle.

### The Fundamental Engineering Problem
Ocean forecasting traditionally relies on computationally crushing **Numerical Ocean General Circulation Models (OGCMs)** like NEMO, MOM, or HYCOM. These models solve the Navier-Stokes equations under hydrostatic and Boussinesq approximations across billions of grid cells, requiring supercomputers, high data latency, and complex 4D-Var data assimilation pipelines.

Conversely, while modern spaceborne satellite constellations monitor the ocean continuously, **they can only measure surface-skin variables**. Satellites cannot penetrate seawater deeper than a few millimeters (infrared/microwave) to centimeters (radar). Meanwhile, in-situ measuring devices (ARGO robotic profiling floats) plunge into the ocean interior but are drastically sparse (~300 floats scattered across millions of square kilometers in the Indian Ocean basin).

### The OceanEmbed Solution
OceanEmbed bridges this observational chasm by formulating 3D subsurface ocean reconstruction as a **physics-informed multi-modal deep learning synthesis problem**:
1. It ingests 2D surface observation fields: Sea Surface Height/Anomaly ($\text{SSH}/\text{SLA}$), Sea Surface Temperature ($\text{SST}$), Sea Surface Salinity ($\text{SSS}$), and Surface Wind Stress ($\vec{\tau}_{10}$).
2. It projects these 2D boundary perturbations into full 3D subsurface baroclinic structures through a 5-member deep neural ensemble.
3. It packages and serves these high-dimensional forecasts through an ultra-low-latency, zero-downtime, read-only API server and an interactive WebGL geospatial dashboard.

---

# 2. Physical Oceanography & Marine Science from First Principles

To understand why the code is structured as it is, one must first grasp the physical laws governing the ocean interior.

```
                      SURFACE BOUNDARY (Air-Sea Interface)
    Satellites Observe: SST, SSS, SLA, Winds
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ z = 0m
  |   MIXED LAYER (Quasi-uniform Temperature & Salinity)               |
  |   Turbulently stirred by winds, waves, and convective cooling       |
  |   Thickness = MLD (~20m to ~80m in Indian Ocean)                   |
  |-------------------------------------------------------------------| z = MLD
  |   THERMOCLINE / PYCNOCLINE (High Vertical Gradient Zone)           |
  |   Temperature plummets: 28°C ---> 12°C                             |
  |   Density spikes: Stable stratification                            |
  |   Depth of 26°C isotherm (D26) lives here                          |
  |-------------------------------------------------------------------| z = 200m
  |   DEEP ABYSS / INTERMEDIATE WATER                                  |
  |   Cold (< 8°C), Dense, Hydrostatically Stable                      |
  |   Acoustic Sound Velocity Channel (SOFAR Axis ~800m - 1000m)       |
  v                                                                   v z = 1000m+
```

### 2.1 The Remote Sensing Dilemma: The Surface-Skin Limitation
Electromagnetic radiation attenuates exponentially in water according to the **Beer-Lambert Law**:
$$I(z) = I_0 e^{-\alpha z}$$
- **Infrared Radiometry (SST)**: The absorption coefficient $\alpha$ for thermal infrared ($\sim 10.5 - 12.5\,\mu\text{m}$) is so high that the observed signal emanates exclusively from the **thermal skin layer** (the top $10 - 20\,\mu\text{m}$).
- **Radar Altimetry (SSH/SLA)**: Emits microwave pulses at $\sim 13.5\,\text{GHz}$ (Ku-band) to measure round-trip time from satellite to the sea surface. It yields the exact sea surface height above the reference ellipsoid down to centimeters, but gives **zero direct vertical information** about the water below.
- **Microwave Radiometry (SSS)**: L-band radiometers ($\sim 1.4\,\text{GHz}$) measure surface dielectric properties, reflecting the top $1 - 2\,\text{cm}$ of seawater salinity.

Thus, satellite remote sensing leaves $99.999\%$ of the ocean volume completely invisible.

### 2.2 Stratification, Vertical Gradients & The Equation of State
Seawater density $\rho$ is not constant; it is governed non-linearly by temperature ($T$), practical salinity ($S$), and hydrostatic pressure ($p$, directly proportional to depth $z$):
$$\rho = \rho(S, T, p)$$
Under international standards (TEOS-10 / EOS-80), seawater density increases as:
- Temperature **decreases** (thermal contraction, down to freezing point).
- Salinity **increases** (addition of dissolved ionic mass).
- Depth/Pressure **increases** (compressibility of water).

The vertical stability of the water column is dictated by the **Brunt-Väisälä Frequency ($N$)**:
$$N^2 = -\frac{g}{\rho_0} \frac{\partial \rho_{\text{pot}}}{\partial z}$$
For an ocean to be hydrostatically stable, $N^2 > 0$, meaning potential density must increase monotonically with depth:
$$\frac{\partial \rho_{\text{pot}}}{\partial z} \le 0 \quad (\text{where } z \text{ is positive upwards})$$
If a model predicts warmer, fresher water beneath cold, saline water without compensating pressure/salinity terms, it introduces an **unphysical density inversion**, creating simulated gravitational overturning that violates real-world fluid dynamics.

### 2.3 Core Physical & Dynamic Variables

| Variable | Symbol | Unit | Oceanographic Meaning |
|---|---|---|---|
| **Temperature Profile** | $T(z)$ | °C | Thermal energy distribution from surface to $1000\,\text{m}$. |
| **Salinity Profile** | $S(z)$ | $\text{PSU}$ (or $\text{g/kg}$) | Haline structure, controlling barrier layers and water mass identification. |
| **Mixed Layer Depth** | $\text{MLD}$ | $\text{m}$ | The depth of the wind-mixed upper layer where temperature drops by $\Delta T = 0.2^\circ\text{C}$ or density increases by $\Delta \sigma_\theta = 0.03\,\text{kg/m}^3$ relative to surface. |
| **Isotherm 26°C Depth** | $D_{26}$ | $\text{m}$ | The physical depth where water temperature crosses $26^\circ\text{C}$. Serves as the lower boundary of cyclone-fueling warm water. |
| **Tropical Cyclone Heat Potential** | $\text{TCHP}$ | $\text{kJ/cm}^2$ | Integrated thermal energy available to fuel cyclones above the $26^\circ\text{C}$ threshold. |

### 2.4 Tropical Cyclone Rapid Intensification & Acoustic SOFAR Channels
#### Why Sea Surface Temperature (SST) Lies to Forecasters
A classic operational forecasting failure occurs when meteorologists predict cyclone intensity based solely on SST. When a cyclone's hurricane-force cyclonic winds blow over the ocean, they generate intense surface divergence through **Ekman pumping**:
$$w_{\text{Ekman}} = \frac{1}{\rho_0 f} \left( \nabla \times \vec{\tau} \right)$$
This divergence forces bottom water to upwell. 
- If the upper warm layer is thin (shallow $D_{26}$, low $\text{TCHP}$), upwelling rapidly brings cold deep water ($18^\circ\text{C} - 22^\circ\text{C}$) to the surface, killing the storm's thermodynamic heat engine.
- If the water column has a deep thermocline (high $D_{26}$, high $\text{TCHP}$), the water upwelled is still above $26^\circ\text{C}$. The ocean continues feeding heat flux into the atmospheric vortex, resulting in **Rapid Intensification (RI)**.

#### The Mathematical Formulation of TCHP
$$\text{TCHP} = \rho_0 c_p \int_0^{D_{26}} \left( T(z) - 26 \right) dz$$
where:
- $\rho_0 \approx 1025\,\text{kg/m}^3$ (reference seawater density),
- $c_p \approx 3993\,\text{J}/(\text{kg}\cdot^\circ\text{C})$ (specific heat capacity of seawater),
- $D_{26}$ is the depth where $T(z) = 26^\circ\text{C}$.

#### Underwater Acoustics: The SOFAR Channel
The speed of sound in seawater $c$ is a function of Temperature, Salinity, and Pressure (Mackenzie Equation):
$$c(T, S, z) \approx 1448.96 + 4.591 T - 5.304 \times 10^{-2} T^2 + 2.374 \times 10^{-4} T^3 + 1.340 (S - 35) + 1.630 \times 10^{-2} z$$
In the upper ocean, $T$ plummets rapidly, causing sound velocity to decrease with depth. Deeper down, temperature stabilizes near $4^\circ\text{C}$, but hydrostatic pressure increases linearly, causing sound velocity to climb. The resulting minimum in the sound velocity profile forms the **SOFAR (Sound Fixing and Ranging) Channel Axis**. Sound waves trapped in this acoustic wave-guide travel thousands of kilometers without boundary reflection loss. Accurate 3D $T(z)$ and $S(z)$ prediction is therefore critical for naval sonar propagation and submarine acoustic horizon modeling.

### 2.5 In-Situ Profiling: The ARGO Float Network & Spatial Sparsity
The global gold standard for subsurface truth is the **ARGO Program**:
- Free-drifting battery-powered robotic floats.
- Operational cycle: Float descends to a parking depth of $1,000\,\text{m}$, drifts passively with deep currents for 9–10 days, descends to $2,000\,\text{m}$, and then ascends to the surface while its CTD (Conductivity-Temperature-Depth) sensor records a continuous vertical profile.
- At the surface, it transmits data via Iridium satellites to data centers (INCOIS, Coriolis) and repeats the cycle.

**The Sparsity Problem**: In the North Indian Ocean, there are only roughly 250 to 350 active ARGO floats at any given time across an area of over 15 million square kilometers. That equates to roughly **one profile per 50,000 square kilometers every 10 days**. They provide sparse "pins" of ground truth, completely inadequate for continuous synoptic tracking of mesoscale eddies (diameter 50–200 km).

### 2.6 The Governing Coupling Hypothesis: Surface Altimetry to Subsurface Baroclinic Modes
Why is it mathematically possible for an AI to predict deep 3D structures from 2D surface data?
The answer lies in **ocean baroclinic dynamics**:
In a stratified, two-layer ocean approximation (warm upper layer of density $\rho_1$ over cold dense deep layer $\rho_2$), sea level anomaly ($\eta' = \text{SLA}$) and thermocline depth anomaly ($h'$) are coupled through reduced gravity:
$$g' = g \frac{\rho_2 - \rho_1}{\rho_2}$$
$$\eta' = -\frac{\rho_2 - \rho_1}{\rho_2} h' = -\frac{g'}{g} h'$$
Because $\frac{g'}{g} \sim \frac{1}{300} - \frac{1}{500}$, a **$10\,\text{cm}$ rise in Sea Level Anomaly corresponds to a $30 - 50\,\text{meter}$ depression (deepening) of the warm thermocline!**
- **Anticyclonic Eddies**: Convergent surface currents $\to$ downwelling $\to$ elevated SLA ($+15\,\text{cm}$) $\to$ deep thermocline $\to$ warm water column.
- **Cyclonic Eddies**: Divergent surface currents $\to$ upwelling $\to$ depressed SLA ($-15\,\text{cm}$) $\to$ shallow thermocline $\to$ cold water column.

Surface signals are the boundary projection of internal vertical normal modes. Deep neural networks learn this non-linear operator from millions of historical points.

---

# 3. Machine Learning, Statistical Ensembling & Physics Constraints

```
                            INPUT: 2D Surface Fields (0.25° Grid)
                  [SST, SSS, SLA, U10, V10, Bathymetry, Coriolis, Climatology]
                                            |
                                            v
         +---------------------------------------------------------------------+
         |                5-MEMBER DEEP ENSEMBLE FORWARD PASS                  |
         |  Member 0       Member 1       Member 2       Member 3       Member 4  |
         +---------------------------------------------------------------------+
            |                 |              |              |              |
            v                 v              v              v              v
     (T, S, Products)  (T, S, Prod)   (T, S, Prod)   (T, S, Prod)   (T, S, Prod)
            \                 \              |              /              /
             +-------------------------------+----------------------------+
                                             |
                                             v
                           ENSEMBLE AGGREGATION & CALIBRATION
                 Mean: y_hat = (1/M) sum(y_m)
                 Raw Spread: s_raw = sqrt( (1/(M-1)) sum(y_m - y_hat)^2 )
                 Calibrated Uncertainty: s_cal = gamma * s_raw (from calibration.json)
                                             |
                                             v
                             PHYSICS & DISTRIBUTION QUALITY GATE
                   - NaN / Land Mask Coverage Check
                   - Physical Plausibility Bounds
                   - Per-channel Z-score drift: |z| = |x - mu_train| / sigma_train
```

### 3.1 Dual-Head 5-Member Ensemble Architecture
Rather than predicting temperature and salinity sequentially, the network architecture uses a shared convolutional/transformer backbone with **dual task-specific prediction heads**:
- **Temperature Head**: Outputs a 3D tensor $\hat{T} \in \mathbb{R}^{15 \times H \times W}$.
- **Salinity Head**: Outputs a 3D tensor $\hat{S} \in \mathbb{R}^{15 \times H \times W}$.

To capture epistemic (model) uncertainty, OceanEmbed uses a **Deep Ensemble of 5 independently trained members** ($m \in \{0, 1, 2, 3, 4\}$). Each member is trained with:
- Different stochastic weight initialization seeds.
- Shuffled temporal batch orderings.
- Perturbed data augmentations.

### 3.2 Physics-Informed Monotonic Stability Loss ($\partial \rho / \partial z \ge 0$)
Standard Mean Squared Error (MSE) loss treats every vertical level independently:
$$\mathcal{L}_{\text{MSE}} = \frac{1}{K} \sum_{k=1}^{15} \left( T(z_k) - T^*(z_k) \right)^2 + \lambda_s \left( S(z_k) - S^*(z_k) \right)^2$$
This loss allows the model to predict static instability (heavy water sitting on top of light water). To prevent this, the loss function includes a **differentiable hydrostatic penalty**:
$$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{MSE}} + \lambda_{\text{physics}} \mathcal{L}_{\text{strat}}$$
where potential density $\sigma_k = \rho(S_k, T_k, z_k) - 1000$ is computed via a polynomial approximation of the equation of state, and the penalty is:
$$\mathcal{L}_{\text{strat}} = \frac{1}{K-1} \sum_{k=1}^{14} \text{ReLU}\left( \sigma_k - \sigma_{k+1} \right)^2$$
If $\sigma_{k+1} \ge \sigma_k$ (density increases with depth), the ReLU is zero and no gradient is applied. If an unphysical inversion occurs ($\sigma_{k+1} < \sigma_k$), the loss penalizes the network heavily.

### 3.3 Uncertainty Quantification: The Underdispersion Trap & Calibrated Variance Inflation
The raw uncertainty is the sample standard deviation across the 5 ensemble members:
$$\sigma_{\text{raw}}(x, y, z) = \sqrt{\frac{1}{M-1} \sum_{m=0}^{M-1} \left( \hat{y}_m(x, y, z) - \bar{y}(x, y, z) \right)^2}$$

#### The Underdispersion Trap
In deep learning ensembles, models share identical inductive biases (architectures, loss formulations, training dataset distributions). Consequently, **deep ensembles are notoriously overconfident and systematically underdispersed**:
$$\mathbb{E}\left[ (\bar{y} - y_{\text{true}})^2 \right] > \sigma_{\text{raw}}^2$$
The empirical error measured against real-world ARGO floats is significantly wider than what the 5 ensemble members' disagreement predicts.

#### The Fix: Calibrated Variance Inflation Factor (VIF)
During offline validation against thousands of co-located ARGO float matchups, OceanEmbed fits an empirical **Variance Inflation Factor ($\gamma$)**:
$$\sigma_{\text{calibrated}}(x, y, z) = \gamma \cdot \sigma_{\text{raw}}(x, y, z)$$
The scalar $\gamma$ (typically between $1.4$ and $2.2$ depending on depth level) is calibrated such that a $2\sigma$ uncertainty envelope ($\bar{y} \pm 2\sigma_{\text{calibrated}}$) empirically captures **$95.4\%$ of observed ARGO profile observations**.

This calibrated scalar $\gamma$ is exported into `calibration.json` and bundled into the model registry.

### 3.4 The Frozen Artifact Bundle & Model Registry Pattern
A common point of failure in machine learning engineering is **train/serve skew caused by loosely coupled artifacts**.
- Example: An engineer assumes the model takes 5 input channels; another doc says 12 channels. The inference worker crashes or, worse, passes features in the wrong channel order (e.g. feeding Salinity into the Temperature channel).

OceanEmbed solves this structurally through the **Frozen Model Bundle**:
Every model version in `model-registry/<version>/` is immutable and bundles 4 tightly coupled artifacts:
```
model-registry/oceanembed-v1.0.0/
├── manifest.json         <-- Metadata, training dates, spatial bounds, target variables
├── members/
│   ├── member_0.pt       <-- PyTorch weight checkpoints (5 ensemble members)
│   ├── member_1.pt
│   ├── member_2.pt
│   ├── member_3.pt
│   └── member_4.pt
├── scaler.json           <-- Per-channel mean and std from training set (used for normalization & quality gate)
├── channels.json         <-- CANONICAL channel names and sequence expected by tensor input [0..C-1]
└── calibration.json      <-- Variance inflation factors (gamma) fit against ARGO matchups
```
The inference worker **never assumes channel ordering or normalization constants**—it programmatically reads `channels.json` and `scaler.json` directly from the bundle.

---

# 4. Systems Architecture: The Three-Lane Serving Paradigm

```
========================================================================================
                         THE THREE-LANE ARCHITECTURE DIAGRAM
========================================================================================

 [ LANE 1: OFFLINE TRAINING ]
 (Isolated GPU Server, Runs Rarely)
   Historical CMEMS / PO.DAAC Satellite Cubes (2020-2024)
              |
              v
   `oceanembed_core` Preprocessing Package (Regrid 0.25°, gap-fill, normalize)
              |
              v
   Train 5-Member Ensemble (PyTorch + Physics Loss)
              |
              v
   ARGO Validation & Uncertainty Calibration (fit gamma)
              |
              v
   Export Frozen Bundle: {member_*.pt, scaler.json, channels.json, calibration.json}
              |
              +----------------------------+
                                           |
                                           v
                        [ FROZEN MODEL REGISTRY ]
                        model-registry/oceanembed-v1.0.0/
                                           |
                                           +----------------------------+
                                                                        |
 [ LANE 2: INFERENCE WORKER ]                                           |
 (Batch Cron Job / Weekly / GPU / PyTorch)                              |
   Weekly Satellite Ingest (SST, SSS, SLA, Winds)                       |
              |                                                         |
              v                                                         |
   `oceanembed_core` (Byte-for-byte identical preprocessing)            |
              |                                                         |
              v                                                         |
   Load Frozen Model Bundle <-------------------------------------------+
              |
              v
   5-Member Forward Pass ---> Derive T, S, D26, TCHP, MLD per member
              |
              v
   Aggregate Mean + Spread with Calibrated Variance Inflation (VIF)
              |
              v
   QUALITY GATE:
     - Check NaNs, Coverage, Bounds
     - Compute per-channel Z-score vs scaler.json
              |
       +------+------+
       |             |
     [PASS]        [FAIL] ---> Alert Team! Old symlink stays live (Zero Downtime)
       |
       v
   Write Immutable Zarr Store: `data/published/week=YYYY-Www/`
       |
       v
   ATOMIC SYMLINK SWAP: `published/latest` ---> `week=YYYY-Www`
       |
       v
   Insert ModelRun Record into PostgreSQL (gate_status='pass', log, timestamp)
       |
       +------------------------------------+
                                            |
                                            v
 [ LANE 3: API SERVER & WEB DASHBOARD ]
 (FastAPI / Read-Only / ZERO PyTorch / Pure Reader)
   Storage Mounts:
     - `data/published` (MOUNTED READ-ONLY :ro)
     - `PostgreSQL / PostGIS` (ModelRun audit, ARGO float profiles)
              |
              v
   `ZarrStoreResolver`: Periodic TTL Symlink Re-Resolution (os.readlink)
              |
              +-----------------------------+-----------------------------+
              |                             |                             |
              v                             v                             v
        GET /v1/ocean/field          GET /v1/ocean/field_json      GET /v1/ocean/profile
      Raw binary float32 buffer      Vector-strided JSON           Vertical 15-depth profile
      (application/octet-stream)     (MapLibre WebGL, ~120KB)      + PostGIS nearest ARGO float
              |                             |                             |
              +-----------------------------+-----------------------------+
                                            |
                                            v
                                  [ REACT + MAPLIBRE GL ]
                                 Interactive Web Dashboard
========================================================================================
```

### 4.1 Lane Separation & The Zero-PyTorch Serving Axiom
A core architectural mandate of OceanEmbed is: **The API server must NEVER import PyTorch (`import torch`).**

#### The Rationale from First Principles
1. **Memory Bloat**: PyTorch with CUDA bindings consumes $1.5\,\text{GB}$ to $3.0\,\text{GB}$ of resident memory just by being imported into the Python runtime. Without PyTorch, the FastAPI backend container image is lightweight ($\sim 180\,\text{MB}$ vs. $15\,\text{GB}$) and runs in under $120\,\text{MB}$ of RAM.
2. **CUDA Context Contention**: If a web server shares a process or GPU with deep learning runtimes, FastAPI worker forks (`uvicorn --workers N`) collide over the CUDA initialization context, leading to random deadlocks or CUDA initialization errors (`CUDA error: initialization error`).
3. **Serving vs. Inference Cadence**: Inference happens **once a week** (batch process). API serving happens **thousands of times a minute** (real-time read process). Forcing real-time requests to pass through inference models is architectural anti-pattern; serving must be pure read-only slicing from pre-computed, verified storage.

### 4.2 Partitioned Weekly Storage & The Atomic Symlink Swap
OceanEmbed stores gridded data in **Zarr format**, partitioned into immutable week directories:
```
data/published/
├── week=2025-W01/
│   ├── temp/
│   ├── sal/
│   ├── d26/
│   ├── tchp/
│   ├── mld/
│   └── .zattrs
├── week=2025-W02/
│   └── ...
└── latest -> week=2025-W01   <-- Symlink pointer
```
- Each weekly directory is **completely immutable** once written. It is never modified or appended to in-place.
- When the inference worker completes week `2025-W02` and passes the Quality Gate, it performs an **Atomic Symlink Swap**:
  ```python
  # POSIX atomic replacement
  tmp_symlink.symlink_to("week=2025-W02")
  os.replace(tmp_symlink, "data/published/latest")
  ```
- **Guarantees**:
  - Readers never observe a partially written or corrupted week.
  - If the worker crashes mid-write, the existing `latest` symlink continues pointing safely to the previous week.
  - Zero downtime during updates.

### 4.3 The "Latest-Pointer Caching" Anti-Pattern & TTL Re-Resolution
A classic trap in high-performance Python servers is caching file handles at startup:
```python
# THE FATAL ANTI-PATTERN:
class BadResolver:
    def __init__(self):
        # Resolved ONCE at container boot
        self.store = xr.open_zarr("data/published/latest")
```
If the API does this, it resolves `latest` to `week=2025-W01` at boot time. When the inference worker runs a week later and repoints `latest` to `week=2025-W02`, the running API process **silently continues serving `week=2025-W01` forever**. No error is thrown, no log is emitted; the dashboard simply freezes in the past.

#### The OceanEmbed Solution: Time-To-Live (TTL) Pointer Resolution
In [`backend/src/infrastructure/zarr/resolver.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/resolver.py), the `ZarrStoreResolver` employs a decoupled lookup:
1. `os.path.realpath("published/latest")` is executed, but only when the TTL has elapsed (default: 30 seconds).
2. Slicing requests reuse the in-memory opened `xr.Dataset` keyed by absolute canonical path (`dict[str, xr.Dataset]`).
3. When the symlink changes, the resolver detects the path divergence on the next TTL tick, opens the new week's dataset, logs the swap, and serves the new week without a process restart.

### 4.4 Data Transmission Bottlenecks: Raw Binary Slicing vs. Strided Vectorized GeoJSON
Consider serving the full 3D domain slice at 0.25° resolution across the North Indian Ocean:
- Domain: $5^\circ\text{N} - 30^\circ\text{N}$ ($100$ latitude points), $45^\circ\text{E} - 105^\circ\text{E}$ ($240$ longitude points).
- Grid size: $100 \times 240 = 24,000$ points per depth.
- Across 15 depth levels: $24,000 \times 15 = 360,000$ floating-point values.

#### The ASCII JSON Bottleneck
Serializing 360,000 coordinate-value dictionaries to JSON:
```json
[{"lat": 5.0, "lon": 45.0, "depth": 0, "val": 28.452}, ...]
```
- Inflates memory to **over 12 megabytes** of ASCII text.
- Serializing millions of characters locks the Python asyncio event loop for hundreds of milliseconds.
- The user's web browser tab spikes in RAM and stutters while parsing JSON strings.

#### OceanEmbed's Two-Tier Transmission Strategy
1. **Binary Endpoint (`/v1/ocean/field`)**:
   - Casts array to IEEE 754 32-bit float (`float32`).
   - Calls `.tobytes()` directly into memory.
   - Transmits with header `Content-Type: application/octet-stream`.
   - **Size: exactly $360,000 \times 4\,\text{bytes} \approx 1.44\,\text{MB}$ (an $88\%$ reduction!)**.
   - Custom HTTP headers transmit dimensional reconstruction metadata:
     ```http
     X-Shape: 100,240,15
     X-Variable: temp
     X-Model-Version: oceanembed-v1.0.0
     X-Week: 2025-W01
     ```
   - The frontend JavaScript instantiates a `new Float32Array(arrayBuffer)` and feeds it directly into WebGL/GPU memory in zero copy!

2. **Vectorized Strided JSON Endpoint (`/v1/ocean/field_json`)**:
   - For web map overlay libraries (like MapLibre/GeoJSON) that require JSON, the server provides a spatial stride factor (`stride=4` by default).
   - Stride 4 samples every 4th grid point ($\sim 1.0^\circ$ resolution), dropping cell count from $24,000$ down to $\sim 1,500$ points ($< 120\,\text{KB}$).
   - **Vectorized Generation**: Instead of nested Python loops:
     ```python
     # Vectorized meshgrid execution in NumPy
     lats, lons = np.meshgrid(da_sub.coords["lat"].values, da_sub.coords["lon"].values, indexing="ij")
     return [
         {"lat": float(la), "lon": float(lo), "value": float(v), "uncertainty": float(u)}
         for la, lo, v, u in zip(lats.flat, lons.flat, values.flat, uncertainties.flat)
     ]
     ```
     This executes in milliseconds, preserving 60 FPS UI interactivity.

---

# 5. Exhaustive Codebase Anatomy & Lineage

### 5.1 Repository File Tree & Component Roles
```
oceanembed/
├── core/                               <-- Shared Preprocessing Package (Zero skew)
│   ├── pyproject.toml
│   └── oceanembed_core/
│       ├── __init__.py
│       └── preprocessing/
│           ├── channels.py             <-- Canonical channel orders & domain constants
│           ├── regrid.py               <-- Target 0.25° coordinate mesh & interpolation
│           ├── gapfill.py              <-- Missing satellite data & cloud gap filling
│           └── normalize.py            <-- Scaler normalization & Z-score drift computation
│
├── backend/                            <-- FastAPI Server (Pure Reader, Zero PyTorch)
│   ├── src/
│   │   ├── infrastructure/
│   │   │   ├── config/settings.py      <-- OceanEmbedSettings (pydantic-settings)
│   │   │   ├── dependencies.py         <-- ZarrResolverDep & AsyncSessionDep injection
│   │   │   └── zarr/
│   │   │       ├── resolver.py         <-- ZarrStoreResolver (TTL symlink re-resolution)
│   │   │       └── fake_data.py        <-- Synthetic multi-week Zarr generator
│   │   ├── modules/ocean/
│   │   │   ├── db/
│   │   │   │   ├── models.py           <-- ModelRun & ArgoProfile (GeoAlchemy2)
│   │   │   │   └── init.sql            <-- PostGIS schema, extensions & GiST index
│   │   │   ├── schemas/                <-- Pydantic response models (FieldPoint, Profile)
│   │   │   ├── services/
│   │   │   │   └── postgis_queries.py  <-- ST_Point(lon, lat, 4326) KNN nearest neighbor
│   │   │   └── routes/
│   │   │       ├── field.py            <-- /field (binary) & /field_json (strided)
│   │   │       ├── profile.py          <-- /profile (15-depth vertical + ARGO matchup)
│   │   │       ├── health.py           <-- /health & /weeks (Model run audit trail)
│   │   │       └── argo.py             <-- /argo_floats (Float locations for map overlay)
│   │   └── interfaces/
│   │       ├── main.py                 <-- Lifespan resolver lifecycle & CORS setup
│   │       └── api/v1/__init__.py      <-- Router aggregation
│   └── tests/unit/ocean/
│       └── test_zarr_resolver.py       <-- Unit tests including pointer swap validation
│
├── frontend/                           <-- React 18 + Vite + MapLibre GL Dashboard
│   ├── src/
│   │   ├── api/
│   │   │   ├── types.ts                <-- Domain types (OceanEmbedApi, Profile, RunStatus)
│   │   │   ├── liveOceanApi.ts         <-- Real HTTP fetch client & field mapping
│   │   │   ├── mockOceanApi.ts         <-- Standalone offline mock client
│   │   │   └── index.ts                <-- Environment-based toggle (VITE_USE_MOCK)
│   │   ├── App.tsx                     <-- Layout state, DepthSlider, Profile modals
│   │   └── map/OceanMap.tsx            <-- MapLibre GL raster/vector rendering
│   └── vite.config.ts                  <-- Development reverse-proxy to backend:8000
│
├── model-registry/                     <-- Frozen Model Bundles
│   └── oceanembed-v1.0.0/
│       └── manifest.json               <-- Artifact manifest, domain boundaries, metadata
│
├── data/published/                     <-- Partitioned Zarr directory store
├── docker-compose.yml                  <-- Orchestration (PostGIS db + API + Frontend)
└── README.md                           <-- Operational user guide
```

---

### 5.2 The Shared Core (`core/oceanembed_core/`)
Located at the root of the repository, `oceanembed_core` is a standalone, installable Python package (`pip install -e ./core`). It is imported by **both the offline training pipeline and the weekly inference worker**. This structural choice prevents **train/serve skew**: if preprocessing lives in two separate scripts, minor floating-point or indexing divergences silently degrade inference accuracy over time.

#### 1. [`channels.py`](file:///d:/Projects/oceanembed-sih/oceanembed/core/oceanembed_core/preprocessing/channels.py)
- **Domain Constants**: Defines the North Indian Ocean bounding box:
  $$\text{LAT} \in [5.0^\circ\text{N}, 30.0^\circ\text{N}], \quad \text{LON} \in [45.0^\circ\text{E}, 105.0^\circ\text{E}], \quad \Delta = 0.25^\circ$$
- **Standard Depth Levels**: Defines the 15 standard reference vertical levels (meters) matching the GLORYS reanalysis target field:
  $$[0.49, 1.54, 2.65, 3.82, 5.08, 6.44, 7.93, 9.57, 11.41, 13.47, 15.81, 18.50, 21.60, 25.21, 29.44, \dots, 1000.0]$$
- **Dynamic Channel Loading**: `load_channels(channels_json_path)` reads the canonical input channel sequence from `channels.json`. Code never hardcodes tensor indices like `x[:, 0, :, :]`; it resolves channels by name.

#### 2. [`regrid.py`](file:///d:/Projects/oceanembed-sih/oceanembed/core/oceanembed_core/preprocessing/regrid.py)
- **Grid Mesh Construction**: `target_grid()` builds the exact 1D NumPy coordinates for latitude and longitude.
- **Interpolation**: `regrid_to_standard(ds)` projects arbitrary satellite swath observations or CMEMS grids onto the uniform $0.25^\circ$ grid via conservative/nearest interpolation.

#### 3. [`gapfill.py`](file:///d:/Projects/oceanembed-sih/oceanembed/core/oceanembed_core/preprocessing/gapfill.py)
- **Cloud Mask Handling**: Satellite infrared radiometry (SST) cannot penetrate clouds. During the summer Southwest Monsoon, the Arabian Sea and Bay of Bengal experience near-continuous cloud cover for weeks.
- **Functionality**:
  - `nan_fraction(ds)`: Computes the missing value ratio per variable.
  - `fill_gaps(ds, method="nearest")`: Implements spatial interpolation (with forward/backward directional fills) to ensure the neural network receives continuous tensors without NaN propagation.

#### 4. [`normalize.py`](file:///d:/Projects/oceanembed-sih/oceanembed/core/oceanembed_core/preprocessing/normalize.py)
- **Standardization**: Neural networks require zero-mean, unit-variance input tensors:
  $$z = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}}$$
- `load_scaler(path)`: Loads training set statistics from `scaler.json`.
- `compute_zscore(ds, scaler)`: Calculates absolute Z-scores for every cell:
  $$|z_{c, i, j}| = \frac{|x_{c, i, j} - \mu_c|}{\sigma_c}$$
  This is the primary mathematical instrument used by the Quality Gate to detect out-of-distribution input anomalies.

---

### 5.3 High-Performance Zarr Resolver & Synthetic Layout (`backend/src/infrastructure/zarr/`)

#### 1. [`resolver.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/resolver.py)
The `ZarrStoreResolver` is the central heart of the data layer. It resolves requests for weekly data without process restarts.

- **Class Definition & State**:
  ```python
  class ZarrStoreResolver:
      def __init__(self, root: str, recheck_seconds: int = 30) -> None:
          self._root = Path(root)
          self._recheck_seconds = recheck_seconds
          self._store_cache: dict[str, xr.Dataset] = {}
          self._latest_resolved: str | None = None
          self._last_check_time: float = 0.0
  ```
- **Symlink Resolution Algorithm**:
  When `get_store(week=None)` is requested:
  1. Check if `now - self._last_check_time >= self._recheck_seconds`.
  2. If expired, execute `os.path.realpath(self._root / "latest")`.
  3. If the resolved path has changed (e.g. from `week=2025-W01` to `week=2025-W02`), log the swap and update `self._latest_resolved`.
  4. Fetch the opened dataset from `self._store_cache[resolved_path]`. If not present, open it via `xr.open_zarr(resolved_path)`.
- **Explicit Week Bypass**:
  If a user requests `get_store(week="2025-W01")`, the resolver bypasses the symlink check completely and opens `self._root / "week=2025-W01"`.

#### 2. [`fake_data.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/zarr/fake_data.py)
Enables immediate full-stack development, integration testing, and CI verification without requiring access to a 500GB production satellite archive.
- `create_fake_published_layout(root)`: Generates two realistic weekly Zarr stores (`week=2025-W01` and `week=2025-W02`) with physically bounded values ($T \in [10, 32]^\circ\text{C}$, $S \in [34, 37]\,\text{PSU}$, $\text{TCHP} \in [0, 120]\,\text{kJ/cm}^2$, $\text{D26} \in [50, 150]\,\text{m}$).
- `_safe_symlink(link, target)`: Implements **cross-platform symlink creation**:
  - On POSIX: Uses atomic temporary symlink creation and `os.replace` rename.
  - On Windows: Safely unlinks and recreates the symlink (handling Windows file system permission semantics).
- `swap_latest(root, week_label)`: Programmatically repoints the `latest` pointer to simulate a live weekly publish event.

---

### 5.4 Database Models, PostGIS Geometries & Spatial Queries

OceanEmbed pairs gridded Zarr storage with **PostgreSQL + PostGIS** for relational metadata and spatial indexing.

#### 1. [`models.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/db/models.py) & [`init.sql`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/db/init.sql)
- **`ModelRun` Table**:
  Tracks every execution of the inference worker.
  - `week_label`: ISO week string (e.g. `2025-W01`).
  - `gate_status`: `pass` or `fail`.
  - `gate_log`: `JSONB` column recording per-channel NaN fractions, Z-scores, and error diagnostics.
  - `published_at`: UTC timestamp of symlink swap (null if run failed the gate).
- **`ArgoProfile` Table**:
  Stores in-situ float vertical observations.
  - `geom`: Defined strictly as `Geometry(geometry_type='POINT', srid=4326)`.
  - `depth_levels`, `temp_values`, `sal_values`: Stored as `JSONB` arrays representing the vertical profile.
  - **GiST Spatial Index**:
    ```sql
    CREATE INDEX IF NOT EXISTS argo_geom_gist_idx ON argo_profiles USING GIST (geom);
    ```

#### 2. [`postgis_queries.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/services/postgis_queries.py)
Encapsulates spatial SQL logic.

- **The Coordinate Order Convention**:
  PostGIS strictly enforces `(x, y) = (longitude, latitude)`.
  A pervasive bug in GIS systems is passing `ST_Point(lat, lon)`. In PostGIS, this swaps coordinates, placing points in the wrong hemisphere!
  OceanEmbed enforces:
  ```sql
  ST_Point(:lon, :lat, 4326)
  ```
- **K-Nearest Neighbors (KNN) Spatial Operator (`<->`)**:
  To locate the nearest ARGO float profile to a user click on the dashboard:
  ```sql
  SELECT uuid, platform_id, profile_date, lat, lon, depth_levels, temp_values, sal_values,
         ST_Distance(geom, ST_Point(:lon, :lat, 4326)) AS dist_deg
  FROM argo_profiles
  WHERE profile_date <= :before_date
  ORDER BY geom <-> ST_Point(:lon, :lat, 4326)
  LIMIT 1;
  ```
  The `<->` operator calculates bounding-box 2D distance directly over the **GiST index**, finding the nearest float in sub-millisecond query time without performing a full table scan.

---

### 5.5 Fast REST Slicing Routes & Serialization

#### 1. [`field.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/field.py)
- **Binary Slicing (`GET /v1/ocean/field`)**:
  Extracts 2D slices or full 3D volumes:
  ```python
  da = store[variable].sel(depth=depth, method="nearest")
  buf = da.values.astype("float32").tobytes()
  return Response(
      content=buf,
      media_type="application/octet-stream",
      headers={"X-Shape": f"{da.shape[0]},{da.shape[1]}", "X-Variable": variable}
  )
  ```
- **Strided JSON (`GET /v1/ocean/field_json`)**:
  Slices along lat/lon using integer strides (`slice(None, None, stride)`), pairs values with their corresponding ensemble spread (`temp_spread`), and returns a lightweight list of points for map rendering.

#### 2. [`profile.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/profile.py)
Extracts a vertical water column at a specific coordinate $(x, y)$:
1. Queries the Zarr dataset at the 15 standard depth levels via nearest-neighbor spatial interpolation.
2. Extracts matching derived surface parameters ($\text{TCHP}, D_{26}$).
3. Concurrently calls `get_nearest_argo_profile(session, lat, lon)` in PostGIS.
4. Returns the combined payload: model prediction, calibrated uncertainty envelope, and empirical ARGO profile for benchmark comparison.

#### 3. [`health.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/health.py) & [`argo.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/modules/ocean/routes/argo.py)
- `/v1/ocean/health`: Returns current live week label, model version, and gate status for UI header telemetry.
- `/v1/ocean/weeks`: Returns the 52-week gate audit trail.
- `/v1/ocean/argo_floats`: Returns the latest geographic coordinates of all active ARGO floats to render floating marker beacons on the map.

---

### 5.6 Application Lifespan & Settings

#### 1. [`settings.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/infrastructure/config/settings.py)
Built on `pydantic-settings`. Configures environment variables without hardcoded paths:
- `PUBLISHED_ZARR_ROOT`: Location of gridded data (`/data/published`).
- `ZARR_POINTER_RECHECK_SECONDS`: TTL interval (default `30`).
- `MODEL_REGISTRY_PATH`: Model directory (`/model-registry`).
- `QUALITY_GATE_ZSCORE_THRESHOLD`: Threshold for anomaly detection (default `4.0`).

#### 2. [`main.py`](file:///d:/Projects/oceanembed-sih/oceanembed/backend/src/interfaces/main.py)
Configures the ASGI lifecycle:
- **Lifespan Context Manager**: Instantiates `app.state.zarr_resolver` at boot and gracefully invalidates caches on shutdown.
- **CORS Middleware**: Explicitly exposes custom binary header metadata:
  ```python
  expose_headers=["X-Shape", "X-Variable", "X-Model-Version", "X-Week"]
  ```

---

### 5.7 The React + MapLibre GL Interactive Dashboard (`frontend/src/`)

The frontend is a single-page application built with **React 18, Vite, TypeScript, and MapLibre GL JS**.

```
+---------------------------------------------------------------------------------------+
|  OCEANEMBED DASHBOARD  | Week: 2025-W01 | Model: v1.0.0 | Status: [PUBLISHED (PASS)]  |
+---------------------------------------------------------------------------------------+
| [Field Selector]       |                                          | [Depth Slider]    |
| (o) Temperature        |       MAPLIBRE GL VECTOR MAP CANVAS      |   0m (Surface)    |
| ( ) Salinity           |                                          |  10m              |
| ( ) Uncertainty (Spread|   - Ocean Surface Color Ramp (Turbo)     |  50m              |
| ( ) TCHP (Cyclones)    |   - Dynamic Eddy Contours                | [100m] <--- Active|
| ( ) D26 (Thermocline)  |   - ARGO Float Markers (Yellow Dots)     |  200m             |
| ( ) Mixed Layer Depth  |   - Click Pin: (12.5°N, 68.2°E)          |  500m             |
+------------------------+                                          | 1000m (Abyss)     |
| [VERTICAL PROFILE MODAL: Lat 12.5°N, Lon 68.2°E]                  +-------------------+
| Depth (m)                                                                             |
|    0 |----* (Model)                                                                   |
|   50 |====[  Uncertainty Envelope  ]====*                                            |
|  100 |======[                      ]======* (ARGO Observation Dot)                    |
|  200 |--------*                                                                       |
|  500 |----------*                                                                     |
| 1000 |------------*                                                                   |
| TCHP: 78.4 kJ/cm²  |  D26: 84.2 m  |  Nearest ARGO: 42 km (WMO 2902734)              |
+---------------------------------------------------------------------------------------+
```

#### 1. [`types.ts`](file:///d:/Projects/oceanembed-sih/oceanembed/frontend/src/api/types.ts) & Clean Architectural Contracts
Defines the `OceanEmbedApi` interface:
```typescript
export interface OceanEmbedApi {
  getStatus(): Promise<RunStatus>;
  getField(field: FieldId, depth: number): Promise<FieldPoint[]>;
  getProfile(location: Coordinate): Promise<Profile>;
  getArgoFloats(): Promise<ArgoFloat[]>;
}
```

#### 2. Dual Implementations: Live vs. Mock API
- [`liveOceanApi.ts`](file:///d:/Projects/oceanembed-sih/oceanembed/frontend/src/api/liveOceanApi.ts): Fetches data from `/api/v1/ocean/*` and translates field naming discrepancies:
  - Frontend `temperature` $\to$ Backend `temp`.
  - Frontend `uncertainty` $\to$ Backend `temp_spread`.
- [`mockOceanApi.ts`](file:///d:/Projects/oceanembed-sih/oceanembed/frontend/src/api/mockOceanApi.ts): Generates mathematical synthetic wave fields in pure client-side JavaScript.
- [`index.ts`](file:///d:/Projects/oceanembed-sih/oceanembed/frontend/src/api/index.ts): Toggles between live and mock implementations via `VITE_USE_MOCK=true`. This allows UI/UX engineers to work completely decoupled from backend databases.

#### 3. MapLibre GL Integration ([`OceanMap.tsx`](file:///d:/Projects/oceanembed-sih/oceanembed/frontend/src/map/OceanMap.tsx))
- Visualizes 2D scalar fields using WebGL circle layers with dynamic color ramps (Turbo, Viridis).
- Plots active ARGO floats as interactive vector marker pins.
- Listens to user map clicks, captures coordinates, and triggers the vertical profile drawer.

---

### 5.8 Containerization & Multi-Service Orchestration (`docker-compose.yml`)

The entire production stack is orchestrated via Docker Compose:
- **`db`**: Image `postgis/postgis:16-3.4`. Automatically mounts `init.sql` into `/docker-entrypoint-initdb.d/` on first startup. Includes automated healthchecks (`pg_isready`).
- **`api`**: Builds the lightweight FastAPI backend.
  - **Security Boundary**: Mounts `./data/published:/data/published:ro` in **READ-ONLY mode**. The API server is physically prevented by the Linux container kernel from writing to or altering the published data archive.
  - Mounts `./model-registry:/model-registry:ro` in read-only mode.
- **`frontend`**: Multi-stage build (Node.js builds static SPA assets, served via an optimized Nginx container on port 80).

---

# 6. Operational Quality Gating & Fault Tolerance

```
                           WEEKLY INFERENCE RUN
                                    |
                                    v
                    RAW ENSEMBLE OUTPUT TENSORS (T, S)
                                    |
                                    v
         +-----------------------------------------------------+
         |            THE DUAL-CHECK QUALITY GATE              |
         +-----------------------------------------------------+
         | 1. DATA INTEGRITY CHECK                             |
         |    - NaN fraction per variable <= 0.05              |
         |    - Land mask consistency                          |
         |    - Hard physical bounds:                          |
         |        -2.0°C <= Temp <= 36.0°C                     |
         |        10.0 PSU <= Sal <= 42.0 PSU                  |
         |                                                     |
         | 2. DISTRIBUTION DRIFT CHECK (Z-Score)               |
         |    - Compute |z| = |x - mu_train| / sigma_train     |
         |    - Fraction of cells with |z| > 4.0 must be < 1%  |
         +-----------------------------------------------------+
                                    |
                                    v
                               Is gate OK?
                               /         \
                             YES          NO
                             /              \
                            v                v
                 [ PUBLISH PIPELINE ]   [ ROLLBACK & ALERT ]
                 - Write Zarr Store     - Symlink remains untouched
                 - Atomic symlink swap  - Last week remains live
                 - PostGIS: gate=pass   - PostGIS: gate=fail + log
                 - Zero user disruption - Emit operational alert
```

### 6.1 Dual-Check Verification
Before any weekly inference is published to the public dashboard, it must pass through two rigorous mathematical filters:

1. **Structural Data Integrity Check**:
   - **NaN Ratio**: Missing values must not exceed $5\%$ of ocean cells (accounting for expected satellite swath edges).
   - **Physical Bound Check**: Seawater cannot freeze above $-2.0^\circ\text{C}$ or boil in the open ocean ($> 36.0^\circ\text{C}$). Extreme salinity anomalies ($< 10\,\text{PSU}$ or $> 42\,\text{PSU}$) trigger immediate failures.

2. **Univariate Distribution Drift Check**:
   - An input field might have zero NaNs and stay within physical bounds, yet represent an extreme data anomaly (e.g. sensor calibration drift on a satellite).
   - The quality gate loads $\mu_c, \sigma_c$ from `scaler.json` and evaluates the normalized Z-score across the grid:
     $$|z_{c, i, j}| = \frac{|x_{c, i, j} - \mu_c|}{\sigma_c}$$
   - If the fraction of cells exceeding $|z| > 4.0$ (four standard deviations from the historical training mean) exceeds $1\%$, the gate triggers a **distribution drift alert**.

### 6.2 Rollback Prevention & Persistent Audit Trails
- If the quality gate fails, the pipeline aborts **before touching the symlink**.
- The existing `published/latest` pointer remains untouched. Users accessing the dashboard continue viewing the previous week's verified forecast without error or downtime.
- A failure row is written to PostgreSQL's `model_runs` table with `gate_status='fail'`, and the detailed diagnostic breakdown is stored in `gate_log` JSONB for ML engineers to inspect.

---

# 7. Trap Fixes Applied, Known Limitations & Technical Reviewer Defense

### 7.1 Engineering Trap Fixes Summary Table

| Identified Trap / Bottleneck | Impact If Unfixed | First-Principles Solution Implemented |
|---|---|---|
| **Caching `latest` Forever** | API serves old data indefinitely after a weekly publish. Dashboard freezes in time without error. | Periodic TTL re-resolution (`os.readlink`) in `ZarrStoreResolver`. Cache keyed on resolved canonical path. |
| **JSON Serialization of 3D Grid** | $360\text{k}$ floats inflate to $> 12\,\text{MB}$ JSON. Python event loop blocks, browser crashes. | Dual-mode serving: `/field` sends raw binary `float32.tobytes()` ($1.4\,\text{MB}$); `/field_json` uses strided NumPy meshgrid. |
| **SRID Omission in GeoAlchemy2** | Spatial nearest-neighbor `<->` operator performs full table sequential scan; spherical distortion near antimeridian. | Column typed explicitly as `Geometry(POINT, srid=4326)` + GiST index. Coordinates strictly ordered `ST_Point(lon, lat, 4326)`. |
| **Atomic Symlink on Windows** | `os.rename` throws `FileExistsError` on Windows native hosts during local development. | `_safe_symlink()` branches on OS: POSIX uses atomic `rename`; Windows uses safe unlink/recreate fallback. |
| **Train/Serve Preprocessing Divergence** | Minor code variations between training and worker cause silent long-term model degradation. | Preprocessing extracted into standalone root package `oceanembed_core`, installed identically in both environments. |
| **Channel Sequence Ambiguity** | Team confusion over 5 vs 12 input channels results in mismatched tensors or wrong channel assignments. | Canonical ordering frozen into `channels.json` inside model registry. Model is self-describing code-as-data. |
| **Ensemble Underdispersion** | Raw ensemble spread is overconfident and underestimates actual prediction error. | Variance Inflation Factor ($\gamma$) fit against empirical ARGO float matchups, bundled in `calibration.json`. |

---

### 7.2 Honest Residual Gaps & INCOIS Technical Defense
When presenting OceanEmbed to technical reviewers, oceanographers, or operational agencies (such as **INCOIS - Indian National Centre for Ocean Information Services**), defending the system requires intellectual honesty regarding physical limitations:

#### 1. Univariate Z-Score vs. Joint Multivariate Outliers
- **The Reality**: The per-channel Z-score check catches univariate outliers (e.g. an SST reading of $38^\circ\text{C}$). However, it **cannot detect novel multivariate combinations** where each variable is individually normal, but their joint occurrence is physically anomalous (e.g., normal SST + normal SSS, but an unprecedented wind stress pattern).
- **The Defense**: Acknowledge this boundary. Univariate gating is the mandatory baseline; multivariate autoencoder anomaly detection or Mahalanobis distance checks represent the next evolutionary phase.

#### 2. Calibrated Variance Inflation vs. Out-of-Distribution Blind Spots
- **The Reality**: Multiplying raw spread by $\gamma$ corrects for average historical underdispersion across seen data distributions. It **does not make ensemble members disagree more on genuinely novel physical inputs** that none of the models were trained to understand (e.g., an unprecedented Category 5 supercyclone).
- **The Defense**: Clarify that calibrated variance inflation represents calibrated aleatoric and expected epistemic uncertainty, not an absolute guarantee against out-of-distribution blind spots.

#### 3. Reanalysis Correlated Bias (GLORYS vs. ARMOR3D)
- **The Reality**: Benchmarking OceanEmbed against ARMOR3D or GLORYS reanalysis shows favorable agreement partly because these numerical products assimilate similar underlying satellite datasets and share related physical parameterization biases.
- **The Defense**: Point to in-situ ARGO float matchups as the only true independent, un-assimilated baseline of truth.

#### 4. Cloud Cover During Monsoon Seasons
- **The Reality**: During the Southwest Monsoon, persistent cloud cover degrades infrared SST satellite feeds for weeks at a time.
- **The Defense**: OceanEmbed combines microwave radiometry (which penetrates clouds at coarser resolution) with spatial gap-filling and reliance on altimetry (SLA), which is unaffected by cloud cover.

---

### Summary
OceanEmbed is not merely a collection of scripts; it is a **hardened, physics-aware, zero-downtime oceanographic serving infrastructure**. By strictly enforcing separation between training, batch inference, and pure read-only API serving, it delivers real-time operational ocean intelligence with production reliability.
