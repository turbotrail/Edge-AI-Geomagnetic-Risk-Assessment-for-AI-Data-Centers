import time
import logging
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import yaml
import os
import math

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HistoricalReplay:
    def __init__(self, config_path: str = '../configs/config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        db_config = self.config['database']['influxdb']
        self.influx_client = InfluxDBClient(url=db_config['url'], token=db_config['token'], org=db_config['org'])
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.bucket = db_config['bucket']

    def simulate_storm_event(self, event_name: str = "Halloween 2003 Profile"):
        """
        Injects a simulated severe geomagnetic storm profile into InfluxDB.
        The data spans the last 3 hours up to 'now'.
        """
        logging.info(f"Starting Historical Replay simulation for: {event_name}")
        
        now = datetime.utcnow()
        # Create 180 minutes of data (3 hours)
        for i in range(180, -1, -1):
            timestamp = now - timedelta(minutes=i)
            
            # Simulate Kp rising from 3 to 9 and back down
            # Bell curve centered at i=90 (peak of storm)
            dist_from_peak = abs(i - 90)
            kp = max(1.0, 9.0 * math.exp(-(dist_from_peak**2) / 1000.0))
            
            # Simulate Solar Wind speed rising from 400 to 1200 km/s
            sw_speed = 400 + 800 * math.exp(-(dist_from_peak**2) / 800.0)
            
            # Tag this specifically so the dashboard knows it's a replay
            point_kp = Point("geomagnetic_indices") \
                .tag("source", "historical_replay") \
                .tag("event", event_name) \
                .field("kp_index", round(kp, 2)) \
                .time(timestamp, WritePrecision.S)
                
            point_sw = Point("solar_wind") \
                .tag("source", "historical_replay") \
                .tag("event", event_name) \
                .field("speed", round(sw_speed, 2)) \
                .field("density", 15.0) \
                .time(timestamp, WritePrecision.S)
                
            self.write_api.write(bucket=self.bucket, record=[point_kp, point_sw])
            
        logging.info(f"Successfully injected 3 hours of replay data for {event_name}")

if __name__ == "__main__":
    config_file = os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.yaml')
    replay = HistoricalReplay(config_path=config_file)
    replay.simulate_storm_event("May 2024 Geomagnetic Storm")
