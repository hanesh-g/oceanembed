import pytest
import numpy as np
import sys
import os
from pathlib import Path

# Add worker dir to path so we can import quality_gate
# It's assumed the test runs from backend or root.
worker_dir = Path(__file__).parent.parent.parent.parent.parent / "worker"
sys.path.append(str(worker_dir))

from quality_gate import QualityGate

def test_quality_gate_passes_clean_data(mock_scaler_json, dummy_ocean_dataset):
    """Test that the quality gate passes perfectly clean, in-bounds data."""
    qg = QualityGate(mock_scaler_json)
    passed, log = qg.evaluate(dummy_ocean_dataset)
    assert passed is True
    assert log["data_integrity"]["nan_fractions"]["thetao"] == 0.0
    assert log["data_integrity"]["nan_fractions"]["so"] == 0.0

def test_quality_gate_fails_out_of_bounds(mock_scaler_json, dummy_ocean_dataset):
    """Test that the quality gate fails if physical bounds are exceeded."""
    # thetao bounds are (-2.0, 36.0). Let's set a value to 40.0
    dummy_ocean_dataset["thetao"].values[0, 0, 0] = 40.0
    
    qg = QualityGate(mock_scaler_json)
    passed, log = qg.evaluate(dummy_ocean_dataset)
    assert passed is False
    assert "thetao" in log["data_integrity"]["bounds_violations"]
    assert log["data_integrity"]["bounds_violations"]["thetao"]["max"] == 40.0

def test_quality_gate_fails_excessive_nans(mock_scaler_json, dummy_ocean_dataset):
    """Test that the quality gate fails if NaN fraction exceeds 5%."""
    # Set 10% of the values to NaN
    data = dummy_ocean_dataset["thetao"].values
    size = data.size
    data.flat[:int(size * 0.10)] = np.nan
    
    qg = QualityGate(mock_scaler_json)
    passed, log = qg.evaluate(dummy_ocean_dataset)
    assert passed is False
    assert log["data_integrity"]["nan_fractions"]["thetao"] >= 0.10

def test_quality_gate_fails_distribution_drift(mock_scaler_json, dummy_ocean_dataset):
    """Test that the quality gate fails if Z-scores are extremely anomalous."""
    # Z-score > 4.0 on more than 1% of cells.
    # mean is 15.0, std is 2.0. So 15.0 + 4.1*2.0 = 23.2
    data = dummy_ocean_dataset["thetao"].values
    size = data.size
    # Set 2% of the values to a high Z-score
    data.flat[:int(size * 0.02)] = 23.2
    
    qg = QualityGate(mock_scaler_json)
    passed, log = qg.evaluate(dummy_ocean_dataset)
    assert passed is False
    assert log["distribution_drift"]["anomalous_fractions"]["thetao"] >= 0.02
