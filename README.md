# Edge AI Geomagnetic Risk Assessment

This project provides an edge-computing framework for continuously evaluating the risk posed by solar storms to AI data centers, designed to run on devices like the Arduino Uno Q SBC.

## Prerequisites

Ensure your board (e.g., Arduino Uno Q running Debian Linux) has the following installed:
- Python 3.9+
- Docker and Docker Compose (for the database layer)

## 1. Start the Entire Application Stack

The entire application (Database, Ingestion, and Dashboard) is fully Dockerized. You can start everything with a single command:

```bash
docker-compose up -d --build
```

*Note: This will start all services in the background. It will automatically build the Python environment, connect to InfluxDB, start the background data ingestion loop, and serve the dashboard.*

## 2. Launch the Dashboard

Once the containers are running, you can view the live geomagnetic conditions and AI risk map by opening your browser to:

`http://localhost:8501`

*(Grafana is also available at `http://localhost:3000`)*

## Testing

To verify the components are working, you can run the test suite:
```bash
pytest tests/
```
