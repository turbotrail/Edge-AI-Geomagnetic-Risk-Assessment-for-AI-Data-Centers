import streamlit as st
import pandas as pd
import numpy as np
import math
import requests
from influxdb_client import InfluxDBClient
import yaml
import os
import sys

# Ensure modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analytics.datacenter_exposure import DataCenterExposure
from analytics.grid_stress import GridStressIndex
from ml.risk_model import RiskEngine
from ingestion.historical_replay import HistoricalReplay
import json

st.set_page_config(
    page_title="Geomagnetic Risk Dashboard",
    page_icon="🌍",
    layout="wide",
)

# Load configuration
@st.cache_resource
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Initialize Analytics Engines
exposure_engine = DataCenterExposure(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.yaml'))
stress_engine = GridStressIndex()

@st.cache_resource
def get_influx_client():
    db_config = config['database']['influxdb']
    try:
        client = InfluxDBClient(url=db_config['url'], token=db_config['token'], org=db_config['org'])
        return client, db_config['bucket']
    except Exception as e:
        return None, None

influx_client, bucket = get_influx_client()

def fetch_latest_metric(client, bucket_name, measurement, field, source=None):
    if not client: return 0.0
    
    source_filter = f'|> filter(fn: (r) => r["source"] == "{source}")' if source else ""
    
    query = f'''
        from(bucket: "{bucket_name}")
        |> range(start: -30d)
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        |> filter(fn: (r) => r["_field"] == "{field}")
        {source_filter}
        |> last()
    '''
    try:
        result = client.query_api().query(query)
        if result and len(result) > 0 and len(result[0].records) > 0:
            return result[0].records[0].get_value()
    except Exception as e:
        import logging
        logging.error(f"InfluxDB Query Error: {e}")
    return 0.0

def fetch_historical_series(client, bucket_name, measurement, field, source=None, station=None):
    if not client: return pd.DataFrame(columns=['_time', field]).set_index('_time')
    
    filters = []
    if source:
        filters.append(f'|> filter(fn: (r) => r["source"] == "{source}")')
    if station:
        filters.append(f'|> filter(fn: (r) => r["station"] == "{station}")')
        
    filter_str = "\n        ".join(filters)
        
    query = f'''
        from(bucket: "{bucket_name}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        |> filter(fn: (r) => r["_field"] == "{field}")
        {filter_str}
        |> drop(columns: ["_start", "_stop", "_measurement", "_field", "source", "host", "station", "network"])
    '''
    try:
        df = client.query_api().query_data_frame(query)
        if type(df) is list:
            if len(df) == 0: return pd.DataFrame()
            df = pd.concat(df)
        if not df.empty:
            df['_time'] = pd.to_datetime(df['_time'])
            df.set_index('_time', inplace=True)
            df.rename(columns={'_value': field}, inplace=True)
            df = df[[field]]
            
            # Streamlit cannot draw a line with only 1 point. 
            # For low-frequency data (like Kp and SFU), duplicate the last known reading to 'now' to draw a flat line.
            if len(df) == 1:
                last_row = df.iloc[-1:].copy()
                last_row.index = [pd.Timestamp.utcnow()]
                df = pd.concat([df, last_row])
                
            return df
    except Exception as e:
        import logging
        logging.error(f"Error fetching historical series for {field}: {e}")
    return pd.DataFrame()

st.title("Edge AI Geomagnetic Risk Assessment")
st.markdown("Monitoring space weather impact on AI Data Centers")

# Sidebar
with st.sidebar:
    st.header("System Status")
    st.success("Edge Node: ONLINE (Arduino Uno Q)")
    if influx_client:
        st.success("Database: CONNECTED (InfluxDB)")
    else:
        st.error("Database: DISCONNECTED")
    
    st.divider()
    view = st.radio("Select View", ["Live Dashboard", "Data Center Risk Map", "Alerts", "Analytics"])

# Determine Data Source
data_source = "noaa_swpc"

# Fetch data based on source
live_kp = fetch_latest_metric(influx_client, bucket, "geomagnetic_indices", "kp_index", data_source)
live_sw_speed = fetch_latest_metric(influx_client, bucket, "solar_wind", "speed", data_source)
live_bt = fetch_latest_metric(influx_client, bucket, "solar_wind", "bt", data_source)
live_bz = fetch_latest_metric(influx_client, bucket, "solar_wind", "bz", data_source)
live_f107 = fetch_latest_metric(influx_client, bucket, "solar_flux", "f107_flux", data_source)

# Fallback for display if db is empty
display_kp = f"{live_kp:.1f}" if live_kp > 0 else "4.3 (Mock)"
display_sw = f"{live_sw_speed:.0f} km/s" if live_sw_speed > 0 else "450 km/s (Mock)"
display_imf = f"{live_bt:.1f} / {live_bz:.1f} nT" if live_bt > 0 else "5.0 / -2.0 nT (Mock)"
display_f107 = f"{live_f107:.0f} sfu" if live_f107 > 0 else "150 sfu (Mock)"

def render_kp_blocks(df_kp):
    if df_kp.empty:
        st.info("No historical K-index data available")
        return
        
    now = pd.Timestamp.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Ensure DatetimeIndex with UTC to avoid pandas timezone mixup issues
    df_kp.index = pd.to_datetime(df_kp.index, utc=True)
    
    df_today = df_kp[df_kp.index >= start_of_day]
    if df_today.empty:
        st.info("No Kp data available for today yet")
        return
        
    df_3h = df_today.resample('3h').max()
    
    html = '<div style="display: flex; gap: 4px; overflow-x: auto; margin-bottom: 20px;">'
    for dt, row in df_3h.iterrows():
        val = row['kp_index']
        if pd.isna(val):
            val_str = "-"
            color = "#555555"
        else:
            val_str = f"{val:.1f}"
            if val < 5: color = "#92d050"
            elif val < 6: color = "#ffff00"
            elif val < 7: color = "#ffc000"
            elif val < 8: color = "#ff9900"
            elif val < 9: color = "#ff0000"
            else: color = "#c00000"
            
        time_label = f"{dt.hour:02d}Z"
        text_color = "black" if color in ["#ffff00", "#ffc000", "#92d050"] else "white"
        
        block = f'''<div style="background-color: {color}; color: {text_color}; padding: 10px; border-radius: 4px; min-width: 60px; text-align: center;">
    <div style="font-size: 0.8em; opacity: 0.8;">{time_label}</div>
    <div style="font-weight: bold; font-size: 1.1em;">{val_str}</div>
</div>'''
        html += block
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_all_stations():
    stations = []
    # Intermagnet Mock Stations
    intermagnet = [
        {"id": "ESK", "lat": 55.3, "lon": -3.2, "network": "INTERMAGNET"},
        {"id": "HAD", "lat": 51.0, "lon": -4.5, "network": "INTERMAGNET"},
        {"id": "LER", "lat": 60.1, "lon": -1.2, "network": "INTERMAGNET"},
        {"id": "NGK", "lat": 52.1, "lon": 12.7, "network": "INTERMAGNET"},
        {"id": "BEL", "lat": 51.8, "lon": 20.8, "network": "INTERMAGNET"}
    ]
    stations.extend(intermagnet)
    
    try:
        url = "https://geomag.usgs.gov/ws/observatories/"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            features = data.get('features', [])
            for f in features:
                station_id = f.get('id')
                geom = f.get('geometry')
                if not geom:
                    continue
                coords = geom.get('coordinates', [])
                if station_id and len(coords) >= 2 and coords[0] is not None and coords[1] is not None:
                    lon, lat = coords[0], coords[1]
                    stations.append({"id": station_id, "lat": lat, "lon": lon, "network": "USGS"})
    except Exception as e:
        import logging
        logging.error(f"Failed to fetch USGS observatories for mapping: {e}")
        
    return stations

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_closest_station(dc_lat, dc_lon, influx_client, bucket):
    stations = load_all_stations()
    if not stations: return "BOU"
    
    # Query InfluxDB for stations with recent data
    query = f'''
        from(bucket: "{bucket}")
        |> range(start: -30m)
        |> filter(fn: (r) => r["_measurement"] == "magnetometer")
        |> filter(fn: (r) => r["_field"] == "db_dt")
        |> keep(columns: ["station"])
        |> distinct(column: "station")
    '''
    try:
        tables = influx_client.query_api().query(query)
        active_stations = set()
        for table in tables:
            for record in table.records:
                active_stations.add(record.values.get("_value"))
    except Exception as e:
        import logging
        logging.error(f"Failed to query active stations: {e}")
        active_stations = None
    
    closest_usgs = None
    min_dist_usgs = float('inf')
    
    closest_im = None
    min_dist_im = float('inf')
    
    for s in stations:
        if active_stations is not None and s['id'] not in active_stations:
            continue
            
        if s['lat'] is not None and s['lon'] is not None:
            dist = haversine(dc_lat, dc_lon, s['lat'], s['lon'])
            if s['network'] == 'USGS':
                if dist < min_dist_usgs:
                    min_dist_usgs = dist
                    closest_usgs = s['id']
            else:
                if dist < min_dist_im:
                    min_dist_im = dist
                    closest_im = s['id']
                    
    # Prioritize USGS if within reasonable continental distance (e.g., 4000 km)
    if closest_usgs and min_dist_usgs <= 4000:
        return closest_usgs
    elif closest_im:
        return closest_im
    return "BOU"

if view == "Live Dashboard":
    st.header("Live Geomagnetic Conditions")
    
    # Get all datacenters
    datacenters = exposure_engine.get_all_datacenters()
    dc_names = [dc["name"] for dc in datacenters]
    options = ["Global Baseline (50° Lat)"] + dc_names
    selected_option = st.selectbox("Select Target Grid / Data Center", options)
    
    if selected_option == "Global Baseline (50° Lat)":
        target_lat = 50.0
        target_lon = -105.2 # Boulder longitude
        stress_label = f"Grid Stress Index (BOU Baseline)"
    else:
        dc = next(dc for dc in datacenters if dc["name"] == selected_option)
        target_lat = dc["lat"]
        target_lon = dc["lon"]
        stress_label = f"Grid Stress ({dc['grid_region']})"
        
    target_station = get_closest_station(target_lat, target_lon, influx_client, bucket)
        
        # Fetch real magnetometer data for this station
    df_mag = fetch_historical_series(influx_client, bucket, "magnetometer", "db_dt", station=target_station)
    if not df_mag.empty:
        live_db_dt_series = df_mag['db_dt'].values
        calculated_stress = stress_engine.calculate_index_from_dbdt(live_db_dt_series, target_lat, bt=live_bt, bz=live_bz)
        ground_activity = min(abs(live_db_dt_series[-1]) / 10.0, 1.0)
    else:
        calculated_stress = 0.0
        ground_activity = 0.0

    # Calculate ML Risk Score for the selected location
    risk_engine = RiskEngine(model_path=os.path.join(os.path.dirname(__file__), '..', 'ml', 'models', 'risk_model.joblib'))
    storm_severity = min(live_kp / 9.0, 1.0) if live_kp > 0 else 0.5
    
    if selected_option == "Global Baseline (50° Lat)":
        exposure = (calculated_stress + (50.0/90.0)**2) * 0.5
    else:
        exposure = exposure_engine.calculate_facility_exposure(dc["id"], calculated_stress)
        
    ml_risk_score = risk_engine.calculate_risk_score(storm_severity, ground_activity, calculated_stress, exposure)
    alert_level = risk_engine.get_alert_level(ml_risk_score)
    
    # Display an eye-catching AI alert banner based on the live Neural Network evaluation
    if alert_level == "CRITICAL":
        st.error(f"🚨 **CRITICAL GEOMAGNETIC ALERT** — Neural Network Risk Score: {ml_risk_score:.4f} 🚨")
    elif alert_level == "HIGH":
        st.warning(f"⚠️ **HIGH RISK** — Neural Network Risk Score: {ml_risk_score:.4f} ⚠️")
    elif alert_level == "MODERATE":
        st.info(f"🟡 **MODERATE RISK** — Neural Network Risk Score: {ml_risk_score:.4f}")
    else:
        st.success(f"✅ **SYSTEM NOMINAL** — Neural Network Risk Score: {ml_risk_score:.4f}")

    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Current Kp Index", display_kp)
    with col2:
        st.metric("Solar Wind Speed", display_sw)
    with col3:
        st.metric("IMF (Bt / Bz)", display_imf)
    with col4:
        st.metric("F10.7 Solar Flux", display_f107)
    with col5:
        st.metric(stress_label, f"{calculated_stress:.2f}/1.00")
        
    st.divider()
    st.subheader("Geomagnetic Activity Trends (Last 24 Hours)")
    
    # Fetch historical data
    df_kp = fetch_historical_series(influx_client, bucket, "geomagnetic_indices", "kp_index", data_source)
    df_sw = fetch_historical_series(influx_client, bucket, "solar_wind", "speed", data_source)
    
    st.markdown("**Planetary K-index (Kp) - Today's 3-Hour Blocks**")
    render_kp_blocks(df_kp)
    
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown(f"**Local Ground Magnetic Disturbance - {target_station} (dB/dt in nT/min)**")
        if not df_mag.empty:
            st.line_chart(df_mag, color="#8800ff")
        else:
            st.info(f"No magnetometer data available for station {target_station}")
            
    with chart_col2:
        st.markdown("**Solar Wind Speed (km/s)**")
        if not df_sw.empty:
            st.line_chart(df_sw, color="#00aaff")
        else:
            st.info("No historical Solar Wind data available")

elif view == "Data Center Risk Map":
    st.header("AI Data Center Risk Exposure")
    st.write("Regional risk assessment based on magnetic latitude, ground geology, and grid stress.")
    
    # Instantiate Risk Engine for ML calculations
    risk_engine = RiskEngine(model_path=os.path.join(os.path.dirname(__file__), '..', 'ml', 'models', 'risk_model.joblib'))
    
    # Calculate risk for all DCs
    map_data = []
    for dc in exposure_engine.get_all_datacenters():
        station = get_closest_station(dc["lat"], dc["lon"], influx_client, bucket)
        df_dc_mag = fetch_historical_series(influx_client, bucket, "magnetometer", "db_dt", station=station)
        
        if not df_dc_mag.empty:
            local_stress = stress_engine.calculate_index_from_dbdt(df_dc_mag['db_dt'].values, dc["lat"], bt=live_bt, bz=live_bz)
            local_ground_activity = min(abs(df_dc_mag['db_dt'].values[-1]) / 10.0, 1.0)
        else:
            local_stress = 0.0
            local_ground_activity = 0.0
            
        exposure = exposure_engine.calculate_facility_exposure(dc["id"], local_stress)
        storm_severity = min(live_kp / 9.0, 1.0) if live_kp > 0 else 0.5
        
        # Feed all 4 features into the ML Model for this specific data center
        ml_risk_score = risk_engine.calculate_risk_score(storm_severity, local_ground_activity, local_stress, exposure)
        alert_level = risk_engine.get_alert_level(ml_risk_score)
        
        ml_risk_score = round(ml_risk_score, 4)
        
        # Color coding: Green (Low), Yellow (Moderate), Orange (High), Red (Critical)
        if alert_level == "CRITICAL":
            color = "#FF0000"
        elif alert_level == "HIGH":
            color = "#FFA500"
        elif alert_level == "MODERATE":
            color = "#FFFF00"
        else:
            color = "#00FF00"
        
        map_data.append({
            "name": dc["name"],
            "lat": dc["lat"],
            "lon": dc["lon"],
            "risk": ml_risk_score,
            "alert": alert_level,
            "color": color
        })
        
    df_map = pd.DataFrame(map_data)
    
    import pydeck as pdk
    
    def hex_to_rgb(h):
        h = h.lstrip('#')
        return [int(h[i:i+2], 16) for i in (0, 2, 4)] + [200]
        
    df_map['color_rgb'] = df_map['color'].apply(hex_to_rgb)
    
    view_state = pdk.ViewState(
        latitude=35.0,
        longitude=0.0,
        zoom=1.2,
        min_zoom=1.2,  # Prevents zooming out far enough to see map repetition
        max_zoom=12,
        pitch=45       # Gives a premium 3D tilted aesthetic
    )
    
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_map,
        get_position='[lon, lat]',
        get_color='color_rgb',
        get_radius=50000,  # 50km radius for much smaller, cleaner dots
        pickable=True,
        stroked=True,
        filled=True,
        radius_scale=1,
        radius_min_pixels=6,
        radius_max_pixels=20,
        line_width_min_pixels=1,
    )
    
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style='dark',
        tooltip={"text": "{name}\nRisk Score: {risk}\nAlert Level: {alert}"}
    )
    
    st.pydeck_chart(deck, use_container_width=True)
    
    st.subheader("Facility Breakdown")
    # Display the ML risk and the resulting alert level
    st.dataframe(df_map[["name", "lat", "lon", "risk", "alert"]])

