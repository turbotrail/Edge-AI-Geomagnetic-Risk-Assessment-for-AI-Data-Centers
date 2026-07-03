import requests
import time
import yaml
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NOAAIngestor:
    def __init__(self, config_path: str = '../configs/config.yaml'):
        self.config = self._load_config(config_path)
        self.k_index_url = self.config['data_ingestion']['noaa_swpc_url']
        self.solar_wind_url = self.config['data_ingestion']['solar_wind_url']
        self.solar_mag_url = self.config['data_ingestion']['solar_mag_url']
        
        # InfluxDB Setup
        db_config = self.config['database']['influxdb']
        self.influx_client = InfluxDBClient(url=db_config['url'], token=db_config['token'], org=db_config['org'])
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.bucket = db_config['bucket']
        
        # Enforce retention policy
        retention_days = db_config.get('retention_days', 30)
        self._enforce_retention(retention_days)
        
    def _enforce_retention(self, days: int):
        try:
            buckets_api = self.influx_client.buckets_api()
            bucket = buckets_api.find_bucket_by_name(self.bucket)
            if bucket:
                retention_seconds = days * 24 * 60 * 60
                
                # Check current rules
                needs_update = True
                if bucket.retention_rules:
                    current_rule = bucket.retention_rules[0]
                    # Note: API might return a dict or an object depending on version
                    if hasattr(current_rule, 'every_seconds') and current_rule.every_seconds == retention_seconds:
                        needs_update = False
                    elif isinstance(current_rule, dict) and current_rule.get('every_seconds') == retention_seconds:
                        needs_update = False
                        
                if needs_update:
                    rule = BucketRetentionRules(type='expire', every_seconds=retention_seconds)
                    bucket.retention_rules = [rule]
                    buckets_api.update_bucket(bucket)
                    logging.info(f"Enforced {days}-day retention policy on InfluxDB bucket '{self.bucket}'.")
                else:
                    logging.info(f"Retention policy for '{self.bucket}' is already set to {days} days.")
            else:
                logging.warning(f"Bucket '{self.bucket}' not found. Retention policy could not be set.")
        except Exception as e:
            logging.error(f"Failed to enforce bucket retention policy: {e}")

    def _load_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.error(f"Failed to load config from {path}: {e}")
            return {}

    def fetch_planetary_k_index(self) -> Optional[list]:
        """Fetch real-time Planetary K-index from NOAA SWPC."""
        try:
            response = requests.get(self.k_index_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info("Successfully fetched Planetary K-index data")
            return data
        except requests.RequestException as e:
            logging.error(f"Error fetching K-index: {e}")
            return None

    def fetch_solar_wind(self) -> list:
        try:
            response = requests.get(self.solar_wind_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info(f"Successfully fetched Solar Wind Speed data")
            return data
        except Exception as e:
            logging.error(f"Failed to fetch Solar Wind data: {e}")
            return []
            
    def fetch_solar_mag(self) -> list:
        try:
            response = requests.get(self.solar_mag_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info(f"Successfully fetched Solar Mag (IMF) data")
            return data
        except Exception as e:
            logging.error(f"Failed to fetch Solar Mag data: {e}")
            return []

    def fetch_f107_flux(self) -> list:
        url = self.config['data_ingestion'].get('f107_flux_url')
        if not url: return []
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            logging.info("Successfully fetched F10.7 Flux data")
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch F10.7 Flux data: {e}")
            return []

    def write_k_index_to_influx(self, data: list):
        if not data or len(data) <= 1:
            return
            
        written = 0
        for entry in data:
            try:
                time_tag_str = entry["time_tag"]
                try:
                    # Format: "2026-06-25T00:00:00"
                    time_tag = datetime.strptime(time_tag_str, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    # Skip invalid format
                    continue
                    
                kp_value = float(entry["Kp"])
                
                point = Point("geomagnetic_indices") \
                    .tag("source", "noaa_swpc") \
                    .field("kp_index", kp_value) \
                    .time(time_tag, WritePrecision.S)
                    
                self.write_api.write(bucket=self.bucket, record=point)
                written += 1
            except Exception as e:
                logging.debug(f"Failed to parse K-index entry: {e}")
                
        logging.info(f"Wrote {written} K-index records to InfluxDB")

    def write_solar_wind_to_influx(self, wind_data: list, mag_data: list):
        if not wind_data or len(wind_data) == 0:
            logging.warning("Solar wind data is empty.")
            return
            
        latest_wind = wind_data[-1]
        
        # Parse time_tag
        time_tag_str = latest_wind.get("time_tag")
        if time_tag_str:
            time_tag_str = time_tag_str.replace("Z", "+00:00")
            time_tag = datetime.fromisoformat(time_tag_str)
        else:
            time_tag = datetime.utcnow()
            
        speed = float(latest_wind.get("proton_speed", 0))
        
        bt = 0.0
        bz = 0.0
        if mag_data and len(mag_data) > 0:
            latest_mag = mag_data[-1]
            bt = float(latest_mag.get("bt", 0))
            bz = float(latest_mag.get("bz_gsm", 0))
        
        try:
            point = Point("solar_wind") \
                .tag("source", "noaa_swpc") \
                .field("speed", speed) \
                .field("bt", bt) \
                .field("bz", bz) \
                .time(time_tag, WritePrecision.S)
                
            self.write_api.write(bucket=self.bucket, record=point)
            logging.info(f"Wrote Solar Wind (speed: {speed}, bt: {bt}, bz: {bz}) to InfluxDB")
        except Exception as e:
            logging.exception(f"Failed to write Solar Wind to InfluxDB")

    def write_f107_to_influx(self, data: list):
        if not data or len(data) == 0:
            return
            
        latest_entry = data[-1]
        try:
            time_tag_str = latest_entry["time_tag"]
            try:
                time_tag = datetime.strptime(time_tag_str, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                time_tag = datetime.utcnow()
                
            flux_value = float(latest_entry["flux"])
            
            point = Point("solar_flux") \
                .tag("source", "noaa_swpc") \
                .field("f107_flux", flux_value) \
                .time(time_tag, WritePrecision.S)
                
            self.write_api.write(bucket=self.bucket, record=point)
            logging.info(f"Wrote F10.7 Flux {flux_value} to InfluxDB")
        except Exception as e:
            logging.exception(f"Failed to write F10.7 Flux to InfluxDB")

    def run_ingestion_loop(self):
        interval = self.config['data_ingestion'].get('update_interval_seconds', 60)
        logging.info(f"Starting NOAA Ingestion Loop (Interval: {interval}s)")
        
        while True:
            try:
                k_index_data = self.fetch_planetary_k_index()
                self.write_k_index_to_influx(k_index_data)
            except Exception as e:
                logging.error(f"Error during K-index processing: {e}")
                
            try:
                solar_wind = self.fetch_solar_wind()
                solar_mag = self.fetch_solar_mag()
                self.write_solar_wind_to_influx(solar_wind, solar_mag)
            except Exception as e:
                logging.error(f"Error during Solar Wind processing: {e}")
                
            try:
                flux_data = self.fetch_f107_flux()
                self.write_f107_to_influx(flux_data)
            except Exception as e:
                logging.error(f"Error during F10.7 Flux processing: {e}")
                
            time.sleep(interval)

if __name__ == "__main__":
    import os
    config_file = os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.yaml')
    
    ingestor = NOAAIngestor(config_path=config_file)
    
    # Run once for testing if we just want a single execution, 
    # but normally we'd run the loop
    k_index = ingestor.fetch_planetary_k_index()
    ingestor.write_k_index_to_influx(k_index)
    
    solar_wind = ingestor.fetch_solar_wind()
    solar_mag = ingestor.fetch_solar_mag()
    ingestor.write_solar_wind_to_influx(solar_wind, solar_mag)
    
    # To run continuously:
    ingestor.run_ingestion_loop()
