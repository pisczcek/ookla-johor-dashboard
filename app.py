import streamlit as st
import pandas as pd
import pydeck as pdk
import os

st.set_page_config(page_title="Ookla Johor Dashboard", layout="wide")

DATA_PATH = "data/ookla_johor.parquet"

# ------------------------------------------------------------------
# Load dataset
# ------------------------------------------------------------------
@st.cache_data
def load_data():
    if not os.path.exists(DATA_PATH):
        st.error("Dataset missing. Please run load_ookla.py first.")
        st.stop()
    return pd.read_parquet(DATA_PATH)

st.title("📡 Johor Internet Performance – Ookla Open Data")

# Load data
df = load_data()

# Expected columns from Ookla tile data
# avg_d_kbps, avg_u_kbps, avg_lat_ms, tile_x, tile_y, tile_z, quadkey, provider
if 'avg_d_kbps' not in df.columns:
    st.error("Parquet file does not match Ookla schema. Check loader.")
    st.stop()

# ------------------------------------------------------------------
# Sidebar filters
# ------------------------------------------------------------------
st.sidebar.header("Filters")

provider_list = ["All"] + sorted(df["provider"].dropna().unique().tolist())
provider = st.sidebar.selectbox("Provider", provider_list)

if provider != "All":
    df = df[df["provider"] == provider]

# ------------------------------------------------------------------
# Map settings
# ------------------------------------------------------------------
st.subheader("📍 Coverage Map")

df = df.rename(columns={"avg_d_kbps": "download", "avg_u_kbps": "upload"})

# Convert speed to Mbps
df["download_mbps"] = df["download"] / 1000
df["upload_mbps"] = df["upload"] / 1000

# pydeck layer
layer = pdk.Layer(
    "ScatterplotLayer",
    df,
    pickable=True,
    opacity=0.6,
    get_position=["lon", "lat"],
    get_radius=300,
    get_fill_color="[255 - download_mbps * 5, download_mbps * 5, 100]",
)

view_state = pdk.ViewState(
    latitude=1.48,
    longitude=103.76,
    zoom=9,
)

st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))

# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------
st.subheader("📊 Statistics")

col1, col2, col3 = st.columns(3)
col1.metric("Avg Download (Mbps)", f"{df['download_mbps'].mean():.2f}")
col2.metric("Avg Upload (Mbps)", f"{df['upload_mbps'].mean():.2f}")
col3.metric("Avg Latency (ms)", f"{df['avg_lat_ms'].mean():.2f}")

# ------------------------------------------------------------------
# Raw data
# ------------------------------------------------------------------
st.subheader("📄 Raw Data")
st.dataframe(df.head(500))