elif view == "Alerts":
    st.header("Recent System Alerts")
    st.write("A log of recent risk assessments and triggered alerts.")
    
    alerts_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'realtime', 'alerts', 'active_alerts.jsonl')
    alerts_data = []
    
    if os.path.exists(alerts_file):
        with open(alerts_file, 'r') as f:
            for line in reversed(f.readlines()): # Show newest first
                try:
                    alerts_data.append(json.loads(line.strip()))
                except Exception:
                    pass
    
    if alerts_data:
        df_alerts = pd.DataFrame(alerts_data)
        # Reorder columns and format
        if not df_alerts.empty:
            df_alerts['timestamp'] = pd.to_datetime(df_alerts['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")
            # Style based on level
            def color_level(val):
                color = 'red' if val == 'CRITICAL' else 'orange' if val == 'HIGH' else 'yellow' if val == 'MODERATE' else 'green'
                return f'color: {color}'
            
            st.dataframe(
                df_alerts[['timestamp', 'level', 'risk_score', 'context']].style.map(color_level, subset=['level']),
                use_container_width=True
            )
    else:
        st.info("No active alerts found in the system log.")

elif view == "Analytics":
    st.header("Edge AI Risk Analytics")
    st.markdown("This section utilizes a **unique, lightweight Neural Network (MLP)** specifically tailored to run efficiently on 2GB RAM edge devices (e.g., Raspberry Pi 4/5).")
    
    risk_engine = RiskEngine(model_path=os.path.join(os.path.dirname(__file__), '..', 'ml', 'models', 'risk_model.joblib'))
    if not getattr(risk_engine, 'is_trained', False):
        st.warning("The Edge ML Model is currently untrained or using fallback heuristic rules. Let's initialize and train the edge-optimized model.")
        if st.button("Initialize & Train Edge Model"):
            with st.spinner("Training lightweight Neural Network on edge..."):
                risk_engine.train_model()
            st.success("Edge Model Trained Successfully! Refreshing analytics...")
            st.rerun()
            
    st.subheader("Live Real-time Model Prediction")
    
    # Calculate features for Live Prediction
    # We use live_kp mapped to a 0-1 range roughly, or just use live values
    # The dummy model expects features in some range. Our dummy features were 0-1 range.
    # Let's normalize the live values roughly to 0-1 for the sake of the dummy model.
    storm_severity = min(live_kp / 9.0, 1.0) if live_kp > 0 else 0.5
    ground_activity = min(abs(live_db_dt_series[-1] if 'live_db_dt_series' in locals() and len(live_db_dt_series) > 0 else 0.0) / 10.0, 1.0)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Feature: Storm Severity", f"{storm_severity:.2f}")
    col2.metric("Feature: Ground Activity", f"{ground_activity:.2f}")
    
    # Assume global baseline for live analytics overview
    grid_stress = min(stress_engine.calculate_index_from_dbdt(np.array([0]), 50.0, bt=live_bt, bz=live_bz), 1.0)
    col3.metric("Feature: Grid Stress", f"{grid_stress:.2f}")
    
    facility_exposure = 0.5 # Mean exposure
    col4.metric("Feature: Facility Exposure", f"{facility_exposure:.2f}")
    
    live_risk = risk_engine.calculate_risk_score(storm_severity, ground_activity, grid_stress, facility_exposure)
    live_alert = risk_engine.get_alert_level(live_risk)
    
    st.divider()
    
    score_col, alert_col = st.columns(2)
    with score_col:
        st.markdown(f"### Current Aggregated Risk Score: `{live_risk:.3f}`")
        st.progress(live_risk)
    
    with alert_col:
        st.markdown(f"### System State: **{live_alert}**")
        if live_alert == "CRITICAL":
            st.error("Immediate Mitigation Required!")
        elif live_alert == "HIGH":
            st.warning("Monitor Data Center Power Stability")
        elif live_alert == "MODERATE":
            st.info("Elevated Activity - Normal Operations")
        else:
            st.success("Nominal Space Weather Conditions")



