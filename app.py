"""Streamlit app for Ookla Johor Explorer"""

import streamlit as st
import geopandas as gpd
from shapely.geometry import shape, Point
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from shapely.ops import unary_union
import time
from math import radians, cos, sin, asin, sqrt
import os
import subprocess

# ----------------------------------------------------------
# MUST BE FIRST STREAMLIT COMMAND
# ----------------------------------------------------------
st.set_page_config(layout='wide', page_title='Ookla Johor Explorer')

# ----------------------------------------------------------
# Now it's safe to use Streamlit UI
# ----------------------------------------------------------

# Auto-run loader if no data
if not os.path.exists("data/ookla_johor.geojson"):
    st.warning("Data not found. Running loader for the first time...")
    try:
        subprocess.run(["python", "load_ookla.py"], check=True)
        st.success("Data loaded successfully! Reloading app...")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Failed to run loader: {e}")
        st.stop()


JOHOR_CENTER = [1.4927, 103.7414]

@st.cache_data
def load_data(path='data/ookla_johor.geojson'):
    gdf = gpd.read_file(path)
    provider_cols = [c for c in gdf.columns if 'provider' in c or 'operator' in c]
    if provider_cols:
        gdf['operator'] = gdf[provider_cols[0]].fillna('Unknown').astype(str)
    else:
        gdf['operator'] = 'Unknown'
    for col in ['download_mean','upload_mean','latency_mean']:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors='coerce')
    return gdf

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))

def compute_radius_avg(gdf, center, radius_km=5.0):
    cx, cy = center
    coords = np.array([[pt.x, pt.y] for pt in gdf.geometry])
    dists = np.array([haversine(cx, cy, x, y) for x,y in coords])
    sel = gdf.loc[dists <= radius_km]
    if sel.empty:
        return pd.DataFrame()
    return sel.groupby('operator').agg(
        count=('download_mean','count'),
        download_mean=('download_mean','mean'),
        upload_mean=('upload_mean','mean'),
        latency_mean=('latency_mean','mean')
    ).reset_index()

def compute_polygon_avg(gdf, poly):
    sel = gdf[gdf.geometry.within(poly)]
    if sel.empty:
        return pd.DataFrame()
    return sel.groupby('operator').agg(
        count=('download_mean','count'),
        download_mean=('download_mean','mean'),
        upload_mean=('upload_mean','mean'),
        latency_mean=('latency_mean','mean')
    ).reset_index()


st.title('Ookla Johor — 5km / Polygon Averages')

left, right = st.columns([1,2])

# Load data (now safe)
try:
    gdf = load_data()
except Exception as e:
    st.error(f'Failed to load data: {e}')
    st.stop()


with left:
    st.subheader('Search / Controls')
    q = st.text_input('Search place (Nominatim)', 'Johor Bahru')
    if st.button('Search'):
        geolocator = Nominatim(user_agent='ookla-johor-app')
        try:
            loc = geolocator.geocode(q, timeout=10)
            if loc:
                st.session_state['search_point'] = (loc.longitude, loc.latitude)
                st.success(f'Found: {loc.address}')
            else:
                st.error('Not found')
        except Exception as e:
            st.error('Geocoding error: ' + str(e))

    radius_km = st.number_input('Radius (km)', 1.0, 50.0, 5.0, 1.0)
    operator_filter = st.multiselect(
        'Filter operators (optional)',
        sorted(gdf['operator'].unique())
    )


with right:
    m = folium.Map(location=JOHOR_CENTER, zoom_start=9)

    # sample for speed
    sample = gdf.sample(min(len(gdf), 3000), random_state=1)
    for _, r in sample.iterrows():
        folium.CircleMarker(
            location=[r.geometry.y, r.geometry.x],
            radius=2,
            popup=f"{r['operator']} - DL: {r['download_mean']}"
        ).add_to(m)

    from folium.plugins import Draw
    Draw(export=True).add_to(m)

    if 'search_point' in st.session_state:
        sx, sy = st.session_state['search_point']
        folium.Marker([sy, sx], icon=folium.Icon(color='red')).add_to(m)

    st_map = st_folium(m, width=900, height=650, returned_objects=['all_drawings'])

    drawn = None
    if st_map and 'all_drawings' in st_map:
        dd = st_map['all_drawings']
        if isinstance(dd, list) and dd:
            drawn = dd[-1]
        elif isinstance(dd, dict) and dd:
            drawn = dd

    point = None
    if drawn:
        try:
            geom = shape(drawn.get('geometry', {}))
            if geom.geom_type == 'Point':
                point = (geom.x, geom.y)
            else:
                polygon_avg = compute_polygon_avg(gdf, geom)
                st.subheader('Polygon averages')
                st.table(polygon_avg)
        except Exception as e:
            st.error(f"Drawing parse error: {e}")

    if not point and 'search_point' in st.session_state:
        point = st.session_state['search_point']

    if point:
        rad = compute_radius_avg(gdf, point, radius_km)
        if operator_filter:
            rad = rad[rad['operator'].isin(operator_filter)]
        st.subheader(f'Radius {radius_km}km averages')
        st.table(rad)


st.markdown("---")
st.caption("Data: Ookla Open Data")
