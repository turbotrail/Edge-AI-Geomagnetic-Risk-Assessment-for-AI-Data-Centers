import requests
import pandas as pd
import numpy as np
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_historical_kp_data(start_year=2010, end_year=2024):
    """
    Downloads historical Kp index data from GFZ Potsdam.
    This provides REAL space weather severity data covering a full solar cycle!
    """
    url = f"https://kp.gfz-potsdam.de/app/json/?start={start_year}-01-01T00:00:00Z&end={end_year}-01-01T00:00:00Z&index=Kp"
    
    logging.info(f"Downloading historical Kp data from GFZ Potsdam ({start_year}-{end_year})...")
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame({
            'datetime': pd.to_datetime(data['datetime']),
            'kp_index': data['Kp']
        })
        logging.info(f"Successfully downloaded {len(df)} historical data points.")
        return df
    else:
        logging.error(f"Failed to download data. HTTP Status: {response.status_code}")
        return pd.DataFrame()

def generate_training_dataset(df_kp, output_path="historical_training_data.csv"):
    """
    Transforms the raw Kp data into the 4 features needed by the RiskEngine:
    [storm_severity, ground_activity, grid_stress, facility_exposure]
    
    Since true data center outages are private, we use the REAL Kp index to 
    simulate the other highly-correlated terrestrial effects to build a training set.
    """
    logging.info("Engineering features for the ML model...")
    
    # 1. Storm Severity (Normalized Kp: 0 to 1)
    df_kp['storm_severity'] = df_kp['kp_index'] / 9.0
    
    # 2. Ground Activity (Strongly correlated with Kp, with some random local variance)
    # dB/dt spikes exponentially at higher Kp levels
    noise = np.random.normal(0, 0.1, len(df_kp))
    df_kp['ground_activity'] = np.clip((df_kp['kp_index'] / 9.0)**2 + noise, 0.0, 1.0)
    
    # 3. Grid Stress (Correlated with ground activity + regional factors)
    noise_grid = np.random.normal(0, 0.05, len(df_kp))
    df_kp['grid_stress'] = np.clip(df_kp['ground_activity'] * 0.8 + noise_grid, 0.0, 1.0)
    
    # 4. Facility Exposure (Randomized between 0.1 and 0.9 to simulate different data centers)
    df_kp['facility_exposure'] = np.random.uniform(0.1, 0.9, len(df_kp))
    
    # --- Create the Target Label ---
    # We create a heuristic target label based on the severe physics of geomagnetic storms
    # so the ML model has something to learn and predict.
    def label_risk(row):
        # Weighted impact score
        impact = (row['storm_severity'] * 0.35 + 
                  row['ground_activity'] * 0.30 + 
                  row['grid_stress'] * 0.20 + 
                  row['facility_exposure'] * 0.15)
        
        if impact > 0.75: return 3 # CRITICAL
        elif impact > 0.50: return 2 # HIGH
        elif impact > 0.25: return 1 # MODERATE
        else: return 0 # LOW

    logging.info("Assigning risk labels to historical events...")
    df_kp['risk_label'] = df_kp.apply(label_risk, axis=1)
    
    # Save the final dataset
    df_final = df_kp[['datetime', 'storm_severity', 'ground_activity', 'grid_stress', 'facility_exposure', 'risk_label']]
    df_final.to_csv(output_path, index=False)
    logging.info(f"Dataset saved successfully to {output_path}")
    
    # Print a summary of the events
    logging.info("\nDataset Risk Distribution:")
    logging.info(df_final['risk_label'].value_counts().sort_index())
    
    return df_final

if __name__ == "__main__":
    # 1. Download real space weather data spanning a 14-year solar cycle
    df_raw = download_historical_kp_data(start_year=2010, end_year=2024)
    
    if not df_raw.empty:
        # 2. Build the training dataset and save it
        output_csv = os.path.join(os.path.dirname(__file__), 'historical_training_data.csv')
        df_train = generate_training_dataset(df_raw, output_path=output_csv)
        
        print("\n--- Next Steps ---")
        print(f"You can now modify risk_model.py's train_placeholder_model() to read from {output_csv}")
        print("instead of using np.random.rand()!")
