"""Streamlit app for Ookla Johor Explorer

Features:
- Load preprocessed data (data/ookla_johor.geojson)
- Map with folium + streamlit_folium
- Search (Nominatim via geopy)
- Click to set point; compute 5km radius average per telco
- Polygon draw tool to compute polygon averages
"""

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

st.set_page_config(layout='wide', page_title='Ookla Johor Explorer')

JOHOR_CENTER = [1.4927, 103.7414]  # approx Johor Bahru

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
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r

def compute_radius_avg(gdf, center, radius_km=5.0):
    cx, cy = center
    coords = np.array([[pt.x, pt.y] for pt in gdf.geometry])
    dists = np.array([haversine(cx, cy, x, y) for x,y in coords])
    mask = dists <= radius_km
    sel = gdf.loc[mask]
    if sel.empty:
        return pd.DataFrame()
    grouped = sel.groupby('operator').agg(
        count=('download_mean','count'),
        download_mean=('download_mean','mean'),
        upload_mean=('upload_mean','mean'),
        latency_mean=('latency_mean','mean')
    ).reset_index()
    return grouped

def compute_polygon_avg(gdf, polygon_geom):
    sel = gdf[gdf.geometry.within(polygon_geom)]
    if sel.empty:
        return pd.DataFrame()
    grouped = sel.groupby('operator').agg(
        count=('download_mean','count'),
        download_mean=('download_mean','mean'),
        upload_mean=('upload_mean','mean'),
        latency_mean=('latency_mean','mean')
    ).reset_index()
    return grouped

st.title('Ookla Johor — 5km / Polygon Averages')

left, right = st.columns([1,2])

gdf = None
try:
    gdf = load_data()
except Exception as e:
    st.error(f'Failed to load data: {e}')
    st.info('Run `python load_ookla.py` to download and prepare data, then reload this app.')
    st.stop()

with left:
    st.subheader('Search / Controls')
    q = st.text_input('Search place (Nominatim)', 'Johor Bahru')
    if st.button('Search'):
        geolocator = Nominatim(user_agent='ookla-johor-app')
        try:
            loc = geolocator.geocode(q, timeout=10)
        except Exception as e:
            st.error('Geocoding error: ' + str(e))
            loc = None
        if loc:
            cx, cy = loc.longitude, loc.latitude
            st.session_state['search_point'] = (cx, cy)
            st.success(f'Found: {loc.address} ({loc.latitude}, {loc.longitude})')
        else:
            st.error('Not found')

    st.write('Or draw/click on the map to set a point.')
    radius_km = st.number_input('Radius (km)', min_value=1.0, max_value=50.0, value=5.0, step=1.0)
    operator_filter = st.multiselect('Filter operators (leave blank for all)', options=sorted(gdf['operator'].unique()))

with right:
    m = folium.Map(location=JOHOR_CENTER, zoom_start=9, tiles='OpenStreetMap')

    sample_n = min(len(gdf), 3000)
    sample = gdf.sample(sample_n, random_state=1)
    for _, r in sample.iterrows():
        popup = f"Operator: {r.get('operator','')}<br>Download: {r.get('download_mean', '')}"
        folium.CircleMarker(location=[r.geometry.y, r.geometry.x], radius=2, popup=popup).add_to(m)

    from folium.plugins import Draw
    draw = Draw(export=True)
    draw.add_to(m)

    if 'search_point' in st.session_state:
        sx, sy = st.session_state['search_point']
        folium.Marker(location=[sy, sx], icon=folium.Icon(color='red'), popup='Search Point').add_to(m)

    st_map = st_folium(m, width=900, height=650, returned_objects=['all_drawings'])

    drawn = None
    if st_map and 'all_drawings' in st_map:
        drawings = st_map['all_drawings']
        if isinstance(drawings, list) and len(drawings) > 0:
            drawn = drawings[-1]
        elif isinstance(drawings, dict) and drawings:
            drawn = drawings

    point = None
    if drawn:
        try:
            if drawn.get('geometry'):
                geom = shape(drawn['geometry'])
                if geom.geom_type == 'Point':
                    point = (geom.x, geom.y)
                else:
                    poly = geom
                    polygon_avg = compute_polygon_avg(gdf, poly)
                    if not polygon_avg.empty:
                        st.subheader('Polygon averages')
                        st.table(polygon_avg.sort_values('download_mean', ascending=False))
                    else:
                        st.info('No data points inside polygon.')
            else:
                typ = drawn.get('type')
                coords = drawn.get('coordinates') or drawn.get('geometry', {}).get('coordinates')
                if typ == 'Point' and coords:
                    point = (coords[0], coords[1])
        except Exception as e:
            st.error('Failed to parse drawn geometry: ' + str(e))

    if point is None and 'search_point' in st.session_state:
        sx, sy = st.session_state['search_point']
        point = (sx, sy)

    if point:
        rad = compute_radius_avg(gdf, point, radius_km=radius_km)
        if not rad.empty:
            if operator_filter:
                rad = rad[rad['operator'].isin(operator_filter)]
            st.subheader(f'Radius {radius_km} km averages (center {point[1]:.5f}, {point[0]:.5f})')
            st.table(rad.sort_values('download_mean', ascending=False))
        else:
            st.info('No data points within radius.')

st.markdown('---')
st.caption('Data: Ookla Open Data (public). App: sample implementation.')
