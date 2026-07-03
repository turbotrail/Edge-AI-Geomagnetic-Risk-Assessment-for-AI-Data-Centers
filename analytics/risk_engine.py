import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RiskEngine:
    def __init__(self, model_path: str = '../ml/models/risk_model.joblib'):
        """
        Initialize the Risk Engine.
        Attempts to load a trained Scikit-Learn pipeline. If none exists, 
        initializes an untrained placeholder model.
        """
        self.model_path = model_path
        self.model = None
        self._load_or_initialize_model()
        
    def _load_or_initialize_model(self):
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logging.info(f"Loaded trained risk model from {self.model_path}")
            else:
                logging.warning(f"No trained model found at {self.model_path}. Initializing default untrained pipeline.")
                self.model = Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
                ])
                # We can't use it until it's trained, so we'll set a flag or just leave it untrained
                self.is_trained = False
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            self.model = None

    def train_placeholder_model(self):
        """Trains the model on dummy data to bootstrap the system."""
        logging.info("Training placeholder model with dummy data...")
        
        # Features: [storm_severity, ground_activity, grid_stress, facility_exposure]
        X_dummy = np.random.rand(100, 4)
        
        # Labels: 0 (Low), 1 (Moderate), 2 (High), 3 (Critical)
        # Create some correlation: higher features -> higher risk
        y_dummy = (X_dummy.sum(axis=1) // 1).astype(int) 
        y_dummy = np.clip(y_dummy, 0, 3)
        
        self.model.fit(X_dummy, y_dummy)
        self.is_trained = True
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        logging.info(f"Saved placeholder model to {self.model_path}")

    def calculate_risk_score(self, storm_severity: float, ground_activity: float, grid_stress: float, facility_exposure: float) -> float:
        """
        Calculate the overall AI operational risk score using the ML model.
        Returns a float between 0.0 and 1.0 (approximated from probabilities).
        """
        if not getattr(self, 'is_trained', True):
            logging.warning("Model is untrained. Falling back to simple heuristic.")
            return (storm_severity * 0.35 + ground_activity * 0.30 + grid_stress * 0.20 + facility_exposure * 0.15)
            
        features = np.array([[storm_severity, ground_activity, grid_stress, facility_exposure]])
        
        try:
            # Get probabilities for all classes [Low, Moderate, High, Critical]
            probas = self.model.predict_proba(features)[0]
            
            # Map probabilities to a continuous 0.0 - 1.0 score
            # Expected value of the class indices divided by max class index (3)
            expected_class_val = np.sum(probas * np.array([0, 1, 2, 3]))
            risk_score = expected_class_val / 3.0
            
            logging.info(f"ML Calculated Risk Score: {risk_score:.3f}")
            return risk_score
        except Exception as e:
            logging.error(f"Prediction failed: {e}")
            return 0.0

    def get_alert_level(self, risk_score: float) -> str:
        """Determine alert level based on risk score."""
        if risk_score >= 0.75:
            return "CRITICAL"
        elif risk_score >= 0.50:
            return "HIGH"
        elif risk_score >= 0.25:
            return "MODERATE"
        else:
            return "LOW"

if __name__ == "__main__":
    import os
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models')
    os.makedirs(model_dir, exist_ok=True)
    model_file = os.path.join(model_dir, 'risk_model.joblib')
    
    engine = RiskEngine(model_path=model_file)
    
    # Train the placeholder so it works immediately
    engine.train_placeholder_model()
    
    # Simulate a moderate geomagnetic storm
    simulated_risk = engine.calculate_risk_score(
        storm_severity=0.6,
        ground_activity=0.4,
        grid_stress=0.2,
        facility_exposure=0.5
    )
    
    alert = engine.get_alert_level(simulated_risk)
    print(f"Risk Score: {simulated_risk:.3f} -> Alert Level: {alert}")
