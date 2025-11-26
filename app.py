import streamlit as st
import pandas as pd
import json
import os
import subprocess
from shapely.geometry import shape, Point
import numpy as np
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt

DATA_PATH = "data/ookla_johor.geojson"
JOHOR_CENTER = [1.4927, 103.7414]  # Johor Bahru

# ----------------------------
# Helpers
# ----------------------------

def run_loader_if_missing():
    """Run load_ookla.py if data file does not exist."""
    if not os.path.exists(DATA_PATH):
        st.warning("Data not found. Running loader...")
        try:
            result = subprocess.run(["python", "load_ookla.py"], capture_output=True, text=True)
            if result.returncode != 0:
                st.error("Failed to run loader:")
                st.code(result.stderr)
                return False
        except Exception as e:
            st.error(f"Loader execution error: {e}")
            return False
    return True


def load_geojson(path):
    """Load GeoJSON into Pandas DataFrame (no GeoPandas)."""
    with open(path) as f:
        data = json.load(f)

    rows = []
    for feat in data["features"]:
        geom = shape(feat["geometry"])
        props = feat["properties"]
        props["geometry"] = geom
        rows.append(props)

    df = pd.DataFrame(rows)
    df["lon"] = df["geometry"].apply(lambda g: g.x)
    df["lat"] = df["geometry"].apply(lambda g: g.y)

    return df


def haversine(lon1, lat1, lon2, lat2):
    """Fast distance (km)."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 2 * asin(sqrt(a)) * 6371


def compute_radius_avg(df, center, radius_km=5.0):
    cx, cy = center
    coords = df[["lon", "lat"]].values

    dists = np.array([haversine(cx, cy, x, y) for x, y in coords])
    df_sel = df[dists <= radius_km]

    if df_sel.empty:
        return pd.DataFrame()

    grouped = df_sel.groupby("provider").agg(
        count=("download_mean", "count"),
        download_mean=("download_mean", "mean"),
        upload_mean=("upload_mean", "mean"),
        latency_mean=("latency_mean", "mean"),
    ).reset_index()

    return grouped


def compute_polygon_avg(df, polygon_geom):
    df_sel = df[df["geometry"].apply(lambda g: polygon_geom.contains(g))]
    if df_sel.empty:
        return pd.DataFrame()

    grouped = df_sel.groupby("provider").agg(
        count=("download_mean", "count"),
        download_mean=("download_mean", "mean"),
        upload_mean=("upload_mean", "mean"),
        latency_mean=("latency_mean", "mean"),
    ).reset_index()

    return grouped


# -------------------------------------
# Streamlit UI
# -------------------------------------
st.set_page_config(layout="wide", page_title="Ookla Johor Explorer")
st.title("📡 Ookla Johor — 5km / Polygon Averages")

# Load data
if not run_loader_if_missing():
    st.stop()

try:
    df = load_geojson(DATA_PATH)
except Exception as e:
    st.error(f"Failed to load GeoJSON: {e}")
    st.stop()

left, right = st.columns([1, 2])

# LEFT PANEL
with left:
    st.subheader("Search / Controls")

    query = st.text_input("Search place (Nominatim)", "Johor Bahru")
    if st.button("Search"):
        geolocator = Nominatim(user_agent="ookla-johor-app")
        try:
            loc = geolocator.geocode(query, timeout=10)
            if loc:
                st.session_state["search_point"] = (loc.longitude, loc.latitude)
                st.success(f"Found: {loc.address}")
            else:
                st.error("No result.")
        except Exception as e:
            st.error(f"Geocoding error: {e}")

    radius_km = st.number_input("Radius (km)", min_value=1.0, max_value=50.0, value=5.0)

    providers = sorted(df["provider"].dropna().unique().tolist())
    provider_filter = st.multiselect("Filter provider", providers)


# RIGHT PANEL
with right:
    st.subheader("Map")

    m = folium.Map(location=JOHOR_CENTER, zoom_start=9)

    # Plot sample points (lightweight)
    sample = df.sample(min(len(df), 3000))
    for _, row in sample.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=2,
            color="blue",
            fill=True,
            fill_opacity=0.6,
        ).add_to(m)

    # Add draw tool
    from folium.plugins import Draw

    Draw(export=True).add_to(m)

    # Place search marker
    if "search_point" in st.session_state:
        lx, ly = st.session_state["search_point"]
        folium.Marker([ly, lx], icon=folium.Icon(color="red")).add_to(m)

    map_data = st_folium(m, width=900, height=650, returned_objects=["all_drawings"])

# ----------------------------------------
# Process map interactions
# ----------------------------------------
drawn = None
if map_data and "all_drawings" in map_data:
    drawings = map_data["all_drawings"]
    if isinstance(drawings, list) and len(drawings):
        drawn = drawings[-1]

point = None

if drawn:
    geom = shape(drawn["geometry"])
    if geom.geom_type == "Point":
        point = (geom.x, geom.y)
    else:
        poly = geom
        poly_avg = compute_polygon_avg(df, poly)
        st.subheader("Polygon Average")
        if poly_avg.empty:
            st.info("No points inside polygon.")
        else:
            if provider_filter:
                poly_avg = poly_avg[poly_avg["provider"].isin(provider_filter)]
            st.dataframe(poly_avg)
else:
    if "search_point" in st.session_state:
        point = st.session_state["search_point"]

# Radius search
if point:
    rad_avg = compute_radius_avg(df, point, radius_km)
    st.subheader(f"Radius {radius_km} km Average")
    if rad_avg.empty:
        st.info("No points in radius.")
    else:
        if provider_filter:
            rad_avg = rad_avg[rad_avg["provider"].isin(provider_filter)]
        st.dataframe(rad_avg)

st.markdown("---")
st.caption("Data source: Ookla Open Data")
