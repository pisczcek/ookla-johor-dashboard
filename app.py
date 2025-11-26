import streamlit as st
import pandas as pd
import os
import subprocess

DATA_FILE = "data/ookla_johor.parquet"

st.set_page_config(layout="wide", page_title="Johor Ookla Explorer")

# ------------------------------------------------------------
# LOAD DATA OR AUTO-RUN LOADER
# ------------------------------------------------------------

def ensure_data():
    """Ensures parquet file exists. If missing, run loader."""
    if not os.path.exists(DATA_FILE):
        st.warning("Dataset missing. Running loader...")

        try:
            result = subprocess.run(
                ["python", "load_ookla.py"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                st.error("Loader failed:\n" + result.stderr)
                return None

        except Exception as e:
            st.error(f"Error running loader: {e}")
            return None

    try:
        df = pd.read_parquet(DATA_FILE)
        return df
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return None


df = ensure_data()
if df is None:
    st.stop()

# ------------------------------------------------------------
# APPLICATION UI
# ------------------------------------------------------------

st.title("📡 Ookla Johor Explorer (5km Radius Averages)")

st.write(f"Loaded **{len(df):,}** data points from Ookla Open Data.")

lat = st.number_input("Latitude", value=1.4927)
lon = st.number_input("Longitude", value=103.7414)
radius_km = st.slider("Radius (km)", 1, 20, 5)

# Haversine
from math import radians, sin, cos, asin, sqrt
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r

# Compute distances
df["dist_km"] = df.apply(lambda r: haversine(lon, lat, r["lon"], r["lat"]), axis=1)
selected = df[df["dist_km"] <= radius_km]

st.subheader(f"📍 Average Speed Within {radius_km} km")

if selected.empty:
    st.warning("No samples inside radius.")
    st.stop()

summary = selected.groupby("provider").agg(
    count=("download", "count"),
    avg_download=("download", "mean"),
    avg_upload=("upload", "mean"),
    avg_latency=("latency", "mean")
).reset_index()

st.dataframe(summary)

st.write("---")
st.caption("Built using Ookla Open Data | Streamlit Cloud Ready")
