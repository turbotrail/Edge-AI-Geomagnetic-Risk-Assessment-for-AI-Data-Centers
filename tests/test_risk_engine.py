import pytest
import os
import sys

# Add parent directory to path to allow importing modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analytics.risk_engine import RiskEngine

def test_risk_engine_initialization():
    engine = RiskEngine(model_path='test_model.joblib')
    assert engine is not None
    # Clean up test model if it was created
    if os.path.exists('test_model.joblib'):
        os.remove('test_model.joblib')
