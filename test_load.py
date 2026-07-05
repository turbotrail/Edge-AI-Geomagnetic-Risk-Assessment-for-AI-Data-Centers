import os
import joblib

try:
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ml', 'models', 'risk_model.joblib'))
    print(f"Loading from {model_path}")
    model = joblib.load(model_path)
    print("Success!")
except Exception as e:
    print(f"Failed to load: {type(e).__name__}: {e}")
