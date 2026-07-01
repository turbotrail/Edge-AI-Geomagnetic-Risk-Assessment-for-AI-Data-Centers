# Edge AI Geomagnetic Risk Assessment for AI Data Centers

## Project Vision

### Executive Summary

This project proposes an **edge-computing framework** that continuously
evaluates the risk posed by solar storms and geomagnetic disturbances to
AI data centers using a low-cost Single Board Computer (SBC) such as a
Raspberry Pi 5.

Unlike traditional space weather dashboards, the system transforms
scientific observations into infrastructure-oriented risk intelligence
by combining: - Real-time space weather observations - Ground
magnetometer measurements - Geophysical models - Public infrastructure
metadata - AI-based risk scoring - Local visualization and alerting

The goal is **decision support**, not utility-grade power-grid
simulation.

------------------------------------------------------------------------

# Motivation

Large AI data centers consume hundreds of megawatts of power and depend
on uninterrupted electrical supply.

During severe geomagnetic storms:

Solar Storm → Magnetosphere → Geomagnetic disturbance → Geoelectric
field → Geomagnetically Induced Currents (GIC) → Transformer stress →
Grid instability → Data center operational risk

Current research mainly focuses on: - Space weather forecasting - Power
grids - Transformer GIC modelling

Very little work connects these directly to AI infrastructure.

------------------------------------------------------------------------

# Novelty

## Scientific Novelty

Bridge three traditionally separate domains:

1.  Space Weather
2.  Electrical Power Systems
3.  AI Infrastructure

instead of studying each independently.

------------------------------------------------------------------------

## Engineering Novelty

Perform continuous assessment on a low-cost edge device.

Typical workflow:

Satellite → HPC → Research Paper

Proposed workflow:

Satellite → Raspberry Pi → Continuous Risk Assessment → Dashboard →
Alerts

------------------------------------------------------------------------

## Practical Novelty

Instead of showing:

Kp = 8

show:

-   Grid Risk: High
-   AI Data Center Risk: Medium
-   UPS Utilization Probability
-   Generator Activation Probability
-   Recommended Operational Status

------------------------------------------------------------------------

# Objectives

-   Continuous monitoring
-   Regional geomagnetic risk estimation
-   AI data center exposure analysis
-   Dashboard visualization
-   Alert generation
-   Historical event replay
-   Machine-learning based risk scoring

------------------------------------------------------------------------

# Overall Architecture

    Solar Wind
          │
          ▼
    Satellite Data
          │
          ▼
    Space Weather Processing
          │
          ▼
    Ground Magnetic Analysis
          │
          ▼
    Geoelectric Estimation
          │
          ▼
    Regional Grid Stress Index
          │
          ▼
    AI Data Center Exposure
          │
          ▼
    Operational Risk Score
          │
          ▼
    Dashboard + Alerts

------------------------------------------------------------------------

# Project Structure

``` text
edge-ai-risk/
│
├── data/
│   ├── realtime/
│   ├── historical/
│   ├── magnetometers/
│   ├── solarwind/
│   ├── indices/
│   ├── geology/
│   └── datacenters/
│
├── ingestion/
├── preprocessing/
├── analytics/
├── ml/
├── visualization/
├── alerts/
├── api/
├── configs/
├── notebooks/
├── docs/
└── tests/
```

------------------------------------------------------------------------

# Functional Modules

## 1. Data Ingestion

-   NOAA solar wind
-   Space weather indices
-   Ground magnetometers
-   Local magnetometer
-   Weather APIs (optional)

## 2. Signal Processing

-   FFT
-   PSD
-   Wavelet transform
-   dB/dt
-   Event detection
-   Cross correlation

## 3. Space Weather Severity

Inputs

-   IMF Bz
-   Solar wind speed
-   Density
-   Dynamic pressure
-   Kp
-   Dst
-   AE
-   SYM-H

Outputs

-   Storm severity
-   Expected disturbance

------------------------------------------------------------------------

## 4. Ground Magnetic Analysis

Compute

-   dB/dt
-   Rate of change
-   Spectral energy
-   Quiet-day baseline
-   Local anomalies

