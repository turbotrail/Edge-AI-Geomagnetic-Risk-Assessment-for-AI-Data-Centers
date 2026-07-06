from arduino.app_utils import *
from influxdb_client import InfluxDBClient, Point
import math
import time

logger = Logger("Magnetometer")

# -----------------------------
# InfluxDB Configuration
# -----------------------------
INFLUX_URL = "http://192.168.0.113:8086"      # or http://influxdb:8086 if on same Docker network
TOKEN = "your-influxdb-token-here"
ORG = "spacewx"
BUCKET = "mag_sensor"

client = InfluxDBClient(
    url=INFLUX_URL,
    token=TOKEN,
    org=ORG
)

write_api = client.write_api()

# -----------------------------
# Buffer
# -----------------------------
samples = []
last_write = time.time()

WRITE_INTERVAL = 60      # seconds


def record_magnetometer(x, y, z):

    global last_write

    # Store sample
    samples.append((x, y, z))

    # Time to write?
    now = time.time()

    if now - last_write >= WRITE_INTERVAL and samples:

        avg_x = sum(s[0] for s in samples) / len(samples)
        avg_y = sum(s[1] for s in samples) / len(samples)
        avg_z = sum(s[2] for s in samples) / len(samples)

        B = math.sqrt(avg_x**2 + avg_y**2 + avg_z**2)

        point = (
            Point("magnetometer")
            .tag("sensor", "mmc5603")
            .field("x", avg_x)
            .field("y", avg_y)
            .field("z", avg_z)
            .field("B", B)
        )

        write_api.write(bucket=BUCKET, record=point)

        logger.info(
            f"Wrote {len(samples)} samples "
            f"Avg=({avg_x:.2f}, {avg_y:.2f}, {avg_z:.2f}) "
            f"B={B:.2f}"
        )

        samples.clear()
        last_write = now


Bridge.provide(
    "record_magnetometer",
    record_magnetometer
)

App.run()