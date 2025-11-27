import streamlit as st
import requests, io, zipfile, tempfile
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, shape
from math import radians, cos, sin, asin, sqrt
import folium
from streamlit_folium import st_folium
import altair as alt
import datetime
import os
from auth import check_login

st.set_page_config(layout="wide", page_title="Ookla Johor Explorer")

# LOGIN
if not check_login():
    st.stop()

# Optional simple auth via Streamlit secrets (not committed)
def check_auth():
    auth = {}
    try:
        auth = st.secrets["auth"]
    except Exception:
        pass
    if auth.get("enabled"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if u == auth.get("username") and p == auth.get("password"):
                st.session_state["logged_in"] = True
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")
        return st.session_state.get("logged_in", False)
    return True

if not check_auth():
    st.stop()

# ---------------------
# Constants / Config
# ---------------------
JOHOR_POLY = Polygon([(103.0,1.15),(104.5,1.15),(104.5,2.7),(103.0,2.7)])

OPERATORS = {
    "CelcomDigi": {"logo":"https://upload.wikimedia.org/wikipedia/commons/3/3b/CelcomDigi_logo.png","color":"#0033A0"},
    "Maxis": {"logo":"https://upload.wikimedia.org/wikipedia/commons/7/76/Maxis_logo.png","color":"#FF0000"},
    "U Mobile": {"logo":"https://upload.wikimedia.org/wikipedia/commons/0/06/U_Mobile_logo.png","color":"#00A859"},
    "Yes": {"logo":"https://upload.wikimedia.org/wikipedia/commons/6/64/Yes_logo.png","color":"#7B3F00"},
    "TM": {"logo":"https://upload.wikimedia.org/wikipedia/commons/6/6b/Telekom_Malaysia_logo.png","color":"#0070C0"}
}

# ---------------------
# Utility functions
# ---------------------
def quarter_start(year:int, q:int):
    return datetime.datetime(year, (q-1)*3+1, 1)

def get_tile_url(service_type: str, year: int, q: int) -> str:
    dt = quarter_start(year, q)
    base_url = "https://ookla-open-data.s3.amazonaws.com/shapefiles/performance"
    return (
        f"{base_url}/type={service_type}/year={dt:%Y}/quarter={q}/"
        f"{dt:%Y-%m-%d}_performance_{service_type}_tiles.zip"
    )

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2-lon1; dlat = lat2-lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))

def download_extract_johor_shapefile(url: str):
    """Download ZIP, extract Shapefile, filter Johor tiles, return GeoDataFrame."""
    r = requests.get(url, stream=True, timeout=60)
    if r.status_code != 200:
        st.error(f"Failed to download data. HTTP {r.status_code}")
        return None

    zip_bytes = io.BytesIO(r.content)
    with zipfile.ZipFile(zip_bytes) as z:
        with tempfile.TemporaryDirectory() as tmpdir:
            z.extractall(tmpdir)
            shp_files = [f for f in os.listdir(tmpdir) if f.endswith(".shp")]
            if not shp_files:
                st.error("No .shp file in ZIP")
                return None
            gdf = gpd.read_file(f"{tmpdir}/{shp_files[0]}")
            # Filter Johor
            gdf_johor = gdf[gdf.geometry.intersects(JOHOR_POLY)]
            gdf_johor["lon"] = gdf_johor.geometry.centroid.x
            gdf_johor["lat"] = gdf_johor.geometry.centroid.y
            return gdf_johor

# ---------------------
# Sidebar controls
# ---------------------
st.sidebar.header("Controls")
years = list(range(2019, 2026))
year = st.sidebar.selectbox("Year", years, index=years.index(2025))
quarter = st.sidebar.selectbox("Quarter", [1,2,3,4])
mode = st.sidebar.radio("Mode", ["Radius","Polygon"])
operator_filter = st.sidebar.multiselect("Filter operator", options=list(OPERATORS.keys()))
service = "mobile"
url = get_tile_url(service, year, quarter)
st.sidebar.markdown(f"**Data URL:** {url}")

load_button = st.sidebar.button("Stream & Load Johor Tiles")
df = None

if load_button or st.session_state.get("data_loaded", False):
    st.info("Streaming ZIP and extracting Johor tiles...")
    df = download_extract_johor_shapefile(url)
    if df is not None:
        st.success(f"Loaded {len(df)} Johor tiles")
        st.session_state.data_loaded = True

# ---------------------
# Analysis
# ---------------------
if df is not None:
    st.subheader("Ookla Johor Tile Analysis")

    if mode == "Radius":
        lat = st.number_input("Latitude", 1.4927, format="%.6f")
        lon = st.number_input("Longitude", 103.7414, format="%.6f")
        radius_km = st.number_input("Radius (km)", 1.0,50.0,5.0,1.0)
        df["dist_km"] = df.apply(lambda r: haversine(lon, lat, r["lon"], r["lat"]), axis=1)
        sel = df[df["dist_km"] <= radius_km]
        if operator_filter:
            sel = sel[sel[df.columns[0]].isin(operator_filter)]
        if sel.empty:
            st.info("No tiles within radius")
        else:
            summary = sel.groupby(sel.columns[0]).agg(
                count=('avg_d_kbps','count'),
                avg_download_kbps=('avg_d_kbps','mean'),
                avg_upload_kbps=('avg_u_kbps','mean'),
                avg_latency_ms=('avg_latency_ms','mean')
            ).reset_index()
            st.dataframe(summary.sort_values("avg_download_kbps", ascending=False))

            # Altair chart
            chart = alt.Chart(summary).mark_bar().encode(
                x="avg_download_kbps",
                y=alt.Y(sel.columns[0], sort="-x"),
                color=alt.Color(sel.columns[0], scale=alt.Scale(
                    domain=list(OPERATORS.keys()),
                    range=[v["color"] for v in OPERATORS.values()]
                ))
            )
            st.altair_chart(chart, use_container_width=True)

    else:
        m = folium.Map(location=[1.4927,103.7414], zoom_start=9)
        from folium.plugins import Draw
        Draw(export=True).add_to(m)
        for _, r in df.sample(min(2000,len(df))).iterrows():
            folium.CircleMarker(location=[r['lat'], r['lon']], radius=2, color="#3388ff", fill=True).add_to(m)
        map_data = st_folium(m, width=900, height=650, returned_objects=["all_drawings"])

        drawn = None
        if map_data and "all_drawings" in map_data:
            dd = map_data["all_drawings"]
            if isinstance(dd, list) and dd: drawn = dd[-1]
            elif isinstance(dd, dict) and dd: drawn = dd
        if drawn:
            geom = shape(drawn.get('geometry', {}))
            df["inside"] = df.apply(lambda r: geom.contains(Point(r['lon'], r['lat'])), axis=1)
            sel = df[df["inside"]]
            if operator_filter:
                sel = sel[sel[df.columns[0]].isin(operator_filter)]
            if sel.empty:
                st.info("No tiles inside polygon")
            else:
                summary = sel.groupby(sel.columns[0]).agg(
                    count=('avg_d_kbps','count'),
                    avg_download_kbps=('avg_d_kbps','mean')
                ).reset_index()
                st.dataframe(summary)

st.markdown("---")
st.caption("Data: Ookla Open Data — CC BY-NC-SA 4.0")
