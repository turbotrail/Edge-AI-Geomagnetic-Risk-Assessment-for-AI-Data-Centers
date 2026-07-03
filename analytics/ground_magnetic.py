import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GroundMagneticAnalyzer:
    def __init__(self, sampling_rate_hz: float = 1.0):
        """
        Initializes the analyzer for ground magnetometer data.
        :param sampling_rate_hz: The sampling rate of the magnetometer in Hz.
        """
        self.sampling_rate_hz = sampling_rate_hz
        self.dt_seconds = 1.0 / sampling_rate_hz
        
    def calculate_db_dt(self, magnetic_field_series: np.ndarray) -> np.ndarray:
        """
        Calculates the rate of change of the magnetic field (dB/dt).
        This is a primary driver for Geomagnetically Induced Currents (GIC).
        
        :param magnetic_field_series: 1D numpy array of magnetic field readings (e.g., in nT)
        :return: 1D numpy array of dB/dt (e.g., in nT/s)
        """
        if len(magnetic_field_series) < 2:
            logging.warning("Not enough data points to calculate dB/dt.")
            return np.array([])
            
        # Use numpy gradient for numerical differentiation
        db_dt = np.gradient(magnetic_field_series, self.dt_seconds)
        return db_dt
        
    def extract_anomalies(self, magnetic_field_series: np.ndarray, window_size: int = 60, threshold_sigma: float = 3.0) -> np.ndarray:
        """
        Detects anomalous spikes in the magnetic field using a rolling window Z-score approach.
        
        :param magnetic_field_series: 1D numpy array of magnetic field readings.
        :param window_size: Size of the rolling window to compute baseline mean/std.
        :param threshold_sigma: Number of standard deviations to flag as an anomaly.
        :return: Boolean array where True indicates an anomaly.
        """
        if len(magnetic_field_series) < window_size:
            return np.zeros_like(magnetic_field_series, dtype=bool)
            
        series = pd.Series(magnetic_field_series)
        rolling_mean = series.rolling(window=window_size, min_periods=1).mean()
        rolling_std = series.rolling(window=window_size, min_periods=1).std()
        
        # Avoid division by zero
        rolling_std = rolling_std.replace(0, 1e-6)
        
        z_scores = np.abs((series - rolling_mean) / rolling_std)
        anomalies = (z_scores > threshold_sigma).to_numpy()
        
        num_anomalies = np.sum(anomalies)
        if num_anomalies > 0:
            logging.info(f"Detected {num_anomalies} anomalies in the magnetic field data.")
            
        return anomalies

if __name__ == "__main__":
    # Test the Analyzer with dummy data
    analyzer = GroundMagneticAnalyzer(sampling_rate_hz=1.0)
    
    # Simulate a quiet baseline with a sudden storm spike
    time_steps = np.arange(0, 300)
    quiet_field = 50000 + 10 * np.sin(2 * np.pi * time_steps / 100) # Baseline 50,000 nT
    storm_spike = np.zeros_like(time_steps)
    storm_spike[150:160] = np.linspace(0, 500, 10) # 500 nT spike
    
    total_field = quiet_field + storm_spike
    
    db_dt = analyzer.calculate_db_dt(total_field)
    anomalies = analyzer.extract_anomalies(total_field)
    
    print(f"Max dB/dt: {np.max(np.abs(db_dt)):.2f} nT/s")
    print(f"Number of anomalies detected: {np.sum(anomalies)}")
