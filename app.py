import streamlit as st
import pandas as pd
import os
import subprocess
import json
from math import radians, sin, cos, asin, sqrt
from shapely.geometry import shape, Point, Polygon
from streamlit_folium import st_folium
import folium
import altair as alt

# Config
DATA_FILE = "data/ookla_johor.parquet"
OPERATORS_FILE = "assets/operators.json"

st.set_page_config(layout="wide", page_title="Ookla Johor Explorer (Upgraded)")

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

st.title("📡 Ookla Johor Explorer — Upgraded")

# Ensure data exists (auto-run loader if missing)
def ensure_data():
    if not os.path.exists(DATA_FILE):
        st.info("Dataset missing. Running loader (this may take 30-90s)...")
        try:
            res = subprocess.run(["python", "load_ookla.py"], capture_output=True, text=True)
            if res.returncode != 0:
                st.error("Loader failed:\n" + res.stderr)
                return None
        except Exception as e:
            st.error("Failed to run loader: " + str(e))
            return None
    try:
        df = pd.read_parquet(DATA_FILE)
        return df
    except Exception as e:
        st.error("Failed to load parquet: " + str(e))
        return None

df = ensure_data()
if df is None:
    st.stop()

# Load operator metadata (colors/logos)
if os.path.exists(OPERATORS_FILE):
    with open(OPERATORS_FILE) as f:
        operators_meta = json.load(f)
else:
    operators_meta = {}

st.sidebar.header("Controls")
mode = st.sidebar.radio("Mode", ["Radius (5km default)", "Polygon (draw)"])
provider_filter = st.sidebar.multiselect("Filter operators (optional)", options=sorted(df['provider_name'].dropna().unique().tolist()))

# helper distance
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c

# compute provider summary function
def summarize(df_sel):
    if df_sel.empty:
        return pd.DataFrame()
    grp = df_sel.groupby("provider_name").agg(
        count=("avg_d_kbps","count"),
        avg_download_kbps=("avg_d_kbps","mean"),
        avg_upload_kbps=("avg_u_kbps","mean"),
        avg_latency_ms=("avg_latency_ms","mean")
    ).reset_index()
    # add metadata
    grp["color"] = grp["provider_name"].apply(lambda x: operators_meta.get(x, {}).get("color","#777777"))
    grp["logo"] = grp["provider_name"].apply(lambda x: operators_meta.get(x, {}).get("logo",""))
    return grp

# UI layout
left, right = st.columns([1,2])

if mode.startswith("Radius"):
    with left:
        lat = st.number_input("Latitude", value=1.4927, format="%.6f")
        lon = st.number_input("Longitude", value=103.7414, format="%.6f")
        radius_km = st.number_input("Radius (km)", min_value=1.0, max_value=20.0, value=5.0, step=1.0)
        if st.button("Compute Radius Averages"):
            df["dist_km"] = df.apply(lambda r: haversine(lon, lat, r["tile_lon"], r["tile_lat"]), axis=1)
            sel = df[df["dist_km"] <= radius_km]
            if provider_filter:
                sel = sel[sel["provider_name"].isin(provider_filter)]
            summary = summarize(sel)
            if summary.empty:
                st.info("No samples found in this radius.")
            else:
                st.subheader("Operator Averages in Radius")
                # show chart
                bars = alt.Chart(summary).mark_bar().encode(
                    x=alt.X("avg_download_kbps:Q", title="Avg download (kbps)"),
                    y=alt.Y("provider_name:N", sort="-x", title=None),
                    color=alt.Color("provider_name:N", scale=None)
                )
                st.altair_chart(bars, use_container_width=True)
                # table with logos/colors
                def render_row(r):
                    logo = r['logo'] or ''
                    color = r['color'] or '#777777'
                    return f"{logo} **{r['provider_name']}** — {r['avg_download_kbps']:.0f} kbps (n={int(r['count'])})"
                for _, row in summary.iterrows():
                    st.markdown(render_row(row))
    with right:
        st.map(df.sample(min(2000, len(df)))[["tile_lat","tile_lon"]].rename(columns={"tile_lat":"lat","tile_lon":"lon"}))
else:
    # polygon mode using folium draw and streamlit_folium
    with right:
        m = folium.Map(location=[1.4927,103.7414], zoom_start=9)
        from folium.plugins import Draw
        Draw(export=True).add_to(m)
        for _, r in df.sample(min(2000, len(df))).iterrows():
            folium.CircleMarker(location=[r["tile_lat"], r["tile_lon"]], radius=2, color="#3388ff", fill=True).add_to(m)
        map_data = st_folium(m, width=900, height=650, returned_objects=["all_drawings"])
    # parse polygon
    drawn = None
    if map_data and "all_drawings" in map_data:
        drawings = map_data["all_drawings"]
        if isinstance(drawings, list) and drawings:
            drawn = drawings[-1]
        elif isinstance(drawings, dict) and drawings:
            drawn = drawings
    if drawn:
        try:
            geom = shape(drawn.get("geometry", {}))
            if geom.geom_type in ("Polygon","MultiPolygon"):
                poly = geom
                # select points within polygon
                df_pts = df.copy()
                df_pts["inside"] = df_pts.apply(lambda r: poly.contains(Point(r["tile_lon"], r["tile_lat"])), axis=1)
                sel = df_pts[df_pts["inside"]]
                if provider_filter:
                    sel = sel[sel["provider_name"].isin(provider_filter)]
                summary = summarize(sel)
                if summary.empty:
                    st.info("No data in polygon.")
                else:
                    st.subheader("Operator Averages in Polygon")
                    st.dataframe(summary)
            else:
                st.info("Draw a polygon to aggregate.")
        except Exception as e:
            st.error("Failed to parse drawn geometry: " + str(e))

st.markdown("---")
st.caption("Data: Ookla Open Data — CC BY-NC-SA 4.0")
st.markdown("**Attribution:** Ookla Open Data — https://github.com/teamookla/ookla-open-data")
