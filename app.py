import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
import folium
from streamlit_folium import st_folium
import os
import subprocess

st.set_page_config(layout="wide")

st.title("Johor Internet Performance Map (Ookla Open Data)")

# ---------------------------
# Load data or run loader
# ---------------------------
if not os.path.exists("johor.geojson"):
    st.warning("Data not found. Running loader...")
    try:
        subprocess.check_call(["python", "load_ookla.py"])
    except Exception as e:
        st.error(f"Failed to run loader: {e}")

gdf = gpd.read_file("johor.geojson")

# ---------------------------
# Map UI
# ---------------------------
st.subheader("Search or Draw Area")

search_lat = st.number_input("Latitude", value=1.55)
search_lon = st.number_input("Longitude", value=103.6)
radius_km = st.slider("Radius (km)", 1, 10, 5)

m = folium.Map(location=[search_lat, search_lon], zoom_start=11)

# Circle
folium.Circle(
    [search_lat, search_lon],
    radius=radius_km * 1000,
    color="blue",
    fill=True,
    fill_opacity=0.1
).add_to(m)

result = st_folium(m, height=500)

# ---------------------------
# Compute ROI average
# ---------------------------
st.subheader("Average Performance in Selected Area")

circle_geom = Point(search_lon, search_lat).buffer(radius_km / 110.574)

sel = gdf[gdf.geometry.intersects(circle_geom)]

if len(sel) == 0:
    st.warning("No Ookla tiles found in this area.")
else:
    st.dataframe(sel[["avg_d_kbps", "avg_u_kbps", "avg_lat_ms", "tests", "devices"]].describe())

# ---------------------------
# License Footer
# ---------------------------
st.markdown(
"""
---
**Data Source:** Ookla Open Data  
Licensed under CC BY-NC-SA 4.0  
© Ookla, LLC  
"""
)
