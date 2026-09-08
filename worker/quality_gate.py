import json
import logging
from typing import Dict, Any, Tuple
import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

class QualityGate:
    """
    Implements a dual-check verification system for weekly inference output.
    """
    
    # Strict physical bounds for core variables
    PHYSICAL_BOUNDS = {
        "temp": (-2.0, 36.0),    # Temperature in Celsius
        "sal": (10.0, 42.0),     # Salinity in PSU
        "d26": (0.0, 300.0),     # Depth of 26C isotherm
        "tchp": (0.0, 200.0),    # Tropical Cyclone Heat Potential
        "mld": (0.0, 500.0),     # Mixed Layer Depth
        "zos": (-2.0, 2.0),      # Sea surface height in meters
        "uo": (-3.0, 3.0),       # Eastward velocity m/s
        "vo": (-3.0, 3.0),       # Northward velocity m/s
    }

    def __init__(self, scaler_path: str):
        self.scaler_path = scaler_path
        self._load_scaler()

    def _load_scaler(self):
        """Loads the scaler.json from the model registry."""
        try:
            with open(self.scaler_path, "r") as f:
                self.scaler_config = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load scaler config from {self.scaler_path}: {e}")
            self.scaler_config = {}

    def check_data_integrity(self, ds: xr.Dataset) -> Tuple[bool, Dict[str, Any]]:
        """
        Check 1: Data Integrity
        - NaN fractions < 5%
        - Variables fall within strict physical bounds
        """
        passed = True
        log = {"nan_fractions": {}, "bounds_violations": {}}

        for var_name, bounds in self.PHYSICAL_BOUNDS.items():
            if var_name not in ds:
                continue

            data = ds[var_name].values
            valid_mask = ~np.isnan(data)
            nan_fraction = 1.0 - (valid_mask.sum() / data.size) if data.size > 0 else 1.0
            
            log["nan_fractions"][var_name] = float(nan_fraction)
            if nan_fraction > 0.05:
                passed = False

            # Check bounds
            if valid_mask.any():
                valid_data = data[valid_mask]
                min_val = float(valid_data.min())
                max_val = float(valid_data.max())
                
                if min_val < bounds[0] or max_val > bounds[1]:
                    passed = False
                    log["bounds_violations"][var_name] = {
                        "min": min_val,
                        "max": max_val,
                        "allowed": bounds
                    }

        return passed, log

    def check_distribution_drift(self, ds: xr.Dataset) -> Tuple[bool, Dict[str, Any]]:
        """
        Check 2: Distribution Drift
        - Compute per-channel Z-scores using scaler.json.
        - Flag anomalous distributions where |z| > 4.0 on more than 1% of the cells.
        """
        passed = True
        log = {"anomalous_fractions": {}}

        if not self.scaler_config:
            log["error"] = "Scaler config not loaded"
            return False, log

        means = self.scaler_config.get("means", {})
        stds = self.scaler_config.get("stds", {})

        for var_name in means.keys():
            if var_name not in ds:
                continue

            data = ds[var_name].values
            valid_mask = ~np.isnan(data)
            
            if not valid_mask.any():
                continue

            mean = means[var_name]
            std = stds[var_name]

            if std == 0:
                continue

            # Compute Z-scores
            valid_data = data[valid_mask]
            z_scores = np.abs((valid_data - mean) / std)
            
            # Fraction where |z| > 4.0
            anomalous_fraction = float((z_scores > 4.0).sum() / valid_data.size)
            log["anomalous_fractions"][var_name] = anomalous_fraction

            if anomalous_fraction > 0.01:
                passed = False

        return passed, log

    def evaluate(self, ds: xr.Dataset) -> Tuple[bool, Dict[str, Any]]:
        """
        Run all quality gate checks and return an audit log.
        """
        integrity_passed, integrity_log = self.check_data_integrity(ds)
        drift_passed, drift_log = self.check_distribution_drift(ds)

        passed = integrity_passed and drift_passed
        audit_log = {
            "passed": passed,
            "data_integrity": integrity_log,
            "distribution_drift": drift_log
        }

        return passed, audit_log
