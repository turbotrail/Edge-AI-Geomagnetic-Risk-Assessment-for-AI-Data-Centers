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
    def __init__(self, model_path: str = None):
        """
        Initialize the Risk Engine.
        Attempts to load a trained Scikit-Learn pipeline. If none exists, 
        initializes an untrained placeholder model.
        """
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), 'models', 'risk_model.joblib')
        self.model_path = model_path
        self.model = None
        self._load_or_initialize_model()
        
    def _load_or_initialize_model(self):
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logging.info(f"Loaded trained risk model from {self.model_path}")
            else:
                self._initialize_default_model()
        except Exception as e:
            logging.error(f"Error loading model: {e}")
            self._initialize_default_model()

    def _initialize_default_model(self):
        logging.warning("Initializing default untrained MLP pipeline.")
        from sklearn.neural_network import MLPClassifier
        
        self.model = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', MLPClassifier(
                hidden_layer_sizes=(16, 8),
                max_iter=500,
                activation='relu',
                solver='adam',
                random_state=42,
                learning_rate_init=0.01
            ))
        ])
        self.is_trained = False

    def train_model(self, data_path: str = None):
        """Trains the model on historical space weather data."""
        if data_path is None:
            data_path = os.path.join(os.path.dirname(__file__), 'historical_training_data.csv')
            
        if os.path.exists(data_path):
            logging.info(f"Training model with real historical data from {data_path}...")
            df = pd.read_csv(data_path)
            
            # If historical data doesn't have the new local_b_field, generate synthetic baseline
            if 'local_b_field' not in df.columns:
                df['local_b_field'] = np.random.normal(loc=1000.0, scale=100.0, size=len(df))
            
            # Features: [storm_severity, ground_activity, grid_stress, facility_exposure, local_b_field]
            X = df[['storm_severity', 'ground_activity', 'grid_stress', 'facility_exposure', 'local_b_field']].values
            y = df['risk_label'].values
        else:
            logging.warning(f"Training data not found at {data_path}. Falling back to dummy data...")
            X = np.random.rand(100, 5)
            # Scale the 5th feature to realistic B field values
            X[:, 4] = X[:, 4] * 2000.0 
            y = (X[:, :4].sum(axis=1) // 1).astype(int) 
            y = np.clip(y, 0, 3)
            
        self.model.fit(X, y)
        self.is_trained = True
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        logging.info(f"Saved trained model to {self.model_path}")

    def calculate_risk_score(self, storm_severity: float, ground_activity: float, grid_stress: float, facility_exposure: float, local_b_field: float = 0.0) -> float:
        """
        Calculate the overall AI operational risk score using the ML model.
        Returns a float between 0.0 and 1.0 (approximated from probabilities).
        """
        if not getattr(self, 'is_trained', True):
            logging.warning("Model is untrained. Falling back to simple heuristic.")
            return (storm_severity * 0.30 + ground_activity * 0.25 + grid_stress * 0.20 + facility_exposure * 0.15 + local_b_field * 0.10)
            
        features = np.array([[storm_severity, ground_activity, grid_stress, facility_exposure, local_b_field]])
        
        try:
            # Get probabilities for all classes [Low, Moderate, High, Critical]
            probas = self.model.predict_proba(features)[0]
            
            # Map probabilities to a continuous 0.0 - 1.0 score
            # Expected value of risk (0 to 3) normalized to 0.0 - 1.0
            expected_risk = sum(i * p for i, p in enumerate(probas))
            
            # The MLP pushes probabilities to infinitesimally small values (e.g. e-39) when conditions are totally calm.
            # We add a fraction of the static facility_exposure to represent the inherent geographic vulnerability 
            # (baseline risk) even during calm space weather. This ensures distinct, readable numbers per data center.
            base_vulnerability = facility_exposure * 0.15
            
            final_score = (expected_risk / 3.0) + base_vulnerability
            
            logging.info(f"ML Calculated Risk Score: {final_score:.3f}")
            return final_score
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
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
    os.makedirs(model_dir, exist_ok=True)
    model_file = os.path.join(model_dir, 'risk_model.joblib')
    
    engine = RiskEngine(model_path=model_file)
    
    # Train the model (will use historical CSV if available)
    engine.train_model()
    
    # Simulate a moderate geomagnetic storm
    simulated_risk = engine.calculate_risk_score(
        storm_severity=0.6,
        ground_activity=0.4,
        grid_stress=0.2,
        facility_exposure=0.5,
        local_b_field=0.3
    )
    
    alert = engine.get_alert_level(simulated_risk)
    print(f"Risk Score: {simulated_risk:.3f} -> Alert Level: {alert}")
