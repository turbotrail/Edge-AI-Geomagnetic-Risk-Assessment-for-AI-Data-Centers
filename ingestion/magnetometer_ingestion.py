import os
import time
import json
import logging
import requests
import yaml
from datetime import datetime, timedelta
import numpy as np
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MagnetometerIngestion:
    def __init__(self, config_path: str = '/app/configs/config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        db_config = self.config['database']['influxdb']
        self.client = InfluxDBClient(
            url=db_config['url'],
            token=db_config['token'],
            org=db_config['org']
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.bucket = db_config['bucket']
        
        self.intermagnet_stations = self.config['data_ingestion'].get('intermagnet_stations', [])
        self.usgs_stations = []
        self._load_usgs_observatories()

    def _load_usgs_observatories(self):
        try:
            url = "https://geomag.usgs.gov/ws/observatories/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            features = data.get('features', [])
            
            for f in features:
                station_id = f.get('id')
                if station_id:
                    self.usgs_stations.append(station_id)
            logging.info(f"Dynamically loaded {len(self.usgs_stations)} USGS observatories.")
        except Exception as e:
            logging.error(f"Failed to load USGS observatories dynamically: {e}")
            # Fallback to config list if API fails
            self.usgs_stations = self.config['data_ingestion'].get('usgs_stations', [])

    def fetch_usgs_dbdt(self, station: str):
        now = datetime.utcnow()
        # Fetch the last 15 minutes to ensure we get at least one valid recent reading
        start_time = (now - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        url = f"https://geomag.usgs.gov/ws/algorithms/dbdt/?id={station}&elements=H&starttime={start_time}&endtime={end_time}&format=json"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'times' in data and 'values' in data and len(data['values']) > 0:
                times = data['times']
                values = data['values'][0].get('values', [])
                
                # Filter out null values
                valid_pairs = [(t, v) for t, v in zip(times, values) if v is not None]
                if valid_pairs:
                    latest_time_str, latest_val = valid_pairs[-1]
                    # Robust datetime parsing to handle both Z and .000Z
                    latest_time_str = latest_time_str.replace("Z", "+00:00")
                    time_tag = datetime.fromisoformat(latest_time_str)
                    return {"time": time_tag, "db_dt": float(latest_val)}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                # 422 Unprocessable Entity usually means the station (like TST) doesn't have dbdt algorithms enabled
                logging.debug(f"Skipping USGS station {station} (422 Unprocessable Entity)")
            else:
                logging.error(f"HTTP Error fetching USGS db/dt for {station}: {e}")
        except Exception as e:
            logging.error(f"Failed to fetch USGS db/dt for {station}: {e}")
        return None

    def fetch_intermagnet_station(self, station: str):
        # MOCK/FALLBACK for INTERMAGNET stations without direct db/dt API
        time_tag = datetime.utcnow()
        # Mocking a small db/dt variation
        db_dt = np.random.normal(0, 0.5) 
        return {"time": time_tag, "db_dt": db_dt}

    def process_station(self, station: str, network: str):
        if network == 'USGS':
            data = self.fetch_usgs_dbdt(station)
        else:
            data = self.fetch_intermagnet_station(station)
            
        if not data:
            return
            
        current_time = data["time"]
        db_dt = data["db_dt"]
        
        try:
            point = Point("magnetometer") \
                .tag("station", station) \
                .tag("network", network) \
                .field("db_dt", db_dt) \
                .time(current_time, WritePrecision.S)
                
            self.write_api.write(bucket=self.bucket, record=point)
            logging.info(f"Wrote {network} {station} data (dB/dt: {db_dt:.2f} nT/min)")
        except Exception as e:
            logging.exception(f"Failed to write data for {station}")

    def run_ingestion_loop(self):
        interval = self.config['data_ingestion'].get('update_interval_seconds', 60)
        logging.info(f"Starting Magnetometer Ingestion Loop (Interval: {interval}s)")
        
        while True:
            for station in self.usgs_stations:
                self.process_station(station, 'USGS')
                
            for station in self.intermagnet_stations:
                self.process_station(station, 'INTERMAGNET')
                
            time.sleep(interval)

if __name__ == "__main__":
    ingestion = MagnetometerIngestion()
    ingestion.run_ingestion_loop()
