import os
import json
import uuid
import shutil
import datetime
import logging
import argparse
import numpy as np
import xarray as xr
from pathlib import Path
from quality_gate import QualityGate

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_dummy_data(week_str: str) -> xr.Dataset:
    """Simulate output data of a 5-member ensemble forward pass."""
    # Assuming global 0.25 deg resolution: 1440 lon x 720 lat
    # But for a dummy, we use smaller dimensions just for testing
    lon = np.linspace(-180, 180, 144)
    lat = np.linspace(-90, 90, 72)
    depth = [0, 5, 10, 20, 50, 100, 200, 500, 1000]

    ds = xr.Dataset(
        coords={
            "lon": lon,
            "lat": lat,
            "depth": depth,
            "time": [datetime.datetime.strptime(week_str + "-1", "%Y-W%W-%w")] # e.g. "2025-W01-1"
        }
    )

    # Generate some dummy variables
    dims = ("time", "depth", "lat", "lon")
    shape = (1, len(depth), len(lat), len(lon))
    
    # Simulate temperatures around 15C
    ds["temp"] = (dims, np.random.normal(15, 5, shape).astype(np.float32))
    # Simulate salinity around 35 PSU
    ds["sal"] = (dims, np.random.normal(35, 1, shape).astype(np.float32))
    # Simulate derived products
    ds["d26"] = (dims, np.random.normal(50, 10, shape).astype(np.float32))
    ds["tchp"] = (dims, np.random.normal(60, 20, shape).astype(np.float32))
    ds["mld"] = (dims, np.random.normal(30, 5, shape).astype(np.float32))
    
    # Simulate uncertainty/spread
    ds["temp_spread"] = (dims, np.random.exponential(0.5, shape).astype(np.float32))
    ds["sal_spread"] = (dims, np.random.exponential(0.1, shape).astype(np.float32))
    ds["d26_spread"] = (dims, np.random.exponential(2.0, shape).astype(np.float32))
    ds["tchp_spread"] = (dims, np.random.exponential(5.0, shape).astype(np.float32))
    ds["mld_spread"] = (dims, np.random.exponential(1.5, shape).astype(np.float32))

    return ds

def run_weekly_inference(week_str: str, model_registry_path: str, published_path: str):
    logger.info(f"Starting weekly inference for {week_str}")

    model_dir = Path(model_registry_path) / "oceanembed-v1.0.0"
    scaler_path = model_dir / "scaler.json"
    calibration_path = model_dir / "calibration.json"

    # In a real run, we would load weights and run model
    logger.info("Performing 5-member ensemble forward pass...")
    ds = create_dummy_data(week_str)

    logger.info("Aggregating ensemble mean and applying VIF to spread...")
    # Read VIF from calibration.json
    vif = 1.0
    if calibration_path.exists():
        try:
            with open(calibration_path, "r") as f:
                calib = json.load(f)
                vif = calib.get("vif", 1.0)
        except Exception as e:
            logger.warning(f"Could not load VIF from {calibration_path}: {e}")

    # Apply VIF
    for var in ["temp_spread", "sal_spread", "d26_spread", "tchp_spread", "mld_spread"]:
        ds[var] = ds[var] * vif

    logger.info("Executing Quality Gate...")
    qg = QualityGate(str(scaler_path))
    passed, audit_log = qg.evaluate(ds)

    logger.info(f"Quality Gate passed: {passed}")
    if not passed:
        logger.error(f"Quality Gate failed! Audit log: {json.dumps(audit_log, indent=2)}")
        raise RuntimeError("Inference output failed quality gate verification.")

    # Write resulting arrays to immutable Zarr directory
    output_dir = Path(published_path) / f"week={week_str}"
    
    # Remove if exists (to be idempotent)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    logger.info(f"Writing data to {output_dir}")
    ds.to_zarr(output_dir)

    # Perform atomic symlink swap
    latest_symlink = Path(published_path) / "latest"
    tmp_symlink = Path(published_path) / f"latest_tmp_{uuid.uuid4().hex}"

    logger.info("Performing atomic symlink swap...")
    # target for symlink is just the directory name to keep it relative
    target = f"week={week_str}"

    os.symlink(target, tmp_symlink)
    os.replace(tmp_symlink, latest_symlink)
    
    logger.info(f"Successfully published {week_str} and repointed latest.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly inference worker")
    parser.add_argument("--week", type=str, help="Target week (e.g., 2025-W03)", required=True)
    parser.add_argument("--model-registry", type=str, default="../model-registry", help="Path to model registry")
    parser.add_argument("--published", type=str, default="../data/published", help="Path to published data")
    
    args = parser.parse_args()
    
    # Set default paths assuming running from worker dir if paths are relative
    base_path = Path(__file__).parent.parent
    model_registry = args.model_registry if Path(args.model_registry).is_absolute() else base_path / args.model_registry
    published = args.published if Path(args.published).is_absolute() else base_path / args.published
    
    run_weekly_inference(args.week, str(model_registry), str(published))
