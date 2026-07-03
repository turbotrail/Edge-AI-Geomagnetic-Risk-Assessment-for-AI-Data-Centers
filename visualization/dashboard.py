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
from ingestion.historical_replay import HistoricalReplay

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
    view = st.radio("Select View", ["Live Dashboard", "Data Center Risk Map"])

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
    else:
        calculated_stress = 0.0

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
    
    # Calculate risk for all DCs
    map_data = []
    for dc in exposure_engine.get_all_datacenters():
        station = get_closest_station(dc["lat"], dc["lon"], influx_client, bucket)
        df_dc_mag = fetch_historical_series(influx_client, bucket, "magnetometer", "db_dt", station=station)
        
        if not df_dc_mag.empty:
            local_stress = stress_engine.calculate_index_from_dbdt(df_dc_mag['db_dt'].values, dc["lat"], bt=live_bt, bz=live_bz)
        else:
            local_stress = 0.0
            
        exposure = exposure_engine.calculate_facility_exposure(dc["id"], local_stress)
        
        # Color coding: Green (Low), Yellow (Moderate), Red (High)
        color = "#00FF00" if exposure < 0.3 else "#FFFF00" if exposure < 0.7 else "#FF0000"
        
        map_data.append({
            "name": dc["name"],
            "lat": dc["lat"],
            "lon": dc["lon"],
            "risk": exposure,
            "color": color
        })
        
    df_map = pd.DataFrame(map_data)
    
    st.map(df_map, color="color", size=5000)
    
    st.subheader("Facility Breakdown")
    st.dataframe(df_map[["name", "lat", "lon", "risk"]])