------------------------------------------------------------------------

## 5. Geoelectric Field Estimation

Estimate

-   Regional electric field
-   Conductivity influence
-   Latitude dependence

Initially use simplified published empirical models.

------------------------------------------------------------------------

## 6. Grid Stress Index

Not a full power-grid simulation.

Estimate:

-   Transmission exposure
-   Transformer stress likelihood
-   Regional grid stress
-   Confidence score

------------------------------------------------------------------------

## 7. Data Center Exposure

Metadata:

-   Latitude
-   Longitude
-   Grid region
-   Power redundancy (if public)
-   Facility size (where available)

Derived metrics:

-   Magnetic latitude
-   Historical storm exposure
-   Regional risk

------------------------------------------------------------------------

## 8. AI Risk Engine

Example score:

Risk = 0.35 × Storm Severity + 0.30 × Ground Activity + 0.20 × Grid
Stress + 0.15 × Facility Exposure

Weights should later be calibrated.

------------------------------------------------------------------------

## 9. Dashboard

Pages

-   Live Solar Wind
-   Ground Magnetometers
-   Risk Map
-   AI Facilities
-   Historical Replay
-   Alerts
-   Analytics

------------------------------------------------------------------------

# Data Sources

## Space Weather

-   NOAA SWPC
-   NASA CDAWeb
-   DSCOVR
-   ACE
-   SWFO-L1 (when available)

## Geomagnetic Indices

-   GFZ Potsdam Kp
-   WDC Kyoto (Dst)
-   SuperMAG
-   INTERMAGNET

## Ground Magnetometers

-   INTERMAGNET
-   USGS
-   SuperMAG
-   Local sensors

## Satellites

-   ESA Swarm
-   Parker Solar Probe
-   GOES
-   Aditya-L1 (selected analyses)

## Geology

-   USGS conductivity models
-   National geological surveys
-   Magnetotelluric datasets

## Data Centers

-   Public hyperscale campus information
-   Company sustainability reports
-   OpenStreetMap
-   Public GIS datasets

------------------------------------------------------------------------

# Machine Learning

Possible models

-   Random Forest
-   XGBoost
-   LightGBM
-   Temporal CNN
-   LSTM (optional)

Features

-   Solar wind
-   IMF
-   Kp
-   Dst
-   dB/dt
-   Latitude
-   Season
-   Local time

Outputs

-   Regional risk
-   Alert level
-   Confidence

------------------------------------------------------------------------

# Validation

Replay historical events

-   March 1989
-   October 2003
-   May 2024
-   Future storms

Compare

-   Forecast vs observed indices
-   Regional disturbances
-   Published reports

------------------------------------------------------------------------

# SBC Deployment

Target hardware

-   Raspberry Pi 5
-   NVMe SSD
-   UPS
-   Local magnetometer
-   LoRa/Wi-Fi

Software

-   Python
-   Docker
-   InfluxDB
-   Grafana
-   Streamlit
-   MQTT

------------------------------------------------------------------------

# Future Extensions

-   Multi-node sensor network
-   Citizen-science deployment
-   Local transformer monitoring
-   Real-time ML adaptation
-   Digital twin integration
-   Utility collaboration

------------------------------------------------------------------------

# Research Deliverables

1.  Open-source edge framework
2.  Risk-scoring methodology
3.  Validation dataset
4.  Dashboard
5.  Scientific publication
6.  Conference presentation

------------------------------------------------------------------------

# Expected Impact

## Scientific

-   Connect space weather and AI infrastructure.

## Engineering

-   Demonstrate continuous edge analytics on affordable hardware.

## Societal

-   Improve awareness and preparedness for geomagnetic hazards affecting
    critical digital infrastructure.

------------------------------------------------------------------------

# Important Limitations

-   Does **not** replace utility GIC simulators.
-   Risk scores are probabilistic and should be presented with
    uncertainty.
-   Facility-specific resilience (UPS, generators, transformer topology)
    is often proprietary and must be modeled using public assumptions or
    scenarios.
